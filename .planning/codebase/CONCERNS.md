# Codebase Concerns

**Analysis Date:** 2026-07-08

## Tech Debt

**Oversized core files (god objects):**
- Issue: Calculator, model, and serializer files have grown too large to maintain safely
- Files:
  - `djangoexact/api/calculators.py` (8,270 lines)
  - `djangoexact/api/serializers.py` (4,091 lines)
  - `djangoexact/api/models.py` (3,396 lines)
  - `djangoexact/api/views.py` (3,081 lines)
  - `djangoexact/api/minitool.py` (3,016 lines)
- Impact: Impossible to debug or review. Changes ripple across unrelated code. Increased risk of regression bugs.
- Fix approach: Break into topic-specific modules. Split calculators by domain (land modules, livestock, aquaculture, energy, value chains). Split models into concern-based files. Split views into multiple viewsets.

**Unresolved TODOs and FIXMEs:**
- Issue: 50+ TODO comments scattered across codebase indicating incomplete features or deferred refactors
- Files:
  - `djangoexact/api/calculators.py` (15+ TODOs)
  - `djangoexact/api/defaults.py` (6+ TODOs)
  - `djangoexact/api/models.py` (8+ TODOs)
  - `djangoexact/api/serializers.py` (3 TODOs)
  - `djangoexact/math_model/no_time_dependency_final/inputs.py` (2 TODOs)
  - `djangoexact/math_model/no_time_dependency_final/annuals.py` (1 TODO)
- Impact: Deferred work accumulates. No tracking of which are critical vs. cosmetic.
- Fix approach: Migrate all TODOs to issue tracker. Categorize by priority and epic. Create separate cleanup sprint.

**Verbose and repetitive defaults implementation:**
- Issue: `api/defaults.py` line 33 notes its own implementation is "too verbose" and should be refactored
- Files: `djangoexact/api/defaults.py` (1,764 lines)
- Impact: Hard to reason about default value flow. Easy to miss edge cases. Maintenance burden.
- Fix approach: Extract patterns into reusable base classes. Use declarative approach instead of conditional chains.

## Known Bugs

**Missing tier-2 IPCC data fallback:**
- Symptoms: Calculators expect tier-2 values for specific categories (cultivation days for flooded rice, electricity for aquaculture, peat volume conversions) but may receive None or empty lists
- Files:
  - `djangoexact/api/serializers.py` line 2086 (cultivation_days TODO)
  - `djangoexact/api/calculators.py` line 3624 (ELECTRICITY_USED_DEFAULT hardcoded to 0)
  - `djangoexact/api/calculators.py` lines 6808, 6906 (peat conversion factor TODOs)
- Trigger: Editing flooded rice modules, aquaculture inputs, or peat extraction without complete tier-2 data
- Current mitigation: Hardcoded defaults (0 for electricity, 1 for conversion factors)
- Workaround: Manually check that tier-2 data is available before calculating

**Forestry module scenario confusion:**
- Symptoms: Forest start, agb, and bgb tier-2 values exist separately for start/_w/_wo scenarios but calculators sometimes reuse start values across scenarios
- Files:
  - `djangoexact/api/calculators.py` lines 7265, 7399 (agb_t2_start, forest_type==forest_type tautology, math_start reuse)
  - `djangoexact/api/calculators.py` lines 7476-7477 (same issues in 'without' scenario)
- Trigger: Afforestation and deforestation calculations with tier-2 overrides
- Current mitigation: Commented-out TODOs indicating known inconsistency
- Workaround: Ensure tier-2 values are set identically for all scenarios to avoid surprises

**Activity builder double-counting and duplication:**
- Symptoms: Changing activity modules without modifying any values can duplicate modules. Editing with LUC+organic soil combinations crashes.
- Files: `djangoexact/api/serializers.py` (activity builder serializer)
- Trigger: Activity edit operations with certain module combinations
- Current mitigation: Recent CHANGELOG entries show fixes (v1.18.3, v1.18.4 include activity_builder rewrites)
- Workaround: Avoid rapid consecutive edits. Verify module counts before/after save.

**Reference data PK drift (fixture instability):**
- Symptoms: If a row at PK N changes semantic meaning (e.g., pk=50 was "Plantation" becomes "Annual Cropland"), foreign keys silently break
- Files:
  - `djangoexact/api/fixtures_manifest.py`
  - `djangoexact/docs/guides/fixtures-guide.md` lines 37-49
- Current mitigation: `dump_reference_data` command refuses to overwrite if PK meaning changes, prints diff
- Workaround: Use `--force` flag only for legitimate renames (e.g., "Turkey" to "Türkiye"). Investigate any unexpected PK drift.
- Risk: Round-trip test (`api/tests/test_reference_bootstrap.py`) passes locally but would fail in production if fixtures are malformed.

## Security Considerations

**Deployment sed templating with secrets:**
- Risk: `.github/workflows/deploy.yaml` and `bitbucket-pipelines.yml` substitute environment variables into `app.yaml` and `settings.py` using `sed`. If secrets are accidentally echoed, they leak to CI logs.
- Files:
  - `.github/workflows/deploy.yaml` lines 48-89 (note: comments warn NOT to echo after substitution)
  - `bitbucket-pipelines.yml` lines 29-62
- Current mitigation: Comments explicitly state "do NOT echo app.yaml" and "do NOT echo settings.py" after substitution
- Recommendations:
  - Use dedicated secret injection tools (e.g., Sealed Secrets, External Secrets) instead of sed
  - Add CI lint rule to reject commits with secret variables in echo statements
  - Rotate SECRET_KEY and DB_PASSWORD if any accidentally commit to git

**Firebase authentication integration fragility:**
- Risk: Custom Firebase wrapper (`djangoexact/djangoexact/settings.py` line 8, pyrebase replaced in v1.19.2a2) is responsible for user auth. Errors in wrapper bypass token validation.
- Files:
  - `djangoexact/accounts/` (Firebase integration)
  - `djangoexact/api/permissions.py` (permission checks tied to Firebase UID)
- Impact: If Firebase credentials are compromised, attacker gains access to all user data. Custom wrapper adds surface area.
- Current mitigation: SimpleJWT + Firebase Admin SDK
- Recommendations:
  - Audit Firebase Admin SDK usage for proper credential isolation
  - Monitor Firebase console for unauthorized sign-in attempts
  - Implement rate-limiting on auth endpoints
  - Add webhook validation for Firebase events

**CORS allow-all in DEBUG mode:**
- Risk: `djangoexact/djangoexact/settings.py` line 58 sets `CORS_ORIGIN_ALLOW_ALL = DEBUG`. If DEBUG is accidentally True in production, all origins can access the API.
- Impact: Sensitive endpoints (project data, calculations) exposed to any website
- Current mitigation: DEBUG defaults to False; requires explicit env var
- Recommendations:
  - Use environment-based CORS lists only (no blanket allow-all)
  - Pre-deploy sanity check: verify DEBUG=False and CORS_ALLOWED_ORIGINS is non-empty

**Wildcard imports in tests:**
- Risk: `api/tests/` files use `from * import` making it hard to audit what's imported. Could mask symbol collisions or security-related names.
- Files:
  - `djangoexact/api/tests/perennial_to_rice_w_organic_soil.py` lines 3-6
  - `djangoexact/api/tests/modules/flooded_rice_w_season.py` lines 3-6
  - Multiple others
- Impact: Harder to review test code. Easier to accidentally use wrong function/class.
- Fix approach: Replace with explicit imports

**Unvalidated input in calculation jobs:**
- Risk: Admin scripts accept `from_value`, `to_value`, and `filters` parameters without type validation before hashing and storing
- Files: `djangoexact/admin_scripts/job_dispatcher.py` lines 54-68 (enqueue_or_join), lines 24-51 (compute_filters_hash)
- Current mitigation: JSON serialization catches most type errors
- Recommendations:
  - Add Pydantic validation for job parameters
  - Limit max size of filters dict
  - Log all job parameter hashes for audit trail

## Performance Bottlenecks

**No query optimization in activity/project retrieval:**
- Problem: Views fetch Project and Activity objects without prefetch_related() or select_related(), causing N+1 queries when iterating modules
- Files:
  - `djangoexact/api/views.py` line 627 (minimal prefetch)
  - `djangoexact/api/views.py` line 1940 (empty prefetch)
- Trigger: GET `/api/projects/{id}/activities/` with many modules, or list view with multiple projects
- Cause: Modern Django ORMs make N+1 queries invisible until load testing
- Improvement path:
  - Add select_related('project') to Activity querysets
  - Add prefetch_related('modules', 'modules__inputs') where needed
  - Use only() / defer() to limit field retrieval
  - Profile with Django Debug Toolbar

**Minitool permutation generation and concurrent execution:**
- Problem: `djangoexact/api/minitool.py` uses ProcessPoolExecutor to run parameter permutations in parallel, can saturate CPU/memory on large datasets
- Files: `djangoexact/api/minitool.py` (3,016 lines of complex permutation/scenario logic)
- Cause: No max worker limit or timeout per job
- Improvement path:
  - Cap worker pool size based on CPU count
  - Add per-job timeout to prevent runaway processes
  - Stream results incrementally instead of collecting in memory
  - Use async/await instead of process pools for I/O-bound work

**Calculators load IPCC tables every time:**
- Problem: Each calculator instantiation queries ipcc.FIData, ipcc.FMGData, ipcc.GlobalWarmingPotential without caching
- Files: `djangoexact/api/calculators.py` lines 263-269 (get_fi_data), 294-298 (get_fmg_data)
- Cause: Reference data is immutable but not cached
- Improvement path:
  - Load IPCC tables into module-level cache on app startup
  - Use functools.lru_cache for IPCC lookups
  - Pre-populate most-used tables (Countries, Regions, GWP) in memory

## Fragile Areas

**Complex three-scenario calculation pipeline:**
- Files: `djangoexact/api/calculators.py` (entire file)
- Why fragile: Every calculator must implement start / with / without scenarios. Each scenario has different validation rules and data requirements. Missing scenario handling causes silent wrong results.
- Recent bugs: CHANGELOG v1.18.4 lists "add workaround that sanitizes any modules with missing land_use_change references due to bug in ActivityBuilderSerializer"
- Safe modification:
  1. Add scenario validation before calculation (assert all required fields for given scenario exist)
  2. Write scenario-specific test for each new calculator (test_annual_cropland_start, test_annual_cropland_with, test_annual_cropland_without)
  3. Use dataclass or Enum to encode scenario rules explicitly instead of conditional logic
- Test coverage: Partial; many edge cases in CHANGELOG fixes suggest gaps

**Forest management biomass matrices:**
- Files: `djangoexact/api/calculators.py` lines 7174-7175 (TODOs about agb_start/agb_end reference values)
- Why fragile: Forest type matching, AGB growth data, and mangrove factor selection involve matrix lookups. Non-mangrove factor set to 0.47 but marked for removal.
- CHANGELOG notes multiple fixes (v1.19.0: "wrong activity type for refrigerant causing crash", v1.18.3: "logical issue causing date for forest management AGB to be wrong")
- Safe modification:
  1. Extract forest matrix logic into separate class hierarchy (ForestMatrixResolver)
  2. Add schema validation for matrix completeness (all required regions/types present)
  3. Write golden-file tests comparing old Excel outputs to new calculations
- Test coverage: Partial; script tests exist but not in main test suite

**Activity builder serializer (module add/remove logic):**
- Files: `djangoexact/api/serializers.py` (ActivityBuilderSerializer)
- Why fragile: Handles complex interactions: LUC requires organic soil on same activity, removing LUC must preserve land modules, duplicating modules is possible with certain edit patterns
- CHANGELOG v1.18.3 through v1.18.1 show repeated rewrites and fixes
- Safe modification:
  1. Extract into separate state machine class (ActivityModuleState)
  2. Pre/post-state validation (assert no duplicate modules, assert module counts consistent)
  3. Write comprehensive matrix tests (LUC + no organic soil, LUC + organic soil, no LUC + no organic soil, etc.)
- Test coverage: Gaps; many edge cases discovered post-release

**Custom user model with Firebase UID:**
- Files: `djangoexact/api/models.py` lines 71-95 (CustomUser)
- Why fragile: Unique Firebase UID can become null if auth provider changes. Email-based USERNAME_FIELD conflicts with some Django conventions.
- Safe modification:
  1. Add migrations test that ensures HistoricalRecords cascade delete works (auth requires audit trail)
  2. Never allow Firebase UID to be reassigned to different user (add unique_together constraint)
  3. Add soft-delete flag instead of full deletion to preserve FK references
- Test coverage: Simple; no auth integration tests in main suite

## Scaling Limits

**Reference data fixture loading time:**
- Current capacity: `load_reference_data --app=all` takes 30+ seconds (per fixtures-guide.md)
- Limit: No caching; every app startup loads from JSON
- Scaling path:
  - Cache fixtures in application memory on first load
  - Use database views or materialized tables for read-heavy reference queries
  - Consider read-only replica for reference data

**Calculation job dispatch (admin_scripts):**
- Current capacity: `enqueue_or_join` uses select_for_update(). Works well for 10-100 concurrent jobs.
- Limit: Heavy contention on ComputationJob table with 1000+ concurrent users
- Scaling path:
  - Use advisory locks (PostgreSQL) instead of row locks
  - Add Redis-based coalescing layer to avoid DB bottleneck
  - Separate ComputationJob queue into topic-specific tables

**Minitool permutation generation:**
- Current capacity: Generates full Cartesian product in memory; capped by available RAM
- Limit: Projects with 20+ land modules x 5+ scenarios x large parameter ranges will OOM
- Scaling path:
  - Stream permutations lazily (generator-based)
  - Use disk-based temp tables for large intermediate results
  - Implement incremental/checkpoint-based scenario generation

## Dependencies at Risk

**Custom Firebase wrapper (v1.19.2a2 replaced pyrebase):**
- Risk: Custom wrapper has limited external review. Errors in token handling could bypass auth.
- Impact: If wrapper has bugs, all user sessions at risk
- Migration plan: Use official Firebase Admin SDK directly (already in requirements.txt). Deprecate custom wrapper.

**Outdated or pinned versions:**
- Issue: Some packages have known vulnerabilities or limited maintenance
  - `django-archive==0.2.0` (minimal package, no recent updates)
  - `pydotplus==2.0.2` (no updates since 2014, use `graphviz` instead)
  - `itypes==1.2.0` (unused by DRF)
- Impact: Security updates may lag; dependency tree inflated
- Recommendations:
  - Run `pip-audit -r djangoexact/requirements.txt` regularly
  - Remove unused packages (itypes, pydotplus)
  - Consider upgrading to latest Django LTS (5.2 is current; 4.1 EOL Dec 2024)

## Missing Critical Features

**No automated test execution in CI/CD:**
- Problem: Neither `.github/workflows/deploy.yaml` nor `bitbucket-pipelines.yml` run pytest before deployment
- Blocks: Cannot catch regressions automatically. All test coverage is local/PR gate only.
- Files:
  - `.github/workflows/deploy.yaml` (no pytest step)
  - `bitbucket-pipelines.yml` line 5 (name: "test App" but only echoes)
- Impact: Broken code can ship to production. Tests are advisory only.
- Priority: HIGH
- Fix approach:
  1. Add pytest step to GitHub Actions workflow before deploy
  2. Add bandit (security scan) and pip-audit (dependency audit) to same step
  3. Block deployment if tests or audits fail
  4. Configure test matrix for multiple Python versions if needed

**No database routing implementation (scaffolding only):**
- Problem: `api/db_router.py` and `ipcc/db_router.py` both hardcode `db_name = "default"`. Written as scaffolding for future split, never completed.
- Files:
  - `djangoexact/api/db_router.py` (identical to ipcc version)
  - `djangoexact/ipcc/db_router.py`
  - `djangoexact/djangoexact/settings.py` line 177 (router configuration)
- Impact: Future split of reference data to separate database will require significant refactor
- Priority: MEDIUM (nice-to-have for multi-tenancy/scaling, not currently blocking)
- Fix approach:
  1. Implement proper read/write routing to separate databases if needed
  2. Or remove routers and simplify settings if single-DB model is committed

**No scenario-based input validation before calculation:**
- Problem: Calculators accept modules with missing required fields and fail at math layer (deep stack trace)
- Files: All calculator classes in `djangoexact/api/calculators.py`
- Impact: Errors discovered too late, making debugging hard
- Priority: MEDIUM
- Fix approach:
  1. Add pre-flight validation in BaseCalculator.calculate()
  2. Raise early ValidationError if required fields for scenario are missing
  3. Include field name and expected type in error message

## Test Coverage Gaps

**Untested area: Flooded rice minor seasons with tier-2 overrides:**
- What's not tested: Interaction between MinorSeasonFloodedRice.water_management_t2, parent FloodedRice tier-2 values, and scenario switching
- Files:
  - `djangoexact/api/calculators.py` line 1954 (TODO: "This can also be called by Minor Seasons")
  - `djangoexact/api/models.py` (MinorSeasonFloodedRice model)
  - `djangoexact/api/tests/reports/test_flooded_rice_seasons.py` (partial coverage only)
- Risk: Season-based calculations could silently ignore tier-2 overrides
- Priority: MEDIUM

**Untested area: LUC permutations with rare combinations:**
- What's not tested: LUC transitions involving OrganicSoil, Settlement, or rare land-use combinations
- Files:
  - `djangoexact/admin_scripts/luc_permutations.py`
  - `djangoexact/admin_scripts/tests/test_luc_permutations.py` (test exists but coverage unknown)
- Risk: Edge-case LUC calculations silently produce wrong results
- Priority: MEDIUM

**Untested area: Value chain calculations with energy and refrigerants:**
- What's not tested: ValueChain modules (Storage, Processing, Transport, Packaging) with Refrigerant types and energy entries
- Files:
  - `djangoexact/api/calculators.py` line 8055 (TODO: "This is basically only the Energy module")
  - `djangoexact/api/models.py` (RefrigerantType, ValueChainSubmodule)
- Risk: Refrigerant GWP conversion or energy routing could fail silently
- Priority: HIGH (value chains are critical for lifecycle assessments)

**Untested area: Project copy with nested organic soil modules:**
- What's not tested: Duplicating a project with organic soil modules attached to multiple activities
- Files:
  - `djangoexact/api/views.py` (project copy view)
  - CHANGELOG v1.18.3: "issue caused by stale organic soil ids causing crash when copying projects"
- Risk: Copy operation crashes or creates orphaned modules
- Priority: MEDIUM (but recent fix suggests stability improving)

**Untested area: Firebase auth synchronization:**
- What's not tested: Firebase UID mismatch, email change triggers, concurrent auth events
- Files:
  - `djangoexact/accounts/` (Firebase integration)
  - `djangoexact/api/tests/unit/test_sync_firebase_emails.py` (test exists but integration coverage unknown)
- Risk: User auth can diverge between Firebase and Django DB
- Priority: HIGH (affects all users)

---

*Concerns audit: 2026-07-08*
