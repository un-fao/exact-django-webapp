---
phase: 01-ci-test-gate-production-config-guard
verified: 2026-07-09T08:30:00Z
status: human_needed
score: 10/10 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Open a PR against develop/main/review and confirm the `test` job actually starts, provisions postgres:15, and completes; then confirm the reported test count is not suspiciously low (compare against the 38-label list enumerated in this report) and that `load_reference_data` visibly takes 30+ seconds in the log (not a silent no-op)."
    expected: "The test job runs to completion against a real Postgres service container; `api.tests.test_reference_bootstrap`'s tests specifically appear and pass in the log; runtime confirms fixtures actually loaded."
    why_human: "The local sandbox has no Postgres/Docker (per phase CONTEXT.md), so `--keepdb` DB reuse, `load_reference_data` runtime, and the full suite against Postgres cannot be exercised locally. This is explicitly deferred by the phase's own plans to the first real CI run."
  - test: "On that same PR, confirm the `bandit -r . --severity-level high` and `pip-audit -r requirements.txt` steps execute cleanly (or intentionally fail closed) against the real CI runner's dependency tree."
    expected: "Both scanners run to completion; a HIGH-severity bandit finding or a known-CVE pip-audit hit fails the job and blocks `deploy`."
    why_human: "Cannot install/run bandit and pip-audit against the full real dependency tree in this offline sandbox in a way that proves CI-equivalence; first real CI run is the stated verification step in 01-03-SUMMARY.md."
  - test: "Push to `main` (or trigger the deploy job) and confirm `needs: test` actually blocks `deploy` end to end when `test` fails, and that the deploy job's `check --deploy` step sees real `APP_MODE`/`CORS_ALLOWED_ORIGINS` values sourced from `vars.CORS_ALLOWED_ORIGINS`."
    expected: "A red `test` job prevents `deploy` from starting at all (not just failing partway); a push to main with a correctly configured `CORS_ALLOWED_ORIGINS` GitHub environment variable passes `check --deploy` without the CR-01 false-positive."
    why_human: "GitHub Actions' `needs:`/`if:` gating and the live value of the `vars.CORS_ALLOWED_ORIGINS` repository/environment variable cannot be exercised or inspected from a local git checkout; this is an operational confirmation, not a code-level check."
---

# Phase 1: CI Test Gate & Production Config Guard Verification Report

**Phase Goal:** A failing test, a high-severity security finding, or a misconfigured production deploy is blocked before it reaches App Engine.
**Verified:** 2026-07-09T08:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `manage.py check --deploy` exits non-zero when APP_MODE=production and DEBUG is True (SEC-03) | VERIFIED | Live command run: `APP_MODE=production DJANGO_DEBUG=True CORS_ALLOWED_ORIGINS="" manage.py check --deploy` -> exit code 1, `SystemCheckError` with `(api.E001) DEBUG is True while APP_MODE is production.` |
| 2 | `manage.py check --deploy` exits non-zero when APP_MODE=production and CORS_ALLOWED_ORIGINS is empty (SEC-03) | VERIFIED | Same live run also emitted `(api.E002) CORS_ALLOWED_ORIGINS is empty while APP_MODE is production.` |
| 3 | The check stays silent for a safe production config and for any non-production APP_MODE | VERIFIED | Live run `APP_MODE=production DJANGO_DEBUG=False CORS_ALLOWED_ORIGINS="https://example.org" manage.py check --deploy` -> exit code 0, no api.E00x errors; unit tests `test_production_safe_config_passes` and `test_non_production_is_silent` pass (5/5 suite green) |
| 4 | The non-GAE `DATABASES["default"]` block declares a `TEST.NAME` (gated to CI, per CR-02 fix) so `manage.py test --keepdb` reuses the seeded DB in CI without risking a developer's real DB (CI-01) | VERIFIED | `djangoexact/djangoexact/settings.py:176-181` — `if os.getenv("CI", "").lower() == "true": DATABASES["default"]["TEST"] = {"NAME": os.getenv("DB_NAME", ...)}`; GitHub Actions always sets `CI=true`, so this fires only in CI, matching the CR-02-fixed intent (improves on the original plan text, does not weaken it) |
| 5 | `loaddata test_seed_data` creates the two Group rows and two CustomUser rows the test base classes look up (CI-01) | VERIFIED | `api/fixtures/test_seed_data.json` parses via `json.load`; contains `auth.group` "Admin"/"Second Reviewer" (pk 1000/1001) and `api.customuser` "testuser@example.com"/"test@user.org" (pk 1000/1001, `password: "!unusable-test-account"` per WR-03 fix); cross-checked against consumers `api/tests/base_test_classes.py:20,59` and `api/tests/unit/utils.py:45-47` — exact string matches; absent from `api/fixtures_manifest.py` as required |
| 6 | `requirements-dev.txt` pins bandit and pip-audit at researched versions, kept out of runtime `requirements.txt` (CI-02) | VERIFIED | `djangoexact/requirements-dev.txt` contains exactly `bandit==1.9.4` and `pip-audit==2.10.1`; `grep -iE "bandit\|pip-audit" requirements.txt` returns nothing |
| 7 | A `test` job runs on `pull_request` (develop, main, review) and `push` (main, review, develop, feature/id-responses), spins up a `postgres:15` service container, and runs the suite via `manage.py test --keepdb` with an explicit label list (CI-01) | VERIFIED | `.github/workflows/deploy.yaml` lines 3-15 (triggers), 17-32 (postgres:15 service + health check), 98-149 (`test --keepdb` + 38 explicit dotted-path labels); every one of the 38 labels resolves to a real file/package on disk (verified by direct filesystem check); `yaml.safe_load` parses the file without error |
| 8 | The `deploy` job declares `needs: test` and only runs on `push` (never PR), and never on `develop` pushes (CI-01, WR-04 fix) | VERIFIED | `deploy: needs: test` and `if: github.event_name == 'push' && github.ref_name != 'develop'` at lines 180-185 |
| 9 | The `test` job runs `bandit --severity-level high` and `pip-audit -r requirements.txt` as gated steps (CI-02) | VERIFIED | Lines 167-178: `bandit -r . -x ./venv,./node_modules --severity-level high` and `pip-audit -r requirements.txt`, both steps inside the `test` job (a non-zero exit fails the job, blocking `deploy` via the `needs:` edge) |
| 10 | The `deploy` job exports `APP_MODE` (and, per CR-01 fix, `CORS_ALLOWED_ORIGINS`) via the branch ternary / GH var, and runs `manage.py check --deploy` after sed substitution (now before `migrate`, per WR-02 fix) (SEC-03) | VERIFIED | Lines 215-223 (`Deploy` step env: `APP_MODE`, `CORS_ALLOWED_ORIGINS: ${{ vars.CORS_ALLOWED_ORIGINS }}`); line 278 `python manage.py check --deploy` runs after all sed substitutions (lines 227-265) and before `migrate` (line 279) |

**Score:** 10/10 truths verified (0 present-but-behavior-unverified at the code/config level; live runtime execution against real Postgres/GitHub Actions is the remaining unverifiable-locally layer, routed to human verification below)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `djangoexact/api/checks.py` | `check_production_config` registered `@register(Tags.security, deploy=True)` | VERIFIED | Exists, compiles, reads `os.getenv("APP_MODE")` (not `settings.APP_MODE`), emits `Error` (not `Warning`) `api.E001`/`api.E002` only under production |
| `djangoexact/api/apps.py` | Imports `checks` module inside `ready()` | VERIFIED | `ready()` contains `from . import checks  # noqa: F401  registers the deploy check` after the `post_migrate.connect(...)` line |
| `djangoexact/api/tests/test_production_config_check.py` | DB-free unit test, 4 env combinations | VERIFIED, exceeds spec | `SimpleTestCase` with 5 tests (the 4 planned behaviors plus `test_check_is_registered_for_deploy`, added post-review to close WR-01); all 5 pass live (`Ran 5 tests in 0.005s / OK`) |
| `djangoexact/djangoexact/settings.py` | `TEST.NAME` on non-GAE `DATABASES["default"]` | VERIFIED (improved) | Present, CI-gated (see Truth 4) |
| `djangoexact/api/fixtures/test_seed_data.json` | loaddata fixture, 2 Group + 2 CustomUser rows | VERIFIED (improved) | Present, valid JSON, unusable-password markers post-WR-03 |
| `djangoexact/requirements-dev.txt` | Pins bandit + pip-audit | VERIFIED | Present, exact pins, human-approved (01-02 checkpoint) |
| `.github/workflows/deploy.yaml` | test job + trigger + gating + APP_MODE + check --deploy + scanners | VERIFIED | All present; valid YAML; commit history for all 6 post-review fix commits confirmed in `git log` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `api/apps.py` | `api/checks.py` | `ready()` imports `checks`, `@register` runs at import time | WIRED | Confirmed by grep and by the new `test_check_is_registered_for_deploy` assertion (`check_production_config in registry.deployment_checks`) passing live |
| `api/checks.py` | `APP_MODE` env var | `os.getenv("APP_MODE")` | WIRED | Confirmed by live `check --deploy` runs producing the correct Error ids under `APP_MODE=production` and staying silent otherwise |
| `api/fixtures/test_seed_data.json` | `api/tests/base_test_classes.py`, `api/tests/unit/utils.py` | Fixture rows satisfy `.get(email=...)`/`.get(name=...)` lookups | WIRED | Exact string matches confirmed by direct grep of both consumer files |
| `settings.py` `TEST.NAME` | `manage.py test --keepdb` (deploy.yaml) | Same-name TEST DB, CI-gated | WIRED | `--keepdb` present in the workflow's "Run test suite" step; `CI=true` is a GitHub Actions default env var |
| `deploy.yaml` `deploy` job | `deploy.yaml` `test` job | `needs: test` | WIRED | Present at job level; `if: github.event_name == 'push' && github.ref_name != 'develop'` layered on top |
| `deploy.yaml` `test` job | `requirements-dev.txt`, `test_seed_data.json` | `pip install -r requirements-dev.txt`, `loaddata test_seed_data` | WIRED | Both present in the install/seed steps |
| `deploy.yaml` `deploy` job `APP_MODE`/`CORS_ALLOWED_ORIGINS` | `api/checks.py` | Real production values feed `check_production_config` at deploy time | WIRED | Both env vars present in the `Deploy` step; check step runs after sed substitution, before `migrate` |

### Data-Flow Trace (Level 4)

Not applicable in the conventional sense (this phase produces CI configuration and a deploy-time system check, not a UI component rendering dynamic data). The closest equivalent, "does the check consume real settings values rather than a hardcoded stub," was directly exercised: live `manage.py check --deploy` invocations under three different env combinations produced three different, correct outcomes (E001+E002 fail / clean pass / non-production silent), proving the check reads live `settings.DEBUG` / `settings.CORS_ALLOWED_ORIGINS` / `os.environ["APP_MODE"]` rather than any cached or stubbed value.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All modified Python files compile | `python -m py_compile api/checks.py api/apps.py api/tests/test_production_config_check.py djangoexact/settings.py` | no errors | PASS |
| `deploy.yaml` is valid YAML | `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yaml'))"` | `yaml ok` | PASS |
| `test_seed_data.json` is valid JSON with 4 rows | `python -c "import json; ..."` | `json ok 4` | PASS |
| DB-free unit test suite | `manage.py test api.tests.test_production_config_check` (via repo `.venv`) | `Ran 5 tests in 0.005s — OK` | PASS |
| `check --deploy` fails on unsafe production config | `APP_MODE=production DJANGO_DEBUG=True CORS_ALLOWED_ORIGINS="" manage.py check --deploy` | exit 1, `api.E001` + `api.E002` both raised | PASS |
| `check --deploy` passes on safe production config | `APP_MODE=production DJANGO_DEBUG=False CORS_ALLOWED_ORIGINS="https://example.org" manage.py check --deploy` | exit 0 | PASS |
| Every explicit test label in deploy.yaml resolves to a real file/package | filesystem existence check for all 38 dotted-path labels | all 38 resolved | PASS |
| Scan tools stay out of runtime requirements.txt | `grep -iE "bandit\|pip-audit" requirements.txt` | no match | PASS |
| Fixture excluded from reference-data manifest | `grep test_seed_data api/fixtures_manifest.py` | no match (correctly absent) | PASS |
| bitbucket-pipelines.yml untouched by this phase | `git show --stat` on all 14 phase commits | none touch `bitbucket-pipelines.yml` | PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` files exist in this repository and none are referenced by the phase's PLAN/SUMMARY files. Step 7c: SKIPPED (no probes declared or found).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|--------------|--------|----------|
| CI-01 | 01-02, 01-03 | Full suite runs against real Postgres on every push/PR; deploy job cannot start unless test job passes | SATISFIED | Truths 4, 5, 7, 8 above; runtime proof against real Postgres deferred to first CI run (human verification) |
| CI-02 | 01-02, 01-03 | bandit (HIGH) + pip-audit run in the same gated job | SATISFIED | Truths 6, 9 above; live scanner execution deferred to first CI run (human verification) |
| SEC-03 | 01-01, 01-03 | Deploy-time system check fails on unsafe production config, wired into CI | SATISFIED | Truths 1, 2, 3, 10 above — the only requirement whose core behavior was directly exercised end to end with live command execution in this sandbox (no CI dependency) |

No orphaned requirements: `.planning/REQUIREMENTS.md`'s Phase-1 mapping (line 78-80) lists exactly CI-01, CI-02, SEC-03, matching the union of all three plans' frontmatter `requirements:` fields.

### Anti-Patterns Found

None. Scanned all 7 phase-modified files for `TBD`/`FIXME`/`XXX`, `TODO`/`HACK`/`PLACEHOLDER`, "placeholder"/"coming soon"/"not yet implemented" (case-insensitive), and em-dashes. The only em-dash hits in `deploy.yaml` and `settings.py` (lines 243, 267, 347, and settings.py:342) were confirmed via `git blame` to be pre-existing lines from commits dated April-May 2026, well before this phase (2026-07-08/09) — not introduced by this phase's diff.

### Code Review Fix Verification

The 01-REVIEW.md flagged 2 critical + 4 warning findings; 01-REVIEW-FIX.md claims all 6 fixed. Verified against live files (not the fix report's narrative):

- **CR-01** (false-positive api.E002 on every production deploy): `CORS_ALLOWED_ORIGINS: ${{ vars.CORS_ALLOWED_ORIGINS }}` present in the `Deploy` step env — CONFIRMED FIXED.
- **CR-02** (TEST.NAME data-loss footgun): CI-gated via `if os.getenv("CI", "").lower() == "true"` — CONFIRMED FIXED.
- **WR-01** (no proof the check is registered): `test_check_is_registered_for_deploy` present and passing, plus the negative smoke step "Guard actually fires under APP_MODE=production" present in deploy.yaml — CONFIRMED FIXED.
- **WR-02** (migrate before check --deploy): `check --deploy` now precedes `migrate` in the deploy job — CONFIRMED FIXED.
- **WR-03** (live password hashes, colliding pks): fixture now uses `"!unusable-test-account"` and pks 1000/1001 — CONFIRMED FIXED.
- **WR-04** (develop pushes untested): `develop` added to push branches; deploy job gated `&& github.ref_name != 'develop'` — CONFIRMED FIXED.

All six fixes are live in the codebase, not just claimed in the fix report.

### Human Verification Required

See frontmatter `human_verification` block. Summary: three items, all concerning runtime confirmation on the **first real GitHub Actions execution** of this workflow (real Postgres, real bandit/pip-audit run, real `needs:` gating in practice, and the live value of the `vars.CORS_ALLOWED_ORIGINS` GitHub environment variable). None of these are code-level gaps; every artifact and wiring path is present, correct, and — for SEC-03 specifically — was directly exercised with live command execution in this sandbox. This sandbox has no Postgres/Docker (per phase CONTEXT.md), so the CI-01/CI-02 runtime claims are inherently only provable by observing the first live pipeline run, exactly as anticipated and documented in 01-01/01-02/01-03-SUMMARY.md.

### Gaps Summary

No gaps. All 10 merged must-have truths (roadmap Success Criteria 1-4 plus plan-level detail) are verified against the live codebase, including two critical and four warning defects found in code review, all of which were confirmed fixed in the current file contents (not merely claimed in the fix report). The only reason this phase is not marked `passed` is that a subset of the CI-01/CI-02 claims describe runtime behavior against real Postgres and real GitHub Actions infrastructure that cannot be exercised in this local, Docker-less sandbox — this is an inherent property of a CI-gate phase, explicitly flagged by the phase's own plans as deferred to the first real CI run, and is correctly routed to human verification rather than treated as a failure.

---

_Verified: 2026-07-09T08:30:00Z_
_Verifier: Claude (gsd-verifier)_
