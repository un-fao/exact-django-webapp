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


class StorageTestCase(base_module.BaseModuleWithSubmoduleTestCase):
    def setUp(self):
        self.ModuleClass = models.Storage
        self.submodule_classes = [models.StorageEntry]
        super().setUp()

        self.land_use_types = self.land_use_types.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)

        self.validated_data = {
            "quantity_consumed_per_year_start": FuzzyFloat(0, 1000).fuzz(),
            "quantity_consumed_per_year_w": FuzzyFloat(0, 1000).fuzz(),
            "quantity_consumed_per_year_wo": FuzzyFloat(0, 1000).fuzz(),
            "is_refrigerant_used": False,
        }

        self.edit_module(self.submodules[0], self.user, self.validated_data)
        self.module.refresh_from_db()

    def test_modify(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["quantity_consumed_per_year_start"] = FuzzyFloat(0, 1000).fuzz()
        response = self.edit_module(self.submodules[0], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_patch_to_not_ready(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["quantity_consumed_per_year_start"] = None
        response = self.edit_module(self.submodules[0], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

    def test_add_refrigerant(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["is_refrigerant_used"] = True
        validated_data["refrigerant_type_start"] = models.RefrigerantType.objects.order_by("?").first().pk
        validated_data["refrigerant_type_w"] = models.RefrigerantType.objects.order_by("?").first().pk
        validated_data["refrigerant_type_wo"] = models.RefrigerantType.objects.order_by("?").first().pk
        validated_data["total_refrigerant_leakage_start"] = FuzzyFloat(0, 1000).fuzz()
        validated_data["total_refrigerant_leakage_w"] = FuzzyFloat(0, 1000).fuzz()
        validated_data["total_refrigerant_leakage_wo"] = FuzzyFloat(0, 1000).fuzz()
        response = self.edit_module(self.submodules[0], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

        self.test_calculate_results()

    def test_calculate_results(self):
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

    def test_get_defaults(self):

        subresponse = self.create_submodule(models.StorageEntry, self.user, {"parent": self.module.pk})
        self.assertEqual(subresponse.status_code, status.HTTP_201_CREATED)

        submodule = models.StorageEntry.objects.get(pk=subresponse.data["id"])
        self.edit_module(submodule, self.user, self.validated_data)

        view = generic_module_viewset(models.StorageEntry).as_view({"get": "defaults"})
        print(subresponse.data["id"])
        request = self.request_factory.get(reverse(f"storageentry-defaults", args=[subresponse.data["id"]]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(type(response.data) == dict)
