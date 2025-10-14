from rest_framework import serializers
import api.models as api_models
import ipcc.models as ipcc_models
import api.serializers as api_serializers
from django.db import models


class PublicProjectSerializer(serializers.ModelSerializer):
    country = api_serializers.CountrySerializer(many=False, read_only=True)
    climate = api_serializers.get_model_serializer(api_models.Climate)(many=False, read_only=True)
    moisture = api_serializers.get_model_serializer(api_models.Moisture)(many=False, read_only=True)
    soil_type = api_serializers.get_model_serializer(api_models.SoilType)(many=False, read_only=True)
    gw_potential = api_serializers.get_model_serializer(ipcc_models.GlobalWarmingPotential)(many=False, read_only=True)
    status = api_serializers.get_model_serializer(api_models.ProjectStatus)(many=False, required=False, read_only=True)
    total_hectares = serializers.SerializerMethodField()
    total_catch = serializers.SerializerMethodField()
    total_livestock = serializers.SerializerMethodField()

    capitalization_years = serializers.FloatField(read_only=True)

    class Meta:
        model = api_models.Project
        exclude = ["owner", "created_at", "updated_at"]
        ref_name = "Project"

    def get_total_hectares(self, obj):
        return sum([activity.get_land_modules_area() for activity in obj.activities.all()])

    def get_total_catch(self, obj):
        small_fisheries = api_models.SmallFishery.objects.filter(activity__project=obj).all()
        large_fisheries = api_models.LargeFishery.objects.filter(activity__project=obj).all()
        aquacultures = api_models.Aquaculture.objects.filter(activity__project=obj).all()

        def safe_sum(items, attr):
            return sum(getattr(item, attr) or 0 for item in items)

        scenario_based_catch = {
            "start": safe_sum(small_fisheries, "total_catch_yr_start") + safe_sum(large_fisheries, "total_catch_yr_start") + safe_sum(aquacultures, "annual_production_start"),
            "w": safe_sum(small_fisheries, "total_catch_yr_w") + safe_sum(large_fisheries, "total_catch_yr_w") + safe_sum(aquacultures, "annual_production_w"),
            "wo": safe_sum(small_fisheries, "total_catch_yr_wo") + safe_sum(large_fisheries, "total_catch_yr_wo") + safe_sum(aquacultures, "annual_production_wo"),
        }

        return scenario_based_catch

    def get_total_livestock(self, obj):
        livestock = api_models.Livestock.objects.filter(activity__project=obj).all()

        all_livestock_start = sum([animal.heads_number_start for animal in list(filter(lambda animal: animal.heads_number_start is not None, livestock))])
        all_livestock_w = sum([animal.heads_number_w for animal in list(filter(lambda animal: animal.heads_number_w is not None, livestock))])
        all_livestock_wo = sum([animal.heads_number_wo for animal in list(filter(lambda animal: animal.heads_number_wo is not None, livestock))])

        scenario_based_livestock = {
            "start": all_livestock_start,
            "w": all_livestock_w,
            "wo": all_livestock_wo,
        }

        return scenario_based_livestock


class PublicActivitySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = api_models.Activity
        fields = ["id", "name", "module_types", "completion_percentage"]
        ref_name = "Activity"


class PublicActivitySerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255, read_only=True)
    project = PublicProjectSerializer(many=False, read_only=True)
    change_rate = api_serializers.get_model_serializer(api_models.ChangeRate)(many=False, read_only=True)
    climate_t2 = api_serializers.get_model_serializer(api_models.Climate)(read_only=True)
    moisture_t2 = api_serializers.get_model_serializer(api_models.Moisture)(read_only=True)
    soil_type_t2 = api_serializers.get_model_serializer(api_models.SoilType)(read_only=True)
    module_types = api_serializers.get_model_serializer(api_models.ModuleType)(many=True, read_only=True)

    class Meta:
        model = api_models.Activity
        fields = ["id", "name", "project", "change_rate", "climate_t2", "moisture_t2", "soil_type_t2", "module_types", "duration_t2", "start_year_t2"]
        ref_name = "Activity"


class PublicActivitySerializerWithModules(PublicActivitySerializer):
    modules = serializers.SerializerMethodField(read_only=True)

    def get_modules(self, obj: api_models.Activity):
        return [get_public_module_serializer(module.__class__)(module, many=False).data for module in obj.modules]

    class Meta:
        model = api_models.Activity
        fields = ["id", "name", "project", "change_rate", "climate_t2", "moisture_t2", "soil_type_t2", "module_types", "duration_t2", "start_year_t2", "modules"]
        ref_name = "ActivityWithModules"


def get_public_module_serializer(model_arg: models.Model) -> serializers.ModelSerializer:
    class GenericPublicModuleSerializer(serializers.ModelSerializer):
        module_type = serializers.SerializerMethodField(read_only=True)
        status = api_serializers.get_model_serializer(api_models.StatusType)(read_only=True)

        class Meta:
            model = model_arg
            fields = "__all__"
            ref_name = model_arg.__name__

        def get_module_type(self, obj):
            try:
                return api_serializers.get_model_serializer(api_models.ModuleType)(obj.module_type, many=False).data
            except api_models.ModuleType.DoesNotExist:
                return None

    try:
        return globals()["Public" + model_arg.__name__ + "Serializer"]
    except KeyError:
        return GenericPublicModuleSerializer
