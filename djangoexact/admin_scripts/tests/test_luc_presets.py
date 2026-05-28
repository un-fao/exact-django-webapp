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


from admin_scripts.luc_permutations import Side, expand_preset


class ExpandPresetStartSideTest(TestCase):
    databases = {"default"}

    def test_annual_cropland_template_0_expands_to_single_concrete_combo(self):
        combos = expand_preset("AnnualCropland", 0, Side.START)
        self.assertEqual(len(combos), 1)
        c = combos[0]
        # FK values come back as model instances; check their string form.
        self.assertEqual(str(c["land_use_type"]), "Default")
        self.assertEqual(str(c["tillage_management_type"]), "Full Tillage")
        self.assertEqual(str(c["organic_input_type"]), "Low C input")
        self.assertEqual(str(c["residue_management_type"]), "Burned")

    def test_grassland_template_1_has_correct_management_type(self):
        combos = expand_preset("Grassland", 1, Side.START)
        self.assertEqual(len(combos), 1)
        self.assertEqual(
            str(combos[0]["grassland_management_type"]),
            "Improved With High Inputs",
        )

    def test_forest_management_start_side_cycles_all_combinations(self):
        # 2 forest_types (Natural, Plantation) x 2 conditions (Primary, Secondary)
        combos = expand_preset("ForestManagement", 0, Side.START)
        self.assertEqual(len(combos), 4)
        condition_names = {str(c["forest_condition_type"]) for c in combos}
        self.assertEqual(condition_names, {"Primary", "Secondary"})

    def test_set_aside_and_other_land_expand_to_single_empty_combo(self):
        self.assertEqual(expand_preset("SetAside", 0, Side.START), [{}])
        self.assertEqual(expand_preset("OtherLand", 0, Side.START), [{}])

    def test_perennial_cycle_lands_on_perennial_filtered_luts(self):
        combos = expand_preset("PerennialCropland", 0, Side.START)
        # PerennialCropland's MODULE_CONFIGS filters land_use_type to
        # ``module_types__name="Perennial Cropland"``; the expansion must
        # use that filtered queryset (not the unfiltered LandUseType.all()).
        from api.minitool import MODULE_CONFIGS
        expected_names = {
            str(o) for o in MODULE_CONFIGS["PerennialCropland"]["fields"]["land_use_type_start"]
        }
        actual_names = {str(c["land_use_type"]) for c in combos}
        self.assertEqual(actual_names, expected_names)
        # Other fields stay fixed.
        for c in combos:
            self.assertEqual(str(c["tillage_management_type"]), "Full Tillage")
            self.assertEqual(c["is_biomass_burned"], True)


class ExpandPresetDestinationOverrideTest(TestCase):
    databases = {"default"}

    def test_forest_management_w_side_restricts_to_secondary(self):
        # Without override: 2 forest_types x 2 conditions = 4 combos.
        # With override: 2 forest_types x 1 condition (Secondary) = 2 combos.
        combos = expand_preset("ForestManagement", 0, Side.W)
        self.assertEqual(len(combos), 2)
        for c in combos:
            self.assertEqual(str(c["forest_condition_type"]), "Secondary")

    def test_destination_override_does_not_leak_to_start_side(self):
        start_combos = expand_preset("ForestManagement", 0, Side.START)
        conditions = {str(c["forest_condition_type"]) for c in start_combos}
        self.assertEqual(conditions, {"Primary", "Secondary"})
