from rest_framework import serializers
from rest_framework.fields import empty
from .models import *
from ipcc.models import *
from django.contrib.auth.models import User
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import sys


class ResultSerializer(serializers.Serializer):
    total_w = serializers.FloatField()
    total_wo = serializers.FloatField()
    balance = serializers.FloatField()


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

def get_module_serializer(model_arg):
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

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class ProjectSerializer(serializers.ModelSerializer):
    climate = get_model_serializer(Climate)(many=False)
    continent = get_model_serializer(Continent)(many=False)
    country = get_model_serializer(Country)(many=False)
    moisture = get_model_serializer(Moisture)(many=False)
    soil_type = get_model_serializer(SoilType)(many=False)
    gw_potential = get_model_serializer(GlobalWarmingPotential)(many=False)
    soc_ref = get_model_serializer(SoilOrganicCarbon)(many=False)
    status = get_model_serializer(ProjectStatus)(many=False)

    class Meta:
        model = Project
        fields = "__all__"
        ref_name = "Project"

class ProjectResultSerializer(serializers.Serializer):
    # TODO: This can probably be removed and the fields moved to ProjectSerializer as read_only
    activities = serializers.SerializerMethodField()
    results = ResultSerializer(many=False)

class ActivitySerializer(serializers.ModelSerializer):
    project = ProjectSerializer(many=False, read_only=True)
    user = UserSerializer(many=False, read_only=True)

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
        class Meta:
            model = LandUseChange
            fields = ["module_type_start", "module_type_w", "module_type_wo", "area"]
            ref_name = "LandUseChange"

    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=True)
    name = serializers.CharField(max_length=255, required=True)
    climate = serializers.PrimaryKeyRelatedField(queryset=Climate.objects.all(), required=True)
    soil_type = serializers.PrimaryKeyRelatedField(queryset=SoilType.objects.all(), required=True)
    duration = serializers.IntegerField(required=True)
    land_use_change = LandUseChangeBuilderSerializer(many=False, required=False)
    modules = serializers.PrimaryKeyRelatedField(queryset=ModuleType.objects.all(), many=True, required=False)
    has_input = serializers.BooleanField(default=False, required=False)

    def validate(self, data):
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
                land_use_change = LandUseChange.objects.create(**self.validated_data["land_use_change"], activity=activity)
                land_use_change.save()
            
            if self.validated_data.get("modules", None):
                for module_type in self.validated_data["modules"]:
                    try:
                        Module = apps.get_model("api", module_type.class_name)
                        Module.objects.create(activity=activity)
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