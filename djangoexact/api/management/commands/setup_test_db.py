"""Build and seed the SQLite test database in one step.

Run once before the suite, then run tests with ``--keepdb``:

    python manage.py setup_test_db --settings=djangoexact.settings_test
    python manage.py test api.tests.unit --settings=djangoexact.settings_test --keepdb

The pre-seed + ``--keepdb`` combination is required because the suite queries
reference models at import time (``api/tests/factories.py``), which Django
imports before it would otherwise create the test database.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Migrate and seed the (SQLite) test database with reference data, role groups and test users."

    def handle(self, *args, **options):
        from api.tests.seed import bootstrap_test_db

        self.stdout.write("Applying migrations...")
        call_command("migrate", verbosity=0, run_syncdb=True)

        self.stdout.write("Seeding reference data, role groups and test users...")
        bootstrap_test_db(force_reference=True)

        self.stdout.write(self.style.SUCCESS("Test database ready. Run tests with --keepdb."))
