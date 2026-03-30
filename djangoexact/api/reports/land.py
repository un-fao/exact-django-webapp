"""Land module report classes – calculation only, no Excel imports.

Each class implements compute() -> ModuleResult.
"""

from __future__ import annotations

import functools
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
        super().__post_init__()
        length = (
            self.module.activity.implementation_years
            + self.module.activity.capitalization_years
        )
        if self._from_cache:
            self._units_breakdown_w  = [0.0] * length
            self._units_breakdown_wo = [0.0] * length
        else:
            break_w  = getattr(self.calculator.math_w,  "hectares_total", np.zeros(length))
            break_wo = getattr(self.calculator.math_wo, "hectares_total", np.zeros(length))
            self._units_breakdown_w  = list(np.round(break_w,  2))
            self._units_breakdown_wo = list(np.round(break_wo, 2))

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
        total_emissions = _add(
            _add(_add(_add(_add(biomass_co2, soil_co2), soil_n2o), fire_n2o), fire_ch4),
            dom_co2,
        )

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
            total_emissions=total_emissions,
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

    def _add_minor_seasons(self, biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4):
        minor_seasons = getattr(self.module, "minor_seasons", None)
        if not minor_seasons:
            return biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4

        for minor_season in minor_seasons.all():
            minor_calc = calculators.PerennialCropCalculator(minor_season)
            minor_es = []
            if self.module.is_with():
                minor_es += minor_calc.results_w.yearly_emissions_by_sector_by_gas
                if self.calculator.results_start_w is not None:
                    minor_es += self.calculator.results_start_w.yearly_emissions_by_sector_by_gas
            if self.module.is_without():
                minor_es += minor_calc.results_wo.yearly_emissions_by_sector_by_gas
                if self.calculator.results_start_wo is not None:
                    minor_es += minor_calc.results_start_wo.yearly_emissions_by_sector_by_gas

            dur = self._project_duration
            biomass_co2 = _add(biomass_co2, extract_emissions(minor_es, math_utils.ActivityTypes.BIOMASS, math_utils.GasTypes.CO2, duration=dur))
            soil_co2 = _add(soil_co2, extract_emissions(minor_es, math_utils.ActivityTypes.SOIL_CO2_CHANGE, math_utils.GasTypes.CO2, duration=dur))
            soil_n2o = _add(soil_n2o, extract_emissions(minor_es, math_utils.ActivityTypes.SOM, math_utils.GasTypes.N2O, duration=dur))
            fire_n2o = _add(fire_n2o, extract_emissions(minor_es, math_utils.ActivityTypes.RESIDUE_BURNING, math_utils.GasTypes.N2O, duration=dur))
            fire_ch4 = _add(fire_ch4, extract_emissions(minor_es, math_utils.ActivityTypes.RESIDUE_BURNING, math_utils.GasTypes.CH4, duration=dur))

        return biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._extract_land_base()
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._add_minor_seasons(
            biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4
        )
        total_emissions = _add(_add(_add(_add(biomass_co2, soil_co2), soil_n2o), fire_n2o), fire_ch4)

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
            total_emissions=total_emissions,
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

    def _add_minor_seasons(self, biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4):
        minor_seasons = getattr(self.module, "submodules", [])
        dur = self._project_duration
        for minor_season in minor_seasons:
            minor_calc = calculators.AnnualCropCalculator(minor_season)
            minor_es = []
            if self.module.is_with():
                minor_es += minor_calc.results_w.yearly_emissions_by_sector_by_gas
                if self.calculator.results_start_w is not None:
                    minor_es += self.calculator.results_start_w.yearly_emissions_by_sector_by_gas
            if self.module.is_without():
                minor_es += minor_calc.results_wo.yearly_emissions_by_sector_by_gas
                if self.calculator.results_start_wo is not None:
                    minor_es += self.calculator.results_start_wo.yearly_emissions_by_sector_by_gas

            biomass_co2 = _add(biomass_co2, extract_emissions(minor_es, math_utils.ActivityTypes.BIOMASS, math_utils.GasTypes.CO2, duration=dur))
            soil_co2 = _add(soil_co2, extract_emissions(minor_es, math_utils.ActivityTypes.SOIL_CO2_CHANGE, math_utils.GasTypes.CO2, duration=dur))
            soil_n2o = _add(soil_n2o, extract_emissions(minor_es, math_utils.ActivityTypes.SOM, math_utils.GasTypes.N2O, duration=dur))
            fire_n2o = _add(fire_n2o, extract_emissions(minor_es, math_utils.ActivityTypes.RESIDUE_BURNING, math_utils.GasTypes.N2O, duration=dur))
            fire_ch4 = _add(fire_ch4, extract_emissions(minor_es, math_utils.ActivityTypes.RESIDUE_BURNING, math_utils.GasTypes.CH4, duration=dur))

        return biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._extract_land_base()
        biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4 = self._add_minor_seasons(
            biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4
        )
        total_emissions = _add(_add(_add(_add(biomass_co2, soil_co2), soil_n2o), fire_n2o), fire_ch4)

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
            total_emissions=total_emissions,
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
        total_emissions = _add(_add(_add(_add(biomass_co2, soil_co2), soil_n2o), fire_n2o), fire_ch4)

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
            total_emissions=total_emissions,
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
        total_emissions = _add(_add(_add(_add(biomass_co2, soil_co2), soil_n2o), fire_n2o), fire_ch4)

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
            total_emissions=total_emissions,
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
        total_emissions = _add(_add(_add(_add(biomass_co2, soil_co2), soil_n2o), fire_n2o), fire_ch4)
        m = self.module
        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title=m.module_type.name,
            result_rows=self._standard_result_rows(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4),
            metadata_writes=[],
            total_emissions=total_emissions,
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
        total_emissions = _add(
            _add(_add(_add(_add(biomass_co2, soil_co2), soil_n2o), fire_n2o), fire_ch4),
            drainage_co2,
        )

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
            total_emissions=total_emissions,
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )


@dataclass
class FloodedRiceReport(LandModuleReport):
    module: api_models.FloodedRice

    def __post_init__(self):
        self.calculator: calculators.FloodedRiceSeasonCalculator = calculators.FloodedRiceSeasonCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        dur = self._project_duration
        es = self.emissions_set

        # FloodedRice uses STRAW_BURNING instead of RESIDUE_BURNING for fire sources
        biomass_co2 = self._extract(es, math_utils.ActivityTypes.BIOMASS, math_utils.GasTypes.CO2)
        soil_co2 = self._extract(es, math_utils.ActivityTypes.SOIL_CO2_CHANGE, math_utils.GasTypes.CO2)
        soil_n2o = self._extract(es, math_utils.ActivityTypes.SOM, math_utils.GasTypes.N2O)
        fire_n2o = self._extract(es, math_utils.ActivityTypes.STRAW_BURNING, math_utils.GasTypes.N2O)
        fire_ch4 = self._extract(es, math_utils.ActivityTypes.STRAW_BURNING, math_utils.GasTypes.CH4)
        rice_ch4 = self._extract(es, math_utils.ActivityTypes.CH4_EMITTED_RICE, math_utils.GasTypes.CH4)

        # Add submodule seasons
        minor_seasons = getattr(m, "submodules", [])
        for minor_season in minor_seasons:
            minor_calc = calculators.FloodedRiceSeasonCalculator(minor_season)
            minor_calc.calculate()
            minor_es = []
            if m.is_with():
                minor_es += minor_calc.results_w.yearly_emissions_by_sector_by_gas
                if self.calculator.results_start_w is not None:
                    minor_es += self.calculator.results_start_w.yearly_emissions_by_sector_by_gas
            if m.is_without():
                minor_es += minor_calc.results_wo.yearly_emissions_by_sector_by_gas
                if self.calculator.results_start_wo is not None:
                    minor_es += self.calculator.results_start_wo.yearly_emissions_by_sector_by_gas

            biomass_co2 = _add(biomass_co2, extract_emissions(minor_es, math_utils.ActivityTypes.BIOMASS, math_utils.GasTypes.CO2, duration=dur))
            soil_co2 = _add(soil_co2, extract_emissions(minor_es, math_utils.ActivityTypes.SOIL_CO2_CHANGE, math_utils.GasTypes.CO2, duration=dur))
            soil_n2o = _add(soil_n2o, extract_emissions(minor_es, math_utils.ActivityTypes.SOM, math_utils.GasTypes.N2O, duration=dur))
            fire_n2o = _add(fire_n2o, extract_emissions(minor_es, math_utils.ActivityTypes.STRAW_BURNING, math_utils.GasTypes.N2O, duration=dur))
            rice_ch4 = _add(rice_ch4, extract_emissions(minor_es, math_utils.ActivityTypes.CH4_EMITTED_RICE, math_utils.GasTypes.CH4, duration=dur))

        total_emissions = _add(_add(_add(_add(_add(biomass_co2, soil_co2), soil_n2o), fire_n2o), fire_ch4), rice_ch4)

        # Metadata: row 1 = number of seasons (col 2), rows 2-7 = main season data
        n_seasons = len(minor_seasons) + 1
        mw = [MetadataWrite(1, 2, n_seasons)]

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

        # Sub-season rows start at offset 8 (+i for each season)
        for i, season in enumerate(minor_seasons):
            season_calc = calculators.FloodedRiceSeasonCalculator(season)
            season_calc.calculate()
            for col, is_state, sfx in [(2, m.is_start(), "start"), (3, m.is_with(), "w"), (4, m.is_without(), "wo")]:
                if not is_state:
                    continue
                mw += [
                    MetadataWrite(8 + i, col, season.area),
                    MetadataWrite(9 + i, col, season_calc.efc_default.cultivation_period),
                    MetadataWrite(10 + i, col, getattr(season, f"water_management_type_before_cultivation_{sfx}").name),
                    MetadataWrite(11 + i, col, getattr(season, f"water_management_type_after_cultivation_{sfx}").name),
                    MetadataWrite(12 + i, col, getattr(season, f"organic_amendment_type_{sfx}").name),
                    MetadataWrite(13 + i, col, season_calc.yield_default.value),
                ]
        mw.append(MetadataWrite(7, 6, m.crop_yield_t2_thread.format_comments()))

        extra_rows = [ResultRow("CH4 from rice cultivation", rice_ch4)]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title=m.module_type.name,
            result_rows=self._standard_result_rows(biomass_co2, soil_co2, soil_n2o, fire_n2o, fire_ch4, extra_rows),
            metadata_writes=mw,
            total_emissions=total_emissions,
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
        total_emissions = functools.reduce(_add, [
            zeros,
            rotation_hwp_agb_co2, rotation_hwp_bgb_co2,
            rotation_agb_n2o, rotation_agb_ch4,
            rotation_bgb_n2o, rotation_bgb_ch4,
            rotation_agb_co2, rotation_bgb_co2,
            disturbance_agb_co2, disturbance_bgb_co2,
            disturbance_fire_agb_n2o, disturbance_fire_agb_ch4,
            disturbance_fire_bgb_n2o, disturbance_fire_bgb_ch4,
            logging_hwp_agb_co2, logging_hwp_bgb_co2,
            logging_agb_n2o, logging_agb_ch4,
            logging_bgb_n2o, logging_bgb_ch4,
            logging_agb_co2, logging_bgb_co2,
            degradation_agb_co2, degradation_bgb_co2,
            growth_agb_co2, growth_bgb_co2,
            litter_co2, deadwood_co2,
            degradation_litter_co2, degradation_deadwood_co2,
        ])

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
        for i, dist in enumerate(disturbances):
            mw += [
                MetadataWrite(17 + i, 1, f"Disturbance {i + 1}: type"),
                MetadataWrite(18 + i, 1, "distrubance recurrence (years)"),
                MetadataWrite(19 + i, 1, "biomass destruction (%)"),
            ]
            for col, is_state, sfx in [(2, m.is_start(), "start"), (3, m.is_with(), "w"), (4, m.is_without(), "wo")]:
                if not is_state:
                    continue
                mw += [
                    MetadataWrite(18 + i, col, dist.disturbance_type.name),
                    MetadataWrite(19 + i, col, getattr(dist, f"recurrence_yrs_{sfx}")),
                    MetadataWrite(20 + i, col, getattr(dist, f"percentage_biomass_destruction_{sfx}")),
                ]
        deg_row = 17 + len(disturbances)
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
            total_emissions=total_emissions,
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
        zeros = [0.0] * dur

        buildings_co2, roads_co2, infra_co2 = self._compute_submodule_emissions(dur)
        total_emissions = _add(_add(buildings_co2, roads_co2), infra_co2)

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
            ResultRow("CO2 in biomass", zeros),
            ResultRow("CO2 in soils", zeros),
            ResultRow("N2O in soils", zeros),
            ResultRow("N2O from fires", zeros),
            ResultRow("CH4 from fires", zeros),
            ResultRow("CO2-eq from buildings", buildings_co2),
            ResultRow("CO2-eq from roads", roads_co2),
            ResultRow("CO2-eq from other infrastructure", infra_co2),
        ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title=m.module_type.name,
            result_rows=result_rows,
            metadata_writes=mw,
            total_emissions=total_emissions,
            units_breakdown_w=self._units_breakdown_w,
            units_breakdown_wo=self._units_breakdown_wo,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items(activity_title),
        )
