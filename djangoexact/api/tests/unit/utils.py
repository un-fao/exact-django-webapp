from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework import status
from django.urls import reverse
from api.views import ProjectViewSet, ActivityViewSet, generic_module_viewset, ProjectMembershipViewSet, ProjectInvitationViewSet, ProjectFileAttachmentViewSet, CommentViewSet
import api.models as models
import ipcc.models as ipcc_models
import api.tests.factories as factories
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyText, FuzzyInteger, FuzzyChoice
import logging as log
from api import serializers
import io
from django.core.files.uploadedfile import SimpleUploadedFile

import public.views as public_views


class APITestCaseMixin(APITestCase):
    def setUp(self):
        """
        Set up the test environment for the project lock tests.

        This method initializes the following attributes:
        - self.user: A CustomUser instance with the email "claudio.lavacca@fao.org".
        - self.user2: A CustomUser instance with the email "test@user.org".
        - self.group: A Group instance with the name "Second Reviewer".
        - self.country: A randomly selected Country instance.
        - self.climate: A randomly selected Climate instance.
        - self.moisture: A randomly selected Moisture instance associated with the selected Climate.
        - self.soil_type: A randomly selected SoilType instance.
        - self.project_data: A dictionary containing project data with the following keys:
            - "name": A randomly generated string.
            - "start_year_of_activities": The year 2024.
            - "implementation_years": The number 10.
            - "last_year_of_accounting": The year 2040.
            - "country": The ID of the selected Country instance.
            - "climate": The ID of the selected Climate instance.
            - "moisture": The ID of the selected Moisture instance.
            - "soil_type": The ID of the selected SoilType instance.
            - "gw_potential": The ID of a randomly selected GlobalWarmingPotential instance.
        """
        log.getLogger().setLevel(log.INFO)
        log.info("Setting up ProjectLockTestCase")
        self.request_factory = APIRequestFactory(enforce_csrf_checks=False)
        self.user = models.CustomUser.objects.get(email="claudio.lavacca@fao.org")
        self.user2 = models.CustomUser.objects.get(email="test@user.org")
        self.group = models.Group.objects.get(name="Second Reviewer")
        self.country = models.Country.objects.order_by("?").first()
        self.climate = models.Climate.objects.order_by("?").first()
        self.moisture = self.climate.moistures.order_by("?").first()
        self.soil_type = models.SoilType.objects.filter(active=True).order_by("?").first()
        self.module_type = models.ModuleType.objects.filter(is_luc=True).order_by("?").first()
        self.change_rate = models.ChangeRate.objects.get(name="linear")
        self.project_data = {
            "name": FuzzyText().fuzz(),
            "start_year_of_activities": 2024,
            "implementation_years": 10,
            "last_year_of_accounting": 2040,
            "country": self.country.id,
            "climate": self.climate.id,
            "moisture": self.moisture.id,
            "soil_type": self.soil_type.id,
            "gw_potential": ipcc_models.GlobalWarmingPotential.objects.order_by("?").first().id,
            "soc_ref_t2": FuzzyInteger(0, 100).fuzz(),
        }

    def create_project(self):
        """
        Create a project using the ProjectViewSet.

        This method creates a project by sending a POST request to the 'project-list' endpoint
        with the provided project data in JSON format. The request is authenticated with the test user,
        and the response is returned.
        """
        log.info("Creating project")
        factory = APIRequestFactory(enforce_csrf_checks=False)
        view = ProjectViewSet.as_view({"post": "create"})

        request = self.request_factory.post(
            reverse("project-list"),
            self.project_data,
            format="json",
        )
        force_authenticate(request, user=self.user)
        return view(request)

    def send_project_invitation(self, project, user, group):
        """
        Send a project invitation using the ProjectViewSet.

        This method sends a project invitation by sending a POST request to the 'project-invite' endpoint
        with the provided project data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Sending project invitation")
        view = ProjectInvitationViewSet.as_view({"post": "create"})
        request = self.request_factory.post(
            reverse("projectinvitation-list"),
            {"email": user.email, "project": project.id, "group": group.id},
            format="json",
        )
        force_authenticate(request, user=self.user)
        return view(request)

    def create_project_membership(self, project, user, group=None):
        """
        Create a project membership for a user.

        This method creates a project membership for the provided user and project.
        """
        log.info("Creating project membership")

        if group is None:
            group = self.group

        view = ProjectMembershipViewSet.as_view({"post": "create"})
        request = self.request_factory.post(
            reverse("projectmembership-list"),
            {"user": user.id, "project": project.id, "group": group.id},
            format="json",
        )
        force_authenticate(request, user=self.user)
        return view(request)
    
    def get_project_memberships(self, project):
        """
        Get project memberships for a project.
        """
        log.info("Getting project memberships")
        view = ProjectViewSet.as_view({"get": "memberships"})
        request = self.request_factory.get(reverse("project-list"), format="json")
        force_authenticate(request, user=self.user)
        return view(request, pk=project.id)
    
    def get_project_memberships_filter_by_user(self, project):
        """
        Get project memberships for a project, filtered by user.
        """
        log.info("Getting project memberships filtered by user")
        view = ProjectViewSet.as_view({"get": "memberships"})
        request = self.request_factory.get(
            reverse("project-list"),
            {"user": self.user.id},
            format="json"
        )
        force_authenticate(request, user=self.user)
        return view(request, pk=project.id)

    def edit_project(self, project, user, data):
        """
        Edit a project using the ProjectViewSet.

        This method edits a project by sending a PATCH request to the 'project-detail' endpoint
        with the provided project data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Editing project")
        view = ProjectViewSet.as_view({"patch": "partial_update"})

        request = self.request_factory.patch(
            reverse("project-detail", args=[project.id]),
            data,
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=project.id)

    def upload_project_file(self, project, user, file=None):
        """
        Upload a project file using the ProjectViewSet.

        This method uploads a project file by sending a POST request to the 'project-upload' endpoint
        with the provided file data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Uploading project file")
        view = ProjectFileAttachmentViewSet.as_view({"post": "create"})

        if file is None:
            sample_content = b"Sample file content for testing."
            file = SimpleUploadedFile("testfile.txt", sample_content, content_type="text/plain")

        request = self.request_factory.post(
            reverse("projectattachment-list"),
            {"file": file, "project": project.id},
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request)

    def create_activity(self, project, user, module_types=None):
        """
        Create an activity using the ActivityViewSet.

        This method creates an activity by sending a POST request to the 'activity-build' endpoint
        with the provided activity data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Creating activity")

        activity_builder_data = {
            "name": FuzzyText().fuzz(),
            "project": project.id,
            "module_types": [self.module_type.id] if module_types is None else [module_type.id for module_type in module_types],
            "area": 100,
            "change_rate": self.change_rate.id,
            "cost": 0,
        }

        view = ActivityViewSet.as_view({"post": "build"})
        request = self.request_factory.post(
            reverse("activities-list"),
            activity_builder_data,
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request)

    def edit_activity(self, activity, user, data):
        """
        Edit an activity using the ActivityViewSet.

        This method edits an activity by sending a PATCH request to the 'activity-detail' endpoint
        with the provided activity data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Editing activity")
        view = ActivityViewSet.as_view({"patch": "partial_update"})

        request = self.request_factory.patch(
            reverse("activities-detail", args=[activity.id]),
            data,
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=activity.id)

    def copy_activity(self, activity, user):
        """
        Copy an activity using the ActivityViewSet.

        This method copies an activity by sending a POST request to the 'activity-copy' endpoint
        with the provided activity ID. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Copying activity")
        view = ActivityViewSet.as_view({"post": "copy"})

        request = self.request_factory.post(
            reverse("activities-copy", args=[activity.id]),
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=activity.id)

    def delete_activity(self, activity, user):
        """
        Delete an activity using the ActivityViewSet.

        This method deletes an activity by sending a DELETE request to the 'activity-detail' endpoint
        with the provided activity ID. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Deleting activity")
        view = ActivityViewSet.as_view({"delete": "destroy"})

        request = self.request_factory.delete(
            reverse("activities-detail", args=[activity.id]),
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=activity.id)

    def edit_module(self, module, user, data):
        """
        Edit a module using the ModuleViewSet.

        This method edits a module by sending a PATCH request to the 'module-detail' endpoint
        with the provided module data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.debug(f"Editing module: {module.__class__.__name__}")
        log.debug(f"Data: {data}")
        view = generic_module_viewset(module.__class__).as_view({"patch": "partial_update"})
        # Get viewset url name
        request = self.request_factory.patch(
            reverse(f"{module.__class__.__name__.lower()}-detail", args=[module.pk]),
            data,
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=module.pk)

    def create_submodule(self, SubmoduleClass, user, data):
        """
        Create a submodule using the ModuleViewSet.

        This method creates a submodule by sending a POST request to the 'module-list' endpoint
        with the provided submodule data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info(f"Creating submodule with data: {data}")
        view = generic_module_viewset(SubmoduleClass).as_view({"post": "create"})
        request = self.request_factory.post(
            reverse(f"{SubmoduleClass.__name__.lower()}-list"),
            data,
            format="json",
        )
        force_authenticate(request, user=user)
        response = view(request)
        return response

    def get_module_defaults(self, module, user):
        """
        Get module defaults using the ModuleViewSet.

        This method retrieves module defaults by sending a GET request to the 'module-defaults' endpoint
        with the provided module ID. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Getting module defaults")
        view = generic_module_viewset(module.__class__).as_view({"get": "defaults"})
        request = self.request_factory.get(
            reverse(f"{module.__class__.__name__.lower()}-defaults", args=[module.pk]),
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=module.pk)

    def calculate_project_results(self, project, user):
        """
        Calculate project results using the ProjectViewSet.

        This method calculates project results by sending a POST request to the 'project-calculate' endpoint
        with the provided project ID. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Calculating project results")
        view = ProjectViewSet.as_view({"get": "results"})
        request = self.request_factory.get(
            reverse("results", args=[project.id]),
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=project.id)

    def calculate_activity_results(self, activity, user):
        """
        Calculate activity results using the ActivityViewSet.

        This method calculates activity results by sending a POST request to the 'activity-calculate' endpoint
        with the provided activity ID. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Calculating activity results")
        view = ActivityViewSet.as_view({"get": "results"})
        request = self.request_factory.get(
            reverse("activities-results", args=[activity.id]),
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=activity.id)

    def calculate_activity_results_anonimously(self, activity):
        """
        Calculate activity results without authentication.
        This method calculates activity results by sending a GET request to the 'activity-results' endpoint
        with the provided activity ID. The request is not authenticated, and the response is returned.
        """
        log.info("Calculating activity results without authentication")
        view = public_views.PublicActivityViewSet.as_view({"get": "results"})
        request = self.request_factory.get(
            reverse("activity-results", args=[activity.id]),
            format="json",
        )
        return view(request, pk=activity.id)

    def get_activity_anonimously(self, activity):
        """
        Get activity data without authentication.
        This method retrieves activity data by sending a GET request to the 'activity-detail' endpoint
        with the provided activity ID. The request is not authenticated, and the response is returned.
        """
        log.info("Getting activity data without authentication")
        view = public_views.PublicActivityViewSet.as_view({"get": "retrieve"})
        request = self.request_factory.get(
            reverse("activity-detail", args=[activity.id]),
            format="json",
        )
        return view(request, pk=activity.id)

    def get_report_anonimously(self, project, templated=False):
        """
        Get project report data without authentication.
        This method retrieves project report data by sending a GET request to the 'project-report' endpoint
        with the provided project ID. The request is not authenticated, and the response is returned.
        """
        log.info("Getting project report data without authentication")
        view = public_views.PublicProjectViewSet.as_view({"get": "report"})
        queryparams = None
        if templated:
            queryparams = {"template": "fao"}
        request = self.request_factory.get(
            reverse("project-detail", args=[project.id]),
            queryparams,
            format="json",
        )
        return view(request, pk=project.id)

    def get_activities_anonimously(self, project):
        """
        Get activities data without authentication.
        This method retrieves activities data by sending a GET request to the 'activities-list' endpoint
        with the provided project ID. The request is not authenticated, and the response is returned.
        """
        log.info("Getting activities data without authentication")
        view = public_views.PublicProjectViewSet.as_view({"get": "activities"})
        request = self.request_factory.get(
            reverse("project-detail", args=[project.pk]),
            format="json",
        )
        return view(request, pk=project.pk)
    
    def add_comment(self, thread: models.CommentThread, text: str):
        """
        Add a comment to a module using the ModuleViewSet.

        This method adds a comment to a module by sending a POST request to the 'module-comment' endpoint
        with the provided module data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Adding comment to module")

        view = CommentViewSet.as_view({"post": "create"})
        request = self.request_factory.post(
            reverse("comments-list"),
            {"thread": thread.id, "content": text},
            format="json",
        )
        force_authenticate(request, user=self.user)
        return view(request)