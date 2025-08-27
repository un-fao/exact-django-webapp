import minitool.models as models
from rest_framework import serializers


class EntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Entry
        fields = ["module_type", "region", "climate", "moisture", "soil_type", "total", "changes"]


class StatisticsModuleTotalSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StatisticsModuleTotal
        fields = ["id", "module_type", "field", "from_value", "to_value", "mean", "median", "min", "max", "q1", "q3"]


class StatisticsModuleTotalAggregateSerializer(serializers.Serializer):
    module_type = serializers.CharField()
    field = serializers.CharField()
    total = serializers.FloatField()


class EmissionStatisticsByModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EmissionStatisticsByModule
        fields = "__all__"


class EmissionScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EmissionScenario
        fields = "__all__"


class EmissionScenarioWithResultsSerializer(serializers.Serializer):
    emission_scenario = EmissionScenarioSerializer()
    count = serializers.IntegerField()
    sum_total = serializers.FloatField(allow_null=True)
    mean = serializers.FloatField(allow_null=True)
    median = serializers.FloatField(allow_null=True)
    min = serializers.FloatField(allow_null=True)
    max = serializers.FloatField(allow_null=True)
    std = serializers.FloatField(allow_null=True)
    q1 = serializers.FloatField(allow_null=True)
    q3 = serializers.FloatField(allow_null=True)
    iqr = serializers.FloatField(allow_null=True)
    ci_95 = serializers.FloatField(allow_null=True)
    ci_99 = serializers.FloatField(allow_null=True)
    range_min = serializers.FloatField(allow_null=True)
    range_max = serializers.FloatField(allow_null=True)
