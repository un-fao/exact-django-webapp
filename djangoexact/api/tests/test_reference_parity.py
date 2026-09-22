"""Unit tests for the reference-data identity diff.

`SimpleTestCase` on purpose: `diff_reference_identity` is pure logic with no
Django dependency, so these run with no database.
"""

from django.test import SimpleTestCase

from api.reference_parity import diff_reference_identity


class DiffReferenceIdentityTests(SimpleTestCase):
    def test_identical_inputs_produce_an_empty_diff(self):
        rows = {1: ("Tropical",), 2: ("Boreal",)}

        diff = diff_reference_identity(rows, dict(rows), model="api.Climate")

        self.assertEqual(diff.changed, [])
        self.assertEqual(diff.missing_in_db, [])
        self.assertEqual(diff.extra_in_db, [])
        self.assertTrue(diff.is_clean)
        self.assertFalse(diff.is_fatal)
        self.assertEqual(diff.model, "api.Climate")

    def test_changed_identity_on_a_shared_pk_is_fatal(self):
        fixture = {50: ("Annual Cropland Minor Season",)}
        db = {50: ("Plantation",)}

        diff = diff_reference_identity(fixture, db, model="api.ModuleType")

        self.assertEqual(
            diff.changed,
            [(50, ("Annual Cropland Minor Season",), ("Plantation",))],
        )
        self.assertEqual(diff.missing_in_db, [])
        self.assertEqual(diff.extra_in_db, [])
        self.assertTrue(diff.is_fatal)

    def test_pk_only_in_fixtures_is_missing_in_db(self):
        diff = diff_reference_identity({1: ("A",), 2: ("B",)}, {1: ("A",)})

        self.assertEqual(diff.missing_in_db, [2])
        self.assertEqual(diff.changed, [])
        self.assertEqual(diff.extra_in_db, [])
        self.assertFalse(diff.is_fatal)

    def test_pk_only_in_db_is_extra_in_db(self):
        diff = diff_reference_identity({1: ("A",)}, {1: ("A",), 9: ("Z",)})

        self.assertEqual(diff.extra_in_db, [9])
        self.assertEqual(diff.changed, [])
        self.assertEqual(diff.missing_in_db, [])
        self.assertFalse(diff.is_fatal)

    def test_matching_pk_appears_in_no_category(self):
        diff = diff_reference_identity(
            {1: ("A",), 2: ("B",)},
            {1: ("A",), 3: ("C",)},
        )

        self.assertNotIn(1, [pk for pk, _fixture, _db in diff.changed])
        self.assertNotIn(1, diff.missing_in_db)
        self.assertNotIn(1, diff.extra_in_db)
        self.assertEqual(diff.missing_in_db, [2])
        self.assertEqual(diff.extra_in_db, [3])

    def test_categories_are_reported_together_and_sorted(self):
        fixture = {1: ("A",), 2: ("B",), 4: ("D",)}
        db = {1: ("A",), 2: ("changed",), 3: ("C",)}

        diff = diff_reference_identity(fixture, db, model="api.SoilType")

        self.assertEqual(diff.changed, [(2, ("B",), ("changed",))])
        self.assertEqual(diff.missing_in_db, [4])
        self.assertEqual(diff.extra_in_db, [3])
        self.assertFalse(diff.is_clean)
        self.assertTrue(diff.is_fatal)

    def test_composite_identity_tuples_compare_elementwise(self):
        fixture = {1: ("Diesel", "Stationary", "Fossil")}
        db = {1: ("Diesel", "Mobile", "Fossil")}

        diff = diff_reference_identity(fixture, db, model="api.FuelType")

        self.assertTrue(diff.is_fatal)
        self.assertEqual(diff.changed[0][0], 1)

    def test_as_dict_is_json_shaped(self):
        diff = diff_reference_identity({1: ("A",)}, {1: ("B",), 2: ("C",)}, model="api.Unit")

        payload = diff.as_dict()

        self.assertEqual(payload["model"], "api.Unit")
        self.assertEqual(payload["changed"], [{"pk": 1, "fixture": ["A"], "db": ["B"]}])
        self.assertEqual(payload["extra_in_db"], [2])
        self.assertEqual(payload["missing_in_db"], [])
        self.assertTrue(payload["fatal"])
