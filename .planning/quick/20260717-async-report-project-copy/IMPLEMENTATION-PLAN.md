# Async Report Generation & Project Copy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move PDF/Excel report generation and large-project copy off the request thread onto the existing Cloud Run Jobs infrastructure, tracked by a generic `AsyncJob` model, exposed through additive `202`+poll API endpoints.

**Architecture:** Reuse the deployed `admin_scripts` job pattern (Cloud Run Jobs + `subprocess` fallback + DB-tracked status + stale-job reconcile). Add one generic `AsyncJob` model in `api`, a dispatch service that reuses the existing `exact-computation-job` image (overriding the container args to run a new `run_async_job` command), and per-kind worker handlers. Reports upload to GCS and stream back through Django. Project copy stays synchronous for small projects and is offloaded to a job only above a size threshold.

**Tech Stack:** Django 5.2, DRF 3.16, `google-cloud-run` (`run_v2`), `google-cloud-storage`, WeasyPrint 68, `django-simple-history`, PostgreSQL (Cloud SQL), App Engine Standard (web) + Cloud Run Jobs (workers).

## Global Constraints

- Python 3.11; Django 5.2.14; DRF 3.16.1; pinned `djangoexact/requirements.txt` (no new runtime dependencies required — `google-cloud-run`, `google-cloud-storage`, `weasyprint` are already present).
- Never use em-dashes anywhere in this repo (project rule).
- Public API contract for existing paths must not change: the current sync `GET .../report/` and `POST .../copy/` endpoints stay behavior-identical. All async behavior is additive.
- No pytest-django. Django-dependent tests inherit `django.test.TestCase` / `rest_framework.test.APITestCase`. `pytest` and `python manage.py test` both discover them.
- The local dev sandbox has NO Postgres/Docker: the only reliable local gate is `python -m py_compile <files>`. Full test runs happen in CI or on a DB-equipped machine. Every task below lists both the local `py_compile` gate and the DB-machine test command.
- Reference data / fixtures are database-truth: do not hand-edit JSON fixtures. This plan adds no reference data.
- Conventional commits (commitizen), feature branch off `develop`, PR targets `develop`. Do NOT hand-edit version files.
- Run all `python`/`manage.py` commands from `djangoexact/` (the Django root), not the repo root.

## File Structure

New files:
- `djangoexact/api/services/async_jobs.py` — enqueue + dispatch (Cloud Run vs subprocess). One responsibility: get a queued `AsyncJob` running.
- `djangoexact/api/services/report_jobs.py` — report worker handler (compute -> render -> GCS).
- `djangoexact/api/services/copy_jobs.py` — project-copy worker handler (populate a pre-created shell project).
- `djangoexact/api/management/commands/run_async_job.py` — the command the Cloud Run Job / subprocess executes.
- `djangoexact/api/management/commands/reconcile_stale_async_jobs.py` — safety net for jobs stuck RUNNING.
- `djangoexact/api/tests/test_async_jobs.py` — foundation + endpoint tests.
- `djangoexact/api/tests/test_project_copy_async.py` — copy bug-fix + threshold routing tests.

Modified files:
- `djangoexact/api/models.py` — add `AsyncJob` model.
- `djangoexact/api/serializers.py` — add `AsyncJobSerializer`.
- `djangoexact/api/views.py` — add `AsyncJobViewSet`, `ProjectViewSet.report_async`, `ProjectViewSet.copy_async`; remove the duplicate membership create in `ProjectViewSet.copy`.
- `djangoexact/api/urls.py` — register `async-jobs` route.
- `djangoexact/api/utilities.py` — split `copy_project` into `create_project_shell` + `copy_activities_into`; fix membership bugs.
- `djangoexact/api/reports/html_context.py` — make `build_template_context(result, request=None, lang="en")` request-optional.
- `djangoexact/djangoexact/settings.py` — add `PROJECT_COPY_ASYNC_THRESHOLD`.
- `djangoexact/api/migrations/00NN_asyncjob.py` — generated.
- `deploy/Dockerfile.computation_job` — add WeasyPrint native libs + fonts.
- `.github/workflows/deploy.yaml` — no new job resource; verify the reused image ships WeasyPrint deps (documentation/CI note only).

---

## PHASE A — Shared foundation

### Task 1: `AsyncJob` model + migration

**Files:**
- Modify: `djangoexact/api/models.py` (append the model)
- Create: `djangoexact/api/migrations/00NN_asyncjob.py` (generated)
- Test: `djangoexact/api/tests/test_async_jobs.py`

**Interfaces:**
- Produces: `api.models.AsyncJob` with `Kind` (`REPORT="report"`, `PROJECT_COPY="project_copy"`) and `Status` (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`) TextChoices; fields `kind, status, progress, params(JSON), result(JSON), error_message, pid, cloud_run_execution_name, created_by(FK user), project(FK Project), created_at, updated_at, started_at, completed_at`.

- [ ] **Step 1: Write the failing test**

Create `djangoexact/api/tests/test_async_jobs.py`:

```python
from django.test import TestCase

from api.models import AsyncJob


class AsyncJobModelTestCase(TestCase):
    def test_defaults(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={"project_id": 1})
        self.assertEqual(job.status, AsyncJob.Status.PENDING)
        self.assertEqual(job.progress, 0)
        self.assertEqual(job.result, {})
        self.assertEqual(job.error_message, "")
        self.assertIsNone(job.started_at)
        self.assertIsNotNone(job.created_at)

    def test_kind_choices(self):
        self.assertEqual(AsyncJob.Kind.PROJECT_COPY.value, "project_copy")
        self.assertEqual(AsyncJob.Kind.REPORT.value, "report")
```

- [ ] **Step 2: Add the model to `djangoexact/api/models.py`**

Append near the end of the module (after the existing model definitions; `settings` and `models` are already imported in this file):

```python
class AsyncJob(models.Model):
    """Generic background job tracked in the DB and executed by the
    exact-computation-job Cloud Run Job (or a local subprocess). Used for
    async report generation and large project copies. Not Historical: these
    rows are ephemeral operational state, matching admin_scripts.ComputationJob.
    """

    class Kind(models.TextChoices):
        REPORT = "report", "Report generation"
        PROJECT_COPY = "project_copy", "Project copy"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    kind = models.CharField(max_length=32, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    progress = models.PositiveSmallIntegerField(default=0)
    params = models.JSONField(default=dict)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(default="", blank=True)
    pid = models.IntegerField(null=True, blank=True)
    cloud_run_execution_name = models.CharField(max_length=255, default="", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="async_jobs",
    )
    project = models.ForeignKey(
        "api.Project", null=True, blank=True,
        on_delete=models.CASCADE, related_name="async_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["kind", "status"]),
        ]

    def __str__(self):
        return f"AsyncJob<{self.pk} {self.kind} {self.status}>"
```

If `settings` is not already imported at the top of `models.py`, add `from django.conf import settings`.

- [ ] **Step 3: Generate the migration (DB-equipped machine or CI)**

Run from `djangoexact/`: `python manage.py makemigrations api`
Expected: creates `api/migrations/00NN_asyncjob.py` (NN = next sequential number after the current latest `api` migration). If you cannot run `makemigrations`, hand-write the file with `dependencies = [("api", "<latest_api_migration_name>")]` and a single `migrations.CreateModel` for `AsyncJob` matching the fields above.

- [ ] **Step 4: Local gate**

Run from `djangoexact/`: `python -m py_compile api/models.py api/tests/test_async_jobs.py`
Expected: no output (success).

- [ ] **Step 5: Run the test (DB machine / CI)**

Run: `python manage.py test api.tests.test_async_jobs.AsyncJobModelTestCase -v 2`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add api/models.py api/migrations/00NN_asyncjob.py api/tests/test_async_jobs.py
git commit -m "feat(api): add generic AsyncJob model for background jobs"
```

---

### Task 2: `async_jobs` dispatch service

**Files:**
- Create: `djangoexact/api/services/async_jobs.py`
- Test: `djangoexact/api/tests/test_async_jobs.py` (append)

**Interfaces:**
- Consumes: `api.models.AsyncJob`; `settings.CLOUD_RUN_COMPUTATION_JOB_NAME` (reused — same job resource, different container args).
- Produces:
  - `enqueue(kind: str, params: dict, user=None, project=None) -> AsyncJob` (creates row, schedules dispatch on commit)
  - `dispatch(job_pk: int) -> None` (branches Cloud Run vs subprocess)

- [ ] **Step 1: Write the failing test (append to `test_async_jobs.py`)**

```python
from unittest import mock

from django.test import TestCase, override_settings

from api.models import AsyncJob
from api.services import async_jobs


class AsyncJobDispatchTestCase(TestCase):
    def test_enqueue_creates_job_and_schedules_dispatch(self):
        with mock.patch.object(async_jobs, "dispatch") as m_dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                job = async_jobs.enqueue(AsyncJob.Kind.REPORT, {"project_id": 1})
        self.assertEqual(job.kind, AsyncJob.Kind.REPORT)
        self.assertEqual(job.status, AsyncJob.Status.PENDING)
        m_dispatch.assert_called_once_with(job.pk)

    @override_settings(CLOUD_RUN_COMPUTATION_JOB_NAME="")
    def test_dispatch_uses_subprocess_when_no_job_name(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={})
        fake_proc = mock.Mock(pid=4242)
        with mock.patch("api.services.async_jobs.subprocess.Popen", return_value=fake_proc) as m_popen:
            async_jobs.dispatch(job.pk)
        m_popen.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.pid, 4242)

    @override_settings(CLOUD_RUN_COMPUTATION_JOB_NAME="projects/p/locations/l/jobs/exact-computation-job")
    def test_dispatch_uses_cloud_run_when_job_name_set(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={})
        with mock.patch("api.services.async_jobs._dispatch_cloud_run") as m_cr:
            async_jobs.dispatch(job.pk)
        m_cr.assert_called_once_with(job.pk)
```

- [ ] **Step 2: Create `djangoexact/api/services/async_jobs.py`**

```python
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
    if not log_dir:
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
```

Ensure `djangoexact/api/services/__init__.py` exists (it does — `luc_compute.py` lives there). No change needed.

- [ ] **Step 3: Local gate**

Run: `python -m py_compile api/services/async_jobs.py api/tests/test_async_jobs.py`
Expected: success.

- [ ] **Step 4: Run tests (DB machine / CI)**

Run: `python manage.py test api.tests.test_async_jobs.AsyncJobDispatchTestCase -v 2`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add api/services/async_jobs.py api/tests/test_async_jobs.py
git commit -m "feat(api): add AsyncJob enqueue/dispatch service (Cloud Run + subprocess)"
```

---

### Task 3: `run_async_job` management command

**Files:**
- Create: `djangoexact/api/management/commands/run_async_job.py`
- Test: `djangoexact/api/tests/test_async_jobs.py` (append)

**Interfaces:**
- Consumes: `api.models.AsyncJob`; `api.services.report_jobs.run(job) -> dict` (Task 6); `api.services.copy_jobs.run(job) -> dict` (Task 10).
- Produces: CLI `python manage.py run_async_job --job-id N`. Loads the row, marks RUNNING, dispatches by `kind`, writes `result`, marks terminal. On exception, refreshes the DB connection (post-fork hygiene) then records FAILED.

Note: `report_jobs` and `copy_jobs` are imported lazily inside `handle()` so this task compiles and its dispatch logic is testable before those handlers exist.

- [ ] **Step 1: Write the failing test (append)**

```python
class RunAsyncJobCommandTestCase(TestCase):
    def _run(self, job_id):
        from django.core.management import call_command
        call_command("run_async_job", "--job-id", str(job_id))

    def test_dispatches_report_kind_and_marks_completed(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={})
        with mock.patch("api.services.report_jobs.run", return_value={"gcs_path": "x"}) as m_run:
            self._run(job.pk)
        m_run.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.COMPLETED)
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.result, {"gcs_path": "x"})
        self.assertIsNotNone(job.completed_at)

    def test_marks_failed_on_handler_exception(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.PROJECT_COPY, params={})
        with mock.patch("api.services.copy_jobs.run", side_effect=RuntimeError("boom")):
            self._run(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.FAILED)
        self.assertIn("boom", job.error_message)

    def test_skips_non_pending_job(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.CANCELLED, params={})
        with mock.patch("api.services.report_jobs.run") as m_run:
            self._run(job.pk)
        m_run.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.CANCELLED)
```

- [ ] **Step 2: Create the command**

Create `djangoexact/api/management/commands/run_async_job.py` (ensure the `management/commands/` package dirs and their `__init__.py` files exist under `api/`; create empty `__init__.py` files if missing):

```python
import logging

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from api.models import AsyncJob

log = logging.getLogger("console")


class Command(BaseCommand):
    help = "Execute a queued AsyncJob by id (report generation or project copy)."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", type=int, required=True)

    def handle(self, *args, **options):
        job_id = options["job_id"]
        job = AsyncJob.objects.get(pk=job_id)

        if job.status != AsyncJob.Status.PENDING:
            # Cancelled or already handled: do nothing (idempotent re-dispatch guard).
            self.stdout.write(f"Job {job_id} is {job.status}; skipping.")
            return

        job.status = AsyncJob.Status.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])

        try:
            if job.kind == AsyncJob.Kind.REPORT:
                from api.services import report_jobs
                result = report_jobs.run(job)
            elif job.kind == AsyncJob.Kind.PROJECT_COPY:
                from api.services import copy_jobs
                result = copy_jobs.run(job)
            else:
                raise ValueError(f"Unknown AsyncJob kind: {job.kind}")

            job.result = result or {}
            job.status = AsyncJob.Status.COMPLETED
            job.progress = 100
        except Exception as e:
            # The container may have forked from the web app; the inherited DB
            # connection can be unusable. Drop it so the status write reconnects.
            connection.close()
            log.exception(e)
            job.status = AsyncJob.Status.FAILED
            job.error_message = str(e)[:2000]
        finally:
            job.completed_at = timezone.now()
            job.save(update_fields=[
                "status", "progress", "result", "error_message",
                "completed_at", "updated_at",
            ])
```

- [ ] **Step 3: Local gate**

Run: `python -m py_compile api/management/commands/run_async_job.py api/tests/test_async_jobs.py`
Expected: success.

- [ ] **Step 4: Run tests (DB machine / CI)**

Run: `python manage.py test api.tests.test_async_jobs.RunAsyncJobCommandTestCase -v 2`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add api/management/commands/run_async_job.py api/tests/test_async_jobs.py
git commit -m "feat(api): add run_async_job management command"
```

---

### Task 4: DRF status endpoint (`AsyncJobViewSet` + serializer + route)

**Files:**
- Modify: `djangoexact/api/serializers.py` (add `AsyncJobSerializer`)
- Modify: `djangoexact/api/views.py` (add `AsyncJobViewSet`)
- Modify: `djangoexact/api/urls.py` (register route)
- Test: `djangoexact/api/tests/test_async_jobs.py` (append)

**Interfaces:**
- Produces: `GET /api/async-jobs/{id}/` -> `{id, kind, status, progress, result, error_message, created_at, started_at, completed_at, project}`, scoped to `created_by == request.user`. Basename `async-job`.

- [ ] **Step 1: Write the failing test (append)**

```python
from rest_framework.test import APITestCase
from api.tests.factories import UserFactory  # existing factory-boy factory


class AsyncJobEndpointTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other = UserFactory()
        self.client.force_authenticate(self.user)

    def test_owner_can_read_own_job(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={}, created_by=self.user)
        resp = self.client.get(f"/api/async-jobs/{job.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "pending")
        self.assertEqual(resp.data["kind"], "report")

    def test_other_user_cannot_read_job(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={}, created_by=self.other)
        resp = self.client.get(f"/api/async-jobs/{job.pk}/")
        self.assertEqual(resp.status_code, 404)
```

If the existing factory module path differs, adjust the import to the repo's user factory (search `api/tests/` for `class UserFactory`).

- [ ] **Step 2: Add the serializer to `djangoexact/api/serializers.py`**

```python
class AsyncJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AsyncJob
        fields = [
            "id", "kind", "status", "progress", "result", "error_message",
            "created_at", "started_at", "completed_at", "project",
        ]
        read_only_fields = fields
```

Add `AsyncJob` to the models import at the top of `serializers.py` (the file already imports from `api.models`).

- [ ] **Step 3: Add the viewset to `djangoexact/api/views.py`**

```python
class AsyncJobViewSet(viewsets.ReadOnlyModelViewSet):
    """Poll endpoint for background jobs. Users see only their own jobs."""
    serializer_class = serializers.AsyncJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AsyncJob.objects.filter(created_by=self.request.user)
```

Ensure `views.py` imports cover `viewsets`, `permissions` (from `rest_framework`), and `AsyncJob` (from `api.models`). The download action is added in Task 8.

- [ ] **Step 4: Register the route in `djangoexact/api/urls.py`**

Add next to the other `router.register(...)` calls (the `projects` route is registered at line 28):

```python
router.register(r"async-jobs", views.AsyncJobViewSet, basename="async-job")
```

- [ ] **Step 5: Local gate**

Run: `python -m py_compile api/serializers.py api/views.py api/urls.py api/tests/test_async_jobs.py`
Expected: success.

- [ ] **Step 6: Run tests (DB machine / CI)**

Run: `python manage.py test api.tests.test_async_jobs.AsyncJobEndpointTestCase -v 2`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add api/serializers.py api/views.py api/urls.py api/tests/test_async_jobs.py
git commit -m "feat(api): add AsyncJob polling endpoint (GET /api/async-jobs/{id}/)"
```

---

### Task 5: Stale-job reconciler

**Files:**
- Create: `djangoexact/api/management/commands/reconcile_stale_async_jobs.py`
- Test: `djangoexact/api/tests/test_async_jobs.py` (append)

**Interfaces:**
- Produces: CLI `python manage.py reconcile_stale_async_jobs`. Marks any `RUNNING` `AsyncJob` older than `STALE_THRESHOLD` (1 hour, matching `--task-timeout=3600`) as FAILED with an explanatory message. Intended for Cloud Scheduler.

- [ ] **Step 1: Write the failing test (append)**

```python
from datetime import timedelta


class ReconcileStaleAsyncJobsTestCase(TestCase):
    def test_marks_old_running_job_failed(self):
        from django.core.management import call_command
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.RUNNING, params={})
        AsyncJob.objects.filter(pk=job.pk).update(
            started_at=timezone.now() - timedelta(hours=2),
        )
        call_command("reconcile_stale_async_jobs")
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.FAILED)
        self.assertIn("stale", job.error_message.lower())

    def test_leaves_recent_running_job(self):
        from django.core.management import call_command
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.RUNNING, params={})
        call_command("reconcile_stale_async_jobs")
        job.refresh_from_db()
        self.assertEqual(job.status, AsyncJob.Status.RUNNING)
```

Add `from django.utils import timezone` at the top of the test module if not already present.

- [ ] **Step 2: Create the command**

```python
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import AsyncJob

STALE_THRESHOLD = timedelta(hours=1)


class Command(BaseCommand):
    help = "Fail AsyncJobs stuck in RUNNING beyond the task timeout."

    def handle(self, *args, **options):
        cutoff = timezone.now() - STALE_THRESHOLD
        stale = AsyncJob.objects.filter(
            status=AsyncJob.Status.RUNNING, started_at__lt=cutoff,
        )
        count = stale.update(
            status=AsyncJob.Status.FAILED,
            error_message="Marked failed: job stale (exceeded task timeout without completing).",
            completed_at=timezone.now(),
        )
        self.stdout.write(f"Reconciled {count} stale AsyncJob(s).")
```

- [ ] **Step 3: Local gate**

Run: `python -m py_compile api/management/commands/reconcile_stale_async_jobs.py api/tests/test_async_jobs.py`
Expected: success.

- [ ] **Step 4: Run tests (DB machine / CI)**

Run: `python manage.py test api.tests.test_async_jobs.ReconcileStaleAsyncJobsTestCase -v 2`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add api/management/commands/reconcile_stale_async_jobs.py api/tests/test_async_jobs.py
git commit -m "feat(api): add reconcile_stale_async_jobs safety-net command"
```

---

## PHASE B — Report async

### Task 6: Report worker handler + request-optional context

**Files:**
- Modify: `djangoexact/api/reports/html_context.py` (make `request` optional in `build_template_context`)
- Create: `djangoexact/api/services/report_jobs.py`
- Test: `djangoexact/api/tests/test_async_jobs.py` (append)

**Interfaces:**
- Consumes: `api.reports.compute_project_result(project, activities=None)`; `api.reports.generate_excel_report(project, activities=None)`; `api.reports.html_context.build_template_context(result, request=None, lang="en")`; `settings.STORAGE_BUCKET`.
- Produces: `report_jobs.run(job: AsyncJob) -> dict` returning `{"gcs_path": str, "filename": str, "content_type": str}`. Reads `job.params`: `project_id`, `activity_ids` (list|None), `format` ("pdf"|"xlsx"), `template` (str|None), `lang` (str).

- [ ] **Step 1: Make `build_template_context` request-optional**

In `djangoexact/api/reports/html_context.py`, change the signature at line ~345 from `def build_template_context(result, request, lang):` to:

```python
def build_template_context(result, request=None, lang="en"):
```

The function already calls `activate(lang)` for i18n. Audit the body for any `request.` access (the report map found it is used only for language). If any `request.<attr>` remains, guard it: `if request is not None:`. Do not change call sites in `api/views.py` / `public/views.py` — they pass `request` positionally and stay valid.

- [ ] **Step 2: Write the failing test (append)**

```python
class ReportJobRunTestCase(TestCase):
    def test_pdf_path_uploads_and_returns_metadata(self):
        from api.services import report_jobs
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT,
            params={"project_id": 7, "activity_ids": None, "format": "pdf",
                    "template": "standard", "lang": "en"},
        )
        fake_project = mock.Mock(pk=7, name="P")
        with mock.patch("api.services.report_jobs.Project") as m_project, \
             mock.patch("api.services.report_jobs.compute_project_result", return_value=mock.Mock()), \
             mock.patch("api.services.report_jobs.build_template_context", return_value={}), \
             mock.patch("api.services.report_jobs.render_to_string", return_value="<html></html>"), \
             mock.patch("api.services.report_jobs._weasyprint_pdf", return_value=b"%PDF-1.7"), \
             mock.patch("api.services.report_jobs._upload", return_value="reports/7/1.pdf") as m_upload:
            m_project.objects.get.return_value = fake_project
            result = report_jobs.run(job)
        self.assertEqual(result["gcs_path"], "reports/7/1.pdf")
        self.assertEqual(result["content_type"], "application/pdf")
        m_upload.assert_called_once()
```

- [ ] **Step 3: Create `djangoexact/api/services/report_jobs.py`**

```python
"""Worker handler for async report generation.

Reproduces ProjectViewSet.template()/report() off-request: compute the
ProjectResult, render (PDF via WeasyPrint or Excel), and upload the bytes to GCS.
The result dict points the download endpoint at the stored object.
"""
import io

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import activate

from api.models import AsyncJob, Project
from api.reports import compute_project_result, generate_excel_report
from api.reports.html_context import build_template_context


def run(job: AsyncJob) -> dict:
    params = job.params
    project = Project.objects.get(pk=params["project_id"])

    activity_ids = params.get("activity_ids")
    activities = None
    if activity_ids:
        activities = list(project.activities.filter(pk__in=activity_ids))

    fmt = params.get("format", "pdf")
    lang = params.get("lang", "en")
    activate(lang)

    if fmt == "pdf":
        template_name = params["template"]
        content = _render_pdf(project, activities, template_name, lang)
        content_type = "application/pdf"
        ext = "pdf"
        default_name = f"{template_name}.pdf"
    else:
        buffer = generate_excel_report(project, activities)
        content = buffer.getvalue() if isinstance(buffer, io.BytesIO) else buffer
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
        default_name = f"{project.name}_report.xlsx"

    gcs_path = _upload(project, job, content, ext)
    return {
        "gcs_path": gcs_path,
        "filename": params.get("filename") or default_name,
        "content_type": content_type,
    }


def _render_pdf(project, activities, template_name, lang):
    result = compute_project_result(project, activities)
    context = build_template_context(result, None, lang)
    html = render_to_string(f"reports/{template_name}_{lang}.html", context)
    return _weasyprint_pdf(html)


def _weasyprint_pdf(html):
    from weasyprint import HTML
    return HTML(string=html).write_pdf()


def _upload(project, job, content, ext):
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(settings.STORAGE_BUCKET)
    blob_path = f"reports/{project.pk}/{job.pk}.{ext}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(content, content_type="application/octet-stream")
    return blob_path
```

- [ ] **Step 4: Local gate**

Run: `python -m py_compile api/reports/html_context.py api/services/report_jobs.py api/tests/test_async_jobs.py`
Expected: success.

- [ ] **Step 5: Run tests (DB machine / CI)**

Run: `python manage.py test api.tests.test_async_jobs.ReportJobRunTestCase -v 2`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add api/reports/html_context.py api/services/report_jobs.py api/tests/test_async_jobs.py
git commit -m "feat(api): add async report worker handler (report_jobs.run)"
```

---

### Task 7: Async report enqueue endpoint

**Files:**
- Modify: `djangoexact/api/views.py` (add `report_async` action to `ProjectViewSet`)
- Test: `djangoexact/api/tests/test_async_jobs.py` (append)

**Interfaces:**
- Consumes: `api.services.async_jobs.enqueue`; `AsyncJob.Kind.REPORT`; existing `security.check_permission`, `project.is_ready`, `utils.ErrorResponse`.
- Produces: `POST /api/projects/{pk}/report/async/?template=&lang=&activities=&format=` -> `202 {"job_id": int, "status": "pending"}`.

- [ ] **Step 1: Write the failing test (append)**

```python
class ReportAsyncEndpointTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_authenticate(self.user)

    def test_enqueues_pdf_report_job(self):
        # Build a minimal ready project the user can view. Reuse existing project
        # factory + membership helpers from api/tests (see test_project_copy_async).
        from api.tests.factories import ProjectFactory
        project = ProjectFactory(owner=self.user)
        with mock.patch("api.views.security.check_permission", return_value=None), \
             mock.patch.object(type(project), "is_ready", return_value=True), \
             mock.patch("api.views.ProjectViewSet.get_object", return_value=project):
            resp = self.client.post(f"/api/projects/{project.pk}/report/async/?template=standard&lang=en")
        self.assertEqual(resp.status_code, 202)
        self.assertIn("job_id", resp.data)
        job = AsyncJob.objects.get(pk=resp.data["job_id"])
        self.assertEqual(job.kind, AsyncJob.Kind.REPORT)
        self.assertEqual(job.params["template"], "standard")
```

Adjust factory imports to match the repo's existing project factory.

- [ ] **Step 2: Add the action to `ProjectViewSet` in `djangoexact/api/views.py`**

Place beside the existing `report` action (near line 702):

```python
@action(detail=True, methods=["post"], url_path="report/async")
def report_async(self, request, pk=None):
    """Enqueue a report for background generation. Returns 202 + job id.

    The existing synchronous `report/` action is unchanged. Poll the job at
    GET /api/async-jobs/{id}/ then download via that job's /download/ action.
    """
    project = self.get_object()
    error = security.check_permission("view_project", request.user, project)
    if error:
        return error

    template_name = request.query_params.get("template")
    lang = request.query_params.get("lang", getattr(request, "LANGUAGE_CODE", "en"))
    fmt = "pdf" if template_name else request.query_params.get("format", "xlsx")

    activities_param = request.query_params.get("activities")
    activity_ids = None
    if activities_param:
        activity_ids = [int(a) for a in activities_param.split(",") if a.strip()]

    selected = None
    if activity_ids:
        selected = project.activities.filter(pk__in=activity_ids)
    if not project.is_ready(selected):
        return utils.ErrorResponse("Project is not ready for reporting", status=http_status.HTTP_400_BAD_REQUEST)

    if fmt == "pdf" and not template_name:
        return utils.ErrorResponse("Template name is required for PDF", status=http_status.HTTP_400_BAD_REQUEST)

    params = {
        "project_id": project.pk,
        "activity_ids": activity_ids,
        "format": fmt,
        "template": template_name,
        "lang": lang,
    }
    job = async_jobs.enqueue(AsyncJob.Kind.REPORT, params, user=request.user, project=project)
    return Response({"job_id": job.pk, "status": job.status}, status=http_status.HTTP_202_ACCEPTED)
```

Add `from api.services import async_jobs` (or `from api.services import async_jobs, ...`) to the imports in `views.py`, and confirm `http_status` (the existing alias for `rest_framework.status`) is imported.

- [ ] **Step 3: Local gate**

Run: `python -m py_compile api/views.py api/tests/test_async_jobs.py`
Expected: success.

- [ ] **Step 4: Run tests (DB machine / CI)**

Run: `python manage.py test api.tests.test_async_jobs.ReportAsyncEndpointTestCase -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/views.py api/tests/test_async_jobs.py
git commit -m "feat(api): add POST /projects/{pk}/report/async/ enqueue endpoint"
```

---

### Task 8: Report download (streaming)

**Files:**
- Modify: `djangoexact/api/views.py` (add `download` action to `AsyncJobViewSet`)
- Test: `djangoexact/api/tests/test_async_jobs.py` (append)

**Interfaces:**
- Produces: `GET /api/async-jobs/{id}/download/` -> streams the stored report blob as an attachment. 404 unless the job is a COMPLETED report with a `gcs_path`.

- [ ] **Step 1: Write the failing test (append)**

```python
class ReportDownloadTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_authenticate(self.user)

    def test_download_streams_completed_report(self):
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.COMPLETED,
            created_by=self.user,
            result={"gcs_path": "reports/7/1.pdf", "filename": "standard.pdf",
                    "content_type": "application/pdf"},
        )
        fake_blob = mock.Mock()
        fake_blob.open.return_value = io.BytesIO(b"%PDF-1.7")
        with mock.patch("api.views.storage.Client") as m_client:
            m_client.return_value.bucket.return_value.blob.return_value = fake_blob
            resp = self.client.get(f"/api/async-jobs/{job.pk}/download/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("standard.pdf", resp["Content-Disposition"])

    def test_download_404_when_not_completed(self):
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.REPORT, status=AsyncJob.Status.RUNNING, created_by=self.user,
        )
        resp = self.client.get(f"/api/async-jobs/{job.pk}/download/")
        self.assertEqual(resp.status_code, 404)
```

Add `import io` at the top of the test module if not present.

- [ ] **Step 2: Add the download action to `AsyncJobViewSet` in `djangoexact/api/views.py`**

```python
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        job = self.get_object()
        if job.kind != AsyncJob.Kind.REPORT or job.status != AsyncJob.Status.COMPLETED:
            return utils.ErrorResponse("Report not available", status=http_status.HTTP_404_NOT_FOUND)
        gcs_path = (job.result or {}).get("gcs_path")
        if not gcs_path:
            return utils.ErrorResponse("Report not available", status=http_status.HTTP_404_NOT_FOUND)

        client = storage.Client()
        bucket = client.bucket(settings.STORAGE_BUCKET)
        blob = bucket.blob(gcs_path)
        stream = blob.open("rb")
        response = FileResponse(
            stream,
            content_type=job.result.get("content_type", "application/octet-stream"),
        )
        filename = job.result.get("filename", "report")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
```

Confirm `views.py` imports: `FileResponse` (from `django.http`), `storage` (`from google.cloud import storage`), `settings` (`from django.conf import settings`). The streaming attachment code at `views.py:2819-2835` already uses `storage.Client()`; reuse that import.

- [ ] **Step 3: Local gate**

Run: `python -m py_compile api/views.py api/tests/test_async_jobs.py`
Expected: success.

- [ ] **Step 4: Run tests (DB machine / CI)**

Run: `python manage.py test api.tests.test_async_jobs.ReportDownloadTestCase -v 2`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add api/views.py api/tests/test_async_jobs.py
git commit -m "feat(api): stream async report via GET /async-jobs/{id}/download/"
```

---

## PHASE C — Project copy (bug fixes, split, threshold, async)

### Task 9: Fix copy bugs + split `copy_project` into shell + populate

**Files:**
- Modify: `djangoexact/api/utilities.py` (`copy_project` -> `create_project_shell` + `copy_activities_into`; fix membership)
- Modify: `djangoexact/api/views.py` (`ProjectViewSet.copy`: remove the duplicate membership create at line 1197)
- Test: `djangoexact/api/tests/test_project_copy_async.py`

**Interfaces:**
- Produces:
  - `create_project_shell(project, owner) -> Project` (fast: clones the Project row + one Admin membership)
  - `copy_activities_into(source_project, target_project, owner) -> None` (the slow per-activity loop)
  - `copy_project(project, owner) -> Project` (unchanged external behavior: shell + populate under one transaction)

- [ ] **Step 1: Write the failing test**

Create `djangoexact/api/tests/test_project_copy_async.py`:

```python
from django.test import TestCase

from api import utilities as utils
from api.models import Project, ProjectMembership
from api.tests.factories import UserFactory, ProjectFactory  # adjust to repo factories


class CopyProjectMembershipTestCase(TestCase):
    def test_copy_creates_exactly_one_admin_membership(self):
        owner = UserFactory()
        source = ProjectFactory(owner=owner)
        new_project = utils.copy_project(source, owner)
        admin_memberships = ProjectMembership.objects.filter(
            project=new_project, user=owner, group__name="Admin",
        )
        self.assertEqual(admin_memberships.count(), 1)

    def test_shell_has_no_activities_but_project_row_exists(self):
        owner = UserFactory()
        source = ProjectFactory(owner=owner)
        shell = utils.create_project_shell(source, owner)
        self.assertIsNotNone(shell.pk)
        self.assertNotEqual(shell.pk, source.pk)
        self.assertEqual(shell.activities.count(), 0)
        self.assertFalse(shell.is_finalized)
        self.assertFalse(shell.is_public)
```

- [ ] **Step 2: Refactor `copy_project` in `djangoexact/api/utilities.py`**

Replace the existing `copy_project` (lines 223-250) with the split below. `copy`, `api_models`, `get_unique_name`, and `copy_activity` are already in scope in this module.

```python
def _ensure_admin_membership(project_copy, owner):
    if not project_copy.members.filter(user=owner, group__name="Admin").exists():
        api_models.ProjectMembership.objects.create(
            user=owner,
            project=project_copy,
            group=api_models.Group.objects.get(name="Admin"),
        )


@transaction.atomic
def create_project_shell(project, owner):
    """Clone the Project row only (fast). Activities are copied separately."""
    project_copy = copy.deepcopy(project)
    project_copy.pk = None
    project_copy.name = get_unique_name(project_copy, project_copy.name)
    project_copy._state.adding = True
    project_copy.is_finalized = False
    project_copy.is_public = False
    project_copy.owner = owner
    project_copy.save()
    _ensure_admin_membership(project_copy, owner)
    return project_copy


def copy_activities_into(source_project, target_project, owner):
    """Deep-copy every activity of source_project into target_project."""
    for activity in source_project.activities.all():
        copy_activity(activity, target_project, owner)


@transaction.atomic
def copy_project(project, owner):
    try:
        project_copy = create_project_shell(project, owner)
        copy_activities_into(project, project_copy, owner)
        return project_copy
    except Exception as e:
        log.error(f"Error copying project: {e}")
        raise e
```

This fixes the original membership bug (it checked `project.members` on the SOURCE; now `_ensure_admin_membership` checks the TARGET) and keeps a single Admin membership.

- [ ] **Step 3: Remove the duplicate membership create in `ProjectViewSet.copy`**

In `djangoexact/api/views.py` (the `copy` action, ~lines 1188-1200), delete the now-redundant post-copy membership create (originally at line 1197):

```python
    def copy(self, request, pk=None):
        project = self.get_object()
        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        new_project = utils.copy_project(project, self.request.user)
        # (removed) ProjectMembership.objects.create(...): copy_project already
        # creates the Admin membership inside its transaction. The old call ran
        # outside that transaction and could orphan a committed project on failure.

        serializer = ReadProjectSerializer(new_project, context={"request": request})
        return Response(data=serializer.data, status=http_status.HTTP_201_CREATED)
```

- [ ] **Step 4: Local gate**

Run: `python -m py_compile api/utilities.py api/views.py api/tests/test_project_copy_async.py`
Expected: success.

- [ ] **Step 5: Run tests (DB machine / CI)**

Run: `python manage.py test api.tests.test_project_copy_async.CopyProjectMembershipTestCase -v 2`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add api/utilities.py api/views.py api/tests/test_project_copy_async.py
git commit -m "fix(api): dedupe project-copy Admin membership and split copy into shell+populate"
```

---

### Task 10: Copy worker + size-threshold async endpoint

**Files:**
- Create: `djangoexact/api/services/copy_jobs.py`
- Modify: `djangoexact/djangoexact/settings.py` (add `PROJECT_COPY_ASYNC_THRESHOLD`)
- Modify: `djangoexact/api/views.py` (add `ProjectViewSet.copy_async`)
- Test: `djangoexact/api/tests/test_project_copy_async.py` (append)

**Interfaces:**
- Consumes: `api.utilities.create_project_shell`, `api.utilities.copy_activities_into`; `api.services.async_jobs.enqueue`.
- Produces:
  - `copy_jobs.run(job: AsyncJob) -> dict` -> `{"new_project_id": int}`. Reads `job.params`: `source_project_id`, `target_project_id`.
  - `POST /api/projects/{pk}/copy/async/` -> `201` + `ReadProjectSerializer` (small projects, copied inline) OR `202 {"job_id", "new_project_id", "status"}` (large projects, offloaded).

- [ ] **Step 1: Add the setting**

In `djangoexact/djangoexact/settings.py` (near the `CLOUD_RUN_*` block around line 342):

```python
# Projects whose (activities + module-type) count exceeds this are copied via a
# background job instead of synchronously in the request. Small copies stay sync.
PROJECT_COPY_ASYNC_THRESHOLD = int(os.environ.get("PROJECT_COPY_ASYNC_THRESHOLD", "40"))
```

- [ ] **Step 2: Write the failing test (append to `test_project_copy_async.py`)**

```python
from unittest import mock

from django.test import override_settings
from rest_framework.test import APITestCase

from api.models import AsyncJob


class CopyAsyncEndpointTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_authenticate(self.user)

    @override_settings(PROJECT_COPY_ASYNC_THRESHOLD=1000)
    def test_small_project_copies_inline_201(self):
        project = ProjectFactory(owner=self.user)
        with mock.patch("api.views.security.check_permission", return_value=None), \
             mock.patch("api.views.ProjectViewSet.get_object", return_value=project):
            resp = self.client.post(f"/api/projects/{project.pk}/copy/async/")
        self.assertEqual(resp.status_code, 201)
        self.assertNotEqual(resp.data["id"], project.pk)

    @override_settings(PROJECT_COPY_ASYNC_THRESHOLD=0)
    def test_large_project_offloads_202(self):
        project = ProjectFactory(owner=self.user)
        with mock.patch("api.views.security.check_permission", return_value=None), \
             mock.patch("api.views.ProjectViewSet.get_object", return_value=project):
            resp = self.client.post(f"/api/projects/{project.pk}/copy/async/")
        self.assertEqual(resp.status_code, 202)
        self.assertIn("job_id", resp.data)
        self.assertIn("new_project_id", resp.data)
        job = AsyncJob.objects.get(pk=resp.data["job_id"])
        self.assertEqual(job.kind, AsyncJob.Kind.PROJECT_COPY)


class CopyJobRunTestCase(TestCase):
    def test_run_populates_target(self):
        from api.services import copy_jobs
        owner = UserFactory()
        source = ProjectFactory(owner=owner)
        target = utils.create_project_shell(source, owner)
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.PROJECT_COPY, created_by=owner,
            params={"source_project_id": source.pk, "target_project_id": target.pk},
        )
        result = copy_jobs.run(job)
        self.assertEqual(result["new_project_id"], target.pk)
```

- [ ] **Step 3: Create `djangoexact/api/services/copy_jobs.py`**

```python
"""Worker handler for async project copy: populate a pre-created shell project."""
from django.db import transaction

from api import utilities as utils
from api.models import AsyncJob, Project


def run(job: AsyncJob) -> dict:
    params = job.params
    source = Project.objects.get(pk=params["source_project_id"])
    target = Project.objects.get(pk=params["target_project_id"])
    with transaction.atomic():
        utils.copy_activities_into(source, target, job.created_by)
    return {"new_project_id": target.pk}
```

- [ ] **Step 4: Add the `copy_async` action to `ProjectViewSet` in `djangoexact/api/views.py`**

Place beside the existing `copy` action (~line 1180):

```python
@action(detail=True, methods=["post"], url_path="copy/async")
def copy_async(self, request, pk=None):
    """Smart copy: inline (201) for small projects, offloaded (202) for large.

    The legacy synchronous `copy/` action is unchanged. New clients should call
    this endpoint and handle both 201 (body is the new project) and 202
    (poll GET /api/async-jobs/{job_id}/, then GET /api/projects/{new_project_id}/).
    """
    project = self.get_object()
    error = security.check_permission("view_project", request.user, project)
    if error:
        return error

    activity_count = project.activities.count()
    module_count = sum(a.module_types.count() for a in project.activities.all())
    threshold = getattr(settings, "PROJECT_COPY_ASYNC_THRESHOLD", 40)

    if activity_count + module_count <= threshold:
        new_project = utils.copy_project(project, request.user)
        serializer = ReadProjectSerializer(new_project, context={"request": request})
        return Response(data=serializer.data, status=http_status.HTTP_201_CREATED)

    with transaction.atomic():
        shell = utils.create_project_shell(project, request.user)
    params = {"source_project_id": project.pk, "target_project_id": shell.pk}
    job = async_jobs.enqueue(AsyncJob.Kind.PROJECT_COPY, params, user=request.user, project=shell)
    return Response(
        {"job_id": job.pk, "new_project_id": shell.pk, "status": job.status},
        status=http_status.HTTP_202_ACCEPTED,
    )
```

Confirm `transaction` (`from django.db import transaction`) is imported in `views.py` (it is: `update` uses `@transaction.atomic`).

- [ ] **Step 5: Local gate**

Run: `python -m py_compile api/services/copy_jobs.py djangoexact/settings.py api/views.py api/tests/test_project_copy_async.py`
Expected: success. (Run the settings compile as `python -m py_compile djangoexact/settings.py` from the Django root.)

- [ ] **Step 6: Run tests (DB machine / CI)**

Run: `python manage.py test api.tests.test_project_copy_async -v 2`
Expected: PASS (all classes).

- [ ] **Step 7: Commit**

```bash
git add api/services/copy_jobs.py djangoexact/djangoexact/settings.py api/views.py api/tests/test_project_copy_async.py
git commit -m "feat(api): add size-threshold async project copy (copy/async + copy_jobs)"
```

---

## PHASE D — Deploy / infrastructure

### Task 11: WeasyPrint native deps in the job image

**Files:**
- Modify: `deploy/Dockerfile.computation_job`

**Interfaces:** none (container build). Rationale: the `exact-computation-job` image is `python:3.11-slim` and has never needed WeasyPrint (LUC compute does not render PDFs). Report generation in the job requires Pango/Cairo/GDK-PixBuf plus fonts, or PDFs render with fallback typography.

- [ ] **Step 1: Add an apt layer before `pip install`**

In `deploy/Dockerfile.computation_job`, in the stage that installs Python deps, add before the `RUN pip install -r ... requirements.txt` line:

```dockerfile
# WeasyPrint (report PDF) native dependencies + base fonts. matplotlib wheels
# are self-contained, but WeasyPrint needs system Pango/Cairo/GDK-PixBuf/fonts.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fontconfig \
        fonts-dejavu \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
```

If the report templates rely on specific fonts (check `djangoexact/api/templates/reports/` CSS `font-family` declarations), add the matching `fonts-*` packages here so rendered output matches the synchronous path.

- [ ] **Step 2: Build locally to verify (DB/Docker machine only; skip in the no-Docker sandbox)**

Run: `docker build -f deploy/Dockerfile.computation_job -t exact-computation-job:weasytest .`
Then smoke-test WeasyPrint inside the image:
`docker run --rm exact-computation-job:weasytest python -c "from weasyprint import HTML; HTML(string='<h1>ok</h1>').write_pdf(); print('WEASYPRINT_OK')"`
Expected: prints `WEASYPRINT_OK` with no missing-library errors.

If Docker is unavailable in your environment, note in the PR that this build check must run in CI or on a Docker-equipped machine before merge.

- [ ] **Step 3: Commit**

```bash
git add deploy/Dockerfile.computation_job
git commit -m "build(job): add WeasyPrint native deps + fonts to computation job image"
```

---

### Task 12: Reconciler schedule, GCS lifecycle, deploy verification, docs

**Files:**
- Modify: `.github/workflows/deploy.yaml` (documentation/verification note only — no new job resource)
- Create/modify: infra docs under `djangoexact/docs/` (or repo `docs/`) describing the operational runbook

**Interfaces:** none (operational). The web SA already has permission to trigger job executions (LUC dispatch proves it); the job SA already reaches Cloud SQL + GCS. No new IAM required.

- [ ] **Step 1: Cloud Scheduler for the reconciler**

The `run_computation_job` reconciler (`reconcile_stale_jobs`) is described as "intended to run on a schedule". Confirm whether a Cloud Scheduler job already invokes stale reconciliation. If yes, add `reconcile_stale_async_jobs` to the same schedule target. If no scheduler exists, document creating one that runs (hourly) either:
- a Cloud Run Job execution overriding args to `["python","manage.py","reconcile_stale_async_jobs"]`, or
- an authenticated request to a small admin endpoint that runs the command.

Write the chosen mechanism into the runbook doc (Step 3). Do not silently rely on it: if no scheduler is provisioned, stale jobs still auto-fail only when the reconciler is invoked.

- [ ] **Step 2: GCS lifecycle rule for report objects**

Add a lifecycle rule to the `STORAGE_BUCKET` deleting objects under the `reports/` prefix after N days (recommend 7). This is a bucket config change (Terraform/gcloud), applied out-of-band from the app deploy. Example (documented in the runbook, run by an operator):

```bash
# lifecycle.json: {"rule":[{"action":{"type":"Delete"},"condition":{"age":7,"matchesPrefix":["reports/"]}}]}
gcloud storage buckets update gs://$STORAGE_BUCKET --lifecycle-file=lifecycle.json
```

- [ ] **Step 3: Write the operational runbook**

Create `djangoexact/docs/guides/async-jobs.md` documenting: the `AsyncJob` lifecycle; which endpoints enqueue/poll/download; the reused `exact-computation-job` image + `run_async_job` command; the reconciler + schedule; the GCS `reports/` prefix + lifecycle cleanup; the `PROJECT_COPY_ASYNC_THRESHOLD` knob; and the frontend migration note (WebApp must adopt `report/async` + poll + download, and `copy/async` handling both 201 and 202).

- [ ] **Step 4: Deploy pipeline verification note**

In `.github/workflows/deploy.yaml`, confirm the job-deploy step (gated on `vars.CLOUD_RUN_COMPUTATION_JOB_NAME`) rebuilds and redeploys the `exact-computation-job` image so the WeasyPrint layer from Task 11 ships. No new job resource is added. Add a one-line comment near the job-deploy step noting the image now also serves `run_async_job`. Verify `--task-timeout=3600` still matches the reconciler's 1h `STALE_THRESHOLD`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/deploy.yaml djangoexact/docs/guides/async-jobs.md
git commit -m "docs(ops): async-jobs runbook, reconciler schedule, GCS lifecycle notes"
```

---

## Self-review notes (coverage against the evaluation)

- Reuse Cloud Run Jobs pattern: Tasks 2, 11, 12 (same image, arg override, no new job resource).
- Generic `AsyncJob` model with `kind`: Task 1; consumed everywhere.
- Additive API contract: Tasks 7, 8, 10 add new endpoints; existing `report/` and `copy/` untouched (Task 9 only removes a buggy duplicate write from `copy`, preserving its response).
- Report async (PDF + Excel): Tasks 6, 7, 8, including the `render_to_string` refactor and GCS streaming.
- Copy optimize + threshold hybrid: Tasks 9, 10 (bug fixes + shell/populate split + threshold routing). NOTE: Task 9 preserves the existing per-object save semantics; the further `bulk_create_with_history` throughput rewrite is deferred (see below) because it carries real `simple_history` + comment-thread correctness risk and needs DB-machine testing.
- WeasyPrint deps, IAM, GCS lifecycle, reconciler schedule: Tasks 11, 12.

## Deferred follow-up (out of scope for this plan, flagged intentionally)

- **Batch-insert rewrite of `copy_activity`** using `simple_history.utils.bulk_create_with_history` plus explicit `create_comment_threads`, to make even large copies fast on the sync path. Deferred because `bulk_create` bypasses `Module.save()` (which today drives comment-thread creation and history rows), so it must reproduce both behaviors exactly. Warrants its own plan with golden-record tests on a DB-equipped machine. The size-threshold async path (Task 10) already removes the request-timeout risk in the meantime.
- **Async-ing the public (unauthenticated) report endpoint** in `public/views.py`, if the client needs it.
- **Job completion notifications**: reuse `admin_scripts.notifications.notify_job_completed` for `AsyncJob` (email on completion) if desired.

## Execution handoff

Recommended: implement Phase A fully first (it unblocks everything), then B, then C, then D. Phases B and C are independent of each other once A lands. Task 9's bug fixes are worth landing even independently of the async work.
