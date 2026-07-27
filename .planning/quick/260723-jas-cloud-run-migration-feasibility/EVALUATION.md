# App Engine to Cloud Run: Migration Feasibility

**Date:** 2026-07-23
**Quick task:** 260723-jas
**Status:** Evaluated, no code changed. Recommendation below awaits a go/no-go.
**Scope:** the web API service only. The existing Cloud Run *Jobs* (compute + async report/copy) are already on Cloud Run and are not in question.

## Verdict

**Technically feasible, and most of the hard work is already done and running in production.** The blocking risk is not code, it is the ingress/hostname change, which is FAO IT territory.

**Recommendation: yes, but sequence it.** Do the Secret Manager work first (on App Engine), finish the async-jobs milestone, then move the service. Do not run this as a standalone infrastructure project ahead of the current hardening milestone.

## Current state, verified

| Aspect | Today |
|---|---|
| Runtime | App Engine Standard `python311`, `instance_class: F4_1G`, `automatic_scaling: min_idle_instances: 1` (`djangoexact/app.yaml`) |
| Entrypoint | `gunicorn -b :$PORT -w 4 main:app --timeout 120`, `main.py` re-exports `djangoexact.wsgi.application` |
| Static files | Served by the App Engine handler `- url: /static → static_dir: static/`; `collectstatic` runs on the CI runner before `gcloud app deploy` |
| Database | `settings.py:146` branches on `GAE_APPLICATION`: on App Engine it uses the `/cloudsql/$DB_INSTANCE_CONNECTION` unix socket; otherwise it reads `DB_*` env vars |
| Secrets | `sed`-substituted by CI into both `app.yaml` and `settings.py` at deploy time. No Secret Manager anywhere |
| Warmup | `inbound_services: warmup` plus `path("_ah/warmup", warmup)` (`djangoexact/urls.py:30` → `api/views.py:260`, returns a bare 200) |
| Migrations | Run from the GitHub runner over `cloud-sql-proxy`, before `gcloud app deploy` |
| Already containerized | `deploy/Dockerfile.computation_job`: `python:3.11-slim`, full `requirements.txt`, `libpq5`, and the complete WeasyPrint runtime stack (Pango/Cairo/GDK-PixBuf/fontconfig/DejaVu/Liberation). Copies all of `djangoexact/`. Built with `docker build` on the runner and pushed to `gcr.io` (Cloud Build is blocked by an org policy on its staging bucket) |
| Cloud Run Job in prod | `exact-computation-job`, `--set-cloudsql-instances`, `--memory=4Gi --cpu=2 --task-timeout=3600`, SA `$PROJECT_ID@appspot.gserviceaccount.com` |

### App Engine coupling is minimal

A repo-wide search for App Engine SDK usage returns **zero** `google.appengine` imports. The entire coupling surface is three things:

1. the `os.getenv("GAE_APPLICATION")` branch in `settings.py`,
2. the `_ah/warmup` route,
3. `app.yaml` itself.

There is no local filesystem state to migrate: attachments and reports go straight to GCS through `google.cloud.storage` (`api/views.py`, `api/serializers.py`, `api/admin.py`), and the only disk writes are `tempfile.gettempdir()` scratch files (`api/reports/excel_manager.py:45`), which are in-memory tmpfs on both platforms.

### The Cloud Run Job already proves the container path works

The 2026-05-11 design note (`docs/superpowers/specs/2026-05-11-cloud-run-job-review-env-design.md`) explicitly reasoned that `GAE_APPLICATION` is unset on Cloud Run, so the job takes the env-var DB branch. That has been running in production since. The same image already carries every native dependency the web service needs, including the awkward ones (psycopg2 + WeasyPrint).

## Work items, ordered by risk

### 1. Ingress, domain and TLS — highest risk, not a code problem

App Engine gives you `*.appspot.com` plus whatever custom-domain mapping FAO has configured. Cloud Run needs either a Cloud Run domain mapping or an external HTTPS load balancer with a serverless NEG. Changing the API hostname cascades into `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `BACKEND_BASE_URL` (the emailed report download links, `api/services/report_links.py`), the WebApp frontend config, and possibly the Firebase authorized-domains list.

**Get an answer from FAO IT before committing to any date.** If a custom-domain path onto Cloud Run is not approved in this GCP project, stop here. Everything else is straightforward and pointless without an ingress route.

### 2. Secrets — the migration forces this, and you want it anyway

Today the Cloud Run Job's DB password and `SECRET_KEY` are read back out of the *deployed App Engine version*:

```
gcloud app versions describe "$LATEST" --format=json > /tmp/aev.json
... 'DB_PASSWORD': aev['DB_PASSWORD'], 'SECRET_KEY': aev['SECRET_KEY'] ...
```

The workflow comment explains why: GitHub Actions' YAML `env:` interpolation adds escaping that diverges from the `sed` path, adding two characters to any secret containing `$` or `\`, which breaks psycopg2 auth. App Engine is therefore the current source of truth for the job's credentials.

**Retire App Engine and that source disappears.** So the move hard-requires replacing the `sed`-into-`settings.py` templating with Secret Manager (`gcloud run deploy --set-secrets`). That is a real improvement on its own: it eliminates the `$`/`\` mangling bug class and stops writing plaintext credentials into `settings.py` on a CI runner. But it must land *in the same change*, not after.

### 3. Static files — medium, mechanical

The `- url: /static` handler goes away. Options: WhiteNoise (add to `requirements.txt` + `MIDDLEWARE`, run `collectstatic` in the Dockerfile), or push `collectstatic` output to GCS behind the load balancer.

WhiteNoise is the right call here. The source `static/` tree is 4 files / 616 KB; the bulk of `collectstatic` output is admin, `unfold`, `ckeditor` and `drf_yasg` assets, all small and cache-bustable. The admin panel, `public/` pages and `minitool` all need it, so this is not optional.

### 4. Concurrency and connection churn — medium, needs a deliberate choice

App Engine Standard automatic scaling caps concurrent requests per instance around 10, against 4 gunicorn workers on F4_1G (1 GB). Cloud Run defaults to 80 concurrent requests per instance.

`CONN_MAX_AGE = 0` (`settings.py`), so **every request opens and closes a Postgres connection**. Raising per-instance concurrency 8x directly multiplies Cloud SQL connection churn. Set `--concurrency` explicitly (start at 8 to 16 to mirror current behaviour) and revisit `CONN_MAX_AGE` separately. Size `--cpu`/`--memory` to at least match F4_1G; 1 vCPU / 1 GiB will not comfortably render WeasyPrint PDFs on the synchronous path (the job uses 2 CPU / 4 GiB for exactly that reason).

### 5. Cold start and warmup — low

`_ah/warmup` becomes dead. Replace with `--min-instances=1` (the direct analogue of `min_idle_instances: 1`) plus `--cpu-boost`; both are GA. Keep the `warmup` view as a plain health endpoint or wire it to a startup probe.

### 6. Request timeout — a win

App Engine Standard automatic scaling caps a request at 10 minutes; gunicorn is additionally pinned to `--timeout 120`. Cloud Run allows up to 60 minutes per request. This matters less now that report generation is moving async, but it removes a ceiling that has bitten before.

### 7. Deploy workflow — low

Replace `gcloud app deploy` and the `gcloud app versions list | tail -n +100 | xargs gcloud app versions delete` pruning with a single `gcloud run deploy`. Cloud Run manages revisions itself and gives real traffic splitting and instant rollback, which App Engine version juggling does not do as cleanly. The `cloud-sql-proxy` + `migrate` + `check --deploy` steps are platform-independent and stay as they are.

### 8. Cost — check, do not assume

F4_1G with `min_idle_instances: 1` bills a resident instance around the clock. Cloud Run with `--min-instances=1` also bills idle, but at the reduced idle rate with finer-grained CPU/memory sizing. Likely neutral to modestly cheaper. Not a reason to move on its own; worth pricing before the go/no-go so nobody is surprised.

## What does not change

Database, schema, migrations and fixtures. GCS buckets and attachment handling. Firebase auth. The public API contract. The existing Cloud Run Job (it keeps working; it only needs its env sourced from Secret Manager instead of from App Engine).

**There is no data migration.** That is the single biggest reason this is low-risk: you can stand up the Cloud Run service against the *same* Cloud SQL instance and the *same* bucket, point a test hostname at it, validate against real data, and flip. Both platforms can serve simultaneously during the cutover.

## Effort estimate

| Item | Estimate |
|---|---|
| Web-service Dockerfile (fork `Dockerfile.computation_job`, add `collectstatic`, swap CMD to gunicorn) | a few hours |
| WhiteNoise wiring | a few hours |
| Secret Manager migration (removes the `sed`-into-`settings.py` pipeline, rewires the Job too) | 1 to 2 days |
| `deploy.yaml` rewrite | half a day |
| Concurrency / resource tuning + load validation | 1 day |
| Ingress, domain, TLS | **unknown, FAO IT dependent** |

Code side: roughly 3 to 4 days. Total schedule is dominated by item 1.

## Opinion

Do it, but not right now, and not as its own project.

It is feasible and the genuinely hard part, containerizing *this* codebase with WeasyPrint and psycopg2, is already solved and running. What holds me back is that it buys little today. The things App Engine actually costs you (the 10-minute request cap, weak traffic splitting, the `sed`-secret pipeline) are either already being engineered around via async jobs, or fixable in place without touching the platform.

The real payoff is consolidation: one image, one build, one runtime for both the API and the jobs, instead of an App Engine deploy plus a separate container build plus the "read the secrets back out of App Engine" hack that exists *only* because the two platforms diverge. That is architectural hygiene, and it compounds with the current reliability milestone rather than competing with it.

Suggested sequence:

1. Finish the async report / project copy work (in flight, `exact-django-webapp-7xn`).
2. Move secrets to Secret Manager **while still on App Engine**. Highest value, lowest risk, and it severs the App Engine to Job credential coupling that would otherwise make the platform move all-or-nothing.
3. In parallel, get a written answer from FAO IT on custom-domain mapping or an HTTPS LB in front of Cloud Run.
4. Only then do the service move. With steps 2 and 3 done it is a one-to-two day change plus validation, run side-by-side against the same database, with a hostname flip as the only cutover event.

If the answer at step 3 is no, drop the idea and spend the effort on the hardening milestone instead. Nothing about App Engine is currently blocking the product.
