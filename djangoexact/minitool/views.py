from rest_framework.filters import SearchFilter
from rest_framework import viewsets, mixins, decorators
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
import minitool.models as models
import minitool.serializers as serializers
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from django.db.models import JSONField, Sum, Avg, Min, Max, Q, Count, FloatField, StdDev, Aggregate
import logging

# Deliberately avoid importing connection at module level; imported where needed
from django.db.utils import NotSupportedError, ProgrammingError
from django.contrib.postgres.aggregates.mixins import OrderableAggMixin
from django.core.cache import cache
from rest_framework.pagination import PageNumberPagination
import api.models as api_models
import statistics
from collections import defaultdict  # noqa: F401 (kept if needed for future use)
from typing import Dict, List, Any
from functools import wraps
from .db_manager import cleanup_connections, get_connection_info


def close_db_connections(view_func):
    """Decorator to ensure database connections are closed after view execution."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        try:
            return view_func(*args, **kwargs)
        finally:
            # Close all database connections
            from django.db import connections

            connections.close_all()

    return wrapper


class PercentileCont(OrderableAggMixin, Aggregate):
    """
    Cross-database percentile calculation aggregate.
    Uses PostgreSQL's PERCENTILE_CONT for PostgreSQL and optimized Python calculation for SQLite.
    """

    function = "PERCENTILE_CONT"
    name = "PercentileCont"
    default_ordering = "ASC"
    output_field = FloatField()
    template = "%(function)s(%(percentile)s) WITHIN GROUP (ORDER BY %(expressions)s)"

    def __init__(self, expression, percentile, **extra):
        super().__init__(expression, percentile=percentile, **extra)

    def convert_value(self, value, expression, connection):  # noqa: F811 (shadowed name by design)
        return float(value) if value is not None else None

    def as_sql(self, compiler, connection, **extra_context):  # noqa: F811
        if connection.vendor == "postgresql":
            # Use PostgreSQL's native PERCENTILE_CONT. The SQL is produced entirely
            # by Django's ORM compiler from the static Aggregate template above:
            # no user input reaches this expression's SQL.
            # nosemgrep: python.django.security.audit.custom-expression-as-sql.custom-expression-as-sql, python.django.security.injection.tainted-sql-string.tainted-sql-string
            return super().as_sql(compiler, connection, **extra_context)
        else:
            # For non-PostgreSQL databases, raise NotSupportedError to trigger optimized fallback
            from django.db.utils import NotSupportedError

            raise NotSupportedError("PERCENTILE_CONT is not supported on this database backend")


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
        try:
            # Get all unique fields
            fields = queryset.values_list("field", flat=True).distinct()

            results = []
            for field in fields:
                field_data = {"field": field, "changes": []}

                # Get all changes for this field
                field_changes = (
                    queryset.filter(field=field)
                    .values("from_value", "to_value")
                    .annotate(
                        count=Sum("count"), sum_total=Sum("sum_total"), mean=Avg("mean"), median=Avg("median"), min_value=Min("min_value"), max_value=Max("max_value"), q1=Avg("q1"), q3=Avg("q3")
                    )
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
        finally:
            # Ensure connections are cleaned up after heavy aggregation
            cleanup_connections()

    def get_filtered_queryset(self, module_type, request, extra_filters=None):
        """Helper method to get filtered queryset for any module."""
        filters = {}
        filter_fields = ["country", "climate", "moisture", "soil_type", "field"]

        # Start with base queryset filtered by module type
        queryset = models.ChangeAggregate.objects.all()

        # Filter by module type using custom_filters
        module_type_mapping = {
            "livestock": "Livestock",
            "annual-cropland": "Annual Cropland",
            "flooded-rice": "Flooded Rice",
            "grassland": "Grassland",
            "perennial-cropland": "Perennial Cropland",
            "forest-management": "Forest Management",
            "small-fishery": "Small Fishery",
            "large-fishery": "Large Fishery",
            "waterbody": "Waterbody",
        }
        module_type_value = module_type_mapping.get(module_type, module_type)
        queryset = queryset.filter(module_type=module_type_value)

        # Apply standard filters
        for field in filter_fields:
            value = request.query_params.get(field)
            if value:
                filters[field] = value
                if field == "country":
                    country = api_models.Country.objects.get(name=value)
                    queryset = queryset.filter(region=country.region)
                elif hasattr(queryset.model, field):
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
        module_type_mapping = {
            "livestock": "Livestock",
            "annual-cropland": "Annual Cropland",
            "flooded-rice": "Flooded Rice",
            "grassland": "Grassland",
            "perennial-cropland": "Perennial Cropland",
            "waterbody": "Waterbody",
            "forest-management": "Forest Management",
            "small-fishery": "Small Fishery",
            "large-fishery": "Large Fishery",
        }
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

    def get_filters_with_entries(self, queryset, custom_only=False):
        """Helper method to get filters with their unique entries."""
        filters_with_entries = {}

        # Standard filters (only include if custom_only is False)
        if not custom_only:
            standard_filters = ["country", "climate", "moisture", "soil_type"]
            for filter_name in standard_filters:
                if filter_name == "country":
                    values = api_models.Country.objects.values_list("name", flat=True).distinct()
                else:
                    values = queryset.values_list(filter_name, flat=True).distinct()
                filters_with_entries[filter_name] = sorted(list(values)) if values else []

        # Custom filters
        if queryset.exists():
            first_record = queryset.first()
            if hasattr(first_record, "custom_filters") and first_record.custom_filters:
                for filter_name in first_record.custom_filters.keys():
                    # Exclude module from custom filter list
                    if filter_name == "module":
                        continue
                    values = queryset.exclude(custom_filters__isnull=True).exclude(custom_filters={}).values_list(f"custom_filters__{filter_name}", flat=True).distinct()
                    values = list(filter(lambda x: x is not None, values))
                    filters_with_entries[filter_name] = sorted(list(values)) if values else []

        return filters_with_entries

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
    def filters(self, request, *args, **kwargs):
        """
        Get filters for emissions modules data with filtering and aggregation.
        Returns both standard filters and custom filters with their unique entries.

        Query parameters:
        - custom_only: If 'true', returns only custom module filters (default: false)
        """
        queryset = models.ChangeAggregate.objects.all()
        custom_only = request.query_params.get("custom_only", "false").lower() == "true"
        filters_with_entries = self.get_filters_with_entries(queryset, custom_only=custom_only)
        return Response(filters_with_entries)

    @decorators.action(detail=False, methods=["get"])
    def types(self, request, *args, **kwargs):
        """
        Get available module types in statistics/modules.
        Returns a list of all available module types with their details.
        """
        # Cache settings
        cache_key = "minitool_module_types"
        cache_timeout = 60 * 15  # 15 minutes

        # Try to get cached data first
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        # Get all unique module types from the database
        module_types = models.ChangeAggregate.objects.values_list("module_type", flat=True).distinct()

        # Build response with dynamic module information
        available_modules = []
        for module_type in module_types:
            # Get module-specific queryset
            queryset = models.ChangeAggregate.objects.filter(module_type=module_type)

            # Generate dynamic module ID (convert to lowercase, replace spaces with hyphens)
            module_id = module_type.lower().replace(" ", "-")

            # Get custom filters dynamically
            custom_filters = []
            if queryset.exists():
                first_record = queryset.first()
                if hasattr(first_record, "custom_filters") and first_record.custom_filters:
                    custom_filters = list(first_record.custom_filters.keys())

            # Get all available filters for this module
            available_filters = list(self.get_filters_with_entries(queryset, custom_only=False).keys())

            # Build module data dynamically
            module_data = {
                "id": module_id,
                "name": module_type,
                "display_name": module_type,
                "description": f"{module_type} emissions and management data",
                "has_custom_filters": len(custom_filters) > 0,
                "custom_filters": custom_filters,
                "endpoint": f"/statistics/modules/{module_id}/",
                "total_records": queryset.count(),
                "total_changes": queryset.aggregate(total=Sum("count"))["total"] or 0,
                "unique_fields": queryset.values("field").distinct().count(),
                "unique_regions": queryset.values("region").distinct().count(),
                "available_filters": available_filters,
            }

            available_modules.append(module_data)

        response_data = {"available_modules": available_modules, "total_modules": len(available_modules), "modules": [module["id"] for module in available_modules]}

        # Cache the response data
        cache.set(cache_key, response_data, cache_timeout)

        return Response(response_data)

    @decorators.action(detail=False, methods=["get"])
    @close_db_connections
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
    @close_db_connections
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
    @close_db_connections
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
    @close_db_connections
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

    @decorators.action(detail=False, methods=["get"], url_path="perennial-cropland")
    @close_db_connections
    def perennial_cropland(self, request, *args, **kwargs):
        """
        Get perennial cropland emissions modules data with filtering and aggregation.
        """
        queryset, filters = self.get_filtered_queryset("perennial-cropland", request)

        # Get total count
        total_records = queryset.count()

        if total_records == 0:
            return Response({"error": "No perennial cropland data found", "filters_applied": filters, "total_records_analyzed": 0, "aggregated_results": {}}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate by change
        aggregated_data = self.aggregate_by_change(queryset)

        # Prepare response
        response_data = {"filters_applied": filters, "total_records_analyzed": total_records, "aggregated_results": aggregated_data}

        return Response(response_data)

    @decorators.action(detail=False, methods=["get"], url_path="forest-management")
    @close_db_connections
    def forest_management(self, request, *args, **kwargs):
        """
        Get forest management emissions modules data with filtering and aggregation.
        """
        queryset, filters = self.get_filtered_queryset("forest-management", request)

        # Get total count
        total_records = queryset.count()

        if total_records == 0:
            return Response({"error": "No forest management data found", "filters_applied": filters, "total_records_analyzed": 0, "aggregated_results": {}}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate by change
        aggregated_data = self.aggregate_by_change(queryset)

        # Prepare response
        response_data = {"filters_applied": filters, "total_records_analyzed": total_records, "aggregated_results": aggregated_data}

        return Response(response_data)

    @decorators.action(detail=False, methods=["get"], url_path="small-fishery")
    @close_db_connections
    def small_fishery(self, request, *args, **kwargs):
        """
        Get small fishery emissions modules data with filtering and aggregation.
        """
        queryset, filters = self.get_filtered_queryset("small-fishery", request)

        # Get total count
        total_records = queryset.count()

        if total_records == 0:
            return Response({"error": "No small fishery data found", "filters_applied": filters, "total_records_analyzed": 0, "aggregated_results": {}}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate by change
        aggregated_data = self.aggregate_by_change(queryset)

        # Prepare response
        response_data = {"filters_applied": filters, "total_records_analyzed": total_records, "aggregated_results": aggregated_data}

        return Response(response_data)

    @decorators.action(detail=False, methods=["get"], url_path="large-fishery")
    @close_db_connections
    def large_fishery(self, request, *args, **kwargs):
        """
        Get large fishery emissions modules data with filtering and aggregation.
        """
        queryset, filters = self.get_filtered_queryset("large-fishery", request)

        # Get total count
        total_records = queryset.count()

        if total_records == 0:
            return Response({"error": "No large fishery data found", "filters_applied": filters, "total_records_analyzed": 0, "aggregated_results": {}}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate by change
        aggregated_data = self.aggregate_by_change(queryset)

        # Prepare response
        response_data = {"filters_applied": filters, "total_records_analyzed": total_records, "aggregated_results": aggregated_data}

        return Response(response_data)

    @decorators.action(detail=False, methods=["get"], url_path="waterbody")
    @close_db_connections
    def waterbody(self, request, *args, **kwargs):
        """
        Get waterbody emissions modules data with filtering and aggregation.
        """
        queryset, filters = self.get_filtered_queryset("waterbody", request)

        # Get total count
        total_records = queryset.count()

        if total_records == 0:
            return Response({"error": "No waterbody data found", "filters_applied": filters, "total_records_analyzed": 0, "aggregated_results": {}}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate by change
        aggregated_data = self.aggregate_by_change(queryset)

        # Prepare response
        response_data = {"filters_applied": filters, "total_records_analyzed": total_records, "aggregated_results": aggregated_data}

        return Response(response_data)

    ##### FIELDS #####

    # Nested actions for livestock module
    @decorators.action(detail=False, methods=["get"], url_path="livestock/fields")
    def livestock_fields(self, request, *args, **kwargs):
        """Get available fields for livestock data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Livestock")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="annual-cropland/fields")
    def annual_cropland_fields(self, request, *args, **kwargs):
        """Get available fields for annual cropland data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Annual Cropland")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="flooded-rice/fields")
    def flooded_rice_fields(self, request, *args, **kwargs):
        """Get available fields for flooded rice data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Flooded Rice")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="grassland/fields")
    def grassland_fields(self, request, *args, **kwargs):
        """Get available fields for grassland data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Grassland")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="perennial-cropland/fields")
    def perennial_cropland_fields(self, request, *args, **kwargs):
        """Get available fields for perennial cropland data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Perennial Cropland")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="forest-management/fields")
    def forest_management_fields(self, request, *args, **kwargs):
        """Get available fields for forest management data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Forest Management")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="small-fishery/fields")
    def small_fishery_fields(self, request, *args, **kwargs):
        """Get available fields for small fishery data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Small Fishery")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="large-fishery/fields")
    def large_fishery_fields(self, request, *args, **kwargs):
        """Get available fields for large fishery data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Large Fishery")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="waterbody/fields")
    def waterbody_fields(self, request, *args, **kwargs):
        """Get available fields for waterbody data with their unique entries."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Waterbody")
        fields_with_entries = self.get_fields_with_entries(queryset)
        return Response(fields_with_entries)

    ##### FILTERS #####

    @decorators.action(detail=False, methods=["get"], url_path="livestock/filters")
    def livestock_filters(self, request, *args, **kwargs):
        """
        Get available filters for livestock data with their unique entries.

        Query parameters:
        - custom_only: If 'true', returns only custom module filters (default: false)
        """
        queryset = models.ChangeAggregate.objects.filter(module_type="Livestock")
        custom_only = request.query_params.get("custom_only", "false").lower() == "true"
        filters_with_entries = self.get_filters_with_entries(queryset, custom_only=custom_only)
        return Response(filters_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="annual-cropland/filters")
    def annual_cropland_filters(self, request, *args, **kwargs):
        """
        Get available filters for annual cropland data with their unique entries.
        """
        queryset = models.ChangeAggregate.objects.filter(module_type="Annual Cropland")
        custom_only = request.query_params.get("custom_only", "false").lower() == "true"
        filters_with_entries = self.get_filters_with_entries(queryset, custom_only=custom_only)
        return Response(filters_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="flooded-rice/filters")
    def flooded_rice_filters(self, request, *args, **kwargs):
        """
        Get available filters for flooded rice data with their unique entries.
        """
        queryset = models.ChangeAggregate.objects.filter(module_type="Flooded Rice")
        custom_only = request.query_params.get("custom_only", "false").lower() == "true"
        filters_with_entries = self.get_filters_with_entries(queryset, custom_only=custom_only)
        return Response(filters_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="grassland/filters")
    def grassland_filters(self, request, *args, **kwargs):
        """
        Get available filters for grassland data with their unique entries.
        """
        queryset = models.ChangeAggregate.objects.filter(module_type="Grassland")
        custom_only = request.query_params.get("custom_only", "false").lower() == "true"
        filters_with_entries = self.get_filters_with_entries(queryset, custom_only=custom_only)
        return Response(filters_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="perennial-cropland/filters")
    def perennial_cropland_filters(self, request, *args, **kwargs):
        """
        Get available filters for perennial cropland data with their unique entries.
        """
        queryset = models.ChangeAggregate.objects.filter(module_type="Perennial Cropland")
        custom_only = request.query_params.get("custom_only", "false").lower() == "true"
        filters_with_entries = self.get_filters_with_entries(queryset, custom_only=custom_only)
        return Response(filters_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="forest-management/filters")
    def forest_management_filters(self, request, *args, **kwargs):
        """
        Get available filters for forest management data with their unique entries.
        """
        queryset = models.ChangeAggregate.objects.filter(module_type="Forest Management")
        custom_only = request.query_params.get("custom_only", "false").lower() == "true"
        filters_with_entries = self.get_filters_with_entries(queryset, custom_only=custom_only)
        return Response(filters_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="small-fishery/filters")
    def small_fishery_filters(self, request, *args, **kwargs):
        """
        Get available filters for small fishery data with their unique entries.
        """
        queryset = models.ChangeAggregate.objects.filter(module_type="Small Fishery")
        custom_only = request.query_params.get("custom_only", "false").lower() == "true"
        filters_with_entries = self.get_filters_with_entries(queryset, custom_only=custom_only)
        return Response(filters_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="large-fishery/filters")
    def large_fishery_filters(self, request, *args, **kwargs):
        """
        Get available filters for large fishery data with their unique entries.
        """
        queryset = models.ChangeAggregate.objects.filter(module_type="Large Fishery")
        custom_only = request.query_params.get("custom_only", "false").lower() == "true"
        filters_with_entries = self.get_filters_with_entries(queryset, custom_only=custom_only)
        return Response(filters_with_entries)

    @decorators.action(detail=False, methods=["get"], url_path="waterbody/filters")
    def waterbody_filters(self, request, *args, **kwargs):
        """
        Get available filters for waterbody data with their unique entries.
        """
        queryset = models.ChangeAggregate.objects.filter(module_type="Waterbody")
        custom_only = request.query_params.get("custom_only", "false").lower() == "true"
        filters_with_entries = self.get_filters_with_entries(queryset, custom_only=custom_only)
        return Response(filters_with_entries)

    ##### REGIONS #####

    @decorators.action(detail=False, methods=["get"], url_path="livestock/regions")
    def livestock_regions(self, request, *args, **kwargs):
        """Get available regions for livestock data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Livestock")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="annual-cropland/regions")
    def annual_cropland_regions(self, request, *args, **kwargs):
        """Get available regions for annual cropland data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Annual Cropland")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="flooded-rice/regions")
    def flooded_rice_regions(self, request, *args, **kwargs):
        """Get available regions for flooded rice data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Flooded Rice")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="grassland/regions")
    def grassland_regions(self, request, *args, **kwargs):
        """Get available regions for grassland data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Grassland")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="perennial-cropland/regions")
    def perennial_cropland_regions(self, request, *args, **kwargs):
        """Get available regions for perennial cropland data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Perennial Cropland")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="forest-management/regions")
    def forest_management_regions(self, request, *args, **kwargs):
        """Get available regions for forest management data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Forest Management")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="small-fishery/regions")
    def small_fishery_regions(self, request, *args, **kwargs):
        """Get available regions for small fishery data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Small Fishery")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="large-fishery/regions")
    def large_fishery_regions(self, request, *args, **kwargs):
        """Get available regions for large fishery data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Large Fishery")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    @decorators.action(detail=False, methods=["get"], url_path="waterbody/regions")
    def waterbody_regions(self, request, *args, **kwargs):
        """Get available regions for waterbody data."""
        queryset = models.ChangeAggregate.objects.filter(module_type="Waterbody")
        regions = queryset.values_list("region", flat=True).distinct()
        return Response(list(regions))

    ##### CUSTOM FILTERS #####

    @decorators.action(detail=False, methods=["get"], url_path="livestock/custom-filters")
    def livestock_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for livestock data."""
        custom_filters = self.get_available_custom_filters("livestock")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="annual-cropland/custom-filters")
    def annual_cropland_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for annual cropland data."""
        custom_filters = self.get_available_custom_filters("annual-cropland")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="flooded-rice/custom-filters")
    def flooded_rice_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for flooded rice data."""
        custom_filters = self.get_available_custom_filters("flooded-rice")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="grassland/custom-filters")
    def grassland_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for grassland data."""
        custom_filters = self.get_available_custom_filters("grassland")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="perennial-cropland/custom-filters")
    def perennial_cropland_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for perennial cropland data."""
        custom_filters = self.get_available_custom_filters("perennial-cropland")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="forest-management/custom-filters")
    def forest_management_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for forest management data."""
        custom_filters = self.get_available_custom_filters("forest-management")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="small-fishery/custom-filters")
    def small_fishery_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for small fishery data."""
        custom_filters = self.get_available_custom_filters("small-fishery")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="large-fishery/custom-filters")
    def large_fishery_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for large fishery data."""
        custom_filters = self.get_available_custom_filters("large-fishery")
        return Response(custom_filters)

    @decorators.action(detail=False, methods=["get"], url_path="waterbody/custom-filters")
    def waterbody_custom_filters(self, request, *args, **kwargs):
        """Get available custom filter fields and values for waterbody data."""
        custom_filters = self.get_available_custom_filters("waterbody")
        return Response(custom_filters)

    ##### STATISTICS #####

    @decorators.action(detail=False, methods=["get"], url_path="livestock/statistics")
    def livestock_statistics(self, request, *args, **kwargs):
        """Get overall statistics for livestock data."""
        queryset, filters = self.get_filtered_queryset("livestock", request, extra_filters=["livestock_category_type"])

        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    @decorators.action(detail=False, methods=["get"], url_path="annual-cropland/statistics")
    def annual_cropland_statistics(self, request, *args, **kwargs):
        """Get overall statistics for annual cropland data."""
        queryset, filters = self.get_filtered_queryset("annual-cropland", request)
        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    @decorators.action(detail=False, methods=["get"], url_path="flooded-rice/statistics")
    def flooded_rice_statistics(self, request, *args, **kwargs):
        """Get overall statistics for flooded rice data."""
        queryset, filters = self.get_filtered_queryset("flooded-rice", request)
        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    @decorators.action(detail=False, methods=["get"], url_path="grassland/statistics")
    def grassland_statistics(self, request, *args, **kwargs):
        """Get overall statistics for grassland data."""
        queryset, filters = self.get_filtered_queryset("grassland", request)
        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    @decorators.action(detail=False, methods=["get"], url_path="perennial-cropland/statistics")
    def perennial_cropland_statistics(self, request, *args, **kwargs):
        """Get overall statistics for perennial cropland data."""
        queryset, filters = self.get_filtered_queryset("perennial-cropland", request)
        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    @decorators.action(detail=False, methods=["get"], url_path="forest-management/statistics")
    def forest_management_statistics(self, request, *args, **kwargs):
        """Get overall statistics for forest management data."""
        queryset, filters = self.get_filtered_queryset("forest-management", request)
        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    @decorators.action(detail=False, methods=["get"], url_path="small-fishery/statistics")
    def small_fishery_statistics(self, request, *args, **kwargs):
        """Get overall statistics for small fishery data."""
        queryset, filters = self.get_filtered_queryset("small-fishery", request)
        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    @decorators.action(detail=False, methods=["get"], url_path="large-fishery/statistics")
    def large_fishery_statistics(self, request, *args, **kwargs):
        """Get overall statistics for large fishery data."""
        queryset, filters = self.get_filtered_queryset("large-fishery", request)
        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    @decorators.action(detail=False, methods=["get"], url_path="waterbody/statistics")
    def waterbody_statistics(self, request, *args, **kwargs):
        """Get overall statistics for waterbody data."""
        queryset, filters = self.get_filtered_queryset("waterbody", request)
        total_records = queryset.count()
        total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
        avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

        return Response({"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact, "filters_applied": filters})

    ##### COMPARE #####

    @decorators.action(detail=False, methods=["get"], url_path="compare")
    def compare_modules(self, request, *args, **kwargs):
        """Compare statistics across all modules."""
        modules = request.query_params.get("modules", "livestock,annual-cropland,flooded-rice,grassland").split(",")

        comparison_data = {}

        for module in modules:
            module_type_mapping = {
                "livestock": "Livestock",
                "annual-cropland": "Annual Cropland",
                "flooded-rice": "Flooded Rice",
                "grassland": "Grassland",
                "perennial-cropland": "Perennial Cropland",
                "waterbody": "Waterbody",
                "forest-management": "Forest Management",
                "small-fishery": "Small Fishery",
                "large-fishery": "Large Fishery",
            }
            module_type_value = module_type_mapping.get(module, module)

            queryset = models.ChangeAggregate.objects.filter(module_type=module_type_value)

            total_records = queryset.count()
            total_changes = queryset.aggregate(total=Sum("count"))["total"] or 0
            avg_impact = queryset.aggregate(avg=Avg("mean"))["avg"] or 0

            comparison_data[module] = {"total_records": total_records, "total_changes": total_changes, "average_impact": avg_impact}

        return Response(comparison_data)

    ##### SUMMARY #####

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

        # Perennial cropland summary
        perennial_queryset = models.ChangeAggregate.objects.filter(module_type="Perennial Cropland")
        summary_data["perennial_cropland"] = {
            "total_records": perennial_queryset.count(),
            "total_changes": perennial_queryset.aggregate(total=Sum("count"))["total"] or 0,
            "unique_fields": perennial_queryset.values("field").distinct().count(),
        }

        # Forest management summary
        forest_queryset = models.ChangeAggregate.objects.filter(module_type="Forest Management")
        summary_data["forest_management"] = {
            "total_records": forest_queryset.count(),
            "total_changes": forest_queryset.aggregate(total=Sum("count"))["total"] or 0,
            "unique_fields": forest_queryset.values("field").distinct().count(),
        }

        # Small fishery summary
        small_queryset = models.ChangeAggregate.objects.filter(module_type="Small Fishery")
        summary_data["small_fishery"] = {
            "total_records": small_queryset.count(),
            "total_changes": small_queryset.aggregate(total=Sum("count"))["total"] or 0,
            "unique_fields": small_queryset.values("field").distinct().count(),
        }

        # Large fishery summary
        large_queryset = models.ChangeAggregate.objects.filter(module_type="Large Fishery")
        summary_data["large_fishery"] = {
            "total_records": large_queryset.count(),
            "total_changes": large_queryset.aggregate(total=Sum("count"))["total"] or 0,
            "unique_fields": large_queryset.values("field").distinct().count(),
        }

        # Waterbody summary
        waterbody_queryset = models.ChangeAggregate.objects.filter(module_type="Waterbody")
        summary_data["waterbody"] = {
            "total_records": waterbody_queryset.count(),
            "total_changes": waterbody_queryset.aggregate(total=Sum("count"))["total"] or 0,
            "unique_fields": waterbody_queryset.values("field").distinct().count(),
        }

        return Response(summary_data)

    @decorators.action(detail=False, methods=["get"], url_path="db-status")
    def db_status(self, request, *args, **kwargs):
        """Get database connection status for monitoring."""
        try:
            # Use the connection manager to get info
            db_info = get_connection_info()
            return Response(db_info)
        except Exception as e:
            return Response({"connection_healthy": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @decorators.action(detail=False, methods=["get"], url_path="connection-stats")
    def connection_stats(self, request, *args, **kwargs):
        """Get detailed connection statistics for monitoring."""
        try:
            from django.db import connections

            # connections.all() returns a plain list of DatabaseWrapper instances,
            # not a queryset, so len() over the materialized list is correct and
            # no .count() method exists here.
            database_connections = connections.all()
            stats = {"total_connections": len(database_connections), "databases": {}}

            for db_name, db_connection in connections.all().items():
                stats["databases"][db_name] = {
                    "connected": db_connection.connection is not None,
                    "settings": {
                        "name": db_connection.settings_dict.get("NAME", "unknown"),
                        "host": db_connection.settings_dict.get("HOST", "unknown"),
                        "port": db_connection.settings_dict.get("PORT", "unknown"),
                    },
                }

            return Response(stats)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

        # Extract params (currently unused, kept for API compatibility)
        request.query_params.get("aggregate_by", None)
        request.query_params.get("aggregate_field", None)

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


class EmissionScenarioViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = models.EmissionScenario.objects.all()
    serializer_class = serializers.EmissionScenarioSerializer
    filter_backends = [DjangoFilterBackend]

    def stats_for(self, qs):
        """
        Optimized statistical calculation that adapts to database backend.
        Uses database-native functions when available, falls back to optimized Python calculations.
        """
        from django.db import connection

        # Check if we're using SQLite and optimize accordingly
        if connection.vendor == "sqlite":
            return self._stats_for_sqlite_optimized(qs)

        try:
            # Try PostgreSQL-native functions first
            agg = qs.aggregate(
                n=Count("id"),
                sum_total=Sum("total"),
                mean=Avg("total"),
                minv=Min("total"),
                maxv=Max("total"),
                stddev=StdDev("total", sample=True),
                q1=PercentileCont("total", 0.25),
                median=PercentileCont("total", 0.5),
                q3=PercentileCont("total", 0.75),
            )
        except (NotSupportedError, ProgrammingError):
            return self._stats_for_python(qs)

        n = agg["n"] or 0
        total_sum = agg["sum_total"] or 0.0
        mean = agg["mean"]

        std = self._to_float(agg["stddev"])
        q1 = self._to_float(agg["q1"])
        median = self._to_float(agg["median"])
        q3 = self._to_float(agg["q3"])

        if n > 1 and std is not None:
            se = std / (n**0.5)
            ci95 = 1.96 * se
            ci99 = 2.58 * se
        else:
            ci95 = ci99 = None

        return self._finalize_stats(
            n=n,
            sum_total=total_sum,
            mean=mean,
            min_value=agg["minv"],
            max_value=agg["maxv"],
            std=std,
            q1=q1,
            median=median,
            q3=q3,
            ci95=ci95,
            ci99=ci99,
        )

    def _stats_for_sqlite_optimized(self, qs):
        """
        Optimized statistical calculation specifically for SQLite.
        Uses efficient database aggregations where possible and optimized Python calculations for percentiles.
        """
        # Get basic aggregates using SQLite-compatible functions
        agg = qs.aggregate(
            n=Count("id"),
            sum_total=Sum("total"),
            mean=Avg("total"),
            minv=Min("total"),
            maxv=Max("total"),
        )

        n = agg["n"] or 0
        total_sum = agg["sum_total"] or 0.0
        mean = agg["mean"] if n else None

        if n == 0:
            return self._finalize_stats(n=0, sum_total=0, mean=None, min_value=None, max_value=None, std=None, q1=None, median=None, q3=None, ci95=None, ci99=None)

        # For small datasets, use Python calculations
        if n <= 1000:
            return self._stats_for_python(qs)

        # For larger datasets, use optimized approach
        # Get all values in one query to minimize database hits
        total_values = list(qs.values_list("total", flat=True))

        if not total_values:
            return self._finalize_stats(n=0, sum_total=0, mean=None, min_value=None, max_value=None, std=None, q1=None, median=None, q3=None, ci95=None, ci99=None)

        # Calculate statistics efficiently
        sorted_values = sorted(total_values)

        # Standard deviation calculation
        if n > 1:
            variance = statistics.variance(total_values)
            std = variance**0.5
            se = std / (n**0.5)
            ci95 = 1.96 * se
            ci99 = 2.58 * se
        else:
            std = None
            ci95 = ci99 = None

        # Percentile calculations using optimized methods
        median = statistics.median(sorted_values)

        if len(sorted_values) >= 4:
            quartiles = statistics.quantiles(sorted_values, n=4)
            q1, q3 = quartiles[0], quartiles[2]
        else:
            q1 = self._interpolate_quantile(sorted_values, 0.25)
            q3 = self._interpolate_quantile(sorted_values, 0.75)

        return self._finalize_stats(
            n=n,
            sum_total=total_sum,
            mean=mean,
            min_value=agg["minv"],
            max_value=agg["maxv"],
            std=std,
            q1=q1,
            median=median,
            q3=q3,
            ci95=ci95,
            ci99=ci99,
        )

    def _stats_for_python(self, qs):
        agg = qs.aggregate(
            n=Count("id"),
            sum_total=Sum("total"),
            mean=Avg("total"),
            minv=Min("total"),
            maxv=Max("total"),
        )

        n = agg["n"] or 0
        total_sum = agg["sum_total"] or 0.0
        mean = agg["mean"] if n else None

        if n > 0:
            total_values = list(qs.values_list("total", flat=True))
            if n > 1:
                ss = sum(x * x for x in total_values)
                variance = max((ss - (total_sum * total_sum) / n) / (n - 1), 0.0)
                std = variance**0.5
                se = std / (n**0.5)
                ci95 = 1.96 * se
                ci99 = 2.58 * se
            else:
                std = None
                ci95 = ci99 = None

            sorted_values = sorted(total_values)
            median = statistics.median(sorted_values)
            if len(sorted_values) >= 4:
                quartiles = statistics.quantiles(sorted_values, n=4)
                q1, q3 = quartiles[0], quartiles[2]
            else:
                q1 = self._interpolate_quantile(sorted_values, 0.25)
                q3 = self._interpolate_quantile(sorted_values, 0.75)
        else:
            std = None
            ci95 = ci99 = None
            q1 = q3 = median = None

        return self._finalize_stats(
            n=n,
            sum_total=total_sum,
            mean=mean,
            min_value=agg["minv"],
            max_value=agg["maxv"],
            std=std,
            q1=q1,
            median=median,
            q3=q3,
            ci95=ci95,
            ci99=ci99,
        )

    def _interpolate_quantile(self, values, quantile):
        if not values:
            return None

        if len(values) == 1:
            return float(values[0])

        idx = (len(values) - 1) * quantile
        lower_idx = int(idx)
        upper_idx = min(lower_idx + 1, len(values) - 1)
        weight = idx - lower_idx

        lower = values[lower_idx]
        upper = values[upper_idx]

        if upper_idx == lower_idx:
            return float(lower)

        return float(lower * (1 - weight) + upper * weight)

    def _to_float(self, value):
        return float(value) if value is not None else None

    def _finalize_stats(self, n, sum_total, mean, min_value, max_value, std, q1, median, q3, ci95, ci99):
        iqr = (q3 - q1) if (q1 is not None and q3 is not None) else None

        mean_value = self._to_float(mean)
        mean_minus_median = (mean_value - median) if (mean_value is not None and median is not None) else None
        is_dataset_symmetric = bool(mean_minus_median is not None and std not in (None, 0) and mean_minus_median < 0.25 * std)

        if is_dataset_symmetric and mean_value is not None and std is not None:
            range_min = mean_value - std
            range_max = mean_value + std
        else:
            range_min = q1
            range_max = q3

        return {
            "count": n,
            "sum_total": sum_total,
            "mean": mean,
            "median": median,
            "min": min_value,
            "max": max_value,
            "std": std,
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "ci_95": ci95,
            "ci_99": ci99,
            "range_min": range_min,
            "range_max": range_max,
        }

    @action(detail=True, methods=["get"])
    def results(self, request, *args, **kwargs):
        """
        Optimized results action for emission scenarios.
        Uses efficient query building and caching for better performance.
        """
        instance: models.EmissionScenario = self.get_object()

        # Extract global filters from query parameters
        global_filters = {
            "climate": request.query_params.get("climate"),
            "moisture": request.query_params.get("moisture"),
            "soil_type": request.query_params.get("soil_type"),
            "region": request.query_params.get("region"),
        }

        # Remove None values to avoid unnecessary filtering
        global_filters = {k: v for k, v in global_filters.items() if v is not None}

        # Build optimized query using bulk operations
        q_objects = self._build_scenario_query(instance.changes, global_filters)

        if not q_objects:
            # Return empty results if no valid changes
            stats = {"count": 0}
            serializer = serializers.EmissionScenarioWithResultsSerializer({"emission_scenario": instance, **stats})
            return Response(serializer.data)

        # Use optimized queryset with select_related for better performance
        qs = models.ChangeRecord.objects.filter(q_objects).select_related()

        try:
            stats = self.stats_for(qs)
        except Exception as e:
            # Log the error for debugging but don't expose it to the client
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating statistics: {e}")
            stats = {"count": 0}

        serializer = serializers.EmissionScenarioWithResultsSerializer({"emission_scenario": instance, **stats})

        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="results/all")
    def all_results(self, request, *args, **kwargs):
        """
        Get all results for all emission scenarios.
        """
        scenarios = models.EmissionScenario.objects.all()
        results = []

        # Extract global filters from query parameters
        global_filters = {
            "climate": request.query_params.get("climate"),
            "moisture": request.query_params.get("moisture"),
            "soil_type": request.query_params.get("soil_type"),
            "region": request.query_params.get("region"),
        }

        for scenario in scenarios:
            try:
                # Get the scenario's results using the same logic as the results method
                scenario_results = self._get_scenario_results(scenario, global_filters)
                results.append({"scenario_id": scenario.pk, "scenario_name": scenario.name, "results": scenario_results})
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error getting results for scenario {scenario.pk}: {e}")
                results.append({"scenario_id": scenario.pk, "scenario_name": scenario.name, "results": [], "error": str(e)})

        return Response(results)

    def _get_scenario_results(self, scenario, global_filters):
        """
        Helper method to get results for a specific scenario.
        Extracts the core logic from the results method.
        """
        # Remove None values to avoid unnecessary filtering
        global_filters = {k: v for k, v in global_filters.items() if v is not None}

        # Build optimized query using bulk operations
        q_objects = self._build_scenario_query(scenario.changes, global_filters)

        if not q_objects:
            # Return empty results if no valid changes
            return {"count": 0, "results": []}

        # Use optimized queryset with select_related for better performance
        qs = models.ChangeRecord.objects.filter(q_objects).select_related()

        try:
            stats = self.stats_for(qs)
        except Exception as e:
            # Log the error for debugging but don't expose it to the client
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating statistics: {e}")
            stats = {"count": 0}

        # Serialize the results
        serializer = serializers.EmissionScenarioWithResultsSerializer({"emission_scenario": scenario, **stats})
        return serializer.data

    def _build_scenario_query(self, changes, global_filters):
        """
        Build optimized query for scenario changes.
        Uses bulk operations and efficient filtering with csv_row_data fallback.
        """
        q_objects = Q()

        for change in changes:
            module_type = change.get("module_type")
            if not module_type:
                continue

            # Normalize values to match even if stored as numeric-like strings
            def _value_variants(raw_value):
                v = raw_value
                variants = set()
                # Always include the original
                variants.add(v)
                # Include string form
                try:
                    variants.add(str(v))
                except Exception:
                    pass
                # If numeric-like, include canonical string without trailing zeros
                try:
                    from decimal import Decimal

                    num = Decimal(str(v))
                    # Normalize to remove trailing zeros (e.g., 1.0 -> 1)
                    normalized = num.normalize()
                    variants.add(format(normalized, "f").rstrip("0").rstrip(".") if "." in format(normalized, "f") else format(normalized, "f"))
                    # Also include int form when applicable
                    if normalized == normalized.to_integral():
                        variants.add(str(int(normalized)))
                        # Add common float renderings for integral values (handles stored "1.0", "1.00", ...)
                        base_int = int(normalized)
                        for places in range(1, 7):
                            variants.add(f"{base_int:.{places}f}")
                    else:
                        # For non-integral values, include a few fixed-precision forms ("1.5", "1.50", ...)
                        as_float = float(normalized)
                        for places in range(1, 7):
                            variants.add(f"{as_float:.{places}f}")
                except Exception:
                    pass
                return list(variants)

            _start_variants = _value_variants(change["start"]["value"])
            _end_variants = _value_variants(change["end"]["value"])

            # Build base change query
            change_q = Q(
                module_type=module_type,
                field=change["start"]["field"],
                from_value__in=_start_variants,
                to_value__in=_end_variants,
            )

            # Apply change-specific filters with csv_row_data fallback
            change_filters = change.get("filters", {})
            for filter_key, filter_value in change_filters.items():
                if filter_value:
                    change_q &= self._apply_filter_with_fallback(change_q, filter_key, filter_value)

            # Apply global filters (override change filters if specified)
            for filter_key, filter_value in global_filters.items():
                if filter_value:
                    change_q &= self._apply_filter_with_fallback(change_q, filter_key, filter_value)

            q_objects |= change_q

        return q_objects

    def _apply_filter_with_fallback(self, existing_q, filter_key, filter_value):
        """
        Apply filter with fallback to csv_row_data if the field doesn't exist as a direct field.
        """
        # Standard fields that exist directly on the model
        standard_fields = {"climate", "moisture", "soil_type", "region", "module_type", "field", "from_value", "to_value", "total"}

        if filter_key in standard_fields:
            # Use direct field filtering
            return Q(**{filter_key: filter_value})
        else:
            # Use csv_row_data JSON field filtering as fallback
            return Q(**{f"csv_row_data__{filter_key}": filter_value})

    @action(detail=False, methods=["post"])
    def compute(self, request, *args, **kwargs):
        """
        Compute custom scenarios with provided changes and filters.

        Supports two modes:
        1. Legacy mode: Provide module_type as a top-level parameter
           - module_type: string
           - changes: list of change objects with start/end field/value pairs

        2. Multi-module mode: Provide module_type within each change
           - changes: list of change objects with module_type, start, end, and optional filters

        Additional optional filter parameters (global, applied to all changes):
        - climate, moisture, soil_type, region: optional filter parameters

        Each change can also have its own "filters" object with the same fields.
        Global filters override change-specific filters if both are provided.
        """
        # Extract and validate input data
        legacy_module_type = request.data.get("module_type")
        changes = request.data.get("changes", [])

        # Extract global filters
        global_filters = {"climate": request.data.get("climate"), "moisture": request.data.get("moisture"), "soil_type": request.data.get("soil_type"), "region": request.data.get("region")}

        # Remove None values
        global_filters = {k: v for k, v in global_filters.items() if v is not None}

        if not changes:
            return Response({"error": "changes field is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate changes structure and ensure module_type is present
        for change in changes:
            if not isinstance(change, dict):
                return Response({"error": "Each change must be an object"}, status=status.HTTP_400_BAD_REQUEST)

            start = change.get("start", {})
            end = change.get("end", {})

            if not start.get("field") or not start.get("value"):
                return Response({"error": "Each change must have start.field and start.value"}, status=status.HTTP_400_BAD_REQUEST)

            if not end.get("field") or not end.get("value"):
                return Response({"error": "Each change must have end.field and end.value"}, status=status.HTTP_400_BAD_REQUEST)

            if not change.get("module_type") and not legacy_module_type:
                return Response({"error": "Each change must have module_type, or provide module_type as a top-level parameter"}, status=status.HTTP_400_BAD_REQUEST)

            if legacy_module_type and not change.get("module_type"):
                change["module_type"] = legacy_module_type

        # Build optimized query using the helper method
        q_objects = self._build_scenario_query(changes, global_filters)

        if not q_objects:
            # Return empty results if no valid changes
            stats = {"count": 0}
            temp_scenario = models.EmissionScenario(name="Custom Computation", description="Computed scenario with custom changes", changes=changes)
            serializer = serializers.EmissionScenarioWithResultsSerializer({"emission_scenario": temp_scenario, **stats})
            return Response(serializer.data)

        # Use optimized queryset
        qs = models.ChangeRecord.objects.filter(q_objects).select_related()

        try:
            stats = self.stats_for(qs)
        except Exception as e:
            # Log the error for debugging but don't expose it to the client
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating statistics: {e}")
            stats = {"count": 0}

        temp_scenario = models.EmissionScenario(name="Custom Computation", description="Computed scenario with custom changes", changes=changes)

        serializer = serializers.EmissionScenarioWithResultsSerializer({"emission_scenario": temp_scenario, **stats})

        return Response(serializer.data)
