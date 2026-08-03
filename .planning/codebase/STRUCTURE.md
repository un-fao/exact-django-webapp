# Codebase Structure

**Analysis Date:** 2026-07-08

## Directory Layout

```
exact-django-webapp/                        # Repo root (deployment templates, CI config)
├── README.md                                # Project overview
├── bitbucket-pipelines.yml                  # Legacy CI (Bitbucket)
├── .github/workflows/deploy.yaml            # Active CI (GitHub)
├── .env                                     # Base environment config
├── .env.development                         # Dev overrides
├── .env.review                              # Review env overrides
├── .env.production                          # Prod overrides (secrets from Google Cloud Secret Manager)
├── deploy/                                  # Deployment artifacts
│   ├── Dockerfile.computation_job           # Cloud Run image for long-running jobs
│   └── app.yaml                             # App Engine config template
├── gcp-deployment/                          # GCP Cloud Function config
├── docs/                                    # Project documentation
│   ├── plans/                               # GSD phase documentation
│   ├── migrations/                          # Database migration notes
│   └── superpowers/                         # Claude agent guides
│
└── djangoexact/                             # Django project root (python manage.py from here)
    ├── manage.py                            # Django CLI
    ├── main.py                              # App Engine WSGI entrypoint
    ├── requirements.txt                     # Python dependencies
    ├── package.json                         # Frontend dependencies
    ├── pytest.ini                           # (Not checked in; pytest uses defaults)
    │
    ├── djangoexact/                         # Django settings package
    │   ├── settings.py                      # All config (env-driven)
    │   ├── urls.py                          # Root URL routing
    │   ├── wsgi.py                          # WSGI application
    │   ├── .env                             # (Runtime env, not checked in)
    │   ├── .env.development                 # Dev overrides
    │   └── .env.review
    │
    ├── api/                                 # Main Django app (projects, activities, modules, calculations)
    │   ├── models.py                        # Project, Activity, Module, LandModule, CustomUser models
    │   ├── serializers.py                   # ~1200 lines: DRF serializers for all models
    │   ├── views.py                         # ~2800 lines: DRF ViewSets, nested routers, actions
    │   ├── urls.py                          # Router config (rest_framework + rest_framework_nested)
    │   ├── calculators.py                   # ~8000 lines: CalculatorFactory + 60+ calculator classes
    │   ├── defaults.py                      # DefaultsFactory - IPCC defaults resolution
    │   ├── utilities.py                     # Helpers (ScenarioTypes, FOSSIL_METHANE_FUELS, etc.)
    │   ├── permissions.py                   # Custom permission classes
    │   ├── filters.py                       # DjangoFilterBackend predicates
    │   ├── labels.py                        # Field label mappings for reports
    │   │
    │   ├── reports/                         # PDF generation (WeasyPrint)
    │   │   ├── base.py                      # ProjectReportGenerator, ActivityReportGenerator
    │   │   ├── renderer.py                  # WeasyPrint template rendering
    │   │   ├── html_context.py              # HTML template context builders
    │   │   ├── data_types.py                # ProjectResult, ActivityResult dataclasses
    │   │   ├── extractors.py                # Module-to-narrative extractors
    │   │   ├── registry.py                  # Module type -> extractor mapping
    │   │   ├── cache.py                     # Calculation cache (WeakValueDictionary)
    │   │   ├── constants.py                 # Report formatting constants
    │   │   └── templates/                   # HTML email/report templates
    │   │
    │   ├── services/                        # Business logic services
    │   │   ├── luc_compute.py               # Land use change scenario computation
    │   │   ├── minitool_compute.py          # Standalone calculator integration
    │   │   └── minitool_changes_import.py   # Import results from minitool
    │   │
    │   ├── management/commands/             # Custom Django commands
    │   │   ├── load_reference_data.py       # Load IPCC fixtures from JSON
    │   │   ├── dump_reference_data.py       # Export DB to JSON fixtures
    │   │   └── ...
    │   │
    │   ├── tests/                           # APITestCase test suites
    │   │   ├── test_reference_bootstrap.py  # Fixture round-trip validation
    │   │   ├── test_faostat_service.py      # External data service tests
    │   │   └── ...
    │   │
    │   ├── migrations/                      # Django ORM schema (auto-generated)
    │   ├── fixtures/                        # API reference data JSON
    │   ├── templates/                       # Django HTML templates
    │   └── static/                          # (Compiled to djangoexact/static/)
    │
    ├── ipcc/                                # Reference data app
    │   ├── models.py                        # IPCCTable, GlobalWarmingPotential, regional factors
    │   ├── views.py                         # Public read-only endpoints
    │   ├── serializers.py                   # IPCC model serializers
    │   ├── admin.py                         # Django admin config
    │   ├── db_router.py                     # Database routing (scaffold for future split)
    │   │
    │   ├── fixtures/                        # IPCC reference data (JSON, large)
    │   │   ├── gwp.json                     # Global Warming Potentials
    │   │   ├── ipcc_table_*.json            # Per-category emission factors
    │   │   └── ...
    │   │
    │   ├── api_fixtures/                    # API-specific reference data
    │   ├── management/commands/             # IPCC-specific management commands
    │   ├── migrations/                      # ORM schema
    │   └── tests/
    │
    ├── accounts/                            # Authentication app
    │   ├── models.py                        # (Empty; CustomUser in api/models.py)
    │   ├── views.py                         # Auth endpoints (verify-token, reset-password, etc.)
    │   ├── serializers.py                   # AuthToken, PasswordReset serializers
    │   ├── firebase.py                      # FirebaseAuthentication DRF class
    │   ├── firebase_auth.py                 # Firebase Admin SDK wrapper
    │   ├── urls.py                          # Auth route handlers
    │   ├── middleware.py                    # (Disabled in settings; for future use)
    │   └── migrations/
    │
    ├── blog/                                # In-app news/announcements
    │   ├── models.py                        # BlogPost model
    │   ├── views.py                         # BlogPostViewSet
    │   ├── urls.py
    │   ├── migrations/
    │   ├── static/
    │   └── templates/
    │
    ├── public/                              # Public data endpoints (no auth required)
    │   ├── models.py
    │   ├── views.py                         # Public read-only ViewSets
    │   ├── urls.py
    │   └── migrations/
    │
    ├── minitool/                            # Lightweight standalone calculator
    │   ├── models.py                        # MinitoolProject, MinitoolResult
    │   ├── views.py                         # MinitoolViewSet
    │   ├── urls.py
    │   ├── middleware.py                    # Separate SQLite DB connection
    │   ├── minitool.db                      # (Checked-in working file; local SQLite)
    │   ├── migrations/
    │   └── tests/
    │
    ├── admin_scripts/                       # Admin utility app
    │   ├── models.py                        # Admin task models
    │   ├── views.py                         # Admin action endpoints
    │   ├── urls.py
    │   ├── catalog/                         # Admin task catalog definitions
    │   ├── management/commands/             # Custom admin scripts
    │   ├── migrations/
    │   ├── static/
    │   └── templates/
    │
    ├── math_model/                          # Pure math library (framework-agnostic)
    │   ├── no_time_dependency_final/        # Current IPCC calculation models
    │   │   ├── annuals.py                   # Annual cropland emissions (11 KB)
    │   │   ├── perennial_cropping.py        # Perennial cropland (12 KB)
    │   │   ├── flooded_rice.py              # Flooded rice (12 KB)
    │   │   ├── livestock.py                 # Livestock + manure (22 KB)
    │   │   ├── forest_management.py         # Forest C sequestration (54 KB)
    │   │   ├── coastal_wetlands.py          # Wetland emissions (15 KB)
    │   │   ├── grassland_management.py      # Grassland management (6 KB)
    │   │   ├── fisheries_and_aquaculture.py # Fisheries + aquaculture (16 KB)
    │   │   ├── inputs.py                    # Fuel, electricity, irrigation (17 KB)
    │   │   ├── inlands.py                   # Organic soils, peat (35 KB)
    │   │   ├── defo.py                      # Deforestation (9 KB)
    │   │   ├── oluc.py                      # Other land use change (7 KB)
    │   │   ├── value_chains.py              # Post-harvest emissions (1 KB)
    │   │   ├── waterbodies.py               # Inland water (3 KB)
    │   │   ├── general_functions.py         # Utility math functions (39 KB)
    │   │   ├── ghg_emissions_classes.py     # Result, Inventory dataclasses (14 KB)
    │   │   ├── ghg_inventory_class.py       # Inventory aggregation (3 KB)
    │   │   └── generalized_modules.py       # Base classes (4 KB)
    │   │
    │   └── excel_reference_version/         # Legacy Excel-derived calculations (for validation)
    │
    ├── scripts/                             # Utility scripts (not Django commands)
    │   ├── load_*.py
    │   └── ...
    │
    ├── locale/                              # i18n translations
    │   ├── en/
    │   ├── es/                              # Spanish
    │   ├── fr/                              # French
    │   └── ru/                              # Russian
    │
    ├── docs/                                # In-repo documentation
    │   └── guides/
    │       ├── fixtures-guide.md            # How to manage IPCC fixtures
    │       └── ...
    │
    ├── media/                               # User uploads (file attachments)
    ├── static/                              # Compiled frontend assets (webpack output)
    ├── logs/                                # Runtime log files
    └── test_db.sqlite3                      # (Checked-in test fixture; do not delete)
```

## Directory Purposes

**`exact-django-webapp/` (Repo Root):**
- Purpose: Deployment and CI configuration; documentation root
- Contains: .env files (templates), Docker/App Engine configs, CI pipelines, docs/
- Notes: `.env*` files here are sed-substituted by CI; actual secrets in Google Cloud Secret Manager

**`djangoexact/` (Django Root):**
- Purpose: All Python/Django code; entry point for `python manage.py` commands
- Contains: Apps, math_model, static/media directories
- Key files: manage.py, main.py (App Engine WSGI), requirements.txt, package.json

**`djangoexact/api/` (Main App):**
- Purpose: Core project/activity/module CRUD + calculation orchestration
- Size: ~8000 lines (calculators.py), ~2800 lines (views.py), ~1200 lines (serializers.py)
- Key patterns: DRF ViewSets, nested routers, CalculatorFactory, three-scenario support

**`djangoexact/api/calculators.py`:**
- Purpose: Adapter layer; translates Django models to math inputs
- Contains: BaseCalculator, 60+ specific calculators (one per module type), CalculatorFactory
- Pattern: Class name matching (e.g., AnnualCropland model -> AnnualCroplandCalculator class)
- Scenarios: Each calculator computes start_w, start_wo, w, wo internally; returns tuple

**`djangoexact/api/reports/`:**
- Purpose: Convert calculation results to PDF reports
- Contains: ProjectReportGenerator, ActivityReportGenerator, extractors registry, WeasyPrint templates
- Output: Single PDF with executive summary, per-activity narratives, result tables

**`djangoexact/math_model/no_time_dependency_final/`:**
- Purpose: Pure IPCC emission calculations; no framework imports
- Size: 13 category-specific modules + 3 shared utility modules
- Pattern: Each module exports a class (e.g., AnnualCropland) with calculate() method
- Result: Returns MathResult tuple (with_intervention, without_intervention)

**`djangoexact/ipcc/`:**
- Purpose: Immutable reference data (IPCC tables, GWP coefficients, regional defaults)
- Contains: Models for 50+ IPCC tables; fixture JSON files
- Operations: load_reference_data (JSON -> DB), dump_reference_data (DB -> JSON)
- Round-trip validation: test_reference_bootstrap.py ensures no PK changes without --force

**`djangoexact/accounts/`:**
- Purpose: User authentication and authorization
- Auth method: Firebase Admin SDK + email-based CustomUser (no username field)
- Flow: Client obtains Firebase token -> POST /api/accounts/verify-token -> JWT (SimpleJWT)
- Protected: All /api/* endpoints except /api/public/*

**`djangoexact/minitool/`:**
- Purpose: Lightweight standalone calculator with separate SQLite DB
- Uses: Same math_model layer, but single-scenario (no with/without split)
- Isolation: DatabaseConnectionMiddleware manages separate connection pool

**`djangoexact/blog/`, `djangoexact/public/`, `djangoexact/admin_scripts/`:**
- Purpose: Supplementary apps (news, reference data lookup, admin utilities)
- Auth: blog requires auth; public is open; admin_scripts requires staff
- Minimal coupling: Independent models and ViewSets

## Key File Locations

**Entry Points:**
- `djangoexact/main.py` - App Engine WSGI (calls wsgi.app)
- `djangoexact/djangoexact/wsgi.py` - Django WSGI application
- `djangoexact/djangoexact/urls.py` - Root URL router

**Configuration:**
- `djangoexact/djangoexact/settings.py` - All Django config (env-driven)
- `djangoexact/requirements.txt` - Python dependencies
- `djangoexact/package.json` - Frontend dependencies (webpack, etc.)

**Core Logic:**
- `djangoexact/api/models.py` - Project, Activity, Module hierarchy
- `djangoexact/api/calculators.py` - Adapter layer + calculation orchestration
- `djangoexact/api/views.py` - HTTP endpoint logic (DRF ViewSets)
- `djangoexact/api/serializers.py` - Request/response transformation
- `djangoexact/math_model/no_time_dependency_final/` - Pure calculation logic

**Testing:**
- `djangoexact/api/tests/` - Test suites (Django APITestCase or pytest)
- `djangoexact/ipcc/test_fixture_*.py` - Reference data round-trip tests

**Reports:**
- `djangoexact/api/reports/base.py` - Report generation entry point
- `djangoexact/api/reports/renderer.py` - WeasyPrint template rendering
- `djangoexact/api/reports/registry.py` - Module type -> extractor mapping

**Reference Data:**
- `djangoexact/ipcc/fixtures/gwp.json` - Global Warming Potentials
- `djangoexact/ipcc/fixtures/ipcc_table_*.json` - Per-category factors
- `djangoexact/api/fixtures/` - API-level reference data

## Naming Conventions

**Files:**
- Model: `api/models.py` (single file per app)
- Serializer: `api/serializers.py` (single file per app)
- View: `api/views.py` (single file per app)
- URL routes: `app/urls.py`
- Test: `app/tests/test_*.py` or `app/tests/*.py` (co-located)
- Utility: `app/utilities.py`, `app/defaults.py`, `app/permissions.py`, `app/filters.py`

**Directories:**
- Per-app: `djangoexact/[app_name]/` (accounts, api, ipcc, blog, etc.)
- Tests: `app/tests/` (inside app directory)
- Reports: `api/reports/` (sub-package)
- Services: `api/services/` (business logic)
- Management commands: `app/management/commands/`
- Migrations: `app/migrations/`
- Templates: `app/templates/`
- Fixtures: `app/fixtures/`

**Classes:**
- Models: PascalCase (e.g., CustomUser, AnnualCropland, Project)
- Calculators: [ModelName] + "Calculator" (e.g., AnnualCroplandCalculator)
- ViewSets: [ModelName] + "ViewSet" (e.g., ProjectViewSet, ActivityViewSet)
- Serializers: [ModelName] + "Serializer" (e.g., ProjectSerializer, ReadProjectSerializer, WriteProjectSerializer)
- Permissions: [Name] + "Permission" (e.g., ProjectPermission)

**Functions/Methods:**
- Helpers in calculators.py: is_luc_remaining_same(), is_business_as_usual()
- Calculator methods: calculate(), defaults(), validate_inputs()
- View actions: @action decorator (e.g., results, export, report)
- Serializer methods: validate_[field](), to_representation()

**Enum/Constants:**
- ScenarioTypes (api/utilities.py) - start_w, start_wo, w, wo
- BreakdownTypes (math_model/ghg_emissions_classes.py) - TOTAL, ACTIVITY, GAS, ACTIVITY_GAS
- FOSSIL_METHANE_FUELS (api/utilities.py) - Hardcoded list

## Where to Add New Code

**New Feature (e.g., add calculation module for new activity type):**
1. Create Django model: `api/models.py` (inherit from Module or LandModule)
2. Add calculator: `api/calculators.py` (create [ModelName]Calculator class)
3. Add serializer: `api/serializers.py` (get_model_serializer or custom)
4. Add math logic: `math_model/no_time_dependency_final/[category_name].py`
5. Register in router: `api/urls.py` (add router.register() line)
6. Add tests: `api/tests/test_[module_type].py`

**New Component/Module:**
- Implementation: `api/models.py` (model definition) + `api/calculators.py` (calculation logic)
- If complex service: `api/services/[name].py`
- Tests: `api/tests/test_[name].py`

**Utilities:**
- Shared helpers: `api/utilities.py` or `api/defaults.py`
- Permission rules: `api/permissions.py`
- Filter predicates: `api/filters.py`

**Reference Data:**
- IPCC tables: `ipcc/models.py` (define model) + `ipcc/fixtures/*.json` (populate)
- API defaults: `api/fixtures/*.json`
- Rebuild fixtures: `python manage.py dump_reference_data --app=all`

**Reports:**
- New report section: `api/reports/extractors.py` (add extractor function)
- Register: `api/reports/registry.py` (add to MODULE_EXTRACTOR_MAP)
- Template: `api/reports/templates/*.html`

## Special Directories

**`djangoexact/media/`:**
- Purpose: User-uploaded files (project attachments)
- Generated: Yes (at runtime)
- Committed: No (in .gitignore)

**`djangoexact/static/`:**
- Purpose: Compiled frontend assets (webpack output)
- Generated: Yes (`npm run build`)
- Committed: No (symlinked or generated in CI)

**`djangoexact/locale/`:**
- Purpose: i18n translation files (.po, .mo)
- Generated: Partially (from `makemessages` command)
- Committed: Yes (.po source files)

**`djangoexact/migrations/`:**
- Purpose: Schema migration history (auto-generated by Django)
- Generated: Yes (`makemigrations` command)
- Committed: Yes (must be tracked for deployment)

**`djangoexact/test_db.sqlite3`:**
- Purpose: Checked-in test fixture database
- Generated: No (manually committed)
- Committed: Yes (tests may depend on schema)

**`djangoexact/minitool.db`:**
- Purpose: Minitool standalone calculator database
- Generated: No (manually committed)
- Committed: Yes (working file for tool)

**`djangoexact/logs/`:**
- Purpose: Runtime log files
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-07-08*
