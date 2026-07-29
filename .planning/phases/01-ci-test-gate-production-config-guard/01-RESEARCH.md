# Phase 1: CI Test Gate & Production Config Guard - Research

**Researched:** 2026-07-08
**Domain:** GitHub Actions CI gating for a Django 5.2 / DRF brownfield app, Django system checks framework, pytest vs Django test runner bootstrapping
**Confidence:** MEDIUM-HIGH. The CI/workflow shape and the Django-runner-vs-pytest findings are HIGH confidence (verified directly against this repo's code and, for the Firebase credential question, verified by executing real Python in this session). The exact list of every test file needing an explicit label is MEDIUM confidence because this sandbox has no Django/Postgres installed, so test discovery itself could not be executed end to end; the plan should treat the first real CI run as the verification step for that list.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Workflow topology**
- D-01: Extend the existing `.github/workflows/deploy.yaml` rather than adding a second workflow file: add a `test` job, give the `deploy` job `needs: test` plus an `if:` guard so deploy only runs on push events to its existing branches. One source of truth, no duplicated job definitions between a ci.yaml and deploy.yaml.
- D-02: Trigger coverage: the `test` job runs on `pull_request` (targets: develop, main, review) and on `push` to the branches deploy.yaml already listens to. Deploy job triggers stay exactly as they are today (push to main/review/feature branch); only the `needs:` edge is new.
- D-03: `bitbucket-pipelines.yml` is legacy and stays untouched.

**CI database provisioning**
- D-04: Postgres as a GitHub Actions service container with a health check, not cloud-sql-proxy to a throwaway Cloud SQL instance. PR runs need no GCP credentials. Postgres major version should match the production Cloud SQL major; planner/researcher confirms the version (default to postgres:15 if it cannot be determined).
- D-05: The test job runs `manage.py migrate` and `manage.py load_reference_data --app=all` against the service container before pytest, per the roadmap success criterion. `api/tests/test_reference_bootstrap.py` passing is the fixture-load proof.

**Test-job environment**
- D-06: Configure the test job with explicit env vars in the workflow YAML (DB_ENGINE=django.db.backends.postgresql, DB_HOST=localhost, DB_PORT/DB_USER/DB_PASSWORD/DB_NAME matching the service container, a dummy SECRET_KEY, DJANGO_DEBUG=True to mirror local test conditions). Do NOT depend on the checked-in `.env.test` contents (they are environment files with secrets; CI must be self-describing).
- D-07: Do not set APP_MODE in the test job unless research shows the suite requires it; if it does, that finding overrides D-06's "no APP_MODE" default and the plan must say so explicitly.

**Security scans (CI-02)**
- D-08: bandit and pip-audit are not in requirements.txt today; pin them in a new `djangoexact/requirements-dev.txt` so CI and local runs use the same versions. Do not add them to the runtime requirements.txt.
- D-09: bandit runs with a HIGH-severity threshold (`--severity-level high`) over `djangoexact` with the README's existing exclusions (venv, node_modules); pip-audit runs against `djangoexact/requirements.txt` and fails on any known CVE, with `--ignore-vuln` (each with an inline justification comment) as the documented escape hatch for unfixable pins.
- D-10: Scans run as steps inside the same gated `test` job (single `needs:` edge protects deploy), not as a separate workflow.

**Production config guard (SEC-03)**
- D-11: Implement as Django system checks in a new `api/checks.py` registered with `@register(Tags.security, deploy=True)`, emitting `Error` (not `Warning`) level messages so `manage.py check --deploy` fails at its default fail level. Do NOT use `--fail-level WARNING`: that would make Django's built-in deploy warnings (HSTS, SSL redirect, etc.) block deploys of this legacy app.
- D-12: The check asserts: when APP_MODE == "production", DEBUG must be False and CORS_ALLOWED_ORIGINS must be non-empty. It reads the same settings values the app runs with; a unit test simulates the bad env combinations and asserts the check raises.
- D-13: CI invokes `manage.py check --deploy` inside the deploy job after sed substitution and before `gcloud app deploy`, with APP_MODE exported to match the target environment, so the check sees real production values. It also runs in the test job as a smoke check with test env values.

### Claude's Discretion
- Exact Postgres image tag, health-check parameters, pip caching, and job step ordering.
- Whether to split lint/scan steps for readability within the single test job.
- How to name the test job and any reusable composite steps.

### Deferred Ideas (OUT OF SCOPE)
- Surfacing bandit/pip-audit findings as PR comments or job summaries (CI-V2-01), future milestone polish.
- Running pytest matrix across multiple Python versions, no requirement demands it.
- Replacing sed templating with a proper secret-injection mechanism, noted in the audit as a security recommendation, out of this milestone's scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| CI-01 | CI runs the full pytest suite against a real Postgres (service container or proxied instance) on every push/PR, and the App Engine deploy job cannot start unless the test job passes (needs: gating in deploy.yaml) | Critical Finding 1 (bare `pytest` cannot bootstrap this suite; use `python manage.py test`), Finding 2 (test-DB/reference-data reach), Finding 8 (discovery-pattern landmines and the explicit-label fix), Architecture Patterns section (concrete job YAML) |
| CI-02 | CI runs bandit (HIGH-severity threshold) and pip-audit in the same gated job, so a high-severity finding or known CVE blocks deploy | Critical Finding 4 (exact invocation, verified flags and versions), Standard Stack, Package Legitimacy Audit |
| SEC-03 | A Django system check fails deploy/startup when APP_MODE is production and either DEBUG is True or CORS_ALLOWED_ORIGINS is empty, wired into CI so a bad production config never reaches App Engine | Critical Finding 5 (checks.py placement, APP_MODE read gotcha), Critical Finding 9 (deploy job never sets APP_MODE today), Code Examples |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Never use em-dashes in any output (this document complies).
- Django root is `djangoexact/`; almost every command in this research runs from there. Repo root is `exact-django-webapp/` and holds `.github/workflows/`, `bitbucket-pipelines.yml`, `.env.*` deployment templates.
- `bitbucket-pipelines.yml` is legacy; do not touch it (matches D-03).
- There is no checked-in `pytest.ini`/`pyproject.toml`; `pytest-django` is not installed. CLAUDE.md itself lists `python manage.py test api.tests` as the "Django test runner fallback", which this research independently confirms is the only command that actually works against a fresh database (see Critical Finding 1).
- `bandit -r djangoexact -x djangoexact/venv,djangoexact/node_modules` and `pip-audit -r djangoexact/requirements.txt` are already documented as the expected local commands (README.md); CI must mirror them, not invent new invocations.
- Conventional commit messages required; feature branches off `develop`.
- Database routing: `DATABASE_ROUTERS` in settings.py point both `ipcc` and `api` apps at the `default` DB. Not relevant to this phase's changes (no new app is being added).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Test suite execution against Postgres | CI/CD Pipeline (GitHub Actions) | Database (service container) | The workflow orchestrates; Postgres just needs to be reachable at `localhost:5432` |
| Deploy gating (test/scan failure blocks App Engine deploy) | CI/CD Pipeline | - | Pure workflow-graph concern (`needs:` + `if:`), no application code involved |
| Security static/dependency scanning (bandit, pip-audit) | CI/CD Pipeline | - | Runs as workflow steps against the checked-out source and requirements.txt; no app code changes |
| Production config validation (DEBUG/CORS) | API/Backend (Django system checks framework) | CI/CD Pipeline (invocation + exit-code enforcement) | The assertion logic is versioned application code (`api/checks.py`); CI's only job is to run `manage.py check --deploy` with the right env and treat a non-zero exit as a gate failure |
| Test fixture/seed data bootstrapping (reference data + user/group seed) | Database / Backend (management commands) | CI/CD Pipeline (sequencing) | `load_reference_data` and the new test-seed step are Django management commands that mutate the DB; CI merely calls them in the right order |

## Summary

This phase wires a CI gate onto a Django app that has never run its test suite in any CI system before. The two decisions with the biggest blast radius are not about GitHub Actions YAML syntax, they are about whether the thing the workflow calls actually works: (1) this repo has no `pytest-django`, no `conftest.py`, and no `pytest.ini`, which means bare `pytest` cannot bootstrap Django's app registry or swap in a test database, so the CI job must invoke `python manage.py test` (Django's own runner), not `pytest`, to get a suite that actually exercises the database; and (2) a large share of the existing test files assume database rows (a `CustomUser` with email `testuser@example.com`, `Group` rows named `Admin` and `Second Reviewer`) that are not part of `load_reference_data`'s manifest and have no reproducible source anywhere in the repository, so a fresh CI Postgres database will fail most of the suite unless a small, new test-seed step is added alongside the reference-data load.

Beyond those two, three more concrete, previously-undocumented facts materially change how the plan should be written: `djangoexact/djangoexact/settings.py` will hard-crash on import if `FIREBASE_SERVICE_ACCOUNT` is not a structurally valid base64-encoded service-account JSON (verified by executing the failure path in this session), so the test job needs a throwaway-but-valid dummy credential, not just any placeholder string; the deploy job in `.github/workflows/deploy.yaml` never sets `APP_MODE` today, so SEC-03's check would silently never fire in production unless the plan adds it; and several legacy files under `api/tests/old/` (never intended as real tests, one of them importing `xlwings`, which is not even in `requirements.txt`) sit on file-name patterns that match either Django's or pytest's default test-discovery glob, so naive "just run all the tests" invocations will crash the whole CI job on collection before a single real test executes.

**Primary recommendation:** Use `python manage.py test` (not `pytest`) with an explicit, enumerated list of test labels (not bare app-level discovery) as the CI test-execution command; add a small test-seed step alongside `load_reference_data`; generate a throwaway Firebase service-account credential inline in the workflow; and add `APP_MODE` to the deploy job's env so the new system check has something real to assert against.

## Critical Findings (Resolved CONTEXT.md Research Questions)

These findings are ordered to match the seven numbered "CRITICAL research questions" in CONTEXT.md and add two more discovered during codebase verification (Finding 8 and Finding 9).

### Finding 1: Bare `pytest` cannot run this suite; use `python manage.py test`

[VERIFIED: codebase read + execution reasoning] Confirmed by direct inspection:
- `pytest-django` is absent from `djangoexact/requirements.txt` (only `pytest==9.0.3` and `factory-boy==3.3.3` are testing-related).
- No `conftest.py`, `pytest.ini`, `setup.cfg`, or `pyproject.toml` exists anywhere in the repo.
- `DJANGO_SETTINGS_MODULE` is only ever set via `os.environ.setdefault(...)` inside entry points that are never invoked by bare pytest: `manage.py`, `djangoexact/wsgi.py`, `djangoexact/asgi.py`, and various one-off `scripts/*.py` files. None of these run when you type `pytest` at a shell prompt.
- Even if `DJANGO_SETTINGS_MODULE` were exported ambiently, `django.setup()` (which populates the app registry so `from api.models import Project` works) is called only by `execute_from_command_line()` (i.e. `manage.py`) or by the WSGI/ASGI entry points. Bare pytest never calls it.
- Django's `TestCase`/`TransactionTestCase` machinery relies on the test runner (`DiscoverRunner.setup_databases()`) to create and swap in a test database before any test runs. Nothing in this repo does that outside of `manage.py test`.

Conclusion: the literal wording "CI runs pytest" in the roadmap/requirements cannot be implemented as written. The test-execution step in the CI workflow must invoke `python manage.py test`, matching the "Django test runner fallback" CLAUDE.md already documents. This is a deviation from the roadmap's literal phrasing that the plan must state explicitly (with this evidence) rather than silently interpreting "pytest" loosely.

### Finding 2: `load_reference_data` before `manage.py test` does not reach the test database by default

[VERIFIED: codebase read] `djangoexact/djangoexact/settings.py`'s non-GAE `DATABASES["default"]` block (the branch used locally and in CI, since `GAE_APPLICATION` is only set when actually running on App Engine) has **no `TEST` sub-key**. Only the GAE branch (used only inside the deployed App Engine instance) has `"TEST": {"NAME": "$DB_NAME"}`.

Without a `TEST.NAME` override, Django's test runner creates and migrates a brand-new database named `test_<DB_NAME>` for every `manage.py test` invocation, independent of whatever `manage.py migrate` + `load_reference_data --app=all` already did to `DB_NAME` itself. That means D-05's ordering (migrate, then load_reference_data, then run tests) does not actually deliver reference data into the database the tests will use, unless one of two things is done:

1. Add `"TEST": {"NAME": os.getenv("DB_NAME", default="$DB_NAME")}` to the non-GAE `DATABASES["default"]` block in `settings.py` (mirroring the pattern the GAE branch already uses), and invoke `manage.py test --keepdb` in CI. With the same name and `--keepdb`, Django detects the database already exists (with migrations and reference data already applied) and reuses it instead of dropping and recreating it. This exact `--keepdb` convention is already referenced as the intended pattern in `docs/superpowers/plans/2026-04-15-minitool-sqlite-to-postgres.md` (a prior internal plan document), so this is consolidation of an existing intention, not a new idea.
2. Alternatively, rely only on tests that load their own fixtures via `call_command("load_reference_data", ...)` inside `setUp`/the test body itself. `api/tests/test_reference_bootstrap.py` already does this (see its `test_load_reference_data_matches_committed_row_counts` method), which is why it works regardless of which database Django's test runner constructs. But most other tests do not do this (see Finding 2b), so option 1 is required for the suite broadly, not just for the bootstrap test.

**Recommended fix (settings.py, one line):** add the `TEST.NAME` override to the non-GAE branch, then have CI run `python manage.py test --keepdb <explicit labels>` (see Finding 8) after `migrate` + `load_reference_data --app=all` have populated `DB_NAME`.

### Finding 2b: Test-only seed data (users, groups) has no reproducible source in the repository

[VERIFIED: codebase read, cross-checked against fixtures_manifest.py] `api/tests/base_test_classes.py`'s `ProjectTest.__init__` does `User.objects.get(email="testuser@example.com")` and `Group.objects.get(name="Admin")`. `api/tests/unit/utils.py`'s `APITestCaseMixin.setUp` does `CustomUser.objects.get(email="testuser@example.com")`, `CustomUser.objects.get(email="test@user.org")`, and `Group.objects.get(name="Second Reviewer")`. All four `.get()` calls assume the rows already exist; none of these test base classes create them via factories or `get_or_create`.

`api/fixtures_manifest.py`'s `MANIFEST` (the single source of truth for `load_reference_data`) contains **no** `auth.Group` or `api.CustomUser` entries; by its own docstring, "Project/Activity/Module/Note/Tag/User and other user-generated data are explicitly excluded." A repo-wide search confirms no migration, `post_migrate` signal, or management command creates these specific rows (`api/signals.py`'s only `post_migrate` receiver creates an `APIHealth` singleton, unrelated). A prior internal audit document (`docs/std-1019-compliance-review.md`) confirms `testuser@example.com` was originally a real developer's personal FAO email address, manually anonymized in test code; the implication is that a real developer's local database (built up over months of manual admin-panel use) has always stood in for this "fixture," and it was never captured reproducibly.

**Consequence:** on a genuinely fresh CI Postgres database (`migrate` + `load_reference_data --app=all` only), every test that inherits from `ProjectTest`/`ActivityTest`/`ModuleTest` (in `api/tests/base_test_classes.py`) or `APITestCaseMixin` (in `api/tests/unit/utils.py`, which underlies essentially all of `api/tests/unit/*`) will fail immediately with `DoesNotExist`, not because of a real regression, but because the CI database is missing test-only seed rows that no developer has ever had to think about before (their local databases already had them). This is exactly the failure mode PITFALLS.md's Pitfall 1 describes in the abstract; this research confirms it concretely for this repo.

**Recommended fix:** add one new, small, versioned artifact, e.g. `api/fixtures/test_seed_data.json` (a Django `loaddata`-format fixture containing the two `CustomUser` rows and the two `Group` rows), loaded via a new CI step: `python manage.py loaddata test_seed_data` (or a tiny new idempotent management command using `get_or_create`), run once after `load_reference_data --app=all` and before the test-execution step. This is test-environment setup, not calculator/application-code hardening, so it fits within this phase's stated boundary ("No application-code hardening beyond api/checks.py belongs here"). Flag this to the planner as a required new task; it is not optional if CI-01 is to mean "the full suite genuinely passes," not "the suite is invoked and something (possibly a red herring) happens."

### Finding 3: Production Postgres major version cannot be determined from the repository

[ASSUMED, per D-04's own fallback instruction] Checked `djangoexact/app.yaml`, `djangoexact/djangoexact/settings.py`, `.github/workflows/deploy.yaml`, `bitbucket-pipelines.yml`, `README.md`, and `docs/setup-guide.md`. None state a Cloud SQL Postgres major version; the docs only confirm the engine is "Cloud SQL for PostgreSQL" and list instance connection names (`fao-exact-dev:europe-west1:fao-exact-dev-postgres`, etc.) without a version. Per D-04's explicit instruction, default to `postgres:15` as the GitHub Actions service container image. This is a candidate for the Assumptions Log; if a teammate can confirm the actual Cloud SQL version from the GCP console, the plan should be updated accordingly, but this does not block Phase 1.

### Finding 4: bandit/pip-audit exact invocation and current versions

[VERIFIED: README.md + executed in sandbox this session] README.md (lines 236-240) already documents the exact local commands:
```bash
pip install bandit pip-audit
bandit -r djangoexact -x djangoexact/venv,djangoexact/node_modules
pip-audit -r djangoexact/requirements.txt
```
D-09 adds a HIGH-severity threshold. Verified via `bandit --help` (installed and executed in this session's sandbox, network-confirmed): the correct flag is `--severity-level {all,low,medium,high}`, so the CI invocation is:
```bash
bandit -r djangoexact -x djangoexact/venv,djangoexact/node_modules --severity-level high
```
`pip-audit --help` (also executed in this session) confirms `-r REQUIREMENT` and `--ignore-vuln ID` (repeatable) are the correct flags for D-09's documented escape hatch:
```bash
pip-audit -r djangoexact/requirements.txt
# with an accepted CVE: pip-audit -r djangoexact/requirements.txt --ignore-vuln GHSA-xxxx  # justification: ...
```
Current versions, confirmed via `pip index versions` executed against the real PyPI index in this session: **bandit 1.9.4**, **pip-audit 2.10.1**. These match the versions already recorded in `.planning/research/STACK.md`.

### Finding 5: `api/checks.py` placement, registration, and the APP_MODE read gotcha

[VERIFIED: codebase read] `djangoexact/api/apps.py` today only does:
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
There is no `api/checks.py` yet. The check module must be imported inside `ready()` (importing a module that calls `@register(...)` at import time is the standard Django idiom; see Code Examples).

**Gotcha (important, code-level):** `APP_MODE` is **not** a Django setting. In `settings.py`, `app_mode = os.getenv("APP_MODE", None)` is a plain local Python variable used only to decide which `.env.{app_mode}` file to load; it is never assigned to a Django setting (there is no `settings.APP_MODE`). The new check function must read it directly via `os.getenv("APP_MODE")`, not `getattr(settings, "APP_MODE", None)` (the latter will always be `None`/raise, since Django's `Settings` object only exposes names that were assigned as module-level uppercase settings). `DEBUG` and `CORS_ALLOWED_ORIGINS`, by contrast, are real Django settings and can be read via `settings.DEBUG` / `settings.CORS_ALLOWED_ORIGINS` normally; both are fully resolved by the time system checks run (checks run after all apps are ready, well after `settings.py` finishes executing).

### Finding 6: Required env vars for `settings.py` to import cleanly, and the Firebase credential trap

[VERIFIED: codebase read + executed in sandbox] Reading `settings.py` line by line for every `os.getenv(...)` call without a safe default:

| Variable | Has safe default? | CI test-job requirement |
|----------|--------------------|--------------------------|
| `SECRET_KEY` | Yes if `DJANGO_DEBUG=True` (falls back to an insecure placeholder); otherwise raises `ImproperlyConfigured` | Set `DJANGO_DEBUG=True` (per D-06) and a dummy `SECRET_KEY` is optional but harmless to set anyway |
| `DB_ENGINE`/`DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME`/`DB_PORT` | Fallback is a literal `"$VAR"` string (not a crash, but a nonsense DB connection) | Must be set explicitly to match the service container (per D-06) |
| `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | Yes (default hosts list; empty list) | No action needed unless testing SEC-03 specifically |
| `EMAIL_HOST`/`EMAIL_PORT`/`SMTP_USER_EMAIL`/`SMTP_USER_PASSWORD` | Falls back to literal `"$VAR"` strings; harmless because nothing in the test suite sends real email | No action needed |
| `STORAGE_BUCKET` | Falls back to literal `"$VAR"` string; harmless unless a test genuinely uploads to GCS (none observed) | No action needed |
| `FIREBASE_API_KEY`/`AUTH_DOMAIN`/`PROJECT_ID`/`STORAGE_BUCKET`/`MESSAGING_SENDER_ID`/`APP_ID`/`MEASUREMENT_ID` | Falls back to literal `"$VAR"` strings; harmless, `FirebaseAuth.__init__` just stores the api_key with no validation or network call | No action needed |
| **`FIREBASE_SERVICE_ACCOUNT`** | **No safe fallback.** Its literal `"$FIREBASE_SERVICE_ACCOUNT"` default is not valid base64; `base64.b64decode(...)` then `json.loads(...)` raises, and the surrounding `try/except` re-raises as `Exception("Firebase config not found: ...")`, crashing the entire `settings.py` import | **Must be set to a structurally valid, base64-encoded service-account JSON string** |

`firebase_admin.initialize_app(firebase_admin.credentials.Certificate(FIREBASE_CONFIG["serviceAccount"]))` runs unconditionally at settings-import time (i.e. on every single `manage.py` invocation: migrate, load_reference_data, test, check --deploy, all of it), so this is not optional to solve.

**Verified fix (executed in this session's sandbox, zero network calls made):** generate a throwaway 2048-bit RSA key and a structurally valid but fake service-account JSON (the real cryptographic content is irrelevant since nothing in this test suite calls `verify_id_token` for real, see Finding 7), then base64-encode it:
```python
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import base64, json

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
pem = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode()

fake_sa = {
    "type": "service_account",
    "project_id": "ci-dummy-project",
    "private_key_id": "dummy",
    "private_key": pem,
    "client_email": "ci-dummy@ci-dummy-project.iam.gserviceaccount.com",
    "client_id": "123456789",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/ci-dummy%40ci-dummy-project.iam.gserviceaccount.com",
}
print(base64.b64encode(json.dumps(fake_sa).encode()).decode())
```
Confirmed in this session: `firebase_admin.initialize_app(firebase_admin.credentials.Certificate(fake_sa))` succeeds with this structure, with `cryptography` and `firebase-admin==6.5.0` installed, no network access used. `firebase-admin` is already pinned in `requirements.txt`; `cryptography` is a transitive dependency of it (already present in the dependency tree, no new top-level pin needed). The recommended approach is a small workflow step (or an inline `python -c` one-liner) that generates this JSON fresh on every CI run and exports it as `FIREBASE_SERVICE_ACCOUNT` (base64-encoded), so no long-lived fake secret needs to be stored in GitHub.

### Finding 7: No test in the current suite requires live external service credentials

[CITED: TESTING.md, cross-checked by reading auth/test-helper code] `api/tests/test_faostat_service.py` mocks the FAOSTAT client via `unittest.mock.patch` (confirmed pattern already documented in `.planning/codebase/TESTING.md`). For Firebase specifically: every test that authenticates a request uses DRF's `force_authenticate(request, user=self.user)` helper (confirmed throughout `api/tests/unit/utils.py` and `api/tests/unit/base_module.py`), which attaches a user directly to the request object and bypasses the `DEFAULT_AUTHENTICATION_CLASSES` pipeline entirely; `accounts.firebase.FirebaseAuthentication.authenticate_credentials` (which calls `firebase_admin_auth.verify_id_token(token)`, a real network call) is never actually exercised by the existing test suite. The only place a real Firebase/GCS/Cloud Run credential would matter is the settings-import-time `initialize_app()` call (Finding 6), not test runtime behavior. No test in the current suite needs real GCP credentials to pass.

### Finding 8: `api/tests/old/` and file-naming mismatches are collection-time landmines for whichever runner is chosen

[VERIFIED: codebase read, empirically reasoned against Django/unittest/pytest discovery semantics] Two distinct problems, both concrete:

**(a) `api/tests/old/` contains legacy, non-test demo/exploration scripts with unconditional module-level Django ORM calls and print statements**, e.g. `api/tests/old/aquaculture_test.py` line 37: `group: api_models.Group = api_models.Group.objects.get(name="Admin")` executed at import time, not inside a function. Worse, `api/tests/old/tests.py` does `import xlwings as xw` at the top of the file; **`xlwings` is not in `requirements.txt`**, so merely importing this file in any environment matching this repo's pinned dependencies raises `ModuleNotFoundError` before even reaching the ORM call. This directory has no `__init__.py` (confirmed via `ls`), but Python 3's namespace-package support means both Django's `unittest.TestLoader.discover()` (used by `manage.py test`, default pattern `test*.py`) and pytest's own discovery would still walk into it.
  - `old/tests.py` matches Django's default `test*.py` glob (it literally starts with "test") and would be **imported and crash `manage.py test`'s entire collection phase** if a bare app-level label like `api` or `api.tests` is passed.
  - `old/aquaculture_test.py` matches pytest's default `*_test.py` glob and would similarly crash a bare `pytest` invocation, on top of Finding 1's more fundamental problem.

**(b) The bulk of `api/tests/unit/`'s most valuable test files do not match either runner's default discovery pattern at all.** Files like `annual_cropland.py`, `livestock.py`, `forest_management.py`, `grassland.py`, `aquaculture.py` (one per module type, containing real `*TestCase` classes per `.planning/codebase/TESTING.md`'s own documented example) start with neither `test_` nor end in `_test`, and do not match Django's `test*.py` pattern either (they do not start with the literal substring "test"). Only two files in that directory (`test_soc_t2_w_unit_simple.py`, `test_sync_firebase_emails.py`) would be found by either runner's default auto-discovery. **A naive `manage.py test` or `pytest` invocation with no explicit labels would silently skip nearly the entire calculator-module unit-test suite while still exiting 0**, which is precisely the "CI gate ships red-herring green" failure mode PITFALLS.md's Pitfall 1 warns about, materializing at the file-naming level rather than the database level.

**Recommended fix:** invoke `manage.py test` (per Finding 1) with an **explicit, enumerated list of test labels** (dotted module/package paths), not bare app-level discovery. Explicit dotted-path labels bypass pattern-based directory walking entirely (Django imports the named module directly via `TestLoader.loadTestsFromModule()`), which simultaneously (i) picks up every real test file regardless of its name, and (ii) never touches `api/tests/old/` or `api/tests/modules/` since they are simply never named. A starter list, assembled from the current directory listing (the plan/executor should re-verify this against the actual first CI run, since this sandbox cannot execute Django's test discovery to confirm it directly):

```
api.tests.test_reference_bootstrap
api.tests.test_faostat_service
api.tests.test_build_luc_fixture
api.tests.test_compute_luc_slice
api.tests.test_compute_module_slice_luc_routing
api.tests.test_luc_compute_iterator
api.tests.test_project_export
api.tests.unit.test_soc_t2_w_unit_simple
api.tests.unit.test_sync_firebase_emails
api.tests.unit.activity
api.tests.unit.annual_cropland
api.tests.unit.aquaculture
api.tests.unit.coastal_wetland
api.tests.unit.energy
api.tests.unit.flooded_rice
api.tests.unit.forest_management
api.tests.unit.grassland
api.tests.unit.irrigation
api.tests.unit.land_use_change
api.tests.unit.land_use_change_examples
api.tests.unit.large_fishery
api.tests.unit.livestock
api.tests.unit.packaging
api.tests.unit.perennial_cropland
api.tests.unit.processing
api.tests.unit.project
api.tests.unit.settlement
api.tests.unit.small_fishery
api.tests.unit.storage
api.tests.unit.transport
api.tests.unit.waterbody
api.tests.reports.test_activity_hectares
api.tests.reports.test_cache
api.tests.reports.test_flooded_rice_seasons
api.tests.reports.test_html_context
accounts
blog
public
minitool
ipcc
admin_scripts.tests
```
(`math_model/tests/repro_perennial_agb_max_zero.py` is intentionally excluded; its own docstring says it is a standalone script run via `python math_model/tests/repro_perennial_agb_max_zero.py`, not part of any test runner's discovery, and it needs no Django at all.)

An alternative, lower-maintenance fix is to physically move `api/tests/old/` out of any discoverable path (e.g. to a top-level `scripts/legacy_test_scripts/` directory). This is a one-time mechanical rename that permanently removes the landmine, but touches more files than the explicit-label approach and was not explicitly authorized by CONTEXT.md's phase boundary. Recommend the explicit-label approach for Phase 1 and note the rename as a lower-priority future cleanup.

### Finding 9: The deploy job never sets `APP_MODE` today, so SEC-03's check would never fire in production without a change

[VERIFIED: codebase read] `.github/workflows/deploy.yaml`'s `deploy` job sed-substitutes many `$VAR` placeholders directly into `app.yaml` and `settings.py` (DB_*, SECRET_KEY, FIREBASE_*, etc.) and sets exactly two env vars in its `env:` block (`DJANGO_DEBUG`, `SECRET_KEY`). **`APP_MODE` is never set, sed-substituted, or otherwise present anywhere in this workflow file.** Since `settings.py`'s `app_mode = os.getenv("APP_MODE", None)` would therefore always evaluate to `None` during the deploy job's own `migrate`/`collectstatic`/(new) `check --deploy` invocation, and D-12's check logic is gated on `app_mode == "production"`, the new check would **never fire**, silently defeating SEC-03's entire purpose, unless the plan adds `APP_MODE` as an explicit env var to the deploy job.

**Recommended fix:** reuse the exact ternary expression the workflow already uses for the `environment:` field (`github.ref_name == 'main' && 'production' || github.ref_name == 'review' && 'review' || 'develop'`) to also set `APP_MODE` in the `Deploy` step's `env:` block:
```yaml
env:
  APP_MODE: ${{ github.ref_name == 'main' && 'production' || github.ref_name == 'review' && 'review' || 'develop' }}
  DJANGO_DEBUG: ${{ vars.DJANGO_DEBUG }}
  SECRET_KEY: ${{ secrets.SECRET_KEY }}
```
This gives `manage.py check --deploy` (invoked per D-13, after sed substitution, before `gcloud app deploy`) a real `APP_MODE` value to key off, matching the target environment.

## Standard Stack

### Core

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|---------------|
| GitHub Actions `postgres` service container | `postgres:15` (major version unconfirmed against Cloud SQL, see Finding 3; use official Docker Hub `postgres` image) | Real Postgres for the test job | Matches production's engine family; avoids SQLite-vs-Postgres behavioral drift (see Common Pitfalls) |
| `python manage.py test` (Django's built-in test runner) | Ships with Django 5.2.14 (already pinned) | Executes the suite against a real, swapped-in test database with `django.setup()` already handled | Bare `pytest` cannot bootstrap this suite without `pytest-django`, which is explicitly excluded this milestone (see Finding 1) |
| bandit | 1.9.4 [VERIFIED: `pip index versions` executed this session] | Static security linter, HIGH-severity gate | Already a documented project convention (README.md); pin the version for CI/local parity |
| pip-audit | 2.10.1 [VERIFIED: `pip index versions` executed this session] | Dependency CVE scanning | Already a documented project convention (README.md); fails closed on known CVEs by default |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `cryptography` | already a transitive dependency of `firebase-admin==6.5.0` | Generates the throwaway RSA key for the dummy Firebase service-account credential | CI test-job setup step only; not a new top-level requirements.txt pin |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `python manage.py test` | Adding `pytest-django` now | Explicitly excluded by CONTEXT.md/PROJECT.md constraints for this milestone; would solve the bootstrapping problem more elegantly but is out of scope |
| Explicit test labels | Bare `manage.py test` (no labels) | Would silently skip most of `api/tests/unit/`'s real coverage (Finding 8b) and crash on `api/tests/old/tests.py` (Finding 8a); rejected |
| Postgres service container | `cloud-sql-proxy` to a throwaway Cloud SQL instance | Requires GCP credentials on every PR run; rejected per D-04 |
| Inline-generated dummy Firebase credential | A stored GitHub secret containing a fixed fake service account | Either works; inline generation avoids maintaining yet another long-lived secret and makes the CI job fully self-describing, consistent with D-06's spirit |

## Package Legitimacy Audit

| Package | Registry | Age (verified via PyPI metadata this session) | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|------|-----------|-------------|---------|-------------|
| bandit | PyPI | Long-established PyCQA project; latest release 1.9.4 published 2026-02-25 | Not returned by the automated check (PyPI download-stats endpoint not queried by the seam) | https://github.com/PyCQA/bandit (readthedocs listed as homepage) | SUS (automated reasons: `unknown-downloads`) | **Approved, override.** Already an established project convention per README.md/CLAUDE.md (authoritative in-repo source, not a WebSearch guess); independently confirmed installable via `pip install bandit==1.9.4` in this session. Planner should still add a `checkpoint:human-verify` before the `requirements-dev.txt` commit per protocol, but this is not a hallucinated package. |
| pip-audit | PyPI | Official PyPA project; latest release 2.10.1 published 2026-06-10 | Not returned by the automated check | https://github.com/pypa/pip-audit | SUS (automated reasons: `too-new`, `unknown-downloads`) | **Approved, override.** Same reasoning: already an established project convention, owned by the official Python Packaging Authority (PyPA) GitHub org, independently confirmed installable in this session. The "too-new" signal reflects the latest point release date, not the package's actual multi-year history; not a hallucination risk. |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** bandit, pip-audit, both overridden above with cited justification (pre-existing project convention plus verified PyPA/PyCQA ownership plus successful local install in this session). The planner should still gate the `requirements-dev.txt` commit behind a lightweight `checkpoint:human-verify` per protocol, primarily so a human confirms the pinned versions before merge, not because either package is actually suspect.

## Architecture Patterns

### System Architecture Diagram

```
PR opened / push to develop, main, review, or feature branch
        |
        v
GitHub Actions workflow trigger (pull_request + push, per D-02)
        |
        v
+--------------------------- test job (new) ---------------------------+
| 1. checkout                                                          |
| 2. start postgres:15 service container (health-checked)              |
| 3. setup-python 3.11, pip cache keyed on requirements*.txt            |
| 4. pip install -r requirements.txt -r requirements-dev.txt            |
| 5. generate throwaway Firebase service-account JSON, export env vars |
| 6. python manage.py migrate                                          |
| 7. python manage.py load_reference_data --app=all                    |
| 8. python manage.py loaddata test_seed_data   (NEW, Finding 2b)      |
| 9. python manage.py test --keepdb <explicit labels>  (Finding 1, 8)  |
| 10. python manage.py check --deploy   (smoke check, test env, D-13)  |
| 11. bandit -r djangoexact -x djangoexact/venv,djangoexact/node_modules \
|     --severity-level high                                            |
| 12. pip-audit -r djangoexact/requirements.txt                        |
+------------------------------------------------------------------------+
        |
        | needs: test   (D-01)
        v
+------------------------- deploy job (existing) ------------------------+
| if: github.event_name == 'push'                                       |
| ... existing sed substitution of app.yaml / settings.py ...           |
| + APP_MODE env var added (Finding 9), matching target environment     |
| python manage.py migrate                                              |
| python manage.py check --deploy   (NEW, real production values, D-13) |
| gcloud app deploy app.yaml ...                                        |
+--------------------------------------------------------------------------+
```

### Recommended Project Structure

```
djangoexact/
├── api/
│   ├── apps.py                  # MODIFIED: import checks module in ready()
│   ├── checks.py                # NEW: @register(Tags.security, deploy=True) check
│   └── fixtures/
│       └── test_seed_data.json  # NEW: CustomUser + Group rows tests assume exist
├── djangoexact/
│   └── settings.py              # MODIFIED: add TEST.NAME to non-GAE DATABASES branch
├── requirements-dev.txt         # NEW: bandit==1.9.4, pip-audit==2.10.1
.github/workflows/
└── deploy.yaml                  # MODIFIED: new `test` job, `needs:` edge, APP_MODE var
```

### Pattern 1: Django deploy-time system check

**What:** A function registered with `@register(Tags.security, deploy=True)` that Django's `check --deploy` command runs and that fails the command (non-zero exit) by returning `Error` instances.
**When to use:** Exactly SEC-03's case: assertions that should only apply when actually deploying, not during ordinary `runserver`/`migrate` invocations.
**Example:**
```python
# Source: Django docs "How to write and use system checks" (confirmed via ARCHITECTURE.md's
# Context7 lookup this milestone: /websites/djangoproject_en_5_2), adapted to this repo's
# APP_MODE-is-not-a-setting gotcha (Finding 5).
import os

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_production_config(app_configs, **kwargs):
    errors = []
    app_mode = os.getenv("APP_MODE")  # NOT settings.APP_MODE; it is not a Django setting
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
```python
# api/apps.py, ready() addition
def ready(self):
    from .signals import create_default_api_status
    post_migrate.connect(create_default_api_status, sender=self)
    from . import checks  # noqa: F401  registers the deploy check
```

### Anti-Patterns to Avoid

- **Registering the check as `Warning` instead of `Error`:** Django's `check` command only exits non-zero for `ERROR` level and above by default; a `Warning`-level check prints but does not fail the command, silently defeating the whole point of gating on it (this is explicitly called out as Anti-Pattern 4 in `.planning/research/ARCHITECTURE.md`, confirmed independently here).
- **Reading `settings.APP_MODE`:** it does not exist as a Django setting; use `os.getenv("APP_MODE")` (Finding 5).
- **Passing bare `manage.py test` or `pytest` with no labels/paths:** silently skips most of `api/tests/unit/`'s real coverage and/or crashes on `api/tests/old/` (Finding 8).
- **Assuming `load_reference_data` populates whatever database `manage.py test` will use:** it does not, unless `TEST.NAME` is overridden and `--keepdb` is passed (Finding 2).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Production-config safety assertions | A shell/grep script that checks `DJANGO_DEBUG`/`CORS_ALLOWED_ORIGINS` string values in `app.yaml` | Django's `django.core.checks` framework (`api/checks.py` + `manage.py check --deploy`) | Composes with Django's own built-in deploy checks; testable in isolation with `override_settings`; already the D-11 decision |
| Dependency vulnerability scanning | A hand-rolled script parsing `pip list --outdated` or CVE feeds | `pip-audit -r requirements.txt` | Already the project's documented convention; maintained by PyPA, understands `requirements.txt` format directly |
| Postgres test-database provisioning | A custom Docker-compose file checked into the repo, spun up manually in a CI step | GitHub Actions' built-in `services:` block | Zero extra infrastructure, health-checked natively, is the standard idiom for this exact need |

**Key insight:** every piece of this phase that looks like it needs custom scripting (config assertions, vulnerability scanning, database provisioning) already has a first-class, already-adopted-by-this-project mechanism; the actual work is wiring, not building.

## Common Pitfalls

### Pitfall 1: Trusting a "green" CI run without checking what it actually executed
**What goes wrong:** The workflow is added, it goes green on the first PR, and everyone assumes the gate is real.
**Why it happens:** Silent skips (wrong test-discovery pattern, missing seed data causing early-exit rather than failure in some misconfigured runner setups) can look identical to "all tests passed."
**How to avoid:** On the first real CI run, manually inspect the job log for: (a) the actual number of tests run (compare against a local count of `test_*` methods across the labels in Finding 8's list), (b) the `load_reference_data` step's duration (should be 30+ seconds per the fixtures guide; a suspiciously fast run means it silently no-op'd), (c) that `test_reference_bootstrap.py`'s three tests specifically appear and pass in the output.
**Warning signs:** Job completes in under 30 seconds total; test count in the log is far lower than expected; no explicit mention of `test_reference_bootstrap` in the output.

### Pitfall 2: SQLite-vs-Postgres drift masked by an accidental fallback
**What goes wrong:** If any `DB_*` env var is missing or misspelled in the workflow YAML, `settings.py`'s `os.getenv(..., default="$DB_ENGINE")` fallback produces a literal, invalid engine string rather than crashing cleanly, which can manifest as a confusing `ImproperlyConfigured` deep in Django's engine-loading code rather than an obvious "env var missing" message.
**How to avoid:** Set all six `DB_*` variables explicitly in the test job's `env:` block (per D-06); do not rely on any default.
**Warning signs:** Errors mentioning `$DB_ENGINE` or another literal `$VAR` string appearing in a traceback.

### Pitfall 3: Firebase settings-import crash masquerading as a Django/DB problem
**What goes wrong:** If `FIREBASE_SERVICE_ACCOUNT` is missing or not valid base64/JSON, every single `manage.py` invocation in the job (migrate, load_reference_data, test, check) fails at import time with `Exception("Firebase config not found: ...")`, which can be misread as a database connectivity problem since it happens before any DB code runs.
**How to avoid:** Generate and export the dummy service-account credential (Finding 6) as the very first env-setup step, before any `manage.py` command runs.
**Warning signs:** Every step fails identically, immediately, regardless of which manage.py subcommand was invoked; the traceback mentions `firebase_admin` or `base64`.

### Pitfall 4: `api/tests/old/` crashing test collection
**What goes wrong:** A "just run everything" invocation (`manage.py test` with no labels, or `pytest` with no args) imports `api/tests/old/tests.py` or `api/tests/old/aquaculture_test.py`, which either raises `ModuleNotFoundError: No module named 'xlwings'` or `Group.DoesNotExist` at collection time, before any real test runs.
**How to avoid:** Use the explicit label list from Finding 8; never pass a bare `api` or `api.tests` label.
**Warning signs:** The very first line of the test job's failure output mentions `xlwings`, or a `DoesNotExist` at a suspiciously early point in the log (before any test name is printed).

## Code Examples

### Recommended `test` job skeleton

```yaml
# Source: this repo's existing deploy.yaml conventions (Postgres major version per D-04's
# fallback; env vars per D-06; verified bandit/pip-audit flags per Finding 4).
jobs:
  test:
    runs-on: ubuntu-22.04
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: exact_ci
          POSTGRES_PASSWORD: exact_ci
          POSTGRES_DB: exact_ci
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DB_ENGINE: django.db.backends.postgresql
      DB_HOST: localhost
      DB_PORT: "5432"
      DB_USER: exact_ci
      DB_PASSWORD: exact_ci
      DB_NAME: exact_ci
      SECRET_KEY: ci-dummy-secret-key-not-for-production
      DJANGO_DEBUG: "True"
      # APP_MODE intentionally unset per D-07 (no test evidence requires it)
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: djangoexact/requirements*.txt
      - name: Install dependencies
        run: |
          cd djangoexact
          pip install -r requirements.txt -r requirements-dev.txt
      - name: Generate throwaway Firebase credential
        run: |
          cd djangoexact
          echo "FIREBASE_SERVICE_ACCOUNT=$(python - <<'PYEOF'
          from cryptography.hazmat.primitives import serialization
          from cryptography.hazmat.primitives.asymmetric import rsa
          import base64, json
          key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
          pem = key.private_bytes(
              encoding=serialization.Encoding.PEM,
              format=serialization.PrivateFormat.TraditionalOpenSSL,
              encryption_algorithm=serialization.NoEncryption(),
          ).decode()
          fake_sa = {
              "type": "service_account", "project_id": "ci-dummy-project",
              "private_key_id": "dummy", "private_key": pem,
              "client_email": "ci-dummy@ci-dummy-project.iam.gserviceaccount.com",
              "client_id": "123456789",
              "auth_uri": "https://accounts.google.com/o/oauth2/auth",
              "token_uri": "https://oauth2.googleapis.com/token",
              "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
              "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/ci-dummy%40ci-dummy-project.iam.gserviceaccount.com",
          }
          print(base64.b64encode(json.dumps(fake_sa).encode()).decode())
          PYEOF
          )" >> "$GITHUB_ENV"
      - name: Migrate and load reference data
        run: |
          cd djangoexact
          python manage.py migrate
          python manage.py load_reference_data --app=all
          python manage.py loaddata test_seed_data
      - name: Run test suite
        run: |
          cd djangoexact
          python manage.py test --keepdb \
            api.tests.test_reference_bootstrap \
            api.tests.unit.annual_cropland \
            admin_scripts.tests \
            ipcc
            # (full label list per Finding 8; abbreviated here for readability)
      - name: Production config smoke check
        run: |
          cd djangoexact
          python manage.py check --deploy
      - name: bandit
        run: |
          cd djangoexact
          bandit -r . -x ./venv,./node_modules --severity-level high
      - name: pip-audit
        run: |
          cd djangoexact
          pip-audit -r requirements.txt

  deploy:
    needs: test
    if: github.event_name == 'push'
    # ... existing deploy job, unchanged except for the added APP_MODE env var (Finding 9)
    # and the new `python manage.py check --deploy` step after sed substitution.
```

## State of the Art

| Old Approach (as-is today) | Current Approach (this phase) | When Changed | Impact |
|--------------------------|-------------------------------|---------------|--------|
| No CI runs the test suite at all (`CONCERNS.md`/PITFALLS.md confirm neither GitHub Actions nor Bitbucket does today) | GitHub Actions `test` job gates `deploy` via `needs:` | This phase | First trustworthy automated gate this project has ever had |
| `bitbucket-pipelines.yml`'s `predeploy` step is a literal `echo 'deploying djangoexact'` (no-op) | Untouched, explicitly out of scope (D-03) | N/A | Legacy pipeline stays cosmetic; GitHub Actions becomes the real gate |
| Deploy job never validates `DEBUG`/`CORS_ALLOWED_ORIGINS` before `gcloud app deploy` | `manage.py check --deploy` runs after sed substitution, before deploy | This phase | A misconfigured production deploy (DEBUG=True, empty CORS) can no longer reach App Engine silently |

**Deprecated/outdated:** none; this phase adds new capability rather than replacing an existing mechanism.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Production Cloud SQL Postgres major version is unconfirmed; defaulting to `postgres:15` per D-04's own fallback instruction | Finding 3, Standard Stack | If production actually runs a different major version, a Postgres-version-specific SQL feature could pass in CI and fail in production (low probability for standard Django ORM usage, but non-zero for raw SQL or certain migration operations) |
| A2 | The explicit test-label list in Finding 8 is complete and matches every real `TestCase` in the repo | Finding 8, Code Examples | If a test file was missed, it silently would not run in CI (same failure mode this finding is trying to prevent); the plan should treat the first real CI run's test count as the verification step, since this sandbox has no Django installed to confirm discovery directly |
| A3 | No test in the current suite makes a real network call to Firebase, GCS, or Cloud Run | Finding 7 | If one does (not observed in this research, but not exhaustively grepped line-by-line for every test file), that test would fail or hang in CI against the dummy credential; should surface immediately and loudly (a clear connection/auth error) rather than silently passing, so this is a low-severity risk even if wrong |

**If this table is empty:** N/A, see rows above.

## Open Questions

1. **Is `xlwings` (imported by `api/tests/old/tests.py`) a leftover from a Windows-only local workflow, or does anything else in the repo actually depend on it?**
   - What we know: it is not in `requirements.txt`; the file that imports it is a legacy demo script, not a real test.
   - What's unclear: whether any other tooling (not covered by this phase's grep) expects it.
   - Recommendation: no action needed for Phase 1 since the file is simply never invoked by the recommended explicit-label approach (Finding 8); flag for a future cleanup phase if `api/tests/old/` is ever formally retired.

2. **Should `api/fixtures/test_seed_data.json` (Finding 2b) be considered "reference data" and folded into `fixtures_manifest.py`, or kept deliberately separate?**
   - What we know: `fixtures_manifest.py`'s own docstring explicitly excludes User/Group data from the reference-data manifest by design (it is meant for lookup/reference tables only, not this kind of test-only seed data).
   - What's unclear: whether the project would want a parallel, explicitly-named "test seed" pipeline (its own small manifest/loader) for future test-only fixtures beyond just these four rows.
   - Recommendation: keep it separate and minimal for Phase 1 (a single fixture file, loaded via one `loaddata` call); do not expand `fixtures_manifest.py`'s scope, since that manifest's docstring makes its boundary a deliberate design decision, not an oversight.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|----------|
| GitHub Actions `postgres` service container | CI-01 (test job DB) | Yes (GitHub-hosted runners support `services:` natively) | `postgres:15` (assumed, Finding 3) | N/A, this is the chosen approach itself |
| bandit | CI-02 | Yes, confirmed installable via `pip install bandit==1.9.4` in this session | 1.9.4 | N/A |
| pip-audit | CI-02 | Yes, confirmed installable via `pip install pip-audit==2.10.1` in this session | 2.10.1 | N/A |
| `cryptography` (for the dummy Firebase key) | Test-job env setup (Finding 6) | Yes, already a transitive dependency of `firebase-admin==6.5.0`, confirmed installable in this session | whatever version `firebase-admin` pulls in | N/A |
| Local Postgres/Docker in this development sandbox | N/A (informational) | No, per this project's own `docs/superpowers/plans/*.md` notes and CONTEXT.md's "specifics" section: "Local sandbox has no Postgres/Docker" | N/A | The GitHub Actions CI job is the only place this suite can actually run end to end; local verification of this phase's changes is limited to `python -m py_compile` and manual YAML review |

**Missing dependencies with no fallback:** none identified; everything this phase needs is either already available or generatable inline in the CI job itself.

**Missing dependencies with fallback:** local Postgres/Docker (fallback: rely entirely on the CI job itself as the verification loop for this phase, consistent with CONTEXT.md's "specifics" section).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|--------------------|
| V1 Architecture, Design and Threat Modeling | Yes | This phase's own subject: a CI gate and a deploy-time config check are both architecture-level controls preventing insecure states from reaching production |
| V5 Input Validation | No | This phase touches no user-facing input paths |
| V7 Error Handling and Logging | Partial | The Firebase settings-import crash (Finding 6) is itself a form of fail-closed error handling already present in the codebase; this phase does not change that behavior, only supplies a valid credential so it does not spuriously trigger in CI |
| V14 Configuration | Yes | SEC-03 is squarely a V14-style "secure configuration by default, verified at deploy time" control; `manage.py check --deploy` plus the new `api/checks.py` check is the standard Django control for this |
| V10 Malicious/CVE-Known Code | Yes | CI-02's `pip-audit` step is the standard control for known-CVE dependencies |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| `DEBUG=True` reaching production, silently opening `CORS_ORIGIN_ALLOW_ALL` (since `settings.py` ties `CORS_ORIGIN_ALLOW_ALL = DEBUG`) | Information Disclosure / Tampering | The new `api/checks.py` deploy check (D-11/D-12), enforced via `manage.py check --deploy` in the deploy job (D-13) |
| Known-CVE dependencies shipping to production undetected | Tampering / Elevation of Privilege | `pip-audit -r requirements.txt` in the gated test job (CI-02) |
| High-severity code patterns (e.g. hardcoded secrets, unsafe deserialization) shipping undetected | Tampering / Information Disclosure | `bandit --severity-level high` in the gated test job (CI-02) |
| A broken test suite reaching production because nothing ever gated on it | Tampering (of correctness, not directly a STRIDE-security category but the phase's core threat model) | `needs: test` edge on the deploy job (CI-01) |

## Sources

### Primary (HIGH confidence, verified this session)
- Direct read of `djangoexact/djangoexact/settings.py`, `djangoexact/api/apps.py`, `djangoexact/api/signals.py`, `djangoexact/api/checks.py` (absence confirmed), `djangoexact/api/fixtures_manifest.py`, `djangoexact/api/tests/base_test_classes.py`, `djangoexact/api/tests/unit/utils.py`, `djangoexact/api/tests/unit/base_module.py`, `djangoexact/api/tests/test_reference_bootstrap.py`, `djangoexact/accounts/firebase.py`, `djangoexact/accounts/firebase_auth.py`, `.github/workflows/deploy.yaml`, `bitbucket-pipelines.yml`, `djangoexact/app.yaml`, `djangoexact/requirements.txt`, `README.md`.
- Executed in this session's sandbox: `pip index versions bandit` and `pip index versions pip-audit` against the real PyPI index (confirmed 1.9.4 and 2.10.1); installed `bandit==1.9.4`, `pip-audit==2.10.1`, `firebase-admin==6.5.0`, `cryptography` into a throwaway venv and ran `bandit --help` / `pip-audit --help` to confirm exact CLI flag names; executed a Python script constructing a dummy RSA key and service-account JSON and confirmed `firebase_admin.initialize_app(credentials.Certificate(...))` succeeds with zero network calls.

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md`, `.planning/research/PITFALLS.md`, `.planning/research/ARCHITECTURE.md`, `.planning/codebase/TESTING.md`, `.planning/codebase/STACK.md` (prior milestone-level research, cross-checked against this phase's own direct codebase verification and found consistent).
- `docs/superpowers/plans/2026-04-15-minitool-sqlite-to-postgres.md`, `docs/std-1019-compliance-review.md` (internal prior planning/audit documents, corroborating the `--keepdb` convention and the `testuser@example.com` provenance).

### Tertiary (LOW confidence)
- Cloud SQL Postgres major version (Finding 3, Assumption A1): not found in any repository source; defaulted per explicit user instruction (D-04).

## Metadata

**Confidence breakdown:**
- Standard stack (bandit/pip-audit versions and flags, Postgres service container pattern): HIGH, versions and flags directly verified by installing and running the tools in this session.
- Test-runner bootstrapping (Findings 1, 2, 2b, 8): HIGH for the mechanism and the concrete evidence (absence of conftest.py/pytest-django, exact `.get()` call sites, exact fixtures_manifest.py contents); MEDIUM for the completeness of the explicit test-label list, since it could not be executed against a real Django install in this sandbox.
- Firebase credential requirement (Finding 6): HIGH, reproduced the actual failure and the actual fix by executing code in this session.
- Deploy job APP_MODE gap (Finding 9): HIGH, directly confirmed by reading the entire `deploy.yaml` file.
- Production Postgres version (Finding 3): LOW, explicitly unconfirmable from the repository; defaulted per user instruction.

**Research date:** 2026-07-08
**Valid until:** 30 days (stable domain: Django system checks and GitHub Actions YAML patterns do not change quickly; re-verify bandit/pip-audit versions if this research is reused after that window, since both tools release frequently)
