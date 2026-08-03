# External Integrations

**Analysis Date:** 2026-07-08

## APIs & External Services

**FAOSTAT (Food and Agriculture Organization Statistics):**
- Service: FAOSTAT API - Provides crop yield data by area, item, and year
- What it's used for: `api/faostat_service.py` fetches yield records to populate agricultural input data
- SDK/Client: `faostat==2.0.1` (Python package)
- Auth: HTTP Basic Auth via `FAOSTAT_USERNAME` and `FAOSTAT_PASSWORD` environment variables
- Key contract: `get_yield(area, item, year=None) -> YieldRecord` in `api/faostat_service.py:1-19`
- Concurrency guard: Module-level lock (`threading.Lock`) due to global state mutation in faostat library (see `api/faostat_service.py:46-50`)
- Error handling: Custom exceptions `FAOSTATNoDataError`, `FAOSTATNetworkError`, `FAOSTATInvalidInputError` in `api/faostat_exceptions.py`
- Business rules: Domain=QCL, Element=Yield; no year = highest year in response; year supplied = exact match or error; prefer Flag="A" for conflicts

**Firebase Authentication:**
- Service: Google Firebase Authentication Service
- What it's used for: User identity verification, token validation for API access
- SDK/Client: `firebase-admin==6.5.0` (Python Admin SDK)
- Auth: Service account credentials via `FIREBASE_SERVICE_ACCOUNT` (base64-encoded JSON)
- Configuration:
  - API Key: `FIREBASE_API_KEY`
  - Auth Domain: `FIREBASE_AUTH_DOMAIN`
  - Project ID: `FIREBASE_PROJECT_ID`
  - Storage Bucket: `FIREBASE_STORAGE_BUCKET`
  - Messaging Sender ID: `FIREBASE_MESSAGING_SENDER_ID`
  - App ID: `FIREBASE_APP_ID`
  - Measurement ID: `FIREBASE_MEASUREMENT_ID`
- Implementation:
  - Service initialized at `djangoexact/djangoexact/settings.py:320` via `firebase_admin.initialize_app(credentials.Certificate(...))`
  - Token verification: `accounts/firebase.py` class `FirebaseAuthentication` extends DRF `BaseAuthentication`
  - Extracts Bearer token from `Authorization` header, verifies via `firebase_admin_auth.verify_id_token()`
  - Maps Firebase UID to `api.CustomUser.firebase_uid` field
  - Excludes paths: `/api/accounts/register/`, `/api/accounts/login/`, `/admin`, `/api/swagger/`, `/api/admin-scripts/*`

**SMTP Email:**
- Service: SMTP mail server for email notifications
- What it's used for: User notifications, password reset emails, job completion messages
- Configuration:
  - Host: `EMAIL_HOST` environment variable
  - Port: `EMAIL_PORT` environment variable
  - TLS enabled: `EMAIL_USE_TLS = True`
  - Username: `SMTP_USER_EMAIL` environment variable
  - Password: `SMTP_USER_PASSWORD` environment variable (secret)
  - Default from address: Derived from `SMTP_USER_EMAIL`
- Implementation: Django built-in `django.core.mail.backends.smtp.EmailBackend` in `settings.py:297`
- Job notifications: Controlled by `JOB_NOTIFICATIONS_ENABLED` environment variable (boolean)

## Data Storage

**Databases:**
- Type/Provider: PostgreSQL (Cloud SQL in production)
- Connection:
  - Production (App Engine): Unix socket at `/cloudsql/<DB_INSTANCE_CONNECTION>` (template-substituted in `settings.py:141-158`)
  - Local/CI: TCP connection via `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT` (template-substituted in `settings.py:160-175`)
  - Connection pooling: Disabled (`CONN_MAX_AGE = 0`), atomic requests disabled (`ATOMIC_REQUESTS = False`)
  - Timeout: 30 seconds on connection init
- Client: Django ORM via `django.db.backends.postgresql` (Engine in settings)
- Adapter: `psycopg2-binary==2.9.6`
- Database routers: `ipcc.db_router.AppSpecificDatabaseRouter` and `api.db_router.AppSpecificDatabaseRouter` (both route to `default` DB; scaffolding for future split)
- Migrations: Auto-run via `python manage.py migrate` in CI/CD (`deploy.yaml:97`)

**File Storage:**
- Primary: Google Cloud Storage (GCS)
- Bucket: `STORAGE_BUCKET` environment variable
- Client: `google-cloud-storage==2.19.0`
- Usage:
  - Upload/download files in `api/serializers.py`, `api/views.py`, `api/admin.py`
  - Used for project exports, reference data archives, report PDFs
  - Explicit import: `from google.cloud import storage` (lazy-imported, not module-level)
- Fallback: Local filesystem during development (no explicit fallback handler; local dev uses local FS by default)

**Caching:**
- Cache: None detected
- In-memory state: Module-level singletons in `api/faostat_service.py` (threading lock, captured base URL)

## Authentication & Identity

**Auth Provider:**
- Primary: Firebase Authentication (handled by `firebase-admin==6.5.0`)
- Secondary: Django Session Authentication (disabled by default in `settings.py:237-240`, commented out)
- Custom User Model: `api.CustomUser` (extends Django `AbstractUser`)
  - Fields: `email` (unique, required), `firebase_uid` (unique), standard Django user fields
  - Manager: `CustomUserManager` with `create_user()` and `create_superuser()` methods
  - Email-based authentication (no username field)

**Token Strategy:**
- Request flow: Client extracts Firebase ID token from frontend auth, passes as Bearer token in `Authorization` header
- Validation: `FirebaseAuthentication.authenticate_credentials()` verifies token expiry and validity via `firebase_admin_auth.verify_id_token(decoded_token)`
- Errors: `AuthenticationFailed` exceptions on expired or invalid tokens
- Token lifetime: 1 hour for JWT (`SIMPLE_JWT.ACCESS_TOKEN_LIFETIME` in `settings.py:258`)

**Admin Access:**
- Method: Django session-based (not Firebase)
- Excluded from Firebase auth via explicit path check in `FirebaseAuthentication` class (line 15: `/admin`, `/api/admin-scripts/*`)
- Django admin panel uses unfold customization (`django-unfold==0.34.0`)

## Monitoring & Observability

**Error Tracking:**
- Tracking: Not detected
- Logging: Django logging to console via `StreamHandler` (settings.py:265-285)
  - Root logger level: DEBUG
  - Handlers: Console only (no file handlers, no Sentry/Rollbar/DataDog)

**Logs:**
- Destination: Standard output (stdout/stderr)
- Format:
  - Simple format: `[{levelname} {asctime}] {module} \t {message}`
  - Verbose format: `{levelname} {asctime} {module} {process:d} {thread:d} {message}`
- Location: App Engine logs aggregated via Cloud Logging; local dev logs to console

**Request Auditing:**
- Mechanism: `django-auditlog==3.0.0` and `django-simple-history==3.8.0`
- Scope: All models tracked for changes (via `AUDITLOG_INCLUDE_ALL_MODELS = True`)
- Middleware: `auditlog.middleware.AuditlogMiddleware` and `simple_history.middleware.HistoryRequestMiddleware`
- Excluded fields: `created`, `modified` (from `AUDITLOG_EXCLUDE_TRACKING_FIELDS`)
- Use case: Compliance, change tracking, audit trail

## CI/CD & Deployment

**Hosting:**
- Primary: Google App Engine Standard (Python 3.11 runtime)
- Secondary: Google Cloud Run (background computation jobs)
- Configuration: `djangoexact/app.yaml` (templated by CI, not checked in with real values)

**CI Pipeline:**
- System: GitHub Actions (primary), Bitbucket Pipelines (legacy, commented in CLAUDE.md)
- Workflow: `.github/workflows/deploy.yaml`
- Trigger: Push to `main`, `review`, or `feature/id-responses` branches
- Environment selection:
  - `main` branch -> Production environment
  - `review` branch -> Review environment
  - Other -> Develop environment
- Authentication: Workload Identity Federation (OIDC token exchange with GCP)
- Steps:
  1. Checkout code (including LFS)
  2. Authenticate to GCP via `google-github-actions/auth` with workload identity
  3. Set up Python 3.11
  4. Start cloud-sql-proxy for local DB access
  5. Template substitute secrets into `app.yaml` and `settings.py` via sed
  6. Install Python dependencies
  7. Run migrations
  8. Collect static files
  9. Deploy to App Engine (implicit via `gcloud app deploy`)

**Background Jobs (Cloud Run):**
- Trigger: Manual dispatch from API endpoint (via `admin_scripts/cloud_run.py`)
- Job: `python manage.py run_computation_job` (management command at `admin_scripts/management/commands/run_computation_job.py`)
- Execution: Cloud Run Job (serverless container)
- Container: `gcr.io/$PROJECT_ID/exact-computation-job:latest` (built and pushed by `deploy/cloudbuild-computation-job.yaml`)
- Configuration:
  - Job name: `CLOUD_RUN_COMPUTATION_JOB_NAME` env var
  - Region: `CLOUD_RUN_REGION` env var (default: `europe-west1`)
  - Client: `google-cloud-run==0.16.0` (SDK for dispatching jobs)

**Build Artifacts:**
- Docker image (Cloud Run): Multi-stage build at `deploy/Dockerfile.computation_job`
  - Base: `python:3.11-slim`
  - Dependencies: `psycopg2` (libpq), build tools in builder stage, stripped in runtime
  - CMD: `python manage.py run_computation_job`
- Cloud Build config: `deploy/cloudbuild-computation-job.yaml` (invoked from GitHub Actions)

## Environment Configuration

**Required env vars (per-environment):**

Production:
- `DJANGO_DEBUG=False`
- `SECRET_KEY` (from GCP Secret Manager)
- `DB_ENGINE=django.db.backends.postgresql`
- `DB_INSTANCE_CONNECTION=project:region:instance` (for Unix socket)
- `DB_PASSWORD` (from Secret Manager)
- `ALLOWED_HOSTS=exact.apps.fao.org`
- `CORS_ALLOWED_ORIGINS=https://exact.apps.fao.org` (comma-separated)
- All Firebase config vars
- `STORAGE_BUCKET=prod-storage-bucket`
- `CLOUD_RUN_COMPUTATION_JOB_NAME=projects/*/locations/*/jobs/*`
- `JOB_NOTIFICATIONS_ENABLED=true`

Review/Staging:
- Similar to production, with different hostnames/buckets
- `FRONTEND_URL=https://exact.review.fao.org`

Development:
- `DJANGO_DEBUG=True`
- Optional `SECRET_KEY` (defaults to placeholder)
- `DB_ENGINE`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT` (local PostgreSQL)
- `ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0`
- Firebase config optional (can be stubbed for local testing)

**Secrets location:**
- Production: Google Cloud Secret Manager (accessed via Application Default Credentials)
- Secrets injected into CI/CD environment via GitHub repository/environment secrets
- Never committed to Git (`.gitignore` excludes `.env*`, credentials files)

**Local development:**
- `.env` file (checked in CLAUDE.md as per-repo, not checked in `.env.development`)
- Template: `.env.{APP_MODE}` for overrides

## Webhooks & Callbacks

**Incoming:**
- Endpoints: None detected
- No Stripe/webhook-like receivers in `urls.py`

**Outgoing:**
- Email notifications: Job completion messages (optional, controlled by `JOB_NOTIFICATIONS_ENABLED`)
- PDF exports: Generated and stored in GCS, returned to client via HTTP response (not pushed)
- No scheduled outbound webhooks or scheduled events detected

## API Documentation & Schema

**OpenAPI/Swagger:**
- Schema generator: `drf-spectacular==0.26.2` (primary)
- Legacy: `drf-yasg==1.21.14` (coexists but superseded by spectacular)
- Endpoints:
  - `/api/swagger/` (Swagger UI)
  - `/api/schema/` (OpenAPI YAML schema)
  - Excluded from Firebase auth via `FirebaseAuthentication` (line 15)

---

*Integration audit: 2026-07-08*
