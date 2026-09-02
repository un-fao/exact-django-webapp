---
phase: quick-260902-f1z
plan: 01
subsystem: api
tags: [django, drf, migrations, email, permissions]

requires:
  - phase: quick-260828-gjy
    provides: "Button-triggered recap email windowed on last send, with the recap endpoint's check_project_admin idiom"
provides:
  - "ProjectNotificationPreference.is_subscribed (opt-in, default False) replacing is_opted_out (opt-out)"
  - "Migration 0294: RemoveField(is_opted_out) + AddField(is_subscribed, default=False) — wipes prior values"
  - "send_changes_email recipient derivation collapsed to a single queryset (Admin + not globally opted out + subscribed row for this project)"
  - "Admin-only gate on ProjectNotificationPreferenceViewSet create/partial_update/update (PUT delegates to gated PATCH path)"
  - "Caller-neutral wording in security.check_project_admin (no longer names the recap endpoint)"
affects: [recap-email, project-notifications, project-admin-permissions]

actuals:
  tokens: 3879
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Recipient derivation as one filter() call across a multi-valued relation, keeping both preference conditions in the same call so Django resolves them against the same related row"
    - "Inherited ModelViewSet.update overridden to delegate to a gated partial_update, closing an unguarded PUT path"

key-files:
  created:
    - djangoexact/api/migrations/0294_projectnotificationpreference_is_subscribed.py
  modified:
    - djangoexact/api/models.py
    - djangoexact/api/serializers.py
    - djangoexact/api/utilities.py
    - djangoexact/api/views.py
    - djangoexact/api/security.py
    - djangoexact/api/tests/test_recap_email.py

key-decisions:
  - "D-01 (locked): pure opt-in, wipe the slate — migration is RemoveField + AddField(default=False), no RunPython, no grandfathering of existing rows"
  - "D-02 (locked): reuse api.security.check_project_admin for the preference write gate rather than writing a second admin check"

patterns-established:
  - "Preference write paths (create/partial_update/update) all funnel through the same security.check_project_admin gate before touching the database"

requirements-completed: [260902-f1z]

coverage:
  - id: D1
    description: "Field renamed to positive polarity (is_subscribed, default False) across model, both serializers, viewset, and migration 0294"
    requirement: "260902-f1z"
    verification:
      - kind: unit
        ref: "manage.py check && makemigrations --check --dry-run (no pending model changes)"
        status: pass
    human_judgment: false
  - id: D2
    description: "send_changes_email recipient selection is one queryset (Admin, not globally opted out, subscribed row for this project); explicit recipients=[...] still bypasses derivation"
    requirement: "260902-f1z"
    verification:
      - kind: unit
        ref: "api/tests/test_recap_email.py#SendChangesEmailRecipientDerivationTestCase.test_recipient_queryset_shape"
        status: pass
      - kind: unit
        ref: "api/tests/test_recap_email.py#SendChangesEmailRecipientDerivationTestCase.test_explicit_recipients_bypasses_derivation"
        status: pass
    human_judgment: false
  - id: D3
    description: "Non-admin project member gets 403 on preference create and writes nothing; admin reaches get_or_create with the renamed field"
    requirement: "260902-f1z"
    verification:
      - kind: unit
        ref: "api/tests/test_recap_email.py#ProjectNotificationPreferenceCreateGateTestCase.test_non_admin_create_is_rejected_and_writes_nothing"
        status: pass
      - kind: unit
        ref: "api/tests/test_recap_email.py#ProjectNotificationPreferenceCreateGateTestCase.test_admin_create_reaches_get_or_create_with_new_field_name"
        status: pass
    human_judgment: false
  - id: D4
    description: "PUT on the preference endpoint can no longer bypass ownership/admin gates (inherited ModelViewSet.update now delegates to gated partial_update)"
    requirement: "260902-f1z"
    verification:
      - kind: unit
        ref: "grep-based structural check: exactly one def update in ProjectNotificationPreferenceViewSet, delegating to partial_update"
        status: pass
    human_judgment: false

duration: 3min
completed: 2026-09-02
status: complete
---

# Quick Task 260902-f1z: Per-Project Opt-In for Automated Recap Summary

**Inverted `ProjectNotificationPreference` from opt-out to opt-in (migration 0294, drop-then-add), collapsed recipient derivation to a single queryset, and gated every preference write path on project-admin.**

## Performance

- **Duration:** 3 min (11:00:10 -> 11:02:44 CEST, per task commit timestamps)
- **Tasks:** 3
- **Files modified:** 6 modified + 1 created (7 total, matches plan's `files_modified`)

## Accomplishments
- `ProjectNotificationPreference.is_opted_out` replaced with `is_subscribed` (default `False`); migration 0294 wipes the slate per D-01 (no `RunPython`, no value carry-forward)
- `send_changes_email` recipient selection is now one queryset (`project.members.filter(group__name="Admin", user__is_opted_out_of_emails=False, user__project_notification_preferences__project=project, user__project_notification_preferences__is_subscribed=True)`), replacing the per-member N+1 loop; explicit `recipients=[...]` still bypasses derivation entirely
- `ProjectNotificationPreferenceViewSet.create` and `partial_update` both call `security.check_project_admin` before any write; a new `update()` delegates to `partial_update` so PUT can't bypass the gate (D-02)
- `security.check_project_admin`'s message/log wording generalized to caller-neutral project-admin phrasing (no longer names the recap endpoint specifically); the recap endpoint's swagger 403 doc and the new preference-create 403 doc both use the updated wording
- 4 new DB-free tests added to `api/tests/test_recap_email.py` covering: the recipient queryset shape (cases a/b/c collapse into one assertion), the explicit-recipients bypass, non-admin 403 with no write (case d), and the admin path reaching `get_or_create` with the renamed field

## Task Commits

Each task was committed atomically:

1. **Task 1: Invert the preference to opt-in, model through consumer (D-01)** - `f2036cdd` (feat)
2. **Task 2: Gate every preference write path on project admin (D-02)** - `f819f679` (feat)
3. **Task 3: DB-free tests for the four CONTEXT cases** - `a1d20733` (test)

**Plan metadata:** committed by orchestrator after this SUMMARY (per constraint: this executor does not commit docs artifacts)

## Files Created/Modified
- `djangoexact/api/migrations/0294_projectnotificationpreference_is_subscribed.py` - hand-written migration: `RemoveField(is_opted_out)` + `AddField(is_subscribed, default=False)`, depends on `0293_project_last_recap_sent_at`
- `djangoexact/api/models.py` - `ProjectNotificationPreference.is_subscribed` field + updated `__str__`
- `djangoexact/api/serializers.py` - both read and write serializer `fields` lists renamed
- `djangoexact/api/utilities.py` - `send_changes_email` recipient block collapsed to one queryset with a comment explaining why both preference conditions must stay in one `filter()` call
- `djangoexact/api/views.py` - `create`/`partial_update` read validated data via `.get("is_subscribed", False)`, both now call `security.check_project_admin`; new `update()` delegates to `partial_update`; swagger 403 docs updated
- `djangoexact/api/security.py` - `check_project_admin` message/log/docstring generalized to caller-neutral wording
- `djangoexact/api/tests/test_recap_email.py` - 4 new test methods across 2 new test case classes

## Decisions Made
- Followed D-01 and D-02 exactly as locked in CONTEXT.md — no grandfathering, no second admin check.
- Extended `security.check_project_admin`'s docstring/message generalization to remove every mention of "recap email" (not just the two strings named in the plan action text), since the Task 2 `<verify>` block asserts zero occurrences of "recap email" anywhere in `security.py`, including the docstring parenthetical.
- In the Task 3 admin-path test, added a patch on `api.views.ProjectNotificationPreferenceReadSerializer` (not explicitly named in the plan's "same patches" instruction) so the success-path response construction doesn't attempt to serialize a bare `SimpleNamespace` fake preference through the real nested `ProjectNameIdSerializer`/`UserReadSerializer` — a Rule 3 blocking-issue fix scoped entirely to the new test, no production code touched.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Generalized security.py docstring beyond the two named strings**
- **Found during:** Task 2 verification
- **Issue:** The plan named the log line and error message as needing generalization; the `<verify>` block's `grep -c "recap email" api/security.py` check additionally caught the docstring's parenthetical example, which the first edit pass left untouched
- **Fix:** Removed the "(e.g. triggering a recap email, managing project notification subscriptions)" parenthetical from the docstring, leaving a purely caller-neutral docstring
- **Files modified:** djangoexact/api/security.py
- **Verification:** `grep -c "recap email" api/security.py` returns 0
- **Committed in:** f819f679 (Task 2 commit)

**2. [Rule 3 - Blocking] Patched ProjectNotificationPreferenceReadSerializer in the admin-path create test**
- **Found during:** Task 3, writing the admin-path success test
- **Issue:** `create()`'s success path constructs `ProjectNotificationPreferenceReadSerializer(preference).data` and passes it to `Response(...)`; with a bare `SimpleNamespace` fake preference (no real `project`/`user` model instances), the real nested serializers would attempt to introspect attributes the fake doesn't meaningfully provide, making the test's outcome depend on unrelated serializer internals rather than on the gate/rename being tested
- **Fix:** Added `@patch("api.views.ProjectNotificationPreferenceReadSerializer")` to both new create-gate tests so the response construction is inert Mock plumbing; the assertions target only `get_or_create` call presence/absence and its `defaults` kwarg
- **Files modified:** djangoexact/api/tests/test_recap_email.py
- **Verification:** both tests pass; `python manage.py test api.tests.test_recap_email --keepdb -v 2` — 12/12 green
- **Committed in:** a1d20733 (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking, both minimal and scoped to satisfying the plan's own `<verify>`/test-correctness requirements)
**Impact on plan:** No scope creep — both fixes tighten conformance to the plan's stated intent rather than adding new behavior.

## Issues Encountered
None beyond the two deviations above.

## User Setup Required
None - no external service configuration required. This is a backend-only change; the frontend (separate repo) needs to be updated to send `is_subscribed` instead of `is_opted_out` with inverted polarity, per the plan's explicit no-compatibility-shim decision.

## Next Phase Readiness
- Backend is fully wired: model, migration, serializers, viewset, and recipient derivation all agree on `is_subscribed`.
- Migration 0294 has not yet been applied against a live Postgres in this session (no local DB reachable); `makemigrations --check --dry-run` confirms no model drift, but running `manage.py migrate` against staging/production is still needed before deploy.
- Frontend repo needs a corresponding update: field renamed and polarity inverted, no compatibility alias exists by design (D-01).

---
*Quick task: 260902-f1z*
*Completed: 2026-09-02*

## Self-Check: PASSED

All 7 files_modified paths exist on disk plus the SUMMARY.md itself; commits f2036cdd, f819f679, a1d20733 all found in `git log --oneline --all`.
