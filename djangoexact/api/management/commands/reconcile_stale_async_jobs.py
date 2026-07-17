from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from api.models import AsyncJob

STALE_THRESHOLD = timedelta(hours=1)


class Command(BaseCommand):
    help = (
        "Fail AsyncJobs stuck in RUNNING beyond the task timeout, or stuck in "
        "PENDING beyond the same threshold (e.g. the dispatched container "
        "crashed before ever flipping the job to RUNNING)."
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
