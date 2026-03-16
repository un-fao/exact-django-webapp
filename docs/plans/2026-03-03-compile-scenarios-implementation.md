# Compile Scenarios UI — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dynamic scenario builder to the admin_scripts app that lets staff users create emission scenarios via htmx-powered forms, run them against ChangeRecord data, and view computed statistics.

**Architecture:** Django views + htmx for cascading dropdowns and dynamic form management. Utility functions extracted from `scripts/minitool__compile_scenarios.py`. All endpoints staff-only under `/api/admin-scripts/compile-scenarios/`.

**Tech Stack:** Django 4.x, htmx (CDN), Tailwind CSS (CDN), pandas + openpyxl (for Excel export)

**Design doc:** `docs/plans/2026-03-03-compile-scenarios-ui-design.md`

---

### Task 1: Extract utility functions into scenario_utils.py

**Files:**
- Create: `djangoexact/admin_scripts/scenario_utils.py`
- Reference: `djangoexact/scripts/minitool__compile_scenarios.py:67-143` (stats_for) and `:666-761` (Q-building)
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing tests for stats_for**

Add a new test class to `djangoexact/admin_scripts/tests.py`:

```python
from minitool.models import ChangeRecord


@override_settings(MIDDLEWARE=MIDDLEWARE_WITHOUT_DB_CLEANUP)
class ScenarioUtilsTest(TestCase):
    def setUp(self):
        # Create test ChangeRecord data
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
            )

    def test_stats_for_returns_all_keys(self):
        from admin_scripts.scenario_utils import stats_for
        qs = ChangeRecord.objects.all()
        result = stats_for(qs)
        expected_keys = {"count", "sum_total", "mean", "median", "min", "max", "std", "q1", "q3", "iqr", "ci_95", "ci_99"}
        self.assertEqual(set(result.keys()), expected_keys)

    def test_stats_for_correct_count_and_mean(self):
        from admin_scripts.scenario_utils import stats_for
        qs = ChangeRecord.objects.all()
        result = stats_for(qs)
        self.assertEqual(result["count"], 5)
        self.assertAlmostEqual(result["mean"], -2.0, places=5)
        self.assertAlmostEqual(result["median"], -2.0, places=5)

    def test_stats_for_empty_queryset(self):
        from admin_scripts.scenario_utils import stats_for
        qs = ChangeRecord.objects.none()
        result = stats_for(qs)
        self.assertEqual(result["count"], 0)
        self.assertIsNone(result["mean"])
        self.assertIsNone(result["std"])
```

**Step 2: Run tests to verify they fail**

Run: `pytest djangoexact/admin_scripts/tests.py::ScenarioUtilsTest -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'admin_scripts.scenario_utils'`

**Step 3: Create scenario_utils.py with stats_for**

Create `djangoexact/admin_scripts/scenario_utils.py`:

```python
import statistics as stats_module

from django.db.models import Avg, Count, Max, Min, Q, Sum

from minitool.models import ChangeRecord


def stats_for(qs):
    """Compute descriptive statistics for a ChangeRecord queryset's 'total' field."""
    agg = qs.aggregate(
        n=Count("id"),
        s=Sum("total"),
        mean=Avg("total"),
        minv=Min("total"),
        maxv=Max("total"),
    )
    n, s = agg["n"] or 0, agg["s"] or 0.0
    mean = agg["mean"] if n else None

    if n > 0:
        total_values = list(qs.values_list("total", flat=True))
        ss = sum(x * x for x in total_values)

        if n > 1:
            var = (ss - (s * s) / n) / (n - 1)
            std = var**0.5
            se = std / (n**0.5)
            ci95 = 1.96 * se
            ci99 = 2.58 * se
        else:
            std = se = ci95 = ci99 = None

        sorted_values = sorted(total_values)

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
    else:
        std = se = ci95 = ci99 = None
        q1 = median = q3 = None

    iqr = (q3 - q1) if (q1 is not None and q3 is not None) else None

    return {
        "count": n,
        "sum_total": s,
        "mean": mean,
        "median": median,
        "min": agg["minv"],
        "max": agg["maxv"],
        "std": std,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "ci_95": ci95,
        "ci_99": ci99,
    }
```

**Step 4: Run tests to verify stats_for passes**

Run: `pytest djangoexact/admin_scripts/tests.py::ScenarioUtilsTest -v`
Expected: 3 PASSED

**Step 5: Write failing tests for build_scenario_query**

Add to the `ScenarioUtilsTest` class:

```python
    def test_build_scenario_query_basic(self):
        from admin_scripts.scenario_utils import build_scenario_query
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
        }]
        q = build_scenario_query(changes, {})
        results = ChangeRecord.objects.filter(q)
        self.assertEqual(results.count(), 5)

    def test_build_scenario_query_with_soil_filter(self):
        from admin_scripts.scenario_utils import build_scenario_query
        changes = [{
            "module_type": "Grassland",
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
        }]
        global_filters = {"soil_type": ["Sandy"]}
        q = build_scenario_query(changes, global_filters)
        results = ChangeRecord.objects.filter(q)
        self.assertEqual(results.count(), 0)  # Our test data uses "High Activity Clay"

    def test_build_scenario_query_multiple_changes(self):
        from admin_scripts.scenario_utils import build_scenario_query
        # Add a second type of record
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
                "module_type": "Grassland",
                "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
                "end": {"field": "grassland_management_type", "value": "Improved Grassland"},
            },
            {
                "module_type": "Annual Cropland",
                "start": {"field": "organic_input_type", "value": "Low C input"},
                "end": {"field": "organic_input_type", "value": "High C input"},
            },
        ]
        q = build_scenario_query(changes, {})
        results = ChangeRecord.objects.filter(q)
        self.assertEqual(results.count(), 6)  # 5 Grassland + 1 Cropland
```

**Step 6: Run tests to verify they fail**

Run: `pytest djangoexact/admin_scripts/tests.py::ScenarioUtilsTest::test_build_scenario_query_basic -v`
Expected: FAIL — `ImportError: cannot import name 'build_scenario_query'`

**Step 7: Implement build_scenario_query**

Add to `djangoexact/admin_scripts/scenario_utils.py`:

```python
def _create_flexible_value_query(field_name, value):
    """Handle numeric values that may be stored as int or float strings."""
    try:
        float_val = float(value)
        if float_val.is_integer():
            return Q(**{field_name: str(int(float_val))}) | Q(**{field_name: str(float_val)})
        else:
            return Q(**{field_name: str(float_val)})
    except (ValueError, TypeError):
        return Q(**{field_name: str(value)})


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
        module_type = change.get("module_type")
        if not module_type:
            continue

        change_filters = {**global_filters, **change.get("filters", {})}
        csv_row_filters = change.get("csv_row_filters", {})

        change_q = (
            Q(module_type=module_type, field=change["start"]["field"])
            & _create_flexible_value_query("from_value", change["start"]["value"])
            & _create_flexible_value_query("to_value", change["end"]["value"])
        )

        # Standard column filters
        for col in ("region", "climate", "moisture", "soil_type"):
            if change_filters.get(col):
                values = change_filters[col] if isinstance(change_filters[col], list) else [change_filters[col]]
                col_q = Q()
                for val in values:
                    col_q |= Q(**{col: val})
                change_q &= col_q

        # Custom filters (non-standard columns)
        for filter_key, filter_value in change_filters.items():
            if filter_key in ("region", "climate", "moisture", "soil_type"):
                continue
            filter_values = filter_value if isinstance(filter_value, list) else [filter_value]
            filter_q = Q()
            for val in filter_values:
                filter_q |= Q(**{f"csv_row_data__{filter_key}": val}) | Q(**{f"custom_filters__{filter_key}": val})
            change_q &= filter_q

        # CSV row data filters
        for filter_key, filter_value in csv_row_filters.items():
            if filter_key in ("module_start_type", "module_w_type"):
                continue
            filter_values = filter_value if isinstance(filter_value, list) else [filter_value]
            csv_filter_q = Q()
            for val in filter_values:
                csv_filter_q |= Q(**{f"csv_row_data__{filter_key}": val})
            change_q &= csv_filter_q

        q_objects |= change_q

    return q_objects
```

**Step 8: Run all utility tests**

Run: `pytest djangoexact/admin_scripts/tests.py::ScenarioUtilsTest -v`
Expected: 6 PASSED

**Step 9: Commit**

```bash
git add djangoexact/admin_scripts/scenario_utils.py djangoexact/admin_scripts/tests.py
git commit -m "feat(admin-scripts): add scenario_utils with stats_for and build_scenario_query"
```

---

### Task 2: Add htmx to base template and register the script

**Files:**
- Modify: `djangoexact/admin_scripts/templates/admin_scripts/base.html:7` (add htmx CDN)
- Modify: `djangoexact/admin_scripts/views.py:18-24` (add to SCRIPTS list)
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing test**

Add to `AdminScriptsAccessTest` in `djangoexact/admin_scripts/tests.py`:

```python
    def test_dashboard_shows_compile_scenarios(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/")
        self.assertContains(response, "Compile Scenarios")
```

**Step 2: Run test to verify it fails**

Run: `pytest djangoexact/admin_scripts/tests.py::AdminScriptsAccessTest::test_dashboard_shows_compile_scenarios -v`
Expected: FAIL — "Compile Scenarios" not found in response

**Step 3: Add htmx to base.html**

In `djangoexact/admin_scripts/templates/admin_scripts/base.html`, after line 7 (the Tailwind CDN script), add:

```html
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
```

**Step 4: Add compile-scenarios to SCRIPTS list**

In `djangoexact/admin_scripts/views.py`, add a new entry to the SCRIPTS list (after line 23):

```python
    {
        "name": "Compile Scenarios",
        "url": "compile-scenarios",
        "description": "Build custom emission scenarios and compute statistics from ChangeRecord data.",
    },
```

**Step 5: Run test to verify it passes**

Run: `pytest djangoexact/admin_scripts/tests.py::AdminScriptsAccessTest::test_dashboard_shows_compile_scenarios -v`
Expected: PASS

**Step 6: Commit**

```bash
git add djangoexact/admin_scripts/templates/admin_scripts/base.html djangoexact/admin_scripts/views.py
git commit -m "feat(admin-scripts): add htmx CDN and register compile-scenarios script"
```

---

### Task 3: Create main compile-scenarios view (GET) and form template

**Files:**
- Modify: `djangoexact/admin_scripts/views.py` (add compile_scenarios view)
- Modify: `djangoexact/admin_scripts/urls.py` (add URL patterns)
- Create: `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html`
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing test**

Add a new test class to `djangoexact/admin_scripts/tests.py`:

```python
@override_settings(MIDDLEWARE=MIDDLEWARE_WITHOUT_DB_CLEANUP)
class CompileScenariosViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = CustomUser.objects.create_user(
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
            firebase_uid="staff_uid",
        )

    def test_compile_scenarios_get_returns_form(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/compile-scenarios/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compile Scenarios")
        self.assertContains(response, "Scenario Name")
        self.assertContains(response, "Add Another Change")
        self.assertContains(response, "Run Scenario")

    def test_compile_scenarios_requires_staff(self):
        response = self.client.get("/api/admin-scripts/compile-scenarios/")
        self.assertEqual(response.status_code, 302)
```

**Step 2: Run test to verify it fails**

Run: `pytest djangoexact/admin_scripts/tests.py::CompileScenariosViewTest -v`
Expected: FAIL — 404

**Step 3: Add the view to views.py**

Add to `djangoexact/admin_scripts/views.py`:

```python
from minitool.models import ChangeRecord


@login_required(login_url="/admin/login/")
@staff_required
def compile_scenarios(request):
    if request.method == "POST":
        # Handled in Task 5
        pass

    # GET: load module types for the first change fieldset
    module_types = list(
        ChangeRecord.objects.values_list("module_type", flat=True)
        .distinct()
        .order_by("module_type")
    )
    return render(request, "admin_scripts/scripts/compile_scenarios.html", {
        "module_types": module_types,
    })
```

**Step 4: Add URL patterns to urls.py**

In `djangoexact/admin_scripts/urls.py`, add:

```python
from django.urls import path, include

# Inside urlpatterns:
    path("compile-scenarios/", views.compile_scenarios, name="compile-scenarios"),
```

**Step 5: Create the form template**

Create `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html`:

```html
{% extends "admin_scripts/base.html" %}

{% block title %}Compile Scenarios — Admin Scripts{% endblock %}

{% block content %}
<a href="{% url 'admin_scripts:dashboard' %}" class="text-sm text-blue-600 hover:text-blue-800 mb-4 inline-block">← Back to Dashboard</a>

<h1 class="text-2xl font-bold text-gray-900 mb-2">Compile Scenarios</h1>
<p class="text-sm text-gray-500 mb-6">Build custom emission scenarios and compute statistics from ChangeRecord data.</p>

<form method="post" id="scenario-form">
    {% csrf_token %}

    <div class="bg-white border border-gray-200 rounded-lg p-5 mb-4">
        <div class="grid grid-cols-2 gap-4 mb-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Scenario Name</label>
                <input type="text" name="scenario_name" required
                       class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                       placeholder="e.g. Custom Grassland Improvement">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <input type="text" name="category"
                       class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                       placeholder="e.g. Soil and Land Restoration">
            </div>
        </div>
    </div>

    <div id="changes-container">
        {% include "admin_scripts/partials/change_fieldset.html" with index=0 module_types=module_types %}
    </div>

    <button type="button"
            hx-get="{% url 'admin_scripts:htmx-add-change' %}"
            hx-target="#changes-container"
            hx-swap="beforeend"
            hx-vals='js:{"index": document.querySelectorAll("[data-change-index]").length}'
            class="mt-2 mb-6 text-sm text-blue-600 hover:text-blue-800 font-medium">
        + Add Another Change
    </button>

    <details class="bg-white border border-gray-200 rounded-lg p-5 mb-6">
        <summary class="text-sm font-medium text-gray-700 cursor-pointer">Global Filters (applied to all changes)</summary>
        <div class="mt-3 grid grid-cols-2 gap-4">
            <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">Soil Type</label>
                <select name="global_filter_soil_type" multiple
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm" size="3">
                    <option value="High Activity Clay" selected>High Activity Clay</option>
                    <option value="Low Activity Clay" selected>Low Activity Clay</option>
                    <option value="Sandy" selected>Sandy</option>
                </select>
            </div>
            <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">Region</label>
                <select name="global_filter_region" multiple
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm" size="3">
                </select>
                <p class="text-xs text-gray-400 mt-1">Leave empty for all regions</p>
            </div>
        </div>
    </details>

    <button type="submit"
            class="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 text-sm font-medium">
        Run Scenario
    </button>
</form>

{% if statistics %}
<div class="mt-8 bg-white border border-gray-200 rounded-lg p-5">
    <h2 class="text-lg font-semibold text-gray-900 mb-4">Results</h2>

    {% if statistics.count == 0 %}
    <p class="text-gray-500">No matching records found for this scenario.</p>
    {% else %}
    <div class="grid grid-cols-3 gap-4 text-sm">
        <div><span class="text-gray-500">Count:</span> <span class="font-medium">{{ statistics.count }}</span></div>
        <div><span class="text-gray-500">Mean:</span> <span class="font-medium">{{ statistics.mean|floatformat:4 }}</span></div>
        <div><span class="text-gray-500">Median:</span> <span class="font-medium">{{ statistics.median|floatformat:4 }}</span></div>
        <div><span class="text-gray-500">Std Dev:</span> <span class="font-medium">{{ statistics.std|floatformat:4 }}</span></div>
        <div><span class="text-gray-500">Min:</span> <span class="font-medium">{{ statistics.min|floatformat:4 }}</span></div>
        <div><span class="text-gray-500">Max:</span> <span class="font-medium">{{ statistics.max|floatformat:4 }}</span></div>
        <div><span class="text-gray-500">Q1:</span> <span class="font-medium">{{ statistics.q1|floatformat:4 }}</span></div>
        <div><span class="text-gray-500">Q3:</span> <span class="font-medium">{{ statistics.q3|floatformat:4 }}</span></div>
        <div><span class="text-gray-500">IQR:</span> <span class="font-medium">{{ statistics.iqr|floatformat:4 }}</span></div>
        <div><span class="text-gray-500">CI 95%:</span> <span class="font-medium">{{ statistics.ci_95|floatformat:4 }}</span></div>
        <div><span class="text-gray-500">CI 99%:</span> <span class="font-medium">{{ statistics.ci_99|floatformat:4 }}</span></div>
        <div><span class="text-gray-500">Sum Total:</span> <span class="font-medium">{{ statistics.sum_total|floatformat:4 }}</span></div>
    </div>

    {% if distribution %}
    <div class="mt-4 p-3 rounded {{ distribution_class }}">
        <p class="text-sm font-medium">Distribution: {{ distribution }}</p>
        <p class="text-sm">Range: {{ range_lower|floatformat:4 }} to {{ range_upper|floatformat:4 }}</p>
    </div>
    {% endif %}
    {% endif %}
</div>
{% endif %}

{% if error %}
<div class="mt-4 bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
    {{ error }}
</div>
{% endif %}
{% endblock %}
```

**Step 6: Create the change fieldset partial**

Create directory `djangoexact/admin_scripts/templates/admin_scripts/partials/` then create `change_fieldset.html`:

```html
<div data-change-index="{{ index }}" class="bg-white border border-gray-200 rounded-lg p-5 mb-3 relative">
    <div class="flex justify-between items-center mb-3">
        <h3 class="text-sm font-semibold text-gray-700">Change #{{ index|add:1 }}</h3>
        {% if index > 0 %}
        <button type="button" onclick="this.closest('[data-change-index]').remove()"
                class="text-gray-400 hover:text-red-500 text-lg leading-none">&times;</button>
        {% endif %}
    </div>

    <div class="grid grid-cols-2 gap-4">
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Module Type</label>
            <select name="change-{{ index }}-module_type" required
                    hx-get="{% url 'admin_scripts:htmx-fields' %}"
                    hx-target="#change-{{ index }}-field-container"
                    hx-include="this"
                    hx-trigger="change"
                    class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
                <option value="">Select module type...</option>
                {% for mt in module_types %}
                <option value="{{ mt }}">{{ mt }}</option>
                {% endfor %}
            </select>
        </div>

        <div id="change-{{ index }}-field-container">
            <label class="block text-xs font-medium text-gray-500 mb-1">Field</label>
            <select name="change-{{ index }}-field" required disabled
                    class="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-gray-50">
                <option value="">Select module type first...</option>
            </select>
        </div>
    </div>

    <div id="change-{{ index }}-values-container" class="grid grid-cols-2 gap-4 mt-3">
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">From Value</label>
            <select name="change-{{ index }}-from_value" required disabled
                    class="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-gray-50">
                <option value="">Select field first...</option>
            </select>
        </div>
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">To Value</label>
            <select name="change-{{ index }}-to_value" required disabled
                    class="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-gray-50">
                <option value="">Select field first...</option>
            </select>
        </div>
    </div>

    <details class="mt-3">
        <summary class="text-xs font-medium text-gray-500 cursor-pointer">Change-level Filters</summary>
        <div id="change-{{ index }}-filters-container" class="mt-2 grid grid-cols-2 gap-3">
            <div>
                <label class="block text-xs text-gray-400 mb-1">Region</label>
                <select name="change-{{ index }}-filter-region" multiple
                        class="w-full border border-gray-300 rounded px-2 py-1 text-xs" size="2">
                </select>
            </div>
            <div>
                <label class="block text-xs text-gray-400 mb-1">Climate</label>
                <select name="change-{{ index }}-filter-climate" multiple
                        class="w-full border border-gray-300 rounded px-2 py-1 text-xs" size="2">
                </select>
            </div>
        </div>
    </details>
</div>
```

**Step 7: Run tests to verify they pass**

Run: `pytest djangoexact/admin_scripts/tests.py::CompileScenariosViewTest -v`
Expected: 2 PASSED

**Step 8: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/urls.py \
       djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html \
       djangoexact/admin_scripts/templates/admin_scripts/partials/change_fieldset.html
git commit -m "feat(admin-scripts): add compile-scenarios form view and templates"
```

---

### Task 4: Create htmx partial endpoints

**Files:**
- Modify: `djangoexact/admin_scripts/views.py` (add htmx views)
- Modify: `djangoexact/admin_scripts/urls.py` (add htmx URL patterns)
- Create: `djangoexact/admin_scripts/templates/admin_scripts/partials/field_options.html`
- Create: `djangoexact/admin_scripts/templates/admin_scripts/partials/value_options.html`
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing tests for htmx endpoints**

Add to `CompileScenariosViewTest` in `djangoexact/admin_scripts/tests.py`:

```python
    def setUp(self):
        # ...existing setUp...
        # Add ChangeRecord test data for htmx endpoints
        ChangeRecord.objects.create(
            module_type="Grassland", region="Central Asia", climate="Cool Temperate",
            moisture="Moist", soil_type="High Activity Clay", total=-2.0,
            field="grassland_management_type", from_value="Non-Degraded", to_value="Improved Grassland",
        )
        ChangeRecord.objects.create(
            module_type="Grassland", region="Eastern Europe", climate="Warm Temperate",
            moisture="Dry", soil_type="Sandy", total=-1.5,
            field="grassland_management_type", from_value="High Intensity Grazing", to_value="Non-Degraded",
        )
        ChangeRecord.objects.create(
            module_type="Annual Cropland", region="Central Asia", climate="Cool Temperate",
            moisture="Moist", soil_type="High Activity Clay", total=-0.5,
            field="organic_input_type", from_value="Low C input", to_value="High C input",
        )

    def test_htmx_module_types(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/compile-scenarios/htmx/module-types/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Grassland")
        self.assertContains(response, "Annual Cropland")

    def test_htmx_fields(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get(
            "/api/admin-scripts/compile-scenarios/htmx/fields/",
            {"change-0-module_type": "Grassland"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "grassland_management_type")

    def test_htmx_values(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get(
            "/api/admin-scripts/compile-scenarios/htmx/values/",
            {"module_type": "Grassland", "field": "grassland_management_type", "index": "0"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Non-Degraded")
        self.assertContains(response, "Improved Grassland")

    def test_htmx_add_change(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get(
            "/api/admin-scripts/compile-scenarios/htmx/add-change/",
            {"index": "1"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Change #2")
        self.assertContains(response, "change-1-module_type")
```

**Step 2: Run tests to verify they fail**

Run: `pytest djangoexact/admin_scripts/tests.py::CompileScenariosViewTest::test_htmx_module_types -v`
Expected: FAIL — 404

**Step 3: Implement htmx views**

Add to `djangoexact/admin_scripts/views.py`:

```python
from django.http import HttpResponseForbidden, HttpResponse


@login_required(login_url="/admin/login/")
@staff_required
def htmx_module_types(request):
    module_types = list(
        ChangeRecord.objects.values_list("module_type", flat=True)
        .distinct()
        .order_by("module_type")
    )
    options = ['<option value="">Select module type...</option>']
    for mt in module_types:
        options.append(f'<option value="{mt}">{mt}</option>')
    return HttpResponse("\n".join(options))


@login_required(login_url="/admin/login/")
@staff_required
def htmx_fields(request):
    # Find the module_type param from any change-N-module_type key
    module_type = None
    for key, value in request.GET.items():
        if key.startswith("change-") and key.endswith("-module_type") and value:
            module_type = value
            break

    if not module_type:
        return HttpResponse('<select disabled><option>Select module type first...</option></select>')

    # Extract the change index from the key
    index = key.split("-")[1] if key else "0"

    fields = list(
        ChangeRecord.objects.filter(module_type=module_type)
        .values_list("field", flat=True)
        .distinct()
        .order_by("field")
    )
    html = f'''<label class="block text-xs font-medium text-gray-500 mb-1">Field</label>
<select name="change-{index}-field" required
        hx-get="{{% url 'admin_scripts:htmx-values' %}}"
        hx-target="#change-{index}-values-container"
        hx-include="[name='change-{index}-module_type']"
        hx-vals='{{"index": "{index}"}}'
        hx-trigger="change"
        class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
    <option value="">Select field...</option>'''
    for f in fields:
        html += f'\n    <option value="{f}">{f}</option>'
    html += '\n</select>'
    return HttpResponse(html)


@login_required(login_url="/admin/login/")
@staff_required
def htmx_values(request):
    module_type = request.GET.get("module_type")
    # Also check for change-N-module_type pattern
    if not module_type:
        for key, value in request.GET.items():
            if key.startswith("change-") and key.endswith("-module_type") and value:
                module_type = value
                break

    field = request.GET.get("field")
    # Also check for change-N-field pattern
    if not field:
        for key, value in request.GET.items():
            if key.startswith("change-") and key.endswith("-field") and value:
                field = value
                break

    index = request.GET.get("index", "0")

    if not module_type or not field:
        return HttpResponse("<p class='text-xs text-gray-400'>Select module type and field first</p>")

    from_values = list(
        ChangeRecord.objects.filter(module_type=module_type, field=field)
        .values_list("from_value", flat=True)
        .distinct()
        .order_by("from_value")
    )
    to_values = list(
        ChangeRecord.objects.filter(module_type=module_type, field=field)
        .values_list("to_value", flat=True)
        .distinct()
        .order_by("to_value")
    )

    return render(request, "admin_scripts/partials/value_options.html", {
        "index": index,
        "from_values": from_values,
        "to_values": to_values,
    })


@login_required(login_url="/admin/login/")
@staff_required
def htmx_add_change(request):
    index = int(request.GET.get("index", 1))
    module_types = list(
        ChangeRecord.objects.values_list("module_type", flat=True)
        .distinct()
        .order_by("module_type")
    )
    return render(request, "admin_scripts/partials/change_fieldset.html", {
        "index": index,
        "module_types": module_types,
    })
```

**Step 4: Add URL patterns**

In `djangoexact/admin_scripts/urls.py`, add inside `urlpatterns`:

```python
    path("compile-scenarios/htmx/module-types/", views.htmx_module_types, name="htmx-module-types"),
    path("compile-scenarios/htmx/fields/", views.htmx_fields, name="htmx-fields"),
    path("compile-scenarios/htmx/values/", views.htmx_values, name="htmx-values"),
    path("compile-scenarios/htmx/add-change/", views.htmx_add_change, name="htmx-add-change"),
```

**Step 5: Create value_options.html partial**

Create `djangoexact/admin_scripts/templates/admin_scripts/partials/value_options.html`:

```html
<div>
    <label class="block text-xs font-medium text-gray-500 mb-1">From Value</label>
    <select name="change-{{ index }}-from_value" required
            class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
        <option value="">Select from value...</option>
        {% for val in from_values %}
        <option value="{{ val }}">{{ val }}</option>
        {% endfor %}
    </select>
</div>
<div>
    <label class="block text-xs font-medium text-gray-500 mb-1">To Value</label>
    <select name="change-{{ index }}-to_value" required
            class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
        <option value="">Select to value...</option>
        {% for val in to_values %}
        <option value="{{ val }}">{{ val }}</option>
        {% endfor %}
    </select>
</div>
```

**Step 6: Fix htmx_fields to not use template tags in Python string**

Note: The `htmx_fields` view constructs HTML in Python. The `{% url %}` tag won't work there. Instead, use `django.urls.reverse`:

```python
from django.urls import reverse

# In htmx_fields, replace the template tag with:
values_url = reverse("admin_scripts:htmx-values")
# And use f-string: hx-get="{values_url}"
```

**Step 7: Run all htmx tests**

Run: `pytest djangoexact/admin_scripts/tests.py::CompileScenariosViewTest -v`
Expected: ALL PASSED

**Step 8: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/urls.py \
       djangoexact/admin_scripts/templates/admin_scripts/partials/value_options.html \
       djangoexact/admin_scripts/tests.py
git commit -m "feat(admin-scripts): add htmx partial endpoints for cascading dropdowns"
```

---

### Task 5: Implement form POST processing (compute and display statistics)

**Files:**
- Modify: `djangoexact/admin_scripts/views.py` (complete POST handler in compile_scenarios)
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing tests for POST**

Add to `CompileScenariosViewTest`:

```python
    def test_compile_scenarios_post_returns_statistics(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/compile-scenarios/", {
            "scenario_name": "Test Scenario",
            "category": "Test Category",
            "change-0-module_type": "Grassland",
            "change-0-field": "grassland_management_type",
            "change-0-from_value": "Non-Degraded",
            "change-0-to_value": "Improved Grassland",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Results")
        self.assertContains(response, "Count")

    def test_compile_scenarios_post_no_matching_records(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/compile-scenarios/", {
            "scenario_name": "Empty Scenario",
            "category": "Test",
            "change-0-module_type": "Nonexistent",
            "change-0-field": "fake_field",
            "change-0-from_value": "A",
            "change-0-to_value": "B",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No matching records")

    def test_compile_scenarios_post_with_global_filters(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/compile-scenarios/", {
            "scenario_name": "Filtered Scenario",
            "category": "Test",
            "change-0-module_type": "Grassland",
            "change-0-field": "grassland_management_type",
            "change-0-from_value": "Non-Degraded",
            "change-0-to_value": "Improved Grassland",
            "global_filter_soil_type": ["Sandy"],
        })
        self.assertEqual(response.status_code, 200)
        # Only 1 record matches Sandy soil
        # (check that results section is present)
        self.assertContains(response, "Results")

    def test_compile_scenarios_post_multiple_changes(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/compile-scenarios/", {
            "scenario_name": "Multi-Change",
            "category": "Test",
            "change-0-module_type": "Grassland",
            "change-0-field": "grassland_management_type",
            "change-0-from_value": "Non-Degraded",
            "change-0-to_value": "Improved Grassland",
            "change-1-module_type": "Annual Cropland",
            "change-1-field": "organic_input_type",
            "change-1-from_value": "Low C input",
            "change-1-to_value": "High C input",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Results")
```

**Step 2: Run tests to verify they fail**

Run: `pytest djangoexact/admin_scripts/tests.py::CompileScenariosViewTest::test_compile_scenarios_post_returns_statistics -v`
Expected: FAIL — no "Results" in response (POST handler is a pass)

**Step 3: Implement the POST handler**

Add a helper function and update `compile_scenarios` in `djangoexact/admin_scripts/views.py`:

```python
from admin_scripts.scenario_utils import stats_for, build_scenario_query


def _parse_changes_from_post(post_data):
    """Parse indexed change fields from POST data into a list of change dicts."""
    changes = []
    index = 0
    while True:
        module_type = post_data.get(f"change-{index}-module_type")
        if module_type is None:
            break
        if module_type:  # skip empty entries
            change = {
                "module_type": module_type,
                "start": {
                    "field": post_data.get(f"change-{index}-field", ""),
                    "value": post_data.get(f"change-{index}-from_value", ""),
                },
                "end": {
                    "field": post_data.get(f"change-{index}-field", ""),
                    "value": post_data.get(f"change-{index}-to_value", ""),
                },
                "filters": {},
            }
            # Change-level filters
            region = post_data.getlist(f"change-{index}-filter-region")
            if region:
                change["filters"]["region"] = region
            climate = post_data.getlist(f"change-{index}-filter-climate")
            if climate:
                change["filters"]["climate"] = climate

            changes.append(change)
        index += 1
    return changes


def _parse_global_filters(post_data):
    """Parse global filter fields from POST data."""
    filters = {}
    soil_type = post_data.getlist("global_filter_soil_type")
    if soil_type:
        filters["soil_type"] = soil_type
    region = post_data.getlist("global_filter_region")
    if region:
        filters["region"] = region
    return filters
```

Update the `compile_scenarios` view's POST branch:

```python
@login_required(login_url="/admin/login/")
@staff_required
def compile_scenarios(request):
    module_types = list(
        ChangeRecord.objects.values_list("module_type", flat=True)
        .distinct()
        .order_by("module_type")
    )
    context = {"module_types": module_types}

    if request.method == "POST":
        changes = _parse_changes_from_post(request.POST)
        global_filters = _parse_global_filters(request.POST)

        if not changes:
            context["error"] = "Please add at least one change."
        else:
            q_objects = build_scenario_query(changes, global_filters)
            aggregates = ChangeRecord.objects.filter(q_objects)
            statistics = stats_for(aggregates)
            context["statistics"] = statistics

            # Determine distribution type
            if statistics["count"] > 1 and statistics["std"] and statistics["mean"] is not None and statistics["median"] is not None:
                mean_minus_median = abs(statistics["mean"] - statistics["median"])
                if mean_minus_median < 0.25 * statistics["std"]:
                    context["distribution"] = "Symmetric"
                    context["distribution_class"] = "bg-blue-50 text-blue-800"
                    context["range_lower"] = statistics["mean"] - statistics["std"]
                    context["range_upper"] = statistics["mean"] + statistics["std"]
                else:
                    context["distribution"] = "Skewed"
                    context["distribution_class"] = "bg-amber-50 text-amber-800"
                    context["range_lower"] = statistics["q1"]
                    context["range_upper"] = statistics["q3"]

        # Preserve form inputs
        context["scenario_name"] = request.POST.get("scenario_name", "")
        context["category"] = request.POST.get("category", "")
        context["changes"] = changes

    return render(request, "admin_scripts/scripts/compile_scenarios.html", context)
```

**Step 4: Run tests**

Run: `pytest djangoexact/admin_scripts/tests.py::CompileScenariosViewTest -v`
Expected: ALL PASSED

**Step 5: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/tests.py
git commit -m "feat(admin-scripts): implement compile-scenarios POST with statistics computation"
```

---

### Task 6: Add Excel export endpoint

**Files:**
- Modify: `djangoexact/admin_scripts/views.py` (add export view)
- Modify: `djangoexact/admin_scripts/urls.py` (add export URL)
- Modify: `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html` (add export button)
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing test**

Add to `CompileScenariosViewTest`:

```python
    def test_export_to_excel(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/compile-scenarios/export/", {
            "scenario_name": "Test Export",
            "category": "Test",
            "change-0-module_type": "Grassland",
            "change-0-field": "grassland_management_type",
            "change-0-from_value": "Non-Degraded",
            "change-0-to_value": "Improved Grassland",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
```

**Step 2: Run test to verify it fails**

Run: `pytest djangoexact/admin_scripts/tests.py::CompileScenariosViewTest::test_export_to_excel -v`
Expected: FAIL — 404

**Step 3: Implement export view**

Add to `djangoexact/admin_scripts/views.py`:

```python
import io
import pandas as pd
from django.http import FileResponse
from datetime import datetime


@login_required(login_url="/admin/login/")
@staff_required
def compile_scenarios_export(request):
    if request.method != "POST":
        return HttpResponse("POST required", status=405)

    changes = _parse_changes_from_post(request.POST)
    global_filters = _parse_global_filters(request.POST)

    if not changes:
        return HttpResponse("No changes provided", status=400)

    q_objects = build_scenario_query(changes, global_filters)
    aggregates = ChangeRecord.objects.filter(q_objects)
    statistics = stats_for(aggregates)

    scenario_name = request.POST.get("scenario_name", "Custom Scenario")
    category = request.POST.get("category", "")

    # Determine distribution
    distribution_type = ""
    range_lower = range_upper = None
    if statistics["count"] > 1 and statistics["std"] and statistics["mean"] is not None and statistics["median"] is not None:
        mean_minus_median = abs(statistics["mean"] - statistics["median"])
        if mean_minus_median < 0.25 * statistics["std"]:
            distribution_type = "Symmetric"
            range_lower = statistics["mean"] - statistics["std"]
            range_upper = statistics["mean"] + statistics["std"]
        else:
            distribution_type = "Skewed"
            range_lower = statistics["q1"]
            range_upper = statistics["q3"]

    # Build Excel file in memory
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_data = [{
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
            "Distribution": distribution_type,
            "Range Lower": range_lower,
            "Range Upper": range_upper,
        }]
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)

        # Changes detail sheet
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
            pd.DataFrame(changes_data).to_excel(writer, sheet_name="Changes", index=False)

    buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scenario_{timestamp}.xlsx"

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

**Step 4: Add URL pattern**

In `djangoexact/admin_scripts/urls.py`:

```python
    path("compile-scenarios/export/", views.compile_scenarios_export, name="compile-scenarios-export"),
```

**Step 5: Add export button to template**

In `compile_scenarios.html`, inside the `{% if statistics.count %}` block (after the stats grid), add:

```html
    <form method="post" action="{% url 'admin_scripts:compile-scenarios-export' %}" class="mt-4">
        {% csrf_token %}
        <!-- Re-submit all the scenario data as hidden fields -->
        <input type="hidden" name="scenario_name" value="{{ scenario_name }}">
        <input type="hidden" name="category" value="{{ category }}">
        {% for change in changes %}
        <input type="hidden" name="change-{{ forloop.counter0 }}-module_type" value="{{ change.module_type }}">
        <input type="hidden" name="change-{{ forloop.counter0 }}-field" value="{{ change.start.field }}">
        <input type="hidden" name="change-{{ forloop.counter0 }}-from_value" value="{{ change.start.value }}">
        <input type="hidden" name="change-{{ forloop.counter0 }}-to_value" value="{{ change.end.value }}">
        {% endfor %}
        <button type="submit"
                class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 text-sm font-medium">
            Export to Excel
        </button>
    </form>
```

**Step 6: Run tests**

Run: `pytest djangoexact/admin_scripts/tests.py::CompileScenariosViewTest -v`
Expected: ALL PASSED

**Step 7: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/urls.py \
       djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html \
       djangoexact/admin_scripts/tests.py
git commit -m "feat(admin-scripts): add Excel export for compile-scenarios results"
```

---

### Task 7: Final integration tests and cleanup

**Files:**
- Modify: `djangoexact/admin_scripts/tests.py` (add edge case tests)

**Step 1: Write integration and edge case tests**

Add to `CompileScenariosViewTest`:

```python
    def test_compile_scenarios_post_missing_required_fields(self):
        """POST with no changes should show error."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/compile-scenarios/", {
            "scenario_name": "Empty",
            "category": "Test",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "at least one change")

    def test_htmx_fields_requires_module_type(self):
        """htmx fields endpoint without module_type returns disabled select."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/compile-scenarios/htmx/fields/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select module type first")

    def test_htmx_values_requires_both_params(self):
        """htmx values endpoint without params returns placeholder."""
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/compile-scenarios/htmx/values/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select module type and field first")

    def test_compile_scenarios_access_forbidden_non_staff(self):
        regular_user = CustomUser.objects.create_user(
            email="regular@example.com", password="testpass123",
            is_staff=False, firebase_uid="regular_uid",
        )
        self.client.login(email="regular@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/compile-scenarios/")
        self.assertEqual(response.status_code, 403)

    def test_export_requires_post(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/compile-scenarios/export/")
        self.assertEqual(response.status_code, 405)
```

**Step 2: Run all tests**

Run: `pytest djangoexact/admin_scripts/tests.py -v`
Expected: ALL PASSED

**Step 3: Commit**

```bash
git add djangoexact/admin_scripts/tests.py
git commit -m "test(admin-scripts): add edge case and integration tests for compile-scenarios"
```

---

## Summary of All Files

| Action | File |
|--------|------|
| Create | `djangoexact/admin_scripts/scenario_utils.py` |
| Create | `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html` |
| Create | `djangoexact/admin_scripts/templates/admin_scripts/partials/change_fieldset.html` |
| Create | `djangoexact/admin_scripts/templates/admin_scripts/partials/value_options.html` |
| Modify | `djangoexact/admin_scripts/views.py` |
| Modify | `djangoexact/admin_scripts/urls.py` |
| Modify | `djangoexact/admin_scripts/tests.py` |
| Modify | `djangoexact/admin_scripts/templates/admin_scripts/base.html` |
