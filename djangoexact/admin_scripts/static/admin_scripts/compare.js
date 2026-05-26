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

    function renderCompare() {
        // Filled in by later tasks.
    }

    window.renderCompare = renderCompare;
})();
