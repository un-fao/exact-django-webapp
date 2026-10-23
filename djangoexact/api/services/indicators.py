"""Project indicators: a registry of indicator groups computed from a project's results.

A group is a function ``IndicatorContext -> {"indicators": [...], "data": {...}} | None``
registered with ``@register_group``. Groups live in their own modules
(``api/services/indicators_<topic>.py``) and are imported from ``ApiConfig.ready``,
so adding one never edits this file. Returning None, or no indicators, marks the
group unavailable for the project (the frontend shows an empty state).

Labels are lazy translations; they resolve in the language active when the
response or report is rendered.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("console")


@dataclass(frozen=True)
class IndicatorGroup:
    id: str
    label: Any
    order: int
    compute: Callable[["IndicatorContext"], dict | None]


_GROUPS: dict[str, IndicatorGroup] = {}


def register_group(group_id: str, label: Any, *, order: int = 100):
    """Register an indicator group. ``order`` sets its position in the response and reports."""

    def decorator(fn):
        _GROUPS[group_id] = IndicatorGroup(group_id, label, order, fn)
        return fn

    return decorator


def registered_groups() -> list[IndicatorGroup]:
    return sorted(_GROUPS.values(), key=lambda g: (g.order, g.id))


def indicator(
    indicator_id: str,
    label: Any,
    unit: str,
    *,
    start: float | None = None,
    with_: float | None = None,
    without: float | None = None,
    value: float | None = None,
    target: float | None = None,
    series: dict | None = None,
) -> dict:
    """One indicator row. ``series`` is ``{"years": [...], "with": [...], "without": [...]}``."""
    return {
        "id": indicator_id,
        "label": label,
        "unit": unit,
        "start": start,
        "with": with_,
        "without": without,
        "value": value,
        "target": target,
        "series": series,
    }


@dataclass
class IndicatorContext:
    """What a group gets: the project and the computed results of its ready activities.

    ``activity_results`` are ``api.reports.data_types.ActivityResult`` objects; each
    carries its Activity (``_activity``) and its module reports with the
    with/without emission sets, read from the module result cache when valid.
    """

    project: Any
    activity_results: list
    skipped_activities: list = field(default_factory=list)
    _memo: dict = field(default_factory=dict, repr=False)

    @property
    def duration(self) -> int:
        return self.project.implementation_years + self.project.capitalization_years

    @property
    def start_year(self) -> int:
        return self.project.start_year_of_activities

    def memo(self, key: str, fn: Callable[[], Any]) -> Any:
        """Share one expensive read between groups of the same request."""
        if key not in self._memo:
            self._memo[key] = fn()
        return self._memo[key]


def build(project, activity_results: list, skipped_activities: list | None = None) -> dict:
    ctx = IndicatorContext(project, activity_results, list(skipped_activities or []))
    groups = []
    for group in registered_groups():
        try:
            out = group.compute(ctx) or {}
        except Exception:
            # An indicator bug must not take down the results page or the report.
            logger.exception(f"Indicator group {group.id} failed for project {project.pk}")
            out = {}
        indicators = out.get("indicators") or []
        groups.append({
            "id": group.id,
            "label": group.label,
            "available": bool(indicators),
            "indicators": indicators,
            "data": out.get("data"),
        })
    return {
        "project": project.pk,
        "start_year": ctx.start_year,
        "skipped_activities": ctx.skipped_activities,
        "groups": groups,
    }


def compute_project_indicators(project) -> dict:
    """Indicators for every ready activity of the project, reusing cached module results."""
    from api.reports.base import BaseActivityReport, BaseProjectReport

    activities = list(project.activities.filter(is_b_intact=False))
    project_report = BaseProjectReport(project, activities)
    results, skipped = [], []
    for activity in activities:
        modules = activity.cache_modules()
        if not modules:
            continue
        if not all(m.is_ready() for m in modules):
            skipped.append({"id": activity.pk, "name": activity.name})
            continue
        try:
            results.append(BaseActivityReport(project_report, activity).compute())
        except Exception as e:
            # Calculators raise NotReadyError, ValidationError or plain Exception on
            # incomplete data; one such activity must not hide the others' indicators.
            logger.warning(f"Indicators skip activity {activity.pk}: {e}")
            skipped.append({"id": activity.pk, "name": activity.name})
    project_report.cache_batch.flush()
    return build(project, results, skipped)
