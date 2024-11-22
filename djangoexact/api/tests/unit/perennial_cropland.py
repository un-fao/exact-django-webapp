from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework import status
from django.urls import reverse
from api.views import generic_module_viewset
import api.models as models
import ipcc.models as ipcc_models
import api.tests.factories as factories
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyText, FuzzyInteger, FuzzyChoice
import logging as log
from api.tests.unit.utils import APITestCaseMixin
from api import serializers


class PerennialCroplandTestCase(APITestCaseMixin):

    def setUp(self):
        super().setUp()

        project_response = self.create_project()
        self.assertEqual(project_response.status_code, status.HTTP_201_CREATED)

        self.project = models.Project.objects.get(id=project_response.data["id"])
        self.perennial_cropland_module_type = models.ModuleType.objects.get(class_name="PerennialCropland")

        activity_response = self.create_activity(self.project, self.user, [self.perennial_cropland_module_type])
        self.assertEqual(activity_response.status_code, status.HTTP_200_OK)

        self.activity = models.Activity.objects.get(id=activity_response.data["id"])
        self.module: models.Module = self.activity.perennialcropland.first()

        self.validated_data = self.get_valid_module_data()
        self.edit_module(self.module, self.user, self.validated_data)
        self.module.refresh_from_db()

        self.module_viewset = generic_module_viewset(models.PerennialCropland)

    def get_valid_module_data(self):
        trees = models.LandUseType.objects.filter(module_types__class_name="PerennialCropland", climates__id=self.project.climate.id, moistures__id=self.project.moisture.id, is_active=True)
        data = {
            "land_use_type_start": trees.order_by("?").first().id,
            "land_use_type_w": trees.order_by("?").first().id,
            "land_use_type_wo": trees.order_by("?").first().id,
            "tillage_management_type_start": models.TillageManagementType.objects.order_by("?").first().id,
            "tillage_management_type_w": models.TillageManagementType.objects.order_by("?").first().id,
            "tillage_management_type_wo": models.TillageManagementType.objects.order_by("?").first().id,
            "organic_input_type_start": models.OrganicInputType.objects.order_by("?").first().id,
            "organic_input_type_w": models.OrganicInputType.objects.order_by("?").first().id,
            "organic_input_type_wo": models.OrganicInputType.objects.order_by("?").first().id,
            "is_biomass_burned_start": FuzzyChoice([True, False]).fuzz(),
            "is_biomass_burned_w": FuzzyChoice([True, False]).fuzz(),
            "is_biomass_burned_wo": FuzzyChoice([True, False]).fuzz(),
        }
        return data

    def test_modify_perennial_cropland(self):

        validated_data = self.get_valid_module_data()
        print(validated_data)
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_patch_perennial_cropland_to_not_ready(self):

        validated_data = self.get_valid_module_data()
        validated_data["land_use_type_start"] = None
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

    def test_calculate_perennial_cropland_results(self):

        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse("perennialcropland-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

    def test_get_perennial_cropland_defaults(self):

        view = self.module_viewset.as_view({"get": "defaults"})
        request = self.request_factory.get(reverse("perennialcropland-defaults", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print(response.data)
        self.assertTrue(type(response.data) == dict)
