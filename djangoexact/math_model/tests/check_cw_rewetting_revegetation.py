"""Coastal wetlands: rewetting CO2 only where vegetation is actively re-established.

IPCC Wetlands Supplement ch. 4 p. 4.28: at Tier 1 the rewetting CO2 factor applies only to
rewetted land that is replanted or reseeded. A Tier 2 factor applies to the whole rewetted
area (it is how users account for natural recolonization). CH4 applies to the whole rewetted
area regardless of revegetation.

Django-free, runs as a plain script:

    python djangoexact/math_model/tests/check_cw_rewetting_revegetation.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.coastal_wetlands import CoastalWetland  # noqa: E402
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes  # noqa: E402

T, C = 5, 15
EF_CO2, EF_CH4, GWP_CH4 = -1.62, 193.7, 27
FULL_AREA_YEARS = 17.5  # linear 0 -> area over 5 years, then 15 years at full area
# The salinity fix (#331) removes the soil_type input; pass it only while the model still has it.
LEGACY_INPUTS = {"soil_type": "<18"} if "soil_type" in CoastalWetland.__dataclass_fields__ else {}


def rewetting(rewetted, revegetated, co2_tier_2=None):
    module = CoastalWetland(
        implementation_time=T, capitalization_time=C, rate_type="linear", delay=0,
        maximum_area_for_water_management=1000, area_drained_start=rewetted, area_drained_end=0,
        agb_default=0, bgb_default=0, litter_default=0, deadwood_default=0,
        soil_1m_default=255.0, EF_drainage_default=7.9,
        area_excavated_start=0, area_excavated_end=0,
        area_revegated_start=0, area_revegated_end=revegetated,
        percentage_c_lost_excavation_default=0.5,
        ef_rewetting_carbon_default=EF_CO2, ef_rewetting_methane_default=EF_CH4, ef_rewetting_carbon_tier_2=co2_tier_2,
        methane_constant=GWP_CH4, mangrove_factor=1, **LEGACY_INPUTS,
    )
    module.calculate_emissions()
    totals = {}
    for s in module.result.yearly_emissions_by_sector_by_gas:
        if s.activity == ActivityTypes.REWETTING_REVEGETATION:
            totals[s.gas_type] = sum(e.value for e in s.emissions)
    return totals[GasTypes.CO2], totals[GasTypes.CH4]


def co2(area, ef=EF_CO2):
    return 44 / 12 * area * ef * FULL_AREA_YEARS


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


CH4_100 = GWP_CH4 * 100 * EF_CH4 / 1000 * FULL_AREA_YEARS

# Rewetting without active revegetation: no Tier 1 CO2 uptake, CH4 still emitted.
c, m = rewetting(100, 0)
assert c == 0 and close(m, CH4_100), (c, m)

# Partly revegetated: CO2 uptake only on the revegetated 40 ha, CH4 on all 100 ha.
c, m = rewetting(100, 40)
assert close(c, co2(40)) and close(m, CH4_100), (c, m)

# Revegetated area larger than rewetted area (front-end validation bypassed): capped at the rewetted area.
c, _ = rewetting(100, 150)
assert close(c, co2(100)), c

# Tier 2 factor applies to the whole rewetted area, with or without active revegetation.
c, _ = rewetting(100, 0, co2_tier_2=-0.5)
assert close(c, co2(100, -0.5)), c

print("ok")
