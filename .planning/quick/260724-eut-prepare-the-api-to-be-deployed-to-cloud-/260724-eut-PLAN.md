---
phase: quick-260724-eut
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - djangoexact/requirements.txt
  - djangoexact/djangoexact/settings.py
  - deploy/Dockerfile.web_service
  - deploy/cloudrun-service.yaml
  - .github/workflows/deploy-cloudrun.yaml
  - djangoexact/docs/guides/cloud-run-deploy.md
autonomous: true
requirements:
  - CR-01
  - CR-02
  - CR-03
  - CR-04
  - CR-05
branch: feat/cloud-run-deploy

must_haves:
  truths:
    - "A push to review, or a manual dispatch, builds a web-service image, migrates the review database, and replaces a Cloud Run service, without any change to what the App Engine pipeline deploys."
    - "The Cloud Run service serves /static/ from assets baked into the image by WhiteNoise, with no App Engine static handler and no GCS static bucket."
    - "The Cloud Run service reaches the same Cloud SQL instance over the /cloudsql unix socket, using the same DB_USER value the computation Job already uses in production."
    - "No secret value (DB_PASSWORD, SECRET_KEY, SMTP_USER_PASSWORD, FIREBASE_SERVICE_ACCOUNT) is written to a CI log line, to the checkout, or to a Docker image layer."
    - "djangoexact/app.yaml and .github/workflows/deploy.yaml are byte-identical to their pre-change state, and the two settings.py / requirements.txt edits are inert on App Engine."
    - "Every environment variable settings.py reads at runtime is present in the Cloud Run service spec, so no setting silently resolves to its literal placeholder default."
  artifacts:
    - deploy/Dockerfile.web_service
    - deploy/cloudrun-service.yaml
    - .github/workflows/deploy-cloudrun.yaml
    - djangoexact/docs/guides/cloud-run-deploy.md
    - djangoexact/requirements.txt
    - djangoexact/djangoexact/settings.py
  key_links:
    - "settings.py:172 reads DB_USER, but the repo variable is named DB_USERNAME. The service spec must emit an env entry NAMED DB_USER whose VALUE is the $DB_USERNAME placeholder, or psycopg2 authenticates as the literal string placeholder and fails."
    - "settings.py:146 branches on GAE_APPLICATION, which Cloud Run never sets, so the env-var DATABASES branch at :168 applies. DB_HOST must therefore be the /cloudsql socket path built from DB_INSTANCE_CONNECTION, matching the cloudsql-instances annotation."
    - "Cloud Run injects PORT at run time. The Dockerfile CMD must be shell form so the variable expands; the exec form would pass the literal through to gunicorn."
    - "collectstatic imports settings.py, which hard-fails at :53 without SECRET_KEY or DEBUG and at :319-336 without a base64 JSON service account that firebase_admin can parse. The build supplies throwaway values for both over a BuildKit secret mount."
    - "MIDDLEWARE[0] stays django.middleware.security.SecurityMiddleware and WhiteNoiseMiddleware becomes MIDDLEWARE[1]. On App Engine the `- url: /static` handler intercepts first, so the middleware never serves a request there."
---

<objective>
Add a complete, standalone Cloud Run deployment path for the EX-ACT web API, additively,
so the review environment can be validated on Cloud Run while App Engine keeps serving
production unchanged.

Purpose: the container path for this codebase is already proven by the production
computation Job, but the web service has no image, no static file story off App Engine,
and no Cloud Run pipeline. This closes those three gaps and documents the human setup
required before the first run, so the eventual production cutover becomes a hostname flip
rather than a project.

Output:
- `whitenoise` pinned in requirements.txt and its middleware wired into settings.py (CR-01)
- `deploy/Dockerfile.web_service`, a gunicorn web-service image with collectstatic (CR-02)
- `deploy/cloudrun-service.yaml`, a Knative service template with the full env set (CR-03)
- `.github/workflows/deploy-cloudrun.yaml`, review-only, with full pipeline parity (CR-04)
- `djangoexact/docs/guides/cloud-run-deploy.md`, the operator setup guide (CR-05)

Non-goals, restated so the executor does not drift: no production cutover, no ingress or
custom-domain work, no Secret Manager, no change to the existing Cloud Run Jobs, no change
to `djangoexact/app.yaml` or `.github/workflows/deploy.yaml`.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/quick/260724-eut-prepare-the-api-to-be-deployed-to-cloud-/260724-eut-CONTEXT.md
@.planning/quick/260723-jas-cloud-run-migration-feasibility/EVALUATION.md
@CLAUDE.md
@.claude/CLAUDE.md

Read for reference, do not modify:
@.github/workflows/deploy.yaml
@djangoexact/app.yaml
@deploy/Dockerfile.computation_job
</context>

<verified_facts>
Everything below was checked against the working tree on 2026-07-24. The executor should
build on these rather than re-deriving them, but must not contradict them silently.

1. **settings.py needs no sed.** Every setting reads from the environment with a
   `$PLACEHOLDER` string only as a fallback default: `:36` BACKEND_BASE_URL, `:53`
   SECRET_KEY, `:63` ALLOWED_HOSTS, `:67` CORS_ALLOWED_ORIGINS, `:170-175` DB_*,
   `:312-316` EMAIL_* and SMTP_*, `:321-329` FIREBASE_*, `:347-348` STORAGE_BUCKET and
   DEFAULT_FROM_EMAIL. Build the image from unsubstituted source.

2. **`GAE_APPLICATION` is unset on Cloud Run**, so the env-var DATABASES branch at
   `settings.py:168` applies. Proven by the production computation Job.

3. **`STATIC_ROOT` is the source `static/` directory** (`settings.py:236`:
   `STATIC_ROOT = os.path.join(BASE_DIR, "static/")`, `STATIC_URL = "/static/"`).
   `STATICFILES_DIRS` is commented out at `:239-241`, so collectstatic gathers only app
   assets (admin, unfold, ckeditor, drf_yasg, rest_framework) into that same directory
   alongside the four committed source files. This is pre-existing and stays as it is.

4. **`MIDDLEWARE` starts at `settings.py:106`** with
   `"django.middleware.security.SecurityMiddleware"` at `:107`.

5. **requirements.txt** has `Django==5.2.14` (line 9) and `gunicorn==22.0.0` (line 19).
   It has no whitenoise. Lines 1 to 51 are roughly alphabetical, lines 52 to 71 are
   appended chronologically; new pins go at the end.

6. **`DB_USERNAME` versus `DB_USER`.** `app.yaml:24` exports `DB_USERNAME`, but
   `settings.py:172` reads `DB_USER`. The computation Job bridges this at
   `deploy.yaml:419` with `'DB_USER': aev['DB_USERNAME']`. The Cloud Run service spec must
   do the same bridging.

7. **Cloud Build is bypassed deliberately** (`deploy.yaml:353-357`): an org policy blocks
   the deploy service account from the Cloud Build staging bucket. Build with docker on
   the runner.

8. **The Django root is `djangoexact/`.** The computation Job Dockerfile builds from
   repo-root context and does `COPY djangoexact/ /app/`.

9. **NEW, verified this session: settings.py cannot be imported without a valid
   `FIREBASE_SERVICE_ACCOUNT`.** `base64.b64decode("$FIREBASE_SERVICE_ACCOUNT")` raises
   `binascii.Error: Incorrect padding`, and `settings.py:335-336` re-raises it as
   `Exception("Firebase config not found: ...")`. It also needs `SECRET_KEY` or
   `DJANGO_DEBUG=True` (`:53-60`). This directly gates `collectstatic` inside the Docker
   build. A throwaway RSA service account was generated and confirmed accepted by
   `firebase_admin.initialize_app(credentials.Certificate(...))` with no network access,
   using the same construction the CI test job already uses at `deploy.yaml:61-89`.

10. **NEW, verified this session: `STATICFILES_STORAGE` no longer exists in Django 5.2.**
    `django.conf.global_settings` in the repo's `.venv` (Django 5.2.14) has no
    `STATICFILES_STORAGE` attribute; the setting was deprecated in 4.2 and removed in 5.1.
    `STORAGES` is the only remaining mechanism. See the storage decision below.

11. **NEW, verified this session: `.env*` is gitignored** (`.gitignore:180`), so
    `djangoexact/djangoexact/.env.review` exists on developer machines but never in a CI
    checkout or a build context. Setting `APP_MODE` at container run time would therefore
    load nothing. This informs the BRANCH_NAME choice below.

12. **NEW, verified this session:** `djangoexact/scripts/invalidate_results_cache.py`
    exists, so `manage.py runscript invalidate_results_cache` is valid. The `_ah/warmup`
    route (`djangoexact/urls.py:30`) stays in place and is harmless on Cloud Run.

13. **NEW, verified this session:** there is no `.dockerignore` in the repo. See the
    deliberate non-change note below.
</verified_facts>

<decisions>
Decisions taken under "Claude's Discretion" in CONTEXT.md, plus the two the deliverables
asked to be justified.

**D-A. No `STORAGES` change. Middleware only.**
Do not add a `STORAGES` block and do not attempt to add `STATICFILES_STORAGE` (fact 10:
it does nothing on Django 5.2). Reasons, in order of weight:
- Any `STORAGES` change is global, so it would also change what the existing App Engine
  runner-side `collectstatic` (`deploy.yaml:337`) emits and uploads. That breaches the
  additive-only constraint.
- `CompressedManifestStaticFilesStorage` hash-renames files into `STATIC_ROOT`, which here
  is the committed source `static/` tree (fact 3). Repeated runs would accumulate hashed
  copies of already-hashed files in a tracked directory.
- The manifest pass hard-fails on any unresolvable `url()` reference in third-party CSS
  (ckeditor, unfold, drf_yasg). That failure cannot be reproduced in this sandbox, and it
  would break both pipelines, not just the new one.
WhiteNoise's middleware alone still serves `STATIC_ROOT` with correct content types and
sane cache headers. Compression is a follow-up, and it should land together with moving
`STATIC_ROOT` to a dedicated `staticfiles/` directory, not before.

**D-B. Fork the Dockerfile, do not share stages.**
`deploy/Dockerfile.web_service`, a near-copy of `deploy/Dockerfile.computation_job`. Docker
cannot share stages across files without a published base image, and converting the
existing file into a multi-target build would change the computation Job's build inputs,
which this change may not do. The duplication is called out in both file headers and in the
guide as an explicit follow-up (unify behind one base image once Cloud Run is proven). A
verify gate compares the two runtime apt package lists so they cannot drift silently.

**D-C. Resource sizing.**
`containerConcurrency: 10`, mirroring App Engine Standard's roughly 10 concurrent requests
per instance against 4 gunicorn workers, and sitting inside the 8 to 16 band CONTEXT.md
asked for. `CONN_MAX_AGE = 0` makes every request a new Postgres connection, so Cloud Run's
default of 80 would multiply connection churn eightfold.
`cpu: 2`, `memory: 4Gi`, matching the computation Job, which is sized that way precisely
because of WeasyPrint. The web service still renders PDFs synchronously, and an OOM on
Cloud Run kills the container and every in-flight request with it, which is strictly worse
than App Engine's per-instance behaviour. Cost at review scale with `minScale: 0` is
negligible.
`minScale: 0` (review does not need a warm instance, unlike App Engine's
`min_idle_instances: 1`), `maxScale: 4`, `timeoutSeconds: 300`. All of these are repo
variable driven with those numbers as defaults.

**D-D. Entrypoint ported unchanged.**
`gunicorn -b :$PORT -w 4 main:app --timeout 120`, exactly as `app.yaml:5`, plus access and
error logging to stdout and stderr (App Engine supplies request logging for free, Cloud Run
does not). Worker count and timeout are overridable by env var, defaulting to 4 and 120.
`gunicorn --timeout 120` stays the effective request ceiling; Cloud Run's 300 is headroom
so that a gunicorn worker timeout surfaces as gunicorn's own error rather than a platform
504.

**D-E. `BRANCH_NAME`, not `APP_MODE`, in the container.**
Mirror the computation Job (`deploy.yaml:430`): set `BRANCH_NAME=review` and leave
`APP_MODE` unset at run time. `APP_MODE` would trigger the `.env.{mode}` load at
`settings.py:28`, and that file is never present in a CI-built image (fact 11).
`BRANCH_NAME=review` makes `FRONTEND_URL` resolve to `https://exact.review.fao.org`
(`settings.py:32`), which is correct for review and is what the Job already does.
Note this is a deliberate divergence from App Engine review, which sets neither variable
and therefore resolves `FRONTEND_URL` to the production frontend. That is a pre-existing
quirk on the App Engine side and is not fixed here.
`APP_MODE=review` IS set for the runner-side `check --deploy` step, matching
`deploy.yaml:253`.

**D-F. Single-quoted YAML scalars for env values, plus an apostrophe guard.**
This is the most consequential small decision in the plan. `envsubst` is pure text
substitution, so the quoting style of the template decides how a secret survives into the
manifest. Double-quoted YAML interprets backslash escapes, and `deploy.yaml:370-381`
records that these secrets do contain `$` and backslash characters. Single-quoted YAML
treats backslash and `$` literally; only an embedded apostrophe is special. The template
therefore uses single-quoted scalars for every env value, and the workflow fails the render
step, by variable NAME only, if any required value contains an apostrophe. This closes the
same bug class the heredoc `$GITHUB_ENV` pattern exists to close.

**D-G. Render to /tmp, never into the checkout, and never print it.**
The org template substitutes `service.yaml` in place and then prints it. Both halves are
changed: the template lives at `deploy/cloudrun-service.yaml` and renders to
`/tmp/service.yaml`, which is deleted after `gcloud run services replace`. Rendering into
the checkout would leave a secret-laden file where a later step or an artifact upload could
capture it. The dropped print is replaced by two checks that leak nothing: a
`yaml.safe_load` parse, and a required-variable emptiness check that reports names only.
This is the security-motivated deviation CONTEXT.md called for, made stronger.

**D-H. The `subst()` helper is not carried over.**
The org helper ends with a trailing
`sed -i 's|\\n|\n|g;s|\\t|\t|g;s|\\\\$|\\|g'` unescape pass. Applied to a rendered manifest
it would rewrite any literal backslash sequence inside a secret, which is exactly the
corruption this whole pattern exists to prevent. The template needs no `\n` expansion, so
the helper collapses to a plain `envsubst` redirect. This is a fifth deviation from the org
template beyond the four CONTEXT.md lists; it is a refinement of the same security
rationale as the dropped print, and it is called out in the workflow comments.

**D-I. Distinct variable names where the existing repo already uses the name.**
The blanket `toJson(vars)` dump means every existing repo variable lands in the job
environment. Three collisions matter:
- `SERVICE_NAME` is already the App Engine service name. The Cloud Run service uses
  `CLOUD_RUN_SERVICE_NAME`, defaulting to `exact-api`. The org template's
  "fall back to the repository name" behaviour is not carried over, because that would
  silently name the service `exact-django-webapp`.
- `DB_HOST` is already the value App Engine seds into settings.py. The manifest never
  references it; it builds `/cloudsql/$DB_INSTANCE_CONNECTION` directly, as the Job does.
  The runner-side migrate step overrides `DB_HOST=127.0.0.1` for the proxy.
- `REGION` is not introduced; the existing `CLOUD_RUN_REGION` variable is reused.
`ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` and `BACKEND_BASE_URL` are read through
`CLOUDRUN_`-prefixed overrides that fall back to the App Engine values, so tightening or
widening the Cloud Run service cannot touch App Engine.

**D-J. Deliberate non-change: no `.dockerignore`.**
Adding one would change the build context of the existing computation Job image as well.
In CI the ignored paths (`node_modules/`, `.venv`, `.env*`) do not exist in the checkout,
so it would be a no-op there and a behaviour change only for local ad-hoc builds. Noted as
a follow-up in the guide, not done here.
</decisions>

<recommendations>
Surfaced for the human, deliberately NOT acted on in this plan.

**R-1. `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` for the review Cloud Run service.**
The service's `*.run.app` hostname is not knowable until the service first deploys, because
it embeds the project number. So the first deploy of a service whose `ALLOWED_HOSTS` was
inherited from App Engine will return `400 Bad Request` with `DisallowedHost` on every
request, even though the deploy itself succeeded. Three options:

| Option | What it means | Trade-off |
|---|---|---|
| Two-pass (recommended) | Deploy once, read the URL from the job summary, set `CLOUDRUN_ALLOWED_HOSTS` and `CLOUDRUN_CORS_ALLOWED_ORIGINS` repo variables, re-run | One throwaway first run. Fully explicit. Nothing widened. |
| Subdomain wildcard | Add `.run.app` to `CLOUDRUN_ALLOWED_HOSTS`. Django treats a leading dot as a subdomain wildcard | One pass, but the service accepts any `*.run.app` Host header. Cloud Run only routes its own hostname to the service, so the practical exposure is low, and it is still a real widening. |
| Precompute | Look up the project number and construct the URL before the first deploy | One pass, but the URL format is a Cloud Run implementation detail and has changed before. |

The workflow is built so that either of the first two is a repo-variable change with no code
edit. The plan does not choose; the guide documents all three and the first-run checklist
assumes the two-pass path. The same applies to `CLOUDRUN_BACKEND_BASE_URL`, which feeds the
emailed report download links (`api/services/report_links.py`); leaving it empty soft
disables that email rather than breaking the deploy.

**R-2. Double migration on review.** CONTEXT.md residual risk 1, accepted. A push to
`review` now triggers two pipelines that both run `migrate` against the same database. The
new workflow carries its own `concurrency` group so it does not race itself, but it cannot
serialise against `deploy.yaml` without editing `deploy.yaml`. If it proves noisy, give both
workflows the same `concurrency.group`; that is a one-line change to each and is the moment
to revisit the additive-only constraint.

**R-3. Follow-ups, in the order they should be picked up.** Unify the two Dockerfiles behind
a shared published base image; add a `.dockerignore`; move `STATIC_ROOT` off the source
`static/` tree and then enable WhiteNoise compression; run the container as a non-root user;
retire the "read credentials back out of App Engine" hack in `deploy.yaml:403-423` once the
heredoc env pattern proven here can be applied to the Job.
</recommendations>

<package_legitimacy_audit>
One package-manager install is introduced. There is no RESEARCH.md for this quick task, so
the audit was performed live against the registry during planning.

| Package | Pin | Registry evidence (checked 2026-07-24) | Verdict |
|---|---|---|---|
| whitenoise | 6.12.0 | pypi.org/pypi/whitenoise/json: author David Evans, maintainer Adam Johnson, repository github.com/evansd/whitenoise, docs whitenoise.readthedocs.io, requires-python >=3.10, latest 6.12.0 released 2026-02-27, not yanked, prior releases 6.11.0 / 6.10.0 / 6.9.0 / 6.8.2 form a continuous history | VERIFIED |

Middleware placement was confirmed against the upstream docs
(github.com/evansd/whitenoise docs/index.md): `WhiteNoiseMiddleware` goes immediately after
`django.middleware.security.SecurityMiddleware`. No blocking human checkpoint is required
because the package resolved to a real, long-lived, non-yanked PyPI project with a matching
source repository. If the executor cannot install `whitenoise==6.12.0` for any reason, stop
and escalate rather than substituting a different version or package.
</package_legitimacy_audit>

<tasks>

<task type="auto">
  <name>Task 1 (CR-01): Pin WhiteNoise and wire its middleware</name>
  <files>djangoexact/requirements.txt, djangoexact/djangoexact/settings.py</files>
  <action>
Append `whitenoise==6.12.0` as the final line of `djangoexact/requirements.txt`, matching the
chronological-append convention of lines 52 to 71 (verified fact 5). Do not reorder or
reformat anything else in that file.

In `djangoexact/djangoexact/settings.py`, insert `"whitenoise.middleware.WhiteNoiseMiddleware",`
into the `MIDDLEWARE` list at index 1, immediately after
`"django.middleware.security.SecurityMiddleware"` (verified fact 4, and confirmed against the
upstream WhiteNoise docs). Nothing else in the list moves.

Add a short comment above the new entry, in the repo's existing comment voice, recording
two things: that it serves `STATIC_ROOT` for the Cloud Run service, and that it stays inert
on App Engine because the `- url: /static` handler in `app.yaml:10-11` intercepts those
requests before Django sees them. Keep the comment to three lines or fewer. The comment must
not contain the name of the Django storages setting at the start of a line, and it must not
contain an em-dash.

Per D-A, do NOT add a `STORAGES` block, do NOT add `STATICFILES_STORAGE` (it is a no-op on
Django 5.2, verified fact 10), and do NOT touch `STATIC_ROOT` or `STATIC_URL`.

Commit as `feat(deploy): add whitenoise for Cloud Run static file serving`.
  </action>
  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp

# 1. Pin present exactly once, exact version.
test "$(grep -c '^whitenoise==6.12.0$' djangoexact/requirements.txt)" -eq 1

# 2. settings.py still compiles.
.venv/bin/python -m py_compile djangoexact/djangoexact/settings.py

# 3. MIDDLEWARE order, checked by AST so no import and no database are needed.
.venv/bin/python - <<'PY'
import ast
tree = ast.parse(open('djangoexact/djangoexact/settings.py').read())
mw = next(n.value for n in tree.body
          if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'MIDDLEWARE')
vals = [e.value for e in mw.elts]
assert vals[0] == 'django.middleware.security.SecurityMiddleware', vals[:2]
assert vals[1] == 'whitenoise.middleware.WhiteNoiseMiddleware', vals[:2]
assert len(vals) == 15, f'middleware count changed: {len(vals)}'
print('OK middleware order and count')
PY

# 4. D-A honoured: no module-level storages assignment introduced.
test "$(grep -cE '^[[:space:]]*STORAGES[[:space:]]*=' djangoexact/djangoexact/settings.py)" -eq 0

# 5. Static path settings untouched.
test "$(grep -c 'STATIC_ROOT = os.path.join(BASE_DIR, "static/")' djangoexact/djangoexact/settings.py)" -eq 1

# 6. No em-dash introduced (U+2014), expressed as a PCRE escape.
! grep -rnP '\x{2014}' djangoexact/requirements.txt djangoexact/djangoexact/settings.py

# 7. App Engine artefacts untouched.
git diff --quiet HEAD -- djangoexact/app.yaml .github/workflows/deploy.yaml
    </automated>
  </verify>
  <done>
`whitenoise==6.12.0` is the last line of requirements.txt. `MIDDLEWARE` has exactly 15
entries with SecurityMiddleware first and WhiteNoiseMiddleware second. No storages setting
was added, `STATIC_ROOT` is unchanged, and `app.yaml` and `deploy.yaml` show no diff.
  </done>
</task>

<task type="auto">
  <name>Task 2 (CR-02): Web-service Dockerfile</name>
  <files>deploy/Dockerfile.web_service</files>
  <action>
Create `deploy/Dockerfile.web_service` following the skeleton in `<reference_specs>` section
`SPEC-A` exactly. It is a near-copy of `deploy/Dockerfile.computation_job` per D-B, with three
differences and nothing else.

Difference 1, the collectstatic step. It must run in the `runtime` stage, after
`COPY --from=builder /install /usr/local` and after `COPY djangoexact/ /app/`, because it
needs both the installed dependencies and the application code. It must supply
`DJANGO_DEBUG=True` and a `FIREBASE_SERVICE_ACCOUNT` value read from a BuildKit secret mount
`id=build_firebase_cred,required=true`, because settings.py refuses to import without both
(verified fact 9). Use `required=true` so a missing secret produces a clear BuildKit error
rather than a confusing `cat` failure. Run `python manage.py collectstatic --noinput` with no
other flags; if a Django system check turns out to be noisy in CI, `--skip-checks` is the
sanctioned fallback, but do not add it pre-emptively.

Difference 2, the entrypoint. `ENV PORT=8080`, `EXPOSE 8080`, and a CMD in SHELL form, not
exec form, per D-D and the key_link on PORT. The exec form would pass the placeholder to
gunicorn literally. Prefix the command with `exec` so gunicorn becomes PID 1 and receives
SIGTERM during a revision drain.

Difference 3, the header comment. Record: what the image is for, that the build context is
the repo root, the exact `docker build` invocation including the secret flag, that it is a
deliberate fork of `Dockerfile.computation_job` per D-B, and that the base image, builder
stage and runtime apt list must be kept in sync with that file.

Keep the runtime apt package list byte-identical to the computation Job's list. A verify gate
compares them. Do not add a `.dockerignore` (D-J). Do not add a non-root USER (follow-up).

Commit as `feat(deploy): add Cloud Run web service Dockerfile`.
  </action>
  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp

# 1. File exists with the BuildKit syntax directive on line 1.
head -1 deploy/Dockerfile.web_service | grep -qx '# syntax=docker/dockerfile:1.6'

# 2. Runtime apt package list is identical to the computation job's.
pkgs() {
  awk '/AS runtime/,/rm -rf \/var\/lib\/apt\/lists/' "$1" \
    | grep -oE '^[[:space:]]+(lib[a-z0-9.+-]+|fonts-[a-z]+|fontconfig|shared-mime-info)[[:space:]]*\\?$' \
    | tr -d ' \\' | sort
}
diff <(pkgs deploy/Dockerfile.computation_job) <(pkgs deploy/Dockerfile.web_service)

# 3. Application code copied from the Django root, same as the job image.
grep -qx 'COPY djangoexact/ /app/' deploy/Dockerfile.web_service

# 4. collectstatic runs, behind a required BuildKit secret mount.
grep -q 'manage.py collectstatic --noinput' deploy/Dockerfile.web_service
grep -q 'type=secret,id=build_firebase_cred,required=true' deploy/Dockerfile.web_service

# 5. CMD is shell form (expands PORT), not exec form, and appears once.
#    grep -F is required: in BRE a dollar sign immediately before a brace is not
#    matched literally, so the plain-pattern form of this check silently fails.
test "$(grep -c '^CMD ' deploy/Dockerfile.web_service)" -eq 1
test "$(grep -c '^CMD \[' deploy/Dockerfile.web_service)" -eq 0
grep -E '^CMD ' deploy/Dockerfile.web_service | grep -qF '${PORT'
grep -E '^CMD ' deploy/Dockerfile.web_service | grep -q 'main:app'

# 6. The build-time throwaway credential is never a build arg (would persist in history).
test "$(grep -c 'ARG.*FIREBASE' deploy/Dockerfile.web_service)" -eq 0

# 7. No em-dash.
! grep -nP '\x{2014}' deploy/Dockerfile.web_service

# 8. The computation job Dockerfile is untouched.
git diff --quiet HEAD -- deploy/Dockerfile.computation_job
    </automated>
  </verify>
  <done>
`deploy/Dockerfile.web_service` exists, its runtime apt list diffs clean against
`Dockerfile.computation_job`, it runs collectstatic behind a required BuildKit secret mount,
its single CMD is shell form referencing `${PORT` and `main:app`, no FIREBASE build arg
exists, and `Dockerfile.computation_job` shows no diff.

Honest limitation: this sandbox has no Docker, so the image is not built here. First real
build happens in CI. The gates above are structural and catch the classes of error that
would otherwise only surface as a Cloud Run container start failure.
  </done>
</task>

<task type="auto">
  <name>Task 3 (CR-03): Knative service template</name>
  <files>deploy/cloudrun-service.yaml</files>
  <action>
Create `deploy/cloudrun-service.yaml` following `<reference_specs>` section `SPEC-B` exactly.
It is a `serving.knative.dev/v1` Service manifest with `$PLACEHOLDER` tokens for `envsubst`.

The env list is the crux of this task. It was cross-checked against three sources, and every
entry must be present or a setting silently resolves to its literal placeholder default:
- `djangoexact/app.yaml:19-34` env_variables (15 names)
- the computation Job env file at `deploy.yaml:411-449`
- every `os.getenv` and `os.environ.get` call in settings.py

Two mappings are load-bearing and easy to get wrong:
- The entry NAMED `DB_USER` takes the VALUE `$DB_USERNAME` (verified fact 6). An entry named
  `DB_USERNAME` would leave settings.py reading the literal placeholder.
- `DB_HOST` is `/cloudsql/$DB_INSTANCE_CONNECTION`, built inline, not `$DB_HOST` (D-I). It
  must agree with the `run.googleapis.com/cloudsql-instances` annotation.

Four settings that `app.yaml` does not carry, because App Engine seds them into settings.py
instead, must appear here: `EMAIL_HOST`, `EMAIL_PORT`, `SMTP_USER_EMAIL`,
`SMTP_USER_PASSWORD`. So must all eight `FIREBASE_*` values.

Do NOT add a `PORT` entry. Cloud Run reserves it and rejects a manifest that sets it.
Do NOT add `APP_MODE`; set `BRANCH_NAME` instead, per D-E.

Every env `value` uses a SINGLE-quoted YAML scalar, per D-F. Structural numeric fields
(`containerConcurrency`, `timeoutSeconds`) stay unquoted so they render as integers.

Annotations, per D-C: `minScale`, `maxScale`, `cloudsql-instances`,
`execution-environment: gen2` (full native-library compatibility for Pango and Cairo, and
what Cloud Run Jobs already run under), and `startup-cpu-boost`. Ingress `all` at the service
level. `serviceAccountName` is `$RUNTIME_SERVICE_ACCOUNT`, which the workflow defaults to the
same `$PROJECT_ID@appspot.gserviceaccount.com` identity the computation Job uses, so GCS and
Cloud SQL access behave identically.

Add a header comment block explaining that this is a template rendered by
`.github/workflows/deploy-cloudrun.yaml`, that the rendered output is written outside the
checkout and is never printed because it carries four secrets, and the DB_USER mapping trap.
Phrase the warning as a statement that the rendered manifest is not printed; do not write out
a shell command that would print it.

Commit as `feat(deploy): add Cloud Run service manifest template`.
  </action>
  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp

.venv/bin/python - <<'PY'
import yaml

doc = yaml.safe_load(open('deploy/cloudrun-service.yaml'))
assert doc['apiVersion'] == 'serving.knative.dev/v1', doc['apiVersion']
assert doc['kind'] == 'Service'

tmpl = doc['spec']['template']
ann = tmpl['metadata']['annotations']
assert 'run.googleapis.com/cloudsql-instances' in ann, sorted(ann)
assert ann['run.googleapis.com/cloudsql-instances'] == '$DB_INSTANCE_CONNECTION'
assert ann['run.googleapis.com/execution-environment'] == 'gen2'
for k in ('autoscaling.knative.dev/minScale', 'autoscaling.knative.dev/maxScale'):
    assert k in ann, sorted(ann)

spec = tmpl['spec']
assert 'containerConcurrency' in spec and 'timeoutSeconds' in spec
assert spec['serviceAccountName'] == '$RUNTIME_SERVICE_ACCOUNT'

c = spec['containers'][0]
assert c['image'] == '$IMAGE', c['image']
assert c['ports'][0]['containerPort'] == 8080
assert set(c['resources']['limits']) == {'cpu', 'memory'}

names = [e['name'] for e in c['env']]
assert len(names) == len(set(names)), 'duplicate env name'

expected = {
    'PROJECT_ID', 'STORAGE_BUCKET', 'DB_ENGINE', 'DB_HOST', 'DB_USER', 'DB_PASSWORD',
    'DB_NAME', 'DB_PORT', 'SECRET_KEY', 'DJANGO_DEBUG', 'ALLOWED_HOSTS',
    'CORS_ALLOWED_ORIGINS', 'BACKEND_BASE_URL', 'CLOUD_RUN_COMPUTATION_JOB_NAME',
    'CLOUD_RUN_REGION', 'BRANCH_NAME', 'EMAIL_HOST', 'EMAIL_PORT', 'SMTP_USER_EMAIL',
    'SMTP_USER_PASSWORD', 'FIREBASE_API_KEY', 'FIREBASE_AUTH_DOMAIN',
    'FIREBASE_PROJECT_ID', 'FIREBASE_STORAGE_BUCKET', 'FIREBASE_MESSAGING_SENDER_ID',
    'FIREBASE_APP_ID', 'FIREBASE_MEASUREMENT_ID', 'FIREBASE_SERVICE_ACCOUNT',
}
assert set(names) == expected, f'missing={expected - set(names)} extra={set(names) - expected}'

env = {e['name']: e['value'] for e in c['env']}
assert env['DB_USER'] == '$DB_USERNAME', env['DB_USER']
assert env['DB_HOST'] == '/cloudsql/$DB_INSTANCE_CONNECTION', env['DB_HOST']
assert env['ALLOWED_HOSTS'] == '$CLOUDRUN_ALLOWED_HOSTS'
assert env['CORS_ALLOWED_ORIGINS'] == '$CLOUDRUN_CORS_ALLOWED_ORIGINS'
assert env['BACKEND_BASE_URL'] == '$CLOUDRUN_BACKEND_BASE_URL'
assert 'PORT' not in env, 'PORT is reserved by Cloud Run'
assert 'APP_MODE' not in env, 'D-E: BRANCH_NAME is used instead'
print(f'OK manifest structure, {len(names)} env entries')
PY

# Every env value is a single-quoted scalar (D-F).
test "$(grep -cE "^[[:space:]]+value: '" deploy/cloudrun-service.yaml)" -eq 28
test "$(grep -cE '^[[:space:]]+value: "' deploy/cloudrun-service.yaml)" -eq 0

# Cross-check: every settings.py env name that this service must supply is present.
.venv/bin/python - <<'PY'
import re, yaml
src = open('djangoexact/djangoexact/settings.py').read()
reads = set(re.findall(r'os\.(?:getenv|environ\.get)\(\s*"([A-Z0-9_]+)"', src))
supplied = {e['name'] for e in
            yaml.safe_load(open('deploy/cloudrun-service.yaml'))
            ['spec']['template']['spec']['containers'][0]['env']}
# Names settings.py reads that the service deliberately does not set.
exempt = {
    'GAE_APPLICATION',            # App Engine only, must stay unset here
    'APP_MODE',                   # D-E
    'CI',                         # test runner only
    'DB_USERNAME',                # not read by settings.py; it is the repo variable name
    'REPORT_READY_EMAIL_ENABLED', # defaults to enabled
    'JOB_NOTIFICATIONS_ENABLED',  # job concern, not the web service
    'PROJECT_COPY_ASYNC_THRESHOLD',
}
gap = reads - supplied - exempt
assert not gap, f'settings.py reads these but the manifest does not supply them: {sorted(gap)}'
print('OK settings.py env coverage')
PY

! grep -nP '\x{2014}' deploy/cloudrun-service.yaml
    </automated>
  </verify>
  <done>
`deploy/cloudrun-service.yaml` parses as a Knative Service, carries the cloudsql-instances
annotation, `containerConcurrency`, `timeoutSeconds`, resource limits and scaling bounds, and
its env list is exactly the 28 expected names with `DB_USER` mapped from `$DB_USERNAME`,
`DB_HOST` as the socket path, no `PORT`, and no `APP_MODE`. Every env value is single-quoted.
The settings.py coverage cross-check finds no unsupplied variable.
  </done>
</task>

<task type="auto">
  <name>Task 4 (CR-04): Review-only Cloud Run deploy workflow</name>
  <files>.github/workflows/deploy-cloudrun.yaml</files>
  <action>
Create `.github/workflows/deploy-cloudrun.yaml` following `<reference_specs>` section `SPEC-C`
exactly. `.github/workflows/deploy.yaml` is NOT modified.

Triggers: `workflow_dispatch` and push to `review` only. Never `main`, never `develop`.
`environment: review`. A `concurrency` group keyed on the ref, with `cancel-in-progress`.
Permissions: `id-token: write`, `contents: read`, `actions: read`, `issues: write` (the last
for the shared failure-issue action).

Step order matters and is fixed:
1. Dump `toJson(vars)` then `toJson(secrets)` into `$GITHUB_ENV` with heredoc delimiters.
   Use `GHEOF` as the delimiter, not `EOF`, to reduce the chance of a value colliding with it.
   Add the comment explaining why heredoc form is used, citing `deploy.yaml:370`.
2. Resolve identifiers and defaults (D-C, D-I). Note in a comment that `SERVICE_NAME` is
   already the App Engine service name and must not be reused.
3. Build `TAG` and `TAG_LATEST` from Artifact Registry, using `${{ github.run_number }}` and
   `latest`.
4. Checkout, WIF auth, setup-gcloud, setup-python 3.11, pip install requirements.
5. cloud-sql-proxy. Copy the SIGPIPE redirect comment from `deploy.yaml:236-248` and the
   readiness-wait loop from `deploy.yaml:318-331` rather than reinventing either.
6. `check --deploy`, THEN `migrate`, THEN `runscript invalidate_results_cache`. The ordering
   is WR-02: a rejected config must abort before the schema is mutated. This step overrides
   `DB_HOST=127.0.0.1` for the proxy and sets `APP_MODE=review`, matching `deploy.yaml:253`.
7. Create the Artifact Registry repository if it does not exist.
8. Generate the throwaway Firebase credential to a file under /tmp using the same
   construction as `deploy.yaml:61-89`, build with `DOCKER_BUILDKIT=1` and
   `--secret id=build_firebase_cred,src=...`, delete the credential file, push both tags.
   The credential is written straight to a file and never echoed.
9. Render the manifest: export `IMAGE`, verify `envsubst` is available, run the
   required-variable and apostrophe guards (D-F), `envsubst` into `/tmp/service.yaml`, parse
   it with `yaml.safe_load`. The guards report variable NAMES only, never values.
10. `gcloud run services replace /tmp/service.yaml`, then remove the rendered file. Do NOT
    raise gcloud's log verbosity to debug on this step; unlike the App Engine deploy, that
    would dump the request body, and the request body is every env value. A verify gate
    greps the workflow for that flag's spelling, so the explanatory comment must describe
    the flag rather than spell it out.
11. `add-iam-policy-binding` for `allUsers` with `roles/run.invoker`, plus
    `gcloud run services update --ingress=all`.
12. Write the service URL to `$GITHUB_STEP_SUMMARY` using
    `--format='value(status.url)'`, which prints the URL and nothing else. A bare
    `gcloud run services describe` would print the whole spec including env values.
13. `un-fao/fao-ga-create-issue@v2` on failure, matching `deploy.yaml:472-474`.

Nothing in this workflow may print the rendered manifest. Where a comment warns about that,
phrase it as a statement that the file is not printed; do not write the printing command
itself into the comment.

Commit as `feat(ci): add review-only Cloud Run deploy workflow`.
  </action>
  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp
WF=.github/workflows/deploy-cloudrun.yaml

.venv/bin/python - <<'PY'
import yaml
d = yaml.safe_load(open('.github/workflows/deploy-cloudrun.yaml'))
# PyYAML parses the bare key `on` as boolean True.
trig = d.get('on', d.get(True))
assert 'workflow_dispatch' in trig, sorted(trig)
assert trig['push']['branches'] == ['review'], trig['push']['branches']
assert 'pull_request' not in trig
job = d['jobs']['deploy']
assert job['environment'] == 'review', job['environment']
assert job['permissions']['id-token'] == 'write'
assert job['permissions']['issues'] == 'write'
assert 'concurrency' in d or 'concurrency' in job
names = [s.get('name', '') for s in job['steps']]
assert any('Create Issue' in n for n in names), names
print(f'OK workflow shape, {len(job["steps"])} steps')
PY

# main is never a trigger.
test "$(grep -cE '^[[:space:]]+- main$' "$WF")" -eq 0

# WR-02: check --deploy strictly precedes migrate.
CHK=$(grep -n 'manage.py check --deploy' "$WF" | head -1 | cut -d: -f1)
MIG=$(grep -n 'manage.py migrate' "$WF" | head -1 | cut -d: -f1)
test -n "$CHK" && test -n "$MIG" && test "$CHK" -lt "$MIG"

# Pipeline parity: proxy, readiness loop, cache invalidation all present.
grep -q 'cloud-sql-proxy' "$WF"
grep -q '/dev/tcp/127.0.0.1' "$WF"
grep -q 'runscript invalidate_results_cache' "$WF"

# Secret handling gates.
test "$(grep -cE '(cat|echo|printf|head|tail|less|more)[[:space:]]+[^&|;]*service\.yaml' "$WF")" -eq 0
test "$(grep -c 'verbosity=debug' "$WF")" -eq 0
grep -q "format='value(status.url)'" "$WF"
grep -q 'GHEOF' "$WF"
grep -q 'secret id=build_firebase_cred' "$WF"
grep -q "envsubst < deploy/cloudrun-service.yaml > /tmp/service.yaml" "$WF"
grep -q 'rm -f /tmp/service.yaml' "$WF"

# Deploy target and image registry.
grep -q 'gcloud run services replace /tmp/service.yaml' "$WF"
grep -q 'docker.pkg.dev' "$WF"
test "$(grep -c 'gcr.io' "$WF")" -eq 0

# D-I: the App Engine service name variable is not reused as the Cloud Run service name.
grep -q 'CLOUD_RUN_SERVICE_NAME' "$WF"
test "$(grep -cE '(SERVICE_NAME=\$\{SERVICE_NAME|services replace.*\$SERVICE_NAME|--region.*\$SERVICE_NAME)' "$WF")" -eq 0

! grep -nP '\x{2014}' "$WF"

# ADDITIVE ONLY: the App Engine pipeline and config are untouched.
git diff --quiet HEAD -- .github/workflows/deploy.yaml djangoexact/app.yaml
    </automated>
  </verify>
  <done>
`.github/workflows/deploy-cloudrun.yaml` parses, triggers only on `workflow_dispatch` and
push to `review`, targets `environment: review`, and carries a concurrency group. Its
`check --deploy` line precedes `migrate`. cloud-sql-proxy, the readiness loop and the cache
invalidation are all present. No step prints the rendered manifest, no step uses debug
verbosity, the service URL is read with a value-only format, and the rendered file is
removed after deploy. `deploy.yaml` and `app.yaml` show no diff.

Honest limitation: nothing here proves the deploy succeeds. Only a real CI run on `review`
can validate WIF permissions, the Artifact Registry create path, the docker build, the
Cloud SQL socket connection and the container start. The first-run checklist in Task 5
exists for exactly that.
  </done>
</task>

<task type="auto">
  <name>Task 5 (CR-05): Operator setup guide</name>
  <files>djangoexact/docs/guides/cloud-run-deploy.md</files>
  <action>
Create `djangoexact/docs/guides/cloud-run-deploy.md`, following the established location
convention alongside `async-jobs.md` and `fixtures-guide.md`. It is the human-facing half of
this change and must be complete enough that someone who did not write the workflow can get
the first run green.

Required sections, using these exact H2 headings so the verify gate can find them:

`## What this deploys` and what it does not. State plainly that App Engine is unchanged and
still serves production, that this covers the review environment only, and that ingress and
custom-domain mapping remain an open FAO IT question.

`## One-time GCP setup`. APIs to enable (`run.googleapis.com`,
`artifactregistry.googleapis.com`). IAM roles the WIF deploy service account needs beyond
what App Engine already required: `roles/run.admin`, `roles/artifactregistry.writer`,
`roles/iam.serviceAccountUser` on the runtime service account, and `roles/cloudsql.client`.
Note the workflow creates the Artifact Registry repository itself if it is missing.

`## Repository variables and secrets`. A table with columns Name, Kind (variable or secret),
Scope (repository or review environment), Status (existing or NEW), Purpose. It must list
every placeholder that appears in `deploy/cloudrun-service.yaml` plus the workflow's own
inputs. NEW entries are: `CLOUD_RUN_SERVICE_NAME`, `IMAGE_REPO`, `CLOUDRUN_ALLOWED_HOSTS`,
`CLOUDRUN_CORS_ALLOWED_ORIGINS`, `CLOUDRUN_BACKEND_BASE_URL`, `RUNTIME_SERVICE_ACCOUNT`,
`MIN_SCALE`, `MAX_SCALE`, `CONTAINER_CONCURRENCY`, `REQUEST_TIMEOUT_SECONDS`, `CPU_LIMIT`,
`MEMORY_LIMIT`. State which of those are optional and give the default the workflow applies.
Everything else is marked existing and reused unchanged. Add a warning that secret values
must not contain an apostrophe, and why (D-F).

`## First run checklist`. Numbered, assuming the two-pass hostname path from R-1: dispatch
manually, read the service URL from the job summary, set the two `CLOUDRUN_` host variables,
re-run, then verify the admin panel renders styled (which proves WhiteNoise), a report PDF
downloads (which proves the WeasyPrint native stack), and a login round-trips (which proves
Firebase and the Cloud SQL socket).

`## Ingress and allowed hosts`. Reproduce the R-1 three-option table with the recommendation
and the reasoning, explicitly framed as an open decision for the team.

`## How this differs from App Engine`. Static files via WhiteNoise instead of the
`- url: /static` handler; `BRANCH_NAME` set so `FRONTEND_URL` resolves to the review frontend
(D-E), which App Engine review does not do; `containerConcurrency: 10` chosen to mirror App
Engine rather than take Cloud Run's default of 80, and why `CONN_MAX_AGE = 0` makes that
matter; `_ah/warmup` is inert; the request ceiling is still gunicorn's 120 seconds.

`## Rollback`. `gcloud run services update-traffic --to-revisions=REVISION=100`, and note that
this is strictly better than the App Engine version juggling in `deploy.yaml:346`.

`## Known follow-ups`. The R-3 list, plus the R-2 double-migration risk on review, plus D-J
(no `.dockerignore`) and D-B (the two Dockerfiles are a deliberate fork that must be kept in
sync).

No em-dashes anywhere.

Commit as `docs(deploy): document Cloud Run review deployment setup`.
  </action>
  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp
DOC=djangoexact/docs/guides/cloud-run-deploy.md

test -f "$DOC"

for h in \
  '## What this deploys' \
  '## One-time GCP setup' \
  '## Repository variables and secrets' \
  '## First run checklist' \
  '## Ingress and allowed hosts' \
  '## How this differs from App Engine' \
  '## Rollback' \
  '## Known follow-ups'; do
  grep -qxF "$h" "$DOC" || { echo "missing heading: $h" >&2; exit 1; }
done

# Every placeholder used by the manifest template is documented.
.venv/bin/python - <<'PY'
import re
tmpl = open('deploy/cloudrun-service.yaml').read()
doc = open('djangoexact/docs/guides/cloud-run-deploy.md').read()
# IMAGE is derived inside the workflow, not a repository variable.
derived = {'IMAGE'}
placeholders = set(re.findall(r'\$([A-Z][A-Z0-9_]+)', tmpl))
assert len(placeholders) == 37, f'template placeholder count changed: {len(placeholders)}'
undocumented = sorted(p for p in placeholders - derived if p not in doc)
assert not undocumented, f'template placeholders missing from the guide: {undocumented}'
print(f'OK {len(placeholders)} placeholders, all documented')
PY

# The new variables are all named in the guide.
for v in CLOUD_RUN_SERVICE_NAME IMAGE_REPO CLOUDRUN_ALLOWED_HOSTS \
         CLOUDRUN_CORS_ALLOWED_ORIGINS CLOUDRUN_BACKEND_BASE_URL RUNTIME_SERVICE_ACCOUNT \
         MIN_SCALE MAX_SCALE CONTAINER_CONCURRENCY REQUEST_TIMEOUT_SECONDS \
         CPU_LIMIT MEMORY_LIMIT; do
  grep -qF "$v" "$DOC" || { echo "undocumented new variable: $v" >&2; exit 1; }
done

! grep -nP '\x{2014}' "$DOC"

# Final additive-only assertion across the whole change.
git diff --quiet HEAD -- .github/workflows/deploy.yaml djangoexact/app.yaml deploy/Dockerfile.computation_job deploy/cloudbuild-computation-job.yaml
    </automated>
  </verify>
  <done>
`djangoexact/docs/guides/cloud-run-deploy.md` exists with all eight required headings, names
every placeholder the manifest template uses and every new repository variable, contains no
em-dash, and the four App Engine and computation Job artefacts still show no diff.
  </done>
</task>

</tasks>

<reference_specs>
Exact file skeletons. The executor should treat these as the target content and adapt only
where a task action says to. Fenced here rather than inside the task actions so the actions
stay directive prose.

## SPEC-A: `deploy/Dockerfile.web_service`

```dockerfile
# syntax=docker/dockerfile:1.6

# Cloud Run *service* image for the EX-ACT web API (gunicorn + Django).
#
# Deliberately a fork of deploy/Dockerfile.computation_job rather than a shared
# build: Docker cannot share stages across files without a published base image,
# and turning that file into a multi-target build would change the inputs of the
# computation Job image, which this change is not allowed to touch. Keep the base
# image, the builder stage and the runtime apt list below in sync with it.
# See djangoexact/docs/guides/cloud-run-deploy.md.
#
# Build context: repo root.
#   DOCKER_BUILDKIT=1 docker build \
#     -f deploy/Dockerfile.web_service \
#     --secret id=build_firebase_cred,src=/tmp/build_firebase_cred.txt \
#     -t <tag> .

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# psycopg2 needs libpq + a build toolchain. Keep the toolchain in a separate
# stage so the runtime image stays slim.
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
# libpq5: psycopg2 runtime. The rest are WeasyPrint runtime dependencies:
# Pango/Cairo/GDK-PixBuf/libffi for rendering, plus fontconfig and base fonts so
# report typography matches the App Engine rendering path. This list is kept
# byte-identical to deploy/Dockerfile.computation_job on purpose.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fontconfig \
        fonts-dejavu \
        fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
WORKDIR /app
COPY djangoexact/ /app/

# collectstatic imports djangoexact/settings.py, which refuses to load without
# SECRET_KEY or DEBUG (settings.py:53) and without a base64 JSON service account
# that firebase_admin can parse (settings.py:319-336). Both values here are
# build-time throwaways with access to nothing: the RSA key is generated by the
# caller for this build alone and arrives over a BuildKit secret mount, so it is
# absent from every layer and from image history.
#
# STATIC_ROOT is the same directory as the source static/ tree (settings.py:236),
# so the collected admin/unfold/ckeditor/drf_yasg assets land alongside the four
# committed source files. That is pre-existing behaviour and is preserved.
RUN --mount=type=secret,id=build_firebase_cred,required=true \
    DJANGO_DEBUG=True \
    FIREBASE_SERVICE_ACCOUNT="$(cat /run/secrets/build_firebase_cred)" \
    python manage.py collectstatic --noinput

ENV PORT=8080
EXPOSE 8080

# Shell form on purpose. Cloud Run injects PORT at run time and the exec form
# would hand gunicorn the literal placeholder. `exec` gives gunicorn PID 1 so
# SIGTERM reaches it during a revision drain.
# Worker count and timeout mirror app.yaml:5 exactly.
CMD exec gunicorn -b :${PORT:-8080} -w ${GUNICORN_WORKERS:-4} main:app --timeout ${GUNICORN_TIMEOUT:-120} --access-logfile - --error-logfile -
```

## SPEC-B: `deploy/cloudrun-service.yaml`

```yaml
# Knative Service template for the EX-ACT web API on Cloud Run.
#
# Rendered by .github/workflows/deploy-cloudrun.yaml with envsubst, into a file
# outside the checkout. The rendered manifest carries DB_PASSWORD, SECRET_KEY,
# SMTP_USER_PASSWORD and FIREBASE_SERVICE_ACCOUNT, so it is never written into
# the working tree and never appears in a log line.
#
# Env value scalars are SINGLE quoted on purpose. Double-quoted YAML interprets
# backslash escapes, and these secrets are known to contain dollar signs and
# backslashes (.github/workflows/deploy.yaml:370-381). Single quotes keep both
# literal. The workflow refuses to render if a required value contains an
# apostrophe.
#
# Trap: settings.py:172 reads DB_USER, while the repository variable is named
# DB_USERNAME. The entry below is NAMED DB_USER and VALUED $DB_USERNAME. Renaming
# either half makes psycopg2 authenticate as the literal placeholder string.
#
# PORT is reserved by Cloud Run and must not be listed. APP_MODE is deliberately
# unset; BRANCH_NAME is set instead, matching the computation Job.
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: $CLOUD_RUN_SERVICE_NAME
  labels:
    cloud.googleapis.com/location: $CLOUD_RUN_REGION
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: '$MIN_SCALE'
        autoscaling.knative.dev/maxScale: '$MAX_SCALE'
        # Unix socket to the same Cloud SQL instance App Engine uses. Must agree
        # with the DB_HOST value below.
        run.googleapis.com/cloudsql-instances: $DB_INSTANCE_CONNECTION
        # gen2 for full native library compatibility (Pango, Cairo, GDK-PixBuf).
        # Cloud Run Jobs already run under gen2 with this same dependency stack.
        run.googleapis.com/execution-environment: gen2
        run.googleapis.com/startup-cpu-boost: 'true'
    spec:
      # App Engine Standard caps concurrency near 10 per instance against 4
      # gunicorn workers. CONN_MAX_AGE is 0, so every request opens a new
      # Postgres connection; Cloud Run's default of 80 would multiply connection
      # churn eightfold.
      containerConcurrency: $CONTAINER_CONCURRENCY
      # Headroom above gunicorn's own 120s timeout, which stays the real ceiling.
      timeoutSeconds: $REQUEST_TIMEOUT_SECONDS
      serviceAccountName: $RUNTIME_SERVICE_ACCOUNT
      containers:
        - image: $IMAGE
          ports:
            - name: http1
              containerPort: 8080
          resources:
            limits:
              cpu: '$CPU_LIMIT'
              memory: '$MEMORY_LIMIT'
          env:
            - name: PROJECT_ID
              value: '$PROJECT_ID'
            - name: STORAGE_BUCKET
              value: '$STORAGE_BUCKET'
            - name: DB_ENGINE
              value: '$DB_ENGINE'
            - name: DB_HOST
              value: '/cloudsql/$DB_INSTANCE_CONNECTION'
            - name: DB_USER
              value: '$DB_USERNAME'
            - name: DB_PASSWORD
              value: '$DB_PASSWORD'
            - name: DB_NAME
              value: '$DB_NAME'
            - name: DB_PORT
              value: '$DB_PORT'
            - name: SECRET_KEY
              value: '$SECRET_KEY'
            - name: DJANGO_DEBUG
              value: '$DJANGO_DEBUG'
            - name: ALLOWED_HOSTS
              value: '$CLOUDRUN_ALLOWED_HOSTS'
            - name: CORS_ALLOWED_ORIGINS
              value: '$CLOUDRUN_CORS_ALLOWED_ORIGINS'
            - name: BACKEND_BASE_URL
              value: '$CLOUDRUN_BACKEND_BASE_URL'
            - name: CLOUD_RUN_COMPUTATION_JOB_NAME
              value: '$CLOUD_RUN_COMPUTATION_JOB_NAME'
            - name: CLOUD_RUN_REGION
              value: '$CLOUD_RUN_REGION'
            - name: BRANCH_NAME
              value: '$BRANCH_NAME'
            - name: EMAIL_HOST
              value: '$EMAIL_HOST'
            - name: EMAIL_PORT
              value: '$EMAIL_PORT'
            - name: SMTP_USER_EMAIL
              value: '$SMTP_USER_EMAIL'
            - name: SMTP_USER_PASSWORD
              value: '$SMTP_USER_PASSWORD'
            - name: FIREBASE_API_KEY
              value: '$FIREBASE_API_KEY'
            - name: FIREBASE_AUTH_DOMAIN
              value: '$FIREBASE_AUTH_DOMAIN'
            - name: FIREBASE_PROJECT_ID
              value: '$FIREBASE_PROJECT_ID'
            - name: FIREBASE_STORAGE_BUCKET
              value: '$FIREBASE_STORAGE_BUCKET'
            - name: FIREBASE_MESSAGING_SENDER_ID
              value: '$FIREBASE_MESSAGING_SENDER_ID'
            - name: FIREBASE_APP_ID
              value: '$FIREBASE_APP_ID'
            - name: FIREBASE_MEASUREMENT_ID
              value: '$FIREBASE_MEASUREMENT_ID'
            - name: FIREBASE_SERVICE_ACCOUNT
              value: '$FIREBASE_SERVICE_ACCOUNT'
  traffic:
    - percent: 100
      latestRevision: true
```

## SPEC-C: `.github/workflows/deploy-cloudrun.yaml`

```yaml
name: Deploy Cloud Run (review)

# Additive pipeline. .github/workflows/deploy.yaml still owns App Engine and is
# untouched. Review only, never main: production must not have two pipelines
# deploying and migrating against it.
on:
  workflow_dispatch:
  push:
    branches:
      - review

concurrency:
  group: cloudrun-${{ github.ref_name }}
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-22.04
    environment: review
    permissions:
      id-token: 'write'
      contents: 'read'
      actions: 'read'
      issues: 'write'
    steps:
      # Repository vars and secrets go into $GITHUB_ENV with heredoc delimiters
      # so the values stay byte-for-byte literal. Interpolating them through a
      # YAML env: block instead is what adds two characters to any value
      # containing a dollar sign or a backslash, which breaks psycopg2 auth.
      # See .github/workflows/deploy.yaml:370-381 for the full history.
      - name: Export repository variables
        run: echo '${{ toJson(vars) }}' | jq -r 'to_entries[] | "\(.key)<<GHEOF\n\(.value)\nGHEOF"' >> "$GITHUB_ENV"

      - name: Export repository secrets
        run: echo '${{ toJson(secrets) }}' | jq -r 'to_entries[] | "\(.key)<<GHEOF\n\(.value)\nGHEOF"' >> "$GITHUB_ENV"

      - name: Resolve deployment identifiers
        run: |
          set -eu
          if [ -z "${PROJECT_ID:-}" ]; then
            p="${SERVICE_ACCOUNT#*@}"
            PROJECT_ID="${p%%.*}"
            echo "PROJECT_ID=$PROJECT_ID" >> "$GITHUB_ENV"
          fi
          # SERVICE_NAME is already taken: the variables dump above sets it to
          # the App Engine service name. The Cloud Run service gets its own.
          echo "CLOUD_RUN_SERVICE_NAME=${CLOUD_RUN_SERVICE_NAME:-exact-api}" >> "$GITHUB_ENV"
          echo "IMAGE_REPO=${IMAGE_REPO:-artifacts}" >> "$GITHUB_ENV"
          echo "RUNTIME_SERVICE_ACCOUNT=${RUNTIME_SERVICE_ACCOUNT:-${PROJECT_ID}@appspot.gserviceaccount.com}" >> "$GITHUB_ENV"
          echo "MIN_SCALE=${MIN_SCALE:-0}" >> "$GITHUB_ENV"
          echo "MAX_SCALE=${MAX_SCALE:-4}" >> "$GITHUB_ENV"
          echo "CONTAINER_CONCURRENCY=${CONTAINER_CONCURRENCY:-10}" >> "$GITHUB_ENV"
          echo "REQUEST_TIMEOUT_SECONDS=${REQUEST_TIMEOUT_SECONDS:-300}" >> "$GITHUB_ENV"
          echo "CPU_LIMIT=${CPU_LIMIT:-2}" >> "$GITHUB_ENV"
          echo "MEMORY_LIMIT=${MEMORY_LIMIT:-4Gi}" >> "$GITHUB_ENV"
          echo "BRANCH_NAME=${{ github.ref_name }}" >> "$GITHUB_ENV"
          # Cloud Run gets its own host settings so tightening or widening them
          # can never reach App Engine. They fall back to the App Engine values,
          # which do not yet contain the *.run.app hostname; see the deploy guide.
          echo "CLOUDRUN_ALLOWED_HOSTS=${CLOUDRUN_ALLOWED_HOSTS:-${ALLOWED_HOSTS:-}}" >> "$GITHUB_ENV"
          echo "CLOUDRUN_CORS_ALLOWED_ORIGINS=${CLOUDRUN_CORS_ALLOWED_ORIGINS:-${CORS_ALLOWED_ORIGINS:-}}" >> "$GITHUB_ENV"
          echo "CLOUDRUN_BACKEND_BASE_URL=${CLOUDRUN_BACKEND_BASE_URL:-${BACKEND_BASE_URL:-}}" >> "$GITHUB_ENV"

      - name: Resolve image tags
        run: |
          set -eu
          base="$CLOUD_RUN_REGION-docker.pkg.dev/$PROJECT_ID/$IMAGE_REPO/$CLOUD_RUN_SERVICE_NAME"
          echo "TAG=$base:${{ github.run_number }}" >> "$GITHUB_ENV"
          echo "TAG_LATEST=$base:latest" >> "$GITHUB_ENV"

      - name: 'Checkout Code'
        uses: actions/checkout@v4
        with:
          lfs: true

      - name: Authenticate to Google Cloud
        uses: 'google-github-actions/auth@v2'
        with:
          workload_identity_provider: ${{ vars.WORKLOAD_ID_PROVIDER }}
          service_account: ${{ vars.SERVICE_ACCOUNT }}

      - name: Set up Cloud SDK
        uses: 'google-github-actions/setup-gcloud@v2'

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: djangoexact/requirements*.txt

      - name: Install dependencies
        run: |
          cd djangoexact
          pip install --upgrade pip 'setuptools>=78.1.1' wheel
          pip install -r requirements.txt --no-cache-dir
          pip install --force-reinstall 'setuptools>=78.1.1'

      - name: Setup cloud-sql-proxy
        run: |
          curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.2/cloud-sql-proxy.linux.amd64
          chmod +x cloud-sql-proxy
          # Redirect the proxy's output to a file. When this step ends its log
          # pipe closes; without the redirect the backgrounded Go proxy is killed
          # by SIGPIPE on its next write (the "Listening on 127.0.0.1" line) and
          # never ends up serving 127.0.0.1:5432 for the later steps. The next
          # step waits for readiness and cats this log if it never comes up.
          #
          # Authenticate via Application Default Credentials, i.e. the WIF
          # credential file that google-github-actions/auth exports as
          # GOOGLE_APPLICATION_CREDENTIALS. Do NOT pass --gcloud-auth (-g): it
          # shells out to "gcloud config config-helper", which fails with "You do
          # not currently have an active account selected" because the auth step
          # writes an ADC file without activating a gcloud account.
          ./cloud-sql-proxy -p ${{ vars.DB_PORT }} ${{ vars.DB_INSTANCE_CONNECTION }} > /tmp/cloud-sql-proxy.log 2>&1 &

      - name: Validate config, migrate and invalidate cache
        env:
          APP_MODE: review
          # The proxy listens on localhost; the container will use the /cloudsql
          # socket instead. DB_HOST from the variables dump is the App Engine
          # value and must not leak into these runner-side commands.
          DB_HOST: 127.0.0.1
        run: |
          set -eu

          echo "Waiting for cloud-sql-proxy on 127.0.0.1:${{ vars.DB_PORT }}..."
          for i in $(seq 1 30); do
            if (echo > /dev/tcp/127.0.0.1/${{ vars.DB_PORT }}) 2>/dev/null; then
              echo "cloud-sql-proxy is accepting connections."
              break
            fi
            if [ "$i" -eq 30 ]; then
              echo "cloud-sql-proxy never started listening on 127.0.0.1:${{ vars.DB_PORT }}." >&2
              echo "----- cloud-sql-proxy log -----" >&2
              cat /tmp/cloud-sql-proxy.log >&2 || true
              exit 1
            fi
            sleep 1
          done

          cd djangoexact
          # WR-02: validate config BEFORE migrate so a rejected config aborts the
          # deploy without mutating the schema.
          python manage.py check --deploy
          python manage.py migrate
          python manage.py runscript invalidate_results_cache

      - name: Ensure Artifact Registry repository
        run: |
          set -eu
          gcloud artifacts repositories describe "$IMAGE_REPO" \
            --location="$CLOUD_RUN_REGION" --project="$PROJECT_ID" >/dev/null 2>&1 \
          || gcloud artifacts repositories create "$IMAGE_REPO" \
            --repository-format=docker --location="$CLOUD_RUN_REGION" --project="$PROJECT_ID"

      - name: Build and push image
        env:
          DOCKER_BUILDKIT: '1'
        # Cloud Build stays bypassed: an org policy blocks the deploy service
        # account from the Cloud Build staging bucket, so the image is built with
        # docker on the runner. Same rationale as deploy.yaml:353-357.
        run: |
          set -eu
          # collectstatic inside the image has to import settings.py, which
          # refuses to load without a parseable service account. This generates a
          # throwaway RSA credential for this build alone, exactly as the test job
          # in deploy.yaml:61-89 does. It is written straight to a file and never
          # printed, and it reaches the build over a BuildKit secret mount so it
          # is absent from every layer and from image history.
          python - <<'PYEOF' > /tmp/build_firebase_cred.txt
          from cryptography.hazmat.primitives import serialization
          from cryptography.hazmat.primitives.asymmetric import rsa
          import base64, json
          key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
          pem = key.private_bytes(
              encoding=serialization.Encoding.PEM,
              format=serialization.PrivateFormat.TraditionalOpenSSL,
              encryption_algorithm=serialization.NoEncryption(),
          ).decode()
          throwaway = {
              "type": "service_account", "project_id": "build-only",
              "private_key_id": "build-only", "private_key": pem,
              "client_email": "build-only@build-only.iam.gserviceaccount.com",
              "client_id": "123456789",
              "auth_uri": "https://accounts.google.com/o/oauth2/auth",
              "token_uri": "https://oauth2.googleapis.com/token",
              "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
              "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/build-only",
          }
          print(base64.b64encode(json.dumps(throwaway).encode()).decode())
          PYEOF

          gcloud auth configure-docker "$CLOUD_RUN_REGION-docker.pkg.dev" --quiet
          docker build \
            -f deploy/Dockerfile.web_service \
            --secret id=build_firebase_cred,src=/tmp/build_firebase_cred.txt \
            -t "$TAG" -t "$TAG_LATEST" \
            .
          rm -f /tmp/build_firebase_cred.txt
          docker push "$TAG"
          docker push "$TAG_LATEST"

      - name: Render Cloud Run service manifest
        run: |
          set -eu
          command -v envsubst >/dev/null 2>&1 || { sudo apt-get update && sudo apt-get install -y gettext-base; }

          export IMAGE="$TAG"

          # Guard rails that report NAMES only. The rendered manifest carries four
          # secrets and is never printed, so these two checks replace the
          # inspection that printing it would have given us.
          #
          # Emptiness matters because envsubst silently substitutes an unset
          # variable with an empty string rather than leaving the placeholder,
          # which would ship a blank setting instead of failing.
          #
          # Apostrophes matter because every env value is a single-quoted YAML
          # scalar (single quotes are what keep dollar signs and backslashes in
          # secrets literal).
          missing=
          for v in PROJECT_ID CLOUD_RUN_REGION CLOUD_RUN_SERVICE_NAME IMAGE_REPO IMAGE \
                   DB_INSTANCE_CONNECTION DB_ENGINE DB_USERNAME DB_PASSWORD DB_NAME DB_PORT \
                   SECRET_KEY STORAGE_BUCKET DJANGO_DEBUG BRANCH_NAME \
                   CLOUDRUN_ALLOWED_HOSTS CLOUDRUN_CORS_ALLOWED_ORIGINS \
                   EMAIL_HOST EMAIL_PORT SMTP_USER_EMAIL SMTP_USER_PASSWORD \
                   FIREBASE_API_KEY FIREBASE_AUTH_DOMAIN FIREBASE_PROJECT_ID \
                   FIREBASE_STORAGE_BUCKET FIREBASE_MESSAGING_SENDER_ID FIREBASE_APP_ID \
                   FIREBASE_SERVICE_ACCOUNT RUNTIME_SERVICE_ACCOUNT \
                   MIN_SCALE MAX_SCALE CONTAINER_CONCURRENCY REQUEST_TIMEOUT_SECONDS \
                   CPU_LIMIT MEMORY_LIMIT; do
            eval "val=\${$v-}"
            if [ -z "$val" ]; then
              echo "required variable is empty: $v" >&2
              missing=1
            fi
            case "$val" in
              *"'"*)
                echo "value contains an apostrophe and cannot be templated: $v" >&2
                missing=1
                ;;
            esac
          done
          [ -z "$missing" ] || exit 1

          # Rendered outside the checkout so no later step or artifact upload can
          # pick it up. A plain envsubst redirect, deliberately without the
          # backslash-unescape pass the org template's subst() helper ends with:
          # that pass would rewrite literal backslash sequences inside a secret.
          envsubst < deploy/cloudrun-service.yaml > /tmp/service.yaml

          python3 -c "import yaml; yaml.safe_load(open('/tmp/service.yaml'))"
          echo "Manifest rendered and parsed."

      - name: Deploy to Cloud Run
        # Debug-level gcloud logging is deliberately not enabled on this step.
        # Unlike the App Engine deploy, it would emit the request body here, and
        # the request body is every env value.
        run: |
          set -eu
          gcloud run services replace /tmp/service.yaml \
            --platform=managed \
            --region="$CLOUD_RUN_REGION" \
            --project="$PROJECT_ID" \
            --quiet
          rm -f /tmp/service.yaml

      - name: Allow unauthenticated invocations
        # Matches the current App Engine exposure. Django auth is unchanged.
        # Revisit together with the FAO IT ingress decision.
        run: |
          set -eu
          gcloud run services add-iam-policy-binding "$CLOUD_RUN_SERVICE_NAME" \
            --region="$CLOUD_RUN_REGION" --project="$PROJECT_ID" \
            --member="allUsers" --role="roles/run.invoker" --quiet
          gcloud run services update "$CLOUD_RUN_SERVICE_NAME" \
            --region="$CLOUD_RUN_REGION" --project="$PROJECT_ID" \
            --ingress=all --quiet

      - name: Report service URL
        # value(status.url) prints the URL and nothing else. A bare describe would
        # print the whole spec, env values included.
        run: |
          set -eu
          url=$(gcloud run services describe "$CLOUD_RUN_SERVICE_NAME" \
            --region="$CLOUD_RUN_REGION" --project="$PROJECT_ID" \
            --format='value(status.url)')
          echo "Cloud Run service URL: $url" >> "$GITHUB_STEP_SUMMARY"

      - name: Create Issue
        if: failure()
        uses: un-fao/fao-ga-create-issue@v2
```
</reference_specs>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| GitHub Actions runner to GCP | WIF-minted short-lived credentials cross here; the runner holds every plaintext secret for the duration of the job |
| Runner process to CI log | Anything written to stdout or stderr becomes a durable, org-visible artefact |
| Build context to image layers | Anything a RUN or ARG touches without a secret mount persists in image history |
| Public internet to Cloud Run | Unauthenticated HTTP reaches Django; the Host header is attacker controlled |
| Cloud Run container to Cloud SQL | Unix socket, credentials supplied as plain env values in the service spec |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-260724-01 | Information disclosure | Rendered `/tmp/service.yaml` printed to CI log | high | mitigate | The org template's trailing print of the substituted manifest is removed (D-G). Replaced by a `yaml.safe_load` parse plus an emptiness and apostrophe guard that report variable NAMES only. Verify gate greps the workflow for any printing command applied to that path. |
| T-260724-02 | Information disclosure | Rendered manifest left in the checkout | medium | mitigate | Template lives at `deploy/cloudrun-service.yaml`, renders to `/tmp/service.yaml`, and is removed immediately after `gcloud run services replace`. Nothing secret-bearing ever exists inside the working tree. |
| T-260724-03 | Information disclosure | `gcloud` verbose or describe output | medium | mitigate | Debug-level gcloud logging is not enabled on the replace step, unlike the App Engine deploy. The URL is read with `--format='value(status.url)'` rather than a bare describe, which would print every env value. Both are verify-gated. |
| T-260724-04 | Tampering | Secret corruption in transit through CI | high | mitigate | Heredoc `$GITHUB_ENV` entries keep values literal (CONTEXT.md). Single-quoted YAML scalars keep dollar signs and backslashes literal (D-F). The org template's backslash-unescape pass is dropped (D-H). An apostrophe in a required value fails the render loudly instead of producing a mangled manifest. |
| T-260724-SC | Tampering | pip install of `whitenoise` | high | mitigate | Live registry audit recorded in `<package_legitimacy_audit>`: whitenoise 6.12.0, evansd/whitenoise, not yanked, continuous release history. Pinned to an exact version. Executor must escalate rather than substitute if the pin does not resolve. |
| T-260724-05 | Information disclosure | Throwaway Firebase RSA key baked into image layers | low | mitigate | Delivered over a BuildKit secret mount, never a build arg or a COPY, so it is absent from layers and from image history. Generated per build, grants access to nothing, and the source file is deleted from the runner right after the build. |
| T-260724-06 | Spoofing | Host header against the Cloud Run service | medium | mitigate | `ALLOWED_HOSTS` comes from a dedicated `CLOUDRUN_ALLOWED_HOSTS` variable, so it is set explicitly for this service and cannot widen App Engine. The render step fails if it is empty. Blanket `*` is called out as unacceptable in the guide. |
| T-260724-07 | Elevation of privilege | `allUsers` bound to `roles/run.invoker` | medium | accept | Mirrors the current App Engine exposure; the API is already public and Django's own auth is unchanged by this task. Ingress hardening is blocked on the FAO IT custom-domain decision and is explicitly out of scope (CONTEXT.md). |
| T-260724-08 | Tampering | Image tag drift via `:latest` | low | mitigate | The service manifest pins the immutable `${{ github.run_number }}` tag. `:latest` is pushed as a convenience alias only and is never what gets deployed. |
| T-260724-09 | Denial of service | Concurrent `migrate` from two review pipelines | medium | accept | CONTEXT.md residual risk 1, accepted knowingly for review only. The new workflow has its own concurrency group; serialising against `deploy.yaml` would require editing it. Documented as a follow-up in the guide (R-2). |
| T-260724-10 | Denial of service | Connection churn against Cloud SQL | medium | mitigate | `containerConcurrency` pinned to 10 rather than Cloud Run's default 80, because `CONN_MAX_AGE = 0` makes every request a fresh connection (D-C). `maxScale` bounded at 4 by default. |
</threat_model>

<verification>
Run after all five tasks, from the repository root.

1. Additive-only, the single most important gate:
   `git diff --quiet HEAD~5 -- .github/workflows/deploy.yaml djangoexact/app.yaml deploy/Dockerfile.computation_job deploy/cloudbuild-computation-job.yaml`
   Adjust the ref to whatever the pre-change commit is. Any diff here is a failed change.

2. Exactly six files touched across the five commits, and no others:
   `git diff --name-only HEAD~5 HEAD` must list only the six paths in `files_modified`.

3. No em-dash anywhere in the change:
   `git diff --name-only HEAD~5 HEAD | xargs grep -nP '\x{2014}'` must find nothing.

4. Every Python file still compiles:
   `.venv/bin/python -m py_compile djangoexact/djangoexact/settings.py`

5. Both YAML artefacts parse:
   `.venv/bin/python -c "import yaml; yaml.safe_load(open('deploy/cloudrun-service.yaml')); yaml.safe_load(open('.github/workflows/deploy-cloudrun.yaml'))"`

6. Five commits exist, each conventional, one per task.
</verification>

<success_criteria>
- `whitenoise==6.12.0` pinned, `WhiteNoiseMiddleware` at `MIDDLEWARE[1]`, no storages setting added.
- `deploy/Dockerfile.web_service` exists, runtime apt list identical to the computation Job image, collectstatic behind a required BuildKit secret mount, shell-form gunicorn CMD expanding `${PORT`.
- `deploy/cloudrun-service.yaml` exists and parses, with exactly the 28 expected env names, `DB_USER` valued from `$DB_USERNAME`, `DB_HOST` as the `/cloudsql` socket path, the cloudsql-instances annotation, `containerConcurrency`, `timeoutSeconds`, resource limits, scaling bounds, no `PORT`, no `APP_MODE`.
- `.github/workflows/deploy-cloudrun.yaml` exists and parses, triggers on `workflow_dispatch` and `review` only, `environment: review`, `check --deploy` before `migrate`, proxy readiness loop and `invalidate_results_cache` present, no step prints the rendered manifest, no debug verbosity, image pushed to Artifact Registry.
- `djangoexact/docs/guides/cloud-run-deploy.md` exists with all eight headings, documents every template placeholder and every new repository variable, and records the ingress and allowed-hosts decision as open.
- `djangoexact/app.yaml`, `.github/workflows/deploy.yaml`, `deploy/Dockerfile.computation_job` and `deploy/cloudbuild-computation-job.yaml` show zero diff.
- No em-dash in any changed file.

Explicitly NOT claimed by this plan, and stated so nobody reads the green gates as more than
they are: no image was built, no container was started, no deploy was attempted. The sandbox
has neither Docker nor Postgres. Every runtime assertion (Cloud SQL socket connectivity,
WeasyPrint rendering inside the image, WhiteNoise actually serving `/static/`, gunicorn
binding the injected PORT, WIF permissions for Artifact Registry and Cloud Run) is validated
only by the first real CI run on `review`, following the first-run checklist in the guide.
</success_criteria>

<output>
Create `.planning/quick/260724-eut-prepare-the-api-to-be-deployed-to-cloud-/260724-eut-SUMMARY.md` when done.

Record in it: the five commit SHAs, the resource sizing actually chosen, the exact list of
new repository variables the human must create before the first run, the open ingress and
allowed-hosts decision from R-1 with the recommended two-pass path, and the explicit
statement that nothing was validated at run time.
</output>
