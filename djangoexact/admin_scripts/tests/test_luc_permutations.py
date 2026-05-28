"""Tests for the LUC permutation planner helpers."""
from django.test import SimpleTestCase

from admin_scripts.luc_permutations import (
    format_identifier,
    list_preset_templates,
    parse_identifier,
)


class ListPresetTemplatesTest(SimpleTestCase):
    def test_returns_one_tuple_per_template(self):
        # 2+2+2+1+2+1+1+1 = 12 templates across the 8 LUC classes.
        result = list_preset_templates()
        self.assertEqual(len(result), 12)

    def test_each_entry_is_class_name_and_zero_based_index(self):
        result = list_preset_templates()
        # AnnualCropland has 2 templates -> indices 0 and 1 must both appear.
        ac_indices = sorted(idx for cls, idx in result if cls == "AnnualCropland")
        self.assertEqual(ac_indices, [0, 1])
        sa_indices = [idx for cls, idx in result if cls == "SetAside"]
        self.assertEqual(sa_indices, [0])


class IdentifierRoundtripTest(SimpleTestCase):
    def test_format_then_parse_yields_original_tuple(self):
        ident = format_identifier("AnnualCropland", 1)
        self.assertEqual(ident, "AnnualCropland#1")
        self.assertEqual(parse_identifier(ident), ("AnnualCropland", 1))

    def test_parse_rejects_bad_format(self):
        with self.assertRaises(ValueError):
            parse_identifier("AnnualCropland")
        with self.assertRaises(ValueError):
            parse_identifier("AnnualCropland#not_an_int")


from admin_scripts.luc_permutations import plan_luc_pairs


class PlanLucPairsTest(SimpleTestCase):
    def test_emits_one_entry_per_directed_template_pair(self):
        entries = plan_luc_pairs()
        # 12 templates -> 12 * 12 = 144 directed pairs (self-pairs included).
        self.assertEqual(len(entries), 144)

    def test_each_entry_has_planner_shape(self):
        entries = plan_luc_pairs()
        for e in entries:
            self.assertEqual(set(e.keys()),
                             {"module_type", "field_name", "from_value", "to_value"})
            self.assertEqual(e["module_type"], "LandUseChange")
            self.assertEqual(e["field_name"], "module_type")

    def test_first_entry_is_first_template_to_itself(self):
        entries = plan_luc_pairs()
        # First template is AnnualCropland#0 (insertion order of LUC_PRESETS).
        self.assertEqual(entries[0]["from_value"], "AnnualCropland#0")
        self.assertEqual(entries[0]["to_value"], "AnnualCropland#0")

    def test_no_duplicate_pairs(self):
        entries = plan_luc_pairs()
        pairs = [(e["from_value"], e["to_value"]) for e in entries]
        self.assertEqual(len(pairs), len(set(pairs)))
