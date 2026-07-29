<!-- refreshed: 2026-07-08 -->
# Architecture

**Analysis Date:** 2026-07-08

## System Overview

EX-ACT is a Django REST API for calculating greenhouse gas emissions from agricultural and land-use activities. It implements a four-layer architecture separating pure mathematics from framework integration.

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        REST API Layer (DRF)                          │
│  Views, Serializers, Routers, Authentication (Firebase)             │
│  `djangoexact/api/views.py`, `djangoexact/api/serializers.py`       │
├─────────────────────────────────────────────────────────────────────┤
│  HTTP endpoints: /api/projects, /api/activities, /api/[modules]     │
│  Nested routers: /api/projects/{id}/[sub-resources]                 │
│  Result routes: ChangeRecord, ChangeHistory                         │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│              Adapter Layer (Calculators & Services)                   │
│  `djangoexact/api/calculators.py` - 60+ calculator classes           │
│  `djangoexact/api/services/` - specialized compute services          │
│                                                                       │
│  Responsibilities:                                                   │
│  - Fetch data from Django models                                     │
│  - Resolve IPCC defaults via ipcc app                                │
│  - Prepare inputs for math layer                                     │
│  - Transform math results to data classes                            │
│  - Handle three scenarios: start, with, without                      │
│                                                                       │
│  Key classes: CalculatorFactory, BaseCalculator,                     │
│  LandModuleCalculator, [Specific]Calculator variants                 │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│           Pure Math Layer (Framework-Agnostic)                        │
│  `djangoexact/math_model/no_time_dependency_final/`                  │
│                                                                       │
│  IPCC emission factor calculations per land/activity type:           │
│  - annuals.py - Annual cropland emissions                            │
│  - flooded_rice.py - Flooded rice cultivation                        │
│  - livestock.py - Livestock and manure management                    │
│  - forest_management.py - Forest carbon sequestration                │
│  - coastal_wetlands.py - Wetland emissions                           │
│  - value_chains.py - Post-harvest losses                             │
│  - fisheries_and_aquaculture.py - Aquatic production                 │
│  - grassland_management.py - Grassland management                    │
│  - inputs.py, inlands.py, defo.py, oluc.py, waterbodies.py          │
│                                                                       │
│  No Django imports. Returns: MathResult (with/without tuples)        │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│               Reference Data Layer (IPCC Defaults)                    │
│  `djangoexact/ipcc/` app - Immutable reference tables                │
│  `djangoexact/api/models.py` - Project data models                   │
│  Database: PostgreSQL (production) or local SQLite                   │
│                                                                       │
│  IPCC data loaded from JSON fixtures (api/fixtures/, ipcc/fixtures/) │
│  via `load_reference_data`, dumped via `dump_reference_data`         │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Project | Container for activities and metadata | `djangoexact/api/models.py:589` |
| Activity | Aggregates modules (land use, inputs, energy, etc.) | `djangoexact/api/models.py:930` |
| Module | Individual input for emission calculation | `djangoexact/api/models.py:1351` |
| LandModule | Land-use-specific module with scenarios | `djangoexact/api/models.py:1726` |
| Calculator | Adapts Django model to math function inputs | `djangoexact/api/calculators.py:519+` |
| CalculatorFactory | Resolves model type to calculator class | `djangoexact/api/calculators.py:449` |
| DRF ViewSet | HTTP endpoint logic | `djangoexact/api/views.py:412+` |
| Serializer | Model <-> JSON transformation | `djangoexact/api/serializers.py` |
| ReportGenerator | WeasyPrint PDF output | `djangoexact/api/reports/base.py` |
| IPCCTable | Reference data (factors, coefficients) | `djangoexact/ipcc/models.py` |

## Pattern Overview

**Overall:** Layered adapter pattern with inversion of dependencies. Business logic (math layer) has zero dependencies on frameworks. API layer depends on adapters, which depend on both models and math layer.

**Key Characteristics:**
- Clean separation: math layer is testable in isolation
- Calculator factory pattern for extensibility
- Three-scenario support (start/with/without) per activity
- Nested routing for project hierarchies
- Firebase authentication with SimpleJWT tokens
- Auditlog and change tracking on all models
- i18n support (en, es, fr, ru)

## Layers

**Layer 1: REST API (DRF)**
- Purpose: Expose project, activity, module data via HTTP; handle auth and rate limiting
- Location: `djangoexact/api/views.py`, `djangoexact/api/serializers.py`, `djangoexact/api/urls.py`
- Contains: ViewSets (ProjectViewSet, ActivityViewSet, generic_module_viewset), serializers, nested routers
- Depends on: Django models, DRF, calculators (for defaults/results)
- Used by: Frontend (WebApp), mobile clients, external integrations

**Layer 2: Adapters & Services**
- Purpose: Bridge Django models to pure-math layer; handle defaults resolution; coordinate compute jobs
- Location: `djangoexact/api/calculators.py`, `djangoexact/api/services/`, `djangoexact/api/defaults.py`
- Contains: BaseCalculator, 60+ specific calculators (one per module type), CalculatorFactory, compute services for LUC and minitool
- Depends on: API models, IPCC models, math layer
- Used by: API views, reports module, background jobs

**Layer 3: Pure Math**
- Purpose: IPCC GHG calculation logic; no framework coupling
- Location: `djangoexact/math_model/no_time_dependency_final/`
- Contains: Category-specific modules (annuals.py, livestock.py, etc.), utility functions, Result and Inventory dataclasses
- Depends on: Python stdlib, numpy (numerical operations)
- Used by: Adapters/calculators only

**Layer 4: Reference Data**
- Purpose: Immutable IPCC coefficients, emission factors, defaults per region/climate/etc.
- Location: `djangoexact/ipcc/models.py`, `djangoexact/ipcc/fixtures/`, `djangoexact/api/fixtures/`
- Contains: IPCCTable, GlobalWarmingPotential, regional/climate-specific factors
- Depends on: Django ORM
- Used by: Calculators (via defaults.py), reports

**Supporting Layer: Accounts & Auth**
- Purpose: User management, Firebase token validation
- Location: `djangoexact/accounts/firebase.py`, `djangoexact/accounts/views.py`
- Auth flow: Firebase Client -> API /accounts/verify-token -> CustomUser (email-based, no username)

**Supporting Layer: Reports & PDF**
- Purpose: Generate WeasyPrint PDFs from calculated results
- Location: `djangoexact/api/reports/base.py`, `djangoexact/api/reports/renderer.py`
- Registry-based module support: each module type has extract/render methods

## Data Flow

### Primary Request Path (Calculate Activity Emissions)

1. Client POST to `/api/projects/{project_id}/activities/{activity_id}/results/` with scenario filter
   - Entry: `ActivityViewSet.results()` action (`djangoexact/api/views.py:2200+`)
2. DRF serializer validates, deserializes request payload
3. View fetches Activity and related Modules
4. For each Module:
   a. CalculatorFactory.get_calculator(module) resolves correct Calculator class
   b. Calculator.__init__(module) stores module reference
   c. Calculator.calculate() invokes compute:
      - Fetches inputs from module fields
      - Resolves IPCC defaults from ipcc tables
      - Invokes math_model function (e.g., MathAnnualCropland.calculate())
      - Returns tuple of (MathResult_with, MathResult_without)
5. Results aggregated by BreakdownTypes (TOTAL, ACTIVITY, GAS, ACTIVITY_GAS)
6. ChangeRecord created (audit trail)
7. DynamicResultSerializer formats output
8. Response: 200 OK with per-activity emissions (CO2e by year, by gas, by scenario)

**Code References:**
- Request entry: `djangoexact/api/views.py:2200` (ActivityViewSet.results)
- Calculator resolution: `djangoexact/api/calculators.py:463`
- Math invocation: `djangoexact/api/calculators.py:620+` (LandModuleCalculator.calculate)
- Result class: `djangoexact/math_model/no_time_dependency_final/ghg_emissions_classes.py` (Result, MathResult)

### Secondary Flow: Generate PDF Report

1. Client GET `/api/projects/{project_id}/report/` or POST to export endpoint
   - Entry: `ProjectViewSet.report()` or `export()` action
2. ProjectReportGenerator iterates all activities
3. For each activity, ActivityReportGenerator:
   - Calls CalculatorFactory.calculate_result(activity_modules)
   - Extracts text narratives via ActivityDescriptorExtractor
   - Builds WeasyPrint context (HTML + CSS)
4. Renderer combines all sections into single PDF
5. Response: application/pdf file download

**Code References:**
- Report generation: `djangoexact/api/reports/base.py:1+`
- Registry of extractors: `djangoexact/api/reports/registry.py`
- Renderer: `djangoexact/api/reports/renderer.py`

### Tertiary Flow: Bulk LandUseChange Computation (Cloud Run Job)

1. Project triggers LUC scenario computation job
   - Entry: `LandUseChangeViewSet.compute_change()` action or scheduled batch
2. View dispatches to Cloud Run (or subprocess fallback) via `gcp_utils.dispatch_job()`
3. Job service (`api/services/luc_compute.py`) recalculates all LUC slices
4. Results persisted back to ChangeRecord
5. Webhook (if configured) notifies frontend

**Code References:**
- Job dispatch: `djangoexact/api/views.py` (LUC actions)
- Service: `djangoexact/api/services/luc_compute.py`
- Job submission: `djangoexact/gcp_utils.py` (or subprocess)

**State Management:**
- Models use DirtyFieldsMixin to track changes
- HistoricalRecords (simple_history) audit all mutations
- AuditLog middleware captures HTTP-level changes
- ChangeRecord tracks per-activity calculation results

## Key Abstractions

**Module Hierarchy:**
- Purpose: Represent inputs to emission calculations; support scenario variants
- Examples: `AnnualCropland`, `Livestock`, `ForestManagement`, `Fuel`, `Electricity`, `Transport`
- Pattern: Each model type has a corresponding Calculator class (ClassName + "Calculator")
- Scenarios: start (baseline), with (intervention), without (business-as-usual)

**Land Modules vs. Non-Land Modules:**
- Purpose: Separate land-use-specific calculation (three scenarios) from simple inputs (single value)
- Examples (Land): AnnualCropland, PerennialCropland, Grassland, ForestManagement
- Examples (Non-Land): Fuel, Electricity, Input, Transport
- Pattern: LandModule requires land_use_change relation; others do not

**BreakdownTypes Enum:**
- Purpose: Aggregate results by emission type or source
- Options: TOTAL (sum), ACTIVITY (by type), GAS (CO2/CH4/N2O), ACTIVITY_GAS (matrix)
- Used by: Serializers to format result output

**Scenario Strings:**
- start_w (with intervention at start year)
- start_wo (without intervention at start year)
- w (with intervention, ongoing)
- wo (without intervention, ongoing)
- Pattern: Calculators compute all three at once; views filter by request param

## Entry Points

**HTTP Entry Point:**
- Location: `djangoexact/urls.py:21` (ROOT_URLCONF)
- Routes to: `djangoexact/api/urls.py` (DRF router)
- WSGI app: `djangoexact/main.py:1` (App Engine entrypoint; imports from wsgi.py)

**Management Commands:**
- `python manage.py load_reference_data --app=all` - Bootstrap IPCC fixtures from JSON
- `python manage.py dump_reference_data --app=all` - Export DB to JSON fixtures
- `python manage.py migrate` - Apply schema changes
- `python manage.py runserver` - Local development

**Background Jobs:**
- Cloud Run Job: `deploy/Dockerfile.computation_job` for long-running emissions calculations
- Subprocess fallback: `api/services/luc_compute.py` runs in-process if Cloud Run unavailable

**Admin Interface:**
- Location: `/admin/` (unfold-styled Django admin)
- Auth: Django superuser (separate from Firebase users)

## Architectural Constraints

- **Threading:** Single-threaded event loop (Django/WSGI). Background compute jobs delegated to Cloud Run (or subprocess).
- **Global state:** Module-level singletons in `api/defaults.py` (DefaultsFactory cache). CalculatorFactory is stateless.
- **Circular imports:** Avoided via explicit imports in calculators.py (no `from api.models import *`).
- **Database:** Single PostgreSQL instance (Cloud SQL production; SQLite dev). Routers point both to 'default'.
- **Calculation cache:** WeakValueDictionary in reports/cache.py to avoid recalculation within same request.
- **Immutable reference data:** IPCC tables loaded once at startup; updates via dump/load cycle.

## Anti-Patterns

### Circular Dependency in Scenario Helpers

**What happens:** `is_with()`, `is_without()`, `is_business_as_usual()` helpers in calculators.py inspect module attributes to determine scenario eligibility, but scenarios are defined on the LandUseChange relation.

**Why it's wrong:** Coupling between land modules and land use change logic; hard to test scenario logic in isolation; breaks if relation is nullable.

**Do this instead:** Pass scenario as explicit parameter to calculator constructor; extract scenario-determination logic to separate service class in `api/services/scenario_resolution.py`.

### Hardcoded Scenario Constants

**What happens:** Scenario strings like "start_w", "start_wo", "w", "wo" are hardcoded throughout calculators.

**Why it's wrong:** Typos go undetected; changes require string search; no single source of truth.

**Do this instead:** Create `ScenarioType` enum in `api/models.py` or `api/utilities.py`; import everywhere.

### Calculator-specific Defaults Resolution

**What happens:** Each calculator fetches IPCC defaults via different patterns (some call `defaults.py` functions, some inline queries).

**Why it's wrong:** Inconsistent error handling; defaults fetching logic scattered across 60+ files.

**Do this instead:** Extract all defaults queries to single `DefaultsResolver` class in `api/defaults.py`; inject as dependency to calculator.

## Error Handling

**Strategy:** Explicit exception raises in adapters; errors bubble to DRF exception handler; returns 400 BadRequest with detail.

**Patterns:**
- CalculatorFactory raises Exception if no calculator found for model type
- Calculator.calculate() catches math layer exceptions, wraps with context (module name)
- DRF ValidationError serialized to 400 response
- Firebase token validation in accounts/firebase.py returns 401 Unauthorized
- IPCC defaults missing -> 400 with "Default not found for [table].[field]" message

## Cross-Cutting Concerns

**Logging:** Python logging module via `import logging as log`. DEBUG level used in calculators. Console handler in settings.py.

**Validation:** Django model validators (RegexValidator for alphanumeric); DRF serializer validate_* methods; calculator.validate_inputs() pre-compute.

**Authentication:** Firebase Admin SDK verifies tokens; custom FirebaseAuthentication class in DRF; email-based CustomUser model (no username).

**Authorization:** Custom permissions in `api/permissions.py` (ProjectPermission, ActivityPermission). DRF permission_classes on ViewSet actions.

**Caching:** WeakValueDictionary for calculator results within request. Django cache backend for reference data (optional).

**Change Tracking:** AuditLog middleware (all changes logged). HistoricalRecords on Project, Activity, Comment models. SimpleHistory tracks what changed, not why. ChangeRecord captures scenario results.

---

*Architecture analysis: 2026-07-08*
