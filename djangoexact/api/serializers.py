import logging as log
from enum import Enum
import uuid

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import Count, Model
from django.db.models.query import QuerySet
from django.forms.models import model_to_dict
from django.utils import timezone
from ipcc.models import GlobalWarmingPotential
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes
from rest_framework import serializers
from rest_framework.fields import empty
from simple_history.utils import update_change_reason
from abc import ABC, abstractmethod

import api.calculators as calcs
import api.utilities as utils
from api.models import CustomUser as User
from django.utils.text import slugify

from . import labels
from .models import (
    Module,
    Submodule,
    Activity,
    AnnualCropland,
    Aquaculture,
    Building,
    Climate,
    CoastalWetland,
    Comment,
    CommentThread,
    ConfigParam,
    Country,
    CustomUser,
    OtherLand,
    Electricity,
    Energy,
    FloodedRice,
    ForestDisturbance,
    ForestManagement,
    Fuel,
    FuelType,
    GasType,
    GLEAMRegion,
    Grassland,
    Input,
    InputEntry,
    InputType,
    IPCCRegion,
    Irrigation,
    IrrigationPhase,
    IrrigationSystem,
    LandUseChange,
    LandUseType,
    LargeFishery,
    Livestock,
    MAX_ACTIVITIES_PER_PROJECT,
    MacroFuelType,
    MacroInputType,
    MinorSeasonAnnualCropland,
    MinorSeasonFloodedRice,
    MinorSeasonPerennialCropland,
    ModuleType,
    Moisture,
    OrganicSoil,
    OtherInfrastructure,
    PerennialCropland,
    Project,
    ProjectInvitation,
    ProjectStatus,
    Region,
    Road,
    SetAside,
    Settlement,
    SmallFishery,
    SoilType,
    StatusType,
    ProjectMembership,
    ProjectNotificationPreference,
    Waterbody,
    LandModule,
    InvitationStatusType,
    ChangeRate,
    Note,
    FieldDefinition,
    ProjectTag,
    Storage,
    Processing,
    Packaging,
    Transport,
    StorageEntry,
    ProcessingEntry,
    PackagingEntry,
    TransportEntry,
    ProjectFileAttachment,
    ApplicationParameter,
    APIHealth,
    FuelUseType,
    PublicToken,
    EnergyEntry,
    HandInHandRegion,
    HandInHandCountry,
    HandInHandAssessment,
    AsyncJob,
)
from typing import Optional
from django.contrib.contenttypes.models import ContentType
import api.security as security
from django.conf import settings


class EmptySerializer(serializers.Serializer):
    pass


class ActionTypes(Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    RETRIEVE = "RETRIEVE"


def are_fields_filled(data, mandatory_fields):
    return all(list(map(lambda field: data.get(field, None) is not None, mandatory_fields)))


def generate_fields_for_scenarios(scenarios: list[str], mandatory_fields: list):
    fields = []
    for scenario in scenarios:
        fields += generate_fields_for_scenario(scenario, mandatory_fields)
    return fields


def generate_fields_for_scenario(scenario: str, mandatory_fields: list):
    fields = []
    for field in mandatory_fields:
        if scenario:
            fields.append(f"{field}_{scenario}")
        else:
            fields.append(field)
    return fields


def is_scenario_filled(data: dict, scenario: str, mandatory_fields: list):
    """
    Returns true if any of the fields for the given scenario are filled
    """
    return all(
        list(
            map(
                lambda field: data.get(f"{field}_{scenario}", data.get(f"{field}_{scenario}_id", None)) is not None,
                mandatory_fields,
            )
        )
    )


def get_filled_scenarios(data, mandatory_fields: list):
    """
    Returns a list of scenarios for which all mandatory fields are filled
    """
    scenarios = []
    if is_scenario_filled(data, "start", mandatory_fields):
        scenarios.append("start")
    if is_scenario_filled(data, "w", mandatory_fields):
        scenarios.append("w")
    if is_scenario_filled(data, "wo", mandatory_fields):
        scenarios.append("wo")
    return scenarios


def validate_module_fields(data, mandatory_fields: list):
    filled_scenarios = get_filled_scenarios(data, mandatory_fields)

    for scenario in filled_scenarios:
        mandatory_fields += generate_fields_for_scenario(scenario, mandatory_fields)

    if not are_fields_filled(data, mandatory_fields):
        raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")


class _SerializerRegistry(dict):
    """Lazily-populated allowlist of DRF serializer classes resolvable by
    dynamic name.

    Populated from this module's namespace on first miss and refreshed on
    later misses rather than snapshotted at import time: some lookups run
    while the module is still being imported (class bodies below call
    get_model_serializer), so an early snapshot would miss classes defined
    later and change resolution behavior. Hits cost O(1); a miss rescans the
    namespace before failing, which is what every lookup cost before caching.
    Restricting entries to serializer classes keeps dynamically-built,
    model-derived names from indexing arbitrary module globals.
    """

    def _refresh(self):
        self.update(
            (name, obj)
            for name, obj in globals().items()
            if isinstance(obj, type) and issubclass(obj, serializers.BaseSerializer)
        )

    def __missing__(self, key):
        self._refresh()
        # dict.__getitem__ on a subclass re-enters __missing__ for an absent
        # key, so raise directly instead of re-indexing after the refresh.
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        raise KeyError(key)

    def __contains__(self, key):
        if dict.__contains__(self, key):
            return True
        self._refresh()
        return dict.__contains__(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


_SERIALIZER_REGISTRY = _SerializerRegistry()


def _serializer_registry() -> dict:
    """Return the lazily-populated serializer allowlist registry."""
    return _SERIALIZER_REGISTRY


def get_model_serializer(model_arg):
    class GenericSerializer(serializers.ModelSerializer):
        class Meta:
            model = model_arg
            fields = "__all__"
            ref_name = model_arg.__name__

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

    try:
        return _serializer_registry()[model_arg.__name__ + "Serializer"]
    except KeyError:
        return GenericSerializer


def get_module_serializer(model_arg: Model, action=ActionTypes.RETRIEVE) -> serializers.ModelSerializer:
    try:
        match action:
            case ActionTypes.CREATE | ActionTypes.UPDATE:
                return _serializer_registry()[model_arg.__name__ + "WriteSerializer"]
            case ActionTypes.RETRIEVE:
                return _serializer_registry()[model_arg.__name__ + "ReadSerializer"]
    except KeyError:
        raise ValueError(f"Serializer for {model_arg.__name__} not found")


class EmissionSerializer(serializers.Serializer):
    gas_type = get_model_serializer(GasType)(many=False, read_only=True)
    value = serializers.FloatField()


class YearlyGasEmissionSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    gas_type = get_model_serializer(GasType)(many=False, read_only=True)
    emissions = EmissionSerializer(many=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class YearlyActivityEmissionSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    gas_type = get_model_serializer(GasType)(many=False, read_only=True)
    emissions = EmissionSerializer(many=True)
    activity = serializers.CharField()


class TotalResultSerializer(serializers.Serializer):
    total_w = serializers.FloatField()
    total_wo = serializers.FloatField()
    balance = serializers.FloatField()


class ResultSerializerFactory:
    @staticmethod
    def by(by: BreakdownTypes = BreakdownTypes.TOTAL):
        match by:
            case BreakdownTypes.TOTAL:
                return TotalResultSerializer
            case BreakdownTypes.GAS:
                return YearlyGasEmissionSerializer
            case BreakdownTypes.ACTIVITY:
                return YearlyActivityEmissionSerializer
            case BreakdownTypes.ACTIVITY_GAS:
                return YearlyActivityEmissionSerializer
            case _:
                raise ValueError("Invalid breakdown type")


class ResultSerializer(serializers.Serializer):
    serializer = TotalResultSerializer

    def __init__(self, *args, **kwargs):
        # Get the serializer passed in the constructor
        if "serializer" in kwargs:
            self.serializer = kwargs["serializer"]
            del kwargs["serializer"]
        if self.serializer == TotalResultSerializer:
            self.fields["total_w"] = serializers.FloatField()
            self.fields["total_wo"] = serializers.FloatField()
            self.fields["balance"] = serializers.FloatField()
        else:
            self.fields["total_w"] = self.serializer(many=True, required=False)
            self.fields["total_wo"] = self.serializer(many=True, required=False)
            self.fields["balance"] = self.serializer(many=True, required=False)

        super().__init__(*args, **kwargs)


class UserReadSerializer(serializers.ModelSerializer):
    country = get_model_serializer(Country)(many=False, read_only=True)

    class Meta:
        model = CustomUser
        fields = ["id", "email", "first_name", "last_name", "country", "organization", "is_opted_out_of_emails"]


class UserWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "email", "first_name", "last_name", "country", "organization", "is_opted_out_of_emails"]


class CountrySerializer(serializers.ModelSerializer):
    region = get_model_serializer(Region)(many=False, read_only=True)
    ipcc_region = get_model_serializer(IPCCRegion)(many=False, read_only=True)
    gleam_region = get_model_serializer(GLEAMRegion)(many=False, read_only=True)

    class Meta:
        model = Country
        fields = "__all__"
        ref_name = "Country"


class ProjectTagSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProjectTag
        fields = ["id", "name"]

    def validate_name(self, value):
        project = self.context["project"]
        user = self.context["user"]
        if not ProjectMembership.objects.filter(project=project, user=user).exists():
            raise serializers.ValidationError("User does not have permission to add tags to this project.")

        if ProjectTag.objects.filter(project=project, user=user, slug=slugify(value)).exists():
            raise serializers.ValidationError("Tag with this name already exists for this project.")

        return value


class ProjectSummarySerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField(read_only=True)
    country = serializers.StringRelatedField(many=False, read_only=True, source="country.name")
    tags = ProjectTagSerializer(many=True, read_only=True)
    activity_count = serializers.SerializerMethodField(read_only=True)
    module_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Project
        fields = ["id", "name", "country", "updated_at", "role", "tags", "created_at", "is_archived", "is_finalized", "activity_count", "module_count"]

    def get_role(self, obj):
        ctx = self.context.get("request", None)

        if not ctx:
            return []

        user = ctx.user
        user_project_group = ProjectMembership.objects.filter(user=user, project=obj).all()

        return [group.group.name for group in user_project_group] if user_project_group else []

    def get_activity_count(self, obj):
        cached = getattr(obj, "_activity_count", None)
        if cached is not None:
            return cached
        return obj.activities.count()

    def get_module_count(self, obj):
        cached = getattr(obj, "_module_count", None)
        if cached is not None:
            return cached
        return obj.activities.aggregate(c=Count("module_types"))["c"] or 0


class ProjectResultSerializer(serializers.Serializer):
    # activities = serializers.ListField(child=ResultSerializer())
    pass


class ReadProjectSerializer(serializers.ModelSerializer):
    climate = get_model_serializer(Climate)(many=False, read_only=True)
    country = CountrySerializer(many=False, read_only=True)
    moisture = get_model_serializer(Moisture)(many=False, read_only=True)
    soil_type = get_model_serializer(SoilType)(many=False, read_only=True)
    gw_potential = get_model_serializer(GlobalWarmingPotential)(many=False, read_only=True)
    status = get_model_serializer(ProjectStatus)(many=False, required=False, read_only=True)
    owner = UserReadSerializer(many=False, read_only=True)
    role = serializers.SerializerMethodField()
    total_hectares = serializers.SerializerMethodField()
    total_catch = serializers.SerializerMethodField()
    total_livestock = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()
    activity_count = serializers.SerializerMethodField(read_only=True)
    module_count = serializers.SerializerMethodField(read_only=True)

    capitalization_years = serializers.FloatField(read_only=True)

    def get_note(self, obj):
        return NoteSerializer(obj.note.first(), many=False).data if obj.note.exists() else None

    def get_activity_count(self, obj):
        cached = getattr(obj, "_activity_count", None)
        if cached is not None:
            return cached
        return obj.activities.count()

    def get_module_count(self, obj):
        cached = getattr(obj, "_module_count", None)
        if cached is not None:
            return cached
        return obj.activities.aggregate(c=Count("module_types"))["c"] or 0

    def get_role(self, obj):
        ctx = self.context.get("request", None)

        if not ctx:
            return []

        user = ctx.user
        user_project_group = ProjectMembership.objects.filter(user=user, project=obj).all()

        return [group.group.name for group in user_project_group] if user_project_group else []

    def get_total_hectares(self, obj):
        return sum([activity.get_land_modules_area() for activity in obj.activities.all()])

    def get_total_catch(self, obj):
        small_fisheries = SmallFishery.objects.filter(activity__project=obj).all()
        large_fisheries = LargeFishery.objects.filter(activity__project=obj).all()
        aquacultures = Aquaculture.objects.filter(activity__project=obj).all()

        def safe_sum(items, attr):
            return sum(getattr(item, attr) or 0 for item in items)

        scenario_based_catch = {
            "start": safe_sum(small_fisheries, "total_catch_yr_start") + safe_sum(large_fisheries, "total_catch_yr_start") + safe_sum(aquacultures, "annual_production_start"),
            "w": safe_sum(small_fisheries, "total_catch_yr_w") + safe_sum(large_fisheries, "total_catch_yr_w") + safe_sum(aquacultures, "annual_production_w"),
            "wo": safe_sum(small_fisheries, "total_catch_yr_wo") + safe_sum(large_fisheries, "total_catch_yr_wo") + safe_sum(aquacultures, "annual_production_wo"),
        }

        return scenario_based_catch

    def get_total_livestock(self, obj):
        livestock = Livestock.objects.filter(activity__project=obj).all()

        all_livestock_start = sum([animal.heads_number_start for animal in list(filter(lambda animal: animal.heads_number_start is not None, livestock))])
        all_livestock_w = sum([animal.heads_number_w for animal in list(filter(lambda animal: animal.heads_number_w is not None, livestock))])
        all_livestock_wo = sum([animal.heads_number_wo for animal in list(filter(lambda animal: animal.heads_number_wo is not None, livestock))])

        scenario_based_livestock = {
            "start": all_livestock_start,
            "w": all_livestock_w,
            "wo": all_livestock_wo,
        }

        return scenario_based_livestock

    class Meta:
        model = Project
        fields = "__all__"
        ref_name = "Project"


class WriteProjectSerializer(serializers.ModelSerializer):
    climate = serializers.PrimaryKeyRelatedField(queryset=Climate.objects.all(), required=False, allow_null=True, write_only=True)
    country = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all(), required=True, write_only=True)
    moisture = serializers.PrimaryKeyRelatedField(queryset=Moisture.objects.all(), required=False, allow_null=True, write_only=True)
    soil_type = serializers.PrimaryKeyRelatedField(queryset=SoilType.objects.all(), required=False, allow_null=True, write_only=True)
    gw_potential = serializers.PrimaryKeyRelatedField(queryset=GlobalWarmingPotential.objects.all(), required=True, write_only=True)

    class Meta:
        model = Project
        exclude = ["owner"]
        ref_name = "Project"

    def sanitize_soc_ref_t2(self, data):
        """
        Sanitizes the 'soc_ref_t2' field in the provided data dictionary.

        If the 'soc_ref_t2' field is present and its value is an empty string,
        it sets the value of 'soc_ref_t2' to None.

        Args:
            data (dict): The data dictionary containing the 'soc_ref_t2' field.

        Returns:
            None: The function modifies the input dictionary in place.
        """
        soc_ref_t2 = data.get("soc_ref_t2", None)
        if soc_ref_t2 is not None and soc_ref_t2 == "":
            data["soc_ref_t2"] = None

    def validate(self, data):
        if self.instance:
            project: Project = self.instance
            cost = data.get("cost", None)
            new_years = data.get("implementation_years", None)
            is_locking = data.get("is_locked", None)
            user = self.context["request"].user
            is_archived = data.get("is_archived", None)
            is_finalized = data.get("is_finalized", None)
            is_public = data.get("is_public", None)

            last_year_of_accounting = data.get("last_year_of_accounting", None)

            if project.is_archived and is_archived is not False:
                raise serializers.ValidationError("Archived projects cannot be modified")

            is_only_public_change = is_public is not None and set(data.keys()) <= {"is_public"}

            if project.is_finalized and is_finalized is not False and not is_only_public_change:
                raise serializers.ValidationError("Finalized projects cannot be modified except for their publication status")

            if not project.is_archived and is_archived:
                data["archived_at"] = timezone.now()

            if is_archived and project.members.filter(group__name="Admin").count() > 1:
                raise serializers.ValidationError("Project cannot be archived if there are multiple admins")

            errors = security.check_permission("change_public_project_flag", user, project)
            if is_public is not None and errors is not None:
                raise serializers.ValidationError("User does not have permission to change the public project flag")

            if cost is not None:
                total_activity_cost = project.activities.all().values_list("cost", flat=True)

                if sum(total_activity_cost) > data.get("cost"):
                    raise serializers.ValidationError("Total cost of activities cannot be greater than project cost")

            if last_year_of_accounting is not None:
                activities: list[Activity] = project.activities.all()

                if any(a.start_year + a.duration > last_year_of_accounting for a in activities):
                    raise serializers.ValidationError("Last year of accounting cannot be less than the start year of current activities")

            if new_years is not None:
                project.implementation_years = new_years

                if project.start_year_of_activities + project.implementation_years > project.last_year_of_accounting:
                    raise serializers.ValidationError("Project implementation phase duration cannot exceed the last year of accounting")

                for activity in project.activities.all():
                    if activity.duration_t2 and activity.duration_t2 > new_years:
                        log.warning(f"Activity {activity.name} duration_t2 is greater than project implementation years. Setting activity duration_t2 to project implementation years.")
                        activity.duration_t2 = new_years
                        activity.save()
                project.save()

            project._check_lock_expiration()

            if project.is_locked and project.locked_by != user and not user.is_staff:
                log.warning(f"Project is already locked by: {project.locked_by.email}")
                raise serializers.ValidationError("The project is already locked")

            # If the project is not locked, or a lock is requested
            if not project.is_locked or is_locking is True:
                if project.is_locked and project.locked_by != user and not user.is_staff:
                    log.warning(f"Project is already locked by: {project.locked_by.email}")
                    raise serializers.ValidationError("The project is already locked")

                if project.is_locked:
                    project.refresh_lock()
                else:
                    project.lock(self.context["request"].user)

            # If an unlock is requested
            elif is_locking is False:
                is_user_authorized = user.is_superuser or project.locked_by == user or user.memberships.filter(user=user, project=project, group__name="Admin").exists()

                if not is_user_authorized:
                    log.error("User does not have permission to unlock the project")
                    raise serializers.ValidationError("User does not have permission to unlock the project", code="permission_denied")

                project.unlock()

        if not self.instance:
            if self.context["request"].user.projects.filter(name=data.get("name")).exists():
                raise serializers.ValidationError("Project with the same name already exists")

            data["owner"] = self.context["request"].user

        return super().validate(data)

    def is_valid(self, *, raise_exception=False):
        # NOTE: This is a workaround made as a favor to the frontend team. The frontend sends an empty string due to a bug in the form.
        # Ask the frontend team if this is still necessary before removing it.
        self.sanitize_soc_ref_t2(self.initial_data)
        return super().is_valid(raise_exception=raise_exception)


class ModuleExportSerializer(serializers.Serializer):
    """Generic serializer for exporting any module type."""

    def _serialize_comment(self, comment):
        """Serialize a single comment with its replies."""
        comment_data = {
            'content': comment.content,
            'author_email': comment.author.email if comment.author else None,
            'date_created': comment.date_created.isoformat() if comment.date_created else None,
        }
        # Include replies recursively
        if comment.replies.exists():
            comment_data['replies'] = [
                self._serialize_comment(reply) for reply in comment.replies.all()
            ]
        return comment_data

    def _serialize_thread(self, thread):
        """Serialize a CommentThread with all its comments."""
        if thread is None:
            return None

        # Get top-level comments only (those without a parent)
        top_level_comments = thread.comments.filter(parent__isnull=True).order_by('date_created')

        return {
            'comments': [self._serialize_comment(comment) for comment in top_level_comments]
        }

    def to_representation(self, instance):
        """Export all model fields except relations that will be recreated."""
        data = {}
        # Include original ID so the importer can remap cross-module
        # OneToOneField references (e.g. Settlement.land_use_change →
        # LandUseChange) whose PKs change in the target database.
        data['_original_id'] = instance.id
        # NOTE: 'status' and 'last_modified' are exported on purpose.
        # An appraisal is a record of the numbers as they were computed, so the
        # round trip has to carry the module's computed state, not just its
        # inputs. 'status' is what makes the results endpoint serve a module at
        # all (it refuses anything that is not READY), and 'last_modified' is
        # what validates the cache: is_cached_results_valid() compares
        # last_cached_at against it, so re-stamping it at import time would
        # silently invalidate every restored result.
        excluded_fields = (
            'id', 'activity', 'data_source', 'note',
            'history', 'parent'
        )
        for field in instance._meta.get_fields():
            if field.name in excluded_fields:
                continue
            # Skip reverse relations (they have no DB column)
            if not hasattr(field, 'column'):
                continue
            if hasattr(field, 'get_internal_type'):
                field_type = field.get_internal_type()
                if field_type in ('ForeignKey', 'OneToOneField'):
                    # For thread fields, serialize the full thread data with comments
                    if field.name.endswith('_thread'):
                        thread_instance = getattr(instance, field.name, None)
                        thread_data = self._serialize_thread(thread_instance)
                        if thread_data and thread_data.get('comments'):
                            data[field.name] = thread_data
                    else:
                        # Store FK / OneToOne as ID
                        value = getattr(instance, f'{field.name}_id', None)
                        if value is not None:
                            data[field.name] = value
                elif field_type in ('ManyToManyField', 'ManyToOneRel', 'GenericRelation'):
                    continue
                else:
                    value = getattr(instance, field.name, None)
                    if value is not None:
                        data[field.name] = value

        # Export submodules if the module has them
        if hasattr(instance, 'submodules'):
            submodules = instance.submodules
            if submodules:
                submodules_list = []
                for submodule in submodules:
                    submodule_data = self.to_representation(submodule)
                    # Include the submodule class name for proper reconstruction
                    submodule_data['_submodule_type'] = submodule.__class__.__name__
                    submodules_list.append(submodule_data)
                data['_submodules'] = submodules_list

        return data


class ActivityExportSerializer(serializers.ModelSerializer):
    """Serializer for exporting activities with their modules."""
    modules = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        exclude = ['id', 'project', 'owner', 'created_at', 'updated_at']

    def get_modules(self, obj):
        """Group modules by their type."""
        result = {}
        module_serializer = ModuleExportSerializer()
        for module in obj.modules:
            module_type = module.__class__.__name__
            if module_type not in result:
                result[module_type] = []
            result[module_type].append(module_serializer.to_representation(module))
        return result


class ProjectExportSerializer(serializers.ModelSerializer):
    """Serializer for full project export."""
    activities = ActivityExportSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        exclude = ['id', 'owner', 'created_at', 'updated_at', 'locked_at',
                   'lock_updated_at', 'locked_by', 'is_locked', 'export_id',
                   'last_recap_sent_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for field in ['country', 'climate', 'moisture', 'soil_type', 'gw_potential', 'status']:
            if field in data and data[field] is not None:
                if isinstance(data[field], dict) and 'id' in data[field]:
                    data[field] = data[field]['id']
        return data


class ProjectImportSerializer(serializers.Serializer):
    """Serializer for validating and processing project imports."""
    formatVersion = serializers.IntegerField()
    appVersion = serializers.CharField()
    compatibilityGroup = serializers.IntegerField()
    exportedAt = serializers.DateTimeField()
    exportId = serializers.UUIDField()
    project = serializers.DictField()

    def validate_compatibilityGroup(self, value):
        """Ensure compatibility group matches current app."""
        from .views import get_version_config
        current_config = get_version_config()
        current_group = current_config.get("compatibilityGroup", 1)
        if value != current_group:
            raise serializers.ValidationError(
                f"This project was created with EX-ACT v{value} and cannot be "
                f"imported into this version (v{current_group})."
            )
        return value

    def validate_formatVersion(self, value):
        """Ensure format version is supported."""
        if value != 1:
            raise serializers.ValidationError(
                f"Unsupported file format version: {value}"
            )
        return value


class ActivitySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ["id", "name", "module_types", "completion_percentage", "is_b_intact"]
        ref_name = "Activity"


class ActivityResultSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    cost = serializers.FloatField(read_only=True)
    pass


class ActivitySerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255, read_only=True)
    project = ReadProjectSerializer(many=False, read_only=True)
    user = UserReadSerializer(many=False, read_only=True)
    change_rate = get_model_serializer(ChangeRate)(many=False, read_only=True)
    climate_t2 = get_model_serializer(Climate)(read_only=True)
    moisture_t2 = get_model_serializer(Moisture)(read_only=True)
    soil_type_t2 = get_model_serializer(SoilType)(read_only=True)
    module_types = get_model_serializer(ModuleType)(many=True, read_only=True)
    owner = UserReadSerializer(many=False, read_only=True)

    status = get_model_serializer(StatusType)(many=False, read_only=True)
    completion_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = Activity
        fields = "__all__"
        ref_name = "Activity"


class ActivitySerializerWithModules(ActivitySerializer):
    modules = serializers.SerializerMethodField(read_only=True)

    def get_modules(self, obj: Activity):
        return [get_module_serializer(module.__class__)(module, many=False).data for module in obj.modules]


class WriteActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = "__all__"
        ref_name = "Activity"

    def validate(self, data):
        project: Project = self.instance.project if self.instance else data.get("project")

        if project.is_archived:
            return serializers.ValidationError("Archived projects cannot have activities added")

        if project.is_finalized:
            return serializers.ValidationError("Finalized projects cannot have activities added")

        # Enforce the activity cap on creation and when an existing activity is
        # reassigned to a different project (the destination would gain an activity).
        # Note: on update, `project` above is pinned to the instance's current
        # project, so the destination must be read from the incoming data.
        target_project: Project = data.get("project") or project
        is_reassignment = self.instance is not None and target_project != self.instance.project
        if (not self.instance or is_reassignment) and target_project.activities.count() >= MAX_ACTIVITIES_PER_PROJECT:
            raise serializers.ValidationError(f"A project cannot have more than {MAX_ACTIVITIES_PER_PROJECT} activities")

        project._check_lock_expiration()
        if project.is_locked and not project.locked_by == self.context["request"].user and not self.context["request"].user.is_staff:
            raise serializers.ValidationError("Project is locked by another user")
        project.lock(self.context["request"].user)

        if self.instance:
            luc_module: ModuleType = ModuleType.objects.get(name_en="Land Use Change")

            module_types = data.get("module_types", [])

            if luc_module in module_types:
                raise serializers.ValidationError("Land Use Change module cannot be added manually")

            if self.instance.landusechange.exists() and len(list(filter(lambda module: module.is_luc, module_types))) > 0:
                raise serializers.ValidationError("Land Modules cannot be independently added to activities with a Land Use Change")

            new_duration = data.get("duration_t2", None)
            if new_duration and new_duration > (self.instance.project.implementation_years + self.instance.project.capitalization_years):
                raise serializers.ValidationError("Activity duration cannot be greater than project duration")

        activity_cost = data.get("cost", None)

        if activity_cost:
            project = getattr(self.instance, "project", data.get("project"))
            project_cost = project.cost if project.cost else 0

            if self.instance and activity_cost > project_cost:
                raise serializers.ValidationError("Activity cost cannot be greater than project cost")

            total_activity_cost = list(project.activities.all().values_list("cost", flat=True))
            total_activity_cost.append(activity_cost)

            if project_cost and sum(total_activity_cost) > project_cost:
                raise serializers.ValidationError("Total cost of activities cannot be greater than project cost")

        return super().validate(data)

    def save(self, **kwargs):
        project: Project = getattr(self.instance, "project", self.validated_data.get("project"))
        project.refresh_lock()

        return super().save(**kwargs)


class ActivityBuilderSerializer(serializers.Serializer):
    """
    Serializer for the activity builder.\n
    The serializer validates the input data and creates a new activity object with the specified fields.\n
    It then creates the associated land use change and module objects, if any.

    This serializer expects a JSON object with the following fields:
    - project: the ID of the project to which the activity belongs (required).
    - name: the name of the activity (required).
    - climate: the ID of the climate associated with the activity (required).
    - soil_type: the ID of the soil type associated with the activity (required).
    - duration: the duration of the activity in days (required).
    - land_use_change: an optional object with the following fields:
        - module_type_start: the ID of the module type at the start of the land use change.
        - module_type_end: the ID of the module type at the end of the land use change.
        - area: the area affected by the land use change in hectares.
    - modules: an optional list of module type IDs associated with the activity.
    - has_input: a boolean flag indicating whether the activity requires the Inputs module (default is false).
    """

    class LandUseChangeBuilderSerializer(serializers.ModelSerializer):
        module_type_start = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), required=True)
        module_type_w = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), required=True)
        module_type_wo = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), required=True)

        class Meta:
            model = LandUseChange
            fields = ["module_type_start", "module_type_w", "module_type_wo"]
            ref_name = "LandUseChange"

    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=True)
    name = serializers.CharField(max_length=255, required=True)
    cost = serializers.FloatField(required=False)
    climate_t2 = serializers.PrimaryKeyRelatedField(queryset=Climate.objects.all(), required=False, allow_null=True)
    moisture_t2 = serializers.PrimaryKeyRelatedField(queryset=Moisture.objects.all(), required=False, allow_null=True)
    soil_type_t2 = serializers.PrimaryKeyRelatedField(queryset=SoilType.objects.all(), required=False, allow_null=True)
    duration_t2 = serializers.IntegerField(required=False, allow_null=True)
    start_year_t2 = serializers.IntegerField(required=False, allow_null=True)
    last_year_of_accounting_t2 = serializers.IntegerField(required=False, allow_null=True)
    land_use_change = LandUseChangeBuilderSerializer(many=False, required=False, allow_null=True)
    module_types = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), many=True, required=False)
    area = serializers.FloatField(required=False, min_value=0)
    module_types = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), many=True, required=False)
    change_rate = serializers.PrimaryKeyRelatedField(queryset=ChangeRate.objects.all(), many=False, required=False)
    activity_id = serializers.PrimaryKeyRelatedField(queryset=Activity.objects.all(), many=False, required=False)

    def validate(self, data):
        if data.get("activity_id", None):
            self.instance = data.get("activity_id")

        luc_module = ModuleType.objects.get(name_en="Land Use Change")
        module_types = data.get("module_types", [])
        land_use_change = data.get("land_use_change", None)
        area = data.get("area", None)
        project: Project = data.get("project")

        project._check_lock_expiration()
        if project.is_locked and not project.locked_by == self.context["request"].user and not self.context["request"].user.is_staff:
            raise serializers.ValidationError("Project is locked by another user")

        if project.is_archived:
            raise serializers.ValidationError("Archived projects cannot have activities added")

        if project.is_finalized:
            raise serializers.ValidationError("Finalized projects cannot have activities added")

        if not self.instance and project.activities.count() >= MAX_ACTIVITIES_PER_PROJECT:
            raise serializers.ValidationError(f"A project cannot have more than {MAX_ACTIVITIES_PER_PROJECT} activities")

        if luc_module in module_types:
            raise serializers.ValidationError("Land Use Change module cannot be added manually")

        if land_use_change and any(module.is_luc for module in module_types):
            raise serializers.ValidationError("Land Modules cannot be independently added to activities with a Land Use Change")

        if (land_use_change or any(module.is_luc for module in module_types)) and not area:
            raise serializers.ValidationError("Area must be provided")

        if sum(module.is_luc for module in module_types) > 1:
            raise serializers.ValidationError("Only one independent Land Use module is allowed per activity")

        if land_use_change and any(not module.is_luc for module in land_use_change.values()):
            raise serializers.ValidationError("Only land-based modules are allowed in the Land Use Change")

        super().validate(data)

        return data

    def create_activity(self):
        default_change_rate = ChangeRate.objects.get(name="linear")

        return Activity.objects.create(
            name=self.validated_data["name"],
            project=self.validated_data["project"],
            cost=self.validated_data["cost"],
            change_rate=self.validated_data.get("change_rate", default_change_rate),
            climate_t2=self.validated_data.get("climate_t2", None),
            moisture_t2=self.validated_data.get("moisture_t2", None),
            duration_t2=self.validated_data.get("duration_t2", None),
            soil_type_t2=self.validated_data.get("soil_type_t2", None),
            start_year_t2=self.validated_data.get("start_year_t2", None),
            last_year_of_accounting_t2=self.validated_data.get("last_year_of_accounting_t2", None),
            owner=self.context["request"].user,
        )

    def handle_luc_module(self, activity, create_organic_soil):
        luc = LandUseChange.objects.create(
            **self.validated_data["land_use_change"],
            activity=activity,
            area=self.validated_data["area"],
        )
        activity.module_types.add(
            luc.module_type_start.id,
            luc.module_type_w.id,
            luc.module_type_wo.id,
            ModuleType.objects.get(name_en="Land Use Change").id,
        )

        if create_organic_soil:
            organic_soil = OrganicSoil.objects.filter(activity=activity).first()
            if not organic_soil:
                organic_soil = OrganicSoil.objects.create(activity=activity, area=self.validated_data.get("area"))
            organic_soil.land_use_change = luc
            organic_soil.save()
            activity.module_types.add(ModuleType.objects.get(name_en="Organic Soil").id)
            luc.organic_soil = organic_soil

        luc.save()
        return luc

    def create_modules(self, activity, luc, has_organic_soil, has_luc_module):
        from api.models import Module, Submodule

        project = activity.project

        module_types = activity.module_types.all()

        if any(issubclass(apps.get_model("api", module_type.class_name), (Module, Submodule)) for module_type in module_types):
            climate = activity.climate_t2 or project.climate
            moisture = activity.moisture_t2 or project.moisture
            soil_type = activity.soil_type_t2 or project.soil_type

            missing_fields = []
            if climate is None:
                missing_fields.append("climate")
            if moisture is None:
                missing_fields.append("moisture")
            if soil_type is None:
                missing_fields.append("soil_type")

            if missing_fields:
                raise serializers.ValidationError(
                    f"{', '.join(missing_fields).title()} {'is' if len(missing_fields) == 1 else 'are'} "
                    f"required for this module type. Please set {'/'.join([f'{f}_t2' for f in missing_fields])} "
                    f"on the activity or {', '.join(missing_fields)} on the project."
                )

        for module_type in module_types:
            if module_type.class_name in ["LandUseChange", "OrganicSoil"]:
                continue

            ModuleClass = apps.get_model("api", module_type.class_name)

            if module_type.is_luc:
                module_instance = ModuleClass.objects.create(activity=activity, land_use_change=luc, area=self.validated_data.get("area"))
                if has_organic_soil and not has_luc_module:
                    organic_soil = OrganicSoil.objects.create(activity=activity, area=self.validated_data.get("area"))
                    activity.module_types.add(ModuleType.objects.get(name_en="Organic Soil").id)
                    module_instance.organic_soil = organic_soil
            else:
                filters = {"activity": activity}
                if module_type.class_name in [CoastalWetland.__name__, Waterbody.__name__]:
                    filters["area"] = self.validated_data.get("area")
                module_instance = ModuleClass.objects.create(**filters)

            module_instance.save()

            if module_instance.history.exists():
                utils.update_change_reason(module_instance, "update")

    def unique_activity_name(self):
        base_name = self.validated_data["name"]
        project = self.validated_data["project"]
        suffix = 1

        while Activity.objects.filter(name=f"{base_name} ({suffix})", project=project).exists():
            suffix += 1

        return f"{base_name} ({suffix})"

    def validate_total_project_cost(self):
        project = self.validated_data["project"]
        total_cost = sum(project.activities.values_list("cost", flat=True)) + self.validated_data.get("cost", 0)

        if project.cost and total_cost > project.cost:
            raise serializers.ValidationError("Total cost of activities cannot be greater than project cost")

    def edit_existing_luc(self):
        luc: LandUseChange = LandUseChange.objects.filter(activity=self.instance).first()

        luc.module_type_start = self.validated_data["land_use_change"]["module_type_start"]
        luc.module_type_w = self.validated_data["land_use_change"]["module_type_w"]
        luc.module_type_wo = self.validated_data["land_use_change"]["module_type_wo"]
        luc.area = self.validated_data["area"]

        luc.save()
        self.instance.save()

        return luc

    def delete_existing_luc(self):
        luc: LandUseChange = self.instance.landusechange.first()
        self.instance.module_types.remove(luc.module_type_start.id, luc.module_type_w.id, luc.module_type_wo.id, luc.module_type.id)
        module_start, module_w, module_wo = luc.get_modules()
        for module in [module_start, module_w, module_wo]:
            module: LandModule
            module.land_use_change = None
            module.save()
        luc.delete()
        self.instance.save()

    def sanitize_input_entries(self):
        if not self.instance:
            return

        self.instance: Activity
        for module in self.instance.modules:
            module: Module
            if not module.is_start():
                for field in module._meta.fields:
                    if field.name.endswith("_start"):
                        if field.get_internal_type() == "BooleanField":
                            setattr(module, field.name, False)
                        else:
                            # Use field default if defined, otherwise None
                            default = field.get_default() if field.has_default() else None
                            setattr(module, field.name, default)
            if not module.is_with():
                for field in module._meta.fields:
                    if field.name.endswith("_w"):
                        if field.get_internal_type() == "BooleanField":
                            setattr(module, field.name, False)
                        else:
                            default = field.get_default() if field.has_default() else None
                            setattr(module, field.name, default)
            if not module.is_without():
                for field in module._meta.fields:
                    if field.name.endswith("_wo"):
                        if field.get_internal_type() == "BooleanField":
                            setattr(module, field.name, False)
                        else:
                            default = field.get_default() if field.has_default() else None
                            setattr(module, field.name, default)

            if hasattr(module, "area"):
                module.area = self.validated_data.get("area")

            module.save()

    def create_module(self, module_type: ModuleType, in_luc: bool = False, luc: LandUseChange = None, area: float = None):
        ModuleClass = apps.get_model("api", module_type.class_name)
        is_organic_soil = module_type.class_name == "OrganicSoil"

        module_data = {"activity": self.instance}
        if in_luc:
            module_data["land_use_change"] = luc

        if area and hasattr(ModuleClass, "area"):
            module_data["area"] = area

        module_instance = ModuleClass.objects.create(**module_data)

        if is_organic_soil and luc:
            luc.organic_soil = module_instance
            luc.save()

        return module_instance

    @transaction.atomic
    def save(self, **kwargs):
        self.validate_total_project_cost()

        create_organic_soil = "OrganicSoil" in [module.class_name for module in self.validated_data.get("module_types", [])]
        has_luc_module = self.validated_data.get("land_use_change", False)
        area = self.validated_data.get("area", None)

        if self.instance:
            # LUC
            luc: LandUseChange = self.instance.landusechange.first()
            was_luc_removed = luc and not has_luc_module
            was_luc_added = not luc and has_luc_module

            builder_module_types = list(set([module for module in self.validated_data["module_types"] if module.class_name != "LandUseChange"]))
            builder_luc_module_types = list(set(list(self.validated_data["land_use_change"].values()) if has_luc_module else []))
            all_builder_module_types = builder_module_types + builder_luc_module_types
            activity_module_types = list(set(list(map(lambda module: module, self.instance.module_types.all()))))
            organic_soil_module_type = ModuleType.objects.filter(class_name="OrganicSoil").first()
            excluded_types = {ModuleType.objects.get(class_name="LandUseChange")}
            if organic_soil_module_type:
                excluded_types.add(organic_soil_module_type)
            removed_module_types = list(set(list(set(activity_module_types) - set(all_builder_module_types) - excluded_types)))

            organic_soil: OrganicSoil = OrganicSoil.objects.filter(activity=self.instance).first()

            self.instance.module_types.clear()
            module_types_to_append = []

            if was_luc_removed:
                self.delete_existing_luc()
                luc = None
            elif was_luc_added:
                luc = self.handle_luc_module(self.instance, create_organic_soil)
            elif luc:
                self.edit_existing_luc()

            if not organic_soil and create_organic_soil:
                organic_soil = OrganicSoil.objects.create(activity=self.instance, area=area)
                if luc:
                    organic_soil.land_use_change = luc
                    organic_soil.save()
                    luc.organic_soil = organic_soil
                    luc.save()
                module_types_to_append.append(ModuleType.objects.get(class_name="OrganicSoil").id)
            elif organic_soil and not create_organic_soil:
                for module_type in activity_module_types:
                    if module_type.is_luc and module_type.class_name != "OrganicSoil":
                        ModuleClass = apps.get_model("api", module_type.class_name)
                        module_instance = ModuleClass.objects.filter(activity=self.instance).first()
                        if module_instance and hasattr(module_instance, "organic_soil") and module_instance.organic_soil == organic_soil:
                            module_instance.organic_soil = None
                            module_instance.save()
                if luc:
                    organic_soil.land_use_change = None
                    organic_soil.save()
                    luc.organic_soil = None
                    luc.save()
                organic_soil.delete()
                organic_soil = None

            for module_type in filter(lambda module: module.class_name != "OrganicSoil", all_builder_module_types):
                module_type: ModuleType
                ModuleClass = apps.get_model("api", module_type.class_name)
                module_instance: Module = ModuleClass.objects.filter(activity=self.instance).first()
                if not module_instance:
                    module_instance = self.create_module(module_type, in_luc=module_type in builder_luc_module_types, luc=luc, area=area)
                else:
                    if hasattr(module_instance, "area"):
                        module_instance.area = area
                    if hasattr(module_instance, "land_use_change"):
                        current_luc_id = module_instance.land_use_change.id if module_instance.land_use_change is not None else None
                        new_luc_id = luc.id if luc is not None else None
                        if current_luc_id != new_luc_id:
                            module_instance.land_use_change = luc if module_type in builder_luc_module_types else None
                    if hasattr(module_instance, "organic_soil"):
                        if (not luc or was_luc_removed) and organic_soil and module_type.is_luc:
                            module_instance: LandModule
                            module_instance.organic_soil = organic_soil
                        else:
                            module_instance.organic_soil = None
                    module_instance.save()

                module_types_to_append.append(module_type.id)

            for module_type in removed_module_types:
                ModuleClass = apps.get_model("api", module_type.class_name)
                module_instance: Module = ModuleClass.objects.filter(activity=self.instance).first()
                if module_instance:
                    module_instance.land_use_change = None
                    module_instance.organic_soil = None
                    module_instance.save()
                    module_instance.delete()
                    if module_type.id in module_types_to_append:
                        module_types_to_append.remove(module_type.id)

            if organic_soil and create_organic_soil:
                if luc:
                    if organic_soil.land_use_change is not None and organic_soil.land_use_change.id != luc.id:
                        organic_soil.land_use_change = luc
                        organic_soil.save()
                    luc.organic_soil = organic_soil
                    luc.save()
                organic_soil.area = area
                organic_soil.save()
                module_types_to_append.append(ModuleType.objects.get(class_name="OrganicSoil").id)

            self.instance.module_types.add(*module_types_to_append)
            if (luc or was_luc_added) and not was_luc_removed:
                self.instance.module_types.add(ModuleType.objects.get(class_name="LandUseChange").id)

            # Sanitize AFTER module_types are re-populated: Activity.modules is derived
            # from module_types.all(), so running this while the M2M is cleared (see the
            # module_types.clear() above) would iterate zero modules and clear nothing.
            # This is what leaves stale _start/_w/_wo values behind when a LUC's module
            # roles are swapped.
            self.sanitize_input_entries()

            self.instance.save()

            return self.instance
        else:
            if Activity.objects.filter(name=self.validated_data["name"], project=self.validated_data["project"]).exists():
                self.validated_data["name"] = self.unique_activity_name()

            activity = self.create_activity()
            activity.module_types.set(self.validated_data.get("module_types", []))

            luc = None
            if has_luc_module:
                luc = self.handle_luc_module(activity, create_organic_soil)

            self.create_modules(activity, luc, create_organic_soil, has_luc_module)
            activity.save()

            return activity


class RecursiveField(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "is_opted_out_of_emails"]


class CommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()
    author = UserSummarySerializer(many=False, read_only=True)

    class Meta:
        model = Comment
        fields = "__all__"

    def get_replies(self, obj):
        if obj.replies.exists():
            return CommentSerializer(obj.replies.all(), many=True).data
        return []

    def validate(self, attrs):
        if attrs.get("parent", None) and attrs.get("parent", None).parent:
            raise serializers.ValidationError("Cannot reply to a reply")

        if not attrs.get("parent", None) and not attrs.get("thread", None):
            raise serializers.ValidationError("Either parent comment or thread must be provided")

        return super().validate(attrs)


class CommentThreadSerializer(serializers.ModelSerializer):
    comments = CommentSerializer(many=True, read_only=True)
    author = UserSummarySerializer(many=False, read_only=True)

    class Meta:
        model = CommentThread
        fields = "__all__"


class LandUseTypeSerializer(serializers.ModelSerializer):
    module_types = get_model_serializer(ModuleType)(many=True, read_only=True)
    climate = get_model_serializer(Climate)(many=False, read_only=True)
    moisture = get_model_serializer(Moisture)(many=False, read_only=True)

    class Meta:
        model = LandUseType
        fields = "__all__"
        ref_name = "LandUseType"


class ModuleResultSerializer(serializers.Serializer):
    results_total = serializers.SerializerMethodField()
    results_by_activity = serializers.SerializerMethodField()
    results_by_gas = serializers.SerializerMethodField()
    results_by_activity_by_gas = serializers.SerializerMethodField()

    def get_results_total(self, obj):
        return DynamicResultSerializer(obj.cached_results_total, aggregate_by=BreakdownTypes.TOTAL).data if obj.cached_results_total else None

    def get_results_by_activity(self, obj):
        return DynamicResultSerializer(obj.cached_results_by_activity, aggregate_by=BreakdownTypes.ACTIVITY).data if obj.cached_results_by_activity else None

    def get_results_by_gas(self, obj):
        return DynamicResultSerializer(obj.cached_results_by_gas, aggregate_by=BreakdownTypes.GAS).data if obj.cached_results_by_gas else None

    def get_results_by_activity_by_gas(self, obj):
        return DynamicResultSerializer(obj.cached_results_by_activity_by_gas, aggregate_by=BreakdownTypes.ACTIVITY_GAS).data if obj.cached_results_by_activity_by_gas else None


class BaseGenericModuleSerializer(serializers.ModelSerializer):
    # activity = ActivitySerializer(many=False, read_only=True)
    module_type = serializers.SerializerMethodField()
    status = get_model_serializer(StatusType)(read_only=True)
    note = serializers.SerializerMethodField()

    last_cached_at = serializers.SerializerMethodField()
    cached_results_total = serializers.SerializerMethodField()
    cached_results_by_activity = serializers.SerializerMethodField()
    cached_results_by_gas = serializers.SerializerMethodField()
    cached_results_by_activity_by_gas = serializers.SerializerMethodField()

    class Meta:
        extra_fields = ["module_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self.Meta, "ref_name") or not hasattr(self.Meta, "mandatory_fields"):
            raise ValueError(f"Meta class of {self.__class__.__name__} must have a ref_name and a mandatory_fields attribute")

    def get_last_cached_at(self, obj):
        return None

    def get_cached_results_total(self, obj):
        # NOTE: This is hidden for now. Could be returned as a field in the future.
        # return DynamicResultSerializer(obj.cached_results_total, aggregate_by=BreakdownTypes.TOTAL).data if obj.cached_results_total else None
        return None

    def get_cached_results_by_activity(self, obj):
        # NOTE: This is hidden for now. Could be returned as a field in the future.
        # return DynamicResultSerializer(obj.cached_results_by_activity, aggregate_by=BreakdownTypes.ACTIVITY).data if obj.cached_results_by_activity else None
        return None

    def get_cached_results_by_gas(self, obj):
        # NOTE: This is hidden for now. Could be returned as a field in the future.
        # return DynamicResultSerializer(obj.cached_results_by_gas, aggregate_by=BreakdownTypes.GAS).data if obj.cached_results_by_gas else None
        return None

    def get_cached_results_by_activity_by_gas(self, obj):
        # NOTE: This is hidden for now. Could be returned as a field in the future.
        # return DynamicResultSerializer(obj.cached_results_by_activity_by_gas, aggregate_by=BreakdownTypes.ACTIVITY_GAS).data if obj.cached_results_by_activity_by_gas else None
        return None

    def get_module_type(self, obj):
        return get_model_serializer(ModuleType)(ModuleType.objects.get(class_name=self.Meta.ref_name), many=False).data

    def get_note(self, obj):
        return NoteSerializer(obj.note.first(), many=False).data if obj.note.exists() else None

    def merge_instance_data(self, data: dict, instance=None) -> dict:
        """
        Merges the data from the given dictionary with the data from the instance object.

        Args:
            data (dict): The dictionary containing the data to be merged.
            instance (object, optional): The instance object to merge the data with. Defaults to None.

        Returns:
            dict: The merged data dictionary.
        """
        combined_data = {**{field.name: getattr(instance, field.name) for field in instance._meta.fields}, **data} if instance else data.copy()
        return combined_data

    def get_scenario(self, field_name: str):
        """
        Returns the scenario based on the given field name.

        Args:
            field_name (str): The name of the field.

        Returns:
            str: The scenario corresponding to the field name. Possible values are 'start', 'w', 'wo', or None if no match is found.
        """
        if field_name.endswith("_start"):
            return utils.ScenarioTypes.START.value
        elif field_name.endswith("_w"):
            return utils.ScenarioTypes.WITH.value
        elif field_name.endswith("_wo"):
            return utils.ScenarioTypes.WITHOUT.value
        return None

    @abstractmethod
    def is_ready(self, data, mandatory_fields, instance=None):
        raise NotImplementedError("is_ready method must be implemented")


class BaseModuleSerializer(BaseGenericModuleSerializer):
    def validate(self, data):
        log.debug(f"START BaseModuleSerializer[{self.Meta.ref_name}].validate")

        activity = data["parent"].activity if data.get("parent") else data.get("activity", self.instance.activity)
        project: Project = activity.project

        module_types = list(map(lambda module: module.class_name, activity.module_types.all()))

        project._check_lock_expiration()
        if project.is_locked and not project.locked_by == self.context["request"].user and not self.context["request"].user.is_staff:
            log.error("Project is locked by another user")
            raise serializers.ValidationError("Project is locked by another user")
        if project.is_locked:
            project.refresh_lock()
        else:
            project.lock(self.context["request"].user)

        # Validate climate/moisture/soil_type if module requires them
        module_instance = self.instance or self.Meta.model(**{k: v for k, v in data.items() if k != "activity" and k != "parent"})
        if hasattr(module_instance, "activity"):
            module_instance.activity = activity

        if self._module_requires_climate_moisture_soil_type(module_instance):
            climate = activity.climate_t2 or project.climate
            moisture = activity.moisture_t2 or project.moisture
            soil_type = activity.soil_type_t2 or project.soil_type

            missing_fields = []
            if climate is None:
                missing_fields.append("climate")
            if moisture is None:
                missing_fields.append("moisture")
            if soil_type is None:
                missing_fields.append("soil_type")

            if missing_fields:
                raise serializers.ValidationError(
                    f"{', '.join(missing_fields).title()} {'is' if len(missing_fields) == 1 else 'are'} "
                    f"required for this module type. Please set {'/'.join([f'{f}_t2' for f in missing_fields])} "
                    f"on the activity or {', '.join(missing_fields)} on the project."
                )

        if project.is_archived:
            log.error("Modules belonging to archived projects cannot be modified")
            raise serializers.ValidationError("Modules belonging to archived projects cannot be modified")

        if project.is_finalized:
            log.error("Modules belonging to finalized projects cannot be modified")
            raise serializers.ValidationError("Modules belonging to finalized projects cannot be modified")

        if getattr(activity, self.Meta.ref_name.lower(), None).exists() and not self.instance:
            log.error(f"Activity already has a {self.Meta.ref_name}")
            raise serializers.ValidationError("A module of this type is already present for this activity")

        if self.Meta.ref_name not in module_types and self.Meta.ref_name != "LandUseChange":
            log.error(f"Module type {self.Meta.ref_name} is not present for this activity")
            raise serializers.ValidationError("This module type is not present for this activity")

        is_ready, errors = self.is_ready(data, self.Meta.mandatory_fields, instance=self.instance)

        if not is_ready:
            log.debug(f"Module {self.Meta.ref_name} is not ready for calculations")
            data["status"] = StatusType.objects.get(name_en="EMPTY")
            return super().validate(data)

        data["status"] = StatusType.objects.get(name_en="READY")

        log.debug(f"END BaseModuleSerializer[{self.Meta.ref_name}].validate")
        return super().validate(data)

    def save(self, **kwargs):
        if self.instance:
            self.instance.activity.project.lock_updated_at = timezone.now()
            self.instance.activity.project.save()
        else:
            self.validated_data["activity"].project.lock_updated_at = timezone.now()
            self.validated_data["activity"].project.save()
        return super().save(**kwargs)

    def _module_requires_climate_moisture_soil_type(self, module):
        """Check if module type requires climate/moisture/soil_type."""
        from api.models import Module, Submodule

        return isinstance(module, (Module, Submodule))


class BaseSubmoduleSerializer(BaseGenericModuleSerializer):
    def validate(self, data):
        log.debug(f"START SubmoduleBaseSerializer[{self.Meta.ref_name}].validate")

        if not data.get("parent", None) and (not self.instance or not self.instance.parent):
            log.error(f"Parent field is required for {self.Meta.ref_name}")
            raise serializers.ValidationError("Parent field is required")

        project: Project = data["parent"].activity.project if data.get("parent") else self.instance.parent.activity.project

        project._check_lock_expiration()
        if project.is_locked and not project.locked_by == self.context["request"].user and not self.context["request"].user.is_staff:
            log.error("Project is locked by another user")
            raise serializers.ValidationError("Project is locked by another user")
        if project.is_locked:
            project.refresh_lock()
        else:
            project.lock(self.context["request"].user)

        is_ready, errors = self.is_ready(data, self.Meta.mandatory_fields, instance=self.instance)

        if not is_ready:
            log.debug(f"Module {self.Meta.ref_name} is not ready for calculations")
            data["status"] = StatusType.objects.get(name_en="EMPTY")
            return super().validate(data)

        data["status"] = StatusType.objects.get(name_en="READY")

        log.debug(f"END SubmoduleBaseSerializer[{self.Meta.ref_name}].validate")
        return super().validate(data)

    def parent_validation(self, parent):
        ParentWriteSerializer = _serializer_registry().get(f"{parent.__class__.__name__}WriteSerializer", None)
        if ParentWriteSerializer is None:
            raise ValueError(f"Write serializer for {parent.__class__.__name__} does not exist")

        parent_serializer: serializers.ModelSerializer = ParentWriteSerializer(data={}, instance=parent, partial=True, context=self.context)
        if parent_serializer.is_valid():
            parent_serializer.save()

    def save(self, **kwargs):
        super().save(**kwargs)

        if not hasattr(self.instance, "parent"):
            log.error(f"Parent attribute is not defined for {self.instance}")
            raise ValueError("Parent attribute is not defined")

        parent = utils.getany([self.instance, dict(kwargs)], "parent")
        log.info(f"Parent in serializer: {parent}")
        self.parent_validation(parent)

        return self.instance


class NoScenarioBaseSerializer(BaseGenericModuleSerializer):
    def is_ready(self, data, mandatory_fields, instance=None):
        combined_data = self.merge_instance_data(data, instance=instance)

        model_instance = self.Meta.model(**combined_data)
        errors = {}

        # If the module is a submodule, the parent module must be retrieved for the scenario checks
        module_type = ModuleType.objects.get(class_name=self.Meta.ref_name)

        if module_type.is_submodule:
            model_instance = model_instance.parent

        for scenario, config in mandatory_fields.items():
            scenario_check_method = f"is_{scenario}"
            if hasattr(model_instance, scenario_check_method) and getattr(model_instance, scenario_check_method)():
                # Validate mandatory fields
                mandatory_fields = config.get("mandatory", [])
                missing_mandatory_fields = [field for field in mandatory_fields if combined_data.get(field) is None]
                if missing_mandatory_fields:
                    errors[scenario] = f"Missing mandatory fields: {', '.join(missing_mandatory_fields)}"

                # Validate conditional fields
                conditional_fields = config.get("conditional", {})
                for field, dependent_fields in conditional_fields.items():
                    if combined_data.get(field):
                        missing_dependent_fields = [dep_field for dep_field in dependent_fields if not combined_data.get(dep_field)]
                        if missing_dependent_fields:
                            if scenario not in errors:
                                errors[scenario] = []
                            errors[scenario].append(f"Since '{field}' is filled, the following fields are also mandatory: {', '.join(missing_dependent_fields)}")

        return not errors, errors


class ScenarioBaseSerializer(BaseGenericModuleSerializer):
    def is_ready(self, data, mandatory_fields, instance=None):
        combined_data = self.merge_instance_data(data, instance=instance)

        model_instance = self.Meta.model(**combined_data)
        errors = {}

        # If the module is a submodule, the parent module must be retrieved for the scenario checks
        module_type = ModuleType.objects.get(class_name=self.Meta.ref_name)

        if module_type.is_submodule:
            model_instance = model_instance.parent

        for scenario, config in mandatory_fields.items():
            scenario_check_method = f"is_{scenario}"
            if hasattr(model_instance, scenario_check_method) and getattr(model_instance, scenario_check_method)():
                # Validate mandatory fields
                mandatory_fields = config.get("mandatory", [])
                missing_mandatory_fields = [field for field in mandatory_fields if combined_data.get(field) is None]
                if missing_mandatory_fields:
                    errors[scenario] = [f"Missing mandatory fields: {', '.join(missing_mandatory_fields)}"]

                # Validate conditional fields
                conditional_fields = config.get("conditional", {})
                for field, dependent_fields in conditional_fields.items():
                    if combined_data.get(field):
                        missing_dependent_fields = [dep_field for dep_field in dependent_fields if combined_data.get(dep_field) is None]
                        if missing_dependent_fields:
                            if scenario not in errors:
                                errors[scenario] = []
                            errors[scenario].append(f"Since '{field}' is filled, the following fields are also mandatory: {', '.join(missing_dependent_fields)}")

        return not errors, errors


class NoScenarioModuleSerializer(BaseModuleSerializer, NoScenarioBaseSerializer):
    pass


class ScenarioModuleSerializer(BaseModuleSerializer, ScenarioBaseSerializer):
    pass


class NoScenarioSubmoduleSerializer(BaseSubmoduleSerializer, NoScenarioBaseSerializer):
    pass


class ScenarioSubmoduleSerializer(BaseSubmoduleSerializer, ScenarioBaseSerializer):
    pass


class LandModuleSeralizer(ScenarioModuleSerializer):
    # activity = ActivitySerializer(many=False, read_only=True)
    land_use_change = get_model_serializer(LandUseChange)(many=False, read_only=True, required=False)
    status = get_model_serializer(StatusType)(many=False, read_only=True)

    class Meta:
        model = None
        fields = "__all__"
        ref_name = None
        mandatory_fields = {}

    def validate(self, data):
        log.debug(f"START LandModuleSerializer[{self.Meta.ref_name}].validate")
        log.debug(f"Data: {data}")

        activity = data["activity"] if "activity" in data else self.instance.activity
        luc: LandUseChange = activity.landusechange.first()

        if self.instance and not isinstance(self.instance, LandUseChange):
            is_ready, errors = self.is_ready(data, self.Meta.mandatory_fields, instance=self.instance)

            if not is_ready:
                log.debug(f"Module {self.Meta.ref_name} is not ready for calculations")
                data["status"] = StatusType.objects.get(name_en="EMPTY")
            else:
                data["status"] = StatusType.objects.get(name_en="READY")

            super().validate(data)

            for field, value in data.items():
                setattr(self.instance, field, value)

            self.instance.save()

            # Validate the parent Land Use Change on related LandModule change
            parent_luc = getattr(self.instance, "land_use_change", None)

            if parent_luc:
                luc_serializer = get_module_serializer(LandUseChange)(data={}, instance=parent_luc, many=False, partial=True, context=self.context)
                luc_serializer.is_valid()
                luc_serializer.save()

        if luc:
            # If the module is associated with a Land Use Change, update the status of the Land Use Change
            luc_serializer: LandUseChangeWriteSerializer = get_module_serializer(LandUseChange)(data={}, instance=luc, many=False, partial=True, context=self.context)
            luc_serializer.is_valid(raise_exception=True)
            luc_serializer.save()

        log.debug(f"END LandModuleSerializer[{self.Meta.ref_name}].validate")
        return data


# Grassland


class GrasslandWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = Grassland
        fields = "__all__"
        ref_name = "Grassland"

        mandatory_fields = {
            "start": {
                "mandatory": ["grassland_management_type_start"],
                "conditional": {
                    "grassland_management_type_start": [
                        "is_fire_used_start",
                        "fire_periodicity_start",
                        "fire_impact_start",
                    ],
                },
            },
            "with": {
                "mandatory": ["grassland_management_type_w"],
                "conditional": {
                    "grassland_management_type_w": [
                        "is_fire_used_w",
                        "fire_periodicity_w",
                        "fire_impact_w",
                    ],
                },
            },
            "without": {
                "mandatory": ["grassland_management_type_wo"],
                "conditional": {
                    "grassland_management_type_wo": [
                        "is_fire_used_wo",
                        "fire_periodicity_wo",
                        "fire_impact_wo",
                    ],
                },
            },
        }


class GrasslandReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Grassland
        fields = "__all__"
        ref_name = "Grassland"
        mandatory_fields = GrasslandWriteSerializer.Meta.mandatory_fields


# Annual Cropping


class MinorSeasonAnnualCroplandWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = MinorSeasonAnnualCropland
        fields = "__all__"
        ref_name = "MinorSeasonAnnualCropland"

        mandatory_fields = {
            "start": {
                "mandatory": [
                    "land_use_type_start",
                    "residue_management_type_start",
                ],
            },
            "with": {
                "mandatory": [
                    "land_use_type_w",
                    "residue_management_type_w",
                ],
            },
            "without": {
                "mandatory": [
                    "land_use_type_wo",
                    "residue_management_type_wo",
                ],
            },
        }

    def validate(self, data):
        parent: AnnualCropland = self.instance.parent if self.instance else data.get("parent")
        land_use_type_start = self.instance.land_use_type_start if self.instance else data.get("land_use_type_start", None)
        land_use_type_w = self.instance.land_use_type_w if self.instance else data.get("land_use_type_w", None)
        land_use_type_wo = self.instance.land_use_type_wo if self.instance else data.get("land_use_type_wo", None)

        if parent and not parent.is_start() and land_use_type_start:
            raise serializers.ValidationError("Land use type start cannot be set if the main cropland is not in the start scenario")

        if parent and not parent.is_with() and land_use_type_w:
            raise serializers.ValidationError("Land use type with cannot be set if the main cropland is not in the with scenario")

        if parent and not parent.is_without() and land_use_type_wo:
            raise serializers.ValidationError("Land use type without cannot be set if the main cropland is not in the without scenario")

        return super().validate(data)


class MinorSeasonAnnualCroplandReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = MinorSeasonAnnualCropland
        fields = "__all__"
        ref_name = "MinorSeasonAnnualCropland"
        mandatory_fields = MinorSeasonAnnualCroplandWriteSerializer.Meta.mandatory_fields


class AnnualCroplandSerializer(LandModuleSeralizer):
    class Meta:
        model = AnnualCropland
        fields = "__all__"
        ref_name = "AnnualCropland"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "land_use_type_start",
                    "tillage_management_type_start",
                    "organic_input_type_start",
                    "residue_management_type_start",
                ],
            },
            "with": {
                "mandatory": [
                    "land_use_type_w",
                    "tillage_management_type_w",
                    "organic_input_type_w",
                    "residue_management_type_w",
                ],
            },
            "without": {
                "mandatory": [
                    "land_use_type_wo",
                    "tillage_management_type_wo",
                    "organic_input_type_wo",
                    "residue_management_type_wo",
                ],
            },
        }

    def validate(self, data):
        for minor_season in self.instance.minor_seasons.all():
            minor_season: MinorSeasonAnnualCropland
            if not minor_season.is_ready():
                data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")
                return data

        return super().validate(data)


class AnnualCroplandWriteSerializer(AnnualCroplandSerializer):
    pass


class AnnualCroplandReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = AnnualCropland
        fields = "__all__"
        ref_name = "AnnualCropland"
        mandatory_fields = AnnualCroplandSerializer.Meta.mandatory_fields


# Perennial Cropping
class MinorSeasonPerennialCroplandWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = MinorSeasonPerennialCropland
        fields = "__all__"
        ref_name = "MinorSeasonPerennialCropland"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "land_use_type_start",
                    "tillage_management_type_start",
                    "organic_input_type_start",
                ],
            },
            "with": {
                "mandatory": [
                    "land_use_type_w",
                    "tillage_management_type_w",
                    "organic_input_type_w",
                ],
            },
            "without": {
                "mandatory": [
                    "land_use_type_wo",
                    "tillage_management_type_wo",
                    "organic_input_type_wo",
                ],
            },
        }


class MinorSeasonPerennialCroplandReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = MinorSeasonPerennialCropland
        fields = "__all__"
        ref_name = "MinorSeasonPerennialCropland"
        mandatory_fields = MinorSeasonPerennialCroplandWriteSerializer.Meta.mandatory_fields


class PerennialCroplandWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = PerennialCropland
        fields = "__all__"
        ref_name = "PerennialCropland"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "land_use_type_start",
                    "tillage_management_type_start",
                    "organic_input_type_start",
                ],
            },
            "with": {
                "mandatory": [
                    "land_use_type_w",
                    "tillage_management_type_w",
                    "organic_input_type_w",
                ],
            },
            "without": {
                "mandatory": [
                    "land_use_type_wo",
                    "tillage_management_type_wo",
                    "organic_input_type_wo",
                ],
            },
        }


class PerennialCroplandReadSerializer(BaseGenericModuleSerializer):
    minor_seasons = MinorSeasonPerennialCroplandReadSerializer(many=True, read_only=True)

    class Meta:
        model = PerennialCropland
        fields = "__all__"
        ref_name = "PerennialCropland"
        mandatory_fields = PerennialCroplandWriteSerializer.Meta.mandatory_fields


# Land Use Change


class LandUseChangeWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = LandUseChange
        fields = "__all__"
        ref_name = "LandUseChange"
        mandatory_fields = {}

    def validate(self, data):
        if self.instance:
            self.instance: LandUseChange
            if all([m.is_ready() for m in self.instance.get_modules()]):
                data["status"] = StatusType.objects.get(name_en="READY")
            else:
                data["status"] = StatusType.objects.get(name_en="EMPTY")
            self.instance.save()

        return data


class LandUseChangeReadSerializer(LandUseChangeWriteSerializer):
    pass


# Organic Soil


class OrganicSoilWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = OrganicSoil
        fields = "__all__"
        ref_name = "OrganicSoil"
        mandatory_fields = {
            "start": {
                "conditional": {
                    "peat_type": [],
                    "peat_area_start": [
                        "peat_extraction_height_start",
                        "peat_ditches_area_start",
                    ],
                    "drainage_area_start": [
                        "area_not_drained_start",
                    ],
                },
            },
            "with": {
                "conditional": {
                    "peat_type": [],
                    "peat_area_w": [
                        "peat_extraction_height_w",
                        "peat_ditches_area_w",
                    ],
                    "drainage_area_w": [
                        "area_not_drained_w",
                    ],
                },
            },
            "without": {
                "conditional": {
                    "peat_type": [],
                    "peat_area_wo": [
                        "peat_area_wo",
                        "peat_extraction_height_wo",
                        "peat_ditches_area_wo",
                    ],
                    "drainage_area_wo": [
                        "area_not_drained_wo",
                    ],
                },
            },
        }

    def is_ready(self, data, mandatory_fields, instance=None):
        combined_data = self.merge_instance_data(data, instance=instance)

        errors = {}

        for scenario, config in mandatory_fields.items():
            # Validate mandatory fields
            mandatory_fields = config.get("mandatory", [])
            missing_mandatory_fields = [field for field in mandatory_fields if combined_data.get(field) is None]
            if missing_mandatory_fields:
                errors[scenario] = f"Missing mandatory fields: {', '.join(missing_mandatory_fields)}"

            # Validate conditional fields
            conditional_fields = config.get("conditional", {})
            for field, dependent_fields in conditional_fields.items():
                if combined_data.get(field):
                    missing_dependent_fields = [dep_field for dep_field in dependent_fields if combined_data.get(dep_field) is None]
                    if missing_dependent_fields:
                        if scenario not in errors:
                            errors[scenario] = []
                        errors[scenario].append(f"Since '{field}' is filled, the following fields are also mandatory: {', '.join(missing_dependent_fields)}")

        return not errors, errors


class OrganicSoilReadSerializer(LandModuleSeralizer):
    parent_land_use_type_start = serializers.IntegerField(read_only=True)
    parent_land_use_type_w = serializers.IntegerField(read_only=True)
    parent_land_use_type_wo = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrganicSoil
        fields = "__all__"
        ref_name = "OrganicSoil"
        mandatory_fields = OrganicSoilWriteSerializer.Meta.mandatory_fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance:
            return

        self.instance: OrganicSoil

        luc: LandUseChange = self.instance.land_use_change

        if luc:
            self.parent_land_use_type_start = luc.module_type_start.id if luc.module_type_start else None
            self.parent_land_use_type_w = luc.module_type_w.id if luc.module_type_w else None
            self.parent_land_use_type_wo = luc.module_type_wo.id if luc.module_type_wo else None
        else:
            parent_module, parent_module_type = utils.find_organic_soil_parent_module(self.instance)

            self.parent_land_use_type_start = parent_module_type.id if parent_module_type else None
            self.parent_land_use_type_w = parent_module_type.id
            self.parent_land_use_type_wo = parent_module_type.id

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["parent_land_use_type_start"] = self.parent_land_use_type_start
        representation["parent_land_use_type_w"] = self.parent_land_use_type_w
        representation["parent_land_use_type_wo"] = self.parent_land_use_type_wo
        return representation


# Flooded Rice


class MinorSeasonFloodedRiceWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = MinorSeasonFloodedRice
        fields = "__all__"
        ref_name = "MinorSeasonFloodedRice"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "water_management_type_before_cultivation_start",
                    "water_management_type_after_cultivation_start",
                    "organic_amendment_type_start",
                ],
            },
            "with": {
                "mandatory": [
                    "water_management_type_before_cultivation_w",
                    "water_management_type_after_cultivation_w",
                    "organic_amendment_type_w",
                ],
            },
            "without": {
                "mandatory": [
                    "water_management_type_before_cultivation_wo",
                    "water_management_type_after_cultivation_wo",
                    "organic_amendment_type_wo",
                ],
            },
        }


class MinorSeasonFloodedRiceReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = MinorSeasonFloodedRice
        fields = "__all__"
        ref_name = "MinorSeasonFloodedRice"
        mandatory_fields = MinorSeasonFloodedRiceWriteSerializer.Meta.mandatory_fields


class FloodedRiceWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = FloodedRice
        fields = "__all__"
        ref_name = "FloodedRice"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "water_management_type_before_cultivation_start",
                    "water_management_type_after_cultivation_start",
                    "organic_amendment_type_start",
                ],
            },
            "with": {
                "mandatory": [
                    "water_management_type_before_cultivation_w",
                    "water_management_type_after_cultivation_w",
                    "organic_amendment_type_w",
                ],
            },
            "without": {
                "mandatory": [
                    "water_management_type_before_cultivation_wo",
                    "water_management_type_after_cultivation_wo",
                    "organic_amendment_type_wo",
                ],
            },
        }

    def validate(self, data):
        # Get cultivation_days of all minor_seasons and check that they are not greater than 365 including the main season
        cultivation_days = data.get("cultivation_days", 0)  # TODO: This must be fetched from IPCC data (or t2)
        minor_seasons = data.get("minor_seasons", None)

        if minor_seasons:
            # TODO: Move to database Parameter
            if minor_seasons.count() > 4:
                raise serializers.ValidationError("Minor seasons cannot be more than 4")

            # for season in minor_seasons:
            #     cultivation_days += season.get("cultivation_days", 0)

        # TODO: Move to database Parameter
        if cultivation_days > 365:
            raise serializers.ValidationError("Cultivation days cannot be greater than 365 (one year)")

        return super().validate(data)


class FloodedRiceReadSerializer(BaseGenericModuleSerializer):
    minor_seasons = MinorSeasonFloodedRiceReadSerializer(many=True, read_only=True)

    class Meta:
        model = FloodedRice
        fields = "__all__"
        ref_name = "FloodedRice"
        mandatory_fields = FloodedRiceWriteSerializer.Meta.mandatory_fields


# Building
class BuildingSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = Building
        fields = "__all__"
        ref_name = "Building"
        mandatory_fields = {
            "start": {
                "mandatory": [],
            },
            "with": {
                "mandatory": [
                    "building_type",
                    "area_m2_w",
                ],
            },
            "without": {
                "mandatory": [
                    "building_type",
                    "area_m2_wo",
                ],
            },
        }


class BuildingWriteSerializer(BuildingSerializer):
    pass


class BuildingReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Building
        fields = "__all__"
        ref_name = "Building"
        mandatory_fields = {}


# Road


class RoadSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = Road
        fields = "__all__"
        ref_name = "Road"
        mandatory_fields = {
            "start": {
                "mandatory": [],
            },
            "with": {
                "mandatory": [
                    "road_type",
                    "length_km_w",
                    "width_m_w",
                ],
            },
            "without": {
                "mandatory": [
                    "road_type",
                    "length_km_wo",
                    "width_m_wo",
                ],
            },
        }


class RoadWriteSerializer(RoadSerializer):
    pass


class RoadReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Road
        fields = "__all__"
        ref_name = "Road"
        mandatory_fields = {}


# Other


class OtherInfrastructureSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = OtherInfrastructure
        fields = "__all__"
        ref_name = "OtherInfrastructure"
        mandatory_fields = {
            "start": {
                "mandatory": [],
            },
            "with": {
                "mandatory": ["area_m2_w"],
            },
            "without": {
                "mandatory": ["area_m2_wo"],
            },
        }


class OtherInfrastructureWriteSerializer(OtherInfrastructureSerializer):
    pass


class OtherInfrastructureReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = OtherInfrastructure
        fields = "__all__"
        ref_name = "OtherInfrastructure"
        mandatory_fields = {}


class IrrigationWriteSerializer(ScenarioModuleSerializer):
    class Meta:
        model = Irrigation
        fields = "__all__"
        ref_name = "Irrigation"
        mandatory_fields = {}

    def validate(self, data):
        super().validate(data)

        irrigation_systems: list[IrrigationSystem] = self.instance.irrigation_systems.all()
        irrigation_phases: list[IrrigationPhase] = self.instance.irrigation_phases.all()

        for irrigation_system in irrigation_systems:
            if not irrigation_system.is_ready():
                data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")
                break

        for irrigation_phase in irrigation_phases:
            if not irrigation_phase.is_ready():
                data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")
                break

        return data


class IrrigationReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Irrigation
        fields = "__all__"
        ref_name = "Irrigation"
        mandatory_fields = {}


# IrrigationSystem


class IrrigationSystemWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = IrrigationSystem
        fields = "__all__"
        ref_name = "IrrigationSystem"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "irrigation_system_type",
                    "ha_start",
                ],
            },
            "with": {
                "mandatory": [
                    "irrigation_system_type",
                    "ha_w",
                ],
            },
            "without": {
                "mandatory": [
                    "irrigation_system_type",
                    "ha_wo",
                ],
            },
        }

    def validate(self, data):
        super().validate(data)

        max_entries = ConfigParam.objects.get(name=labels.IRRIGATION_SYSTEMS_LIMIT).get_parsed_value()

        if self.instance and self.instance.parent.irrigation_systems.all().count() + 1 > max_entries:
            raise serializers.ValidationError(f"Only {max_entries} irrigation systems are allowed")

        return data


class IrrigationSystemReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = IrrigationSystem
        fields = "__all__"
        ref_name = "IrrigationSystem"
        mandatory_fields = {}


# IrrigationPhase


class IrrigationPhaseWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = IrrigationPhase
        fields = "__all__"
        ref_name = "IrrigationPhase"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "gross_irrigation_water_start",
                    "irrigation_system_type",
                    "fuel_type_start",
                    "well_depth",
                    "ha_start",
                ],
            },
            "with": {
                "mandatory": [
                    "gross_irrigation_water_w",
                    "irrigation_system_type",
                    "fuel_type_w",
                    "well_depth",
                    "ha_w",
                ],
            },
            "without": {
                "mandatory": [
                    "gross_irrigation_water_wo",
                    "irrigation_system_type",
                    "fuel_type_wo",
                    "well_depth",
                    "ha_wo",
                ],
            },
        }

    def validate(self, data):
        super().validate(data)

        max_entries = ConfigParam.objects.get(name=labels.IRRIGATION_PHASES_LIMIT).get_parsed_value()

        if self.instance and self.instance.parent.irrigation_phases.all().count() + 1 > max_entries:
            raise serializers.ValidationError(f"Only {max_entries} irrigation phases are allowed")

        return data


class IrrigationPhaseReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = IrrigationPhase
        fields = "__all__"
        ref_name = "IrrigationPhase"
        mandatory_fields = {}


class EnergySerializer(ScenarioModuleSerializer):
    fuels = serializers.SerializerMethodField(read_only=True)
    electricities = serializers.SerializerMethodField(read_only=True)

    def get_fuels(self, instance):
        return FuelReadSerializer(instance.fuels.all(), many=True).data

    def get_electricities(self, instance):
        return ElectricityReadSerializer(instance.electricities.all(), many=True).data

    class Meta:
        model = Energy
        fields = "__all__"
        ref_name = "Energy"
        mandatory_fields = {}

    def validate(self, data):
        super().validate(data)

        electricities: QuerySet[Electricity] = self.instance.electricities.all()
        fuels: QuerySet[Fuel] = self.instance.fuels.all()

        if any([not entry.is_ready() for entry in self.instance.entries.all()]):
            data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")

        if any([not electricity.is_ready() for electricity in electricities]):
            data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")

        if any([not fuel.is_ready() for fuel in fuels]):
            data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")

        return data


class EnergyWriteSerializer(EnergySerializer):
    pass


class EnergyReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Energy
        fields = "__all__"
        ref_name = "Energy"
        mandatory_fields = {}


# Fuel


class FuelSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = Fuel
        fields = "__all__"
        ref_name = "Fuel"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "fuel_type_start",
                    "quantity_consumed_per_year_start",
                ],
            },
            "with": {
                "mandatory": [
                    "fuel_type_w",
                    "quantity_consumed_per_year_w",
                ],
            },
            "without": {
                "mandatory": [
                    "fuel_type_wo",
                    "quantity_consumed_per_year_wo",
                ],
            },
        }

    def validate(self, data):
        super().validate(data)

        parent = utils.getany([self.instance, dict(data)], "parent")
        max_elements = ConfigParam.objects.get(name=labels.FUEL_MODULES_LIMIT).get_parsed_value()

        if parent.fuels.count() + 1 > max_elements:
            raise serializers.ValidationError(f"Only {max_elements} fuel modules are allowed")

        return data


class FuelWriteSerializer(FuelSerializer):
    pass


class FuelReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Fuel
        fields = "__all__"
        ref_name = "Fuel"
        mandatory_fields = {}


# EnergyEntry
class EnergyEntryWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = EnergyEntry
        fields = "__all__"
        ref_name = "EnergyEntry"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "fuel_type_start",
                    "quantity_consumed_per_year_start",
                    "transmission_loss_t2_start",
                ],
            },
            "with": {
                "mandatory": [
                    "fuel_type_w",
                    "quantity_consumed_per_year_w",
                    "transmission_loss_t2_w",
                ],
            },
            "without": {
                "mandatory": [
                    "fuel_type_wo",
                    "quantity_consumed_per_year_wo",
                    "transmission_loss_t2_wo",
                ],
            },
        }


class EnergyEntryReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = EnergyEntry
        fields = "__all__"
        ref_name = "EnergyEntry"
        mandatory_fields = {}


class ElectricityWriteSerializer(NoScenarioSubmoduleSerializer):
    class Meta:
        model = Electricity
        fields = "__all__"
        ref_name = "Electricity"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "quantity_consumed_per_year_start",
                    "transmission_loss_t2_start",
                ],
            },
            "with": {
                "mandatory": [
                    "quantity_consumed_per_year_w",
                    "transmission_loss_t2_w",
                ],
            },
            "without": {
                "mandatory": [
                    "quantity_consumed_per_year_wo",
                    "transmission_loss_t2_wo",
                ],
            },
        }

    def validate(self, data):
        super().validate(data)

        parent = utils.getany([self.instance, dict(data)], "parent")
        max_elements = ConfigParam.objects.get(name=labels.ELECTRICITY_MODULES_LIMIT).get_parsed_value()

        if not self.instance and parent.electricities.count() + 1 > max_elements:
            raise serializers.ValidationError(f"Only {max_elements} electricity modules are allowed")

        return data


class ElectricityReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Electricity
        fields = "__all__"
        ref_name = "Electricity"
        mandatory_fields = {}


# Livestock


class LivestockWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = Livestock
        fields = "__all__"
        ref_name = "Livestock"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "livestock_category_type",
                    "livestock_production_type_start",
                    "heads_number_start",
                ],
                "conditional": {
                    "complementary_manure_management_type_start": [],
                },
            },
            "with": {
                "mandatory": [
                    "livestock_category_type",
                    "livestock_production_type_w",
                    "heads_number_w",
                ],
                "conditional": {
                    "complementary_manure_management_type_w": [],
                },
            },
            "without": {
                "mandatory": [
                    "livestock_category_type",
                    "livestock_production_type_wo",
                    "heads_number_wo",
                ],
                "conditional": {
                    "complementary_manure_management_type_wo": [],
                },
            },
        }


class LivestockReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Livestock
        fields = "__all__"
        ref_name = "Livestock"
        mandatory_fields = LivestockWriteSerializer.Meta.mandatory_fields


# Aquaculture


class AquacultureWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = Aquaculture
        fields = "__all__"
        ref_name = "Aquaculture"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "annual_production_start",
                ],
            },
            "with": {
                "mandatory": [
                    "annual_production_w",
                ],
            },
            "without": {
                "mandatory": [
                    "annual_production_wo",
                ],
            },
        }

    def validate(self, data):
        return super().validate(data)


class AquacultureReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Aquaculture
        fields = "__all__"
        ref_name = "Aquaculture"
        mandatory_fields = AquacultureWriteSerializer.Meta.mandatory_fields


# SmllFishery


class SmallFisheryWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = SmallFishery
        fields = "__all__"
        ref_name = "SmallFishery"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "fishery_type",
                ],
                "conditional": {
                    "gear_type_start": [
                        "total_catch_yr_start",
                    ],
                },
            },
            "with": {
                "mandatory": [
                    "fishery_type",
                ],
                "conditional": {
                    "gear_type_w": [
                        "total_catch_yr_w",
                    ],
                },
            },
            "without": {
                "mandatory": [
                    "fishery_type",
                ],
                "conditional": {
                    "gear_type_wo": [
                        "total_catch_yr_wo",
                    ],
                },
            },
        }


class SmallFisheryReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = SmallFishery
        fields = "__all__"
        ref_name = "SmallFishery"
        mandatory_fields = SmallFisheryWriteSerializer.Meta.mandatory_fields


# LargeFishery


class LargeFisheryWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = LargeFishery
        fields = "__all__"
        ref_name = "LargeFishery"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "fish_type",
                ],
                "conditional": {
                    "gear_type_start": [
                        "total_catch_yr_start",
                    ],
                },
            },
            "with": {
                "mandatory": [
                    "fish_type",
                ],
                "conditional": {
                    "gear_type_w": [
                        "total_catch_yr_w",
                    ],
                },
            },
            "without": {
                "mandatory": [
                    "fish_type",
                ],
                "conditional": {
                    "gear_type_wo": [
                        "total_catch_yr_wo",
                    ],
                },
            },
        }


class LargeFisheryReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = LargeFishery
        fields = "__all__"
        ref_name = "LargeFishery"
        mandatory_fields = LargeFisheryWriteSerializer.Meta.mandatory_fields


# Waterbody


class WaterbodySerializer(LandModuleSeralizer):
    class Meta:
        model = Waterbody
        fields = "__all__"
        ref_name = "Waterbody"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "waterbody_type",
                    "area",
                    "trophic_type_start",
                ],
            },
            "with": {
                "mandatory": [
                    "waterbody_type",
                    "area",
                    "trophic_type_w",
                ],
            },
            "without": {
                "mandatory": [
                    "waterbody_type",
                    "area",
                    "trophic_type_wo",
                ],
            },
        }


class WaterbodyWriteSerializer(WaterbodySerializer):
    pass


class WaterbodyReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Waterbody
        fields = "__all__"
        ref_name = "Waterbody"
        mandatory_fields = WaterbodyWriteSerializer.Meta.mandatory_fields


class ProjectNameIdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name"]


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["name"]
        ref_name = "Permission"


class GroupSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = "__all__"
        ref_name = "Group"


class ProjectInvitationReadSerializer(serializers.ModelSerializer):
    user = UserReadSerializer(many=False, read_only=True)
    project = ProjectNameIdSerializer(many=False, read_only=True)
    group = GroupSerializer(many=False, read_only=True)
    status = get_model_serializer(InvitationStatusType)(many=False, read_only=True)

    class Meta:
        model = ProjectInvitation
        fields = "__all__"
        ref_name = "ProjectInvitation"


class ForestManagementWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = ForestManagement
        fields = "__all__"
        ref_name = "ForestManagement"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "land_use_type_start",
                    "forest_condition_type",
                    "forest_type",
                ],
                "conditional": {
                    "rotation_length_yrs_start": [
                        "rotation_percentage_biomass_for_energy_start",
                    ],
                    "logging_recurrence_yrs_start": [
                        "logging_percentage_agb_logged_start",
                        "logging_percentage_biomass_for_energy_start",
                    ],
                },
            },
            "with": {
                "mandatory": [
                    "land_use_type_start",
                    "forest_condition_type",
                    "forest_type",
                ],
                "conditional": {
                    "rotation_length_yrs_w": [
                        "rotation_percentage_biomass_for_energy_w",
                    ],
                    "logging_recurrence_yrs_w": [
                        "logging_percentage_agb_logged_w",
                        "logging_percentage_biomass_for_energy_w",
                    ],
                },
            },
            "without": {
                "mandatory": [
                    "land_use_type_start",
                    "forest_condition_type",
                    "forest_type",
                ],
                "conditional": {
                    "rotation_length_yrs_wo": [
                        "rotation_percentage_biomass_for_energy_wo",
                    ],
                    "logging_recurrence_yrs_wo": [
                        "logging_percentage_agb_logged_wo",
                        "logging_percentage_biomass_for_energy_wo",
                    ],
                },
            },
        }

    def validate(self, data):
        super().validate(data)

        errors = []

        instance: ForestManagement = self.instance

        data = self.merge_instance_data(data, instance=instance)
        disturbances = self.instance.disturbances.all().count() if self.instance else 0
        scenarios = [utils.ScenarioTypes.START.value, utils.ScenarioTypes.WITH.value, utils.ScenarioTypes.WITHOUT.value]

        def has_data_for(scenario, *keys):
            return any(data.get(f"{key}_{scenario}") for key in keys)

        for scenario in scenarios:
            verbose_scenario_name = utils.ScenarioTypes(scenario).verbose_name

            if has_data_for(scenario, "rotation_length_yrs") and (has_data_for(scenario, "logging_recurrence_yrs", "average_yearly_degradation_percentage") or disturbances):
                errors.append(f"If a forest has rotation it cannot have logging, degradation, or disturbances in the {verbose_scenario_name} scenario")

            if has_data_for(scenario, "logging_recurrence_yrs") and has_data_for(scenario, "rotation_length_yrs", "average_yearly_degradation_percentage"):
                errors.append(f"If a forest has logging it cannot have rotation or degradation in the {verbose_scenario_name} scenario")

            if disturbances and has_data_for(scenario, "rotation_length_yrs", "degredation_dry_matter_impacted_t2"):
                errors.append(f"If a forest has disturbances it cannot have rotation or degradation in the {verbose_scenario_name} scenario")

            if has_data_for(scenario, "average_yearly_degradation_percentage") and (has_data_for(scenario, "rotation_length_yrs", "logging_recurrence_yrs") or disturbances):
                errors.append(f"If a forest has degradation it cannot have rotation, logging, or disturbances in the {verbose_scenario_name} scenario")

        if instance and instance.disturbances.count() > 0:
            pc_biomass_destruction_start = data.get("logging_percentage_agb_logged_start", 0) or 0
            pc_biomass_destruction_wo = data.get("logging_percentage_agb_logged_wo", 0) or 0
            pc_biomass_destruction_w = data.get("logging_percentage_agb_logged_w", 0) or 0

            for disturbance in instance.disturbances.all():
                disturbance: ForestDisturbance
                pc_biomass_destruction_start += disturbance.percentage_biomass_destruction_start if disturbance.percentage_biomass_destruction_start else 0
                pc_biomass_destruction_wo += disturbance.percentage_biomass_destruction_wo if disturbance.percentage_biomass_destruction_wo else 0
                pc_biomass_destruction_w += disturbance.percentage_biomass_destruction_w if disturbance.percentage_biomass_destruction_w else 0

            max_pc = ConfigParam.objects.get(name=labels.MAX_PC_BIOMASS_DESTRUCTION).get_parsed_value()

            if pc_biomass_destruction_start > max_pc:
                errors += [serializers.ValidationError("Total percentage of biomass destruction (start) cannot be greater than 100%")]

            if pc_biomass_destruction_wo > max_pc:
                errors += [serializers.ValidationError("Total percentage of biomass destruction (without) cannot be greater than 100%")]

            if pc_biomass_destruction_w > max_pc:
                errors += [serializers.ValidationError("Total percentage of biomass destruction (with) cannot be greater than 100%")]

        if errors:
            raise serializers.ValidationError(errors)

        if any([not d.is_ready() for d in instance.disturbances.all()]):
            data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")

        return data


class ForestManagementReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = ForestManagement
        fields = "__all__"
        ref_name = "ForestManagement"
        mandatory_fields = ForestManagementWriteSerializer.Meta.mandatory_fields


class InputSerializer(ScenarioModuleSerializer):
    class Meta:
        model = Input
        fields = "__all__"
        ref_name = "Input"
        mandatory_fields = {}

    def validate(self, data):
        entries = InputEntry.objects.filter(parent=self.instance).all()
        for entry in entries:
            entry: InputEntry
            if not entry.is_ready():
                data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")
                return data

        return super().validate(data)


class InputWriteSerializer(InputSerializer):
    pass


class InputReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Input
        fields = "__all__"
        ref_name = "Input"
        mandatory_fields = {}


class InputEntrySerializer(ScenarioSubmoduleSerializer):
    module_type = serializers.SerializerMethodField(read_only=True)

    def get_module_type(self, obj):
        return get_model_serializer(ModuleType)(ModuleType.objects.get(class_name=obj.__class__.__name__), many=False).data

    class Meta:
        model = InputEntry
        fields = "__all__"
        ref_name = "InputEntry"
        extra_fields = ["module_type"]
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "input_type",
                    "value_start",
                ],
            },
            "with": {
                "mandatory": [
                    "input_type",
                    "value_w",
                ],
            },
            "without": {
                "mandatory": [
                    "input_type",
                    "value_wo",
                ],
            },
        }

    def validate(self, data):
        super().validate(data)

        parent = utils.getany([self.instance, dict(data)], "parent")
        max_entries = ConfigParam.objects.get(name=labels.INPUT_ENTRIES_LIMIT).get_parsed_value()

        if parent.input_entries.count() + 1 > max_entries:
            raise serializers.ValidationError(f"Only {max_entries} input entries are allowed")

        return data


class InputEntryWriteSerializer(InputEntrySerializer):
    pass


class InputEntryReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = InputEntry
        fields = "__all__"
        ref_name = "InputEntry"
        mandatory_fields = {}


class DynamicResultSerializer(serializers.Serializer):
    total_w = serializers.SerializerMethodField()
    total_wo = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    inventory = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        self.aggregate_by = kwargs.pop("aggregate_by", None)
        super().__init__(*args, **kwargs)

    def get_breakdown_type(self, obj):
        return self.Meta.breakdown_type

    def get_total_w(self, obj):
        return self._serialize_data(obj.get("total_w"))

    def get_total_wo(self, obj):
        return self._serialize_data(obj.get("total_wo"))

    def get_balance(self, obj):
        return self._serialize_data(obj.get("balance"))

    def get_inventory(self, obj):
        return obj.get("inventory")

    def _serialize_data(self, data):
        match self.aggregate_by:
            case BreakdownTypes.TOTAL:
                return data
            case BreakdownTypes.GAS:
                return YearlyGasEmissionSerializer(data, many=True).data
            case BreakdownTypes.ACTIVITY:
                return YearlyActivityEmissionSerializer(data, many=True).data
            case BreakdownTypes.ACTIVITY_GAS:
                return YearlyActivityEmissionSerializer(data, many=True).data
            case _:
                raise ValueError("Invalid breakdown type")


class DynamicResultFactory:
    @staticmethod
    def create(activity: Activity, data: dict, aggregate_by: Optional[BreakdownTypes] = BreakdownTypes.TOTAL):
        results = DynamicResultFactory.prepare_data(activity, data, aggregate_by)
        return DynamicResultSerializer(results, aggregate_by=aggregate_by)

    @staticmethod
    def prepare_data(activity: Activity, data: dict, aggregate_by: Optional[BreakdownTypes] = BreakdownTypes.TOTAL):
        results = {
            "total_w": data[0],
            "total_wo": data[1],
            "balance": data[2],
        }

        match aggregate_by:
            case BreakdownTypes.TOTAL:
                pass
            case BreakdownTypes.GAS | BreakdownTypes.ACTIVITY | BreakdownTypes.ACTIVITY_GAS:
                results["total_w"] = list(results["total_w"])
                results["total_wo"] = list(results["total_wo"])
                results["balance"] = list(results["balance"])
            case _:
                raise ValueError("Invalid breakdown type")

        return results


class MacroInputTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MacroInputType
        fields = "__all__"
        ref_name = "MacroInputType"


class InputTypeSerializer(serializers.ModelSerializer):
    macro_input_type = MacroInputTypeSerializer(many=False, read_only=True)

    class Meta:
        model = InputType
        fields = "__all__"
        ref_name = "InputType"


def check_member_management_allowed(project: Project, request):
    """Guard for adding/updating project memberships and invitations.

    Archived projects are closed for good. Finalized projects are read-only for
    everyone except the people who administer them: project Admins (and
    superusers, who bypass every other project permission check) must still be
    able to hand over or share administration after finalization.
    """
    user = getattr(request, "user", None)
    is_project_admin = user is not None and user.is_authenticated and (user.is_superuser or project.members.filter(user=user, group__name="Admin").exists())

    if project.is_archived:
        raise serializers.ValidationError("Cannot add members to an archived project")

    if project.is_finalized and not is_project_admin:
        raise serializers.ValidationError("Cannot add members to a finalized project")


class ProjectMembershipWriteSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), many=False, write_only=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), many=False, write_only=True)
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), many=False, write_only=True)

    class Meta:
        model = ProjectMembership
        fields = ["project", "user", "group"]
        ref_name = "ProjectMembership"

    def validate(self, data):
        super().validate(data)

        project: Project = utils.getany([data, self.instance], "project")

        check_member_management_allowed(project, self.context.get("request"))

        return data


class ProjectMembershipReadSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    project = ProjectNameIdSerializer(many=False, read_only=True)
    user = UserReadSerializer(many=False, read_only=True)
    group = GroupSerializer(many=False, read_only=True)

    class Meta:
        model = ProjectMembership
        fields = "__all__"
        ref_name = "ProjectMembership"


class ProjectNotificationPreferenceReadSerializer(serializers.ModelSerializer):
    project = ProjectNameIdSerializer(many=False, read_only=True)
    user = UserReadSerializer(many=False, read_only=True)

    class Meta:
        model = ProjectNotificationPreference
        fields = ["id", "project", "user", "is_subscribed", "created_at", "updated_at"]
        ref_name = "ProjectNotificationPreference"


class ProjectNotificationPreferenceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectNotificationPreference
        fields = ["project", "is_subscribed"]
        ref_name = "ProjectNotificationPreference"

    def validate(self, data):
        super().validate(data)

        # Get the user from the request context
        user = self.context["request"].user
        project = data["project"]

        # Check if user is a member of the project
        if not ProjectMembership.objects.filter(user=user, project=project).exists():
            raise serializers.ValidationError("You must be a member of this project to manage notification preferences")

        return data

    def create(self, validated_data):
        # Set the user from the request context
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Ensure user can only update their own preferences
        if instance.user != self.context["request"].user:
            raise serializers.ValidationError("You can only update your own notification preferences")
        return super().update(instance, validated_data)


class SetAsideWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = SetAside
        fields = "__all__"
        ref_name = "SetAside"
        mandatory_fields = {}


class SetAsideReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = SetAside
        fields = "__all__"
        ref_name = "SetAside"
        mandatory_fields = {}


class OtherLandWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = OtherLand
        fields = "__all__"
        ref_name = "OtherLand"
        mandatory_fields = {}


class OtherLandReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = OtherLand
        fields = "__all__"
        ref_name = "OtherLand"
        mandatory_fields = {}


class SettlementSerializer(LandModuleSeralizer):
    class Meta:
        model = Settlement
        fields = "__all__"
        ref_name = "Settlement"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "settlement_type_start",
                ],
            },
            "with": {
                "mandatory": [
                    "settlement_type_w",
                ],
            },
            "without": {
                "mandatory": [
                    "settlement_type_wo",
                ],
            },
        }

    def validate(self, data):
        super().validate(data)

        buildings = Building.objects.filter(parent=self.instance).all()

        if any(not building.is_ready() for building in buildings):
            data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")

        roads = Road.objects.filter(parent=self.instance).all()

        if any(not road.is_ready() for road in roads):
            data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")

        other_infrastructures = OtherInfrastructure.objects.filter(parent=self.instance).all()

        if any(not other_infrastructure.is_ready() for other_infrastructure in other_infrastructures):
            data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")

        return data


class SettlementWriteSerializer(SettlementSerializer):
    pass


class SettlementReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Settlement
        fields = "__all__"
        ref_name = "Settlement"
        mandatory_fields = {}


class ConfigParamSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigParam
        fields = "__all__"
        ref_name = "ConfigParams"

    def validate(self, data):
        if not self.context["request"].user.is_staff:
            raise serializers.ValidationError("You do not have permission to change this parameter")


class MacroFuelTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MacroFuelType
        fields = "__all__"
        ref_name = "MacroFuelType"


class FuelUseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuelUseType
        fields = "__all__"
        ref_name = "FuelUseType"


class FuelTypeSerializer(serializers.ModelSerializer):
    macro_fuel_type = MacroFuelTypeSerializer(many=False, read_only=True)
    fuel_use_type = FuelUseTypeSerializer(many=False, read_only=True)
    unit = serializers.SerializerMethodField()

    def get_unit(self, obj):
        return obj.unit.name if obj.unit else None

    class Meta:
        model = FuelType
        fields = "__all__"
        ref_name = "FuelType"


class CoastalWetlandSerializer(NoScenarioModuleSerializer):
    class Meta:
        model = CoastalWetland
        fields = "__all__"
        ref_name = "CoastalWetland"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "land_use_type",
                    "area",
                ],
            },
            "with": {
                "mandatory": [
                    "land_use_type",
                    "area",
                ],
            },
            "without": {
                "mandatory": [
                    "land_use_type",
                    "area",
                ],
            },
        }


class CoastalWetlandWriteSerializer(CoastalWetlandSerializer):
    pass


class CoastalWetlandReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = CoastalWetland
        fields = "__all__"
        ref_name = "CoastalWetland"
        mandatory_fields = {}


class ForestDisturbanceWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = ForestDisturbance
        fields = "__all__"
        ref_name = "ForestDisturbance"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "disturbance_type",
                ],
                "conditional": {
                    "recurrence_yrs_start": [
                        "percentage_biomass_destruction_start",
                    ],
                },
            },
            "with": {
                "mandatory": [
                    "disturbance_type",
                ],
                "conditional": {
                    "recurrence_yrs_w": [
                        "percentage_biomass_destruction_w",
                    ],
                },
            },
            "without": {
                "mandatory": [
                    "disturbance_type",
                ],
                "conditional": {
                    "recurrence_yrs_wo": [
                        "percentage_biomass_destruction_wo",
                    ],
                },
            },
        }

    def validate(self, data):
        super().validate(data)

        parent = utils.getany([self.instance, dict(data)], "parent")

        if parent.disturbances.count() + 1 > 3:
            raise serializers.ValidationError("Only 3 disturbances are allowed")

        if not self.instance or not self.instance.is_ready():
            parent.status = StatusType.objects.get(name_en="SUBMODULES_EMPTY")
            parent.save()

        return data


class ForestDisturbanceReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = ForestDisturbance
        fields = "__all__"
        ref_name = "ForestDisturbance"
        mandatory_fields = ForestDisturbanceWriteSerializer.Meta.mandatory_fields


class ChangeSerializer(serializers.Serializer):
    field = serializers.CharField()
    new = serializers.CharField()
    old = serializers.CharField()


class ChangeHistorySerializer(serializers.Serializer):
    reason = serializers.CharField()
    date = serializers.DateTimeField()
    user = serializers.EmailField()
    changes = ChangeSerializer(many=True)


class ProjectInvitationModelReadSerializer(serializers.ModelSerializer):
    project = ReadProjectSerializer(many=False, read_only=True)
    group = GroupSerializer(many=False, read_only=True)
    status = get_model_serializer(InvitationStatusType)(many=False, read_only=True)

    class Meta:
        model = ProjectInvitation
        fields = "__all__"
        ref_name = "ProjectInvitation"


class ProjectInvitationModelWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectInvitation
        fields = "__all__"
        ref_name = "ProjectInvitation"


class ProjectInvitationWriteSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=True)

    class Meta:
        model = ProjectInvitation
        fields = ["email", "group", "project"]
        ref_name = "ProjectInvitation"

    def validate(self, data):
        super().validate(data)

        project: Project = utils.getany([data, self.instance], "project")

        check_member_management_allowed(project, self.context.get("request"))

        if self.instance:
            new_status = InvitationStatusType.objects.filter(id=data.get("status", None)).first()
            if self.instance.status.name_en != utils.InvitationStatus.PENDING.value and (new_status and new_status.name_en == utils.InvitationStatus.ACCEPTED.value):
                raise serializers.ValidationError("Cannot accept an invitation that is not pending")

        return data


class ProjectInvitationAcceptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectInvitation
        fields = ["status"]
        ref_name = "ProjectInvitation"

    def validate(self, data):
        super().validate(data)

        if uuid.UUID(self.context.get("token", None)) != self.instance.token:
            raise serializers.ValidationError("Invalid token")

        if self.instance.status.name_en != utils.InvitationStatus.PENDING.value and (data.get("status", None) and data.get("status", None).name_en == utils.InvitationStatus.ACCEPTED.value):
            raise serializers.ValidationError("Cannot accept an invitation that is not pending")

        return data

    def save(self, **kwargs):
        self.instance.status = InvitationStatusType.objects.get(name_en=utils.InvitationStatus.ACCEPTED.value)
        self.instance.save()
        return self.instance


class NewNoteSerializer(serializers.ModelSerializer):
    content = serializers.CharField(required=True)
    module_type_id = serializers.IntegerField(required=False)
    module_id = serializers.IntegerField(required=True)

    class Meta:
        model = Note
        fields = ["content", "module_type_id", "module_id"]
        ref_name = "Note"

    def validate(self, data):
        if data.get("module_type_id", None) is None:
            raise serializers.ValidationError("Module type ID is required for modules")

        try:
            module_type = ModuleType.objects.get(pk=data["module_type_id"])
        except ModuleType.DoesNotExist:
            raise serializers.ValidationError("Module type does not exist")

        ModuleClass = utils.get_model(module_type.class_name, suffix=None)
        try:
            module: Module | Submodule | Project = ModuleClass.objects.get(pk=data["module_id"])
        except ModuleClass.DoesNotExist:
            raise serializers.ValidationError("Module does not exist")

        module_note = Note.objects.filter(content_type=ContentType.objects.get_for_model(module), object_id=module.id).first()

        if module_note:
            raise serializers.ValidationError(f"Note already exists for this {module_type.name}.")

        return super().validate(data)

    def save(self, **kwargs):
        module_type = ModuleType.objects.get(pk=self.validated_data["module_type_id"])
        ModuleClass = utils.get_model(module_type.class_name, suffix=None)
        content_object = ModuleClass.objects.get(pk=self.validated_data["module_id"])

        note = Note.objects.create(
            author=self.context["request"].user,
            content=self.validated_data["content"],
            content_object=content_object,
        )

        return note


class NoteSerializer(serializers.ModelSerializer):
    module_type = serializers.SerializerMethodField(read_only=True)
    module_id = serializers.SerializerMethodField(read_only=True)

    def get_module_type(self, obj):
        module_type = ModuleType.objects.get(class_name=obj.content_object.__class__.__name__)
        return get_model_serializer(ModuleType)(module_type, many=False).data

    def get_module_id(self, obj):
        return obj.content_object.id

    def validate(self, data):
        if not self.instance:
            raise serializers.ValidationError("Instance not found")

        project: Project = self.instance.project
        if not project:
            raise serializers.ValidationError("Project not found")

        if project.is_archived:
            raise serializers.ValidationError("Project is archived")

        if project.is_finalized:
            raise serializers.ValidationError("Project is finalized")

        return super().validate(data)

    class Meta:
        model = Note
        fields = ["id", "content", "module_type", "module_id"]
        ref_name = "Note"


class ResetPasswordSerializer(serializers.Serializer):
    password_old = serializers.CharField(required=True)
    password_new = serializers.CharField(required=True)

    def validate(self, data):
        user: CustomUser = self.context["request"].user
        psasword_old = data.get("password_old", None)
        password_new = data.get("password_new", None)

        if not user.check_password(data["password_old"]):
            raise serializers.ValidationError("Old password is incorrect")

        if password_new is None or psasword_old is None:
            raise serializers.ValidationError("Old and new password are required")

        return super().validate(data)


class FieldDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldDefinition
        fields = ("field_name", "description")
        ref_name = "FieldDefinition"


class FieldMetadataSerializer(serializers.Serializer):
    description = serializers.CharField()


class FieldDefinitionResponseSerializer(serializers.Serializer):
    field_name = FieldMetadataSerializer(many=True)


class ValueChainParentModuleSerializer(ScenarioModuleSerializer):
    def validate(self, data):
        super().validate(data)

        if not self.instance:
            return data

        entries = self.instance.entries.all()

        if any([not submodule.is_ready() for submodule in entries]):
            data["status"] = StatusType.objects.get(name_en="SUBMODULES_EMPTY")

        return data


class ValueChainSubmoduleWriteSerializer(ScenarioSubmoduleSerializer):
    pass


class StorageSerializer(ValueChainParentModuleSerializer):
    class Meta:
        model = Storage
        fields = "__all__"
        ref_name = "Storage"
        mandatory_fields = {}


class StorageWriteSerializer(StorageSerializer):
    pass


class StorageReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Storage
        fields = "__all__"
        ref_name = "Storage"
        mandatory_fields = {}


class StorageEntrySerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = StorageEntry
        fields = "__all__"
        ref_name = "StorageEntry"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "quantity_consumed_per_year_start",
                ],
                "conditional": {
                    "is_refrigerant_used": [
                        "refrigerant_type_start",
                        "total_refrigerant_leakage_start",
                    ]
                },
            },
            "with": {
                "mandatory": [
                    "quantity_consumed_per_year_w",
                ],
                "conditional": {
                    "is_refrigerant_used": [
                        "refrigerant_type_w",
                        "total_refrigerant_leakage_w",
                    ]
                },
            },
            "without": {
                "mandatory": [
                    "quantity_consumed_per_year_wo",
                ],
                "conditional": {
                    "is_refrigerant_used": [
                        "refrigerant_type_wo",
                        "total_refrigerant_leakage_wo",
                    ]
                },
            },
        }


class StorageEntryWriteSerializer(StorageEntrySerializer, ValueChainSubmoduleWriteSerializer):
    pass


class StorageEntryReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = StorageEntry
        fields = "__all__"
        ref_name = "StorageEntry"
        mandatory_fields = {}


class ProcessingSerializer(ValueChainParentModuleSerializer):
    class Meta:
        model = Processing
        fields = "__all__"
        ref_name = "Processing"
        mandatory_fields = {}


class ProcessingWriteSerializer(ProcessingSerializer):
    pass


class ProcessingReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Processing
        fields = "__all__"
        ref_name = "Processing"
        mandatory_fields = {}


class ProcessingEntrySerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = ProcessingEntry
        fields = "__all__"
        ref_name = "ProcessingEntry"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "fuel_type_start",
                    "quantity_consumed_per_year_start",
                ],
                "conditional": {
                    "is_water_used": [
                        "water_use_per_year_start",
                    ]
                },
            },
            "with": {
                "mandatory": [
                    "fuel_type_w",
                    "quantity_consumed_per_year_w",
                ],
                "conditional": {
                    "is_water_used": [
                        "water_use_per_year_w",
                    ]
                },
            },
            "without": {
                "mandatory": [
                    "fuel_type_wo",
                    "quantity_consumed_per_year_wo",
                ],
                "conditional": {
                    "is_water_used": [
                        "water_use_per_year_wo",
                    ]
                },
            },
        }


class ProcessingEntryWriteSerializer(ProcessingEntrySerializer, ValueChainSubmoduleWriteSerializer):
    pass


class ProcessingEntryReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = ProcessingEntry
        fields = "__all__"
        ref_name = "ProcessingEntry"
        mandatory_fields = {}


class PackagingSerializer(ValueChainParentModuleSerializer):
    class Meta:
        model = Packaging
        fields = "__all__"
        ref_name = "Packaging"
        mandatory_fields = {}


class PackagingWriteSerializer(PackagingSerializer):
    pass


class PackagingReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Packaging
        fields = "__all__"
        ref_name = "Packaging"
        mandatory_fields = {}


class PackagingEntrySerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = PackagingEntry
        fields = "__all__"
        ref_name = "PackagingEntry"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "packaging_material_type_start",
                    "kg_of_packaging_material_start",
                ],
                "conditional": {
                    "is_electric": [
                        "quantity_consumed_per_year_start",
                    ],
                },
            },
            "with": {
                "mandatory": [
                    "packaging_material_type_w",
                    "kg_of_packaging_material_w",
                ],
                "conditional": {
                    "is_electric": [
                        "quantity_consumed_per_year_w",
                    ],
                },
            },
            "without": {
                "mandatory": [
                    "packaging_material_type_wo",
                    "kg_of_packaging_material_wo",
                ],
                "conditional": {
                    "is_electric": [
                        "quantity_consumed_per_year_wo",
                    ]
                },
            },
        }


class PackagingEntryWriteSerializer(PackagingEntrySerializer, ValueChainSubmoduleWriteSerializer):
    pass


class PackagingEntryReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = PackagingEntry
        fields = "__all__"
        ref_name = "PackagingEntry"
        mandatory_fields = {}


class TransportSerializer(ValueChainParentModuleSerializer):
    class Meta:
        model = Transport
        fields = "__all__"
        ref_name = "Transport"
        mandatory_fields = {}


class TransportWriteSerializer(TransportSerializer):
    pass


class TransportReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Transport
        fields = "__all__"
        ref_name = "Transport"
        mandatory_fields = {}


class TransportEntrySerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = TransportEntry
        fields = "__all__"
        ref_name = "TransportEntry"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "fuel_type_start",
                    "quantity_consumed_per_year_start",
                ]
            },
            "with": {
                "mandatory": [
                    "fuel_type_w",
                    "quantity_consumed_per_year_w",
                ]
            },
            "without": {
                "mandatory": [
                    "fuel_type_wo",
                    "quantity_consumed_per_year_wo",
                ]
            },
        }


class TransportEntryWriteSerializer(TransportEntrySerializer, ValueChainSubmoduleWriteSerializer):
    pass


class TransportEntryReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = TransportEntry
        fields = "__all__"
        ref_name = "TransportEntry"
        mandatory_fields = {}


class ProjectFileUploadSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    bucket_public_url = serializers.URLField(read_only=True)
    file = serializers.FileField(required=True, write_only=True)
    size = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProjectFileAttachment
        fields = "__all__"
        ref_name = "ProjectFileAttachment"

    def validate(self, attrs):
        file = attrs["file"]

        project: Project = self.context["project"]

        if project.is_finalized:
            raise serializers.ValidationError("Finalized projects cannot be modified")

        max_size_in_mb = int(ApplicationParameter.objects.get(name__iexact="project_uploads_max_file_size_mb").value)

        if file.size > max_size_in_mb * 1024 * 1024:
            raise serializers.ValidationError(f"File size must be less than {max_size_in_mb}MB")

        attrs["file"].name = utils.get_unique_name(attrs["project"], file.name)

        return super().validate(attrs)

    def save(self, **kwargs):
        project = self.validated_data["project"]
        file = self.validated_data["file"]

        from google.cloud import storage

        blob = None
        try:
            client = storage.Client()
            bucket = client.get_bucket(settings.STORAGE_BUCKET)

            if not bucket.exists():
                raise serializers.ValidationError("Storage bucket does not exist")

            project_folder = f"projects/{project.id}/"
            blob = bucket.blob(f"{project_folder}{file.name}")

            file_size = file.size

            max_size_in_mb = int(ApplicationParameter.objects.get(name__iexact="project_uploads_max_file_size_mb").value)

            total_size = sum([b.size for b in bucket.list_blobs(prefix=project_folder)])
            if total_size + file_size > max_size_in_mb * 1024 * 1024:
                raise serializers.ValidationError(f"Maximum total project files size reached. Total size of all files in the project must be less than {max_size_in_mb}MB.")

            blob.upload_from_file(file, content_type=file.content_type)
            public_url = blob.public_url

            attachment = ProjectFileAttachment.objects.create(name=file.name, project=project, bucket_public_url=public_url, size=file_size)
        except Exception as e:
            if blob:
                blob.delete()
            raise serializers.ValidationError(str(e))

        return attachment


class ProjectFileReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFileAttachment
        fields = "__all__"
        ref_name = "ProjectFileAttachment"


class ProjectFileDownloadSerializer(serializers.Serializer):
    file_name = serializers.CharField()
    content_type = serializers.CharField()


class APIStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIHealth
        fields = ["is_under_maintenance", "maintenance_end_time", "maintenance_message"]
        ref_name = "APIStatus"


class ProjectLockHolderInformationSerializer(serializers.Serializer):
    is_locked = serializers.BooleanField()
    locked_at = serializers.DateTimeField()
    lock_updated_at = serializers.DateTimeField()
    locked_by = serializers.SerializerMethodField()

    def get_locked_by(self, obj):
        return obj.locked_by.email if obj.locked_by else None


class PublicTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicToken
        fields = "__all__"
        ref_name = "PublicToken"


class HandInHandRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandInHandRegion
        fields = "__all__"
        ref_name = "HandInHandRegion"


class HandInHandCountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = HandInHandCountry
        fields = "__all__"
        ref_name = "HandInHandCountry"


class HandInHandAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandInHandAssessment
        fields = ["id", "name", "year", "country", "link"]
        ref_name = "HandInHandAssessment"


class HandInHandAssessmentGroupedSerializer(serializers.Serializer):
    """
    Serializer that returns HandInHandAssessment data grouped by region > country > year
    """

    def to_representation(self, instance):
        # Get all assessments
        assessments = HandInHandAssessment.objects.select_related("country__region").order_by("country__region__name", "country__name", "year", "name")

        # Get all countries to ensure we include those without assessments
        all_countries = HandInHandCountry.objects.select_related("region").order_by("region__name", "name")

        # Group by region, then country, then year
        grouped_data = {}

        # First, initialize all countries with empty years structure
        for country in all_countries:
            region_name = country.region.name
            country_name = country.name

            # Initialize region if not exists
            if region_name not in grouped_data:
                grouped_data[region_name] = {"name": region_name, "countries": {}}

            # Initialize country if not exists
            if country_name not in grouped_data[region_name]["countries"]:
                grouped_data[region_name]["countries"][country_name] = {"name": country_name, "iso_code": country.iso_code, "years": {}}

        # Then, add assessments to their respective countries
        for assessment in assessments:
            region_name = assessment.country.region.name
            country_name = assessment.country.name
            year = assessment.year or "Unknown Year"

            # Initialize year if not exists
            if year not in grouped_data[region_name]["countries"][country_name]["years"]:
                grouped_data[region_name]["countries"][country_name]["years"][year] = {"year": year, "assessments": []}

            # Add assessment to the year
            grouped_data[region_name]["countries"][country_name]["years"][year]["assessments"].append({"id": assessment.id, "name": assessment.name, "link": assessment.link})

        # Convert nested dictionaries to lists for better JSON structure
        result = []
        for region_name, region_data in grouped_data.items():
            region_dict = {"name": region_data["name"], "countries": []}

            for country_name, country_data in region_data["countries"].items():
                country_dict = {"name": country_data["name"], "iso_code": country_data["iso_code"], "years": []}

                for year, year_data in country_data["years"].items():
                    country_dict["years"].append(year_data)

                # Sort years (handle "Unknown Year" case)
                country_dict["years"].sort(key=lambda x: float("inf") if x["year"] == "Unknown Year" else x["year"])
                region_dict["countries"].append(country_dict)

            # Sort countries alphabetically
            region_dict["countries"].sort(key=lambda x: x["name"])
            result.append(region_dict)

        # Sort regions alphabetically
        result.sort(key=lambda x: x["name"])

        return result


class AsyncJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AsyncJob
        fields = [
            "id", "kind", "status", "progress", "result", "error_message",
            "created_at", "started_at", "completed_at", "project",
        ]
        read_only_fields = fields
