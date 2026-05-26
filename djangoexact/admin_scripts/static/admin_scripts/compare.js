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

    function renderCompare() {
        // Filled in by later tasks.
    }

    window.renderCompare = renderCompare;
})();
