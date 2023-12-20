from api.models import *
import factory
import factory.fuzzy
from factory.django import DjangoModelFactory
import random
from api.serializers import *

sma_gear_types = [gear for gear in SmallFisheryGearType.objects.all()]
lge_gear_types = [gear for gear in LargeFisheryGearType.objects.all()]
rate_types = [rate for rate in ChangeRate.objects.all()]
fishery_types = [fishery for fishery in FisheryType.objects.all()]
fish_types = [fish for fish in FishType.objects.all()]
statuses = [status for status in ProjectStatus.objects.all()]

crop_types = [crop for crop in LandUseType.objects.filter(module_types__class_name="AnnualCropping")]
tillage_management_types = [tillage for tillage in TillageManagementType.objects.all()]
organic_input_types = [organic for organic in OrganicInputType.objects.all()]
residue_management_types = [residue for residue in ResidueManagementType.objects.all()]
grassland_management_types = GrasslandManagementType.objects.all()

livestock_category_types = [
    c
    for c in LivestockCategoryType.objects.all().exclude(
        Q(name="Sheep") | Q(name="Swine")
    )
]
livestock_production_types = [c for c in LivestockProductionType.objects.all()]

def_rate = ChangeRate.objects.get(name="D")
sm_gear_type = random.choice(sma_gear_types)
lge_gear_type = random.choice(lge_gear_types)


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

    implementation_years = factory.fuzzy.FuzzyInteger(1, 10)
    capitalization_years = factory.fuzzy.FuzzyInteger(1, 10)


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

    fishery_type = factory.fuzzy.FuzzyChoice(fishery_types)

    gear_type_start = sm_gear_type
    gear_type_w = sm_gear_type
    gear_type_wo = sm_gear_type


class LargeFisheryFactory(FisheryFactory):
    class Meta:
        model = LargeFishery
        abstract = False

    fish_type = factory.fuzzy.FuzzyChoice(fish_types)

    gear_type_start = lge_gear_type
    gear_type_w = lge_gear_type
    gear_type_wo = lge_gear_type


class AnnualCroppingFactory(DjangoModelFactory):
    class Meta:
        model = AnnualCropping

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

    area = factory.fuzzy.FuzzyInteger(1, 150)


class PerennialCroppingFactory(DjangoModelFactory):
    class Meta:
        model = PerennialCropping

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

    livestock_category_type_start = factory.fuzzy.FuzzyChoice(livestock_category_types)
    livestock_category_type_w = factory.fuzzy.FuzzyChoice(livestock_category_types)
    livestock_category_type_wo = factory.fuzzy.FuzzyChoice(livestock_category_types)

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

    fire_periodicity_start = factory.fuzzy.FuzzyFloat(0, 1)
    fire_periodicity_w = factory.fuzzy.FuzzyFloat(0, 1)
    fire_periodicity_wo = factory.fuzzy.FuzzyFloat(0, 1)

    fire_impact_start = factory.fuzzy.FuzzyFloat(0, 1)
    fire_impact_w = factory.fuzzy.FuzzyFloat(0, 1)
    fire_impact_wo = factory.fuzzy.FuzzyFloat(0, 1)

    yield_start = factory.fuzzy.FuzzyInteger(0, 100)
    yield_w = factory.fuzzy.FuzzyInteger(0, 100)
    yield_wo = factory.fuzzy.FuzzyInteger(0, 100)

    area = factory.fuzzy.FuzzyInteger(1, 150)

land_modules = ModuleType.objects.filter(is_luc=True, is_submodule=False).all()

ready_land_modules = land_modules.filter(name__in=["Annual Cropland", "Grassland"]).all()

class LandUseChangeFactory(DjangoModelFactory):
    class Meta:
        model = LandUseChange

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