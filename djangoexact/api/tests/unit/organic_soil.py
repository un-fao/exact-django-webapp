from rest_framework.test import APIRequestFactory
from rest_framework import status
from django.urls import reverse
from api.views import generic_module_viewset
import api.models as models
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyFloat
import logging as log
import copy
from . import base_module


class OrganicSoilWithGrasslandTestCase(base_module.BaseModuleTestCase):
    """
    Test OrganicSoil module when associated with a Grassland (non-LUC scenario).
    OrganicSoil must be associated with a LandModule, so we first create a Grassland.
    """

    def setUp(self):
        self.ModuleClass = models.Grassland
        super().setUp()

        # Ensure activity supports OrganicSoil
        organic_soil_type = models.ModuleType.objects.filter(class_name="OrganicSoil").first()
        if organic_soil_type:
            self.activity.module_types.add(organic_soil_type)
            self.activity.save()

        grassland_data = {
            "grassland_management_type_start": models.GrasslandManagementType.objects.order_by("?").first().id,
            "grassland_management_type_w": models.GrasslandManagementType.objects.order_by("?").first().id,
            "grassland_management_type_wo": models.GrasslandManagementType.objects.order_by("?").first().id,
            "is_fire_used_start": False,
            "is_fire_used_w": False,
            "is_fire_used_wo": False,
            "fire_periodicity_start": 2,
            "fire_periodicity_w": 2,
            "fire_periodicity_wo": 2,
            "fire_impact_start": 0.5,
            "fire_impact_w": 0.5,
            "fire_impact_wo": 0.5,
            "yield_start": 50.0,
            "yield_w": 60.0,
            "yield_wo": 50.0,
        }

        self.edit_module(self.module, self.user, grassland_data)
        self.module.refresh_from_db()

        self.peat_type = models.PeatType.objects.first()
        self.fire_type = models.FireType.objects.first()

        self.organic_soil = models.OrganicSoil.objects.create(
            activity=self.activity,
            peat_type=self.peat_type,
            drainage_area_start=50.0,
            drainage_area_w=30.0,
            drainage_area_wo=50.0,
            area_not_drained_start=100.0,
            area_not_drained_w=120.0,
            area_not_drained_wo=100.0,
            ditches_area_start=10.0,
            ditches_area_w=8.0,
            ditches_area_wo=10.0,
            soil_fire_periodicity_start=2.0,
            soil_fire_periodicity_w=2.0,
            soil_fire_periodicity_wo=2.0,
            soil_fire_impact_percentage_start=0.3,
            soil_fire_impact_percentage_w=0.3,
            soil_fire_impact_percentage_wo=0.3,
            status=models.StatusType.objects.get(name_en="READY"),
        )

        self.module.organic_soil = self.organic_soil
        self.module.save()
        self.organic_soil.refresh_from_db()

        self.organic_soil_viewset = generic_module_viewset(models.OrganicSoil)

        self.validated_data = {
            "peat_type": self.peat_type.id,
            "drainage_area_start": FuzzyFloat(0, 100).fuzz(),
            "drainage_area_w": FuzzyFloat(0, 100).fuzz(),
            "drainage_area_wo": FuzzyFloat(0, 100).fuzz(),
            "area_not_drained_start": FuzzyFloat(0, 200).fuzz(),
            "area_not_drained_w": FuzzyFloat(0, 200).fuzz(),
            "area_not_drained_wo": FuzzyFloat(0, 200).fuzz(),
            "ditches_area_start": FuzzyFloat(0, 50).fuzz(),
            "ditches_area_w": FuzzyFloat(0, 50).fuzz(),
            "ditches_area_wo": FuzzyFloat(0, 50).fuzz(),
            "onsite_co2_drainage_t2_start": FuzzyFloat(0.1, 10).fuzz(),
            "onsite_co2_drainage_t2_w": FuzzyFloat(0.1, 10).fuzz(),
            "onsite_co2_drainage_t2_wo": FuzzyFloat(0.1, 10).fuzz(),
            "onsite_ch4_drainage_t2_start": FuzzyFloat(0.01, 1).fuzz(),
            "onsite_ch4_drainage_t2_w": FuzzyFloat(0.01, 1).fuzz(),
            "onsite_ch4_drainage_t2_wo": FuzzyFloat(0.01, 1).fuzz(),
            "onsite_n2o_drainage_t2_start": FuzzyFloat(0.001, 0.1).fuzz(),
            "onsite_n2o_drainage_t2_w": FuzzyFloat(0.001, 0.1).fuzz(),
            "onsite_n2o_drainage_t2_wo": FuzzyFloat(0.001, 0.1).fuzz(),
            "offsite_doc_drainage_t2_start": FuzzyFloat(0.01, 1).fuzz(),
            "offsite_doc_drainage_t2_w": FuzzyFloat(0.01, 1).fuzz(),
            "offsite_doc_drainage_t2_wo": FuzzyFloat(0.01, 1).fuzz(),
            "offsite_ch4_drainage_t2_start": FuzzyFloat(0.001, 0.1).fuzz(),
            "offsite_ch4_drainage_t2_w": FuzzyFloat(0.001, 0.1).fuzz(),
            "offsite_ch4_drainage_t2_wo": FuzzyFloat(0.001, 0.1).fuzz(),
            "onsite_co2_rewetting_t2_start": FuzzyFloat(0.1, 10).fuzz(),
            "onsite_co2_rewetting_t2_w": FuzzyFloat(0.1, 10).fuzz(),
            "onsite_co2_rewetting_t2_wo": FuzzyFloat(0.1, 10).fuzz(),
            "onsite_ch4_rewetting_t2_start": FuzzyFloat(0.01, 1).fuzz(),
            "onsite_ch4_rewetting_t2_w": FuzzyFloat(0.01, 1).fuzz(),
            "onsite_ch4_rewetting_t2_wo": FuzzyFloat(0.01, 1).fuzz(),
            "onsite_n2o_rewetting_t2_start": FuzzyFloat(0.001, 0.1).fuzz(),
            "onsite_n2o_rewetting_t2_w": FuzzyFloat(0.001, 0.1).fuzz(),
            "onsite_n2o_rewetting_t2_wo": FuzzyFloat(0.001, 0.1).fuzz(),
            "offsite_doc_rewetting_t2_start": FuzzyFloat(0.01, 1).fuzz(),
            "offsite_doc_rewetting_t2_w": FuzzyFloat(0.01, 1).fuzz(),
            "offsite_doc_rewetting_t2_wo": FuzzyFloat(0.01, 1).fuzz(),
        }

    def _edit_organic_soil(self, data):
        view = self.organic_soil_viewset.as_view({"patch": "partial_update"})
        request = self.request_factory.patch(
            reverse("organicsoil-detail", args=[self.organic_soil.pk]),
            data,
            format="json",
        )
        force_authenticate(request, user=self.user)
        return view(request, pk=self.organic_soil.pk)

    def _get_organic_soil_results(self, cached="true"):
        view = self.organic_soil_viewset.as_view({"get": "results"})
        request = self.request_factory.get(
            reverse("organicsoil-results", args=[self.organic_soil.pk]) + f"?cached={cached}",
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.organic_soil.pk)
        log.error(response.data) if response.status_code != status.HTTP_200_OK else None
        return response

    def _get_organic_soil_defaults(self):
        view = self.organic_soil_viewset.as_view({"get": "defaults"})
        request = self.request_factory.get(
            reverse("organicsoil-defaults", args=[self.organic_soil.pk]),
            format="json",
        )
        force_authenticate(request, user=self.user)
        return view(request, pk=self.organic_soil.pk)

    def test_modify_organic_soil(self):
        validated_data = copy.deepcopy(self.validated_data)
        response = self._edit_organic_soil(validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_modify_drainage_areas(self):
        validated_data = {
            "drainage_area_start": 100.0,
            "drainage_area_w": 50.0,
            "drainage_area_wo": 100.0,
        }
        response = self._edit_organic_soil(validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organic_soil.refresh_from_db()
        self.assertEqual(self.organic_soil.drainage_area_start, 100.0)
        self.assertEqual(self.organic_soil.drainage_area_w, 50.0)
        self.assertEqual(self.organic_soil.drainage_area_wo, 100.0)

    def test_calculate_results(self):
        self._edit_organic_soil(self.validated_data)
        self.organic_soil.refresh_from_db()

        response = self._get_organic_soil_results(cached="false")
        print(f"Results response: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", response.data)

    def test_get_defaults(self):
        response = self._get_organic_soil_defaults()
        print(f"Defaults response: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))

    def test_modify_and_check_cache_invalidation(self):
        self._edit_organic_soil(self.validated_data)
        self.organic_soil.refresh_from_db()

        initial_response = self._get_organic_soil_results(cached="false")
        self.assertEqual(initial_response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", initial_response.data)
        old_balance = initial_response.data["balance"]

        new_data = copy.deepcopy(self.validated_data)
        new_data["drainage_area_w"] = 1000.0
        response = self._edit_organic_soil(new_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_response = self._get_organic_soil_results(cached="false")
        self.assertEqual(new_response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", new_response.data)
        new_balance = new_response.data["balance"]

        self.assertNotEqual(old_balance, new_balance)

    def test_organic_soil_associated_with_parent_module(self):
        self.module.refresh_from_db()
        self.assertIsNotNone(self.module.organic_soil)
        self.assertEqual(self.module.organic_soil.id, self.organic_soil.id)

    def test_peat_type_assignment(self):
        new_peat_type = models.PeatType.objects.exclude(id=self.peat_type.id).first()
        if new_peat_type:
            response = self._edit_organic_soil({"peat_type": new_peat_type.id})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.organic_soil.refresh_from_db()
            self.assertEqual(self.organic_soil.peat_type_id, new_peat_type.id)


class OrganicSoilWithLandUseChangeTestCase(base_module.BaseLandUseChangeTestCase):
    """
    Test OrganicSoil module when associated with a Land Use Change scenario.
    """

    def setUp(self):
        super().setUp()
        self.setup_land_use_change("Grassland", "ForestManagement", "Grassland")

        organic_soil_type = models.ModuleType.objects.filter(class_name="OrganicSoil").first()
        if organic_soil_type:
            self.activity.module_types.add(organic_soil_type)
            self.activity.save()

        self.peat_type = models.PeatType.objects.first()

        self.organic_soil = models.OrganicSoil.objects.create(
            activity=self.activity,
            land_use_change=self.land_use_change,
            peat_type=self.peat_type,
            drainage_area_start=50.0,
            drainage_area_w=30.0,
            drainage_area_wo=50.0,
            area_not_drained_start=100.0,
            area_not_drained_w=120.0,
            area_not_drained_wo=100.0,
            ditches_area_start=10.0,
            ditches_area_w=8.0,
            ditches_area_wo=10.0,
            soil_fire_periodicity_start=2.0,
            soil_fire_periodicity_w=2.0,
            soil_fire_periodicity_wo=2.0,
            soil_fire_impact_percentage_start=0.3,
            soil_fire_impact_percentage_w=0.3,
            soil_fire_impact_percentage_wo=0.3,
            onsite_co2_drainage_t2_start=5.0,
            onsite_co2_drainage_t2_w=4.0,
            onsite_co2_drainage_t2_wo=5.0,
            onsite_ch4_drainage_t2_start=0.5,
            onsite_ch4_drainage_t2_w=0.4,
            onsite_ch4_drainage_t2_wo=0.5,
            onsite_n2o_drainage_t2_start=0.05,
            onsite_n2o_drainage_t2_w=0.04,
            onsite_n2o_drainage_t2_wo=0.05,
            offsite_doc_drainage_t2_start=0.2,
            offsite_doc_drainage_t2_w=0.15,
            offsite_doc_drainage_t2_wo=0.2,
            offsite_ch4_drainage_t2_start=0.02,
            offsite_ch4_drainage_t2_w=0.015,
            offsite_ch4_drainage_t2_wo=0.02,
            onsite_co2_rewetting_t2_start=3.0,
            onsite_co2_rewetting_t2_w=2.5,
            onsite_co2_rewetting_t2_wo=3.0,
            onsite_ch4_rewetting_t2_start=0.3,
            onsite_ch4_rewetting_t2_w=0.25,
            onsite_ch4_rewetting_t2_wo=0.3,
            onsite_n2o_rewetting_t2_start=0.03,
            onsite_n2o_rewetting_t2_w=0.025,
            onsite_n2o_rewetting_t2_wo=0.03,
            offsite_doc_rewetting_t2_start=0.1,
            offsite_doc_rewetting_t2_w=0.08,
            offsite_doc_rewetting_t2_wo=0.1,
            status=models.StatusType.objects.get(name_en="READY"),
        )

        self.land_use_change.organic_soil = self.organic_soil
        self.land_use_change.save()

        self.organic_soil_viewset = generic_module_viewset(models.OrganicSoil)
        self.request_factory = APIRequestFactory(enforce_csrf_checks=False)

    def _edit_organic_soil(self, data):
        view = self.organic_soil_viewset.as_view({"patch": "partial_update"})
        request = self.request_factory.patch(
            reverse("organicsoil-detail", args=[self.organic_soil.pk]),
            data,
            format="json",
        )
        force_authenticate(request, user=self.user)
        return view(request, pk=self.organic_soil.pk)

    def _get_organic_soil_results(self, cached="true"):
        view = self.organic_soil_viewset.as_view({"get": "results"})
        request = self.request_factory.get(
            reverse("organicsoil-results", args=[self.organic_soil.pk]) + f"?cached={cached}",
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.organic_soil.pk)
        log.error(response.data) if response.status_code != status.HTTP_200_OK else None
        return response

    def test_organic_soil_with_luc_calculation(self):
        response = self._get_organic_soil_results(cached="false")
        print(f"OrganicSoil with LUC results: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", response.data)

    def test_organic_soil_associated_with_land_use_change(self):
        self.land_use_change.refresh_from_db()
        self.assertIsNotNone(self.land_use_change.organic_soil)
        self.assertEqual(self.land_use_change.organic_soil.id, self.organic_soil.id)

    def test_modify_organic_soil_in_luc_context(self):
        validated_data = {
            "drainage_area_w": 20.0,
            "area_not_drained_w": 150.0,
        }
        response = self._edit_organic_soil(validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organic_soil.refresh_from_db()
        self.assertEqual(self.organic_soil.drainage_area_w, 20.0)
        self.assertEqual(self.organic_soil.area_not_drained_w, 150.0)


class OrganicSoilPeatExtractionTestCase(base_module.BaseModuleTestCase):
    """
    Test OrganicSoil module with peat extraction scenarios.
    """

    def setUp(self):
        self.ModuleClass = models.Grassland
        super().setUp()

        organic_soil_type = models.ModuleType.objects.filter(class_name="OrganicSoil").first()
        if organic_soil_type:
            self.activity.module_types.add(organic_soil_type)
            self.activity.save()

        grassland_data = {
            "grassland_management_type_start": models.GrasslandManagementType.objects.order_by("?").first().id,
            "grassland_management_type_w": models.GrasslandManagementType.objects.order_by("?").first().id,
            "grassland_management_type_wo": models.GrasslandManagementType.objects.order_by("?").first().id,
            "is_fire_used_start": False,
            "is_fire_used_w": False,
            "is_fire_used_wo": False,
        }

        self.edit_module(self.module, self.user, grassland_data)
        self.module.refresh_from_db()

        self.peat_type = models.PeatType.objects.first()
        self.organic_soil = models.OrganicSoil.objects.create(
            activity=self.activity,
            peat_type=self.peat_type,
            drainage_area_start=50.0,
            drainage_area_w=30.0,
            drainage_area_wo=50.0,
            area_not_drained_start=100.0,
            area_not_drained_w=120.0,
            area_not_drained_wo=100.0,
            ditches_area_start=10.0,
            ditches_area_w=8.0,
            ditches_area_wo=10.0,
            peat_area_start=20.0,
            peat_area_w=10.0,
            peat_area_wo=20.0,
            peat_ditches_area_start=5.0,
            peat_ditches_area_w=3.0,
            peat_ditches_area_wo=5.0,
            peat_extraction_height_start=0.5,
            peat_extraction_height_w=0.3,
            peat_extraction_height_wo=0.5,
            is_peat_for_energy_start=False,
            is_peat_for_energy_w=False,
            is_peat_for_energy_wo=False,
            onsite_co2_drainage_t2_start=5.0,
            onsite_co2_drainage_t2_w=4.0,
            onsite_co2_drainage_t2_wo=5.0,
            onsite_ch4_drainage_t2_start=0.5,
            onsite_ch4_drainage_t2_w=0.4,
            onsite_ch4_drainage_t2_wo=0.5,
            onsite_n2o_drainage_t2_start=0.05,
            onsite_n2o_drainage_t2_w=0.04,
            onsite_n2o_drainage_t2_wo=0.05,
            offsite_doc_drainage_t2_start=0.2,
            offsite_doc_drainage_t2_w=0.15,
            offsite_doc_drainage_t2_wo=0.2,
            offsite_ch4_drainage_t2_start=0.02,
            offsite_ch4_drainage_t2_w=0.015,
            offsite_ch4_drainage_t2_wo=0.02,
            onsite_co2_rewetting_t2_start=3.0,
            onsite_co2_rewetting_t2_w=2.5,
            onsite_co2_rewetting_t2_wo=3.0,
            onsite_ch4_rewetting_t2_start=0.3,
            onsite_ch4_rewetting_t2_w=0.25,
            onsite_ch4_rewetting_t2_wo=0.3,
            onsite_n2o_rewetting_t2_start=0.03,
            onsite_n2o_rewetting_t2_w=0.025,
            onsite_n2o_rewetting_t2_wo=0.03,
            offsite_doc_rewetting_t2_start=0.1,
            offsite_doc_rewetting_t2_w=0.08,
            offsite_doc_rewetting_t2_wo=0.1,
            onsite_co2_peat_t2_start=2.0,
            onsite_co2_peat_t2_w=1.5,
            onsite_co2_peat_t2_wo=2.0,
            onsite_ch4_peat_t2_start=0.2,
            onsite_ch4_peat_t2_w=0.15,
            onsite_ch4_peat_t2_wo=0.2,
            onsite_n2o_peat_t2_start=0.02,
            onsite_n2o_peat_t2_w=0.015,
            onsite_n2o_peat_t2_wo=0.02,
            offsite_doc_peat_t2_start=0.1,
            offsite_doc_peat_t2_w=0.08,
            offsite_doc_peat_t2_wo=0.1,
            offsite_ch4_peat_t2_start=0.01,
            offsite_ch4_peat_t2_w=0.008,
            offsite_ch4_peat_t2_wo=0.01,
            peat_density_t2_start=100.0,
            peat_density_t2_w=80.0,
            peat_density_t2_wo=100.0,
            status=models.StatusType.objects.get(name_en="READY"),
        )

        self.module.organic_soil = self.organic_soil
        self.module.save()
        self.organic_soil.refresh_from_db()

        self.organic_soil_viewset = generic_module_viewset(models.OrganicSoil)

    def _edit_organic_soil(self, data):
        view = self.organic_soil_viewset.as_view({"patch": "partial_update"})
        request = self.request_factory.patch(
            reverse("organicsoil-detail", args=[self.organic_soil.pk]),
            data,
            format="json",
        )
        force_authenticate(request, user=self.user)
        return view(request, pk=self.organic_soil.pk)

    def _get_organic_soil_results(self, cached="true"):
        view = self.organic_soil_viewset.as_view({"get": "results"})
        request = self.request_factory.get(
            reverse("organicsoil-results", args=[self.organic_soil.pk]) + f"?cached={cached}",
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.organic_soil.pk)
        log.error(response.data) if response.status_code != status.HTTP_200_OK else None
        return response

    def test_peat_extraction_calculation(self):
        response = self._get_organic_soil_results(cached="false")
        print(f"Peat extraction results: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", response.data)

    def test_modify_peat_extraction_areas(self):
        validated_data = {
            "peat_area_start": 30.0,
            "peat_area_w": 15.0,
            "peat_area_wo": 30.0,
            "peat_extraction_height_start": 1.0,
            "peat_extraction_height_w": 0.5,
            "peat_extraction_height_wo": 1.0,
        }
        response = self._edit_organic_soil(validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organic_soil.refresh_from_db()
        self.assertEqual(self.organic_soil.peat_area_start, 30.0)
        self.assertEqual(self.organic_soil.peat_area_w, 15.0)
        self.assertEqual(self.organic_soil.peat_extraction_height_start, 1.0)

    def test_peat_density_tier2_values(self):
        validated_data = {
            "peat_density_t2_start": 150.0,
            "peat_density_t2_w": 120.0,
            "peat_density_t2_wo": 150.0,
        }
        response = self._edit_organic_soil(validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organic_soil.refresh_from_db()
        self.assertEqual(self.organic_soil.peat_density_t2_start, 150.0)
        self.assertEqual(self.organic_soil.peat_density_t2_w, 120.0)
        self.assertEqual(self.organic_soil.peat_density_t2_wo, 150.0)

    def test_peat_for_energy_flag(self):
        validated_data = {
            "is_peat_for_energy_start": True,
            "is_peat_for_energy_w": True,
            "is_peat_for_energy_wo": False,
        }
        response = self._edit_organic_soil(validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organic_soil.refresh_from_db()
        self.assertTrue(self.organic_soil.is_peat_for_energy_start)
        self.assertTrue(self.organic_soil.is_peat_for_energy_w)
        self.assertFalse(self.organic_soil.is_peat_for_energy_wo)


class OrganicSoilFireScenarioTestCase(base_module.BaseModuleTestCase):
    """
    Test OrganicSoil module with fire scenarios enabled.
    """

    def setUp(self):
        self.ModuleClass = models.Grassland
        super().setUp()

        grassland_data = {
            "grassland_management_type_start": models.GrasslandManagementType.objects.order_by("?").first().id,
            "grassland_management_type_w": models.GrasslandManagementType.objects.order_by("?").first().id,
            "grassland_management_type_wo": models.GrasslandManagementType.objects.order_by("?").first().id,
            "is_fire_used_start": False,
            "is_fire_used_w": False,
            "is_fire_used_wo": False,
        }

        self.edit_module(self.module, self.user, grassland_data)
        self.module.refresh_from_db()

        self.peat_type = models.PeatType.objects.first()
        self.fire_type = models.FireType.objects.first()

        self.organic_soil = models.OrganicSoil.objects.create(
            activity=self.activity,
            peat_type=self.peat_type,
            fire_type_start=self.fire_type,
            fire_type_w=self.fire_type,
            fire_type_wo=self.fire_type,
            drainage_area_start=50.0,
            drainage_area_w=30.0,
            drainage_area_wo=50.0,
            area_not_drained_start=100.0,
            area_not_drained_w=120.0,
            area_not_drained_wo=100.0,
            ditches_area_start=10.0,
            ditches_area_w=8.0,
            ditches_area_wo=10.0,
            soil_fire_periodicity_start=3.0,
            soil_fire_periodicity_w=5.0,
            soil_fire_periodicity_wo=3.0,
            soil_fire_impact_percentage_start=0.4,
            soil_fire_impact_percentage_w=0.2,
            soil_fire_impact_percentage_wo=0.4,
            mean_dry_matter_t2_start=50.0,
            mean_dry_matter_t2_w=40.0,
            mean_dry_matter_t2_wo=50.0,
            onsite_co2_drainage_t2_start=5.0,
            onsite_co2_drainage_t2_w=4.0,
            onsite_co2_drainage_t2_wo=5.0,
            onsite_ch4_drainage_t2_start=0.5,
            onsite_ch4_drainage_t2_w=0.4,
            onsite_ch4_drainage_t2_wo=0.5,
            onsite_n2o_drainage_t2_start=0.05,
            onsite_n2o_drainage_t2_w=0.04,
            onsite_n2o_drainage_t2_wo=0.05,
            offsite_doc_drainage_t2_start=0.2,
            offsite_doc_drainage_t2_w=0.15,
            offsite_doc_drainage_t2_wo=0.2,
            offsite_ch4_drainage_t2_start=0.02,
            offsite_ch4_drainage_t2_w=0.015,
            offsite_ch4_drainage_t2_wo=0.02,
            onsite_co2_rewetting_t2_start=3.0,
            onsite_co2_rewetting_t2_w=2.5,
            onsite_co2_rewetting_t2_wo=3.0,
            onsite_ch4_rewetting_t2_start=0.3,
            onsite_ch4_rewetting_t2_w=0.25,
            onsite_ch4_rewetting_t2_wo=0.3,
            onsite_n2o_rewetting_t2_start=0.03,
            onsite_n2o_rewetting_t2_w=0.025,
            onsite_n2o_rewetting_t2_wo=0.03,
            offsite_doc_rewetting_t2_start=0.1,
            offsite_doc_rewetting_t2_w=0.08,
            offsite_doc_rewetting_t2_wo=0.1,
            status=models.StatusType.objects.get(name_en="READY"),
        )

        self.module.organic_soil = self.organic_soil
        self.module.save()
        self.organic_soil.refresh_from_db()

        self.organic_soil_viewset = generic_module_viewset(models.OrganicSoil)

    def _edit_organic_soil(self, data):
        view = self.organic_soil_viewset.as_view({"patch": "partial_update"})
        request = self.request_factory.patch(
            reverse("organicsoil-detail", args=[self.organic_soil.pk]),
            data,
            format="json",
        )
        force_authenticate(request, user=self.user)
        return view(request, pk=self.organic_soil.pk)

    def _get_organic_soil_results(self, cached="true"):
        view = self.organic_soil_viewset.as_view({"get": "results"})
        request = self.request_factory.get(
            reverse("organicsoil-results", args=[self.organic_soil.pk]) + f"?cached={cached}",
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.organic_soil.pk)
        log.error(response.data) if response.status_code != status.HTTP_200_OK else None
        return response

    def test_fire_scenario_calculation(self):
        response = self._get_organic_soil_results(cached="false")
        print(f"Fire scenario results: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", response.data)

    def test_modify_fire_periodicity(self):
        validated_data = {
            "soil_fire_periodicity_start": 5.0,
            "soil_fire_periodicity_w": 10.0,
            "soil_fire_periodicity_wo": 5.0,
        }
        response = self._edit_organic_soil(validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organic_soil.refresh_from_db()
        self.assertEqual(self.organic_soil.soil_fire_periodicity_start, 5.0)
        self.assertEqual(self.organic_soil.soil_fire_periodicity_w, 10.0)

    def test_modify_fire_impact_percentage(self):
        validated_data = {
            "soil_fire_impact_percentage_start": 0.5,
            "soil_fire_impact_percentage_w": 0.1,
            "soil_fire_impact_percentage_wo": 0.5,
        }
        response = self._edit_organic_soil(validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organic_soil.refresh_from_db()
        self.assertEqual(self.organic_soil.soil_fire_impact_percentage_start, 0.5)
        self.assertEqual(self.organic_soil.soil_fire_impact_percentage_w, 0.1)

    def test_change_fire_type(self):
        other_fire_type = models.FireType.objects.exclude(id=self.fire_type.id).first()
        if other_fire_type:
            validated_data = {
                "fire_type_w": other_fire_type.id,
            }
            response = self._edit_organic_soil(validated_data)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.organic_soil.refresh_from_db()
            self.assertEqual(self.organic_soil.fire_type_w_id, other_fire_type.id)

    def test_fire_vs_no_fire_balance_difference(self):
        initial_response = self._get_organic_soil_results(cached="false")
        self.assertEqual(initial_response.status_code, status.HTTP_200_OK)
        initial_balance = initial_response.data["balance"]

        validated_data = {
            "fire_type_w": None,
            "soil_fire_periodicity_w": None,
            "soil_fire_impact_percentage_w": None,
        }
        self._edit_organic_soil(validated_data)
        self.organic_soil.refresh_from_db()

        no_fire_response = self._get_organic_soil_results(cached="false")
        self.assertEqual(no_fire_response.status_code, status.HTTP_200_OK)
        no_fire_balance = no_fire_response.data["balance"]

        print(f"Balance with fire: {initial_balance}")
        print(f"Balance without fire: {no_fire_balance}")
