---
status: resolved
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

- `djangoexact/api/inventory_labels.py`: inventory label mapping
- `djangoexact/api/reports/excel_manager.py`: Excel workbook generation
- `djangoexact/api/reports/base.py`: ProjectResult / ActivityResult assembly
- `djangoexact/api/reports/registry.py` + `modules.py`: per-module-type extract/render registry
- `djangoexact/math_model/no_time_dependency_final/ghg_inventory_class.py`: inventory data structure
- `djangoexact/api/calculators.py`: model -> math_model adapter layer

## Current Focus

bug_class: Bohrbug (deterministic, structural, same empty result on every run)

status: RESOLVED. Q1 value-semantics fix applied, targeted suites run against the
review database, and the Excel report rendered end-to-end with a clean before/after
on the same untouched project.

checkpoint_answers:
  q1_value_semantics: >
    "Fix to real emissions." User independently confirmed general_functions.py:358
    computes emissions_start but returns only (annual_emissions, sum(annual_emissions)),
    and confirmed these rows have never reached a report (both math objects hang off
    entry calculators via self.math_w at calculators.py:3923 and 5984, previously
    throwaway locals), so correcting them regresses no published number.
  q2_land_use_change: >
    "Out of scope, file as follow-up." Leave LandUseChange untouched, do not widen
    the diff. Recorded under Follow-ups.
  q3_verification: >
    Database now reachable via cloud-sql-proxy on 127.0.0.1:5432 against the SHARED
    review instance fao-exact-review. End-to-end verification expected.

next_action: none. Session complete and committed.

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

- checked: the seven container calculators, `InputCalculator:3741`, `EnergyCalculator:3905`,
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

- checked: Q1 value semantics, `general_functions.input_single_calculation` call sites
  found: `input_single_calculation_different_ef` has ZERO call sites anywhere outside its
  own definition (`grep -rn input_single_calculation --include=*.py`, excel_reference_version
  excluded and separately confirmed empty). The user's condition "if it shares call sites"
  is therefore false.
  implication: only `input_single_calculation` was changed. Its 6 call sites are all inside
  inputs.py as predicted (3 in Inputs, 3 in OperationPhaseIrrigation), so the return-shape
  change is fully contained. The sibling's divergence is recorded as a follow-up.

- checked: `NewIrrigation` baseline semantics (the 0 versus `ef * units_start / 1000` choice)
  found: `total_emissions = ef * (units_end - units_start) / 1000`, broken down over
  `compute_yearly_delta(units_start, units_end, ...)`. The quantity is a one-off embodied
  emission proportional to the AREA DELTA, i.e. infrastructure the project builds. Every
  family that records a real number records the start-year ANNUAL rate that seeds its yearly
  series (`ValueChain.emissions_start`, `ElectricityConsumption.annual_start`,
  `SolidAndLiquidFuelsConsumption.annual_start_*`), and this module has no such rate.
  `Roads` has the identical delta shape with an implicit units_start of 0 and already
  records 0.
  implication: CHOSE 0. `ef * units_start / 1000` would price irrigation infrastructure that
  existed BEFORE the project, a historical one-off rather than a baseline annual flux, and
  would be the only inventory row in the codebase carrying that meaning.

- checked: end-to-end Excel render, review DB via cloud-sql-proxy, project 4281
  ("test 2805 todelete2"), a project with all 7 families whose module caches had never been
  touched by this session
  found: BEFORE (pristine HEAD): "Coverage of the seven reported families: FOUND (0/7) []",
  MISSING (7/7) all of Input/Energy/Irrigation/Storage/Processing/Packaging/Transport, while
  Livestock DID contribute 9 rows. AFTER (fixed tree), same project: FOUND (7/7), MISSING
  (0/7).
  implication: the defect and the fix are both confirmed on real data, on the same project,
  with the only variable being the source tree. Livestock appearing in both runs confirms
  the fix does not disturb the families that already worked.

- checked: cache contamination during verification
  found: the FIRST end-to-end render (project 702) wrote corrected rows into that project's
  module caches. A subsequent pristine-HEAD render of 702 then showed 7/7 because HEAD was
  SERVING the cache the fixed run had just persisted, not recomputing.
  implication: this invalidated 702 as a before/after subject and is why project 4281 was
  used instead. It is also live confirmation of contributing cause (3): the cached inventory
  is what the report reads, so cache invalidation was genuinely required for the fix to be
  observable. Verified by direct inspection: 32 target-family modules elsewhere in review
  still hold the pre-fix `"inventory": []` payload.

- checked: Q1 fix against real Input data
  found: project 4281 InputEntry 548 has `value_start = 225.0`. Pre-fix, BOTH of its
  inventory rows would read 225.0. Post-fix the persisted cache holds
  `[{'value': 281.0892857142857, 'activity': 'N2O Field'}, {'value': 1072.500000075,
  'activity': 'CO2 Equivalent VC'}]`. Project 702 InputEntry 460: `value_start = 123.0`
  becomes 67.65; InputEntry 461: `value_start = 0.0` stays 0.0.
  implication: the rows now carry per-gas emissions rather than one repeated input quantity.
  The per-gas divergence is the tell: a single activity-data figure cannot differ by gas,
  an emission must.

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
  after the code fix. Confirmed live during verification: a pristine-HEAD render of project
  702 returned 7/7 correct families purely because it was serving the cache a fixed-code run
  had just written.
  (4) SECONDARY, code (the Q1 value-semantics defect, fixed after the user's decision):
  `Inputs` wrote `self.unit_start` and `NewIrrigation` wrote `self.units_start` into a column
  headed "Value (tCO2-eq)". Both are activity data (tonnes of input, hectares), not
  emissions. `input_single_calculation` computed the correct `emissions_start` and then
  discarded it, returning only `(annual_emissions, sum(annual_emissions))`, so the correct
  value was genuinely unavailable at the call sites. Latent rather than user-visible: these
  rows could never reach a report while cause (1) was suppressing them.

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
  (5) Q1 value semantics, per the user's "fix to real emissions" decision.
  `input_single_calculation` now returns a third value, `emissions_start`, which it already
  computed and threw away. The three `Inputs` rows record their own per-gas
  `emissions_start` instead of the shared `unit_start`. `NewIrrigation` records 0 rather
  than `units_start`. The schema version was NOT bumped again: version 2 has never been
  written by any deployed build, so the roll-up fix and this value fix ship as one
  unreleased change set, and `Input` and `Irrigation` are both already inside
  `INVENTORY_ROLLUP_FIXED_MODULES`, so the same invalidation covers both corrections.

verification:
  guardrail_verdict: accepted
  environment: >
    Review Cloud SQL (fao-exact-review) reached through cloud-sql-proxy on 127.0.0.1:5432.
    APP_MODE=review, 748 projects. Targeted suites only; the full suite was NOT run, per the
    shared-instance constraint. Django reported "Skipping setup of unused database(s):
    default", so no test_* database was created on the shared instance.
  signal_regression_test: >
    PASS. `api/tests/test_inventory_rollup.py` grew from 16 to 26 tests (10 added for Q1).
    Final run: "Ran 26 tests ... OK". The 10 new tests were verified RED against pristine
    HEAD first: "Ran 10 tests ... FAILED (failures=5, errors=3)", and the failures show the
    exact defect values rather than incidental errors, e.g.
    "AssertionError: 100.0 unexpectedly found in [100.0, 100.0, 100.0]" (unit_start repeated
    across all three gas rows), "AssertionError: Lists differ: [('New Irrigation', 'CO2',
    40.0)] != [('New Irrigation', 'CO2', 0)]" (units_start), and
    "ValueError: not enough values to unpack (expected 3, got 2)" on the return contract.
    The 2 that passed on HEAD are the deliberate no-regression guards (zero baseline stays
    zero; the yearly emission series is untouched).
  signal_no_collateral_damage: >
    PASS. Combined targeted run: "Ran 60 tests ... FAILED (failures=2)". Both failures are
    the pre-existing `inventory_label` wording drift, and both were reproduced identically on
    pristine HEAD ("Ran 34 tests ... FAILED (failures=2)", same two assertions
    "'Biomass Carbon stock' != 'Biomass'"). Zero new failures.
    `api/tests/test_inventory_labels.py` passes.
  signal_root_cause_not_symptom: >
    PASS. The changes are in the discovery mechanism, the container contract, the cache
    validity rule and the math layer's return contract. Nothing in the renderer or the sheet
    layout was touched.
  signal_diff_shape: >
    PASS. Additive and structural, not deletion-only. 4 source files plus 1 new test file.
  signal_revert_reproduces_bug: >
    PASS, end-to-end and on real data. Project 4281, all 7 families, caches untouched by this
    session. Pristine HEAD: "FOUND (0/7): []" / "MISSING (7/7)". Fixed tree, same project:
    "FOUND (7/7)" / "MISSING (0/7): []". Livestock contributed 9 rows in BOTH runs, so the
    families that already worked are unaffected.
  signal_end_to_end_render: >
    PASS. Excel reports rendered through `api.reports.generate_excel_report` and the produced
    workbook's Inventory sheet inspected with openpyxl. Three projects rendered with all
    seven families present: 702 (101 inventory rows), 951 (79), 942 (84), plus 4281 as the
    before/after subject. Project 702 shows the multi-component roll-up working: Storage
    contributes Storage/CO2, Electricity/CO2 and Fuel CO2/CH4/N2O rows from one module,
    which is exactly the case the old single-attribute lookup could not express.
    Families observed on the sheet: Input, Energy, Irrigation, Storage, Processing,
    Packaging, Transport, all 7 of 7.
  observed_values: >
    Q1 confirmed on real data. Project 4281 InputEntry 548 `value_start = 225.0`, which is
    what BOTH rows reported pre-fix; post-fix they read 281.0892857142857 (N2O Field) and
    1072.500000075 (CO2 Equivalent VC). Project 702 InputEntry 460: 123.0 becomes 67.65.
    InputEntry 461 with `value_start = 0.0` correctly stays 0.0. Irrigation rows are 0
    throughout, by the deliberate baseline decision.
  oracle_type: >
    derived (contract) plus one specified oracle. The roll-up assertions are on the
    aggregation contract: one representative per component, summed across components, merged
    by (gas, activity) across entries. The Q1 assertions are specified: the expected numbers
    are computed by hand from the documented formula
    (unit_start * unit_factor * ipcc_or_tier_2 * emissions_factor) with factors chosen so no
    correct result coincides with unit_start, so the assertion cannot pass by luck. Boundary
    neighbours covered: zero entries, one entry, two entries, no math module at all, zero
    baseline quantity, a gas whose factors are None, and tier-2 override.
  side_effects_on_review: >
    DISCLOSED. Rendering a report recomputes and calls `save_results_to_cache`, so this
    verification WROTE new cached inventory rows onto real review modules: 89 target-family
    modules across projects 702, 942, 951, 4281, 8205, 8211, 8212 and 8214. That is the
    intended self-healing behaviour of change (4) and the values written are the corrected
    ones, but it is a write to projects not created by this session and is recorded here
    explicitly. No project data, schema, migration or fixture was modified.
  not_verified_here: >
    Projects 8205/8211/8212/8214 ("Testing 31-7") and 444, 505, 520, 538 could not be
    rendered at all: they fail earlier with pre-existing data gaps unrelated to the inventory
    (missing RiceSFW tier-2 values, missing AGB growth rates, a missing organic-soil drainage
    EF, and an openpyxl "Cannot convert [list]" cell-write error). Those are separate defects
    and were not investigated. The full test suite was not run.

files_changed:
  - djangoexact/api/calculators.py (MATH_COMPONENT_GROUPS, inventory property, entry-calculator tracking, 7 containers wired)
  - djangoexact/math_model/no_time_dependency_final/inputs.py (OperationPhaseIrrigation argument order; Inputs and NewIrrigation inventory values)
  - djangoexact/math_model/no_time_dependency_final/general_functions.py (input_single_calculation returns emissions_start)
  - djangoexact/api/reports/cache.py (INVENTORY_SCHEMA_VERSION and scoped invalidation)
  - djangoexact/api/tests/test_inventory_rollup.py (new, 26 regression tests)

resolved_questions:
  - >
    VALUE SEMANTICS (Q1): ANSWERED and FIXED. User decided "fix to real emissions".
    `input_single_calculation` now returns `emissions_start`; the three `Inputs` rows record
    their own per-gas start-year emission. `NewIrrigation` records 0. All 7 families now
    report tCO2-eq rather than activity data. Rationale and evidence above.
  - >
    LANDUSECHANGE (Q2): ANSWERED. Out of scope by user decision, left untouched. See
    Follow-ups.
  - >
    VERIFICATION (Q3): ANSWERED. Database reachable, end-to-end render performed. See
    verification.signal_end_to_end_render.

## Follow-ups

Separate issues, deliberately NOT addressed in this change set.

- id: luc-empty-inventory
  title: LandUseChange has the same empty-inventory defect
  status: out of scope by explicit user decision (Q2), do not widen this diff
  detail: >
    `LandUseChangeCalculator` (calculators.py:755) has the identical container shape:
    it builds throwaway Deforestation / OtherLandUse calculators and assigns no math module
    of its own, so `BaseCalculator.inventory` returns empty for it. It was deliberately left
    out of the roll-up because its child land modules may also be reported separately, and
    rolling it up could double count. Settling that needs a project whose LandUseChange and
    child land modules are both present, and a decision on which level owns the row.
  next_step: file as its own issue and investigate with a purpose-built project.

- id: zero-baseline-ipcc-treatment
  title: Confirm the zero-baseline treatment for project-built infrastructure
  status: open question for the domain owner, not a code defect
  detail: >
    Three activity rows now record a hard 0 for their start-year inventory: `Roads`
    (inputs.py, pre-existing), `OperationPhaseIrrigation` (set here) and `NewIrrigation`
    (set here). The reading is that infrastructure the project builds has no baseline
    emission, since the emission is a one-off proportional to the built delta rather than an
    annual rate. This is internally consistent across the three and matches the pre-existing
    Roads precedent, but it has not been checked against IPCC guidance by a domain expert.
    Observable effect: the Irrigation family shows a full set of correctly labelled rows
    whose values are all 0.
  next_step: confirm with the EX-ACT science owner whether 0 is the intended treatment.

- id: inventory-label-wording-drift
  title: Two pre-existing test_cache.py failures from inventory_label wording
  status: pre-existing, unrelated to this session, NOT introduced here
  detail: >
    `api/tests/reports/test_cache.py` fails 2 tests,
    `TestBaseModuleReportDispatcher.test_inventory_items_uses_live_inventory_when_from_cache_false`
    (line 369) and `TestBuildInventoryFromCache.test_reconstructs_inventory_items_correctly`
    (line 197), both with "AssertionError: 'Biomass Carbon stock' != 'Biomass'".
    `inventory_label` renames "Biomass" to "Biomass Carbon stock" and the tests still assert
    the raw wording. Reproduced identically on pristine HEAD, so it is not a regression from
    this work. Either the label or the expectation is stale.
  next_step: decide which side is authoritative and fix the mismatch.

- id: input-single-calculation-different-ef-divergence
  title: Sibling helper still returns a 2-tuple
  status: minor, deliberately deferred to keep this diff narrow
  detail: >
    `input_single_calculation` now returns 3 values; its sibling
    `input_single_calculation_different_ef` still returns 2. The sibling has ZERO call sites
    anywhere in the codebase, which is why the user's "if it shares call sites" condition did
    not apply and why it was left alone. A future caller switching between the two would hit
    a loud ValueError on unpacking rather than a silent wrong number, so the risk is low.
  next_step: either align the signatures or delete the unused helper.

- id: projects-that-cannot-render
  title: Several review projects fail report generation for unrelated reasons
  status: observed during verification, not investigated
  detail: >
    Projects 444, 505, 520, 538 and the four "Testing 31-7" projects (8205, 8211, 8212, 8214)
    could not be rendered. Causes seen: NotReadyError for missing RiceSFW tier-2 values,
    missing AGB growth rates, a missing organic-soil drainage EF, and an openpyxl
    "ValueError: Cannot convert [1584.0, 1232.0, ...] to Excel" when a list reaches a cell
    write. The last one looks like a genuine code defect rather than a data gap and may be
    worth its own session.
  next_step: triage separately, starting with the openpyxl list-to-cell error.
