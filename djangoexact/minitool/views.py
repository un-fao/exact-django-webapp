from django.shortcuts import render
from rest_framework import views, generics, viewsets, mixins, decorators
from rest_framework.response import Response
from rest_framework import status
import minitool.models as models
import minitool.serializers as serializers
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from django.db.models import JSONField, Sum, F
from rest_framework.pagination import PageNumberPagination
import api.models as api_models


class DefaultPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 10000


class EntryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    class GenericFilterSet(django_filters.FilterSet):
        class Meta:
            model = models.Entry
            fields = "__all__"
            filter_overrides = {
                JSONField: {
                    "filter_class": django_filters.CharFilter,
                },
            }

    queryset = models.Entry.objects.all()
    serializer_class = serializers.EntrySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = GenericFilterSet

    def list(self, request, *args, **kwargs):
        queryset = self.queryset
        queryset = self.filter_queryset(queryset)

        country = request.query_params.get("country", None)
        if country:
            region = api_models.Country.objects.get(name=country).region
            queryset = queryset.filter(region=region)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = serializers.EntrySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = serializers.EntrySerializer(queryset, many=True)
        return Response(serializer.data)


class StatisticsModuleTotalViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    class GenericFilterSet(django_filters.FilterSet):
        class Meta:
            model = models.StatisticsModuleTotal
            fields = "__all__"
            filter_overrides = {
                JSONField: {
                    "filter_class": django_filters.CharFilter,
                },
            }

    queryset = models.StatisticsModuleTotal.objects.all()
    serializer_class = serializers.StatisticsModuleTotalSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = GenericFilterSet

    @decorators.action(detail=False, methods=["get"])
    def aggregate(self, request, *args, **kwargs):
        queryset = self.queryset
        queryset = self.filter_queryset(queryset)

        results = []
        module_types = queryset.values_list("module_type", flat=True).distinct()
        for module_type in module_types:
            data = {
                "module_type": module_type,
                "practices": [],
            }
            for field in queryset.filter(module_type=module_type).values_list("field", flat=True).distinct():
                field_data = queryset.filter(module_type=module_type, field=field).values("from_value", "to_value").annotate(total=Sum("mean"))
                data["practices"].append(
                    {
                        "field": field,
                        "total": field_data.aggregate(total=Sum("mean"))["total"],
                        "changes": list(field_data),
                    }
                )
            results.append(data)

        return Response(results)
