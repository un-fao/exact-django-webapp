"""Frozen results for finalized projects.

A finalized project's results must never change, even when a later release fixes the calculator
or the reference data. Results are therefore snapshotted into ``FinalizedModuleResult`` when the
project is finalized, and every reader (results API, public API, reports) serves finalized
projects from that snapshot only. See docs/decision_logs/2026-10-19-frozen-finalized-results.md.
"""

import logging
from collections import Counter
from collections.abc import Iterator

import numpy as np
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from djangoexact import __version__ as APP_VERSION
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes

log = logging.getLogger("console")


class FinalizationError(Exception):
    """A module of the project cannot be calculated, so its results cannot be frozen."""


class FrozenResultMissingError(Exception):
    """A finalized project has a ready module without a frozen result."""


def _models():
    # api.models imports this module inside Project.save, so the import must be deferred.
    from api import models

    return models


def iter_result_modules(project) -> Iterator:
    for activity in project.activities.all():
        for module in activity.modules:
            if not module:
                continue
            yield module
            for submodule in getattr(module, "submodules", None) or []:
                yield submodule


def is_ready_for_results(module) -> bool:
    """Same readiness rule the results endpoint applies before calculating."""
    if isinstance(module, _models().LandUseChange):
        return all(m.is_ready() for m in module.get_modules())
    return bool(module.is_ready())


def _needs_units(module) -> bool:
    # Land reports print hectares per year next to the emissions; only land modules have them.
    return isinstance(module, _models().LandModule)


def compute_module_results(module) -> dict:
    """Calculate a module's results in the shape the cache columns and the results endpoint use."""
    from api.calculators import CalculatorFactory, Result
    from api.serializers import DynamicResultFactory

    try:
        calculator = CalculatorFactory().get_calculator(module)(module)
        result = Result(*calculator.calculate())
    except Exception as e:
        raise Exception(f"Error in {module.__class__.__name__}: {e}") from e

    activity = module.get_activity()
    inventory = calculator.inventory
    computed = {}
    for key, by in (
        ("total", BreakdownTypes.TOTAL),
        ("by_activity", BreakdownTypes.ACTIVITY),
        ("by_gas", BreakdownTypes.GAS),
        ("by_activity_by_gas", BreakdownTypes.ACTIVITY_GAS),
    ):
        data = DynamicResultFactory.create(activity, result.breakdown(by=by), aggregate_by=by).data
        data["inventory"] = inventory.breakdown(by=by)
        computed[key] = data

    computed["units"] = None
    math_w, math_wo = getattr(calculator, "math_w", None), getattr(calculator, "math_wo", None)
    if hasattr(math_w, "hectares_total") and hasattr(math_wo, "hectares_total"):
        computed["units"] = {
            "w": [float(v) for v in np.round(math_w.hectares_total, 2)],
            "wo": [float(v) for v in np.round(math_wo.hectares_total, 2)],
        }
    return computed


def _cache_payload(obj) -> dict | None:
    """The result columns of a module or a historical module row, when they form a usable cache."""
    if obj.last_cached_at is None or (obj.last_modified is not None and obj.last_cached_at <= obj.last_modified):
        return None
    payload = {
        "total": obj.cached_results_total,
        "by_activity": obj.cached_results_by_activity,
        "by_gas": obj.cached_results_by_gas,
        "by_activity_by_gas": obj.cached_results_by_activity_by_gas,
        "units": getattr(obj, "cached_units_breakdown", None),
    }
    # The report pipeline refreshes only by_activity_by_gas, so a cache is usable only when the
    # results endpoint has written all four breakdowns.
    if any(payload[key] is None for key in ("total", "by_activity", "by_gas", "by_activity_by_gas")):
        return None
    return payload


def _row(project, finalized_at, module, payload, source, computed_at, app_version):
    return _models().FinalizedModuleResult(
        project=project,
        finalized_at=finalized_at,
        content_type=ContentType.objects.get_for_model(module.__class__),
        object_id=module.pk,
        results_total=payload["total"],
        results_by_activity=payload["by_activity"],
        results_by_gas=payload["by_gas"],
        results_by_activity_by_gas=payload["by_activity_by_gas"],
        units_breakdown=payload["units"],
        computed_at=computed_at,
        app_version=app_version,
        source=source,
    )


def _must_freeze(module) -> bool | None:
    """True: must be frozen. False: freeze if it calculates (reports calculate submodules whatever
    their status). None: skip, it has no results to show."""
    if is_ready_for_results(module):
        return True
    return False if isinstance(module, _models().Submodule) else None


def _compute_row(project, finalized_at, module, source, required: bool = True):
    try:
        payload = compute_module_results(module)
    except Exception as e:
        if not required:
            return None
        raise FinalizationError(
            f"Results of {module.module_type.name} in activity {module.get_activity().name} cannot be calculated: {e}"
        ) from e
    return _row(project, finalized_at, module, payload, source, timezone.now(), APP_VERSION)


def freeze_project(project) -> int:
    """Snapshot the results of every ready module of a project that is being finalized.

    Reuses the live cache when it is valid and complete, so the frozen numbers are the ones the
    analyst was looking at when finalizing; calculates otherwise. Must run in the same
    transaction that sets ``is_finalized``.
    """
    models = _models()
    finalize = models.FinalizedModuleResult.Source.FINALIZE
    rows = []
    for module in iter_result_modules(project):
        required = _must_freeze(module)
        if required is None:
            continue
        payload = _cache_payload(module)
        if payload is not None and (payload["units"] is not None or not _needs_units(module)):
            rows.append(_row(project, project.finalized_at, module, payload, finalize, module.last_cached_at, None))
        else:
            rows.append(_compute_row(project, project.finalized_at, module, finalize, required))
    rows = [row for row in rows if row is not None]
    models.FinalizedModuleResult.objects.bulk_create(rows)
    freeze_report_data(project, finalize, APP_VERSION)
    return len(rows)


def freeze_report_data(project, source, app_version) -> int:
    """Freeze the report data (parameters, reference names, shadow prices, indicators) of a project.

    Runs after its results snapshot exists. A finalized project must be able to produce its
    report, so any module the report would include that is not ready, or a report that cannot be
    computed, raises FinalizationError.
    """
    from api.reports import NotReadyError
    from api.reports.frozen import capture_report_data, report_data_rows
    from api.reports.registry import get_report_class

    for activity in project.activities.all():
        for module in activity.modules:
            if module and get_report_class(module) is not None and not is_ready_for_results(module):
                raise FinalizationError(
                    f"{module.module_type.name} in activity {activity.name} is not ready. Complete or remove it: "
                    "a finalized project must be able to produce its report."
                )
    try:
        captured = capture_report_data(project)
    except Exception as e:
        # Calculators raise ValidationError (e.g. a missing climate) as well as NotReadyError; either
        # way the project cannot be finalized, and the request must answer 400, not 500.
        if not isinstance(e, NotReadyError):
            log.exception(f"Report data of project {project.pk} could not be captured")
        raise FinalizationError(f"The report of this project cannot be produced: {e}") from e
    rows = report_data_rows(project, captured, source=source, app_version=app_version)
    _models().FinalizedReportData.objects.bulk_create(rows)
    return len(rows)


def restore_report_data(project, dry_run: bool = True) -> Counter:
    """Freeze the report data of an already-finalized project that has none, computing it now.

    No history ever stored report parameters, so they can only be frozen as of today and are
    marked frozen_retroactively. Requires the results snapshot (restore_frozen_results) first.
    """
    models = _models()
    if models.FinalizedReportData.objects.filter(project=project, finalized_at=project.finalized_at).exists():
        return Counter(report_data_already_frozen=1)
    if dry_run:
        return Counter(report_data_frozen_retroactively=1)
    freeze_report_data(project, models.FinalizedModuleResult.Source.RETROACTIVE, APP_VERSION)
    return Counter(report_data_frozen_retroactively=1)


def frozen_result(module):
    """The frozen result of a module of a finalized project, or None when the project is open.

    Raises FrozenResultMissingError when the project is finalized but the module has no snapshot:
    callers must not fall back to calculating, since that would silently unfreeze the results.
    """
    project = module.project
    if not project.is_finalized:
        return None
    row = (
        _models()
        .FinalizedModuleResult.objects.filter(
            content_type=ContentType.objects.get_for_model(module.__class__),
            object_id=module.pk,
            finalized_at=project.finalized_at,
        )
        .first()
    )
    if row is None:
        log.error(f"Finalized project {project.pk} has no frozen result for {module.__class__.__name__} {module.pk}")
        raise FrozenResultMissingError(
            f"The frozen results of {module.module_type.name} in activity {module.get_activity().name} are missing. "
            "They will not be recalculated because the project is finalized; please contact support."
        )
    return row


_BREAKDOWN_KEYS = {
    BreakdownTypes.TOTAL: "total",
    BreakdownTypes.ACTIVITY: "by_activity",
    BreakdownTypes.GAS: "by_gas",
    BreakdownTypes.ACTIVITY_GAS: "by_activity_by_gas",
}


def module_results(module, aggregate_by: BreakdownTypes, use_cache: bool = True):
    """Results of a ready module for the results endpoints, plus the frozen row when they are frozen.

    Finalized projects are served from their snapshot whatever ``use_cache`` says; open projects
    use the live cache and recalculate (and re-cache) when it is stale or bypassed.
    """
    frozen = frozen_result(module)
    if frozen is not None:
        return frozen.results(aggregate_by), frozen

    results = module.get_cached_results(by=aggregate_by) if use_cache else None
    if results is None:
        log.debug(f"Cache is invalid. Calculating results for module {module.pk}")
        computed = compute_module_results(module)
        module.cache_results(computed["total"], computed["by_activity"], computed["by_gas"], computed["by_activity_by_gas"])
        results = computed[_BREAKDOWN_KEYS[aggregate_by]]
    return results, None


def _history_payload(module, finalized_at):
    for row in module.history.filter(history_date__lte=finalized_at).order_by("-history_date", "-history_id").iterator():
        payload = _cache_payload(row)
        if payload is not None:
            return payload, row.last_cached_at
    return None, None


def restore_frozen_results(project, dry_run: bool = True) -> Counter:
    """Freeze an already-finalized project as it stood at ``finalized_at``.

    For projects finalized before snapshots existed. Per ready module, the first usable source wins:
    the live cache if it was written before finalization, else the latest history row at or before
    finalization holding a usable cache, else a calculation now (marked retroactive). Modules that
    already have a snapshot for this finalization are skipped, so the command is re-runnable.
    """
    models = _models()
    Source = models.FinalizedModuleResult.Source
    finalized_at = project.finalized_at
    counts = Counter()
    existing = set(
        models.FinalizedModuleResult.objects.filter(project=project, finalized_at=finalized_at).values_list("content_type_id", "object_id")
    )
    rows = []
    for module in iter_result_modules(project):
        required = _must_freeze(module)
        if required is None:
            counts["skipped_not_ready"] += 1
            continue
        if (ContentType.objects.get_for_model(module.__class__).pk, module.pk) in existing:
            counts["already_frozen"] += 1
            continue

        payload = _cache_payload(module)
        if payload is not None and module.last_cached_at <= finalized_at:
            rows.append(_row(project, finalized_at, module, payload, Source.LIVE_CACHE, module.last_cached_at, None))
            counts[Source.LIVE_CACHE] += 1
            continue

        payload, computed_at = _history_payload(module, finalized_at)
        if payload is not None:
            rows.append(_row(project, finalized_at, module, payload, Source.HISTORY, computed_at, None))
            counts[Source.HISTORY] += 1
            continue

        if dry_run:
            counts[Source.RETROACTIVE] += 1
            continue
        row = _compute_row(project, finalized_at, module, Source.RETROACTIVE, required)
        if row is None:
            counts["skipped_not_calculable_submodule"] += 1
            continue
        rows.append(row)
        counts[Source.RETROACTIVE] += 1

    if not dry_run:
        models.FinalizedModuleResult.objects.bulk_create(rows)
    return counts
