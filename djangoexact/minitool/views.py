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
from django.db import connection
from rest_framework.pagination import PageNumberPagination
import api.models as api_models
import statistics
from collections import defaultdict
from typing import Dict, List, Any
from functools import wraps
from .db_manager import managed_db_connection, cleanup_connections, get_connection_info


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
        module_type_mapping = {"livestock": "Livestock", "annual-cropland": "Annual Cropland", "flooded-rice": "Flooded Rice", "grassland": "Grassland", "perennial-cropland": "Perennial Cropland"}
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

        return Response({"available_modules": available_modules, "total_modules": len(available_modules), "modules": [module["id"] for module in available_modules]})

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

    ##### COMPARE #####

    @decorators.action(detail=False, methods=["get"], url_path="compare")
    def compare_modules(self, request, *args, **kwargs):
        """Compare statistics across all modules."""
        modules = request.query_params.get("modules", "livestock,annual-cropland,flooded-rice,grassland").split(",")

        comparison_data = {}

        for module in modules:
            module_type_mapping = {"livestock": "Livestock", "annual-cropland": "Annual Cropland", "flooded-rice": "Flooded Rice", "grassland": "Grassland", "perennial-cropland": "Perennial Cropland"}
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

            stats = {"total_connections": len(connections.all()), "databases": {}}

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
