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

    return GenericSerializer


def get_module_serializer(model_arg):
    class GenericSerializer(serializers.ModelSerializer):
        # activity = serializers.PrimaryKeyRelatedField(source='activity.name', queryset=Activity.objects.all(), many=False)
        module_type = serializers.ReadOnlyField(default=model_arg.__name__)

        class Meta:
            model = model_arg
            fields = "__all__"
            extra_fields = ["module_type"]
            ref_name = model_arg.__name__

    return GenericSerializer


class ProjectSerializer(serializers.ModelSerializer):
    climate = get_model_serializer(Climate)(many=False)
    continent = get_model_serializer(Continent)(many=False)
    country = get_model_serializer(Country)(many=False)
    moisture = get_model_serializer(Moisture)(many=False)
    soil_type = get_model_serializer(SoilType)(many=False)
    gw_potential = get_model_serializer(GlobalWarmingPotential)(many=False)

    class Meta:
        model = Project
        fields = "__all__"
        ref_name = "Project"


class ActivitySerializer(serializers.ModelSerializer):
    project = get_model_serializer(Project)(many=False)
    modules = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = "__all__"
        ref_name = "Activity"
