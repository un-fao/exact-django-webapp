from pathlib import Path

from django.test import SimpleTestCase
from io import StringIO
from types import ModuleType
from unittest.mock import patch, MagicMock
import sys
import yaml
import tempfile
import os

from django.core.management import call_command

from admin_scripts.catalog import (
    CatalogModule,
    CatalogField,
    load_catalog,
    validate_catalog,
    ValidationError,
    get_catalog,
)


def _make_qs_mock(model_name: str) -> MagicMock:
    """Create a MagicMock that behaves like a Django QuerySet."""
    mock = MagicMock()
    mock.model.__name__ = model_name
    # Ensure isinstance(value, list) returns False
    mock.__class__ = type("QuerySet", (), {})
    return mock


MOCK_MODULE_CONFIGS = {
    "Grassland": {
        "fields": {
            "grassland_management_type_start": _make_qs_mock(
                "GrasslandManagementType"
            ),
            "grassland_management_type_w": _make_qs_mock(
                "GrasslandManagementType"
            ),
            "is_fire_used_start": [True, False],
            "is_fire_used_w": [True, False],
        },
        "config_name": "grassland",
    },
    "ForestManagement": {
        "fields": {
            "forest_type": _make_qs_mock("ForestType"),
            "forest_condition_type": _make_qs_mock("ForestConditionType"),
            "average_yearly_degradation_percentage_start": [0],
            "average_yearly_degradation_percentage_w": [0.01, 0.02],
        },
        "config_name": "forest_management",
    },
    "CoastalWetland": {
        "fields": {
            "land_use_type": _make_qs_mock("LandUseType"),
            "area_under_drainage_start": [1, 0],
            "area_under_drainage_w": [1, 0],
        },
        "config_name": "coastal_wetland",
    },
    "CoastalWetland2": {
        "fields": {
            "land_use_type": _make_qs_mock("LandUseType"),
            "area_under_drainage_start": [0],
            "area_under_drainage_w": [0],
        },
        "config_name": "coastal_wetland",
    },
}

_fake_minitool = ModuleType("api.minitool")
_fake_minitool.MODULE_CONFIGS = MOCK_MODULE_CONFIGS


VALID_YAML = """
modules:
  - module_type: Grassland
    label: Grassland Management
    config_name: grassland
    fields:
      - field_name: grassland_management_type
        label: Management Type
        value_source:
          kind: queryset
          model: GrasslandManagementType
      - field_name: is_fire_used
        label: Fire Used
        value_source:
          kind: static
          values: [true, false]
"""

INVALID_MODULE_TYPE_YAML = """
modules:
  - module_type: NonExistentModule
    label: Fake
    config_name: fake
    fields: []
"""

INVALID_FIELD_YAML = """
modules:
  - module_type: Grassland
    label: Grassland
    config_name: grassland
    fields:
      - field_name: totally_fake_field
        label: Fake
        value_source:
          kind: static
          values: [1, 2]
"""


def load_catalog_from_string(yaml_string):
    data = yaml.safe_load(yaml_string)
    return [CatalogModule.from_dict(m) for m in data.get("modules", [])]


class CatalogDataclassTest(SimpleTestCase):

    def test_catalog_module_from_dict(self):
        data = yaml.safe_load(VALID_YAML)["modules"][0]
        module = CatalogModule.from_dict(data)
        self.assertEqual(module.module_type, "Grassland")
        self.assertEqual(module.label, "Grassland Management")
        self.assertEqual(module.config_name, "grassland")
        self.assertEqual(len(module.fields), 2)

    def test_catalog_field_from_dict(self):
        data = yaml.safe_load(VALID_YAML)["modules"][0]["fields"][0]
        field = CatalogField.from_dict(data)
        self.assertEqual(field.field_name, "grassland_management_type")
        self.assertEqual(field.value_source["kind"], "queryset")

    def test_catalog_field_missing_field_name_raises(self):
        data = {"label": "No name", "value_source": {"kind": "static", "values": [1]}}
        with self.assertRaises(KeyError):
            CatalogField.from_dict(data)


class LoadCatalogTest(SimpleTestCase):

    def test_load_catalog_parses_valid_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(VALID_YAML)
            f.flush()
            try:
                modules = load_catalog(f.name)
                self.assertEqual(len(modules), 1)
                self.assertIsInstance(modules[0], CatalogModule)
            finally:
                os.unlink(f.name)

    def test_load_catalog_empty_file_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            try:
                with self.assertRaises(ValidationError):
                    load_catalog(f.name)
            finally:
                os.unlink(f.name)

    def test_load_catalog_missing_modules_key_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("something_else: true\n")
            f.flush()
            try:
                with self.assertRaises(ValidationError):
                    load_catalog(f.name)
            finally:
                os.unlink(f.name)


@patch.dict(sys.modules, {"api.minitool": _fake_minitool})
class ValidateCatalogTest(SimpleTestCase):

    def test_valid_catalog_passes(self):
        modules = load_catalog_from_string(VALID_YAML)
        errors = validate_catalog(modules)
        self.assertEqual(errors, [])

    def test_invalid_module_type_caught(self):
        modules = load_catalog_from_string(INVALID_MODULE_TYPE_YAML)
        errors = validate_catalog(modules)
        self.assertTrue(any("NonExistentModule" in e for e in errors))

    def test_invalid_field_name_caught(self):
        modules = load_catalog_from_string(INVALID_FIELD_YAML)
        errors = validate_catalog(modules)
        self.assertTrue(any("totally_fake_field" in e for e in errors))


@patch.dict(sys.modules, {"api.minitool": _fake_minitool})
class ScaffoldCatalogCommandTest(SimpleTestCase):

    def test_command_outputs_valid_yaml(self):
        out = StringIO()
        call_command("scaffold_scenario_catalog", stdout=out)
        output = out.getvalue()
        data = yaml.safe_load(output)
        self.assertIn("modules", data)
        self.assertGreater(len(data["modules"]), 0)

    def test_command_output_passes_validation(self):
        out = StringIO()
        call_command("scaffold_scenario_catalog", stdout=out)
        data = yaml.safe_load(out.getvalue())
        modules = [CatalogModule.from_dict(m) for m in data["modules"]]
        errors = validate_catalog(modules)
        self.assertEqual(errors, [], f"Scaffold output has validation errors: {errors}")

    def test_each_module_has_at_least_one_field(self):
        out = StringIO()
        call_command("scaffold_scenario_catalog", stdout=out)
        data = yaml.safe_load(out.getvalue())
        for mod in data["modules"]:
            self.assertGreater(
                len(mod.get("fields", [])), 0,
                f"Module {mod['module_type']} has no fields",
            )

    def test_duplicate_config_name_skipped(self):
        out = StringIO()
        call_command("scaffold_scenario_catalog", stdout=out)
        data = yaml.safe_load(out.getvalue())
        module_types = [m["module_type"] for m in data["modules"]]
        self.assertNotIn("CoastalWetland2", module_types)
        self.assertIn("CoastalWetland", module_types)


class CatalogFileTest(SimpleTestCase):

    def test_catalog_yaml_exists(self):
        catalog_path = Path(__file__).resolve().parent.parent / "catalog" / "scenario_catalog.yaml"
        self.assertTrue(catalog_path.exists(), f"Catalog file not found at {catalog_path}")

    def test_catalog_yaml_loads_without_error(self):
        catalog_path = Path(__file__).resolve().parent.parent / "catalog" / "scenario_catalog.yaml"
        modules = load_catalog(str(catalog_path))
        self.assertGreater(len(modules), 0)


class GetCatalogTest(SimpleTestCase):

    def test_get_catalog_returns_modules(self):
        modules = get_catalog()
        self.assertGreater(len(modules), 0)
        self.assertIsInstance(modules[0], CatalogModule)

    def test_get_catalog_is_cached(self):
        modules1 = get_catalog()
        modules2 = get_catalog()
        self.assertIs(modules1, modules2)

    def test_get_catalog_modules_have_fields(self):
        modules = get_catalog()
        for module in modules:
            self.assertGreater(len(module.fields), 0, f"{module.module_type} has no fields")
