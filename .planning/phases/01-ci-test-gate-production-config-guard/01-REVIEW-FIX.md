---
phase: 01-ci-test-gate-production-config-guard
fixed_at: 2026-07-09T00:00:00Z
review_path: .planning/phases/01-ci-test-gate-production-config-guard/01-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-07-09
**Source review:** .planning/phases/01-ci-test-gate-production-config-guard/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (2 Critical, 4 Warning)
- Fixed: 6
- Skipped: 0

Info findings were out of scope for this pass. IN-02 (apps.py trailing newline)
was conditionally in scope only if apps.py was already being modified; no fix
touched apps.py, so it was left as-is along with IN-01/IN-03/IN-04.

## Fixed Issues

### CR-01: `check --deploy` in the deploy job fails every production deploy with a false-positive api.E002

**Files modified:** `.github/workflows/deploy.yaml`
**Commit:** 40d7f98b
**Applied fix:** Added `CORS_ALLOWED_ORIGINS: ${{ vars.CORS_ALLOWED_ORIGINS }}` to the Deploy step's `env:` block (APP_MODE with the branch ternary was already present). The deploy check now validates the same value that gets sed-substituted into app.yaml, so api.E002 guards the shipped config instead of always tripping on an empty env.
**Verification:** `yaml.safe_load` on deploy.yaml passes.

### CR-02: `TEST.NAME = DB_NAME` applies to every non-GAE environment and can destroy a developer's real database

**Files modified:** `djangoexact/djangoexact/settings.py`
**Commit:** 93e362e4
**Applied fix:** Removed the unconditional `TEST` block from the non-GAE `DATABASES` dict and replaced it with a CI-gated assignment after the dict, exactly per the review's fix block: `if os.getenv("CI", "").lower() == "true": DATABASES["default"]["TEST"] = {"NAME": os.getenv("DB_NAME", default="$DB_NAME")}`. GitHub Actions always sets CI=true, so the seeded-DB reuse still works in CI; local runs (including cloud-sql-proxy against production) keep Django's default `test_<name>` database.
**Verification:** `py_compile` passes; the DB-free suite `api.tests.test_production_config_check` stays green (5 tests OK) with CI unset.

### WR-01: Nothing verifies the check is actually registered; deleting one line disables the guard with a fully green CI

**Files modified:** `djangoexact/api/tests/test_production_config_check.py`, `.github/workflows/deploy.yaml`
**Commit:** 8d9ba9a0
**Applied fix:** Both halves of the review's suggestion:
1. Added `test_check_is_registered_for_deploy` asserting `check_production_config in registry.deployment_checks` (still `SimpleTestCase`, registry inspection only, no DB).
2. Added a negative smoke step "Guard actually fires under APP_MODE=production" to the test job right after the existing positive smoke check: since the test job runs with `DJANGO_DEBUG=True`, `APP_MODE=production python manage.py check --deploy` must exit non-zero (api.E001) or the step fails the build.
**Verification:** Suite runs 5 tests OK including the new registration assertion; deploy.yaml still parses.

### WR-02: Deploy job migrates the production database before running the config guard

**Files modified:** `.github/workflows/deploy.yaml`
**Commit:** b9979aa6
**Applied fix:** Reordered the deploy job's run block so `python manage.py check --deploy` executes before `python manage.py migrate`, with a comment explaining that a rejected config now aborts before any production schema mutation.
**Verification:** `yaml.safe_load` passes; only the two lines swapped (plus comment), no other step touched.

### WR-03: Seed fixture ships live password hashes for active accounts and hardcodes auth.group pks 1 and 2

**Files modified:** `djangoexact/api/fixtures/test_seed_data.json`
**Commit:** f2794cec
**Applied fix:** Replaced both pbkdf2 hashes with the unusable-password marker `"!unusable-test-account"` (any string starting with `!` is unusable to Django) and moved `auth.group` pks from 1/2 to 1000/1001, matching the user pks. Checked for user-to-group references: the fixture's `api.customuser` entries carry no `groups` field, and all test consumers resolve groups by name (`base_test_classes.py:59` `Group.objects.get(name="Admin")`, `unit/utils.py:47` `Group.objects.get(name="Second Reviewer")`), so no reference updates were needed.
**Verification:** `json.load` passes; script-asserted that all customuser passwords start with `!` and group pks are exactly [1000, 1001].

### WR-04: Direct pushes and merge commits to `develop` are never tested

**Files modified:** `.github/workflows/deploy.yaml`
**Commit:** 6265b593
**Applied fix:** Added `develop` to the `push` trigger branch list and hardened the deploy job gate to `if: github.event_name == 'push' && github.ref_name != 'develop'`, so merges and direct pushes to the default branch run the test gate without ever triggering a deploy.
**Verification:** `yaml.safe_load` passes.

## Verification Summary

Run against the final state (all six commits applied):

- `py_compile` on `settings.py` and `test_production_config_check.py`: OK
- `yaml.safe_load` on `.github/workflows/deploy.yaml`: OK
- `json.load` on `djangoexact/api/fixtures/test_seed_data.json`: OK
- `manage.py test api.tests.test_production_config_check`: Ran 5 tests, OK (DB-free; executed with a throwaway generated Firebase credential and sqlite engine stub since the sandbox has no Postgres and no .env)
- Em-dash scan of every added line across all six commits: none found

Local sandbox has no Postgres/Docker, so the full CI suite and the workflow's
runtime behavior (negative smoke step, deploy ordering) could not be exercised
end-to-end here; they will be proven by the first CI run on this branch.

---

_Fixed: 2026-07-09_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
