---
phase: quick-260729-exi
plan: 01
subsystem: database
tags: [django, auth-group, review-database, data-cleanup, django-orm]

requires: []
provides:
  - "Staff auth Group and its permission links removed from the review environment database"
  - "Evidenced before/after transcripts proving no user, membership, or invitation data was collaterally affected"
affects: []

tech-stack:
  added: []
  patterns:
    - "Data-only cleanup pattern: read-only inspection script first, checkpoint on findings, then a transaction.atomic deletion script with a re-resolve-and-assert identity check plus an allowlist safety net on the final delete() mapping, followed by a fresh-process verification script consuming baselines via environment variables"

key-files:
  created:
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/inspect_staff.py
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/delete_staff.py
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/verify_staff.py
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/01-inspection.txt
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/02-deletion.txt
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/03-verification.txt
  modified: []

key-decisions:
  - "Checkpoint decision: proceed-full, selected because the inspection found zero membership traces of any kind (STAFF_LINKED_USER_COUNT=0, STAFF_MEMBERSHIP_COUNT=0, STAFF_INVITATION_COUNT=0, STAFF_INVITATION_HISTORY_ROWS=0), so the ProjectInvitation CASCADE concern was theoretical for the current review database state and the deletion touched only the Staff auth_group row and its permission links"

patterns-established:
  - "Re-resolve-by-name-and-assert-pk guard before any destructive ORM operation against a shared, human-editable database table, to catch drift between an inspection read and a later write"

requirements-completed: [STAFF-01, STAFF-02, STAFF-03, STAFF-04]

coverage:
  - id: D1
    description: "Staff auth Group (id=5) and its 1253 auth_group_permissions rows removed from the review database"
    requirement: "STAFF-01"
    verification:
      - kind: manual_procedural
        ref: ".planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/03-verification.txt (CHECK_1_STAFF_GROUP_ABSENT=PASS, CHECK_6_GROUP_COUNT_MINUS_ONE=PASS)"
        status: pass
    human_judgment: false
  - id: D2
    description: "All CustomUser rows and the is_staff flag preserved unchanged before and after the deletion"
    requirement: "STAFF-02"
    verification:
      - kind: manual_procedural
        ref: ".planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/03-verification.txt (CHECK_5_USERS_PRESERVED=PASS total_users baseline=82 now=82; is_staff_users baseline=6 now=6)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Zero rows in the CustomUser/Group through table, ProjectMembership, and ProjectInvitation reference the deleted Staff group id, and no unrelated ProjectMembership row was collaterally removed"
    requirement: "STAFF-03"
    verification:
      - kind: manual_procedural
        ref: ".planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/03-verification.txt (CHECK_2, CHECK_4, CHECK_7 all PASS)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every removed/affected trace type recorded per row with the group id, attributable to named users and projects, in three evidence transcripts"
    requirement: "STAFF-04"
    verification:
      - kind: manual_procedural
        ref: ".planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/01-inspection.txt, evidence/02-deletion.txt, evidence/03-verification.txt"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-07-29
status: complete
---

# Quick Task 260729-exi: Remove Staff role and membership traces Summary

**Deleted the residual Staff auth Group (id=5, 1253 permission rows) and confirmed via a fresh-process verification script that all 82 users, all 6 is_staff=True users, all 734 ProjectMembership rows, and all 86 ProjectInvitation rows were untouched, because the inspection found the group had zero linked users, zero memberships, and zero invitations before deletion.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-29T08:54:00Z
- **Completed:** 2026-07-29T08:58:00Z
- **Tasks:** 3 (Task 1 inspect, Task 2 checkpoint decision, Task 3 delete + verify)
- **Files modified:** 6 (all under `.planning/`; nothing under `djangoexact/`)

## Accomplishments

- Ran a read-only inspection script against the review database (`cloud-sql-proxy` at 127.0.0.1:5432, `APP_MODE=review`) that resolved the Staff group by name, walked all three trace types (M2M through table, ProjectMembership, ProjectInvitation plus its history), ran Django's `NestedObjects` collector, and captured baseline totals.
- Presented the findings at a blocking `checkpoint:decision` gate before any write. The developer selected **proceed-full**.
- Executed the deletion inside a single `transaction.atomic` block: re-resolved the group by name and asserted its primary key matched the value recorded during inspection (guards against drift between read and write), cleared the M2M links, deleted matching `ProjectMembership` and `ProjectInvitation` rows, deleted the group itself through the concrete `django.contrib.auth.models.Group` manager (not the `api.Group` proxy), and applied an allowlist safety assertion over the group's own `delete()` return mapping to catch any cascade path the plan did not foresee.
- Ran a separate, fresh-process verification script that asserted 7 labeled checks against the Task 1 baselines, all of which passed.

## Task Commits

This is a data-only quick task against the review database; no source files under `djangoexact/` were touched, so there are no per-task feature commits. The orchestrator handles the single docs commit for the `.planning/` artifacts listed under `key-files.created` above.

## Files Created/Modified

- `.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/inspect_staff.py` - Read-only ORM inspection of the Staff group footprint, printing a greppable transcript
- `.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/delete_staff.py` - Transactional deletion with identity re-verification and an allowlist safety net
- `.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/verify_staff.py` - Fresh-process, baseline-driven verification of the post-deletion state
- `.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/01-inspection.txt` - Inspection transcript, ends `RESULT: INSPECTION_COMPLETE`
- `.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/02-deletion.txt` - Deletion transcript, ends `RESULT: DELETION_COMPLETE`
- `.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/03-verification.txt` - Verification transcript, ends `RESULT: VERIFICATION_PASSED`

## Before / After State

Recorded from `evidence/01-inspection.txt` (baseline, before deletion):

```
STAFF_GROUP_ID=5
STAFF_GROUP_NAME='Staff'
STAFF_GROUP_PERMISSION_COUNT=1253
THROUGH_TABLE_NAME=api_customuser_groups
STAFF_LINKED_USER_COUNT=0
STAFF_MEMBERSHIP_COUNT=0
STAFF_INVITATION_COUNT=0
STAFF_INVITATION_HISTORY_ROWS=0
COLLECTOR_MODEL label=auth.Group count=1
COLLECTOR_MODEL label=auth.Group_permissions count=1253
BASELINE_TOTAL_USERS=82
BASELINE_USERS_WITH_IS_STAFF_TRUE=6
BASELINE_TOTAL_GROUPS=4
BASELINE_TOTAL_PROJECT_MEMBERSHIPS=734
BASELINE_TOTAL_PROJECT_INVITATIONS=86
BASELINE_TOTAL_THROUGH_TABLE_ROWS=0
```

Recorded from `evidence/02-deletion.txt` (deletion result, mode=proceed-full):

```
CONFIRMED_STAFF_GROUP_ID=5
TX_M2M_LINK_COUNT=0
TX_MEMBERSHIP_COUNT=0
TX_INVITATION_COUNT=0
REMOVED_M2M_LINKS=0
REMOVED_MEMBERSHIP_COUNT=0
REMOVED_INVITATION_COUNT=0
REMOVED_GROUP_COUNT=1254
REMOVED_GROUP_MAPPING={'auth.Group_permissions': 1253, 'auth.Group': 1}
SAFETY_ALLOWLIST=['api.CustomUser_groups', 'api.Group', 'auth.Group', 'auth.Group_permissions']
SAFETY_ASSERTION_PASSED
RESULT: DELETION_COMPLETE
```

No user, project membership, or project invitation row was affected by the deletion because the Staff group had no active traces of any of those types at inspection time. There were no affected user emails or project names to record for this reason.

Recorded from `evidence/03-verification.txt` (post-deletion checks, all pass):

```
CHECK_1_STAFF_GROUP_ABSENT=PASS
CHECK_2_ZERO_STAFF_MEMBERSHIPS=PASS remaining=0
CHECK_3_ZERO_STAFF_INVITATIONS=PASS remaining=0
CHECK_4_ZERO_THROUGH_TABLE_ROWS=PASS remaining=0
CHECK_5_USERS_PRESERVED=PASS total_users baseline=82 now=82; is_staff_users baseline=6 now=6
CHECK_6_GROUP_COUNT_MINUS_ONE=PASS baseline=4 expected=3 now=3 no_staff_name_remaining=True
CHECK_7_MEMBERSHIP_COUNT_DELTA=PASS baseline=734 staff_removed=0 expected=734 now=734
RESULT: VERIFICATION_PASSED
```

No source file under `djangoexact/` was modified at any point in this task (`git status --porcelain djangoexact/` shows only the pre-existing, unrelated diffs to `djangoexact/api/views.py`, `djangoexact/public/views.py`, and two untracked files, which were present before this task started and were never touched by it).

## Two Planning Discoveries Worth Recording

1. **`ProjectInvitation` also cascades from `Group`, not just `ProjectMembership`.** `ProjectInvitation.group` (`djangoexact/api/models.py:899`) is a second `CASCADE` foreign key to `Group`, unlike the original task brief which named only `ProjectMembership`. Because `ProjectInvitation` inherits `Historical` with `cascade_delete_history=True` (`djangoexact/api/models.py:145`), deleting an invitation would also silently delete its `HistoricalProjectInvitation` rows through a `post_delete` signal invisible to Django's `NestedObjects` collector. In this run the invitation count was zero, so the concern never materialized, but the deletion script and evidence transcripts still explicitly measured and reported it (`STAFF_INVITATION_COUNT`, `STAFF_INVITATION_HISTORY_ROWS`) so the next person doing a similar cleanup has the pattern to reuse.
2. **`api.models.Group` is a proxy, not a second table.** It is declared `class Group(auth_models.Group)` with `proxy = True` (`djangoexact/api/models.py:103`), so `api.models.Group` and `django.contrib.auth.models.Group` both address the same `auth_group` row. The deletion script deliberately deleted through the concrete `django.contrib.auth.models.Group` manager rather than the proxy, per the plan's instruction, though either manager would have produced the same database effect.

## Decisions Made

- **Checkpoint decision: proceed-full.** Selected because the inspection showed zero membership traces of any kind, so the deletion touched only the Staff `auth_group` row and its 1253 `auth_group_permissions` rows. No user, membership, or invitation data was at risk either way, making `proceed-full` and `memberships-only` differ only in whether the empty group row itself was removed. `proceed-full` fully satisfies the original request (no residual Staff role visible in the admin or any group listing).

## Deviations from Plan

None - plan executed exactly as written. The one operational note: the plan's second automated verify gate for each task (`git status --porcelain djangoexact/ | grep -c . | grep -qx 0`) fails in this repository state because of pre-existing, unrelated uncommitted changes to `djangoexact/api/views.py` and `djangoexact/public/views.py` (present before this task began, out of scope per the orchestrator's constraints). This task did not add to that diff; every file it touched lives under `.planning/`.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. This task ran entirely against the already-running `cloud-sql-proxy` connection to the review Cloud SQL instance.

## Next Phase Readiness

The Staff group residue is fully removed from the review environment database with an auditable trail. No follow-up work is required; this was a standalone data cleanup with no source code changes, so it has no bearing on the current milestone's phase sequencing (Phase 1: CI Test Gate & Production Config Guard).

## Self-Check: PASSED

All 7 listed artifacts confirmed present on disk (3 scripts, 3 evidence transcripts, this SUMMARY.md). `git status --porcelain djangoexact/` confirmed unchanged by this task (only pre-existing, unrelated diffs remain). No commit was made in this run; the orchestrator handles the single docs commit for `.planning/` artifacts.

---
*Phase: quick-260729-exi*
*Completed: 2026-07-29*
