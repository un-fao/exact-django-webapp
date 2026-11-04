"""Land indicator group: the land use change matrix.

ORM reads only; the math is in math_model/indicators.py.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

import api.models as api_models
import math_model.indicators as mi
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


def land_activities(ctx: IndicatorContext) -> list[mi.ActivityLand]:
    out = []
    for ar in ctx.activity_results:
        activity = ar._activity
        if activity is None:
            continue
        parcels = _parcels(activity.modules)
        if parcels:
            out.append(mi.ActivityLand(id=activity.pk, name=activity.name, parcels=parcels))
    return out


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
