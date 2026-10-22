"""Energy fuel consumption: a Tier 2 emission factor overrides the IPCC default.

SolidAndLiquidFuelsConsumption backs Energy and the value-chain submodules (Transport,
Processing, Storage, Packaging). It used to keep the default whenever one existed, so
analysts' Tier 2 factors were silently ignored.

Django-free, runs as a plain script:

    python djangoexact/math_model/tests/check_fuel_tier2_precedence.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.inputs import SolidAndLiquidFuelsConsumption  # noqa: E402
from math_model.no_time_dependency_final.ghg_emissions_classes import GasTypes  # noqa: E402

GWP_CH4, GWP_N2O = 27, 273
MWH = 10.0


def first_year(defaults, tier_2):
    module = SolidAndLiquidFuelsConsumption(
        implementation_time=5, capitalization_time=15, rate_type="linear", delay=0,
        emissions_factor_co2=defaults[0], specific_factor_co2=tier_2[0],
        emissions_factor_ch4=defaults[1], specific_factor_ch4=tier_2[1],
        emissions_factor_n2o=defaults[2], specific_factor_n2o=tier_2[2],
        mwh_start=MWH, mwh_end=MWH, methane_constant=GWP_CH4, nitrous_constant=GWP_N2O,
    )
    module.calculate_emissions()
    by_gas = {s.gas_type: s.emissions[0].value for s in module.result.yearly_emissions_by_sector_by_gas}
    return by_gas[GasTypes.CO2], by_gas[GasTypes.CH4], by_gas[GasTypes.N2O]


def expected(co2, ch4, n2o):
    return MWH * co2, MWH * ch4 * GWP_CH4, MWH * n2o * GWP_N2O


def close(a, b):
    return all(abs(x - y) < 1e-9 for x, y in zip(a, b))


# Tier 2 present: it wins over the default, per gas.
got = first_year(defaults=(1.0, 0.1, 0.01), tier_2=(2.0, 0.2, 0.02))
assert close(got, expected(2.0, 0.2, 0.02)), f"Tier 2 ignored: {got}"

# Only some gases have Tier 2: the others keep their default.
got = first_year(defaults=(1.0, 0.1, 0.01), tier_2=(2.0, None, None))
assert close(got, expected(2.0, 0.1, 0.01)), f"partial Tier 2 wrong: {got}"

# A Tier 2 of 0 is a real value, not "unset".
got = first_year(defaults=(1.0, 0.1, 0.01), tier_2=(0.0, 0.0, 0.0))
assert close(got, expected(0.0, 0.0, 0.0)), f"zero Tier 2 ignored: {got}"

# No default in the reference data: Tier 2 fills the gap (behaviour kept).
got = first_year(defaults=(None, None, None), tier_2=(2.0, 0.2, 0.02))
assert close(got, expected(2.0, 0.2, 0.02)), f"Tier 2 fallback broken: {got}"

print("ok")
