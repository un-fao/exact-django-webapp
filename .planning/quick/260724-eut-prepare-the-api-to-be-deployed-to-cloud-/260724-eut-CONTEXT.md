# Quick Task 260724-eut: prepare the API to be deployed to Cloud Run instead of App Engine - Context

**Gathered:** 2026-07-24
**Status:** Ready for planning

<domain>
## Task Boundary

Prepare the EX-ACT web API service to run on Cloud Run, additively, without disturbing
the App Engine deployment that currently serves production.

In scope: a web-service container image, WhiteNoise static file serving, a Knative
`service.yaml`, and a new GitHub Actions workflow that builds and deploys to Cloud Run
in the **review** environment only.

Out of scope: the production cutover itself, the ingress/custom-domain decision (FAO IT
dependency), Secret Manager, and any change to the existing Cloud Run *Jobs*
(`exact-computation-job`), which already run on Cloud Run and are not in question.

Builds on the feasibility evaluation at
`.planning/quick/260723-jas-cloud-run-migration-feasibility/EVALUATION.md`.

</domain>

<decisions>
## Implementation Decisions

### Scope: additive, App Engine stays live

- `djangoexact/app.yaml` and `.github/workflows/deploy.yaml` are **not modified**.
  App Engine keeps deploying exactly as it does today.
- Cloud Run is added alongside. Both platforms can serve the same Cloud SQL instance
  and the same GCS bucket simultaneously. There is no data migration, so the eventual
  cutover is a hostname flip, not a move.
- If FAO IT declines the custom-domain path onto Cloud Run, nothing has to be undone.

### Secrets: no Secret Manager, use the org's Cloud Run pattern

The user supplied a working Cloud Run workflow from another API in the FAO organization.
That pattern is the reference implementation and should be followed closely.

- Dump all repo `vars` and `secrets` into `$GITHUB_ENV` with heredoc delimiters:
  ```
  echo '${{ toJson(vars) }}'    | jq -r 'to_entries[] | "\(.key)<<EOF\n\(.value)\nEOF"' >> $GITHUB_ENV
  echo '${{ toJson(secrets) }}' | jq -r 'to_entries[] | "\(.key)<<EOF\n\(.value)\nEOF"' >> $GITHUB_ENV
  ```
- **Why this matters beyond convenience:** heredoc-delimited `$GITHUB_ENV` entries are
  literal, so they do not suffer the escaping divergence documented at
  `.github/workflows/deploy.yaml:370`, where GitHub Actions' YAML `env:` interpolation
  adds two characters to any secret containing `$` or a backslash and breaks psycopg2
  auth. That bug is the sole reason the computation Job currently reads `DB_PASSWORD`
  and `SECRET_KEY` back out of the deployed App Engine version. This pattern removes
  the need for Secret Manager entirely.
- Values reach the container by `envsubst` into `service.yaml`, using the org template's
  `subst()` helper. Do **not** echo the substituted `service.yaml`: it contains
  `DB_PASSWORD`, `SECRET_KEY`, `SMTP_USER_PASSWORD` and `FIREBASE_SERVICE_ACCOUNT`.
  This is the one deliberate deviation from the org template, which cats the file.

### No sed of settings.py in the image

**Verified:** every setting reads from the environment with the `$PLACEHOLDER` only as a
fallback default (`settings.py:36,53,67,170-175,312-329,347-348`). The `GAE_APPLICATION`
branch at `settings.py:146` is not taken on Cloud Run, so the env-var branch at line 168
applies. The image is therefore built from unsubstituted source and configured purely
through `service.yaml` env vars, exactly as `deploy/Dockerfile.computation_job` already
does in production.

### Deploy mechanism

- Artifact Registry, not gcr.io:
  `$REGION-docker.pkg.dev/$PROJECT_ID/$IMAGE_REPO/$SERVICE_NAME:${{ github.run_number }}`
  plus a `:latest` tag. Create the repository if it does not exist.
- `docker build` on the runner with BuildKit, then `gcloud run services replace service.yaml`.
  Cloud Build stays bypassed: an org policy blocks the deploy service account from the
  Cloud Build staging bucket (see `.github/workflows/deploy.yaml:353-357`).
- Auth by Workload Identity Federation via `vars.WORKLOAD_ID_PROVIDER` and
  `vars.SERVICE_ACCOUNT`. This repo already uses WIF, so no new setup is required.
- Public access: `add-iam-policy-binding` for `allUsers` with `roles/run.invoker`, plus
  `--ingress=all`, matching the org template.

### Cloud SQL connectivity

Use the `run.googleapis.com/cloudsql-instances` annotation with
`DB_HOST=/cloudsql/$DB_INSTANCE_CONNECTION`, mirroring the existing computation Job
(`deploy.yaml:418,465`), which is proven in production against this same instance.
No VPC connector and no `VPC_EGRESS`, unlike the org template, because the unix-socket
path is already known to work here.

### Static files: WhiteNoise

- Add `whitenoise` to `djangoexact/requirements.txt` and insert its middleware directly
  after `django.middleware.security.SecurityMiddleware` (`settings.py:106-107`).
- Run `collectstatic` inside the Docker build so the image is self-contained.
- Note `STATIC_ROOT` and the source `static/` directory are the same path
  (`settings.py:236`). Preserve that behaviour rather than fixing it here; it is
  pre-existing and orthogonal to this task.
- WhiteNoise is inert on App Engine, whose `- url: /static` handler intercepts before
  Django, so adding it does not change App Engine behaviour.

### Workflow layout and trigger

- New file `.github/workflows/deploy-cloudrun.yaml`, a close adaptation of the org
  template. The existing `deploy.yaml` is untouched.
- Triggers: `workflow_dispatch` plus push to **`review` only**. Explicitly not `main`.
- `environment: review`.
- Rationale: full pipeline parity is wanted, but production must not have two pipelines
  deploying and migrating against it.

### Pipeline parity

The Cloud Run workflow is a complete standalone pipeline from day one: `cloud-sql-proxy`,
`check --deploy` before `migrate` (so a rejected config aborts without mutating schema,
per WR-02 in the existing workflow), `migrate`, and `runscript invalidate_results_cache`.

### Claude's Discretion

- Container resource sizing and concurrency. Guidance from the evaluation: App Engine
  Standard caps concurrency near 10 per instance against 4 gunicorn workers on F4_1G,
  and `CONN_MAX_AGE = 0` means every request opens a new Postgres connection, so Cloud
  Run's default of 80 would multiply connection churn eightfold. Set `containerConcurrency`
  explicitly in the 8 to 16 range. Size CPU and memory at least at F4_1G, bearing in mind
  the computation Job uses 2 CPU / 4 GiB specifically because of WeasyPrint. Prefer
  repo-variable-driven values with sane defaults.
- Whether to keep the gunicorn entrypoint identical
  (`gunicorn -b :$PORT -w 4 main:app --timeout 120`). Cloud Run supplies `$PORT` the same
  way App Engine does, so it should port unchanged.
- Dockerfile location and whether to share stages with `Dockerfile.computation_job`.
- Request timeout: Cloud Run allows up to 60 minutes against App Engine's 10, but
  gunicorn's `--timeout 120` is the effective ceiling today.
- Scaling floor: `--min-instances`/`minScale` is the analogue of App Engine's
  `min_idle_instances: 1`, but review does not need a warm instance.

</specifics>
## Specific Ideas

The user supplied a verbatim reference workflow from another Cloud Run API in the FAO
organization. Follow its structure: the `vars`/`secrets` jq dump into `$GITHUB_ENV`, the
`PROJECT_ID` derivation from the service account (`p="${SERVICE_ACCOUNT#*@}"; PROJECT_ID=${p%%.*}`),
the `SERVICE_NAME` fallback to the repository name, the `TAG`/`TAG_LATEST` construction,
the `subst()` envsubst helper, the Artifact Registry create-if-missing step, and
`gcloud run services replace`.

Deviations from that template, all deliberate and listed above: no `VPC_EGRESS`, review
branch only rather than `[main, review]`, no `cat` of the substituted `service.yaml`, and
Cloud SQL by socket annotation.

</specifics>

<canonical_refs>
## Canonical References

- `.planning/quick/260723-jas-cloud-run-migration-feasibility/EVALUATION.md` (2026-07-23)
  Feasibility verdict, work items ordered by risk, effort estimate.
- `.github/workflows/deploy.yaml` Current App Engine pipeline. Lines 370-381 document the
  `$`/backslash secret-mangling bug this task's env pattern sidesteps.
- `deploy/Dockerfile.computation_job` Proven container build for this codebase, carrying
  the full psycopg2 and WeasyPrint native dependency stack.
- `djangoexact/app.yaml` The App Engine config being mirrored, not replaced.
- `djangoexact/docs/guides/async-jobs.md` Context on the Cloud Run Jobs already in use.

</canonical_refs>

<residual_risks>
## Residual Risks

1. **Double migration on `review`.** A push to `review` triggers both the existing App
   Engine pipeline and the new Cloud Run pipeline, and both run `migrate` against the same
   review database. Django migrations are individually locked but two concurrent runs can
   still race. Accepted knowingly: it affects the review environment only. Worth a shared
   `concurrency:` group later if it proves noisy.
2. **Ingress is still unresolved.** Cloud Run will be reachable only on its
   `*.run.app` URL until FAO IT rules on custom-domain mapping. `ALLOWED_HOSTS`,
   `CORS_ALLOWED_ORIGINS` and `BACKEND_BASE_URL` for the review service must include that
   URL for validation to be meaningful.
3. **The computation Job still reads credentials from App Engine.** Untouched by this
   task by design, so App Engine cannot be retired yet. The env pattern adopted here is
   what will eventually let that hack go.

</residual_risks>
