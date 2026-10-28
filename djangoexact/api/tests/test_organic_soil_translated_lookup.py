"""OrganicSoilCalculator must find its IPCC emission factors whatever language is active.

ModuleType.name is translated by django-modeltranslation, but the ipcc lookups filter on the
English base column. Building `module_type__name=` from `.name` broke every Forest Management
organic soil in fr/es/ru ("Could not find EF On-Site Drainage Start for Gestion forestiere").

Run with:
    python manage.py test api.tests.test_organic_soil_translated_lookup --keepdb
"""

from django.test import TestCase
from django.utils.translation import override

import api.models as models
import ipcc.models as ipcc_models
from api.calculators import OrganicSoilCalculator


class OrganicSoilTranslatedLookupTestCase(TestCase):
    fixtures = [
        "region", "ipccregion", "gleamregion", "country", "moisture", "climate", "soiltype", "foresttype",
        "moduletype", "landusetype", "peattype", "sitelocationtype", "statustype", "changerate",
        "globalwarmingpotential", "organicsoilgefemissionfactor", "organicsoildrainageemissionfactor",
        "organicsoilrewettingemissionfactor", "peatextractionemissionfactor", "peatextractionconversionfactor",
    ]

    def setUp(self):
        # Boreal / Dry / Nutrient Rich has a full EF set for Forest Management and Annual Cropland.
        climate = models.Climate.objects.get(name_en="Boreal")
        user = models.CustomUser.objects.create_user(email="organic-soil-i18n@example.com", password="x")
        project = models.Project.objects.create(
            owner=user, name="Organic soil i18n", country=models.Country.objects.filter(region__isnull=False).first(),
            climate=climate, moisture=climate.moistures.get(name_en="Dry"),
            soil_type=models.SoilType.objects.filter(active=True).first(),
            gw_potential=ipcc_models.GlobalWarmingPotential.objects.first(),
            start_year_of_activities=2024, implementation_years=10, last_year_of_accounting=2040,
        )
        self.activity = models.Activity.objects.create(project=project, name="Organic soil i18n")
        self.forest_management = models.ModuleType.objects.get(class_name="ForestManagement")
        self.annual_cropland = models.ModuleType.objects.get(class_name="AnnualCropland")
        self.organic_soil = models.OrganicSoil.objects.create(
            activity=self.activity, peat_type=models.PeatType.objects.get(name_en="Nutrient Rich"),
        )

    def assert_defaults_load_in_french(self):
        with override("fr"):
            self.assertNotEqual(self.forest_management.name, self.forest_management.name_en)
            try:
                OrganicSoilCalculator(self.organic_soil).get_defaults(calculate=False)
            except ValueError as e:
                self.fail(f"get_defaults raised under fr: {e}")

    def test_luc_forest_management_defaults_load_in_french(self):
        self.organic_soil.land_use_change = models.LandUseChange.objects.create(
            activity=self.activity, area=100, module_type_start=self.annual_cropland,
            module_type_w=self.forest_management, module_type_wo=self.forest_management,
        )
        self.organic_soil.save()

        self.assert_defaults_load_in_french()

    def test_forest_management_parent_defaults_load_in_french(self):
        self.activity.module_types.add(self.forest_management)
        models.ForestManagement.objects.create(activity=self.activity, area=100, organic_soil=self.organic_soil)

        self.assert_defaults_load_in_french()
