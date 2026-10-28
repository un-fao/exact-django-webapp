"""Carbon-pool grouping of land CO2 lines for the Excel Results sheet.

Forest management books each pool on its own lines (AGB, BGB, litter, deadwood,
per growth / harvest / disturbance / degradation cause), so its CO2 can be
reported per pool. The other land modules book living biomass as a single
``Biomass`` line: their Tier 1 data (annual, grassland, rice, set aside, other
land) has no AGB/BGB split, and where the inputs do have one (perennial growth
capped on AGB, land use change net of removals and regrowth, coastal wetland
blocks with different AGB factors) a fixed ratio would not reproduce the line.
Those modules keep one ``Biomass (AGB+BGB)`` row.
"""

from __future__ import annotations

import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils

from .extractors import _add, extract_emissions

AT = math_utils.ActivityTypes

AGB = (
    AT.AGB_GROWTH,
    AT.ROTATION_AGB,
    AT.HWP_ROTATION_AGB,
    AT.LOGGING_AGB,
    AT.HWP_LOGGING_AGB,
    AT.DISTURBANCE_AGB,
    AT.DISTURBANCE_FIRE_AGB,
    AT.DEGRADATION_AGB,
)
BGB = (
    AT.BGB_GROWTH,
    AT.ROTATION_BGB,
    AT.HWP_ROTATION_BGB,
    AT.LOGGING_BGB,
    AT.HWP_LOGGING_BGB,
    AT.DISTURBANCE_BGB,
    AT.DISTURBANCE_FIRE_BGB,
    AT.DEGRADATION_BGB,
)
BIOMASS = (AT.BIOMASS,)
DOM = (AT.DOM, AT.LITTER, AT.DEADWOOD, AT.DEGRADATION_LITTER, AT.DEGRADATION_DEADWOOD)
ALL = AGB + BGB + BIOMASS + DOM

LABEL_AGB = "CO2 in above-ground biomass (AGB)"
LABEL_BGB = "CO2 in below-ground biomass (BGB)"
LABEL_BIOMASS = "CO2 in biomass (AGB+BGB)"
LABEL_DOM = "CO2 in dead organic matter (litter and deadwood)"


def co2(source, activities, duration: int) -> list[float]:
    """Sum the CO2 of ``activities`` in ``source``, per year."""
    total = [0.0] * duration
    for activity in activities:
        total = _add(total, extract_emissions(source, activity, math_utils.GasTypes.CO2, duration=duration))
    return total
