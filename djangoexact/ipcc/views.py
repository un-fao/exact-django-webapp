import django_filters
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model
from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated
from django.apps import apps
from django.shortcuts import render
from django.db.models import Q
from django.db import models


from .serializers import get_model_serializer


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
            if self.action == "list" and not self.request.query_params.get("filter_inactive"):
                try:
                    is_active_field = self.queryset.model._meta.get_field("is_active")
                    return self.queryset.filter(is_active=True)
                except FieldDoesNotExist:
                    return super().get_queryset()

            return super().get_queryset()

    return GenericViewSet


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
