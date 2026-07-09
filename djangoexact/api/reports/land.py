"""Land module report classes – calculation only, no Excel imports.

Each class implements compute() -> ModuleResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import logging as log
import numpy as np

import api.models as api_models
import api.calculators as calculators
import api.defaults as defaults
import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils

from .base import BaseModuleReport, NotReadyError
from .data_types import InventoryItem, MetadataWrite, ModuleResult, ResultRow
from .extractors import _add, extract_emissions


@dataclass
class LandModuleReport(BaseModuleReport):
    """Base for all land module reports.

    Subclasses must assign self.calculator before calling super().__post_init__().
    """

    # set in __post_init__ from calculator hectares data
    _units_breakdown_w: list[float] = field(default_factory=list, repr=False)
    _units_breakdown_wo: list[float] = field(default_factory=list, repr=False)

    def __post_init__(self):
        length = (
            self.module.activity.implementation_years
            + self.module.activity.capitalization_years
        )
        # Snapshot whether cached units exist BEFORE base __post_init__ decides the path
        _cached_units = (
            self.module.cached_units_breakdown
            if self.module.is_cached_results_valid()
            else None
        )

        super().__post_init__()  # dispatches to _init_from_cache or _init_from_calculator

        if self._from_cache and _cached_units is not None:
            # ── Full cache hit ──────────────────────────────────────────────────
            self._units_breakdown_w  = _cached_units["w"]
            self._units_breakdown_wo = _cached_units["wo"]

        elif self._from_cache and _cached_units is None:
            # ── Partial cache hit: emissions cached, units not yet stored ───────
            # Run the calculator solely to extract hectares, then persist.
            try:
                self.calculator.calculate()
                break_w  = getattr(self.calculator.math_w,  "hectares_total", np.zeros(length))
                break_wo = getattr(self.calculator.math_wo, "hectares_total", np.zeros(length))
                self._units_breakdown_w  = list(np.round(break_w,  2))
                self._units_breakdown_wo = list(np.round(break_wo, 2))
                self.module.cache_units_breakdown(
                    self._units_breakdown_w, self._units_breakdown_wo
                )
            except Exception as exc:
                log.warning(
                    f"Could not compute units_breakdown for cached module "
                    f"{self.module.pk}: {exc}"
                )
                self._units_breakdown_w  = [0.0] * length
                self._units_breakdown_wo = [0.0] * length

        else:
            # ── Calculator path (full, original logic) ──────────────────────────
            break_w  = getattr(self.calculator.math_w,  "hectares_total", np.zeros(length))
            break_wo = getattr(self.calculator.math_wo, "hectares_total", np.zeros(length))
            self._units_breakdown_w  = list(np.round(break_w,  2))
            self._units_breakdown_wo = list(np.round(break_wo, 2))
            # Cache units alongside emissions for future report runs.
            if self.module.is_cached_results_valid():
                try:
                    self.module.cache_units_breakdown(
                        self._units_breakdown_w, self._units_breakdown_wo
                    )
                except Exception as exc:
                    log.warning(
                        f"Could not cache units_breakdown for module {self.module.pk}: {exc}"
                    )

    def _extract_land_base(self):
        """Return (biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4) from balance emissions."""
        es = self.emissions_set
        biomass_co2 = self._extract(es, math_utils.ActivityTypes.BIOMASS, math_utils.GasTypes.CO2)
        soil_co2 = self._extract(es, math_utils.ActivityTypes.SOIL_CO2_CHANGE, math_utils.GasTypes.CO2)
        soil_n2o = self._extract(es, math_utils.ActivityTypes.SOM, math_utils.GasTypes.N2O)
        fire_n2o = self._extract(es, math_utils.ActivityTypes.RESIDUE_BURNING, math_utils.GasTypes.N2O)
        fire_ch4 = self._extract(es, math_utils.ActivityTypes.RESIDUE_BURNING, math_utils.GasTypes.CH4)
        return biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4

    def _standard_result_rows(
        self,
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4,
        extra_rows: list[ResultRow] | None = None,
    ) -> list[ResultRow]:
        rows = [
            ResultRow("CO2 in biomass", biomass_co2),
            ResultRow("CO2 in soils", soil_co2),
            ResultRow("N2O in soils", soil_n2o),
            ResultRow("N2O from fires", fire_n2o),
            ResultRow("CH4 from fires", fire_ch4),
        ]
        if extra_rows:
            rows.extend(extra_rows)
        return rows

    def _inventory_items(self, activity_title: str) -> list[InventoryItem]:
        return self._inventory_items_from_module(activity_title)


@dataclass
class LandUseChangeReport(LandModuleReport):
    module: api_models.LandUseChange

    def __post_init__(self):
        self.calculator = calculators.LandUseChangeCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._extract_land_base()

        # LandUseChange adds DOM CO2 to soil_co2
        dom_co2 = self._extract(
            self.emissions_set, math_utils.ActivityTypes.DOM, math_utils.GasTypes.CO2
        )
        soil_co2 = _add(soil_co2, dom_co2)

        m = self.module
        mw = [
            MetadataWrite(1, 1, "Type of land use change"),
            MetadataWrite(2, 1, "Fire used during conversion"),
            MetadataWrite(3, 1, "Dry matter removed during conversion"),
        ]
        if m.is_start():
            mw += [
                MetadataWrite(1, 2, m.module_type_start.name),
                MetadataWrite(2, 2, "Yes" if m.is_fire_used_start else "No"),
                MetadataWrite(3, 2, m.dry_matter_start),
            ]
        if m.is_with():
            mw += [
                MetadataWrite(1, 3, m.module_type_w.name),
                MetadataWrite(2, 3, "Yes" if m.is_fire_used_w else "No"),
                MetadataWrite(3, 3, m.dry_matter_w),
            ]
        if m.is_without():
            mw += [
                MetadataWrite(1, 4, m.module_type_wo.name),
                MetadataWrite(2, 4, "Yes" if m.is_fire_used_wo else "No"),
                MetadataWrite(3, 4, m.dry_matter_wo),
            ]
        mw += [
            MetadataWrite(1, 6, m.module_type_thread.format_comments()),
            MetadataWrite(2, 6, m.is_fire_used_thread.format_comments()),
            MetadataWrite(3, 6, m.dry_matter_thread.format_comments()),
        ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="Land Use Change",
            result_rows=self._standard_result_rows(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4),
            metadata_writes=mw,
            total_emissions=self._balance_total(),
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )


@dataclass
class PerennialCroplandReport(LandModuleReport):
    module: api_models.PerennialCropland

    def __post_init__(self):
        self.calculator = calculators.PerennialCroplandCalculator(self.module)
        super().__post_init__()

        # In the calculator path, the main calculator only computes the main
        # module — minor seasons must be merged in so emissions_set contains
        # the full PerennialCropland picture (main + every minor season). The
        # previous in-compute() _add_minor_seasons loop never called
        # minor_calc.calculate(), used the MAIN module's start_w/wo, and
        # appended raw w + wo into a balance — see exact-django-webapp-flx
        # (covers exact-django-webapp-ttm / -fqg for PerennialCropland).
        if not self._from_cache:
            minor_seasons = getattr(self.module, "submodules", []) or []
            if minor_seasons:
                (
                    self.emissions_set,
                    self.emissions_set_w,
                    self.emissions_set_wo,
                    minor_inventories,
                ) = _aggregate_minor_seasons_into_emissions_sets(
                    self.emissions_set,
                    self.emissions_set_w,
                    self.emissions_set_wo,
                    minor_seasons,
                    calculators.PerennialCropCalculator,
                )
                self.inventory = _merge_minor_inventories(self.inventory, minor_inventories)
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
                        f"Could not re-save merged PerennialCropland cache for module {self.module.pk}: {e}"
                    )

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._extract_land_base()

        m = self.module
        units = m.area
        mw = [
            MetadataWrite(1, 1, "Hectares"),
            MetadataWrite(2, 1, "Agroforestry system"),
            MetadataWrite(3, 1, "Tillage management type"),
            MetadataWrite(4, 1, "Organic input type"),
            MetadataWrite(5, 1, "Yield"),
        ]
        if m.is_start():
            mw += [
                MetadataWrite(1, 2, units),
                MetadataWrite(2, 2, m.land_use_type_start.name),
                MetadataWrite(3, 2, m.tillage_management_type_start.name),
                MetadataWrite(4, 2, m.organic_input_type_start.name),
                MetadataWrite(5, 2, m.crop_yield_t2_start if m.crop_yield_t2_start is not None else "Default"),
            ]
        if m.is_with():
            mw += [
                MetadataWrite(1, 3, units),
                MetadataWrite(2, 3, m.land_use_type_w.name),
                MetadataWrite(3, 3, m.tillage_management_type_w.name),
                MetadataWrite(4, 3, m.organic_input_type_w.name),
                MetadataWrite(5, 3, m.crop_yield_t2_w if m.crop_yield_t2_w is not None else "Default"),
            ]
        if m.is_without():
            mw += [
                MetadataWrite(1, 4, units),
                MetadataWrite(2, 4, m.land_use_type_wo.name),
                MetadataWrite(3, 4, m.tillage_management_type_wo.name),
                MetadataWrite(4, 4, m.organic_input_type_wo.name),
                MetadataWrite(5, 4, m.crop_yield_t2_wo if m.crop_yield_t2_wo is not None else "Default"),
            ]
        mw += [
            MetadataWrite(2, 6, m.land_use_type_thread.format_comments()),
            MetadataWrite(3, 6, m.tillage_management_type_thread.format_comments()),
            MetadataWrite(4, 6, m.organic_input_type_thread.format_comments()),
            MetadataWrite(5, 6, m.crop_yield_t2_thread.format_comments()),
        ]

        dur = self._project_duration
        ai_w = [("Perennial Cropland (ha)", self._units_breakdown_w[:dur])]
        ai_wo = [("Perennial Cropland (ha)", self._units_breakdown_wo[:dur])]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="Perennial Cropland",
            result_rows=self._standard_result_rows(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4),
            metadata_writes=mw,
            additional_indicator_rows_w=ai_w,
            additional_indicator_rows_wo=ai_wo,
            total_emissions=self._balance_total(),
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )


@dataclass
class AnnualCroplandReport(LandModuleReport):
    module: api_models.AnnualCropland

    def __post_init__(self):
        self.calculator = calculators.AnnualCroplandCalculator(self.module)
        super().__post_init__()

        # In the calculator path, the main calculator only computes the main
        # module — minor seasons must be merged in so emissions_set contains
        # the full AnnualCropland picture (main + every minor season). The
        # previous in-compute() _add_minor_seasons loop never called
        # minor_calc.calculate(), used the MAIN module's start_w/wo (BOTH
        # branches, not just is_with — fully broken vs PerennialCropland's
        # half-fix), and appended raw w + wo into a balance — see
        # exact-django-webapp-flx (covers exact-django-webapp-ttm / -fqg for
        # AnnualCropland).
        if not self._from_cache:
            minor_seasons = getattr(self.module, "submodules", []) or []
            if minor_seasons:
                (
                    self.emissions_set,
                    self.emissions_set_w,
                    self.emissions_set_wo,
                    minor_inventories,
                ) = _aggregate_minor_seasons_into_emissions_sets(
                    self.emissions_set,
                    self.emissions_set_w,
                    self.emissions_set_wo,
                    minor_seasons,
                    calculators.AnnualCropCalculator,
                )
                self.inventory = _merge_minor_inventories(self.inventory, minor_inventories)
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
                        f"Could not re-save merged AnnualCropland cache for module {self.module.pk}: {e}"
                    )

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._extract_land_base()

        m = self.module
        units = m.area
        mw = [
            MetadataWrite(1, 1, "Hectares"),
            MetadataWrite(2, 1, "Main season crop"),
            MetadataWrite(3, 1, "Tillage management type"),
            MetadataWrite(4, 1, "Organic input type"),
            MetadataWrite(5, 1, "Residue management type"),
            MetadataWrite(6, 1, "Yield"),
            MetadataWrite(7, 1, "Minor season crop"),
            MetadataWrite(8, 1, "Minor residue management type"),
            MetadataWrite(9, 1, "Minor yield"),
        ]
        if m.is_start():
            mw += [
                MetadataWrite(1, 2, units),
                MetadataWrite(2, 2, m.land_use_type_start.name),
                MetadataWrite(3, 2, m.tillage_management_type_start.name),
                MetadataWrite(4, 2, m.organic_input_type_start.name),
                MetadataWrite(5, 2, m.residue_management_type_start.name),
                MetadataWrite(6, 2, m.crop_yield_t2_start if m.crop_yield_t2_start is not None else "Default"),
                MetadataWrite(7, 2, m.minor_land_use_type_start.name if m.minor_land_use_type_start is not None else "Default"),
                MetadataWrite(8, 2, m.minor_residue_management_type_start.name if m.minor_residue_management_type_start is not None else "Default"),
                MetadataWrite(9, 2, m.minor_yield_start if m.minor_yield_start is not None else "Default"),
            ]
        if m.is_with():
            mw += [
                MetadataWrite(1, 3, units),
                MetadataWrite(2, 3, m.land_use_type_w.name),
                MetadataWrite(3, 3, m.tillage_management_type_w.name),
                MetadataWrite(4, 3, m.organic_input_type_w.name),
                MetadataWrite(5, 3, m.residue_management_type_w.name),
                MetadataWrite(6, 3, m.crop_yield_t2_w if m.crop_yield_t2_w is not None else "Default"),
                MetadataWrite(7, 3, m.minor_land_use_type_w.name if m.minor_land_use_type_w is not None else "Default"),
                MetadataWrite(8, 3, m.minor_residue_management_type_w.name if m.minor_residue_management_type_w is not None else "Default"),
                MetadataWrite(9, 3, m.minor_yield_w if m.minor_yield_w is not None else "Default"),
            ]
        if m.is_without():
            mw += [
                MetadataWrite(1, 4, units),
                MetadataWrite(2, 4, m.land_use_type_wo.name),
                MetadataWrite(3, 4, m.tillage_management_type_wo.name),
                MetadataWrite(4, 4, m.organic_input_type_wo.name),
                MetadataWrite(5, 4, m.residue_management_type_wo.name),
                MetadataWrite(6, 4, m.crop_yield_t2_wo if m.crop_yield_t2_wo is not None else "Default"),
                MetadataWrite(7, 4, m.minor_land_use_type_wo.name if m.minor_land_use_type_wo is not None else "Default"),
                MetadataWrite(8, 4, m.minor_residue_management_type_wo.name if m.minor_residue_management_type_wo is not None else "Default"),
                MetadataWrite(9, 4, m.minor_yield_wo if m.minor_yield_wo is not None else "Default"),
            ]
        mw += [
            MetadataWrite(2, 6, m.land_use_type_thread.format_comments()),
            MetadataWrite(3, 6, m.tillage_management_type_thread.format_comments()),
            MetadataWrite(4, 6, m.organic_input_type_thread.format_comments()),
            MetadataWrite(5, 6, m.residue_management_type_thread.format_comments()),
            MetadataWrite(6, 6, m.crop_yield_t2_thread.format_comments()),
        ]

        dur = self._project_duration
        ai_w = [("Annual Cropland (ha)", self._units_breakdown_w[:dur])]
        ai_wo = [("Annual Cropland (ha)", self._units_breakdown_wo[:dur])]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="Annual Cropland",
            result_rows=self._standard_result_rows(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4),
            metadata_writes=mw,
            additional_indicator_rows_w=ai_w,
            additional_indicator_rows_wo=ai_wo,
            total_emissions=self._balance_total(),
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )


@dataclass
class SetAsideReport(LandModuleReport):
    module: api_models.SetAside

    def __post_init__(self):
        self.calculator = calculators.SetAsideCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._extract_land_base()

        m = self.module
        units = m.area
        mw = [
            MetadataWrite(1, 1, "Hectares"),
            MetadataWrite(2, 1, "Is set aside"),
        ]
        if m.is_start():
            mw += [MetadataWrite(1, 2, units), MetadataWrite(2, 2, m.is_set_aside_start)]
        if m.is_with():
            mw += [MetadataWrite(1, 3, units), MetadataWrite(2, 3, m.is_set_aside_w)]
        if m.is_without():
            mw += [MetadataWrite(1, 4, units), MetadataWrite(2, 4, m.is_set_aside_wo)]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="Set Aside",
            result_rows=self._standard_result_rows(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4),
            metadata_writes=mw,
            total_emissions=self._balance_total(),
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )


@dataclass
class GrasslandReport(LandModuleReport):
    module: api_models.Grassland

    def __post_init__(self):
        self.calculator = calculators.GrasslandCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._extract_land_base()

        m = self.module
        units = m.area
        mw = [
            MetadataWrite(1, 1, "Hectares"),
            MetadataWrite(2, 1, "Grassland management"),
            MetadataWrite(3, 1, "Yield"),
            MetadataWrite(4, 1, "Fire occurrence (yes/no)"),
            MetadataWrite(5, 1, "Fire periodicity (years)"),
            MetadataWrite(6, 1, "Fire impact (%)"),
        ]
        if m.is_start():
            mw += [
                MetadataWrite(1, 2, units),
                MetadataWrite(2, 2, m.grassland_management_type_start.name),
                MetadataWrite(3, 2, m.yield_start),
                MetadataWrite(4, 2, "Yes" if m.is_fire_used_start else "No"),
                MetadataWrite(5, 2, m.fire_periodicity_start),
                MetadataWrite(6, 2, m.fire_impact_start),
            ]
        if m.is_with():
            mw += [
                MetadataWrite(1, 3, units),
                MetadataWrite(2, 3, m.grassland_management_type_w.name),
                MetadataWrite(3, 3, m.yield_w),
                MetadataWrite(4, 3, "Yes" if m.is_fire_used_w else "No"),
                MetadataWrite(5, 3, m.fire_periodicity_w),
                MetadataWrite(6, 3, m.fire_impact_w),
            ]
        if m.is_without():
            mw += [
                MetadataWrite(1, 4, units),
                MetadataWrite(2, 4, m.grassland_management_type_wo.name),
                MetadataWrite(3, 4, m.yield_wo),
                MetadataWrite(4, 4, "Yes" if m.is_fire_used_wo else "No"),
                MetadataWrite(5, 4, m.fire_periodicity_wo),
                MetadataWrite(6, 4, m.fire_impact_wo),
            ]
        mw += [
            MetadataWrite(3, 6, m.yield_thread.format_comments()),
            MetadataWrite(4, 6, m.is_fire_used_thread.format_comments()),
            MetadataWrite(5, 6, m.fire_periodicity_thread.format_comments()),
            MetadataWrite(6, 6, m.fire_impact_thread.format_comments()),
        ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="Grassland",
            result_rows=self._standard_result_rows(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4),
            metadata_writes=mw,
            total_emissions=self._balance_total(),
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )


@dataclass
class OtherLandReport(LandModuleReport):
    module: api_models.OtherLand

    def __post_init__(self):
        self.calculator = calculators.OtherLandCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._extract_land_base()
        m = self.module
        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title=m.module_type.name,
            result_rows=self._standard_result_rows(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4),
            metadata_writes=[],
            total_emissions=self._balance_total(),
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )


@dataclass
class CoastalWetlandReport(LandModuleReport):
    module: api_models.CoastalWetland

    def __post_init__(self):
        self.calculator: calculators.CoastalWetlandCalculator = calculators.CoastalWetlandCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._extract_land_base()

        # CoastalWetland adds drainage CO2 to soil_co2
        drainage_co2 = self._extract(
            self.emissions_set, math_utils.ActivityTypes.DRAINAGE, math_utils.GasTypes.CO2
        )
        soil_co2 = _add(soil_co2, drainage_co2)

        m = self.module
        c = self.calculator
        units = m.area
        mw = [
            MetadataWrite(1, 1, "Hectares"),
            MetadataWrite(2, 1, "Type of vegetation"),
            MetadataWrite(3, 1, "Area under drainage"),
            MetadataWrite(4, 1, "Drained area excavated"),
            MetadataWrite(5, 1, "Are not drained or rewetted"),
            MetadataWrite(6, 1, "Area with restored vegetation (ha)"),
            MetadataWrite(7, 1, "Type of soil"),
            MetadataWrite(8, 1, "Soil carbon (tC/ha)"),
            MetadataWrite(9, 1, "% C lost after excavation (%)"),
            MetadataWrite(10, 1, "AGB (tC/ha)"),
            MetadataWrite(11, 1, "BGB (tC/ha)"),
            MetadataWrite(12, 1, "Litter (tC/ha)"),
            MetadataWrite(13, 1, "Deadwood (tC/ha)"),
            MetadataWrite(14, 1, "Average salinity"),
        ]
        for col, is_state, sfx in [
            (2, m.is_start(), "start"),
            (3, m.is_with(), "w"),
            (4, m.is_without(), "wo"),
        ]:
            if not is_state:
                continue
            mw += [
                MetadataWrite(1, col, units),
                MetadataWrite(2, col, m.land_use_type.name),
                MetadataWrite(3, col, getattr(m, f"area_under_drainage_{sfx}")),
                MetadataWrite(4, col, getattr(m, f"drained_area_excavated_{sfx}")),
                MetadataWrite(5, col, getattr(m, f"area_not_drained_or_rewetted_{sfx}")),
                MetadataWrite(6, col, getattr(m, f"area_w_restored_vegetation_{sfx}")),
                MetadataWrite(7, col, m.soil_type_t2.name if m.soil_type_t2 is not None else "Default"),
                MetadataWrite(8, col, getattr(m, f"soc_t2_{sfx}") if getattr(m, f"soc_t2_{sfx}") is not None else "Default"),
                MetadataWrite(9, col, getattr(m, f"pc_c_lost_after_excavation_t2_{sfx}")),
                MetadataWrite(10, col, c.agb.value),
                MetadataWrite(11, col, c.bgb.value),
                MetadataWrite(12, col, c.litter.value),
                MetadataWrite(13, col, c.dw.value),
                MetadataWrite(14, col, c.salinity_type.value),
            ]
        mw += [
            MetadataWrite(3, 6, m.area_under_drainage_thread.format_comments()),
            MetadataWrite(4, 6, m.drained_area_excavated_thread.format_comments()),
            MetadataWrite(5, 6, m.area_not_drained_or_rewetted_thread.format_comments()),
            MetadataWrite(6, 6, m.area_w_restored_vegetation_thread.format_comments()),
        ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="Coastal Wetland",
            result_rows=self._standard_result_rows(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4),
            metadata_writes=mw,
            total_emissions=self._balance_total(),
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )


def _aggregate_minor_seasons_into_emissions_sets(
    emissions_set: list,
    emissions_set_w: list,
    emissions_set_wo: list,
    minor_seasons: list,
    calculator_cls,
) -> tuple[list, list, list, list]:
    """Append each minor season's balance / total_w / total_wo entries to the
    main module's emission lists, and collect their inventories, so that
    downstream extract_emissions() sees a fully aggregated picture (main
    module + every minor season) and the report's inventory items include
    minor-season contributions.

    The emission values added per minor season come from
    ``Result(*calculator_cls(season).calculate()).balance`` (and
    ``.total_w`` / ``.total_wo``) — i.e. the minor's own balance (w − wo),
    not a raw with+without sum, and using the minor's own start contribution
    rather than the main module's.

    ``calculator_cls`` is the season-level calculator for the module family —
    ``FloodedRiceSeasonCalculator`` for FloodedRice, ``PerennialCropCalculator``
    for PerennialCropland, ``AnnualCropCalculator`` for AnnualCropland. It MUST
    accept a single minor-season module on instantiation and return a
    ``(results_w, results_wo)`` tuple from ``.calculate()`` consumable by
    ``Result(*…)`` and expose an ``.inventory`` attribute (typically an
    ``Inventory`` instance, possibly ``None``).

    Returns ``(emissions_set, emissions_set_w, emissions_set_wo, minor_inventories)``
    where ``minor_inventories`` is the list of ``minor_calc.inventory`` values
    (in season order, with ``None`` entries preserved).

    See exact-django-webapp-h8z / -ttm / -fqg / -7qn / -flx / -80d.
    """
    from api.calculators import Result

    es = list(emissions_set)
    es_w = list(emissions_set_w)
    es_wo = list(emissions_set_wo)
    minor_inventories: list = []

    for minor_season in minor_seasons:
        minor_calc = calculator_cls(minor_season)
        minor_results = minor_calc.calculate()
        r = Result(*minor_results)
        es.extend(list(r.balance.yearly_emissions_by_sector_by_gas))
        es_w.extend(list(r.total_w.yearly_emissions_by_sector_by_gas))
        es_wo.extend(list(r.total_wo.yearly_emissions_by_sector_by_gas))
        minor_inventories.append(getattr(minor_calc, "inventory", None))

    return es, es_w, es_wo, minor_inventories


def _merge_minor_inventories(main_inventory, minor_inventories: list):
    """Return ``main_inventory + Σ minor_inventories`` aggregated by
    (gas_type, activity).

    Uses ``Inventory.__add__`` which sums entries with matching keys and
    appends new entries otherwise. ``None`` entries in ``minor_inventories``
    are skipped. If ``main_inventory`` is ``None`` the first non-None minor
    is used as the seed. Returns ``None`` if nothing aggregates.

    See exact-django-webapp-80d.
    """
    from math_model.no_time_dependency_final.ghg_inventory_class import Inventory

    result = main_inventory
    for minor_inv in minor_inventories:
        if minor_inv is None:
            continue
        if result is None:
            # Deep-copy via __add__ on an empty inventory keeps the
            # semantics (Inventory.__add__ deep-copies self).
            result = Inventory() + minor_inv
        else:
            result = result + minor_inv
    return result


def _forest_disturbance_metadata_writes(
    disturbance,
    disturbance_index: int,
    base_row: int,
    *,
    is_start: bool,
    is_with: bool,
    is_without: bool,
) -> list[MetadataWrite]:
    """Return the 3-row metadata block for one ForestManagement.Disturbance entry.

    Each disturbance occupies exactly 3 metadata rows (type, recurrence,
    biomass destruction), so the caller must pass
    ``base_row = first_disturbance_row + 3 * disturbance_index`` to avoid
    overlap between disturbances (and to leave a contiguous block before any
    following degradation row). The col=1 label on each row matches the
    field whose value is written at col >= 2 on the same row — fixing the
    label/data row mismatch that the original stride-1 layout had.
    See exact-django-webapp-a34.
    """
    writes: list[MetadataWrite] = [
        MetadataWrite(base_row + 0, 1, f"Disturbance {disturbance_index + 1}: type"),
        MetadataWrite(base_row + 1, 1, f"Disturbance {disturbance_index + 1}: recurrence (years)"),
        MetadataWrite(base_row + 2, 1, f"Disturbance {disturbance_index + 1}: biomass destruction (%)"),
    ]
    for col, is_state, sfx in [
        (2, is_start, "start"),
        (3, is_with, "w"),
        (4, is_without, "wo"),
    ]:
        if not is_state:
            continue
        writes += [
            MetadataWrite(base_row + 0, col, disturbance.disturbance_type.name),
            MetadataWrite(base_row + 1, col, getattr(disturbance, f"recurrence_yrs_{sfx}")),
            MetadataWrite(base_row + 2, col, getattr(disturbance, f"percentage_biomass_destruction_{sfx}")),
        ]
    return writes


def _flooded_rice_minor_season_metadata_writes(
    season,
    season_calc,
    base_row: int,
    season_index: int,
    *,
    is_start: bool,
    is_with: bool,
    is_without: bool,
) -> list[MetadataWrite]:
    """Return the metadata writes for a single FloodedRice minor season.

    Each season occupies exactly 6 metadata rows (area, cultivation_period,
    water_before, water_after, organic_amendment, yield), so the caller must
    pass ``base_row = 8 + 6 * season_index`` to avoid overlap between seasons.

    Following the _forest_disturbance_metadata_writes precedent, the col-1
    label for every row is emitted once, up front, prefixed with
    "Minor season {n}:" (n = season_index + 1) so stacked minor seasons are
    distinguishable and every data row lines up under a label, like every
    other land activity.

    See exact-django-webapp-65h.
    """
    n = season_index + 1
    writes: list[MetadataWrite] = [
        MetadataWrite(base_row + 0, 1, f"Minor season {n}: Hectares"),
        MetadataWrite(base_row + 1, 1, f"Minor season {n}: Cultivation period (days)"),
        MetadataWrite(base_row + 2, 1, f"Minor season {n}: Water management before cultivation"),
        MetadataWrite(base_row + 3, 1, f"Minor season {n}: Water management after cultivation"),
        MetadataWrite(base_row + 4, 1, f"Minor season {n}: Organic amendment"),
        MetadataWrite(base_row + 5, 1, f"Minor season {n}: Yield"),
    ]
    for col, is_state, sfx in [
        (2, is_start, "start"),
        (3, is_with, "w"),
        (4, is_without, "wo"),
    ]:
        if not is_state:
            continue
        cultivation_period_t2 = getattr(season, f"cultivation_period_t2_{sfx}")
        writes += [
            MetadataWrite(base_row + 0, col, season.area),
            MetadataWrite(
                base_row + 1,
                col,
                season_calc.efc_default.cultivation_period if cultivation_period_t2 is None else cultivation_period_t2,
            ),
            MetadataWrite(base_row + 2, col, getattr(season, f"water_management_type_before_cultivation_{sfx}").name),
            MetadataWrite(base_row + 3, col, getattr(season, f"water_management_type_after_cultivation_{sfx}").name),
            MetadataWrite(base_row + 4, col, getattr(season, f"organic_amendment_type_{sfx}").name),
            MetadataWrite(base_row + 5, col, season_calc.yield_default.value),
        ]
    return writes


@dataclass
class FloodedRiceReport(LandModuleReport):
    module: api_models.FloodedRice

    def __post_init__(self):
        self.calculator: calculators.FloodedRiceSeasonCalculator = calculators.FloodedRiceSeasonCalculator(self.module)
        super().__post_init__()

        # In the calculator path, the main calculator only computes the main
        # season — minor seasons must be merged in to match what the
        # production-path FloodedRiceCalculator does (and what the cache,
        # populated via the API view, already contains).
        # See exact-django-webapp-h8z.
        if not self._from_cache:
            minor_seasons = getattr(self.module, "submodules", []) or []
            if minor_seasons:
                (
                    self.emissions_set,
                    self.emissions_set_w,
                    self.emissions_set_wo,
                    minor_inventories,
                ) = _aggregate_minor_seasons_into_emissions_sets(
                    self.emissions_set,
                    self.emissions_set_w,
                    self.emissions_set_wo,
                    minor_seasons,
                    calculators.FloodedRiceSeasonCalculator,
                )
                # Also fold minor-season inventories into the report's
                # inventory so the Inventory worksheet includes their
                # contributions, not just the main season. See
                # exact-django-webapp-80d.
                self.inventory = _merge_minor_inventories(self.inventory, minor_inventories)
                # Re-save the cache with the merged FloodedRice picture so the
                # next report run reads the same numbers that this run is
                # about to display. Without this, BaseModuleReport.
                # _init_from_calculator() has already cached the (smaller)
                # main-season-only balance, and subsequent report renders
                # would silently downgrade to main-only until the API
                # /results endpoint runs the full FloodedRiceCalculator.
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
                        f"Could not re-save merged FloodedRice cache for module {self.module.pk}: {e}"
                    )

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        es = self.emissions_set

        # FloodedRice uses STRAW_BURNING instead of RESIDUE_BURNING for fire
        # sources, so _extract_land_base() (which assumes RESIDUE_BURNING) is
        # not applicable here.
        biomass_co2 = self._extract(es, math_utils.ActivityTypes.BIOMASS, math_utils.GasTypes.CO2)
        soil_co2 = self._extract(es, math_utils.ActivityTypes.SOIL_CO2_CHANGE, math_utils.GasTypes.CO2)
        soil_n2o = self._extract(es, math_utils.ActivityTypes.SOM, math_utils.GasTypes.N2O)
        fire_n2o = self._extract(es, math_utils.ActivityTypes.STRAW_BURNING, math_utils.GasTypes.N2O)
        fire_ch4 = self._extract(es, math_utils.ActivityTypes.STRAW_BURNING, math_utils.GasTypes.CH4)
        rice_ch4 = self._extract(es, math_utils.ActivityTypes.CH4_EMITTED_RICE, math_utils.GasTypes.CH4)

        # All minor-season contributions are already merged into
        # self.emissions_set by __post_init__ (calculator path) or by the cache
        # writer in the view (cached path). No further per-row summing needed.

        minor_seasons = getattr(m, "submodules", []) or []

        # Metadata: row 1 = number of seasons (col 2), rows 2-7 = main season data
        n_seasons = len(minor_seasons) + 1
        mw = [
            MetadataWrite(1, 2, n_seasons),
            MetadataWrite(1, 1, "Number of seasons"),
            MetadataWrite(2, 1, "Hectares"),
            MetadataWrite(3, 1, "Cultivation period (days)"),
            MetadataWrite(4, 1, "Water management before cultivation"),
            MetadataWrite(5, 1, "Water management after cultivation"),
            MetadataWrite(6, 1, "Organic amendment"),
            MetadataWrite(7, 1, "Yield"),
        ]

        # Main season rows 2-7
        efc = self.calculator.efc_default
        yield_val = self.calculator.yield_default.value
        for col, is_state, sfx in [(2, m.is_start(), "start"), (3, m.is_with(), "w"), (4, m.is_without(), "wo")]:
            if not is_state:
                continue
            mw += [
                MetadataWrite(2, col, m.area),
                MetadataWrite(3, col, efc.cultivation_period if getattr(m, f"cultivation_period_t2_{sfx}") is None else getattr(m, f"cultivation_period_t2_{sfx}")),
                MetadataWrite(4, col, getattr(m, f"water_management_type_before_cultivation_{sfx}").name),
                MetadataWrite(5, col, getattr(m, f"water_management_type_after_cultivation_{sfx}").name),
                MetadataWrite(6, col, getattr(m, f"organic_amendment_type_{sfx}").name),
                MetadataWrite(7, col, yield_val),
            ]

        # Minor-season metadata blocks. Stride is 6 (one per field) — earlier
        # code used stride 1 which silently overwrote consecutive seasons.
        # See exact-django-webapp-65h.
        for i, season in enumerate(minor_seasons):
            season_calc = calculators.FloodedRiceSeasonCalculator(season)
            season_calc.calculate()
            mw += _flooded_rice_minor_season_metadata_writes(
                season,
                season_calc,
                base_row=8 + 6 * i,
                season_index=i,
                is_start=m.is_start(),
                is_with=m.is_with(),
                is_without=m.is_without(),
            )
        mw.append(MetadataWrite(7, 6, m.crop_yield_t2_thread.format_comments()))

        extra_rows = [ResultRow("CH4 from rice cultivation", rice_ch4)]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title=m.module_type.name,
            result_rows=self._standard_result_rows(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4, extra_rows),
            metadata_writes=mw,
            total_emissions=self._balance_total(),
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )


@dataclass
class ForestManagementReport(LandModuleReport):
    module: api_models.ForestManagement

    def __post_init__(self):
        self.calculator: calculators.ForestManagementCalculator = calculators.ForestManagementCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:  # noqa: C901
        activity_title = self.module.activity.name
        m = self.module
        es = self.emissions_set

        def extr(activity, gas):
            return self._extract(es, activity, gas)

        AT = math_utils.ActivityTypes
        GT = math_utils.GasTypes

        rotation_hwp_agb_co2 = extr(AT.HWP_ROTATION_AGB, GT.CO2)
        rotation_hwp_bgb_co2 = extr(AT.HWP_ROTATION_BGB, GT.CO2)
        rotation_agb_co2 = extr(AT.ROTATION_AGB, GT.CO2)
        rotation_agb_n2o = extr(AT.ROTATION_AGB, GT.N2O)
        rotation_agb_ch4 = extr(AT.ROTATION_AGB, GT.CH4)
        rotation_bgb_co2 = extr(AT.ROTATION_BGB, GT.CO2)
        rotation_bgb_n2o = extr(AT.ROTATION_BGB, GT.N2O)
        rotation_bgb_ch4 = extr(AT.ROTATION_BGB, GT.CH4)
        disturbance_agb_co2 = extr(AT.DISTURBANCE_AGB, GT.CO2)
        disturbance_bgb_co2 = extr(AT.DISTURBANCE_BGB, GT.CO2)
        disturbance_fire_agb_n2o = extr(AT.DISTURBANCE_FIRE_AGB, GT.N2O)
        disturbance_fire_agb_ch4 = extr(AT.DISTURBANCE_FIRE_AGB, GT.CH4)
        disturbance_fire_bgb_n2o = extr(AT.DISTURBANCE_FIRE_BGB, GT.N2O)
        disturbance_fire_bgb_ch4 = extr(AT.DISTURBANCE_FIRE_BGB, GT.CH4)
        logging_hwp_agb_co2 = extr(AT.HWP_LOGGING_AGB, GT.CO2)
        logging_hwp_bgb_co2 = extr(AT.HWP_LOGGING_BGB, GT.CO2)
        logging_agb_co2 = extr(AT.LOGGING_AGB, GT.CO2)
        logging_agb_n2o = extr(AT.LOGGING_AGB, GT.N2O)
        logging_agb_ch4 = extr(AT.LOGGING_AGB, GT.CH4)
        logging_bgb_co2 = extr(AT.LOGGING_BGB, GT.CO2)
        logging_bgb_n2o = extr(AT.LOGGING_BGB, GT.N2O)
        logging_bgb_ch4 = extr(AT.LOGGING_BGB, GT.CH4)
        degradation_agb_co2 = extr(AT.DEGRADATION_AGB, GT.CO2)
        degradation_bgb_co2 = extr(AT.DEGRADATION_BGB, GT.CO2)
        degradation_litter_co2 = extr(AT.DEGRADATION_LITTER, GT.CO2)
        degradation_deadwood_co2 = extr(AT.DEGRADATION_DEADWOOD, GT.CO2)
        growth_agb_co2 = extr(AT.AGB_GROWTH, GT.CO2)
        growth_bgb_co2 = extr(AT.BGB_GROWTH, GT.CO2)
        litter_co2 = extr(AT.LITTER, GT.CO2)
        deadwood_co2 = extr(AT.DEADWOOD, GT.CO2)

        hwp_co2 = _add(_add(_add(rotation_hwp_agb_co2, rotation_hwp_bgb_co2), logging_hwp_agb_co2), logging_hwp_bgb_co2)
        fire_n2o = _add(_add(_add(_add(_add(rotation_agb_n2o, rotation_bgb_n2o), disturbance_fire_agb_n2o), disturbance_fire_bgb_n2o), logging_agb_n2o), logging_bgb_n2o)
        fire_ch4 = _add(_add(_add(_add(_add(rotation_agb_ch4, rotation_bgb_ch4), disturbance_fire_agb_ch4), disturbance_fire_bgb_ch4), logging_agb_ch4), logging_bgb_ch4)
        biomass_loss_co2 = _add(_add(_add(_add(_add(_add(_add(_add(_add(
            rotation_agb_co2, rotation_bgb_co2), disturbance_agb_co2), disturbance_bgb_co2),
            logging_agb_co2), logging_bgb_co2), degradation_agb_co2), degradation_bgb_co2),
            degradation_litter_co2), degradation_deadwood_co2)
        biomass_gain_co2 = _add(_add(_add(growth_agb_co2, growth_bgb_co2), litter_co2), deadwood_co2)

        zeros = [0.0] * self._project_duration

        # Metadata
        default = defaults.ForestManagementDefaults(input=m).get_defaults()
        disturbances = list(m.disturbances.all())
        mw = [
            MetadataWrite(1, 1, "Hectares"),
            MetadataWrite(2, 1, "Type of forest"),
            MetadataWrite(3, 1, "Forest category"),
            MetadataWrite(4, 1, "Length of rotation (years)"),
            MetadataWrite(5, 1, "% of harvest used for energy"),
            MetadataWrite(6, 1, "start year of rotations (no of years)"),
            MetadataWrite(7, 1, "Harvesting recurrence (years)"),
            MetadataWrite(8, 1, "timber harvested (% AGB logged)"),
            MetadataWrite(9, 1, "Biomass used for Energy (%)"),
            MetadataWrite(10, 1, "start year of harvesting (no of years)"),
            MetadataWrite(11, 1, "AGB (tC/ha)", fill="LIGHT_RED"),
            MetadataWrite(12, 1, "BGB (tC/ha)", fill="LIGHT_RED"),
            MetadataWrite(13, 1, "AGB growth rate <=20 years (tC/ha)", fill="LIGHT_RED"),
            MetadataWrite(14, 1, "BGB growth rate <=20 years (tC/ha)", fill="LIGHT_RED"),
            MetadataWrite(15, 1, "Litter (tC/ha)", fill="LIGHT_RED"),
            MetadataWrite(16, 1, "Deadwood (tC/ha)", fill="LIGHT_RED"),
        ]
        for col, is_state, sfx in [(2, m.is_start(), "start"), (3, m.is_with(), "w"), (4, m.is_without(), "wo")]:
            if not is_state:
                continue
            mw += [
                MetadataWrite(1, col, m.area),
                MetadataWrite(2, col, m.forest_type.name),
                MetadataWrite(3, col, m.forest_condition_type.name),
                MetadataWrite(4, col, getattr(m, f"rotation_length_yrs_{sfx}")),
                MetadataWrite(5, col, getattr(m, f"rotation_percentage_biomass_for_energy_{sfx}")),
                MetadataWrite(6, col, getattr(m, f"rotation_start_year_t2_{sfx}")),
                MetadataWrite(7, col, getattr(m, f"logging_recurrence_yrs_{sfx}")),
                MetadataWrite(8, col, getattr(m, f"logging_percentage_agb_logged_{sfx}")),
                MetadataWrite(9, col, getattr(m, f"logging_percentage_biomass_for_energy_{sfx}")),
                MetadataWrite(10, col, getattr(m, f"logging_start_year_t2_{sfx}")),
                MetadataWrite(11, col, getattr(default, f"agb_t2_{sfx}_default"), fill="LIGHT_RED"),
                MetadataWrite(12, col, getattr(default, f"bgb_t2_{sfx}_default"), fill="LIGHT_RED"),
                MetadataWrite(13, col, getattr(default, f"agb_growth_rate_le_20_yrs_t2_{sfx}_default"), fill="LIGHT_RED"),
                MetadataWrite(14, col, getattr(default, f"bgb_growth_rate_le_20_yrs_t2_{sfx}_default"), fill="LIGHT_RED"),
                MetadataWrite(15, col, getattr(default, f"litter_t2_{sfx}_default"), fill="LIGHT_RED"),
                MetadataWrite(16, col, getattr(default, f"deadwood_t2_{sfx}_default"), fill="LIGHT_RED"),
            ]
        # Disturbance metadata blocks. Stride is 3 (one row per field) —
        # earlier code used stride 1 which silently overwrote consecutive
        # disturbances, AND placed the col=1 labels one row above their
        # col >= 2 data, AND used the typo "distrubance". See
        # exact-django-webapp-a34.
        for i, dist in enumerate(disturbances):
            mw += _forest_disturbance_metadata_writes(
                dist,
                disturbance_index=i,
                base_row=17 + 3 * i,
                is_start=m.is_start(),
                is_with=m.is_with(),
                is_without=m.is_without(),
            )
        deg_row = 17 + 3 * len(disturbances)
        mw.append(MetadataWrite(deg_row, 1, "average yearly degradation (%)"))
        for col, is_state, sfx in [(2, m.is_start(), "start"), (3, m.is_with(), "w"), (4, m.is_without(), "wo")]:
            if not is_state:
                continue
            mw.append(MetadataWrite(deg_row, col, getattr(m, f"average_yearly_degradation_percentage_{sfx}")))
        mw += [
            MetadataWrite(4, 6, m.rotation_length_yrs_thread.format_comments()),
            MetadataWrite(5, 6, m.rotation_percentage_biomass_for_energy_thread.format_comments()),
            MetadataWrite(7, 6, m.logging_recurrence_yrs_thread.format_comments()),
            MetadataWrite(8, 6, m.logging_percentage_agb_logged_thread.format_comments()),
            MetadataWrite(deg_row, 6, m.average_yearly_degradation_percentage_thread.format_comments()),
        ]

        # ForestManagement result rows: standard 5 rows (biomass/soil zeros) + HWP, loss, gain
        result_rows = [
            ResultRow("CO2 in biomass", zeros),
            ResultRow("CO2 in soils", zeros),
            ResultRow("N2O in soils", zeros),
            ResultRow("N2O from fires", fire_n2o),
            ResultRow("CH4 from fires", fire_ch4),
            ResultRow("CO2 from HWP (rotation and logging)", hwp_co2),
            ResultRow("CO2 from biomass loss", biomass_loss_co2),
            ResultRow("CO2 from biomass gain", biomass_gain_co2),
        ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="Forest Management",
            result_rows=result_rows,
            metadata_writes=mw,
            total_emissions=self._balance_total(),
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )


@dataclass
class SettlementReport(LandModuleReport):
    module: api_models.Settlement

    def __post_init__(self):
        self.calculator = calculators.SettlementCalculator(self.module)
        super().__post_init__()

    def _compute_submodule_emissions(self, dur: int):
        from api.calculators import Result

        buildings_co2 = [0.0] * dur
        roads_co2 = [0.0] * dur
        infra_co2 = [0.0] * dur

        for submodule in self.module.submodules:
            if isinstance(submodule, api_models.OtherInfrastructure):
                continue
            CalculatorClass = (
                calculators.RoadCalculator
                if isinstance(submodule, api_models.Road)
                else calculators.BuildingCalculator
            )
            try:
                sub_es = Result(*CalculatorClass(submodule).calculate()).balance.yearly_emissions_by_sector_by_gas
            except Exception as e:
                log.error(f"Cannot calculate submodule {submodule.module_type.name}: {e}")
                raise NotReadyError(f"Cannot calculate submodule {submodule.module_type.name}: {e}")

            val = extract_emissions(sub_es, math_utils.ActivityTypes.ROADS, math_utils.GasTypes.CO2, duration=dur)
            if isinstance(submodule, api_models.Road):
                roads_co2 = _add(roads_co2, val)
            elif isinstance(submodule, api_models.Building):
                buildings_co2 = _add(buildings_co2, val)

        return buildings_co2, roads_co2, infra_co2

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        dur = self._project_duration

        # Settlement is a land module: its balance carries land-use-change
        # emissions (biomass / SOC / SOM-N2O / fire) in addition to the
        # roads/buildings submodules. These 5 rows were hardcoded to zeros
        # and excluded from the total: see exact-django-webapp-jcb.
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._extract_land_base()
        buildings_co2, roads_co2, infra_co2 = self._compute_submodule_emissions(dur)

        # Metadata: buildings, roads, other_infrastructures sub-loops
        mw = []
        row = 0
        for i, building in enumerate(m.buildings.all()):
            if i != 0:
                row += 1
            mw += [
                MetadataWrite(1 + row + i, 1, "Type of building"),
                MetadataWrite(2 + row + i, 1, "Area of building (m2)"),
            ]
            for col, is_state, sfx in [(2, m.is_start(), "start"), (3, m.is_with(), "w"), (4, m.is_without(), "wo")]:
                if not is_state:
                    continue
                mw += [
                    MetadataWrite(1 + row + i, col, building.building_type.name),
                    MetadataWrite(2 + row + i, col, getattr(building, f"area_m2_{sfx}")),
                ]
            mw += [
                MetadataWrite(1 + row + i, 6, building.building_type_thread.format_comments()),
                MetadataWrite(2 + row + i, 6, building.area_m2_thread.format_comments()),
            ]
        row += len(list(m.buildings.all())) + 1

        for i, road in enumerate(m.roads.all()):
            if i != 0:
                row += 2
            mw += [
                MetadataWrite(1 + row + i, 1, "Type of road"),
                MetadataWrite(2 + row + i, 1, "Length of road (km)"),
                MetadataWrite(3 + row + i, 1, "Width of road (m)"),
            ]
            for col, is_state, sfx in [(2, m.is_start(), "start"), (3, m.is_with(), "w"), (4, m.is_without(), "wo")]:
                if not is_state:
                    continue
                mw += [
                    MetadataWrite(1 + row + i, col, road.road_type.name),
                    MetadataWrite(2 + row + i, col, getattr(road, f"length_km_{sfx}")),
                    MetadataWrite(3 + row + i, col, getattr(road, f"width_m_{sfx}")),
                ]
            mw += [
                MetadataWrite(1 + row + i, 6, road.road_type_thread.format_comments()),
                MetadataWrite(2 + row + i, 6, road.length_km_thread.format_comments()),
                MetadataWrite(3 + row + i, 6, road.width_m_thread.format_comments()),
            ]
        row += len(list(m.roads.all())) + 2

        for i, infra in enumerate(m.other_infrastructures.all()):
            mw.append(MetadataWrite(2 + row + i, 1, f"Area of infrastructure {i + 1} (m2)"))
            for col, is_state, sfx in [(2, m.is_start(), "start"), (3, m.is_with(), "w"), (4, m.is_without(), "wo")]:
                if not is_state:
                    continue
                mw.append(MetadataWrite(2 + row + i, col, getattr(infra, f"area_m2_{sfx}")))
            mw.append(MetadataWrite(2 + row + i, 6, infra.area_m2_thread.format_comments()))

        result_rows = [
            ResultRow("CO2 in biomass", biomass_co2),
            ResultRow("CO2 in soils", soil_co2),
            ResultRow("N2O in soils", soil_n2o),
            ResultRow("N2O from fires", fire_n2o),
            ResultRow("CH4 from fires", fire_ch4),
            ResultRow("CO2-eq from buildings", buildings_co2),
            ResultRow("CO2-eq from roads", roads_co2),
            ResultRow("CO2-eq from other infrastructure", infra_co2),
        ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title=m.module_type.name,
            result_rows=result_rows,
            metadata_writes=mw,
            total_emissions=self._balance_total(),
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )
