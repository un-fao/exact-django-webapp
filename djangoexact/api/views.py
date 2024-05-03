import logging
from datetime import timedelta
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth.models import Group
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db.models import Model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes
from rest_framework import permissions, viewsets
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

import api.filters as filters
import api.labels as labels
import api.utilities as utils
from api.defaults import DefaultsFactory
from api.models import CustomUser as User

from .calculators import CalculatorFactory
from .models import (
    Activity,
    Comment,
    CommentThread,
    Country,
    CustomUser,
    InputType,
    LandUseChange,
    LandUseType,
    MacroInputType,
    Module,
    ModuleType,
    Project,
    ProjectInvitation,
    StatusType,
    Submodule,
    UserProjectGroup,
)
from .serializers import (
    ActionTypes,
    ActivityBuilderSerializer,
    ActivitySerializer,
    CommentSerializer,
    CommentThreadSerializer,
    CountrySerializer,
    DynamicResultSerializer,
    EmptySerializer,
    GroupSerializer,
    InputTypeSerializer,
    LandUseTypeSerializer,
    ProjectInvitationModelSerializer,
    ProjectInvitationReadSerializer,
    ProjectInvitationWriteSerializer,
    ReadProjectSerializer,
    UserProjectGroupSerializer,
    UserReadSerializer,
    UserWriteSerializer,
    WriteActivitySerializer,
    WriteProjectSerializer,
    get_model_serializer,
    get_module_serializer,
)

logger = logging.getLogger("console")

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

climate = openapi.Parameter(
    "climate",
    openapi.IN_QUERY,
    description="Climate associated with Land Use Type",
    type=openapi.TYPE_INTEGER,
)
moisture = openapi.Parameter(
    "moisture",
    openapi.IN_QUERY,
    description="Moisture associated with Land Use Type",
    type=openapi.TYPE_INTEGER,
)
cascade = openapi.Parameter(
    "cascade",
    openapi.IN_QUERY,
    description="Include comments in thread",
    type=openapi.TYPE_BOOLEAN,
)
email = openapi.Parameter(
    "email",
    openapi.IN_BODY,
    description="Email of user to invite",
    type=openapi.TYPE_STRING,
)

module_type = openapi.Parameter(
    "module_type",
    openapi.IN_QUERY,
    description="Module id",
    type=openapi.TYPE_INTEGER,
)
macro_input_type = openapi.Parameter(
    "macro_input_type",
    openapi.IN_QUERY,
    description="Macro input type id",
    type=openapi.TYPE_INTEGER,
)


def get_modules(activity: Activity, serialized=True) -> list:
    modules = []
    module_serializers_list = []
    for module in activity.module_types.all():
        try:
            module_model = apps.get_model(utils.API, module.class_name)
        except LookupError:
            logger.warning(f"get_modules: Module {module.name} not found")
            continue
        module_object = module_model.objects.filter(activity__id=activity.pk).first()
        if module_object:
            modules.append(module_object)
            module_dict = get_module_serializer(module_model)(module_object).data
            module_serializers_list.append(module_dict)

    return module_serializers_list if serialized else modules


class BaseWiewSet(viewsets.GenericViewSet):
    def get_queryset(self):

        # If list operation, filter out inactive objects, unless ?filter_inactive=true
        if self.action == "list" and not self.request.query_params.get("filter_inactive"):
            try:
                is_active_field = self.queryset.model._meta.get_field("is_active")
                return self.queryset.filter(is_active=True)
            except FieldDoesNotExist:
                return super().get_queryset()

        return super().get_queryset()


class AuthenticatedViewSet(BaseWiewSet):
    permission_classes = [permissions.IsAuthenticated]


class PublicViewSet(BaseWiewSet):
    permission_classes = [permissions.AllowAny]


class GroupViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class UserViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserReadSerializer

    # If user is not an admin, only return the user's own data
    def get_queryset(self):
        if self.request.user.is_superuser:
            return self.queryset
        return self.queryset.filter(pk=self.request.user.pk)

    def update(self, request, *args, **kwargs):
        self.serializer_class = UserWriteSerializer
        return super().update(request, *args, **kwargs)


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

        filters["is_active"] = True

        list = LandUseType.objects.filter(**filters).all()
        serializer = get_model_serializer(LandUseType)(list, many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)


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
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        project = serializer.save()

        UserProjectGroup.objects.create(user=self.request.user, project=project, group=Group.objects.get(name="Admin"))

        read_serializer = ReadProjectSerializer(instance=project)

        return Response(read_serializer.data, status=http_status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        user = self.request.user

        if not utils.has_project_permission("delete_project", user, project):
            logging.error("Selected user does not have permission to delete the project")
            return utils.ErrorResponse("Selected user does not have permission to delete the project", status=http_status.HTTP_403_FORBIDDEN)

        if user != project.user:
            logging.error("Selected user is not the owner of the project")
            return utils.ErrorResponse("Only the owner can delete a project.", status=http_status.HTTP_403_FORBIDDEN)

        project.delete()

        return Response(status=http_status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"}, serializer_class=ReadProjectSerializer)
    def retrieve(self, request, pk=None):
        """
        Get a single project for a given user.
        """

        project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        return Response(data=ReadProjectSerializer(project).data, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"}, serializer_class=ReadProjectSerializer)
    def list(self, request):
        """
        Get all projects for a given user.
        """

        shared_projects = request.user.memberships.all()
        list = [share.project for share in shared_projects if utils.has_project_permission("view_project", self.request.user, share.project)]
        return Response(data=ReadProjectSerializer(list, many=True).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"})
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the project.
        """

        project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        serialized_project = ReadProjectSerializer(project).data

        response = serialized_project
        response["activities"] = []

        for activity in project.activities.all():
            response["activities"].append(ActivityViewSet.results(self, request, activity.pk).data)

        return Response(data=response, status=http_status.HTTP_200_OK)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        new_years = request.data.get("implementation_years", None)
        is_locking = request.data.get("is_locked")
        project: Project = self.get_object()
        user: CustomUser = self.request.user

        if not utils.has_project_permission("change_project", user, project):
            logging.error("Selected user does not have permission to update the project")
            return utils.ErrorResponse("Selected user does not have permission to update the project", status=http_status.HTTP_403_FORBIDDEN)

        # Unlock the project if it has been locked for more than 30 minutes from the last project update
        if project.is_locked and timezone.now() - project.lock_updated_at > timedelta(minutes=30):
            project.unlock()

        # If the project is not locked, or a lock is requested
        if not project.is_locked or is_locking is True:
            if project.is_locked and project.locked_by != user:
                logging.warning(f"Project is already locked by: {project.locked_by.email}")
                return Response({"message": "Project is already locked"}, status=http_status.HTTP_200_OK)

            project.lock(user)

        # If an unlock is requested
        elif is_locking is False:
            is_user_authorized = user.is_superuser or project.locked_by == user or user.memberships.filter(user=user, project=project, group__name="Admin").exists()

            if not is_user_authorized:
                logging.error("User does not have permission to unlock the project")
                return Response({"message": "User does not have permission to unlock the project"}, status=http_status.HTTP_403_FORBIDDEN)

            project.unlock()

        if new_years:
            project.implementation_years = new_years
            for activity in project.activities.all():
                if activity.duration_t2 > new_years:
                    logging.warning(f"Activity {activity.name} duration_t2 is greater than project implementation years. Setting activity duration_t2 to project implementation years.")
                    activity.duration_t2 = new_years
                    activity.save()
            project.save()

        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    @swagger_auto_schema(responses={404: "Project not found", 403: "Selected user does not have permission to copy the project", 201: ReadProjectSerializer}, request_body=EmptySerializer)
    def copy(self, request, pk=None):
        project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to copy the project")
            return utils.ErrorResponse("Selected user does not have permission to copy the project", status=http_status.HTTP_403_FORBIDDEN)

        new_project = utils.copy_project(project)
        UserProjectGroup.objects.create(user=self.request.user, project=new_project, group=Group.objects.get(name="Admin"))

        return Response(data=ReadProjectSerializer(new_project).data, status=http_status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def users(self, request, pk=None):
        project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to copy the project")
            return utils.ErrorResponse("Selected user does not have permission to copy the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = UserProjectGroupSerializer(project.members.all(), many=True)

        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view invitations", 200: ProjectInvitationReadSerializer})
    def invitations(self, request, pk=None):
        project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view invitations")
            return utils.ErrorResponse("Selected user does not have permission to view invitations", status=http_status.HTTP_403_FORBIDDEN)

        serializer = ProjectInvitationReadSerializer(project.invitations.all(), many=True)

        return Response(data=serializer.data, status=http_status.HTTP_200_OK)


class ProjectInvitationViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = ProjectInvitation.objects.all()
    serializer_class = ProjectInvitationWriteSerializer

    @swagger_auto_schema(
        operation_description="Get a single invitation by id",
        responses={
            400: "Bad request",
            403: "Selected user does not have permission to view invitations",
            200: ProjectInvitationReadSerializer,
        },
    )
    def retrieve(self, request, *args, **kwargs):
        logging.debug("START ProjectInvitationViewset.retrieve")
        invitation: ProjectInvitation = self.get_object()

        if not utils.has_project_permission("view_projectinvitation", self.request.user, invitation.project):
            logging.error("Selected user does not have permission to view invitations")
            return utils.ErrorResponse("Selected user does not have permission to view invitations", status=http_status.HTTP_403_FORBIDDEN)

        logging.debug("END ProjectInvitationViewset.retrieve")
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Invite a user to a project with a specific permission group",
        request_body=ProjectInvitationWriteSerializer,
        responses={
            400: "Bad request",
            201: "Invitation sent successfully",
            403: "Selected user does not have permission to invite users",
        },
    )
    def create(self, request, pk=None):
        logging.debug("START ProjectInvitationViewset.create")

        serializer = ProjectInvitationWriteSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        project = serializer.validated_data["project"]

        if not utils.has_project_permission("add_projectinvitation", self.request.user, project):
            logging.error("Selected user does not have permission to invite users to the project")
            return utils.ErrorResponse("Selected user does not have permission to invite users to the project", status=http_status.HTTP_403_FORBIDDEN)

        try:
            email = serializer.validated_data["email"]
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            logging.error(f"User with email {email} does not exist")
            return utils.ErrorResponse(f"User with email {email} does not exist", status=http_status.HTTP_400_BAD_REQUEST)

        group = serializer.validated_data["group"]
        invitation, created = ProjectInvitation.objects.get_or_create(project=project, user=user, group=group)

        if not created:
            logging.error(f"Invitation for {user.email} already sent with id {invitation.id}")
            return utils.ErrorResponse({"error": f"Invitation for {user.email} already sent"}, status=http_status.HTTP_400_BAD_REQUEST)

        invitation.status = "accepted"
        invitation.save()

        UserProjectGroup.objects.create(user=user, project=project, group=group)

        logging.debug("END ProjectInvitationViewset.create")
        return Response({"message": f"Invitation for {user.email} sent successfully"})

    @swagger_auto_schema(
        request_body=ProjectInvitationModelSerializer,
        responses={
            400: "Bad request",
            200: "Invitation updated successfully",
            403: "Selected user does not have permission to update invitations",
        },
    )
    def partial_update(self, request, *args, **kwargs):
        invitation = get_object_or_404(ProjectInvitation, pk=kwargs["pk"])
        data = ProjectInvitationModelSerializer(invitation, data=request.data, partial=True)

        if not utils.has_project_permission("change_projectinvitation", self.request.user, invitation.project):
            logging.error("Selected user does not have permission to update invitations")
            return utils.ErrorResponse("Selected user does not have permission to update invitations", status=http_status.HTTP_403_FORBIDDEN)

        if not data.is_valid():
            return Response(data.errors, status=http_status.HTTP_400_BAD_REQUEST)

        if invitation.status == "declined" or invitation.status == "accepted":
            logger.warning(f"Invitation already {invitation.status}. No further action is possible.")
            return Response({"message": f"Invitation already {invitation.status}. No further action is possible."}, status=http_status.HTTP_200_OK)

        new_status = data.validated_data.get("status", None)

        if new_status == invitation.status:
            logger.warning(f"Invitation already {new_status}")
            return Response({"message": f"Invitation already {new_status}"}, status=http_status.HTTP_200_OK)

        if new_status == "accepted":
            UserProjectGroup.objects.create(user=self.request.user, project=invitation.project, group=invitation.group)

        invitation.status = new_status
        invitation.save()

        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        manual_parameters=[project_id],
        responses={
            400: "Bad request",
            200: ProjectInvitationReadSerializer,
            403: "Selected user does not have permission to delete invitations",
        },
    )
    def list(self, request, *args, **kwargs):
        project_id = self.request.query_params.get("project_id", None)

        if not project_id:
            logging.error("Project id not provided")
            return utils.ErrorResponse("Project id not provided", status=http_status.HTTP_400_BAD_REQUEST)

        project = get_object_or_404(Project, pk=project_id)

        if not utils.has_project_permission("view_projectinvitation", self.request.user, project):
            logging.error("Selected user does not have permission to view invitations")
            return utils.ErrorResponse("Selected user does not have permission to view invitations", status=http_status.HTTP_403_FORBIDDEN)

        serializer = ProjectInvitationReadSerializer(project.invitations.all(), many=True)

        return Response(serializer.data, status=http_status.HTTP_200_OK)


class ActivityViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows activities to be viewed or edited.
    """

    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer

    def update(self, request, *args, **kwargs):
        activity = self.get_object()

        if not utils.has_project_permission("change_activity", self.request.user, activity.project):
            logging.error("Selected user does not have permission to update activities in the project")
            return utils.ErrorResponse("Selected user does not have permission to update activities in the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = WriteActivitySerializer(data=request.data, instance=activity)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        activity = serializer.save()

        read_serializer = ActivitySerializer(instance=activity)

        return Response(read_serializer.data, status=http_status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        activity = self.get_object()

        if not utils.has_project_permission("change_activity", self.request.user, activity.project):
            logging.error("Selected user does not have permission to update activities in the project")
            return utils.ErrorResponse("Selected user does not have permission to update activities in the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = WriteActivitySerializer(data=request.data, partial=True, instance=activity)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        activity = serializer.save()

        read_serializer = ActivitySerializer(instance=activity)

        return Response(read_serializer.data, status=http_status.HTTP_200_OK)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        _status = StatusType.objects.get_or_create(name="EMPTY")[0]
        request.data["status"] = _status.pk
        serializer = WriteActivitySerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        if not utils.has_project_permission("add_activity", self.request.user, serializer.validated_data["project"]):
            logging.error("Selected user does not have permission to add activities to the project")
            return utils.ErrorResponse("Selected user does not have permission to add activities to the project", status=http_status.HTTP_403_FORBIDDEN)

        activity = serializer.save()

        read_serializer = ActivitySerializer(instance=activity)

        return Response(read_serializer.data, status=http_status.HTTP_201_CREATED)

    @swagger_auto_schema(manual_parameters=[project_id], responses={400: "activity_id not provided"})
    def retrieve(self, request, pk=None):
        """
        Get a single activity for a given user.
        """
        logger.info("ActivityViewSet.retrieve")
        activity = get_object_or_404(Activity, pk=pk)

        if not utils.has_project_permission("view_activity", self.request.user, activity.project):
            logging.error("Selected user does not have permission to view the activity")
            return utils.ErrorResponse("Selected user does not have permission to view the activity", status=http_status.HTTP_403_FORBIDDEN)

        activity_dict = ActivitySerializer(activity).data
        activity_dict["modules"] = get_modules(activity)

        return Response(data=activity_dict, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(
        manual_parameters=[project_id],
        responses={
            400: "activity_id not provided",
            403: "Selected user does not have permission to view activities in the project",
            200: ActivitySerializer(many=True),
        },
    )
    def list(self, request):
        """
        Get all activities for a given project, by filtering against a `project_id` query parameter in the URL.
        """
        logger.info("ActivityViewSet.list")
        project_id = utils.get_query_param_or_validation_error(self.request, "project_id")
        project = get_object_or_404(Project, pk=project_id)

        if not utils.has_project_permission("view_activity", self.request.user, project):
            logging.error("Selected user does not have permission to view activities in the project")
            return utils.ErrorResponse("Selected user does not have permission to view activities in the project", status=http_status.HTTP_403_FORBIDDEN)

        list = Activity.objects.filter(project__id=project_id)

        response = []

        for activity in list:
            activity_dict = ActivitySerializer(activity).data
            activity_dict["modules"] = get_modules(activity)
            response.append(activity_dict)

        return Response(data=response, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the activity.
        """

        activity = get_object_or_404(Activity, pk=pk)

        if not utils.has_project_permission("view_activity", self.request.user, activity.project):
            logging.error("Selected user does not have permission to view the activity")
            return utils.ErrorResponse("Selected user does not have permission to view the activity", status=http_status.HTTP_403_FORBIDDEN)

        response = {**ActivitySerializer(activity).data}

        modules = []
        # TODO: Make a serializer for this
        for module in activity.module_types.all():
            try:
                model_ref = apps.get_model(utils.API, module.class_name)
            except LookupError:
                logger.warning(f"Module {module.name} not found")
                continue

            object = getattr(activity, module.class_name.lower(), None).first()

            if not object or (object.status and object.status.name != "READY"):
                continue

            module_dict = get_module_serializer(model_ref)(object).data

            try:
                viewset = generic_module_viewset(model_ref).results(self, request, pk=object.pk)
                module_dict[labels.RESULTS] = viewset.data

            except Exception as e:
                logger.error("Error calculating result in ActivityViewSet.results", e)
                module_dict[labels.RESULTS] = utils.error(str(e))

            modules.append(module_dict)

        response["modules"] = modules

        return Response(response)

    @action(detail=True, methods=["get"])
    def modules(self, request, pk=None):
        """
        Lists the modules of a given activity.
        """

        activity = get_object_or_404(Activity, pk=pk)

        if not utils.has_project_permission("view_activity", self.request.user, activity.project):
            logging.error("Selected user does not have permission to view the activity")
            return utils.ErrorResponse("Selected user does not have permission to view the activity", status=http_status.HTTP_403_FORBIDDEN)

        modules = get_modules(activity)

        return Response(data=modules, status=http_status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    @swagger_auto_schema(
        request_body=ActivityBuilderSerializer,
        responses={400: "Bad request", 200: ActivitySerializer},
    )
    @transaction.atomic
    def build(self, request):
        """
        Builds a new activity and the modules associated with it.
        """

        serializer = ActivityBuilderSerializer(data=request.data)

        if not serializer.is_valid():
            return utils.ErrorResponse(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        project = serializer.validated_data["project"]

        if not utils.has_project_permission("add_activity", self.request.user, project):
            logging.error("Selected user does not have permission to add activities to the project")
            return utils.ErrorResponse("Selected user does not have permission to add activities to the project", status=http_status.HTTP_403_FORBIDDEN)

        try:
            activity = serializer.save()
        except ValidationError as e:
            return utils.ErrorResponse(e.detail, status=http_status.HTTP_400_BAD_REQUEST)

        return Response(ActivitySerializer(activity).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    @swagger_auto_schema(responses={404: "Project not found", 403: "Selected user does not have permission to copy the activity", 201: ActivitySerializer}, request_body=EmptySerializer)
    def copy(self, request, pk=None):
        activity = self.get_object()

        if not utils.has_project_permission("view_activity", self.request.user, activity.project):
            logging.error("Selected user does not have permission to copy the activity")
            return utils.ErrorResponse("Selected user does not have permission to copy the activity", status=http_status.HTTP_403_FORBIDDEN)

        new_activity = utils.copy_activity(activity)

        return Response(data=ActivitySerializer(new_activity).data, status=http_status.HTTP_201_CREATED)


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

        return Response(data=CommentSerializer(comments, many=True).data, status=http_status.HTTP_200_OK)


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        queryset = Comment.objects.all()
        parent = self.request.query_params.get("parent", None)
        if parent is not None:
            queryset = queryset.filter(parent=parent)
        else:
            queryset = queryset.filter(parent__isnull=True)
        return queryset

    @action(detail=True, methods=["get"])
    def replies(self, request, thread_id=None, pk=None):
        """
        Lists the replies of a given comment.
        """

        comment = get_object_or_404(Comment, pk=pk)
        replies = comment.replies.all()

        return Response(data=CommentSerializer(replies, many=True).data, status=http_status.HTTP_200_OK)


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
            return Response(data=serializer.data, status=http_status.HTTP_200_OK)

        return super().list(request)


class CountryViewSet(viewsets.ModelViewSet, PublicViewSet):
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
            return Response(data=serializer.data, status=http_status.HTTP_200_OK)

        return super().list(request)


class InputTypeViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows input types to be viewed or edited.
    """

    queryset = InputType.objects.all()
    serializer_class = InputTypeSerializer

    @swagger_auto_schema(manual_parameters=[macro_input_type])
    def list(self, request):
        """
        Get all input types.
        """

        macro_input_type_id = self.request.query_params.get("macro_input_type", None)

        if macro_input_type_id:
            input_types = InputType.objects.filter(macro_input_type__id=macro_input_type_id).all()
        else:
            input_types = InputType.objects.all()

        serializer = get_model_serializer(InputType)(input_types, many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)


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

            module: Module = self.get_object()
            module_type = ModuleType.objects.get(class_name=model.__name__)

            activity = module.parent.activity if module_type.is_submodule else module.activity

            if not utils.has_project_permission("can_change_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to update this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to update this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            serializer = get_module_serializer(model, action=ActionTypes.CREATE)(data=request.data, instance=module)

            if not serializer.is_valid():
                return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

            module = serializer.save()

            read_serializer = get_module_serializer(model)(instance=module, context={"request": request})

            return Response(read_serializer.data, status=http_status.HTTP_200_OK)

        def partial_update(self, request, *args, **kwargs):
            """
            Partially updates a module.
            """

            module: Module = self.get_object()
            module_type = ModuleType.objects.get(class_name=model.__name__)

            activity = module.parent.activity if module_type.is_submodule else module.activity

            if not utils.has_project_permission("can_change_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to update this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to update this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            serializer = get_module_serializer(model, action=ActionTypes.CREATE)(data=request.data, partial=True, instance=module)

            if not serializer.is_valid():
                return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

            module = serializer.save()

            read_serializer = get_module_serializer(model)(instance=module, context={"request": request})

            return Response(read_serializer.data, status=http_status.HTTP_200_OK)

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
                return Response(module_serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

            module_type = ModuleType.objects.get(class_name=model.__name__)

            if module_type.is_submodule:
                activity = module_serializer.validated_data["parent"].activity
            else:
                activity = module_serializer.validated_data["activity"]

            if not utils.has_project_permission("can_create_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to add this module to the project")
                return utils.ErrorResponse("Selected user does not have permission to add this module to the project", status=http_status.HTTP_403_FORBIDDEN)

            module_serializer.save()

            utils.create_module_threads(module_serializer.instance)

            read_serializer = get_module_serializer(model)(instance=module_serializer.instance)

            logging.debug(f"END GenericModuleViewSet[{model.__name__}].create")

            return Response(read_serializer.data, status=http_status.HTTP_201_CREATED)

        @swagger_auto_schema(manual_parameters=[activity_id, module_type])
        def list(self, request):
            """
            Lists the module(s) of a given activity
            by filtering against an `activity_id` query parameter in the URL or
            by filtering against the 'module_type' query parameter in the URL.
            """

            activity_id = utils.get_query_param_or_validation_error(self.request, "activity")
            activity = get_object_or_404(Activity, pk=activity_id)

            if not utils.has_project_permission("can_view_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to view this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to view this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            module_type = ModuleType.objects.get(class_name=model.__name__)

            if module_type.is_submodule:
                modules = model.objects.filter(parent__activity__id=activity_id).all()
            else:
                modules = model.objects.filter(activity__id=activity_id).all()

            data = []

            for i, module in enumerate(modules):
                serializer = get_module_serializer(model)(instance=module)
                data.append({**serializer.data})

            return Response(data)

        @action(detail=True, methods=["get"])
        def results(self, request, pk=None):
            """
            Calculates and returns total emissions for a single module.
            """

            module: Module = get_object_or_404(model, pk=pk)
            module_type = ModuleType.objects.get(class_name=model.__name__)

            activity: Activity = module.parent.activity if module_type.is_submodule else module.activity

            if not utils.has_project_permission("can_view_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to view this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to view this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            serializer = get_module_serializer(model)(instance=module)
            if not serializer.validate(module.__dict__):
                return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

            if module_type.class_name == LandUseChange.__name__:

                status_start = utils.get_module_status(self, activity, module.module_type_start)
                status_w = utils.get_module_status(self, activity, module.module_type_w)
                status_wo = utils.get_module_status(self, activity, module.module_type_wo)

                if not all(status == StatusType.objects.get(name="READY") for status in [status_start, status_w, status_wo]):
                    return utils.ErrorResponse("Not all modules are ready. Land Use Change module cannot be calculated.")
            else:
                status: StatusType = module.status

                if not status or status.name != "READY":
                    return utils.ErrorResponse("Module is not ready. Cannot calculate result.")

            try:
                aggregate_by = BreakdownTypes(request.query_params.get("aggregate", BreakdownTypes.TOTAL))
                results_w, results_wo, results_tot = CalculatorFactory().calculate_result(module, aggregate_by=aggregate_by)

                module_results = {
                    "total_w": results_w,
                    "total_wo": results_wo,
                    "balance": results_tot,
                }

                serializer = DynamicResultSerializer(module_results, aggregate_by=aggregate_by)
                serialized_data = serializer.data

                return Response(serialized_data)

            except Exception as e:
                logging.error("Error calculating result in GenericModuleViewSet.results", e)
                return utils.ErrorResponse(str(e))

        @action(detail=True, methods=["get"])
        def defaults(self, request, pk=None):
            """
            Returns the default values for a module.

            ex. GET /annual-croplands/1/defaults/
            """
            module_type = ModuleType.objects.get(class_name=model.__name__)

            if module_type.is_submodule:
                module: Submodule = get_object_or_404(model, pk=pk, parent__activity__project__user=self.request.user)
                activity = module.parent.activity
                if module.parent.status.name != "READY":
                    return utils.ErrorResponse("Parent module is not ready. Cannot fetch defaults.")

            else:
                module: Module = get_object_or_404(model, pk=pk, activity__project__user=self.request.user)
                activity = module.activity
                # TODO: Maybe move all status checks to middleware
                if module.status.name != "READY":
                    return utils.ErrorResponse("Module is not ready. Cannot fetch defaults.")

            if not utils.has_project_permission("can_view_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to view this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to view this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            try:
                defaults: SimpleNamespace = DefaultsFactory.get_defaults(module, calculate=True)
                return Response(defaults.__dict__)
            except Exception as e:
                return utils.ErrorResponse(str(e))

    return GenericModuleViewSet


def generic_viewset(model: Model):
    class GenericViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_model_serializer(model)
        filterset_class = filters.get_model_filter(model)

    return GenericViewSet


def public_generic_viewset(model: Model):
    class PublicGenericViewSet(viewsets.ModelViewSet, PublicViewSet):
        queryset = model.objects.all()
        serializer_class = get_model_serializer(model)

    return PublicGenericViewSet
