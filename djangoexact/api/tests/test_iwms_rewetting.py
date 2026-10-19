"""Rewetting of inland wetland mineral soils on land modules (NEXT CROP&GRASS port, IPCC 2013 Wetlands Supplement ch.5)."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import force_authenticate

import api.calculators as calcs
import api.models as models
import ipcc.models as ipcc_models
from api.inventory_labels import inventory_label
from api.serializers import OtherLandReadSerializer
from api.tests.unit.utils import APITestCaseMixin
from api.views import generic_module_viewset
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes

IWMS_KEYS = {"iwms_rewetted_start", "iwms_rewetted_end", "ef_ch4_iwms", "iwms_flu_after_20", "methane_constant"}


def _sum(result, activity, gas):
    return sum(e.value for s in result.yearly_emissions_by_sector_by_gas if s.activity == activity and s.gas_type == gas for e in s.emissions)


class IwmsRewettingTestCase(APITestCaseMixin):
    def setUp(self):
        super().setUp()
        climate = models.Climate.objects.get(name_en="Cool Temperate")
        self.gwp = ipcc_models.GlobalWarmingPotential.objects.order_by("pk").first()
        self.project_data.update(
            climate=climate.id,
            moisture=climate.moistures.get(name_en="Moist").id,
            soil_type=models.SoilType.objects.get(name_en="Wetland").id,
            gw_potential=self.gwp.id,
            soc_ref_t2=50,
        )
        response = self.create_project()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.project = models.Project.objects.get(id=response.data["id"])

    def _module(self, class_name):
        module_type = models.ModuleType.objects.get(class_name=class_name)
        response = self.create_activity(self.project, self.user, [module_type])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=response.data["id"])
        return getattr(models, class_name).objects.get(activity=activity)

    def _patch(self, module, data):
        view = generic_module_viewset(module.__class__).as_view({"patch": "partial_update"})
        request = self.request_factory.patch(reverse(f"{module.__class__.__name__.lower()}-detail", args=[module.pk]), data, format="json")
        force_authenticate(request, user=self.user)
        return view(request, pk=module.pk)

    def _calculate(self, module, calculator_class, **fields):
        for name, value in fields.items():
            setattr(module, name, value)
        module.save()
        calculator = calculator_class(module)
        calculator.calculate()
        return calculator

    def test_ch4_matches_table_5_4_by_hand(self):
        """Rewetted in every scenario: 100 ha emit 235 kg CH4/ha/yr (temperate) over the whole analysis period."""
        module = self._module("OtherLand")
        calculator = self._calculate(module, calcs.OtherLandCalculator, is_rewetted_start=True, is_rewetted_w=True, is_rewetted_wo=True)

        years = module.activity.implementation_years + module.activity.capitalization_years
        expected = 100 * 235 / 1000 * self.gwp.ch4 * years
        with_total = calculator.results_w + calculator.results_start_w
        self.assertAlmostEqual(_sum(with_total, ActivityTypes.IWMS_REWETTING_CH4, GasTypes.CH4), expected, places=6)

        inventory = [row for row in calculator.inventory.emissions_by_sector_by_gas if row.activity == ActivityTypes.IWMS_REWETTING_CH4]
        self.assertEqual(len(inventory), 1)
        self.assertAlmostEqual(inventory[0].value, 100 * 235 / 1000 * self.gwp.ch4)
        self.assertTrue(inventory_label(module, inventory[0].activity.value).startswith("4(II)"))

    def test_rewetting_only_in_with_scenario(self):
        module = self._module("OtherLand")
        calculator = self._calculate(module, calcs.OtherLandCalculator, is_rewetted_w=True)

        self.assertGreater(_sum(calculator.results_w, ActivityTypes.IWMS_REWETTING_CH4, GasTypes.CH4), 0)
        self.assertEqual(_sum(calculator.results_start_w, ActivityTypes.IWMS_REWETTING_CH4, GasTypes.CH4), 0)
        self.assertNotIn("ef_ch4_iwms", calculator.inputs_wo)

    def test_cropland_uses_table_5_3_flu(self):
        module = self._module("SetAside")
        calculator = self._calculate(module, calcs.SetAsideCalculator, is_rewetted_w=True)

        self.assertEqual(calculator.flu_w.value, 0.8)
        self.assertNotEqual(calculator.flu_wo.value, 0.8)
        self.assertEqual(calculator.inputs_w["iwms_flu_after_20"], 1.0)
        self.assertAlmostEqual(calculator.math_w.soc_end, 50 * calculator.fmg_w.value * calculator.fi_w.value * 0.8)

    def test_other_land_keeps_2006_flu(self):
        module = self._module("OtherLand")
        calculator = self._calculate(module, calcs.OtherLandCalculator, is_rewetted_w=True)
        self.assertNotIn("iwms_flu_after_20", calculator.inputs_w)

    def test_flags_off_leave_inputs_untouched(self):
        module = self._module("SetAside")
        calculator = self._calculate(module, calcs.SetAsideCalculator)
        for inputs in (calculator.inputs_start_w, calculator.inputs_start_wo, calculator.inputs_w, calculator.inputs_wo):
            self.assertFalse(IWMS_KEYS & set(inputs))
        activities = {s.activity for s in (calculator.results_w + calculator.results_start_w).yearly_emissions_by_sector_by_gas}
        self.assertNotIn(ActivityTypes.IWMS_REWETTING_CH4, activities)

    def test_stale_flag_on_non_wetland_soil_is_ignored(self):
        module = self._module("SetAside")
        module.activity.soil_type_t2 = models.SoilType.objects.get(name_en="Sandy")
        module.activity.save()
        calculator = self._calculate(module, calcs.SetAsideCalculator, is_rewetted_w=True)
        self.assertFalse(IWMS_KEYS & set(calculator.inputs_w))

    def test_flag_rejected_on_non_wetland_soil(self):
        module = self._module("Grassland")
        module.activity.soil_type_t2 = models.SoilType.objects.get(name_en="High Activity Clay")
        module.activity.save()

        response = self._patch(module, {"is_rewetted_w": True})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("is_rewetted_w", response.data)
        self.assertIn("Wetland", str(response.data["is_rewetted_w"]))
        module.refresh_from_db()
        self.assertFalse(module.is_rewetted_w)

    def test_flag_accepted_on_wetland_soil(self):
        module = self._module("Grassland")
        response = self._patch(module, {"is_rewetted_w": True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        module.refresh_from_db()
        self.assertTrue(module.is_rewetted_w)

    def test_read_serializer_says_when_toggle_applies(self):
        module = self._module("OtherLand")
        self.assertTrue(OtherLandReadSerializer(module).data["iwms_rewetting_available"])
        module.activity.soil_type_t2 = models.SoilType.objects.get(name_en="Sandy")
        module.activity.save()
        self.assertFalse(OtherLandReadSerializer(module).data["iwms_rewetting_available"])
