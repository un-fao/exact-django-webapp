import sys
import types
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from api.models import AsyncJob
from api.services import async_jobs
from api.tests.factories import UserFactory
import api.services as services_pkg


def _stub_handler_module(dotted_name):
    """Build an in-memory stand-in for a not-yet-implemented api.services
    handler module (e.g. report_jobs / copy_jobs, added by later tasks).

    A real ``mock.patch("api.services.report_jobs.run", ...)`` cannot resolve
    its target while the module has no backing file on disk: patch's target
    lookup imports "api.services.report_jobs" itself, which raises
    ModuleNotFoundError before it ever gets to the "run" attribute, and that
    error is not something a plain ``create=True`` papers over. Registering a
    throwaway ModuleType under both sys.modules and the api.services package
    attribute (so `from api.services import report_jobs` resolves via either
    lookup path CPython's import system may take) lets `mock.patch` find and
    replace a real "run" attribute on it, so the test exercises the actual
    lazy `from api.services import report_jobs` in the command rather than a
    stand-in for the whole call.
    """
    mod = types.ModuleType(dotted_name)
    mod.run = lambda *args, **kwargs: None
    return mod


class AsyncJobModelTestCase(TestCase):
    def test_defaults(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={"project_id": 1})
        self.assertEqual(job.status, AsyncJob.Status.PENDING)
        self.assertEqual(job.progress, 0)
        self.assertEqual(job.result, {})
        self.assertEqual(job.error_message, "")
        self.assertIsNone(job.started_at)
        self.assertIsNotNone(job.created_at)

    def test_kind_choices(self):
        self.assertEqual(AsyncJob.Kind.PROJECT_COPY.value, "project_copy")
        self.assertEqual(AsyncJob.Kind.REPORT.value, "report")


class AsyncJobDispatchTestCase(TestCase):
    def test_enqueue_creates_job_and_schedules_dispatch(self):
        with mock.patch.object(async_jobs, "dispatch") as m_dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                job = async_jobs.enqueue(AsyncJob.Kind.REPORT, {"project_id": 1})
        self.assertEqual(job.kind, AsyncJob.Kind.REPORT)
        self.assertEqual(job.status, AsyncJob.Status.PENDING)
        m_dispatch.assert_called_once_with(job.pk)

    @override_settings(CLOUD_RUN_COMPUTATION_JOB_NAME="")
    def test_dispatch_uses_subprocess_when_no_job_name(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={})
        fake_proc = mock.Mock(pid=4242)
        with mock.patch("api.services.async_jobs.subprocess.Popen", return_value=fake_proc) as m_popen:
            async_jobs.dispatch(job.pk)
        m_popen.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.pid, 4242)

    @override_settings(CLOUD_RUN_COMPUTATION_JOB_NAME="projects/p/locations/l/jobs/exact-computation-job")
    def test_dispatch_uses_cloud_run_when_job_name_set(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={})
        with mock.patch("api.services.async_jobs._dispatch_cloud_run") as m_cr:
            async_jobs.dispatch(job.pk)
        m_cr.assert_called_once_with(job.pk)

    @override_settings(CLOUD_RUN_COMPUTATION_JOB_NAME="projects/p/locations/l/jobs/exact-computation-job")
    def test_cloud_run_dispatch_failure_marks_job_failed(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={})
        fake_run_v2 = mock.MagicMock()
        fake_run_v2.JobsClient.return_value.run_job.side_effect = RuntimeError("boom")
        with mock.patch.dict("sys.modules", {"google.cloud": mock.MagicMock(run_v2=fake_run_v2)}):
            async_jobs._dispatch_cloud_run(job.pk)  # must not raise
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.FAILED)
        self.assertIn("boom", job.error_message)
        self.assertIsNotNone(job.completed_at)


class RunAsyncJobCommandTestCase(TestCase):
    def _run(self, job_id):
        from django.core.management import call_command
        call_command("run_async_job", "--job-id", str(job_id))

    def test_dispatches_report_kind_and_marks_completed(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={})
        stub = _stub_handler_module("api.services.report_jobs")
        with mock.patch.dict(sys.modules, {"api.services.report_jobs": stub}), \
                mock.patch.object(services_pkg, "report_jobs", stub, create=True):
            with mock.patch("api.services.report_jobs.run", return_value={"gcs_path": "x"}) as m_run:
                self._run(job.pk)
            m_run.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.COMPLETED)
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.result, {"gcs_path": "x"})
        self.assertIsNotNone(job.completed_at)

    def test_marks_failed_on_handler_exception(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.PROJECT_COPY, params={})
        stub = _stub_handler_module("api.services.copy_jobs")
        with mock.patch.dict(sys.modules, {"api.services.copy_jobs": stub}), \
                mock.patch.object(services_pkg, "copy_jobs", stub, create=True):
            with mock.patch("api.services.copy_jobs.run", side_effect=RuntimeError("boom")):
                self._run(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.FAILED)
        self.assertIn("boom", job.error_message)

    def test_skips_non_pending_job(self):
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.CANCELLED, params={},
        )
        stub = _stub_handler_module("api.services.report_jobs")
        with mock.patch.dict(sys.modules, {"api.services.report_jobs": stub}), \
                mock.patch.object(services_pkg, "report_jobs", stub, create=True):
            with mock.patch("api.services.report_jobs.run") as m_run:
                self._run(job.pk)
            m_run.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.CANCELLED)


class AsyncJobEndpointTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory(email="owner@example.com")
        self.other = UserFactory(email="other@example.com")
        self.client.force_authenticate(self.user)

    def test_owner_can_read_own_job(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={}, created_by=self.user)
        resp = self.client.get(f"/api/async-jobs/{job.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "pending")
        self.assertEqual(resp.data["kind"], "report")

    def test_other_user_cannot_read_job(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={}, created_by=self.other)
        resp = self.client.get(f"/api/async-jobs/{job.pk}/")
        self.assertEqual(resp.status_code, 404)
