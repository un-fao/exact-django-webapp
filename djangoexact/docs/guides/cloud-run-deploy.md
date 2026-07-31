# Cloud Run deployment guide (review environment)

## What this deploys

`.github/workflows/deploy-cloudrun.yaml` builds a self-contained gunicorn
image for the EX-ACT web API and deploys it to Cloud Run as a standalone,
additive pipeline. It covers the **review environment only**.

What it does NOT do:

- It does not touch App Engine. `djangoexact/app.yaml` and
  `.github/workflows/deploy.yaml` are unmodified, and App Engine keeps
  serving production exactly as it does today.
- It does not touch the existing Cloud Run Jobs (`exact-computation-job`).
  Those are a separate image, a separate workflow, and out of scope here.
- It does not perform a production cutover. Both platforms can serve the
  same Cloud SQL instance and the same GCS bucket at once, so the eventual
  cutover is a hostname flip, not a data migration.
- It does not resolve ingress or custom-domain mapping. That is an open FAO
  IT question, tracked below under "Ingress and allowed hosts".
- It does not use Secret Manager. Secrets reach the container the same way
  they already reach the App Engine build, through repository/environment
  secrets exported into the GitHub Actions job environment.

## One-time GCP setup

APIs to enable on the project, if not already enabled:

- `run.googleapis.com`
- `artifactregistry.googleapis.com`

The workflow creates the Artifact Registry repository itself the first time
it runs, if `IMAGE_REPO` does not already exist at `CLOUD_RUN_REGION`. No
manual repository creation is required.

IAM roles the WIF deploy service account (`vars.SERVICE_ACCOUNT`) needs,
beyond whatever App Engine deploys already required:

- `roles/run.admin` (deploy and manage the Cloud Run service)
- `roles/artifactregistry.writer` (push images)
- `roles/iam.serviceAccountUser` on the runtime service account
  (`RUNTIME_SERVICE_ACCOUNT`), so the deploy service account can attach it
  to the Cloud Run revision
- `roles/cloudsql.client` (connect through the `/cloudsql` unix socket)

## Repository variables and secrets

Every placeholder in `deploy/cloudrun-service.yaml` and every input the
workflow itself resolves is listed below. "Existing" entries are already
configured for the App Engine pipeline and are reused unchanged; setting a
Cloud Run specific value never widens or narrows what App Engine sees.

| Name | Kind | Scope | Status | Purpose |
|---|---|---|---|---|
| `PROJECT_ID` | variable | repository | existing | GCP project id, also derivable from `SERVICE_ACCOUNT` if unset |
| `SERVICE_ACCOUNT` | variable | repository | existing | WIF service account email; used to derive `PROJECT_ID` as a fallback |
| `WORKLOAD_ID_PROVIDER` | variable | repository | existing | WIF provider resource name |
| `STORAGE_BUCKET` | variable | review environment | existing | GCS media bucket |
| `DB_ENGINE` | variable | review environment | existing | Django DB backend, e.g. `django.db.backends.postgresql` |
| `DB_INSTANCE_CONNECTION` | variable | review environment | existing | Cloud SQL instance connection name, used for both the proxy and the `cloudsql-instances` annotation |
| `DB_USERNAME` | variable | review environment | existing | DB user; mapped in the manifest to the env var NAMED `DB_USER`, which is what `settings.py` reads |
| `DB_PASSWORD` | secret | review environment | existing | DB password |
| `DB_NAME` | variable | review environment | existing | DB name |
| `DB_PORT` | variable | review environment | existing | DB port, also used by the runner-side cloud-sql-proxy |
| `SECRET_KEY` | secret | review environment | existing | Django `SECRET_KEY` |
| `DJANGO_DEBUG` | variable | review environment | existing | Django debug flag |
| `ALLOWED_HOSTS` | variable | review environment | existing | App Engine review's `ALLOWED_HOSTS`; used only as the fallback if `CLOUDRUN_ALLOWED_HOSTS` is unset |
| `CORS_ALLOWED_ORIGINS` | variable | review environment | existing | App Engine review's CORS origins; fallback only, see `CLOUDRUN_CORS_ALLOWED_ORIGINS` |
| `BACKEND_BASE_URL` | variable | review environment | existing | App Engine review's backend URL. **Not** a fallback for the Cloud Run service; see `CLOUDRUN_BACKEND_BASE_URL` |
| `CLOUD_RUN_COMPUTATION_JOB_NAME` | variable | review environment | existing | Name of the existing computation Job, unrelated to this service but read by `settings.py` |
| `CLOUD_RUN_REGION` | variable | review environment | existing | Region for both the existing Job and this new service |
| `EMAIL_HOST` | variable | review environment | existing | SMTP host; App Engine seds this into `settings.py`, this workflow supplies it as a plain env var instead |
| `EMAIL_PORT` | variable | review environment | existing | SMTP port |
| `SMTP_USER_EMAIL` | variable | review environment | existing | SMTP auth user |
| `SMTP_USER_PASSWORD` | secret | review environment | existing | SMTP auth password |
| `FIREBASE_API_KEY` | variable | review environment | existing | Firebase web config |
| `FIREBASE_AUTH_DOMAIN` | variable | review environment | existing | Firebase web config |
| `FIREBASE_PROJECT_ID` | variable | review environment | existing | Firebase project id |
| `FIREBASE_STORAGE_BUCKET` | variable | review environment | existing | Firebase storage bucket |
| `FIREBASE_MESSAGING_SENDER_ID` | variable | review environment | existing | Firebase web config |
| `FIREBASE_APP_ID` | variable | review environment | existing | Firebase web config |
| `FIREBASE_MEASUREMENT_ID` | variable | review environment | existing | Firebase web config |
| `FIREBASE_SERVICE_ACCOUNT` | secret | review environment | existing | Base64 JSON Firebase Admin service account used at runtime; distinct from the throwaway build-time credential |
| `CLOUD_RUN_SERVICE_NAME` | variable | review environment | NEW, optional | Cloud Run service name. Defaults to `exact-api`. Deliberately distinct from `SERVICE_NAME`, which is already the App Engine service name |
| `IMAGE_REPO` | variable | review environment | NEW, optional | Artifact Registry repository name. Defaults to `artifacts` |
| `CLOUDRUN_ALLOWED_HOSTS` | variable | review environment | NEW, optional | `ALLOWED_HOSTS` for the Cloud Run service only. Falls back to `ALLOWED_HOSTS` if unset, but that App Engine value does not include the `*.run.app` hostname yet. See "Ingress and allowed hosts" below |
| `CLOUDRUN_CORS_ALLOWED_ORIGINS` | variable | review environment | NEW, optional | `CORS_ALLOWED_ORIGINS` for the Cloud Run service only, same fallback caveat |
| `CLOUDRUN_BACKEND_BASE_URL` | variable | review environment | NEW, optional | `BACKEND_BASE_URL` for the Cloud Run service **and** for the computation Job that sends the email. Feeds report-download email links. Unlike the two rows above it does **not** fall back to the App Engine value: see "Why the base URL has no fallback". Leaving it empty soft-disables that email rather than breaking the deploy |
| `RUNTIME_SERVICE_ACCOUNT` | variable | review environment | NEW, optional | Service account the Cloud Run revision runs as. Defaults to `$PROJECT_ID@appspot.gserviceaccount.com`, the same identity the computation Job already uses |
| `MIN_SCALE` | variable | review environment | NEW, optional | Knative `minScale`. Defaults to `0` |
| `MAX_SCALE` | variable | review environment | NEW, optional | Knative `maxScale`. Defaults to `4` |
| `CONTAINER_CONCURRENCY` | variable | review environment | NEW, optional | Requests per container instance. Defaults to `10`, mirroring App Engine Standard's roughly 10 concurrent requests against 4 gunicorn workers |
| `REQUEST_TIMEOUT_SECONDS` | variable | review environment | NEW, optional | Knative `timeoutSeconds`. Defaults to `300`, headroom above gunicorn's own 120s timeout |
| `CPU_LIMIT` | variable | review environment | NEW, optional | Container CPU limit. Defaults to `2` |
| `MEMORY_LIMIT` | variable | review environment | NEW, optional | Container memory limit. Defaults to `4Gi` |

`BRANCH_NAME` and `IMAGE` are not repository variables: `BRANCH_NAME` is set
inline by the workflow from `github.ref_name`, and `IMAGE` is derived from
the resolved Artifact Registry tag. Neither needs to be configured by hand.

**Warning:** no secret value above may contain an apostrophe. Every env
value in `deploy/cloudrun-service.yaml` is a single-quoted YAML scalar,
which is what keeps dollar signs and backslashes inside a secret literal
through `envsubst` (D-F). A single-quoted YAML scalar cannot itself contain
an unescaped apostrophe, so the render step fails loudly, naming the
variable, if any required value contains one.

## First run checklist

This follows the two-pass hostname path (recommended in "Ingress and
allowed hosts" below), because the Cloud Run service's `*.run.app` hostname
is not knowable until the service has deployed once.

1. Dispatch the workflow manually (`workflow_dispatch`) rather than pushing
   to `review`, so the first, throwaway run is deliberate.
2. Read the service URL from the job's `$GITHUB_STEP_SUMMARY` output
   (the "Report service URL" step).
3. Set `CLOUDRUN_ALLOWED_HOSTS`, `CLOUDRUN_CORS_ALLOWED_ORIGINS` and
   `CLOUDRUN_BACKEND_BASE_URL` to that hostname. The third is not
   optional in practice: until it is set, the report-ready email is
   soft-disabled, and the "Verify report download base URL" step will
   say so in the job summary.
4. Re-run the workflow.
5. Verify the admin panel at `/admin/` renders styled. This proves
   WhiteNoise is serving `STATIC_ROOT` correctly.
6. Verify a report PDF downloads successfully. This proves the WeasyPrint
   native library stack (Pango, Cairo, GDK-PixBuf, fontconfig) is present
   and working inside the image.
7. Verify a login round-trips. This proves Firebase Admin initialization
   and the Cloud SQL `/cloudsql` socket connection both work at runtime.

## Ingress and allowed hosts

The Cloud Run service's `*.run.app` hostname embeds the project number and
is not knowable before the first deploy. Until `ALLOWED_HOSTS` includes it,
every request returns `400 Bad Request` (`DisallowedHost`), even though the
deploy itself succeeds. Three options, presented as an open decision for
the team:

| Option | What it means | Trade-off |
|---|---|---|
| Two-pass (recommended) | Deploy once, read the URL from the job summary, set `CLOUDRUN_ALLOWED_HOSTS` and `CLOUDRUN_CORS_ALLOWED_ORIGINS`, re-run | One throwaway first run. Fully explicit, nothing widened |
| Subdomain wildcard | Add `.run.app` to `CLOUDRUN_ALLOWED_HOSTS`. Django treats a leading dot as a subdomain wildcard | One pass, but the service then accepts any `*.run.app` Host header. Cloud Run only routes its own hostname to the service, so practical exposure is low, but it is still a real widening |
| Precompute | Look up the project number and construct the URL before the first deploy | One pass, but the URL format is a Cloud Run implementation detail that has changed before |

This guide does not choose for the team; the first-run checklist above
assumes the two-pass path because it widens nothing.

## Why the base URL has no fallback

`CLOUDRUN_ALLOWED_HOSTS` and `CLOUDRUN_CORS_ALLOWED_ORIGINS` fall back to
their App Engine counterparts. `CLOUDRUN_BACKEND_BASE_URL` deliberately
does not, and the difference is not cosmetic.

A wrong `ALLOWED_HOSTS` fails loudly and immediately: the very next request
returns `400 DisallowedHost` and somebody notices within minutes. A wrong
`BACKEND_BASE_URL` fails silently and much later. It is not read on the
request path at all. It is read by a background worker with no request to
derive a host from, baked into a link, and mailed to a user who discovers
the problem hours later when the link 404s.

That is exactly what happened on review. The environment moved to Cloud
Run while its App Engine app was left at `servingStatus: USER_DISABLED`,
so `https://<project>.ew.r.appspot.com` served nothing. Because
`CLOUDRUN_BACKEND_BASE_URL` was never set, the old fallback substituted
that dead App Engine hostname into every emailed report link. Google's
routing layer answered `Error: Page not found` before the request ever
reached Django, so no application log recorded a thing. Two guards now
prevent a repeat:

- No fallback. An unset `CLOUDRUN_BACKEND_BASE_URL` yields an empty
  `BACKEND_BASE_URL`, and `send_report_ready_email` already refuses to
  send on empty, logging a warning. No email beats a dead link.
- The "Verify report download base URL" step probes
  `$CLOUDRUN_BACKEND_BASE_URL/api/health/` after every deploy and fails
  the run if the host is unreachable or answers `404`. A `5xx` passes:
  `/api/health/` legitimately returns `503` while the maintenance flag is
  on, and that still proves Django is serving the host.

The same value also reaches the computation Job through
`.github/workflows/deploy.yaml`, since that Job, not the web service, is
what sends the email. It prefers `CLOUDRUN_BACKEND_BASE_URL` and falls
back to `BACKEND_BASE_URL` only for environments still served by App
Engine.

## How this differs from App Engine

- Static files are served by WhiteNoise middleware, baked into the image at
  build time via `collectstatic`, instead of App Engine's
  `- url: /static` handler.
- `BRANCH_NAME=review` is set in the container so `FRONTEND_URL` resolves
  to the review frontend (D-E). App Engine review sets neither `APP_MODE`
  nor `BRANCH_NAME`, so it resolves `FRONTEND_URL` to the production
  frontend instead; that is a pre-existing App Engine quirk and is not
  fixed by this change.
- `containerConcurrency: 10` is chosen deliberately over Cloud Run's
  default of 80, to mirror App Engine Standard's roughly 10 concurrent
  requests per instance. This matters because `CONN_MAX_AGE = 0` makes
  every request open a new Postgres connection; Cloud Run's default
  concurrency would multiply connection churn eightfold against the same
  Cloud SQL instance.
- `_ah/warmup` (`djangoexact/urls.py:30`) stays in the URL configuration
  but is inert on Cloud Run; nothing calls it there.
- The request ceiling is still gunicorn's own `--timeout 120`, unchanged
  from `app.yaml:5`, even though Cloud Run's own `timeoutSeconds` is set
  higher as headroom so a gunicorn timeout surfaces as gunicorn's own
  error rather than a platform 504.

## Rollback

```
gcloud run services update-traffic $CLOUD_RUN_SERVICE_NAME \
  --to-revisions=REVISION=100 --region=$CLOUD_RUN_REGION --project=$PROJECT_ID
```

This is strictly better than the App Engine version juggling at
`deploy.yaml:346`, which prunes old versions by count rather than shifting
traffic to a known-good revision by name.

## Known follow-ups

In the order they should be picked up:

1. Unify `deploy/Dockerfile.web_service` and `deploy/Dockerfile.computation_job`
   behind one shared, published base image. They are a deliberate fork
   (D-B) kept in sync by hand; a verify gate compares their runtime apt
   package lists so they cannot drift silently, but that is a stopgap, not
   a fix.
2. Add a `.dockerignore` (D-J). Not done here because it would also change
   the build context of the existing computation Job image; safe in CI
   today since the ignored paths do not exist in a checkout, but a
   behaviour change for local ad-hoc builds.
3. Move `STATIC_ROOT` off the committed source `static/` tree into a
   dedicated `staticfiles/` directory, then enable WhiteNoise compression
   (`CompressedManifestStaticFilesStorage`). Not done together with adding
   WhiteNoise because the manifest pass can hard-fail on unresolvable
   `url()` references in third-party CSS (ckeditor, unfold, drf_yasg), and
   that failure was not reproducible in the sandbox this change was built
   in.
4. Run the container as a non-root user.
5. Retire the "read credentials back out of App Engine" pattern in
   `deploy.yaml:403-423` once the heredoc `$GITHUB_ENV` pattern proven here
   is applied to the computation Job as well.
6. Double migration on `review`: a push to `review` now triggers both this
   pipeline and the existing App Engine pipeline, and both run `migrate`
   against the same database. Accepted knowingly for the review
   environment only. If it proves noisy, give both workflows the same
   `concurrency.group`, which is a one-line change to each.
