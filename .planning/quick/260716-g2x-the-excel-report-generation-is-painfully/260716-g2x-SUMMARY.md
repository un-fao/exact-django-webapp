---
phase: 260716-g2x
plan: 01
subsystem: api
tags: [django-orm, lru_cache, performance, calculators, reports]

requires: []
provides:
  - Single Result construction per freshly-calculated module in reports/base.py (2 deepcopies instead of 6)
  - Module-level lru_cache memo for ModuleType.objects.get(class_name=...) via module_type_for_class()
  - Module-level lru_cache memo for the READY StatusType row via get_ready_status()
  - api/reference_cache.py with memoized SoilOrganicCarbon, NitrousEmissionFactor, ForestCombustionFactor, LitterDeadwoodCarbonStock, and ForestManagementRootToShoot (first-above-threshold) lookups, plus clear_reference_caches() escape hatch
affects: [excel-report-generation, pdf-report-generation, deforestation-calculator, oluc-calculator, forest-management-calculator]

tech-stack:
  added: []
  patterns:
    - "Per-process reference-data memoization via functools.lru_cache on module-level functions keyed by primitive ids/strings, never on methods taking self"

key-files:
  created:
    - djangoexact/api/reference_cache.py
  modified:
    - djangoexact/api/reports/base.py
    - djangoexact/api/models.py
    - djangoexact/api/calculators.py

key-decisions:
  - "Cached helpers return resolved model instances or None, never lazy querysets; every rewired call site only reads attributes off the returned instance"
  - "lru_cache applied only to module-level functions keyed by primitive args, never to methods taking self, per the locked R1 decision"
  - "ForestManagementCalculator internals (calculators.py ~7050-7085) and the manager's max-below-threshold/highest/lowest-value methods stay uncached because their results are mutated downstream"
  - "Two pre-existing argument quirks in the bgb_w and bgb_wo root-to-shoot lookups (both reusing land_use_type_start_id / land_use_type_w_id instead of the scenario-matching id) were preserved verbatim, not fixed, since fixing them would change computed results"

requirements-completed: [R1-MEMOIZE-REFERENCE-LOOKUPS, R2-SINGLE-RESULT-CONSTRUCTION]

coverage:
  - id: D1
    description: "reports/base.py builds exactly one Result per freshly-calculated module instead of three, removing 4 of 6 deepcopies per module"
    requirement: "R2-SINGLE-RESULT-CONSTRUCTION"
    verification:
      - kind: other
        ref: "python -m py_compile djangoexact/api/reports/base.py && grep -Fc 'Result(*self.result)' djangoexact/api/reports/base.py == 1"
        status: pass
    human_judgment: false
  - id: D2
    description: "ModuleType property lookups and the READY StatusType lookups inside calculators.py loops are memoized via module-level lru_cache helpers in api/models.py"
    requirement: "R1-MEMOIZE-REFERENCE-LOOKUPS"
    verification:
      - kind: other
        ref: "python -m py_compile djangoexact/api/models.py djangoexact/api/calculators.py && grep gates for zero StatusType.objects.get / one ModuleType.objects.get in calculators.py and models.py respectively"
        status: pass
    human_judgment: false
  - id: D3
    description: "Hot IPCC reference lookups (SoilOrganicCarbon, NitrousEmissionFactor, ForestCombustionFactor, LitterDeadwoodCarbonStock, root-to-shoot above-threshold) are served from api/reference_cache.py memos across all 11 identified call sites in calculators.py"
    requirement: "R1-MEMOIZE-REFERENCE-LOOKUPS"
    verification:
      - kind: other
        ref: "python -m py_compile djangoexact/api/reference_cache.py djangoexact/api/calculators.py && grep gates for zero direct ORM calls at the 11 rewired sites, one remaining direct call at the out-of-scope ForestManagementCalculator internal (line ~7064)"
        status: pass
    human_judgment: true
    rationale: "Static grep and py_compile confirm the rewiring is mechanically correct and complete, but confirming computed emission results are byte-identical requires running the Django test suite (pytest/manage.py test) against a real Postgres DB, which this sandbox does not have. This is deferred to CI per the plan's own verification section."

duration: 25min
completed: 2026-07-16
status: complete
---

# Quick Task 260716-g2x: Excel Report Generation Performance Summary

**Memoized immutable IPCC/ModuleType/StatusType reference lookups behind module-level lru_cache helpers and collapsed three redundant Result constructions into one, cutting hundreds of duplicate ORM queries and 4 of 6 deepcopies per freshly-calculated report module.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-16T09:33:00Z
- **Completed:** 2026-07-16T09:58:07Z
- **Tasks:** 3 completed
- **Files modified:** 4 (3 modified, 1 created)

## Accomplishments
- reports/base.py now constructs `Result(*self.result)` once per module and reads `emissions_set`, `emissions_set_w`, `emissions_set_wo` off that single instance, removing 4 of 6 full-MathResult deepcopies per freshly-calculated module (R2, research H4).
- `Module.module_type` and `Submodule.module_type` now resolve through a per-process `lru_cache` memo (`module_type_for_class`), eliminating a `ModuleType.objects.get()` query per inventory item during report generation (R1, research H3).
- The READY `StatusType` row is now fetched at most once per process via `get_ready_status()`, replacing three loop-internal queries in calculators.py's LUC readiness, deforestation readiness, and OLUC readiness checks (R1, research H1).
- New `djangoexact/api/reference_cache.py` memoizes the five hottest IPCC reference lookups in the deforestation and OLUC calculate paths (SoilOrganicCarbon, NitrousEmissionFactor, ForestCombustionFactor, LitterDeadwoodCarbonStock, ForestManagementRootToShoot first-above-threshold), rewiring exactly the 11 call sites identified in research H1, with a `clear_reference_caches()` escape hatch for tests/reference-data reloads.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build Result once per module in reports base (R2)** - `aa43f24c` (perf)
2. **Task 2: Memoize ModuleType property and READY status lookups (R1, part 1)** - `5aa0d172` (perf)
3. **Task 3: Cache hot IPCC reference lookups behind reference_cache module (R1, part 2)** - `15790cb0` (perf)

**Plan metadata:** committed separately by the orchestrator per constraints (SUMMARY.md/STATE.md not committed by this executor).

## Files Created/Modified
- `djangoexact/api/reference_cache.py` - New module: five lru_cache-decorated IPCC reference getters keyed by primitive ids, plus `clear_reference_caches()`
- `djangoexact/api/reports/base.py` - Single `combined_result = Result(*self.result)` instead of three separate constructions
- `djangoexact/api/models.py` - Added `module_type_for_class()` and `get_ready_status()` module-level lru_cache helpers; rewired `Submodule.module_type` and `Module.module_type` properties to use the memo
- `djangoexact/api/calculators.py` - Rewired 3 READY status readiness checks and 11 hot IPCC lookup call sites to the memoized helpers; dropped the now-unused `StatusType` import

## Decisions Made
- Cached helpers return resolved model instances or None, never lazy querysets, and callers only ever read attributes off them (verified by grep across every rewired call site), so no cached instance can be silently mutated.
- Preserved two pre-existing argument quirks verbatim in the `bgb_w` and `bgb_wo` root-to-shoot lookups (both reuse `land_use_type_start_id` / `land_use_type_w_id` rather than the scenario-matching id) per the plan's explicit instruction not to fix them, since fixing would change computed results.
- Left the `ForestManagementCalculator` internal `LitterDeadwoodCarbonStock` get (calculators.py ~7064) and the root-to-shoot manager's max-below-threshold/highest/lowest-value methods uncached, since their results are mutated downstream (threshold reassignment), matching the plan's mutation-safety guidance.

## Deviations from Plan

None - plan executed exactly as written. All three tasks' automated verify gates passed on the first attempt; no auto-fixes, no architectural questions, no auth gates encountered.

## Issues Encountered

None. Line numbers referenced in the plan shifted slightly across tasks as each prior task's edits changed file length (e.g., the forest management readiness check moved from calculators.py:823/824 to 824/825 after Task 2's first edit); this was handled by re-reading the file content at each step rather than trusting absolute line numbers, with no functional impact.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three locked optimizations (R2, R1 parts 1 and 2) are complete; R3 through R8 from the research ranking remain explicitly out of scope and untouched (Activity.modules fetching, is_ready pre-pass, calculator construction timing, cache persistence, renderer, job offloading all unchanged).
- Local gates (py_compile on all four touched files, all plan grep verification gates, em-dash scan) all pass. Full-suite regression (pytest/manage.py test against real Postgres) is deferred to CI per the plan's own verification section, since this sandbox has no local Postgres/Docker - the plan's `human_judgment: true` coverage entry (D3) reflects this gap explicitly.
- No blockers for closing this quick task.

---
*Phase: 260716-g2x*
*Completed: 2026-07-16*

## Self-Check: PASSED

All created/modified files verified present on disk; all three task commit hashes (aa43f24c, 5aa0d172, 15790cb0) verified present in git log.
