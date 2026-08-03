# Multi-Scenario Support — Design Document

**Date:** 2026-03-04
**Branch:** feature/admin-scripts
**Builds on:** `docs/plans/2026-03-03-compile-scenarios-ui-design.md`

## Goal

Extend the compile-scenarios page to support **multiple scenarios** in a tab-based UI, each with its own name, category, changes, and per-scenario results — while sharing global filters across all scenarios.

## Requirements

- **Tab-based switching** — each scenario in its own tab/panel
- **Shared global filters** — soil type, region applied to all scenarios
- **Per-scenario run** — each scenario has its own "Run" button, computes results independently via htmx POST
- **Export all** — one Excel workbook with a Summary + Changes sheet per scenario
- **Add/remove scenarios** — "Add Scenario" appends a new tab; each scenario (except first) can be removed

## UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Compile Scenarios                                          │
│  ← Back to Dashboard                                       │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐  [+ Add Scenario]  │
│  │Scenario 1│ │Scenario 2│ │Scenario 3│                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Scenario Name: [________________________]              ││
│  │  Category:      [________________________]              ││
│  │                                                         ││
│  │  ┌─ Change #1 ──────────────────────────── [✕] ─┐      ││
│  │  │ Module Type / Field / From / To / Filters     │      ││
│  │  └──────────────────────────────────────────────┘      ││
│  │  [+ Add Another Change]                                 ││
│  │                                                         ││
│  │  [ Run Scenario ]                        [✕ Remove]     ││
│  │                                                         ││
│  │  ┌─ Results ────────────────────────────────────┐      ││
│  │  │ Count / Mean / Median / Std / Min / Max ...  │      ││
│  │  └──────────────────────────────────────────────┘      ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  ▸ Global Filters (shared across all scenarios)             │
│                                                             │
│  [ Export All to Excel ]                                    │
└─────────────────────────────────────────────────────────────┘
```

## Field Naming Convention

Each field is prefixed with the scenario index:

```
scenario-0-scenario_name
scenario-0-category
scenario-0-change-0-module_type
scenario-0-change-0-field
scenario-0-change-0-from_value
scenario-0-change-0-to_value
scenario-0-change-0-filter-region
scenario-1-change-0-module_type
...
```

Global filters remain unprefixed: `global_filter_soil_type`, `global_filter_region`.

## Data Flow

### Per-scenario "Run" (htmx POST)

1. User clicks "Run Scenario" on scenario tab N
2. htmx POSTs to `/compile-scenarios/htmx/run-scenario/`
3. `hx-include` gathers that scenario's fields + global filters via CSS selector `[name^='scenario-N-'], [name^='global_filter_']`
4. Server parses changes, builds Q objects, computes stats
5. Returns results partial HTML
6. htmx swaps into `#scenario-N-results`

### Export All (standard POST)

The "Export All" button submits a standard form POST with all scenarios' data. Server iterates each scenario, creates Summary + Changes sheets per scenario in one workbook.

## Endpoints

### New endpoints

| URL | Method | Purpose | Returns |
|-----|--------|---------|---------|
| `htmx/add-scenario/?index=N` | GET | New scenario tab + panel | Tab button + panel partial HTML |
| `htmx/run-scenario/` | POST | Compute stats for one scenario | Results partial HTML |

### Modified endpoints

| Endpoint | Change |
|----------|--------|
| `htmx/fields/` | Detect `scenario-N-change-M-module_type` prefix |
| `htmx/values/` | Same prefix awareness |
| `htmx/filters/` | Same prefix awareness |
| `htmx/add-change/` | Accept `scenario_index` + `index` params |

## Backend Changes

### views.py

**Modified:**
- `_parse_changes_from_post(post_data, prefix="")` — optional prefix for scenario-scoped parsing
- `compile_scenarios(request)` — GET renders one empty scenario tab. POST iterates scenario indices, computes stats per scenario, passes `scenarios` list to template.
- `compile_scenarios_export(request)` — iterates all scenarios, creates per-scenario sheets in one workbook.
- `htmx_fields`, `htmx_values`, `htmx_filters` — updated key detection for `scenario-N-change-M-` prefix.
- `htmx_add_change(request)` — accepts `scenario_index` param.

**New:**
- `htmx_add_scenario(request)` — returns new scenario tab + panel HTML.
- `htmx_run_scenario(request)` — parses one scenario's POST data + global filters, returns results partial.

### Templates

**New:**
- `partials/scenario_tab.html` — tab button element
- `partials/scenario_panel.html` — tab panel (name, category, changes, run button, results area)
- `partials/scenario_results.html` — results grid (extracted from current inline block)

**Modified:**
- `scripts/compile_scenarios.html` — restructured to tab layout, global filters outside tabs, "Export All" button
- `partials/change_fieldset.html` — field names prefixed with `scenario-{{ scenario_index }}-`

### urls.py

Two new paths:
```python
path("compile-scenarios/htmx/add-scenario/", views.htmx_add_scenario, name="htmx-add-scenario"),
path("compile-scenarios/htmx/run-scenario/", views.htmx_run_scenario, name="htmx-run-scenario"),
```

## Client-side JS

Minimal tab switching (no framework):

```javascript
function switchScenarioTab(index) {
    document.querySelectorAll('[data-scenario-panel]').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('[data-scenario-tab]').forEach(t => {
        t.classList.remove('border-blue-500', 'text-blue-600');
        t.classList.add('border-transparent', 'text-gray-500');
    });
    document.querySelector(`[data-scenario-panel="${index}"]`).classList.remove('hidden');
    const tab = document.querySelector(`[data-scenario-tab="${index}"]`);
    tab.classList.add('border-blue-500', 'text-blue-600');
    tab.classList.remove('border-transparent', 'text-gray-500');
}
```

New scenarios added via htmx auto-switch to the new tab on `hx-on::after-settle`.

## Key Decisions

- **Tab-based UI** over side-by-side or separate pages — best UX for independent scenario management
- **Shared global filters** — avoids duplication, applied server-side to all scenario queries
- **Per-scenario run** — avoids re-running unmodified scenarios
- **Single workbook export** — one file with per-scenario sheets for easy comparison in Excel
- **htmx-first** — consistent with existing architecture, minimal client-side JS

## Testing

- Add/remove scenario tabs via htmx
- Per-scenario run returns correct results
- Field naming with scenario prefix works for cascading dropdowns
- Export all produces correct multi-sheet workbook
- Global filters applied to all scenarios
- Form re-renders correctly after full-page POST
