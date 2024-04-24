import logging
from enum import Enum

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import Model
from django.utils import timezone
from ipcc.models import GlobalWarmingPotential
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes
from rest_framework import serializers
from rest_framework.fields import empty

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
        fields = ["id", "username", "email", "first_name", "last_name", "country"]


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
    climate_t2 = get_model_serializer(Climate)(read_only=True)
    soil_type_t2 = get_model_serializer(SoilType)(read_only=True)
    module_types = get_model_serializer(ModuleType)(many=True, read_only=True)

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
    soil_type = serializers.PrimaryKeyRelatedField(queryset=SoilType.objects.all(), required=True)
    duration = serializers.IntegerField(required=True)
    land_use_change = LandUseChangeBuilderSerializer(many=False, required=False, allow_null=True)
    module_types = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), many=True, required=False)
    area = serializers.FloatField(required=False)
    module_types = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), many=True, required=False)

    def validate(self, data):
        luc_module = ModuleType.objects.filter(name="Land Use Change").first()
        module_types = data.get("module_types", [])
        land_use_change = data.get("land_use_change", None)
        area = data.get("area", None)

        if luc_module and luc_module in module_types:
            raise serializers.ValidationError("Land Use Change module cannot be added manually")

        if land_use_change and any(module.is_luc for module in module_types):
            raise serializers.ValidationError("Land Modules cannot be independently added to activities with a Land Use Change")

        if land_use_change and not area or (any(module.is_luc for module in module_types) and not area):
            raise serializers.ValidationError("Area must be provided")

        super().validate(data)

        return data

    @transaction.atomic
    def save(self, **kwargs):
        if Activity.objects.filter(name=self.validated_data["name"], project=self.validated_data["project"]).exists():
            raise serializers.ValidationError("An activity with this name already exists for this project")

        activities_cost = list(self.validated_data["project"].activities.all().values_list("cost", flat=True))
        activities_cost.append(self.validated_data.get("cost", 0))

        if self.validated_data["project"].cost and sum(activities_cost) > self.validated_data["project"].cost:
            raise serializers.ValidationError("Total cost of activities cannot be greater than project cost")

        activity: Activity = Activity.objects.create(
            name=self.validated_data["name"],
            project=self.validated_data["project"],
            climate_t2=self.validated_data["climate"],
            soil_type_t2=self.validated_data["soil_type"],
            duration_t2=self.validated_data["duration"],
            cost=self.validated_data.get("cost"),
        )
        activity.module_types.set(self.validated_data.get("module_types", []))

        luc = None

        if self.validated_data.get("land_use_change", None):
            luc = LandUseChange.objects.create(
                **self.validated_data["land_use_change"],
                activity=activity,
                area=self.validated_data["area"],
            )
            activity.module_types.add(luc.module_type_start.id)
            activity.module_types.add(luc.module_type_w.id)
            activity.module_types.add(luc.module_type_wo.id)
            activity.module_types.add(ModuleType.objects.get(name="Land Use Change").id)
            luc.status = StatusType.objects.get(name="READY")
            luc.save()

        for module_type in activity.module_types.all():
            if module_type.class_name == "LandUseChange":
                continue

            logging.debug(f"Creating module {module_type.class_name}")

            ModuleClass = apps.get_model("api", module_type.class_name)
            module_instance = None

            if module_type.is_luc:
                module_instance = ModuleClass.objects.create(
                    activity=activity,
                    land_use_change=luc,
                    area=self.validated_data.get("area"),
                )
            else:
                module_instance = ModuleClass.objects.create(activity=activity)

            utils.create_module_threads(module_instance)
            module_instance.save()

        activity.save()

        return activity


class InputTypeSerializer(serializers.ModelSerializer):
    macro_input_type = get_model_serializer(MacroInputType)(many=False, read_only=True)

    class Meta:
        model = InputType
        fields = "__all__"
        ref_name = "InputType"


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


class SubmoduleBaseSerializer(serializers.ModelSerializer):
    class Meta:
        mandatory_fields = ["parent"]

    def validate(self, data):
        logging.debug(f"START SubmoduleBaseSerializer[{self.Meta.ref_name}].validate")

        if not data.get("parent", None) and (not self.instance or not self.instance.parent):
            logging.error(f"Parent field is required for {self.Meta.ref_name}")
            raise serializers.ValidationError("Parent field is required")

        logging.debug(f"END SubmoduleBaseSerializer[{self.Meta.ref_name}].validate")
        return super().validate(data)


class ModuleBaseSerializer(serializers.ModelSerializer):
    module_type = get_model_serializer(ModuleType)(many=False, read_only=True)

    class Meta:
        mandatory_fields = []
        extra_fields = ["module_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["module_type"].default = ModuleType.objects.get(class_name=self.Meta.ref_name)

    def validate(self, data):
        logging.debug(f"START ModuleBaseSerializer[{self.Meta.ref_name}].validate")

        activity = data["activity"] if "activity" in data else self.instance.activity
        module_types = list(map(lambda module: module.class_name, activity.module_types.all()))

        if getattr(activity, self.Meta.ref_name.lower(), None).exists() and not self.instance:
            logging.error(f"Activity already has a {self.Meta.ref_name}")
            raise serializers.ValidationError("A module of this type is already present for this activity")

        if self.Meta.ref_name not in module_types and self.Meta.ref_name != "LandUseChange":
            logging.error(f"Module type {self.Meta.ref_name} is not present for this activity")
            raise serializers.ValidationError("This module type is not present for this activity")

        logging.debug(f"END ModuleBaseSerializer[{self.Meta.ref_name}].validate")
        return super().validate(data)

    def save(self, **kwargs):
        if self.instance:
            self.instance.activity.project.lock_updated_at = timezone.now()
            self.instance.activity.project.save()
        else:
            self.validated_data["activity"].project.lock_updated_at = timezone.now()
            self.validated_data["activity"].project.save()
        return super().save(**kwargs)


class LandModuleWriteSerializer(ModuleBaseSerializer):
    def validate(self, data):
        logging.debug(f"START LandModuleSerializer[{self.Meta.ref_name}].validate")
        logging.debug(f"Data: {data}")

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
                logging.error(f"Cannot add {module_type.class_name} to an activity with a Land Use Change")
                raise serializers.ValidationError("Cannot add this module to an activity with a Land Use Change")

            module_types += luc_module_types

        # Checking if the mandatory fields are already filled in the instance or have been provided in the new data
        # And setting the status of the module accordingly

        has_w = False
        has_wo = False
        has_same = False
        has_usual = False

        needs_w = False
        needs_wo = False
        needs_same = False
        needs_usual = False

        if self.instance:

            needs_wo = calcs.is_without(self.instance) and not is_scenario_filled(dict(self.instance.__dict__), "wo", self.Meta.mandatory_fields)
            needs_w = calcs.is_with(self.instance) and not is_scenario_filled(dict(self.instance.__dict__), "w", self.Meta.mandatory_fields)
            needs_same = calcs.is_luc_remaining_same(self.instance) and not is_scenario_filled(dict(self.instance.__dict__), "start", self.Meta.mandatory_fields) and is_scenario_filled(self.instance.__dict__, "w", self.Meta.mandatory_fields)
            needs_usual = calcs.is_business_as_usual(self.instance) and not is_scenario_filled(dict(self.instance.__dict__), "start", self.Meta.mandatory_fields) and is_scenario_filled(self.instance.__dict__, "wo", self.Meta.mandatory_fields)

            has_w = calcs.is_with(self.instance) and is_scenario_filled(dict(self.instance.__dict__), "w", self.Meta.mandatory_fields)
            has_wo = calcs.is_without(self.instance) and is_scenario_filled(dict(self.instance.__dict__), "wo", self.Meta.mandatory_fields)
            has_same = calcs.is_luc_remaining_same(self.instance) and is_scenario_filled(dict(self.instance.__dict__), "start", self.Meta.mandatory_fields) and is_scenario_filled(self.instance.__dict__, "w", self.Meta.mandatory_fields)
            has_usual = calcs.is_business_as_usual(self.instance) and is_scenario_filled(dict(self.instance.__dict__), "start", self.Meta.mandatory_fields) and is_scenario_filled(self.instance.__dict__, "wo", self.Meta.mandatory_fields)

        if needs_w or has_w:
            needs_w = calcs.is_with(data) and not is_scenario_filled(dict(data), "w", self.Meta.mandatory_fields)
        if needs_wo or has_wo:
            needs_wo = calcs.is_without(data) and not is_scenario_filled(dict(data), "wo", self.Meta.mandatory_fields)
        if needs_same or has_same:
            needs_same = calcs.is_luc_remaining_same(data) and not is_scenario_filled(dict(data), "start", self.Meta.mandatory_fields) and is_scenario_filled(data, "w", self.Meta.mandatory_fields)
        if needs_usual or has_usual:
            needs_usual = calcs.is_business_as_usual(data) and not is_scenario_filled(dict(data), "start", self.Meta.mandatory_fields) and is_scenario_filled(data, "wo", self.Meta.mandatory_fields)

        if (needs_w and not has_w) or (needs_wo and not has_wo) or (needs_same and not has_same) or (needs_usual and not has_usual):
            data["status"] = StatusType.objects.get(name="EMPTY")
        else:
            data["status"] = StatusType.objects.get(name="READY")

        logging.debug(f"END LandModuleSerializer[{self.Meta.ref_name}].validate")
        return super().validate(data)


class LandModuleReadSerializer(ModuleBaseSerializer):
    activity = ActivitySerializer(many=False, read_only=True)
    land_use_change = get_model_serializer(LandUseChange)(many=False, read_only=True, required=False)
    status = get_model_serializer(StatusType)(many=False, read_only=True)


# Grassland


class GrasslandWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = Grassland
        fields = "__all__"
        ref_name = "Grassland"

        mandatory_fields = [
            "grassland_management_type",
            "is_fire_used",
        ]

    def validate(self, data):
        mandatory_fields = []

        grassland_mgmt_scenarios = get_filled_scenarios(data, ["grassland_management_type"])
        fire_scenarios = get_filled_scenarios(data, ["is_fire_used"])

        for scenario in grassland_mgmt_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)
            if scenario in fire_scenarios and data.get("is_fire_used", None):
                mandatory_fields += generate_fields_for_scenario(scenario, ["fire_periodicity", "fire_impact"])

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class GrasslandReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = Grassland
        fields = "__all__"
        ref_name = "Grassland"


# Annual Cropping


class MinorSeasonAnnualCroppingWriteSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = MinorSeasonAnnualCropping
        fields = "__all__"
        ref_name = "MinorSeasonAnnualCropping"
        mandatory_fields = [
            "land_use_type",
            "tillage_management_type",
            "organic_input_type",
            "residue_management_type",
        ]

    def validate(self, data):
        mandatory_fields = []

        lut_scenarios = get_filled_scenarios(data, ["land_use_type"])

        for scenario in lut_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class MinorSeasonAnnualCroppingReadSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = MinorSeasonAnnualCropping
        fields = "__all__"
        ref_name = "MinorSeasonAnnualCropping"


class AnnualCroppingWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = AnnualCropping
        fields = "__all__"
        ref_name = "AnnualCropping"
        mandatory_fields = [
            "land_use_type",
            "tillage_management_type",
            "organic_input_type",
            "residue_management_type",
        ]

    def validate(self, data):
        mandatory_fields = []

        lut_scenarios = get_filled_scenarios(data, ["land_use_type"])

        for scenario in lut_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class AnnualCroppingReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = AnnualCropping
        fields = "__all__"
        ref_name = "AnnualCropping"


# Perennial Cropping


class MinorSeasonPerennialCroppingWriteSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = MinorSeasonPerennialCropping
        fields = "__all__"
        ref_name = "MinorSeasonPerennialCropping"
        mandatory_fields = [
            "land_use_type",
            "tillage_management_type",
            "organic_input_type",
        ]

    def validate(self, data):
        mandatory_fields = []

        lut_scenarios = get_filled_scenarios(data, ["land_use_type"])

        for scenario in lut_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class MinorSeasonPerennialCroppingReadSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = MinorSeasonPerennialCropping
        fields = "__all__"
        ref_name = "MinorSeasonPerennialCropping"


class PerennialCroppingWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = PerennialCropping
        fields = "__all__"
        ref_name = "PerennialCropping"
        mandatory_fields = [
            "land_use_type",
            "tillage_management_type",
            "organic_input_type",
        ]

    def validate(self, data):
        mandatory_fields = []

        lut_scenarios = get_filled_scenarios(data, ["land_use_type"])

        for scenario in lut_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class PerennialCroppingReadSerializer(LandModuleReadSerializer):
    minor_seasons = MinorSeasonPerennialCroppingReadSerializer(many=True, read_only=True)

    class Meta:
        model = PerennialCropping
        fields = "__all__"
        ref_name = "PerennialCropping"
        extra_fields = ["minor_seasons"]


# Land Use Change


class LandUseChangeWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = LandUseChange
        fields = "__all__"
        ref_name = "LandUseChange"
        mandatory_fields = []


class LandUseChangeReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = LandUseChange
        fields = "__all__"
        ref_name = "LandUseChange"


# Organic Soil


class OrganicSoilWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = OrganicSoil
        fields = "__all__"
        ref_name = "OrganicSoil"
        mandatory_fields = [
            "fire_type",
        ]

    def validate(self, data):
        mandatory_fields = ["peat_type"]

        peat_scenarios = ["start", "w", "wo"]
        fire_scenarios = get_filled_scenarios(data, ["fire_type"])

        for scenario in peat_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, ["peat_extraction_height", "peat_area"])
        for scenario in fire_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, ["soil_fire_periodicity", "soil_fire_impact_percentage"])

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class OrganicSoilReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = OrganicSoil
        fields = "__all__"
        ref_name = "OrganicSoil"


# Flooded Rice


class MinorSeasonFloodedRiceWriteSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = MinorSeasonFloodedRice
        fields = "__all__"
        ref_name = "MinorSeasonFloodedRice"
        mandatory_fields = [
            "water_management_type_before_cultivation",
            "water_management_type_after_cultivation",
            "organic_amendment_type",
        ]

    def validate(self, data):
        mandatory_fields = []

        water_mgmt_before_scenarios = get_filled_scenarios(data, ["water_management_type_before_cultivation"])
        water_mgmt_after_scenarios = get_filled_scenarios(data, ["water_management_type_after_cultivation"])
        organic_amendment_scenarios = get_filled_scenarios(data, ["organic_amendment_type"])

        for scenario in water_mgmt_before_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, ["water_management_type_before_cultivation"])
        for scenario in water_mgmt_after_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, ["water_management_type_after_cultivation"])
        for scenario in organic_amendment_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, ["organic_amendment_type"])

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class MinorSeasonFloodedRiceReadSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = MinorSeasonFloodedRice
        fields = "__all__"
        ref_name = "MinorSeasonFloodedRice"


class FloodedRiceWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = FloodedRice
        fields = "__all__"
        ref_name = "FloodedRice"
        mandatory_fields = [
            "water_management_type_before_cultivation",
            "water_management_type_after_cultivation",
            "organic_amendment_type",
        ]

    def validate(self, data):

        mandatory_fields = []

        water_mgmt_before_scenarios = get_filled_scenarios(data, ["water_management_type_before_cultivation"])
        water_mgmt_after_scenarios = get_filled_scenarios(data, ["water_management_type_after_cultivation"])
        organic_amendment_scenarios = get_filled_scenarios(data, ["organic_amendment_type"])

        for scenario in water_mgmt_before_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, ["water_management_type_before_cultivation"])
        for scenario in water_mgmt_after_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, ["water_management_type_after_cultivation"])
        for scenario in organic_amendment_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, ["organic_amendment_type"])

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        # Get cultivation_days of all minor_seasons and check that they are not greater than 365 including the main season
        cultivation_days = data.get("cultivation_days", 0)
        minor_seasons = data.get("minor_seasons", None)

        if minor_seasons:
            if minor_seasons.count() > 4:
                raise serializers.ValidationError(f"Minor seasons cannot be more than 4")

            for season in minor_seasons:
                cultivation_days += season.get("cultivation_days", 0)

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


# Building
class BuildingWriteSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = Building
        fields = "__all__"
        ref_name = "Building"
        mandatory_fields = [
            "building_type",
            "area_m2",
        ]

    def validate(self, data):
        mandatory_fields = []

        building_type_scenarios = get_filled_scenarios(data, ["building_type"])

        for scenario in building_type_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")
        elif mandatory_fields:
            data["status"] = StatusType.objects.get(name="READY")

        return super().validate(data)


class BuildingReadSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = Building
        fields = "__all__"
        ref_name = "Building"

    def validate(self, data):
        if not self.instance.status.name == "READY":
            raise serializers.ValidationError("A building module is not ready")

        return super().validate(data)


# Road


class RoadWriteSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = Road
        fields = "__all__"
        ref_name = "Road"
        mandatory_fields = [
            "road_type",
            "length_km",
            "width_m",
        ]

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


class RoadReadSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = Road
        fields = "__all__"
        ref_name = "Road"

    def validate(self, data):
        if not self.instance.status.name == "READY":
            raise serializers.ValidationError("A road module is not ready")

        return super().validate(data)


# Other


class OtherInfrastructureWriteSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = OtherInfrastructure
        fields = "__all__"
        ref_name = "Other"
        mandatory_fields = [
            "area_m2",
        ]

    def validate(self, data):
        mandatory_fields = []

        areas = get_filled_scenarios(data, self.Meta.mandatory_fields)

        for scenario in areas:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")
        elif mandatory_fields:
            data["status"] = StatusType.objects.get(name="READY")

        return super().validate(data)


class OtherInfrastructureReadSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = OtherInfrastructure
        fields = "__all__"
        ref_name = "Other"

    def validate(self, data):
        if not self.instance.status.name == "READY":
            raise serializers.ValidationError("An other infrastructure module is not ready")

        return super().validate(data)


class IrrigationWriteSerializer(ModuleBaseSerializer):
    class Meta:
        model = Irrigation
        fields = "__all__"
        ref_name = "Irrigation"
        mandatory_fields = [
            "irrigation_type",
            "ha",
        ]


class IrrigationReadSerializer(ModuleBaseSerializer):
    class Meta:
        model = Irrigation
        fields = "__all__"
        ref_name = "Irrigation"


# IrrigationSystem


class IrrigationSystemWriteSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = IrrigationSystem
        fields = "__all__"
        ref_name = "IrrigationSystem"
        mandatory_fields = [
            "irrigation_type",
            "ha",
        ]

    def validate(self, data):
        super().validate(data)
        mandatory_fields = []

        irrigation_type_scenarios = get_filled_scenarios(data, ["irrigation_type"])

        for scenario in irrigation_type_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        max_entries = ConfigParam.objects.get(name=labels.IRRIGATION_SYSTEMS_LIMIT).get_parsed_value()

        if self.instance and self.instance.parent.irrigation_systems.count() + 1 > max_entries:
            raise serializers.ValidationError(f"Only {max_entries} irrigation systems are allowed")

        return data


class IrrigationSystemReadSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = IrrigationSystem
        fields = "__all__"
        ref_name = "IrrigationSystem"


# IrrigationPhase


class IrrigationPhaseWriteSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = IrrigationPhase
        fields = "__all__"
        ref_name = "IrrigationPhase"
        mandatory_fields = [
            "irrigation_phase_type",
            "fuel_type",
            "ha",
            "gross_irrigation_water",
        ]

    def validate(self, data):
        super().validate(data)

        mandatory_fields = []

        irrigation_phase_type_scenarios = get_filled_scenarios(data, ["irrigation_phase_type"])

        for scenario in irrigation_phase_type_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        max_entries = ConfigParam.objects.get(name=labels.IRRIGATION_PHASES_LIMIT).get_parsed_value()

        if self.instance and self.instance.parent.irrigation_phases.count() + 1 > max_entries:
            raise serializers.ValidationError(f"Only {max_entries} irrigation phases are allowed")

        return data


class IrrigationPhaseReadSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = IrrigationPhase
        fields = "__all__"
        ref_name = "IrrigationPhase"


class EnergyWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = Energy
        fields = "__all__"
        ref_name = "Energy"
        mandatory_fields = [
            "mwh",
        ]

    def validate(self, data):
        mandatory_fields = []

        energy_type_scenarios = get_filled_scenarios(data, ["mwh"])

        if energy_type_scenarios != []:
            mandatory_fields += "country"

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class EnergyReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = Energy
        fields = "__all__"
        ref_name = "Energy"


# Fuel


class FuelWriteSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = Fuel
        fields = "__all__"
        ref_name = "Fuel"
        mandatory_fields = [
            "fuel_type",
            "fuel",
        ]

    def validate(self, data):
        super().validate(data)
        mandatory_fields = []

        fuel_type_scenarios = get_filled_scenarios(data, ["fuel_type"])

        for scenario in fuel_type_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        parent = utils.getany([self.instance, dict(data)], "parent")
        max_elements = ConfigParam.objects.get(name=labels.FUEL_MODULES_LIMIT).get_parsed_value()

        if parent.fuels.count() + 1 > max_elements:
            raise serializers.ValidationError(f"Only {max_elements} fuel modules are allowed")

        return data


class FuelReadSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = Fuel
        fields = "__all__"
        ref_name = "Fuel"


class ElectricityWriteSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = Electricity
        fields = "__all__"
        ref_name = "Electricity"
        mandatory_fields = []

    def validate(self, data):
        super().validate(data)

        parent = utils.getany([self.instance, dict(data)], "parent")
        max_elements = ConfigParam.objects.get(name=labels.ELECTRICITY_MODULES_LIMIT).get_parsed_value()

        if not self.instance and parent.electricities.count() + 1 > max_elements:
            raise serializers.ValidationError(f"Only {max_elements} electricity modules are allowed")

        return data


class ElectricityReadSerializer(SubmoduleBaseSerializer):
    class Meta:
        model = Electricity
        fields = "__all__"
        ref_name = "Electricity"


# Livestock


class LivestockWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = Livestock
        fields = "__all__"
        ref_name = "Livestock"
        mandatory_fields = [
            "livestock_category_type",
            "heads_number",
            "livestock_production_type",
        ]

    def validate(self, data):
        mandatory_fields = []

        livestock_type_scenarios = get_filled_scenarios(data, ["livestock_category_type"])
        complementary_manure_mngt_scenarios = get_filled_scenarios(data, ["complementary_manure_management_type_t2"])

        for scenario in livestock_type_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)
            if scenario in complementary_manure_mngt_scenarios:
                mandatory_fields += generate_fields_for_scenario(
                    scenario,
                    ["complementary_manure_management_type_t2, percentage_heads_on_pasture"],
                )

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class LivestockReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = Livestock
        fields = "__all__"
        ref_name = "Livestock"


# Aquaculture


class AquacultureWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = Aquaculture
        fields = "__all__"
        ref_name = "Aquaculture"
        mandatory_fields = [
            "annual_production",
        ]

    def validate(self, data):
        return super().validate(data)


class AquacultureReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = Aquaculture
        fields = "__all__"
        ref_name = "Aquaculture"


# SmllFishery


class SmallFisheryWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = SmallFishery
        fields = "__all__"
        ref_name = "SmallFishery"
        mandatory_fields = [
            "fishery_type",
            "gear_type",
            "total_catch_yr",
        ]

    def validate(self, data):
        mandatory_fields = []

        fishery_type_scenarios = get_filled_scenarios(data, self.Meta.mandatory_fields)

        for scenario in fishery_type_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class SmallFisheryReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = SmallFishery
        fields = "__all__"
        ref_name = "SmallFishery"


# LargeFishery


class LargeFisheryWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = LargeFishery
        fields = "__all__"
        ref_name = "LargeFishery"
        mandatory_fields = [
            "fish_type",
            "gear_type",
            "total_catch_yr",
        ]

    def validate(self, data):
        mandatory_fields = []

        fishery_type_scenarios = get_filled_scenarios(data, self.Meta.mandatory_fields)

        for scenario in fishery_type_scenarios:
            mandatory_fields += generate_fields_for_scenario(scenario, self.Meta.mandatory_fields)

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class LargeFisheryReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = LargeFishery
        fields = "__all__"
        ref_name = "LargeFishery"


# Waterbody


class WaterbodyWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = Waterbody
        fields = "__all__"
        ref_name = "Waterbody"
        mandatory_fields = ["trophic_type"]

    def validate(self, data):
        mandatory_fields = []

        waterbody_type_scenarios = get_filled_scenarios(data, ["trophic_type"])

        mandatory_fields += generate_fields_for_scenarios(waterbody_type_scenarios, mandatory_fields)

        mandatory_fields += ["waterbody_type"]

        if waterbody_type_scenarios:
            mandatory_fields += ["area"]

        if not are_fields_filled(data, mandatory_fields):
            raise serializers.ValidationError(f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}")

        return super().validate(data)


class WaterbodyReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = Waterbody
        fields = "__all__"
        ref_name = "Waterbody"


class ProjectInvitationModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectInvitation
        fields = "__all__"
        ref_name = "ProjectInvitation"


class ProjectInvitationWriteSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=True)


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
        mandatory_fields = [
            "forest_type",
            "forest_condition_type",
        ]

    def validate(self, data):
        mandatory_fields = []
        errors = []

        mandatory_fields += self.Meta.mandatory_fields

        # Rotation mandatory fields
        rotation_length_yrs = get_filled_scenarios(data, ["rotation_length_yrs"])
        mandatory_fields += generate_fields_for_scenarios(rotation_length_yrs, ["rotation_percentage_biomass_for_energy"])

        # Logging mandatory fields
        logging_recurrence_yrs = get_filled_scenarios(data, ["logging_recurrence_yrs"])
        mandatory_fields += generate_fields_for_scenarios(logging_recurrence_yrs, ["logging_percentage_agb_logged", "logging_percentage_biomass_for_energy"])

        if not are_fields_filled(data, mandatory_fields):
            errors += [f"Missing fields. Check that all mandatory fields are present: {mandatory_fields}"]

        if self.instance and self.instance.disturbances.count() > 0:
            if logging_recurrence_yrs:
                errors += ["Cannot have logging and other disturbances at the same time"]

            pc_biomass_destruction_start = data.get("logging_percentage_agb_logged_start", 0)
            pc_biomass_destruction_wo = data.get("logging_percentage_agb_logged_wo", 0)
            pc_biomass_destruction_w = data.get("logging_percentage_agb_logged_w", 0)

            for disturbance in self.instance.disturbances.all():
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


class InputWriteSerializer(ModuleBaseSerializer):
    class Meta:
        model = Input
        fields = "__all__"
        ref_name = "Input"


class InputReadSerializer(ModuleBaseSerializer):
    class Meta:
        model = Input
        fields = "__all__"
        ref_name = "Input"


class InputEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InputEntry
        fields = "__all__"
        ref_name = "InputEntry"

    def validate(self, data):
        super().validate(data)

        parent = utils.getany([self.instance, dict(data)], "parent")
        max_entries = ConfigParam.objects.get(name=labels.INPUT_ENTRIES_LIMIT).get_parsed_value()

        if parent.input_entries.count() + 1 > max_entries:
            raise serializers.ValidationError(f"Only {max_entries} input entries are allowed")

        return data


class InputEntryReadSerializer(serializers.ModelSerializer):
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
        mandatory_fields = []

    def validate(self, data):
        return super().validate(data)


class SetAsideReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = SetAside
        fields = "__all__"
        ref_name = "SetAside"
        mandatory_fields = []


class DegradedLandWriteSerializer(LandModuleWriteSerializer):
    class Meta:
        model = DegradedLand
        fields = "__all__"
        ref_name = "DegradedLand"
        mandatory_fields = []

    def validate(self, data):
        return super().validate(data)


class DegradedLandReadSerializer(LandModuleReadSerializer):
    class Meta:
        model = DegradedLand
        fields = "__all__"
        ref_name = "DegradedLand"


class SettlementWriteSerializer(ModuleBaseSerializer):
    class Meta:
        model = Settlement
        fields = "__all__"
        ref_name = "Settlement"
        mandatory_fields = []


class SettlementReadSerializer(ModuleBaseSerializer):
    class Meta:
        model = Settlement
        fields = "__all__"
        ref_name = "Settlement"

    def validate(self, data):

        buildings = Building.objects.filter(parent=self.instance).all()

        for building in buildings:
            building_serializer = BuildingReadSerializer(data=building.__dict__, instance=building)
            if not building_serializer.is_valid():
                raise serializers.ValidationError(building_serializer.errors)

        roads = Road.objects.filter(parent=self.instance).all()
        for road in roads:
            road_serializer = RoadReadSerializer(data=road.__dict__, instance=road)
            if not road_serializer.is_valid():
                raise serializers.ValidationError(road_serializer.errors)

        other_infrastructures = OtherInfrastructure.objects.filter(parent=self.instance).all()
        for other_infrastructure in other_infrastructures:
            other_infrastructure_serializer = OtherInfrastructureReadSerializer(data=other_infrastructure.__dict__, instance=other_infrastructure)
            if not other_infrastructure_serializer.is_valid():
                raise serializers.ValidationError(other_infrastructure_serializer.errors)

        return super().validate(data)


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


class CoastalWetlandWriteSerializer(ModuleBaseSerializer):
    class Meta:
        model = CoastalWetland
        fields = "__all__"
        ref_name = "CoastalWetland"
        mandatory_fields = []

    def validate(self, data):
        return super().validate(data)


class CoastalWetlandReadSerializer(ModuleBaseSerializer):
    class Meta:
        model = CoastalWetland
        fields = "__all__"
        ref_name = "CoastalWetland"
