from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import AsyncJob

STALE_THRESHOLD = timedelta(hours=1)


class Command(BaseCommand):
    help = "Fail AsyncJobs stuck in RUNNING beyond the task timeout."

    def handle(self, *args, **options):
        cutoff = timezone.now() - STALE_THRESHOLD
        stale = AsyncJob.objects.filter(
            status=AsyncJob.Status.RUNNING, started_at__lt=cutoff,
        )
        count = stale.update(
            status=AsyncJob.Status.FAILED,
            error_message="Marked failed: job stale (exceeded task timeout without completing).",
            completed_at=timezone.now(),
        )
        self.stdout.write(f"Reconciled {count} stale AsyncJob(s).")
