import django_filters as filters
from .models import FuelType
from django.db.models import Q


def get_model_filter(model_arg):
    class GenericModelFilter(filters.FilterSet):

        class Meta:
            model = model_arg
            fields = "__all__"

    try:
        return globals()[f"{model_arg.__name__}Filter"]
    except KeyError:
        return GenericModelFilter

class FuelTypeFilter(filters.FilterSet):
    fuel_use_type = filters.CharFilter(
        field_name='fuel_use_type', method='filter_fuel_use_type'
    )

    def filter_fuel_use_type(self, queryset, name, value):
        # Split the comma-separated values
        fuel_use_types = value.split(',')
        query = Q()
        for fuel_use_type in fuel_use_types:
            query |= Q(**{f"{name}__name__iexact": fuel_use_type.strip()})
        return queryset.filter(query)

    class Meta:
        model = FuelType
        fields = ['fuel_use_type']