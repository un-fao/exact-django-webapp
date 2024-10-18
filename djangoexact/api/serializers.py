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
    Waterbody,
    LandModule,
    InvitationStatusType,
    ChangeRate,
    Note,
    FieldDefinition,
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

        def __init__(self, *args, **kwargs):
            log.debug(f"START GenericSerializer[{model_arg.__name__}].init")
            super().__init__(*args, **kwargs)

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
        fields = ["id", "email", "first_name", "last_name", "country", "organization"]


class UserWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "first_name", "last_name", "country", "organization"]


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
    owner = UserReadSerializer(many=False, read_only=True)
    role = serializers.SerializerMethodField()

    capitalization_years = serializers.FloatField(read_only=True)

    def get_role(self, obj):
        ctx = self.context.get("request", None)

        if not ctx:
            return []

        user = ctx.user
        user_project_group = ProjectMembership.objects.filter(user=user, project=obj).all()

        return [group.group.name for group in user_project_group] if user_project_group else []

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
        if self.instance and data.get("cost", None):
            total_activity_cost = self.instance.activities.all().values_list("cost", flat=True)

            if sum(total_activity_cost) > data.get("cost"):
                raise serializers.ValidationError("Total cost of activities cannot be greater than project cost")

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


class ProjectResultSerializer(serializers.Serializer):
    # TODO: This can probably be removed and the fields moved to ProjectSerializer as read_only
    activities = serializers.SerializerMethodField()
    results = ResultSerializer(many=False)


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
        if self.instance:
            luc_module: ModuleType = ModuleType.objects.get(name="Land Use Change")

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
    activity_id = serializers.PrimaryKeyRelatedField(queryset=Activity.objects.all(), many=False, required=False)

    def validate(self, data):
        if data.get("activity_id", None):
            self.instance = data.get("activity_id")

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

        default_change_rate = ChangeRate.objects.get(name="linear")

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
            ModuleType.objects.get(name="Land Use Change").id,
        )

        if create_organic_soil:
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

    def edit_existing_luc(self):
        luc: LandUseChange = self.instance.landusechange.first()

        self.instance.module_types.remove(luc.module_type_start.id, luc.module_type_w.id, luc.module_type_wo.id)

        luc_modules = luc.get_module_types()
        new_modules = list(self.validated_data["land_use_change"].values())

        difference = list(set(luc_modules) - set(new_modules))

        for module in difference:
            module_instance = getattr(self.instance, module.class_name.lower())
            if module_instance.exists():
                module_instance.first().delete()

        luc.module_type_start = self.validated_data["land_use_change"]["module_type_start"]
        luc.module_type_w = self.validated_data["land_use_change"]["module_type_w"]
        luc.module_type_wo = self.validated_data["land_use_change"]["module_type_wo"]
        luc.area = self.validated_data["area"]

        self.instance.module_types.add(luc.module_type_start.id, luc.module_type_w.id, luc.module_type_wo.id)

        luc.save()
        self.instance.save()

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
                        # If field is a boolean, set it to False
                        if field.get_internal_type() == "BooleanField":
                            setattr(module, field.name, False)
                        else:
                            setattr(module, field.name, None)
            if not module.is_with():
                for field in module._meta.fields:
                    if field.name.endswith("_w"):
                        if field.get_internal_type() == "BooleanField":
                            setattr(module, field.name, False)
                        else:
                            setattr(module, field.name, None)
            if not module.is_without():
                for field in module._meta.fields:
                    if field.name.endswith("_wo"):
                        if field.get_internal_type() == "BooleanField":
                            setattr(module, field.name, False)
                        else:
                            setattr(module, field.name, None)

            if hasattr(module, "area"):
                module.area = self.validated_data.get("area")

            module.save()

    @transaction.atomic
    def save(self, **kwargs):
        self.validate_total_project_cost()

        create_organic_soil = "OrganicSoil" in [module.class_name for module in self.validated_data.get("module_types", [])]
        has_luc_module = self.validated_data.get("land_use_change", False)

        if self.instance:
            old_module_types = list(map(lambda module: module, self.instance.module_types.all()))
            new_module_types = list(map(lambda module: module, self.validated_data["module_types"]))
            create_organic_soil = create_organic_soil and not "OrganicSoil" in [module.class_name for module in old_module_types]

            luc: LandUseChange = self.instance.landusechange.first()
            if luc and has_luc_module:
                self.edit_existing_luc()
            elif luc and not has_luc_module:
                self.delete_existing_luc()
            elif not luc and has_luc_module:
                luc = self.handle_luc_module(self.instance, create_organic_soil)

            luc = self.instance.landusechange.first()

            luc_module_types = list(luc.get_module_types()) + [ModuleType.objects.get(class_name="LandUseChange")] if luc else []
            new_module_types = list(map(lambda module: module, self.validated_data["module_types"] + luc_module_types) if has_luc_module else [module for module in self.validated_data["module_types"]])

            kept_module_types = list(set(old_module_types) & set(new_module_types))
            removed_module_types = list(set(old_module_types) - set(new_module_types))
            added_module_types = list(set(new_module_types) - set(old_module_types))

            for module in removed_module_types:
                ModuleClass = apps.get_model("api", module.class_name)
                module_instance = ModuleClass.objects.filter(activity=self.instance)
                if module_instance.exists():
                    module_instance.first().delete()

            for module in kept_module_types:
                if module.class_name == "LandUseChange":
                    continue

                ModuleClass = apps.get_model("api", module.class_name)
                module_instance = ModuleClass.objects.filter(activity=self.instance).first()
                # TODO: Maybe instead of checking the module type we can check the instance class?
                if module_instance and module_instance.module_type in luc_module_types or module.class_name == "OrganicSoil":
                    module_instance.land_use_change = luc
                    module_instance.save()
                elif module_instance:
                    module_instance.land_use_change = None
                    module_instance.save()

            for module in added_module_types:
                if module.class_name == "LandUseChange":
                    if module in self.validated_data["module_types"]:
                        raise serializers.ValidationError("Land Use Change module cannot be added manually")
                    continue

                ModuleClass = apps.get_model("api", module.class_name)

                module_data = {"activity": self.instance}
                if module in luc_module_types:
                    module_data["area"] = self.validated_data.get("area")

                module_instance = ModuleClass.objects.create(**module_data)
                if luc and module in list(luc.get_module_types()):
                    module_instance.land_use_change = luc
                    module_instance.save()

            self.instance.module_types.clear()
            self.instance.module_types.add(*new_module_types)
            self.instance.save()

            self.sanitize_input_entries()

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
    activity = ActivitySerializer(many=False, read_only=True)
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
        log.debug(f"START BaseGenericModuleSerializer[{self.Meta.ref_name}].init")

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


class BaseSubmoduleSerializer(BaseGenericModuleSerializer):

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


class NoScenarioModuleSerializer(BaseModuleSerializer, NoScenarioBaseSerializer):
    pass


class ScenarioModuleSerializer(BaseModuleSerializer, ScenarioBaseSerializer):
    pass


class NoScenarioSubmoduleSerializer(BaseSubmoduleSerializer, NoScenarioBaseSerializer):
    pass


class ScenarioSubmoduleSerializer(BaseSubmoduleSerializer, ScenarioBaseSerializer):
    pass


class LandModuleSeralizer(ScenarioModuleSerializer):
    activity = ActivitySerializer(many=False, read_only=True)
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
                data["status"] = StatusType.objects.get(name="EMPTY")
            else:
                data["status"] = StatusType.objects.get(name="READY")

            super().validate(data)

            for field, value in data.items():
                setattr(self.instance, field, value)

            self.instance.save()

        if luc:
            # If the module is associated with a Land Use Change, pdate the status of the Land Use Change
            luc_serializer: LandUseChangeWriteSerializer = get_module_serializer(LandUseChange)(data={}, instance=luc, many=False, partial=True)
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


class GrasslandReadSerializer(GrasslandWriteSerializer):
    pass


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


class MinorSeasonAnnualCroplandReadSerializer(MinorSeasonAnnualCroplandWriteSerializer):
    pass


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
                data["status"] = StatusType.objects.get(name="SUBMODULES_EMPTY")
                return data

        return super().validate(data)


class AnnualCroplandWriteSerializer(AnnualCroplandSerializer):
    pass


class AnnualCroplandReadSerializer(AnnualCroplandSerializer):
    pass


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


class MinorSeasonPerennialCroplandReadSerializer(MinorSeasonPerennialCroplandWriteSerializer):
    pass


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


class PerennialCroplandReadSerializer(PerennialCroplandWriteSerializer):
    minor_seasons = MinorSeasonPerennialCroplandReadSerializer(many=True, read_only=True)
    pass


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
                data["status"] = StatusType.objects.get(name="READY")
            else:
                data["status"] = StatusType.objects.get(name="EMPTY")
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


class MinorSeasonFloodedRiceReadSerializer(MinorSeasonFloodedRiceWriteSerializer):
    pass


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
            if minor_seasons.count() > 4:
                raise serializers.ValidationError(f"Minor seasons cannot be more than 4")

            # for season in minor_seasons:
            #     cultivation_days += season.get("cultivation_days", 0)

        if cultivation_days > 365:
            raise serializers.ValidationError(f"Cultivation days cannot be greater than 365 (one year)")

        return super().validate(data)


class FloodedRiceReadSerializer(FloodedRiceWriteSerializer):
    minor_seasons = MinorSeasonFloodedRiceReadSerializer(many=True, read_only=True)

    class Meta:
        model = FloodedRice
        fields = "__all__"
        ref_name = "FloodedRice"
        extra_fields = ["minor_seasons"]
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


# Building
class BuildingSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = Building
        fields = "__all__"
        ref_name = "Building"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "building_type",
                    "area_m2_start",
                ],
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

    def validate(self, data):

        return super().validate(data)


class BuildingWriteSerializer(BuildingSerializer):
    pass


class BuildingReadSerializer(BuildingSerializer):
    pass


# Road


class RoadSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = Road
        fields = "__all__"
        ref_name = "Road"
        mandatory_fields = {
            "start": {
                "mandatory": [
                    "road_type",
                    "length_km_start",
                    "width_m_start",
                ],
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

    def validate(self, data):
        return super().validate(data)


class RoadWriteSerializer(RoadSerializer):
    pass


class RoadReadSerializer(RoadSerializer):
    pass


# Other


class OtherInfrastructureSerializer(ScenarioSubmoduleSerializer):
    class Meta:
        model = OtherInfrastructure
        fields = "__all__"
        ref_name = "OtherInfrastructure"
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


class OtherInfrastructureWriteSerializer(OtherInfrastructureSerializer):
    pass


class OtherInfrastructureReadSerializer(OtherInfrastructureSerializer):
    pass


class IrrigationWriteSerializer(ScenarioModuleSerializer):
    class Meta:
        model = Irrigation
        fields = "__all__"
        ref_name = "Irrigation"
        mandatory_fields = {}


class IrrigationReadSerializer(ScenarioModuleSerializer):
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


class IrrigationSystemReadSerializer(IrrigationSystemWriteSerializer):
    pass


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


class IrrigationPhaseReadSerializer(IrrigationPhaseWriteSerializer):
    pass


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

        if any([not electricity.is_ready() for electricity in electricities]):
            raise serializers.ValidationError("Electricity modules are not ready for calculations")

        if any([not fuel.is_ready() for fuel in fuels]):
            raise serializers.ValidationError("Fuel modules are not ready for calculations")

        return data


class EnergyWriteSerializer(EnergySerializer):
    pass


class EnergyReadSerializer(EnergySerializer):
    pass


# Fuel


class FuelSerializer(ScenarioSubmoduleSerializer):
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


class FuelWriteSerializer(FuelSerializer):
    pass


class FuelReadSerializer(FuelSerializer):
    pass


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


class ElectricityReadSerializer(ElectricityWriteSerializer):
    pass


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


class LivestockReadSerializer(LivestockWriteSerializer):
    pass


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


class AquacultureReadSerializer(AquacultureWriteSerializer):
    pass


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


class SmallFisheryReadSerializer(SmallFisheryWriteSerializer):
    pass


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


class LargeFisheryReadSerializer(LargeFisheryWriteSerializer):
    pass


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


class WaterbodyReadSerializer(WaterbodySerializer):
    pass


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

        data = self.merge_instance_data(data, instance=instance)

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


class ForestManagementReadSerializer(ForestManagementWriteSerializer):
    pass


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
                data["status"] = StatusType.objects.get(name="SUBMODULES_EMPTY")
                return data

        return super().validate(data)


class InputWriteSerializer(InputSerializer):
    pass


class InputReadSerializer(InputSerializer):
    pass


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


class InputEntryReadSerializer(InputEntrySerializer):
    pass


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


class ProjectMembershipSerializer(serializers.ModelSerializer):
    user = UserReadSerializer(many=False, read_only=True)
    group = GroupSerializer(many=False, read_only=True)

    class Meta:
        model = ProjectMembership
        fields = "__all__"
        ref_name = "ProjectMembership"


class SetAsideWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = SetAside
        fields = "__all__"
        ref_name = "SetAside"
        mandatory_fields = {}


class SetAsideReadSerializer(SetAsideWriteSerializer):
    pass


class OtherLandWriteSerializer(LandModuleSeralizer):
    class Meta:
        model = OtherLand
        fields = "__all__"
        ref_name = "OtherLand"
        mandatory_fields = {}


class OtherLandReadSerializer(OtherLandWriteSerializer):
    pass


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

        buildings = Building.objects.filter(parent=self.instance).all()

        if any(not building.is_ready() for building in buildings):
            raise serializers.ValidationError("At least one building is not ready for calculations")

        for building in buildings:
            building_serializer = BuildingReadSerializer(data={}, partial=True, instance=building)
            if not building_serializer.is_valid():
                raise serializers.ValidationError(building_serializer.errors)

        roads = Road.objects.filter(parent=self.instance).all()

        if any(not road.is_ready() for road in roads):
            raise serializers.ValidationError("At least one road is not ready for calculations")

        for road in roads:
            road_serializer = RoadReadSerializer(data={}, partial=True, instance=road)
            if not road_serializer.is_valid():
                raise serializers.ValidationError(road_serializer.errors)

        other_infrastructures = OtherInfrastructure.objects.filter(parent=self.instance).all()

        if any(not other_infrastructure.is_ready() for other_infrastructure in other_infrastructures):
            raise serializers.ValidationError("At least one other infrastructure is not ready for calculations")

        for other_infrastructure in other_infrastructures:
            other_infrastructure_serializer = OtherInfrastructureReadSerializer(data={}, partial=True, instance=other_infrastructure)
            if not other_infrastructure_serializer.is_valid():
                raise serializers.ValidationError(other_infrastructure_serializer.errors)

        return super().validate(data)


class SettlementWriteSerializer(SettlementSerializer):
    pass


class SettlementReadSerializer(SettlementSerializer):
    pass


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


class CoastalWetlandSerializer(NoScenarioModuleSerializer):
    class Meta:
        model = CoastalWetland
        fields = "__all__"
        ref_name = "CoastalWetland"
        mandatory_fields = {
            "start": {
                "mandatory": ["land_use_type", "area"],
            },
            "with": {
                "mandatory": ["land_use_type", "area"],
            },
            "without": {
                "mandatory": ["land_use_type", "area"],
            },
        }


class CoastalWetlandWriteSerializer(CoastalWetlandSerializer):
    pass


class CoastalWetlandReadSerializer(CoastalWetlandSerializer):
    pass


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


class ForestDisturbanceReadSerializer(ForestDisturbanceWriteSerializer):
    pass


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


class NewNoteSerializer(serializers.ModelSerializer):
    content = serializers.CharField(required=True)
    module_type_id = serializers.IntegerField(required=True)
    module_id = serializers.IntegerField(required=True)

    class Meta:
        model = Note
        fields = ["content", "module_type_id", "module_id"]
        ref_name = "Note"

    def validate(self, data):

        try:
            module_type = ModuleType.objects.get(pk=data["module_type_id"])
        except ModuleType.DoesNotExist:
            raise serializers.ValidationError("Module type does not exist")

        ModuleClass = utils.get_model(module_type.class_name, suffix=None)
        try:
            module: Module | Submodule = ModuleClass.objects.get(pk=data["module_id"])
        except ModuleClass.DoesNotExist:
            raise serializers.ValidationError("Module does not exist")

        if module.note.exists():
            raise serializers.ValidationError(f"Note already exists for this module. Use PUT with id {module.note.pk} to update")

        return super().validate(data)

    def save(self, **kwargs):
        module_type = ModuleType.objects.get(pk=self.validated_data["module_type_id"])
        ModuleClass = utils.get_model(module_type.class_name, suffix=None)
        module: Module | Submodule = ModuleClass.objects.get(pk=self.validated_data["module_id"])

        note = Note.objects.create(
            author=self.context["request"].user,
            content=self.validated_data["content"],
            content_object=module,
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
