# Cloud Run Job Provisioning for `review` Environment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish end-to-end Cloud Run Jobs provisioning for the admin-scripts scenario builder on the GitHub `review` environment so enqueued computations dispatch to a real Cloud Run Job (not the local subprocess fallback) and complete successfully on the deployed `review` site.

**Architecture:** The app-level dispatcher (`admin_scripts/cloud_run.py::dispatch_cloud_run_job`) already calls `run_v2.JobsClient.run_job` with arg overrides — the implementation work is to (1) make the `google-cloud-run` SDK installable on App Engine, (2) produce a self-contained container image for the Cloud Run Job, (3) extend `.github/workflows/deploy.yaml` with two guarded steps that build the image and create/update the Cloud Run Job resource per push, and (4) wire IAM + GitHub env vars for the review project. The CI steps are guarded by `if: vars.CLOUD_RUN_COMPUTATION_JOB_NAME != ''` so production/develop stay no-op until later.

**Tech Stack:** Python 3.11, Django, App Engine Standard (webapp), Cloud Run Jobs (compute target), Cloud Build (image build), Container Registry / `gcr.io`, GitHub Actions, Workload Identity Federation, Cloud SQL (PostgreSQL via unix socket).

**Linked beads issue:** `exact-django-webapp-89e`

**Source spec:** `docs/superpowers/specs/2026-05-11-cloud-run-job-review-env-design.md`

---

## Pre-flight

Before any task, claim the beads issue and confirm the current working tree.

- [ ] **Step 0a: Claim the beads issue**

Run:
```bash
bd update exact-django-webapp-89e --claim
bd update exact-django-webapp-89e --status=in_progress
```

- [ ] **Step 0b: Confirm clean working tree**

Run:
```bash
git status
git log -1 --oneline
```

Expected: working tree clean (or only contains the new spec/plan files in untracked state), branch is `develop`.

- [ ] **Step 0c: Resolve the exact `google-cloud-run` pin**

Run:
```bash
pip index versions google-cloud-run 2>&1 | head -3
```

Record the latest 0.10.x stable version (no `b`/`rc` suffix). For the rest of this plan I will write `0.10.X` — substitute the resolved version in every place the literal appears.

Expected output looks like:
```
google-cloud-run (0.10.18)
Available versions: 0.10.18, 0.10.17, ...
```

---

## Task 1: Add `google-cloud-run` to webapp dependencies

**Why:** Without this, `from google.cloud import run_v2` in `cloud_run.py:23` raises `ImportError` on App Engine. The current code logs and returns `None`, but `job_dispatcher.dispatch_job` does **not** fall back to subprocess when `CLOUD_RUN_COMPUTATION_JOB_NAME` is non-empty (job_dispatcher.py:93-96). Result: dispatch silently fails and `ComputationJob` rows stay `pending` forever.

**Files:**
- Modify: `djangoexact/requirements.txt`

- [ ] **Step 1.1: Locate the `google-cloud-storage` line as anchor for placement**

Run:
```bash
grep -n "google-cloud" djangoexact/requirements.txt
```

Expected: one match, `google-cloud-storage==2.19.0`.

- [ ] **Step 1.2: Add `google-cloud-run` directly below `google-cloud-storage`**

Edit `djangoexact/requirements.txt`. Replace the line:

```
google-cloud-storage==2.19.0
```

with:

```
google-cloud-storage==2.19.0
google-cloud-run==0.10.X
```

(Substitute the version resolved in Step 0c.)

- [ ] **Step 1.3: Verify the pin resolves in a fresh venv (optional but recommended)**

Run from a scratch directory:
```bash
python -m venv /tmp/cloud-run-pin-check
/tmp/cloud-run-pin-check/Scripts/activate    # Windows
# or: source /tmp/cloud-run-pin-check/bin/activate   # Unix
pip install google-cloud-run==0.10.X
python -c "from google.cloud import run_v2; print(run_v2.JobsClient)"
deactivate
rm -rf /tmp/cloud-run-pin-check
```

Expected: `<class 'google.cloud.run_v2.services.jobs.client.JobsClient'>` printed.

- [ ] **Step 1.4: Commit**

```bash
git add djangoexact/requirements.txt
git commit -m "deps(jobs): add google-cloud-run for Cloud Run Job dispatch

Without this, the App Engine webapp hits the ImportError branch in
admin_scripts/cloud_run.py and silently returns None when
CLOUD_RUN_COMPUTATION_JOB_NAME is set, leaving ComputationJob rows
stuck at pending."
```

---

## Task 2: Rewrite `deploy/Dockerfile.computation_job` as self-contained image

**Why:** The current Dockerfile starts `FROM ${BASE_IMAGE}` with `BASE_IMAGE=gcr.io/$PROJECT_ID/exact-webapp:latest` — but App Engine Standard does not produce a container image, so that base does not exist. We need a self-contained Dockerfile that builds the Django app from scratch.

**Files:**
- Modify (full rewrite): `deploy/Dockerfile.computation_job`

- [ ] **Step 2.1: Confirm the current contents (sanity check before overwriting)**

Run:
```bash
cat deploy/Dockerfile.computation_job
```

Expected: the two-step `FROM ${BASE_IMAGE}` wrapper documented in the spec.

- [ ] **Step 2.2: Replace `deploy/Dockerfile.computation_job` with the self-contained image**

Full new content:

```dockerfile
# syntax=docker/dockerfile:1.6

# Self-contained image for the Cloud Run Job that executes
# `python manage.py run_computation_job`. This image is *not* derived from
# the App Engine deployment — App Engine Standard does not produce a
# container, so the Cloud Run Job builds its own.
#
# Build context: repo root. Invoked from CI via:
#   gcloud builds submit --config=deploy/cloudbuild-computation-job.yaml .

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# psycopg2 needs libpq + a build toolchain. We keep the toolchain in a
# separate stage so the runtime image stays slim.
FROM base AS builder
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY djangoexact/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip 'setuptools>=78.1.1' wheel \
 && pip install --prefix=/install -r /app/requirements.txt \
 && pip install --prefix=/install --force-reinstall 'setuptools>=78.1.1'

FROM base AS runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
WORKDIR /app
COPY djangoexact/ /app/

# Cloud Run Jobs execute the container command once and exit.
# `run_computation_job` is the management command at
# admin_scripts/management/commands/run_computation_job.py.
ENTRYPOINT ["python", "manage.py", "run_computation_job"]
```

- [ ] **Step 2.3: Build the image locally to verify the Dockerfile**

Run from repo root:
```bash
docker build -f deploy/Dockerfile.computation_job -t exact-computation-job:local .
```

Expected: build succeeds; final image tagged `exact-computation-job:local`. Build time will be 2-5 minutes (full pip install).

- [ ] **Step 2.4: Verify the entrypoint surfaces the Django management command help**

Run:
```bash
docker run --rm exact-computation-job:local --help
```

Expected output starts with:
```
usage: manage.py run_computation_job [-h] --job-id JOB_ID ...
```

If it says `manage.py: error: unrecognized arguments`, the ENTRYPOINT is wrong. If you get an `ImportError` for a Django setting like `FIREBASE_SERVICE_ACCOUNT`, that is **expected** — settings.py:305-322 wants those env vars and they are unset in the local test run; the Cloud Run Job will set them via `--set-env-vars` (covered in Task 5). The `--help` invocation should still work because Django arg parsing happens before settings import for `--help`.

If `--help` itself crashes with the Firebase error, that is a regression worth investigating before proceeding — the management command framework normally short-circuits on `--help`. Add `--skip-checks` and re-test:
```bash
docker run --rm -e SECRET_KEY=test exact-computation-job:local --help --skip-checks
```

- [ ] **Step 2.5: Commit**

```bash
git add deploy/Dockerfile.computation_job
git commit -m "build(jobs): rewrite computation-job Dockerfile as self-contained image

The previous wrapper extended gcr.io/PROJECT_ID/exact-webapp:latest, but
the webapp deploys via App Engine Standard which produces no container.
This rewrite builds from python:3.11-slim, installs Django + psycopg2,
copies djangoexact/ unmodified, and sets the entrypoint to the
run_computation_job management command. Runtime env vars are supplied
by the Cloud Run Job at dispatch time."
```

---

## Task 3: Simplify `deploy/cloudbuild-computation-job.yaml`

**Why:** The Cloud Build YAML still passes `--build-arg BASE_IMAGE=gcr.io/$PROJECT_ID/exact-webapp:latest`. Now that the Dockerfile is self-contained, the build-arg is unused and would fail if the referenced base image doesn't exist.

**Files:**
- Modify: `deploy/cloudbuild-computation-job.yaml`

- [ ] **Step 3.1: Replace the file contents**

Full new content:

```yaml
# Cloud Build config for the computation-job image.
# Triggered by .github/workflows/deploy.yaml on push to a wired
# environment (currently `review`). Invoke from repo root with:
#   gcloud builds submit --config=deploy/cloudbuild-computation-job.yaml \
#     --substitutions=COMMIT_SHA=$GITHUB_SHA --project=$PROJECT_ID .
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-f'
      - 'deploy/Dockerfile.computation_job'
      - '-t'
      - 'gcr.io/$PROJECT_ID/exact-computation-job:$COMMIT_SHA'
      - '-t'
      - 'gcr.io/$PROJECT_ID/exact-computation-job:latest'
      - '.'
images:
  - 'gcr.io/$PROJECT_ID/exact-computation-job:$COMMIT_SHA'
  - 'gcr.io/$PROJECT_ID/exact-computation-job:latest'
```

(`$PROJECT_ID` and `$COMMIT_SHA` are Cloud Build substitutions; the `--substitutions=COMMIT_SHA=...` arg in the CI step overrides `$COMMIT_SHA` so it ties to the GitHub SHA.)

- [ ] **Step 3.2: Validate the YAML parses**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('deploy/cloudbuild-computation-job.yaml'))" && echo "YAML OK"
```

Expected: `YAML OK`.

- [ ] **Step 3.3: Commit**

```bash
git add deploy/cloudbuild-computation-job.yaml
git commit -m "build(jobs): drop fake BASE_IMAGE build-arg from cloudbuild config

The self-contained Dockerfile no longer derives from a non-existent
exact-webapp container image, so the --build-arg becomes dead config.
Tags both :COMMIT_SHA and :latest unchanged."
```

---

## Task 4: Add image-build step to `.github/workflows/deploy.yaml`

**Why:** Nothing currently invokes the Cloud Build config. Without this step, the image is never built and `gcloud run jobs deploy` (Task 5) has nothing to point at.

**Files:**
- Modify: `.github/workflows/deploy.yaml`

- [ ] **Step 4.1: Re-read the current `Deploy` step's tail to locate the insertion point**

Run:
```bash
grep -n "gcloud app deploy\|gcloud app versions list\|Create Issue" .github/workflows/deploy.yaml
```

Expected: a `gcloud app deploy app.yaml ...` line, a `gcloud app versions list ...` line, and a `- name: Create Issue` step.

The new step goes **after** the existing `Deploy` step (the one ending with `gcloud app versions list ...`) and **before** the `Create Issue` step. The two new steps share the same `gcloud` auth (set up by the `google-github-actions/auth@v2` step above) and run in the same job, so no new auth wiring is needed.

- [ ] **Step 4.2: Insert the build step**

Edit `.github/workflows/deploy.yaml`. Find the existing block:

```yaml
        gcloud app versions list --service=${{ vars.SERVICE_NAME }} --project=${{ vars.PROJECT_ID }} --format="value(version.id)" --sort-by="~version.createTime" | tail -n +100 | xargs -r gcloud app versions delete -q

    - name: Create Issue
```

Insert the new step between them so the file becomes:

```yaml
        gcloud app versions list --service=${{ vars.SERVICE_NAME }} --project=${{ vars.PROJECT_ID }} --format="value(version.id)" --sort-by="~version.createTime" | tail -n +100 | xargs -r gcloud app versions delete -q

    - name: Build computation-job image
      if: vars.CLOUD_RUN_COMPUTATION_JOB_NAME != ''
      run: |
        gcloud builds submit \
          --config=deploy/cloudbuild-computation-job.yaml \
          --substitutions=COMMIT_SHA=${{ github.sha }} \
          --project=${{ vars.PROJECT_ID }} \
          .

    - name: Create Issue
```

- [ ] **Step 4.3: Validate the YAML parses**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yaml'))" && echo "YAML OK"
```

Expected: `YAML OK`.

- [ ] **Step 4.4: Do not commit yet**

Task 5 adds the second step in the same file; commit them together.

---

## Task 5: Add Cloud Run Job deploy step to `.github/workflows/deploy.yaml`

**Why:** This is the step that actually creates or updates the `exact-computation-job` Cloud Run Job resource in GCP, pointing it at the freshly-built image, granting it Cloud SQL access, and setting all the env vars Django needs at startup. `gcloud run jobs deploy` is idempotent — first run creates, subsequent runs update.

**Files:**
- Modify: `.github/workflows/deploy.yaml`

- [ ] **Step 5.1: Insert the deploy step after the build step**

Edit `.github/workflows/deploy.yaml`. The file should now contain (around the bottom):

```yaml
    - name: Build computation-job image
      if: vars.CLOUD_RUN_COMPUTATION_JOB_NAME != ''
      run: |
        gcloud builds submit \
          --config=deploy/cloudbuild-computation-job.yaml \
          --substitutions=COMMIT_SHA=${{ github.sha }} \
          --project=${{ vars.PROJECT_ID }} \
          .

    - name: Create Issue
```

Replace that block with:

```yaml
    - name: Build computation-job image
      if: vars.CLOUD_RUN_COMPUTATION_JOB_NAME != ''
      run: |
        gcloud builds submit \
          --config=deploy/cloudbuild-computation-job.yaml \
          --substitutions=COMMIT_SHA=${{ github.sha }} \
          --project=${{ vars.PROJECT_ID }} \
          .

    - name: Deploy/update Cloud Run Job
      if: vars.CLOUD_RUN_COMPUTATION_JOB_NAME != ''
      run: |
        gcloud run jobs deploy exact-computation-job \
          --image=gcr.io/${{ vars.PROJECT_ID }}/exact-computation-job:${{ github.sha }} \
          --region=${{ vars.CLOUD_RUN_REGION }} \
          --project=${{ vars.PROJECT_ID }} \
          --service-account=${{ vars.PROJECT_ID }}@appspot.gserviceaccount.com \
          --set-cloudsql-instances=${{ vars.DB_INSTANCE_CONNECTION }} \
          --memory=4Gi \
          --cpu=2 \
          --task-timeout=3600 \
          --max-retries=0 \
          --set-env-vars="^|^DB_ENGINE=${{ vars.DB_ENGINE }}|DB_HOST=/cloudsql/${{ vars.DB_INSTANCE_CONNECTION }}|DB_USER=${{ vars.DB_USERNAME }}|DB_PASSWORD=${{ secrets.DB_PASSWORD }}|DB_NAME=${{ vars.DB_NAME }}|DB_PORT=${{ vars.DB_PORT }}|SECRET_KEY=${{ secrets.SECRET_KEY }}|ALLOWED_HOSTS=${{ vars.ALLOWED_HOSTS }}|STORAGE_BUCKET=${{ vars.STORAGE_BUCKET }}|PROJECT_ID=${{ vars.PROJECT_ID }}|DJANGO_DEBUG=${{ vars.DJANGO_DEBUG }}|BRANCH_NAME=${{ github.ref_name }}|EMAIL_HOST=${{ vars.EMAIL_HOST }}|EMAIL_PORT=${{ vars.EMAIL_PORT }}|SMTP_USER_EMAIL=${{ vars.SMTP_USER_EMAIL }}|SMTP_USER_PASSWORD=${{ secrets.SMTP_USER_PASSWORD }}|FIREBASE_API_KEY=${{ vars.FIREBASE_API_KEY }}|FIREBASE_AUTH_DOMAIN=${{ vars.FIREBASE_AUTH_DOMAIN }}|FIREBASE_PROJECT_ID=${{ vars.FIREBASE_PROJECT_ID }}|FIREBASE_STORAGE_BUCKET=${{ vars.FIREBASE_STORAGE_BUCKET }}|FIREBASE_MESSAGING_SENDER_ID=${{ vars.FIREBASE_MESSAGING_SENDER_ID }}|FIREBASE_APP_ID=${{ vars.FIREBASE_APP_ID }}|FIREBASE_MEASUREMENT_ID=${{ vars.FIREBASE_MEASUREMENT_ID }}|FIREBASE_SERVICE_ACCOUNT=${{ secrets.FIREBASE_SERVICE_ACCOUNT }}|JOB_NOTIFICATIONS_ENABLED=True"

    - name: Create Issue
```

Key details to **not** alter:

- `^|^` — the leading `^X^` syntax tells gcloud to use `X` as the delimiter for `--set-env-vars`. Using `|` (instead of the default `,`) sidesteps commas inside values like `ALLOWED_HOSTS`.
- `DB_USER=${{ vars.DB_USERNAME }}` — deliberate key rename. `settings.py:164` reads `DB_USER`, but the GitHub var is named `DB_USERNAME`. If you copy-paste with `DB_USERNAME=...`, the Job will read `os.getenv("DB_USER", default="$DB_USERNAME")` → literal `"$DB_USERNAME"` → connection failure.
- `DB_HOST=/cloudsql/${{ vars.DB_INSTANCE_CONNECTION }}` — Cloud SQL unix-socket path. `psycopg2` treats hosts starting with `/` as socket directories. Pairs with `--set-cloudsql-instances` above.
- Every `FIREBASE_*` var is mandatory — `settings.py:305-322` re-raises if Firebase init fails at import time, so omitting any of them crashes the Job before `run_computation_job` even starts.

- [ ] **Step 5.2: Validate the YAML still parses**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yaml'))" && echo "YAML OK"
```

Expected: `YAML OK`.

- [ ] **Step 5.3: Diff the workflow file as a final eyeball check**

Run:
```bash
git --no-pager diff .github/workflows/deploy.yaml
```

Confirm: exactly two new steps added, both with the `if:` guard, no other changes.

- [ ] **Step 5.4: Commit Tasks 4 and 5 together**

```bash
git add .github/workflows/deploy.yaml
git commit -m "ci(jobs): build and deploy Cloud Run Job alongside App Engine

Adds two guarded steps after gcloud app deploy:
  1. gcloud builds submit to build the computation-job image via
     deploy/cloudbuild-computation-job.yaml, tagged with the commit SHA
     and :latest.
  2. gcloud run jobs deploy (idempotent create-or-update) for
     exact-computation-job in the env's GCP project, with Cloud SQL
     unix-socket connectivity, App Engine default SA, and the full
     env-var payload Django needs at import time (including FIREBASE_*).

Both steps are guarded by 'if: vars.CLOUD_RUN_COMPUTATION_JOB_NAME != \"\"'
so production and develop stay no-op until those environments are
populated."
```

---

## Task 6: Operator checklist — IAM grants in the `review` GCP project

These are not code changes. They must be applied **once** by an operator with project owner / IAM admin on the review GCP project. After applying, mark the checklist boxes done in the beads issue notes.

**No file changes.**

- [ ] **Step 6.1: Set shell variables for the review project**

```bash
export PROJECT_ID=<review-project-id>           # the actual GCP project id, e.g. exact-review-12345
export DEPLOY_SA=<value of GitHub vars.SERVICE_ACCOUNT for the review env>
```

- [ ] **Step 6.2: Grant App Engine SA permission to run the Cloud Run Job**

Run:
```bash
gcloud run jobs add-iam-policy-binding exact-computation-job \
  --region=europe-west1 \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/run.developer" \
  --project="${PROJECT_ID}"
```

This will fail with `NOT_FOUND` until the Cloud Run Job exists. That is expected on the very first attempt — re-run this after the first successful workflow run.

- [ ] **Step 6.3: Allow App Engine SA to act as itself**

```bash
gcloud iam service-accounts add-iam-policy-binding \
  "${PROJECT_ID}@appspot.gserviceaccount.com" \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser" \
  --project="${PROJECT_ID}"
```

- [ ] **Step 6.4: Grant deploy SA permission to manage Cloud Run Jobs**

```bash
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${DEPLOY_SA}" \
  --role="roles/run.admin"

gcloud iam service-accounts add-iam-policy-binding \
  "${PROJECT_ID}@appspot.gserviceaccount.com" \
  --member="serviceAccount:${DEPLOY_SA}" \
  --role="roles/iam.serviceAccountUser" \
  --project="${PROJECT_ID}"
```

- [ ] **Step 6.5: Confirm Cloud Build SA can push images**

```bash
gcloud projects get-iam-policy "${PROJECT_ID}" \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members~cloudbuild.gserviceaccount.com AND bindings.role~storage"
```

Expected: at least one binding contains `roles/storage.admin` or `roles/storage.objectAdmin`. If empty, run:

```bash
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/storage.admin"
```

- [ ] **Step 6.6: Record completion in beads**

```bash
bd update exact-django-webapp-89e --notes="IAM bindings applied to <PROJECT_ID> on $(date -u +%Y-%m-%dT%H:%MZ)."
```

---

## Task 7: Operator checklist — GitHub `review` environment variables

**No file changes.** Performed in the GitHub repo settings UI.

- [ ] **Step 7.1: Open the `review` environment settings**

Navigate to: `Settings → Environments → review` in the GitHub repo UI.

- [ ] **Step 7.2: Add `CLOUD_RUN_COMPUTATION_JOB_NAME`**

Under "Environment variables", click **Add variable**:

- Name: `CLOUD_RUN_COMPUTATION_JOB_NAME`
- Value: `projects/<review-project-id>/locations/europe-west1/jobs/exact-computation-job`

(Replace `<review-project-id>` with the same value used in Task 6.1.)

- [ ] **Step 7.3: Add `CLOUD_RUN_REGION`**

- Name: `CLOUD_RUN_REGION`
- Value: `europe-west1`

- [ ] **Step 7.4: Confirm no secret renames are required**

Verify these secrets already exist in the `review` environment (no action needed, just confirm):

- `DB_PASSWORD`
- `SECRET_KEY`
- `SMTP_USER_PASSWORD`
- `FIREBASE_SERVICE_ACCOUNT`

And these vars:

- `PROJECT_ID`, `DB_INSTANCE_CONNECTION`, `DB_ENGINE`, `DB_USERNAME`, `DB_NAME`, `DB_PORT`, `ALLOWED_HOSTS`, `STORAGE_BUCKET`, `DJANGO_DEBUG`, `EMAIL_HOST`, `EMAIL_PORT`, `SMTP_USER_EMAIL`, `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, `FIREBASE_STORAGE_BUCKET`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_APP_ID`, `FIREBASE_MEASUREMENT_ID`

If any are missing the workflow will fail loudly at the `gcloud run jobs deploy` step (gcloud rejects empty `--set-env-vars` values like `FOO=`).

- [ ] **Step 7.5: Record completion in beads**

```bash
bd update exact-django-webapp-89e --notes="GitHub review env vars CLOUD_RUN_COMPUTATION_JOB_NAME and CLOUD_RUN_REGION configured."
```

---

## Task 8: First-run + end-to-end verification

This is the live smoke test that proves the feature works on the deployed `review` site. Run only after Tasks 1-7 are complete and the PR has been merged into the `review` branch (or after pushing the branch if you push direct).

- [ ] **Step 8.1: Push and watch the workflow**

```bash
git push origin develop  # then open PR to review; or push to review directly per team policy
```

Open the GitHub Actions tab. Confirm the `Deploy` workflow runs for the `review` environment. Expected:

- `Deploy` step (existing) — succeeds.
- `Build computation-job image` step — **runs** (not skipped) and succeeds. Build duration 3-8 minutes.
- `Deploy/update Cloud Run Job` step — **runs** (not skipped) and succeeds.

If the build step is **skipped**, the `CLOUD_RUN_COMPUTATION_JOB_NAME` review env var is empty. Re-check Task 7.2.

- [ ] **Step 8.2: Re-apply the run.developer IAM binding now that the Job exists**

This was deferred from Task 6.2 because the Job didn't exist on first attempt. Run:

```bash
gcloud run jobs add-iam-policy-binding exact-computation-job \
  --region=europe-west1 \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/run.developer" \
  --project="${PROJECT_ID}"
```

Expected: returns the updated IAM policy.

- [ ] **Step 8.3: Inspect the Cloud Run Job resource**

```bash
gcloud run jobs describe exact-computation-job \
  --region=europe-west1 \
  --project="${PROJECT_ID}" \
  --format="yaml(spec.template.spec.template.spec.containers[0].image, spec.template.spec.template.spec.containers[0].env[].name, spec.template.spec.template.spec.serviceAccountName)"
```

Expected:
- `image:` ends with `:<git-sha-of-the-deploy>`
- env name list contains `DB_USER`, `DB_HOST`, `SECRET_KEY`, all eight `FIREBASE_*` keys, `STORAGE_BUCKET`, `JOB_NOTIFICATIONS_ENABLED`.
- `serviceAccountName: <PROJECT_ID>@appspot.gserviceaccount.com`

- [ ] **Step 8.4: Dispatch a real job from the deployed `review` site**

Log into the deployed `review` admin-scripts site as a staff user. Navigate to **Compile Scenarios**. Add a change for a (module_type, attribute, from→to) combination that has no existing `ChangeRecord` rows (a known gap — pick one whose computation has never been run). Click **Run scenario**. The UI should report a gap and offer an **Enqueue computation** button. Click it.

Expected: page shows "Job #N enqueued" or similar (per `partials/job_enqueued.html`).

- [ ] **Step 8.5: Confirm the dispatch happened on the App Engine side**

In Cloud Logging for App Engine (Logs Explorer, resource type `gae_app`), filter for `"Dispatched Cloud Run Job for job"`. Expect one log line per enqueue, of the form:

```
Dispatched Cloud Run Job for job N: projects/.../executions/exact-computation-job-xxxxx
```

If you see `"google-cloud-run not installed"` instead: Task 1's dep was not picked up by App Engine — re-trigger the workflow or check `app deploy` succeeded.

If you see `PermissionDenied: 403 ... Permission 'run.jobs.runWithOverrides' denied`: Task 6.2 / Step 8.2 IAM binding is missing.

- [ ] **Step 8.6: Confirm the Cloud Run execution started**

```bash
gcloud run jobs executions list \
  --job=exact-computation-job \
  --region=europe-west1 \
  --project="${PROJECT_ID}" \
  --limit=3
```

Expected: at least one execution with status `Running` or `Succeeded`, started within the last few minutes.

- [ ] **Step 8.7: Watch progress in the jobs panel**

In the deployed `review` site, open the Jobs panel (`/admin-scripts/jobs/`). The new job should show as `Running`, with `progress` ticking up via the management command's `_update_progress` callback.

- [ ] **Step 8.8: Confirm completion**

Expected within the task timeout (1h):

- Job status flips to `Completed`.
- The GCS `STORAGE_BUCKET` for the review env contains the new CSV artifact under whatever path `DataManager.save_data` writes to.
- `ChangeRecord` rows appear for the (module_type, attribute, from, to) combination.
- A repeat **Run scenario** click on the same combination returns statistics, not a gap.

- [ ] **Step 8.9: Confirm idempotent re-deploy**

Trigger a second workflow run (push a no-op commit, e.g. update a comment):

```bash
git commit --allow-empty -m "chore: re-trigger deploy to verify idempotency"
git push
```

Expected: workflow succeeds. `gcloud run jobs describe ...` (Step 8.3) shows the new `:<sha>` image tag. No manual cleanup needed.

- [ ] **Step 8.10: Close the beads issue and the loop**

```bash
bd close exact-django-webapp-89e --reason="Cloud Run Job provisioned in review; first end-to-end execution succeeded."
```

---

## Acceptance criteria recap

(Mirrors the spec — use as the PR-ready checklist.)

1. `git diff main` touches exactly four repo files: `djangoexact/requirements.txt`, `deploy/Dockerfile.computation_job`, `deploy/cloudbuild-computation-job.yaml`, `.github/workflows/deploy.yaml`.
2. The GitHub `review` environment carries `CLOUD_RUN_COMPUTATION_JOB_NAME` and `CLOUD_RUN_REGION`.
3. Four IAM bindings applied in the review GCP project (Steps 6.2 → 8.2, 6.3, 6.4 ×2).
4. End-to-end happy path (Steps 8.4-8.8) succeeds for one real scenario gap.
5. Idempotent re-deploy (Step 8.9) succeeds.
6. Pushing to `main` or `develop` does not attempt to build or deploy the Cloud Run Job (both new workflow steps are skipped — the `if:` guard does its job).
