"""Coastal wetlands: rewetting CH4 uses the emission factor it is given.

The calculator looks up the default CH4 factor for the resolved salinity (default "<18"; the
reference data holds 0 for ">18"). The math model must use that factor as is, and a Tier 2
value must still override it.

Django-free, runs as a plain script:

    python djangoexact/math_model/tests/check_cw_salinity_default.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.coastal_wetlands import CoastalWetland  # noqa: E402
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes  # noqa: E402

T, C = 5, 15
GWP_CH4 = 27
REWETTED = 100


def rewetting_ch4(ef_default, ef_tier_2=None):
    module = CoastalWetland(
        implementation_time=T, capitalization_time=C, rate_type="linear", delay=0,
        maximum_area_for_water_management=1000, area_drained_start=REWETTED, area_drained_end=0,
        agb_default=0, bgb_default=0, litter_default=0, deadwood_default=0,
        soil_1m_default=255.0, EF_drainage_default=7.9,
        area_excavated_start=0, area_excavated_end=0,
        area_revegated_start=0, area_revegated_end=0,
        percentage_c_lost_excavation_default=0.5,
        ef_rewetting_carbon_default=0, ef_rewetting_methane_default=ef_default, ef_rewetting_methane_tier_2=ef_tier_2,
        methane_constant=GWP_CH4, mangrove_factor=1,
    )
    module.calculate_emissions()
    sets = [s for s in module.result.yearly_emissions_by_sector_by_gas if s.activity == ActivityTypes.REWETTING_REVEGETATION and s.gas_type == GasTypes.CH4]
    return sum(e.value for e in sets[0].emissions)


# Linear 0 -> 100 ha over 5 years, then 15 years at 100 ha: 2.5 + 15 = 17.5 full-area years.
FULL_AREA_YEARS = 17.5


def expected(ef):
    return GWP_CH4 * REWETTED * ef / 1000 * FULL_AREA_YEARS


# "<18" default factor (193.7 kg CH4/ha/yr for mangroves and tidal marsh) is used, not zeroed.
assert abs(rewetting_ch4(193.7) - expected(193.7)) < 1e-6, rewetting_ch4(193.7)
# ">18" comes from the reference data as 0.
assert rewetting_ch4(0.0) == 0
# Tier 2 overrides the default either way.
assert abs(rewetting_ch4(0.0, ef_tier_2=50.0) - expected(50.0)) < 1e-6
assert abs(rewetting_ch4(193.7, ef_tier_2=50.0) - expected(50.0)) < 1e-6

print("ok")
