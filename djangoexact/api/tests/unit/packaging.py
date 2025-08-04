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


class PackagingTestCase(base_module.BaseModuleWithSubmoduleTestCase):
    def setUp(self):
        self.ModuleClass = models.Packaging
        self.submodule_classes = [models.PackagingEntry]
        super().setUp()

        self.land_use_types = self.land_use_types.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)

        self.validated_data = {
            "packaging_material_type_start": models.PackagingMaterialType.objects.order_by("?").first().id,
            "packaging_material_type_w": models.PackagingMaterialType.objects.order_by("?").first().id,
            "packaging_material_type_wo": models.PackagingMaterialType.objects.order_by("?").first().id,
            "kg_of_packaging_material_start": FuzzyFloat(0, 1000).fuzz(),
            "kg_of_packaging_material_w": FuzzyFloat(0, 1000).fuzz(),
            "kg_of_packaging_material_wo": FuzzyFloat(0, 1000).fuzz(),
            "is_electric": FuzzyChoice([True, False]).fuzz(),
            "quantity_consumed_per_year_start": FuzzyFloat(0, 1000).fuzz(),
            "quantity_consumed_per_year_w": FuzzyFloat(0, 1000).fuzz(),
            "quantity_consumed_per_year_wo": FuzzyFloat(0, 1000).fuzz(),
        }

        self.edit_module(self.submodules[0], self.user, self.validated_data)
        self.module.refresh_from_db()

    def test_modify(self):
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["packaging_material_type_start"] = models.PackagingMaterialType.objects.order_by("?").first().id
        response = self.edit_module(self.submodules[0], self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_patch_to_not_ready(self):
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["packaging_material_type_start"] = None
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
        view = self.submodules_viewsets[0].as_view({"get": "defaults"})
        request = self.request_factory.get(reverse(f"{self.submodules[0].__class__.__name__.lower()}-defaults", args=[self.submodules[0].pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(type(response.data) == dict)

    def test_create_then_add_electricity_with_country_t2_and_check_different_results(self):
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

        first_balance = response.data["balance"]

        # Add a country to the module
        country_t2 = models.Country.objects.order_by("?").first()
        self.submodules[0].country_t2 = country_t2
        edit_response = self.edit_module(
            self.submodules[0],
            self.user,
            {
                "country_t2": country_t2.id,
                "is_electric": True,
                "fuel_type_start": models.FuelType.objects.get(name="Electricity").id,
                "fuel_type_w": models.FuelType.objects.get(name="Electricity").id,
                "fuel_type_wo": models.FuelType.objects.get(name="Electricity").id,
                "quantity_consumed_per_year_start": FuzzyFloat(0, 1000).fuzz(),
                "quantity_consumed_per_year_w": FuzzyFloat(0, 1000).fuzz(),
                "quantity_consumed_per_year_wo": FuzzyFloat(0, 1000).fuzz(),
            },
        )

        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(edit_response.data["status"]["name"], "READY")

        self.submodules[0].refresh_from_db()
        self.assertEqual(self.submodules[0].country_t2, country_t2)

        self.module.refresh_from_db()
        self.assertEqual(self.module.status.name, "READY")

        # Check that the results are different
        response = view(request, pk=self.module.pk)
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)
        self.assertNotEqual(response.data["balance"], first_balance)

    def test_excel_report(self):
        self.test_calculate_results()
        self.module.refresh_from_db()
        response = self.get_report(self.project, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", response["Content-Type"])