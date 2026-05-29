# Scenario Builder — Live-Compiled Results Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat 12-stat grid in the Compile Scenarios admin tool with a dedicated Compare tab that aggregates per-scenario results into a chip strip, mean+CI bar chart, distribution box plots, per-change composition stacks, and a comparison table — all client-side.

**Architecture:** Each scenario's existing **Run Scenario** HTMX response is enriched with `data-scenario-result` JSON. A new vanilla-JS file (`compare.js`) listens for swap events, stores results in `window.scenarioResults`, tracks form-input hashes for stale detection, and renders the Compare tab using Chart.js + plugins via CDN. No new server endpoints; no server-side state.

**Tech Stack:** Django 4.x, Python, HTMX (existing), Tailwind via CDN (existing), Chart.js 4 + `@sgratzl/chartjs-chart-boxplot` + `chartjs-chart-error-bars` (new CDN deps), vanilla ES6 JS (no build step), Django `TestCase` for backend tests.

**Spec:** `docs/superpowers/specs/2026-05-26-scenario-builder-results-visualization-design.md`

**Sandbox constraint:** The local dev environment has no Postgres/Docker — `manage.py` cannot bootstrap, so DB-requiring tests cannot run locally. `py_compile` is the only local syntax gate; Django/JS tests run in CI on the PR. Browser smoke testing requires a DB-equipped machine.

---

## File Structure

**Backend (Python):**

- `djangoexact/admin_scripts/scenario_utils.py` — extend `stats_for_scenario` with `outliers_low`, `outliers_high`, `per_change`. No changes to other helpers.
- `djangoexact/admin_scripts/views.py` — extend `htmx_run_scenario` context with `scenario_index` and `result_json`.
- `djangoexact/admin_scripts/tests/test_views.py` — extend `ScenarioUtilsTest` with new test methods for outlier counts, per-change rollup, and view context.

**Templates:**

- `djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_results.html` — restructure with always-rendered outer `<div data-scenario-result data-scenario-index>` wrapper; slim one-line headline replacing the 12-cell grid.
- `djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_panel.html` — pass `scenario_index` through the initial-render include (one-line edit).
- `djangoexact/admin_scripts/templates/admin_scripts/partials/compare_panel.html` — **new**, empty mount points (`#cmp-chips`, `#cmp-bar`, `#cmp-box`, `#cmp-composition`, `#cmp-table`).
- `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html` — add Compare tab button, include compare panel, add Chart.js CDN scripts, load `compare.js`.

**Frontend (static JS):**

- `djangoexact/admin_scripts/static/admin_scripts/compare.js` — **new**, manages `window.scenarioResults`, form-input hashing, Compare tab activation, chip rendering, four chart renderings, table rendering, MutationObserver for scenario removal.

Each file has one clear responsibility. `scenario_utils.py` does math. `views.py` is the glue between request and template. Each template renders one well-bounded fragment. `compare.js` is the single owner of browser-side comparison state.

---

## Task 1: Add `outliers_low` / `outliers_high` to `stats_for_scenario`

**Files:**
- Modify: `djangoexact/admin_scripts/scenario_utils.py`
- Test: `djangoexact/admin_scripts/tests/test_views.py`

- [ ] **Step 1: Write the failing tests**

Append to the `ScenarioUtilsTest` class in `djangoexact/admin_scripts/tests/test_views.py`:

```python
    def test_stats_for_scenario_no_outliers_in_baseline_fixture(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        # The five-record baseline fixture (-3.0, -2.5, -2.0, -1.5, -1.0) has no
        # values past Q3+1.5*IQR or below Q1-1.5*IQR.
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
        }]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(stats["outliers_low"], 0)
        self.assertEqual(stats["outliers_high"], 0)

    def test_stats_for_scenario_counts_outliers_outside_iqr_fences(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        # Add two extreme records — one well below Q1 - 1.5*IQR, one above.
        # Baseline Q1=-2.75, Q3=-1.25, IQR=1.5, so fences are -5.0 / 1.0.
        # -100 is a low outlier; 50 is a high outlier.
        for extreme in (-100.0, 50.0):
            ChangeRecord.objects.create(
                module_type="Grassland",
                region="Central Asia",
                climate="Cool Temperate",
                moisture="Moist",
                soil_type="High Activity Clay",
                total=extreme,
                field="grassland_management_type",
                from_value="Non-Degraded",
                to_value="Improved Grassland",
            )
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
        }]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(stats["count"], 7)
        self.assertEqual(stats["outliers_low"], 1)
        self.assertEqual(stats["outliers_high"], 1)

    def test_stats_for_scenario_outlier_counts_zero_when_iqr_undefined(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        # With fewer than 4 values, IQR is undefined; outlier counts must be 0.
        ChangeRecord.objects.all().delete()
        ChangeRecord.objects.create(
            module_type="Grassland",
            region="Central Asia",
            climate="Cool Temperate",
            moisture="Moist",
            soil_type="High Activity Clay",
            total=1.0,
            field="grassland_management_type",
            from_value="Non-Degraded",
            to_value="Improved Grassland",
        )
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
        }]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["outliers_low"], 0)
        self.assertEqual(stats["outliers_high"], 0)
```

- [ ] **Step 2: Verify tests are syntactically valid (sandbox cannot run DB tests)**

Run from the repo root:

```bash
python -m py_compile djangoexact/admin_scripts/tests/test_views.py
```

Expected: exit 0, no output.
(On a CI/DB-equipped machine, the test would `FAIL` because `stats_for_scenario` does not yet return `outliers_low`/`outliers_high`. Locally this is taken on trust.)

- [ ] **Step 3: Implement outlier counting**

Edit `djangoexact/admin_scripts/scenario_utils.py`. At the bottom of `_descriptive_stats_from_values`, the dict already contains `q1`, `q3`, `iqr`. We compute outlier counts at the top level of `stats_for_scenario` (per the spec) because we have the materialized `scaled_values` list there.

Locate the existing `stats_for_scenario` function. Modify its return value:

```python
def stats_for_scenario(changes, global_filters):
    """Compute descriptive statistics over ``record.total × change.unit`` for
    every ChangeRecord matched by each change in *changes*.

    A record matching multiple changes is counted once *per matching change*
    (so its scaled value appears once for each change's unit). The unit
    defaults to 1.0 for missing / blank / non-numeric / negative inputs,
    which makes a scenario with no explicit units behave equivalently to the
    legacy ``stats_for(build_scenario_query(...))`` pipeline.
    """
    from minitool.models import ChangeRecord

    scaled_values = []
    for change in changes:
        if not change.get("module_type"):
            continue
        unit = _coerce_unit(change.get("unit"))
        q = _build_single_change_q(change, global_filters)
        totals = ChangeRecord.objects.filter(q).values_list("total", flat=True)
        if unit == 1.0:
            scaled_values.extend(totals)
        else:
            scaled_values.extend(v * unit for v in totals)

    stats = _descriptive_stats_from_values(scaled_values)

    # Outlier counts past the standard 1.5*IQR fences.
    # 0 when IQR is not defined (n < 4) — q1/q3 will be None and the
    # comparison below is skipped.
    outliers_low = 0
    outliers_high = 0
    q1, q3, iqr = stats["q1"], stats["q3"], stats["iqr"]
    if q1 is not None and q3 is not None and iqr is not None and len(scaled_values) >= 4:
        lo_fence = q1 - 1.5 * iqr
        hi_fence = q3 + 1.5 * iqr
        for v in scaled_values:
            if v < lo_fence:
                outliers_low += 1
            elif v > hi_fence:
                outliers_high += 1
    stats["outliers_low"] = outliers_low
    stats["outliers_high"] = outliers_high

    return stats
```

Also extend the empty-result branch of `_descriptive_stats_from_values` so callers reading the dict's shape see consistent keys. Locate the empty-list path inside that helper:

```python
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
```

`stats_for_scenario` adds `outliers_low`/`outliers_high` itself after calling the helper, so the helper does **not** need to know about them. Leave `_descriptive_stats_from_values` otherwise unchanged.

- [ ] **Step 4: Syntax-check the implementation**

```bash
python -m py_compile djangoexact/admin_scripts/scenario_utils.py
```

Expected: exit 0, no output.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/scenario_utils.py djangoexact/admin_scripts/tests/test_views.py
git commit -m "feat(scenario-builder): add outlier counts to stats_for_scenario"
```

---

## Task 2: Add `per_change` breakdown to `stats_for_scenario`

**Files:**
- Modify: `djangoexact/admin_scripts/scenario_utils.py`
- Test: `djangoexact/admin_scripts/tests/test_views.py`

- [ ] **Step 1: Write the failing tests**

Append to the `ScenarioUtilsTest` class:

```python
    def test_stats_for_scenario_per_change_single_change(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
            "unit": "2",
        }]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(len(stats["per_change"]), 1)
        entry = stats["per_change"][0]
        self.assertEqual(entry["module_type"], "Grassland")
        self.assertEqual(entry["field"], "grassland_management_type")
        self.assertEqual(entry["from_value"], "Non-Degraded")
        self.assertEqual(entry["to_value"], "Improved Grassland")
        self.assertEqual(entry["unit"], 2.0)
        self.assertEqual(entry["count"], 5)
        self.assertAlmostEqual(entry["sum"], -20.0, places=5)
        self.assertAlmostEqual(entry["mean"], -4.0, places=5)
        self.assertEqual(
            entry["label"],
            "Grassland: Non-Degraded → Improved Grassland",
        )

    def test_stats_for_scenario_per_change_two_changes_preserves_order(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        ChangeRecord.objects.create(
            module_type="Annual Cropland",
            region="Central Asia",
            climate="Cool Temperate",
            moisture="Moist",
            soil_type="High Activity Clay",
            total=-0.5,
            field="organic_input_type",
            from_value="Low C input",
            to_value="High C input",
        )
        changes = [
            {
                "module_type": "Annual Cropland",
                "start": {"field": "organic_input_type", "value": "Low C input"},
                "end": {"field": "organic_input_type", "value": "High C input"},
                "unit": "1",
            },
            {
                "module_type": "Grassland",
                "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
                "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
                "unit": "1",
            },
        ]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(len(stats["per_change"]), 2)
        self.assertEqual(stats["per_change"][0]["module_type"], "Annual Cropland")
        self.assertEqual(stats["per_change"][0]["count"], 1)
        self.assertAlmostEqual(stats["per_change"][0]["sum"], -0.5, places=5)
        self.assertEqual(stats["per_change"][1]["module_type"], "Grassland")
        self.assertEqual(stats["per_change"][1]["count"], 5)
        self.assertAlmostEqual(stats["per_change"][1]["sum"], -10.0, places=5)

    def test_stats_for_scenario_per_change_skips_change_without_module_type(self):
        from admin_scripts.scenario_utils import stats_for_scenario
        changes = [
            {"module_type": "", "start": {"field": "", "value": ""}, "end": {"field": "", "value": ""}},
            {
                "module_type": "Grassland",
                "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
                "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
            },
        ]
        stats = stats_for_scenario(changes, {})
        self.assertEqual(len(stats["per_change"]), 1)
        self.assertEqual(stats["per_change"][0]["module_type"], "Grassland")
```

- [ ] **Step 2: Syntax-check the test file**

```bash
python -m py_compile djangoexact/admin_scripts/tests/test_views.py
```

Expected: exit 0.

- [ ] **Step 3: Implement `per_change` rollup inside `stats_for_scenario`**

Replace the body of `stats_for_scenario` in `djangoexact/admin_scripts/scenario_utils.py` (now incorporating Task 1's outlier code) with:

```python
def stats_for_scenario(changes, global_filters):
    """Compute descriptive statistics over ``record.total × change.unit`` for
    every ChangeRecord matched by each change in *changes*.

    Returns the descriptive stats dict (see ``_descriptive_stats_from_values``)
    plus three extra keys:

    - ``outliers_low``  — count of scaled values below ``Q1 - 1.5*IQR``
    - ``outliers_high`` — count of scaled values above ``Q3 + 1.5*IQR``
    - ``per_change``    — list of per-change rollups in input order, one entry
                          per change with a ``module_type``. Each entry:
                          ``{label, module_type, field, from_value, to_value,
                          unit, count, sum, mean}``.
    """
    from minitool.models import ChangeRecord

    scaled_values = []
    per_change = []
    for change in changes:
        if not change.get("module_type"):
            continue
        unit = _coerce_unit(change.get("unit"))
        q = _build_single_change_q(change, global_filters)
        # Materialize once — used for both the aggregate distribution and the
        # per-change rollup. One query per change, identical to today.
        totals = list(ChangeRecord.objects.filter(q).values_list("total", flat=True))
        scaled = totals if unit == 1.0 else [v * unit for v in totals]
        scaled_values.extend(scaled)

        n_change = len(scaled)
        sum_change = sum(scaled) if n_change else 0.0
        mean_change = (sum_change / n_change) if n_change else None
        from_value = change["start"]["value"]
        to_value = change["end"]["value"]
        per_change.append({
            "label": f"{change['module_type']}: {from_value} → {to_value}",
            "module_type": change["module_type"],
            "field": change["start"]["field"],
            "from_value": from_value,
            "to_value": to_value,
            "unit": unit,
            "count": n_change,
            "sum": sum_change,
            "mean": mean_change,
        })

    stats = _descriptive_stats_from_values(scaled_values)

    # Outlier counts past the standard 1.5*IQR fences.
    outliers_low = 0
    outliers_high = 0
    q1, q3, iqr = stats["q1"], stats["q3"], stats["iqr"]
    if q1 is not None and q3 is not None and iqr is not None and len(scaled_values) >= 4:
        lo_fence = q1 - 1.5 * iqr
        hi_fence = q3 + 1.5 * iqr
        for v in scaled_values:
            if v < lo_fence:
                outliers_low += 1
            elif v > hi_fence:
                outliers_high += 1
    stats["outliers_low"] = outliers_low
    stats["outliers_high"] = outliers_high
    stats["per_change"] = per_change

    return stats
```

This replaces the version from Task 1. The change is: capture `totals` as a list (was a queryset before), reuse it for both aggregate `scaled_values.extend(...)` and the per-change rollup.

- [ ] **Step 4: Syntax-check**

```bash
python -m py_compile djangoexact/admin_scripts/scenario_utils.py
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/scenario_utils.py djangoexact/admin_scripts/tests/test_views.py
git commit -m "feat(scenario-builder): add per_change rollup to stats_for_scenario"
```

---

## Task 3: Pass `scenario_index` and `result_json` from `htmx_run_scenario`

**Files:**
- Modify: `djangoexact/admin_scripts/views.py`
- Test: `djangoexact/admin_scripts/tests/test_views.py`

- [ ] **Step 1: Write the failing tests**

Append a new test class to the bottom of `djangoexact/admin_scripts/tests/test_views.py`:

```python
@override_settings(MIDDLEWARE=MIDDLEWARE_WITHOUT_DB_CLEANUP)
class HtmxRunScenarioContextTest(TestCase):
    databases = {"default"}

    def setUp(self):
        self.client = Client()
        self.staff_user = CustomUser.objects.create_user(
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
            firebase_uid="staff_uid",
        )
        self.client.login(email="staff@example.com", password="testpass123")
        for i, total in enumerate([-3.0, -2.5, -2.0, -1.5, -1.0]):
            ChangeRecord.objects.create(
                module_type="Grassland",
                region="Central Asia",
                climate="Cool Temperate",
                moisture="Moist",
                soil_type="High Activity Clay",
                total=total,
                field="grassland_management_type",
                from_value="Non-Degraded",
                to_value="Improved Grassland",
                csv_row_data={"row": i},
            )

    def _post_run_scenario(self, scenario_index="0", scenario_name="My Scenario"):
        return self.client.post(
            "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
            {
                "scenario_index": scenario_index,
                f"scenario-{scenario_index}-scenario_name": scenario_name,
                f"scenario-{scenario_index}-category": "",
                f"scenario-{scenario_index}-change-0-module_type": "Grassland",
                f"scenario-{scenario_index}-change-0-field": "grassland_management_type",
                f"scenario-{scenario_index}-change-0-from_value": "Non-Degraded",
                f"scenario-{scenario_index}-change-0-to_value": "Improved Grassland",
                f"scenario-{scenario_index}-change-0-unit": "1",
            },
        )

    def test_response_contains_data_scenario_result_attribute(self):
        import json
        response = self._post_run_scenario(scenario_index="2", scenario_name="Foo")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn('data-scenario-result=', body)
        self.assertIn('data-scenario-index=\'2\'', body)

    def test_data_scenario_result_payload_parses_and_has_expected_keys(self):
        import json, html
        response = self._post_run_scenario(scenario_index="0", scenario_name="Foo")
        body = response.content.decode("utf-8")
        # Extract the JSON inside data-scenario-result='...'
        marker = "data-scenario-result='"
        start = body.index(marker) + len(marker)
        end = body.index("'", start)
        raw = html.unescape(body[start:end])
        payload = json.loads(raw)
        self.assertEqual(payload["scenario_index"], "0")
        self.assertEqual(payload["scenario_name"], "Foo")
        self.assertIn("statistics", payload)
        self.assertEqual(payload["statistics"]["count"], 5)
        self.assertIn("outliers_low", payload["statistics"])
        self.assertIn("per_change", payload["statistics"])
        self.assertEqual(payload["gaps"], [])
        self.assertIsNone(payload["error"])
        self.assertFalse(payload["not_computed"])

    def test_data_scenario_result_present_when_no_matching_records(self):
        import json, html
        response = self.client.post(
            "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
            {
                "scenario_index": "0",
                "scenario-0-scenario_name": "Empty",
                "scenario-0-category": "",
                "scenario-0-change-0-module_type": "Grassland",
                "scenario-0-change-0-field": "grassland_management_type",
                "scenario-0-change-0-from_value": "DoesNotExist",
                "scenario-0-change-0-to_value": "AlsoMissing",
                "scenario-0-change-0-unit": "1",
            },
        )
        body = response.content.decode("utf-8")
        self.assertIn("data-scenario-result=", body)
        marker = "data-scenario-result='"
        start = body.index(marker) + len(marker)
        end = body.index("'", start)
        raw = html.unescape(body[start:end])
        payload = json.loads(raw)
        # statistics dict is always present, even on a zero-count scenario
        self.assertIn("statistics", payload)
        self.assertEqual(payload["statistics"]["count"], 0)
```

- [ ] **Step 2: Syntax-check**

```bash
python -m py_compile djangoexact/admin_scripts/tests/test_views.py
```

Expected: exit 0.

- [ ] **Step 3: Update `htmx_run_scenario` to populate the new context keys**

Edit `djangoexact/admin_scripts/views.py`. Find the `htmx_run_scenario` function (currently ending around line 533). Replace it with:

```python
@login_required(login_url="/admin/login/")
@staff_required
def htmx_run_scenario(request):
    if request.method != "POST":
        return HttpResponse("POST required", status=405)

    import json

    scenario_index = request.POST.get("scenario_index", "0")
    prefix = f"scenario-{scenario_index}-"

    changes = _parse_changes_from_post(request.POST, prefix=prefix)
    global_filters = _parse_global_filters(request.POST)

    context = {
        "scenario_index": scenario_index,
    }
    stats = None
    gaps = []
    error = None
    not_computed = False

    if not changes:
        error = "Please add at least one change."
        context["error"] = error
    else:
        stats = stats_for_scenario(changes, global_filters)

        if stats["count"] == 0:
            # Check whether the empty result is due to ungrown data rather
            # than user error.
            for change in changes:
                field = change["start"]["field"]
                from_val = change["start"]["value"]
                to_val = change["end"]["value"]
                if detect_gap(change["module_type"], field, from_val, to_val):
                    gaps.append({
                        "module_type": change["module_type"],
                        "field": field,
                        "from_value": from_val,
                        "to_value": to_val,
                    })
            if gaps:
                context["gaps"] = gaps
            else:
                context["statistics"] = stats
        else:
            context["statistics"] = stats

    # Always-present payload for the Compare tab. ``statistics`` is included
    # even when ``count == 0`` so the client never has to special-case.
    payload = {
        "scenario_index": scenario_index,
        "scenario_name": request.POST.get(f"{prefix}scenario_name", ""),
        "category": request.POST.get(f"{prefix}category", ""),
        "statistics": stats if stats is not None else _empty_stats(),
        "gaps": gaps,
        "error": error,
        "not_computed": not_computed,
    }
    context["result_json"] = json.dumps(payload, default=str)

    return render(request, "admin_scripts/partials/scenario_results.html", context)


def _empty_stats():
    """Same shape ``stats_for_scenario`` returns when no scaled values exist,
    plus the new fields. Used when ``htmx_run_scenario`` cannot run the
    aggregation (no changes provided) — gives the Compare tab a stable schema.
    """
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
        "outliers_low": 0,
        "outliers_high": 0,
        "per_change": [],
    }
```

The `import json` is local to keep the existing import block tidy; module-level would also be fine — pick one and stay consistent. The `_empty_stats` helper is defined in the same module right below `htmx_run_scenario`.

- [ ] **Step 4: Syntax-check**

```bash
python -m py_compile djangoexact/admin_scripts/views.py
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/tests/test_views.py
git commit -m "feat(scenario-builder): add result_json + scenario_index to run-scenario response"
```

---

## Task 4: Restructure `scenario_results.html` + update `scenario_panel.html` include

**Files:**
- Modify: `djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_results.html`
- Modify: `djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_panel.html`

- [ ] **Step 1: Rewrite `scenario_results.html`**

Open `djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_results.html` and replace its entire contents with:

```html
<div data-scenario-result='{{ result_json|default:""|escape }}'
     data-scenario-index='{{ scenario_index|default:"" }}'>

    {% if statistics %}
        {% if statistics.count > 0 %}
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
        {% else %}
        <div class="bg-white border border-gray-200 rounded-lg p-5 mt-4">
            <p class="text-sm text-gray-500">No matching records for this scenario.</p>
        </div>
        {% endif %}
    {% endif %}

    {% if gaps %}
    <div class="mt-4 bg-amber-50 border border-amber-200 text-amber-700 rounded-lg p-4 text-sm">
        <p class="font-medium">Data not yet computed</p>
        <p class="mt-1">The following combinations have no pre-computed results:</p>
        <ul class="mt-2 list-disc list-inside">
            {% for gap in gaps %}
            <li>
                {{ gap.module_type }} / {{ gap.field }}: {{ gap.from_value }} &rarr; {{ gap.to_value }}
                <button type="button"
                        hx-post="{% url 'admin_scripts:htmx-enqueue-job' %}"
                        hx-vals='{"module_type": "{{ gap.module_type }}", "attribute": "{{ gap.field }}", "from_value": "{{ gap.from_value }}", "to_value": "{{ gap.to_value }}"}'
                        hx-target="closest li"
                        hx-swap="outerHTML"
                        class="ml-2 text-xs text-blue-600 hover:text-blue-800 underline">
                    Compute
                </button>
            </li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}

    {% if error %}
    <div class="mt-4 bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
        {{ error }}
    </div>
    {% endif %}

    {% if not_computed %}
    <div class="mt-4 bg-amber-50 border border-amber-200 text-amber-700 rounded-lg p-4 text-sm">
        <p class="font-medium">Data not yet computed</p>
        <p class="mt-1">No pre-computed results exist for this scenario combination.</p>
    </div>
    {% endif %}
</div>
```

The gap, error, and not_computed banner markup is preserved verbatim from the existing template. The 12-cell stat grid is replaced by the one-line headline.

- [ ] **Step 2: Update the include in `scenario_panel.html`**

Open `djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_panel.html` and find the existing include on or near line 24:

```
{% include "admin_scripts/partials/scenario_results.html" with statistics=scenario.statistics %}
```

Replace with:

```
{% include "admin_scripts/partials/scenario_results.html" with statistics=scenario.statistics scenario_index=scenario_index %}
```

`result_json` is intentionally not passed here — the initial-render path on GET never carries a precomputed result, so the wrapper renders with an empty `data-scenario-result=""`.

- [ ] **Step 3: Local syntax check (Django template syntax has no compile gate; rely on the runserver smoke)**

Open the file once to verify no stray markers:

```bash
grep -n "{% endif %}\|{% endfor %}\|{% if" djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_results.html
```

Expected: each `{% if %}` paired with an `{% endif %}`; each `{% for %}` paired with `{% endfor %}`.

- [ ] **Step 4: Commit**

```bash
git add djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_results.html \
        djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_panel.html
git commit -m "refactor(scenario-builder): slim per-scenario result headline + data-scenario-result wrapper"
```

---

## Task 5: Create `compare_panel.html` and wire Compare tab into `compile_scenarios.html`

**Files:**
- Create: `djangoexact/admin_scripts/templates/admin_scripts/partials/compare_panel.html`
- Modify: `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html`

- [ ] **Step 1: Create the empty compare panel template**

Write `djangoexact/admin_scripts/templates/admin_scripts/partials/compare_panel.html`:

```html
<div data-compare-panel class="hidden">
    <div id="cmp-empty" class="text-sm text-gray-500 p-6 text-center bg-white border border-gray-200 rounded-lg">
        Run at least one scenario to populate the comparison view.
    </div>

    <div id="cmp-chips" class="hidden flex flex-wrap gap-2 mb-4"></div>

    <div id="cmp-bar" class="hidden bg-white border border-gray-200 rounded-lg p-5 mb-4">
        <h3 class="text-md font-semibold text-gray-900 mb-3">Mean &plusmn; CI 95%</h3>
        <div style="position: relative; height: 280px;"><canvas></canvas></div>
    </div>

    <div id="cmp-box" class="hidden bg-white border border-gray-200 rounded-lg p-5 mb-4">
        <h3 class="text-md font-semibold text-gray-900 mb-3">Distribution</h3>
        <div style="position: relative; height: 280px;"><canvas></canvas></div>
    </div>

    <div id="cmp-composition" class="hidden bg-white border border-gray-200 rounded-lg p-5 mb-4">
        <h3 class="text-md font-semibold text-gray-900 mb-3">Per-change contribution to sum</h3>
        <div style="position: relative; height: 280px;"><canvas></canvas></div>
    </div>

    <div id="cmp-table" class="hidden bg-white border border-gray-200 rounded-lg p-5 mb-4">
        <h3 class="text-md font-semibold text-gray-900 mb-3">All statistics</h3>
        <div data-cmp-table-body class="overflow-x-auto"></div>
    </div>
</div>
```

Each chart canvas is wrapped in a fixed-height relative div — Chart.js requires that or it stretches indefinitely.

- [ ] **Step 2: Add the Compare tab button and include the compare panel in `compile_scenarios.html`**

Open `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html`.

Find the tab bar block (around line 14):

```html
{# Tab bar #}
<div class="flex items-center gap-1 border-b border-gray-200 mb-4">
    <div id="scenario-tabs" class="flex">
        {% for scenario in scenarios %}
        <button type="button" data-scenario-tab="{{ forloop.counter0 }}"
                onclick="switchScenarioTab({{ forloop.counter0 }})"
                class="px-4 py-2 text-sm font-medium border-b-2 {% if forloop.first %}border-blue-500 text-blue-600{% else %}border-transparent text-gray-500 hover:text-gray-700{% endif %}">
            Scenario {{ forloop.counter }}
        </button>
        {% endfor %}
    </div>
    <button type="button"
            hx-get="{% url 'admin_scripts:htmx-add-scenario' %}"
            hx-target="#scenario-panels"
            hx-swap="beforeend"
            hx-vals='js:{"index": document.querySelectorAll("[data-scenario-panel]").length}'
            hx-on::after-settle="switchScenarioTab(document.querySelectorAll('[data-scenario-panel]').length - 1)"
            class="px-3 py-2 text-sm text-blue-600 hover:text-blue-800 font-medium">
        + Add Scenario
    </button>
</div>
```

Add a Compare tab button right before the closing `</div>` of the outer tab bar, using `ml-auto` so it floats to the right:

```html
    <button type="button" data-scenario-tab="compare"
            onclick="switchScenarioTab('compare')"
            class="ml-auto px-4 py-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">
        Compare
    </button>
</div>
```

Find the scenario panels block (around line 37):

```html
{# Scenario panels #}
<div id="scenario-panels">
    {% for scenario in scenarios %}
        {% include "admin_scripts/partials/scenario_panel.html" with scenario_index=forloop.counter0 scenario=scenario module_types=module_types default_prefix=scenario.default_prefix default_id_prefix=scenario.default_id_prefix active=forloop.first %}
    {% endfor %}
</div>
```

Immediately after the closing `</div>` of `#scenario-panels`, include the compare panel:

```html
{% include "admin_scripts/partials/compare_panel.html" %}
```

Find the existing `switchScenarioTab` function in the `<script>` block (around line 71):

```javascript
function switchScenarioTab(index) {
    document.querySelectorAll('[data-scenario-panel]').forEach(function(p) {
        p.classList.add('hidden');
    });
    document.querySelectorAll('[data-scenario-tab]').forEach(function(t) {
        t.classList.remove('border-blue-500', 'text-blue-600');
        t.classList.add('border-transparent', 'text-gray-500');
    });
    var panel = document.querySelector('[data-scenario-panel="' + index + '"]');
    if (panel) panel.classList.remove('hidden');
    var tab = document.querySelector('[data-scenario-tab="' + index + '"]');
    if (tab) {
        tab.classList.add('border-blue-500', 'text-blue-600');
        tab.classList.remove('border-transparent', 'text-gray-500');
    }
}
```

Replace with the version that handles the `'compare'` sentinel:

```javascript
function switchScenarioTab(index) {
    // Hide every scenario panel and the compare panel.
    document.querySelectorAll('[data-scenario-panel]').forEach(function(p) {
        p.classList.add('hidden');
    });
    var comparePanel = document.querySelector('[data-compare-panel]');
    if (comparePanel) comparePanel.classList.add('hidden');

    // Reset every tab's active style.
    document.querySelectorAll('[data-scenario-tab]').forEach(function(t) {
        t.classList.remove('border-blue-500', 'text-blue-600');
        t.classList.add('border-transparent', 'text-gray-500');
    });

    // Show the requested panel.
    if (index === 'compare') {
        if (comparePanel) comparePanel.classList.remove('hidden');
        if (window.renderCompare) window.renderCompare();
    } else {
        var panel = document.querySelector('[data-scenario-panel="' + index + '"]');
        if (panel) panel.classList.remove('hidden');
    }

    // Highlight the active tab.
    var tab = document.querySelector('[data-scenario-tab="' + index + '"]');
    if (tab) {
        tab.classList.add('border-blue-500', 'text-blue-600');
        tab.classList.remove('border-transparent', 'text-gray-500');
    }
}
```

The Compare tab will land on an empty `data-compare-panel` div (showing only `#cmp-empty`) until `compare.js` is added in Task 6.

- [ ] **Step 3: Smoke-check (templates only, no JS yet)**

```bash
grep -n "Compare\|data-compare-panel\|compare_panel" djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html
```

Expected: shows the Compare button line, the compare panel include, and the new `switchScenarioTab` branch referring to `'compare'`.

- [ ] **Step 4: Commit**

```bash
git add djangoexact/admin_scripts/templates/admin_scripts/partials/compare_panel.html \
        djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html
git commit -m "feat(scenario-builder): add Compare tab + empty compare panel"
```

---

## Task 6: Create `compare.js` skeleton + load Chart.js CDN scripts

**Files:**
- Create: `djangoexact/admin_scripts/static/admin_scripts/compare.js`
- Modify: `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html`

- [ ] **Step 1: Create the JS skeleton**

Create the static directory and the file:

```bash
mkdir -p djangoexact/admin_scripts/static/admin_scripts
```

Write `djangoexact/admin_scripts/static/admin_scripts/compare.js`:

```javascript
/* admin_scripts: Compile Scenarios — comparison view.
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
```

- [ ] **Step 2: Load Chart.js + plugins + compare.js in `compile_scenarios.html`**

Open `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html`. At the very top of `{% block content %}` (just under the heading + intro `<p>` and before the `<form>`, or anywhere inside the block — Chart.js can be loaded anywhere before `compare.js` runs) verify the top of the file has `{% load static %}`:

```html
{% extends "admin_scripts/base.html" %}
{% load static %}
```

If `{% load static %}` is not already present after `{% extends %}`, add it.

Then find the bottom of `{% block content %}`, right before `{% endblock %}`, after the existing `<script>` block that defines `switchScenarioTab`. Add:

```html
{# Chart.js + plugins for the Compare tab. CDN parity with htmx / Tom Select. #}
{# nosemgrep: html.security.audit.missing-integrity.missing-integrity #}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
{# nosemgrep: html.security.audit.missing-integrity.missing-integrity #}
<script src="https://cdn.jsdelivr.net/npm/@sgratzl/chartjs-chart-boxplot@4"></script>
{# nosemgrep: html.security.audit.missing-integrity.missing-integrity #}
<script src="https://cdn.jsdelivr.net/npm/chartjs-chart-error-bars@4"></script>
<script src="{% static 'admin_scripts/compare.js' %}"></script>
```

SRI hashes are intentionally omitted to match the existing Tailwind/Tom Select CDN pattern in `base.html` (each preceded by a `nosemgrep` comment). A future task can compute and add SRI hashes via `curl <url> | openssl dgst -sha384 -binary | openssl base64 -A` if hardening is required.

- [ ] **Step 3: Smoke-check the static file lands**

```bash
ls djangoexact/admin_scripts/static/admin_scripts/compare.js
```

Expected: file exists.

```bash
node --check djangoexact/admin_scripts/static/admin_scripts/compare.js
```

Expected: exit 0, no output (Node is used purely as a syntax check; the file targets browser globals).

- [ ] **Step 4: Commit**

```bash
git add djangoexact/admin_scripts/static/admin_scripts/compare.js \
        djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html
git commit -m "feat(scenario-builder): add compare.js skeleton and load Chart.js CDN"
```

---

## Task 7: Implement state ingestion + form-hash + stale detection in `compare.js`

**Files:**
- Modify: `djangoexact/admin_scripts/static/admin_scripts/compare.js`

- [ ] **Step 1: Add the form-hash helper and the two event listeners**

Open `djangoexact/admin_scripts/static/admin_scripts/compare.js`. Inside the IIFE, after the `colorForScenario` function and before the placeholder `renderCompare`, add:

```javascript
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
```

- [ ] **Step 2: Syntax check**

```bash
node --check djangoexact/admin_scripts/static/admin_scripts/compare.js
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/static/admin_scripts/compare.js
git commit -m "feat(scenario-builder): ingest run-scenario results into window.scenarioResults with stale tracking"
```

---

## Task 8: Implement chip rendering in `compare.js`

**Files:**
- Modify: `djangoexact/admin_scripts/static/admin_scripts/compare.js`

- [ ] **Step 1: Add chip computation and rendering**

Open `djangoexact/admin_scripts/static/admin_scripts/compare.js`. Replace the placeholder `renderCompare()` body with the chip-rendering version (charts/table sections still empty placeholders for later tasks):

```javascript
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
        // Charts and table — added in later tasks.
    }
```

`window.switchScenarioTab` is the global function defined in `compile_scenarios.html`. The chip click handler relies on `window.htmx` (htmx 2.x exposes itself globally) for programmatic dispatch of the Run button.

- [ ] **Step 2: Syntax check**

```bash
node --check djangoexact/admin_scripts/static/admin_scripts/compare.js
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/static/admin_scripts/compare.js
git commit -m "feat(scenario-builder): render Compare tab status chips with threshold rules"
```

---

## Task 9: Implement the Mean ± CI 95% bar chart

**Files:**
- Modify: `djangoexact/admin_scripts/static/admin_scripts/compare.js`

- [ ] **Step 1: Add bar chart rendering**

Open `djangoexact/admin_scripts/static/admin_scripts/compare.js`. Inside the IIFE, just below the `tooltipText` function, add a chart-lifecycle helper:

```javascript
    var charts = {};  // key: mount id, value: Chart instance (so we can destroy on re-render)

    function destroyChart(key) {
        if (charts[key]) {
            charts[key].destroy();
            delete charts[key];
        }
    }
```

Below the `renderChips` function and before the final `renderCompare`, add:

```javascript
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
```

Update `renderCompare()` to call the new function. Replace the placeholder comment:

```javascript
    function renderCompare() {
        var indices = Object.keys(window.scenarioResults).sort(function (a, b) {
            return Number(a) - Number(b);
        });
        var empty = document.getElementById("cmp-empty");
        var hasAny = indices.length > 0;
        if (empty) empty.classList.toggle("hidden", hasAny);

        renderChips(indices);
        renderBarChart(indices);
        // Box plot, composition, table — added in later tasks.
    }
```

- [ ] **Step 2: Syntax check**

```bash
node --check djangoexact/admin_scripts/static/admin_scripts/compare.js
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/static/admin_scripts/compare.js
git commit -m "feat(scenario-builder): render mean +/- CI 95% bar chart on Compare tab"
```

---

## Task 10: Implement the box-plot row

**Files:**
- Modify: `djangoexact/admin_scripts/static/admin_scripts/compare.js`

- [ ] **Step 1: Add box-plot rendering**

Open `djangoexact/admin_scripts/static/admin_scripts/compare.js`. After `renderBarChart`, add:

```javascript
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
                items: [s.min, s.q1, s.median, s.q3, s.max],  // satisfies plugin's input shape
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
```

Update `renderCompare()` to also call the box plot:

```javascript
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
        // Composition stack and table — added in later tasks.
    }
```

- [ ] **Step 2: Syntax check**

```bash
node --check djangoexact/admin_scripts/static/admin_scripts/compare.js
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/static/admin_scripts/compare.js
git commit -m "feat(scenario-builder): render distribution box plots on Compare tab"
```

---

## Task 11: Implement the per-change composition stack

**Files:**
- Modify: `djangoexact/admin_scripts/static/admin_scripts/compare.js`

- [ ] **Step 1: Add composition stack rendering**

Open `djangoexact/admin_scripts/static/admin_scripts/compare.js`. After `renderBoxPlot`, add a small string-hash helper and the composition renderer:

```javascript
    function colorForLabel(label) {
        // FNV-like 32-bit hash, mapped into the palette.
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
```

Update `renderCompare()`:

```javascript
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
        // Table — added in next task.
    }
```

- [ ] **Step 2: Syntax check**

```bash
node --check djangoexact/admin_scripts/static/admin_scripts/compare.js
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/static/admin_scripts/compare.js
git commit -m "feat(scenario-builder): render per-change composition stack on Compare tab"
```

---

## Task 12: Implement the comparison data table

**Files:**
- Modify: `djangoexact/admin_scripts/static/admin_scripts/compare.js`

- [ ] **Step 1: Add table rendering**

Open `djangoexact/admin_scripts/static/admin_scripts/compare.js`. After `renderComposition`, add:

```javascript
    function fmt(v, places) {
        if (v === null || v === undefined) return "—";
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
```

Update `renderCompare()` one last time:

```javascript
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
```

- [ ] **Step 2: Syntax check**

```bash
node --check djangoexact/admin_scripts/static/admin_scripts/compare.js
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/static/admin_scripts/compare.js
git commit -m "feat(scenario-builder): render comparison data table on Compare tab"
```

---

## Task 13: Handle scenario removal via MutationObserver

**Files:**
- Modify: `djangoexact/admin_scripts/static/admin_scripts/compare.js`

- [ ] **Step 1: Add a MutationObserver that cleans up `window.scenarioResults`**

Open `djangoexact/admin_scripts/static/admin_scripts/compare.js`. Right after the `change` event listener (which is the last top-level statement before the `window.renderCompare = renderCompare;` assignment), add:

```javascript
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
```

- [ ] **Step 2: Syntax check**

```bash
node --check djangoexact/admin_scripts/static/admin_scripts/compare.js
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/static/admin_scripts/compare.js
git commit -m "feat(scenario-builder): clear removed scenarios from comparison state"
```

---

## Task 14: Manual QA pass on a CI / DB-equipped machine

**Files:** None (verification only).

This task does not produce code; it is the manual-QA gate the spec calls out (the sandbox cannot bootstrap Django). Run from a machine with Postgres + the Django app reachable.

- [ ] **Step 1: Bootstrap and serve**

```bash
cd djangoexact
python manage.py migrate
python manage.py load_reference_data --app=all
python manage.py runserver
```

Expected: server starts, admin scripts dashboard reachable at `http://localhost:8000/api/admin-scripts/`.

- [ ] **Step 2: Run the backend test suite**

```bash
pytest djangoexact/admin_scripts/tests/test_views.py -v
```

Expected: all tests pass, including the new `test_stats_for_scenario_*_outlier*`, `test_stats_for_scenario_per_change_*`, and `HtmxRunScenarioContextTest` tests.

- [ ] **Step 3: Smoke-check the UI**

In a logged-in staff session, open `http://localhost:8000/api/admin-scripts/compile-scenarios/`. Verify each:

- The **Compare** tab is present at the right of the tab strip.
- Clicking **Compare** with no scenarios run shows "Run at least one scenario to populate the comparison view."
- Run Scenario 1 with a Grassland change. The in-tab result is now a one-line headline (`n=… · sum=… · mean=… ± …`).
- Click **Compare**: a status chip, a single bar with error bars, a single box plot, a single composition stack, and a one-row table appear.
- Add Scenario 2, fill it, click Run. The Compare tab shows two of everything, colour-keyed to the tab indices.
- Edit a value in Scenario 1's form, switch back to Compare: S1's chip flips to amber "Stale". Click the chip → triggers Scenario 1's Run button (chip returns to green or the appropriate level).
- Remove Scenario 2 via the "Remove Scenario" button. The Compare tab updates to show only Scenario 1.
- Construct a scenario that produces a gap (e.g., uncomputed combination). The Compare tab shows a 🔴 chip and the bar/box/composition for that scenario are absent.
- Browser console is clean — no JS errors, no 404s on `static/admin_scripts/compare.js` or any Chart.js CDN.

- [ ] **Step 4: Push the branch and open a PR**

```bash
git push -u origin <feature-branch>
gh pr create --base develop --title "feat(scenario-builder): live-compiled results comparison view"
```

Expected: PR created targeting `develop`. CI runs the new tests on a Postgres-equipped runner.

---

## Self-Review Notes

**Spec coverage:** every Goal / UI / Backend / Frontend / Testing block in the spec maps to a task above:
- `stats_for_scenario` outlier counts → Task 1
- `stats_for_scenario` per-change rollup → Task 2
- `htmx_run_scenario` enriched context → Task 3
- `scenario_results.html` restructure + `scenario_panel.html` include → Task 4
- Compare tab in `compile_scenarios.html` + `compare_panel.html` → Tasks 5 + 6
- `compare.js` state ingestion + form-hash → Task 7
- Chips + thresholds → Task 8
- Charts (bar, box, composition) → Tasks 9, 10, 11
- Comparison table → Task 12
- Scenario removal cleanup → Task 13
- Manual QA → Task 14

**Sandbox honesty:** all backend tests use `python -m py_compile` as the local gate; the actual Django test run happens in Task 14 on a DB-equipped machine. The plan does not claim local test runs verify behaviour.

**Type/name consistency:** `stats_for_scenario` returns keys `outliers_low`, `outliers_high`, `per_change` throughout. `per_change` entries always have `label`, `module_type`, `field`, `from_value`, `to_value`, `unit`, `count`, `sum`, `mean`. `window.scenarioResults[idx]` always has `{ result, formHash, runAt, stale }`. `result.statistics` always exists (empty stats shape on zero / gap responses). `window.renderCompare` and `window.switchScenarioTab` are the only globals introduced. Chart mount IDs (`cmp-bar`, `cmp-box`, `cmp-composition`, `cmp-table`, `cmp-chips`, `cmp-empty`) appear identically in template and JS.
