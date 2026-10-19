"""Finalized projects serve frozen results that no later calculation can change.

The calculator is patched with a fake whose output is controlled by the test, so a "release
that changes the numbers" is simply the fake returning a different value. What is pinned here
is the freezing contract, not the science.
"""

from datetime import timedelta
from unittest import mock

from django.db import DatabaseError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from api import utilities as utils
from api.models import FinalizedModuleResult, Group, Input, ModuleType, Project
from api.reports.cache import load_emissions_from_cache
from api.services import finalization
from api.tests.factories import ActivityFactory, InputFactory, ProjectFactory, UserFactory
from api.tests.test_project_guided_step import pick_country
from djangoexact import __version__
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes

COMPUTE = "api.services.finalization.compute_module_results"


def payload(value: float) -> dict:
    breakdown = {"balance": value, "total_w": value, "total_wo": 0.0, "inventory": []}
    rows = {"balance": [], "total_w": [], "total_wo": [], "inventory": []}
    return {"total": breakdown, "by_activity": breakdown, "by_gas": breakdown, "by_activity_by_gas": rows, "units": None}


def add_input_module(activity) -> Input:
    # Activity.modules lists modules through activity.module_types, as the frontend sets them.
    activity.module_types.add(ModuleType.objects.get(class_name="Input"))
    return InputFactory(activity=activity)


def calculator_returning(value: float):
    return mock.patch(COMPUTE, side_effect=lambda module: payload(value))


class FrozenResultsTestCase(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        self.user = UserFactory(email="frozen-results@example.com")
        self.project = ProjectFactory(owner=self.user, country=pick_country())
        self.activity = ActivityFactory(project=self.project, name="Frozen activity")
        self.module = add_input_module(self.activity)

    def finalize(self):
        self.project.is_finalized = True
        self.project.save()
        self.project.refresh_from_db()

    def fresh_module(self) -> Input:
        # cache_results() leaves skip_history_when_saving on the instance, which would also
        # suppress the history row of every later save of that same instance.
        return Input.objects.get(pk=self.module.pk)

    def cache(self, value: float):
        module = self.fresh_module()
        data = payload(value)
        module.cache_results(data["total"], data["by_activity"], data["by_gas"], data["by_activity_by_gas"])
        self.fresh_module().save()  # records the cache in the module history

    def test_finalizing_sets_finalized_at_and_freezes_every_ready_module(self):
        with calculator_returning(1.0):
            self.finalize()

        self.assertIsNotNone(self.project.finalized_at)
        row = FinalizedModuleResult.objects.get(project=self.project)
        self.assertEqual(row.object_id, self.module.pk)
        self.assertEqual(row.finalized_at, self.project.finalized_at)
        self.assertEqual(row.source, FinalizedModuleResult.Source.FINALIZE)
        self.assertEqual(row.app_version, __version__)
        self.assertEqual(row.results_total["balance"], 1.0)

    def test_finalizing_reuses_the_valid_live_cache_without_calculating(self):
        self.cache(7.0)
        with mock.patch(COMPUTE, side_effect=AssertionError("must not calculate")):
            self.finalize()

        row = FinalizedModuleResult.objects.get(project=self.project)
        self.assertEqual(row.results_total["balance"], 7.0)
        self.assertIsNone(row.app_version)
        self.assertEqual(row.computed_at, self.fresh_module().last_cached_at)

    def test_results_do_not_move_when_the_calculator_changes(self):
        with calculator_returning(1.0):
            self.finalize()

        with calculator_returning(2.0) as compute:
            results, frozen = finalization.module_results(self.fresh_module(), BreakdownTypes.TOTAL, use_cache=False)

        compute.assert_not_called()
        self.assertEqual(results["balance"], 1.0)
        self.assertEqual(frozen.provenance()["finalized_at"], self.project.finalized_at)

    def test_reports_read_the_snapshot_not_the_live_cache(self):
        with calculator_returning(1.0):
            self.finalize()
        self.cache(99.0)

        loaded = load_emissions_from_cache(self.fresh_module())

        row = FinalizedModuleResult.objects.get(project=self.project)
        self.assertEqual(loaded.balance, row.results_by_activity_by_gas["balance"])

    def test_open_projects_keep_calculating_and_caching(self):
        with calculator_returning(3.0):
            results, frozen = finalization.module_results(self.fresh_module(), BreakdownTypes.TOTAL)

        self.assertIsNone(frozen)
        self.assertEqual(results["balance"], 3.0)
        self.assertEqual(self.fresh_module().cached_results_total["balance"], 3.0)

    def test_a_missing_snapshot_fails_loudly_instead_of_recalculating(self):
        Project.objects.filter(pk=self.project.pk).update(is_finalized=True, finalized_at=timezone.now())

        with calculator_returning(2.0) as compute, self.assertRaises(finalization.FrozenResultMissingError):
            finalization.module_results(self.fresh_module(), BreakdownTypes.TOTAL)
        compute.assert_not_called()

    def test_failed_calculation_leaves_the_project_open(self):
        with mock.patch(COMPUTE, side_effect=ValueError("bad input")), self.assertRaises(finalization.FinalizationError):
            self.finalize()

        self.project.refresh_from_db()
        self.assertFalse(self.project.is_finalized)
        self.assertIsNone(self.project.finalized_at)
        self.assertFalse(FinalizedModuleResult.objects.exists())

    def test_refinalizing_adds_a_new_snapshot_and_keeps_the_old_one(self):
        with calculator_returning(1.0):
            self.finalize()
        first = self.project.finalized_at

        self.project.is_finalized = False
        self.project.save()
        self.project.refresh_from_db()
        self.assertIsNone(self.project.finalized_at)

        with calculator_returning(2.0):
            self.finalize()

        self.assertNotEqual(self.project.finalized_at, first)
        self.assertEqual(FinalizedModuleResult.objects.filter(project=self.project).count(), 2)
        results, _ = finalization.module_results(self.fresh_module(), BreakdownTypes.TOTAL)
        self.assertEqual(results["balance"], 2.0)

    def test_database_refuses_to_update_or_delete_a_frozen_result(self):
        with calculator_returning(1.0):
            self.finalize()
        rows = FinalizedModuleResult.objects.filter(project=self.project)

        with self.assertRaises(DatabaseError), transaction.atomic():
            rows.update(app_version="tampered")
        with self.assertRaises(DatabaseError), transaction.atomic():
            rows.delete()
        self.assertEqual(rows.get().app_version, __version__)

    def test_deleting_the_project_purges_its_frozen_results(self):
        with calculator_returning(1.0):
            self.finalize()
        project_id = self.project.pk

        self.project.delete()

        self.assertFalse(FinalizedModuleResult.objects.filter(project_id=project_id).exists())

    def test_a_copy_of_a_finalized_project_is_open(self):
        with calculator_returning(1.0):
            self.finalize()

        shell = utils.create_project_shell(self.project, self.user)
        shell.refresh_from_db()

        self.assertFalse(shell.is_finalized)
        self.assertIsNone(shell.finalized_at)


class RestoreFrozenResultsTestCase(FrozenResultsTestCase):
    """Projects finalized before snapshots existed are frozen as they stood at finalized_at."""

    def finalize_legacy(self, finalized_at):
        # Legacy finalization: the flag was set without any snapshot being taken.
        Project.objects.filter(pk=self.project.pk).update(is_finalized=True, finalized_at=finalized_at)
        self.project.refresh_from_db()

    def test_live_cache_written_before_finalization_is_kept(self):
        self.cache(1.0)
        self.finalize_legacy(timezone.now())

        with mock.patch(COMPUTE, side_effect=AssertionError("must not calculate")):
            counts = finalization.restore_frozen_results(self.project, dry_run=False)

        self.assertEqual(counts[FinalizedModuleResult.Source.LIVE_CACHE], 1)
        self.assertEqual(FinalizedModuleResult.objects.get(project=self.project).results_total["balance"], 1.0)

    def test_results_recalculated_after_finalization_are_reverted_from_history(self):
        self.cache(1.0)
        finalized_at = timezone.now()
        self.finalize_legacy(finalized_at)
        with mock.patch("django.utils.timezone.now", return_value=finalized_at + timedelta(days=12)):
            self.cache(2.0)  # what a recalculation after finalization left in the live cache

        with mock.patch(COMPUTE, side_effect=AssertionError("must not calculate")):
            counts = finalization.restore_frozen_results(self.project, dry_run=False)

        self.assertEqual(counts[FinalizedModuleResult.Source.HISTORY], 1)
        results, _ = finalization.module_results(self.fresh_module(), BreakdownTypes.TOTAL)
        self.assertEqual(results["balance"], 1.0)

    def test_modules_never_calculated_before_finalization_are_frozen_retroactively(self):
        self.finalize_legacy(timezone.now())

        with calculator_returning(5.0):
            counts = finalization.restore_frozen_results(self.project, dry_run=False)

        self.assertEqual(counts[FinalizedModuleResult.Source.RETROACTIVE], 1)
        row = FinalizedModuleResult.objects.get(project=self.project)
        self.assertEqual(row.app_version, __version__)
        self.assertEqual(row.results_total["balance"], 5.0)

    def test_dry_run_writes_nothing_and_rerun_is_idempotent(self):
        self.cache(1.0)
        self.finalize_legacy(timezone.now())

        counts = finalization.restore_frozen_results(self.project, dry_run=True)
        self.assertEqual(counts[FinalizedModuleResult.Source.LIVE_CACHE], 1)
        self.assertFalse(FinalizedModuleResult.objects.exists())

        finalization.restore_frozen_results(self.project, dry_run=False)
        rerun = finalization.restore_frozen_results(self.project, dry_run=False)
        self.assertEqual(rerun["already_frozen"], 1)
        self.assertEqual(FinalizedModuleResult.objects.count(), 1)


class FinalizeThroughTheApiTestCase(APITestCase):
    # One request per test, and no database access after it: locally the test database connection
    # is closed when a request finishes (pre-existing, reproduced on develop with
    # test_project_guided_step), so anything after the first request fails with InterfaceError.

    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        self.user = UserFactory(email="frozen-results-api@example.com")
        self.client.force_authenticate(self.user)
        self.project = ProjectFactory(owner=self.user, country=pick_country())
        self.module = add_input_module(ActivityFactory(project=self.project, name="Api activity"))

    def patch_project(self, payload_):
        with mock.patch("api.views.security.check_permission", return_value=None), \
             mock.patch("api.views.ProjectViewSet.get_object", return_value=self.project), \
             mock.patch("api.models.Project._check_lock_expiration"):
            return self.client.patch(f"/api/projects/{self.project.pk}/", payload_, format="json")

    def get_results(self):
        with mock.patch("api.views.security.check_permission", return_value=None):
            return self.client.get(f"/api/inputs/{self.module.pk}/results/?cached=false")

    def test_finalize_sets_finalized_at_on_the_server(self):
        with calculator_returning(1.0):
            resp = self.patch_project({"is_finalized": True, "finalized_at": "2000-01-01T00:00:00Z"})

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data["is_finalized"])
        self.assertNotEqual(resp.data["finalized_at"][:4], "2000")  # read-only: the server sets it

    def test_results_of_a_finalized_project_ignore_cached_false(self):
        with calculator_returning(1.0):
            self.project.is_finalized = True
            self.project.save()

        with calculator_returning(2.0):
            resp = self.get_results()

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["balance"], 1.0)
        self.assertEqual(resp.data["frozen"]["source"], FinalizedModuleResult.Source.FINALIZE)

    def test_finalize_is_refused_when_a_module_cannot_be_calculated(self):
        with mock.patch(COMPUTE, side_effect=ValueError("bad input")):
            resp = self.patch_project({"is_finalized": True})

        self.assertEqual(resp.status_code, 400)
        self.assertIn("is_finalized", resp.data)
