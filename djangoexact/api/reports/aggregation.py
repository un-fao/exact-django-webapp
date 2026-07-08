"""Pure-Python aggregation helpers for the report computation layer.

No Django ORM, no Excel library imports (stdlib only) so the accounting logic
can be unit-tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import zip_longest


@dataclass
class HectaresContribution:
    """One module's land-area contribution to an activity's yearly hectares.

    ``luc_group`` identifies the land-use-change group the hectares belong to:
    a LUC activity carries several land-module instances (start / with / without)
    plus a ``LandUseChange`` module, and they all describe the *same* physical
    area. All modules sharing a LUC reference carry the same ``luc_group`` so the
    area is counted once. ``None`` marks a standalone module whose hectares are
    independent (e.g. a non-LUC land module or a coastal wetland).
    """

    luc_group: object | None
    is_with: bool
    is_without: bool
    units_breakdown_w: list[float]
    units_breakdown_wo: list[float]


def cumulative_activity_hectares(
    duration: int, contributions: list[HectaresContribution]
) -> list[float]:
    """Sum an activity's yearly land hectares, counting each LUC group once.

    Mirrors ``Activity.get_land_modules_area()`` (which counts each activity's
    land area a single time, see commit 6d37c194f) so the Excel "Cumulative
    Hectares Impacted" row agrees with the app's ``total_hectares`` instead of
    double-counting a land-use-change activity's with/without land modules.

    For each contribution the *with* breakdown is preferred when the module is
    part of the with-project scenario, otherwise the *without* breakdown — the
    same selection the report has always used. A contribution with no usable
    breakdown (empty list, or neither scenario applicable) is skipped and does
    not consume its LUC group, so a later module in the same group can still
    supply the hectares.
    """
    total = [0.0] * duration
    counted_groups: set = set()

    for contrib in contributions:
        if contrib.luc_group is not None and contrib.luc_group in counted_groups:
            continue

        if contrib.is_with and contrib.units_breakdown_w:
            units = contrib.units_breakdown_w
        elif contrib.is_without and contrib.units_breakdown_wo:
            units = contrib.units_breakdown_wo
        else:
            continue

        total = list(map(sum, zip_longest(total, units, fillvalue=0)))
        if contrib.luc_group is not None:
            counted_groups.add(contrib.luc_group)

    return total
