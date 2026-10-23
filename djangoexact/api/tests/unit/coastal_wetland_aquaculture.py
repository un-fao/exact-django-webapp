"""Aquaculture ponds in the Coastal Wetland module: pond CH4 and fish N2O.

Run with:
    python manage.py test api.tests.unit.coastal_wetland_aquaculture
"""

from rest_framework import status

import api.models as models
import ipcc.models as ipcc_models
from api.calculators import CoastalWetlandCalculator
from api.defaults import CoastalWetlandDefaults
from api.inventory_labels import inventory_label
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes

from . import base_module

BRACKISH_EF, SALINE_EF = 183.0, 30.0  # IPCC 2019 Table 7.12
N2O_EF = 0.00169  # 2013 Wetlands Supplement Table 4.15
POND_ACTIVITIES = {ActivityTypes.COASTAL_WATERBODIES, ActivityTypes.N20_FIELD}
# 5 implementation + 5 capitalization years, linear: yearly shares 0.1, 0.3, 0.5, 0.7, 0.9, then 5 x 1.
PHASE_IN_YEARS = 7.5


def _total(result, activity, gas):
    return sum(e.value for s in result.yearly_emissions_by_sector_by_gas if s.activity == activity and s.gas_type == gas for e in s.emissions)


def _non_pond(result):
    return sorted(
        (s.activity.value, s.gas_type.name, round(sum(e.value for e in s.emissions), 9))
        for s in result.yearly_emissions_by_sector_by_gas
        if s.activity not in POND_ACTIVITIES
    )


class CoastalWetlandAquacultureTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.CoastalWetland
        super().setUp()

        self.project.climate = models.Climate.objects.get(name_en="Tropical")
        self.project.moisture = models.Moisture.objects.get(name_en="Moist")
        self.project.start_year_of_activities = 2025
        self.project.implementation_years = 5
        self.project.last_year_of_accounting = 2035
        self.project.save()
        self.activity.change_rate = models.ChangeRate.objects.get(name="linear")
        self.activity.save()

        self.trophic = {t.name_en: t.id for t in models.TrophicType.objects.all()}
        # Alpha from the shared factor table, as the calculator reads it (first row per type), so the test follows its values.
        self.alpha = {f.trophic_type.name_en: f.value for f in ipcc_models.TrophicStateFactor.objects.select_related("trophic_type").order_by("-pk")}
        self.gwp = self.project.gwp
        # Mangrove, 40 ha drained and excavated in the with scenario: the conversion's carbon loss.
        self.base = {
            "land_use_type": models.LandUseType.objects.get(name_en="Mangrove", module_types__class_name="CoastalWetland").id,
            "area": 100,
            "area_under_drainage_w": 40,
            "drained_area_excavated_w": 40,
        }

    def _calculate(self, **extra):
        response = self.edit_module(self.module, self.user, {**self.base, **extra})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module.refresh_from_db()
        self.assertTrue(self.module.is_ready())
        calculator = CoastalWetlandCalculator(self.module)
        return calculator, calculator.calculate()

    def test_no_ponds_leaves_results_unchanged(self):
        calculator, (results_w, results_wo) = self._calculate()
        self.assertIsNone(calculator.pond_math_w)
        self.assertIs(results_w, calculator.math_w.result)
        self.assertIs(results_wo, calculator.math_wo.result)
        self.assertFalse({s.activity for s in results_w.yearly_emissions_by_sector_by_gas} & POND_ACTIVITIES)

    def test_mangrove_converted_to_brackish_pond(self):
        _, (baseline_w, _) = self._calculate()
        calculator, (results_w, results_wo) = self._calculate(
            pond_area_w=40, fish_production_w=2000, pond_trophic_type_w=self.trophic["Mesotrophic"]
        )

        # 40 ha x 183 kg CH4/ha/yr x alpha 3; 40 ha x 2000 kg fish/ha/yr x 0.00169 kg N2O-N/kg x 44/28
        ch4 = 40 * BRACKISH_EF * 3 / 1000 * self.gwp.ch4 * PHASE_IN_YEARS
        n2o = 40 * 2000 * N2O_EF / 1000 * 44 / 28 * self.gwp.n2o * PHASE_IN_YEARS
        self.assertAlmostEqual(_total(results_w, ActivityTypes.COASTAL_WATERBODIES, GasTypes.CH4), ch4, places=6)
        self.assertAlmostEqual(_total(results_w, ActivityTypes.N20_FIELD, GasTypes.N2O), n2o, places=6)
        self.assertAlmostEqual(_total(results_wo, ActivityTypes.COASTAL_WATERBODIES, GasTypes.CH4), 0)

        # Drainage, excavation and biomass loss come from the existing coastal math, untouched by the ponds.
        self.assertEqual(_non_pond(results_w), _non_pond(baseline_w))
        self.assertAlmostEqual(results_w.compute_balance() - baseline_w.compute_balance(), ch4 + n2o, places=6)

    def test_water_quality_improvement_reduces_ch4(self):
        _, (results_w, results_wo) = self._calculate(
            pond_area_start=40,
            pond_area_w=40,
            pond_area_wo=40,
            pond_trophic_type_start=self.trophic["Eutrophic"],
            pond_trophic_type_w=self.trophic["Mesotrophic"],
            pond_trophic_type_wo=self.trophic["Eutrophic"],
        )
        ch4_w = _total(results_w, ActivityTypes.COASTAL_WATERBODIES, GasTypes.CH4)
        ch4_wo = _total(results_wo, ActivityTypes.COASTAL_WATERBODIES, GasTypes.CH4)
        eutrophic, mesotrophic = self.alpha["Eutrophic"], self.alpha["Mesotrophic"]
        self.assertAlmostEqual(ch4_wo, 40 * BRACKISH_EF * eutrophic / 1000 * self.gwp.ch4 * 10, places=6)
        self.assertAlmostEqual(ch4_wo - ch4_w, 40 * BRACKISH_EF * (eutrophic - mesotrophic) / 1000 * self.gwp.ch4 * PHASE_IN_YEARS, places=6)

    def test_salinity_above_18_uses_saline_pond_ef_and_tier_2_overrides(self):
        _, (results_w, _) = self._calculate(pond_area_w=10, avg_salinity_t2=models.SalinityType.objects.get(value=">18").id)
        # No trophic state given: alpha = 1 (Eq. 7.12, Tier 1).
        self.assertAlmostEqual(_total(results_w, ActivityTypes.COASTAL_WATERBODIES, GasTypes.CH4), 10 * SALINE_EF / 1000 * self.gwp.ch4 * PHASE_IN_YEARS, places=6)

        _, (results_w, _) = self._calculate(pond_area_w=10, pond_ch4_ef_t2_w=100, pond_alpha_t2_w=2, fish_production_w=1000, fish_n2o_ef_t2_w=0.002)
        self.assertAlmostEqual(_total(results_w, ActivityTypes.COASTAL_WATERBODIES, GasTypes.CH4), 10 * 100 * 2 / 1000 * self.gwp.ch4 * PHASE_IN_YEARS, places=6)
        self.assertAlmostEqual(_total(results_w, ActivityTypes.N20_FIELD, GasTypes.N2O), 10 * 1000 * 0.002 / 1000 * 44 / 28 * self.gwp.n2o * PHASE_IN_YEARS, places=6)

    def test_defaults_and_inventory_label(self):
        self._calculate(pond_area_w=10, pond_trophic_type_w=self.trophic["Hypereutrophic"])
        values = CoastalWetlandDefaults(self.module).get_defaults()
        self.assertEqual(values.pond_ch4_ef_t2_w_default, BRACKISH_EF)
        self.assertEqual(values.pond_alpha_t2_start_default, 1.0)
        self.assertEqual(values.pond_alpha_t2_w_default, self.alpha["Hypereutrophic"])
        self.assertEqual(values.fish_n2o_ef_t2_wo_default, N2O_EF)
        self.assertEqual(inventory_label(self.module, "N2O Field"), "FISH EMISSION (EXCRETA)")
