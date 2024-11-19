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


class ProjectLockTestCase(APITestCase):

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
        self.user = models.CustomUser.objects.get(email="claudio.lavacca@fao.org")
        self.user2 = models.CustomUser.objects.get(email="test@user.org")
        self.group = models.Group.objects.get(name="Second Reviewer")
        self.country = models.Country.objects.order_by("?").first()
        self.climate = models.Climate.objects.order_by("?").first()
        self.moisture = self.climate.moistures.order_by("?").first()
        self.soil_type = models.SoilType.objects.order_by("?").first()
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

        request = factory.post(
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

        request = factory.patch(
            reverse("project-detail", args=[project.id]),
            data,
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=project.id)

    def create_activity(self, project, user):
        """
        Create an activity using the ActivityViewSet.

        This method creates an activity by sending a POST request to the 'activity-build' endpoint
        with the provided activity data in JSON format. The request is authenticated with the provided user,
        and the response is returned.
        """
        log.info("Creating activity")
        module_type = models.ModuleType.objects.get(class_name="PerennialCropland")
        change_rate = models.ChangeRate.objects.get(name="linear")

        activity_builder_data = {
            "name": FuzzyText().fuzz(),
            "project": project.id,
            "module_types": [module_type.id],
            "area": 100,
            "change_rate": change_rate.id,
            "cost": 0,
        }

        factory = APIRequestFactory(enforce_csrf_checks=False)
        view = ActivityViewSet.as_view({"post": "build"})
        request = factory.post(
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
        factory = APIRequestFactory(enforce_csrf_checks=False)
        view = ActivityViewSet.as_view({"patch": "partial_update"})

        request = factory.patch(
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
        factory = APIRequestFactory(enforce_csrf_checks=False)
        view = generic_module_viewset(module.__class__).as_view({"patch": "partial_update"})
        # Get viewset url name
        request = factory.patch(
            reverse("perennial-croplands-detail", args=[module.id]),
            data,
            format="json",
        )
        force_authenticate(request, user=user)
        return view(request, pk=module.id)

    def test_create_project(self):
        """
        Test the creation of a project using the ProjectViewSet.

        This test uses the APIRequestFactory to create a POST request to the
        'project-list' endpoint with the provided project data in JSON format.
        The request is authenticated with a test user, and the response is
        checked to ensure that the project is created successfully with a
        status code of 201 (Created).
        """
        response = self.create_project()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_modify_project_as_not_lock_holder(self):
        """
        Test that a user who is not the lock holder of a project cannot modify the project.

        This test performs the following steps:
        1. Creates a project using the `ProjectViewSet` and verifies that the project is created successfully.
        2. Retrieves the created project from the database.
        3. Creates a project membership for a second user (`self.user2`) who is not the lock holder.
        4. Attempts to modify the project using the second user and verifies that the modification is not allowed,
           expecting a `HTTP_400_BAD_REQUEST` status code.

        Assertions:
        - The project creation response status code is `HTTP_201_CREATED`.
        - The project modification response status code is `HTTP_400_BAD_REQUEST`.
        """

        create_response = self.create_project()
        project = models.Project.objects.get(id=create_response.data["id"])
        self.create_project_membership(project, self.user2)
        modify_response = self.edit_project(project, self.user2, {"name": "New Name"})
        self.assertEqual(modify_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modify_project_as_lock_holder(self):
        """
        Test that a project lock holder can modify the project.

        This test performs the following steps:
        1. Creates a project using the ProjectViewSet's create action.
        2. Authenticates the request with a user.
        3. Verifies that the project is created successfully with a 201 status code.
        4. Retrieves the created project from the database.
        5. Modifies the project's name using the ProjectViewSet's partial_update action.
        6. Authenticates the modification request with the same user.
        7. Verifies that the project is modified successfully with a 200 status code.
        8. Confirms that the project's name has been updated to "New Name".
        """

        create_response = self.create_project()

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        project = models.Project.objects.get(id=create_response.data["id"])
        modify_response = self.edit_project(project, self.user, {"name": "New Name"})

        self.assertEqual(modify_response.status_code, status.HTTP_200_OK)
        self.assertEqual(modify_response.data["name"], "New Name")

    def test_modify_actvity_as_not_lock_holder(self):
        """
        Test that a user who is not the lock holder of an activity cannot modify it.

        Steps:
        1. Create a project.
        2. Verify the project creation response status is HTTP 201 Created.
        3. Retrieve the created project from the database.
        4. Create a project membership for a second user.
        5. Create an activity within the project by the first user.
        6. Verify the activity creation response status is HTTP 200 OK.
        7. Retrieve the created activity from the database.
        8. Attempt to modify the activity by the second user.
        9. Verify the modification response status is HTTP 400 Bad Request.
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])
        self.create_project_membership(project, self.user2)

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        modify_activity_response = self.edit_activity(activity, self.user2, {"name": "New Name"})
        self.assertEqual(modify_activity_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modify_activity_as_lock_holder(self):
        """
        Test modifying an activity as the lock holder.

        This test performs the following steps:
        1. Creates a project and verifies the response status code is 201 (Created).
        2. Retrieves the created project from the database.
        3. Creates an activity within the project and verifies the response status code is 200 (OK).
        4. Retrieves the created activity from the database.
        5. Modifies the activity's name and verifies the response status code is 200 (OK).
        6. Confirms that the activity's name has been updated to the new value.

        Assertions:
        - The project creation response status code is 201.
        - The activity creation response status code is 200.
        - The activity modification response status code is 200.
        - The activity's name is updated to "New Name".
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        modify_activity_response = self.edit_activity(activity, self.user, {"name": "New Name"})
        self.assertEqual(modify_activity_response.status_code, status.HTTP_200_OK)
        self.assertEqual(modify_activity_response.data["name"], "New Name")

    def test_modify_module_as_not_lock_holder(self):
        """
        Test that a user who is not the lock holder of a module cannot modify it.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Adds a second user as a member of the project.
        3. Creates an activity within the project and verifies the activity creation.
        4. Attempts to modify a module within the activity using the second user.
        5. Verifies that the modification attempt fails with a 400 Bad Request status code.

        The test ensures that only the lock holder of a module can modify it.
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])
        self.create_project_membership(project, self.user2)

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        module = activity.modules[0]

        response = self.edit_module(module, self.user2, {"area": 50})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modify_module_as_lock_holder(self):
        """
        Test modifying a module as the lock holder.
        This test case verifies that a user who holds the lock on a project can successfully modify a module within that project.
        Steps:
        1. Create a project and verify the response status is HTTP 201 Created.
        2. Retrieve the created project from the database.
        3. Create an activity within the project and verify the response status is HTTP 200 OK.
        4. Retrieve the created activity from the database.
        5. Select the first module from the activity.
        6. Attempt to edit the module's area attribute as the lock holder and verify the response status is HTTP 200 OK.
        7. Verify that the module's area attribute has been updated to the new value.
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        module = activity.modules[0]

        response = self.edit_module(module, self.user, {"area": 50})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["area"], 50)
