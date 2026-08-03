# Technology Stack

**Analysis Date:** 2026-07-08

## Languages

**Primary:**
- Python 3.11 - Server-side business logic, GHG calculations, Django ORM, API layer
- JavaScript - Frontend asset bundling (Webpack), Tailwind CSS processing

## Runtime

**Environment:**
- Python 3.11.x via `pyenv` / `.python-version` file
- App Engine Standard runtime: `python311` (declared in `djangoexact/app.yaml`)
- WSGI server: Gunicorn 22.0.0 (entrypoint in `app.yaml`: `gunicorn -b :$PORT -w 4 main:app --timeout 120`)

**Package Manager:**
- pip (Python) - pinned versions in `djangoexact/requirements.txt` (71 packages)
- npm (Node.js) - minimal, only for frontend tooling in `djangoexact/package.json`
- Lockfile: `djangoexact/requirements.txt` (no `Pipfile.lock` or `poetry.lock`)

## Frameworks

**Core:**
- Django 5.2.14 - Web framework, ORM, admin interface, migrations
- Django REST Framework 3.16.1 - REST API layer, serializers, viewsets, nested routing
- drf-spectacular 0.26.2 - OpenAPI 3.0 schema generation for API docs
- drf-yasg 1.21.14 - Swagger/OpenAPI documentation (legacy, coexists with drf-spectacular)

**Database/ORM:**
- Django ORM (built-in) - No additional ORMs; all database queries via Django models
- psycopg2-binary 2.9.6 - PostgreSQL adapter for `django.db.backends.postgresql`

**Authentication/Authorization:**
- djangorestframework-simplejwt 5.5.1 - JWT token generation and validation
- firebase-admin 6.5.0 - Firebase Admin SDK; custom `FirebaseAuthentication` class at `accounts/firebase.py` handles Bearer token verification via `firebase_admin_auth.verify_id_token()`
- Custom user model: `api.CustomUser` (extends `AbstractUser`, email-based, Firebase UID field)

**Admin/UI:**
- django-unfold 0.34.0 - Modern admin panel replacement (pre-configured at `INSTALLED_APPS`, settings at `djangoexact/djangoexact/settings.py:324`)
- django-ckeditor 6.7.1 - Rich text editor for blog/content fields

**Data Processing:**
- pandas 2.0.1 - DataFrame operations for reference data loading, FAOSTAT response parsing
- numpy 1.24.3 - Numerical operations, underlying pandas
- openpyxl 3.1.2 - Excel file reading for fixtures
- XlsxWriter 3.2.0 - Excel file generation (exports)

**PDF Generation:**
- weasyprint 68.0 - HTML-to-PDF converter (used in `api/views.py` and `public/views.py` for report PDF generation)

**Utilities:**
- python-dotenv 1.2.2 - Load environment variables from `.env` files
- django-environ 0.11.2 - Environment variable parsing
- django-extensions 3.2.3 - Additional management commands
- python-slugify 8.0.4 - URL-safe slug generation
- requests 2.33.0 - HTTP client library (used for external API calls, headers setup)
- PyYAML 6.0.2 - YAML parsing for fixtures
- ruamel.yaml 0.17.26 - Enhanced YAML support for round-trip preservation

**Auditing/History:**
- django-auditlog 3.0.0 - Change tracking for all models (audit middleware in settings)
- django-simple-history 3.8.0 - Historical record snapshots for models (tracked via middleware)
- django-dirtyfields 1.9.3 - Track which fields changed in an instance

**Internationalization:**
- django-modeltranslation 0.19.9 - Multi-language model fields (English, French, Spanish, Russian; see `settings.py:210`)
- django-archive 0.2.0 - Soft delete / archiving support

**API Routing:**
- drf-nested-routers 0.94.1 - Nested REST routing (e.g., `/api/projects/{pk}/activities/`)

**Testing:**
- pytest 9.0.3 - Test runner
- factory-boy 3.3.3 - Test fixture factories
- Django's built-in `APITestCase` / `TestCase` (tests inherit from these, no pytest-django)

**Build/Frontend:**
- webpack 5.95.0 - Module bundler for JavaScript
- webpack-cli 5.1.4 - CLI for Webpack
- tailwindcss 3.4.14 - Utility-first CSS framework (PostCSS-based)
- @tailwindcss/typography 0.5.15 - Tailwind plugin for prose styling
- @tanstack/react-store 0.7.3 - State management library (minimal frontend logic)
- lodash 4.17.21 - Utility functions library

**Development Tools:**
- pip-chill 1.0.3 - Display installed packages in human-readable format
- matplotlib 3.8.2 - Data visualization (used in admin dashboards, reference data validation)

**Data Source Integration:**
- faostat 2.0.1 - FAOSTAT API client for fetching crop yield data (used in `api/faostat_service.py`)
- tqdm 4.67.1 - Progress bars for long-running tasks

**Cloud/Storage:**
- google-cloud-storage 2.19.0 - Google Cloud Storage client (upload/download files)
- google-cloud-run 0.16.0 - Cloud Run job dispatch (trigger background computation jobs from API)

**Dependency Management:**
- setuptools >= 78.1.1 - Package installer/builder (pinned in requirements.txt and CI/CD)
- packaging >= 24.0 - Version parsing utilities

## Configuration

**Environment:**
- Primary config: `djangoexact/djangoexact/settings.py` (437 lines, modular, template-aware)
- Environment loading: `.env` (defaults) + `.env.{APP_MODE}` (overrides) via `load_dotenv()` at `settings.py:23-29`
- APP_MODE detection: `os.getenv("APP_MODE")` (values: `development`, `review`, `production`, `test`)
- Key env vars (required or defaulted):
  - `SECRET_KEY` - Django secret (required in non-DEBUG mode)
  - `DB_ENGINE`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT` - PostgreSQL connection
  - `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT` (base64-encoded)
  - `STORAGE_BUCKET` - Google Cloud Storage bucket name
  - `CLOUD_RUN_COMPUTATION_JOB_NAME`, `CLOUD_RUN_REGION` - Background job configuration
  - `EMAIL_HOST`, `EMAIL_PORT`, `SMTP_USER_EMAIL`, `SMTP_USER_PASSWORD` - SMTP configuration
  - `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` - Security headers
  - `FAOSTAT_USERNAME`, `FAOSTAT_PASSWORD` - FAOSTAT API credentials

**Build:**
- Python dependencies: `djangoexact/requirements.txt` (pip freeze format, pinned versions)
- Frontend: `djangoexact/package.json` (minimal npm scripts: `npm run build` = `webpack --mode=development`)
- Webpack config: `djangoexact/webpack.config.js` (entry: `static/js/index.js`, output: `static/js/main.js`)
- Database migrations: `djangoexact/api/migrations/`, `djangoexact/ipcc/migrations/`
- Fixtures: `djangoexact/api/fixtures/`, `djangoexact/ipcc/fixtures/` (JSON format, loaded via `load_reference_data` command)

## Platform Requirements

**Development:**
- Python 3.11
- PostgreSQL 12+ (local dev or Cloud SQL proxy via `cloud-sql-proxy`)
- Node.js 16+ (for npm/Webpack)
- Virtualenv: `python -m venv env` (convention)
- Optional: `cloud-sql-proxy` for local connection to Cloud SQL

**Production:**
- Google App Engine Standard (Python 3.11 runtime)
- Google Cloud SQL for PostgreSQL (primary database)
- Google Cloud Storage (file storage, media bucket)
- Google Cloud Run (background computation jobs)
- Firebase (authentication service)
- SMTP server (email notifications)

**Testing:**
- pytest (local execution, no CI automation; tests are a pre-PR gate)
- Django TestCase/APITestCase (no pytest-django plugin)

## Summary

EX-ACT is a Python 3.11 + Django 5.2 REST API backed by PostgreSQL, deployed on Google App Engine Standard with supplementary Cloud Run jobs. Authentication uses Firebase Admin SDK. Frontend assets are minimal (Tailwind + Webpack). The stack emphasizes scientific computing (NumPy, Pandas for GHG calculations) and data integrity (auditlog, simple-history, versioning). Deployment templating uses sed substitution on `app.yaml` and `settings.py` for per-environment secrets injection from GitHub Actions / GCP Secret Manager.

---

*Stack analysis: 2026-07-08*
