"""DB-free tests for import_uncertainties (see conftest.py -- SimpleTestCase only,
no `databases` attribute, so these run safely under bare pytest and manage.py test)."""

import json
import math
import os
import tempfile
from io import StringIO
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
os.environ.setdefault("DJANGO_DEBUG", "True")
django.setup()

from django.core.management import call_command  # noqa: E402
from django.test import SimpleTestCase  # noqa: E402

from ipcc.management.commands import import_uncertainties as iu  # noqa: E402
from ipcc.management.commands.apply_uncertainty_ranges import plan_writes  # noqa: E402


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


class FixtureWriterTests(SimpleTestCase):
    """Proves the writer's D-01/D-03 guarantees against the fixtures already on disk
    (this test suite runs after `manage.py import_uncertainties` has patched them)."""

    def test_combined_fixture_matches_per_model_fixtures(self):
        combined = []
        for spec in iu.MANIFEST:
            with open(iu.fixture_path(spec), encoding="utf-8") as fh:
                combined.extend(json.load(fh))
        combined_path = Path(iu.settings.BASE_DIR) / "api" / "fixtures" / "all_reference_data.json"
        with open(combined_path, encoding="utf-8") as fh:
            actual = json.load(fh)
        self.assertEqual(combined, actual)

    def test_patch_only_touches_new_keys(self):
        """Strips the on-disk fixture back to its pre-patch shape (works whether or
        not this run already patched it), copies that reconstruction to a temp dir,
        and asserts re-running the patch reproduces the current on-disk file exactly --
        proving the patch only ever adds the new `_min`/`_max` keys."""
        manifest_by_fixture = {spec.fixture_file: spec for spec in iu.MANIFEST}
        cases = [("CoastalBGB.csv", "coastalbgb.json"), ("GrasslandAGB.csv", "grasslandbiomass.json")]
        for csv_name, fixture_file in cases:
            spec = manifest_by_fixture[fixture_file]
            with open(iu.fixture_path(spec), encoding="utf-8") as fh:
                current = json.load(fh)

            csv_path = iu.data_dir() / csv_name
            model = iu.django_apps.get_model(spec.model)
            field_map = {f.name: f for f in model._meta.concrete_fields}
            name_to_index, _rows = iu.read_csv_rows(csv_path)
            groups, _names_used = iu.compute_ranged_groups(csv_path, name_to_index, field_map)
            new_columns = set(iu.new_columns_for_groups(groups))

            stripped_original = [
                {
                    "model": row["model"],
                    "pk": row["pk"],
                    "fields": {k: v for k, v in row["fields"].items() if k not in new_columns},
                }
                for row in current
            ]

            with tempfile.TemporaryDirectory() as tmp:
                tmp_copy = Path(tmp) / fixture_file
                tmp_copy.write_text(json.dumps(stripped_original), encoding="utf-8")
                fixture_cache = {fixture_file: json.loads(tmp_copy.read_text(encoding="utf-8"))}
                _tables, results = iu.compute_all([csv_path], fixture_cache)
                _spec, patches, groups2, _base_values = results[fixture_file]
                patched = iu.apply_patches(spec, patches, groups2, fixture_cache)

            self.assertEqual(patched, current, f"{csv_name}: re-patching the stripped fixture didn't reproduce the current one")

    def test_base_values_agree_on_written_rows(self):
        """Restricted to the ten largest CSVs (by file size) to keep runtime well
        under the ~60s cap for the plan's 58k-row full pass; the join code path is
        identical regardless of how many CSVs are given."""
        csv_paths = sorted(iu.data_dir().glob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)[:10]
        _tables, results = iu.compute_all(csv_paths, {})
        checked = 0
        for spec, _patches, _groups, base_values in results.values():
            fixture_by_pk = {row["pk"]: row["fields"] for row in iu.load_fixture(spec, {})}
            for pk, fields_at_pk in base_values.items():
                fixture_fields = fixture_by_pk[pk]
                for model_field, csv_val in fields_at_pk.items():
                    fixture_val = fixture_fields[model_field]
                    if not isinstance(fixture_val, (int, float)) or isinstance(fixture_val, bool):
                        continue  # matches process_csv's own gate: nothing comparable, nothing to prove
                    self.assertTrue(
                        math.isclose(csv_val, fixture_val, rel_tol=1e-6, abs_tol=1e-9),
                        f"{spec.model} pk={pk} {model_field}: csv={csv_val} fixture={fixture_val}",
                    )
                    checked += 1
        self.assertGreater(checked, 0)

    def test_committed_fixtures_carry_bounds_only_for_published_tables(self):
        report = json.loads((iu.data_dir() / "import_report.json").read_text(encoding="utf-8"))
        published = {t["model"] for t in report["tables"] if t["published"]}
        for spec, model, column in iu.iter_mapped_columns():
            if spec.model in published:
                continue
            with open(iu.fixture_path(spec), encoding="utf-8") as fh:
                bounded = [row["pk"] for row in json.load(fh) if row["fields"].get(column) is not None]
            self.assertEqual(bounded, [], f"{spec.model}.{column} is unpublished but carries bounds")

    def test_report_matches_committed_baseline(self):
        report_path = str(iu.data_dir() / "import_report.json")
        try:
            call_command("import_uncertainties", "--dry-run", "--check", report_path, stdout=StringIO())
        except iu.CommandError as exc:
            self.fail(f"report does not match committed baseline: {exc}")


class PublishRuleTests(SimpleTestCase):
    """The join against a tiny in-memory source: which rows count as issues, and that one
    issue holds the whole table back."""

    AMENDMENT_FIXTURE = next(s.fixture_file for s in iu.MANIFEST if s.model == "api.OrganicAmendmentType")

    def join(self, csv_rows, fixture_values, amendment_names=None):
        amendment_names = amendment_names or {3: "Straw", 4: "Compost"}
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "ipcc.ricesfo.csv"
            lines = ["id,organic_amendment_type,value,value_min,value_max", *csv_rows]
            csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            cache = {
                self.AMENDMENT_FIXTURE: [
                    {"model": "api.organicamendmenttype", "pk": pk, "fields": {"name": name}}
                    for pk, name in amendment_names.items()
                ],
                "ricesfo.json": [
                    {"model": "ipcc.ricesfo", "pk": 70 + amendment, "fields": {"organic_amendment_type": amendment, "value": value}}
                    for amendment, value in fixture_values.items()
                ],
            }
            tables, results = iu.compute_all([csv_path], cache)
        return tables[0], results["ricesfo.json"][1]

    def test_matching_rows_publish_their_bounds(self):
        table, patches = self.join(["1,Straw,1.0,0.5,1.5"], {3: 1.0})
        self.assertTrue(table["published"])
        self.assertEqual(patches, {73: {"value_min": 0.5, "value_max": 1.5}})

    def test_empty_base_value_is_a_base_mismatch(self):
        table, patches = self.join(["1,Straw,1.0,0.5,1.5"], {3: None})
        self.assertEqual(table["base_mismatch"], 1)
        self.assertFalse(table["published"])
        self.assertEqual(patches, {})

    def test_name_shared_by_two_rows_stays_unresolved(self):
        table, patches = self.join(["1,Straw,1.0,0.5,1.5"], {3: 1.0, 4: 1.0}, {3: "Straw", 4: "Straw"})
        self.assertEqual((table["unresolved_fk"], table["written"]), (1, 0))
        self.assertEqual(patches, {})

    def test_one_skipped_row_holds_back_the_whole_table(self):
        table, patches = self.join(["1,Straw,1.0,0.5,1.5", "2,Compost,2.0,1.0,3.0"], {3: 1.0, 4: 9.9})
        self.assertEqual((table["written"], table["base_mismatch"]), (1, 1))
        self.assertFalse(table["published"])
        self.assertEqual(patches, {})


class PlanWritesTests(SimpleTestCase):
    def test_fills_only_empty_columns_and_never_writes_null(self):
        current = {1: {"value_min": None, "value_max": 2.0}, 2: {"value_min": 0.5, "value_max": None}}
        patches = {1: {"value_min": 0.1, "value_max": 2.0}, 2: {"value_min": 0.7, "value_max": None}}
        writes, conflicts = plan_writes(current, patches)
        self.assertEqual(writes, {1: {"value_min": 0.1}})
        self.assertEqual(conflicts, [(2, "value_min", 0.5, 0.7)])
