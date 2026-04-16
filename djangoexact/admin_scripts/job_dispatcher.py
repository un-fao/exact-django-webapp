"""Job coalescing and dispatch for ComputationJob."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys

from django.db import transaction

from admin_scripts.models import ComputationJob


def compute_filters_hash(params: dict) -> str:
    """Compute a deterministic SHA-256 hash of canonicalized job parameters.

    Parameters
    ----------
    params:
        Must contain keys: module_type, attribute, from_value, to_value.
        May contain: filters (dict).
    """
    canonical = json.dumps(
        {
            "module_type": params["module_type"],
            "attribute": params["attribute"],
            "from_value": params["from_value"],
            "to_value": params["to_value"],
            "filters": params.get("filters", {}),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
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
    """Dispatch a computation job via subprocess (local fallback).

    In production, this will be replaced by Cloud Run Job dispatch (PR 6).
    """
    subprocess.Popen(
        [sys.executable, "manage.py", "run_computation_job", "--job-id", str(job_pk)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
