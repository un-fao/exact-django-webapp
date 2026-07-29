"""Presentation-layer relabeling for Inventory result rows.

The IPCC Category wording shown to users in the online results API and in the
Excel report Inventory sheet is renamed here, at display time only. The
`ActivityTypes` enum in `math_model.no_time_dependency_final` keeps its
original raw string values: it is the identity key used for emission-set
filtering and it is what gets persisted in the per-module result caches. It
is therefore never edited, and this module never imports it.
"""

DEFAULT_LABELS = {
    "Soil CO2 Change": "Soil Carbon stocks (SOC)",
    "Soil Organic Matter": "Soil Organic mineralization",
    "Biomass": "Biomass Carbon stock",
    "AGB Growth": "AGB STOCK",
    "BGB Growth": "BGB STOCK",
    "Litter": "LITTER STOCK",
    "Deadwood": "DEAD WOOD STOCK",
    "Catch": "FISHERIES EMISSIONS (FUEL)",
    "Refrigerant": "Refrigerant emissions (CO2-eq)",
    "Ice": "Ice emissions (CO2-eq)",
    "Coastal Waterbodies": "Waterbody emissions (CH4)",
}

MODULE_OVERRIDES = {
    # "N2O Field" and "Electricity" are ActivityTypes members shared with the
    # Inputs and Electricity math modules, whose wording must not change, so
    # the rename below is scoped to Aquaculture only.
    "Aquaculture": {
        "N2O Field": "FISH EMISSION (EXCRETA)",
        "Electricity": "Electricity emissions (CO2-eq)",
    },
}


def inventory_label(module, category):
    """Resolve the display label for an inventory row's IPCC Category.

    Resolves module-specific overrides first, then the default mapping,
    then falls back to the category itself unchanged. The override is keyed
    strictly on the Python class name of `module`, never on
    `module.module_type.name`, since that field is registered with
    modeltranslation and its value changes with the active request language.
    """
    overrides = MODULE_OVERRIDES.get(type(module).__name__, {})
    if category in overrides:
        return overrides[category]
    return DEFAULT_LABELS.get(category, category)
