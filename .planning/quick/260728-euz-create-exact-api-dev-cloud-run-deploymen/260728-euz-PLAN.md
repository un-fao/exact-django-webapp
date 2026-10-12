---
quick_id: 260728-euz
title: exact-api-dev Cloud Run deployment for feature/id-responses on the review DB
date: 2026-07-28
status: in-progress
---

# Plan: exact-api-dev Cloud Run deployment (develop)

## Goal

Stand up a new `exact-api-dev` Cloud Run service in `fao-exact-review` that
builds and serves the `feature/id-responses` branch and connects to the shared
review database, via an additive, skip-migrate CI pipeline that mirrors the
review Cloud Run workflow. Never touches App Engine, the review Cloud Run
service, or the review DB schema.

## Tasks

### Task 1 - Bring deploy machinery onto feature/id-responses (DONE)
- **files:** merge commit on `feature/id-responses`
- **action:** merge `origin/develop` into `feature/id-responses`; resolve the two
  trivial conflicts (requirements.txt -> keep develop superset incl.
  `whitenoise==6.12.0`; STATE.md -> union both quick-task rows).
- **verify:** `deploy/Dockerfile.web_service`, `deploy/cloudrun-service.yaml`,
  `.github/workflows/deploy-cloudrun.yaml` present; `SECURE_PROXY_SSL_HEADER` in
  settings.py; `whitenoise` in requirements.txt.
- **done:** merge commit created, tree clean, no conflict markers.

### Task 2 - Author deploy-cloudrun-develop.yaml
- **files:** `.github/workflows/deploy-cloudrun-develop.yaml` (new)
- **action:** derive from `deploy-cloudrun.yaml` with exactly these deltas:
  name `(develop)`; trigger `push: [feature/id-responses]` + `workflow_dispatch`;
  `environment: develop`; `CLOUD_RUN_SERVICE_NAME` default `exact-api-dev`;
  `BRANCH_NAME=develop` (hardcoded); REMOVE the cloud-sql-proxy step and the
  migrate/check/invalidate step; replace the full requirements install with a
  minimal `cryptography`+`PyYAML` install (only the cred-gen and yaml-parse need
  Python). Preserve verbatim: the heredoc `$GITHUB_ENV` secret dump, the
  render-guard, the no-print deploy, the report-URL step, image build with the
  BuildKit-mounted throwaway Firebase cred.
- **verify:** `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-cloudrun-develop.yaml'))"` parses; no `migrate`/`cloud-sql-proxy` strings; `environment: develop`; `exact-api-dev` present.
- **done:** file committed atomically (code-only commit) on feature/id-responses.

### Task 3 - Isolate config in-workflow (REVISED: no shared-env changes)
- **discovery:** the App Engine develop deploy (`deploy.yaml`) triggers on
  `develop`, uses the SAME `develop` GitHub environment, and templates
  `DJANGO_DEBUG`, `CLOUD_RUN_REGION`, `CLOUD_RUN_COMPUTATION_JOB_NAME` into
  `app.yaml`. Adding those as develop-env variables would change the App Engine
  dev service (e.g. flip it to DEBUG=True). REJECTED.
- **action:** resolve all missing values as defaults INSIDE the new workflow's
  "Resolve deployment identifiers" step (region=europe-west1, DJANGO_DEBUG=False
  to match App Engine dev, the computation-job path, and the precomputed
  `exact-api-dev-mesob2hoya-ew.a.run.app` for ALLOWED_HOSTS / BACKEND_BASE_URL).
  The shared `develop` environment is left completely untouched.
- **verify:** render-guard var list satisfied without any new env var; App Engine
  dev deploy behaviour unchanged.
- **done:** defaults baked into the workflow (commit ba630742); zero gh-api env
  writes.

## must_haves

- truths:
  - The dev pipeline connects to `fao-exact-review:europe-west1:fao-exact-review-postgres` / db `exact`.
  - The dev pipeline runs no `migrate` / no runner-side DB mutation.
  - The service deploys as `exact-api-dev` in `fao-exact-review`.
- artifacts:
  - `.github/workflows/deploy-cloudrun-develop.yaml`
  - merge of develop into feature/id-responses (deploy machinery present)
- key_links:
  - `.github/workflows/deploy-cloudrun.yaml` (template)
  - `deploy/cloudrun-service.yaml` (reused unchanged)

## Out of scope / checkpoint

- Actually pushing `feature/id-responses` (which triggers the live first deploy,
  and would also push 5 pre-existing unpushed local commits from task 260727-h79)
  is gated behind explicit user confirmation.
