# Quick Task: Report Generation Performance (follow-up to R1-R3) - Research

**Researched:** 2026-07-17
**Domain:** Django report compute pipeline, ORM query patterns, CPU cost in aggregation/math layers
**Confidence:** HIGH on code facts (all re-anchored to current develop); MEDIUM on where the *remaining* time actually goes (never profiled - see headline)

## Summary

R1-R3 removed the bulk of the *per-request ORM overhead* the original research flagged: reference-table lookups, `ModuleType`/`StatusType` resolution, and the module re-query storm are all memoized now. What is left is mostly **CPU inside Python**, not database round-trips: the cold path still deep-copies full emission results and runs `calculate()` per module, and *both* paths run a heavy list-crunching aggregation (~24 filtered passes over every module's emission set in `base.py`, plus dozens of `_extract` calls per module in the compute classes). The original research's core assumption A2 ("ORM dominates, not CPU") was never confirmed, and R1-R3 made it *less* likely to still be true.

**Primary recommendation (headline):** Do NOT guess at another caching round. Run ONE profiled report on a DB-equipped machine (recipe below) to settle CPU-vs-ORM. If the profile confirms CPU dominance (likely), the highest-leverage safe moves are N1 (drop two redundant deep-copies, cold path) and N2 (single-pass aggregation, both paths). R6 (batch cache writes) remains the biggest *cold-path ORM* win. R4/R5/R7 payoffs shrank after R1-R3.

## What's already done (baseline - do not re-propose)

- **R1** - immutable reference lookups memoized: `module_type_for_class()` + `get_ready_status()` (`api/models.py:452-472`), plus `api/reference_cache.py` for hot IPCC getters.
- **R2** - single `Result(*self.result)` construction per freshly-calculated module (`api/reports/base.py:89`), down from three.
- **R3** - per-instance `Activity.cache_modules()` memo + `select_related("status")` (`api/models.py:1041-1059`, `1214`), shared across the readiness pre-pass, Excel compute, and PDF context.

## R4-R8 revisited (re-anchored to current develop)

| # | What | Still open? | Current anchor | Updated verdict |
|---|------|-------------|----------------|-----------------|
| R4 | Drop/cheapen the `is_ready` pre-pass | Open but **largely neutralized** | `views.py:715` -> `models.py:774-782` | R3 already made this cheap: `is_ready` now calls `cache_modules()` (priming the same memo compute reuses) and reads `status` via `select_related`. It no longer double-fetches. Keep it (preserves the 400 "not ready" contract). **Do not spend effort here.** |
| R5 | Lazy calculator construction | Open | Every subclass sets `self.calculator = calculators.XxxCalculator(self.module)` before `super().__post_init__()` (`land.py:126,188,297,425,464,...`; `modules.py:123,175,270,...`) | Calculator is still built per module even on warm cache hits. But `BaseCalculator.__init__` (`calculators.py:528-563`) is now **amortized**: modules share one `Activity`/`Project` instance (Django known-related-objects), so `project.country`, `region`, `activity.change_rate`, `project.climate` load once per activity, not per module. R1 also cached the reference reads. **Payoff shrank to per-module Python object creation + climate/moisture/soil validation + per-module `country_t2`.** Still worth doing for warm reports, but modest; touches 20+ subclasses (MED risk). Lower priority than before. |
| R6 | Batch cache persistence (`bulk_update`) | Open | `cache.py:127` `module.save(update_fields=...)` per module; land modules add a 2nd write via `cache_units_breakdown` (`models.py:1302-1307`, called from `land.py:63`) | **Cold-path only**, and still the single biggest cold-path ORM win left (first report after any edit does N per-module writes, each through `CachedResultMixin.save` + auditlog + dirtyfields). Risk MED: `bulk_update` bypasses the custom `save()`/history, which is acceptable *only* for the cache JSON fields (the `last_modified` guard at `models.py:1271-1282` already exempts them), but must preserve `skip_history_when_saving` behavior and the `last_modified` initialization at `cache.py:122-124`. |
| R7 | Renderer `insert_rows()` loop | Open, unchanged | `renderer.py` Additional Indicators sheet | Excel-only, presentational. Verdict unchanged: LOW-MED, only pursue if profiling fingers the renderer (unlikely - rendering was never the bottleneck). |
| R8 | Offload to Cloud Run job | Open | `app.yaml:5` `gunicorn -w 4 ... --timeout 120`, `F4_1G` | Addresses the **120s wall + 4-sync-worker starvation** for very large projects, not per-report speed. HIGH effort, changes the API interaction model (async + polling/download). Strategic fallback if latency wins are insufficient, not a quick fix. |

## New opportunities (ranked; all safe re: no-calculation-change / no-API-change)

### N1. Two redundant deep-copies in `calculators.Result.__init__` [HIGH-confidence, LOW-MED risk] - COLD path
`api/calculators.py:408`:
```python
self.balance = copy.deepcopy(w) - copy.deepcopy(wo) if balance is None else copy.deepcopy(balance)
```
The math-layer `Result.__sub__` (`math_model/.../ghg_emissions_classes.py:240-261`) **already** does `result_obj = copy.deepcopy(self)` internally and builds the balance from freshly-constructed `Emission`/`YearlyGasActivityEmissionSet` objects out of `other` (lines 251, 256-258) - it never mutates or aliases either operand. So `copy.deepcopy(w)` and `copy.deepcopy(wo)` are both dead work: `w - wo` produces an already-independent balance. Changing the balance branch to `self.balance = w - wo` removes **two full-MathResult deep-copies per freshly-calculated module** with byte-identical output.
- **Impact:** MED on the cold path (deepcopy of the full sector x gas x year structure is expensive). Zero on warm cache (no `Result` built there).
- **Why safe:** verified `__sub__` reads-only both operands; `total_w`/`total_wo`/`balance` remain mutually independent. Golden-file compare of one project confirms.
- This is the residual of H4/R2 that R2 did not touch - R2 collapsed *three constructions into one*; each construction still carried two redundant deepcopies.

### N2. Aggregation does ~24 filtered passes over every module's emissions [needs profiling first, MED-HIGH impact] - BOTH paths
`api/reports/base.py:339-395` (`_build_aggregated_from_module_emissions`): for every module it calls `extract_emissions` ~24 times (8 buckets x 3 scenarios), and `extract_emissions` (`extractors.py:87-112`) re-iterates the module's *entire* emissions list on each call. On top of that each module's `compute()` runs its own `_extract`/`_balance_total` calls (35 call sites in `land.py`, 72 in `modules.py`). This is pure Python list arithmetic that runs on **warm reports too**, so after R1-R3 it is a prime candidate for the "still slow" dominant cost on large projects.
- **Opportunity:** replace the 24 filtered passes with a **single pass** per emissions set that routes each `(activity, gas)` entry into the right accumulator (a dict keyed by bucket), preserving the exact `_eq` enum-vs-string matching (`extractors.py:16-31`).
- **Impact:** MED-HIGH for module-dense / long-duration projects. **Risk MED** - the bucket routing must reproduce the exact exclusion logic (`excl_a=[BIOMASS, SOIL_CO2_CHANGE]`) and the DOC/CO/OTHER folding into `other_ghgs`. Golden-file gate mandatory.
- **Gate it behind the profile:** if the profile shows `extract_emissions` low in cumtime, skip this - it is the riskiest of the new items.

### N3. `is_with()/is_without()` trigger a `land_use_change` fetch per land module [LOW-MED, LOW risk] - both paths
`base.py:218,223` call `module.is_with()` / `module.is_without()`, which read `self.land_use_change` (`models.py:1536,1522`). `land_use_change` is a `OneToOneField` on the module (`models.py:1814`) and is **not** in R3's `select_related("status")`. First access per land module issues a query. Because it is a forward relation on the module (not the shared `Activity`), adding it to the per-type fetch is memo-safe (unlike joining `activity`, which R3 correctly avoided). Requires a per-type conditional in `__get_all_modules` (`models.py:1209-1216`) since non-land module types have no `land_use_change`.
- **Impact:** LOW-MED (one query per land module, cold and warm). **Risk LOW.**

### N4. PDF path discards the readiness-primed instances and computes ALL activities [LOW impact]
`views.py:702-720`: `report()` primes the memo on `selected_activities`, then for the template case calls `self.template()`, which re-fetches via `self.get_object()` (`views.py:1326`) and runs `compute_project_result(project)` with `activities=None` (`views.py:1328`) - fresh instances, and it ignores the `selected_activities` filter entirely. The PDF path therefore re-fetches modules the readiness pass already loaded, and always renders every activity. Low per-report cost, but a correctness-adjacent nuance worth flagging to planning (the `selected_activities` filter is silently dropped for PDF).

### N5 (closed questions - state and move on)
- **Indexes:** the hot filter columns are already indexed. Django auto-indexes every `ForeignKey`/`OneToOneField`, so `Module.activity`, `Module.status`, and `LandModule.land_use_change` (`models.py:1442,1450,1814`) all have DB indexes. **No missing-index issue** on the report's hot paths.
- **CONN_MAX_AGE = 0** (`djangoexact/settings.py:155,172`): closes the connection after each request. This does **not** affect a single report's latency - one connection is reused for the whole request - it only adds cross-request reconnect cost. Not relevant to "this report is slow"; leave as-is unless a separate connection-churn concern arises (raising it on App Engine + Cloud SQL risks pool exhaustion, so out of scope here).
- **Double compute?** No. For Excel: `is_ready` (status-only pass) + one `compute`. For PDF: `is_ready` + one `compute` inside `template()`. `compute_project_result` runs **once** per request on each path.
- **Parallelism:** compute is sequential (`base.py:294-295`). The workload is CPU-bound Python (math + aggregation), so threads hit the GIL and multiprocessing would need to pickle Django model graphs. **Not recommended** as a caching-style quick win; it belongs with R8 if latency remains unacceptable after CPU cuts.

## How to measure before committing (do this FIRST)

Run one real project through both paths on a DB-equipped machine (CI shell, or local with `cloud-sql-proxy`). `CaptureQueriesContext` forces query logging without needing global `DEBUG`.

```python
# from djangoexact/ :  python manage.py shell
import cProfile, pstats, io
from django.db import connection
from django.test.utils import CaptureQueriesContext
from api.models import Project, AnnualCropland  # any module model to force-invalidate
from api.reports import compute_project_result, generate_excel_report

project = Project.objects.get(pk=PK)   # pick a big, slow one

# --- WARM run: query count + DB time ---
with CaptureQueriesContext(connection) as ctx:
    compute_project_result(project)
print("warm queries:", len(ctx), "db_time:", round(sum(float(q["time"]) for q in ctx), 3))

# --- WARM run: CPU profile (compute + render) ---
pr = cProfile.Profile(); pr.enable()
generate_excel_report(project)
pr.disable()
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(40)
print(s.getvalue())
```
Then force a **cold** run by editing one module (e.g. `m = AnnualCropland.objects.filter(activity__project=project).first(); m.save()` to bump `last_modified` and invalidate its cache) and repeat.

**Read the output like this:**
- `warm queries` high (hundreds) -> a remaining N+1 (start with N3's `land_use_change`); hunt it before any CPU work.
- `warm queries` low + `db_time` small fraction of wall time, with `extract_emissions` / `deepcopy` / `calculate` topping cumtime -> **CPU-bound, A2 is false** -> pursue N1 (cold) and N2 (both).
- Cold run much slower than warm, dominated by `save`/DB writes -> R6 is the target.

This single run converts the next round from guesswork into evidence, which matters precisely because R1-R3 already harvested the obvious ORM wins.

## Recommended next steps (pick from these)

**Do first (headline):**
0. **Profile one slow project, cold and warm** (recipe above). Everything below should be confirmed by it.

**Safe quick wins (no API/calc change, small blast radius):**
1. **N1** - drop the two redundant deepcopies at `calculators.py:408` (`w - wo`). Cheapest cold-path win, LOW-MED risk, golden-file gated.
2. **N3** - add `land_use_change` to the per-land-type `select_related`. Small, memo-safe.
3. **R6** - batch the cold-path cache writes with `bulk_update`. Biggest cold-path ORM win; MED risk around the `last_modified`/history guards.

**Bigger / riskier bets (only if profile justifies):**
4. **N2** - single-pass aggregation in `base.py`. Highest warm-path CPU upside, but the riskiest to keep byte-identical; only if `extract_emissions` shows up hot.
5. **R5** - lazy calculator construction across the 20+ subclasses. Modest, warm-path.
6. **R8** - Cloud Run offload. Only if a single large report still can't fit the 120s/4-worker envelope after 1-5.

Honest bottom line: **the easy ORM money is mostly spent.** If the profile confirms CPU dominance, expect single-digit-to-moderate percentage gains from each remaining item rather than the step-change R1-R3 delivered - which is itself the most important thing to tell the user before they invest in another refactor.

## Gotchas for planning

- **No calculation change, no API change** (PROJECT.md hard constraint): every item above is object-lifetime / query-shape / CPU-structure only. N1 and N2 need a **golden-file compare** of a generated report before/after (same fixture) as the regression gate.
- **Shared pipeline:** compute-layer items (N1, N2, N3, R5, R6) improve **both** Excel and the WeasyPrint PDF path (`views.py:1328`, `public/views.py`); R7 is Excel-only.
- **No local Postgres/Docker** in this sandbox: `py_compile` is the only local gate; the profiling recipe and golden-file compare must run in CI or on a DB-equipped machine.
- **`bulk_update` (R6)** skips signals/history by design - that is the win, but it means the `last_modified` guard and `skip_history_when_saving` must be reproduced explicitly, and auditlog will not see the cache-field writes (acceptable: they are derived data).
- **Project rule: no em-dashes** anywhere; conventional commits (`perf:`), feature branch off `develop`, PR targets `develop`.

## Sources

### Primary (HIGH confidence) - direct code reading on develop
- `api/reports/{__init__,base,cache,extractors,registry,land,modules}.py`
- `api/models.py` (`module_type_for_class`, `get_ready_status`, `Activity.modules`/`cache_modules`, `__get_all_modules`, `Project.is_ready`, `Module`/`Submodule`/`LandModule`, `CachedResultMixin`)
- `api/calculators.py` (`Result.__init__:408`, `BaseCalculator.__init__:528-563`)
- `math_model/no_time_dependency_final/ghg_emissions_classes.py` (`Result.__add__/__sub__:220-261`)
- `api/views.py` (`report:702`, `template:1309`), `public/views.py`, `djangoexact/settings.py` (`CONN_MAX_AGE`), `app.yaml` (gunicorn)
- Prior artifacts: `260716-g2x-RESEARCH.md`, `260716-g2x-SUMMARY.md`, `260716-gu0-SUMMARY.md`

### Assumptions
| # | Claim | Risk if wrong |
|---|-------|---------------|
| A1 | After R1-R3, remaining wall time is CPU-bound (math + aggregation), not ORM | The whole ranking flips toward N3/N+1 hunting; **this is exactly what the profiling recipe resolves** - treat A1 as unconfirmed until then |
| A2 | Modules in one report share a single `Activity`/`Project` instance via Django known-related-objects, so `BaseCalculator.__init__` FK reads are amortized | If some path re-fetches per module, R5's payoff is larger than stated; the query-count line of the profile shows it |
