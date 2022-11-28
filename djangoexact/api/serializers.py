from rest_framework import serializers
from .models import *

class ProjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = Project
        fields = '__all__'

class DeforestationInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeforestationInput
        fields = '__all__'

class DefoResultSerializer(serializers.Serializer):
    total_w = serializers.FloatField()
    total_wo = serializers.FloatField()
    balance = serializers.FloatField()

class DefoResultInputSerializer(serializers.Serializer):
    input = DeforestationInputSerializer()
    result = DefoResultSerializer()

class DefoResultsSerializer(serializers.Serializer):
    inputs_emissions_list = DefoResultInputSerializer(many=True)
    result = DefoResultSerializer()