# Phase 1: CI Test Gate & Production Config Guard - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a CI gate in GitHub Actions: a test job that runs the full pytest suite against a real Postgres service container plus bandit and pip-audit scans, wired so the existing App Engine deploy job cannot start unless the gate passes; and a Django deploy-time system check that fails when production config is unsafe (DEBUG=True or empty CORS_ALLOWED_ORIGINS). Requirements: CI-01, CI-02, SEC-03. No application-code hardening beyond api/checks.py belongs here (calculator work is Phase 2+).

</domain>

<decisions>
## Implementation Decisions

### Workflow topology
- **D-01:** Extend the existing `.github/workflows/deploy.yaml` rather than adding a second workflow file: add a `test` job, give the `deploy` job `needs: test` plus an `if:` guard so deploy only runs on push events to its existing branches. One source of truth, no duplicated job definitions between a ci.yaml and deploy.yaml.
- **D-02:** Trigger coverage: the `test` job runs on `pull_request` (targets: develop, main, review) and on `push` to the branches deploy.yaml already listens to. Deploy job triggers stay exactly as they are today (push to main/review/feature branch); only the `needs:` edge is new.
- **D-03:** `bitbucket-pipelines.yml` is legacy and stays untouched.

### CI database provisioning
- **D-04:** Postgres as a GitHub Actions service container with a health check, not cloud-sql-proxy to a throwaway Cloud SQL instance. PR runs need no GCP credentials. Postgres major version should match the production Cloud SQL major; planner/researcher confirms the version (default to postgres:15 if it cannot be determined).
- **D-05:** The test job runs `manage.py migrate` and `manage.py load_reference_data --app=all` against the service container before pytest, per the roadmap success criterion. `api/tests/test_reference_bootstrap.py` passing is the fixture-load proof.

### Test-job environment
- **D-06:** Configure the test job with explicit env vars in the workflow YAML (DB_ENGINE=django.db.backends.postgresql, DB_HOST=localhost, DB_PORT/DB_USER/DB_PASSWORD/DB_NAME matching the service container, a dummy SECRET_KEY, DJANGO_DEBUG=True to mirror local test conditions). Do NOT depend on the checked-in `.env.test` contents (they are environment files with secrets; CI must be self-describing).
- **D-07:** Do not set APP_MODE in the test job unless research shows the suite requires it; if it does, that finding overrides D-06's "no APP_MODE" default and the plan must say so explicitly.

### Security scans (CI-02)
- **D-08:** bandit and pip-audit are not in requirements.txt today; pin them in a new `djangoexact/requirements-dev.txt` so CI and local runs use the same versions. Do not add them to the runtime requirements.txt.
- **D-09:** bandit runs with a HIGH-severity threshold (`--severity-level high`) over `djangoexact` with the README's existing exclusions (venv, node_modules); pip-audit runs against `djangoexact/requirements.txt` and fails on any known CVE, with `--ignore-vuln` (each with an inline justification comment) as the documented escape hatch for unfixable pins.
- **D-10:** Scans run as steps inside the same gated `test` job (single `needs:` edge protects deploy), not as a separate workflow.

### Production config guard (SEC-03)
- **D-11:** Implement as Django system checks in a new `api/checks.py` registered with `@register(Tags.security, deploy=True)`, emitting `Error` (not `Warning`) level messages so `manage.py check --deploy` fails at its default fail level. Do NOT use `--fail-level WARNING`: that would make Django's built-in deploy warnings (HSTS, SSL redirect, etc.) block deploys of this legacy app.
- **D-12:** The check asserts: when APP_MODE == "production", DEBUG must be False and CORS_ALLOWED_ORIGINS must be non-empty. It reads the same settings values the app runs with; a unit test simulates the bad env combinations and asserts the check raises.
- **D-13:** CI invokes `manage.py check --deploy` inside the deploy job after sed substitution and before `gcloud app deploy`, with APP_MODE exported to match the target environment, so the check sees real production values. It also runs in the test job as a smoke check with test env values.

### Claude's Discretion
- Exact Postgres image tag, health-check parameters, pip caching, and job step ordering.
- Whether to split lint/scan steps for readability within the single test job.
- How to name the test job and any reusable composite steps.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning artifacts
- `.planning/REQUIREMENTS.md` — CI-01, CI-02, SEC-03 definitions and acceptance shape
- `.planning/ROADMAP.md` — Phase 1 success criteria (the four observable behaviors)
- `.planning/research/STACK.md` — tool choices with versions and rationale (pytest-django recommendation is OVERRIDDEN by project constraint: no pytest-django this milestone, see FEATURES.md anti-features)
- `.planning/research/PITFALLS.md` — CI-theater pitfalls: SQLite-vs-Postgres drift, fixture bypass, missing env vars
- `.planning/research/ARCHITECTURE.md` — placement of api/checks.py and CI build order

### Codebase map
- `.planning/codebase/TESTING.md` — existing test layout, no pytest-django, no conftest.py documented
- `.planning/codebase/STACK.md` — pinned versions (pytest 9.0.3, Django 5.2.14)

### Live files this phase edits or must understand
- `.github/workflows/deploy.yaml` — the only active CI; single deploy job, push-only triggers (main, review, feature/id-responses), sed-templating of app.yaml and settings.py, cloud-sql-proxy usage, secret-echo warnings that MUST be preserved
- `djangoexact/djangoexact/settings.py` — two-pass env loading (load_dotenv then .env.{APP_MODE}), DEBUG/SECRET_KEY/CORS logic at lines 40-59, DB config via DB_* env vars in the non-App-Engine branch (lines 160-175)
- `djangoexact/requirements.txt` — pytest 9.0.3 and factory-boy pinned; bandit/pip-audit absent
- `djangoexact/api/tests/test_reference_bootstrap.py` — the fixture round-trip test the success criteria name
- `bitbucket-pipelines.yml` — legacy, echo-only test step, DO NOT MODIFY

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `deploy.yaml` environment mapping expression (ref_name -> production/review/develop) can be reused by the test job for env-specific values if needed.
- README/CLAUDE.md already document the exact bandit and pip-audit invocations expected locally; CI should mirror them.
- `load_reference_data --app=all` management command is the canonical fixture bootstrap (30+ seconds; the roadmap treats runtime > 30s as proof fixtures loaded).

### Established Patterns
- Secrets flow through GitHub vars/secrets into sed substitution; comments in deploy.yaml explicitly forbid echoing substituted files. Any new steps must respect this.
- Conventional commits; feature branches off develop; PRs target develop (which currently triggers NO CI at all: this phase closes that gap via pull_request triggers).
- Tests are Django TestCase/APITestCase run under plain pytest (no pytest-django). CRITICAL research question: how the suite bootstraps Django settings under bare pytest (DJANGO_SETTINGS_MODULE/django.setup() mechanism) and how reference data reaches the test database that Django's runner creates (test_<name>), since load_reference_data targets the main DB. The plan must resolve this before declaring the gate trustworthy.

### Integration Points
- New `test` job in `.github/workflows/deploy.yaml`; `deploy` job gains `needs: test` and an event guard.
- New `djangoexact/api/checks.py` (Django system checks); registered via api app; invoked by `manage.py check --deploy` in both CI jobs.
- New `djangoexact/requirements-dev.txt` for bandit/pip-audit pins.

</code_context>

<specifics>
## Specific Ideas

- The gate must be real, not theater: the success criterion explicitly demands the reference-bootstrap test passes against the service container and that job runtime exceeding 30 seconds is treated as evidence fixtures actually loaded.
- Local sandbox has no Postgres/Docker; this CI job is the ONLY place the full suite runs. py_compile is the only local gate, which raises the stakes on getting the CI job right the first time.
- The environment files (.env*) are private; CI must not depend on reading them and agents must not cat them.

</specifics>

<deferred>
## Deferred Ideas

- Surfacing bandit/pip-audit findings as PR comments or job summaries (CI-V2-01) - future milestone polish.
- Running pytest matrix across multiple Python versions - no requirement demands it.
- Replacing sed templating with a proper secret-injection mechanism - noted in the audit as a security recommendation, out of this milestone's scope.

</deferred>

---

*Phase: 1-CI Test Gate & Production Config Guard*
*Context gathered: 2026-07-08*
