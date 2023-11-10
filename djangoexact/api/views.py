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


activity_id = openapi.Parameter("activity_id",openapi.IN_QUERY,description="ID of activity related to the module",type=openapi.TYPE_INTEGER)
project_id = openapi.Parameter( "project_id", openapi.IN_QUERY, description="ID of project related to the activity", type=openapi.TYPE_INTEGER)
include_related = openapi.Parameter( "include_related", openapi.IN_QUERY, description="Include related modules", type=openapi.TYPE_BOOLEAN)
module_type = openapi.Parameter("module_type", openapi.IN_QUERY, description="Module associated with Land Use Type", type=openapi.TYPE_INTEGER)
cascade = openapi.Parameter("cascade", openapi.IN_QUERY, description="Include comments in thread", type=openapi.TYPE_BOOLEAN)


def get_modules(activity: Activity, serialized=True) -> list:
    modules = []
    module_serializers_list = []
    module_types = ModuleType.objects.all()
    for module in module_types:
        try:
            module_model = apps.get_model(API, module.class_name)
        except LookupError:
            print(f"get_modules: Module {module.name} not found")
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
    serializer_class = get_model_serializer(LandUseType)

    @swagger_auto_schema(manual_parameters=[module_type])
    def list(self, request):
        """
        Get all land use types, or all land use types for a given module type, by filtering against a `module_type` query parameter in the URL.
        """
        module_type_id = self.request.query_params.get("module_type", None)
        if module_type_id:
            land_use_types = LandUseType.objects.filter(module_types__pk=module_type_id).all()
            serializer = get_model_serializer(LandUseType)(land_use_types, many=True)
            return Response(data=serializer.data, status=status.HTTP_200_OK)

        return super().list(request)

class ProjectViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"})
    def retrieve(self, request, pk=None):
        """
        Get a single project for a given user.
        """
        project = get_object_or_404(Project, pk=pk, user=self.request.user)
        return Response(
            data=ProjectSerializer(project).data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"})
    def list(self, request):
        """
        Get all projects for a given user.
        """
        list = Project.objects.filter(user=self.request.user)

        return Response(
            data=ProjectSerializer(list, many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"})
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the project.
        """

        project = get_object_or_404(Project, pk=pk, user=self.request.user)
        serialized_project = ProjectSerializer(project).data

        project_results = Result()

        response = serialized_project
        response["activities"] = []

        activities = project.activities.all()
        for activity in activities:
            activity_results = ActivityViewSet.results(self, request, activity.pk).data
            response["activities"].append(activity_results)

            project_results.add(Result(activity_results[RESULTS]['total_w'], activity_results[RESULTS]['total_wo']))

        response["results"] = ResultSerializer(project_results).data

        return Response(data=response, status=status.HTTP_200_OK)


class ActivityViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows activities to be viewed or edited.
    """

    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer

    def create(self, request, *args, **kwargs):
        state = ActivityState.objects.get_or_create(name="EMPTY")[0]
        request.data["state"] = state.pk
        return super().create(request, *args, **kwargs)
    
    @swagger_auto_schema(manual_parameters=[project_id], responses={400: "activity_id not provided"})
    def retrieve(self, request, pk=None):
        """
        Get a single activity for a given user.
        """
        activity = get_object_or_404(Activity, pk=pk, project__user=self.request.user)
        activity_dict = ActivitySerializer(activity).data
        activity_dict["modules"] = get_modules(activity)

        return Response(
            data=activity_dict,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(manual_parameters=[project_id], responses={400: "activity_id not provided"})
    def list(self, request):
        """
        Get all activities for a given project, by filtering against a `project_id` query parameter in the URL.
        """
        print("list")
        project_id = get_query_param_or_validation_error(self.request, "project_id")
        list = Activity.objects.filter(project__id=project_id, project__user=self.request.user)

        response = []

        for activity in list:
            activity_dict = ActivitySerializer(activity).data
            activity_dict["modules"] = get_modules(activity)
            response.append(activity_dict)

        return Response(
            data=response,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the activity.
        """

        activity = get_object_or_404(Activity, pk=pk, project__user=self.request.user)

        response = {**ActivitySerializer(activity).data}
        tot_result = Result()

        modules = []
        module_types = ModuleType.objects.all()
        # TODO: Make a serializer for this
        for module in module_types:
            try:
                model_ref = apps.get_model(API, module.class_name)
            except LookupError:
                print(f"Module {module.name} not found")
                continue
            object = model_ref.objects.filter(activity__id=pk, activity__project__user=self.request.user).first()

            if object:
                module_dict = get_module_serializer(model_ref)(object).data

                try:
                    result: Result = CalculatorFactory().calculate_result(object)
                    module_dict[RESULTS] = ResultSerializer(result).data
                    tot_result.add(result)
                except Exception as e:
                    print("module_id", module_dict["id"])
                    print("Error calculating result in ActivityViewSet.results", e)
                    module_dict[RESULTS] = error(str(e))

                modules.append(module_dict)
                    

        response["modules"] = modules
        response["results"] = ResultSerializer(tot_result).data

        return Response(response)

    @action(detail=True, methods=["get"])
    def modules(self, request, pk=None):
        """
        Lists the modules of a given activity.
        """

        activity = get_object_or_404(Activity, pk=pk, project__user=self.request.user)
        modules = get_modules(activity)

        return Response(data=modules, status=status.HTTP_200_OK)

    @transaction.atomic
    @action(detail=False, methods=["post"])
    @swagger_auto_schema(request_body=ActivityBuilderSerializer, responses={400: "Bad request", 200: ActivitySerializer})
    def build(self, request):
        """
        Builds a new activity and the modules associated with it.
        """

        try:

            serializer = ActivityBuilderSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            activity = serializer.save()

        except Exception as e:
            import traceback
            traceback.print_exc()
            print("Error building activity:", e)
            return ErrorResponse(str(e))

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


def generic_module_viewset(model: Model):
    class GenericModuleViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_module_serializer(model)

        @transaction.atomic
        def create(self, request):
            """
            Creates a new module for a given activity.
            """

            module_serializer = get_module_serializer(model, create=True)(data=request.data, many=request.data.__class__ == list)
            
            if not module_serializer.is_valid():
                return Response(module_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            luc = module_serializer.validated_data.get("land_use_change", None)

            if luc:
                luc_start = luc.land_use_type_start
                luc_end = luc.land_use_type_end

                if not luc_start and not luc_end:
                    return ErrorResponse(f"Land use change must have at least one land use type selected.", status=status.HTTP_400_BAD_REQUEST)
                
                if (luc_start and luc_start.module_type.name != model.__name__) or (luc_end and luc_end.module_type.name != model.__name__):
                    return ErrorResponse(f"At least one land use type in land use change must be related to a {model.__name__} module.", status=status.HTTP_400_BAD_REQUEST)
                
            for attr in dir(model):
                if attr.endswith("_thread"): # NOTE: This could create problems if any other attribute ends in "_thread"
                    module_serializer.validated_data[attr] = CommentThread.objects.create()

            module_serializer.save()

            return Response(module_serializer.data, status=status.HTTP_201_CREATED)
            

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

            # TODO: Use a serializer for this
            for i, module in enumerate(modules):
                data.append({**self.serializer_class(module).data})

                if request.query_params.get(INCLUDE_RELATED):
                    relative, relation = get_relative(module)

                    if relative:
                        relative_serializer = get_module_serializer(relative.__class__)(relative)
                        data[i][relation] = relative_serializer.data

            return Response(data)

        @action(detail=True, methods=["get"])
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

            return Response(ResultSerializer(module_results).data)

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
