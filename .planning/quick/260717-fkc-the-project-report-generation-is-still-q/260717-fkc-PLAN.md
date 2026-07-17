---
phase: quick-260717-fkc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - djangoexact/api/calculators.py
  - djangoexact/api/models.py
  - djangoexact/api/reports/cache.py
  - djangoexact/api/reports/base.py
  - djangoexact/api/reports/land.py
autonomous: true
requirements:
  - PERF-N1
  - PERF-N3
  - PERF-R6
branch: perf/report-generation-followup

must_haves:
  truths:
    - "A generated report (Excel and PDF) is byte-identical before vs after all three changes for the same fixture project (no calculation change, no API change)."
    - "N3: no per-land-module land_use_change query fires during report compute (it is resolved by select_related)."
    - "R6: the cold path (first report after an edit) issues one bulk_update per concrete module class instead of N per-module cache saves."
    - "The activity module-list memo (cache_modules) is preserved: __get_all_modules never joins activity, so the shared parent instance is not replaced."
  artifacts:
    - djangoexact/api/calculators.py
    - djangoexact/api/models.py
    - djangoexact/api/reports/cache.py
    - djangoexact/api/reports/base.py
    - djangoexact/api/reports/land.py
  key_links:
    - "N1: math-layer Result.__sub__ reads both operands read-only (deep-copies self internally), so w - wo yields an independent balance."
    - "N3: issubclass(manager.model, LandModule) gates the extra select_related on land types only (mirrors is_luc at models.py:1094)."
    - "R6: save_results_to_cache defers to a per-project-compute batch when one is active, and BaseProjectReport.compute flushes it after all activities compute; fallback to immediate save when no batch is active."
---

<objective>
Report generation performance follow-up (round 4). Implement exactly THREE pre-chosen, low-risk optimizations from 260717-fkc-RESEARCH.md, one per task with an atomic commit each:

- N1 (cold path): drop two redundant deep-copies in api/calculators.py Result.__init__.
- N3 (both paths): add land_use_change to select_related for land-module querysets in Activity.__get_all_modules.
- R6 (cold path): batch the per-module cache writes in api/reports/cache.py save_results_to_cache into a bulk_update per concrete module class.

Purpose: shave residual CPU (N1) and ORM (N3 query, R6 writes) cost off the shared Excel + WeasyPrint report pipeline without changing any emission number or the public API contract.
Output: five files modified across three atomic commits; py_compile-clean; golden-file report compare (CI / DB machine) is the regression gate.

HARD CONSTRAINT (PROJECT.md): computed emission numbers and the public API contract MUST NOT change. Every change here is object-lifetime, query-shape, or write-batching only.
Profiling, N2, R5, and R8 are explicitly DEFERRED and MUST NOT appear in this plan.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@.planning/quick/260717-fkc-the-project-report-generation-is-still-q/260717-fkc-RESEARCH.md
@djangoexact/api/calculators.py
@djangoexact/math_model/no_time_dependency_final/ghg_emissions_classes.py
@djangoexact/api/models.py
@djangoexact/api/reports/cache.py
@djangoexact/api/reports/base.py
@djangoexact/api/reports/land.py

Environment note: this sandbox has no Postgres/Docker. `python -m py_compile` is the only local gate. The behavioral regression (byte-identical report) and the query/write-count checks run in CI or on a DB-equipped machine (recipe in RESEARCH.md "How to measure"). Encode both in each task.
Project rules: NO em-dashes anywhere. Conventional commits with the `perf:` type. Branch `perf/report-generation-followup` is already checked out; do NOT create branches.
</context>

<tasks>

<task type="auto">
  <name>Task 1 (N1): Drop the two redundant deep-copies in Result.__init__ balance construction</name>
  <files>djangoexact/api/calculators.py</files>
  <action>
In `Result.__init__` (calculators.py, class `Result` starting at line 400, the balance assignment is currently at line 408), the balance-is-None branch wraps both operands in `copy.deepcopy(...)` before subtracting. The math-layer subtraction already produces an independent object, so those two deep-copies are dead work on the cold path.

Change ONLY the balance-is-None branch so it subtracts the operands directly. The new line 408 must read exactly:

`        self.balance = w - wo if balance is None else copy.deepcopy(balance)`

Leave the `else copy.deepcopy(balance)` branch UNCHANGED: that path receives a caller-supplied balance that may be aliased, so it must keep its defensive copy. Do NOT touch lines 406-407 (`self.total_w = w` / `self.total_wo = wo`) and do NOT remove the `copy` import (still used by the else branch and elsewhere).

Safety basis (already re-confirmed by the planner, do not re-verify by editing): the math-layer `Result.__sub__` in math_model/no_time_dependency_final/ghg_emissions_classes.py lines 240-261 does `result_obj = copy.deepcopy(self)` and mutates only `result_obj`; it reads `other` strictly read-only (iterates it, negates values into freshly-built Emission / YearlyGasActivityEmissionSet objects). It never mutates or returns either operand. The same `total_w - total_wo` pattern (no deepcopy) is ALREADY used in `Result.add` at calculators.py line 419, so the aggregation path already relies on this producing an independent balance. Output is byte-identical.
  </action>
  <verify>
    <automated>python -m py_compile djangoexact/api/calculators.py</automated>
    <automated>grep -Fq "self.balance = w - wo if balance is None else copy.deepcopy(balance)" djangoexact/api/calculators.py && echo N1-NEW-LINE-PRESENT</automated>
    <automated>test "$(grep -Fc 'copy.deepcopy(w) - copy.deepcopy(wo)' djangoexact/api/calculators.py)" = "0" && echo N1-OLD-PATTERN-GONE</automated>
    <human-check>On a DB-equipped machine / CI: generate one Excel report and one PDF report for a fixed fixture project BEFORE this change and AFTER; the two files must be byte-identical (golden-file compare). Use the RESEARCH.md recipe; force a COLD run (edit one module to invalidate its cache) so a fresh Result is actually built.</human-check>
  </verify>
  <done>calculators.py compiles; the balance-is-None branch subtracts operands directly with no deepcopy on w/wo; the else branch still deep-copies the supplied balance; golden-file report compare is byte-identical. Atomic commit: `perf(calculators): drop redundant deepcopies in Result balance (N1)`.</done>
</task>

<task type="auto">
  <name>Task 2 (N3): select_related land_use_change for land-module querysets in __get_all_modules</name>
  <files>djangoexact/api/models.py</files>
  <action>
In `Activity.__get_all_modules` (models.py lines 1209-1216) the per-type fetch is:
`modules.extend(list(getattr(self, module_type.class_name.lower()).all().select_related("status")))`

`is_with()` / `is_without()` (models.py 1536 / 1522) read `self.land_use_change`, a forward OneToOneField declared on `LandModule` (models.py 1814). It is NOT covered by the existing `select_related("status")`, so the first access per land module issues an extra query on both the Excel and PDF paths.

Rewrite the loop body so that land-module querysets also select_related `land_use_change`, while non-land querysets keep only `status`. Resolve the related model via the manager's `.model` attribute and gate on `LandModule` subclass membership (the same predicate `is_luc` already uses at models.py line 1094). Concretely:

- Capture the related manager once: `manager = getattr(self, module_type.class_name.lower())`.
- Build a related list starting with `["status"]`; append `"land_use_change"` when `issubclass(manager.model, LandModule)`.
- Fetch with `manager.all().select_related(*related)`.

Add a short code comment (no em-dashes) noting that this covers all concrete top-level land types (AnnualCropland, PerennialCropland, ForestManagement via LandModule; FloodedRice, Grassland via LandModuleFixed, which subclasses LandModule), and that the abstract LandModuleNoScenarios / LandSubmodule also carry land_use_change but have no concrete top-level subclasses today.

MEMO-SAFETY CONSTRAINT (do not violate): only ever add `land_use_change` (a forward relation on the module itself). Do NOT add `activity` (or any `activity__...` path) to select_related here. Joining `activity` would replace the shared parent Activity instance and defeat the cache_modules memo (R3). `LandModule` is defined later in the file (line 1813) but is resolved at call time inside this method body, exactly as `is_luc` (line 1094) already references it, so the forward reference is fine.
  </action>
  <verify>
    <automated>python -m py_compile djangoexact/api/models.py</automated>
    <automated>grep -Fq 'issubclass(manager.model, LandModule)' djangoexact/api/models.py && echo N3-LAND-GATE-PRESENT</automated>
    <automated>grep -Fq 'select_related(*related)' djangoexact/api/models.py && echo N3-CONDITIONAL-SELECT-PRESENT</automated>
    <automated>awk 'NR>=1209 && NR<=1230' djangoexact/api/models.py | grep -F 'select_related' | grep -Fq 'activity' && echo N3-ACTIVITY-JOIN-LEAK || echo N3-NO-ACTIVITY-JOIN</automated>
    <human-check>On a DB-equipped machine / CI: run the RESEARCH.md warm-run query counter (CaptureQueriesContext) on a project with land modules before vs after; the per-land-module land_use_change SELECT must disappear and total query count must drop by roughly one per land module. Golden-file report compare must stay byte-identical (query shape only, no data change).</human-check>
  </verify>
  <done>models.py compiles; land-module querysets select_related both `status` and `land_use_change`, non-land keep only `status`; `activity` is never joined in __get_all_modules; report output unchanged; warm query count drops by ~1 per land module. Atomic commit: `perf(models): select_related land_use_change for land modules (N3)`.</done>
</task>

<task type="auto">
  <name>Task 3 (R6): batch cold-path module cache writes into bulk_update per concrete class</name>
  <files>djangoexact/api/reports/cache.py, djangoexact/api/reports/base.py, djangoexact/api/reports/land.py</files>
  <action>
GOAL: on the cold path, replace the N per-module `module.save(update_fields=...)` calls inside `save_results_to_cache` (cache.py line 127) with a single `bulk_update` per concrete module class, issued once at the end of a project compute. Data written and final row state must be identical to today. This is the biggest remaining cold-path ORM win.

Scope decision (per RESEARCH.md and the task brief): batch ONLY the primary emissions cache write (`save_results_to_cache`, which fires for every freshly-calculated top-level module: base.py line 96 plus the three land re-saves at land.py 216 / 327 / 852). LEAVE the land-module second write `cache_units_breakdown` (models.py 1302-1307, called from land.py 63 and 83) AS-IS on the normal `save()` path. Rationale (correctness over completeness): cache_units_breakdown fires only for the land-module subset and in specific branches; keeping it on the audited `CachedResultMixin.save()` path preserves its exact semantics with zero added risk, while the emissions write (all N modules) is where the batching win concentrates. Document this rationale in a comment.

Implement in three parts:

1) cache.py: add a lightweight, per-compute batch collector and make save_results_to_cache defer to it.
   - Add a small class (e.g. `CacheWriteBatch`) that holds modules keyed by `(type(module), module.pk)` and, per key, the set of `update_fields` recorded. Provide `register(module, update_fields)` (dedupes by key, unions fields; because the SAME module instance is re-registered by any land re-save, the final in-memory field values win naturally) and `flush()`.
   - `flush()` groups registered modules by their concrete class and, for each group, calls `ModelClass.objects.bulk_update(objs, sorted(fields))`. Wrap each per-class bulk_update in its own try/except that logs a warning and continues (mirrors today's per-module tolerance: a cache-write failure must never break the report, which already holds the in-memory results). Skip empty groups.
   - Change the signature to `save_results_to_cache(module, emissions_set, emissions_set_w, emissions_set_wo, inventory, batch=None)`. Keep ALL existing in-memory field assignments EXACTLY as today (lines 118-126): build `data`, set `module.last_cached_at = now`, set `module.cached_results_by_activity_by_gas = data`, initialize `module.last_modified = now - timedelta(seconds=1)` only when it is None (and add "last_modified" to update_fields in that case), and set `module.skip_history_when_saving = True` when present. THEN: if `batch is not None`, call `batch.register(module, update_fields)` and return; otherwise fall back to the current `module.save(update_fields=update_fields)`. The `if module.pk is None: return` guard at line 93 stays first.
   - CRITICAL field-list constraint: bulk_update must write ONLY the fields already in `update_fields` (subset of last_cached_at, cached_results_by_activity_by_gas, last_modified). Do NOT add `updated_at` (auto_now) or `cached_units_breakdown` to the bulk_update field list: the current per-module save with update_fields does not refresh `updated_at`, so adding it would diverge. Writing last_modified back as its unchanged value for modules that already had it is a harmless no-op and keeps the per-class field list uniform.

2) base.py: own and flush the batch on the project report.
   - Give `BaseProjectReport` a `cache_batch` attribute (create it in `__post_init__`, base.py 276-278, e.g. `self.cache_batch = CacheWriteBatch()`; import from `.cache`).
   - In `BaseProjectReport.compute` (base.py 292-303), after the `activity_results = [ar.compute() for ar in activity_reports]` line (295) has run all module `__post_init__` saves, flush: `self.cache_batch.flush()`. Place the flush so it always runs after compute of all activities and before returning; a try/finally around the activities-compute block is acceptable but not required since flush() itself swallows per-class errors.
   - Add a helper on `BaseModuleReport` to resolve the active batch from the object graph, e.g. a property `_cache_batch` returning the project report's `cache_batch` via `self.activity_report.project_report.cache_batch`, guarding for `activity_report is None` (returns None so the fallback immediate save is used). `BaseModuleReport.activity_report` is base.py field line 42; `BaseActivityReport.project_report` is base.py line 175.
   - At the base.py call site (line 96-103) pass `batch=self._cache_batch`.

3) land.py: pass the batch at the three land re-save call sites.
   - At land.py 216-222 (PerennialCropland), 327-333 (AnnualCropland), and 852-858 (FloodedRice), add `batch=self._cache_batch` to the `save_results_to_cache(...)` call (these classes inherit `_cache_batch` from BaseModuleReport). Do NOT change the `cache_units_breakdown` calls at land.py 63 and 83.

Behavior-identical basis (already reasoned by the planner; encode as comments, do not re-derive by trial): (a) save_results_to_cache is only ever called on top-level Module instances, never a Submodule, so CachedResultMixin.save's Submodule parent-invalidation branch (models.py 1284-1286) is not in play; (b) report modules are freshly fetched and only cache fields are mutated, so no non-cache field is dirty and the last_modified bump branch (models.py 1281-1282) would not fire under the current save either; (c) these cache saves already set `skip_history_when_saving`, so simple_history is skipped today, and bulk_update skipping history is therefore not a change; (d) bulk_update does bypass auditlog for these derived cache-JSON fields, which is the accepted trade (RESEARCH.md Gotchas). Group by concrete class because bulk_update operates on one table at a time and the modules span 20+ concrete classes.

NO em-dashes in any added code or comment.
  </action>
  <verify>
    <automated>python -m py_compile djangoexact/api/reports/cache.py djangoexact/api/reports/base.py djangoexact/api/reports/land.py</automated>
    <automated>grep -Fq 'bulk_update' djangoexact/api/reports/cache.py && echo R6-BULK-UPDATE-PRESENT</automated>
    <automated>grep -Fq 'def save_results_to_cache(module, emissions_set, emissions_set_w, emissions_set_wo, inventory, batch=None)' djangoexact/api/reports/cache.py && echo R6-SIGNATURE-OK</automated>
    <automated>grep -Fq 'module.save(update_fields=update_fields)' djangoexact/api/reports/cache.py && echo R6-FALLBACK-SAVE-PRESENT</automated>
    <automated>grep -Fq 'cache_batch.flush()' djangoexact/api/reports/base.py && echo R6-FLUSH-PRESENT</automated>
    <automated>test "$(grep -Fc 'batch=self._cache_batch' djangoexact/api/reports/land.py)" = "3" && echo R6-LAND-CALLSITES-WIRED</automated>
    <automated>grep -Fq 'updated_at' djangoexact/api/reports/cache.py && echo R6-CHECK-UPDATED-AT-NOT-IN-FIELDLIST || echo R6-NO-UPDATED-AT-OK</automated>
    <automated>test "$(grep -Fc 'cache_units_breakdown' djangoexact/api/models.py)" -ge "1" && echo R6-UNITS-WRITE-UNTOUCHED</automated>
    <human-check>On a DB-equipped machine / CI (RESEARCH.md recipe): (1) COLD run on a multi-module project must produce byte-identical Excel and PDF reports vs before R6 (golden-file). (2) Count DB writes on the cold run: per-module cache saves must collapse to one bulk_update per distinct module class. (3) Confirm the cache is populated after the cold run (a second run is a warm cache hit: is_cached_results_valid() true, no recompute). (4) Confirm the land-module cached_units_breakdown is still written (units still render). ACCEPTED semantic change to sign off: auditlog no longer records the derived cache-JSON field writes (bulk_update bypasses signals) - this is intended for derived data.</human-check>
  </verify>
  <done>cache.py, base.py, land.py compile; cold-path emissions cache writes go through one bulk_update per concrete class via a project-compute batch, with an immediate-save fallback when no batch is active; cache_units_breakdown is unchanged; updated_at is not added to the bulk_update field list; golden-file report compare byte-identical; cold-run write count drops to one bulk_update per module class; warm re-run is a cache hit. Atomic commit: `perf(reports): batch module cache writes with bulk_update (R6)`.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| (none new) | Internal refactor: no new external input, no new dependency, no auth or API-surface change. Report inputs and the public contract are unchanged. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-fkc-01 | Tampering | R6 bulk_update on cache-JSON fields (reports/cache.py) | low | accept | bulk_update bypasses auditlog/simple_history for derived cache fields only; the current path already sets skip_history_when_saving, and the last_modified guard exempts cache fields. Field list restricted to last_cached_at / cached_results_by_activity_by_gas / last_modified; updated_at and cached_units_breakdown excluded to preserve identical row semantics. |
| T-fkc-02 | Repudiation | Auditlog coverage of cache-field writes | low | accept | Derived cache data is not an audit-relevant fact; losing auditlog rows for these writes is intended (RESEARCH.md). No user-facing or security-relevant field is affected. |
| T-fkc-03 | Denial of Service | R6 all-or-nothing per-class flush | low | mitigate | Each per-class bulk_update is wrapped in try/except that logs and continues; a cache-write failure degrades to recompute-next-time (never a broken report, which already holds in-memory results), matching current per-module tolerance. |
</threat_model>

<verification>
- `python -m py_compile djangoexact/api/calculators.py djangoexact/api/models.py djangoexact/api/reports/cache.py djangoexact/api/reports/base.py djangoexact/api/reports/land.py` passes (only reliable local gate).
- Grep checks in each task pass (new N1 line present, old deepcopy pattern gone; N3 land gate + no activity join; R6 bulk_update + fallback + flush + 3 land call sites + units write untouched).
- Regression gate (CI / DB machine): golden-file compare of one fixture project's Excel and PDF reports before vs after ALL three changes is byte-identical, run on a COLD compute so N1's Result build and R6's write batch both execute.
- Query/write-count check (CI / DB machine): N3 removes ~1 SELECT per land module (warm run); R6 collapses N per-module cache saves into one bulk_update per concrete module class (cold run), and a subsequent run is a warm cache hit.
</verification>

<success_criteria>
- Three atomic `perf:` commits on `perf/report-generation-followup` (N1, N3, R6), no em-dashes anywhere.
- No emission number and no public API response changes for any activity type or scenario (golden-file gate).
- N1: Result.__init__ balance-is-None branch does `w - wo`; else branch still deep-copies supplied balance; copy import retained.
- N3: land-module querysets select_related `status` + `land_use_change`; non-land keep `status`; `activity` never joined in __get_all_modules (cache_modules memo intact).
- R6: cold-path emissions cache writes batched to one bulk_update per concrete class with immediate-save fallback; cache_units_breakdown left on the normal save() path; updated_at not in the bulk_update field list; cache still valid after a cold run.
- Deferred items (profiling, N2, R5, R8) are absent from the implementation.
</success_criteria>

<output>
Three atomic commits on branch `perf/report-generation-followup`. No SUMMARY file required for this quick task beyond the standard quick-task state log.
</output>
