"""Tests for the report-ready email + signed 24-hour download link feature.

Covers the stateless token helpers (api/services/report_links.py), the email
sender (api/services/report_notifications.py), the token-aware download endpoint
(AsyncJobViewSet.download), and the cleanup_expired_reports command.

Django TestCase / APITestCase only (no pytest-django). CustomUser.email is
unique, so every user gets a distinct explicit email.
"""
import io
import time
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import AsyncJob
from api.services import report_links
from api.services.report_notifications import (
    send_report_failed_email,
    send_report_ready_email,
)
from api.tests.factories import ProjectFactory, UserFactory

LOCMEM_EMAIL = "django.core.mail.backends.locmem.EmailBackend"


class ReportDownloadTokenHelperTestCase(TestCase):
    def test_token_round_trip(self):
        token = report_links.make_download_token(4242)
        self.assertEqual(report_links.load_download_token(token), 4242)

    def test_tampered_token_returns_none(self):
        token = report_links.make_download_token(4242)
        self.assertIsNone(report_links.load_download_token(token + "tampered"))

    def test_garbage_token_returns_none(self):
        self.assertIsNone(report_links.load_download_token("not-a-valid-token"))

    def test_expired_token_returns_none(self):
        old = time.time() - (report_links.DOWNLOAD_MAX_AGE + 3600)
        with mock.patch("django.core.signing.time.time", return_value=old):
            token = report_links.make_download_token(4242)
        self.assertIsNone(report_links.load_download_token(token))

    @override_settings(BACKEND_BASE_URL="https://api.example.org")
    def test_build_download_url_shape(self):
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED,
            created_by=UserFactory(email="url-shape@example.com"),
            result={"gcs_path": "reports/1/1.pdf", "filename": "standard.pdf"},
        )
        url = report_links.build_download_url(job)
        prefix = f"https://api.example.org/api/async-jobs/{job.pk}/download/?token="
        self.assertTrue(url.startswith(prefix))
        self.assertGreater(len(url), len(prefix))


class SendReportReadyEmailTestCase(TestCase):
    @override_settings(
        EMAIL_BACKEND=LOCMEM_EMAIL,
        BACKEND_BASE_URL="https://api.example.org",
        REPORT_READY_EMAIL_ENABLED=True,
    )
    def test_sends_email_with_tokenized_link(self):
        mail.outbox = []
        user = UserFactory(email="report-ready@example.com")
        project = ProjectFactory(owner=user)
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED,
            created_by=user, project=project,
            result={"gcs_path": "reports/1/1.pdf", "filename": "standard.pdf",
                    "content_type": "application/pdf"},
        )
        send_report_ready_email(job)

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["report-ready@example.com"])
        link_prefix = f"https://api.example.org/api/async-jobs/{job.pk}/download/?token="
        self.assertIn(link_prefix, msg.body)
        self.assertEqual(len(msg.alternatives), 1)
        html_body, mimetype = msg.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn(link_prefix, html_body)

    @override_settings(EMAIL_BACKEND=LOCMEM_EMAIL, REPORT_READY_EMAIL_ENABLED=False)
    def test_disabled_sends_nothing(self):
        mail.outbox = []
        user = UserFactory(email="report-disabled@example.com")
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED, created_by=user,
            result={"gcs_path": "reports/1/1.pdf", "filename": "standard.pdf"},
        )
        send_report_ready_email(job)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND=LOCMEM_EMAIL, REPORT_READY_EMAIL_ENABLED=True)
    def test_non_report_kind_sends_nothing(self):
        mail.outbox = []
        user = UserFactory(email="report-copy-kind@example.com")
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.PROJECT_COPY, status=AsyncJob.Status.COMPLETED,
            created_by=user, result={},
        )
        send_report_ready_email(job)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_BACKEND=LOCMEM_EMAIL,
        REPORT_READY_EMAIL_ENABLED=True,
        BACKEND_BASE_URL="",
    )
    def test_missing_backend_base_url_sends_nothing(self):
        mail.outbox = []
        user = UserFactory(email="report-no-base-url@example.com")
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED, created_by=user,
            result={"gcs_path": "reports/1/1.pdf", "filename": "standard.pdf"},
        )
        send_report_ready_email(job)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND=LOCMEM_EMAIL, REPORT_READY_EMAIL_ENABLED=True)
    def test_no_recipient_sends_nothing(self):
        mail.outbox = []
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED,
            created_by=None, result={"gcs_path": "reports/1/1.pdf"},
        )
        send_report_ready_email(job)
        self.assertEqual(len(mail.outbox), 0)


class SendReportFailedEmailTestCase(TestCase):
    @override_settings(
        EMAIL_BACKEND=LOCMEM_EMAIL,
        REPORT_READY_EMAIL_ENABLED=True,
        BACKEND_BASE_URL="",
    )
    def test_sends_email_without_link_even_without_base_url(self):
        mail.outbox = []
        user = UserFactory(email="report-failed@example.com")
        project = ProjectFactory(owner=user)
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.FAILED,
            created_by=user, project=project,
            error_message="Boom: something went wrong deep in the calculator.",
        )
        send_report_failed_email(job)

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["report-failed@example.com"])
        # A failure email carries no download link, so it must still send with
        # BACKEND_BASE_URL unset and must not contain a tokenized link.
        self.assertNotIn("/download/?token=", msg.body)
        self.assertEqual(len(msg.alternatives), 1)
        html_body, mimetype = msg.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertNotIn("/download/?token=", html_body)

    @override_settings(EMAIL_BACKEND=LOCMEM_EMAIL, REPORT_READY_EMAIL_ENABLED=False)
    def test_disabled_sends_nothing(self):
        mail.outbox = []
        user = UserFactory(email="report-failed-disabled@example.com")
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.FAILED,
            created_by=user, error_message="Boom",
        )
        send_report_failed_email(job)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND=LOCMEM_EMAIL, REPORT_READY_EMAIL_ENABLED=True)
    def test_non_report_kind_sends_nothing(self):
        mail.outbox = []
        user = UserFactory(email="report-failed-copy-kind@example.com")
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.PROJECT_COPY, status=AsyncJob.Status.FAILED,
            created_by=user, error_message="Boom",
        )
        send_report_failed_email(job)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND=LOCMEM_EMAIL, REPORT_READY_EMAIL_ENABLED=True)
    def test_no_recipient_sends_nothing(self):
        mail.outbox = []
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.FAILED,
            created_by=None, error_message="Boom",
        )
        send_report_failed_email(job)
        self.assertEqual(len(mail.outbox), 0)


class ReportEmailBestEffortTestCase(TestCase):
    """A send failure must be swallowed and logged, never raised to the caller.

    Sends now use fail_silently=False, so the surrounding try/except in each
    sender is what isolates the job from an SMTP error.
    """

    @override_settings(
        EMAIL_BACKEND=LOCMEM_EMAIL,
        REPORT_READY_EMAIL_ENABLED=True,
        BACKEND_BASE_URL="https://api.example.org",
    )
    @mock.patch(
        "api.services.report_notifications.EmailMultiAlternatives.send",
        side_effect=Exception("smtp is down"),
    )
    def test_ready_email_swallows_send_failure(self, _mock_send):
        user = UserFactory(email="best-effort-ready@example.com")
        project = ProjectFactory(owner=user)
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED,
            created_by=user, project=project,
            result={"gcs_path": "reports/1/1.pdf", "filename": "standard.pdf"},
        )
        # Must not raise despite the send blowing up.
        self.assertIsNone(send_report_ready_email(job))
        _mock_send.assert_called_once()

    @override_settings(
        EMAIL_BACKEND=LOCMEM_EMAIL,
        REPORT_READY_EMAIL_ENABLED=True,
        BACKEND_BASE_URL="",
    )
    @mock.patch(
        "api.services.report_notifications.EmailMultiAlternatives.send",
        side_effect=Exception("smtp is down"),
    )
    def test_failed_email_swallows_send_failure(self, _mock_send):
        user = UserFactory(email="best-effort-failed@example.com")
        project = ProjectFactory(owner=user)
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.FAILED,
            created_by=user, project=project, error_message="Boom",
        )
        # Must not raise despite the send blowing up.
        self.assertIsNone(send_report_failed_email(job))
        _mock_send.assert_called_once()


class ReportDownloadTokenEndpointTestCase(APITestCase):
    def setUp(self):
        self.owner = UserFactory(email="token-owner@example.com")
        self.other = UserFactory(email="token-other@example.com")

    def _completed_report(self, owner):
        return AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED,
            created_by=owner,
            result={"gcs_path": "reports/7/1.pdf", "filename": "standard.pdf",
                    "content_type": "application/pdf"},
        )

    def test_valid_token_serves_file_without_auth(self):
        job = self._completed_report(self.owner)
        token = report_links.make_download_token(job.pk)
        self.client.force_authenticate(None)
        fake_blob = mock.Mock()
        fake_blob.open.return_value = io.BytesIO(b"%PDF-1.7")
        with mock.patch("api.views.storage.Client") as m_client:
            m_client.return_value.bucket.return_value.blob.return_value = fake_blob
            resp = self.client.get(f"/api/async-jobs/{job.pk}/download/", {"token": token})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("standard.pdf", resp["Content-Disposition"])

    def test_invalid_token_404s_for_anonymous(self):
        job = self._completed_report(self.owner)
        self.client.force_authenticate(None)
        resp = self.client.get(f"/api/async-jobs/{job.pk}/download/", {"token": "not-a-valid-token"})
        self.assertEqual(resp.status_code, 404)

    def test_expired_token_404s_for_anonymous(self):
        job = self._completed_report(self.owner)
        old = time.time() - (report_links.DOWNLOAD_MAX_AGE + 3600)
        with mock.patch("django.core.signing.time.time", return_value=old):
            token = report_links.make_download_token(job.pk)
        self.client.force_authenticate(None)
        resp = self.client.get(f"/api/async-jobs/{job.pk}/download/", {"token": token})
        self.assertEqual(resp.status_code, 404)

    def test_owner_downloads_without_token(self):
        job = self._completed_report(self.owner)
        self.client.force_authenticate(self.owner)
        fake_blob = mock.Mock()
        fake_blob.open.return_value = io.BytesIO(b"%PDF-1.7")
        with mock.patch("api.views.storage.Client") as m_client:
            m_client.return_value.bucket.return_value.blob.return_value = fake_blob
            resp = self.client.get(f"/api/async-jobs/{job.pk}/download/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("standard.pdf", resp["Content-Disposition"])

    def test_other_user_404s_without_token(self):
        job = self._completed_report(self.owner)
        self.client.force_authenticate(self.other)
        resp = self.client.get(f"/api/async-jobs/{job.pk}/download/")
        self.assertEqual(resp.status_code, 404)


class CleanupExpiredReportsCommandTestCase(TestCase):
    def _report(self, email, gcs_path="reports/7/1.pdf"):
        return AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED,
            created_by=UserFactory(email=email),
            result={"gcs_path": gcs_path, "filename": "standard.pdf",
                    "content_type": "application/pdf"},
        )

    def test_deletes_expired_report_blob_and_clears_path(self):
        job = self._report("cleanup-expired@example.com")
        # completed_at is not auto_now; set it 25h in the past via a bulk update.
        AsyncJob.objects.filter(pk=job.pk).update(
            completed_at=timezone.now() - timedelta(hours=25),
        )
        fake_blob = mock.Mock()
        with mock.patch("google.cloud.storage.Client") as m_client:
            m_client.return_value.bucket.return_value.blob.return_value = fake_blob
            call_command("cleanup_expired_reports")
        fake_blob.delete.assert_called_once()
        job.refresh_from_db()
        self.assertNotIn("gcs_path", job.result)

    def test_recent_report_is_untouched(self):
        job = self._report("cleanup-recent@example.com", gcs_path="reports/7/2.pdf")
        AsyncJob.objects.filter(pk=job.pk).update(completed_at=timezone.now())
        fake_blob = mock.Mock()
        with mock.patch("google.cloud.storage.Client") as m_client:
            m_client.return_value.bucket.return_value.blob.return_value = fake_blob
            call_command("cleanup_expired_reports")
        fake_blob.delete.assert_not_called()
        job.refresh_from_db()
        self.assertIn("gcs_path", job.result)

    def test_already_cleared_job_is_skipped(self):
        job = self._report("cleanup-cleared@example.com", gcs_path="reports/7/3.pdf")
        AsyncJob.objects.filter(pk=job.pk).update(
            completed_at=timezone.now() - timedelta(hours=25),
            result={"filename": "standard.pdf"},
        )
        fake_blob = mock.Mock()
        with mock.patch("google.cloud.storage.Client") as m_client:
            m_client.return_value.bucket.return_value.blob.return_value = fake_blob
            call_command("cleanup_expired_reports")
        fake_blob.delete.assert_not_called()
