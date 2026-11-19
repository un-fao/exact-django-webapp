"""Transport and Processing Results rows follow the entries' current numbers, not their stale cache.

An entry's cache columns are written only by its own results endpoint, and project or activity
edits invalidate module caches only, never submodule ones. So after, for example, a project GWP
change the entry cache still holds the old numbers while the module total is recalculated.

Run with:
    python manage.py test api.tests.reports.test_value_chain_entry_rows
"""

from django.test import TestCase

import api.calculators as calculators
import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils
from api.models import FuelType, Group, ModuleType, Project, ProcessingEntry, TransportEntry
from api.reports import compute_project_result
from api.reports.cache import submodule_emission_sets
from api.reports.extractors import extract_emissions
from api.services import finalization
from api.tests.factories import (
    ActivityFactory,
    ProcessingEntryFactory,
    ProcessingFactory,
    TransportEntryFactory,
    TransportFactory,
    UserFactory,
)
from api.tests.test_finalized_results_frozen import calculable_project
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes

FUEL = math_utils.ActivityTypes.FUEL
# A combustion fuel: the factories may pick Electricity or Renewable, which emit no CH4 or N2O to move.
DIESEL = "Gasoil/Diesel Oil"
FUEL_ROWS = {
    "CO2 from fuel combustion": math_utils.GasTypes.CO2,
    "CH4 from fuel combustion": math_utils.GasTypes.CH4,
    "N2O from fuel combustion": math_utils.GasTypes.N2O,
}


class ValueChainEntryRowsTestCase(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        self.project = calculable_project(UserFactory(email="value-chain-rows@example.com"))
        self.activity = ActivityFactory(project=self.project, name="Value chain")

    def add_module(self, class_name, module_factory, entry_factory):
        self.activity.module_types.add(ModuleType.objects.get(class_name=class_name))
        module = module_factory(activity=self.activity)
        diesel = FuelType.objects.get(name=DIESEL, fuel_use_type__name__icontains="Stationary")
        return entry_factory(parent=module, name=f"{class_name} entry",
                             fuel_type_start=diesel, fuel_type_w=diesel, fuel_type_wo=diesel)

    def cache_entry_then_change_project_gwp(self, entry_model, entry):
        finalization.module_results(entry_model.objects.get(pk=entry.pk), BreakdownTypes.ACTIVITY_GAS)
        project = Project.objects.get(pk=self.project.pk)
        gwp = project.gwp
        project.gwp_ch4_t2, project.gwp_n2o_t2 = gwp.ch4 * 10, gwp.n2o * 10
        project.save()
        stale = entry_model.objects.get(pk=entry.pk)
        self.assertIsNotNone(stale.cached_results_by_activity_by_gas, "the edit must leave the entry cache in place")
        return stale

    def assert_fuel_rows_match_fresh_entry(self, class_name, entry_model, entry, calculator_class):
        stale = self.cache_entry_then_change_project_gwp(entry_model, entry)

        result = compute_project_result(Project.objects.get(pk=self.project.pk))

        fresh = submodule_emission_sets(entry_model.objects.get(pk=entry.pk), calculator_class)["balance"]
        stale_n2o = extract_emissions(stale.cached_results_by_activity_by_gas["balance"], FUEL, math_utils.GasTypes.N2O,
                                      duration=result.duration)
        fresh_n2o = extract_emissions(fresh, FUEL, math_utils.GasTypes.N2O, duration=result.duration)
        self.assertNotEqual(stale_n2o, fresh_n2o, "the GWP change must move the entry numbers")

        module_result = next(m for a in result.activity_results for m in a.module_results
                             if m.title == ModuleType.objects.get(class_name=class_name).name)
        rows = {row.label: row.yearly_values for row in module_result.result_rows}
        for label, gas in FUEL_ROWS.items():
            with self.subTest(row=label):
                self.assertEqual(rows[label], extract_emissions(fresh, FUEL, gas, duration=result.duration))

    def test_transport_rows_ignore_a_stale_entry_cache(self):
        entry = self.add_module("Transport", TransportFactory, TransportEntryFactory)
        self.assert_fuel_rows_match_fresh_entry("Transport", TransportEntry, entry, calculators.TransportEntryCalculator)

    def test_processing_rows_ignore_a_stale_entry_cache(self):
        entry = self.add_module("Processing", ProcessingFactory, ProcessingEntryFactory)
        self.assert_fuel_rows_match_fresh_entry("Processing", ProcessingEntry, entry, calculators.ProcessingEntryCalculator)
