---
task: Async report email notification with 24h tokenized download link
slug: async-report-email-link
beads: exact-django-webapp-eco
date: 2026-07-21
branch: feat/async-report-project-copy
status: complete
implementer: Software Architect (agent)
---

# Summary

When an async report job (`AsyncJob` kind=`report`) completes, the worker now emails the
requesting user a self-contained, signed, 24-hour download link. After 24 hours the link
expires and the file is deleted from GCS. Builds on the async report machinery in PR #215
(open, targets develop); this work rides the same branch.

## What was built

- **Tokenized download link** (`api/services/report_links.py`): `make_download_token` /
  `load_download_token` (Django `signing`, salt `report-download`, `max_age=86400`) and
  `build_download_url` = `{BACKEND_BASE_URL}/api/async-jobs/{pk}/download/?token=...`.
  Stateless, no migration, no model fields.
- **Email on completion** (`api/services/report_notifications.py` +
  `api/templates/api/emails/report_ready.{txt,html}`): `send_report_ready_email(job)`
  sends an HTML+text mail to `job.created_by`. No-ops if disabled, wrong kind, no
  recipient, or `BACKEND_BASE_URL` unset (avoids emailing a broken link). Fully failure
  isolated. Wired into `run_async_job`'s `finally` block, report-completed only, guarded so
  it can never affect the job outcome.
- **Token-aware download** (`AsyncJobViewSet.download`): now `AllowAny`, serving either a
  valid signed token (email path, unscoped, binds to the pk *inside* the token to prevent a
  swapped-URL-pk escalation) or an authenticated owner (unchanged, still works without a
  token). All existing guards (kind/status/gcs_path) intact. Backward compatible.
- **Deletion** (`api/management/commands/cleanup_expired_reports.py`): deletes the GCS blob
  and clears `result.gcs_path` for completed report jobs older than 24h; per-blob try/except,
  idempotent. Documented hourly Cloud Scheduler cadence + a 1-day GCS lifecycle rule as a
  backstop.
- **Settings**: `BACKEND_BASE_URL` (default ""), `REPORT_READY_EMAIL_ENABLED` (default True).
- **Docs**: `djangoexact/docs/guides/async-jobs.md` updated (email, token link, cleanup
  command, lifecycle rule, env vars).
- **Tests** (`api/tests/test_report_email_link.py`, authored for CI): token round-trip /
  tamper / expiry, email send + all no-op branches, download endpoint (valid token, invalid,
  expired, owner-no-token, other-user), cleanup command (deletes+clears, recent untouched,
  already-cleared skipped).

## Decisions

- Email link = tokenized backend download URL (chosen with user 2026-07-21) over signed GCS
  URLs (rejected earlier for App Engine SA signBlob friction) and login-required links.
- Precise 24h enforcement via an in-repo command (testable) + coarse GCS lifecycle backstop.

## Verification

- `python -m py_compile` passes on all 8 changed .py files (only reliable local gate; no
  Postgres/Docker in the sandbox).
- No em-dashes introduced; fixed one pre-existing em-dash in the settings.py region touched.
- DB-dependent tests authored for CI (Django `TestCase`/`APITestCase`, no pytest-django).

## Follow-ups (ops, out of scope here)

- Set `BACKEND_BASE_URL` per environment; confirm `REPORT_READY_EMAIL_ENABLED`.
- Schedule `cleanup_expired_reports` hourly (reuse the exact-computation-job image via arg
  override) and apply the `reports/` 1-day lifecycle rule.
- Verify the report worker container can reach SMTP.
- Frontend: the emailed link is a direct backend download, so no frontend route is required
  for this feature (the SPA still needs to adopt the async endpoints from PR #215).
