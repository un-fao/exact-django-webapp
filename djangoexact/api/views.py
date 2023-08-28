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


activity_id = openapi.Parameter(
    "activity_id",
    openapi.IN_QUERY,
    description="ID of activity related to the module",
    type=openapi.TYPE_INTEGER,
)
project_id = openapi.Parameter(
    "project_id",
    openapi.IN_QUERY,
    description="ID of project related to the activity",
    type=openapi.TYPE_INTEGER,
)
include_related = openapi.Parameter(
    "include_related",
    openapi.IN_QUERY,
    description="Include related modules",
    type=openapi.TYPE_BOOLEAN,
)
parent = openapi.Parameter(
    "parent", openapi.IN_QUERY, description="Parent name", type=openapi.TYPE_STRING
)
cascade = openapi.Parameter(
    "cascade",
    openapi.IN_QUERY,
    description="Include comments in thread",
    type=openapi.TYPE_BOOLEAN,
)


def get_modules(activity, serialized=True):
    modules = []
    modules_dict = []
    module_types = ModuleType.objects.all()
    for module in module_types:
        module_model = apps.get_model(API, sanitize_for_model(module.name))
        module_object = module_model.objects.filter(activity__id=activity.pk).first()
        if module_object:
            modules.append(module_object)
            module_dict = get_module_serializer(module_model)(module_object).data
            modules_dict.append(module_dict)

    return modules_dict if serialized else modules


class AuthenticatedViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]


class LandUseTypeViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows land use types to be viewed or edited.
    """

    queryset = LandUseType.objects.all()
    serializer_class = get_model_serializer(LandUseType)

    # Modify get method to accept OPTIONAL query parameter 'module' to return land use types for a given module
    @swagger_auto_schema(
        manual_parameters=[parent],
        responses={404: "No land use types found for parent"},
    )
    def list(self, request):
        """
        Get all land use types, or all land use types for a given parent, by filtering against a `parent` query parameter in the URL.
        """
        parent = self.request.query_params.get("parent", None)
        if parent:
            land_use_types = LandUseType.objects.filter(parent__name=parent).order_by(
                "name"
            )
            if not land_use_types:
                return ErrorResponse(
                    f"No land use types found for parent: {parent}",
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                data=get_model_serializer(LandUseType)(land_use_types, many=True).data,
                status=status.HTTP_200_OK,
            )

        return super().list(request)


class ProjectViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    @swagger_auto_schema(
        manual_parameters=[project_id], responses={404: "Project not found"}
    )
    def retrieve(self, request, pk=None):
        """
        Get a single project for a given user.
        """
        project = get_object_or_404(Project, pk=pk, user=self.request.user)
        return Response(
            data=ProjectSerializer(project).data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        manual_parameters=[project_id], responses={404: "Project not found"}
    )
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
    @swagger_auto_schema(
        manual_parameters=[project_id], responses={404: "Project not found"}
    )
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

            project_results.add(Result(**activity_results[RESULTS]))

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

    @swagger_auto_schema(
        manual_parameters=[project_id], responses={400: "activity_id not provided"}
    )
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

    @swagger_auto_schema(
        manual_parameters=[project_id], responses={400: "activity_id not provided"}
    )
    def list(self, request):
        """
        Get all activities for a given project, by filtering against a `project_id` query parameter in the URL.
        """
        print("list")
        project_id = get_query_param_or_validation_error(self.request, "project_id")
        list = Activity.objects.filter(
            project__id=project_id, project__user=self.request.user
        )

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
            model_ref = apps.get_model(API, sanitize_for_model(module.name))
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

        get_object_or_404(Activity, pk=pk, project__user=self.request.user)

        modules = []
        module_types = ModuleType.objects.all()

        for module in module_types:
            module_model = apps.get_model(API, sanitize_for_model(module.name))
            module_object = module_model.objects.filter(
                activity__id=pk, activity__project__user=self.request.user
            ).first()
            if module_object:
                modules.append(get_module_serializer(module_model)(module_object).data)

        return Response(data=modules, status=status.HTTP_200_OK)

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


def generic_module_viewset(model: Model):
    class GenericModuleViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_module_serializer(model)

        @transaction.atomic
        def create(self, request):
            """
            Creates a new module for a given activity.
            """

            module_serializer = self.serializer_class(data=request.data)
            if module_serializer.is_valid():
                activity_id = module_serializer.validated_data["activity"].pk

                for attr in dir(model):
                    if attr.endswith("_thread"): # NOTE: This could create problems if any other attribute ends in "_thread"
                        module_serializer.validated_data[attr] = CommentThread.objects.create()

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

            activity_id = get_query_param_or_validation_error(self.request, "activity_id")

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
