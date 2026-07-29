# Scenario Catalog + Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Per the project's `CLAUDE.md`, implementation tasks (code edits) MUST be delegated to the `Backend Architect` agent via the `Agent` tool — plan reading, test runs, and git operations stay in the main session.

**Goal:** Create a curated YAML catalog that defines every module/attribute combination the scenario builder can offer, validated at Django startup against the live `api.Module` subclass graph. Replace the current "only show what exists in `ChangeRecord`" pattern with "show everything the system knows how to model."

**Architecture:** A YAML file (`scenario_catalog.yaml`) defines modules, their permutation fields, value sources, labels, and groupings. A Python loader parses and validates it at startup, rejecting drift between YAML and ORM (e.g., a field name that doesn't match any real model field, or a module type that doesn't exist in `MODULE_CONFIGS`). A `scaffold_scenario_catalog` management command auto-generates a starter YAML by introspecting `MODULE_CONFIGS` from `api.minitool`. This is **PR 2** of eight — no views are touched; user-visible behavior is unchanged.

**Tech Stack:** Django 4.1, Python 3.11+, PyYAML (already a dependency), `manage.py test --keepdb` for the test runner. Feature branch: `feature/scenario-catalog` (stacked on `feature/minitool-sqlite-to-postgres`).

---

## File Structure

```
djangoexact/admin_scripts/
├── catalog/
│   ├── __init__.py          NEW — load_catalog(), validate_catalog(), CatalogEntry dataclass
│   └── scenario_catalog.yaml  NEW — curated catalog (seeded by scaffold command)
├── management/commands/
│   └── scaffold_scenario_catalog.py  NEW — introspects MODULE_CONFIGS → starter YAML
└── tests/
    └── test_catalog.py      NEW — validation + loader tests
```

---

## Task 1: Create the catalog Python package with dataclasses and loader

**Files:**
- Create: `djangoexact/admin_scripts/catalog/__init__.py`

**Goal:** Define the data model (`CatalogModule`, `CatalogField`) and the `load_catalog()` / `validate_catalog()` functions. The loader reads YAML, the validator checks it against `MODULE_CONFIGS`.

- [ ] **Step 1: Write the failing test file**

Create `djangoexact/admin_scripts/tests/test_catalog.py`:

```python
from django.test import SimpleTestCase, override_settings
from unittest.mock import patch
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

MISSING_REQUIRED_YAML = """
modules:
  - module_type: Grassland
    label: Grassland
    config_name: grassland
    fields:
      - label: No field_name
        value_source:
          kind: static
          values: [1]
"""


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


def load_catalog_from_string(yaml_string):
    """Helper: parse YAML string into CatalogModule list."""
    data = yaml.safe_load(yaml_string)
    return [CatalogModule.from_dict(m) for m in data.get("modules", [])]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run:
```bash
cd djangoexact && python manage.py test admin_scripts.tests.test_catalog -v 2 --keepdb
```

Expected: `ImportError` — `admin_scripts.catalog` doesn't exist yet.

- [ ] **Step 3: Delegate implementation to Backend Architect**

Use `Agent` with `subagent_type="Backend Architect"`. Prompt:

> **Task:** Create `djangoexact/admin_scripts/catalog/__init__.py` with these components:
>
> 1. `ValidationError(Exception)` — custom exception for catalog errors.
>
> 2. `CatalogField` dataclass with fields: `field_name` (str), `label` (str), `value_source` (dict). Class method `from_dict(data: dict) -> CatalogField` that extracts these keys (raises `KeyError` if `field_name` missing).
>
> 3. `CatalogModule` dataclass with fields: `module_type` (str), `label` (str), `config_name` (str), `fields` (list[CatalogField]). Class method `from_dict(data: dict) -> CatalogModule`.
>
> 4. `load_catalog(path: str) -> list[CatalogModule]` — reads YAML file, raises `ValidationError` if empty or missing `modules` key, returns list of `CatalogModule`.
>
> 5. `validate_catalog(modules: list[CatalogModule]) -> list[str]` — validates each module against `MODULE_CONFIGS` from `api.minitool`:
>    - Check `module_type` exists as a key in `MODULE_CONFIGS`
>    - Check each `field.field_name` + `"_start"` exists in `MODULE_CONFIGS[module_type]["fields"]`
>    - Return list of error strings (empty = valid)
>
> Import `MODULE_CONFIGS` lazily inside `validate_catalog` (not at module level) to avoid circular imports.
>
> Also create the empty `djangoexact/admin_scripts/tests/__init__.py` if it doesn't exist.
>
> Do not create the YAML file yet. Do not run tests.

- [ ] **Step 4: Run the tests**

Run:
```bash
cd djangoexact && python manage.py test admin_scripts.tests.test_catalog -v 2 --keepdb
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/catalog/__init__.py djangoexact/admin_scripts/tests/test_catalog.py djangoexact/admin_scripts/tests/__init__.py
git commit -m "feat(catalog): add scenario catalog loader and validator

CatalogModule/CatalogField dataclasses, load_catalog() for YAML parsing,
validate_catalog() checks against MODULE_CONFIGS. Tests cover valid input,
missing keys, invalid module types, and invalid field names."
```

---

## Task 2: Create the scaffold_scenario_catalog management command

**Files:**
- Create: `djangoexact/admin_scripts/management/commands/scaffold_scenario_catalog.py`

**Goal:** Introspect `MODULE_CONFIGS` from `api.minitool` and emit a starter YAML that passes `validate_catalog()`. This gives curators a complete starting point they can trim and annotate.

- [ ] **Step 1: Write the failing test**

Append to `djangoexact/admin_scripts/tests/test_catalog.py`:

```python
from io import StringIO
from django.core.management import call_command


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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
cd djangoexact && python manage.py test admin_scripts.tests.test_catalog.ScaffoldCatalogCommandTest -v 2 --keepdb
```

Expected: error — command not found.

- [ ] **Step 3: Delegate implementation to Backend Architect**

Use `Agent` with `subagent_type="Backend Architect"`. Prompt:

> **Task:** Create `djangoexact/admin_scripts/management/commands/scaffold_scenario_catalog.py`.
>
> The command should:
> 1. Import `MODULE_CONFIGS` from `api.minitool`
> 2. For each entry in `MODULE_CONFIGS`:
>    - Extract `module_type` (the dict key, e.g. `"Grassland"`)
>    - Extract `config_name` from the config dict
>    - Extract field pairs: group `fields` keys by stripping `_start`/`_w` suffixes. For each unique base name, create a catalog field entry.
>    - For each field, determine `value_source`:
>      - If the value is a QuerySet, use `{"kind": "queryset", "model": queryset.model.__name__}`
>      - If the value is a list, use `{"kind": "static", "values": the_list}`
>      - If the value is a model instance (e.g. `get()` result), use `{"kind": "queryset", "model": type(value).__name__}`
>    - Set `label` to a human-readable version of the module_type (e.g. `"Grassland"` → `"Grassland"`, `"AnnualCropland"` → `"Annual Cropland"`, `"SmallFishery"` → `"Small Fishery"`)
>    - Skip entries like `"CoastalWetland2"` (duplicate config variant — detect by checking if config_name duplicates an already-seen one)
> 3. Output the YAML to stdout using `yaml.dump()` with `default_flow_style=False, sort_keys=False`
>
> Handle the `fields` dict carefully: some keys have `_start`/`_w` suffixes (permutation pairs), some don't (static fields like `forest_type`, `livestock_category_types`). For suffixed pairs, use the base name (e.g. `grassland_management_type`). For non-suffixed fields, use the key as-is.
>
> The command class: `class Command(BaseCommand)` with `help = "Generate a starter scenario_catalog.yaml from MODULE_CONFIGS"`.
>
> Do not run tests.

- [ ] **Step 4: Run the tests**

```bash
cd djangoexact && python manage.py test admin_scripts.tests.test_catalog.ScaffoldCatalogCommandTest -v 2 --keepdb
```

Expected: all 3 tests pass.

- [ ] **Step 5: Generate and save the actual catalog YAML**

Run:
```bash
cd djangoexact && python manage.py scaffold_scenario_catalog > admin_scripts/catalog/scenario_catalog.yaml
```

Visually inspect the output.

- [ ] **Step 6: Commit**

```bash
git add djangoexact/admin_scripts/management/commands/scaffold_scenario_catalog.py
git commit -m "feat(catalog): add scaffold_scenario_catalog management command

Introspects MODULE_CONFIGS to emit a starter scenario_catalog.yaml.
Handles queryset/static value sources, deduplicates _start/_w field
pairs, skips variant configs like CoastalWetland2."
```

---

## Task 3: Seed the catalog YAML and add a startup validation check

**Files:**
- Create: `djangoexact/admin_scripts/catalog/scenario_catalog.yaml` (generated in Task 2 Step 5)
- Modify: `djangoexact/admin_scripts/apps.py`

**Goal:** Ship the generated YAML and wire up a Django `AppConfig.ready()` hook that validates it at startup. If validation fails, it logs warnings (not hard errors) so the app still starts — curators fix the YAML at their convenience.

- [ ] **Step 1: Write the failing test**

Append to `djangoexact/admin_scripts/tests/test_catalog.py`:

```python
from pathlib import Path


class CatalogFileTest(SimpleTestCase):

    def test_catalog_yaml_exists(self):
        catalog_path = Path(__file__).resolve().parent.parent / "catalog" / "scenario_catalog.yaml"
        self.assertTrue(catalog_path.exists(), f"Catalog file not found at {catalog_path}")

    def test_catalog_yaml_loads_without_error(self):
        catalog_path = Path(__file__).resolve().parent.parent / "catalog" / "scenario_catalog.yaml"
        modules = load_catalog(str(catalog_path))
        self.assertGreater(len(modules), 0)

    def test_catalog_yaml_validates(self):
        catalog_path = Path(__file__).resolve().parent.parent / "catalog" / "scenario_catalog.yaml"
        modules = load_catalog(str(catalog_path))
        errors = validate_catalog(modules)
        self.assertEqual(errors, [], f"Catalog validation errors: {errors}")
```

- [ ] **Step 2: Delegate apps.py edit to Backend Architect**

Use `Agent` with `subagent_type="Backend Architect"`. Prompt:

> **Task:** Edit `djangoexact/admin_scripts/apps.py` to add a `ready()` method that validates the catalog YAML at startup.
>
> First read the current file to see the existing `AppConfig`. Then modify it:
>
> ```python
> import logging
> from django.apps import AppConfig
>
> logger = logging.getLogger(__name__)
>
>
> class AdminScriptsConfig(AppConfig):
>     default_auto_field = "django.db.models.BigAutoField"
>     name = "admin_scripts"
>
>     def ready(self):
>         from pathlib import Path
>         from admin_scripts.catalog import load_catalog, validate_catalog, ValidationError
>
>         catalog_path = Path(__file__).resolve().parent / "catalog" / "scenario_catalog.yaml"
>         if not catalog_path.exists():
>             logger.warning("Scenario catalog not found at %s", catalog_path)
>             return
>
>         try:
>             modules = load_catalog(str(catalog_path))
>             errors = validate_catalog(modules)
>             if errors:
>                 for error in errors:
>                     logger.warning("Catalog validation: %s", error)
>         except ValidationError as e:
>             logger.warning("Catalog load failed: %s", e)
> ```
>
> Keep the existing class name and `name` attribute. If there's already a `ready()` method, merge the logic. Do not run tests.

- [ ] **Step 3: Add the YAML file to git and run all catalog tests**

```bash
git add djangoexact/admin_scripts/catalog/scenario_catalog.yaml
cd djangoexact && python manage.py test admin_scripts.tests.test_catalog -v 2 --keepdb
```

Expected: all tests pass (dataclass tests, scaffold tests, catalog file tests).

- [ ] **Step 4: Run the full admin_scripts + minitool suite**

```bash
cd djangoexact && python manage.py test admin_scripts minitool -v 2 --keepdb
```

Expected: all tests pass, no regressions.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/catalog/ djangoexact/admin_scripts/apps.py djangoexact/admin_scripts/tests/test_catalog.py djangoexact/admin_scripts/tests/__init__.py
git commit -m "feat(catalog): add scenario_catalog.yaml with startup validation

Ship the curated YAML catalog generated by scaffold_scenario_catalog.
AppConfig.ready() validates it against MODULE_CONFIGS at startup,
logging warnings on drift. Tests cover file existence, loading, and
validation."
```

---

## Task 4: Add a get_catalog() convenience function for PR 3

**Files:**
- Modify: `djangoexact/admin_scripts/catalog/__init__.py`

**Goal:** Add a `get_catalog()` function that returns the validated catalog modules, cached after first load. PR 3 will use this from the HTMX views.

- [ ] **Step 1: Write the failing test**

Append to `djangoexact/admin_scripts/tests/test_catalog.py`:

```python
from admin_scripts.catalog import get_catalog


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
```

- [ ] **Step 2: Delegate implementation to Backend Architect**

Use `Agent` with `subagent_type="Backend Architect"`. Prompt:

> **Task:** Add a `get_catalog()` function to `djangoexact/admin_scripts/catalog/__init__.py`.
>
> Read the current file first. Then add:
>
> ```python
> _catalog_cache = None
>
> def get_catalog():
>     """Return the validated catalog modules, cached after first load."""
>     global _catalog_cache
>     if _catalog_cache is not None:
>         return _catalog_cache
>     from pathlib import Path
>     catalog_path = Path(__file__).resolve().parent / "scenario_catalog.yaml"
>     _catalog_cache = load_catalog(str(catalog_path))
>     return _catalog_cache
> ```
>
> Do not change existing code. Do not run tests.

- [ ] **Step 3: Run tests**

```bash
cd djangoexact && python manage.py test admin_scripts.tests.test_catalog -v 2 --keepdb
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add djangoexact/admin_scripts/catalog/__init__.py djangoexact/admin_scripts/tests/test_catalog.py
git commit -m "feat(catalog): add get_catalog() cached accessor

Convenience function for PR 3's HTMX views. Returns validated
CatalogModule list, cached after first load."
```

---

## Task 5: Final sanity pass

**Files:** none modified.

- [ ] **Step 1: Run the full test suite**

```bash
cd djangoexact && python manage.py test admin_scripts minitool -v 2 --keepdb
```

Expected: all tests pass.

- [ ] **Step 2: Verify no orphan imports or dead code**

```bash
cd djangoexact && python manage.py check 2>&1 | tail -5
```

Expected: system check passes.

- [ ] **Step 3: Review the commit log**

```bash
git log --oneline feature/minitool-sqlite-to-postgres..HEAD
```

Expected: 4 clean commits for Tasks 1-4.
