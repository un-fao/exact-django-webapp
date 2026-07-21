---
gsd_summary_version: 1.0
quick_id: 260721-m3y
slug: add-a-metadata-jsonfield-to-customuser
title: Add metadata JSONField to CustomUser
status: complete
beads_issue: exact-django-webapp-awq
branch: feat/customuser-metadata-field
completed: 2026-07-21
---

# Quick Task 260721-m3y: Add metadata JSONField to CustomUser — Summary

## Outcome

Added a free-form `metadata` JSONField to `api.CustomUser` and exposed it
read + write on the authenticated user's own profile. The frontend can now
persist arbitrary frontend-only state against the user without a new endpoint
or table.

## Changes

| File | Change |
|------|--------|
| `djangoexact/api/models.py:88` | Added `metadata = models.JSONField(default=dict, blank=True)` to `CustomUser`. |
| `djangoexact/api/migrations/0290_customuser_metadata_and_more.py` | New additive migration (dep: `0289_asyncjob`) adding `metadata` to both `customuser` and `historicalcustomuser`. |
| `djangoexact/api/serializers.py:280,286` | Added `"metadata"` to `UserReadSerializer` and `UserWriteSerializer` field lists. |

## How the frontend uses it

- **Read:** `GET /api/users/whoami/` (and retrieve) return `metadata` via
  `UserReadSerializer`. The login response also includes it because
  `accounts/serializers.py:UserSerializer` uses `fields = "__all__"`.
- **Write:** `PATCH /api/users/{pk}/` with `{"metadata": {...}}` via
  `UserWriteSerializer`. Partial updates leave metadata untouched when omitted.

## Design decisions

- `default=dict` (not nullable): the field is always a JSON object, so the
  client never null-checks and always has somewhere to write.
- Hand-written migration: sandbox has no Postgres and settings require Firebase
  env to load, so `makemigrations` cannot run locally. The file mirrors the
  prior CustomUser field-add migration (0269) and includes the
  `historicalcustomuser` op required by `HistoricalRecords`.
- `UserSummarySerializer` (api/ + accounts/) intentionally left untouched so
  one user's personal frontend metadata is not exposed in other-user summaries
  (e.g. project member lists).
- No API contract break — all changes additive.

## Verification

- `py_compile` OK on `models.py`, `serializers.py`, and the new migration
  (the only reliable local gate — DB-less sandbox).
- Migration structure verified against the confirmed single migration leaf
  (`0289_asyncjob`) and mirrors the 0269 CustomUser + historical pattern.
- Full Django suite / `makemigrations` deferred to CI / a DB-equipped machine.

## Follow-ups

- None required. Optional future hardening: if untrusted clients could abuse it,
  consider a size cap or schema on the writable `metadata` payload — out of scope
  for this task ("frontend uses it as it pleases").
