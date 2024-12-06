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


class ProcessingTestCase(base_module.BaseModuleWithSubmoduleTestCase):
    def setUp(self):
        self.ModuleClass = models.Processing
        self.submodule_classes = [models.ProcessingEntry]
        super().setUp()

        self.land_use_types = self.land_use_types.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)

        self.validated_data = {
            "fuel_type_start": models.FuelType.objects.filter(fuel_use_type__name="Stationary").order_by("?").first().id,
            "fuel_type_w": models.FuelType.objects.filter(fuel_use_type__name="Stationary").order_by("?").first().id,
            "fuel_type_wo": models.FuelType.objects.filter(fuel_use_type__name="Stationary").order_by("?").first().id,
            "energy_ef_co2_t2": FuzzyFloat(0, 1000).fuzz(),
            "energy_ef_ch4_t2": FuzzyFloat(0, 1000).fuzz(),
            "energy_ef_n2o_t2": FuzzyFloat(0, 1000).fuzz(),
            "quantity_consumed_per_year_start": FuzzyFloat(0, 1000).fuzz(),
            "quantity_consumed_per_year_w": FuzzyFloat(0, 1000).fuzz(),
            "quantity_consumed_per_year_wo": FuzzyFloat(0, 1000).fuzz(),
        }

        self.edit_module(self.submodules[0], self.user, self.validated_data)
        self.module.refresh_from_db()

    def test_modify(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["fuel_type_start"] = models.FuelType.objects.filter(fuel_use_type__name="Stationary").order_by("?").first().id
        response = self.edit_module(self.submodules[0], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_patch_to_not_ready(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["fuel_type_start"] = None
        response = self.edit_module(self.submodules[0], self.user, validated_data)

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
