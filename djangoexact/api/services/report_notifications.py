"""Send the "your report is ready" email after an async report job completes.

Best-effort and self-contained: the whole body is wrapped in try/except and any
failure is logged and swallowed, so a mail problem can never fail the underlying
job. The email carries a signed, 24-hour download link (see report_links) so the
recipient can download straight from their inbox with no login.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from api.models import AsyncJob
from api.services import report_links

logger = logging.getLogger("console")

EXPIRY_HOURS = 24


def send_report_ready_email(job):
    """Email job.created_by a tokenized download link for a completed report.

    No-op unless report emails are enabled, the job is a report kind, and the
    requesting user has an email address. Never raises: any failure is logged
    and swallowed so the job outcome is unaffected.
    """
    if not settings.REPORT_READY_EMAIL_ENABLED:
        return
    if job.kind != AsyncJob.Kind.REPORT:
        return
    if job.created_by is None or not job.created_by.email:
        return
    if not settings.BACKEND_BASE_URL:
        # The link would be schemeless and unusable from an inbox. Skipping is
        # safer than emailing a broken download link; ops must set this per env.
        logger.warning(
            "BACKEND_BASE_URL is not set; skipping report-ready email for job %s.",
            job.pk,
        )
        return

    try:
        url = report_links.build_download_url(job)
        context = {
            "user": job.created_by,
            "job": job,
            "project": job.project,
            "download_url": url,
            "filename": (job.result or {}).get("filename", "report"),
            "expiry_hours": EXPIRY_HOURS,
        }
        subject = "Your EX-ACT report is ready to download"
        text_body = render_to_string("api/emails/report_ready.txt", context)
        html_body = render_to_string("api/emails/report_ready.html", context)
        msg = EmailMultiAlternatives(
            subject,
            text_body,
            settings.DEFAULT_FROM_EMAIL,
            [job.created_by.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=True)
    except Exception:
        logger.exception("Failed to send report-ready email for job %s", job.pk)
