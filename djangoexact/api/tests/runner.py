"""Test runner that keeps the (pre-seeded) SQLite test DB self-contained.

The suite queries reference models at import time (``api/tests/factories.py``),
which Django imports *before* ``setup_databases``. So the SQLite file must be
built and seeded beforehand:

    python manage.py setup_test_db --settings=djangoexact.settings_test
    python manage.py test api.tests.unit --settings=djangoexact.settings_test --keepdb

This runner re-asserts the seed inside ``setup_databases`` as an idempotent
safety net (reference load is skipped when already present).
"""

import logging

from django.test.runner import DiscoverRunner

log = logging.getLogger(__name__)


class SqliteReferenceTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        result = super().setup_databases(**kwargs)
        from api.tests.seed import bootstrap_test_db

        bootstrap_test_db()
        return result
