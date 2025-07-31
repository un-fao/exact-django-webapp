from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework import status
from django.urls import reverse
from api.views import generic_module_viewset
import api.models as models
import ipcc.models as ipcc_models
import api.tests.unit.factories as factories
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
        self.validated_data = factories.UnitTestAnnualCroplandFactory.get_validated_data()

        self.edit_module(self.module, self.user, self.validated_data)
        self.module.refresh_from_db()

    def test_modify_and_check_cache_invalidation(self):
        response = self.get_results()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

        old_balance = response.data["balance"]

        is_modification_valid = False

        while not is_modification_valid:
            try:
                validated_data = copy.deepcopy(self.validated_data)
                validated_data["land_use_type_w"] = factories.UnitTestAnnualCroplandFactory.build().land_use_type_w.id
                response = self.edit_module(self.module, self.user, validated_data)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["status"]["name"], "READY")

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
        validated_data["land_use_type_start"] = factories.UnitTestAnnualCroplandFactory.build().land_use_type_start.id
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
        previous_balance = self.get_results().data["balance"]

        validated_data = copy.deepcopy(self.validated_data)
        validated_data.update(
            {
                "minor_land_use_type_start": factories.UnitTestAnnualCroplandFactory.build().land_use_type_start.id,
                "minor_land_use_type_w": factories.UnitTestAnnualCroplandFactory.build().land_use_type_w.id,
                "minor_land_use_type_wo": factories.UnitTestAnnualCroplandFactory.build().land_use_type_wo.id,
                "minor_residue_management_type_start": factories.UnitTestAnnualCroplandFactory.build().residue_management_type_start.id,
                "minor_residue_management_type_w": factories.UnitTestAnnualCroplandFactory.build().residue_management_type_w.id,
                "minor_residue_management_type_wo": factories.UnitTestAnnualCroplandFactory.build().residue_management_type_wo.id,
            }
        )
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)
        self.assertNotEqual(previous_balance, response.data["balance"])

    def test_calculate_results(self):
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

    def test_get_defaults(self):
        view = self.module_viewset.as_view({"get": "defaults"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-defaults", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))

    def test_add_comment_and_copy_project(self):
        thread = self.module.tillage_management_type_thread
        response = self.add_comment(thread, "test comment")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.copy_activity(self.activity, self.user)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
