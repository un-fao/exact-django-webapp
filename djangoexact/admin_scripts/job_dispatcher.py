"""Job coalescing and dispatch for ComputationJob."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from admin_scripts.models import ComputationJob

logger = logging.getLogger(__name__)


def compute_filters_hash(params: dict) -> str:
    """Compute a deterministic SHA-256 hash of canonicalized job parameters.

    Parameters
    ----------
    params:
        Must contain keys: module_type, attribute, from_value, to_value.
        May contain: filters (dict), max_rows (int or None),
        force_key (str or None). max_rows and force_key are included in
        the canonical JSON only when their value is not None, so omission
        and None are equivalent and the hash stays backward-compatible
        with rows created before these keys existed.
    """
    canonical_dict = {
        "module_type": params["module_type"],
        "attribute": params["attribute"],
        "from_value": params["from_value"],
        "to_value": params["to_value"],
        "filters": params.get("filters", {}),
    }
    max_rows = params.get("max_rows")
    if max_rows is not None:
        canonical_dict["max_rows"] = max_rows
    force_key = params.get("force_key")
    if force_key is not None:
        canonical_dict["force_key"] = force_key
    canonical = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def enqueue_or_join(user, module_type, attribute, from_value, to_value, filters=None):
    """Enqueue a new computation job or subscribe to an existing one.

    Uses select_for_update + transaction.on_commit to ensure only one
    Cloud Run execution is triggered per unique combination.

    Returns the ComputationJob instance (created or existing).
    """
    params = {
        "module_type": module_type,
        "attribute": attribute,
        "from_value": from_value,
        "to_value": to_value,
        "filters": filters or {},
    }
    filters_hash = compute_filters_hash(params)

    with transaction.atomic():
        try:
            job = (
                ComputationJob.objects
                .select_for_update()
                .get(filters_hash=filters_hash)
            )
        except ComputationJob.DoesNotExist:
            job = ComputationJob.objects.create(
                filters_hash=filters_hash,
                module_type=module_type,
                attribute=attribute,
                from_value=from_value,
                to_value=to_value,
                filters=filters or {},
            )
            transaction.on_commit(lambda: dispatch_job(job.pk))

        job.requested_by.add(user)

    return job


def dispatch_job(job_pk):
    """Dispatch a computation job.

    Uses Cloud Run Jobs if settings.CLOUD_RUN_COMPUTATION_JOB_NAME is set,
    otherwise falls back to a local subprocess.
    """
    from admin_scripts.cloud_run import CLOUD_RUN_JOB_NAME

    if CLOUD_RUN_JOB_NAME:
        from admin_scripts.cloud_run import dispatch_cloud_run_job
        dispatch_cloud_run_job(job_pk)
    else:
        # EXACT_JOB_LOG_DIR overrides; otherwise BASE_DIR/logs (writable on local
        # dev). On read-only deploys (e.g. App Engine Standard) BASE_DIR lives
        # under /workspace, so fall back to a temp dir to keep dispatch working.
        log_dir = Path(os.environ.get("EXACT_JOB_LOG_DIR") or settings.BASE_DIR / "logs")
        try:
            log_dir.mkdir(exist_ok=True, parents=True)
        except OSError:
            log_dir = Path(tempfile.gettempdir()) / "exact_job_logs"
            log_dir.mkdir(exist_ok=True, parents=True)
        log_file = log_dir / f"job_{job_pk}.log"
        logger.info("Dispatching local job %d, logging to %s", job_pk, log_file)
        fh = open(log_file, "w")  # noqa: SIM115 — intentionally kept open for subprocess lifetime
        proc = subprocess.Popen(
            [sys.executable, "manage.py", "run_computation_job", "--job-id", str(job_pk)],
            stdout=fh,
            stderr=fh,
            start_new_session=True,
        )
        ComputationJob.objects.filter(pk=job_pk).update(pid=proc.pid)


def cancel_job(job_pk):
    """Cancel a pending or running computation job.

    Terminates the local process group (if any) and cancels the Cloud Run
    execution (if any), then marks the job as cancelled.

    Returns True if the job was cancelled, False if it was not cancellable.
    """
    job = ComputationJob.objects.get(pk=job_pk)
    if job.status not in (ComputationJob.Status.PENDING, ComputationJob.Status.RUNNING):
        return False

    # Kill local process group
    if job.pid:
        try:
            os.killpg(os.getpgid(job.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass  # process already exited

    # Cancel Cloud Run execution
    if job.cloud_run_execution_name:
        from admin_scripts.cloud_run import cancel_cloud_run_job
        cancel_cloud_run_job(job.cloud_run_execution_name)

    job.status = ComputationJob.Status.CANCELLED
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_at", "updated_at"])
    return True
