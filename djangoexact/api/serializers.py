from rest_framework import serializers
from .models import *

def getResultSerializer():
    class ResultSerializer(serializers.Serializer):
        total_w = serializers.FloatField()
        total_wo = serializers.FloatField()
        balance = serializers.FloatField()
    
    return ResultSerializer

def getResultsSerializer(model_arg):

    class GenericSerializer(serializers.ModelSerializer):
        class Meta:
            model = model_arg
            fields = '__all__'

    class GenericResultInputsSerializer(serializers.Serializer):
        input = GenericSerializer()
        result = getResultSerializer()

    class GenericResultsSerializer(serializers.Serializer):
        inputs = GenericResultInputsSerializer(many=True)
        result = getResultSerializer()

    return GenericResultsSerializer

def get_model_serializer(model_arg):
    class GenericSerializer(serializers.ModelSerializer):
        class Meta:
            model = model_arg
            fields = '__all__'
            ref_name = model_arg.__name__

    return GenericSerializer