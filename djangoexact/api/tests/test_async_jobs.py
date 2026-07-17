from unittest import mock

from django.test import TestCase, override_settings

from api.models import AsyncJob
from api.services import async_jobs


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
