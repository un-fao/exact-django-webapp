"""Tests for utilities.find_organic_soil_parent_module.

The lookup must return the land module that owns the organic soil (via its
`organic_soil` FK) and, when no module owns it, fall back deterministically so
Postgres (online) and SQLite (offline tool) pick the same parent.

Objects are built with the ORM instead of api.tests.factories: that module runs
reference-data queries at import time, so importing it needs a seeded database.
"""

from django.test import TestCase

from api.models import Activity, ChangeRate, Country, CustomUser, Grassland, LandUseType, ModuleType, OrganicSoil, PerennialCropland, Project
from api.utilities import find_organic_soil_parent_module
from ipcc.models import GlobalWarmingPotential


class FindOrganicSoilParentModuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Created in this order so pk order is grassland < perennial < organic soil.
        # SQLite returns the M2M rows by moduletype_id, so Grassland comes first there.
        cls.grassland_type = ModuleType.objects.create(name="parent-lookup Grassland", class_name="Grassland", is_luc=True)
        cls.perennial_type = ModuleType.objects.create(name="parent-lookup Perennial", class_name="PerennialCropland", is_luc=True)
        cls.organic_soil_type = ModuleType.objects.create(name="parent-lookup OrganicSoil", class_name="OrganicSoil")

        # Activity.save() get_or_creates this row by name only, which violates the NOT NULL on value.
        ChangeRate.objects.create(name="linear", value=1)
        # Grassland.save() and OrganicSoil.save() look these up by name_en.
        LandUseType.objects.create(name_en="Grassland")
        LandUseType.objects.create(name_en="Organic Soil")
        user = CustomUser.objects.create(email="parent-lookup@example.com")
        country = Country.objects.create(name="parent-lookup country")
        gwp = GlobalWarmingPotential.objects.create(name="parent-lookup gwp", co2=1, ch4=28, n2o=265)
        cls.project = Project.objects.create(
            owner=user,
            name="parent-lookup",
            country=country,
            gw_potential=gwp,
            implementation_years=5,
            start_year_of_activities=2024,
            last_year_of_accounting=2050,
        )

    def setUp(self):
        self.activity = Activity.objects.create(project=self.project, name="activity")
        self.soil = OrganicSoil.objects.create(activity=self.activity)

    def add_types(self, *module_types):
        for mt in module_types:
            self.activity.module_types.add(mt)
        self.activity.module_types.add(self.organic_soil_type)

    def test_returns_owner_of_second_luc_type(self):
        self.add_types(self.grassland_type, self.perennial_type)
        Grassland.objects.create(activity=self.activity)
        owner = PerennialCropland.objects.create(activity=self.activity, organic_soil=self.soil)

        self.assertEqual(find_organic_soil_parent_module(self.soil), (owner, self.perennial_type))

    def test_returns_owner_that_is_not_first_module_of_its_type(self):
        self.add_types(self.perennial_type)
        PerennialCropland.objects.create(activity=self.activity)
        owner = PerennialCropland.objects.create(activity=self.activity, organic_soil=self.soil)

        self.assertEqual(find_organic_soil_parent_module(self.soil), (owner, self.perennial_type))

    def test_without_owner_falls_back_to_first_luc_type_by_insertion_order(self):
        # Inserted Perennial first although Grassland has the lower pk.
        self.add_types(self.perennial_type, self.grassland_type)
        Grassland.objects.create(activity=self.activity)
        first_perennial = PerennialCropland.objects.create(activity=self.activity)
        PerennialCropland.objects.create(activity=self.activity)

        self.assertEqual(find_organic_soil_parent_module(self.soil), (first_perennial, self.perennial_type))

    def test_raises_when_no_parent(self):
        self.activity.module_types.add(self.organic_soil_type)

        with self.assertRaises(ValueError):
            find_organic_soil_parent_module(self.soil)
