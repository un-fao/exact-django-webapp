import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import AsyncJob

log = logging.getLogger("console")

EXPIRY = timedelta(hours=24)


class Command(BaseCommand):
    help = (
        "Delete report files from GCS once their AsyncJob has been completed "
        "for more than 24 hours, then clear the stored gcs_path so the download "
        "endpoint 404s afterward. Precise 24h enforcement complementing the "
        "coarser (day-granularity, asynchronous) bucket lifecycle rule. "
        "Idempotent: jobs whose gcs_path is already cleared are skipped."
    )

    def handle(self, *args, **options):
        cutoff = timezone.now() - EXPIRY
        expired = AsyncJob.objects.filter(
            kind=AsyncJob.Kind.REPORT,
            status=AsyncJob.Status.COMPLETED,
            completed_at__lt=cutoff,
        )

        cleaned = 0
        for job in expired:
            result = job.result or {}
            gcs_path = result.get("gcs_path")
            if not gcs_path:
                continue
            try:
                from google.cloud import storage

                client = storage.Client()
                bucket = client.bucket(settings.STORAGE_BUCKET)
                bucket.blob(gcs_path).delete()
            except Exception as e:
                # One blob failing (already gone, transient GCS error) must not
                # abort the whole sweep; leave gcs_path so a later run retries.
                log.exception(e)
                continue
            result.pop("gcs_path", None)
            job.result = result
            job.save(update_fields=["result", "updated_at"])
            cleaned += 1

        self.stdout.write(f"Cleaned {cleaned} expired report file(s).")
