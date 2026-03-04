import io
from datetime import datetime
from functools import wraps

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import escape

from admin_scripts.scenario_utils import build_scenario_query, stats_for
from minitool.models import ChangeRecord


def staff_required(view_func):
    """Decorator that checks if the authenticated user is a staff member."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("You do not have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return wrapper


SCRIPTS = [
    {
        "name": "Example Script",
        "url": "example-script",
        "description": "A placeholder script to demonstrate the scaffolding pattern.",
    },
    {
        "name": "Compile Scenarios",
        "url": "compile-scenarios",
        "description": "Build custom emission scenarios and compute statistics from ChangeRecord data.",
    },
]


@login_required(login_url="/admin/login/")
@staff_required
def dashboard(request):
    return render(request, "admin_scripts/dashboard.html", {"scripts": SCRIPTS})


@login_required(login_url="/admin/login/")
@staff_required
def example_script(request):
    result = None
    error = None
    if request.method == "POST":
        name = request.POST.get("name", "")
        if name:
            result = f"Hello, {name}! The script ran successfully."
        else:
            error = "Please provide a name."
    return render(request, "admin_scripts/scripts/example_script.html", {
        "result": result,
        "error": error,
    })


# ---------------------------------------------------------------------------
# Compile Scenarios
# ---------------------------------------------------------------------------

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

        # Enrich changes with available options so the form can re-render with selections
        for change in changes:
            mt = change["module_type"]
            change["fields"] = list(
                ChangeRecord.objects.filter(module_type=mt)
                .values_list("field", flat=True).distinct().order_by("field")
            )
            fld = change["start"]["field"]
            if fld:
                qs = ChangeRecord.objects.filter(module_type=mt, field=fld)
                change["from_values"] = list(
                    qs.values_list("from_value", flat=True).distinct().order_by("from_value")
                )
                change["to_values"] = list(
                    qs.values_list("to_value", flat=True).distinct().order_by("to_value")
                )

        context["scenario_name"] = request.POST.get("scenario_name", "")
        context["category"] = request.POST.get("category", "")
        context["changes"] = changes
        context["global_filters"] = global_filters

    return render(request, "admin_scripts/scripts/compile_scenarios.html", context)


# ---------------------------------------------------------------------------
# htmx partial endpoints
# ---------------------------------------------------------------------------

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
        options.append(f'<option value="{escape(mt)}">{escape(mt)}</option>')
    return HttpResponse("\n".join(options))


@login_required(login_url="/admin/login/")
@staff_required
def htmx_fields(request):
    module_type = None
    index = "0"
    for key, value in request.GET.items():
        if key.startswith("change-") and key.endswith("-module_type") and value:
            module_type = value
            index = key.split("-")[1]
            break

    if not module_type:
        return HttpResponse(
            '<label class="block text-xs font-medium text-gray-500 mb-1">Field</label>'
            '<select disabled class="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-gray-50">'
            '<option>Select module type first...</option></select>'
        )

    fields = list(
        ChangeRecord.objects.filter(module_type=module_type)
        .values_list("field", flat=True)
        .distinct()
        .order_by("field")
    )
    values_url = reverse("admin_scripts:htmx-values")
    html = (
        f'<label class="block text-xs font-medium text-gray-500 mb-1">Field</label>'
        f'<select name="change-{index}-field" required'
        f' hx-get="{values_url}"'
        f' hx-target="#change-{index}-values-container"'
        f""" hx-include="[name='change-{index}-module_type']" """
        f""" hx-vals='{{"index": "{index}"}}' """
        f' hx-trigger="change"'
        f' class="w-full border border-gray-300 rounded px-3 py-2 text-sm">'
        f'<option value="">Select field...</option>'
    )
    for f in fields:
        html += f'<option value="{escape(f)}">{escape(f)}</option>'
    html += "</select>"
    return HttpResponse(html)


@login_required(login_url="/admin/login/")
@staff_required
def htmx_values(request):
    module_type = request.GET.get("module_type")
    if not module_type:
        for key, value in request.GET.items():
            if key.startswith("change-") and key.endswith("-module_type") and value:
                module_type = value
                break

    field = request.GET.get("field")
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
def htmx_filters(request):
    module_type = request.GET.get("module_type")
    if not module_type:
        for key, value in request.GET.items():
            if key.startswith("change-") and key.endswith("-module_type") and value:
                module_type = value
                break

    index = request.GET.get("index", "0")

    if not module_type:
        return HttpResponse("")

    qs = ChangeRecord.objects.filter(module_type=module_type)
    regions = list(qs.values_list("region", flat=True).distinct().order_by("region"))
    climates = list(qs.values_list("climate", flat=True).distinct().order_by("climate"))

    return render(request, "admin_scripts/partials/filter_options.html", {
        "index": index,
        "regions": regions,
        "climates": climates,
    })


@login_required(login_url="/admin/login/")
@staff_required
def htmx_add_change(request):
    try:
        index = int(request.GET.get("index", 1))
    except (ValueError, TypeError):
        index = 1
    module_types = list(
        ChangeRecord.objects.values_list("module_type", flat=True)
        .distinct()
        .order_by("module_type")
    )
    return render(request, "admin_scripts/partials/change_fieldset.html", {
        "index": index,
        "module_types": module_types,
    })


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

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
        }]
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)

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
