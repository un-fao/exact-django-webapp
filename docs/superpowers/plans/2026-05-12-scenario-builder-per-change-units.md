# Scenario Builder — Per-Change Unit Multipliers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-Change-row numeric "Units" multiplier to the admin-scripts scenario builder. Each `ChangeRecord` matched by a change contributes `record.total × change.unit` (default `1.0`) to that scenario's descriptive-statistics distribution. Default behavior unchanged.

**Architecture:** A new function `stats_for_scenario(changes, global_filters)` in `admin_scripts/scenario_utils.py` iterates each change, scales matched `total` values by that change's unit, accumulates a Python list, and runs the same descriptive-statistics formulas the existing `stats_for(qs)` uses. The two existing scenario-builder callers (`htmx_run_scenario`, `compile_scenarios_export`) switch from the `build_scenario_query` + `stats_for` pair to a single `stats_for_scenario` call. The form gets a new `<input type="number">` per Change row, placed *outside* the existing HTMX swap targets so it never gets clobbered. POST parsing forwards the raw string; coercion (blank/non-numeric/negative → `1.0`) happens in `stats_for_scenario`. No DB migration.

**Tech Stack:** Python 3.11, Django (function-based views + templates), HTMX, Tailwind utility classes, openpyxl/pandas for export, Django `TestCase` for tests.

**Linked beads issue:** `exact-django-webapp-5os`

**Source spec:** `docs/superpowers/specs/2026-05-12-scenario-builder-per-change-units-design.md`

---

## File Map

**Modified:**
- `djangoexact/admin_scripts/scenario_utils.py` — add `_coerce_unit`, refactor to add `_build_single_change_q`, add `stats_for_scenario`. Keep `stats_for` and `build_scenario_query` signatures unchanged.
- `djangoexact/admin_scripts/views.py` — `_parse_changes_from_post` reads `unit`; `htmx_run_scenario` and `compile_scenarios_export` call `stats_for_scenario`; export Changes sheet gains a `"Units"` column.
- `djangoexact/admin_scripts/templates/admin_scripts/partials/change_fieldset.html` — add the Units input as its own row, plus `× {unit}` suffix on the collapsed change-summary span when non-default.
- `djangoexact/admin_scripts/tests/test_views.py` — new test cases for `_coerce_unit`, `stats_for_scenario`, parser, HTMX run path, and export.

**Not touched:**
- `djangoexact/admin_scripts/templates/admin_scripts/partials/value_options.html` (Units lives outside this swap target).
- `djangoexact/admin_scripts/templates/admin_scripts/partials/field_select.html`.
- Any view or template under `djangoexact/minitool/` (the DRF viewset has its own `stats_for` / `_build_scenario_query`; out of scope).
- `djangoexact/admin_scripts/catalog/scenario_catalog.yaml`.

---

## Pre-flight

- [ ] **Step 0a: Claim the beads issue**

Run:
```bash
bd update exact-django-webapp-5os --claim
bd update exact-django-webapp-5os --status=in_progress
```

- [ ] **Step 0b: Confirm branch and clean working tree**

Run:
```bash
git status
git branch --show-current
```

Expected: branch is `feature/scenario-builder-per-change-units`, working tree clean (or only contains files this plan adds/modifies).

- [ ] **Step 0c: Establish a green baseline**

Run from the repository root:
```bash
python djangoexact/manage.py test admin_scripts.tests.test_views -v 2
```

Expected: all tests pass (this is the baseline; we will run this after every implementation task to confirm we haven't regressed).

If the baseline is not green, stop and surface the failure — do not start the plan on top of a red suite.

---

## Task 1: Add `_coerce_unit` helper to `scenario_utils.py`

**Why:** Centralize the "string from POST → safe float" conversion so the parser stores raw strings and only one place owns the policy (blank / non-numeric / negative → `1.0`).

**Files:**
- Modify: `djangoexact/admin_scripts/scenario_utils.py`
- Test: `djangoexact/admin_scripts/tests/test_views.py`

- [ ] **Step 1.1: Write the failing tests**

Append to `djangoexact/admin_scripts/tests/test_views.py` (inside the existing `ScenarioUtilsTest` class — no new fixtures needed):

```python
    def test_coerce_unit_returns_float_for_numeric_string(self):
        from admin_scripts.scenario_utils import _coerce_unit
        self.assertEqual(_coerce_unit("2.5"), 2.5)
        self.assertEqual(_coerce_unit("3"), 3.0)
        self.assertEqual(_coerce_unit(2.0), 2.0)
        self.assertEqual(_coerce_unit(0), 0.0)

    def test_coerce_unit_defaults_to_one_on_invalid_input(self):
        from admin_scripts.scenario_utils import _coerce_unit
        self.assertEqual(_coerce_unit(None), 1.0)
        self.assertEqual(_coerce_unit(""), 1.0)
        self.assertEqual(_coerce_unit("   "), 1.0)
        self.assertEqual(_coerce_unit("abc"), 1.0)

    def test_coerce_unit_clamps_negative_to_one(self):
        from admin_scripts.scenario_utils import _coerce_unit
        self.assertEqual(_coerce_unit("-2"), 1.0)
        self.assertEqual(_coerce_unit(-0.5), 1.0)
```

- [ ] **Step 1.2: Run the tests to confirm they fail**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.ScenarioUtilsTest.test_coerce_unit_returns_float_for_numeric_string admin_scripts.tests.ScenarioUtilsTest.test_coerce_unit_defaults_to_one_on_invalid_input admin_scripts.tests.ScenarioUtilsTest.test_coerce_unit_clamps_negative_to_one -v 2
```

Expected: 3 failures with `ImportError: cannot import name '_coerce_unit'` (or similar).

- [ ] **Step 1.3: Implement `_coerce_unit`**

At the top of `djangoexact/admin_scripts/scenario_utils.py`, immediately after the `from django.db.models import ...` line, add:

```python
def _coerce_unit(value):
    """Convert a POSTed unit value to a safe float multiplier.

    Returns 1.0 for None, blank strings, non-numeric strings, and negative numbers.
    """
    if value is None:
        return 1.0
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 1.0
    if f < 0:
        return 1.0
    return f
```

- [ ] **Step 1.4: Run the tests to confirm they pass**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.ScenarioUtilsTest -v 2
```

Expected: all `ScenarioUtilsTest` tests pass (the 3 new ones plus all existing ones).

- [ ] **Step 1.5: Commit**

```bash
git add djangoexact/admin_scripts/scenario_utils.py djangoexact/admin_scripts/tests/test_views.py
git commit -m "feat(scenario-builder): add _coerce_unit helper for per-change multipliers"
```

---

## Task 2: Extract `_build_single_change_q` (behavior-preserving refactor)

**Why:** `stats_for_scenario` needs per-change Q objects, not just the OR-folded scenario-wide Q. We extract the per-change Q logic out of `build_scenario_query`'s inner loop so both callers can share it. Behavior of `build_scenario_query` is unchanged.

**Files:**
- Modify: `djangoexact/admin_scripts/scenario_utils.py` (replace the body of `build_scenario_query`)
- Test: no new tests; existing `test_build_scenario_query_*` tests guard the refactor

- [ ] **Step 2.1: Refactor — extract `_build_single_change_q`**

In `djangoexact/admin_scripts/scenario_utils.py`, replace the entire `build_scenario_query` function (currently `def build_scenario_query(changes, global_filters):` through its `return q_objects` line) with this two-function pair:

```python
def _build_single_change_q(change, global_filters):
    """Build a Q object matching ChangeRecords for one change in a scenario.

    Returns Q() (matches nothing) if the change has no module_type — callers
    should skip such changes rather than OR an empty Q into a wider query.
    """
    module_type = change.get("module_type")
    if not module_type:
        return Q(pk__in=[])

    change_filters = {**global_filters, **change.get("filters", {})}
    csv_row_filters = change.get("csv_row_filters", {})

    change_q = (
        Q(module_type=module_type, field=change["start"]["field"])
        & _create_flexible_value_query("from_value", change["start"]["value"])
        & _create_flexible_value_query("to_value", change["end"]["value"])
    )

    for col in ("region", "climate", "moisture", "soil_type"):
        if change_filters.get(col):
            values = change_filters[col] if isinstance(change_filters[col], list) else [change_filters[col]]
            col_q = Q()
            for val in values:
                col_q |= Q(**{col: val})
            change_q &= col_q

    for filter_key, filter_value in change_filters.items():
        if filter_key in ("region", "climate", "moisture", "soil_type"):
            continue
        filter_values = filter_value if isinstance(filter_value, list) else [filter_value]
        filter_q = Q()
        for val in filter_values:
            filter_q |= Q(**{f"csv_row_data__{filter_key}": val}) | Q(**{f"custom_filters__{filter_key}": val})
        change_q &= filter_q

    for filter_key, filter_value in csv_row_filters.items():
        if filter_key in ("module_start_type", "module_w_type"):
            continue
        filter_values = filter_value if isinstance(filter_value, list) else [filter_value]
        csv_filter_q = Q()
        for val in filter_values:
            csv_filter_q |= Q(**{f"csv_row_data__{filter_key}": val})
        change_q &= csv_filter_q

    return change_q


def build_scenario_query(changes, global_filters):
    """
    Build a combined Q object for filtering ChangeRecords based on scenario changes.

    Args:
        changes: List of change dicts, each with keys:
            - module_type (str)
            - start: {field, value}
            - end: {field, value}
            - filters (optional dict): region, climate, moisture, soil_type, or custom
            - csv_row_filters (optional dict): filters on csv_row_data JSONField
        global_filters: Dict of filters applied to ALL changes (same keys as change filters)

    Returns:
        Q object suitable for ChangeRecord.objects.filter()
    """
    q_objects = Q()
    for change in changes:
        if not change.get("module_type"):
            continue
        q_objects |= _build_single_change_q(change, global_filters)
    return q_objects
```

Notes for the implementer:
- The `Q(pk__in=[])` sentinel returned from `_build_single_change_q` for missing-module-type is defensive; `build_scenario_query` filters those out before calling. The `stats_for_scenario` path (Task 3) also filters them out.
- The `_create_flexible_value_query` helper is already defined above in the same file — do not redefine it.

- [ ] **Step 2.2: Confirm existing tests still pass**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.test_views.ScenarioUtilsTest -v 2
```

Expected: all `ScenarioUtilsTest` tests pass — including `test_build_scenario_query_basic`, `test_build_scenario_query_with_soil_filter`, and `test_build_scenario_query_multiple_changes`. If any fail, the refactor changed behavior; fix before continuing.

- [ ] **Step 2.3: Commit**

```bash
git add djangoexact/admin_scripts/scenario_utils.py
git commit -m "refactor(scenario-builder): extract _build_single_change_q from build_scenario_query"
```

---

## Task 3: Add `stats_for_scenario` function

**Why:** The new pipeline that aggregates `record.total × change.unit` across all changes in a scenario. Replaces the queryset-aggregate path for admin-scripts consumers.

**Files:**
- Modify: `djangoexact/admin_scripts/scenario_utils.py`
- Test: `djangoexact/admin_scripts/tests/test_views.py`

- [ ] **Step 3.1: Write the failing tests**

Append to the `ScenarioUtilsTest` class in `djangoexact/admin_scripts/tests/test_views.py`. The class already seeds 5 Grassland `ChangeRecord`s with totals `[-3.0, -2.5, -2.0, -1.5, -1.0]` (sum `-10.0`, mean `-2.0`).

```python
    def test_stats_for_scenario_unit_one_matches_legacy_baseline(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
            "unit": "1",
        }]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(stats["count"], 5)
        self.assertAlmostEqual(stats["sum_total"], -10.0, places=5)
        self.assertAlmostEqual(stats["mean"], -2.0, places=5)
        self.assertAlmostEqual(stats["median"], -2.0, places=5)
        self.assertAlmostEqual(stats["min"], -3.0, places=5)
        self.assertAlmostEqual(stats["max"], -1.0, places=5)

    def test_stats_for_scenario_missing_unit_defaults_to_one(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
            # no "unit" key at all
        }]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(stats["count"], 5)
        self.assertAlmostEqual(stats["sum_total"], -10.0, places=5)
        self.assertAlmostEqual(stats["mean"], -2.0, places=5)

    def test_stats_for_scenario_blank_unit_defaults_to_one(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
            "unit": "",
        }]
        stats = stats_for_scenario(changes, {})
        self.assertAlmostEqual(stats["sum_total"], -10.0, places=5)
        self.assertAlmostEqual(stats["mean"], -2.0, places=5)

    def test_stats_for_scenario_unit_scales_distribution(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
            "unit": "2",
        }]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(stats["count"], 5)
        self.assertAlmostEqual(stats["sum_total"], -20.0, places=5)
        self.assertAlmostEqual(stats["mean"], -4.0, places=5)
        self.assertAlmostEqual(stats["median"], -4.0, places=5)
        self.assertAlmostEqual(stats["min"], -6.0, places=5)
        self.assertAlmostEqual(stats["max"], -2.0, places=5)
        # std and CI scale linearly with the multiplier
        unit_one_changes = [dict(changes[0], unit="1")]
        baseline = stats_for_scenario(unit_one_changes, {})
        self.assertAlmostEqual(stats["std"], baseline["std"] * 2, places=5)
        self.assertAlmostEqual(stats["ci_95"], baseline["ci_95"] * 2, places=5)
        self.assertAlmostEqual(stats["ci_99"], baseline["ci_99"] * 2, places=5)

    def test_stats_for_scenario_unit_zero_zeros_out_distribution(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
            "unit": "0",
        }]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["sum_total"], 0.0)
        self.assertEqual(stats["mean"], 0.0)
        self.assertEqual(stats["min"], 0.0)
        self.assertEqual(stats["max"], 0.0)
        self.assertEqual(stats["std"], 0.0)

    def test_stats_for_scenario_negative_unit_treated_as_one(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
            "unit": "-2",
        }]
        stats = stats_for_scenario(changes, {})
        # negative unit clamps to 1.0 — sum stays negative, not positive
        self.assertAlmostEqual(stats["sum_total"], -10.0, places=5)

    def test_stats_for_scenario_overlapping_changes_count_once_per_change(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        # Both changes match the same 5 Grassland records (same module_type/field/values).
        # With units 1 and 3, the distribution gets 5 + 5 = 10 scaled values:
        # 5 of [-3, -2.5, -2, -1.5, -1] and 5 of [-9, -7.5, -6, -4.5, -3].
        changes = [
            {
                "module_type": "Grassland",
                "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
                "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
                "unit": "1",
            },
            {
                "module_type": "Grassland",
                "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
                "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
                "unit": "3",
            },
        ]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(stats["count"], 10)
        # sum = -10 * 1 + -10 * 3 = -40
        self.assertAlmostEqual(stats["sum_total"], -40.0, places=5)

    def test_stats_for_scenario_no_changes_returns_empty_stats(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        stats = stats_for_scenario([], {})
        self.assertEqual(stats["count"], 0)
        self.assertEqual(stats["sum_total"], 0.0)
        self.assertIsNone(stats["mean"])
        self.assertIsNone(stats["std"])

    def test_stats_for_scenario_skips_changes_without_module_type(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        changes = [
            {
                "module_type": "",
                "start": {"field": "x", "value": "a"},
                "end": {"field": "x", "value": "b"},
                "unit": "2",
            },
            {
                "module_type": "Grassland",
                "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
                "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
                "unit": "1",
            },
        ]
        stats = stats_for_scenario(changes, {})
        # Only the second change contributes; first is skipped.
        self.assertEqual(stats["count"], 5)
        self.assertAlmostEqual(stats["sum_total"], -10.0, places=5)
```

- [ ] **Step 3.2: Run the tests to confirm they fail**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.ScenarioUtilsTest -v 2
```

Expected: 9 new tests fail with `ImportError: cannot import name 'stats_for_scenario'`.

- [ ] **Step 3.3: Implement `stats_for_scenario`**

Append to `djangoexact/admin_scripts/scenario_utils.py` (after `build_scenario_query`):

```python
def _descriptive_stats_from_values(values):
    """Compute the same descriptive-statistics dict shape as ``stats_for(qs)``,
    but from an already-materialized list of floats.
    """
    n = len(values)
    if n == 0:
        return {
            "count": 0,
            "sum_total": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "std": None,
            "q1": None,
            "q3": None,
            "iqr": None,
            "ci_95": None,
            "ci_99": None,
        }

    s = sum(values)
    mean = s / n
    minv = min(values)
    maxv = max(values)
    ss = sum(x * x for x in values)

    if n > 1:
        var = max(0, (ss - (s * s) / n) / (n - 1))
        std = var**0.5
        se = std / (n**0.5)
        ci95 = 1.96 * se
        ci99 = 2.58 * se
    else:
        std = se = ci95 = ci99 = None

    sorted_values = sorted(values)

    if len(sorted_values) >= 4:
        q1 = stats_module.quantiles(sorted_values, n=4)[0]
        median = stats_module.median(sorted_values)
        q3 = stats_module.quantiles(sorted_values, n=4)[2]
    else:
        n_values = len(sorted_values)
        if n_values % 2 == 0:
            median = (sorted_values[n_values // 2 - 1] + sorted_values[n_values // 2]) / 2
        else:
            median = sorted_values[n_values // 2]

        q1_idx = (n_values - 1) * 0.25
        q3_idx = (n_values - 1) * 0.75

        if q1_idx.is_integer():
            q1 = sorted_values[int(q1_idx)]
        else:
            lower_idx = int(q1_idx)
            upper_idx = min(lower_idx + 1, n_values - 1)
            weight = q1_idx - lower_idx
            q1 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

        if q3_idx.is_integer():
            q3 = sorted_values[int(q3_idx)]
        else:
            lower_idx = int(q3_idx)
            upper_idx = min(lower_idx + 1, n_values - 1)
            weight = q3_idx - lower_idx
            q3 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

    iqr = q3 - q1

    return {
        "count": n,
        "sum_total": s,
        "mean": mean,
        "median": median,
        "min": minv,
        "max": maxv,
        "std": std,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "ci_95": ci95,
        "ci_99": ci99,
    }


def stats_for_scenario(changes, global_filters):
    """Compute descriptive statistics over ``record.total × change.unit`` for
    every ChangeRecord matched by each change in *changes*.

    A record matching multiple changes is counted once *per matching change*
    (so its scaled value appears once for each change's unit). The unit
    defaults to 1.0 for missing / blank / non-numeric / negative inputs,
    which makes a scenario with no explicit units behave equivalently to the
    legacy ``stats_for(build_scenario_query(...))`` pipeline.
    """
    # Lazy import to keep this module import-cycle-safe.
    from minitool.models import ChangeRecord

    scaled_values = []
    for change in changes:
        if not change.get("module_type"):
            continue
        unit = _coerce_unit(change.get("unit"))
        q = _build_single_change_q(change, global_filters)
        totals = ChangeRecord.objects.filter(q).values_list("total", flat=True)
        scaled_values.extend(v * unit for v in totals)

    return _descriptive_stats_from_values(scaled_values)
```

- [ ] **Step 3.4: Run the tests to confirm they pass**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.ScenarioUtilsTest -v 2
```

Expected: all `ScenarioUtilsTest` tests pass (the 9 new `stats_for_scenario_*` tests plus the existing baseline tests).

- [ ] **Step 3.5: Commit**

```bash
git add djangoexact/admin_scripts/scenario_utils.py djangoexact/admin_scripts/tests/test_views.py
git commit -m "feat(scenario-builder): add stats_for_scenario with per-change unit scaling"
```

---

## Task 4: Parse `unit` in `_parse_changes_from_post`

**Why:** Without this, POST values for `{prefix}change-{N}-unit` are silently dropped before reaching `stats_for_scenario`. The parser stores the raw string; `_coerce_unit` handles validation inside `stats_for_scenario`.

**Files:**
- Modify: `djangoexact/admin_scripts/views.py` (`_parse_changes_from_post`)
- Test: `djangoexact/admin_scripts/tests/test_views.py`

- [ ] **Step 4.1: Write the failing test**

Append to the `CompileScenariosViewTest` class in `djangoexact/admin_scripts/tests/test_views.py`:

```python
    def test_parse_changes_extracts_unit_field(self):
        from admin_scripts.views import _parse_changes_from_post
        from django.http import QueryDict

        post = QueryDict(mutable=True)
        post["scenario-0-change-0-module_type"] = "Grassland"
        post["scenario-0-change-0-field"] = "grassland_management_type"
        post["scenario-0-change-0-from_value"] = "Non-Degraded"
        post["scenario-0-change-0-to_value"] = "Improved Grassland"
        post["scenario-0-change-0-unit"] = "2.5"

        changes = _parse_changes_from_post(post, prefix="scenario-0-")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["unit"], "2.5")

    def test_parse_changes_unit_defaults_to_empty_string_when_missing(self):
        from admin_scripts.views import _parse_changes_from_post
        from django.http import QueryDict

        post = QueryDict(mutable=True)
        post["scenario-0-change-0-module_type"] = "Grassland"
        post["scenario-0-change-0-field"] = "grassland_management_type"
        post["scenario-0-change-0-from_value"] = "Non-Degraded"
        post["scenario-0-change-0-to_value"] = "Improved Grassland"
        # no unit key

        changes = _parse_changes_from_post(post, prefix="scenario-0-")
        self.assertEqual(changes[0]["unit"], "")
```

- [ ] **Step 4.2: Run the tests to confirm they fail**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.CompileScenariosViewTest.test_parse_changes_extracts_unit_field admin_scripts.tests.CompileScenariosViewTest.test_parse_changes_unit_defaults_to_empty_string_when_missing -v 2
```

Expected: 2 failures with `KeyError: 'unit'`.

- [ ] **Step 4.3: Update `_parse_changes_from_post`**

In `djangoexact/admin_scripts/views.py`, locate the `_parse_changes_from_post` function and add the `unit` key to the change dict it builds. Replace the block that currently reads:

```python
        if module_type:
            change = {
                "module_type": module_type,
                "start": {
                    "field": post_data.get(f"{prefix}change-{index}-field", ""),
                    "value": post_data.get(f"{prefix}change-{index}-from_value", ""),
                },
                "end": {
                    "field": post_data.get(f"{prefix}change-{index}-field", ""),
                    "value": post_data.get(f"{prefix}change-{index}-to_value", ""),
                },
                "filters": {},
            }
```

with:

```python
        if module_type:
            change = {
                "module_type": module_type,
                "start": {
                    "field": post_data.get(f"{prefix}change-{index}-field", ""),
                    "value": post_data.get(f"{prefix}change-{index}-from_value", ""),
                },
                "end": {
                    "field": post_data.get(f"{prefix}change-{index}-field", ""),
                    "value": post_data.get(f"{prefix}change-{index}-to_value", ""),
                },
                "filters": {},
                "unit": post_data.get(f"{prefix}change-{index}-unit", ""),
            }
```

- [ ] **Step 4.4: Run the tests to confirm they pass**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.CompileScenariosViewTest -v 2
```

Expected: all `CompileScenariosViewTest` tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/tests/test_views.py
git commit -m "feat(scenario-builder): parse per-change unit field from POST data"
```

---

## Task 5: Wire `htmx_run_scenario` to use `stats_for_scenario`

**Why:** The "Run Scenario" button is the primary feedback loop for users — it's where the multiplier must affect displayed numbers.

**Files:**
- Modify: `djangoexact/admin_scripts/views.py` (`htmx_run_scenario` body)
- Test: `djangoexact/admin_scripts/tests/test_views.py`

- [ ] **Step 5.1: Write the failing test**

Append to the `CompileScenariosViewTest` class in `djangoexact/admin_scripts/tests/test_views.py`:

```python
    def test_run_scenario_applies_unit_multiplier(self):
        """Posting unit=2 doubles the sum/mean compared to unit=1."""
        self.client.login(email="staff@example.com", password="testpass123")

        base_post = {
            "scenario_index": "0",
            "scenario-0-change-0-module_type": "Grassland",
            "scenario-0-change-0-field": "grassland_management_type",
            "scenario-0-change-0-from_value": "Non-Degraded",
            "scenario-0-change-0-to_value": "Improved Grassland",
        }

        # Baseline: unit=1 (one matching Grassland record with total=-2.0 in fixtures)
        response_one = self.client.post(
            "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
            {**base_post, "scenario-0-change-0-unit": "1"},
        )
        self.assertEqual(response_one.status_code, 200)
        self.assertContains(response_one, "-2.0")

        # unit=2 should scale to -4.0
        response_two = self.client.post(
            "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
            {**base_post, "scenario-0-change-0-unit": "2"},
        )
        self.assertEqual(response_two.status_code, 200)
        self.assertContains(response_two, "-4.0")
```

(`CompileScenariosViewTest.setUp` already creates one Grassland record with `total=-2.0`, `from_value="Non-Degraded"`, `to_value="Improved Grassland"`. The test asserts on the rendered string `-2.0` / `-4.0` — that is how `scenario_results.html` formats the sum.)

- [ ] **Step 5.2: Run the test to confirm it fails**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.CompileScenariosViewTest.test_run_scenario_applies_unit_multiplier -v 2
```

Expected: the `-4.0` assertion fails — without the wiring, both responses still show `-2.0`.

- [ ] **Step 5.3: Update `htmx_run_scenario`**

In `djangoexact/admin_scripts/views.py`, find `htmx_run_scenario`. Replace the import block at the top of the function logic (the current body that builds `q_objects` / `aggregates` / `stats`):

Locate:
```python
        q_objects = build_scenario_query(changes, global_filters)
        aggregates = ChangeRecord.objects.filter(q_objects)
        stats = stats_for(aggregates)
```

Replace with:
```python
        stats = stats_for_scenario(changes, global_filters)
```

Then update the import at the top of `views.py`:

Locate:
```python
from admin_scripts.scenario_utils import build_scenario_query, stats_for
```

Replace with:
```python
from admin_scripts.scenario_utils import build_scenario_query, stats_for, stats_for_scenario
```

(Keep `build_scenario_query` and `stats_for` in the import — they remain used by the export path until Task 7. The `from minitool.models import ChangeRecord` line stays untouched throughout this plan — `htmx_filters` still uses it to populate the region/climate dropdowns.)

- [ ] **Step 5.4: Run the tests to confirm they pass**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.CompileScenariosViewTest -v 2
```

Expected: `test_run_scenario_applies_unit_multiplier` passes; all other `CompileScenariosViewTest` tests still pass (existing "run scenario" tests do not assert specific numbers, so the parallel-codepath swap should not break them).

- [ ] **Step 5.5: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/tests/test_views.py
git commit -m "feat(scenario-builder): wire htmx_run_scenario to stats_for_scenario"
```

---

## Task 6: Add the Units input to `change_fieldset.html`

**Why:** This is the UI surface for the feature. Until this lands, the multiplier is settable only via crafted POST, not through the form.

**Files:**
- Modify: `djangoexact/admin_scripts/templates/admin_scripts/partials/change_fieldset.html`
- Test: `djangoexact/admin_scripts/tests/test_views.py` (smoke test on rendered markup)

- [ ] **Step 6.1: Write the failing tests**

Append to the `CompileScenariosViewTest` class in `djangoexact/admin_scripts/tests/test_views.py`:

```python
    def test_compile_scenarios_form_renders_unit_input(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/compile-scenarios/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="scenario-0-change-0-unit"')
        self.assertContains(response, 'Units')

    def test_htmx_add_change_includes_unit_input(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get(
            "/api/admin-scripts/compile-scenarios/htmx/add-change/",
            {"index": "1", "scenario_index": "0"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="scenario-0-change-1-unit"')
```

- [ ] **Step 6.2: Run the tests to confirm they fail**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.CompileScenariosViewTest.test_compile_scenarios_form_renders_unit_input admin_scripts.tests.CompileScenariosViewTest.test_htmx_add_change_includes_unit_input -v 2
```

Expected: both fail because `name="..."-unit"` is nowhere in the rendered output.

- [ ] **Step 6.3: Add the Units input to the template**

In `djangoexact/admin_scripts/templates/admin_scripts/partials/change_fieldset.html`, locate the closing `</div>` of `id="{{ id_prefix }}-values-container"` (the grid containing From Value / To Value). Immediately after that closing `</div>` and before the `<details class="mt-3">` block for "Change-level Filters", insert:

```html
        <div class="mt-3">
            <label class="block text-xs font-medium text-gray-500 mb-1">Units</label>
            <input type="number"
                   name="{{ prefix }}unit"
                   step="any"
                   min="0"
                   value="{{ change.unit|default:'1' }}"
                   placeholder="1.0"
                   class="w-full sm:w-48 border border-gray-300 rounded px-3 py-2 text-sm">
            <p class="text-xs text-gray-400 mt-1">Multiplier applied to each matched record's total.</p>
        </div>
```

Also update the inline `change-summary` span — locate:

```html
            <span class="text-xs text-gray-400 change-summary">
                {% if change.module_type %}— {{ change.module_type }}: {{ change.start.value }} &rarr; {{ change.end.value }}{% endif %}
            </span>
```

Replace with:

```html
            <span class="text-xs text-gray-400 change-summary">
                {% if change.module_type %}— {{ change.module_type }}: {{ change.start.value }} &rarr; {{ change.end.value }}{% if change.unit and change.unit != '1' and change.unit != '1.0' %} &times; {{ change.unit }}{% endif %}{% endif %}
            </span>
```

- [ ] **Step 6.4: Run the tests to confirm they pass**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.CompileScenariosViewTest -v 2
```

Expected: all `CompileScenariosViewTest` tests pass, including the two new render tests. Existing `test_run_scenario_*` tests that don't supply a `unit` field continue to work (the parser defaults missing fields to `""`, `_coerce_unit("")` returns `1.0`).

- [ ] **Step 6.5: Commit**

```bash
git add djangoexact/admin_scripts/templates/admin_scripts/partials/change_fieldset.html djangoexact/admin_scripts/tests/test_views.py
git commit -m "feat(scenario-builder): add Units input to change fieldset"
```

---

## Task 7: Wire the Excel export to use `stats_for_scenario` and add the Units column

**Why:** The Summary sheet's stats must reflect scaled values, and the per-scenario Changes sheet must record the unit each change was run with so the workbook is self-describing.

**Files:**
- Modify: `djangoexact/admin_scripts/views.py` (`compile_scenarios_export`)
- Test: `djangoexact/admin_scripts/tests/test_views.py`

- [ ] **Step 7.1: Write the failing test**

Append to the `CompileScenariosViewTest` class in `djangoexact/admin_scripts/tests/test_views.py`:

```python
    def test_export_includes_units_column_in_changes_sheet(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/compile-scenarios/export/", {
            "scenario-0-scenario_name": "Test Export",
            "scenario-0-category": "Test",
            "scenario-0-change-0-module_type": "Grassland",
            "scenario-0-change-0-field": "grassland_management_type",
            "scenario-0-change-0-from_value": "Non-Degraded",
            "scenario-0-change-0-to_value": "Improved Grassland",
            "scenario-0-change-0-unit": "2.5",
        })
        self.assertEqual(response.status_code, 200)

        import openpyxl
        buf = io.BytesIO(b"".join(response.streaming_content))
        wb = openpyxl.load_workbook(buf)
        ws = wb["Test Export Changes"]
        # Header row
        headers = [cell.value for cell in ws[1]]
        self.assertIn("Units", headers)
        units_col = headers.index("Units")
        # First data row should have the unit value we posted (stored as string in our dict)
        self.assertEqual(str(ws[2][units_col].value), "2.5")

    def test_export_summary_reflects_unit_scaling(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/compile-scenarios/export/", {
            "scenario-0-scenario_name": "Scaled",
            "scenario-0-category": "Test",
            "scenario-0-change-0-module_type": "Grassland",
            "scenario-0-change-0-field": "grassland_management_type",
            "scenario-0-change-0-from_value": "Non-Degraded",
            "scenario-0-change-0-to_value": "Improved Grassland",
            "scenario-0-change-0-unit": "2",
        })
        self.assertEqual(response.status_code, 200)

        import openpyxl
        buf = io.BytesIO(b"".join(response.streaming_content))
        wb = openpyxl.load_workbook(buf)
        ws = wb["Summary"]
        headers = [cell.value for cell in ws[1]]
        sum_col = headers.index("Sum Total")
        # Fixture has one matching Grassland row with total=-2.0; unit=2 -> sum=-4.0
        self.assertAlmostEqual(ws[2][sum_col].value, -4.0, places=5)
```

- [ ] **Step 7.2: Run the tests to confirm they fail**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.CompileScenariosViewTest.test_export_includes_units_column_in_changes_sheet admin_scripts.tests.CompileScenariosViewTest.test_export_summary_reflects_unit_scaling -v 2
```

Expected:
- `test_export_includes_units_column_in_changes_sheet` fails with `ValueError: 'Units' is not in list` (or `KeyError` on the worksheet) — no Units column today.
- `test_export_summary_reflects_unit_scaling` fails because the sum is `-2.0` (legacy path) not `-4.0`.

- [ ] **Step 7.3: Update `compile_scenarios_export`**

In `djangoexact/admin_scripts/views.py`, locate `compile_scenarios_export`. Replace the per-scenario loop body that currently reads:

```python
        for scenario in scenarios:
            scenario_name = scenario["scenario_name"] or "Unnamed Scenario"
            category = scenario["category"]
            changes = scenario["changes"]

            if not changes:
                continue

            q_objects = build_scenario_query(changes, global_filters)
            aggregates = ChangeRecord.objects.filter(q_objects)
            statistics = stats_for(aggregates)

            summary_rows.append({
                "Category": category,
                "Scenario Name": scenario_name,
                "Count": statistics.get("count", 0),
                "Sum Total": statistics.get("sum_total"),
                "Mean": statistics.get("mean"),
                "Median": statistics.get("median"),
                "Min": statistics.get("min"),
                "Max": statistics.get("max"),
                "Std Dev": statistics.get("std"),
                "Q1": statistics.get("q1"),
                "Q3": statistics.get("q3"),
                "IQR": statistics.get("iqr"),
                "CI 95%": statistics.get("ci_95"),
                "CI 99%": statistics.get("ci_99"),
            })

            # Changes sheet
            changes_sheet = f"{scenario_name} Changes"[:31]
            changes_data = []
            for i, change in enumerate(changes, 1):
                changes_data.append({
                    "Change #": i,
                    "Module Type": change.get("module_type", ""),
                    "Field": change["start"]["field"],
                    "From Value": change["start"]["value"],
                    "To Value": change["end"]["value"],
                })
            if changes_data:
                pd.DataFrame(changes_data).to_excel(writer, sheet_name=changes_sheet, index=False)
```

with:

```python
        for scenario in scenarios:
            scenario_name = scenario["scenario_name"] or "Unnamed Scenario"
            category = scenario["category"]
            changes = scenario["changes"]

            if not changes:
                continue

            statistics = stats_for_scenario(changes, global_filters)

            summary_rows.append({
                "Category": category,
                "Scenario Name": scenario_name,
                "Count": statistics.get("count", 0),
                "Sum Total": statistics.get("sum_total"),
                "Mean": statistics.get("mean"),
                "Median": statistics.get("median"),
                "Min": statistics.get("min"),
                "Max": statistics.get("max"),
                "Std Dev": statistics.get("std"),
                "Q1": statistics.get("q1"),
                "Q3": statistics.get("q3"),
                "IQR": statistics.get("iqr"),
                "CI 95%": statistics.get("ci_95"),
                "CI 99%": statistics.get("ci_99"),
            })

            # Changes sheet
            changes_sheet = f"{scenario_name} Changes"[:31]
            changes_data = []
            for i, change in enumerate(changes, 1):
                changes_data.append({
                    "Change #": i,
                    "Module Type": change.get("module_type", ""),
                    "Field": change["start"]["field"],
                    "From Value": change["start"]["value"],
                    "To Value": change["end"]["value"],
                    "Units": change.get("unit", ""),
                })
            if changes_data:
                pd.DataFrame(changes_data).to_excel(writer, sheet_name=changes_sheet, index=False)
```

Then clean up the `scenario_utils` imports at the top of `views.py`. Locate:

```python
from admin_scripts.scenario_utils import build_scenario_query, stats_for, stats_for_scenario
```

Replace with:

```python
from admin_scripts.scenario_utils import stats_for_scenario
```

**Keep** the `from minitool.models import ChangeRecord` line as-is — `htmx_filters` still uses `ChangeRecord.objects.filter(...)` to populate the region/climate filter dropdowns. Verify before removing anything:

```bash
grep -n "ChangeRecord" djangoexact/admin_scripts/views.py
```

After Task 7, expect exactly three remaining `ChangeRecord` references in `views.py`: the import line, the `description` string in the SCRIPTS list, and the `htmx_filters` queryset. All three stay.

- [ ] **Step 7.4: Run the tests to confirm they pass**

Run:
```bash
python djangoexact/manage.py test admin_scripts.tests.CompileScenariosViewTest -v 2
```

Expected: all tests pass, including the two new export tests.

- [ ] **Step 7.5: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/tests/test_views.py
git commit -m "feat(scenario-builder): scale export stats by unit, add Units column"
```

---

## Task 8: Full test sweep and manual UI smoke test

**Why:** Confirm the whole module's tests still pass together (not just one TestCase) and that the form is usable end-to-end before opening a PR.

- [ ] **Step 8.1: Run the entire admin_scripts test module**

Run:
```bash
python djangoexact/manage.py test admin_scripts -v 2
```

Expected: zero failures, zero errors. Note any test counts so you can confirm new tests were collected (existing suite ~50 tests; expect +~17 new).

- [ ] **Step 8.2: Manual UI smoke test**

Start the dev server (a separate terminal works fine):

```bash
python djangoexact/manage.py runserver
```

In a browser, sign in as a staff user and open:

```
http://localhost:8000/api/admin-scripts/compile-scenarios/
```

Verify, in order:

1. The first Change row shows a **Units** input with default value `1`.
2. Clicking "+ Add Another Change" produces a second change row that also has its own Units input (named `scenario-0-change-1-unit`).
3. Filling in module type / field / from / to with no edit to Units, then clicking "Run Scenario", returns stats that match what the legacy build produced (sanity check; the underlying records are unchanged).
4. Changing Units to `2` and re-running doubles the displayed `Sum Total` and `Mean`.
5. Changing the **module type** for that change does *not* clobber the typed Units value (because Units lives outside the swap target).
6. Click "Export All to Excel" with at least one scenario configured. Open the downloaded `.xlsx`. The per-scenario "<name> Changes" sheet has a `Units` column populated with the value you entered (or empty if you left the default).

Record any deviation as a fix-up commit before opening the PR.

Stop the dev server (Ctrl+C in the runserver terminal).

- [ ] **Step 8.3: Verify branch state**

Run:
```bash
git status
git log --oneline develop..HEAD
```

Expected: working tree clean. The feature branch has 1 spec doc commit (from the brainstorming phase) plus 7 implementation commits from Tasks 1, 2, 3, 4, 5, 6, 7.

---

## Task 9: Push the branch and open the PR

- [ ] **Step 9.1: Sync with remote develop and push**

Run:
```bash
git fetch origin
git rebase origin/develop
bd dolt push
git push -u origin feature/scenario-builder-per-change-units
```

If the rebase surfaces conflicts, resolve them (the only files this plan touches are listed in the File Map; any conflict will be inside one of them or in `.beads/issues.jsonl`).

Expected after success: `git status` shows `up to date with origin/feature/scenario-builder-per-change-units` and `git log -1 --oneline` matches the local HEAD.

- [ ] **Step 9.2: Open the PR**

Run:
```bash
gh pr create --base develop --title "feat(scenario-builder): per-change unit multipliers" --body "$(cat <<'EOF'
## Summary

- Adds a per-Change-row **Units** numeric multiplier to the admin-scripts scenario builder.
- Each `ChangeRecord` matched by a change now contributes `record.total × change.unit` (default `1.0`) to that scenario's distribution.
- The Excel export's per-scenario "<name> Changes" sheet gains a **Units** column; the Summary sheet's numbers reflect the scaled distribution.
- Default `1.0` preserves existing behavior for any scenario without an explicit unit. No DB migration.

Spec: `docs/superpowers/specs/2026-05-12-scenario-builder-per-change-units-design.md`
Plan: `docs/superpowers/plans/2026-05-12-scenario-builder-per-change-units.md`
Beads: `exact-django-webapp-5os`

## Test plan

- [x] `python djangoexact/manage.py test admin_scripts` — full module green
- [x] Manual UI: Units input visible, defaults to 1, persists across module-type/field changes, doubling the unit doubles the displayed Sum/Mean
- [x] Excel export: Changes sheet has Units column; Summary sheet reflects scaled stats
EOF
)"
```

Expected: a PR URL is printed. Surface that URL to the user as the final step.

- [ ] **Step 9.3: Close the beads issue**

```bash
bd close exact-django-webapp-5os --reason="Implemented per-change unit multipliers in admin_scripts scenario builder. PR opened."
```

- [ ] **Step 9.4: Restore the stashed README/CONTRIBUTING edits on develop**

The brainstorming phase stashed unrelated edits before branching. They belong on `develop`, not on this feature branch:

```bash
git checkout develop
git stash list
# Confirm the stash labeled "WIP: README/CONTRIBUTING edits — unrelated to per-change-units feature" exists, then:
git stash pop
git status
```

Expected: the README/CONTRIBUTING/README.pdf changes reappear on `develop`. Do **not** push or commit them as part of this work — the user owns that decision separately.

Return to the feature branch only if more work on this PR is required:

```bash
git checkout feature/scenario-builder-per-change-units
```
