"""Base classes for the computation layer.

All classes here are responsible for CALCULATION only – no Excel imports.
They produce data_types.ModuleResult / ActivityResult / ProjectResult
which are then passed to renderers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import zip_longest
from typing import Any

import logging as log
import numpy as np

import api.models as api_models
import api.calculators as calculators
import ipcc.models as ipcc_models
from .constants import SPC_INCREASE_RATE
from .data_types import (
    ActivityResult,
    EmissionsAggregator,
    InventoryItem,
    ModuleResult,
    ProjectResult,
    ShadowPriceRow,
    T2Override,
)
from .extractors import _add, extract_emissions


class NotReadyError(Exception):
    pass


@dataclass
class BaseModuleReport:
    """Base class for module-level computation. Subclasses implement compute()."""

    module: api_models.Module | api_models.LandModule
    activity_report: "BaseActivityReport" = None

    # Set in __post_init__ after running the calculator
    calculator: Any = field(default=None, repr=False)
    result: dict = field(default=None, repr=False)
    inventory: Any = field(default=None, repr=False)
    emissions_set: list = field(default=None, repr=False)
    emissions_set_w: list = field(default=None, repr=False)
    emissions_set_wo: list = field(default=None, repr=False)
    _from_cache: bool = field(default=False, repr=False)
    _cached_inventory: list = field(default_factory=list, repr=False)
    _cache_result: Any = field(default=None, repr=False)

    def __post_init__(self):
        from .cache import load_emissions_from_cache
        cache_result = load_emissions_from_cache(self.module)
        if cache_result is not None:
            self._init_from_cache(cache_result)
        else:
            self._init_from_calculator()

    def _init_from_cache(self, cache_result: "CacheResult") -> None:
        """Cached path: populate emissions_set* from module's cached results."""
        self.emissions_set    = cache_result.balance
        self.emissions_set_w  = cache_result.with_project
        self.emissions_set_wo = cache_result.without_project
        self._cached_inventory = cache_result.inventory
        self._cache_result = cache_result
        self._from_cache = True

    def _init_from_calculator(self) -> None:
        """Calculated path: run the calculator and extract emissions sets."""
        try:
            self.result = self.calculator.calculate()
            self.inventory = self.calculator.inventory
        except Exception as e:
            log.error(
                f"Cannot calculate report for module {self.module.module_type.name} "
                f"in activity {self.module.activity.name}: {e}"
            )
            raise NotReadyError(
                f"Cannot calculate report for module {self.module.module_type.name} "
                f"in activity {self.module.activity.name}: {e}"
            ) from e

        from api.calculators import Result

        self.emissions_set    = Result(*self.result).balance.yearly_emissions_by_sector_by_gas
        self.emissions_set_w  = Result(*self.result).total_w.yearly_emissions_by_sector_by_gas
        self.emissions_set_wo = Result(*self.result).total_wo.yearly_emissions_by_sector_by_gas

        try:
            from .cache import save_results_to_cache
            save_results_to_cache(
                self.module,
                self.emissions_set,
                self.emissions_set_w,
                self.emissions_set_wo,
                self.inventory,
            )
        except Exception as e:
            log.warning(
                f"Could not save results to cache for module {self.module.pk}: {e}"
            )

    @property
    def _project_duration(self) -> int:
        return self.activity_report.project_report.duration

    def _extract(
        self,
        source,
        activity_type=None,
        gas_type=None,
        excluded_activity_types=None,
        excluded_gas_types=None,
    ) -> list[float]:
        """Extract emissions using the unified extractor with project duration."""
        return extract_emissions(
            source,
            activity_type=activity_type,
            gas_type=gas_type,
            excluded_activity_types=excluded_activity_types,
            excluded_gas_types=excluded_gas_types,
            duration=self._project_duration,
        )

    def _balance_total(self) -> list[float]:
        """Full GHG balance of this module: the sum of *every* entry in
        ``emissions_set`` (all activities, all gases).

        A module's total emissions MUST equal the complete sum of its balance.
        Building the total from a hand-picked whitelist of (activity, gas)
        pairs silently drops any category the calculator emits but the report
        forgot to extract — e.g. the ``Fuel`` activity that the per-change-units
        feature split out of Storage/Packaging, or Settlement land emissions.
        See issue exact-django-webapp-jcb.
        """
        return extract_emissions(
            self.emissions_set, duration=self._project_duration
        )

    def compute(self) -> ModuleResult:
        """Return a ModuleResult with all computed data. Must be overridden."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement compute()"
        )

    def _inventory_items_from_module(self, activity_title: str) -> list[InventoryItem]:
        """Build InventoryItem list — from cache or from live inventory object."""
        if self._from_cache:
            from .cache import build_inventory_from_cache
            return build_inventory_from_cache(self._cached_inventory, self.module, activity_title)
        if self.inventory is None:
            return []
        items = []
        for item in self.inventory.emissions_by_sector_by_gas:
            items.append(InventoryItem(
                activity_name=activity_title,
                module_name=self.module.module_type.name,
                ipcc_category=item.activity.value if item.activity else "N/A",
                gas_type=item.gas_type.name if item.gas_type else "N/A",
                value=item.value,
            ))
        return items


@dataclass
class BaseActivityReport:
    """Computes ActivityResult for a single activity."""

    project_report: "BaseProjectReport"
    activity: api_models.Activity

    @property
    def duration(self) -> int:
        return self.activity.implementation_years + self.activity.capitalization_years

    def compute(self) -> ActivityResult:
        from .registry import get_report_class

        module_results: list[ModuleResult] = []
        module_reports: list[BaseModuleReport] = []
        total_emissions = [0.0] * self.project_report.duration
        total_hectares_yearly = [0.0] * self.project_report.duration
        total_heads_yearly = [0.0] * self.project_report.duration
        total_catch_yearly = [0.0] * self.project_report.duration
        # A single activity's land modules all describe the SAME physical parcel:
        # a land-use change carries a "with" module and a "without" module over
        # the same hectares. Only the first contributing land module is counted
        # so the area is not double-counted (mirrors the break in
        # Activity.get_land_modules_area()). See exact-django-webapp-gz3.
        hectares_counted = False

        for module in self.activity.modules:
            report_cls = get_report_class(module)
            if report_cls is None:
                log.warning(f"No report class for {module.module_type.name}, skipping")
                continue

            report = report_cls(module, self)
            result = report.compute()
            module_results.append(result)
            module_reports.append(report)

            total_emissions = list(map(sum, zip_longest(
                total_emissions, result.total_emissions, fillvalue=0
            )))

            if not hectares_counted:
                if module.is_with() and result.units_breakdown_w:
                    total_hectares_yearly = list(map(sum, zip_longest(
                        total_hectares_yearly, result.units_breakdown_w, fillvalue=0
                    )))
                    hectares_counted = True
                elif module.is_without() and result.units_breakdown_wo:
                    total_hectares_yearly = list(map(sum, zip_longest(
                        total_hectares_yearly, result.units_breakdown_wo, fillvalue=0
                    )))
                    hectares_counted = True

            if result.units_heads_w:
                total_heads_yearly = list(map(sum, zip_longest(
                    total_heads_yearly, result.units_heads_w, fillvalue=0
                )))

            if result.units_catch_w:
                total_catch_yearly = list(map(sum, zip_longest(
                    total_catch_yearly, result.units_catch_w, fillvalue=0
                )))

        t2_overrides = []
        if self.activity.climate_t2:
            t2_overrides.append(T2Override("Climate", self.activity.climate_t2.name))
        if self.activity.moisture_t2:
            t2_overrides.append(T2Override("Moisture", self.activity.moisture_t2.name))
        if self.activity.soil_type_t2:
            t2_overrides.append(T2Override("Soil type", self.activity.soil_type_t2.name))
        if self.activity.duration_t2:
            t2_overrides.append(T2Override("Duration", self.activity.duration_t2))
        if self.activity.start_year_t2 is not None:
            t2_overrides.append(T2Override("Start year", self.activity.start_year_t2))
        if self.activity.last_year_of_accounting_t2:
            t2_overrides.append(T2Override("Last year of accounting", self.activity.last_year_of_accounting_t2))
        if self.activity.soc_t2:
            t2_overrides.append(T2Override("SOC", self.activity.soc_t2))

        return ActivityResult(
            title=self.activity.name,
            module_results=module_results,
            total_emissions=total_emissions,
            total_hectares_yearly=total_hectares_yearly,
            total_heads_yearly=total_heads_yearly,
            total_catch_yearly=total_catch_yearly,
            t2_overrides=t2_overrides,
            _module_reports=module_reports,
        )


@dataclass
class BaseProjectReport:
    """Orchestrates computation of a full ProjectResult."""

    project: api_models.Project
    activities: Any = None  # QuerySet or list; None → use project.activities.all()

    def __post_init__(self):
        if self.activities is None:
            self.activities = self.project.activities.all()

    @property
    def duration(self) -> int:
        return self.project.implementation_years + self.project.capitalization_years

    @property
    def start_year(self) -> int:
        return self.project.start_year_of_activities

    @property
    def last_year(self) -> int:
        return self.project.last_year_of_accounting

    def compute(self) -> ProjectResult:
        """Run all calculations and return the complete ProjectResult."""
        activity_reports = [BaseActivityReport(self, a) for a in self.activities]
        activity_results = [ar.compute() for ar in activity_reports]

        aggregated = self._build_aggregated(activity_results)
        cumulative_hectares = self._build_cumulative_hectares(activity_results)
        cumulative_heads = self._build_cumulative_heads(activity_results)
        cumulative_catch = self._build_cumulative_catch(activity_results)
        shadow_rows, nominal_spcs, extra_spcs = self._build_shadow_price_data(aggregated)
        inventory_items = self._build_inventory_items(activity_results)

        return ProjectResult(
            project=self.project,
            start_year=self.start_year,
            last_year=self.last_year,
            duration=self.duration,
            activity_results=activity_results,
            aggregated=aggregated,
            cumulative_hectares_yearly=cumulative_hectares,
            cumulative_heads_yearly=cumulative_heads,
            cumulative_catch_yearly=cumulative_catch,
            shadow_price_rows=shadow_rows,
            nominal_shadow_prices=nominal_spcs,
            extra_shadow_prices=extra_spcs,
            inventory_items=inventory_items,
        )

    def _build_aggregated(self, activity_results: list[ActivityResult]) -> EmissionsAggregator:
        return self._build_aggregated_from_module_emissions(activity_results)

    def _build_aggregated_from_module_emissions(
        self, activity_results: list[ActivityResult]
    ) -> EmissionsAggregator:
        """Aggregate emissions from all module results.

        This replicates finalize_report()'s 18-parallel-list logic but using
        the emissions data already computed and stored in each ModuleResult.
        """
        import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils

        agg = EmissionsAggregator(duration=self.duration)
        dur = self.duration

        # Emissions sets are stored on BaseModuleReport instances, not on ModuleResult.
        # ActivityResult._module_reports holds the report instances in the same order
        # as module_results, populated by BaseActivityReport.compute().
        for activity_result in activity_results:
            for report in activity_result._module_reports:
                es = report.emissions_set
                es_w = report.emissions_set_w
                es_wo = report.emissions_set_wo

                def extr(source, activity_type=None, gas_type=None, excl_a=None, excl_g=None):
                    return extract_emissions(
                        source, activity_type, gas_type, excl_a, excl_g, duration=dur
                    )

                # Balance
                agg.other_ghgs = _add(agg.other_ghgs, extr(es, gas_type=math_utils.GasTypes.OTHER))
                agg.other_ghgs = _add(agg.other_ghgs, extr(es, gas_type=math_utils.GasTypes.DOC))
                agg.other_ghgs = _add(agg.other_ghgs, extr(es, gas_type=math_utils.GasTypes.CO))
                agg.n2o = _add(agg.n2o, extr(es, gas_type=math_utils.GasTypes.N2O))
                agg.ch4 = _add(agg.ch4, extr(es, gas_type=math_utils.GasTypes.CH4))
                agg.other_co2 = _add(agg.other_co2, extr(es, gas_type=math_utils.GasTypes.CO2,
                    excl_a=[math_utils.ActivityTypes.BIOMASS, math_utils.ActivityTypes.SOIL_CO2_CHANGE]))
                agg.soil_co2 = _add(agg.soil_co2, extr(es,
                    activity_type=math_utils.ActivityTypes.SOIL_CO2_CHANGE,
                    gas_type=math_utils.GasTypes.CO2))
                agg.biomass_co2 = _add(agg.biomass_co2, extr(es,
                    activity_type=math_utils.ActivityTypes.BIOMASS,
                    gas_type=math_utils.GasTypes.CO2))

                # With
                agg.other_ghgs_w = _add(agg.other_ghgs_w, extr(es_w, gas_type=math_utils.GasTypes.OTHER))
                agg.other_ghgs_w = _add(agg.other_ghgs_w, extr(es_w, gas_type=math_utils.GasTypes.DOC))
                agg.other_ghgs_w = _add(agg.other_ghgs_w, extr(es_w, gas_type=math_utils.GasTypes.CO))
                agg.n2o_w = _add(agg.n2o_w, extr(es_w, gas_type=math_utils.GasTypes.N2O))
                agg.ch4_w = _add(agg.ch4_w, extr(es_w, gas_type=math_utils.GasTypes.CH4))
                agg.other_co2_w = _add(agg.other_co2_w, extr(es_w, gas_type=math_utils.GasTypes.CO2,
                    excl_a=[math_utils.ActivityTypes.BIOMASS, math_utils.ActivityTypes.SOIL_CO2_CHANGE]))
                agg.soil_co2_w = _add(agg.soil_co2_w, extr(es_w,
                    activity_type=math_utils.ActivityTypes.SOIL_CO2_CHANGE,
                    gas_type=math_utils.GasTypes.CO2))
                agg.biomass_co2_w = _add(agg.biomass_co2_w, extr(es_w,
                    activity_type=math_utils.ActivityTypes.BIOMASS,
                    gas_type=math_utils.GasTypes.CO2))

                # Without
                agg.other_ghgs_wo = _add(agg.other_ghgs_wo, extr(es_wo, gas_type=math_utils.GasTypes.OTHER))
                agg.other_ghgs_wo = _add(agg.other_ghgs_wo, extr(es_wo, gas_type=math_utils.GasTypes.DOC))
                agg.other_ghgs_wo = _add(agg.other_ghgs_wo, extr(es_wo, gas_type=math_utils.GasTypes.CO))
                agg.n2o_wo = _add(agg.n2o_wo, extr(es_wo, gas_type=math_utils.GasTypes.N2O))
                agg.ch4_wo = _add(agg.ch4_wo, extr(es_wo, gas_type=math_utils.GasTypes.CH4))
                agg.other_co2_wo = _add(agg.other_co2_wo, extr(es_wo, gas_type=math_utils.GasTypes.CO2,
                    excl_a=[math_utils.ActivityTypes.BIOMASS, math_utils.ActivityTypes.SOIL_CO2_CHANGE]))
                agg.soil_co2_wo = _add(agg.soil_co2_wo, extr(es_wo,
                    activity_type=math_utils.ActivityTypes.SOIL_CO2_CHANGE,
                    gas_type=math_utils.GasTypes.CO2))
                agg.biomass_co2_wo = _add(agg.biomass_co2_wo, extr(es_wo,
                    activity_type=math_utils.ActivityTypes.BIOMASS,
                    gas_type=math_utils.GasTypes.CO2))

        return agg

    def _build_cumulative_hectares(self, activity_results: list[ActivityResult]) -> list[float]:
        cumulative = [0.0] * self.duration
        for ar in activity_results:
            cumulative = list(map(sum, zip_longest(
                cumulative, ar.total_hectares_yearly, fillvalue=0
            )))
        return cumulative

    def _build_cumulative_heads(self, activity_results: list[ActivityResult]) -> list[float]:
        cumulative = [0.0] * self.duration
        for ar in activity_results:
            cumulative = list(map(sum, zip_longest(
                cumulative, ar.total_heads_yearly, fillvalue=0
            )))
        return cumulative

    def _build_cumulative_catch(self, activity_results: list[ActivityResult]) -> list[float]:
        cumulative = [0.0] * self.duration
        for ar in activity_results:
            cumulative = list(map(sum, zip_longest(
                cumulative, ar.total_catch_yearly, fillvalue=0
            )))
        return cumulative

    def _build_shadow_price_data(self, aggregated: EmissionsAggregator):
        shadow_prices_qs = ipcc_models.ShadowPriceOfCarbon.objects.all()
        last_known = shadow_prices_qs.last()

        shadow_rows: list[ShadowPriceRow] = []
        extra_spcs = []

        yearly_balance_w = aggregated.yearly_balance_w
        yearly_balance_wo = aggregated.yearly_balance_wo

        # Bulk-fetch all shadow prices once to avoid N+1 queries inside the loop
        shadow_prices_by_year = {sp.year: sp for sp in shadow_prices_qs}

        for i, year in enumerate(range(self.start_year, self.last_year)):
            sp = shadow_prices_by_year.get(year)
            if sp is None and year > 2017:
                sp = ipcc_models.ShadowPriceOfCarbon(
                    year=year,
                    min_value=last_known.min_value * (1 + SPC_INCREASE_RATE),
                    max_value=last_known.max_value * (1 + SPC_INCREASE_RATE),
                )
                last_known = sp
                extra_spcs.append(sp)

            bal_w = yearly_balance_w[i] if i < len(yearly_balance_w) else 0.0
            bal_wo = yearly_balance_wo[i] if i < len(yearly_balance_wo) else 0.0

            sp_wo_min = sp_wo_max = sp_w_min = sp_w_max = None
            if sp is not None and year >= 2017:
                sp_wo_min = sp.min_value * bal_wo
                sp_wo_max = sp.max_value * bal_wo
                sp_w_min = sp.min_value * bal_w
                sp_w_max = sp.max_value * bal_w

            shadow_rows.append(ShadowPriceRow(
                year=year,
                yearly_balance_wo=bal_wo,
                yearly_balance_w=bal_w,
                sp_wo_min=sp_wo_min,
                sp_wo_max=sp_wo_max,
                sp_w_min=sp_w_min,
                sp_w_max=sp_w_max,
                is_extrapolated=(sp in extra_spcs),
                sp_min_value=sp.min_value if sp else None,
                sp_max_value=sp.max_value if sp else None,
            ))

        return shadow_rows, list(shadow_prices_qs), extra_spcs

    def _build_inventory_items(self, activity_results: list[ActivityResult]) -> list[InventoryItem]:
        items = []
        for ar in activity_results:
            for mr in ar.module_results:
                items.extend(mr._inventory_items)
        return items
