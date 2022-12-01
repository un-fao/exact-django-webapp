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

class AfforestationInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = AfforestationInput
        fields = '__all__'

# TODO: Make generic serializer for results

class AffoResultSerializer(serializers.Serializer):
    total_w = serializers.FloatField()
    total_wo = serializers.FloatField()
    balance = serializers.FloatField()

class AffoResultInputSerializer(serializers.Serializer):
    input = AfforestationInputSerializer()
    result = AffoResultSerializer()

class AffoResultsSerializer(serializers.Serializer):
    inputs = AffoResultInputSerializer(many=True)
    result = AffoResultSerializer()

class DefoResultSerializer(serializers.Serializer):
    total_w = serializers.FloatField()
    total_wo = serializers.FloatField()
    balance = serializers.FloatField()

class DefoResultInputSerializer(serializers.Serializer):
    input = DeforestationInputSerializer()
    result = DefoResultSerializer()

class DefoResultsSerializer(serializers.Serializer):
    inputs = DefoResultInputSerializer(many=True)
    result = DefoResultSerializer()