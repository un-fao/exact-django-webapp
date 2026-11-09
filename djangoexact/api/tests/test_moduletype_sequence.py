"""api/0320 resets the ModuleType id sequence after 0316 inserted Solid Waste with an explicit pk=65.

Postgres does not advance a sequence on explicit-id inserts, so on a database whose
sequence was below 65 the next ModuleType created without an id collided with the
Solid Waste row (duplicate key on api_moduletype_pkey).
"""

from importlib import import_module

from django.apps import apps
from django.db import connection
from django.db.models import Max
from django.test import TestCase

from api.models import ModuleType


class ModuleTypeSequenceTestCase(TestCase):
    def test_create_without_pk_does_not_collide_with_solid_waste(self):
        module_type = ModuleType.objects.create(name="Sequence probe", class_name=None)
        self.assertGreater(module_type.pk, 65)

    def test_migration_moves_sequence_past_max_id(self):
        if connection.vendor != "postgresql":
            self.skipTest("sequence state is Postgres-specific")
        migration = import_module("api.migrations.0320_reset_moduletype_sequence")
        table = ModuleType._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), 1)", [table])
            migration.reset_moduletype_sequence(apps, connection.schema_editor())
            cursor.execute(f"SELECT last_value FROM {connection.ops.quote_name(table + '_id_seq')}")
            last_value = cursor.fetchone()[0]
        self.assertGreaterEqual(last_value, ModuleType.objects.aggregate(Max("id"))["id__max"])
