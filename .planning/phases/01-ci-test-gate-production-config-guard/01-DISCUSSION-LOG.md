# Phase 1: CI Test Gate & Production Config Guard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-07-08
**Phase:** 1-CI Test Gate & Production Config Guard
**Mode:** --auto (all gray areas auto-selected; recommended option chosen per question, no user prompts)
**Areas discussed:** Workflow topology, CI database provisioning, Test-job environment, Security scan tooling & thresholds, Deploy-check design, Trigger coverage, Legacy pipeline handling

---

## Workflow topology

| Option | Description | Selected |
|--------|-------------|----------|
| Test job inside deploy.yaml | Add test job to the existing workflow; deploy gains needs: test plus an event guard | ✓ |
| Separate ci.yaml | New workflow for PRs; duplicate test definition referenced by deploy | |

**Auto choice:** Test job inside deploy.yaml (recommended default)
**Notes:** Single source of truth; avoids drift between two job definitions.

---

## CI database provisioning

| Option | Description | Selected |
|--------|-------------|----------|
| Postgres service container | Health-checked container on the runner; no GCP credentials needed for PRs | ✓ |
| cloud-sql-proxy to throwaway Cloud SQL | Matches production engine exactly but needs credentials on every PR run | |

**Auto choice:** Service container (recommended default; roadmap success criterion names it)
**Notes:** Major version to match production Cloud SQL; researcher confirms, default postgres:15.

---

## Test-job environment

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit env vars in workflow | Self-describing CI; DB_*/SECRET_KEY/DJANGO_DEBUG set in YAML | ✓ |
| APP_MODE=test with .env.test | Reuses checked-in env file; couples CI to private file contents | |

**Auto choice:** Explicit env vars (recommended default)
**Notes:** Env files are private (read denied even locally); researcher verifies whether the suite needs APP_MODE=test, which would override.

---

## Security scan tooling & thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| requirements-dev.txt with pins | bandit + pip-audit pinned in a dev-only requirements file, reused locally and in CI | ✓ |
| Unpinned pip install in CI step | Simplest, but versions drift silently | |
| Add to runtime requirements.txt | Pollutes production dependency set | |

**Auto choice:** requirements-dev.txt (recommended default)
**Notes:** bandit at HIGH severity; pip-audit fails on any known CVE with documented --ignore-vuln escape hatch.

---

## Deploy-check design

| Option | Description | Selected |
|--------|-------------|----------|
| Error-level custom checks, default fail level | api/checks.py raises Error; check --deploy fails only on Errors | ✓ |
| --fail-level WARNING | Also blocks on Django built-in deploy warnings (HSTS, SSL redirect) which the legacy app will trip | |

**Auto choice:** Error-level custom checks (recommended default)
**Notes:** Keeps the gate scoped to this phase's assertions without inheriting Django's full deploy-warning checklist.

---

## Trigger coverage

| Option | Description | Selected |
|--------|-------------|----------|
| PRs (develop/main/review) + existing push branches | Gate signal on every PR; deploy stays push-gated | ✓ |
| Push-only | Preserves current triggers but PRs to develop still run nothing | |

**Auto choice:** PRs + existing push branches (recommended default)
**Notes:** develop PRs currently trigger no CI at all; this closes that gap.

---

## Legacy pipeline handling

| Option | Description | Selected |
|--------|-------------|----------|
| Leave bitbucket-pipelines.yml untouched | GitHub Actions is the active CI; Bitbucket file is a legacy mirror | ✓ |
| Update in parallel | Doubles maintenance for a pipeline that may not run | |

**Auto choice:** Leave untouched (recommended default)

---

## Claude's Discretion

- Exact Postgres image tag, health-check parameters, pip caching, step ordering
- Whether to split lint/scan steps for readability within the single test job
- Naming of the test job and any composite steps

## Deferred Ideas

- PR-comment / job-summary reporting for bandit + pip-audit findings (CI-V2-01)
- Python-version test matrix
- Replacing sed templating with a proper secret-injection mechanism (audit recommendation, future milestone)
