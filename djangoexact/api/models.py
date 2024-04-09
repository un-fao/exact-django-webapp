import uuid
from abc import abstractmethod

from django.contrib.auth import models as auth_models
from django.core import exceptions, validators
from django.db import models as models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from . import utilities

alphanumeric = validators.RegexValidator(r"^[0-9a-zA-Z]*$", "Only alphanumeric characters are allowed.")
letters_only = validators.RegexValidator(r"^[a-zA-Z]*$", "Only letters are allowed.")
capitalized = validators.RegexValidator(r"[A-Z][a-z]*(\s[A-Z][a-z]*)*", "Only capitalized words are allowed.")
pc_as_float = validators.RegexValidator(r"^[0-1]*\.?[0-9]*$", "Only correctly formatted percentages are allowed.")

RICE_CULTIVATION_DAYS = 113


# Create your models here.
class CustomUser(auth_models.AbstractUser):
    country = models.ForeignKey("api.Country", on_delete=models.CASCADE, null=True, blank=True, related_name="users")
    email = models.EmailField(unique=True)

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


class ConfigParam(models.Model):
    name = models.CharField(max_length=255)
    value = models.TextField()

    def __str__(self):
        return f"({self.pk}) {self.name}"

    def get_parsed_value(self):
        if self.value.lower() == "true":
            return True
        elif self.value.lower() == "false":
            return False

        if "%" in self.value:
            try:
                return float(self.value.replace("%", "")) / 100
            except ValueError:
                return self.value

        try:
            return int(self.value)
        except ValueError:
            try:
                return float(self.value)
            except ValueError:
                return self.value

    class Meta:
        verbose_name_plural = "Config parameters"


class CommentThread(models.Model):
    def __str__(self):
        return f"({self.pk})"


class Comment(models.Model):
    thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="comments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    date_created = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    content = models.TextField()
    # We can add other fields like 'is_active', 'likes', etc.

    def __str__(self):
        return f"({self.pk}) {self.author.username}: {self.content[:40]}..."


class IPCCRegion(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class GasType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class GLEAMRegion(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ForestType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ForestConditionType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class SiteLocationType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class VegetationType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ActivityType(models.Model):
    name = models.CharField(max_length=255, validators=[letters_only, capitalized])

    def __str__(self):
        return self.name


class StatusType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    value = models.FloatField(null=True, blank=True, unique=True)

    class Meta:
        verbose_name_plural = "Status types"
        unique_together = ("name", "value")

    def __str__(self):
        return f"({self.id}) {self.name}"


class LandUseType(models.Model):
    name = models.CharField(max_length=100)
    module_types = models.ManyToManyField("api.ModuleType", related_name="land_use_types")
    forest_type = models.ForeignKey("api.ForestType", on_delete=models.CASCADE, null=True, blank=True)
    climates = models.ManyToManyField("api.Climate", related_name="land_use_types")
    moistures = models.ManyToManyField("api.Moisture", related_name="land_use_types")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        module_types = ", ".join([str(x.name) for x in self.module_types.all()])
        return f"({self.pk}) {self.name} - Active: {self.is_active}" + (f" ({module_types})" if module_types else "")


class ChangeRate(models.Model):
    name = models.CharField(max_length=25)
    value = models.FloatField(unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ProjectStatus(models.Model):
    name = models.CharField(max_length=25)
    value = models.IntegerField(unique=True)

    class Meta:
        verbose_name_plural = "Project statuses"

    def __str__(self):
        return self.name


class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True, blank=True, related_name="countries")
    ipcc_region = models.ForeignKey(IPCCRegion, on_delete=models.CASCADE, null=True, blank=True, related_name="countries")
    gleam_region = models.ForeignKey(GLEAMRegion, on_delete=models.CASCADE, null=True, blank=True, related_name="countries")

    class Meta:
        verbose_name_plural = "Countries"

    def __str__(self):
        return f"({self.pk}) {self.name}"


class Climate(models.Model):
    name = models.CharField(max_length=100)
    moistures = models.ManyToManyField("api.Moisture", related_name="climates")

    def __str__(self):
        return f"({self.pk}) {self.name}"


class Moisture(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class SoilType(models.Model):
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ExtractionSoilType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class TillageType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class OrganicInputType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ResidueManagementType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class WaterRegimeType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class PreSeasonWaterRegimeType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class OrganicAmendmentType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class TillageManagementType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class WaterManagementTypeBeforeCultivation(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class WaterManagementTypeAfterCultivation(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class GrasslandManagementType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class LivestockCategoryType(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class LivestockProductionType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ManureManagementType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ModuleType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    class_name = models.CharField(max_length=255, null=True, blank=True)
    is_luc = models.BooleanField(default=False)
    is_submodule = models.BooleanField(default=False)
    is_fixed_assessment = models.BooleanField(default=False)

    def __str__(self):
        return f"({self.pk}) {self.name}" + (" (LUC)" if self.is_luc else "")

    class Meta:
        verbose_name_plural = "Module types"


class ForestDegradationLevel(models.Model):
    name = models.CharField(max_length=100)
    value = models.FloatField()

    def __str__(self):
        return self.name


class FireType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class PeatType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class WaterbodyType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class TrophicType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class FisheryType(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class LargeFisheryGearType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class SmallFisheryGearType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class FishType(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class MacroFuelType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class FuelUseType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class FuelType(models.Model):
    name = models.CharField(max_length=100)
    fuel_use_type = models.ForeignKey(FuelUseType, on_delete=models.CASCADE, null=True, blank=True)
    macro_fuel_type = models.ForeignKey(MacroFuelType, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ("name", "fuel_use_type", "macro_fuel_type")

    def __str__(self):
        macro = getattr(self.macro_fuel_type, "name", None)
        return f"({self.pk}) {macro} - {self.name}"


class SalinityType(models.Model):
    value = models.CharField(max_length=3)

    def __str__(self):
        return self.value


##############################
########## Project ###########
##############################


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class Historical(models.Model):
    history = HistoricalRecords(related_name="%(class)s_history")

    class Meta:
        abstract = True


class Project(Historical):
    class Meta:
        verbose_name_plural = "Projects"
        unique_together = ("name", "user")

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="projects")
    date = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100, null=True, blank=True)
    cost = models.FloatField(null=True, blank=True)
    funding_agency = models.CharField(max_length=100, null=True, blank=True)
    executing_agency = models.CharField(max_length=100, null=True, blank=True)
    status = models.ForeignKey(ProjectStatus, on_delete=models.CASCADE, null=True, blank=True)

    implementation_years = models.IntegerField()
    capitalization_years = models.IntegerField()
    start_year = models.IntegerField(null=True, blank=True)

    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    climate = models.ForeignKey(Climate, on_delete=models.CASCADE)
    moisture = models.ForeignKey(Moisture, on_delete=models.CASCADE)
    soil_type = models.ForeignKey(SoilType, on_delete=models.CASCADE)

    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    lock_updated_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name="locked_projects")

    gw_potential = models.ForeignKey("ipcc.GlobalWarmingPotential", on_delete=models.CASCADE)

    soc_ref_t2 = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def save(self, *args, **kwargs):
        if self.pk:
            old = Project.objects.get(pk=self.pk)
            if old.user != self.user:
                raise exceptions.ValidationError("User cannot be changed")
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

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="invitations")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="invitations")
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="sent")

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = (("project", "user"),)

    def __str__(self):
        return f"({self.pk}) {self.project.name} - {self.user.email}"


class UserProjectGroup(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="memberships")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    def __str__(self):
        return f"({self.pk}) {self.project.name} - {self.user.username} - {self.group.name}"


##############################
######### Activity ###########
##############################


class Activity(Historical):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activities")
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    # user = models.ForeignKey(CustomUser, on_delete=models.CASCADE) # TODO: Define when it's useful to have this
    status = models.ForeignKey(StatusType, on_delete=models.CASCADE, null=True, blank=True)
    cost = models.FloatField(default=0)

    change_rate = models.ForeignKey(ChangeRate, on_delete=models.CASCADE, related_name="activities", null=True, blank=True)
    module_types = models.ManyToManyField("api.ModuleType", related_name="activities")

    climate_t2 = models.ForeignKey(Climate, on_delete=models.CASCADE, null=True, blank=True)
    moisture_t2 = models.ForeignKey(Moisture, on_delete=models.CASCADE, null=True, blank=True)
    soil_type_t2 = models.ForeignKey(SoilType, on_delete=models.CASCADE, null=True, blank=True)
    duration_t2 = models.IntegerField(default=0)
    start_year_t2 = models.IntegerField(null=True, blank=True)

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
    # module_type = models.ForeignKey("api.ModuleType", on_delete=models.CASCADE, related_name="%(class)s")
    status = models.ForeignKey(StatusType, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.parent:
            raise exceptions.ValidationError("Submodule must have a parent field specified in the model")

        if not self.status:
            self.status = StatusType.objects.get_or_create(name="EMPTY")[0]

        super().save(*args, **kwargs)


class Module(Historical):
    class Meta:
        abstract = True

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="%(class)s")
    notes = models.TextField(null=True, blank=True)
    start_year = models.IntegerField(default=1)

    soc_t2_start = models.FloatField(null=True, blank=True)
    soc_t2_w = models.FloatField(null=True, blank=True)
    soc_t2_wo = models.FloatField(null=True, blank=True)

    status = models.ForeignKey(StatusType, on_delete=models.CASCADE, null=True, blank=True)

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
    def get_biomass_t2(self, scenario: utilities.ScenarioTypes):
        try:
            return getattr(self, f"soc_t2_{scenario.value}")
        except TypeError:
            return None


class SingleBiomassModule(BiomassModule):
    biomass_t2_start = models.FloatField(null=True, blank=True)
    biomass_t2_w = models.FloatField(null=True, blank=True)
    biomass_t2_wo = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True

    def get_biomass_t2(self, scenario: utilities.ScenarioTypes):
        try:
            return super().get_biomass_t2(scenario) + getattr(self, f"biomass_t2_{scenario.value}")
        except TypeError:
            return None


class DoubleBiomassModule(BiomassModule):
    agb_t2_start = models.FloatField(null=True, blank=True)
    agb_t2_w = models.FloatField(null=True, blank=True)
    agb_t2_wo = models.FloatField(null=True, blank=True)

    bgb_t2_start = models.FloatField(null=True, blank=True)
    bgb_t2_w = models.FloatField(null=True, blank=True)
    bgb_t2_wo = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True

    def get_biomass_t2(self, scenario: utilities.ScenarioTypes):
        try:
            return super().get_biomass_t2(scenario) + getattr(self, f"agb_t2_{scenario.value}") + getattr(self, f"bgb_t2_{scenario.value}")
        except TypeError:
            return None


class MultiBiomassModule(DoubleBiomassModule):
    litter_t2_start = models.FloatField(null=True, blank=True)
    litter_t2_w = models.FloatField(null=True, blank=True)
    litter_t2_wo = models.FloatField(null=True, blank=True)

    deadwood_t2_start = models.FloatField(null=True, blank=True)
    deadwood_t2_w = models.FloatField(null=True, blank=True)
    deadwood_t2_wo = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True

    def get_biomass_t2(self, scenario: utilities.ScenarioTypes):
        try:
            return super().get_biomass_t2(scenario) + getattr(self, f"litter_t2_{scenario.value}") + getattr(self, f"deadwood_t2_{scenario.value}")
        except TypeError:
            return None


##### Land Use Changes #####


class OtherLandUse(Module):
    initial_land_use_type = models.ForeignKey(LandUseType, null=True, blank=True, on_delete=models.CASCADE, related_name="initial_land_use_type")
    final_land_use_type = models.ForeignKey(LandUseType, null=True, blank=True, on_delete=models.CASCADE, related_name="final_land_use_type")

    is_fire_used = models.BooleanField(default=False)

    ha_w = models.FloatField()
    ha_wo = models.FloatField()

    initial_biomass_t2 = models.FloatField(null=True, blank=True)
    initial_soil_carbon_t2 = models.FloatField(null=True, blank=True)

    final_biomass_t2 = models.FloatField(null=True, blank=True)
    final_soil_carbon_t2 = models.FloatField(null=True, blank=True)

    implementation_year_start = models.IntegerField(null=True, blank=True)


class LandModule(Module):
    land_use_change = models.OneToOneField("api.LandUseChange", on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s")

    area = models.FloatField(null=True, blank=True)

    land_use_type_start = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_start")
    land_use_type_w = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_w")
    land_use_type_wo = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_wo")
    land_use_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_thread")

    flu_t2_start = models.FloatField(null=True, blank=True)
    flu_t2_w = models.FloatField(null=True, blank=True)
    flu_t2_wo = models.FloatField(null=True, blank=True)

    fi_t2_start = models.FloatField(null=True, blank=True)
    fi_t2_w = models.FloatField(null=True, blank=True)
    fi_t2_wo = models.FloatField(null=True, blank=True)

    fmg_t2_start = models.FloatField(null=True, blank=True)
    fmg_t2_w = models.FloatField(null=True, blank=True)
    fmg_t2_wo = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True


class LandSubmodule(Submodule):
    land_use_change = models.OneToOneField("api.LandUseChange", on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s")

    area = models.FloatField(null=True, blank=True)

    land_use_type_start = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_start")
    land_use_type_w = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_w")
    land_use_type_wo = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_wo")
    land_use_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_thread")

    flu_t2_start = models.FloatField(null=True, blank=True)
    flu_t2_w = models.FloatField(null=True, blank=True)
    flu_t2_wo = models.FloatField(null=True, blank=True)

    fi_t2_start = models.FloatField(null=True, blank=True)
    fi_t2_w = models.FloatField(null=True, blank=True)
    fi_t2_wo = models.FloatField(null=True, blank=True)

    fmg_t2_start = models.FloatField(null=True, blank=True)
    fmg_t2_w = models.FloatField(null=True, blank=True)
    fmg_t2_wo = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True


class LandModuleNoScenarios(Module):
    land_use_change = models.OneToOneField("api.LandUseChange", on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s")

    land_use_type = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_start")
    land_use_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_thread")

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


class CropType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    is_main_crop = models.BooleanField(default=False)
    is_agrofoforestry = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"({self.pk}) {self.name}"


class AnnualCropping(LandModule, SingleBiomassModule):
    tillage_management_type_start = models.ForeignKey(
        TillageManagementType,
        on_delete=models.CASCADE,
        related_name="%(class)s_tillage_management_type_start",
        null=True,
        blank=True,
    )
    tillage_management_type_w = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, related_name="%(class)s_tillage_management_type_w", null=True, blank=True)
    tillage_management_type_wo = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, related_name="%(class)s_tillage_management_type_wo", null=True, blank=True)
    tillage_management_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_thread")

    organic_input_type_start = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, related_name="%(class)s_organic_input_type_start", null=True, blank=True)
    organic_input_type_w = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, related_name="%(class)s_organic_input_type_w", null=True, blank=True)
    organic_input_type_wo = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, related_name="%(class)s_organic_input_type_wo", null=True, blank=True)
    organic_input_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_thread")

    residue_management_type_start = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, related_name="%(class)s_residue_management_type_start", null=True, blank=True)
    residue_management_type_w = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, related_name="%(class)s_residue_management_type_w", null=True, blank=True)
    residue_management_type_wo = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, related_name="%(class)s_residue_management_type_wo", null=True, blank=True)
    residue_management_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_thread")

    crop_yield_start = models.FloatField(default=0)
    crop_yield_w = models.FloatField(default=0)
    crop_yield_wo = models.FloatField(default=0)
    crop_yield_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_crop_yield_thread")

    area = models.FloatField(null=True, blank=True)

    main_soil_carbon_t2_start = models.FloatField(null=True, blank=True)
    main_soil_carbon_t2_w = models.FloatField(null=True, blank=True)
    main_soil_carbon_t2_wo = models.FloatField(null=True, blank=True)

    main_tillage_factor_t2_start = models.FloatField(null=True, blank=True)
    main_tillage_factor_t2_w = models.FloatField(null=True, blank=True)
    main_tillage_factor_t2_wo = models.FloatField(null=True, blank=True)

    main_organic_input_factor_t2_start = models.FloatField(null=True, blank=True)
    main_organic_input_factor_t2_w = models.FloatField(null=True, blank=True)
    main_organic_input_factor_t2_wo = models.FloatField(null=True, blank=True)

    main_biomass_factor_t2_start = models.FloatField(null=True, blank=True)
    main_biomass_factor_t2_w = models.FloatField(null=True, blank=True)
    main_biomass_factor_t2_wo = models.FloatField(null=True, blank=True)

    main_land_use_factor_t2_start = models.FloatField(null=True, blank=True)
    main_land_use_factor_t2_w = models.FloatField(null=True, blank=True)
    main_land_use_factor_t2_wo = models.FloatField(null=True, blank=True)

    minor_land_use_type_start = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_land_use_type_start")
    minor_land_use_type_w = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_land_use_type_w")
    minor_land_use_type_wo = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_land_use_type_wo")

    minor_yield_start = models.FloatField(null=True, blank=True)
    minor_yield_w = models.FloatField(null=True, blank=True)
    minor_yield_wo = models.FloatField(null=True, blank=True)

    minor_residue_management_type_start = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_residue_management_type")
    minor_residue_management_type_w = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_residue_management_type_w")
    minor_residue_management_type_wo = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_residue_management_type_wo")

    minor_biomass_factor_t2_start = models.FloatField(null=True, blank=True)
    minor_biomass_factor_t2_w = models.FloatField(null=True, blank=True)
    minor_biomass_factor_t2_wo = models.FloatField(null=True, blank=True)

    soc_ref_t2_start = models.FloatField(null=True, blank=True)
    soc_ref_t2_w = models.FloatField(null=True, blank=True)
    soc_ref_t2_wo = models.FloatField(null=True, blank=True)


class PerennialCrop(models.Model):
    class Meta:
        abstract = True

    tillage_management_type_start = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_start")
    tillage_management_type_w = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_w")
    tillage_management_type_wo = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_wo")
    tillage_management_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_thread")

    organic_input_type_start = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_start")
    organic_input_type_w = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_w")
    organic_input_type_wo = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_wo")
    organic_input_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_thread")

    is_biomass_burned_start = models.BooleanField(null=True, blank=True)
    is_biomass_burned_w = models.BooleanField(null=True, blank=True)
    is_biomass_burned_wo = models.BooleanField(null=True, blank=True)
    is_biomass_burned_thread = models.ForeignKey(
        CommentThread,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_is_biomass_burned_thread",
    )

    area = models.FloatField(null=True, blank=True)

    crop_yield_start = models.FloatField(null=True, blank=True)
    crop_yield_w = models.FloatField(null=True, blank=True)
    crop_yield_wo = models.FloatField(null=True, blank=True)
    crop_yield_thread = models.ForeignKey(
        CommentThread,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_crop_yield_thread",
    )

    ag_t2_start = models.FloatField(null=True, blank=True)
    ag_t2_w = models.FloatField(null=True, blank=True)
    ag_t2_wo = models.FloatField(null=True, blank=True)

    agb_max_t2_start = models.FloatField(null=True, blank=True)
    agb_max_t2_w = models.FloatField(null=True, blank=True)
    agb_max_t2_wo = models.FloatField(null=True, blank=True)

    bg_t2_start = models.FloatField(null=True, blank=True)
    bg_t2_w = models.FloatField(null=True, blank=True)
    bg_t2_wo = models.FloatField(null=True, blank=True)

    soc_t2_start = models.FloatField(null=True, blank=True)
    soc_t2_w = models.FloatField(null=True, blank=True)
    soc_t2_wo = models.FloatField(null=True, blank=True)

    tillage_factor_t2_start = models.FloatField(null=True, blank=True)
    tillage_factor_t2_w = models.FloatField(null=True, blank=True)
    tillage_factor_t2_wo = models.FloatField(null=True, blank=True)

    input_factor_t2_start = models.FloatField(null=True, blank=True)
    input_factor_t2_w = models.FloatField(null=True, blank=True)
    input_factor_t2_wo = models.FloatField(null=True, blank=True)

    residue_burned_t2_start = models.FloatField(null=True, blank=True)
    residue_burned_t2_w = models.FloatField(null=True, blank=True)
    residue_burned_t2_wo = models.FloatField(null=True, blank=True)

    fire_periodicity_t2_start = models.FloatField(null=True, blank=True)
    fire_periodicity_t2_w = models.FloatField(null=True, blank=True)
    fire_periodicity_t2_wo = models.FloatField(null=True, blank=True)

    flu_t2_start = models.FloatField(null=True, blank=True)
    flu_t2_w = models.FloatField(null=True, blank=True)
    flu_t2_wo = models.FloatField(null=True, blank=True)

    # def save(self, *args, **kwargs):
    #     if not self.land_use_type_start:
    #         self.land_use_type_start = LandUseType.objects.get(name="Agroforestry - Default")
    #         self.land_use_type_w = self.land_use_type_start
    #         self.land_use_type_wo = self.land_use_type_start

    #     super().save(*args, **kwargs)


class PerennialCropping(PerennialCrop, LandModule, DoubleBiomassModule):
    pass


class CroplandMinorSeason(models.Model):
    class Meta:
        abstract = True

    land_use_type_start = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_start")
    land_use_type_w = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_w")
    land_use_type_wo = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_wo")

    residue_management_type_start = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_start")
    residue_management_type_w = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_w")
    residue_management_type_wo = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_wo")

    yield_start = models.FloatField(null=True, blank=True)
    yield_w = models.FloatField(null=True, blank=True)
    yield_wo = models.FloatField(null=True, blank=True)

    biomass_factor_t2_start = models.FloatField(null=True, blank=True)
    biomass_factor_t2_w = models.FloatField(null=True, blank=True)
    biomass_factor_t2_wo = models.FloatField(null=True, blank=True)


class MinorSeasonPerennialCropping(CroplandMinorSeason, LandSubmodule):
    parent = models.ForeignKey(PerennialCropping, on_delete=models.CASCADE, related_name="minor_seasons", null=True, blank=True)


class MinorSeasonAnnualCropping(CroplandMinorSeason, LandSubmodule):
    parent = models.ForeignKey(AnnualCropping, on_delete=models.CASCADE, related_name="minor_seasons", null=True, blank=True)


class Rice(models.Model):
    class Meta:
        abstract = True

    cultivation_period_start = models.IntegerField(default=RICE_CULTIVATION_DAYS)
    cultivation_period_w = models.IntegerField(default=RICE_CULTIVATION_DAYS)
    cultivation_period_wo = models.IntegerField(default=RICE_CULTIVATION_DAYS)

    water_management_type_before_cultivation_start = models.ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_before_cultivation_start", null=True)
    water_management_type_before_cultivation_w = models.ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_before_cultivation_w", null=True)
    water_management_type_before_cultivation_wo = models.ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_before_cultivation_wo", null=True)

    water_management_type_after_cultivation_start = models.ForeignKey(WaterManagementTypeAfterCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_after_cultivation_start", null=True)
    water_management_type_after_cultivation_w = models.ForeignKey(WaterManagementTypeAfterCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_after_cultivation_w", null=True)
    water_management_type_after_cultivation_wo = models.ForeignKey(WaterManagementTypeAfterCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_after_cultivation_wo", null=True)

    organic_amendment_type_start = models.ForeignKey(OrganicAmendmentType, on_delete=models.CASCADE, related_name="%(class)s_organic_amendment_type_start", null=True)
    organic_amendment_type_w = models.ForeignKey(OrganicAmendmentType, on_delete=models.CASCADE, related_name="%(class)s_organic_amendment_type_w", null=True)
    organic_amendment_type_wo = models.ForeignKey(OrganicAmendmentType, on_delete=models.CASCADE, related_name="%(class)s_organic_amendment_type_wo", null=True)

    crop_yield_start = models.FloatField(null=True, blank=True)
    crop_yield_w = models.FloatField(null=True, blank=True)
    crop_yield_wo = models.FloatField(null=True, blank=True)

    main_biomass_factor_t2_start = models.FloatField(null=True, blank=True)
    main_biomass_factor_t2_w = models.FloatField(null=True, blank=True)
    main_biomass_factor_t2_wo = models.FloatField(null=True, blank=True)

    soc_t2_start = models.FloatField(null=True, blank=True)
    soc_t2_w = models.FloatField(null=True, blank=True)
    soc_t2_wo = models.FloatField(null=True, blank=True)

    land_use_factor_t2_start = models.FloatField(null=True, blank=True)
    land_use_factor_t2_w = models.FloatField(null=True, blank=True)
    land_use_factor_t2_wo = models.FloatField(null=True, blank=True)

    efc_t2_start = models.FloatField(null=True, blank=True)
    efc_t2_w = models.FloatField(null=True, blank=True)
    efc_t2_wo = models.FloatField(null=True, blank=True)

    sfw_t2_start = models.FloatField(null=True, blank=True)
    sfw_t2_w = models.FloatField(null=True, blank=True)
    sfw_t2_wo = models.FloatField(null=True, blank=True)

    sfp_t2_start = models.FloatField(null=True, blank=True)
    sfp_t2_w = models.FloatField(null=True, blank=True)
    sfp_t2_wo = models.FloatField(null=True, blank=True)

    sfp_t2_start = models.FloatField(null=True, blank=True)
    sfp_t2_w = models.FloatField(null=True, blank=True)
    sfp_t2_wo = models.FloatField(null=True, blank=True)

    sfo_t2_start = models.FloatField(null=True, blank=True)
    sfo_t2_w = models.FloatField(null=True, blank=True)
    sfo_t2_wo = models.FloatField(null=True, blank=True)

    efi_t2_start = models.FloatField(null=True, blank=True)
    efi_t2_w = models.FloatField(null=True, blank=True)
    efi_t2_wo = models.FloatField(null=True, blank=True)

    rice_straw_t2_start = models.FloatField(null=True, blank=True)
    rice_straw_t2_w = models.FloatField(null=True, blank=True)
    rice_straw_t2_wo = models.FloatField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name="Flooded Rice")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        super().save(*args, **kwargs)


class FloodedRice(Rice, LandModuleFixed, SingleBiomassModule):
    pass


class MinorSeasonFloodedRice(Rice, LandSubmodule):
    parent = models.ForeignKey(FloodedRice, on_delete=models.CASCADE, related_name="minor_seasons", null=True, blank=True)


##### Grassland and Livestock #####


class Grassland(LandModuleFixed, SingleBiomassModule):
    grassland_management_type_start = models.ForeignKey(GrasslandManagementType, on_delete=models.CASCADE, related_name="%(class)s_grassland_management_type_start", null=True)
    grassland_management_type_w = models.ForeignKey(GrasslandManagementType, on_delete=models.CASCADE, related_name="%(class)s_grassland_management_type_w", null=True)
    grassland_management_type_wo = models.ForeignKey(GrasslandManagementType, on_delete=models.CASCADE, related_name="%(class)s_grassland_management_type_wo", null=True)

    is_fire_used_start = models.BooleanField(default=False)
    is_fire_used_w = models.BooleanField(default=False)
    is_fire_used_wo = models.BooleanField(default=False)
    is_fire_used_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_is_fire_used_thread")

    fire_periodicity_start = models.FloatField(null=True, blank=True, default=0)
    fire_periodicity_w = models.FloatField(null=True, blank=True, default=0)
    fire_periodicity_wo = models.FloatField(null=True, blank=True, default=0)
    fire_periodicity_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fire_periodicity_thread")

    fire_impact_start = models.FloatField(null=True, blank=True)
    fire_impact_w = models.FloatField(null=True, blank=True)
    fire_impact_wo = models.FloatField(null=True, blank=True)
    fire_impact_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fire_impact_thread")

    yield_start = models.FloatField(null=True, blank=True)
    yield_w = models.FloatField(null=True, blank=True)
    yield_wo = models.FloatField(null=True, blank=True)
    yield_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_yield_thread")

    area = models.FloatField(null=True, blank=True)

    combustion_factor_t2_start = models.FloatField(null=True, blank=True)
    combustion_factor_t2_w = models.FloatField(null=True, blank=True)
    combustion_factor_t2_wo = models.FloatField(null=True, blank=True)

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
    livestock_category_type = models.ForeignKey(LivestockCategoryType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_livestock_category_type")
    livestock_category_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_livestock_categories_thread", on_delete=models.SET_NULL)

    livestock_production_type_start = models.ForeignKey(LivestockProductionType, on_delete=models.CASCADE, null=True, blank=True)
    livestock_production_type_w = models.ForeignKey(LivestockProductionType, on_delete=models.CASCADE, related_name="%(class)s_livestock_productions_w", null=True, blank=True)
    livestock_production_type_wo = models.ForeignKey(LivestockProductionType, on_delete=models.CASCADE, related_name="%(class)s_livestock_productions_wo", null=True, blank=True)
    livestock_production_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_livestock_production_type_thread", on_delete=models.SET_NULL)

    production_start = models.FloatField(null=True, blank=True)
    production_w = models.FloatField(null=True, blank=True)
    production_wo = models.FloatField(null=True, blank=True)
    production_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_production_thread", on_delete=models.SET_NULL)

    heads_number_start = models.IntegerField(null=True, blank=True)
    heads_number_w = models.IntegerField(null=True, blank=True)
    heads_number_wo = models.IntegerField(null=True, blank=True)
    heads_number_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_heads_number_thread", on_delete=models.SET_NULL)

    complementary_manure_management_type_start = models.ForeignKey(ManureManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_manure_management_type_t2_start")
    complementary_manure_management_type_w = models.ForeignKey(ManureManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_manure_management_type_t2_w")
    complementary_manure_management_type_wo = models.ForeignKey(ManureManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_manure_management_type_t2_wo")
    complementary_manure_management_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_complementary_manure_management_type_thread", on_delete=models.SET_NULL)

    percentage_heads_on_pasture_start = models.FloatField(null=True, blank=True)
    percentage_heads_on_pasture_w = models.FloatField(null=True, blank=True)
    percentage_heads_on_pasture_wo = models.FloatField(null=True, blank=True)
    percentage_heads_on_pasture_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_percentage_heads_on_pasture_thread", on_delete=models.SET_NULL)

    enteric_fermentation_t2_start = models.FloatField(null=True, blank=True)
    enteric_fermentation_t2_w = models.FloatField(null=True, blank=True)
    enteric_fermentation_t2_wo = models.FloatField(null=True, blank=True)

    prp_percentage_t2_start = models.FloatField(null=True, blank=True)
    prp_percentage_t2_w = models.FloatField(null=True, blank=True)
    prp_percentage_t2_wo = models.FloatField(null=True, blank=True)

    prp_ch4_t2_start = models.FloatField(null=True, blank=True)
    prp_ch4_t2_w = models.FloatField(null=True, blank=True)
    prp_ch4_t2_wo = models.FloatField(null=True, blank=True)

    prp_n2o_t2_start = models.FloatField(null=True, blank=True)
    prp_n2o_t2_w = models.FloatField(null=True, blank=True)
    prp_n2o_t2_wo = models.FloatField(null=True, blank=True)

    emission_factor_ch4_t2_start = models.FloatField(null=True, blank=True)
    emission_factor_n2o_t2_start = models.FloatField(null=True, blank=True)

    emission_factor_ch4_t2_w = models.FloatField(null=True, blank=True)
    emission_factor_n2o_t2_w = models.FloatField(null=True, blank=True)

    emission_factor_ch4_t2_wo = models.FloatField(null=True, blank=True)
    emission_factor_n2o_t2_wo = models.FloatField(null=True, blank=True)

    implementation_year_start = models.IntegerField(null=True, blank=True)


##### Forest Management #####


class ForestManagement(LandModule, MultiBiomassModule):
    forest_type = models.ForeignKey(ForestType, on_delete=models.CASCADE, null=True, blank=True)
    forest_condition_type = models.ForeignKey(ForestConditionType, on_delete=models.CASCADE, null=True, blank=True)

    ##### ROTATION #####

    rotation_length_yrs_start = models.IntegerField(null=True, blank=True)
    rotation_length_yrs_w = models.IntegerField(null=True, blank=True)
    rotation_length_yrs_wo = models.IntegerField(null=True, blank=True)
    rotation_length_yrs_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_rotation_length_yrs_thread")

    rotation_percentage_biomass_for_energy_start = models.FloatField(null=True, blank=True, default=0)
    rotation_percentage_biomass_for_energy_w = models.FloatField(null=True, blank=True, default=0)
    rotation_percentage_biomass_for_energy_wo = models.FloatField(null=True, blank=True, default=0)
    rotation_percentage_biomass_for_energy_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_rotation_percentage_biomass_for_energy_thread")

    ##### LOGGING #####

    logging_recurrence_yrs_start = models.IntegerField(null=True, blank=True)
    logging_recurrence_yrs_w = models.IntegerField(null=True, blank=True)
    logging_recurrence_yrs_wo = models.IntegerField(null=True, blank=True)
    logging_recurrence_yrs_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_logging_recurrence_yrs_thread")

    logging_percentage_agb_logged_start = models.FloatField(null=True, blank=True, default=0, validators=[validators.MinValueValidator(0), validators.MaxValueValidator(1)])
    logging_percentage_agb_logged_w = models.FloatField(null=True, blank=True, default=0, validators=[validators.MinValueValidator(0), validators.MaxValueValidator(1)])
    logging_percentage_agb_logged_wo = models.FloatField(null=True, blank=True, default=0, validators=[validators.MinValueValidator(0), validators.MaxValueValidator(1)])
    logging_percentage_agb_logged_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_logging_percentage_agb_logged_thread")

    logging_percentage_biomass_for_energy_start = models.FloatField(null=True, blank=True, default=0)
    logging_percentage_biomass_for_energy_w = models.FloatField(null=True, blank=True, default=0)
    logging_percentage_biomass_for_energy_wo = models.FloatField(null=True, blank=True, default=0)
    logging_percentage_biomass_for_energy_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_logging_percentage_biomass_for_energy_thread")

    ##### DEGRADATION #####

    average_yearly_degradation_percentage_start = models.FloatField(null=True, blank=True, default=0)
    average_yearly_degradation_percentage_w = models.FloatField(null=True, blank=True, default=0)
    average_yearly_degradation_percentage_wo = models.FloatField(null=True, blank=True, default=0)
    average_yearly_degradation_percentage_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_average_yearly_degradation_percentage_thread")

    ##### TIER 2 #####

    agb_growth_rate_le_20_yrs_t2_start = models.FloatField(null=True, blank=True)
    agb_growth_rate_le_20_yrs_t2_w = models.FloatField(null=True, blank=True)
    agb_growth_rate_le_20_yrs_t2_wo = models.FloatField(null=True, blank=True)

    agb_growth_rate_gt_20_yrs_t2_start = models.FloatField(null=True, blank=True)
    agb_growth_rate_gt_20_yrs_t2_w = models.FloatField(null=True, blank=True)
    agb_growth_rate_gt_20_yrs_t2_wo = models.FloatField(null=True, blank=True)

    bgb_growth_rate_le_20_yrs_t2_start = models.FloatField(null=True, blank=True)
    bgb_growth_rate_le_20_yrs_t2_w = models.FloatField(null=True, blank=True)
    bgb_growth_rate_le_20_yrs_t2_wo = models.FloatField(null=True, blank=True)

    bgb_growth_rate_gt_20_yrs_t2_start = models.FloatField(null=True, blank=True)
    bgb_growth_rate_gt_20_yrs_t2_w = models.FloatField(null=True, blank=True)
    bgb_growth_rate_gt_20_yrs_t2_wo = models.FloatField(null=True, blank=True)

    rotation_start_year_t2_start = models.IntegerField(default=0)
    rotation_start_year_t2_w = models.IntegerField(default=0)
    rotation_start_year_t2_wo = models.IntegerField(default=0)

    logging_start_year_t2_start = models.IntegerField(default=0)
    logging_start_year_t2_w = models.IntegerField(default=0)
    logging_start_year_t2_wo = models.IntegerField(default=0)

    logging_dry_matter_logged_t2_start = models.FloatField(null=True, blank=True)
    logging_dry_matter_logged_t2_w = models.FloatField(null=True, blank=True)
    logging_dry_matter_logged_t2_wo = models.FloatField(null=True, blank=True)

    degradation_dry_matter_impacted_t2_start = models.FloatField(null=True, blank=True)
    degradation_dry_matter_impacted_t2_w = models.FloatField(null=True, blank=True)
    degradation_dry_matter_impacted_t2_wo = models.FloatField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.land_use_type_start:
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start
        return super().save(*args, **kwargs)


class DisturbanceType(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ForestDisturbance(models.Model):
    forest_management = models.ForeignKey(ForestManagement, on_delete=models.CASCADE, related_name="disturbances")

    disturbance_type = models.ForeignKey(DisturbanceType, on_delete=models.CASCADE, null=True, blank=True)
    disturbance_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_disturbance_type_thread")

    recurrence_yrs_start = models.IntegerField(null=True, blank=True)
    recurrence_yrs_w = models.IntegerField(null=True, blank=True)
    recurrence_yrs_wo = models.IntegerField(null=True, blank=True)
    recurrence_yrs_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_disturbance_recurrence_yrs_thread")

    percentage_biomass_destruction_start = models.FloatField(null=True, blank=True)
    percentage_biomass_destruction_w = models.FloatField(null=True, blank=True)
    percentage_biomass_destruction_wo = models.FloatField(null=True, blank=True)
    percentage_biomass_destruction_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_disturbance_percentage_biomass_destruction_thread")

    start_year_t2_start = models.IntegerField(default=1)
    start_year_t2_w = models.IntegerField(default=1)
    start_year_t2_wo = models.IntegerField(default=1)

    dry_matter_impacted_t2_start = models.FloatField(null=True, blank=True)
    dry_matter_impacted_t2_w = models.FloatField(null=True, blank=True)
    dry_matter_impacted_t2_wo = models.FloatField(null=True, blank=True)


class Waterbody(Module):
    waterbody_type = models.ForeignKey(WaterbodyType, on_delete=models.CASCADE, null=True, blank=True)
    area = models.FloatField(null=True, blank=True)
    trophic_type_start = models.ForeignKey(TrophicType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_trophic_class_start")
    trophic_type_w = models.ForeignKey(TrophicType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_trophic_class_w")
    trophic_type_wo = models.ForeignKey(TrophicType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_trophic_class_wo")

    ch4_ef_t2_start = models.FloatField(null=True, blank=True)
    ch4_ef_t2_w = models.FloatField(null=True, blank=True)
    ch4_ef_t2_wo = models.FloatField(null=True, blank=True)

    alpha_t2_start = models.FloatField(null=True, blank=True)
    alpha_t2_w = models.FloatField(null=True, blank=True)
    alpha_t2_wo = models.FloatField(null=True, blank=True)

    mean_annual_t2_start = models.FloatField(null=True, blank=True)
    mean_annual_t2_w = models.FloatField(null=True, blank=True)
    mean_annual_t2_wo = models.FloatField(null=True, blank=True)


class CoastalWetland(Module):
    land_use_type = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True)

    ha_start = models.FloatField(null=True, blank=True)
    ha_w = models.FloatField(null=True, blank=True)
    ha_wo = models.FloatField(null=True, blank=True)
    ha_thread = models.ForeignKey(CommentThread, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_ha_thread")

    area_under_drainage_start = models.FloatField(null=True, blank=True)
    area_under_drainage_w = models.FloatField(null=True, blank=True)
    area_under_drainage_wo = models.FloatField(null=True, blank=True)
    area_under_drainage_thread = models.ForeignKey(CommentThread, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_area_under_drainage_thread")

    drained_area_excavated_start = models.FloatField(null=True, blank=True)
    drained_area_excavated_w = models.FloatField(null=True, blank=True)
    drained_area_excavated_wo = models.FloatField(null=True, blank=True)
    drained_area_excavated_thread = models.ForeignKey(CommentThread, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_drained_area_excavated_thread")

    area_not_drained_or_rewetted_start = models.FloatField(null=True, blank=True)
    area_not_drained_or_rewetted_w = models.FloatField(null=True, blank=True)
    area_not_drained_or_rewetted_wo = models.FloatField(null=True, blank=True)
    area_not_drained_or_rewetted_thread = models.ForeignKey(CommentThread, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_area_not_drained_or_rewetted_thread")

    area_w_restored_vegetation_start = models.FloatField(null=True, blank=True)
    area_w_restored_vegetation_w = models.FloatField(null=True, blank=True)
    area_w_restored_vegetation_wo = models.FloatField(null=True, blank=True)
    area_w_restored_vegetation_thread = models.ForeignKey(CommentThread, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_area_w_restored_vegetation_thread")

    soil_type_t2 = models.ForeignKey(SoilType, null=True, blank=True, on_delete=models.SET_NULL)

    soc_t2_start = models.FloatField(null=True, blank=True)
    soc_t2_w = models.FloatField(null=True, blank=True)
    soc_t2_wo = models.FloatField(null=True, blank=True)

    pc_c_lost_after_excavation_t2_start = models.FloatField(null=True, blank=True)
    pc_c_lost_after_excavation_t2_w = models.FloatField(null=True, blank=True)
    pc_c_lost_after_excavation_t2_wo = models.FloatField(null=True, blank=True)

    agb_t2_start = models.FloatField(null=True, blank=True)
    agb_t2_w = models.FloatField(null=True, blank=True)
    agb_t2_wo = models.FloatField(null=True, blank=True)

    bgb_t2_start = models.FloatField(null=True, blank=True)
    bgb_t2_w = models.FloatField(null=True, blank=True)
    bgb_t2_wo = models.FloatField(null=True, blank=True)

    litter_t2_start = models.FloatField(null=True, blank=True)
    litter_t2_w = models.FloatField(null=True, blank=True)
    litter_t2_wo = models.FloatField(null=True, blank=True)

    deadwood_t2_start = models.FloatField(null=True, blank=True)
    deadwood_t2_w = models.FloatField(null=True, blank=True)
    deadwood_t2_wo = models.FloatField(null=True, blank=True)

    drainage_ef_t2_start = models.FloatField(null=True, blank=True)
    drainage_ef_t2_w = models.FloatField(null=True, blank=True)
    drainage_ef_t2_wo = models.FloatField(null=True, blank=True)

    co2_rewetting_t2_start = models.FloatField(null=True, blank=True)
    co2_rewetting_t2_w = models.FloatField(null=True, blank=True)
    co2_rewetting_t2_wo = models.FloatField(null=True, blank=True)

    ch4_rewetting_t2_start = models.FloatField(null=True, blank=True)
    ch4_rewetting_t2_w = models.FloatField(null=True, blank=True)
    ch4_rewetting_t2_wo = models.FloatField(null=True, blank=True)

    avg_salinity_t2 = models.ForeignKey(SalinityType, null=True, blank=True, on_delete=models.SET_NULL)


##### Fisheries and Aquaculture #####


class Fishery(Module):
    class Meta:
        abstract = True

    refrigerant_pc_start = models.FloatField(validators=[pc_as_float], default=0)
    refrigerant_pc_w = models.FloatField(validators=[pc_as_float], default=0)
    refrigerant_pc_wo = models.FloatField(validators=[pc_as_float], default=0)
    refrigerant_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_refrigerant_thread", on_delete=models.SET_NULL)

    refrigerant_gwp = models.FloatField(null=True, blank=True, default=1810)

    fui_start = models.FloatField(null=True, blank=True)
    fui_w = models.FloatField(null=True, blank=True)
    fui_wo = models.FloatField(null=True, blank=True)

    total_catch_yr_start = models.FloatField(null=True, blank=True)
    total_catch_yr_w = models.FloatField(null=True, blank=True)
    total_catch_yr_wo = models.FloatField(null=True, blank=True)
    total_catch_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_total_catch_thread", on_delete=models.SET_NULL)

    ice_preserved_catch_pc_start = models.FloatField(default=0, validators=[pc_as_float])
    ice_preserved_catch_pc_w = models.FloatField(default=0, validators=[pc_as_float])
    ice_preserved_catch_pc_wo = models.FloatField(default=0, validators=[pc_as_float])
    ice_preserved_catch_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_ice_preserved_catch_thread", on_delete=models.SET_NULL)

    # TODO: Is the non-t2 value static for this specific module? It's always related to Gasoil/Diesel
    energy_emission_factor_t2_start = models.FloatField(null=True, blank=True)
    energy_emission_factor_t2_w = models.FloatField(null=True, blank=True)
    energy_emission_factor_t2_wo = models.FloatField(null=True, blank=True)

    refrigerant_lost_per_tonne_t2_start = models.FloatField(null=True, blank=True)
    refrigerant_lost_per_tonne_t2_w = models.FloatField(null=True, blank=True)
    refrigerant_lost_per_tonne_t2_wo = models.FloatField(null=True, blank=True)

    refrigerant_gwp_t2_start = models.FloatField(null=True, blank=True)
    refrigerant_gwp_t2_w = models.FloatField(null=True, blank=True)
    refrigerant_gwp_t2_wo = models.FloatField(null=True, blank=True)

    tonnes_of_ice_t2_start = models.FloatField(null=True, blank=True)
    tonnes_of_ice_t2_w = models.FloatField(null=True, blank=True)
    tonnes_of_ice_t2_wo = models.FloatField(null=True, blank=True)

    # TODO: This part has some internal logic that has to be examined more deeply
    # NOTE: The logic does not seem to make much sense. It's just to display some values and can probably be ignored altogether
    inshore_ice_production_kwh_per_tonne_t2_start = models.FloatField(null=True, blank=True)
    inshore_ice_production_kwh_per_tonne_t2_w = models.FloatField(null=True, blank=True)
    inshore_ice_production_kwh_per_tonne_t2_wo = models.FloatField(null=True, blank=True)

    inshore_ice_production_country_t2 = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)

    implementation_year_t2 = models.IntegerField(null=True, blank=True)


class SmallFishery(Fishery):
    gear_type_start = models.ForeignKey(SmallFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_start")
    gear_type_w = models.ForeignKey(SmallFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_w")
    gear_type_wo = models.ForeignKey(SmallFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_wo")
    gear_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_gear_type_thread", on_delete=models.SET_NULL)
    fishery_type = models.ForeignKey(FisheryType, on_delete=models.CASCADE, null=True, blank=True)
    fui_default = models.ForeignKey("ipcc.SmallFisheryFUI", on_delete=models.CASCADE, null=True, blank=True)


class LargeFishery(Fishery):
    gear_type_start = models.ForeignKey(LargeFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_start")
    gear_type_w = models.ForeignKey(LargeFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_w")
    gear_type_wo = models.ForeignKey(LargeFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_wo")
    gear_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_gear_type_thread", on_delete=models.SET_NULL)
    fish_type = models.ForeignKey(FishType, on_delete=models.CASCADE, null=True, blank=True)
    fui_default = models.ForeignKey("ipcc.LargeFisheryFUI", on_delete=models.CASCADE, null=True, blank=True)


class Aquaculture(Module):
    # fish_type = models.ForeignKey(FishType, on_delete=models.CASCADE, null=True, blank=True)

    annual_production_start = models.FloatField(null=True, blank=True)
    annual_production_w = models.FloatField(null=True, blank=True)
    annual_production_wo = models.FloatField(null=True, blank=True)

    n2o_from_production_t2_start = models.FloatField(null=True, blank=True)
    n2o_from_production_t2_w = models.FloatField(null=True, blank=True)
    n2o_from_production_t2_wo = models.FloatField(null=True, blank=True)

    electricity_used_t2_start = models.FloatField(null=True, blank=True)
    electricity_used_t2_w = models.FloatField(null=True, blank=True)
    electricity_used_t2_wo = models.FloatField(null=True, blank=True)


class MacroInputType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class InputType(models.Model):
    macro_input_type = models.ForeignKey(MacroInputType, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    has_co2_emissions = models.BooleanField(default=False)
    has_n2o_emissions = models.BooleanField(default=False)
    has_co2_e_emissions = models.BooleanField(default=False)

    class Meta:
        unique_together = ("macro_input_type", "name")

    def __str__(self):
        return f"({self.id}) {self.name}"


class Input(Module):
    pass


class InputEntry(Submodule):
    parent = models.ForeignKey(Input, on_delete=models.CASCADE, related_name="input_entries")
    input_type = models.ForeignKey(InputType, on_delete=models.CASCADE)

    value_start = models.FloatField()
    value_w = models.FloatField()
    value_wo = models.FloatField()
    value_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_value_thread")

    co2_emissions_t2 = models.FloatField(null=True, blank=True)
    n2o_emissions_t2 = models.FloatField(null=True, blank=True)
    co2_e_emissions_t2 = models.FloatField(null=True, blank=True)

    implementation_year_t2 = models.IntegerField(null=True, blank=True)


class EmissionFactorSource(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class Energy(Module):
    pass


class Electricity(Submodule):
    parent = models.ForeignKey(Energy, on_delete=models.CASCADE, null=True, blank=True, related_name="electricities")
    country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)

    mwh_start = models.FloatField(null=True, blank=True)
    mwh_w = models.FloatField(null=True, blank=True)
    mwh_wo = models.FloatField(null=True, blank=True)
    mwh_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_mwh_thread")

    mwh_renewables_start = models.FloatField(null=True, blank=True)
    mwh_renewables_w = models.FloatField(null=True, blank=True)
    mwh_renewables_wo = models.FloatField(null=True, blank=True)
    mwh_renewables_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_mwh_renewables_thread")

    ef_t2 = models.FloatField(null=True, blank=True)
    transmission_loss = models.FloatField(default=0.1)
    ef_source = models.ForeignKey(EmissionFactorSource, on_delete=models.CASCADE, null=True, blank=True)


class Fuel(Submodule):
    parent = models.ForeignKey(Energy, on_delete=models.CASCADE, null=True, blank=True, related_name="fuels")
    fuel_type = models.ForeignKey(FuelType, on_delete=models.CASCADE, null=True, blank=True)

    fuel_consumption_start = models.FloatField(null=True, blank=True)
    fuel_consumption_w = models.FloatField(null=True, blank=True)
    fuel_consumption_wo = models.FloatField(null=True, blank=True)
    fuel_consumption_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fuel_consumption_thread")

    ef_t2 = models.FloatField(null=True, blank=True)
    account_for_co2 = models.BooleanField(default=False)


class IrrigationSystemType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class EnergySourceType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class Irrigation(Module):
    pass


class IrrigationSystem(Submodule):
    parent = models.ForeignKey(Irrigation, on_delete=models.CASCADE, null=True, blank=True, related_name="irrigation_systems")
    irrigation_system_type = models.ForeignKey(IrrigationSystemType, on_delete=models.CASCADE, null=True, blank=True, related_name="irrigation_systems")

    ha_start = models.FloatField(null=True, blank=True)
    ha_w = models.FloatField(null=True, blank=True)
    ha_wo = models.FloatField(null=True, blank=True)
    ha_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_ha_thread")

    ef_t2_start = models.FloatField(null=True, blank=True)
    ef_t2_w = models.FloatField(null=True, blank=True)
    ef_t2_wo = models.FloatField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.irrigation and self.irrigation_phases:
            raise exceptions.ValidationError("Cannot have both irrigation system and irrigation phases in the same irrigation module")
        super().save(*args, **kwargs)


class IrrigationPhase(Submodule):
    parent = models.ForeignKey(Irrigation, on_delete=models.CASCADE, null=True, blank=True, related_name="irrigation_phases")
    irrigation_system_type = models.ForeignKey(IrrigationSystemType, on_delete=models.CASCADE, null=True, blank=True, related_name="irrigation_phases")
    fuel_type = models.ForeignKey(FuelType, on_delete=models.CASCADE, null=True, blank=True)
    well_depth = models.FloatField(null=True, blank=True)

    ha_start = models.FloatField(null=True, blank=True)
    ha_w = models.FloatField(null=True, blank=True)
    ha_wo = models.FloatField(null=True, blank=True)
    ha_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_ha_thread")

    gross_irrigation_water_start = models.FloatField(null=True, blank=True)
    gross_irrigation_water_w = models.FloatField(null=True, blank=True)
    gross_irrigation_water_wo = models.FloatField(null=True, blank=True)
    gross_irrigation_water_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gross_irrigation_water_thread")

    power_origin_country_t2 = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)
    ef_t2_start = models.FloatField(null=True, blank=True)
    ef_t2_w = models.FloatField(null=True, blank=True)
    ef_t2_wo = models.FloatField(null=True, blank=True)

    transmission_loss_t2_start = models.FloatField(null=True, blank=True)
    transmission_loss_t2_w = models.FloatField(null=True, blank=True)
    transmission_loss_t2_wo = models.FloatField(null=True, blank=True)

    average_pressure_t2 = models.FloatField(null=True, blank=True)

    total_dynamic_head_t2 = models.FloatField(null=True, blank=True)

    pumping_efficiency_t2_start = models.FloatField(null=True, blank=True)
    pumping_efficiency_t2_w = models.FloatField(null=True, blank=True)
    pumping_efficiency_t2_wo = models.FloatField(null=True, blank=True)


class BuildingType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class RoadType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class Building(Submodule):
    parent = models.ForeignKey("api.Settlement", on_delete=models.CASCADE, null=True, blank=True, related_name="buildings")

    building_type_start = models.ForeignKey(BuildingType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_building_type_start")
    building_type_w = models.ForeignKey(BuildingType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_building_type_w")
    building_type_wo = models.ForeignKey(BuildingType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_building_type_wo")
    building_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_building_type_thread", on_delete=models.SET_NULL)

    area_m2_start = models.FloatField(null=True, blank=True)
    area_m2_w = models.FloatField(null=True, blank=True)
    area_m2_wo = models.FloatField(null=True, blank=True)
    area_m2_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_surface_thread", on_delete=models.SET_NULL)

    ef_t2_start = models.FloatField(null=True, blank=True)
    ef_t2_w = models.FloatField(null=True, blank=True)
    ef_t2_wo = models.FloatField(null=True, blank=True)


class Road(Submodule):
    parent = models.ForeignKey("api.Settlement", on_delete=models.CASCADE, null=True, blank=True, related_name="roads")

    road_type_start = models.ForeignKey(RoadType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_road_type_start")
    road_type_w = models.ForeignKey(RoadType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_road_type_w")
    road_type_wo = models.ForeignKey(RoadType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_road_type_wo")
    road_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_road_type_thread", on_delete=models.SET_NULL)

    length_km_start = models.FloatField(null=True, blank=True)
    length_km_w = models.FloatField(null=True, blank=True)
    length_km_wo = models.FloatField(null=True, blank=True)
    length_km_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_length_km_thread", on_delete=models.SET_NULL)

    width_m_start = models.FloatField(null=True, blank=True)
    width_m_w = models.FloatField(null=True, blank=True)
    width_m_wo = models.FloatField(null=True, blank=True)
    width_m_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_width_m_thread", on_delete=models.SET_NULL)

    ef_t2_start = models.FloatField(null=True, blank=True)
    ef_t2_w = models.FloatField(null=True, blank=True)
    ef_t2_wo = models.FloatField(null=True, blank=True)


class OtherInfrastructure(Submodule):
    parent = models.ForeignKey("api.Settlement", on_delete=models.CASCADE, null=True, blank=True, related_name="other_infrastructures")

    area_m2_start = models.FloatField(null=True, blank=True)
    area_m2_w = models.FloatField(null=True, blank=True)
    area_m2_wo = models.FloatField(null=True, blank=True)
    area_m2_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_area_m2_thread", on_delete=models.SET_NULL)

    ef_t2_start = models.FloatField(null=True, blank=True)
    ef_t2_w = models.FloatField(null=True, blank=True)
    ef_t2_wo = models.FloatField(null=True, blank=True)


class OrganicSoil(LandModuleFixed):
    drainage_area_start = models.FloatField(null=True, blank=True)
    drainage_area_w = models.FloatField(null=True, blank=True)
    drainage_area_wo = models.FloatField(null=True, blank=True)
    drainage_area_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_drainage_area_thread", on_delete=models.SET_NULL)

    area_not_drained_start = models.FloatField(null=True, blank=True)
    area_not_drained_w = models.FloatField(null=True, blank=True)
    area_not_drained_wo = models.FloatField(null=True, blank=True)
    area_not_drained_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_area_not_drained_thread", on_delete=models.SET_NULL)

    ditches_area_start = models.FloatField(null=True, blank=True)
    ditches_area_w = models.FloatField(null=True, blank=True)
    ditches_area_wo = models.FloatField(null=True, blank=True)
    ditches_area_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_ditches_area_thread", on_delete=models.SET_NULL)

    fire_type_start = models.ForeignKey(FireType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fire_type_start")
    fire_type_w = models.ForeignKey(FireType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fire_type_w")
    fire_type_wo = models.ForeignKey(FireType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fire_type_wo")
    fire_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_fire_type_thread", on_delete=models.SET_NULL)

    soil_fire_periodicity_start = models.FloatField(null=True, blank=True)
    soil_fire_periodicity_w = models.FloatField(null=True, blank=True)
    soil_fire_periodicity_wo = models.FloatField(null=True, blank=True)
    soil_fire_periodicity_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_soil_fire_periodicity_thread", on_delete=models.SET_NULL)

    soil_fire_impact_percentage_start = models.FloatField(null=True, blank=True)
    soil_fire_impact_percentage_w = models.FloatField(null=True, blank=True)
    soil_fire_impact_percentage_wo = models.FloatField(null=True, blank=True)
    soil_fire_impact_percentage_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_soil_fire_impact_percentage_thread", on_delete=models.SET_NULL)

    onsite_co2_drainge_t2_start = models.FloatField(null=True, blank=True)
    onsite_co2_drainge_t2_w = models.FloatField(null=True, blank=True)
    onsite_co2_drainge_t2_wo = models.FloatField(null=True, blank=True)

    onsite_ch4_drainge_t2_start = models.FloatField(null=True, blank=True)
    onsite_ch4_drainge_t2_w = models.FloatField(null=True, blank=True)
    onsite_ch4_drainge_t2_wo = models.FloatField(null=True, blank=True)

    onsite_n2o_drainge_t2_start = models.FloatField(null=True, blank=True)
    onsite_n2o_drainge_t2_w = models.FloatField(null=True, blank=True)
    onsite_n2o_drainge_t2_wo = models.FloatField(null=True, blank=True)

    offsite_doc_drainge_t2_start = models.FloatField(null=True, blank=True)
    offsite_doc_drainge_t2_w = models.FloatField(null=True, blank=True)
    offsite_doc_drainge_t2_wo = models.FloatField(null=True, blank=True)

    offsite_ch4_drainge_t2_start = models.FloatField(null=True, blank=True)
    offsite_ch4_drainge_t2_w = models.FloatField(null=True, blank=True)
    offsite_ch4_drainge_t2_wo = models.FloatField(null=True, blank=True)

    onsite_co2_rewetting_t2_start = models.FloatField(null=True, blank=True)
    onsite_co2_rewetting_t2_w = models.FloatField(null=True, blank=True)
    onsite_co2_rewetting_t2_wo = models.FloatField(null=True, blank=True)

    onsite_ch4_rewetting_t2_start = models.FloatField(null=True, blank=True)
    onsite_ch4_rewetting_t2_w = models.FloatField(null=True, blank=True)
    onsite_ch4_rewetting_t2_wo = models.FloatField(null=True, blank=True)

    onsite_n2o_rewetting_t2_start = models.FloatField(null=True, blank=True)
    onsite_n2o_rewetting_t2_w = models.FloatField(null=True, blank=True)
    onsite_n2o_rewetting_t2_wo = models.FloatField(null=True, blank=True)

    offsite_doc_rewetting_t2_start = models.FloatField(null=True, blank=True)
    offsite_doc_rewetting_t2_w = models.FloatField(null=True, blank=True)
    offsite_doc_rewetting_t2_wo = models.FloatField(null=True, blank=True)

    mean_dry_matter_t2_start = models.FloatField(null=True, blank=True)
    mean_dry_matter_t2_w = models.FloatField(null=True, blank=True)
    mean_dry_matter_t2_wo = models.FloatField(null=True, blank=True)

    fire_on_soil_co2_t2_start = models.FloatField(null=True, blank=True)
    fire_on_soil_co2_t2_w = models.FloatField(null=True, blank=True)
    fire_on_soil_co2_t2_wo = models.FloatField(null=True, blank=True)

    fire_on_soil_co_t2_start = models.FloatField(null=True, blank=True)
    fire_on_soil_co_t2_w = models.FloatField(null=True, blank=True)
    fire_on_soil_co_t2_wo = models.FloatField(null=True, blank=True)

    fire_on_soil_ch4_t2_start = models.FloatField(null=True, blank=True)
    fire_on_soil_ch4_t2_w = models.FloatField(null=True, blank=True)
    fire_on_soil_ch4_t2_wo = models.FloatField(null=True, blank=True)

    ##### Peat Extraction #####

    peat_type_start = models.ForeignKey(PeatType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_peat_type_start")
    peat_type_w = models.ForeignKey(PeatType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_peat_type_w")
    peat_type_wo = models.ForeignKey(PeatType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_peat_type_wo")
    peat_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_type_thread", on_delete=models.SET_NULL)

    peat_area_start = models.FloatField(null=True, blank=True)
    peat_area_w = models.FloatField(null=True, blank=True)
    peat_area_wo = models.FloatField(null=True, blank=True)
    peat_area_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_area_thread", on_delete=models.SET_NULL)

    peat_ditches_area_start = models.FloatField(null=True, blank=True)
    peat_ditches_area_w = models.FloatField(null=True, blank=True)
    peat_ditches_area_wo = models.FloatField(null=True, blank=True)
    peat_ditches_area_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_ditches_area_thread", on_delete=models.SET_NULL)

    peat_extraction_height_start = models.FloatField(null=True, blank=True)
    peat_extraction_height_w = models.FloatField(null=True, blank=True)
    peat_extraction_height_wo = models.FloatField(null=True, blank=True)
    peat_extraction_height_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_extraction_height_thread", on_delete=models.SET_NULL)

    is_peat_for_energy_start = models.BooleanField(default=False)
    is_peat_for_energy_w = models.BooleanField(default=False)
    is_peat_for_energy_wo = models.BooleanField(default=False)
    is_peat_for_energy_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_is_for_energy_thread", on_delete=models.SET_NULL)

    onsite_co2_peat_t2 = models.FloatField(null=True, blank=True)
    onsite_ch4_peat_t2 = models.FloatField(null=True, blank=True)
    onsite_n2o_peat_t2 = models.FloatField(null=True, blank=True)
    offsite_doc_peat_t2 = models.FloatField(null=True, blank=True)
    offsite_ch4_peat_t2 = models.FloatField(null=True, blank=True)

    peat_density_t2 = models.FloatField(null=True, blank=True)


class Settlement(LandModuleFixed):

    is_settlement_start = models.BooleanField(default=False)
    is_settlement_w = models.BooleanField(default=False)
    is_settlement_wo = models.BooleanField(default=False)

    soil_carbon_t2_start = models.FloatField(null=True, blank=True)
    soil_carbon_t2_w = models.FloatField(null=True, blank=True)
    soil_carbon_t2_wo = models.FloatField(null=True, blank=True)

    flu_t2_start = models.FloatField(null=True, blank=True)
    flu_t2_w = models.FloatField(null=True, blank=True)
    flu_t2_wo = models.FloatField(null=True, blank=True)

    agb_t2_start = models.FloatField(null=True, blank=True)
    agb_t2_w = models.FloatField(null=True, blank=True)
    agb_t2_wo = models.FloatField(null=True, blank=True)

    bgb_t2_start = models.FloatField(null=True, blank=True)
    bgb_t2_w = models.FloatField(null=True, blank=True)
    bgb_t2_wo = models.FloatField(null=True, blank=True)


class SetAside(LandModule, DoubleBiomassModule):

    is_set_aside_start = models.BooleanField(default=False)
    is_set_aside_w = models.BooleanField(default=False)
    is_set_aside_wo = models.BooleanField(default=False)


class DegradedLand(LandModule, SingleBiomassModule):
    ha_start = models.FloatField(null=True, blank=True)
    ha_w = models.FloatField(null=True, blank=True)
    ha_wo = models.FloatField(null=True, blank=True)

    is_degraded_land_start = models.BooleanField(default=False)
    is_degraded_land_w = models.BooleanField(default=False)
    is_degraded_land_wo = models.BooleanField(default=False)

    soc_t2_start = models.FloatField(null=True, blank=True)
    soc_t2_w = models.FloatField(null=True, blank=True)
    soc_t2_wo = models.FloatField(null=True, blank=True)

    flu_t2_start = models.FloatField(null=True, blank=True)
    flu_t2_w = models.FloatField(null=True, blank=True)
    flu_t2_wo = models.FloatField(null=True, blank=True)

    agb_t2_start = models.FloatField(null=True, blank=True)
    agb_t2_w = models.FloatField(null=True, blank=True)
    agb_t2_wo = models.FloatField(null=True, blank=True)

    bgb_t2_start = models.FloatField(null=True, blank=True)
    bgb_t2_w = models.FloatField(null=True, blank=True)
    bgb_t2_wo = models.FloatField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name="Degraded Land")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        super().save(*args, **kwargs)


class LandUseChange(Module):
    module_type_start = models.ForeignKey(ModuleType, on_delete=models.CASCADE, related_name="start")
    module_type_w = models.ForeignKey(ModuleType, on_delete=models.CASCADE, related_name="w")
    module_type_wo = models.ForeignKey(ModuleType, on_delete=models.CASCADE, related_name="wo")
    module_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="land_use_change_module_type_thread")

    area = models.FloatField()

    is_fire_used_start = models.BooleanField(default=False)
    is_fire_used_w = models.BooleanField(default=False)
    is_fire_used_wo = models.BooleanField(default=False)
    is_fire_used_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="land_use_change_is_fire_used_thread")

    dry_matter_start = models.FloatField(null=True, blank=True)
    dry_matter_w = models.FloatField(null=True, blank=True)
    dry_matter_wo = models.FloatField(null=True, blank=True)
    dry_matter_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="land_use_change_dry_matter_thread")

    def is_filled(self):
        return self.area is not None and self.module_type_start is not None and self.module_type_w is not None and self.module_type_wo is not None


### MODEL PARAMETERS TABLES ###


class Parameter(models.Model):
    class Meta:
        abstract = True

    name = models.CharField(max_length=255, unique=True)
    value = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=255, null=True, blank=True)

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


class FundingAgency(models.Model):
    name = models.CharField(max_length=255, unique=True)
    abbreviation = models.CharField(max_length=255, unique=True, null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ExecutingAgency(models.Model):
    name = models.CharField(max_length=255, unique=True)
    abbreviation = models.CharField(max_length=255, unique=True, null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"
