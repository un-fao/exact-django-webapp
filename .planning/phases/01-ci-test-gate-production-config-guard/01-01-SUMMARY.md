---
phase: 01-ci-test-gate-production-config-guard
plan: 01
subsystem: infra
tags: [django, system-checks, security, deploy-guard]

requires: []
provides:
  - "check_production_config Django deploy check in djangoexact/api/checks.py"
  - "ApiConfig.ready() registration wiring for the deploy check"
  - "DB-free unit test proving the check's four env-combination behaviors"
affects: [01-03-PLAN.md CI workflow wiring]

tech-stack:
  added: []
  patterns:
    - "Django system check registered via @register(Tags.security, deploy=True), imported inside AppConfig.ready() (mirrors the existing post_migrate signal import idiom)"
    - "APP_MODE read via os.getenv, never settings.APP_MODE, since it is not assigned as a Django setting"

key-files:
  created:
    - djangoexact/api/checks.py
    - djangoexact/api/tests/test_production_config_check.py
  modified:
    - djangoexact/api/apps.py

key-decisions:
  - "Used Error (not Warning) level for both check IDs so manage.py check --deploy fails at its default fail level, per D-11/D-12"
  - "Read APP_MODE via os.getenv, not settings.APP_MODE, per Finding 5 (APP_MODE is a plain env var used only to pick which .env.{mode} file to load, never assigned as a Django setting)"

patterns-established:
  - "Deploy checks live in api/checks.py and are registered by importing the module inside ApiConfig.ready(), following the same in-ready() import idiom already used for signals.py"

requirements-completed: [SEC-03]

coverage:
  - id: D1
    description: "check_production_config fails manage.py check --deploy (Error api.E001) when APP_MODE=production and DEBUG is True"
    requirement: "SEC-03"
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/test_production_config_check.py#test_production_debug_true_flags_e001"
        status: pass
      - kind: other
        ref: "APP_MODE=production DJANGO_DEBUG=True CORS_ALLOWED_ORIGINS=\"\" python manage.py check --deploy (exit code 1)"
        status: pass
    human_judgment: false
  - id: D2
    description: "check_production_config fails manage.py check --deploy (Error api.E002) when APP_MODE=production and CORS_ALLOWED_ORIGINS is empty"
    requirement: "SEC-03"
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/test_production_config_check.py#test_production_empty_cors_flags_e002"
        status: pass
    human_judgment: false
  - id: D3
    description: "The check stays silent (empty list) for a safe production config and for any non-production APP_MODE, even if DEBUG is True"
    requirement: "SEC-03"
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/test_production_config_check.py#test_production_safe_config_passes"
        status: pass
      - kind: unit
        ref: "djangoexact/api/tests/test_production_config_check.py#test_non_production_is_silent"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-07-08
status: complete
---

# Phase 1 Plan 1: Production Config Deploy Guard Summary

**Django deploy-time system check (api.E001/api.E002) blocks `manage.py check --deploy` when APP_MODE=production and DEBUG is on or CORS_ALLOWED_ORIGINS is empty, registered via ApiConfig.ready() and proven by a DB-free SimpleTestCase suite.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-08T13:56:05Z
- **Completed:** 2026-07-08T13:59:04Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Created `djangoexact/api/checks.py` with `check_production_config`, registered `@register(Tags.security, deploy=True)`, emitting `Error` (not `Warning`) findings `api.E001` (DEBUG in production) and `api.E002` (empty CORS in production)
- Wired the check into Django's check framework via a one-line import inside `ApiConfig.ready()`
- Added a DB-free `SimpleTestCase` covering all four env combinations from the plan's `<behavior>` spec
- Locally verified both the unit test suite (4/4 pass) and the real end-to-end behavior: `manage.py check --deploy` exits 1 when `APP_MODE=production`, `DJANGO_DEBUG=True`, `CORS_ALLOWED_ORIGINS=""`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create the production config deploy check (api/checks.py)** - `152dbb16` (feat)
2. **Task 2: Register the check in ApiConfig.ready()** - `d65b8754` (feat)
3. **Task 3: DB-free unit test for the production config check** - `2839a9a3` (test)

**Plan metadata:** pending (docs: complete plan, this commit)

## Files Created/Modified
- `djangoexact/api/checks.py` - New deploy-time system check reading APP_MODE from the environment and emitting Error api.E001/api.E002
- `djangoexact/api/apps.py` - One-line addition inside `ready()` importing `checks` so the check registers
- `djangoexact/api/tests/test_production_config_check.py` - `SimpleTestCase` covering DEBUG-true, empty-CORS, safe-config, and non-production-silent cases

## Decisions Made
- Used `Error` level (not `Warning`) for both check IDs so `manage.py check --deploy` fails at its default fail level, matching D-11/D-12 exactly as specified in the plan.
- Read `APP_MODE` via `os.getenv("APP_MODE")` rather than `settings.APP_MODE`, per Finding 5 in 01-RESEARCH.md; `APP_MODE` is a plain env var used only to select which `.env.{mode}` file to load in settings.py, it is never assigned as a Django setting.

## Deviations from Plan

None - plan executed exactly as written. Task order in the plan (check first, registration second, test third) does not follow classic RED/GREEN task-level TDD sequencing since the plan's frontmatter `type` is `execute`, not `tdd`; the plan-level TDD gate enforcement in the executor workflow applies only to `type: tdd` plans, so no gate violation applies here. All behaviors specified in the plan's `<behavior>` blocks were independently confirmed as passing after Task 3, both via the unit test suite and via a manual `manage.py check --deploy` invocation.

## Issues Encountered

None. The local sandbox has no Postgres/Docker, but this plan's test is a DB-free `SimpleTestCase`, and Django was available via the repo's checked-in `.venv`, so both `python -m py_compile` and the actual `python manage.py test` / `python manage.py check --deploy` commands ran successfully and confirmed the implementation end to end (exceeding the plan's `py_compile`-only local gate).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SEC-03's application-code half is complete and independently verified. Plan 01-03 (CI workflow wiring) can now add `api.tests.test_production_config_check` to the CI test-job label list and insert `python manage.py check --deploy` into the deploy job, per the plan's stated hand-off.
- No blockers identified.

---
*Phase: 01-ci-test-gate-production-config-guard*
*Completed: 2026-07-08*

## Self-Check: PASSED

All created files found on disk (`djangoexact/api/checks.py`, `djangoexact/api/apps.py`, `djangoexact/api/tests/test_production_config_check.py`, this SUMMARY.md). All task commit hashes (`152dbb16`, `d65b8754`, `2839a9a3`) found in `git log --oneline --all`.
