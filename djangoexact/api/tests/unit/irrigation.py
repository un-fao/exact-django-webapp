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


class IrrigationTestCase(base_module.BaseModuleWithSubmoduleTestCase):
    def setUp(self):
        self.ModuleClass = models.Irrigation
        self.submodule_classes = [models.IrrigationSystem, models.IrrigationPhase]
        super().setUp()

        self.land_use_types = self.land_use_types.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)

        self.validated_data = {
            "irrigation_system_type": models.IrrigationSystemType.objects.filter(module_types__class_name="IrrigationSystem").exclude(name__in="Other").order_by("?").first().pk,
            "ha_start": FuzzyFloat(0, 1000).fuzz(),
            "ha_w": FuzzyFloat(0, 1000).fuzz(),
            "ha_wo": FuzzyFloat(0, 1000).fuzz(),
            # "ef_t2_start": FuzzyFloat(0, 1000).fuzz(),
            # "ef_t2_w": FuzzyFloat(0, 1000).fuzz(),
            # "ef_t2_wo": FuzzyFloat(0, 1000).fuzz(),
        }

        self.edit_module(self.submodules[0], self.user, self.validated_data)

        self.validated_data["irrigation_system_type"] = models.IrrigationSystemType.objects.filter(module_types__class_name="IrrigationPhase").exclude(name__in="Other").order_by("?").first().pk

        fuel_data = copy.deepcopy(self.validated_data)
        fuel_data["fuel_type_start"] = models.FuelType.objects.order_by("?").first().pk
        fuel_data["fuel_type_w"] = models.FuelType.objects.order_by("?").first().pk
        fuel_data["fuel_type_wo"] = models.FuelType.objects.order_by("?").first().pk
        fuel_data["well_depth"] = FuzzyFloat(0, 10).fuzz()
        fuel_data["gross_irrigation_water_start"] = FuzzyFloat(0, 100).fuzz()
        fuel_data["gross_irrigation_water_w"] = FuzzyFloat(0, 100).fuzz()
        fuel_data["gross_irrigation_water_wo"] = FuzzyFloat(0, 100).fuzz()
        fuel_data["ef_co2_t2_start"] = FuzzyFloat(0, 1000).fuzz()
        fuel_data["ef_co2_t2_w"] = FuzzyFloat(0, 1000).fuzz()
        fuel_data["ef_co2_t2_wo"] = FuzzyFloat(0, 1000).fuzz()
        fuel_data["ef_ch4_t2_start"] = FuzzyFloat(0, 1000).fuzz()
        fuel_data["ef_ch4_t2_w"] = FuzzyFloat(0, 1000).fuzz()
        fuel_data["ef_ch4_t2_wo"] = FuzzyFloat(0, 1000).fuzz()
        fuel_data["ef_n2o_t2_start"] = FuzzyFloat(0, 1000).fuzz()
        fuel_data["ef_n2o_t2_w"] = FuzzyFloat(0, 1000).fuzz()
        fuel_data["ef_n2o_t2_wo"] = FuzzyFloat(0, 1000).fuzz()

        self.edit_module(self.submodules[1], self.user, fuel_data)

        self.submodules[0].refresh_from_db()
        self.submodules[1].refresh_from_db()
        self.module.refresh_from_db()

    def test_results_influenced_by_tier_2_values(self):
        results_view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = results_view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

        prev_balance = response.data["balance"]

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["ef_t2_start"] = FuzzyFloat(0, 1000).fuzz()

        response = self.edit_module(self.submodules[0], self.user, validated_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        force_authenticate(request, user=self.user)
        response = results_view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)
        self.assertNotEqual(prev_balance, response.data["balance"])

    def test_modify(self):
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["ha_start"] = FuzzyFloat(0, 1000).fuzz()
        response = self.edit_module(self.submodules[0], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_patch_to_not_ready(self):
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["ha_start"] = None
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
        self.assertTrue(isinstance(response.data, dict))

    def test_parent_not_ready_if_submodule_not_ready(self):
        log.info("START - Testing parent not ready if submodule not ready")

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["fuel_type_start"] = None
        response = self.edit_module(self.submodules[1], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

        self.module.refresh_from_db()
        self.assertEqual(self.module.status.name, "SUBMODULES_EMPTY")

        log.info("END - Testing parent not ready if submodule not ready")
