from rest_framework import serializers
from rest_framework.fields import empty
from .models import *
from ipcc.models import *
from django.contrib.auth.models import User
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import sys
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes

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

def get_module_serializer(model_arg: Model) -> serializers.ModelSerializer:
    class GenericSerializer(serializers.ModelSerializer):
        module_type = get_model_serializer(ModuleType)(many=False, read_only=True)
        activity = ActivitySerializer(many=False, read_only=True)

        class Meta:
            model = model_arg
            fields = "__all__"
            extra_fields = ["module_type"]
            ref_name = model_arg.__name__

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields["module_type"].default = ModuleType.objects.get(class_name=model_arg.__name__)
            

    return GenericSerializer

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
    def by(self, by: BreakdownTypes = BreakdownTypes.TOTAL):
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
        if self.serializer == TotalResultSerializer:
            self.fields["total_w"] = serializers.FloatField()
            self.fields["total_wo"] = serializers.FloatField()
            self.fields["balance"] = serializers.FloatField()
        else:
            self.fields["total_w"] = self.serializer(many=True)
            self.fields["total_wo"] = self.serializer(many=True)
            self.fields["balance"] = self.serializer(many=True)
        super().__init__(*args, **kwargs)

    def by(self, by: BreakdownTypes = BreakdownTypes.TOTAL):
        match by:
            case BreakdownTypes.TOTAL:
                self.serializer = TotalResultSerializer
            case BreakdownTypes.GAS:
                self.serializer = YearlyGasEmissionSerializer
            case BreakdownTypes.ACTIVITY:
                self.serializer = YearlyActivityEmissionSerializer
            case BreakdownTypes.ACTIVITY_GAS:
                self.serializer = YearlyActivityEmissionSerializer
            case _:
                self.serializer = TotalResultSerializer

        return self

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class CountrySerializer(serializers.ModelSerializer):
    region = get_model_serializer(Region)(many=False, read_only=True)
    ipcc_region = get_model_serializer(IPCCRegion)(many=False, read_only=True)
    gleam_region = get_model_serializer(GLEAMRegion)(many=False, read_only=True)
    class Meta:
        model = Country
        fields = "__all__"
        ref_name = "Country"

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class ReadProjectSerializer(serializers.ModelSerializer):
    climate = get_model_serializer(Climate)(many=False, read_only=True)
    country = CountrySerializer(many=False, read_only=True)
    moisture = get_model_serializer(Moisture)(many=False, read_only=True)
    soil_type = get_model_serializer(SoilType)(many=False, read_only=True)
    gw_potential = get_model_serializer(GlobalWarmingPotential)(many=False, read_only=True)
    status = get_model_serializer(ProjectStatus)(many=False, required=False, read_only=True)
    user = UserSerializer(many=False, read_only=True)

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

class ProjectResultSerializer(serializers.Serializer):
    # TODO: This can probably be removed and the fields moved to ProjectSerializer as read_only
    activities = serializers.SerializerMethodField()
    results = ResultSerializer(many=False)

class ActivitySerializer(serializers.ModelSerializer):
    project = ReadProjectSerializer(many=False, read_only=True)
    user = UserSerializer(many=False, read_only=True)
    climate_t2 = get_model_serializer(Climate)()
    soil_type_t2 = get_model_serializer(SoilType)()

    class Meta:
        model = Activity
        fields = "__all__"
        ref_name = "Activity"

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
    climate = serializers.PrimaryKeyRelatedField(queryset=Climate.objects.all(), required=True)
    soil_type = serializers.PrimaryKeyRelatedField(queryset=SoilType.objects.all(), required=True)
    duration = serializers.IntegerField(required=True)
    land_use_change = LandUseChangeBuilderSerializer(many=False, required=False)
    modules = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), many=True, required=False)
    has_input = serializers.BooleanField(default=False, required=False)
    area = serializers.FloatField(required=True)

    def validate(self, data):
        luc_module: ModuleType = ModuleType.objects.filter(name="Land Use Change").first()
        if luc_module and luc_module in data["modules"]:
            raise serializers.ValidationError("Land Use Change module cannot be added manually")
        if data["has_input"] and not data.get("modules", None):
            raise serializers.ValidationError("If has_input is true, at least one input module must be provided")
        super().validate(data)
        return data
    
    def save(self, **kwargs):
        try:
            activity = Activity.objects.create(
                name=self.validated_data["name"], 
                project=self.validated_data["project"], 
                climate_t2=self.validated_data["climate"], 
                soil_type_t2=self.validated_data["soil_type"], 
                duration_t2=self.validated_data["duration"]
            )

            if self.validated_data.get("land_use_change", None):
                land_use_change = LandUseChange.objects.create(**self.validated_data["land_use_change"], activity=activity, area=self.validated_data["area"])
                land_use_change.save()
            
            if self.validated_data.get("modules", None):
                for module_type in self.validated_data["modules"]:
                    try:
                        Module = apps.get_model("api", module_type.class_name)

                        data = {"activity": activity}

                        if self.validated_data.get("land_use_change", None) and module_type.is_luc:
                            data["land_use_change"] = land_use_change
                        elif getattr(Module, "area", None):
                            data["area"] = self.validated_data["area"]

                        Module.objects.create(**data)

                    except AttributeError:
                        raise serializers.ValidationError(f"Invalid module type: {module_type.class_name}")
        except Exception as e:
            raise serializers.ValidationError(e)
        
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
        fields = ['id', 'username']

class CommentSerializer(serializers.ModelSerializer):
    replies = RecursiveField(many=True, read_only=True)
    author = UserSummarySerializer(many=False, read_only=True)
    class Meta:
        model = Comment
        fields = '__all__'

class CommentThreadSerializer(serializers.ModelSerializer):
    comments = CommentSerializer(many=True, read_only=True)
    author = UserSummarySerializer(many=False, read_only=True)
    class Meta:
        model = CommentThread
        fields = '__all__'

class LandUseTypeSerializer(serializers.ModelSerializer):

    module_types = get_model_serializer(ModuleType)(many=True, read_only=True)
    climate = get_model_serializer(Climate)(many=False, read_only=True)
    moisture = get_model_serializer(Moisture)(many=False, read_only=True)
    class Meta:
        model = LandUseType
        fields = "__all__"
        ref_name = "LandUseType"