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

from dataclasses import dataclass
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
        items = (
            (k, tuple(v) if isinstance(v, list) else v)
            for k, v in (self.filter or {}).items()
        )
        return hash(("Cycle", frozenset(items)))


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
