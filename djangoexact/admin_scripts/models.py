from django.conf import settings
from django.db import models


class ComputationJob(models.Model):
    """Tracks an async computation request for a scenario combination."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    # Coalescing key — SHA-256 of canonicalized parameters
    filters_hash = models.CharField(max_length=64, unique=True, db_index=True)

    # Parameters that define the computation
    module_type = models.CharField(max_length=255)
    attribute = models.CharField(max_length=255)
    from_value = models.CharField(max_length=255)
    to_value = models.CharField(max_length=255)
    filters = models.JSONField(default=dict, blank=True)

    # Process tracking (for cancellation)
    pid = models.IntegerField(null=True, blank=True)
    cloud_run_execution_name = models.CharField(max_length=512, blank=True, default="")

    # State
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(blank=True, default="")
    progress = models.PositiveSmallIntegerField(default=0)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Users subscribed to this job (for notifications)
    requested_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="computation_jobs",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["module_type", "attribute"]),
        ]

    def __str__(self):
        return f"{self.module_type}/{self.attribute} [{self.status}]"
