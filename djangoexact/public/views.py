from rest_framework.permissions import AllowAny
from rest_framework import viewsets
import api.models as api_models
import api.serializers as api_serializers
import public.serializers as public_serializers
import logging as log
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from rest_framework import status as http_status
from rest_framework.response import Response
import api.concurrency as concurrency
from api import security
import api.utilities as utils
from rest_framework.decorators import action
import api.calculators as calculators
import api.defaults as api_defaults
import types
import api.labels as labels
from django.http import HttpResponse
from django.utils.translation import activate
from django.conf import settings
from django.utils.translation import gettext as _
from datetime import datetime
import os
import base64
import io
import numpy as np
import ipcc.models as ipcc_models
import matplotlib.pyplot as plt
from django.shortcuts import render


def get_modules(activity: api_models.Activity, serialized=True) -> list:
    modules = activity.modules
    module_serializers_list = []

    for module in modules:
        module_dict = public_serializers.get_public_module_serializer(module.__class__)(module).data
        module_serializers_list.append(module_dict)

    return module_serializers_list if serialized else modules


class DefaultPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class PublicProjectViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows public projects to be viewed.
    """

    queryset = api_models.Project.objects.filter(is_public=True)
    serializer_class = public_serializers.PublicProjectSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=["get"])
    def activities(self, request, pk=None):
        project: api_models.Project = get_object_or_404(self.queryset, pk=pk)
        activities = project.activities.all()
        serializer = public_serializers.PublicActivitySerializer(activities, many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "activities",
                openapi.IN_QUERY,
                description="Comma-separated list of activity IDs to filter results",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "cached",
                openapi.IN_QUERY,
                description="Return cached results",
                type=openapi.TYPE_BOOLEAN,
            ),
        ],
        responses={404: "Project not found", 403: "Selected user does not have permission to view project results", 200: api_serializers.ProjectResultSerializer},
    )
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the project.
        """

        try:
            project = self.queryset.prefetch_related("activities").get(pk=pk, is_public=True)
        except api_models.Project.DoesNotExist:
            return utils.ErrorResponse("Project not found", status=http_status.HTTP_404_NOT_FOUND)

        serialized_project = api_serializers.ProjectResultSerializer(project, context={"request": request}).data

        selected_activities = [pk.strip() for pk in request.query_params.get("activities", "").split(",") if pk.strip().isdigit()]
        if not selected_activities:
            selected_activities = project.activities.values_list("id", flat=True)

        response = serialized_project
        response["activities"] = []

        # Function to process an activity
        def process_activity(activity_pk):
            return PublicActivityViewSet.results(self, request, pk=activity_pk).data

        activity_pks = project.activities.filter(pk__in=selected_activities).values_list("id", flat=True)

        def log_activity_failure(activity_pk, exc):
            log.error(f"Activity {activity_pk} generated an exception: {exc}")

        # Bounded fan-out: every worker opens its own Postgres connection, so
        # pool width is a per-instance connection cost (see api/concurrency.py).
        response["activities"] = concurrency.map_in_bounded_threads(
            process_activity,
            activity_pks,
            on_error=log_activity_failure,
        )

        return Response(data=response, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "activities",
                openapi.IN_QUERY,
                description="List of activity IDs to include in the report",
                type=openapi.TYPE_ARRAY,
                items={"type": openapi.TYPE_INTEGER},
            ),
            openapi.Parameter(
                "template",
                openapi.IN_QUERY,
                description="Name of the report template to render",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        responses={404: "Project not found", 403: "Selected user does not have permission to view project results"},
    )
    def report(self, request, pk=None):
        project: api_models.Project = get_object_or_404(self.queryset, pk=pk)

        if not project.is_ready():
            log.error("Project is not ready")
            return utils.ErrorResponse("To get a report for a project, all activities must have been completed.", status=http_status.HTTP_400_BAD_REQUEST)

        if request.query_params.get("template", None):
            response = self.template(request, pk=pk)
            return response

        selected_activities = [pk.strip() for pk in request.query_params.get("activities", "").split(",") if pk.strip().isdigit()]
        if not selected_activities:
            selected_activities = None
        else:
            selected_activities = project.activities.filter(pk__in=selected_activities)

        if request.query_params.get("template", None):
            response = self.template(request, pk=pk, activities=selected_activities)
            return response

        try:
            from api.reports import generate_excel_report
            file_bytes_buffer = generate_excel_report(project, activities=selected_activities)
        except Exception as e:
            log.error(f"Error generating report: {e}")
            return utils.ErrorResponse(str(e), status=http_status.HTTP_422_UNPROCESSABLE_ENTITY)

        try:
            response = HttpResponse(file_bytes_buffer, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f'attachment; filename="{project.name}_report.xlsx"'

            return response
        except FileNotFoundError:
            return utils.ErrorResponse("Error generating report: file not found", status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return utils.ErrorResponse(str(e), status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        operation_description="Generate a PDF from an HTML template",
        manual_parameters=[
            openapi.Parameter("template", openapi.IN_QUERY, description="Name of the Django template to render", type=openapi.TYPE_STRING, required=True),
            openapi.Parameter("lang", openapi.IN_QUERY, description="Language of the template", type=openapi.TYPE_STRING, required=False),
        ],
        responses={200: "PDF file generated successfully", 400: "Template name not provided or template not found", 500: "Error generating PDF"},
        produces=["application/pdf"],
    )
    def template(self, request, pk=None, activities=None):
        template_name = request.query_params.get("template")
        lang = request.query_params.get("lang", "en")
        if hasattr(request, "LANGUAGE_CODE"):
            lang = request.LANGUAGE_CODE

        if not template_name:
            return utils.ErrorResponse("Template name is required", status=http_status.HTTP_400_BAD_REQUEST)

        template_dir = os.path.join(settings.BASE_DIR, "api", "templates", "reports")
        if not os.path.exists(f"{template_dir}/{template_name}_{lang}.html"):
            return utils.ErrorResponse(f"Template '{template_name}' not found for language '{lang}'", status=http_status.HTTP_400_BAD_REQUEST)

        try:
            from api.reports import compute_project_result
            from api.reports.html_context import build_template_context

            project: api_models.Project = get_object_or_404(self.queryset, pk=pk)
            result = compute_project_result(project, activities=activities)
            context = build_template_context(result, request, lang, activities=activities)
            html = render(request, f"reports/{template_name}_{lang}.html", context).content.decode()
            from weasyprint import HTML
            pdf = HTML(string=html).write_pdf()
            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{template_name}.pdf"'
            return response

        except Exception as e:
            log.exception(e)
            return utils.ErrorResponse("An unexpected error occurred while generating the PDF", status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows public activities to be viewed.
    """

    queryset = api_models.Activity.objects.filter(project__is_public=True)
    serializer_class = public_serializers.PublicActivitySerializerWithModules
    permission_classes = [AllowAny]
    pagination_class = DefaultPagination

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "project_id",
                openapi.IN_QUERY,
                description="Project ID to filter activities",
                type=openapi.TYPE_INTEGER,
            )
        ],
        responses={
            400: "activity_id not provided",
            403: "Selected user does not have permission to view activities in the project",
            200: public_serializers.PublicActivitySerializer(many=True),
        },
    )
    def list(self, request):
        """
        Get all activities for a given project, by filtering against a `project_id` query parameter in the URL.
        """
        log.info("ActivityViewSet.list")
        project_id = utils.get_query_param_or_validation_error(self.request, "project_id")
        is_summary = request.query_params.get("summary", False)
        is_b_intact = request.query_params.get("is_b_intact", False) == "true"

        if is_summary:
            self.serializer_class = public_serializers.PublicActivitySummarySerializer

        def process_activity(activity):
            activity_dict = self.serializer_class(activity).data
            return activity_dict

        activities_list = api_models.Activity.objects.filter(project__id=project_id, project__is_public=True)
        activities_list = activities_list.filter(is_b_intact=is_b_intact)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(activities_list, request)
        if page is not None:
            response = concurrency.map_in_bounded_threads(process_activity, page)
            return paginator.get_paginated_response(response)

        return Response(data=self.serializer_class(activities_list, many=True).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def modules(self, request, pk=None):
        """
        Lists the modules of a given activity.
        """

        activity = get_object_or_404(self.queryset, pk=pk)

        modules = get_modules(activity, serialized=True)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(modules, request)
        if page is not None:
            return paginator.get_paginated_response(page)

        return Response(data=modules, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "cached",
                openapi.IN_QUERY,
                description="Return cached results",
                type=openapi.TYPE_BOOLEAN,
            )
        ],
        responses={400: "Bad request", 403: "Selected user does not have permission to view activity results", 200: api_serializers.ActivityResultSerializer},
    )
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the activity.
        """

        activity = get_object_or_404(api_models.Activity, pk=pk, project__is_public=True)

        response = {**api_serializers.ActivityResultSerializer(activity).data}

        modules = []
        # TODO: Make a serializer for this
        for module in activity.modules:
            if not module or (module.status and module.status.name_en != "READY"):
                continue

            module_dict = public_serializers.get_public_module_serializer(module.__class__)(module).data

            try:
                viewset = generic_public_module_viewset(module.__class__).results(self, request, pk=module.pk)
                module_dict[labels.RESULTS] = viewset.data

            except Exception as e:
                log.error("Error calculating result in ActivityViewSet.results", e)
                module_dict[labels.RESULTS] = utils.error(str(e))

            modules.append(module_dict)

        response["modules"] = modules

        return Response(response)


def generic_public_module_viewset(model: api_models.Module):
    class GenericModuleViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = model.objects.all()
        serializer_class = public_serializers.get_public_module_serializer(model)
        permission_classes = [AllowAny]

        def get_queryset(self):
            module_type = api_models.ModuleType.objects.get(class_name=model.__name__)

            if module_type.is_submodule:
                return model.objects.filter(parent__activity__project__is_public=True).all()
            else:
                return model.objects.filter(activity__project__is_public=True).all()

        @swagger_auto_schema(
            manual_parameters=[
                openapi.Parameter("activity", openapi.IN_QUERY, description="Activity ID to filter modules", type=openapi.TYPE_INTEGER),
                openapi.Parameter("module_type", openapi.IN_QUERY, description="Module type to filter modules", type=openapi.TYPE_STRING),
                openapi.Parameter("page_size", openapi.IN_QUERY, description="Number of items per page", type=openapi.TYPE_INTEGER),
                openapi.Parameter("page", openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            ],
            responses={400: "Bad request", 403: "Selected user does not have permission to view the module", 200: public_serializers.get_public_module_serializer(model)},
        )
        def list(self, request):
            """
            Lists the module(s) of a given activity
            by filtering against an `activity_id` query parameter in the URL or
            by filtering against the 'module_type' query parameter in the URL.
            """

            activity_id = utils.get_query_param_or_validation_error(self.request, "activity")
            module_type = api_models.ModuleType.objects.get(class_name=model.__name__)

            if module_type.is_submodule:
                modules = self.queryset.filter(parent__activity__id=activity_id).all()
            else:
                modules = self.queryset.filter(activity__id=activity_id).all()

            data = []

            for i, module in enumerate(modules):
                serializer = public_serializers.get_public_module_serializer(model)(instance=module, context={"request": request})
                data.append({**serializer.data})

            return Response(data)

        @action(detail=True, methods=["get"], url_path="results")
        @swagger_auto_schema(
            manual_parameters=[
                openapi.Parameter(
                    "aggregate",
                    openapi.IN_QUERY,
                    description="Aggregate results by",
                    type=openapi.TYPE_STRING,
                    enum=[
                        api_serializers.BreakdownTypes.TOTAL.value,
                        api_serializers.BreakdownTypes.ACTIVITY.value,
                        api_serializers.BreakdownTypes.GAS.value,
                        api_serializers.BreakdownTypes.ACTIVITY_GAS.value,
                    ],
                ),
                openapi.Parameter("cached", openapi.IN_QUERY, description="Use cached results", type=openapi.TYPE_BOOLEAN),
            ],
            responses={400: "Bad request", 403: "Selected user does not have permission to view module results", 200: api_serializers.DynamicResultSerializer},
        )
        def results(self, request, pk=None):
            """
            Calculates and returns total emissions for a single module.
            """
            log.debug(f"START GenericModuleViewSet.results for module {model} {pk}")
            module: api_models.Module | api_models.Submodule = get_object_or_404(model, pk=pk)
            activity = module.get_activity()

            serializer = public_serializers.get_public_module_serializer(model)(data={"activity": activity.pk}, partial=True, instance=module, context={"request": request})
            serializer.is_valid(raise_exception=True)

            if module.module_type.class_name == api_models.LandUseChange.__name__:
                module: api_models.LandUseChange

                if not all(m.is_ready() for m in module.get_modules()):
                    return utils.ErrorResponse("Not all modules are ready. Land Use Change module cannot be calculated.")
            else:
                if not module.is_ready():
                    log.error(f"Module {module.module_type} is not ready. Cannot calculate result.")
                    return utils.ErrorResponse("Module is not ready. Cannot calculate result.")

            try:
                aggregate_by = api_serializers.BreakdownTypes(request.query_params.get("aggregate", api_serializers.BreakdownTypes.TOTAL))
                module_results = module.get_cached_results(by=aggregate_by)
                use_cached_results = request.query_params.get("cached", "true") == "true"

                if module_results is None or not use_cached_results:
                    log.debug(f"Cache is invalid. Calculating results for module {module.id}")
                    total, by_activity, by_gas, by_activity_gas, inventory = calculators.CalculatorFactory().calculate_result(module)

                    results_total = api_serializers.DynamicResultFactory.create(activity, total, aggregate_by=api_serializers.BreakdownTypes.TOTAL).data
                    results_by_activity = api_serializers.DynamicResultFactory.create(activity, by_activity, aggregate_by=api_serializers.BreakdownTypes.ACTIVITY).data
                    results_by_gas = api_serializers.DynamicResultFactory.create(activity, by_gas, aggregate_by=api_serializers.BreakdownTypes.GAS).data
                    results_by_activity_gas = api_serializers.DynamicResultFactory.create(activity, by_activity_gas, aggregate_by=api_serializers.BreakdownTypes.ACTIVITY_GAS).data

                    results_total["inventory"] = inventory.breakdown(by=api_serializers.BreakdownTypes.TOTAL)
                    results_by_activity["inventory"] = inventory.breakdown(by=api_serializers.BreakdownTypes.ACTIVITY)
                    results_by_gas["inventory"] = inventory.breakdown(by=api_serializers.BreakdownTypes.GAS)
                    results_by_activity_gas["inventory"] = inventory.breakdown(by=api_serializers.BreakdownTypes.ACTIVITY_GAS)

                    module_results = (
                        results_total
                        if aggregate_by == api_serializers.BreakdownTypes.TOTAL
                        else results_by_activity
                        if aggregate_by == api_serializers.BreakdownTypes.ACTIVITY
                        else results_by_gas
                        if aggregate_by == api_serializers.BreakdownTypes.GAS
                        else results_by_activity_gas
                    )
                    module.cache_results(results_total, results_by_activity, results_by_gas, results_by_activity_gas)

                serializer = api_serializers.DynamicResultSerializer(module_results, aggregate_by=aggregate_by)
                serialized_data = serializer.data

                return Response(serialized_data)

            except Exception as e:
                log.error("Error calculating result in GenericModuleViewSet.results", e)
                return utils.ErrorResponse(str(e))

        @action(detail=True, methods=["get"], url_path="defaults")
        def defaults(self, request, pk=None):
            """
            Returns the default values for a module.

            ex. GET /annual-croplands/1/defaults/
            """

            module: api_models.Module | api_models.Submodule = get_object_or_404(self.queryset, pk=pk)

            serializer = public_serializers.get_public_module_serializer(model)(data={}, instance=module, partial=True, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()

            try:
                defaults: types.SimpleNamespace = api_defaults.DefaultsFactory.get_defaults(module, calculate=True)

                if isinstance(defaults, dict):
                    defaults = types.SimpleNamespace(**defaults)

                return Response(defaults.__dict__)
            except Exception as e:
                return utils.ErrorResponse(str(e))

        @action(detail=True, methods=["get"])
        @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view module definitions", 200: "Definitions"})
        def definitions(self, request, pk=None):
            """
            Returns the definitions for a module.
            """

            module: api_models.Module | api_models.Submodule = get_object_or_404(self.queryset, pk=pk)

            try:
                definitions = utils.get_entity_definitions(module.module_type.class_name)
                return Response(definitions)
            except Exception as e:
                return utils.ErrorResponse(str(e))

    return GenericModuleViewSet
