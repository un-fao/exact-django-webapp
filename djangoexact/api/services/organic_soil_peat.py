"""Peat extraction quantity inputs and drainage water-table classes for OrganicSoil.

Ported from NEXT's WETLAND sheet (PEAT EXTRACTION block and water-table columns). Both features are
opt-in: with their fields null, the calculator gets exactly the inputs it got before.
"""

from math_model.no_time_dependency_final.inlands import PEAT_UNIT_VOLUME

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


def default_carbon_fraction(conversion) -> float:
    """tC per tonne of air-dry peat, IPCC 2006 V4 Ch7 Table 7.5 (PeatExtractionConversionFactor.weight)."""
    return conversion.weight


def default_bulk_density(conversion):
    """Air-dry tonnes per m3 implied by Table 7.5: (tC/m3) / (tC/t). Keeps volume inputs on the IPCC volume factor."""
    return conversion.volume / conversion.weight if conversion.weight else None


def peat_offsite_inputs(module, scenario: str, conversion) -> dict:
    """Extra PeatExtraction kwargs for the quantity path, or {} so legacy projects keep the extraction-height path."""
    if module.peat_quantity_unit is None:
        return {}

    def carbon_fraction(s):
        t2 = getattr(module, f"peat_carbon_fraction_t2_{s}")
        return default_carbon_fraction(conversion) if t2 is None else t2

    def bulk_density(s):
        t2 = getattr(module, f"peat_bulk_density_t2_{s}")
        if t2 is not None or module.peat_quantity_unit != PEAT_UNIT_VOLUME:
            return t2 or 0.0
        default = default_bulk_density(conversion)
        if default is None:
            raise ValueError(f"Could not find a peat bulk density for {module.peat_type}. Please provide tier 2 values.")
        return default

    def counted(s):
        return module.include_energy_peat_offsite or not getattr(module, f"is_peat_for_energy_{s}")

    return {
        "quantity_unit": module.peat_quantity_unit,
        "quantity_start": module.peat_quantity_start or 0.0,
        "quantity_end": getattr(module, f"peat_quantity_{scenario}") or 0.0,
        "carbon_fraction_start": carbon_fraction("start"),
        "carbon_fraction_end": carbon_fraction(scenario),
        "bulk_density_start": bulk_density("start"),
        "bulk_density_end": bulk_density(scenario),
        "offsite_counted_start": counted("start"),
        "offsite_counted_end": counted(scenario),
    }
