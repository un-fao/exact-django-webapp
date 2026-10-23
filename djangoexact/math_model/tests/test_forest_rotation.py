import pytest

from math_model.no_time_dependency_final.forest_management import ForestManagement
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes

HECTARES = 100
GROWTH = 10.0
BGB_RATIO = 0.2
ENERGY_SHARE = 0.25
CF = 0.5
GEF_CH4 = 6.8
GEF_N2O = 0.2
GWP_CH4 = 28.0
GWP_N2O = 265.0


def afforestation_with_rotation():
    zeros = dict.fromkeys(
        [
            "soc_start_default", "soc_end_default", "fmg_start_default", "fmg_end_default", "flu_start_default", "flu_end_default",
            "fi_start_default", "fi_end_default", "ef_nitrous_som", "litter_20_years_default", "litter_start", "litter_max",
            "deadwood_20_years_default", "deadwood_start", "deadwood_max", "degradation_percentage", "agb_start_default",
        ],
        0.0,
    )
    forest = ForestManagement(
        **zeros,
        implementation_time=1,
        capitalization_time=9,
        rate_type="linear",
        delay=0,
        hectares_start=0,
        hectares_end=HECTARES,
        is_same_forest_type=False,
        agb_yearly_growth_over_20_default=GROWTH,
        agb_yearly_growth_over_20_tier_2=None,
        agb_yearly_growth_under_20_default=GROWTH,
        agb_yearly_growth_under_20_tier_2=None,
        bgb_ratio_threshold=125.0,
        bgb_ratio_under_threshold=BGB_RATIO,
        bgb_ratio_over_threshold=BGB_RATIO,
        bgb_yearly_growth_under_20_tier_2=None,
        bgb_yearly_growth_over_20_tier_2=None,
        agb_start_tier_2=None,
        max_agb_value_default=1000.0,
        rotation_recurrence=5,
        rotation_start_year=0,
        rotation_percentage_energy=ENERGY_SHARE,
        disturbance_recurrence=[],
        disturbance_percentage=[],
        disturbance_year_of_start=[],
        disturbance_percentage_fire=[],
        logging_recurrence=None,
        logging_percentage=0,
        logging_percentage_energy=0,
        logging_year_of_start=0,
        litter_20_years_tier_2=None,
        deadwood_20_years_tier_2=None,
        ef_methane=GWP_CH4,
        ef_nitrous=GWP_N2O,
        forest_cf=CF,
        forest_gef_ch4=GEF_CH4,
        forest_gef_n2o=GEF_N2O,
        forest_gef_co2=1580.0,
        nitrous_constant=GWP_N2O,
        methane_constant=GWP_CH4,
        mangrove_factor=1.0,
    )
    forest.calculate_emissions()
    return forest


def line_total(forest, activity, gas):
    return sum(e.value for s in forest.result.yearly_emissions_by_sector_by_gas if s.activity == activity and s.gas_type == gas for e in s.emissions)


# 100 ha planted in year 0 growing 10 t/ha/yr, cut every 5 years: one harvest in the 10-year horizon,
# at year 5, of the 40 t/ha standing after four growth years. BGB follows at the 0.2 root ratio.
AGB_HARVEST = HECTARES * 4 * GROWTH
BGB_HARVEST = AGB_HARVEST * BGB_RATIO
TO_CO2 = 44 / 12


@pytest.mark.parametrize(
    "activity,gas,expected",
    [
        (ActivityTypes.HWP_ROTATION_AGB, GasTypes.CO2, AGB_HARVEST * TO_CO2 * (1 - ENERGY_SHARE)),
        (ActivityTypes.HWP_ROTATION_BGB, GasTypes.CO2, BGB_HARVEST * TO_CO2 * (1 - ENERGY_SHARE)),
        (ActivityTypes.ROTATION_AGB, GasTypes.CO2, AGB_HARVEST * TO_CO2 * ENERGY_SHARE),
        (ActivityTypes.ROTATION_BGB, GasTypes.CO2, BGB_HARVEST * TO_CO2 * ENERGY_SHARE),
        (ActivityTypes.ROTATION_AGB, GasTypes.CH4, AGB_HARVEST * TO_CO2 * ENERGY_SHARE * CF * GEF_CH4 * GWP_CH4 / 1000),
        (ActivityTypes.ROTATION_AGB, GasTypes.N2O, AGB_HARVEST * TO_CO2 * ENERGY_SHARE * CF * GEF_N2O * GWP_N2O / 1000),
        (ActivityTypes.ROTATION_BGB, GasTypes.CH4, BGB_HARVEST * TO_CO2 * ENERGY_SHARE * CF * GEF_CH4 * GWP_CH4 / 1000),
        (ActivityTypes.ROTATION_BGB, GasTypes.N2O, BGB_HARVEST * TO_CO2 * ENERGY_SHARE * CF * GEF_N2O * GWP_N2O / 1000),
    ],
)
def test_rotation_harvest_is_booked_once(activity, gas, expected):
    assert line_total(afforestation_with_rotation(), activity, gas) == pytest.approx(expected)
