"""Comprehensive unit tests for the reports caching feature.

Covers all three dispatch branches in LandModuleReport.__post_init__ and the
standard branch in BaseModuleReport, plus parity assertions that guarantee
the cached and non-cached pipelines produce bit-identical output from
extract_emissions() and identical InventoryItem lists.

Run with:
    python manage.py test api.tests.reports.test_cache
"""
from __future__ import annotations

import logging
import unittest
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, Mock, patch

# land.py and extractors.py both use `import logging as log` (root logger).
# Suppress DEBUG-level output (e.g. "Extracting all emissions") globally so
# it doesn't pollute the test runner output.
logging.disable(logging.DEBUG)


# ===========================================================================
# Helpers shared by multiple test cases
# ===========================================================================

def _make_emissions_entry(activity, gas_type, values):
    """Build a dict-format emissions entry as stored in cached_results."""
    return {
        "activity": activity,
        "gas_type": gas_type,
        "emissions": [{"value": v} for v in values],
    }


def _make_module_mock(
    *,
    cache_valid: bool = True,
    cached_results: dict | None = None,
    cached_units: dict | None = None,
    module_type_name: str = "TestModule",
    activity_name: str = "TestActivity",
    implementation_years: int = 3,
    capitalization_years: int = 2,
):
    """Return a Mock that behaves like a CachedResultMixin-aware module."""
    module = Mock()
    module.is_cached_results_valid.return_value = cache_valid
    module.cached_results_by_activity_by_gas = cached_results
    module.cached_units_breakdown = cached_units
    module.module_type.name = module_type_name
    module.activity.name = activity_name
    module.activity.implementation_years = implementation_years
    module.activity.capitalization_years = capitalization_years
    return module


def _minimal_cached_results(duration: int = 3):
    """Return a minimal but realistic cached_results_by_activity_by_gas dict."""
    entry = {
        "activity": "Biomass",
        "gas_type": "CO2",
        "emissions": [{"value": float(i * 10)} for i in range(1, duration + 1)],
    }
    balance = {"1": entry}
    total_w = {"1": dict(entry, emissions=[{"value": float(i * 20)} for i in range(1, duration + 1)])}
    total_wo = {"1": dict(entry, emissions=[{"value": float(i * 5)} for i in range(1, duration + 1)])}
    inventory_row = {
        "activity": "Biomass",
        "gas_type": {"name": "CO2"},
        "value": 1530.4,
    }
    return {
        "balance": balance,
        "total_w": total_w,
        "total_wo": total_wo,
        "inventory": [inventory_row],
    }


def _make_result_mock(emissions_set):
    """Return a mock that behaves like api.calculators.Result when called with *args.

    api.reports.base._init_from_calculator does:
        Result(*self.result).balance.yearly_emissions_by_sector_by_gas
    so the mock is called as a constructor each time and must return an object
    with .balance/.total_w/.total_wo attributes.
    """
    result_instance = Mock()
    result_instance.balance.yearly_emissions_by_sector_by_gas = emissions_set
    result_instance.total_w.yearly_emissions_by_sector_by_gas = emissions_set
    result_instance.total_wo.yearly_emissions_by_sector_by_gas = emissions_set
    result_cls = Mock(return_value=result_instance)
    return result_cls


# ===========================================================================
# 1-6  cache.py unit tests
# ===========================================================================

class TestLoadEmissionsFromCache(unittest.TestCase):
    """Tests for cache.load_emissions_from_cache()."""

    def _call(self, module):
        from api.reports.cache import load_emissions_from_cache
        return load_emissions_from_cache(module)

    # 1
    def test_returns_none_when_cache_invalid(self):
        """load_emissions_from_cache returns None when is_cached_results_valid() is False."""
        module = _make_module_mock(
            cache_valid=False,
            cached_results=_minimal_cached_results(),
        )
        result = self._call(module)
        self.assertIsNone(result)

    # 2
    def test_returns_none_when_cached_results_is_none(self):
        """load_emissions_from_cache returns None when cached_results_by_activity_by_gas is None."""
        module = _make_module_mock(cache_valid=True, cached_results=None)
        result = self._call(module)
        self.assertIsNone(result)

    # 3
    def test_returns_cache_result_with_correct_field_mapping(self):
        """load_emissions_from_cache maps balance/total_w/total_wo keys correctly."""
        cached = _minimal_cached_results()
        module = _make_module_mock(cache_valid=True, cached_results=cached, cached_units=None)
        from api.reports.cache import CacheResult, load_emissions_from_cache
        result = load_emissions_from_cache(module)
        self.assertIsInstance(result, CacheResult)
        self.assertIs(result.balance, cached["balance"])
        self.assertIs(result.with_project, cached["total_w"])
        self.assertIs(result.without_project, cached["total_wo"])
        self.assertEqual(result.inventory, cached["inventory"])

    # 4
    def test_populates_units_breakdown_when_present(self):
        """load_emissions_from_cache populates units_breakdown_w/wo from cached_units_breakdown."""
        cached = _minimal_cached_results()
        units = {"w": [100.0, 200.0, 300.0], "wo": [50.0, 60.0, 70.0]}
        module = _make_module_mock(cache_valid=True, cached_results=cached, cached_units=units)
        from api.reports.cache import load_emissions_from_cache
        result = load_emissions_from_cache(module)
        self.assertEqual(result.units_breakdown_w, units["w"])
        self.assertEqual(result.units_breakdown_wo, units["wo"])

    def test_units_breakdown_none_when_cached_units_absent(self):
        """load_emissions_from_cache leaves units_breakdown_w/wo as None when no units cache."""
        cached = _minimal_cached_results()
        module = _make_module_mock(cache_valid=True, cached_results=cached, cached_units=None)
        from api.reports.cache import load_emissions_from_cache
        result = load_emissions_from_cache(module)
        self.assertIsNone(result.units_breakdown_w)
        self.assertIsNone(result.units_breakdown_wo)

    def test_inventory_defaults_to_empty_list_when_key_absent(self):
        """load_emissions_from_cache uses empty list when inventory key is missing."""
        cached = {
            "balance": {},
            "total_w": {},
            "total_wo": {},
            # 'inventory' key intentionally omitted
        }
        module = _make_module_mock(cache_valid=True, cached_results=cached, cached_units=None)
        from api.reports.cache import load_emissions_from_cache
        result = load_emissions_from_cache(module)
        self.assertEqual(result.inventory, [])


class TestBuildInventoryFromCache(unittest.TestCase):
    """Tests for cache.build_inventory_from_cache()."""

    def _call(self, cached_inventory, module, activity_title):
        from api.reports.cache import build_inventory_from_cache
        return build_inventory_from_cache(cached_inventory, module, activity_title)

    # 5
    def test_reconstructs_inventory_items_correctly(self):
        """build_inventory_from_cache reconstructs InventoryItem fields from dict format."""
        from api.reports.data_types import InventoryItem
        module = _make_module_mock(module_type_name="Grassland")
        cached_inventory = [
            {"activity": "Biomass", "gas_type": {"name": "CO2"}, "value": 1530.4},
            {"activity": "SOM", "gas_type": {"name": "N2O"}, "value": -88.2},
        ]
        items = self._call(cached_inventory, module, "Activity A")
        self.assertEqual(len(items), 2)

        item = items[0]
        self.assertIsInstance(item, InventoryItem)
        self.assertEqual(item.activity_name, "Activity A")
        self.assertEqual(item.module_name, "Grassland")
        self.assertEqual(item.ipcc_category, "Biomass")
        self.assertEqual(item.gas_type, "CO2")
        self.assertAlmostEqual(item.value, 1530.4)

        item2 = items[1]
        self.assertEqual(item2.ipcc_category, "SOM")
        self.assertEqual(item2.gas_type, "N2O")
        self.assertAlmostEqual(item2.value, -88.2)

    # 6
    def test_handles_missing_and_null_fields_gracefully(self):
        """build_inventory_from_cache uses fallback values for missing/null fields."""
        module = _make_module_mock(module_type_name="Cropland")
        cached_inventory = [
            # All keys missing
            {},
            # gas_type is not a dict but a plain string
            {"activity": "Fire", "gas_type": "CH4", "value": 42.0},
            # gas_type is a dict but name key absent
            {"activity": "SOM", "gas_type": {}, "value": 10.0},
            # value key absent
            {"activity": "DOM", "gas_type": {"name": "CO2"}},
        ]
        items = self._call(cached_inventory, module, "Act")
        self.assertEqual(len(items), 4)
        # All-missing entry falls back to "N/A"
        self.assertEqual(items[0].ipcc_category, "N/A")
        self.assertEqual(items[0].gas_type, "N/A")
        self.assertAlmostEqual(items[0].value, 0.0)
        # Plain-string gas_type is used as-is
        self.assertEqual(items[1].gas_type, "CH4")
        # dict with no 'name' falls back to "N/A"
        self.assertEqual(items[2].gas_type, "N/A")
        # Missing value key defaults to 0.0
        self.assertAlmostEqual(items[3].value, 0.0)

    def test_empty_cached_inventory_returns_empty_list(self):
        """build_inventory_from_cache returns an empty list for empty input."""
        module = _make_module_mock()
        items = self._call([], module, "Act")
        self.assertEqual(items, [])


# ===========================================================================
# Shared factory helpers for calculator-path reports
# ===========================================================================

def _make_fake_emissions_set(duration: int = 3):
    """Return a dict-format emissions_set that extract_emissions can parse."""
    entry = {
        "activity": "Biomass",
        "gas_type": "CO2",
        "emissions": [{"value": float(i * 10)} for i in range(1, duration + 1)],
    }
    return {"1": entry}


def _make_calculator_mock(duration: int = 3):
    """Return a mock calculator whose calculate() produces stub results."""
    calc = Mock()
    calc.calculate.return_value = ("fake_result",)
    calc.inventory = Mock()
    calc.inventory.emissions_by_sector_by_gas = []
    calc.math_w = Mock()
    calc.math_w.hectares_total = [float(i * 100) for i in range(1, duration + 1)]
    calc.math_wo = Mock()
    calc.math_wo.hectares_total = [float(i * 50) for i in range(1, duration + 1)]
    return calc


# ===========================================================================
# 7-10  BaseModuleReport dispatcher tests
# ===========================================================================

class TestBaseModuleReportDispatcher(unittest.TestCase):
    """Tests for the __post_init__ dispatch logic in BaseModuleReport."""

    def _make_report_from_cache(self, duration: int = 3):
        """Instantiate a concrete BaseModuleReport subclass via the cache path."""
        cached = _minimal_cached_results(duration)
        module = _make_module_mock(
            cache_valid=True,
            cached_results=cached,
            cached_units=None,
        )
        activity_report = Mock()
        activity_report.project_report.duration = duration

        from api.reports.base import BaseModuleReport

        @dataclass
        class ConcreteReport(BaseModuleReport):
            def compute(self):
                return None

        report = ConcreteReport(module=module, activity_report=activity_report)
        return report, cached

    def _make_report_from_calculator(self, duration: int = 3):
        """Instantiate a concrete BaseModuleReport subclass via the calculator path."""
        emissions_set = _make_fake_emissions_set(duration)
        module = _make_module_mock(
            cache_valid=False,
            cached_results=None,
        )
        activity_report = Mock()
        activity_report.project_report.duration = duration
        calc = _make_calculator_mock(duration)

        from api.reports.base import BaseModuleReport

        @dataclass
        class ConcreteReport(BaseModuleReport):
            def __post_init__(self):
                self.calculator = calc
                result_cls = _make_result_mock(emissions_set)
                with patch("api.calculators.Result", result_cls):
                    super().__post_init__()

            def compute(self):
                return None

        report = ConcreteReport(module=module, activity_report=activity_report)
        return report, emissions_set, calc

    # 7
    def test_cache_path_sets_from_cache_true_and_emissions_sets(self):
        """When load_emissions_from_cache returns a CacheResult, _from_cache=True and emissions_set* are set from cache."""
        report, cached = self._make_report_from_cache()
        self.assertTrue(report._from_cache)
        self.assertIs(report.emissions_set, cached["balance"])
        self.assertIs(report.emissions_set_w, cached["total_w"])
        self.assertIs(report.emissions_set_wo, cached["total_wo"])
        self.assertIsNotNone(report._cache_result)

    # 8
    def test_calculator_path_sets_from_cache_false(self):
        """When load_emissions_from_cache returns None, _from_cache=False and calculator path runs."""
        report, emissions_set, calc = self._make_report_from_calculator()
        self.assertFalse(report._from_cache)
        calc.calculate.assert_called_once()

    # 9
    def test_inventory_items_uses_cache_branch_when_from_cache_true(self):
        """_inventory_items_from_module uses build_inventory_from_cache when _from_cache=True."""
        report, cached = self._make_report_from_cache()
        # build_inventory_from_cache is imported locally inside _inventory_items_from_module
        # via "from .cache import build_inventory_from_cache", so we patch it at its
        # definition site (api.reports.cache) rather than at the call site.
        with patch("api.reports.cache.build_inventory_from_cache") as mock_build:
            mock_build.return_value = []
            report._inventory_items_from_module("Act")
            mock_build.assert_called_once_with(
                report._cached_inventory, report.module, "Act"
            )

    # 10
    def test_inventory_items_uses_live_inventory_when_from_cache_false(self):
        """_inventory_items_from_module reads live inventory when _from_cache=False."""
        report, emissions_set, calc = self._make_report_from_calculator()
        # Provide a minimal live inventory
        inv_item = Mock()
        inv_item.activity = Mock()
        inv_item.activity.value = "Biomass"
        inv_item.gas_type = Mock()
        inv_item.gas_type.name = "CO2"
        inv_item.value = 99.0
        report.inventory = Mock()
        report.inventory.emissions_by_sector_by_gas = [inv_item]

        items = report._inventory_items_from_module("Act")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].ipcc_category, "Biomass")
        self.assertEqual(items[0].gas_type, "CO2")
        self.assertAlmostEqual(items[0].value, 99.0)


# ===========================================================================
# 11-13  LandModuleReport.__post_init__ branch tests
# ===========================================================================

class TestLandModuleReportBranches(unittest.TestCase):
    """Tests for all three branches in LandModuleReport.__post_init__."""

    def _make_land_report(self, *, cache_valid, cached_results, cached_units, duration=3):
        """Build a minimal concrete LandModuleReport with a mock calculator."""
        module = _make_module_mock(
            cache_valid=cache_valid,
            cached_results=cached_results,
            cached_units=cached_units,
            implementation_years=duration,
            capitalization_years=0,
        )
        activity_report = Mock()
        activity_report.project_report.duration = duration
        calc = _make_calculator_mock(duration)
        emissions_set = _make_fake_emissions_set(duration)

        from api.reports.land import LandModuleReport

        @dataclass
        class ConcreteLandReport(LandModuleReport):
            def __post_init__(self):
                self.calculator = calc
                result_cls = _make_result_mock(emissions_set)
                with patch("api.calculators.Result", result_cls):
                    super().__post_init__()

            def compute(self):
                return None

        report = ConcreteLandReport(module=module, activity_report=activity_report)
        return report, calc, module

    # 11
    def test_full_cache_hit_uses_cached_units_without_calling_calculator(self):
        """Full cache hit: _from_cache=True and _units_breakdown_w/wo equal cached values; calculator not called."""
        cached = _minimal_cached_results(3)
        units = {"w": [100.0, 200.0, 300.0], "wo": [50.0, 60.0, 70.0]}
        report, calc, module = self._make_land_report(
            cache_valid=True,
            cached_results=cached,
            cached_units=units,
        )
        self.assertTrue(report._from_cache)
        self.assertEqual(report._units_breakdown_w, units["w"])
        self.assertEqual(report._units_breakdown_wo, units["wo"])
        # In the full-cache-hit path the calculator must NOT be called
        calc.calculate.assert_not_called()

    # 12
    def test_partial_cache_hit_calls_calculator_for_units(self):
        """Partial cache hit: _from_cache=True but cached_units is None -> calculator IS called for units."""
        cached = _minimal_cached_results(3)
        report, calc, module = self._make_land_report(
            cache_valid=True,
            cached_results=cached,
            cached_units=None,  # no units yet
        )
        self.assertTrue(report._from_cache)
        # Calculator must have been called to derive hectares
        calc.calculate.assert_called_once()
        # units_breakdown_w/wo must be populated from calculator.math_w/wo.hectares_total
        expected_w = [round(v, 2) for v in calc.math_w.hectares_total]
        expected_wo = [round(v, 2) for v in calc.math_wo.hectares_total]
        self.assertEqual(report._units_breakdown_w, expected_w)
        self.assertEqual(report._units_breakdown_wo, expected_wo)
        # cache_units_breakdown must be called to persist the values
        module.cache_units_breakdown.assert_called_once_with(expected_w, expected_wo)

    # 13
    def test_calculator_path_sets_units_and_caches_when_valid(self):
        """Calculator path: _from_cache=False -> calculator IS called; units set from math_w/wo; cache_units_breakdown called if cache is valid."""
        # cache_valid=True but cached_results=None forces the calculator path;
        # after calculation is_cached_results_valid() is still True, so
        # cache_units_breakdown() should be called.
        report, calc, module = self._make_land_report(
            cache_valid=True,
            cached_results=None,  # no cached emissions -> calculator path
            cached_units=None,
        )
        self.assertFalse(report._from_cache)
        calc.calculate.assert_called_once()
        expected_w = [round(v, 2) for v in calc.math_w.hectares_total]
        expected_wo = [round(v, 2) for v in calc.math_wo.hectares_total]
        self.assertEqual(report._units_breakdown_w, expected_w)
        self.assertEqual(report._units_breakdown_wo, expected_wo)
        module.cache_units_breakdown.assert_called_once_with(expected_w, expected_wo)

    def test_calculator_path_no_cache_call_when_cache_invalid(self):
        """Calculator path: cache_units_breakdown NOT called when is_cached_results_valid() is False."""
        report, calc, module = self._make_land_report(
            cache_valid=False,
            cached_results=None,
            cached_units=None,
        )
        self.assertFalse(report._from_cache)
        module.cache_units_breakdown.assert_not_called()

    def test_partial_cache_hit_falls_back_to_zeros_on_calculator_error(self):
        """Partial cache hit: _units_breakdown_w/wo fall back to zero-lists when calculator raises."""
        cached = _minimal_cached_results(3)
        duration = 3
        module = _make_module_mock(
            cache_valid=True,
            cached_results=cached,
            cached_units=None,
            implementation_years=duration,
            capitalization_years=0,
        )
        activity_report = Mock()
        activity_report.project_report.duration = duration
        emissions_set = _make_fake_emissions_set(duration)

        from api.reports.land import LandModuleReport

        @dataclass
        class FailingLandReport(LandModuleReport):
            def __post_init__(self):
                failing_calc = Mock()
                failing_calc.calculate.side_effect = RuntimeError("boom")
                self.calculator = failing_calc
                # Emissions path comes from cache; the failing_calc only runs
                # in the partial-cache-hit branch.
                result_cls = _make_result_mock(emissions_set)
                with patch("api.calculators.Result", result_cls):
                    super().__post_init__()

            def compute(self):
                return None

        # Suppress the expected warning that logs to the root logger; also
        # assert it was emitted so the fallback path remains under test.
        with patch("logging.warning") as mock_warn:
            report = FailingLandReport(module=module, activity_report=activity_report)
        mock_warn.assert_called_once()
        self.assertIn("Could not compute units_breakdown", mock_warn.call_args[0][0])
        self.assertTrue(report._from_cache)
        self.assertEqual(report._units_breakdown_w, [0.0] * duration)
        self.assertEqual(report._units_breakdown_wo, [0.0] * duration)


# ===========================================================================
# 14-16  Parity tests: cached == non-cached
# ===========================================================================

class _EmissionsSetFixture:
    """Shared fixtures that produce identical emission data in both dict form
    (for the cache path) and in a mock ORM-object form (for the calculator path).

    The two forms must produce the same output from extract_emissions() so that
    parity tests exercise a genuine equivalence.
    """

    DURATION = 4

    # Emission values per year for each entry
    BIOMASS_CO2_VALUES = [10.0, 20.0, 30.0, 40.0]
    SOIL_CO2_VALUES = [1.0, 2.0, 3.0, 4.0]

    @classmethod
    def dict_emissions_set(cls):
        """Return a dict-keyed emissions set (used by the cached path)."""
        return {
            "1": {
                "activity": "Biomass",
                "gas_type": "CO2",
                "emissions": [{"value": v} for v in cls.BIOMASS_CO2_VALUES],
            },
            "2": {
                "activity": "Soil",
                "gas_type": "CO2",
                "emissions": [{"value": v} for v in cls.SOIL_CO2_VALUES],
            },
        }

    @classmethod
    def object_emissions_set(cls):
        """Return a list-of-objects emissions set (used by the calculator path)."""
        def make_entry(activity_str, gas_str, values):
            entry = Mock()
            entry.activity = activity_str
            entry.gas_type = gas_str
            em_objs = []
            for v in values:
                em = Mock()
                em.value = v
                em_objs.append(em)
            entry.emissions = em_objs
            return entry

        return [
            make_entry("Biomass", "CO2", cls.BIOMASS_CO2_VALUES),
            make_entry("Soil", "CO2", cls.SOIL_CO2_VALUES),
        ]


class TestNonLandModuleParity(unittest.TestCase):
    """Test 14: BaseModuleReport cached vs non-cached paths produce identical extract_emissions output."""

    DURATION = _EmissionsSetFixture.DURATION

    def _build_report_via_cache(self):
        """Run __post_init__ via the cached path."""
        dict_es = _EmissionsSetFixture.dict_emissions_set()
        cached = {
            "balance": dict_es,
            "total_w": dict_es,
            "total_wo": dict_es,
            "inventory": [],
        }
        module = _make_module_mock(
            cache_valid=True,
            cached_results=cached,
            cached_units=None,
        )
        activity_report = Mock()
        activity_report.project_report.duration = self.DURATION

        from api.reports.base import BaseModuleReport

        @dataclass
        class CachedReport(BaseModuleReport):
            def compute(self):
                return None

        return CachedReport(module=module, activity_report=activity_report)

    def _build_report_via_calculator(self):
        """Run __post_init__ via the calculator path."""
        obj_es = _EmissionsSetFixture.object_emissions_set()
        module = _make_module_mock(cache_valid=False, cached_results=None)
        activity_report = Mock()
        activity_report.project_report.duration = self.DURATION

        from api.reports.base import BaseModuleReport

        @dataclass
        class CalcReport(BaseModuleReport):
            def __post_init__(self):
                self.calculator = Mock()
                self.calculator.calculate.return_value = ("stub",)
                self.calculator.inventory = None
                result_cls = _make_result_mock(obj_es)
                with patch("api.calculators.Result", result_cls):
                    super().__post_init__()

            def compute(self):
                return None

        return CalcReport(module=module, activity_report=activity_report)

    # 14
    def test_emissions_sets_produce_identical_extract_emissions_output(self):
        """Cached and non-cached BaseModuleReport produce identical extract_emissions() results."""
        from api.reports.extractors import extract_emissions

        cached_report = self._build_report_via_cache()
        calc_report = self._build_report_via_calculator()

        for attr in ("emissions_set", "emissions_set_w", "emissions_set_wo"):
            cached_vals = extract_emissions(
                getattr(cached_report, attr), duration=self.DURATION
            )
            calc_vals = extract_emissions(
                getattr(calc_report, attr), duration=self.DURATION
            )
            self.assertEqual(
                cached_vals,
                calc_vals,
                msg=f"Mismatch in {attr}: cached={cached_vals} calc={calc_vals}",
            )


class TestLandModuleParity(unittest.TestCase):
    """Test 15: LandModuleReport cached vs non-cached paths produce identical output."""

    DURATION = _EmissionsSetFixture.DURATION
    UNITS_W = [100.0, 200.0, 300.0, 400.0]
    UNITS_WO = [50.0, 60.0, 70.0, 80.0]

    def _build_land_report_via_full_cache(self):
        """LandModuleReport with full cache (emissions + units)."""
        dict_es = _EmissionsSetFixture.dict_emissions_set()
        cached = {
            "balance": dict_es,
            "total_w": dict_es,
            "total_wo": dict_es,
            "inventory": [],
        }
        units = {"w": self.UNITS_W, "wo": self.UNITS_WO}
        module = _make_module_mock(
            cache_valid=True,
            cached_results=cached,
            cached_units=units,
            implementation_years=self.DURATION,
            capitalization_years=0,
        )
        activity_report = Mock()
        activity_report.project_report.duration = self.DURATION

        from api.reports.land import LandModuleReport

        @dataclass
        class CachedLandReport(LandModuleReport):
            def __post_init__(self):
                # Calculator mock is needed for the partial-cache-hit branch guard,
                # but in the full-cache-hit path calculate() must NOT be called.
                self.calculator = Mock()
                super().__post_init__()

            def compute(self):
                return None

        return CachedLandReport(module=module, activity_report=activity_report)

    def _build_land_report_via_calculator(self):
        """LandModuleReport via full calculator path."""
        obj_es = _EmissionsSetFixture.object_emissions_set()
        module = _make_module_mock(
            cache_valid=False,
            cached_results=None,
            cached_units=None,
            implementation_years=self.DURATION,
            capitalization_years=0,
        )
        activity_report = Mock()
        activity_report.project_report.duration = self.DURATION
        units_w = self.UNITS_W
        units_wo = self.UNITS_WO

        from api.reports.land import LandModuleReport

        @dataclass
        class CalcLandReport(LandModuleReport):
            def __post_init__(self):
                calc = Mock()
                calc.calculate.return_value = ("stub",)
                calc.inventory = None
                calc.math_w = Mock()
                calc.math_w.hectares_total = units_w
                calc.math_wo = Mock()
                calc.math_wo.hectares_total = units_wo
                self.calculator = calc
                result_cls = _make_result_mock(obj_es)
                with patch("api.calculators.Result", result_cls):
                    super().__post_init__()

            def compute(self):
                return None

        return CalcLandReport(module=module, activity_report=activity_report)

    # 15
    def test_emissions_and_units_breakdowns_match_between_paths(self):
        """Cached and non-cached LandModuleReport produce identical emissions and units_breakdown_w/wo."""
        from api.reports.extractors import extract_emissions

        cached_report = self._build_land_report_via_full_cache()
        calc_report = self._build_land_report_via_calculator()

        for attr in ("emissions_set", "emissions_set_w", "emissions_set_wo"):
            cached_vals = extract_emissions(
                getattr(cached_report, attr), duration=self.DURATION
            )
            calc_vals = extract_emissions(
                getattr(calc_report, attr), duration=self.DURATION
            )
            self.assertEqual(
                cached_vals,
                calc_vals,
                msg=f"Mismatch in {attr}: cached={cached_vals} calc={calc_vals}",
            )

        self.assertEqual(
            cached_report._units_breakdown_w,
            [round(v, 2) for v in self.UNITS_W],
        )
        self.assertEqual(
            calc_report._units_breakdown_w,
            [round(v, 2) for v in self.UNITS_W],
        )
        self.assertEqual(
            cached_report._units_breakdown_wo,
            [round(v, 2) for v in self.UNITS_WO],
        )
        self.assertEqual(
            calc_report._units_breakdown_wo,
            [round(v, 2) for v in self.UNITS_WO],
        )


class TestInventoryParity(unittest.TestCase):
    """Test 16: InventoryItem lists from cached and non-cached paths are equal."""

    DURATION = 3
    ACTIVITY_TITLE = "Reforestation Activity"
    MODULE_TYPE_NAME = "ForestManagement"

    def _make_live_inventory(self):
        """Mock live inventory.emissions_by_sector_by_gas entries."""
        item = Mock()
        item.activity = Mock()
        item.activity.value = "Biomass"
        item.gas_type = Mock()
        item.gas_type.name = "CO2"
        item.value = 1530.4
        return item

    def _build_cached_report(self):
        """BaseModuleReport via cache path with a known inventory entry."""
        cached_inventory = [
            {"activity": "Biomass", "gas_type": {"name": "CO2"}, "value": 1530.4},
        ]
        cached = {
            "balance": {},
            "total_w": {},
            "total_wo": {},
            "inventory": cached_inventory,
        }
        module = _make_module_mock(
            cache_valid=True,
            cached_results=cached,
            cached_units=None,
            module_type_name=self.MODULE_TYPE_NAME,
        )
        activity_report = Mock()
        activity_report.project_report.duration = self.DURATION

        from api.reports.base import BaseModuleReport

        @dataclass
        class CachedInventoryReport(BaseModuleReport):
            def compute(self):
                return None

        return CachedInventoryReport(module=module, activity_report=activity_report)

    def _build_calc_report(self):
        """BaseModuleReport via calculator path with equivalent live inventory."""
        module = _make_module_mock(
            cache_valid=False,
            cached_results=None,
            module_type_name=self.MODULE_TYPE_NAME,
        )
        activity_report = Mock()
        activity_report.project_report.duration = self.DURATION
        live_item = self._make_live_inventory()
        empty_es = {}

        from api.reports.base import BaseModuleReport

        @dataclass
        class CalcInventoryReport(BaseModuleReport):
            def __post_init__(self):
                inv = Mock()
                inv.emissions_by_sector_by_gas = [live_item]
                calc = Mock()
                calc.calculate.return_value = ("stub",)
                calc.inventory = inv
                self.calculator = calc
                result_cls = _make_result_mock(empty_es)
                with patch("api.calculators.Result", result_cls):
                    super().__post_init__()

            def compute(self):
                return None

        return CalcInventoryReport(module=module, activity_report=activity_report)

    # 16
    def test_inventory_item_lists_are_equal_between_paths(self):
        """InventoryItem lists produced by _inventory_items_from_module are equal between cached and non-cached paths."""
        cached_report = self._build_cached_report()
        calc_report = self._build_calc_report()

        cached_items = cached_report._inventory_items_from_module(self.ACTIVITY_TITLE)
        calc_items = calc_report._inventory_items_from_module(self.ACTIVITY_TITLE)

        self.assertEqual(len(cached_items), len(calc_items))
        for ci, li in zip(cached_items, calc_items):
            self.assertEqual(ci.activity_name, li.activity_name)
            self.assertEqual(ci.module_name, li.module_name)
            self.assertEqual(ci.ipcc_category, li.ipcc_category)
            self.assertEqual(ci.gas_type, li.gas_type)
            self.assertAlmostEqual(ci.value, li.value)
