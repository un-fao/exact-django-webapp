from rest_framework import serializers
from .models import *

class ProjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = Project
        fields = '__all__'

# TODO: Make generic serializer for results


def getGenericResultsSerializer(model_arg):

    class ResultSerializer(serializers.Serializer):
        total_w = serializers.FloatField()
        total_wo = serializers.FloatField()
        balance = serializers.FloatField()

    class GenericSerializer(serializers.ModelSerializer):
        class Meta:
            model = model_arg
            fields = '__all__'

    class GenericResultInputsSerializer(serializers.Serializer):
        input = GenericSerializer()
        result = ResultSerializer()

    class GenericResultsSerializer(serializers.Serializer):
        inputs = GenericResultInputsSerializer(many=True)
        result = ResultSerializer()

    return GenericResultsSerializer

def getGenericSerializer(model_arg):
    class GenericSerializer(serializers.ModelSerializer):
        class Meta:
            model = model_arg
            fields = '__all__'

    return GenericSerializer