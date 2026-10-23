"""Solid waste module (SolidWaste): the agrifood waste stream of an activity, IPCC 2006 Vol. 5 (2019 Refinement where updated)."""

import json
from types import SimpleNamespace
from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import force_authenticate

import api.models as models
from api.faostat_exceptions import FAOSTATNoDataError
from api.reports.modules import SolidWasteReport
from api.reports.registry import get_report_class
from api.views import ProjectViewSet
from math_model.no_time_dependency_final.general_functions import compute_yearly_or_half_year_cumulative
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes
from math_model.no_time_dependency_final.solid_waste import ROUTES

from . import base_module

SCENARIOS = ("start", "w", "wo")
AMOUNTS = {"amount_start": 100.0, "amount_w": 200.0, "amount_wo": 100.0}


def routes(**shares):
    return {f"route_{route}_{scenario}": shares.get(route) for route in ROUTES for scenario in SCENARIOS}


class SolidWasteTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.SolidWaste
        super().setUp()
        self.ready = models.StatusType.objects.get(name_en="READY").pk
        self.empty = models.StatusType.objects.get(name_en="EMPTY").pk

    def status_of(self, response):
        value = response.data["status"]
        return value["id"] if isinstance(value, dict) else value

    def results(self, aggregate="total"):
        view = self.module_viewset.as_view({"get": "results"})
        url = reverse("solidwaste-results", args=[self.module.pk]) + f"?cached=false&aggregate={aggregate}"
        request = self.request_factory.get(url, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def defaults(self):
        view = self.module_viewset.as_view({"get": "defaults"})
        request = self.request_factory.get(reverse("solidwaste-defaults", args=[self.module.pk]), format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def line(self, data, side, activity):
        rows = [row for row in data[side] if row["activity"] == str(activity)]
        return [sum(values) for values in zip(*[[e["value"] for e in row["emissions"]] for row in rows])]

    def test_module_type_and_created_empty(self):
        self.assertEqual(self.module_type.pk, 65)
        self.assertEqual(self.module.status.pk, self.empty)

    def add_annual_cropland(self, **fields):
        self.activity.module_types.add(models.ModuleType.objects.get(class_name="AnnualCropland"))
        lut = models.LandUseType.objects.filter(module_types__class_name="AnnualCropland").first()
        return models.AnnualCropland.objects.create(activity=self.activity, land_use_type_start=lut, land_use_type_w=lut, land_use_type_wo=lut, **fields)

    def test_defaults_before_ready(self):
        defaults = self.defaults()
        self.assertEqual(defaults["composting_ch4_ef_t2_w_default"], 4.0)
        self.assertEqual(defaults["composting_n2o_ef_t2_start_default"], 0.24)
        self.assertEqual(defaults["open_burning_n2o_ef_t2_wo_default"], 150.0)
        self.assertEqual(defaults["crop_sources"], [])
        self.assertFalse(any(key.startswith("composition") for key in defaults))

    @mock.patch("api.calculators._fetch_faostat_yield", return_value=SimpleNamespace(average=2.0))
    def test_crop_sources_use_tier2_yield_or_default(self, _faostat):
        crop = self.add_annual_cropland(area=10.0, crop_yield_t2_w=4.0)
        self.edit_module(self.module, self.user, {"crop_waste_annual_cropland_w": 0.25, "crop_waste_annual_cropland_start": 0.1})

        (source,) = self.defaults()["crop_sources"]
        self.assertEqual((source["key"], source["module_id"], source["area"]), ("annual_cropland", crop.pk, 10.0))
        start, w, wo = (source["scenarios"][s] for s in SCENARIOS)
        self.assertEqual((w["yield"], w["yield_source"], w["production"], w["wasted"]), (4.0, "tier2", 40.0, 10.0))
        self.assertEqual((start["yield"], start["yield_source"], start["production"]), (2.0, "default", 20.0))
        self.assertAlmostEqual(start["wasted"], 2.0)
        self.assertEqual(wo["wasted"], 0.0)
        self.assertEqual(start["crop"], crop.land_use_type_start.name)

    @mock.patch("api.calculators._fetch_faostat_yield", side_effect=FAOSTATNoDataError("none"))
    def test_crop_source_without_yield_is_flagged(self, _faostat):
        self.add_annual_cropland(area=10.0)
        (source,) = self.defaults()["crop_sources"]
        self.assertEqual(source["scenarios"]["w"], {"crop": source["scenarios"]["w"]["crop"], "yield": None, "yield_source": None, "production": None, "waste_share": None, "wasted": 0.0})

    def test_ready_with_amount_or_crop_share_and_routes_at_100(self):
        response = self.edit_module(self.module, self.user, {**AMOUNTS, **routes(composting=0.5)})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self.status_of(response), self.empty)

        response = self.edit_module(self.module, self.user, routes(composting=0.5, swds_uncategorised=0.5))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self.status_of(response), self.ready)

        response = self.edit_module(self.module, self.user, {"amount_w": None})
        self.assertEqual(self.status_of(response), self.empty)
        self.add_annual_cropland(area=1.0, crop_yield_t2_w=1.0)
        response = self.edit_module(self.module, self.user, {"crop_waste_annual_cropland_w": 0.1})
        self.assertEqual(self.status_of(response), self.ready)

    def test_shares_over_100_are_rejected(self):
        response = self.edit_module(self.module, self.user, routes(composting=0.7, incineration=0.4))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.edit_module(self.module, self.user, {"crop_waste_annual_cropland_w": 1.5})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_results_lines_and_food_waste_block(self):
        response = self.edit_module(self.module, self.user, {**AMOUNTS, **routes(composting=0.5, swds_uncategorised=0.5)})
        self.assertEqual(self.status_of(response), self.ready, response.data)

        data = self.results("activity")
        activity = self.activity
        gwp = self.project.gwp
        years = activity.implementation_years + activity.capitalization_years
        expected_ch4_n2o = [v * 0.5 * (4.0 * gwp.ch4 + 0.24 * gwp.n2o) * 1e-3 for v in compute_yearly_or_half_year_cumulative(100.0, 200.0, activity.implementation_years, activity.capitalization_years, activity.change_rate.name)]
        composting = self.line(data, "total_w", ActivityTypes.COMPOSTING)
        self.assertEqual(len(composting), years)
        for got, want in zip(composting, expected_ch4_n2o):
            self.assertAlmostEqual(got, want, places=6)
        swds_w = self.line(data, "total_w", ActivityTypes.SOLID_WASTE_DISPOSAL)
        self.assertEqual(swds_w[0], 0.0)
        self.assertGreater(swds_w[-1], 0.0)

        block = data["solid_waste"]
        self.assertEqual(block["start_year"], self.project.start_year_of_activities)
        self.assertEqual(block["food_waste"], {"start": 100.0, "w": 200.0, "wo": 100.0})
        food = block["food_waste_by_route"]
        self.assertEqual(set(food), {"w", "wo"})
        self.assertEqual(set(food["w"]), {"swds", "composting", "anaerobic_digestion", "incineration", "open_burning", "other"})
        self.assertAlmostEqual(food["wo"]["composting"][0], 50.0)
        self.assertAlmostEqual(food["wo"]["swds"][-1], 50.0)

        total = self.results("total")
        self.assertIn("solid_waste", total)
        by_activity_gas = self.results("activity_gas")
        self.assertIn("Composting (CRT 5.B.1)", {row["activity"] for row in by_activity_gas["inventory"]})

        cached = self.results("total")
        self.assertEqual(cached["balance"], total["balance"])

    def test_crop_waste_adds_to_direct_amount_and_crop_edit_invalidates_cache(self):
        crop = self.add_annual_cropland(area=10.0, crop_yield_t2_start=2.0, crop_yield_t2_w=2.0, crop_yield_t2_wo=2.0)
        self.edit_module(self.module, self.user, {**AMOUNTS, **routes(composting=1.0), "crop_waste_annual_cropland_w": 0.5})
        self.assertEqual(self.results()["solid_waste"]["food_waste"], {"start": 100.0, "w": 210.0, "wo": 100.0})

        crop.crop_yield_t2_w = 4.0
        crop.save()
        self.assertEqual(self.module.__class__.objects.get(pk=self.module.pk).get_cached_results(), None)
        self.assertEqual(self.results()["solid_waste"]["food_waste"]["w"], 220.0)

    def test_tier2_overrides_change_results(self):
        self.edit_module(self.module, self.user, {**AMOUNTS, **routes(composting=1.0)})
        before = self.results()["balance"]
        self.edit_module(self.module, self.user, {"composting_ch4_ef_t2_w": 8.0})
        self.assertNotAlmostEqual(self.results()["balance"], before, places=3)

    def test_report_registered_and_computes(self):
        self.edit_module(self.module, self.user, {**AMOUNTS, **routes(incineration=1.0)})
        self.module.refresh_from_db()
        self.assertIs(get_report_class(self.module), SolidWasteReport)
        report = SolidWasteReport(self.module)
        self.assertTrue(report.emissions_set)

    def test_export_import_round_trip(self):
        values = {**AMOUNTS, **routes(open_burning=0.25, swds_managed_anaerobic=0.75), "swds_recovery_w": 0.3, "crop_waste_flooded_rice_wo": 0.05}
        self.edit_module(self.module, self.user, values)
        self.unlock_project(self.project, self.user)

        request = self.request_factory.get(reverse("project-export", args=[self.project.pk]))
        force_authenticate(request, user=self.user)
        export = ProjectViewSet.as_view({"get": "export"})(request, pk=self.project.pk)
        self.assertEqual(export.status_code, status.HTTP_200_OK)
        payload = json.loads(b"".join(export.streaming_content) if export.streaming else export.content)

        request = self.request_factory.post(reverse("project-import-project") + "?forceCopy=true", payload, format="json")
        force_authenticate(request, user=self.user)
        response = ProjectViewSet.as_view({"post": "import_project"})(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, getattr(response, "data", None))

        imported = models.SolidWaste.objects.get(activity__project_id=response.data["projectId"])
        for field, value in values.items():
            self.assertEqual(getattr(imported, field), value, field)
        self.assertEqual(imported.status.name_en, "READY")


class SolidWasteBackwardCompatibilityTestCase(base_module.BaseModuleTestCase):
    """Modules other than solid waste keep the exact results payload shape (no extra blocks)."""

    def setUp(self):
        self.ModuleClass = models.Waterbody
        super().setUp()

    def test_other_module_payload_has_no_solid_waste_block(self):
        waterbody_type = models.WaterbodyType.objects.filter(otherconstructedwaterbodiesemissionfactor__climate=self.climate, otherconstructedwaterbodiesemissionfactor__moisture=self.moisture).first()
        if waterbody_type is None:
            self.skipTest("No waterbody emission factor for the random test climate")
        trophic = models.TrophicType.objects.filter(trophicstatefactor__isnull=False).first()
        self.edit_module(self.module, self.user, {"waterbody_type": waterbody_type.pk, "area": 10, "trophic_type_start": trophic.pk, "trophic_type_w": trophic.pk, "trophic_type_wo": trophic.pk})
        response = self.get_results(cached="false")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(set(response.data), {"total_w", "total_wo", "balance", "inventory"})
