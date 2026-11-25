"""Database-free tests for the GHG Protocol scope catalog in api.scopes.

Sources are stand-in classes named like the models, because rules key on the Python class name only.
"""

from types import SimpleNamespace
from unittest import mock

from django.apps import apps
from django.test import SimpleTestCase

from api import scopes
from api.models import ValueChainSubmodule
from api.scopes import CLASS_OVERRIDES, DEFAULT_RULES, NEVER_EMITTED_ACTIVITIES, Scope, ScopeRule, scope_rule_for
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes as A
from math_model.no_time_dependency_final.ghg_emissions_classes import GasTypes as G

S1, S2, S3, OUTSIDE = Scope.SCOPE_1, Scope.SCOPE_2, Scope.SCOPE_3, Scope.OUTSIDE_SCOPES


class FuelledSource:
    """Stand-in for a model with per-scenario `fuel_type_*` foreign keys; only `name_en` is read."""

    def __init__(self, start=None, w=None, wo=None):
        self.fuel_type_start = start and SimpleNamespace(name_en=start)
        self.fuel_type_w = w and SimpleNamespace(name_en=w)
        self.fuel_type_wo = wo and SimpleNamespace(name_en=wo)


class AnnualCropland:
    pass


class ForestManagement:
    pass


class HarvestedWoodProducts:
    pass


class OrganicSoil:
    pass


class Waterbody:
    pass


class Livestock:
    pass


class SmallFishery:
    pass


class Aquaculture:
    pass


class InputEntry:
    pass


class EnergyEntry(FuelledSource):
    pass


class TransportEntry(FuelledSource):
    pass


class StorageEntry(FuelledSource):
    pass


class PackagingEntry(FuelledSource):
    pass


class IrrigationSystem:
    pass


class Building:
    pass


class SolidWaste:
    pass


class IrrigationPhase(FuelledSource):
    pass


# (behaviour, source, activity, gas, default, allowed, scope3_category, pending_review)
KEY_MAPPINGS = [
    ("soil carbon is direct", AnnualCropland(), A.SOIL_CO2_CHANGE, G.CO2, S1, (S1,), None, False),
    ("residue burning is direct", AnnualCropland(), A.RESIDUE_BURNING, G.CH4, S1, (S1,), None, False),
    ("fire on soil CO2 is direct", OrganicSoil(), A.FIRE_ON_SOIL, G.CO2, S1, (S1,), None, False),
    ("forest growth is direct", ForestManagement(), A.AGB_GROWTH, G.CO2, S1, (S1,), None, False),
    ("logging fire N2O is direct", ForestManagement(), A.LOGGING_AGB, G.N2O, S1, (S1,), None, False),
    ("wood products await review", HarvestedWoodProducts(), A.HWP_POOL, G.CO2, S1, (S1,), None, True),
    ("offsite peat may be scope 3 cat 10", OrganicSoil(), A.OFFSITE_PEAT, G.CO2, S1, (S1, S3), 10, True),
    ("waterbody methane awaits review", Waterbody(), A.COASTAL_WATERBODIES, G.CH4, S1, (S1, S3), None, True),
    ("reservoir CO2 may be scope 3 cat 3", Waterbody(), A.FLOODED_LAND_CO2, G.CO2, S1, (S1, S3), 3, True),
    ("enteric methane is direct", Livestock(), A.METHANE_ENTERIC_FERMENTATION, G.CH4, S1, (S1,), None, False),
    ("pasture manure N2O is direct", Livestock(), A.NITROUS_MANURE_MANAGEMENT_PRP, G.N2O, S1, (S1,), None, False),
    ("catch depends on vessel ownership", SmallFishery(), A.CATCH, G.CO2, S1, (S1, S3), None, False),
    ("refrigerant awaits review", SmallFishery(), A.REFRIGERANT, G.OTHER, S1, (S1, S3), None, True),
    ("ice can be any scope", SmallFishery(), A.ICE, G.OTHER, S1, (S1, S2, S3), 1, True),
    ("fish excreta is direct", Aquaculture(), A.N20_FIELD, G.N2O, S1, (S1,), None, False),
    ("input field CO2 is direct", InputEntry(), A.CO2_FIELD, G.CO2, S1, (S1,), None, False),
    ("input manufacturing is scope 3 cat 1", InputEntry(), A.CO2_EQUIVALENT_VC, G.CO2, S3, (S3,), 1, True),
    ("fuel methane is scope 1 or 3", EnergyEntry(), A.FUEL, G.CH4, S1, (S1, S3), None, False),
    ("diesel CO2 is plain scope 1", EnergyEntry("Diesel", "Diesel"), A.FUEL, G.CO2, S1, (S1, S3), None, False),
    ("wood CO2 awaits biogenic review", EnergyEntry("Wood", "Wood"), A.FUEL, G.CO2, S1, (S1, S3), None, True),
    ("charcoal CO2 awaits biogenic review", EnergyEntry(w="Charcoal"), A.FUEL, G.CO2, S1, (S1, S3), None, True),
    ("ramp from a wood start is biogenic", EnergyEntry("Wood", "Diesel"), A.FUEL, G.CO2, S1, (S1, S3), None, True),
    ("ethanol CO2 is plain scope 1", EnergyEntry(w="Ethanol (Cars)"), A.FUEL, G.CO2, S1, (S1, S3), None, False),
    ("wood methane is not biogenic CO2", EnergyEntry(w="Wood"), A.FUEL, G.CH4, S1, (S1, S3), None, False),
    ("transport fuel is scope 3 cat 4 when outsourced", TransportEntry(), A.FUEL, G.N2O, S1, (S1, S3), 4, False),
    ("transport diesel CO2 keeps cat 4", TransportEntry(w="Diesel"), A.FUEL, G.CO2, S1, (S1, S3), 4, False),
    ("transport wood CO2 keeps cat 4", TransportEntry(w="Wood"), A.FUEL, G.CO2, S1, (S1, S3), 4, True),
    ("storage fuel is scope 3 cat 4 when outsourced", StorageEntry(), A.FUEL, G.CH4, S1, (S1, S3), 4, False),
    ("energy electricity is scope 2", EnergyEntry(), A.ELECTRICITY, G.CO2, S2, (S2, S3), 3, True),
    ("aquaculture electricity is scope 2", Aquaculture(), A.ELECTRICITY, G.CO2, S2, (S2, S3), 3, True),
    ("new irrigation is capital goods", IrrigationSystem(), A.NEW_IRRIGATION, G.CO2, S3, (S3,), 2, False),
    ("construction is purchased goods", Building(), A.ROADS, G.CO2, S3, (S3,), 1, False),
    ("packaging material is purchased goods", PackagingEntry(), A.PACKAGING, G.CO2, S3, (S1, S3), 1, False),
    ("storage refrigerant is scope 1 or 3", StorageEntry(), A.STORAGE, G.CO2, S1, (S1, S3), 4, False),
    ("landfill methane is scope 3 cat 5", SolidWaste(), A.SOLID_WASTE_DISPOSAL, G.CH4, S3, (S1, S3), 5, True),
    ("incineration CO2 is scope 3 cat 5", SolidWaste(), A.WASTE_INCINERATION, G.CO2, S3, (S1, S3), 5, True),
]


class IsolatedUnassignedLog:
    """Replace the logger call and the logged-once set, so assertions ignore logging.disable() set by other test
    modules (api.tests.unit.utils) and do not depend on which test logged a key first."""

    def setUp(self):
        super().setUp()
        self.log_error = self._patch(scopes.log, "error")
        self._patch(scopes, "_logged_unassigned", set())

    def _patch(self, target, attribute, *replacement):
        patcher = mock.patch.object(target, attribute, *replacement)
        self.addCleanup(patcher.stop)
        return patcher.start()


class ScopeCatalogTests(IsolatedUnassignedLog, SimpleTestCase):
    def test_every_emitted_activity_resolves_to_a_scope_for_every_gas(self):
        # Every GasTypes member, not only today's emitted pairs, so a new gas on an existing flux cannot
        # silently land in UNASSIGNED either. The source has a fuel type because irrigation pumping needs one.
        source = IrrigationPhase(w="Diesel")
        for activity in set(A) - NEVER_EMITTED_ACTIVITIES:
            for gas in G:
                with self.subTest(activity=activity.name, gas=gas.name):
                    self.assertIsNot(scope_rule_for(source, activity, gas, "w").default, Scope.UNASSIGNED)

    def test_key_mappings(self):
        for behaviour, source, activity, gas, default, allowed, category, pending in KEY_MAPPINGS:
            with self.subTest(behaviour):
                rule = scope_rule_for(source, activity, gas, "w")
                self.assertEqual(
                    (rule.default, rule.allowed, rule.scope3_category, rule.pending_review),
                    (default, allowed, category, pending),
                )

    def test_fire_on_soil_carbon_monoxide_is_outside_the_scopes(self):
        rule = scope_rule_for(OrganicSoil(), A.FIRE_ON_SOIL, G.CO, "w")
        self.assertEqual((rule.default, rule.allowed), (OUTSIDE, (OUTSIDE,)))

    def test_rule_rejects_a_default_missing_from_allowed(self):
        with self.assertRaises(ValueError):
            ScopeRule(S2, (S1, S3))

    def test_rule_rejects_a_scope3_category_when_scope_3_is_not_allowed(self):
        with self.assertRaises(ValueError):
            ScopeRule(S1, (S1,), scope3_category=1)

    def test_cached_string_forms_resolve_like_the_enums(self):
        # The result cache stores activity by .value and gas by .name; GasTypes.OTHER is where they differ.
        for activity in set(A) - NEVER_EMITTED_ACTIVITIES:
            for gas in G:
                with self.subTest(activity=activity.name, gas=gas.name):
                    self.assertEqual(
                        scope_rule_for(EnergyEntry(), activity.value, gas.name, "w"),
                        scope_rule_for(EnergyEntry(), activity, gas, "w"),
                    )
        self.assertEqual(scope_rule_for(SmallFishery(), "Ice", "Other", "w").default, S1)

    def test_unknown_activity_is_unassigned_and_logged(self):
        rule = scope_rule_for(EnergyEntry(), "Unknown Activity", G.CO2, "w")
        self.log_error.assert_called_once()
        self.assertEqual((rule.default, rule.allowed), (Scope.UNASSIGNED, (Scope.UNASSIGNED,)))

    def test_unassigned_flux_is_logged_once_per_class_activity_and_gas(self):
        for _ in range(3):
            scope_rule_for(EnergyEntry(), "Unknown Activity", G.CO2, "w")
        scope_rule_for(EnergyEntry(), "Unknown Activity", G.CH4, "w")
        scope_rule_for(TransportEntry(), "Unknown Activity", G.CO2, "w")
        self.assertEqual(self.log_error.call_count, 3)

    def test_class_overrides_name_value_chain_entry_models(self):
        # Overrides match on the class name only, so a renamed model would silently fall back to the defaults.
        for class_name in CLASS_OVERRIDES:
            with self.subTest(class_name):
                self.assertTrue(issubclass(apps.get_model("api", class_name), ValueChainSubmodule))

    def test_never_emitted_activities_have_no_default_rule(self):
        self.assertFalse({activity for activity, _gas in DEFAULT_RULES} & NEVER_EMITTED_ACTIVITIES)

    def test_unknown_scenario_is_a_caller_error(self):
        with self.assertRaises(ValueError):
            scope_rule_for(EnergyEntry(), A.FUEL, G.CO2, "with")


class IrrigationOperationalScopeTests(IsolatedUnassignedLog, SimpleTestCase):
    def test_electric_pump_co2_is_scope_2(self):
        rule = scope_rule_for(IrrigationPhase(start="Diesel", w="Electricity"), A.IRRIGATION_OPERATIONAL, G.CO2, "w")
        self.assertEqual((rule.default, rule.allowed, rule.pending_review), (S2, (S2, S3), True))

    def test_renewable_pump_co2_is_scope_2(self):
        rule = scope_rule_for(IrrigationPhase(wo="Renewable"), A.IRRIGATION_OPERATIONAL, G.CO2, "wo")
        self.assertEqual(rule.default, S2)

    def test_pump_fuel_name_is_matched_with_the_calculators_exact_case(self):
        # IrrigationPhaseCalculator computes "RENEWABLE" as a fuel pump, so its CO2 must not be booked as Scope 2.
        rule = scope_rule_for(IrrigationPhase(wo="RENEWABLE"), A.IRRIGATION_OPERATIONAL, G.CO2, "wo")
        self.assertEqual(rule.default, S1)

    def test_diesel_pump_co2_is_scope_1(self):
        rule = scope_rule_for(IrrigationPhase(w="Diesel"), A.IRRIGATION_OPERATIONAL, G.CO2, "w")
        self.assertEqual((rule.default, rule.allowed, rule.pending_review), (S1, (S1, S3), True))

    def test_scope_follows_the_requested_scenario(self):
        source = IrrigationPhase(start="Electricity", w="Diesel")
        self.assertEqual(scope_rule_for(source, A.IRRIGATION_OPERATIONAL, G.CO2, "start").default, S2)
        self.assertEqual(scope_rule_for(source, A.IRRIGATION_OPERATIONAL, G.CO2, "w").default, S1)

    def test_missing_fuel_type_is_unassigned_like_the_calculator_computes_nothing(self):
        # IrrigationPhaseCalculator raises on a missing fuel type, so no scope can match how numbers were made.
        rule = scope_rule_for(IrrigationPhase(start="Diesel"), A.IRRIGATION_OPERATIONAL, G.CO2, "w")
        self.log_error.assert_called_once()
        self.assertEqual(rule.default, Scope.UNASSIGNED)
        self.assertIn("No fuel type for scenario w", rule.note)

    def test_electric_pump_methane_stays_scope_1(self):
        rule = scope_rule_for(IrrigationPhase(w="Electricity"), A.IRRIGATION_OPERATIONAL, G.CH4, "w")
        self.assertEqual(rule.default, S1)
