"""Food Processing Wastewater module: IPCC industrial wastewater CH4 and N2O (CRT 5.D.2)."""

import json
from unittest.mock import Mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import force_authenticate

import api.models as models
import ipcc.models as ipcc_models
from api import calculators
from api.reports.base import BaseProjectReport
from api.reports.modules import FoodProcessingWastewaterReport
from api import views
from api.views import ProjectViewSet, generic_module_viewset
from math_model.no_time_dependency_final.food_wastewater import ScenarioInputs, TreatmentShare, annual_emissions
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes

from . import base_module

SCENARIOS = ("start", "w", "wo")
CH4 = str(ActivityTypes.FOOD_WASTEWATER_CH4)
N2O = str(ActivityTypes.FOOD_WASTEWATER_N2O)


def meat_poultry():
    return ipcc_models.FoodIndustryWastewater.objects.get(code="meat_poultry")


VALUES = {
    **{f"industry_type_{s}": None for s in SCENARIOS},
    "production_start": 1000.0,
    "production_w": 1000.0,
    "production_wo": 1200.0,
    "treatment_mix_start": {"anaerobic_deep_lagoon": 1.0},
    "treatment_mix_w": {"anaerobic_reactor": 0.5, "aerobic": 0.5},
    "treatment_mix_wo": {"anaerobic_deep_lagoon": 1.0},
    "ch4_recovered_w": 2000.0,
}


class FoodProcessingWastewaterTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.FoodProcessingWastewater
        super().setUp()
        self.validated_data = {**VALUES, **{f"industry_type_{s}": meat_poultry().pk for s in SCENARIOS}}
        response = self.edit_module(self.module, self.user, self.validated_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module.refresh_from_db()

    def results(self, aggregate="activity"):
        view = self.module_viewset.as_view({"get": "results"})
        url = reverse("foodprocessingwastewater-results", args=[self.module.pk]) + f"?cached=false&aggregate={aggregate}"
        request = self.request_factory.get(url, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def line(self, data, key, activity):
        rows = [row for row in data[key] if row["activity"] == activity]
        self.assertEqual(len(rows), 1, (key, activity))
        return [emission["value"] for emission in rows[0]["emissions"]]

    def test_status_ready_and_empty_without_mix(self):
        self.assertTrue(self.module.is_ready())
        response = self.edit_module(self.module, self.user, {"treatment_mix_w": {}})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module.refresh_from_db()
        self.assertFalse(self.module.is_ready())

    def test_mix_must_add_up_to_100_percent(self):
        response = self.edit_module(self.module, self.user, {"treatment_mix_w": {"aerobic": 0.5, "anaerobic_reactor": 0.4}})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("add up to 100%", str(response.data))

    def test_mix_rejects_unknown_system(self):
        response = self.edit_module(self.module, self.user, {"treatment_mix_w": {"septic_tank": 1.0}})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_results_match_ipcc_hand_calculation(self):
        data = self.results()
        gwp = self.project.gwp
        industry = meat_poultry()
        systems = {s.code: s for s in ipcc_models.WastewaterTreatmentSystem.objects.all()}

        def state(scenario):
            mix = VALUES[f"treatment_mix_{scenario}"]
            return ScenarioInputs(
                production=VALUES[f"production_{scenario}"],
                wastewater=13.0,
                cod=4.1,
                total_n=0.19,
                treatment=[TreatmentShare(share, systems[code].mcf, systems[code].ef_n2o_plant, systems[code].n_removal) for code, share in mix.items()],
                ch4_recovered=VALUES.get(f"ch4_recovered_{scenario}", 0.0),
            )

        self.assertEqual((industry.wastewater, industry.cod, industry.total_n), (13.0, 4.1, 0.19))
        ch4_start, _ = annual_emissions(state("start"))
        self.assertAlmostEqual(ch4_start, 1000 * 13 * 4.1 * 0.25 * 0.8 / 1000)

        years = self.activity.implementation_years + self.activity.capitalization_years
        for key, scenario in (("total_w", "w"), ("total_wo", "wo")):
            ch4_end, n2o_end = annual_emissions(state(scenario))
            ch4 = self.line(data, key, CH4)
            n2o = self.line(data, key, N2O)
            self.assertEqual(len(ch4), years + self.activity.delay)
            self.assertAlmostEqual(ch4[-1], ch4_end * gwp.ch4, places=4)
            self.assertAlmostEqual(n2o[-1], n2o_end * gwp.n2o, places=4)

    def test_tier2_overrides_change_results(self):
        before = self.line(self.results(), "total_w", CH4)[-1]
        response = self.edit_module(self.module, self.user, {"cod_t2_w": 8.2})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        after = self.line(self.results(), "total_w", CH4)[-1]
        self.assertGreater(after, before)

    def test_missing_ipcc_default_needs_tier2(self):
        coffee = ipcc_models.FoodIndustryWastewater.objects.get(code="coffee")
        self.edit_module(self.module, self.user, {"industry_type_w": coffee.pk})
        self.module.refresh_from_db()
        with self.assertRaisesMessage(ValueError, "tier 2"):
            calculators.FoodProcessingWastewaterCalculator(self.module).calculate()
        self.edit_module(self.module, self.user, {"wastewater_t2_w": 10.0})
        self.module.refresh_from_db()
        calculators.FoodProcessingWastewaterCalculator(self.module).calculate()

    def test_defaults_follow_industry(self):
        response = self.get_module_defaults(self.module, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["wastewater_t2_w_default"], 13.0)
        self.assertEqual(response.data["cod_t2_start_default"], 4.1)
        self.assertEqual(response.data["tn_t2_wo_default"], 0.19)

    def test_report_rows_and_inventory_labels(self):
        report = FoodProcessingWastewaterReport(module=self.module, activity_report=Mock(project_report=BaseProjectReport(self.project)))
        result = report.compute()
        self.assertEqual([row.label for row in result.result_rows], ["CH4 from industrial wastewater (CRT 5.D.2)", "N2O from industrial wastewater (CRT 5.D.2)"])
        inventory = self.results("total")["inventory"]
        self.assertTrue(inventory)

    def test_export_import_round_trip(self):
        export = ProjectViewSet.as_view({"get": "export"})
        request = self.request_factory.get(f"/api/projects/{self.project.pk}/export/")
        force_authenticate(request, user=self.user)
        payload = json.loads(export(request, pk=self.project.pk).content)
        exported = payload["project"]["activities"][0]["modules"]["FoodProcessingWastewater"][0]
        self.assertEqual(exported["treatment_mix_w"], VALUES["treatment_mix_w"])

        importer = ProjectViewSet.as_view({"post": "import_project"})
        request = self.request_factory.post("/api/projects/import_project/?forceCopy=true", payload, format="json")
        force_authenticate(request, user=self.user)
        response = importer(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        copy = models.FoodProcessingWastewater.objects.exclude(activity__project=self.project).get(activity__project__owner=self.user)
        self.assertEqual(copy.treatment_mix_w, VALUES["treatment_mix_w"])
        self.assertEqual(copy.industry_type_w_id, meat_poultry().pk)


class FoodWastewaterBackwardCompatibilityTestCase(base_module.BaseModuleTestCase):
    """Adding the new module to an activity leaves the results of its other modules untouched."""

    def setUp(self):
        self.ModuleClass = models.Waterbody
        super().setUp()
        response = self.edit_module(
            self.module,
            self.user,
            {
                "waterbody_type": models.WaterbodyType.objects.order_by("id").first().id,
                "area": 50,
                **{f"trophic_type_{s}": models.TrophicType.objects.order_by("id").first().id for s in SCENARIOS},
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module.refresh_from_db()

    def test_waterbody_results_unchanged(self):
        before = self.get_results(cached="false").data
        food_type = models.ModuleType.objects.get(class_name="FoodProcessingWastewater")
        self.activity.module_types.add(food_type)
        food = models.FoodProcessingWastewater.objects.create(activity=self.activity)
        response = self.edit_module(food, self.user, {**VALUES, **{f"industry_type_{s}": meat_poultry().pk for s in SCENARIOS}})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.module.refresh_from_db()
        self.assertEqual(self.get_results(cached="false").data, before)
        self.assertNotIn(CH4, json.dumps(before))


class FoodWastewaterReferenceEndpointsTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.FoodProcessingWastewater
        super().setUp()

    def test_lists_are_public_and_read_only(self):
        for model, name in ((ipcc_models.FoodIndustryWastewater, "foodindustrytypes"), (ipcc_models.WastewaterTreatmentSystem, "wastewatertreatmentsystems")):
            viewset = views.public_read_only_viewset(model)
            response = viewset.as_view({"get": "list"})(self.request_factory.get(reverse(f"{name}-list")))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), model.objects.count())
            post = viewset.as_view({"post": "create"})(self.request_factory.post(reverse(f"{name}-list"), {"code": "x"}, format="json"))
            self.assertEqual(post.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(ipcc_models.WastewaterTreatmentSystem.objects.count(), 8)
        self.assertEqual(ipcc_models.FoodIndustryWastewater.objects.count(), 11)
