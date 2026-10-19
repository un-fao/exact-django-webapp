"""NEXT parity checks for the dynamics prototypes in NEXT's ``Dynamiques`` sheet.

DB-free, run with bare pytest:

    pytest djangoexact/math_model/tests/test_next_parity.py
"""

import math

import pytest
from next_parity import assert_series_close, expected_series, load_golden

from math_model.no_time_dependency_final.general_functions import compute_yearly_or_half_year_cumulative

GOLDEN = load_golden("next_dynamiques")
SCENARIOS = {s["id"]: s for s in GOLDEN["scenarios"]}
SIDES = {"with": "x_with", "without": "x_without"}


@pytest.mark.parametrize("interim_values", [False, True])
@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_linear_matches_next(scenario_id, side, interim_values):
    scenario = SCENARIOS[scenario_id]
    inputs = scenario["inputs"]
    actual = compute_yearly_or_half_year_cumulative(
        inputs["x0"], inputs[SIDES[side]], inputs["time"], inputs["time2"], "linear", interim_values=interim_values
    )
    expected = expected_series(scenario, "linear", side, interim_values=interim_values)
    assert_series_close(actual, expected, label=f"{scenario_id}/{side}/interim={interim_values}")


@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_documented_logistic_formula_reproduces_next(scenario_id, side):
    """Guards the closed form written in the golden metadata, which the S-curve port relies on."""
    scenario = SCENARIOS[scenario_id]
    inputs = scenario["inputs"]
    x0, x1, time = inputs["x0"], inputs[SIDES[side]], inputs["time"]
    offset = 1 / (1 + math.exp(5))
    documented = [
        x1 if t >= time else x0 + (x1 - x0) * (1 / (1 + math.exp(-(10 / time) * (t - time / 2))) - offset)
        for t in scenario["t"]
    ]
    assert_series_close(documented, scenario["logistic"][side], label=f"{scenario_id}/{side}")
