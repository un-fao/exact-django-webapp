# Scenario Builder — Per-Change Unit Multipliers

**Date:** 2026-05-12
**Branch:** `feature/scenario-builder-per-change-units`
**Beads issue:** `exact-django-webapp-5os`

## Background

The admin scripts "Compile Scenarios" tool lets a user build a Scenario by adding one or more Change rows (each row: `module_type` + `field` + `from_value` → `to_value`, plus optional filters). On run, all changes inside a scenario are OR'd into one queryset of `ChangeRecord`s, and descriptive statistics (count, sum, mean, median, min, max, std, q1, q3, iqr, ci_95, ci_99) are computed over the `total` field of those records. The same queryset is re-used for the per-scenario summary row in the Excel export.

The user can already model "what is the emissions effect of transition X?" — but cannot weight a change by how much of the transition is happening (e.g. *5 ha* of grassland improvement vs *2 ha*). Today every matched record contributes its raw `total` once.

## Goal

Add a numeric multiplier — exposed in the UI as **"Units"** — to each Change row. Each `ChangeRecord` matched by that change contributes `record.total × change.unit` to the scenario's distribution. The multiplier defaults to `1.0`, so any pre-existing scenario behaves identically to today.

## Non-Goals

- The DRF viewset `EmissionScenarioViewSet` in `djangoexact/minitool/views.py` has its own copy of `stats_for` / `_build_scenario_query`. It is **not** modified by this change.
- Per-scenario or global multipliers.
- Catalog YAML changes — `unit` is a per-instance property of a Change row, not a property of a module/field.
- A unit-of-measure label (e.g. "tCO2e/ha"). Only the numeric multiplier is in scope.
- Changes to existing `stats_for(qs)` or `build_scenario_query(changes, global_filters)` semantics. Both remain importable and behave exactly as before (tests rely on them).

## Data Model

### Change dict (in-process shape, no DB)

A Change dict gains one optional key:

```
{
    "module_type": str,
    "start": {"field": str, "value": str},
    "end":   {"field": str, "value": str},
    "filters": {...},
    "unit": float,        # NEW — defaults to 1.0 when missing/blank/non-numeric
}
```

- **Type:** `float`. Stored in POST as a string; coerced at consumption time.
- **Default:** `1.0` when key is absent, the value is the empty string, or coercion to `float` fails.
- **Validation:** values `< 0` are coerced to `1.0` (treated as malformed input). `0` is allowed and produces a zeroed distribution for that change.
- **Persistence:** none. The value lives in form state, POST data, and (for the export) the generated Excel file. No migrations.

## UI

### `templates/admin_scripts/partials/change_fieldset.html`

The Units input is placed in its **own row, outside** both HTMX swap targets (`#{{ id_prefix }}-field-container` and `#{{ id_prefix }}-values-container`). This keeps the unit value untouched when the user changes `module_type` or `field` and triggers a swap of those containers — no need to thread the unit through `htmx_fields` / `htmx_values` partials or expand any `hx-include` attributes.

Concrete placement: a new `<div class="mt-3">` *after* the existing values container and *before* the "Change-level Filters" `<details>`:

```
Label: "Units"
Input: <input type="number" name="{{ prefix }}unit" step="any" min="0" value="{{ change.unit|default:'1' }}"
              class="w-full sm:w-48 border border-gray-300 rounded px-3 py-2 text-sm"
              placeholder="1.0">
Helper: small muted text below — "Multiplier applied to each matched record's total"
```

### Header summary (inside `change_fieldset.html`)

The collapsed `change-summary` span currently shows `— {module_type}: {from_value} → {to_value}`. Append ` × {unit}` only when `unit` is set and not equal to `1` (or `1.0`).

### `templates/admin_scripts/partials/value_options.html`

Unchanged. The Units input does not live inside this swap target.

## Backend — `djangoexact/admin_scripts/scenario_utils.py`

### New: `_build_single_change_q(change, global_filters) -> Q`

Refactor: the per-change Q construction inside the existing `build_scenario_query` loop is extracted into this helper. Behavior identical to the inner loop body today.

### Refactored: `build_scenario_query(changes, global_filters) -> Q`

Becomes a thin wrapper that OR-folds `_build_single_change_q` over the changes. Same return value, same callers, same tests.

### New: `stats_for_scenario(changes, global_filters) -> dict`

Replaces the `build_scenario_query` → `ChangeRecord.objects.filter(...)` → `stats_for(qs)` pipeline for admin-script scenario consumption. Algorithm:

1. For each `change` in `changes`:
   1. If `change.get("module_type")` is falsy, skip.
   2. Compute `q = _build_single_change_q(change, global_filters)`.
   3. Coerce the unit: `unit = _coerce_unit(change.get("unit"))` where `_coerce_unit` returns `1.0` on missing / blank / non-numeric / negative input and a `float` otherwise.
   4. Stream the matched totals: `ChangeRecord.objects.filter(q).values_list("total", flat=True)`.
   5. Append `[v * unit for v in totals]` to a running list `scaled_values`.
2. Compute descriptive statistics over `scaled_values` using the same formulas as `stats_for(qs)` today (count, sum, mean, median, min, max, std, q1, q3, iqr, ci_95, ci_99). Return the same dict shape.
3. If `scaled_values` is empty, return the same "empty stats" dict that `stats_for` returns today (count 0; all numeric fields `None` except `sum_total` which stays `0.0`).

**Note on the queryset variant.** `stats_for(qs)` is kept as-is and remains used by tests and by `build_scenario_query` consumers outside admin_scripts. The two functions share the same statistical formulas; that duplication is acceptable here — extracting a shared `_descriptive_stats_from_values(values)` helper and routing both through it is allowed if it doesn't change behavior.

## Backend — `djangoexact/admin_scripts/views.py`

### `_parse_changes_from_post(post_data, prefix="")`

Add a `"unit"` key to the parsed change dict, read from `f"{prefix}change-{index}-unit"`. Store the raw string (including empty string); coercion happens inside `stats_for_scenario`.

### `htmx_run_scenario`

Replace:

```python
q_objects = build_scenario_query(changes, global_filters)
aggregates = ChangeRecord.objects.filter(q_objects)
stats = stats_for(aggregates)
```

with:

```python
stats = stats_for_scenario(changes, global_filters)
```

The gap-detector path (`if stats["count"] == 0: ...`) is unchanged.

### `htmx_values` and `htmx_fields`

Unchanged. Because the Units input lives outside both swap targets, no view or partial in the HTMX path needs to know about it.

### `compile_scenarios_export`

Replace the `build_scenario_query` + `stats_for` calls with `stats_for_scenario` (same as the run path). Add a new column to the per-scenario Changes sheet:

```
Change # | Module Type | Field | From Value | To Value | Units
```

Population: `change.get("unit", "")`. Empty string when the user left it blank (no implicit `1` in the export — the spreadsheet should reflect what was entered).

The Summary sheet's column order is unchanged. Its numeric values reflect the scaled distribution because they come from `stats_for_scenario`.

## Tests — `djangoexact/admin_scripts/tests/test_views.py`

The existing `stats_for` and `build_scenario_query` tests stay green (those functions retain their signatures and behavior).

New tests cover:

1. `test_stats_for_scenario_unit_one_matches_stats_for_baseline`
   A single change with `unit=1.0` returns a stats dict equal to the legacy `stats_for(build_scenario_query(...))` output. Confirms back-compat.
2. `test_stats_for_scenario_missing_unit_defaults_to_one`
   A change dict without a `unit` key behaves identically to one with `unit=1.0`.
3. `test_stats_for_scenario_unit_scales_distribution`
   A single change with `unit=2.0` returns `mean`, `sum_total`, `min`, `max`, `median`, `std`, `ci_95`, `ci_99` all scaled by 2 relative to the `unit=1.0` baseline, with `count` unchanged.
4. `test_stats_for_scenario_unit_zero_zeros_out_distribution`
   `unit=0` returns `count` equal to the matched record count, `sum_total=0`, `mean=0`, `min=0`, `max=0`, `std=0`.
5. `test_stats_for_scenario_overlapping_changes_count_once_per_change`
   Two changes whose Q's match overlapping rows (units 1 and 3) produce a distribution whose `count` equals the sum of the two matched-record counts (each row counted once per matching change), and whose `sum_total` equals `sum(row.total for change_a) * 1 + sum(row.total for change_b) * 3`.
6. `test_stats_for_scenario_blank_unit_string_defaults_to_one`
   `unit=""` (the literal empty string that POST parsing will produce when the input is blanked) behaves identically to `unit=1.0`.
7. `test_stats_for_scenario_negative_unit_defaults_to_one`
   `unit=-2` is treated as malformed and coerced to `1.0` (does not flip signs of totals).
8. `test_excel_export_includes_units_column`
   `POST` to `compile_scenarios_export` with one scenario containing one change carrying `unit="2.5"` produces an xlsx whose `{scenario_name} Changes` sheet contains a `Units` column with value `"2.5"` (or `2.5` numeric — assertion accepts either).
9. `test_htmx_run_scenario_uses_unit_from_post`
   POST to the run endpoint with `scenario-0-change-0-unit=4` returns a `scenario_results.html` rendering whose statistics reflect a 4× scaling compared to the same POST with no unit field.

Fixture data already provided by the test module (5 records) is reusable for most cases; tests 5 and 6 may need a second module_type seeded so two changes match disjoint rows.

## Acceptance Criteria

1. A Change row in the scenario builder UI shows a third input labeled **"Units"** alongside From / To, defaulting to `1`.
2. Submitting a scenario via "Run Scenario" with non-default unit values returns statistics scaled per the per-record × unit formula described above.
3. Exporting via "Export All to Excel" produces a workbook whose per-scenario Changes sheet contains a **"Units"** column.
4. Submitting a scenario with all units left at the default `1` produces statistics equivalent to the previous behavior (numeric equality within floating-point tolerance for `mean` / `sum_total` / `std` / `ci_*` is acceptable, as `stats_for_scenario` does sum/mean arithmetic in Python rather than in the DB; `count` is exact).
5. The `unit` value survives HTMX swaps triggered by changing `module_type` or `field` within the same Change row.
6. `stats_for` and `build_scenario_query` retain their signatures and existing behavior; their test cases pass unchanged.
7. New tests for `stats_for_scenario` cover the cases enumerated above and all pass.

## Risk and Rollback

- **No DB migration**, no schema change. Rollback = revert the diff.
- **No persisted data has the new field.** Pre-existing flows (the DRF API in `minitool/views.py`) are untouched.
- **Performance:** `stats_for_scenario` materializes matched `total` values into Python for scaling. For a typical scenario (a handful of changes, each matching low-thousands of records) this matches the existing `_stats_for_python` path's footprint. Mitigation if needed later: batch via `iterator(chunk_size=...)`. Out of scope here.
