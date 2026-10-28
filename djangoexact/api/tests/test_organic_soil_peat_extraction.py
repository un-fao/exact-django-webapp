"""OrganicSoil drainage water-table classes, temperate grassland CO2 factors, and the unchanged legacy off-site path.

Setup: Grassland activity with OrganicSoil, Cool Temperate / Moist, nutrient-rich peat. Table 7.5 (IPCC 2006
V4 Ch7) gives 0.4 tC/t and 0.24 tC/m3 for that case.
"""

import unittest
from types import SimpleNamespace

from rest_framework import status

import api.calculators as calcs
import api.models as models
import ipcc.models as ipcc_models
from api.serializers import OrganicSoilReadSerializer
from api.services.organic_soil_peat import apply_water_table_class, water_table_class_applies
from api.tests.unit.utils import APITestCaseMixin
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes

LEGACY_PEAT_KEYS = {
    "hectares_start", "hectares_end", "percentage_ditches_start", "percentage_ditches_end", "rate_type",
    "ef_co2_onsite_ref", "ef_co2_onsite_tier_2", "ef_ch4_onsite_ref", "ef_ch4_onsite_tier_2", "ef_n2o_onsite_ref",
    "ef_n2o_onsite_tier_2", "ef_doc_offsite_ref", "ef_doc_offsite_tier_2", "ef_ch4_offsite_ref", "ef_ch4_offsite_tier_2",
    "methane_constant", "nitrous_constant", "weight_peat", "mass_tonnes_tier_2", "conversion_factor_volume",
    "c_fraction_ref", "extraction_height_start", "extraction_height_end", "delay", "implementation_time",
    "capitalization_time",
}


class OrganicSoilPeatExtractionTestCase(APITestCaseMixin):
    def setUp(self):
        super().setUp()
        self.climate = models.Climate.objects.get(name_en="Cool Temperate")
        self.moisture = models.Moisture.objects.get(name_en="Moist")
        self.project_data.update(
            climate=self.climate.id,
            moisture=self.moisture.id,
            gw_potential=ipcc_models.GlobalWarmingPotential.objects.order_by("pk").first().id,
        )
        response = self.create_project()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=response.data["id"])

        module_types = [models.ModuleType.objects.get(class_name=name) for name in ("Grassland", "OrganicSoil")]
        response = self.create_activity(project, self.user, module_types)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=response.data["id"])

        self.module = models.OrganicSoil.objects.get(activity=activity)
        self.module.peat_type = models.PeatType.objects.get(name_en="Nutrient Rich")
        for scenario in ("start", "w", "wo"):
            setattr(self.module, f"peat_area_{scenario}", 100.0)
            setattr(self.module, f"peat_ditches_area_{scenario}", 0.1)
            setattr(self.module, f"peat_extraction_height_{scenario}", 2.0)
        self.module.save()

    def _calculate(self, **fields):
        for name, value in fields.items():
            setattr(self.module, name, value)
        self.module.save()
        calculator = calcs.OrganicSoilCalculator(self.module)
        calculator.calculate()
        return calculator

    @staticmethod
    def _offsite_baseline(calculator):
        rows = calculator.peat_extraction_math_w.inventory.emissions_by_sector_by_gas
        return next(row.value for row in rows if row.activity == ActivityTypes.OFFSITE_PEAT)

    def test_legacy_project_keeps_legacy_inputs_and_result(self):
        calculator = self._calculate()

        self.assertEqual(set(calculator.peat_extraction_inputs_w), LEGACY_PEAT_KEYS)
        self.assertEqual(set(calculator.peat_extraction_inputs_wo), LEGACY_PEAT_KEYS)
        # Legacy height path: 0.4 x 0.24 density proxy x 100 ha x 2 x 100 x carbon fraction 1 x 44/12
        self.assertAlmostEqual(self._offsite_baseline(calculator), 0.4 * 0.24 * 100 * 2.0 * 100 * 44 / 12)
        self.assertAlmostEqual(calculator.ef_onsite_start.co2, 4.85)
        self.assertAlmostEqual(calculator.ef_onsite_w.co2, 4.85)

    def test_nutrient_poor_onsite_co2_is_table_2_1_value(self):
        calculator = self._calculate(peat_type=models.PeatType.objects.get(name_en="Nutrient Poor"))
        self.assertAlmostEqual(calculator.ef_onsite_start.co2, 5.3)

    def test_water_table_class_swaps_drainage_efs_per_scenario(self):
        calculator = self._calculate(water_table_class_w="deep_drained", water_table_class_wo="shallow_drained")

        self.assertAlmostEqual(calculator.ef_onsite_start.co2, 4.85)
        self.assertEqual((calculator.ef_onsite_w.co2, calculator.ef_onsite_w.ch4, calculator.ef_onsite_w.n2o), (6.1, 39.0, 8.2))
        self.assertEqual((calculator.ef_onsite_wo.co2, calculator.ef_onsite_wo.ch4, calculator.ef_onsite_wo.n2o), (3.6, 16.0, 1.6))

    def test_read_serializer_reports_water_table_applicability(self):
        data = OrganicSoilReadSerializer(self.module).data
        self.assertTrue(data["water_table_class_applicable_start"])

        self.module.peat_type = models.PeatType.objects.get(name_en="Nutrient Poor")
        self.module.save()
        self.assertFalse(OrganicSoilReadSerializer(self.module).data["water_table_class_applicable_w"])


class WaterTableApplicabilityTests(unittest.TestCase):
    grassland = SimpleNamespace(class_name="Grassland")
    cropland = SimpleNamespace(class_name="AnnualCropland")
    temperate = SimpleNamespace(name_en="Warm Temperate")
    boreal = SimpleNamespace(name_en="Boreal")
    rich = SimpleNamespace(name_en="Nutrient Rich")
    poor = SimpleNamespace(name_en="Nutrient Poor")

    def test_only_temperate_nutrient_rich_grassland(self):
        self.assertTrue(water_table_class_applies(self.grassland, self.temperate, self.rich))
        self.assertFalse(water_table_class_applies(self.cropland, self.temperate, self.rich))
        self.assertFalse(water_table_class_applies(self.grassland, self.boreal, self.rich))
        self.assertFalse(water_table_class_applies(self.grassland, self.temperate, self.poor))
        self.assertFalse(water_table_class_applies(self.grassland, self.temperate, None))

    def test_not_applicable_leaves_ef_untouched(self):
        ef = SimpleNamespace(co2=5.7, ch4=1.4, n2o=9.5)
        apply_water_table_class(ef, "deep_drained", self.grassland, self.boreal, self.rich)
        self.assertEqual((ef.co2, ef.ch4, ef.n2o), (5.7, 1.4, 9.5))

