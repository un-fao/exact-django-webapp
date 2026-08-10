---
task: Async report email notification with 24h tokenized download link
slug: async-report-email-link
beads: exact-django-webapp-eco
date: 2026-07-21
branch: feat/async-report-project-copy
base: develop
implementer: Software Architect (agent)
---

# Async report email + 24h self-expiring download link

## Goal

When an async report job (`AsyncJob` kind=`report`) completes, email the requesting
user (`job.created_by`) a link to download the generated report. The link is a
self-contained, signed, 24-hour-expiring token URL to the backend download endpoint,
so it works directly from an inbox with no login. After 24 hours the file is deleted
from GCS and the link stops working.

Builds on the async report machinery shipped in PR #215 (still open, targets develop).

## Locked design decisions

| Decision | Choice |
|---|---|
| Email link | Tokenized backend download URL (no login), decided with user 2026-07-21 |
| Token | `django.core.signing.dumps({"job": pk}, salt="report-download")`, verified with `max_age=86400` (exactly 24h) |
| Link base | New `BACKEND_BASE_URL` env setting (absolute URL to the API host) |
| Deletion | In-repo `cleanup_expired_reports` management command (precise, testable) + documented GCS lifecycle rule (defense-in-depth) |
| Email trigger | From the `run_async_job` worker after status flips to COMPLETED, report kind only |
| Failure isolation | Email send wrapped in try/except; a mail failure must never fail the job |

## Constraints (hard)

- Never use em-dashes anywhere.
- Public API contract for existing paths must not change. The `download` action stays
  backward compatible: an authenticated owner must still be able to download without a token.
- Dev sandbox has no Postgres/Docker: `python -m py_compile` is the only local gate.
  DB-dependent tests are authored for CI (Django `APITestCase`/`TestCase`, no pytest-django).
- JSON fixtures never hand-edited. Do not touch the untracked
  `0283_patch_auditlog_changes_text_default.py` migration.
- No new migration needed (token is stateless; no model fields added). Confirm this holds.

## Tasks

### T1 - Settings: BACKEND_BASE_URL + report-email toggle
- Add `BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "")` to `settings.py` near `FRONTEND_URL`.
- Add `REPORT_READY_EMAIL_ENABLED` (default True; env-overridable) so ops can disable if SMTP
  is misconfigured. Distinct from the existing `JOB_NOTIFICATIONS_ENABLED` (which gates
  admin_scripts ComputationJob mails and defaults False).
- Update the deployment `.env` templates in the repo root if that is where such vars are declared
  (check `.env.*`); otherwise document the new vars in the runbook only.

### T2 - Token helpers
- In `api/services/report_jobs.py` (or a small `api/services/report_links.py`), add:
  - `make_download_token(job_pk) -> str` using `signing.dumps({"job": job_pk}, salt="report-download")`.
  - `load_download_token(token) -> int | None` using `signing.loads(token, salt="report-download", max_age=86400)`,
    returning the job pk or None on `BadSignature`/`SignatureExpired`.
  - `build_download_url(job) -> str` = `f"{settings.BACKEND_BASE_URL}/api/async-jobs/{job.pk}/download/?token={token}"`.
    (Verify the actual mounted path for the async-jobs router in `api/urls.py` and match it.)

### T3 - Send the email from the worker
- New `api/services/report_notifications.py`: `send_report_ready_email(job)`.
  - No-op if `not REPORT_READY_EMAIL_ENABLED`, kind != REPORT, no `created_by`, or no `created_by.email`.
  - Build the tokenized URL via T2; render `api/templates/api/emails/report_ready.{txt,html}`
    with `{user, job, project, download_url, filename, expiry_hours: 24}`.
  - Send with `EmailMultiAlternatives(subject, text_body, DEFAULT_FROM_EMAIL, [email])` +
    `attach_alternative(html_body, "text/html")`. Wrap in try/except + `logger.exception`.
- Call it from `api/management/commands/run_async_job.py` after the job is saved COMPLETED,
  outside the try/except that marks FAILED, and itself guarded so it cannot fail the job.
- Create the two email templates (branded-lite, no em-dashes, plain fallback).

### T4 - Token-aware download endpoint
- In `AsyncJobViewSet.download` (`api/views.py`): set `permission_classes=[permissions.AllowAny]`
  on the action. Logic:
  - Read `token` query param. If present and `load_download_token` returns a pk, load that job
    directly (unfiltered) - this is the email-link path.
  - Else require `request.user.is_authenticated` and load the job scoped to `created_by=request.user`
    (preserve today's behavior); return 404/403 otherwise.
  - Keep the existing guards: kind == REPORT, status == COMPLETED, `result.gcs_path` present, else 404.
- Because the viewset is `IsAuthenticated` at class level, confirm the per-action `AllowAny`
  actually takes effect (DRF `get_permissions` uses action-level `permission_classes`).

### T5 - Cleanup command (24h deletion)
- `api/management/commands/cleanup_expired_reports.py`, mirroring `reconcile_stale_async_jobs`:
  - Select COMPLETED REPORT jobs with `completed_at < now - 24h` that still have `result.gcs_path`.
  - For each: delete the GCS blob (lazy `from google.cloud import storage`, try/except per blob so
    one failure does not abort the sweep), then clear `gcs_path` from `result` and save
    (so `download` cleanly 404s afterwards). Count and print.
- Idempotent: jobs whose `gcs_path` is already cleared are skipped.

### T6 - Docs + infra
- Update `djangoexact/docs/guides/async-jobs.md`: the email notification, the tokenized link and its
  24h expiry, the `cleanup_expired_reports` command + its Cloud Scheduler cadence (e.g. hourly),
  the GCS lifecycle rule (`gcloud storage buckets update` age=1 day on `reports/` prefix) as
  defense-in-depth, and the new env vars (`BACKEND_BASE_URL`, `REPORT_READY_EMAIL_ENABLED`).

### T7 - Tests (authored for CI)
- `api/tests/test_report_email_link.py` (Django `TestCase`/`APITestCase`):
  - token round-trips; `load_download_token` returns None on tampered/expired (monkeypatch or
    craft an old signature) tokens.
  - `send_report_ready_email` uses `django.core.mail.outbox` (locmem backend via
    `override_settings(EMAIL_BACKEND=...)`) - asserts one message, correct recipient, link present.
  - download endpoint: valid token serves (mock GCS blob), invalid/expired token 404s,
    authenticated owner still works without token, other users still 404.
  - `cleanup_expired_reports`: seeds an old completed report job, mocks storage, asserts blob
    delete called and `gcs_path` cleared; recent job untouched.
- Mock `google.cloud.storage` (no real GCS in tests), mirroring existing async tests.

## Verification gate

- `python -m py_compile` on every changed `.py` (the only reliable local gate).
- Manual read-through that the download endpoint stays backward compatible.
- Tests authored and syntactically valid for CI (cannot run locally: no DB).

## Out of scope

- Frontend changes (SPA already needs to adopt the async endpoints from PR #215).
- Actually provisioning Cloud Scheduler / the GCS lifecycle rule (documented as ops follow-ups).
- Emailing on project copy or on report FAILURE (report success only, per the request).
