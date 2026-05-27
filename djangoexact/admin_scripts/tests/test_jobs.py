"""Tests for ComputationJob model, gap detector, and job dispatcher."""

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from unittest.mock import patch

from admin_scripts.gap_detector import detect_gap
from admin_scripts.job_dispatcher import compute_filters_hash, enqueue_or_join
from admin_scripts.models import ComputationJob, ModuleTestRun
from api.models import CustomUser
from minitool.models import ChangeRecord


class ComputationJobModelTest(TestCase):
    databases = {"default"}

    def test_create_job(self):
        job = ComputationJob.objects.create(
            filters_hash="abc123",
            module_type="Grassland",
            attribute="grassland_management_type",
            from_value="Non-Degraded",
            to_value="Improved Grassland",
        )
        self.assertEqual(job.status, ComputationJob.Status.PENDING)
        self.assertEqual(str(job), "Grassland/grassland_management_type [pending]")

    def test_status_transitions(self):
        job = ComputationJob.objects.create(
            filters_hash="def456",
            module_type="Grassland",
            attribute="grassland_management_type",
            from_value="A",
            to_value="B",
        )
        job.status = ComputationJob.Status.RUNNING
        job.started_at = timezone.now()
        job.save()
        job.refresh_from_db()
        self.assertEqual(job.status, "running")

    def test_filters_hash_unique(self):
        ComputationJob.objects.create(
            filters_hash="unique_hash",
            module_type="Grassland",
            attribute="test",
            from_value="A",
            to_value="B",
        )
        with self.assertRaises(Exception):
            ComputationJob.objects.create(
                filters_hash="unique_hash",
                module_type="Livestock",
                attribute="test",
                from_value="C",
                to_value="D",
            )

    def test_max_rows_defaults_to_null(self):
        job = ComputationJob.objects.create(
            filters_hash="mr_null_hash",
            module_type="Grassland",
            attribute="x",
            from_value="A",
            to_value="B",
        )
        self.assertIsNone(job.max_rows)


class GapDetectorTest(TestCase):
    databases = {"default"}

    def test_detect_gap_when_no_data(self):
        result = detect_gap("Grassland", "grassland_management_type", "A", "B")
        self.assertTrue(result)

    def test_detect_gap_when_data_exists(self):
        ChangeRecord.objects.create(
            module_type="Grassland",
            field="grassland_management_type",
            from_value="Non-Degraded",
            to_value="Improved Grassland",
            region="Africa",
            climate="Tropical",
            moisture="Moist",
            soil_type="Clay",
            total=-1.0,
        )
        result = detect_gap(
            "Grassland", "grassland_management_type",
            "Non-Degraded", "Improved Grassland",
        )
        self.assertFalse(result)


class FiltersHashTest(TestCase):

    def test_hash_deterministic(self):
        params = {
            "module_type": "Grassland",
            "attribute": "grassland_management_type",
            "from_value": "A",
            "to_value": "B",
        }
        h1 = compute_filters_hash(params)
        h2 = compute_filters_hash(params)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex

    def test_hash_differs_for_different_params(self):
        h1 = compute_filters_hash({
            "module_type": "Grassland",
            "attribute": "grassland_management_type",
            "from_value": "A",
            "to_value": "B",
        })
        h2 = compute_filters_hash({
            "module_type": "Grassland",
            "attribute": "grassland_management_type",
            "from_value": "A",
            "to_value": "C",
        })
        self.assertNotEqual(h1, h2)

    def test_hash_key_order_irrelevant(self):
        h1 = compute_filters_hash({
            "module_type": "Grassland",
            "attribute": "test",
            "from_value": "A",
            "to_value": "B",
            "filters": {"region": "Africa", "climate": "Tropical"},
        })
        h2 = compute_filters_hash({
            "to_value": "B",
            "from_value": "A",
            "module_type": "Grassland",
            "attribute": "test",
            "filters": {"climate": "Tropical", "region": "Africa"},
        })
        self.assertEqual(h1, h2)

    def test_hash_backward_compatible_when_keys_absent(self):
        """A params dict without max_rows/force_key must hash the same as before
        the keys were added, keeping existing rows reachable by enqueue_or_join."""
        params = {
            "module_type": "Grassland",
            "attribute": "grassland_management_type",
            "from_value": "A",
            "to_value": "B",
        }
        # Recompute the legacy hash manually to lock the contract.
        import hashlib, json
        legacy = hashlib.sha256(
            json.dumps(
                {
                    "module_type": "Grassland",
                    "attribute": "grassland_management_type",
                    "from_value": "A",
                    "to_value": "B",
                    "filters": {},
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        self.assertEqual(compute_filters_hash(params), legacy)

    def test_hash_differs_when_max_rows_set(self):
        base = {
            "module_type": "Grassland",
            "attribute": "x",
            "from_value": "A",
            "to_value": "B",
        }
        with_cap = {**base, "max_rows": 100}
        self.assertNotEqual(compute_filters_hash(base), compute_filters_hash(with_cap))

    def test_hash_differs_when_force_key_set(self):
        base = {
            "module_type": "Grassland",
            "attribute": "x",
            "from_value": "A",
            "to_value": "B",
        }
        forced = {**base, "force_key": "run-7"}
        self.assertNotEqual(compute_filters_hash(base), compute_filters_hash(forced))

    def test_hash_treats_none_keys_as_absent(self):
        """Passing max_rows=None or force_key=None must hash identically to omission."""
        base = {
            "module_type": "Grassland",
            "attribute": "x",
            "from_value": "A",
            "to_value": "B",
        }
        with_nones = {**base, "max_rows": None, "force_key": None}
        self.assertEqual(compute_filters_hash(base), compute_filters_hash(with_nones))


class EnqueueOrJoinTest(TransactionTestCase):
    databases = {"default"}

    def setUp(self):
        from api.models import CustomUser
        self.user1 = CustomUser.objects.create_user(
            email="user1@example.com",
            password="test123",
            firebase_uid="uid1",
        )
        self.user2 = CustomUser.objects.create_user(
            email="user2@example.com",
            password="test123",
            firebase_uid="uid2",
        )

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_enqueue_creates_job(self, mock_dispatch):
        job = enqueue_or_join(
            self.user1, "Grassland", "grassland_management_type", "A", "B",
        )
        self.assertEqual(job.status, ComputationJob.Status.PENDING)
        self.assertEqual(job.module_type, "Grassland")
        self.assertIn(self.user1, job.requested_by.all())

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_join_existing_job(self, mock_dispatch):
        job1 = enqueue_or_join(
            self.user1, "Grassland", "grassland_management_type", "A", "B",
        )
        job2 = enqueue_or_join(
            self.user2, "Grassland", "grassland_management_type", "A", "B",
        )
        self.assertEqual(job1.pk, job2.pk)
        self.assertEqual(job1.requested_by.count(), 2)

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_dispatch_called_once_for_coalesced_jobs(self, mock_dispatch):
        enqueue_or_join(
            self.user1, "Grassland", "grassland_management_type", "A", "B",
        )
        enqueue_or_join(
            self.user2, "Grassland", "grassland_management_type", "A", "B",
        )
        # dispatch_job called via on_commit -- only the first enqueue triggers it
        mock_dispatch.assert_called_once()


class ModuleTestRunModelTest(TestCase):
    databases = {"default"}

    def test_create_run(self):
        user = CustomUser.objects.create_user(
            email="run@example.com", password="x", firebase_uid="r1"
        )
        run = ModuleTestRun.objects.create(requested_by=user)
        self.assertEqual(run.jobs.count(), 0)
        self.assertEqual(run.skipped, [])
        self.assertIsNone(run.completed_at)
        self.assertIn(f"TestRun #{run.pk}", str(run))
