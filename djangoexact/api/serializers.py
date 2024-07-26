import logging as log
from enum import Enum

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import Model
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

from . import labels
from .models import (
    Activity,
    AnnualCropping,
    Aquaculture,
    Building,
    Climate,
    CoastalWetland,
    Comment,
    CommentThread,
    ConfigParam,
    Country,
    CustomUser,
    DegradedLand,
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
    MacroFuelType,
    MacroInputType,
    MinorSeasonAnnualCropping,
    MinorSeasonFloodedRice,
    MinorSeasonPerennialCropping,
    ModuleType,
    Moisture,
    OrganicSoil,
    OtherInfrastructure,
    PerennialCropping,
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
    UserProjectGroup,
    Waterbody,
    LandModule,
    InvitationStatusType,
    ChangeRate,
)


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


def get_model_serializer(model_arg):

    class GenericSerializer(serializers.ModelSerializer):
        class Meta:
            model = model_arg
            fields = "__all__"
            ref_name = model_arg.__name__

    try:
        return globals()[model_arg.__name__ + "Serializer"]
    except KeyError:
        return GenericSerializer


def get_module_serializer(model_arg: Model, action=ActionTypes.RETRIEVE) -> serializers.ModelSerializer:
    try:
        match action:
            case ActionTypes.CREATE | ActionTypes.UPDATE:
                return globals()[model_arg.__name__ + "WriteSerializer"]
            case ActionTypes.RETRIEVE:
                return globals()[model_arg.__name__ + "ReadSerializer"]
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
        fields = ["id", "email", "first_name", "last_name", "country"]


class UserWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "first_name", "last_name", "country"]


class CountrySerializer(serializers.ModelSerializer):
    region = get_model_serializer(Region)(many=False, read_only=True)
    ipcc_region = get_model_serializer(IPCCRegion)(many=False, read_only=True)
    gleam_region = get_model_serializer(GLEAMRegion)(many=False, read_only=True)

    class Meta:
        model = Country
        fields = "__all__"
        ref_name = "Country"


class ReadProjectSerializer(serializers.ModelSerializer):
    climate = get_model_serializer(Climate)(many=False, read_only=True)
    country = CountrySerializer(many=False, read_only=True)
    moisture = get_model_serializer(Moisture)(many=False, read_only=True)
    soil_type = get_model_serializer(SoilType)(many=False, read_only=True)
    gw_potential = get_model_serializer(GlobalWarmingPotential)(many=False, read_only=True)
    status = get_model_serializer(ProjectStatus)(many=False, required=False, read_only=True)
    user = UserReadSerializer(many=False, read_only=True)
    role = serializers.SerializerMethodField()

    def get_role(self, obj):
        ctx = self.context.get("request", None)

        if not ctx:
            return []

        user = ctx.user
        user_project_group = UserProjectGroup.objects.filter(user=user, project=obj).all()

        if not user_project_group:
            return []

        return [group.group.name for group in user_project_group]

    class Meta:
        model = Project
        fields = "__all__"
        ref_name = "Project"


class WriteProjectSerializer(serializers.ModelSerializer):
    climate = serializers.PrimaryKeyRelatedField(queryset=Climate.objects.all(), required=True, write_only=True)
    country = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all(), required=True, write_only=True)
    moisture = serializers.PrimaryKeyRelatedField(queryset=Moisture.objects.all(), required=True, write_only=True)
    soil_type = serializers.PrimaryKeyRelatedField(queryset=SoilType.objects.all(), required=True, write_only=True)
    gw_potential = serializers.PrimaryKeyRelatedField(queryset=GlobalWarmingPotential.objects.all(), required=True, write_only=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=True, write_only=True)

    class Meta:
        model = Project
        fields = "__all__"
        ref_name = "Project"

    def validate(self, data):
        if self.instance and data.get("cost", None):
            total_activity_cost = self.instance.activities.all().values_list("cost", flat=True)

            if sum(total_activity_cost) > data.get("cost"):
                raise serializers.ValidationError("Total cost of activities cannot be greater than project cost")

        return super().validate(data)


class ProjectResultSerializer(serializers.Serializer):
    # TODO: This can probably be removed and the fields moved to ProjectSerializer as read_only
    activities = serializers.SerializerMethodField()
    results = ResultSerializer(many=False)


class ActivitySerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255, read_only=True)
    project = ReadProjectSerializer(many=False, read_only=True)
    user = UserReadSerializer(many=False, read_only=True)
    change_rate = get_model_serializer(ChangeRate)(many=False, read_only=True)
    status = get_model_serializer(StatusType)(many=False, read_only=True)
    climate_t2 = get_model_serializer(Climate)(read_only=True)
    moisture_t2 = get_model_serializer(Moisture)(read_only=True)
    soil_type_t2 = get_model_serializer(SoilType)(read_only=True)
    module_types = get_model_serializer(ModuleType)(many=True, read_only=True)
    modules = serializers.JSONField(read_only=True)
    owner = UserReadSerializer(many=False, read_only=True)

    class Meta:
        model = Activity
        fields = "__all__"
        ref_name = "Activity"


class WriteActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = "__all__"
        ref_name = "Activity"

    def validate(self, data):
        if self.instance:
            luc_module: ModuleType = ModuleType.objects.filter(name="Land Use Change").first()

            if luc_module and luc_module in data.get("module_types", []):
                raise serializers.ValidationError("Land Use Change module cannot be added manually")

            if self.instance.landusechange.exists() and len(list(filter(lambda module: module.is_luc, data.get("module_types", [])))) > 0:
                raise serializers.ValidationError("Land Modules cannot be independently added to activities with a Land Use Change")

            new_duration = data.get("duration_t2", None)
            if new_duration and new_duration > (self.instance.project.implementation_years + self.instance.project.capitalization_years):
                raise serializers.ValidationError("Activity duration cannot be greater than project duration")

        activity_cost = data.get("cost", None)

        if activity_cost:

            project = getattr(self.instance, "project", data.get("project"))
            project_cost = project.cost

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
    climate = serializers.PrimaryKeyRelatedField(queryset=Climate.objects.all(), required=True)
    moisture = serializers.PrimaryKeyRelatedField(queryset=Moisture.objects.all(), required=True)
    soil_type = serializers.PrimaryKeyRelatedField(queryset=SoilType.objects.all(), required=True)
    duration = serializers.IntegerField(required=True)
    start_year = serializers.IntegerField(required=False)
    land_use_change = LandUseChangeBuilderSerializer(many=False, required=False, allow_null=True)
    module_types = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), many=True, required=False)
    area = serializers.FloatField(required=False, min_value=0)
    module_types = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), many=True, required=False)
    change_rate = serializers.PrimaryKeyRelatedField(queryset=ChangeRate.objects.all(), many=False, required=False)

    def validate(self, data):
        luc_module = ModuleType.objects.get(name="Land Use Change")
        module_types = data.get("module_types", [])
        land_use_change = data.get("land_use_change", None)
        area = data.get("area", None)

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

        default_change_rate = ChangeRate.objects.get(name="D")

        return Activity.objects.create(
            name=self.validated_data["name"],
            project=self.validated_data["project"],
            cost=self.validated_data["cost"],
            change_rate=self.validated_data.get("change_rate", default_change_rate),
            climate_t2=self.validated_data.get("climate"),
            moisture_t2=self.validated_data.get("moisture"),
            duration_t2=self.validated_data.get("duration"),
            soil_type_t2=self.validated_data.get("soil_type"),
            start_year_t2=self.validated_data.get("start_year"),
            owner=self.context["request"].user,
        )

    def handle_luc_module(self, activity, has_organic_soil):
        luc = LandUseChange.objects.create(
            **self.validated_data["land_use_change"],
            activity=activity,
            area=self.validated_data["area"],
        )
        activity.module_types.add(
            luc.module_type_start.id,
            luc.module_type_w.id,
            luc.module_type_wo.id,
            ModuleType.objects.get(name="Land Use Change").id,
        )
        luc.status = StatusType.objects.get(name="READY")

        if has_organic_soil:
            organic_soil = OrganicSoil.objects.create(activity=activity, area=self.validated_data.get("area"))
            organic_soil.land_use_change = luc
            organic_soil.save()
            activity.module_types.add(ModuleType.objects.get(name="Organic Soil").id)
            luc.organic_soil = organic_soil

        luc.save()
        return luc

    def create_modules(self, activity, luc, has_organic_soil, has_luc_module):
        for module_type in activity.module_types.all():
            if module_type.class_name in ["LandUseChange", "OrganicSoil"]:
                continue

            ModuleClass = apps.get_model("api", module_type.class_name)
            if module_type.is_luc:
                module_instance = ModuleClass.objects.create(activity=activity, land_use_change=luc, area=self.validated_data.get("area"))
                if has_organic_soil and not has_luc_module:
                    organic_soil = OrganicSoil.objects.create(activity=activity, area=self.validated_data.get("area"))
                    activity.module_types.add(ModuleType.objects.get(name="Organic Soil").id)
                    module_instance.organic_soil = organic_soil
            else:
                filters = {"activity": activity}
                if module_type.name in ["Coastal Wetland", "Waterbody"]:
                    filters["area"] = self.validated_data.get("area")
                module_instance = ModuleClass.objects.create(**filters)

            utils.create_comment_threads(module_instance)

            module_instance.save()
            update_change_reason(module_instance, "update")

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

    @transaction.atomic
    def save(self, **kwargs):
        self.validate_total_project_cost()

        if Activity.objects.filter(name=self.validated_data["name"], project=self.validated_data["project"]).exists():
            self.validated_data["name"] = self.unique_activity_name()

        has_organic_soil = "OrganicSoil" in [module.class_name for module in self.validated_data["module_types"]]
        has_luc_module = self.validated_data.get("land_use_change", False)

        activity = self.create_activity()
        activity.module_types.set(self.validated_data.get("module_types", []))

        luc = None
        if has_luc_module:
            luc = self.handle_luc_module(activity, has_organic_soil)

        self.create_modules(activity, luc, has_organic_soil, has_luc_module)
        activity.save()

        return activity


class RecursiveField(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


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


class BaseGenericModuleSerializer(serializers.ModelSerializer):
    module_type = get_model_serializer(ModuleType)(many=False, read_only=True)
    status = get_model_serializer(StatusType)(many=False, read_only=True)

    class Meta:
        extra_fields = ["module_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self.Meta, "ref_name") or not hasattr(self.Meta, "mandatory_fields"):
            raise ValueError(f"Meta class of {self.__class__.__name__} must have a ref_name and a mandatory_fields attribute")
        self.fields["module_type"].default = ModuleType.objects.get(class_name=self.Meta.ref_name)

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
        if field_name.endswith("_start"):
            return "start"
        elif field_name.endswith("_w"):
            return "w"
        elif field_name.endswith("_wo"):
            return "wo"
        return None

    @abstractmethod
    def is_ready(self, data, mandatory_fields, instance=None):
        raise NotImplementedError("is_ready method must be implemented")


class BaseModuleSerializer(BaseGenericModuleSerializer):

    def validate(self, data):
        log.debug(f"START ModuleBaseSerializer[{self.Meta.ref_name}].validate")

        if data.get("parent", None):
            activity = data["parent"].activity

        else:
            activity = data["activity"] if "activity" in data else self.instance.activity

        module_types = list(map(lambda module: module.class_name, activity.module_types.all()))
        if getattr(activity, self.Meta.ref_name.lower(), None).exists() and not self.instance:
            log.error(f"Activity already has a {self.Meta.ref_name}")
            raise serializers.ValidationError("A module of this type is already present for this activity")

        if self.Meta.ref_name not in module_types and self.Meta.ref_name != "LandUseChange":
            log.error(f"Module type {self.Meta.ref_name} is not present for this activity")
            raise serializers.ValidationError("This module type is not present for this activity")

        is_ready, errors = self.is_ready(data, self.Meta.mandatory_fields, instance=self.instance)

        if not is_ready:
            log.debug(f"Module {self.Meta.ref_name} is not ready for calculations")
            data["status"] = StatusType.objects.get(name="EMPTY")
            return super().validate(data)

        data["status"] = StatusType.objects.get(name="READY")

        log.debug(f"END ModuleBaseSerializer[{self.Meta.ref_name}].validate")
        return super().validate(data)

    def save(self, **kwargs):
        if self.instance:
            self.instance.activity.project.lock_updated_at = timezone.now()
            self.instance.activity.project.save()
        else:
            self.validated_data["activity"].project.lock_updated_at = timezone.now()
            self.validated_data["activity"].project.save()
        return super().save(**kwargs)


class SubmoduleBaseSerializer(BaseGenericModuleSerializer):

    def validate(self, data):
        log.debug(f"START SubmoduleBaseSerializer[{self.Meta.ref_name}].validate")

        if not data.get("parent", None) and (not self.instance or not self.instance.parent):
            log.error(f"Parent field is required for {self.Meta.ref_name}")
            raise serializers.ValidationError("Parent field is required")

        is_ready, errors = self.is_ready(data, self.Meta.mandatory_fields, instance=self.instance)

        if not is_ready:
            log.debug(f"Module {self.Meta.ref_name} is not ready for calculations")
            data["status"] = StatusType.objects.get(name="EMPTY")
            return super().validate(data)

        data["status"] = StatusType.objects.get(name="READY")

        log.debug(f"END SubmoduleBaseSerializer[{self.Meta.ref_name}].validate")
        return super().validate(data)


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
                missing_mandatory_fields = [field for field in mandatory_fields if not combined_data.get(field)]
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
                missing_mandatory_fields = [field for field in mandatory_fields if not combined_data.get(field)]
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


class NoScenarioModuleSerializer(BaseModuleSerializer, NoScenarioBaseSerializer):
    pass


class ScenarioModuleSerializer(BaseModuleSerializer, ScenarioBaseSerializer):
    pass


class NoScenarioSubmoduleSerializer(SubmoduleBaseSerializer, NoScenarioBaseSerializer):
    pass


class ScenarioSubmoduleSerializer(SubmoduleBaseSerializer, ScenarioBaseSerializer):
    pass


class AllModulesBaseSerializer(serializers.ModelSerializer):
    class Meta:
        mandatory_fields = {}
        extra_fields = []
        scenarios = {}

    def merge_instance_data(self, data: dict) -> dict:
        """
        Merges the instance data with the new data and returns the merged data.

        Args:
            data (dict): The new data to be merged with the instance data.

        Returns:
            dict: The merged data.

        """

        if not self.instance:
            return data

        self.instance: Model

        # Get instance attributes
        instance_fields = self.instance._meta.get_fields()
        # Exclude the fields that are not editable
        instance_fields = [field for field in instance_fields if field.editable]

        # Merge the instance data with the new data
        data.update({key: getattr(self.instance, key) for key in [field.name for field in instance_fields if field.name not in data]})

        # # If the keys in data have a counterpart in the instance with an _id suffix,
        # # add the value from the data.id to the data as a new key with the _id suffix
        # for key, value in list(data.items()):
        #     if key + "_id" in self.instance.__dict__:
        #         data[key + "_id"] = getattr(value, "id", value)

        return data

    def merge_instance_data_2(self, data: dict, instance=None) -> dict:
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

    def is_ready_for_calculations(self, data, mandatory_fields: dict, first=True):
        """
        Checks if the given data is ready based on the provided mandatory fields.

        Args:
            data (dict): The data to be validated.
            mandatory_fields (dict): A dictionary specifying the mandatory fields and their validation rules.
            first (bool, optional): Indicates if this is the first call to the function. Defaults to True.

        Returns:
            bool: True if the data is ready for calculations, False otherwise.
        """

        if first and not isinstance(mandatory_fields, (dict)):
            raise ValueError(f"Entry point must be a dictionary, got {type(mandatory_fields)}")

        if isinstance(mandatory_fields, list):
            for field in mandatory_fields:
                if data.get(field) in (None, False):
                    return False

        if isinstance(mandatory_fields, dict):

            # If mandatory_fields is empty, return True
            if first and mandatory_fields == {}:
                return True

            # If this is the first call and no mandatory fields are present, return False
            if not any(data.get(f) for f in mandatory_fields.keys()) and first:
                return False

            for field, items in mandatory_fields.items():

                # If the main field is None or False, skip validation for this field
                if data.get(field) in (None, False):
                    continue

                # If items is a list, iterate over its elements
                if isinstance(items, list):
                    for sub_field in items:
                        if isinstance(sub_field, list):
                            # If sub_field is a list of dictionaries, validate all of them
                            if all(isinstance(f, dict) for f in sub_field):

                                # If none of the main fields were provided, return False
                                main_fields = [list(f.keys())[0] for f in sub_field]
                                if not any(data.get(f) for f in main_fields):
                                    return False

                                # Only validate the main fields that were provided and recursively validate nested data
                                available_main_fields = [f for f in sub_field if data.get(list(f.keys())[0])]
                                for main_field in available_main_fields:
                                    for f, v in main_field.items():
                                        if data.get(f) is None or not self.is_ready_for_calculations(data, v, first=False):
                                            return False

                            # If sub_field is a list of strings, validate all of them
                            elif all(isinstance(f, str) for f in sub_field):
                                if not any(data.get(f) for f in sub_field):
                                    return False

                        # If sub_field is a dictionary, validate nested data recursively
                        elif isinstance(sub_field, dict):
                            if not self.is_ready_for_calculations(data, sub_field, first=False):
                                return False

                        # If sub_field is a string, validate the field
                        elif data.get(sub_field) in (None, False):
                            return False

                # If items is a dictionary, recursively validate nested data
                elif isinstance(items, dict):
                    if not self.is_ready_for_calculations(data, items, first=False):
                        return False

        return True

    def get_scenario(self, field_name: str):
        if field_name.endswith("_start"):
            return "start"
        elif field_name.endswith("_w"):
            return "w"
        elif field_name.endswith("_wo"):
            return "wo"
        return None

    def is_ready_for_calculations_2(self, data, scenarios, instance=None):
        combined_data = self.merge_instance_data_2(data, instance=instance)

        model_instance = self.Meta.model(**combined_data)
        errors = {}

        for scenario, config in scenarios.items():
            scenario_check_method = f"is_{scenario}"
            if hasattr(model_instance, scenario_check_method) and getattr(model_instance, scenario_check_method)():
                # Validate mandatory fields
                mandatory_fields = config.get("mandatory", [])
                missing_mandatory_fields = [field for field in mandatory_fields if not combined_data.get(field)]
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

        return not errors


class ModuleBaseSerializer(AllModulesBaseSerializer):
    module_type = get_model_serializer(ModuleType)(many=False, read_only=True)
    status = get_model_serializer(StatusType)(many=False, read_only=True)

    class Meta:
        extra_fields = ["module_type"]
        mandatory_fields = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["module_type"].default = ModuleType.objects.get(class_name=self.Meta.ref_name)

    def is_ready(self, data, mandatory_fields, instance=None):
        combined_data = {**{field.name: getattr(instance, field.name) for field in instance._meta.fields}, **data} if instance else data.copy()

        errors = []

        # Validate mandatory fields
        mandatory_fields = mandatory_fields.get("mandatory", [])
        missing_mandatory_fields = [field for field in mandatory_fields if not combined_data.get(field)]
        if missing_mandatory_fields:
            errors.append(f"Missing mandatory fields: {', '.join(missing_mandatory_fields)}")

        # Validate conditional fields
        conditional_fields = mandatory_fields.get("conditional", {})
        for field, dependent_fields in conditional_fields.items():
            if combined_data.get(field):
                missing_dependent_fields = [dep_field for dep_field in dependent_fields if not combined_data.get(dep_field)]
                if missing_dependent_fields:
                    errors.append(f"Since '{field}' is filled, the following fields are also mandatory: {', '.join(missing_dependent_fields)}")

        return not errors, errors

    def validate(self, data):
        log.debug(f"START ModuleBaseSerializer[{self.Meta.ref_name}].validate")

        activity = data["activity"] if "activity" in data else self.instance.activity
        module_types = list(map(lambda module: module.class_name, activity.module_types.all()))

        if getattr(activity, self.Meta.ref_name.lower(), None).exists() and not self.instance:
            log.error(f"Activity already has a {self.Meta.ref_name}")
            raise serializers.ValidationError("A module of this type is already present for this activity")

        if self.Meta.ref_name not in module_types and self.Meta.ref_name != "LandUseChange":
            log.error(f"Module type {self.Meta.ref_name} is not present for this activity")
            raise serializers.ValidationError("This module type is not present for this activity")

        if not self.is_ready(data, self.Meta.mandatory_fields, instance=self.instance):
            log.debug(f"Module {self.Meta.ref_name} is not ready for calculations")
            data["status"] = StatusType.objects.get(name="EMPTY")
            return super().validate(data)

        data["status"] = StatusType.objects.get(name="READY")

        log.debug(f"END ModuleBaseSerializer[{self.Meta.ref_name}].validate")
        return super().validate(data)

    def save(self, **kwargs):
        if self.instance:
            self.instance.activity.project.lock_updated_at = timezone.now()
            self.instance.activity.project.save()
        else:
            self.validated_data["activity"].project.lock_updated_at = timezone.now()
            self.validated_data["activity"].project.save()
        return super().save(**kwargs)


class LandModuleWriteSerializer(ScenarioModuleSerializer):
    class Meta:
        model = None
        fields = "__all__"
        ref_name = None
        mandatory_fields = {}

    def validate(self, data):
        log.debug(f"START LandModuleSerializer[{self.Meta.ref_name}].validate")
        log.debug(f"Data: {data}")

        activity = data["activity"] if "activity" in data else self.instance.activity
        luc = activity.landusechange.first()
        module_types = list(map(lambda module: module.class_name, activity.module_types.all()))

        if luc:
            module_type = ModuleType.objects.get(class_name=self.Meta.ref_name)
            luc_module_types = [
                luc.module_type_start.class_name,
                luc.module_type_w.class_name,
                luc.module_type_wo.class_name,
            ]

            # NOTE: Redundant as it's already checked in ActivityBuilderSerializer, but just in case
            if module_type.is_luc and module_type.class_name not in luc_module_types:
                log.error(f"Cannot add {module_type.class_name} to an activity with a Land Use Change")
                raise serializers.ValidationError("Cannot add this module to an activity with a Land Use Change")

            module_types += luc_module_types

        is_ready, errors = self.is_ready(data, self.Meta.mandatory_fields, instance=self.instance)

        if not is_ready:
            log.debug(f"Module {self.Meta.ref_name} is not ready for calculations")
            data["status"] = StatusType.objects.get(name="EMPTY")
            return super().validate(data)

        data["status"] = StatusType.objects.get(name="READY")

        log.debug(f"END LandModuleSerializer[{self.Meta.ref_name}].validate")
        return super().validate(data)


class LandModuleReadSerializer(ScenarioModuleSerializer):
    activity = ActivitySerializer(many=False, read_only=True)
    land_use_change = get_model_serializer(LandUseChange)(many=False, read_only=True, required=False)
    status = get_model_serializer(StatusType)(many=False, read_only=True)

    def validate(self, data):
        data = {}
        return super().validate(data)


# Grassland


class GrasslandWriteSerializer(LandModuleWriteSerializer):
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


class GrasslandReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = Grassland
        fields = "__all__"
        ref_name = "Grassland"
        mandatory_fields = {}


# Annual Cropping


class MinorSeasonAnnualCroppingWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = MinorSeasonAnnualCropping
        fields = "__all__"
        ref_name = "MinorSeasonAnnualCropping"

        mandatory_fields = {
            "start": {
                "mandatory": [
                    "land_use_type_start",
                    # "tillage_management_type_start",
                    # "organic_input_type_start",
                    "residue_management_type_start",
                ],
            },
            "with": {
                "mandatory": [
                    "land_use_type_w",
                    # "tillage_management_type_w",
                    # "organic_input_type_w",
                    "residue_management_type_w",
                ],
            },
            "without": {
                "mandatory": [
                    "land_use_type_wo",
                    # "tillage_management_type_wo",
                    # "organic_input_type_wo",
                    "residue_management_type_wo",
                ],
            },
        }


class MinorSeasonAnnualCroppingReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = MinorSeasonAnnualCropping
        fields = "__all__"
        ref_name = "MinorSeasonAnnualCropping"
        mandatory_fields = {}


class AnnualCroppingWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = AnnualCropping
        fields = "__all__"
        ref_name = "AnnualCropping"
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
        super().validate(data)

        for minor_season in self.instance.minor_seasons.all():
            minor_season: MinorSeasonAnnualCropping
            if not minor_season.is_ready():
                data["status"] = StatusType.objects.get(name="SUBMODULES_EMPTY")

        return data


class AnnualCroppingReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = AnnualCropping
        fields = "__all__"
        ref_name = "AnnualCropping"
        mandatory_fields = {}

    def validate(self, data):
        for minor_season in self.instance.minor_seasons.all():
            minor_season: MinorSeasonAnnualCropping
            if not minor_season.is_ready():
                data["status"] = StatusType.objects.get(name="SUBMODULES_EMPTY")
                return data
        return super().validate(data)


# Perennial Cropping


class MinorSeasonPerennialCroppingWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = MinorSeasonPerennialCropping
        fields = "__all__"
        ref_name = "MinorSeasonPerennialCropping"
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


class MinorSeasonPerennialCroppingReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = MinorSeasonPerennialCropping
        fields = "__all__"
        ref_name = "MinorSeasonPerennialCropping"
        mandatory_fields = {}


class PerennialCroppingWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = PerennialCropping
        fields = "__all__"
        ref_name = "PerennialCropping"
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


class PerennialCroppingReadSerializer(LandModuleReadSerializer):
    minor_seasons = MinorSeasonPerennialCroppingReadSerializer(many=True, read_only=True)

    class Meta:
        model = PerennialCropping
        fields = "__all__"
        ref_name = "PerennialCropping"
        extra_fields = ["minor_seasons"]
        mandatory_fields = {}


# Land Use Change


class LandUseChangeWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = LandUseChange
        fields = "__all__"
        ref_name = "LandUseChange"
        mandatory_fields = {}


class LandUseChangeReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = LandUseChange
        fields = "__all__"
        ref_name = "LandUseChange"
        mandatory_fields = {}


# Organic Soil


class OrganicSoilWriteSerializer(LandModuleWriteSerializer):
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
            missing_mandatory_fields = [field for field in mandatory_fields if not combined_data.get(field)]
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


class OrganicSoilReadSerializer(LandModuleReadSerializer):

    parent_land_use_type_start = serializers.IntegerField(read_only=True)
    parent_land_use_type_w = serializers.IntegerField(read_only=True)
    parent_land_use_type_wo = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrganicSoil
        fields = "__all__"
        ref_name = "OrganicSoil"
        mandatory_fields = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance:
            return

        self.instance: OrganicSoil

        luc = self.instance.land_use_change

        if luc:
            self.parent_land_use_type_start = luc.module_type_start.id if luc.module_type_start else None
            self.parent_land_use_type_w = luc.module_type_w.id if luc.module_type_w else None
            self.parent_land_use_type_wo = luc.module_type_wo.id if luc.module_type_wo else None
        else:
            _, parent_module_type = utils.find_organic_soil_parent_module(self.instance)
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
        mandatory_fields = {}


class FloodedRiceWriteSerializer(LandModuleWriteSerializer):
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
            if minor_seasons.count() > 4:
                raise serializers.ValidationError(f"Minor seasons cannot be more than 4")

            # for season in minor_seasons:
            #     cultivation_days += season.get("cultivation_days", 0)

        if cultivation_days > 365:
            raise serializers.ValidationError(f"Cultivation days cannot be greater than 365 (one year)")

        return super().validate(data)


class FloodedRiceReadSerializer(LandModuleReadSerializer):
    minor_seasons = MinorSeasonFloodedRiceReadSerializer(many=True, read_only=True)

    class Meta:
        model = FloodedRice
        fields = "__all__"
        ref_name = "FloodedRice"
        extra_fields = ["minor_seasons"]
        mandatory_fields = {}


# Building
class BuildingWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = Building
        fields = "__all__"
        ref_name = "Building"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "building_type_start",
                    "area_m2_start",
                ],
            },
            "with": {
                "mandatory": [
                    "building_type_w",
                    "area_m2_w",
                ],
            },
            "without": {
                "mandatory": [
                    "building_type_wo",
                    "area_m2_wo",
                ],
            },
        }

    def validate(self, data):

        return super().validate(data)


class BuildingReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Building
        fields = "__all__"
        ref_name = "Building"
        mandatory_fields = {}


# Road


class RoadWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = Road
        fields = "__all__"
        ref_name = "Road"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "road_type_start",
                    "length_km_start",
                    "width_m_start",
                ],
            },
            "with": {
                "mandatory": [
                    "road_type_w",
                    "length_km_w",
                    "width_m_w",
                ],
            },
            "without": {
                "mandatory": [
                    "road_type_wo",
                    "length_km_wo",
                    "width_m_wo",
                ],
            },
        }

    def validate(self, data):
        mandatory_fields = []

        road_type_scenarios = get_filled_scenarios(data, ["road_type"])

        for scenario in road_type_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")
        elif mandatory_fields:
            data["status"] = StatusType.objects.get(name="READY")

        return super().validate(data)


class RoadReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Road
        fields = "__all__"
        ref_name = "Road"
        mandatory_fields = {}


# Other


class OtherInfrastructureWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = OtherInfrastructure
        fields = "__all__"
        ref_name = "Other"
        mandatory_fields = {
            "start": {
                "mandatory": ["area_m2_start"],
            },
            "with": {
                "mandatory": ["area_m2_w"],
            },
            "without": {
                "mandatory": ["area_m2_wo"],
            },
        }


class OtherInfrastructureReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = OtherInfrastructure
        fields = "__all__"
        ref_name = "Other"
        mandatory_fields = {}


class IrrigationWriteSerializer(BaseModuleSerializer):
    class Meta:
        model = Irrigation
        fields = "__all__"
        ref_name = "Irrigation"
        mandatory_fields = {}


class IrrigationReadSerializer(BaseModuleSerializer):
    class Meta:
        model = Irrigation
        fields = "__all__"
        ref_name = "Irrigation"
        mandatory_fields = {}

    def validate(self, data):

        irrigation_systems = self.instance.irrigation_systems.all()
        irrigation_phases = self.instance.irrigation_phases.all()

        if any([system.status.name == "EMPTY" for system in irrigation_systems]):
            raise serializers.ValidationError("Irrigation systems are not ready for calculations")

        if any([phase.status.name == "EMPTY" for phase in irrigation_phases]):
            raise serializers.ValidationError("Irrigation phases are not ready for calculations")

        return super().validate(data)


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
                    "irrigation_system_type",
                    "fuel_type",
                    "well_depth",
                    "ha_start",
                ],
            },
            "with": {
                "mandatory": [
                    "irrigation_system_type",
                    "fuel_type",
                    "well_depth",
                    "ha_w",
                ],
            },
            "without": {
                "mandatory": [
                    "irrigation_system_type",
                    "fuel_type",
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


class EnergyWriteSerializer(ScenarioModuleSerializer):
    class Meta:
        model = Energy
        fields = "__all__"
        ref_name = "Energy"
        mandatory_fields = {}


class EnergyReadSerializer(ScenarioModuleSerializer):
    class Meta:
        model = Energy
        fields = "__all__"
        ref_name = "Energy"
        mandatory_fields = {}

    def validate(self, data):
        super().validate(data)

        electricities = self.instance.electricities.all()
        fuels = self.instance.fuels.all()

        if any([electricity.status.name == "EMPTY" for electricity in electricities]):
            raise serializers.ValidationError("Electricity modules are not ready for calculations")

        if any([fuel.status.name == "EMPTY" for fuel in fuels]):
            raise serializers.ValidationError("Fuel modules are not ready for calculations")

        return data


# Fuel


class FuelWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = Fuel
        fields = "__all__"
        ref_name = "Fuel"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "fuel_type",
                    "fuel_consumption_start",
                ],
            },
            "with": {
                "mandatory": [
                    "fuel_type",
                    "fuel_consumption_w",
                ],
            },
            "without": {
                "mandatory": [
                    "fuel_type",
                    "fuel_consumption_wo",
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


class FuelReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = Fuel
        fields = "__all__"
        ref_name = "Fuel"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "fuel_type",
                    "fuel_consumption_start",
                ],
            },
            "with": {
                "mandatory": [
                    "fuel_type",
                    "fuel_consumption_w",
                ],
            },
            "without": {
                "mandatory": [
                    "fuel_type",
                    "fuel_consumption_wo",
                ],
            },
        }


class ElectricityWriteSerializer(NoScenarioSubmoduleSerializer):
    class Meta:
        model = Electricity
        fields = "__all__"
        ref_name = "Electricity"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "mwh_start",
                    "transmission_loss_start",
                ],
            },
            "with": {
                "mandatory": [
                    "mwh_w",
                    "transmission_loss_w",
                ],
            },
            "without": {
                "mandatory": [
                    "mwh_wo",
                    "transmission_loss_wo",
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


class ElectricityReadSerializer(NoScenarioSubmoduleSerializer):
    class Meta:
        model = Electricity
        fields = "__all__"
        ref_name = "Electricity"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "mwh_start",
                    "transmission_loss_start",
                ],
            },
            "with": {
                "mandatory": [
                    "mwh_w",
                    "transmission_loss_w",
                ],
            },
            "without": {
                "mandatory": [
                    "mwh_wo",
                    "transmission_loss_wo",
                ],
            },
        }


# Livestock


class LivestockWriteSerializer(LandModuleWriteSerializer):
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
                    "complementary_manure_management_type_start": [
                        "percentage_heads_on_pasture_start",
                    ],
                },
            },
            "with": {
                "mandatory": [
                    "livestock_category_type",
                    "livestock_production_type_w",
                    "heads_number_w",
                ],
                "conditional": {
                    "complementary_manure_management_type_w": [
                        "percentage_heads_on_pasture_w",
                    ],
                },
            },
            "without": {
                "mandatory": [
                    "livestock_category_type",
                    "livestock_production_type_wo",
                    "heads_number_wo",
                ],
                "conditional": {
                    "complementary_manure_management_type_wo": [
                        "percentage_heads_on_pasture_wo",
                    ],
                },
            },
        }


class LivestockReadSerializer(LandModuleReadSerializer):
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
                    "complementary_manure_management_type_start": [
                        "percentage_heads_on_pasture_start",
                    ],
                },
            },
            "with": {
                "mandatory": [
                    "livestock_category_type",
                    "livestock_production_type_w",
                    "heads_number_w",
                ],
                "conditional": {
                    "complementary_manure_management_type_w": [
                        "percentage_heads_on_pasture_w",
                    ],
                },
            },
            "without": {
                "mandatory": [
                    "livestock_category_type",
                    "livestock_production_type_wo",
                    "heads_number_wo",
                ],
                "conditional": {
                    "complementary_manure_management_type_wo": [
                        "percentage_heads_on_pasture_wo",
                    ],
                },
            },
        }


# Aquaculture


class AquacultureWriteSerializer(LandModuleWriteSerializer):
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


class AquacultureReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = Aquaculture
        fields = "__all__"
        ref_name = "Aquaculture"
        mandatory_fields = {}


# SmllFishery


class SmallFisheryWriteSerializer(LandModuleWriteSerializer):
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


class SmallFisheryReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = SmallFishery
        fields = "__all__"
        ref_name = "SmallFishery"
        mandatory_fields = {}


# LargeFishery


class LargeFisheryWriteSerializer(LandModuleWriteSerializer):
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


class LargeFisheryReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = LargeFishery
        fields = "__all__"
        ref_name = "LargeFishery"
        mandatory_fields = {}


# Waterbody


class WaterbodyWriteSerializer(LandModuleWriteSerializer):
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


class WaterbodyReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = Waterbody
        fields = "__all__"
        ref_name = "Waterbody"
        mandatory_fields = {}


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

    class Meta:
        model = ProjectInvitation
        fields = "__all__"
        ref_name = "ProjectInvitation"


class ForestManagementWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = ForestManagement
        fields = "__all__"
        ref_name = "ForestManagement"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "land_use_type_start",
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
                    "land_use_type_w",
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
                    "land_use_type_wo",
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
        errors = []

        instance: ForestManagement = self.instance

        # Logging mandatory fields
        loggings = get_filled_scenarios(data, ["logging_recurrence_yrs"])
        rotations = get_filled_scenarios(data, ["rotation_length_yrs"])
        disturbances = self.instance.disturbances.all().count() if self.instance else None

        if rotations and (loggings or disturbances):
            errors += ["Forest rotation cannot be used with logging or other disturbances at the same time"]

        if loggings and disturbances:
            errors += ["Cannot have logging and other disturbances at the same time"]

        if not loggings and not rotations:
            degradations = get_filled_scenarios(data, ["average_yearly_degradation_percentage"])
            if not degradations:
                errors += ["With no logging, rotation or disturbances, average yearly degradation percentage is required"]

        if instance and instance.disturbances.count() > 0:
            pc_biomass_destruction_start = data.get("logging_percentage_agb_logged_start", 0)
            pc_biomass_destruction_wo = data.get("logging_percentage_agb_logged_wo", 0)
            pc_biomass_destruction_w = data.get("logging_percentage_agb_logged_w", 0)

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

        return super().validate(data)


class ForestManagementReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = ForestManagement
        fields = "__all__"
        ref_name = "ForestManagement"
        mandatory_fields = {}


class InputWriteSerializer(BaseModuleSerializer):
    class Meta:
        model = Input
        fields = "__all__"
        ref_name = "Input"
        mandatory_fields = {}


class InputReadSerializer(BaseModuleSerializer):
    class Meta:
        model = Input
        fields = "__all__"
        ref_name = "Input"
        mandatory_fields = {}


class InputEntryWriteSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = InputEntry
        fields = "__all__"
        ref_name = "InputEntry"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "input_type_start",
                    "value_start",
                ],
            },
            "with": {
                "mandatory": [
                    "input_type_w",
                    "value_w",
                ],
            },
            "without": {
                "mandatory": [
                    "input_type_wo",
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


class InputEntryReadSerializer(BaseGenericModuleSerializer):
    module_type = serializers.SerializerMethodField()

    def get_module_type(self, obj):
        return get_model_serializer(ModuleType)(ModuleType.objects.get(class_name=obj.__class__.__name__), many=False).data

    class Meta:
        model = InputEntry
        fields = "__all__"
        ref_name = "InputEntry"
        extra_fields = ["module_type"]


class DynamicResultSerializer(serializers.Serializer):
    total_w = serializers.SerializerMethodField()
    total_wo = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

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


class UserProjectGroupSerializer(serializers.ModelSerializer):
    user = UserReadSerializer(many=False, read_only=True)
    group = GroupSerializer(many=False, read_only=True)

    class Meta:
        model = UserProjectGroup
        fields = "__all__"
        ref_name = "UserProjectGroup"


class SetAsideWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = SetAside
        fields = "__all__"
        ref_name = "SetAside"
        mandatory_fields = {}


class SetAsideReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = SetAside
        fields = "__all__"
        ref_name = "SetAside"
        mandatory_fields = {}


class DegradedLandWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = DegradedLand
        fields = "__all__"
        ref_name = "DegradedLand"
        mandatory_fields = {}


class DegradedLandReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = DegradedLand
        fields = "__all__"
        ref_name = "DegradedLand"
        mandatory_fields = {}


class SettlementWriteSerializer(LandModuleWriteSerializer):
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

        buildings = Building.objects.filter(parent=self.instance).all()

        if any(building.status.name == "EMPTY" for building in buildings):
            raise serializers.ValidationError("At least one building is not ready for calculations")

        for building in buildings:
            building_serializer = BuildingReadSerializer(data=building.__dict__, instance=building)
            if not building_serializer.is_valid():
                raise serializers.ValidationError(building_serializer.errors)

        roads = Road.objects.filter(parent=self.instance).all()

        if any(road.status.name == "EMPTY" for road in roads):
            raise serializers.ValidationError("At least one road is not ready for calculations")

        for road in roads:
            road_serializer = RoadReadSerializer(data=road.__dict__, instance=road)
            if not road_serializer.is_valid():
                raise serializers.ValidationError(road_serializer.errors)

        other_infrastructures = OtherInfrastructure.objects.filter(parent=self.instance).all()

        if any(other_infrastructure.status.name == "EMPTY" for other_infrastructure in other_infrastructures):
            raise serializers.ValidationError("At least one other infrastructure is not ready for calculations")

        for other_infrastructure in other_infrastructures:
            other_infrastructure_serializer = OtherInfrastructureReadSerializer(data=other_infrastructure.__dict__, instance=other_infrastructure)
            if not other_infrastructure_serializer.is_valid():
                raise serializers.ValidationError(other_infrastructure_serializer.errors)

        return super().validate(data)


class SettlementReadSerializer(LandModuleReadSerializer):
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


class FuelTypeSerializer(serializers.ModelSerializer):
    macro_fuel_type = MacroFuelTypeSerializer(many=False, read_only=True)

    class Meta:
        model = FuelType
        fields = "__all__"
        ref_name = "FuelType"


class CoastalWetlandWriteSerializer(NoScenarioModuleSerializer):
    class Meta:
        model = CoastalWetland
        fields = "__all__"
        ref_name = "CoastalWetland"
        mandatory_fields = {
            "mandatory": ["land_use_type_start", "area"],
        }


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
        return super().validate(data)


class ForestDisturbanceReadSerializer(BaseGenericModuleSerializer):
    class Meta:
        model = ForestDisturbance
        fields = "__all__"
        ref_name = "ForestDisturbance"
        mandatory_fields = {}


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


class ProjectInvitationWriteSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=True)
