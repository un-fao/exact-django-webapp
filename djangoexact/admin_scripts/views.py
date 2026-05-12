import io
import re
from datetime import datetime
from functools import wraps

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.urls import reverse

from admin_scripts.catalog import get_catalog
from admin_scripts.gap_detector import detect_gap
from admin_scripts.job_dispatcher import cancel_job, enqueue_or_join
from admin_scripts.models import ComputationJob
from admin_scripts.scenario_utils import stats_for_scenario
from django.apps import apps
from minitool.models import ChangeRecord


def staff_required(view_func):
    """Decorator that checks if the authenticated user is a staff member."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("You do not have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return wrapper


def _resolve_value_source(value_source):
    """Resolve a catalog value_source dict to a list of string values.

    For queryset sources, queries the model and returns str() of each instance.
    For static sources, returns the values list as strings.
    """
    kind = value_source.get("kind", "")
    if kind == "queryset":
        model_name = value_source.get("model", "")
        try:
            model = apps.get_model("api", model_name)
            return [str(obj) for obj in model.objects.all().order_by("pk")]
        except LookupError:
            return []
    elif kind == "static":
        return [str(v) for v in value_source.get("values", [])]
    return []


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
    {
        "name": "Jobs",
        "url": "jobs-list",
        "description": "View computation job status and history.",
    },
]


def _jobs_list_context(request):
    """Build shared context for the jobs list (full page + HTMX partial)."""
    valid_statuses = {s.value for s in ComputationJob.Status}
    raw_status = request.GET.get("status", "") or ""
    selected_status = raw_status if raw_status in valid_statuses else ""

    base_qs = ComputationJob.objects.filter(requested_by=request.user)

    status_counts = dict(
        base_qs.values_list("status")
        .annotate(c=Count("id"))
        .values_list("status", "c")
    )

    if selected_status:
        jobs = base_qs.filter(status=selected_status).order_by("-created_at")
    else:
        jobs = base_qs.order_by("-created_at")

    active_count = status_counts.get("pending", 0) + status_counts.get("running", 0)
    total_count = sum(status_counts.values())

    tab_defs = [
        ("all", "All", total_count),
        ("pending", "Pending", status_counts.get("pending", 0)),
        ("running", "Running", status_counts.get("running", 0)),
        ("completed", "Completed", status_counts.get("completed", 0)),
        ("failed", "Failed", status_counts.get("failed", 0)),
        ("cancelled", "Cancelled", status_counts.get("cancelled", 0)),
    ]
    filter_tabs = []
    for key, label, count in tab_defs:
        # Always show "All"; always show the currently selected status tab;
        # otherwise, only show tabs where count > 0.
        if key == "all" or count > 0 or key == selected_status:
            filter_tabs.append({"key": key, "label": label, "count": count})

    return {
        "jobs": jobs,
        "status_counts": status_counts,
        "active_count": active_count,
        "selected_status": selected_status,
        "filter_tabs": filter_tabs,
        "total_count": total_count,
    }


@login_required(login_url="/admin/login/")
@staff_required
def jobs_list(request):
    """Persistent jobs panel showing all ComputationJobs for the current user."""
    return render(request, "admin_scripts/jobs_list.html", _jobs_list_context(request))


@login_required(login_url="/admin/login/")
@staff_required
def jobs_list_partial(request):
    """HTMX partial endpoint that renders only the jobs list body."""
    return render(
        request,
        "admin_scripts/partials/jobs_table.html",
        _jobs_list_context(request),
    )


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
                "unit": post_data.get(f"{prefix}change-{index}-unit", ""),
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


def _extract_change_key_info(data, suffix):
    """Extract value and index from change-prefixed keys in request data.

    Handles both old format (change-N-suffix) and new format (scenario-S-change-N-suffix).

    Args:
        data: dict-like request.GET or request.POST
        suffix: the field suffix to look for (e.g. "module_type", "field")

    Returns:
        Tuple of (value, change_index, full_prefix) or None if not found.
        full_prefix includes everything up to and including the trailing dash,
        e.g. "scenario-1-change-3-" or "change-2-".
    """
    pattern = re.compile(r"^((?:scenario-\d+-)?change-(\d+)-)" + re.escape(suffix) + r"$")
    for key, value in data.items():
        m = pattern.match(key)
        if m and value:
            return (value, m.group(2), m.group(1))
    return None



@login_required(login_url="/admin/login/")
@staff_required
def compile_scenarios(request):
    catalog = get_catalog()
    module_types = [m.module_type for m in catalog]

    # Render one empty scenario tab on GET
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


# ---------------------------------------------------------------------------
# htmx partial endpoints
# ---------------------------------------------------------------------------

@login_required(login_url="/admin/login/")
@staff_required
def htmx_module_types(request):
    catalog = get_catalog()
    return render(
        request,
        "admin_scripts/partials/module_type_options.html",
        {"modules": catalog},
    )


@login_required(login_url="/admin/login/")
@staff_required
def htmx_fields(request):
    result = _extract_change_key_info(request.GET, "module_type")
    if not result:
        return render(
            request,
            "admin_scripts/partials/field_select.html",
            {"has_module_type": False},
        )

    module_type, index, prefix = result
    id_prefix = prefix.rstrip("-")

    catalog = get_catalog()
    catalog_module = next((m for m in catalog if m.module_type == module_type), None)
    if catalog_module is None:
        fields = []
    else:
        fields = [f.field_name for f in catalog_module.fields]
    values_url = reverse("admin_scripts:htmx-values")
    return render(
        request,
        "admin_scripts/partials/field_select.html",
        {
            "has_module_type": True,
            "prefix": prefix,
            "id_prefix": id_prefix,
            "index": index,
            "values_url": values_url,
            "fields": fields,
        },
    )


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

    catalog = get_catalog()
    catalog_module = next((m for m in catalog if m.module_type == module_type), None)
    catalog_field = None
    if catalog_module:
        catalog_field = next((f for f in catalog_module.fields if f.field_name == field), None)

    if catalog_field:
        values = _resolve_value_source(catalog_field.value_source)
    else:
        values = []

    # Both from and to share the same value pool
    from_values = values
    to_values = values

    return render(request, "admin_scripts/partials/value_options.html", {
        "index": index,
        "prefix": prefix,
        "from_values": from_values,
        "to_values": to_values,
    })


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

    catalog = get_catalog()
    module_types = [m.module_type for m in catalog]
    return render(request, "admin_scripts/partials/change_fieldset.html", {
        "index": index,
        "prefix": prefix,
        "id_prefix": id_prefix,
        "scenario_index": scenario_index,
        "module_types": module_types,
    })


@login_required(login_url="/admin/login/")
@staff_required
def htmx_add_scenario(request):
    try:
        scenario_index = int(request.GET.get("index", 1))
    except (ValueError, TypeError):
        scenario_index = 1

    catalog = get_catalog()
    module_types = [m.module_type for m in catalog]

    default_prefix = f"scenario-{scenario_index}-change-0-"
    default_id_prefix = f"scenario-{scenario_index}-change-0"

    # The scenario_tab partial is an OOB swap carrier — htmx unwraps the inner
    # <button> into #scenario-tabs via beforeend.
    return render(
        request,
        "admin_scripts/partials/scenario_add.html",
        {
            "scenario_index": scenario_index,
            "scenario_number": scenario_index + 1,
            "module_types": module_types,
            "default_prefix": default_prefix,
            "default_id_prefix": default_id_prefix,
            "active": True,
        },
    )


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
        stats = stats_for_scenario(changes, global_filters)

        if stats["count"] == 0:
            # Check if any of the changes are gaps (no data computed yet)
            gaps = []
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

    return render(request, "admin_scripts/partials/scenario_results.html", context)


@login_required(login_url="/admin/login/")
@staff_required
def htmx_enqueue_job(request):
    if request.method != "POST":
        return HttpResponse("POST required", status=405)

    module_type = request.POST.get("module_type", "")
    attribute = request.POST.get("attribute", "")
    from_value = request.POST.get("from_value", "")
    to_value = request.POST.get("to_value", "")

    if not all([module_type, attribute, from_value, to_value]):
        return HttpResponse(
            '<div class="text-red-600 text-sm">Missing parameters.</div>'
        )

    job = enqueue_or_join(
        user=request.user,
        module_type=module_type,
        attribute=attribute,
        from_value=from_value,
        to_value=to_value,
    )

    return render(request, "admin_scripts/partials/job_enqueued.html", {
        "job": job,
    })


@login_required(login_url="/admin/login/")
@staff_required
def htmx_job_status(request):
    """Poll endpoint for job status updates."""
    job_id = request.GET.get("job_id")
    if not job_id:
        return HttpResponse("")

    try:
        job = ComputationJob.objects.get(pk=job_id)
    except ComputationJob.DoesNotExist:
        return HttpResponse('<span class="text-red-500">Job not found</span>')

    return render(request, "admin_scripts/partials/job_status.html", {"job": job})


@login_required(login_url="/admin/login/")
@staff_required
@require_POST
def htmx_cancel_job(request):
    """Cancel a pending or running computation job via HTMX."""
    job_id = request.POST.get("job_id")
    job = get_object_or_404(ComputationJob, pk=job_id)
    cancel_job(job.pk)
    job.refresh_from_db()
    return render(request, "admin_scripts/partials/job_status.html", {"job": job})


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

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
    summary_rows = []
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
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

        if summary_rows:
            pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
            writer.book.move_sheet("Summary", offset=-len(writer.book.sheetnames) + 1)

    buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scenarios_{timestamp}.xlsx"

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
