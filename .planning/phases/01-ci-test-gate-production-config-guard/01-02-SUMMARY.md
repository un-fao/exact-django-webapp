---
phase: 01-ci-test-gate-production-config-guard
plan: 02
subsystem: infra
tags: [django, database, fixtures, ci, security-pins]

requires: []
provides:
  - "TEST.NAME override on the non-GAE DATABASES[\"default\"] branch in settings.py"
  - "api/fixtures/test_seed_data.json loaddata fixture (2 Group + 2 CustomUser rows)"
  - "requirements-dev.txt pinning bandit==1.9.4 and pip-audit==2.10.1"
affects: [01-03-PLAN.md CI workflow wiring]

tech-stack:
  added: []
  patterns:
    - "TEST.NAME sourced from the same DB_NAME env var as the block's NAME, mirroring the existing GAE-branch TEST.NAME convention"
    - "Standalone loaddata fixture deliberately kept out of api/fixtures_manifest.py (that pipeline is documented to exclude User/Group data)"
    - "requirements-dev.txt kept separate from requirements.txt per D-08; both installed together in CI"

key-files:
  created:
    - djangoexact/api/fixtures/test_seed_data.json
    - djangoexact/requirements-dev.txt
  modified:
    - djangoexact/djangoexact/settings.py

key-decisions:
  - "TEST.NAME on the non-GAE branch reads the same DB_NAME env var as the block's NAME so manage.py test --keepdb reuses the already migrated and seeded database instead of creating an empty test_<DB_NAME> (Finding 2)"
  - "Seed fixture rows use stable, high, non-colliding pks (groups 1-2, users 1000-1001) and valid pbkdf2_sha256 password hashes; real password login is never exercised since tests authenticate via force_authenticate (Finding 7)"
  - "Package legitimacy checkpoint approved: bandit==1.9.4 and pip-audit==2.10.1 confirmed via live PyPI verification as published from the canonical PyCQA/pypa repositories, neither yanked"

requirements-completed: [CI-01, CI-02]

coverage:
  - id: D1
    description: "The non-GAE DATABASES[\"default\"] block declares a TEST.NAME so manage.py test --keepdb reuses the migrated and seeded DB"
    requirement: "CI-01"
    verification:
      - kind: other
        ref: "python -m py_compile djangoexact/settings.py and a \"TEST\" key check in the else: branch (both pass)"
        status: pass
      - kind: other
        ref: "Runtime proof (--keepdb actually reusing the seeded DB) executes in CI via plan 01-03; local sandbox has no Postgres/Docker"
        status: deferred
    human_judgment: false
  - id: D2
    description: "loaddata test_seed_data creates the two Group rows and two CustomUser rows the existing test base classes look up"
    requirement: "CI-01"
    verification:
      - kind: other
        ref: "json.load validation confirming 2 auth.group rows (Admin, Second Reviewer) and 2 api.customuser rows (testuser@example.com, test@user.org) each with password + is_active"
        status: pass
      - kind: other
        ref: "grep confirms test_seed_data.json is absent from api/fixtures_manifest.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "requirements-dev.txt pins bandit and pip-audit at the researched versions, kept out of requirements.txt"
    requirement: "CI-02"
    verification:
      - kind: other
        ref: "grep confirms bandit==1.9.4 and pip-audit==2.10.1 in requirements-dev.txt and absence of both from requirements.txt"
        status: pass
      - kind: other
        ref: "Package-legitimacy checkpoint (Task 4): human confirmed both versions on pypi.org, published from PyCQA/bandit and pypa/pip-audit, neither yanked"
        status: pass
    human_judgment: true

duration: unknown (continuation session; started 2026-07-08)
completed: 2026-07-08
status: complete
---

# Phase 1 Plan 2: Test Database Seed and Security Scanner Pins Summary

**Non-GAE settings.py branch gains a same-name TEST database for --keepdb reuse, a versioned test_seed_data.json loaddata fixture supplies the Group/CustomUser rows the test base classes require, and requirements-dev.txt pins bandit==1.9.4 / pip-audit==2.10.1 after a human-verified package-legitimacy checkpoint.**

## Performance

- **Tasks:** 4 (3 auto + 1 checkpoint)
- **Files modified:** 3

## Accomplishments
- Added a `"TEST": {"NAME": os.getenv("DB_NAME", default="$DB_NAME")}` key to the non-GAE `DATABASES["default"]` block in `djangoexact/djangoexact/settings.py`, mirroring the existing GAE-branch convention so the local/CI test database shares a name with the migrated and seeded database
- Created `djangoexact/api/fixtures/test_seed_data.json`, a standalone `loaddata` fixture with two `auth.group` rows ("Admin" pk 1, "Second Reviewer" pk 2) and two `api.customuser` rows ("testuser@example.com" pk 1000, "test@user.org" pk 1001), each with `is_active: true` and a valid pbkdf2_sha256 password hash; deliberately excluded from `api/fixtures_manifest.py`
- Created `djangoexact/requirements-dev.txt` pinning `bandit==1.9.4` and `pip-audit==2.10.1`, kept separate from `requirements.txt` per D-08
- Resolved the Task 4 package-legitimacy checkpoint: the user verified both pins live on PyPI, published from the canonical PyCQA (bandit) and pypa (pip-audit) repositories, and neither version is yanked. Response: "approved"

## Task Commits

Each task was committed atomically:

1. **Task 1: Add TEST.NAME to the non-GAE DATABASES branch (settings.py)** - `bb8300cf` (fix)
2. **Task 2: Create the test-seed loaddata fixture (test_seed_data.json)** - `75cb0490` (feat)
3. **Task 3: Create requirements-dev.txt with pinned bandit and pip-audit** - `992d7b2e` (feat)
4. **Task 4: Package legitimacy checkpoint** - no code change; human approval recorded below (resolved in this continuation session)

**Plan metadata:** pending (docs: complete plan, this commit)

## Files Created/Modified
- `djangoexact/djangoexact/settings.py` - Added `TEST.NAME` to the non-GAE `DATABASES["default"]` block, sourced from the same `DB_NAME` env var as the block's `NAME`
- `djangoexact/api/fixtures/test_seed_data.json` - New loaddata fixture with 2 `auth.group` rows and 2 `api.customuser` rows consumed by `api/tests/base_test_classes.py` and `api/tests/unit/utils.py`
- `djangoexact/requirements-dev.txt` - New file pinning `bandit==1.9.4` and `pip-audit==2.10.1`

## Decisions Made
- `TEST.NAME` reads `DB_NAME` (not a hardcoded literal) so it stays consistent with the block's existing `NAME` source and with the GAE branch's pattern.
- Seed fixture pks were chosen deliberately high and non-sequential (groups 1-2, users 1000-1001) to avoid colliding with rows other fixtures or tests might create.
- Package-legitimacy checkpoint (Task 4) resolved with explicit human approval after live PyPI verification, per the plan's non-auto-approvable, `gate="blocking-human"` instruction.

## Deviations from Plan

None - plan executed exactly as written across all four tasks, including the mandatory human checkpoint at Task 4.

## Checkpoint Resolution

**Task 4: Package legitimacy checkpoint for bandit and pip-audit pins**
- **Type:** checkpoint:human-verify, `gate="blocking-human"` (not auto-approvable regardless of `workflow.auto_advance`)
- **What was verified:** `https://pypi.org/project/bandit/1.9.4/` and `https://pypi.org/project/pip-audit/2.10.1/`, confirming both versions exist, are published by the PyCQA (bandit) and pypa (pip-audit) projects respectively, and are not yanked
- **User response:** "approved"
- **Outcome:** The pins in `djangoexact/requirements-dev.txt` (`bandit==1.9.4`, `pip-audit==2.10.1`) are confirmed legitimate and cleared for installation in the CI test job wired in plan 01-03

## Issues Encountered

None. The local sandbox has no Postgres/Docker, so the runtime proof that `--keepdb` reuses the seeded database and that the seed fixture unblocks the base-class tests is deferred to plan 01-03's CI execution, as specified in this plan's `<verification>` section.

## User Setup Required

None further - the one manual step required by this plan (the package-legitimacy checkpoint) is complete.

## Next Phase Readiness

- Plan 01-03 can now wire the CI test job: `pip install -r requirements.txt -r requirements-dev.txt`, `loaddata test_seed_data`, and `manage.py test --keepdb`, all against DB artifacts this plan supplies.
- No blockers identified.

---
*Phase: 01-ci-test-gate-production-config-guard*
*Completed: 2026-07-08*

## Self-Check: PASSED

All referenced files found on disk (`djangoexact/djangoexact/settings.py`, `djangoexact/api/fixtures/test_seed_data.json`, `djangoexact/requirements-dev.txt`, this SUMMARY.md). All task commit hashes (`bb8300cf`, `75cb0490`, `992d7b2e`) found in `git log --oneline --all`.
