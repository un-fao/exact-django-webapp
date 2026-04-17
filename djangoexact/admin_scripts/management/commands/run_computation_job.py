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

            self.stdout.write(self.style.SUCCESS(f"Job {job_id} completed."))

        except Exception as exc:
            logger.exception("Job %d failed", job_id)
            job.status = ComputationJob.Status.FAILED
            job.error_message = str(exc)
            job.completed_at = timezone.now()
            job.save(
                update_fields=["status", "error_message", "completed_at", "updated_at"]
            )
            raise CommandError(f"Job {job_id} failed: {exc}")

    def _run_computation(self, job):
        """Run the actual computation for a job.

        PR 5 will replace this with compute_module_slice() extracted
        from compute_minitool. For now, this is a placeholder that
        validates the job parameters against MODULE_CONFIGS.
        """
        from api.minitool import MODULE_CONFIGS

        if job.module_type not in MODULE_CONFIGS:
            raise ValueError(
                f"Unknown module_type '{job.module_type}'. "
                f"Valid: {sorted(MODULE_CONFIGS.keys())}"
            )

        config = MODULE_CONFIGS[job.module_type]
        config_fields = config.get("fields", {})

        # Validate the attribute exists
        attr_start = f"{job.attribute}_start"
        if attr_start not in config_fields and job.attribute not in config_fields:
            raise ValueError(
                f"Unknown attribute '{job.attribute}' for module '{job.module_type}'"
            )

        self.stdout.write(
            f"  Module: {job.module_type} (config_name: {config.get('config_name')})"
        )
        self.stdout.write(f"  Attribute: {job.attribute}")
        self.stdout.write(
            "  Computation placeholder — PR 5 adds compute_module_slice"
        )
