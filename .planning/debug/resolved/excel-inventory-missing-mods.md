---
status: awaiting_human_verify
trigger: |
  from the team: "emissions from irrigation, inputs, energy, packaging, transport, storage and processing are not picked up for the inventory in the excel report"
created: 2026-07-31
updated: 2026-07-31
---

# Debug: Excel report inventory misses non-land module emissions

## Symptoms

**Expected behavior**
Emissions computed for the irrigation, inputs, energy, packaging, transport, storage and
processing module families should be picked up by the inventory in the Excel report,
the same way land-module emissions are.

**Actual behavior**
Those seven module families are not picked up for the inventory in the Excel report.
Reported by the team; the exact output surface ("the inventory") was not pinned down by
the reporter. Determining whether this is a missing Inventory sheet row, a zeroed value,
or a module family absent from the inventory aggregation is part of the investigation.

**Error messages**
None reported. Silent omission, not a crash.

**Timeline**
Unknown. No information from the team on whether this ever worked. Part of the
investigation is to determine via git history whether this is a regression (inventory
support existed and broke) or a never-implemented gap (inventory only ever covered land
modules / a subset of module types).

**Reproduction**
No project ID supplied. This sandbox has no Postgres, so reproduction is static:
trace the report/inventory code paths in `djangoexact/api/reports/` (notably
`excel_manager.py`, `base.py`, `modules.py`, `registry.py`, `data_types.py`,
`constants.py`) and `djangoexact/api/inventory_labels.py`, plus the inventory
construction in `djangoexact/math_model/no_time_dependency_final/ghg_inventory_class.py`
and how calculators feed it.

**Scope decision from user**
Fix all seven module families so they flow into the inventory correctly. Do not stop at
diagnosis.

## Known code landmarks

- `djangoexact/api/inventory_labels.py` — inventory label mapping
- `djangoexact/api/reports/excel_manager.py` — Excel workbook generation
- `djangoexact/api/reports/base.py` — ProjectResult / ActivityResult assembly
- `djangoexact/api/reports/registry.py` + `modules.py` — per-module-type extract/render registry
- `djangoexact/math_model/no_time_dependency_final/ghg_inventory_class.py` — inventory data structure
- `djangoexact/api/calculators.py` — model -> math_model adapter layer

## Current Focus

bug_class: Bohrbug (deterministic, structural — same empty result on every run)

status: fix applied and self-verified, awaiting human verification on a real project

next_action: user renders an Excel report for a project containing the seven module
families and confirms the Inventory sheet now lists their rows. Then decide on the value
semantics question recorded under Resolution.open_questions_for_user.

reasoning_checkpoint:
  hypothesis: >
    `BaseCalculator.inventory` discovers its math object through a hardcoded
    five-name attribute whitelist (`math_start`, `math_start_w`, `math_start_wo`,
    `math_w`, `math_wo`) and returns the FIRST match, else an empty `Inventory()`.
    The seven reported families never populate any of those five names, so all seven
    return an empty inventory and contribute zero Inventory rows. Two distinct
    reasons: (a) the container calculators delegate to per-entry sub-calculators
    created as throwaway locals; (b) some entry calculators store their math objects
    under other names (`energy_math_*`, `electricity_math_*`).
  confirming_evidence:
    - "All 7 container calculators build entry calculators as local variables and never assign self.math_* (calculators.py:3741, 3905, 5836, 7911, 8044, 8110, and TransportCalculator)."
    - "TransportEntryCalculator (8255) sets only energy_math_w / energy_math_wo; StorageEntryCalculator (8000/8019) sets electricity_math_*; PackagingEntryCalculator (8190/8209) sets energy_math_*. None are in the whitelist."
    - "Land calculators that DO work assign self.math_start_w / self.math_start_wo on the same instance the report holds (1674, 2263, 2699, 3030), which is exactly why land rows appear and these seven do not."
    - "The math layer already populates inventories for every one of the seven (inputs.py:55/74/93/215/273/323/353, value_chains.py:47). The data exists and is simply never read."
    - "renderer._write_inventory is faithful: an empty item list renders the 'No inventory data available' placeholder, matching the reported symptom exactly."
  falsification_test: >
    If a container calculator did populate any whitelisted attribute, or if the
    report held an entry calculator rather than the container calculator, the
    hypothesis would be wrong. Checked both: registry.py maps only container models,
    and each report's __post_init__ assigns the container calculator.
  fix_rationale: >
    Addresses the root cause (inventory discovery), not the symptom (missing rows).
    Two coordinated changes: (1) generalize discovery from a single whitelist to
    per-component groups so differently-named math objects are found, taking one
    representative per component (scenarios share identical start-year rows, so
    summing them would double count) and summing across components (a value chain's
    own emissions and its energy use are distinct rows); (2) let container
    calculators retain their entry calculators so their inventories roll up. This
    mirrors the precedent already in land.py (_merge_minor_inventories), which
    solved exactly this problem locally for flooded-rice minor seasons.
  blind_spots:
    - "No DB in this sandbox, so no end-to-end Excel render. Verification is static plus targeted unit tests that do not need Django."
    - "The one-representative-per-component rule assumes every scenario variant carries identical start-year figures. Verified for Inputs (unit_start), ValueChain (input_quantity_start) and Energy (mwh_start is quantity_consumed_per_year_start in all three inputs dicts), but not exhaustively for every module."
    - "Value semantics of the inventory column are a separate latent defect (see below). Not fixed here."
  candidate_causes:
    - "code: hardcoded attribute whitelist in BaseCalculator.inventory misses non-land math objects (CONFIRMED, primary)"
    - "code: container calculators discard entry calculators, so nothing to roll up (CONFIRMED, primary)"
    - "code: OperationPhaseIrrigation passes InventoryPerGasPerActivity args in the wrong order (CONFIRMED, secondary)"
    - "data: module caches persist the empty inventory, so already-computed projects stay broken after a code fix (CONFIRMED, contributing)"
    - "environment: ruled out. No env/config input feeds inventory assembly."
  and_gate: >
    YES, multiple contributing conditions. Fixing the plumbing alone is NOT
    sufficient: (1) OperationPhaseIrrigation passes (0, GasTypes.CO2, activity) into
    a (gas_type, value, activity) signature, so once its inventory is actually read,
    Inventory.add_emission would do `GasTypes.CO2 += GasTypes.N2O` and raise
    TypeError, and inventory.to_dict() would emit a non-JSON-serialisable enum. It
    must be fixed in the same change. (2) Existing module caches hold the empty
    inventory and are keyed only on last_modified, so unmodified modules would keep
    serving empty rows after the code fix. Cache invalidation is required for the
    fix to be observable on existing projects.

hypothesis: The seven reported families are exactly the "container" module types whose
calculators delegate all math to throwaway per-entry sub-calculators and never assign
`self.math_*`. `BaseCalculator.inventory` only reads `self.math_start / math_start_w /
math_start_wo / math_w / math_wo`, so on a container calculator it falls through and
returns an empty `Inventory()`. The report layer holds the CONTAINER calculator, so
`_inventory_items_from_module` yields `[]` and no Inventory rows are written.

test: static trace of container calculator -> BaseCalculator.inventory -> report ->
renderer, contrasted against a land calculator that does set `self.math_start_w`.

expecting: land calculators assign `self.math_*` on self (inventory found); container
calculators assign nothing (empty inventory). Confirmed for all seven.

next_action: check git history for regression-vs-gap, then AND-gate check for a second
defect in the math layer (suspected swapped args in OperationPhaseIrrigation).

## Evidence

- checked: `api/reports/excel_manager.py`
  found: only creates the sheet skeleton (`wb.create_sheet("Inventory")`). No writing.
  implication: not the defect site; look at renderer + data assembly.

- checked: `api/reports/renderer.py:472 _write_inventory`
  found: writes one row per `self.result.inventory_items`; if the list is empty it writes
  the single placeholder "No inventory data available for this project.".
  implication: the renderer is faithful. Missing rows means `inventory_items` is empty for
  those modules, not a rendering bug.

- checked: `api/reports/base.py:492 _build_inventory_items` and `:165
  _inventory_items_from_module`
  found: project-level items are just the concatenation of every ModuleResult's
  `_inventory_items`. Per module, items come from `self.inventory.emissions_by_sector_by_gas`
  (live path) or `build_inventory_from_cache` (cached path). `if self.inventory is None:
  return []`.
  implication: an EMPTY (not None) Inventory also yields zero rows, silently.

- checked: `api/reports/registry.py:50`
  found: registry maps the CONTAINER models: `api_models.Energy -> EnergyReport`,
  `Input -> InputReport`, `Irrigation -> IrrigationReport`, `Transport`, `Packaging`,
  `Processing`, `Storage`. Entry/submodule models are NOT registered.
  implication: the report object always wraps a container module, so it holds a CONTAINER
  calculator.

- checked: `api/reports/modules.py` (EnergyReport:501, InputReport:605, IrrigationReport:697,
  and the Transport/Packaging/Processing/Storage equivalents)
  found: each `__post_init__` does `self.calculator = calculators.<X>Calculator(self.module)`
  i.e. the container calculator. Each `compute()` then separately instantiates per-entry
  calculators as LOCAL throwaways to build the result rows, and calls
  `self._inventory_items_from_module(...)` which reads the CONTAINER calculator's inventory.
  implication: the result rows are correct (they go through entry calculators) but the
  inventory rows come from a different, empty object. This is exactly why the numbers show
  up on the Results sheet but not on the Inventory sheet.

- checked: `api/calculators.py:586 BaseCalculator.inventory`
  found: `for math_module in [self.math_start, self.math_start_w, self.math_start_wo,
  self.math_w, self.math_wo]: if math_module and hasattr(math_module, "inventory"): return
  math_module.inventory` then `return Inventory()`.
  implication: the fallback returns an EMPTY Inventory, not None. Combined with
  `_inventory_items_from_module`, an empty inventory produces zero rows with no warning.

- checked: the seven container calculators — `InputCalculator:3741`, `EnergyCalculator:3905`,
  `IrrigationCalculator:5836`, `StorageCalculator:7911`, `ProcessingCalculator:8044`,
  `PackagingCalculator:8110`, `TransportCalculator` (same shape)
  found: every one has the identical body: build two empty `MathResult`s, loop over
  `module.submodules` / `.entries` / `.irrigation_systems` + `.irrigation_phases`, construct
  `<X>EntryCalculator(entry)` as a LOCAL variable, add `r_w`/`r_wo` into `self.results_*`,
  and return. None of them ever assigns `self.math_start`, `self.math_w`, `self.math_wo`, and
  none of them merges the entry calculators' inventories.
  implication: `calculator.inventory` is an empty `Inventory()` for all seven. ROOT CAUSE.

- checked: contrast with land calculators
  found: `AnnualCropCalculator:1674`, `PerennialCropCalculator:2263`,
  `FloodedRiceSeasonCalculator:2699`, `GrasslandCalculator:3030` all assign
  `self.math_start_w = Math<X>(...)` on the SAME instance the report holds.
  implication: land inventory works precisely because the math object lives on the
  calculator the report owns. Non-land containers break the chain. This explains why the
  bug is scoped to exactly the seven reported families.

- checked: the math layer for the seven families
  found: the per-entry math classes DO populate `self.inventory`:
  `inputs.Inputs:55,74,93`, `inputs.ElectricityConsumption:273`,
  `inputs.SolidAndLiquidFuelsConsumption:323-325`, `inputs.NewIrrigation:353`,
  `inputs.OperationPhaseIrrigation:215-217`, `inputs.Roads:242`,
  `value_chains.ValueChain:47-48` (covers Storage/Processing/Packaging/Transport).
  implication: the data exists and is computed. It is simply never surfaced past the entry
  calculator. The fix is plumbing, not new science.

- checked: `api/reports/cache.py:134 save_results_to_cache` and `:106
  build_inventory_from_cache`
  found: the cache persists `inventory.to_dict()` taken from the same
  `BaseModuleReport.inventory`, i.e. the empty container inventory.
  implication: BOTH the live and the cached path are poisoned, and already-computed projects
  have an empty inventory list persisted in their module cache. The fix must invalidate or
  overwrite those cached entries, otherwise fixed code still renders empty rows.

- checked: git history (`git log -S` on the inventory code in calculators.py and
  reports/base.py)
  found: every hit is the single bulk import commit `fe90f7d7`. No commit ever added or
  removed inventory roll-up for the container calculators.
  implication: NEVER-IMPLEMENTED GAP, not a regression. Nothing to revert to.

- checked: `api/reports/land.py:213/325` and `_merge_minor_inventories:690`
  found: the report layer already re-runs minor-season sub-calculators and merges their
  inventories for PerennialCropland and FloodedRice, then re-saves the cache.
  implication: the identical problem was found and patched once, locally, for land minor
  seasons only. The general case for non-land containers was never done. Confirms the gap
  reading and gave the fix its shape.

- checked: `OrganicSoilCalculator` (calculators.py:6436-6950)
  found: sets only `organic_soil_math_*` and `peat_extraction_math_*`, never a whitelisted
  name, so its inventory is empty too, even though `inlands.py` populates DRAINAGE,
  REWETTING, DRAINAGE_PEAT and OFFSITE_PEAT rows.
  implication: an EIGHTH affected family the team did not report. Fixed by the same change;
  no double-count risk because it sets no whitelisted attribute.

- checked: `LandUseChangeCalculator` (calculators.py:755)
  found: same container shape (throwaway Deforestation/OtherLandUse calculators), so its
  inventory is empty as well.
  implication: DELIBERATELY LEFT ALONE. Rolling it up could double count if the child land
  modules are also reported separately, and that cannot be confirmed without a database.
  Recorded as follow-up, not fixed.

- checked: pre-fix run of the new regression suite
  found: 5 assertion failures on the exact defect behaviours and 8 errors on the new API,
  while the 3 no-regression guards pass on both sides. Post-fix: 16/16 pass.
  implication: the suite genuinely bites on this bug rather than passing vacuously.

- checked: `api/tests/reports/test_cache.py` baseline
  found: 2 failures (`inventory_label` renames "Biomass" to "Biomass Carbon stock" but the
  test still expects the raw wording) BOTH before and after the change.
  implication: pre-existing, unrelated to this fix. Not a regression introduced here.

## Eliminated

- hypothesis: the Excel writer or the Inventory worksheet layout drops non-land rows
  evidence: `renderer._write_inventory` is type-agnostic; it writes whatever
  `result.inventory_items` holds and renders a placeholder when the list is empty. The list
  was empty at source.
  timestamp: 2026-07-31

- hypothesis: the report registry has no entry for the seven module families
  evidence: `registry.py:50` maps all seven container models to report classes, and each
  report class calls `_inventory_items_from_module`. Registration was never the problem.
  timestamp: 2026-07-31

- hypothesis: the math layer never computes inventory data for non-land modules
  evidence: `inputs.py` and `value_chains.py` populate `self.inventory` for every one of the
  seven. The data was computed and then dropped.
  timestamp: 2026-07-31

- hypothesis: inventory keys off something land-specific (land_use_change,
  LandModuleCalculator, scenario triples)
  evidence: `BaseCalculator.inventory` is defined on the shared base and references no land
  concept. Land works only incidentally, because land calculators happen to store their math
  object under one of the five names the lookup knew.
  timestamp: 2026-07-31

## Resolution

root_cause: >
  Three contributing causes, all required for the reported symptom.
  (1) PRIMARY, code: `BaseCalculator.inventory` discovered its math module through a
  hardcoded five-name attribute whitelist (`math_start`, `math_start_w`, `math_start_wo`,
  `math_w`, `math_wo`), returned the first hit, and otherwise returned an empty
  `Inventory()`. The seven reported families never populate any of those five names, for two
  reasons: their container calculators delegate to per-entry sub-calculators created as
  throwaway locals and keep no math module of their own, and several entry calculators
  (Transport, Storage, Packaging) store their math modules under `energy_math_*` and
  `electricity_math_*` instead. Both fell through to the empty Inventory, so
  `_inventory_items_from_module` returned no rows and the sheet rendered its "no inventory
  data" placeholder. Land modules were unaffected only because they happen to assign
  `math_start_w` on the same instance the report holds.
  (2) SECONDARY, code: `OperationPhaseIrrigation` built `InventoryPerGasPerActivity(0,
  GasTypes.X, activity)` against a `(gas_type, value, activity)` signature, so gas_type was 0
  and value was an enum. Harmless while nothing read that inventory; once it is aggregated,
  `Inventory.add_emission` sums two GasTypes members and raises TypeError, and
  `to_dict()` emits a non-JSON-serialisable enum into the module cache.
  (3) CONTRIBUTING, data: module caches persist the empty inventory and are validated only
  against `last_modified`, so already-computed projects would keep serving empty rows even
  after the code fix.

fix: >
  (1) Replaced the five-name whitelist with `MATH_COMPONENT_GROUPS`, five component groups
  covering every math-attribute name in use. `BaseCalculator.inventory` now takes exactly one
  representative per component (scenario variants share identical start-year figures, so
  summing them would double count the baseline) and sums across components (a value chain's
  own emissions and the energy it consumes are distinct rows). It returns a freshly
  aggregated Inventory instead of a reference to calculator state.
  (2) Added `_track_entry_calculator` / `_reset_entry_calculators` / `entry_calculators` to
  BaseCalculator and wired all seven container calculators (8 call sites, Irrigation has two)
  so their entry calculators are retained and their inventories roll up. The reset guards
  against double counting when `calculate()` runs more than once on one instance.
  (3) Corrected the three swapped `InventoryPerGasPerActivity` calls in
  `OperationPhaseIrrigation`, keeping value 0 to match the existing Roads and deforestation
  placeholders rather than inventing a baseline.
  (4) Added `INVENTORY_SCHEMA_VERSION` to the cached payload and invalidated pre-fix caches
  for the eight affected module types only, so the fix is self-healing on existing projects
  without forcing a project-wide recompute of the land modules.

verification:
  guardrail_verdict: accepted
  signal_regression_test: >
    PASS. New suite `api/tests/test_inventory_rollup.py`, 16 tests. Verified RED on the
    pre-fix tree (5 assertion failures on the defect behaviours, 8 errors on the new API) and
    GREEN after (16/16). The 3 no-regression guards pass on both trees by design.
  signal_no_collateral_damage: >
    PASS. `api/tests/reports/test_cache.py` shows the same 2 failures before and after
    (pre-existing `inventory_label` wording drift). `api/tests/test_inventory_labels.py`
    passes. No new failures introduced.
  signal_root_cause_not_symptom: >
    PASS. The change is in the discovery mechanism and the container contract, not in the
    renderer or the sheet layout.
  signal_diff_shape: >
    PASS. Additive and structural, not deletion-only. 3 source files, +145/-16.
  signal_revert_reproduces_bug: >
    PASS. Stashing the three source files reproduces the empty-inventory failures exactly;
    restoring them clears the suite.
  oracle_type: >
    derived (contract). Assertions are on the aggregation contract: one representative per
    component, summed across components, merged by (gas, activity) across entries. Boundary
    neighbours covered: zero entries, one entry, two entries, no math module at all.
  not_verified_here: >
    No end-to-end Excel render. This sandbox has no Postgres, so a real project has not been
    rendered to xlsx and the Inventory sheet has not been eyeballed. Requires the user.

files_changed:
  - djangoexact/api/calculators.py (MATH_COMPONENT_GROUPS, inventory property, entry-calculator tracking, 7 containers wired)
  - djangoexact/math_model/no_time_dependency_final/inputs.py (OperationPhaseIrrigation argument order)
  - djangoexact/api/reports/cache.py (INVENTORY_SCHEMA_VERSION and scoped invalidation)
  - djangoexact/api/tests/test_inventory_rollup.py (new, 16 regression tests)

open_questions_for_user:
  - >
    VALUE SEMANTICS, separate latent defect, NOT fixed here. The Inventory column header is
    "Value (tCO2-eq)", but two of the seven families write a quantity rather than an emission
    into it: `Inputs` writes `self.unit_start` (tonnes of input) at inputs.py:55/74/93, and
    `NewIrrigation` writes `self.units_start` (hectares) at inputs.py:353. Energy, Storage,
    Processing, Packaging and Transport all write real start-year emissions and are correct.
    So after this fix 5 of the 7 families are fully right, while Inputs and Irrigation will
    show rows whose numbers are activity data, not tCO2-eq. Fixing that changes reported
    numbers and is a science decision, so it is deliberately left to the domain owner.
    `input_single_calculation` already computes the correct `emissions_start` internally but
    does not return it; all 6 call sites are inside inputs.py, so the change would be
    contained.
  - >
    Zero-valued placeholder rows: Roads (inputs.py:242) and now OperationPhaseIrrigation
    record 0 for their baseline, on the reading that infrastructure built by the project has
    no start-year emissions. Worth confirming that is the intended IPCC treatment.
  - >
    LandUseChange has the same empty-inventory defect but was left untouched, because
    rolling it up could double count if its child land modules are also reported separately.
    Needs a database to settle.
