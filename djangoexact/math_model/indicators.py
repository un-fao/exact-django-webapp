"""Project land indicators: the land use change matrix.

Pure functions over plain dataclasses, no Django. The service layer
(api/services/indicators_land.py) reads the ORM and builds the ActivityLand inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LAND_CATEGORIES = ("forest", "cropland", "grassland", "wetlands", "settlements", "other_land")


@dataclass
class LandParcel:
    """An area of land with its IPCC land category at start, with and without project."""

    start: str
    with_: str
    without: str
    area: float


@dataclass
class ActivityLand:
    id: int
    name: str
    parcels: list[LandParcel] = field(default_factory=list)


def land_use_matrix(activities: list[ActivityLand]) -> dict[str, list[list[float]]]:
    """Hectares from each start category (row) to each end category (column), per scenario."""
    index = {c: i for i, c in enumerate(LAND_CATEGORIES)}
    n = len(LAND_CATEGORIES)
    out = {"with": [[0.0] * n for _ in range(n)], "without": [[0.0] * n for _ in range(n)]}
    for activity in activities:
        for p in activity.parcels:
            out["with"][index[p.start]][index[p.with_]] += p.area
            out["without"][index[p.start]][index[p.without]] += p.area
    return out


def converted_area(matrix: list[list[float]]) -> float:
    return sum(v for i, row in enumerate(matrix) for j, v in enumerate(row) if i != j)
