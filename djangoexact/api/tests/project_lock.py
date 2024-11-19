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
        factory = APIRequestFactory(enforce_csrf_checks=False)
        view = ProjectViewSet.as_view({"post": "create"})

        # force authentication
        request = factory.post(
            reverse("project-list"),
            self.project_data,
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_modify_project_as_not_lock_holder(self):
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
