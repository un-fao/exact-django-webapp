# Async Report Generation & Project Copy — Design Evaluation

**Date:** 2026-07-17
**Status:** Evaluated, direction locked (awaiting go-ahead to plan implementation)
**Requested by:** client ("make report generation and project copy asynchronous")

## Decision summary (locked)

| Decision | Choice |
|---|---|
| Async engine | Reuse the existing Cloud Run Jobs pattern (`admin_scripts.ComputationJob` machinery) |
| Job model | New generic `AsyncJob` table with a `kind` discriminator (report / project_copy) + JSON params |
| API contract | Additive: new `202`+poll endpoints, existing synchronous endpoints left untouched |
| Project copy | Optimize (batch the un-batched writes) so small copies stay synchronous; offload only large projects to a job |

Rationale: a production-deployed async job system already exists (Cloud Run Jobs + subprocess fallback + DB-tracked status + polling + stale-job reconciliation). Both new features share its shape (long-running, needs Cloud SQL, out-of-band result handoff, client polls). Reusing it means adding a model, an enqueue path, management commands, and JSON status endpoints, not standing up a new async platform. Celery/Redis and Cloud Tasks were both rejected as new infrastructure that does not pay for itself here.

## Current state (from codebase mapping)

### Report generation (synchronous today)
- Entry: `GET /api/projects/{pk}/report/?template=<name>&lang=<lang>&activities=<ids>` (`api/views.py:702`), delegates to `template()` (`api/views.py:1309`) when `?template=` is present (PDF), else builds Excel. Public mirror in `public/views.py:147/190`.
- Shared seam: `compute_project_result(project, activities)` -> format renderer (`api/reports/__init__.py`). Heavy cost is CPU: module calculators + WeasyPrint `write_pdf()` + matplotlib charts.
- Returns bytes in a single in-memory `HttpResponse`. No task queue, no GCS upload, no job/status model.
- Worker wrinkle: `render(request, ...)` needs a request object (used only for language) -> refactor to `render_to_string` + `activate(lang)`.

### Project copy (synchronous today)
- Entry: `POST /api/projects/{pk}/copy/` (`api/views.py:1180`) -> `utils.copy_project(project, user)` (`api/utilities.py:223`) -> `201` with full serialized project.
- Deep-copies Project -> every Activity -> every Module -> Submodules -> comment threads + comments, each `.save()`d individually; `simple_history` doubles the writes. Thousands of sequential INSERTs for large projects. No recompute triggered (cached results are deep-copied).
- Bugs to fix during the move: (1) membership double-create (created in `copy_project` AND again at `views.py:1197`); (2) the `views.py:1197` `ProjectMembership.create` runs OUTSIDE `copy_project`'s transaction (`ATOMIC_REQUESTS=False`), so a failure there leaves an orphaned committed project.

### Existing async infrastructure (to reuse)
- App: `admin_scripts`. Model `ComputationJob` (`admin_scripts/models.py:5`): status/progress/params/pid/cloud_run_execution_name/requested_by.
- Dispatch: `admin_scripts/cloud_run.py` `dispatch_cloud_run_job()` uses `run_v2.JobsClient().run_job()` with **container arg overrides** (`args=["python","manage.py","run_computation_job","--job-id",N]`). `CLOUD_RUN_JOB_NAME` is the full resource path.
- Selection: `admin_scripts/job_dispatcher.py` branches on `CLOUD_RUN_COMPUTATION_JOB_NAME` -> Cloud Run in prod, `subprocess.Popen` locally. Enqueue coalesces via SHA-256 hash + `transaction.on_commit(dispatch)`.
- Runner: `run_computation_job --job-id N` loads the row, marks running, computes, writes progress, marks terminal, `notify_job_completed()`. Refreshes DB connection after fork.
- Deployed job: `exact-computation-job`, image `gcr.io/$PROJECT/exact-computation-job`, `--memory=4Gi --cpu=2 --task-timeout=3600 --max-retries=0`, App Engine default SA, Cloud SQL attached. Built from `deploy/Dockerfile.computation_job` (`python:3.11-slim`), deployed in `.github/workflows/deploy.yaml` gated on `vars.CLOUD_RUN_COMPUTATION_JOB_NAME`.
- Status UI is HTMX partials polling every 3-5s. Stale jobs (>1h RUNNING) failed by `reconcile_stale_jobs`.
- Results handoff: job writes to GCS + DB; web app only polls the DB.

## Target architecture

Reuse the SAME `exact-computation-job` image (the dispatcher already overrides container args), so **no new Cloud Run Job resource is required**. Add a new command it can run.

### Shared foundation
- `AsyncJob` model (in `api`, so DRF serializers/endpoints are natural): `id`, `kind` (report | project_copy), `status`, `progress`, `params` (JSON), `result` (JSON: e.g. `{gcs_path, filename}` or `{new_project_id}`), `error_message`, `pid`, `cloud_run_execution_name`, `created_by`, `project` (nullable FK), timestamps. Migration in `api/migrations/`.
- `api/services/async_jobs.py`: `enqueue(kind, params, user, project)` + `dispatch(job_id)` mirroring `job_dispatcher.py`, running `["python","manage.py","run_async_job","--job-id",N]`; branch on a Cloud Run job-name setting (reuse `CLOUD_RUN_COMPUTATION_JOB_NAME` or add a generic alias), else `subprocess.Popen`. Fire via `transaction.on_commit`.
- `api/management/commands/run_async_job.py`: load `AsyncJob`, mark running, dispatch by `kind` to a handler, write `result`, mark terminal, notify. Reproduce the fork DB-connection hygiene.
- `AsyncJobViewSet` (DRF, read-only): `GET /api/async-jobs/{id}/` -> `{status, progress, result, ...}`, scoped so a user only sees their own jobs / jobs on projects they can access.
- Extend `reconcile_stale_jobs` (or a sibling command) to sweep `AsyncJob`. Confirm/add a Cloud Scheduler trigger.

### Report async
- Handler `generate_report_job(job)`: reproduce `template()`/`report()` (compute -> context -> `render_to_string` -> WeasyPrint or Excel), upload to `gs://{STORAGE_BUCKET}/reports/{project_id}/{job_id}.{ext}`, store path+filename in `result`.
- New endpoint `POST /api/projects/{pk}/report/async/?template=&lang=&activities=&format=` -> `202 {job_id}`. Existing sync `report/` untouched.
- Download: `GET /api/async-jobs/{id}/download/` streams the GCS blob (copy the attachment-download streaming pattern at `api/views.py:2819-2835`) to avoid appspot-SA signed-URL `signBlob` friction.
- Public report path (`public/views.py`) deferred unless the client needs it too.

### Project copy (optimize + hybrid)
- Optimize `copy_project`/`copy_activity`: batch inserts. CAUTION: `bulk_create` bypasses `Model.save()`, which currently drives `create_comment_threads()` and `simple_history` rows. Use `simple_history`'s `bulk_create_with_history` and create comment threads explicitly. This is the main correctness risk in the copy work.
- Fix the two membership bugs above; ensure the whole unit runs under one `transaction.atomic`.
- Size threshold: estimate activity+module count. Under threshold -> run the optimized copy inline and keep returning `201` (existing contract). Over threshold -> create the shell `Project` synchronously, return `202 {job_id, new_project_id}`, and let the job populate activities/modules and flip a readiness flag; client polls the job.
- New async endpoint alongside the existing sync `copy/`.

### Deploy / infra checklist
- `deploy/Dockerfile.computation_job`: add WeasyPrint native deps + fonts (`libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi8 shared-mime-info fonts-dejavu` and friends). Without fonts, PDFs render with wrong typography. The image has never needed these because LUC compute does not use WeasyPrint.
- Reuse the existing job resource; verify the rebuilt image ships the deps.
- GCS lifecycle rule on the `reports/` prefix to auto-delete after N days.
- IAM already sufficient: web SA can trigger executions (LUC proves it); job SA has Cloud SQL + GCS.
- Cost: a few cents per report (per-second Cloud Run billing); GCS negligible with cleanup.

## Open questions for planning
- App placement for `AsyncJob`: `api` (recommended, DRF-natural) vs generalizing `admin_scripts`.
- Report `params` shape and whether Excel async is in scope for v1 or PDF-only first.
- Copy size threshold value and whether the async-copy project is hidden until ready.
- Notifications: reuse `notify_job_completed` email path for these kinds?
- Do we async the public (unauthenticated) report endpoint in v1?

## Rejected alternatives
- **Cloud Tasks + warm Cloud Run worker:** lower latency for many small tasks, but adds a queue + a new service; the App Engine web service cannot be the long-task handler (gunicorn `--timeout 120`). Not worth it for two heavyweight operations.
- **Celery + Redis (Memorystore):** heaviest new infra; long-lived workers do not fit App Engine Standard.
