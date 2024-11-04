import uuid
from abc import abstractmethod

from django.contrib.auth import models as auth_models
from django.core import exceptions, validators
from django.db import models as models
from django.utils import timezone
from simple_history.models import HistoricalRecords
import logging as log
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

from api import utilities as utils
import ipcc.models as ipcc

from django.utils.translation import gettext_lazy as _
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes
from dirtyfields import DirtyFieldsMixin
from django.utils.text import slugify


alphanumeric = validators.RegexValidator(r"^[0-9a-zA-Z]*$", "Only alphanumeric characters are allowed.")
letters_only = validators.RegexValidator(r"^[a-zA-Z]*$", "Only letters are allowed.")
capitalized = validators.RegexValidator(r"[A-Z][a-z]*(\s[A-Z][a-z]*)*", "Only capitalized words are allowed.")
pc_as_float = validators.RegexValidator(r"^[0-1]*\.?[0-9]*$", "Only correctly formatted percentages are allowed.")

RICE_CULTIVATION_DAYS = 113


# Create your models here.
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import RegexValidator
import threading

alphanumeric = RegexValidator(r"^[0-9a-zA-Z]*$", "Only alphanumeric characters are allowed.")


class InvitationStatusType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        # username = email  # Automatically set username as email
        # user = self.model(email=email, username=username, **extra_fields)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    country = models.ForeignKey("api.Country", on_delete=models.CASCADE, null=True, blank=True, related_name="users")
    email = models.EmailField(unique=True)
    username = None
    organization = models.CharField(max_length=255, null=True, blank=True)
    firebase_uid = models.CharField(max_length=255, unique=True, validators=[alphanumeric], null=True, blank=True, verbose_name="Firebase UID")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()
    history = HistoricalRecords(cascade_delete_history=True)

    class Meta:
        permissions = (
            ("can_view_modules", "Can view modules"),
            ("can_add_modules", "Can add modules"),
            ("can change_modules", "Can change modules"),
            ("can delete_modules", "Can delete modules"),
        )

    def __str__(self):
        return f"({self.pk}) {self.email}"


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
        value_lower = self.value.lower().strip()
        if value_lower == "true":
            return True
        elif value_lower == "false":
            return False

        try:
            if "%" in value_lower:
                return float(value_lower.replace("%", "")) / 100
            elif "." in value_lower:
                return float(value_lower)
            else:
                return int(value_lower)
        except ValueError:
            return self.value

    class Meta:
        verbose_name_plural = "Configuration parameters"


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
        return f"({self.pk}) {self.author.email}: {self.content[:40]}..."


class IPCCRegion(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class GasType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class GLEAMRegion(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class ForestType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class ForestConditionType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


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
        return self.name


class SettlementType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


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
        return self.name


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True, blank=True, related_name="countries")
    ipcc_region = models.ForeignKey(IPCCRegion, on_delete=models.CASCADE, null=True, blank=True, related_name="countries")
    gleam_region = models.ForeignKey(GLEAMRegion, on_delete=models.CASCADE, null=True, blank=True, related_name="countries")

    class Meta:
        verbose_name_plural = "Countries"

    def __str__(self):
        return self.name


class Climate(models.Model):
    name = models.CharField(max_length=100)
    moistures = models.ManyToManyField("api.Moisture", related_name="climates")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Moisture(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class SoilType(models.Model):
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ExtractionSoilType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class TillageType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class OrganicInputType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


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
        return self.name


class WaterManagementTypeBeforeCultivation(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class WaterManagementTypeAfterCultivation(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class GrasslandManagementType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class LivestockCategoryType(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class LivestockProductionType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class ManureManagementType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class ModuleType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    class_name = models.CharField(max_length=255, null=True, blank=True)
    is_luc = models.BooleanField(default=False)
    is_submodule = models.BooleanField(default=False)
    is_container = models.BooleanField(default=False)

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
        return self.name


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
        return self.name


class LargeFisheryGearType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class SmallFisheryGearType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class FishType(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class MacroFuelType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class FuelUseType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class FuelType(models.Model):
    name = models.CharField(max_length=100)
    fuel_use_type = models.ForeignKey(FuelUseType, on_delete=models.CASCADE, null=True, blank=True)
    macro_fuel_type = models.ForeignKey(MacroFuelType, on_delete=models.CASCADE, null=True, blank=True)
    module_types = models.ManyToManyField(ModuleType, related_name="fuel_types")

    class Meta:
        unique_together = ("name", "fuel_use_type", "macro_fuel_type")

    def __str__(self):
        macro = getattr(self.macro_fuel_type, "name", None)
        use = getattr(self.fuel_use_type, "name", None)
        return self.name


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
    history = HistoricalRecords(inherit=True, related_name="%(class)s_history", cascade_delete_history=True)

    class Meta:
        abstract = True


class Project(Historical, DirtyFieldsMixin):
    class Meta:
        verbose_name_plural = "Projects"
        unique_together = ("name", "owner")
        ordering = ["-id"]  # Orders by created_at descending

    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="projects", verbose_name=_("owner"))
    date = models.DateTimeField(null=True, blank=True, verbose_name=_("date"))
    name = models.CharField(max_length=100, verbose_name=_("name"))
    code = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("code"))
    cost = models.FloatField(null=True, blank=True, verbose_name=_("cost"))
    funding_agency = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("funding_agency"))
    executing_agency = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("executing_agency"))
    status = models.ForeignKey(ProjectStatus, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("status"))

    implementation_years = models.IntegerField(verbose_name=_("implementation_years"))
    start_year_of_activities = models.IntegerField(verbose_name=_("start_year_of_activities"))
    last_year_of_accounting = models.IntegerField(verbose_name=_("last_year_of_accounting"))

    country = models.ForeignKey(Country, on_delete=models.CASCADE, verbose_name=_("country"))
    climate = models.ForeignKey(Climate, on_delete=models.CASCADE, verbose_name=_("climate"))
    moisture = models.ForeignKey(Moisture, on_delete=models.CASCADE, verbose_name=_("moisture"))
    soil_type = models.ForeignKey(SoilType, on_delete=models.CASCADE, verbose_name=_("soil_type"))

    is_locked = models.BooleanField(default=False, verbose_name=_("is_locked"))
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name=_("locked_at"))
    lock_updated_at = models.DateTimeField(null=True, blank=True, verbose_name=_("lock_updated_at"))
    locked_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name="locked_projects", verbose_name=_("locked_by"))

    gw_potential = models.ForeignKey("ipcc.GlobalWarmingPotential", on_delete=models.CASCADE, verbose_name=_("gw_potential"))

    gwp_co2_t2 = models.FloatField(null=True, blank=True, verbose_name=_("gwp_co2_t2"))
    gwp_ch4_t2 = models.FloatField(null=True, blank=True, verbose_name=_("gwp_ch4_t2"))
    gwp_n2o_t2 = models.FloatField(null=True, blank=True, verbose_name=_("gwp_n2o_t2"))
    gwp_ch4_fossil_t2 = models.FloatField(null=True, blank=True, verbose_name=_("gwp_ch4_fossil_t2"))

    soc_ref_t2 = models.FloatField(null=True, blank=True, verbose_name=_("soc_ref_t2"))

    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name=_("created_at"))
    updated_at = models.DateTimeField(auto_now=True, null=True, verbose_name=_("updated_at"))

    @property
    def capitalization_years(self) -> int:
        return self.__get_capitalization_years()

    def save(self, *args, **kwargs):
        if self.pk:
            old = Project.objects.get(pk=self.pk)
            if old.owner != self.owner:
                raise exceptions.ValidationError("User cannot be changed")

            if self.is_dirty(check_relationship=True):
                dirty_fields = self.get_dirty_fields(check_relationship=True)
                exclude_fields = ["is_locked", "locked_at", "lock_updated_at", "locked_by", "updated_at"]

                threads: list[threading.Thread] = []

                if any(field.name in dirty_fields.keys() for field in self._meta.get_fields() if field.name not in exclude_fields):
                    for activity in self.activities.all():
                        activity: Activity
                        for module in activity.modules:
                            module: Module
                            threads.append(threading.Thread(target=module.invalidate_cached_results))

                for thread in threads:
                    thread.start()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"({self.pk}) {self.name}"

    def is_ready(self):
        for activity in self.activities.all():
            for module in activity.modules:
                if not module.is_ready():
                    return False
        return True

    def lock(self, user: CustomUser):
        self.is_locked = True
        self.locked_at = timezone.now()
        self.lock_updated_at = self.locked_at
        self.locked_by = user
        self.save()

    def unlock(self):
        self.is_locked = False
        self.locked_at = None
        self.lock_updated_at = None
        self.locked_by = None
        self.save()

    def refresh_lock(self):
        self.lock_updated_at = timezone.now()
        self.save()

    def __get_capitalization_years(self):
        if any([self.last_year_of_accounting is None, self.start_year_of_activities is None, self.implementation_years is None]):
            raise exceptions.ValidationError("Error calculating project capitalization period. Capitalization years, start year of activities, and implementation years must be set")

        return self.last_year_of_accounting - (self.start_year_of_activities + self.implementation_years)

    @property
    def gwp(self):
        self.gw_potential: ipcc.GlobalWarmingPotential

        # NOTE: Fossil CH4 is not required but is used conditionally in the calculations. The specific case is handled in the calculations where needed.
        # NOTE: Also, maybe this should be handle mathematical model-side as any other tier2 value.
        if self.gw_potential.co2 is None and self.gwp_co2_t2 is None:
            raise exceptions.ValidationError("Missing data for Global Warming Potential (CO2). Please provide tier2 value.")
        if self.gw_potential.ch4 is None and self.gwp_ch4_t2 is None:
            raise exceptions.ValidationError("Missing data for Global Warming Potential (CH4). Please provide tier2 value.")
        if self.gw_potential.n2o is None and self.gwp_n2o_t2 is None:
            raise exceptions.ValidationError("Missing data for Global Warming Potential (N2O). Please provide tier2 value.")

        if self.gwp_co2_t2 is not None:
            self.gw_potential.co2 = self.gwp_co2_t2

        if self.gwp_ch4_t2 is not None:
            self.gw_potential.ch4 = self.gwp_ch4_t2

        if self.gwp_n2o_t2 is not None:
            self.gw_potential.n2o = self.gwp_n2o_t2

        if self.gwp_ch4_fossil_t2 is not None:
            self.gw_potential.ch4_fossil = self.gwp_ch4_fossil_t2

        return self.gw_potential


class ProjectTag(models.Model):
    class Meta:
        verbose_name_plural = "Project Tags"
        unique_together = ("name", "slug", "user", "project")

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tags")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        return super().save(*args, **kwargs)


class ProjectInvitation(Historical):
    STATUS_CHOICES = (("sent", "Sent"), ("accepted", "Accepted"), ("declined", "Declined"))

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="invitations")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="invitations")
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    status = models.ForeignKey(InvitationStatusType, on_delete=models.CASCADE)

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    token_expiry = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = (("project", "user", "group"),)

    def save(self, *args, **kwargs):
        if not self.token_expiry:
            self.token_expiry = timezone.now() + timezone.timedelta(days=3)  # Token valid for 3 days

        super().save(*args, **kwargs)

    def __str__(self):
        return f"({self.pk}) {self.project.name} - {self.user.email}"


class ProjectMembership(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="memberships")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    def __str__(self):
        return f"({self.pk}) {self.project.name} - {self.user.email} - {self.group.name}"


##############################
######### Activity ###########
##############################


class Note(Historical):
    content = models.TextField()
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    @property
    def parent(self):
        return self.content_object

    @property
    def project(self):
        match self.content_object.__class__.__name__:
            case "Project":
                return self.content_object
            case "Activity":
                return self.content_object.project
            case "Module":
                return self.content_object.activity.project
            case "Submodule":
                return self.content_object.parent.activity.project

    def __str__(self):
        return f"({self.pk}) {self.author.email}: {self.content[:40]}..."


class NoteMixin(models.Model):
    note = GenericRelation(Note)

    class Meta:
        abstract = True


class Activity(Historical, NoteMixin, DirtyFieldsMixin):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activities", verbose_name=_("project"))
    name = models.CharField(max_length=255, verbose_name=_("name"))
    description = models.TextField(null=True, blank=True, verbose_name=_("description"))
    cost = models.FloatField(default=0, verbose_name=_("cost"))

    change_rate = models.ForeignKey(ChangeRate, on_delete=models.CASCADE, related_name="activities", null=True, blank=True, verbose_name=_("change_rate"))
    module_types = models.ManyToManyField("api.ModuleType", related_name="activities", verbose_name=_("module_types"))

    climate_t2 = models.ForeignKey(Climate, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("climate_t2"))
    moisture_t2 = models.ForeignKey(Moisture, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("moisture_t2"))
    soil_type_t2 = models.ForeignKey(SoilType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("soil_type_t2"))
    duration_t2 = models.IntegerField(null=True, blank=True, verbose_name=_("duration_t2"))
    start_year_t2 = models.IntegerField(null=True, blank=True, verbose_name=_("start_year_t2"))
    soc_t2 = models.FloatField(null=True, blank=True, verbose_name=_("soc_t2"))

    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name=_("created_at"))
    updated_at = models.DateTimeField(auto_now=True, null=True, verbose_name=_("updated_at"))
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="activities", null=True, blank=True, verbose_name=_("owner"))

    @property
    def implementation_years(self) -> int:
        return self.__get_duration()

    @property
    def capitalization_years(self) -> int:
        return self.__get_capitalization_years()

    @property
    def delay(self) -> int:
        return self.__get_delay()

    @property
    def modules(self) -> list["Module"]:
        return self.__get_all_modules()

    @property
    def status(self):
        return self.__get_status()

    @property
    def completion_percentage(self):
        return self.__calculate_completion_percentage()

    class Meta:
        unique_together = ("name", "project")
        ordering = ["-created_at"]  # Orders by created_at descending

    def get_land_modules_area(self) -> float:
        for module in self.modules:
            if isinstance(module, LandModule) and module.area is not None:
                return module.area
        return 0

    def __str__(self):
        return f"({self.pk}) {self.name} in {self.project.name}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.state = StatusType.objects.get_or_create(name_en="EMPTY")[0]
            if not self.change_rate:
                self.change_rate = ChangeRate.objects.get_or_create(name="linear")[0]
        if self.pk:
            if self.is_dirty(check_relationship=True):
                dirty_fields = self.get_dirty_fields(check_relationship=True)
                exclude_fields = ["cost", "description", "name", "owner", "updated_at"]

                if any(field.name in dirty_fields.keys() for field in self._meta.get_fields() if field.name not in exclude_fields):
                    for module in self.modules:
                        module.invalidate_cached_results()
        super().save(*args, **kwargs)

    def __get_delay(self) -> int:
        if self.start_year_t2 is None:
            return 0

        return self.start_year_t2 - self.project.start_year_of_activities

    def __get_duration(self) -> int:
        if self.duration_t2 is None or self.duration_t2 == 0:
            return self.project.implementation_years

        return self.duration_t2

    def __get_capitalization_years(self) -> int:
        if any([self.start_year_t2 is None, self.start_year_t2 == 0, self.duration_t2 is None, self.duration_t2 == 0]):
            return self.project.capitalization_years

        return self.project.last_year_of_accounting - (self.start_year_t2 + self.duration_t2)

    def __get_all_modules(self):
        module_types = self.module_types.all()
        modules = []

        for module_type in module_types:
            modules.extend(getattr(self, module_type.class_name.lower()).all())

        return modules

    def __calculate_completion_percentage(self):
        """
        Calculates the completion percentage of an activity.

        Args:
        activity (Activity): The activity object to update.
        """
        statuses = [module.status for module in self.modules]

        ready_count = statuses.count(StatusType.objects.get(name_en="READY"))

        if len(statuses) == 0:
            return 1

        percentage_complete = ready_count / len(statuses)

        return percentage_complete

    # TODO: Maybe persist on database and add a signal to update the status of the activity on module save
    def __get_status(self):
        are_modules_ready = all([module.is_ready() for module in self.modules])
        is_any_module_ready = any([module.is_ready() for module in self.modules])

        if are_modules_ready:
            return StatusType.objects.get(name_en="READY")
        elif is_any_module_ready:
            return StatusType.objects.get(name_en="IN PROGRESS")
        else:
            return StatusType.objects.get(name_en="EMPTY")


##############################
########## Modules ###########
##############################


class CachedResultMixin(models.Model, DirtyFieldsMixin):
    class Meta:
        abstract = True

    updated_at = models.DateTimeField(auto_now=True, null=True, verbose_name=_("updated_at"))
    last_cached_at = models.DateTimeField(null=True, blank=True, verbose_name=_("last_cached_at"))
    cached_results_total = models.JSONField(null=True, blank=True, verbose_name=_("cached_results_total"))
    cached_results_by_activity = models.JSONField(null=True, blank=True, verbose_name=_("cached_results_total"))
    cached_results_by_gas = models.JSONField(null=True, blank=True, verbose_name=_("cached_results_total"))
    cached_results_by_activity_by_gas = models.JSONField(null=True, blank=True, verbose_name=_("cached_results_total"))
    last_modified = models.DateTimeField(auto_now=False, null=True, blank=True, verbose_name=_("last_modified"))

    def save(self, *args, **kwargs):
        if self.last_modified is None:
            self.last_modified = timezone.now()

        if self.pk and self.is_dirty(check_relationship=True):
            dirty_fields = self.get_dirty_fields(check_relationship=True)
            cache_fields = ["last_cached_at", "cached_results_total", "cached_results_by_activity", "cached_results_by_gas", "cached_results_by_activity_by_gas"]

            if any(field.name in dirty_fields.keys() for field in self._meta.get_fields() if field.name not in cache_fields):
                self.last_modified = timezone.now()

        if isinstance(self, Submodule):
            parent: Module = self.parent
            parent.invalidate_cached_results()

        super().save(*args, **kwargs)

    def cache_results(self, balance: dict, by_activity: dict, by_gas: dict, by_activity_by_gas: dict):
        self.last_cached_at = timezone.now()
        self.cached_results_total = balance
        self.cached_results_by_activity = by_activity
        self.cached_results_by_gas = by_gas
        self.cached_results_by_activity_by_gas = by_activity_by_gas
        self.save()

    def invalidate_cached_results(self):
        self.last_cached_at = None
        self.cached_results_total = None
        self.cached_results_by_activity = None
        self.cached_results_by_gas = None
        self.cached_results_by_activity_by_gas = None
        if isinstance(self, Submodule):
            parent: Module = self.parent
            parent.invalidate_cached_results()
        self.save()

    def is_cached_results_valid(self):
        return self.last_cached_at is not None and self.last_cached_at > self.last_modified

    def get_cached_results(self, by=BreakdownTypes.TOTAL):
        if self.is_cached_results_valid():
            if by == BreakdownTypes.TOTAL:
                return self.cached_results_total
            elif by == BreakdownTypes.ACTIVITY:
                return self.cached_results_by_activity
            elif by == BreakdownTypes.GAS:
                return self.cached_results_by_gas
            elif by == BreakdownTypes.ACTIVITY_GAS:
                return self.cached_results_by_activity_by_gas
        return None

    def invalidate_luc_results(self):
        # NOTE: If the module is associated with a land use change, invalidate the cached results of the land use change.
        # NOTE: This is necessary because the calculations for modules with a land use change reference other modules (mostly tier2s) that may have been updated, which would invalidate the results.
        luc: LandUseChange = self.land_use_change
        luc_modules = luc.get_modules()
        for module in luc_modules:
            module.invalidate_cached_results()

    def delete(self, *args, **kwargs):
        if isinstance(self, Submodule):
            parent: Module = self.parent
            parent.invalidate_cached_results()
        super().delete(*args, **kwargs)


class Submodule(Historical, CachedResultMixin):
    soc_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("soc_t2_start"))
    soc_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("soc_t2_w"))
    soc_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("soc_t2_wo"))
    status = models.ForeignKey(StatusType, on_delete=models.CASCADE, null=True, blank=True)
    note = GenericRelation("api.Note")

    class Meta:
        abstract = True

    @property
    def module_type(self):
        return ModuleType.objects.get(class_name=self.__class__.__name__)

    @property
    def project(self):
        return self.parent.activity.project

    @property
    def threads(self):
        return self.__get_threads()

    def save(self, *args, **kwargs):
        if not self.parent:
            raise exceptions.ValidationError("Submodule must have a parent field specified in the model")

        if not self.status:
            self.status = StatusType.objects.get_or_create(name_en="EMPTY")[0]

        if not self.pk:
            utils.create_comment_threads(self)

        super().save(*args, **kwargs)

    def is_ready(self) -> bool:
        return self.status and self.status.name_en == "READY"

    def is_start(self) -> bool:
        return self.parent.is_start()

    def is_with(self) -> bool:
        return self.parent.is_with()

    def is_without(self) -> bool:
        return self.parent.is_without()

    def __get_threads(self: models.Model):
        return [attr for attr in self._meta.get_fields() if attr.name.endswith("_thread")]

    def get_activity(self) -> Activity:
        return self.parent.activity

    def get_relevant_scenarios(self):
        """
        Returns the relevant scenarios for a given field.

        Args:
            field (str): The field to check.

        Returns:
            list: The relevant scenarios for the given field.
        """
        log.debug("Get relevant scenarios for field")
        module_start = module_w = module_wo = self

        scenarios = []

        if self.__class__.__name__ == module_start.__class__.__name__:
            scenarios.append(utils.ScenarioTypes.START)
        if self.__class__.__name__ == module_w.__class__.__name__:
            scenarios.append(utils.ScenarioTypes.WITH)
        if self.__class__.__name__ == module_wo.__class__.__name__:
            scenarios.append(utils.ScenarioTypes.WITHOUT)

        return scenarios

    def get_cached_results(self, by=BreakdownTypes.TOTAL):
        # TODO: Implement caching for submodules
        return None


class Module(Historical, CachedResultMixin):
    class Meta:
        abstract = True

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="%(class)s", verbose_name=_("activity"))
    start_year = models.IntegerField(default=1, verbose_name=_("start_year"))
    note = GenericRelation(Note)

    soc_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("soc_t2_start"))
    soc_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("soc_t2_w"))
    soc_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("soc_t2_wo"))

    status = models.ForeignKey(StatusType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("status"))

    @property
    def module_type(self):
        return ModuleType.objects.get(class_name=self.__class__.__name__)

    @property
    def project(self):
        return self.activity.project

    @property
    def threads(self):
        return self.__get_threads()

    def __str__(self):
        return f"({self.pk}) {self._meta.object_name} in {self.activity.name}"

    def is_ready(self) -> bool:
        return self.status and self.status.name_en == "READY"

    def save(self, *args, **kwargs):
        if not self.status:
            self.status = StatusType.objects.get(name_en="EMPTY")

        if not self.pk:
            utils.create_comment_threads(self)

        super().save(*args, **kwargs)

    def is_luc_remaining_same(self) -> bool:
        """
        Checks if the land use change for a given module remains the same.

        Args:
            module (LandModule): The land module to check.

        Returns:
            bool: True if the land use change remains the same, False otherwise.
        """
        log.debug("Is LUC remaining the same")
        luc: LandUseChange = getattr(self, "land_use_change", None)
        return not luc or (luc and luc.module_type_start.class_name == self.__class__.__name__ and luc.module_type_w.class_name == self.__class__.__name__)

    def is_business_as_usual(self) -> bool:
        """
        Checks if the given module represents a business-as-usual scenario.

        Args:
            module (LandModule): The land module to check.

        Returns:
            bool: True if the module represents a business-as-usual scenario, False otherwise.
        """
        log.debug("Is business as usual")
        luc: LandUseChange = getattr(self, "land_use_change", None)
        return not luc or (luc and luc.module_type_start.class_name == self.__class__.__name__ and luc.module_type_wo.class_name == self.__class__.__name__)

    def is_start(self) -> bool:
        """
        Checks if the given module represents the start of a land use change.

        Args:
            module (LandModule): The land module to check.

        Returns:
            bool: True if the module represents the start of a land use change, False otherwise.
        """
        log.debug("Is start")
        luc: LandUseChange = getattr(self, "land_use_change", None)
        return not luc or (luc and luc.module_type_start.class_name == self.__class__.__name__)

    def is_without(self) -> bool:
        """
        Checks if the given module is without a land use change or if the module type without land use change matches the module's class name.

        Args:
            module (LandModule): The module to check.

        Returns:
            bool: True if the module is associated with the land use change or if the provided module types the LandUseChange "WITHOUT" scenario. False otherwise.
        """
        log.debug("Is without")
        luc: LandUseChange = getattr(self, "land_use_change", None)
        return not luc or (luc.module_type_wo.class_name == self.__class__.__name__)

    def is_with(self) -> bool:
        """
        Checks if the given module is associated with a specific land use change.

        Args:
            module (LandModule): The module to check.

        Returns:
            bool: True if the module is associated with the land use change or if the provided module types the LandUseChange "WITH" scenario. False otherwise.
        """
        log.debug("Is with")
        luc: LandUseChange = getattr(self, "land_use_change", None)
        return not luc or (luc.module_type_w.class_name == self.__class__.__name__)

    def get_relevant_scenarios(self):
        """
        Returns the relevant scenarios for a given field.

        Args:
            field (str): The field to check.

        Returns:
            list: The relevant scenarios for the given field.
        """
        log.debug("Get relevant scenarios for field")
        luc: LandUseChange = getattr(self, "land_use_change", None)
        module_start = module_w = module_wo = self
        if luc:
            module_start, module_w, module_wo = luc.get_modules()

        scenarios = []

        if self.__class__.__name__ == module_start.__class__.__name__:
            scenarios.append(utils.ScenarioTypes.START)
        if self.__class__.__name__ == module_w.__class__.__name__:
            scenarios.append(utils.ScenarioTypes.WITH)
        if self.__class__.__name__ == module_wo.__class__.__name__:
            scenarios.append(utils.ScenarioTypes.WITHOUT)

        return scenarios

    def __get_threads(self: models.Model):
        return [attr for attr in self._meta.get_fields() if attr.name.endswith("_thread")]

    def get_activity(self) -> Activity:
        return self.activity


class BiomassModule(Module):
    class Meta:
        abstract = True

    @property
    def biomass_t2_start(self):
        raise NotImplementedError("Biomass modules must implement the biomass_t2_start property")

    @property
    def biomass_t2_w(self):
        raise NotImplementedError("Biomass modules must implement the biomass_t2_w property")

    @property
    def biomass_t2_wo(self):
        raise NotImplementedError("Biomass modules must implement the biomass_t2_wo property")


class BiomassMixin(models.Model):
    biomass_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("biomass_t2_start"))
    biomass_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("biomass_t2_w"))
    biomass_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("biomass_t2_wo"))

    class Meta:
        abstract = True

    @property
    def biomass_t2_start(self):
        return self.get_biomass_t2(utils.ScenarioTypes.START)

    @property
    def biomass_t2_w(self):
        return self.get_biomass_t2(utils.ScenarioTypes.WITH)

    @property
    def biomass_t2_wo(self):
        return self.get_biomass_t2(utils.ScenarioTypes.WITHOUT)

    def get_biomass_t2(self, scenario: utils.ScenarioTypes):
        return getattr(self, f"biomass_t2_{scenario.value}", None)

    def get_biomass_ef(self, scenario: utils.ScenarioTypes) -> ipcc.ForestTotalBiomass | ipcc.TotalBiomassAfterDefo:
        BiomassModel: models.Model = ipcc.ForestTotalBiomass if scenario == utils.ScenarioTypes.START else ipcc.TotalBiomassAfterDefo
        activity: Activity = getattr(self, "parent", self).activity
        module: LandModule = getattr(self, "parent", self)
        climate = activity.climate_t2 if activity.climate_t2 is not None else activity.project.climate
        moisture = activity.moisture_t2 if activity.moisture_t2 is not None else activity.project.moisture
        continent = activity.project.country.region
        land_use_type = getattr(module, f"land_use_type_{scenario.value}", None)
        if land_use_type is None:
            raise exceptions.ValidationError(f"Missing land use type for {scenario.value} scenario")

        try:
            return BiomassModel.objects.get(climate=climate, moisture=moisture, continent=continent, land_use_type=land_use_type)
        except BiomassModel.DoesNotExist:
            if getattr(self, f"biomass_t2_{scenario.value}", None) is None:
                raise exceptions.ValidationError(f"Missing biomass data for {land_use_type}, {climate}, {moisture}, {continent}, for {scenario.verbose_name} scenario. Please provide tier2 value.")
            return BiomassModel()


class SingleBiomassModule(BiomassModule):
    biomass_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("biomass_t2_start"))
    biomass_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("biomass_t2_w"))
    biomass_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("biomass_t2_wo"))

    class Meta:
        abstract = True

    def get_biomass_t2(self, scenario: utils.ScenarioTypes):
        return getattr(self, f"biomass_t2_{scenario.value}", None)

    def get_biomass_ef(self, scenario: utils.ScenarioTypes) -> ipcc.ForestTotalBiomass | ipcc.TotalBiomassAfterDefo:
        BiomassModel: models.Model = ipcc.ForestTotalBiomass if scenario == utils.ScenarioTypes.START else ipcc.TotalBiomassAfterDefo
        climate = self.activity.climate_t2 if self.activity.climate_t2 is not None else self.activity.project.climate
        moisture = self.activity.moisture_t2 if self.activity.moisture_t2 is not None else self.activity.project.moisture
        continent = self.activity.project.country.region
        land_use_type = getattr(self, f"land_use_type_{scenario.value}", None)
        if land_use_type is None:
            raise ValueError(f"Missing land use type for {scenario.value} scenario")

        try:
            return BiomassModel.objects.get(climate=climate, moisture=moisture, continent=continent, land_use_type=land_use_type)
        except BiomassModel.DoesNotExist:
            if getattr(self, f"biomass_t2_{scenario.value}", None) is None:
                raise ValueError(f"Missing biomass data for {land_use_type.name}, {climate.name}, {moisture.name}, {continent.name}, for {scenario.verbose_name} scenario. Please provide tier2 value.")
            return BiomassModel()


class ResidueAvailability(models.Model):
    residue_availability_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("residue_availability_t2_start"))
    residue_availability_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("residue_availability_t2_w"))
    residue_availability_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("residue_availability_t2_wo"))

    class Meta:
        abstract = True


class AboveBelowGroundBiomassModule(BiomassModule):
    agb_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("agb_t2_start"))
    agb_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("agb_t2_w"))
    agb_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("agb_t2_wo"))

    bgb_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("bgb_t2_start"))
    bgb_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("bgb_t2_w"))
    bgb_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("bgb_t2_wo"))

    class Meta:
        abstract = True

    @property
    def biomass_t2_start(self):
        return self.get_biomass_t2(utils.ScenarioTypes.START)

    @property
    def biomass_t2_w(self):
        return self.get_biomass_t2(utils.ScenarioTypes.WITH)

    @property
    def biomass_t2_wo(self):
        return self.get_biomass_t2(utils.ScenarioTypes.WITHOUT)

    def get_biomass_t2(self, scenario: utils.ScenarioTypes):

        if getattr(self, f"agb_t2_{scenario.value}", None) is None and getattr(self, f"bgb_t2_{scenario.value}", None) is None:
            return None

        agb_t2 = getattr(self, f"agb_t2_{scenario.value}")
        bgb_t2 = getattr(self, f"bgb_t2_{scenario.value}")

        if agb_t2 is not None and bgb_t2 is not None:
            return agb_t2 + bgb_t2
        elif agb_t2 is not None:
            return agb_t2
        elif bgb_t2 is not None:
            return bgb_t2
        else:
            return None

    def get_biomass_ef(self, scenario: utils.ScenarioTypes):
        BiomassModel: models.Model = ipcc.ForestTotalBiomass if scenario == utils.ScenarioTypes.START else ipcc.TotalBiomassAfterDefo
        climate = self.activity.climate_t2 if self.activity.climate_t2 is not None else self.activity.project.climate
        moisture = self.activity.moisture_t2 if self.activity.moisture_t2 is not None else self.activity.project.moisture
        continent = self.activity.project.country.region
        land_use_type = getattr(self, f"land_use_type_{scenario.value}", None)
        if land_use_type is None:
            raise exceptions.ValidationError(f"Missing land use type for {scenario.value} scenario")

        try:
            return BiomassModel.objects.get(climate=climate, moisture=moisture, continent=continent, land_use_type=land_use_type)
        except BiomassModel.DoesNotExist:
            if self.get_biomass_t2(scenario) is None:
                raise exceptions.ValidationError(f"Missing biomass data for {land_use_type.name}, {climate.name}, {moisture.name}, {continent.name}. Please provide tier2 value.")
            return None


class LitterDeadwoodBiomassModule(AboveBelowGroundBiomassModule):
    litter_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("litter_t2_start"))
    litter_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("litter_t2_w"))
    litter_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("litter_t2_wo"))

    deadwood_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("deadwood_t2_start"))
    deadwood_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("deadwood_t2_w"))
    deadwood_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("deadwood_t2_wo"))

    class Meta:
        abstract = True

    @property
    def biomass_t2_start(self):
        return self.get_biomass_t2(utils.ScenarioTypes.START)

    @property
    def biomass_t2_w(self):
        return self.get_biomass_t2(utils.ScenarioTypes.WITH)

    @property
    def biomass_t2_wo(self):
        return self.get_biomass_t2(utils.ScenarioTypes.WITHOUT)

    def get_biomass_t2(self, scenario: utils.ScenarioTypes):

        if getattr(self, f"litter_t2_{scenario.value}", None) is None and getattr(self, f"deadwood_t2_{scenario.value}", None) is None:
            return None

        litter_t2 = getattr(self, f"litter_t2_{scenario.value}")
        deadwood_t2 = getattr(self, f"deadwood_t2_{scenario.value}")
        super_t2 = super().get_biomass_t2(scenario)

        if litter_t2 is not None and deadwood_t2 is not None and super_t2 is not None:
            return litter_t2 + deadwood_t2 + super_t2
        elif litter_t2 is not None and deadwood_t2 is not None:
            return litter_t2 + deadwood_t2
        elif litter_t2 is not None:
            return litter_t2
        elif deadwood_t2 is not None:
            return deadwood_t2
        else:
            return super_t2


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
    land_use_change = models.OneToOneField("api.LandUseChange", on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s", verbose_name=_("land_use_change"))
    organic_soil = models.OneToOneField("api.OrganicSoil", on_delete=models.CASCADE, null=True, blank=True, related_name="organic_soil_%(class)s", verbose_name=_("organic_soil"))

    area = models.FloatField(null=True, blank=True, validators=[validators.MinValueValidator(0)], verbose_name=_("area"))

    land_use_type_start = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_start", verbose_name=_("land_use_type_start"))
    land_use_type_w = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_w", verbose_name=_("land_use_type_w"))
    land_use_type_wo = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_wo", verbose_name=_("land_use_type_wo"))
    land_use_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_thread")

    flu_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("flu_t2_start"))
    flu_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("flu_t2_w"))
    flu_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("flu_t2_wo"))

    fi_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("fi_t2_start"))
    fi_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("fi_t2_w"))
    fi_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("fi_t2_wo"))

    fmg_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("fmg_t2_start"))
    fmg_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("fmg_t2_w"))
    fmg_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("fmg_t2_wo"))

    class Meta:
        abstract = True

    def is_perennial(self) -> bool:
        return self.module_type.class_name == ["PerennialCropland"]

    def is_forest(self) -> bool:
        return self.module_type.class_name == ["ForestManagement"]


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


class AnnualCropland(LandModule, SingleBiomassModule, ResidueAvailability):
    tillage_management_type_start = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, related_name="%(class)s_tillage_management_type_start", null=True, blank=True, verbose_name=_("tillage_management_type_start"))
    tillage_management_type_w = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, related_name="%(class)s_tillage_management_type_w", null=True, blank=True, verbose_name=_("tillage_management_type_w"))
    tillage_management_type_wo = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, related_name="%(class)s_tillage_management_type_wo", null=True, blank=True, verbose_name=_("tillage_management_type_wo"))
    tillage_management_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_thread")

    organic_input_type_start = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, related_name="%(class)s_organic_input_type_start", null=True, blank=True, verbose_name=_("organic_input_type_start"))
    organic_input_type_w = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, related_name="%(class)s_organic_input_type_w", null=True, blank=True, verbose_name=_("organic_input_type_w"))
    organic_input_type_wo = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, related_name="%(class)s_organic_input_type_wo", null=True, blank=True, verbose_name=_("organic_input_type_wo"))
    organic_input_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_thread")

    residue_management_type_start = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, related_name="%(class)s_residue_management_type_start", null=True, blank=True, verbose_name=_("residue_management_type_start"))
    residue_management_type_w = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, related_name="%(class)s_residue_management_type_w", null=True, blank=True, verbose_name=_("residue_management_type_w"))
    residue_management_type_wo = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, related_name="%(class)s_residue_management_type_wo", null=True, blank=True, verbose_name=_("residue_management_type_wo"))
    residue_management_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_thread")

    crop_yield_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_start"))
    crop_yield_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_w"))
    crop_yield_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_wo"))
    crop_yield_t2_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_crop_yield_t2_thread")

    area = models.FloatField(null=True, blank=True, verbose_name=_("area"))

    minor_land_use_type_start = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_land_use_type_start", verbose_name=_("minor_land_use_type_start"))
    minor_land_use_type_w = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_land_use_type_w", verbose_name=_("minor_land_use_type_w"))
    minor_land_use_type_wo = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_land_use_type_wo", verbose_name=_("minor_land_use_type_wo"))

    minor_yield_start = models.FloatField(null=True, blank=True, verbose_name=_("minor_yield_start"))
    minor_yield_w = models.FloatField(null=True, blank=True, verbose_name=_("minor_yield_w"))
    minor_yield_wo = models.FloatField(null=True, blank=True, verbose_name=_("minor_yield_wo"))

    minor_residue_management_type_start = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_residue_management_type", verbose_name=_("minor_residue_management_type_start"))
    minor_residue_management_type_w = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_residue_management_type_w", verbose_name=_("minor_residue_management_type_w"))
    minor_residue_management_type_wo = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_minor_residue_management_type_wo", verbose_name=_("minor_residue_management_type_wo"))

    minor_biomass_factor_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("minor_biomass_factor_t2_start"))
    minor_biomass_factor_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("minor_biomass_factor_t2_w"))
    minor_biomass_factor_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("minor_biomass_factor_t2_wo"))

    @property
    def submodules(self) -> list["Submodule"]:
        return list(self.minor_seasons.all())


class PerennialCrop(models.Model):
    class Meta:
        abstract = True

    tillage_management_type_start = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_start", verbose_name=_("tillage_management_type_start"))
    tillage_management_type_w = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_w", verbose_name=_("tillage_management_type_w"))
    tillage_management_type_wo = models.ForeignKey(TillageManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_wo", verbose_name=_("tillage_management_type_wo"))
    tillage_management_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_tillage_management_type_thread")

    organic_input_type_start = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_start", verbose_name=_("organic_input_type_start"))
    organic_input_type_w = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_w", verbose_name=_("organic_input_type_w"))
    organic_input_type_wo = models.ForeignKey(OrganicInputType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_wo", verbose_name=_("organic_input_type_wo"))
    organic_input_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_organic_input_type_thread")

    is_biomass_burned_start = models.BooleanField(null=True, blank=True, verbose_name=_("is_biomass_burned_start"))
    is_biomass_burned_w = models.BooleanField(null=True, blank=True, verbose_name=_("is_biomass_burned_w"))
    is_biomass_burned_wo = models.BooleanField(null=True, blank=True, verbose_name=_("is_biomass_burned_wo"))
    is_biomass_burned_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_is_biomass_burned_thread")

    area = models.FloatField(null=True, blank=True, verbose_name=_("area"))

    crop_yield_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_start"))
    crop_yield_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_w"))
    crop_yield_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_wo"))
    crop_yield_t2_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_crop_yield_t2_thread")

    agb_max_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("agb_max_t2_start"))
    agb_max_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("agb_max_t2_w"))
    agb_max_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("agb_max_t2_wo"))

    fire_periodicity_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("fire_periodicity_t2_start"))
    fire_periodicity_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("fire_periodicity_t2_w"))
    fire_periodicity_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("fire_periodicity_t2_wo"))


class PerennialCropland(PerennialCrop, LandModule, SingleBiomassModule, AboveBelowGroundBiomassModule, ResidueAvailability):
    pass

    # NOTE: Why having AGB and BGB AND Biomass when Biomass = AGB + BGB?
    def get_biomass_t2(self, scenario: utils.ScenarioTypes):
        return getattr(self, f"biomass_t2_{scenario.value}", None)

    @property
    def submodules(self) -> list["Submodule"]:
        return list(self.minor_seasons.all())


class CroplandMinorSeason(models.Model):
    class Meta:
        abstract = True

    land_use_type_start = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_start", verbose_name=_("land_use_type_start"))
    land_use_type_w = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_w", verbose_name=_("land_use_type_w"))
    land_use_type_wo = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_wo", verbose_name=_("land_use_type_wo"))
    land_use_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_land_use_type_thread")

    residue_management_type_start = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_start", verbose_name=_("residue_management_type_start"))
    residue_management_type_w = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_w", verbose_name=_("residue_management_type_w"))
    residue_management_type_wo = models.ForeignKey(ResidueManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_wo", verbose_name=_("residue_management_type_wo"))
    residue_management_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_residue_management_type_thread")

    crop_yield_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_start"))
    crop_yield_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_w"))
    crop_yield_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_wo"))
    crop_yield_t2_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_yield_t2_thread")


class MinorSeasonPerennialCropland(CroplandMinorSeason, LandSubmodule):
    parent = models.ForeignKey(PerennialCropland, on_delete=models.CASCADE, related_name="minor_seasons", null=True, blank=True)


class MinorSeasonAnnualCropland(CroplandMinorSeason, LandSubmodule):
    parent = models.ForeignKey(AnnualCropland, on_delete=models.CASCADE, related_name="minor_seasons", null=True, blank=True)


class Rice(ResidueAvailability):
    class Meta:
        abstract = True

    water_management_type_before_cultivation_start = models.ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_before_cultivation_start", null=True, verbose_name=_("water_management_type_before_cultivation_start"))
    water_management_type_before_cultivation_w = models.ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_before_cultivation_w", null=True, verbose_name=_("water_management_type_before_cultivation_w"))
    water_management_type_before_cultivation_wo = models.ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_before_cultivation_wo", null=True, verbose_name=_("water_management_type_before_cultivation_wo"))

    water_management_type_after_cultivation_start = models.ForeignKey(WaterManagementTypeAfterCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_after_cultivation_start", null=True, verbose_name=_("water_management_type_after_cultivation_start"))
    water_management_type_after_cultivation_w = models.ForeignKey(WaterManagementTypeAfterCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_after_cultivation_w", null=True, verbose_name=_("water_management_type_after_cultivation_w"))
    water_management_type_after_cultivation_wo = models.ForeignKey(WaterManagementTypeAfterCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_after_cultivation_wo", null=True, verbose_name=_("water_management_type_after_cultivation_wo"))

    organic_amendment_type_start = models.ForeignKey(OrganicAmendmentType, on_delete=models.CASCADE, related_name="%(class)s_organic_amendment_type_start", null=True)
    organic_amendment_type_w = models.ForeignKey(OrganicAmendmentType, on_delete=models.CASCADE, related_name="%(class)s_organic_amendment_type_w", null=True)
    organic_amendment_type_wo = models.ForeignKey(OrganicAmendmentType, on_delete=models.CASCADE, related_name="%(class)s_organic_amendment_type_wo", null=True)

    crop_yield_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_start"))
    crop_yield_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_w"))
    crop_yield_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("crop_yield_t2_wo"))
    crop_yield_t2_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_crop_yield_t2_thread")

    efc_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("efc_t2_start"))
    efc_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("efc_t2_w"))
    efc_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("efc_t2_wo"))

    sfw_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("sfw_t2_start"))
    sfw_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("sfw_t2_w"))
    sfw_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("sfw_t2_wo"))

    sfp_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("sfp_t2_start"))
    sfp_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("sfp_t2_w"))
    sfp_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("sfp_t2_wo"))

    sfo_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("sfo_t2_start"))
    sfo_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("sfo_t2_w"))
    sfo_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("sfo_t2_wo"))

    efi_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("efi_t2_start"))
    efi_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("efi_t2_w"))
    efi_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("efi_t2_wo"))

    rice_straw_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("rice_straw_t2_start"))
    rice_straw_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("rice_straw_t2_w"))
    rice_straw_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("rice_straw_t2_wo"))

    cultivation_period_t2_start = models.IntegerField(null=True, blank=True, verbose_name=_("cultivation_period_t2_start"))
    cultivation_period_t2_w = models.IntegerField(null=True, blank=True, verbose_name=_("cultivation_period_t2_w"))
    cultivation_period_t2_wo = models.IntegerField(null=True, blank=True, verbose_name=_("cultivation_period_t2_wo"))

    def save(self, *args, **kwargs):
        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name_en="Flooded Rice")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        super().save(*args, **kwargs)

    def is_minor_season(self) -> bool:
        return hasattr(self, "parent")


class FloodedRice(Rice, LandModuleFixed, SingleBiomassModule):
    pass

    @property
    def submodules(self) -> list["Submodule"]:
        return list(self.minor_seasons.all())


class MinorSeasonFloodedRice(Rice, LandSubmodule, BiomassMixin):
    parent = models.ForeignKey(FloodedRice, on_delete=models.CASCADE, related_name="minor_seasons", null=True, blank=True)


##### Grassland and Livestock #####


class Grassland(LandModuleFixed, SingleBiomassModule, AboveBelowGroundBiomassModule):
    grassland_management_type_start = models.ForeignKey(GrasslandManagementType, on_delete=models.CASCADE, related_name="%(class)s_grassland_management_type_start", null=True, verbose_name=_("grassland_management_type_start"))
    grassland_management_type_w = models.ForeignKey(GrasslandManagementType, on_delete=models.CASCADE, related_name="%(class)s_grassland_management_type_w", null=True, verbose_name=_("grassland_management_type_w"))
    grassland_management_type_wo = models.ForeignKey(GrasslandManagementType, on_delete=models.CASCADE, related_name="%(class)s_grassland_management_type_wo", null=True, verbose_name=_("grassland_management_type_wo"))

    is_fire_used_start = models.BooleanField(default=False, verbose_name=_("is_fire_used_start"))
    is_fire_used_w = models.BooleanField(default=False, verbose_name=_("is_fire_used_w"))
    is_fire_used_wo = models.BooleanField(default=False, verbose_name=_("is_fire_used_wo"))
    is_fire_used_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_is_fire_used_thread")

    fire_periodicity_start = models.FloatField(null=True, blank=True, default=0, verbose_name=_("fire_periodicity_start"))
    fire_periodicity_w = models.FloatField(null=True, blank=True, default=0, verbose_name=_("fire_periodicity_w"))
    fire_periodicity_wo = models.FloatField(null=True, blank=True, default=0, verbose_name=_("fire_periodicity_wo"))
    fire_periodicity_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fire_periodicity_thread")

    fire_impact_start = models.FloatField(null=True, blank=True, default=0, verbose_name=_("fire_impact_start"))
    fire_impact_w = models.FloatField(null=True, blank=True, default=0, verbose_name=_("fire_impact_w"))
    fire_impact_wo = models.FloatField(null=True, blank=True, default=0, verbose_name=_("fire_impact_wo"))
    fire_impact_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fire_impact_thread")

    yield_start = models.FloatField(null=True, blank=True, verbose_name=_("yield_start"))
    yield_w = models.FloatField(null=True, blank=True, verbose_name=_("yield_w"))
    yield_wo = models.FloatField(null=True, blank=True, verbose_name=_("yield_wo"))
    yield_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_yield_thread")

    area = models.FloatField(null=True, blank=True, verbose_name=_("area"))

    combustion_factor_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("combustion_factor_t2_start"))
    combustion_factor_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("combustion_factor_t2_w"))
    combustion_factor_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("combustion_factor_t2_wo"))

    def save(self, *args, **kwargs):
        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name_en="Grassland")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        super().save(*args, **kwargs)


class Livestock(Module):
    livestock_category_type = models.ForeignKey(LivestockCategoryType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_livestock_category_type", verbose_name=_("livestock_category_type"))
    livestock_category_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_livestock_categories_thread", on_delete=models.SET_NULL)

    livestock_production_type_start = models.ForeignKey(LivestockProductionType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("livestock_production_type_start"))
    livestock_production_type_w = models.ForeignKey(LivestockProductionType, on_delete=models.CASCADE, related_name="%(class)s_livestock_productions_w", null=True, blank=True, verbose_name=_("livestock_production_type_w"))
    livestock_production_type_wo = models.ForeignKey(LivestockProductionType, on_delete=models.CASCADE, related_name="%(class)s_livestock_productions_wo", null=True, blank=True, verbose_name=_("livestock_production_type_wo"))
    livestock_production_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_livestock_production_type_thread", on_delete=models.SET_NULL)

    production_start = models.FloatField(null=True, blank=True, verbose_name=_("production_start"))
    production_w = models.FloatField(null=True, blank=True, verbose_name=_("production_w"))
    production_wo = models.FloatField(null=True, blank=True, verbose_name=_("production_wo"))
    production_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_production_thread", on_delete=models.SET_NULL)

    heads_number_start = models.IntegerField(null=True, blank=True, verbose_name=_("heads_number_start"))
    heads_number_w = models.IntegerField(null=True, blank=True, verbose_name=_("heads_number_w"))
    heads_number_wo = models.IntegerField(null=True, blank=True, verbose_name=_("heads_number_wo"))
    heads_number_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_heads_number_thread", on_delete=models.SET_NULL)

    complementary_manure_management_type_start = models.ForeignKey(ManureManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_manure_management_type_t2_start", verbose_name=_("complementary_manure_management_type_start"))
    complementary_manure_management_type_w = models.ForeignKey(ManureManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_manure_management_type_t2_w", verbose_name=_("complementary_manure_management_type_w"))
    complementary_manure_management_type_wo = models.ForeignKey(ManureManagementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_manure_management_type_t2_wo", verbose_name=_("complementary_manure_management_type_wo"))
    complementary_manure_management_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_complementary_manure_management_type_thread", on_delete=models.SET_NULL)

    enteric_fermentation_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("enteric_fermentation_t2_start"))
    enteric_fermentation_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("enteric_fermentation_t2_w"))
    enteric_fermentation_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("enteric_fermentation_t2_wo"))

    prp_percentage_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("prp_percentage_t2_start"))
    prp_percentage_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("prp_percentage_t2_w"))
    prp_percentage_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("prp_percentage_t2_wo"))
    prp_percentage_t2_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_prp_percentage_t2_thread", on_delete=models.SET_NULL)

    prp_ch4_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("prp_ch4_t2_start"))
    prp_ch4_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("prp_ch4_t2_w"))
    prp_ch4_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("prp_ch4_t2_wo"))

    prp_n2o_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("prp_n2o_t2_start"))
    prp_n2o_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("prp_n2o_t2_w"))
    prp_n2o_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("prp_n2o_t2_wo"))

    emission_factor_ch4_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("emission_factor_ch4_t2_start"))
    emission_factor_n2o_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("emission_factor_n2o_t2_start"))

    emission_factor_ch4_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("emission_factor_ch4_t2_w"))
    emission_factor_n2o_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("emission_factor_n2o_t2_w"))

    emission_factor_ch4_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("emission_factor_ch4_t2_wo"))
    emission_factor_n2o_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("emission_factor_n2o_t2_wo"))

    implementation_year_start = models.IntegerField(null=True, blank=True, verbose_name=_("implementation_year_start"))


##### Forest Management #####


class ForestManagement(LandModule, LitterDeadwoodBiomassModule):
    forest_type = models.ForeignKey(ForestType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("forest_type"))
    forest_condition_type = models.ForeignKey(ForestConditionType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("forest_condition_type"))

    ##### ROTATION #####

    rotation_length_yrs_start = models.IntegerField(null=True, blank=True, verbose_name=_("rotation_length_yrs_start"))
    rotation_length_yrs_w = models.IntegerField(null=True, blank=True, verbose_name=_("rotation_length_yrs_w"))
    rotation_length_yrs_wo = models.IntegerField(null=True, blank=True, verbose_name=_("rotation_length_yrs_wo"))
    rotation_length_yrs_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_rotation_length_yrs_thread")

    rotation_percentage_biomass_for_energy_start = models.FloatField(null=True, blank=True, default=0, verbose_name=_("rotation_percentage_biomass_for_energy_start"))
    rotation_percentage_biomass_for_energy_w = models.FloatField(null=True, blank=True, default=0, verbose_name=_("rotation_percentage_biomass_for_energy_w"))
    rotation_percentage_biomass_for_energy_wo = models.FloatField(null=True, blank=True, default=0, verbose_name=_("rotation_percentage_biomass_for_energy_wo"))
    rotation_percentage_biomass_for_energy_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_rotation_percentage_biomass_for_energy_thread")

    ##### LOGGING #####

    logging_recurrence_yrs_start = models.IntegerField(null=True, blank=True, verbose_name=_("logging_recurrence_yrs_start"))
    logging_recurrence_yrs_w = models.IntegerField(null=True, blank=True, verbose_name=_("logging_recurrence_yrs_w"))
    logging_recurrence_yrs_wo = models.IntegerField(null=True, blank=True, verbose_name=_("logging_recurrence_yrs_wo"))
    logging_recurrence_yrs_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_logging_recurrence_yrs_thread")

    logging_percentage_agb_logged_start = models.FloatField(null=True, blank=True, default=0, validators=[validators.MinValueValidator(0), validators.MaxValueValidator(1)], verbose_name=_("logging_percentage_agb_logged_start"))
    logging_percentage_agb_logged_w = models.FloatField(null=True, blank=True, default=0, validators=[validators.MinValueValidator(0), validators.MaxValueValidator(1)], verbose_name=_("logging_percentage_agb_logged_w"))
    logging_percentage_agb_logged_wo = models.FloatField(null=True, blank=True, default=0, validators=[validators.MinValueValidator(0), validators.MaxValueValidator(1)], verbose_name=_("logging_percentage_agb_logged_wo"))
    logging_percentage_agb_logged_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_logging_percentage_agb_logged_thread")

    logging_percentage_biomass_for_energy_start = models.FloatField(null=True, blank=True, default=0, verbose_name=_("logging_percentage_biomass_for_energy_start"))
    logging_percentage_biomass_for_energy_w = models.FloatField(null=True, blank=True, default=0, verbose_name=_("logging_percentage_biomass_for_energy_w"))
    logging_percentage_biomass_for_energy_wo = models.FloatField(null=True, blank=True, default=0, verbose_name=_("logging_percentage_biomass_for_energy_wo"))
    logging_percentage_biomass_for_energy_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_logging_percentage_biomass_for_energy_thread")

    ##### DEGRADATION #####

    average_yearly_degradation_percentage_start = models.FloatField(null=True, blank=True, default=0, verbose_name=_("average_yearly_degradation_percentage_start"))
    average_yearly_degradation_percentage_w = models.FloatField(null=True, blank=True, default=0, verbose_name=_("average_yearly_degradation_percentage_w"))
    average_yearly_degradation_percentage_wo = models.FloatField(null=True, blank=True, default=0, verbose_name=_("average_yearly_degradation_percentage_wo"))
    average_yearly_degradation_percentage_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_average_yearly_degradation_percentage_thread")

    ##### TIER 2 #####

    agb_growth_rate_le_20_yrs_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("agb_growth_rate_le_20_yrs_t2_start"))
    agb_growth_rate_le_20_yrs_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("agb_growth_rate_le_20_yrs_t2_w"))
    agb_growth_rate_le_20_yrs_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("agb_growth_rate_le_20_yrs_t2_wo"))

    agb_growth_rate_gt_20_yrs_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("agb_growth_rate_gt_20_yrs_t2_start"))
    agb_growth_rate_gt_20_yrs_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("agb_growth_rate_gt_20_yrs_t2_w"))
    agb_growth_rate_gt_20_yrs_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("agb_growth_rate_gt_20_yrs_t2_wo"))

    bgb_growth_rate_le_20_yrs_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("bgb_growth_rate_le_20_yrs_t2_start"))
    bgb_growth_rate_le_20_yrs_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("bgb_growth_rate_le_20_yrs_t2_w"))
    bgb_growth_rate_le_20_yrs_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("bgb_growth_rate_le_20_yrs_t2_wo"))

    bgb_growth_rate_gt_20_yrs_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("bgb_growth_rate_gt_20_yrs_t2_start"))
    bgb_growth_rate_gt_20_yrs_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("bgb_growth_rate_gt_20_yrs_t2_w"))
    bgb_growth_rate_gt_20_yrs_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("bgb_growth_rate_gt_20_yrs_t2_wo"))

    rotation_start_year_t2_start = models.IntegerField(null=True, blank=True, default=0, verbose_name=_("rotation_start_year_t2_start"))
    rotation_start_year_t2_w = models.IntegerField(null=True, blank=True, default=0, verbose_name=_("rotation_start_year_t2_w"))
    rotation_start_year_t2_wo = models.IntegerField(null=True, blank=True, default=0, verbose_name=_("rotation_start_year_t2_wo"))

    logging_start_year_t2_start = models.IntegerField(null=True, blank=True, default=0, verbose_name=_("logging_start_year_t2_start"))
    logging_start_year_t2_w = models.IntegerField(null=True, blank=True, default=0, verbose_name=_("logging_start_year_t2_w"))
    logging_start_year_t2_wo = models.IntegerField(null=True, blank=True, default=0, verbose_name=_("logging_start_year_t2_wo"))

    logging_dry_matter_logged_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("logging_dry_matter_logged_t2_start"))
    logging_dry_matter_logged_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("logging_dry_matter_logged_t2_w"))
    logging_dry_matter_logged_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("logging_dry_matter_logged_t2_wo"))

    degradation_dry_matter_impacted_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("degradation_dry_matter_impacted_t2_start"))
    degradation_dry_matter_impacted_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("degradation_dry_matter_impacted_t2_w"))
    degradation_dry_matter_impacted_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("degradation_dry_matter_impacted_t2_wo"))

    @property
    def submodules(self) -> list["Submodule"]:
        return list(self.disturbances.all())

    def save(self, *args, **kwargs):
        if self.land_use_type_start:
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start
        return super().save(*args, **kwargs)

    def get_agb_growth_ref(self, land_use_type: LandUseType, from_year: int = 0) -> ipcc.ForestManagementAGB:
        climate = self.activity.climate_t2 if self.activity.climate_t2 else self.activity.project.climate

        filters = {
            "climate": climate,
            "region": self.activity.project.country.region,
            "land_use_type": land_use_type,
            "forest_type": self.forest_type,
            "forest_condition_type": self.forest_condition_type,
            "from_year": from_year,
        }

        ref: ipcc.ForestManagementAGB = ipcc.ForestManagementAGB.objects.filter(**filters).first()

        return ref


class DisturbanceType(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class ForestDisturbance(Submodule):
    parent = models.ForeignKey(ForestManagement, on_delete=models.CASCADE, related_name="disturbances")

    disturbance_type = models.ForeignKey(DisturbanceType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("disturbance_type"))
    disturbance_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_disturbance_type_thread")

    recurrence_yrs_start = models.IntegerField(null=True, blank=True, verbose_name=_("recurrence_yrs_start"))
    recurrence_yrs_w = models.IntegerField(null=True, blank=True, verbose_name=_("recurrence_yrs_w"))
    recurrence_yrs_wo = models.IntegerField(null=True, blank=True, verbose_name=_("recurrence_yrs_wo"))
    recurrence_yrs_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_disturbance_recurrence_yrs_thread")

    percentage_biomass_destruction_start = models.FloatField(null=True, blank=True, verbose_name=_("percentage_biomass_destruction_start"))
    percentage_biomass_destruction_w = models.FloatField(null=True, blank=True, verbose_name=_("percentage_biomass_destruction_w"))
    percentage_biomass_destruction_wo = models.FloatField(null=True, blank=True, verbose_name=_("percentage_biomass_destruction_wo"))
    percentage_biomass_destruction_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_disturbance_percentage_biomass_destruction_thread")

    start_year_t2_start = models.IntegerField(default=1, verbose_name=_("start_year_t2_start"))
    start_year_t2_w = models.IntegerField(default=1, verbose_name=_("start_year_t2_w"))
    start_year_t2_wo = models.IntegerField(default=1, verbose_name=_("start_year_t2_wo"))

    dry_matter_impacted_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("dry_matter_impacted_t2_start"))
    dry_matter_impacted_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("dry_matter_impacted_t2_w"))
    dry_matter_impacted_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("dry_matter_impacted_t2_wo"))


class Waterbody(Module):
    waterbody_type = models.ForeignKey(WaterbodyType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("waterbody_type"))
    area = models.FloatField(null=True, blank=True, verbose_name=_("area"))
    trophic_type_start = models.ForeignKey(TrophicType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_trophic_class_start", verbose_name=_("trophic_type_start"))
    trophic_type_w = models.ForeignKey(TrophicType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_trophic_class_w", verbose_name=_("trophic_type_w"))
    trophic_type_wo = models.ForeignKey(TrophicType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_trophic_class_wo", verbose_name=_("trophic_type_wo"))

    ch4_ef_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("ch4_ef_t2_start"))
    ch4_ef_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("ch4_ef_t2_w"))
    ch4_ef_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("ch4_ef_t2_wo"))

    alpha_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("alpha_t2_start"))
    alpha_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("alpha_t2_w"))
    alpha_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("alpha_t2_wo"))

    mean_annual_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("mean_annual_t2_start"))
    mean_annual_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("mean_annual_t2_w"))
    mean_annual_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("mean_annual_t2_wo"))


class CoastalWetland(Module):
    land_use_type = models.ForeignKey(LandUseType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("land_use_type"))

    area = models.FloatField(null=True, blank=True, verbose_name=_("area"))
    ha_thread = models.ForeignKey(CommentThread, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_ha_thread")

    area_under_drainage_start = models.FloatField(null=True, blank=True, default=0, verbose_name=_("area_under_drainage_start"))
    area_under_drainage_w = models.FloatField(null=True, blank=True, default=0, verbose_name=_("area_under_drainage_w"))
    area_under_drainage_wo = models.FloatField(null=True, blank=True, default=0, verbose_name=_("area_under_drainage_wo"))
    area_under_drainage_thread = models.ForeignKey(CommentThread, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_area_under_drainage_thread")

    drained_area_excavated_start = models.FloatField(null=True, blank=True, default=0, verbose_name=_("drained_area_excavated_start"))
    drained_area_excavated_w = models.FloatField(null=True, blank=True, default=0, verbose_name=_("drained_area_excavated_w"))
    drained_area_excavated_wo = models.FloatField(null=True, blank=True, default=0, verbose_name=_("drained_area_excavated_wo"))
    drained_area_excavated_thread = models.ForeignKey(CommentThread, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_drained_area_excavated_thread")

    area_not_drained_or_rewetted_start = models.FloatField(null=True, blank=True, default=0, verbose_name=_("area_not_drained_or_rewetted_start"))
    area_not_drained_or_rewetted_w = models.FloatField(null=True, blank=True, default=0, verbose_name=_("area_not_drained_or_rewetted_w"))
    area_not_drained_or_rewetted_wo = models.FloatField(null=True, blank=True, default=0, verbose_name=_("area_not_drained_or_rewetted_wo"))
    area_not_drained_or_rewetted_thread = models.ForeignKey(CommentThread, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_area_not_drained_or_rewetted_thread")

    area_w_restored_vegetation_start = models.FloatField(null=True, blank=True, default=0, verbose_name=_("area_w_restored_vegetation_start"))
    area_w_restored_vegetation_w = models.FloatField(null=True, blank=True, default=0, verbose_name=_("area_w_restored_vegetation_w"))
    area_w_restored_vegetation_wo = models.FloatField(null=True, blank=True, default=0, verbose_name=_("area_w_restored_vegetation_wo"))
    area_w_restored_vegetation_thread = models.ForeignKey(CommentThread, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_area_w_restored_vegetation_thread")

    soil_type_t2 = models.ForeignKey(SoilType, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("soil_type_t2"))

    soc_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("soc_t2_start"))
    soc_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("soc_t2_w"))
    soc_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("soc_t2_wo"))

    pc_c_lost_after_excavation_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("pc_c_lost_after_excavation_t2_start"))
    pc_c_lost_after_excavation_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("pc_c_lost_after_excavation_t2_w"))
    pc_c_lost_after_excavation_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("pc_c_lost_after_excavation_t2_wo"))

    agb_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("agb_t2_start"))
    agb_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("agb_t2_w"))
    agb_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("agb_t2_wo"))

    bgb_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("bgb_t2_start"))
    bgb_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("bgb_t2_w"))
    bgb_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("bgb_t2_wo"))

    litter_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("litter_t2_start"))
    litter_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("litter_t2_w"))
    litter_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("litter_t2_wo"))

    deadwood_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("deadwood_t2_start"))
    deadwood_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("deadwood_t2_w"))
    deadwood_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("deadwood_t2_wo"))

    drainage_ef_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("drainage_ef_t2_start"))
    drainage_ef_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("drainage_ef_t2_w"))
    drainage_ef_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("drainage_ef_t2_wo"))

    co2_rewetting_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("co2_rewetting_t2_start"))
    co2_rewetting_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("co2_rewetting_t2_w"))
    co2_rewetting_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("co2_rewetting_t2_wo"))

    ch4_rewetting_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("ch4_rewetting_t2_start"))
    ch4_rewetting_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("ch4_rewetting_t2_w"))
    ch4_rewetting_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("ch4_rewetting_t2_wo"))

    avg_salinity_t2 = models.ForeignKey(SalinityType, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("avg_salinity_t2"))


##### Fisheries and Aquaculture #####


class Fishery(Module):
    class Meta:
        abstract = True

    refrigerant_pc_start = models.FloatField(validators=[pc_as_float], default=0, verbose_name=_("refrigerant_pc_start"))
    refrigerant_pc_w = models.FloatField(validators=[pc_as_float], default=0, verbose_name=_("refrigerant_pc_w"))
    refrigerant_pc_wo = models.FloatField(validators=[pc_as_float], default=0, verbose_name=_("refrigerant_pc_wo"))
    refrigerant_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_refrigerant_thread", on_delete=models.SET_NULL)

    refrigerant_gwp = models.FloatField(null=True, blank=True, default=1810, verbose_name=_("refrigerant_gwp"))

    total_catch_yr_start = models.FloatField(null=True, blank=True, verbose_name=_("total_catch_yr_start"))
    total_catch_yr_w = models.FloatField(null=True, blank=True, verbose_name=_("total_catch_yr_w"))
    total_catch_yr_wo = models.FloatField(null=True, blank=True, verbose_name=_("total_catch_yr_wo"))
    total_catch_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_total_catch_thread", on_delete=models.SET_NULL)

    ice_preserved_catch_pc_start = models.FloatField(default=0, validators=[pc_as_float], verbose_name=_("ice_preserved_catch_pc_start"))
    ice_preserved_catch_pc_w = models.FloatField(default=0, validators=[pc_as_float], verbose_name=_("ice_preserved_catch_pc_w"))
    ice_preserved_catch_pc_wo = models.FloatField(default=0, validators=[pc_as_float], verbose_name=_("ice_preserved_catch_pc_wo"))
    ice_preserved_catch_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_ice_preserved_catch_thread", on_delete=models.SET_NULL)

    energy_ef_co2_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("energy_emission_factor_co2_t2_start"))
    energy_ef_co2_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("energy_emission_factor_co2_t2_w"))
    energy_ef_co2_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("energy_emission_factor_co2_t2_wo"))

    energy_ef_ch4_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("energy_emission_factor_ch4_t2_start"))
    energy_ef_ch4_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("energy_emission_factor_ch4_t2_w"))
    energy_ef_ch4_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("energy_emission_factor_ch4_t2_wo"))

    energy_ef_n2o_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("energy_emission_factor_n2o_t2_start"))
    energy_ef_n2o_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("energy_emission_factor_n2o_t2_w"))
    energy_ef_n2o_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("energy_emission_factor_n2o_t2_wo"))

    refrigerant_lost_per_tonne_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("refrigerant_lost_per_tonne_t2_start"))
    refrigerant_lost_per_tonne_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("refrigerant_lost_per_tonne_t2_w"))
    refrigerant_lost_per_tonne_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("refrigerant_lost_per_tonne_t2_wo"))

    refrigerant_gwp_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("refrigerant_gwp_t2_start"))
    refrigerant_gwp_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("refrigerant_gwp_t2_w"))
    refrigerant_gwp_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("refrigerant_gwp_t2_wo"))

    tonnes_of_ice_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("tonnes_of_ice_t2_start"))
    tonnes_of_ice_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("tonnes_of_ice_t2_w"))
    tonnes_of_ice_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("tonnes_of_ice_t2_wo"))

    inshore_ice_production_kwh_per_tonne_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("inshore_ice_production_kwh_per_tonne_t2_start"))
    inshore_ice_production_kwh_per_tonne_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("inshore_ice_production_kwh_per_tonne_t2_w"))
    inshore_ice_production_kwh_per_tonne_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("inshore_ice_production_kwh_per_tonne_t2_wo"))

    fui_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("fui_t2_start"))
    fui_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("fui_t2_w"))
    fui_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("fui_t2_wo"))

    inshore_ice_production_country_t2 = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("inshore_ice_production_country_t2"))

    implementation_year_t2 = models.IntegerField(null=True, blank=True, verbose_name=_("implementation_year_t2"))


class SmallFishery(Fishery):
    gear_type_start = models.ForeignKey(SmallFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_start", verbose_name=_("gear_type_start"))
    gear_type_w = models.ForeignKey(SmallFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_w", verbose_name=_("gear_type_w"))
    gear_type_wo = models.ForeignKey(SmallFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_wo", verbose_name=_("gear_type_wo"))
    gear_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_gear_type_thread", on_delete=models.SET_NULL)
    fishery_type = models.ForeignKey(FisheryType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("fishery_type"))


class LargeFishery(Fishery):
    gear_type_start = models.ForeignKey(LargeFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_start", verbose_name=_("gear_type_start"))
    gear_type_w = models.ForeignKey(LargeFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_w", verbose_name=_("gear_type_w"))
    gear_type_wo = models.ForeignKey(LargeFisheryGearType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gear_type_wo", verbose_name=_("gear_type_wo"))
    gear_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_gear_type_thread", on_delete=models.SET_NULL)
    fish_type = models.ForeignKey(FishType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("fish_type"))


class Aquaculture(Module):
    annual_production_start = models.FloatField(null=True, blank=True, verbose_name=_("annual_production_start"))
    annual_production_w = models.FloatField(null=True, blank=True, verbose_name=_("annual_production_w"))
    annual_production_wo = models.FloatField(null=True, blank=True, verbose_name=_("annual_production_wo"))

    n2o_from_production_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("n2o_from_production_t2_start"))
    n2o_from_production_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("n2o_from_production_t2_w"))
    n2o_from_production_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("n2o_from_production_t2_wo"))

    electricity_used_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("electricity_used_t2_start"))
    electricity_used_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("electricity_used_t2_w"))
    electricity_used_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("electricity_used_t2_wo"))

    electricity_ef_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("electricity_ef_t2_start"))  # TODO: Rename to n2o_fish_production
    electricity_ef_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("electricity_ef_t2_w"))
    electricity_ef_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("electricity_ef_t2_wo"))


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

    @property
    def submodules(self) -> list["Submodule"]:
        return list(self.input_entries.all())


class InputEntry(Submodule):
    parent = models.ForeignKey(Input, on_delete=models.CASCADE, related_name="input_entries")
    input_type = models.ForeignKey(InputType, on_delete=models.CASCADE, verbose_name=_("input_type"))

    value_start = models.FloatField(verbose_name=_("value_start"))
    value_w = models.FloatField(verbose_name=_("value_w"))
    value_wo = models.FloatField(verbose_name=_("value_wo"))
    value_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_value_thread")

    co2_emissions_t2 = models.FloatField(null=True, blank=True, verbose_name=_("co2_emissions_t2"))
    n2o_emissions_t2 = models.FloatField(null=True, blank=True, verbose_name=_("n2o_emissions_t2"))
    co2_e_emissions_t2 = models.FloatField(null=True, blank=True, verbose_name=_("co2_e_emissions_t2"))

    implementation_year_t2 = models.IntegerField(null=True, blank=True, verbose_name=_("implementation_year_t2"))


class EmissionFactorSource(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class Energy(Module):
    pass

    @property
    def submodules(self) -> list["Submodule"]:
        return list(self.electricities.all()) + list(self.fuels.all())


class Electricity(Submodule):
    parent = models.ForeignKey(Energy, on_delete=models.CASCADE, null=True, blank=True, related_name="electricities")
    country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("country"))

    mwh_start = models.FloatField(null=True, blank=True, verbose_name=_("mwh_start"))
    mwh_w = models.FloatField(null=True, blank=True, verbose_name=_("mwh_w"))
    mwh_wo = models.FloatField(null=True, blank=True, verbose_name=_("mwh_wo"))
    mwh_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_mwh_thread")

    mwh_renewables_start = models.FloatField(null=True, blank=True, verbose_name=_("mwh_renewables_start"))
    mwh_renewables_w = models.FloatField(null=True, blank=True, verbose_name=_("mwh_renewables_w"))
    mwh_renewables_wo = models.FloatField(null=True, blank=True, verbose_name=_("mwh_renewables_wo"))
    mwh_renewables_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_mwh_renewables_thread")

    electricity_ef_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_start"))
    electricity_ef_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_w"))
    electricity_ef_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_wo"))

    transmission_loss_start = models.FloatField(default=0.1, verbose_name=_("transmission_loss_start"))
    transmission_loss_w = models.FloatField(default=0.1, verbose_name=_("transmission_loss_w"))
    transmission_loss_wo = models.FloatField(default=0.1, verbose_name=_("transmission_loss_wo"))

    ef_source = models.ForeignKey(EmissionFactorSource, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("ef_source"))

    def save(self, *args, **kwargs):

        if self.pk is None:
            self.ef_source = EmissionFactorSource.objects.get_or_create(name="Operating Margin")[0]

        return super().save(*args, **kwargs)


class Fuel(Submodule):
    parent = models.ForeignKey(Energy, on_delete=models.CASCADE, null=True, blank=True, related_name="fuels")
    fuel_type = models.ForeignKey(FuelType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("fuel_type"))

    fuel_consumption_start = models.FloatField(null=True, blank=True, verbose_name=_("fuel_consumption_start"))
    fuel_consumption_w = models.FloatField(null=True, blank=True, verbose_name=_("fuel_consumption_w"))
    fuel_consumption_wo = models.FloatField(null=True, blank=True, verbose_name=_("fuel_consumption_wo"))
    fuel_consumption_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fuel_consumption_thread")

    energy_ef_co2_t2 = models.FloatField(null=True, blank=True, verbose_name=_("ef_co2_t2"))
    energy_ef_ch4_t2 = models.FloatField(null=True, blank=True, verbose_name=_("ef_ch4_t2"))
    energy_ef_n2o_t2 = models.FloatField(null=True, blank=True, verbose_name=_("ef_n2o_t2"))

    account_for_co2 = models.BooleanField(default=False, verbose_name=_("account_for_co2"))


class IrrigationSystemType(models.Model):
    module_types = models.ManyToManyField(ModuleType, related_name="irrigation_system_types", null=True, blank=True)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class EnergySourceType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.id}) {self.name}"


class Irrigation(Module):
    pass

    @property
    def submodules(self) -> list["Submodule"]:
        return list(self.irrigation_systems.all()) + list(self.irrigation_phases.all())


class IrrigationSystem(Submodule):
    parent = models.ForeignKey(Irrigation, on_delete=models.CASCADE, null=True, blank=True, related_name="irrigation_systems")
    irrigation_system_type = models.ForeignKey(IrrigationSystemType, on_delete=models.CASCADE, null=True, blank=True, related_name="irrigation_systems", verbose_name=_("irrigation_system_type"))

    ha_start = models.FloatField(null=True, blank=True, verbose_name=_("ha_start"))
    ha_w = models.FloatField(null=True, blank=True, verbose_name=_("ha_w"))
    ha_wo = models.FloatField(null=True, blank=True, verbose_name=_("ha_wo"))
    ha_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_ha_thread")

    ef_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_start"))
    ef_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_w"))
    ef_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_wo"))

    def __str__(self):
        return f"({self.id}) {self.irrigation_system_type}"


class IrrigationPhase(Submodule):
    parent = models.ForeignKey(Irrigation, on_delete=models.CASCADE, null=True, blank=True, related_name="irrigation_phases")
    irrigation_system_type = models.ForeignKey(IrrigationSystemType, on_delete=models.CASCADE, null=True, blank=True, related_name="irrigation_phases", verbose_name=_("irrigation_system_type"))
    fuel_type = models.ForeignKey(FuelType, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("fuel_type"))
    well_depth = models.FloatField(null=True, blank=True, verbose_name=_("well_depth"))

    ha_start = models.FloatField(null=True, blank=True, verbose_name=_("ha_start"))
    ha_w = models.FloatField(null=True, blank=True, verbose_name=_("ha_w"))
    ha_wo = models.FloatField(null=True, blank=True, verbose_name=_("ha_wo"))
    ha_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_ha_thread")

    gross_irrigation_water_start = models.FloatField(null=True, blank=True, verbose_name=_("gross_irrigation_water_start"))
    gross_irrigation_water_w = models.FloatField(null=True, blank=True, verbose_name=_("gross_irrigation_water_w"))
    gross_irrigation_water_wo = models.FloatField(null=True, blank=True, verbose_name=_("gross_irrigation_water_wo"))
    gross_irrigation_water_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_gross_irrigation_water_thread")

    power_origin_country_t2 = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("power_origin_country_t2"))

    ef_co2_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("ef_co2_t2_start"))
    ef_co2_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("ef_co2_t2_w"))
    ef_co2_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("ef_co2_t2_wo"))

    ef_ch4_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("ef_ch4_t2_start"))
    ef_ch4_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("ef_ch4_t2_w"))
    ef_ch4_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("ef_ch4_t2_wo"))

    ef_n2o_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("ef_n2o_t2_start"))
    ef_n2o_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("ef_n2o_t2_w"))
    ef_n2o_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("ef_n2o_t2_wo"))

    transmission_loss_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("transmission_loss_t2_start"))
    transmission_loss_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("transmission_loss_t2_w"))
    transmission_loss_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("transmission_loss_t2_wo"))

    average_pressure_t2 = models.FloatField(null=True, blank=True, verbose_name=_("average_pressure_t2"))

    total_dynamic_head_t2 = models.FloatField(null=True, blank=True, verbose_name=_("total_dynamic_head_t2"))

    pumping_efficiency_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("pumping_efficiency_t2_start"))
    pumping_efficiency_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("pumping_efficiency_t2_w"))
    pumping_efficiency_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("pumping_efficiency_t2_wo"))

    def __str__(self):
        return f"({self.id}) {self.irrigation_system_type}"


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

    building_type = models.ForeignKey(BuildingType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_building_type", verbose_name=_("building_type"))
    building_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_building_type_thread", on_delete=models.SET_NULL)

    area_m2_start = models.FloatField(null=True, blank=True, verbose_name=_("area_m2_start"))
    area_m2_w = models.FloatField(null=True, blank=True, verbose_name=_("area_m2_w"))
    area_m2_wo = models.FloatField(null=True, blank=True, verbose_name=_("area_m2_wo"))
    area_m2_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_surface_thread", on_delete=models.SET_NULL)

    ef_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_start"))
    ef_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_w"))
    ef_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_wo"))


class Road(Submodule):
    parent = models.ForeignKey("api.Settlement", on_delete=models.CASCADE, null=True, blank=True, related_name="roads")

    road_type = models.ForeignKey(RoadType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_road_type", verbose_name=_("road_type"))
    road_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_road_type_thread", on_delete=models.SET_NULL)

    length_km_start = models.FloatField(null=True, blank=True, verbose_name=_("length_km_start"))
    length_km_w = models.FloatField(null=True, blank=True, verbose_name=_("length_km_w"))
    length_km_wo = models.FloatField(null=True, blank=True, verbose_name=_("length_km_wo"))
    length_km_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_length_km_thread", on_delete=models.SET_NULL)

    width_m_start = models.FloatField(null=True, blank=True, verbose_name=_("width_m_start"))
    width_m_w = models.FloatField(null=True, blank=True, verbose_name=_("width_m_w"))
    width_m_wo = models.FloatField(null=True, blank=True, verbose_name=_("width_m_wo"))
    width_m_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_width_m_thread", on_delete=models.SET_NULL)

    ef_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_start"))
    ef_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_w"))
    ef_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_wo"))


class OtherInfrastructure(Submodule):
    parent = models.ForeignKey("api.Settlement", on_delete=models.CASCADE, null=True, blank=True, related_name="other_infrastructures")

    area_m2_start = models.FloatField(null=True, blank=True, verbose_name=_("area_m2_start"))
    area_m2_w = models.FloatField(null=True, blank=True, verbose_name=_("area_m2_w"))
    area_m2_wo = models.FloatField(null=True, blank=True, verbose_name=_("area_m2_wo"))
    area_m2_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_area_m2_thread", on_delete=models.SET_NULL)

    ef_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_start"))
    ef_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_w"))
    ef_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("ef_t2_wo"))


class OrganicSoil(LandModuleFixed):
    drainage_area_start = models.FloatField(default=0, verbose_name=_("drainage_area_start"))
    drainage_area_w = models.FloatField(default=0, verbose_name=_("drainage_area_w"))
    drainage_area_wo = models.FloatField(default=0, verbose_name=_("drainage_area_wo"))
    drainage_area_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_drainage_area_thread", on_delete=models.SET_NULL)

    area_not_drained_start = models.FloatField(default=0, verbose_name=_("area_not_drained_start"))
    area_not_drained_w = models.FloatField(default=0, verbose_name=_("area_not_drained_w"))
    area_not_drained_wo = models.FloatField(default=0, verbose_name=_("area_not_drained_wo"))
    area_not_drained_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_area_not_drained_thread", on_delete=models.SET_NULL)

    ditches_area_start = models.FloatField(default=0, verbose_name=_("ditches_area_start"))
    ditches_area_w = models.FloatField(default=0, verbose_name=_("ditches_area_w"))
    ditches_area_wo = models.FloatField(default=0, verbose_name=_("ditches_area_wo"))
    ditches_area_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_ditches_area_thread", on_delete=models.SET_NULL)

    fire_type_start = models.ForeignKey(FireType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fire_type_start", verbose_name=_("fire_type_start"))
    fire_type_w = models.ForeignKey(FireType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fire_type_w", verbose_name=_("fire_type_w"))
    fire_type_wo = models.ForeignKey(FireType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_fire_type_wo", verbose_name=_("fire_type_wo"))
    fire_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_fire_type_thread", on_delete=models.SET_NULL)

    soil_fire_periodicity_start = models.FloatField(null=True, blank=True, verbose_name=_("soil_fire_periodicity_start"))
    soil_fire_periodicity_w = models.FloatField(null=True, blank=True, verbose_name=_("soil_fire_periodicity_w"))
    soil_fire_periodicity_wo = models.FloatField(null=True, blank=True, verbose_name=_("soil_fire_periodicity_wo"))
    soil_fire_periodicity_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_soil_fire_periodicity_thread", on_delete=models.SET_NULL)

    soil_fire_impact_percentage_start = models.FloatField(null=True, blank=True, verbose_name=_("soil_fire_impact_percentage_start"))
    soil_fire_impact_percentage_w = models.FloatField(null=True, blank=True, verbose_name=_("soil_fire_impact_percentage_w"))
    soil_fire_impact_percentage_wo = models.FloatField(null=True, blank=True, verbose_name=_("soil_fire_impact_percentage_wo"))
    soil_fire_impact_percentage_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_soil_fire_impact_percentage_thread", on_delete=models.SET_NULL)

    onsite_co2_drainge_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("onsite_co2_drainge_t2_start"))
    onsite_co2_drainge_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("onsite_co2_drainge_t2_w"))
    onsite_co2_drainge_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("onsite_co2_drainge_t2_wo"))

    onsite_ch4_drainge_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("onsite_ch4_drainge_t2_start"))
    onsite_ch4_drainge_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("onsite_ch4_drainge_t2_w"))
    onsite_ch4_drainge_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("onsite_ch4_drainge_t2_wo"))

    onsite_n2o_drainge_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("onsite_n2o_drainge_t2_start"))
    onsite_n2o_drainge_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("onsite_n2o_drainge_t2_w"))
    onsite_n2o_drainge_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("onsite_n2o_drainge_t2_wo"))

    offsite_doc_drainge_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("offsite_doc_drainge_t2_start"))
    offsite_doc_drainge_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("offsite_doc_drainge_t2_w"))
    offsite_doc_drainge_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("offsite_doc_drainge_t2_wo"))

    offsite_ch4_drainge_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("offsite_ch4_drainge_t2_start"))
    offsite_ch4_drainge_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("offsite_ch4_drainge_t2_w"))
    offsite_ch4_drainge_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("offsite_ch4_drainge_t2_wo"))

    onsite_co2_rewetting_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("onsite_co2_rewetting_t2_start"))
    onsite_co2_rewetting_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("onsite_co2_rewetting_t2_w"))
    onsite_co2_rewetting_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("onsite_co2_rewetting_t2_wo"))

    onsite_ch4_rewetting_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("onsite_ch4_rewetting_t2_start"))
    onsite_ch4_rewetting_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("onsite_ch4_rewetting_t2_w"))
    onsite_ch4_rewetting_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("onsite_ch4_rewetting_t2_wo"))

    onsite_n2o_rewetting_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("onsite_n2o_rewetting_t2_start"))
    onsite_n2o_rewetting_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("onsite_n2o_rewetting_t2_w"))
    onsite_n2o_rewetting_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("onsite_n2o_rewetting_t2_wo"))

    offsite_doc_rewetting_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("offsite_doc_rewetting_t2_start"))
    offsite_doc_rewetting_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("offsite_doc_rewetting_t2_w"))
    offsite_doc_rewetting_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("offsite_doc_rewetting_t2_wo"))

    mean_dry_matter_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("mean_dry_matter_t2_start"))
    mean_dry_matter_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("mean_dry_matter_t2_w"))
    mean_dry_matter_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("mean_dry_matter_t2_wo"))

    fire_on_soil_co2_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("fire_on_soil_co2_t2_start"))
    fire_on_soil_co2_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("fire_on_soil_co2_t2_w"))
    fire_on_soil_co2_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("fire_on_soil_co2_t2_wo"))

    fire_on_soil_co_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("fire_on_soil_co_t2_start"))
    fire_on_soil_co_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("fire_on_soil_co_t2_w"))
    fire_on_soil_co_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("fire_on_soil_co_t2_wo"))

    fire_on_soil_ch4_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("fire_on_soil_ch4_t2_start"))
    fire_on_soil_ch4_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("fire_on_soil_ch4_t2_w"))
    fire_on_soil_ch4_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("fire_on_soil_ch4_t2_wo"))

    ##### Peat Extraction #####

    peat_type = models.ForeignKey(PeatType, on_delete=models.CASCADE, null=True, blank=True, default=utils.get_default_peat_type, related_name="%(class)s_peat_type", verbose_name=_("peat_type"))
    peat_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_type_thread", on_delete=models.SET_NULL)

    peat_area_start = models.FloatField(null=True, blank=True, verbose_name=_("peat_area_start"))
    peat_area_w = models.FloatField(null=True, blank=True, verbose_name=_("peat_area_w"))
    peat_area_wo = models.FloatField(null=True, blank=True, verbose_name=_("peat_area_wo"))
    peat_area_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_area_thread", on_delete=models.SET_NULL)

    peat_ditches_area_start = models.FloatField(null=True, blank=True, verbose_name=_("peat_ditches_area_start"))
    peat_ditches_area_w = models.FloatField(null=True, blank=True, verbose_name=_("peat_ditches_area_w"))
    peat_ditches_area_wo = models.FloatField(null=True, blank=True, verbose_name=_("peat_ditches_area_wo"))
    peat_ditches_area_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_ditches_area_thread", on_delete=models.SET_NULL)

    peat_extraction_height_start = models.FloatField(null=True, blank=True, verbose_name=_("peat_extraction_height_start"))
    peat_extraction_height_w = models.FloatField(null=True, blank=True, verbose_name=_("peat_extraction_height_w"))
    peat_extraction_height_wo = models.FloatField(null=True, blank=True, verbose_name=_("peat_extraction_height_wo"))
    peat_extraction_height_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_extraction_height_thread", on_delete=models.SET_NULL)

    is_peat_for_energy_start = models.BooleanField(default=False, verbose_name=_("is_peat_for_energy_start"))
    is_peat_for_energy_w = models.BooleanField(default=False, verbose_name=_("is_peat_for_energy_w"))
    is_peat_for_energy_wo = models.BooleanField(default=False, verbose_name=_("is_peat_for_energy_wo"))
    is_peat_for_energy_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_peat_is_for_energy_thread", on_delete=models.SET_NULL)

    onsite_co2_peat_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("onsite_co2_peat_t2_start"))
    onsite_co2_peat_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("onsite_co2_peat_t2_w"))
    onsite_co2_peat_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("onsite_co2_peat_t2_wo"))

    onsite_n2o_peat_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("onsite_n2o_peat_t2_start"))
    onsite_n2o_peat_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("onsite_n2o_peat_t2_w"))
    onsite_n2o_peat_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("onsite_n2o_peat_t2_wo"))

    offsite_doc_peat_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("offsite_doc_peat_t2_start"))
    offsite_doc_peat_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("offsite_doc_peat_t2_w"))
    offsite_doc_peat_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("offsite_doc_peat_t2_wo"))

    offsite_ch4_peat_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("offsite_ch4_peat_t2_start"))
    offsite_ch4_peat_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("offsite_ch4_peat_t2_w"))
    offsite_ch4_peat_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("offsite_ch4_peat_t2_wo"))

    peat_density_t2_start = models.FloatField(null=True, blank=True, verbose_name=_("peat_density_t2_start"))
    peat_density_t2_w = models.FloatField(null=True, blank=True, verbose_name=_("peat_density_t2_w"))
    peat_density_t2_wo = models.FloatField(null=True, blank=True, verbose_name=_("peat_density_t2_wo"))

    def save(self, *args, **kwargs):
        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name_en="Organic Soil")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        return super().save(*args, **kwargs)


class Settlement(LandModuleFixed, SingleBiomassModule):

    settlement_type_start = models.ForeignKey(SettlementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_settlement_type_start", verbose_name=_("settlement_type_start"))
    settlement_type_w = models.ForeignKey(SettlementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_settlement_type_w", verbose_name=_("settlement_type_w"))
    settlement_type_wo = models.ForeignKey(SettlementType, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_settlement_type_wo", verbose_name=_("settlement_type_wo"))
    settlement_type_thread = models.OneToOneField("api.CommentThread", null=True, blank=True, related_name="%(class)s_settlement_type_thread", on_delete=models.SET_NULL)

    @property
    def submodules(self) -> list["Submodule"]:
        return list(self.buildings.all()) + list(self.roads.all()) + list(self.other_infrastructures.all())

    # NOTE: Why having AGB and BGB AND Biomass when Biomass = AGB + BGB?
    def get_biomass_t2(self, scenario: utils.ScenarioTypes):
        return getattr(self, f"biomass_t2_{scenario.value}", None)

    def save(self, *args, **kwargs):

        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name_en="Settlement")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        return super().save(*args, **kwargs)


class SetAside(LandModule, SingleBiomassModule):

    is_set_aside_start = models.BooleanField(default=False, verbose_name=_("is_set_aside_start"))
    is_set_aside_w = models.BooleanField(default=False, verbose_name=_("is_set_aside_w"))
    is_set_aside_wo = models.BooleanField(default=False, verbose_name=_("is_set_aside_wo"))

    # NOTE: Why having AGB and BGB AND Biomass when Biomass = AGB + BGB?
    def get_biomass_t2(self, scenario: utils.ScenarioTypes):
        return getattr(self, f"biomass_t2_{scenario.value}", None)

    def save(self, *args, **kwargs):

        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name_en="Set Aside")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        return super().save(*args, **kwargs)


class OtherLand(LandModule, SingleBiomassModule):
    is_degraded_land_start = models.BooleanField(default=False, verbose_name=_("is_degraded_land_start"))
    is_degraded_land_w = models.BooleanField(default=False, verbose_name=_("is_degraded_land_w"))
    is_degraded_land_wo = models.BooleanField(default=False, verbose_name=_("is_degraded_land_wo"))

    # NOTE: Why having AGB and BGB AND Biomass when Biomass = AGB + BGB?
    def get_biomass_t2(self, scenario: utils.ScenarioTypes):
        return getattr(self, f"biomass_t2_{scenario.value}", None)

    def save(self, *args, **kwargs):
        if not self.land_use_type_start:
            self.land_use_type_start = LandUseType.objects.get(name_en="Other Land")
            self.land_use_type_w = self.land_use_type_start
            self.land_use_type_wo = self.land_use_type_start

        return super().save(*args, **kwargs)


class LandUseChange(Module):
    module_type_start = models.ForeignKey(ModuleType, on_delete=models.CASCADE, related_name="start", verbose_name=_("module_type_start"))
    module_type_w = models.ForeignKey(ModuleType, on_delete=models.CASCADE, related_name="w", verbose_name=_("module_type_w"))
    module_type_wo = models.ForeignKey(ModuleType, on_delete=models.CASCADE, related_name="wo", verbose_name=_("module_type_wo"))
    module_type_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="land_use_change_module_type_thread")

    area = models.FloatField(verbose_name=_("area"))

    is_fire_used_start = models.BooleanField(default=False, verbose_name=_("is_fire_used_start"))
    is_fire_used_w = models.BooleanField(default=False, verbose_name=_("is_fire_used_w"))
    is_fire_used_wo = models.BooleanField(default=False, verbose_name=_("is_fire_used_wo"))
    is_fire_used_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="land_use_change_is_fire_used_thread")

    dry_matter_start = models.FloatField(null=True, blank=True, default=0, verbose_name=_("dry_matter_start"))
    dry_matter_w = models.FloatField(null=True, blank=True, default=0, verbose_name=_("dry_matter_w"))
    dry_matter_wo = models.FloatField(null=True, blank=True, default=0, verbose_name=_("dry_matter_wo"))
    dry_matter_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, null=True, blank=True, related_name="land_use_change_dry_matter_thread")

    organic_soil = models.OneToOneField(OrganicSoil, on_delete=models.CASCADE, null=True, blank=True, related_name="land_use_change_organic_soil", verbose_name=_("organic_soil"))

    def is_filled(self):
        return self.area is not None and self.module_type_start is not None and self.module_type_w is not None and self.module_type_wo is not None

    def get_modules(self) -> tuple[LandModule]:
        """
        Retrieves the land use change modules associated with each scenario of a given LandUseChange object.

        Args:
            luc (LandUseChange): The LandUseChange object.

        Returns:
            tuple[LandModule]: A tuple containing the land use change modules for each scenario.

        Raises:
            Exception: If at least one module is missing.
        """
        modules = (
            getattr(self.activity, self.module_type_start.class_name.lower(), None).first(),
            getattr(self.activity, self.module_type_w.class_name.lower(), None).first(),
            getattr(self.activity, self.module_type_wo.class_name.lower(), None).first(),
        )

        if not all(modules):
            raise Exception("At least one module is missing")

        return modules

    def get_module_types(self) -> tuple[ModuleType]:
        """
        Retrieves the module types associated with each scenario of a given LandUseChange object.

        Args:
            luc (LandUseChange): The LandUseChange object.

        Returns:
            tuple[ModuleType]: A tuple containing the module types for each scenario.

        Raises:
            Exception: If at least one module type is missing.
        """
        module_types = (self.module_type_start, self.module_type_w, self.module_type_wo)

        if not all(module_types):
            raise Exception("At least one module type is missing")

        return module_types


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


class Definition(models.Model):
    module_type = models.ForeignKey(ModuleType, on_delete=models.CASCADE, related_name="definitions")
    definitions = models.JSONField()

    def __str__(self):
        return f"({self.pk}) {self.module_type}"


class OrganizationType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"({self.pk}) {self.name}"


class FieldDefinition(models.Model):
    module_type = models.ForeignKey(ModuleType, on_delete=models.CASCADE, related_name="field_definitions")
    field_name = models.CharField(max_length=255, verbose_name=_("Field Name"))
    description = models.TextField(verbose_name=_("Field Description"))

    class Meta:
        unique_together = ("module_type", "field_name")
        verbose_name = _("Field Definition")
        verbose_name_plural = _("Field Definitions")

    def __str__(self):
        return f"{self.module_type}.{self.field_name}"
