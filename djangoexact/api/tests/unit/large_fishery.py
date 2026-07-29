from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework import status
from django.urls import reverse
from api.views import generic_module_viewset
import api.models as models
import ipcc.models as ipcc_models
import api.tests.factories as factories
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyText, FuzzyInteger, FuzzyChoice, FuzzyFloat
import logging as log
from api.tests.unit.utils import APITestCaseMixin
from api import serializers
import copy
from . import base_module


class LargeFisheryTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.LargeFishery
        super().setUp()

        self.land_use_types = self.land_use_types.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)

        self.validated_data = {
            "gear_type_start": models.LargeFisheryGearType.objects.order_by("?").first().id,
            "gear_type_w": models.LargeFisheryGearType.objects.order_by("?").first().id,
            "gear_type_wo": models.LargeFisheryGearType.objects.order_by("?").first().id,
            "total_catch_yr_start": FuzzyInteger(1, 100).fuzz(),
            "total_catch_yr_w": FuzzyInteger(1, 100).fuzz(),
            "total_catch_yr_wo": FuzzyInteger(1, 100).fuzz(),
            "fish_type": models.FishType.objects.order_by("?").first().id,
        }

        self.edit_module(self.module, self.user, self.validated_data)
        self.module.refresh_from_db()

    def test_modify(self):
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["fish_type"] = models.FishType.objects.order_by("?").first().id
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_modify_and_check_cache_invalidation(self):
        self.module.refresh_from_db()

        second_to_last_modified = self.module.last_modified

        self.test_modify()
        self.module.refresh_from_db()

        self.assertNotEqual(second_to_last_modified, self.module.last_modified)

    def test_patch_to_not_ready(self):
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["fish_type"] = None
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
        self.assertTrue(type(response.data) is dict)

    def test_presence_of_fui_t2_in_defaults(self):
        response = self.get_module_defaults(self.module, self.user)
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("fui_t2_start_default", response.data)
        self.assertIn("fui_t2_w_default", response.data)
        self.assertIn("fui_t2_wo_default", response.data)

    def test_presence_of_electricity_emission_default_in_defaults(self):
        response = self.get_module_defaults(self.module, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("electricity_emission_default", response.data)

    def test_patch_country_t2_and_ef_source_t2(self):
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["country_t2"] = self.project.country.id
        validated_data["ef_source_t2"] = models.EmissionFactorSource.objects.get_or_create(name="Combined Margin")[0].id
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")
