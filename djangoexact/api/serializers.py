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

def getModelSerializer(model_arg):
    class GenericSerializer(serializers.ModelSerializer):
        class Meta:
            model = model_arg
            fields = '__all__'

    return GenericSerializer

def getAssessmentSerializer(model_arg):
    class AssessmentSerializer(serializers.Serializer):
        parent_name = serializers.CharField(max_length=200)
        parent_id = serializers.IntegerField()
        assessment = getModelSerializer(model_arg)()

        def save(self):
            self.assessment.save()
            return self.assessment

    return AssessmentSerializer