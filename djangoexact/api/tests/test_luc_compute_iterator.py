"""Tests for iterate_concrete_combos in luc_compute."""
from django.test import TestCase

from api.services.luc_compute import iterate_concrete_combos


class IterateConcreteCombosTest(TestCase):
    databases = {"default"}

    def test_two_fixed_presets_yield_single_pair(self):
        # AnnualCropland template 0 (single Fixed combo) on both sides.
        pairs = list(iterate_concrete_combos(
            ("AnnualCropland", 0), ("AnnualCropland", 0),
        ))
        self.assertEqual(len(pairs), 1)
        start_values, w_values = pairs[0]
        self.assertEqual(str(start_values["tillage_management_type"]), "Full Tillage")
        self.assertEqual(str(w_values["tillage_management_type"]), "Full Tillage")

    def test_cycle_on_w_side_expands_to_n_pairs(self):
        # ForestManagement template 0 on w side: 2 forest_types x 1 condition
        # (Secondary, via destination override) = 2 combos. Start side is
        # AnnualCropland template 0 (1 combo). Pairs = 1 * 2 = 2.
        pairs = list(iterate_concrete_combos(
            ("AnnualCropland", 0), ("ForestManagement", 0),
        ))
        self.assertEqual(len(pairs), 2)
        for _, w in pairs:
            self.assertEqual(str(w["forest_condition_type"]), "Secondary")

    def test_same_class_self_pair_iterates_full_cartesian_product(self):
        # ForestManagement on both sides: start has 4 combos, w has 2 (after
        # afforestation override) = 4 * 2 = 8 pairs.
        pairs = list(iterate_concrete_combos(
            ("ForestManagement", 0), ("ForestManagement", 0),
        ))
        self.assertEqual(len(pairs), 8)
