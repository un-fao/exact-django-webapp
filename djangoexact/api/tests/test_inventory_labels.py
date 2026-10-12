"""Database-free unit tests for api.inventory_labels.

Deliberately imports only `unittest` and the three names under test: no
Django, no models, no math_model. Runnable with plain
`python -m unittest api.tests.test_inventory_labels`, with no settings
configured and no database.
"""

import unittest

from api.inventory_labels import DEFAULT_LABELS, MODULE_OVERRIDES, inventory_label


class AnnualCropland:
    pass


class Aquaculture:
    pass


class Input:
    pass


class InventoryLabelTests(unittest.TestCase):
    def setUp(self):
        self.fake_annual_cropland = AnnualCropland()
        self.fake_aquaculture = Aquaculture()
        self.fake_input_module = Input()

    def test_default_mapping_hit(self):
        self.assertEqual(
            inventory_label(self.fake_annual_cropland, "Soil CO2 Change"),
            "Soil Carbon stocks (SOC)",
        )

    def test_unmapped_category_passes_through_unchanged(self):
        self.assertEqual(
            inventory_label(self.fake_annual_cropland, "Residues Burning"),
            "Residues Burning",
        )

    def test_aquaculture_override_n2o_field(self):
        self.assertEqual(
            inventory_label(self.fake_aquaculture, "N2O Field"),
            "FISH EMISSION (EXCRETA)",
        )

    def test_aquaculture_override_electricity(self):
        self.assertEqual(
            inventory_label(self.fake_aquaculture, "Electricity"),
            "Electricity emissions (CO2-eq)",
        )

    def test_override_is_aquaculture_only(self):
        self.assertEqual(
            inventory_label(self.fake_input_module, "N2O Field"),
            "N2O Field",
        )
        self.assertEqual(
            inventory_label(self.fake_input_module, "Electricity"),
            "Electricity",
        )

    def test_overridden_module_still_gets_defaults_for_other_categories(self):
        self.assertEqual(
            inventory_label(self.fake_aquaculture, "Biomass"),
            "Biomass Carbon stock",
        )

    def test_produced_labels_are_disjoint_from_mapping_keys(self):
        keys = set(DEFAULT_LABELS.keys())
        values = set(DEFAULT_LABELS.values())
        for overrides in MODULE_OVERRIDES.values():
            keys |= set(overrides.keys())
            values |= set(overrides.values())

        self.assertEqual(
            keys & values,
            set(),
            "A mapping key also appears as a produced label; a second pass "
            "of the mapping would not be a no-op.",
        )

    def test_idempotent_for_every_key_on_plain_module(self):
        for key in DEFAULT_LABELS:
            once = inventory_label(self.fake_annual_cropland, key)
            twice = inventory_label(self.fake_annual_cropland, once)
            self.assertEqual(once, twice)

    def test_idempotent_for_every_key_on_aquaculture_module(self):
        all_keys = set(DEFAULT_LABELS.keys())
        for overrides in MODULE_OVERRIDES.values():
            all_keys |= set(overrides.keys())

        for key in all_keys:
            once = inventory_label(self.fake_aquaculture, key)
            twice = inventory_label(self.fake_aquaculture, once)
            self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
