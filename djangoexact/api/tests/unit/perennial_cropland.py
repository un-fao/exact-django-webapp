from rest_framework import status
from django.urls import reverse
import api.models as models
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyChoice
import copy
from . import base_module
import logging
logging.getLogger().setLevel(logging.CRITICAL)
logging.getLogger('matplotlib').setLevel(logging.CRITICAL)
logging.getLogger('django').setLevel(logging.CRITICAL)

class PerennialCroplandTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.PerennialCropland
        super().setUp()

        self.trees = models.LandUseType.objects.filter(module_types__class_name="PerennialCropland", climates=self.project.climate, moistures=self.project.moisture, is_active=True)


        self.validated_data = self.build_validated_data()

        self.edit_module(self.module, self.user, self.validated_data)
        self.module.refresh_from_db()

        self.test_modify(retry=True)

    def build_validated_data(self):
        tree = self.trees.order_by("?").first()
        return {
            "land_use_type_start": tree.id,
            "land_use_type_w": tree.id,
            "land_use_type_wo": tree.id,
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

    def test_modify(self, retry=False):
        self.validated_data = self.build_validated_data()
        response = self.edit_module(self.module, self.user, self.validated_data)
        self.module.refresh_from_db()
        if retry:
            workable = False
            while not workable:
                try:
                    self.test_calculate_results()
                    workable = True
                except Exception as e:
                    self.validated_data = self.build_validated_data()
                    self.edit_module(self.module, self.user, self.validated_data)
                    self.module.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_modify_and_check_cache_invalidation(self):
        self.test_modify(retry=True)

        # Check that the cache is invalidated
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

        old_balance = response.data["balance"]

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["land_use_type_w"] = self.trees.exclude(id=self.validated_data["land_use_type_start"]).order_by("?").first().id
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

        self.assertNotEqual(old_balance, new_balance)

    def test_patch_to_not_ready(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["land_use_type_start"] = None
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

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
        self.assertTrue(type(response.data) == dict)  # noqa: E721

    def calculate_module_results(self):
        """Helper method to get results for a module"""
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_maturity_system_change_affects_results(self):

        module_details = self.get_module_details(self.module, self.user)

        validated_data = copy.deepcopy(module_details.data)
        validated_data["is_system_in_maturity"] = False
        validated_data["land_use_type_w"] = self.trees.exclude(id=self.validated_data["land_use_type_start"]).order_by("?").first().id

        print(f"land_use_type_start: {validated_data['land_use_type_start']}")
        print(f"land_use_type_w: {validated_data['land_use_type_w']}")
        print(f"land_use_type_wo: {validated_data['land_use_type_wo']}")
        print(f"is_system_in_maturity: {validated_data['is_system_in_maturity']}")
        print(f"is_complete_renewal_start: {validated_data['is_complete_renewal_start']}")
        print(f"is_complete_renewal_w: {validated_data['is_complete_renewal_w']}")
        print(f"is_complete_renewal_wo: {validated_data['is_complete_renewal_wo']}")

        response = self.edit_module(self.module, self.user, validated_data, put=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        non_mature_results = self.calculate_module_results()["balance"]

        validated_data = copy.deepcopy(module_details.data)
        validated_data["is_system_in_maturity"] = True

        response = self.edit_module(self.module, self.user, validated_data, put=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        mature_results = self.calculate_module_results()["balance"]
        self.assertNotEqual(non_mature_results, mature_results)
