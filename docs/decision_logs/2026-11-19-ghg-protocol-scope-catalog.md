# GHG Protocol scope catalog

**Date**: 2026-11-19
**Status**: accepted (provisional mapping; 11 topics pending review, listed below)

## Context

Analysts want EX-ACT results split by GHG Protocol scope (1, 2, 3). EX-ACT computes each flux as an
`ActivityTypes` member plus a `GasTypes` member, emitted by a module or a submodule entry, per scenario, per year.
Nothing in the calculation knows about scopes, and the scope of some fluxes depends on facts EX-ACT does not
collect yet (who owns the vessel, who runs the pump, where the waste is treated).

This first slice adds the catalog only: `djangoexact/api/scopes.py` and its tests. A later slice writes the Excel
scope sheets from it, and Phase 2 exposes it (and user choices) through the API.

## Decision

- **Scopes apply to gross per-scenario emissions, not to the balance.** The balance (with minus without) is not an
  inventory; a scope total only means something for one scenario. Emissions and removals are reported as separate
  per-year series inside each scope, so a removal never silently nets off an emission.
- **An outside-scopes bucket** (`Scope.OUTSIDE_SCOPES`) holds fluxes the team doc excludes from the scopes, today
  CO from fire on soil. `Scope.UNASSIGNED` exists only as the fallback for a flux with no rule; a test fails if any
  emitted activity reaches it, and at runtime it logs an error instead of failing the report.
- **The catalog is keyed by Python class name**, mirroring `api/inventory_labels.py`: default rules per activity
  (optionally per gas), then per-class overrides keyed by `type(source).__name__`. Never by `module_type.name`, which
  is translated. One input-dependent rule: irrigation pumping CO2 is Scope 2 for an electric pump and Scope 1 for a
  fuel pump, read from that scenario's `fuel_type_*` with the calculator's exact-case check. A missing fuel type
  stays UNASSIGNED (with a note): `IrrigationPhaseCalculator` raises in that case, so there are no numbers whose
  pumping type the scope could follow.
- **Provisional defaults come from the team's scope document.** Each rule also lists the scopes a user may pick
  (`allowed`), the Scope 3 category where known, and `pending_review` with a note naming the open question.
  `api/scopes.py` has 11 `pending_review=True` rule definitions (a 12th grep hit is the module docstring), one per
  topic; derived rules (`replace(...)` of a pending rule, such as electric irrigation CO2) inherit the flag, and the
  biomass fuel flag is applied on top of whichever FUEL rule matched, so class-specific Scope 3 categories survive. The 11 topics:
  1. Harvested wood products (`HWP_*`): Scope 1 gross removals vs LSR product storage category.
  2. Offsite peat extraction: depends on the peat's use (`is_peat_for_energy` is stored but unused).
  3. Waterbodies (`Coastal Waterbodies`): inclusion depends on the waterbody's function.
  4. Reservoirs (`Flooded Land CH4/CO2`): LSR books them as Scope 3 category 3 for electricity purchasers.
  5. Fisheries refrigerant: should it follow vessel ownership?
  6. Fisheries ice: stored as gas Other, labelled electricity CO2-eq; Scope 1, 2 or 3.
  7. Manufacturing of inputs (`CO2 Equivalent VC`): confirm meaning, check double counting with value chains.
  8. Biogenic CO2 from biomass fuels (`Fuel` CO2 when the scenario or start fuel is Wood or Charcoal, the fuel types
     whose default CO2 factor includes biogenic CO2): Scope 1 gross vs reported outside the inventory. Fossil fuel
     CO2 is a plain Scope 1 rule.
  9. Grid electricity: T&D losses multiplied in, which the GHG Protocol books as Scope 3 category 3.
  10. Irrigation pumping CO2 (fuel case): one series can mix electric and fuel pumping.
  11. Solid waste (5 activities): not in the team doc.
- **Ownership and control are a Phase 2 question.** Where the scope depends on ownership (vessels, contracted
  pumping, outsourced storage or transport, waste treated off site), the default follows the team doc and the
  alternative is listed in `allowed`. Phase 2 lets the user choose; this slice stores no choice.

## Tradeoffs

- Rejected: **scope as a calculator input.** Each calculator would tag its emission sets with a scope. It spreads a
  reporting concern across about 50 calculators and the pure `math_model`, invalidates every cached result, and a
  scope correction would mean recomputing results whose numbers did not change.
- Rejected: **a provenance-preserving `Result` restructure** (keep the source entry and scenario on every emission
  set through `Result.__add__`). It is the clean long-term model but touches every calculator and the result cache.
  The report already walks modules and entries, so it knows the source of each flux; the catalog only needs that.
- Cost of the chosen design: the rules are data maintained by hand next to the calculators. The completeness test
  catches a new activity without a rule, but not a flux whose meaning changes under an existing activity.
- Electricity series include grid transmission and distribution losses, so a "Scope 2" total overstates Scope 2 by
  the loss share until the losses are split out (pending).

## Sources

- GHG Protocol, Land Sector and Removals Standard v1.1 (2026):
  https://ghgprotocol.org/sites/default/files/2026-06/Land-Sector-and-Removals-Standard-v1.1.pdf
- IFI Harmonised GHG Accounting Guideline, v02.0 (2021).
- The team's scope mapping document (internal).
