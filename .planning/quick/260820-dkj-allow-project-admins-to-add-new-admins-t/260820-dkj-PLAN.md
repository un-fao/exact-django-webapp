---
phase: quick
quick_id: 260820-dkj
title: Allow project admins to add new admins to finalized projects
date: 2026-08-20
---

# Quick Task 260820-dkj

Project admins can no longer add (or promote) admins on a **finalized** project.

## Root cause

`ProjectMembershipWriteSerializer.validate()` and `ProjectInvitationWriteSerializer.validate()`
both carried a copy-pasted finalized-project guard that reads the acting user via
`self.context["request"].user`.

`ProjectMembershipViewSet.update()` and `.partial_update()` build that serializer
**without** a context (`djangoexact/api/views.py:1689`, `:1704`). On a non-finalized
project the `project.is_finalized and ...` short-circuit never touches the context, so
the bug is invisible. On a finalized project the second operand is evaluated and
`self.context["request"]` raises `KeyError` — an HTTP 500 — so promoting an existing
member to Admin fails for everyone, admins included.

Secondary gap in the same guard: superusers bypass every other project permission check
(`utils.has_project_permission`) but were blocked here, since they are usually not
project members.

## Tasks

1. Replace both copies of the guard with one shared
   `check_member_management_allowed(project, request)` helper in `serializers.py`.
   Read the request with `.get()` so a missing context is a validation error, not a 500,
   and exempt superusers alongside project Admins.
2. Pass `context={"request": request}` in the two membership update views.
3. Add a DB-free regression test for the guard.

## Verify

`python manage.py test api.tests.test_finalized_member_management`
