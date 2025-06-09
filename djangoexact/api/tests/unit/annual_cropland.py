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
import copy
from . import base_module


class AnnualCroplandTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.AnnualCropland
        super().setUp()

        self.land_use_types = self.land_use_types.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)
        self.validated_data = {
            "land_use_type_start": self.land_use_types.order_by("?").first().id,
            "land_use_type_w": self.land_use_types.order_by("?").first().id,
            "land_use_type_wo": self.land_use_types.order_by("?").first().id,
            "tillage_management_type_start": models.TillageManagementType.objects.order_by("?").first().id,
            "tillage_management_type_w": models.TillageManagementType.objects.order_by("?").first().id,
            "tillage_management_type_wo": models.TillageManagementType.objects.order_by("?").first().id,
            "organic_input_type_start": models.OrganicInputType.objects.order_by("?").first().id,
            "organic_input_type_w": models.OrganicInputType.objects.order_by("?").first().id,
            "organic_input_type_wo": models.OrganicInputType.objects.order_by("?").first().id,
            "residue_management_type_start": models.ResidueManagementType.objects.order_by("?").first().id,
            "residue_management_type_w": models.ResidueManagementType.objects.order_by("?").first().id,
            "residue_management_type_wo": models.ResidueManagementType.objects.order_by("?").first().id,
        }

        self.edit_module(self.module, self.user, self.validated_data)
        self.module.refresh_from_db()

    def test_modify_and_check_cache_invalidation(self):
        # Check that the cache is invalidated
        response = self.get_results()
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

        old_balance = response.data["balance"]

        is_modification_valid = False

        while not is_modification_valid:
            try:
                validated_data = copy.deepcopy(self.validated_data)
                validated_data["land_use_type_w"] = models.LandUseType.objects.order_by("?").exclude(id=validated_data["land_use_type_w"]).first().id
                response = self.edit_module(self.module, self.user, validated_data)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["status"]["name"], "READY")

                # Check that the cache is invalidated
                view = self.module_viewset.as_view({"get": "results"})
                request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

                force_authenticate(request, user=self.user)
                response = view(request, pk=self.module.pk)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertTrue("balance" in response.data)

                new_balance = response.data["balance"]
                is_modification_valid = True
            except Exception as e:
                pass

        self.assertNotEqual(old_balance, new_balance)

    def test_modify(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["land_use_type_start"] = models.LandUseType.objects.order_by("?").first().id
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_patch_to_not_ready(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["land_use_type_start"] = None
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

    def test_add_minor_season_and_calculate_results(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data.update(
            {
                "minor_land_use_type_start": self.land_use_types.order_by("?").first().id,
                "minor_land_use_type_w": self.land_use_types.order_by("?").first().id,
                "minor_land_use_type_wo": self.land_use_types.order_by("?").first().id,
                "minor_residue_management_type_start": models.ResidueManagementType.objects.order_by("?").first().id,
                "minor_residue_management_type_w": models.ResidueManagementType.objects.order_by("?").first().id,
                "minor_residue_management_type_wo": models.ResidueManagementType.objects.order_by("?").first().id,
            }
        )
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

    def test_calculate_results(self):

        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

    def test_get_defaults(self):

        view = self.module_viewset.as_view({"get": "defaults"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-defaults", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(type(response.data) == dict)

    def test_add_comment_and_copy_project(self):

        thread = self.module.tillage_management_type_thread
        response = self.add_comment(thread, "test comment")
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.copy_activity(self.activity, self.user)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
