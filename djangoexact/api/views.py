import os
import logging
from types import SimpleNamespace
from django.urls import reverse
from django.conf import settings
from django.shortcuts import render
import numpy as np
import traceback

from django.contrib.auth.models import Group
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db.models import Model
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes
from rest_framework import permissions, viewsets, views
from rest_framework import status as http_status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from google.cloud import storage
import api.filters as api_filters
import api.labels as labels
import api.utilities as utils
from api.defaults import DefaultsFactory
from api.models import CustomUser as User
from datetime import datetime
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

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
    Module,
    ModuleType,
    Project,
    ProjectInvitation,
    StatusType,
    Submodule,
    ProjectMembership,
    ProjectNotificationPreference,
    InvitationStatusType,
    Note,
    FieldDefinition,
    LandModule,
    ProjectTag,
    ProjectFileAttachment,
    APIHealth,
    FuelType,
    SoilType,
    Fishery,
    Livestock,
    LivestockCategoryType,
    FisheryType,
    SmallFishery,
    LargeFishery,
    PublicToken,
    HandInHandAssessment,
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
    ProjectInvitationModelReadSerializer,
    ProjectInvitationReadSerializer,
    ProjectInvitationWriteSerializer,
    ReadProjectSerializer,
    ProjectMembershipWriteSerializer,
    ProjectMembershipReadSerializer,
    ProjectNotificationPreferenceReadSerializer,
    ProjectNotificationPreferenceWriteSerializer,
    UserReadSerializer,
    UserWriteSerializer,
    WriteActivitySerializer,
    WriteProjectSerializer,
    get_model_serializer,
    get_module_serializer,
    ChangeHistorySerializer,
    ProjectInvitationModelWriteSerializer,
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
    ProjectFileUploadSerializer,
    ProjectFileReadSerializer,
    APIStatusSerializer,
    FuelTypeSerializer,
    ProjectLockHolderInformationSerializer,
    Aquaculture,
    DynamicResultFactory,
    PublicTokenSerializer,
    HandInHandRegionSerializer,
    HandInHandCountrySerializer,
    HandInHandAssessmentSerializer,
    HandInHandAssessmentGroupedSerializer,
    ProjectInvitationAcceptSerializer,
)

from firebase_admin import auth as firebase_admin_auth
from auditlog.context import disable_auditlog, LogEntry
from django.db import connection
import time
import api.reports as reports
from django.http import HttpResponse
from django.core.cache import cache
import api.security as security
import ipcc.models as ipcc_models
import matplotlib.pyplot as plt
import io
import base64
import api.permissions as api_permissions
from django.utils.translation import gettext as _
from django.utils.translation import activate

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


def warmup(request):
    return HttpResponse("Warmup successful.")


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


class DynamicFilterViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = [api_filters.DynamicSearchAndFilterBackend]

    @swagger_auto_schema(
        parameters=[
            openapi.Parameter(
                name="s",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description='Search query. Example: ?s="search query". Allows for multiple queryes. Example: ?s="search query 1&s=search query 2"',
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


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

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        self.serializer_class = UserWriteSerializer
        user = self.get_object()
        old_email = user.email
        new_email = request.data.get("email")

        if new_email and user.firebase_uid:
            normalized_email = new_email.casefold().strip()
            if normalized_email != old_email:
                try:
                    firebase_admin_auth.update_user(user.firebase_uid, email=normalized_email, email_verified=False)
                except Exception as e:
                    logging.error(f"Failed to update Firebase email for user {user.pk}: {e}")
                    raise ValidationError(f"Failed to update email in authentication system: {str(e)}")

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


class LandUseTypeViewSet(viewsets.ModelViewSet, PublicViewSet):
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


class ProjectViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """

    queryset = Project.objects.all()
    serializer_class = WriteProjectSerializer
    pagination_class = DefaultPagination
    permission_classes = [api_permissions.IsPublicOrAuthenticated]

    @transaction.atomic
    @swagger_auto_schema(responses={400: "Bad request", 201: ReadProjectSerializer})
    def create(self, request, *args, **kwargs):
        """
        Creates a new project for a given user.
        """

        request.data["user"] = self.request.user.pk
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        project: Project = serializer.save()
        utils.update_change_reason(project, utils.ChangeReasons.CREATE.value)

        project.lock(self.request.user)

        ProjectMembership.objects.create(user=self.request.user, project=project, group=Group.objects.get(name="Admin"))
        read_serializer = ReadProjectSerializer(instance=project, context={"request": request})

        return Response(read_serializer.data, status=http_status.HTTP_201_CREATED)

    @transaction.atomic
    @swagger_auto_schema(responses={400: "Bad request", 204: "Project deleted successfully"})
    def destroy(self, request, *args, **kwargs):
        project: Project = self.get_object()

        error = security.check_permission("delete_project", self.request.user, project)
        if error:
            return error

        if project.members.filter(group__name="Admin").count() > 1:
            return utils.ErrorResponse("You cannot delete a project if there are other admins. You can only remove yourself from it", status=http_status.HTTP_400_BAD_REQUEST)

        # NOTE: This is a workaround for a bug in the simple_history library caused by an unhandled AttributeError when deleting a project with no previous history
        if project.history.count() > 0:
            utils.update_change_reason(project, utils.ChangeReasons.DELETE.value)

        is_deleted = self.raw_delete_cascade(project)
        if not is_deleted:
            return utils.ErrorResponse("Error deleting project", status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=http_status.HTTP_204_NO_CONTENT)

    def raw_delete_cascade(self, project: Project):
        with connection.cursor() as cursor:
            project.members.all().delete()
            project.invitations.all().delete()

            # Delete all activities
            activities = project.activities.all()
            for activity in activities:
                for m in activity.modules:
                    if hasattr(m, "submodules"):
                        for sm in m.submodules:
                            table_name = sm._meta.db_table
                            # Ensures the table is a valid identifier, reducing the risk of SQL injection
                            if not table_name.isidentifier():
                                raise ValueError("Invalid table name")
                            cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", [sm.id])  # nosemgrep: table_name comes from Django _meta.db_table and is isidentifier()-guarded above; id is parameterized
                    table_name = m._meta.db_table
                    # Ensures the table is a valid identifier, reducing the risk of SQL injection
                    if not table_name.isidentifier():
                        raise ValueError("Invalid table name")
                    cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", [m.id])  # nosemgrep: table_name comes from Django _meta.db_table and is isidentifier()-guarded above; id is parameterized

                LandUseChange.objects.filter(activity=activity).delete()
                cursor.execute("DELETE FROM api_activity_module_types WHERE activity_id = %s", [activity.id])
                cursor.execute("DELETE FROM api_activity WHERE id = %s", [activity.id])

            ProjectTag.objects.filter(project=project).delete()
            ProjectFileAttachment.objects.filter(project=project).delete()
            cursor.execute("DELETE FROM api_project WHERE id = %s", [project.id])

        return True

    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"}, serializer_class=ReadProjectSerializer)
    def retrieve(self, request, pk=None):
        """
        Get a single project for a given user.
        """

        project = self.get_object()
        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        return Response(data=ReadProjectSerializer(project, context={"request": request}).data, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(
        manual_parameters=[
            name,
            page,
            page_size,
            openapi.Parameter(
                "summary",
                openapi.IN_QUERY,
                description="Return a summary of the project",
                type=openapi.TYPE_BOOLEAN,
            ),
            openapi.Parameter(
                "show_archived",
                openapi.IN_QUERY,
                description="Show archived projects",
                type=openapi.TYPE_BOOLEAN,
            ),
            openapi.Parameter(
                "tags",
                openapi.IN_QUERY,
                description="Filter projects by tags, comma separated. Example: ?tags=tag1,tag2",
                type=openapi.TYPE_STRING,
            ),
        ],
        responses={
            404: "Project not found",
            403: "Selected user does not have permission to view projects",
            200: ReadProjectSerializer,
            201: ProjectSummarySerializer,
        },
        serializer_class=ReadProjectSerializer,
    )
    def list(self, request):
        """
        Get all projects for a given user.
        """

        search_query = request.query_params.get("name", None)
        is_summary = request.query_params.get("summary", False)
        show_archived = request.query_params.get("show_archived", None)
        tags = request.query_params.get("tags", None)

        filters = {}
        if search_query:
            filters["project__name__icontains"] = search_query
        if not show_archived:
            filters["project__is_archived"] = False
        if tags:
            filters["project__tags__name__in"] = tags.split(",")

        # Get all other filters from the request (this should be done in a more generic way in the future)
        for key, value in request.query_params.items():
            if key not in ["name", "summary", "show_archived", "tags", "page", "page_size"]:
                if value == "true":
                    filters[f"project__{key}"] = True
                elif value == "false":
                    filters[f"project__{key}"] = False
                else:
                    filters[f"project__{key}"] = value

        # NOTE: Users can have multiple memberships to the same project, so we need to filter by distinct projects
        # And deduplicate them by assigning them to a dictionary with the project id as the unique key
        shared_projects = request.user.memberships.filter(**filters).distinct()
        project_map = {}
        for share in shared_projects:
            project = share.project
            if utils.has_project_permission("view_project", self.request.user, project):
                project_map[project.pk] = project
        projects_list = list(project_map.values())

        ordered_projects = sorted(projects_list, key=lambda x: x.updated_at, reverse=True)

        SerializerClass = ReadProjectSerializer
        if is_summary:
            SerializerClass = ProjectSummarySerializer

        def serialize_project(project):
            return SerializerClass(project, context={"request": request}).data

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(ordered_projects, request)
        if page is not None:
            # Serial serialization: each ThreadPoolExecutor thread opens its own
            # Django thread-local DB connection. With 10 workers per request, a
            # handful of concurrent requests saturated the App Engine ↔ Cloud SQL
            # Auth Proxy cap of 100 connections, surfacing as "Connection refused".
            response = [serialize_project(project) for project in page]
            return paginator.get_paginated_response(response)

        return Response(data=SerializerClass(ordered_projects, many=True, context={"request": request}).data, status=http_status.HTTP_200_OK)

    activities = openapi.Parameter(
        "activities",
        openapi.IN_QUERY,
        description="List of activity ids to include in the results",
        type=openapi.TYPE_ARRAY,
        items={"type": openapi.TYPE_INTEGER},
    )

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(
        manual_parameters=[
            activities,
            openapi.Parameter(
                "cached",
                openapi.IN_QUERY,
                description="Return cached results",
                type=openapi.TYPE_BOOLEAN,
            ),
        ],
        responses={404: "Project not found", 403: "Selected user does not have permission to view project results", 200: ProjectResultSerializer},
    )
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the project.
        """

        try:
            project = Project.objects.prefetch_related("activities").get(pk=pk)
        except Project.DoesNotExist:
            logging.error("Project not found")
            return utils.ErrorResponse("Project not found", status=http_status.HTTP_404_NOT_FOUND)

        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        serialized_project = ProjectResultSerializer(project, context={"request": request}).data

        selected_activities = request.query_params.get("activities", "").split(",")
        if selected_activities == [""]:
            selected_activities = project.activities.values_list("id", flat=True)

        response = serialized_project
        response["activities"] = []

        # Function to process an activity
        def process_activity(activity_pk):
            return ActivityViewSet.results(self, request, pk=activity_pk).data

        activity_pks = project.activities.filter(pk__in=selected_activities).values_list("id", flat=True)

        # Serial processing: parallel threads each opened their own Django
        # thread-local DB connection and saturated the App Engine ↔ Cloud SQL
        # Auth Proxy cap of 100 connections per instance.
        for pk in activity_pks:
            try:
                data = process_activity(pk)
            except Exception as exc:
                logging.error(f"Activity {pk} generated an exception: {exc}")
            else:
                response["activities"].append(data)

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
        project: Project = get_object_or_404(Project, pk=pk)
        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        selected_activities = request.query_params.get("activities", "").split(",")
        if selected_activities == [""]:
            selected_activities = None
        else:
            selected_activities = project.activities.filter(pk__in=selected_activities)

        if not project.is_ready(selected_activities):
            logging.error("Project is not ready")
            return utils.ErrorResponse("To get a report for a project, all activities must have been completed.", status=http_status.HTTP_400_BAD_REQUEST)

        if request.query_params.get("template", None):
            response = self.template(request, pk=pk)
            return response

        try:
            report = reports.BaseProjectReport(project, activities=selected_activities)
            _, file_bytes_buffer = report.build_report()
            report.close_file()
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error generating report: {e}")
            return utils.ErrorResponse(str(e), status=http_status.HTTP_422_UNPROCESSABLE_ENTITY)

        try:
            response = HttpResponse(file_bytes_buffer, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f'attachment; filename="{project.name}_report.xlsx"'

            return response
        except FileNotFoundError:
            return utils.ErrorResponse("Error generating report: file not found", status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return utils.ErrorResponse(str(e), status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        project: Project = self.get_object()
        error = security.check_permission("change_project", self.request.user, project)
        if error:
            return error

        serializer = self.serializer_class(project, data=request.data, partial=True, context={"request": request})
        if not serializer.is_valid():
            logging.error(f"Error updating project: {serializer.errors}")
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save()
        if project.history.count() > 0:
            utils.update_change_reason(project, utils.ChangeReasons.UPDATE.value)

        return Response(ReadProjectSerializer(project, context={"request": request}).data, status=http_status.HTTP_200_OK)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        project: Project = self.get_object()
        error = security.check_permission("change_project", self.request.user, project)
        if error:
            return error

        serializer = self.serializer_class(project, data=request.data, context={"request": request})
        if not serializer.is_valid():
            logging.error("Error updating project:", serializer.errors)
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save()
        if project.history.count() > 0:
            utils.update_change_reason(project, utils.ChangeReasons.UPDATE.value)

        return Response(ReadProjectSerializer(project, context={"request": request}).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    @swagger_auto_schema(
        responses={
            404: "Project not found",
            403: "Selected user does not have permission to copy the project",
            400: "Bad request",
            201: ReadProjectSerializer,
        },
        request_body=EmptySerializer,
    )
    def copy(self, request, pk=None):
        project = self.get_object()
        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        new_project = utils.copy_project(project, self.request.user)
        ProjectMembership.objects.create(user=self.request.user, project=new_project, group=Group.objects.get(name="Admin"))

        serializer = ReadProjectSerializer(new_project, context={"request": request})
        return Response(data=serializer.data, status=http_status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view project memberships", 200: ProjectMembershipReadSerializer})
    def memberships(self, request, pk=None):
        project = self.get_object()
        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        serializer = ProjectMembershipReadSerializer(project.members.all(), many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    # TODO: Remove this action when the frontend is updated
    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view project memberships", 200: ProjectMembershipReadSerializer})
    def users(self, request, pk=None):
        return self.memberships(request, pk)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view invitations", 200: ProjectInvitationReadSerializer})
    def invitations(self, request, pk=None):
        project = self.get_object()
        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        serializer = ProjectInvitationReadSerializer(project.invitations.all(), many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "The current user does not have permission to view project changes", 200: ChangeHistorySerializer})
    def history(self, request, pk=None):
        project: Project = self.get_object()
        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        changes = utils.get_changes(project.history.all())
        return Response(data=ChangeHistorySerializer(changes, many=True).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view project tags", 200: ProjectFileReadSerializer})
    def attachments(self, request, pk=None):
        project: Project = self.get_object()
        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        serializer = ProjectFileReadSerializer(project.attachments.all(), many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(method="get", responses={200: ProjectLockHolderInformationSerializer})
    @swagger_auto_schema(method="post", responses={200: ProjectLockHolderInformationSerializer, 409: "Project is already locked by another user"})
    @action(detail=True, methods=["get", "post"])
    def lock(self, request, pk=None):
        project: Project = self.get_object()
        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        project._check_lock_expiration()

        if request.method == "POST":
            if project.is_locked and project.locked_by != request.user and not request.user.is_superuser:
                return utils.ErrorResponse("Project is already locked by another user", status=http_status.HTTP_409_CONFLICT)

            project.lock(request.user)

        serializer = ProjectLockHolderInformationSerializer(project, many=False)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    @swagger_auto_schema(responses={200: ProjectLockHolderInformationSerializer, 403: "Only superusers can unlock projects"})
    def unlock(self, request, pk=None):
        project: Project = self.get_object()

        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        if project.is_locked and not request.user.is_superuser and project.locked_by != request.user:
            return utils.ErrorResponse("Only superusers and the project lock holder can unlock projects", status=http_status.HTTP_403_FORBIDDEN)

        project.unlock()

        serializer = ProjectLockHolderInformationSerializer(project, many=False)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def activities(self, request, pk=None):
        project: Project = self.get_object()
        error = security.check_permission("view_project", self.request.user, project)
        if error:
            return error

        activities = project.activities.all()
        serializer = ActivitySerializer(activities, many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Generate a PDF from an HTML template",
        manual_parameters=[
            openapi.Parameter("template", openapi.IN_QUERY, description="Name of the Django template to render", type=openapi.TYPE_STRING, required=True),
            openapi.Parameter("lang", openapi.IN_QUERY, description="Language of the template", type=openapi.TYPE_STRING, required=False),
        ],
        responses={200: "PDF file generated successfully", 400: "Template name not provided or template not found", 500: "Error generating PDF"},
        produces=["application/pdf"],
    )
    def template(self, request, pk=None):
        template_name = request.query_params.get("template")
        lang = request.query_params.get("lang", "en")
        if hasattr(request, "LANGUAGE_CODE"):
            lang = request.LANGUAGE_CODE

        if not template_name:
            return utils.ErrorResponse("Template name is required", status=http_status.HTTP_400_BAD_REQUEST)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.exists(f"{current_dir}/templates/reports/{template_name}_{lang}.html"):
            return utils.ErrorResponse(f"Template '{template_name}' not found for language '{lang}'", status=http_status.HTTP_400_BAD_REQUEST)

        try:
            activate(lang)

            project: Project = self.get_object()
            soc: ipcc_models.SoilOrganicCarbon = ipcc_models.SoilOrganicCarbon.objects.get(climate=project.climate, moisture=project.moisture, soil_type=project.soil_type)

            # Calculate total area of all activities
            total_area = sum(activity.area for activity in project.activities.all())

            # Call project results endpoint
            total_results_response = self.results(request, pk=pk)

            total_data = total_results_response.data
            activities = total_data["activities"]
            modules = [module for activity in activities for module in activity["modules"]]
            results = [module["results"] for module in modules]
            # TODO: Maybe instead of doing this show the module but with an error message
            total_w = sum(result["total_w"] for result in results if result.get("total_w", None) is not None)
            total_wo = sum(result["total_wo"] for result in results if result.get("total_wo", None) is not None)
            total_balance = total_w - total_wo

            project_emissions_w = total_w
            project_emissions_wo = total_wo
            project_emissions_balance = total_balance

            new_request = request._request
            new_request.query_params = request.query_params.copy()
            new_request.query_params["aggregate"] = "gas"

            gas_results_response = self.results(new_request, pk=pk)
            gas_data = gas_results_response.data
            activities = gas_data["activities"]
            modules = [module for activity in activities for module in activity["modules"]]
            results = [module["results"] for module in modules]

            emissions_w = [result["total_w"] for result in results if result.get("total_w", None) is not None]
            emissions_wo = [result["total_wo"] for result in results if result.get("total_wo", None) is not None]

            co2_w = {"name": "CO2", "value": 0}
            ch4_w = {"name": "CH4", "value": 0}
            n2o_w = {"name": "N2O", "value": 0}
            co_w = {"name": "CO", "value": 0}
            doc_w = {"name": "DOC", "value": 0}
            other_w = {"name": "OTHER", "value": 0}

            gases_w = [co2_w, ch4_w, n2o_w, co_w, doc_w, other_w]

            for w in emissions_w:
                for g in w:
                    if g["gas_type"]["name"] == "CO2":
                        co2_w["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CH4":
                        ch4_w["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "N2O":
                        n2o_w["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CO":
                        co_w["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "DOC":
                        doc_w["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "OTHER":
                        other_w["value"] += sum([e["value"] for e in g["emissions"]])

            co2_wo = {"name": "CO2", "value": 0}
            ch4_wo = {"name": "CH4", "value": 0}
            n2o_wo = {"name": "N2O", "value": 0}
            co_wo = {"name": "CO", "value": 0}
            doc_wo = {"name": "DOC", "value": 0}
            other_wo = {"name": "OTHER", "value": 0}

            gases_wo = [co2_wo, ch4_wo, n2o_wo, co_wo, doc_wo, other_wo]

            for wo in emissions_wo:
                for g in wo:
                    if g["gas_type"]["name"] == "CO2":
                        co2_wo["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CH4":
                        ch4_wo["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "N2O":
                        n2o_wo["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CO":
                        co_wo["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "DOC":
                        doc_wo["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "OTHER":
                        other_wo["value"] += sum([e["value"] for e in g["emissions"]])

            balances = [result["balance"] for result in results if result.get("balance", None) is not None]

            co2 = {"name": "CO2", "value": 0}
            ch4 = {"name": "CH4", "value": 0}
            n2o = {"name": "N2O", "value": 0}
            co = {"name": "CO", "value": 0}
            doc = {"name": "DOC", "value": 0}
            other = {"name": "OTHER", "value": 0}

            for b in balances:
                for g in b:
                    if g["gas_type"]["name"] == "CO2":
                        co2["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CH4":
                        ch4["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "N2O":
                        n2o["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CO":
                        co["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "DOC":
                        doc["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "OTHER":
                        other["value"] += sum([e["value"] for e in g["emissions"]])

            gases = [co2, ch4, n2o, co, doc, other]

            INCREASES = _("increases")
            DECREASES = _("decreases")

            sorted_gases = sorted(gases, key=lambda x: (abs(x["value"]) and x["value"] != 0), reverse=True)
            highest_gas = sorted_gases[0]
            second_highest_gas = sorted_gases[1]
            third_highest_gas = sorted_gases[2]

            project_primary_ghg = highest_gas["name"]
            project_primary_ghg_emissions = highest_gas["value"]
            project_primary_ghg_direction = INCREASES if project_primary_ghg_emissions >= 0 else DECREASES

            project_secondary_ghg = second_highest_gas["name"]
            project_secondary_ghg_emissions = second_highest_gas["value"]
            project_secondary_ghg_direction = INCREASES if project_secondary_ghg_emissions >= 0 else DECREASES

            project_tertiary_ghg = third_highest_gas["name"]
            project_tertiary_ghg_emissions = third_highest_gas["value"]
            project_tertiary_ghg_direction = INCREASES if project_tertiary_ghg_emissions >= 0 else DECREASES

            activities = project.activities.all()

            processed_activities = []

            # Hectares: if with to without, with is counted as 0 and without as area
            livestock_heads = [{"name": lct.name, "value_w": 0, "value_wo": 0} for lct in LivestockCategoryType.objects.all()]

            small_fishery_types = [{"name": ft.name, "value_w": 0, "value_wo": 0} for ft in FisheryType.objects.all()]
            large_fishery_data = {"name": "Large Fisheries", "value_w": 0, "value_wo": 0}
            aquaculture_data = {"name": "Aquaculture", "value_w": 0, "value_wo": 0}
            land_types = [{"name": lt.name, "value_w": 0, "value_wo": 0} for lt in ModuleType.objects.filter(is_luc=True).all()]

            for a in total_data["activities"]:
                db_activity: Activity = activities.get(name=a["name"])
                mlist = list(filter(lambda x: x.get("results", None) is not None and x["results"].get("balance", None) is not None, a["modules"]))
                modules_by_highest_emissions = sorted(mlist, key=lambda x: x["results"]["balance"], reverse=total_balance > 0)

                db_activity.modules_emissions = [{"name": m["module_type"]["name"], "balance": m["results"]["balance"]} for m in modules_by_highest_emissions]

                sum_all_total_w = sum([m["results"]["total_w"] for m in mlist if m["results"]["total_w"] is not None])
                sum_all_total_wo = sum([m["results"]["total_wo"] for m in mlist if m["results"]["total_wo"] is not None])
                sum_all_balance = sum_all_total_w - sum_all_total_wo

                db_activity.results = {"total_w": sum_all_total_w, "total_wo": sum_all_total_wo, "balance": sum_all_balance}

                main_impact = None
                secondary_impacts = []

                if db_activity.is_luc:
                    main_impact = _("hectares")
                elif db_activity.is_fishery:
                    main_impact = _("tonnes of catch")
                elif db_activity.is_livestock:
                    main_impact = _("livestock heads")

                if any([db_activity.is_energy, db_activity.is_storage, db_activity.is_transport, db_activity.is_processing]):
                    secondary_impacts.append(_("energy consumption"))
                if db_activity.is_packaging:
                    secondary_impacts.append(_("packaging material"))
                if db_activity.is_input:
                    secondary_impacts.append(_("agricultural inputs use"))

                secondary_impacts = ", ".join(secondary_impacts)

                db_activity.main_impact = main_impact
                if secondary_impacts:
                    db_activity.secondary_impacts = secondary_impacts

                for m in db_activity.modules:
                    if issubclass(m.__class__, Fishery):
                        if isinstance(m, SmallFishery):
                            m: SmallFishery
                            for ft in small_fishery_types:
                                if ft["name"] == m.fishery_type.name:
                                    ft["value_w"] += m.total_catch_yr_w
                                    ft["value_wo"] += m.total_catch_yr_wo
                        elif isinstance(m, LargeFishery):
                            m: LargeFishery
                            large_fishery_data["value_wo"] += m.total_catch_yr_wo
                            large_fishery_data["value_w"] += m.total_catch_yr_w

                    elif isinstance(m, Livestock):
                        m: Livestock
                        for lh in livestock_heads:
                            if lh["name"] == m.livestock_category_type.name:
                                lh["value_w"] += m.heads_number_w
                                lh["value_wo"] += m.heads_number_wo

                    elif isinstance(m, Aquaculture):
                        m: Aquaculture
                        aquaculture_data["value_w"] += m.annual_production_w
                        aquaculture_data["value_wo"] += m.annual_production_wo

                    elif issubclass(m.__class__, LandModule):
                        m: LandModule
                        for lt in land_types:
                            if lt["name"] == m.module_type.name:
                                if m.is_with() and not m.is_without():
                                    lt["value_w"] += m.area
                                elif m.is_without() and not m.is_with():
                                    lt["value_wo"] += m.area
                                elif m.is_with() and m.is_without():
                                    lt["value_w"] += m.area
                                    lt["value_wo"] += m.area

                processed_activities.append(db_activity)

            processed_activities = sorted(processed_activities, key=lambda x: x.results["balance"], reverse=total_balance > 0)

            livestock_heads = list(filter(lambda x: x["value_w"] != 0 or x["value_wo"] != 0, livestock_heads))
            small_fishery_types = list(filter(lambda x: x["value_w"] != 0 or x["value_wo"] != 0, small_fishery_types))
            large_fishery_data = {} if large_fishery_data["value_w"] == 0 or large_fishery_data["value_wo"] == 0 else large_fishery_data
            aquaculture_data = {} if aquaculture_data["value_w"] == 0 or aquaculture_data["value_wo"] == 0 else aquaculture_data
            land_types = list(filter(lambda x: x["value_w"] != 0 or x["value_wo"] != 0, land_types))
            total_heads = sum([lh["value_w"] for lh in livestock_heads])
            total_tonnes_of_catch = sum([ft["value_w"] for ft in small_fishery_types]) + large_fishery_data.get("value_w", 0)

            activities_total = processed_activities

            def plot_with_without_balance_bar_chart_stacked_by_gas(data_w: list, data_wo: list):
                co2_w, ch4_w, n2o_w, co_w, doc_w, other_w = data_w
                co2_wo, ch4_wo, n2o_wo, co_wo, doc_wo, other_wo = data_wo

                # Prepare bar labels
                labels = ["With", "Without", "Balance"]

                # Build lists of values for each gas for "With", "Without", and the difference
                co2_vals = [
                    co2_w["value"],
                    co2_wo["value"],
                    co2_w["value"] - co2_wo["value"],
                ]
                ch4_vals = [
                    ch4_w["value"],
                    ch4_wo["value"],
                    ch4_w["value"] - ch4_wo["value"],
                ]
                n2o_vals = [
                    n2o_w["value"],
                    n2o_wo["value"],
                    n2o_w["value"] - n2o_wo["value"],
                ]
                co_vals = [
                    co_w["value"],
                    co_wo["value"],
                    co_w["value"] - co_wo["value"],
                ]
                doc_vals = [
                    doc_w["value"],
                    doc_wo["value"],
                    doc_w["value"] - doc_wo["value"],
                ]
                other_vals = [
                    other_w["value"],
                    other_wo["value"],
                    other_w["value"] - other_wo["value"],
                ]

                # Stack them in an array for plotting
                data_arrays = np.array([co2_vals, ch4_vals, n2o_vals, co_vals, doc_vals, other_vals])
                # Each row is a gas, each column is a bar (With, Without, Balance)

                x = np.arange(len(labels))
                width = 0.6

                fig, ax = plt.subplots(figsize=(6.5, 4))

                # We'll accumulate the bottom of each stack as we go
                bottom = np.zeros(len(labels))

                colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
                names = ["CO2", "CH4", "N2O", "CO", "DOC", "OTHER"]

                for idx, row in enumerate(data_arrays):
                    ax.bar(x, row, width, bottom=bottom, color=colors[idx], label=names[idx])
                    bottom += row

                ax.set_xticks(x)
                ax.set_xticklabels(labels)
                ax.ticklabel_format(style="plain", axis="y", useOffset=False)
                ax.set_ylabel("Emissions (tonnes)")
                ax.set_title("")
                ax.legend()

                # Save to a BytesIO buffer
                buf = io.BytesIO()
                plt.savefig(buf, format="svg")
                buf.seek(0)

                # Encode as base64 for embedding in HTML
                chart_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                plt.close(fig)
                plt.clf()

                buf.close()
                return chart_base64

            def plot_project_balance_graph(project_emissions_w, project_emissions_wo, project_emissions_balance):
                # Create the figure and axis
                fig, ax = plt.subplots(figsize=(6.5, 4))

                # Data
                labels = ["With", "Without", "Balance"]
                emissions = [project_emissions_w, project_emissions_wo, project_emissions_balance]
                # Create horizontal bar chart
                ax.barh(labels, emissions, color=["#1f77b4", "#ff7f0e", "#2ca02c"])

                for i, v in enumerate(emissions):
                    ax.text(0 if v > 0 else v, i, f"{v:,.2f}", va="center")

                # Add legend
                ax.text(0.5, 1.1, "tCO2e", ha="center", va="bottom", transform=ax.transAxes)

                # Customize the chart
                ax.ticklabel_format(style="plain", axis="x", useOffset=False)
                ax.grid(True, axis="x", linestyle="--", alpha=0.7)

                # Save to a BytesIO buffer
                buf = io.BytesIO()
                plt.savefig(buf, format="svg")
                buf.seek(0)

                # Encode as base64 for embedding in HTML
                chart_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                plt.close(fig)
                plt.clf()

                buf.close()
                return chart_base64

            # Get faologo.eps from static files
            try:
                faologo = open(os.path.join(settings.BASE_DIR, "media", f"faologo_{lang}.svg"), "rb")
            except FileNotFoundError:
                faologo = open(os.path.join(settings.BASE_DIR, "media", "faologo.svg"), "rb")

            # Add it as base64 to the context
            faologo_base64 = base64.b64encode(faologo.read()).decode("utf-8")

            project_chart_base64 = plot_project_balance_graph(project_emissions_w, project_emissions_wo, project_emissions_balance)
            project_gases_chart_base64 = plot_with_without_balance_bar_chart_stacked_by_gas(gases_w, gases_wo)

            download_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            context = {
                "project": project,
                "start_year_of_activities": project.start_year_of_activities,
                "implementation_years": project.implementation_years,
                "last_year_of_accounting": project.last_year_of_accounting,
                "total_project_years": (project.implementation_years + project.capitalization_years),
                "total_carbon_balance": project_emissions_balance,
                "project_emissions_w": project_emissions_w,
                "project_emissions_wo": project_emissions_wo,
                "project_emissions_balance": project_emissions_balance,
                "total_area": total_area,
                "total_heads": total_heads,
                "total_tonnes_of_catch": total_tonnes_of_catch,
                "soc": soc.value,
                "project_primary_ghg": project_primary_ghg,
                "project_primary_ghg_emissions": project_primary_ghg_emissions,
                "project_primary_ghg_direction": project_primary_ghg_direction,
                "project_secondary_ghg": project_secondary_ghg,
                "project_secondary_ghg_emissions": project_secondary_ghg_emissions,
                "project_secondary_ghg_direction": project_secondary_ghg_direction,
                "project_tertiary_ghg": project_tertiary_ghg,
                "project_tertiary_ghg_emissions": project_tertiary_ghg_emissions,
                "project_tertiary_ghg_direction": project_tertiary_ghg_direction,
                "activities": activities,
                "activities_total": activities_total,
                "project_chart_base64": project_chart_base64,
                "project_gases_chart_base64": project_gases_chart_base64,
                "faologo_base64": faologo_base64,
                "livestock_heads": livestock_heads,
                "small_fishery_types": small_fishery_types,
                "large_fishery_data": large_fishery_data,
                "aquaculture_data": aquaculture_data,
                "land_types": land_types,
                "download_date_time": download_date_time,
            }

            html = render(request, f"reports/{template_name}_{lang}.html", context).content.decode()

            # Generate PDF from HTML using WeasyPrint
            from weasyprint import HTML

            pdf = HTML(string=html).write_pdf()

            # Create the HTTP response with PDF content
            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{template_name}.pdf"'

            faologo.close()

            return response

        except Exception as e:
            return utils.ErrorResponse(f"Error generating PDF: {str(e)}", status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"])
    @swagger_auto_schema(
        responses={200: ProjectTagSerializer},
        operation_description="Get all tags for the current user",
    )
    def tags(self, request):
        tags = ProjectTag.objects.filter(user=self.request.user).values("name", "id").distinct()
        serializer = ProjectTagSerializer(tags, many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    @swagger_auto_schema(
        manual_parameters=[openapi.Parameter("pk", openapi.IN_PATH, description="Project ID", type=openapi.TYPE_STRING)],
        operation_description="Send recap email with project changes",
        responses={200: "Email sent successfully", 400: "Bad request", 500: "Internal server error"},
    )
    def recap(self, request, pk=None):
        project = self.get_object()
        error = security.check_permission("view_project", request.user, project)
        if error:
            return error

        try:
            utils.send_changes_email(project)
            return Response({"message": "Recap email sent successfully"}, status=http_status.HTTP_200_OK)

        except Exception as e:
            return utils.ErrorResponse(f"Error sending recap email: {str(e)}", status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectMembershipViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = ProjectMembership.objects.all()
    serializer_class = ProjectMembershipReadSerializer

    @swagger_auto_schema(
        operation_description="Get a single project membership by id",
        responses={
            400: "Bad request",
            403: "Selected user does not have permission to view project memberships",
            200: ProjectMembershipReadSerializer,
        },
    )
    def retrieve(self, request, *args, **kwargs):
        membership: ProjectMembership = self.get_object()
        error = security.check_permission("view_projectmembership", self.request.user, membership.project)
        if error:
            return error

        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Get all project memberships for a given project",
        responses={
            400: "Bad request",
            403: "Selected user does not have permission to view project memberships",
            200: ProjectMembershipReadSerializer,
        },
    )
    def list(self, request, *args, **kwargs):
        project_id = self.request.query_params.get("project_id", None)

        # TODO: Generalize query param validation checks
        if not project_id:
            logging.error("Project id not provided")
            return utils.ErrorResponse("Project id not provided", status=http_status.HTTP_400_BAD_REQUEST)

        project = get_object_or_404(Project, pk=project_id)
        error = security.check_permission("view_projectmembership", self.request.user, project)
        if error:
            return error

        serializer = ProjectMembershipReadSerializer(project.members.all(), many=True)

        return Response(serializer.data, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Create a new project membership",
        request_body=ProjectMembershipWriteSerializer,
        responses={
            400: "Bad request",
            201: "Project membership created successfully",
            403: "Selected user does not have permission to add project memberships",
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = ProjectMembershipWriteSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        project = serializer.validated_data["project"]
        error = security.check_permission("add_projectmembership", self.request.user, project)
        if error:
            return error

        membership = serializer.save()

        return Response(ProjectMembershipReadSerializer(membership).data, status=http_status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_description="Update a project membership",
        request_body=ProjectMembershipWriteSerializer,
        responses={
            400: "Bad request",
            200: "Project membership updated successfully",
            403: "Selected user does not have permission to change project memberships",
        },
    )
    def update(self, request, *args, **kwargs):
        membership = self.get_object()
        error = security.check_permission("change_projectmembership", self.request.user, membership.project)
        if error:
            return error

        serializer = ProjectMembershipWriteSerializer(data=request.data, instance=membership)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save()

        return Response(ProjectMembershipReadSerializer(membership).data, status=http_status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        membership = self.get_object()
        error = security.check_permission("change_projectmembership", self.request.user, membership.project)
        if error:
            return error

        serializer = ProjectMembershipWriteSerializer(data=request.data, instance=membership, partial=True)

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save()

        return Response(ProjectMembershipReadSerializer(membership).data, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Delete a project membership",
        responses={
            400: "Bad request",
            204: "Project membership deleted successfully",
            403: "Selected user does not have permission to delete project memberships",
        },
    )
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()

        if membership.user == self.request.user == membership.project.owner:
            other_admin = membership.project.members.filter(group__name="Admin").exclude(user=membership.project.owner).first()
            if not other_admin:
                return utils.ErrorResponse("Last remaining project Admin cannot delete their own membership. Delete the project instead.", status=http_status.HTTP_400_BAD_REQUEST)

            membership.project.owner = other_admin.user
            membership.project.save()

        error = security.check_permission("delete_projectmembership", self.request.user, membership.project)
        if error and not membership.user == self.request.user:
            return error

        if membership.group.name == "Admin":
            admin_count = membership.project.members.filter(group__name="Admin").count()
            if admin_count == 1:
                return utils.ErrorResponse("Cannot delete the last Admin in the project", status=http_status.HTTP_400_BAD_REQUEST)

        if membership.project.locked_by == membership.user:
            membership.project.unlock()

        membership.delete()

        return Response(status=http_status.HTTP_204_NO_CONTENT)


class ProjectNotificationPreferenceViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = ProjectNotificationPreference.objects.all()
    serializer_class = ProjectNotificationPreferenceReadSerializer

    def get_queryset(self):
        """Filter to only show the current user's notification preferences"""
        return self.queryset.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_description="Get notification preferences for the current user",
        responses={
            200: ProjectNotificationPreferenceReadSerializer(many=True),
        },
    )
    def list(self, request, *args, **kwargs):
        project_id = self.request.query_params.get("project_id", None)

        queryset = self.get_queryset()
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=http_status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Get or create notification preference for a specific project",
        responses={
            200: ProjectNotificationPreferenceReadSerializer,
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Create or update notification preference for a project",
        request_body=ProjectNotificationPreferenceWriteSerializer,
        responses={
            200: ProjectNotificationPreferenceReadSerializer,
            201: ProjectNotificationPreferenceReadSerializer,
            400: "Bad request",
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = ProjectNotificationPreferenceWriteSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        user = request.user
        project = serializer.validated_data["project"]

        # Get or create the preference
        preference, created = ProjectNotificationPreference.objects.get_or_create(user=user, project=project, defaults={"is_opted_out": serializer.validated_data["is_opted_out"]})

        if not created:
            # Update existing preference
            preference.is_opted_out = serializer.validated_data["is_opted_out"]
            preference.save()

        response_serializer = ProjectNotificationPreferenceReadSerializer(preference)
        status_code = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK

        return Response(response_serializer.data, status=status_code)

    @swagger_auto_schema(
        operation_description="Update notification preference for a project",
        request_body=ProjectNotificationPreferenceWriteSerializer,
        responses={
            200: ProjectNotificationPreferenceReadSerializer,
            400: "Bad request",
            403: "Forbidden",
        },
    )
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.user != request.user:
            return Response({"error": "You can only update your own notification preferences"}, status=http_status.HTTP_403_FORBIDDEN)

        serializer = ProjectNotificationPreferenceWriteSerializer(instance, data=request.data, partial=True, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save()
        response_serializer = ProjectNotificationPreferenceReadSerializer(instance)

        return Response(response_serializer.data, status=http_status.HTTP_200_OK)


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
        error = security.check_permission("view_projectinvitation", self.request.user, invitation.project)
        if error:
            return error

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

        serializer = ProjectInvitationWriteSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        project: Project = serializer.validated_data["project"]
        error = security.check_permission("add_projectinvitation", self.request.user, project)
        if error:
            return error

        try:
            email = serializer.validated_data["email"]
            email = email.casefold().strip()
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            logging.error(f"User with email {email} does not exist")
            return utils.ErrorResponse(f"User with email {email} does not exist", status=http_status.HTTP_400_BAD_REQUEST)

        # BUG: owner should already be a member of the project, so this should be redundant but apparently it's not
        if user == project.owner:
            logging.error("Project owner cannot be invited to the project")

        group: Group = serializer.validated_data["group"]
        invitation = ProjectInvitation.objects.filter(project=project, user=user, group=group).exclude(status__name=utils.InvitationStatus.REJECTED.value).first()

        if not invitation:
            invitation = ProjectInvitation(project=project, user=user, group=group)
            invitation.status = InvitationStatusType.objects.get(name_en=utils.InvitationStatus.PENDING.value)
            invitation.sender = self.request.user
            invitation.save()

        if not invitation.status.name_en == utils.InvitationStatus.PENDING.value:
            logging.warning(f"Invitation for {user.email} already sent with id {invitation.pk}")
            return Response({"message": f"Invitation for {user.email} already sent for group {invitation.group.name}"}, status=http_status.HTTP_200_OK)

        invitation_link = reverse("projectinvitations-accept", args=[invitation.token])
        invitation_subject = f'[EX-ACT] You have been invited to join the project "{project.name}"'
        context = {
            "project_title": project.name,
            "invitation_role": group.name,
            "invitation_recipient_name": user.get_full_name(),
            "invitation_link": request.build_absolute_uri(invitation_link),
            "exact_email": "ex-act@fao.org",
            "invitation_date": invitation.created_at.strftime("%Y-%m-%d"),
            "invitation_sender": invitation.sender.get_full_name(),
        }

        html_message = render_to_string(os.path.join(settings.BASE_DIR, "api", "templates", "invitation.html"), context)
        plain_message = render_to_string(os.path.join(settings.BASE_DIR, "api", "templates", "invitation.txt"), context)

        # Create and send email with both HTML and plain text versions to support different email clients
        # NOTE: Alternatives are in order of increasing preference
        email = EmailMultiAlternatives(subject=invitation_subject, body=plain_message, from_email=settings.EMAIL_HOST_USER, to=[invitation.user.email])
        email.attach_alternative(html_message, "text/html")
        email.send()

        logging.debug(f"Email sent to user ID {user.pk} with role {group.name} for project ID {project.pk}")
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
        error = security.check_permission("change_projectinvitation", self.request.user, invitation.project)
        if error:
            return error

        data = ProjectInvitationModelWriteSerializer(invitation, data=request.data, partial=True)

        if not data.is_valid():
            return Response(data.errors, status=http_status.HTTP_400_BAD_REQUEST)

        if invitation.status == "declined" or invitation.status == "accepted":
            logger.warning(f"Invitation already {invitation.status.name}. No further action is possible.")
            return Response({"message": f"Invitation already {invitation.status.name}. No further action is possible."}, status=http_status.HTTP_200_OK)

        new_status = data.validated_data.get("status", None)

        if new_status == invitation.status:
            logger.warning(f"Invitation already {new_status.name}")
            return Response({"message": f"Invitation already {new_status}"}, status=http_status.HTTP_200_OK)

        does_membership_exist = ProjectMembership.objects.filter(user=invitation.user, project=invitation.project, group=invitation.group).exists()
        if new_status.name_en == utils.InvitationStatus.ACCEPTED.value and not does_membership_exist:
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
        error = security.check_permission("view_projectinvitation", self.request.user, project)
        if error:
            return error

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
        invitation: ProjectInvitation = get_object_or_404(ProjectInvitation, token=token)

        serializer = ProjectInvitationAcceptSerializer(data=request.data, instance=invitation, partial=True, context={"token": token})
        serializer.is_valid(raise_exception=True)

        invitation = serializer.save()
        ProjectMembership.objects.create(user=invitation.user, project=invitation.project, group=invitation.group)

        return render(request, "invitation_accepted.html", {"project_name": invitation.project.name, "group": invitation.group.name, "link": settings.FRONTEND_URL})


class ActivityViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows activities to be viewed or edited.
    """

    queryset = Activity.objects.all()
    serializer_class = ActivitySerializerWithModules
    permission_classes = [api_permissions.IsPublicOrAuthenticated]

    def update(self, request, *args, **kwargs):
        activity = self.get_object()
        error = security.check_permission("change_activity", self.request.user, activity.project)
        if error:
            return error

        serializer = WriteActivitySerializer(data=request.data, instance=activity, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        activity = serializer.save()
        if activity.history.count() > 0:
            utils.update_change_reason(activity, utils.ChangeReasons.UPDATE.value)

        read_serializer = self.serializer_class(instance=activity)

        return Response(read_serializer.data, status=http_status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        activity = self.get_object()
        error = security.check_permission("change_activity", self.request.user, activity.project)
        if error:
            return error

        serializer = WriteActivitySerializer(data=request.data, partial=True, instance=activity, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        activity = serializer.save()
        if activity.history.count() > 0:
            utils.update_change_reason(activity, utils.ChangeReasons.UPDATE.value)

        read_serializer = self.serializer_class(instance=activity)

        return Response(read_serializer.data, status=http_status.HTTP_200_OK)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        _status = StatusType.objects.get_or_create(name_en="EMPTY")[0]
        request.data["status"] = _status.pk

        serializer = WriteActivitySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        error = security.check_permission("add_activity", self.request.user, serializer.validated_data["project"])
        if error:
            return error

        activity: Activity = serializer.save()
        activity.owner = self.request.user
        activity.save()

        utils.update_change_reason(activity, utils.ChangeReasons.CREATE.value)

        read_serializer = self.serializer_class(instance=activity)

        return Response(read_serializer.data, status=http_status.HTTP_201_CREATED)

    @swagger_auto_schema(manual_parameters=[project_id], responses={404: "Project not found"})
    def retrieve(self, request, pk=None):
        """
        Get a single activity for a given user.
        """
        logger.info("ActivityViewSet.retrieve")

        activity = get_object_or_404(Activity, pk=pk)
        error = security.check_permission("view_activity", self.request.user, activity.project)
        if error:
            return error

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
        is_b_intact = request.query_params.get("is_b_intact", False) == "true"
        SerializerClass = ActivitySerializerWithModules
        if is_summary:
            SerializerClass = ActivitySummarySerializer

        error = security.check_permission("view_activity", self.request.user, project)
        if error:
            return error

        def process_activity(activity):
            activity_dict = SerializerClass(activity).data
            return activity_dict

        activities_list = Activity.objects.filter(project__id=project_id)
        activities_list = activities_list.filter(is_b_intact=is_b_intact)

        # Start measuring time
        start = time.time()

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(activities_list, request)
        if page is not None:
            # Serial serialization: a default ThreadPoolExecutor() on Python 3.11
            # spawns min(32, cpu_count + 4) workers — each acquires its own
            # Django thread-local DB connection and saturates the App Engine
            # ↔ Cloud SQL Auth Proxy cap of 100 connections per instance.
            response = [process_activity(activity) for activity in page]
            logger.debug(f"Time taken to process activities: {time.time() - start}")
            return paginator.get_paginated_response(response)

        # End measuring time
        logger.debug(f"Time taken to process activities: {time.time() - start}")

        return Response(data=SerializerClass(activities_list, many=True).data, status=http_status.HTTP_200_OK)

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
        responses={400: "Bad request", 403: "Selected user does not have permission to view activity results", 200: ActivityResultSerializer},
    )
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the activity.
        """

        activity = Activity.objects.prefetch_related().get(pk=pk)
        error = security.check_permission("view_activity", self.request.user, activity.project)
        if error:
            return error

        response = {**ActivityResultSerializer(activity).data}

        modules = []
        # TODO: Make a serializer for this
        for module in activity.modules:
            if not module or (module.status and module.status.name_en != "READY"):
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
        error = security.check_permission("view_activity", self.request.user, activity.project)
        if error:
            return error

        modules = get_modules(activity)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(modules, request)
        if page is not None:
            return paginator.get_paginated_response(page)

        return Response(data=modules, status=http_status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="build")
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
        serializer.is_valid(raise_exception=True)

        project: Project = serializer.validated_data["project"]
        error = security.check_permission("add_activity", self.request.user, project)
        if error:
            return error

        try:
            activity = serializer.save()
        except ValidationError as e:
            return utils.ErrorResponse(e.detail, status=http_status.HTTP_400_BAD_REQUEST)

        return Response(self.serializer_class(activity).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    @swagger_auto_schema(
        responses={404: "Project not found", 403: "Selected user does not have permission to copy the activity", 201: ActivitySerializer},
        request_body=EmptySerializer,
    )
    @transaction.atomic
    def copy(self, request, pk=None):
        activity: Activity = get_object_or_404(Activity, pk=pk)
        error = security.check_permission("view_activity", self.request.user, activity.project)
        if error:
            return error

        if activity.project.is_finalized:
            return utils.ErrorResponse("Cannot copy activity from a finalized project", status=http_status.HTTP_400_BAD_REQUEST)

        if activity.project.is_archived:
            return utils.ErrorResponse("Cannot copy activity from an archived project", status=http_status.HTTP_400_BAD_REQUEST)

        new_activity = utils.copy_activity(activity, owner=self.request.user)

        return Response(data=self.serializer_class(new_activity).data, status=http_status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view activity changes", 200: ChangeHistorySerializer})
    def history(self, request, pk=None):
        activity: Activity = self.get_object()
        error = security.check_permission("view_activity", self.request.user, activity.project)
        if error:
            return error

        changes = utils.get_changes(activity.history.all())

        return Response(data=ChangeHistorySerializer(changes, many=True).data, status=http_status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        activity = self.get_object()
        error = security.check_permission("delete_activity", self.request.user, activity.project)
        if error:
            return error

        serializer = WriteActivitySerializer(data=request.data, instance=activity, partial=True, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        activity.delete()

        return Response(status=http_status.HTTP_204_NO_CONTENT)


class CommentThreadViewSet(viewsets.ModelViewSet):
    queryset = CommentThread.objects.all()
    serializer_class = CommentThreadSerializer

    @action(detail=True, methods=["get"])
    def comments(self, request, pk=None):
        """
        Lists the comments of a given thread.
        """

        thread = get_object_or_404(CommentThread, pk=pk)
        comments = thread.comments.filter(parent=None).all()

        return Response(data=CommentSerializer(comments, many=True).data, status=http_status.HTTP_200_OK)


class NoteViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer

    @transaction.atomic
    @swagger_auto_schema(responses={400: "Bad request", 201: NoteSerializer}, request_body=NewNoteSerializer)
    def create(self, request, *args, **kwargs):
        serializer = NewNoteSerializer(data=request.data, context={"request": request})

        project = None

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        module_type = get_object_or_404(ModuleType, pk=serializer.validated_data["module_type_id"])

        ModuleClass = utils.get_model(module_type.class_name, suffix=None)
        module: Module | Submodule | Project = get_object_or_404(ModuleClass, pk=serializer.validated_data["module_id"])
        project = module.project if module_type.class_name != "Project" else module

        if not utils.has_project_permission("add_note", self.request.user, project):
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
        if note.history.count() > 0:
            utils.update_change_reason(note, utils.ChangeReasons.UPDATE.value)

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
        if note.history.count() > 0:
            utils.update_change_reason(note, utils.ChangeReasons.UPDATE.value)

        return Response(self.serializer_class(note).data, status=http_status.HTTP_200_OK)


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

        return Response(data=CommentSerializer(replies, many=True).data, status=http_status.HTTP_200_OK)

    def list(self, request):
        """
        Get all comments.
        """
        thread_id = self.request.query_params.get("thread", None)

        if thread_id is None:
            return utils.ErrorResponse("Thread id not provided", status=http_status.HTTP_400_BAD_REQUEST)

        comments = Comment.objects.filter(thread__id=thread_id, parent=None).all()
        serializer = CommentSerializer(comments, many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)


class ModuleTypeViewSet(viewsets.ModelViewSet, PublicViewSet):
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
        permission_classes = [api_permissions.IsPublicOrAuthenticated]

        def get_serializer_class(self):
            if self.action in ["create", "update", "partial_update"]:
                return get_module_serializer(model, action=ActionTypes.CREATE)
            return get_module_serializer(model)

        def update(self, request, pk=None):
            """
            Updates a module.
            """

            module: Module | Submodule | LandModule = get_object_or_404(model, pk=pk)
            activity: Activity = module.get_activity()

            error = security.check_permission("change_modules", self.request.user, activity.project)
            if error:
                return error

            serializer = get_module_serializer(model, action=ActionTypes.CREATE)(data=request.data, partial=True, instance=module, context={"request": request})

            if not serializer.is_valid():
                return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

            module = serializer.save()
            if module.history.count() > 0:
                utils.update_change_reason(module, utils.ChangeReasons.UPDATE.value)

            if hasattr(module, "land_use_change") and module.land_use_change is not None:
                module.invalidate_luc_results()

            read_serializer = get_module_serializer(model)(instance=module, context={"request": request})

            return Response(read_serializer.data, status=http_status.HTTP_200_OK)

        def partial_update(self, request, pk=None):
            """
            Partially updates a module.
            """

            module: Module | Submodule = get_object_or_404(model, pk=pk)
            activity: Activity = module.get_activity()

            error = security.check_permission("change_modules", self.request.user, activity.project)
            if error:
                return error

            serializer = get_module_serializer(model, action=ActionTypes.CREATE)(data=request.data, partial=True, instance=module, context={"request": request})

            if not serializer.is_valid():
                return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

            module = serializer.save()
            if module.history.count() > 0:
                utils.update_change_reason(module, utils.ChangeReasons.UPDATE.value)

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

            module_serializer = get_module_serializer(model, action=ActionTypes.CREATE)(data=request.data, many=isinstance(request.data, list), context={"request": request})
            module_type = ModuleType.objects.get(class_name=model.__name__)

            if not module_serializer.is_valid():
                logger.error(f"Error creating module: {module_serializer.errors}")
                return Response(module_serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

            if module_type.is_submodule:
                activity: Activity = module_serializer.validated_data["parent"].activity
            else:
                activity: Activity = module_serializer.validated_data["activity"]

            error = security.check_permission("add_modules", self.request.user, activity.project)
            if error:
                return error

            module_serializer.save()

            read_serializer = get_module_serializer(model, action=ActionTypes.RETRIEVE)(instance=module_serializer.instance, context={"request": request})

            try:
                utils.update_change_reason(module_serializer.instance, utils.ChangeReasons.CREATE.value)
            except AttributeError:
                logger.warning("Module does not have a change reason attribute")
                pass

            logging.debug(f"END GenericModuleViewSet[{model.__name__}].create")

            return Response(read_serializer.data, status=http_status.HTTP_201_CREATED)

        @swagger_auto_schema(
            manual_parameters=[activity_id, module_type, page_size, page],
            responses={400: "Bad request", 403: "Selected user does not have permission to view the module", 200: get_module_serializer(model)},
        )
        def list(self, request):
            """
            Lists the module(s) of a given activity
            by filtering against an `activity_id` query parameter in the URL or
            by filtering against the 'module_type' query parameter in the URL.
            """

            activity_id = utils.get_query_param_or_validation_error(self.request, "activity")
            activity = get_object_or_404(Activity, pk=activity_id)
            module_type = ModuleType.objects.get(class_name=model.__name__)

            error = security.check_permission("view_modules", self.request.user, activity.project)
            if error:
                return error

            if module_type.is_submodule:
                modules = model.objects.filter(parent__activity__id=activity_id).all()
            else:
                modules = model.objects.filter(activity__id=activity_id).all()

            data = []

            for i, module in enumerate(modules):
                serializer = get_module_serializer(model)(instance=module, context={"request": request})
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
                    enum=[BreakdownTypes.TOTAL.value, BreakdownTypes.ACTIVITY.value, BreakdownTypes.GAS.value, BreakdownTypes.ACTIVITY_GAS.value],
                ),
                openapi.Parameter("cached", openapi.IN_QUERY, description="Use cached results", type=openapi.TYPE_BOOLEAN),
            ],
            responses={400: "Bad request", 403: "Selected user does not have permission to view module results", 200: DynamicResultSerializer},
        )
        def results(self, request, pk=None):
            """
            Calculates and returns total emissions for a single module.
            """
            logger.debug(f"START GenericModuleViewSet.results for module {model} {pk}")
            module: Module | Submodule = get_object_or_404(model, pk=pk)
            activity = module.get_activity()

            error = security.check_permission("view_modules", self.request.user, activity.project)
            if error:
                return error

            serializer = get_module_serializer(model, ActionTypes.RETRIEVE)(data={"activity": activity.pk}, partial=True, instance=module, context={"request": request})
            serializer.is_valid(raise_exception=True)

            if module.module_type.class_name == LandUseChange.__name__:
                module: LandUseChange

                if not all(m.is_ready() for m in module.get_modules()):
                    return utils.ErrorResponse("Not all modules are ready. Land Use Change module cannot be calculated.")
            else:
                if not module.is_ready():
                    logger.error(f"Module {module.module_type} is not ready. Cannot calculate result.")
                    return utils.ErrorResponse("Module is not ready. Cannot calculate result.")

            try:
                aggregate_by = BreakdownTypes(request.query_params.get("aggregate", BreakdownTypes.TOTAL))
                module_results = module.get_cached_results(by=aggregate_by)
                use_cached_results = request.query_params.get("cached", "true") == "true"

                if module_results is None or not use_cached_results:
                    logger.debug(f"Cache is invalid. Calculating results for module {module.id}")
                    total, by_activity, by_gas, by_activity_gas, inventory = CalculatorFactory().calculate_result(module)

                    results_total = DynamicResultFactory.create(activity, total, aggregate_by=BreakdownTypes.TOTAL).data
                    results_by_activity = DynamicResultFactory.create(activity, by_activity, aggregate_by=BreakdownTypes.ACTIVITY).data
                    results_by_gas = DynamicResultFactory.create(activity, by_gas, aggregate_by=BreakdownTypes.GAS).data
                    results_by_activity_gas = DynamicResultFactory.create(activity, by_activity_gas, aggregate_by=BreakdownTypes.ACTIVITY_GAS).data

                    results_total["inventory"] = inventory.breakdown(by=BreakdownTypes.TOTAL)
                    results_by_activity["inventory"] = inventory.breakdown(by=BreakdownTypes.ACTIVITY)
                    results_by_gas["inventory"] = inventory.breakdown(by=BreakdownTypes.GAS)
                    results_by_activity_gas["inventory"] = inventory.breakdown(by=BreakdownTypes.ACTIVITY_GAS)

                    module_results = (
                        results_total
                        if aggregate_by == BreakdownTypes.TOTAL
                        else results_by_activity
                        if aggregate_by == BreakdownTypes.ACTIVITY
                        else results_by_gas
                        if aggregate_by == BreakdownTypes.GAS
                        else results_by_activity_gas
                    )
                    module.cache_results(results_total, results_by_activity, results_by_gas, results_by_activity_gas)

                serializer = DynamicResultSerializer(module_results, aggregate_by=aggregate_by)
                serialized_data = serializer.data

                return Response(serialized_data)

            except Exception as e:
                logging.error("Error calculating result in GenericModuleViewSet.results", e)
                return utils.ErrorResponse(str(e))

        @action(detail=True, methods=["get"], url_path="defaults")
        def defaults(self, request, pk=None):
            """
            Returns the default values for a module.

            ex. GET /annual-croplands/1/defaults/
            """

            module: Module | Submodule = get_object_or_404(model, pk=pk)

            error = security.check_permission("view_modules", self.request.user, module.activity.project)
            if error:
                return error

            try:
                defaults: SimpleNamespace = DefaultsFactory.get_defaults(module, calculate=True)

                if isinstance(defaults, dict):
                    defaults = SimpleNamespace(**defaults)

                return Response(defaults.__dict__)
            except Exception as e:
                return utils.ErrorResponse(str(e))

        @action(detail=True, methods=["get"])
        @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view module changes", 200: ChangeHistorySerializer})
        def history(self, request, pk=None):
            module: Module | Submodule = get_object_or_404(model, pk=pk)
            activity = module.get_activity()

            error = security.check_permission("view_modules", self.request.user, activity.project)
            if error:
                return error

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

            error = security.check_permission("view_modules", self.request.user, activity.project)
            if error:
                return error

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
        filter_backends = [filters.OrderingFilter, DjangoFilterBackend, api_filters.DynamicSearchAndFilterBackend]

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
        filterset_class = api_filters.get_model_filter(model)
        filter_backends = [filters.OrderingFilter, DjangoFilterBackend, api_filters.DynamicSearchAndFilterBackend]

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
        if getattr(self, "swagger_fake_view", False):
            return {}
        context = super().get_serializer_context()
        project_id = self.kwargs.get("project_pk")
        context["project"] = get_object_or_404(Project, pk=project_id)
        context["user"] = self.request.user
        return context

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        project_id = self.kwargs.get("project_pk")
        project = get_object_or_404(Project, pk=project_id)

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = ProjectTagSerializer(data=request.data, context={"project": project, "user": self.request.user})

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save(project=project, user=self.request.user)

        return Response(serializer.data, status=http_status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        project_id = self.kwargs.get("project_pk")
        search = self.request.query_params.get("search", None)

        project = get_object_or_404(Project, pk=project_id)

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        filters = {"project": project, "user": self.request.user}

        if search:
            filters["name__icontains"] = search

        queryset = ProjectTag.objects.filter(**filters)
        serializer = ProjectTagSerializer(queryset, many=True)

        return Response(serializer.data, status=http_status.HTTP_200_OK)


class ProjectFileAttachmentViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = ProjectFileAttachment.objects.all()
    serializer_class = ProjectFileUploadSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name"]
    ordering = ["name"]

    def get_serializer_context(self):
        if getattr(self, "swagger_fake_view", False):
            return {}
        context = super().get_serializer_context()
        project_id = self.kwargs.get("project_pk")
        context["project"] = get_object_or_404(Project, pk=project_id)
        context["user"] = self.request.user
        return context

    @transaction.atomic
    def create(self, request):
        project_id = request.data.get("project", None)

        if project_id is None:
            return utils.ErrorResponse("Project not provided", status=http_status.HTTP_400_BAD_REQUEST)

        project = get_object_or_404(Project, pk=project_id)

        if not utils.has_project_permission("change_project", self.request.user, project):
            logging.error("Selected user does not have permission to edit the project")
            return utils.ErrorResponse("Selected user does not have permission to edit the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = ProjectFileUploadSerializer(data=request.data, context={"project": project, "user": self.request.user})

        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        attachment = serializer.save(project=project, user=self.request.user)
        read_serializer = ProjectFileReadSerializer(instance=attachment)

        return Response(read_serializer.data, status=http_status.HTTP_201_CREATED)

    def list(self, request):
        project_id = self.request.query_params.get("project_id", None)
        search = self.request.query_params.get("search", None)

        project = get_object_or_404(Project, pk=project_id)

        if not utils.has_project_permission("view_project", self.request.user, project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        filters = {"project": project}

        if search:
            filters["name__icontains"] = search

        queryset = ProjectFileAttachment.objects.filter(**filters)
        serializer = ProjectFileReadSerializer(queryset, many=True)

        return Response(serializer.data, status=http_status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        attachment = get_object_or_404(ProjectFileAttachment, pk=pk)

        if not utils.has_project_permission("view_project", self.request.user, attachment.project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        serializer = ProjectFileReadSerializer(attachment)

        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        logger.debug(f"START ProjectFileAttachmentViewSet.download for attachment {pk}")
        attachment = get_object_or_404(ProjectFileAttachment, pk=pk)

        if not utils.has_project_permission("view_project", self.request.user, attachment.project):
            logging.error("Selected user does not have permission to view the project")
            return utils.ErrorResponse("Selected user does not have permission to view the project", status=http_status.HTTP_403_FORBIDDEN)

        client = storage.Client()
        bucket = client.bucket(settings.STORAGE_BUCKET)

        if not bucket.exists():
            logging.error("Bucket does not exist")
            return utils.ErrorResponse("Bucket does not exist", status=http_status.HTTP_404_NOT_FOUND)

        blob = bucket.blob(f"projects/{attachment.project.id}/{attachment.name}")

        def file_iterator(blob):
            with blob.open("rb") as f:
                for line in f:
                    yield line

        response = HttpResponse(file_iterator(blob), content_type=blob.content_type)
        response["Content-Disposition"] = f"attachment; filename={attachment.name}"

        logger.debug(f"END ProjectFileAttachmentViewSet.download for attachment {pk}")
        return response

    def destroy(self, request, pk=None):
        attachment = get_object_or_404(ProjectFileAttachment, pk=pk)

        if not utils.has_project_permission("change_project", self.request.user, attachment.project):
            logging.error("Selected user does not have permission to edit the project")
            return utils.ErrorResponse("Selected user does not have permission to edit the project", status=http_status.HTTP_403_FORBIDDEN)

        client = storage.Client()
        bucket = client.bucket(settings.STORAGE_BUCKET)
        blob = bucket.blob(f"projects/{attachment.project.id}/{attachment.name}")

        blob.delete()
        attachment.delete()

        return Response(status=http_status.HTTP_204_NO_CONTENT)


class APIHealthView(views.APIView):
    permission_classes = [permissions.AllowAny]

    CACHE_KEY = "api_health_status"
    CACHE_TIMEOUT_SECONDS = 60

    @swagger_auto_schema(responses={503: APIStatusSerializer, 200: APIStatusSerializer})
    def get(self, request):
        status = http_status.HTTP_200_OK
        cached_status: dict = cache.get(self.CACHE_KEY)

        if cached_status:
            if cached_status["is_under_maintenance"]:
                status = http_status.HTTP_503_SERVICE_UNAVAILABLE
            return Response(cached_status, status=status)

        try:
            api_status = APIHealth.objects.first()
            serializer = APIStatusSerializer(api_status)
            if api_status and api_status.is_under_maintenance:
                status = http_status.HTTP_503_SERVICE_UNAVAILABLE
        except APIHealth.DoesNotExist:
            pass

        cache.set(self.CACHE_KEY, serializer.data, self.CACHE_TIMEOUT_SECONDS)
        return Response(serializer.data, status=status)


class FuelTypeViewSet(viewsets.ModelViewSet, PublicViewSet, DynamicFilterViewSet):
    queryset = FuelType.objects.all()
    serializer_class = FuelTypeSerializer


class SoilTypeViewset(viewsets.ModelViewSet, PublicViewSet):
    queryset = SoilType.objects.all()
    serializer_class = get_model_serializer(SoilType)
    filter_backends = [DjangoFilterBackend]
    filterset_class = api_filters.SoilTypeFilter

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name="all",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_BOOLEAN,
                description="Retrieve all entries.",
            ),
        ],
        responses={200: get_model_serializer(SoilType)(many=True)},
        description="Retrieve a list of entries filtered by coastal status.",
    )
    def get_queryset(self):
        queryset = super().get_queryset()

        if "all" in self.request.query_params:
            all = self.request.query_params.get("all", None)
            if all == "true":
                return queryset

        if "active" not in self.request.query_params:
            queryset = queryset.filter(active=True)
        if "is_coastal" not in self.request.query_params:
            queryset = queryset.filter(is_coastal=False)

        return queryset


def generate_chart(with_value, without_value, balance):
    # Create the bar chart
    fig, ax = plt.subplots(figsize=(10, 4))
    labels = ["With", "Without", "Balance"]
    values = [with_value, without_value, balance]
    colors = ["green" if v < 0 else "red" for v in values]

    # Create horizontal bar chart
    ax.barh(labels, values, color=colors)

    # Customize the chart
    ax.set_xlim(min(values) - 10000, max(values) + 10000)
    ax.grid(True, axis="x", linestyle="--", alpha=0.7)

    # Save the chart
    chart_path = os.path.join(settings.STATIC_ROOT, "images", "ghg_chart.png")
    os.makedirs(os.path.dirname(chart_path), exist_ok=True)
    plt.savefig(chart_path, bbox_inches="tight", dpi=300)
    plt.close()


class PublicTokenViewset(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = PublicToken.objects.all()
    serializer_class = PublicTokenSerializer

    def create(self, request, *args, **kwargs):
        project = get_object_or_404(Project, pk=self.kwargs.get("project_pk", None))

        error = security.check_permission("create_publictoken", self.request.user, project)
        if error:
            return error

        serializer = PublicTokenSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        serializer.save(project=project, user=self.request.user)

        return Response(serializer.data, status=http_status.HTTP_201_CREATED)


class HandInHandAssessmentViewSet(viewsets.ModelViewSet, PublicViewSet):
    """
    API endpoint that allows Hand in Hand assessments to be viewed or edited.
    """

    queryset = HandInHandAssessment.objects.all()
    serializer_class = HandInHandAssessmentSerializer

    # Cache settings
    CACHE_KEY_PREFIX = "handinhand_assessments"
    CACHE_TIMEOUT_SECONDS = 60 * 15  # 15 minutes

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "grouped",
                openapi.IN_QUERY,
                description="Return assessments grouped by region > country > year",
                type=openapi.TYPE_BOOLEAN,
            ),
            openapi.Parameter(
                "cached",
                openapi.IN_QUERY,
                description="Return cached results",
                type=openapi.TYPE_BOOLEAN,
            ),
        ],
        responses={200: HandInHandAssessmentGroupedSerializer},
    )
    def list(self, request, *args, **kwargs):
        """
        Get all Hand in Hand assessments, optionally grouped by region > country > year
        """
        grouped = request.query_params.get("grouped", "false").lower() == "true"
        use_cache = request.query_params.get("cached", "true").lower() == "true"

        # Generate cache key based on grouping option
        cache_key = f"{self.CACHE_KEY_PREFIX}_{'grouped' if grouped else 'list'}"

        # Try to get cached data if cache is enabled
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return Response(cached_data)

        if grouped:
            serializer = HandInHandAssessmentGroupedSerializer(data={})
            response_data = serializer.to_representation(None)
        else:
            response_data = super().list(request, *args, **kwargs).data

        # Cache the response data
        if use_cache:
            cache.set(cache_key, response_data, self.CACHE_TIMEOUT_SECONDS)

        return Response(response_data)


class MinitoolProcessingView(APIView):
    """
    API endpoint for running minitool processing locally
    Replicates the functionality of the GCP Cloud Function
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Check if user is staff
        if not request.user.is_staff:
            return Response({"error": "Access denied. Staff privileges required."}, status=http_status.HTTP_403_FORBIDDEN)

        # # Check for additional password
        # password = request.data.get("password")
        # if not password:
        #     return Response({"error": "Additional password required for minitool processing"}, status=http_status.HTTP_400_BAD_REQUEST)

        # minitool_password = os.getenv("MINITOOL_API_PASSWORD", "default_password_change_me")
        # if password != minitool_password:
        #     return Response({"error": "Invalid password"}, status=http_status.HTTP_401_UNAUTHORIZED)

        # Validate request data
        is_valid, message, config = self._validate_request_data(request.data)
        if not is_valid:
            return Response({"error": message}, status=http_status.HTTP_400_BAD_REQUEST)

        # Run minitool processing
        try:
            from django.core.management import call_command
            from django.core.management.base import CommandError
            from io import StringIO

            output = StringIO()
            call_command("compute_minitool", stdout=output)
            results = output.getvalue()
            return Response({"status": "success", "message": "Processing completed successfully", "results": results})
        except CommandError as e:
            return Response({"error": f"Processing failed: {e}"}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Minitool processing error: {str(e)}")
            return Response({"error": f"Processing failed: {str(e)}"}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _validate_request_data(self, request_data):
        """Validate and sanitize request data"""
        if not request_data:
            return False, "No data provided", {}

        # Extract and validate parameters
        config = {"modules": {}, "performance": {}}

        # Module configuration
        valid_modules = ["annual_cropland", "flooded_rice", "grassland", "livestock", "perennial_cropland", "forest_management", "small_fishery", "large_fishery"]

        modules_config = request_data.get("modules", {})
        if isinstance(modules_config, dict):
            for module in valid_modules:
                config["modules"][module] = modules_config.get(module, False)
        else:
            # Legacy support: single module name
            module_name = request_data.get("module_name", "small_fishery")
            if module_name in valid_modules:
                config["modules"][module_name] = True

        # Performance configuration
        config["performance"] = {
            "max_rows": min(int(request_data.get("max_rows", 10000)), 100000),  # Cap at 100k
            "max_workers": min(int(request_data.get("max_workers", 4)), 16) if request_data.get("max_workers") else None,
            "chunk_size": min(int(request_data.get("chunk_size", 10000)), 50000),  # Cap at 50k
        }

        return True, "Valid request", config

    def _run_minitool_processing(self, config):
        """Run minitool processing with the provided configuration"""
        import sys
        import os
        import tempfile
        import yaml
        from pathlib import Path

        # Add scripts directory to path
        scripts_dir = Path(settings.BASE_DIR) / "scripts"
        sys.path.insert(0, str(scripts_dir))

        try:
            # Import minitool components
            import api.minitool as minitool
            import api.models as models

            # Initialize components
            data_builder_registry = minitool.ModuleDataBuilderRegistry()
            processor_registry = minitool.ProcessorRegistry(data_builder_registry)
            data_manager = minitool.DataManager()
            permutation_computer = minitool.PermutationComputer(processor_registry)

            # Load configuration
            config_loader = minitool.ConfigurationLoader()
            loaded_config = config_loader.load_config(local=True)

            # Extract configuration
            runtime_config = {**loaded_config["modules"], **loaded_config["performance"]}

            results_summary = {"processed_modules": [], "total_records": 0, "total_errors": 0, "files_created": []}

            # Process enabled modules
            for module_name, module_config in minitool.MODULE_CONFIGS.items():
                if runtime_config.get(module_config["config_name"], False):
                    try:
                        model_class = getattr(models, module_name)
                        data, errors = permutation_computer.compute_permutations(
                            module_config["fields"],
                            model_class,
                            chunk_size=runtime_config["chunk_size"],
                            stop_at=runtime_config["max_rows"],
                            max_workers=runtime_config["max_workers"],
                        )

                        if data or errors:
                            data_manager.save_data(data, errors, module_name)

                            results_summary["processed_modules"].append(module_name)
                            results_summary["total_records"] += len(data)
                            results_summary["total_errors"] += len(errors)
                            results_summary["files_created"].extend([f"minitool/{module_name.lower()}.csv", f"minitool/{module_name.lower()}_errors.csv"])

                    except Exception as e:
                        logger.error(f"Error processing {module_name}: {str(e)}")
                        results_summary["total_errors"] += 1

            return results_summary

        except Exception as e:
            logger.error(f"Critical error in minitool execution: {str(e)}")
            raise
