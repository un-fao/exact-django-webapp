# Compile Scenarios UI — Design Document

**Date:** 2026-03-03
**Branch:** feature/admin-scripts

## Goal

Add a "Compile Scenarios" script to the admin_scripts app that lets staff users dynamically create emission scenarios through a web form, run them against ChangeRecord data, and view computed statistics — without editing Python code.

## Architecture

- **Approach:** Django views + htmx for cascading dropdowns and dynamic form management
- **Location:** Within the existing `admin_scripts` app, following the same patterns (staff-only, dashboard entry, dedicated template)
- **Reuse:** `stats_for()` and Q-object building logic extracted from `scripts/minitool__compile_scenarios.py`

## Endpoints

All under `/api/admin-scripts/compile-scenarios/`, protected by `@login_required` + `@staff_required`.

| URL | Method | Purpose | Returns |
|-----|--------|---------|---------|
| `/` | GET | Render scenario builder form | Full page |
| `/` | POST | Submit scenario, compute stats | Page with results |
| `htmx/module-types/` | GET | Distinct module types from ChangeRecord | `<option>` elements |
| `htmx/fields/?module_type=X` | GET | Distinct fields for a module type | `<option>` elements |
| `htmx/values/?module_type=X&field=Y` | GET | Distinct from/to values | Two `<select>` partials |
| `htmx/filters/?module_type=X` | GET | Distinct filter values (region, climate, etc.) | Filter `<select>` partials |
| `htmx/add-change/?index=N` | GET | New empty change fieldset | Change form partial HTML |
| `export/` | POST | Re-run query, return Excel file | File download |

## Form Layout

```
┌─────────────────────────────────────────────────┐
│  Compile Scenarios                              │
│  ← Back to Dashboard                           │
├─────────────────────────────────────────────────┤
│  Scenario Name: [________________________]      │
│  Category:      [______ dropdown ________] ▼    │
│                                                 │
│  ┌─ Change #1 ───────────────────────── [✕] ─┐  │
│  │ Module Type: [________] ▼                  │  │
│  │ Field:       [________] ▼  (htmx cascade)  │  │
│  │ From Value:  [________] ▼                  │  │
│  │ To Value:    [________] ▼                  │  │
│  │                                            │  │
│  │ ▸ Filters (collapsible)                    │  │
│  │   Region / Climate / Moisture / Soil Type  │  │
│  └────────────────────────────────────────────┘  │
│                                                 │
│  [+ Add Another Change]                         │
│                                                 │
│  ▸ Global Filters (collapsible)                 │
│    Soil Type defaults: [HAC, LAC, Sandy]        │
│                                                 │
│  [ Run Scenario ]                               │
├─────────────────────────────────────────────────┤
│  Results (after submission)                     │
│  Count / Mean / Median / Std / Min / Max        │
│  Q1 / Q3 / IQR / CI 95% / CI 99%               │
│  Distribution type + range                      │
│  [ Export to Excel ]                            │
└─────────────────────────────────────────────────┘
```

## htmx Data Flow

1. User selects module type → `hx-get="htmx/fields/?module_type=X"` → server returns `<option>` elements for field dropdown
2. User selects field → `hx-get="htmx/values/?module_type=X&field=Y"` → server returns from/to value `<select>` elements
3. User clicks "Add Change" → `hx-get="htmx/add-change/?index=N"` → server returns new change fieldset appended to form
4. Form submit is a standard POST (no htmx), full page renders with results below

## Backend Logic

### Reusable utilities (`admin_scripts/scenario_utils.py`)

- **`stats_for(queryset)`** — Copied/imported from `compile_scenarios.py`. Computes count, sum, mean, median, min, max, std, Q1, Q3, IQR, CI 95%, CI 99%.
- **`build_scenario_query(changes, global_filters)`** — Extracted from `run()`. Takes a list of change dicts and global filters, returns a combined Q object.

### Processing flow on POST

```python
# 1. Parse form data into changes list
changes = parse_changes_from_post(request.POST)
global_filters = parse_global_filters(request.POST)

# 2. Build Q objects
q_objects = build_scenario_query(changes, global_filters)

# 3. Query and compute
aggregates = ChangeRecord.objects.filter(q_objects)
statistics = stats_for(aggregates)

# 4. Determine distribution type (symmetric vs skewed)
# 5. Render results
```

### Form field naming convention

Each change fieldset uses indexed names: `change-0-module_type`, `change-0-field`, `change-0-from_value`, `change-0-to_value`, `change-0-filter-region`, etc.

## Key Decisions

- **Multiple changes per scenario** — users can add/remove changes, each with its own module type and filters
- **Live DB queries** — dropdowns populated from actual ChangeRecord data (always current)
- **Display stats only** — results shown on page, not saved to EmissionScenario table
- **Optional Excel export** — reuses `save_to_excel()` logic, returns as file download
- **htmx over vanilla JS** — server-rendered partials, minimal client-side code

## Testing

- Access control: staff auth required for all endpoints
- htmx endpoints: return correct HTML fragments for valid params
- Form submission: valid data returns statistics
- Empty results: no matching records shows appropriate message
- Multiple changes: OR'd Q objects work correctly
- Validation: missing required fields return errors

## Files to Create/Modify

- `admin_scripts/views.py` — new views + htmx partial views
- `admin_scripts/urls.py` — new URL patterns
- `admin_scripts/scenario_utils.py` — extracted reusable logic
- `admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html` — main form
- `admin_scripts/templates/admin_scripts/partials/` — htmx partial templates
- `admin_scripts/base.html` — add htmx `<script>` tag
- `admin_scripts/tests.py` — new test cases
