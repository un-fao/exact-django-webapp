import api.models as models
import ipcc.models as ipcc_models

# TODO: Run in review and prod


def add_climate_tropical_montane_to_perennial_cropland():
    """
    Add Climate Tropical Montane to all LandUseTypes with module_type "Perennial Cropland"
    """
    perennial_cropland = models.LandUseType.objects.filter(module_types__name="Perennial Cropland")
    climate_tropical_montane = models.Climate.objects.get(name_en="Tropical Montane")

    for land_use_type in perennial_cropland:
        land_use_type.climates.add(climate_tropical_montane)
        land_use_type.save()


def add_0_12_to_co2_value_in_input_emission_factor():
    """
    Add 0,12 to co2_value in InputEmissionFactor if input_type__name="Urea"
    """
    urea = models.InputType.objects.get(name_en="Urea")
    input_emission_factor = ipcc_models.InputEmissionFactor.objects.filter(input_type=urea).update(co2_value=0.12)


def change_forest_agb_tropical_mountain_system_to_tropical_montane():
    """
    Change all Forest AGB Tropical Mountain System to Tropical Montane
    """
    tropical_montane_climate = models.Climate.objects.get(name_en="Tropical Montane")
    agbs = ipcc_models.ForestManagementAGB.objects.filter(climate__name="Tropical", land_use_type__name="Mountain System").update(climate=tropical_montane_climate)


def change_forest_bgb_tropical_mountain_system_to_tropical_montane():
    """
    Change all Forest AGB Tropical Mountain System to Tropical Montane
    """
    tropical_montane_climate = models.Climate.objects.get(name_en="Tropical Montane")
    agbs = ipcc_models.ForestManagementBGB.objects.filter(climate__name="Tropical", land_use_type__name="Mountain System").update(climate=tropical_montane_climate)


def change_forest_agb_growth_tropical_mountain_system_to_tropical_montane():
    """
    Change all Forest AGB Tropical Mountain System to Tropical Montane
    """
    tropical_montane_climate = models.Climate.objects.get(name_en="Tropical Montane")
    agbs = ipcc_models.ForestManagementAGBGrowth.objects.filter(climate__name="Tropical", land_use_type__name="Mountain System").update(climate=tropical_montane_climate)


# TODO: Run in prod

# add_climate_tropical_montane_to_perennial_cropland()
# add_0_12_to_co2_value_in_input_emission_factor()
# change_forest_agb_tropical_mountain_system_to_tropical_montane()
# change_forest_bgb_tropical_mountain_system_to_tropical_montane()
# change_forest_agb_growth_tropical_mountain_system_to_tropical_montane()
