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


class SettlementTestCase(base_module.BaseModuleWithSubmoduleTestCase):
    def setUp(self):
        self.ModuleClass = models.Settlement
        self.submodule_classes = [models.Building, models.Road, models.OtherInfrastructure]
        super().setUp()

        self.validated_data = {
            # models.Settlement
            "settlement_type_start": models.SettlementType.objects.order_by("?").first().pk,
            "settlement_type_w": models.SettlementType.objects.order_by("?").first().pk,
            "settlement_type_wo": models.SettlementType.objects.order_by("?").first().pk,

            # models.Building
            "building_type": models.BuildingType.objects.order_by("?").first().pk,
            # + models.OtherInfrastructure
            "area_m2_start": FuzzyFloat(0, 1000).fuzz(),
            "area_m2_w": FuzzyFloat(0, 1000).fuzz(),
            "area_m2_wo": FuzzyFloat(0, 1000).fuzz(),

            # models.Road
            "road_type": models.RoadType.objects.order_by("?").first().pk,
            "length_km_start": FuzzyFloat(0, 1000).fuzz(),
            "length_km_w": FuzzyFloat(0, 1000).fuzz(),
            "length_km_wo": FuzzyFloat(0, 1000).fuzz(),
            "width_m_start": FuzzyFloat(0, 1000).fuzz(),
            "width_m_w": FuzzyFloat(0, 1000).fuzz(),
            "width_m_wo": FuzzyFloat(0, 1000).fuzz(),
        }

        self.edit_module(self.module, self.user, self.validated_data)
        self.edit_module(self.submodules[0], self.user, self.validated_data)
        self.edit_module(self.submodules[1], self.user, self.validated_data)
        self.edit_module(self.submodules[2], self.user, self.validated_data)

        self.submodules[0].refresh_from_db()
        self.submodules[1].refresh_from_db()
        self.submodules[2].refresh_from_db()
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
        validated_data["ef_t2_w"] = FuzzyFloat(0, 1000).fuzz()

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
        validated_data["building_type"] = models.BuildingType.objects.order_by("?").first().pk
        response = self.edit_module(self.submodules[0], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_patch_to_not_ready(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["building_type"] = None
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
        validated_data["building_type"] = None
        response = self.edit_module(self.submodules[0], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

        self.module.refresh_from_db()
        self.assertEqual(self.module.status.name, "SUBMODULES_EMPTY")

        log.info("END - Testing parent not ready if submodule not ready")

    def test_parent_not_ready_if_submodule_not_ready_after_modification_making_parent_ready(self):

        log.info("START - Testing parent not ready if submodule not ready after modification that makes the parent ready")

        # Modify parent module to not ready
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["settlement_type_start"] = None
        response = self.edit_module(self.module, self.user, validated_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

        # Modify submodule to not ready
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["building_type"] = None
        response = self.edit_module(self.submodules[0], self.user, validated_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

        # Modify parent module to ready
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["settlement_type_start"] = models.SettlementType.objects.order_by("?").first().pk
        response = self.edit_module(self.module, self.user, validated_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Assert parent module is not ready because submodule is still not ready
        self.module.refresh_from_db()
        self.assertNotEqual(self.module.status.name, "READY")
        self.assertEqual(self.module.status.name, "SUBMODULES_EMPTY")

        log.info("END - Testing parent not ready if submodule not ready after modification that makes the parent ready")

    def test_submodules_empty_takes_precedence_over_empty(self):
        # er8 rule: when the parent's OWN mandatory fields are missing AND a
        # submodule is not ready, the parent status must be SUBMODULES_EMPTY
        # (submodule-unready outranks own-EMPTY) — not EMPTY. This precedence
        # was deliberately introduced by the refactor and was previously
        # unasserted.
        parent_data = copy.deepcopy(self.validated_data)
        parent_data["settlement_type_start"] = None
        response = self.edit_module(self.module, self.user, parent_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        sub_data = copy.deepcopy(self.validated_data)
        sub_data["building_type"] = None
        response = self.edit_module(self.submodules[0], self.user, sub_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

        self.module.refresh_from_db()
        self.assertEqual(self.module.status.name, "SUBMODULES_EMPTY")