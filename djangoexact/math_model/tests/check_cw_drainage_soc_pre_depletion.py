"""Coastal wetlands: drainage and excavation areas and soil stocks.

- Land already drained at project start has drained for PRE_PROJECT_DRAINAGE_YEARS, so it
  emits only for the years of stock it has left; newly drained land emits for the full
  soil_1m / EF years.
- Drainage only counts drained land that is not excavated (AD - AEX).
- Drainage biomass is lost only on newly drained land.
- Excavation takes newly drained land first, then pre-drained land. Pre-drained land has
  no biomass left and a depleted soil stock.

Django-free, runs as a plain script:

    python djangoexact/math_model/tests/check_cw_drainage_soc_pre_depletion.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.coastal_wetlands import CoastalWetland  # noqa: E402
from math_model.no_time_dependency_final.general_functions import compute_half_year_cumulative_n_year_maturity  # noqa: E402
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes  # noqa: E402

T, C = 5, 15
SOIL, EF = 255.0, 7.9  # n = int(255 / 7.9) = 32 years, 12 left after 20 years of pre-project drainage
DEPLETED_SOIL = SOIL - 20 * EF
LITTER = 2.0  # the only biomass pool, so biomass C per hectare is easy to check
PCT_LOST = 0.5
CO2 = 44 / 12


def build(rate="linear", drained=(0.0, 0.0), excavated=(0.0, 0.0)):
    module = CoastalWetland(
        implementation_time=T, capitalization_time=C, rate_type=rate, delay=0,
        maximum_area_for_water_management=1000, area_drained_start=drained[0], area_drained_end=drained[1],
        agb_default=0, bgb_default=0, litter_default=LITTER, deadwood_default=0,
        soil_1m_default=SOIL, EF_drainage_default=EF,
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


def drainage_soil(module):
    return sum(series(module, ActivityTypes.DRAINAGE))


def drainage_biomass(module):
    return sum(series(module, ActivityTypes.BIOMASS, index=0))


def excavation_biomass(module):
    return sum(series(module, ActivityTypes.BIOMASS, index=1))


def excavation_soil(module):
    return sum(series(module, ActivityTypes.SOIL_CO2_CHANGE))


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


# --- Drainage soil: pre-depletion ---

# No pre-drained and no excavated area: identical to the pre-change formula, for every rate.
for rate in ("linear", "exponential", "immediate"):
    old_hectares, _ = compute_half_year_cumulative_n_year_maturity(0, 100, T, C, rate, number_of_years=int(SOIL / EF))
    assert close(drainage_soil(build(rate, drained=(0, 100))), EF * CO2 * sum(old_hectares)), rate

# 50 ha pre-drained stays drained, 100 ha newly drained:
# 50 ha x 11.5 yr (12 years left, half-year averaging) + 100 ha ramping in = 575 + 1750 ha-yr.
assert close(drainage_soil(build(drained=(50, 150))), EF * CO2 * (575 + 1750))

# Pre-drained area unchanged: only the 12 remaining years.
assert close(drainage_soil(build(drained=(100, 100))), EF * CO2 * 100 * 11.5)

# Rewetting 150 -> 50 ha of pre-drained land: emissions stop once the 12 remaining years are used.
for rate in ("linear", "immediate"):
    drainage = series(build(rate, drained=(150, 50)), ActivityTypes.DRAINAGE)
    assert all(v == 0 for v in drainage[12:]), (rate, drainage)
    assert all(v >= 0 for v in drainage), (rate, drainage)
    assert sum(drainage) <= 150 * DEPLETED_SOIL * CO2 + 1e-6, rate

# --- Drainage biomass: only on newly drained land ---

assert close(drainage_biomass(build(drained=(0, 100))), LITTER * CO2 * 100)
assert close(drainage_biomass(build(drained=(50, 150))), LITTER * CO2 * 100)
assert drainage_biomass(build(drained=(100, 100))) == 0
assert drainage_biomass(build(drained=(150, 50))) == 0

# --- Excavated area is taken away from drainage ---

# 0 -> 100 ha drained, 30 of them excavated: drainage counts 70 ha (soil and biomass).
m = build(drained=(0, 100), excavated=(0, 30))
assert close(drainage_soil(m), drainage_soil(build(drained=(0, 70))))
assert close(drainage_biomass(m), LITTER * CO2 * 70)
# Excavation on newly drained land: full soil stock and biomass.
assert close(excavation_soil(m), PCT_LOST * SOIL * CO2 * 30)
assert close(excavation_biomass(m), LITTER * CO2 * 30)

# 100 ha pre-drained, 30 excavated by the project: excavation on pre-drained land only.
m = build(drained=(100, 100), excavated=(0, 30))
assert close(drainage_soil(m), EF * CO2 * (70 * 11.5 + 30 * 2.5)), drainage_soil(m)  # 30 ha phase out over T=5
assert drainage_biomass(m) == 0
assert close(excavation_soil(m), PCT_LOST * DEPLETED_SOIL * CO2 * 30)
assert excavation_biomass(m) == 0

# Mixed: 50 -> 100 ha drained, 80 excavated: 50 on newly drained land, 30 on pre-drained land.
m = build(drained=(50, 100), excavated=(0, 80))
assert close(excavation_soil(m), PCT_LOST * CO2 * (50 * SOIL + 30 * DEPLETED_SOIL))
assert close(excavation_biomass(m), LITTER * CO2 * 50)
assert drainage_biomass(m) == 0

# Excavated area larger than drained area (front-end validation bypassed): no negative drainage.
m = build(drained=(0, 10), excavated=(0, 30))
assert drainage_soil(m) >= 0 and drainage_biomass(m) >= 0

print("ok")
