"""Management command to run a single ComputationJob."""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from admin_scripts.models import ComputationJob

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run a single ComputationJob by primary key"

    def add_arguments(self, parser):
        parser.add_argument(
            "--job-id",
            type=int,
            required=True,
            help="Primary key of the ComputationJob to run",
        )

    def handle(self, *args, **options):
        job_id = options["job_id"]

        try:
            job = ComputationJob.objects.get(pk=job_id)
        except ComputationJob.DoesNotExist:
            raise CommandError(f"ComputationJob {job_id} not found")

        if job.status == ComputationJob.Status.CANCELLED:
            self.stderr.write(f"Job {job_id} was cancelled. Skipping.")
            return

        if job.status != ComputationJob.Status.PENDING:
            self.stderr.write(
                f"Job {job_id} is '{job.status}', expected 'pending'. Skipping."
            )
            return

        # Mark as running
        job.status = ComputationJob.Status.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])

        self.stdout.write(
            f"Running job {job_id}: {job.module_type}/{job.attribute} "
            f"({job.from_value} → {job.to_value})"
        )

        try:
            self._run_computation(job)

            job.status = ComputationJob.Status.COMPLETED
            job.completed_at = timezone.now()
            job.save(update_fields=["status", "completed_at", "updated_at"])

            from admin_scripts.notifications import notify_job_completed
            notify_job_completed(job)

            self.stdout.write(self.style.SUCCESS(f"Job {job_id} completed."))

        except Exception as exc:
            logger.exception("Job %d failed", job_id)
            # Ensure DB connection is fresh before saving failure status —
            # the fork-based pool may have caused a stale connection.
            from django.db import connection
            connection.ensure_connection()
            job.status = ComputationJob.Status.FAILED
            job.error_message = str(exc)
            job.completed_at = timezone.now()
            job.save(
                update_fields=["status", "error_message", "completed_at", "updated_at"]
            )

            from admin_scripts.notifications import notify_job_completed
            notify_job_completed(job)

            raise CommandError(f"Job {job_id} failed: {exc}")

    def _run_computation(self, job):
        """Run the actual computation for a job."""
        from api.services.minitool_compute import compute_module_slice

        def _update_progress(pct):
            from django.db import connection
            if connection.connection and not connection.is_usable():
                connection.close()
            from admin_scripts.models import ComputationJob
            ComputationJob.objects.filter(pk=job.pk).update(progress=pct)

        data, errors = compute_module_slice(
            module_type=job.module_type,
            attribute=job.attribute,
            from_value=job.from_value,
            to_value=job.to_value,
            chunk_size=10000,
            max_rows=job.max_rows or 10000,
            max_workers=None,
            save_results=True,
            progress_callback=_update_progress,
        )

        self.stdout.write(
            f"  Results: {len(data)} successful, {len(errors)} errors"
        )

        if errors and not data:
            raise RuntimeError(
                f"All {len(errors)} permutations failed. "
                f"First error: {errors[0]}"
            )
