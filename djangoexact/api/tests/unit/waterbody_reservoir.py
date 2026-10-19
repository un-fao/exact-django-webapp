"""Reservoir (flooded land) waterbodies, IPCC 2019 Vol. 4 Ch. 7 (NEXT port, feature reservoirs).

Run with:
    python manage.py test api.tests.unit.waterbody_reservoir
"""

from rest_framework import status

import api.models as models
from api.calculators import WaterbodyCalculator
from api.defaults import WaterbodyDefaults
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes

from . import base_module

# Tropical moist: Table 7.15 (<= 20 y), Table 7.9 (> 20 y), Table 7.13 (t CO2-C/ha/yr); ponds 183 (Table 7.12).
EF_LE_20, EF_GT_20, CO2_C, EF_POND = 251.6, 141.1, 2.77, 183.0
AREA = 100
CO2 = 44 / 12


def _yearly(result, activity, gas):
    (s,) = [s for s in result.yearly_emissions_by_sector_by_gas if s.activity == activity and s.gas_type == gas]
    return [e.value for e in s.emissions]


class WaterbodyReservoirTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.Waterbody
        super().setUp()

        # 5 implementation + 5 capitalization years, linear change, no delay.
        self.project.climate = models.Climate.objects.get(name_en="Tropical")
        self.project.moisture = models.Moisture.objects.get(name_en="Moist")
        self.project.start_year_of_activities = 2025
        self.project.implementation_years = 5
        self.project.last_year_of_accounting = 2035
        self.project.save()
        self.activity.change_rate = models.ChangeRate.objects.get(name="linear")
        self.activity.save()

        self.trophic = {t.name_en: t.id for t in models.TrophicType.objects.all()}
        self.reservoir = models.WaterbodyType.objects.get(is_reservoir=True)
        self.gwp = self.project.gwp.ch4

    def _edit(self, **data):
        response = self.edit_module(self.module, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module.refresh_from_db()
        return response

    def _reservoir(self, **extra):
        data = {
            "waterbody_type": self.reservoir.id,
            "area": AREA,
            "trophic_type_start": self.trophic["Mesotrophic"],
            "trophic_type_w": self.trophic["Oligotrophic"],
            "trophic_type_wo": self.trophic["Mesotrophic"],
            "reservoir_age_start": 17,
        }
        self._edit(**{**data, **extra})
        self.assertTrue(self.module.is_ready())
        return WaterbodyCalculator(self.module).calculate()

    def test_reservoir_crossing_20_years_mid_project(self):
        results_w, results_wo = self._reservoir()
        k = (1 + 0.09) / 1000 * self.gwp

        # alpha x area per year, start phasing out (alpha 3) plus w phasing in (alpha 0.7):
        # [270+7, 210+21, 150+35, 90+49, 30+63, 70, 70, 70, 70, 70]; ages 17-19 use the <= 20 y EF.
        alpha_area_w = [277, 231, 185, 139, 93, 70, 70, 70, 70, 70]
        expected_w = [a * (EF_LE_20 if i < 3 else EF_GT_20) * k for i, a in enumerate(alpha_area_w)]
        for got, want in zip(_yearly(results_w, ActivityTypes.FLOODED_LAND_CH4, GasTypes.CH4), expected_w):
            self.assertAlmostEqual(got, want, places=6)

        ch4_wo = sum(_yearly(results_wo, ActivityTypes.FLOODED_LAND_CH4, GasTypes.CH4))
        self.assertAlmostEqual(ch4_wo, 300 * (3 * EF_LE_20 + 7 * EF_GT_20) * k, places=6)

        # CO2 only in the 3 years before the reservoir turns 20, the same in both scenarios.
        co2_w = _yearly(results_w, ActivityTypes.FLOODED_LAND_CO2, GasTypes.CO2)
        for got, want in zip(co2_w, [AREA * CO2_C * CO2] * 3 + [0] * 7):
            self.assertAlmostEqual(got, want, places=6)
        self.assertAlmostEqual(sum(co2_w), sum(_yearly(results_wo, ActivityTypes.FLOODED_LAND_CO2, GasTypes.CO2)), places=6)

    def test_chlorophyll_tier_2_and_no_downstream(self):
        # Eq. 7.11: alpha = 0.26 x 10 ug/L = 2.6 in the w scenario; downstream off means Rd = 0.
        results_w, _ = self._reservoir(mean_annual_t2_w=10, downstream_emissions=False, reservoir_age_start=30)
        ch4_w = sum(_yearly(results_w, ActivityTypes.FLOODED_LAND_CH4, GasTypes.CH4))
        # start 300 x 2.5 hectare-years, w 260 x 7.5
        self.assertAlmostEqual(ch4_w, (300 * 2.5 + 260 * 7.5) * EF_GT_20 / 1000 * self.gwp, places=6)
        self.assertEqual(sum(_yearly(results_w, ActivityTypes.FLOODED_LAND_CO2, GasTypes.CO2)), 0)

    def test_downstream_tier_2_ratio(self):
        _, results_wo = self._reservoir(rd_t2=0.2, reservoir_age_start=40)
        ch4_wo = sum(_yearly(results_wo, ActivityTypes.FLOODED_LAND_CH4, GasTypes.CH4))
        self.assertAlmostEqual(ch4_wo, 300 * 10 * EF_GT_20 * 1.2 / 1000 * self.gwp, places=6)

    def test_reservoir_without_age_is_not_ready(self):
        self._edit(
            waterbody_type=self.reservoir.id,
            area=AREA,
            trophic_type_start=self.trophic["Default"],
            trophic_type_w=self.trophic["Default"],
            trophic_type_wo=self.trophic["Default"],
        )
        self.assertFalse(self.module.is_ready())

    def test_defaults_follow_reservoir_age(self):
        self._reservoir()
        defaults = WaterbodyDefaults(self.module).get_defaults()
        self.assertEqual(defaults.ch4_ef_t2_w_default, EF_LE_20)
        self.assertEqual(defaults.rd_t2_default, 0.09)

    def test_pond_results_unchanged(self):
        # Pinned on develop @ 9dcc3d3b with the same inputs: start eutrophic (9.9), w oligotrophic (0.7).
        self._edit(
            waterbody_type=models.WaterbodyType.objects.get(name_en="Freshwater Pond").id,
            area=AREA,
            trophic_type_start=self.trophic["Eutrophic"],
            trophic_type_w=self.trophic["Oligotrophic"],
            trophic_type_wo=self.trophic["Eutrophic"],
        )
        results_w, results_wo = WaterbodyCalculator(self.module).calculate()
        ch4_w = sum(_yearly(results_w, ActivityTypes.COASTAL_WATERBODIES, GasTypes.CH4))
        ch4_wo = sum(_yearly(results_wo, ActivityTypes.COASTAL_WATERBODIES, GasTypes.CH4))
        self.assertAlmostEqual(ch4_w, AREA * (9.9 * 2.5 + 0.7 * 7.5) * EF_POND / 1000 * self.gwp, places=6)
        self.assertAlmostEqual(ch4_wo, AREA * 9.9 * 10 * EF_POND / 1000 * self.gwp, places=6)
        self.assertEqual([s for s in results_w.yearly_emissions_by_sector_by_gas if s.activity != ActivityTypes.COASTAL_WATERBODIES], [])

    def test_report_rows_and_inventory(self):
        from unittest.mock import Mock

        from api.reports.modules import WaterbodyReport

        self._reservoir()
        activity_report = Mock()
        activity_report.project_report.duration = 10
        activity_report.project_report.cache_batch = None
        result = WaterbodyReport(module=self.module, activity_report=activity_report).compute()
        self.assertEqual([r.label for r in result.result_rows], ["CH4 from flooded land (reservoir)", "CO2 from land converted to flooded land"])
        # w and wo share the same area and age, so the CO2 balance is zero.
        self.assertAlmostEqual(sum(result.result_rows[1].yearly_values), 0, places=6)

        calc = WaterbodyCalculator(self.module)
        calc.calculate()
        inventory = {i.activity: i.value for i in calc.inventory.emissions_by_sector_by_gas}
        self.assertAlmostEqual(inventory[ActivityTypes.FLOODED_LAND_CH4], AREA * 3 * EF_LE_20 * 1.09 / 1000 * self.gwp, places=6)
        self.assertAlmostEqual(inventory[ActivityTypes.FLOODED_LAND_CO2], AREA * CO2_C * CO2, places=6)
