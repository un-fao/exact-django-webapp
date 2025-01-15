import django_filters
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model
from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated
from django.apps import apps
from django.shortcuts import render
from django.db.models import Q
from django.db import models
from rest_framework.response import Response


from .serializers import get_model_serializer
from . import models as ipcc_models
import api.models as api_models


class AuthenticatedViewSet:
    permission_classes = [IsAuthenticated]


def generic_viewset(_model: Model):
    class GenericFilterSet(django_filters.FilterSet):
        class Meta:
            model = _model
            fields = "__all__"

    class GenericViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = _model.objects.all()
        serializer_class = get_model_serializer(_model)
        filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
        filterset_class = GenericFilterSet

        def get_queryset(self):

            # If list operation, filter out inactive objects, unless ?filter_inactive=true
            if self.action == "list" and not self.request.query_params.get("filter_inactive") and hasattr(_model, "is_active"):
                try:
                    return self.queryset.filter(is_active=True)
                except FieldDoesNotExist:
                    return super().get_queryset()

            return super().get_queryset()

    concrete_viewset = globals().get(f"{_model.__name__}ViewSet", GenericViewSet)

    return concrete_viewset or GenericViewSet


class CropYieldStatViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    class CropYieldStatFilterSet(django_filters.FilterSet):
        class Meta:
            model = ipcc_models.CropYieldStat
            fields = "__all__"

    queryset = ipcc_models.CropYieldStat.objects.all()
    serializer_class = get_model_serializer(ipcc_models.CropYieldStat)
    filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
    filterset_class = CropYieldStatFilterSet

    def list(self, request, *args, **kwargs):

        land_use_type_id = request.query_params.get("land_use_type")
        continent_id = request.query_params.get("continent")

        if land_use_type_id and not api_models.LandUseType.objects.filter(id=land_use_type_id).exists():
            return Response({"error": "Invalid land_use_type"}, status=400)

        if continent_id and not api_models.Region.objects.filter(id=continent_id).exists():
            return Response({"error": "Invalid continent"}, status=400)

        filters = {}

        if land_use_type_id:
            filters["land_use_type_id"] = land_use_type_id
        if continent_id:
            filters["continent_id"] = continent_id

        crop = self.queryset.filter(**filters).all()
        if not crop and continent_id:
            region_stats = ipcc_models.CropYieldStat.objects.get_or_region_average(land_use_type_id, continent_id)
            result = ipcc_models.CropYieldStat()
            result.land_use_type = api_models.LandUseType.objects.get(id=land_use_type_id)
            result.continent = api_models.Region.objects.get(id=continent_id)
            result.average = region_stats.average
            return Response(self.serializer_class(result).data)

        return Response(self.serializer_class(crop, many=True).data)


def table_list_view(request):
    models = apps.get_app_config("ipcc").get_models()
    models_info = []
    for model in models:
        models_info.append({"verbose_name": model._meta.verbose_name_plural, "model_name": model.__name__})

    context = {"models_info": models_info}
    return render(request, "table_list.html", context)


def table_data_view(request, model_name):
    # Get the model class
    model = apps.get_model("ipcc", model_name)

    # Get field names and verbose names
    fields = [field.name for field in model._meta.fields]
    verbose_fields = [field.verbose_name for field in model._meta.fields]

    # Fetch data for the model
    query_string = request.GET.get("q", "").strip()
    data = model.objects.all()

    if query_string:
        q_object = Q()
        queries = query_string.split()  # Split the query by spaces

        for query in queries:
            sub_q = Q()
            for field in model._meta.fields:
                if isinstance(field, (models.CharField, models.TextField)):
                    sub_q |= Q(**{f"{field.name}__icontains": query})
                elif isinstance(field, (models.FloatField, models.IntegerField)):
                    try:
                        query_value = float(query)
                        sub_q |= Q(**{f"{field.name}": query_value})
                    except ValueError:
                        pass
                elif isinstance(field, models.ForeignKey):
                    sub_q |= Q(**{f"{field.name}__name__icontains": query})
            q_object &= sub_q

        data = model.objects.filter(q_object)

    context = {
        "model_name": model._meta.verbose_name_plural,
        "fields": fields,
        "verbose_fields": verbose_fields,
        "data": data,
        "query": query_string,
    }
    return render(request, "table_data.html", context)
