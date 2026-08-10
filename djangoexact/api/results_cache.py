"""Project-level cache for GET /api/projects/{id}/results/.

Keeps module-level imports out of this file (models are imported inside each
function), mirroring the local-import style already used in
api/management/commands/run_async_job.py, so this module can be imported early
without triggering app-registry loading.
"""
from __future__ import annotations

import hashlib
import json

# Bumped whenever the assembly or the computation semantics of the project results
# payload changes. Forgetting to bump this means every existing project keeps serving a
# payload built by the old code, because a matching cache_key short-circuits the compute.
#
# This is the ONE deliberate exception to "an untouched project is preserved as it is":
# bumping it force-recomputes every project without any user action, so reserve it for
# fixing a defect in our own code (the precedent is INVENTORY_SCHEMA_VERSION in
# api/reports/cache.py, added exactly that way). Never bump it to propagate a reference
# data change: new IPCC factors must not rewrite an appraisal a user already ran.
RESULTS_SCHEMA_VERSION = 1


def build_cache_key(activity_pks) -> str:
    """Build a stable, deterministic cache key for a project results request.

    Normalizes the activity pk collection so that duplicate ids and ordering never
    create a second cache entry (?activities=2,1 and ?activities=1,2 collapse to the
    same key). Folds in RESULTS_SCHEMA_VERSION and INVENTORY_SCHEMA_VERSION so a change
    to either invalidates every existing key without needing a stamp bump.

    Deliberately excludes user identity and language: ProjectResultSerializer is an
    empty serializer (api/serializers.py), so the payload carries no per-user field, and
    the thread fan-out already forces settings.LANGUAGE_CODE for every caller.

    Deliberately excludes any reference-data epoch, and that is a product rule rather
    than an oversight. Reloading IPCC factors or GWP coefficients must NOT retroactively
    change a project a user already computed: an appraisal is a record of what the
    numbers were when it was run. An untouched project keeps its payload until the user
    edits something, so the only inputs that can move a project off its cached result
    are the user's own edits (via results_stamp) and a deliberate operator sweep
    (scripts/invalidate_results_cache.py).
    """
    from api.reports.cache import INVENTORY_SCHEMA_VERSION

    normalized_pks = sorted({int(pk) for pk in activity_pks})
    descriptor = f"{RESULTS_SCHEMA_VERSION}:{INVENTORY_SCHEMA_VERSION}:{','.join(str(pk) for pk in normalized_pks)}"
    return hashlib.sha256(descriptor.encode("utf-8")).hexdigest()


def normalize_payload(response):
    """Round-trip a response dict through DRF's JSON encoder to plain JSON types.

    Uses rest_framework.utils.encoders.JSONEncoder specifically, not
    DjangoJSONEncoder, because DRF's JSONRenderer renders with it, so the stored
    payload is guaranteed to render to the same bytes as the live object (Decimal,
    datetime, and any other DRF-special type is normalized the same way).
    """
    from rest_framework.utils.encoders import JSONEncoder

    return json.loads(json.dumps(response, cls=JSONEncoder))


def read(project_id, cache_key: str, stamp: int):
    """Read a stored payload, or None on a miss.

    Filtering on results_stamp=stamp means a row written before a later edit is never
    selected: the stamp mismatch alone rules it out. No delete race, no explicit
    staleness check needed.
    """
    from api.models import ProjectResultCache

    return (
        ProjectResultCache.objects
        .filter(project_id=project_id, cache_key=cache_key, results_stamp=stamp, schema_version=RESULTS_SCHEMA_VERSION)
        .values_list("payload", flat=True)
        .first()
    )


def write(project_id, cache_key: str, stamp: int, payload):
    """Store (or replace) the payload for this project/cache_key pair."""
    from api.models import ProjectResultCache

    ProjectResultCache.objects.update_or_create(
        project_id=project_id,
        cache_key=cache_key,
        defaults={
            "results_stamp": stamp,
            "schema_version": RESULTS_SCHEMA_VERSION,
            "payload": payload,
        },
    )


def clear_for_projects(project_qs):
    """Delete all stored ProjectResultCache rows for every project in project_qs.

    Used by the manual ops invalidation lever (scripts/invalidate_results_cache.py).
    """
    from api.models import ProjectResultCache

    return ProjectResultCache.objects.filter(project__in=project_qs).delete()
