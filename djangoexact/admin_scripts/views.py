import io
from datetime import datetime
from functools import wraps

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.urls import reverse

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

def _parse_changes_from_post(post_data):
    """Parse indexed change fields from POST data into a list of change dicts."""
    changes = []
    index = 0
    while True:
        module_type = post_data.get(f"change-{index}-module_type")
        if module_type is None:
            break
        if module_type:
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


def _compute_distribution(statistics):
    """Determine if distribution is symmetric or skewed and compute range."""
    if (
        statistics["count"] > 1
        and statistics["std"]
        and statistics["mean"] is not None
        and statistics["median"] is not None
    ):
        mean_minus_median = abs(statistics["mean"] - statistics["median"])
        if mean_minus_median < 0.25 * statistics["std"]:
            return {
                "distribution": "Symmetric",
                "distribution_class": "bg-blue-50 text-blue-800",
                "range_lower": statistics["mean"] - statistics["std"],
                "range_upper": statistics["mean"] + statistics["std"],
            }
        else:
            return {
                "distribution": "Skewed",
                "distribution_class": "bg-amber-50 text-amber-800",
                "range_lower": statistics["q1"],
                "range_upper": statistics["q3"],
            }
    return {}


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
            context.update(_compute_distribution(statistics))

        context["scenario_name"] = request.POST.get("scenario_name", "")
        context["category"] = request.POST.get("category", "")
        context["changes"] = changes

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
        options.append(f'<option value="{mt}">{mt}</option>')
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
        html += f'<option value="{f}">{f}</option>'
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

    dist = _compute_distribution(statistics)

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
            "Distribution": dist.get("distribution", ""),
            "Range Lower": dist.get("range_lower"),
            "Range Upper": dist.get("range_upper"),
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
