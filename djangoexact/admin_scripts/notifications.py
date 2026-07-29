"""Notification fan-out for completed ComputationJobs."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from admin_scripts.models import ComputationJob

logger = logging.getLogger(__name__)

JOB_NOTIFICATIONS_ENABLED = getattr(settings, "JOB_NOTIFICATIONS_ENABLED", False)


def notify_job_completed(job: ComputationJob) -> None:
    """Fan out notifications for a completed job.

    Called after a job transitions to COMPLETED or FAILED.
    Sends email to all subscribed users for jobs that ran > 2 minutes.
    """
    if not JOB_NOTIFICATIONS_ENABLED:
        return

    # Only email for jobs that took more than 2 minutes
    if job.started_at and job.completed_at:
        duration = (job.completed_at - job.started_at).total_seconds()
        if duration < 120:
            return

    subject = f"Computation Job #{job.pk} {job.get_status_display()}"

    for user in job.requested_by.all():
        if not user.email:
            continue
        try:
            body = render_to_string(
                "admin_scripts/emails/job_completed.txt",
                {"job": job, "user": user},
            )
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Failed to send notification to %s for job %d", user.email, job.pk)
