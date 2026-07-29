---
phase: quick-260729-k8y
plan: 01
subsystem: api
tags: [django, drf, reports, weasyprint, inventory]

requires: []
provides:
  - "api/inventory_labels.py: a presentation-layer mapping from raw ActivityTypes strings to new Inventory display labels, keyed by module class name for overrides"
  - "Inventory rows relabeled at display time in the results API (GenericModuleViewSet.results) and in both the live and cached Excel report Inventory-sheet paths"
affects: [reports, api-results, inventory]

tech-stack:
  added: []
  patterns:
    - "Presentation-layer relabeling module with zero imports (no Django, no models, no math_model), applied at display time only, never touching the identity-key enum it relabels"

key-files:
  created:
    - djangoexact/api/inventory_labels.py
    - djangoexact/api/tests/test_inventory_labels.py
  modified:
    - djangoexact/api/views.py
    - djangoexact/api/reports/base.py
    - djangoexact/api/reports/cache.py

key-decisions:
  - "Override lookup keys strictly on type(module).__name__ (e.g. class Aquaculture), never on module.module_type.name, since the latter is modeltranslation-registered and changes with request language"
  - "views.py relabel is inserted after module.cache_results(...) and immediately before DynamicResultSerializer construction, covering both the cached and fresh-compute branches with one insertion while leaving the persisted JSONField cache raw"
  - "module_results is rebuilt via shallow copies (new list, new dict) rather than mutated in place, since on the cached branch it is the in-memory value of a model JSON field and mutating it risks persisting presentation labels on a later save"
  - "Test file placed directly in api/tests/, not api/tests/unit/, because api/tests/unit/__init__.py star-imports Django APITestCase modules and would drag in settings and a database"

requirements-completed: [LBL-01, LBL-02, LBL-03]

coverage:
  - id: D1
    description: "inventory_labels.py mapping module (DEFAULT_LABELS, MODULE_OVERRIDES, inventory_label()) with disjointness invariant between mapping keys and produced labels"
    requirement: LBL-01
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/test_inventory_labels.py#InventoryLabelTests (9 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Results API (GET /api/<module>/<pk>/results/?aggregate=activity) returns relabeled inventory activity strings on both the fresh-compute and cached branches, without persisting labels to module.cached_results_*"
    requirement: LBL-02
    verification:
      - kind: manual_procedural
        ref: "Deploy to review; GET /api/aquacultures/<pk>/results/?aggregate=activity then repeat with ?cached=true, per PLAN.md verification steps 1 and 3"
        status: unknown
    human_judgment: true
    rationale: "Requires a live Postgres-backed module instance and a running server; not reproducible in the no-database dev sandbox. Deferred to manual confirmation once deployed to review, per PLAN.md verification section."
  - id: D3
    description: "Excel report Inventory sheet shows relabeled IPCC Category values on both the live compute path (_inventory_items_from_module) and the cached path (build_inventory_from_cache)"
    requirement: LBL-03
    verification:
      - kind: manual_procedural
        ref: "Download a project Excel report and read the Inventory sheet, per PLAN.md verification step 4"
        status: unknown
    human_judgment: true
    rationale: "WeasyPrint/Excel report generation needs a full project with computed modules against Postgres; not reproducible in the no-database dev sandbox. Deferred to manual confirmation once deployed to review."

duration: 10min
completed: 2026-07-29
status: complete
---

# Quick Task 260729-k8y: Relabel Inventory Result Categories Summary

**Presentation-layer relabeling of IPCC Category strings in Inventory results (results API and Excel report), via a new zero-dependency api/inventory_labels.py mapping module, without touching the ActivityTypes enum used as an identity key**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-07-29T14:41:00+02:00 (approx, first commit 14:42:09+02:00)
- **Completed:** 2026-07-29T14:43:29+02:00
- **Tasks:** 2 completed
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- Added `api/inventory_labels.py`: `DEFAULT_LABELS` (11 entries), `MODULE_OVERRIDES` (one Aquaculture entry, 2 pairs), and `inventory_label(module, category)`, which resolves overrides first, then defaults, then falls back to the category unchanged
- Added `api/tests/test_inventory_labels.py`, a database-free `unittest.TestCase` covering every case in the plan's behavior list, including a real assertion that the set of produced labels is disjoint from the set of mapping keys (guarantees idempotency)
- Wired `inventory_label` into all three display sites: `GenericModuleViewSet.results` in `api/views.py` (both the cached and fresh-compute branches), `_inventory_items_from_module` in `api/reports/base.py` (live report path), and `build_inventory_from_cache` in `api/reports/cache.py` (cached report path)
- Verified `math_model/` and `api/reports/renderer.py` were left untouched, and that the git diff touches exactly the 5 planned files

## Task Commits

Each task was committed atomically:

1. **Task 1: Add the inventory label mapping module and its database-free unit test** - `9240d0f5` (feat)
2. **Task 2: Wire the three display sites to inventory_label** - `63d8b004` (feat)

_Note: Task 1 is `type="tracer"`. Its `<verify>` (the database-free unit test) was re-run and confirmed passing before Task 2 began, per the tracer feedback gate._

## Files Created/Modified

- `djangoexact/api/inventory_labels.py` - new: the mapping module (`DEFAULT_LABELS`, `MODULE_OVERRIDES`, `inventory_label`)
- `djangoexact/api/tests/test_inventory_labels.py` - new: 9-test database-free unit suite, including the disjointness invariant and idempotency checks
- `djangoexact/api/views.py` - added import; inserted relabel logic in `GenericModuleViewSet.results` after `module.cache_results(...)` and before `DynamicResultSerializer` construction
- `djangoexact/api/reports/base.py` - added import; `_inventory_items_from_module` now passes `item.activity.value` through `inventory_label(self.module, ...)`, leaving the "N/A" branch untouched
- `djangoexact/api/reports/cache.py` - added import; `build_inventory_from_cache` now passes the resolved `activity` string through `inventory_label(module, ...)` for `ipcc_category` only

## Decisions Made

- Override lookup keys strictly on `type(module).__name__`, never `module.module_type.name`, per the plan's stated reasoning (modeltranslation makes the latter language-dependent)
- `module_results` in `views.py` is rebuilt via shallow copies rather than mutated in place, to avoid ever writing a presentation label into a live `module.cached_results_*` field
- Test module placed in `api/tests/` (not `api/tests/unit/`) to keep it importable and runnable with plain `python -m unittest`, with no Django settings and no database

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The mapping and all three wiring sites are in place and verified locally (py_compile, unit tests, scope guard). Two verification items remain deferred per the plan itself, since the dev sandbox has no Postgres and cannot run the Django suite or exercise a real module/report:

- `python manage.py test api.tests` (in particular `api/tests/reports/`) should be run in CI or on a database-equipped machine; if any test asserts a renamed literal such as `"Soil CO2 Change"` in an Inventory row, the expectation should be updated to the new label rather than the mapping being weakened.
- Manual confirmation once deployed to review: `GET /api/aquacultures/<pk>/results/?aggregate=activity` (fresh and `?cached=true`), `GET /api/inputs/<pk>/results/?aggregate=activity` (unchanged wording), and the Excel report Inventory sheet.

No blockers.

---
*Phase: quick-260729-k8y*
*Completed: 2026-07-29*

## Self-Check: PASSED

All created/modified files found on disk; both task commits (`9240d0f5`, `63d8b004`) found in git log.
