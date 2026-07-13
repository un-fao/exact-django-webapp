---
slug: scenario-builder-overrides
status: resolved
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
next_action: RESOLVED (2026-07-13). Fix applied per the product-owner call: the per-change
  climate/moisture/soil_type override dropdowns are now sourced from the canonical reference
  tables (api.Climate / api.Moisture / api.SoilType, active-filtered) via the new
  _reference_filter_options() helper, and htmx_filters no longer narrows them by module_type.
  py_compile passed; DB-backed suite updated and must run in CI (no local Postgres/Docker).

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

- timestamp: 2026-07-13
  checked: djangoexact/minitool.db snapshot (sqlite3, 57,622 minitool_changerecord rows)
    vs api/fixtures/climate.json, soiltype.json, moisture.json
  found: ChangeRecord contains all 5 reference climates and all 3 moistures, but only
    3 of 9 active reference soil types (High Activity Clay, Low Activity Clay, Sandy).
    Missing: Aggregated, Mineral, Organic, Spodic, Volcanic, Wetland. Every module_type
    carries the same 5/3/3 distinct set, so the htmx_filters per-module narrowing is
    currently a no-op on this data. Note: deployed environments store minitool models in
    the default Postgres DB; minitool.db is a local snapshot.
  implication: Confirms the root cause empirically. Soil type is the dimension users see
    truncated (3 of 9). The missing values were never computed, consistent with rows being
    generated on demand.

- timestamp: 2026-07-13
  checked: user decision at fix checkpoint
  found: "ChangeRecord rows are computed on demand by users: populate the overrides from
    api.Climate/Moisture/SoilType." This settles the scoping-intent ambiguity flagged in
    the Specialist Review: constraining options to computed data is NOT intended behaviour.
  implication: Fix should source the three override dropdowns from the reference tables
    (active-filtered) in _change_record_filter_choices and htmx_filters.

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

- specialist_hint: python (maps to python-expert / python-pro best-practices review)
- status: completed (2026-07-13, run against the actual diff after the fix was applied)
- verdict: SUGGEST_CHANGE (minor, low-risk, in-scope), otherwise LOOKS_GOOD.
- checks: queryset idioms (idiomatic, column-narrow values_list, no N+1); import placement
  (api.models at module top, no circular-import risk since admin_scripts depends on api and
  not vice versa); dict-merge correctness (spread keys climates/moistures/soil_types do not
  collide with regions); behavioural regression (the only caller that passed qs for
  climate/moisture/soil narrowing, htmx_filters, was rewritten to bypass
  _change_record_filter_choices, so no caller silently loses expected narrowing; regions
  untouched).
- change applied: added return annotation `-> dict[str, list[str]]` to the new
  `_reference_filter_options` helper to document the flat-string-list contract the templates
  depend on. No behavioural change; re-ran py_compile clean.

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
fix: Added a new helper admin_scripts.views._reference_filter_options() that sources the per-change
  climate/moisture/soil_type override option lists from the canonical reference tables
  (api.Climate.filter(is_active=True), api.Moisture.filter(is_active=True),
  api.SoilType.filter(active=True), each ordered by name, returned as FLAT name lists).
  _change_record_filter_choices now keeps regions ChangeRecord-derived but spreads
  _reference_filter_options() for the three override lists, so every valid option is offered
  regardless of what has been computed into ChangeRecord. htmx re-render decision: htmx_filters is
  KEPT (minimal change) but no longer scopes by module_type; it now calls _reference_filter_options()
  directly and simply re-serves the full active reference set when a module_type is (re)chosen. The
  templates (change_fieldset.html / filter_options.html) were not touched (context keys
  climates/moistures/soil_types and their loop variables are unchanged).
verification: python -m py_compile passed on both touched files (admin_scripts/views.py,
  admin_scripts/tests/test_views.py). Static view/template cross-check confirmed all four render
  paths (compile_scenarios, htmx_add_change, htmx_add_scenario, htmx_filters) still supply
  climates/moistures/soil_types as flat string lists matching the unchanged template loops, and that
  regions/field/from/to logic was left intact. Existing DB-backed tests in test_views.py were updated
  (not newly created) to seed api.Climate/Moisture/SoilType reference rows and to assert the corrected
  behaviour, including a regression-proof case: active reference values absent from any Grassland
  ChangeRecord (Tropical / Wet / Organic) now appear, and inactive reference values (Boreal / Wetland /
  Aquic) do not. DB-backed runtime verification (running the suite / server) was NOT possible locally:
  this dev sandbox has no Postgres or Docker, so the updated TestCase suite must be exercised in CI or
  on a DB-equipped machine. py_compile is the reliable local gate and it passed.
files_changed:
  - djangoexact/admin_scripts/views.py
  - djangoexact/admin_scripts/tests/test_views.py
