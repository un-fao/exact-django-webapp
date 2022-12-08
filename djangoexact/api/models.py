from django.db.models import *
from django.contrib.auth import models as auth_models
from polymorphic.models import PolymorphicModel
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

RICE_CULTIVATION_DAYS = 113

# Create your models here.
class User(auth_models.User):
    class Meta:
        proxy = True

    def __str__(self):
        return f"{self.username}"

##############################
############# ELSE ###########
##############################

class VegetationType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class LandUseType(Model):
    name = CharField(max_length=100)
    parent = ForeignKey(
        "self", 
        on_delete=CASCADE, 
        null=True, 
        blank=True, 
        related_name="children", 
        limit_choices_to={'parent': None}
    )

    def __str__(self):
        return self.name

class ChangeDynamic(Model):
    name = CharField(max_length=25)
    value = IntegerField(unique=True)

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

##############################
############ FORMS ###########
##############################

class Project(Model):
    # TODO: Implement uuid instead of BigAutoField?
    # id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = ForeignKey(User, on_delete=CASCADE)
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

    def __str__(self):
        return self.name

##############################
######### LAND USE ###########
##############################

class LandUseInput(Model):

    class Meta:
        abstract = True

    project = ForeignKey(Project, on_delete=CASCADE)

    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    land_use_type = ForeignKey(
        LandUseType,
        on_delete=CASCADE, 
        null=True, 
        blank=True, 
        limit_choices_to=Q(parent__isnull=True) | Q(parent__name="Agroforestry")
    )
    is_fire_used = BooleanField(default=False)
    ha_w  = IntegerField()
    ha_w_rate = ForeignKey(ChangeDynamic, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = IntegerField()
    ha_wo_rate = ForeignKey(ChangeDynamic, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate+")

    def get_child_input(self):
        child = None
        match self.land_use_type_name:
            case "Agroforestry":
                child = input.perennialcroppinginput_set.first()
            case "Annual Cropping":
                child = input.annualcroppinginput_set.first()
            case "Flooded Rice":
                child = input.floodedriceinput_set.first()
        return child
    # See https://docs.djangoproject.com/en/1.8/ref/contrib/contenttypes/#generic-relations
    content_type = ForeignKey(ContentType, null=True, blank=True, on_delete=CASCADE)
    object_id = PositiveIntegerField(null=True, blank=True)
    child_input = GenericForeignKey('content_type', 'object_id')

class DeforestationInput(LandUseInput):

    hwp = FloatField()
    ha_start = IntegerField()

    rcs_ag_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for above-ground biomass (in tC/ha)")
    rcs_bg_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for below-ground biomass (in tC/ha)")
    rcs_litter_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for litter (in tC/ha)")
    rcs_deadwood_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for deadwood (in tC/ha)")
    rcs_soil_c_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for soil carbon (in tC/ha)") 
    final_rcs_biomass_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for biomass in final land use (in tC/ha)")
    final_rcs_soil_c_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for soil carbon in final land use (in tC/ha)")

    def __str__(self):
        return f"{self.land_use_type.name} in a {self.vegetation_type.name}"

class AfforestationInput(LandUseInput):
    # TODO: Add T2 values

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
        return f"AfforestationInput for {self.vegetation_type.name}"

class OtherLandUseChangeInput(LandUseInput):
    # TODO: Add T2 values

    notes = TextField(null=True, blank=True)
    final_land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, related_name="%(class)s_final_land_use_type")

    def __str__(self):
        return f"OtherLandUseChangeInput for {self.vegetation_type.name}"

##############################
######### CROPLAND ###########
##############################

class CroplandInput(Model):

    class Meta:
        abstract = True
    
    project = ForeignKey(Project, on_delete=CASCADE)

    # See https://docs.djangoproject.com/en/1.8/ref/contrib/contenttypes/#generic-relations
    content_type = ForeignKey(ContentType, on_delete=CASCADE)
    input_id = PositiveIntegerField()
    input = GenericForeignKey('content_type', 'input_id')

class AnnualCroppingInput(CroplandInput):
    tillage_management_type = ForeignKey(TillageManagementType, on_delete=CASCADE)
    organic_input_type = ForeignKey(OrganicInputType, on_delete=CASCADE)
    residue_management_type = ForeignKey(ResidueManagementType, on_delete=CASCADE)
    crop_yield = FloatField()

    def __str__(self):
        return f"AnnualCroppingInput for {self.input.land_use_type.name} in {self.project.name}"

class RemainingAnnualCroppingInput(AnnualCroppingInput):
    user_notes = TextField(null=True, blank=True)
    ha_start = IntegerField()
    ha_w = IntegerField()
    ha_w_rate = ForeignKey(ChangeDynamic, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = IntegerField()
    ha_wo_rate = ForeignKey(ChangeDynamic, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate")

class PerennialCroppingInput(CroplandInput):
    tillage_management_type = ForeignKey(TillageManagementType, on_delete=CASCADE)
    organic_input_type = ForeignKey(OrganicInputType, on_delete=CASCADE)
    is_biomass_burned = BooleanField()
    crop_yield = FloatField()

class RemainingPerennialCroppingInput(PerennialCroppingInput):
    user_notes = TextField(null=True, blank=True)
    ha_start = IntegerField()
    ha_w = IntegerField()
    ha_w_rate = ForeignKey(ChangeDynamic, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = IntegerField()
    ha_wo_rate = ForeignKey(ChangeDynamic, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate")

class FloodedRiceInput(CroplandInput):
    cultivation_period = IntegerField(default=RICE_CULTIVATION_DAYS)
    water_management_type_before_cultivation = ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=CASCADE)
    water_management_type_after_cultivation = ForeignKey(WaterManagementTypeAfterCultivation, on_delete=CASCADE)
    organic_amendment_type = ForeignKey(OrganicAmendmentType, on_delete=CASCADE)
    crop_yield = FloatField()

class RemainingFloodedRiceInput(FloodedRiceInput):
    user_notes = TextField(null=True, blank=True)
    ha_start = IntegerField()
    ha_w = IntegerField()
    ha_w_rate = ForeignKey(ChangeDynamic, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = IntegerField()
    ha_wo_rate = ForeignKey(ChangeDynamic, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate")
    ha_total_remaining = IntegerField()