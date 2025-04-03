from rest_framework import generics
import api.models as models
import public.serializers as serializers
from rest_framework import viewsets
import django_filters
from django.db.models import JSONField
from rest_framework.decorators import action
from rest_framework.response import Response
import math_model.no_time_dependency_final.ghg_emissions_classes as ghg_emissions_classes
from api import serializers as api_serializers
import logging as log
import api.utilities as utils
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.shortcuts import get_object_or_404


class PublicProjectRetrieveViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View to retrieve a public project.
    """

    queryset = models.Project.objects.all()
    serializer_class = serializers.PublicProjectSerializer

    def get_queryset(self):
        """
        Override the get_queryset method to filter projects by public status.
        """
        return self.queryset.filter(is_public=True)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """
        Custom action to retrieve results for a specific project.
        """
        project = self.get_object()

        response = {**serializers.PublicProjectSerializer(project).data}

        selected_activities = request.query_params.getlist("activities", "").split(",")
        if selected_activities:
            selected_activities = project.activities.values_list("id", flat=True)

        response["activities"] = []

        # Function to process an activity
        def process_activity(activity_pk):
            return PublicActivityRetrieveViewSet.results(self, request, pk=activity_pk).data

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

        return Response(data=response)


class PublicActivityRetrieveViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View to retrieve a public activity.
    """

    class ActivityFilterSet(django_filters.FilterSet):
        class Meta:
            model = models.Activity
            fields = ["project"]

    queryset = models.Activity.objects.all()
    serializer_class = serializers.PublicActivitySerializer
    filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
    filterset_class = ActivityFilterSet

    def get_queryset(self):
        """
        Override the get_queryset method to filter activities by public status and project.
        """
        self.queryset = self.queryset.filter(project__is_public=True)
        return super().get_queryset()

    @action(detail=True, methods=["get"])
    def modules(self, request, pk=None):
        """
        Custom action to retrieve modules for a specific activity.
        """
        activity = self.get_object()
        modules = activity.modules

        modules_data = []

        for module in modules:
            modules_data.append(serializers.get_module_serializer(module.__class__)(module).data)

        return Response(modules_data)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """
        Custom action to retrieve results for a specific activity.
        """
        activity = get_object_or_404(models.Activity, pk=pk)
        response = {**serializers.PublicActivitySerializer(activity).data}

        modules = []
        for module in activity.modules:
            if not module or (module.status and module.status.name_en != "READY"):
                continue

            module_data = serializers.get_module_serializer(module.__class__)(module).data

            try:
                viewset = public_module(module.__class__).results(self, request, pk=module.pk)
                module_data["results"] = viewset.data
            except Exception as e:
                log.error("Error calculating result in ActivityViewSet.results", e)
                module_data["results"] = utils.error(str(e))

            modules.append(module_data)
        response["modules"] = modules

        return Response(response)


def public_module(ModuleClass: models.Module | models.Submodule):
    class GenericModuleRetrieveViewSet(viewsets.ReadOnlyModelViewSet):
        """
        View to retrieve a public module.
        """

        class GenericFilterSet(django_filters.FilterSet):
            class Meta:
                model = ModuleClass
                fields = "__all__"
                filter_overrides = {
                    "cached_results_total": {
                        "filter_class": django_filters.CharFilter,
                        "extra": lambda f: {
                            "lookup_expr": "exact",
                            "help_text": "Filter for JSON field cached_results_total",
                        },
                    },
                    JSONField: {
                        "filter_class": django_filters.CharFilter,
                        "extra": lambda f: {
                            "lookup_expr": "exact",
                        },
                    },
                }

        queryset = ModuleClass.objects.all()
        serializer_class = serializers.get_module_serializer(ModuleClass)
        filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
        filterset_class = GenericFilterSet

        def get_queryset(self):
            """
            Override the get_queryset method to filter modules by public status.
            """

            filter = {"parent__activity__project__is_public": True} if issubclass(ModuleClass, models.Submodule) else {"activity__project__is_public": True}
            self.queryset = self.queryset.filter(**filter)
            return super().get_queryset()

        @action(detail=True, methods=["get"])
        def results(self, request, pk=None):
            """
            Custom action to retrieve results for a specific module.
            """
            module: models.Module | models.Submodule = get_object_or_404(ModuleClass, pk=pk)
            aggregate_by = ghg_emissions_classes.BreakdownTypes(request.query_params.get("aggregate", ghg_emissions_classes.BreakdownTypes.TOTAL))

            results = module.get_cached_results(by=aggregate_by)
            serializer = api_serializers.DynamicResultSerializer(results, aggregate_by=aggregate_by)

            return Response(serializer.data)

    return GenericModuleRetrieveViewSet
