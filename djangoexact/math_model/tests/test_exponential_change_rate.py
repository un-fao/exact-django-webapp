import math

import pytest

from math_model.no_time_dependency_final.general_functions import compute_yearly_or_half_year_cumulative


def points(start, end, years, capitalization=0, function="exponential"):
    return compute_yearly_or_half_year_cumulative(start, end, years, capitalization, function, interim_values=False)


def normalised_area(start, end, years):
    # Mean of the yearly midpoint values, as a share of the change: what the results actually sum.
    interim = compute_yearly_or_half_year_cumulative(start, end, years, 0, "exponential", interim_values=True)
    return sum((v - start) / (end - start) for v in interim) / years


@pytest.mark.parametrize("start,end", [(10, 30), (0, 30), (10, 0), (30, 10), (-5, 5)])
@pytest.mark.parametrize("years", [1, 2, 5, 20])
def test_endpoints_are_exact(start, end, years):
    series = points(start, end, years, capitalization=3)
    assert series[0] == start
    assert series[years] == end
    assert series[years:] == [end] * 4


@pytest.mark.parametrize("start,end", [(10, 30), (0, 30), (30, 10), (10, 0)])
def test_monotonic_and_front_loaded(start, end):
    series = points(start, end, 10)
    steps = [b - a for a, b in zip(series, series[1:])]
    sign = 1 if end > start else -1
    assert all(sign * s > 0 for s in steps)
    assert all(abs(a) > abs(b) for a, b in zip(steps, steps[1:]))


def test_increasing_from_non_zero_start_stays_within_range():
    # Before the fix 10 -> 30 over 5 years ended at 40.
    series = points(10, 30, 5)
    assert series[-1] == 30
    assert all(10 <= v <= 30 for v in series)


def test_decreasing_runs_from_start_to_end():
    # Before the fix 10 -> 0 ran 0 -> 10.
    series = points(10, 0, 5)
    assert series[0] == 10 and series[-1] == 0


def test_decreasing_mirrors_increasing():
    up = points(0, 1, 7)
    down = points(1, 0, 7)
    assert down == pytest.approx([1 - v for v in up])


def test_continuous_area_is_excel_coefficient():
    # EX-ACT Excel "list" sheet: exponential dynamic coefficient 0.78 (linear 0.5, immediate 1).
    c = -4.270296
    area = (1 - (math.exp(c) - 1) / c) / (1 - math.exp(c))
    assert area == pytest.approx(0.78, abs=1e-6)


@pytest.mark.parametrize("years,expected", [(1, 0.5), (5, 0.7659), (10, 0.7765), (20, 0.7791)])
def test_yearly_area_converges_to_coefficient(years, expected):
    # Yearly midpoint averaging can only approximate the continuous 0.78; with one year it is the straight line.
    assert normalised_area(10, 30, years) == pytest.approx(expected, abs=1e-4)
    assert normalised_area(30, 10, years) == pytest.approx(expected, abs=1e-4)


def test_linear_and_immediate_unchanged():
    assert points(10, 30, 4, 2, "linear") == [10, 15, 20, 25, 30, 30, 30]
    assert points(30, 10, 4, 0, "linear") == [30, 25, 20, 15, 10]
    assert points(10, 30, 2, 1, "immediate") == [30, 30, 30, 30]
