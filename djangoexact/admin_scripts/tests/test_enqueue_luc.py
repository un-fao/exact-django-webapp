"""End-to-end: LUC jobs go through the enqueue dispatcher and run_computation_job."""
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from admin_scripts.catalog import get_catalog
from admin_scripts.job_dispatcher import enqueue_for_test_run
from admin_scripts.models import ComputationJob, ModuleTestRun
from admin_scripts.test_planner import plan_module_tests
from api.models import CustomUser


class EnqueueLucTest(TestCase):
    databases = {"default"}

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="luc@example.com", password="x", firebase_uid="luc1",
        )

    def test_plan_module_tests_emits_luc_pair_entries(self):
        catalog = get_catalog()
        planned, skipped = plan_module_tests(catalog)
        luc_planned = [e for e in planned if e["module_type"] == "LandUseChange"]
        luc_skipped = [e for e in skipped if e["module_type"] == "LandUseChange"]
        self.assertEqual(len(luc_planned), 144)
        self.assertEqual(luc_skipped, [])

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_enqueue_luc_job_creates_pending_computation_job(self, mock_dispatch):
        run = ModuleTestRun.objects.create(requested_by=self.user)
        job = enqueue_for_test_run(
            user=self.user,
            run_id=run.id,
            module_type="LandUseChange",
            attribute="module_type",
            from_value="AnnualCropland#0",
            to_value="Grassland#0",
            max_rows=10,
        )
        self.assertIsNotNone(job)
        self.assertEqual(job.module_type, "LandUseChange")
        self.assertEqual(job.from_value, "AnnualCropland#0")
        self.assertEqual(job.to_value, "Grassland#0")
        self.assertEqual(job.status, ComputationJob.Status.PENDING)

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_run_computation_job_dispatches_to_luc_slice(self, mock_dispatch):
        run = ModuleTestRun.objects.create(requested_by=self.user)
        job = enqueue_for_test_run(
            user=self.user, run_id=run.id,
            module_type="LandUseChange",
            attribute="module_type",
            from_value="AnnualCropland#0",
            to_value="Grassland#0",
            max_rows=10,
        )
        with patch("api.services.luc_compute._compute_luc_slice") as mock_slice:
            mock_slice.return_value = ([{"ok": 1}], [])
            call_command("run_computation_job", job_id=job.id)
        job.refresh_from_db()
        self.assertEqual(job.status, ComputationJob.Status.COMPLETED)
        mock_slice.assert_called_once()
