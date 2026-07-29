# Multi-Scenario Support — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend compile-scenarios to support multiple scenarios in a tab-based UI, each with per-scenario run and results, sharing global filters, with combined Excel export.

**Architecture:** Server-rendered tab panels via htmx. Field names gain a `scenario-N-` prefix (e.g. `scenario-0-change-0-module_type`). Each scenario runs independently via htmx POST. Export generates one workbook with per-scenario sheets.

**Tech Stack:** Django 4.x, htmx 2.0.4, Tailwind CSS (CDN), pandas + openpyxl

**Design doc:** `docs/plans/2026-03-04-multi-scenario-design.md`

---

### Task 1: Add prefix support to `_parse_changes_from_post`

**Files:**
- Modify: `djangoexact/admin_scripts/views.py:67-96` (`_parse_changes_from_post`)
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing test**

Add to `CompileScenariosViewTest` in `djangoexact/admin_scripts/tests.py`:

```python
def test_parse_changes_with_scenario_prefix(self):
    from admin_scripts.views import _parse_changes_from_post
    from django.http import QueryDict

    post = QueryDict(mutable=True)
    post["scenario-0-change-0-module_type"] = "Grassland"
    post["scenario-0-change-0-field"] = "grassland_management_type"
    post["scenario-0-change-0-from_value"] = "Non-Degraded"
    post["scenario-0-change-0-to_value"] = "Improved Grassland"
    post.setlist("scenario-0-change-0-filter-region", ["Central Asia"])

    changes = _parse_changes_from_post(post, prefix="scenario-0-")
    self.assertEqual(len(changes), 1)
    self.assertEqual(changes[0]["module_type"], "Grassland")
    self.assertEqual(changes[0]["start"]["field"], "grassland_management_type")
    self.assertEqual(changes[0]["start"]["value"], "Non-Degraded")
    self.assertEqual(changes[0]["end"]["value"], "Improved Grassland")
    self.assertEqual(changes[0]["filters"]["region"], ["Central Asia"])
```

**Step 2: Run test to verify it fails**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_parse_changes_with_scenario_prefix --verbosity=2`

Expected: FAIL — `_parse_changes_from_post()` got unexpected keyword argument 'prefix'

**Step 3: Implement prefix support**

In `djangoexact/admin_scripts/views.py`, change `_parse_changes_from_post`:

```python
def _parse_changes_from_post(post_data, prefix=""):
    """Parse indexed change fields from POST data into a list of change dicts.

    Args:
        post_data: QueryDict from request.POST
        prefix: Optional prefix before 'change-N-' keys (e.g. "scenario-0-")
    """
    changes = []
    index = 0
    while True:
        module_type = post_data.get(f"{prefix}change-{index}-module_type")
        if module_type is None:
            break
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
            region = post_data.getlist(f"{prefix}change-{index}-filter-region")
            if region:
                change["filters"]["region"] = region
            climate = post_data.getlist(f"{prefix}change-{index}-filter-climate")
            if climate:
                change["filters"]["climate"] = climate
            changes.append(change)
        index += 1
    return changes
```

**Step 4: Run test to verify it passes**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_parse_changes_with_scenario_prefix --verbosity=2`

Expected: PASS

**Step 5: Verify existing tests still pass (backward compat)**

Run: `cd djangoexact && python manage.py test admin_scripts --verbosity=2`

Expected: All existing tests pass (default `prefix=""` preserves old behavior)

**Step 6: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/tests.py
git commit -m "feat(admin-scripts): add prefix param to _parse_changes_from_post"
```

---

### Task 2: Add `_parse_scenarios_from_post` helper

**Files:**
- Modify: `djangoexact/admin_scripts/views.py`
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing test**

Add to `CompileScenariosViewTest`:

```python
def test_parse_scenarios_from_post(self):
    from admin_scripts.views import _parse_scenarios_from_post
    from django.http import QueryDict

    post = QueryDict(mutable=True)
    post["scenario-0-scenario_name"] = "Scenario A"
    post["scenario-0-category"] = "Cat A"
    post["scenario-0-change-0-module_type"] = "Grassland"
    post["scenario-0-change-0-field"] = "grassland_management_type"
    post["scenario-0-change-0-from_value"] = "Non-Degraded"
    post["scenario-0-change-0-to_value"] = "Improved Grassland"
    post["scenario-1-scenario_name"] = "Scenario B"
    post["scenario-1-category"] = "Cat B"
    post["scenario-1-change-0-module_type"] = "Annual Cropland"
    post["scenario-1-change-0-field"] = "organic_input_type"
    post["scenario-1-change-0-from_value"] = "Low C input"
    post["scenario-1-change-0-to_value"] = "High C input"

    scenarios = _parse_scenarios_from_post(post)
    self.assertEqual(len(scenarios), 2)
    self.assertEqual(scenarios[0]["scenario_name"], "Scenario A")
    self.assertEqual(scenarios[0]["category"], "Cat A")
    self.assertEqual(len(scenarios[0]["changes"]), 1)
    self.assertEqual(scenarios[0]["changes"][0]["module_type"], "Grassland")
    self.assertEqual(scenarios[1]["scenario_name"], "Scenario B")
    self.assertEqual(len(scenarios[1]["changes"]), 1)
    self.assertEqual(scenarios[1]["changes"][0]["module_type"], "Annual Cropland")
```

**Step 2: Run test to verify it fails**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_parse_scenarios_from_post --verbosity=2`

Expected: FAIL — `_parse_scenarios_from_post` not found

**Step 3: Implement**

Add to `djangoexact/admin_scripts/views.py` after `_parse_global_filters`:

```python
def _parse_scenarios_from_post(post_data):
    """Parse multiple scenarios from POST data.

    Looks for scenario-N-scenario_name keys to detect scenario count,
    then delegates to _parse_changes_from_post for each.

    Returns:
        List of dicts with keys: scenario_name, category, changes
    """
    scenarios = []
    index = 0
    while True:
        name_key = f"scenario-{index}-scenario_name"
        if name_key not in post_data:
            break
        prefix = f"scenario-{index}-"
        scenarios.append({
            "scenario_name": post_data.get(name_key, ""),
            "category": post_data.get(f"scenario-{index}-category", ""),
            "changes": _parse_changes_from_post(post_data, prefix=prefix),
        })
        index += 1
    return scenarios
```

**Step 4: Run test to verify it passes**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_parse_scenarios_from_post --verbosity=2`

Expected: PASS

**Step 5: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/tests.py
git commit -m "feat(admin-scripts): add _parse_scenarios_from_post helper"
```

---

### Task 3: Add key-detection helper for htmx views

**Files:**
- Modify: `djangoexact/admin_scripts/views.py`
- Test: `djangoexact/admin_scripts/tests.py`

The current htmx views have duplicated logic scanning for `change-N-module_type` keys. After multi-scenario, these keys become `scenario-S-change-N-module_type`. Extract a helper that works with both formats.

**Step 1: Write failing test**

Add a new test class to `djangoexact/admin_scripts/tests.py`:

```python
class ChangeKeyParsingTest(TestCase):
    def test_extract_change_key_info_old_format(self):
        from admin_scripts.views import _extract_change_key_info

        result = _extract_change_key_info(
            {"change-2-module_type": "Grassland"},
            suffix="module_type"
        )
        self.assertEqual(result, ("Grassland", "2", "change-2-"))

    def test_extract_change_key_info_scenario_format(self):
        from admin_scripts.views import _extract_change_key_info

        result = _extract_change_key_info(
            {"scenario-1-change-3-module_type": "Grassland"},
            suffix="module_type"
        )
        self.assertEqual(result, ("Grassland", "3", "scenario-1-change-3-"))

    def test_extract_change_key_info_no_match(self):
        from admin_scripts.views import _extract_change_key_info

        result = _extract_change_key_info(
            {"unrelated_key": "value"},
            suffix="module_type"
        )
        self.assertIsNone(result)
```

**Step 2: Run test to verify it fails**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.ChangeKeyParsingTest --verbosity=2`

Expected: FAIL — `_extract_change_key_info` not found

**Step 3: Implement**

Add to `djangoexact/admin_scripts/views.py`:

```python
import re

def _extract_change_key_info(data, suffix):
    """Extract value and index from change-prefixed keys in request data.

    Handles both old format (change-N-suffix) and new format (scenario-S-change-N-suffix).

    Args:
        data: dict-like request.GET or request.POST
        suffix: the field suffix to look for (e.g. "module_type", "field")

    Returns:
        Tuple of (value, change_index, full_prefix) or None if not found.
        full_prefix includes everything up to and including the suffix base,
        e.g. "scenario-1-change-3-" or "change-2-".
    """
    pattern = re.compile(r'^((?:scenario-\d+-)?change-(\d+)-)' + re.escape(suffix) + r'$')
    for key, value in data.items():
        m = pattern.match(key)
        if m and value:
            return (value, m.group(2), m.group(1))
    return None
```

**Step 4: Run test to verify it passes**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.ChangeKeyParsingTest --verbosity=2`

Expected: PASS

**Step 5: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/tests.py
git commit -m "feat(admin-scripts): add _extract_change_key_info helper for prefix detection"
```

---

### Task 4: Update htmx views for scenario-prefix awareness

**Files:**
- Modify: `djangoexact/admin_scripts/views.py:180-303` (htmx_fields, htmx_values, htmx_filters, htmx_add_change)
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing tests**

Add to `CompileScenariosViewTest`:

```python
def test_htmx_fields_with_scenario_prefix(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.get(
        "/api/admin-scripts/compile-scenarios/htmx/fields/",
        {"scenario-0-change-0-module_type": "Grassland"},
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "grassland_management_type")
    self.assertContains(response, 'name="scenario-0-change-0-field"')

def test_htmx_values_with_scenario_prefix(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.get(
        "/api/admin-scripts/compile-scenarios/htmx/values/",
        {
            "scenario-0-change-0-module_type": "Grassland",
            "scenario-0-change-0-field": "grassland_management_type",
            "index": "0",
            "prefix": "scenario-0-change-0-",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Non-Degraded")
    self.assertContains(response, 'name="scenario-0-change-0-from_value"')

def test_htmx_filters_with_scenario_prefix(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.get(
        "/api/admin-scripts/compile-scenarios/htmx/filters/",
        {
            "scenario-0-change-0-module_type": "Grassland",
            "index": "0",
            "prefix": "scenario-0-change-0-",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Central Asia")
    self.assertContains(response, 'name="scenario-0-change-0-filter-region"')

def test_htmx_add_change_with_scenario_index(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.get(
        "/api/admin-scripts/compile-scenarios/htmx/add-change/",
        {"index": "1", "scenario_index": "2"},
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Change #2")
    self.assertContains(response, 'name="scenario-2-change-1-module_type"')
```

**Step 2: Run tests to verify they fail**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_htmx_fields_with_scenario_prefix admin_scripts.tests.CompileScenariosViewTest.test_htmx_values_with_scenario_prefix admin_scripts.tests.CompileScenariosViewTest.test_htmx_filters_with_scenario_prefix admin_scripts.tests.CompileScenariosViewTest.test_htmx_add_change_with_scenario_index --verbosity=2`

Expected: FAIL — responses don't contain scenario-prefixed field names

**Step 3: Update htmx_fields**

Replace `htmx_fields` in `djangoexact/admin_scripts/views.py`:

```python
@login_required(login_url="/admin/login/")
@staff_required
def htmx_fields(request):
    result = _extract_change_key_info(request.GET, "module_type")
    if not result:
        return HttpResponse(
            '<label class="block text-xs font-medium text-gray-500 mb-1">Field</label>'
            '<select disabled class="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-gray-50">'
            '<option>Select module type first...</option></select>'
        )

    module_type, index, prefix = result

    fields = list(
        ChangeRecord.objects.filter(module_type=module_type)
        .values_list("field", flat=True)
        .distinct()
        .order_by("field")
    )
    values_url = reverse("admin_scripts:htmx-values")
    html = (
        f'<label class="block text-xs font-medium text-gray-500 mb-1">Field</label>'
        f'<select name="{prefix}field" required'
        f' hx-get="{values_url}"'
        f' hx-target="#{prefix.replace("-", "-").rstrip("-")}-values-container"'
        f""" hx-include="[name='{prefix}module_type']" """
        f""" hx-vals='{{"index": "{index}", "prefix": "{prefix}"}}' """
        f' hx-trigger="change"'
        f' class="w-full border border-gray-300 rounded px-3 py-2 text-sm">'
        f'<option value="">Select field...</option>'
    )
    for f in fields:
        html += f'<option value="{escape(f)}">{escape(f)}</option>'
    html += "</select>"
    return HttpResponse(html)
```

Wait — the `hx-target` with dynamic prefix creates brittle IDs. Let me rethink. The htmx targets use IDs like `#change-0-field-container`. With scenario prefix, these become `#scenario-0-change-0-field-container`. The safest approach is to pass both `scenario_index` and `index` explicitly, and construct the target ID from those.

Actually, let me reconsider. The `htmx_fields` view currently generates raw HTML (not a template). With the scenario prefix, the generated HTML gets more complex. A cleaner approach: convert `htmx_fields` to use a template too, and pass `scenario_index` + `index` to templates. But that's a bigger refactor.

Simpler: keep the generated HTML approach but build the correct element ID prefix. The element IDs in templates use the pattern `change-{index}-field-container` currently. With scenarios they'll be `scenario-{scenario_index}-change-{index}-field-container`. The htmx view needs to know both indices to generate the correct target ID.

The `_extract_change_key_info` already gives us the `full_prefix` which is `scenario-S-change-N-` or `change-N-`. We can derive the element ID from stripping the trailing `-` from `full_prefix`.

Let me simplify. The element ID prefix = `full_prefix` without trailing `-`. So `scenario-0-change-0-` becomes ID prefix `scenario-0-change-0`.

Let me rewrite step 3 with this clearer approach:

```python
@login_required(login_url="/admin/login/")
@staff_required
def htmx_fields(request):
    result = _extract_change_key_info(request.GET, "module_type")
    if not result:
        return HttpResponse(
            '<label class="block text-xs font-medium text-gray-500 mb-1">Field</label>'
            '<select disabled class="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-gray-50">'
            '<option>Select module type first...</option></select>'
        )

    module_type, index, prefix = result
    id_prefix = prefix.rstrip("-")  # e.g. "scenario-0-change-0" or "change-0"

    fields = list(
        ChangeRecord.objects.filter(module_type=module_type)
        .values_list("field", flat=True)
        .distinct()
        .order_by("field")
    )
    values_url = reverse("admin_scripts:htmx-values")
    html = (
        f'<label class="block text-xs font-medium text-gray-500 mb-1">Field</label>'
        f'<select name="{prefix}field" required'
        f' hx-get="{values_url}"'
        f' hx-target="#{id_prefix}-values-container"'
        f""" hx-include="[name='{prefix}module_type']" """
        f""" hx-vals='{{"index": "{index}", "prefix": "{prefix}"}}' """
        f' hx-trigger="change"'
        f' class="w-full border border-gray-300 rounded px-3 py-2 text-sm">'
        f'<option value="">Select field...</option>'
    )
    for f in fields:
        html += f'<option value="{escape(f)}">{escape(f)}</option>'
    html += "</select>"
    return HttpResponse(html)
```

**Step 4: Update htmx_values**

Replace `htmx_values` in `djangoexact/admin_scripts/views.py`:

```python
@login_required(login_url="/admin/login/")
@staff_required
def htmx_values(request):
    result = _extract_change_key_info(request.GET, "module_type")
    module_type = result[0] if result else None

    field_result = _extract_change_key_info(request.GET, "field")
    field = field_result[0] if field_result else None

    prefix = request.GET.get("prefix", f"change-{request.GET.get('index', '0')}-")
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
        "prefix": prefix,
        "from_values": from_values,
        "to_values": to_values,
    })
```

**Step 5: Update htmx_filters**

Replace `htmx_filters` in `djangoexact/admin_scripts/views.py`:

```python
@login_required(login_url="/admin/login/")
@staff_required
def htmx_filters(request):
    result = _extract_change_key_info(request.GET, "module_type")
    module_type = result[0] if result else None

    prefix = request.GET.get("prefix", f"change-{request.GET.get('index', '0')}-")
    index = request.GET.get("index", "0")

    if not module_type:
        return HttpResponse("")

    qs = ChangeRecord.objects.filter(module_type=module_type)
    regions = list(qs.values_list("region", flat=True).distinct().order_by("region"))
    climates = list(qs.values_list("climate", flat=True).distinct().order_by("climate"))

    return render(request, "admin_scripts/partials/filter_options.html", {
        "index": index,
        "prefix": prefix,
        "regions": regions,
        "climates": climates,
    })
```

**Step 6: Update htmx_add_change**

Replace `htmx_add_change` in `djangoexact/admin_scripts/views.py`:

```python
@login_required(login_url="/admin/login/")
@staff_required
def htmx_add_change(request):
    try:
        index = int(request.GET.get("index", 1))
    except (ValueError, TypeError):
        index = 1
    scenario_index = request.GET.get("scenario_index", None)
    module_types = list(
        ChangeRecord.objects.values_list("module_type", flat=True)
        .distinct()
        .order_by("module_type")
    )
    return render(request, "admin_scripts/partials/change_fieldset.html", {
        "index": index,
        "scenario_index": scenario_index,
        "module_types": module_types,
    })
```

**Step 7: Update template partials for prefix support**

Update `djangoexact/admin_scripts/templates/admin_scripts/partials/value_options.html`:

```html
<div>
    <label class="block text-xs font-medium text-gray-500 mb-1">From Value</label>
    <select name="{{ prefix }}from_value" required
            class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
        <option value="">Select from value...</option>
        {% for val in from_values %}
        <option value="{{ val }}">{{ val }}</option>
        {% endfor %}
    </select>
</div>
<div>
    <label class="block text-xs font-medium text-gray-500 mb-1">To Value</label>
    <select name="{{ prefix }}to_value" required
            class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
        <option value="">Select to value...</option>
        {% for val in to_values %}
        <option value="{{ val }}">{{ val }}</option>
        {% endfor %}
    </select>
</div>
```

Update `djangoexact/admin_scripts/templates/admin_scripts/partials/filter_options.html`:

```html
<div>
    <label class="block text-xs text-gray-400 mb-1">Region</label>
    <select name="{{ prefix }}filter-region" multiple
            class="w-full border border-gray-300 rounded px-2 py-1 text-xs" size="3">
        {% for r in regions %}
        <option value="{{ r }}">{{ r }}</option>
        {% endfor %}
    </select>
</div>
<div>
    <label class="block text-xs text-gray-400 mb-1">Climate</label>
    <select name="{{ prefix }}filter-climate" multiple
            class="w-full border border-gray-300 rounded px-2 py-1 text-xs" size="3">
        {% for c in climates %}
        <option value="{{ c }}">{{ c }}</option>
        {% endfor %}
    </select>
</div>
```

Update `djangoexact/admin_scripts/templates/admin_scripts/partials/change_fieldset.html`:

Use a computed prefix variable. Django templates don't support string concatenation easily, so we'll pass `prefix` from the view context. For the include from `compile_scenarios.html` and `scenario_panel.html`, the prefix will be constructed in the parent template.

Actually, Django templates are limited with string ops. The cleanest approach: always pass a `prefix` variable to change_fieldset.html that contains `scenario-N-change-M-` or `change-M-`. The template just uses `{{ prefix }}`.

But the parent template constructs this with `{% with %}`. Let's use this approach:

```html
{% with prefix=prefix|default:change_prefix %}
<div data-change-index="{{ index }}" class="bg-white border border-gray-200 rounded-lg mb-3 relative">
    <div class="flex justify-between items-center px-5 py-3 cursor-pointer select-none"
         onclick="let b=this.nextElementSibling; let a=this.querySelector('[data-chevron]'); b.classList.toggle('hidden'); a.classList.toggle('rotate-180')">
        <div class="flex items-center gap-2">
            <svg data-chevron class="w-4 h-4 text-gray-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
            <h3 class="text-sm font-semibold text-gray-700">Change #{{ index|add:1 }}</h3>
            <span class="text-xs text-gray-400 change-summary">
                {% if change.module_type %}— {{ change.module_type }}: {{ change.start.value }} &rarr; {{ change.end.value }}{% endif %}
            </span>
        </div>
        {% if index > 0 %}
        <button type="button" onclick="event.stopPropagation(); this.closest('[data-change-index]').remove()"
                class="text-gray-400 hover:text-red-500 text-lg leading-none">&times;</button>
        {% endif %}
    </div>

    <div class="px-5 pb-5">
        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">Module Type</label>
                <select name="{{ prefix }}module_type" required
                        hx-get="{% url 'admin_scripts:htmx-fields' %}"
                        hx-target="#{{ prefix|cut:'-' }}-field-container"
                        hx-include="this"
                        hx-trigger="change"
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
                    <option value="">Select module type...</option>
                    {% for mt in module_types %}
                    <option value="{{ mt }}" {% if change.module_type == mt %}selected{% endif %}>{{ mt }}</option>
                    {% endfor %}
                </select>
            </div>
```

Hmm, `{{ prefix|cut:'-' }}` won't work for building IDs. Django `cut` removes ALL occurrences.

Better approach: pass an explicit `id_prefix` (without trailing `-`) alongside `prefix` (with trailing `-`) for name attributes. This avoids template gymnastics.

Let me restructure: views pass both `prefix` (for `name` attrs, e.g. `"scenario-0-change-0-"`) and `id_prefix` (for `id` attrs, e.g. `"scenario-0-change-0"`).

The full rewritten `change_fieldset.html`:

```html
<div data-change-index="{{ index }}" class="bg-white border border-gray-200 rounded-lg mb-3 relative">
    <div class="flex justify-between items-center px-5 py-3 cursor-pointer select-none"
         onclick="let b=this.nextElementSibling; let a=this.querySelector('[data-chevron]'); b.classList.toggle('hidden'); a.classList.toggle('rotate-180')">
        <div class="flex items-center gap-2">
            <svg data-chevron class="w-4 h-4 text-gray-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
            <h3 class="text-sm font-semibold text-gray-700">Change #{{ index|add:1 }}</h3>
            <span class="text-xs text-gray-400 change-summary">
                {% if change.module_type %}— {{ change.module_type }}: {{ change.start.value }} &rarr; {{ change.end.value }}{% endif %}
            </span>
        </div>
        {% if index > 0 %}
        <button type="button" onclick="event.stopPropagation(); this.closest('[data-change-index]').remove()"
                class="text-gray-400 hover:text-red-500 text-lg leading-none">&times;</button>
        {% endif %}
    </div>

    <div class="px-5 pb-5">
        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">Module Type</label>
                <select name="{{ prefix }}module_type" required
                        hx-get="{% url 'admin_scripts:htmx-fields' %}"
                        hx-target="#{{ id_prefix }}-field-container"
                        hx-include="this"
                        hx-trigger="change"
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
                    <option value="">Select module type...</option>
                    {% for mt in module_types %}
                    <option value="{{ mt }}" {% if change.module_type == mt %}selected{% endif %}>{{ mt }}</option>
                    {% endfor %}
                </select>
            </div>

            <div id="{{ id_prefix }}-field-container">
                <label class="block text-xs font-medium text-gray-500 mb-1">Field</label>
                {% if change.fields %}
                <select name="{{ prefix }}field" required
                        hx-get="{% url 'admin_scripts:htmx-values' %}"
                        hx-target="#{{ id_prefix }}-values-container"
                        hx-include="[name='{{ prefix }}module_type']"
                        hx-vals='{"index": "{{ index }}", "prefix": "{{ prefix }}"}'
                        hx-trigger="change"
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
                    <option value="">Select field...</option>
                    {% for f in change.fields %}
                    <option value="{{ f }}" {% if change.start.field == f %}selected{% endif %}>{{ f }}</option>
                    {% endfor %}
                </select>
                {% else %}
                <select name="{{ prefix }}field" required disabled
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-gray-50">
                    <option value="">Select module type first...</option>
                </select>
                {% endif %}
            </div>
        </div>

        <div id="{{ id_prefix }}-values-container" class="grid grid-cols-2 gap-4 mt-3">
            <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">From Value</label>
                {% if change.from_values %}
                <select name="{{ prefix }}from_value" required
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
                    <option value="">Select from value...</option>
                    {% for val in change.from_values %}
                    <option value="{{ val }}" {% if change.start.value == val %}selected{% endif %}>{{ val }}</option>
                    {% endfor %}
                </select>
                {% else %}
                <select name="{{ prefix }}from_value" required disabled
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-gray-50">
                    <option value="">Select field first...</option>
                </select>
                {% endif %}
            </div>
            <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">To Value</label>
                {% if change.to_values %}
                <select name="{{ prefix }}to_value" required
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
                    <option value="">Select to value...</option>
                    {% for val in change.to_values %}
                    <option value="{{ val }}" {% if change.end.value == val %}selected{% endif %}>{{ val }}</option>
                    {% endfor %}
                </select>
                {% else %}
                <select name="{{ prefix }}to_value" required disabled
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-gray-50">
                    <option value="">Select field first...</option>
                </select>
                {% endif %}
            </div>
        </div>

        <details class="mt-3">
            <summary class="text-xs font-medium text-gray-500 cursor-pointer">Change-level Filters</summary>
            <div id="{{ id_prefix }}-filters-container" class="mt-2 grid grid-cols-2 gap-3"
                 hx-get="{% url 'admin_scripts:htmx-filters' %}"
                 hx-include="[name='{{ prefix }}module_type']"
                 hx-vals='{"index": "{{ index }}", "prefix": "{{ prefix }}"}'
                 hx-trigger="change from:[name='{{ prefix }}module_type']"
                 hx-swap="innerHTML">
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Region</label>
                    <select name="{{ prefix }}filter-region" multiple
                            class="w-full border border-gray-300 rounded px-2 py-1 text-xs" size="2">
                    </select>
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Climate</label>
                    <select name="{{ prefix }}filter-climate" multiple
                            class="w-full border border-gray-300 rounded px-2 py-1 text-xs" size="2">
                    </select>
                </div>
            </div>
        </details>
    </div>
</div>
```

The `htmx_add_change` view must construct `prefix` and `id_prefix`:

```python
@login_required(login_url="/admin/login/")
@staff_required
def htmx_add_change(request):
    try:
        index = int(request.GET.get("index", 1))
    except (ValueError, TypeError):
        index = 1
    scenario_index = request.GET.get("scenario_index", None)

    if scenario_index is not None:
        prefix = f"scenario-{scenario_index}-change-{index}-"
        id_prefix = f"scenario-{scenario_index}-change-{index}"
    else:
        prefix = f"change-{index}-"
        id_prefix = f"change-{index}"

    module_types = list(
        ChangeRecord.objects.values_list("module_type", flat=True)
        .distinct()
        .order_by("module_type")
    )
    return render(request, "admin_scripts/partials/change_fieldset.html", {
        "index": index,
        "prefix": prefix,
        "id_prefix": id_prefix,
        "scenario_index": scenario_index,
        "module_types": module_types,
    })
```

The `htmx_fields` view must also pass `id_prefix` in `hx-vals` and use it for generated target IDs. Revise the `htmx_fields` implementation:

```python
@login_required(login_url="/admin/login/")
@staff_required
def htmx_fields(request):
    result = _extract_change_key_info(request.GET, "module_type")
    if not result:
        return HttpResponse(
            '<label class="block text-xs font-medium text-gray-500 mb-1">Field</label>'
            '<select disabled class="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-gray-50">'
            '<option>Select module type first...</option></select>'
        )

    module_type, index, prefix = result
    id_prefix = prefix.rstrip("-")

    fields = list(
        ChangeRecord.objects.filter(module_type=module_type)
        .values_list("field", flat=True)
        .distinct()
        .order_by("field")
    )
    values_url = reverse("admin_scripts:htmx-values")
    html = (
        f'<label class="block text-xs font-medium text-gray-500 mb-1">Field</label>'
        f'<select name="{prefix}field" required'
        f' hx-get="{values_url}"'
        f' hx-target="#{id_prefix}-values-container"'
        f""" hx-include="[name='{prefix}module_type']" """
        f""" hx-vals='{{"index": "{index}", "prefix": "{prefix}"}}' """
        f' hx-trigger="change"'
        f' class="w-full border border-gray-300 rounded px-3 py-2 text-sm">'
        f'<option value="">Select field...</option>'
    )
    for f in fields:
        html += f'<option value="{escape(f)}">{escape(f)}</option>'
    html += "</select>"
    return HttpResponse(html)
```

**Step 8: Run tests to verify they pass**

Run: `cd djangoexact && python manage.py test admin_scripts --verbosity=2`

Expected: All tests pass (both old-format and new scenario-prefixed tests)

**Step 9: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/tests.py djangoexact/admin_scripts/templates/
git commit -m "feat(admin-scripts): update htmx views and templates for scenario-prefix support"
```

---

### Task 5: Create scenario_results.html partial

**Files:**
- Create: `djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_results.html`

**Step 1: Extract the results block from compile_scenarios.html**

Create `djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_results.html`:

```html
{% if statistics %}
<div class="bg-white border border-gray-200 rounded-lg p-5 mt-4">
    <h3 class="text-md font-semibold text-gray-900 mb-3">Results</h3>

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
    {% endif %}
</div>
{% endif %}

{% if error %}
<div class="mt-4 bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
    {{ error }}
</div>
{% endif %}
```

**Step 2: Commit**

```bash
git add djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_results.html
git commit -m "feat(admin-scripts): extract scenario_results.html partial"
```

---

### Task 6: Add htmx_run_scenario view + URL

**Files:**
- Modify: `djangoexact/admin_scripts/views.py`
- Modify: `djangoexact/admin_scripts/urls.py`
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing test**

Add to `CompileScenariosViewTest`:

```python
def test_htmx_run_scenario(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.post(
        "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
        {
            "scenario-0-scenario_name": "Test Scenario",
            "scenario-0-category": "Test",
            "scenario-0-change-0-module_type": "Grassland",
            "scenario-0-change-0-field": "grassland_management_type",
            "scenario-0-change-0-from_value": "Non-Degraded",
            "scenario-0-change-0-to_value": "Improved Grassland",
            "global_filter_soil_type": ["High Activity Clay"],
            "scenario_index": "0",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Results")
    self.assertContains(response, "Count")

def test_htmx_run_scenario_no_changes(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.post(
        "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
        {
            "scenario-0-scenario_name": "Empty",
            "scenario-0-category": "Test",
            "scenario_index": "0",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "at least one change")

def test_htmx_run_scenario_requires_post(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.get("/api/admin-scripts/compile-scenarios/htmx/run-scenario/")
    self.assertEqual(response.status_code, 405)
```

**Step 2: Run test to verify it fails**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_htmx_run_scenario --verbosity=2`

Expected: 404 — URL doesn't exist yet

**Step 3: Add URL**

In `djangoexact/admin_scripts/urls.py`, add:

```python
path("compile-scenarios/htmx/run-scenario/", views.htmx_run_scenario, name="htmx-run-scenario"),
```

**Step 4: Implement view**

Add to `djangoexact/admin_scripts/views.py`:

```python
@login_required(login_url="/admin/login/")
@staff_required
def htmx_run_scenario(request):
    if request.method != "POST":
        return HttpResponse("POST required", status=405)

    scenario_index = request.POST.get("scenario_index", "0")
    prefix = f"scenario-{scenario_index}-"

    changes = _parse_changes_from_post(request.POST, prefix=prefix)
    global_filters = _parse_global_filters(request.POST)

    context = {}
    if not changes:
        context["error"] = "Please add at least one change."
    else:
        q_objects = build_scenario_query(changes, global_filters)
        aggregates = ChangeRecord.objects.filter(q_objects)
        context["statistics"] = stats_for(aggregates)

    return render(request, "admin_scripts/partials/scenario_results.html", context)
```

**Step 5: Run tests to verify they pass**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_htmx_run_scenario admin_scripts.tests.CompileScenariosViewTest.test_htmx_run_scenario_no_changes admin_scripts.tests.CompileScenariosViewTest.test_htmx_run_scenario_requires_post --verbosity=2`

Expected: PASS

**Step 6: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/urls.py djangoexact/admin_scripts/tests.py
git commit -m "feat(admin-scripts): add htmx_run_scenario view for per-scenario execution"
```

---

### Task 7: Add htmx_add_scenario view + URL + scenario_panel.html

**Files:**
- Modify: `djangoexact/admin_scripts/views.py`
- Modify: `djangoexact/admin_scripts/urls.py`
- Create: `djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_panel.html`
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing test**

Add to `CompileScenariosViewTest`:

```python
def test_htmx_add_scenario(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.get(
        "/api/admin-scripts/compile-scenarios/htmx/add-scenario/",
        {"index": "1"},
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, 'data-scenario-tab="1"')
    self.assertContains(response, 'data-scenario-panel="1"')
    self.assertContains(response, 'name="scenario-1-scenario_name"')
    self.assertContains(response, 'name="scenario-1-change-0-module_type"')
```

**Step 2: Run test to verify it fails**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_htmx_add_scenario --verbosity=2`

Expected: 404

**Step 3: Create scenario_panel.html**

Create `djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_panel.html`:

```html
<div data-scenario-panel="{{ scenario_index }}" {% if not active %}class="hidden"{% endif %}>
    <div class="bg-white border border-gray-200 rounded-lg p-5 mb-4">
        <div class="grid grid-cols-2 gap-4 mb-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Scenario Name</label>
                <input type="text" name="scenario-{{ scenario_index }}-scenario_name" required
                       value="{{ scenario.scenario_name|default:'' }}"
                       class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                       placeholder="e.g. Custom Grassland Improvement">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <input type="text" name="scenario-{{ scenario_index }}-category"
                       value="{{ scenario.category|default:'' }}"
                       class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                       placeholder="e.g. Soil and Land Restoration">
            </div>
        </div>
    </div>

    <div id="scenario-{{ scenario_index }}-changes-container">
        {% if scenario.changes %}
            {% for change in scenario.changes %}
                {% include "admin_scripts/partials/change_fieldset.html" with index=forloop.counter0 prefix=change.prefix id_prefix=change.id_prefix module_types=module_types change=change %}
            {% endfor %}
        {% else %}
            {% include "admin_scripts/partials/change_fieldset.html" with index=0 prefix=default_prefix id_prefix=default_id_prefix module_types=module_types %}
        {% endif %}
    </div>

    <button type="button"
            hx-get="{% url 'admin_scripts:htmx-add-change' %}"
            hx-target="#scenario-{{ scenario_index }}-changes-container"
            hx-swap="beforeend"
            hx-vals='js:{"index": document.querySelectorAll("#scenario-{{ scenario_index }}-changes-container [data-change-index]").length, "scenario_index": "{{ scenario_index }}"}'
            class="mt-2 mb-4 text-sm text-blue-600 hover:text-blue-800 font-medium">
        + Add Another Change
    </button>

    <div class="flex items-center gap-3 mb-4">
        <button type="button"
                hx-post="{% url 'admin_scripts:htmx-run-scenario' %}"
                hx-target="#scenario-{{ scenario_index }}-results"
                hx-include="[name^='scenario-{{ scenario_index }}-'], [name^='global_filter_']"
                hx-vals='{"scenario_index": "{{ scenario_index }}"}'
                class="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 text-sm font-medium">
            Run Scenario
        </button>
        {% if scenario_index != "0" and scenario_index != 0 %}
        <button type="button"
                onclick="document.querySelector('[data-scenario-panel=\'{{ scenario_index }}\']').remove(); document.querySelector('[data-scenario-tab=\'{{ scenario_index }}\']').remove(); var tabs = document.querySelectorAll('[data-scenario-tab]'); if (tabs.length > 0) switchScenarioTab(tabs[0].dataset.scenarioTab);"
                class="text-sm text-red-500 hover:text-red-700">
            Remove Scenario
        </button>
        {% endif %}
    </div>

    <div id="scenario-{{ scenario_index }}-results">
        {% if scenario.statistics %}
            {% include "admin_scripts/partials/scenario_results.html" with statistics=scenario.statistics %}
        {% endif %}
    </div>
</div>
```

**Step 4: Add URL**

In `djangoexact/admin_scripts/urls.py`, add:

```python
path("compile-scenarios/htmx/add-scenario/", views.htmx_add_scenario, name="htmx-add-scenario"),
```

**Step 5: Implement view**

Add to `djangoexact/admin_scripts/views.py`:

```python
@login_required(login_url="/admin/login/")
@staff_required
def htmx_add_scenario(request):
    try:
        scenario_index = int(request.GET.get("index", 1))
    except (ValueError, TypeError):
        scenario_index = 1

    module_types = list(
        ChangeRecord.objects.values_list("module_type", flat=True)
        .distinct()
        .order_by("module_type")
    )

    default_prefix = f"scenario-{scenario_index}-change-0-"
    default_id_prefix = f"scenario-{scenario_index}-change-0"

    # Return both the tab button and the panel, separated by an OOB swap
    tab_html = (
        f'<button type="button" data-scenario-tab="{scenario_index}"'
        f' onclick="switchScenarioTab({scenario_index})"'
        f' class="px-4 py-2 text-sm font-medium border-b-2 border-blue-500 text-blue-600"'
        f' hx-swap-oob="beforeend:#scenario-tabs">'
        f'Scenario {scenario_index + 1}'
        f'</button>'
    )

    from django.template.loader import render_to_string
    panel_html = render_to_string(
        "admin_scripts/partials/scenario_panel.html",
        {
            "scenario_index": scenario_index,
            "module_types": module_types,
            "default_prefix": default_prefix,
            "default_id_prefix": default_id_prefix,
            "active": True,
        },
        request=request,
    )

    # The panel is the main response (appended to panels container)
    # The tab is an out-of-band swap
    return HttpResponse(panel_html + tab_html)
```

**Step 6: Run tests to verify they pass**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_htmx_add_scenario --verbosity=2`

Expected: PASS

**Step 7: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/urls.py djangoexact/admin_scripts/tests.py djangoexact/admin_scripts/templates/admin_scripts/partials/scenario_panel.html
git commit -m "feat(admin-scripts): add htmx_add_scenario view and scenario_panel template"
```

---

### Task 8: Restructure compile_scenarios.html for tab layout

**Files:**
- Modify: `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html`
- Modify: `djangoexact/admin_scripts/views.py:113-157` (compile_scenarios view)

**Step 1: Rewrite compile_scenarios.html**

Replace `djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html`:

```html
{% extends "admin_scripts/base.html" %}

{% block title %}Compile Scenarios — Admin Scripts{% endblock %}

{% block content %}
<a href="{% url 'admin_scripts:dashboard' %}" class="text-sm text-blue-600 hover:text-blue-800 mb-4 inline-block">&larr; Back to Dashboard</a>

<h1 class="text-2xl font-bold text-gray-900 mb-2">Compile Scenarios</h1>
<p class="text-sm text-gray-500 mb-6">Build custom emission scenarios and compute statistics from ChangeRecord data.</p>

<form method="post" action="{% url 'admin_scripts:compile-scenarios-export' %}" id="scenario-form">
    {% csrf_token %}

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

    {# Scenario panels #}
    <div id="scenario-panels">
        {% for scenario in scenarios %}
            {% include "admin_scripts/partials/scenario_panel.html" with scenario_index=forloop.counter0 scenario=scenario module_types=module_types default_prefix=scenario.default_prefix default_id_prefix=scenario.default_id_prefix active=forloop.first %}
        {% endfor %}
    </div>

    {# Global filters (shared) #}
    <details class="bg-white border border-gray-200 rounded-lg p-5 mb-6">
        <summary class="text-sm font-medium text-gray-700 cursor-pointer">Global Filters (applied to all scenarios)</summary>
        <div class="mt-3 grid grid-cols-2 gap-4">
            <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">Soil Type</label>
                <select name="global_filter_soil_type" multiple
                        class="w-full border border-gray-300 rounded px-3 py-2 text-sm" size="3">
                    <option value="High Activity Clay" {% if "High Activity Clay" in global_filter_soil_type %}selected{% else %}selected{% endif %}>High Activity Clay</option>
                    <option value="Low Activity Clay" {% if "Low Activity Clay" in global_filter_soil_type %}selected{% else %}selected{% endif %}>Low Activity Clay</option>
                    <option value="Sandy" {% if "Sandy" in global_filter_soil_type %}selected{% else %}selected{% endif %}>Sandy</option>
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

    {# Export all #}
    <button type="submit"
            class="bg-green-600 text-white px-6 py-2 rounded hover:bg-green-700 text-sm font-medium">
        Export All to Excel
    </button>
</form>

<script>
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
</script>
{% endblock %}
```

**Step 2: Update compile_scenarios view**

Replace the `compile_scenarios` view in `djangoexact/admin_scripts/views.py`:

```python
@login_required(login_url="/admin/login/")
@staff_required
def compile_scenarios(request):
    module_types = list(
        ChangeRecord.objects.values_list("module_type", flat=True)
        .distinct()
        .order_by("module_type")
    )

    if request.method == "POST":
        # This path is no longer used for running scenarios (htmx handles that).
        # Keep it as a fallback that redirects back to the GET page.
        pass

    # On GET, render one empty scenario tab
    scenarios = [{
        "scenario_name": "",
        "category": "",
        "changes": [],
        "default_prefix": "scenario-0-change-0-",
        "default_id_prefix": "scenario-0-change-0",
    }]

    context = {
        "module_types": module_types,
        "scenarios": scenarios,
    }
    return render(request, "admin_scripts/scripts/compile_scenarios.html", context)
```

**Step 3: Run all existing tests**

Run: `cd djangoexact && python manage.py test admin_scripts --verbosity=2`

Some existing tests that POST to compile_scenarios with the old `change-0-` naming will need updating (see Task 10). For now, verify the GET tests and htmx tests pass.

**Step 4: Commit**

```bash
git add djangoexact/admin_scripts/templates/admin_scripts/scripts/compile_scenarios.html djangoexact/admin_scripts/views.py
git commit -m "feat(admin-scripts): restructure compile_scenarios for tab-based multi-scenario UI"
```

---

### Task 9: Update compile_scenarios_export for multi-scenario

**Files:**
- Modify: `djangoexact/admin_scripts/views.py:310-370` (compile_scenarios_export)
- Test: `djangoexact/admin_scripts/tests.py`

**Step 1: Write failing test**

Add to `CompileScenariosViewTest`:

```python
def test_export_multi_scenario(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.post("/api/admin-scripts/compile-scenarios/export/", {
        "scenario-0-scenario_name": "Scenario A",
        "scenario-0-category": "Cat A",
        "scenario-0-change-0-module_type": "Grassland",
        "scenario-0-change-0-field": "grassland_management_type",
        "scenario-0-change-0-from_value": "Non-Degraded",
        "scenario-0-change-0-to_value": "Improved Grassland",
        "scenario-1-scenario_name": "Scenario B",
        "scenario-1-category": "Cat B",
        "scenario-1-change-0-module_type": "Annual Cropland",
        "scenario-1-change-0-field": "organic_input_type",
        "scenario-1-change-0-from_value": "Low C input",
        "scenario-1-change-0-to_value": "High C input",
        "global_filter_soil_type": ["High Activity Clay"],
    })
    self.assertEqual(response.status_code, 200)
    self.assertEqual(
        response["Content-Type"],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    # Verify workbook has sheets for both scenarios
    import openpyxl
    from io import BytesIO
    wb = openpyxl.load_workbook(BytesIO(b"".join(response.streaming_content)))
    sheet_names = wb.sheetnames
    self.assertIn("Scenario A", sheet_names)
    self.assertIn("Scenario A Changes", sheet_names)
    self.assertIn("Scenario B", sheet_names)
    self.assertIn("Scenario B Changes", sheet_names)
```

**Step 2: Run test to verify it fails**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_export_multi_scenario --verbosity=2`

Expected: FAIL — current export uses single-scenario format

**Step 3: Implement multi-scenario export**

Replace `compile_scenarios_export` in `djangoexact/admin_scripts/views.py`:

```python
@login_required(login_url="/admin/login/")
@staff_required
def compile_scenarios_export(request):
    if request.method != "POST":
        return HttpResponse("POST required", status=405)

    scenarios = _parse_scenarios_from_post(request.POST)
    global_filters = _parse_global_filters(request.POST)

    if not scenarios:
        return HttpResponse("No scenarios provided", status=400)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for scenario in scenarios:
            scenario_name = scenario["scenario_name"] or "Unnamed Scenario"
            category = scenario["category"]
            changes = scenario["changes"]

            if not changes:
                continue

            q_objects = build_scenario_query(changes, global_filters)
            aggregates = ChangeRecord.objects.filter(q_objects)
            statistics = stats_for(aggregates)

            # Summary sheet (truncate name to 31 chars for Excel limit)
            summary_sheet = scenario_name[:31]
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
            }]
            pd.DataFrame(summary_data).to_excel(writer, sheet_name=summary_sheet, index=False)

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

    buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scenarios_{timestamp}.xlsx"

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

**Step 4: Run test to verify it passes**

Run: `cd djangoexact && python manage.py test admin_scripts.tests.CompileScenariosViewTest.test_export_multi_scenario --verbosity=2`

Expected: PASS

**Step 5: Commit**

```bash
git add djangoexact/admin_scripts/views.py djangoexact/admin_scripts/tests.py
git commit -m "feat(admin-scripts): update export for multi-scenario workbook"
```

---

### Task 10: Update existing tests for new naming convention

**Files:**
- Modify: `djangoexact/admin_scripts/tests.py`

The existing `CompileScenariosViewTest` tests that POST to `/compile-scenarios/` using the old `change-0-` naming need updating. Since the main `compile_scenarios` view no longer processes POST (htmx handles that), these tests should be redirected to test the htmx_run_scenario endpoint, or removed if redundant.

**Step 1: Update tests**

Replace the POST tests in `CompileScenariosViewTest` to use scenario-prefixed names and target the htmx endpoint:

```python
def test_compile_scenarios_post_returns_statistics(self):
    """Test via htmx run-scenario endpoint."""
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.post(
        "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
        {
            "scenario-0-scenario_name": "Test Scenario",
            "scenario-0-category": "Test Category",
            "scenario-0-change-0-module_type": "Grassland",
            "scenario-0-change-0-field": "grassland_management_type",
            "scenario-0-change-0-from_value": "Non-Degraded",
            "scenario-0-change-0-to_value": "Improved Grassland",
            "scenario_index": "0",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Results")
    self.assertContains(response, "Count")

def test_compile_scenarios_post_no_matching_records(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.post(
        "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
        {
            "scenario-0-scenario_name": "Empty Scenario",
            "scenario-0-category": "Test",
            "scenario-0-change-0-module_type": "Nonexistent",
            "scenario-0-change-0-field": "fake_field",
            "scenario-0-change-0-from_value": "A",
            "scenario-0-change-0-to_value": "B",
            "scenario_index": "0",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "No matching records")

def test_compile_scenarios_post_with_global_filters(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.post(
        "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
        {
            "scenario-0-scenario_name": "Filtered Scenario",
            "scenario-0-category": "Test",
            "scenario-0-change-0-module_type": "Grassland",
            "scenario-0-change-0-field": "grassland_management_type",
            "scenario-0-change-0-from_value": "Non-Degraded",
            "scenario-0-change-0-to_value": "Improved Grassland",
            "global_filter_soil_type": ["Sandy"],
            "scenario_index": "0",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Results")

def test_compile_scenarios_post_multiple_changes(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.post(
        "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
        {
            "scenario-0-scenario_name": "Multi-Change",
            "scenario-0-category": "Test",
            "scenario-0-change-0-module_type": "Grassland",
            "scenario-0-change-0-field": "grassland_management_type",
            "scenario-0-change-0-from_value": "Non-Degraded",
            "scenario-0-change-0-to_value": "Improved Grassland",
            "scenario-0-change-1-module_type": "Annual Cropland",
            "scenario-0-change-1-field": "organic_input_type",
            "scenario-0-change-1-from_value": "Low C input",
            "scenario-0-change-1-to_value": "High C input",
            "scenario_index": "0",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Results")

def test_compile_scenarios_post_missing_changes(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.post(
        "/api/admin-scripts/compile-scenarios/htmx/run-scenario/",
        {
            "scenario-0-scenario_name": "Empty",
            "scenario-0-category": "Test",
            "scenario_index": "0",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "at least one change")
```

Also update the export test:

```python
def test_export_to_excel(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.post("/api/admin-scripts/compile-scenarios/export/", {
        "scenario-0-scenario_name": "Test Export",
        "scenario-0-category": "Test",
        "scenario-0-change-0-module_type": "Grassland",
        "scenario-0-change-0-field": "grassland_management_type",
        "scenario-0-change-0-from_value": "Non-Degraded",
        "scenario-0-change-0-to_value": "Improved Grassland",
    })
    self.assertEqual(response.status_code, 200)
    self.assertEqual(
        response["Content-Type"],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

Update the htmx tests for scenario prefix where applicable:

```python
def test_htmx_add_change(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.get(
        "/api/admin-scripts/compile-scenarios/htmx/add-change/",
        {"index": "1", "scenario_index": "0"},
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Change #2")
    self.assertContains(response, "scenario-0-change-1-module_type")
```

Update the GET test to check for the new UI elements:

```python
def test_compile_scenarios_get_returns_form(self):
    self.client.login(email="staff@example.com", password="testpass123")
    response = self.client.get("/api/admin-scripts/compile-scenarios/")
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Compile Scenarios")
    self.assertContains(response, "Scenario Name")
    self.assertContains(response, "Add Scenario")
    self.assertContains(response, "Run Scenario")
    self.assertContains(response, "Export All to Excel")
```

**Step 2: Run all tests**

Run: `cd djangoexact && python manage.py test admin_scripts --verbosity=2`

Expected: All tests pass

**Step 3: Commit**

```bash
git add djangoexact/admin_scripts/tests.py
git commit -m "test(admin-scripts): update tests for multi-scenario naming convention"
```

---

### Task 11: Final integration testing and cleanup

**Step 1: Run the full test suite**

Run: `cd djangoexact && python manage.py test admin_scripts --verbosity=2`

Expected: All tests pass

**Step 2: Manual smoke test (optional)**

Run: `cd djangoexact && python manage.py runserver`

Visit `http://localhost:8000/api/admin-scripts/compile-scenarios/` and verify:
- Single scenario tab renders on load
- "Add Scenario" adds a new tab
- Tab switching works
- Per-scenario "Run Scenario" returns results via htmx
- "Remove Scenario" removes the tab and panel
- "Export All" downloads a workbook
- Global filters are visible below all scenario tabs

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix(admin-scripts): integration fixes for multi-scenario UI"
```
