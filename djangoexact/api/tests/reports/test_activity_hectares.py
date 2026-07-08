"""Regression tests for activity-level cumulative hectares aggregation.

A land-use-change (LUC) activity carries multiple land modules that describe the
SAME physical parcel: a "with" module and a "without" module over the same
hectares. ``BaseActivityReport.compute()`` must count that area only once,
otherwise the Excel "Cumulative Hectares Impacted" row reports double.

Guards against regression of exact-django-webapp-gz3 — the March-2026 reports
refactor reintroduced the double-count that ``api/models.py`` had already fixed
in ``Activity.get_land_modules_area()`` (Nov 2025).

Run with:
    python manage.py test api.tests.reports.test_activity_hectares
"""
from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock, patch

from api.reports.base import BaseActivityReport
from api.reports.data_types import ModuleResult

logging.disable(logging.DEBUG)


def _module_result(units_w, units_wo, duration):
    return ModuleResult(
        title="Land",
        metadata_section_title="Land",
        result_rows=[],
        total_emissions=[0.0] * duration,
        units_breakdown_w=units_w,
        units_breakdown_wo=units_wo,
    )


def _land_module(*, is_with, is_without, result):
    from api.models import LandModule
    module = MagicMock(spec=LandModule)
    module.is_with.return_value = is_with
    module.is_without.return_value = is_without
    module._result = result
    return module


def _coastal_module(*, is_with, is_without, result):
    # CoastalWetland is a Module, NOT a LandModule, so the single-count guard
    # must not apply to it (mirrors the separate branch in get_land_modules_area).
    from api.models import CoastalWetland
    module = MagicMock(spec=CoastalWetland)
    module.is_with.return_value = is_with
    module.is_without.return_value = is_without
    module._result = result
    return module


class _FakeReport:
    """Stand-in module report: returns the module's preset ModuleResult."""

    def __init__(self, module, activity_report):
        self._module = module

    def compute(self):
        return self._module._result


def _activity(modules):
    activity = MagicMock(
        modules=modules,
        climate_t2=None,
        moisture_t2=None,
        soil_type_t2=None,
        duration_t2=None,
        start_year_t2=None,
        last_year_of_accounting_t2=None,
        soc_t2=None,
    )
    activity.name = "Act"
    return activity


class TestActivityHectaresNoDoubleCount(unittest.TestCase):
    DURATION = 3

    def _compute(self, modules):
        project_report = MagicMock(duration=self.DURATION)
        activity = _activity(modules)
        report = BaseActivityReport(project_report=project_report, activity=activity)
        with patch("api.reports.registry.get_report_class", return_value=_FakeReport):
            return report.compute()

    def test_luc_counts_hectares_once(self):
        # LUC: a "with" module and a "without" module over the same 10 ha parcel.
        area = [10.0, 10.0, 10.0]
        with_mod = _land_module(
            is_with=True, is_without=False,
            result=_module_result(area, area, self.DURATION),
        )
        without_mod = _land_module(
            is_with=False, is_without=True,
            result=_module_result(area, area, self.DURATION),
        )

        result = self._compute([with_mod, without_mod])

        # Single-count: 10 ha, NOT 20 ha.
        self.assertEqual(result.total_hectares_yearly, [10.0, 10.0, 10.0])

    def test_luc_counts_once_regardless_of_module_order(self):
        area = [10.0, 10.0, 10.0]
        with_mod = _land_module(
            is_with=True, is_without=False,
            result=_module_result(area, area, self.DURATION),
        )
        without_mod = _land_module(
            is_with=False, is_without=True,
            result=_module_result(area, area, self.DURATION),
        )

        result = self._compute([without_mod, with_mod])

        self.assertEqual(result.total_hectares_yearly, [10.0, 10.0, 10.0])

    def test_non_luc_single_module_unchanged(self):
        # No LUC: Module.is_with() and is_without() both return True; one module.
        area = [7.5, 7.5, 7.5]
        mod = _land_module(
            is_with=True, is_without=True,
            result=_module_result(area, area, self.DURATION),
        )

        result = self._compute([mod])

        self.assertEqual(result.total_hectares_yearly, [7.5, 7.5, 7.5])

    def test_coastal_wetland_and_land_module_both_counted(self):
        # CoastalWetland is NOT a LandModule; get_land_modules_area() counts it
        # separately from the first LandModule, so both must be counted. The
        # LandModule single-count guard must not swallow the CoastalWetland.
        coastal = _coastal_module(
            is_with=True, is_without=True,
            result=_module_result([4.0, 4.0, 4.0], [4.0, 4.0, 4.0], self.DURATION),
        )
        land = _land_module(
            is_with=True, is_without=True,
            result=_module_result([6.0, 6.0, 6.0], [6.0, 6.0, 6.0], self.DURATION),
        )

        result = self._compute([coastal, land])

        # 4 ha coastal + 6 ha land = 10 ha.
        self.assertEqual(result.total_hectares_yearly, [10.0, 10.0, 10.0])

    def test_land_modules_single_counted_alongside_coastal(self):
        # A LUC pair of LandModules (same 6 ha parcel) plus a distinct 4 ha
        # CoastalWetland: land counted once, coastal added -> 10 ha, not 16.
        land_w = _land_module(
            is_with=True, is_without=False,
            result=_module_result([6.0, 6.0, 6.0], [6.0, 6.0, 6.0], self.DURATION),
        )
        land_wo = _land_module(
            is_with=False, is_without=True,
            result=_module_result([6.0, 6.0, 6.0], [6.0, 6.0, 6.0], self.DURATION),
        )
        coastal = _coastal_module(
            is_with=True, is_without=True,
            result=_module_result([4.0, 4.0, 4.0], [4.0, 4.0, 4.0], self.DURATION),
        )

        result = self._compute([land_w, land_wo, coastal])

        self.assertEqual(result.total_hectares_yearly, [10.0, 10.0, 10.0])


if __name__ == "__main__":
    unittest.main()
