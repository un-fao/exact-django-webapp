"""Cloud Run Jobs client for dispatching computation jobs."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Cloud Run Job name — empty string means "use subprocess fallback"
CLOUD_RUN_JOB_NAME = getattr(settings, "CLOUD_RUN_COMPUTATION_JOB_NAME", "")
CLOUD_RUN_REGION = getattr(settings, "CLOUD_RUN_REGION", "europe-west1")


def dispatch_cloud_run_job(job_pk: int) -> str | None:
    """Dispatch a Cloud Run Job execution for the given ComputationJob pk.

    Returns the execution name on success, or None on failure.
    Requires ``google-cloud-run`` package.
    """
    try:
        from google.cloud import run_v2
    except ImportError:
        logger.error(
            "google-cloud-run not installed. "
            "Install it or clear CLOUD_RUN_COMPUTATION_JOB_NAME to use subprocess."
        )
        return None

    client = run_v2.JobsClient()

    overrides = run_v2.RunJobRequest.Overrides(
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                args=["python", "manage.py", "run_computation_job", "--job-id", str(job_pk)],
            ),
        ],
    )

    request = run_v2.RunJobRequest(
        name=CLOUD_RUN_JOB_NAME,
        overrides=overrides,
    )

    try:
        operation = client.run_job(request=request)
        logger.info("Dispatched Cloud Run Job for job %d: %s", job_pk, operation.name)
        return operation.name
    except Exception:
        logger.exception("Failed to dispatch Cloud Run Job for job %d", job_pk)
        return None
