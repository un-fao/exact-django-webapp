"""Project land indicators ported from NEXT's AGRIFOOD INDICATORS sheet.

Pure functions over plain dataclasses, no Django. The service layer
(api/services/indicators_land.py) reads the ORM and the cached module results
and builds the ActivityLand inputs.

Sign convention: soil CO2 values are emissions in tCO2 (positive = the soil
loses carbon, negative = the soil gains carbon), as in the module results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LAND_CATEGORIES = ("forest", "cropland", "grassland", "wetlands", "settlements", "other_land")
FOREST = "forest"

C_PER_CO2 = 12 / 44
FOUR_PER_1000_TARGET_PCT = 0.4


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
    start_year: int = 0
    implementation_years: int = 0
    soil_co2_w: list[float] = field(default_factory=list)
    soil_co2_wo: list[float] = field(default_factory=list)
    soc_ref: float | None = None
    has_soil_results: bool = False

    @property
    def area(self) -> float:
        return sum(p.area for p in self.parcels)

    @property
    def starts_in_forest(self) -> bool:
        return any(p.start == FOREST for p in self.parcels)


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


def classify_soc(soil_w: float, soil_wo: float) -> tuple[str | None, float]:
    """Classify an activity's soil carbon outcome and return (class, tC).

    NEXT ('Ag land' rows 1713-1801) compares the target and reference soil CO2
    flux of each activity: enhanced when both are sinks and the target sinks
    more, preserved when both are sources and the target emits less, lost when
    both are sources and the target emits more. NEXT drops the mixed-sign
    cases; here they are kept so every activity lands in one class: a better
    outcome counts as enhanced when the with-project soil is a net sink, else
    preserved, and any worse outcome counts as lost.
    """
    delta = soil_w - soil_wo
    if delta == 0:
        return None, 0.0
    tc = abs(delta) * C_PER_CO2
    if delta > 0:
        return "lost", tc
    return ("enhanced" if soil_w < 0 else "preserved"), tc


def soil_carbon_summary(activities: list[ActivityLand]) -> dict:
    totals = {k: {"area": 0.0, "tc": 0.0} for k in ("preserved", "enhanced", "lost")}
    rows = []
    for a in activities:
        if not a.has_soil_results or a.area <= 0:
            continue
        cls, tc = classify_soc(sum(a.soil_co2_w), sum(a.soil_co2_wo))
        rows.append({"id": a.id, "name": a.name, "area": a.area, "class": cls, "tc": tc})
        if cls:
            totals[cls]["area"] += a.area
            totals[cls]["tc"] += tc
    return {"totals": totals, "activities": rows}


def soc_stock_change_series(activities: list[ActivityLand]) -> dict[str, list[float]]:
    """Cumulative SOC stock change in tC per year (positive = gain), summed over activities."""
    def cumulative(values):
        out, running = [], 0.0
        for v in values:
            running += -v * C_PER_CO2
            out.append(running)
        return out

    w: list[float] = []
    wo: list[float] = []
    for a in activities:
        if not a.has_soil_results:
            continue
        w = _add(w, a.soil_co2_w)
        wo = _add(wo, a.soil_co2_wo)
    return {"with": cumulative(w), "without": cumulative(wo)}


def four_per_1000(activities: list[ActivityLand], years: int) -> dict:
    """Annual SOC stock increase of the with-project scenario against the 0.4 %/yr target.

    NEXT (Land!BT64, BT78-80) divides the annual enhanced SOC (tCO2) by the
    area with increased SOC and converts to tC/ha/yr. EX-ACT also knows the
    reference SOC stock of each activity, so the rate is additionally expressed
    relative to it (tC/ha/yr / SOCref), which is what the 4 per 1000 target
    measures. Activities without a SOCref get no relative rate.
    """
    rows = []
    gain_total = 0.0
    stock_total = 0.0
    area_total = 0.0
    for a in activities:
        if not a.has_soil_results or a.area <= 0 or years <= 0:
            continue
        gain_tc_yr = -sum(a.soil_co2_w) * C_PER_CO2 / years
        rate = gain_tc_yr / a.area
        relative = rate / a.soc_ref * 100 if a.soc_ref else None
        rows.append({
            "id": a.id,
            "name": a.name,
            "area": a.area,
            "rate_tc_ha_yr": rate,
            "relative_pct_yr": relative,
            "target_pct_yr": FOUR_PER_1000_TARGET_PCT,
            "meets_target": relative is not None and relative >= FOUR_PER_1000_TARGET_PCT,
        })
        area_total += a.area
        gain_total += gain_tc_yr
        if a.soc_ref:
            stock_total += a.soc_ref * a.area
    return {
        "rate_tc_ha_yr": gain_total / area_total if area_total else None,
        "relative_pct_yr": gain_total / stock_total * 100 if stock_total else None,
        "target_pct_yr": FOUR_PER_1000_TARGET_PCT,
        "activities": rows,
    }


def forest_cover(activities: list[ActivityLand]) -> dict[str, float]:
    out = {"start": 0.0, "with": 0.0, "without": 0.0}
    for a in activities:
        for p in a.parcels:
            out["start"] += p.area if p.start == FOREST else 0.0
            out["with"] += p.area if p.with_ == FOREST else 0.0
            out["without"] += p.area if p.without == FOREST else 0.0
    return out


def forest_soc_loss(activities: list[ActivityLand]) -> float:
    """tC of soil carbon lost on land that is forest at start (NEXT 'Forest SOC loss', Land!BT19)."""
    summary = soil_carbon_summary([a for a in activities if a.starts_in_forest])
    return summary["totals"]["lost"]["tc"]


def net_zero_deforestation(activities: list[ActivityLand]) -> dict:
    """First year with no gross deforestation in the with-project scenario.

    NEXT (DASHBOARD!I20 over 'FOREST LAND' T/U/X) returns the target year of
    the implementation period when the target still deforests, the base year
    when only the reference deforests, and N/A when neither does. Here the
    conversion of each activity runs over its implementation years, so the
    first year without it is start_year + implementation_years.
    """
    deforested = {"with": 0.0, "without": 0.0}
    year = None
    for a in activities:
        for p in a.parcels:
            if p.start != FOREST:
                continue
            w = p.with_ != FOREST
            wo = p.without != FOREST
            deforested["with"] += p.area if w else 0.0
            deforested["without"] += p.area if wo else 0.0
            if w:
                candidate = a.start_year + a.implementation_years
            elif wo:
                candidate = a.start_year
            else:
                continue
            year = candidate if year is None else max(year, candidate)
    return {"year": year, "deforested_with": deforested["with"], "deforested_without": deforested["without"]}


def _add(a: list[float], b: list[float]) -> list[float]:
    n = max(len(a), len(b))
    return [(a[i] if i < len(a) else 0.0) + (b[i] if i < len(b) else 0.0) for i in range(n)]
