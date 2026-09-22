"""Regression tests for the OrganicSoil (inlands) drainage inventory.

Covers the defect where every ready OrganicSoil module raised
`TypeError: unsupported operand type(s) for +: 'int' and 'list'`.

`AnnexedModule.calculate_drainage_emissions` wrote the per-year cumulative
*series* returned by `compute_yearly_or_half_year_cumulative(...,
interim_values=True)` into the scalar `value` slot of
`InventoryPerGasPerActivity`. Nothing failed at that point: the break happened
three frames later in `Inventory.to_total()`, which sums those values against an
int 0 seed. The ACTIVITY_GAS breakdown did not even raise, it passed the list
straight into the response and cache JSON.

The correct value is the baseline (start-year) scalar, as the peat-extraction
block in the same file and every other producer in math_model already do. Note
that `total_x[0]` is NOT that value: with `interim_values=True` element 0 is the
mean of year 0 and year 1. The expected numbers below are therefore derived from
the IPCC formula (EF x area x conversion), not copied from the implementation.

These tests need Django's app registry but no database: `AnnexedModule` is a
plain dataclass and nothing here touches the ORM.
"""

import dataclasses
import os
import unittest

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
os.environ.setdefault("DJANGO_DEBUG", "True")
django.setup()

from math_model.no_time_dependency_final.general_functions import (  # noqa: E402
    compute_yearly_or_half_year_cumulative,
)
from math_model.no_time_dependency_final.ghg_emissions_classes import (  # noqa: E402
    ActivityTypes,
    BreakdownTypes,
    GasTypes,
)
from math_model.no_time_dependency_final.ghg_inventory_class import (  # noqa: E402
    Inventory,
    InventoryPerGasPerActivity,
)
from math_model.no_time_dependency_final.inlands import AnnexedModule  # noqa: E402

METHANE_CONSTANT = 28.0
NITROUS_CONSTANT = 265.0

EF_CO2 = 7.9
EF_DOC = 0.31
EF_CH4_ONSITE = 3.0
EF_CH4_OFFSITE = 500.0
EF_N2O = 13.0


def _organic_soil(area_drained_start=100.0, percentage_ditches_start=0.25, **overrides) -> AnnexedModule:
    """Build an AnnexedModule with only the drainage inputs under test set.

    Every other field is zeroed and every tier-2 override is None, so the
    reference emission factors are the ones that apply. Fields are enumerated
    from the dataclass rather than listed, so a new field cannot silently make
    this fixture stale.
    """
    kwargs = {}
    for f in dataclasses.fields(AnnexedModule):
        kwargs[f.name] = None if "tier_2" in f.name else 0.0

    kwargs.update(
        implementation_time=5,
        capitalization_time=5,
        rate_type="linear",
        delay=0,
        fire_boolean_end=0,
        fire_periodicity_end=1.0,
        area_drained_start=area_drained_start,
        area_drained_end=area_drained_start,
        percentage_ditches_start=percentage_ditches_start,
        percentage_ditches_end=percentage_ditches_start,
        area_affected_by_action_end=area_drained_start,
        maximum_area_for_water_management=area_drained_start,
        methane_constant=METHANE_CONSTANT,
        nitrous_constant=NITROUS_CONSTANT,
        ef_co2_ref_drainage_initial=EF_CO2,
        ef_doc_ref_drainage_initial=EF_DOC,
        ef_ch4_onsite_ref_drainage_initial=EF_CH4_ONSITE,
        ef_ch4_offsite_ref_drainage_initial=EF_CH4_OFFSITE,
        ef_n2o_ref_drainage_initial=EF_N2O,
    )
    kwargs.update(overrides)

    module = AnnexedModule(**kwargs)
    module.calculate_emissions()
    return module


def _drainage_rows(module) -> dict:
    return {row.gas_type: row.value for row in module.inventory.emissions_by_sector_by_gas if row.activity == ActivityTypes.DRAINAGE}


class DrainageInventoryValueTests(unittest.TestCase):
    """The drainage inventory must be the baseline scalar, not the yearly series."""

    def test_every_inventory_value_is_a_number(self):
        """The exact defect: a per-year list in a scalar slot."""
        for row in _organic_soil().inventory.emissions_by_sector_by_gas:
            self.assertIsInstance(row.value, (int, float), f"{row.gas_type} / {row.activity} carries a {type(row.value).__name__}")

    def test_all_four_breakdowns_aggregate(self):
        """to_total / to_by_activity / to_by_gas all raised TypeError; to_by_activity_gas leaked the list."""
        inventory = _organic_soil().inventory

        self.assertIsInstance(inventory.breakdown(by=BreakdownTypes.TOTAL), (int, float))
        for breakdown in (BreakdownTypes.ACTIVITY, BreakdownTypes.GAS, BreakdownTypes.ACTIVITY_GAS):
            for entry in inventory.breakdown(by=breakdown):
                self.assertIsInstance(entry["value"], (int, float), f"{breakdown} leaked a {type(entry['value']).__name__}")

    def test_baseline_matches_the_ipcc_formula(self):
        """Derived oracle: EF x start-year area x conversion, computed here, not read off the implementation."""
        rows = _drainage_rows(_organic_soil())

        self.assertAlmostEqual(rows[GasTypes.CO2], EF_CO2 * 100.0 * 44 / 12)
        self.assertAlmostEqual(rows[GasTypes.DOC], EF_DOC * 100.0 * 44 / 12)
        self.assertAlmostEqual(rows[GasTypes.N2O], EF_N2O * 100.0 * 44 / 28 * NITROUS_CONSTANT / 1000)
        self.assertAlmostEqual(
            rows[GasTypes.CH4],
            EF_CH4_ONSITE * 100.0 * 0.75 * METHANE_CONSTANT / 1000 + EF_CH4_OFFSITE * 100.0 * 0.25 * METHANE_CONSTANT / 1000,
        )

    def test_baseline_is_not_the_first_interim_year(self):
        """Guards the plausible wrong fix: `total_x[0]` is the mean of year 0 and year 1, not the baseline."""
        co2_start = EF_CO2 * 100.0 * 44 / 12
        series = compute_yearly_or_half_year_cumulative(co2_start, 0.0, 5, 5, "linear", interim_values=True)

        self.assertNotAlmostEqual(series[0], co2_start, msg="fixture no longer distinguishes the two, pick different end values")
        self.assertAlmostEqual(_drainage_rows(_organic_soil(area_drained_end=0.0))[GasTypes.CO2], co2_start)

    def test_one_row_per_gas(self):
        """Onsite and offsite CH4 belong in one merged row, as DRAINAGE_PEAT already does."""
        gases = [row.gas_type for row in _organic_soil().inventory.emissions_by_sector_by_gas if row.activity == ActivityTypes.DRAINAGE]

        self.assertEqual(sorted(g.name for g in gases), ["CH4", "CO2", "DOC", "N2O"])


class DrainageInventoryBoundaryTests(unittest.TestCase):
    """Neighbours of the fixed defect's equivalence class."""

    def test_no_drained_area_gives_a_zero_baseline(self):
        for gas, value in _drainage_rows(_organic_soil(area_drained_start=0.0)).items():
            self.assertAlmostEqual(value, 0.0, msg=f"{gas} should be zero with no drained area")

    def test_no_ditches_leaves_only_onsite_methane(self):
        rows = _drainage_rows(_organic_soil(percentage_ditches_start=0.0))

        self.assertAlmostEqual(rows[GasTypes.CH4], EF_CH4_ONSITE * 100.0 * METHANE_CONSTANT / 1000)

    def test_all_ditches_leaves_only_offsite_methane(self):
        rows = _drainage_rows(_organic_soil(percentage_ditches_start=1.0))

        self.assertAlmostEqual(rows[GasTypes.CH4], EF_CH4_OFFSITE * 100.0 * METHANE_CONSTANT / 1000)


class InventoryValueGuardTests(unittest.TestCase):
    """The shared trust boundary every inventory value routes through."""

    def test_constructor_rejects_a_series(self):
        with self.assertRaises(TypeError):
            InventoryPerGasPerActivity(GasTypes.CO2, [1.0, 2.0, 3.0], ActivityTypes.DRAINAGE)

    def test_constructor_rejects_swapped_positional_arguments(self):
        """The `excel-inventory-missing-mods` shape: InventoryPerGasPerActivity(0, GasTypes.X, activity)."""
        with self.assertRaises(TypeError):
            InventoryPerGasPerActivity(0, GasTypes.CO2, ActivityTypes.DRAINAGE)

    def test_add_emission_rejects_a_series_on_the_merge_branch(self):
        """add_emission mutates an existing row in place and never reaches the constructor.

        Without the guard this still raises, but from `float + list` deep inside the
        merge, naming neither the gas nor the activity. Assert on the message so the
        test fails if the guard is removed and the useless error comes back.
        """
        inventory = Inventory()
        inventory.add_emission(GasTypes.CO2, 1.0, ActivityTypes.DRAINAGE)

        with self.assertRaises(TypeError) as caught:
            inventory.add_emission(GasTypes.CO2, [1.0, 2.0], ActivityTypes.DRAINAGE)

        self.assertIn("must be a number", str(caught.exception))

    def test_numbers_are_accepted(self):
        inventory = Inventory()
        inventory.add_emission(GasTypes.CO2, 1, ActivityTypes.DRAINAGE)
        inventory.add_emission(GasTypes.CO2, 2.5, ActivityTypes.DRAINAGE)

        self.assertAlmostEqual(inventory.breakdown(by=BreakdownTypes.TOTAL), 3.5)


if __name__ == "__main__":
    unittest.main()
