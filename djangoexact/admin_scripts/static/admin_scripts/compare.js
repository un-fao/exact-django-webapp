/* admin_scripts: Compile Scenarios -- comparison view.
 *
 * Single owner of the cross-scenario state used by the Compare tab.
 * Exposes window.scenarioResults (read-only convention) and window.renderCompare()
 * which is called by switchScenarioTab when the user activates the Compare tab.
 */
(function () {
    "use strict";

    var THRESHOLDS = {
        SMALL_SAMPLE: 30,
        WIDE_CI_RATIO: 0.5,
        OUTLIER_MIN_COUNT: 5,
        OUTLIER_RATIO: 0.05,
    };

    var PALETTE = [
        "#3b82f6", "#10b981", "#f59e0b", "#f43f5e",
        "#8b5cf6", "#06b6d4", "#d946ef", "#84cc16",
    ];

    window.scenarioResults = window.scenarioResults || {};

    function colorForScenario(index) {
        return PALETTE[Number(index) % PALETTE.length];
    }

    function hashScenarioInputs(scenarioIndex) {
        var panel = document.querySelector('[data-scenario-panel="' + scenarioIndex + '"]');
        if (!panel) return null;
        var parts = [];
        panel.querySelectorAll("input, select").forEach(function (el) {
            if (el.type === "hidden") return;
            var name = el.name || el.id || "";
            if (el.multiple) {
                var vals = Array.from(el.selectedOptions).map(function (o) { return o.value; }).sort();
                parts.push(name + "=[" + vals.join(",") + "]");
            } else {
                parts.push(name + "=" + el.value);
            }
        });
        document.querySelectorAll('[name^="global_filter_"]').forEach(function (el) {
            if (el.type === "hidden") return;
            var vals = el.multiple
                ? Array.from(el.selectedOptions).map(function (o) { return o.value; }).sort()
                : [el.value];
            parts.push(el.name + "=[" + vals.join(",") + "]");
        });
        return parts.join("|");
    }

    function ingestNode(node) {
        if (!node || node.nodeType !== 1) return false;
        var raw = node.getAttribute("data-scenario-result") || "";
        if (!raw) return false;
        var result;
        try {
            result = JSON.parse(raw);
        } catch (e) {
            console.warn("compare.js: failed to parse data-scenario-result", e, raw);
            return false;
        }
        var idx = node.getAttribute("data-scenario-index");
        if (idx === null || idx === "") return false;
        window.scenarioResults[idx] = {
            result: result,
            formHash: hashScenarioInputs(idx),
            runAt: Date.now(),
            stale: false,
        };
        return true;
    }

    function ingestSwap(target) {
        var ingested = 0;
        // Try the swap target itself, then its descendants.
        if (target && target.nodeType === 1) {
            if (target.matches && target.matches("[data-scenario-result]")) {
                if (ingestNode(target)) ingested++;
            }
            if (target.querySelectorAll) {
                Array.prototype.forEach.call(
                    target.querySelectorAll("[data-scenario-result]"),
                    function (n) { if (ingestNode(n)) ingested++; }
                );
            }
        }
        // Fallback: if the swap target didn't carry the wrapper (event target
        // may be the request initiator in some HTMX versions), scan everything.
        if (ingested === 0) {
            Array.prototype.forEach.call(
                document.querySelectorAll("[data-scenario-result]"),
                function (n) { ingestNode(n); }
            );
        }
        renderCompare();
    }

    document.body.addEventListener("htmx:afterSwap", function (evt) {
        // HTMX 2.x: detail.target is the documented swap target. evt.target is
        // also the swap target in most cases, but detail.target is canonical.
        var t = (evt.detail && evt.detail.target) || evt.target;
        ingestSwap(t);
    });

    function markStaleIfChanged(scenarioIndex) {
        var slot = window.scenarioResults[scenarioIndex];
        if (!slot) return;
        var currentHash = hashScenarioInputs(scenarioIndex);
        if (currentHash !== slot.formHash) {
            slot.stale = true;
            renderCompare();
        }
    }

    function handleFormMutation(evt) {
        var panel = evt.target.closest && evt.target.closest("[data-scenario-panel]");
        if (panel) {
            var idx = panel.getAttribute("data-scenario-panel");
            markStaleIfChanged(idx);
            return;
        }
        // Global filter change invalidates every recorded scenario.
        if (evt.target.name && evt.target.name.indexOf("global_filter_") === 0) {
            Object.keys(window.scenarioResults).forEach(function (idx) {
                markStaleIfChanged(idx);
            });
        }
    }

    document.body.addEventListener("input", handleFormMutation, true);
    document.body.addEventListener("change", handleFormMutation, true);

    function observeScenarioRemoval() {
        var container = document.getElementById("scenario-panels");
        if (!container) return;
        var obs = new MutationObserver(function (mutations) {
            var anyRemoved = false;
            mutations.forEach(function (m) {
                m.removedNodes.forEach(function (node) {
                    if (node.nodeType !== 1) return;
                    var idx = node.getAttribute && node.getAttribute("data-scenario-panel");
                    if (idx !== null && idx !== undefined && idx in window.scenarioResults) {
                        delete window.scenarioResults[idx];
                        anyRemoved = true;
                    }
                });
            });
            if (anyRemoved) renderCompare();
        });
        obs.observe(container, { childList: true });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", observeScenarioRemoval);
    } else {
        observeScenarioRemoval();
    }

    function classifyChip(slot) {
        // Worst rule wins. Returns { level: 'red'|'amber'|'green', label, detail }.
        var r = slot && slot.result;
        if (!r) return { level: "red", label: "Never run", detail: "Click to run this scenario." };
        if (r.error) return { level: "red", label: "Error", detail: r.error };
        if (r.gaps && r.gaps.length > 0) return { level: "red", label: "No data", detail: r.gaps.length + " missing combination(s)." };
        var stats = r.statistics || {};
        if ((stats.count || 0) === 0) return { level: "red", label: "No matching records", detail: "n = 0" };
        if (slot.stale) return { level: "amber", label: "Stale", detail: "Edited since last run." };
        if (stats.count < THRESHOLDS.SMALL_SAMPLE) {
            return { level: "amber", label: "Small sample", detail: "n = " + stats.count };
        }
        if (stats.mean !== null && Math.abs(stats.mean) > 1e-9 && stats.ci_95 !== null) {
            var ratio = (2 * stats.ci_95) / Math.abs(stats.mean);
            if (ratio > THRESHOLDS.WIDE_CI_RATIO) {
                return { level: "amber", label: "Wide CI", detail: "2*ci_95/|mean| = " + ratio.toFixed(2) };
            }
        }
        var outliers = (stats.outliers_low || 0) + (stats.outliers_high || 0);
        var outlierFloor = Math.max(THRESHOLDS.OUTLIER_MIN_COUNT, THRESHOLDS.OUTLIER_RATIO * stats.count);
        if (outliers > outlierFloor) {
            return { level: "amber", label: "Outliers", detail: outliers + " past 1.5*IQR" };
        }
        return { level: "green", label: "Fine", detail: "n = " + stats.count };
    }

    function scenarioLabel(idx, slot) {
        var r = slot && slot.result;
        var n = (r && r.scenario_name) || "";
        return n || ("Scenario " + (Number(idx) + 1));
    }

    function tooltipText(slot) {
        var s = (slot && slot.result && slot.result.statistics) || {};
        var pieces = [];
        if (s.count !== undefined) pieces.push("n=" + s.count);
        if (s.mean !== null && s.mean !== undefined) pieces.push("mean=" + Number(s.mean).toFixed(4));
        if (s.ci_95 !== null && s.ci_95 !== undefined) pieces.push("ci_95=±" + Number(s.ci_95).toFixed(4));
        var outliers = (s.outliers_low || 0) + (s.outliers_high || 0);
        if (outliers) pieces.push("outliers=" + outliers);
        return pieces.join(", ");
    }

    var charts = {};  // key: mount id, value: Chart instance (destroyed before each re-render)

    function destroyChart(key) {
        if (charts[key]) {
            charts[key].destroy();
            delete charts[key];
        }
    }

    function renderChips(indices) {
        var container = document.getElementById("cmp-chips");
        if (!container) return;
        container.innerHTML = "";
        if (indices.length === 0) {
            container.classList.add("hidden");
            return;
        }
        container.classList.remove("hidden");
        var COLORS = {
            red: "bg-red-50 border-red-200 text-red-700",
            amber: "bg-amber-50 border-amber-200 text-amber-700",
            green: "bg-emerald-50 border-emerald-200 text-emerald-700",
        };
        indices.forEach(function (idx) {
            var slot = window.scenarioResults[idx];
            var chip = classifyChip(slot);
            var btn = document.createElement("button");
            btn.type = "button";
            btn.title = tooltipText(slot);
            btn.className = "inline-flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-medium " + COLORS[chip.level];
            btn.innerHTML = "<span class=\"font-semibold\"></span><span></span>";
            btn.children[0].textContent = scenarioLabel(idx, slot);
            btn.children[1].textContent = chip.label;
            btn.addEventListener("click", function () {
                if (chip.label === "Stale" || chip.label === "Never run") {
                    // Selector matches the URL fragment from
                    // urls.py: 'compile-scenarios/htmx/run-scenario/'
                    var runButton = document.querySelector(
                        '[data-scenario-panel="' + idx + '"] button[hx-post*="run-scenario"]'
                    );
                    if (runButton && window.htmx) {
                        window.htmx.trigger(runButton, "click");
                        return;
                    }
                }
                if (window.switchScenarioTab) window.switchScenarioTab(idx);
            });
            container.appendChild(btn);
        });
    }

    function renderBarChart(indices) {
        var mount = document.getElementById("cmp-bar");
        if (!mount) return;
        destroyChart("bar");
        var renderable = indices.filter(function (idx) {
            var s = window.scenarioResults[idx];
            return s && s.result && s.result.statistics && s.result.statistics.count > 0
                   && s.result.statistics.mean !== null;
        });
        if (renderable.length === 0) {
            mount.classList.add("hidden");
            return;
        }
        mount.classList.remove("hidden");
        var canvas = mount.querySelector("canvas");
        var labels = renderable.map(function (idx) {
            return scenarioLabel(idx, window.scenarioResults[idx]);
        });
        var data = renderable.map(function (idx) {
            var s = window.scenarioResults[idx].result.statistics;
            var ci = s.ci_95 || 0;
            return { y: s.mean, yMin: s.mean - ci, yMax: s.mean + ci };
        });
        var colors = renderable.map(function (idx) { return colorForScenario(idx); });

        charts.bar = new Chart(canvas, {
            type: "barWithErrorBars",
            data: {
                labels: labels,
                datasets: [{
                    label: "Mean",
                    data: data,
                    backgroundColor: colors,
                    borderColor: colors,
                    errorBarColor: "#374151",
                    errorBarWhiskerColor: "#374151",
                }],
            },
            options: {
                indexAxis: "x",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                var d = ctx.raw || {};
                                var s = window.scenarioResults[renderable[ctx.dataIndex]].result.statistics;
                                return [
                                    "mean: " + Number(d.y).toFixed(4),
                                    "CI 95%: ±" + Number(s.ci_95 || 0).toFixed(4),
                                    "n: " + s.count,
                                ];
                            },
                        },
                    },
                },
                scales: {
                    y: { beginAtZero: false },
                },
            },
        });
    }

    function renderBoxPlot(indices) {
        var mount = document.getElementById("cmp-box");
        if (!mount) return;
        destroyChart("box");
        var renderable = indices.filter(function (idx) {
            var s = window.scenarioResults[idx];
            return s && s.result && s.result.statistics && s.result.statistics.count > 0
                   && s.result.statistics.q1 !== null && s.result.statistics.q3 !== null;
        });
        if (renderable.length === 0) {
            mount.classList.add("hidden");
            return;
        }
        mount.classList.remove("hidden");
        var canvas = mount.querySelector("canvas");
        var labels = renderable.map(function (idx) {
            return scenarioLabel(idx, window.scenarioResults[idx]);
        });
        var data = renderable.map(function (idx) {
            var s = window.scenarioResults[idx].result.statistics;
            return {
                min: s.min,
                q1: s.q1,
                median: s.median,
                q3: s.q3,
                max: s.max,
                items: [s.min, s.q1, s.median, s.q3, s.max],
            };
        });
        var colors = renderable.map(function (idx) { return colorForScenario(idx) + "55"; });
        var borderColors = renderable.map(function (idx) { return colorForScenario(idx); });

        charts.box = new Chart(canvas, {
            type: "boxplot",
            data: {
                labels: labels,
                datasets: [{
                    label: "Distribution",
                    data: data,
                    backgroundColor: colors,
                    borderColor: borderColors,
                    borderWidth: 1,
                    outlierStyle: "none",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                var d = ctx.raw || {};
                                var s = window.scenarioResults[renderable[ctx.dataIndex]].result.statistics;
                                return [
                                    "min: " + Number(d.min).toFixed(4),
                                    "Q1: " + Number(d.q1).toFixed(4),
                                    "median: " + Number(d.median).toFixed(4),
                                    "Q3: " + Number(d.q3).toFixed(4),
                                    "max: " + Number(d.max).toFixed(4),
                                    "outliers: " + ((s.outliers_low || 0) + (s.outliers_high || 0)),
                                ];
                            },
                        },
                    },
                },
            },
        });
    }

    function colorForLabel(label) {
        // FNV-like 32-bit hash, mapped into the PALETTE.
        var h = 2166136261;
        for (var i = 0; i < label.length; i++) {
            h ^= label.charCodeAt(i);
            h = (h * 16777619) >>> 0;
        }
        return PALETTE[h % PALETTE.length];
    }

    function renderComposition(indices) {
        var mount = document.getElementById("cmp-composition");
        if (!mount) return;
        destroyChart("composition");
        var renderable = indices.filter(function (idx) {
            var s = window.scenarioResults[idx];
            var pc = s && s.result && s.result.statistics && s.result.statistics.per_change;
            return pc && pc.length > 0;
        });
        if (renderable.length === 0) {
            mount.classList.add("hidden");
            return;
        }
        mount.classList.remove("hidden");
        var canvas = mount.querySelector("canvas");

        // Collect the union of change labels across all scenarios.
        var labelSet = {};
        renderable.forEach(function (idx) {
            window.scenarioResults[idx].result.statistics.per_change.forEach(function (pc) {
                labelSet[pc.label] = true;
            });
        });
        var allLabels = Object.keys(labelSet);

        var datasets = allLabels.map(function (label) {
            return {
                label: label,
                backgroundColor: colorForLabel(label),
                data: renderable.map(function (idx) {
                    var pc = window.scenarioResults[idx].result.statistics.per_change;
                    var match = pc.find(function (e) { return e.label === label; });
                    return match ? match.sum : 0;
                }),
            };
        });

        var scenarioLabels = renderable.map(function (idx) {
            return scenarioLabel(idx, window.scenarioResults[idx]);
        });

        charts.composition = new Chart(canvas, {
            type: "bar",
            data: { labels: scenarioLabels, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom" },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                return ctx.dataset.label + ": " + Number(ctx.parsed.y).toFixed(4);
                            },
                        },
                    },
                },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true },
                },
            },
        });
    }

    function fmt(v, places) {
        if (v === null || v === undefined) return "n/a";
        return Number(v).toFixed(places === undefined ? 4 : places);
    }

    function renderTable(indices) {
        var mount = document.getElementById("cmp-table");
        if (!mount) return;
        var body = mount.querySelector("[data-cmp-table-body]");
        if (!body) return;
        if (indices.length === 0) {
            mount.classList.add("hidden");
            body.innerHTML = "";
            return;
        }
        mount.classList.remove("hidden");

        var columns = [
            { key: "count",     label: "n",         places: 0 },
            { key: "sum_total", label: "Sum",       places: 2 },
            { key: "mean",      label: "Mean",      places: 4 },
            { key: "median",    label: "Median",    places: 4 },
            { key: "std",       label: "Std",       places: 4 },
            { key: "min",       label: "Min",       places: 4 },
            { key: "max",       label: "Max",       places: 4 },
            { key: "q1",        label: "Q1",        places: 4 },
            { key: "q3",        label: "Q3",        places: 4 },
            { key: "ci_95",     label: "CI 95%",    places: 4 },
        ];

        var thead = "<thead><tr class=\"text-left text-xs text-gray-500 border-b\">"
            + "<th class=\"px-3 py-2\">Scenario</th>"
            + columns.map(function (c) {
                return "<th class=\"px-3 py-2 text-right\">" + c.label + "</th>";
            }).join("")
            + "</tr></thead>";

        var rows = indices.map(function (idx) {
            var slot = window.scenarioResults[idx];
            var s = (slot && slot.result && slot.result.statistics) || {};
            var name = scenarioLabel(idx, slot);
            var color = colorForScenario(idx);
            var cells = columns.map(function (c) {
                return "<td class=\"px-3 py-2 text-right font-mono text-xs\">" + fmt(s[c.key], c.places) + "</td>";
            }).join("");
            return "<tr class=\"border-b last:border-b-0\">"
                + "<td class=\"px-3 py-2 text-sm font-medium\" style=\"color:" + color + "\">"
                + escapeText(name) + "</td>" + cells + "</tr>";
        }).join("");

        body.innerHTML = "<table class=\"min-w-full text-sm\">" + thead + "<tbody>" + rows + "</tbody></table>";
    }

    function escapeText(s) {
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#x27;");
    }

    function renderCompare() {
        var indices = Object.keys(window.scenarioResults).sort(function (a, b) {
            return Number(a) - Number(b);
        });
        var empty = document.getElementById("cmp-empty");
        var hasAny = indices.length > 0;
        if (empty) empty.classList.toggle("hidden", hasAny);

        renderChips(indices);
        renderBarChart(indices);
        renderBoxPlot(indices);
        renderComposition(indices);
        renderTable(indices);
    }

    window.renderCompare = renderCompare;
})();
