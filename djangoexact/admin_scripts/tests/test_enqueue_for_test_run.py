"""Tests for admin_scripts.job_dispatcher.enqueue_for_test_run."""
from unittest.mock import patch

from django.test import TransactionTestCase

from admin_scripts.job_dispatcher import (
    compute_filters_hash,
    enqueue_for_test_run,
    enqueue_or_join,
)
from admin_scripts.models import ComputationJob
from api.models import CustomUser


class EnqueueForTestRunTest(TransactionTestCase):
    databases = {"default"}

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="t@example.com", password="x", firebase_uid="t1",
        )

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_creates_job_with_max_rows_and_run_scoped_hash(self, mock_dispatch):
        job = enqueue_for_test_run(
            user=self.user, run_id=7,
            module_type="Grassland", attribute="is_fire_used",
            from_value="True", to_value="False", max_rows=100,
        )
        self.assertEqual(job.max_rows, 100)
        self.assertEqual(job.module_type, "Grassland")
        self.assertEqual(job.attribute, "is_fire_used")
        self.assertIn(self.user, job.requested_by.all())
        # Hash must include both max_rows and force_key="testrun-7"
        expected_hash = compute_filters_hash({
            "module_type": "Grassland",
            "attribute": "is_fire_used",
            "from_value": "True",
            "to_value": "False",
            "filters": {},
            "max_rows": 100,
            "force_key": "testrun-7",
        })
        self.assertEqual(job.filters_hash, expected_hash)
        mock_dispatch.assert_called_once_with(job.pk)

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_does_not_collide_with_existing_production_job(self, mock_dispatch):
        # Pre-existing production job with no max_rows (the legacy hash).
        prod = enqueue_or_join(
            self.user, "Grassland", "is_fire_used", "True", "False",
        )
        # Test-run job for the "same" parameters must be a fresh, distinct row.
        test_job = enqueue_for_test_run(
            user=self.user, run_id=1,
            module_type="Grassland", attribute="is_fire_used",
            from_value="True", to_value="False", max_rows=100,
        )
        self.assertNotEqual(prod.pk, test_job.pk)
        self.assertNotEqual(prod.filters_hash, test_job.filters_hash)

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_different_runs_get_different_jobs(self, mock_dispatch):
        job_a = enqueue_for_test_run(
            user=self.user, run_id=1,
            module_type="Grassland", attribute="is_fire_used",
            from_value="True", to_value="False", max_rows=100,
        )
        job_b = enqueue_for_test_run(
            user=self.user, run_id=2,
            module_type="Grassland", attribute="is_fire_used",
            from_value="True", to_value="False", max_rows=100,
        )
        self.assertNotEqual(job_a.pk, job_b.pk)
        # Both rows are preserved (no delete, no cascade).
        self.assertEqual(
            ComputationJob.objects.filter(pk__in=[job_a.pk, job_b.pk]).count(), 2
        )
