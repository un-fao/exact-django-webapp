"""Self-contained test settings: fresh SQLite DB seeded from committed fixtures.

Lets the suite run without a cloud Postgres / cloud-sql-proxy:

    python djangoexact/manage.py test api.tests.unit \
        --settings=djangoexact.settings_test

`--keepdb` is supported and recommended for iterative runs (skips the slow
reference-data load on subsequent runs).
"""

import os

# Must be set BEFORE importing base settings: settings.py raises at import time
# if SECRET_KEY is missing (DEBUG False) and the Firebase block crashes without
# cloud credentials. These only take effect when not already provided.
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("SKIP_FIREBASE_INIT", "1")
# admin_scripts.AppConfig.ready() validates the scenario catalog, which
# imports api.minitool and queries the DB at import time — before the test
# DB exists. Skip that startup check under tests.
os.environ.setdefault("SKIP_STARTUP_CATALOG_VALIDATION", "1")

from .settings import *  # noqa: F401,F403,E402

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "test_db.sqlite3"),  # noqa: F405
        "TEST": {"NAME": str(BASE_DIR / "test_db.sqlite3")},  # noqa: F405
    }
}

# Reference data + groups + canonical test users are seeded here once the
# fresh SQLite schema is built.
TEST_RUNNER = "api.tests.runner.SqliteReferenceTestRunner"

# Faster, hermetic, and no external services during tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CLOUD_RUN_COMPUTATION_JOB_NAME = ""
DEBUG = False

# Disable django-auditlog under tests. With AUDITLOG_INCLUDE_ALL_MODELS the
# post_save receiver writes a LogEntry that deepcopies every changed field —
# including the multi-MB cached_results_* JSON the calculation tests populate
# — which thrashes/hangs (effectively forever, ~0 CPU). Auditing is orthogonal
# to the status refactor; read at AuditlogConfig.ready() so no models register.
# EXCLUDE_TRACKING_FIELDS/MODELS must be cleared too: auditlog's
# register_from_settings() raises if they are set while INCLUDE_ALL is False.
AUDITLOG_INCLUDE_ALL_MODELS = False
AUDITLOG_EXCLUDE_TRACKING_FIELDS = ()
AUDITLOG_EXCLUDE_TRACKING_MODELS = ()
