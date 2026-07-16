# Quick Task: Excel Report Generation Performance - Research

**Researched:** 2026-07-16
**Domain:** Django ORM query patterns, report computation pipeline, openpyxl rendering
**Confidence:** HIGH (all hotspots verified by direct code reading; no runtime profiling possible in this sandbox)

## Summary

The Excel report is slow because of the **computation layer, not the Excel writer**. The request path (`GET /api/projects/{pk}/report`) recalculates every module's emissions through the calculator stack, and that stack issues hundreds to thousands of small uncached ORM queries: per-access `Activity.modules` re-queries, a `ModuleType.objects.get()` DB hit per inventory item, dozens of uncached IPCC reference lookups per `calculate()`, and `StatusType.objects.get(name_en="READY")` inside per-module loops. On top of that, `base.py` deep-copies each module's full math result six times where one construction would do, and the first report after any edit performs a `module.save()` (DB write plus dirtyfields relationship check) per module. The openpyxl renderer itself is comparatively cheap; its only real sin is `insert_rows()` in a loop.

**Primary recommendation:** Attack the compute layer first (query caching and memoization, single `Result` construction, prefetched module lists). Leave the renderer largely alone. These fixes also speed up the WeasyPrint PDF path, which shares `compute_project_result` (`djangoexact/api/views.py:1307` template action, `djangoexact/public/views.py:204-208`).

## Request Path (verified)

1. `ProjectViewSet.report` at `djangoexact/api/views.py:701`
2. Readiness pre-pass: `project.is_ready(selected_activities)` at `views.py:713` -> `djangoexact/api/models.py:746-754`
3. `generate_excel_report` at `views.py:722-723` -> `djangoexact/api/reports/__init__.py:34-52`
4. Compute: `BaseProjectReport.compute()` at `djangoexact/api/reports/base.py:290-316` (per activity -> per module -> calculator or module-level JSON cache)
5. Render: `ExcelRenderer.render()` at `djangoexact/api/reports/renderer.py:81-94` (openpyxl 3.1.2, in-memory workbook, serialized once at the end in `excel_manager.py:37-53`)

## Concrete Hotspots (file:line evidence, ranked by expected cost)

### H1. Uncached IPCC reference and status lookups inside calculators [VERIFIED: codebase grep]
`djangoexact/api/calculators.py` contains 148 `objects.get/filter/all` call sites; every `calculate()` re-resolves reference rows that never change. Examples: `ipcc.SoilOrganicCarbon.objects.get(...)` (calculators.py:831), `ipcc.NitrousEmissionFactor.objects.get(...)` (837), `ipcc.ForestManagementRootToShoot...` (856, 883, 910), `ipcc.ForestCombustionFactor` (914-915). Worse, `StatusType.objects.get(name_en="READY")` runs INSIDE per-module generator loops (calculators.py:606, 823, 1117), so it fires once per module per check. PROJECT.md already lists "Immutable IPCC reference-table lookups cached" as an active MEDIUM requirement, confirming this is known and unaddressed.

### H2. `Activity.modules` is a property that re-queries on every access [VERIFIED: models.py]
`djangoexact/api/models.py:1006-1008` -> `__get_all_modules()` at models.py:1158-1165: 1 query for `module_types.all()` plus 1 query per module type, with no `select_related`. Accessed at least twice per activity per report request: once by the `is_ready` pre-pass (models.py:746-754, where each `module.is_ready()` also lazy-loads the `status` FK, 1 query per module) and again by `BaseActivityReport.compute()` (base.py:198). Additional accesses via `get_land_modules_area()` (models.py:1081-1091, which reads `self.modules` twice and runs an extra `CoastalWetland.objects.filter(...)`).

### H3. `Module.module_type` property is a DB query per access, called per inventory item [VERIFIED: models.py + base.py]
`models.py:1403-1404` (and 1313-1314 for submodules): `ModuleType.objects.get(class_name=...)` on every access. `base.py:158-165` reads `self.module.module_type.name` inside the loop over inventory items, so a project with hundreds of inventory rows issues hundreds of identical `ModuleType` queries. Same pattern in the cached path at `cache.py:66-79` (line 74).

### H4. Triple `Result` construction with deep copies per module [VERIFIED: base.py + calculators.py]
`base.py:89-91` constructs `Result(*self.result)` three times. Each `Result.__init__` (calculators.py:404-407) runs `copy.deepcopy(w) - copy.deepcopy(wo)` on the full `MathResult` (all sectors x gases x years). That is six deep copies per freshly-calculated module where one construction (two deep copies) suffices; the three attribute reads can come off a single instance.

### H5. Per-module DB writes during a GET report [VERIFIED: cache.py + models.py]
On the first report after any edit, `save_results_to_cache` (cache.py:83-127) calls `module.save(update_fields=...)` per module. `CachedResultMixin.save` (models.py:1216-1237) runs `is_dirty(check_relationship=True)`, which loads related fields, and the save still passes through auditlog middleware. Land modules add a second save via `cache_units_breakdown` (models.py:1251-1256, called from land.py:63-66). Write amplification makes the first post-edit report markedly slower than subsequent cached ones.

### H6. Calculator instantiated even on full cache hits; partial cache hit recalculates everything [VERIFIED: land.py + calculators.py]
Every report subclass assigns `self.calculator = calculators.XxxCalculator(self.module)` BEFORE `super().__post_init__()` decides the cached path (e.g. land.py:297, modules.py:405). `BaseCalculator.__init__` (calculators.py:527-562) resolves `activity`, `project`, climate/moisture/soil validation, `project.country.region`, `activity.change_rate`: roughly 5-10 lazy FK queries per module even when the emissions cache is hit. And the "partial cache hit" branch for land modules (land.py:54-70) runs the FULL `calculator.calculate()` just to extract hectares, negating the cache once per module until units are persisted.

### H7. Renderer: `insert_rows()` in a loop [VERIFIED: renderer.py]
`renderer.py:221` and `renderer.py:230` call `ws_ai.insert_rows()` once per additional-indicator row; each insert shifts every row below it in the Additional Indicators sheet, giving quadratic cell moves within an activity block. Moderate cost, hidden sheet, but easy to restructure into precomputed row positions with straight writes. The rest of the renderer is fine: single workbook, single serialization at the end (excel_manager.py:37-53), per-cell writes on modest sheet sizes, shared `PatternFill` constants (renderer.py:61-64).

## Optimizations Ranked (impact vs risk)

Constraint reminder: calculation results for currently-correct paths must NOT change, and the public API contract must not change. All of R1-R5 are read-path memoization or object-lifetime changes that cannot alter computed numbers.

| # | Optimization | Impact | Risk | Notes |
|---|-------------|--------|------|-------|
| R1 | Memoize immutable reference lookups: `ModuleType.objects.get(class_name=...)` behind `functools.lru_cache` (or per-request dict), hoist `StatusType.objects.get(name_en="READY")` out of loops, `lru_cache` the hot IPCC table getters (SoilOrganicCarbon, NitrousEmissionFactor, combustion/root-to-shoot factors, GWP) | HIGH | LOW | Reference data is immutable at runtime by design (loaded via load_reference_data); PROJECT.md already mandates this. Invalidate on process restart is acceptable; document that reference-data reloads need a restart or cache clear |
| R2 | Build `Result(*self.result)` ONCE in `base.py:89-91` and read the three attributes off it | HIGH | LOW | Pure object-lifetime change; removes 4 of 6 deepcopies per module. Verify balance semantics stay identical (they do: same constructor, same inputs) |
| R3 | Fetch modules once per activity and reuse: either a per-instance memo on `Activity` scoped to the report (safest: build the module list in `BaseActivityReport`/`Project.is_ready` callers and pass it down) plus `select_related("status", "activity", "activity__project")` in `__get_all_modules` | HIGH | MED | Do NOT blindly cache the model property globally; other code paths mutate modules mid-request. Report-layer local reuse is safe |
| R4 | Drop or merge the `project.is_ready` pre-pass (views.py:713): compute already raises `NotReadyError` per module with a clear message. Alternatively make `is_ready` reuse the fetched module lists with `select_related("status")` | MED | LOW-MED | Response for not-ready projects changes from 400 to 422 if the pre-pass is dropped; keep the pre-pass but make it cheap to preserve the contract |
| R5 | Defer calculator construction until the cache decides it is needed (move `self.calculator = ...` into a lazy factory or into `_init_from_calculator`) | MED | MED | Touches all 20+ report subclasses; benefits warm-cache reports most. The partial-cache hectares recalculation (land.py:54-70) self-heals after one run, so lower priority |
| R6 | Batch cache persistence: collect dirty modules and `bulk_update` the cache JSON fields after compute instead of per-module `save()` | MED | MED | `bulk_update` skips signals and the custom `save()`; must replicate the `last_modified` guard (models.py:1216-1231) carefully or restrict to the cache fields which the guard already exempts |
| R7 | Renderer: precompute Additional Indicators row layout, replace `insert_rows` loops with direct writes | LOW-MED | LOW | Purely presentational ordering; verify row order in output matches current files byte-for-byte semantics |
| R8 | For very large projects, move report generation onto the existing Cloud Run job path (deploy/Dockerfile.computation_job, api/services/luc_compute.py pattern) with polling/download | HIGH (worst case) | HIGH | Changes the API interaction model; only if R1-R4 are insufficient under the 120s gunicorn timeout. Out of scope for a quick fix |

## Library-Level Notes

- openpyxl write-only mode is append-only: no writing to arbitrary cell locations, sheets created explicitly, one save only [CITED: openpyxl.readthedocs.io/en/stable/optimized.html]. The current renderer relies on random access (`max_row`, `insert_rows`, back-filling the activity title row at renderer.py:236-239), so write-only mode would require a full renderer rewrite. Not worth it: rendering is not the bottleneck.
- XlsxWriter `constant_memory` mode has the same row-ordered append-only restriction, so switching writer libraries buys nothing here either [ASSUMED].
- The SPC sheet writes Excel formulas (renderer.py:400-433); any writer swap must preserve formula strings exactly, another reason to keep openpyxl.

## Gotchas for Planning

- **Shared pipeline:** the WeasyPrint PDF template path uses the same `compute_project_result` (views.py:1307 `template` action delegates through it; public/views.py:204-208). Compute-layer fixes improve both; renderer fixes improve only Excel.
- **Module-level JSON cache already exists** (`CachedResultMixin`, models.py:1203-1298) and works: warm reports skip `calculate()`. Slowness reports likely concern first-report-after-edit (full recalculation plus per-module saves) and the constant per-request ORM overhead (H2, H3, H6) that the cache does NOT eliminate.
- **`lru_cache` on querysets:** cache resolved model instances or plain values, never lazy querysets. Instances of reference models are safe to share; they are treated as immutable.
- **Multi-worker note:** gunicorn runs 4 workers; process-level caches are per-worker, which is fine for immutable reference data.
- **No local runtime:** this sandbox has no Postgres/Docker; verify with the CI suite or a DB-equipped machine. Golden-file comparison of a generated report before/after (same project fixture) is the right regression gate for R2/R3/R7.
- **Project rule:** no em-dashes in any repo file; conventional commits.

## Sources

### Primary (HIGH confidence)
- Direct code reading: `djangoexact/api/views.py`, `djangoexact/api/models.py`, `djangoexact/api/calculators.py`, `djangoexact/api/reports/{__init__,base,cache,registry,renderer,excel_manager,land,modules}.py`
- openpyxl official docs via Context7 (`/websites/openpyxl_readthedocs_io_en_stable`): write-only mode constraints

### Assumptions
| # | Claim | Risk if wrong |
|---|-------|---------------|
| A1 | XlsxWriter constant_memory is append-only like openpyxl write-only | None material; recommendation is to keep openpyxl regardless |
| A2 | ORM query volume, not CPU in math_model, dominates wall time | If math dominates, R1-R4 gains shrink; a single profiled run on a DB-equipped machine (django-debug-toolbar or `connection.queries` count) would confirm before large refactors |
