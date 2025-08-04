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
