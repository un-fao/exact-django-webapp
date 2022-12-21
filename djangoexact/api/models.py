from django.db.models import *
from django.contrib.auth import models as auth_models
from django.core.validators import RegexValidator

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
        return f"{self.name}"+(f" of {self.parent_land_use}" if self.parent_land_use else "")

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
        return self.name

class Country(Model):
    name = CharField(max_length=100)
    continent = ForeignKey(Continent, on_delete=CASCADE)

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
        return self.name

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
        return self.name

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
        return self.name

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
    name = CharField(max_length=100, )

    def __str__(self):
        return self.name

##############################
########## MODULES ###########
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

class Activity(Model):
    project = ForeignKey(Project, on_delete=CASCADE)
    name = CharField(max_length=255)
    description = TextField(null=True, blank=True)
    user = ForeignKey(User, on_delete=CASCADE)
    created_at = DateTimeField(auto_now_add=True, null=True)
    updated_at = DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.name

class Module(Model):
    activity = ForeignKey(Activity, on_delete=CASCADE)

    class Meta:
        abstract = True

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
    ha_start = IntegerField()
    ha_w  = IntegerField()
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = IntegerField()
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate+")

    rcs_ag_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for above-ground biomass (in tC/ha)")
    rcs_bg_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for below-ground biomass (in tC/ha)")
    rcs_litter_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for litter (in tC/ha)")
    rcs_deadwood_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for deadwood (in tC/ha)")
    rcs_soil_c_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for soil carbon (in tC/ha)") 
    final_rcs_biomass_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for biomass in final land use (in tC/ha)")
    final_rcs_soil_c_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for soil carbon in final land use (in tC/ha)")

    def __str__(self):
        return f"Deforestation fof {self.land_use_type.name}"

class Afforestation(Module):

    land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, null= True, blank=True)
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE, null= True, blank=True)

    is_fire_used = BooleanField(default=False)

    ha_w  = IntegerField()
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = IntegerField()
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

    def __str__(self):
        return f"Afforestation for {self.land_use_type.name}"

class OtherLandUseChange(Module):

    notes = TextField(null=True, blank=True)
    initial_land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, related_name="%(class)s_initial_land_use_type", null= True, blank=True)
    final_land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, related_name="%(class)s_land_use_type", null= True, blank=True)

    is_fire_used = BooleanField(default=False)

    ha_w  = IntegerField()
    ha_w_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = IntegerField()
    ha_wo_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate+")

    initial_biomass_t2 = FloatField(null=True, blank=True)
    initial_soil_carbon_t2 = FloatField(null=True, blank=True)

    final_biomass_t2 = FloatField(null=True, blank=True)
    final_soil_carbon_t2 = FloatField(null=True, blank=True)

    implementation_year_start = IntegerField(null=True, blank=True)

    def __str__(self):
        return f"OtherLandUseChange for {self.final_land_use_type.name}"

class AnnualCropping(Module):

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

    def __str__(self):
        return f"AnnualCroppingInput for activity {self.activity.name}, crop {self.land_use_type.name} in project {self.activity.project.name}"

class PerennialCropping(Module):

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
    crop_yield = FloatField()

    def __str__(self):
        return f"PerennialCroppingInput for activity {self.activity.name}, {self.agroforestry_system.name} in project {self.activity.module.project.name}"

class FloodedRice(Module):

    user_notes = TextField(null=True, blank=True)

    cultivation_period = IntegerField(default=RICE_CULTIVATION_DAYS)
    water_management_type_before_cultivation = ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=CASCADE)
    water_management_type_after_cultivation = ForeignKey(WaterManagementTypeAfterCultivation, on_delete=CASCADE)
    organic_amendment_type = ForeignKey(OrganicAmendmentType, on_delete=CASCADE)
    crop_yield = FloatField()

    def __str__(self):
        return f"FloodedRice for activity {self.activity.name} in project {self.activity.project.name}"

class Grassland(Module):

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

    def __str__(self):
        return f"GrasslandInput for activity {self.activity.name} in project {self.activity.project.name}"

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

