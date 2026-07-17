# Async Jobs (Report Generation and Project Copy)

This guide documents the operational picture for the generic `AsyncJob` background-job
system: what it is, which endpoints drive it, how it executes, how stale jobs get cleaned
up, and how generated report files get purged from storage.

## The `AsyncJob` model

`AsyncJob` (`api/models.py`) is a generic, non-historical background job row. It is
intentionally not tracked by `simple_history`: rows are ephemeral operational state, the
same pattern already used by `admin_scripts.ComputationJob`.

Fields of note: `kind`, `status`, `progress`, `params` (JSON, the job's input), `result`
(JSON, set on completion), `error_message`, `pid` (subprocess dispatch only),
`cloud_run_execution_name` (Cloud Run dispatch only), `created_by`, `project`,
`created_at` / `updated_at` / `started_at` / `completed_at`.

`kind` (`AsyncJob.Kind`):

- `report`: background report generation (PDF or Excel).
- `project_copy`: background copy of a large project.

`status` lifecycle (`AsyncJob.Status`):

```text
pending -> running -> completed
                    -> failed
pending -> cancelled
```

A job is created as `pending`. `run_async_job` (see below) flips it to `running` when the
worker picks it up, then to `completed` or `failed` once the work finishes or raises. A
job can also end in `cancelled` if it is never dispatched or picked up (the worker treats
any non-`pending` job it is asked to run as a no-op, so a cancelled job cannot be
resurrected by a stray re-dispatch).

## Endpoints

All async endpoints are additive: the existing synchronous `report/` and `copy/` actions
on `ProjectViewSet` are unchanged, and existing clients that only know about them keep
working exactly as before.

- `POST /api/projects/{pk}/report/async/` (`ProjectViewSet.report_async`, in
  `api/views.py`)
  Enqueues report generation and returns immediately with `202 Accepted` and
  `{"job_id": <id>, "status": "pending"}`. Query params mirror the sync `report/` action
  (`activities`, `template`, `lang`, `format`).

- `POST /api/projects/{pk}/copy/async/` (`ProjectViewSet.copy_async`, in `api/views.py`)
  "Smart" copy. Counts the source project's activities plus module types across those
  activities. If the total is at or below `PROJECT_COPY_ASYNC_THRESHOLD` (see below), the
  copy runs inline in the request and returns `201 Created` with the full new project body
  (identical shape to the legacy `copy/` action). If the total exceeds the threshold, the
  view creates an empty "shell" project synchronously (so the client gets a real project id
  immediately), enqueues an `AsyncJob` of kind `project_copy` to populate it, and returns
  `202 Accepted` with `{"job_id": <id>, "new_project_id": <id>, "status": "pending"}`.
  Callers must handle both response codes.

- `GET /api/async-jobs/{id}/` (`AsyncJobViewSet`, read-only, in `api/views.py`)
  Poll a job's status. Scoped to `created_by=request.user`: a job created by one user
  404s for every other user, including staff (no elevated-access branch exists here).
  Returns the serialized `AsyncJob` (`kind`, `status`, `progress`, `result`,
  `error_message`, timestamps, `project`).

- `GET /api/async-jobs/{id}/download/` (`AsyncJobViewSet.download`)
  Streams the generated report back as an attachment once the job is `completed`. Returns
  `404` if the job is not a `report` job, is not yet `completed`, or has no stored GCS path
  (defensive: should not happen for a genuinely completed report job). No signed URLs are
  used; Django itself streams the GCS blob through to the client via `FileResponse`, so the
  requesting user's session/JWT is the only thing gating access to the bytes.

## Execution: dispatcher and worker

Enqueuing happens through `api/services/async_jobs.py`:

- `enqueue(kind, params, user=None, project=None)` creates the `pending` `AsyncJob` row
  and registers `dispatch(job.pk)` to run via `transaction.on_commit`, so a job is never
  dispatched against a row that might still roll back.
- `dispatch(job_pk)` branches on `settings.CLOUD_RUN_COMPUTATION_JOB_NAME`:
  - If set (production), it calls `_dispatch_cloud_run`, which triggers a Cloud Run Job
    execution of the existing `exact-computation-job` image, overriding the container args
    to `["python", "manage.py", "run_async_job", "--job-id", "<pk>"]`. This reuses the same
    deployed Cloud Run Job resource that already runs LUC bulk computation and legacy
    `ComputationJob` work; no new GCP job resource is created for async jobs.
  - If empty (local dev, no Cloud Run configured), it calls `_dispatch_subprocess`, which
    runs the same `manage.py run_async_job --job-id <pk>` command via `subprocess.Popen`,
    detached (`start_new_session=True`), logging to `EXACT_JOB_LOG_DIR` (or `BASE_DIR/logs`,
    or the system temp dir as a last resort).

The worker itself is `python manage.py run_async_job --job-id <N>`
(`api/management/commands/run_async_job.py`). It:

1. Loads the `AsyncJob`. If its status is not `pending`, it exits immediately (idempotent
   re-dispatch guard: a Cloud Run retry or a duplicate subprocess launch cannot re-run
   already-started work).
2. Marks the job `running` and records `started_at`.
3. Dispatches on `kind` to the matching service module:
   - `report` -> `api/services/report_jobs.py::run`
   - `project_copy` -> `api/services/copy_jobs.py::run`
4. On success, stores the returned dict in `result`, sets `status=completed`,
   `progress=100`.
5. On any exception, closes the (possibly forked-and-broken) DB connection before writing
   the failure state, sets `status=failed`, and truncates the exception message into
   `error_message` (2000 chars).
6. Always records `completed_at` and saves, in a `finally` block, so a job can never be
   left `running` forever by a code path that forgets to update status (short of the
   process being killed outright, which is exactly what the reconciler below exists for).

## Report output and download

`api/services/report_jobs.py::run` reproduces what the synchronous `template()` /
`report()` actions on `ProjectViewSet` already do (compute the `ProjectResult`, render via
WeasyPrint for PDF or via the existing Excel generator), then uploads the bytes to Google
Cloud Storage at:

```text
gs://{STORAGE_BUCKET}/reports/{project_id}/{job_id}.{ext}
```

where `ext` is `pdf` or `xlsx`. The `result` JSON on the `AsyncJob` stores `gcs_path`,
`filename`, and `content_type`. The download endpoint above reads those back and streams
the blob through Django; there are no signed URLs and no direct client access to the
bucket, so bucket IAM does not need to grant anything to end users.

## Project copy threshold

`PROJECT_COPY_ASYNC_THRESHOLD` (`djangoexact/djangoexact/settings.py`, default `40`,
overridable via the `PROJECT_COPY_ASYNC_THRESHOLD` env var) is the sync/async cutoff for
`copy/async/`. The view sums the source project's activity count and its total module-type
count across those activities; at or below the threshold the copy runs inline in the
request (matching the existing `copy/` behavior byte-for-byte, including the `201`
response body), above it the copy is offloaded to an `AsyncJob`. Raise this if projects
that should still be fast are tipping into the async path, or lower it if large synchronous
copies are still timing out requests.

## Reconciliation of stale jobs

`python manage.py reconcile_stale_async_jobs`
(`api/management/commands/reconcile_stale_async_jobs.py`) marks any `AsyncJob` that is
still `running` and was `started_at` more than `STALE_THRESHOLD` (1 hour) ago as `failed`,
with an explanatory `error_message`. The 1-hour threshold intentionally matches the Cloud
Run Job's `--task-timeout=3600` (see the deploy pipeline note below): if a job execution
were killed by the platform for exceeding that timeout, the row would otherwise stay
`running` forever with nothing to correct it.

This mirrors the existing `admin_scripts` command `reconcile_stale_jobs`, which does the
same thing for the older `ComputationJob` model and its own 1-hour `STALE_THRESHOLD`. As
of this task, neither command has a Cloud Scheduler (or other automated trigger) wired up
in this repository: there is no Terraform, no scheduler config, and no admin endpoint that
invokes either reconciler. **State this plainly: until a scheduler is provisioned, stale
jobs only get auto-failed when an operator runs the reconciler by hand.** A user polling
`GET /api/async-jobs/{id}/` for a job whose worker process died outright (OOM-killed, node
preempted, etc.) will see it stuck at `running` indefinitely until someone runs the command.

Recommended fix, to be provisioned out-of-band from the app deploy (Cloud Console,
`gcloud`, or Terraform, whichever this project standardizes on): create an hourly Cloud
Scheduler job targeting one of:

- A Cloud Run Job execution of the existing `exact-computation-job` image, overriding the
  container args to:

  ```json
  ["python", "manage.py", "reconcile_stale_async_jobs"]
  ```

  This is the same override mechanism `_dispatch_cloud_run` already uses for
  `run_async_job`, so it needs no new IAM: Cloud Scheduler needs only the existing
  permission to invoke the `exact-computation-job` execution (the same permission the web
  service account already has to trigger LUC/async dispatch), and the job's own service
  account already reaches Cloud SQL.

- An authenticated HTTP request (OIDC token, Cloud Scheduler's built-in auth) to a small
  admin-only endpoint that runs `call_command("reconcile_stale_async_jobs")`. Only worth
  building if the team prefers an HTTP-triggerable surface over another Cloud Run Job
  execution; no such endpoint exists in this codebase today.

Either mechanism should also cover the older `reconcile_stale_jobs` command for
`ComputationJob` if it is not already scheduled somewhere outside this repo; this task did
not find evidence that it is.

## GCS lifecycle for report objects

Report files accumulate under `reports/{project_id}/{job_id}.{ext}` in `STORAGE_BUCKET`
and are never deleted by application code (the async report flow only writes; nothing in
this codebase issues a delete for these objects). Left alone, this prefix grows without
bound.

Recommended: a lifecycle rule on the bucket that deletes objects under `reports/` after N
days (7 is a reasonable default: long enough to cover any reasonable "I meant to download
that report" delay, short enough to bound storage growth). This is a bucket configuration
change, applied out-of-band from the app deploy, by an operator with bucket-admin access:

```bash
# lifecycle.json
# {"rule":[{"action":{"type":"Delete"},"condition":{"age":7,"matchesPrefix":["reports/"]}}]}
gcloud storage buckets update gs://$STORAGE_BUCKET --lifecycle-file=lifecycle.json
```

Confirm `STORAGE_BUCKET` is not shared with other long-lived object prefixes that should
not be subject to this rule before applying it (the `matchesPrefix` scoping to `reports/`
is what keeps this safe).

## Frontend migration note

The WebApp frontend currently calls only the legacy synchronous `report/` and `copy/`
endpoints; those are unchanged by this work and require no frontend change to keep
functioning. To pick up the async behavior, the frontend needs to:

- Call `POST /api/projects/{pk}/report/async/` instead of (or in addition to) `report/`,
  then poll `GET /api/async-jobs/{job_id}/` (recommend a short interval, backing off, with
  a reasonable cap given the `--task-timeout=3600` upper bound on job runtime) until
  `status` is `completed` or `failed`, then fetch
  `GET /api/async-jobs/{job_id}/download/` to obtain the file.
- Call `POST /api/projects/{pk}/copy/async/` and branch on the HTTP status: `201` means the
  response body is already the finished project (same shape as the old `copy/` response,
  no polling needed); `202` means the body is `{"job_id", "new_project_id", "status"}` and
  the frontend must poll `GET /api/async-jobs/{job_id}/` until `completed`, then navigate to
  `new_project_id` (which already exists as a project record throughout, populated
  in-place by the worker).

Until the frontend adopts `report/async` and `copy/async`, it will simply keep hitting the
legacy endpoints and see no behavior change, including no exposure to the
`PROJECT_COPY_ASYNC_THRESHOLD` routing.

## IAM

No new IAM is required for any of this. The web service account already has permission to
trigger Cloud Run Job executions (the existing LUC bulk-compute dispatch proves this path
works), and the job's own service account already has the Cloud SQL and GCS access it
needs (the same `exact-computation-job` image and service account already reads/writes
GCS for other computation work). The only new out-of-band grant, if the Cloud Scheduler
option above is chosen for the reconciler, is Cloud Scheduler's own permission to invoke a
Cloud Run Job execution, which is a standard `roles/run.invoker`-style grant on the
scheduler's own service account, not a change to the app's service accounts.
