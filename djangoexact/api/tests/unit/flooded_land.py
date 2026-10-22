"""Reservoir (flooded land) as a land use change target, IPCC 2019 Vol. 4 Ch. 7 (NEXT port, feature reservoirs).

Run with:
    python manage.py test api.tests.unit.flooded_land
"""

from unittest.mock import Mock

from rest_framework import status

import api.models as models
import ipcc.models as ipcc_models
from api.calculators import FloodedLandCalculator, LandUseChangeCalculator
from api.defaults import FloodedLandDefaults
from api.reports.land import FloodedLandReport
from api.tests.unit.utils import APITestCaseMixin
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes

from . import base_module
from .factories import UnitTestAnnualCroplandFactory, UnitTestForestManagementFactory

AREA = 100  # create_activity's area
CO2 = 44 / 12


def _yearly(result, activity, gas=None):
    sets = [s for s in result.yearly_emissions_by_sector_by_gas if s.activity == activity and (gas is None or s.gas_type == gas)]
    if not sets:
        return []
    (s,) = sets
    return [e.value for e in s.emissions]


class FloodedLandTestMixin:
    def create_project(self):
        # Fixed site so reservoir, SOC and forest reference data all exist: Tropical / Moist, Kenya.
        climate = models.Climate.objects.get(name_en="Tropical")
        moisture = models.Moisture.objects.get(name_en="Moist")
        soil = ipcc_models.SoilOrganicCarbon.objects.filter(climate=climate, moisture=moisture).order_by("pk").first()
        self.project_data.update(
            climate=climate.id,
            moisture=moisture.id,
            soil_type=soil.soil_type_id,
            country=models.Country.objects.get(name="Kenya").id,
            start_year_of_activities=2025,
            implementation_years=5,
            last_year_of_accounting=2055,
        )
        return super().create_project()

    def flood(self, **extra):
        trophic = {t.name_en: t.id for t in models.TrophicType.objects.all()}
        response = self.edit_module(self.module_w, self.user, {"trophic_type_w": trophic["Mesotrophic"], **extra})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module_w.refresh_from_db()
        self.assertTrue(self.module_w.is_ready())

    def expected_reservoir(self, alpha=3.0, rd=0.09, ef_le=None, ef_gt=None):
        """CH4 and CO2 per year with yearly cohorts aged from their own flooding (mid-year linear areas)."""
        ef = ipcc_models.ReservoirEmissionFactor.objects.get(climate=self.project.climate, moisture=self.project.moisture)
        ef_le = ef.ch4_age_le_20 if ef_le is None else ef_le
        ef_gt = ef.ch4_age_gt_20 if ef_gt is None else ef_gt
        years = self.activity.implementation_years + self.activity.capitalization_years
        flooded = [AREA * min(i + 0.5, 5) / 5 for i in range(years)]
        aged = [flooded[i - 20] if i >= 20 else 0 for i in range(years)]
        k = alpha * (1 + rd) / 1000 * self.project.gwp.ch4
        ch4 = [((f - a) * ef_le + a * ef_gt) * k for f, a in zip(flooded, aged)]
        co2 = [(f - a) * ef.co2_c_age_le_20 * CO2 for f, a in zip(flooded, aged)]
        return ch4, co2

    def assert_series(self, got, want):
        self.assertEqual(len(got), len(want))
        for g, w in zip(got, want):
            self.assertAlmostEqual(g, w, places=6)

    def assert_reservoir_and_soil(self):
        calc = FloodedLandCalculator(self.module_w)
        flooded_w, flooded_wo = calc.calculate()

        ch4, co2 = self.expected_reservoir()
        self.assert_series(_yearly(flooded_w, ActivityTypes.FLOODED_LAND_CH4, GasTypes.CH4), ch4)
        self.assert_series(_yearly(flooded_w, ActivityTypes.FLOODED_LAND_CO2, GasTypes.CO2), co2)
        self.assertEqual(_yearly(flooded_w, ActivityTypes.FLOODED_LAND_CO2, GasTypes.CO2)[-1], 0)

        # Pre-flood soil carbon is lost (final FLU 0) and nothing regrows on the flooded area.
        self.assertEqual(calc.math_w.soc_end, 0)
        self.assertGreater(calc.math_w.soc_start, 0)
        self.assertAlmostEqual(sum(_yearly(flooded_w, ActivityTypes.SOIL_CO2_CHANGE, GasTypes.CO2)), calc.math_w.soc_start * AREA * CO2, places=4)
        self.assertEqual(_yearly(flooded_w, ActivityTypes.BIOMASS), [])

        # The without-project scenario keeps the original land use: no reservoir in it.
        self.assertEqual(flooded_wo.yearly_emissions_by_sector_by_gas, [])
        return flooded_w


class ForestToFloodedLandTestCase(FloodedLandTestMixin, base_module.BaseLandUseChangeTestCase):
    def setUp(self):
        super().setUp()
        self.setup_land_use_change(module_type_start_name="ForestManagement", module_type_w_name="FloodedLand", module_type_wo_name="ForestManagement")
        forest = UnitTestForestManagementFactory.build()
        self.edit_module(
            self.module_start,
            self.user,
            {
                "land_use_type_start": forest.land_use_type_start.id,
                "forest_type": forest.forest_type.id,
                "forest_condition_type": forest.forest_condition_type.id,
            },
        )
        self.flood()

    def test_deforestation_losses_then_reservoir_emissions(self):
        luc_w, luc_wo = LandUseChangeCalculator(self.land_use_change).calculate()
        self.assertGreater(sum(_yearly(luc_w, ActivityTypes.BIOMASS, GasTypes.CO2)), 0)
        self.assertEqual(_yearly(luc_wo, ActivityTypes.BIOMASS, GasTypes.CO2), [])
        self.assert_reservoir_and_soil()

    def test_results_endpoint(self):
        self.land_use_change.refresh_from_db()
        self.assertEqual(self.get_land_use_change_results(cached="false").status_code, status.HTTP_200_OK)
        response = self.get_module_results(self.module_w, cached="false")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)


class CroplandToFloodedLandTestCase(FloodedLandTestMixin, base_module.BaseLandUseChangeTestCase):
    def setUp(self):
        super().setUp()
        self.setup_land_use_change(module_type_start_name="AnnualCropland", module_type_w_name="FloodedLand", module_type_wo_name="AnnualCropland")
        annual = UnitTestAnnualCroplandFactory.build()
        config = {
            f"{field}_{scenario}": getattr(annual, f"{field}_{scenario}").id
            for field in ("land_use_type", "tillage_management_type", "organic_input_type", "residue_management_type")
            for scenario in ("start", "wo")
        }
        self.edit_module(self.module_start, self.user, config)
        self.flood()

    def test_not_ready_without_trophic_class(self):
        self.edit_module(self.module_w, self.user, {"trophic_type_w": None})
        self.module_w.refresh_from_db()
        self.assertFalse(self.module_w.is_ready())

    def test_cropland_losses_then_reservoir_emissions(self):
        luc_w, _ = LandUseChangeCalculator(self.land_use_change).calculate()
        self.assertGreaterEqual(sum(_yearly(luc_w, ActivityTypes.BIOMASS, GasTypes.CO2)), 0)
        self.assert_reservoir_and_soil()

    def test_tier_2_inputs(self):
        # Chl-a 10 ug/L gives alpha 2.6 (Eq. 7.11); separate measured CH4 factors per age class; no downstream CH4.
        self.flood(mean_annual_t2_w=10, ch4_ef_le_20_t2_w=200, ch4_ef_gt_20_t2_w=100, downstream_emissions=False)
        flooded_w, _ = FloodedLandCalculator(self.module_w).calculate()
        ch4, _ = self.expected_reservoir(alpha=2.6, rd=0, ef_le=200, ef_gt=100)
        self.assert_series(_yearly(flooded_w, ActivityTypes.FLOODED_LAND_CH4, GasTypes.CH4), ch4)

    def test_default_trophic_class_and_downstream_tier_2(self):
        default = models.TrophicType.objects.get(name_en="Default").id
        self.flood(trophic_type_w=default, rd_t2=0.2)
        flooded_w, _ = FloodedLandCalculator(self.module_w).calculate()
        ch4, _ = self.expected_reservoir(alpha=0.7, rd=0.2)
        self.assert_series(_yearly(flooded_w, ActivityTypes.FLOODED_LAND_CH4, GasTypes.CH4), ch4)

    def test_defaults(self):
        ef = ipcc_models.ReservoirEmissionFactor.objects.get(climate=self.project.climate, moisture=self.project.moisture)
        defaults = FloodedLandDefaults(self.module_w).get_defaults()
        self.assertEqual(defaults.ch4_ef_le_20_t2_w_default, ef.ch4_age_le_20)
        self.assertEqual(defaults.ch4_ef_gt_20_t2_w_default, ef.ch4_age_gt_20)
        self.assertEqual(defaults.alpha_t2_w_default, 3.0)
        self.assertEqual(defaults.rd_t2_default, 0.09)

    def test_report_rows(self):
        activity_report = Mock()
        activity_report.project_report.duration = self.activity.implementation_years + self.activity.capitalization_years
        activity_report.project_report.cache_batch = None
        result = FloodedLandReport(module=self.module_w, activity_report=activity_report).compute()
        labels = [r.label for r in result.result_rows]
        self.assertIn("CH4 from flooded land (reservoir)", labels)
        self.assertIn("CO2 from land converted to flooded land", labels)
        self.assertIn("CO2 in soils", labels)


class FloodedLandBuilderTestCase(APITestCaseMixin):
    def setUp(self):
        super().setUp()
        response = self.create_project()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.project = models.Project.objects.get(id=response.data["id"])
        self.flooded = models.ModuleType.objects.get(class_name="FloodedLand")
        self.cropland = models.ModuleType.objects.get(class_name="AnnualCropland")

    def test_module_type_row(self):
        self.assertEqual(self.flooded.pk, 67)
        self.assertTrue(self.flooded.is_luc)
        self.assertEqual(self.flooded.name_en, "Reservoir (flooded land)")

    def test_cannot_be_the_starting_land_use(self):
        response = self.create_activity(self.project, self.user, [self.flooded, self.cropland, self.flooded], land_use_change=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_be_added_without_a_land_use_change(self):
        response = self.create_activity(self.project, self.user, [self.flooded])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_be_the_final_land_use(self):
        response = self.create_activity(self.project, self.user, [self.cropland, self.flooded, self.cropland], land_use_change=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        module = models.FloodedLand.objects.get(activity_id=response.data["id"])
        self.assertEqual(module.land_use_type_w.name_en, "Reservoir (flooded land)")


class GrasslandToFloodedLandTestCase(FloodedLandTestMixin, base_module.BaseLandUseChangeTestCase):
    def setUp(self):
        super().setUp()
        self.setup_land_use_change(module_type_start_name="Grassland", module_type_w_name="FloodedLand", module_type_wo_name="Grassland")
        management = models.GrasslandManagementType.objects.order_by("pk").first().id
        self.edit_module(self.module_start, self.user, {"grassland_management_type_start": management, "grassland_management_type_wo": management})
        self.flood()

    def test_grassland_losses_then_reservoir_emissions(self):
        LandUseChangeCalculator(self.land_use_change).calculate()
        self.assert_reservoir_and_soil()
