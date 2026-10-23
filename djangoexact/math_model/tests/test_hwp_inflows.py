"""Harvested wood inflows exposed by parent math modules for the HWP add-on (api/services/hwp_pool.py)."""

import pytest

from math_model.no_time_dependency_final.defo import Defo
from math_model.no_time_dependency_final.forest_management import ForestManagement
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes
from math_model.no_time_dependency_final.hwp_decay import C_TO_CO2
from math_model.no_time_dependency_final.oluc import OtherLandUseChanges
from math_model.no_time_dependency_final.perennial_cropping import PerennialCropland

TIMING = {"implementation_time": 5, "capitalization_time": 15, "rate_type": "linear", "delay": 0}
SOIL = {
    f"{factor}_{side}_default": 1.0 for factor in ("soc", "fmg", "flu", "fi") for side in ("start", "end")
}


def line(module, activity):
    return [e.value for line in module.result.yearly_emissions_by_sector_by_gas if line.activity == activity for e in line.emissions]


def perennial(agb_start, agb_end, bgb_end, complete_renewal=True):
    module = PerennialCropland(
        hwp_complete_renewal=complete_renewal,
        **TIMING,
        **SOIL,
        hectares_start=10.0,
        hectares_end=0.0,
        calculate_soc_som=False,
        calculate_biomass=True,
        ef_nitrous_som=0.01,
        nitrous_constant=273.0,
        methane_constant=27.0,
        residue_burnt=False,
        emission_factor_burning_nitrous_residue=0.07,
        emission_factor_burning_methane=2.7,
        combustion_factor=0.5,
        fire_periodicity_default=1.0,
        agb_rate_default=2.0,
        agb_maximum_c=60.0,
        bgb_rate_default=0.5,
        end_module_has_growth=False,
        agb_start_default=agb_start,
        agb_end_default=agb_end,
        bgb_end_default=bgb_end,
    )
    module.calculate_emissions()
    return module


def test_perennial_removal_inflow_is_the_agb_part_of_the_booked_loss():
    module = perennial(agb_start=40.0, agb_end=0.0, bgb_end=0.0)
    assert module.HWP_INFLOW_ALREADY_EMITTED is True

    biomass = line(module, ActivityTypes.BIOMASS)
    inflow = list(module.hwp_inflow_co2)
    assert sum(inflow) == pytest.approx(40.0 * 10.0 * C_TO_CO2)
    assert sum(biomass) == pytest.approx((40.0 + module.bgb_start) * 10.0 * C_TO_CO2)
    # Same yearly spread as the loss it comes from, and never larger than it.
    for removed, booked in zip(inflow, biomass):
        assert removed == pytest.approx(booked * 40.0 / (40.0 + module.bgb_start))


def test_perennial_loss_other_than_complete_renewal_has_no_inflow():
    # Change of system or conversion to another land use: the trees are not assumed to become products.
    module = perennial(agb_start=40.0, agb_end=0.0, bgb_end=0.0, complete_renewal=False)
    assert getattr(module, "hwp_inflow_co2", None) is None
    assert sum(line(module, ActivityTypes.BIOMASS)) == pytest.approx(sum(line(perennial(40.0, 0.0, 0.0), ActivityTypes.BIOMASS)))


def test_perennial_without_removal_has_no_inflow():
    module = perennial(agb_start=40.0, agb_end=40.0, bgb_end=20.0)
    assert getattr(module, "hwp_inflow_co2", None) is None


def defo(hwp_before_t_dm_per_ha):
    module = Defo(
        **TIMING,
        ha_start=0,
        ha_end=10.0,
        biomass_final_1_year_t_per_ha_default=0,
        nitrous_constant=273.0,
        methane_constant=27.0,
        fire_bool=False,
        n2o_vegetation=0.2,
        ch4_vegetation=6.8,
        cf_vegetation=0.5,
        moisture_emission_factor=0.01,
        litter=2.0,
        dw=3.0,
        hwp_before_t_dm_per_ha=hwp_before_t_dm_per_ha,
        mangrove_factor=0.47,
        agb_t_c_per_ha_default=100.0,
        bgb_t_c_per_ha_default_input_parameter=0.2,
        c_n_ratio=15,
        soc_after_defo_tier_2=None,
        soc_reference_default=50.0,
        soc_reference_tier_2=None,
        **{f"{factor}_{side}_tier_2": None for factor in ("fmg", "fi", "flu", "soc") for side in ("start", "end")},
        **{f"{factor}_{side}_default": 1.0 for factor in ("fmg", "fi", "flu", "soc") for side in ("start", "end")},
        calculate_soc_som=False,
        end_module_has_growth=False,
    )
    module.calculate_emissions()
    return module


def test_deforestation_inflow_is_the_wood_harvested_before_clearing():
    module = defo(hwp_before_t_dm_per_ha=50.0)
    assert module.HWP_INFLOW_ALREADY_EMITTED is False
    assert sum(module.hwp_inflow_co2) == pytest.approx(50.0 * 0.47 * 10.0 * C_TO_CO2)

    # Today that wood is subtracted from the biomass loss and never emitted: the add-on must emit it.
    without_harvest = sum(line(defo(hwp_before_t_dm_per_ha=0.0), ActivityTypes.BIOMASS))
    assert without_harvest - sum(line(module, ActivityTypes.BIOMASS)) == pytest.approx(sum(module.hwp_inflow_co2))


def test_other_land_use_change_flag():
    assert OtherLandUseChanges.HWP_INFLOW_ALREADY_EMITTED is False


def test_forest_flag():
    assert ForestManagement.HWP_INFLOW_ALREADY_EMITTED is True
