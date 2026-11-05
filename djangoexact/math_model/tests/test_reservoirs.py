"""Hand-checked reservoir (flooded land) emissions, IPCC 2019 Vol. 4 Ch. 7."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes  # noqa: E402
from math_model.no_time_dependency_final.reservoirs import RESERVOIR_DEFAULT_ALPHA, ReservoirConversion, Reservoir, trophic_alpha  # noqa: E402

# Tropical moist/wet: Table 7.15 (<= 20 y), Table 7.9 (> 20 y), Table 7.13 (CO2-C)
EF_LE_20, EF_GT_20, CO2_C = 251.6, 141.1, 2.77
GWP_CH4 = 28
CO2 = 44 / 12


def reservoir(**kw):
    base = dict(
        implementation_time=5,
        capitalization_time=5,
        rate_type="linear",
        delay=0,
        area_start=0,
        area_end=0,
        alpha_start=1.0,
        alpha_end=1.0,
        age_at_series_start=17,
        ch4_ef_age_le_20=EF_LE_20,
        ch4_ef_age_gt_20=EF_GT_20,
        co2_c_ef_age_le_20=CO2_C,
        rd=0.09,
        methane_constant=GWP_CH4,
    )
    base.update(kw)
    r = Reservoir(**base)
    r.calculate_emissions()
    return r


def series(r, activity):
    (s,) = [s for s in r.result.yearly_emissions_by_sector_by_gas if s.activity == activity]
    return [e.value for e in s.emissions]


def test_crosses_20_years_mid_project():
    # 100 ha mesotrophic (alpha 3) phased out linearly over 5 years: alpha x area by year (mid-year averages)
    # [270, 210, 150, 90, 30, 0, ...]; area [90, 70, 50, 30, 10, 0, ...]. Ages 17, 18, 19 are <= 20 years old.
    r = reservoir(area_start=100, alpha_start=3)
    k = 1.09 / 1000 * GWP_CH4
    assert series(r, ActivityTypes.FLOODED_LAND_CH4) == pytest.approx(
        [270 * EF_LE_20 * k, 210 * EF_LE_20 * k, 150 * EF_LE_20 * k, 90 * EF_GT_20 * k, 30 * EF_GT_20 * k, 0, 0, 0, 0, 0]
    )
    assert series(r, ActivityTypes.FLOODED_LAND_CO2) == pytest.approx([90 * CO2_C * CO2, 70 * CO2_C * CO2, 50 * CO2_C * CO2, 0, 0, 0, 0, 0, 0, 0])


def test_trophic_change_and_scenario_sum_keep_area_constant():
    start = reservoir(area_start=100, alpha_start=3)
    w = reservoir(area_end=100, alpha_end=0.7)
    total_ch4 = [a + b for a, b in zip(series(start, ActivityTypes.FLOODED_LAND_CH4), series(w, ActivityTypes.FLOODED_LAND_CH4))]
    total_co2 = [a + b for a, b in zip(series(start, ActivityTypes.FLOODED_LAND_CO2), series(w, ActivityTypes.FLOODED_LAND_CO2))]

    k = 1.09 / 1000 * GWP_CH4
    # w alpha x area: [7, 21, 35, 49, 63, 70, 70, ...]
    assert total_ch4[0] == pytest.approx((270 + 7) * EF_LE_20 * k)
    assert total_ch4[3] == pytest.approx((90 + 49) * EF_GT_20 * k)
    assert total_ch4[9] == pytest.approx(70 * EF_GT_20 * k)
    assert total_co2[:4] == pytest.approx([100 * CO2_C * CO2] * 3 + [0])


def test_downstream_off_and_old_reservoir():
    r = reservoir(area_start=100, rate_type="immediate", area_end=0, age_at_series_start=20, rd=0)
    r_w = reservoir(area_end=100, rate_type="immediate", age_at_series_start=20, rd=0)
    assert series(r_w, ActivityTypes.FLOODED_LAND_CH4) == pytest.approx([100 * EF_GT_20 / 1000 * GWP_CH4] * 10)
    assert sum(series(r_w, ActivityTypes.FLOODED_LAND_CO2)) == 0
    assert sum(series(r, ActivityTypes.FLOODED_LAND_CH4)) == 0


def test_inventory_uses_start_year():
    r = reservoir(area_start=10, alpha_start=1)
    inv = {(i.gas_type, i.activity): i.value for i in r.inventory.emissions_by_sector_by_gas}
    assert inv[(GasTypes.CH4, ActivityTypes.FLOODED_LAND_CH4)] == pytest.approx(10 * EF_LE_20 * 1.09 / 1000 * GWP_CH4)
    assert inv[(GasTypes.CO2, ActivityTypes.FLOODED_LAND_CO2)] == pytest.approx(10 * CO2_C * CO2)


def test_trophic_alpha_precedence():
    assert trophic_alpha(5.0, 100.0, 0.7) == 5.0
    assert trophic_alpha(None, 20.0, 0.7) == pytest.approx(5.2)  # Eq. 7.11
    assert trophic_alpha(None, None, 0.7) == 0.7


def conversion(**kw):
    base = dict(
        implementation_time=5,
        capitalization_time=25,
        rate_type="linear",
        delay=0,
        area=100,
        alpha=3.0,
        ch4_ef_age_le_20=EF_LE_20,
        ch4_ef_age_gt_20=EF_GT_20,
        co2_c_ef_age_le_20=CO2_C,
        rd=0.09,
        methane_constant=GWP_CH4,
    )
    base.update(kw)
    r = ReservoirConversion(**base)
    r.calculate_emissions()
    return r


def test_conversion_cohorts_switch_to_old_ef_20_years_after_flooding():
    # 100 ha flooded linearly over 5 years: mid-year flooded area [10, 30, 50, 70, 90, 100, ...]. Each yearly
    # cohort uses the <= 20 y EF for 20 years from its own flooding, so the switch is staggered over years 20-24.
    r = conversion()
    flooded = [10, 30, 50, 70, 90] + [100] * 25
    aged = [0] * 20 + [10, 30, 50, 70, 90] + [100] * 5
    k = 3.0 * 1.09 / 1000 * GWP_CH4
    expected = [((f - a) * EF_LE_20 + a * EF_GT_20) * k for f, a in zip(flooded, aged)]
    assert series(r, ActivityTypes.FLOODED_LAND_CH4) == pytest.approx(expected)
    assert series(r, ActivityTypes.FLOODED_LAND_CH4)[19] == pytest.approx(100 * EF_LE_20 * k)
    assert series(r, ActivityTypes.FLOODED_LAND_CH4)[25] == pytest.approx(100 * EF_GT_20 * k)


def test_conversion_co2_stops_when_each_cohort_turns_20():
    r = conversion()
    co2 = series(r, ActivityTypes.FLOODED_LAND_CO2)
    young = [10, 30, 50, 70, 90] + [100] * 15 + [90, 70, 50, 30, 10] + [0] * 5
    assert co2 == pytest.approx([y * CO2_C * CO2 for y in young])
    assert co2[25:] == [0] * 5


def test_conversion_without_downstream_and_zero_start_inventory():
    r = conversion(rd=0, alpha=RESERVOIR_DEFAULT_ALPHA, rate_type="immediate", capitalization_time=5)
    assert series(r, ActivityTypes.FLOODED_LAND_CH4) == pytest.approx([100 * 0.7 * EF_LE_20 / 1000 * GWP_CH4] * 10)
    # Converted land is not flooded in the start year.
    assert all(i.value == 0 for i in r.inventory.emissions_by_sector_by_gas)


def test_pond_conversion_constant_ch4_and_no_co2():
    # A pond, canal or ditch: one Eq. 7.12 EF for every age, no Rd, no CO2 (no IPCC method).
    r = conversion(ch4_ef_age_le_20=183, ch4_ef_age_gt_20=183, co2_c_ef_age_le_20=0, rd=0, alpha=1.0)
    flooded = [10, 30, 50, 70, 90] + [100] * 25
    assert series(r, ActivityTypes.FLOODED_LAND_CH4) == pytest.approx([f * 183 / 1000 * GWP_CH4 for f in flooded])
    assert series(r, ActivityTypes.FLOODED_LAND_CO2) == pytest.approx([0] * 30)
