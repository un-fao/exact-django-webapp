import pytest

from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes
from math_model.no_time_dependency_final.iwms_rewetting import IwmsRewetting


def _run(**overrides):
    inputs = dict(
        implementation_time=5,
        capitalization_time=15,
        rate_type="immediate",
        delay=0,
        area_start=0.0,
        area_end=100.0,
        ef_ch4_start=235.0,
        ef_ch4_end=235.0,
        gwp_ch4=28.0,
    )
    inputs.update(overrides)
    module = IwmsRewetting(**inputs)
    module.calculate_emissions()
    return module


def _total(module):
    return sum(e.value for s in module.result.yearly_emissions_by_sector_by_gas if s.activity == ActivityTypes.IWMS_REWETTING_CH4 and s.gas_type == GasTypes.CH4 for e in s.emissions)


def test_ch4_is_area_times_table_5_4_ef():
    # 100 ha rewetted for 20 years, temperate EF 235 kg CH4/ha/yr, GWP 28: 100 * 235 / 1000 * 28 * 20
    assert _total(_run()) == pytest.approx(13160)


def test_no_area_no_emissions():
    module = _run(area_end=0.0)
    assert _total(module) == 0
    assert module.inventory.emissions_by_sector_by_gas[0].value == 0


def test_inventory_is_the_start_state():
    module = _run(area_start=100.0, area_end=0.0, ef_ch4_start=900.0)
    assert module.inventory.emissions_by_sector_by_gas[0].value == pytest.approx(100 * 900 / 1000 * 28)


def test_linear_rewetting_follows_the_change_rate():
    # Linear from 0 to 100 ha over 5 years: 250 ha-years during implementation, then 15 full years.
    module = _run(rate_type="linear")
    assert _total(module) == pytest.approx((250 + 1500) * 235 / 1000 * 28)
