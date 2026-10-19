"""Project balance split by NDC conditionality (NEXT DASHBOARD, "Conditionality impact").

Rolls up the per-activity results that ``ProjectViewSet.results`` already returns
with ``aggregate=gas`` (one emissions list per gas, one value per year), so the
numbers always reconcile with the gas breakdown the results page shows.
"""

from __future__ import annotations

from itertools import zip_longest

AGGREGATE_CONDITIONALITY = "conditionality"

UNCONDITIONAL = "unconditional"
CONDITIONAL = "conditional"
UNSPECIFIED = "unspecified"
GROUPS = (UNCONDITIONAL, CONDITIONAL, UNSPECIFIED)
SCENARIOS = ("total_w", "total_wo", "balance")


def _add(a: list[float], b: list[float]) -> list[float]:
    return [x + y for x, y in zip_longest(a, b, fillvalue=0.0)]


def _yearly(gas_rows) -> list[float]:
    """Sum one scenario's gas rows into a single tCO2-eq value per year.

    A module that failed to calculate carries an error string instead of rows;
    it contributes nothing, as on the results page.
    """
    if not isinstance(gas_rows, list):
        return []
    yearly: list[float] = []
    for row in gas_rows:
        yearly = _add(yearly, [e["value"] for e in row.get("emissions", [])])
    return yearly


def aggregate_by_conditionality(activities: list[dict], start_year: int) -> dict:
    """Return cumulative totals and annual series per conditionality group.

    ``activities`` are activity result payloads with ``conditionality`` and
    ``modules[].results`` in the by-gas shape. Year ``i`` of every series is
    ``start_year + i``, the same indexing the gas breakdown uses. Every group
    gets an entry, and all annual series share one length, so a client can
    stack them without padding.
    """
    series = {group: {scenario: [] for scenario in SCENARIOS} for group in GROUPS}
    for activity in activities:
        group = activity.get("conditionality") or UNSPECIFIED
        for module in activity.get("modules", []):
            results = module.get("results")
            if not isinstance(results, dict):
                continue
            for scenario in SCENARIOS:
                series[group][scenario] = _add(series[group][scenario], _yearly(results.get(scenario)))

    years = max((len(s) for g in series.values() for s in g.values()), default=0)
    out = {}
    for group, by_scenario in series.items():
        padded = {scenario: values + [0.0] * (years - len(values)) for scenario, values in by_scenario.items()}
        out[group] = {
            "cumulative": {scenario: sum(values) for scenario, values in padded.items()},
            "annual": [
                {"year": start_year + i, **{scenario: padded[scenario][i] for scenario in SCENARIOS}}
                for i in range(years)
            ],
        }
    return out
