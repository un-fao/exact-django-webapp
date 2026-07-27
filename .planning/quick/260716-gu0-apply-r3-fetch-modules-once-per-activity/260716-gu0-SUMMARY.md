---
phase: 260716-gu0
plan: 01
subsystem: api
tags: [django, orm, performance, memoization, select_related, reports]

requires:
  - phase: 260716-g2x
    provides: R1 reference-lookup memoization (module_type_for_class, get_ready_status, api/reference_cache.py) and R2 single-Result construction
provides:
  - Per-instance opt-in memoization of Activity.modules via cache_modules()
  - select_related("status") on the per-type module queries inside Activity.__get_all_modules
  - Single shared module fetch per activity across the Excel report readiness pre-pass and compute pass
  - Single module fetch per activity inside build_template_context for the PDF path
affects: [reports, performance, api-views]

tech-stack:
  added: []
  patterns:
    - "Opt-in per-instance memo (self._modules_memo) consulted by an existing property, primed by an idempotent public method (cache_modules()) — avoids signature changes across is_ready/generate_excel_report/BaseProjectReport/BaseActivityReport"

key-files:
  created: []
  modified:
    - djangoexact/api/models.py
    - djangoexact/api/views.py
    - djangoexact/api/reports/__init__.py
    - djangoexact/api/reports/base.py
    - djangoexact/api/reports/html_context.py

key-decisions:
  - "Chose an opt-in per-instance memo on Activity over explicit list-passing or a report-scoped cache object, per the plan's delegated decision, to avoid touching is_ready/generate_excel_report/BaseProjectReport/BaseActivityReport signatures"
  - "select_related scope limited to status only (not activity/activity__project), since reverse-manager module fetches already share the parent Activity instance via Django's known-related-objects mechanism, and joining activity would replace it with fresh per-row copies and defeat the memo"
  - "generate_excel_report's non-None branch filters is_b_intact in Python (list comprehension) instead of re-cloning the queryset, preserving the caller's primed Activity instances; behavior-identical since is_b_intact is a non-nullable BooleanField(default=False)"

patterns-established:
  - "Opt-in memo + idempotent priming method pattern for other N+1 hotspots (R4-R8) flagged in the 260716-g2x research, if applied in future quick tasks"

requirements-completed: [R3-FETCH-MODULES-ONCE-PER-REPORT]

coverage:
  - id: D1
    description: "Activity.modules is memoized per-instance via cache_modules(); non-report callers that never call cache_modules() get an unchanged fresh fetch each access, now with status joined"
    requirement: "R3-FETCH-MODULES-ONCE-PER-REPORT"
    verification:
      - kind: other
        ref: "python -m py_compile djangoexact/api/models.py; grep gates for cache_modules/_modules_memo/select_related(\"status\")/is_ready priming (all passed)"
        status: pass
    human_judgment: true
    rationale: "Static grep and py_compile gates confirm the code shape, but the sandbox has no Postgres/Docker to run the ORM query count assertions or a golden-file Excel/PDF comparison; CI must confirm no regression in report bytes and query counts, per the plan's human-check note"
  - id: D2
    description: "Excel report request (ProjectViewSet.report) materializes one activity list shared by the readiness pre-pass (Project.is_ready) and BaseActivityReport.compute, and generate_excel_report preserves those primed instances instead of re-querying"
    requirement: "R3-FETCH-MODULES-ONCE-PER-REPORT"
    verification:
      - kind: other
        ref: "python -m py_compile djangoexact/api/views.py djangoexact/api/reports/__init__.py djangoexact/api/reports/base.py; grep gates for selected_activities materialization, is_b_intact Python filter, cache_modules() in compute (all passed)"
        status: pass
    human_judgment: true
    rationale: "No local Postgres/Docker to exercise the endpoint end-to-end; CI run and a golden-file Excel comparison (per the plan's human-check) are required to confirm zero behavior change in report bytes and status codes"
  - id: D3
    description: "PDF template context (build_template_context) primes each activity's module list once before the ~12 derived property reads per activity (is_luc, is_fishery, is_livestock, is_energy, area, and the indicator aggregation loop)"
    requirement: "R3-FETCH-MODULES-ONCE-PER-REPORT"
    verification:
      - kind: other
        ref: "python -m py_compile djangoexact/api/reports/html_context.py; grep gate for cache_modules usage (passed)"
        status: pass
    human_judgment: true
    rationale: "PDF rendering path requires WeasyPrint and a live project fixture to visually and byte-compare; not runnable in this sandbox"

duration: 20min
completed: 2026-07-16
status: complete
---

# Phase 260716-gu0 Plan 01: Apply R3 — fetch modules once per activity Summary

**Opt-in per-instance memoization of Activity.modules (cache_modules()) plus select_related("status"), shared across the Excel readiness pre-pass/compute and the PDF template context, eliminating the R3 re-query storm (research hotspot H2).**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-16 (session start)
- **Completed:** 2026-07-16T10:21:26Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added an idempotent `Activity.cache_modules()` method and rewired the `modules` property to consult a per-instance memo (`self._modules_memo`) before falling back to the existing fresh-fetch path, so non-report callers are byte-identical in behavior.
- Joined `status` on the per-type module queries inside `Activity.__get_all_modules`, removing the per-module `StatusType` lazy-load that the readiness pre-pass previously triggered.
- `Project.is_ready` now primes the memo via `cache_modules()` while checking readiness, instead of reading the plain `modules` property.
- `ProjectViewSet.report` materializes one activity list (`list(selected_activities)`) shared by both the readiness pre-pass and `generate_excel_report`, so the compute pass hits the primed memo instead of re-fetching.
- `generate_excel_report`'s non-None branch now filters `is_b_intact` in Python over the caller's instances instead of re-cloning the queryset (which would have discarded the memo and re-queried).
- `BaseActivityReport.compute` iterates `self.activity.cache_modules()` instead of the plain property, benefiting both the Excel path (pure memo hit, already primed) and the PDF/public template path (primes on first access).
- `build_template_context` primes each activity once while building `activities_by_name`, so the ~12 derived property reads per activity in `_compute_activity_contexts` and `_compute_indicator_aggregates` (is_luc, is_fishery, is_livestock, is_energy, is_storage, is_transport, is_processing, is_packaging, is_input, area, and the module loop) transparently reuse the primed list.

## Task Commits

Each task was committed atomically:

1. **Task 1: Memoize Activity module list per instance and select_related status** - `6d3b0b8d` (perf)
2. **Task 2: Share one module fetch per activity across the report request** - `fe5323fe` (perf)

_Note: No TDD tasks in this plan; each task is a single perf commit._

## Files Created/Modified
- `djangoexact/api/models.py` - Added `cache_modules()`, memo-aware `modules` property, `select_related("status")` on per-type module queries, `Project.is_ready` primes the memo
- `djangoexact/api/views.py` - `ProjectViewSet.report` materializes the selected activity list once, shared by the pre-pass and compute
- `djangoexact/api/reports/__init__.py` - `generate_excel_report` filters `is_b_intact` in Python for pre-evaluated activity sequences, preserving caller instances
- `djangoexact/api/reports/base.py` - `BaseActivityReport.compute` iterates via `cache_modules()`
- `djangoexact/api/reports/html_context.py` - `build_template_context` primes each activity's module list once when building `activities_by_name`

## Decisions Made
- Opt-in per-instance memo chosen over explicit list-passing or a report-scoped cache object (plan's delegated decision), avoiding signature changes to `is_ready`, `generate_excel_report`, `BaseProjectReport`, and `BaseActivityReport`.
- `select_related` limited to `status` only; `activity`/`activity__project` deliberately excluded since Django's known-related-objects mechanism already shares the parent Activity instance across reverse-manager module fetches, and joining `activity` would replace it with fresh per-row copies and defeat the memo.
- `generate_excel_report`'s Python-level `is_b_intact` filter is behavior-identical to the ORM `.filter(is_b_intact=False)` it replaces, because `is_b_intact` is a non-nullable `BooleanField(default=False)`.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' verify gates (py_compile, grep counts, em-dash check on new code) passed. Note: the plan's blanket "no em-dash in any touched file" gate found pre-existing em-dashes in unrelated, unmodified regions of `djangoexact/api/views.py` and `djangoexact/api/reports/base.py` (confirmed via `git diff` that no added line contains an em-dash); these are out of scope for this task per the deviation rules' scope boundary and were left untouched.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- R3 applied and committed on `perf/excel-report-reference-caching` (existing branch/PR #210, carrying R1+R2 from 260716-g2x).
- Full-suite regression (pytest / manage.py test against real Postgres) and a golden-file Excel/PDF comparison for the same project fixture before/after are deferred to CI, per the plan's human-check note. Confirm CI is green on this branch before merging.
- R4-R8 from the 260716-g2x research remain out of scope and unaddressed by this task.

---
*Phase: 260716-gu0*
*Completed: 2026-07-16*

## Self-Check: PASSED

All 5 modified files found on disk, SUMMARY.md found, and both task commit hashes (6d3b0b8d, fe5323fe) confirmed present in git log.
