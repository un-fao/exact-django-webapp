"""The report data of a finalized project (parameters, reference names, tier 2 overrides, shadow
prices, indicators) is frozen at finalization and served from there, in every language.

Results are faked as in test_finalized_results_frozen; what is pinned here is that the report
intermediate model no longer comes from live code or reference data once a project is finalized.
"""

from decimal import Decimal
from unittest import mock

import numpy as np
from django.db import DatabaseError, transaction
from django.test import SimpleTestCase
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy

import ipcc.models as ipcc_models
from api.models import FinalizedReportData, Project, StatusType
from api.reports import NotReadyError, compute_project_result
from api.reports.data_types import InventoryItem, MetadataWrite, ModuleResult, ResultRow
from api.reports.frozen import LANGUAGES, FrozenReport, module_result_from_json, module_result_to_json
from api.reports.modules import InputReport
from api.services import finalization
from api.tests.factories import ActivityFactory, InputFactory
from api.tests.test_finalized_results_frozen import FrozenProjectTestCase, calculator_returning


class ModuleResultSerializationTestCase(SimpleTestCase):
    def test_round_trip_keeps_every_field_and_numeric_cells(self):
        result = ModuleResult(
            title=gettext_lazy("Inputs"),
            metadata_section_title="Inputs",
            result_rows=[ResultRow(label="CO2", yearly_values=[np.float64(1.5), 2.0])],
            metadata_writes=[MetadataWrite(row_offset=1, col=2, value=Decimal("0.25"), fill="LIGHT_BLUE"), MetadataWrite(2, 3, None)],
            additional_indicator_rows_w=[("Hectares", [1.0, 2.0])],
            total_emissions=[np.float64(3.0)],
            units_breakdown_w=[1.0],
            units_heads_w=[np.int64(4)],
            is_with=True,
            _inventory_items=[InventoryItem("Activity", "Inputs", "3.C.4", "N2O", 0.5)],
        )

        decoded = module_result_from_json(module_result_to_json(result))

        self.assertEqual(decoded.title, "Inputs")
        self.assertEqual(decoded.metadata_writes[0].value, 0.25)
        self.assertIsInstance(decoded.metadata_writes[0].value, float)
        self.assertEqual(decoded.result_rows, [ResultRow(label="CO2", yearly_values=[1.5, 2.0])])
        self.assertEqual(decoded.additional_indicator_rows_w, [("Hectares", [1.0, 2.0])])
        self.assertEqual(decoded.units_heads_w, [4])
        self.assertTrue(decoded.is_with)
        self.assertEqual(decoded._inventory_items, result._inventory_items)

    def test_a_value_that_would_not_render_the_same_is_refused_at_freeze_time(self):
        result = ModuleResult(title="x", metadata_section_title="x", result_rows=[], metadata_writes=[MetadataWrite(1, 2, object())])

        with self.assertRaises(TypeError):
            module_result_to_json(result)


class FrozenReportDataTestCase(FrozenProjectTestCase):
    def report_rows(self):
        return FinalizedReportData.objects.filter(project=self.project, finalized_at=self.project.finalized_at)

    def finalize_legacy(self):
        Project.objects.filter(pk=self.project.pk).update(is_finalized=True, finalized_at=timezone.now())
        self.project.refresh_from_db()
        with calculator_returning(1.0):
            finalization.restore_frozen_results(self.project, dry_run=False)

    def test_finalizing_freezes_module_activity_and_project_data_in_every_language(self):
        with calculator_returning(1.0):
            self.finalize()

        rows = {row.content_type.model: row for row in self.report_rows()}
        self.assertEqual(set(rows), {"input", "activity", "project"})
        self.assertEqual(set(rows["input"].data["langs"]), set(LANGUAGES))
        self.assertEqual(set(rows["activity"].data["langs"]), set(LANGUAGES))
        self.assertEqual(set(rows["project"].data["indicators"]), set(LANGUAGES))
        self.assertEqual(rows["input"].data["schema"], 1)

    def test_reports_of_a_finalized_project_never_run_the_live_module_report(self):
        with calculator_returning(1.0):
            self.finalize()
        frozen = self.report_rows().get(content_type__model="input").data["langs"]["en"]

        with mock.patch.object(InputReport, "compute", side_effect=AssertionError("live report must not run")), \
             translation.override("en"):
            result = compute_project_result(self.project)

        self.assertEqual(module_result_to_json(result.activity_results[0].module_results[0]), frozen)

    def test_each_language_serves_its_own_frozen_data(self):
        with calculator_returning(1.0):
            self.finalize()
        langs = self.report_rows().get(content_type__model="input").data["langs"]

        for lang in LANGUAGES:
            with translation.override(lang):
                served = FrozenReport(self.project).module_result(self.fresh_module())
            self.assertEqual(module_result_to_json(served), langs[lang])

    def test_shadow_price_changes_after_finalization_do_not_reach_the_report(self):
        with calculator_returning(1.0):
            self.finalize()
        frozen = [(sp.year, sp.min_value) for sp in compute_project_result(self.project).nominal_shadow_prices]
        self.assertTrue(frozen, "needs seeded shadow prices, otherwise this test proves nothing")

        ipcc_models.ShadowPriceOfCarbon.objects.update(min_value=123456.0)

        served = [(sp.year, sp.min_value) for sp in compute_project_result(self.project).nominal_shadow_prices]
        self.assertEqual(served, frozen)

    def test_indicators_and_soc_come_from_the_snapshot(self):
        with calculator_returning(1.0):
            self.finalize()
        stored = self.report_rows().get(content_type__model="project").data["indicators"]["en"]

        with translation.override("en"):
            result = compute_project_result(self.project)

        self.assertEqual(result.frozen_indicators, stored)
        self.assertIn("soc", result.frozen_indicators)

    def test_open_projects_keep_computing_reports_live(self):
        with calculator_returning(1.0):
            result = compute_project_result(self.project)

        self.assertIsNone(result.frozen_indicators)
        self.assertFalse(FinalizedReportData.objects.exists())

    def test_a_module_that_is_not_ready_refuses_the_finalize(self):
        draft_activity = ActivityFactory(project=self.project, name="Draft activity")
        draft_activity.module_types.set(self.activity.module_types.all())
        InputFactory(activity=draft_activity, status=StatusType.objects.get_or_create(name_en="EMPTY")[0])

        with calculator_returning(1.0), self.assertRaisesMessage(finalization.FinalizationError, "is not ready"):
            self.finalize()

        self.project.refresh_from_db()
        self.assertFalse(self.project.is_finalized)
        self.assertFalse(FinalizedReportData.objects.exists())

    def test_missing_report_data_fails_the_report_instead_of_computing_it(self):
        self.finalize_legacy()

        with self.assertRaisesMessage(NotReadyError, "frozen report data"):
            compute_project_result(self.project)

    def test_restore_freezes_report_data_retroactively_and_is_idempotent(self):
        self.finalize_legacy()

        self.assertEqual(finalization.restore_report_data(self.project, dry_run=True)["report_data_frozen_retroactively"], 1)
        self.assertFalse(self.report_rows().exists())

        finalization.restore_report_data(self.project, dry_run=False)
        self.assertEqual({row.source for row in self.report_rows()}, {"frozen_retroactively"})
        self.assertEqual(finalization.restore_report_data(self.project, dry_run=False)["report_data_already_frozen"], 1)

    def test_database_refuses_to_change_report_data_and_purges_it_with_the_project(self):
        with calculator_returning(1.0):
            self.finalize()
        rows = self.report_rows()

        with self.assertRaises(DatabaseError), transaction.atomic():
            rows.update(app_version="tampered")
        with self.assertRaises(DatabaseError), transaction.atomic():
            rows.delete()

        project_id = self.project.pk
        self.project.delete()
        self.assertFalse(FinalizedReportData.objects.filter(project_id=project_id).exists())
