import uuid
from abc import ABC, abstractmethod

from django.contrib.auth import models as auth_models
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db.models import *
from django.utils import timezone
from simple_history.models import HistoricalRecords

from .utilities import *

alphanumeric = RegexValidator(r"^[0-9a-zA-Z]*$", "Only alphanumeric characters are allowed.")
letters_only = RegexValidator(r"^[a-zA-Z]*$", "Only letters are allowed.")
capitalized = RegexValidator(r"[A-Z][a-z]*(\s[A-Z][a-z]*)*", "Only capitalized words are allowed.")
pc_as_float = RegexValidator(r"^[0-1]*\.?[0-9]*$", "Only correctly formatted percentages are allowed.")

RICE_CULTIVATION_DAYS = 113


# Create your models here.
class CustomUser(auth_models.AbstractUser):
    country = ForeignKey("api.Country", on_delete=CASCADE, null=True, blank=True, related_name="users")
    email = EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        permissions = (
            ("can_view_modules", "Can view modules"),
            ("can_add_modules", "Can add modules"),
            ("can_change_modules", "Can change modules"),
            ("can_delete_modules", "Can delete modules"),
        )

    def __str__(self):
        return f"{self.username}"


class Group(auth_models.Group):
    class Meta:
        proxy = True

    def __str__(self) -> str:
        return f"({self.pk}) {self.name}"


##############################
############# MISC ###########
##############################


class ConfigParam(Model):
    name = CharField(max_length=255)
    value = TextField()

    def __str__(self):
        return f"({self.pk}) {self.name}"

    def get_parsed_value(self):
        if self.value.lower() == "true":
            return True
        elif self.value.lower() == "false":
            return False
        try:
            return int(self.value)
        except ValueError:
            try:
                return float(self.value)
            except ValueError:
                return self.value

    class Meta:
        verbose_name_plural = "Config parameters"


class CommentThread(Model):
    def __str__(self):
        return f"({self.pk})"


class Comment(Model):
    thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="comments")
    parent = ForeignKey("self", null=True, blank=True, on_delete=CASCADE, related_name="replies")
    date_created = DateTimeField(auto_now_add=True)
    author = ForeignKey(CustomUser, on_delete=CASCADE)

    content = TextField()
    # We can add other fields like 'is_active', 'likes', etc.

    def __str__(self):
        return f"({self.pk}) {self.author.username}: {self.content[:40]}..."


class IPCCRegion(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class GasType(Model):
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


class StatusType(Model):
    name = CharField(max_length=255, unique=True)
    value = FloatField(null=True, blank=True, unique=True)

    class Meta:
        verbose_name_plural = "Status types"
        unique_together = ("name", "value")

    def __str__(self):
        return f"({self.id}) {self.name}"


class LandUseType(Model):
    name = CharField(max_length=100)
    module_types = ManyToManyField("api.ModuleType", related_name="land_use_types")
    forest_type = ForeignKey("api.ForestType", on_delete=CASCADE, null=True, blank=True)
    climates = ManyToManyField("api.Climate", related_name="land_use_types")
    moistures = ManyToManyField("api.Moisture", related_name="land_use_types")
    is_active = BooleanField(default=True)

    def __str__(self):
        module_types = ", ".join([str(x.name) for x in self.module_types.all()])
        return f"({self.pk}) {self.name} - Active: {self.is_active}" + (f" ({module_types})" if module_types else "")


class ChangeRate(Model):
    name = CharField(max_length=25)
    value = FloatField(unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ProjectStatus(Model):
    name = CharField(max_length=25)
    value = IntegerField(unique=True)

    class Meta:
        verbose_name_plural = "Project statuses"

    def __str__(self):
        return self.name


class Region(Model):
    name = CharField(max_length=100, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class Country(Model):
    name = CharField(max_length=100, unique=True)
    region = ForeignKey(Region, on_delete=CASCADE, null=True, blank=True, related_name="countries")
    ipcc_region = ForeignKey(IPCCRegion, on_delete=CASCADE, null=True, blank=True, related_name="countries")
    gleam_region = ForeignKey(GLEAMRegion, on_delete=CASCADE, null=True, blank=True, related_name="countries")

    class Meta:
        verbose_name_plural = "Countries"

    def __str__(self):
        return f"({self.pk}) {self.name}"


class Climate(Model):
    name = CharField(max_length=100)
    moistures = ManyToManyField("api.Moisture", related_name="climates")

    def __str__(self):
        return f"({self.pk}) {self.name}"


class Moisture(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class SoilType(Model):
    name = CharField(max_length=100)
    active = BooleanField(default=True)

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
    is_active = BooleanField(default=True)

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
        return f"({self.pk}) {self.name}"


class LivestockCategoryType(Model):
    name = CharField(max_length=100)
    is_active = BooleanField(default=True)

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
    class_name = CharField(max_length=255, null=True, blank=True)
    is_luc = BooleanField(default=False)
    is_submodule = BooleanField(default=False)
    is_fixed_assessment = BooleanField(default=False)

    def __str__(self):
        return f"({self.pk}) {self.name}" + (" (LUC)" if self.is_luc else "")

    class Meta:
        verbose_name_plural = "Module types"


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
    macro_fuel_type = ForeignKey(MacroFuelType, on_delete=CASCADE, null=True, blank=True)

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
    class Meta:
        verbose_name_plural = "Projects"
        unique_together = ("name", "user")

    user = ForeignKey(CustomUser, on_delete=CASCADE, related_name="projects")
    date = DateTimeField(null=True, blank=True)
    name = CharField(max_length=100)
    code = CharField(max_length=100, null=True, blank=True)
    cost = FloatField(null=True, blank=True)
    funding_agency = CharField(max_length=100, null=True, blank=True)
    executing_agency = CharField(max_length=100, null=True, blank=True)
    status = ForeignKey(ProjectStatus, on_delete=CASCADE, null=True, blank=True)

    implementation_years = IntegerField()
    capitalization_years = IntegerField()
    start_year = IntegerField(null=True, blank=True)

    country = ForeignKey(Country, on_delete=CASCADE)
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    soil_type = ForeignKey(SoilType, on_delete=CASCADE)

    is_locked = BooleanField(default=False)
    locked_at = DateTimeField(null=True, blank=True)
    lock_updated_at = DateTimeField(null=True, blank=True)
    locked_by = ForeignKey(CustomUser, on_delete=CASCADE, null=True, blank=True, related_name="locked_projects")

    gw_potential = ForeignKey("ipcc.GlobalWarmingPotential", on_delete=CASCADE)

    soc_ref_t2 = FloatField(null=True, blank=True)

    created_at = DateTimeField(auto_now_add=True, null=True)
    updated_at = DateTimeField(auto_now=True, null=True)

    def save(self, *args, **kwargs):
        if self.pk:
            old = Project.objects.get(pk=self.pk)
            if old.user != self.user:
                raise ValidationError("User cannot be changed")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"({self.pk}) {self.name}"

    def lock(self, user: CustomUser):
        self.is_locked = True
        self.locked_at = timezone.now()
        self.locked_by = user
        self.save()

    def unlock(self):
        self.is_locked = False
        self.locked_at = None
        self.locked_by = None
        self.save()

    def refresh_lock(self):
        self.lock_updated_at = timezone.now()
        self.save()


class ProjectInvitation(Historical):
    STATUS_CHOICES = (("sent", "Sent"), ("accepted", "Accepted"), ("declined", "Declined"))

    project = ForeignKey(Project, on_delete=CASCADE, related_name="invitations")
    user = ForeignKey(CustomUser, on_delete=CASCADE, related_name="invitations")
    group = ForeignKey(Group, on_delete=CASCADE)
    status = CharField(max_length=20, choices=STATUS_CHOICES, default="sent")

    created_at = DateTimeField(auto_now_add=True, null=True)
    updated_at = DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = (("project", "user"),)

    def __str__(self):
        return f"({self.pk}) {self.project.name} - {self.user.email}"


class UserProjectGroup(Model):
    user = ForeignKey(CustomUser, on_delete=CASCADE, related_name="memberships")
    project = ForeignKey(Project, on_delete=CASCADE, related_name="members")
    group = ForeignKey(Group, on_delete=CASCADE)

    def __str__(self):
        return f"({self.pk}) {self.project.name} - {self.user.username} - {self.group.name}"


##############################
######### Activity ###########
##############################


class Activity(Historical):
    project = ForeignKey(Project, on_delete=CASCADE, related_name="activities")
    name = CharField(max_length=255)
    description = TextField(null=True, blank=True)
    # user = ForeignKey(CustomUser, on_delete=CASCADE) # TODO: Define when it's useful to have this
    status = ForeignKey(StatusType, on_delete=CASCADE, null=True, blank=True)
    cost = FloatField(default=0)

    change_rate = ForeignKey(ChangeRate, on_delete=CASCADE, related_name="activities", null=True, blank=True)
    module_types = ManyToManyField("api.ModuleType", related_name="activities")

    climate_t2 = ForeignKey(Climate, on_delete=CASCADE, null=True, blank=True)
    moisture_t2 = ForeignKey(Moisture, on_delete=CASCADE, null=True, blank=True)
    soil_type_t2 = ForeignKey(SoilType, on_delete=CASCADE, null=True, blank=True)
    duration_t2 = IntegerField(default=0)
    start_year_t2 = IntegerField(null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.name} in {self.project.name}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.state = StatusType.objects.get_or_create(name="EMPTY")[0]
            if not self.change_rate:
                self.change_rate = ChangeRate.objects.get_or_create(name="D")[0]
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("name", "project")


##############################
########## Modules ###########
##############################


class Submodule(Historical):
    # module_type = ForeignKey("api.ModuleType", on_delete=CASCADE, related_name="%(class)s")
    status = ForeignKey(StatusType, on_delete=CASCADE, null=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.parent:
            raise ValidationError("Submodule must have a parent field specified in the model")

        if not self.status:
            self.status = StatusType.objects.get_or_create(name="EMPTY")[0]

        super().save(*args, **kwargs)


class Module(Historical):
    class Meta:
        abstract = True

    activity = ForeignKey(Activity, on_delete=CASCADE, related_name="%(class)s")
    notes = TextField(null=True, blank=True)
    start_year = IntegerField(default=1)

    soc_t2_start = FloatField(null=True, blank=True)
    soc_t2_w = FloatField(null=True, blank=True)
    soc_t2_wo = FloatField(null=True, blank=True)

    status = ForeignKey(StatusType, on_delete=CASCADE, null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self._meta.object_name} in {self.activity.name}"

    def save(self, *args, **kwargs):
        if not self.status:
            self.status = StatusType.objects.get_or_create(name="EMPTY")[0]

        super().save(*args, **kwargs)


class BiomassModule(Module):
    class Meta:
        abstract = True

    @abstractmethod
    def get_biomass_t2(self, scenario: ScenarioTypes):
        try:
            return getattr(self, f"soc_t2_{scenario.value}")
        except TypeError:
            return None


class SingleBiomassModule(BiomassModule):
    biomass_t2_start = FloatField(null=True, blank=True)
    biomass_t2_w = FloatField(null=True, blank=True)
    biomass_t2_wo = FloatField(null=True, blank=True)

    class Meta:
        abstract = True

    def get_biomass_t2(self, scenario: ScenarioTypes):
        try:
            return super().get_biomass_t2(scenario) + getattr(self, f"biomass_t2_{scenario.value}")
        except TypeError:
            return None


class DoubleBiomassModule(BiomassModule):
    agb_t2_start = FloatField(null=True, blank=True)
    agb_t2_w = FloatField(null=True, blank=True)
    agb_t2_wo = FloatField(null=True, blank=True)

    bgb_t2_start = FloatField(null=True, blank=True)
    bgb_t2_w = FloatField(null=True, blank=True)
    bgb_t2_wo = FloatField(null=True, blank=True)

    class Meta:
        abstract = True

    def get_biomass_t2(self, scenario: ScenarioTypes):
        try:
            return super().get_biomass_t2(scenario) + getattr(self, f"agb_t2_{scenario.value}") + getattr(self, f"bgb_t2_{scenario.value}")
        except TypeError:
            return None


class MultiBiomassModule(DoubleBiomassModule):
    litter_t2_start = FloatField(null=True, blank=True)
    litter_t2_w = FloatField(null=True, blank=True)
    litter_t2_wo = FloatField(null=True, blank=True)

    deadwood_t2_start = FloatField(null=True, blank=True)
    deadwood_t2_w = FloatField(null=True, blank=True)
    deadwood_t2_wo = FloatField(null=True, blank=True)

    class Meta:
        abstract = True

    def get_biomass_t2(self, scenario: ScenarioTypes):
        try:
            return super().get_biomass_t2(scenario) + getattr(self, f"litter_t2_{scenario.value}") + getattr(self, f"deadwood_t2_{scenario.value}")
        except TypeError:
            return None


##### Land Use Changes #####


class OtherLandUse(Module):
    initial_land_use_type = ForeignKey(LandUseType, null=True, blank=True, on_delete=CASCADE, related_name="initial_land_use_type")
    final_land_use_type = ForeignKey(LandUseType, null=True, blank=True, on_delete=CASCADE, related_name="final_land_use_type")

    is_fire_used = BooleanField(default=False)

    ha_w = FloatField()
    ha_wo = FloatField()

    initial_biomass_t2 = FloatField(null=True, blank=True)
    initial_soil_carbon_t2 = FloatField(null=True, blank=True)

    final_biomass_t2 = FloatField(null=True, blank=True)
    final_soil_carbon_t2 = FloatField(null=True, blank=True)

    implementation_year_start = IntegerField(null=True, blank=True)


class LandModule(Module):
    land_use_change = OneToOneField("api.LandUseChange", on_delete=CASCADE, null=True, blank=True, related_name="%(class)s")

    area = FloatField(null=True, blank=True)

    land_use_type_start = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_start")
    land_use_type_w = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_w")
    land_use_type_wo = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_wo")
    land_use_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_thread")

    flu_t2_start = FloatField(null=True, blank=True)
    flu_t2_w = FloatField(null=True, blank=True)
    flu_t2_wo = FloatField(null=True, blank=True)

    fi_t2_start = FloatField(null=True, blank=True)
    fi_t2_w = FloatField(null=True, blank=True)
    fi_t2_wo = FloatField(null=True, blank=True)

    fmg_t2_start = FloatField(null=True, blank=True)
    fmg_t2_w = FloatField(null=True, blank=True)
    fmg_t2_wo = FloatField(null=True, blank=True)

    class Meta:
        abstract = True


class LandSubmodule(Submodule):
    land_use_change = OneToOneField("api.LandUseChange", on_delete=CASCADE, null=True, blank=True, related_name="%(class)s")

    area = FloatField(null=True, blank=True)

    land_use_type_start = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_start")
    land_use_type_w = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_w")
    land_use_type_wo = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_wo")
    land_use_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_thread")

    flu_t2_start = FloatField(null=True, blank=True)
    flu_t2_w = FloatField(null=True, blank=True)
    flu_t2_wo = FloatField(null=True, blank=True)

    fi_t2_start = FloatField(null=True, blank=True)
    fi_t2_w = FloatField(null=True, blank=True)
    fi_t2_wo = FloatField(null=True, blank=True)

    fmg_t2_start = FloatField(null=True, blank=True)
    fmg_t2_w = FloatField(null=True, blank=True)
    fmg_t2_wo = FloatField(null=True, blank=True)

    class Meta:
        abstract = True


class LandModuleNoScenarios(Module):
    land_use_change = OneToOneField("api.LandUseChange", on_delete=CASCADE, null=True, blank=True, related_name="%(class)s")

    land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_start")
    land_use_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_thread")

    class Meta:
        abstract = True


class LandModuleFixed(LandModule):
    # TODO: Rework
    # def save(self, *args, **kwargs):
    #     if not self.land_use_type_start:

    #         mt = ModuleType.objects.get(class_name=self.__class__.__name__)

    #         self.land_use_type_start = LandUseType.objects.get(name=mt.name)
    #         self.land_use_type_w = self.land_use_type_start
    #         self.land_use_type_wo = self.land_use_type_start

    #     super().save(*args, **kwargs)

    class Meta:
        abstract = True


class CropType(Model):
    name = CharField(max_length=255, unique=True)
    description = TextField(null=True, blank=True)
    is_main_crop = BooleanField(default=False)
    is_agrofoforestry = BooleanField(default=False)

    def __str__(self) -> str:
        return f"({self.pk}) {self.name}"


class AnnualCropping(LandModule, SingleBiomassModule):
    tillage_management_type_start = ForeignKey(
        TillageManagementType,
        on_delete=CASCADE,
        related_name="%(class)s_tillage_management_type_start",
        null=True,
        blank=True,
    )
    tillage_management_type_w = ForeignKey(TillageManagementType, on_delete=CASCADE, related_name="%(class)s_tillage_management_type_w", null=True, blank=True)
    tillage_management_type_wo = ForeignKey(TillageManagementType, on_delete=CASCADE, related_name="%(class)s_tillage_management_type_wo", null=True, blank=True)
    tillage_management_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_thread")

    organic_input_type_start = ForeignKey(OrganicInputType, on_delete=CASCADE, related_name="%(class)s_organic_input_type_start", null=True, blank=True)
    organic_input_type_w = ForeignKey(OrganicInputType, on_delete=CASCADE, related_name="%(class)s_organic_input_type_w", null=True, blank=True)
    organic_input_type_wo = ForeignKey(OrganicInputType, on_delete=CASCADE, related_name="%(class)s_organic_input_type_wo", null=True, blank=True)
    organic_input_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_thread")

    residue_management_type_start = ForeignKey(ResidueManagementType, on_delete=CASCADE, related_name="%(class)s_residue_management_type_start", null=True, blank=True)
    residue_management_type_w = ForeignKey(ResidueManagementType, on_delete=CASCADE, related_name="%(class)s_residue_management_type_w", null=True, blank=True)
    residue_management_type_wo = ForeignKey(ResidueManagementType, on_delete=CASCADE, related_name="%(class)s_residue_management_type_wo", null=True, blank=True)
    residue_management_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_thread")

    crop_yield_start = FloatField(default=0)
    crop_yield_w = FloatField(default=0)
    crop_yield_wo = FloatField(default=0)
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

    minor_land_use_type_start = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_minor_land_use_type_start")
    minor_land_use_type_w = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_minor_land_use_type_w")
    minor_land_use_type_wo = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_minor_land_use_type_wo")

    minor_yield_start = FloatField(null=True, blank=True)
    minor_yield_w = FloatField(null=True, blank=True)
    minor_yield_wo = FloatField(null=True, blank=True)

    minor_residue_management_type_start = ForeignKey(ResidueManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_minor_residue_management_type")
    minor_residue_management_type_w = ForeignKey(ResidueManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_minor_residue_management_type_w")
    minor_residue_management_type_wo = ForeignKey(ResidueManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_minor_residue_management_type_wo")

    minor_biomass_factor_t2_start = FloatField(null=True, blank=True)
    minor_biomass_factor_t2_w = FloatField(null=True, blank=True)
    minor_biomass_factor_t2_wo = FloatField(null=True, blank=True)

    soc_ref_t2_start = FloatField(null=True, blank=True)
    soc_ref_t2_w = FloatField(null=True, blank=True)
    soc_ref_t2_wo = FloatField(null=True, blank=True)


class PerennialCrop(Model):
    class Meta:
        abstract = True

    tillage_management_type_start = ForeignKey(TillageManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_start")
    tillage_management_type_w = ForeignKey(TillageManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_w")
    tillage_management_type_wo = ForeignKey(TillageManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_wo")
    tillage_management_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_thread")

    organic_input_type_start = ForeignKey(OrganicInputType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_start")
    organic_input_type_w = ForeignKey(OrganicInputType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_w")
    organic_input_type_wo = ForeignKey(OrganicInputType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_wo")
    organic_input_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_thread")

    is_biomass_burned_start = BooleanField(null=True, blank=True)
    is_biomass_burned_w = BooleanField(null=True, blank=True)
    is_biomass_burned_wo = BooleanField(null=True, blank=True)
    is_biomass_burned_thread = ForeignKey(
        CommentThread,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_is_biomass_burned_thread",
    )

    area = FloatField(null=True, blank=True)

    crop_yield_start = FloatField(null=True, blank=True)
    crop_yield_w = FloatField(null=True, blank=True)
    crop_yield_wo = FloatField(null=True, blank=True)
    crop_yield_thread = ForeignKey(
        CommentThread,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_crop_yield_thread",
    )

    ag_t2_start = FloatField(null=True, blank=True)
    ag_t2_w = FloatField(null=True, blank=True)
    ag_t2_wo = FloatField(null=True, blank=True)

    agb_max_t2_start = FloatField(null=True, blank=True)
    agb_max_t2_w = FloatField(null=True, blank=True)
    agb_max_t2_wo = FloatField(null=True, blank=True)

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

    # def save(self, *args, **kwargs):
    #     if not self.land_use_type_start:
    #         self.land_use_type_start = LandUseType.objects.get(name="Agroforestry - Default")
    #         self.land_use_type_w = self.land_use_type_start
    #         self.land_use_type_wo = self.land_use_type_start

    #     super().save(*args, **kwargs)


class PerennialCropping(PerennialCrop, LandModule, DoubleBiomassModule):
    pass


class CroplandMinorSeason(Model):
    class Meta:
        abstract = True

    land_use_type_start = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_start")
    land_use_type_w = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_w")
    land_use_type_wo = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_wo")

    residue_management_type_start = ForeignKey(ResidueManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_start")
    residue_management_type_w = ForeignKey(ResidueManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_w")
    residue_management_type_wo = ForeignKey(ResidueManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_wo")

    yield_start = FloatField(null=True, blank=True)
    yield_w = FloatField(null=True, blank=True)
    yield_wo = FloatField(null=True, blank=True)

    biomass_factor_t2_start = FloatField(null=True, blank=True)
    biomass_factor_t2_w = FloatField(null=True, blank=True)
    biomass_factor_t2_wo = FloatField(null=True, blank=True)


class MinorSeasonPerennialCropping(CroplandMinorSeason, LandSubmodule):
    parent = ForeignKey(PerennialCropping, on_delete=CASCADE, related_name="minor_seasons", null=True, blank=True)


class MinorSeasonAnnualCropping(CroplandMinorSeason, LandSubmodule):
    parent = ForeignKey(AnnualCropping, on_delete=CASCADE, related_name="minor_seasons", null=True, blank=True)


class Rice(Model):
    class Meta:
        abstract = True

    cultivation_period_start = IntegerField(default=RICE_CULTIVATION_DAYS)
    cultivation_period_w = IntegerField(default=RICE_CULTIVATION_DAYS)
    cultivation_period_wo = IntegerField(default=RICE_CULTIVATION_DAYS)

    water_management_type_before_cultivation_start = ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_before_cultivation_start", null=True)
    water_management_type_before_cultivation_w = ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_before_cultivation_w", null=True)
    water_management_type_before_cultivation_wo = ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_before_cultivation_wo", null=True)

    water_management_type_after_cultivation_start = ForeignKey(WaterManagementTypeAfterCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_after_cultivation_start", null=True)
    water_management_type_after_cultivation_w = ForeignKey(WaterManagementTypeAfterCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_after_cultivation_w", null=True)
    water_management_type_after_cultivation_wo = ForeignKey(WaterManagementTypeAfterCultivation, on_delete=CASCADE, related_name="%(class)s_water_management_type_after_cultivation_wo", null=True)

    organic_amendment_type_start = ForeignKey(OrganicAmendmentType, on_delete=CASCADE, related_name="%(class)s_organic_amendment_type_start", null=True)
    organic_amendment_type_w = ForeignKey(OrganicAmendmentType, on_delete=CASCADE, related_name="%(class)s_organic_amendment_type_w", null=True)
    organic_amendment_type_wo = ForeignKey(OrganicAmendmentType, on_delete=CASCADE, related_name="%(class)s_organic_amendment_type_wo", null=True)

    crop_yield_start = FloatField(null=True, blank=True)
    crop_yield_w = FloatField(null=True, blank=True)
    crop_yield_wo = FloatField(null=True, blank=True)

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

    def save(self, *args, **kwargs):
        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name="Flooded Rice")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        super().save(*args, **kwargs)


class FloodedRice(Rice, LandModuleFixed, SingleBiomassModule):
    pass


class MinorSeasonFloodedRice(Rice, LandSubmodule):
    parent = ForeignKey(FloodedRice, on_delete=CASCADE, related_name="minor_seasons", null=True, blank=True)


##### Grassland and Livestock #####


class Grassland(LandModuleFixed, SingleBiomassModule):
    grassland_management_type_start = ForeignKey(GrasslandManagementType, on_delete=CASCADE, related_name="%(class)s_grassland_management_type_start", null=True)
    grassland_management_type_w = ForeignKey(GrasslandManagementType, on_delete=CASCADE, related_name="%(class)s_grassland_management_type_w", null=True)
    grassland_management_type_wo = ForeignKey(GrasslandManagementType, on_delete=CASCADE, related_name="%(class)s_grassland_management_type_wo", null=True)

    is_fire_used_start = BooleanField(default=False)
    is_fire_used_w = BooleanField(default=False)
    is_fire_used_wo = BooleanField(default=False)
    is_fire_used_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_is_fire_used_thread")

    fire_periodicity_start = FloatField(null=True, blank=True, default=0)
    fire_periodicity_w = FloatField(null=True, blank=True, default=0)
    fire_periodicity_wo = FloatField(null=True, blank=True, default=0)
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

    combustion_factor_t2_start = FloatField(null=True, blank=True)
    combustion_factor_t2_w = FloatField(null=True, blank=True)
    combustion_factor_t2_wo = FloatField(null=True, blank=True)

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     if self.is_fire_used_start:
    #         self._meta.get_field("fire_periodicity_start").null = False
    #         self._meta.get_field("fire_impact_start").null = False
    #     if self.is_fire_used_w:
    #         self._meta.get_field("fire_periodicity_w").null = False
    #         self._meta.get_field("fire_impact_w").null = False
    #     if self.is_fire_used_wo:
    #         self._meta.get_field("fire_periodicity_wo").null = False
    #         self._meta.get_field("fire_impact_wo").null = False

    def save(self, *args, **kwargs):
        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name="Grassland")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        super().save(*args, **kwargs)


class Livestock(Module):
    livestock_category_type = ForeignKey(LivestockCategoryType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_livestock_category_type")
    livestock_category_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_livestock_categories_thread", on_delete=SET_NULL)

    livestock_production_type_start = ForeignKey(LivestockProductionType, on_delete=CASCADE, null=True, blank=True)
    livestock_production_type_w = ForeignKey(LivestockProductionType, on_delete=CASCADE, related_name="%(class)s_livestock_productions_w", null=True, blank=True)
    livestock_production_type_wo = ForeignKey(LivestockProductionType, on_delete=CASCADE, related_name="%(class)s_livestock_productions_wo", null=True, blank=True)
    livestock_production_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_livestock_production_type_thread", on_delete=SET_NULL)

    production_start = FloatField(null=True, blank=True)
    production_w = FloatField(null=True, blank=True)
    production_wo = FloatField(null=True, blank=True)
    production_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_production_thread", on_delete=SET_NULL)

    heads_number_start = IntegerField(null=True, blank=True)
    heads_number_w = IntegerField(null=True, blank=True)
    heads_number_wo = IntegerField(null=True, blank=True)
    heads_number_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_heads_number_thread", on_delete=SET_NULL)

    complementary_manure_management_type_start = ForeignKey(ManureManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_manure_management_type_t2_start")
    complementary_manure_management_type_w = ForeignKey(ManureManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_manure_management_type_t2_w")
    complementary_manure_management_type_wo = ForeignKey(ManureManagementType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_manure_management_type_t2_wo")
    complementary_manure_management_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_complementary_manure_management_type_thread", on_delete=SET_NULL)

    percentage_heads_on_pasture_start = FloatField(null=True, blank=True)
    percentage_heads_on_pasture_w = FloatField(null=True, blank=True)
    percentage_heads_on_pasture_wo = FloatField(null=True, blank=True)
    percentage_heads_on_pasture_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_percentage_heads_on_pasture_thread", on_delete=SET_NULL)

    enteric_fermentation_t2_start = FloatField(null=True, blank=True)
    enteric_fermentation_t2_w = FloatField(null=True, blank=True)
    enteric_fermentation_t2_wo = FloatField(null=True, blank=True)

    prp_percentage_t2_start = FloatField(null=True, blank=True)
    prp_percentage_t2_w = FloatField(null=True, blank=True)
    prp_percentage_t2_wo = FloatField(null=True, blank=True)

    prp_ch4_t2_start = FloatField(null=True, blank=True)
    prp_ch4_t2_w = FloatField(null=True, blank=True)
    prp_ch4_t2_wo = FloatField(null=True, blank=True)

    prp_n2o_t2_start = FloatField(null=True, blank=True)
    prp_n2o_t2_w = FloatField(null=True, blank=True)
    prp_n2o_t2_wo = FloatField(null=True, blank=True)

    emission_factor_ch4_t2_start = FloatField(null=True, blank=True)
    emission_factor_n2o_t2_start = FloatField(null=True, blank=True)

    emission_factor_ch4_t2_w = FloatField(null=True, blank=True)
    emission_factor_n2o_t2_w = FloatField(null=True, blank=True)

    emission_factor_ch4_t2_wo = FloatField(null=True, blank=True)
    emission_factor_n2o_t2_wo = FloatField(null=True, blank=True)

    implementation_year_start = IntegerField(null=True, blank=True)


##### Forest Management #####


class ForestManagement(LandModule, MultiBiomassModule):
    forest_type = ForeignKey(ForestType, on_delete=CASCADE, null=True, blank=True)
    forest_condition_type = ForeignKey(ForestConditionType, on_delete=CASCADE, null=True, blank=True)

    ##### ROTATION #####

    rotation_length_yrs_start = IntegerField(null=True, blank=True)
    rotation_length_yrs_w = IntegerField(null=True, blank=True)
    rotation_length_yrs_wo = IntegerField(null=True, blank=True)
    rotation_length_yrs_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_rotation_length_yrs_thread")

    rotation_percentage_biomass_for_energy_start = FloatField(null=True, blank=True, default=0)
    rotation_percentage_biomass_for_energy_w = FloatField(null=True, blank=True, default=0)
    rotation_percentage_biomass_for_energy_wo = FloatField(null=True, blank=True, default=0)
    rotation_percentage_biomass_for_energy_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_rotation_percentage_biomass_for_energy_thread")

    ##### LOGGING #####

    logging_recurrence_yrs_start = IntegerField(null=True, blank=True)
    logging_recurrence_yrs_w = IntegerField(null=True, blank=True)
    logging_recurrence_yrs_wo = IntegerField(null=True, blank=True)
    logging_recurrence_yrs_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_logging_recurrence_yrs_thread")

    logging_percentage_agb_logged_start = FloatField(null=True, blank=True, default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    logging_percentage_agb_logged_w = FloatField(null=True, blank=True, default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    logging_percentage_agb_logged_wo = FloatField(null=True, blank=True, default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    logging_percentage_agb_logged_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_logging_percentage_agb_logged_thread")

    logging_percentage_biomass_for_energy_start = FloatField(null=True, blank=True, default=0)
    logging_percentage_biomass_for_energy_w = FloatField(null=True, blank=True, default=0)
    logging_percentage_biomass_for_energy_wo = FloatField(null=True, blank=True, default=0)
    logging_percentage_biomass_for_energy_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_logging_percentage_biomass_for_energy_thread")

    ##### DEGRADATION #####

    average_yearly_degradation_percentage_start = FloatField(null=True, blank=True, default=0)
    average_yearly_degradation_percentage_w = FloatField(null=True, blank=True, default=0)
    average_yearly_degradation_percentage_wo = FloatField(null=True, blank=True, default=0)
    average_yearly_degradation_percentage_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_average_yearly_degradation_percentage_thread")

    ##### TIER 2 #####

    agb_growth_rate_le_20_yrs_t2_start = FloatField(null=True, blank=True)
    agb_growth_rate_le_20_yrs_t2_w = FloatField(null=True, blank=True)
    agb_growth_rate_le_20_yrs_t2_wo = FloatField(null=True, blank=True)

    agb_growth_rate_gt_20_yrs_t2_start = FloatField(null=True, blank=True)
    agb_growth_rate_gt_20_yrs_t2_w = FloatField(null=True, blank=True)
    agb_growth_rate_gt_20_yrs_t2_wo = FloatField(null=True, blank=True)

    bgb_growth_rate_le_20_yrs_t2_start = FloatField(null=True, blank=True)
    bgb_growth_rate_le_20_yrs_t2_w = FloatField(null=True, blank=True)
    bgb_growth_rate_le_20_yrs_t2_wo = FloatField(null=True, blank=True)

    bgb_growth_rate_gt_20_yrs_t2_start = FloatField(null=True, blank=True)
    bgb_growth_rate_gt_20_yrs_t2_w = FloatField(null=True, blank=True)
    bgb_growth_rate_gt_20_yrs_t2_wo = FloatField(null=True, blank=True)

    rotation_start_year_t2_start = IntegerField(default=0)
    rotation_start_year_t2_w = IntegerField(default=0)
    rotation_start_year_t2_wo = IntegerField(default=0)

    logging_start_year_t2_start = IntegerField(default=0)
    logging_start_year_t2_w = IntegerField(default=0)
    logging_start_year_t2_wo = IntegerField(default=0)

    logging_dry_matter_logged_t2_start = FloatField(null=True, blank=True)
    logging_dry_matter_logged_t2_w = FloatField(null=True, blank=True)
    logging_dry_matter_logged_t2_wo = FloatField(null=True, blank=True)

    degradation_dry_matter_impacted_t2_start = FloatField(null=True, blank=True)
    degradation_dry_matter_impacted_t2_w = FloatField(null=True, blank=True)
    degradation_dry_matter_impacted_t2_wo = FloatField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.land_use_type_start:
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start
        return super().save(*args, **kwargs)


class DisturbanceType(Model):
    name = CharField(max_length=255)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ForestDisturbance(Model):
    forest_management = ForeignKey(ForestManagement, on_delete=CASCADE, related_name="disturbances")

    disturbance_type = ForeignKey(DisturbanceType, on_delete=CASCADE, null=True, blank=True)
    disturbance_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_disturbance_type_thread")

    recurrence_yrs_start = IntegerField(null=True, blank=True)
    recurrence_yrs_w = IntegerField(null=True, blank=True)
    recurrence_yrs_wo = IntegerField(null=True, blank=True)
    recurrence_yrs_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_disturbance_recurrence_yrs_thread")

    percentage_biomass_destruction_start = FloatField(null=True, blank=True)
    percentage_biomass_destruction_w = FloatField(null=True, blank=True)
    percentage_biomass_destruction_wo = FloatField(null=True, blank=True)
    percentage_biomass_destruction_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_disturbance_percentage_biomass_destruction_thread")

    start_year_t2_start = IntegerField(default=1)
    start_year_t2_w = IntegerField(default=1)
    start_year_t2_wo = IntegerField(default=1)

    dry_matter_impacted_t2_start = FloatField(null=True, blank=True)
    dry_matter_impacted_t2_w = FloatField(null=True, blank=True)
    dry_matter_impacted_t2_wo = FloatField(null=True, blank=True)


class Waterbody(Module):
    waterbody_type = ForeignKey(WaterbodyType, on_delete=CASCADE, null=True, blank=True)
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
    land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, null=True, blank=True)

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
    gear_type_start = ForeignKey(SmallFisheryGearType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_start")
    gear_type_w = ForeignKey(SmallFisheryGearType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_w")
    gear_type_wo = ForeignKey(SmallFisheryGearType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_wo")
    gear_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_gear_type_thread", on_delete=SET_NULL)
    fishery_type = ForeignKey(FisheryType, on_delete=CASCADE, null=True, blank=True)
    fui_default = ForeignKey("ipcc.SmallFisheryFUI", on_delete=CASCADE, null=True, blank=True)


class LargeFishery(Fishery):
    gear_type_start = ForeignKey(LargeFisheryGearType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_start")
    gear_type_w = ForeignKey(LargeFisheryGearType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_w")
    gear_type_wo = ForeignKey(LargeFisheryGearType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_wo")
    gear_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_gear_type_thread", on_delete=SET_NULL)
    fish_type = ForeignKey(FishType, on_delete=CASCADE, null=True, blank=True)
    fui_default = ForeignKey("ipcc.LargeFisheryFUI", on_delete=CASCADE, null=True, blank=True)


class Aquaculture(Module):
    # fish_type = ForeignKey(FishType, on_delete=CASCADE, null=True, blank=True)

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
    macro_input_type = ForeignKey(MacroInputType, on_delete=CASCADE, null=True, blank=True)
    name = CharField(max_length=255, unique=True)
    description = TextField(null=True, blank=True)
    has_co2_emissions = BooleanField(default=False)
    has_n2o_emissions = BooleanField(default=False)
    has_co2_e_emissions = BooleanField(default=False)

    class Meta:
        unique_together = ("macro_input_type", "name")

    def __str__(self):
        return f"({self.id}) {self.name}"


class Input(Module):
    pass


class InputEntry(Submodule):
    parent = ForeignKey(Input, on_delete=CASCADE, related_name="input_entries")
    input_type = ForeignKey(InputType, on_delete=CASCADE)

    value_start = FloatField()
    value_w = FloatField()
    value_wo = FloatField()
    value_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_value_thread")

    co2_emissions_t2 = FloatField(null=True, blank=True)
    n2o_emissions_t2 = FloatField(null=True, blank=True)
    co2_e_emissions_t2 = FloatField(null=True, blank=True)

    implementation_year_t2 = IntegerField(null=True, blank=True)


class EmissionFactorSource(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class Energy(Module):
    pass


class Electricity(Submodule):
    parent = ForeignKey(Energy, on_delete=CASCADE, null=True, blank=True, related_name="electricities")
    country = ForeignKey(Country, on_delete=CASCADE, null=True, blank=True)

    mwh_start = FloatField(null=True, blank=True)
    mwh_w = FloatField(null=True, blank=True)
    mwh_wo = FloatField(null=True, blank=True)
    mwh_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_mwh_thread")

    mwh_renewables_start = FloatField(null=True, blank=True)
    mwh_renewables_w = FloatField(null=True, blank=True)
    mwh_renewables_wo = FloatField(null=True, blank=True)
    mwh_renewables_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_mwh_renewables_thread")

    ef_t2 = FloatField(null=True, blank=True)
    transmission_loss = FloatField(default=0.1)
    ef_source = ForeignKey(EmissionFactorSource, on_delete=CASCADE, null=True, blank=True)


class Fuel(Submodule):
    parent = ForeignKey(Energy, on_delete=CASCADE, null=True, blank=True, related_name="fuels")
    fuel_type = ForeignKey(FuelType, on_delete=CASCADE, null=True, blank=True)

    fuel_consumption_start = FloatField(null=True, blank=True)
    fuel_consumption_w = FloatField(null=True, blank=True)
    fuel_consumption_wo = FloatField(null=True, blank=True)
    fuel_consumption_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_fuel_consumption_thread")

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


class Irrigation(Module):
    pass


class IrrigationSystem(Submodule):
    parent = ForeignKey(Irrigation, on_delete=CASCADE, null=True, blank=True, related_name="irrigation_systems")
    irrigation_system_type = ForeignKey(IrrigationSystemType, on_delete=CASCADE, null=True, blank=True, related_name="irrigation_systems")

    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_wo = FloatField(null=True, blank=True)
    ha_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_thread")

    ef_t2_start = FloatField(null=True, blank=True)
    ef_t2_w = FloatField(null=True, blank=True)
    ef_t2_wo = FloatField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.irrigation and self.irrigation_phases:
            raise ValidationError("Cannot have both irrigation system and irrigation phases in the same irrigation module")
        super().save(*args, **kwargs)


class IrrigationPhase(Submodule):
    parent = ForeignKey(Irrigation, on_delete=CASCADE, null=True, blank=True, related_name="irrigation_phases")
    irrigation_system_type = ForeignKey(IrrigationSystemType, on_delete=CASCADE, null=True, blank=True, related_name="irrigation_phases")
    fuel_type = ForeignKey(FuelType, on_delete=CASCADE, null=True, blank=True)
    well_depth = FloatField(null=True, blank=True)

    ha_start = FloatField(null=True, blank=True)
    ha_w = FloatField(null=True, blank=True)
    ha_wo = FloatField(null=True, blank=True)
    ha_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_ha_thread")

    gross_irrigation_water_start = FloatField(null=True, blank=True)
    gross_irrigation_water_w = FloatField(null=True, blank=True)
    gross_irrigation_water_wo = FloatField(null=True, blank=True)
    gross_irrigation_water_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_gross_irrigation_water_thread")

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


class Building(Submodule):
    parent = ForeignKey("api.Settlement", on_delete=CASCADE, null=True, blank=True, related_name="buildings")

    building_type_start = ForeignKey(BuildingType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_building_type_start")
    building_type_w = ForeignKey(BuildingType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_building_type_w")
    building_type_wo = ForeignKey(BuildingType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_building_type_wo")
    building_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_building_type_thread", on_delete=SET_NULL)

    area_m2_start = FloatField(null=True, blank=True)
    area_m2_w = FloatField(null=True, blank=True)
    area_m2_wo = FloatField(null=True, blank=True)
    area_m2_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_surface_thread", on_delete=SET_NULL)

    ef_t2_start = FloatField(null=True, blank=True)
    ef_t2_w = FloatField(null=True, blank=True)
    ef_t2_wo = FloatField(null=True, blank=True)


class Road(Submodule):
    parent = ForeignKey("api.Settlement", on_delete=CASCADE, null=True, blank=True, related_name="roads")

    road_type_start = ForeignKey(RoadType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_road_type_start")
    road_type_w = ForeignKey(RoadType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_road_type_w")
    road_type_wo = ForeignKey(RoadType, on_delete=CASCADE, null=True, blank=True, related_name="%(class)s_road_type_wo")
    road_type_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_road_type_thread", on_delete=SET_NULL)

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


class OtherInfrastructure(Submodule):
    parent = ForeignKey("api.Settlement", on_delete=CASCADE, null=True, blank=True, related_name="other_infrastructures")

    area_m2_start = FloatField(null=True, blank=True)
    area_m2_w = FloatField(null=True, blank=True)
    area_m2_wo = FloatField(null=True, blank=True)
    area_m2_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_area_m2_thread", on_delete=SET_NULL)

    ef_t2_start = FloatField(null=True, blank=True)
    ef_t2_w = FloatField(null=True, blank=True)
    ef_t2_wo = FloatField(null=True, blank=True)


class OrganicSoil(LandModuleFixed):
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
    is_peat_for_energy_w = BooleanField(default=False)
    is_peat_for_energy_wo = BooleanField(default=False)
    is_peat_for_energy_thread = OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_is_for_energy_thread", on_delete=SET_NULL)

    onsite_co2_peat_t2 = FloatField(null=True, blank=True)
    onsite_ch4_peat_t2 = FloatField(null=True, blank=True)
    onsite_n2o_peat_t2 = FloatField(null=True, blank=True)
    offsite_doc_peat_t2 = FloatField(null=True, blank=True)
    offsite_ch4_peat_t2 = FloatField(null=True, blank=True)

    peat_density_t2 = FloatField(null=True, blank=True)


class Settlement(LandModuleFixed):

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


class SetAside(LandModule, DoubleBiomassModule):

    is_set_aside_start = BooleanField(default=False)
    is_set_aside_w = BooleanField(default=False)
    is_set_aside_wo = BooleanField(default=False)


class DegradedLand(LandModule, SingleBiomassModule):
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

    def save(self, *args, **kwargs):
        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name="Degraded Land")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        super().save(*args, **kwargs)


class LandUseChange(Module):
    module_type_start = ForeignKey(ModuleType, on_delete=CASCADE, related_name="start")
    module_type_w = ForeignKey(ModuleType, on_delete=CASCADE, related_name="w")
    module_type_wo = ForeignKey(ModuleType, on_delete=CASCADE, related_name="wo")
    module_type_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="land_use_change_module_type_thread")

    area = FloatField()

    is_fire_used_start = BooleanField(default=False)
    is_fire_used_w = BooleanField(default=False)
    is_fire_used_wo = BooleanField(default=False)
    is_fire_used_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="land_use_change_is_fire_used_thread")

    dry_matter_start = FloatField(null=True, blank=True)
    dry_matter_w = FloatField(null=True, blank=True)
    dry_matter_wo = FloatField(null=True, blank=True)
    dry_matter_thread = ForeignKey(CommentThread, on_delete=CASCADE, null=True, blank=True, related_name="land_use_change_dry_matter_thread")

    def is_filled(self):
        return self.area is not None and self.module_type_start is not None and self.module_type_w is not None and self.module_type_wo is not None


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


class FundingAgency(Model):
    name = CharField(max_length=255, unique=True)
    abbreviation = CharField(max_length=255, unique=True, null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ExecutingAgency(Model):
    name = CharField(max_length=255, unique=True)
    abbreviation = CharField(max_length=255, unique=True, null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"
