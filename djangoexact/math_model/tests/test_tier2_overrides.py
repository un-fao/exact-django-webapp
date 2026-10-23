"""User tier 2 inputs must win over the IPCC default. Django-free: run with pytest."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.annuals import AnnualCropland  # noqa: E402
from math_model.no_time_dependency_final.inputs import SolidAndLiquidFuelsConsumption  # noqa: E402

TIME = {"implementation_time": 5, "capitalization_time": 15, "rate_type": "linear", "delay": 0}


def total(module):
    module.calculate_emissions()
    return sum(e.value for s in module.result.yearly_emissions_by_sector_by_gas for e in s.emissions)


def fuel(**tier_2):
    return SolidAndLiquidFuelsConsumption(
        **TIME,
        emissions_factor_co2=2.0,
        emissions_factor_ch4=0.001,
        emissions_factor_n2o=0.0001,
        mwh_start=100.0,
        mwh_end=100.0,
        methane_constant=27.0,
        nitrous_constant=273.0,
        **tier_2,
    )


def annual(**minor):
    inputs = dict(
        **TIME,
        hectares_start=0.0,
        hectares_end=10.0,
        soc_start_default=50.0,
        soc_end_default=50.0,
        fmg_start_default=1.0,
        fmg_end_default=1.0,
        flu_start_default=1.0,
        flu_end_default=1.0,
        fi_start_default=1.0,
        fi_end_default=1.0,
        calculate_soc_som=False,
        calculate_biomass=False,
        ef_nitrous_som=0.01,
        nitrous_constant=273.0,
        methane_constant=27.0,
        ef_methane_agr_residues_main=None,
        combustion_factor_main=0.8,
        n_estimation_slope_main=1.0,
        n_estimation_intercept_main=0.5,
        yield_value_main=2.0,
        ef_nitrous_agr_residues_main=None,
        retained_main=False,
        n_content_ag_main=0.006,
        ratio_bg_ag_main=0.2,
        n_content_bg_main=0.009,
        dm_content_main=0.9,
        n_estimation_slope_minor=1.0,
        n_estimation_intercept_minor=0.5,
        yield_value_minor=2.0,
        retained_minor=True,
        n_content_ag_minor=0.006,
        ratio_bg_ag_minor=0.2,
        n_content_bg_minor=0.009,
        dm_content_minor=0.9,
    )
    return AnnualCropland(**{**inputs, **minor})


def test_fuel_tier_2_emission_factor_overrides_default():
    assert total(fuel(specific_factor_co2=4.0)) > total(fuel())
    assert total(fuel(specific_factor_ch4=1.0)) > total(fuel())
    assert total(fuel(specific_factor_n2o=1.0)) > total(fuel())


def test_minor_season_tier_2_yield_overrides_default():
    assert total(annual(yield_minor_tier_2=6.0)) > total(annual())


def test_minor_season_tier_2_yield_counts_without_a_default():
    assert total(annual(yield_value_minor=None, yield_minor_tier_2=6.0)) > total(annual(yield_value_minor=None))
