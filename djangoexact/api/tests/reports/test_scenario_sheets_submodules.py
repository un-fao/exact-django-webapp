"""Scenario sheets for modules that build their Results rows per submodule.

Energy, Input, Irrigation, Transport, Processing and Settlement split their
rows by submodule (fuel type, input type, road vs building), so they read each
submodule's emission sets instead of ``self.emissions_set``. Those rows used to
always come from the submodule balance, so "Results - With" and
"Results - Without" showed the balance for them while the activity and project
totals showed the real fluxes. Project 2549's transport module made it obvious:
0 with, 233 without, and both sheets showed -233.

Run with:
    python manage.py test api.tests.reports.test_scenario_sheets_submodules
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import api.models as api_models
from api.reports.land import SettlementReport
from api.reports.modules import IrrigationReport, TransportReport

DURATION = 3
BALANCE = [-233.3] * DURATION
WITH = [0.0] * DURATION
WITHOUT = [233.3] * DURATION


def _sets(activity: str) -> dict:
    def entry(values):
        return [{"activity": activity, "gas_type": {"name": "CO2"}, "emissions": [{"value": v} for v in values]}]

    return {"balance": entry(BALANCE), "total_w": entry(WITH), "total_wo": entry(WITHOUT)}


def _report(cls, module, sets):
    activity_report = Mock()
    activity_report.project_report.duration = DURATION
    with patch.object(cls, "__post_init__", lambda self: None):
        report = cls(module=module, activity_report=activity_report)
    report.emissions_set = sets["balance"]
    report.emissions_set_w = sets["total_w"]
    report.emissions_set_wo = sets["total_wo"]
    report._from_cache = True
    return report


def _frozen(sets):
    return patch("api.services.finalization.frozen_result", return_value=SimpleNamespace(results_by_activity_by_gas=sets))


class TestSubmoduleScenarioRows(unittest.TestCase):
    def assert_scenario_rows(self, result, label):
        expected = {"balance": BALANCE, "w": WITH, "wo": WITHOUT}
        rows = {"balance": result.result_rows, "w": result.result_rows_w, "wo": result.result_rows_wo}
        totals = {"balance": result.total_emissions, "w": result.total_emissions_w, "wo": result.total_emissions_wo}
        for scenario, scenario_rows in rows.items():
            with self.subTest(scenario=scenario):
                row = next(r for r in scenario_rows if r.label == label)
                self.assertEqual(row.yearly_values, expected[scenario])
                # The activity row on each sheet is the sum of module totals, so the rows must add up to it.
                row_sum = [sum(year) for year in zip(*(r.yearly_values for r in scenario_rows))]
                self.assertEqual(row_sum, totals[scenario])

    def test_transport_cached_entry(self):
        sets = _sets("Fuel")
        module = Mock(submodules=[Mock(cached_results_by_activity_by_gas=sets)])
        report = _report(TransportReport, module, sets)
        with patch.object(TransportReport, "_inventory_items_from_module", return_value=[]):
            result = report.compute_with_scenarios()
        self.assert_scenario_rows(result, "CO2 from fuel combustion")

    def test_transport_calculated_entry(self):
        sets = _sets("Fuel")
        module = Mock(submodules=[Mock(cached_results_by_activity_by_gas=None)])
        report = _report(TransportReport, module, sets)
        with _frozen(sets), patch("api.calculators.TransportEntryCalculator"), \
                patch.object(TransportReport, "_inventory_items_from_module", return_value=[]):
            result = report.compute_with_scenarios()
        self.assert_scenario_rows(result, "CO2 from fuel combustion")

    def test_irrigation(self):
        sets = _sets("New Irrigation")
        module = MagicMock(submodules=[MagicMock()])
        report = _report(IrrigationReport, module, sets)
        with _frozen(sets), patch("api.calculators.IrrigationSystemCalculator"), \
                patch.object(IrrigationReport, "_inventory_items_from_module", return_value=[]):
            result = report.compute_with_scenarios()
        self.assert_scenario_rows(result, "CO2-eq from other infrastructure")

    def test_settlement_roads(self):
        sets = _sets("Roads")
        module = MagicMock(submodules=[MagicMock(spec=api_models.Road)])
        report = _report(SettlementReport, module, sets)
        with _frozen(sets), patch("api.calculators.RoadCalculator"), \
                patch.object(SettlementReport, "_inventory_items_from_module", return_value=[]):
            result = report.compute_with_scenarios()
        self.assert_scenario_rows(result, "CO2-eq from roads")

    def test_each_submodule_is_computed_once_for_all_three_sheets(self):
        sets = _sets("Fuel")
        module = Mock(submodules=[Mock(cached_results_by_activity_by_gas=None)])
        report = _report(TransportReport, module, sets)
        with _frozen(sets) as frozen, patch("api.calculators.TransportEntryCalculator"), \
                patch.object(TransportReport, "_inventory_items_from_module", return_value=[]):
            report.compute_with_scenarios()
        self.assertEqual(frozen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
