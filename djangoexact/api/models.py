from django.db.models import *
from django.contrib.auth import models as auth_models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from .utilities import *
import uuid
from simple_history.models import HistoricalRecords

alphanumeric = RegexValidator(
    r"^[0-9a-zA-Z]*$", "Only alphanumeric characters are allowed."
)
letters_only = RegexValidator(r"^[a-zA-Z]*$", "Only letters are allowed.")
capitalized = RegexValidator(
    r"[A-Z][a-z]*(\s[A-Z][a-z]*)*", "Only capitalized words are allowed."
)
pc_as_float = RegexValidator(
    r"^[0-1]*\.?[0-9]*$", "Only correctly formatted percentages are allowed."
)

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

class CommentThread(Model):

    def __str__(self):
        return f"({self.pk})"

class Comment(Model):
    thread = ForeignKey(CommentThread, on_delete=CASCADE, related_name="comments", null=True, blank=True)
    content = TextField()
    date_created = DateTimeField(auto_now_add=True)
    author = ForeignKey(User, on_delete=CASCADE)
    parent = ForeignKey('self', null=True, blank=True, on_delete=CASCADE, related_name='replies')
    # You can add other fields like 'is_active', 'likes', etc.

    def __str__(self):
        return f"({self.pk}) {self.author.username}: {self.content[:40]}..."

class IPCCRegion(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class GLEAMRegion(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"

class ForestType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"
    
class ForestConditionType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"

class SiteLocationType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"

class VegetationType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ActivityType(Model):
    name = CharField(max_length=255, validators=[letters_only, capitalized])

    def __str__(self):
        return self.name


class ActivityState(Model):
    name = CharField(max_length=255, unique=True)
    value = FloatField(null=True, blank=True, unique=True)

    class Meta:
        verbose_name_plural = "Activity states"
        unique_together = ("name", "value")

    def __str__(self):
        return f"({self.id}) {self.name}"


class LandUseType(Model):
    name = CharField(max_length=100)
    parent = ForeignKey(
        "self",
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="children",
        limit_choices_to={"parent": None},
    )
    module_type = ForeignKey("api.ModuleType", on_delete=CASCADE, null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.name}" + (
            f" of {self.parent}" if self.parent else ""
        )


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
    name = CharField(max_length=100, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class Country(Model):
    name = CharField(max_length=100, unique=True)
    continent = ForeignKey(
        Continent, on_delete=CASCADE, null=True, blank=True, related_name="countries"
    )
    ipcc_region = ForeignKey(
        IPCCRegion, on_delete=CASCADE, null=True, blank=True, related_name="countries"
    )
    gleam_region = ForeignKey(
        GLEAMRegion, on_delete=CASCADE, null=True, blank=True, related_name="countries"
    )

    class Meta:
        verbose_name_plural = "Countries"

    def __str__(self):
        return f"({self.pk}) {self.name}"


class Climate(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class Moisture(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class SoilType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ExtractionSoilType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class TillageType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name


class OrganicInputType(Model):
    name = CharField(max_length=100, unique=True)

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
    name = CharField(max_length=100, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class WaterManagementTypeBeforeCultivation(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class WaterManagementTypeAfterCultivation(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class GrasslandManagementType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name


class LivestockCategoryType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class LivestockProductionType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ManureManagementType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ModuleType(Model):
    name = CharField(max_length=100, unique=True)
    verbose_name = CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ForestDegradationLevel(Model):
    name = CharField(max_length=100)
    value = FloatField()

    def __str__(self):
        return self.name


class FireType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


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
        return f"({self.pk}) {self.name}"


class LargeFisheryGearType(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class SmallFisheryGearType(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class FishType(Model):
    name = CharField(max_length=255)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class MacroFuelType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class FuelUseType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class FuelType(Model):
    name = CharField(max_length=100)
    fuel_use_type = ForeignKey(FuelUseType, on_delete=CASCADE, null=True, blank=True)
    macro_fuel_type = ForeignKey(
        MacroFuelType, on_delete=CASCADE, null=True, blank=True
    )

    class Meta:
        unique_together = ("name", "fuel_use_type", "macro_fuel_type")

    def __str__(self):
        macro = getattr(self.macro_fuel_type, "name", None)
        return f"({self.pk}) {macro} - {self.name}"


class SalinityType(Model):
    value = CharField(max_length=3)

    def __str__(self):
        return self.value


##############################
########## Project ###########
##############################


class BaseModel(Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True

class Historical(Model):
    history = HistoricalRecords(related_name="%(class)s_history")

    class Meta:
        abstract = True

class Project(Historical):
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

    implementation_duration_yrs = IntegerField()
    capitalization_duration_yrs = IntegerField()

    # TODO: Rename continent to region
    continent = ForeignKey(Continent, on_delete=CASCADE)
    country = ForeignKey(Country, on_delete=CASCADE)
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    soil_type = ForeignKey(SoilType, on_delete=CASCADE)

    gw_potential = ForeignKey("ipcc.GlobalWarmingPotential", on_delete=CASCADE)

    soc_ref = ForeignKey("ipcc.SoilOrganicCarbon", on_delete=CASCADE)
    soc_ref_t2 = FloatField(null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


##############################
######### Activity ###########
##############################


class Activity(Historical):
    project = ForeignKey(Project, on_delete=CASCADE, related_name="activities")
    name = CharField(max_length=255)
    description = TextField(null=True, blank=True)
    user = ForeignKey(User, on_delete=CASCADE)
    state = ForeignKey(ActivityState, on_delete=CASCADE, null=True, blank=True)
    created_at = DateTimeField(auto_now_add=True, null=True)
    updated_at = DateTimeField(auto_now=True, null=True)

    change_rate = ForeignKey(ChangeRate, on_delete=CASCADE, null=True, related_name="change_rate")

    def __str__(self):
        return f"({self.pk}) {self.name} in {self.project.name}"


##############################
########## Modules ###########
##############################

class Module(Historical):
    activity = ForeignKey(Activity, on_delete=CASCADE, related_name="%(class)s")
    notes = TextField(null=True, blank=True)
    start_year = IntegerField(default=1)

    created_at = DateTimeField(auto_now_add=True, null=True)
    updated_at = DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"({self.pk}) {self._meta.object_name} in {self.activity.name}"

    class Meta:
        abstract = True


##### Land Use Changes #####


class Deforestation(Module):
    vegetation_type_start = ForeignKey(VegetationType, on_delete=CASCADE, related_name="%(class)s_vegetation_type_start")
    vegetation_type_w = ForeignKey(VegetationType, on_delete=CASCADE, related_name="%(class)s_vegetation_type_w")
    vegetation_type_wo = ForeignKey(VegetationType, on_delete=CASCADE, related_name="%(class)s_vegetation_type_wo")


    land_use_type_start = ForeignKey(
        LandUseType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        limit_choices_to=Q(parent__isnull=True) | Q(parent__name="Agroforestry"),
        related_name="%(class)s_land_use_type_start",
    )
    land_use_type_w = ForeignKey(
        LandUseType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        limit_choices_to=Q(parent__isnull=True) | Q(parent__name="Agroforestry"),
        related_name="%(class)s_land_use_type_w",
    )
    land_use_type_wo = ForeignKey(
        LandUseType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        limit_choices_to=Q(parent__isnull=True) | Q(parent__name="Agroforestry"),
        related_name="%(class)s_land_use_type_wo",
    )

    hwp_start = FloatField()
    hwp_w = FloatField()
    hwp_wo = FloatField()

    is_fire_used_start = BooleanField(default=False)
    is_fire_used_w = BooleanField(default=False)
    is_fire_used_wo = BooleanField(default=False)

    ha_start = FloatField()
    ha_w = FloatField()
    ha_wo = FloatField()

    rcs_ag_t2_start = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for above-ground biomass (in tC/ha)",
    )
    rcs_ag_t2_w = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for above-ground biomass (in tC/ha)",
    )
    rcs_ag_t2_wo = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for above-ground biomass (in tC/ha)",
    )

    rcs_bg_t2_start = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for below-ground biomass (in tC/ha)",
    )
    rcs_bg_t2_w = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for below-ground biomass (in tC/ha)",
    )
    rcs_bg_t2_wo = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for below-ground biomass (in tC/ha)",
    )


    rcs_litter_t2_start = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for litter (in tC/ha)",
    )
    rcs_litter_t2_w = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for litter (in tC/ha)",
    )
    rcs_litter_t2_wo = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for litter (in tC/ha)",
    )
    rcs_deadwood_t2_start = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for deadwood (in tC/ha)",
    )
    rcs_deadwood_t2_w = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for deadwood (in tC/ha)",
    )
    rcs_deadwood_t2_wo = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for deadwood (in tC/ha)",
    )

    rcs_soil_c_t2_start = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for soil carbon (in tC/ha)",
    )
    rcs_soil_c_t2_w = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for soil carbon (in tC/ha)",
    )
    rcs_soil_c_t2_wo = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for soil carbon (in tC/ha)",
    )

    final_rcs_biomass_t2_start = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for biomass in final land use (in tC/ha)",
    )
    final_rcs_biomass_t2_w = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for biomass in final land use (in tC/ha)",
    )
    final_rcs_biomass_t2_wo = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for biomass in final land use (in tC/ha)",
    )

    soc_after_defo_t2_start = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for soil carbon in final land use (in tC/ha)",
    )
    soc_after_defo_t2_w = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for soil carbon in final land use (in tC/ha)",
    )
    soc_after_defo_t2_wo = FloatField(
        null=True,
        blank=True,
        help_text="Custom reference carbon stock for soil carbon in final land use (in tC/ha)",
    )


class Afforestation(Module):
    land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True)
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE, null=True, blank=True)

    is_fire_used = BooleanField(default=False)

    ha_w = FloatField()
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
    initial_land_use_type = ForeignKey(
        LandUseType,
        on_delete=CASCADE,
        related_name="%(class)s_initial_land_use_type",
        null=True,
        blank=True,
    )
    final_land_use_type = ForeignKey(
        LandUseType,
        on_delete=CASCADE,
        related_name="%(class)s_land_use_type",
        null=True,
        blank=True,
    )

    is_fire_used = BooleanField(default=False)

    ha_w = FloatField()
    ha_w_rate = ForeignKey(
        ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_w_rate"
    )
    ha_wo = FloatField()
    ha_wo_rate = ForeignKey(
        ChangeRate, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate+"
    )

    initial_biomass_t2 = FloatField(null=True, blank=True)
    initial_soil_carbon_t2 = FloatField(null=True, blank=True)

    final_biomass_t2 = FloatField(null=True, blank=True)
    final_soil_carbon_t2 = FloatField(null=True, blank=True)

    implementation_year_start = IntegerField(null=True, blank=True)


##### Cropland Management #####


class Assessment(Module):
    land_use_change = OneToOneField("api.LandUseChange", on_delete=CASCADE, null=True, blank=True, related_name="%(class)s")
    parent_afforestation = OneToOneField(
        Afforestation,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_assessment",
    )
    parent_deforestation = OneToOneField(
        Deforestation,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_assessment",
    )
    parent_other_land_use = OneToOneField(
        OtherLandUse,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_assessment",
    )

    def clean(self) -> None:
        super().clean()

        fields = [
            self.parent_afforestation,
            self.parent_deforestation,
            self.parent_other_land_use,
        ]
        if len([f for f in fields if f]) > 1:
            raise ValidationError(
                "Exactly one of deforestation, afforestation, or other land use can be set."
            )

        relative, relationship = get_relative(self)
        if relative and not relative in fields:
            raise ValidationError(f"{relative} is already a {relationship}")

    class Meta:
        abstract = True


class CropType(Model):
    name = CharField(max_length=255, unique=True)
    description = TextField(null=True, blank=True)
    is_main_crop = BooleanField(default=False)
    is_agrofoforestry = BooleanField(default=False)

    def __str__(self) -> str:
        return f"({self.pk}) {self.name}"


class AnnualCropping(Assessment):
    user_notes = TextField(null=True, blank=True)

    crop_type_start = ForeignKey(
        CropType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_crop_type_start",
    )
    crop_type_w = ForeignKey(
        CropType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_crop_type_w",
    )
    crop_type_wo = ForeignKey(
        CropType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_crop_type_wo",
    )
    crop_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_crop_type_thread")

    tillage_management_type_start = ForeignKey(
        TillageManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_tillage_management_type_start",
    )
    tillage_management_type_w = ForeignKey(
        TillageManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_tillage_management_type_w",
    )
    tillage_management_type_wo = ForeignKey(
        TillageManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_tillage_management_type_wo",
    )
    tillage_management_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_thread")

    organic_input_type_start = ForeignKey(
        OrganicInputType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_organic_input_type_start",
    )
    organic_input_type_w = ForeignKey(
        OrganicInputType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_organic_input_type_w",
    )
    organic_input_type_wo = ForeignKey(
        OrganicInputType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_organic_input_type_wo",
    )
    organic_input_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_thread")

    residue_management_type_start = ForeignKey(
        ResidueManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_residue_management_type_start",
    )
    residue_management_type_w = ForeignKey(
        ResidueManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_residue_management_type_w",
    )
    residue_management_type_wo = ForeignKey(
        ResidueManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_residue_management_type_wo",
    )
    residue_management_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_thread")

    crop_yield_start = FloatField(null=True, blank=True)
    crop_yield_w = FloatField(null=True, blank=True)
    crop_yield_wo = FloatField(null=True, blank=True)
    crop_yield_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_crop_yield_thread")

    area = FloatField(null=True, blank=True)

    main_soil_carbon_t2_start = FloatField(null=True, blank=True)
    main_soil_carbon_t2_w = FloatField(null=True, blank=True)
    main_soil_carbon_t2_wo = FloatField(null=True, blank=True)

    main_tillage_factor_t2_start = FloatField(null=True, blank=True)
    main_tillage_factor_t2_w = FloatField(null=True, blank=True)
    main_tillage_factor_t2_wo = FloatField(null=True, blank=True)

    main_organic_input_factor_t2_start = FloatField(null=True, blank=True)
    main_organic_input_factor_t2_w = FloatField(null=True, blank=True)
    main_organic_input_factor_t2_wo = FloatField(null=True, blank=True)

    main_biomass_factor_t2_start = FloatField(null=True, blank=True)
    main_biomass_factor_t2_w = FloatField(null=True, blank=True)
    main_biomass_factor_t2_wo = FloatField(null=True, blank=True)

    main_land_use_factor_t2_start = FloatField(null=True, blank=True)
    main_land_use_factor_t2_w = FloatField(null=True, blank=True)
    main_land_use_factor_t2_wo = FloatField(null=True, blank=True)

    minor_crop_type_start = ForeignKey(
        CropType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_minor_crop_type",
    )
    minor_crop_type_w = ForeignKey(
        CropType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_minor_crop_type_w",
    )
    minor_crop_type_wo = ForeignKey(
        CropType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_minor_crop_type_wo",
    )

    minor_yield_start = FloatField(null=True, blank=True)
    minor_yield_w = FloatField(null=True, blank=True)
    minor_yield_wo = FloatField(null=True, blank=True)

    minor_residue_management_type_start = ForeignKey(
        ResidueManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_minor_residue_management_type",
    )
    minor_residue_management_type_w = ForeignKey(
        ResidueManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_minor_residue_management_type_w",
    )
    minor_residue_management_type_wo = ForeignKey(
        ResidueManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_minor_residue_management_type_wo",
    )

    minor_biomass_factor_t2_start = FloatField(null=True, blank=True)
    minor_biomass_factor_t2_w = FloatField(null=True, blank=True)
    minor_biomass_factor_t2_wo = FloatField(null=True, blank=True)

    soc_ref_t2_start = FloatField(null=True, blank=True)
    soc_ref_t2_w = FloatField(null=True, blank=True)
    soc_ref_t2_wo = FloatField(null=True, blank=True)


class PerennialCropping(Assessment):
    user_notes = TextField(null=True, blank=True)

    crop_type_start = ForeignKey(CropType,on_delete=CASCADE,null=True,blank=True, related_name="%(class)s_crop_type_start")
    crop_type_w = ForeignKey(CropType,on_delete=CASCADE,null=True,blank=True, related_name="%(class)s_crop_type_w")
    crop_type_wo = ForeignKey(CropType,on_delete=CASCADE,null=True,blank=True, related_name="%(class)s_crop_type_wo")
    crop_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_crop_type_thread")

    tillage_management_type_start = ForeignKey(TillageManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_start")
    tillage_management_type_w = ForeignKey(TillageManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_w")
    tillage_management_type_wo = ForeignKey(TillageManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_wo")
    tillage_management_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_thread")

    organic_input_type_start = ForeignKey(OrganicInputType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_start")
    organic_input_type_w = ForeignKey(OrganicInputType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_w")
    organic_input_type_wo = ForeignKey(OrganicInputType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_wo")
    organic_input_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_thread")

    is_biomass_burned_start = BooleanField()
    is_biomass_burned_w = BooleanField()
    is_biomass_burned_wo = BooleanField()
    is_biomass_burned_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_is_biomass_burned_thread")

    area = FloatField(null=True, blank=True)

    crop_yield_start = FloatField(null=True, blank=True)
    crop_yield_w = FloatField(null=True, blank=True)
    crop_yield_wo = FloatField(null=True, blank=True)
    crop_yield_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_crop_yield_thread")

    ag_t2_start = FloatField(null=True, blank=True)
    ag_t2_w = FloatField(null=True, blank=True)
    ag_t2_wo = FloatField(null=True, blank=True)

    bg_t2_start = FloatField(null=True, blank=True)
    bg_t2_w = FloatField(null=True, blank=True)
    bg_t2_wo = FloatField(null=True, blank=True)

    soc_t2_start = FloatField(null=True, blank=True)
    soc_t2_w = FloatField(null=True, blank=True)
    soc_t2_wo = FloatField(null=True, blank=True)

    tillage_factor_t2_start = FloatField(null=True, blank=True)
    tillage_factor_t2_w = FloatField(null=True, blank=True)
    tillage_factor_t2_wo = FloatField(null=True, blank=True)

    input_factor_t2_start = FloatField(null=True, blank=True)
    input_factor_t2_w = FloatField(null=True, blank=True)
    input_factor_t2_wo = FloatField(null=True, blank=True)

    residue_burned_t2_start = FloatField(null=True, blank=True)
    residue_burned_t2_w = FloatField(null=True, blank=True)
    residue_burned_t2_wo = FloatField(null=True, blank=True)

    fire_periodicity_t2_start = FloatField(null=True, blank=True)
    fire_periodicity_t2_w = FloatField(null=True, blank=True)
    fire_periodicity_t2_wo = FloatField(null=True, blank=True)

    flu_t2_start = FloatField(null=True, blank=True)
    flu_t2_w = FloatField(null=True, blank=True)
    flu_t2_wo = FloatField(null=True, blank=True)


class FloodedRice(Assessment):
    user_notes = TextField(null=True, blank=True)

    area = FloatField(null=True, blank=True)

    cultivation_period_start = IntegerField(default=RICE_CULTIVATION_DAYS)
    cultivation_period_w = IntegerField(default=RICE_CULTIVATION_DAYS)
    cultivation_period_wo = IntegerField(default=RICE_CULTIVATION_DAYS)

    water_management_type_before_cultivation_start = ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_before_cultivation_start")
    water_management_type_before_cultivation_w = ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_before_cultivation_w")
    water_management_type_before_cultivation_wo = ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_before_cultivation_wo")

    water_management_type_after_cultivation_start = ForeignKey(WaterManagementTypeAfterCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_after_cultivation_start")
    water_management_type_after_cultivation_w = ForeignKey(WaterManagementTypeAfterCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_after_cultivation_w")
    water_management_type_after_cultivation_wo = ForeignKey(WaterManagementTypeAfterCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_after_cultivation_wo")

    organic_amendment_type_start = ForeignKey(OrganicAmendmentType, on_delete=CASCADE, related_name="%(class)s_organic_amendment_type_start")
    organic_amendment_type_w = ForeignKey(OrganicAmendmentType, on_delete=CASCADE, related_name="%(class)s_organic_amendment_type_w")
    organic_amendment_type_wo = ForeignKey(OrganicAmendmentType, on_delete=CASCADE, related_name="%(class)s_organic_amendment_type_wo")

    crop_yield_start = FloatField()
    crop_yield_w = FloatField()
    crop_yield_wo = FloatField()

    main_biomass_factor_t2_start = FloatField(null=True, blank=True)
    main_biomass_factor_t2_w = FloatField(null=True, blank=True)
    main_biomass_factor_t2_wo = FloatField(null=True, blank=True)

    soc_t2_start = FloatField(null=True, blank=True)
    soc_t2_w = FloatField(null=True, blank=True)
    soc_t2_wo = FloatField(null=True, blank=True)

    land_use_factor_t2_start = FloatField(null=True, blank=True)
    land_use_factor_t2_w = FloatField(null=True, blank=True)
    land_use_factor_t2_wo = FloatField(null=True, blank=True)

    efc_t2_start = FloatField(null=True, blank=True)
    efc_t2_w = FloatField(null=True, blank=True)
    efc_t2_wo = FloatField(null=True, blank=True)

    sfw_t2_start = FloatField(null=True, blank=True)
    sfw_t2_w = FloatField(null=True, blank=True)
    sfw_t2_wo = FloatField(null=True, blank=True)

    sfp_t2_start = FloatField(null=True, blank=True)
    sfp_t2_w = FloatField(null=True, blank=True)
    sfp_t2_wo = FloatField(null=True, blank=True)

    sfp_t2_start = FloatField(null=True, blank=True)
    sfp_t2_w = FloatField(null=True, blank=True)
    sfp_t2_wo = FloatField(null=True, blank=True)

    sfo_t2_start = FloatField(null=True, blank=True)
    sfo_t2_w = FloatField(null=True, blank=True)
    sfo_t2_wo = FloatField(null=True, blank=True)

    efi_t2_start = FloatField(null=True, blank=True)
    efi_t2_w = FloatField(null=True, blank=True)
    efi_t2_wo = FloatField(null=True, blank=True)

    rice_straw_t2_start = FloatField(null=True, blank=True)
    rice_straw_t2_w = FloatField(null=True, blank=True)
    rice_straw_t2_wo = FloatField(null=True, blank=True)


##### Grassland and Livestock #####


class Grassland(Assessment):
    description = TextField(null=True, blank=True)
    user_notes = TextField(null=True, blank=True)

    grassland_management_type_start = ForeignKey(GrasslandManagementType,on_delete=CASCADE,related_name="%(class)s_management_type_start",null=True)
    grassland_management_type_w = ForeignKey(GrasslandManagementType,on_delete=CASCADE,related_name="%(class)s_management_type_w",null=True)
    grassland_management_type_wo = ForeignKey(GrasslandManagementType,on_delete=CASCADE,related_name="%(class)s_management_type_wo",null=True)

    is_fire_used_start = BooleanField(default=False)
    is_fire_used_w = BooleanField(default=False)
    is_fire_used_wo = BooleanField(default=False)
    is_fire_used_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_is_fire_used_thread")

    fire_periodicity_start = FloatField(null=True, blank=True)
    fire_periodicity_w = FloatField(null=True, blank=True)
    fire_periodicity_wo = FloatField(null=True, blank=True)
    fire_periodicity_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_fire_periodicity_thread")

    fire_impact_start = FloatField(null=True, blank=True)
    fire_impact_w = FloatField(null=True, blank=True)
    fire_impact_wo = FloatField(null=True, blank=True)
    fire_impact_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_fire_impact_thread")

    yield_start = FloatField(null=True, blank=True)
    yield_w = FloatField(null=True, blank=True)
    yield_wo = FloatField(null=True, blank=True)
    yield_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_yield_thread")

    area = FloatField(null=True, blank=True)

    soil_carbon_t2_start = FloatField(null=True, blank=True)
    soil_carbon_t2_w = FloatField(null=True, blank=True)
    soil_carbon_t2_wo = FloatField(null=True, blank=True)

    agb_t2_start = FloatField(null=True, blank=True)
    agb_t2_w = FloatField(null=True, blank=True)
    agb_t2_wo = FloatField(null=True, blank=True)

    combustion_factor_t2_start = FloatField(null=True, blank=True)
    combustion_factor_t2_w = FloatField(null=True, blank=True)
    combustion_factor_t2_wo = FloatField(null=True, blank=True)

class Livestock(Module):
    description = TextField(null=True, blank=True)
    user_notes = TextField(null=True, blank=True)

    livestock_category_type_start = ForeignKey(LivestockCategoryType, on_delete=CASCADE)
    livestock_category_type_w = ForeignKey(
        LivestockCategoryType,
        on_delete=CASCADE,
        related_name="%(class)s_livestock_categories_w",
        null=True,
        blank=True,
    )
    livestock_category_type_wo = ForeignKey(
        LivestockCategoryType,
        on_delete=CASCADE,
        related_name="%(class)s_livestock_categories_wo",
        null=True,
        blank=True,
    )
    livestock_category_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_livestock_categories_thread", on_delete=SET_NULL)

    livestock_production_type_start = ForeignKey(LivestockProductionType, on_delete=CASCADE)
    livestock_production_type_w = ForeignKey(LivestockProductionType,on_delete=CASCADE,related_name="%(class)s_livestock_productions_w",null=True,blank=True)
    livestock_production_type_wo = ForeignKey(LivestockProductionType,on_delete=CASCADE,related_name="%(class)s_livestock_productions_wo",null=True,blank=True)
    livestock_production_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_livestock_production_type_thread", on_delete=SET_NULL)

    production_start = FloatField(null=True, blank=True)
    production_w = FloatField(null=True, blank=True)
    production_wo = FloatField(null=True, blank=True)
    production_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_production_thread", on_delete=SET_NULL)

    heads_number_start = IntegerField(null=True, blank=True)
    heads_number_w = IntegerField(null=True, blank=True)
    heads_number_wo = IntegerField(null=True, blank=True)
    heads_number_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_heads_number_thread", on_delete=SET_NULL)

    enteric_fermentation_start_t2 = FloatField(null=True, blank=True)
    enteric_fermentation_w_t2 = FloatField(null=True, blank=True)
    enteric_fermentation_wo_t2 = FloatField(null=True, blank=True)

    prp_percentage_start_t2 = FloatField(null=True, blank=True)
    prp_percentage_w_t2 = FloatField(null=True, blank=True)
    prp_percentage_wo_t2 = FloatField(null=True, blank=True)

    prp_ch4_start_t2 = FloatField(null=True, blank=True)
    prp_ch4_w_t2 = FloatField(null=True, blank=True)
    prp_ch4_wo_t2 = FloatField(null=True, blank=True)

    prp_n2o_start_t2 = FloatField(null=True, blank=True)
    prp_n2o_w_t2 = FloatField(null=True, blank=True)
    prp_n2o_wo_t2 = FloatField(null=True, blank=True)

    manure_management_type_t2_start = ForeignKey(
        ManureManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_manure_management_type_t2_start",
    )
    emission_factor_ch4_t2_start = FloatField(null=True, blank=True)
    emission_factor_n2o_t2_start = FloatField(null=True, blank=True)

    manure_management_type_t2_w = ForeignKey(
        ManureManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_manure_management_type_t2_w",
    )
    emission_factor_ch4_t2_w = FloatField(null=True, blank=True)
    emission_factor_n2o_t2_w = FloatField(null=True, blank=True)

    manure_management_type_t2_wo = ForeignKey(
        ManureManagementType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_manure_management_type_t2_wo",
    )
    emission_factor_ch4_t2_wo = FloatField(null=True, blank=True)
    emission_factor_n2o_t2_wo = FloatField(null=True, blank=True)

    implementation_year_start = IntegerField(null=True, blank=True)


##### Forest Management #####


class ForestManagement(Assessment):
    forest_type = ForeignKey(ForestType, on_delete=CASCADE)
    forest_condition_type = ForeignKey(ForestConditionType, on_delete=CASCADE, related_name="%(class)s_forest_condition_type")

    rotation_occurrence_start = FloatField(null=True, blank=True)
    rotation_occurrence_w = FloatField(null=True, blank=True)
    rotation_occurrence_wo = FloatField(null=True, blank=True)
    rotation_occurrence_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_rotation_occurrence_thread")

    is_rotation_used_for_energy_start = BooleanField(default=False)
    is_rotation_used_for_energy_w = BooleanField(default=False)
    is_rotation_used_for_energy_wo = BooleanField(default=False)
    is_rotation_used_for_energy_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_is_used_for_energy_thread")

    logging_start = FloatField(null=True, blank=True)
    logging_w = FloatField(null=True, blank=True)
    logging_wo = FloatField(null=True, blank=True)
    logging_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_logging_thread")

    is_logging_used_for_energy_start = BooleanField(default=False)
    is_logging_used_for_energy_w = BooleanField(default=False)
    is_logging_used_for_energy_wo = BooleanField(default=False)
    is_logging_used_for_energy_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_is_logging_used_for_energy_thread")

    soil_carbon_t2_start = FloatField(null=True, blank=True)
    soil_carbon_t2_w = FloatField(null=True, blank=True)
    soil_carbon_t2_wo = FloatField(null=True, blank=True)

    land_use_factor_t2_start = FloatField(null=True, blank=True)
    land_use_factor_t2_w = FloatField(null=True, blank=True)
    land_use_factor_t2_wo = FloatField(null=True, blank=True)

    agb_t2_start = FloatField(null=True, blank=True)
    agb_t2_w = FloatField(null=True, blank=True)
    agb_t2_wo = FloatField(null=True, blank=True)

    bgb_t2_start = FloatField(null=True, blank=True)
    bgb_t2_w = FloatField(null=True, blank=True)
    bgb_t2_wo = FloatField(null=True, blank=True)

    agb_growth_rate_gt_20_yrs_t2_start = FloatField(null=True, blank=True)
    agb_growth_rate_gt_20_yrs_t2_w = FloatField(null=True, blank=True)
    agb_growth_rate_gt_20_yrs_t2_wo = FloatField(null=True, blank=True)

    agb_growth_rate_le_20_yrs_t2_start = FloatField(null=True, blank=True)
    agb_growth_rate_le_20_yrs_t2_w = FloatField(null=True, blank=True)
    agb_growth_rate_le_20_yrs_t2_wo = FloatField(null=True, blank=True)

    bgb_growth_rate_gt_20_yrs_t2_start = FloatField(null=True, blank=True)
    bgb_growth_rate_gt_20_yrs_t2_w = FloatField(null=True, blank=True)
    bgb_growth_rate_gt_20_yrs_t2_wo = FloatField(null=True, blank=True)

    bgb_growth_rate_le_20_yrs_t2_start = FloatField(null=True, blank=True)
    bgb_growth_rate_le_20_yrs_t2_w = FloatField(null=True, blank=True)
    bgb_growth_rate_le_20_yrs_t2_wo = FloatField(null=True, blank=True)

    litter_t2_start = FloatField(null=True, blank=True)
    litter_t2_w = FloatField(null=True, blank=True)
    litter_t2_wo = FloatField(null=True, blank=True)

    deadwood_t2_start = FloatField(null=True, blank=True)
    deadwood_t2_w = FloatField(null=True, blank=True)
    deadwood_t2_wo = FloatField(null=True, blank=True)

##### Inland Wetlands #####

class InlandWaterbody(Module):
    waterbody_type = ForeignKey(WaterbodyType, on_delete=CASCADE)

    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(
        ChangeRate,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_ha_w_rate",
    )
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(
        ChangeRate,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_ha_wo_rate",
    )

    trophic_type = ForeignKey(TrophicType, on_delete=CASCADE, null=True, blank=True)

    ch4_emissions_start_t2 = FloatField(null=True, blank=True)
    ch4_emissions_w_t2 = FloatField(null=True, blank=True)
    ch4_emissions_wo_t2 = FloatField(null=True, blank=True)

    trophic_alpha_t2 = FloatField(null=True, blank=True)
    trophic_mean_annual_t2 = FloatField(null=True, blank=True)


##### Coastal Wetlands #####

class Extraction(Module):
    # TODO: Remove class
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    ha_start = IntegerField(null=True, blank=True)
    ha_w_excavated_percentage = FloatField(null=True, blank=True)
    ha_wo_excavated_percentage = FloatField(null=True, blank=True)

    extraction_ag_t2 = FloatField(null=True, blank=True)
    extraction_bg_t2 = FloatField(null=True, blank=True)
    extraction_litter_t2 = FloatField(null=True, blank=True)
    extraction_deadwood_t2 = FloatField(null=True, blank=True)
    extraction_soil_type_t2 = ForeignKey(
        SoilType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_extracted_soil_type_t2",
    )
    extraction_soil_t2 = FloatField(null=True, blank=True)
    c_after_excavation_t2 = FloatField(null=True, blank=True, default=0.96)

    # TODO: Drainage as separate module? (probably not, since it's only used here)
    drainage_percentage_start = FloatField(null=True, blank=True)
    drainage_percentage_w = FloatField(null=True, blank=True)
    drainage_percentage_w_rate = ForeignKey(
        ChangeRate,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_drainage_percentage_w_rate",
    )
    drainage_percentage_wo = FloatField(null=True, blank=True)
    drainage_percentage_wo_rate = ForeignKey(
        ChangeRate,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_drainage_percentage_wo_rate",
    )

    drainage_ag_t2 = FloatField(null=True, blank=True)
    drainage_bg_t2 = FloatField(null=True, blank=True)
    drainage_litter_t2 = FloatField(null=True, blank=True)
    drainage_deadwood_t2 = FloatField(null=True, blank=True)
    drainage_soil_type_t2 = ForeignKey(
        SoilType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_drained_soil_type_t2",
    )
    drainage_soil_t2 = FloatField(null=True, blank=True)

    ef_drainage_t2 = FloatField(null=True, blank=True)


class Rewetting(Module):
    # TODO: Remove class
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(
        ChangeRate,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_ha_w_rate",
    )
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(
        ChangeRate,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_ha_wo_rate",
    )

    restored_biomass_percentage_w = FloatField(null=True, blank=True)
    restored_biomass_percentage_wo = FloatField(null=True, blank=True)

    ag_t2 = FloatField(null=True, blank=True)
    bg_t2 = FloatField(null=True, blank=True)
    litter_t2 = FloatField(null=True, blank=True)
    deadwood_t2 = FloatField(null=True, blank=True)
    avg_salinity_t2 = ForeignKey(
        SalinityType,
        on_delete=CASCADE,
        null=True,
        blank=True,
    )
    ef_co2_t2 = FloatField(null=True, blank=True)
    ef_ch4_t2 = FloatField(null=True, blank=True)


class CoastalWaterbody(Module):
    # TODO: Remove class

    waterbody_type = ForeignKey(WaterbodyType, on_delete=CASCADE)
    trophic_type = ForeignKey(TrophicType, on_delete=CASCADE, null=True, blank=True)

    # NOTE: Total area must remain constant
    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_w_rate = ForeignKey(
        ChangeRate,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_ha_w_rate",
    )
    ha_wo = FloatField(null=True, blank=True)
    ha_wo_rate = ForeignKey(
        ChangeRate,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_ha_wo_rate",
    )

    ch4_start_t2 = FloatField(null=True, blank=True)
    ch4_w_t2 = FloatField(null=True, blank=True)
    ch4_wo_t2 = FloatField(null=True, blank=True)

    trophic_alpha_t2 = FloatField(null=True, blank=True)
    trophic_mean_annual_t2 = FloatField(null=True, blank=True)

class Waterbody(Module):
    waterbody_type = ForeignKey(WaterbodyType, on_delete=CASCADE)
    area = FloatField(null=True, blank=True)
    trophic_type_start = ForeignKey(TrophicType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_trophic_class_start")
    trophic_type_w = ForeignKey(TrophicType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_trophic_class_w")
    trophic_type_wo = ForeignKey(TrophicType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_trophic_class_wo")

    ch4_ef_t2_start = FloatField(null=True, blank=True)
    ch4_ef_t2_w = FloatField(null=True, blank=True)
    ch4_ef_t2_wo = FloatField(null=True, blank=True)

    alpha_t2_start = FloatField(null=True, blank=True)
    alpha_t2_w = FloatField(null=True, blank=True)
    alpha_t2_wo = FloatField(null=True, blank=True)

    mean_annual_t2_start = FloatField(null=True, blank=True)
    mean_annual_t2_w = FloatField(null=True, blank=True)
    mean_annual_t2_wo = FloatField(null=True, blank=True)

class CoastalWetland(Module):
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)

    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_wo = FloatField(null=True, blank=True)
    ha_thread = ForeignKey(CommentThread, null=True, blank=True, on_delete=SET_NULL, related_name="%(class)s_ha_thread")

    area_under_drainage_start = FloatField(null=True, blank=True)
    area_under_drainage_w = FloatField(null=True, blank=True)
    area_under_drainage_wo = FloatField(null=True, blank=True)
    area_under_drainage_thread = ForeignKey(CommentThread, null=True, blank=True, on_delete=SET_NULL, related_name="%(class)s_area_under_drainage_thread")

    drained_area_excavated_start = FloatField(null=True, blank=True)
    drained_area_excavated_w = FloatField(null=True, blank=True)
    drained_area_excavated_wo = FloatField(null=True, blank=True)
    drained_area_excavated_thread = ForeignKey(CommentThread, null=True, blank=True, on_delete=SET_NULL, related_name="%(class)s_drained_area_excavated_thread")

    area_not_drained_or_rewetted_start = FloatField(null=True, blank=True)
    area_not_drained_or_rewetted_w = FloatField(null=True, blank=True)
    area_not_drained_or_rewetted_wo = FloatField(null=True, blank=True)
    area_not_drained_or_rewetted_thread = ForeignKey(CommentThread, null=True, blank=True, on_delete=SET_NULL, related_name="%(class)s_area_not_drained_or_rewetted_thread")

    area_w_restored_vegetation_start = FloatField(null=True, blank=True)
    area_w_restored_vegetation_w = FloatField(null=True, blank=True)
    area_w_restored_vegetation_wo = FloatField(null=True, blank=True)
    area_w_restored_vegetation_thread = ForeignKey(CommentThread, null=True, blank=True, on_delete=SET_NULL, related_name="%(class)s_area_w_restored_vegetation_thread")

    soil_type_t2 = ForeignKey(SoilType, null=True, blank=True, on_delete=SET_NULL)

    soc_t2_start = FloatField(null=True, blank=True)
    soc_t2_w = FloatField(null=True, blank=True)
    soc_t2_wo = FloatField(null=True, blank=True)

    pc_c_lost_after_excavation_t2_start = FloatField(null=True, blank=True)
    pc_c_lost_after_excavation_t2_w = FloatField(null=True, blank=True)
    pc_c_lost_after_excavation_t2_wo = FloatField(null=True, blank=True)

    agb_t2_start = FloatField(null=True, blank=True)
    agb_t2_w = FloatField(null=True, blank=True)
    agb_t2_wo = FloatField(null=True, blank=True)

    bgb_t2_start = FloatField(null=True, blank=True)
    bgb_t2_w = FloatField(null=True, blank=True)
    bgb_t2_wo = FloatField(null=True, blank=True)

    litter_t2_start = FloatField(null=True, blank=True)
    litter_t2_w = FloatField(null=True, blank=True)
    litter_t2_wo = FloatField(null=True, blank=True)

    deadwood_t2_start = FloatField(null=True, blank=True)
    deadwood_t2_w = FloatField(null=True, blank=True)
    deadwood_t2_wo = FloatField(null=True, blank=True)

    drainage_ef_t2_start = FloatField(null=True, blank=True)
    drainage_ef_t2_w = FloatField(null=True, blank=True)
    drainage_ef_t2_wo = FloatField(null=True, blank=True)

    co2_rewetting_t2_start = FloatField(null=True, blank=True)
    co2_rewetting_t2_w = FloatField(null=True, blank=True)
    co2_rewetting_t2_wo = FloatField(null=True, blank=True)

    ch4_rewetting_t2_start = FloatField(null=True, blank=True)
    ch4_rewetting_t2_w = FloatField(null=True, blank=True)
    ch4_rewetting_t2_wo = FloatField(null=True, blank=True)

    avg_salinity_t2 = ForeignKey(SalinityType, null=True, blank=True, on_delete=SET_NULL)

##### Fisheries and Aquaculture #####

class Fishery(Module):
    class Meta:
        abstract = True

    refrigerant_pc_start = FloatField(validators=[pc_as_float], default=0)
    refrigerant_pc_w = FloatField(validators=[pc_as_float], default=0)
    refrigerant_pc_wo = FloatField(validators=[pc_as_float], default=0)
    refrigerant_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_refrigerant_thread", on_delete=SET_NULL)

    refrigerant_gwp = FloatField(null=True, blank=True, default=1810)

    fui_start = FloatField(null=True, blank=True)
    fui_w = FloatField(null=True, blank=True)
    fui_wo = FloatField(null=True, blank=True)

    total_catch_yr_start = FloatField(null=True, blank=True)
    total_catch_yr_w = FloatField(null=True, blank=True)
    total_catch_yr_wo = FloatField(null=True, blank=True)
    total_catch_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_total_catch_thread", on_delete=SET_NULL)

    ice_preserved_catch_pc_start = FloatField(default=0, validators=[pc_as_float])
    ice_preserved_catch_pc_w = FloatField(default=0, validators=[pc_as_float])
    ice_preserved_catch_pc_wo = FloatField(default=0, validators=[pc_as_float])
    ice_preserved_catch_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_ice_preserved_catch_thread", on_delete=SET_NULL)

    # TODO: Is the non-t2 value static for this specific module? It's always related to Gasoil/Diesel
    energy_emission_factor_t2_start = FloatField(null=True, blank=True)
    energy_emission_factor_t2_w = FloatField(null=True, blank=True)
    energy_emission_factor_t2_wo = FloatField(null=True, blank=True)

    refrigerant_lost_per_tonne_t2_start = FloatField(null=True, blank=True)
    refrigerant_lost_per_tonne_t2_w = FloatField(null=True, blank=True)
    refrigerant_lost_per_tonne_t2_wo = FloatField(null=True, blank=True)

    refrigerant_gwp_t2_start = FloatField(null=True, blank=True)
    refrigerant_gwp_t2_w = FloatField(null=True, blank=True)
    refrigerant_gwp_t2_wo = FloatField(null=True, blank=True)

    tonnes_of_ice_t2_start = FloatField(null=True, blank=True)
    tonnes_of_ice_t2_w = FloatField(null=True, blank=True)
    tonnes_of_ice_t2_wo = FloatField(null=True, blank=True)

    # TODO: This part has some internal logic that has to be examined more deeply
    # NOTE: The logic does not seem to make much sense. It's just to display some values and can probably be ignored altogether
    inshore_ice_production_kwh_per_tonne_t2_start = FloatField(null=True, blank=True)
    inshore_ice_production_kwh_per_tonne_t2_w = FloatField(null=True, blank=True)
    inshore_ice_production_kwh_per_tonne_t2_wo = FloatField(null=True, blank=True)
    
    inshore_ice_production_country_t2 = ForeignKey(Country, on_delete=CASCADE, null=True, blank=True)

    implementation_year_t2 = IntegerField(null=True, blank=True)

class SmallFishery(Fishery):
    gear_type_start = ForeignKey(
        SmallFisheryGearType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_gear_type_start",
    )
    gear_type_w = ForeignKey(
        SmallFisheryGearType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_gear_type_w",
    )
    gear_type_wo = ForeignKey(
        SmallFisheryGearType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_gear_type_wo",
    )
    gear_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_gear_type_thread", on_delete=SET_NULL)
    fishery_type = ForeignKey(FisheryType, on_delete=CASCADE, null=True, blank=True)
    fui_default = ForeignKey("ipcc.SmallFisheryFUI", on_delete=CASCADE, null=True, blank=True)

class LargeFishery(Fishery):
    gear_type_start = ForeignKey(
        LargeFisheryGearType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_gear_type_start",
    )
    gear_type_w = ForeignKey(
        LargeFisheryGearType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_gear_type_w",
    )
    gear_type_wo = ForeignKey(
        LargeFisheryGearType,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_gear_type_wo",
    )
    gear_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_gear_type_thread", on_delete=SET_NULL)
    fish_type = ForeignKey(FishType, on_delete=CASCADE)
    fui_default = ForeignKey(
        "ipcc.LargeFisheryFUI", on_delete=CASCADE, null=True, blank=True
    )

class Aquaculture(Module):
    user_notes = TextField(null=True, blank=True)

    annual_production_start = FloatField(null=True, blank=True)
    annual_production_w = FloatField(null=True, blank=True)
    annual_production_wo = FloatField(null=True, blank=True)

    n2o_from_production_t2_start = FloatField(null=True, blank=True)
    n2o_from_production_t2_w = FloatField(null=True, blank=True)
    n2o_from_production_t2_wo = FloatField(null=True, blank=True)
    
    electricity_used_t2_start = FloatField(null=True, blank=True)
    electricity_used_t2_w = FloatField(null=True, blank=True)
    electricity_used_t2_wo = FloatField(null=True, blank=True)

class MacroInputType(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class InputType(Model):
    macro_input_type = ForeignKey(
        MacroInputType, on_delete=CASCADE, null=True, blank=True
    )
    name = CharField(max_length=255, unique=True)
    description = TextField(null=True, blank=True)

    class Meta:
        unique_together = ("macro_input_type", "name")

    def __str__(self):
        return f"({self.id}) {self.name}"


class Input(Module):
    input_type = ForeignKey(InputType, on_delete=CASCADE, null=True, blank=True)
    value_start = FloatField(null=True, blank=True)
    value_w = FloatField(null=True, blank=True)
    value_w_rate = ForeignKey(
        ChangeRate,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_value_w_rate",
    )
    value_wo = FloatField(null=True, blank=True)
    value_wo_rate = ForeignKey(
        ChangeRate,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_value_wo_rate",
    )

    co2_emissions_t2 = FloatField(null=True, blank=True)
    n2o_emissions_t2 = FloatField(null=True, blank=True)
    co2_e_emissions_t2 = FloatField(null=True, blank=True)

    implementation_year_t2 = IntegerField(null=True, blank=True)

class EmissionFactorSource(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"

class Electricity(Module):
    country = ForeignKey(Country, on_delete=CASCADE, null=True, blank=True)
    mwh_start = FloatField(null=True, blank=True)
    mwh_w = FloatField(null=True, blank=True)
    mwh_wo = FloatField(null=True, blank=True)

    mwh_renewables_start = FloatField(null=True, blank=True)
    mwh_renewables_w = FloatField(null=True, blank=True)
    mwh_renewables_wo = FloatField(null=True, blank=True)

    ef_t2 = FloatField(null=True, blank=True)
    transmission_loss = FloatField(default=0.1)
    ef_source = ForeignKey(
        EmissionFactorSource, on_delete=CASCADE, null=True, blank=True
    )

class Fuel(Module):
    fuel_type = ForeignKey(FuelType, on_delete=CASCADE, null=True, blank=True)
    fuel_start = FloatField(null=True, blank=True)
    fuel_w = FloatField(null=True, blank=True)
    fuel_wo = FloatField(null=True, blank=True)

    ef_t2 = FloatField(null=True, blank=True)
    account_for_co2 = BooleanField(default=False)


class IrrigationSystemType(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class EnergySourceType(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class IrrigationSystem(Module):
    irrigation_system_type = ForeignKey(IrrigationSystemType, on_delete=CASCADE, null=True, blank=True)
    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_wo = FloatField(null=True, blank=True)

    ef_t2_start = FloatField(null=True, blank=True)
    ef_t2_w = FloatField(null=True, blank=True)
    ef_t2_wo = FloatField(null=True, blank=True)


class IrrigationPhase(Module):
    irrigation_system_type = ForeignKey(IrrigationSystemType, on_delete=CASCADE, null=True, blank=True)
    fuel_type = ForeignKey(FuelType, on_delete=CASCADE, null=True, blank=True)
    well_depth = FloatField(null=True, blank=True)
    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_wo = FloatField(null=True, blank=True)

    gross_irrigation_water_start = FloatField(null=True, blank=True)
    gross_irrigation_water_w = FloatField(null=True, blank=True)
    gross_irrigation_water_wo = FloatField(null=True, blank=True)

    power_origin_country_t2 = ForeignKey(Country, on_delete=CASCADE, null=True, blank=True)
    ef_t2_start = FloatField(null=True, blank=True)
    ef_t2_w = FloatField(null=True, blank=True)
    ef_t2_wo = FloatField(null=True, blank=True)

    transmission_loss_t2_start = FloatField(null=True, blank=True)
    transmission_loss_t2_w = FloatField(null=True, blank=True)
    transmission_loss_t2_wo = FloatField(null=True, blank=True)

    average_pressure_t2 = FloatField(null=True, blank=True)

    total_dynamic_head_t2 = FloatField(null=True, blank=True)

    pumping_efficiency_t2_start = FloatField(null=True, blank=True)
    pumping_efficiency_t2_w = FloatField(null=True, blank=True)
    pumping_efficiency_t2_wo = FloatField(null=True, blank=True)


class BuildingType(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"
    
class RoadType(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"
class Building(Module):
    settlement = ForeignKey("api.Settlement", on_delete=CASCADE, null=True, blank=True, related_name="buildings")

    building_type_start = ForeignKey(BuildingType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_building_type_start")
    building_type_w = ForeignKey(BuildingType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_building_type_w")
    building_type_wo = ForeignKey(BuildingType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_building_type_wo")
    
    area_m2_start = FloatField(null=True, blank=True)
    area_m2_w = FloatField(null=True, blank=True)
    area_m2_wo = FloatField(null=True, blank=True)
    area_m2_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_surface_thread", on_delete=SET_NULL)

    ef_t2_start = FloatField(null=True, blank=True)
    ef_t2_w = FloatField(null=True, blank=True)
    ef_t2_wo = FloatField(null=True, blank=True)

class Road(Module):
    settlement = ForeignKey("api.Settlement", on_delete=CASCADE, null=True, blank=True, related_name="roads")

    road_type_start = ForeignKey(RoadType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_road_type_start")
    road_type_w = ForeignKey(RoadType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_road_type_w")
    road_type_wo = ForeignKey(RoadType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_road_type_wo")

    length_km_start = FloatField(null=True, blank=True)
    length_km_w = FloatField(null=True, blank=True)
    length_km_wo = FloatField(null=True, blank=True)
    length_km_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_length_km_thread", on_delete=SET_NULL)

    width_m_start = FloatField(null=True, blank=True)
    width_m_w = FloatField(null=True, blank=True)
    width_m_wo = FloatField(null=True, blank=True)
    width_m_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_width_m_thread", on_delete=SET_NULL)

    ef_t2_start = FloatField(null=True, blank=True)
    ef_t2_w = FloatField(null=True, blank=True)
    ef_t2_wo = FloatField(null=True, blank=True)

class OtherInfrastructure(Module):
    settlement = ForeignKey("api.Settlement", on_delete=CASCADE, null=True, blank=True, related_name="other_infrastructure")

    area_m2_start = FloatField(null=True, blank=True)
    area_m2_w = FloatField(null=True, blank=True)
    area_m2_wo = FloatField(null=True, blank=True)
    area_m2_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_area_m2_thread", on_delete=SET_NULL)

    ef_t2_start = FloatField(null=True, blank=True)
    ef_t2_w = FloatField(null=True, blank=True)
    ef_t2_wo = FloatField(null=True, blank=True)

class OrganicSoil(Assessment):

    drainage_area_start = FloatField(null=True, blank=True)
    drainage_area_w = FloatField(null=True, blank=True)
    drainage_area_wo = FloatField(null=True, blank=True)
    drainage_area_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_drainage_area_thread", on_delete=SET_NULL)

    area_not_drained_start = FloatField(null=True, blank=True)
    area_not_drained_w = FloatField(null=True, blank=True)
    area_not_drained_wo = FloatField(null=True, blank=True)
    area_not_drained_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_area_not_drained_thread", on_delete=SET_NULL)

    ditches_area_start = FloatField(null=True, blank=True)
    ditches_area_w = FloatField(null=True, blank=True)
    ditches_area_wo = FloatField(null=True, blank=True)
    ditches_area_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_ditches_area_thread", on_delete=SET_NULL)

    # TODO: Change to fire_type
    fire_type_start = ForeignKey(FireType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_fire_type_start")
    fire_type_w = ForeignKey(FireType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_fire_type_w")
    fire_type_wo = ForeignKey(FireType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_fire_type_wo")
    fire_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_fire_type_thread", on_delete=SET_NULL)

    soil_fire_periodicity_start = FloatField(null=True, blank=True)
    soil_fire_periodicity_w = FloatField(null=True, blank=True)
    soil_fire_periodicity_wo = FloatField(null=True, blank=True)
    soil_fire_periodicity_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_soil_fire_periodicity_thread", on_delete=SET_NULL)

    soil_fire_impact_percentage_start = FloatField(null=True, blank=True)
    soil_fire_impact_percentage_w = FloatField(null=True, blank=True)
    soil_fire_impact_percentage_wo = FloatField(null=True, blank=True)
    soil_fire_impact_percentage_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_soil_fire_impact_percentage_thread", on_delete=SET_NULL)

    onsite_co2_drainge_t2_start = FloatField(null=True, blank=True)
    onsite_co2_drainge_t2_w = FloatField(null=True, blank=True)
    onsite_co2_drainge_t2_wo = FloatField(null=True, blank=True)

    onsite_ch4_drainge_t2_start = FloatField(null=True, blank=True)
    onsite_ch4_drainge_t2_w = FloatField(null=True, blank=True)
    onsite_ch4_drainge_t2_wo = FloatField(null=True, blank=True)

    onsite_n2o_drainge_t2_start = FloatField(null=True, blank=True)
    onsite_n2o_drainge_t2_w = FloatField(null=True, blank=True)
    onsite_n2o_drainge_t2_wo = FloatField(null=True, blank=True)

    offsite_doc_drainge_t2_start = FloatField(null=True, blank=True)
    offsite_doc_drainge_t2_w = FloatField(null=True, blank=True)
    offsite_doc_drainge_t2_wo = FloatField(null=True, blank=True)

    offsite_ch4_drainge_t2_start = FloatField(null=True, blank=True)
    offsite_ch4_drainge_t2_w = FloatField(null=True, blank=True)
    offsite_ch4_drainge_t2_wo = FloatField(null=True, blank=True)

    onsite_co2_rewetting_t2_start = FloatField(null=True, blank=True)
    onsite_co2_rewetting_t2_w = FloatField(null=True, blank=True)
    onsite_co2_rewetting_t2_wo = FloatField(null=True, blank=True)

    onsite_ch4_rewetting_t2_start = FloatField(null=True, blank=True)
    onsite_ch4_rewetting_t2_w = FloatField(null=True, blank=True)
    onsite_ch4_rewetting_t2_wo = FloatField(null=True, blank=True)

    onsite_n2o_rewetting_t2_start = FloatField(null=True, blank=True)
    onsite_n2o_rewetting_t2_w = FloatField(null=True, blank=True)
    onsite_n2o_rewetting_t2_wo = FloatField(null=True, blank=True)

    offsite_doc_rewetting_t2_start = FloatField(null=True, blank=True)
    offsite_doc_rewetting_t2_w = FloatField(null=True, blank=True)
    offsite_doc_rewetting_t2_wo = FloatField(null=True, blank=True)

    mean_dry_matter_t2_start = FloatField(null=True, blank=True)
    mean_dry_matter_t2_w = FloatField(null=True, blank=True)
    mean_dry_matter_t2_wo = FloatField(null=True, blank=True)

    fire_on_soil_co2_t2_start = FloatField(null=True, blank=True)
    fire_on_soil_co2_t2_w = FloatField(null=True, blank=True)
    fire_on_soil_co2_t2_wo = FloatField(null=True, blank=True)

    fire_on_soil_co_t2_start = FloatField(null=True, blank=True)
    fire_on_soil_co_t2_w = FloatField(null=True, blank=True)
    fire_on_soil_co_t2_wo = FloatField(null=True, blank=True)

    fire_on_soil_ch4_t2_start = FloatField(null=True, blank=True)
    fire_on_soil_ch4_t2_w = FloatField(null=True, blank=True)
    fire_on_soil_ch4_t2_wo = FloatField(null=True, blank=True)

    ##### Peat Extraction #####

    # TODO: Remove this field
    has_peat_extraction = BooleanField(default=False)

    peat_type_start = ForeignKey(PeatType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_peat_type_start")
    peat_type_w = ForeignKey(PeatType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_peat_type_w")
    peat_type_wo = ForeignKey(PeatType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_peat_type_wo")
    peat_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_type_thread", on_delete=SET_NULL)

    peat_area_start = FloatField(null=True, blank=True)
    peat_area_w = FloatField(null=True, blank=True)
    peat_area_wo = FloatField(null=True, blank=True)
    peat_area_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_area_thread", on_delete=SET_NULL)

    peat_ditches_area_start = FloatField(null=True, blank=True)
    peat_ditches_area_w = FloatField(null=True, blank=True)
    peat_ditches_area_wo = FloatField(null=True, blank=True)
    peat_ditches_area_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_ditches_area_thread", on_delete=SET_NULL)

    peat_extraction_height_start = FloatField(null=True, blank=True)
    peat_extraction_height_w = FloatField(null=True, blank=True)
    peat_extraction_height_wo = FloatField(null=True, blank=True)
    peat_extraction_height_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_extraction_height_thread", on_delete=SET_NULL)

    is_peat_for_energy_start = BooleanField(default=False)
    is_peat_is_for_energy_w = BooleanField(default=False)
    is_peat_is_for_energy_wo = BooleanField(default=False)
    is_peat_is_for_energy_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_is_for_energy_thread", on_delete=SET_NULL)

    onsite_co2_peat_t2 = FloatField(null=True, blank=True)
    onsite_ch4_peat_t2 = FloatField(null=True, blank=True)
    onsite_n2o_peat_t2 = FloatField(null=True, blank=True)
    offsite_doc_peat_t2 = FloatField(null=True, blank=True)
    offsite_ch4_peat_t2 = FloatField(null=True, blank=True)

    peat_density_t2 = FloatField(null=True, blank=True)

class Settlement(Assessment):
    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_wo = FloatField(null=True, blank=True)
    ha_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_ha_thread", on_delete=SET_NULL)

    is_settlement_start = BooleanField(default=False)
    is_settlement_w = BooleanField(default=False)
    is_settlement_wo = BooleanField(default=False)

    soil_carbon_t2_start = FloatField(null=True, blank=True)
    soil_carbon_t2_w = FloatField(null=True, blank=True)
    soil_carbon_t2_wo = FloatField(null=True, blank=True)

    flu_t2_start = FloatField(null=True, blank=True)
    flu_t2_w = FloatField(null=True, blank=True)
    flu_t2_wo = FloatField(null=True, blank=True)

    agb_t2_start = FloatField(null=True, blank=True)
    agb_t2_w = FloatField(null=True, blank=True)
    agb_t2_wo = FloatField(null=True, blank=True)

    bgb_t2_start = FloatField(null=True, blank=True)
    bgb_t2_w = FloatField(null=True, blank=True)
    bgb_t2_wo = FloatField(null=True, blank=True)

class SetAside(Module):
    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_wo = FloatField(null=True, blank=True)
    ha_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_ha_thread", on_delete=SET_NULL)

    is_set_aside_start = BooleanField(default=False)
    is_set_aside_w = BooleanField(default=False)
    is_set_aside_wo = BooleanField(default=False)

    soc_t2_start = FloatField(null=True, blank=True)
    soc_t2_w = FloatField(null=True, blank=True)
    soc_t2_wo = FloatField(null=True, blank=True)

    flu_t2_start = FloatField(null=True, blank=True)
    flu_t2_w = FloatField(null=True, blank=True)
    flu_t2_wo = FloatField(null=True, blank=True)

    agb_t2_start = FloatField(null=True, blank=True)
    agb_t2_w = FloatField(null=True, blank=True)
    agb_t2_wo = FloatField(null=True, blank=True)

    bgb_t2_start = FloatField(null=True, blank=True)
    bgb_t2_w = FloatField(null=True, blank=True)
    bgb_t2_wo = FloatField(null=True, blank=True)

class DegradedLand(Module):
    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_wo = FloatField(null=True, blank=True)

    is_degraded_land_start = BooleanField(default=False)
    is_degraded_land_w = BooleanField(default=False)
    is_degraded_land_wo = BooleanField(default=False)

    soc_t2_start = FloatField(null=True, blank=True)
    soc_t2_w = FloatField(null=True, blank=True)
    soc_t2_wo = FloatField(null=True, blank=True)

    flu_t2_start = FloatField(null=True, blank=True)
    flu_t2_w = FloatField(null=True, blank=True)
    flu_t2_wo = FloatField(null=True, blank=True)

    agb_t2_start = FloatField(null=True, blank=True)
    agb_t2_w = FloatField(null=True, blank=True)
    agb_t2_wo = FloatField(null=True, blank=True)

    bgb_t2_start = FloatField(null=True, blank=True)
    bgb_t2_w = FloatField(null=True, blank=True)
    bgb_t2_wo = FloatField(null=True, blank=True)

class LandUseChange(Module):

    land_use_type_start = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="luc_start")
    land_use_type_end = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="luc_end")

    module_type_start = ForeignKey(ModuleType, on_delete=CASCADE, null=True, blank=True, related_name="start")
    module_type_end = ForeignKey(ModuleType, on_delete=CASCADE, null=True, blank=True, related_name="end")
    area = FloatField(null=True, blank=True)

    is_fire_used_start = BooleanField(default=False)
    is_fire_used_end = BooleanField(default=False)

    dry_matter_start = FloatField(null=True, blank=True)
    dry_matter_end = FloatField(null=True, blank=True)
    
### MODEL PARAMETERS TABLES ###

class Parameter(Model):
    class Meta:
        abstract = True

    name = CharField(max_length=255, unique=True)
    value = FloatField(null=True, blank=True)
    unit = CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.name} = {self.value} {self.unit if self.unit else ''}"
    
class LivestockParameter(Parameter):
    pass

class IrrigationParameter(Parameter):
    pass

class SmallFisheryParameter(Parameter):
    pass

class LargeFisheryParameter(Parameter):
    pass

class AquacultureParameter(Parameter):
    pass

class GrasslandParameter(Parameter):
    pass

class AnnualCroplandParameter(Parameter):
    pass

class CoastalWetlandParameter(Parameter):
    pass