import math

import pytest

from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes
from math_model.no_time_dependency_final.hwp_decay import (
    C_TO_CO2,
    DEFAULT_HALF_LIVES,
    PANELS,
    PAPER,
    SAWNWOOD,
    fod_stocks,
    hwp_pool,
    hwp_pool_emission_set,
)


def test_ipcc_tier1_half_lives():
    assert DEFAULT_HALF_LIVES == {SAWNWOOD: 35.0, PANELS: 25.0, PAPER: 2.0}


def test_first_year_matches_hand_calculation():
    k = math.log(2) / 35
    expected = (1 - math.exp(-k)) / k * 100
    assert fod_stocks([100.0], 35)[0] == pytest.approx(expected)
    assert expected == pytest.approx(99.01, abs=0.01)


@pytest.mark.parametrize("half_life", [2.0, 25.0, 35.0])
def test_single_pulse_halves_after_one_half_life(half_life):
    years = int(half_life)
    stocks = fod_stocks([100.0] + [0.0] * years, half_life)
    # The pulse enters with the (1 - e^-k)/k mid-year factor, then decays by e^-k per year.
    assert stocks[years] / stocks[0] == pytest.approx(0.5, rel=1e-9)


def test_continuous_inflow_approaches_steady_state():
    half_life = 2.0
    k = math.log(2) / half_life
    stocks = fod_stocks([10.0] * 200, half_life)
    assert stocks[-1] == pytest.approx(10.0 / k, rel=1e-6)
    assert stocks[-1] - stocks[-2] == pytest.approx(0.0, abs=1e-9)


def test_fuelwood_remainder_is_instant_and_not_stored():
    pool = hwp_pool([50.0, 50.0], {})
    assert pool.total_stock == [0.0, 0.0]
    assert pool.instant_oxidation == [50.0, 50.0]
    assert pool.co2 == [0.0, 0.0]


def test_shares_split_the_inflow():
    pool = hwp_pool([100.0], {SAWNWOOD: 0.5, PAPER: 0.2})
    assert pool.instant_oxidation == pytest.approx([30.0])
    assert pool.stock[SAWNWOOD][0] == pytest.approx(fod_stocks([50.0], 35)[0])
    assert pool.stock[PAPER][0] == pytest.approx(fod_stocks([20.0], 2)[0])
    assert pool.stock[PANELS] == [0.0]


def test_growing_pool_is_a_removal():
    pool = hwp_pool([100.0, 0.0], {SAWNWOOD: 1.0})
    co2 = pool.co2_by_product()[SAWNWOOD]
    assert co2[0] == pytest.approx(-pool.stock[SAWNWOOD][0] * C_TO_CO2)
    assert co2[1] > 0
    assert sum(pool.stock_change[SAWNWOOD]) == pytest.approx(pool.stock[SAWNWOOD][-1])


def test_tier2_half_life_override():
    pool = hwp_pool([100.0], {SAWNWOOD: 1.0}, {SAWNWOOD: 50.0})
    assert pool.stock[SAWNWOOD][0] == pytest.approx(fod_stocks([100.0], 50.0)[0])


@pytest.mark.parametrize(
    "shares,half_lives",
    [({SAWNWOOD: 0.7, PANELS: 0.4}, None), ({SAWNWOOD: -0.1}, None), ({"pallets": 0.1}, None), ({SAWNWOOD: 0.5}, {SAWNWOOD: 0})],
)
def test_invalid_inputs(shares, half_lives):
    with pytest.raises(ValueError):
        hwp_pool([1.0], shares, half_lives)


def test_emission_set_is_net_of_instant_oxidation():
    inflow_co2 = [100.0 * C_TO_CO2, 0.0]
    emission_set = hwp_pool_emission_set(inflow_co2, {SAWNWOOD: 1.0}, None, delay=1)
    assert emission_set.activity == ActivityTypes.HWP_POOL
    values = [e.value for e in emission_set.emissions]
    assert values[0] == 0
    stock = fod_stocks([100.0, 0.0], 35)
    assert values[1:] == pytest.approx([-stock[0] * C_TO_CO2, -(stock[1] - stock[0]) * C_TO_CO2])


def test_matches_eq_12_2_recurrence_on_cumulative_harvest():
    """Eq. 12.2 on a cumulative harvest: pool(i) = pool(i-1) * e^-k + (cum(i) - cum(i-1)) * ((1 - e^-k) / k) * share."""
    cumulative = [0, 120, 250, 250, 400, 400, 400, 610]
    share = 0.8
    k = 0.023
    expected_pool = []
    previous = 0.0
    for i in range(1, len(cumulative)):
        previous = previous * math.exp(-k) + (cumulative[i] - cumulative[i - 1]) * ((1 - math.exp(-k)) / k) * share
        expected_pool.append(previous)

    inflow = [b - a for a, b in zip(cumulative, cumulative[1:])]
    pool = hwp_pool(inflow, {SAWNWOOD: share}, {SAWNWOOD: math.log(2) / k})
    assert pool.stock[SAWNWOOD] == pytest.approx(expected_pool, rel=1e-12)


LONG_HORIZON = 2000


@pytest.mark.parametrize("already_emitted,expected_total_share", [(True, 0.0), (False, 1.0)])
def test_long_horizon_cumulative_emission(already_emitted, expected_total_share):
    """Already emitted inflow: the pool only delays emissions, so the line nets to 0. Never emitted inflow: the line
    ends up emitting the whole inflow (unshared part at once, the rest as it decays)."""
    inflow_co2 = [50.0, 30.0, 20.0] + [0.0] * LONG_HORIZON
    shares = {SAWNWOOD: 0.5, PANELS: 0.2, PAPER: 0.1}
    values = [e.value for e in hwp_pool_emission_set(inflow_co2, shares, None, already_emitted=already_emitted).emissions]
    assert sum(values) == pytest.approx(expected_total_share * sum(inflow_co2), abs=1e-6)


def test_never_emitted_inflow_year_by_year():
    inflow_tc = [100.0, 0.0, 0.0]
    inflow_co2 = [value * C_TO_CO2 for value in inflow_tc]
    values = [e.value for e in hwp_pool_emission_set(inflow_co2, {SAWNWOOD: 0.6}, None, already_emitted=False).emissions]

    stock = fod_stocks([60.0, 0.0, 0.0], 35)
    change = [stock[0], stock[1] - stock[0], stock[2] - stock[1]]
    assert values == pytest.approx([(inflow - dc) * C_TO_CO2 for inflow, dc in zip(inflow_tc, change)])
    # Year 1: the 40% fuel share plus the in-year decay of the sawnwood share; later years: decay only.
    assert values[0] == pytest.approx((40.0 + 60.0 - stock[0]) * C_TO_CO2)
    assert values[1] > 0
