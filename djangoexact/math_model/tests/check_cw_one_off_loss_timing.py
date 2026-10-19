"""Coastal wetlands: timing of one-off losses (drainage biomass clearing, excavation).

A hectare is cleared or excavated once, so its loss belongs to the year it is converted:
totals are preserved, nothing lands in the capitalization years, and under "immediate"
everything lands in year 1.

Django-free, runs as a plain script:

    python djangoexact/math_model/tests/check_cw_one_off_loss_timing.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.coastal_wetlands import CoastalWetland  # noqa: E402
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes  # noqa: E402

T, C = 5, 15
SOIL, LITTER, PCT_LOST = 255.0, 2.0, 0.5
CO2 = 44 / 12


def build(rate, drained=(0.0, 100.0), excavated=(0.0, 30.0)):
    module = CoastalWetland(
        implementation_time=T, capitalization_time=C, rate_type=rate, delay=0,
        maximum_area_for_water_management=1000, area_drained_start=drained[0], area_drained_end=drained[1],
        agb_default=0, bgb_default=0, litter_default=LITTER, deadwood_default=0,
        soil_1m_default=SOIL, EF_drainage_default=7.9,
        area_excavated_start=excavated[0], area_excavated_end=excavated[1],
        area_revegated_start=0, area_revegated_end=0,
        percentage_c_lost_excavation_default=PCT_LOST,
        ef_rewetting_carbon_default=0, ef_rewetting_methane_default=0,
        soil_type="<18", methane_constant=27, mangrove_factor=1,
    )
    module.calculate_emissions()
    return module


def series(module, activity, index=0):
    sets = [s for s in module.result.yearly_emissions_by_sector_by_gas if s.activity == activity and s.gas_type == GasTypes.CO2]
    return [e.value for e in sets[index].emissions]


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


for rate in ("linear", "exponential", "immediate"):
    m = build(rate)
    drainage_biomass = series(m, ActivityTypes.BIOMASS, index=0)
    excavation_biomass = series(m, ActivityTypes.BIOMASS, index=1)
    excavation_soil = series(m, ActivityTypes.SOIL_CO2_CHANGE)

    for name, values, total in (
        ("drainage biomass", drainage_biomass, LITTER * CO2 * 70),
        ("excavation biomass", excavation_biomass, LITTER * CO2 * 30),
        ("excavation soil", excavation_soil, PCT_LOST * SOIL * CO2 * 30),
    ):
        assert len(values) == T + C, (rate, name, len(values))
        assert close(sum(values), total), (rate, name, sum(values), total)
        assert all(v == 0 for v in values[T:]), (rate, name, "leaks past implementation", values)
        if rate == "immediate":
            assert close(values[0], total) and all(v == 0 for v in values[1:]), (rate, name, values)

# Linear: the same number of hectares is converted every implementation year.
soil = series(build("linear"), ActivityTypes.SOIL_CO2_CHANGE)
assert all(close(v, PCT_LOST * SOIL * CO2 * 30 / T) for v in soil[:T]), soil

# Exponential: front-loaded, decreasing every year.
soil = series(build("exponential"), ActivityTypes.SOIL_CO2_CHANGE)
assert all(a > b for a, b in zip(soil[: T - 1], soil[1:T])), soil

print("ok")
