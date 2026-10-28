"""Drainage water-table classes for OrganicSoil.

Opt-in: with the class null, the calculator keeps the fixture EFs (the mean of the two classes).
"""

# Drainage EFs for temperate nutrient-rich grassland by water-table depth, IPCC 2013 Wetlands Supplement,
# chapter 2: Table 2.1 (CO2, tCO2-C/ha/yr), Table 2.3 (CH4, kg CH4/ha/yr), Table 2.5 (N2O, kg N2O-N/ha/yr).
# No other land use, climate or nutrient status is split by water-table depth in those tables, and the
# fixture rows for this case hold the mean of the two classes (CO2 4.85, CH4 27.5, N2O 4.9).
WATER_TABLE_DRAINAGE_EF = {
    "deep_drained": {"co2": 6.1, "ch4": 39.0, "n2o": 8.2},
    "shallow_drained": {"co2": 3.6, "ch4": 16.0, "n2o": 1.6},
}
WATER_TABLE_CLIMATES = {"Cool Temperate", "Warm Temperate"}


def water_table_class_applies(module_type, climate, peat_type) -> bool:
    """Compared on untranslated names: `name` follows the request language under modeltranslation."""
    return (
        module_type is not None
        and module_type.class_name == "Grassland"
        and climate is not None
        and climate.name_en in WATER_TABLE_CLIMATES
        and peat_type is not None
        and peat_type.name_en == "Nutrient Rich"
    )


def apply_water_table_class(ef, water_table_class, module_type, climate, peat_type) -> None:
    """Swap the on-site drainage Tier 1 EFs on `ef` (an unsaved ipcc row) for the class-specific ones."""
    if water_table_class is None or not water_table_class_applies(module_type, climate, peat_type):
        return
    for gas, value in WATER_TABLE_DRAINAGE_EF[water_table_class].items():
        setattr(ef, gas, value)
        setattr(ef, f"{gas}_min", None)
        setattr(ef, f"{gas}_max", None)

