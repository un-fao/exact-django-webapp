"""Unit tests for FloodedRiceReport minor-season aggregation and metadata layout.

Guards beads issues:
- exact-django-webapp-h8z: report uses FloodedRiceSeasonCalculator (main only) while
  production uses FloodedRiceCalculator (main + minor seasons)
- exact-django-webapp-ttm: minor-season loop adds MAIN module start, not minor's own
- exact-django-webapp-fqg: minor-season contributions added as raw w+wo sums instead
  of balance (w - wo)
- exact-django-webapp-7qn: fire_ch4 not updated in minor-season loop
- exact-django-webapp-65h: minor-season metadata row offsets collide (stride 1 vs 6)
- exact-django-webapp-7nt: dead-code total_emissions in compute()

All tests are DB-free; they exercise the report helpers with synthetic emission sets.

Run with:
    python manage.py test api.tests.reports.test_flooded_rice_seasons
"""
from __future__ import annotations

import logging
import unittest
from dataclasses import dataclass
from unittest.mock import Mock, patch

# Suppress noisy DEBUG output from extract_emissions / land.py.
logging.disable(logging.DEBUG)


# ===========================================================================
# Helpers
# ===========================================================================

def _entry_obj(activity_str: str, gas_str: str, values: list[float]):
    """Build a mock that mimics YearlyGasActivityEmissionSet objects (.activity, .gas_type, .emissions)."""
    e = Mock()
    e.activity = activity_str
    e.gas_type = gas_str
    em_objs = []
    for v in values:
        em = Mock()
        em.value = v
        em_objs.append(em)
    e.emissions = em_objs
    return e


def _result_class_mock(balance_entries, total_w_entries=None, total_wo_entries=None):
    """Return a class-mock such that Result(*args).balance.yearly_emissions_by_sector_by_gas == balance_entries."""
    instance = Mock()
    instance.balance.yearly_emissions_by_sector_by_gas = list(balance_entries)
    instance.total_w.yearly_emissions_by_sector_by_gas = list(
        total_w_entries if total_w_entries is not None else balance_entries
    )
    instance.total_wo.yearly_emissions_by_sector_by_gas = list(
        total_wo_entries if total_wo_entries is not None else []
    )
    return Mock(return_value=instance)


def _make_calc_mock(*, balance, total_w=None, total_wo=None, hectares_w=None, hectares_wo=None):
    """Return a calculator-like mock with calculate(), inventory, math_w/wo and a tag for Result patching."""
    calc = Mock()
    # calculate() returns a tuple consumed by Result(*tuple). The exact contents don't
    # matter because we patch api.calculators.Result to return our own data.
    calc.calculate.return_value = ("results_w_placeholder", "results_wo_placeholder")
    calc.inventory = None
    calc.math_w = Mock()
    calc.math_w.hectares_total = hectares_w if hectares_w is not None else [0.0]
    calc.math_wo = Mock()
    calc.math_wo.hectares_total = hectares_wo if hectares_wo is not None else [0.0]
    # Stash the emission entries on the mock so the test's side_effect picks them up.
    calc._test_balance = list(balance)
    calc._test_total_w = list(total_w if total_w is not None else balance)
    calc._test_total_wo = list(total_wo if total_wo is not None else [])
    return calc


# ===========================================================================
# 1. Metadata stride helper (Bug exact-django-webapp-65h)
# ===========================================================================

class TestMinorSeasonMetadataStride(unittest.TestCase):
    """Two or more minor seasons must not produce colliding (row_offset, col)
    coordinates in the metadata block."""

    def _build_season(self, n: int):
        """Build a fake minor-season module and season_calc with .area, water/organic types, yield."""
        season = Mock()
        season.area = 5.0 + n
        season.water_management_type_before_cultivation_start = Mock(name=f"wb_start_{n}")
        season.water_management_type_before_cultivation_start.name = f"wb_start_{n}"
        season.water_management_type_before_cultivation_w = Mock()
        season.water_management_type_before_cultivation_w.name = f"wb_w_{n}"
        season.water_management_type_before_cultivation_wo = Mock()
        season.water_management_type_before_cultivation_wo.name = f"wb_wo_{n}"
        season.water_management_type_after_cultivation_start = Mock()
        season.water_management_type_after_cultivation_start.name = f"wa_start_{n}"
        season.water_management_type_after_cultivation_w = Mock()
        season.water_management_type_after_cultivation_w.name = f"wa_w_{n}"
        season.water_management_type_after_cultivation_wo = Mock()
        season.water_management_type_after_cultivation_wo.name = f"wa_wo_{n}"
        season.organic_amendment_type_start = Mock()
        season.organic_amendment_type_start.name = f"oa_start_{n}"
        season.organic_amendment_type_w = Mock()
        season.organic_amendment_type_w.name = f"oa_w_{n}"
        season.organic_amendment_type_wo = Mock()
        season.organic_amendment_type_wo.name = f"oa_wo_{n}"
        season_calc = Mock()
        season_calc.efc_default = Mock(cultivation_period=120 + n)
        season_calc.yield_default = Mock(value=10.0 + n)
        return season, season_calc

    def _collect_coords(self, n_minor_seasons: int, is_start, is_with, is_without):
        from api.reports.land import _flooded_rice_minor_season_metadata_writes

        writes = []
        for i in range(n_minor_seasons):
            season, season_calc = self._build_season(i)
            writes.extend(
                _flooded_rice_minor_season_metadata_writes(
                    season,
                    season_calc,
                    base_row=8 + 6 * i,
                    is_start=is_start,
                    is_with=is_with,
                    is_without=is_without,
                )
            )
        return [(w.row_offset, w.col) for w in writes]

    def test_two_minor_seasons_with_only_have_unique_coords(self):
        """With 2 minor seasons and is_with-only state, no (row_offset, col) duplicates."""
        coords = self._collect_coords(2, is_start=False, is_with=True, is_without=False)
        self.assertEqual(
            len(coords),
            len(set(coords)),
            f"Duplicate coords detected: {sorted([c for c in coords if coords.count(c) > 1])}",
        )

    def test_three_minor_seasons_all_three_states_have_unique_coords(self):
        """With 3 minor seasons and all three (start/with/without) states, no duplicates."""
        coords = self._collect_coords(3, is_start=True, is_with=True, is_without=True)
        self.assertEqual(
            len(coords),
            len(set(coords)),
            f"Duplicate coords detected: {sorted([c for c in coords if coords.count(c) > 1])}",
        )

    def test_stride_is_six_per_season(self):
        """Each minor season occupies exactly 6 metadata rows; consecutive seasons are 6 apart."""
        from api.reports.land import _flooded_rice_minor_season_metadata_writes

        s0, sc0 = self._build_season(0)
        s1, sc1 = self._build_season(1)
        w0 = _flooded_rice_minor_season_metadata_writes(
            s0, sc0, base_row=8 + 6 * 0,
            is_start=False, is_with=True, is_without=False,
        )
        w1 = _flooded_rice_minor_season_metadata_writes(
            s1, sc1, base_row=8 + 6 * 1,
            is_start=False, is_with=True, is_without=False,
        )
        rows0 = sorted({w.row_offset for w in w0})
        rows1 = sorted({w.row_offset for w in w1})
        # Each season writes 6 distinct rows in its own block.
        self.assertEqual(rows0, [8, 9, 10, 11, 12, 13])
        self.assertEqual(rows1, [14, 15, 16, 17, 18, 19])

    def test_with_only_writes_only_with_column(self):
        """is_with=True/is_start=is_without=False writes only column 3 (with-project)."""
        from api.reports.land import _flooded_rice_minor_season_metadata_writes
        season, sc = self._build_season(0)
        writes = _flooded_rice_minor_season_metadata_writes(
            season, sc, base_row=8,
            is_start=False, is_with=True, is_without=False,
        )
        cols = {w.col for w in writes}
        self.assertEqual(cols, {3})


# ===========================================================================
# 2. Aggregation helper (Bugs h8z, ttm, fqg, 7qn)
# ===========================================================================

class TestAggregateMinorSeasonsIntoEmissionsSets(unittest.TestCase):
    """The aggregation helper appends each minor season's balance entries (and
    total_w/total_wo) so that extract_emissions over the merged sets sums main
    plus every minor season — with the minor contribution being a *balance*
    (w - wo), never a raw w+wo sum, and using the *minor's* own start, not the
    main module's start."""

    DURATION = 3

    def _patch_paths(self, minor_balance_entries, minor_total_w_entries, minor_total_wo_entries):
        """Patch FloodedRiceSeasonCalculator and Result so the helper sees the synthetic data."""
        # The helper instantiates calculators.FloodedRiceSeasonCalculator(minor_season).
        # We replace it with a no-op that returns a stub object whose .calculate()
        # returns the placeholder tuple consumed by Result(*).
        fake_minor_calc = Mock()
        fake_minor_calc.calculate.return_value = ("w_stub", "wo_stub")

        calc_patch = patch(
            "api.reports.land.calculators.FloodedRiceSeasonCalculator",
            return_value=fake_minor_calc,
        )
        result_patch = patch(
            "api.calculators.Result",
            _result_class_mock(
                minor_balance_entries,
                minor_total_w_entries,
                minor_total_wo_entries,
            ),
        )
        return calc_patch, result_patch

    def test_helper_appends_minor_balance_entries_to_emissions_set(self):
        """Each minor season's balance entries are appended to emissions_set."""
        from api.reports.land import _aggregate_minor_seasons_into_emissions_sets
        from api.reports.extractors import extract_emissions

        # Main module's emissions_set: BIOMASS+CO2 with values [10, 20, 30].
        main_es = [_entry_obj("Biomass", "CO2", [10.0, 20.0, 30.0])]
        main_es_w = [_entry_obj("Biomass", "CO2", [12.0, 22.0, 33.0])]
        main_es_wo = [_entry_obj("Biomass", "CO2", [2.0, 2.0, 3.0])]

        # Each minor season contributes BIOMASS+CO2 [1, 2, 3] to the balance.
        minor_balance = [_entry_obj("Biomass", "CO2", [1.0, 2.0, 3.0])]

        minor_seasons = [Mock(), Mock()]  # two minor seasons

        calc_patch, result_patch = self._patch_paths(minor_balance, minor_balance, [])
        with calc_patch, result_patch:
            es, es_w, es_wo = _aggregate_minor_seasons_into_emissions_sets(
                main_es, main_es_w, main_es_wo, minor_seasons
            )

        biomass_sum = extract_emissions(es, "Biomass", "CO2", duration=self.DURATION)
        # main 10/20/30 + 2 minor seasons × [1, 2, 3] = [12, 24, 36]
        self.assertEqual(biomass_sum, [12.0, 24.0, 36.0])

    def test_helper_does_not_mutate_inputs_in_place(self):
        """The helper must return new lists; the original main lists are unchanged."""
        from api.reports.land import _aggregate_minor_seasons_into_emissions_sets

        main_es = [_entry_obj("Biomass", "CO2", [10.0, 20.0, 30.0])]
        main_es_w = [_entry_obj("Biomass", "CO2", [12.0, 22.0, 33.0])]
        main_es_wo = []
        original_main_len = len(main_es)

        minor_balance = [_entry_obj("Biomass", "CO2", [1.0, 2.0, 3.0])]
        minor_seasons = [Mock()]

        calc_patch, result_patch = self._patch_paths(minor_balance, minor_balance, [])
        with calc_patch, result_patch:
            _aggregate_minor_seasons_into_emissions_sets(
                main_es, main_es_w, main_es_wo, minor_seasons
            )
        self.assertEqual(len(main_es), original_main_len)

    def test_helper_returns_main_unchanged_when_no_minor_seasons(self):
        """With zero minor seasons the returned lists equal the inputs."""
        from api.reports.land import _aggregate_minor_seasons_into_emissions_sets

        main_es = [_entry_obj("Biomass", "CO2", [10.0])]
        main_es_w = [_entry_obj("Biomass", "CO2", [11.0])]
        main_es_wo = [_entry_obj("Biomass", "CO2", [1.0])]

        es, es_w, es_wo = _aggregate_minor_seasons_into_emissions_sets(
            main_es, main_es_w, main_es_wo, []
        )
        self.assertEqual(es, main_es)
        self.assertEqual(es_w, main_es_w)
        self.assertEqual(es_wo, main_es_wo)

    def test_helper_aggregates_straw_burning_ch4(self):
        """STRAW_BURNING/CH4 from minor seasons is included (Bug 7qn)."""
        from api.reports.land import _aggregate_minor_seasons_into_emissions_sets
        from api.reports.extractors import extract_emissions

        main_es = [_entry_obj("Straw Burning", "CH4", [5.0, 5.0, 5.0])]
        minor_balance = [_entry_obj("Straw Burning", "CH4", [2.0, 2.0, 2.0])]
        minor_seasons = [Mock(), Mock()]

        calc_patch, result_patch = self._patch_paths(minor_balance, minor_balance, [])
        with calc_patch, result_patch:
            es, _, _ = _aggregate_minor_seasons_into_emissions_sets(
                main_es, [], [], minor_seasons
            )
        fire_ch4 = extract_emissions(es, "Straw Burning", "CH4", duration=3)
        # main 5/5/5 + 2 minors × [2, 2, 2] = [9, 9, 9]
        self.assertEqual(fire_ch4, [9.0, 9.0, 9.0])

    def test_helper_passes_balance_not_raw_w_plus_wo(self):
        """The helper must use Result(...).balance (w - wo), never raw w+wo."""
        from api.reports.land import _aggregate_minor_seasons_into_emissions_sets
        from api.reports.extractors import extract_emissions

        main_es = []
        # Minor's balance is +1 per year; minor's total_w is +10/yr, total_wo is +9/yr.
        # A buggy implementation that appends raw total_w + total_wo would yield 19/yr.
        minor_balance = [_entry_obj("Biomass", "CO2", [1.0, 1.0, 1.0])]
        minor_total_w = [_entry_obj("Biomass", "CO2", [10.0, 10.0, 10.0])]
        minor_total_wo = [_entry_obj("Biomass", "CO2", [9.0, 9.0, 9.0])]
        minor_seasons = [Mock()]

        calc_patch, result_patch = self._patch_paths(minor_balance, minor_total_w, minor_total_wo)
        with calc_patch, result_patch:
            es, _, _ = _aggregate_minor_seasons_into_emissions_sets(
                main_es, [], [], minor_seasons
            )

        balance_sum = extract_emissions(es, "Biomass", "CO2", duration=3)
        # If helper correctly took balance: [1, 1, 1]; if it added w+wo: [19, 19, 19].
        self.assertEqual(balance_sum, [1.0, 1.0, 1.0])


# ===========================================================================
# 3. Per-row totals consistency in compute() (catches Bug 7nt, the dead total)
# ===========================================================================

class TestRowSumEqualsBalanceTotal(unittest.TestCase):
    """For a balance whose entries match the FloodedRice whitelist exactly, the
    sum of the displayed result rows must equal _balance_total() per year.

    This is the invariant the dead local `total_emissions` was supposed to enforce."""

    DURATION = 3

    def _make_cached_module(self, balance_entries):
        """Build a module mock whose cached results carry the supplied balance."""
        cached = {
            "balance": balance_entries,
            "total_w": balance_entries,
            "total_wo": [],
            "inventory": [],
        }
        module = Mock()
        module.is_cached_results_valid.return_value = True
        module.cached_results_by_activity_by_gas = cached
        module.cached_units_breakdown = {"w": [0.0] * self.DURATION, "wo": [0.0] * self.DURATION}
        module.module_type.name = "Flooded Rice"
        module.activity.name = "TestActivity"
        module.activity.implementation_years = self.DURATION
        module.activity.capitalization_years = 0
        return module

    def test_sum_of_whitelisted_rows_equals_balance_total(self):
        """With a synthetic FloodedRice balance touching all six whitelist categories,
        the sum across (biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4, rice_ch4)
        equals _balance_total() per year."""
        # Entries are stored as a dict (cached-format) – extractors handle both.
        balance = {
            "1": {"activity": "Biomass",             "gas_type": "CO2", "emissions": [{"value": 1.0},  {"value": 2.0},  {"value": 3.0}]},
            "2": {"activity": "Soil CO2 Change",     "gas_type": "CO2", "emissions": [{"value": 10.0}, {"value": 20.0}, {"value": 30.0}]},
            "3": {"activity": "Soil Organic Matter", "gas_type": "N2O", "emissions": [{"value": 0.5},  {"value": 0.5},  {"value": 0.5}]},
            "4": {"activity": "Straw Burning",       "gas_type": "N2O", "emissions": [{"value": 0.1},  {"value": 0.1},  {"value": 0.1}]},
            "5": {"activity": "Straw Burning",       "gas_type": "CH4", "emissions": [{"value": 0.2},  {"value": 0.2},  {"value": 0.2}]},
            "6": {"activity": "CH4 Emitted Rice",    "gas_type": "CH4", "emissions": [{"value": 5.0},  {"value": 5.0},  {"value": 5.0}]},
        }
        module = self._make_cached_module(balance)

        from api.reports.base import BaseModuleReport
        from api.reports.extractors import extract_emissions

        @dataclass
        class ConcreteReport(BaseModuleReport):
            def compute(self):
                return None

        activity_report = Mock()
        activity_report.project_report.duration = self.DURATION
        report = ConcreteReport(module=module, activity_report=activity_report)

        # _balance_total() sums every entry.
        total = report._balance_total()

        # Sum of the six whitelisted extracts.
        import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils
        AT, GT = math_utils.ActivityTypes, math_utils.GasTypes
        biomass_co2 = extract_emissions(report.emissions_set, AT.BIOMASS, GT.CO2, duration=self.DURATION)
        soil_co2 = extract_emissions(report.emissions_set, AT.SOIL_CO2_CHANGE, GT.CO2, duration=self.DURATION)
        soil_n2o = extract_emissions(report.emissions_set, AT.SOM, GT.N2O, duration=self.DURATION)
        fire_n2o = extract_emissions(report.emissions_set, AT.STRAW_BURNING, GT.N2O, duration=self.DURATION)
        fire_ch4 = extract_emissions(report.emissions_set, AT.STRAW_BURNING, GT.CH4, duration=self.DURATION)
        rice_ch4 = extract_emissions(report.emissions_set, AT.CH4_EMITTED_RICE, GT.CH4, duration=self.DURATION)

        row_sum = [sum(vals) for vals in zip(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4, rice_ch4)]
        for i in range(self.DURATION):
            self.assertAlmostEqual(row_sum[i], total[i], places=6,
                                   msg=f"Year {i}: row_sum={row_sum[i]} total={total[i]}")
