"""Rewetting of inland wetland mineral soils (IWMS) on land modules.

Reference values come from the IPCC 2013 Wetlands Supplement, chapter 5 (Inland Wetland Mineral Soils):

- Table 5.4: EF CH4 for managed lands with IWMS where the water table has been raised, kg CH4/ha/yr, by climate
  region (boreal 76, temperate 235, tropical 900).
- Table 5.3: FLU for rewetting of Cropland with IWMS, 0.80 for years 1-20 and 1.0 for years 21-40.

The flags are off by default; with all of them off, or on a non-wetland soil, the calculators get the same inputs
as before.
"""

from rest_framework import serializers

from ipcc.models import FLUData

WETLAND_SOIL = "Wetland"

EF_CH4_IWMS_BY_CLIMATE = {
    "Boreal": 76.0,
    "Cool Temperate": 235.0,
    "Warm Temperate": 235.0,
    "Tropical": 900.0,
    "Tropical Montane": 900.0,
}

FLU_REWETTED_YEARS_1_20 = 0.80
FLU_REWETTED_YEARS_21_40 = 1.0

# Table 5.3 is given for Cropland only; for Grassland and Other Land the 2006 Guidelines factors stay in force.
CROPLAND_CLASSES = {"AnnualCropland", "PerennialCropland", "SetAside"}

REWETTING_FIELDS = ("is_rewetted_start", "is_rewetted_w", "is_rewetted_wo")


def is_wetland_soil(soil_type) -> bool:
    """Compared on the untranslated name: `name` follows the request language under modeltranslation."""
    return soil_type is not None and soil_type.name_en == WETLAND_SOIL


def activity_soil_type(activity):
    return activity.soil_type_t2 or activity.project.soil_type


def validate_rewetting(data: dict, activity) -> None:
    """Reject setting a rewetted flag when the activity is not on Wetland soil (HTTP 400).

    Only flags turned on in this request are checked, so a flag left stale by a later soil change does not
    block unrelated edits (the calculation ignores it).
    """
    flagged = [field for field in REWETTING_FIELDS if data.get(field)]
    if flagged and not is_wetland_soil(activity_soil_type(activity)):
        raise serializers.ValidationError(
            {field: "Rewetting applies only to inland wetland mineral soils: set the activity soil type to Wetland first." for field in flagged}
        )


def _flags(calculator, scenario: str) -> tuple[bool, bool, object]:
    end_module = calculator.module_w if scenario == "w" else calculator.module_wo
    rewetted_start = bool(getattr(calculator.module_start, "is_rewetted_start", False))
    rewetted_end = bool(getattr(end_module, f"is_rewetted_{scenario}", False))
    return rewetted_start, rewetted_end, end_module


def apply_rewetted_flu(calculator) -> None:
    """Swap the Tier 1 FLU of rewetted Cropland scenarios for Table 5.3 years 1-20, so defaults and results agree.

    A user FLU tier 2 still wins, as for any other FLU.
    """
    if not is_wetland_soil(calculator.soil_type):
        return
    if getattr(calculator.module_start, "is_rewetted_start", False) and type(calculator.module_start).__name__ in CROPLAND_CLASSES:
        calculator.flu_start = FLUData(value=FLU_REWETTED_YEARS_1_20)
    for scenario in ("w", "wo"):
        _, rewetted_end, end_module = _flags(calculator, scenario)
        if rewetted_end and type(end_module).__name__ in CROPLAND_CLASSES:
            setattr(calculator, f"flu_{scenario}", FLUData(value=FLU_REWETTED_YEARS_1_20))


def rewetting_inputs(calculator, scenario: str) -> dict:
    """Extra math LandModule kwargs for the transition from start to `scenario` ("w" or "wo").

    Returns {} when nothing is rewetted, so legacy inputs are untouched. Stale flags on a soil that is no
    longer Wetland are ignored rather than raised, so changing the activity soil never breaks a calculation.
    """
    if not is_wetland_soil(calculator.soil_type):
        return {}

    rewetted_start, rewetted_end, end_module = _flags(calculator, scenario)
    if not (rewetted_start or rewetted_end):
        return {}

    climate = calculator.climate.name_en
    if climate not in EF_CH4_IWMS_BY_CLIMATE:
        raise ValueError(f"No IWMS rewetting CH4 emission factor for {climate} climate.")

    inputs = {
        "iwms_rewetted_start": rewetted_start,
        "iwms_rewetted_end": rewetted_end,
        "ef_ch4_iwms": EF_CH4_IWMS_BY_CLIMATE[climate],
        "methane_constant": calculator.project.gwp.ch4,
    }
    if rewetted_end and type(end_module).__name__ in CROPLAND_CLASSES:
        inputs["iwms_flu_after_20"] = FLU_REWETTED_YEARS_21_40
    return inputs
