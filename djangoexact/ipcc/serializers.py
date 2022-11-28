from rest_framework import serializers

# Template class for serializing
class GeneralSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'