"""Enqueue and dispatch for AsyncJob.

Mirrors admin_scripts.job_dispatcher but targets the generic AsyncJob model and
runs `manage.py run_async_job --job-id N`. Reuses the same deployed Cloud Run Job
(exact-computation-job) by overriding the container args, so no new GCP job
resource is required.
"""
import logging
import os
import subprocess
import sys
import tempfile

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.models import AsyncJob

log = logging.getLogger("console")


def enqueue(kind, params, user=None, project=None):
    """Create a pending AsyncJob and schedule its dispatch after commit."""
    job = AsyncJob.objects.create(
        kind=kind, params=params, created_by=user, project=project,
    )
    transaction.on_commit(lambda: dispatch(job.pk))
    return job


def dispatch(job_pk):
    """Start the worker for a queued job: Cloud Run in prod, subprocess locally."""
    job_name = getattr(settings, "CLOUD_RUN_COMPUTATION_JOB_NAME", "") or ""
    if job_name:
        _dispatch_cloud_run(job_pk)
    else:
        _dispatch_subprocess(job_pk)


def _dispatch_cloud_run(job_pk):
    try:
        from google.cloud import run_v2

        client = run_v2.JobsClient()
        overrides = run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    args=["python", "manage.py", "run_async_job", "--job-id", str(job_pk)],
                ),
            ],
        )
        request = run_v2.RunJobRequest(
            name=settings.CLOUD_RUN_COMPUTATION_JOB_NAME, overrides=overrides,
        )
        operation = client.run_job(request=request)
    except Exception as e:
        log.exception(e)
        AsyncJob.objects.filter(pk=job_pk).update(
            status=AsyncJob.Status.FAILED,
            error_message=f"Cloud Run dispatch failed: {e}"[:2000],
            completed_at=timezone.now(),
        )
        return

    execution_name = ""
    try:
        # google-cloud-run >= 0.11 returns an Operation whose metadata carries
        # the execution resource name (the Operation itself has no .name).
        execution_name = operation.metadata.name
    except Exception as e:  # pragma: no cover - defensive, mirrors admin_scripts
        log.warning("Could not read Cloud Run execution name for job %s: %s", job_pk, e)
    if execution_name:
        AsyncJob.objects.filter(pk=job_pk).update(cloud_run_execution_name=execution_name)


def _dispatch_subprocess(job_pk):
    log_dir = os.environ.get("EXACT_JOB_LOG_DIR")
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            log_dir = tempfile.gettempdir()
    else:
        base = getattr(settings, "BASE_DIR", None)
        candidate = os.path.join(str(base), "logs") if base else None
        try:
            if candidate:
                os.makedirs(candidate, exist_ok=True)
                log_dir = candidate
        except OSError:
            log_dir = None
    if not log_dir:
        log_dir = tempfile.gettempdir()
    log_path = os.path.join(log_dir, f"async_job_{job_pk}.log")

    fh = open(log_path, "a")  # closed by the child process lifetime; matches admin_scripts
    proc = subprocess.Popen(
        [sys.executable, "manage.py", "run_async_job", "--job-id", str(job_pk)],
        stdout=fh, stderr=fh, start_new_session=True,
    )
    AsyncJob.objects.filter(pk=job_pk).update(pid=proc.pid)
