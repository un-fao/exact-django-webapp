"""Empty-DB bootstrap guarantee for the unified reference data pipeline.

This is THE executable guarantee that a fresh database plus
`load_reference_data` yields the same bytes `dump_reference_data` would
produce — i.e. the committed fixtures are round-trip stable against the
manifest.
"""

import json
import tempfile
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.test import TransactionTestCase

from api.fixtures_manifest import MANIFEST


class ReferenceDataBootstrapTests(TransactionTestCase):
    serialized_rollback = False
    # Scope flush() to only the apps whose models the manifest owns. Without
    # this, Django's TransactionTestCase teardown tries to TRUNCATE every
    # table in the project — including Wagtail/auth tables whose inbound FKs
    # require `TRUNCATE ... CASCADE` (which Django does not emit). That leaves
    # reference data in place between tests and blows up subsequent loaddata
    # runs on unique constraints. Restricting `available_apps` tells Django
    # to flush only these apps' tables, avoiding the Wagtail FK chain entirely.
    available_apps = ["api", "ipcc"]

    def test_fixture_files_exist_for_every_manifest_entry(self):
        missing = []
        for spec in MANIFEST:
            path = Path(settings.BASE_DIR) / spec.app / "fixtures" / spec.fixture_file
            if not path.exists():
                missing.append(str(path))
        self.assertEqual(missing, [], f"Manifest entries without committed fixtures: {missing}")

    def test_load_reference_data_matches_committed_row_counts(self):
        call_command("load_reference_data", "--app=all", verbosity=0)
        mismatches = []
        for spec in MANIFEST:
            model = apps.get_model(spec.model)
            committed_path = Path(settings.BASE_DIR) / spec.app / "fixtures" / spec.fixture_file
            expected = len(json.loads(committed_path.read_text(encoding="utf-8")))
            actual = model.objects.count()
            if actual != expected:
                mismatches.append(f"{spec.model}: expected {expected}, got {actual}")
        self.assertEqual(mismatches, [], f"Row count drift after load: {mismatches}")

    def test_round_trip_dump_matches_committed_fixtures(self):
        call_command("load_reference_data", "--app=all", verbosity=0)
        with tempfile.TemporaryDirectory() as tmp:
            call_command(
                "dump_reference_data",
                f"--output-dir={tmp}",
                "--no-combined",
                "--force",
                verbosity=0,
            )
            drift = []
            for spec in MANIFEST:
                committed_path = Path(settings.BASE_DIR) / spec.app / "fixtures" / spec.fixture_file
                regenerated_path = Path(tmp) / spec.fixture_file
                if not committed_path.exists() or not regenerated_path.exists():
                    continue
                committed = json.loads(committed_path.read_text(encoding="utf-8"))
                regenerated = json.loads(regenerated_path.read_text(encoding="utf-8"))
                if committed != regenerated:
                    drift.append(spec.model)
        self.assertEqual(drift, [], f"Fixtures drifted from canonical dump: {drift}")
