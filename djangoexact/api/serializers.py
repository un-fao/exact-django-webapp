from rest_framework import serializers
from rest_framework.fields import empty
from .models import *
from ipcc.models import *
from django.contrib.auth.models import User
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


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

def get_module_serializer(model_arg, create=False):
    class GenericSerializer(serializers.ModelSerializer):
        if not create:
            module_type = serializers.ReadOnlyField(default=model_arg.__name__)
            # exclude activity for update
            activity = ActivitySerializer(many=False, read_only=True)
        class Meta:
            model = model_arg
            fields = "__all__"
            extra_fields = ["module_type"]
            ref_name = model_arg.__name__

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