---
phase: quick
quick_id: 260820-dkj
status: complete
date: 2026-08-20
commit: ee4a98a6
---

# Summary — 260820-dkj

Project admins can manage members (add, invite, promote to Admin) on finalized projects again.

## What was wrong

`ProjectMembershipViewSet.update()` / `.partial_update()` built
`ProjectMembershipWriteSerializer` without a serializer context. The finalized-project
guard inside `validate()` reads `self.context["request"].user`, so it raised `KeyError`
(HTTP 500) whenever `project.is_finalized` was true. On open projects the boolean
short-circuit skipped the lookup, which hid the bug until a project was finalized.

## Changes

- `djangoexact/api/serializers.py` — new `check_member_management_allowed(project, request)`
  replaces the duplicated guard in `ProjectMembershipWriteSerializer.validate()` and
  `ProjectInvitationWriteSerializer.validate()`. Reads the request via `.get()` (missing
  context → validation error, not a 500) and exempts superusers alongside project Admins,
  matching `utils.has_project_permission`.
- `djangoexact/api/views.py` — pass `context={"request": request}` in both membership
  update views.
- `djangoexact/api/tests/test_finalized_member_management.py` — new DB-free regression
  test (6 cases): admin allowed, superuser allowed, non-admin blocked, missing request
  rejected rather than crashing, archived still closed to everyone, open project unaffected.
- `.github/workflows/deploy.yaml` — added the new module to the (currently disabled) test
  label list.

## Verification

`python manage.py test api.tests.test_finalized_member_management` → 6 tests, OK.
The rest of the suite was not run: it needs the ~25 min seeded reference DB and is
already red on the pre-existing group-permission seeding gap (exact-django-webapp-1b8).

## Note

The test lives in `api/tests/` rather than `api/tests/unit/` because
`api/tests/unit/__init__.py` star-imports `factories.py`, which runs queries at import
time and crashes collection without a seeded database.
