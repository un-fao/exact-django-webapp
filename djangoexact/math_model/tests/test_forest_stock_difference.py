import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.forest_stock_difference import ForestStockDifference, yearly_change_fractions  # noqa: E402
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes  # noqa: E402

START = {"agb": 50.0, "bgb": 10.0, "litter": 5.0, "deadwood": 4.0, "soc": 60.0}
END = {"agb": 70.0, "bgb": 10.0, "litter": 3.0, "deadwood": 6.0, "soc": 55.0}


def build(stocks_end=END, rate_type="linear", delay=0, **kwargs):
    module = ForestStockDifference(
        implementation_time=4, capitalization_time=2, rate_type=rate_type, delay=delay, hectares=100.0, stocks_start=START, stocks_end=stocks_end, **kwargs
    )
    module.calculate_emissions()
    return module


def series(module, activity):
    [emission_set] = [s for s in module.result.yearly_emissions_by_sector_by_gas if s.activity == activity]
    return [e.value for e in emission_set.emissions]


def test_linear_series_hand_checked():
    module = build()
    # AGB +20 tC/ha on 100 ha over 4 years: -20 * 100 * 44/12 / 4 = -1833.33 tCO2 per year, then nothing.
    assert series(module, ActivityTypes.AGB_GROWTH) == pytest.approx([-1833.3333, -1833.3333, -1833.3333, -1833.3333, 0, 0])
    assert series(module, ActivityTypes.BGB_GROWTH) == pytest.approx([0] * 6)
    # Litter -2 tC/ha: +733.33 tCO2 in total.
    assert series(module, ActivityTypes.LITTER) == pytest.approx([183.3333] * 4 + [0, 0])
    assert series(module, ActivityTypes.DEADWOOD) == pytest.approx([-183.3333] * 4 + [0, 0])
    assert series(module, ActivityTypes.SOIL_CO2_CHANGE) == pytest.approx([458.3333] * 4 + [0, 0])


def test_pools_sum_to_total_stock_difference():
    module = build()
    expected = -sum(END[p] - START[p] for p in START) * 100 * 44 / 12
    assert module.result.compute_balance() == pytest.approx(expected)
    assert module.inventory.to_total() == pytest.approx(sum(START.values()) * 100 * 44 / 12)


@pytest.mark.parametrize("rate_type", ["linear", "exponential", "immediate"])
def test_every_rate_type_conserves_the_total_change(rate_type):
    fractions = yearly_change_fractions(4, 2, rate_type)
    assert len(fractions) == 6
    assert sum(fractions) == pytest.approx(1)


def test_immediate_puts_the_whole_change_in_year_one():
    assert yearly_change_fractions(4, 2, "immediate") == [1, 0, 0, 0, 0, 0]


def test_unchanged_stocks_emit_nothing_and_delay_pads_the_series():
    module = build(stocks_end=START, delay=2)
    assert series(module, ActivityTypes.AGB_GROWTH) == [0] * 8
    assert module.result.compute_balance() == 0


@pytest.mark.parametrize("bad", [None, -1.0])
def test_missing_or_negative_stock_is_rejected(bad):
    with pytest.raises(ValueError, match="litter"):
        build(stocks_end={**END, "litter": bad})
