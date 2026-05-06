import firebase_admin.auth
import api.models as models
import minitool.models as minitool_models
import ipcc.models as ipcc_models
from django.apps import apps
import logging as log
from django.db.models import Q
from djangoexact.settings import auth
import firebase_admin
import os
import pandas as pd
import csv

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
    agbs = ipcc_models.ForestManagementRootToShoot.objects.filter(climate__name="Tropical", land_use_type__name="Mountain System").update(climate=tropical_montane_climate)


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
    for module_type in models.ModuleType.objects.all():
        log.debug(f"Invalidating cached results for {module_type}")
        try:
            ModuleClass: models.Module = apps.get_model("api", module_type.class_name)
            if issubclass(ModuleClass, models.CachedResultMixin):
                ModuleClass.objects.all().update(
                    updated_at=None,
                    last_cached_at=None,
                    cached_results_total=None,
                    cached_results_by_activity=None,
                    cached_results_by_gas=None,
                    cached_results_by_activity_by_gas=None,
                    last_modified=None,
                )
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


def migrate_all_parameters():
    from camel_converter import to_snake

    params = [
        models.LivestockParameter,
        models.IrrigationParameter,
        models.SmallFisheryParameter,
        models.LargeFisheryParameter,
        models.AquacultureParameter,
        models.GrasslandParameter,
        models.AnnualCroplandParameter,
        models.CoastalWetlandParameter,
    ]

    for param in params:
        print(f"Migrating {param}")
        objs: list[models.Parameter] = param.objects.all()
        for obj in objs:
            print(f"Creating {obj.name} {obj.value}")
            models.ApplicationParameter.objects.create(
                name=obj.name.casefold() if param not in [models.SmallFisheryParameter, models.LargeFisheryParameter] else f"{to_snake(param.__name__.replace('Parameter', ''))}_{to_snake(obj.name)}",
                value=obj.value,
                unit=obj.unit,
            )


def add_c_fraction_ref_parameter():
    """
    Add c_fraction_ref parameter to all LandUseTypes
    """
    models.ApplicationParameter.objects.create(name="c_fraction_ref", value=1)


def add_project_uploads_max_file_size_parameter():
    """
    Add project_uploads_max_file_size parameter
    """
    models.ApplicationParameter.objects.create(name="project_uploads_max_file_size_mb", value=50)


def print_all_fuel_types():
    """
    Print all fuel types
    """
    for fuel_type in models.FuelType.objects.all():
        print(fuel_type.name)


def create_twenty_projects_and_assign_a_tag():
    """
    Create twenty projects and assign a tag
    """
    tag = models.ProjectTag.objects.create(name="Test")
    u = models.CustomUser.objects.get(email="admin@admin.com")
    for i in range(20):
        p = models.Project.objects.create(name=f"Project {i}", tag=tag, owner=u)
        models.ProjectMembership.objects.create(project=p, user=u, group=models.Group.objects.get(name="Admin"))


# TODO: Run in prod

# add_climate_tropical_montane_to_perennial_cropland()
# add_0_12_to_co2_value_in_input_emission_factor()
# change_forest_agb_tropical_mountain_system_to_tropical_montane()
# change_forest_bgb_tropical_mountain_system_to_tropical_montane()
# change_forest_agb_growth_tropical_mountain_system_to_tropical_montane()
# models.ApplicationParameter.objects.all().delete()
# migrate_all_parameters()
# add_c_fraction_ref_parameter()
# add_project_uploads_max_file_size_parameter()

# cycle_all_modules_and_invalidate_cached_results()
# create_test_user_for_peter()
# activate_test_user_for_peter_on_firebase()
# create_twenty_projects_and_assign_a_tag()


def add_default_project_lock_expiration_time_minutes_application_parameter():
    """
    Add default project lock expiration time minutes application parameter
    """
    models.ApplicationParameter.objects.create(name="project_lock_expiration_time_minutes", value=30)


def verify_user_firebase_email():
    """
    Verify user firebase email
    """
    user = models.CustomUser.objects.get(email="admin@admin.com")
    firebase_admin.auth.update_user(user.firebase_uid, email_verified=True)


def search_historical_projects_for_project_name():
    """
    Search historical projects for project name
    """
    projects = models.Project.history.filter(name__icontains="example project name", owner__email="owner@example.com", history_change_reason="delete")
    print(f"Found {projects.count()} projects")
    for project in projects:
        print(f"Project: {project.name}")
        print(f"Owner: {project.owner}")
        print(f"Action: {project.history_change_reason}")
        print(f"Perpetrator: {project.history_user}")
        print(f"Action Date: {project.history_date}")

        # Find connected historical activities
        activities = models.Activity.history.filter(project=project.instance).order_by("name").distinct("name")
        print(f"Found {activities.count()} activities")
        for activity in activities:
            print("----------------------------------------")
            print(f"Activity: {activity.name}")
            # print(f"Action: {activity.history_change_reason}")
            # print(f"Perpetrator: {activity.history_user}")
            # print(f"Action Date: {activity.history_date}")

            # Get all models of api app
            api_models = apps.get_app_config("api").get_models()
            api_models = list(filter(lambda x: issubclass(x, (models.Module)), api_models))

            api_submodules = apps.get_app_config("api").get_models()
            api_submodules = list(filter(lambda x: issubclass(x, (models.Submodule)), api_submodules))

            for Model in api_models:
                # Find connected historical modules
                modules = Model.history.filter(activity=activity.instance).order_by("id").distinct("id")

                if not modules:
                    continue

                print(f"Found {modules.count()} {Model.__name__} modules")
                for module in modules:
                    # print(f"Action: {module.history_change_reason}")
                    # print(f"Perpetrator: {module.history_user}")
                    # print(f"Action Date: {module.history_date}")

                    for Submodule in api_submodules:
                        # Find connected historical submodules
                        try:
                            parent_field_name = [f for f in Submodule._meta.get_fields() if f.is_relation and f.related_model == module.instance.__class__]
                            if not parent_field_name:
                                continue
                            parent_field_name = parent_field_name[0].name
                            filter_kwargs = {f"{parent_field_name}": module.instance}
                            submodules = Submodule.history.filter(**filter_kwargs).order_by("id", "history_date").distinct("id")
                        except ValueError:
                            continue

                        if not submodules:
                            continue

                        print(f"Found {submodules.count()} {Submodule.__name__} submodules for {module.instance.__class__.__name__}")
                        # for submodule in submodules:
                        #     print(f"Action: {submodule.history_change_reason}")
                        #     print(f"Perpetrator: {submodule.history_user}")
                        #     print(f"Action Date: {submodule.history_date}")
            print("----------------------------------------\n\n\n")


def import_hih_regions():
    """
    Import Hand in Hand regions from the database
    """

    df = pd.read_json(os.path.join(os.path.dirname(__file__), "HIHRegion.json"))
    for index, row in df.iterrows():
        region, created = models.HandInHandRegion.objects.get_or_create(name=row["name"])
        if created:
            print(f"Created region: {region.name}")
        else:
            print(f"Region already exists: {region.name}")


def import_hih_countries():
    """
    Import Hand in Hand countries from the database
    """

    df = pd.read_json(os.path.join(os.path.dirname(__file__), "HIHCountry.json"))
    for index, row in df.iterrows():
        country, created = models.HandInHandCountry.objects.get_or_create(name=row["name"], region=models.HandInHandRegion.objects.get(name=row["region"]), iso_code=row["code"])
        if created:
            print(f"Created country: {country.name} in region {country.region.name}")
        else:
            print(f"Country already exists: {country.name} in region {country.region.name}")


def import_hih_links():
    """
    Import Hand in Hand links from the database
    """
    df = pd.read_json(os.path.join(os.path.dirname(__file__), "ipcc_data/HIHLinks.json"))
    for index, row in df.iterrows():
        country = models.HandInHandCountry.objects.get(name=row["country"])
        link = row["link"]
        name = row["name"]
        year = row["year"]
        assessment, created = models.HandInHandAssessment.objects.get_or_create(country=country, link=link, name=name, year=year)
        if created:
            print(f"Created assessment: {assessment.name} for {assessment.country.name} in {assessment.year}")
        else:
            print(f"Assessment already exists: {assessment.name} for {assessment.country.name} in {assessment.year}")


def add_public_id_to_projects():
    """
    Add public_id to all projects
    """
    projects = []
    for project in models.Project.objects.all():
        if not project.public_id:
            project.public_id = models.uuid.uuid4()
            projects.append(project)
            print(f"Added public_id {project.public_id} to project {project.name}")
        else:
            print(f"Project {project.name} already has public_id {project.public_id}")

    if projects:
        models.Project.objects.bulk_update(projects, ["public_id"])
        print(f"Updated {len(projects)} projects with public_id")


def remove_irrigation_modules_from_wood_peat_and_charcoal_fuel_types():
    """
    Remove Irrigation modules from Wood, Peat, and Charcoal fuel types
    """
    modules_to_remove = [
        models.ModuleType.objects.get(class_name="Irrigation"),
        models.ModuleType.objects.get(class_name="IrrigationPhase"),
        models.ModuleType.objects.get(class_name="IrrigationSystem"),
    ]
    modules_to_add = [
        models.ModuleType.objects.get(class_name="Processing"),
        models.ModuleType.objects.get(class_name="ProcessingEntry"),
        models.ModuleType.objects.get(class_name="Packaging"),
        models.ModuleType.objects.get(class_name="PackagingEntry"),
    ]
    for fuel_type in models.FuelType.objects.filter(name__in=["Wood", "Peat", "Charcoal"]):
        fuel_type.module_types.remove(*modules_to_remove)
        fuel_type.save()
        print(f"Removed Irrigation modules from {fuel_type.name} fuel type")

        fuel_type.module_types.add(*modules_to_add)
        fuel_type.save()
        print(f"Added Processing and Packaging modules to {fuel_type.name} fuel type")


def find_duplicates_in_crop_yield_stat_model():
    """
    Find duplicates in CropYieldStat model
    """
    from django.db.models import Count

    # Get all CropYieldStats and find duplicates based on crop, country and year
    duplicates = ipcc_models.CropYieldStat.objects.values("land_use_type__name", "continent__name").annotate(count=Count("id")).filter(count__gt=1)

    for duplicate in duplicates:
        print(f"Duplicate: {duplicate['land_use_type__name']} {duplicate['continent__name']}")


def add_macro_input_type_other():
    """
    Add MacroInputType Other to all InputTypes
    """
    models.MacroInputType.objects.create(name="Other")


def add_other_macro_input_type_to_user_defined_tier_2_input_type_except_animal_feed():
    """
    Add Other macro input type to User Defined Tier 2 InputType
    """
    user_defined_input_types = models.InputType.objects.filter(name_en__icontains="User Defined").exclude(name_en__icontains="Animal Feed")
    other_macro_input_type = models.MacroInputType.objects.get(name="Other")
    input_types_to_update = []
    for input_type in user_defined_input_types:
        input_type.macro_input_type = other_macro_input_type
        input_types_to_update.append(input_type)

    if input_types_to_update:
        models.InputType.objects.bulk_update(input_types_to_update, ["macro_input_type"])
        print(f"Updated {len(input_types_to_update)} input types with macro input type {other_macro_input_type.name}")


def find_all_countries_with_no_region():
    """
    Find all countries with no region
    """
    countries = models.Country.objects.filter(region=None)
    print(f"Found {countries.count()} countries with no region")
    for country in countries:
        country.delete()
        print(f"Deleted country: {country.name}")


def find_all_countries_with_no_ipcc_region():
    """
    Find all countries with no ipcc region
    """
    countries = models.Country.objects.filter(ipcc_region=None)
    print(f"Found {countries.count()} countries with no ipcc region")
    for country in countries:
        country.delete()
        print(f"Deleted country: {country.name}")


def sanitize_minitool_data():
    """
    Get all module type waterbody change aggregates and capitalize module type
    """
    print("Deleting smallfishery data")
    minitool_models.ChangeRecord.objects.filter(module_type__icontains="smallfishery").delete()
    minitool_models.ChangeAggregate.objects.filter(module_type__icontains="smallfishery").delete()
    print("Deleting Flooded Rice data")
    minitool_models.ChangeRecord.objects.filter(module_type__icontains="Flooded Rice").delete()
    minitool_models.ChangeAggregate.objects.filter(module_type__icontains="Flooded Rice").delete()
    print("Deleting Perennial Cropland data")
    minitool_models.ChangeRecord.objects.filter(module_type__icontains="Perennial Cropland").delete()
    minitool_models.ChangeAggregate.objects.filter(module_type__icontains="Perennial Cropland").delete()
    print("Done")


def import_input_types_units():
    """
    Import input types units
    """
    df = pd.read_json(os.path.join(os.path.dirname(__file__), "InputTypeUnits.json"))
    for index, row in df.iterrows():
        print(f"Importing input type {row['name']} with unit {row['unit']}")
        input_type = models.InputType.objects.get(name__iexact=row["name"])
        input_type.unit = row["unit"]
        input_type.save()
        print(f"Imported input type {input_type.name} with unit {input_type.unit}")


def check_forest_numbers(activities=None):
    """
    Check forest numbers
    """
    from api.models import ForestManagement

    if activities is None:
        activities = models.Activity.objects.all()
    activities = activities.filter(module_types__name__icontains="Forest Management")
    print(f"Activities: {activities.count()}")
    forest_management_modules = ForestManagement.objects.filter(activity__in=activities)
    print(f"Forest management modules: {forest_management_modules.count()}")
    secondary_forest_modules = forest_management_modules.filter(Q(forest_condition_type__name="Secondary"))
    print(f"Secondary forest modules: {secondary_forest_modules.count()}")
    plantation_forest_modules = secondary_forest_modules.filter(Q(forest_type__name="Plantation"))
    print(f"Of which plantations: {plantation_forest_modules.count()}")

    print(f"Percentage of secondary forest modules: {secondary_forest_modules.count() / forest_management_modules.count() * 100}%")
    print(f"Percentage of plantation forest modules: {plantation_forest_modules.count() / secondary_forest_modules.count() * 100}%")

    # List the (unique) emails of users with the most unique projects that have activities in forest management modules
    from django.db.models import Count

    users = (
        models.CustomUser.objects.filter(projects__activities__in=activities)
        .distinct()
        .annotate(project_count=Count("projects", filter=Q(projects__activities__in=activities), distinct=True))
        .order_by("-project_count")
    )
    print(f"Users: {users.count()}")
    for user in users:
        print(f"User: {user.email} - {user.project_count} unique projects with activities in forest management modules")

    # Confront users affected with total users (in percentage)
    total_users = models.CustomUser.objects.count()
    print(f"Total users: {total_users}")
    print(f"Percentage of users affected: {users.count() / total_users * 100}%")


def check_how_many_users_logged_in_last_month(time_period=30):
    """
    Check how many users logged in last month
    """
    from django.utils import timezone
    from datetime import timedelta

    users = models.CustomUser.objects.filter(last_login__gte=timezone.now() - timedelta(days=time_period))
    # Confront users affected with total users (in percentage)
    total_users = models.CustomUser.objects.count()
    print(f"Percentage of users logged in last {time_period} days: {users.count()} ({users.count() / total_users * 100:.2f}% of total userbase)")

    return users


def check_how_many_users_logged_in_last_time_period_have_been_forest_management_activities(time_period=30):
    """
    Check how many users logged in last time period have been forest management activities
    """
    from django.utils import timezone
    from datetime import timedelta

    activities = models.Activity.objects.filter(created_at__gte=timezone.now() - timedelta(days=time_period))
    activities = activities.filter(module_types__name__icontains="Forest Management")
    users_last_time_period = check_how_many_users_logged_in_last_month(time_period=time_period)

    users_last_time_period_with_forest_management_activities = users_last_time_period.filter(activities__in=activities)
    print(
        f"Amount of active users with activities in forest management in the last {time_period} days: {users_last_time_period_with_forest_management_activities.count()} ({users_last_time_period_with_forest_management_activities.count() / users_last_time_period.count() * 100:.2f}% of active users)"
    )
    return users_last_time_period_with_forest_management_activities


def get_projects_with_forest_management_activities():
    projects = models.Project.objects.filter(activities__module_types__name__icontains="Forest Management").distinct()
    return projects


def get_users_with_projects_with_forest_management_activities():
    users = models.CustomUser.objects.filter(projects__activities__module_types__name__icontains="Forest Management").distinct()
    return users


def get_forest_management_modules_in_plantation_projects():
    """
    Get the number of forest management modules in activities in projects with forest type 'Plantation'
    """
    projects = get_projects_with_forest_management_activities()
    forests = models.ForestManagement.objects.filter(activity__project__in=projects, forest_type__name__iexact="Plantation")
    print(f"Forest management modules in secondary forests or plantation projects: {forests.count()}")

    # How many of them have users that logged in last 90 days?
    users_last_90_days = check_how_many_users_logged_in_last_month(time_period=90)
    print(f"Active users last 90 days: {users_last_90_days.count()}")
    forests_with_users_last_90_days = forests.filter(activity__project__members__user__in=users_last_90_days).distinct("activity__project__members__user")
    print(f"Active users with Forest management modules in secondary forests or plantations in the last 90 days: {forests_with_users_last_90_days.count()}")

    # Extract users emails
    users_emails = forests_with_users_last_90_days.values_list(
        "activity__project__members__user__email", "activity__project__members__user__first_name", "activity__project__members__user__last_name"
    ).distinct()
    print(f"Users emails: {users_emails.count()}")

    # Save them to csv
    with open("users_emails.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Email", "First Name", "Last Name"])
        for user_email in users_emails:
            writer.writerow([user_email[0], user_email[1], user_email[2]])

    return forests

def change_all_other_land_flu_data_to_1():
    """
    Change all OtherLandFLUData objects to have a value of 1.0 for all land use types.
    """
    from ipcc.models import FLUData
    flu_datas = FLUData.objects.filter(land_use_type__name__iexact="Other Land").all()
    for flu_data in flu_datas:
        flu_data.value = 1.0
        flu_data.save()


def import_fires_combustion_factors():
    """
    Import FiresCombustionFactors from CSV.
    For each row, get the api.LandUseType by name (no creation), then update_or_create
    the ipcc.FiresCombustionFactor with the given value.
    """
    from ipcc.models import FiresCombustionFactor

    df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data/FiresCombustionFactors_20260408.csv"))
    for _, row in df.iterrows():
        try:
            land_use_type = models.LandUseType.objects.get(name=row["land_use_type"])
        except models.LandUseType.DoesNotExist:
            print(f"LandUseType not found: {row['land_use_type']}, skipping")
            continue

        factor, created = FiresCombustionFactor.objects.update_or_create(
            land_use_type=land_use_type,
            defaults={"value": row["value"]},
        )
        if created:
            print(f"Created FiresCombustionFactor for {land_use_type.name}")
        else:
            print(f"Updated FiresCombustionFactor for {land_use_type.name}")


def import_crop_nitrous_estimation_default_factors():
    """
    Import CropNitrousEstimationDefaultFactors from CSV.
    For each row, get_or_create the api.CropType by name, then get_or_create
    the ipcc.CropNitrousEstimationDefaultFactor with the remaining fields.
    """
    from ipcc.models import CropNitrousEstimationDefaultFactor

    df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data/CropNitrousEstimationDefaultFactors_20260804.csv"))
    for _, row in df.iterrows():
        land_use_type, created = models.LandUseType.objects.get_or_create(name=row["land_use_type"])
        if created:
            annual_cropland = models.ModuleType.objects.get(class_name="AnnualCropland")
            land_use_type.module_types.set([annual_cropland])
            print(f"Created LandUseType: {land_use_type.name}")

        factor, created = CropNitrousEstimationDefaultFactor.objects.update_or_create(
            land_use_type=land_use_type,
            defaults={
                "dry_matter": row["dry_matter"],
                "slope": row["slope"],
                "intercept": row["intercept"],
                "n_ag_residues": row["n_ag_residues"],
                "rag": row["rag"],
                "rs_t": row["rs_t"],
                "n_bg_t": row["n_bg_t"],
                "comment": row["comment"],
            },
        )
        if created:
            print(f"Created CropNitrousEstimationDefaultFactor for {land_use_type.name}")
        else:
            print(f"Updated CropNitrousEstimationDefaultFactor for {land_use_type.name}")


def set_all_climates_and_moistures_for_crop_nitrous_land_use_types():
    """
    For every land_use_type in CropNitrousEstimationDefaultFactors_20260804.csv,
    set .climates to all available api.Climate and .moistures to all available api.Moisture.
    """
    all_climates = list(models.Climate.objects.all())
    all_moistures = list(models.Moisture.objects.all())

    df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data/CropNitrousEstimationDefaultFactors_20260804.csv"))
    for _, row in df.iterrows():
        try:
            land_use_type = models.LandUseType.objects.get(name=row["land_use_type"])
        except models.LandUseType.DoesNotExist:
            print(f"LandUseType not found: {row['land_use_type']}, skipping")
            continue

        land_use_type.climates.set(all_climates)
        land_use_type.moistures.set(all_moistures)
        print(f"Updated {land_use_type.name}: {len(all_climates)} climates, {len(all_moistures)} moistures")


def remove_perennial_cropland_module_from_perennial_land_use_types():
    """
    Remove the PerennialCropland ModuleType association from every LandUseType whose
    name matches an ITEM marked PERENNIALS=YES in
    CropNitrous-annualperennials.xlsx (sheet 'Annualsperennials').

    Uses a single bulk delete on the LandUseType.module_types through table.
    """
    perennial_item_names = [
        "Default",
        "Abaca, manila hemp, raw",
        "Almonds, in shell",
        "Anise, badian, coriander, cumin, caraway, fennel and juniper berries, raw",
        "Apples",
        "Apricots",
        "Areca nuts",
        "Avocados",
        "Bananas",
        "Blueberries",
        "Brazil nuts, in shell",
        "Cashew nuts, in shell",
        "Cherries",
        "Chestnuts, in shell",
        "Cocoa beans",
        "Coconuts, in shell",
        "Coffee, green",
        "Coir, raw",
        "Cranberries",
        "Currants",
        "Dates",
        "Figs",
        "Gooseberries",
        "Grapes",
        "Hazelnuts, in shell",
        "Jojoba seeds",
        "Kapok fruit",
        "Karite nuts (sheanuts)",
        "Kiwi fruit",
        "Kola nuts",
        "Lemons and limes",
        "Locust beans (carobs)",
        "Mangoes, guavas and mangosteens",
        "Nutmeg, mace, cardamoms, raw",
        "Oil palm fruit",
        "Olives",
        "Oranges",
        "Other berries and fruits of the genus vaccinium n.e.c.",
        "Palm kernels",
        "Papayas",
        "Peaches and nectarines",
        "Pears",
        "Pepper (Piper spp.), raw",
        "Peppermint, spearmint",
        "Persimmons",
        "Pineapples",
        "Pistachios, in shell",
        "Plantains and cooking bananas",
        "Plums and sloes",
        "Pomelos and grapefruits",
        "Quinces",
        "Raspberries",
        "Sour cherries",
        "Tallowtree seeds",
        "Tangerines, mandarins, clementines",
        "Tea leaves",
        "Tung nuts",
        "Vanilla, raw",
        "Walnuts, in shell",
        "Wine",
        "Citrus Fruit, Total + (Total)",
        "Fruit Primary + (Total)",
    ]

    print(f"Processing {len(perennial_item_names)} perennial ITEM names from CropNitrous-annualperennials.xlsx")

    try:
        perennial_cropland = models.ModuleType.objects.get(class_name="PerennialCropland")
    except models.ModuleType.DoesNotExist:
        print("ModuleType with class_name='PerennialCropland' not found, aborting")
        return

    matched_land_use_types = models.LandUseType.objects.filter(name__in=perennial_item_names)
    matched_names = set(matched_land_use_types.values_list("name", flat=True))
    missing_names = sorted(set(perennial_item_names) - matched_names)

    print(f"Matched {len(matched_names)}/{len(perennial_item_names)} ITEM names to LandUseType records")
    if missing_names:
        print(f"Skipping {len(missing_names)} ITEM names with no LandUseType match:")
        for name in missing_names:
            print(f"  - {name}")

    if not matched_land_use_types.exists():
        print("No LandUseTypes matched, nothing to remove")
        return

    through = models.LandUseType.module_types.through
    associations = through.objects.filter(
        landusetype__in=matched_land_use_types,
        moduletype=perennial_cropland,
    )
    to_remove_count = associations.count()
    print(f"Found {to_remove_count} LandUseType <-> PerennialCropland associations to remove")

    if to_remove_count == 0:
        print("No PerennialCropland associations present on matched LandUseTypes, nothing to do")
        return

    affected_lut_names = sorted(associations.values_list("landusetype__name", flat=True))
    deleted, _ = associations.delete()
    print(f"Bulk-removed {deleted} PerennialCropland associations from {len(affected_lut_names)} LandUseTypes:")
    for name in affected_lut_names:
        print(f"  - {name}")


def run():
    import os

    app_mode = os.getenv("APP_MODE", None)
    print(f"Running script in {app_mode} mode")

    if app_mode == "production":
        # TODO: Run in production
        # cycle_all_modules_and_invalidate_cached_results()
        # import_input_types_units()
        # check_how_many_users_logged_in_last_time_period_have_been_forest_management_activities(time_period=90)
        # get_forest_management_modules_in_plantation_projects()
        change_all_other_land_flu_data_to_1()
        import_crop_nitrous_estimation_default_factors()
        import_fires_combustion_factors()
        import_crop_nitrous_estimation_default_factors()
        import_fires_combustion_factors()
        set_all_climates_and_moistures_for_crop_nitrous_land_use_types()
        pass

    if app_mode == "review":
        # TODO: Run in review
        # import_input_types_units()
        # change_all_other_land_flu_data_to_1()
        # import_crop_nitrous_estimation_default_factors()
        # import_fires_combustion_factors()
        # set_all_climates_and_moistures_for_crop_nitrous_land_use_types()
        remove_perennial_cropland_module_from_perennial_land_use_types()
        pass

    if app_mode == "development" or app_mode == "local":
        # TODO: Run in development
        # sanitize_minitool_data()
        # change_all_other_land_flu_data_to_1()
        # import_crop_nitrous_estimation_default_factors()
        # import_fires_combustion_factors()
        # import_input_types_units()
        # set_all_climates_and_moistures_for_crop_nitrous_land_use_types()
        pass

    if app_mode == "test":
        # TODO: Run in test
        add_default_project_lock_expiration_time_minutes_application_parameter()
        import_hih_links()
        change_all_other_land_flu_data_to_1()
        pass

    return True
