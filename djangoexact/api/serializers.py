from rest_framework import serializers
from .models import *

class ResultSerializer(serializers.Serializer):
    total_w = serializers.FloatField()
    total_wo = serializers.FloatField()
    balance = serializers.FloatField()

def get_model_serializer(model_arg):
    class GenericSerializer(serializers.ModelSerializer):
        class Meta:
            model = model_arg
            fields = '__all__'
            ref_name = model_arg.__name__
    return GenericSerializer

def get_module_serializer(model_arg):
    class GenericSerializer(serializers.ModelSerializer):

        # activity = serializers.PrimaryKeyRelatedField(source='activity.name', queryset=Activity.objects.all(), many=False)

        class Meta:
            model = model_arg
            fields = '__all__'
            ref_name = model_arg.__name__

    return GenericSerializer