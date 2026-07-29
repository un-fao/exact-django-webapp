---
slug: async-copy-operational-errors
status: fix_committed_pending_live_verification
trigger: "since when I deployed the async copy in review, when load testing the async copy I get quite a bit of operational errors: [Image #1] (also in other endpoints). You are connected to the review database through proxy. Investigate"
goal: find_and_fix
created: 2026-07-29
updated: 2026-07-29
---

# Debug: OperationalErrors under load testing of async copy (review env)

## Symptoms
- expected: Async project copy endpoint handles load testing without database errors; other endpoints stay healthy during the load test.
- actual: "Quite a bit" of OperationalErrors during load testing of the async copy, and the errors also appear on OTHER endpoints during the test.
- error_message: User-supplied screenshot shows OperationalError entries (exact text NOT captured in this session; the orchestrator did not receive the image). Presumed django.db.utils.OperationalError; the exact Postgres message (e.g. "remaining connection slots are reserved", "sorry, too many clients already", "server closed the connection unexpectedly") MUST be confirmed from GCP logs or load-test output as first evidence.
- timeline: Started since the async copy feature was deployed to the REVIEW environment. Did not observe these before that deploy (per user).
- reproduction: Run a load test against the async copy endpoint in review; errors appear on the copy endpoint and bleed into other endpoints.
- environment: REVIEW environment. The review Postgres database is reachable locally through cloud-sql-proxy (verify port/db name before querying; prior sessions used 127.0.0.1:5432). Read-only diagnostics against the DB are fine; no destructive statements.
- scope: find_and_fix

## Leads / prior context (verify, do not assume)
- Prior RESOLVED session `.planning/debug/project-4380-cannot-finalize.md` found: api/models.py Project.save() spawns ONE unjoined threading.Thread per module (invalidate_cached_results -> module.save()), each opening its OWN Postgres connection that is never closed; prod max_connections=400, CONN_MAX_AGE=0, no pooling (DATABASE_CONNECTION_POOLING is dead config). A copy of a project touches Project.save()/module saves heavily, so concurrent copies could reproduce the same connection storm. Check whether the review DB shows connection exhaustion in pg_stat_activity during/after load.
- Async copy design (merged to develop, deployed to review): reuses admin_scripts Cloud Run Jobs machinery, i.e. ComputationJob + cloud_run.py dispatch_cloud_run_job, with job_dispatcher.py SUBPROCESS FALLBACK. In review, determine which path executes: if the subprocess fallback runs on the App Engine instance, each spawned subprocess opens its own DB connection(s) in addition to the request workers.
- Recent related work on develop: PR #230 (merge cc1cd880) added reconcile_stale_async_jobs orphan-shell sweep; fccf29f5 refreshes updated_at when unlinking swept jobs. The async copy endpoint itself creates a shell Project synchronously then dispatches the copy job.
- Errors on OTHER endpoints during the load test suggest a shared-resource exhaustion (DB connections at the Postgres server level, since App Engine instances scale independently) rather than a per-request bug in the copy code path.

## Current Focus
- bug_class: Mandelbug (transient, resource/timing dependent; cannot be reproduced by a deterministic unit test)
- status: root cause confirmed, applying fix

```yaml
reasoning_checkpoint:
  hypothesis: >
    Each request to the paginated list endpoints fans out into a per-request ThreadPoolExecutor
    whose worker threads run Django ORM queries. Django connections are thread-local and
    CONN_MAX_AGE=0 with no pool (DATABASE_CONNECTION_POOLING is dead config), so every worker
    thread opens a BRAND-NEW Postgres connection. One /api/projects/ or /api/activities/ request
    therefore issues ~11 near-simultaneous connect() calls on the App Engine instance-local
    /cloudsql unix socket, multiplied by 4 gunicorn workers per instance. That burst exceeds what
    the instance-local socket will accept, and the overflow connect() is refused with ECONNREFUSED,
    surfacing as django.db.utils.OperationalError on whichever request is connecting at that instant.
  confirming_evidence:
    - "Error is at connect() time on the instance-local socket: 'connection to server on socket \"/cloudsql/...\" failed: Connection refused'. Not a server-side FATAL."
    - "Postgres num_backends peaked at 7 of max_connections=400 and Cloud SQL logged zero warnings: the refused connects never reached the database, so the ceiling being hit is per-App-Engine-instance, not per-database."
    - "All 16 failures came from ONE App Engine instance while the sibling instance served 200s throughout: the constraint is instance-scoped."
    - "The two endpoints that failed (/api/projects/ 9x, /api/activities/ 2x) are exactly the two that fan out ORM work into a ThreadPoolExecutor (views.py:638 max_workers=10, views.py:2092 bare ThreadPoolExecutor)."
    - "Endpoints with no fan-out took no failures at all in the same window on the same instance: /api/async-jobs/{id}/ (~100 polls), /api/health/, /api/module-types/, /api/projects/tags/, /api/project-attachments/, /api/parameters/, /api/projects/{pk}/."
    - "Successful /api/projects/ list responses take 0.65-1.03s for a 15-row summary page, consistent with latency dominated by ~10 parallel connection setups rather than by query work."
    - "Google documents an App Engine standard-environment ceiling of 100 concurrent Cloud SQL connections per instance, and intermittent ECONNREFUSED on the /cloudsql socket is a known App Engine failure mode (cloud-sql-proxy issue #1305)."
  falsification_test: >
    If the fan-out is the cause, removing the ThreadPoolExecutor from the two list endpoints drops
    peak simultaneous connect() calls per instance from ~44 to 4 and the ECONNREFUSED must stop.
    The hypothesis is FALSIFIED if OperationalErrors still appear on /api/projects/ or
    /api/activities/ after the fan-out is gone, or if they appear on endpoints that never fanned out.
  fix_rationale: >
    Addresses the root cause (the burst of brand-new connections), not the symptom. The worker
    threads give no CPU parallelism anyway (GIL, pure-Python serialization); their only benefit is
    overlapping DB waits, and each pays a full connection setup on a contended socket to get it.
    executor.map preserves input order, so list(executor.map(f, page)) is semantically identical to
    a sequential comprehension: same serializer, same order, same exception propagation. Batching
    role/tags/country removes the per-object N+1 the threads were hiding, so the sequential path is
    also strictly cheaper than the threaded one.
  blind_spots:
    - "Cannot reproduce on App Engine from this sandbox, and cannot measure the exact socket backlog/limit the burst hits. The evidence pins the ceiling to the instance, not to which instance-level ceiling."
    - "No local Postgres, so the full suite cannot run here; verification is py_compile plus targeted reasoning plus a new regression test that CI must run."
    - "ProjectViewSet.results (views.py:697) keeps a 10-worker fan-out. It did not fail in the observed window, so it is out of scope for this fix, but it is the same defect class and is recorded as follow-up."
    - "The async-copy feature did not introduce the fan-out (it predates it). It is an aggravator, so the fix may reduce rather than eliminate errors if a second aggravator exists."
  candidate_causes:
    - "code: ORM work fanned out into per-request ThreadPoolExecutor worker threads (views.py:638, 697, 2092)"
    - "config: CONN_MAX_AGE=0 plus DATABASE_CONNECTION_POOLING=True being dead config, so every thread opens a brand-new connection and nothing is pooled or reused"
    - "environment: App Engine Standard instance-local /cloudsql socket has a per-instance concurrency ceiling; 4 gunicorn workers per instance multiply the burst"
    - "data: project 8183 is large enough to cross the async threshold, so list pages containing it do the most per-object work"
  and_gate: >
    YES - this failure requires two conditions simultaneously. The thread fan-out alone is harmless
    if connections are pooled or persistent; CONN_MAX_AGE=0 alone is harmless without fan-out
    (1 connection per request). Only fan-out AND no-reuse together produce the ~11x connect burst.
    The App Engine per-instance socket ceiling is the environment condition that turns the burst
    into an error rather than just latency.
```

- next_action: LIVE VERIFICATION PENDING. Fix was REVISED after specialist review (both blockers cleared;
  see Fix Revision Cycle at the end of this file) and is now COMMITTED on branch
  `fix/list-endpoint-connection-fanout`, per the user decision "commit, verify later". Not pushed, no PR.
  This session stays OPEN and is deliberately NOT archived to `.planning/debug/resolved/`: the fix has
  never been observed working against the live failure. Redeploy to review, re-run the load test, then
  work the checklist in `## Pending Live Verification` at the end of this file. Only once that checklist
  passes should this session be marked resolved and moved to `.planning/debug/resolved/`.

## Evidence
- 2026-07-29 CONFIRMED ERROR TEXT (GCP Logging, project fao-exact-review, resource module_id="default" = App Engine Standard, version 20260727t141224):
  `django.db.utils.OperationalError: connection to server on socket "/cloudsql/fao-exact-review:europe-west1:fao-exact-review-postgres/.s.PGSQL.5432" failed: Connection refused`
  raised from psycopg2.connect inside django.db.backends.base.base.ensure_connection -> connect().
  IMPLICATION: failure is at CONNECT time on the instance-local Cloud SQL unix socket. It is NOT "too many clients already", NOT "server closed the connection unexpectedly", NOT a lock/statement timeout.
- Errors occurred ONLY on 2026-07-28, in two clusters: 14:44-14:54 and 15:14-15:15. 71 log lines ~= 18 distinct failures (each failure emits ~4 lines: psycopg2 + django-wrapped traceback).
- Service is APP ENGINE (`default`), not Cloud Run. Review runs BOTH: deploy.yaml deploys App Engine on `review` push, deploy-cloudrun.yaml deploys Cloud Run service `exact-api` on the same push. The load test hit the App Engine host.
- REVIEW Cloud SQL instance fao-exact-review-postgres (Cloud SQL Admin API): tier db-perf-optimized-N-2, POSTGRES_14, flags max_connections=400, log_connections=on, idle_in_transaction_session_timeout=30000.
- DECISIVE (Cloud Monitoring, cloudsql.googleapis.com/database/postgresql/num_backends, 14:20-15:25): backends on database `exact` NEVER exceeded 7 (peak 7 of max_connections 400). Sum over all DBs peaked ~14.
  IMPLICATION: server-side connection exhaustion is impossible. The refused connections never reached Postgres.
- Cloud SQL server logs (resource.type=cloudsql_database) severity>=WARNING in the window: ZERO entries. Server side was completely healthy.
- App Engine request_log 14:40-15:20: only 319 requests total, 2 distinct instances, latency p50 0.03s / p95 1.03s. This was LIGHT traffic, not a saturating load test.
- ALL 16 HTTP 500s came from ONE instance: c803ea6b, spread over 31 minutes (14:44:50 -> 15:15:49). The other instance served 200s throughout.
- Failing endpoints on that instance: GET /api/projects/?summary=true (9x), GET /api/activities/?summary=true (2x), POST /api/accounts/token/refresh/ (3x, latency 0.047-0.18s), GET /api/projects/?summary=true&is_archived=false&is_finalized=false (1x). token/refresh is unrelated to copy -> confirms "bleeds into other endpoints" is instance-scoped, not endpoint-scoped.
- Load-test traffic included 4x POST /api/projects/8183/copy/async/ and 6x HTTP 202, plus heavy polling of /api/async-jobs/{14,15,16,17}/.
- CODE api/views.py:638 ProjectViewSet.list uses ThreadPoolExecutor(max_workers=10) to serialize each page item; api/views.py:697 ProjectViewSet.results uses ThreadPoolExecutor(max_workers=10) over activities; api/views.py:2092 uses a bare ThreadPoolExecutor() (default max_workers = min(32, cpu+4)). Django ORM calls in those worker threads each open their OWN connection and no code calls connection.close() in the workers.

## Eliminated
- hypothesis: Postgres server-side connection exhaustion ("too many clients already" / "remaining connection slots are reserved") -> ELIMINATED. num_backends peaked at 7/400; error text is "Connection refused" at the local socket, not a server FATAL.
- hypothesis: idle_in_transaction_session_timeout (30s) killing long copy transactions -> ELIMINATED as the cause of THESE errors. That flag produces "terminating connection due to idle-in-transaction timeout" on an EXISTING session; observed failures are at connect() time, and no Cloud SQL server-side log entries exist.
- hypothesis: lock contention / deadlock from concurrent copies of the same source project -> ELIMINATED. Lock waits surface as statement/lock timeouts or deadlock-detected errors from the server; the server logged nothing and the failure is pre-connection.
- hypothesis: Cloud SQL instance under-provisioned for review (small tier) -> ELIMINATED. tier is db-perf-optimized-N-2 with max_connections=400 and it was idle (<=7 backends).
- hypothesis: job_dispatcher SUBPROCESS FALLBACK running on the App Engine instance (each subprocess opening its own connections) -> ELIMINATED. CLOUD_RUN_COMPUTATION_JOB_NAME is set in app.yaml, so async_jobs.dispatch takes the _dispatch_cloud_run branch, and Cloud Run job executions (resource.type=cloud_run_job, job exact-computation-job) are present in the logs for that window. No subprocess path ran.
- hypothesis: the async copy feature INTRODUCED the defect -> ELIMINATED. git log -L on views.py:638 shows the ThreadPoolExecutor in ProjectViewSet.list predates the async-copy work (commit 34c01aa8, "Add faster summary serialization for project and activity lists"). The async-copy feature is an AGGRAVATOR, not the origin: it added activity_count/module_count to ProjectSummarySerializer (heavier list rows), a ~6s polling loop on /api/async-jobs/{id}/, and a frontend project-list refresh right after each 202, which is why 500s cluster within a second of every copy/async and report/async dispatch.

## Resolution

root_cause: >
  TWO conditions together (AND-gate fired), plus one environment condition that turns them into an error:
  (1) CODE - the paginated list endpoints fan ORM work out into a per-request ThreadPoolExecutor
      (api/views.py:638 ProjectViewSet.list max_workers=10; api/views.py:2092 ActivityViewSet.list
      with a BARE ThreadPoolExecutor(), default min(32, os.cpu_count()+4); api/views.py:697
      ProjectViewSet.results max_workers=10).
  (2) CONFIG - Django connections are thread-local and CONN_MAX_AGE=0, and settings.DATABASE_CONNECTION_POOLING
      is dead config no code reads, so a worker thread cannot reuse the request connection and nothing is
      pooled: every worker thread opens a BRAND-NEW Postgres connection.
  Together, one list request costs 1 + max_workers simultaneous connect() calls. With DefaultPagination.max_page_size=100,
  ActivityViewSet.list's bare executor could open up to 32 connections for a single request, and with
  4 gunicorn workers per instance that is up to 132 concurrent connections from one App Engine instance.
  (3) ENVIRONMENT - App Engine Standard serves Cloud SQL through an instance-local unix socket
      (/cloudsql/<instance>/.s.PGSQL.5432) with a per-instance ceiling (documented cap: 100 concurrent
      connections). Under the burst that socket refuses the overflow, and psycopg2 surfaces ECONNREFUSED as
      django.db.utils.OperationalError on whichever request is connecting at that instant - which is why
      unrelated endpoints (POST /api/accounts/token/refresh/) failed too, and why the failures were confined
      to the one instance receiving the fan-out traffic while its sibling served 200s throughout.
  The database was never the constraint: it peaked at 7 of 400 backends and logged nothing.

fix: >
  REVISED after specialist review (see Specialist Review below and Fix Revision Cycle at the end).

  New module api/concurrency.py owns the whole defect shape in one place:
  - SERIALIZATION_MAX_WORKERS = 4, with the per-instance budget documented inline
    (4 gunicorn workers x (1 request connection + 4 workers) = 20, well under the 100 cap) and with the
    "4 gunicorn workers" assumption named explicitly, including where it breaks (Cloud Run
    containerConcurrency > 1 makes the formula understate the peak).
  - map_in_bounded_threads(func, items, max_workers, on_error): workers drain a shared deque, so the run
    costs min(max_workers, len(items)) connections rather than one per item, each worker closes its own
    connection in a finally, results come back in INPUT order, and error handling mirrors
    ThreadPoolExecutor.map (earliest failure in input order is re-raised; or on_error drops the item).
  - default_language(): pins the active language to settings.LANGUAGE_CODE for a block.

  Call sites, all five request-path pools now routed through the helper:
  - api/views.py ProjectViewSet.list: ThreadPoolExecutor(max_workers=10) removed; the page is serialized
    on the request's own connection, wrapped in default_language() to preserve response bytes.
    This endpoint carried 9 of the 16 observed 500s.
  - api/views.py ProjectViewSet.results: max_workers=10 pool + as_completed replaced by the helper.
  - api/views.py ActivityViewSet.list: bare ThreadPoolExecutor() replaced by the helper.
  - public/views.py PublicProjectViewSet.results: max_workers=10 pool + as_completed replaced (BLOCKER 2).
  - public/views.py PublicActivityViewSet.list: bare ThreadPoolExecutor() replaced (BLOCKER 2).

  Peak simultaneous connects per App Engine instance drops from up to 132 to 20, and the worker
  connections are now released when the work finishes instead of being held for the life of the pool.

files_changed:
  - djangoexact/api/concurrency.py (new)
  - djangoexact/api/views.py
  - djangoexact/public/views.py
  - djangoexact/api/tests/test_serialization_connection_fanout.py (new)

oracle_type: derived (contract) - the assertions are derived from the App Engine per-instance connection
  budget, from ThreadPoolExecutor.map's order-preserving and first-exception contract, and from the
  measured thread-locality of django.utils.translation and django.db.connections. Not from a specified
  requirement, and not from a mere absence of crashes.

blocker_1_decision: PRESERVE THE EXISTING BYTES. See Fix Revision Cycle for the full reasoning.

verification:
  - signal_regression_test_red_before_fix: PASS (executed). scratch replay_head.py runs the static guard
    against `git show HEAD:` for both request-path modules. HEAD reports 5 direct pools (api/views.py
    638, 697, 2092; public/views.py 112, 269) => FAIL. The FIRST-PASS fix as reviewed still reports 5
    direct pools => FAIL, which is exactly BLOCKER 2: the old guard only parsed api/views.py and so
    reported green while public/views.py shipped the identical defect. The revised tree => PASS.
  - signal_mutation_at_fix_site: PASS (executed). 5 source mutations, each run in a fresh subprocess with
    the file restored afterwards; all 5 killed:
      A  remove connection.close() from the worker finally -> test_each_worker_releases_its_connection
      B  add an inline fast path for single-item input     -> test_work_never_runs_on_the_calling_thread
      B2 make default_language() a no-op                   -> test_override_reproduces_the_language...
      C  return results in completion order                -> test_results_come_back_in_input_order...
      D  reintroduce a bare pool in public/views.py        -> test_request_path_modules_do_not_build...
    A SIXTH mutation SURVIVED on the first attempt and was acted on: wrapping the worker body in
    default_language() could be removed with every test still green, because a worker thread inherits no
    language anyway. That line was redundant protection and an untestable liability, so it was deleted and
    replaced by test_work_never_runs_on_the_calling_thread, which pins the invariant that actually keeps
    the worker-language behaviour true. Mutation B above is the proof that the replacement bites.
  - signal_diff_is_not_deletion_only: PASS. Deletions (the five pools) are the RCA-justified change; the
    diff also adds a shared helper, a shared bound, deterministic connection release, and deterministic
    result ordering.
  - signal_scope: PASS. Four files. No serializer, model, calculation or URL change. No response-byte
    change (see blocker_1_decision); the one intentional behaviour change is that
    ProjectViewSet.results / PublicProjectViewSet.results now return activities in request order instead
    of thread-completion order, which was never stable and so could not have been depended on.
  - local_test_run: PASS (executed). 16 of the 20 tests in the new module need no database and are plain
    unittest.TestCase, so they were run for real in this sandbox against the project's own settings on
    sqlite: `ran=16 failures=0 errors=0`. api/tests/factories.py runs queries at import time, so it was
    stubbed in the scratch runner only; nothing in the repo depends on that stub.
  - blocker_1_empirical_check: PASS (executed). Independently reproduced the reviewer's finding before
    acting on it. With LANGUAGE_CODE="en": request thread under Accept-Language fr -> get_language()=="fr";
    fresh ThreadPoolExecutor workers -> ["en","en","en","en"]; under override(LANGUAGE_CODE) -> "en", and
    the request language is restored on exit. Fixtures confirm Climate/Moisture/SoilType carry real
    name_fr/name_es/name_ru, so the byte change would have been material, not theoretical.
  - suggestion_1_empirical_check: PASS (executed). Counted live driver Connection objects across a pool's
    lifecycle. Without an explicit close: 3 workers held 3 connections for the whole life of the pool and
    only pool shutdown released them (baseline 0, during 3, after 0). With connection.close() in a finally:
    during 0. This confirms the reviewer's "sustained, not a spike" and is why the helper closes.
  - signal_bug_returns_on_revert: NOT RUNNABLE. Reproducing requires App Engine Standard under concurrent
    load; the sandbox has no Postgres, no Docker, and gcloud user auth is expired. Accepted technical debt:
    confirmation depends on redeploying review and re-running the load test.
  - py_compile: PASS on api/concurrency.py, api/views.py, public/views.py and the new test module.
    Both api.views and public.views also import cleanly under the real settings.
  - full suite: NOT RUNNABLE locally (no Postgres; a sqlite `migrate --run-syncdb` was attempted and did
    not finish within 9 minutes, so it is not a usable local gate). CI runs it against postgres:15 per
    .github/workflows/deploy.yaml. The 4 APITestCase tests, including the non-English Accept-Language
    assertion required by BLOCKER 1, run only there.

suggestions_taken:
  - Worker connections are never closed: TAKEN, but NOT as a per-task close. A per-task close would raise
    total connect() calls from ~max_workers to len(page) (up to 100 at max_page_size) on the very socket
    that is refusing connections, trading a bounded peak for far more handshakes. The helper instead has
    each worker drain a shared queue and close once when the queue runs dry: min(max_workers, len(items))
    connections, released deterministically. Strictly better than both the status quo and a per-task close.
  - ProjectViewSet.results ordering nondeterministic: TAKEN. Both results endpoints now return activities
    in request order.
  - GUNICORN_WORKERS_PER_INSTANCE assumption unpinned: TAKEN. Named in api/concurrency.py and in the test,
    including the Cloud Run containerConcurrency case where the formula understates the peak.
  - "byte-identical" wording: TAKEN. Removed from both the code comment and the test docstrings.

suggestions_deferred:
  - Batch the get_role membership N+1 before claiming a latency win: PARTIALLY TAKEN. The latency claim was
    dropped from the comment rather than left unsupported, which was the reviewer's minimum ask. The
    batching itself is deferred: it means changing ProjectSummarySerializer/ReadProjectSerializer.get_role,
    which is response-shaping code, and this fix deliberately touches no serializer. Recorded below.
  - Delete settings.DATABASE_CONNECTION_POOLING: DEFERRED. Re-confirmed dead (settings.py:208 is the only
    assignment; the only other occurrences are this fix's own comments naming it as dead). Deleting a
    setting is unrelated to the connection burst and belongs in its own commit; meanwhile the code comments
    now stop it from implying protection that does not exist.
  - CONN_MAX_AGE > 0 / a real connection pool: NOT DONE, agreed with the reviewer. CONN_MAX_AGE > 0 would
    retain connections in thread-locals that are about to be destroyed, trading refused connections for
    leaked ones. Django 5.1+ native OPTIONS {"pool": True} needs psycopg 3 and requirements.txt:33 pins
    psycopg2-binary==2.9.6, so that is a migration, not a fix.

remaining_risk_and_followups:
  - LATENCY IS UNMEASURED AND IS THE MAIN OPEN RISK. ActivityViewSet.list went from up to 32 workers to 4
    against a documented Activity.status N+1, and ProjectViewSet.list is now sequential against an
    unbatched get_role N+1 (up to 100 serial round trips at max_page_size). The redeploy load test must
    measure LATENCY, not just the absence of OperationalErrors. If p95 regresses, batch the two N+1s
    rather than widening the pools back.
  - ProjectViewSet.list's non-paginated branch (page is None) still serializes on the request thread with
    no language pin, so it localizes while the paginated branch does not. That split predates this fix and
    the branch is effectively unreachable (DefaultPagination.page_size is always truthy), so it was left
    alone rather than have this fix change bytes on a path it did not touch.
  - ProjectViewSet.retrieve has always honoured Accept-Language while the list has not. Characterized by
    test_retrieve_localizes_and_list_does_not so that whoever unifies the behaviour must do it knowingly.
  - Localizing the list/results endpoints is the real follow-up implied by BLOCKER 1. It is an API change
    and needs its own commit, all endpoints at once, with the WebApp frontend in the loop.
  - The get_role membership N+1 in both project serializers (see suggestions_deferred).
  - api/minitool.py and scripts/*.py use ProcessPoolExecutor. Forked children inherit the parent's psycopg2
    connection, a separate latent corruption risk; not investigated here and not implicated by this evidence.
  - copy_async computes `sum(a.module_types.count() for a in project.activities.all())`, an N+1 of
    1 + activity_count queries on the request thread, on every call.
  - api/tests/factories.py executes ORM queries at import time, so any test module that imports it needs a
    live database even for tests that never touch one. That is why the DB-free classes here had to be run
    with the factories module stubbed.
  - api/views.py carries pre-existing em-dashes at lines 999, 1020 and 1024 as of HEAD (project rule
    violation). Not introduced by this fix and deliberately not touched, to keep this diff to the defect.
  - Review deploys BOTH App Engine (deploy.yaml) and Cloud Run (deploy-cloudrun.yaml) on a push to `review`,
    against the same Cloud SQL instance. The load test hit App Engine. Two live web tiers on one review DB
    is worth an explicit decision.
  - Review logs at DEBUG level, which floods Cloud Logging (it exhausted the Logging read quota during this
    investigation) and makes future diagnosis harder.

## Specialist Review

Independent code review of the applied fix (specialist_hint: python). Verdict: **SUGGEST_CHANGE**.
Two blockers, three suggestions, one nit. Recorded verbatim in substance; the fix is NOT ready to
commit as-is.

### BLOCKER 1 - the "byte-identical response" claim is false on the default ProjectViewSet.list path
`django.utils.translation` active language is thread-local and ThreadPoolExecutor workers do not
inherit it. Verified empirically by the reviewer: request thread active language `fr`, worker threads
`['en', 'en']`. `LocaleMiddleware` is active. `ReadProjectSerializer` (serializers.py:359, the default
when `?summary=true` is absent) embeds `climate`, `moisture` and `soil_type` with `fields = "__all__"`,
and all three are modeltranslation-registered with a translated `name` (api/translation.py:59, 219, 224).

So BEFORE the change those names always came back in `en`, because serialization ran in worker threads
with no language activated. AFTER the change they follow `Accept-Language`. For any non-English client
the response bytes change - which collides with the project compatibility constraint.

Aggravating: the new test only exercises `?summary=true`, and `ProjectSummarySerializer` reaches no
translated field, so the one path that changed is the one path untested. It also introduces an
inconsistency: project list now localizes while ActivityViewSet.list and ProjectViewSet.results still
fan out and still return `en`.

Required: decide the intended behaviour deliberately. Either localize all three (and call it a
behaviour change in the commit), or wrap the comprehension in `translation.override(settings.LANGUAGE_CODE)`
to preserve the old bytes. Either way drop "byte-identical" from the comment and the test docstring, and
add a non-English `Accept-Language` assertion on the non-summary path.

### BLOCKER 2 - public/views.py has the same defect and was not fixed
- `djangoexact/public/views.py:269` - `with ThreadPoolExecutor() as executor:` (bare, unbounded)
- `djangoexact/public/views.py:112` - `ThreadPoolExecutor(max_workers=10)`

Same process, same instance, same /cloudsql socket, same budget. The bare one alone reproduces the exact
4 x 33 = 132 figure the fix's own comment cites as the failure mode. These are UNAUTHENTICATED endpoints
wired at `api/public/` (djangoexact/urls.py:24), so they are the most load-exposed surface.
`ThreadPoolBoundsStaticTests` only parses `api/views.py`, so the guard reports green while the identical
defect ships. Required: extend the AST scan across both modules (or the package) and bound both pools.

### SUGGESTION - worker connections are never closed (confirmed)
Neither `process_activity` closes its connection. `minitool.middleware.DatabaseConnectionMiddleware` does
not help: `connections.close_all()` iterates `ConnectionHandler._connections`, an asgiref `Local`, so it
closes only the CALLING thread's connection. Worker connections survive until the pool's threads exit.
The codebase already has the right pattern at `api/management/commands/run_async_job.py:50` and
`admin_scripts/management/commands/run_computation_job.py:91` (both call `connection.close()`).
Apply `try/finally: connection.close()` in both remaining executor bodies. This matters more than it
looks: the connection is held for the life of the pool, so the budgeted peak is SUSTAINED, not a spike.

### SUGGESTION - ProjectViewSet.results ordering is nondeterministic
`as_completed(future_to_pk)` + `append` yields COMPLETION order, not `activity_pks` order. Narrowing 10 to
4 does not break it (it was never ordered) but it does change the empirical ordering clients have seen.
Since the block is already being touched, make it deterministic by collecting into a dict keyed by pk and
rebuilding in `activity_pks` order. Error handling is unaffected by the narrower pool.

### SUGGESTION - the now-sequential ProjectViewSet.list has an unbatched N+1
The latency claim in the comment is unverified and probably optimistic. `get_role` runs
`ProjectMembership.objects.filter(user=user, project=obj)` PER PROJECT; `_attach_project_counts` batches
the counts but not this. At `max_page_size=100` the sequential path now does up to 100 serial round trips
where it previously did 10 in parallel. Batch memberships before claiming a latency win, or measure it.
Same concern larger on ActivityViewSet.list: 32 workers to 4 on a 100-item page, against the documented
`Activity.status` N+1, is up to an 8x parallelism cut on the slowest endpoint. Re-run the load test for
LATENCY, not just for errors.

### NIT - on the choice of SERIALIZATION_MAX_WORKERS = 4
Defensible stopgap; the alternatives are mostly worse here.
- `CONN_MAX_AGE > 0` would actively HURT: with per-request pools, worker threads die at end of request, so
  a non-zero CONN_MAX_AGE tells Django to RETAIN connections in thread-locals about to be destroyed. It
  trades refused connections for leaked ones.
- A real pool is unavailable: requirements.txt:33 pins `psycopg2-binary==2.9.6`, and Django 5.1+ native
  `OPTIONS: {"pool": True}` requires psycopg 3. That is a migration, not a fix.
- Removing all three pools is the idiomatic endpoint. The work is N+1-bound, not latency-bound, so the
  parallelism is compensating for query count. Fix the N+1s and drop the pools - then no budget constant
  is needed at all. Worth stating as the follow-up.
Loose ends: `GUNICORN_WORKERS_PER_INSTANCE = 4` is hardcoded in the test, but
`deploy/Dockerfile.web_service:96` reads `${GUNICORN_WORKERS:-4}` and `deploy/cloudrun-service.yaml`
templates `containerConcurrency: $CONTAINER_CONCURRENCY` - on Cloud Run with concurrency > 1 the formula
UNDERSTATES the peak. Pin that assumption in a comment. And since the fix documents
`DATABASE_CONNECTION_POOLING` as dead config (settings.py:208 is the only assignment, nothing reads it),
delete it rather than leaving a setting that reads as if pooling were on.

### What the reviewer endorsed
The root cause work: pinning it on refused-at-the-socket rather than database exhaustion, backed by
"num_backends peaked at 7 of 400" and the single-instance blast radius. Also
`test_budget_formula_rejects_the_previous_bare_executor_default` (keeps the guard from being weakened
later) and the AST-based bound check (right instinct for a recurring defect shape - it just needs to scan
the second file where the shape already recurs).
On the narrow sub-question: `list(executor.map(f, xs))` and `[f(x) for x in xs]` ARE equivalent for
ordering and for which exception surfaces; `map` submits eagerly so every item executes even when item 0
raises, while the comprehension short-circuits, but serialization is read-only so no side effects diverge.
The ordering half of the claim is sound. It is the thread-local language that breaks it.

## Fix Revision Cycle (post specialist review)

Verdict handled: SUGGEST_CHANGE, two blockers. Root cause was NOT re-investigated; it stands.

### BLOCKER 1 - resolved by PRESERVING the existing bytes

Reproduced independently before acting. With `LANGUAGE_CODE = "en"`:

| context | `translation.get_language()` |
|---|---|
| request thread, `Accept-Language: fr` | `fr` |
| fresh `ThreadPoolExecutor` worker | `en` |
| `translation.override(settings.LANGUAGE_CODE)` | `en` |

and `override` restores `fr` on exit. Fixtures confirm `Climate`, `Moisture` and `SoilType` carry real
`name_fr` / `name_es` / `name_ru`, so the reviewer is right that the first-pass fix would have changed
response bytes for every non-English client on the default `ProjectViewSet.list` path.

DECISION: wrap the now-sequential comprehension in `concurrency.default_language()` so the bytes stay
exactly as they were. Reasoning:

1. The milestone constraint is explicit that the public API contract must not change, and this is a
   reliability fix. Localizing would be a user-visible behaviour change smuggled in under a connection fix,
   on a path with no test coverage before this cycle and no frontend coordination.
2. The frontend is an unknown here. It may match these reference names as strings; it has only ever
   received English from the list endpoint. That risk is not worth taking as a side effect.
3. Preserving is the reversible choice. Localizing later is a deliberate, reviewable change; shipping the
   localization now and discovering the frontend breaks means a rollback of the reliability fix too.
4. It also removes the inconsistency the reviewer flagged: with the pin, all five fanned-out or
   de-fanned-out endpoints answer in `settings.LANGUAGE_CODE`, exactly as before.

`override(settings.LANGUAGE_CODE)` was verified to be the exact equivalent of "no language activated",
so this reproduces worker behaviour rather than approximating it.

Also done, as required: "byte-identical" removed from the code comment and from the test docstrings; a
non-English `Accept-Language` assertion added on the non-summary path
(`test_non_summary_list_still_answers_in_the_default_language`), which is the path that actually changed
and the one the first-pass tests missed. `test_retrieve_localizes_and_list_does_not` characterizes the
pre-existing split so a future unification has to be deliberate.

### BLOCKER 2 - resolved by fixing both modules and widening the guard

`public/views.py:112` (`max_workers=10`) and `public/views.py:269` (bare) both now route through
`api/concurrency.py`. These are `AllowAny` endpoints wired at `api/public/`, so they were the most
load-exposed instance of the defect.

The guard was replaced rather than extended. Instead of "every `ThreadPoolExecutor` must pass
`max_workers=SERIALIZATION_MAX_WORKERS`" in one file, it is now "no request-path module constructs a
`ThreadPoolExecutor` at all", scanning `api/views.py` and `public/views.py`, plus a check that the
helper's single pool is bounded. Replaying that guard over `git show HEAD:`:

| tree | verdict |
|---|---|
| HEAD, before any fix | FAIL, 5 direct pools |
| first-pass fix as reviewed | FAIL, 5 direct pools |
| revised fix | PASS |

The middle row is the point: the first-pass guard reported green on a tree that still contained two
unbounded pools.

### What the mutation run changed about the fix

Wrapping the worker body in `default_language()` survived mutation: every test stayed green with the line
deleted, because a worker inherits no language regardless. It was redundant protection that looked like a
guarantee, so it was removed and replaced with `test_work_never_runs_on_the_calling_thread`, which fails
the moment anyone adds an inline fast path (the realistic way that guarantee would actually break). All
five remaining mutants are killed.

## Pending Live Verification

STATUS: **PENDING**. User decision at the human-verify checkpoint was "commit, verify later"
(2026-07-29). The fix is committed on `fix/list-endpoint-connection-fanout` but has NEVER been observed
working against the live failure. Everything verified so far is static, unit-level or empirical-in-sandbox
(see `verification:` in the Resolution section). The one signal that actually matters,
`signal_bug_returns_on_revert`, was NOT RUNNABLE locally: reproducing needs App Engine Standard under
concurrent load.

Do NOT move this session to `.planning/debug/resolved/` until every box below is ticked.

### 1. Redeploy and re-run the load test
- [ ] Merge / deploy `fix/list-endpoint-connection-fanout` to the `review` environment.
- [ ] Re-run the SAME async-copy load test that produced the original errors. Same shape and concurrency,
      otherwise a green result proves nothing.
- [ ] Note the new App Engine version id, so the log query below can be scoped to it.

### 2. Confirm the OperationalError is gone
```
gcloud logging read 'textPayload:"Connection refused"' --project=fao-exact-review --freshness=1d
```
- [ ] Returns nothing for the load-test window.
- [ ] Cross-check the broader symptom, since the socket error is only one spelling of it:
      `gcloud logging read 'textPayload:"OperationalError"' --project=fao-exact-review --freshness=1d`
- [ ] Confirm the 500s on `/api/projects/` and `/api/activities/` are gone, and that no NEW endpoint
      started failing (the original bug landed the error on whatever was connecting, e.g.
      `POST /api/accounts/token/refresh/`, so absence there matters too).

### 3. Measure p95 latency (THE MAIN OPEN RISK)
Absence of errors is NOT sufficient to close this. The fix trades parallelism for connections, and the
latency cost is unmeasured:
- `ActivityViewSet.list` went from up to 32 workers to 4, against a documented `Activity.status` N+1.
- `ProjectViewSet.list` is now fully sequential, against an unbatched `get_role` N+1 (up to 100 serial
  round trips at `max_page_size=100`).

- [ ] p95 latency on `/api/projects/` (both `?summary=true` and the default path) has not regressed.
- [ ] p95 latency on `/api/activities/` has not regressed.
- [ ] Baseline for comparison: successful pre-fix `/api/projects/` list responses took 0.65 to 1.03s for a
      15-row summary page. The fix was expected to IMPROVE this by removing ~10 parallel connection
      handshakes; if it did not, the N+1s are dominating.
- [ ] IF p95 REGRESSES: batch the two N+1s (`get_role` membership lookup, `Activity.status`). Do NOT widen
      the pools back, that reintroduces the defect.

### 4. Confirm no response-shape or localization regression
BLOCKER 1 from the specialist review was resolved by PRESERVING existing bytes, and the non-English
assertion that proves it (`APITestCase`) could not run locally.
- [ ] CI has run the 4 `APITestCase` tests in `api/tests/test_serialization_connection_fanout.py` green,
      including the non-English `Accept-Language` assertion on the non-summary path.
- [ ] `/api/projects/` returns the same shape and ordering as before for a non-English client
      (`climate`, `moisture`, `soil_type` names must still come back in English, as they always have).
- [ ] Sanity-check the public endpoints too: `public/views.py` was changed under BLOCKER 2 and those are
      unauthenticated, so they carry the most load exposure and were NOT part of the original report.

### 5. Only then
- [ ] Mark this session resolved and move it to `.planning/debug/resolved/`.
- [ ] Open the deferred follow-ups recorded in `remaining_risk_and_followups` as their own items,
      in particular: batching the `get_role` N+1, deleting the dead `DATABASE_CONNECTION_POOLING`
      setting, and the "localize list/results endpoints" API change implied by BLOCKER 1.
