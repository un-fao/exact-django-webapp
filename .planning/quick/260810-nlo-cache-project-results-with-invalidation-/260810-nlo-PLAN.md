---
quick_id: 260810-nlo
type: execute
wave: 1
depends_on: []
autonomous: true
requirements: [D1, D2, D3, D3a]
files_modified:
  - djangoexact/api/models.py
  - djangoexact/api/migrations/0290_projectresultcache.py
  - djangoexact/api/migrations/0291_asyncjob_results_recompute.py
  - djangoexact/api/results_cache.py
  - djangoexact/api/views.py
  - djangoexact/api/services/results_jobs.py
  - djangoexact/api/management/commands/run_async_job.py
  - djangoexact/djangoexact/settings.py
  - djangoexact/scripts/invalidate_results_cache.py
  - djangoexact/api/tests/test_results_cache.py
  - djangoexact/api/tests/test_project_results_cache_api.py
  - .planning/BACKLOG.md

estimate:
  tokens: 190000
  raw_tokens: 95000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "GET /api/projects/{id}/results/ returns 200 with an unchanged payload shape on both cache hit and cache miss (D1, hard constraint)."
    - "A cache hit is byte-equivalent to the live compute for the same project and activity selection (D1)."
    - "Any project, activity, or module change advances Project.results_stamp, so the previously stored row can never be read again (D1)."
    - "Deleting a top-level Module or an Activity advances the stamp (must_cover)."
    - "After a stamp bump, exactly one RESULTS_RECOMPUTE AsyncJob is enqueued per project while none is PENDING or RUNNING (D2)."
    - "A recompute worker that starts after a newer edit exits without writing an outdated payload (D2)."
    - "scripts/invalidate_results_cache.py clears the new project-level rows and bumps the stamp, while still skipping finalized projects (D3a)."
  artifacts:
    - djangoexact/api/results_cache.py
    - djangoexact/api/services/results_jobs.py
    - djangoexact/api/migrations/0290_projectresultcache.py
    - djangoexact/api/migrations/0291_asyncjob_results_recompute.py
    - djangoexact/api/tests/test_results_cache.py
    - djangoexact/api/tests/test_project_results_cache_api.py
  key_links:
    - "invalidate_module_caches (api/models.py:637-660) calls bump_project_results_stamp, so both the Project cascade (api/models.py:752-768) and the Activity cascade (api/models.py:1169-1181) are covered by one edit."
    - "security.check_permission (api/views.py:682-684) stays strictly above the cache read."
    - "The cache key is built from the parsed activity pk list (api/views.py:699), never the raw query string."
    - "bump_project_results_stamp uses QuerySet.update(), so it bypasses Project.save() and cannot recurse into invalidate_module_caches."
    - "ProjectResultCache is listed in AUDITLOG_EXCLUDE_TRACKING_MODELS and does not inherit Historical."
---

<objective>
Add a project-level cache for `GET /api/projects/{id}/results/`, invalidate it on any project, activity, or module change, and recompute it asynchronously after invalidation, using only Django builtins and machinery already in this repo (D1).

Purpose: the endpoint re-derives the entire response on every call. Even on a fully warm module cache it still pays thread fan-out, one query per module type per activity, a `get_object_or_404` per module, a write-serializer `is_valid()` per module, and a permission check per module (RESEARCH "What does NOT exist"). A project-scoped stored payload removes all of that.

Output: `ProjectResultCache` model plus `Project.results_stamp`, a read path that serves the stored payload or computes and stores it, complete invalidation coverage including the two gaps the research flagged, an extended ops invalidation lever, and a `RESULTS_RECOMPUTE` AsyncJob that warms the cache after every invalidation.
</objective>

<context>
@.planning/quick/260810-nlo-cache-project-results-with-invalidation-/260810-nlo-RESEARCH.md
@CLAUDE.md
@.claude/CLAUDE.md
</context>

<environment>
A working virtualenv exists at `/home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/.venv`. Verified this session:

- Django loads and `manage.py makemigrations --check --dry-run` runs with no database, given `DJANGO_DEBUG=True`.
- `manage.py test <module>` runs locally when the module contains only `SimpleTestCase` classes (verified on `api.tests.test_inventory_labels`).
- Any test touching `TestCase` / `APITestCase` needs Postgres and is CI-gated only.

**Pre-existing migration drift:** `makemigrations --check --dry-run` already reports unrelated `AlterField` operations on `ef_source` for `largefishery` / `smallfishery` / their historical models. That drift predates this task. Do NOT let `makemigrations` fold it into the new migrations: hand-write the migration files following the style of `djangoexact/api/migrations/0289_asyncjob.py`.

All commands below use absolute paths because the shell working directory resets between calls.
</environment>

<scope_dispositions>
Explicit rulings on the write paths the research flagged as uncovered, plus the deferred bugs.

| Item | Ruling | Reason |
|------|--------|--------|
| Top-level `Module.delete()` (api/models.py:1366-1370) | **IN SCOPE**, Task 1 | Today only the Submodule branch fires. Without a bump, deleting a module leaves a stale project payload servable. |
| `Activity.delete()` | **IN SCOPE**, Task 1 | No project-level notification exists at all. Same staleness consequence. |
| `minitool_changes_import` bulk path (api/services/minitool_changes_import.py:293) | **DEFERRED**, with a confirmation step | The `bulk_create` writes `minitool.ChangeRecord` rows (`minitool/models.py:58`), not `api` Module rows. `ChangeRecord` is an output of `api/services/luc_compute.py`, consumed by the minitool and the scenario builder, not an input to `ProjectViewSet.results`. Task 1 requires the executor to confirm this by grep before accepting the deferral, and to add the bump if the grep contradicts it. |
| `load_reference_data` invalidates nothing (research bug 1) | **NOT FIXED HERE**, filed (D3) | Backlog entry in Task 2. No reference-data epoch is folded into the cache key, because there is nothing to advance it. The manual lever from D3a is the mitigation. |
| `copy_activity` deepcopies a valid cache (research bug 2) | **NOT FIXED HERE**, filed (D3) | Backlog entry in Task 2. |
| `queryset.update()` / `loaddata` / admin bulk actions / direct SQL | **OUT OF SCOPE** | Same blind spots the existing module cache already has. The D3a manual lever covers them operationally. |
| `recompute_dirty_project_results` sweep command + Cloud Scheduler | **NOT BUILT** (D2) | No `cron.yaml` is checked in and the scheduler job could not be confirmed (research open question 1). Replaced by per-edit enqueue with PENDING/RUNNING dedupe. |
</scope_dispositions>

<tasks>

<task type="auto">
  <name>Task 1: Invalidation core, ProjectResultCache model, stamp on every write path</name>
  <files>djangoexact/api/models.py, djangoexact/api/migrations/0290_projectresultcache.py, djangoexact/djangoexact/settings.py</files>
  <read_first>
    djangoexact/api/models.py:625-660 (invalidate_module_caches and _MODULE_CACHE_INVALIDATION),
    djangoexact/api/models.py:752-768 (Project.save cascade and its exclude_fields),
    djangoexact/api/models.py:1169-1181 (Activity.save cascade),
    djangoexact/api/models.py:1288-1370 (CachedResultMixin save/delete),
    djangoexact/api/models.py:3507-3555 (AsyncJob, for model placement style),
    djangoexact/api/migrations/0289_asyncjob.py (hand-written migration style),
    djangoexact/djangoexact/settings.py:282-283 (auditlog settings)
  </read_first>
  <action>
Ships the invalidation machinery and the storage, with no read path yet. Deliberate sequencing (D1): nothing reads the cache until Task 2, so this commit cannot serve a stale number even though invalidation coverage lands first.

1. **`Project.results_stamp`.** Add `results_stamp = models.BigIntegerField(default=0, verbose_name="results_stamp")` to `Project` next to `is_finalized` (api/models.py:719). Add `"results_stamp"` to the `exclude_fields` list inside `Project.save` (api/models.py:760-763) so that if a stamp value ever arrives on a model instance save it does not re-trigger `invalidate_module_caches`.

2. **`bump_project_results_stamp(project_id)`.** New module-level function immediately after `invalidate_module_caches` (after api/models.py:660). Body: return early on a falsy `project_id`, then `Project.objects.filter(pk=project_id).update(results_stamp=F("results_stamp") + 1)`. Add `F` to the existing `django.db.models` imports if it is not already imported. Two properties this must have, and a comment must say so: the bump is atomic (`F` expression, never read-modify-write), and it goes through `QuerySet.update()` so it bypasses `Project.save()` entirely and therefore cannot recurse into `invalidate_module_caches`. Do NOT enqueue anything here yet; Task 3 adds that line.

3. **Central cascade coverage.** At the end of `invalidate_module_caches` (after the model loop at api/models.py:658-660) call `bump_project_results_stamp(project.pk if project is not None else activity.project_id)`. This single edit covers both the `Project.save` cascade (api/models.py:752-768) and the `Activity.save` cascade (api/models.py:1169-1181), which is why it is preferred over scattering calls into views and serializers.

4. **Gap: top-level `Module.delete()`.** In `CachedResultMixin.delete` (api/models.py:1366-1370), resolve the owning project id BEFORE calling `super().delete()` (the row is gone afterwards) using the existing `self.get_activity()` helper that `api/views.py:2596` already relies on for both Module and Submodule. Wrap the resolution in a narrow `try/except` returning `None` so a module whose activity link is already broken cannot turn a delete into a 500. Keep the existing Submodule parent invalidation, call `super().delete()`, then call `bump_project_results_stamp` with the captured id.

5. **Gap: `Activity.delete()`.** Add a `delete` override to `Activity` (class at api/models.py:1002), placed directly after its `save` at api/models.py:1169-1181. Capture `self.project_id`, call `super().delete(*args, **kwargs)`, then bump, then return the value `super().delete()` returned. Bumping after the delete means a failed delete does not bump.

6. **Confirm the minitool deferral.** Run `grep -rn "ChangeRecord" djangoexact/api/calculators.py djangoexact/api/defaults.py djangoexact/api/reports/`. If there are zero hits, the deferral in `<scope_dispositions>` stands and no code is needed. If there are hits, add a `bump_project_results_stamp` call after the `bulk_create` in `djangoexact/api/services/minitool_changes_import.py:293` for every affected project and record that you did so in the commit body.

7. **`ProjectResultCache` model.** Add at the end of api/models.py next to `AsyncJob`. Fields: `project` FK to `"api.Project"` with `on_delete=models.CASCADE, related_name="result_caches"`; `cache_key` `CharField(max_length=64)`; `results_stamp` `BigIntegerField()`; `schema_version` `PositiveIntegerField()`; `payload` `JSONField()`; `computed_at` `DateTimeField(auto_now=True)`. `Meta`: `unique_together = ("project", "cache_key")`. Do NOT inherit `Historical` or `DirtyFieldsMixin`: this is ephemeral derived state, exactly like `AsyncJob` (see its docstring at api/models.py:3508-3512). Uniqueness on `(project, cache_key)` rather than on the stamp is what bounds row growth: a write replaces the row for that key instead of appending one row per edit.

8. **Keep auditlog off it.** `AUDITLOG_INCLUDE_ALL_MODELS = True` at djangoexact/settings.py:282 auto-registers every model, and an audited save deep-copies the whole JSON blob (research bug 3, `.planning/BACKLOG.md` entry `4ng`). Add `AUDITLOG_EXCLUDE_TRACKING_MODELS = ("api.ProjectResultCache",)` immediately after djangoexact/settings.py:283. Verified against the installed `django_auditlog-3.0.0`: `auditlog/registry.py:285-295` reads exactly that setting name and requires `AUDITLOG_INCLUDE_ALL_MODELS = True`, which is already set.

9. **Migration `0290_projectresultcache.py`.** Hand-write it, `dependencies = [("api", "0289_asyncjob")]`, two operations: `AddField` for `Project.results_stamp` and `CreateModel` for `ProjectResultCache` with the `unique_together` in `options`. Follow the formatting of 0289.
  </action>
  <verify>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact && ../.venv/bin/python -m py_compile api/models.py api/migrations/0290_projectresultcache.py djangoexact/settings.py</automated>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact && DJANGO_DEBUG=True ../.venv/bin/python manage.py makemigrations --check --dry-run 2>&1 | grep -icE "projectresultcache|results_stamp"</automated>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact && DJANGO_DEBUG=True ../.venv/bin/python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','djangoexact.settings'); django.setup(); from auditlog.registry import auditlog; from api.models import ProjectResultCache; assert not auditlog.contains(ProjectResultCache), 'ProjectResultCache is still auditlog-registered'; print('auditlog exclusion OK')"</automated>
  </verify>
  <done>
    - `py_compile` passes on all three files.
    - The `makemigrations --check` grep prints `0`, meaning Django sees no unapplied model changes for `ProjectResultCache` or `results_stamp`. The pre-existing `ef_source` drift may still be reported and is not this task's concern.
    - The auditlog assertion prints `auditlog exclusion OK`.
    - `bump_project_results_stamp` is reachable from `invalidate_module_caches`, `CachedResultMixin.delete`, and `Activity.delete`, and uses `F("results_stamp") + 1` through `QuerySet.update()`.
    - The minitool grep result is recorded in the commit body.
    - Commit: `feat(api): add project results stamp and ProjectResultCache storage`
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Read path on the results endpoint, ops invalidation lever, backlog entries</name>
  <files>djangoexact/api/results_cache.py, djangoexact/api/views.py, djangoexact/scripts/invalidate_results_cache.py, djangoexact/api/tests/test_results_cache.py, djangoexact/api/tests/test_project_results_cache_api.py, .planning/BACKLOG.md</files>
  <read_first>
    djangoexact/api/views.py:655-712 (ProjectViewSet.results, including the already-documented `cached` query parameter at :662-667),
    djangoexact/api/views.py:2616-2646 (the module endpoint's compute-on-miss shape, the pattern to mirror),
    djangoexact/api/reports/cache.py:18-23 (INVENTORY_SCHEMA_VERSION),
    djangoexact/scripts/invalidate_results_cache.py (all 43 lines, note the finalized carve-out at :18-22),
    .planning/BACKLOG.md:145-160 (entry format for the two filed bugs)
  </read_first>
  <behavior>
`api/tests/test_results_cache.py`, all `SimpleTestCase` so it runs without Postgres:
- `build_cache_key([2, 1])` equals `build_cache_key([1, 2])`: order does not create a second entry.
- `build_cache_key([1, 1, 2])` equals `build_cache_key([1, 2])`: duplicates collapse.
- `build_cache_key([])` is stable and differs from `build_cache_key([1])`.
- `build_cache_key(["1", 2])` equals `build_cache_key([1, 2])`: string and int pks collapse.
- The returned key is 64 lowercase hex characters, so it always fits `cache_key`'s `max_length=64`.
- Changing `RESULTS_SCHEMA_VERSION` changes the key for the same activity list (patch the constant in the test).
- `normalize_payload` round-trips a dict containing a `Decimal` and a `datetime` to plain JSON types and is idempotent.

`api/tests/test_project_results_cache_api.py`, `APITestCase`, **not locally runnable, CI/DB-gated**:
- Two consecutive `GET /results/` calls return equal JSON bodies and both are 200.
- The second call creates no additional `ProjectResultCache` row (`update_or_create` on the same key).
- Editing a module between the two calls changes `Project.results_stamp` and the second response is recomputed, not served from the first row.
- `?cached=false` bypasses the stored row and still returns 200.
- `?activities=2,1` and `?activities=1,2` hit the same row.
- A user without `view_project` gets the permission error and no cache row is read or created.
  </behavior>
  <action>
1. **New `djangoexact/api/results_cache.py`.** Keep it free of module-level `api.models` imports; import models inside the functions, mirroring the local-import style already used in `api/management/commands/run_async_job.py:33`.
   - `RESULTS_SCHEMA_VERSION = 1`, with a comment next to it stating it must be bumped whenever the assembly or the computation semantics of the project results payload change, otherwise every existing project serves stale numbers forever (research pitfall table).
   - `build_cache_key(activity_pks)`: normalize to `sorted({int(pk) for pk in activity_pks})`, build a descriptor string folding `RESULTS_SCHEMA_VERSION`, `INVENTORY_SCHEMA_VERSION` (imported from `api.reports.cache`), and the comma-joined ids, then return `hashlib.sha256(descriptor.encode("utf-8")).hexdigest()`. Do NOT fold in user identity or language: the research verified `ProjectResultSerializer` is an empty serializer (`api/serializers.py:404-406`) and that the thread fan-out already forces `settings.LANGUAGE_CODE` for every caller. Do NOT fold in a reference-data epoch: bug 1 is deferred by D3, so there is nothing that would advance it.
   - `normalize_payload(response)`: `json.loads(json.dumps(response, cls=JSONEncoder))` using `rest_framework.utils.encoders.JSONEncoder`. Use DRF's encoder specifically, not `DjangoJSONEncoder`, because DRF's `JSONRenderer` renders with it, so the stored payload is guaranteed to render to the same bytes as the live object.
   - `read(project_id, cache_key, stamp)`: filter `ProjectResultCache` on project, key, `results_stamp=stamp`, `schema_version=RESULTS_SCHEMA_VERSION`, then `.values_list("payload", flat=True).first()`. A stale row is filtered out by the stamp mismatch and is never read, so no delete race exists.
   - `write(project_id, cache_key, stamp, payload)`: `update_or_create` on `(project_id, cache_key)` with the stamp, schema version, and payload in `defaults`.
   - `clear_for_projects(project_qs)`: delete `ProjectResultCache` rows whose project is in the queryset. Used by the ops script.

2. **Wire `ProjectViewSet.results` (api/views.py:671-712).** Preserve the existing order: `get` the project, then `security.check_permission` at :682-684. The cache read goes strictly BELOW that check and is never hoisted above it (hard constraint, research Security Domain V4). Then:
   - Move the `activity_pks` computation up from :699 to just after the `selected_activities` parse at :688-690, and materialize it with `list(...)` so it is evaluated once rather than by both the key builder and the fan-out.
   - Read the stamp fresh: `Project.objects.filter(pk=project.pk).values_list("results_stamp", flat=True).first() or 0`. Capture it BEFORE computing. A concurrent edit during compute advances the stamp, so the row this request writes is keyed to the old value and will never be read. That is the intended outcome.
   - Reuse the `cached` query parameter that is already declared in this action's swagger block at api/views.py:662-667: `use_cached = request.query_params.get("cached", "true") == "true"`. This matches `GenericModuleViewSet.results` at api/views.py:2620 and adds no new parameter to the public contract.
   - On hit, `return Response(data=cached_payload, status=http_status.HTTP_200_OK)`. Never 202 (hard constraint).
   - On miss, run the existing assembly untouched, then call `results_cache.write(...)` with `normalize_payload(response)`, then return the ORIGINAL `response` object exactly as today. Wrap only the write in `try/except Exception` with `logging.exception(e)`, so a cache write failure can never change the response the user gets.
   - Do not move, reorder, or reformat the `ProjectResultSerializer` call, the fan-out, or `log_activity_failure`.

3. **Extend `djangoexact/scripts/invalidate_results_cache.py` (D3a).** Add a second function, `invalidate_project_result_caches()`, and call it from `run()` after `cycle_all_modules_and_invalidate_cached_results()`. It selects `Project.objects.filter(is_finalized=False)`, deletes the matching `ProjectResultCache` rows via `results_cache.clear_for_projects`, and bumps their stamps with a single `.update(results_stamp=F("results_stamp") + 1)`. Leave lines 6 to 38 byte-for-byte unchanged, including the finalized carve-out at :18-22 that `api/tests/unit/project.py:1404-1466` pins. Log the count of affected projects with the same `log.debug` style the file already uses.

4. **File the two deferred bugs in `.planning/BACKLOG.md` (D3).** Match the existing entry format exactly: an `###` heading, then a `**P2** · \`bug\` · created 2026-08-10` line, then a `>` blockquote body. One entry for `load_reference_data` performing no invalidation (evidence: no `invalidate_module_caches`, no cache-column `.update()`, and no `clear_reference_caches()` call anywhere in `api/management/commands/load_reference_data.py`; `api/reference_cache.py:70-86` defines `clear_reference_caches()` for exactly this and its docstring at :7-8 says a reload requires it; consequence: changing an IPCC emission factor or GWP coefficient leaves every module cache valid and the API keeps serving the old numbers indefinitely, and the new project-level cache adds one more stale layer above it). One entry for `copy_activity` (evidence: `api/utilities.py:365-427` `copy.deepcopy(module)` then `pk = None`, while `CachedResultMixin.save` only stamps `last_modified` when it is `None` at `api/models.py:1289-1290`; consequence: the copy is born with a valid cache, so a copy into a project with a different country, climate, moisture, soil type, or GWP serves the source project's numbers, and it copies multi-megabyte JSON per module). Both entries must name the D3a mitigation shipped here: `scripts/invalidate_results_cache.py` now clears the project-level rows too.
  </action>
  <verify>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact && ../.venv/bin/python -m py_compile api/results_cache.py api/views.py scripts/invalidate_results_cache.py api/tests/test_results_cache.py api/tests/test_project_results_cache_api.py</automated>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact && DJANGO_DEBUG=True ../.venv/bin/python manage.py test api.tests.test_results_cache -v 2</automated>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact && grep -n "check_permission\|results_cache.read" api/views.py | grep -A2 -B2 "results_cache.read"</automated>
  </verify>
  <done>
    - `py_compile` passes on all five files.
    - `manage.py test api.tests.test_results_cache` runs locally with no database and reports OK.
    - In `api/views.py`, the line number of the `results_cache.read` call inside `ProjectViewSet.results` is greater than the line number of the `security.check_permission` call at :682, confirmed by the grep output.
    - `api/tests/test_project_results_cache_api.py` exists and carries a module docstring stating it requires Postgres and runs in CI only.
    - `djangoexact/scripts/invalidate_results_cache.py` lines 6 to 38 are unchanged, confirmed with `git diff`.
    - `.planning/BACKLOG.md` has two new entries in the file's existing format.
    - Commits: `feat(api): serve project results from a stamped project-level cache`, then `chore(scripts): clear project result caches in the manual invalidation lever`, then `docs(backlog): file reference-data reload and copy_activity cache defects`.
  </done>
</task>

<task type="auto">
  <name>Task 3: Asynchronous recompute via AsyncJob with PENDING dedupe</name>
  <files>djangoexact/api/models.py, djangoexact/api/migrations/0291_asyncjob_results_recompute.py, djangoexact/api/services/results_jobs.py, djangoexact/api/management/commands/run_async_job.py, djangoexact/djangoexact/settings.py, djangoexact/api/tests/test_results_cache.py</files>
  <read_first>
    djangoexact/api/models.py:3507-3555 (AsyncJob, Kind, and the (kind, status) index at :3550),
    djangoexact/api/services/async_jobs.py:23-29 (enqueue plus transaction.on_commit),
    djangoexact/api/management/commands/run_async_job.py (the whole file, note the connection.close() guard at :49-50),
    djangoexact/api/services/report_jobs.py:18-33 (the shape to mirror, and the activate(lang) call at :29 that must NOT be copied),
    djangoexact/djangoexact/settings.py:367 (CLOUD_RUN_COMPUTATION_JOB_NAME)
  </read_first>
  <action>
1. **New job kind.** Add `RESULTS_RECOMPUTE = "results_recompute", "Results recompute"` to `AsyncJob.Kind` (api/models.py:3514-3516). Hand-write `0291_asyncjob_results_recompute.py` with `dependencies = [("api", "0290_projectresultcache")]` and a single `AlterField` on `AsyncJob.kind` carrying the three choices. This is a no-op at the database level but Django requires the migration for state consistency.

2. **Feature gate.** Add near djangoexact/settings.py:367:
   `RESULTS_RECOMPUTE_ENABLED = os.environ.get("RESULTS_RECOMPUTE_ENABLED", "").lower() in ("true", "1") or bool(CLOUD_RUN_COMPUTATION_JOB_NAME)`
   with a comment explaining why. Rationale: `api/services/async_jobs.py:32-38` falls back to `_dispatch_subprocess` when `CLOUD_RUN_COMPUTATION_JOB_NAME` is empty, which is exactly the local and CI condition, and per-edit enqueue would then spawn a subprocess for every module save in the test suite. Defaulting to the presence of a real Cloud Run target keeps production enabled and local/CI quiet, with an explicit env override for anyone who wants to exercise the path locally.

3. **New `djangoexact/api/services/results_jobs.py`.** Three public callables.
   - `schedule_recompute(project_id)`: returns immediately unless `settings.RESULTS_RECOMPUTE_ENABLED`, then `transaction.on_commit(lambda: _enqueue_if_idle(project_id))`. Post-commit is mandatory (hard constraint, mirroring `api/services/async_jobs.py:28`), never inline in the save. Running post-commit also means the callback reads the FINAL stamp after every bump in that transaction.
   - `_enqueue_if_idle(project_id)`: skip when `AsyncJob.objects.filter(project_id=project_id, kind=AsyncJob.Kind.RESULTS_RECOMPUTE, status__in=[AsyncJob.Status.PENDING, AsyncJob.Status.RUNNING]).exists()` (D2, served by the `(kind, status)` index at api/models.py:3550). Otherwise read the current stamp and call `async_jobs.enqueue(kind=AsyncJob.Kind.RESULTS_RECOMPUTE, params={"project_id": project_id, "results_stamp": stamp}, project_id=project_id)`. Recording the stamp in `params` is what lets a late worker detect it was superseded (D2). Wrap the whole body in `try/except Exception` with `log.exception(e)`: a failure to warm a cache must never surface as a request error, because this runs after commit on a user's write.
   - `is_superseded(job_stamp, current_stamp)`: a pure function, `job_stamp is not None and current_stamp != job_stamp`. Kept separate so it is testable without a database.
   - `run(job)`: the worker entry point.
     - Load the project and re-read `results_stamp`. If `is_superseded(...)`, return `{"skipped": "superseded", "job_stamp": ..., "current_stamp": ...}` without writing anything.
     - **Do NOT call `activate()`.** Copying `api/services/report_jobs.py:29` would write a localized payload into a key that assumes `settings.LANGUAGE_CODE` and then serve non-English text to every user (hard constraint). Add a comment at the point where `report_jobs` would have called it, explaining the omission is deliberate.
     - Reproduce the request path rather than reimplementing it, so the warmed payload cannot drift from what the endpoint would compute. Build a request with `rest_framework.test.APIRequestFactory().get(f"/api/projects/{project.pk}/results/")`, `force_authenticate(request, user=project.owner)`, wrap it in `rest_framework.request.Request` with the viewset's parsers, instantiate `ProjectViewSet`, set `view.request`, `view.format_kwarg = None`, `view.kwargs = {"pk": project.pk}`, and call `view.results(request, pk=project.pk)`. `project.owner` passes `check_permission("view_project", ...)`, and the research verified the payload carries no per-user field, so the actor choice cannot leak into the bytes. Warm only the all-activities key (no `activities` parameter), which is the key the endpoint serves by default.
     - The view itself performs the `results_cache.write`, so `run` does not write the cache a second time. Return `{"project_id": ..., "results_stamp": ..., "status_code": response.status_code}`.
     - Treat a non-200 `status_code` as a failure by raising, so the job is recorded FAILED rather than silently reported COMPLETED.

4. **Wire the worker.** Add an `elif job.kind == AsyncJob.Kind.RESULTS_RECOMPUTE:` branch to `run_async_job.py:32-39` importing `api.services.results_jobs` locally, matching the two existing branches. Do not touch the `finally` block or the report-notification block at :60-74: the notification is guarded by `if job.kind == AsyncJob.Kind.REPORT`, so a recompute job sends no email. The forked-connection guard at :49-50 already covers the new branch.

5. **Wire the trigger.** Add the enqueue to `bump_project_results_stamp` in api/models.py, after the `.update()`, using a function-body import (`from api.services import results_jobs`) to avoid a models/services import cycle, and wrapped so it cannot raise into the caller. Add a comment noting the two loop-breakers: the recompute worker writes only `ProjectResultCache` rows, which never bump the stamp, and the stamp write and the payload write are separate code paths by construction (hard constraint).

6. **Extend `api/tests/test_results_cache.py`** with `SimpleTestCase` coverage for `is_superseded`: `None` job stamp is never superseded, equal stamps are not superseded, a lower job stamp is superseded. These stay database-free so the local gate keeps working.
  </action>
  <verify>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact && ../.venv/bin/python -m py_compile api/models.py api/migrations/0291_asyncjob_results_recompute.py api/services/results_jobs.py api/management/commands/run_async_job.py djangoexact/settings.py api/tests/test_results_cache.py</automated>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact && DJANGO_DEBUG=True ../.venv/bin/python manage.py makemigrations --check --dry-run 2>&1 | grep -icE "asyncjob"</automated>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact && DJANGO_DEBUG=True ../.venv/bin/python manage.py test api.tests.test_results_cache -v 2</automated>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact && grep -vE "^\s*#" api/services/results_jobs.py | grep -c "activate("</automated>
  </verify>
  <done>
    - `py_compile` passes on all six files.
    - The `makemigrations --check` grep prints `0` for `asyncjob`.
    - `manage.py test api.tests.test_results_cache` runs locally with no database and reports OK, now including the `is_superseded` cases.
    - The comment-stripped grep for `activate(` in `api/services/results_jobs.py` prints `0`, proving the localization trap was not reproduced.
    - `run_async_job.py` dispatches `RESULTS_RECOMPUTE` and its `finally` block is unchanged.
    - Commit: `feat(api): recompute project results asynchronously after invalidation`
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client to API | `GET /api/projects/{id}/results/` carries an attacker-controlled `activities` query parameter and an authenticated identity |
| request path to stored payload | a cached row is served to a later request under a different identity |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-nlo-01 | Information Disclosure | `ProjectViewSet.results` cache read | critical | mitigate | The cache read sits strictly below `security.check_permission` at api/views.py:682-684, so every request is authorized on its own. The row is keyed by project only, and the payload carries no per-user field (`ProjectResultSerializer` is empty at api/serializers.py:404-406). Task 2 `<done>` asserts the ordering by line number. |
| T-nlo-02 | Denial of Service | cache key space | medium | mitigate | The key is built from the parsed and `isdigit`-filtered pk list at api/views.py:688-699 and then intersected with the project's own activities, never from the raw query string, so junk input cannot pivot the key space. Ordering and duplicates are canonicalized, and `unique_together` on `(project, cache_key)` bounds rows per key. |
| T-nlo-03 | Tampering | stale payload served after an edit | high | mitigate | `results_stamp` is part of the read filter, so a row written before the edit is not selectable. The bump is atomic via `F("results_stamp") + 1`. Task 1 covers the two previously uncovered delete paths. |
| T-nlo-04 | Denial of Service | per-edit job enqueue | medium | mitigate | PENDING/RUNNING dedupe per `(project, kind)` (D2) plus the post-commit callback collapse, plus `RESULTS_RECOMPUTE_ENABLED` defaulting off wherever no Cloud Run target exists so the local subprocess fallback cannot fork per save. |
| T-nlo-05 | Tampering | stale IPCC reference data above the new layer | high | accept | Bug 1 is deferred by D3. Accepted with the D3a mitigation shipped in Task 2: `scripts/invalidate_results_cache.py` now clears the project-level rows and bumps stamps, giving ops a manual lever, and the defect is filed in `.planning/BACKLOG.md`. |
| T-nlo-SC | Tampering | package installs | n/a | n/a | No packages are added. No `pip install` step exists in this plan, so no legitimacy gate is required. |
</threat_model>

<verification>
Local, runnable in this sandbox:
1. `py_compile` clean across every touched Python file.
2. `manage.py makemigrations --check --dry-run` reports nothing about `ProjectResultCache`, `results_stamp`, or `AsyncJob`. The pre-existing `ef_source` drift is expected and out of scope.
3. `manage.py test api.tests.test_results_cache` passes without a database.
4. The auditlog exclusion assertion passes.
5. `git diff | grep -cP "\x{2014}"` prints `0` (the project rule bans that punctuation mark in code, comments, docs, and commit messages; the check is written with a PCRE escape so the file itself stays clean).

CI or a Postgres-equipped machine, not runnable here:
6. `manage.py test api.tests.test_project_results_cache_api`
7. `manage.py test api.tests.unit.project` (pins the finalized-project carve-out at api/tests/unit/project.py:1404-1466)
8. `manage.py test api.tests.test_async_jobs`
9. `manage.py migrate` applies 0290 and 0291 cleanly.
</verification>

<success_criteria>
- The results endpoint returns 200 with the same payload shape on hit and on miss, and never 202.
- A hit is byte-equivalent to a miss for the same project and activity selection.
- Every project, activity, and module write path listed as covered in `<scope_dispositions>` advances `results_stamp`.
- Exactly one recompute job exists per project while one is PENDING or RUNNING.
- A superseded worker exits without writing.
- `scripts/invalidate_results_cache.py` clears both layers and still skips finalized projects.
- Two backlog entries are filed for the deferred bugs.
- No new package is added anywhere.
</success_criteria>

<output>
Write `.planning/quick/260810-nlo-cache-project-results-with-invalidation-/260810-nlo-SUMMARY.md` when done, recording: which tasks landed, the minitool grep result and its ruling, the migration numbers used, and every verification command that was actually executed with its outcome, clearly separating locally-run from CI-gated.
</output>
