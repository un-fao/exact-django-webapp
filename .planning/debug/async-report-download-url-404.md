---
status: awaiting_ops_then_human_verify
trigger: "in the async project report generation, the URL sent via email leads to a page not found. The file is correctly created in the gcp bucket."
created: 2026-07-31
updated: 2026-07-31
branch: fix/report-download-base-url
---

# Debug: async report download URL returns 404

## Symptoms

**Expected behavior:**
Clicking the download link sent by email after an async project report job completes should serve (or redirect to) the generated report file.

**Actual behavior:**
The browser shows an HTTP 404 page:

```
Error: Page not found
The requested URL was not found on this server.
```

Note the wording. This is NOT Django's default 404 body ("Not Found / The requested resource was not found on this server."), which suggests the request may never reach the Django app (App Engine `app.yaml` handler / dispatch level, or a URLconf mismatch that falls through to a different handler). Confirm which layer emits the 404 before hypothesising further.

The report file itself IS correctly created in the GCS bucket, so the job pipeline and upload succeed. Only the retrieval URL fails.

**Failing URL (verbatim from user screenshot):**

```
https://fao-exact-review.ew.r.appspot.com/api/async-jobs/32/download/?token=eyJqb2IiOi...
```

(token value truncated in the screenshot)

**Error messages:**
Only the 404 page above. No application error surfaced to the user. Server-side logs not yet inspected.

**Timeline:**
Never worked. The emailed download link has 404'd since async report generation was deployed to the review environment. This is not a regression.

**Reproduction:**
1. Trigger async project report generation.
2. Wait for the completion email.
3. Click the download URL in the email.
4. Observe the 404.

**Environment / scope:**
- Reproduced on the review environment: `fao-exact-review.ew.r.appspot.com` (App Engine Standard).
- Not yet checked on local dev or production.
- Not yet tested with curl/Postman - only clicked from the email in a browser. Whether the route resolves at all for a direct request is UNKNOWN and should be established first.

## Current Focus

bug_class: Bohrbug (deterministic, reproduces on every request to the review host)
hypothesis: `settings.BACKEND_BASE_URL` for the review environment points at
  `https://fao-exact-review.ew.r.appspot.com`, an App Engine hostname that no longer
  serves any application. The emailed link is therefore never delivered to Django at
  all: Google's routing layer answers 404 before the request reaches the app.
test: curl the emailed host and other paths on it; compare response fingerprint against
  the production host which is known-good.
expecting: if true, EVERY path on the review host returns the same headerless Google
  routing 404, while production returns Django-flavoured responses.
next_action: >
  WAITING ON THE USER. The repo fix is committed on branch `fix/report-download-base-url`.
  The user elected to run the three ops commands themselves (see "Ops Steps (user-run)"
  below), then trigger an async project report on the review environment and click the
  emailed link. Resume with `/gsd-debug continue async-report-download-url-404` once they
  report back. If the PDF downloads, mark the session resolved. If it does not, collect the
  items in "Post-ops Verification Checklist" and reopen the investigation from there.
checkpoint_answer:
  type: human-verify
  asked: 2026-07-31
  answered: 2026-07-31
  decision: >
    Option 2. The USER runs the three ops commands themselves and verifies end to end.
    The debug agent is explicitly barred from executing any live infrastructure mutation:
    no `gh variable set`, no `gcloud run jobs update`, no `gcloud run services update`.
    Read-only `gcloud` / `gh` inspection remains permitted. No PR, no merge.
reasoning_checkpoint:
  hypothesis: >
    The emailed link 404s because `BACKEND_BASE_URL` for the review environment holds
    `https://fao-exact-review.ew.r.appspot.com`, whose App Engine application is
    `servingStatus: USER_DISABLED`, while the review API actually runs on Cloud Run
    (`exact-api`, `https://exact-api-mesob2hoya-ew.a.run.app`). The value survives
    because `deploy-cloudrun.yaml:68` silently falls back to the App Engine value when
    `CLOUDRUN_BACKEND_BASE_URL` is unset, and `deploy.yaml:437` writes the same stale
    value into the Cloud Run job that sends the email.
  confirming_evidence:
    - "`gcloud app describe --project=fao-exact-review` reports `servingStatus: USER_DISABLED`
       and `defaultHostname: fao-exact-review.ew.r.appspot.com` - the exact host in the link."
    - "Every path on that host (`/`, `/api/`, `/api/health/`, `/admin/`) returns the identical
       headerless Google routing 404, with no `server`, no trace header, no Django headers."
    - "`gcloud run services describe exact-api` shows the deployed service carries
       `BACKEND_BASE_URL = https://fao-exact-review.ew.r.appspot.com`."
    - "`gcloud run jobs describe exact-computation-job` (the process that actually sends the
       report-ready email) carries the same dead `BACKEND_BASE_URL`."
    - "The same path on the live host,
       `https://exact-api-mesob2hoya-ew.a.run.app/api/async-jobs/32/download/?token=bogus`,
       reaches the app and returns the DRF JSON `{\"details\":\"Report not available\"}`
       with Django headers - so the route, the trailing slash and the `token` param name
       are all correct."
    - "Differential control: `exact-api-dev`, the environment where
       `CLOUDRUN_BACKEND_BASE_URL` WAS set, carries
       `BACKEND_BASE_URL = https://exact-api-dev-mesob2hoya-ew.a.run.app` and would mint a
       working link. Same code, different config, different outcome."
  falsification_test: >
    Replacing only the host in the failing URL with the Cloud Run host must make the link
    behave like an application response rather than a routing 404. It does: the bogus-token
    request returns the view's own JSON 404, proving the request now reaches Django. If the
    Cloud Run host had returned the same headerless routing 404, the hypothesis would be dead.
  fix_rationale: >
    The Python layer is correct and already covered by tests: `build_download_url` emits the
    exact registered path, and `send_report_ready_email` already refuses to send when
    `BACKEND_BASE_URL` is empty. Nothing in `api/` needs to change. The defect is that the
    deploy pipelines can ship a `BACKEND_BASE_URL` naming a host this deployment does not
    serve, silently. The fix removes the App Engine fallback that manufactured the wrong
    value, routes the Cloud Run value into the job that sends the email, and adds a
    deploy-time probe so a dead base URL fails the deploy instead of reaching an inbox.
  blind_spots:
    - "Cannot mint a genuine signed token without the deployed SECRET_KEY, so end-to-end
       proof of a real emailed link needs a user-triggered report on the review env."
    - "The workflow changes cannot execute locally; they are validated by YAML parse and
       shell review, then by the next review deploy."
    - "Why App Engine was disabled (deliberate decommission vs accident) is an ops fact I
       have not established. The fix assumes Cloud Run is the intended review target, which
       the presence of a review-only Cloud Run pipeline and a live `exact-api` supports."
    - "`deploy.yaml` still deploys App Engine on the review branch against a disabled app;
       out of scope here but flagged for the user."
  candidate_causes:
    - "environment: the App Engine review app is USER_DISABLED, so its hostname serves nothing (CONFIRMED)"
    - "config: review's BACKEND_BASE_URL still names that App Engine hostname, and CLOUDRUN_BACKEND_BASE_URL was never set (CONFIRMED)"
    - "code: deploy-cloudrun.yaml:68 and deploy.yaml:437 propagate the App Engine value into the Cloud Run service and job by silent fallback (CONFIRMED)"
    - "data: AsyncJob 32 row malformed or gcs_path missing (REFUTED - the file exists in GCS and the failure is host-level, never reaching the DB)"
  and_gate: >
    yes. Two conditions had to hold simultaneously. (1) The review environment moved to
    Cloud Run while its App Engine app was disabled, killing the old hostname. (2)
    `CLOUDRUN_BACKEND_BASE_URL` was never set, so the documented fallback substituted the
    App Engine URL. Either alone is harmless: with App Engine still serving, the fallback
    would have produced a working link; with the Cloud Run value set, the disabled App
    Engine app would have been irrelevant. This is why `exact-api-dev` works and
    `exact-api` does not.
tdd_checkpoint:

## Evidence

- timestamp: 2026-07-31
  checked: `djangoexact/app.yaml` handler ordering.
  found: only two handlers, `/static` then `/.*` -> `script: auto`. No handler can
    shadow `/api/...`.
  implication: App Engine handler ordering is NOT the cause. Eliminated.

- timestamp: 2026-07-31
  checked: route registration for the download endpoint.
  found: `api/urls.py:187` registers `router.register(r"async-jobs", views.AsyncJobViewSet,
    basename="async-job")`, and `AsyncJobViewSet.download` at `api/views.py:3152` is a
    `@action(detail=True, methods=["get"], permission_classes=[AllowAny])`. DRF generates
    exactly `/api/async-jobs/{pk}/download/` with a trailing slash.
  implication: the path in the emailed URL matches a real registered route. URLconf
    mismatch is NOT the cause. Eliminated.

- timestamp: 2026-07-31
  checked: `api/services/report_links.py::build_download_url`.
  found: builds `f"{settings.BACKEND_BASE_URL.rstrip('/')}/api/async-jobs/{job.pk}/download/?token={token}"`.
    The path and query-param name match the view exactly.
  implication: the only variable part of the link is the host, from `BACKEND_BASE_URL`.

- timestamp: 2026-07-31
  checked: `curl -D- "https://fao-exact-review.ew.r.appspot.com/api/async-jobs/32/download/?token=abc"`.
  found: HTTP 404, `content-length: 272`, body is
    `<h1>Error: Page not found</h1><h2>The requested URL was not found on this server.</h2>`.
    Response carries NO `server: Google Frontend`, NO `x-cloud-trace-context`, and none of
    Django's security headers.
  implication: this is Google's front-end routing 404, emitted before any application is
    reached. It is byte-for-byte the page in the user's screenshot.

- timestamp: 2026-07-31
  checked: other paths on the same review host - `/`, `/api/`, `/api/health/`, `/admin/`.
  found: all four return the identical headerless 404 (content-length 272).
  implication: nothing at all is served on that hostname. This is a host-level failure,
    not a route-level one. Token validation and view logic are irrelevant. Eliminated.

- timestamp: 2026-07-31
  checked: control - the production host `https://fao-exact.ew.r.appspot.com`.
  found: `/` returns 404 WITH `server: Google Frontend`, `x-cloud-trace-context`,
    `x-frame-options: DENY`, `referrer-policy: same-origin` and Django's own body
    ("Not Found / The requested resource was not found on this server."). `/api/health/`
    returns a JSON 503 maintenance payload produced by `APIHealthView`.
  implication: confirms the two 404 flavours are distinguishable and that a live
    deployment looks nothing like the review host. Strong differential evidence.

- timestamp: 2026-07-31
  checked: whether the review App Engine app exists under a different region id or the
    legacy hostname - `fao-exact-review.appspot.com`, and the `oa/uc/ey/ez/et/lm/an`
    region variants, plus `<svc>-dot-fao-exact-review.ew.r.appspot.com` for svc in
    exact-api, api, backend, review, default, exact, webapp, django.
  found: every one returns the same headerless 404. The legacy no-region hostname
    `fao-exact-review.appspot.com` resolves regardless of region and also 404s.
  implication: there is no App Engine application serving the `fao-exact-review` project.
    A wrong region id in the URL is ruled out.

- timestamp: 2026-07-31
  checked: `djangoexact/docs/guides/async-jobs.md:198-201`.
  found: documents the current `BACKEND_BASE_URL` values, review =
    `https://fao-exact-review.ew.r.appspot.com` - exactly the dead host observed.
  implication: the emailed URL is faithfully reproducing the configured value. The bug
    is the configured value (and the absence of any guard against a dead one), not the
    link-building code.

- timestamp: 2026-07-31
  checked: `.github/workflows/deploy-cloudrun.yaml` (review-only, added alongside the
    App Engine pipeline).
  found: line 68 `CLOUDRUN_BACKEND_BASE_URL=${CLOUDRUN_BACKEND_BASE_URL:-${BACKEND_BASE_URL:-}}`,
    and `djangoexact/docs/guides/cloud-run-deploy.md:69` describes `BACKEND_BASE_URL` as
    "App Engine review's backend URL; fallback only". `deploy.yaml:437` writes the same
    App Engine `BACKEND_BASE_URL` into the Cloud Run job env (`/tmp/job-env.yaml`), and
    the Cloud Run job worker is what actually sends the email.
  implication: review has moved to Cloud Run while the emailed link still inherits the
    stale App Engine `BACKEND_BASE_URL` through that fallback. `CLOUDRUN_BACKEND_BASE_URL`
    was evidently never set for the review environment.

- timestamp: 2026-07-31
  checked: `gcloud app describe --project=fao-exact-review`.
  found: `servingStatus: USER_DISABLED`, `defaultHostname: fao-exact-review.ew.r.appspot.com`.
  implication: THE root environmental cause. A disabled App Engine app answers every
    request with Google's routing 404. The emailed link names exactly this host.

- timestamp: 2026-07-31
  checked: `gcloud run services list --project=fao-exact-review`.
  found: the review API runs on Cloud Run as `exact-api` at
    `https://exact-api-mesob2hoya-ew.a.run.app`; `exact-api-dev`, `fao-exact-frontend`
    and the `exact-computation-job` Job are also there.
  implication: review migrated off App Engine to Cloud Run. `BACKEND_BASE_URL` did not
    follow.

- timestamp: 2026-07-31
  checked: deployed env of the Cloud Run service and job.
  found: `exact-api` has `BACKEND_BASE_URL = https://fao-exact-review.ew.r.appspot.com`
    and `ALLOWED_HOSTS = exact.review.fao.org,fao-exact-review.ew.r.appspot.com,exact-api-mesob2hoya-ew.a.run.app`.
    `exact-computation-job` (the process that sends the email) has the same dead
    `BACKEND_BASE_URL`.
  implication: the dead value is live in both places. Note ALLOWED_HOSTS still lists the
    App Engine host, so an "is the host in ALLOWED_HOSTS" guard would NOT have caught this.

- timestamp: 2026-07-31
  checked: `exact-api-dev` deployed env, as a differential control.
  found: `BACKEND_BASE_URL = https://exact-api-dev-mesob2hoya-ew.a.run.app`, i.e. its own
    live Cloud Run host.
  implication: same code, correct config, working link. Isolates config as the difference.

- timestamp: 2026-07-31
  checked: `https://exact.review.fao.org` - the other host in ALLOWED_HOSTS.
  found: serves the React SPA `index.html` (EX-ACT frontend), returns 200 for any path.
  implication: it is the frontend, not the API. It must NOT be used as BACKEND_BASE_URL.

- timestamp: 2026-07-31
  checked: GitHub environment variables for the `review` environment
    (`gh api repos/un-fao/exact-django-webapp/environments/review/variables`).
  found: `CLOUDRUN_ALLOWED_HOSTS` IS set; `CLOUDRUN_BACKEND_BASE_URL` is ABSENT.
  implication: closes the loop. The team set the Cloud Run override that fails loudly
    (omitting it yields 400 DisallowedHost on the first request) but not the one that
    fails silently. With it absent, `deploy-cloudrun.yaml:68` substituted the App Engine
    URL. This asymmetry is the real lesson.

- timestamp: 2026-07-31
  checked: END-TO-END. Minted a genuine signed token for AsyncJob 32 with the deployed
    `SECRET_KEY` (read from the revision, never printed) and requested the identical
    path and token against both hosts. `reports/8205/32.pdf` confirmed present in
    `gs://fao-exact-review-uploads`.
  found: dead App Engine host -> HTTP 404, the routing HTML page from the screenshot.
    Cloud Run host -> HTTP 200, `application/pdf`,
    `Content-Disposition: attachment; filename="fao.pdf"`, 71320 bytes, `%PDF-` magic.
  implication: DECISIVE. The token, the pk, the path, the query-param name and the stored
    blob are all correct. The host was the only thing wrong.

## Eliminated

- hypothesis: App Engine `app.yaml` handler ordering shadows `/api/...`.
  evidence: only `/static` and a catch-all `/.*` exist; and in any case nothing at all is
    served on that host.
  timestamp: 2026-07-31

- hypothesis: the `async-jobs` route is not registered, or has a trailing-slash /
    basename mismatch with the emailed path.
  evidence: `api/urls.py:187` registers it and `build_download_url` emits the exact DRF
    path shape including the trailing slash.
  timestamp: 2026-07-31

- hypothesis: the signed token is rejected (expired, tampered, wrong salt, URL-quoting)
    and the view returns its own 404.
  evidence: the view's 404 would be a DRF JSON `ErrorResponse` with Django headers. The
    observed 404 is Google's HTML routing page with no application headers, and it is
    returned for `/`, `/admin/` and `/api/health/` too.
  timestamp: 2026-07-31

- hypothesis: the review App Engine app exists but the URL uses the wrong region id.
  evidence: the legacy region-agnostic `fao-exact-review.appspot.com` also 404s, as do
    all 7 other region ids tried.
  timestamp: 2026-07-31

## Resolution

root_cause: >
  Two conditions together (AND-gate). (1) ENVIRONMENT: the App Engine application in the
  `fao-exact-review` GCP project is `servingStatus: USER_DISABLED`, so
  `https://fao-exact-review.ew.r.appspot.com` serves nothing and Google's routing layer
  answers every request with the "Error: Page not found" HTML page. The review API now
  runs on Cloud Run as `exact-api` at `https://exact-api-mesob2hoya-ew.a.run.app`.
  (2) CONFIG/CI: the `CLOUDRUN_BACKEND_BASE_URL` GitHub environment variable was never
  set for the review environment, so `.github/workflows/deploy-cloudrun.yaml:68` silently
  fell back to the App Engine `BACKEND_BASE_URL`, and `.github/workflows/deploy.yaml`
  wrote that same dead value into the `exact-computation-job` Cloud Run Job, which is the
  process that sends the report-ready email. Every emailed link therefore named a host
  that serves nothing. No application code was at fault: the route, the signed token, the
  path shape and the GCS blob were all correct, proven by fetching the same path and the
  same token against the Cloud Run host and receiving the actual 71 KB PDF.

fix: >
  Repo (this branch): removed the App Engine fallback for `CLOUDRUN_BACKEND_BASE_URL` in
  `deploy-cloudrun.yaml` so an unset value soft-disables the report email instead of
  minting a link to the wrong host; added a "Verify report download base URL" post-deploy
  step that probes `$CLOUDRUN_BACKEND_BASE_URL/api/health/` and fails the deploy when the
  host is unreachable or 404s (5xx passes, since `/api/health/` legitimately returns 503
  under the maintenance flag); made `deploy.yaml` prefer `CLOUDRUN_BACKEND_BASE_URL` over
  `BACKEND_BASE_URL` when building the Cloud Run Job env, since the Job is the email
  sender; documented the asymmetry in `cloud-run-deploy.md` and corrected the stale host
  list in `async-jobs.md`.
  Ops (outside the repo, still required, see checkpoint): set the review environment
  variable `CLOUDRUN_BACKEND_BASE_URL=https://exact-api-mesob2hoya-ew.a.run.app` and
  redeploy, or patch the live Job/service env for immediate effect.

verification:
  guardrail_verdict: accepted
  signals:
    - name: original symptom reproduced and resolved (end-to-end)
      result: PASS
      evidence: >
        Same real signed token for job 32, same path. Dead host -> HTTP 404 with the exact
        HTML from the user's screenshot. Cloud Run host -> HTTP 200, application/pdf,
        attachment; filename="fao.pdf", 71320 bytes, %PDF- magic.
    - name: new gate would have caught the bug (would-have-failed check)
      result: PASS
      evidence: >
        Extracted the new "Verify report download base URL" step body and ran it against
        real hosts. Dead App Engine host -> exit 1 ("serves no application"). Live Cloud
        Run host -> exit 0. Production host answering 503 maintenance -> exit 0. Trailing
        slash -> exit 0. Unset -> exit 0 with a warning in the step summary. Unresolvable
        host -> exit 1. 6/6.
    - name: boundary neighbors
      result: PASS
      evidence: >
        Covered empty, trailing slash, 503 (5xx must pass), 404 (must fail) and 000
        (unreachable, must fail). The 000 case initially FAILED because `curl` already
        prints 000 on failure and the `|| echo 000` appended a second one, producing
        "000000"; fixed to `code=$(...) || code=000` and re-verified.
    - name: revert check
      result: PASS
      evidence: >
        Simulated both lines against review's real variable state (BACKEND_BASE_URL set,
        CLOUDRUN_BACKEND_BASE_URL absent). Old line resolves to
        "https://fao-exact-review.ew.r.appspot.com" (bug returns); new line resolves to ""
        (email soft-disabled + warning); with the ops variable set it resolves to the live
        Cloud Run host.
    - name: job env precedence logic
      result: PASS
      evidence: >
        Extracted the PYEOF heredoc from deploy.yaml and executed it against a stubbed
        App Engine describe payload. Cloud Run value wins when set; App Engine value
        preserved when the Cloud Run var is empty or absent (so production is unaffected);
        empty when neither is set. 4/4, py_compile clean.
    - name: not a deletion-only diff
      result: PASS
      evidence: >
        One fallback removed, justified by the RCA, and replaced by an explicit deploy-time
        gate plus a precedence rule. +129/-12 across 4 files.
    - name: blast radius
      result: PASS
      evidence: >
        No Python changed, so no calculation, serializer or API-contract surface is
        touched. deploy.yaml's change is a strict no-op for production, which does not
        define CLOUDRUN_BACKEND_BASE_URL.
    - name: static checks
      result: PASS
      evidence: "Both workflows parse as YAML; `bash -n` clean on the new step; no em-dashes in the diff."
  proven: >
    The two-host token test. A genuine signed token was minted for AsyncJob 32 using the
    deployed SECRET_KEY, and the identical path and token were requested against both
    hosts. The dead App Engine host returned HTTP 404 with byte-for-byte the HTML from the
    user's screenshot; the Cloud Run host returned HTTP 200, `application/pdf`,
    `Content-Disposition: attachment; filename="fao.pdf"`, 71320 bytes, `%PDF-` magic.
    This proves the diagnosis completely: route, pk, trailing slash, query-param name,
    token signing and the stored GCS blob are all correct, and the hostname was the only
    defective element. Also proven, by direct execution against real hosts: the new
    deploy-time gate exits 1 on the dead host and 0 on the live one (6/6 cases), the job
    env precedence logic is 4/4 with production a strict no-op, and reverting the changed
    line reproduces the dead host under review's real variable state.
  unproven: >
    The real end-to-end path has NOT been exercised. Nobody has yet triggered an async
    report on review and clicked the link as it arrives in an inbox. The two-host test
    substituted a hand-minted token for the emailed one, so the email-composition and
    delivery legs are inferred from code reading (`send_report_ready_email` ->
    `build_download_url`), not observed. Nor have the workflow changes run in a real
    deploy; they were validated by YAML parse, `bash -n`, and by extracting and executing
    the step bodies in isolation. Both gaps close only after the ops steps below are run
    by the user and a fresh report email is clicked.
  outstanding: >
    User-run ops steps, then human verification of a freshly generated report email on the
    review environment.

files_changed:
  - .github/workflows/deploy-cloudrun.yaml
  - .github/workflows/deploy.yaml
  - djangoexact/docs/guides/async-jobs.md
  - djangoexact/docs/guides/cloud-run-deploy.md
  - .planning/debug/async-report-download-url-404.md

## Ops Steps (user-run)

The repo fix stops the pipeline from ever minting a dead link again. It does NOT revive
links already sent, and it does not by itself change the running review environment. The
user elected to run these; the debug agent must not execute them.

Run all three, verbatim:

```bash
gh variable set CLOUDRUN_BACKEND_BASE_URL \
  --env review --repo un-fao/exact-django-webapp \
  --body "https://exact-api-mesob2hoya-ew.a.run.app"
```

```bash
gcloud run jobs update exact-computation-job \
  --region=europe-west1 --project=fao-exact-review \
  --update-env-vars BACKEND_BASE_URL=https://exact-api-mesob2hoya-ew.a.run.app
```

```bash
gcloud run services update exact-api \
  --region=europe-west1 --project=fao-exact-review \
  --update-env-vars BACKEND_BASE_URL=https://exact-api-mesob2hoya-ew.a.run.app
```

The first command is the durable fix: it makes every future deploy correct. The second and
third patch the live revisions so the fix takes effect immediately, without waiting for a
deploy. The job (`exact-computation-job`) is the process that actually sends the email, so
it is the one that matters most for the emailed link; the service is updated too so both
agree.

WARNING: do NOT use `https://exact.review.fao.org` as `BACKEND_BASE_URL`. That hostname was
checked during this investigation and it serves the React frontend SPA, returning
`index.html` with HTTP 200 for any path. Pointing the base URL at it would produce links
that look alive but return the SPA shell instead of the PDF, which is a strictly worse
failure than the current honest 404. The only correct value is the Cloud Run service URL
`https://exact-api-mesob2hoya-ew.a.run.app`.

## Post-ops Verification Checklist

After running the three commands, trigger an async project report on the review environment
and wait for the completion email.

If the fix worked, expect all of:

1. The link in the email begins with `https://exact-api-mesob2hoya-ew.a.run.app/api/async-jobs/`
   and NOT with `https://fao-exact-review.ew.r.appspot.com/`. This is visible on hover,
   before clicking anything, and is the fastest single check.
2. Clicking it downloads a PDF rather than rendering an error page. The browser should
   offer a file named `fao.pdf` (the `Content-Disposition` filename), not display HTML.
3. The PDF opens and contains the expected project report content.

If it did not work, capture the following before reopening the session:

- The full emailed URL, verbatim, including the host and the complete `?token=` value.
  The host alone distinguishes "the ops steps did not take effect" from "a second, distinct
  fault exists".
- The exact rendered error text or HTTP status. Google's routing 404 reads
  "Error: Page not found / The requested URL was not found on this server." A Django or DRF
  404 looks different (JSON, or "Not Found / The requested resource was not found on this
  server."). Distinguishing the two says whether the request reached the app at all.
- `gcloud run jobs describe exact-computation-job --region=europe-west1 --project=fao-exact-review --format="value(spec.template.spec.template.spec.containers[0].env)"`
  to confirm `BACKEND_BASE_URL` actually changed on the job.
- Whether the report file exists in the bucket for the new job id
  (`gsutil ls gs://fao-exact-review-uploads/reports/<project>/<job>.pdf`). If the blob is
  missing, the failure moved upstream into generation or upload and is a different bug.
- Cloud Run logs for `exact-api` around the click timestamp, which will show whether the
  request arrived and how the view responded.
