import django_filters as filters
from .models import FuelType, SoilType
from django.db.models import Q, CharField, TextField, FloatField, IntegerField, ForeignKey
from rest_framework.filters import BaseFilterBackend


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

class SoilTypeFilter(filters.FilterSet):
    active = filters.BooleanFilter(field_name='active', initial=True)
    is_coastal = filters.BooleanFilter(field_name='is_coastal', initial=False)

    class Meta:
        model = SoilType
        fields = ['active', 'is_coastal']

class AllFieldsSearchFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        search_terms = request.query_params.getlist('s')  # Get multiple values for 'search'
        if not search_terms:
            return queryset

        search_fields = getattr(view, 'search_fields', None)
        if search_fields is None:
            # Automatically discover applicable fields
            model = queryset.model
            search_fields = []
            for field in model._meta.fields:
                if isinstance(field, (CharField, TextField)):
                    search_fields.append(field.name)
                elif isinstance(field, (FloatField, IntegerField)):
                    search_fields.append(field.name)
                elif isinstance(field, ForeignKey):
                    search_fields.append(f"{field.name}__name")

        query = Q()
        for search_term in search_terms:
            term_query = Q()
            for field in search_fields:
                try:
                    # Attempt numeric match for numeric fields
                    query_value = float(search_term)
                    term_query |= Q(**{f"{field}": query_value})
                except ValueError:
                    term_query |= Q(**{f"{field}__icontains": search_term})
            query |= term_query  # Combine all conditions for the current term

        return queryset.filter(query)