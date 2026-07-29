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
        # google-cloud-run >=0.11 returns google.api_core.operation.Operation,
        # which does not expose `.name` directly. The Execution being built is
        # available as operation.metadata; its .name is the execution resource
        # path that we need for cancellation. Older versions used to expose
        # .name on the operation itself — assuming that here crashed dispatch
        # with AttributeError despite the underlying execution starting fine,
        # making jobs appear stuck at "pending".
        execution_name = getattr(getattr(operation, "metadata", None), "name", "") or ""
        logger.info(
            "Dispatched Cloud Run Job for job %d: %s", job_pk, execution_name,
        )
        from admin_scripts.models import ComputationJob
        ComputationJob.objects.filter(pk=job_pk).update(
            cloud_run_execution_name=execution_name,
        )
        return execution_name or None
    except Exception:
        logger.exception("Failed to dispatch Cloud Run Job for job %d", job_pk)
        return None


def cancel_cloud_run_job(execution_name: str) -> bool:
    """Cancel a running Cloud Run Job execution.

    Returns True on success, False on failure.
    """
    try:
        from google.cloud import run_v2
    except ImportError:
        logger.error("google-cloud-run not installed; cannot cancel execution.")
        return False

    client = run_v2.ExecutionsClient()
    request = run_v2.CancelExecutionRequest(name=execution_name)

    try:
        client.cancel_execution(request=request)
        logger.info("Cancelled Cloud Run execution: %s", execution_name)
        return True
    except Exception:
        logger.exception("Failed to cancel Cloud Run execution: %s", execution_name)
        return False
