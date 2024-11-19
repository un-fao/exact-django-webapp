from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework import status
from django.urls import reverse
from api.views import ProjectViewSet
import api.models as models
import ipcc.models as ipcc_models
import api.tests.factories as factories
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyText, FuzzyInteger, FuzzyChoice


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

    def test_create_project(self):
        """
        Test the creation of a project using the ProjectViewSet.

        This test uses the APIRequestFactory to create a POST request to the
        'project-list' endpoint with the provided project data in JSON format.
        The request is authenticated with a test user, and the response is
        checked to ensure that the project is created successfully with a
        status code of 201 (Created).
        """
        factory = APIRequestFactory(enforce_csrf_checks=False)
        view = ProjectViewSet.as_view({"post": "create"})

        request = factory.post(
            reverse("project-list"),
            self.project_data,
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = view(request)
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
        factory = APIRequestFactory(enforce_csrf_checks=False)
        create_view = ProjectViewSet.as_view({"post": "create"})

        create_request = factory.post(
            reverse("project-list"),
            self.project_data,
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = create_view(create_request)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        project = models.Project.objects.get(id=create_response.data["id"])

        modify_view = ProjectViewSet.as_view({"patch": "partial_update"})
        models.ProjectMembership.objects.create(user=self.user2, project=project, group=self.group)

        modify_request = factory.patch(reverse("project-detail", args=[project.id]), {"name": "New Name"}, format="json")
        force_authenticate(modify_request, user=self.user2)
        modify_response = modify_view(modify_request, pk=project.id)
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
        factory = APIRequestFactory(enforce_csrf_checks=False)
        create_view = ProjectViewSet.as_view({"post": "create"})

        create_request = factory.post(
            reverse("project-list"),
            self.project_data,
            format="json",
        )

        force_authenticate(create_request, user=self.user)
        create_response = create_view(create_request)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        project = models.Project.objects.get(id=create_response.data["id"])

        modify_view = ProjectViewSet.as_view({"patch": "partial_update"})
        modify_request = factory.patch(reverse("project-detail", args=[project.id]), {"name": "New Name"}, format="json")
        force_authenticate(modify_request, user=self.user)
        modify_response = modify_view(modify_request, pk=project.id)
        self.assertEqual(modify_response.status_code, status.HTTP_200_OK)
        self.assertEqual(modify_response.data["name"], "New Name")
