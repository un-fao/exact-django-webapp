import os
import logging
from datetime import timedelta
from types import SimpleNamespace
import uuid
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.shortcuts import render

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
from simple_history.utils import update_change_reason
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
import django_filters
from rest_framework import filters
from rest_framework.exceptions import PermissionDenied


import api.filters as api_filters
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
    ProjectMembership,
    InvitationStatusType,
    Definition,
    Note,
    FieldDefinition,
    LandModule,
    CachedResultMixin,
    ProjectTag,
)
from .serializers import (
    ActionTypes,
    ModuleResultSerializer,
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
    ProjectInvitationModelReadSerializer,
    ProjectInvitationReadSerializer,
    ProjectInvitationWriteSerializer,
    ReadProjectSerializer,
    ProjectMembershipSerializer,
    UserReadSerializer,
    UserWriteSerializer,
    WriteActivitySerializer,
    WriteProjectSerializer,
    get_model_serializer,
    get_module_serializer,
    ChangeHistorySerializer,
    ProjectInvitationModelWriteSerializer,
    ProjectInvitationModelReadSerializer,
    NewNoteSerializer,
    NoteSerializer,
    ActivitySerializerWithModules,
    ResetPasswordSerializer,
    FieldDefinitionResponseSerializer,
    FieldDefinitionSerializer,
    ProjectResultSerializer,
    ActivityResultSerializer,
    ProjectSummarySerializer,
    ActivitySummarySerializer,
    ProjectTagSerializer,
)

from djangoexact.settings import auth
from django.utils.translation import activate, get_language, deactivate
from firebase_admin import auth as firebase_admin_auth
from django.contrib.auth import logout
from auditlog.context import disable_auditlog, LogEntry
from django.utils import translation
from django.db import connection
import time
import api.reports as reports
from django.http import FileResponse
from django.http import HttpResponse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.test import RequestFactory
import asyncio
from asgiref.sync import sync_to_async
from django.utils.text import slugify


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

page_size = openapi.Parameter(
    "page_size",
    openapi.IN_QUERY,
    description="Number of items per page",
    type=openapi.TYPE_INTEGER,
)
page = openapi.Parameter(
    "page",
    openapi.IN_QUERY,
    description="Page number",
    type=openapi.TYPE_INTEGER,
)
name = openapi.Parameter("name", openapi.IN_QUERY, description="Name of the project", type=openapi.TYPE_STRING)


def get_modules(activity: Activity, serialized=True) -> list:
    modules = activity.modules
    module_serializers_list = []

    for module in modules:
        module_dict = get_module_serializer(module.__class__)(module).data
        module_serializers_list.append(module_dict)

    return module_serializers_list if serialized else modules


class DefaultPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


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

    @transaction.atomic
    def destroy(self, request, pk=None):
        logging.info("Deleting user")
        user: CustomUser = CustomUser.objects.get(pk=pk)
        if user == self.request.user or self.request.user.is_superuser or self.request.user.is_staff:
            LogEntry.objects.log_create(user, force_log=True, action=LogEntry.Action.DELETE)
            with disable_auditlog():
                ProjectInvitation.objects.filter(user=user).delete()
                ProjectMembership.objects.filter(user=user).delete()
                user.delete()
            firebase_admin_auth.delete_user(user.firebase_uid)
            return Response(status=http_status.HTTP_204_NO_CONTENT)

        return utils.ErrorResponse("Selected user does not have permission to delete the user", status=http_status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=["post"], url_path="reset-password")
    @swagger_auto_schema(request_body=ResetPasswordSerializer, responses={400: "Bad request", 200: "Password reset successfully"})
    @transaction.atomic
    def reset_password(self, request, pk=None):
        user: CustomUser = self.get_object()

        serializer = ResetPasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        new_password = serializer.validated_data["password_new"]

        user.set_password(new_password)
        user.save()

        try:
            # NOTE: This makes the refresh token invalid but the current access token remains valid
            firebase_admin_auth.update_user(user.firebase_uid, password=new_password)
            firebase_admin_auth.revoke_refresh_tokens(user.firebase_uid)
        except Exception as e:
            return utils.ErrorResponse(str(e), status=http_status.HTTP_400_BAD_REQUEST)

        return Response(status=http_status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def whoami(self, request):
        return Response(UserReadSerializer(request.user).data, status=http_status.HTTP_200_OK)


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
    pagination_class = DefaultPagination

    @transaction.atomic
    @swagger_auto_schema(responses={400: "Bad request", 201: ReadProjectSerializer})
    def create(self, request, *args, **kwargs):
        """
        Creates a new project for a given user.
        """

        request.data["user"] = self.request.user.pk
        serializer = self.serializer_class(data=request.data, context={"request": request})

        if not serializer.is_valid():
            logging.error("Error creating project:", serializer.errors)
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        project = serializer.save()
        update_change_reason(project, utils.ChangeReasons.CREATE.value)

        ProjectMembership.objects.create(user=self.request.user, project=project, group=Group.objects.get(name="Admin"))
        read_serializer = ReadProjectSerializer(instance=project, context={"request": request})

        return Response(read_serializer.data, status=http_status.HTTP_201_CREATED)

    @transaction.atomic
    @swagger_auto_schema(responses={400: "Bad request", 204: "Project deleted successfully"})
    def destroy(self, request, *args, **kwargs):
        project: Project = self.get_object()
        user = self.request.user

        if not utils.has_project_permission("delete_project", user, project):
            logging.error("Selected user does not have permission to delete the project")
            return utils.ErrorResponse("Selected user does not have permission to delete the project", status=http_status.HTTP_403_FORBIDDEN)

        # NOTE: This is a workaround for a bug in the simple_history library caused by an unhandled AttributeError when deleting a project with no previous history
        if project.history.count() > 0:
            update_change_reason(project, utils.ChangeReasons.DELETE.value)

        is_deleted = self.raw_delete(project)
        if not is_deleted:
            return utils.ErrorResponse("Error deleting project", status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=http_status.HTTP_204_NO_CONTENT)

    def raw_delete(self, project: Project):
        with connection.cursor() as cursor:
            project.members.all().delete()
            project.invitations.all().delete()

            # Delete all activities
            activities = project.activities.all()
            for activity in activities:
                for m in activity.modules:
                    if hasattr(m, "submodules"):
                        for sm in m.submodules:
                            cursor.execute(f"DELETE FROM {sm._meta.db_table} WHERE id = %s", [sm.id])
                    cursor.execute(f"DELETE FROM {m._meta.db_table} WHERE id = %s", [m.id])
                LandUseChange.objects.filter(activity=activity).delete()
                cursor.execute("DELETE FROM api_activity_module_types WHERE activity_id = %s", [activity.id])
                cursor.execute("DELETE FROM api_activity WHERE id = %s", [activity.id])

            cursor.execute("DELETE FROM api_project WHERE id = %s", [project.id])

        return True

    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"}, serializer_class=ReadProjectSerializer)
    def retrieve(self, request, pk=None):
        """
        Get a single project for a given user.
        """

        project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        return Response(data=ReadProjectSerializer(project, context={"request": request}).data, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(manual_parameters=[name], responses={404: "Project not found"}, serializer_class=ReadProjectSerializer)
    def list(self, request):
        """
        Get all projects for a given user.
        """

        search_query = request.query_params.get("name", None)
        is_summary = request.query_params.get("summary", False)

        filters = {}
        if search_query:
            filters["project__name__icontains"] = search_query

        shared_projects = request.user.memberships.filter(**filters).all()
        projects_list = [share.project for share in shared_projects if utils.has_project_permission("view_project", self.request.user, share.project)]
        ordered_projects = sorted(projects_list, key=lambda x: x.created_at, reverse=True)

        SerializerClass = ReadProjectSerializer
        if is_summary:
            SerializerClass = ProjectSummarySerializer

        def serialize_project(project):
            return SerializerClass(project, context={"request": request}).data

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(ordered_projects, request)
        if page is not None:
            with ThreadPoolExecutor(max_workers=10) as executor:
                response = list(executor.map(serialize_project, page))
            return paginator.get_paginated_response(response)

        return Response(data=SerializerClass(ordered_projects, many=True, context={"request": request}).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"})
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the project.
        """

        project = Project.objects.prefetch_related("activities").get(pk=pk)

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        serialized_project = ProjectResultSerializer(project, context={"request": request}).data

        response = serialized_project
        response["activities"] = []

        # Function to process an activity
        def process_activity(activity_pk):
            return ActivityViewSet.results(self, request, pk=activity_pk).data

        activity_pks = [activity.pk for activity in project.activities.all()]

        # Use ThreadPoolExecutor to run tasks in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all tasks to the executor
            future_to_pk = {executor.submit(process_activity, pk): pk for pk in activity_pks}

            for future in as_completed(future_to_pk):
                pk = future_to_pk[future]
                try:
                    data = future.result()
                except Exception as exc:
                    logging.error(f"Activity {pk} generated an exception: {exc}")
                    # You can choose to handle exceptions differently if needed
                else:
                    response["activities"].append(data)

        return Response(data=response, status=http_status.HTTP_200_OK)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        project: Project = self.get_object()
        user: CustomUser = self.request.user

        if not utils.has_project_permission("change_project", user, project):
            logging.error("Selected user does not have permission to update the project")
            return utils.ErrorResponse("Selected user does not have permission to update the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = self.serializer_class(project, data=request.data, partial=True, context={"request": request})
        if not serializer.is_valid():
            logging.error("Error updating project:", serializer.errors)
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save()
        update_change_reason(project, utils.ChangeReasons.UPDATE.value)

        return Response(ReadProjectSerializer(project, context={"request": request}).data, status=http_status.HTTP_200_OK)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        project: Project = self.get_object()
        user: CustomUser = self.request.user

        if not utils.has_project_permission("change_project", user, project):
            logging.error("Selected user does not have permission to update the project")
            return utils.ErrorResponse("Selected user does not have permission to update the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = self.serializer_class(project, data=request.data, context={"request": request})
        if not serializer.is_valid():
            logging.error("Error updating project:", serializer.errors)
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save()
        update_change_reason(project, utils.ChangeReasons.UPDATE.value)

        return Response(ReadProjectSerializer(project, context={"request": request}).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={404: "Project not found", 403: "Selected user does not have permission to view project results"})
    def report(self, request, pk=None):
        project: Project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        if not project.is_ready():
            logging.error("Project is not ready")
            return utils.ErrorResponse("To get a report for a project, all activities must have been completed.", status=http_status.HTTP_400_BAD_REQUEST)

        report = reports.BaseProjectReport(project)
        _, file_bytes_buffer = report.build_report()
        report.close_file()

        try:
            response = HttpResponse(file_bytes_buffer, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f'attachment; filename="{project.name}_report.xlsx"'

            return response
        except FileNotFoundError:
            return utils.ErrorResponse("Error generating report: file not found", status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return utils.ErrorResponse(str(e), status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"])
    @swagger_auto_schema(responses={404: "Project not found", 403: "Selected user does not have permission to copy the project", 201: ReadProjectSerializer}, request_body=EmptySerializer)
    def copy(self, request, pk=None):
        project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to copy the project")
            return utils.ErrorResponse("Selected user does not have permission to copy the project", status=http_status.HTTP_403_FORBIDDEN)

        new_project = utils.copy_project(project)
        ProjectMembership.objects.create(user=self.request.user, project=new_project, group=Group.objects.get(name="Admin"))

        return Response(data=ReadProjectSerializer(new_project, context={"request": request}).data, status=http_status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view project memberships", 200: ProjectMembershipSerializer})
    def memberships(self, request, pk=None):
        project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to copy the project")
            return utils.ErrorResponse("Selected user does not have permission to copy the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = ProjectMembershipSerializer(project.members.all(), many=True)

        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    # TODO: Remove this action when the frontend is updated
    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view project memberships", 200: ProjectMembershipSerializer})
    def users(self, request, pk=None):
        return self.memberships(request, pk)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view invitations", 200: ProjectInvitationReadSerializer})
    def invitations(self, request, pk=None):
        project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view invitations")
            return utils.ErrorResponse("Selected user does not have permission to view invitations", status=http_status.HTTP_403_FORBIDDEN)

        serializer = ProjectInvitationReadSerializer(project.invitations.all(), many=True)

        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "The current user does not have permission to view project changes", 200: ChangeHistorySerializer})
    def history(self, request, pk=None):
        project: Project = self.get_object()

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        changes = utils.get_changes(project.history.all())

        return Response(data=ChangeHistorySerializer(changes, many=True).data, status=http_status.HTTP_200_OK)


class ProjectMembershipViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = ProjectMembership.objects.all()
    serializer_class = ProjectMembershipSerializer

    @swagger_auto_schema(
        operation_description="Get a single project membership by id",
        responses={
            400: "Bad request",
            403: "Selected user does not have permission to view project memberships",
            200: ProjectMembershipSerializer,
        },
    )
    def retrieve(self, request, *args, **kwargs):
        membership: ProjectMembership = self.get_object()

        if not utils.has_project_permission("view_projectmembership", self.request.user, membership.project):
            logging.error("Selected user does not have permission to view project memberships")
            return utils.ErrorResponse("Selected user does not have permission to view project memberships", status=http_status.HTTP_403_FORBIDDEN)

        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Get all project memberships for a given project",
        responses={
            400: "Bad request",
            403: "Selected user does not have permission to view project memberships",
            200: ProjectMembershipSerializer,
        },
    )
    def list(self, request, *args, **kwargs):
        project_id = self.request.query_params.get("project_id", None)

        if not project_id:
            logging.error("Project id not provided")
            return utils.ErrorResponse("Project id not provided", status=http_status.HTTP_400_BAD_REQUEST)

        project = get_object_or_404(Project, pk=project_id)

        if not utils.has_project_permission("view_projectmembership", self.request.user, project):
            logging.error("Selected user does not have permission to view project memberships")
            return utils.ErrorResponse("Selected user does not have permission to view project memberships", status=http_status.HTTP_403_FORBIDDEN)

        serializer = ProjectMembershipSerializer(project.members.all(), many=True)

        return Response(serializer.data, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Create a new project membership",
        request_body=ProjectMembershipSerializer,
        responses={
            400: "Bad request",
            201: "Project membership created successfully",
            403: "Selected user does not have permission to add project memberships",
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = ProjectMembershipSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        project = serializer.validated_data["project"]

        if not utils.has_project_permission("add_projectmembership", self.request.user, project):
            logging.error("Selected user does not have permission to add project memberships")
            return utils.ErrorResponse("Selected user does not have permission to add project memberships", status=http_status.HTTP_403_FORBIDDEN)

        membership = serializer.save()

        return Response(ProjectMembershipSerializer(membership).data, status=http_status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_description="Update a project membership",
        request_body=ProjectMembershipSerializer,
        responses={
            400: "Bad request",
            200: "Project membership updated successfully",
            403: "Selected user does not have permission to change project memberships",
        },
    )
    def update(self, request, *args, **kwargs):
        membership = self.get_object()

        if not utils.has_project_permission("change_projectmembership", self.request.user, membership.project):
            logging.error("Selected user does not have permission to change project memberships")
            return utils.ErrorResponse("Selected user does not have permission to change project memberships", status=http_status.HTTP_403_FORBIDDEN)

        serializer = ProjectMembershipSerializer(data=request.data, instance=membership)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save()

        return Response(ProjectMembershipSerializer(membership).data, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Delete a project membership",
        responses={
            400: "Bad request",
            204: "Project membership deleted successfully",
            403: "Selected user does not have permission to delete project memberships",
        },
    )
    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()

        if membership.user == self.request.user and membership.project.owner != self.request.user:
            membership.delete()
        elif not utils.has_project_permission("delete_projectmembership", self.request.user, membership.project):
            logging.error("Selected user does not have permission to delete project memberships")
            return utils.ErrorResponse("Selected user does not have permission to delete project memberships", status=http_status.HTTP_403_FORBIDDEN)

        membership.delete()

        return Response(status=http_status.HTTP_204_NO_CONTENT)


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

        project: Project = serializer.validated_data["project"]

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
        invitation = ProjectInvitation.objects.filter(project=project, user=user, group=group).first()

        if invitation:
            logging.warning(f"Invitation for {user.email} already sent with id {invitation.id}")
            return Response({"message": f"Invitation for {user.email} already sent for group {invitation.group.name}"}, status=http_status.HTTP_200_OK)

        invitation = ProjectInvitation(project=project, user=user, group=group)
        invitation.status = InvitationStatusType.objects.get(name_en=utils.InvitationStatus.PENDING.value)
        invitation.save()

        invitation_link = reverse("project-invitations-accept", args=[invitation.token])
        send_mail(
            f"You have been invited to join the project {project.name}",
            f"Click the link to accept the invitation: {request.build_absolute_uri(invitation_link)}",
            settings.EMAIL_HOST_USER,
            [invitation.user.email],
        )

        logging.debug("END ProjectInvitationViewset.create")
        return Response({"message": f"Invitation for {user.email} sent successfully", "id": invitation.id}, status=http_status.HTTP_201_CREATED)

    @swagger_auto_schema(
        request_body=ProjectInvitationModelReadSerializer,
        responses={
            400: "Bad request",
            200: "Invitation updated successfully",
            403: "Selected user does not have permission to update invitations",
        },
    )
    def partial_update(self, request, *args, **kwargs):
        invitation = get_object_or_404(ProjectInvitation, pk=kwargs["pk"])
        data = ProjectInvitationModelWriteSerializer(invitation, data=request.data, partial=True)

        if not utils.has_project_permission("change_projectinvitation", self.request.user, invitation.project):
            logging.error("Selected user does not have permission to update invitations")
            return utils.ErrorResponse("Selected user does not have permission to update invitations", status=http_status.HTTP_403_FORBIDDEN)

        if not data.is_valid():
            return Response(data.errors, status=http_status.HTTP_400_BAD_REQUEST)

        if invitation.status == "declined" or invitation.status == "accepted":
            logger.warning(f"Invitation already {invitation.status.name}. No further action is possible.")
            return Response({"message": f"Invitation already {invitation.status.name}. No further action is possible."}, status=http_status.HTTP_200_OK)

        new_status = data.validated_data.get("status", None)

        if new_status == invitation.status:
            logger.warning(f"Invitation already {new_status.name}")
            return Response({"message": f"Invitation already {new_status}"}, status=http_status.HTTP_200_OK)

        if new_status.name == utils.InvitationStatus.ACCEPTED.value:
            ProjectMembership.objects.create(user=invitation.user, project=invitation.project, group=invitation.group)
        else:
            ProjectMembership.objects.filter(user=invitation.user, project=invitation.project, group=invitation.group).delete()

        data.save()

        resp = ProjectInvitationModelReadSerializer(invitation).data

        return Response(resp, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=ProjectInvitationModelReadSerializer,
        responses={
            400: "Bad request",
            200: "Invitation updated successfully",
            403: "Selected user does not have permission to update invitations",
        },
    )
    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

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

    @transaction.atomic
    @swagger_auto_schema(
        manual_parameters=[openapi.Parameter("token", openapi.IN_PATH, description="Token of the invitation", type=openapi.TYPE_STRING)],
        responses={
            400: "Bad request",
            200: "Invitations deleted successfully",
            403: "Selected user does not have permission to delete invitations",
        },
    )
    @action(detail=False, methods=["get"], url_path="accept/(?P<token>[0-9a-f-]+)", permission_classes=[permissions.AllowAny])
    def accept(self, request, token=None):

        if not token:
            return utils.ErrorResponse("Token not provided", status=http_status.HTTP_400_BAD_REQUEST)

        try:
            uuid.UUID(token)
        except ValueError:
            return utils.ErrorResponse("Invalid token", status=http_status.HTTP_400_BAD_REQUEST)

        invitation: ProjectInvitation = get_object_or_404(ProjectInvitation, token=token)

        # NOTE: This is not possible since clicking the link will not authenticate the user
        # user: CustomUser = self.request.user
        # if user != invitation.user and not any([user.is_staff, user.is_superuser]):
        #     return utils.ErrorResponse("Selected user does not have permission to accept the invitation", status=http_status.HTTP_403_FORBIDDEN)

        if invitation.status.name != utils.InvitationStatus.PENDING.value:
            return utils.ErrorResponse("Invitation is not pending", status=http_status.HTTP_400_BAD_REQUEST)

        # NOTE: This clashes with the uniqueness of the invitations for the same user and the same role in the same project
        # If we want to allow multiple invitations for the same user and the same role in the same project, we need to change the invitation logic
        # Possibly removing the error in case of multiple invitation, and instead refreshing the token and sending a new invitation email
        # if invitation.token_expiry < timezone.now():
        #     return utils.ErrorResponse("Invitation link has expired", status=http_status.HTTP_400_BAD_REQUEST)

        invitation.status = InvitationStatusType.objects.get(name_en=utils.InvitationStatus.ACCEPTED.value)

        ProjectMembership.objects.create(user=invitation.user, project=invitation.project, group=invitation.group)

        invitation.save()

        # Teturn simple html page with message
        return render(request, "invitation_accepted.html", {"project_name": invitation.project.name, "group": invitation.group.name})


class ActivityViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows activities to be viewed or edited.
    """

    queryset = Activity.objects.all()
    serializer_class = ActivitySerializerWithModules

    def update(self, request, *args, **kwargs):
        activity = self.get_object()

        if not utils.has_project_permission("change_activity", self.request.user, activity.project):
            logging.error("Selected user does not have permission to update activities in the project")
            return utils.ErrorResponse("Selected user does not have permission to update activities in the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = WriteActivitySerializer(data=request.data, instance=activity)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        activity = serializer.save()
        update_change_reason(activity, utils.ChangeReasons.UPDATE.value)

        read_serializer = self.serializer_class(instance=activity)

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
        update_change_reason(activity, utils.ChangeReasons.UPDATE.value)

        read_serializer = self.serializer_class(instance=activity)

        return Response(read_serializer.data, status=http_status.HTTP_200_OK)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        _status = StatusType.objects.get_or_create(name_en="EMPTY")[0]
        request.data["status"] = _status.pk
        serializer = WriteActivitySerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        if not utils.has_project_permission("add_activity", self.request.user, serializer.validated_data["project"]):
            logging.error("Selected user does not have permission to add activities to the project")
            return utils.ErrorResponse("Selected user does not have permission to add activities to the project", status=http_status.HTTP_403_FORBIDDEN)

        activity: Activity = serializer.save()
        activity.owner = self.request.user
        activity.save()

        update_change_reason(activity, utils.ChangeReasons.CREATE.value)

        read_serializer = self.serializer_class(instance=activity)

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

        return Response(data=self.serializer_class(activity).data, status=http_status.HTTP_200_OK)

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
        is_summary = request.query_params.get("summary", False)
        SerializerClass = ActivitySerializerWithModules
        if is_summary:
            SerializerClass = ActivitySummarySerializer

        if not utils.has_project_permission("view_activity", self.request.user, project):
            logging.error("Selected user does not have permission to view activities in the project")
            return utils.ErrorResponse("Selected user does not have permission to view activities in the project", status=http_status.HTTP_403_FORBIDDEN)

        def process_activity(activity):
            activity_dict = SerializerClass(activity).data
            return activity_dict

        activities_list = Activity.objects.filter(project__id=project_id)

        # Start measuring time
        start = time.time()

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(activities_list, request)
        if page is not None:
            with ThreadPoolExecutor() as executor:
                response = list(executor.map(process_activity, page))
                logger.debug(f"Time taken to process activities: {time.time() - start}")
            return paginator.get_paginated_response(response)

        # End measuring time
        logger.debug(f"Time taken to process activities: {time.time() - start}")

        return Response(data=SerializerClass(activities_list, many=True).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the activity.
        """

        activity = Activity.objects.prefetch_related().get(pk=pk)

        if not utils.has_project_permission("view_activity", self.request.user, activity.project):
            logging.error("Selected user does not have permission to view the activity")
            return utils.ErrorResponse("Selected user does not have permission to view the activity", status=http_status.HTTP_403_FORBIDDEN)

        response = {**ActivityResultSerializer(activity).data}

        modules = []
        # TODO: Make a serializer for this
        for module in activity.modules:

            if not module or (module.status and module.status.name != "READY"):
                continue

            module_dict = get_module_serializer(module.__class__)(module).data

            try:
                viewset = generic_module_viewset(module.__class__).results(self, request, pk=module.pk)
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

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(modules, request)
        if page is not None:
            return paginator.get_paginated_response(page)

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

        serializer = ActivityBuilderSerializer(data=request.data, context={"request": request})

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

        return Response(self.serializer_class(activity).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    @swagger_auto_schema(responses={404: "Project not found", 403: "Selected user does not have permission to copy the activity", 201: ActivitySerializer}, request_body=EmptySerializer)
    def copy(self, request, pk=None):
        activity = self.get_object()

        if not utils.has_project_permission("view_activity", self.request.user, activity.project):
            logging.error("Selected user does not have permission to copy the activity")
            return utils.ErrorResponse("Selected user does not have permission to copy the activity", status=http_status.HTTP_403_FORBIDDEN)

        new_activity = utils.copy_activity(activity)

        return Response(data=self.serializer_class(new_activity).data, status=http_status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view activity changes", 200: ChangeHistorySerializer})
    def history(self, request, pk=None):
        activity: Activity = self.get_object()

        if not utils.has_project_permission("view_activity", self.request.user, activity.project):
            logging.error("Selected user does not have permission to view the activity")
            return utils.ErrorResponse("Selected user does not have permission to view the activity", status=http_status.HTTP_403_FORBIDDEN)

        changes = utils.get_changes(activity.history.all())

        return Response(data=ChangeHistorySerializer(changes, many=True).data, status=http_status.HTTP_200_OK)


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


class NoteViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer

    @transaction.atomic
    @swagger_auto_schema(responses={400: "Bad request", 201: NoteSerializer}, request_body=NewNoteSerializer)
    def create(self, request, *args, **kwargs):
        serializer = NewNoteSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        try:
            module_type = ModuleType.objects.get(pk=serializer.validated_data["module_type_id"])
        except ModuleType.DoesNotExist:
            logging.error("Module type not found")
            return utils.ErrorResponse("Module type not found", status=http_status.HTTP_400_BAD_REQUEST)

        ModuleClass = utils.get_model(module_type.class_name, suffix=None)
        module: Module | Submodule = ModuleClass.objects.get(pk=serializer.validated_data["module_id"])

        if not utils.has_project_permission("add_note", self.request.user, module.project):
            logging.error("Selected user does not have permission to add notes to the project")
            return utils.ErrorResponse("Selected user does not have permission to add notes to the project", status=http_status.HTTP_403_FORBIDDEN)

        note = serializer.save()

        return Response(self.serializer_class(note).data, status=http_status.HTTP_201_CREATED)

    @transaction.atomic
    @swagger_auto_schema(responses={400: "Bad request", 200: NoteSerializer}, request_body=NoteSerializer)
    def update(self, request, *args, **kwargs):
        note: Note = self.get_object()

        if not utils.has_project_permission("change_note", self.request.user, note.project):
            logging.error("Selected user does not have permission to update notes in the project")
            return utils.ErrorResponse("Selected user does not have permission to update notes in the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = self.serializer_class(data=request.data, instance=note)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        note = serializer.save()
        update_change_reason(note, utils.ChangeReasons.UPDATE.value)

        return Response(self.serializer_class(note).data, status=http_status.HTTP_200_OK)

    @transaction.atomic
    @swagger_auto_schema(responses={400: "Bad request", 200: NoteSerializer}, request_body=NoteSerializer)
    def partial_update(self, request, *args, **kwargs):
        note: Note = self.get_object()

        if not utils.has_project_permission("change_note", self.request.user, note.project):
            logging.error("Selected user does not have permission to update notes in the project")
            return utils.ErrorResponse("Selected user does not have permission to update notes in the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = self.serializer_class(data=request.data, partial=True, instance=note)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        note = serializer.save()
        update_change_reason(note, utils.ChangeReasons.UPDATE.value)

        return Response(self.serializer_class(note).data, status=http_status.HTTP_200_OK)


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
        is_submodule = self.request.query_params.get("is_submodule", None) == "true"
        is_container = self.request.query_params.get("is_container", None) == "true"

        # NOTE: Containers are hidden by default
        filters = {"is_container": False}
        if is_luc:
            filters["is_luc"] = is_luc
        if is_submodule:
            filters["is_submodule"] = is_submodule
        if is_container:
            filters["is_container"] = is_container

        module_types = ModuleType.objects.filter(**filters).all()
        serializer = get_model_serializer(ModuleType)(module_types, many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)


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


def generic_module_viewset(model: Module):
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

            module: Module | Submodule | LandModule = self.get_object()
            activity = module.get_activity()

            if not utils.has_project_permission("can_change_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to update this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to update this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            serializer = get_module_serializer(model, action=ActionTypes.CREATE)(data=request.data, partial=True, instance=module)

            if not serializer.is_valid():
                return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

            module = serializer.save()
            update_change_reason(module, utils.ChangeReasons.UPDATE.value)

            if hasattr(module, "land_use_change") and module.land_use_change is not None:
                module.invalidate_luc_results()

            read_serializer = get_module_serializer(model)(instance=module, context={"request": request})

            return Response(read_serializer.data, status=http_status.HTTP_200_OK)

        def partial_update(self, request, *args, **kwargs):
            """
            Partially updates a module.
            """

            module: Module | Submodule = self.get_object()
            activity = module.get_activity()

            if not utils.has_project_permission("can_change_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to update this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to update this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            serializer = get_module_serializer(model, action=ActionTypes.CREATE)(data=request.data, partial=True, instance=module)

            if not serializer.is_valid():
                return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

            module = serializer.save()
            update_change_reason(module, utils.ChangeReasons.UPDATE.value)

            if hasattr(module, "land_use_change") and module.land_use_change is not None:
                module.invalidate_luc_results()

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
            module_type = ModuleType.objects.get(class_name=model.__name__)

            if not module_serializer.is_valid():
                logger.error(f"Error creating module: {module_serializer.errors}")
                return Response(module_serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

            if module_type.is_submodule:
                activity = module_serializer.validated_data["parent"].activity
            else:
                activity = module_serializer.validated_data["activity"]

            if not utils.has_project_permission("can_create_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to add this module to the project")
                return utils.ErrorResponse("Selected user does not have permission to add this module to the project", status=http_status.HTTP_403_FORBIDDEN)

            module_serializer.save()

            read_serializer = get_module_serializer(model)(instance=module_serializer.instance)

            update_change_reason(module_serializer.instance, utils.ChangeReasons.CREATE.value)

            logging.debug(f"END GenericModuleViewSet[{model.__name__}].create")

            return Response(read_serializer.data, status=http_status.HTTP_201_CREATED)

        @swagger_auto_schema(manual_parameters=[activity_id, module_type, page_size, page], responses={400: "Bad request", 403: "Selected user does not have permission to view the module", 200: get_module_serializer(model)})
        def list(self, request):
            """
            Lists the module(s) of a given activity
            by filtering against an `activity_id` query parameter in the URL or
            by filtering against the 'module_type' query parameter in the URL.
            """

            activity_id = utils.get_query_param_or_validation_error(self.request, "activity")
            activity = get_object_or_404(Activity, pk=activity_id)
            module_type = ModuleType.objects.get(class_name=model.__name__)

            if not utils.has_project_permission("can_view_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to view this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to view this module in the project", status=http_status.HTTP_403_FORBIDDEN)

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

            module: Module | Submodule = get_object_or_404(model, pk=pk)
            activity = module.get_activity()

            if not utils.has_project_permission("can_view_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to view this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to view this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            serializer = get_module_serializer(model, ActionTypes.RETRIEVE)(data={"activity": activity.pk}, partial=True, instance=module)
            serializer.is_valid(raise_exception=True)

            if module.module_type.class_name == LandUseChange.__name__:
                module: LandUseChange

                if not all(m.is_ready() for m in module.get_modules()):
                    return utils.ErrorResponse("Not all modules are ready. Land Use Change module cannot be calculated.")
            else:
                if not module.is_ready():
                    return utils.ErrorResponse("Module is not ready. Cannot calculate result.")

            try:

                aggregate_by = BreakdownTypes(request.query_params.get("aggregate", BreakdownTypes.TOTAL))
                module_results = module.get_cached_results(by=aggregate_by)

                if module_results is None:
                    logger.debug(f"Cache is invalid. Calculating results for module {module.id}")
                    total, by_activity, by_gas, by_activity_gas = CalculatorFactory().calculate_result(module)

                    results_total = {
                        "total_w": total[0],
                        "total_wo": total[1],
                        "balance": total[2],
                    }

                    results_by_activity = {
                        "total_w": list(by_activity[0]),
                        "total_wo": list(by_activity[1]),
                        "balance": list(by_activity[2]),
                    }

                    results_by_gas = {
                        "total_w": list(by_gas[0]),
                        "total_wo": list(by_gas[1]),
                        "balance": list(by_gas[2]),
                    }

                    results_by_activity_gas = {
                        "total_w": list(by_activity_gas[0]),
                        "total_wo": list(by_activity_gas[1]),
                        "balance": list(by_activity_gas[2]),
                    }

                    module_results = results_total if aggregate_by == BreakdownTypes.TOTAL else results_by_activity if aggregate_by == BreakdownTypes.ACTIVITY else results_by_gas if aggregate_by == BreakdownTypes.GAS else results_by_activity_gas
                    module.cache_results(results_total, results_by_activity, results_by_gas, results_by_activity_gas)

                serializer = DynamicResultSerializer(module_results, aggregate_by=aggregate_by)
                serialized_data = serializer.data
                # serializer = ModuleResultSerializer(module)
                # serialized_data = serializer.data

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

            module: Module | Submodule = get_object_or_404(model, pk=pk)
            activity = module.get_activity()

            serializer = get_module_serializer(model, ActionTypes.UPDATE)(data={}, instance=module, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            if not utils.has_project_permission("can_view_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to view this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to view this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            try:
                defaults: SimpleNamespace = DefaultsFactory.get_defaults(module, calculate=True)
                return Response(defaults.__dict__)
            except Exception as e:
                return utils.ErrorResponse(str(e))

        @action(detail=True, methods=["get"])
        @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view module changes", 200: ChangeHistorySerializer})
        def history(self, request, pk=None):
            module: Module = self.get_object()
            activity = module.get_activity()

            if not utils.has_project_permission("can_view_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to view this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to view this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            changes = utils.get_changes(module.history.all())

            return Response(data=ChangeHistorySerializer(changes, many=True).data, status=http_status.HTTP_200_OK)

        @action(detail=True, methods=["get"])
        @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view module definitions", 200: "Definitions"})
        def definitions(self, request, pk=None):
            """
            Returns the definitions for a module.
            """

            module: Module | Submodule = get_object_or_404(model, pk=pk)
            activity = module.get_activity()

            if not utils.has_project_permission("can_view_modules", self.request.user, activity.project):
                logging.error("Selected user does not have permission to view this module in the project")
                return utils.ErrorResponse("Selected user does not have permission to view this module in the project", status=http_status.HTTP_403_FORBIDDEN)

            try:
                definitions = utils.get_entity_definitions(module.module_type.class_name)
                return Response(definitions)
            except Exception as e:
                return utils.ErrorResponse(str(e))

    return GenericModuleViewSet


def generic_viewset(model: Model):
    class GenericViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_model_serializer(model)
        filterset_class = api_filters.get_model_filter(model)

        def get_queryset(self):
            for field in model._meta.get_fields():
                if field.name == "active":
                    return model.objects.filter(active=True)
            return super().get_queryset()

    return GenericViewSet


def public_generic_viewset(model: Model):
    class PublicGenericViewSet(viewsets.ModelViewSet, PublicViewSet):
        queryset = model.objects.all()
        serializer_class = get_model_serializer(model)

    return PublicGenericViewSet


class FieldDefinitionViewSet(viewsets.ViewSet):

    @swagger_auto_schema(
        request_body=FieldDefinitionSerializer,
        responses={400: "Bad request", 201: FieldDefinitionSerializer},
    )
    def create(self, request, *args, **kwargs):

        serializer = FieldDefinitionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save()

        return Response(serializer.data, status=http_status.HTTP_201_CREATED)

    # Custom action for listing field definitions
    @swagger_auto_schema(
        manual_parameters=[openapi.Parameter("module_type_id", openapi.IN_QUERY, description="Module type id", type=openapi.TYPE_INTEGER)],
        responses={400: "Model name not provided", 404: "Model not found", 200: FieldDefinitionResponseSerializer},
    )
    def list(self, request, *args, **kwargs):
        module_type_id = request.query_params.get("module_type_id", None)

        if module_type_id is None:
            return Response({"error": "Model name not provided"}, status=400)

        try:
            module_type = ModuleType.objects.get(pk=module_type_id)
        except ModuleType.DoesNotExist:
            return Response({"error": "Module not found"}, status=404)

        field_metadata = self.get_model_field_metadata(module_type)

        return Response(field_metadata)

    def get_model_field_metadata(self, module_type):
        field_metadata = {}
        definitions = FieldDefinition.objects.filter(module_type=module_type).all()

        for definition in definitions:
            field_metadata[definition.field_name] = {
                "description": definition.description,
            }

        return field_metadata


class ProjectTagViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = ProjectTag.objects.all()
    serializer_class = ProjectTagSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name"]
    ordering = ["name"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        project_id = self.kwargs.get("project_pk")
        context["project"] = get_object_or_404(Project, pk=project_id)
        return context

    def get_queryset(self):
        project_id = self.kwargs.get("project_pk")  # 'project_pk' comes from the nested router
        search = self.request.query_params.get("search", None)

        project = get_object_or_404(Project, pk=project_id)

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        filters = {"project": project}

        if search:
            filters["name__icontains"] = search

        return ProjectTag.objects.filter(**filters)

    def perform_create(self, serializer):
        project_id = self.kwargs.get("project_pk")
        project = get_object_or_404(Project, pk=project_id)

        if not utils.has_project_permission("add_tag", self.request.user, serializer.validated_data["project"]):
            logging.error("Selected user does not have permission to add tags to the project")
            raise PermissionDenied("Selected user does not have permission to add tags to the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer.save(project=project)

    # def create(self, request, *args, **kwargs):
    #     serializer = TagSerializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)

    #     if not utils.has_project_permission("add_tag", self.request.user, serializer.validated_data["project"]):
    #         logging.error("Selected user does not have permission to add tags to the project")
    #         return utils.ErrorResponse("Selected user does not have permission to add tags to the project", status=http_status.HTTP_403_FORBIDDEN)

    #     if Tag.objects.filter(slug=slugify(serializer.validated_data["name"]), project=serializer.validated_data["project"]).exists():
    #         return utils.ErrorResponse("Tag with the same name already exists in the project", status=http_status.HTTP_400_BAD_REQUEST)

    #     serializer.save()

    #     return Response(serializer.data, status=http_status.HTTP_201_CREATED)

    # def list(self, request, *args, **kwargs):

    #     project_id = self.request.query_params.get("project_id", None)
    #     search = self.request.query_params.get("search", None)

    #     if not project_id:
    #         logging.error("Project id not provided")
    #         return utils.ErrorResponse("Project id not provided", status=http_status.HTTP_400_BAD_REQUEST)

    #     project = get_object_or_404(Project, pk=project_id)

    #     if not utils.has_project_permission("view_tag", self.request.user, project):
    #         logging.error("Selected user does not have permission to view tags in the project")
    #         return utils.ErrorResponse("Selected user does not have permission to view tags in the project", status=http_status.HTTP_403_FORBIDDEN)

    #     if search:
    #         tags = Tag.objects.filter(project=project, name__icontains=search).all()
    #     else:
    #         tags = Tag.objects.filter(project=project).all()

    #     serializer = TagSerializer(tags, many=True)

    #     return Response(serializer.data, status=http_status.HTTP_200_OK)
