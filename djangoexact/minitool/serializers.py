import minitool.models as models
from rest_framework import serializers


class EntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Entry
        fields = ["module_type", "region", "climate", "moisture", "soil_type", "total", "changes"]
