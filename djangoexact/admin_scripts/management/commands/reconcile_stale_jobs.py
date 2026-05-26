"""Reconcile stale ComputationJobs that may have lost their completion signal."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from admin_scripts.models import ComputationJob

logger = logging.getLogger(__name__)

# Jobs running longer than this are considered stale
STALE_THRESHOLD = timedelta(hours=1)


class Command(BaseCommand):
    help = "Mark stale running ComputationJobs as failed"

    def handle(self, *args, **options):
        cutoff = timezone.now() - STALE_THRESHOLD
        stale_jobs = ComputationJob.objects.filter(
            status=ComputationJob.Status.RUNNING,
            started_at__lt=cutoff,
        )

        count = stale_jobs.count()
        if count == 0:
            self.stdout.write("No stale jobs found.")
            return

        for job in stale_jobs:
            job.status = ComputationJob.Status.FAILED
            job.error_message = "Marked as failed by reconcile_stale_jobs (exceeded 1 hour)"
            job.completed_at = timezone.now()
            job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])

            from admin_scripts.notifications import notify_job_completed
            notify_job_completed(job)

            self.stdout.write(f"Marked job #{job.pk} as failed (stale)")

        self.stdout.write(self.style.SUCCESS(f"Reconciled {count} stale job(s)."))
