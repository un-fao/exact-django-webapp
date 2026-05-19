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


class EnergyTestCase(base_module.BaseModuleWithSubmoduleTestCase):
    def setUp(self):
        log.info("START - EnergyTestCase")
        self.ModuleClass = models.Energy
        self.submodule_classes = [
            models.EnergyEntry,
            models.EnergyEntry,
        ]
        super().setUp()

        self.land_use_types = self.land_use_types.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)

        self.validated_data = {
            "fuel_type_start": models.FuelType.objects.order_by("?").first().pk,
            "fuel_type_w": models.FuelType.objects.order_by("?").first().pk,
            "fuel_type_wo": models.FuelType.objects.order_by("?").first().pk,
            "quantity_consumed_per_year_start": FuzzyFloat(0, 1000).fuzz(),
            "quantity_consumed_per_year_w": FuzzyFloat(0, 1000).fuzz(),
            "quantity_consumed_per_year_wo": FuzzyFloat(0, 1000).fuzz(),
            # "electricity_ef_t2_start": FuzzyFloat(0, 10).fuzz(),
            # "electricity_ef_t2_w": FuzzyFloat(0, 10).fuzz(),
            # "electricity_ef_t2_wo": FuzzyFloat(0, 10).fuzz(),
            # "energy_ef_co2_t2_start": FuzzyFloat(0, 10).fuzz(),
            # "energy_ef_ch4_t2_start": FuzzyFloat(0, 10).fuzz(),
            # "energy_ef_n2o_t2_start": FuzzyFloat(0, 10).fuzz(),
            # "energy_ef_co2_t2_w": FuzzyFloat(0, 10).fuzz(),
            # "energy_ef_ch4_t2_w": FuzzyFloat(0, 10).fuzz(),
            # "energy_ef_n2o_t2_w": FuzzyFloat(0, 10).fuzz(),
            # "energy_ef_co2_t2_wo": FuzzyFloat(0, 10).fuzz(),
            # "energy_ef_ch4_t2_wo": FuzzyFloat(0, 10).fuzz(),
            # "energy_ef_n2o_t2_wo": FuzzyFloat(0, 10).fuzz(),
        }

        self.edit_module(self.submodules[0], self.user, self.validated_data)

        fuel_data = copy.deepcopy(self.validated_data)
        fuel_data["fuel_type_start"] = models.FuelType.objects.order_by("?").first().pk
        fuel_data["fuel_type_w"] = models.FuelType.objects.order_by("?").first().pk
        fuel_data["fuel_type_wo"] = models.FuelType.objects.order_by("?").first().pk
        self.edit_module(self.submodules[1], self.user, fuel_data)

        self.submodules[0].refresh_from_db()
        self.submodules[1].refresh_from_db()
        self.module.refresh_from_db()

    def test_results_influenced_by_tier_2_values(self):
        log.info("START - Testing results influenced by tier 2 values")
        results_view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = results_view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

        prev_balance = response.data["balance"]

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["transmission_loss_t2_w"] = FuzzyFloat(0, 10).fuzz()  # Electricity
        validated_data["energy_ef_ch4_t2_start"] = FuzzyFloat(0, 10).fuzz()  # Fuel

        response = self.edit_module(self.submodules[0], self.user, validated_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        force_authenticate(request, user=self.user)
        response = results_view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)
        self.assertNotEqual(prev_balance, response.data["balance"])

    def test_modify(self):
        log.info("START - Testing modify")
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["quantity_consumed_per_year_start"] = FuzzyFloat(0, 1000).fuzz()
        response = self.edit_module(self.submodules[0], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_patch_to_not_ready(self):
        log.info("START - Testing patch to not ready")
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["quantity_consumed_per_year_start"] = None
        response = self.edit_module(self.submodules[0], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

    def test_calculate_results(self):
        log.info("START - Testing calculate results")
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

    def test_get_defaults(self):
        log.info("START - Testing get defaults")

        response = self.get_module_defaults(self.submodules[0], self.user)
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

    def test_create_submodule_fully_populated_is_ready(self):
        # er8 create path: when ALL mandatory fields are in the create payload
        # the submodule must come back READY. validate() computes the status
        # into data["status"] (from the POST body, since there's no instance
        # to merge model defaults from on create) and super().save() persists
        # it; the cascade then runs with recompute_self=False, so this asserts
        # the create-time status is correct without the redundant post-save
        # self-recompute. transmission_loss_t2_* is a mandatory EnergyEntry
        # field that defaults on a persisted instance but must be supplied
        # explicitly on create to be READY (same pre-er8 behaviour).
        data = copy.deepcopy(self.validated_data)
        data["parent"] = self.module.pk
        data["transmission_loss_t2_start"] = 0.1
        data["transmission_loss_t2_w"] = 0.1
        data["transmission_loss_t2_wo"] = 0.1
        response = self.create_submodule(models.EnergyEntry, self.user, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"]["name"], "READY")
