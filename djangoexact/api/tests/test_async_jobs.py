import io
import sys
import types
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import AsyncJob
from api.services import async_jobs
from api.tests.factories import ProjectFactory, UserFactory
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


class ReportAsyncEndpointTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory(email="report-async-owner@example.com")
        self.client.force_authenticate(self.user)

    def test_enqueues_pdf_report_job(self):
        project = ProjectFactory(owner=self.user)
        with mock.patch("api.views.security.check_permission", return_value=None), \
                mock.patch.object(type(project), "is_ready", return_value=True), \
                mock.patch("api.views.ProjectViewSet.get_object", return_value=project):
            resp = self.client.post(f"/api/projects/{project.pk}/report/async/?template=standard&lang=en")
        self.assertEqual(resp.status_code, 202)
        self.assertIn("job_id", resp.data)
        job = AsyncJob.objects.get(pk=resp.data["job_id"])
        self.assertEqual(job.kind, AsyncJob.Kind.REPORT)
        self.assertEqual(job.params["template"], "standard")
        self.assertEqual(job.params["format"], "pdf")
        self.assertEqual(job.params["project_id"], project.pk)
        self.assertIsNone(job.params["activity_ids"])
        self.assertEqual(job.status, AsyncJob.Status.PENDING)

    def test_enqueues_xlsx_report_job_with_selected_activities(self):
        project = ProjectFactory(owner=self.user)
        with mock.patch("api.views.security.check_permission", return_value=None), \
                mock.patch.object(type(project), "is_ready", return_value=True), \
                mock.patch("api.views.ProjectViewSet.get_object", return_value=project):
            resp = self.client.post(f"/api/projects/{project.pk}/report/async/?activities=1,2")
        self.assertEqual(resp.status_code, 202)
        job = AsyncJob.objects.get(pk=resp.data["job_id"])
        self.assertEqual(job.params["format"], "xlsx")
        self.assertIsNone(job.params["template"])
        self.assertEqual(job.params["activity_ids"], [1, 2])

    def test_pdf_format_without_template_returns_400(self):
        project = ProjectFactory(owner=self.user)
        with mock.patch("api.views.security.check_permission", return_value=None), \
                mock.patch.object(type(project), "is_ready", return_value=True), \
                mock.patch("api.views.ProjectViewSet.get_object", return_value=project):
            resp = self.client.post(f"/api/projects/{project.pk}/report/async/?format=pdf")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(AsyncJob.objects.filter(project=project).exists())

    def test_not_ready_project_returns_400_and_does_not_enqueue(self):
        project = ProjectFactory(owner=self.user)
        with mock.patch("api.views.security.check_permission", return_value=None), \
                mock.patch.object(type(project), "is_ready", return_value=False), \
                mock.patch("api.views.ProjectViewSet.get_object", return_value=project):
            resp = self.client.post(f"/api/projects/{project.pk}/report/async/?template=standard")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(AsyncJob.objects.filter(project=project).exists())


class ReconcileStaleAsyncJobsTestCase(TestCase):
    def test_marks_old_running_job_failed(self):
        from django.core.management import call_command
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.RUNNING, params={})
        AsyncJob.objects.filter(pk=job.pk).update(
            started_at=timezone.now() - timedelta(hours=2),
        )
        call_command("reconcile_stale_async_jobs")
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.FAILED)
        self.assertIn("stale", job.error_message.lower())

    def test_leaves_recent_running_job(self):
        from django.core.management import call_command
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.RUNNING, params={})
        call_command("reconcile_stale_async_jobs")
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.RUNNING)

    def test_marks_old_pending_job_failed(self):
        from django.core.management import call_command
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.PENDING, params={})
        AsyncJob.objects.filter(pk=job.pk).update(
            created_at=timezone.now() - timedelta(hours=2),
        )
        call_command("reconcile_stale_async_jobs")
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.FAILED)
        self.assertIn("stuck", job.error_message.lower())

    def test_leaves_recent_pending_job(self):
        from django.core.management import call_command
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.PENDING, params={})
        call_command("reconcile_stale_async_jobs")
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.PENDING)


class ReportJobRunTestCase(TestCase):
    def test_pdf_path_uploads_and_returns_metadata(self):
        from api.services import report_jobs
        requester = UserFactory(email="report-job-requester@example.com")
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT,
            created_by=requester,
            params={"project_id": 7, "activity_ids": None, "format": "pdf",
                    "template": "standard", "lang": "en"},
        )
        fake_project = mock.Mock(pk=7, name="P")
        with mock.patch("api.services.report_jobs.Project") as m_project, \
             mock.patch("api.services.report_jobs.compute_project_result", return_value=mock.Mock()), \
             mock.patch("api.services.report_jobs.build_template_context", return_value={}), \
             mock.patch("api.services.report_jobs.render_to_string", return_value="<html></html>") as m_render, \
             mock.patch("api.services.report_jobs._weasyprint_pdf", return_value=b"%PDF-1.7"), \
             mock.patch("api.services.report_jobs._upload", return_value="reports/7/1.pdf") as m_upload:
            m_project.objects.get.return_value = fake_project
            result = report_jobs.run(job)
        self.assertEqual(result["gcs_path"], "reports/7/1.pdf")
        self.assertEqual(result["content_type"], "application/pdf")
        m_upload.assert_called_once()
        m_render.assert_called_once()
        rendered_context = m_render.call_args.args[1]
        self.assertEqual(rendered_context["user"], requester)


class ReportDownloadTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory(email="report-download-owner@example.com")
        self.client.force_authenticate(self.user)

    def test_download_streams_completed_report(self):
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED,
            created_by=self.user,
            result={"gcs_path": "reports/7/1.pdf", "filename": "standard.pdf",
                    "content_type": "application/pdf"},
        )
        fake_blob = mock.Mock()
        fake_blob.open.return_value = io.BytesIO(b"%PDF-1.7")
        with mock.patch("api.views.storage.Client") as m_client:
            m_client.return_value.bucket.return_value.blob.return_value = fake_blob
            resp = self.client.get(f"/api/async-jobs/{job.pk}/download/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("standard.pdf", resp["Content-Disposition"])

    def test_download_404_when_not_completed(self):
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.RUNNING, created_by=self.user,
        )
        resp = self.client.get(f"/api/async-jobs/{job.pk}/download/")
        self.assertEqual(resp.status_code, 404)

    def test_download_404_for_wrong_kind(self):
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.PROJECT_COPY, status=AsyncJob.Status.COMPLETED,
            created_by=self.user, result={"gcs_path": "reports/7/1.pdf"},
        )
        resp = self.client.get(f"/api/async-jobs/{job.pk}/download/")
        self.assertEqual(resp.status_code, 404)

    def test_download_404_when_missing_gcs_path(self):
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED,
            created_by=self.user, result={"filename": "standard.pdf"},
        )
        resp = self.client.get(f"/api/async-jobs/{job.pk}/download/")
        self.assertEqual(resp.status_code, 404)

    def test_other_user_cannot_download_job(self):
        other = UserFactory(email="report-download-other@example.com")
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED,
            created_by=other,
            result={"gcs_path": "reports/7/1.pdf", "filename": "standard.pdf",
                    "content_type": "application/pdf"},
        )
        resp = self.client.get(f"/api/async-jobs/{job.pk}/download/")
        self.assertEqual(resp.status_code, 404)
