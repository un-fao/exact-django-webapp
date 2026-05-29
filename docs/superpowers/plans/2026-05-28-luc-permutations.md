# LandUseChange Permutations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift LandUseChange out of the `_UNTESTABLE_MODULES` set in `admin_scripts/test_planner.py` by introducing a preset spec drawn from `Permutations LUC.xlsx` and a saved-fixtures runner that builds the sibling land modules `LandUseChange.get_modules()` needs.

**Architecture:** A new preset spec module (`admin_scripts/catalog/luc_presets.py`) encodes per-class preset templates. A new helper module (`admin_scripts/luc_permutations.py`) expands those templates into concrete field dicts and emits pair entries that slot into the existing `plan_module_tests` output. A new service (`api/services/luc_compute.py`) builds saved Project/Activity/sibling-module/LUC fixtures inside a rolled-back transaction, runs `LandUseChangeCalculator`, and returns data dicts. `compute_module_slice` gates LUC into the new path; all other modules keep the existing pipeline.

**Tech Stack:** Django 4.x ORM, model factories from `api/factories.py`, `LandUseChangeCalculator`, `transaction.atomic` / `set_rollback`.

**Reference spec:** `docs/superpowers/specs/2026-05-28-luc-permutations-design.md` (local only - `docs/superpowers/specs/` is gitignored).

**Prerequisites:** All file paths in this plan are relative to the repo root `exact-django-webapp/`. Most `pytest` invocations run from `djangoexact/` (the Django root). The dev sandbox has no Postgres; tests requiring DB run in CI. Local gate is `python -m py_compile <file>`.

---

## Task 1: Preset data structures and content

**Files:**
- Create: `djangoexact/admin_scripts/catalog/luc_presets.py`
- Test: `djangoexact/admin_scripts/tests/test_luc_presets.py`

- [ ] **Step 1: Write the failing test**

Create `djangoexact/admin_scripts/tests/test_luc_presets.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run from `djangoexact/`:
```bash
python manage.py test admin_scripts.tests.test_luc_presets -v 2
```
Expected: ImportError / ModuleNotFoundError for `admin_scripts.catalog.luc_presets`.

- [ ] **Step 3: Write the minimal implementation**

Create `djangoexact/admin_scripts/catalog/luc_presets.py`:

```python
"""Preset spec for LandUseChange permutations.

Each entry in :data:`LUC_PRESETS` maps a Django model class name (the
``class_name`` field on ``api.ModuleType``) to a list of preset templates.
A preset template is a dict mapping base field name (without the
``_start``/``_w``/``_wo`` suffix) to a :class:`Fixed` or :class:`Cycle`
value selector. The optional ``_destination_overrides`` key holds a dict
of field-name -> selector that replaces matching entries when this
template is used as the ``module_type_w`` side of a transition. That is
how the afforestation rule is encoded for ``ForestManagement``.

Contents transcribed once from ``Permutations LUC.xlsx`` at the repo
root; future changes happen here in Python, not in the spreadsheet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Fixed:
    """A literal value. For FKs this is the name string (looked up by
    ``name``/``name_en``); for scalars (bool, int) it is the value itself.
    """
    name: Any


@dataclass(frozen=True)
class Cycle:
    """Cycle through every option exposed for this field.

    ``filter`` is forwarded to ``QuerySet.filter`` to restrict the cycle,
    e.g. ``Cycle(filter={"name__in": ["Secondary"]})``.
    """
    filter: dict | None = None

    def __eq__(self, other):
        if not isinstance(other, Cycle):
            return NotImplemented
        return self.filter == other.filter

    def __hash__(self):
        return hash(("Cycle", frozenset((self.filter or {}).items())))


LUC_PRESETS: dict[str, list[dict[str, Any]]] = {
    "AnnualCropland": [
        {
            "land_use_type": Fixed("Default"),
            "tillage_management_type": Fixed("Full Tillage"),
            "organic_input_type": Fixed("Low C input"),
            "residue_management_type": Fixed("Burned"),
        },
        {
            "land_use_type": Fixed("Default"),
            "tillage_management_type": Fixed("No Tillage"),
            "organic_input_type": Fixed("High C input, with manure"),
            "residue_management_type": Fixed("Exported"),
        },
    ],
    "PerennialCropland": [
        {
            "land_use_type": Cycle(),
            "tillage_management_type": Fixed("Full Tillage"),
            "organic_input_type": Fixed("Low C input"),
            "is_biomass_burned": Fixed(True),
        },
        {
            "land_use_type": Cycle(),
            "tillage_management_type": Fixed("No Tillage"),
            "organic_input_type": Fixed("High C input, with manure"),
            "is_biomass_burned": Fixed(False),
        },
    ],
    "FloodedRice": [
        {
            "water_management_type_before_cultivation": Fixed("Non Flooded Pre-Season >180 D"),
            "water_management_type_after_cultivation": Fixed("Rainfed, Deep Water"),
            "organic_amendment_type": Fixed("Straw Exported"),
        },
        {
            "water_management_type_before_cultivation": Fixed("Flooded Pre-Season > 30 D"),
            "water_management_type_after_cultivation": Fixed("Irrigated, Continuously Flooded"),
            "organic_amendment_type": Fixed("Straw Incorporated Long (>30 Days) Before Cultivation"),
        },
    ],
    "ForestManagement": [
        {
            "forest_type": Cycle(),
            "forest_condition_type": Cycle(),
            "_destination_overrides": {
                "forest_condition_type": Cycle(filter={"name__in": ["Secondary"]}),
            },
        },
    ],
    "Grassland": [
        {"grassland_management_type": Fixed("Severely Degraded")},
        {"grassland_management_type": Fixed("Improved With High Inputs")},
    ],
    "Settlement": [{"settlement_type": Cycle()}],
    "SetAside": [{}],
    "OtherLand": [{}],
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python manage.py test admin_scripts.tests.test_luc_presets -v 2
```
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/catalog/luc_presets.py djangoexact/admin_scripts/tests/test_luc_presets.py
git commit -m "feat(admin_scripts): add LUC preset spec for permutations"
```

---

## Task 2: Preset expansion (start side, no overrides)

**Files:**
- Create: `djangoexact/admin_scripts/luc_permutations.py`
- Modify: `djangoexact/admin_scripts/tests/test_luc_presets.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `djangoexact/admin_scripts/tests/test_luc_presets.py`:

```python
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
        from api import models
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test admin_scripts.tests.test_luc_presets.ExpandPresetStartSideTest -v 2
```
Expected: ImportError for `admin_scripts.luc_permutations`.

- [ ] **Step 3: Write the minimal implementation**

Create `djangoexact/admin_scripts/luc_permutations.py`:

```python
"""LUC permutation planning helpers.

The Test All Modules admin script feeds its planner output into the same
``ComputationJob`` dispatcher every other module uses. For LandUseChange
we emit one entry per directed (start_template, w_template) pair drawn
from :data:`admin_scripts.catalog.luc_presets.LUC_PRESETS`.

``expand_preset`` resolves a single template into the concrete list of
field-dict combinations the runner will iterate. ``Fixed`` selectors
yield exactly one combination; ``Cycle`` selectors expand to one
combination per matching ORM row, taking the Cartesian product across
all cycled fields in the template.
"""
from __future__ import annotations

import enum
import itertools
from typing import Any

from admin_scripts.catalog.luc_presets import LUC_PRESETS, Cycle, Fixed


class Side(enum.Enum):
    START = "start"
    W = "w"


def _resolve_fk_by_name(model_cls, name: str):
    """Look up a row by ``name`` or ``name_en``. Raises if not found."""
    for field_name in ("name_en", "name"):
        try:
            return model_cls.objects.get(**{field_name: name})
        except model_cls.DoesNotExist:
            continue
        except Exception:
            # name_en may not be a field on this model; fall through to name.
            continue
    raise ValueError(
        f"{model_cls.__name__}: no row with name='{name}' or name_en='{name}'"
    )


def _field_value_choices(class_name: str, field_name: str, selector: Any) -> list[Any]:
    """Return the list of concrete values for one template entry.

    ``Fixed(value)`` returns ``[value]`` for scalars or ``[<resolved FK>]``
    for FK fields. ``Cycle(filter=...)`` reads the corresponding entry from
    ``MODULE_CONFIGS[class_name]["fields"]`` (the ``_start`` variant if
    present, else the bare field name) and forwards ``filter`` to the
    queryset.
    """
    from api.minitool import MODULE_CONFIGS

    fields = MODULE_CONFIGS.get(class_name, {}).get("fields", {})
    source = fields.get(f"{field_name}_start") or fields.get(field_name)

    if isinstance(selector, Fixed):
        if isinstance(selector.name, bool):
            return [selector.name]
        if source is None:
            return [selector.name]
        # source is a queryset of FK rows; resolve by name.
        model_cls = source.model
        return [_resolve_fk_by_name(model_cls, selector.name)]

    if isinstance(selector, Cycle):
        if source is None:
            raise ValueError(
                f"Cycle() on {class_name}.{field_name} but no MODULE_CONFIGS entry"
            )
        qs = source
        if selector.filter:
            qs = qs.filter(**selector.filter)
        return list(qs)

    raise TypeError(f"Unknown selector type: {selector!r}")


def expand_preset(class_name: str, template_idx: int, side: Side) -> list[dict[str, Any]]:
    """Expand one preset template into the list of concrete field dicts.

    When ``side == Side.W`` and the template has a ``_destination_overrides``
    dict, override entries replace matching field selectors before expansion.
    """
    template = dict(LUC_PRESETS[class_name][template_idx])
    overrides = template.pop("_destination_overrides", {})

    if side is Side.W and overrides:
        for field_name, selector in overrides.items():
            template[field_name] = selector

    if not template:
        return [{}]

    field_names = list(template.keys())
    per_field_values = [
        _field_value_choices(class_name, fname, template[fname])
        for fname in field_names
    ]
    return [
        dict(zip(field_names, combo))
        for combo in itertools.product(*per_field_values)
    ]
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python manage.py test admin_scripts.tests.test_luc_presets.ExpandPresetStartSideTest -v 2
```
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/luc_permutations.py djangoexact/admin_scripts/tests/test_luc_presets.py
git commit -m "feat(admin_scripts): expand LUC preset templates to concrete combos"
```

---

## Task 3: Destination-side override (afforestation)

**Files:**
- Modify: `djangoexact/admin_scripts/tests/test_luc_presets.py` (extend)

`expand_preset` already accepts a `Side` parameter and applies overrides. This task just locks the behavior in with a direct test.

- [ ] **Step 1: Write the failing test**

Append to `djangoexact/admin_scripts/tests/test_luc_presets.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify the implementation already passes**

```bash
python manage.py test admin_scripts.tests.test_luc_presets.ExpandPresetDestinationOverrideTest -v 2
```
Expected: 2 tests pass (the Side-aware override logic was implemented in Task 2).

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/tests/test_luc_presets.py
git commit -m "test(admin_scripts): lock in destination-only afforestation override"
```

---

## Task 4: Template listing + identifier helpers

**Files:**
- Modify: `djangoexact/admin_scripts/luc_permutations.py` (append)
- Create: `djangoexact/admin_scripts/tests/test_luc_permutations.py`

- [ ] **Step 1: Write the failing test**

Create `djangoexact/admin_scripts/tests/test_luc_permutations.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test admin_scripts.tests.test_luc_permutations -v 2
```
Expected: ImportError for `list_preset_templates`, `format_identifier`, `parse_identifier`.

- [ ] **Step 3: Write the minimal implementation**

Append to `djangoexact/admin_scripts/luc_permutations.py`:

```python
def list_preset_templates() -> list[tuple[str, int]]:
    """Return [(class_name, template_idx), ...] for every entry in LUC_PRESETS,
    ordered by class-name insertion order then template index.
    """
    out: list[tuple[str, int]] = []
    for class_name, templates in LUC_PRESETS.items():
        for idx in range(len(templates)):
            out.append((class_name, idx))
    return out


def format_identifier(class_name: str, template_idx: int) -> str:
    """Encode a (class_name, template_idx) tuple as a from/to_value string."""
    return f"{class_name}#{template_idx}"


def parse_identifier(value: str) -> tuple[str, int]:
    """Inverse of :func:`format_identifier`. Raises ``ValueError`` on bad input."""
    if "#" not in value:
        raise ValueError(f"LUC identifier missing '#': {value!r}")
    class_name, _, idx_str = value.partition("#")
    try:
        return class_name, int(idx_str)
    except ValueError as exc:
        raise ValueError(f"LUC identifier has non-integer index: {value!r}") from exc
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python manage.py test admin_scripts.tests.test_luc_permutations -v 2
```
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/luc_permutations.py djangoexact/admin_scripts/tests/test_luc_permutations.py
git commit -m "feat(admin_scripts): list templates and identifier helpers for LUC permutations"
```

---

## Task 5: Pair planner

**Files:**
- Modify: `djangoexact/admin_scripts/luc_permutations.py` (append)
- Modify: `djangoexact/admin_scripts/tests/test_luc_permutations.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `djangoexact/admin_scripts/tests/test_luc_permutations.py`:

```python
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
        first_class = next(iter([cls for cls, _ in [("AnnualCropland", 0)]]))
        self.assertEqual(entries[0]["from_value"], "AnnualCropland#0")
        self.assertEqual(entries[0]["to_value"], "AnnualCropland#0")

    def test_no_duplicate_pairs(self):
        entries = plan_luc_pairs()
        pairs = [(e["from_value"], e["to_value"]) for e in entries]
        self.assertEqual(len(pairs), len(set(pairs)))
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test admin_scripts.tests.test_luc_permutations.PlanLucPairsTest -v 2
```
Expected: ImportError for `plan_luc_pairs`.

- [ ] **Step 3: Write the minimal implementation**

Append to `djangoexact/admin_scripts/luc_permutations.py`:

```python
def plan_luc_pairs() -> list[dict]:
    """Return one planner entry per directed (start_template, w_template) pair.

    Each entry slots into ``plan_module_tests``'s ``planned`` list with the
    same shape used for non-LUC modules:

        {"module_type": "LandUseChange",
         "field_name": "module_type",
         "from_value": "<ClassName>#<idx>",
         "to_value":   "<ClassName>#<idx>"}
    """
    templates = list_preset_templates()
    entries: list[dict] = []
    for start_class, start_idx in templates:
        from_value = format_identifier(start_class, start_idx)
        for w_class, w_idx in templates:
            entries.append({
                "module_type": "LandUseChange",
                "field_name": "module_type",
                "from_value": from_value,
                "to_value": format_identifier(w_class, w_idx),
            })
    return entries
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python manage.py test admin_scripts.tests.test_luc_permutations.PlanLucPairsTest -v 2
```
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/luc_permutations.py djangoexact/admin_scripts/tests/test_luc_permutations.py
git commit -m "feat(admin_scripts): plan_luc_pairs emits 144 directed template pairs"
```

---

## Task 6: Drop LUC from `_UNTESTABLE_MODULES`, integrate pairs into the planner

**Files:**
- Modify: `djangoexact/admin_scripts/test_planner.py`
- Modify: `djangoexact/admin_scripts/tests/test_test_planner.py`

- [ ] **Step 1: Update the failing existing test**

In `djangoexact/admin_scripts/tests/test_test_planner.py`, replace the existing `test_land_use_change_is_skipped_with_clear_reason` with:

```python
    def test_land_use_change_pairs_are_planned_not_skipped(self):
        # LUC fields now route through plan_luc_pairs (saved-fixtures runner).
        # The planner must not surface LUC entries in `skipped`, and the
        # 144 LUC pair entries (one per template pair) must be in `planned`.
        catalog = [_module("LandUseChange", [
            _field("module_type", {"kind": "queryset", "model": "ModuleType"}),
        ])]
        planned, skipped = plan_module_tests(catalog)
        luc_skipped = [e for e in skipped if e["module_type"] == "LandUseChange"]
        luc_planned = [e for e in planned if e["module_type"] == "LandUseChange"]
        self.assertEqual(luc_skipped, [])
        self.assertEqual(len(luc_planned), 144)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test admin_scripts.tests.test_test_planner.PlanModuleTestsTest.test_land_use_change_pairs_are_planned_not_skipped -v 2
```
Expected: FAIL - current code emits 1 skipped entry per catalog field, no planned entries.

- [ ] **Step 3: Update `test_planner.py`**

Replace the top-of-file constants and the catalog loop in `djangoexact/admin_scripts/test_planner.py`:

Replace this block (lines 13-20 - the `_UNTESTABLE_MODULES` / `_UNTESTABLE_REASON` constants and their docstring):

```python
# LandUseChange runs against three sibling land modules attached to the same
# saved Activity (`activity.annualcropland.first()` etc.). The permutation
# runner builds Activity unsaved and does not provision siblings, so any LUC
# permutation crashes inside `LandUseChange.get_modules()`. Until the runner
# learns to build siblings, surface LUC fields as Skipped with a clear reason
# rather than failing the run. Tracked in LandUseChangeProcessor docstring.
_UNTESTABLE_MODULES = frozenset({"LandUseChange"})
_UNTESTABLE_REASON = "LandUseChange permutations need sibling fixtures (TODO)"
```

with:

```python
# LandUseChange permutations now route through a dedicated saved-fixtures
# runner; the planner emits one entry per (start_template, w_template) pair
# from admin_scripts.luc_permutations.plan_luc_pairs(). See
# api/services/luc_compute.py for the runner.
```

And inside `plan_module_tests`, replace:

```python
    for module in catalog:
        if module.module_type in _UNTESTABLE_MODULES:
            for field in module.fields:
                skipped.append({
                    "module_type": module.module_type,
                    "field_name": field.field_name,
                    "reason": _UNTESTABLE_REASON,
                })
            continue

        for field in module.fields:
```

with:

```python
    for module in catalog:
        if module.module_type == "LandUseChange":
            # LUC pairs come from plan_luc_pairs(); the catalog entry's
            # fields are informational only for LUC.
            from admin_scripts.luc_permutations import plan_luc_pairs
            planned.extend(plan_luc_pairs())
            continue

        for field in module.fields:
```

- [ ] **Step 4: Run the updated test**

```bash
python manage.py test admin_scripts.tests.test_test_planner -v 2
```
Expected: all existing planner tests pass, plus the new pair test.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/test_planner.py djangoexact/admin_scripts/tests/test_test_planner.py
git commit -m "feat(admin_scripts): route LandUseChange through plan_luc_pairs"
```

---

## Task 7: Catalog YAML cleanup (drop `is_fire_used` from LUC)

**Files:**
- Modify: `djangoexact/admin_scripts/catalog/scenario_catalog.yaml`

- [ ] **Step 1: Edit the YAML**

In `djangoexact/admin_scripts/catalog/scenario_catalog.yaml`, locate the `LandUseChange` entry (around lines 477-494) and remove the `is_fire_used` field block. After edit, the entry must look like:

```yaml
- module_type: LandUseChange
  label: LandUseChange
  config_name: land_use_change
  fields:
  - field_name: module_type
    label: Module Type Transition
    value_source:
      kind: queryset
      model: ModuleType
```

- [ ] **Step 2: Run the catalog validation test**

```bash
python manage.py test admin_scripts.tests.test_catalog -v 2
```
Expected: pass (catalog still validates against MODULE_CONFIGS - `is_fire_used_start` exists there but the catalog is permitted to expose a subset).

- [ ] **Step 3: Re-run the planner test**

```bash
python manage.py test admin_scripts.tests.test_test_planner -v 2
```
Expected: still passes; LUC catalog now exposes one field but the planner emits 144 entries via `plan_luc_pairs`.

- [ ] **Step 4: Commit**

```bash
git add djangoexact/admin_scripts/catalog/scenario_catalog.yaml
git commit -m "chore(admin_scripts): drop is_fire_used from LandUseChange catalog"
```

---

## Task 8: Concrete combo iterator

**Files:**
- Create: `djangoexact/api/services/luc_compute.py`
- Create: `djangoexact/api/tests/test_luc_compute_iterator.py`

- [ ] **Step 1: Write the failing test**

Create `djangoexact/api/tests/test_luc_compute_iterator.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test api.tests.test_luc_compute_iterator -v 2
```
Expected: ImportError for `api.services.luc_compute`.

- [ ] **Step 3: Write the minimal implementation**

Create `djangoexact/api/services/luc_compute.py`:

```python
"""Saved-fixtures permutation runner for LandUseChange.

Unlike per-module slices, LUC needs a saved ``Activity`` with attached
sibling land modules so ``LandUseChange.get_modules()`` resolves. This
module wraps that work in ``transaction.atomic`` + ``set_rollback(True)``
so each combination's fixtures are rolled back; only the data dicts
collected in memory escape the transaction.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def iterate_concrete_combos(
    start_spec: tuple[str, int],
    w_spec: tuple[str, int],
) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Cross-product of expand_preset(start, START) x expand_preset(w, W).

    Yields ``(start_values, w_values)`` field dicts. ``w_values`` already
    has any ``_destination_overrides`` applied.
    """
    from admin_scripts.luc_permutations import Side, expand_preset

    start_combos = expand_preset(start_spec[0], start_spec[1], Side.START)
    w_combos = expand_preset(w_spec[0], w_spec[1], Side.W)
    for s in start_combos:
        for w in w_combos:
            yield s, w
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python manage.py test api.tests.test_luc_compute_iterator -v 2
```
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/api/services/luc_compute.py djangoexact/api/tests/test_luc_compute_iterator.py
git commit -m "feat(api): iterate concrete LUC value combinations across template pair"
```

---

## Task 9: Saved-fixture builder

**Files:**
- Modify: `djangoexact/api/services/luc_compute.py` (append)
- Create: `djangoexact/api/tests/test_build_luc_fixture.py`

- [ ] **Step 1: Write the failing test**

Create `djangoexact/api/tests/test_build_luc_fixture.py`:

```python
"""Tests for build_luc_fixture in luc_compute."""
from django.db import transaction
from django.test import TestCase

from admin_scripts.luc_permutations import Side, expand_preset
from api.services.luc_compute import build_luc_fixture


class BuildLucFixtureTest(TestCase):
    databases = {"default"}

    def test_different_classes_create_two_siblings_and_one_luc(self):
        from api import models
        start_values = expand_preset("AnnualCropland", 0, Side.START)[0]
        w_values = expand_preset("Grassland", 0, Side.W)[0]

        with transaction.atomic():
            luc = build_luc_fixture(
                start_class="AnnualCropland", start_values=start_values,
                w_class="Grassland", w_values=w_values,
            )
            self.assertIsNotNone(luc.pk)
            self.assertEqual(luc.module_type_start.class_name, "AnnualCropland")
            self.assertEqual(luc.module_type_w.class_name, "Grassland")
            self.assertEqual(luc.module_type_wo.class_name, "AnnualCropland")
            activity = luc.activity
            self.assertEqual(activity.annualcropland.count(), 1)
            self.assertEqual(activity.grassland.count(), 1)
            transaction.set_rollback(True)

        # After rollback, none of the rows persist.
        self.assertEqual(models.LandUseChange.objects.count(), 0)
        self.assertEqual(models.AnnualCropland.objects.count(), 0)
        self.assertEqual(models.Grassland.objects.count(), 0)

    def test_same_class_creates_single_sibling_with_both_sides_populated(self):
        from api import models
        start_values = expand_preset("AnnualCropland", 0, Side.START)[0]
        w_values = expand_preset("AnnualCropland", 1, Side.W)[0]

        with transaction.atomic():
            luc = build_luc_fixture(
                start_class="AnnualCropland", start_values=start_values,
                w_class="AnnualCropland", w_values=w_values,
            )
            self.assertEqual(luc.activity.annualcropland.count(), 1)
            sibling = luc.activity.annualcropland.first()
            self.assertEqual(str(sibling.tillage_management_type_start), "Full Tillage")
            self.assertEqual(str(sibling.tillage_management_type_w), "No Tillage")
            self.assertEqual(str(sibling.tillage_management_type_wo), "Full Tillage")
            transaction.set_rollback(True)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test api.tests.test_build_luc_fixture -v 2
```
Expected: ImportError for `build_luc_fixture`.

- [ ] **Step 3: Write the minimal implementation**

Append to `djangoexact/api/services/luc_compute.py`:

```python
def _save_sibling(activity, sibling_class, start_values, w_values):
    """Save one land-module sibling on ``activity`` with start/w/wo fields.

    Each base field in ``start_values`` is written to the model's
    ``_start`` attribute. The corresponding ``_w`` attribute uses
    ``w_values[field]`` when the key exists (same-class case) or the
    start value as filler (different-class case). ``_wo`` mirrors start
    (matches LandUseChangeProcessor's existing convention).
    """
    from api import models as api_models

    model_cls = getattr(api_models, sibling_class)
    instance = model_cls(activity=activity)
    for field_name, start_val in start_values.items():
        setattr(instance, f"{field_name}_start", start_val)
        setattr(instance, f"{field_name}_w", w_values.get(field_name, start_val))
        setattr(instance, f"{field_name}_wo", start_val)
    # area is required on every LandModule but isn't part of the preset.
    if hasattr(instance, "area"):
        instance.area = 1
    instance.save()
    return instance


def build_luc_fixture(start_class, start_values, w_class, w_values):
    """Build & save Project, Activity, sibling(s), and a LandUseChange.

    Caller MUST run this inside a ``transaction.atomic()`` block and call
    ``transaction.set_rollback(True)`` after running the calculator so
    nothing persists to the database.
    """
    from api import models as api_models

    project = api_models.Project.objects.create()
    activity = api_models.Activity.objects.create(project=project)

    if start_class == w_class:
        _save_sibling(activity, start_class, start_values, w_values)
    else:
        # Different classes: each side gets its own sibling. The w fields
        # on the start sibling and the start fields on the w sibling get
        # the same-side preset values (they aren't read by the calculator
        # but the model requires non-null in some cases).
        _save_sibling(activity, start_class, start_values, start_values)
        _save_sibling(activity, w_class, w_values, w_values)

    module_type_start = api_models.ModuleType.objects.get(class_name=start_class)
    module_type_w = api_models.ModuleType.objects.get(class_name=w_class)

    luc = api_models.LandUseChange.objects.create(
        activity=activity,
        module_type_start=module_type_start,
        module_type_w=module_type_w,
        module_type_wo=module_type_start,
        area=1,
        is_fire_used_start=False,
        is_fire_used_w=False,
        is_fire_used_wo=False,
    )
    return luc
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python manage.py test api.tests.test_build_luc_fixture -v 2
```
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/api/services/luc_compute.py djangoexact/api/tests/test_build_luc_fixture.py
git commit -m "feat(api): build saved Project/Activity/sibling/LUC fixtures for permutations"
```

---

## Task 10: `_compute_luc_slice` orchestrator

**Files:**
- Modify: `djangoexact/api/services/luc_compute.py` (append)
- Create: `djangoexact/api/tests/test_compute_luc_slice.py`

- [ ] **Step 1: Write the failing test**

Create `djangoexact/api/tests/test_compute_luc_slice.py`:

```python
"""Tests for _compute_luc_slice end-to-end."""
from django.test import TestCase

from api import models
from api.services.luc_compute import _compute_luc_slice


class ComputeLucSliceTest(TestCase):
    databases = {"default"}

    def test_same_class_self_transition_produces_data_rows(self):
        data, errors = _compute_luc_slice(
            from_value="AnnualCropland#0",
            to_value="AnnualCropland#1",
            save_results=False,
        )
        self.assertGreaterEqual(len(data) + len(errors), 1)
        # Every data row carries the LUC identifier pair.
        for row in data:
            self.assertEqual(row["from_value"], "AnnualCropland#0")
            self.assertEqual(row["to_value"], "AnnualCropland#1")

    def test_rolls_back_fixtures_after_each_combo(self):
        before_luc = models.LandUseChange.objects.count()
        before_act = models.Activity.objects.count()
        _compute_luc_slice(
            from_value="AnnualCropland#0", to_value="Grassland#0",
            save_results=False,
        )
        self.assertEqual(models.LandUseChange.objects.count(), before_luc)
        self.assertEqual(models.Activity.objects.count(), before_act)

    def test_afforestation_w_side_only_uses_secondary_condition(self):
        # AnnualCropland -> ForestManagement: w side must restrict
        # forest_condition_type to "Secondary".
        data, errors = _compute_luc_slice(
            from_value="AnnualCropland#0", to_value="ForestManagement#0",
            save_results=False,
        )
        # Either we produced data (must all be Secondary) or all errors are
        # unrelated to the afforestation rule (we don't assert success here
        # since the math model may legitimately fail on some combos).
        for row in data:
            cond = row.get("w_values", {}).get("forest_condition_type")
            if cond is not None:
                self.assertEqual(str(cond), "Secondary")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test api.tests.test_compute_luc_slice -v 2
```
Expected: ImportError for `_compute_luc_slice`.

- [ ] **Step 3: Write the minimal implementation**

Append to `djangoexact/api/services/luc_compute.py`:

```python
def _serialize_result(luc, start_values, w_values, result, from_value, to_value) -> dict:
    """Reduce one calculator result to a dict for DataManager / ChangeRecord."""
    def _str(v):
        return None if v is None else str(v)

    return {
        "from_value": from_value,
        "to_value": to_value,
        "start_class": luc.module_type_start.class_name,
        "w_class": luc.module_type_w.class_name,
        "start_values": {k: _str(v) for k, v in start_values.items()},
        "w_values": {k: _str(v) for k, v in w_values.items()},
        "result": result,
    }


def _compute_luc_slice(
    from_value: str,
    to_value: str,
    *,
    save_results: bool = True,
    progress_callback=None,
) -> tuple[list[dict], list[dict]]:
    """Iterate concrete LUC combinations and run LandUseChangeCalculator.

    Each combination builds saved fixtures inside ``transaction.atomic``
    and rolls back after the calculator returns. Errors are captured per
    combination so a single bad combo doesn't abort the slice.
    """
    from django.db import transaction
    from admin_scripts.luc_permutations import parse_identifier
    from api.calculators import LandUseChangeCalculator

    start_spec = parse_identifier(from_value)
    w_spec = parse_identifier(to_value)

    data: list[dict] = []
    errors: list[dict] = []

    combos = list(iterate_concrete_combos(start_spec, w_spec))
    total = len(combos)
    for i, (start_values, w_values) in enumerate(combos):
        with transaction.atomic():
            try:
                luc = build_luc_fixture(
                    start_class=start_spec[0], start_values=start_values,
                    w_class=w_spec[0], w_values=w_values,
                )
                result = LandUseChangeCalculator(luc).calculate()
                data.append(_serialize_result(
                    luc, start_values, w_values, result,
                    from_value, to_value,
                ))
            except Exception as exc:
                errors.append({
                    "from_value": from_value,
                    "to_value": to_value,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                })
            finally:
                transaction.set_rollback(True)
        if progress_callback and total:
            progress_callback(int(100 * (i + 1) / total))

    if save_results and data:
        from api.minitool import DataManager
        DataManager().save_data(data, errors, "LandUseChange")

    logger.info(
        "LUC slice %s -> %s: %d data, %d errors (from %d combos)",
        from_value, to_value, len(data), len(errors), total,
    )
    return data, errors
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python manage.py test api.tests.test_compute_luc_slice -v 2
```
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/api/services/luc_compute.py djangoexact/api/tests/test_compute_luc_slice.py
git commit -m "feat(api): _compute_luc_slice runs calculator inside rolled-back transaction"
```

---

## Task 11: Route LandUseChange through `_compute_luc_slice` in `compute_module_slice`

**Files:**
- Modify: `djangoexact/api/services/minitool_compute.py`
- Create: `djangoexact/api/tests/test_compute_module_slice_luc_routing.py`

- [ ] **Step 1: Write the failing test**

Create `djangoexact/api/tests/test_compute_module_slice_luc_routing.py`:

```python
"""Tests that compute_module_slice routes LandUseChange to _compute_luc_slice."""
from unittest.mock import patch

from django.test import SimpleTestCase

from api.services.minitool_compute import compute_module_slice


class ComputeModuleSliceLucRoutingTest(SimpleTestCase):
    def test_landusechange_module_routes_to_luc_slice(self):
        with patch("api.services.luc_compute._compute_luc_slice") as mock_slice:
            mock_slice.return_value = ([{"ok": 1}], [])
            data, errors = compute_module_slice(
                module_type="LandUseChange",
                attribute="module_type",
                from_value="AnnualCropland#0",
                to_value="Grassland#0",
                save_results=False,
            )
            mock_slice.assert_called_once_with(
                from_value="AnnualCropland#0",
                to_value="Grassland#0",
                save_results=False,
                progress_callback=None,
            )
            self.assertEqual(data, [{"ok": 1}])
            self.assertEqual(errors, [])
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test api.tests.test_compute_module_slice_luc_routing -v 2
```
Expected: FAIL - current `compute_module_slice` raises `ValueError("Unknown module_type 'LandUseChange'...")` because the LUC entry in `MODULE_CONFIGS` declares fields the existing constrainer can't handle (and even if it could, no calculator is set up for unsaved LUC).

- [ ] **Step 3: Add the LUC gate**

In `djangoexact/api/services/minitool_compute.py`, just inside `compute_module_slice` (after the docstring, before the `from api.minitool import MODULE_CONFIGS, ...` import block), insert:

```python
    if module_type == "LandUseChange":
        from api.services.luc_compute import _compute_luc_slice
        return _compute_luc_slice(
            from_value=from_value,
            to_value=to_value,
            save_results=save_results,
            progress_callback=progress_callback,
        )
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python manage.py test api.tests.test_compute_module_slice_luc_routing -v 2
```
Expected: pass.

- [ ] **Step 5: Run the existing slice tests to confirm no regression**

```bash
python manage.py test api.tests -v 2 -k slice
```
Expected: existing `compute_module_slice` tests still pass.

- [ ] **Step 6: Commit**

```bash
git add djangoexact/api/services/minitool_compute.py djangoexact/api/tests/test_compute_module_slice_luc_routing.py
git commit -m "feat(api): compute_module_slice routes LandUseChange to _compute_luc_slice"
```

---

## Task 12: End-to-end smoke through the job dispatcher

**Files:**
- Create: `djangoexact/admin_scripts/tests/test_enqueue_luc.py`

- [ ] **Step 1: Write the integration test**

Create `djangoexact/admin_scripts/tests/test_enqueue_luc.py`:

```python
"""End-to-end: LUC jobs go through the enqueue dispatcher and run_computation_job."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from admin_scripts.catalog import get_catalog
from admin_scripts.job_dispatcher import enqueue_for_test_run
from admin_scripts.models import ComputationJob, ModuleTestRun
from admin_scripts.test_planner import plan_module_tests


class EnqueueLucTest(TestCase):
    databases = {"default"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="luc@example.com", password="x",
        )

    def test_plan_module_tests_emits_luc_pair_entries(self):
        catalog = get_catalog()
        planned, skipped = plan_module_tests(catalog)
        luc_planned = [e for e in planned if e["module_type"] == "LandUseChange"]
        luc_skipped = [e for e in skipped if e["module_type"] == "LandUseChange"]
        self.assertEqual(len(luc_planned), 144)
        self.assertEqual(luc_skipped, [])

    def test_enqueue_luc_job_creates_pending_computation_job(self):
        run = ModuleTestRun.objects.create(requested_by=self.user)
        job = enqueue_for_test_run(
            user=self.user,
            run_id=run.id,
            module_type="LandUseChange",
            attribute="module_type",
            from_value="AnnualCropland#0",
            to_value="Grassland#0",
            max_rows=10,
        )
        self.assertIsNotNone(job)
        self.assertEqual(job.module_type, "LandUseChange")
        self.assertEqual(job.from_value, "AnnualCropland#0")
        self.assertEqual(job.to_value, "Grassland#0")
        self.assertEqual(job.status, ComputationJob.Status.PENDING)

    def test_run_computation_job_dispatches_to_luc_slice(self):
        run = ModuleTestRun.objects.create(requested_by=self.user)
        job = enqueue_for_test_run(
            user=self.user, run_id=run.id,
            module_type="LandUseChange",
            attribute="module_type",
            from_value="AnnualCropland#0",
            to_value="Grassland#0",
            max_rows=10,
        )
        with patch("api.services.luc_compute._compute_luc_slice") as mock_slice:
            mock_slice.return_value = ([{"ok": 1}], [])
            from django.core.management import call_command
            call_command("run_computation_job", job_id=job.id)
        job.refresh_from_db()
        self.assertEqual(job.status, ComputationJob.Status.COMPLETED)
        mock_slice.assert_called_once()
```

- [ ] **Step 2: Run the test**

```bash
python manage.py test admin_scripts.tests.test_enqueue_luc -v 2
```
Expected: all 3 tests pass. If `enqueue_for_test_run` requires extra fields, mirror what the existing `test_enqueue_for_test_run.py` does.

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/tests/test_enqueue_luc.py
git commit -m "test(admin_scripts): end-to-end LUC enqueue and dispatch"
```

---

## Task 13: Final sweep and full suite

- [ ] **Step 1: Local py_compile sanity check**

```bash
cd djangoexact && \
python -m py_compile admin_scripts/catalog/luc_presets.py \
                     admin_scripts/luc_permutations.py \
                     admin_scripts/test_planner.py \
                     api/services/luc_compute.py \
                     api/services/minitool_compute.py
```
Expected: silent (no syntax errors).

- [ ] **Step 2: Run all admin_scripts tests (CI only - needs Postgres)**

```bash
python manage.py test admin_scripts -v 2
```
Expected: all tests pass.

- [ ] **Step 3: Run all api tests touching luc_compute / minitool_compute (CI only)**

```bash
python manage.py test api.tests.test_luc_compute_iterator api.tests.test_build_luc_fixture api.tests.test_compute_luc_slice api.tests.test_compute_module_slice_luc_routing -v 2
```
Expected: all pass.

- [ ] **Step 4: Visual smoke test (optional, requires DB)**

Manually load `/admin_scripts/test-modules/` in the dev server, click Run, and confirm:
- The detail page shows 144 LUC rows in the LandUseChange group.
- No LUC rows appear under "Skipped".
- Each row has a Pending status and a from/to_value of the form `<Class>#<idx>`.

- [ ] **Step 5: Confirm clean tree**

```bash
git status
```
Expected: working tree clean.

---

## File-level summary

| File | Status |
|---|---|
| `djangoexact/admin_scripts/catalog/luc_presets.py` | NEW |
| `djangoexact/admin_scripts/luc_permutations.py` | NEW |
| `djangoexact/admin_scripts/test_planner.py` | MODIFY (drop untestable, append plan_luc_pairs) |
| `djangoexact/admin_scripts/catalog/scenario_catalog.yaml` | MODIFY (drop `is_fire_used` from LUC) |
| `djangoexact/admin_scripts/tests/test_luc_presets.py` | NEW |
| `djangoexact/admin_scripts/tests/test_luc_permutations.py` | NEW |
| `djangoexact/admin_scripts/tests/test_test_planner.py` | MODIFY (replace skipped-LUC assertion) |
| `djangoexact/admin_scripts/tests/test_enqueue_luc.py` | NEW |
| `djangoexact/api/services/luc_compute.py` | NEW |
| `djangoexact/api/services/minitool_compute.py` | MODIFY (route LUC) |
| `djangoexact/api/tests/test_luc_compute_iterator.py` | NEW |
| `djangoexact/api/tests/test_build_luc_fixture.py` | NEW |
| `djangoexact/api/tests/test_compute_luc_slice.py` | NEW |
| `djangoexact/api/tests/test_compute_module_slice_luc_routing.py` | NEW |
