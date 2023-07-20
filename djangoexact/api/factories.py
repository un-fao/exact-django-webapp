from .models import *
import factory
import factory.fuzzy
from factory.django import DjangoModelFactory
import random

sma_gear_types = [gear for gear in SmallFisheryGearType.objects.all()]
lge_gear_types = [gear for gear in LargeFisheryGearType.objects.all()]
rate_types = [rate for rate in ChangeRate.objects.all()]
fishery_types = [fishery for fishery in FisheryType.objects.all()]
fish_types = [fish for fish in FishType.objects.all()]
statuses = [status for status in ProjectStatus.objects.all()]

crop_types = [crop for crop in CropType.objects.filter(is_main_crop=True)]
tillage_management_types = [tillage for tillage in TillageManagementType.objects.all()]
organic_input_types = [organic for organic in OrganicInputType.objects.all()]
residue_management_types = [residue for residue in ResidueManagementType.objects.all()]

def_rate = ChangeRate.objects.get(name="D")


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

    implementation_duration_yrs = factory.fuzzy.FuzzyInteger(1, 20)
    capitalization_duration_yrs = factory.fuzzy.FuzzyInteger(1, 20)


class ActivityFactory(DjangoModelFactory):
    class Meta:
        model = Activity

    name = factory.fuzzy.FuzzyText()
    user = factory


sm_gear_type = random.choice(sma_gear_types)
lge_gear_type = random.choice(lge_gear_types)


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
    total_catch_yr_w_rate = def_rate
    total_catch_yr_wo = factory.fuzzy.FuzzyFloat(0.0, 100)
    total_catch_yr_wo_rate = def_rate

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

    crop_type = factory.fuzzy.FuzzyChoice(crop_types)
    tillage_management_type = factory.fuzzy.FuzzyChoice(tillage_management_types)
    organic_input_type = factory.fuzzy.FuzzyChoice(organic_input_types)
    residue_management_type = factory.fuzzy.FuzzyChoice(residue_management_types)

    ha_start = factory.fuzzy.FuzzyInteger(0.0, 100)
    ha_w = factory.fuzzy.FuzzyInteger(0.0, 100)
    ha_w_rate = def_rate
    ha_wo = factory.fuzzy.FuzzyInteger(0.0, 100)
    ha_wo_rate = def_rate

    crop_yield = factory.fuzzy.FuzzyInteger(0.0, 100)


class PerennialCroppingFactory(DjangoModelFactory):
    class Meta:
        model = PerennialCropping

    crop_type = factory.fuzzy.FuzzyChoice(crop_types)
    tillage_management_type = factory.fuzzy.FuzzyChoice(tillage_management_types)
    organic_input_type = factory.fuzzy.FuzzyChoice(organic_input_types)
    is_biomass_burned = factory.fuzzy.FuzzyChoice([True, False])

    ha_start = factory.fuzzy.FuzzyInteger(0, 100)
    ha_w = factory.fuzzy.FuzzyInteger(0, 100)
    ha_w_rate = def_rate
    ha_wo = factory.fuzzy.FuzzyInteger(0, 100)
    ha_wo_rate = def_rate

    crop_yield = factory.fuzzy.FuzzyInteger(0, 100)
