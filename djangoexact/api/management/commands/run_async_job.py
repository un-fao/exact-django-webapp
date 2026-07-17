import logging

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from api.models import AsyncJob

log = logging.getLogger("console")


class Command(BaseCommand):
    help = "Execute a queued AsyncJob by id (report generation or project copy)."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", type=int, required=True)

    def handle(self, *args, **options):
        job_id = options["job_id"]
        job = AsyncJob.objects.get(pk=job_id)

        if job.status != AsyncJob.Status.PENDING:
            # Cancelled or already handled: do nothing (idempotent re-dispatch guard).
            self.stdout.write(f"Job {job_id} is {job.status}; skipping.")
            return

        job.status = AsyncJob.Status.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])

        try:
            if job.kind == AsyncJob.Kind.REPORT:
                from api.services import report_jobs
                result = report_jobs.run(job)
            elif job.kind == AsyncJob.Kind.PROJECT_COPY:
                from api.services import copy_jobs
                result = copy_jobs.run(job)
            else:
                raise ValueError(f"Unknown AsyncJob kind: {job.kind}")

            job.result = result or {}
            job.status = AsyncJob.Status.COMPLETED
            job.progress = 100
        except Exception as e:
            # The container may have forked from the web app; the inherited DB
            # connection can be unusable. Drop it so the status write reconnects.
            # Skip inside an atomic block (e.g. TestCase) where closing would
            # poison the connection the finally-block save still needs.
            if not connection.in_atomic_block:
                connection.close()
            log.exception(e)
            job.status = AsyncJob.Status.FAILED
            job.error_message = str(e)[:2000]
        finally:
            job.completed_at = timezone.now()
            job.save(update_fields=[
                "status", "progress", "result", "error_message",
                "completed_at", "updated_at",
            ])
