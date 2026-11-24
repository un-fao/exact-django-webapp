"""Reference series for the change-rate dynamics and helpers to compare math_model output to them.

Goldens live in ``goldens/`` as plain JSON, so tests stay DB-free. Each golden
scenario stores one point per integer year t
(t = 0..time_tot, no half-year averaging), so it lines up with
``compute_yearly_or_half_year_cumulative(..., interim_values=False)``.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.general_functions import average_yearly_value  # noqa: E402

GOLDENS_DIR = os.path.join(os.path.dirname(__file__), "goldens")


def load_golden(name: str) -> dict:
    """Return the parsed ``goldens/<name>.json``."""
    with open(os.path.join(GOLDENS_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def expected_series(scenario: dict, function: str, side: str = "with", interim_values: bool = False) -> list:
    """Reference points for one scenario, mid-year averaged like EX-ACT when ``interim_values`` is set."""
    points = scenario[function][side]
    return average_yearly_value(points) if interim_values else points


def assert_series_close(actual, expected, rel_tol: float = 1e-9, abs_tol: float = 1e-9, label: str = "") -> None:
    """Assert two yearly series have the same length and match point by point."""
    assert len(actual) == len(expected), f"{label}: length {len(actual)} != {len(expected)}"
    bad = [
        (t, a, e)
        for t, (a, e) in enumerate(zip(actual, expected))
        if not math.isclose(a, e, rel_tol=rel_tol, abs_tol=abs_tol)
    ]
    assert not bad, f"{label}: {len(bad)} point(s) differ, first (t, actual, expected): {bad[0]}"
