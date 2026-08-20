"""Stop bare `pytest` from running database tests against a real database.

This repo has no pytest-django. Under bare `pytest` no test database is created,
so `DATABASES['default']` is whatever `.env.<APP_MODE>` points at -- review, or
production. Django's `TransactionTestCase._post_teardown` then TRUNCATEs every
table in `available_apps`. On 2026-08-20 that emptied the review database.

`manage.py test` is unaffected: Django creates and connects to `test_<name>`
before any test runs, so the name check below passes.

Database-free tests (the math_model suites, which call `django.setup()` only for
the app registry) still run under bare pytest -- their classes declare no
databases, so they are never dangerous and are left alone.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "djangoexact"))


def _is_test_database():
    from django.conf import settings

    if not settings.configured:
        return True  # nothing connected yet; nothing to protect
    name = settings.DATABASES.get("default", {}).get("NAME") or ""
    return os.path.basename(str(name)).startswith("test_")


def pytest_collection_modifyitems(items):
    """Skip any DB-touching Django test when pointed at a non-test database."""
    from django.test import SimpleTestCase

    if _is_test_database():
        return

    for item in items:
        cls = getattr(item, "cls", None)
        if cls is None or not issubclass(cls, SimpleTestCase):
            continue
        # SimpleTestCase defaults to databases=set(); TransactionTestCase and
        # TestCase set {'default'}. Non-empty means teardown will flush.
        if getattr(cls, "databases", None):
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        f"REFUSED: {cls.__name__} would run against a non-test database "
                        "and its teardown would TRUNCATE your tables. "
                        "Run database tests with `python manage.py test` instead."
                    )
                )
            )
