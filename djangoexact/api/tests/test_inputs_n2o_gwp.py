"""Inputs N2O follows the project's GWP set (InputReference bakes in 44/28 x 265, the AR5 value)."""

from importlib import import_module

from django.apps import apps
from django.test import TestCase

from api.calculators import InputEntryCalculator
from api.models import Activity, Climate, Country, Input, InputEntry, InputType, Moisture, SoilType
from api.models import CustomUser as User
from api.tests.factories import ActivityFactory, ProjectFactory
from ipcc.models import GlobalWarmingPotential
from math_model.no_time_dependency_final.ghg_emissions_classes import GasTypes

cache_migration = import_module("api.migrations.0299_invalidate_input_caches_project_gwp")

SYNTHETIC_N = "Synthetic N-Fertilizers Other Than Urea"
AR5 = "IPCC Fifth Assessment Report (AR5) without Climate Change Feedback"
AR6 = "IPCC Sixth Assessment Report (AR6)"
EF1_TROPICAL_WET = 0.016


def make_project(gwp, **kwargs):
    return ProjectFactory(
        owner=User.objects.get(email="testuser@example.com"),
        country=Country.objects.exclude(region=None).first(),
        gw_potential=GlobalWarmingPotential.objects.get(name=gwp),
        **kwargs,
    )


class InputsN2OGwpTestCase(TestCase):
    def n2o_start(self, gwp, **project_kwargs):
        project = make_project(
            gwp,
            climate=Climate.objects.get(name_en="Tropical"),
            moisture=Moisture.objects.get(name_en="Wet"),
            soil_type=SoilType.objects.filter(active=True).first(),
            **project_kwargs,
        )
        activity: Activity = ActivityFactory(project=project)
        entry = InputEntry.objects.create(
            parent=Input.objects.create(activity=activity),
            input_type=InputType.objects.get(name=SYNTHETIC_N),
            value_start=100.0,
            value_w=100.0,
            value_wo=100.0,
        )
        calculator = InputEntryCalculator(entry)
        calculator.calculate()
        return sum(e.value for e in calculator.math_w.inventory.emissions_by_sector_by_gas if e.gas_type == GasTypes.N2O)

    def test_ar5_unchanged(self):
        self.assertAlmostEqual(self.n2o_start(AR5), 100 * EF1_TROPICAL_WET * 44 / 28 * 265, places=6)

    def test_n2o_follows_project_gwp(self):
        self.assertAlmostEqual(self.n2o_start(AR6), 100 * EF1_TROPICAL_WET * 44 / 28 * 273, places=6)

    def test_n2o_follows_tier_2_gwp_override(self):
        self.assertAlmostEqual(self.n2o_start(AR5, gwp_n2o_t2=300), 100 * EF1_TROPICAL_WET * 44 / 28 * 300, places=6)

    def test_cache_migration_clears_only_non_finalized_projects_off_265(self):
        def cached_input(gwp, finalized=False):
            module = Input.objects.create(activity=ActivityFactory(project=make_project(gwp, is_finalized=finalized)))
            Input.objects.filter(pk=module.pk).update(cached_results_total={"x": 1})
            return module

        stale, ar5, finalized = cached_input(AR6), cached_input(AR5), cached_input(AR6, finalized=True)
        cache_migration.invalidate_input_caches(apps, None)

        def cached(module):
            return Input.objects.get(pk=module.pk).cached_results_total

        self.assertIsNone(cached(stale))
        self.assertEqual(cached(ar5), {"x": 1})
        self.assertEqual(cached(finalized), {"x": 1})
