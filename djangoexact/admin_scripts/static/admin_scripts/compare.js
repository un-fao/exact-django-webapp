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

    function ingestSwap(target) {
        if (!target) return;
        var nodes = target.matches && target.matches("[data-scenario-result]")
            ? [target]
            : Array.prototype.slice.call(target.querySelectorAll("[data-scenario-result]"));
        nodes.forEach(function (node) {
            var raw = node.getAttribute("data-scenario-result") || "";
            if (!raw) return;
            var result;
            try {
                result = JSON.parse(raw);
            } catch (e) {
                console.warn("compare.js: failed to parse data-scenario-result", e);
                return;
            }
            var idx = node.getAttribute("data-scenario-index");
            if (idx === null || idx === "") return;
            window.scenarioResults[idx] = {
                result: result,
                formHash: hashScenarioInputs(idx),
                runAt: Date.now(),
                stale: false,
            };
        });
        renderCompare();
    }

    document.body.addEventListener("htmx:afterSwap", function (evt) {
        ingestSwap(evt.target);
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

    function renderCompare() {
        var indices = Object.keys(window.scenarioResults).sort(function (a, b) {
            return Number(a) - Number(b);
        });
        var empty = document.getElementById("cmp-empty");
        var hasAny = indices.length > 0;
        if (empty) empty.classList.toggle("hidden", hasAny);

        renderChips(indices);
        // Charts and table will be added in later tasks.
    }

    window.renderCompare = renderCompare;
})();
