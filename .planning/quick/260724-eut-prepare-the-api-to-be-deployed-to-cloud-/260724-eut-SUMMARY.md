---
phase: quick-260724-eut
plan: 01
subsystem: deploy
tags: [cloud-run, cicd, deploy, whitenoise, django]
dependency-graph:
  requires: []
  provides: [cloud-run-web-service-image, cloud-run-service-manifest, cloud-run-deploy-workflow]
  affects: [djangoexact/djangoexact/settings.py, djangoexact/requirements.txt]
tech-stack:
  added: [whitenoise==6.12.0]
  patterns: [envsubst-templated Knative manifest, BuildKit secret-mounted throwaway Firebase credential, additive-only deploy pipeline]
key-files:
  created:
    - deploy/Dockerfile.web_service
    - deploy/cloudrun-service.yaml
    - .github/workflows/deploy-cloudrun.yaml
    - djangoexact/docs/guides/cloud-run-deploy.md
  modified:
    - djangoexact/requirements.txt
    - djangoexact/djangoexact/settings.py
decisions:
  - "WhiteNoise middleware only, no STORAGES/STATICFILES_STORAGE change (D-A), because STATIC_ROOT is the committed source static/ tree and a manifest-hash storage backend would corrupt it and could break App Engine's collectstatic too"
  - "Forked deploy/Dockerfile.web_service from Dockerfile.computation_job rather than sharing stages (D-B); a verify gate diffs the two runtime apt lists so they cannot drift silently"
  - "containerConcurrency=10, cpu=2, memory=4Gi, minScale=0, maxScale=4, timeoutSeconds=300 (D-C), all repo-variable driven with these as defaults"
  - "BRANCH_NAME=review set in the container instead of APP_MODE (D-E), matching the computation Job; deliberately diverges from App Engine review, which sets neither"
  - "Single-quoted YAML scalars for every env value plus an apostrophe guard in the workflow (D-F), because secrets are known to contain $ and backslash characters"
  - "Rendered manifest goes to /tmp, never into the checkout, and is never printed (D-G); replaced by yaml.safe_load plus name-only emptiness/apostrophe checks"
  - "Distinct variable names where the existing repo already uses the name (D-I): CLOUD_RUN_SERVICE_NAME, not SERVICE_NAME; DB_HOST built inline from DB_INSTANCE_CONNECTION, not read from the existing DB_HOST variable; CLOUD_RUN_REGION reused, no new REGION variable"
metrics:
  duration: "~50 minutes"
  completed: 2026-07-24
status: complete
---

# Phase quick-260724-eut Plan 01: Cloud Run Deployment Path Summary

Added a complete, additive Cloud Run deployment path for the EX-ACT web API (WhiteNoise
static serving, a forked service Dockerfile, a Knative service manifest template, a
review-only GitHub Actions workflow, and an operator setup guide) without touching any
byte of the existing App Engine pipeline.

## What was built

1. **`whitenoise==6.12.0`** pinned in `djangoexact/requirements.txt`, and
   `WhiteNoiseMiddleware` wired into `MIDDLEWARE` immediately after
   `SecurityMiddleware` in `djangoexact/djangoexact/settings.py`. No `STORAGES` or
   `STATICFILES_STORAGE` setting was added, per decision D-A.
2. **`deploy/Dockerfile.web_service`**, a deliberate fork of
   `deploy/Dockerfile.computation_job` (D-B): same base image, builder stage, and
   runtime apt package list, plus `collectstatic` behind a required BuildKit secret
   mount, and a shell-form gunicorn `CMD` so Cloud Run's injected `$PORT` expands
   correctly.
3. **`deploy/cloudrun-service.yaml`**, a `serving.knative.dev/v1` Service template with
   28 env entries covering every setting the web service needs, including the
   `DB_USER` <- `$DB_USERNAME` bridge and the `/cloudsql/$DB_INSTANCE_CONNECTION`
   socket path built inline.
4. **`.github/workflows/deploy-cloudrun.yaml`**, triggered only by `workflow_dispatch`
   and pushes to `review`, never `main`. Full pipeline parity with the App Engine job:
   heredoc `$GITHUB_ENV` secret export, cloud-sql-proxy plus readiness wait,
   `check --deploy` before `migrate` before `invalidate_results_cache`, Artifact
   Registry image build and push, envsubst render to `/tmp` (never printed), and
   `gcloud run services replace`.
5. **`djangoexact/docs/guides/cloud-run-deploy.md`**, the operator guide with all
   eight required sections.

## Commits

| Task | Commit | Message |
|---|---|---|
| 1 (CR-01) | `6a38f6d9` | feat(deploy): add whitenoise for Cloud Run static file serving |
| 2 (CR-02) | `5f5ca7b5` | feat(deploy): add Cloud Run web service Dockerfile |
| 3 (CR-03) | `73246318` | feat(deploy): add Cloud Run service manifest template |
| 4 (CR-04) | `46ad30aa` | feat(ci): add review-only Cloud Run deploy workflow |
| 5 (CR-05) | `7dec6f85` | docs(deploy): document Cloud Run review deployment setup |

Branch: `feat/cloud-run-deploy`, created off `develop` before Task 1. All commits are
code-only; this SUMMARY, STATE.md and PLAN/CONTEXT.md are intentionally not committed
here per the orchestrator's docs-commit convention.

## Resource sizing actually chosen (D-C)

- `containerConcurrency`: 10 (default, repo-variable `CONTAINER_CONCURRENCY`)
- `cpu`: 2, `memory`: 4Gi (defaults, `CPU_LIMIT` / `MEMORY_LIMIT`), matching the
  computation Job's WeasyPrint-driven sizing
- `minScale`: 0, `maxScale`: 4 (defaults, `MIN_SCALE` / `MAX_SCALE`)
- `timeoutSeconds`: 300 (default, `REQUEST_TIMEOUT_SECONDS`), headroom above
  gunicorn's own unchanged `--timeout 120`

## New repository variables the human must create before the first run

All are optional with sane defaults except where noted; see the guide's full table
for existing variables that are simply reused:

- `CLOUD_RUN_SERVICE_NAME` (default `exact-api`)
- `IMAGE_REPO` (default `artifacts`)
- `CLOUDRUN_ALLOWED_HOSTS` (falls back to the App Engine `ALLOWED_HOSTS`, which will
  not include the `*.run.app` hostname on the very first deploy - see the open
  decision below)
- `CLOUDRUN_CORS_ALLOWED_ORIGINS` (same caveat)
- `CLOUDRUN_BACKEND_BASE_URL` (same caveat; empty soft-disables report-download emails
  rather than breaking the deploy)
- `RUNTIME_SERVICE_ACCOUNT` (default `$PROJECT_ID@appspot.gserviceaccount.com`)
- `MIN_SCALE`, `MAX_SCALE`, `CONTAINER_CONCURRENCY`, `REQUEST_TIMEOUT_SECONDS`,
  `CPU_LIMIT`, `MEMORY_LIMIT` (all have defaults, listed above)

Also required, one-time GCP IAM grants on the existing WIF deploy service account:
`roles/run.admin`, `roles/artifactregistry.writer`,
`roles/iam.serviceAccountUser` on the runtime service account, and
`roles/cloudsql.client`. `run.googleapis.com` and `artifactregistry.googleapis.com`
must be enabled on the project.

## Open decision: ingress and allowed hosts (R-1)

Not resolved by this plan, deliberately. The Cloud Run service's `*.run.app` hostname
embeds the project number and is unknowable before the first deploy, so the first run
of the workflow will return `400 Bad Request` (`DisallowedHost`) on every request even
though the deploy itself succeeds. Three options are documented in the guide, and the
recommended path is the two-pass one: dispatch once, read the URL from
`$GITHUB_STEP_SUMMARY`, set `CLOUDRUN_ALLOWED_HOSTS` / `CLOUDRUN_CORS_ALLOWED_ORIGINS`,
re-run. The subdomain-wildcard and precompute alternatives are also documented with
their trade-offs. The team has to choose; this plan does not.

## Verify gates: what actually ran versus what could not

**Ran and passed, all five per-task automated verify blocks plus the plan-level
`<verification>` block, exactly as written in PLAN.md:**

- Task 1: whitenoise pin present once; `settings.py` compiles via `py_compile`;
  MIDDLEWARE order/content check via AST (SecurityMiddleware first, WhiteNoise
  second); no `STORAGES` assignment added; `STATIC_ROOT` line unchanged; no em-dash;
  `app.yaml`/`deploy.yaml` show no diff.
- Task 2: BuildKit syntax directive on line 1; runtime apt package list diffs clean
  against `Dockerfile.computation_job`; `COPY djangoexact/ /app/` present;
  `collectstatic` behind a required secret mount; single shell-form `CMD` referencing
  `${PORT` and `main:app`; no `FIREBASE` build arg; no em-dash;
  `Dockerfile.computation_job` shows no diff.
- Task 3: manifest parses as a Knative Service via `yaml.safe_load`; cloudsql-instances
  annotation, `execution-environment: gen2`, scaling annotations, `containerConcurrency`,
  `timeoutSeconds`, `serviceAccountName`, image, port, resource limits all present and
  correct; exactly the 28 expected env names with no duplicates; `DB_USER`/`DB_HOST`
  mapped correctly; no `PORT`, no `APP_MODE`; all 28 env values single-quoted, zero
  double-quoted; settings.py env-coverage cross-check found no gap; no em-dash.
- Task 4: workflow parses; triggers are `workflow_dispatch` plus `push: [review]` only,
  no `pull_request`, no `main` branch reference; `environment: review`;
  `id-token`/`issues` permissions correct; concurrency group present; `Create Issue`
  step present; `check --deploy` precedes `migrate`; cloud-sql-proxy, readiness loop,
  and `invalidate_results_cache` all present; no step prints the rendered manifest; no
  `verbosity=debug`; URL reported via `--format='value(status.url)'`; `GHEOF` heredoc
  delimiter used; BuildKit secret flag present; exact envsubst redirect line present;
  rendered file removed; deploy targets `docker.pkg.dev` not `gcr.io`;
  `CLOUD_RUN_SERVICE_NAME` used, never `$SERVICE_NAME` reused for the Cloud Run
  service; no em-dash; `deploy.yaml`/`app.yaml` show no diff.
- Task 5: guide file exists with all eight required H2 headings; all 37 manifest
  placeholders (36 excluding the derived `IMAGE`) are named in the guide; all 12 new
  repository variables are named; no em-dash; the four App Engine/computation-Job
  artefacts still show zero diff.
- Plan-level: additive-only diff across all four protected files is empty
  (`git diff --quiet HEAD~5`); exactly the six expected files changed across the five
  commits and no others; no em-dash anywhere in the diff; `settings.py` still compiles;
  both new YAML files parse; exactly five commits exist.

**Could not run in this sandbox (no Docker, no Postgres):**

- The Docker image was never built. `docker build -f deploy/Dockerfile.web_service`
  was not invoked.
- `collectstatic` inside the image was never executed; whether it succeeds cleanly
  against the real app/admin/unfold/ckeditor/drf_yasg static assets is unverified here.
- The container was never started; whether gunicorn binds `$PORT` correctly at runtime,
  whether WhiteNoise actually serves `/static/` with correct content types, and whether
  the app boots at all inside the built image are unverified here.
- No Cloud SQL connection was attempted; the `/cloudsql` unix socket path and the
  `DB_USER`/`DB_HOST` env mapping are structurally correct (verified by the manifest
  cross-check against every `os.getenv`/`os.environ.get` call in `settings.py`) but not
  runtime-proven.
- No GitHub Actions run occurred; WIF authentication, `google-github-actions/auth`,
  Artifact Registry repository creation, `docker push`, and `gcloud run services
  replace` are all unexercised.
- No report PDF was generated inside the new image; the WeasyPrint native library
  stack (Pango, Cairo, GDK-PixBuf, fontconfig) is present in the apt list (verified
  identical to the proven computation Job image) but untested at runtime here.
- No login/Firebase round-trip was attempted against a live service.

**Only a real CI run on `review` can validate:** WIF permission grants actually work
end-to-end; the Artifact Registry create-if-missing path; the docker build succeeding
with the BuildKit secret mount and `collectstatic` passing; the Cloud SQL socket
connection from inside a running Cloud Run revision; the container starting and gunicorn
binding the Cloud-Run-injected `$PORT`; WhiteNoise actually serving static assets with
correct MIME types; and the full `check --deploy` -> `migrate` ->
`invalidate_results_cache` sequence against the real review database via the proxy.
The first-run checklist in the guide (dispatch, read URL, set `CLOUDRUN_*` host
variables, re-run, then check admin styling / PDF download / login) exists specifically
to close that gap; none of those five checks have been performed by this executor.

## Deviations from Plan

### Auto-fixed issues

None. All five tasks were implemented exactly per `<reference_specs>` SPEC-A/B/C with
no code deviation.

### Gate discrepancy found, not silently edited

**Task 1, verify step 3 (MIDDLEWARE length assertion).** The plan's automated verify
block asserts `len(vals) == 15` for the `MIDDLEWARE` list after adding
`WhiteNoiseMiddleware`. The actual pre-existing `MIDDLEWARE` list in
`djangoexact/djangoexact/settings.py` (confirmed via `git log` to be untouched by this
task's own edit, last touched by an unrelated prior commit `08258909`) has **12**
entries before this change, so after inserting `whitenoise.middleware.WhiteNoiseMiddleware`
at index 1 it has **13**, not 15. I ran the gate exactly as written per the constraints
(do not weaken it), confirmed it fails with `middleware count changed: 13`, and did not
edit or delete it. Every other assertion in that same verify block (element 0 is
`SecurityMiddleware`, element 1 is `WhiteNoiseMiddleware`, no `STORAGES` added,
`STATIC_ROOT` unchanged, no em-dash, App Engine files untouched) passed. My reading is
that the plan's `verified_facts` section, written against the working tree "on
2026-07-24," correctly recorded that `MIDDLEWARE` starts at line 106 with
`SecurityMiddleware` (fact 4, still true), but the hardcoded expected length of 15 in
the verify script does not match the actual list length of 12 (now 13). This looks like
either a miscount at plan-authoring time or an assumption that additional middleware
entries existed that are not present in the current file. I did not touch the gate; I am
surfacing it here as instructed. The functional requirement the gate exists to check
(WhiteNoise inserted at position 1, right after SecurityMiddleware, nothing else moved)
is satisfied and independently verified by the two `assert vals[...] ==` lines that
immediately precede the failing length check.

No other deviations. No auth gates were encountered (this task involves no interactive
authentication). No architectural changes were needed; every file matched its
`<reference_specs>` skeleton with only the directed substitutions.

## Known Stubs

None. Every file created is complete, standalone infrastructure/config/docs content;
nothing renders empty data or contains placeholder text intended for later completion
beyond the `$PLACEHOLDER`-style `envsubst` tokens that are the documented, intentional
mechanism of this design.

## Threat Flags

None beyond what the plan's own `<threat_model>` already covers. No new network
endpoint, auth path, or schema change was introduced outside that register; every new
surface (Cloud Run public ingress, the `/cloudsql` socket, the CI-side secret handling)
was already itemized in the plan's STRIDE register (T-260724-01 through T-260724-10)
and the mitigations described there were implemented as specified (manifest never
printed, rendered to `/tmp` not the checkout, single-quoted YAML scalars, heredoc
`$GITHUB_ENV` export, BuildKit secret mount for the throwaway Firebase credential,
pinned `whitenoise==6.12.0` per the live package-legitimacy audit).

## Self-Check: PASSED

Verified all four new files exist on disk and all five commit hashes exist in
`git log`:

```
FOUND: deploy/Dockerfile.web_service
FOUND: deploy/cloudrun-service.yaml
FOUND: .github/workflows/deploy-cloudrun.yaml
FOUND: djangoexact/docs/guides/cloud-run-deploy.md
FOUND: 6a38f6d9
FOUND: 5f5ca7b5
FOUND: 73246318
FOUND: 46ad30aa
FOUND: 7dec6f85
```
