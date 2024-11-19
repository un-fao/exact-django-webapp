from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework import status
from django.urls import reverse
from api.views import ProjectViewSet, ActivityViewSet, generic_module_viewset
import api.models as models
import ipcc.models as ipcc_models
import api.tests.factories as factories
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyText, FuzzyInteger, FuzzyChoice
import logging as log


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
        self.soil_type = models.SoilType.objects.order_by("?").first()
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

    def create_project_membership(self, project, user):
        """
        Create a project membership for a user.

        This method creates a project membership for the provided user and project.
        """
        log.info("Creating project membership")
        return models.ProjectMembership.objects.create(user=user, project=project, group=self.group)

    def edit_project(self, project, user, data):
        """
        Edit a project using the ProjectViewSet.

        This method edits a project by sending a PATCH request to the 'project-detail' endpoint
        with the provided project data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Editing project")
        factory = APIRequestFactory(enforce_csrf_checks=False)
        view = ProjectViewSet.as_view({"patch": "partial_update"})

        request = self.request_factory.patch(
            reverse("project-detail", args=[project.id]),
            data,
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=project.id)

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
            "module_types": [self.module_type.id] if module_types is None else module_types,
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

    def edit_module(self, module, user, data):
        """
        Edit a module using the ModuleViewSet.

        This method edits a module by sending a PATCH request to the 'module-detail' endpoint
        with the provided module data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Editing module")
        view = generic_module_viewset(module.__class__).as_view({"patch": "partial_update"})
        # Get viewset url name
        request = self.request_factory.patch(
            reverse(f"{module.__class__.__name__.lower()}-detail", args=[module.id]),
            data,
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=module.id)

    def create_submodule(self, SubmoduleClass, user, data):
        """
        Create a submodule using the ModuleViewSet.

        This method creates a submodule by sending a POST request to the 'module-list' endpoint
        with the provided submodule data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Creating submodule")
        view = generic_module_viewset(SubmoduleClass).as_view({"post": "create"})
        request = self.request_factory.post(
            reverse(f"{SubmoduleClass.__name__.lower()}-list"),
            data,
            format="json",
        )
        force_authenticate(request, user=user)
        response = view(request)
        return response
