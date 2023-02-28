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
from .results import calc_result

activity_id = openapi.Parameter('activity_id', openapi.IN_QUERY, description="ID of activity related to the module", type=openapi.TYPE_INTEGER)
project_id = openapi.Parameter('project_id', openapi.IN_QUERY, description="ID of project related to the activity", type=openapi.TYPE_INTEGER)
include_related = openapi.Parameter('include_related', openapi.IN_QUERY, description="Include related modules", type=openapi.TYPE_BOOLEAN)

class AuthenticatedViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

class ProjectViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = Project.objects.all()
    serializer_class = get_model_serializer(Project)

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
        activity = get_object_or_404(Activity, pk=pk, project__user=self.request.user)

        modules = []
        module_types = ModuleType.objects.all()
        for module in module_types:
            module_model = apps.get_model(API, sanitize_for_model(module.name))
            module_object = module_model.objects.filter(activity__id=pk, activity__project__user=self.request.user).first()
            if module_object:
                module_dict = get_module_serializer(module_model)(module_object).data
                try:
                    module_dict[RESULTS] = ResultSerializer(calc_result(module_object, activity.project), many=True).data
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

def generic_module_viewset(model: Model):
    class GenericModuleViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_module_serializer(model)

        def create(self, request):
            """
            Creates a new module for a given activity.
            """

            module_serializer = get_module_serializer(model)(data=request.data)
            if module_serializer.is_valid():

                activity_id = module_serializer.validated_data["activity"].pk

                # Check if the same module for this activity already exists
                # TODO: Can activities have multiples of the same module?
                if model.objects.filter(activity__id=activity_id).exists():
                    return Response(error(f"Module '{model.__name__}' already exists for this activity."), status=status.HTTP_400_BAD_REQUEST)
                
                if get_assessment_or_parent(model):
                    return Response(error(f"Module '{model.__name__}' already has an attached assessment."), status=status.HTTP_400_BAD_REQUEST)

                # Check if the activity belongs to the user
                activity = get_object_or_404(Activity, pk=activity_id, project__user=self.request.user)
                module_serializer.save(activity=activity)

                return Response(module_serializer.data, status=status.HTTP_201_CREATED)
            return Response(module_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        def retrieve(self, request: Request, pk=None):
            module = get_object_or_404(model, pk=pk, activity__project__user=self.request.user)
            return Response(get_module_serializer(model)(module).data)

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

            module = get_object_or_404(model, activity__id=activity_id)
            module_serializer = get_module_serializer(model)(module)

            if request.query_params.get(INCLUDE_RELATED):
                relative_module, relation = get_assessment_or_parent(module)

                if relative_module:
                    relative_serializer = get_module_serializer(relative_module.__class__)(relative_module)
                    return Response({relation: relative_serializer.data, **module_serializer.data})

            return Response(module_serializer.data)

        @action(detail=True, methods=['get'])
        def results(self, request, pk=None):
            """
            Calculates and returns total emissions for a single module.
            TODO: Define structure and format of the real response.
            """

            module = get_object_or_404(model, pk=pk, activity__project__user=self.request.user)

            try:
                module_results = calc_result(module, module.activity.project)
            except Exception as e:
                return Response(error(str(e)), status=status.HTTP_400_BAD_REQUEST)

            return Response(ResultSerializer(module_results, many=True).data)

    return GenericModuleViewSet