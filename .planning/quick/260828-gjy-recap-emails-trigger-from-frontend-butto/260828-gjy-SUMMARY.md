---
phase: quick-260828-gjy
plan: 01
subsystem: api
tags: [django, simple-history, email, drf]

requires: []
provides:
  - "Project.last_recap_sent_at nullable timestamp (migration 0293)"
  - "send_changes_email windows on last_recap_sent_at instead of locked_at, works unlocked, returns a recipient count"
  - "security.check_project_admin admin-only gate"
  - "POST /projects/{id}/recap/ admin-only, reports sent/count in its 200 body"
affects: [project-lock-workflow, project-export-import, recap-email-frontend-button]

actuals:
  tokens: 6060
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Nullable 'last sent' timestamp captured before the diff is computed, advanced only on success (crash/empty-diff/total-failure safe)"

key-files:
  created:
    - djangoexact/api/migrations/0293_project_last_recap_sent_at.py
    - djangoexact/api/tests/test_recap_email.py
  modified:
    - djangoexact/api/models.py
    - djangoexact/api/utilities.py
    - djangoexact/api/security.py
    - djangoexact/api/views.py
    - djangoexact/api/serializers.py
    - djangoexact/api/templates/changes/changes.html
    - .github/workflows/deploy.yaml

key-decisions:
  - "Kept Project.unlock() byte-identical; auto-trigger stays commented out (D-07, user decision)"
  - "First send (last_recap_sent_at NULL) covers all history since creation via an empty filter dict, no branching (D-04, user decision)"
  - "Recap endpoint tightened from view_project to project-admin-only via new check_project_admin (D-06, user decision)"
  - "Collapsed the four repeated get_changes call sites into one closure (diff()) that also drops empty-changes changelogs, so a first-send creation record can't falsely defeat the no-changes bail-out"
  - "Fixed two pre-existing get_changes defects required for a since-creation window: missing history_user on creation records no longer raises, and the newest history record is no longer unconditionally skipped"

patterns-established:
  - "Lock context (holder name/group/date) degrades gracefully to None/neutral phrasing when a project is unlocked, in both the Python context dict and the template"

requirements-completed: [260828-gjy]

coverage:
  - id: D1
    description: "Project admin can POST /projects/{id}/recap/ on an unlocked project and get a 200 (D-03)"
    requirement: "260828-gjy"
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/test_recap_email.py#SendChangesEmailWindowTestCase (lock guard removed; no locked_at/locked_by required)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Recap covers only changes since the previous recap email, not since lock (D-02); first-ever recap covers all history since creation (D-04)"
    requirement: "260828-gjy"
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/test_recap_email.py#SendChangesEmailWindowTestCase.test_first_send_has_no_lower_date_bound"
        status: pass
      - kind: unit
        ref: "djangoexact/api/tests/test_recap_email.py#SendChangesEmailWindowTestCase.test_subsequent_send_bounds_on_last_recap_timestamp"
        status: pass
    human_judgment: false
  - id: D3
    description: "Window advances only after a successful send; empty diff or total send failure leaves it untouched (D-05)"
    requirement: "260828-gjy"
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/test_recap_email.py#SendChangesEmailAdvanceRuleTestCase.test_successful_send_returns_count_and_advances_timestamp"
        status: pass
      - kind: unit
        ref: "djangoexact/api/tests/test_recap_email.py#SendChangesEmailAdvanceRuleTestCase.test_empty_diff_sends_nothing_and_leaves_timestamp_untouched"
        status: pass
      - kind: unit
        ref: "djangoexact/api/tests/test_recap_email.py#SendChangesEmailAdvanceRuleTestCase.test_failed_send_returns_zero_and_leaves_timestamp_untouched"
        status: pass
    human_judgment: false
  - id: D4
    description: "Non-admin project member gets 403; project Admins and superusers get through (D-06)"
    requirement: "260828-gjy"
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/test_recap_email.py#CheckProjectAdminTestCase (all 3 cases)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Project.unlock() auto-trigger stays commented out (D-07)"
    requirement: "260828-gjy"
    verification:
      - kind: other
        ref: "grep -vE '^\\s*#' api/models.py | grep -c send_changes_email  (returns 0)"
        status: pass
    human_judgment: false
  - id: D6
    description: "200 response distinguishes sent vs not-sent, additive to the existing message key (D-08)"
    requirement: "260828-gjy"
    verification: []
    human_judgment: true
    rationale: "No DRF request-level test exercises ProjectViewSet.recap directly (would require a database); the response shape was verified by code review against the plan's spec, not by an automated HTTP test. A human/API-level check against a real Postgres is the remaining gap."

duration: ~35min
completed: 2026-08-28
status: complete
---

# Quick Task 260828-gjy: Recap Emails Trigger From Frontend Button — Summary

**Turned the project recap email from a lock-driven side effect into a button-driven action: a nullable `Project.last_recap_sent_at` windows `send_changes_email` on "since the previous recap" (or since creation on first send), the endpoint is now project-admin-only and works on unlocked projects, and two pre-existing bugs in `get_changes` (missing-history-user crash, newest-record always dropped) are fixed as a required side effect.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3
- **Files modified:** 9 (7 modified, 2 created)

## Accomplishments
- `Project.last_recap_sent_at` (nullable `DateTimeField`), migration 0293 chaining off `0292_country_iso3`, excluded from `ProjectExportSerializer` so an imported project can't inherit a foreign window
- `send_changes_email` rewritten: windows on the persisted timestamp (empty filter = since creation), no longer requires a lock, returns a recipient count, advances the timestamp only on success, and degrades lock context to a neutral "recap" greeting when unlocked
- `security.check_project_admin` added and wired into `ProjectViewSet.recap`, replacing the `view_project` check; the 200 body now carries `sent`/`count` alongside the existing `message` key
- Two root-cause fixes in `get_changes` (missing `history_user` on creation records, the newest-record skip) — both required for a since-creation window and both also correct the three read-only changelog endpoints sharing this function
- 8 DB-free `SimpleTestCase` tests covering the window kwargs, the advance rule (success/empty-diff/failed-send), and the admin gate; registered in the CI test label list

## Task Commits

1. **Task 1: Persist the per-project recap window start (D-01)** - `8ed2a080` (feat)
2. **Task 2: Window the recap on the last send, unlock the trigger, lock down the endpoint (D-02..D-08)** - `a3a20493` (feat)
3. **Task 3: DB-free regression tests for the window, the advance rule, and the 403 (D-05, D-06)** - `233090ef` (test)

**Plan metadata:** committed separately by the orchestrator after this summary.

## Files Created/Modified
- `djangoexact/api/models.py` - Added `Project.last_recap_sent_at`
- `djangoexact/api/migrations/0293_project_last_recap_sent_at.py` - Generated migration (Project + HistoricalProject)
- `djangoexact/api/serializers.py` - Excluded new field from `ProjectExportSerializer`
- `djangoexact/api/utilities.py` - `send_changes_email` rewrite, `get_changes` bug fixes, `timezone` import
- `djangoexact/api/security.py` - `check_project_admin` guard
- `djangoexact/api/views.py` - `ProjectViewSet.recap` wired to the new guard and return contract
- `djangoexact/api/templates/changes/changes.html` - Greeting/Reviewer block conditional on a lock holder being present
- `djangoexact/api/tests/test_recap_email.py` - New DB-free test module (8 tests)
- `.github/workflows/deploy.yaml` - Registered `api.tests.test_recap_email` in the CI label list

## Decisions Made
- Filter dicts (`{}` vs `{"history_date__gte": ...}`) rather than a sentinel date, so Django's `filter(**{})` naturally means "everything" with no branching — matches the plan's D-04 instruction not to revisit this
- Collapsed the four repeated `get_changes(...filter(history_date__gte=locked_at)...)` call sites into one `diff()` closure that also drops changelogs with an empty `changes` list, so a first-send creation record (which always produces an empty changelog) can't defeat the "nothing to report" bail-out
- Moved the "nothing to report" early return before lock-context resolution (previously it ran after building the full email context) — pure reordering, no behavior change, avoids resolving a lock holder that will never be used
- Endpoint response key is `count` (not `recipients`) for the recipient tally — the plan named the concept but not the exact key; kept it short and consistent with `sent`

## Deviations from Plan

None — plan executed exactly as written, including both required `get_changes` fixes and the D-07 no-touch constraint on `Project.unlock()`.

## Issues Encountered
- Local `python manage.py makemigrations`/`check` calls initially failed with `ModuleNotFoundError: No module named 'django'` — the project venv at `.venv/` wasn't activated by default in this shell. Activated it (`source ../.venv/Scripts/activate`) for every subsequent Django command; no code change needed.
- `python manage.py makemigrations` printed a `RuntimeWarning` about a failed Postgres connection (`FATAL: password authentication failed`) while checking migration history consistency — cosmetic; migration generation and `--check --dry-run` both completed successfully afterward.

## Not Verified

The plan's task 3 anticipated `python manage.py test api.tests.test_recap_email --keepdb` might need a reachable Postgres even for `SimpleTestCase`. That did **not** turn out to be true in this environment — Django reported `Skipping setup of unused database(s): default.` and all 8 tests ran and passed with no DB connection:

```
cd djangoexact && source ../.venv/Scripts/activate && python manage.py test api.tests.test_recap_email --keepdb -v 2
# Ran 8 tests in 0.002s — OK
```

What was **not** exercised locally (no DB, no running server):
- `POST /projects/{id}/recap/` end-to-end through DRF (routing, `get_object`, the actual 200/403 response bodies) — only `security.check_project_admin` and `utilities.send_changes_email` were unit-tested in isolation.
- The migration's `AddField` operations actually applying to a real Postgres schema (`makemigrations --check --dry-run` confirms the migration is complete and matches the models, but does not run it).

A DB-equipped machine (or CI, once its `if: false` test-suite gate is lifted per the pre-existing `exact-django-webapp-1b8` note in `deploy.yaml`) should run:
```
cd djangoexact && python manage.py migrate && python manage.py test api.tests.test_recap_email --keepdb
```
and separately exercise `POST /projects/{id}/recap/` against a real project fixture to confirm the HTTP-layer response shape (D-08 / coverage item D6 above).

## User Setup Required

None - no external service configuration required. This is backend-only; the frontend button lives in a separate repo and is out of scope for this task.

## Next Phase Readiness
- The endpoint contract (`{"message": ..., "sent": bool, "count": int}`) is ready for the frontend repo to build a recap button against.
- The CI test-suite step that would run `api.tests.test_recap_email` in a real pipeline is currently disabled (`if: false`, tracked as pre-existing issue `exact-django-webapp-1b8` in `deploy.yaml`) — unrelated to this task, but worth noting the new test won't actually execute in CI until that gate is re-enabled.

---
*Phase: quick-260828-gjy*
*Completed: 2026-08-28*

## Self-Check: PASSED

All 3 created files found on disk; all 3 task commit hashes (`8ed2a080`, `a3a20493`, `233090ef`) found in git log.
