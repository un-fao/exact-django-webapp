"""Public API for the reports package.

Usage:
    from api.reports import compute_project_result, generate_excel_report

    result = compute_project_result(project)
    excel_bytes = generate_excel_report(project)
"""
from __future__ import annotations

from .base import BaseProjectReport, NotReadyError
from .data_types import ProjectResult
from .renderer import ExcelRenderer


def compute_project_result(project, activities=None) -> ProjectResult:
    """Compute and return the full ProjectResult for *project*.

    Args:
        project: api_models.Project instance.
        activities: Optional queryset / list of Activity instances.
            If None, all activities belonging to the project are used.

    Returns:
        A ProjectResult containing all computed emissions, shadow prices,
        inventory items, and aggregated totals.

    Raises:
        NotReadyError: If any module cannot be calculated (e.g. missing data).
    """
    return BaseProjectReport(project, activities).compute()


def generate_excel_report(project, activities=None) -> bytes:
    """Compute the project result and render it as Excel bytes.

    Args:
        project: api_models.Project instance.
        activities: Optional queryset / list of Activity instances.

    Returns:
        Excel file contents as bytes.

    Raises:
        NotReadyError: If any module cannot be calculated.
    """
    if activities is None:
        activities = project.activities.filter(is_b_intact=False)
    else:
        # Keep the caller's Activity instances (memoized module lists from
        # the readiness pre-pass) instead of re-cloning the queryset, which
        # would re-query and discard the memo. is_b_intact is a non-nullable
        # BooleanField(default=False), so this Python-level exclusion is
        # behavior-identical to the ORM filter used in the None branch above.
        activities = [a for a in activities if not a.is_b_intact]
    result = compute_project_result(project, activities)
    return ExcelRenderer(result).render()


__all__ = [
    "compute_project_result",
    "generate_excel_report",
    "ProjectResult",
    "NotReadyError",
]
