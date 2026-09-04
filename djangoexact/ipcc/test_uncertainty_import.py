"""DB-free tests for import_uncertainties (see conftest.py -- SimpleTestCase only,
no `databases` attribute, so these run safely under bare pytest and manage.py test)."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
os.environ.setdefault("DJANGO_DEBUG", "True")
django.setup()

from django.test import SimpleTestCase  # noqa: E402

from ipcc.management.commands import import_uncertainties as iu  # noqa: E402


class SchemaSyncTests(SimpleTestCase):
    """Keeps models.py and the command's mapping table from drifting apart: every
    column the mapping table derives must exist on its model as a nullable FloatField,
    and no new column name may collide with an existing ranged base field."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mapped_columns = list(iu.iter_mapped_columns())

        manifest_by_fixture = {spec.fixture_file: spec for spec in iu.MANIFEST}
        cls.base_fields_by_model = {}
        for csv_path in sorted(iu.data_dir().glob("*.csv")):
            name = iu.resolve_fixture_name(csv_path)
            spec = manifest_by_fixture[f"{name}.json"]
            model = iu.django_apps.get_model(spec.model)
            field_map = {f.name: f for f in model._meta.concrete_fields}
            name_to_index, _rows = iu.read_csv_rows(csv_path)
            groups, _names_used = iu.compute_ranged_groups(csv_path, name_to_index, field_map)
            cls.base_fields_by_model.setdefault(model, set()).update(groups)

    def test_every_mapped_column_exists_on_its_model(self):
        for spec, model, column in self.mapped_columns:
            field = next((f for f in model._meta.concrete_fields if f.name == column), None)
            self.assertIsNotNone(field, f"{spec.model}.{column} is not a concrete field")
            self.assertEqual(field.get_internal_type(), "FloatField", f"{spec.model}.{column}")
            self.assertTrue(field.null, f"{spec.model}.{column} must be null=True")

    def test_no_base_field_was_turned_nullable(self):
        for spec, model, column in self.mapped_columns:
            base_fields = self.base_fields_by_model.get(model, set())
            self.assertNotIn(
                column, base_fields,
                f"{spec.model}.{column} collides with a ranged base field -- would silently retype it",
            )
