"""User text in the Excel report is written as literal text, never as a formula.

openpyxl stores any string starting with "=" as a formula, so an activity named
``=HYPERLINK("https://evil","click")`` would run in the reviewer's Excel, and a
control character in a comment would abort the whole report.

Run with:
    python manage.py test api.tests.reports.test_excel_literal_text
"""
from __future__ import annotations

import unittest
from io import BytesIO
from types import SimpleNamespace

import openpyxl as pxl
from django.utils.translation import gettext_lazy

from api.reports.constants import SPC_NPV_START_ROW, WS_INVENTORY, WS_METADATA, WS_RESULTS, WS_SHADOW_PRICE
from api.reports.data_types import (
    ActivityResult,
    EmissionsAggregator,
    InventoryItem,
    MetadataWrite,
    ModuleResult,
    ProjectResult,
    ResultRow,
)
from api.reports.excel_manager import write_literal_cell

DURATION = 2
PROJECT_NAME = '=HYPERLINK("https://evil.example","click")'
ACTIVITY_TITLE = "=1+1"
INVENTORY_ACTIVITY = "=SUM(A1:A9)"
METADATA_COMMENT = "=cmd|' /C calc'!A0"
LABEL_WITH_BELL = "CO2\x07 in biomass"
COMMENT_WITH_NUL = "looks\x00 fine"


def _project_result() -> ProjectResult:
    values = [1.0, 2.0]
    module = ModuleResult(
        title="Annual Cropland",
        metadata_section_title="Annual Cropland",
        result_rows=[ResultRow(LABEL_WITH_BELL, values)],
        metadata_writes=[MetadataWrite(1, 6, METADATA_COMMENT), MetadataWrite(2, 6, COMMENT_WITH_NUL)],
        total_emissions=values,
    )
    activity = ActivityResult(
        title=ACTIVITY_TITLE, module_results=[module], total_emissions=values,
        total_hectares_yearly=[0.0] * DURATION,
    )
    named = SimpleNamespace(name="x")
    project = SimpleNamespace(
        name=PROJECT_NAME, status=named, country=named, climate=named, moisture=named,
        soil_type=named, implementation_years=1, capitalization_years=1,
        gwp=SimpleNamespace(name="AR5", co2=1, ch4=28, n2o=265, ch4_fossil=30),
    )
    return ProjectResult(
        project=project, start_year=2020, last_year=2020 + DURATION, duration=DURATION,
        activity_results=[activity], aggregated=EmissionsAggregator(duration=DURATION),
        cumulative_hectares_yearly=[0.0] * DURATION,
        cumulative_heads_yearly=[0.0] * DURATION,
        cumulative_catch_yearly=[0.0] * DURATION,
        shadow_price_rows=[], nominal_shadow_prices=[], extra_shadow_prices=[],
        inventory_items=[InventoryItem(INVENTORY_ACTIVITY, "Annual Cropland", "3B2", "CO2", 1.0)],
    )


def _written_and_reloaded(value):
    wb = pxl.Workbook()
    write_literal_cell(wb.active, 1, 1, value)
    buf = BytesIO()
    wb.save(buf)
    cell = pxl.load_workbook(buf).active.cell(row=1, column=1)
    return cell.value, cell.data_type


def _cells_with_value(ws, value):
    return [c for row in ws.iter_rows() for c in row if c.value == value]


class TestExcelLiteralText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from api.reports.renderer import ExcelRenderer

        cls.wb = pxl.load_workbook(BytesIO(ExcelRenderer(_project_result()).render()))

    def assertLiteralText(self, ws, value):
        cells = _cells_with_value(ws, value)
        self.assertTrue(cells, f"{value!r} not found on {ws.title}")
        for cell in cells:
            self.assertEqual(cell.data_type, "s", cell.coordinate)

    def test_project_name_starting_with_equals_stays_text_after_reload(self):
        cell = self.wb[WS_METADATA].cell(row=2, column=2)
        self.assertEqual(cell.value, PROJECT_NAME)
        self.assertEqual(cell.data_type, "s")

    def test_activity_title_starting_with_equals_stays_text(self):
        self.assertLiteralText(self.wb[WS_RESULTS], ACTIVITY_TITLE)
        self.assertLiteralText(self.wb[WS_METADATA], ACTIVITY_TITLE)

    def test_metadata_comment_starting_with_equals_stays_text(self):
        self.assertLiteralText(self.wb[WS_METADATA], METADATA_COMMENT)

    def test_inventory_activity_starting_with_equals_stays_text(self):
        self.assertLiteralText(self.wb[WS_INVENTORY], INVENTORY_ACTIVITY)

    def test_control_characters_are_dropped_instead_of_aborting_the_report(self):
        self.assertLiteralText(self.wb[WS_RESULTS], "CO2 in biomass")
        self.assertLiteralText(self.wb[WS_METADATA], "looks fine")

    def test_normal_text_is_unchanged(self):
        self.assertLiteralText(self.wb[WS_RESULTS], "Annual Cropland")

    def test_shadow_price_formulas_are_still_formulas(self):
        cell = self.wb[WS_SHADOW_PRICE].cell(row=SPC_NPV_START_ROW + 3, column=2)
        self.assertEqual(cell.value, "=B2")
        self.assertEqual(cell.data_type, "f")

    def test_non_string_values_pass_through(self):
        self.assertEqual(_written_and_reloaded(2.5), (2.5, "n"))

    def test_numeric_looking_string_stays_a_string(self):
        self.assertEqual(_written_and_reloaded("123"), ("123", "s"))

    def test_error_code_string_stays_a_string_not_an_error_cell(self):
        self.assertEqual(_written_and_reloaded("#N/A"), ("#N/A", "s"))

    def test_lazy_translation_is_written_as_text(self):
        self.assertEqual(_written_and_reloaded(gettext_lazy("=1+1")), ("=1+1", "s"))


if __name__ == "__main__":
    unittest.main()
