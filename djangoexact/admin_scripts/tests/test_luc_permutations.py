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
