# Quick Task 260728-euz: exact-api-dev Cloud Run deployment - Context

**Gathered:** 2026-07-28
**Status:** Ready for planning

<domain>
## Task Boundary

Create a new Cloud Run deployment that runs the `feature/id-responses` branch
code (the active branch for the development environment) and connects to the
shared **review** database, mirroring the existing review Cloud Run pipeline
(`deploy-cloudrun.yaml` -> service `exact-api`).
</domain>

<decisions>
## Implementation Decisions (locked with user 2026-07-28)

### Pipeline wiring
- Workflow lives ON `feature/id-responses` and auto-deploys on push to that
  branch (plus `workflow_dispatch`). The deploy machinery (`deploy/Dockerfile.web_service`,
  `deploy/cloudrun-service.yaml`, and the `SECURE_PROXY_SSL_HEADER` + WhiteNoise
  settings fixes) is brought onto the branch by merging `origin/develop` (the
  files did not exist on the feature branch; develop was only 15 commits ahead).

### Service name
- New Cloud Run service: **`exact-api-dev`**, deployed into the existing
  `fao-exact-review` GCP project (there is NO separate dev project; the dev
  frontend `fao-exact-frontend-dev` already lives in `fao-exact-review`).

### Migrations
- The dev pipeline **SKIPS migrate**. It must never mutate the shared review
  schema. The review Cloud Run pipeline and the App Engine pipelines own
  migrations. (feature/id-responses adds no new migrations vs review today, so
  this is a no-op difference now, but the guarantee is structural.)

### Config source (Claude's discretion, grounded in live infra)
- Runs under the existing GitHub **`develop` environment**, which already points
  at the review DB (`DB_INSTANCE_CONNECTION = fao-exact-review:europe-west1:fao-exact-review-postgres`,
  `DB_NAME = exact`, `PROJECT_ID = fao-exact-review`) and carries dev-flavoured
  Firebase / storage / CORS values.
- `BRANCH_NAME=develop` in the container (clean, slash-free; only affects
  `FRONTEND_URL` review-vs-prod selection in settings.py:32).
- `DJANGO_DEBUG=True` to mirror the review Cloud Run service.
</decisions>

<specifics>
## Specific Ideas / grounding facts

- Deploy SA is identical for develop and review
  (`github-actions-appengine@fao-exact-review.iam.gserviceaccount.com`), so the
  Cloud Run / Artifact Registry / Cloud SQL IAM is already satisfied.
- Every Cloud Run service in `fao-exact-review` shares the URL hash
  `mesob2hoya`, so the dev host is precomputable:
  `exact-api-dev-mesob2hoya-ew.a.run.app`. This lets the first deploy be a clean
  single pass (no 400 two-pass window) by setting `CLOUDRUN_ALLOWED_HOSTS` up
  front.
- The `develop` GitHub environment is MISSING required render-guard variables
  that must be added: `CLOUD_RUN_REGION`, `DJANGO_DEBUG`. Also recommended:
  `CLOUD_RUN_COMPUTATION_JOB_NAME` (async report/copy dispatch),
  `CLOUDRUN_ALLOWED_HOSTS` (precomputed dev host), `CLOUDRUN_BACKEND_BASE_URL`
  (report-link correctness). No repo-level vars exist; everything is env-scoped.
</specifics>

<canonical_refs>
## Canonical References

- `djangoexact/docs/guides/cloud-run-deploy.md` (review Cloud Run operator guide)
- `.github/workflows/deploy-cloudrun.yaml` (review pipeline, the template)
- `deploy/cloudrun-service.yaml` (Knative manifest, reused unchanged)
</canonical_refs>
