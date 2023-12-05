from .models import Project, Activity, ModuleType
from .utilities import *
from .serializers import *
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.views import *
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from .calculators import CalculatorFactory, Result
from rest_framework.permissions import AllowAny
from rest_framework import generics
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db import transaction
import logging
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes, Result as MathResult
from django.core import serializers as django_serializers

logger = logging.getLogger("console")

activity_id = openapi.Parameter("activity_id",openapi.IN_QUERY,description="ID of activity related to the module",type=openapi.TYPE_INTEGER)
project_id = openapi.Parameter( "project_id", openapi.IN_QUERY, description="ID of project related to the activity", type=openapi.TYPE_INTEGER)
include_related = openapi.Parameter( "include_related", openapi.IN_QUERY, description="Include related modules", type=openapi.TYPE_BOOLEAN)
module_type = openapi.Parameter("module_type", openapi.IN_QUERY, description="Module associated with Land Use Type", type=openapi.TYPE_INTEGER)
climate = openapi.Parameter("climate", openapi.IN_QUERY, description="Climate associated with Land Use Type", type=openapi.TYPE_INTEGER)
moisture = openapi.Parameter("moisture", openapi.IN_QUERY, description="Moisture associated with Land Use Type", type=openapi.TYPE_INTEGER)
cascade = openapi.Parameter("cascade", openapi.IN_QUERY, description="Include comments in thread", type=openapi.TYPE_BOOLEAN)


def get_modules(activity: Activity, serialized=True) -> list:
    modules = []
    module_serializers_list = []
    module_types = ModuleType.objects.filter(is_submodule=False).all()
    for module in module_types:
        try:
            module_model = apps.get_model(API, module.class_name)
        except LookupError:
            logger.warning(f"get_modules: Module {module.name} not found")
            continue
        module_object = module_model.objects.filter(activity__id=activity.pk).first()
        if module_object:
            modules.append(module_object)
            module_dict = get_module_serializer(module_model)(module_object).data
            module_serializers_list.append(module_dict)

    return module_serializers_list if serialized else modules


class AuthenticatedViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

class LandUseTypeViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows land use types to be viewed or edited.
    """

    queryset = LandUseType.objects.all()
    serializer_class = LandUseTypeSerializer

    @swagger_auto_schema(manual_parameters=[module_type, climate, moisture])
    def list(self, request):
        """
        Get all land use types, or all land use types for a given module type, by filtering against a `module_type` query parameter in the URL.
        """

        module_type_id = self.request.query_params.get("module_type", None)
        climate_id = self.request.query_params.get("climate", None)
        moisture_id = self.request.query_params.get("moisture", None)

        if not module_type_id and not climate_id and not moisture_id:
            return super().list(request)

        filters = {}

        if module_type_id:
            filters["module_types__id"] = module_type_id
        if climate_id:
            filters["climates__id"] = climate_id
        if moisture_id:
            filters["moistures__id"] = moisture_id
        
        list = LandUseType.objects.filter(**filters).all()
        serializer = get_model_serializer(LandUseType)(list, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)
    
class ProjectViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """

    queryset = Project.objects.all()
    serializer_class = WriteProjectSerializer

    def create(self, request, *args, **kwargs):
        """
        Creates a new project for a given user.
        """
        request.data["user"] = self.request.user.pk
        serializer = WriteProjectSerializer(data=request.data)

        if not serializer.is_valid():
            logging.error("Error creating project:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        project = serializer.save()

        read_serializer = ReadProjectSerializer(instance=project)

        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"})
    def retrieve(self, request, pk=None):
        """
        Get a single project for a given user.
        """
        project = get_object_or_404(Project, pk=pk, user=self.request.user)
        return Response(data=ReadProjectSerializer(project).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"})
    def list(self, request):
        """
        Get all projects for a given user.
        """
        list = Project.objects.filter(user=self.request.user).all()
        return Response(data=ReadProjectSerializer(list, many=True).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"})
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the project.
        """

        project = get_object_or_404(Project, pk=pk, user=self.request.user)
        serialized_project = ReadProjectSerializer(project).data

        response = serialized_project
        response["activities"] = []

        for activity in project.activities.all():
            response["activities"].append(ActivityViewSet.results(self, request, activity.pk).data)

        return Response(data=response, status=status.HTTP_200_OK)

class ActivityViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows activities to be viewed or edited.
    """

    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer

    def update(self, request, *args, **kwargs):
        
        activity = self.get_object()

        serializer = WriteActivitySerializer(data=request.data, instance=activity)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        activity = serializer.save()

        read_serializer = ActivitySerializer(instance=activity)

        return Response(read_serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):

        activity = self.get_object()

        serializer = WriteActivitySerializer(data=request.data, partial=True, instance=activity)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        activity = serializer.save()

        read_serializer = ActivitySerializer(instance=activity)

        return Response(read_serializer.data, status=status.HTTP_200_OK)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        state = ActivityState.objects.get_or_create(name="EMPTY")[0]
        request.data["status"] = state.pk
        serializer = WriteActivitySerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        activity = serializer.save()

        read_serializer = ActivitySerializer(instance=activity)

        return Response(read_serializer.data, status=status.HTTP_201_CREATED)
    
    @swagger_auto_schema(manual_parameters=[project_id], responses={400: "activity_id not provided"})
    def retrieve(self, request, pk=None):
        """
        Get a single activity for a given user.
        """
        logger.info("ActivityViewSet.retrieve")
        activity = get_object_or_404(Activity, pk=pk)
        activity_dict = ActivitySerializer(activity).data
        activity_dict["modules"] = get_modules(activity)

        return Response(data=activity_dict, status=status.HTTP_200_OK)

    @swagger_auto_schema(manual_parameters=[project_id], responses={400: "activity_id not provided"})
    def list(self, request):
        """
        Get all activities for a given project, by filtering against a `project_id` query parameter in the URL.
        """
        logger.info("ActivityViewSet.list")
        project_id = get_query_param_or_validation_error(self.request, "project_id")
        list = Activity.objects.filter(project__id=project_id)

        response = []

        for activity in list:
            activity_dict = ActivitySerializer(activity).data
            activity_dict["modules"] = get_modules(activity)
            response.append(activity_dict)

        return Response(data=response, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the activity.
        """

        activity = get_object_or_404(Activity, pk=pk)
        response = {**ActivitySerializer(activity).data}

        modules = []
        # TODO: Make a serializer for this
        for module in activity.module_types.all():
            try:
                model_ref = apps.get_model(API, module.class_name)
            except LookupError:
                logger.warning(f"Module {module.name} not found")
                continue

            object = getattr(activity, module.class_name.lower(), None).first()

            if not object or (object.status and object.status.name != "READY"):
                continue

            module_dict = get_module_serializer(model_ref)(object).data

            try:

                viewset = generic_module_viewset(model_ref).results(self, request, pk=object.pk)
                module_dict[RESULTS] = viewset.data

            except Exception as e:
                logger.error("Error calculating result in ActivityViewSet.results", e)
                module_dict[RESULTS] = error(str(e))

            modules.append(module_dict)
                    
        response["modules"] = modules

        return Response(response)

    @action(detail=True, methods=["get"])
    def modules(self, request, pk=None):
        """
        Lists the modules of a given activity.
        """

        activity = get_object_or_404(Activity, pk=pk)
        modules = get_modules(activity)

        return Response(data=modules, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    @swagger_auto_schema(request_body=ActivityBuilderSerializer, responses={400: "Bad request", 200: ActivitySerializer})
    @transaction.atomic
    def build(self, request):
        """
        Builds a new activity and the modules associated with it.
        """

        try:

            serializer = ActivityBuilderSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            activity = serializer.save()
        
        except serializers.ValidationError as e:
            logger.error("Error building activity:", e.get_full_details())
            return Response(e.get_full_details(), status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error("Error building activity:", e)
            return ErrorResponse(str(e), status=status.HTTP_400_BAD_REQUEST)

        return Response(ActivitySerializer(activity).data, status=status.HTTP_200_OK)

class CommentThreadViewSet(viewsets.ModelViewSet):
    queryset = CommentThread.objects.all()
    serializer_class = CommentThreadSerializer

    @action(detail=True, methods=["get"])
    def comments(self, request, pk=None):
        """
        Lists the comments of a given thread.
        """

        thread = get_object_or_404(CommentThread, pk=pk)
        comments = thread.comments.all()

        return Response(data=CommentSerializer(comments, many=True).data, status=status.HTTP_200_OK)

class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=["get"])
    def replies(self, request, thread_id=None, pk=None):
        """
        Lists the replies of a given comment.
        """

        comment = get_object_or_404(Comment, pk=pk)
        replies = comment.replies.all()

        return Response(data=CommentSerializer(replies, many=True).data, status=status.HTTP_200_OK)

class ModuleTypeViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows module types to be viewed or edited.
    """

    queryset = ModuleType.objects.all()
    serializer_class = get_model_serializer(ModuleType)

    def list(self, request):
        """
        Get all module types.
        """
        is_luc = self.request.query_params.get("is_luc", None) == "true"

        if is_luc:
            module_types = ModuleType.objects.filter(is_luc=is_luc).all()
            serializer = get_model_serializer(ModuleType)(module_types, many=True)
            return Response(data=serializer.data, status=status.HTTP_200_OK)
    
        return super().list(request)

class CountryViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows countries to be viewed or edited.
    """

    queryset = Country.objects.all()
    serializer_class = CountrySerializer

    def list(self, request):
        """
        Get all countries.
        """
        region_id = self.request.query_params.get("region", None)

        if region_id:
            countries = Country.objects.filter(region__id=region_id).all()
            serializer = get_model_serializer(Country)(countries, many=True)
            return Response(data=serializer.data, status=status.HTTP_200_OK)
    
        return super().list(request)

def generic_module_viewset(model: Model):
    class GenericModuleViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_module_serializer(model)

        def get_serializer_class(self):
            if self.action in ["create", "update", "partial_update"]:
                return get_module_serializer(model, action=ActionTypes.CREATE)
            return get_module_serializer(model)
        
        def update(self, request, *args, **kwargs):
            """
            Updates a module.
            """

            module = self.get_object()

            serializer = get_module_serializer(model, action=ActionTypes.CREATE)(data=request.data, instance=module)

            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            module = serializer.save()

            read_serializer = get_module_serializer(model)(instance=module, context={"request": request})

            return Response(read_serializer.data, status=status.HTTP_200_OK)
        
        def partial_update(self, request, *args, **kwargs):
            """
            Partially updates a module.
            """

            module = self.get_object()

            serializer = get_module_serializer(model, action=ActionTypes.CREATE)(data=request.data, partial=True, instance=module)

            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            module = serializer.save()

            read_serializer = get_module_serializer(model)(instance=module, context={"request": request})

            return Response(read_serializer.data, status=status.HTTP_200_OK)

        @transaction.atomic
        def create(self, request):
            """
            Creates a new module for a given activity.
            """

            logging.debug(f"START GenericModuleViewSet[{model.__name__}].create")
            logging.debug(f"request.data: {request.data}")

            module_serializer = get_module_serializer(model, action=ActionTypes.CREATE)(data=request.data, many=request.data.__class__ == list)

            if not module_serializer.is_valid():
                logger.error(f"Error creating module: {module_serializer.errors}")
                return Response(module_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # for t in get_thread_attributes(model):
            #     module_serializer.validated_data[t.name] = CommentThread.objects.create()

            module_serializer.save()

            read_serializer = get_module_serializer(model)(module_serializer.instance)

            logging.debug(f"END GenericModuleViewSet[{model.__name__}].create")

            return Response(read_serializer.data, status=status.HTTP_201_CREATED)

        @swagger_auto_schema(manual_parameters=[activity_id, include_related])
        def list(self, request):
            """
            Lists the module(s) of a given activity
            by filtering against an `activity_id` query parameter in the URL and
            optionally including related modules by sending the `include_related` query parameter as `true`.
            """

            activity_id = get_query_param_or_validation_error(self.request, "activity_id")
            modules = model.objects.filter(activity__id=activity_id)

            data = []

            for i, module in enumerate(modules):
                data.append({**self.serializer_class(module).data})

            return Response(data)

        @action(detail=True, methods=["get"])
        def results(self, request, pk=None):
            """
            Calculates and returns total emissions for a single module.
            TODO: Define structure and format of the real response.
            """

            from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes

            aggregate_by = BreakdownTypes(request.query_params.get("aggregate", BreakdownTypes.TOTAL))

            module = get_object_or_404(model, pk=pk, activity__project__user=self.request.user)

            try:
                results_w, results_wo, results_tot = CalculatorFactory().calculate_result(module, aggregate_by=aggregate_by)
                Serializer = ResultSerializerFactory().by(aggregate_by)

                if Serializer == TotalResultSerializer:
                    module_results = Serializer(
                        {
                            "total_w": results_w,
                            "total_wo": results_wo,
                            "balance": results_tot,
                        }
                    ).data
                else:
                    module_results = {
                        "total_w": Serializer(results_w, many=True).data,
                        "total_wo": Serializer(results_wo, many=True).data,
                        "balance": Serializer(results_tot, many=True).data,
                    }

            except Exception as e:
                logging.error("Error calculating result in GenericModuleViewSet.results", e)
                return ErrorResponse(str(e))

            return Response(module_results)

        @action(detail=True, methods=["get"])
        def defaults(self, request, pk=None):
            """
            Returns the default values for a module.

            ex. GET /annual-croplands/1/defaults/
            """

            get_object_or_404(model, pk=pk, activity__project__user=self.request.user)

            try:
                # TODO: Implement defaults
                # module_defaults = get_defaults(module)
                return ErrorResponse("Not implemented", status=status.HTTP_501_NOT_IMPLEMENTED)
            except Exception as e:
                return ErrorResponse(str(e))

    return GenericModuleViewSet


def generic_viewset(model: Model):
    class GenericViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_model_serializer(model)

    return GenericViewSet
