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


class CoastalWetlandTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.CoastalWetland
        super().setUp()

        print(f"Land use types: {self.land_use_types}")

        self.validated_data = {
            "land_use_type": self.land_use_types.order_by("?").first().id,
            "area": FuzzyInteger(1, 100).fuzz(),
            "area_under_drainage_start": FuzzyInteger(1, 100).fuzz(),
            "area_under_drainage_w": FuzzyInteger(1, 100).fuzz(),
            "area_under_drainage_wo": FuzzyInteger(1, 100).fuzz(),
            # NOTE: Added to avoid issues with IPCC missing data
            "co2_rewetting_t2_start": FuzzyFloat(0, 100).fuzz(),
            "co2_rewetting_t2_w": FuzzyFloat(0, 100).fuzz(),
            "co2_rewetting_t2_wo": FuzzyFloat(0, 100).fuzz(),
        }

        self.edit_module(self.module, self.user, self.validated_data)
        self.module.refresh_from_db()

    def test_modify(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["land_use_type"] = self.land_use_types.order_by("?").first().id
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_modify_and_check_cache_invalidation(self):
        self.test_modify()

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
        validated_data["area_under_drainage_w"] = 10000
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
        validated_data["land_use_type"] = None
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
        self.assertTrue(type(response.data) == dict)
