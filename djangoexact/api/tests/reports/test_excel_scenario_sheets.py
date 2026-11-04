"""The Excel report's "Results - With" / "Results - Without" sheets.

They show the absolute fluxes of each scenario laid out exactly like the
balance on "Results". Two things can break that:

  * BaseModuleReport.compute_with_scenarios() re-runs compute() against the
    with/without emission sets; if it reads the wrong set or fails to restore
    the balance, every sheet is silently wrong.
  * The renderer shares one writer across the three sheets; a layout change
    that only reaches one of them would desynchronise the rows.

Run with:
    python manage.py test api.tests.reports.test_excel_scenario_sheets
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import openpyxl as pxl

from api.reports.constants import ROW_FIRST_CATEGORY, ROW_YEARLY_FLUX_W, SUMMARY_CATEGORY_ROWS

from api.reports.data_types import (
    ActivityResult,
    EmissionsAggregator,
    ModuleResult,
    ProjectResult,
    ResultRow,
)

DURATION = 3


def _entry(activity, gas, values):
    return {
        "activity": activity,
        "gas_type": {"name": gas},
        "emissions": [{"value": v} for v in values],
    }


class TestComputeWithScenarios(unittest.TestCase):
    BALANCE = [_entry("Biomass", "CO2", [6.0, 6.0, 6.0])]
    WITH = [_entry("Biomass", "CO2", [10.0, 20.0, 30.0])]
    WITHOUT = [_entry("Biomass", "CO2", [4.0, 14.0, 24.0])]

    def _report(self, *, fail_on=None):
        from api.reports.base import BaseModuleReport

        module = Mock()
        module.project.is_finalized = False
        module.is_cached_results_valid.return_value = True
        module.cached_results_by_activity_by_gas = {
            "balance": self.BALANCE,
            "total_w": self.WITH,
            "total_wo": self.WITHOUT,
            "inventory": [],
        }
        activity_report = Mock()
        activity_report.project_report.duration = DURATION

        @dataclass
        class ConcreteReport(BaseModuleReport):
            def compute(self):
                if fail_on is not None and self.emissions_set is fail_on:
                    raise RuntimeError("boom")
                return ModuleResult(
                    title="M",
                    metadata_section_title="M",
                    result_rows=[ResultRow("CO2 in biomass", self._extract(self.emissions_set))],
                    metadata_writes=[],
                    total_emissions=self._balance_total(),
                )

        return ConcreteReport(module=module, activity_report=activity_report)

    def test_rows_and_totals_come_from_each_scenario_set(self):
        result = self._report().compute_with_scenarios()

        self.assertEqual(result.result_rows[0].yearly_values, [6.0, 6.0, 6.0])
        self.assertEqual(result.result_rows_w[0].yearly_values, [10.0, 20.0, 30.0])
        self.assertEqual(result.result_rows_wo[0].yearly_values, [4.0, 14.0, 24.0])
        self.assertEqual(result.total_emissions, [6.0, 6.0, 6.0])
        self.assertEqual(result.total_emissions_w, [10.0, 20.0, 30.0])
        self.assertEqual(result.total_emissions_wo, [4.0, 14.0, 24.0])
        self.assertEqual(result.result_rows_w[0].label, result.result_rows[0].label)

    def test_balance_set_is_restored(self):
        report = self._report()
        report.compute_with_scenarios()
        self.assertIs(report.emissions_set, self.BALANCE)

    def test_balance_set_is_restored_when_compute_fails(self):
        report = self._report(fail_on=self.WITHOUT)
        with self.assertRaises(RuntimeError):
            report.compute_with_scenarios()
        self.assertIs(report.emissions_set, self.BALANCE)


def _project_result():
    bal, w, wo = [6.0, 6.0, 6.0], [10.0, 20.0, 30.0], [4.0, 14.0, 24.0]
    module = ModuleResult(
        title="Annual Cropland",
        metadata_section_title="Annual Cropland",
        result_rows=[ResultRow("CO2 in biomass", bal)],
        metadata_writes=[],
        total_emissions=bal,
        result_rows_w=[ResultRow("CO2 in biomass", w)],
        result_rows_wo=[ResultRow("CO2 in biomass", wo)],
        total_emissions_w=w,
        total_emissions_wo=wo,
    )
    activity = ActivityResult(
        title="Maize",
        module_results=[module],
        total_emissions=bal,
        total_hectares_yearly=[0.0] * DURATION,
        total_emissions_w=w,
        total_emissions_wo=wo,
    )
    aggregated = EmissionsAggregator(
        duration=DURATION, biomass_co2=bal, biomass_co2_w=w, biomass_co2_wo=wo,
    )
    gwp = SimpleNamespace(name="AR5", co2=1, ch4=28, n2o=265, ch4_fossil=30)
    named = SimpleNamespace(name="x")
    project = SimpleNamespace(
        name="P", status=named, country=named, climate=named, moisture=named,
        soil_type=named, implementation_years=2, capitalization_years=1, gwp=gwp,
        analysis_purpose=None, project_phase=None,
    )
    return ProjectResult(
        project=project, start_year=2020, last_year=2020 + DURATION, duration=DURATION,
        activity_results=[activity], aggregated=aggregated,
        cumulative_hectares_yearly=[0.0] * DURATION,
        cumulative_heads_yearly=[0.0] * DURATION,
        cumulative_catch_yearly=[0.0] * DURATION,
        shadow_price_rows=[], nominal_shadow_prices=[], extra_shadow_prices=[],
        inventory_items=[],
    )


BIOMASS_ROW = ROW_FIRST_CATEGORY + [attr for _, attr in SUMMARY_CATEGORY_ROWS].index("biomass_co2")
BIOMASS_LABEL = SUMMARY_CATEGORY_ROWS[BIOMASS_ROW - ROW_FIRST_CATEGORY][0]
# Scenario sheets have no balance-only rows, so their activity blocks start right after the categories.
SCENARIO_ACTIVITY_ROW = ROW_FIRST_CATEGORY + len(SUMMARY_CATEGORY_ROWS)


def _row(ws, row):
    return [ws.cell(row=row, column=c).value for c in range(1, DURATION + 2)]


class TestScenarioSheets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from api.reports.renderer import ExcelRenderer

        cls.wb = pxl.load_workbook(BytesIO(ExcelRenderer(_project_result()).render()))

    def test_sheets_follow_results(self):
        self.assertEqual(self.wb.sheetnames[:3], ["Results", "Results - With", "Results - Without"])

    def test_balance_sheet_layout_is_unchanged(self):
        ws = self.wb["Results"]
        self.assertEqual(_row(ws, 2), ["Cumulative balance in Tco2-eq", 6.0, 12.0, 18.0])
        self.assertEqual(_row(ws, BIOMASS_ROW), [BIOMASS_LABEL, 6.0, 6.0, 6.0])
        self.assertEqual(ws.cell(row=ROW_YEARLY_FLUX_W, column=1).value, "Yearly flux - with (tCO2-eq)")
        self.assertEqual(_row(ws, ROW_YEARLY_FLUX_W + 1), ["Maize", 6.0, 6.0, 6.0])
        self.assertEqual(ws.cell(row=ROW_YEARLY_FLUX_W + 2, column=1).value, "Annual Cropland")
        self.assertEqual(_row(ws, ROW_YEARLY_FLUX_W + 3), ["CO2 in biomass", 6.0, 6.0, 6.0])

    def test_with_sheet_holds_absolute_with_fluxes(self):
        ws = self.wb["Results - With"]
        self.assertEqual(_row(ws, 1), ["Activity and GHGs / Years", 2020, 2021, 2022])
        self.assertEqual(_row(ws, 2), ["Cumulative flux in Tco2-eq", 10.0, 30.0, 60.0])
        self.assertEqual(_row(ws, 3), ["Yearly flux in Tco2-eq", 10.0, 20.0, 30.0])
        self.assertEqual(_row(ws, BIOMASS_ROW), [BIOMASS_LABEL, 10.0, 20.0, 30.0])
        self.assertEqual(_row(ws, SCENARIO_ACTIVITY_ROW), ["Maize", 10.0, 20.0, 30.0])
        self.assertEqual(ws.cell(row=SCENARIO_ACTIVITY_ROW + 1, column=1).value, "Annual Cropland")
        self.assertEqual(_row(ws, SCENARIO_ACTIVITY_ROW + 2), ["CO2 in biomass", 10.0, 20.0, 30.0])

    def test_without_sheet_holds_absolute_without_fluxes(self):
        ws = self.wb["Results - Without"]
        self.assertEqual(_row(ws, 2), ["Cumulative flux in Tco2-eq", 4.0, 18.0, 42.0])
        self.assertEqual(_row(ws, SCENARIO_ACTIVITY_ROW), ["Maize", 4.0, 14.0, 24.0])
        self.assertEqual(_row(ws, SCENARIO_ACTIVITY_ROW + 2), ["CO2 in biomass", 4.0, 14.0, 24.0])

    def test_scenario_sheets_mirror_the_balance_labels(self):
        res = self.wb["Results"]
        balance_labels = [res.cell(row=r, column=1).value for r in range(ROW_FIRST_CATEGORY, SCENARIO_ACTIVITY_ROW)]
        balance_labels += [res.cell(row=r, column=1).value for r in range(ROW_YEARLY_FLUX_W + 1, res.max_row + 1)]
        for name in ("Results - With", "Results - Without"):
            ws = self.wb[name]
            labels = [ws.cell(row=r, column=1).value for r in range(ROW_FIRST_CATEGORY, ws.max_row + 1)]
            with self.subTest(sheet=name):
                self.assertEqual(labels, balance_labels)


if __name__ == "__main__":
    unittest.main()
