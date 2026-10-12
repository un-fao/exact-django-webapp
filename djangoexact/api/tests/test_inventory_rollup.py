"""Regression tests for the Excel report Inventory roll-up.

Covers the defect where the irrigation, inputs, energy, packaging, transport,
storage and processing module families contributed no rows at all to the Excel
report's Inventory sheet.

`BaseCalculator.inventory` used to look for a math module under a fixed list of
five attribute names and return the first hit, else an empty `Inventory()`.
Those seven families never populate any of the five: the container calculators
delegate to per-entry sub-calculators built as throwaway locals, and several
entry calculators keep their math modules under other names
(`energy_math_*`, `electricity_math_*`). Both cases fell through to the empty
`Inventory()`, so `_inventory_items_from_module` produced no rows and the
Inventory sheet rendered its "no inventory data" placeholder.

These tests need Django's app registry (api.calculators imports api.models) but
no database: the calculator under test is a stub subclass that skips
`BaseCalculator.__init__`, so nothing touches the ORM.
"""

import os
import unittest

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
os.environ.setdefault("DJANGO_DEBUG", "True")
django.setup()

import api.calculators as calculators  # noqa: E402
from math_model.no_time_dependency_final.general_functions import (  # noqa: E402
    input_single_calculation,
)
from math_model.no_time_dependency_final.ghg_emissions_classes import (  # noqa: E402
    ActivityTypes,
    GasTypes,
)
from math_model.no_time_dependency_final.ghg_inventory_class import Inventory  # noqa: E402
from math_model.no_time_dependency_final.inputs import (  # noqa: E402
    Inputs,
    NewIrrigation,
    OperationPhaseIrrigation,
)


def _inventory(*rows) -> Inventory:
    """Build an Inventory from (gas_type, value, activity) triples."""
    inventory = Inventory()
    for gas_type, value, activity in rows:
        inventory.add_emission(gas_type, value, activity)
    return inventory


class _FakeMathModule:
    """Stands in for a math_model module, which exposes `.inventory`."""

    def __init__(self, inventory: Inventory):
        self.inventory = inventory


class _StubCalculator(calculators.BaseCalculator):
    """A BaseCalculator that skips the DB-backed __init__.

    Everything under test (`inventory`, `entry_calculators`,
    `_track_entry_calculator`, `_reset_entry_calculators`) is inherited
    unchanged from BaseCalculator, so this exercises the real production code.
    """

    # The five names the old lookup knew about are always present (BaseCalculator
    # sets them to None in __init__). Declaring them here keeps the tests honest:
    # against the pre-fix implementation they produce a real empty-inventory
    # assertion failure rather than an incidental AttributeError.
    LEGACY_MATH_ATTRIBUTES = (
        "math_start",
        "math_start_w",
        "math_start_wo",
        "math_w",
        "math_wo",
    )

    def __init__(self, **math_attributes):
        self._entry_calculators = []
        for name in self.LEGACY_MATH_ATTRIBUTES:
            setattr(self, name, None)
        for name, value in math_attributes.items():
            setattr(self, name, value)

    def calculate(self, *args, **kwargs):
        return None

    def get_defaults(self, calculate=False):
        return {}


def _rows(inventory: Inventory):
    """Comparable (activity, gas, value) triples for an Inventory."""
    return sorted(
        (
            item.activity.value if item.activity else None,
            item.gas_type.name if item.gas_type else None,
            item.value,
        )
        for item in inventory.emissions_by_sector_by_gas
    )


class MathComponentGroupTests(unittest.TestCase):
    """BaseCalculator.inventory must find math modules under every name in use."""

    def test_land_style_single_math_module_is_unchanged(self):
        """A land calculator sets math_start_w only. Its rows must survive verbatim.

        This is the regression guard for the families that already worked: the
        fix must not alter what land modules contribute.
        """
        calc = _StubCalculator(
            math_start_w=_FakeMathModule(
                _inventory((GasTypes.CO2, 1530.4, ActivityTypes.BIOMASS))
            )
        )
        self.assertEqual(_rows(calc.inventory), [("Biomass", "CO2", 1530.4)])

    def test_scenario_variants_within_a_component_are_not_double_counted(self):
        """math_w and math_wo carry identical start-year rows, so take one.

        Both are built from the same `*_start` inputs, so summing them would
        report twice the baseline.
        """
        rows = ((GasTypes.CO2, 42.0, ActivityTypes.STORAGE),)
        calc = _StubCalculator(
            math_w=_FakeMathModule(_inventory(*rows)),
            math_wo=_FakeMathModule(_inventory(*rows)),
        )
        self.assertEqual(_rows(calc.inventory), [("Storage", "CO2", 42.0)])

    def test_distinct_components_are_summed(self):
        """A storage entry's refrigerant rows and its electricity rows both count."""
        calc = _StubCalculator(
            math_w=_FakeMathModule(
                _inventory((GasTypes.CO2, 10.0, ActivityTypes.STORAGE))
            ),
            electricity_math_w=_FakeMathModule(
                _inventory((GasTypes.CO2, 3.5, ActivityTypes.ELECTRICITY))
            ),
        )
        self.assertEqual(
            _rows(calc.inventory),
            [("Electricity", "CO2", 3.5), ("Storage", "CO2", 10.0)],
        )

    def test_energy_only_component_is_found(self):
        """TransportEntryCalculator sets energy_math_* and nothing else.

        Under the old five-name lookup this returned an empty inventory, which
        is why transport never reached the Inventory sheet.
        """
        calc = _StubCalculator(
            energy_math_w=_FakeMathModule(
                _inventory((GasTypes.CO2, 7.25, ActivityTypes.FUEL))
            )
        )
        self.assertEqual(_rows(calc.inventory), [("Fuel", "CO2", 7.25)])

    def test_organic_soil_and_peat_components_are_found(self):
        """OrganicSoilCalculator keeps two components, neither in the old list."""
        calc = _StubCalculator(
            organic_soil_math_w=_FakeMathModule(
                _inventory((GasTypes.CO2, 12.0, ActivityTypes.DRAINAGE))
            ),
            peat_extraction_math_w=_FakeMathModule(
                _inventory((GasTypes.CO2, 4.0, ActivityTypes.OFFSITE_PEAT))
            ),
        )
        self.assertEqual(
            _rows(calc.inventory),
            [
                ("Drainage", "CO2", 12.0),
                ("Offsite Peat Extraction", "CO2", 4.0),
            ],
        )

    def test_calculator_with_no_math_module_yields_empty_inventory(self):
        """Boundary: nothing set at all must be empty, not an error."""
        self.assertEqual(_rows(_StubCalculator().inventory), [])

    def test_every_group_name_is_a_real_attribute_somewhere(self):
        """MATH_COMPONENT_GROUPS must not drift from the calculators.

        Guards against a component being renamed in calculators.py while the
        lookup table silently keeps pointing at the dead name, which is the
        exact failure mode this table replaced.
        """
        import inspect

        source = inspect.getsource(calculators)
        for group in calculators.MATH_COMPONENT_GROUPS:
            for name in group:
                self.assertIn(
                    f"self.{name}",
                    source,
                    f"{name} is in MATH_COMPONENT_GROUPS but no calculator sets it",
                )


class EntryCalculatorRollupTests(unittest.TestCase):
    """Container calculators must roll their entry calculators' inventories up."""

    def test_container_with_no_entries_is_empty(self):
        """Boundary: zero entries."""
        container = _StubCalculator()
        container._reset_entry_calculators()
        self.assertEqual(_rows(container.inventory), [])

    def test_container_with_one_entry_takes_its_rows(self):
        """Boundary: exactly one entry."""
        container = _StubCalculator()
        container._reset_entry_calculators()
        container._entry_calculators.append(
            _StubCalculator(
                math_w=_FakeMathModule(
                    _inventory((GasTypes.N2O, 2.0, ActivityTypes.N20_FIELD))
                )
            )
        )
        self.assertEqual(_rows(container.inventory), [("N2O Field", "N2O", 2.0)])

    def test_container_sums_across_entries_merging_matching_keys(self):
        """Two entries on the same (gas, activity) must merge into one summed row."""
        container = _StubCalculator()
        container._reset_entry_calculators()
        for value in (2.0, 5.0):
            container._entry_calculators.append(
                _StubCalculator(
                    math_w=_FakeMathModule(
                        _inventory((GasTypes.CO2, value, ActivityTypes.CO2_FIELD))
                    )
                )
            )
        self.assertEqual(_rows(container.inventory), [("CO2 Field", "CO2", 7.0)])

    def test_track_entry_calculator_registers_for_rollup(self):
        """_track_entry_calculator must return the calculator and record it."""
        container = _StubCalculator()
        container._reset_entry_calculators()

        def factory(entry):
            return _StubCalculator(
                math_w=_FakeMathModule(
                    _inventory((GasTypes.CO2, entry, ActivityTypes.PACKAGING))
                )
            )

        tracked = container._track_entry_calculator(factory, 9.0)

        self.assertIs(tracked, container.entry_calculators[0])
        self.assertEqual(_rows(container.inventory), [("Packaging", "CO2", 9.0)])

    def test_reset_prevents_double_counting_when_calculate_runs_twice(self):
        """calculate() can run more than once on one instance.

        Without the reset the entries accumulate and the baseline doubles.
        """
        container = _StubCalculator()

        def factory(entry):
            return _StubCalculator(
                math_w=_FakeMathModule(
                    _inventory((GasTypes.CO2, 6.0, ActivityTypes.TRANSPORT))
                )
            )

        for _ in range(2):
            container._reset_entry_calculators()
            container._track_entry_calculator(factory, None)

        self.assertEqual(_rows(container.inventory), [("Transport", "CO2", 6.0)])

    def test_inventory_does_not_alias_the_math_modules_inventory(self):
        """The property must return a fresh object, not calculator state.

        A caller mutating the returned Inventory must not corrupt the math
        module it came from.
        """
        source = _inventory((GasTypes.CO2, 1.0, ActivityTypes.FUEL))
        calc = _StubCalculator(math_w=_FakeMathModule(source))

        returned = calc.inventory
        returned.add_emission(GasTypes.CH4, 99.0, ActivityTypes.FUEL)

        self.assertEqual(_rows(source), [("Fuel", "CO2", 1.0)])


class OperationPhaseIrrigationInventoryTests(unittest.TestCase):
    """The irrigation operational phase built malformed InventoryPerGasPerActivity.

    Args were passed as (0, GasTypes.X, activity) into a
    (gas_type, value, activity) signature, so gas_type was 0 and value was a
    GasTypes member. Invisible while nothing read the inventory; fatal once it
    is aggregated.
    """

    def _module(self) -> OperationPhaseIrrigation:
        return OperationPhaseIrrigation(
            implementation_time=5,
            capitalization_time=5,
            rate_type="linear",
            delay=0,
            ef_co2_default=0.5,
            ef_n2o_default=0.01,
            ef_ch4_default=0.02,
            average_pressure_default=2.0,
            pumping_efficiency_default=0.75,
            erh_electricity=0.0036,
            fuel_density=0.85,
            fuel_net_calorific_values=43.0,
            depth=30.0,
            units_start=100.0,
            units_end=150.0,
            transportation_loss=0.1,
            gwir=5.0,
        )

    def test_rows_carry_a_real_gas_type_and_a_numeric_value(self):
        module = self._module()
        module.calculate_emissions()

        rows = module.inventory.emissions_by_sector_by_gas
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertIsInstance(row.gas_type, GasTypes)
            self.assertIsInstance(row.value, (int, float))
            self.assertEqual(row.activity, ActivityTypes.IRRIGATION_OPERATIONAL)

        self.assertEqual(
            sorted(row.gas_type.name for row in rows), ["CH4", "CO2", "N2O"]
        )

    def test_inventory_can_be_aggregated_without_raising(self):
        """Inventory.__add__ sums values; enum values used to raise TypeError."""
        module = self._module()
        module.calculate_emissions()

        merged = Inventory() + module.inventory

        self.assertEqual(len(merged.emissions_by_sector_by_gas), 3)
        self.assertEqual(merged.to_total(), 0)

    def test_inventory_is_json_serialisable_for_the_module_cache(self):
        """save_results_to_cache persists inventory.to_dict() as JSON."""
        import json

        module = self._module()
        module.calculate_emissions()

        payload = json.dumps(module.inventory.to_dict())

        self.assertIn("Operational Phase of Irrigation", payload)


class InputSingleCalculationContractTests(unittest.TestCase):
    """`input_single_calculation` must hand back its start-year emission.

    It computed `emissions_start` internally and then discarded it, which is why
    `Inputs` had nothing to record and fell back to activity data.
    """

    def test_returns_three_values_with_the_start_year_emission_last(self):
        annual, total, emissions_start = input_single_calculation(
            100.0,  # unit_start
            200.0,  # unit_end
            0.5,  # ipcc_factor
            None,  # tier_2_factor
            2.0,  # unit_factor
            4.0,  # emissions_factor
            5,  # time_implementation
            5,  # time_capitalization
            "linear",
        )

        # 100 units * 2.0 unit_factor * 0.5 ipcc * 4.0 emissions_factor
        self.assertEqual(emissions_start, 400.0)
        self.assertEqual(total, sum(annual))

    def test_tier_2_factor_overrides_the_ipcc_factor(self):
        _, _, emissions_start = input_single_calculation(
            100.0, 200.0, 0.5, 1.5, 2.0, 4.0, 5, 5, "linear"
        )

        # tier 2 (1.5) replaces the ipcc factor (0.5): 100 * 2.0 * 1.5 * 4.0
        self.assertEqual(emissions_start, 1200.0)

    def test_start_year_emission_seeds_the_yearly_series(self):
        """The returned value must be the same seed the yearly series is built on.

        This is what makes the inventory row consistent with the Results sheet,
        and it mirrors ValueChain, which records exactly this quantity.
        """
        annual, _, emissions_start = input_single_calculation(
            100.0, 200.0, 0.5, None, 2.0, 4.0, 5, 5, "linear"
        )

        # Linear interim values average consecutive year boundaries, so the first
        # entry sits half a yearly step above the start value.
        step = (800.0 - 400.0) / 5
        self.assertAlmostEqual(annual[0], emissions_start + step / 2)


class InputsInventoryValueTests(unittest.TestCase):
    """`Inputs` wrote activity data into a column headed "Value (tCO2-eq)".

    All three rows recorded `self.unit_start` (tonnes of fertiliser, litres of
    pesticide) rather than an emission. Those rows never reached a report before
    the roll-up fix, so correcting them regresses no published number.
    """

    UNIT_START = 100.0

    def _module(self, **overrides) -> Inputs:
        kwargs = dict(
            implementation_time=5,
            capitalization_time=5,
            rate_type="linear",
            delay=0,
            unit_start=self.UNIT_START,
            unit_end=200.0,
            # 100 * 2.0 * 0.5 * 4.0 = 400.0
            ipcc_factor_co2=0.5,
            unit_factor_co2=2.0,
            emissions_factor_co2=4.0,
            # 100 * 1.0 * 0.25 * 8.0 = 200.0
            ipcc_factor_n2o=0.25,
            unit_factor_n2o=1.0,
            emissions_factor_n2o=8.0,
            # 100 * 0.5 * 2.0 * 3.0 = 300.0
            ipcc_factor_eq=2.0,
            unit_factor_eq=0.5,
            emissions_factor_eq=3.0,
        )
        kwargs.update(overrides)
        return Inputs(**kwargs)

    def test_rows_hold_start_year_emissions_not_input_quantities(self):
        module = self._module()
        module.calculate_emissions()

        self.assertEqual(
            _rows(module.inventory),
            [
                ("CO2 Equivalent VC", "CO2", 300.0),
                ("CO2 Field", "CO2", 400.0),
                ("N2O Field", "N2O", 200.0),
            ],
        )

    def test_no_row_reports_the_raw_input_quantity(self):
        """Direct guard on the defect: unit_start must not appear as a value.

        The factors are chosen so no correct emission coincides with unit_start,
        which makes this assertion bite rather than pass by luck.
        """
        module = self._module()
        module.calculate_emissions()

        values = [row.value for row in module.inventory.emissions_by_sector_by_gas]
        self.assertNotIn(self.UNIT_START, values)

    def test_tier_2_factors_are_reflected_in_the_recorded_emission(self):
        module = self._module(tier_2_factor_co2=1.5)
        module.calculate_emissions()

        co2_field = next(
            row
            for row in module.inventory.emissions_by_sector_by_gas
            if row.activity == ActivityTypes.CO2_FIELD
        )
        # 100 * 2.0 * 1.5 (tier 2, not the 0.5 ipcc default) * 4.0
        self.assertEqual(co2_field.value, 1200.0)

    def test_zero_baseline_quantity_gives_zero_emission_rows(self):
        """Boundary: nothing applied at start means no baseline emission.

        Under the old behaviour this happened to be right for the wrong reason,
        because unit_start was 0 too. It must stay right for the right one.
        """
        module = self._module(unit_start=0.0)
        module.calculate_emissions()

        self.assertEqual(
            [row.value for row in module.inventory.emissions_by_sector_by_gas],
            [0.0, 0.0, 0.0],
        )

    def test_a_gas_with_missing_factors_contributes_no_row(self):
        """Boundary: the guarded branches must stay guarded.

        A None factor skips the whole block, inventory row included, so two rows
        remain rather than three with a null.
        """
        module = self._module(emissions_factor_n2o=None)
        module.calculate_emissions()

        self.assertEqual(
            _rows(module.inventory),
            [
                ("CO2 Equivalent VC", "CO2", 300.0),
                ("CO2 Field", "CO2", 400.0),
            ],
        )


class NewIrrigationInventoryValueTests(unittest.TestCase):
    """`NewIrrigation` recorded `units_start`, which is hectares, not emissions.

    0 is recorded instead of a derived figure: total_emissions is
    ef * (units_end - units_start), a one-off embodied emission of infrastructure
    the project builds. ef * units_start would price irrigation that already
    existed before the project, a historical one-off rather than a baseline
    annual flux. Matches Roads and OperationPhaseIrrigation.
    """

    UNITS_START = 40.0

    def _module(self) -> NewIrrigation:
        return NewIrrigation(
            implementation_time=5,
            capitalization_time=5,
            rate_type="linear",
            delay=0,
            ef_ref=250.0,
            units_start=self.UNITS_START,
            units_end=100.0,
        )

    def test_records_a_zero_baseline_not_the_irrigated_area(self):
        module = self._module()
        module.calculate_emissions()

        self.assertEqual(_rows(module.inventory), [("New Irrigation", "CO2", 0)])

    def test_the_yearly_emission_series_is_untouched(self):
        """Only the inventory row changed. The Results numbers must not move.

        total_emissions stays ef * (units_end - units_start) / 1000.
        """
        module = self._module()
        module.calculate_emissions()

        self.assertAlmostEqual(module.total_emissions, 250.0 * (100.0 - 40.0) / 1000)
        self.assertAlmostEqual(sum(module.emissions_total_yearly), module.total_emissions)


if __name__ == "__main__":
    unittest.main()
