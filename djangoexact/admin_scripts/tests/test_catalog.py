from django.test import SimpleTestCase
from types import ModuleType
from unittest.mock import patch
import sys
import yaml
import tempfile
import os

from admin_scripts.catalog import (
    CatalogModule,
    CatalogField,
    load_catalog,
    validate_catalog,
    ValidationError,
)


MOCK_MODULE_CONFIGS = {
    "Grassland": {
        "fields": {
            "grassland_management_type_start": {},
            "is_fire_used": {},
        },
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
