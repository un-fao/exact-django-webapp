---
phase: 01-ci-test-gate-production-config-guard
reviewed: 2026-07-08T14:33:59Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - djangoexact/api/checks.py
  - djangoexact/api/apps.py
  - djangoexact/api/tests/test_production_config_check.py
  - djangoexact/djangoexact/settings.py
  - djangoexact/api/fixtures/test_seed_data.json
  - djangoexact/requirements-dev.txt
  - .github/workflows/deploy.yaml
findings:
  critical: 2
  warning: 4
  info: 4
  total: 10
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-07-08T14:33:59Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the Phase 1 CI test gate and production config guard: `api/checks.py` (api.E001/E002 deploy check), its registration in `ApiConfig.ready()`, the DB-free `SimpleTestCase`, the `TEST.NAME` change in settings.py, the loaddata seed fixture, requirements-dev pins, and the reworked `.github/workflows/deploy.yaml`.

What checks out cleanly:

- The gating semantics are correct. `deploy: needs: test` plus `if: github.event_name == 'push'` gives the intended matrix: PRs to develop/main/review run the test job only; pushes to main/review/feature-id-responses run test then deploy, and the job-level `if` retains the implicit `success()` so a failed test job blocks deploy.
- The postgres service container env (`POSTGRES_USER/PASSWORD/DB = exact_ci`, port 5432 mapped) is byte-for-byte consistent with the job-level `DB_*` env consumed by settings.py.
- The `--keepdb` + `TEST.NAME == DB_NAME` combination works as designed in CI: `migrate` + `load_reference_data` + `loaddata test_seed_data` seed `exact_ci`, and the test runner reuses it. Django's suite reordering runs all `TestCase` subclasses before the `TransactionTestCase` classes (`api.tests.test_reference_bootstrap`, `admin_scripts.tests.*`), and those classes self-provision their data, so the teardown flushes do not starve later tests.
- The test labels are all real modules or packages with `test_*.py` files (`api/tests/unit/*.py` are modules, so explicit labels load their classes despite not matching default discovery); a renamed module fails loudly rather than silently collecting zero tests.
- `test_seed_data.json` matches consumer expectations exactly: `api/tests/base_test_classes.py:20` (`testuser@example.com`), `api/tests/base_test_classes.py:59` (`Group name="Admin"`), and `api/tests/unit/utils.py:45-47` (`testuser@example.com`, `test@user.org`, `Second Reviewer`). `CustomUser`'s nullable `firebase_uid`/`country` and empty `REQUIRED_FIELDS` make the minimal fixture loadable.
- `api/checks.py` uses the documented registration idiom (`@register(Tags.security, deploy=True)` at module level, module imported from `ready()`), reads `settings.DEBUG`/`settings.CORS_ALLOWED_ORIGINS` lazily at check time (so `override_settings` and the two-pass env loading are both handled), reads `APP_MODE` from `os.environ` consistently with settings.py, and has no other import-time side effects. Error IDs follow the `api.E00x` convention.
- The throwaway Firebase credential is generated to `$GITHUB_ENV` without ever being printed to the log, and no new step echoes substituted secrets.
- No em-dashes in any new file or in any line added by this phase (the em-dashes visible in deploy.yaml and settings.py are pre-existing lines outside this diff).

However, two critical defects remain: the production deploy gate as wired will fail every push to main with a false-positive api.E002, and the `TEST.NAME` change creates a data-loss footgun for every developer environment, including the documented cloud-sql-proxy-against-production workflow.

## Critical Issues

### CR-01: `check --deploy` in the deploy job fails every production deploy with a false-positive api.E002

**File:** `.github/workflows/deploy.yaml:199-204, 258` (interacting with `djangoexact/djangoexact/settings.py:59` and `djangoexact/api/checks.py:35`)
**Issue:** On a push to `main`, the Deploy step exports `APP_MODE=production`, `DJANGO_DEBUG`, and `SECRET_KEY`, then runs `python manage.py check --deploy`. At that point `settings.CORS_ALLOWED_ORIGINS` is computed from `os.getenv("CORS_ALLOWED_ORIGINS", "")`, and that variable is set nowhere in the runner:

- It is not in the Deploy step's `env:` block (only `APP_MODE`, `DJANGO_DEBUG`, `SECRET_KEY` are).
- `vars.CORS_ALLOWED_ORIGINS` is only sed-substituted into `app.yaml` (line 220), which is App Engine runtime env, not the CI shell env.
- The `.env` / `.env.production` fallback does not exist in CI: `.gitignore:177` ignores `.env*`, and `git ls-files` confirms no `.env` file is tracked, so `load_dotenv()` in settings.py is a no-op on a fresh checkout.

Result: `CORS_ALLOWED_ORIGINS == []`, `check_production_config` returns api.E002, `manage.py check --deploy` raises `SystemCheckError`, and every production deploy is blocked regardless of how correctly `app.yaml` is configured. The guard, as wired, cannot pass on main. The likely operational outcome is someone deleting the check or the step under deploy pressure, which silently removes the protection the phase was built to add.
**Fix:**
```yaml
    - name: Deploy
      env:
        APP_MODE: ${{ github.ref_name == 'main' && 'production' || github.ref_name == 'review' && 'review' || 'develop' }}
        DJANGO_DEBUG: ${{ vars.DJANGO_DEBUG }}
        SECRET_KEY: ${{ secrets.SECRET_KEY }}
        CORS_ALLOWED_ORIGINS: ${{ vars.CORS_ALLOWED_ORIGINS }}
```
This makes the check validate the same value that gets baked into `app.yaml`, which is exactly what api.E002 is supposed to guard.

### CR-02: `TEST.NAME = DB_NAME` applies to every non-GAE environment and can destroy a developer's real database, including production via cloud-sql-proxy

**File:** `djangoexact/djangoexact/settings.py:168-170`
**Issue:** The new block sets the test database name equal to the live database name for every environment where `GAE_APPLICATION` is unset, i.e. all local development, not just CI:

```python
"TEST": {
    "NAME": os.getenv("DB_NAME", default="$DB_NAME"),
},
```

Consequences outside CI:

- `python manage.py test` (no `--keepdb`): Django tries to create a test database with the dev DB's name, finds it exists, and prompts "Type 'yes' if you would like to try deleting the test database"; answering yes, or running with `--noinput` (common in scripts), DROPS the developer's real database.
- `python manage.py test --keepdb` (the invocation the workflow now teaches people): tests run directly inside the real database, and every `TransactionTestCase` teardown flush (`api/tests/test_reference_bootstrap.py`, `admin_scripts/tests/*`) TRUNCATEs real tables. Data loss without any prompt.
- Project docs (CLAUDE.md) explicitly describe running locally with `cloud-sql-proxy` against the production Cloud SQL instance. With this setting, a routine local test run against that proxy can flush or drop the production database.

The intent (reuse the seeded DB in CI) only requires this in CI, where `CI=true` is always set by GitHub Actions.
**Fix:**
```python
        }
    }
    if os.getenv("CI", "").lower() == "true":
        # CI only: reuse the pre-seeded database via `manage.py test --keepdb`.
        DATABASES["default"]["TEST"] = {"NAME": os.getenv("DB_NAME", default="$DB_NAME")}
```
(Or gate on a dedicated `DJANGO_TEST_DB_NAME` variable set only in deploy.yaml.)

## Warnings

### WR-01: Nothing verifies the check is actually registered; deleting one line disables the guard with a fully green CI

**File:** `djangoexact/api/apps.py:11`, `djangoexact/api/tests/test_production_config_check.py:13`, `.github/workflows/deploy.yaml:150-153`
**Issue:** The unit tests import and call `check_production_config` directly, so they pass whether or not the check is registered with Django. The CI smoke step runs `check --deploy` with `APP_MODE` deliberately unset, so the guard is exercised zero times end-to-end. If the `from . import checks` line in `ApiConfig.ready()` is ever removed (refactor, merge conflict), every test stays green, `check --deploy` stays silent, and the production guard is gone without a trace.
**Fix:** Add either (a) a registration assertion in the unit test:
```python
from django.core.checks.registry import registry

def test_check_is_registered_for_deploy(self):
    self.assertIn(check_production_config, registry.deployment_checks)
```
or (b) a negative smoke step in the test job that proves the wiring fires (DEBUG=True there, so api.E001 must trip):
```yaml
      - name: Guard actually fires under APP_MODE=production
        run: |
          cd djangoexact
          if APP_MODE=production python manage.py check --deploy; then
            echo "api.E001 guard did not fire" >&2; exit 1
          fi
```

### WR-02: Deploy job migrates the production database before running the config guard

**File:** `.github/workflows/deploy.yaml:257-258`
**Issue:** The step order is `migrate` then `check --deploy`. When the guard correctly rejects a bad production config, the production schema has already been migrated while the previous app version is still serving. That is a partial deploy: new schema, old code, deploy blocked. The check is pure configuration validation and needs nothing from `migrate`.
**Fix:** Move `python manage.py check --deploy` before `python manage.py migrate` so a rejected config aborts before any production mutation.

### WR-03: Seed fixture ships live password hashes for active accounts and hardcodes auth.group pks 1 and 2

**File:** `djangoexact/api/fixtures/test_seed_data.json:4-32`
**Issue:** Two problems if this fixture is ever loaded outside CI (nothing prevents it; it resolves via a bare `manage.py loaddata test_seed_data` and sits in `api/fixtures/` beside real reference fixtures):

1. Both users carry valid pbkdf2 hashes and `is_active: true`. The plaintexts are known to whoever generated the hashes, so loading this into a shared/review/production DB creates two live accounts with externally known passwords. The tests never need password auth: `api/tests/unit/utils.py` and `base_test_classes.py` only `objects.get(...)` and `force_authenticate(...)`.
2. `auth.group` pks 1 and 2 are hardcoded. `loaddata` upserts by pk, so loading into a database where pks 1/2 are already occupied by other groups silently renames them (or fails on the unique `name` constraint), corrupting authorization data.

**Fix:** Use Django's unusable-password marker instead of real hashes:
```json
"password": "!unusable-test-account"
```
(any string starting with `!` is unusable). For the groups, prefer high, collision-unlikely pks (e.g. 1000/1001, matching the user pks) or document loudly in the fixture that it is CI-only and must never be loaded into a real database.

### WR-04: Direct pushes and merge commits to `develop` are never tested

**File:** `.github/workflows/deploy.yaml:3-13`
**Issue:** The `push` trigger covers `main`, `review`, `feature/id-responses`; the `pull_request` trigger covers PRs into `develop`/`main`/`review`. But when a PR into `develop` merges (or anyone pushes directly to `develop`, which branch rules may allow), the resulting push event matches no trigger and nothing runs. PR runs test the pre-merge snapshot, so the actual integrated state of `develop`, the project's default branch, is never exercised by the new gate until a PR toward `main` is opened much later.
**Fix:** Add `develop` to the push branch list (the `if: github.event_name == 'push'` on deploy already prevents an unwanted deploy only if the environment expression is acceptable; alternatively guard deploy with `github.ref_name != 'develop'`):
```yaml
on:
  push:
    branches:
      - main
      - review
      - develop
      - feature/id-responses
```

## Info

### IN-01: APP_MODE value `develop` matches no documented mode

**File:** `.github/workflows/deploy.yaml:202`
**Issue:** The new expression yields `develop` for non-main/review pushes, but settings.py's documented modes are `development` / `review` / `production` / `test`. settings.py will print "Running in develop mode" and attempt to load a nonexistent `.env.develop`. Harmless today (no `.env` files exist in CI at all), but it is a latent trap: anyone adding a real `.env.development` will silently not have it loaded in CI, and `FRONTEND_URL` resolution treats any truthy non-review mode as production.
**Fix:** Use `'development'` in the expression, or restrict the env var to the two values the guard cares about.

### IN-02: apps.py missing trailing newline

**File:** `djangoexact/api/apps.py:11`
**Issue:** The file ends without a newline (`\ No newline at end of file` in the diff), which produces noisy diffs on the next edit.
**Fix:** Add a trailing newline.

### IN-03: pip-audit does not cover requirements-dev.txt

**File:** `.github/workflows/deploy.yaml:160-166`, `djangoexact/requirements-dev.txt:1-2`
**Issue:** The audit step scans only `requirements.txt`, so the newly pinned `bandit==1.9.4` and `pip-audit==2.10.1` (installed into the same CI environment) are themselves never audited and will drift stale silently.
**Fix:** `pip-audit -r requirements.txt -r requirements-dev.txt`

### IN-04: `--keepdb` reuse weakens the "empty-DB bootstrap guarantee" of test_reference_bootstrap

**File:** `.github/workflows/deploy.yaml:90-95, 106` (interacting with `djangoexact/api/tests/test_reference_bootstrap.py:1-30`)
**Issue:** `ReferenceDataBootstrapTests` documents itself as "THE executable guarantee that a fresh database plus load_reference_data" round-trips. Under the new CI scheme the test database is the already-seeded `exact_ci`, so the first DB-touching test in that class runs against pre-loaded reference data rather than an empty database (subsequent tests are fine because the scoped teardown flush empties `api`/`ipcc` tables). The load is idempotent and row counts are still asserted, so this is a soft weakening, not a failure, but the class no longer tests exactly what its docstring claims in CI.
**Fix:** No action strictly required; optionally have the class flush `api`/`ipcc` tables in `setUp` (or note the CI seeding interplay in the workflow comment) so the empty-DB claim stays literally true.

---

_Reviewed: 2026-07-08T14:33:59Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
