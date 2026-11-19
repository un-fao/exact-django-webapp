"""The Excel report's GHG Protocol scope sheets: Scope Assignment, Results by Scope and the hidden Scope Lists.

The row builder is tested on stand-in modules and entries named like the models (scope rules and flux labels key
on the Python class name only). test_scope_sheets_project runs a real project end to end.

Run with:
    python manage.py test api.tests.reports.test_scope_sheets
"""
from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import openpyxl as pxl
from django.test import SimpleTestCase
from openpyxl.utils import get_column_letter

from api.reports import scope_rows, scopes_sheet
from api.reports.base import NotReadyError
from api.reports.scope_rows import (
    MODULE_LEVEL_ENTRY,
    ActivitySets,
    EntrySets,
    ModuleSets,
    build_scope_rows,
    split_gross,
)
from api.reports.scopes_sheet import (
    WS_RESULTS_BY_SCOPE,
    WS_SCOPE_ASSIGNMENT,
    WS_SCOPE_LISTS,
    AssignmentCol,
    write_scope_sheets,
)
from api.scopes import Scope
from api.services.finalization import FrozenResultMissingError
from api.utilities import ScenarioTypes

W, WO = ScenarioTypes.WITH, ScenarioTypes.WITHOUT
YEARS = 3


class Energy:
    def __init__(self, submodules=()):
        self.submodules = list(submodules)
        self.pk = 1


class EnergyEntry:
    pk = 7


class AnnualCropland:
    pass


def cached(activity: str, gas: str, values: list[float]) -> dict:
    """An emission set entry in the result cache's form: activity by value, gas by name."""
    return {"activity": activity, "gas_type": {"name": gas}, "emissions": [{"value": v} for v in values]}


def energy_module(index=1, title="Energy", activity_index=1, activity_title="Activity A") -> ActivitySets:
    """A diesel entry, an electricity entry, and module sets equal to their sum."""
    diesel = EntrySets(EnergyEntry(), "Energy 1: Diesel",
                       [cached("Fuel", "CO2", [10, 10, 10])], [cached("Fuel", "CO2", [5, 5, 5])])
    electricity = EntrySets(EnergyEntry(), "Energy 2: Electricity",
                            [cached("Electricity", "CO2", [4, 4, 4])], [])
    module = ModuleSets(
        index, title, Energy(),
        sets_w=[cached("Fuel", "CO2", [10, 10, 10]), cached("Electricity", "CO2", [4, 4, 4])],
        sets_wo=[cached("Fuel", "CO2", [5, 5, 5])],
        entries=(diesel, electricity),
    )
    return ActivitySets(activity_index, activity_title, (module,))


def cropland_module(index=2, activity_index=1, activity_title="Activity A") -> ActivitySets:
    module = ModuleSets(
        index, "Annual Cropland", AnnualCropland(),
        sets_w=[cached("Biomass", "CO2", [-3, -3, 1])],
        sets_wo=[cached("Biomass", "CO2", [1, 1, 1])],
    )
    return ActivitySets(activity_index, activity_title, (module,))


def row_by(rows, entry, scenario):
    return next(r for r in rows if r.entry_label == entry and r.scenario is scenario)


class RowBuilderTests(SimpleTestCase):
    def test_split_is_per_year_so_a_series_can_carry_both_emissions_and_removals(self):
        self.assertEqual(split_gross([5.0, -3.0, 2.0, 0.0]), (7.0, -3.0))

    def test_entries_get_their_own_rows_with_the_entry_class_scope(self):
        rows = build_scope_rows([energy_module()], YEARS)
        diesel_w = row_by(rows, "Energy 1: Diesel", W)
        self.assertEqual((diesel_w.emissions, diesel_w.removals), (30, 0))
        self.assertEqual(diesel_w.rule.default, Scope.SCOPE_1)
        self.assertEqual(diesel_w.rule.allowed, (Scope.SCOPE_1, Scope.SCOPE_3))
        self.assertEqual(diesel_w.gas_label, "CO2")
        self.assertEqual(row_by(rows, "Energy 2: Electricity", W).rule.default, Scope.SCOPE_2)

    def test_module_sets_equal_to_the_entries_leave_no_module_level_row(self):
        rows = build_scope_rows([energy_module()], YEARS)
        self.assertFalse([r for r in rows if r.entry_label == MODULE_LEVEL_ENTRY])

    def test_all_zero_fluxes_are_skipped(self):
        rows = build_scope_rows([energy_module()], YEARS)
        self.assertFalse([r for r in rows if r.entry_label == "Energy 2: Electricity" and r.scenario is WO])

    def test_module_without_entries_is_one_module_level_row_per_flux_and_scenario(self):
        rows = build_scope_rows([cropland_module()], YEARS)
        self.assertEqual([(r.entry_label, r.scenario, r.emissions, r.removals) for r in rows],
                         [(MODULE_LEVEL_ENTRY, W, 1, -6), (MODULE_LEVEL_ENTRY, WO, 3, 0)])
        self.assertEqual(rows[0].rule.allowed, (Scope.SCOPE_1,))
        self.assertEqual(rows[0].flux_label, "Biomass Carbon stock")

    def test_year_window_cuts_longer_series(self):
        rows = build_scope_rows([cropland_module()], year_count=2)
        self.assertEqual((rows[0].emissions, rows[0].removals), (0, -6))

    def test_entry_drift_becomes_a_module_level_row_and_is_logged(self):
        entry = EntrySets(EnergyEntry(), "Energy 1", [cached("Fuel", "CO2", [8, 8, 8])], [])
        module = ModuleSets(5, "Energy", Energy(), [cached("Fuel", "CO2", [10, 10, 10])], [], (entry,))
        with patch.object(scope_rows.log, "warning") as warning:
            rows = build_scope_rows([ActivitySets(1, "A", (module,))], YEARS)
        residual = row_by(rows, MODULE_LEVEL_ENTRY, W)
        self.assertEqual(residual.emissions, 6)
        self.assertEqual(residual.rule.default, Scope.SCOPE_1)
        warning.assert_called_once()
        self.assertEqual(warning.call_args.args[1:6], (5, "Fuel", "CO2", 6, 2))

    def test_float_noise_between_module_and_entries_is_not_a_row(self):
        entries = tuple(EntrySets(EnergyEntry(), f"E{v}", [cached("Fuel", "CO2", [v] * YEARS)], []) for v in (0.1, 0.2))
        module = ModuleSets(1, "Energy", Energy(), [cached("Fuel", "CO2", [0.3] * YEARS)], [], entries)
        with patch.object(scope_rows.log, "warning") as warning:
            rows = build_scope_rows([ActivitySets(1, "A", (module,))], YEARS)
        self.assertFalse([r for r in rows if r.entry_label == MODULE_LEVEL_ENTRY])
        warning.assert_not_called()

    def test_rows_reconcile_with_the_module_sets(self):
        rows = build_scope_rows([energy_module(), cropland_module(activity_index=2)], YEARS)
        net = {s: sum(r.emissions + r.removals for r in rows if r.scenario is s) for s in (W, WO)}
        self.assertEqual(net[W], 30 + 12 - 5)
        self.assertEqual(net[WO], 15 + 3)

    def test_live_enum_sets_match_cached_string_sets(self):
        from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes

        live = [SimpleNamespace(activity=ActivityTypes.FUEL, gas_type=GasTypes.CO2,
                                emissions=[SimpleNamespace(value=v) for v in (10, 10, 10)])]
        entry = EntrySets(EnergyEntry(), "Energy 1", live, [])
        module = ModuleSets(1, "Energy", Energy(), [cached("Fuel", "CO2", [10, 10, 10])], [], (entry,))
        rows = build_scope_rows([ActivitySets(1, "A", (module,))], YEARS)
        self.assertEqual([(r.entry_label, r.emissions) for r in rows], [("Energy 1", 30)])


class Storage(Energy):
    pass


class StorageEntry:
    pk = 8


class Settlement(Energy):
    pass


class Building:
    pk = 9


class OtherInfrastructure:
    pk = 10


def failing_report(error: Exception) -> SimpleNamespace:
    def raise_error(entry, calculator):
        raise error

    return SimpleNamespace(module=Energy([EnergyEntry()]), submodule_scenario_sets=raise_error)


class EntryCollectionTests(SimpleTestCase):
    def test_entries_that_cannot_be_calculated_fall_back_to_the_module_level(self):
        for error in (FrozenResultMissingError(), NotReadyError(), ValueError("no EF"), Exception("not ready")):
            with self.subTest(error=type(error).__name__), patch.object(scope_rows.log, "warning") as warning:
                self.assertEqual(scope_rows._entry_sets(failing_report(error)), ())
                warning.assert_called_once()

    def test_bugs_in_entry_calculation_propagate(self):
        with self.assertRaises(AttributeError):
            scope_rows._entry_sets(failing_report(AttributeError("bug")))

    def test_modules_without_entry_rows_never_read_submodules(self):
        report = SimpleNamespace(module=AnnualCropland())
        self.assertEqual(scope_rows._entry_sets(report), ())

    def test_storage_entries_are_collected_with_the_value_chain_scope_3_category(self):
        entry = StorageEntry()
        sets = {"total_w": [cached("Fuel", "CO2", [2, 2, 2]), cached("Storage", "CO2", [1, 1, 1])], "total_wo": []}
        report = SimpleNamespace(module=Storage([entry]), submodule_scenario_sets=lambda e, calculator: sets)
        entries = scope_rows._entry_sets(report)
        self.assertEqual([(e.entry, e.label) for e in entries], [(entry, "StorageEntry 1")])

        module = ModuleSets(1, "Storage", report.module, sets_w=[cached("Fuel", "CO2", [2, 2, 2])], sets_wo=[],
                            entries=entries)
        with patch.object(scope_rows.log, "warning") as warning:
            rows = build_scope_rows([ActivitySets(1, "A", (module,))], YEARS)
        fuel = next(r for r in rows if r.entry_label == "StorageEntry 1" and r.flux_label == "Fuel")
        self.assertEqual((fuel.rule.default, fuel.rule.scope3_category), (Scope.SCOPE_1, 4))
        residual = row_by(rows, MODULE_LEVEL_ENTRY, W)
        self.assertEqual((residual.flux_label, residual.removals), ("Storage", -3))
        warning.assert_called_once()

    def test_other_infrastructure_gets_its_own_settlement_row_without_a_drift_warning(self):
        building, infrastructure = Building(), OtherInfrastructure()
        sets_by_entry = {
            building: {"total_w": [cached("Roads", "CO2", [1, 1, 1])], "total_wo": []},
            infrastructure: {"total_w": [cached("Roads", "CO2", [4, 4, 4])], "total_wo": []},
        }
        calculators_used = []

        def entry_sets(entry, calculator):
            calculators_used.append(calculator.__name__)
            return sets_by_entry[entry]

        report = SimpleNamespace(module=Settlement([building, infrastructure]), submodule_scenario_sets=entry_sets)
        entries = scope_rows._entry_sets(report)
        self.assertEqual(calculators_used, ["BuildingCalculator", "OtherInfrastructureCalculator"])

        module_total_since_infrastructure_counts = [cached("Roads", "CO2", [5, 5, 5])]
        module = ModuleSets(1, "Settlement", report.module, sets_w=module_total_since_infrastructure_counts,
                            sets_wo=[], entries=entries)
        with patch.object(scope_rows.log, "warning") as warning:
            rows = build_scope_rows([ActivitySets(1, "A", (module,))], YEARS)
        infrastructure_row = next(r for r in rows if r.entry_label == "OtherInfrastructure 2")
        self.assertEqual((infrastructure_row.emissions, infrastructure_row.rule.default), (12, Scope.SCOPE_3))
        self.assertFalse([r for r in rows if r.entry_label == MODULE_LEVEL_ENTRY])
        warning.assert_not_called()


def fake_result(activities: list[ActivitySets]) -> SimpleNamespace:
    """A ProjectResult stand-in whose module reports hand back the given sets."""
    def report(module: ModuleSets):
        sets = {id(e.entry): {"total_w": e.sets_w, "total_wo": e.sets_wo} for e in module.entries}
        module.module.submodules = [e.entry for e in module.entries]
        return SimpleNamespace(
            module=module.module, emissions_set_w=module.sets_w, emissions_set_wo=module.sets_wo,
            submodule_scenario_sets=lambda entry, calculator: sets[id(entry)],
        )

    return SimpleNamespace(
        start_year=2024, last_year=2024 + YEARS,
        activity_results=[
            SimpleNamespace(title=a.title, module_results=[SimpleNamespace(title=m.title) for m in a.modules],
                            _module_reports=[report(m) for m in a.modules])
            for a in activities
        ],
    )


def rendered(result) -> pxl.Workbook:
    wb = pxl.Workbook()
    write_scope_sheets(wb, result)
    buffer = BytesIO()
    wb.save(buffer)
    return pxl.load_workbook(BytesIO(buffer.getvalue()))


class WorkbookTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Entries are distinct instances so the stand-in reports can tell them apart.
        cls.wb = rendered(fake_result([energy_module(activity_title="=1+1"), cropland_module(activity_index=2)]))
        cls.ws = cls.wb[WS_SCOPE_ASSIGNMENT]

    def data_rows(self):
        return list(self.ws.iter_rows(min_row=scopes_sheet.ASSIGNMENT_FIRST_DATA_ROW))

    def test_sheets_are_appended_with_the_lists_hidden(self):
        self.assertEqual(self.wb.sheetnames[-3:], [WS_SCOPE_ASSIGNMENT, WS_RESULTS_BY_SCOPE, WS_SCOPE_LISTS])
        self.assertEqual(self.wb[WS_SCOPE_LISTS].sheet_state, "hidden")

    def test_dropdowns_only_on_selectable_rows_and_read_the_lists_range(self):
        validations = self.ws.data_validations.dataValidation
        selectable = {f"G{row[0].row}" for row in self.data_rows()
                      if row[AssignmentCol.USER_SELECTABLE - 1].value == "Yes"}
        covered = {rng.coord for dv in validations for rng in dv.sqref.ranges}
        self.assertTrue(selectable)
        self.assertEqual(covered, selectable)
        formulas = {dv.formula1 for dv in validations}
        self.assertIn("'Scope Lists'!$A$1:$A$2", formulas)
        lists = self.wb[WS_SCOPE_LISTS]
        self.assertEqual([lists["A1"].value, lists["A2"].value], ["Scope 1", "Scope 3"])
        self.assertTrue(all(dv.showErrorMessage and not dv.allow_blank for dv in validations))

    def test_sheet_is_protected_and_only_dropdown_cells_are_unlocked(self):
        self.assertTrue(self.ws.protection.sheet)
        for row in self.data_rows():
            scope_cell = row[AssignmentCol.SCOPE - 1]
            selectable = row[AssignmentCol.USER_SELECTABLE - 1].value == "Yes"
            self.assertEqual(scope_cell.protection.locked, not selectable, scope_cell.coordinate)
            self.assertTrue(row[AssignmentCol.EMISSIONS - 1].protection.locked)

    def test_helper_columns_are_hidden(self):
        for column in scopes_sheet.HELPER_COLUMNS:
            self.assertTrue(self.ws.column_dimensions[get_column_letter(column)].hidden, column.name)

    def test_user_text_starting_with_equals_stays_text(self):
        cell = self.ws.cell(row=scopes_sheet.ASSIGNMENT_FIRST_DATA_ROW, column=AssignmentCol.ACTIVITY)
        self.assertEqual((cell.value, cell.data_type), ("=1+1", "s"))
        titles = [c for row in self.wb[WS_RESULTS_BY_SCOPE].iter_rows() for c in row if c.value == "=1+1"]
        self.assertTrue(titles)
        self.assertTrue(all(c.data_type == "s" for c in titles))

    def test_net_is_a_formula_of_the_same_row(self):
        row = scopes_sheet.ASSIGNMENT_FIRST_DATA_ROW
        self.assertEqual(self.ws.cell(row=row, column=AssignmentCol.NET).value, f"=L{row}+M{row}")

    def test_results_formulas_key_only_on_codes_and_labels(self):
        last = scopes_sheet.ASSIGNMENT_FIRST_DATA_ROW + len(self.data_rows()) - 1
        ws = self.wb[WS_RESULTS_BY_SCOPE]
        project_scope_1 = scopes_sheet.RESULTS_FIRST_BLOCK_ROW + 2
        self.assertEqual(ws.cell(row=project_scope_1, column=1).value, "Scope 1")
        self.assertEqual(
            ws.cell(row=project_scope_1, column=2).value,
            f"=SUMIFS('Scope Assignment'!$L$5:$L${last},'Scope Assignment'!$G$5:$G${last},\"Scope 1\","
            f"'Scope Assignment'!$O$5:$O${last},\"w\")",
        )
        self.assertEqual(ws.cell(row=project_scope_1, column=8).value, f"=D{project_scope_1}-G{project_scope_1}")
        formulas = [c.value for row in ws.iter_rows() for c in row if str(c.value).startswith("=SUMIFS")]
        self.assertFalse([f for f in formulas if "=1+1" in f or "Activity" in f])
        self.assertTrue([f for f in formulas if f.endswith(f"'Scope Assignment'!$Q$5:$Q${last},2)")])

    def test_results_list_the_four_scopes_without_unassigned(self):
        ws = self.wb[WS_RESULTS_BY_SCOPE]
        first = scopes_sheet.RESULTS_FIRST_BLOCK_ROW + 2
        self.assertEqual([ws.cell(row=r, column=1).value for r in range(first, first + 5)],
                         ["Scope 1", "Scope 2", "Scope 3", "Outside scopes", scopes_sheet.TOTAL_CHANGE_LABEL])
        self.assertEqual(ws.cell(row=first + 4, column=8).value, f"=SUM(H{first}:H{first + 3})")

    def test_project_without_modules_still_gets_headers_and_bounded_formulas(self):
        wb = rendered(fake_result([]))
        ws = wb[WS_SCOPE_ASSIGNMENT]
        self.assertEqual(ws.cell(row=scopes_sheet.ASSIGNMENT_ROW_HEADER, column=1).value, "Activity")
        self.assertEqual(ws.cell(row=scopes_sheet.ASSIGNMENT_FIRST_DATA_ROW, column=1).value, scopes_sheet.NO_ROWS_NOTE)
        formula = wb[WS_RESULTS_BY_SCOPE].cell(row=scopes_sheet.RESULTS_FIRST_BLOCK_ROW + 2, column=2).value
        self.assertIn("$L$5:$L$5", formula)
