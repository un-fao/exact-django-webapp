---
phase: 260810-nlo
plan: 01
subsystem: api
tags: [django-orm, caching, invalidation, async-jobs, results]

requires: []
provides:
  - "Project.results_stamp (BigIntegerField), bumped atomically via F() from invalidate_module_caches, CachedResultMixin.delete, and Activity.delete"
  - "ProjectResultCache model (project, cache_key, results_stamp, schema_version, payload, computed_at), unique on (project, cache_key), excluded from auditlog"
  - "api/results_cache.py: RESULTS_SCHEMA_VERSION, build_cache_key, normalize_payload, read, write, clear_for_projects"
  - "ProjectViewSet.results serves a stamped cache hit or computes, stores, and returns on miss; permission check stays strictly above the cache read"
  - "scripts/invalidate_results_cache.py clears ProjectResultCache rows and bumps stamps for non-finalized projects (D3a manual lever)"
  - "AsyncJob.Kind.RESULTS_RECOMPUTE plus api/services/results_jobs.py: post-commit, PENDING/RUNNING-deduped, stamp-superseded-aware async cache warming"
affects: [project-results-endpoint, module-delete, activity-delete, ops-invalidation-script, async-job-worker]

tech-stack:
  added: []
  patterns:
    - "Monotonic stamp column bumped via F() through QuerySet.update() as the invalidation signal, read fresh before compute so the row a request writes can never outlive a concurrent edit"
    - "Compute-on-miss, store, return 200 (never 202) for a project-level cache layered above an existing module-level cache"
    - "Async cache warm reproduces the request path off-request (APIRequestFactory + force_authenticate) instead of reimplementing the assembly, so the warmed payload cannot drift from a live compute"

key-files:
  created:
    - djangoexact/api/results_cache.py
    - djangoexact/api/services/results_jobs.py
    - djangoexact/api/migrations/0290_projectresultcache.py
    - djangoexact/api/migrations/0291_asyncjob_results_recompute.py
    - djangoexact/api/tests/test_results_cache.py
    - djangoexact/api/tests/test_project_results_cache_api.py
  modified:
    - djangoexact/api/models.py
    - djangoexact/api/views.py
    - djangoexact/api/management/commands/run_async_job.py
    - djangoexact/djangoexact/settings.py
    - djangoexact/scripts/invalidate_results_cache.py
    - .planning/BACKLOG.md

key-decisions:
  - "Migration 0290 was hand-written with an extra AddField on historicalproject that the plan did not call out: Project inherits Historical (django-simple-history with inherit=True), so a bare AddField on project alone left makemigrations still reporting an unapplied HistoricalProject.results_stamp change. Confirmed by running makemigrations --check --dry-run and reading the diff before finalizing the migration, following the same pattern as the prior is_finalized migration (0227)."
  - "BACKLOG.md was edited (two new entries filed, Open count updated 22 to 24) but left UNSTAGED, per this executor's explicit constraint that BACKLOG.md is a docs artifact for the orchestrator to commit, overriding the plan's own <done> instruction to commit it as a third Task 2 commit."
  - "Minitool grep check (grep -rn ChangeRecord api/calculators.py api/defaults.py api/reports/) returned zero hits, confirming the deferral for the minitool_changes_import bulk path stands per scope_dispositions; no bump call was added there."
  - "results_jobs.run's docstring was reworded mid-task to avoid the literal substring 'activate(' outside a # comment line, after the plan's own activate( grep verification gate caught it inside a docstring explaining the deliberate omission."

requirements-completed: [D1, D2, D3, D3a]

coverage:
  - id: D1
    description: "GET /api/projects/{id}/results/ returns 200 with an unchanged payload shape on both cache hit and cache miss; a hit is byte-equivalent to a live compute for the same project and activity selection"
    requirement: D1
    verification:
      - kind: other
        ref: "manage.py test api.tests.test_results_cache (local, 11/11 pass); manage.py makemigrations --check --dry-run grep for projectresultcache|results_stamp == 0"
        status: pass
      - kind: other
        ref: "api/tests/test_project_results_cache_api.py::test_two_consecutive_calls_return_equal_bodies_both_200 and ::test_second_call_creates_no_additional_cache_row"
        status: not_run
    human_judgment: true
    rationale: "The database-backed API round-trip (hit == live compute, exactly one row per key) is exercised only by test_project_results_cache_api.py, which needs Postgres. This sandbox has no local Postgres/Docker; the module was written but not executed here. CI or a DB-equipped machine must run it before this is fully confirmed."
  - id: D2
    description: "Any project, activity, or module change advances Project.results_stamp; exactly one RESULTS_RECOMPUTE AsyncJob is enqueued per project while none is PENDING or RUNNING; a superseded worker exits without writing"
    requirement: D2
    verification:
      - kind: other
        ref: "manage.py test api.tests.test_results_cache (is_superseded: None/equal/lower stamp cases, local, pass); makemigrations --check --dry-run grep for asyncjob == 0"
        status: pass
      - kind: other
        ref: "AsyncJob PENDING/RUNNING dedupe and post-commit enqueue behavior (results_jobs._enqueue_if_idle)"
        status: not_run
    human_judgment: true
    rationale: "The dedupe query and the post-commit transaction.on_commit wiring are implemented per the plan and pass a static read-through, but exercising the dedupe under real concurrent AsyncJob rows needs Postgres/transactions, which are CI/DB-machine only here."
  - id: D3
    description: "Two pre-existing bugs (load_reference_data invalidates nothing; copy_activity copies a valid cache) are filed in .planning/BACKLOG.md, not fixed, with the D3a mitigation named"
    requirement: D3
    verification:
      - kind: other
        ref: "Two new entries added to .planning/BACKLOG.md Open section (count 22 to 24), each naming scripts/invalidate_results_cache.py as the shipped mitigation"
        status: pass
    human_judgment: false
  - id: D3a
    description: "scripts/invalidate_results_cache.py clears the new project-level rows and bumps the stamp, while still skipping finalized projects"
    requirement: D3a
    verification:
      - kind: other
        ref: "git diff confirms lines 6-38 (cycle_all_modules_and_invalidate_cached_results, including the finalized carve-out) are byte-for-byte unchanged; new invalidate_project_result_caches() filters is_finalized=False and is called from run()"
        status: pass
      - kind: other
        ref: "api.tests.unit.project (pins the finalized-project carve-out at api/tests/unit/project.py:1404-1466)"
        status: not_run
    human_judgment: true
    rationale: "The finalized carve-out logic in cycle_all_modules_and_invalidate_cached_results is untouched (verified by diff), and invalidate_project_result_caches mirrors the same is_finalized=False filter, but the pinning test itself needs Postgres and was not run here."

duration: 55min
completed: 2026-08-10
status: complete
---

# Quick Task 260810-nlo: Cache Project Results with Invalidation and Async Recompute Summary

**Added a project-level cache (ProjectResultCache) for GET /api/projects/{id}/results/, keyed by a monotonic Project.results_stamp bumped atomically at every project/activity/module write path including the two previously-uncovered delete gaps, and warmed asynchronously after each invalidation via a new AsyncJob kind with PENDING/RUNNING dedupe.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-08-10T15:25:00Z (approx, first baseline command)
- **Completed:** 2026-08-10T15:36:20Z (approx, final verification pass)
- **Tasks:** 3 of 3 completed
- **Files modified:** 11 (5 modified pre-existing + created new: 6 new files, 5 modified files, plus BACKLOG.md left unstaged)

## Accomplishments

- `Project.results_stamp` (BigIntegerField, default 0) added and excluded from the `Project.save` dirty-field cascade so writing the stamp itself cannot re-trigger `invalidate_module_caches`.
- `bump_project_results_stamp(project_id)` added, called from `invalidate_module_caches` so both the `Project.save` and `Activity.save` cascades are covered by one edit; atomic via `F("results_stamp") + 1` through `QuerySet.update()`.
- The two previously-uncovered delete paths are now covered: `CachedResultMixin.delete` (top-level Module) resolves the owning project via `get_activity()` before calling `super().delete()`, with a narrow try/except so a broken activity link cannot turn a delete into a 500; `Activity` gained a `delete()` override that captures `project_id` before deleting and bumps after (a failed delete does not bump).
- `ProjectResultCache` model added (not Historical, not DirtyFieldsMixin, excluded from auditlog via `AUDITLOG_EXCLUDE_TRACKING_MODELS`), matching `AsyncJob`'s ephemeral derived-state pattern.
- `api/results_cache.py` provides `build_cache_key` (order/duplicate-insensitive, folds in `RESULTS_SCHEMA_VERSION` and `INVENTORY_SCHEMA_VERSION`), `normalize_payload` (DRF `JSONEncoder` round-trip so a stored payload renders identically to a live one), `read`, `write`, `clear_for_projects`.
- `ProjectViewSet.results` now reads the cache strictly below `security.check_permission`, keyed on a stamp read fresh before compute; never returns 202; wraps the cache write in try/except so a write failure can never change the response.
- `scripts/invalidate_results_cache.py` gained `invalidate_project_result_caches()`, called from `run()`, clearing `ProjectResultCache` rows and bumping stamps for non-finalized projects only, with lines 6-38 of the original file byte-for-byte unchanged.
- `AsyncJob.Kind.RESULTS_RECOMPUTE` and `api/services/results_jobs.py` added: `schedule_recompute` (post-commit, feature-gated by `RESULTS_RECOMPUTE_ENABLED`), `_enqueue_if_idle` (PENDING/RUNNING dedupe, records the stamp in `params`), `is_superseded` (pure predicate), `run` (reproduces `ProjectViewSet.results` off-request via `APIRequestFactory` + `force_authenticate` as `project.owner`, deliberately never activates a locale, raises on non-200 so the job is recorded FAILED). `run_async_job.py` dispatches the new kind; the REPORT-only notification block and the connection-close guard are unchanged.
- Two pre-existing bugs (load_reference_data invalidates nothing; copy_activity copies a valid cache) filed in `.planning/BACKLOG.md` per D3, naming the D3a mitigation.

## Task Commits

Each task was committed atomically:

1. **Task 1: Invalidation core, ProjectResultCache model, stamp on every write path** - `a108fb75` (feat)
2. **Task 2a: Serve project results from a stamped project-level cache** - `a8b0ecc5` (feat)
3. **Task 2b: Clear project result caches in the manual invalidation lever** - `ced5e811` (chore)
4. **Task 3: Recompute project results asynchronously after invalidation** - `efea7f94` (feat)

**Not committed:** `.planning/BACKLOG.md` (Task 2 step 4, the two filed backlog entries) was edited but deliberately left **unstaged**, per this executor's explicit instruction that BACKLOG.md is a docs artifact for the orchestrator to commit alongside SUMMARY.md/STATE.md, overriding the plan's own `<done>` note that named a third `docs(backlog): ...` commit for Task 2.

**Plan/summary metadata:** committed separately by the orchestrator per constraints.

## Files Created/Modified

- `djangoexact/api/models.py` - `Project.results_stamp` field; `bump_project_results_stamp()`; `invalidate_module_caches` now calls it; `CachedResultMixin.delete` and new `Activity.delete` bump the stamp; `AsyncJob.Kind.RESULTS_RECOMPUTE`; `ProjectResultCache` model
- `djangoexact/api/migrations/0290_projectresultcache.py` - New, hand-written: `AddField` on `historicalproject.results_stamp` and `project.results_stamp`, `CreateModel` for `ProjectResultCache`
- `djangoexact/api/migrations/0291_asyncjob_results_recompute.py` - New, hand-written: `AlterField` on `AsyncJob.kind` adding the `RESULTS_RECOMPUTE` choice
- `djangoexact/djangoexact/settings.py` - `AUDITLOG_EXCLUDE_TRACKING_MODELS`; `RESULTS_RECOMPUTE_ENABLED`
- `djangoexact/api/results_cache.py` - New: cache key building, payload normalization, read/write/clear
- `djangoexact/api/views.py` - `ProjectViewSet.results` wired to the cache; `from api import results_cache` import added
- `djangoexact/scripts/invalidate_results_cache.py` - New `invalidate_project_result_caches()`, called from `run()`
- `djangoexact/api/services/results_jobs.py` - New: async recompute worker and scheduler
- `djangoexact/api/management/commands/run_async_job.py` - New `elif` branch dispatching `RESULTS_RECOMPUTE`
- `djangoexact/api/tests/test_results_cache.py` - New: `SimpleTestCase` coverage for `build_cache_key`, `normalize_payload`, `is_superseded`
- `djangoexact/api/tests/test_project_results_cache_api.py` - New: `APITestCase` coverage for the full endpoint contract (CI/DB-gated)
- `.planning/BACKLOG.md` - Two new entries filed (load_reference_data invalidation gap; copy_activity cache copy bug); Open count updated 22 to 24. **Left unstaged, not committed by this executor.**

## Decisions Made

- Hand-wrote both migrations per the plan's instruction, to avoid folding the pre-existing, unrelated `ef_source` `AlterField` drift on the fishery models into the new migrations. Verified via `makemigrations --check --dry-run` before and after each migration: the drift is present at baseline, absent from the grep for the new model/field names after each task, and still present (renumbered) at the very end, confirming it was never touched.
- Discovered mid-Task-1 that the plan's two-operation migration sketch (`AddField` on `project` plus `CreateModel`) was incomplete: `Project` inherits `Historical` (`simple_history.HistoricalRecords(inherit=True)`), so Django also expected the mirrored field on `historicalproject`. Added that `AddField` following the exact pattern of the prior `is_finalized` migration (`0227_historicalprocessingentry_fuel_type_thread_and_more.py`), confirmed by re-running `makemigrations --check --dry-run` until the grep for `projectresultcache|results_stamp` returned `0`.
- Task 3's `activate(` grep verification gate caught its own explanatory docstring (which mentioned `activate()` to describe why the recompute worker does NOT call it). Reworded the docstring to avoid the literal substring outside a `#`-prefixed line, without weakening the explanation.
- Kept `BACKLOG.md`'s edit unstaged per this session's explicit constraint, even though the plan's own `<done>` criteria list a third commit for it; the executor-level constraint takes precedence per the instructions given for this run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Migration 0290 needed an additional AddField for historicalproject.results_stamp**
- **Found during:** Task 1, verification step 2 (`makemigrations --check --dry-run`)
- **Issue:** The plan's migration sketch listed only two operations (`AddField` on `project`, `CreateModel` for `ProjectResultCache`). Running the dry-run check after writing the migration as specified still reported an unapplied `Add field results_stamp to historicalproject` change, because `Project` inherits `Historical`, which auto-generates a mirrored `HistoricalProject` model via django-simple-history.
- **Fix:** Added a matching `AddField` for `historicalproject.results_stamp` to the same migration, following the exact style of the pre-existing `0227_historicalprocessingentry_fuel_type_thread_and_more.py` migration that added `is_finalized` the same way.
- **Files modified:** `djangoexact/api/migrations/0290_projectresultcache.py`
- **Commit:** `a108fb75`

**2. [Rule 3 - Blocking issue] results_jobs.py docstring tripped its own activate( verification grep**
- **Found during:** Task 3, verification step 4 (`grep -vE "^\s*#" ... | grep -c "activate("`)
- **Issue:** The docstring for `run()` explained, in prose, that the function deliberately does not call `django.utils.translation.activate()`. Because the grep only strips `#`-prefixed lines (not docstring lines), the literal substring `activate(` inside the explanatory sentence itself caused the gate to report `1` instead of `0`.
- **Fix:** Reworded the sentence to reference "django.utils.translation" and the omission without the contiguous `activate(` substring, preserving the same explanation.
- **Files modified:** `djangoexact/api/services/results_jobs.py`
- **Commit:** `efea7f94`

No architectural changes, no auth gates, no packages installed.

## Verification Summary

**Run locally in this sandbox (no Postgres/Docker available):**

| Command | Result |
|---|---|
| `py_compile` across every touched/created Python file (models.py, views.py, results_cache.py, results_jobs.py, run_async_job.py, settings.py, invalidate_results_cache.py, both migrations, both test modules) | PASS |
| `manage.py makemigrations --check --dry-run` (grep for `projectresultcache\|results_stamp`) | `0` (clean) |
| `manage.py makemigrations --check --dry-run` (grep for `asyncjob`) | `0` (clean) |
| `manage.py makemigrations --check --dry-run` (full output) | Only the pre-existing, unrelated `ef_source` AlterField drift on largefishery/smallfishery/historical models remains, confirmed present at baseline before any edits and unchanged after |
| `manage.py test api.tests.test_results_cache -v 2` | **11/11 PASS** (build_cache_key x6, normalize_payload x2, is_superseded x3) |
| Auditlog exclusion assertion (`not auditlog.contains(ProjectResultCache)`) | PASS: prints "auditlog exclusion OK" |
| `git diff | grep -cP "\x{2014}"` across the full task diff (41388f79..HEAD) | `0` (no em-dashes) |
| `git diff` on `scripts/invalidate_results_cache.py` confirming lines 6-38 unchanged | Confirmed: diff shows only import-line and post-function additions |
| Minitool deferral grep (`grep -rn ChangeRecord api/calculators.py api/defaults.py api/reports/`) | `0` hits, deferral confirmed to stand |

**NOT run locally (CI or Postgres-equipped machine required, per this sandbox's documented constraint):**

| Command | Reason not run |
|---|---|
| `manage.py test api.tests.test_project_results_cache_api` | New APITestCase suite exercising the full endpoint contract (hit/miss equality, no duplicate rows, stamp-driven recompute, `cached=false` bypass, activity-order collapsing, permission gate), needs Postgres |
| `manage.py test api.tests.unit.project` | Pins the finalized-project carve-out at `api/tests/unit/project.py:1404-1466`, needs Postgres |
| `manage.py test api.tests.test_async_jobs` | Existing AsyncJob suite, unaffected by this change but not re-run, needs Postgres |
| `manage.py migrate` (apply 0290 and 0291) | Needs Postgres; migration files were validated structurally via `makemigrations --check --dry-run` instead |

## Issues Encountered

None beyond the two auto-fixes documented above under Deviations. All plan-cited line numbers (invalidate_module_caches, Project.save cascade, Activity.save cascade, CachedResultMixin, AsyncJob, ProjectViewSet.results, GenericModuleViewSet.results, INVENTORY_SCHEMA_VERSION, the finalized carve-out) matched the plan's citations at read time; no drift required adaptation.

## User Setup Required

None. No external service configuration required. `RESULTS_RECOMPUTE_ENABLED` defaults to on only where `CLOUD_RUN_COMPUTATION_JOB_NAME` is already configured (production), so no environment change is needed to deploy this safely; an operator wanting to exercise the async path locally would set `RESULTS_RECOMPUTE_ENABLED=true`.

## Next Phase Readiness

- All three plan tasks landed and are committed on `feat/project-results-cache`.
- The CI/DB-gated verification items above (test_project_results_cache_api, api.tests.unit.project, api.tests.test_async_jobs, manage.py migrate) should be run on the next CI pass or a Postgres-equipped machine before this branch is considered fully verified.
- `.planning/BACKLOG.md` has an uncommitted edit (two new entries, Open count 22 to 24) awaiting the orchestrator's docs commit.
- No blockers for closing this quick task from the executor's side.

---
*Phase: 260810-nlo*
*Completed: 2026-08-10*

## Self-Check: PASSED

All created files verified present on disk (results_cache.py, services/results_jobs.py, both migrations, both test modules). All four task commit hashes (a108fb75, a8b0ecc5, ced5e811, efea7f94) verified present in `git log --oneline`.
