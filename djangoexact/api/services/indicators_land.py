"""Land indicator groups: land use change, mineral soils, 4 per 1000, forest.

ORM and cached-result reads only; the math is in math_model/indicators.py.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

import api.models as api_models
import ipcc.models as ipcc_models
import math_model.indicators as mi
import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils
from api.reports.extractors import _add, extract_emissions
from api.services.indicators import IndicatorContext, indicator, register_group

# IPCC 2006 Vol 4 Ch 3 land categories. Set-aside is cropland taken out of
# production (Ch 5); coastal wetlands follow the 2013 Wetlands Supplement Ch 4.
CATEGORY_BY_MODULE = {
    "ForestManagement": "forest",
    "AnnualCropland": "cropland",
    "PerennialCropland": "cropland",
    "FloodedRice": "cropland",
    "SetAside": "cropland",
    "Grassland": "grassland",
    "CoastalWetland": "wetlands",
    "Settlement": "settlements",
    "OtherLand": "other_land",
}

CATEGORY_LABELS = {
    "forest": _("Forest"),
    "cropland": _("Cropland"),
    "grassland": _("Grassland"),
    "wetlands": _("Wetlands"),
    "settlements": _("Settlements"),
    "other_land": _("Other land"),
}


def _parcels(modules) -> list[mi.LandParcel]:
    parcels = []
    luc = next((m for m in modules if isinstance(m, api_models.LandUseChange)), None)
    if luc is not None:
        categories = [CATEGORY_BY_MODULE.get(mt.class_name) for mt in luc.get_module_types()]
        if luc.area and all(categories):
            parcels.append(mi.LandParcel(*categories, luc.area))
    else:
        # One parcel per activity, like Activity.get_land_modules_area: further
        # land modules (organic soil, minor seasons) describe the same hectares.
        land = next(
            (m for m in modules if isinstance(m, api_models.LandModule) and type(m).__name__ in CATEGORY_BY_MODULE and m.area),
            None,
        )
        if land is not None:
            category = CATEGORY_BY_MODULE[type(land).__name__]
            parcels.append(mi.LandParcel(category, category, category, land.area))
    for m in modules:
        if isinstance(m, api_models.CoastalWetland) and m.area and m.area > 0:
            parcels.append(mi.LandParcel("wetlands", "wetlands", "wetlands", m.area))
    return parcels


def _soc_ref(activity) -> float | None:
    """Mineral SOC reference stock (tC/ha): Tier 2 if given, else IPCC 2019 Vol 4 Ch 2 Table 2.3."""
    if activity.soc:
        return activity.soc
    project = activity.project
    climate = activity.climate_t2 or project.climate
    moisture = activity.moisture_t2 or project.moisture
    soil_type = activity.soil_type_t2 or project.soil_type
    if not (climate and moisture and soil_type):
        return None
    row = ipcc_models.SoilOrganicCarbon.objects.filter(climate=climate, moisture=moisture, soil_type=soil_type).first()
    return row.value if row and row.value else None


def _soil_co2(reports, attr: str, duration: int) -> list[float]:
    total: list[float] = []
    for report in reports:
        total = _add(total, extract_emissions(
            getattr(report, attr) or [],
            math_utils.ActivityTypes.SOIL_CO2_CHANGE,
            math_utils.GasTypes.CO2,
            duration=duration,
        ))
    return total


def land_activities(ctx: IndicatorContext) -> list[mi.ActivityLand]:
    def read():
        out = []
        for ar in ctx.activity_results:
            activity = ar._activity
            if activity is None:
                continue
            parcels = _parcels(activity.modules)
            if not parcels:
                continue
            out.append(mi.ActivityLand(
                id=activity.pk,
                name=activity.name,
                parcels=parcels,
                start_year=activity.start_year,
                implementation_years=activity.implementation_years,
                soil_co2_w=_soil_co2(ar._module_reports, "emissions_set_w", ctx.duration),
                soil_co2_wo=_soil_co2(ar._module_reports, "emissions_set_wo", ctx.duration),
                soc_ref=_soc_ref(activity),
                has_soil_results=True,
            ))
        return out

    return ctx.memo("land_activities", read)


def _years(ctx: IndicatorContext, n: int) -> list[int]:
    return list(range(ctx.start_year, ctx.start_year + n))


@register_group("land_use_change_matrix", _("Land use change matrix"), order=10)
def land_use_change_matrix(ctx: IndicatorContext) -> dict | None:
    activities = land_activities(ctx)
    if not activities:
        return None
    matrix = mi.land_use_matrix(activities)
    return {
        "indicators": [
            indicator(
                "converted_area", _("Area changing land use"), "ha",
                with_=mi.converted_area(matrix["with"]),
                without=mi.converted_area(matrix["without"]),
            ),
        ],
        "data": {
            "categories": [{"id": c, "label": CATEGORY_LABELS[c]} for c in mi.LAND_CATEGORIES],
            "with": matrix["with"],
            "without": matrix["without"],
        },
    }


@register_group("soil_carbon", _("Soil organic carbon"), order=20)
def soil_carbon(ctx: IndicatorContext) -> dict | None:
    activities = land_activities(ctx)
    summary = mi.soil_carbon_summary(activities)
    if not summary["activities"]:
        return None
    totals = summary["totals"]
    series = mi.soc_stock_change_series(activities)
    labels = {
        "preserved": (_("SOC preserved"), _("Area with SOC preserved")),
        "enhanced": (_("SOC enhanced"), _("Area with SOC enhanced")),
        "lost": (_("SOC lost"), _("Area with SOC lost")),
    }
    indicators = []
    for cls, (tc_label, area_label) in labels.items():
        indicators.append(indicator(f"soc_{cls}", tc_label, "tC", value=totals[cls]["tc"]))
        indicators.append(indicator(f"soc_{cls}_area", area_label, "ha", value=totals[cls]["area"]))
    indicators.append(indicator(
        "soc_stock_change", _("Cumulative SOC stock change"), "tC",
        with_=series["with"][-1] if series["with"] else 0.0,
        without=series["without"][-1] if series["without"] else 0.0,
        series={"years": _years(ctx, len(series["with"])), **series},
    ))
    return {"indicators": indicators, "data": {"activities": summary["activities"]}}


@register_group("four_per_1000", _("4 per 1000"), order=30)
def four_per_1000(ctx: IndicatorContext) -> dict | None:
    result = mi.four_per_1000(land_activities(ctx), ctx.duration)
    if not result["activities"]:
        return None
    return {
        "indicators": [
            indicator(
                "soc_relative_rate", _("Annual SOC stock increase"), "%/yr",
                with_=result["relative_pct_yr"], target=result["target_pct_yr"],
            ),
            indicator("soc_absolute_rate", _("Annual SOC sequestration"), "tC/ha/yr", with_=result["rate_tc_ha_yr"]),
        ],
        "data": {"activities": result["activities"]},
    }


def _touches_forest(activities: list[mi.ActivityLand]) -> bool:
    return any(mi.FOREST in (p.start, p.with_, p.without) for a in activities for p in a.parcels)


@register_group("forest_cover", _("Forest cover"), order=40)
def forest_cover(ctx: IndicatorContext) -> dict | None:
    activities = land_activities(ctx)
    if not _touches_forest(activities):
        return None
    cover = mi.forest_cover(activities)
    return {
        "indicators": [
            indicator("forest_area", _("Forest area"), "ha", start=cover["start"], with_=cover["with"], without=cover["without"]),
            indicator("forest_area_change", _("Forest area gained by the project"), "ha", value=cover["with"] - cover["without"]),
            indicator("forest_soc_loss", _("Forest SOC loss"), "tC", value=mi.forest_soc_loss(activities)),
        ],
    }


@register_group("net_zero_deforestation", _("Net-zero deforestation"), order=50)
def net_zero_deforestation(ctx: IndicatorContext) -> dict | None:
    result = mi.net_zero_deforestation(land_activities(ctx))
    if not (result["deforested_with"] or result["deforested_without"]):
        return None
    return {
        "indicators": [
            indicator("net_zero_deforestation_year", _("Net-zero deforestation year"), "year", value=result["year"]),
            indicator(
                "deforested_area", _("Deforested area"), "ha",
                with_=result["deforested_with"], without=result["deforested_without"],
            ),
        ],
    }
