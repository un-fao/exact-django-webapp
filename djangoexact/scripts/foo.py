import api.models as models

# TODO: Run in review and prod


# Add Climate Tropical Montane to all LandUseTypes with module_type "Perennial Cropland"
def add_climate_tropical_montane_to_perennial_cropland():
    """
    Add Climate Tropical Montane to all LandUseTypes with module_type "Perennial Cropland"
    """
    perennial_cropland = models.LandUseType.objects.filter(module_types__name="Perennial Cropland")
    climate_tropical_montane = models.Climate.objects.get(name="Tropical Montane")

    for land_use_type in perennial_cropland:
        land_use_type.climates.add(climate_tropical_montane)
        land_use_type.save()


add_climate_tropical_montane_to_perennial_cropland()
