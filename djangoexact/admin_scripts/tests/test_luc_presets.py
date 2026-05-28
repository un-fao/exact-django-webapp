"""Tests for the LUC preset spec module."""
from django.test import TestCase

from admin_scripts.catalog.luc_presets import (
    LUC_PRESETS,
    Cycle,
    Fixed,
)


class LucPresetsContentTest(TestCase):
    databases = {"default"}

    def test_all_eight_luc_classes_have_at_least_one_template(self):
        expected_classes = {
            "AnnualCropland", "PerennialCropland", "FloodedRice",
            "ForestManagement", "Grassland", "Settlement",
            "SetAside", "OtherLand",
        }
        self.assertEqual(set(LUC_PRESETS.keys()), expected_classes)
        for class_name, templates in LUC_PRESETS.items():
            self.assertGreaterEqual(
                len(templates), 1,
                f"{class_name} must have at least one preset template",
            )

    def test_annual_cropland_templates_are_two_fixed_presets(self):
        templates = LUC_PRESETS["AnnualCropland"]
        self.assertEqual(len(templates), 2)
        t0, t1 = templates
        self.assertEqual(t0["tillage_management_type"], Fixed("Full Tillage"))
        self.assertEqual(t0["residue_management_type"], Fixed("Burned"))
        self.assertEqual(t1["tillage_management_type"], Fixed("No Tillage"))
        self.assertEqual(t1["residue_management_type"], Fixed("Exported"))

    def test_forest_management_template_has_destination_override(self):
        templates = LUC_PRESETS["ForestManagement"]
        self.assertEqual(len(templates), 1)
        t0 = templates[0]
        self.assertIsInstance(t0["forest_type"], Cycle)
        self.assertIsInstance(t0["forest_condition_type"], Cycle)
        overrides = t0["_destination_overrides"]
        self.assertEqual(
            overrides["forest_condition_type"],
            Cycle(filter={"name__in": ["Secondary"]}),
        )

    def test_perennial_cropland_uses_is_biomass_burned_boolean(self):
        templates = LUC_PRESETS["PerennialCropland"]
        self.assertEqual(len(templates), 2)
        self.assertEqual(templates[0]["is_biomass_burned"], Fixed(True))
        self.assertEqual(templates[1]["is_biomass_burned"], Fixed(False))

    def test_set_aside_and_other_land_templates_are_empty(self):
        self.assertEqual(LUC_PRESETS["SetAside"], [{}])
        self.assertEqual(LUC_PRESETS["OtherLand"], [{}])
