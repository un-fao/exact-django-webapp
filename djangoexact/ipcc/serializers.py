from rest_framework import serializers
import ipcc.utilities as utils

# Template class for serializing


def get_model_serializer(model_arg):
    class GenericSerializer(serializers.ModelSerializer):
        data_url = serializers.SerializerMethodField()

        def get_data_url(self, obj):
            return f"api/ipcc/data/{model_arg.__name__.lower()}/?q={obj.id}"

        class Meta:
            model = model_arg
            fields = "__all__"
            ref_name = model_arg.__name__

    return GenericSerializer
