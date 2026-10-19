from rest_framework import status
from django.urls import reverse
import api.models as models
import ipcc.models as ipcc_models
from rest_framework.test import force_authenticate
import copy
from . import base_module
import logging

logging.getLogger().setLevel(logging.CRITICAL)
logging.getLogger("matplotlib").setLevel(logging.CRITICAL)
logging.getLogger("django").setLevel(logging.CRITICAL)
logging.getLogger("django.request").propagate = False

logging.basicConfig(level=logging.CRITICAL)


class ForestManagementTestCase(base_module.BaseModuleTestCase):
    def build_validated_data(self):
        validated_data = {
            "land_use_type_start": self.land_use_types.order_by("?").first().id,
            "forest_type": models.ForestType.objects.get(name_en="Natural").id,
            "forest_condition_type": models.ForestConditionType.objects.get(name_en="Primary").id,
            "rotation_start_year_t2_start": 1,
            "rotation_start_year_t2_w": 2,
            "rotation_start_year_t2_wo": 0,
            "rotation_length_yrs_start": 2,
            "rotation_length_yrs_w": 2,
            "rotation_length_yrs_wo": 2,
            # NOTE: Added to avoid validation errors due to missing IPCC data for some forest types
            # "agb_t2_start": FuzzyFloat(1, 100).fuzz(),
            # "agb_t2_w": FuzzyFloat(1, 100).fuzz(),
            # "agb_t2_wo": FuzzyFloat(1, 100).fuzz(),
            # "bgb_t2_start": FuzzyFloat(1, 100).fuzz(),
            # "bgb_t2_w": FuzzyFloat(1, 100).fuzz(),
            # "bgb_t2_wo": FuzzyFloat(1, 100).fuzz(),
            # "agb_max_t2_start": FuzzyFloat(1, 100).fuzz(),
            # "agb_max_t2_w": FuzzyFloat(1, 100).fuzz(),
            # "agb_max_t2_wo": FuzzyFloat(1, 100).fuzz(),
            # "bgb_max_t2_start": FuzzyFloat(1, 100).fuzz(),
            # "bgb_max_t2_w": FuzzyFloat(1, 100).fuzz(),
            # "bgb_max_t2_wo": FuzzyFloat(1, 100).fuzz(),
            # "agb_growth_rate_le_20_yrs_t2_start": FuzzyFloat(1, 100).fuzz(),
            # "agb_growth_rate_le_20_yrs_t2_w": FuzzyFloat(1, 100).fuzz(),
            # "agb_growth_rate_le_20_yrs_t2_wo": FuzzyFloat(1, 100).fuzz(),
            # "agb_growth_rate_gt_20_yrs_t2_start": FuzzyFloat(1, 100).fuzz(),
            # "agb_growth_rate_gt_20_yrs_t2_w": FuzzyFloat(1, 100).fuzz(),
            # "agb_growth_rate_gt_20_yrs_t2_wo": FuzzyFloat(1, 100).fuzz(),
            # "bgb_growth_rate_le_20_yrs_t2_start": FuzzyFloat(1, 100).fuzz(),
            # "bgb_growth_rate_le_20_yrs_t2_w": FuzzyFloat(1, 100).fuzz(),
            # "bgb_growth_rate_le_20_yrs_t2_wo": FuzzyFloat(1, 100).fuzz(),
            # "bgb_growth_rate_gt_20_yrs_t2_start": FuzzyFloat(1, 100).fuzz(),
            # "bgb_growth_rate_gt_20_yrs_t2_w": FuzzyFloat(1, 100).fuzz(),
            # "bgb_growth_rate_gt_20_yrs_t2_wo": FuzzyFloat(1, 100).fuzz(),
        }
        return validated_data

    def setUp(self):
        self.ModuleClass = models.ForestManagement
        super().setUp()

        self.land_use_types = self.land_use_types.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)

        self.validated_data = self.build_validated_data()

        self.edit_module(self.module, self.user, self.validated_data)
        self.module.refresh_from_db()

        def results_ok():
            self.assertEqual(self.get_results().status_code, status.HTTP_200_OK)

        def repick():
            self.validated_data = self.build_validated_data()
            self.edit_module(self.module, self.user, self.validated_data)
            self.module.refresh_from_db()

        self.retry(results_ok, repick, "forest management results in setUp")

    def test_modify(self):
        def modify():
            response = self.edit_module(self.module, self.user, {"land_use_type_start": self.land_use_types.order_by("?").first().id})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(self.module_status_name(response), "READY")
            return response

        return self.retry(modify, what="forest management test_modify")

    def test_modify_and_check_cache_invalidation(self):
        self.module.refresh_from_db()
        self.assertTrue(self.module.is_cached_results_valid())

        # test_modify can re-pick the current land use type, which is a no-op edit,
        # so change a field that always differs.
        response = self.edit_module(self.module, self.user, {"rotation_length_yrs_w": self.module.rotation_length_yrs_w + 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.module.refresh_from_db()

        # Invalidation works by stamping last_modified past last_cached_at, not by nulling last_cached_at.
        self.assertFalse(self.module.is_cached_results_valid())

    def test_patch_to_not_ready(self):
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["forest_type"] = None
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
        response = self.get_module_defaults(self.module, self.user)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)

    def test_select_fra_data_source_and_check_if_results_change(self):
        response = self.get_results()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # FRA replaces the stocks of every scenario alike, so in a standalone module the
        # with/without balance can stay put while each scenario total moves.
        first_total_w = response.data["total_w"]

        # Change the data source
        edit_response = self.edit_module(self.module, self.user, {"data_source": models.DataSource.objects.get(short_name="FRA").pk})
        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.module_status_name(edit_response), "READY")
        self.module.refresh_from_db()

        if not ipcc_models.FRACarbonStock.objects.filter(country=self.project.country).exists():
            self.skipTest("FRA carbon stock data not found for this country")

        response = self.get_results(cached="false")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(first_total_w, response.data["total_w"])

    def disable_rotation_w(self):
        # With a short rotation the stand is cut before it can approach the AGB/BGB cap,
        # and the with scenario continues the start stand, so neither tier 2 can matter.
        response = self.edit_module(self.module, self.user, {"rotation_length_yrs_w": None})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.module_status_name(response), "READY")
        self.module.refresh_from_db()

    def test_if_defaults_contain_not_none_agb_max_t2_start_default(self):
        response = self.get_module_defaults(self.module, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("agb_max_t2_start_default", response.data)
        self.assertIsNotNone(response.data["agb_max_t2_start_default"])

    def test_if_defaults_contain_not_none_agb_max_t2_w_default(self):
        response = self.get_module_defaults(self.module, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("agb_max_t2_w_default", response.data)
        self.assertIsNotNone(response.data["agb_max_t2_w_default"])

    def test_if_defaults_contain_not_none_agb_max_t2_wo_default(self):
        response = self.get_module_defaults(self.module, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("agb_max_t2_wo_default", response.data)

    def test_that_agb_and_agb_max_t2_w_changes_balance(self):
        self.disable_rotation_w()
        results = self.get_results(cached="false")
        self.assertEqual(results.status_code, status.HTTP_200_OK)
        self.assertIn("total_w", results.data)
        initial_balance = results.data["total_w"]

        edit_response = self.edit_module(self.module, self.user, {"agb_t2_w": 100, "agb_max_t2_w": 10000})
        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.module_status_name(edit_response), "READY")
        self.module.refresh_from_db()

        results = self.get_results(cached="false")
        self.assertEqual(results.status_code, status.HTTP_200_OK)
        self.assertIn("total_w", results.data)
        new_balance = results.data["total_w"]

        self.assertNotEqual(initial_balance, new_balance)

    def test_that_bgb_and_bgb_max_t2_w_changes_balance(self):
        self.disable_rotation_w()
        results = self.get_results(cached="false")
        self.assertEqual(results.status_code, status.HTTP_200_OK)
        self.assertIn("total_w", results.data)
        initial_balance = results.data["total_w"]

        edit_response = self.edit_module(self.module, self.user, {"bgb_t2_w": 100, "bgb_max_t2_w": 10000})
        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.module_status_name(edit_response), "READY")
        self.module.refresh_from_db()

        results = self.get_results(cached="false")
        self.assertEqual(results.status_code, status.HTTP_200_OK)
        self.assertIn("total_w", results.data)
        new_balance = results.data["total_w"]

        self.assertNotEqual(initial_balance, new_balance)

    def test_set_fra_data_source_and_check_if_litter_and_deadwood_defaults_change(self):
        fra = ipcc_models.FRACarbonStock.objects.filter(country=self.project.country).first()
        if fra is None:
            self.skipTest("FRA carbon stock data not found for this country")

        edit_response = self.edit_module(self.module, self.user, {"data_source": models.DataSource.objects.get(short_name="FRA").pk})
        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.module_status_name(edit_response), "READY")
        self.module.refresh_from_db()

        new_defaults = self.get_module_defaults(self.module, self.user)
        self.assertEqual(new_defaults.status_code, status.HTTP_200_OK)
        # The IPCC default can coincide with the FRA figure (Kenya: both 0), so assert the source, not a change.
        self.assertEqual(new_defaults.data["litter_t2_w_default"], fra.litter or 0)
        self.assertEqual(new_defaults.data["deadwood_t2_w_default"], fra.deadwood or 0)

    def test_get_defaults_and_check_it_has_agb_and_bgb_max_t2_start_default(self):
        defaults = self.get_module_defaults(self.module, self.user)
        self.assertEqual(defaults.status_code, status.HTTP_200_OK)
        self.assertIn("agb_max_t2_start_default", defaults.data)
        self.assertIn("bgb_max_t2_start_default", defaults.data)
        self.assertIsNotNone(defaults.data["agb_max_t2_start_default"])
        self.assertIsNotNone(defaults.data["bgb_max_t2_start_default"])
