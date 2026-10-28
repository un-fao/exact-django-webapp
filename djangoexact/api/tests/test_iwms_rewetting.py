"""Rewetted Inland Wetland Mineral Soils module (IPCC 2013 Wetlands Supplement ch. 5, Eq. 5.1, Table 5.4)."""

import json
from unittest.mock import Mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import force_authenticate

import api.calculators as calcs
import api.models as models
import ipcc.models as ipcc_models
from api.inventory_labels import inventory_label
from api.reports.base import BaseProjectReport
from api.reports.modules import IwmsRewettingReport
from api.reports.registry import get_report_class
from api.serializers import IwmsRewettingReadSerializer
from api.tests.unit.utils import APITestCaseMixin
from api.views import ProjectViewSet, generic_module_viewset
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes

CH4_LINE = str(ActivityTypes.IWMS_REWETTING_CH4)
LAND_CLASSES = ("AnnualCropland", "PerennialCropland", "Grassland", "SetAside", "OtherLand")


def _lines(module):
    results = calcs.CalculatorFactory().get_calculator(module)(module).calculate()
    return [[(str(s.activity), str(s.gas_type), [e.value for e in s.emissions]) for s in r.yearly_emissions_by_sector_by_gas] for r in results]


def _sum(result, gas=GasTypes.CH4):
    return sum(e.value for s in result.yearly_emissions_by_sector_by_gas if s.activity == ActivityTypes.IWMS_REWETTING_CH4 and s.gas_type == gas for e in s.emissions)


class WetlandProjectMixin(APITestCaseMixin):
    def setUp(self):
        super().setUp()
        climate = models.Climate.objects.get(name_en="Cool Temperate")
        self.gwp = ipcc_models.GlobalWarmingPotential.objects.order_by("pk").first()
        self.project_data.update(
            climate=climate.id,
            moisture=climate.moistures.get(name_en="Moist").id,
            soil_type=models.SoilType.objects.get(name_en="Wetland").id,
            gw_potential=self.gwp.id,
        )
        response = self.create_project()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.project = models.Project.objects.get(id=response.data["id"])

    def _activity(self, *class_names):
        module_types = [models.ModuleType.objects.get(class_name=name) for name in class_names]
        response = self.create_activity(self.project, self.user, module_types)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return models.Activity.objects.get(id=response.data["id"])

    def _module(self, activity=None):
        return models.IwmsRewetting.objects.get(activity=activity or self._activity("IwmsRewetting"))

    def _patch(self, module, data):
        view = generic_module_viewset(module.__class__).as_view({"patch": "partial_update"})
        request = self.request_factory.patch(reverse(f"{module.__class__.__name__.lower()}-detail", args=[module.pk]), data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=module.pk)
        module.refresh_from_db()
        return response

    def _results(self, module, aggregate="activity"):
        view = generic_module_viewset(module.__class__).as_view({"get": "results"})
        url = reverse(f"{module.__class__.__name__.lower()}-results", args=[module.pk]) + f"?cached=false&aggregate={aggregate}"
        request = self.request_factory.get(url, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=module.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data


class IwmsRewettingTestCase(WetlandProjectMixin):
    def test_new_module_is_empty_and_computes_nothing(self):
        module = self._module()
        self.assertFalse(module.is_ready())
        self.assertEqual((module.area_start, module.area_w, module.area_wo), (None, None, None))
        calculator = calcs.IwmsRewettingCalculator(module)
        calculator.calculate()
        self.assertEqual(_sum(calculator.results_w), 0)
        self.assertEqual(_sum(calculator.results_wo), 0)

    def test_ch4_matches_table_5_4_by_hand(self):
        """100 ha rewetted in every state emit 235 kg CH4/ha/yr (temperate) over the whole analysis period."""
        module = self._module()
        response = self._patch(module, {"area_start": 100, "area_w": 100, "area_wo": 100})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(module.is_ready())

        calculator = calcs.IwmsRewettingCalculator(module)
        calculator.calculate()
        years = module.activity.implementation_years + module.activity.capitalization_years
        self.assertAlmostEqual(_sum(calculator.results_w), 100 * 235 / 1000 * self.gwp.ch4 * years, places=6)

        inventory = [row for row in calculator.inventory.emissions_by_sector_by_gas if row.activity == ActivityTypes.IWMS_REWETTING_CH4]
        self.assertEqual(len(inventory), 1)
        self.assertAlmostEqual(inventory[0].value, 100 * 235 / 1000 * self.gwp.ch4)
        self.assertTrue(inventory_label(module, inventory[0].activity.value).startswith("4(II)"))

    def test_rewetting_only_with_project(self):
        module = self._module()
        self._patch(module, {"area_start": 0, "area_w": 100, "area_wo": 0})
        data = self._results(module)
        with_line = [row for row in data["total_w"] if row["activity"] == CH4_LINE]
        without_line = [row for row in data["total_wo"] if row["activity"] == CH4_LINE]
        self.assertGreater(sum(e["value"] for e in with_line[0]["emissions"]), 0)
        self.assertEqual(sum(e["value"] for e in without_line[0]["emissions"]), 0)

    def test_defaults_follow_the_activity_climate(self):
        module = self._module()
        response = self.get_module_defaults(module, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["ef_ch4_t2_w_default"], 235.0)

        tropical = models.Climate.objects.get(name_en="Tropical")
        module.activity.climate_t2 = tropical
        module.activity.moisture_t2 = tropical.moistures.first()
        module.activity.save()
        response = self.get_module_defaults(module, self.user)
        self.assertEqual(response.data["ef_ch4_t2_start_default"], 900.0)

    def test_tier2_ef_overrides_the_default(self):
        module = self._module()
        self._patch(module, {"area_start": 0, "area_w": 100, "area_wo": 0, "ef_ch4_t2_w": 100})
        calculator = calcs.IwmsRewettingCalculator(module)
        calculator.calculate()
        self.assertEqual(calculator.ef_ch4("w"), 100)
        self.assertEqual(calculator.ef_ch4("wo"), 235.0)

    def test_area_rejected_on_non_wetland_soil(self):
        module = self._module()
        module.activity.soil_type_t2 = models.SoilType.objects.get(name_en="High Activity Clay")
        module.activity.save()

        response = self._patch(module, {"area_w": 100})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Wetland", str(response.data["area_w"]))
        self.assertIsNone(module.area_w)
        self.assertEqual(self._patch(module, {"area_w": 0}).status_code, status.HTTP_200_OK)

    def test_area_left_after_soil_change_counts_nothing(self):
        module = self._module()
        self._patch(module, {"area_start": 0, "area_w": 100, "area_wo": 0})
        module.activity.soil_type_t2 = models.SoilType.objects.get(name_en="Sandy")
        module.activity.save()
        calculator = calcs.IwmsRewettingCalculator(module)
        calculator.calculate()
        self.assertEqual(_sum(calculator.results_w), 0)

    def test_read_serializer_says_whether_the_soil_is_wetland(self):
        module = self._module()
        self.assertTrue(IwmsRewettingReadSerializer(module).data["is_wetland_soil"])
        module.activity.soil_type_t2 = models.SoilType.objects.get(name_en="Sandy")
        module.activity.save()
        self.assertFalse(IwmsRewettingReadSerializer(module).data["is_wetland_soil"])

    def test_report_row(self):
        module = self._module()
        self._patch(module, {"area_start": 0, "area_w": 100, "area_wo": 0})
        self.assertIs(get_report_class(module), IwmsRewettingReport)
        result = IwmsRewettingReport(module=module, activity_report=Mock(project_report=BaseProjectReport(self.project))).compute()
        self.assertEqual([row.label for row in result.result_rows], ["CH4 from rewetted wetland mineral soils"])

    def test_export_import_round_trip(self):
        module = self._module()
        self._patch(module, {"area_start": 10, "area_w": 100, "area_wo": 10})
        export = ProjectViewSet.as_view({"get": "export"})
        request = self.request_factory.get(f"/api/projects/{self.project.pk}/export/")
        force_authenticate(request, user=self.user)
        payload = json.loads(export(request, pk=self.project.pk).content)
        self.assertEqual(payload["project"]["activities"][0]["modules"]["IwmsRewetting"][0]["area_w"], 100)

        importer = ProjectViewSet.as_view({"post": "import_project"})
        request = self.request_factory.post("/api/projects/import_project/?forceCopy=true", payload, format="json")
        force_authenticate(request, user=self.user)
        response = importer(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        copy = models.IwmsRewetting.objects.exclude(activity__project=self.project).get(activity__project__owner=self.user)
        self.assertEqual((copy.area_start, copy.area_w, copy.area_wo), (10, 100, 10))


class IwmsRewettingBackwardCompatibilityTestCase(WetlandProjectMixin):
    """The land modules are back to their develop behaviour: no rewetting field, no CH4 line, untouched results."""

    def test_land_modules_carry_no_rewetting_field(self):
        for class_name in LAND_CLASSES:
            fields = {field.name for field in getattr(models, class_name)._meta.get_fields()}
            self.assertFalse({"is_rewetted_start", "is_rewetted_w", "is_rewetted_wo"} & fields, class_name)

    def test_land_module_results_unchanged_by_the_addendum(self):
        activity = self._activity("OtherLand")
        land = models.OtherLand.objects.get(activity=activity)
        before = _lines(land)
        self.assertTrue(before[0])
        self.assertNotIn(CH4_LINE, str(before))

        activity.module_types.add(models.ModuleType.objects.get(class_name="IwmsRewetting"))
        module = models.IwmsRewetting.objects.create(activity=activity)
        response = self._patch(module, {"area_start": 0, "area_w": 100, "area_wo": 0})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        land.refresh_from_db()
        self.assertEqual(_lines(land), before)
