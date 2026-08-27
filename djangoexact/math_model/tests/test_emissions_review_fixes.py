"""Regression tests for the methodological fixes from the emissions review.

Django-free: the math model only depends on stdlib/numpy/matplotlib/PIL, so
this runs as a plain script:

    python djangoexact/math_model/tests/test_emissions_review_fixes.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.general_functions import (  # noqa: E402
    compute_luc_hectare_delta,
    compute_yearly_or_half_year_cumulative,
)
from math_model.no_time_dependency_final.inputs import SolidAndLiquidFuelsConsumption  # noqa: E402


def approx(a, b, tol=1e-9):
    return abs(a - b) <= tol


def test_exponential_endpoints():
    """The exponential ramp must start at start_value and end at end_value."""
    # Increasing from zero: historical behaviour, must be preserved exactly.
    curve = compute_yearly_or_half_year_cumulative(0, 100, 5, 2, "exponential", interim_values=False)
    assert approx(curve[0], 0) and approx(curve[5], 100), curve
    # Increasing from a nonzero start used to end at start + end (140).
    curve = compute_yearly_or_half_year_cumulative(40, 100, 5, 2, "exponential", interim_values=False)
    assert approx(curve[0], 40) and approx(curve[5], 100), curve
    assert all(curve[i] <= curve[i + 1] + 1e-9 for i in range(len(curve) - 1)), curve
    # Decreasing series used to come out ascending (from 40 up to 140).
    curve = compute_yearly_or_half_year_cumulative(100, 40, 5, 2, "exponential", interim_values=False)
    assert approx(curve[0], 100) and approx(curve[5], 40), curve
    assert all(curve[i] >= curve[i + 1] - 1e-9 for i in range(len(curve) - 1)), curve
    # Decreasing to zero mirrors the increasing curve, like the linear branch.
    down = compute_yearly_or_half_year_cumulative(100, 0, 5, 0, "exponential", interim_values=False)
    up = compute_yearly_or_half_year_cumulative(0, 100, 5, 0, "exponential", interim_values=False)
    assert all(approx(d, u) for d, u in zip(down, reversed(up))), (down, up)


def test_luc_hectare_delta_immediate():
    """Under 'immediate' all hectares change in year one and none afterwards."""
    # Full conversion (the deforestation/OLUC pattern): area in year 1, then zero.
    delta = compute_luc_hectare_delta(1000, 0, 5, 15, "immediate")
    assert delta[0] == 1000 and sum(delta[1:]) == 0, delta
    # No area change must mean no converted hectares (used to sum to start + end*(n-1)).
    delta = compute_luc_hectare_delta(1000, 1000, 5, 15, "immediate")
    assert sum(delta) == 0, delta
    # Consistency with the linear rate: same total converted area.
    linear = compute_luc_hectare_delta(1000, 0, 5, 15, "linear")
    immediate = compute_luc_hectare_delta(1000, 0, 5, 15, "immediate")
    assert approx(sum(linear), sum(immediate)), (sum(linear), sum(immediate))


def test_fuel_tier_2_precedence():
    """A user tier-2 fuel EF must override the IPCC default, including zero."""

    def total_for(specific_co2):
        module = SolidAndLiquidFuelsConsumption(
            emissions_factor_co2=2.5,
            specific_factor_co2=specific_co2,
            emissions_factor_ch4=0.0,
            specific_factor_ch4=None,
            emissions_factor_n2o=0.0,
            specific_factor_n2o=None,
            mwh_start=10,
            mwh_end=10,
            nitrous_constant=265,
            methane_constant=28,
            implementation_time=5,
            capitalization_time=0,
            rate_type="linear",
            delay=0,
        )
        module.calculate_emissions()
        return module.result.compute_balance()

    default_total = total_for(None)
    override_total = total_for(1.25)
    zero_total = total_for(0.0)

    assert default_total > 0, default_total
    assert approx(override_total, default_total / 2), (override_total, default_total)
    assert approx(zero_total, 0), zero_total


def main():
    tests = [test_exponential_endpoints, test_luc_hectare_delta_immediate, test_fuel_tier_2_precedence]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    main()
