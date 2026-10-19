"""S-curve change-rate dynamic: shape checks and NEXT parity.

DB-free, run with bare pytest:

    pytest djangoexact/math_model/tests/test_s_curve.py
"""

import math

import pytest
from next_parity import assert_series_close, load_golden

from math_model.no_time_dependency_final.general_functions import (
    compute_luc_hectare_delta,
    compute_matrix_for_log_rec_dis,
    compute_yearly_cumulative_matrix,
    compute_yearly_or_half_year_cumulative,
    s_curve_fraction,
)

GOLDEN = load_golden("next_dynamiques")
SCENARIOS = {s["id"]: s for s in GOLDEN["scenarios"]}
SIDES = {"with": "x_with", "without": "x_without"}

# NEXT's curve reaches L(T) - L(0) = tanh(2.5) of the change before t = T; the rescaled curve
# divides by that, so the gap before T is (1 / tanh(2.5) - 1) * share * |delta|, which peaks
# just before T at 1 - tanh(2.5) (about 1.34%) of |x1 - x0|.
PARITY_REL_TOL = 1 - math.tanh(2.5)

CASES = [(100.0, 0.0), (0.0, 100.0), (37.5, 12.25), (-5.0, 20.0)]


def s_curve(start, end, impl, cap, interim_values=False):
    return compute_yearly_or_half_year_cumulative(start, end, impl, cap, "s-curve", interim_values=interim_values)


@pytest.mark.parametrize("start,end", CASES)
@pytest.mark.parametrize("impl", [1, 2, 5, 20])
def test_endpoints_are_exact(start, end, impl):
    points = s_curve(start, end, impl, 3)
    assert points[0] == start
    assert points[impl] == end
    assert points[impl:] == [end] * 4


@pytest.mark.parametrize("start,end", CASES)
@pytest.mark.parametrize("impl", [2, 5, 20])
def test_monotonic_in_the_direction_of_change(start, end, impl):
    points = s_curve(start, end, impl, 0)
    steps = [b - a for a, b in zip(points, points[1:])]
    assert all(step * (end - start) > 0 for step in steps)


@pytest.mark.parametrize("impl", [1, 2, 5, 7, 20])
def test_symmetric_about_midpoint(impl):
    for t in range(impl + 1):
        assert math.isclose(s_curve_fraction(t, impl) + s_curve_fraction(impl - t, impl), 1.0, abs_tol=1e-12)


@pytest.mark.parametrize("interim_values", [False, True])
@pytest.mark.parametrize("impl,cap", [(1, 0), (1, 5), (5, 15), (20, 0)])
def test_length_matches_other_dynamics(impl, cap, interim_values):
    lengths = {
        function: len(compute_yearly_or_half_year_cumulative(10.0, 0.0, impl, cap, function, interim_values=interim_values))
        for function in ("linear", "exponential", "immediate", "s-curve")
    }
    assert len(set(lengths.values())) == 1, lengths


def test_interim_values_are_half_year_averages():
    points = s_curve(0.0, 100.0, 5, 2)
    assert s_curve(0.0, 100.0, 5, 2, interim_values=True) == [(a + b) / 2 for a, b in zip(points, points[1:])]


def test_one_year_implementation_matches_linear():
    assert s_curve(80.0, 20.0, 1, 4) == compute_yearly_or_half_year_cumulative(80.0, 20.0, 1, 4, "linear", interim_values=False)


def test_zero_year_implementation_is_already_at_end_value():
    assert s_curve(80.0, 20.0, 0, 3) == [20.0] * 4


def test_flows_through_delta_and_matrix_helpers():
    assert len(compute_luc_hectare_delta(0.0, 100.0, 5, 5, "s-curve")) == 10
    assert compute_yearly_cumulative_matrix(0.0, 100.0, 5, 5, "s-curve").shape == (5, 10)
    assert compute_matrix_for_log_rec_dis(100.0, 0.0, 5, 5, "s-curve").shape == (5, 10)


@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_within_tolerance_of_next_logistic(scenario_id, side):
    scenario = SCENARIOS[scenario_id]
    inputs = scenario["inputs"]
    x0, x1, impl = inputs["x0"], inputs[SIDES[side]], inputs["time"]
    actual = s_curve(x0, x1, impl, inputs["time2"])
    expected = scenario["logistic"][side]
    assert len(actual) == len(expected)

    tolerance = PARITY_REL_TOL * abs(x1 - x0)
    for t, (a, e) in enumerate(zip(actual, expected)):
        assert abs(a - e) <= tolerance + 1e-9, f"t={t}: {a} vs NEXT {e}"
    assert_series_close(actual[impl:], expected[impl:], label=f"{scenario_id}/{side} from t = T")
