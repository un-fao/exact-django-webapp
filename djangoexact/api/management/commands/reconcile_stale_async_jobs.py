import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from api.models import AsyncJob

logger = logging.getLogger(__name__)

STALE_THRESHOLD = timedelta(hours=1)

# Grace period before a failed PROJECT_COPY job's empty shell project is
# deleted. A client polling GET /api/async-jobs/{id}/ must still be able to
# read the failed status and error_message, attached to a real project,
# before the project link is removed.
ORPHAN_SHELL_GRACE = timedelta(hours=24)


class Command(BaseCommand):
    help = (
        "Fail AsyncJobs stuck in RUNNING beyond the task timeout, or stuck in "
        "PENDING beyond the same threshold (e.g. the dispatched container "
        "crashed before ever flipping the job to RUNNING). Also sweeps "
        "orphaned shell projects left behind by failed PROJECT_COPY jobs, "
        "once ORPHAN_SHELL_GRACE has elapsed since the job failed."
    )

    def handle(self, *args, **options):
        cutoff = timezone.now() - STALE_THRESHOLD
        stale = AsyncJob.objects.filter(
            Q(status=AsyncJob.Status.RUNNING, started_at__lt=cutoff)
            | Q(status=AsyncJob.Status.PENDING, created_at__lt=cutoff),
        )
        count = stale.update(
            status=AsyncJob.Status.FAILED,
            error_message=(
                "Marked failed: job did not complete within the task timeout "
                "(stale/stuck)."
            ),
            completed_at=timezone.now(),
        )
        self.stdout.write(f"Reconciled {count} stale AsyncJob(s).")

        deleted = self._sweep_orphaned_shells()
        self.stdout.write(f"Deleted {deleted} orphaned shell project(s) from failed copies.")

    def _sweep_orphaned_shells(self):
        """Delete the empty shell Project of a failed PROJECT_COPY AsyncJob,
        once the job has been failed for longer than ORPHAN_SHELL_GRACE.

        A FAILED row with a null completed_at is deliberately skipped: without
        that timestamp there is no anchor for the grace window, and every
        current failure path (dispatch, run_async_job, and the stale flip
        above) stamps completed_at, so this should not occur in practice.
        """
        cutoff = timezone.now() - ORPHAN_SHELL_GRACE
        candidates = AsyncJob.objects.filter(
            kind=AsyncJob.Kind.PROJECT_COPY,
            status=AsyncJob.Status.FAILED,
            completed_at__lt=cutoff,
            project__isnull=False,
        ).select_related("project")

        deleted = 0
        for job in candidates:
            try:
                params = job.params or {}
                # Only ever touch a copy destination, never a source project:
                # the linked project must be the recorded target, and must
                # not also be recorded as the source.
                if params.get("target_project_id") != job.project_id:
                    continue
                if params.get("source_project_id") == job.project_id:
                    continue
                project = job.project
                if project.activities.exists():
                    continue

                with transaction.atomic():
                    # Re-check inside the transaction: a project that gained
                    # an activity between selection and here must survive.
                    if project.activities.exists():
                        continue
                    # Unlink before delete: AsyncJob.project is CASCADE, so
                    # deleting first would take the failed job row with it.
                    # Being inside the atomic block also means a failing
                    # delete rolls the unlink back instead of orphaning the
                    # job with a dangling project reference.
                    job.project = None
                    # updated_at is auto_now: with update_fields it is only
                    # written if listed explicitly.
                    job.save(update_fields=["project", "updated_at"])
                    project.delete()
                deleted += 1
            except Exception as exc:
                logger.exception("Failed to sweep orphaned shell for AsyncJob %s: %s", job.pk, exc)
                continue

        return deleted
