---
slug: scenario-builder-overrides
status: diagnosed
trigger: "in /admin-scripts scenario builder, the per-change climate and soil-type overrides are not showing all available options. Why?"
created: 2026-07-13
updated: 2026-07-13
---

## Symptoms

DATA_START
- expected: In the admin_scripts scenario builder UI, the per-change climate and soil-type override selects should list all available climate and soil-type options (the full set known to the system / IPCC reference data).
- actual: The per-change climate and soil-type override selects show only a subset of the available options.
- errors: None reported by the user.
- timeline: Unknown; user just noticed. Not known whether it ever showed the full set.
- reproduction: Open the /admin-scripts scenario builder, add or edit a change, inspect the per-change climate and soil-type override dropdowns.
DATA_END

Notes (orchestrator pre-scan, verify during investigation):
- Candidate UI template for the per-change fieldset: djangoexact/admin_scripts/templates/admin_scripts/partials/change_fieldset.html
- Option data likely assembled in djangoexact/admin_scripts/views.py and/or djangoexact/admin_scripts/scenario_utils.py
- Related partials: scenario_add.html, scenario_panel.html, filter_options.html
- Goal is DIAGNOSIS ONLY: the user asked "Why?" — produce a Root Cause Report, do not apply a fix.

## Current Focus

hypothesis: The per-change climate/soil_type override option lists are derived from
  distinct values present in minitool.ChangeRecord (data-derived), not from the canonical
  reference set (api.Climate / api.SoilType). After a module_type is selected the
  htmx_filters endpoint narrows them further to values present only for that module_type.
test: Static code reading of the render paths (compile_scenarios, htmx_add_change,
  htmx_add_scenario, htmx_filters), the option source helper (_change_record_filter_choices),
  the templates (change_fieldset.html, filter_options.html), and the reference models.
expecting: If confirmed, the option lists trace to ChangeRecord.values_list(...).distinct()
  and never to api.Climate/api.SoilType, and htmx_filters scopes the queryset by module_type.
next_action: Root cause confirmed. Diagnosis-only mode: do NOT apply a fix. Report produced.

## Evidence

- timestamp: 2026-07-13
  checked: djangoexact/admin_scripts/views.py:35-60 (_change_record_filter_choices)
  found: The helper builds climates/moistures/soil_types via
    qs.exclude(<col>="").values_list("<col>", flat=True).distinct().order_by("<col>")
    over a ChangeRecord queryset (defaults to ChangeRecord.objects.all()). Options are the
    DISTINCT VALUES ACTUALLY STORED in ChangeRecord, not a canonical reference list.
  implication: Any climate/soil_type known to the system but not present in a computed
    ChangeRecord row can never appear in the dropdown. This is the primary limiter.

- timestamp: 2026-07-13
  checked: views.py compile_scenarios (276-301), htmx_add_change (422-450),
    htmx_add_scenario (453-484)
  found: All three initial/added render paths feed the fieldset from _change_record_filter_choices()
    with qs=None (all ChangeRecords). So even before any module_type is chosen, the list is
    already limited to values present somewhere in the ChangeRecord table.
  implication: The subset limitation exists at first render, independent of later narrowing.

- timestamp: 2026-07-13
  checked: views.py htmx_filters (398-419) and change_fieldset.html:109-116 (hx-trigger on
    module_type change into #..-filters-container) + filter_options.html
  found: When the change's module_type <select> fires change, htmx_filters re-queries
    qs = ChangeRecord.objects.filter(module_type=module_type) and re-renders the three
    dropdowns from that scoped queryset via filter_options.html.
  implication: After a module type is selected, the climate/soil_type options shrink to only
    the distinct values present for THAT module_type -- a second, tighter narrowing on top of
    the ChangeRecord-derived base set. Soil-type is hit hardest since many module types store
    only one or two soil_type values (or blanks, which exclude(soil_type="") drops).

- timestamp: 2026-07-13
  checked: djangoexact/minitool/models.py ChangeRecord (58-95)
  found: climate/moisture/soil_type are free-text CharFields populated only from computed
    permutation results (api/services/minitool_changes_import.py, minitool_compute.py, the
    import_changes management command). Rows exist solely for module/field/from/to/attribute
    combinations that have actually been computed and imported.
  implication: The option universe is gated by what has been computed, not by what is valid.

- timestamp: 2026-07-13
  checked: djangoexact/api/models.py Climate (307-313), Moisture (316-321), SoilType (324-330)
  found: Canonical reference models exist: api.Climate (is_active), api.Moisture (is_active),
    api.SoilType (active, is_coastal). These enumerate the full option set known to the system.
  implication: The "all available options" the user expects live in these reference tables,
    but the scenario builder never queries them; it queries ChangeRecord instead. This is the
    exact source vs expectation mismatch behind the symptom.

## Eliminated

- hypothesis: Template bug (options passed to context but not rendered, or {% include %}
    dropping climates/soil_types via `only`).
  evidence: change_fieldset.html:119-143 and filter_options.html loop over climates/moistures/
    soil_types correctly; scenario_panel.html includes change_fieldset without `only`, so parent
    context (which carries the choices) is inherited. Rendering is faithful to the data supplied;
    the shortfall is in the data source, not the template.
  timestamp: 2026-07-13

- hypothesis: A WHERE/exclude clause is wrongly discarding valid options (e.g. exclude(climate="")
    removing real values).
  evidence: exclude(<col>="") only drops empty-string values, which are non-options anyway. The
    limitation is the DISTINCT-over-ChangeRecord source plus per-module_type scoping, not an
    over-aggressive filter on otherwise-present values.
  timestamp: 2026-07-13

## Specialist Review

- specialist_hint: python (maps to python-expert-best-practices-code-review)
- status: deferred
- decision: This is a find_root_cause_only, autonomous session. No fix is applied here, so
  the specialist fix-direction review has no concrete change to gate. The python-expert
  review should run at fix-planning time (e.g. /gsd-plan-phase --gaps) against the proposed
  direction: sourcing the per-change climate/moisture/soil_type override options from the
  canonical reference models (api.Climate / api.Moisture / api.SoilType, filtered by active
  flags) rather than from ChangeRecord distinct values. Reviewer should confirm whether the
  existing per-module_type scoping in htmx_filters is intended (constrain to computed data)
  or a bug (should expose the full reference set).

## Resolution

root_cause: The per-change climate and soil-type override dropdowns are populated from the
  DISTINCT VALUES that already exist in the minitool.ChangeRecord table, via
  admin_scripts.views._change_record_filter_choices() ->
  ChangeRecord.objects...values_list("climate"/"soil_type").distinct(). They are NOT sourced
  from the canonical reference tables (api.Climate / api.SoilType) that define the full set of
  options known to the system. Two compounding effects follow:
  (1) At initial render every path (compile_scenarios, htmx_add_change, htmx_add_scenario) uses
      the unscoped ChangeRecord queryset, so only climate/soil_type values that appear in some
      already-computed ChangeRecord row are ever offered.
  (2) When a change's module_type is selected, admin_scripts.views.htmx_filters re-queries
      ChangeRecord.objects.filter(module_type=module_type) and re-renders the dropdowns
      (filter_options.html), narrowing the options to only the distinct values present for that
      one module_type -- a second, tighter subset.
  Result: the overrides show only the intersection of "value exists in ChangeRecord" and (after
  module selection) "value exists for this module_type", which is a strict subset of the full
  reference set the user expects.
fix: (diagnosis only -- not applied) Direction: source the per-change climate/moisture/soil_type
  override option lists from the canonical reference models (api.Climate / api.Moisture /
  api.SoilType, filtered by their active flags) instead of from ChangeRecord distinct values, in
  admin_scripts.views._change_record_filter_choices (or a new helper) and correspondingly in
  htmx_filters. Keep ChangeRecord-derived values only if the intent is truly to constrain to
  computed data; otherwise reference tables give the full set. Confirm desired behaviour with the
  product owner before changing, since htmx_filters was deliberately written to scope by module_type.
verification: (not performed -- diagnosis only; dev sandbox has no DB so runtime verification is
  not possible here)
files_changed: []
