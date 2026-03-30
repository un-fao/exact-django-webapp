"""Unified emissions extractor replacing the two duplicated methods in BaseModuleReport."""

from __future__ import annotations

from itertools import zip_longest
from typing import Any

import logging as log


def _add(a: list[float], b: list[float]) -> list[float]:
    """Element-wise addition of two float lists, zero-filling the shorter one."""
    return list(map(sum, zip_longest(a, b, fillvalue=0)))


def extract_emissions(
    source: list | dict,
    activity_type: Any = None,
    gas_type: Any = None,
    excluded_activity_types: list | None = None,
    excluded_gas_types: list | None = None,
    duration: int = 0,
) -> list[float]:
    """Extract and sum emissions from a queryset result or dict keyed by index.

    Args:
        source: Either a list of ``YearlyGasActivityEmissionSet`` objects
                (with ``.activity``, ``.gas_type``, ``.emissions`` attributes)
                or a dict whose values are dicts with the same keys.
        activity_type: Filter to this activity type (or None for all).
        gas_type: Filter to this gas type (or None for all).
        excluded_activity_types: Skip entries whose activity is in this list.
        excluded_gas_types: Skip entries whose gas_type is in this list.
        duration: Fallback zero-list length when source is empty.

    Returns:
        Summed list of floats, one entry per year.
    """
    excluded_activity_types = excluded_activity_types or []
    excluded_gas_types = excluded_gas_types or []

    zeros = [0.0] * duration
    emissions: list[list[float]] = [zeros]

    if isinstance(source, dict):
        entries = source.values()
        get_activity = lambda e: e.get("activity")
        get_gas = lambda e: e.get("gas_type")
        get_values = lambda e: [v["value"] for v in e.get("emissions", [])]
    else:
        entries = source
        get_activity = lambda e: e.activity
        get_gas = lambda e: e.gas_type
        get_values = lambda e: [v.value for v in e.emissions]

    for entry in entries:
        e_activity = get_activity(entry)
        e_gas = get_gas(entry)

        if e_activity in excluded_activity_types or e_gas in excluded_gas_types:
            continue

        if activity_type is not None and gas_type is not None:
            if e_activity == activity_type and e_gas == gas_type:
                log.debug(f"Found emissions for {activity_type} / {gas_type}")
                emissions.append(get_values(entry))
        elif activity_type is not None:
            if e_activity == activity_type:
                log.debug(f"Found emissions for {e_activity} / {e_gas}")
                emissions.append(get_values(entry))
        elif gas_type is not None:
            if e_gas == gas_type:
                log.debug(f"Found emissions for {e_activity} / {e_gas}")
                emissions.append(get_values(entry))
        else:
            log.debug("Extracting all emissions (no filter)")
            emissions.append(get_values(entry))

    return list(map(sum, zip_longest(*emissions, fillvalue=0)))
