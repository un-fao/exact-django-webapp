"""OrganicSoilCalculator must accept tier 2 values when the IPCC drainage EF row is missing.

The DoesNotExist branches used `filter(...)` as a boolean, which is always truthy, so a missing
row raised "Please provide tier 2 values" even when every tier 2 value was supplied.

Run with:
    python manage.py test api.tests.test_organic_soil_missing_ef_t2 --keepdb
"""

from django.test import TestCase

import api.models as models
import ipcc.models as ipcc_models
from api.calculators import OrganicSoilCalculator

SCENARIOS = ("start", "w", "wo")
ONSITE_GASES = ("co2", "ch4", "n2o")
OFFSITE_GASES = ("doc", "ch4")


class OrganicSoilMissingDrainageEfTestCase(TestCase):
    fixtures = [
        "region", "ipccregion", "gleamregion", "country", "moisture", "climate", "soiltype", "foresttype",
        "moduletype", "landusetype", "peattype", "sitelocationtype", "statustype", "changerate",
        "globalwarmingpotential", "organicsoilgefemissionfactor", "organicsoildrainageemissionfactor",
        "organicsoilrewettingemissionfactor", "peatextractionemissionfactor", "peatextractionconversionfactor",
    ]

    def setUp(self):
        climate = models.Climate.objects.get(name_en="Boreal")
        moisture = climate.moistures.get(name_en="Dry")
        peat_type = models.PeatType.objects.get(name_en="Nutrient Rich")
        user = models.CustomUser.objects.create_user(email="organic-soil-t2@example.com", password="x")
        project = models.Project.objects.create(
            owner=user, name="Organic soil t2", country=models.Country.objects.filter(region__isnull=False).first(),
            climate=climate, moisture=moisture,
            soil_type=models.SoilType.objects.filter(active=True).first(),
            gw_potential=ipcc_models.GlobalWarmingPotential.objects.first(),
            start_year_of_activities=2024, implementation_years=10, last_year_of_accounting=2040,
        )
        activity = models.Activity.objects.create(project=project, name="Organic soil t2")
        annual = models.ModuleType.objects.get(class_name="AnnualCropland")
        forest = models.ModuleType.objects.get(class_name="ForestManagement")
        luc = models.LandUseChange.objects.create(
            activity=activity, area=100, module_type_start=annual, module_type_w=forest, module_type_wo=annual,
        )
        self.organic_soil = models.OrganicSoil.objects.create(
            activity=activity, peat_type=peat_type, land_use_change=luc,
            drainage_area_start=50, drainage_area_w=20, drainage_area_wo=60,
            ditches_area_start=5, ditches_area_w=2, ditches_area_wo=6,
        )
        self.drainage_rows = ipcc_models.OrganicSoilDrainageEmissionFactor.objects.filter(
            climate=climate, moisture=moisture, peat_type=peat_type, module_type__in=[annual, forest],
        )
        self.scenario_module_type = {"start": annual, "w": forest, "wo": annual}
        self.assertEqual(self.drainage_rows.count(), 4, "fixture should have on/off-site rows for both module types")

    def fill_t2_from_ipcc_rows(self):
        """Copy the IPCC drainage EFs into the tier 2 fields so results must match the tier 1 run."""
        for scenario, module_type in self.scenario_module_type.items():
            rows = self.drainage_rows.filter(module_type=module_type)
            onsite = rows.get(site_location_type__name="On-Site")
            offsite = rows.get(site_location_type__name="Off-Site")
            for gas in ONSITE_GASES:
                setattr(self.organic_soil, f"onsite_{gas}_drainage_t2_{scenario}", getattr(onsite, gas))
            for gas in OFFSITE_GASES:
                setattr(self.organic_soil, f"offsite_{gas}_drainage_t2_{scenario}", getattr(offsite, gas))
        self.organic_soil.save()

    def test_missing_row_with_all_t2_does_not_raise(self):
        self.fill_t2_from_ipcc_rows()
        self.drainage_rows.delete()

        try:
            OrganicSoilCalculator(self.organic_soil).get_defaults(calculate=False)
        except ValueError as e:
            self.fail(f"get_defaults raised with every tier 2 value supplied: {e}")

    def test_missing_row_with_one_t2_missing_raises(self):
        self.fill_t2_from_ipcc_rows()
        self.drainage_rows.delete()
        self.organic_soil.onsite_n2o_drainage_t2_w = None
        self.organic_soil.save()

        with self.assertRaisesMessage(ValueError, "Could not find EF On-Site Drainage W"):
            OrganicSoilCalculator(self.organic_soil).get_defaults(calculate=False)

    def test_missing_row_with_t2_matches_tier_1_results(self):
        tier_1 = OrganicSoilCalculator(self.organic_soil)
        tier_1.calculate()

        self.fill_t2_from_ipcc_rows()
        self.drainage_rows.delete()
        tier_2 = OrganicSoilCalculator(self.organic_soil)
        tier_2.calculate()

        self.assertNotEqual(tier_1.organic_soil_math_w.result.compute_balance(), 0)
        self.assertEqual(tier_2.organic_soil_math_w.result.to_dict(), tier_1.organic_soil_math_w.result.to_dict())
        self.assertEqual(tier_2.organic_soil_math_wo.result.to_dict(), tier_1.organic_soil_math_wo.result.to_dict())
