"""Livestock co-digestate / co-bedding N and managed manure N, IPCC 2019 Vol. 4 Ch. 10.

Run with:
    python manage.py test api.tests.unit.livestock_n_inputs
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import force_authenticate

import api.models as models
from ipcc.models import GlobalWarmingPotential
from api.calculators import LivestockCalculator
from api.serializers import LivestockReadSerializer
from math_model.no_time_dependency_final.general_functions import compute_yearly_or_half_year_cumulative
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes

from . import base_module

HEADS = 1000
# Growing swine, high productivity, South Asia, tropical moist (fixtures from Tables 10.21 / 10.22 / 10A.6):
EF3_DIGESTER, FRAC_GAS_DIGESTER = 0.0006, 0.275
EF4 = 0.01  # ManureManagementVolatilizationMultiplier for Moist
N2O = (ActivityTypes.NITROUS_MANURE_MANAGEMENT_SYSTEM, ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_SYSTEM, ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM)


def _yearly(result, activity):
    (emission_set,) = [s for s in result.yearly_emissions_by_sector_by_gas if s.activity == activity and s.gas_type == GasTypes.N2O]
    return [e.value for e in emission_set.emissions]


class LivestockNInputsTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.Livestock
        super().setUp()

        self.project.country = models.Country.objects.get(name="India")
        self.project.climate = models.Climate.objects.get(name_en="Tropical")
        self.project.moisture = models.Moisture.objects.get(name_en="Moist")
        self.project.gw_potential = GlobalWarmingPotential.objects.get(name_en="IPCC Sixth Assessment Report (AR6)")
        self.project.gwp_co2_t2 = self.project.gwp_ch4_t2 = self.project.gwp_n2o_t2 = None
        self.project.start_year_of_activities = 2025
        self.project.implementation_years = 5
        self.project.last_year_of_accounting = 2035
        self.project.save()
        self.activity.change_rate = models.ChangeRate.objects.get(name="linear")
        self.activity.save()
        self.gwp = self.project.gwp.n2o

        production = models.LivestockProductionType.objects.get(name_en="High-Productivity").id
        self.base = {
            "livestock_category_type": models.LivestockCategoryType.objects.get(name_en="Growing Swine").id,
            "livestock_production_type_start": production,
            "livestock_production_type_w": production,
            "livestock_production_type_wo": production,
            "heads_number_start": HEADS,
            "heads_number_w": HEADS,
            "heads_number_wo": HEADS,
        }
        self.lagoon = models.ManureManagementType.objects.get(name_en="Lagoon").id

    def _edit(self, **extra):
        return self.edit_module(self.module, self.user, {**self.base, **extra})

    def _calculate(self, **extra):
        response = self._edit(**extra)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module.refresh_from_db()
        self.assertTrue(self.module.is_ready())
        calculator = LivestockCalculator(self.module)
        calculator.calculate()
        return calculator

    def _managed_n(self):
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse("livestock-results", args=[self.module.pk]) + "?aggregate=managed_manure_n", format="json")
        force_authenticate(request, user=self.user)
        return view(request, pk=self.module.pk)

    def test_existing_results_unchanged(self):
        # Pinned on develop @ 9dcc3d3b with the same inputs: w uses a complementary system and a tier 2 PRP share, wo the defaults.
        solid_storage = models.ManureManagementType.objects.get(name_en="Solid Storage").id
        calculator = self._calculate(complementary_manure_management_type_w=solid_storage, prp_percentage_t2_w=0.3, heads_number_w=1500)
        totals = {
            f"{scenario}:{s.activity.name}": round(sum(e.value for e in s.emissions), 9)
            for scenario, math in (("w", calculator.math_w), ("wo", calculator.math_wo))
            for s in math.result.yearly_emissions_by_sector_by_gas
        }
        self.maxDiff = None
        self.assertEqual(totals, PINNED_TOTALS)

    def test_codigestate_n2o_hand_check(self):
        base = self._calculate().math_w.result
        with_cdg = self._calculate(co_digestate_n_w=10000).math_w.result

        to_co2e = 1 / 1000 * 44 / 28 * self.gwp
        # Eq. 10.25 direct, Eq. 10.26 x EF4 (10.28), Eq. 10.27 x EF5 (10.29) with FracLeach 0 for digesters.
        expected = [10000 * EF3_DIGESTER * to_co2e, 10000 * FRAC_GAS_DIGESTER * EF4 * to_co2e, 0.0]
        for activity, annual in zip(N2O, expected):
            delta = [a - b for a, b in zip(_yearly(with_cdg, activity), _yearly(base, activity))]
            ramp = compute_yearly_or_half_year_cumulative(0, annual, 5, 5, "linear")
            for got, want in zip(delta, ramp):
                self.assertAlmostEqual(got, want, places=9, msg=activity)

    def test_co_bedding_changes_managed_n_only(self):
        base = self._calculate()
        bedding = self._calculate(co_bedding_n_w=5.5)
        for activity in N2O:
            self.assertEqual(_yearly(bedding.math_w.result, activity), _yearly(base.math_w.result, activity))
        # Solid storage takes 13% of excreted N for this category / region; bedding has no losses (Eq. 10.34).
        self.assertAlmostEqual(bedding.math_w.managed_manure_n_available_end - base.math_w.managed_manure_n_available_end, HEADS * 0.13 * 5.5, places=6)

    def test_managed_manure_n_endpoint(self):
        calculator = self._calculate(co_digestate_n_w=10000)
        response = self._managed_n()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["unit"], "kg N/yr")
        self.assertAlmostEqual(response.data["w"], calculator.math_w.managed_manure_n_available_end)
        self.assertAlmostEqual(response.data["w"] - response.data["wo"], 10000 * (1 - (FRAC_GAS_DIGESTER + 4 * EF3_DIGESTER)), places=6)
        self.assertAlmostEqual(response.data["start"], response.data["wo"])

    def test_inputs_rejected_without_the_system(self):
        response = self._edit(complementary_manure_management_type_w=self.lagoon, prp_percentage_t2_w=0.2, co_digestate_n_w=100, co_bedding_n_w=2)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.data), {"co_digestate_n_w", "co_bedding_n_w"})

        self.assertEqual(self._edit(co_digestate_n_start=-1).status_code, status.HTTP_400_BAD_REQUEST)

    def test_applicability_flags(self):
        self._edit(complementary_manure_management_type_wo=self.lagoon, prp_percentage_t2_wo=0.2)
        self.module.refresh_from_db()
        data = LivestockReadSerializer(self.module).data
        self.assertTrue(data["co_digestate_applicable_start"])
        self.assertTrue(data["co_bedding_applicable_w"])
        self.assertFalse(data["co_digestate_applicable_wo"])
        self.assertFalse(data["co_bedding_applicable_wo"])

    def test_management_option_is_a_label(self):
        base = self._calculate()
        labelled = self._calculate(livestock_management_option="population_control")
        self.assertEqual(self.module.livestock_management_option, "population_control")
        for activity in N2O:
            self.assertEqual(_yearly(labelled.math_w.result, activity), _yearly(base.math_w.result, activity))
        self.assertEqual(self._edit(livestock_management_option="culling").status_code, status.HTTP_400_BAD_REQUEST)


PINNED_TOTALS = {
    "w:METHANE_ENTERIC_FERMENTATION": 556.875,
    "w:METHANE_MANURE_MANAGEMENT_PRP": 7.134404062,
    "w:METHANE_MANURE_MANAGEMENT_SYSTEM": 1186.768480219,
    "w:NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_PRP": 28.391757323,
    "w:NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM": 10.769589429,
    "w:NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_PRP": 45.168704831,
    "w:NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_SYSTEM": 234.091260605,
    "w:NITROUS_MANURE_MANAGEMENT_PRP": 86.03562825,
    "w:NITROUS_MANURE_MANAGEMENT_SYSTEM": 517.084746244,
    "wo:METHANE_ENTERIC_FERMENTATION": 405.0,
    "wo:METHANE_MANURE_MANAGEMENT_PRP": 0.0,
    "wo:METHANE_MANURE_MANAGEMENT_SYSTEM": 3071.28167775,
    "wo:NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_PRP": 0.0,
    "wo:NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM": 9.954640839,
    "wo:NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_PRP": 0.0,
    "wo:NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_SYSTEM": 223.703255084,
    "wo:NITROUS_MANURE_MANAGEMENT_PRP": 0.0,
    "wo:NITROUS_MANURE_MANAGEMENT_SYSTEM": 562.715490599,
}
