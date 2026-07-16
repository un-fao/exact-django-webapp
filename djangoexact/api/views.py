import json
import os
import logging
import uuid
from pathlib import Path
from types import SimpleNamespace
from django.urls import reverse
from django.conf import settings
from django.shortcuts import render
import numpy as np
import traceback

from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db.models import Model
from django.utils import timezone
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
    ProjectExportSerializer,
    ProjectImportSerializer,
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
from django.http import HttpResponse
from concurrent.futures import ThreadPoolExecutor, as_completed
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
activity_status = openapi.Parameter(
    "status",
    openapi.IN_QUERY,
    description="Filter activities by computed status. Accepts one or more values as a comma-separated list and/or a repeated parameter (e.g. status=IN PROGRESS,EMPTY).",
    type=openapi.TYPE_ARRAY,
    items={"type": openapi.TYPE_STRING, "enum": ["READY", "IN PROGRESS", "EMPTY"]},
)
activity_ready = openapi.Parameter(
    "ready",
    openapi.IN_QUERY,
    description="Convenience status filter: true returns only READY activities, false returns the rest (IN PROGRESS and EMPTY). Intersects with `status` when both are given.",
    type=openapi.TYPE_BOOLEAN,
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

        validate_password(new_password, user=user)
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


def get_version_config():
    """Read version config from file or environment."""
    config_paths = [
        Path(__file__).parent.parent.parent / 'version.config.json',
        Path(os.environ.get('EXACT_USER_DATA_DIR', '')) / 'version.config.json',
    ]
    for config_path in config_paths:
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
    # Default for development
    return {"appVersion": "1.0.0", "compatibilityGroup": 1}


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
                            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                            cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", [sm.id])  # nosec B608
                    table_name = m._meta.db_table
                    # Ensures the table is a valid identifier, reducing the risk of SQL injection
                    if not table_name.isidentifier():
                        raise ValueError("Invalid table name")
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", [m.id])  # nosec B608

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
            with ThreadPoolExecutor(max_workers=10) as executor:
                response = list(executor.map(serialize_project, page))
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

        selected_activities = [pk.strip() for pk in request.query_params.get("activities", "").split(",") if pk.strip().isdigit()]
        if not selected_activities:
            selected_activities = project.activities.values_list("id", flat=True)

        response = serialized_project
        response["activities"] = []

        # Function to process an activity
        def process_activity(activity_pk):
            return ActivityViewSet.results(self, request, pk=activity_pk).data

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
                    logging.error(f"Activity {pk} generated an exception: {exc}")
                    # You can choose to handle exceptions differently if needed
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

        selected_activities = [pk.strip() for pk in request.query_params.get("activities", "").split(",") if pk.strip().isdigit()]
        if not selected_activities:
            selected_activities = project.activities.all()
        else:
            selected_activities = project.activities.filter(pk__in=selected_activities)
        selected_activities = list(selected_activities)

        if not project.is_ready(selected_activities):
            logging.error("Project is not ready")
            return utils.ErrorResponse("To get a report for a project, all activities must have been completed.", status=http_status.HTTP_400_BAD_REQUEST)

        if request.query_params.get("template", None):
            response = self.template(request, pk=pk)
            return response

        try:
            from .reports import generate_excel_report
            file_bytes_buffer = generate_excel_report(project, activities=selected_activities)
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

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(
        operation_description="Export project as .exactproject file",
        responses={
            200: "Project exported successfully",
            403: "Permission denied",
            404: "Project not found"
        }
    )
    def export(self, request, pk=None):
        """Export a project with all its activities and modules."""
        project: Project = get_object_or_404(Project, pk=pk)

        # Check permission
        error = security.check_permission("view_project", request.user, project)
        if error:
            return error

        # Generate export_id if not exists
        if not project.export_id:
            project.export_id = uuid.uuid4()
            project.save(update_fields=['export_id'])

        # Get version config
        version_config = get_version_config()

        # Build export data
        serializer = ProjectExportSerializer(project)
        export_data = {
            "formatVersion": 1,
            "appVersion": version_config.get("appVersion", "1.0.0"),
            "compatibilityGroup": version_config.get("compatibilityGroup", 1),
            "exportedAt": timezone.now().isoformat(),
            "exportId": str(project.export_id),
            "project": serializer.data
        }

        # Return as JSON file
        response = HttpResponse(
            json.dumps(export_data, indent=2, default=str),
            content_type="application/json"
        )
        safe_name = project.name.replace('"', '').replace('/', '-')[:50]
        response["Content-Disposition"] = f'attachment; filename="{safe_name}.exactproject"'
        return response

    @action(detail=False, methods=["post"])
    @swagger_auto_schema(
        operation_description="Import a .exactproject file",
        request_body=ProjectImportSerializer,
        responses={
            200: "Project already exists",
            201: "Project imported successfully",
            400: "Invalid file format or compatibility mismatch"
        }
    )
    def import_project(self, request):
        """Import a project from .exactproject file data."""
        serializer = ProjectImportSerializer(data=request.data)
        if not serializer.is_valid():
            return utils.ErrorResponse(
                serializer.errors,
                status=http_status.HTTP_400_BAD_REQUEST
            )

        validated_data = serializer.validated_data
        export_id = validated_data['exportId']
        force_copy = request.query_params.get('forceCopy', 'false').lower() == 'true'

        # Check if project with this export_id already exists
        if not force_copy:
            existing = Project.objects.filter(export_id=export_id).first()
            if existing:
                return Response({
                    "exists": True,
                    "projectId": existing.id,
                    "projectName": existing.name
                }, status=http_status.HTTP_200_OK)

        # Create new project
        project_data = validated_data['project'].copy()

        def _create_comment(thread, comment_data, author_cache, parent=None):
            """
            Recursively create a comment and its replies.
            Returns the created Comment instance.
            """
            from dateutil import parser as date_parser

            author_email = comment_data.get('author_email')
            author = None
            if author_email:
                if author_email in author_cache:
                    author = author_cache[author_email]
                else:
                    author = CustomUser.objects.filter(email=author_email).first()
                    author_cache[author_email] = author

            # If author not found, use the importing user
            if author is None:
                author = request.user

            # Parse date_created if provided
            date_created = None
            if comment_data.get('date_created'):
                try:
                    date_created = date_parser.parse(comment_data['date_created'])
                except (ValueError, TypeError):
                    pass

            comment = Comment.objects.create(
                thread=thread,
                parent=parent,
                author=author,
                content=comment_data.get('content', ''),
            )

            # Update date_created if provided (auto_now_add prevents setting during create)
            if date_created:
                Comment.objects.filter(pk=comment.pk).update(date_created=date_created)

            # Create replies recursively
            for reply_data in comment_data.get('replies', []):
                _create_comment(thread, reply_data, author_cache, parent=comment)

            return comment

        def _reconstruct_threads(instance, module_data, author_cache):
            """
            Reconstruct CommentThread objects for a module from exported thread data.
            This handles thread fields that contain comment data from the export.
            """
            for field in instance._meta.get_fields():
                if not hasattr(field, 'column'):
                    continue
                field_name = field.name
                if not field_name.endswith('_thread'):
                    continue

                thread_data = module_data.get(field_name)
                if not thread_data or not isinstance(thread_data, dict):
                    continue

                comments_data = thread_data.get('comments', [])
                if not comments_data:
                    continue

                # Get the thread that was created by the module's save() method
                thread = getattr(instance, field_name, None)
                if thread is None:
                    # Create a new thread if one doesn't exist
                    thread = CommentThread.objects.create()
                    setattr(instance, field_name, thread)
                    instance.save(update_fields=[field_name])

                # Create comments within the thread
                for comment_data in comments_data:
                    _create_comment(thread, comment_data, author_cache)

        def prepare_model_data(model_class, data, module_id_map=None):
            """
            Filter data to valid model fields and convert FK fields to use _id suffix.
            Django expects FK fields as either model instances or field_id=integer.
            Since exports contain integer IDs, we need to use the _id suffix.

            For OneToOneField cross-references between modules in the same
            activity (e.g. Settlement.land_use_change → LandUseChange),
            ``module_id_map`` remaps old PKs to newly-created instances.
            """
            import re
            from django.db.models import ForeignKey
            from django.db.models.fields.related import OneToOneField

            if module_id_map is None:
                module_id_map = {}

            result = {}
            for field in model_class._meta.get_fields():
                if not hasattr(field, 'column'):
                    continue
                field_name = field.name
                if field_name not in data:
                    continue
                value = data[field_name]

                # Skip _thread FK fields — these now contain thread/comment data
                # that will be reconstructed after the module is created.
                if isinstance(field, ForeignKey) and field_name.endswith('_thread'):
                    continue

                # OneToOneField cross-module references need ID remapping
                # because the referenced module was re-created with a new PK.
                if isinstance(field, OneToOneField):
                    if isinstance(value, int) and value in module_id_map:
                        # New export format: integer ID that maps to a
                        # previously-created module in this activity.
                        result[f"{field_name}_id"] = module_id_map[value].id
                    elif isinstance(value, str):
                        # Old export format: string like "(4) LandUseChange
                        # in settlements". Parse the PK and remap.
                        match = re.match(r'\((\d+)\)', value)
                        if match:
                            old_pk = int(match.group(1))
                            if old_pk in module_id_map:
                                result[f"{field_name}_id"] = module_id_map[old_pk].id
                        # If not in the map the target module hasn't been
                        # created yet or doesn't exist — skip gracefully
                        # (the field is nullable).
                    elif isinstance(value, int):
                        # Reference-data FK (e.g. OrganicSoil pointing to
                        # a shared record) — not in the map, use as-is.
                        result[f"{field_name}_id"] = value
                    continue

                # For ForeignKey fields with integer values, use field_id suffix
                if isinstance(field, ForeignKey) and isinstance(value, int):
                    result[f"{field_name}_id"] = value
                else:
                    result[field_name] = value
            return result

        try:
            with transaction.atomic():
                # Extract activities before creating project
                activities_data = project_data.pop('activities', [])

                # Prepare project data with proper FK handling
                filtered_project_data = prepare_model_data(Project, project_data)

                # Generate unique name if needed (unique_together on name + owner)
                base_name = filtered_project_data.get('name', 'Imported Project')
                name = base_name
                counter = 1
                while Project.objects.filter(name=name, owner=request.user).exists():
                    counter += 1
                    name = f"{base_name} (Copy {counter})" if counter > 2 else f"{base_name} (Copy)"
                filtered_project_data['name'] = name

                # Create project
                project = Project.objects.create(
                    owner=request.user,
                    export_id=export_id if not force_copy else uuid.uuid4(),
                    **filtered_project_data
                )

                # Lock project and create membership (same as regular create)
                project.lock(request.user)
                ProjectMembership.objects.create(
                    user=request.user,
                    project=project,
                    group=Group.objects.get_or_create(name="Admin")[0]
                )

                # Create activities and modules
                for activity_data in activities_data:
                    activity_data = activity_data.copy()
                    modules_data = activity_data.pop('modules', {})
                    module_types_data = activity_data.pop('module_types', [])

                    # Prepare activity data with proper FK handling
                    filtered_activity_data = prepare_model_data(Activity, activity_data)

                    activity = Activity.objects.create(
                        project=project,
                        owner=request.user,
                        **filtered_activity_data
                    )

                    # Set module types
                    if module_types_data:
                        activity.module_types.set(module_types_data)

                    # Sort so modules referenced via OneToOneField are created
                    # first: OrganicSoil → LandUseChange → everything else.
                    def _module_sort_key(item):
                        priority = {'OrganicSoil': 0, 'LandUseChange': 1}
                        return priority.get(item[0], 2)

                    modules_data = dict(sorted(modules_data.items(), key=_module_sort_key))

                    # Maps old module PK → newly-created instance so that
                    # cross-module OneToOneField refs can be resolved.
                    module_id_map = {}

                    # Cache for author lookups to avoid repeated DB queries
                    author_cache = {}

                    # Create modules
                    for module_type, modules_list in modules_data.items():
                        model_class = self._get_module_class(module_type)
                        if model_class:
                            for module_data in modules_list:
                                module_data = module_data.copy()
                                original_id = module_data.pop('_original_id', None)
                                submodules_data = module_data.pop('_submodules', [])

                                filtered_module_data = prepare_model_data(
                                    model_class, module_data, module_id_map
                                )
                                new_instance = model_class.objects.create(
                                    activity=activity,
                                    **filtered_module_data
                                )

                                if original_id is not None:
                                    module_id_map[original_id] = new_instance

                                # Reconstruct threads with comments for the module
                                _reconstruct_threads(new_instance, module_data, author_cache)

                                # Create submodules if present in the export
                                if submodules_data:
                                    self._create_submodules(
                                        new_instance, submodules_data, prepare_model_data,
                                        _reconstruct_threads, author_cache, module_id_map
                                    )

                return Response({
                    "exists": False,
                    "projectId": project.id,
                    "projectName": project.name
                }, status=http_status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Failed to import project: {str(e)}")
            return utils.ErrorResponse(
                f"Failed to import project: {str(e)}",
                status=http_status.HTTP_400_BAD_REQUEST
            )

    def _get_module_class(self, class_name):
        """Get module model class by name."""
        from . import models
        return getattr(models, class_name, None)

    def _create_submodules(self, parent_instance, submodules_data, prepare_model_data,
                           reconstruct_threads_fn, author_cache, module_id_map):
        """
        Create submodules for a parent module from exported submodule data.

        Args:
            parent_instance: The parent module instance
            submodules_data: List of submodule data dictionaries from export
            prepare_model_data: Function to filter model data
            reconstruct_threads_fn: Function to reconstruct thread comments
            author_cache: Cache for author lookups
            module_id_map: Map of original IDs to new instances
        """
        for submodule_data in submodules_data:
            submodule_data = submodule_data.copy()
            original_id = submodule_data.pop('_original_id', None)
            nested_submodules = submodule_data.pop('_submodules', [])
            submodule_type = submodule_data.pop('_submodule_type', None)

            # Get the submodule class
            submodule_class = None

            # First try to use the stored submodule type from the export
            if submodule_type:
                submodule_class = self._get_module_class(submodule_type)

            # Fallback: try to determine from parent's related models
            if submodule_class is None:
                for field in parent_instance._meta.get_fields():
                    if hasattr(field, 'related_model') and hasattr(field, 'related_query_name'):
                        related_model = field.related_model
                        # Check if this related model has a 'parent' field pointing to our parent class
                        for related_field in related_model._meta.get_fields():
                            if hasattr(related_field, 'column') and related_field.name == 'parent':
                                if hasattr(related_field, 'related_model'):
                                    if related_field.related_model == parent_instance.__class__:
                                        submodule_class = related_model
                                        break
                    if submodule_class:
                        break

            if submodule_class is None:
                logger.warning(f"Could not determine submodule class for {parent_instance.__class__.__name__}")
                continue

            filtered_submodule_data = prepare_model_data(
                submodule_class, submodule_data, module_id_map
            )

            # Create the submodule with parent reference
            new_submodule = submodule_class.objects.create(
                parent=parent_instance,
                **filtered_submodule_data
            )

            if original_id is not None:
                module_id_map[original_id] = new_submodule

            # Reconstruct threads for the submodule
            reconstruct_threads_fn(new_submodule, submodule_data, author_cache)

            # Recursively create nested submodules if present
            if nested_submodules:
                self._create_submodules(
                    new_submodule, nested_submodules, prepare_model_data,
                    reconstruct_threads_fn, author_cache, module_id_map
                )

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
            from .reports import compute_project_result
            from .reports.html_context import build_template_context

            project: Project = self.get_object()

            result = compute_project_result(project)
            context = build_template_context(result, request, lang)
            html = render(request, f"reports/{template_name}_{lang}.html", context).content.decode()

            # Generate PDF from HTML using WeasyPrint
            from weasyprint import HTML

            pdf = HTML(string=html).write_pdf()

            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{template_name}.pdf"'
            return response

        except Exception as e:
            logger.exception(e)
            return utils.ErrorResponse(
                f"Error generating PDF ({type(e).__name__}): {e}",
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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


# The three statuses Activity.status (api/models.py __get_status) can resolve to.
# This is intentionally a subset of the StatusType table (which also holds
# module-level values like SUBMODULES_EMPTY): only these apply at activity level.
ACTIVITY_STATUS_VALUES = {"READY", "IN PROGRESS", "EMPTY"}


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
        manual_parameters=[project_id, activity_status, activity_ready],
        responses={
            400: "activity_id not provided",
            403: "Selected user does not have permission to view activities in the project",
            200: ActivitySerializer(many=True),
        },
    )
    def list(self, request):
        """
        Get all activities for a given project, by filtering against a `project_id` query parameter in the URL.

        Optionally filter by computed activity status:
        - `status`: one or more of `READY`, `IN PROGRESS`, `EMPTY`, given as a comma-separated
          list and/or a repeated parameter (e.g. `status=IN PROGRESS,EMPTY`).
        - `ready`: convenience toggle; `true` returns only READY activities, `false` returns the
          rest (IN PROGRESS and EMPTY). Intersects with `status` when both are given.
        """
        logger.info("ActivityViewSet.list")
        project_id = utils.get_query_param_or_validation_error(self.request, "project_id")
        project = get_object_or_404(Project, pk=project_id)
        is_summary = request.query_params.get("summary", False)
        is_b_intact_param = request.query_params.get("is_b_intact", None)
        SerializerClass = ActivitySerializerWithModules
        if is_summary:
            SerializerClass = ActivitySummarySerializer

        error = security.check_permission("view_activity", self.request.user, project)
        if error:
            return error

        def process_activity(activity):
            activity_dict = SerializerClass(activity).data
            return activity_dict

        # Prefetch module_types in a single query: both the optional status
        # filter below and activity serialization walk each activity's modules,
        # so this trims the per-activity relation fetch. It mitigates but does
        # not remove the N+1 in Activity.status (the per-subclass module queries
        # and StatusType lookups remain); a full fix is the persisted-status TODO.
        activities_list = Activity.objects.filter(project__id=project_id).prefetch_related("module_types")
        if is_b_intact_param is not None:
            activities_list = activities_list.filter(is_b_intact=is_b_intact_param == "true")

        # `status` is a computed property derived from module statuses
        # (Activity.__get_status), not a DB column, so it cannot be filtered in
        # SQL. Re-derive it in Python from the same property the endpoint already
        # serializes, so the filter can never diverge from the reported status.
        # Filtering here materializes the queryset before pagination, which is
        # fine at per-project activity counts; the unfiltered path stays lazy.
        #
        # Two query params narrow the status, both resolved to a set of allowed
        # StatusType names:
        #   - `status`: explicit values, as a comma-separated list and/or a
        #     repeated param (e.g. ?status=IN PROGRESS,EMPTY).
        #   - `ready`: convenience toggle; true -> {READY}, false -> the
        #     complement {IN PROGRESS, EMPTY}.
        # When both are given they intersect (AND); a contradictory pair (e.g.
        # ?ready=true&status=EMPTY) yields an empty result, which is correct.
        allowed_statuses = None  # None means "no status constraint"

        requested_statuses = {
            value.strip().upper().replace("_", " ")
            for raw in request.query_params.getlist("status")
            for value in raw.split(",")
            if value.strip()
        }
        if requested_statuses:
            invalid_statuses = requested_statuses - ACTIVITY_STATUS_VALUES
            if invalid_statuses:
                raise ValidationError(f"Invalid status value(s): {', '.join(sorted(invalid_statuses))}. Allowed values: {', '.join(sorted(ACTIVITY_STATUS_VALUES))}")
            allowed_statuses = requested_statuses

        ready_param = request.query_params.get("ready", None)
        if ready_param is not None:
            normalized_ready = ready_param.strip().lower()
            if normalized_ready not in ("true", "false"):
                raise ValidationError(f"Invalid ready value '{ready_param}'. Allowed values: true, false")
            ready_statuses = {"READY"} if normalized_ready == "true" else ACTIVITY_STATUS_VALUES - {"READY"}
            allowed_statuses = ready_statuses if allowed_statuses is None else allowed_statuses & ready_statuses

        if allowed_statuses is not None:
            activities_list = [activity for activity in activities_list if activity.status.name_en in allowed_statuses]

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
