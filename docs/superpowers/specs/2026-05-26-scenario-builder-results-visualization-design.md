# Scenario Builder — Live-Compiled Results Visualization

**Date:** 2026-05-26
**Branch:** `develop` (feature branch TBD)
**Beads issue:** TBD

## Background

The admin scripts "Compile Scenarios" tool (`djangoexact/admin_scripts/`) lets a user build one or more scenarios, each containing one or more changes. Clicking **Run Scenario** in a scenario tab fires an HTMX POST to `htmx_run_scenario`, which calls `scenario_utils.stats_for_scenario` and renders `partials/scenario_results.html`.

Today the rendered partial is a flat 3-column grid of 12 numeric stats (count, sum, mean, median, std, min, max, Q1, Q3, IQR, CI 95%, CI 99%) inside the active scenario tab. Each scenario's stats render in isolation; switching between scenario tabs hides the previous result. Gaps and errors render as colored banners.

The primary user goal is **comparing scenarios side-by-side** (confirmed during brainstorming). The current UI fights that goal: scenarios live in separate tabs, only one is visible at a time, and there is no chart of any kind. The secondary signal users care about is **magnitude with uncertainty** (mean and CI 95%); distribution shape and per-change composition come third and fourth.

## Goal

Add a dedicated **Compare** tab next to the existing scenario tabs that aggregates per-scenario results into a single visual panel: a status-chip strip, a bar chart with CI 95% error bars, a row of box plots, a per-change composition stack, and a comparison table. Cross-scenario aggregation lives in the browser; the server stays stateless.

Simplify the in-tab stat grid to a one-line headline so per-scenario feedback survives without duplicating the Compare tab.

## Non-Goals

- Persisting scenarios or results across page reloads. Refresh discards work, same as today.
- A new server-side aggregation endpoint. The Compare tab reads from per-scenario HTMX responses stored in browser state.
- Changes to `build_scenario_query`, `stats_for`, or the DRF viewset `EmissionScenarioViewSet` in `djangoexact/minitool/views.py`. Those code paths and their tests are unaffected.
- Modifications to the Excel export path. `excel_export.build_scenarios_workbook` and `compile_scenarios_export` are untouched.
- Sortable charts, drill-down click-through, multi-page Compare layouts. The Compare tab is one screen.
- Heatmaps, geographic maps, time-series. Not in this iteration.
- Sharing or exporting the comparison view itself (screenshots, PDF). Out of scope.

## User Flow

1. User builds Scenario 1 in tab S1, clicks **Run Scenario** → existing HTMX response renders. Behind the scenes, JS parses the response's data attribute and stores the result in `window.scenarioResults[0]`.
2. User adds Scenario 2 via `+ Add Scenario`, builds it, clicks **Run Scenario** → same as above, stored in `window.scenarioResults[1]`.
3. User clicks the **Compare** tab → all stored results render as chips, charts, and table.
4. If the user edits Scenario 1's form afterwards, the hash of its form snapshot diverges from the stored one → Compare tab's chip for S1 turns amber with a one-click refresh button (which fires the same HTMX request as **Run Scenario** for that scenario).
5. Removing a scenario also deletes its slot from `window.scenarioResults`.

## UI

### `templates/admin_scripts/scripts/compile_scenarios.html`

- The existing `#scenario-tabs` container gains a right-aligned **Compare** tab button. CSS: `ml-auto` so it floats to the right of `+ Add Scenario`.
- A new `<div data-compare-panel class="hidden">` is appended to `#scenario-panels`. The existing `switchScenarioTab(index)` JS is extended to handle the string sentinel `"compare"`: hide all scenario panels, show the compare panel.
- Chart.js + plugins + `compare.js` are loaded at the bottom of the `{% block content %}`:
  - `<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>`
  - `<script src="https://cdn.jsdelivr.net/npm/@sgratzl/chartjs-chart-boxplot@4"></script>`
  - `<script src="https://cdn.jsdelivr.net/npm/chartjs-chart-error-bars@4"></script>`
  - `<script src="{% static 'admin_scripts/compare.js' %}"></script>`
  - All four with SRI attributes matching the pattern of the existing htmx/Tom Select includes.

### `templates/admin_scripts/partials/scenario_panel.html` (modified, minimal)

The existing initial-render include is updated to pass `scenario_index` through, so the new partial wrapper has the value available even when rendered at GET time (currently dead code — `compile_scenarios` never sets `scenario.statistics` on GET — but kept consistent):

```
{% include "admin_scripts/partials/scenario_results.html" with statistics=scenario.statistics scenario_index=scenario_index %}
```

No other changes to this template.

### `templates/admin_scripts/partials/compare_panel.html` (new)

Empty mount points. All content is rendered by `compare.js` on activation and on every result update.

```
<div data-compare-panel-content>
  <div id="cmp-empty" class="text-sm text-gray-500 p-6 text-center">
    Run at least one scenario to populate the comparison view.
  </div>
  <div id="cmp-chips" class="hidden flex flex-wrap gap-2 mb-4"></div>
  <div id="cmp-bar" class="hidden bg-white border border-gray-200 rounded-lg p-5 mb-4">
    <h3 class="text-md font-semibold text-gray-900 mb-3">Mean &plusmn; CI 95%</h3>
    <canvas></canvas>
  </div>
  <div id="cmp-box" class="hidden bg-white border border-gray-200 rounded-lg p-5 mb-4">
    <h3 class="text-md font-semibold text-gray-900 mb-3">Distribution</h3>
    <canvas></canvas>
  </div>
  <div id="cmp-composition" class="hidden bg-white border border-gray-200 rounded-lg p-5 mb-4">
    <h3 class="text-md font-semibold text-gray-900 mb-3">Per-change contribution to sum</h3>
    <canvas></canvas>
  </div>
  <div id="cmp-table" class="hidden bg-white border border-gray-200 rounded-lg p-5 mb-4">
    <h3 class="text-md font-semibold text-gray-900 mb-3">All statistics</h3>
    <div data-cmp-table-body></div>
  </div>
</div>
```

When `window.scenarioResults` is empty, `#cmp-empty` is the only visible block. When at least one slot is populated, `#cmp-empty` is hidden and the four chart/table blocks are shown.

### `templates/admin_scripts/partials/scenario_results.html` (modified)

The entire partial is restructured around a single outermost wrapper that always carries the data attributes — so `compare.js`'s `htmx:afterSwap` listener fires reliably regardless of whether the result is a stat headline, a gap banner, or an error:

```
<div data-scenario-result='{{ result_json|escape }}'
     data-scenario-index='{{ scenario_index }}'>

    {% if statistics and statistics.count > 0 %}
    <div class="bg-white border border-gray-200 rounded-lg p-5 mt-4">
        <h3 class="text-md font-semibold text-gray-900 mb-3">Results</h3>
        <p class="text-sm text-gray-700">
            <span class="text-gray-500">n =</span> <span class="font-medium">{{ statistics.count }}</span>
            &nbsp;&middot;&nbsp; <span class="text-gray-500">sum =</span> <span class="font-medium">{{ statistics.sum_total|floatformat:2 }}</span>
            &nbsp;&middot;&nbsp; <span class="text-gray-500">mean =</span> <span class="font-medium">{{ statistics.mean|floatformat:4 }} &plusmn; {{ statistics.ci_95|floatformat:4 }}</span>
            <span class="text-xs text-gray-400">(CI 95%)</span>
        </p>
        <p class="text-xs text-gray-400 mt-2">Full breakdown in the Compare tab.</p>
    </div>
    {% endif %}

    {# Gap, error, not_computed banners — kept verbatim from current partial #}
    {% if gaps %} ... {% endif %}
    {% if error %} ... {% endif %}
    {% if not_computed %} ... {% endif %}

</div>
```

- The outer `<div>` is always rendered, so the data attributes are always present after an HTMX swap. The inner blocks toggle as before.
- `result_json` is HTML-escaped via Django's `escape` filter; the raw payload contains no user-controlled HTML strings (only numbers + catalog-derived module/field labels), but escaping is defense-in-depth.
- The `data-scenario-index` attribute is read by `compare.js` to key the result into the right slot.
- The existing `{% if statistics.count == 0 %}` "No matching records found" branch becomes redundant — when `count == 0` and no gaps/error, the outer wrapper is still emitted (so the Compare tab can show a 🔴 chip) but no headline is rendered inside. A small muted line "No matching records for this scenario." can replace it for in-tab feedback.

## Backend

### `djangoexact/admin_scripts/scenario_utils.py`

#### Modified: `stats_for_scenario(changes, global_filters) -> dict`

Returns the existing dict plus three new keys:

```
{
    ...existing keys...,
    "outliers_low":  int,                          # count of values below  Q1 - 1.5*IQR
    "outliers_high": int,                          # count of values above  Q3 + 1.5*IQR
    "per_change": [
        {
            "label":      str,    # f"{module_type}: {start_value} → {end_value}"
                                  #   (no unit suffix; the unit is shown in the chart legend if != 1)
            "module_type": str,
            "field":       str,
            "from_value":  str,
            "to_value":    str,
            "unit":        float,
            "count":       int,
            "sum":         float,
            "mean":        float | None,
        },
        ...one entry per change with a module_type, in input order...
    ],
}
```

- `outliers_low` / `outliers_high` are computed in a **single additional pass** over the same `scaled_values` list that the function already materializes. No extra DB query. Both are `0` when `n < 4` (no IQR defined).
- `per_change` is built by re-using `_build_single_change_q` per change to fetch totals, applying the per-change `unit`, and computing count/sum/mean over those scaled values. This is **one extra `values_list` per change**; the same query each change already runs for the aggregate computation is not re-done — the per-change scaled-totals list is captured once and used for both the aggregate `scaled_values.extend(...)` and the per-change rollup. The function's overall query count remains `O(number_of_changes)`, identical to today.
- Changes with no `module_type` are skipped (already the case for the aggregate); they do **not** appear in `per_change`.
- `_descriptive_stats_from_values` is unchanged. The outlier counts are computed at the top level of `stats_for_scenario`, not inside the descriptive-stats helper.

#### Unchanged

`stats_for`, `build_scenario_query`, `_build_single_change_q`, `_descriptive_stats_from_values`, `_coerce_unit`, `_create_flexible_value_query`. All existing callers and tests keep working.

### `djangoexact/admin_scripts/views.py`

#### Modified: `htmx_run_scenario`

Adds two new keys to the context:

- `scenario_index` — the index parsed from POST (`request.POST.get("scenario_index", "0")`), exposed so the partial can render `data-scenario-index='{{ scenario_index }}'`.
- `result_json` — a JSON-serialized object the Compare tab consumes:

```
{
    "scenario_index":   "<int as string, matching the POST prefix>",
    "scenario_name":    "<from POST data: scenario-N-scenario_name>",
    "category":         "<from POST data: scenario-N-category>",
    "statistics":       { ...full stats dict from stats_for_scenario, always present... },
    "gaps":             [ {module_type, field, from_value, to_value}, ... ] | [],
    "error":            "<string>" | null,
    "not_computed":     bool
}
```

`statistics` is **always** included in `result_json`, even when `count == 0` or when gaps are detected. In those cases the dict carries `count: 0` and `None` for the other fields — same shape as `_descriptive_stats_from_values([])`. This lets the Compare tab key off `result.statistics.count === 0` plus `result.gaps.length` without separate code paths.

`scenario_name` and `category` are included so the Compare tab can label bars with the user-chosen name (falling back to "Scenario N+1" when blank). The view reads these from POST data — no new fields, just expose what's already there.

Encoded with `json.dumps(..., default=str)` so any `Decimal` returned by Django aggregates serializes cleanly.

#### Unchanged

All other view functions, the `compile_scenarios` GET view, every htmx_* partial, and `compile_scenarios_export`. The Excel path consumes scenarios from POST directly and is unaffected.

## Frontend

### `static/admin_scripts/compare.js` (new)

Vanilla JS, no build step. Loaded via `<script src>` (not a module). Exposes nothing on `window` except `window.scenarioResults` (read-only convention; mutated only by this file).

#### Responsibilities

1. **Result ingestion.** Listen for `htmx:afterSwap` on `document.body`. When the swapped target (or any descendant) carries `[data-scenario-result]`, parse the JSON, snapshot the corresponding scenario's form-input hash (see below), and write `{ result, formHash, runAt: Date.now() }` into `window.scenarioResults[scenarioIndex]`.

2. **Stale detection.** Listen for `input` and `change` events on `document.body`. When the event target lives inside `[data-scenario-panel="N"]`, recompute the form hash for that scenario; compare to the stored hash; toggle a `stale` flag on `window.scenarioResults[N]`. Trigger a Compare tab re-render if the compare panel is currently visible.

3. **Compare tab activation.** Patch `switchScenarioTab` (or wrap it via a follow-up event hook) to detect the `"compare"` sentinel and:
   - Hide all scenario panels and the existing tab-indicator styling.
   - Show `[data-compare-panel]`.
   - Call `renderCompare()`.

4. **Rendering.** `renderCompare()` reads `window.scenarioResults`, fills in chips / charts / table mount points. Charts are destroyed and re-created on each render (Chart.js idiom; the chart count is small).

5. **Scenario removal.** When a scenario panel is removed by the existing "Remove Scenario" button, also `delete window.scenarioResults[N]` and re-render. Hook via a `MutationObserver` on `#scenario-panels` watching for removed children with a `data-scenario-panel` attribute.

#### Form-hash function

```
function hashScenarioInputs(scenarioIndex) {
    const panel = document.querySelector(`[data-scenario-panel="${scenarioIndex}"]`);
    if (!panel) return null;
    const parts = [];
    panel.querySelectorAll('input, select').forEach(el => {
        if (el.type === 'hidden') return;  // CSRF token etc.
        const name = el.name || el.id || '';
        if (el.multiple) {
            const vals = Array.from(el.selectedOptions).map(o => o.value).sort();
            parts.push(`${name}=[${vals.join(',')}]`);
        } else {
            parts.push(`${name}=${el.value}`);
        }
    });
    // Also include global filters — changing region invalidates every scenario.
    document.querySelectorAll('[name^="global_filter_"]').forEach(el => {
        const vals = el.multiple ? Array.from(el.selectedOptions).map(o => o.value).sort() : [el.value];
        parts.push(`${el.name}=[${vals.join(',')}]`);
    });
    return parts.join('|');
}
```

A plain string concatenation is enough; collisions are not a security concern.

#### Chip thresholds

Single constants block at the top of the file. From Section 4 of the brainstorm:

```
const THRESHOLDS = {
    SMALL_SAMPLE: 30,                  // count < 30 → amber "small sample"
    WIDE_CI_RATIO: 0.5,                // 2*ci_95 / |mean| > 0.5  → amber "wide CI"
    OUTLIER_MIN_COUNT: 5,              // outliers must be > max(5, 5% of n)
    OUTLIER_RATIO: 0.05,
};
```

Chip precedence (worst rule wins):

1. 🔴 No data — `result.statistics.count === 0`, or `result.gaps.length > 0`, or `result.error`, or scenario was never run.
2. 🟠 Stale — `slot.stale === true`.
3. 🟠 Small sample — `count < 30`.
4. 🟠 Wide CI — `count >= 30 && |mean| > 1e-9 && (2 * ci_95) / Math.abs(mean) > 0.5`.
5. 🟠 Outliers — `outliers_low + outliers_high > Math.max(5, 0.05 * count)`.
6. 🟢 Fine — none of the above.

Hover tooltip on every chip shows the actual numbers: `n=18, ci_95=±0.34, mean=0.91, outliers=2`.

The "Stale" chip carries a refresh button that fires the same HTMX request the scenario's Run button does, via `htmx.trigger(runButton, 'click')` (htmx 2.x has `htmx.trigger` for programmatic dispatch). The "No data — never run" chip links to the scenario tab via a click handler that calls `switchScenarioTab(N)`.

#### Charts

- **Mean ± CI 95% bar (`#cmp-bar canvas`)**: `chartjs-chart-error-bars` `barWithErrorBars` chart type. One dataset, one bar per scenario, each bar coloured by `colorForScenario(index)`. Error bar bounds: `[mean - ci_95, mean + ci_95]`. Tooltip: scenario name, mean, ± CI 95%, count.
- **Box-plot row (`#cmp-box canvas`)**: `chartjs-chart-boxplot` `boxplot` chart type. Each scenario's data point is its `{min, q1, median, q3, max}` directly (Chart.js boxplot accepts pre-computed quantiles via `coef: 0` and `quantiles: 'precomputed'`). Outlier counts shown as inline text overlay above each box ("· 12 outliers above"), not as plotted points.
- **Composition stack (`#cmp-composition canvas`)**: Chart.js core stacked bar. One stacked bar per scenario, segments = `result.statistics.per_change` entries, each segment's value = that change's `sum`. Legend shows each unique change label across all scenarios; segments with the same label across scenarios share a colour (deterministic colour from a hash of the label).
- **Comparison table (`#cmp-table div[data-cmp-table-body]`)**: a plain `<table>` rendered by `compare.js`. Rows = scenarios, columns = count, sum, mean, median, std, min, max, Q1, Q3, CI 95%. Header row + scenario rows; no sort interactivity in this iteration (out of scope per Non-Goals).

#### Colour palette

`colorForScenario(index)` cycles through Tailwind blue-500, emerald-500, amber-500, rose-500, violet-500, cyan-500, fuchsia-500, lime-500 (eight scenarios is plenty; the existing UI doesn't limit scenario count, but more than eight is degenerate UX). The same palette is applied to the scenario tab button's text colour so visual identity is consistent between tab strip and Compare tab.

## CDN dependency notes

All three Chart.js scripts are pinned to major versions (`@4`) and loaded with `integrity` SRI attributes matching the existing pattern. If the project later moves admin_scripts to webpack-bundled assets, these CDN tags become candidates for the bundle — out of scope for this change. The existing `# nosemgrep: html.security.audit.missing-integrity.missing-integrity` comment pattern from `base.html` is followed for the Tailwind Play CDN; the chart libraries get real SRI hashes.

## Testing

- `djangoexact/admin_scripts/tests/test_views.py` — extend `htmx_run_scenario` tests to assert the `result_json` context key is present and parseable, and that its `statistics` block matches the partial-rendered numbers.
- `djangoexact/admin_scripts/tests/` — new unit tests for `stats_for_scenario`:
  - `outliers_low` and `outliers_high` correctly count records past the 1.5·IQR fences.
  - `per_change` returns one entry per change in input order, with correct `count`/`sum`/`mean`, skipping changes that have no `module_type`.
  - With a single change and `unit=1.0`, `per_change[0].sum` equals the aggregate `sum_total` (sanity).
- Frontend behaviour (chip thresholds, hash diff → stale flag, chart render) is **not** unit-tested. Manual QA on a CI-equipped machine per the per-change-units design's precedent. (Sandbox cannot run the Django suite locally; rely on CI.)

## Risks & open questions

- **CDN availability for Chart.js plugins.** jsdelivr serves all three. If the project pins to a different CDN, the URLs need adjusting.
- **Chart.js boxplot pre-computed quantiles.** The `@sgratzl/chartjs-chart-boxplot` plugin supports passing pre-computed `{min, q1, median, q3, max}` via the `items` parameter on each data point. If this API changes between minor versions, the chart-init code needs adjustment — pin to `@4` exact major.
- **Form-hash false positives.** Typing in an `<input>` then backspacing back to the original value still fires `input` events; the hash recomputes but matches the stored one → no false stale. Tom Select's hidden multi-select firing `change` on every option toggle is fine — same hash function handles it.
- **Per-change label duplication.** Two scenarios might have a change with an identical label (e.g. "Annual Cropland: ConventionalTill → NoTill"). They get the same colour segment in the composition stack — that's intended and desired.
- **No persistence.** Refreshing the page wipes `window.scenarioResults`. Same constraint as today; no behavioural regression.

## File-change summary

```
djangoexact/admin_scripts/scenario_utils.py            modify   stats_for_scenario gains outlier counts + per_change
djangoexact/admin_scripts/views.py                     modify   htmx_run_scenario passes scenario_index + result_json
djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html
                                                       modify   Compare tab, chart CDNs, compare.js include
djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_panel.html
                                                       modify   pass scenario_index through the initial-render include
djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_results.html
                                                       modify   data-* outer wrapper, slim headline, banners preserved
djangoexact/admin_scripts/templates/admin_scripts/partials/compare_panel.html
                                                       create   mount points for chips/charts/table
djangoexact/admin_scripts/static/admin_scripts/compare.js
                                                       create   client-side state, stale detection, chart rendering
djangoexact/admin_scripts/tests/test_views.py          modify   assert result_json shape + scenario_index
djangoexact/admin_scripts/tests/test_scenario_utils.py modify   (or create) outlier + per_change tests
```
