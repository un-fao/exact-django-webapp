"""IPCC 2019 fertiliser N forms and sewage sludge (ipcc/0068), ported from NEXT's NUTRIENT module.

Expected values are worked by hand from the 2019 Refinement, Vol. 4, Ch. 11,
independently of the migration's own tables:
    Eq. 11.1  direct:          N x EF1
    Eq. 11.9  volatilisation:  N x Frac_GAS x EF4
    Eq. 11.10 leaching:        N x Frac_LEACH x EF5
    N2O = N2O-N x 44/28, in tCO2-eq x the project's N2O GWP (265 under AR5).
"""

from importlib import import_module

from django.apps import apps
from django.test import TestCase

from api.calculators import InputEntryCalculator
from api.models import Activity, Climate, Country, Input, InputEntry, InputType, Moisture, SoilType
from api.models import CustomUser as User
from api.tests.factories import ActivityFactory, ProjectFactory
from ipcc.models import GlobalWarmingPotential, InputEmissionFactor, InputReference
from math_model.no_time_dependency_final.ghg_emissions_classes import GasTypes

migration = import_module("ipcc.migrations.0068_fertilizer_n_forms_ipcc_2019")
cache_migration = import_module("ipcc.migrations.0069_invalidate_input_caches_project_gwp")

N2O_TO_CO2E = 44 / 28 * 265
AR5 = "IPCC Fifth Assessment Report (AR5) without Climate Change Feedback"
AR6 = "IPCC Sixth Assessment Report (AR6)"

# Hand-worked kg N2O-N per kg N: EF1 + Frac_GAS x EF4 + Frac_LEACH x EF5.
# Wet: EF1 synthetic 0.016 / other 0.006, EF4 0.014, Frac_LEACH 0.24, EF5 0.011.
# Dry: EF1 0.005, EF4 0.005, Frac_LEACH 0.
EXPECTED = {
    "Synthetic N, Unspecified Form (IPCC 2019)": {"wet": 0.016 + 0.11 * 0.014 + 0.00264, "dry": 0.005 + 0.11 * 0.005},
    "Urea (IPCC 2019)": {"wet": 0.016 + 0.15 * 0.014 + 0.00264, "dry": 0.005 + 0.15 * 0.005},
    "Ammonium-Based N (IPCC 2019)": {"wet": 0.016 + 0.08 * 0.014 + 0.00264, "dry": 0.005 + 0.08 * 0.005},
    "Nitrate-Based N (IPCC 2019)": {"wet": 0.016 + 0.01 * 0.014 + 0.00264, "dry": 0.005 + 0.01 * 0.005},
    "Ammonium Nitrate-Based N (IPCC 2019)": {"wet": 0.016 + 0.05 * 0.014 + 0.00264, "dry": 0.005 + 0.05 * 0.005},
    "Sewage Sludge (IPCC 2019)": {"wet": 0.006 + 0.21 * 0.014 + 0.00264, "dry": 0.005 + 0.21 * 0.005},
}

# (climate, moisture) -> IPCC wetness. Moist counts as wet (Table 11.1 footnote).
CLIMATES = {
    ("Tropical", "Wet"): "wet",
    ("Tropical", "Moist"): "wet",
    ("Cool Temperate", "Moist"): "wet",
    ("Tropical", "Dry"): "dry",
    ("Warm Temperate", "Dry"): "dry",
}


def ef_for(type_name, climate, moisture):
    return InputEmissionFactor.objects.get(input_type__name=type_name, climate__name_en=climate, moisture__name_en=moisture)


class FertilizerNFormsTestCase(TestCase):
    def entry_n2o_start(self, type_name, climate, moisture, value=100.0, gwp=AR5):
        project = ProjectFactory(
            owner=User.objects.get(email="testuser@example.com"),
            climate=Climate.objects.get(name_en=climate),
            moisture=Moisture.objects.get(name_en=moisture),
            country=Country.objects.exclude(region=None).first(),
            soil_type=SoilType.objects.filter(active=True).first(),
            gw_potential=GlobalWarmingPotential.objects.get(name=gwp),
        )
        activity: Activity = ActivityFactory(project=project)
        entry = InputEntry.objects.create(
            parent=Input.objects.create(activity=activity),
            input_type=InputType.objects.get(name=type_name),
            value_start=value,
            value_w=value,
            value_wo=value,
        )
        calculator = InputEntryCalculator(entry)
        calculator.calculate()
        return sum(e.value for e in calculator.math_w.inventory.emissions_by_sector_by_gas if e.gas_type == GasTypes.N2O)

    def test_rows_exist_for_every_climate_of_the_generic_type(self):
        generic_rows = InputEmissionFactor.objects.filter(input_type__name=migration.SYNTHETIC_N).count()
        for type_name in EXPECTED:
            self.assertEqual(InputEmissionFactor.objects.filter(input_type__name=type_name).count(), generic_rows, type_name)
            self.assertTrue(InputReference.objects.filter(input_type__name=type_name).exists(), type_name)

    def test_combined_factor_matches_equations_11_1_11_9_11_10(self):
        for type_name, by_wetness in EXPECTED.items():
            for (climate, moisture), wetness in CLIMATES.items():
                with self.subTest(type_name=type_name, climate=climate, moisture=moisture):
                    self.assertAlmostEqual(ef_for(type_name, climate, moisture).n2o_value, by_wetness[wetness], places=9)

    def test_calculator_n2o_per_form(self):
        for type_name, by_wetness in EXPECTED.items():
            for (climate, moisture), wetness in (
                (("Tropical", "Wet"), "wet"),
                (("Warm Temperate", "Dry"), "dry"),
            ):
                # Urea is entered in t urea, 46.7 % N.
                n = 100.0 * (0.467 if type_name.startswith("Urea") else 1)
                with self.subTest(type_name=type_name, climate=climate):
                    self.assertAlmostEqual(self.entry_n2o_start(type_name, climate, moisture), n * by_wetness[wetness] * N2O_TO_CO2E, places=6)

    def test_urea_keeps_co2_and_production_factors(self):
        new, old = ef_for("Urea (IPCC 2019)", "Tropical", "Wet"), ef_for("Urea", "Tropical", "Wet")
        self.assertEqual((new.co2_value, new.co2_eq_value), (old.co2_value, old.co2_eq_value))
        self.assertTrue(InputType.objects.get(name="Urea (IPCC 2019)").has_co2_emissions)

    def test_synthetic_forms_use_generic_production_factor(self):
        generic = ef_for(migration.SYNTHETIC_N, "Tropical", "Wet").co2_eq_value
        self.assertEqual(ef_for("Nitrate-Based N (IPCC 2019)", "Tropical", "Wet").co2_eq_value, generic)
        self.assertIsNone(ef_for("Sewage Sludge (IPCC 2019)", "Tropical", "Wet").co2_eq_value)

    def test_existing_types_unchanged(self):
        self.assertEqual(ef_for(migration.SYNTHETIC_N, "Tropical", "Wet").n2o_value, 0.016)
        self.assertEqual(ef_for(migration.SYNTHETIC_N, "Cool Temperate", "Moist").n2o_value, 0.0105)
        self.assertEqual(ef_for("Sewage", "Tropical", "Wet").n2o_value, 0.006)
        self.assertEqual(ef_for("Urea", "Tropical", "Dry").n2o_value, 0.005)
        self.assertAlmostEqual(self.entry_n2o_start(migration.SYNTHETIC_N, "Tropical", "Wet"), 100 * 0.016 * N2O_TO_CO2E, places=6)
        self.assertAlmostEqual(self.entry_n2o_start("Sewage", "Tropical", "Wet"), 100 * 0.006 * N2O_TO_CO2E, places=6)

    def test_n2o_follows_project_gwp(self):
        n2o = self.entry_n2o_start(migration.SYNTHETIC_N, "Tropical", "Wet", gwp=AR6)
        self.assertAlmostEqual(n2o, 100 * 0.016 * 44 / 28 * 273, places=6)

    def test_cache_migration_clears_only_open_projects_off_265(self):
        def cached_input(gwp, finalized=False):
            project = ProjectFactory(
                owner=User.objects.get(email="testuser@example.com"),
                country=Country.objects.exclude(region=None).first(),
                gw_potential=GlobalWarmingPotential.objects.get(name=gwp),
                is_finalized=finalized,
            )
            module = Input.objects.create(activity=ActivityFactory(project=project))
            Input.objects.filter(pk=module.pk).update(cached_results_total={"x": 1})
            return module

        stale, ar5, finalized = cached_input(AR6), cached_input(AR5), cached_input(AR6, finalized=True)
        cache_migration.invalidate_input_caches(apps, None)
        cached = lambda m: Input.objects.get(pk=m.pk).cached_results_total  # noqa: E731
        self.assertIsNone(cached(stale))
        self.assertEqual(cached(ar5), {"x": 1})
        self.assertEqual(cached(finalized), {"x": 1})

    def test_migration_is_idempotent(self):
        before = InputEmissionFactor.objects.count(), InputType.objects.count()
        migration.add_n_forms(apps, None)
        self.assertEqual((InputEmissionFactor.objects.count(), InputType.objects.count()), before)
