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
from concurrent.futures import ThreadPoolExecutor, as_completed
from api import security
import api.utilities as utils
from rest_framework.decorators import action
import api.calculators as calculators
import api.defaults as api_defaults
import types
import api.labels as labels


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
    pagination_class = None

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
            project = api_models.Project.objects.prefetch_related("activities").get(pk=pk)
        except api_models.Project.DoesNotExist:
            log.error("Project not found")
            return utils.ErrorResponse("Project not found", status=http_status.HTTP_404_NOT_FOUND)

        serialized_project = api_serializers.ProjectResultSerializer(project, context={"request": request}).data

        selected_activities = request.query_params.get("activities", "").split(",")
        if selected_activities == [""]:
            selected_activities = project.activities.values_list("id", flat=True)

        response = serialized_project
        response["activities"] = []

        # Function to process an activity
        def process_activity(activity_pk):
            return PublicActivityViewSet.results(self, request, pk=activity_pk).data

        activity_pks = project.activities.filter(pk__in=selected_activities).values_list("id", flat=True)

        # Use ThreadPoolExecutor to run tasks in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all tasks to the executor
            future_to_pk = {executor.submit(process_activity, pk): pk for pk in activity_pks}

            for future in as_completed(future_to_pk):
                pk = future_to_pk[future]
                try:
                    data = future.result()
                except Exception as exc:
                    log.error(f"Activity {pk} generated an exception: {exc}")
                    # You can choose to handle exceptions differently if needed
                else:
                    response["activities"].append(data)

        return Response(data=response, status=http_status.HTTP_200_OK)


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

        if is_summary:
            self.serializer_class = public_serializers.PublicActivitySummarySerializer

        def process_activity(activity):
            activity_dict = self.serializer_class(activity).data
            return activity_dict

        activities_list = api_models.Activity.objects.filter(project__id=project_id)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(activities_list, request)
        if page is not None:
            with ThreadPoolExecutor() as executor:
                response = list(executor.map(process_activity, page))
            return paginator.get_paginated_response(response)

        return Response(data=self.serializer_class(activities_list, many=True).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def modules(self, request, pk=None):
        """
        Lists the modules of a given activity.
        """

        activity = get_object_or_404(api_models.Activity, pk=pk)

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

        activity = api_models.Activity.objects.prefetch_related().get(pk=pk)

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
            activity_id = utils.get_query_param_or_validation_error(self.request, "activity")
            activity = get_object_or_404(api_models.Activity, pk=activity_id)
            module_type = api_models.ModuleType.objects.get(class_name=model.__name__)

            error = security.check_permission("view_modules", self.request.user, activity.project)
            if error:
                return error

            if module_type.is_submodule:
                return model.objects.filter(parent__activity__id=activity_id).all()
            else:
                return model.objects.filter(activity__id=activity_id).all()

        def get_serializer_class(self):
            if self.action == "retrieve":
                return public_serializers.get_public_module_serializer(model, api_serializers.ActionTypes.RETRIEVE)
            return super().get_serializer_class()

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
                modules = model.objects.filter(parent__activity__id=activity_id).all()
            else:
                modules = model.objects.filter(activity__id=activity_id).all()

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
                    enum=[api_serializers.BreakdownTypes.TOTAL.value, api_serializers.BreakdownTypes.ACTIVITY.value, api_serializers.BreakdownTypes.GAS.value, api_serializers.BreakdownTypes.ACTIVITY_GAS.value],
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
                    total, by_activity, by_gas, by_activity_gas = calculators.CalculatorFactory().calculate_result(module)

                    results_total = api_serializers.DynamicResultFactory.create(activity, total, aggregate_by=api_serializers.BreakdownTypes.TOTAL).data
                    results_by_activity = api_serializers.DynamicResultFactory.create(activity, by_activity, aggregate_by=api_serializers.BreakdownTypes.ACTIVITY).data
                    results_by_gas = api_serializers.DynamicResultFactory.create(activity, by_gas, aggregate_by=api_serializers.BreakdownTypes.GAS).data
                    results_by_activity_gas = api_serializers.DynamicResultFactory.create(activity, by_activity_gas, aggregate_by=api_serializers.BreakdownTypes.ACTIVITY_GAS).data

                    module_results = results_total if aggregate_by == api_serializers.BreakdownTypes.TOTAL else results_by_activity if aggregate_by == api_serializers.BreakdownTypes.ACTIVITY else results_by_gas if aggregate_by == api_serializers.BreakdownTypes.GAS else results_by_activity_gas
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

            module: api_models.Module | api_models.Submodule = get_object_or_404(model, pk=pk)
            activity = module.get_activity()

            serializer = public_serializers.get_public_module_serializer(model, api_serializers.ActionTypes.UPDATE)(data={}, instance=module, partial=True, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()

            error = security.check_permission("view_modules", self.request.user, activity.project)
            if error:
                return error

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

            module: api_models.Module | api_models.Submodule = get_object_or_404(model, pk=pk)

            try:
                definitions = utils.get_entity_definitions(module.module_type.class_name)
                return Response(definitions)
            except Exception as e:
                return utils.ErrorResponse(str(e))

    return GenericModuleViewSet
