# Quick Task 260810-nlo: Cache Project Results with Invalidation and Async Recompute - Research

**Researched:** 2026-08-10
**Domain:** Django result caching, cache invalidation, async recompute on App Engine Standard
**Confidence:** HIGH on current-state findings (all read from source this session), MEDIUM on the GCP topology recommendations

## Summary

The user's ask is **already half-built**. A persistent, per-module result cache exists and is fully wired: JSON columns on every module row, a `last_cached_at > last_modified` validity rule, and a cascade that bulk-invalidates modules when a Project or Activity changes. What does not exist is any **project-level or activity-level cached payload**. `GET /api/projects/{id}/results/` re-derives the whole response on every call, and on a fully warm cache it still pays for thread fan-out, one query per module type per activity, a `get_object_or_404` per module, a full write-serializer `is_valid()` per module, and a permission check per module. That per-request assembly cost, not the IPCC math, is what makes the endpoint slow.

So the work is **extend, not duplicate**: add one project-scoped cache row holding the assembled response, keyed by a monotonic stamp that the existing invalidation cascade already knows how to bump. The module cache stays exactly as-is and becomes the warm inner layer that makes recompute cheap.

Two correctness landmines exist in the current cache and must be fixed as part of this work, because a project-level cache amplifies both: reloading IPCC reference data invalidates nothing, and `copy_activity` deep-copies a valid cache into the copy.

**Primary recommendation:** Add a `ProjectResultCache` model plus a `Project.results_stamp` counter bumped by the existing `invalidate_module_caches` call sites. Read path stays synchronous compute-on-miss (never 202) so the frontend contract is untouched. Async recompute reuses the existing `AsyncJob` + Cloud Run job pattern, coalesced by a Cloud Scheduler sweep rather than one job per edit. Do not introduce Redis, Celery, or django-q2.

## Project Constraints (from CLAUDE.md and PROJECT.md)

- Never use em-dashes anywhere in this repo.
- Public API contract must not change: the WebApp frontend depends on endpoint shapes and result formats.
- Calculation results for currently-correct paths must not change.
- Python 3.11, Django 5.2.17 (`djangoexact/requirements.txt:9`), DRF 3.16.1. Production is App Engine Standard `python311`.
- No pytest-django. Django-dependent tests use `TestCase` / `APITestCase`.
- Local sandbox has no Postgres or Docker. `py_compile` is the only reliable local gate.
- Conventional commits, feature branch off `develop`.
- `nyquist_validation: false` in `.planning/config.json`, so no Validation Architecture section here.

## Current State: What Already Exists

### The module-level cache (fully built, in production)

`CachedResultMixin` at `djangoexact/api/models.py:1275-1370` is the entire existing mechanism.

Cache columns, verbatim from `api/models.py:1279-1286`:

```
    updated_at = models.DateTimeField(auto_now=True, null=True, verbose_name="updated_at")
    last_cached_at = models.DateTimeField(null=True, blank=True, verbose_name="last_cached_at")
    cached_results_total = models.JSONField(null=True, blank=True, verbose_name="cached_results_total")
    cached_results_by_activity = models.JSONField(null=True, blank=True, verbose_name="cached_results_total")
    cached_results_by_gas = models.JSONField(null=True, blank=True, verbose_name="cached_results_total")
    cached_results_by_activity_by_gas = models.JSONField(null=True, blank=True, verbose_name="cached_results_total")
    cached_units_breakdown = models.JSONField(null=True, blank=True, verbose_name="cached_units_breakdown")
    last_modified = models.DateTimeField(auto_now=False, null=True, blank=True, verbose_name="last_modified")
```

[VERIFIED: djangoexact/api/models.py:1279-1286]

Validity rule, verbatim from `api/models.py:1342-1343`:

```
    def is_cached_results_valid(self):
        return self.last_cached_at is not None and self.last_cached_at > self.last_modified
```

[VERIFIED: djangoexact/api/models.py:1342-1343]

| Concern | Where | Granularity |
|---------|-------|-------------|
| Cache read | `api/views.py:2619` `module.get_cached_results(by=aggregate_by)` | one module, one breakdown |
| Cache write | `api/views.py:2645` `module.cache_results(...)` | writes all four breakdowns at once |
| Stamp bump on edit | `api/models.py:1288-1309` (`CachedResultMixin.save`, dirtyfields-driven) | per module |
| Project cascade | `api/models.py:752-768` calls `invalidate_module_caches(project=self)` | bulk UPDATE per concrete Module subclass |
| Activity cascade | `api/models.py:1169-1181` calls `invalidate_module_caches(activity=self)` | same |
| Bulk invalidator | `api/models.py:637-660` | iterates `apps.get_app_config("api").get_models()` |
| Submodule to parent | `api/models.py:1305-1307` (save) and `api/models.py:1366-1370` (delete) | per parent module |
| LUC cross-module | `api/models.py:1357-1364`, called at `api/views.py:2473` and `api/views.py:2501` | LUC plus all its member modules |

Persistence is **Postgres rows**, not `django.core.cache`. That is the right call for this data and the new layer should follow it.

### The report pipeline's second cache adapter

`djangoexact/api/reports/cache.py` is a separate adapter over the same columns, used by the WeasyPrint/Excel path. Verbatim from `api/reports/cache.py:23` and `:31-40`:

```
INVENTORY_SCHEMA_VERSION = 2
```

```
INVENTORY_ROLLUP_FIXED_MODULES = frozenset({
    "Input",
    "Energy",
    "Irrigation",
    "Storage",
    "Processing",
    "Packaging",
    "Transport",
    "OrganicSoil",
})
```

[VERIFIED: djangoexact/api/reports/cache.py:23, :31-40]

The version gate lives at `api/reports/cache.py:116-122`: a cached payload whose `inventory_schema` is below `INVENTORY_SCHEMA_VERSION` is rejected, but **only for the eight module names in that frozenset**. `save_results_to_cache` stamps `"inventory_schema": INVENTORY_SCHEMA_VERSION` into the payload (`api/reports/cache.py:206`). `CacheWriteBatch` (`api/reports/cache.py:43-88`) coalesces cold-path writes into one `bulk_update` per concrete class, flushed by `BaseProjectReport.compute` (`api/reports/base.py:308-314`).

**This is the pattern to absorb, not reinvent.** The new project-level cache needs the same idea generalized: a `RESULTS_SCHEMA_VERSION` that is unconditional, not scoped to a name list. The scoped frozenset was a deliberate one-time cost-control hack for a specific fix; it is not a general design.

### What does NOT exist

There is **no project-level or activity-level cached payload anywhere**. `ProjectViewSet.results` (`api/views.py:671-712`) assembles the response fresh every call:

- `api/views.py:706` fans out over activities via `concurrency.map_in_bounded_threads`, bounded at `SERIALIZATION_MAX_WORKERS = 4` (`api/concurrency.py:45`). Each worker opens its own Postgres connection (`api/concurrency.py:1-17`).
- Each worker calls `ActivityViewSet.results` (`api/views.py:2114-2146`), which loops `activity.modules` at `api/views.py:2128`.
- `activity.modules` resolves to `__get_all_modules` (`api/models.py:1216-1237`), which runs **one query per module type on the activity**.
- Per module, `api/views.py:2135` calls into `GenericModuleViewSet.results`, which does `get_object_or_404(model, pk=pk)` (`api/views.py:2597`), a `security.check_permission` (`api/views.py:2600`), and constructs a write serializer then calls `serializer.is_valid(raise_exception=True)` (`api/views.py:2604-2605`) purely to read.

Only after all of that does line 2619 consult the module cache. **A 100 percent cache hit still pays every one of those costs.** This is independently corroborated in `.planning/BACKLOG.md:130`, which names defect "5gq (results-view get_object_or_404 query explosion)".

### `django.core.cache` state

`django.core.cache` is used at `api/views.py:2985` and `:3000` (APIHealthView), `api/views.py:3125` and `:3137` (HandInHand list), `minitool/views.py:324` and `:371`, and `api/signals.py:16`.

**No `CACHES` setting exists anywhere in the repository.** A grep across `*.py`, `*.yaml`, `*.yml`, and `.env*` returned zero hits. Django therefore falls back to its documented default, `LocMemCache` [CITED: https://docs.djangoproject.com/en/5.2/ref/settings], which is per-process [CITED: https://docs.djangoproject.com/en/5.2/topics/cache].

That means those existing caches are **already per-gunicorn-worker**: `app.yaml:5` runs `gunicorn -b :$PORT -w 4`, and `app.yaml:36-37` sets `automatic_scaling: min_idle_instances: 1` with no instance cap. So there are at minimum 4 independent copies per instance, times N autoscaled instances. This confirms the premise in the task focus: **local-memory cache cannot be the source of truth for project results.** It is fine for the 60-second health blob; it is not fine for results.

### Existing async plumbing (reusable as-is)

| Piece | Location | Note |
|-------|----------|------|
| `AsyncJob` model | `api/models.py:3507-3554` | has `kind`, `status`, `progress`, `params`, `result`, `project` FK, indexes on `status` and `(kind, status)` |
| Enqueue + post-commit dispatch | `api/services/async_jobs.py:23-29` | `transaction.on_commit(lambda: dispatch(job.pk))` |
| Cloud Run dispatch | `api/services/async_jobs.py:41-74` | overrides container args on the existing `exact-computation-job`, no new GCP resource |
| Local subprocess fallback | `api/services/async_jobs.py:77-102` | selected when `CLOUD_RUN_COMPUTATION_JOB_NAME` is empty |
| Worker entrypoint | `api/management/commands/run_async_job.py` | dispatches on `job.kind`, idempotent PENDING guard, full try/except/finally status write |
| Stuck-job sweep | `api/management/commands/reconcile_stale_async_jobs.py` | `STALE_THRESHOLD = timedelta(hours=1)` |
| Poll endpoint | `api/views.py:3142` `AsyncJobViewSet` | already the frontend's polling contract |
| 202 precedent | `api/views.py:773-813` `report_async` | returns `{"job_id":..., "status":...}` with `HTTP_202_ACCEPTED` |

`AsyncJob.Kind` today, verbatim from `api/models.py:3514-3516`:

```
    class Kind(models.TextChoices):
        REPORT = "report", "Report generation"
        PROJECT_COPY = "project_copy", "Project copy"
```

[VERIFIED: djangoexact/api/models.py:3514-3516]

**Verdict: this pattern fits the ask directly.** Adding a third `Kind` is a one-line model change plus one `elif` in `run_async_job.py`. No new dependency, no broker, no worker host.

## Pre-existing Correctness Bugs the New Layer Must Not Inherit

### 1. Reference-data reload invalidates nothing (HIGH)

`api/management/commands/load_reference_data.py` contains no call to `invalidate_module_caches`, no `.update()` on cache columns, and no call to `clear_reference_caches`. A grep for `cache_clear|invalidate` across `api/management/commands/*.py` returned zero hits.

Meanwhile `api/reference_cache.py:70-86` defines `clear_reference_caches()` explicitly for this purpose, and its own docstring at `api/reference_cache.py:7-8` states: "Reloading reference data requires a process restart or calling clear_reference_caches()." Nothing calls it from the loader.

Consequence today: changing an IPCC emission factor or a GWP coefficient leaves every module cache `valid`, and the API keeps serving numbers derived from the old factors indefinitely. A project-level cache makes this strictly worse because there is one more stale layer above it.

### 2. `copy_activity` copies a valid cache (MEDIUM)

`api/utilities.py:365-427` uses `copy.deepcopy(module)` then sets `pk = None`. The deepcopy carries `last_cached_at`, `last_modified`, and all `cached_results_*` blobs. `CachedResultMixin.save()` only stamps `last_modified` when it is `None` (`api/models.py:1289-1290`), and here it is not `None`. So the copy is born with a **valid** cache.

Inside `copy_project` (`api/utilities.py:261-269`) the target is a clone of the source, so the numbers happen to agree. But `copy_activities_into(source_project, target_project, owner)` (`api/utilities.py:255-258`) is generic in its signature, and `ActivityViewSet.copy` (`api/views.py:2200-2217`) also copies. Any copy into a project with a different country, climate, moisture, soil type, or GWP would serve the source project's numbers. It also copies multi-megabyte JSON per module.

### 3. `AUDITLOG_INCLUDE_ALL_MODELS=True` audits every cache write (MEDIUM)

`.planning/BACKLOG.md:148-152` documents this: every `module.save()` that writes `cached_results_*` creates an auditlog `LogEntry` that deep-copies the multi-megabyte JSON. Any new cache write path must avoid re-triggering it. Note the existing code already dodges this via `skip_history_when_saving` (`api/reports/cache.py:218-219`) for simple-history, but that is a different library from auditlog.

### 4. Cached inventory already diverges from cached balance (MEDIUM)

`.planning/BACKLOG.md:233-243` records two open defects where cached inventory and cached balance disagree (SetAside, Settlement). Caching the assembled project payload will freeze whichever value is currently served. Not a blocker, but it means "cached output equals live output" is not a safe assumption for a verification test on those two module types.

## Full Write-Path Inventory (what must bump the stamp)

| Path | Location | Covered today? | Notes |
|------|----------|----------------|-------|
| Module create/update via serializer | `api/views.py:2463-2505` | yes | goes through `CachedResultMixin.save()` |
| Submodule save/delete | `api/models.py:1305-1307`, `:1366-1370` | yes | bumps parent |
| LUC member changes | `api/views.py:2473`, `:2501` | yes | explicit `invalidate_luc_results()` |
| `Project.save()` | `api/models.py:752-768` | yes | excludes lifecycle flags, see below |
| `Activity.save()` | `api/models.py:1169-1181` | yes | excludes `cost`, `description`, `name`, `owner`, `updated_at` |
| **Top-level Module delete** | `api/models.py:1366-1370` | **NO** | `delete()` only handles the Submodule case; deleting a Module never touches Activity or Project |
| **Activity delete** | n/a | **NO** | no project-level notification exists |
| **`queryset.update()` / `bulk_update` / `bulk_create`** | see below | **NO** | Django confirms `.update()` bypasses `save()`, `pre_save`, `post_save`, and `auto_now` [CITED: https://docs.djangoproject.com/en/5.2/topics/db/queries] |
| **`load_reference_data`** | `api/management/commands/load_reference_data.py` | **NO** | see bug 1; invalidates EVERYTHING logically |
| **`loaddata` / fixture loads** | Django builtin | **NO** | fixture loading sends `post_save` with `raw=True` and bypasses custom `save()` |
| **Admin bulk actions** | django-unfold | **NO** | single-object admin saves do go through `save()`; queryset-based actions do not |
| Project copy | `api/utilities.py:365-427` | partial | see bug 2 |
| Minitool changes import | `api/services/minitool_changes_import.py:293` | **NO** | `bulk_create(update_conflicts=True, ...)` |
| LUC compute job | `api/services/luc_compute.py:77` | yes | uses `instance.save()` |
| Manual `invalidate_results_cache` script | `scripts/invalidate_results_cache.py:24-32` | n/a | uses `.update()`, and **deliberately skips finalized projects** (`:18-22`) |
| Direct SQL / Cloud SQL console | n/a | **NO** | accept as out of scope, document it |

Note the finalized-project carve-out at `scripts/invalidate_results_cache.py:18-22` and its pinning test at `api/tests/unit/project.py:1404-1466`. A finalized project's cache is treated as immutable by design. The new layer must honour the same rule or that test will fail.

## Recommended Design

### Storage: a dedicated model, not `django.core.cache`

| Option | Verdict | Reasoning |
|--------|---------|-----------|
| `LocMemCache` (today's default) | **Rejected** | per-process; 4 gunicorn workers times N autoscaled instances means N*4 divergent copies and a near-zero hit rate |
| Cloud Memorystore / Redis | **Rejected for now** | Memorystore is private-IP only, so App Engine Standard requires a **Serverless VPC Access connector**, a new billed always-on resource plus FAO IT network sign-off. Results payloads are multi-megabyte, a poor fit for a small Redis tier. `.planning/STATE.md:85` already lists "confirm ... Memorystore/Redis availability" as an **unresolved** Phase 4 blocker, so this would block on an open question. [ASSUMED: the VPC connector requirement, from platform knowledge, not verified against GCP docs this session] |
| `DatabaseCache` via `createcachetable` | **Rejected** | the DB cache backend culls entries on `MAX_ENTRIES`, so results could be silently evicted; the opaque key/value/expires schema is not queryable or inspectable; no FK cascade on project delete |
| **`ProjectResultCache` model** | **Recommended** | FK cascade delete for free, queryable and admin-inspectable, can carry stamp and recompute-state columns, matches the existing "cache lives in Postgres rows" pattern already proven by `CachedResultMixin` |

Sketch (illustrative, all field names are new and therefore `[ASSUMED]`):

```python
class ProjectResultCache(models.Model):
    project = models.ForeignKey("api.Project", on_delete=models.CASCADE, related_name="result_caches")
    cache_key = models.CharField(max_length=200, db_index=True)
    results_stamp = models.BigIntegerField()
    schema_version = models.PositiveIntegerField()
    payload = models.JSONField()
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "cache_key")
```

Keep it out of auditlog and simple-history registration (bug 3).

### Invalidation: a monotonic stamp, not a delete sweep

Add `Project.results_stamp = models.BigIntegerField(default=0)`. Bump it with an atomic `F("results_stamp") + 1` at exactly the points that already call `invalidate_module_caches`, which centralizes the change:

- inside `invalidate_module_caches` itself (`api/models.py:637-660`), covering both the Project and Activity cascades in one edit
- plus the currently-uncovered paths from the table above

Because the stamp is part of the cache key, a stale row is **never read**. No delete race, no cache-key sweep needed under load, and a background job cannot clobber a newer entry. Old rows are reaped by a periodic sweep, which is a cost concern rather than a correctness one.

Ranked against the alternatives:

1. **Stamp bumped in the existing cascade (recommended).** Reuses machinery that already exists and is already tested. Explicit, greppable, no signal magic.
2. **Explicit service-layer invalidation calls.** Equivalent correctness, but spreads call sites across views, serializers, services, and commands. More places to forget.
3. **`post_save` / `post_delete` / `m2m_changed` signals.** Tempting because it catches paths nobody remembered, but it has exactly the blind spots that matter here: `.update()`, `bulk_create`, `bulk_update`, raw SQL, and `loaddata` (which fires `post_save` with `raw=True`). It also fires on the cache write itself, which needs a guard to avoid an infinite bump loop. The repo already prefers explicit invalidation over signals: the only signal receiver in `api/` is `api/signals.py:15-17`, a three-line health-cache delete.

Cover the blind spots explicitly rather than hoping a signal catches them:

- `load_reference_data`: bump a **global** reference epoch (a `ConfigParam` row or a dedicated singleton) that is folded into every cache key, and call `clear_reference_caches()` (`api/reference_cache.py:70`). This fixes bug 1 at the same time.
- Top-level `Module.delete()` and `Activity.delete()`: add a project stamp bump.
- `minitool_changes_import` bulk path: bump after the `bulk_create`.
- `copy_activity`: null the cache columns on the copy. This fixes bug 2 and removes the multi-megabyte copy cost.

### Cache key contents

The key must fold in every input that can change the bytes:

| Component | Source | Why |
|-----------|--------|-----|
| `project.pk` | request | scope |
| `project.results_stamp` | new column | any project/activity/module change |
| reference-data epoch | new global | IPCC factor or GWP table changes |
| sorted selected activity ids | `api/views.py:688-690` | the `activities` query param subsets the response |
| `RESULTS_SCHEMA_VERSION` | new constant | any change to assembly or computation semantics |
| `INVENTORY_SCHEMA_VERSION` | `api/reports/cache.py:23` | inventory contributions changed |

**Deliberately excluded, and why:**

- **User identity.** Verified safe: `ProjectResultSerializer` is an empty `serializers.Serializer` with a bare `pass` (`api/serializers.py:404-406`), so its `.data` is `{}`. `ActivityResultSerializer` (`api/serializers.py:777-780`) exposes only `name` and `cost`. The payload carries no per-user field. Permission is checked before the cache read (`api/views.py:682-684`), so authorization still happens per request.
- **Language.** Verified safe **because of an existing quirk**: `map_in_bounded_threads` always runs `func` on a worker thread, and a worker inherits no active language, so modeltranslation fields always render in `settings.LANGUAGE_CODE` regardless of `Accept-Language`. This is documented at `api/concurrency.py:50-63` and `:78-83` and pinned by a test. So today's project results payload is always English.
- **`aggregate` param.** Not read by `ProjectViewSet.results`; it is a `GenericModuleViewSet.results` parameter (`api/views.py:2618`). Confirm against the frontend before finalizing.

**Trap:** `report_jobs.run` calls `activate(lang)` at `api/services/report_jobs.py:29`. If a recompute worker copies that line, it will write a **localized** payload into a cache key that assumes English, and non-English text will then be served to every user. The recompute worker must reproduce the request path's language conditions exactly, meaning no `activate()` call.

### Read path on miss: compute synchronously, never 202

**Recommended: compute-on-miss, store, return 200.** Identical to what the module cache does today at `api/views.py:2622-2645`.

- Returning 202 from `GET /api/projects/{id}/results/` would break the frontend contract, which PROJECT.md explicitly forbids. The async 202 pattern already exists but is scoped to `POST .../report/async` (`api/views.py:773-813`), a different endpoint the frontend already polls.
- **Reject stale-while-revalidate as the default.** For a GHG calculator, serving the previous numbers right after a user edits an input is worse than being slow: the user sees their change silently ignored. If wanted at all, gate it behind an explicit opt-in query param, defaulting off.

Stampede protection: `select_for_update(skip_locked=True)` on the cache row inside `transaction.atomic` [CITED: https://docs.djangoproject.com/en/5.2/ref/models/querysets]. Note the current code already tolerates duplicate concurrent compute, so this is an improvement rather than a prerequisite.

### Async recompute: reuse AsyncJob, coalesce via a scheduled sweep

**Recommended shape:**

1. Add `RESULTS_RECOMPUTE = "results_recompute", "Results recompute"` to `AsyncJob.Kind` (`api/models.py:3514-3516`) and an `elif` branch in `run_async_job.py`.
2. Add `api/services/results_jobs.py` mirroring `report_jobs.py`: load project, re-read the current `results_stamp`, compute, write the cache row.
3. **Do not enqueue one job per edit.** A module PATCH is a single field change and a user filling a form fires many. Cloud Run Jobs have no native delay, so per-edit dispatch would fan out badly.

**Debounce strategy (recommended):** dirty flag plus scheduled sweep.

- Bumping `Project.results_stamp` is itself the dirty flag: the project is dirty whenever `results_stamp` differs from the newest `ProjectResultCache.results_stamp`.
- A new management command, `recompute_dirty_project_results`, selects dirty projects and enqueues at most one `AsyncJob` each. Run it from Cloud Scheduler on a few-minute cadence. All edits inside the window coalesce into a single recompute, for free.
- This reuses a pattern the repo already has: `reconcile_stale_async_jobs` and `cleanup_expired_reports` are both scheduler-driven management commands.

**Job-level dedupe (belt and braces):** before enqueuing, skip if a `PENDING` or `RUNNING` job already exists for that project and kind. The `(kind, status)` index at `api/models.py:3550` already supports this query. Record the stamp in `params` so the worker can detect it has been superseded and exit early.

**Rejected alternatives:**

| Option | Verdict |
|--------|---------|
| Celery | needs a broker (Memorystore or Pub/Sub) plus a long-lived worker host. Two new billed resources plus a new dependency. |
| django-q2 | needs a broker and a worker process. The DB broker option means constant polling against Cloud SQL. |
| `threading` after response | App Engine Standard may freeze or reclaim the instance once the response is sent. Also, `api/concurrency.py:1-17` documents that each thread opens its own Postgres connection, and the old per-module thread fan-out already caused a connection exhaustion outage (`api/models.py:640-645`). |
| Cloud Tasks | viable and would give native scheduled delay, i.e. real debounce for free. But it is a new GCP resource and a new client dependency, where the existing AsyncJob path costs nothing. Worth naming as the upgrade path if the sweep cadence proves too coarse. |

## Common Pitfalls

| Pitfall | Mitigation |
|---------|-----------|
| Forgetting to bump `RESULTS_SCHEMA_VERSION` when computation semantics change | Every existing project serves stale numbers forever. Put the constant next to `INVENTORY_SCHEMA_VERSION` with a comment, and add a checklist line to the calculators' contributing notes. |
| Scoping the version gate to a module name list | `INVENTORY_ROLLUP_FIXED_MODULES` (`api/reports/cache.py:31-40`) was a deliberate one-time cost-control hack. Do not generalize it. The new gate must be unconditional. |
| Auditlog bloat on cache writes | See bug 3. Exclude the new model from auditlog registration; verify with a save-count test. |
| The recompute worker calling `activate(lang)` | Copies a line from `report_jobs.py:29` and poisons the cache with a localized payload. |
| Recompute worker reusing a forked DB connection | `run_async_job.py` already handles this with a `connection.close()` guarded by `if not connection.in_atomic_block`. Mirror it. |
| Bumping the stamp inside the cache write | Infinite recompute loop. The stamp write and the payload write must be distinct code paths, exactly as `cache_fields` is excluded from the dirty check at `api/models.py:1294-1302`. |
| Breaking the finalized-project carve-out | `api/tests/unit/project.py:1404-1466` pins that finalized projects keep their cache. Honour it in the new layer. |
| Non-atomic stamp bump | Use `F("results_stamp") + 1`, never read-modify-write, or concurrent edits will lose bumps. |
| Cache rows growing unbounded | Stamp-keyed rows accumulate one per edit. The sweep command must delete rows whose stamp is behind the project's current stamp. |

## Environment Availability

| Dependency | Required by | Available | Notes |
|------------|-------------|-----------|-------|
| Postgres / Cloud SQL | cache storage | yes | already the primary DB |
| Cloud Run Job `exact-computation-job` | async recompute | yes | `CLOUD_RUN_COMPUTATION_JOB_NAME` templated at `djangoexact/app.yaml:32` |
| Cloud Scheduler | debounce sweep | [ASSUMED] yes | `reconcile_stale_async_jobs` was built for it (`.planning/quick/20260717-async-report-project-copy/IMPLEMENTATION-PLAN.md:559`), but no `cron.yaml` is checked in and no scheduler job definition was found in the repo. **Confirm the job actually exists in GCP before depending on the cadence.** |
| Redis / Memorystore | not needed | no | zero references anywhere in the repo |
| Local Postgres | running the test suite | no | dev sandbox constraint; `py_compile` is the local gate |

## Package Legitimacy Audit

**Not applicable. This design adds no external packages.** Everything recommended uses Django 5.2 builtins plus machinery already in the repo. That is a deliberate goal, not a coincidence: it keeps the change inside "Django's limits and Django tech" as the user asked, and it avoids the Serverless VPC connector, broker, and worker-host costs that every third-party queue would drag in.

## Security Domain

| ASVS category | Applies | Control |
|---------------|---------|---------|
| V4 Access Control | **yes** | The cache row is keyed by project, not by user. Permission MUST be checked on every request before the cache is read. `api/views.py:682-684` already does this and must stay ahead of any cache lookup. Never move the cache read above the permission check. |
| V5 Input Validation | yes | `activities` query param already validated by `.isdigit()` at `api/views.py:688`. The cache key must use the **parsed and filtered** ids (`api/views.py:699`), never the raw string, or an attacker could pivot the key space with junk input. |
| V2 Authentication | no change | untouched |
| V6 Cryptography | no | no secrets in the payload |

Also: the cache key must be built from a canonical, sorted representation of the activity id set, so `?activities=2,1` and `?activities=1,2` collapse to one entry rather than two.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | Memorystore on App Engine Standard requires a Serverless VPC Access connector | Storage options | If Redis is actually reachable without one, the Redis option becomes more attractive, though the multi-megabyte payload objection still stands |
| A2 | A Cloud Scheduler job for `reconcile_stale_async_jobs` exists in GCP | Environment | The debounce sweep would silently never run. **Verify before planning.** |
| A3 | The frontend does not pass an `aggregate` param to the project results endpoint | Cache key | Missing key dimension leads to wrong-breakdown responses. Verify against the WebApp. |
| A4 | Field names in the `ProjectResultCache` sketch | Design | Naming only, no correctness impact |
| A5 | Django admin bulk actions on modules exist and use `queryset.update()` | Write paths | If no such action exists, one blind spot disappears |

## Open Questions

1. **Is the Cloud Scheduler job actually provisioned?** No `cron.yaml` is checked in and nothing in `.github/workflows/deploy.yaml` creates a scheduler job. If it is not provisioned, the sweep-based debounce has no trigger and the design falls back to per-edit enqueue with PENDING dedupe.
2. **Should finalized projects be cached more aggressively?** They are immutable by policy (`scripts/invalidate_results_cache.py:18-22`), so their cache never needs invalidation. That is the single highest-value, lowest-risk subset to cache first.
3. **What is the actual latency split?** `.planning/BACKLOG.md:249` records open question A2 from a prior task: whether ORM or `math_model` CPU dominates. The evidence here (per-module `get_object_or_404`, per-module serializer `is_valid`, per-module-type queries) points strongly at ORM and serialization overhead, which the project-level cache eliminates wholesale. Worth a single profiling run to confirm before sizing the work.
4. **Fix the two pre-existing bugs in this task or separately?** Bug 1 (reference reload) is arguably a prerequisite: without it the new cache inherits a known-stale input. Bug 2 (copy) is smaller and could be split.

## Sources

### Primary (HIGH confidence)
- Repository source read directly this session: `api/models.py`, `api/views.py`, `api/serializers.py`, `api/utilities.py`, `api/concurrency.py`, `api/reference_cache.py`, `api/reports/cache.py`, `api/reports/base.py`, `api/services/async_jobs.py`, `api/services/report_jobs.py`, `api/management/commands/run_async_job.py`, `api/management/commands/reconcile_stale_async_jobs.py`, `scripts/invalidate_results_cache.py`, `djangoexact/app.yaml`, `djangoexact/requirements.txt`
- `.planning/BACKLOG.md`, `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/codebase/CONCERNS.md`

### Secondary (MEDIUM confidence)
- Django 5.2 docs via Context7 `/websites/djangoproject_en_5_2`: cache framework backends and default `CACHES`, cache key versioning, `get_or_set`, `QuerySet.update()` signal bypass, `select_for_update`

## Metadata

**Confidence breakdown:**
- Current state and existing cache: HIGH, every claim read from source with line ranges
- Write-path inventory: HIGH for in-repo paths, MEDIUM for admin bulk actions (A5)
- Storage recommendation: MEDIUM, rests on A1
- Async recompute recommendation: HIGH that AsyncJob fits, MEDIUM on the sweep cadence pending A2

**Research date:** 2026-08-10
**Valid until:** 2026-09-10 (stable stack, pinned dependencies)
