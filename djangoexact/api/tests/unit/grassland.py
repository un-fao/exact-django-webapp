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
from api.calculators import GrasslandCalculator
from api.defaults import GrasslandDefaults
import copy
from . import base_module


class GrasslandTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.Grassland
        super().setUp()

        self.land_use_types = self.land_use_types.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)

        self.validated_data = {
            "grassland_management_type_start": models.GrasslandManagementType.objects.order_by("?").first().id,
            "grassland_management_type_w": models.GrasslandManagementType.objects.order_by("?").first().id,
            "grassland_management_type_wo": models.GrasslandManagementType.objects.order_by("?").first().id,
            "is_fire_used_start": FuzzyChoice([True, False]).fuzz(),
            "is_fire_used_w": FuzzyChoice([True, False]).fuzz(),
            "is_fire_used_wo": FuzzyChoice([True, False]).fuzz(),
            "fire_periodicity_start": FuzzyInteger(1, 3).fuzz(),
            "fire_periodicity_w": FuzzyInteger(1, 3).fuzz(),
            "fire_periodicity_wo": FuzzyInteger(1, 3).fuzz(),
            "fire_impact_start": FuzzyFloat(0, 1).fuzz(),
            "fire_impact_w": FuzzyFloat(0, 1).fuzz(),
            "fire_impact_wo": FuzzyFloat(0, 1).fuzz(),
            "yield_start": FuzzyFloat(0, 100).fuzz(),
            "yield_w": FuzzyFloat(0, 100).fuzz(),
            "yield_wo": FuzzyFloat(0, 100).fuzz(),
        }

        self.edit_module(self.module, self.user, self.validated_data)
        self.module.refresh_from_db()

    def test_modify(self):
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["grassland_management_type_start"] = models.GrasslandManagementType.objects.order_by("?").first().id
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.module_status_name(response), "READY")

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

        # yield_* is descriptive metadata (reports only) and never enters the calculation.
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["soc_t2_w"] = 10000

        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.module_status_name(response), "READY")

        # Check that the cache is invalidated
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

        new_balance = response.data["balance"]

        self.assertNotEqual(old_balance, new_balance)

    def test_patch_to_not_ready(self):
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["grassland_management_type_start"] = None
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.module_status_name(response), "EMPTY")

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

    def test_fire_uses_agb_not_total_biomass(self):
        """IPCC 2006 Table 6.4 lists AGB and total (above + below) biomass; fire burns only AGB."""
        agb_t_c_ha, total_t_c_ha = 0.94, 4.7
        ipcc_models.GrasslandBiomass.objects.update_or_create(
            climate=self.climate,
            moisture=self.moisture,
            defaults={"agb_t_dm_ha": 2.0, "agb_t_c_ha": agb_t_c_ha, "total_biomass_t_dm_ha": 10.0, "total_biomass_t_c_ha": total_t_c_ha},
        )

        calculator = GrasslandCalculator(self.module)
        calculator.calculate()
        for inputs in (calculator.inputs_w, calculator.inputs_wo):
            self.assertEqual(inputs["agb_ref"], agb_t_c_ha)

        defaults = GrasslandDefaults(self.module).get_defaults()
        for scenario in ("start", "w", "wo"):
            self.assertEqual(getattr(defaults, f"agb_t2_{scenario}_default"), agb_t_c_ha)

    def test_luc_biomass_t2_fills_missing_half_from_ipcc(self):
        """The LUC stock is AGB + BGB; entering only AGB (the fire value) must not drop BGB."""
        agb_t_c_ha, total_t_c_ha = 0.94, 4.7
        ipcc_models.GrasslandBiomass.objects.update_or_create(
            climate=self.climate,
            moisture=self.moisture,
            defaults={"agb_t_dm_ha": 2.0, "agb_t_c_ha": agb_t_c_ha, "total_biomass_t_dm_ha": 10.0, "total_biomass_t_c_ha": total_t_c_ha},
        )
        bgb_ref = total_t_c_ha - agb_t_c_ha

        cases = [
            ((None, None), None),
            ((2.0, None), 2.0 + bgb_ref),
            ((None, 3.0), agb_t_c_ha + 3.0),
            ((2.0, 3.0), 5.0),
        ]
        for (agb, bgb), expected in cases:
            with self.subTest(agb=agb, bgb=bgb):
                self.module.agb_t2_w, self.module.bgb_t2_w = agb, bgb
                if expected is None:
                    self.assertIsNone(self.module.biomass_t2_w)
                else:
                    self.assertAlmostEqual(self.module.biomass_t2_w, expected)

        defaults = GrasslandDefaults(self.module).get_defaults()
        for scenario in ("start", "w", "wo"):
            self.assertAlmostEqual(getattr(defaults, f"bgb_t2_{scenario}_default"), bgb_ref)

    def test_that_changing_grassland_management_type_changes_fi_in_defaults(self):
        self.test_get_defaults()

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["grassland_management_type_start"] = models.GrasslandManagementType.objects.order_by("?").first().id
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.module_status_name(response), "READY")
