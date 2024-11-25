import firebase_admin.auth
import api.models as models
import ipcc.models as ipcc_models
from django.apps import apps
import logging as log
from django.db.models import Q
from djangoexact.settings import auth
import firebase_admin

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


def cycle_all_modules_and_invalidate_cached_results():
    """
    Cycle all modules and invalidate cached results
    """
    models.ForestDisturbance.objects.all().delete()
    for module_type in models.ModuleType.objects.all():
        log.debug(f"Invalidating cached results for {module_type}")
        try:
            ModuleClass: models.Module = apps.get_model("api", module_type.class_name)
            if hasattr(ModuleClass, "last_cached_at"):
                ModuleClass.history.all().update(updated_at=None, last_cached_at=None, cached_results_total=None, cached_results_by_activity=None, cached_results_by_gas=None, cached_results_by_activity_by_gas=None, last_modified=None)
                for module in ModuleClass.objects.filter(Q(last_cached_at__isnull=False) | Q(cached_results_total__isnull=False)):
                    if hasattr(module, "invalidate_cached_results"):
                        module.invalidate_cached_results()
                    else:
                        log.error(f"Could not find invalidate_cached_results for {module}")
            else:
                log.error(f"Could not find last_cached_at for {module_type}")
        except LookupError:
            log.error(f"Could not find module class for {module_type}")


def create_test_user_for_peter():
    """
    Create a test user for Peter
    """

    user = models.CustomUser.objects.get(email="testuser@test.com")


def activate_test_user_for_peter_on_firebase():
    """
    Activate test user for Peter on Firebase
    """

    # Find firebase user with email and activate
    user = auth.sign_in_with_email_and_password("testuser@test.com", "testuser")
    firebase_admin.auth.update_user(user["localId"], email_verified=True)


# TODO: Run in prod

# add_climate_tropical_montane_to_perennial_cropland()
# add_0_12_to_co2_value_in_input_emission_factor()
# change_forest_agb_tropical_mountain_system_to_tropical_montane()
# change_forest_bgb_tropical_mountain_system_to_tropical_montane()
# change_forest_agb_growth_tropical_mountain_system_to_tropical_montane()
# cycle_all_modules_and_invalidate_cached_results()
# create_test_user_for_peter()
# activate_test_user_for_peter_on_firebase()
