"""Whole-database foreign key integrity for the committed reference fixtures.

`test_reference_bootstrap.py` already fails if `load_reference_data` cannot load
a fixture, because `loaddata` runs `connection.check_constraints()` per fixture
file. That is strict, but it is scoped to the tables each individual fixture
touches. This module adds the complementary check: after the whole manifest is
loaded, assert that NOT ONE row anywhere in the database has a dangling foreign
key, whether it arrived via a fixture or via a data migration.

Regression guard for the orphaned `ipcc.CropNitrousEstimationDefaultFactor`
row (pk 179) whose `land_use_type` pointed at `api.LandUseType` pk 29
("Generic Value"), removed from `landusetype.json` by commit c2155bec4 on
2026-04-29. It survived two months undetected because `loaddata` upserts and
never deletes: every pre-existing database still physically held pk 29, so its
foreign key resolved. Only a from-scratch database dangled, and the only thing
that builds one is the offline Electron seed (`electron/scripts/seed_db.py`),
which is exercised at release time rather than on a pull request.
"""

from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase


class ReferenceFixtureForeignKeyIntegrityTests(TransactionTestCase):
    serialized_rollback = False
    # Same rationale as ReferenceDataBootstrapTests: scope flush() to the apps
    # the manifest owns, so teardown does not try to TRUNCATE Wagtail/auth
    # tables whose inbound FKs would need `TRUNCATE ... CASCADE`.
    available_apps = ["api", "ipcc"]

    def test_reference_data_leaves_no_dangling_foreign_keys(self):
        call_command("load_reference_data", "--app=all", verbosity=0)

        if connection.vendor != "sqlite":
            # PostgreSQL enforces these constraints itself: loaddata defers them
            # and the deferred check fires at commit, so a dangling key would
            # already have blown up in the call above.
            connection.check_constraints()
            return

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_key_check")
            violations = cursor.fetchall()

        self.assertEqual(violations, [], self._describe(violations))

    def _describe(self, violations):
        """Turn PRAGMA rows into something a reader can act on.

        Each row is (child_table, child_rowid, parent_table, fk_index). The
        offending column name lives in `PRAGMA foreign_key_list(child_table)`
        at position `fk_index`.
        """
        if not violations:
            return ""
        lines = ["Reference fixtures produced dangling foreign keys:"]
        with connection.cursor() as cursor:
            for child_table, child_rowid, parent_table, fk_index in violations:
                cursor.execute(f"PRAGMA foreign_key_list({child_table})")
                fks = {row[0]: row for row in cursor.fetchall()}
                fk = fks.get(fk_index)
                column = fk[3] if fk else "?"
                value = "?"
                if column != "?":
                    cursor.execute(
                        f"SELECT {column} FROM {child_table} WHERE rowid = %s",
                        [child_rowid],
                    )
                    row = cursor.fetchone()
                    if row:
                        value = row[0]
                lines.append(
                    f"  {child_table}.{column} = {value} "
                    f"(rowid {child_rowid}) has no matching {parent_table} row"
                )
        return "\n".join(lines)
