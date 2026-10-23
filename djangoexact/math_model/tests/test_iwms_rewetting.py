import pytest

from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes
from math_model.no_time_dependency_final.not_cultivated_land import NotCultivatedLand


def _land(**overrides):
    inputs = dict(
        hectares_start=0,
        hectares_end=100,
        implementation_time=5,
        capitalization_time=15,
        rate_type="immediate",
        delay=0,
        nitrous_constant=265,
        ef_nitrous_som=0.01,
        soc_start_default=50,
        soc_end_default=50,
        fmg_start_default=1,
        fmg_end_default=1,
        flu_start_default=0.7,
        flu_end_default=0.7,
        fi_start_default=1,
        fi_end_default=1,
        calculate_soc_som=True,
        calculate_biomass=False,
    )
    inputs.update(overrides)
    module = NotCultivatedLand(**inputs)
    module.calculate_emissions()
    return module


def _total(module, activity, gas):
    return sum(e.value for s in module.result.yearly_emissions_by_sector_by_gas if s.activity == activity and s.gas_type == gas for e in s.emissions)


def test_off_by_default_adds_nothing():
    module = _land()
    activities = {s.activity for s in module.result.yearly_emissions_by_sector_by_gas}
    assert ActivityTypes.IWMS_REWETTING_CH4 not in activities
    assert all(row.activity != ActivityTypes.IWMS_REWETTING_CH4 for row in module.inventory.emissions_by_sector_by_gas)


def test_ch4_is_area_times_table_5_4_ef():
    # 100 ha rewetted for 20 years, temperate EF 235 kg CH4/ha/yr, GWP 28: 100 * 235 / 1000 * 28 * 20
    module = _land(iwms_rewetted_end=True, ef_ch4_iwms=235, methane_constant=28)
    assert _total(module, ActivityTypes.IWMS_REWETTING_CH4, GasTypes.CH4) == pytest.approx(13160)


def test_start_cohort_uses_start_flag_and_fills_inventory():
    module = _land(hectares_start=100, hectares_end=0, rate_type="linear", iwms_rewetted_start=True, ef_ch4_iwms=900, methane_constant=28)
    inventory = [row for row in module.inventory.emissions_by_sector_by_gas if row.activity == ActivityTypes.IWMS_REWETTING_CH4]
    assert inventory[0].value == pytest.approx(100 * 900 / 1000 * 28)
    # Linear exit over 5 years: the start cohort holds 50 ha-years before leaving, 250 ha-years in total.
    assert _total(module, ActivityTypes.IWMS_REWETTING_CH4, GasTypes.CH4) == pytest.approx(250 * 900 / 1000 * 28)


def test_end_flag_does_not_apply_to_start_cohort():
    module = _land(hectares_start=100, hectares_end=0, iwms_rewetted_end=True, ef_ch4_iwms=235, methane_constant=28)
    assert _total(module, ActivityTypes.IWMS_REWETTING_CH4, GasTypes.CH4) == 0


def test_soc_second_step_years_21_to_40():
    # Box 5.3: FLU 0.80 for years 1-20, then on to 1.0 over years 21-40.
    # Linear adoption over 10 years, 40-year horizon: 1500 ha-years fall in the 21-40 window.
    # Per ha-year: -(50 * 1.0 - 50 * 0.8) / 20 * 44/12.
    base = dict(implementation_time=10, capitalization_time=30, rate_type="linear", flu_end_default=0.8)
    plain = _land(**base)
    rewetted = _land(**base, iwms_rewetted_end=True, ef_ch4_iwms=235, methane_constant=28, iwms_flu_after_20=1.0)
    extra = _total(rewetted, ActivityTypes.SOIL_CO2_CHANGE, GasTypes.CO2) - _total(plain, ActivityTypes.SOIL_CO2_CHANGE, GasTypes.CO2)
    assert extra == pytest.approx(-1500 * 10 / 20 * 44 / 12)


def test_no_second_step_when_already_rewetted_at_start():
    base = dict(implementation_time=10, capitalization_time=30, rate_type="linear", flu_start_default=0.8, flu_end_default=0.8)
    plain = _land(**base)
    rewetted = _land(**base, iwms_rewetted_start=True, iwms_rewetted_end=True, ef_ch4_iwms=235, methane_constant=28, iwms_flu_after_20=1.0)
    assert _total(rewetted, ActivityTypes.SOIL_CO2_CHANGE, GasTypes.CO2) == pytest.approx(_total(plain, ActivityTypes.SOIL_CO2_CHANGE, GasTypes.CO2))
