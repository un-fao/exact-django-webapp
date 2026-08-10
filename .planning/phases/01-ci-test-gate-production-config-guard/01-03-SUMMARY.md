---
phase: 01-ci-test-gate-production-config-guard
plan: 03
subsystem: infra
tags: [github-actions, ci, postgres, django, bandit, pip-audit, deploy-guard]

requires:
  - phase: 01-ci-test-gate-production-config-guard (plan 01)
    provides: "djangoexact/api/checks.py check_production_config, ApiConfig.ready() registration"
  - phase: 01-ci-test-gate-production-config-guard (plan 02)
    provides: "TEST.NAME on the non-GAE DATABASES branch, api/fixtures/test_seed_data.json, requirements-dev.txt"
provides:
  - "Gated test job in .github/workflows/deploy.yaml running python manage.py test --keepdb against a postgres:15 service container, on pull_request and push"
  - "needs: test plus if: github.event_name == 'push' on the deploy job, so a failing test/scan blocks the App Engine deploy and PRs never deploy"
  - "APP_MODE env var on the Deploy step and a manage.py check --deploy step after sed substitution, so SEC-03's check runs against real production values"
affects: []

tech-stack:
  added: []
  patterns:
    - "GitHub Actions postgres service container with pg_isready health check, mirroring the plan's D-04 fallback of postgres:15"
    - "Inline-generated throwaway Firebase service-account credential (RSA key + fake JSON, base64-encoded to $GITHUB_ENV) so settings.py's unconditional firebase_admin.initialize_app() import-time call never crashes CI"
    - "Explicit dotted-path test label list for manage.py test, never a bare app/api.tests label, to avoid api/tests/old/ collection landmines and silent discovery-pattern skips"

key-files:
  created: []
  modified:
    - .github/workflows/deploy.yaml

key-decisions:
  - "APP_MODE intentionally left unset in the test job (D-07): the suite does not require it, and setting it to production would make the smoke check --deploy step fail on test-env DEBUG/CORS values"
  - "check --deploy runs twice: once in the test job (smoke check on test-env values) and once in the deploy job (real production values, after sed substitution), matching D-13 exactly"
  - "Task 1 (test job + pull_request trigger) and Task 2 (deploy job gating + APP_MODE + check --deploy) committed as two separate atomic commits even though both touch the same file, per the plan's explicit task boundary ('Do not modify the deploy job in this task, that is Task 2')"

patterns-established:
  - "Any new CI step that touches a secret or generated credential must carry a do-NOT-echo NOTE comment, matching the existing lines 224/248 convention"

requirements-completed: [CI-01, CI-02, SEC-03]

coverage:
  - id: D1
    description: "A new test job runs on pull_request (develop, main, review) and push, spins up postgres:15, and runs the suite via manage.py test --keepdb with explicit labels including api.tests.test_production_config_check"
    requirement: "CI-01"
    verification:
      - kind: other
        ref: "grep assertions: pull_request, postgres:15, requirements-dev.txt, loaddata test_seed_data, manage.py test --keepdb, api.tests.test_production_config_check all present in .github/workflows/deploy.yaml"
        status: pass
      - kind: other
        ref: "python3 -c \"import yaml; yaml.safe_load(open('.github/workflows/deploy.yaml'))\" - parses without error"
        status: pass
      - kind: other
        ref: "Live end-to-end proof (suite passes on real Postgres, test count matches expectation) runs on the first real GitHub Actions execution; local sandbox has no Postgres/Docker"
        status: deferred
    human_judgment: true
    rationale: "The explicit test-label list (Finding 8/Assumption A2) could not be executed against a real Django+Postgres install in this sandbox; the first real CI run is the stated verification step and requires a human to inspect the job log per Pitfall 1 (test count, load_reference_data duration, test_reference_bootstrap appearing in output)."
  - id: D2
    description: "The deploy job declares needs: test and if: github.event_name == 'push', so a failing test job blocks deploy and PRs never trigger it"
    requirement: "CI-01"
    verification:
      - kind: other
        ref: "grep 'needs: test' and grep \"github.event_name == 'push'\" both present in .github/workflows/deploy.yaml deploy job"
        status: pass
    human_judgment: false
  - id: D3
    description: "The test job runs bandit --severity-level high and pip-audit -r requirements.txt as gated steps"
    requirement: "CI-02"
    verification:
      - kind: other
        ref: "grep -- '--severity-level high' and grep 'pip-audit -r requirements.txt' both present in the test job"
        status: pass
      - kind: other
        ref: "Live execution of both scanners against real CI runners deferred to the first GitHub Actions run"
        status: deferred
    human_judgment: true
    rationale: "bandit/pip-audit cannot execute against this repo's actual dependency tree in the local sandbox in a way that proves the CI invocation is equivalent; first real CI run is the verification step."
  - id: D4
    description: "The deploy job exports APP_MODE via the branch ternary and runs manage.py check --deploy after sed substitution, so a bad production config never reaches App Engine"
    requirement: "SEC-03"
    verification:
      - kind: other
        ref: "grep 'APP_MODE:' and grep 'manage.py check --deploy' both present in the deploy job's Deploy step, positioned between migrate and collectstatic"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-08
status: complete
---

# Phase 1 Plan 3: CI Test Gate and Production Config Guard Wiring Summary

**Extended `.github/workflows/deploy.yaml` with a gated `test` job (postgres:15 service container, explicit `manage.py test --keepdb` label list, bandit/pip-audit) whose `needs:` edge blocks the `deploy` job on push, and added `APP_MODE` plus `manage.py check --deploy` to the deploy job so a bad production config or a red test/scan run can no longer reach App Engine.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-08T16:05:00Z (approx, continuation session)
- **Completed:** 2026-07-08T16:17:38Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Added a `pull_request` trigger (develop, main, review) alongside the existing `push` trigger
- Added a new `test` job: `postgres:15` service container with health check, explicit `DB_*`/`SECRET_KEY`/`DJANGO_DEBUG` env vars (no `APP_MODE`, per D-07), `pip install -r requirements.txt -r requirements-dev.txt`, an inline-generated throwaway Firebase service-account credential written to `$GITHUB_ENV`, `migrate` + `load_reference_data --app=all` + `loaddata test_seed_data`, `manage.py test --keepdb` with an explicit 38-label dotted-path list (including the new `api.tests.test_production_config_check`), a `check --deploy` smoke check, `bandit -r . -x ./venv,./node_modules --severity-level high`, and `pip-audit -r requirements.txt`
- Gated the existing `deploy` job with `needs: test` and `if: github.event_name == 'push'`, so the App Engine deploy only starts after a green test job and only on push events (never on pull_request)
- Added `APP_MODE` (reusing the exact branch ternary already used for `environment:`) to the `Deploy` step's `env:` block, and inserted `python manage.py check --deploy` between `migrate` and `collectstatic --noinput`, so SEC-03's check runs on real production values before `gcloud app deploy`
- Preserved both existing do-NOT-echo NOTE comments unchanged; `bitbucket-pipelines.yml` untouched (D-03)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add the gated `test` job and pull_request trigger to deploy.yaml** - `e2bb141f` (ci)
2. **Task 2: Wire the deploy job to the gate and the production config check** - `b0b12f26` (ci)

**Plan metadata:** pending (docs: complete plan, this commit)

## Files Created/Modified
- `.github/workflows/deploy.yaml` - Added the `pull_request` trigger, the full `test` job (Postgres service container, dependency install, Firebase credential generation, migrate/load/seed, `manage.py test --keepdb` with explicit labels, `check --deploy` smoke check, bandit, pip-audit), and gated the `deploy` job with `needs: test` / `if: github.event_name == 'push'` plus a real `APP_MODE` env var and a `check --deploy` step

## Decisions Made
- `APP_MODE` stays unset in the test job (D-07): the suite doesn't need it, and setting it to `production` would make the smoke `check --deploy` step fail against test-env `DEBUG=True`/empty `CORS_ALLOWED_ORIGINS` values that are fine outside production.
- `check --deploy` runs in both jobs for different reasons: the test job's run is a smoke check against test-env values (should always pass, proves the check itself doesn't crash); the deploy job's run is the real gate against production values (D-13).
- Split the single-file diff into two atomic commits along the plan's task boundary: Task 1 committed the `test` job and trigger with the `deploy` job completely untouched (verified via `grep -n "needs: test\|if: github.event_name"` returning nothing after Task 1's commit); Task 2 then added `needs`/`if`/`APP_MODE`/`check --deploy` on top. This required editing the file once, then temporarily reverting the `needs`/`if` lines before the first commit and reapplying them for the second, since both tasks touch the same file and the plan requires per-task atomicity.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched the RESEARCH.md skeleton and PATTERNS.md analogs; the explicit test-label list was cross-checked against the actual `djangoexact/api/tests/`, `api/tests/unit/`, `api/tests/reports/`, and `admin_scripts/tests/` directory listings before being written into the workflow, and matched the plan/research list exactly (with `api.tests.test_production_config_check` added per the plan's explicit requirement).

## Issues Encountered

None blocking. `pyyaml` was not installed in the local sandbox by default; installed it via `pip install --user pyyaml` (no code/config change, a one-time local verification aid) to run the authoritative `yaml.safe_load` gate specified in each task's `<verify>` block, confirming the final `.github/workflows/deploy.yaml` parses as valid YAML. All other verification per this plan's environment constraints (no Postgres/Docker locally) is deferred to the first real GitHub Actions run, as stated in the plan's own `<verification>` section and Pitfall 1.

## User Setup Required

None for this plan's own changes. The next real push/PR to this repository will be the first execution of this workflow end-to-end; per Pitfall 1, whoever reviews that first CI run should confirm: (a) the reported test count is not suspiciously low, (b) the `load_reference_data` step takes 30+ seconds (not a silent no-op), and (c) `api.tests.test_reference_bootstrap`'s three tests specifically appear and pass in the log.

## Next Phase Readiness

- All three of this phase's requirements (CI-01, CI-02, SEC-03) now have both application-code (plans 01/02) and CI-wiring (this plan) halves complete.
- The phase's core deliverable, a deploy that cannot proceed on a failing suite, a high-severity security finding, or an unsafe production config, is fully wired into the single source-of-truth `.github/workflows/deploy.yaml`.
- No blockers identified. The one open item carried forward is Assumption A2 (test-label list completeness) and the general "trust the first green run" caution from Pitfall 1, both of which require a human to inspect the first real CI execution rather than being verifiable in this sandbox.

---
*Phase: 01-ci-test-gate-production-config-guard*
*Completed: 2026-07-08*

## Self-Check: PASSED

`.github/workflows/deploy.yaml` and this SUMMARY.md found on disk. Both task commit hashes (`e2bb141f`, `b0b12f26`) found in `git log --oneline --all`. `yaml.safe_load` parses the final workflow file without error. No em-dashes in the summary.
