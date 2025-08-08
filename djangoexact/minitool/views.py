from django.shortcuts import render
from rest_framework.filters import SearchFilter
from rest_framework import views, generics, viewsets, mixins, decorators
from rest_framework.response import Response
from rest_framework import status
import minitool.models as models
import minitool.serializers as serializers
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from django.db.models import JSONField, Sum, F, Avg, Min, Max, Q
from rest_framework.pagination import PageNumberPagination
import api.models as api_models
import statistics
from collections import defaultdict
from typing import Dict, List, Any


class DefaultPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 10000


class EmissionsModulesViewSet(viewsets.GenericViewSet):
    """
    ViewSet for emissions modules data with filtering and aggregation capabilities.
    """

    def calculate_statistics(self, values: List[float]) -> Dict[str, float]:
        """Calculate statistical measures for a list of values."""
        if not values:
            return {"count": 0, "sum": 0, "mean": 0, "median": 0, "min": 0, "max": 0, "q1": 0, "q3": 0}

        sorted_values = sorted(values)
        n = len(sorted_values)

        q1_idx = n // 4
        q3_idx = 3 * n // 4

        return {
            "count": n,
            "sum": sum(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "q1": sorted_values[q1_idx] if n > 0 else 0,
            "q3": sorted_values[q3_idx] if n > 0 else 0,
        }

    def aggregate_by_change(self, queryset) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate data by change type with structured output using database queries.
        """
        # Get all unique fields
        fields = queryset.values_list("field", flat=True).distinct()

        results = []
        for field in fields:
            field_data = {"field": field, "changes": []}

            # Get all changes for this field
            field_changes = (
                queryset.filter(field=field)
                .values("from_value", "to_value")
                .annotate(count=Sum("count"), sum_total=Sum("sum_total"), mean=Avg("mean"), median=Avg("median"), min_value=Min("min_value"), max_value=Max("max_value"), q1=Avg("q1"), q3=Avg("q3"))
            )

            for change in field_changes:
                change_data = {
                    "from": change["from_value"],
                    "to": change["to_value"],
                    "statistics": {
                        "count": change["count"],
                        "sum": change["sum_total"],
                        "mean": change["mean"],
                        "median": change["median"],
                        "min": change["min_value"],
                        "max": change["max_value"],
                        "q1": change["q1"],
                        "q3": change["q3"],
                    },
                }
                field_data["changes"].append(change_data)

            # Sort changes by count (descending)
            field_data["changes"].sort(key=lambda x: x["statistics"]["count"], reverse=True)
            results.append(field_data)

        return results

    @decorators.action(detail=False, methods=["get"])
    def livestock(self, request, *args, **kwargs):
        """
        Get livestock emissions modules data with filtering and aggregation.
        """
        # Get filter parameters from query params
        filters = {}
        filter_fields = ["region", "climate", "moisture", "soil_type", "livestock_category_type", "field"]

        for field in filter_fields:
            value = request.query_params.get(field)
            if value:
                filters[field] = value

        # Start with base queryset
        queryset = models.LivestockChangeAggregate.objects.all()

        # Apply filters
        if filters.get("region"):
            queryset = queryset.filter(region=filters["region"])
        if filters.get("climate"):
            queryset = queryset.filter(climate=filters["climate"])
        if filters.get("moisture"):
            queryset = queryset.filter(moisture=filters["moisture"])
        if filters.get("soil_type"):
            queryset = queryset.filter(soil_type=filters["soil_type"])
        if filters.get("livestock_category_type"):
            queryset = queryset.filter(livestock_category_type=filters["livestock_category_type"])
        if filters.get("field"):
            queryset = queryset.filter(field=filters["field"])

        # Get total count
        total_records = queryset.count()

        if total_records == 0:
            return Response({"error": "No livestock data found", "filters_applied": filters, "total_records_analyzed": 0, "aggregated_results": {}}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate by change
        aggregated_data = self.aggregate_by_change(queryset)

        # Prepare response
        response_data = {"filters_applied": filters, "total_records_analyzed": total_records, "aggregated_results": aggregated_data}

        return Response(response_data)


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

        aggregate_by = request.query_params.get("aggregate_by", None)
        aggregate_field = request.query_params.get("aggregate_field", None)

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


class EmissionStatisticsByModuleViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    class GenericFilterSet(django_filters.FilterSet):
        class Meta:
            model = models.EmissionStatisticsByModule
            fields = "__all__"
            filter_overrides = {
                JSONField: {
                    "filter_class": django_filters.CharFilter,
                },
            }

    class MultipleModuleFilter(django_filters.FilterSet):
        class Meta:
            model = models.EmissionStatisticsByModule
            fields = "__all__"
            filter_overrides = {
                JSONField: {
                    "filter_class": django_filters.CharFilter,
                },
            }

        module_type = django_filters.CharFilter(method="filter_module_type")

        def filter_module_type(self, queryset, name, value):
            return queryset.filter(module_type__in=value.split(","))

    queryset = models.EmissionStatisticsByModule.objects.all()
    serializer_class = serializers.EmissionStatisticsByModuleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = MultipleModuleFilter
    search_fields = ["module_type", "region", "climate", "moisture", "soil_type"]

    @decorators.action(detail=False, methods=["get"])
    def aggregate(self, request, *args, **kwargs):
        queryset = self.queryset
        queryset = self.filter_queryset(queryset)

        country = request.query_params.get("country", None)
        if country:
            region = api_models.Country.objects.get(name=country).region
            queryset = queryset.filter(region=region)

        by = request.query_params.get("by", None)

        results = []
        aggregates = queryset.values_list(by, flat=True).distinct()
        for aggregate in aggregates:
            data = {by: aggregate, "statistics": {}}

            filtered_queryset = queryset.filter(**{by: aggregate})

            # Calculate aggregate statistics
            stats = filtered_queryset.aggregate(
                total_count=Sum("count"), total_sum=Sum("total"), avg_mean=Avg("mean"), avg_median=Avg("median"), min_val=Min("min"), max_val=Max("max"), avg_q1=Avg("q1"), avg_q3=Avg("q3")
            )

            data["statistics"] = {
                "count": stats["total_count"],
                "sum": stats["total_sum"],
                "mean": stats["avg_mean"],
                "median": stats["avg_median"],
                "min": stats["min_val"],
                "max": stats["max_val"],
                "q1": stats["avg_q1"],
                "q3": stats["avg_q3"],
            }

            results.append(data)

        return Response(results)
