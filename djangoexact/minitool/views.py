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

    def get_filtered_queryset(self, module_type, request, extra_filters=None):
        """Helper method to get filtered queryset for any module."""
        filters = {}
        filter_fields = ["region", "climate", "moisture", "soil_type", "field"]

        # Start with base queryset filtered by module type
        queryset = models.ChangeAggregate.objects.all()

        # Filter by module type using custom_filters
        module_type_mapping = {"livestock": "Livestock", "annual-cropland": "Annual Cropland", "flooded-rice": "Flooded Rice", "grassland": "Grassland"}
        module_type_value = module_type_mapping.get(module_type, module_type)
        queryset = queryset.filter(module_type=module_type_value)

        # Apply standard filters
        for field in filter_fields:
            value = request.query_params.get(field)
            if value:
                filters[field] = value
                if hasattr(queryset.model, field):
                    queryset = queryset.filter(**{field: value})

        # Apply custom filters from custom_filters JSONField
        custom_filters = {}
        for param, value in request.query_params.items():
            # Skip standard filters and other parameters
            if param in filter_fields or param in ["page", "page_size", "format"]:
                continue

            # Check if this is a custom filter by looking at the first record
            if queryset.exists():
                first_record = queryset.first()
                if hasattr(first_record, "custom_filters") and first_record.custom_filters:
                    if param in first_record.custom_filters:
                        custom_filters[param] = value
                        # Filter by JSON field
                        queryset = queryset.filter(**{f"custom_filters__{param}": value})

        # Add custom filters to the filters dict for response
        filters.update(custom_filters)

        return queryset, filters

    def get_available_custom_filters(self, module_type):
        """Get available custom filter fields and their values for a specific module."""
        module_type_mapping = {"livestock": "Livestock", "annual-cropland": "Annual Cropland", "flooded-rice": "Flooded Rice", "grassland": "Grassland"}
        module_type_value = module_type_mapping.get(module_type, module_type)

        queryset = models.ChangeAggregate.objects.filter(module_type=module_type_value)

        if not queryset.exists():
            return {}

        first_record = queryset.first()
        if not hasattr(first_record, "custom_filters") or not first_record.custom_filters:
            return {}

        custom_filters = {}
        for filter_name in first_record.custom_filters.keys():
            # Get distinct values for this custom filter
            values = queryset.exclude(custom_filters__isnull=True).exclude(custom_filters={}).values_list(f"custom_filters__{filter_name}", flat=True).distinct()

            custom_filters[filter_name] = list(values)

        return custom_filters

    def get_fields_with_entries(self, queryset):
        """Helper method to get fields with their unique entries."""
        fields = queryset.values_list("field", flat=True).distinct()

        # Get unique entries for each field
        fields_with_entries = []
        for field in fields:
            # Get unique from_value and to_value entries for this field
            from_values = queryset.filter(field=field).values_list("from_value", flat=True).distinct()
            to_values = queryset.filter(field=field).values_list("to_value", flat=True).distinct()

            # Combine and deduplicate all unique values
            all_values = list(set(list(from_values) + list(to_values)))

            field_data = {"field": field, "unique_entries": sorted(all_values) if all_values else []}
            fields_with_entries.append(field_data)

        return fields_with_entries

    @decorators.action(detail=False, methods=["get"])
    def fields(self, request, *args, **kwargs):
        """
        Get fields for emissions modules data with filtering and aggregation.
        Returns both field names and their unique entries.
        """
        queryset = models.ChangeAggregate.objects.all()
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"])
    def livestock(self, request, *args, **kwargs):
        """
        Get livestock emissions modules data with filtering and aggregation.
        """
        queryset, filters = self.get_filtered_queryset("livestock", request, extra_filters=["livestock_category_type"])

        # Get total count
        total_records = queryset.count()

        if total_records == 0:
            return Response({"error": "No livestock data found", "filters_applied": filters, "total_records_analyzed": 0, "aggregated_results": {}}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate by change
        aggregated_data = self.aggregate_by_change(queryset)

        # Prepare response
        response_data = {"filters_applied": filters, "total_records_analyzed": total_records, "aggregated_results": aggregated_data}

        return Response(response_data)

    @decorators.action(detail=False, methods=["get"], url_path="annual-cropland")
    def annual_cropland(self, request, *args, **kwargs):
        """
        Get annual cropland emissions modules data with filtering and aggregation.
        """
        queryset, filters = self.get_filtered_queryset("annual-cropland", request)

        # Get total count
        total_records = queryset.count()

        if total_records == 0:
            return Response({"error": "No annual cropland data found", "filters_applied": filters, "total_records_analyzed": 0, "aggregated_results": {}}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate by change
        aggregated_data = self.aggregate_by_change(queryset)

        # Prepare response
        response_data = {"filters_applied": filters, "total_records_analyzed": total_records, "aggregated_results": aggregated_data}

        return Response(response_data)

    @decorators.action(detail=False, methods=["get"], url_path="flooded-rice")
    def flooded_rice(self, request, *args, **kwargs):
        """
        Get flooded rice emissions modules data with filtering and aggregation.
        """
        queryset, filters = self.get_filtered_queryset("flooded-rice", request)

        # Get total count
        total_records = queryset.count()

        if total_records == 0:
            return Response({"error": "No flooded rice data found", "filters_applied": filters, "total_records_analyzed": 0, "aggregated_results": {}}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate by change
        aggregated_data = self.aggregate_by_change(queryset)

        # Prepare response
        response_data = {"filters_applied": filters, "total_records_analyzed": total_records, "aggregated_results": aggregated_data}

        return Response(response_data)

    @decorators.action(detail=False, methods=["get"], url_path="grassland")
    def grassland(self, request, *args, **kwargs):
        """
        Get grassland emissions modules data with filtering and aggregation.
        """
        queryset, filters = self.get_filtered_queryset("grassland", request)

        # Get total count
        total_records = queryset.count()

        if total_records == 0:
            return Response({"error": "No grassland data found", "filters_applied": filters, "total_records_analyzed": 0, "aggregated_results": {}}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate by change
        aggregated_data = self.aggregate_by_change(queryset)

        # Prepare response
        response_data = {"filters_applied": filters, "total_records_analyzed": total_records, "aggregated_results": aggregated_data}

        return Response(response_data)

    # Nested actions for livestock module
    @decorators.action(detail=False, methods=["get"], url_path="livestock/fields")
    def livestock_fields(self, request, *args, **kwargs):
        """Get available fields for livestock data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Livestock")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="livestock/categories")
    def livestock_categories(self, request, *args, **kwargs):
        """Get available livestock categories."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Livestock")
        categories = queryset.values_list("custom_filters__livestock_category_type", flat=True).distinct()
        return Response(list(categories))

    @decorators.action(detail=False, methods=["get"], url_path="livestock/regions")
    def livestock_regions(self, request, *args, **kwargs):
        """Get available regions for livestock data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Livestock")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="livestock/custom-filters")
    def livestock_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for livestock data."""
        custom_filters = self.get_available_custom_filters("livestock")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="livestock/statistics")
    def livestock_statistics(self, request, *args, **kwargs):
        """Get overall statistics for livestock data."""
        queryset, filters = self.get_filtered_queryset("livestock", request, extra_filters=["livestock_category_type"])

        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    # Nested actions for annual cropland module
    @decorators.action(detail=False, methods=["get"], url_path="annual-cropland/fields")
    def annual_cropland_fields(self, request, *args, **kwargs):
        """Get available fields for annual cropland data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Annual Cropland")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="annual-cropland/regions")
    def annual_cropland_regions(self, request, *args, **kwargs):
        """Get available regions for annual cropland data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Annual Cropland")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="annual-cropland/custom-filters")
    def annual_cropland_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for annual cropland data."""
        custom_filters = self.get_available_custom_filters("annual-cropland")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="annual-cropland/statistics")
    def annual_cropland_statistics(self, request, *args, **kwargs):
        """Get overall statistics for annual cropland data."""
        queryset, filters = self.get_filtered_queryset("annual-cropland", request)

        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    # Nested actions for flooded rice module
    @decorators.action(detail=False, methods=["get"], url_path="flooded-rice/fields")
    def flooded_rice_fields(self, request, *args, **kwargs):
        """Get available fields for flooded rice data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Flooded Rice")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="flooded-rice/regions")
    def flooded_rice_regions(self, request, *args, **kwargs):
        """Get available regions for flooded rice data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Flooded Rice")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="flooded-rice/custom-filters")
    def flooded_rice_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for flooded rice data."""
        custom_filters = self.get_available_custom_filters("flooded-rice")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="flooded-rice/statistics")
    def flooded_rice_statistics(self, request, *args, **kwargs):
        """Get overall statistics for flooded rice data."""
        queryset, filters = self.get_filtered_queryset("flooded-rice", request)

        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    # Nested actions for grassland module
    @decorators.action(detail=False, methods=["get"], url_path="grassland/fields")
    def grassland_fields(self, request, *args, **kwargs):
        """Get available fields for grassland data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Grassland")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="grassland/regions")
    def grassland_regions(self, request, *args, **kwargs):
        """Get available regions for grassland data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Grassland")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="grassland/custom-filters")
    def grassland_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for grassland data."""
        custom_filters = self.get_available_custom_filters("grassland")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="grassland/statistics")
    def grassland_statistics(self, request, *args, **kwargs):
        """Get overall statistics for grassland data."""
        queryset, filters = self.get_filtered_queryset("grassland", request)

        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    # Cross-module nested actions
    @decorators.action(detail=False, methods=["get"], url_path="compare")
    def compare_modules(self, request, *args, **kwargs):
        """Compare statistics across all modules."""
        modules = request.query_params.get("modules", "livestock,annual-cropland,flooded-rice,grassland").split(",")

        comparison_data = {}

        for module in modules:
            module_type_mapping = {"livestock": "Livestock", "annual-cropland": "Annual Cropland", "flooded-rice": "Flooded Rice", "grassland": "Grassland"}
            module_type_value = module_type_mapping.get(module, module)

            queryset = models.ChangeAggregate.objects.filter(module_type=module_type_value)

            total_records = queryset.count()
            total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
            avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

            comparison_data[module] = {"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact}

        return Response(comparison_data)

    @decorators.action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request, *args, **kwargs):
        """Get summary statistics for all modules."""
        summary_data = {}

        # Livestock summary
        livestock_queryset = models.ChangeAggregate.objects.filter(module_type="Livestock")
        summary_data["livestock"] = {
            "total_records": livestock_queryset.count(),
            "total_changes": livestock_queryset.aggregate(total=Sum("count"))["total"] or 0,
            "unique_categories": livestock_queryset.values("custom_filters__livestock_category_type").distinct().count(),
            "unique_fields": livestock_queryset.values("field").distinct().count(),
        }

        # Annual cropland summary
        annual_queryset = models.ChangeAggregate.objects.filter(module_type="Annual Cropland")
        summary_data["annual_cropland"] = {
            "total_records": annual_queryset.count(),
            "total_changes": annual_queryset.aggregate(total=Sum("count"))["total"] or 0,
            "unique_fields": annual_queryset.values("field").distinct().count(),
        }

        # Flooded rice summary
        flooded_queryset = models.ChangeAggregate.objects.filter(module_type="Flooded Rice")
        summary_data["flooded_rice"] = {
            "total_records": flooded_queryset.count(),
            "total_changes": flooded_queryset.aggregate(total=Sum("count"))["total"] or 0,
            "unique_fields": flooded_queryset.values("field").distinct().count(),
        }

        # Grassland summary
        grassland_queryset = models.ChangeAggregate.objects.filter(module_type="Grassland")
        summary_data["grassland"] = {
            "total_records": grassland_queryset.count(),
            "total_changes": grassland_queryset.aggregate(total=Sum("count"))["total"] or 0,
            "unique_fields": grassland_queryset.values("field").distinct().count(),
        }

        return Response(summary_data)


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
