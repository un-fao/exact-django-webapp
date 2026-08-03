## 1.20 (2026-08-03)

### Feat

- **api**: wire inventory_label into results API and Excel report paths
- **api**: add inventory_labels mapping module and unit tests
- **api**: sweep orphaned shell projects from failed async copies
- **ci**: add review-only Cloud Run deploy workflow
- **deploy**: add Cloud Run service manifest template
- **deploy**: add Cloud Run web service Dockerfile
- **deploy**: add whitenoise for Cloud Run static file serving
- **api**: expose activity_count and module_count on project serializers
- **api**: email report failures and log SMTP errors (email-first)
- **api**: email async report link, 24h token download, cleanup command
- **api**: add size-threshold async project copy (copy/async + copy_jobs)
- **api**: stream async report via GET /async-jobs/{id}/download/
- **api**: add POST /projects/{pk}/report/async/ enqueue endpoint
- **api**: add async report worker handler (report_jobs.run)
- **api**: add reconcile_stale_async_jobs safety-net command
- **api**: add AsyncJob polling endpoint (GET /api/async-jobs/{id}/)
- **api**: add run_async_job management command
- **api**: add AsyncJob enqueue/dispatch service (Cloud Run + subprocess)
- **api**: add generic AsyncJob model for background jobs
- **api**: cap activities per project at 50 across create, build, and copy paths
- **api**: add ready toggle to activity list filter
- **api**: accept multiple statuses in activity list filter
- **api**: filter activity list by computed status
- **01-02**: add requirements-dev.txt pinning bandit and pip-audit
- **01-02**: add test-seed loaddata fixture for base test classes
- **01-01**: register production config check in ApiConfig.ready()
- **01-01**: add production config deploy check
- **api**: compute_module_slice routes LandUseChange to _compute_luc_slice
- **api**: _compute_luc_slice runs calculator inside rolled-back transaction
- **api**: build saved Project/Activity/sibling/LUC fixtures for permutations
- **api**: iterate concrete LUC value combinations across template pair
- **admin_scripts**: route LandUseChange through plan_luc_pairs
- **admin_scripts**: plan_luc_pairs emits 144 directed template pairs
- **admin_scripts**: list templates and identifier helpers for LUC permutations
- **admin_scripts**: expand LUC preset templates to concrete combos
- **admin_scripts**: add LUC preset spec for permutations
- **admin_scripts**: per-module reference-data validator filters bad pairings
- **admin_scripts**: flesh out Test All Modules templates
- **admin_scripts**: add Test All Modules views, URLs, dashboard entry
- **admin_scripts**: runner honors ComputationJob.max_rows
- **admin_scripts**: add enqueue_for_test_run with run-scoped hash
- **admin_scripts**: add test_planner with plan_module_tests
- **admin_scripts**: hash max_rows and force_key when present
- **admin_scripts**: add ModuleTestRun model and ComputationJob.max_rows
- **scenario-builder**: restore in-tab stat grid, accordion compare panels, wider layout
- **scenario-builder**: clear removed scenarios from comparison state
- **scenario-builder**: render comparison data table on Compare tab
- **scenario-builder**: render per-change composition stack on Compare tab
- **scenario-builder**: render distribution box plots on Compare tab
- **scenario-builder**: render mean +/- CI 95% bar chart on Compare tab
- **scenario-builder**: render Compare tab status chips with threshold rules
- **scenario-builder**: ingest run-scenario results into window.scenarioResults with stale tracking
- **scenario-builder**: add compare.js skeleton and load Chart.js CDN
- **scenario-builder**: add Compare tab and empty compare panel
- **scenario-builder**: add result_json and scenario_index to run-scenario response
- **scenario-builder**: add per_change rollup to stats_for_scenario
- **scenario-builder**: add outlier counts to stats_for_scenario
- **scenario-builder**: richer Excel export with per-scenario detail sheets
- **scenario-builder**: enable Energy, Irrigation, value-chain, settlement & LUC
- **scenario-builder**: restructure filters and add Tom Select comboboxes
- **auth**: maintain Staff Group with all permissions for is_staff users
- **auth**: auto-grant all permissions to staff users
- **scenario-builder**: scale export stats by unit, add Units column
- **scenario-builder**: add Units input to change fieldset
- **scenario-builder**: wire htmx_run_scenario to stats_for_scenario
- **scenario-builder**: parse per-change unit field from POST data
- **scenario-builder**: add stats_for_scenario with per-change unit scaling
- **scenario-builder**: add _coerce_unit helper for per-change multipliers
- **admin**: add is_opted_out_of_emails to CustomUser CSV export
- **admin_scripts**: register ComputationJob in Django admin
- Add is_opted_out_of_emails to RegisterSerializer and user serializers
- add ef_source_t2 and country_t2 to Small/Large Fisheries
- **jobs**: add cancellation/progress, fix Grassland processor, auto-populate ChangeRecord
- **jobs-panel**: add persistent jobs panel UI
- **notifications**: add job notifications with polling and email
- **cloud-run**: add Cloud Run Jobs dispatch with subprocess fallback
- **jobs**: wire gap detection and job enqueueing into scenario views
- **jobs**: add run_computation_job management command
- **jobs**: add gap detector and job dispatcher with coalescing
- **jobs**: add ComputationJob model for async computation tracking
- **catalog**: replace ChangeRecord dropdown queries with catalog
- **catalog**: add get_catalog() cached accessor
- **catalog**: add scenario_catalog.yaml with startup validation
- **catalog**: add scaffold_scenario_catalog management command
- **catalog**: add scenario catalog loader and validator
- **minitool**: remove sqlite DB alias and router
- **fixtures**: unified reference data pipeline
- **scripts**: add fix_bom_country_duplicates runscript
- **i18n**: fill missing es/ru labels and sanitize fr/ru msgstr formatting
- **scripts**: add runscript to sync cropland module types from IPCC CSV
- **scripts**: add rename_countries runscript for Q1 renames and Q3 duplicate merges
- **reports**: revise SPC NPV section per stakeholder feedback
- **calculators**: add dry matter content reference values to annual cropland model inputs
- **math_model,annuals**: add dry matter content to residues calculations
- **reports**: exclude is_b_intact activities from Excel report
- **api**: add faostat_year_t2 override to AnnualCropland
- **api**: fall back to CropYieldStat when FAOSTAT data is unavailable
- **api**: use username/password auth for FAOSTAT token retrieval
- **api**: use FAOSTAT yield data in AnnualCropCalculator
- **api**: add FAOSTAT yield data service
- **scripts**: add import functions for FiresCombustionFactor and CropNitrousEstimationDefaultFactor
- **models**: add new fields to CropNitrousEstimationDefaultFactor
- **reports**: auto-populate module cache after fresh calculation
- **reports**: cache land module units_breakdown to eliminate cached/non-cached data divergence
- **reports**: use module cached results instead of recalculating when valid
- implement Cumulative Heads and Catch Impacted rows in Excel report
- **export/import**: preserve full thread comments data
- **api**: add project import endpoint
- **api**: add project export endpoint
- **config**: add version.config.json and get_version_config helper
- **serializers**: add ProjectImportSerializer for validation
- **serializers**: add export serializers for Project, Activity, Module
- **models**: add export_id UUID field to Project
- **serializers**: add 'is_b_intact' field to ActivitySummarySerializer for enhanced activity tracking
- **admin-scripts**: update compile_scenarios_export to include summary sheet and adjust scenario handling
- **admin-scripts**: update export for multi-scenario workbook
- **admin-scripts**: restructure compile_scenarios for tab-based multi-scenario UI
- **admin-scripts**: add htmx_add_scenario view and scenario_panel template
- **admin-scripts**: add htmx_run_scenario view for per-scenario execution
- **admin-scripts**: extract scenario_results.html partial
- **admin-scripts**: update htmx views and templates for scenario-prefix support
- **admin-scripts**: add _extract_change_key_info helper for prefix detection
- **admin-scripts**: add _parse_scenarios_from_post helper
- **admin-scripts**: add prefix param to _parse_changes_from_post
- **admin-scripts**: add compile-scenarios UI with htmx
- **admin-scripts**: extend Tailwind content paths and rebuild CSS
- **admin-scripts**: add base, dashboard, and example script templates with Tailwind
- **admin-scripts**: add staff_required decorator, dashboard view, and example script view
- **admin-scripts**: register app and configure URL routing
- **admin-scripts**: create admin_scripts app skeleton
- Added tC to tCO2 converter to forest management
- Added constant to inventory calculation
- **reports**: reorder SPC tables and use dynamic NPV discounting exponent
- **.gitignore**: add docs/plans/ to ignored files
- **reports**: add SPC table with Net Present Value discounting
- **reports**: add Inventory sheet to Excel report
- **calculators**: integrate refrigerant emission factors in fisheries
- **calculators**: use project-level GWP for refrigerant calculations

### Fix

- **reports**: roll non-land module inventories into the Excel Inventory sheet
- **math_model**: record real emissions in inputs and irrigation inventory rows
- **ci**: sync SECRET_KEY into the computation job
- **ci**: verify report base URL by comparison, not by probing it
- **ci**: sync report download base URL into the computation job
- **ci**: stop minting report download links at a dead App Engine host
- **api**: raise KeyError from registry missing hook instead of re-indexing
- **minitool**: iterate connection aliases instead of calling items on a list
- **templates**: scope csrf suppressions to the firing Semgrep rule id
- **minitool**: resolve formatted-sql and len-count Semgrep findings
- **api**: replace dynamic globals() lookups with serializer registry
- **api**: bound ORM thread fan-out in request-path endpoints
- **api**: refresh updated_at when unlinking swept async jobs
- **settings**: trust X-Forwarded-Proto behind the Cloud Run/App Engine proxy
- **deploy**: set build-time DB_ENGINE for collectstatic in web image
- **ci**: bridge DB_USER from DB_USERNAME for runner-side migrate
- **ci**: address Semgrep SAST findings in Cloud Run deploy workflow
- **api**: correct inverted comment-thread permission check
- **api**: populate report user context and reconcile stuck-pending async jobs
- **api**: dedupe project-copy Admin membership and split copy into shell+populate
- **api**: give distinct emails to AsyncJob endpoint test users
- **api**: guard connection.close in run_async_job under atomic tests
- **api**: guard Cloud Run dispatch failures and env log-dir in async_jobs
- **api**: enforce activity cap on project reassignment
- **api**: ignore empty values in activities query param to avoid pk__in ValueError
- **deps**: bump PyJWT 2.12.1 to 2.13.0 for CVE-2026-48526/48522
- **api**: exclude lifecycle flags from Project cache invalidation
- **ci**: authenticate cloud-sql-proxy via ADC, not gcloud-auth
- **ci**: wait for cloud-sql-proxy readiness before deploy migrate
- **api**: clear stale scenario fields when swapping LUC module roles (exact-django-webapp-bor)
- **admin_scripts**: source scenario override options from reference tables
- **fixtures**: drop orphaned CropNitrous default factor for removed Generic Value LUC
- **reports**: label and align the Flooded Rice metadata block
- **reports**: use minor rice season Tier-2 cultivation period override
- **01**: use unusable password markers and high group pks in seed fixture (WR-03)
- **01**: gate CI-only TEST.NAME on CI=true to protect local databases (CR-02)
- **01-02**: add TEST.NAME to non-GAE DATABASES branch
- **reports**: count LUC hectares once in Cumulative Hectares Impacted (#195)
- **reports**: correct fishery catch totals and per-activity narrative
- **calculators**: None-guard dm_content_minor for crops missing IPCC dry_matter
- **api**: pin LUC fixture country to region with AGB coverage
- **api**: persist LUC slice results to ChangeRecord
- **admin_scripts**: resolve LandUseChange.module_type as preset identifiers
- **scenario_catalog**: remove references to t2 values
- **scenario_catalog**: add zero-values as options for numerical permuations
- **admin_scripts**: set land_use_type on ForestManagement preset
- **api**: set sibling.status=READY in _save_sibling so LUC calculator runs
- **api**: persist non-sided FK fields and forward max_rows in LUC slice
- **api**: populate project climate/moisture/soil_type in build_luc_fixture
- **api**: use factory-boy factories in build_luc_fixture for required fields
- **admin_scripts**: make Cycle hashable when filter holds list values
- **admin_scripts**: add Livestock combination validator
- **admin_scripts**: require field-level non-null on ForestManagementAGB
- **admin_scripts**: require single LitterDeadwoodCarbonStock row
- **admin_scripts**: SoilOrganicCarbon value-is-null still trips SOC check
- **admin_scripts**: extend Livestock + ForestManagement validators
- **admin_scripts**: tighten Livestock country pick + ForestManagement SOC validator
- **admin_scripts**: clear remaining Test All Modules failures from #4
- **admin_scripts**: clear FloodedRice + value-chain math failures
- **admin_scripts**: gate test-runner querysets on IPCC reference data
- **admin_scripts**: clear five more Test All Modules failure classes
- **admin_scripts**: unblock Test All Modules runner across modules
- **inputs**: model-side logical error causing zero values to be ignored
- **scenario-builder**: ensure new scenario tabs work correctly
- **scenario-builder**: use evt.detail.target for HTMX swap target with fallback scan
- **scenario-builder**: align Compare tab button indent with siblings
- **scenario-builder**: clarify outlier guard and comments per code review
- **scenario-builder**: stop double border on TomSelect comboboxes & hide stray template comment
- **reports**: surface exception details in narrative PDF errors
- **reports**: match cached GasTypes.OTHER entries in extract_emissions
- **deps**: patch security vulnerabilities flagged by Dependabot
- **defaults**: set self.values on @dataclass Defaults subclasses
- **scenario-builder**: populate scenario-level region filter
- **reports**: close remaining FloodedRice-audit findings (flx, 5g2, a34, wuz, 80d)
- **reports**: FloodedRice numbers wrong with minor seasons — aggregate at __post_init__
- **reports**: stop report PDF 500 and put cover on its own page
- **calculators**: SettlementCalculator double-counted land + start emissions
- **reports**: module total must be full balance — stop dropping calculator emissions
- **perennial_cropping**: honor explicit agb_maximum_c_tier_2 = 0
- **calculators**: extract salinity_type and soil_type_name into init of CoastalWetlandCalculator
- **fixtures**: add tropical climate in allowed climates for Agroforestry default LandUseType
- **fixtures**: deactivate alfalfa LandUseType
- **scenario-builder**: reject non-finite values in _coerce_unit
- **ci**: use version.id/version.createTime in gcloud app versions list
- **ci**: source DB/SECRET env from App Engine version, not GitHub secrets
- **jobs**: write Cloud Run env-vars via Python YAML; fix Operation API
- **ci**: hoist secrets to env block to stop bash from mangling $ in values
- **ci**: substitute CLOUD_RUN_COMPUTATION_JOB_NAME / CLOUD_RUN_REGION in app.yaml
- **admin_scripts**: propagate CSRF token on HTMX POSTs via base.html
- **ci**: build computation-job image with docker, not Cloud Build
- **security**: hoist github.* into env: block (Semgrep CI rule)
- **jobs**: use CMD not ENTRYPOINT and lift cloudbuild timeout
- **defaults**: reference of t2 soc for grassland
- **deaults**: show project-level soc override in grassland defaults
- **admin_scripts**: harden job dispatcher log dir for read-only deploys
- **fixtures**: remove Generic Value from landusetype fixture
- **calculators**: typo in SettlementCalculator existing infrastructure check
- **deploy**: plumb ALLOWED_HOSTS and CORS_ALLOWED_ORIGINS through deploy pipeline
- **deploy**: plumb DJANGO_DEBUG and SECRET_KEY through deploy pipeline
- **security**: resolve Semgrep findings across views, templates, and settings
- set is_public to False when copying projects
- **security**: resolve bandit security issues (B113, B307, B602, B608)
- **migrations**: make 0286 idempotent for historicalprocessingentry.fuel_type_thread
- **api**: make Swagger/ReDoc views publicly accessible
- remove gitleaks check
- **security**: solve npm vulnerabilities
- **api**: remove duplicate fuel_type_thread field from migration 0246
- **scripts**: remove db_manager("minitool") from minitool_import
- **admin_scripts**: remove minitool from test databases attr
- **minitool**: use default DB connection in import_changes
- **api**: correct FAOSTAT yield unit — kg/ha not hg/ha, divide by 1000
- **api**: convert FAOSTAT yield from hg/ha to t/ha
- **api**: reset faostat __BASE_URL__ before each set_requests_args call
- **api**: restore None sentinel for minor yield defaults in AnnualCropCalculator
- **api**: resolve FAOSTAT labels to numeric codes before querying
- **reports**: harden html_context and view error handling
- **reports**: remove wrong prefetch_related call to a class property
- **serializers**: save instance before validating parent LUC in LandModuleSeralizer
- **calculators**: issue causing LUC status to never be correctly evaluated first try
- **calculators**: typo in LivestockCalculator causing some complementary manure management variables for with to be set for without
- **extractors**: handle serialized list-of-dicts cache format in extract_emissions
- **general_functions**: normalize ef_system length array for gas_head_alculation so it always matches percentage_system_default
- **forest_management**: allow disturbance or logging calculations if any recurrence is nonzero
- **calculators**: fill ForestManagementCalculator disturbance_percentage_fire input array with 1 if the disturbance type is fire, 0 otherwise
- **calculators**: apply SOCInitial to LUC and infrastructure on existing land
- address 8 critical code quality issues in reports package
- correct ForestManagement _add chain and always write heads/catch zeros
- **compile-scenarios**: generate organic soil field changes for wetland scenarios
- **import**: resolve OneToOneField cross-module references during project import
- **calculators**: set forest management rshoot before 20 yrs to 0 if it is None
- **reports**: guard luc None access in OrganicSoilReport.populate_metadata
- **admin-scripts**: wrap OOB tab button in carrier div for htmx beforeend
- **admin-scripts**: update tests for multi-scenario naming convention
- **admin-scripts**: address code review issues for compile-scenarios
- **calculators**: add with and without calculators when looking for inventory emissions
- **perennial_cropping**: calculate inventory regardless of biomass emissions dynamics
- **api**: update error messages for drainage emission factors
- **deps**: upgrade djangorestframework-simplejwt to 5.5.0
- **api**: remove deprecated CoreAPI docs endpoint
- **deps**: upgrade drf-yasg to 1.21.14 to remove pkg_resources dependency
- **ci**: force reinstall setuptools after requirements installation
- **deps**: update packaging version to fix pkg_resources import error
- **deps**: add setuptools to requirements for pkg_resources at runtime
- **deps**: replace Pyrebase4 with direct Firebase REST API calls
- **deps**: add setuptools to requirements for pkg_resources compatibility
- **calculators**: consolidate values of initial BGB with FRA data source selected
- **calculators**: correct constructor method in LargeFisheryCalculator
- **reports**: include drainage soil CO2 in coastal wetland reports

### Refactor

- **reports**: defensively merge cache-write registrations for same row
- **api**: simplify dirty-field checks in Project/Activity save
- **api**: bulk-invalidate module caches instead of per-module threads
- **api**: drop Staff group auto-sync signals
- **admin_scripts**: wrap test-run POST in transaction, hoist imports
- **admin_scripts**: move _resolve_value_source to test_planner
- **admin_scripts/tests**: co-locate ComputationJob test, hoist imports
- **scenario-builder**: slim per-scenario result headline and add data wrapper
- **admin_scripts**: use statistics.stdev and inclusive quantiles in stats_for
- **scenario-builder**: extract _build_single_change_q from build_scenario_query
- extract Operating Margin to EmissionFactorSource constant
- **compute**: extract compute_module_slice from compute_minitool
- **api**: normalize yield attribute to .value in AnnualCropCalculator
- address notable code smells in reports package
- replace reports.py monolith with clean package architecture

### Perf

- **api**: cache serializer registry with refresh-on-miss
- **reports**: batch module cache writes with bulk_update (R6)
- **models**: select_related land_use_change for land modules (N3)
- **calculators**: drop redundant deepcopies in Result balance (N1)
- **reports**: share one module fetch per activity across report request
- **api**: memoize Activity module list per instance, select_related status
- **calculators**: cache immutable IPCC reference lookups
- **api**: memoize ModuleType and READY status lookups
- **reports**: build Result once per module in report base
- **api**: prefetch module_types in activity list to trim N+1

## 1.19.2a5 (2026-04-29)

### Fix

- **coastal_wetlands**: invert calculation logic of drainage stock biomass

## 1.19.2a4 (2026-04-20)

### Fix

- **i18n**: use .name_en for control-flow on translated models
- **deploy**: bump packaging to >=24.0 for GAE Cloud Build compatibility
- **deploy**: restrict setuptools version in deploy workflow and requirements.txt

## 1.19.2a3 (2026-03-24)

## 1.19.2a2 (2026-03-24)

### Fix

- replace outdate pyrebase library with custom lightwaight firebase wrapper

## 1.19.2a1 (2026-03-24)

### Fix

- **reports**: missing heads of livestock in activity breakdown

## 1.19.2a0 (2026-01-22)

### Fix

- **views**: add inventory breakdown to public module results

## 1.19.2 (2026-01-14)

### Fix

- **requirements**: set clear httplib2 version

## 1.19.1 (2026-01-14)

## v1.19.0 (2026-01-14)

### Feat

- add revised forest management agb, agb growth and root-to-shoot data
- **api**: add inventory breakdown to module results endpoint
- **organic_soil**: disable soc som of land modules when organic soil module is present in the activity
- **reports**: display activity T2 overrides in Excel metadata

### Fix

- **calculators**: old flu_wo reference to mathematical model causing wrong results
- **math_model**: wrong activity type for refrigerant inventory causing crash
- **not_cultivated_land**: correct indentation for appending SOM emissions to results
- **inventory**: wrong inventory class initialization throwing exception
- **inventory**: correct activity type in inventory initialization for ice emissions
- **inventory**: wrong inventory class initialization causing exception
- **inventory**: updated landuse models with if calculate_soc_som
- **inventory**: remove scenario-based logic in results and only aggregate by single start scenario
- **inventory**: move soil and som inventory calculations outside calculate_soc_som check
- **inventory**: update inventory aggregation to include additional math modules
- **inventory**: various math model issues causing crashes
- **math_model**: Updated import from ghg_inventory_class in inputs
- **math_model**: revert some absolute imports to relative imports
- **perennial_cropland**: account for agb_t2_start and bgb_t2_start only when it is replacing a reference value, not computed or zero
- **activity_builder**: issue causing removal of organic soil module to reset inputs of associated land modules
- **calculators**: revert disturbance_percentage_fire to empty list fallback

## 1.18.4a0 (2025-12-08)

## v1.18.4 (2025-12-08)

## 1.18.4 (2025-12-08)

### Fix

- **activity_builder**: wrong type in issubclass check
- **scripts**: exclude finalized project from cache reset in invalidate_results_cache

## 1.18.3a0 (2025-12-04)

### Feat

- **project**: make climate, moisture, and soil_type optional

### Fix

- **calculators**: add a workaround that sanitizes any modules with missing land_use_change references due to bug in ActivityBuilderSerializer
- **forest management**: add start year to agb matrix logging update
- **forest calculator**: update list absence to Nones instead of []

## v1.18.3 (2025-11-21)

### Feat

- **ci**: force results cache invalidation on new release
- **project**: add ability to manually lock and unlock projects

### Fix

- **ipcc**: logical issue causing the date for forest management AGB and AGBGrowth to be wrong for most entries
- **forest_management**: replace None with empty arrays to account for mathematical model requirements
- **project_copy**: issue caused by stale organic soil ids causing crash when copying projects with organic soil modules
- **math_model**: issue causing disturbances to be calculated even when only logging was present
- **math_model**: issue causing coastal wetland rewetting area not to be calulated correctly
- **activity**: issue causing double counting of hectares when computing total land modules area
- **activity**: issue causing double counting of hectares when computing total land modules area
- **project_copy**: issue causing the admin membership to be duplicated when duplicating a project
- **activity_builder**: add back activity creation logic
- **activity_builder**: prevent luc module type from always being added
- **activity_builder**: rewrite edit logic

## v1.18.2 (2025-10-23)

### Feat

- **minitool**: add api endpoint to get results for all scenarios
- **minitool**: add mitigation scenarios
- **admin**: add ability to upload files to Hand In Hand Assessments from admin panel

### Fix

- **activity_builder**: rewrite activity edit logic for better clarity and performance
- **forest_management**: issue causing bgb max start to always be zero
- **activity**: issue causing only preexisting module types to be involuntarily cleared from activity module types when editing an activity
- **activity**: issue causing duplicate modules when editing an activity without adding or removing any module
- **organic_soil**: issue causing peat extraction not to be calculated when area sart was lower than one
- **accounts**: issue causing the user information on firebase not to update when users changed their email address
- **coastal_wetland**: remove nullability from all area-related fields in coastal wetland and leave default as zero
- **annual_cropland**: issue causing the flu not to be fetched correctly
- **activity**: add coastal wetland area in total area count for activity land modules
- **defaults**: ensure set aside biomass start is populated correctly
- **energy**: issue causing results calculations to crash in languages other than english
- **activity_builder**: issue causing duplication of modules when editing an activity
- **public_project**: add missing capitalization years to PublicProjectSerializer
- **calculators**: set default values for absent disturbances to None instead of empty list

## v1.18.1 (2025-10-09)

### Feat

- **minitool**: add multi-module emissions scenarios

### Fix

- **settlement**: apply conversion of km to meters for road length instead of meters to km for road width
- **activity_builder**: issue causing some combinations of LUC and organic soil to crash
- **roads**: conversion issue in roads area causing unexpected results
- **ActivityBuilder**: correct handling of Organic Soil and Land Use Change logic
- **project_attachments**: issue with cloud bucket name causing error when trying to delete an attachment in non-review environments

## v1.17.22 (2025-10-03)

### Feat

- **minitool**: add scenario categories
- **minitool**: add metadata to emissions scenario

### Fix

- **project_invitations**: issue causing invitations not to be accepted for languages other than english
- **reports**: typo in forest management report causing crash
- **reports**: issue causing flooded rice minor season emissions not to be considered and added to total activity emissions
- **reports**: remaining fillvalue typos causing crash

## v1.17.23 (2025-10-03)

### Feat

- add units to input types model

### Fix

- **bloc**: static files template pathing

## 1.17.22 (2025-10-01)

### Fix

- **calculators**: issue causing some forest management instances to accidentally fetch unneded biomass values, triggering a missing data error

## 1.17.21 (2025-10-01)

### Fix

- **reports**: issue causing any report containing the livestock module to fail
- **reports**: issue caused by old reference to comment thread attributes for small and large fishery

## 1.17.20 (2025-10-01)

### Fix

- **calculators**: update module type check from SingleBiomassModule to BiomassModule in LandModuleCalculator

## 1.17.19 (2025-09-29)

### Fix

- **middleware**: allow public endpoints to skip authentication

## 1.17.18 (2025-09-29)

### Fix

- **activity**: show non-b-intact activities in list endpoint for public activities endpoint
- **activity**: return activities that are not b-intact by default

## 1.17.17 (2025-09-25)

### Feat

- **public**: add module types endpoint to public urls

### Fix

- **calculators**: add missing start results to ForestManagementCalculator result tuple

## 1.17.16 (2025-09-25)

### Fix

- **forest_management**: issue caused by wrong references for flu,fi,fmg start

## 1.17.15 (2025-09-25)

### Fix

- **activity**: issue calculating capitalization years when only last_year_of_accounting was specified

## 1.17.14 (2025-09-24)

### Fix

- **calculators**: send bgb_t_c_ha as agb_ref to mathematical model instead of agb_t_c_ha
- **defaults**: send GrasslandBiomass bgb_t_c_ha as default agb t2 value instead of agb_t_c_ha

## 1.17.13 (2025-09-24)

### Fix

- **defaults**: add agb rate to default return payload for perennial cropland

## 1.19.0 (2026-01-14)

### Feat

- add revised forest management agb, agb growth and root-to-shoot data
- **api**: add inventory breakdown to module results endpoint
- **organic_soil**: disable soc som of land modules when organic soil module is present in the activity
- **reports**: display activity T2 overrides in Excel metadata

### Fix

- **calculators**: old flu_wo reference to mathematical model causing wrong results
- **math_model**: wrong activity type for refrigerant inventory causing crash
- **not_cultivated_land**: correct indentation for appending SOM emissions to results
- **inventory**: wrong inventory class initialization throwing exception
- **inventory**: correct activity type in inventory initialization for ice emissions
- **inventory**: wrong inventory class initialization causing exception
- **inventory**: updated landuse models with if calculate_soc_som
- **inventory**: remove scenario-based logic in results and only aggregate by single start scenario
- **inventory**: move soil and som inventory calculations outside calculate_soc_som check
- **inventory**: update inventory aggregation to include additional math modules
- **inventory**: various math model issues causing crashes
- **math_model**: Updated import from ghg_inventory_class in inputs
- **math_model**: revert some absolute imports to relative imports
- **perennial_cropland**: account for agb_t2_start and bgb_t2_start only when it is replacing a reference value, not computed or zero
- **activity_builder**: issue causing removal of organic soil module to reset inputs of associated land modules
- **calculators**: revert disturbance_percentage_fire to empty list fallback

## 1.18.4a0 (2025-12-08)

## v1.18.4 (2025-12-08)

### Fix

- **activity_builder**: wrong type in issubclass check
- **scripts**: exclude finalized project from cache reset in invalidate_results_cache

## 1.18.4 (2025-12-08)

### Feat

- **project**: make climate, moisture, and soil_type optional

### Fix

- **forest management**: add start year to agb matrix logging update
- **forest calculator**: update list absence to Nones instead of []

## 1.18.3a0 (2025-12-04)

### Fix

- **calculators**: add a workaround that sanitizes any modules with missing land_use_change references due to bug in ActivityBuilderSerializer

## 1.18.3 (2025-11-21)

### Feat

- **ci**: force results cache invalidation on new release
- **project**: add ability to manually lock and unlock projects

### Fix

- **ipcc**: logical issue causing the date for forest management AGB and AGBGrowth to be wrong for most entries
- **forest_management**: replace None with empty arrays to account for mathematical model requirements
- **project_copy**: issue caused by stale organic soil ids causing crash when copying projects with organic soil modules
- **math_model**: issue causing disturbances to be calculated even when only logging was present
- **math_model**: issue causing coastal wetland rewetting area not to be calulated correctly
- **activity**: issue causing double counting of hectares when computing total land modules area
- **activity**: issue causing double counting of hectares when computing total land modules area
- **project_copy**: issue causing the admin membership to be duplicated when duplicating a project
- **activity_builder**: add back activity creation logic
- **activity_builder**: prevent luc module type from always being added
- **activity_builder**: rewrite edit logic
- **activity_builder**: rewrite activity edit logic for better clarity and performance
- **forest_management**: issue causing bgb max start to always be zero
- **activity**: issue causing only preexisting module types to be involuntarily cleared from activity module types when editing an activity
- **activity**: issue causing duplicate modules when editing an activity without adding or removing any module
- **organic_soil**: issue causing peat extraction not to be calculated when area sart was lower than one
- **accounts**: issue causing the user information on firebase not to update when users changed their email address
- **coastal_wetland**: remove nullability from all area-related fields in coastal wetland and leave default as zero

## 1.18.2 (2025-10-23)

### Feat

- **minitool**: add api endpoint to get results for all scenarios
- **minitool**: add mitigation scenarios
- **admin**: add ability to upload files to Hand In Hand Assessments from admin panel

### Fix

- **annual_cropland**: issue causing the flu not to be fetched correctly
- **activity**: add coastal wetland area in total area count for activity land modules
- **defaults**: ensure set aside biomass start is populated correctly
- **energy**: issue causing results calculations to crash in languages other than english
- **activity_builder**: issue causing duplication of modules when editing an activity
- **public_project**: add missing capitalization years to PublicProjectSerializer
- **calculators**: set default values for absent disturbances to None instead of empty list

## 1.18.1 (2025-10-09)

- **settlement**: apply conversion of km to meters for road length instead of meters to km for road width

## 1.18.0 (2025-10-09)

### Feat

- **minitool**: add multi-module emissions scenarios
- **minitool**: add scenario categories
- **minitool**: add metadata to emissions scenario
- add units to input types model

### Fix

- **settlement**: apply conversion of km to meters for road length instead of meters to km for road width
- **activity_builder**: issue causing some combinations of LUC and organic soil to crash
- **roads**: conversion issue in roads area causing unexpected results
- **ActivityBuilder**: correct handling of Organic Soil and Land Use Change logic
- **project_attachments**: issue with cloud bucket name causing error when trying to delete an attachment in non-review environments
- **project_invitations**: issue causing invitations not to be accepted for languages other than english
- **reports**: typo in forest management report causing crash
- **reports**: issue causing flooded rice minor season emissions not to be considered and added to total activity emissions
- **reports**: remaining fillvalue typos causing crash
- **bloc**: static files template pathing

## 1.17.22 (2025-10-01)

### Fix

- **calculators**: issue causing some forest management instances to accidentally fetch unneded biomass values, triggering a missing data error

## 1.17.21 (2025-10-01)

### Fix

- **reports**: issue causing any report containing the livestock module to fail
- **reports**: issue caused by old reference to comment thread attributes for small and large fishery

## 1.17.20 (2025-10-01)

### Fix

- **calculators**: update module type check from SingleBiomassModule to BiomassModule in LandModuleCalculator

## 1.17.19 (2025-09-29)

### Fix

- **middleware**: allow public endpoints to skip authentication

## 1.17.18 (2025-09-29)

### Fix

- **activity**: show non-b-intact activities in list endpoint for public activities endpoint
- **activity**: return activities that are not b-intact by default

## 1.17.17 (2025-09-25)

### Feat

- **public**: add module types endpoint to public urls

### Fix

- **calculators**: add missing start results to ForestManagementCalculator result tuple

## 1.17.16 (2025-09-25)

### Fix

- **forest_management**: issue caused by wrong references for flu,fi,fmg start

## 1.17.15 (2025-09-25)

### Fix

- **activity**: issue calculating capitalization years when only last_year_of_accounting was specified

## 1.17.14 (2025-09-24)

### Fix

- **calculators**: send bgb_t_c_ha as agb_ref to mathematical model instead of agb_t_c_ha
- **defaults**: send GrasslandBiomass bgb_t_c_ha as default agb t2 value instead of agb_t_c_ha

## 1.17.13 (2025-09-24)

### Fix

- **defaults**: add agb rate to default return payload for perennial cropland

## 1.18.0 (2025-10-09)

### Feat

- **minitool**: add multi-module emissions scenarios
- **minitool**: add scenario categories
- **minitool**: add metadata to emissions scenario
- add units to input types model

### Fix

- **activity_builder**: issue causing some combinations of LUC and organic soil to crash
- **roads**: conversion issue in roads area causing unexpected results
- **ActivityBuilder**: correct handling of Organic Soil and Land Use Change logic
- **project_attachments**: issue with cloud bucket name causing error when trying to delete an attachment in non-review environments
- **project_invitations**: issue causing invitations not to be accepted for languages other than english
- **reports**: typo in forest management report causing crash
- **reports**: issue causing flooded rice minor season emissions not to be considered and added to total activity emissions
- **reports**: remaining fillvalue typos causing crash
- **bloc**: static files template pathing

## 1.17.22 (2025-10-01)

### Fix

- **calculators**: issue causing some forest management instances to accidentally fetch unneded biomass values, triggering a missing data error

## 1.17.21 (2025-10-01)

### Fix

- **reports**: issue causing any report containing the livestock module to fail
- **reports**: issue caused by old reference to comment thread attributes for small and large fishery

## 1.17.20 (2025-10-01)

### Fix

- **calculators**: update module type check from SingleBiomassModule to BiomassModule in LandModuleCalculator

## 1.17.19 (2025-09-29)

### Fix

- **middleware**: allow public endpoints to skip authentication

## 1.17.18 (2025-09-29)

### Fix

- **activity**: show non-b-intact activities in list endpoint for public activities endpoint
- **activity**: return activities that are not b-intact by default

## 1.17.17 (2025-09-25)

### Feat

- **public**: add module types endpoint to public urls

### Fix

- **calculators**: add missing start results to ForestManagementCalculator result tuple

## 1.17.16 (2025-09-25)

### Fix

- **forest_management**: issue caused by wrong references for flu,fi,fmg start

## 1.17.15 (2025-09-25)

### Fix

- **activity**: issue calculating capitalization years when only last_year_of_accounting was specified

## 1.17.14 (2025-09-24)

### Fix

- **calculators**: send bgb_t_c_ha as agb_ref to mathematical model instead of agb_t_c_ha
- **defaults**: send GrasslandBiomass bgb_t_c_ha as default agb t2 value instead of agb_t_c_ha

## 1.17.13 (2025-09-24)

### Feat

- **minitool**: import recomputed dataset with hamming space algorithm
- **minitool**: add coastal wetland dataset

### Fix

- **defaults**: add agb rate to default return payload for perennial cropland

## 1.17.12 (2025-09-23)

### Fix

- **activity**: missing request context causing issue during activity creation

## 1.17.11 (2025-09-22)

### Feat

- **activity**: add is_b_intact queryparam to activity list endpoint

## 1.17.10 (2025-09-22)

### Feat

- **activity**: add ability to tag activity as b-intact
- **minitool**: add perennial cropland permutations dataset

## 1.17.9 (2025-09-18)

### Feat

- **minitool**: implement caching for module types retrieval
- **minitool**: add large fishery and annual cropland datasets

### Fix

- **activity_builder**: rewrite activity edit logic to avoid issues with orphaned modules
- inconsistencies in naming of some threads compared to their reference inputs
- correct references to selected electricity ef in value chain and irrigation modules, in accordance with new energy ef logic
- **minitool**: add large fishery endpoint

## 1.17.8 (2025-09-17)

### Feat

- **perennial cropland**: add scenario-based initial biomass t2 value

### Fix

- add fallback fetch to default module values for initial and final biomass

## 1.17.7 (2025-09-17)

### Feat

- **minitool**: implement progress tracking for permutation processing with resume capability
- **project**: allow modifications to finalized projects only for publication status

### Fix

- **energy**: set electricity ef to zero for renewables and make it scenario-dependant

## 1.17.6 (2025-09-15)

### Fix

- **minitool**: reimport small fishery dataset with fixes
- **project_invitations**: issue potentially causing multiple memberships of the same type to be created
- **activity_builder**: issue causing unmodified module types not to receive the new area if changed in the builder

## 1.17.5 (2025-09-12)

## 1.17.4 (2025-09-12)

### Feat

- **minitool**: add grassland dataset to database

## 1.17.3 (2025-09-12)

### Feat

- **minitool**: add waterbody-related endpoints and sanitize db data
- **minitool**: update database

### Fix

- **minitool**: remove grassland factory yield

## 1.17.2 (2025-09-09)

### Fix

- **coastal_wetlands**: remove wrong multiplication from bgb default calculations in mathematical model

## 1.17.1 (2025-09-05)

### Fix

- **minitool**: remove additional password from computation endpoint

## 1.17.0 (2025-09-05)

### Feat

- add endpoint to run compute permutations from cloud

## 1.16.3 (2025-09-04)

### Feat

- **minitool**: add complete small fishery dataset

### Fix

- **forest management**: create_agb_matrix function fix (growth end of year)
- **perennial_cropland**: set tier2 values for start AGB and start BGB to None for all scenarios

## 1.16.2 (2025-08-27)

### Fix

- **ProjectInvitationViewSet**: add request context to ProjectInvitationWriteSerializer

## 1.16.1 (2025-08-27)

### Fix

- **minitool**: make module_type filter optional in compute endpoint

### Refactor

- **hih assessment**: enhance grouping logic to include all countries, ensuring assessments are correctly associated with their respective regions and countries

## 1.16.0 (2025-08-27)

### Feat

- **minitool**: add compute action to EmissionScenarioViewSet for custom scenario calculations with validation and filtering
- **minitool**: introduce EmissionScenario model and related serializers, views, and admin registration; remove legacy models
- **minitool**: implement scenario computation script with comprehensive statistical analysis and documentation
- **minitool**: register ChangeRecord model in admin with display and filter options
- **minitool**: add forest management and fisheries logic and partial datasets
- **minitool**: add Small and Large Fishery data builders and processors with configuration support
- **minitool**: enhance error handling by extracting relevant traceback lines and improve progress bar display
- **minitool**: add LandUseChange data aggregation and processing script

### Fix

- **report**: add missing total_emissions assignments causing vc modules not to be included in the activity totals
- **report**: allow endpoint to only validate readines of filtered activities, if any
- **minitool**: filter regions without countries to prevent "Project has no country" errors
- **minitool**: support single fields without start/w/wo variations in field mapping system
- **factories**: standardize area attribute to 1 for various land use factories

### Perf

- **minitool**: optimize permutation computation with dynamic worker scaling and performance monitoring

## 1.15.16 (2025-08-21)

### Fix

- **oluc**: Correct fire emissions calculations
- **general_functions**: fix cumulative maturity evaluation

## 1.15.15 (2025-08-20)

### Feat

- **minitool**: update database file with new data
- **minitool**: add organic input types and biomass/fire periodicity attributes to perennial cropland data builder
- add database to git lfs
- **minitool**: add perennial cropland to computation scripts
- **minitool**: add perennial cropland to computation script

### Fix

- **grassland**: remove reference to old soc tables and adjust soc logic
- **minitool**: add perennial cropland to module type mapping and exclude 'module' from custom filter list
- **minitool**: update country filter to use api_models
- **minitool**: handle edge cases in quartile calculations
- **minitool**: include country as a filter
- change how quantiles are calculated
- **minitool**: remove useless land use types permutations from flooded rice computations
- update modules data
- delete unused file
- adjust changes json path
- set capitalization years and implementation years to 1 and 0
- specify different deploy configuration for minitool
- add lfs support in deployment yaml
- delete large files
- remove wrong db
- add minitool url to allowed hosts
- remove statement timeout option from database config
- remove large files

## 1.15.14 (2025-08-19)

### Feat

- **forest management**: add disturbance_percentage_fire to calculations and model
- **minitool**: disable thread safety for local database
- **minitool**: add endpoint returning available modules
- add module-based /filters endpoint returning the available filters for each module
- add module-level generalized aggregation
- add module-level data aggregation
- add impact analisys script
- add per-module aggregated results endpoint and rewrite aggregation scripts
- refactor aggregation logic
- add first draft of aggregated module practices statistics
- add script to generate intra-module statistics aggregated by practice
- increase maximum page size in minitool pagination
- add first implementation of minitool endpoint

### Fix

- **calculators**: add missing streamlined soc_t2 fallback references and add unit tests for validation
- **project membership**: unlock project when deleted member is the lock holder
- **minitool**: adjust module type string output in analyze_changes
- **minitool**: add middleware manually handling database connections to ensure proper closing
- merge migrations

## 1.15.13 (2025-08-14)

### Fix

- **grassland**: overwrite default soc with grassland-specific soc when needed

## 1.15.12 (2025-08-13)

### Fix

- **grassland**: add fi, flu, fmg override based on grassland management practices in calculator
- remove old reference to degraded land in favor of other land in FLU data

## 1.15.11 (2025-08-13)

### Fix

- **project copy**: remove double transaction management logic causing TransactionManagementError

## 1.15.10 (2025-08-12)

### Fix

- **activity builder**: add missing check for luc presence when editing activity

## 1.15.9 (2025-08-07)

### Fix

- **activity copy**: remove module saving from handle_threads to avoid integrity errors

## 1.15.8 (2025-08-06)

### Fix

- **activity builder**: move module deletion at the end so activity editing is not affected by delete cascade
- **copy**: rework logic so that organic soil is properly copied
- **fra**: align some countries with mismatching names in the dataset

## 1.15.7 (2025-08-05)

### Fix

- **copy**: handle submodule comment threads before saving

## 1.15.6 (2025-08-05)

### Fix

- **copy**: generalize logic handling copy of submodules
- remove test exception
- **activity builder**: set fields to default values if present when senitizing modules inputs
- **perennial cropland**: add missing growth flag for computed biomass values
- **forest management**: fetch the proper BGB Max values from mathematical model for defaults
- **copy**: add updated organic soil to LUC module to avoid primary key conflicts
- **report**: preventorganic soil peat to be considered when not present

## 1.15.5 (2025-08-04)

### Fix

- **defaults**: add max agb and max bgb values to forest management
- **input**: add macro input type other to user defined inputs
- **report**: remove balance stats for shadow price of carbon
- **perennial cropland**: wrong None allocation causing crash in maturity computation
- **organic soil**: set None ditches area and extraction height to zero to avoid NoneType errors in mathematical model
- make defaults endpoint accessible regardless of project lock

## 1.15.4 (2025-08-01)

### Feat

- **forest management**: add litter and deadwood max default initialization for non-afforestation scenarios with FRA data source
- **test**: add scaffolding for unit testing of land use changes
- **forest management**: add initial AGB values based on AGB Max for forest management calculations when FRA data source is selected

### Fix

- **test**: modify annual cropland unit test so that minor season data is correctly randomized
- **test**: randomize object selection in UnitTestAnnualCroplandFactory
- **annual cropland**: correct minor yield refrence value for start scenario in calculator
- **annuals**: set minor to Optional
- **livestock**: add logic to override systems arrays when complementary manure management is selected
- **livestock**: fix livestock inputs
- **luc**: add tier2 checks for soc in deforestation and other land use change calculators

### Refactor

- **test**: add support for module factories to build validated data in unit tests

## 1.15.3 (2025-07-31)

### Feat

- **test**: add agb and bgb t2 in forest management unit test
- **test**: add ability to calculate non-cached results
- **test**: add ability to override t2 fields to test with custom list
- **test**: add logic to methodically test the effect of t2 values on module results
- **Forest Management**: add agb_max_t2 defaults and corresponding tests
- add project-level notification opt in

### Fix

- **fisheries**: add FUI data to defaults
- raise error if fra carbon stock data is not found for project country
- **test**: filter out countries with no region in test project setup
- **mathematical model**: wrong falsy check for litter and deadwood t2 values in forest management
- add logic that sends default biomass in AGB/BGB modules where scenario is not used
- **Public Project Template**: unchecked language code reference causing AttributeError
- allow lock holders to unlock projects
- **Perennial**: update bgb_start evaluation logic and set bgb_start to nullable
- **Perennial Cropland**: attribute reference issue causing wrong values in maturity computation

### Refactor

- rewrite some tests to include results retry logic
- set bgb_start to None instead of bgb rate in perennial crop maturity computation

## 1.15.2 (2025-07-29)

### Feat

- cache hih assessment endpoint
- add hih assessments import script and data

### Fix

- **Project**: make unlock endpoint post instead of get
- **Defaults**: remove old references to energy and fuel calculators causing null values in value chain classes
- **Organic Soil**: Adjust peat area checks causing None Types to be wrongly evaluated
- **Organic Soil**: Add missing onsite ch4 peat extraction ef tier2 input for all scenarios
- **Input Entry**: Add specific tier2 checks for user defined inputs
- **Minor Season Annual Cropland**: Add additional validation checking for improper scenario inputs
- **Dynamic Filter**: Remove duplicate results from multiple search queries
- **Forest Management**: Solve a disturbance input issue causing a crash
- **Perennial**: Adjust logic for maturity computations for perennial remaining perennial

## 1.15.1 (2025-07-25)

### Feat

- Add recap endpoint to manually send recap email for a project
- Add notification email opt out for users

### Fix

- **Templated Report**: Make english the default language and only evaluate request LANGUAGE_CODE if present

## 1.15.0 (2025-07-24)

### Feat

- **testing**: add system maturity testing in perennial cropland unit test class
- **testing**: add method to get module details and add the ability to edit a module using PUT instead of PATCH
- added default None to Optionals and changed dataclasses to kw_only
- **perennial cropland**: add bgb as an input for the mathematical model
- **perennial**: split biomass into agb and bgb
- **forest management**: add tier2 value for max bgb
- **forest**: add bgb tier 2 values
- added versions changelog

### Fix

- Change commitizen version scheme
- typos in commitizen configuration toml
- Adjust growth dinamics for start-with and start-without scenarios
- Deepcopy reference AGB and BGB values in maturity computations to avoid in-memory value replacements
- **perennial_cropping**: fix biomass assignment
- **perennial cropland**: complete rewrite of maturity computation
- set Perennial agb and bgb to nullable
- added wildcard prefix in allowed hosts to accept load balancer internal hostnames
- **perennial cropland**: initialize biomass_start to 0 for complete renewal
- **grassland**: remove reference to single biomass values causing the wrong bioimass tier2 values to be evaluated

## 1.14.6 (2025-07-21)

### Feat

- add script to convert vc storage refrigerant ef from kg to tonnes

### Fix

- missing specification of request owner in activity copy endpoint
- **calculators**: align agb max label to the new one in the model

## 1.14.5 (2025-07-18)

### Feat

- add agb and bgb max tier 2 values in ForestManagement model

### Fix

- **calculators**: forcibly set disturbance arrays to zero when empty in ForestManagementCalculator
- **calculators**: forcibly set agb tier2 values to zero for afforestation
- wrong t2 emission factor references in EnergyEntryCalculator
- small fishery gear types script not counting unmotorized fishing

## 1.14.4 (2025-07-17)

### Feat

- add update_module_types_of_fuel_types function and FuelType_ModuleType.csv data

### Fix

- refactor migrations to avoid useless mass uuid assignment
- remove call to change_other_land_flu_data_to_1 in development mode

## 1.14.3 (2025-07-17)

### Feat

- add script to correct other land flu data
- add fishery type - small fishery gear type relations
- add fishery type m2m link in the small fishery gear type model
- **filtering**: add support for m2m fields in DynamicSearchAndFilterBackend
- add script to remove irrigation modules from wood peat and charcoal
- **public**: set uuid as project lookup field in public endpoint
- add hih assessment data structure and endpoint
- **reports**: add french templated report
- add better error message when trying to delete a project with multiple admins

### Fix

- logcal error preventing deletion of other people from project where user had admin rights
- remove public id from project model
- **reports**: spanish template not showing all activities
- **reports**: templated report not showing all activities
- **reports**: missing energy entry reference in energy and valuechain reports
- **reports**: offset module emissions in excel
- **copy**: activity reference for submodules when handling comment threads
- **reports**: offset activity emissions in excel

## 1.14.2 (2025-07-09)

### Feat

- **login**: better error handling and messages when login fails

### Fix

- **copy**: solve issue with comment threads and prevent copying comments without the right permissions
- prevent failed project copy from persisting the broken project
- **calculators**: set irrigation phase ch4 and n2o efs to zero when electricity or renewable
- **defaults**: add missing values to irrigation phase defaults
- **reports**: Update ExcelFileManager to disable file saving on disk

## 1.14.1 (2025-05-30)

## 1.14 (2025-05-29)

### Feat

- add value chain modules reports

### Fix

- add missing electricity emissions row population in smal and large fishery reports
- add missing units for modules remaining modules in templated report
- issue with comment threads causing crash during project and activity copy

## 1.13.15 (2025-05-19)

### Fix

- add map data in changes to exclude from get_changes

## 1.13.14 (2025-05-19)

### Fix

- typo causing aquaculture and fishery data not to show up in template units table
- correctly skip module results with errors instead of trying to access them in the templated report
- delete unused files

## 1.13.13 (2025-05-19)

### Feat

- show entity names instead of ids in changelog

### Fix

- **math**: logical error in forest management logging or recurrence checks

## 1.13.12 (2025-05-19)

### Fix

- minor queryset bugs in project and activity

## 1.13.11 (2025-05-17)

### Feat

- add id to membership serializer

### Fix

- unchecked None threads causing crash when sending recaps for entities with uninitialized threads
- public activities list endpoint filters

## 1.13.10 (2025-05-14)

### Fix

- use prefiltered queryset to avoid showing non-public entities

## 1.13.9 (2025-05-14)

### Feat

- add serialized status object in public module serializer

## 1.13.8 (2025-05-14)

### Feat

- add module type to generic public module serializer

## 1.13.7 (2025-05-14)

### Fix

- make soil type viewset public
- remove permission check from public defaults endpoint

## 1.13.6 (2025-05-14)

### Fix

- cut action type definition from generic public serializer call

## 1.13.5 (2025-05-14)

### Fix

- module retrieval in public module viewset

## 1.13.4 (2025-05-14)

### Fix

- account for superuser edits in recap email
- add accidentally removed router endpoints

## 1.13.3 (2025-05-13)

### Feat

- add activities endpoint to public project viewset
- add excel and templated reports to public project viewset
- add scenario based complete renewal in perennial cropland

### Fix

- make all public project fields visible and exclude specific ones
- typo in organic soil drainage t2 references
- threads property getter in module abstract model
- add missing public module endpoints

## 1.13.2 (2025-05-12)

### Feat

- add missing public endpoints
- add more information ton public activity endpoint
- add all public modules endpoints

## 1.13.1 (2025-05-12)

### Feat

- finish setting informational endpoints as public

## 1.13 (2025-05-12)

### Feat

- add modules action to public activity viewset
- make all "-types" endpoints public

## 1.12.3 (2025-05-12)

### Fix

- remove skipping results calculation for archived projects

## 1.12.2a (2025-05-09)

### Feat

- add history of comments to changes recap email
- automatically un-finalize copied projects
- send changes recap email to project admins on project is unlocked

### Fix

- missing inclusion of renewables in irrigation phase calculator
- organic soil drainage t2 field names
- project lock not being updated during activity, modules and submodules writes

## 1.12.2 (2025-05-05)

### Feat

- add parametric storage bucket name in project attachment viewset

### Fix

- prevent empty threads from crashing project copy

## 1.12.1 (2025-04-30)

### Fix

- migrations and deploy script
- some typos in russian translation files

## 1.12 (2025-04-30)

### Feat

- add revised russian translations
- add new french translations
- add energy entry defaults

### Fix

- versioning
- energy default testing suite
- missing populate_metadata method in flooded rice report class
- type error caused by activity duration t2 being None
- missing delete method in activity delete
- typo in retrieval of project from context in project file upload serializer
- add script to fill out missing emission factor sources from irrigation phases with new energy component

## 1.11.2 (2025-04-25)

### Feat

- add datasource endpoint

### Fix

- remove cache changes from module history changelog and skip records with user None

## 1.11.1 (2025-04-25)

### Feat

- activate review github action?

## 1.11 (2025-04-25)

### Feat

- add fao logo in spanish
- add filled french translations
- add more granular information on activity impact in templated scenario
- pass max bgb to mathematical model in forest management calculator
- implement BGBMax as pseudo-tier2 value in forest management mathematical model
- set missing FRA reference values to zero in forest management calculator
- use of data from FRA when selected as a datasource in forest management calculator
- add short name to datasource model
- add data source attribute to all modules and submodules
- add FRA carbon stock data for year 2020
- add multilanguage support for templated reports
- sort activities and modules relative to carbon balance sign in templated report

### Fix

- cut all translation wildcards from api models
- add request language as default templated report language
- properly parse class names with acronyms in url name generator
- change uniqueness rules of datasource model
- issue with country attribute in base calculator causing country to be None
- apply latest corrections to spanish templated report
- prevent copying activities in a finalized or archived project and add missing comment threads copying logic
- prevent file uploads to finalized projects
- block deletion of activities in finalized projects

## 1.10.1 (2025-04-17)

### Fix

- translation script in bitbucket pipeline

## 1.10 (2025-04-17)

### Feat

- add russian language support
- add packaging material types translations
- add text placeholder for activities with no hectares, catch or heads
- add generic model admin adding export to csv and dynamic search
- add search bar and csv export for CustomUserAdmin

### Fix

- replace TillageType with TillageManagementType in translations
- skip removed entries and allow for ipcc models to be included
- minitool region reference in csv

## 1.9.5 (2025-04-11)

### Feat

- integrate energy emission factor in irrigation phase calculator

### Fix

- cut useless and problematic validation of activity in activity builder
- country_t2 not overriding project country in energy and vc calculations and thus in defaults

## 1.9.4 (2025-04-10)

### Fix

- add pagination queryparams to ignored keys in project dynamic filtering

## 1.9.3c (2025-04-09)

### Fix

- add setuptools and wheel update in pipeline

## 1.9.3b (2025-04-09)

### Feat

- change pip install command to prefer binary and use legacy resolver in pipeline configuration

## 1.9.3a (2025-04-09)

### Fix

- add pip upgrade in pipeline steps

## 1.9.3 (2025-04-09)

### Feat

- allow admins to send invitations and create memberships for finalized projects
- add is_finalized to project summary serializer
- add dynamic filters to project viewset
- prevent project archiving if there are multiple admins

### Fix

- deduplicate projects by only allowing unique ids when filtering user memberships
- add missing validation of existing activity in activity builder
- check that new last year of accounting for the project is not lower than the duretion of its activities

## 1.9.2 (2025-04-08)

### Fix

- add id field in project tags action response