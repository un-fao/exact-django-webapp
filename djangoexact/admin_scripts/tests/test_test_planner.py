"""Tests for admin_scripts.test_planner.

The planner is pure (no Django request layer), but _resolve_value_source
queries Django models, so we use TestCase to get a DB.
"""
from unittest.mock import patch

from django.test import TestCase

from admin_scripts.catalog import CatalogField, CatalogModule
from admin_scripts.test_planner import plan_module_tests


def _module(module_type, fields):
    return CatalogModule(
        module_type=module_type, label=module_type, config_name=module_type.lower(),
        fields=fields,
    )


def _field(name, value_source):
    return CatalogField(field_name=name, label=name, value_source=value_source)


class PlanModuleTestsTest(TestCase):
    databases = {"default"}

    def test_plans_one_entry_per_testable_field(self):
        catalog = [_module("Grassland", [
            _field("is_fire_used", {"kind": "static", "values": [True, False]}),
            _field("fire_impact", {"kind": "static", "values": [1, 0]}),
        ])]
        planned, skipped = plan_module_tests(catalog)
        self.assertEqual(len(planned), 2)
        self.assertEqual(skipped, [])
        self.assertEqual(planned[0], {
            "module_type": "Grassland",
            "field_name": "is_fire_used",
            "from_value": "True",
            "to_value": "False",
        })
        self.assertEqual(planned[1], {
            "module_type": "Grassland",
            "field_name": "fire_impact",
            "from_value": "1",
            "to_value": "0",
        })

    def test_skips_single_value_static_field(self):
        catalog = [_module("Grassland", [
            _field("fire_periodicity", {"kind": "static", "values": [1]}),
        ])]
        planned, skipped = plan_module_tests(catalog)
        self.assertEqual(planned, [])
        self.assertEqual(skipped, [{
            "module_type": "Grassland",
            "field_name": "fire_periodicity",
            "reason": "only 1 distinct value(s) available",
        }])

    def test_skips_empty_queryset(self):
        catalog = [_module("Grassland", [
            _field("grassland_management_type", {
                "kind": "queryset", "model": "GrasslandManagementType",
            }),
        ])]
        with patch(
            "admin_scripts.test_planner._resolve_value_source", return_value=[]
        ):
            planned, skipped = plan_module_tests(catalog)
        self.assertEqual(planned, [])
        self.assertEqual(skipped[0]["reason"], "no values available")

    def test_deduplicates_while_preserving_order(self):
        catalog = [_module("M", [
            _field("f", {"kind": "static", "values": ["A", "A", "B", "B"]}),
        ])]
        planned, skipped = plan_module_tests(catalog)
        self.assertEqual(skipped, [])
        self.assertEqual(planned[0]["from_value"], "A")
        self.assertEqual(planned[0]["to_value"], "B")

    def test_preserves_module_order(self):
        catalog = [
            _module("Alpha", [_field("a", {"kind": "static", "values": [1, 2]})]),
            _module("Beta",  [_field("b", {"kind": "static", "values": [3, 4]})]),
        ]
        planned, _ = plan_module_tests(catalog)
        self.assertEqual(planned[0]["module_type"], "Alpha")
        self.assertEqual(planned[1]["module_type"], "Beta")
