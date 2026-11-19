"""Unified emissions extractor replacing the two duplicated methods in BaseModuleReport."""

from __future__ import annotations

from itertools import zip_longest
from typing import Any, Iterator

import logging as log


def _add(a: list[float], b: list[float]) -> list[float]:
    """Element-wise addition of two float lists, zero-filling the shorter one."""
    return list(map(sum, zip_longest(a, b, fillvalue=0)))


def _eq(val: Any, target: Any) -> bool:
    """Return True if val equals target, handling enum vs. string comparisons.

    When source data comes from the serialized cache, ``val`` may be a plain
    string while ``target`` is an enum instance. Cache serialization is
    asymmetric: activity is stored as ``e.activity.value`` but gas_type is
    stored as ``e.gas_type.name`` (see ``save_results_to_cache``), so this
    helper must accept both forms — otherwise any enum whose ``.name``
    differs from its ``.value`` (notably ``GasTypes.OTHER``: name "OTHER",
    value "Other") silently fails to match every cached entry.
    """
    return (
        val == target
        or (hasattr(target, "value") and val == target.value)
        or (hasattr(target, "name") and val == target.name)
    )


def iter_fluxes(source: list | dict) -> Iterator[tuple[Any, Any, list[float]]]:
    """Yield ``(activity, gas, yearly values)`` for each entry of an emission set, in any stored form.

    ``source`` is a list of ``YearlyGasActivityEmissionSet`` objects, the serialized cache form (a list of
    dicts whose ``gas_type`` is a ``{"name": ...}`` dict), or a dict of such dicts keyed by index.
    Activity and gas come back as stored (enums, or the cache's strings), so compare them with ``_eq``.
    """
    for e in source.values() if isinstance(source, dict) else source:
        if isinstance(e, dict):
            activity, gas, values = e.get("activity"), e.get("gas_type"), [v["value"] for v in e.get("emissions", [])]
        else:
            activity, gas, values = e.activity, e.gas_type, [v.value for v in e.emissions]
        yield activity, gas.get("name") if isinstance(gas, dict) else gas, values


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

    for e_activity, e_gas, values in iter_fluxes(source):
        if any(_eq(e_activity, ex) for ex in excluded_activity_types) or any(
            _eq(e_gas, ex) for ex in excluded_gas_types
        ):
            continue

        if activity_type is not None and gas_type is not None:
            if _eq(e_activity, activity_type) and _eq(e_gas, gas_type):
                log.debug(f"Found emissions for {activity_type} / {gas_type}")
                emissions.append(values)
        elif activity_type is not None:
            if _eq(e_activity, activity_type):
                log.debug(f"Found emissions for {e_activity} / {e_gas}")
                emissions.append(values)
        elif gas_type is not None:
            if _eq(e_gas, gas_type):
                log.debug(f"Found emissions for {e_activity} / {e_gas}")
                emissions.append(values)
        else:
            log.debug("Extracting all emissions (no filter)")
            emissions.append(values)

    return list(map(sum, zip_longest(*emissions, fillvalue=0)))
