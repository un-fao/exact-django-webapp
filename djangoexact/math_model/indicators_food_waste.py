"""Food-waste indicators: food waste generated, landfilled, composted and digested, with and without the project.

Pure functions, no Django. Inputs are the ``food_waste_by_route`` blocks of the solid waste module results
(t wet weight per year, one series per route group and scenario, index 0 = project start year).

Every indicator is a yearly series. A reduction is reference minus target, so a project that cuts food waste
shows a positive reduction.
"""

from __future__ import annotations

from math_model.no_time_dependency_final.solid_waste import ANAEROBIC_DIGESTION, COMPOSTING, FOOD_WASTE_ROUTE_GROUPS

SCENARIOS = ("w", "wo")
LANDFILL = "swds"


def _fit(series: list[float], duration: int) -> list[float]:
    return (list(series) + [0.0] * duration)[:duration]


def sum_by_route(blocks: list[dict], duration: int) -> dict[str, dict[str, list[float]]]:
    """Sum ``{"w": {route: [...]}, "wo": {...}}`` blocks over modules, each series cut or zero-padded to ``duration``."""
    total = {s: {route: [0.0] * duration for route in FOOD_WASTE_ROUTE_GROUPS} for s in SCENARIOS}
    for block in blocks:
        for s in SCENARIOS:
            for route, series in (block.get(s) or {}).items():
                if route in total[s]:
                    total[s][route] = [a + b for a, b in zip(total[s][route], _fit(series, duration))]
    return total


def food_waste_series(by_route: dict[str, dict[str, list[float]]]) -> dict[str, list[float]]:
    """Yearly series of every food-waste indicator from the summed routes."""

    def generated(s):
        return [sum(values) for values in zip(*by_route[s].values())]

    def diff(a, b):
        return [x - y for x, y in zip(a, b)]

    out = {"generated_w": generated("w"), "generated_wo": generated("wo")}
    out["reduction"] = diff(out["generated_wo"], out["generated_w"])
    out["landfill_w"] = by_route["w"][LANDFILL]
    out["landfill_wo"] = by_route["wo"][LANDFILL]
    out["landfill_reduction"] = diff(out["landfill_wo"], out["landfill_w"])
    for key, route in (("composting", COMPOSTING), ("anaerobic_digestion", ANAEROBIC_DIGESTION)):
        out[f"{key}_w"] = by_route["w"][route]
        out[f"{key}_wo"] = by_route["wo"][route]
    return out
