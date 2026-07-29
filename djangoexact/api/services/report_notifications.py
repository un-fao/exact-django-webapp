"""Send report outcome emails after an async report job finishes.

Two notifications live here: the "your report is ready" email on success (with a
signed, 24-hour download link, see report_links) and the "your report could not
be generated" email on failure (no link).

Best-effort and self-contained: each sender wraps its whole body in try/except,
so any failure (including an SMTP error, since sends now use fail_silently=False)
is logged and never raised to the caller, and a mail problem can never fail the
underlying job.
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

    No-op unless report emails are enabled, the job is a report kind, the
    requesting user has an email address, and BACKEND_BASE_URL is set (the link
    would be unusable without it). Never raises: any failure is logged (the send
    itself now uses fail_silently=False, so SMTP errors surface into the log)
    so the job outcome is unaffected.
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
        msg.send(fail_silently=False)
    except Exception:
        logger.exception("Failed to send report-ready email for job %s", job.pk)


def send_report_failed_email(job):
    """Email job.created_by that a report job could not be generated.

    No-op unless report emails are enabled, the job is a report kind, and the
    requesting user has an email address. Unlike the ready email this does not
    gate on BACKEND_BASE_URL: a failure email carries no download link, so it is
    still useful (and must send) even when BACKEND_BASE_URL is unset. Never
    raises: any failure is logged and never propagates to the caller.
    """
    if not settings.REPORT_READY_EMAIL_ENABLED:
        return
    if job.kind != AsyncJob.Kind.REPORT:
        return
    if job.created_by is None or not job.created_by.email:
        return

    try:
        context = {
            "user": job.created_by,
            "job": job,
            "project": job.project,
            "error_message": job.error_message,
        }
        subject = "Your EX-ACT report could not be generated"
        text_body = render_to_string("api/emails/report_failed.txt", context)
        html_body = render_to_string("api/emails/report_failed.html", context)
        msg = EmailMultiAlternatives(
            subject,
            text_body,
            settings.DEFAULT_FROM_EMAIL,
            [job.created_by.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
    except Exception:
        logger.exception("Failed to send report-failed email for job %s", job.pk)
