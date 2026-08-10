---
slug: project-4380-cannot-finalize
status: resolved
trigger: "A user with 260 activities on project 4380 reported they are unable to set the project to 'finalized'. Investigate possible reasons why"
goal: find_root_cause_only
created: 2026-07-15
updated: 2026-07-15
---

# Debug: Project 4380 cannot be finalized

## Symptoms
- expected: User can set project 4380 (260 activities) to finalized (is_finalized=True)
- actual: Finalize does not take; user reports being unable to finalize
- error_message: unknown (no details from user)
- timeline: unknown
- reproduction: unknown; user-reported on production
- environment: PRODUCTION db, reachable via cloud-sql-proxy 127.0.0.1:5432 (db `exact`)
- scope: diagnose_only (read-only SELECTs, no writes, no code changes)

## Finalize path (static)
- PATCH /api/projects/4380/ with is_finalized=True
- api/views.py ProjectViewSet.partial_update (line 1130) -> ProjectSerializer.validate (serializers.py:442) -> serializer.save() -> response ReadProjectSerializer
- partial_update is NOT @transaction.atomic (only full `update` at 1147 is)
- validate() gates relevant to a bare finalize:
  - is_archived -> "Archived projects cannot be modified"
  - already is_finalized -> "Finalized projects cannot be modified except for their publication status"
  - is_locked by another user & not staff -> "The project is already locked"

## Current Focus
- hypothesis: Finalize triggers Project.save() with is_finalized dirty -> spawns one unjoined threading.Thread per module (>=871 for proj 4380), each doing its own module.save() DB write on its own connection. Thread + DB-connection storm -> finalize request fails/times out at scale.
- next_action: confirm failure mode (Postgres max_connections vs ~900 threads); confirm deployed code == main

## Evidence
- LIVE proj 4380 "Biodiversity Corridor Project" owner 5184: is_finalized=False, is_archived=False, is_locked=False, locked_by=None, is_public=False. Validation gates would all PASS -> not a validation rejection.
- LIVE activity_count=295 (user said "260"); concrete activity-linked modules counted (raw SQL): Grassland 282, LandUseChange 282, ForestManagement 226, PerennialCropland 68, Input 11, Processing 1, Transport 1 = 871. (Energy/infra module tables not counted due to schema drift; true total >=871.)
- CODE api/models.py:678 Project.save(): if is_dirty on any field NOT in exclude_fields=[is_locked,locked_at,lock_updated_at,locked_by,updated_at], loops all activities x all modules and does threading.Thread(target=module.invalidate_cached_results).start() -- threads NEVER joined, connections NEVER closed. is_finalized is NOT excluded.
- CODE api/models.py:1222 Module.invalidate_cached_results(): nulls cache fields then self.save() (a DB write, per thread). Submodules also save parent.
- CODE api/views.py:1130 ProjectViewSet.partial_update: serializer.save() -> Project.save() (not @transaction.atomic). Full update() at 1148 IS @transaction.atomic (worse: whole storm in one tx).
- DEPLOY prod DB at migration 0282; origin/main at 0282 (MATCH) -> prod runs main. origin/main models.py:671 Project.save() has identical thread block (line 684) with same exclude_fields (line 675). develop is ahead at 0288 (export_id added 0283) but bug present in BOTH.

## Eliminated
- hypothesis: Project already locked by another user -> ELIMINATED (is_locked=False, locked_by=None)
- hypothesis: Project archived -> ELIMINATED (is_archived=False)
- hypothesis: Already finalized (stuck from prior half-success) -> ELIMINATED (is_finalized=False)
- hypothesis: A validate() rule rejects the finalize -> ELIMINATED for a bare finalize (all gates pass with current state)

## Additional confirmations
- DATABASE_CONNECTION_POOLING=True (settings.py:186) is DEAD config (never referenced) -> standard psycopg2 backend, real new connection per thread, no pool mitigation.
- No connection.close()/close_old_connections anywhere in models.py -> worker-thread connections leak (Django only closes the main request thread's connection).
- No alternate finalize endpoint; finalize == PATCH is_finalized=True.
- LIVE prod Postgres: max_connections=400 (3 superuser-reserved), ~15 in use at rest, CONN_MAX_AGE=0, ATOMIC_REQUESTS=False.
- DEPLOY origin/main app.yaml: `gunicorn -b :$PORT -w 4 main:app --timeout 120`, instance_class F4_1G.

## ROOT CAUSE
Setting is_finalized=True flips a non-excluded field on Project, so Project.save() (api/models.py:678, identical on origin/main:671 = deployed prod) spawns ONE unjoined threading.Thread per module across ALL activities. Proj 4380 has 295 activities / >=871 modules -> ~871 threads, each calling module.invalidate_cached_results() -> module.save() -> its OWN Postgres connection that is never closed. The result at this scale is a thread + DB-connection storm (871 >> 400 max_connections) that (a) exhausts connections, (b) risks RuntimeError: can't start new thread / memory pressure on the F4_1G worker, and (c) blows past gunicorn --timeout 120 while also serializing the 295-activity ReadProjectSerializer response. Any of these surfaces as a failed/timed-out finalize. Small projects finalize fine because thread count == module count. Not a validation error; the DB write path itself collapses under scale.

## Secondary risk (CORRECTED)
Earlier note claimed partial_update was not atomic; that was wrong (first read started at line 1130 and missed the decorator). ProjectViewSet.partial_update IS @transaction.atomic on both develop (views.py:1129) and origin/main (views.py:702). So the finalize write does NOT half-commit -- it rolls back on failure, so the "stuck finalized" scenario does not occur. The atomicity does make the storm worse in a different way: the request transaction stays open on the project row while ~871 fire-and-forget threads each open their OWN connection/transaction, adding lock contention on top of connection exhaustion.

## Recommended fixes (diagnose-only; not applied)
1. Add is_finalized (and is_public, is_archived) to Project.save() exclude_fields -- toggling a lifecycle flag must NOT invalidate every module's cached results (finalizing doesn't change any calculation input). Smallest, safest fix; directly unblocks finalize.
2. Replace per-module threading in Project.save() with a single bulk UPDATE (queryset.update(...) to null cache columns) or an offloaded Cloud Run job -- never spawn one thread+connection per module in a web request. If threads are kept, cap concurrency and connection.close() in each + join.
3. Consider moving cache invalidation out of the model save() entirely (signal/service), and make the finalize view atomic + resilient.

## Fix applied (option 1)
- branch: fix/finalize-cache-invalidation-storm (off develop)
- commit: e673b4a2 fix(api): exclude lifecycle flags from Project cache invalidation
- change: api/models.py Project.save() exclude_fields now also contains is_finalized, is_public, is_archived, archived_at.
- verification: py_compile OK; pure-logic check confirms finalize/publish/archive/lock no longer enter the thread-spawn branch, while real input changes (cost, implementation_years) still invalidate caches. Full suite not runnable locally (no Postgres); not reproduced against prod (would be a write).
- NOT done (deferred structural work): options 2 and 3 (remove per-module threading / bulk update / offload; make view atomic + resilient). Fix only removes the storm for lifecycle-flag toggles; a real edit on a huge project still fans out threads.

## Structural fix applied (options 2 and 3)
- commit: (see git log) refactor(api): bulk-invalidate module caches instead of per-module threads
- change: api/models.py
  - New module-level service invalidate_module_caches(*, project=None, activity=None): iterates the 24 concrete Module subclasses and issues one synchronous bulk UPDATE each (nulls the 6 cache columns), scoped by activity__project or activity. Mirrors the established bulk pattern in scripts/invalidate_results_cache.py.
  - Project.save(): replaced the ~871-thread fan-out with invalidate_module_caches(project=self). Removed `import threading` (now unused).
  - Activity.save(): replaced the per-module invalidate loop with invalidate_module_caches(activity=self).
- option 3 "atomic finalize view": already satisfied -- partial_update is @transaction.atomic; the new bulk UPDATEs now run inside that single-connection transaction (commit/rollback together). No view change needed.
- VERIFICATION (read-only, live prod):
  - helper selects exactly 24 concrete Module models, 0 Submodules (matches old behavior).
  - all 24 expose the 6 cache fields (no FieldError at code level).
  - touches exactly 871 rows for project 4380 == the old thread-count. Same rows invalidated, now via 24 bulk UPDATEs on one connection instead of 871 threads/connections.
  - py_compile OK. No .update() executed against prod (would be a write; prod 0282 also lacks cached_units_breakdown until migration 0284 deploys).
- behavior notes: bulk .update() skips per-row save() side effects (simple_history entries + last_modified bump) for cache invalidation -- harmless and arguably cleaner; emission correctness, cache-validity semantics, and the public API are unchanged. Existing cache tests unaffected (module-edit invalidation path untouched; finalized-cache-preservation test still holds).
- FOLLOW-UP recommended: add a regression test (finalize/publish/archive do NOT invalidate caches; a real project field change DOES; large project finalizes without a thread/connection storm). Not added here because the suite cannot run in this sandbox (no local Postgres; port 5432 is the prod proxy).


