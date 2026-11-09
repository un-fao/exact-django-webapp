"""Public (anonymous, read-only) serializers.

The frontend renders public projects with the components it uses for private ones, so
every public payload has the private shape: these classes subclass the private
serializers and only drop what an anonymous reader must not see.
"""

from django.db import models
from rest_framework import serializers

import api.models as api_models
import api.serializers as api_serializers


class PublicProjectSerializer(api_serializers.ReadProjectSerializer):
    # Membership role and analyst notes belong to the project team.
    role = None
    note = None

    class Meta(api_serializers.ReadProjectSerializer.Meta):
        fields = None
        exclude = ["owner", "created_at", "updated_at"]


class PublicActivitySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = api_models.Activity
        fields = ["id", "name", "module_types", "completion_percentage"]
        ref_name = "Activity"


class PublicModuleSummarySerializer(api_serializers.ModuleTypeIdModuleIdAreaSerializer):
    urls_module = "public.urls"
    url_prefix = "api/public"


class PublicActivitySerializer(api_serializers.ActivitySerializer):
    class Meta(api_serializers.ActivitySerializer.Meta):
        fields = None
        exclude = ["owner"]


class PublicActivitySerializerWithModules(PublicActivitySerializer):
    modules = serializers.SerializerMethodField(read_only=True)

    def get_modules(self, obj: api_models.Activity):
        return PublicModuleSummarySerializer(obj.modules, many=True).data

    class Meta(PublicActivitySerializer.Meta):
        ref_name = "ActivityWithModules"


def get_public_module_serializer(model_arg: models.Model) -> serializers.ModelSerializer:
    class PublicModuleSerializer(api_serializers.get_module_serializer(model_arg)):
        # Analyst notes belong to the project team.
        note = None

    return PublicModuleSerializer
