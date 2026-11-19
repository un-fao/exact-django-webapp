"""Scope sheets of a real project: an annual cropland, an Energy module with a diesel and an electricity entry, and
a Storage module whose entry is calculated only for the scope sheets.

Run with:
    python manage.py test api.tests.reports.test_scope_sheets_project
"""
from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import openpyxl as pxl

import api.models as models
from api.reports import generate_excel_report, scope_rows
from api.reports.constants import DATA_COL_START, ROW_CUMULATIVE_BALANCE, WS_RESULTS
from api.reports.scopes_sheet import ASSIGNMENT_FIRST_DATA_ROW, WS_SCOPE_ASSIGNMENT, WS_SCOPE_LISTS, AssignmentCol
from api.tests.factories import StorageEntryFactory
from api.tests.unit.factories import UnitTestAnnualCroplandFactory
from api.tests.unit.utils import APITestCaseMixin

DIESEL = "Gasoil/Diesel Oil"
STORAGE_ENTRY = "Cold store"
ELECTRICITY_EF = 0.5
TOLERANCE_TCO2E = 1e-6


class ProjectScopeSheetsTests(APITestCaseMixin):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.create_project().status_code, 201)
        self.project = models.Project.objects.get(name=self.project_data["name"])
        module_types = [
            models.ModuleType.objects.get(class_name=name) for name in ("AnnualCropland", "Energy", "Storage")
        ]
        response = self.create_activity(self.project, self.user, module_types)
        self.assertEqual(response.status_code, 200, response.data)
        activity = models.Activity.objects.get(id=response.data["id"])

        cropland = models.AnnualCropland.objects.get(activity=activity)
        response = self.edit_module(cropland, self.user, UnitTestAnnualCroplandFactory.get_validated_data())
        self.assertEqual(response.status_code, 200, response.data)

        diesel = models.FuelType.objects.get(fuel_use_type__name_en="Stationary", name_en=DIESEL)
        energy = models.Energy.objects.get(activity=activity)
        for fuel in (diesel, models.FuelType.objects.filter(name_en="Electricity").first()):
            response = self.create_submodule(models.EnergyEntry, self.user, {"parent": energy.pk})
            self.assertEqual(response.status_code, 201, response.data)
            entry = models.EnergyEntry.objects.get(id=response.data["id"])
            data = {f"fuel_type_{s}": fuel.pk for s in ("start", "w", "wo")}
            data |= {"quantity_consumed_per_year_start": 100, "quantity_consumed_per_year_w": 150,
                     "quantity_consumed_per_year_wo": 100}
            # The project country may lack an electricity EF row.
            data |= {f"electricity_ef_t2_{s}": ELECTRICITY_EF for s in ("start", "w", "wo")}
            response = self.edit_module(entry, self.user, data)
            self.assertEqual(response.status_code, 200, response.data)

        storage = models.Storage.objects.get(activity=activity)
        # Diesel is pinned: the factory may pick Electricity or Renewable, which emit no fuel flux.
        StorageEntryFactory(parent=storage, name=STORAGE_ENTRY,
                            fuel_type_start=diesel, fuel_type_w=diesel, fuel_type_wo=diesel, is_refrigerant_used=True)
        # A parent module has no fields of its own, but finalizing requires it to be ready. Set after the entry,
        # whose save re-saves the parent from its stale in-memory copy.
        models.Storage.objects.filter(pk=storage.pk).update(status=models.StatusType.objects.get(name_en="READY"))

    def scope_rows_of_report(self) -> tuple[list[dict], float, pxl.Workbook]:
        """The Scope Assignment rows, the Results cumulative balance and the workbook of a fresh report."""
        with patch.object(scope_rows.log, "warning") as warning:
            data = generate_excel_report(models.Project.objects.get(pk=self.project.pk))
        drift = [c for c in warning.call_args_list if "differs" in c.args[0]]
        self.assertFalse(drift, "entries must add up to their module")
        wb = pxl.load_workbook(BytesIO(data))
        rows = [
            {"row": row[0].row, **{column: row[column - 1].value for column in AssignmentCol}}
            for row in wb[WS_SCOPE_ASSIGNMENT].iter_rows(min_row=ASSIGNMENT_FIRST_DATA_ROW)
        ]
        year_count = self.project.last_year_of_accounting - self.project.start_year_of_activities
        balance = wb[WS_RESULTS].cell(row=ROW_CUMULATIVE_BALANCE, column=DATA_COL_START + year_count - 1).value
        return rows, balance, wb

    def assert_rows_reconcile(self, rows: list[dict], cumulative_balance: float) -> None:
        net = {code: sum(r[AssignmentCol.EMISSIONS] + r[AssignmentCol.REMOVALS] for r in rows
                         if r[AssignmentCol.SCENARIO_CODE] == code) for code in ("w", "wo")}
        self.assertAlmostEqual(net["w"] - net["wo"], cumulative_balance, delta=TOLERANCE_TCO2E)

    @staticmethod
    def entry_rows(rows: list[dict], fragment: str) -> list[dict]:
        return [r for r in rows if fragment in str(r[AssignmentCol.ENTRY])]

    def test_scope_rows_reconcile_with_the_results_balance_and_carry_the_catalog_scopes(self):
        rows, cumulative_balance, wb = self.scope_rows_of_report()
        self.assert_rows_reconcile(rows, cumulative_balance)

        diesel, electricity = self.entry_rows(rows, DIESEL), self.entry_rows(rows, "Electricity")
        self.assertTrue(diesel and electricity, [r[AssignmentCol.ENTRY] for r in rows])
        self.assertEqual({(r[AssignmentCol.SCOPE], r[AssignmentCol.USER_SELECTABLE]) for r in diesel},
                         {("Scope 1", "Yes")})
        self.assertEqual({r[AssignmentCol.SCOPE] for r in electricity}, {"Scope 2"})
        diesel_cells = {f"G{r['row']}" for r in diesel}
        diesel_lists = {dv.formula1 for dv in wb[WS_SCOPE_ASSIGNMENT].data_validations.dataValidation
                        if diesel_cells & {rng.coord for rng in dv.sqref.ranges}}
        self.assertEqual(len(diesel_lists), 1)
        list_cells = wb[WS_SCOPE_LISTS][diesel_lists.pop().split("!")[1].replace("$", "")]
        self.assertEqual([cell.value for (cell,) in list_cells], ["Scope 1", "Scope 3"])

        storage_fuel = [r for r in self.entry_rows(rows, STORAGE_ENTRY) if r[AssignmentCol.FLUX] == "Fuel"]
        self.assertTrue(storage_fuel, [r[AssignmentCol.ENTRY] for r in rows])
        self.assertEqual({r[AssignmentCol.SCOPE3_CATEGORY] for r in storage_fuel}, {4})

        cropland_title = models.ModuleType.objects.get(class_name="AnnualCropland").name
        land = [r for r in rows if r[AssignmentCol.MODULE] == cropland_title]
        self.assertTrue(land)
        self.assertEqual({(r[AssignmentCol.SCOPE], r[AssignmentCol.USER_SELECTABLE]) for r in land},
                         {("Scope 1", "No")})

    def test_finalized_project_reports_the_same_rows_from_its_frozen_snapshots(self):
        live_rows, _, _ = self.scope_rows_of_report()
        project = models.Project.objects.get(pk=self.project.pk)
        project.is_finalized = True
        project.save()

        frozen_rows, cumulative_balance, _ = self.scope_rows_of_report()
        self.assert_rows_reconcile(frozen_rows, cumulative_balance)
        self.assertTrue(self.entry_rows(frozen_rows, STORAGE_ENTRY), "entries must come from their frozen snapshots")
        key = [AssignmentCol.ENTRY, AssignmentCol.FLUX, AssignmentCol.GAS, AssignmentCol.SCENARIO_CODE,
               AssignmentCol.SCOPE]
        self.assertEqual([[r[c] for c in key] for r in frozen_rows], [[r[c] for c in key] for r in live_rows])
        for live, frozen in zip(live_rows, frozen_rows):
            self.assertAlmostEqual(frozen[AssignmentCol.EMISSIONS], live[AssignmentCol.EMISSIONS],
                                   delta=TOLERANCE_TCO2E)
            self.assertAlmostEqual(frozen[AssignmentCol.REMOVALS], live[AssignmentCol.REMOVALS],
                                   delta=TOLERANCE_TCO2E)
