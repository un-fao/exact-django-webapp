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
from .calculators import CalculatorFactory
from decorators import can_access

activity_id = openapi.Parameter('activity_id', openapi.IN_QUERY, description="ID of activity related to the module", type=openapi.TYPE_INTEGER)
project_id = openapi.Parameter('project_id', openapi.IN_QUERY, description="ID of project related to the activity", type=openapi.TYPE_INTEGER)
include_related = openapi.Parameter('include_related', openapi.IN_QUERY, description="Include related modules", type=openapi.TYPE_BOOLEAN)
parent = openapi.Parameter('parent', openapi.IN_QUERY, description="Parent name", type=openapi.TYPE_STRING)

class AuthenticatedViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

class LandUseTypeViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows land use types to be viewed or edited.
    """
    queryset = LandUseType.objects.all()
    serializer_class = get_model_serializer(LandUseType)

    # Modify get method to accept OPTIONAL query parameter 'module' to return land use types for a given module
    @swagger_auto_schema(manual_parameters=[parent], responses={404: 'No land use types found for parent'})
    def list(self, request):
        """
        Get all land use types, or all land use types for a given parent, by filtering against a `parent` query parameter in the URL.
        """
        parent = self.request.query_params.get('parent', None)
        if parent:
            land_use_types = LandUseType.objects.filter(parent__name=parent).order_by('name')
            if not land_use_types:
                return ErrorResponse(f"No land use types found for parent: {parent}", status=status.HTTP_404_NOT_FOUND)
            return Response(data=get_model_serializer(LandUseType)(land_use_types, many=True).data, status=status.HTTP_200_OK)
        
        return super().list(request)

@can_access("project")
class ProjectViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = Project.objects.all()
    serializer_class = get_model_serializer(Project)

@can_access("activity")
class ActivityViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows activities to be viewed or edited. 
    """
    queryset = Activity.objects.all()
    serializer_class = get_module_serializer(Activity)

    @swagger_auto_schema(
        manual_parameters=[project_id],
        responses={400: 'project_id not provided'}
    )
    def list(self, request):
        """
        Get all activities for a given project, by filtering against a `project_id` query parameter in the URL.
        """
        project_id = get_query_param_or_validation_error(self.request, 'project_id')
        list = Activity.objects.filter(project__id=project_id, project__user=self.request.user)
        return Response(data=get_module_serializer(Activity)(list, many=True).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the activity.
        """
        
        get_object_or_404(Activity, pk=pk, project__user=self.request.user)

        modules = []
        module_types = ModuleType.objects.all()
        # TODO: Make a serializer for this
        for module in module_types:
            module_model = apps.get_model(API, sanitize_for_model(module.name))
            module_object = module_model.objects.filter(activity__id=pk, activity__project__user=self.request.user).first()
            if module_object:
                module_dict = get_module_serializer(module_model)(module_object).data
                try:
                    module_dict[RESULTS] = ResultSerializer(CalculatorFactory().calculate_result(module_object), many=True).data
                except Exception as e:
                    module_dict[RESULTS] = error(str(e))
                modules.append(module_dict)

        return Response(modules)

    @action(detail=True, methods=['get'])
    def modules(self, request, pk=None):
        """
        Lists the modules of a given activity.
        """

        get_object_or_404(Activity, pk=pk, project__user=self.request.user)

        modules = []
        module_types = ModuleType.objects.all()

        for module in module_types:
            module_model = apps.get_model(API, sanitize_for_model(module.name))
            module_object = module_model.objects.filter(activity__id=pk, activity__project__user=self.request.user).first()
            if module_object:
                modules.append(get_module_serializer(module_model)(module_object).data)
        
        return Response(data=modules, status=status.HTTP_200_OK)

class ModuleTypeViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows module types to be viewed or edited.
    """
    queryset = ModuleType.objects.all()
    serializer_class = get_model_serializer(ModuleType)

@can_access("module")
def generic_module_viewset(model: Model):
    class GenericModuleViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_module_serializer(model)

        def create(self, request):
            """
            Creates a new module for a given activity.
            """

            module_serializer = self.serializer_class(data=request.data)
            if module_serializer.is_valid():

                activity_id = module_serializer.validated_data["activity"].pk

                # TODO: Can activities have multiples of the same module?
                # if model.objects.filter(activity__id=activity_id).exists():
                #     return ErrorResponse(f"Module '{model.__name__}' already exists for this activity.", status=status.HTTP_400_BAD_REQUEST)

                relative, relation = get_assessment_or_parent(model)
                if relative:
                    return ErrorResponse(f"Module '{model.__name__}' already has an attached {relative.__name__} {relation}.")

                activity = get_object_or_404(Activity, pk=activity_id, project__user=self.request.user)
                module_serializer.save(activity=activity)

                return Response(module_serializer.data, status=status.HTTP_201_CREATED)
            return Response(module_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        @swagger_auto_schema(
            manual_parameters=[activity_id, include_related],
        )
        def list(self, request):
            """
            Lists the module(s) of a given activity
            by filtering against an `activity_id` query parameter in the URL and
            optionally including related modules by sending the `include_related` query parameter as `true`.
            """

            activity_id = get_query_param_or_validation_error(self.request, 'activity_id')

            modules = model.objects.filter(activity__id=activity_id)

            data = []

            # TODO: Use a serializer for this
            for i, module in enumerate(modules):
                data.append({**self.serializer_class(module).data})
                
                if request.query_params.get(INCLUDE_RELATED):
                    relative, relation = get_assessment_or_parent(module)

                    if relative:
                        relative_serializer = get_module_serializer(relative.__class__)(relative)
                        data[i][relation] = relative_serializer.data

            return Response(data)

        @action(detail=True, methods=['get'])
        def results(self, request, pk=None):
            """
            Calculates and returns total emissions for a single module.
            TODO: Define structure and format of the real response.
            """

            module = get_object_or_404(model, pk=pk, activity__project__user=self.request.user)

            try:
                module_results = CalculatorFactory().calculate_result(module)
            except Exception as e:
                return ErrorResponse(str(e))

            return Response(ResultSerializer(module_results, many=True).data)

        @action(detail=True, methods=['get'])
        def defaults(self, request, pk=None):
            """
            Returns the default values for a module.

            GET /annual-croplands/1/defaults/
            """

            module = get_object_or_404(model, pk=pk, activity__project__user=self.request.user)

            try:
                # TODO: Implement defaults
                # module_defaults = get_defaults(module)
                return Response({"details": "Not implemented yet."})
            except Exception as e:
                return ErrorResponse(str(e))

    return GenericModuleViewSet