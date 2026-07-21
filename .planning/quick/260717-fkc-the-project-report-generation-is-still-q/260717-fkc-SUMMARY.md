---
status: complete
quick_id: 260717-fkc
branch: perf/report-generation-followup
requirements:
  - PERF-N1
  - PERF-N3
  - PERF-R6
files_modified:
  - djangoexact/api/calculators.py
  - djangoexact/api/models.py
  - djangoexact/api/reports/cache.py
  - djangoexact/api/reports/base.py
  - djangoexact/api/reports/land.py
commits:
  - hash: cbe42d72
    task: N1
    message: "perf(calculators): drop redundant deepcopies in Result balance (N1)"
  - hash: 84e94a66
    task: N3
    message: "perf(models): select_related land_use_change for land modules (N3)"
  - hash: a68e9fa8
    task: R6
    message: "perf(reports): batch module cache writes with bulk_update (R6)"
completed: 2026-07-17
---

# Report generation performance follow-up (round 4) Summary

Implemented the three pre-chosen, low-risk optimizations from `260717-fkc-RESEARCH.md`: dropped two redundant deep-copies in `Result.__init__` (N1), added `land_use_change` to `select_related` for land-module querysets (N3), and batched cold-path module cache writes into one `bulk_update` per concrete module class (R6). One atomic `perf:` commit per task, all on `perf/report-generation-followup`.

## What Was Built

### Task 1 (N1) — `djangoexact/api/calculators.py`

`Result.__init__`'s balance-is-None branch changed from:
```python
self.balance = copy.deepcopy(w) - copy.deepcopy(wo) if balance is None else copy.deepcopy(balance)
```
to:
```python
self.balance = w - wo if balance is None else copy.deepcopy(balance)
```
The math-layer `Result.__sub__` already deep-copies internally and reads both operands read-only, so `w - wo` was already producing an independent object; the two extra deepcopies were dead work. The `else copy.deepcopy(balance)` branch (defends against a caller-supplied, possibly-aliased balance) is untouched, and the `copy` import is still needed by it.

Commit: `cbe42d72`

### Task 2 (N3) — `djangoexact/api/models.py`

`Activity.__get_all_modules` now captures the related manager once per module type, builds a `related` list starting with `["status"]`, and appends `"land_use_change"` only when `issubclass(manager.model, LandModule)` (mirroring the existing `is_luc` predicate). Land-module querysets are fetched with `manager.all().select_related(*related)`; non-land querysets keep only `status`. `activity` is never joined, preserving the `cache_modules` memo (the shared parent `Activity` instance is not replaced).

Commit: `84e94a66`

### Task 3 (R6) — `djangoexact/api/reports/cache.py`, `base.py`, `land.py`

Added `CacheWriteBatch` in `cache.py`: a small collector keyed by `(type(module), module.pk)` that dedupes registrations (unioning `update_fields`) and, on `flush()`, groups modules by concrete class and issues one `bulk_update` per class, wrapped in a per-class try/except that logs and continues.

`save_results_to_cache` gained a `batch=None` parameter. All existing in-memory field assignments (`last_cached_at`, `cached_results_by_activity_by_gas`, conditional `last_modified` init, `skip_history_when_saving`) are unchanged and run before the batch/immediate-save branch. When `batch` is provided, the module is registered with the batch and the function returns without saving; otherwise it falls back to the original `module.save(update_fields=update_fields)`.

`BaseProjectReport.__post_init__` now creates `self.cache_batch = CacheWriteBatch()`. `BaseProjectReport.compute()` flushes it (`self.cache_batch.flush()`) immediately after all activities have computed (`activity_results = [ar.compute() for ar in activity_reports]`) and before building the aggregated result. `BaseModuleReport` gained a `_cache_batch` property that resolves `self.activity_report.project_report.cache_batch`, returning `None` when `activity_report` is `None` (so standalone module reports still get an immediate save). The base.py call site (in `_init_from_calculator`) and all three land.py re-save call sites (`PerennialCroplandReport`, `AnnualCroplandReport`, `FloodedRiceReport` — the minor-season merge re-saves) now pass `batch=self._cache_batch`.

`cache_units_breakdown` (the separate land-module units write, `models.py` `land.py:63,83`) was deliberately left untouched on the normal `CachedResultMixin.save()` path, per the plan's scope decision — it fires only for the land-module subset and keeping it on the audited path preserves its exact semantics with zero added risk.

Commit: `a68e9fa8`

## Deviations from Plan

None. All three tasks were implemented exactly as specified in `260717-fkc-PLAN.md`: line anchors for N1 and N3 matched the plan's quoted code exactly (no drift since the plan was researched); R6's file/line references (cache.py:127, base.py:96-103/276-278/292-303/42/175, land.py:216-222/327-333/852-858) also matched exactly.

## Verification Results (local gate only)

All automated checks specified in each task's `<verify>` block were run and passed:

- `python -m py_compile djangoexact/api/calculators.py djangoexact/api/models.py djangoexact/api/reports/cache.py djangoexact/api/reports/base.py djangoexact/api/reports/land.py` — clean compile, all five files.
- N1: `N1-NEW-LINE-PRESENT`, `N1-OLD-PATTERN-GONE` — both passed.
- N3: `N3-LAND-GATE-PRESENT`, `N3-CONDITIONAL-SELECT-PRESENT`, `N3-NO-ACTIVITY-JOIN` — all passed (no `activity` join leaked into `select_related`).
- R6: `R6-BULK-UPDATE-PRESENT`, `R6-SIGNATURE-OK`, `R6-FALLBACK-SAVE-PRESENT`, `R6-FLUSH-PRESENT`, `R6-LAND-CALLSITES-WIRED` (3/3 call sites), `R6-NO-UPDATED-AT-OK` (no `updated_at` in the bulk_update field list), `R6-UNITS-WRITE-UNTOUCHED` — all passed.
- No em-dashes introduced in any added line (checked via `git diff | grep '^+' | grep em-dash`; pre-existing em-dashes elsewhere in `base.py`/`land.py` are untouched and out of scope).
- Only the five plan-scoped files were staged and committed per task; the unrelated untracked migration file, `.gitignore` change, and `.planning/` artifacts were left alone.

## Deferred (CI / DB-machine human-checks — NOT run in this sandbox)

This sandbox has no Postgres/Docker, so the following `<human-check>` items from the plan are deferred to CI or a DB-equipped machine, per the RESEARCH.md recipe:

1. **Golden-file report compare (all three tasks):** generate one Excel report and one PDF report for a fixed fixture project before vs after each change (and after all three combined); must be byte-identical. Must be run on a COLD compute (edit one module to invalidate its cache) so N1's `Result` construction and R6's write batch both actually execute.
2. **N3 query-count check:** `CaptureQueriesContext` warm-run query count on a project with land modules before vs after; the per-land-module `land_use_change` SELECT must disappear and total query count should drop by roughly one per land module.
3. **R6 write-count check (cold run):** per-module cache saves must collapse to one `bulk_update` per distinct module class. Confirm the cache is valid after the cold run (a second, warm run should be a cache hit — `is_cached_results_valid()` true, no recompute). Confirm `cached_units_breakdown` is still written (units still render) since that path was intentionally left unbatched.
4. **Accepted semantic change to sign off (R6):** `bulk_update` bypasses auditlog/simple_history for the derived cache-JSON field writes only. This was already true today in effect (the path sets `skip_history_when_saving`), and losing auditlog coverage for these specific derived fields is the accepted trade documented in the plan's threat register (T-fkc-01, T-fkc-02).

## Known Stubs

None.

## Threat Flags

None — this plan closes out the threat register items already declared in `260717-fkc-PLAN.md` (T-fkc-01, T-fkc-02, T-fkc-03), all `accept`/`mitigate` disposition, no new trust boundary or external surface introduced.

## Self-Check: PASSED

- `djangoexact/api/calculators.py` — FOUND, contains `self.balance = w - wo if balance is None else copy.deepcopy(balance)`.
- `djangoexact/api/models.py` — FOUND, `__get_all_modules` contains `issubclass(manager.model, LandModule)` gate.
- `djangoexact/api/reports/cache.py` — FOUND, contains `CacheWriteBatch` class and `bulk_update` call.
- `djangoexact/api/reports/base.py` — FOUND, contains `cache_batch.flush()` and `_cache_batch` property.
- `djangoexact/api/reports/land.py` — FOUND, 3/3 `save_results_to_cache` call sites pass `batch=self._cache_batch`.
- Commit `cbe42d72` — FOUND in `git log --oneline --all`.
- Commit `84e94a66` — FOUND in `git log --oneline --all`.
- Commit `a68e9fa8` — FOUND in `git log --oneline --all`.
