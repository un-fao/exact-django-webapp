# Phase 1: CI Test Gate & Production Config Guard - Pattern Map

**Mapped:** 2026-07-08
**Files analyzed:** 6 (2 new, 4 modified)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `.github/workflows/deploy.yaml` (modify: add `test` job + `needs`/`if` edge + `APP_MODE` env) | config (CI workflow) | event-driven (push/pull_request trigger, sequential steps) | itself (existing `deploy` job in the same file) | exact |
| `djangoexact/api/checks.py` (new) | config/validation (Django system check) | request-response (called synchronously by `manage.py check`, returns list of Error objects) | `djangoexact/api/signals.py` (`create_default_api_status`, a `post_migrate` receiver already wired through `apps.py`) | role-match (both are side-effect-free functions registered in `AppConfig.ready()`) |
| `djangoexact/api/apps.py` (modify: import `checks` in `ready()`) | config (AppConfig) | event-driven (Django app registry lifecycle) | itself (existing `ready()` body) | exact |
| `djangoexact/requirements-dev.txt` (new) | config (dependency pins) | batch (installed once per CI run) | `djangoexact/requirements.txt` | exact (same file format, one directory up) |
| `djangoexact/djangoexact/settings.py` (modify: add `TEST.NAME` to non-GAE `DATABASES["default"]`) | config (Django settings) | CRUD (DB connection config consumed by ORM) | itself (existing GAE-branch `DATABASES["default"]["TEST"]` block, lines 148-150) | exact (literally the same pattern, different branch) |
| `djangoexact/api/fixtures/test_seed_data.json` (new: CustomUser + Group test seed rows) | model/fixture (Django `loaddata` fixture) | batch (loaded once via `loaddata` before test run) | `djangoexact/api/fixtures/activitytype.json` (any reference-data fixture) + `djangoexact/api/fixtures_manifest.py` (manifest/spec pattern, for documentation only — do NOT add this file to `MANIFEST`) | role-match (same JSON fixture format; deliberately outside the reference-data manifest per Finding 2b/D-13 boundary) |

## Pattern Assignments

### `.github/workflows/deploy.yaml` (config, event-driven)

**Analog:** itself — the existing single `deploy` job.

**Trigger block today** (lines 1-8):
```yaml
name: Deploy

on:
  push:
    branches:
      - main
      - review
      - feature/id-responses

jobs:  
  deploy:
```
This must become a top-level `on:` with both `push` (unchanged branch list) and `pull_request` (targets develop, main, review per D-02), plus a new `test:` job before `deploy:`.

**Existing `deploy` job env pattern** (lines 42-44) — reuse for the new `test` job's `env:` block and for adding `APP_MODE` to this exact block per Finding 9:
```yaml
    - name: Deploy
      env:
        DJANGO_DEBUG: ${{ vars.DJANGO_DEBUG }}
        SECRET_KEY: ${{ secrets.SECRET_KEY }}
```
Add `APP_MODE: ${{ github.ref_name == 'main' && 'production' || github.ref_name == 'review' && 'review' || 'develop' }}` here — this reuses the exact ternary expression already used for the job-level `environment:` field at line 13, so it is a copy-paste of an existing expression, not a new one.

**Gating edge to add** (new, modeled on the existing `if:` usage pattern at line 110 `if: vars.CLOUD_RUN_COMPUTATION_JOB_NAME != ''`):
```yaml
  deploy:
    needs: test
    if: github.event_name == 'push'
    runs-on: ubuntu-22.04
    environment: ${{ github.ref_name == 'main' && 'production' || github.ref_name == 'review' && 'review' || 'develop' }}
```

**Deploy-job insertion point for `check --deploy`** (after `migrate`, before `collectstatic`, lines 97-98):
```yaml
        python manage.py migrate
        python manage.py collectstatic --noinput
```
Insert `python manage.py check --deploy` between these two lines (after sed substitution has already run at that point in the script, and after `pip install -r requirements.txt` at line 94, so the check has real production env values per D-13).

**Comment convention to preserve** (lines 64, 88-89) — any new step touching secrets must carry the same style of warning comment:
```yaml
        # NOTE: do NOT echo app.yaml — it contains injected DB_PASSWORD and SECRET_KEY after substitution.
```

**New `test` job** — no analog exists in this repo (this is the first test-running CI job ever added here); use the skeleton already fully worked out in `01-RESEARCH.md` under "Code Examples > Recommended `test` job skeleton" (lines 462-564 of that file), which itself derives its `env:`/`steps:` conventions from this same `deploy.yaml`'s existing patterns (setup-python version pin `3.11` at line 33, `cd djangoexact` before any `manage.py`/`pip` command as at line 91-94).

---

### `djangoexact/api/checks.py` (new; config/validation, request-response)

**Analog:** `djangoexact/api/signals.py` + `djangoexact/api/apps.py` (registration-in-`ready()` pattern) — no existing `checks.py` in this codebase; Django's own system-checks framework is the structural pattern, already fully specified in RESEARCH.md.

**Registration pattern to mirror** (from `djangoexact/api/apps.py`, full file, 9 lines):
```python
from django.apps import AppConfig
from django.db.models.signals import post_migrate

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        from .signals import create_default_api_status
        post_migrate.connect(create_default_api_status, sender=self)
```
Add a third line inside `ready()`:
```python
        from . import checks  # noqa: F401  registers the deploy check
```

**Core check pattern** (verified against Django docs in RESEARCH.md; the critical, codebase-specific gotcha is the `APP_MODE` read):
```python
import os

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_production_config(app_configs, **kwargs):
    errors = []
    app_mode = os.getenv("APP_MODE")  # NOT settings.APP_MODE; it is a plain env var,
                                        # never assigned to a Django setting in settings.py
    if app_mode == "production":
        if settings.DEBUG:
            errors.append(
                Error(
                    "DEBUG is True while APP_MODE is production.",
                    hint="Set DJANGO_DEBUG=False for the production environment.",
                    id="api.E001",
                )
            )
        if not settings.CORS_ALLOWED_ORIGINS:
            errors.append(
                Error(
                    "CORS_ALLOWED_ORIGINS is empty while APP_MODE is production.",
                    hint="Set CORS_ALLOWED_ORIGINS to a comma-separated allowed-origins list.",
                    id="api.E002",
                )
            )
    return errors
```

**Error handling pattern:** use `Error` (not `Warning`) so `manage.py check --deploy` fails at its default fail level (D-11); Django's own `django.core.checks.Error` class is the return type, no try/except needed since this function only reads already-resolved settings values.

**Testing pattern:** a unit test should use `override_settings(DEBUG=True)` plus `mock.patch.dict(os.environ, {"APP_MODE": "production"})` (or `monkeypatch.setenv`) and call `check_production_config(None)` directly, asserting the returned list contains an `Error` with `id="api.E001"`/`"api.E002"`. No existing test file in this repo tests a system check; the closest structural analog for "call a function directly and assert on its return value" is `api/tests/test_reference_bootstrap.py`'s `test_load_reference_data_matches_committed_row_counts` (calls `call_command(...)` then asserts on resulting state) — same "arrange env, call the unit, assert on structured result" shape.

---

### `djangoexact/requirements-dev.txt` (new; config, batch)

**Analog:** `djangoexact/requirements.txt` — same flat `pkg==version` format, one pin per line, no comments needed (existing file has none):
```
django-simple-history==3.8.0
django-archive==0.2.0
matplotlib==3.8.2
firebase-admin==6.5.0
...
pytest==9.0.3
...
factory-boy==3.3.3
```
New file, same directory (`djangoexact/`), same format:
```
bandit==1.9.4
pip-audit==2.10.1
```
Per D-08, these must NOT be added to `requirements.txt` itself (that file stays runtime-only); the CI `pip install` step installs both files together (`pip install -r requirements.txt -r requirements-dev.txt`).

---

### `djangoexact/djangoexact/settings.py` (modify; config, CRUD)

**Analog:** the file's own GAE branch, lines 138-151 (already implements the exact `TEST.NAME` pattern needed for the non-GAE branch):
```python
if os.getenv("GAE_APPLICATION", None):
    # Running on production App Engine, so connect to Google Cloud SQL using
    # the unix socket at /cloudsql/<your-cloudsql-connection string>
    DATABASES = {
        "default": {
            "ENGINE": "$DB_ENGINE",
            "HOST": "/cloudsql/$DB_INSTANCE_CONNECTION",
            "USER": "$DB_USERNAME",
            "PASSWORD": "$DB_PASSWORD",
            "NAME": "$DB_NAME",
            "TEST": {
                "NAME": "$DB_NAME",
            },
```

**Target branch to modify** (non-GAE, lines 160-175 — the branch actually used by CI and local dev):
```python
else:
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", default="$DB_ENGINE"),
            "HOST": os.getenv("DB_HOST", default="$DB_HOST"),
            "USER": os.getenv("DB_USER", default="$DB_USERNAME"),
            "PASSWORD": os.getenv("DB_PASSWORD", default="$DB_PASSWORD"),
            "NAME": os.getenv("DB_NAME", default="$DB_NAME"),
            "PORT": os.getenv("DB_PORT", default="$DB_PORT"),
            "OPTIONS": {
                "connect_timeout": 30,  # Optional: set timeout
                "application_name": "djangoexact",  # Help identify connections
            },
            "CONN_MAX_AGE": 0,  # Close connections immediately after use
            "ATOMIC_REQUESTS": False,  # Disable automatic transactions
        },
    }
```
Add one key, mirroring the GAE branch's convention but reading from the same env var already used for `"NAME"` above:
```python
            "TEST": {
                "NAME": os.getenv("DB_NAME", default="$DB_NAME"),
            },
```
This enables `manage.py test --keepdb` in CI to reuse the already-migrated-and-seeded `DB_NAME` database (Finding 2) instead of creating a fresh, empty `test_<DB_NAME>` database on every run.

---

### `djangoexact/api/fixtures/test_seed_data.json` (new; model/fixture, batch)

**Analog:** `djangoexact/api/fixtures/activitytype.json` for JSON-array `loaddata` format; `djangoexact/api/fixtures_manifest.py` for the *documentation convention only* (this new file must NOT be added to `MANIFEST` — its docstring at lines 1-8 explicitly excludes User/Group rows from the reference-data pipeline; keep this fixture separate and loaded via a standalone `python manage.py loaddata test_seed_data` CI step, per Finding 2b/D-13's stated boundary).

**Fixture JSON shape** (standard Django `loaddata` format, `app_label.model_name` per Django docs, model fields verified against `djangoexact/api/models.py` lines 71-78 for `CustomUser`):
```json
[
  {
    "model": "auth.group",
    "pk": 1,
    "fields": {"name": "Admin"}
  },
  {
    "model": "auth.group",
    "pk": 2,
    "fields": {"name": "Second Reviewer"}
  },
  {
    "model": "api.customuser",
    "pk": 1000,
    "fields": {
      "email": "testuser@example.com",
      "password": "pbkdf2_sha256$...",
      "is_active": true
    }
  },
  {
    "model": "api.customuser",
    "pk": 1001,
    "fields": {
      "email": "test@user.org",
      "password": "pbkdf2_sha256$...",
      "is_active": true
    }
  }
]
```
Callers assuming these rows exist (do not modify these test files in this phase, they are consumers, not part of the file list; listed for completeness so the fixture's shape can be verified against them):
- `djangoexact/api/tests/base_test_classes.py` — `ProjectTest.__init__`: `User.objects.get(email="testuser@example.com")`, `Group.objects.get(name="Admin")`
- `djangoexact/api/tests/unit/utils.py` — `APITestCaseMixin.setUp`: `CustomUser.objects.get(email="testuser@example.com")`, `CustomUser.objects.get(email="test@user.org")`, `Group.objects.get(name="Second Reviewer")`

The planner/executor should pick real bcrypt/pbkdf2 password hashes (any value works since no test logs in via real password auth per Finding 7 — `force_authenticate` bypasses credential checks) or use `django.contrib.auth.hashers.make_password("x")` output.

---

## Shared Patterns

### Django system check registration (`ready()` idiom)
**Source:** `djangoexact/api/apps.py` (existing `post_migrate.connect(...)` pattern)
**Apply to:** `djangoexact/api/checks.py` registration
```python
def ready(self):
    from .signals import create_default_api_status
    post_migrate.connect(create_default_api_status, sender=self)
    from . import checks  # noqa: F401  registers the deploy check
```

### CI secret-handling comment convention
**Source:** `.github/workflows/deploy.yaml` lines 64, 88-89
**Apply to:** any new workflow step touching `secrets.*` or generated credentials (e.g. the throwaway Firebase service-account step)
```yaml
        # NOTE: do NOT echo app.yaml — it contains injected DB_PASSWORD and SECRET_KEY after substitution.
```

### Environment-to-branch ternary
**Source:** `.github/workflows/deploy.yaml` line 13
**Apply to:** the new `APP_MODE` env var in the `deploy` job (Finding 9)
```yaml
${{ github.ref_name == 'main' && 'production' || github.ref_name == 'review' && 'review' || 'develop' }}
```

### `cd djangoexact` before manage.py/pip
**Source:** `.github/workflows/deploy.yaml` line 91 (`cd djangoexact` before `pip install`/`manage.py migrate`)
**Apply to:** every step in the new `test` job that runs `manage.py` or `pip`/`bandit`/`pip-audit` (all of these are invoked relative to the Django root per CLAUDE.md's repo-layout note)

### Requirements pin format
**Source:** `djangoexact/requirements.txt`
**Apply to:** `djangoexact/requirements-dev.txt` — flat `pkg==version`, no header, no comments

## No Analog Found

None. Every file in scope has at least a role-match analog within this repo; the `test` job itself has no direct precedent (this is the first CI test job ever added to the project), but its shape is fully derived from combining this same `deploy.yaml`'s existing conventions (env blocks, `cd djangoexact`, python version pin) with Django/GitHub Actions standard idioms already fully specified in `01-RESEARCH.md`'s Code Examples section — no invention needed at planning time.

## Metadata

**Analog search scope:** `.github/workflows/`, `djangoexact/api/`, `djangoexact/djangoexact/settings.py`, `djangoexact/requirements.txt`, `djangoexact/api/fixtures/`, `djangoexact/api/fixtures_manifest.py`, `djangoexact/api/tests/`
**Files scanned:** 9 (deploy.yaml, apps.py, signals.py, settings.py, requirements.txt, fixtures_manifest.py, test_reference_bootstrap.py, models.py, an example fixtures/*.json)
**Pattern extraction date:** 2026-07-08
