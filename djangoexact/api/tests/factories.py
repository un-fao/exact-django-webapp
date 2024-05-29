import random

import factory
import factory.fuzzy
from api.models import *
from api.models import CustomUser as User
from api.serializers import *
from factory.django import DjangoModelFactory

sma_gear_types = [gear for gear in SmallFisheryGearType.objects.all()]
lge_gear_types = [gear for gear in LargeFisheryGearType.objects.all()]
rate_types = [rate for rate in ChangeRate.objects.all()]
fishery_types = [fishery for fishery in FisheryType.objects.all()]
fish_types = [fish for fish in FishType.objects.all()]
statuses = [status for status in ProjectStatus.objects.all()]

crop_types = [crop for crop in LandUseType.objects.filter(module_types__class_name="AnnualCropping").exclude(is_active=False)]
trees = [tree for tree in LandUseType.objects.filter(module_types__class_name="PerennialCropping").exclude(is_active=False)]
tillage_management_types = [tillage for tillage in TillageManagementType.objects.all()]
organic_input_types = [organic for organic in OrganicInputType.objects.filter(is_active=True).all()]
residue_management_types = [residue for residue in ResidueManagementType.objects.all()]
grassland_management_types = GrasslandManagementType.objects.all()
forests = [forest for forest in LandUseType.objects.filter(module_types__class_name="ForestManagement").exclude(is_active=False)]
coastal_vegetations = [coastal for coastal in LandUseType.objects.filter(module_types__class_name="CoastalWetland").exclude(is_active=False)]

livestock_category_types = [c for c in LivestockCategoryType.objects.filter(is_active=True).all()]
livestock_production_types = [c for c in LivestockProductionType.objects.all()]
fuels = [fuel for fuel in FuelType.objects.exclude(macro_fuel_type__name="Liquid or gaseous").all()]

countries = [country for country in Country.objects.all()]

def_rate = ChangeRate.objects.get(name="D")
sm_gear_type = random.choice(sma_gear_types)
lge_gear_type = random.choice(lge_gear_types)

READY = StatusType.objects.get(name="READY")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    name = factory.fuzzy.FuzzyText()
    code = factory.fuzzy.FuzzyText()
    cost = factory.fuzzy.FuzzyFloat(0.0, 100)
    funding_agency = factory.fuzzy.FuzzyText()
    executing_agency = factory.fuzzy.FuzzyText()
    status = factory.fuzzy.FuzzyChoice(statuses)

    implementation_years = factory.fuzzy.FuzzyInteger(1, 7)
    capitalization_years = factory.fuzzy.FuzzyInteger(7, 7)


class ActivityFactory(DjangoModelFactory):
    class Meta:
        model = Activity

    name = factory.fuzzy.FuzzyText()
    # user = factory

    change_rate = def_rate


class FisheryFactory(DjangoModelFactory):
    class Meta:
        model = Fishery
        abstract = True

    refrigerant_pc_start = factory.fuzzy.FuzzyFloat(0.0, 1)
    refrigerant_pc_w = factory.fuzzy.FuzzyFloat(0.0, 1)
    refrigerant_pc_wo = factory.fuzzy.FuzzyFloat(0.0, 1)

    refrigerant_gwp = factory.fuzzy.FuzzyInteger(1810, 1810)

    fui_start = factory.fuzzy.FuzzyFloat(0.0, 100)
    fui_w = factory.fuzzy.FuzzyFloat(0.0, 100)
    fui_wo = factory.fuzzy.FuzzyFloat(0.0, 100)

    total_catch_yr_start = factory.fuzzy.FuzzyFloat(0.0, 100)
    total_catch_yr_w = factory.fuzzy.FuzzyFloat(0.0, 100)
    total_catch_yr_wo = factory.fuzzy.FuzzyFloat(0.0, 100)

    ice_preserved_catch_pc_start = factory.fuzzy.FuzzyFloat(0.0, 1)
    ice_preserved_catch_pc_w = factory.fuzzy.FuzzyFloat(0.0, 1)
    ice_preserved_catch_pc_wo = factory.fuzzy.FuzzyFloat(0.0, 1)


class SmallFisheryFactory(FisheryFactory):
    class Meta:
        model = SmallFishery
        abstract = False

    status = READY

    fishery_type = factory.fuzzy.FuzzyChoice(fishery_types)

    gear_type_start = sm_gear_type
    gear_type_w = sm_gear_type
    gear_type_wo = sm_gear_type


class LargeFisheryFactory(FisheryFactory):
    class Meta:
        model = LargeFishery
        abstract = False

    status = READY

    fish_type = factory.fuzzy.FuzzyChoice(fish_types)

    gear_type_start = lge_gear_type
    gear_type_w = lge_gear_type
    gear_type_wo = lge_gear_type


class AnnualCroppingFactory(DjangoModelFactory):
    class Meta:
        model = AnnualCropping

    area = 150

    status = READY

    land_use_type_w = factory.fuzzy.FuzzyChoice(crop_types)
    land_use_type_start = land_use_type_w
    land_use_type_wo = land_use_type_w

    tillage_management_type_start = factory.fuzzy.FuzzyChoice(tillage_management_types)
    tillage_management_type_w = factory.fuzzy.FuzzyChoice(tillage_management_types)
    tillage_management_type_wo = factory.fuzzy.FuzzyChoice(tillage_management_types)

    organic_input_type_start = factory.fuzzy.FuzzyChoice(organic_input_types)
    organic_input_type_w = organic_input_type_start
    organic_input_type_wo = organic_input_type_start

    residue_management_type_start = factory.fuzzy.FuzzyChoice(residue_management_types)
    residue_management_type_w = factory.fuzzy.FuzzyChoice(residue_management_types)
    residue_management_type_wo = factory.fuzzy.FuzzyChoice(residue_management_types)

    crop_yield_start = factory.fuzzy.FuzzyInteger(0.0, 100)
    crop_yield_w = factory.fuzzy.FuzzyInteger(0.0, 100)
    crop_yield_wo = factory.fuzzy.FuzzyInteger(0.0, 100)

    area = factory.fuzzy.FuzzyInteger(150, 150)


class PerennialCroppingFactory(DjangoModelFactory):
    class Meta:
        model = PerennialCropping

    area = 150

    status = READY

    land_use_type_start = factory.fuzzy.FuzzyChoice(trees)
    land_use_type_w = land_use_type_start
    land_use_type_wo = land_use_type_start

    tillage_management_type_start = factory.fuzzy.FuzzyChoice(tillage_management_types)
    tillage_management_type_w = factory.fuzzy.FuzzyChoice(tillage_management_types)
    tillage_management_type_wo = factory.fuzzy.FuzzyChoice(tillage_management_types)
    organic_input_type_start = factory.fuzzy.FuzzyChoice(organic_input_types)
    organic_input_type_w = factory.fuzzy.FuzzyChoice(organic_input_types)
    organic_input_type_wo = factory.fuzzy.FuzzyChoice(organic_input_types)
    is_biomass_burned_start = factory.fuzzy.FuzzyChoice([True, False])
    is_biomass_burned_w = factory.fuzzy.FuzzyChoice([True, False])
    is_biomass_burned_wo = factory.fuzzy.FuzzyChoice([True, False])

    crop_yield_start = factory.fuzzy.FuzzyInteger(0, 100)
    crop_yield_w = factory.fuzzy.FuzzyInteger(0, 100)
    crop_yield_wo = factory.fuzzy.FuzzyInteger(0, 100)


class LivestockFactory(DjangoModelFactory):
    class Meta:
        model = Livestock

    livestock_category_type = random.choice(livestock_category_types)

    livestock_production_type_start = factory.fuzzy.FuzzyChoice(livestock_production_types)
    livestock_production_type_w = factory.fuzzy.FuzzyChoice(livestock_production_types)
    livestock_production_type_wo = factory.fuzzy.FuzzyChoice(livestock_production_types)

    production_start = factory.fuzzy.FuzzyInteger(0, 100)
    production_w = factory.fuzzy.FuzzyInteger(0, 100)
    production_wo = factory.fuzzy.FuzzyInteger(0, 100)

    heads_number_start = factory.fuzzy.FuzzyInteger(0, 1000)
    heads_number_w = factory.fuzzy.FuzzyInteger(0, 1000)
    heads_number_wo = factory.fuzzy.FuzzyInteger(0, 1000)


class GrasslandFactory(DjangoModelFactory):
    class Meta:
        model = Grassland

    grassland_management_type_start = factory.fuzzy.FuzzyChoice(grassland_management_types)
    grassland_management_type_w = factory.fuzzy.FuzzyChoice(grassland_management_types)
    grassland_management_type_wo = factory.fuzzy.FuzzyChoice(grassland_management_types)

    is_fire_used_start = factory.fuzzy.FuzzyChoice([True, False])
    is_fire_used_w = factory.fuzzy.FuzzyChoice([True, False])
    is_fire_used_wo = factory.fuzzy.FuzzyChoice([True, False])

    fire_periodicity_start = factory.fuzzy.FuzzyInteger(1, 5)
    fire_periodicity_w = factory.fuzzy.FuzzyInteger(1, 5)
    fire_periodicity_wo = factory.fuzzy.FuzzyInteger(1, 5)

    fire_impact_start = factory.fuzzy.FuzzyFloat(0, 1)
    fire_impact_w = factory.fuzzy.FuzzyFloat(0, 1)
    fire_impact_wo = factory.fuzzy.FuzzyFloat(0, 1)

    yield_start = factory.fuzzy.FuzzyInteger(0, 100)
    yield_w = factory.fuzzy.FuzzyInteger(0, 100)
    yield_wo = factory.fuzzy.FuzzyInteger(0, 100)

    area = factory.fuzzy.FuzzyInteger(150, 150)


land_modules = ModuleType.objects.filter(is_luc=True, is_submodule=False).all()

ready_land_modules = land_modules.filter(name__in=["Annual Cropland", "Grassland"]).all()


class LandUseChangeFactory(DjangoModelFactory):
    class Meta:
        model = LandUseChange

    area = factory.fuzzy.FuzzyInteger(1, 150)

    module_type_start = factory.fuzzy.FuzzyChoice(ready_land_modules)
    module_type_w = factory.fuzzy.FuzzyChoice(ready_land_modules)
    module_type_wo = factory.fuzzy.FuzzyChoice(ready_land_modules)
    area = factory.fuzzy.FuzzyInteger(1, 150)

    is_fire_used_start = factory.fuzzy.FuzzyChoice([True, False])
    is_fire_used_w = factory.fuzzy.FuzzyChoice([True, False])
    is_fire_used_wo = factory.fuzzy.FuzzyChoice([True, False])

    dry_matter_start = factory.fuzzy.FuzzyFloat(0, 1)
    dry_matter_w = factory.fuzzy.FuzzyFloat(0, 1)
    dry_matter_wo = factory.fuzzy.FuzzyFloat(0, 1)


class ForestManagementFactory(DjangoModelFactory):
    class Meta:
        model = ForestManagement

    # On init, choose land_use_type based on activity.project.climate

    land_use_type_start = factory.fuzzy.FuzzyChoice(forests)
    land_use_type_w = land_use_type_start
    land_use_type_wo = land_use_type_start

    forest_type = ForestType.objects.get(name="Natural")

    area = factory.fuzzy.FuzzyInteger(1, 150)

    rotation_length_yrs_start = 7
    rotation_length_yrs_w = 7
    rotation_length_yrs_wo = 7

    rotation_percentage_biomass_for_energy_start = 1
    rotation_percentage_biomass_for_energy_w = 1
    rotation_percentage_biomass_for_energy_wo = 1


water_mgmt_types_before_cultivation = [water for water in WaterManagementTypeBeforeCultivation.objects.all()]
water_mgmt_types_after_cultivation = [water for water in WaterManagementTypeAfterCultivation.objects.all()]
organic_amendment_types = [organic for organic in OrganicAmendmentType.objects.all()]


class FloodedRiceFactory(DjangoModelFactory):
    class Meta:
        model = FloodedRice

    area = factory.fuzzy.FuzzyInteger(150, 150)
    status = READY

    water_management_type_before_cultivation_start = factory.fuzzy.FuzzyChoice(water_mgmt_types_before_cultivation)
    water_management_type_before_cultivation_w = factory.fuzzy.FuzzyChoice(water_mgmt_types_before_cultivation)
    water_management_type_before_cultivation_wo = factory.fuzzy.FuzzyChoice(water_mgmt_types_before_cultivation)

    water_management_type_after_cultivation_start = factory.fuzzy.FuzzyChoice(water_mgmt_types_after_cultivation)
    water_management_type_after_cultivation_w = factory.fuzzy.FuzzyChoice(water_mgmt_types_after_cultivation)
    water_management_type_after_cultivation_wo = factory.fuzzy.FuzzyChoice(water_mgmt_types_after_cultivation)

    organic_amendment_type_start = factory.fuzzy.FuzzyChoice(organic_amendment_types)
    organic_amendment_type_w = factory.fuzzy.FuzzyChoice(organic_amendment_types)
    organic_amendment_type_wo = factory.fuzzy.FuzzyChoice(organic_amendment_types)

    crop_yield_start = factory.fuzzy.FuzzyInteger(1, 10)
    crop_yield_w = factory.fuzzy.FuzzyInteger(1, 10)
    crop_yield_wo = factory.fuzzy.FuzzyInteger(1, 10)


class InputFactory(DjangoModelFactory):
    class Meta:
        model = Input

    status = READY


input_types = [input for input in InputType.objects.all().exclude(name="User Defined Animal Feed")]


class InputEntryFactory(DjangoModelFactory):
    class Meta:
        model = InputEntry

    input_type = factory.fuzzy.FuzzyChoice(input_types)

    status = READY

    value_start = factory.fuzzy.FuzzyFloat(0, 100)
    value_w = factory.fuzzy.FuzzyFloat(0, 100)
    value_wo = factory.fuzzy.FuzzyFloat(0, 100)


class AquacultureFactory(DjangoModelFactory):
    class Meta:
        model = Aquaculture

    annual_production_start = factory.fuzzy.FuzzyFloat(0, 100)
    annual_production_w = factory.fuzzy.FuzzyFloat(0, 100)
    annual_production_wo = factory.fuzzy.FuzzyFloat(0, 100)

    status = READY

    n2o_from_production_t2_start = factory.fuzzy.FuzzyFloat(0, 1)
    n2o_from_production_t2_w = factory.fuzzy.FuzzyFloat(0, 1)
    n2o_from_production_t2_wo = factory.fuzzy.FuzzyFloat(0, 1)

    electricity_used_t2_start = factory.fuzzy.FuzzyFloat(0, 100)
    electricity_used_t2_w = factory.fuzzy.FuzzyFloat(0, 100)
    electricity_used_t2_wo = factory.fuzzy.FuzzyFloat(0, 100)

    # electricity_ef_t2_start = factory.fuzzy.FuzzyFloat(0, 100)
    # electricity_ef_t2_w = factory.fuzzy.FuzzyFloat(0, 100)
    # electricity_ef_t2_wo = factory.fuzzy.FuzzyFloat(0, 100)


class EnergyFactory(DjangoModelFactory):
    class Meta:
        model = Energy

    status = READY


ef_sources = [source for source in EmissionFactorSource.objects.all()]


class ElectricityFactory(DjangoModelFactory):
    class Meta:
        model = Electricity

    status = READY

    country = factory.fuzzy.FuzzyChoice(countries)

    mwh_start = factory.fuzzy.FuzzyFloat(0, 100)
    mwh_w = factory.fuzzy.FuzzyFloat(0, 100)
    mwh_wo = factory.fuzzy.FuzzyFloat(0, 100)

    mwh_renewables_start = factory.fuzzy.FuzzyFloat(0, 100)
    mwh_renewables_w = factory.fuzzy.FuzzyFloat(0, 100)
    mwh_renewables_wo = factory.fuzzy.FuzzyFloat(0, 100)

    # ef_t2 = factory.fuzzy.FuzzyFloat(0, 100)
    # transmission_loss = factory.fuzzy.FuzzyFloat(0, 100)
    ef_source = factory.fuzzy.FuzzyChoice(ef_sources)


class FuelFactory(DjangoModelFactory):
    class Meta:
        model = Fuel

    status = READY

    fuel_type = factory.fuzzy.FuzzyChoice(fuels)

    fuel_consumption_start = factory.fuzzy.FuzzyFloat(0, 100)
    fuel_consumption_w = factory.fuzzy.FuzzyFloat(0, 100)
    fuel_consumption_wo = factory.fuzzy.FuzzyFloat(0, 100)

    # ef_t2 = factory.fuzzy.FuzzyFloat(0, 100)
    # account_for_co2 = factory.fuzzy.FuzzyChoice([True, False])


class CoastalWetlandFactory(DjangoModelFactory):
    class Meta:
        model = CoastalWetland

    status = READY # --------------> NOTE: Add to all factories if not

    area = 150 

    land_use_type = factory.fuzzy.FuzzyChoice(coastal_vegetations)

    area_under_drainage_start = factory.fuzzy.FuzzyFloat(0, area)
    area_under_drainage_w = factory.fuzzy.FuzzyFloat(0, area)
    area_under_drainage_wo = factory.fuzzy.FuzzyFloat(0, area)

    avg_salinity_t2 = SalinityType.objects.get(value="<18")


class WaterbodyFactory(DjangoModelFactory):
    pass
