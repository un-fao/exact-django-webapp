"""Rewetting of inland wetland mineral soils (IWMS): reference values and soil checks.

IPCC 2013 Wetlands Supplement, chapter 5 (Inland Wetland Mineral Soils), Table 5.4: EF CH4 for managed lands with
IWMS where the water table has been raised, kg CH4/ha/yr, by climate region (boreal 76, temperate 235, tropical 900).
"""

from rest_framework import serializers

WETLAND_SOIL = "Wetland"

EF_CH4_IWMS_BY_CLIMATE = {
    "Boreal": 76.0,
    "Cool Temperate": 235.0,
    "Warm Temperate": 235.0,
    "Tropical": 900.0,
    "Tropical Montane": 900.0,
}

AREA_FIELDS = ("area_start", "area_w", "area_wo")


def is_wetland_soil(soil_type) -> bool:
    """Compared on the untranslated name: `name` follows the request language under modeltranslation."""
    return soil_type is not None and soil_type.name_en == WETLAND_SOIL


def activity_soil_type(activity):
    return activity.soil_type_t2 or activity.project.soil_type


def default_ef_ch4(climate) -> float | None:
    return EF_CH4_IWMS_BY_CLIMATE.get(climate.name_en) if climate is not None else None


def validate_areas(data: dict, activity) -> None:
    """Reject a rewetted area above zero when the activity is not on Wetland soil (HTTP 400).

    Only areas sent in this request are checked, so an area left by a later soil change does not block unrelated
    edits (the calculator then counts nothing).
    """
    flagged = [field for field in AREA_FIELDS if data.get(field)]
    if flagged and not is_wetland_soil(activity_soil_type(activity)):
        raise serializers.ValidationError(
            {field: "Rewetting applies only to inland wetland mineral soils: set the activity soil type to Wetland first." for field in flagged}
        )
