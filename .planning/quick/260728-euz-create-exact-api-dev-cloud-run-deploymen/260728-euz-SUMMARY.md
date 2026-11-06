---
quick_id: 260728-euz
title: exact-api-dev Cloud Run deployment for feature/id-responses on the review DB
date: 2026-07-28
status: complete
branch: feature/id-responses
commits:
  - 712df88b  # merge origin/develop (deploy machinery + settings fixes)
  - ba630742  # feat(deploy): add exact-api-dev Cloud Run pipeline
---

# Summary: exact-api-dev Cloud Run deployment (develop)

## What was built

A new additive CI pipeline, `.github/workflows/deploy-cloudrun-develop.yaml`,
that builds the `feature/id-responses` branch and deploys it as a **new Cloud
Run service `exact-api-dev`** in the `fao-exact-review` project, connected to the
**shared review database** (`fao-exact-review:europe-west1:fao-exact-review-postgres`,
db `exact`) through the `/cloudsql` socket. It is a sibling of the review
pipeline (`deploy-cloudrun.yaml` -> `exact-api`) and reuses
`deploy/Dockerfile.web_service` and `deploy/cloudrun-service.yaml` unchanged.

## Decisions (locked with user)

1. **Pipeline on the dev branch** — workflow lives on `feature/id-responses` and
   auto-deploys on push there (plus `workflow_dispatch`).
2. **Service name** `exact-api-dev`.
3. **Skip migrate** — the pipeline runs no `migrate` and no runner-side DB step,
   so it can never mutate the shared review schema.

## How it was done

- **Merged `origin/develop` into `feature/id-responses`** (commit `712df88b`) to
  bring the deploy machinery (`deploy/Dockerfile.web_service`,
  `deploy/cloudrun-service.yaml`) and the required settings fixes
  (`SECURE_PROXY_SSL_HEADER`, WhiteNoise static serving). Two trivial conflicts
  resolved: `requirements.txt` -> kept develop's superset (adds
  `whitenoise==6.12.0`); `STATE.md` -> unioned both branches' quick-task rows.
- **Authored the dev workflow** (commit `ba630742`) as a precise derivative of
  the review workflow with only these deltas: `environment: develop`; service
  default `exact-api-dev`; trigger on `feature/id-responses` + dispatch;
  `BRANCH_NAME=develop`; removed the cloud-sql-proxy and migrate/check/invalidate
  steps; replaced the full requirements install with a minimal
  `cryptography`+`PyYAML` install. All secret-safety patterns (heredoc
  `$GITHUB_ENV` dump, single-quoted manifest scalars, render-guard, no-print
  deploy, BuildKit-mounted throwaway Firebase cred) preserved verbatim.

## Key discovery — App Engine environment coupling (avoided)

The `develop` GitHub environment is **shared** with the App Engine develop
deploy (`deploy.yaml`), which templates `DJANGO_DEBUG`, `CLOUD_RUN_REGION`, and
`CLOUD_RUN_COMPUTATION_JOB_NAME` into `app.yaml`. Adding those as develop-env
variables (the original plan) would have changed the App Engine dev service
(e.g. flipped it to `DEBUG=True`). Instead, every value the dev pipeline needs is
resolved as a **default inside the workflow**, so the shared `develop`
environment is left untouched and App Engine dev is unaffected:
`CLOUD_RUN_REGION=europe-west1`, `DJANGO_DEBUG=False` (matches App Engine dev),
computation-job path, and the precomputed host
`exact-api-dev-mesob2hoya-ew.a.run.app` (single-pass reachable, no 400 window).

## Verification done

- Workflow parses as YAML; no `manage.py` / `migrate` / `cloud-sql-proxy` /
  runner-side DB connection; `environment: develop`, `exact-api-dev`,
  `BRANCH_NAME=develop`, isolation defaults all present.
- IAM already satisfied: develop and review share the deploy SA
  (`github-actions-appengine@fao-exact-review`), so Cloud Run / Artifact Registry
  / Cloud SQL access is proven by the working review pipeline.
- Render-guard required-vars list satisfied by develop-env values + workflow
  defaults, with no new environment variable.

## NOT done (gated on user confirmation)

- **Pushing `feature/id-responses`**, which triggers the live first deploy. The
  push would ALSO publish 5 pre-existing unpushed local commits (prior quick task
  `260727-h79`, orphaned-shell-project sweep). Held for explicit user go-ahead.
- No live Cloud Run resource created yet; no GCP/GitHub infra mutated.
