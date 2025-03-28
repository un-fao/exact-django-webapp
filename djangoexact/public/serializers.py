from rest_framework import serializers

from api.models import Project


class PublicProjectSerializer(serializers.ModelSerializer):
    """
    Serializer for public projects.
    """

    class Meta:
        model = Project
        fields = ["id", "name"]
