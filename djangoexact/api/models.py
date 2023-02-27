from django.db.models import *
from django.contrib.auth import models as auth_models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

alphanumeric = RegexValidator(r'^[0-9a-zA-Z]*$', 'Only alphanumeric characters are allowed.')
letters_only = RegexValidator(r'^[a-zA-Z]*$', 'Only letters are allowed.')
capitalized = RegexValidator(r'[A-Z][a-z]*(\s[A-Z][a-z]*)*', 'Only capitalized words are allowed.')

RICE_CULTIVATION_DAYS = 113

# Create your models here.
class User(auth_models.User):
    class Meta:
        proxy = True

    def __str__(self):
        return f"{self.username}"

##############################
############# MISC ###########
##############################

class VegetationType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class ActivityType(Model):
    name = CharField(max_length=255, validators=[letters_only, capitalized])

    def __str__(self):
        return self.name

class LandUseType(Model):
    
    name = CharField(max_length=100)
    parent_land_use = ForeignKey(
        "self", 
        on_delete=CASCADE, 
        null=True, 
        blank=True, 
        related_name="children", 
        limit_choices_to={'parent_land_use': None}
    )

    assessment_activity = ForeignKey(ActivityType, on_delete=CASCADE, null=True, blank=True)

    needs_assessment = BooleanField(default=False)

    def __str__(self):
        return f"({self.pk}) {self.name}"+(f" of {self.parent_land_use}" if self.parent_land_use else "")

class ChangeRate(Model):
    name = CharField(max_length=25)
    value = FloatField(unique=True)

    def __str__(self):
        return self.name

class ProjectStatus(Model):
    name = CharField(max_length=25)
    value = IntegerField(unique=True)

    class Meta:
        verbose_name_plural = "Project statuses"

    def __str__(self):
        return self.name

class Continent(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"

class Country(Model):
    name = CharField(max_length=100)
    continent = ForeignKey(Continent, on_delete=CASCADE, null=True, blank=True)

    class Meta:
        verbose_name_plural = "Countries"

    def __str__(self):
        return self.name

class Climate(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class Moisture(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class SoilType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class Input(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class TillageType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class OrganicInputType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"

class ResidueManagementType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class WaterRegimeType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class PreSeasonWaterRegimeType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class OrganicAmendmentType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class TillageManagementType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"

class WaterManagementTypeBeforeCultivation(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class WaterManagementTypeAfterCultivation(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class GrasslandManagementType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class LivestockCategoryType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class LivestockProductionType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class ManureManagementType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class ModuleType(Model):
    name = CharField(max_length=100, unique=True)
    verbose_name = CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

class ForestDegradationLevel(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class FireType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class PeatType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class WaterbodyType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class TrophicType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name
 
class FisheryType(Model):
    name = CharField(max_length=255)

    def __str__(self):
        return self.name

class GearType(Model):
    name = CharField(max_length=255)

    def __str__(self):
        return self.name

class FishType(Model):
    name = CharField(max_length=255)

    def __str__(self):
        return self.name

class LargeFisheryFUI(Model):
    fish_type = ForeignKey(FishType, on_delete=CASCADE)
    gear_type = ForeignKey(GearType, on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.fish_type} - {self.gear_type} FUI: {self.value}"

class SmallFisheryFUI(Model):
    fishery_type = ForeignKey(FisheryType, on_delete=CASCADE)
    gear_type = ForeignKey(GearType, on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.fishery_type} - {self.gear_type} FUI: {self.value}"

class ElectricityEmission(Model):
    country = ForeignKey(Country, on_delete=CASCADE)
    continent = ForeignKey(Continent, on_delete=CASCADE)
    year = IntegerField(null=True, blank=True)

    ef_grid = FloatField(null=True, blank=True)
    final_ef_grid = FloatField(null=True, blank=True)
    operating_margin = FloatField(null=True, blank=True)

    # TODO: In the Excel file this is calculated in Elec G5, but here I'm putting it as static. Ask about this.
    combined_margin = FloatField(null=True, blank=True)

    # TODO: What is this exactly?
    for_formulas = FloatField(null=True, blank=True)

    def __str__(self):
        return f"Electricity Emissions for {self.country}"

class SalinityType(Model):
    value = CharField(max_length=3)

    def __str__(self):
        return self.value

##############################
########## Project ###########
##############################

class Project(Model):
    # TODO: Implement uuid instead of BigAutoField?
    # id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = ForeignKey(User, on_delete=CASCADE, related_name="projects")
    date = DateTimeField(auto_now_add=True)
    name = CharField(max_length=100)
    code = CharField(max_length=100)
    cost = FloatField()
    funding_agency = CharField(max_length=100)
    executing_agency = CharField(max_length=100)
    status = ForeignKey(ProjectStatus, on_delete=CASCADE)

    implementation_duration_yrs = FloatField()
    capitalization_duration_yrs = FloatField()

    continent = ForeignKey(Continent, on_delete=CASCADE)
    country = ForeignKey(Country, on_delete=CASCADE)
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    soil_type = ForeignKey(SoilType, on_delete=CASCADE)

    gw_potential = ForeignKey('ipcc.GlobalWarmingPotential', on_delete=CASCADE)

    soc_ref = ForeignKey('ipcc.SoilOrganicCarbon', on_delete=CASCADE)
    soc_ref_t2 = FloatField(null=True, blank=True)

    def __str__(self):
        return self.name

##############################
######### Activity ###########
##############################

class Activity(Model):
    project = ForeignKey(Project, on_delete=CASCADE)
    name = CharField(max_length=255)
    description = TextField(null=True, blank=True)
    user = ForeignKey(User, on_delete=CASCADE)
    created_at = DateTimeField(auto_now_add=True, null=True)
    updated_at = DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.name

##############################
########## Modules ###########
##############################

class Module(Model):
    activity = ForeignKey(Activity, on_delete=CASCADE)
    notes = TextField(null=True, blank=True)

    def __str__(self):
        return f"{self._meta.object_name} in {self.activity.name}"

    class Meta:
        abstract = True

##### Land Use Changes #####

class Deforestation(Module):

    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    land_use_type = ForeignKey(
        LandUseType,
        on_delete=CASCADE, 
        null=True, 
        blank=True, 
        limit_choices_to=Q(parent_land_use__isnull=True) | Q(parent_land_use__name="Agroforestry")
    )

    hwp = FloatField()
    is_fire_used = BooleanField(default=False)
    ha_start = FloatField()
    ha_w  = FloatField()
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField()
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate+")

    rcs_ag_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for above-ground biomass (in tC/ha)")
    rcs_bg_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for below-ground biomass (in tC/ha)")
    rcs_litter_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for litter (in tC/ha)")
    rcs_deadwood_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for deadwood (in tC/ha)")
    rcs_soil_c_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for soil carbon (in tC/ha)") 
    final_rcs_biomass_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for biomass in final land use (in tC/ha)")
    final_rcs_soil_c_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for soil carbon in final land use (in tC/ha)")

class Afforestation(Module):

    land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, null= True, blank=True)
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE, null= True, blank=True)

    is_fire_used = BooleanField(default=False)

    ha_w  = FloatField()
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField()
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate+")

    initial_biomass_t2 = FloatField(null=True, blank=True)
    initial_soil_carbon_t2 = FloatField(null=True, blank=True)
    final_ag_biomass_le_20yrs_t2 = FloatField(null=True, blank=True)
    final_ag_biomass_gt_20yrs_t2 = FloatField(null=True, blank=True)
    final_bg_biomass_le_20yrs_t2 = FloatField(null=True, blank=True)
    final_bg_biomass_gt_20yrs_t2 = FloatField(null=True, blank=True)
    final_rcs_t2 = FloatField(null=True, blank=True)
    final_litter_t2 = FloatField(null=True, blank=True)
    final_dw_t2 = FloatField(null=True, blank=True)
    final_soil_carbon_t2 = FloatField(null=True, blank=True)

    yearly_ghg_t2 = FloatField(null=True, blank=True)

class OtherLandUse(Module):

    notes = TextField(null=True, blank=True)
    initial_land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, related_name="%(class)s_initial_land_use_type", null= True, blank=True)
    final_land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, related_name="%(class)s_land_use_type", null= True, blank=True)

    is_fire_used = BooleanField(default=False)

    ha_w  = FloatField()
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField()
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate+")

    initial_biomass_t2 = FloatField(null=True, blank=True)
    initial_soil_carbon_t2 = FloatField(null=True, blank=True)

    final_biomass_t2 = FloatField(null=True, blank=True)
    final_soil_carbon_t2 = FloatField(null=True, blank=True)

    implementation_year_start = IntegerField(null=True, blank=True)

##### Cropland Management #####

class Assessment(Module):

    parent_afforestation = OneToOneField(Afforestation, on_delete=CASCADE, null=True, blank=True, related_name='%(class)s_assessment')
    parent_deforestation = OneToOneField(Deforestation, on_delete=CASCADE, null=True, blank=True, related_name='%(class)s_assessment')
    parent_other_land_use = OneToOneField(OtherLandUse, on_delete=CASCADE, null=True, blank=True, related_name='%(class)s_assessment')

    def clean(self) -> None:
        super().clean()
        fields = [self.parent_afforestation, self.parent_deforestation, self.parent_other_land_use]
        if len([f for f in fields if f]) > 1:
            raise ValidationError("Exactly one of deforestation, afforestation, or other land use can be set.")

    class Meta:
        abstract = True

class AnnualCropping(Assessment):

    user_notes = TextField(null=True, blank=True)

    land_use_type = ForeignKey(
        LandUseType,
        on_delete=CASCADE, 
        null=True, 
        blank=True, 
        limit_choices_to=Q(parent_land_use__name="Annual Cropland")
    )
    tillage_management_type = ForeignKey(TillageManagementType, on_delete=CASCADE)
    organic_input_type = ForeignKey(OrganicInputType, on_delete=CASCADE)
    residue_management_type = ForeignKey(ResidueManagementType, on_delete=CASCADE)
    crop_yield = FloatField()

    ha_start = FloatField()
    ha_w = FloatField()
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField()
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate+")

    main_soil_carbon_t2 = FloatField(null=True, blank=True)
    main_tillage_factor_t2 = FloatField(null=True, blank=True)
    main_organic_input_factor_t2 = FloatField(null=True, blank=True)
    main_biomass_factor_t2 = FloatField(null=True, blank=True)

    main_land_use_factor_t2 = FloatField(null=True, blank=True)

    minor_crop_type_t2 = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_minor_crop_type")
    minor_yield_t2 = FloatField(null=True, blank=True)
    minor_residue_management_type_t2 = ForeignKey(ResidueManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_minor_residue_management_type")
    minor_biomass_factor_t2 = FloatField(null=True, blank=True)

class PerennialCropping(Assessment):

    user_notes = TextField(null=True, blank=True)

    land_use_type = ForeignKey(
        LandUseType,
        on_delete=CASCADE, 
        null=True,
        blank=True,
        limit_choices_to=Q(parent_land_use__name="Agroforestry")
    )

    tillage_management_type = ForeignKey(TillageManagementType, on_delete=CASCADE)
    organic_input_type = ForeignKey(OrganicInputType, on_delete=CASCADE)
    is_biomass_burned = BooleanField()

    ha_start = FloatField()
    ha_w = FloatField()
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField()
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate+")

    crop_yield = FloatField()

    ag_t2 = FloatField(null=True, blank=True)
    bg_t2 = FloatField(null=True, blank=True)
    soc_t2 = FloatField(null=True, blank=True)
    tillage_factor_t2 = FloatField(null=True, blank=True)
    input_factor_t2 = FloatField(null=True, blank=True)
    residue_burned_t2 = FloatField(null=True, blank=True)
    fire_periodicity_t2 = FloatField(null=True, blank=True)

    flu_t2 = FloatField(null=True, blank=True)

class FloodedRice(Assessment):

    user_notes = TextField(null=True, blank=True)

    cultivation_period = IntegerField(default=RICE_CULTIVATION_DAYS)
    water_management_type_before_cultivation = ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=CASCADE)
    water_management_type_after_cultivation = ForeignKey(WaterManagementTypeAfterCultivation, on_delete=CASCADE)
    organic_amendment_type = ForeignKey(OrganicAmendmentType, on_delete=CASCADE)
    crop_yield = FloatField()

##### Grassland and Livestock #####

class Grassland(Assessment):

    description = TextField(null=True, blank=True)
    user_notes = TextField(null=True, blank=True)

    grassland_at_start = ForeignKey(GrasslandManagementType, on_delete=CASCADE, related_name="%(class)s_start")
    grassland_without = ForeignKey(GrasslandManagementType, on_delete=CASCADE, related_name="%(class)s_without")
    grassland_with = ForeignKey(GrasslandManagementType, on_delete=CASCADE, related_name="%(class)s_with")

    years_w_fire_management = IntegerField(null=True, blank=True)
    years_wo_fire_management = IntegerField(null=True, blank=True)

    yield_start = FloatField(null=True, blank=True)
    yield_w = FloatField(null=True, blank=True)
    yield_wo = FloatField(null=True, blank=True)

    # Tier 2 values
    soil_carbon_start_t2 = FloatField(null=True, blank=True)
    soil_carbon_w_t2 = FloatField(null=True, blank=True)
    soil_carbon_wo_t2 = FloatField(null=True, blank=True)

    agb_t2 = FloatField(null=True, blank=True)
    combustion_factor_t2 = FloatField(null=True, blank=True)

    implementation_year_start = IntegerField(null=True, blank=True)

    ha_start = IntegerField(null=True, blank=True)

class Livestock(Module):
    
    description = TextField(null=True, blank=True)
    user_notes = TextField(null=True, blank=True)

    livestock_category = ForeignKey(LivestockCategoryType, on_delete=CASCADE)
    livestock_production_type = ForeignKey(LivestockProductionType, on_delete=CASCADE)

    production_start = FloatField(null=True, blank=True)
    production_w = FloatField(null=True, blank=True)
    production_wo = FloatField(null=True, blank=True)

    heads_number_start = IntegerField(null=True, blank=True)
    heads_number_w = IntegerField(null=True, blank=True)
    heads_number_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_heads_number_w_rate")
    heads_number_wo = IntegerField(null=True, blank=True)
    heads_number_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_heads_number_wo_rate")

    enteric_fermentation_start_t2 = FloatField(null=True, blank=True)
    enteric_fermentation_w_t2 = FloatField(null=True, blank=True)
    enteric_fermentation_wo_t2 = FloatField(null=True, blank=True)

    pasture_percentage_start_t2 = FloatField(null=True, blank=True)
    pasture_percentage_w_t2 = FloatField(null=True, blank=True)
    pasture_percentage_wo_t2 = FloatField(null=True, blank=True)

    emission_factor_start_t2 = FloatField(null=True, blank=True)
    emission_factor_w_t2 = FloatField(null=True, blank=True)
    emission_factor_wo_t2 = FloatField(null=True, blank=True)

    n2o_start_t2 = FloatField(null=True, blank=True)
    n2o_w_t2 = FloatField(null=True, blank=True)
    n2o_wo_t2 = FloatField(null=True, blank=True)

    manure_management_type_t2 = ForeignKey(ManureManagementType, on_delete=CASCADE, null=True, blank=True)
    emission_factor_ch4_t2 = FloatField(null=True, blank=True)
    emission_factor_n20_t2 = FloatField(null=True, blank=True)

    implementation_year_start = IntegerField(null=True, blank=True)

##### Forest Management #####

class Forest(Module):
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    degradation_level_start = ForeignKey(ForestDegradationLevel, on_delete=CASCADE, related_name="%(class)s_start")
    degradation_level_w = ForeignKey(ForestDegradationLevel, on_delete=CASCADE, related_name="%(class)s_w")
    degradation_level_wo = ForeignKey(ForestDegradationLevel, on_delete=CASCADE, related_name="%(class)s_wo")
    is_fire_used_w = BooleanField(default=False)
    is_fire_used_wo = BooleanField(default=False)
    fire_periodicity_w = IntegerField(null=True, blank=True)
    fire_periodicity_wo = IntegerField(null=True, blank=True)
    fire_impact_percentage_w = FloatField(null=True, blank=True) # TODO: What's the default value?
    fire_impact_percentage_wo = FloatField(null=True, blank=True) # TODO: What's the default value?
    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_wo_rate")

    degradation_level_start_t2 = ForeignKey(ForestDegradationLevel, on_delete=CASCADE, related_name="%(class)s_start_t2")
    degradation_level_w_t2 = ForeignKey(ForestDegradationLevel, on_delete=CASCADE, related_name="%(class)s_w_t2")
    degradation_level_wo_t2 = ForeignKey(ForestDegradationLevel, on_delete=CASCADE, related_name="%(class)s_wo_t2")

    ag_carbon_t2 = FloatField(null=True, blank=True)
    bg_carbon_t2 = FloatField(null=True, blank=True)
    litter_t2 = FloatField(null=True, blank=True)
    deadwood_t2 = FloatField(null=True, blank=True)

    soil_carbon_t2 = FloatField(null=True, blank=True)

    land_input_factor_start_t2 = FloatField(null=True, blank=True)
    land_input_factor_w_t2 = FloatField(null=True, blank=True)
    land_input_factor_wo_t2 = FloatField(null=True, blank=True)

    implementation_year_start_t2 = IntegerField(null=True, blank=True)

##### Inland Wetlands #####

class OrganicSoil(Module):
    class Meta:
        abstract = True
    
    ag_carbon_t2 = FloatField(null=True, blank=True)
    bg_carbon_t2 = FloatField(null=True, blank=True)
    litter_t2 = FloatField(null=True, blank=True)
    deadwood_t2 = FloatField(null=True, blank=True)
    final_land_use_bgb_agb_t2 = FloatField(null=True, blank=True)

    # TODO: Should a second variable be added for each module?
    implementation_year_start_t2 = IntegerField(null=True, blank=True)

class DeforestationSoilManagement(OrganicSoil):
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    hwp = FloatField(default=0.0)
    is_fire_used = BooleanField(default=False)
    final_land_use = ForeignKey(LandUseType, on_delete=CASCADE)
    
    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_wo_rate")

    is_biomass_burned = BooleanField(default=False)

    drainage_ha_start = IntegerField(null=True, blank=True)
    drainage_ha_w = IntegerField(null=True, blank=True)
    drainage_ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drainage_ha_w_rate")
    drainage_ha_wo = IntegerField(null=True, blank=True)
    drainage_ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drainage_ha_wo_rate")

    is_fire_on_soil = BooleanField(default=False) # TODO: Find a better name?

    ag_carbon_t2 = FloatField(null=True, blank=True)
    bg_carbon_t2 = FloatField(null=True, blank=True)
    litter_t2 = FloatField(null=True, blank=True)
    deadwood_t2 = FloatField(null=True, blank=True)
    final_land_use_bgb_agb_t2 = FloatField(null=True, blank=True)

    initial_onsite_drainage_co2_t2 = FloatField(null=True, blank=True)
    initial_onsite_drainage_ch4_t2 = FloatField(null=True, blank=True)
    initial_onsite_drainage_n2o_t2 = FloatField(null=True, blank=True)
    initial_offsite_drainage_doc_t2 = FloatField(null=True, blank=True)
    initial_offsite_drainage_ch4_t2 = FloatField(null=True, blank=True)

    initial_soil_fire_type_t2 = ForeignKey(FireType, on_delete=CASCADE, null=True, blank=True)
    initial_soil_fire_periodicity_w = IntegerField(null=True, blank=True)
    initial_soil_fire_impact_percentage_w = FloatField(null=True, blank=True) # TODO: What's the default value?
    initial_soil_fire_periodicity_wo = IntegerField(null=True, blank=True)
    initial_soil_fire_impact_percentage_wo = FloatField(null=True, blank=True) # TODO: What's the default value?

    initial_soil_co2_t2 = FloatField(null=True, blank=True)
    initial_soil_co_t2 = FloatField(null=True, blank=True)
    initial_soil_ch4_t2 = FloatField(null=True, blank=True)
    initial_soil_mean_dry_matter_t2 = FloatField(null=True, blank=True)

class AfforestationSoilManagement(OrganicSoil):

    final_vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    initial_land_use = ForeignKey(LandUseType, on_delete=CASCADE)

    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_wo_rate")

    is_biomass_burned = BooleanField(default=False)

    # Area under drainage
    drained_ha_w = IntegerField(null=True, blank=True)
    drained_ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drained_ha_w_rate")
    drained_ha_wo = IntegerField(null=True, blank=True)
    drained_ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drained_ha_wo_rate")

    # TODO: Find a better name?
    is_fire_on_soil = BooleanField(default=False) 

    # TODO: Replace other occurrences with this variable name
    initial_ag_bg_biomass_t2 = FloatField(null=True, blank=True) 

    final_ag_biomass_upto_20yrs_t2 = FloatField(null=True, blank=True)
    final_ag_biomass_after_20yrs_t2 = FloatField(null=True, blank=True)

    final_bg_biomass_upto_20yrs_t2 = FloatField(null=True, blank=True)
    final_bg_biomass_after_20yrs_t2 = FloatField(null=True, blank=True)

    final_socref_ag_bg_t2 = FloatField(null=True, blank=True)
    final_litter_t2 = FloatField(null=True, blank=True)
    final_deadwood_t2 = FloatField(null=True, blank=True)

class OtherLandUseSoilManagement(OrganicSoil):

    is_fire_used = BooleanField(default=False)

    initial_land_use = ForeignKey(LandUseType, on_delete=CASCADE, related_name="%(class)s_initial_land_use")
    final_land_use = ForeignKey(LandUseType, on_delete=CASCADE, related_name="%(class)s_final_land_use")

    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_wo_rate")

    is_biomass_burned = BooleanField(default=False)

    # Area under drainage
    drained_ha_start = IntegerField(null=True, blank=True)
    drained_ha_w = IntegerField(null=True, blank=True)
    drained_ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drained_ha_w_rate")
    drained_ha_wo = IntegerField(null=True, blank=True)
    drained_ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drained_ha_wo_rate")

    is_fire_on_soil = BooleanField(default=False)

    initial_ag_carbon_t2 = FloatField(null=True, blank=True)
    final_ag_carbon_t2 = FloatField(null=True, blank=True)

class ForestLandManagement(Module):
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)

    degradation_level_start = ForeignKey(ForestDegradationLevel, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_degradation_level_start")
    degradation_level_w = ForeignKey(ForestDegradationLevel, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_degradation_level_w")
    degradation_level_wo = ForeignKey(ForestDegradationLevel, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_degradation_level_wo")

    # TODO: Are ha_w and ha_wo read-only in the Excel sheet?
    ha_start = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_w_rate")
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_wo_rate")

    is_biomass_burned = BooleanField(default=False)

    # Area under drainage
    drained_ha_start = IntegerField(null=True, blank=True)
    drained_ha_w = IntegerField(null=True, blank=True)
    drained_ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drained_ha_w_rate")
    drained_ha_wo = IntegerField(null=True, blank=True)
    drained_ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drained_ha_wo_rate")

    is_fire_on_soil = BooleanField(default=False)

    degradation_level_start_t2 = FloatField(null=True, blank=True)
    degradation_level_w_t2 = FloatField(null=True, blank=True)
    degradation_level_wo_t2 = FloatField(null=True, blank=True)

    ag_carbon_t2 = FloatField(null=True, blank=True)
    bg_carbon_t2 = FloatField(null=True, blank=True)
    litter_t2 = FloatField(null=True, blank=True)
    deadwood_t2 = FloatField(null=True, blank=True)

    initial_onsite_drainage_co2_t2 = FloatField(null=True, blank=True)
    initial_onsite_drainage_ch4_t2 = FloatField(null=True, blank=True)
    initial_onsite_drainage_n2o_t2 = FloatField(null=True, blank=True)

    initial_offsite_drainage_doc_t2 = FloatField(null=True, blank=True)
    initial_offsite_drainage_ch4_t2 = FloatField(null=True, blank=True)

    initial_soil_fire_type_t2 = ForeignKey(FireType, on_delete=CASCADE, null=True, blank=True)
    initial_soil_fire_periodicity_w = IntegerField(null=True, blank=True)
    initial_soil_fire_impact_percentage_w = FloatField(null=True, blank=True) # TODO: What's the default value? And the max value?
    initial_soil_fire_periodicity_wo = IntegerField(null=True, blank=True)
    initial_soil_fire_impact_percentage_wo = FloatField(null=True, blank=True) # TODO: What's the default value? And the max value?

    initial_soil_co2_t2 = FloatField(null=True, blank=True)
    initial_soil_co_t2 = FloatField(null=True, blank=True)
    initial_soil_ch4_t2 = FloatField(null=True, blank=True)
    initial_soil_mean_dry_matter_t2 = FloatField(null=True, blank=True)

    final_rewitting_onsite_co2_t2 = FloatField(null=True, blank=True)
    final_rewitting_onsite_ch4_t2 = FloatField(null=True, blank=True)
    final_rewitting_n2o_t2 = FloatField(null=True, blank=True)
    final_rewitting_offsite_doc_t2 = FloatField(null=True, blank=True)

class OtherLandManagement(Module):
    land_use_type = ForeignKey(
        LandUseType, 
        on_delete=CASCADE, 
        limit_choices_to=Q(parent_land_use__isnull=True) | Q(parent_land_use__name="Agroforestry")
    )

    land_use_area = FloatField(null=True, blank=True)

    drainage_ha_start = FloatField(null=True, blank=True)
    drainage_ha_w = FloatField(null=True, blank=True)
    drainage_ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drained_ha_w_rate")
    drainage_ha_wo = FloatField(null=True, blank=True)
    drainage_ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drained_ha_wo_rate")

    is_management_burned = BooleanField(default=False)
    is_fire_on_soil = BooleanField(default=False)

    onsite_drainage_co2_t2 = FloatField(null=True, blank=True)
    onsite_drainage_ch4_t2 = FloatField(null=True, blank=True)
    onsite_drainage_n2o_t2 = FloatField(null=True, blank=True)
    offsite_drainage_doc_t2 = FloatField(null=True, blank=True)
    offsite_drainage_ch4_t2 = FloatField(null=True, blank=True)

    soil_fire_type_t2 = ForeignKey(FireType, on_delete=CASCADE, null=True, blank=True)
    soil_fire_periodicity_w = IntegerField(null=True, blank=True)
    soil_fire_impact_percentage_w = FloatField(null=True, blank=True) # TODO: What's the default value? And the max value?
    soil_fire_periodicity_wo = IntegerField(null=True, blank=True)
    soil_fire_impact_percentage_wo = FloatField(null=True, blank=True) # TODO: What's the default value? And the max value?
    soil_co2_t2 = FloatField(null=True, blank=True)
    soil_co_t2 = FloatField(null=True, blank=True)
    soil_ch4_t2 = FloatField(null=True, blank=True)
    soil_mean_dry_matter_t2 = FloatField(null=True, blank=True)

    rewetting_onsite_co2_t2 = FloatField(null=True, blank=True)
    rewetting_onsite_ch4_t2 = FloatField(null=True, blank=True)
    rewetting_n2o_t2 = FloatField(null=True, blank=True)
    rewetting_offsite_doc_t2 = FloatField(null=True, blank=True)

class PeatExtractionLandManagement(Module):
    peat_type = ForeignKey(PeatType, on_delete=CASCADE)

    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_wo_rate")

    ditches_percentage_start = FloatField(null=True, blank=True)
    ditches_percentage_w = FloatField(null=True, blank=True)
    ditches_percentage_wo = FloatField(null=True, blank=True)

    extraction_height_start = FloatField(null=True, blank=True)
    extraction_height_w = FloatField(null=True, blank=True)
    extraction_height_wo = FloatField(null=True, blank=True)

    onsite_drainage_co2_t2 = FloatField(null=True, blank=True)
    onsite_drainage_ch4_t2 = FloatField(null=True, blank=True)
    onsite_drainage_n2o_t2 = FloatField(null=True, blank=True)
    offsite_drainage_doc_t2 = FloatField(null=True, blank=True)
    offsite_drainage_ch4_t2 = FloatField(null=True, blank=True)

    peat_density_t2 = FloatField(null=True, blank=True)
    is_used_for_energy_t2 = BooleanField(default=False)

class InlandWaterbody(Module):
    waterbody_type = ForeignKey(WaterbodyType, on_delete=CASCADE)

    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_wo_rate")

    trophic_type = ForeignKey(TrophicType, on_delete=CASCADE, null=True, blank=True)

    ch4_emissions_start_t2 = FloatField(null=True, blank=True)
    ch4_emissions_w_t2 = FloatField(null=True, blank=True)
    ch4_emissions_wo_t2 = FloatField(null=True, blank=True)

    trophic_alpha_t2 = FloatField(null=True, blank=True)
    trophic_mean_annual_t2 = FloatField(null=True, blank=True)

##### Coastal Wetlands #####

class Extraction(Module):
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    ha_start = IntegerField(null=True, blank=True)
    ha_w_excavated_percentage = FloatField(null=True, blank=True)
    ha_wo_excavated_percentage = FloatField(null=True, blank=True)

    extraction_ag_t2 = FloatField(null=True, blank=True)
    extraction_bg_t2 = FloatField(null=True, blank=True)
    extraction_litter_t2 = FloatField(null=True, blank=True)
    extraction_deadwood_t2 = FloatField(null=True, blank=True)
    extraction_soil_type_t2 = ForeignKey(SoilType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_extracted_soil_type_t2")
    extraction_soil_t2 = FloatField(null=True, blank=True)
    c_after_excavation_t2 = FloatField(null=True, blank=True, default=.96)

    # TODO: Drainage as separate module? (probably not, since it's only used here)
    drainage_percentage_start = FloatField(null=True, blank=True)
    drainage_percentage_w = FloatField(null=True, blank=True)
    drainage_percentage_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drainage_percentage_w_rate")
    drainage_percentage_wo = FloatField(null=True, blank=True)
    drainage_percentage_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drainage_percentage_wo_rate")

    drainage_ag_t2 = FloatField(null=True, blank=True)
    drainage_bg_t2 = FloatField(null=True, blank=True)
    drainage_litter_t2 = FloatField(null=True, blank=True)
    drainage_deadwood_t2 = FloatField(null=True, blank=True)
    drainage_soil_type_t2 = ForeignKey(SoilType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_drained_soil_type_t2")
    drainage_soil_t2 = FloatField(null=True, blank=True)

    ef_drainage_t2 = FloatField(null=True, blank=True)

class Rewetting(Module):
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_wo_rate")

    restored_biomass_percentage_w = FloatField(null=True, blank=True)
    restored_biomass_percentage_wo = FloatField(null=True, blank=True)

    ag_t2 = FloatField(null=True, blank=True)
    bg_t2 = FloatField(null=True, blank=True)
    litter_t2 = FloatField(null=True, blank=True)
    deadwood_t2 = FloatField(null=True, blank=True)
    avg_salinity_t2 = ForeignKey(SalinityType, on_delete=CASCADE, null=True, blank=True, default=SalinityType.objects.get(value="<18").pk)
    ef_co2_t2 = FloatField(null=True, blank=True)
    ef_ch4_t2 = FloatField(null=True, blank=True)

class CoastalWaterbody(Module):
    waterbody_type = ForeignKey(WaterbodyType, on_delete=CASCADE)
    trophic_type = ForeignKey(TrophicType, on_delete=CASCADE, null=True, blank=True)

    # NOTE: Total area must remain constant
    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_w_rate")
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_wo_rate")

    ch4_start_t2 = FloatField(null=True, blank=True)
    ch4_w_t2 = FloatField(null=True, blank=True)
    ch4_wo_t2 = FloatField(null=True, blank=True)

    trophic_alpha_t2 = FloatField(null=True, blank=True)
    trophic_mean_annual_t2 = FloatField(null=True, blank=True)

##### Fisheries and Aquaculture #####

class Fishery(Module):

    class Meta:
        abstract = True

    fishery_type = ForeignKey(FisheryType, on_delete=CASCADE)
    gear_type = ForeignKey(GearType, on_delete=CASCADE)

    refrigerant_pc_start = FloatField(null=True, blank=True)
    refrigerant_pc_w = FloatField(null=True, blank=True)
    refrigerant_pc_wo = FloatField(null=True, blank=True)

    refrigerant_gwp = FloatField(null=True, blank=True, default=1810)

    fui_start = FloatField(null=True, blank=True)
    fui_w = FloatField(null=True, blank=True)
    fui_wo = FloatField(null=True, blank=True)

    total_catch_yr_start = FloatField(null=True, blank=True)
    total_catch_yr_w = FloatField(null=True, blank=True)
    total_catch_yr_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_total_catch_yr_w_rate")
    total_catch_yr_wo = FloatField(null=True, blank=True)
    total_catch_yr_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_total_catch_yr_wo_rate")

    ice_preserved_catch_pc_start = FloatField(null=True, blank=True)
    ice_preserved_catch_pc_w = FloatField(null=True, blank=True)
    ice_preserved_catch_pc_wo = FloatField(null=True, blank=True)

    # TODO: Is the non-t2 value static for this specific module? It's always related to Gasoil/Diesel
    energy_emission_factor_t2 = FloatField(null=True, blank=True)
    refrigerant_lost_per_tonne_t2 = FloatField(null=True, blank=True)
    refrigerant_gwp_t2 = FloatField(null=True, blank=True)
    inshore_ice_production_emissions_t2 = FloatField(null=True, blank=True)

    # TODO: This part has some internal logic that has to be examined more deeply
    # NOTE: The logic does not seem to make much sense. It's just to display some values and can probably be ignored altogether
    inshore_ice_production_kwh_per_tonne_t2 = FloatField(null=True, blank=True)
    inshore_ice_production_country = ForeignKey(Country, on_delete=CASCADE, null=True, blank=True)

    implementation_year_t2 = IntegerField(null=True, blank=True)

class SmallFishery(Fishery):
    fui_default = ForeignKey(SmallFisheryFUI, on_delete=CASCADE, null=True, blank=True)

class LargeFishery(Fishery):
    fui_default = ForeignKey(LargeFisheryFUI, on_delete=CASCADE, null=True, blank=True)

class Aquaculture(Module):
    user_notes = TextField(null=True, blank=True)

    annual_feed_quantity_start = FloatField(null=True, blank=True)
    annual_feed_quantity_w = FloatField(null=True, blank=True)
    annual_feed_quantity_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_annual_feed_quantity_w_rate")
    annual_feed_quantity_wo = FloatField(null=True, blank=True)
    annual_feed_quantity_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_annual_feed_quantity_wo_rate")

    annual_production_start = FloatField(null=True, blank=True)
    annual_production_w = FloatField(null=True, blank=True)
    annual_production_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_annual_production_w_rate")
    annual_production_wo = FloatField(null=True, blank=True)
    annual_production_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_annual_production_wo_rate")

    feed_use_emissions_t2 = FloatField(null=True, blank=True)
    production_n2o_ef_t2 = FloatField(null=True, blank=True)

    implementation_year_t2 = IntegerField(null=True, blank=True)