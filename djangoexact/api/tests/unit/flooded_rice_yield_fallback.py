"""Flooded rice in a country whose region has no IPCC rice yield (e.g. North America).

Run with:
    python manage.py test api.tests.unit.flooded_rice_yield_fallback
"""

from rest_framework import status

import api.models as models
import ipcc.models as ipcc_models
from api.calculators import FloodedRiceCalculator, FloodedRiceSeasonCalculator
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes

from . import base_module

SCENARIOS = ("start", "w", "wo")
# Tier 2 inputs: EFc (kg CH4/ha/day), SFw, SFp, SFo, cultivation days.
EFC, SFW, SFP, SFO, DAYS = 1.19, 0.60, 1.00, 1.50, 120


class FloodedRiceYieldFallbackTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.FloodedRice
        super().setUp()
        # North America has a RiceDefaultEmissionFactor but no RiceYield row.
        self.project.country = models.Country.objects.filter(region__name_en="North America").order_by("id").first()
        self.project.save()
        self.assertFalse(ipcc_models.RiceYield.objects.filter(continent=self.project.country.region).exists())

        payload = {}
        before = models.WaterManagementTypeBeforeCultivation.objects.order_by("id").first().id
        after = models.WaterManagementTypeAfterCultivation.objects.order_by("id").first().id
        amendment = models.OrganicAmendmentType.objects.exclude(name_en="Straw Burnt").order_by("id").first().id
        for sfx in SCENARIOS:
            payload.update(
                {
                    f"water_management_type_before_cultivation_{sfx}": before,
                    f"water_management_type_after_cultivation_{sfx}": after,
                    f"organic_amendment_type_{sfx}": amendment,
                    f"efc_t2_{sfx}": EFC,
                    f"sfw_t2_{sfx}": SFW,
                    f"sfp_t2_{sfx}": SFP,
                    f"sfo_t2_{sfx}": SFO,
                    f"cultivation_period_t2_{sfx}": DAYS,
                    f"crop_yield_t2_{sfx}": 4.0,
                    f"rice_straw_t2_{sfx}": 5.0,
                }
            )
        response = self.edit_module(self.module, self.user, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module = models.FloodedRice.objects.get(pk=self.module.pk)

    def test_defaults_and_results_use_tier_2_yield(self):
        self.assertEqual(self.get_module_defaults(self.module, self.user).status_code, status.HTTP_200_OK)

        calc = FloodedRiceSeasonCalculator(self.module)
        calc.calculate()
        hectare_years = sum(sum(m.hectares_total) for m in (calc.math_start_w, calc.math_w) if m)
        # IPCC 2019 Vol 4 ch.5 eq. 5.2 (EF_i = EF_c x SF_w x SF_p x SF_o) times the cultivation period of eq. 5.1.
        expected = EFC * SFW * SFP * SFO * DAYS * hectare_years * self.project.gwp.ch4 / 1000

        results_w, _ = FloodedRiceCalculator(self.module).calculate()
        rice_ch4 = sum(e.value for s in results_w.yearly_emissions_by_sector_by_gas if s.activity == ActivityTypes.CH4_EMITTED_RICE for e in s.emissions)
        self.assertGreater(expected, 0)
        self.assertAlmostEqual(rice_ch4, expected, places=6)

    def test_missing_tier_2_yield_names_the_country(self):
        self.module.crop_yield_t2_w = None
        self.module.save()
        with self.assertRaisesMessage(Exception, f"RiceYield for {self.project.country.name} does not exist. Please provide Tier 2 values for scenarios: w"):
            FloodedRiceSeasonCalculator(self.module).get_defaults()
