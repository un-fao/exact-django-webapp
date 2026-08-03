import io
import re
from datetime import datetime
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.urls import reverse

from admin_scripts.catalog import get_catalog
from admin_scripts.excel_export import build_scenarios_workbook
from admin_scripts.gap_detector import detect_gap
from admin_scripts.job_dispatcher import cancel_job, enqueue_for_test_run, enqueue_or_join
from admin_scripts.models import ComputationJob, ModuleTestRun
from admin_scripts.scenario_utils import stats_for_scenario
from admin_scripts.test_planner import _resolve_value_source, plan_module_tests
from api.models import Climate, Moisture, SoilType
from minitool.models import ChangeRecord


def staff_required(view_func):
    """Decorator that checks if the authenticated user is a staff member."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("You do not have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return wrapper


def _reference_filter_options() -> dict[str, list[str]]:
    """Canonical climate/moisture/soil_type override options as flat name lists.

    Sourced from the reference tables (api.Climate / api.Moisture /
    api.SoilType), active-filtered and ordered by name. These enumerate the
    full option set known to the system. They are deliberately NOT derived from
    minitool.ChangeRecord distinct values: ChangeRecord rows are computed on
    demand, so a data-derived list would omit any valid option that has not yet
    been computed (product-owner decision, 2026-07-13). Note the differing
    active-flag field names: Climate/Moisture use ``is_active``, SoilType uses
    ``active``.
    """
    return {
        "climates": list(
            Climate.objects.filter(is_active=True)
            .order_by("name").values_list("name", flat=True)
        ),
        "moistures": list(
            Moisture.objects.filter(is_active=True)
            .order_by("name").values_list("name", flat=True)
        ),
        "soil_types": list(
            SoilType.objects.filter(active=True)
            .order_by("name").values_list("name", flat=True)
        ),
    }


def _change_record_filter_choices(qs=None):
    """Filter option lists for the scenario form.

    Returns a dict with keys ``regions`` (used by the global filter) and
    ``climates``/``moistures``/``soil_types`` (used by the per-change filter
    block). Shared by every render path that emits the scenario form so
    dropdowns are populated at initial server-render and don't depend on the
    deferred htmx_filters swap firing first.

    ``regions`` stays ChangeRecord-derived (distinct non-empty stored values);
    pass ``qs`` to scope it. The per-change climate/moisture/soil_type overrides
    come from the canonical reference tables via ``_reference_filter_options``,
    so every valid option is offered regardless of what has been computed into
    ChangeRecord. ``qs`` therefore no longer narrows those three lists.
    """
    if qs is None:
        qs = ChangeRecord.objects.all()
    return {
        "regions": list(
            qs.exclude(region="").values_list("region", flat=True).distinct().order_by("region")
        ),
        **_reference_filter_options(),
    }


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
    {
        "name": "Test All Modules",
        "url": "test-modules",
        "description": "Systematically run a capped computation for every module/field in the catalog and report success/failure per pair.",
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
            for col in ("climate", "moisture", "soil_type"):
                values = post_data.getlist(f"{prefix}change-{index}-filter-{col}")
                if values:
                    change["filters"][col] = values
            changes.append(change)
        index += 1
    return changes


def _parse_global_filters(post_data):
    """Parse global filter fields from POST data.

    Region is the only global filter; climate/moisture/soil_type are scoped
    per-change.
    """
    filters = {}
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

    # Populate the global region filter and the per-change
    # climate/moisture/soil_type dropdowns from distinct values in ChangeRecord.
    # Without these the dropdowns render as empty <select>s on initial load.
    choices = _change_record_filter_choices()

    context = {
        "module_types": module_types,
        "scenarios": scenarios,
        **choices,
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
        # Pass module_type/field so the resolver consults MODULE_CONFIGS'
        # filtered queryset (e.g. PerennialCropland.land_use_type is limited
        # to perennial land use types). Without these args the dropdown lists
        # values the test runner would later reject as out-of-range.
        values = _resolve_value_source(
            catalog_field.value_source, module_type, field,
        )
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

    # The climate/moisture/soil_type overrides are the canonical reference set
    # and no longer narrow by module_type (product-owner decision, 2026-07-13).
    # This endpoint is kept so the selects are (re)populated when a module_type
    # is first chosen; it simply re-serves the full reference options rather than
    # a ChangeRecord-scoped subset.
    choices = _reference_filter_options()

    return render(request, "admin_scripts/partials/filter_options.html", {
        "index": index,
        "prefix": prefix,
        "climates": choices["climates"],
        "moistures": choices["moistures"],
        "soil_types": choices["soil_types"],
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
    choices = _change_record_filter_choices()
    return render(request, "admin_scripts/partials/change_fieldset.html", {
        "index": index,
        "prefix": prefix,
        "id_prefix": id_prefix,
        "scenario_index": scenario_index,
        "module_types": module_types,
        "climates": choices["climates"],
        "moistures": choices["moistures"],
        "soil_types": choices["soil_types"],
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
    choices = _change_record_filter_choices()

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
            "climates": choices["climates"],
            "moistures": choices["moistures"],
            "soil_types": choices["soil_types"],
        },
    )


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

        # Per-change so mixed valid+gap scenarios surface both panels.
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
        # Hide stats only when every change is a gap (preserves prior UX).
        if stats["count"] > 0 or not gaps:
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
    """Empty stats dict in the same shape ``stats_for_scenario`` returns.
    Used by ``htmx_run_scenario`` when no changes were provided, so the
    Compare tab always sees a stable schema.
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

    now = datetime.now()
    requested_by = request.user.get_username() if request.user.is_authenticated else None
    workbook_bytes = build_scenarios_workbook(
        scenarios,
        global_filters,
        requested_by=requested_by,
        now=now,
    )

    filename = f"scenarios_{now.strftime('%Y%m%d_%H%M%S')}.xlsx"
    return FileResponse(
        io.BytesIO(workbook_bytes),
        as_attachment=True,
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Test All Modules
# ---------------------------------------------------------------------------

TERMINAL_STATUSES = {
    ComputationJob.Status.COMPLETED,
    ComputationJob.Status.FAILED,
    ComputationJob.Status.CANCELLED,
}


def _summarize_completed_job(job):
    """Compute a tiny count/mean summary for a completed test-run job.

    Returns a dict with ``count`` (int) and ``mean_str`` (formatted string
    or empty). Preformatting in Python keeps the template free of
    None-comparison gymnastics and lets ``mean=0.0`` render as "0.00"
    rather than being filtered out by template truthiness.
    """
    change = {
        "module_type": job.module_type,
        "start": {"field": job.attribute, "value": job.from_value},
        "end": {"field": job.attribute, "value": job.to_value},
        "filters": {},
        "unit": "",
    }
    stats = stats_for_scenario([change], {})
    mean = stats["mean"]
    mean_str = f"{mean:.2f}" if mean is not None else ""
    return {"count": stats["count"], "mean_str": mean_str}


def _build_run_rows(run):
    """Build the per-job rows shown on the detail page, grouped by module.

    Returns a tuple ``(groups, counts)`` where:
      - groups: ``[{"module_type": str, "rows": [row, ...]}, ...]`` in catalog order
      - counts: dict with totals for the summary chips
    """
    catalog = get_catalog()
    module_order = [m.module_type for m in catalog]

    jobs_by_module: dict[str, list] = {m: [] for m in module_order}
    counts = {
        "total": 0, "pending": 0, "running": 0,
        "completed": 0, "failed": 0, "cancelled": 0,
        "skipped": len(run.skipped),
    }
    for job in run.jobs.all().order_by("module_type", "attribute"):
        summary = None
        if job.status == ComputationJob.Status.COMPLETED:
            summary = _summarize_completed_job(job)
        jobs_by_module.setdefault(job.module_type, []).append({
            "job": job,
            "summary": summary,
        })
        counts["total"] += 1
        counts[job.status] = counts.get(job.status, 0) + 1

    skipped_by_module: dict[str, list] = {m: [] for m in module_order}
    for entry in run.skipped:
        skipped_by_module.setdefault(entry["module_type"], []).append(entry)

    groups = []
    for module_type in module_order:
        rows = jobs_by_module.get(module_type, [])
        skipped = skipped_by_module.get(module_type, [])
        if rows or skipped:
            groups.append({
                "module_type": module_type,
                "rows": rows,
                "skipped": skipped,
            })
    # Any unexpected module names (legacy data) tacked on at the end.
    for module_type, rows in jobs_by_module.items():
        if module_type not in module_order and rows:
            groups.append({
                "module_type": module_type, "rows": rows, "skipped": [],
            })

    return groups, counts


def _run_is_complete(run) -> bool:
    """A run is complete iff it has at least one job and all jobs are terminal."""
    statuses = list(run.jobs.values_list("status", flat=True))
    if not statuses:
        # No jobs at all (every field was skipped): treat as complete immediately.
        return True
    return all(s in TERMINAL_STATUSES for s in statuses)


@login_required(login_url="/admin/login/")
@staff_required
def test_modules(request):
    """Landing page: run button + history of the user's recent test runs."""
    if request.method == "POST":
        catalog = get_catalog()
        planned, skipped = plan_module_tests(catalog)

        with transaction.atomic():
            run = ModuleTestRun.objects.create(requested_by=request.user)
            new_jobs = []
            for entry in planned:
                job = enqueue_for_test_run(
                    user=request.user,
                    run_id=run.id,
                    module_type=entry["module_type"],
                    attribute=entry["field_name"],
                    from_value=entry["from_value"],
                    to_value=entry["to_value"],
                    max_rows=100,
                )
                new_jobs.append(job)
            if new_jobs:
                run.jobs.add(*new_jobs)
            run.skipped = skipped
            run.save(update_fields=["skipped"])

        return redirect("admin_scripts:test-modules-detail", run_id=run.id)

    recent_runs = (
        ModuleTestRun.objects
        .filter(requested_by=request.user)
        .order_by("-created_at")[:20]
    )
    return render(
        request,
        "admin_scripts/scripts/test_modules.html",
        {"recent_runs": recent_runs},
    )


@login_required(login_url="/admin/login/")
@staff_required
def test_modules_detail(request, run_id):
    run = get_object_or_404(
        ModuleTestRun, pk=run_id, requested_by=request.user,
    )
    groups, counts = _build_run_rows(run)
    is_complete = _run_is_complete(run)
    return render(
        request,
        "admin_scripts/scripts/test_modules_detail.html",
        {
            "run": run,
            "groups": groups,
            "counts": counts,
            "is_complete": is_complete,
        },
    )


@login_required(login_url="/admin/login/")
@staff_required
def test_modules_status(request, run_id):
    """HTMX-polled status partial. Stamps completed_at when all jobs are terminal."""
    run = get_object_or_404(
        ModuleTestRun, pk=run_id, requested_by=request.user,
    )
    is_complete = _run_is_complete(run)
    if is_complete and run.completed_at is None:
        run.completed_at = timezone.now()
        run.save(update_fields=["completed_at"])

    groups, counts = _build_run_rows(run)
    return render(
        request,
        "admin_scripts/partials/test_modules_results.html",
        {
            "run": run,
            "groups": groups,
            "counts": counts,
            "is_complete": is_complete,
        },
    )
