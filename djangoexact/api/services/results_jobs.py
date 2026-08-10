"""Worker handler for asynchronous project results recompute (AsyncJob kind
RESULTS_RECOMPUTE).

Reproduces the request path (ProjectViewSet.results) rather than reimplementing the
assembly, so the warmed payload cannot drift from what the endpoint would compute on a
live miss. The view itself performs the cache write via api.results_cache.write, so
run() below never writes the cache a second time.
"""
import logging

from django.db import transaction

log = logging.getLogger("console")


def schedule_recompute(project_id):
    """Enqueue a RESULTS_RECOMPUTE job after the current transaction commits.

    Returns immediately unless settings.RESULTS_RECOMPUTE_ENABLED. Post-commit is
    mandatory, never inline in the caller's save/update: running post-commit is what
    lets the callback read the FINAL stamp after every bump made in that transaction,
    mirroring api/services/async_jobs.py enqueue().
    """
    from django.conf import settings

    if not settings.RESULTS_RECOMPUTE_ENABLED:
        return
    transaction.on_commit(lambda: _enqueue_if_idle(project_id))


def _enqueue_if_idle(project_id):
    """Enqueue a RESULTS_RECOMPUTE job for project_id, unless one is already
    PENDING or RUNNING (D2 dedupe). Served by the (kind, status) index on AsyncJob.

    Wrapped in try/except: a failure to warm a cache must never surface as a request
    error, since this runs after commit on a user's write.
    """
    try:
        from api.models import AsyncJob, Project
        from api.services import async_jobs

        already_queued = AsyncJob.objects.filter(
            project_id=project_id,
            kind=AsyncJob.Kind.RESULTS_RECOMPUTE,
            status__in=[AsyncJob.Status.PENDING, AsyncJob.Status.RUNNING],
        ).exists()
        if already_queued:
            return

        project = Project.objects.filter(pk=project_id).first()
        if project is None:
            return

        # Recording the stamp in params is what lets a late worker detect it was
        # superseded by a later edit and exit without writing (D2).
        async_jobs.enqueue(
            kind=AsyncJob.Kind.RESULTS_RECOMPUTE,
            params={"project_id": project_id, "results_stamp": project.results_stamp},
            project=project,
        )
    except Exception as e:
        log.exception(e)


def is_superseded(job_stamp, current_stamp) -> bool:
    """Pure predicate, kept separate from run() so it is testable without a database."""
    return job_stamp is not None and current_stamp != job_stamp


def run(job) -> dict:
    """Recompute and warm the project results cache for job.params['project_id'].

    Exits without writing if a newer edit has already superseded this job's stamp.
    Deliberately does NOT switch the active locale (django.utils.translation) the way
    api/services/report_jobs.py does for its own job kind: doing so here would write a
    localized payload into a cache key that assumes settings.LANGUAGE_CODE (see
    api/results_cache.build_cache_key), and would then serve non-English text to every
    caller. The omission is intentional, not an oversight.
    """
    from api.models import Project
    from api.views import ProjectViewSet

    params = job.params
    project = Project.objects.get(pk=params["project_id"])

    current_stamp = project.results_stamp
    job_stamp = params.get("results_stamp")
    if is_superseded(job_stamp, current_stamp):
        return {"skipped": "superseded", "job_stamp": job_stamp, "current_stamp": current_stamp}

    request = _build_results_request(project)
    view = ProjectViewSet()
    view.request = request
    view.format_kwarg = None
    view.kwargs = {"pk": project.pk}

    response = view.results(request, pk=project.pk)

    if response.status_code != 200:
        raise RuntimeError(f"Results recompute for project {project.pk} got status {response.status_code}")

    return {"project_id": project.pk, "results_stamp": current_stamp, "status_code": response.status_code}


def _build_results_request(project):
    """Build a DRF Request that ProjectViewSet.results can run off-request.

    Warms only the all-activities key (no "activities" query param), which is the key
    the endpoint serves by default. project.owner passes check_permission("view_project",
    ...) (an Admin-group membership is created for the owner on project creation), and
    the research verified the payload carries no per-user field, so the actor choice
    cannot leak into the bytes.
    """
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory, force_authenticate

    from api.views import ProjectViewSet

    factory = APIRequestFactory()
    django_request = factory.get(f"/api/projects/{project.pk}/results/")
    force_authenticate(django_request, user=project.owner)

    view = ProjectViewSet()
    request = Request(django_request, parsers=view.get_parsers())
    request.user = project.owner
    return request
