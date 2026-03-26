"""Non-land module report classes – calculation only, no Excel imports.

Each class implements compute() -> ModuleResult.

MetadataWrite offset convention:
- For modules WITH a metadata section title: offset 0 = title row (LIGHT_BLUE,
  written by renderer), offset 1 = first data row.
- For modules WITHOUT a metadata section title (Energy, Input, Irrigation,
  Transport, Processing, Packaging, Storage): offset 0 = first data row.
  These modules set metadata_section_title="" in their ModuleResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import logging as log
import numpy as np

import api.models as api_models
import api.calculators as calculators
import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils

from .base import BaseModuleReport, NotReadyError
from .data_types import InventoryItem, MetadataWrite, ModuleResult, ResultRow
from .extractors import _add, extract_emissions


def _zeros(n: int) -> list[float]:
    return [0.0] * n


# ---------------------------------------------------------------------------
# Waterbody
# ---------------------------------------------------------------------------

@dataclass
class WaterbodyReport(BaseModuleReport):
    module: api_models.Waterbody

    def __post_init__(self):
        self.calculator = calculators.WaterbodyCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        es = self.emissions_set

        ch4 = self._extract(es, math_utils.ActivityTypes.COASTAL_WATERBODIES, math_utils.GasTypes.CH4)
        total = list(ch4)

        mw = [
            MetadataWrite(1, 1, "Waterbody type"),
            MetadataWrite(2, 1, "Trophic class"),
        ]
        if m.is_start():
            mw += [
                MetadataWrite(1, 2, m.waterbody_type.name),
                MetadataWrite(2, 2, m.trophic_type_start.name),
            ]
        if m.is_with():
            mw += [
                MetadataWrite(1, 3, m.waterbody_type.name),
                MetadataWrite(2, 3, m.trophic_type_w.name),
            ]
        if m.is_without():
            mw += [
                MetadataWrite(1, 4, m.waterbody_type.name),
                MetadataWrite(2, 4, m.trophic_type_wo.name),
            ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="Waterbody",
            result_rows=[ResultRow("CH4 from waterbody management", ch4)],
            metadata_writes=mw,
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


# ---------------------------------------------------------------------------
# Aquaculture
# ---------------------------------------------------------------------------

@dataclass
class AquacultureReport(BaseModuleReport):
    module: api_models.Aquaculture

    def __post_init__(self):
        self.calculator = calculators.AquacultureCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        es = self.emissions_set

        fish_n2o = self._extract(es, math_utils.ActivityTypes.N20_FIELD, math_utils.GasTypes.N2O)
        electricity_co2_eq = self._extract(es, math_utils.ActivityTypes.ELECTRICITY, math_utils.GasTypes.CO2)
        total = _add(fish_n2o, electricity_co2_eq)

        mw = [
            MetadataWrite(1, 1, "Production (tons fish/year)"),
            MetadataWrite(2, 1, "electricity used for fish production (KWh/ t of production)"),
        ]
        if m.is_start():
            mw += [
                MetadataWrite(1, 2, m.annual_production_start),
                MetadataWrite(2, 2, m.electricity_used_t2_start),
            ]
        if m.is_with():
            mw += [
                MetadataWrite(1, 3, m.annual_production_w),
                MetadataWrite(2, 3, m.electricity_used_t2_w),
            ]
        if m.is_without():
            mw += [
                MetadataWrite(1, 4, m.annual_production_wo),
                MetadataWrite(2, 4, m.electricity_used_t2_wo),
            ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="Aquaculture",
            result_rows=[
                ResultRow("N2O from fish", fish_n2o),
                ResultRow("CO2-eq from electricity", electricity_co2_eq),
            ],
            metadata_writes=mw,
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


# ---------------------------------------------------------------------------
# Fishery (base) / SmallFishery / LargeFishery
# ---------------------------------------------------------------------------

@dataclass
class FisheryReport(BaseModuleReport):
    """Abstract base providing shared fishery emission computation.

    Subclasses must set self.calculator before calling super().__post_init__().
    """

    def _compute_fishery(self, metadata_section_title: str, mw: list[MetadataWrite]) -> ModuleResult:
        m = self.module
        activity_title = m.activity.name
        es = self.emissions_set

        liquid_fuel_co2 = self._extract(es, math_utils.ActivityTypes.CATCH, math_utils.GasTypes.CO2)
        liquid_fuel_n2o = self._extract(es, math_utils.ActivityTypes.CATCH, math_utils.GasTypes.N2O)
        liquid_fuel_ch4 = self._extract(es, math_utils.ActivityTypes.CATCH, math_utils.GasTypes.CH4)
        refrigeration_hfc = self._extract(es, math_utils.ActivityTypes.REFRIGERANT, math_utils.GasTypes.OTHER)
        electricity_co2_eq = self._extract(es, math_utils.ActivityTypes.ICE, math_utils.GasTypes.OTHER)

        total = _add(
            _add(_add(_add(liquid_fuel_co2, liquid_fuel_n2o), liquid_fuel_ch4),
                 refrigeration_hfc),
            electricity_co2_eq,
        )

        dur = m.activity.implementation_years + m.activity.capitalization_years
        units_catch_w = [float(m.total_catch_yr_w)] * dur if m.is_with() else []

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title=metadata_section_title,
            result_rows=[
                ResultRow("CO2 from liquid fuels consumption", liquid_fuel_co2),
                ResultRow("N2O from liquid fuels consumption", liquid_fuel_n2o),
                ResultRow("CH4 from liquid fuels consumption", liquid_fuel_ch4),
                ResultRow("HFC from refrigeration", refrigeration_hfc),
                ResultRow("CO2-eq from electricity", electricity_co2_eq),
            ],
            metadata_writes=mw,
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            units_catch_w=units_catch_w,
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


@dataclass
class SmallFisheryReport(FisheryReport):
    module: api_models.SmallFishery

    def __post_init__(self):
        self.calculator = calculators.SmallFisheryCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        m = self.module
        quantity_of_ice = self.calculator.tonnes_ice_default
        kw_tonnes = self.calculator.kw_tonnes

        mw = [
            MetadataWrite(1, 1, "Type of fisheries"),
            MetadataWrite(2, 1, "Gear category"),
            MetadataWrite(3, 1, "Total catch (t/year)"),
            MetadataWrite(4, 1, "% of refrigerant systems"),
            MetadataWrite(5, 1, "% of total catch preserved with ice"),
            MetadataWrite(6, 1, "Fuel use intensity (l/t)"),
            MetadataWrite(7, 1, "Quantity of ice (t ice/t of catch)"),
            MetadataWrite(8, 1, "Electricity used for ice production (KWh/ t of ice)"),
        ]
        if m.is_start():
            mw += [
                MetadataWrite(1, 2, m.fishery_type.name),
                MetadataWrite(2, 2, m.gear_type_start.name),
                MetadataWrite(3, 2, m.total_catch_yr_start),
                MetadataWrite(4, 2, m.refrigerant_pc_start),
                MetadataWrite(5, 2, m.ice_preserved_catch_pc_start),
                MetadataWrite(6, 2, self.calculator.fui_start),
                MetadataWrite(7, 2, quantity_of_ice),
                MetadataWrite(8, 2, kw_tonnes),
            ]
        if m.is_with():
            mw += [
                MetadataWrite(1, 3, m.fishery_type.name),
                MetadataWrite(2, 3, m.gear_type_w.name),
                MetadataWrite(3, 3, m.total_catch_yr_w),
                MetadataWrite(4, 3, m.refrigerant_pc_w),
                MetadataWrite(5, 3, m.ice_preserved_catch_pc_w),
                MetadataWrite(6, 3, self.calculator.fui_w),
                MetadataWrite(7, 3, quantity_of_ice),
                MetadataWrite(8, 3, kw_tonnes),
            ]
        if m.is_without():
            mw += [
                MetadataWrite(1, 4, m.fishery_type.name),
                MetadataWrite(2, 4, m.gear_type_wo.name),
                MetadataWrite(3, 4, m.total_catch_yr_wo),
                MetadataWrite(4, 4, m.refrigerant_pc_wo),
                MetadataWrite(5, 4, m.ice_preserved_catch_pc_wo),
                MetadataWrite(6, 4, self.calculator.fui_wo),
                MetadataWrite(7, 4, quantity_of_ice),
                MetadataWrite(8, 4, kw_tonnes),
            ]
        mw += [
            MetadataWrite(2, 6, m.gear_type_thread.format_comments() if m.gear_type_thread else ""),
            MetadataWrite(3, 6, m.total_catch_yr_thread.format_comments() if m.total_catch_yr_thread else ""),
            MetadataWrite(4, 6, m.refrigerant_pc_thread.format_comments() if m.refrigerant_pc_thread else ""),
            MetadataWrite(5, 6, m.ice_preserved_catch_pc_thread.format_comments() if m.ice_preserved_catch_pc_thread else ""),
        ]
        return self._compute_fishery("Small Fishery", mw)


@dataclass
class LargeFisheryReport(FisheryReport):
    module: api_models.LargeFishery

    def __post_init__(self):
        self.calculator = calculators.LargeFisheryCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        m = self.module
        quantity_of_ice = self.calculator.tonnes_ice_default
        kw_tonnes = self.calculator.kw_tonnes

        # NOTE: original code uses "Small Fishery" as section title even for LargeFishery
        mw = [
            MetadataWrite(1, 1, "Type of fisheries"),
            MetadataWrite(2, 1, "Gear category"),
            MetadataWrite(3, 1, "Total catch (t/year)"),
            MetadataWrite(4, 1, "% of refrigerant systems"),
            MetadataWrite(5, 1, "% of total catch preserved with ice"),
            MetadataWrite(6, 1, "Fuel use intensity (l/t)"),
            MetadataWrite(7, 1, "Quantity of ice (t ice/t of catch)"),
            MetadataWrite(8, 1, "Electricity used for ice production (KWh/ t of ice)"),
        ]
        if m.is_start():
            mw += [
                MetadataWrite(1, 2, m.fish_type.name),
                MetadataWrite(2, 2, m.gear_type_start.name),
                MetadataWrite(3, 2, m.total_catch_yr_start),
                MetadataWrite(4, 2, m.refrigerant_pc_start),
                MetadataWrite(5, 2, m.ice_preserved_catch_pc_start),
                MetadataWrite(6, 2, self.calculator.fui_default_start),
                MetadataWrite(7, 2, quantity_of_ice),
                MetadataWrite(8, 2, kw_tonnes),
            ]
        if m.is_with():
            mw += [
                MetadataWrite(1, 3, m.fish_type.name),
                MetadataWrite(2, 3, m.gear_type_w.name),
                MetadataWrite(3, 3, m.total_catch_yr_w),
                MetadataWrite(4, 3, m.refrigerant_pc_w),
                MetadataWrite(5, 3, m.ice_preserved_catch_pc_w),
                MetadataWrite(6, 3, self.calculator.fui_default_w),
                MetadataWrite(7, 3, quantity_of_ice),
                MetadataWrite(8, 3, kw_tonnes),
            ]
        if m.is_without():
            mw += [
                MetadataWrite(1, 4, m.fish_type.name),
                MetadataWrite(2, 4, m.gear_type_wo.name),
                MetadataWrite(3, 4, m.total_catch_yr_wo),
                MetadataWrite(4, 4, m.refrigerant_pc_wo),
                MetadataWrite(5, 4, m.ice_preserved_catch_pc_wo),
                MetadataWrite(6, 4, self.calculator.fui_default_wo),
                MetadataWrite(7, 4, quantity_of_ice),
                MetadataWrite(8, 4, kw_tonnes),
            ]
        mw += [
            MetadataWrite(2, 6, m.gear_type_thread.format_comments() if m.gear_type_thread else ""),
            MetadataWrite(3, 6, m.total_catch_yr_thread.format_comments() if m.total_catch_yr_thread else ""),
            MetadataWrite(4, 6, m.refrigerant_pc_thread.format_comments() if m.refrigerant_pc_thread else ""),
            MetadataWrite(5, 6, m.ice_preserved_catch_pc_thread.format_comments() if m.ice_preserved_catch_pc_thread else ""),
        ]
        return self._compute_fishery("Large Fishery", mw)


# ---------------------------------------------------------------------------
# Livestock
# ---------------------------------------------------------------------------

@dataclass
class LivestockReport(BaseModuleReport):
    module: api_models.Livestock

    def __post_init__(self):
        self.calculator = calculators.LivestockCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        es = self.emissions_set

        enteric_ch4 = self._extract(es, math_utils.ActivityTypes.METHANE_ENTERIC_FERMENTATION, math_utils.GasTypes.CH4)
        mm_other_ch4 = self._extract(es, math_utils.ActivityTypes.METHANE_MANURE_MANAGEMENT_SYSTEM, math_utils.GasTypes.CH4)
        mm_other_direct_n2o = self._extract(es, math_utils.ActivityTypes.NITROUS_MANURE_MANAGEMENT_SYSTEM, math_utils.GasTypes.N2O)
        mm_other_leach_n2o = self._extract(es, math_utils.ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM, math_utils.GasTypes.N2O)
        mm_other_vol_n2o = self._extract(es, math_utils.ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_SYSTEM, math_utils.GasTypes.N2O)
        mm_prp_ch4 = self._extract(es, math_utils.ActivityTypes.METHANE_MANURE_MANAGEMENT_PRP, math_utils.GasTypes.CH4)
        mm_prp_direct_n2o = self._extract(es, math_utils.ActivityTypes.NITROUS_MANURE_MANAGEMENT_PRP, math_utils.GasTypes.N2O)
        mm_prp_leach_n2o = self._extract(es, math_utils.ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_PRP, math_utils.GasTypes.N2O)
        mm_prp_vol_n2o = self._extract(es, math_utils.ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_PRP, math_utils.GasTypes.N2O)

        total = _add(
            _add(_add(_add(_add(_add(_add(_add(
                enteric_ch4,
                mm_other_ch4), mm_other_direct_n2o), mm_other_leach_n2o), mm_other_vol_n2o),
                mm_prp_ch4), mm_prp_direct_n2o), mm_prp_leach_n2o),
            mm_prp_vol_n2o,
        )

        mw = [
            MetadataWrite(1, 1, "Livestock category"),
            MetadataWrite(2, 1, "Number of heads"),
            MetadataWrite(3, 1, "Livestock productivity"),
            MetadataWrite(4, 1, "Production (unit of product)"),
            MetadataWrite(5, 1, "Manure management"),
            MetadataWrite(6, 1, "Heads on pasture (%)"),
        ]
        if m.is_start():
            mw += [
                MetadataWrite(1, 2, m.livestock_category_type.name),
                MetadataWrite(2, 2, m.heads_number_start),
                MetadataWrite(3, 2, m.livestock_production_type_start.name),
                MetadataWrite(4, 2, m.production_start),
                MetadataWrite(5, 2, "WIP"),
                MetadataWrite(6, 2, "WIP"),
            ]
        if m.is_with():
            mw += [
                MetadataWrite(1, 3, m.livestock_category_type.name),
                MetadataWrite(2, 3, m.heads_number_w),
                MetadataWrite(3, 3, m.livestock_production_type_w.name),
                MetadataWrite(4, 3, m.production_w),
                MetadataWrite(5, 3, "WIP"),
                MetadataWrite(6, 3, "WIP"),
            ]
        if m.is_without():
            mw += [
                MetadataWrite(1, 4, m.livestock_category_type.name),
                MetadataWrite(2, 4, m.heads_number_wo),
                MetadataWrite(3, 4, m.livestock_production_type_wo.name),
                MetadataWrite(4, 4, m.production_wo),
                MetadataWrite(5, 4, "WIP"),
                MetadataWrite(6, 4, "WIP"),
            ]
        mw += [
            MetadataWrite(1, 6, m.livestock_category_thread.format_comments()),
            MetadataWrite(2, 6, m.heads_number_thread.format_comments()),
            MetadataWrite(3, 6, m.livestock_production_type_thread.format_comments()),
            MetadataWrite(4, 6, m.production_thread.format_comments()),
            MetadataWrite(5, 6, m.complementary_manure_management_type_thread.format_comments()),
        ]

        dur = m.activity.implementation_years + m.activity.capitalization_years
        units_heads_w = [float(m.heads_number_w)] * dur if m.is_with() else []

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="Livestock",
            result_rows=[
                ResultRow("CH4 from enteric fermentation", enteric_ch4),
                ResultRow("CH4 from manure management other than PRP", mm_other_ch4),
                ResultRow("Direct N2O from manure management other than PRP (direct)", mm_other_direct_n2o),
                ResultRow("Indirect N2O from manure management other than PRP (leaching)", mm_other_leach_n2o),
                ResultRow("Indirect N2O from manure management other than PRP (volatilization)", mm_other_vol_n2o),
                ResultRow("CH4 from manure management PRP", mm_prp_ch4),
                ResultRow("Direct N2O from manure management PRP (direct)", mm_prp_direct_n2o),
                ResultRow("Indirect N2O from manure management PRP (leaching)", mm_prp_leach_n2o),
                ResultRow("Indirect N2O from manure management PRP (volatilization)", mm_prp_vol_n2o),
            ],
            metadata_writes=mw,
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            units_heads_w=units_heads_w,
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------

@dataclass
class EnergyReport(BaseModuleReport):
    module: api_models.Energy

    def __post_init__(self):
        self.calculator = calculators.EnergyCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        dur = self._project_duration

        from api.calculators import Result

        electricity_co2_eq = _zeros(dur)
        liquid_fuel_co2 = _zeros(dur)
        liquid_fuel_ch4 = _zeros(dur)
        liquid_fuel_n2o = _zeros(dur)
        solid_fuel_co2 = _zeros(dur)
        solid_fuel_ch4 = _zeros(dur)
        solid_fuel_n2o = _zeros(dur)

        for submodule in m.submodules:
            calculator = calculators.EnergyEntryCalculator(submodule)
            try:
                sub_es = Result(*calculator.calculate()).balance.yearly_emissions_by_sector_by_gas
            except Exception as e:
                log.error(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")
                raise NotReadyError(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")

            electricity_co2_eq = _add(electricity_co2_eq, extract_emissions(sub_es, math_utils.ActivityTypes.ELECTRICITY, math_utils.GasTypes.CO2, duration=dur))

            # Determine whether this entry is a solid fuel or liquid/gaseous fuel.
            # The macro_fuel_type name "Solid (tdm)" identifies solid fuels;
            # "Liquid or gaseous (m3)" (or any non-solid) are liquid fuels.
            # Electricity entries produce ELECTRICITY activity type (already handled above)
            # and no FUEL activity type entries, so they are skipped here automatically.
            fuel_type = getattr(submodule, "fuel_type_w", None) or getattr(submodule, "fuel_type_start", None)
            macro_name = ""
            if fuel_type and fuel_type.macro_fuel_type:
                macro_name = fuel_type.macro_fuel_type.name.casefold()

            if "solid" in macro_name:
                solid_fuel_co2 = _add(solid_fuel_co2, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CO2, duration=dur))
                solid_fuel_ch4 = _add(solid_fuel_ch4, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CH4, duration=dur))
                solid_fuel_n2o = _add(solid_fuel_n2o, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.N2O, duration=dur))
            else:
                liquid_fuel_co2 = _add(liquid_fuel_co2, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CO2, duration=dur))
                liquid_fuel_ch4 = _add(liquid_fuel_ch4, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CH4, duration=dur))
                liquid_fuel_n2o = _add(liquid_fuel_n2o, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.N2O, duration=dur))

        total = _add(
            _add(_add(electricity_co2_eq, liquid_fuel_co2), _add(liquid_fuel_ch4, liquid_fuel_n2o)),
            _add(_add(solid_fuel_co2, solid_fuel_ch4), solid_fuel_n2o),
        )

        # Build metadata writes (no title for Energy – metadata_section_title="")
        # Offsets are 0-based: offset 0 = first row directly after previous section.
        electricities = list(api_models.Electricity.objects.filter(parent=m).all())
        fuels = list(api_models.Fuel.objects.filter(parent=m).all())
        n_elec = len(electricities)

        mw = []
        for i, electricity in enumerate(electricities):
            mw += [
                MetadataWrite(i, 1, "Electricity - power country of origin"),
                MetadataWrite(1 + i, 1, "Electricity grid (MWh/year)"),
                MetadataWrite(2 + i, 1, "Electricity renewable (MWh/year)"),
                MetadataWrite(3 + i, 1, "Scope of emission factor"),
            ]
            if m.is_start():
                mw += [
                    MetadataWrite(i, 2, electricity.country_t2.name),
                    MetadataWrite(1 + i, 2, electricity.quantity_consumed_per_year_start),
                    MetadataWrite(2 + i, 2, electricity.mwh_renewables_start),
                    MetadataWrite(3 + i, 2, electricity.ef_source.name),
                ]
            if m.is_with():
                mw += [
                    MetadataWrite(i, 3, electricity.country_t2.name),
                    MetadataWrite(1 + i, 3, electricity.quantity_consumed_per_year_w),
                    MetadataWrite(2 + i, 3, electricity.mwh_renewables_w),
                    MetadataWrite(3 + i, 3, electricity.ef_source.name),
                ]
            if m.is_without():
                mw += [
                    MetadataWrite(i, 4, electricity.country_t2.name),
                    MetadataWrite(1 + i, 4, electricity.quantity_consumed_per_year_wo),
                    MetadataWrite(2 + i, 4, electricity.mwh_renewables_wo),
                    MetadataWrite(3 + i, 4, electricity.ef_source.name),
                ]
            mw += [
                MetadataWrite(1 + i, 6, electricity.quantity_consumed_per_year_thread.format_comments()),
                MetadataWrite(2 + i, 6, electricity.mwh_renewables_thread.format_comments()),
            ]

        # Fuel rows: offset base = n_elec + 3 (replicates last_metadata_row += n_elec + 3)
        fuel_base = n_elec + 3
        for i, fuel in enumerate(fuels):
            mw += [
                MetadataWrite(fuel_base + i, 1, "Fuel - estate"),
                MetadataWrite(fuel_base + 1 + i, 1, "Fuel - type"),
                MetadataWrite(fuel_base + 2 + i, 1, "Fuel consumption (m3 or tdm)"),
                MetadataWrite(fuel_base + 3 + i, 1, "Accounting for CO2 emissions (yes/no)"),
            ]
            if m.is_start():
                mw += [
                    MetadataWrite(fuel_base + i, 2, "WIP"),
                    MetadataWrite(fuel_base + 1 + i, 2, fuel.fuel_type_start.name),
                    MetadataWrite(fuel_base + 2 + i, 2, fuel.quantity_consumed_per_year_start),
                    MetadataWrite(fuel_base + 3 + i, 2, "WIP"),
                ]
            if m.is_with():
                mw += [
                    MetadataWrite(fuel_base + i, 3, "WIP"),
                    MetadataWrite(fuel_base + 1 + i, 3, fuel.fuel_type_w.name),
                    MetadataWrite(fuel_base + 2 + i, 3, fuel.quantity_consumed_per_year_w),
                    MetadataWrite(fuel_base + 3 + i, 3, "WIP"),
                ]
            if m.is_without():
                mw += [
                    MetadataWrite(fuel_base + i, 4, "WIP"),
                    MetadataWrite(fuel_base + 1 + i, 4, fuel.fuel_type_wo.name),
                    MetadataWrite(fuel_base + 2 + i, 4, fuel.quantity_consumed_per_year_wo),
                    MetadataWrite(fuel_base + 3 + i, 4, "WIP"),
                ]
            mw += [
                MetadataWrite(fuel_base + 2 + i, 6, fuel.quantity_consumed_per_year_thread.format_comments()),
            ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="",  # no standalone metadata title in original
            result_rows=[
                ResultRow("CO2-eq from electricity", electricity_co2_eq),
                ResultRow("CO2 from liquid fuels", liquid_fuel_co2),
                ResultRow("CH4 from liquid fuels", liquid_fuel_ch4),
                ResultRow("N2O from liquid fuels", liquid_fuel_n2o),
                ResultRow("CO2 from solid fuels", solid_fuel_co2),
                ResultRow("CH4 from solid fuels", solid_fuel_ch4),
                ResultRow("N2O from solid fuels", solid_fuel_n2o),
            ],
            metadata_writes=mw,
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

@dataclass
class InputReport(BaseModuleReport):
    module: api_models.Input

    def __post_init__(self):
        self.calculator = calculators.InputCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        dur = self._project_duration

        from api.calculators import Result

        inputs_co2 = _zeros(dur)
        inputs_n2o = _zeros(dur)
        inputs_co2_eq = _zeros(dur)
        feed_co2_eq = _zeros(dur)

        for submodule in m.submodules:
            calculator = calculators.InputEntryCalculator(submodule)
            try:
                sub_es = Result(*calculator.calculate()).balance.yearly_emissions_by_sector_by_gas
            except Exception as e:
                log.error(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")
                raise NotReadyError(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")

            inputs_co2 = _add(inputs_co2, extract_emissions(sub_es, math_utils.ActivityTypes.CO2_FIELD, math_utils.GasTypes.CO2, duration=dur))
            inputs_n2o = _add(inputs_n2o, extract_emissions(sub_es, math_utils.ActivityTypes.N20_FIELD, math_utils.GasTypes.N2O, duration=dur))

            if "feed" in submodule.input_type.macro_input_type.name.casefold():
                feed_co2_eq = _add(feed_co2_eq, extract_emissions(sub_es, math_utils.ActivityTypes.CO2_EQUIVALENT_VC, math_utils.GasTypes.CO2, duration=dur))
            else:
                inputs_co2_eq = _add(inputs_co2_eq, extract_emissions(sub_es, math_utils.ActivityTypes.CO2_EQUIVALENT_VC, math_utils.GasTypes.CO2, duration=dur))

        total = _add(_add(_add(inputs_co2, inputs_n2o), feed_co2_eq), inputs_co2_eq)

        # Metadata writes (no title, 0-based offsets)
        # Pattern: 3 rows per submodule entry, with +2 spacing between entries
        mw = []
        base = 0
        for i, entry in enumerate(m.submodules):
            if i != 0:
                base += 2
            row_label = base + i
            mw += [
                MetadataWrite(row_label, 1, "Macro input type"),
                MetadataWrite(row_label + 1, 1, "Input type"),
                MetadataWrite(row_label + 2, 1, "Quantity (t/year)"),
            ]
            if m.is_start():
                mw += [
                    MetadataWrite(row_label, 2, entry.input_type.macro_input_type.name),
                    MetadataWrite(row_label + 1, 2, entry.input_type.name),
                    MetadataWrite(row_label + 2, 2, entry.value_start),
                ]
            if m.is_with():
                mw += [
                    MetadataWrite(row_label, 3, entry.input_type.macro_input_type.name),
                    MetadataWrite(row_label + 1, 3, entry.input_type.name),
                    MetadataWrite(row_label + 2, 3, entry.value_w),
                ]
            if m.is_without():
                mw += [
                    MetadataWrite(row_label, 4, entry.input_type.macro_input_type.name),
                    MetadataWrite(row_label + 1, 4, entry.input_type.name),
                    MetadataWrite(row_label + 2, 4, entry.value_wo),
                ]
            mw += [
                MetadataWrite(row_label + 2, 6, entry.value_thread.format_comments()),
            ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="",  # no standalone metadata title in original
            result_rows=[
                ResultRow("N2O from inputs (field level)", inputs_n2o),
                ResultRow("CO2 from inputs (field level)", inputs_co2),
                ResultRow("CO2-eq from inputs (production, transportation and storage)", inputs_co2_eq),
                ResultRow("CO2-eq from feed", feed_co2_eq),
            ],
            metadata_writes=mw,
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


# ---------------------------------------------------------------------------
# Irrigation
# ---------------------------------------------------------------------------

@dataclass
class IrrigationReport(BaseModuleReport):
    module: api_models.Irrigation

    def __post_init__(self):
        self.calculator = calculators.IrrigationCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        dur = self._project_duration

        from api.calculators import Result

        other_infra_co2_eq = _zeros(dur)
        lf_elec_co2 = _zeros(dur)
        lf_elec_ch4 = _zeros(dur)
        lf_elec_n2o = _zeros(dur)

        for submodule in m.submodules:
            CalculatorClass = (calculators.IrrigationPhaseCalculator
                               if isinstance(submodule, api_models.IrrigationPhase)
                               else calculators.IrrigationSystemCalculator)
            calculator = CalculatorClass(submodule)
            try:
                sub_es = Result(*calculator.calculate()).balance.yearly_emissions_by_sector_by_gas
            except Exception as e:
                log.error(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")
                raise NotReadyError(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")

            other_infra_co2_eq = _add(other_infra_co2_eq, extract_emissions(sub_es, math_utils.ActivityTypes.NEW_IRRIGATION, math_utils.GasTypes.CO2, duration=dur))
            lf_elec_co2 = _add(lf_elec_co2, extract_emissions(sub_es, math_utils.ActivityTypes.IRRIGATION_OPERATIONAL, math_utils.GasTypes.CO2, duration=dur))
            lf_elec_ch4 = _add(lf_elec_ch4, extract_emissions(sub_es, math_utils.ActivityTypes.IRRIGATION_OPERATIONAL, math_utils.GasTypes.CH4, duration=dur))
            lf_elec_n2o = _add(lf_elec_n2o, extract_emissions(sub_es, math_utils.ActivityTypes.IRRIGATION_OPERATIONAL, math_utils.GasTypes.N2O, duration=dur))

        total = _add(_add(_add(other_infra_co2_eq, lf_elec_co2), lf_elec_ch4), lf_elec_n2o)

        # Metadata writes (no title, 0-based offsets)
        systems = list(m.irrigation_systems.all())
        phases = list(m.irrigation_phases.all())
        n_systems = len(systems)

        mw = []
        base = 0
        for i, system in enumerate(systems):
            if i != 0:
                base += 1
            row = base + i
            mw += [
                MetadataWrite(row, 1, "New irrigation system type"),
                MetadataWrite(row + 1, 1, "Hectares"),
            ]
            if m.is_start():
                mw += [
                    MetadataWrite(row, 2, system.irrigation_system_type.name),
                    MetadataWrite(row + 1, 2, system.ha_start),
                ]
            if m.is_with():
                mw += [
                    MetadataWrite(row, 3, system.irrigation_system_type.name),
                    MetadataWrite(row + 1, 3, system.ha_w),
                ]
            if m.is_without():
                mw += [
                    MetadataWrite(row, 4, system.irrigation_system_type.name),
                    MetadataWrite(row + 1, 4, system.ha_wo),
                ]
            mw += [MetadataWrite(row + 1, 6, system.ha_thread.format_comments())]

        # After systems: base advances by n_systems + 1 (mirrors last_metadata_row += n_systems + 1)
        phase_base = (base + n_systems + 1) if n_systems > 0 else (n_systems + 1)
        phase_offset = 0
        for i, phase in enumerate(phases):
            if i != 0:
                phase_offset += 4
            row = phase_base + phase_offset + i
            mw += [
                MetadataWrite(row, 1, "Operating irrigation system type"),
                MetadataWrite(row + 1, 1, "Hectares"),
                MetadataWrite(row + 2, 1, "Source of energy"),
                MetadataWrite(row + 3, 1, "Depth of well (m)"),
                MetadataWrite(row + 4, 1, "Gross irrigation water requirement (mm/year)"),
            ]
            if m.is_start():
                mw += [
                    MetadataWrite(row, 2, phase.irrigation_system_type.name),
                    MetadataWrite(row + 1, 2, phase.ha_start),
                    MetadataWrite(row + 2, 2, phase.fuel_type_start.name),
                    MetadataWrite(row + 3, 2, phase.well_depth),
                    MetadataWrite(row + 4, 2, phase.gross_irrigation_water_start),
                ]
            if m.is_with():
                mw += [
                    MetadataWrite(row, 3, phase.irrigation_system_type.name),
                    MetadataWrite(row + 1, 3, phase.ha_w),
                    MetadataWrite(row + 2, 3, phase.fuel_type_w.name),
                    MetadataWrite(row + 3, 3, phase.well_depth),
                    MetadataWrite(row + 4, 3, phase.gross_irrigation_water_w),
                ]
            if m.is_without():
                mw += [
                    MetadataWrite(row, 4, phase.irrigation_system_type.name),
                    MetadataWrite(row + 1, 4, phase.ha_wo),
                    MetadataWrite(row + 2, 4, phase.fuel_type_wo.name),
                    MetadataWrite(row + 3, 4, phase.well_depth),
                    MetadataWrite(row + 4, 4, phase.gross_irrigation_water_wo),
                ]
            mw += [
                MetadataWrite(row + 1, 6, phase.ha_thread.format_comments()),
                MetadataWrite(row + 4, 6, phase.gross_irrigation_water_thread.format_comments()),
            ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="",  # no standalone metadata title in original
            result_rows=[
                ResultRow("CO2-eq from other infrastructure", other_infra_co2_eq),
                ResultRow("CO2 from liquid fuel or electricity", lf_elec_co2),
                ResultRow("CH4 from liquid fuel or electricity", lf_elec_ch4),
                ResultRow("N2O from liquid fuel or electricity", lf_elec_n2o),
            ],
            metadata_writes=mw,
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


# ---------------------------------------------------------------------------
# OrganicSoil
# ---------------------------------------------------------------------------

@dataclass
class OrganicSoilReport(BaseModuleReport):
    module: api_models.OrganicSoil

    def __post_init__(self):
        self.calculator = calculators.OrganicSoilCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        luc: api_models.LandUseChange = m.land_use_change

        # OrganicSoil has no result rows – only metadata
        # Stacked layout: start data in col 2 rows 1-12, with data col 3 rows 13-24,
        # without data col 4 rows 25-36
        mw = [
            MetadataWrite(1, 1, "Hectares"),
            MetadataWrite(2, 1, "Type of land use"),
            MetadataWrite(3, 1, "Are under drainage (ha)"),
            MetadataWrite(4, 1, "% area of ditches (ha)"),
            MetadataWrite(5, 1, "Fire on soil"),
            MetadataWrite(6, 1, "Soil fire periodicity"),
            MetadataWrite(7, 1, "% soil fire impact"),
            MetadataWrite(8, 1, "Area of peat extraction (ha)"),
            MetadataWrite(9, 1, "Height of extraction (cm)"),
            MetadataWrite(10, 1, "Peat used for energy (yes/no)"),
            MetadataWrite(11, 1, "Type of peat"),
            MetadataWrite(12, 1, "Peat density (t/m3)"),
        ]

        if (m.is_start() and luc is not None
                and (self.calculator.peat_extraction_math_w is not None
                     or self.calculator.peat_extraction_math_wo is not None)):
            math = self.calculator.peat_extraction_math_w or self.calculator.peat_extraction_math_wo
            peat_density = math.peat_density_tier_2_default
            mw += [
                MetadataWrite(1, 2, luc.module_type_start.area),
                MetadataWrite(2, 2, luc.module_type_start.name),
                MetadataWrite(3, 2, m.drainage_area_start),
                MetadataWrite(4, 2, m.ditches_area_start),
                MetadataWrite(5, 2, m.fire_type_start.name),
                MetadataWrite(6, 2, m.soil_fire_periodicity_start),
                MetadataWrite(7, 2, m.soil_fire_impact_percentage_start),
                MetadataWrite(8, 2, m.peat_area_start),
                MetadataWrite(9, 2, m.peat_extraction_height_start),
                MetadataWrite(10, 2, "Yes" if m.is_peat_for_energy_start else "No"),
                MetadataWrite(11, 2, m.peat_type.name),
                MetadataWrite(12, 2, peat_density),
            ]

        if m.is_with() and luc is not None and self.calculator.peat_extraction_math_w is not None:
            math = self.calculator.peat_extraction_math_w
            peat_density = math.peat_density_tier_2_default
            mw += [
                MetadataWrite(13, 3, luc.module_type_start.area),
                MetadataWrite(14, 3, luc.module_type_w.name),
                MetadataWrite(15, 3, m.drainage_area_w),
                MetadataWrite(16, 3, m.ditches_area_w),
                MetadataWrite(17, 3, m.fire_type_w.name),
                MetadataWrite(18, 3, m.soil_fire_periodicity_w),
                MetadataWrite(19, 3, m.soil_fire_impact_percentage_w),
                MetadataWrite(20, 3, m.peat_area_w),
                MetadataWrite(21, 3, m.peat_extraction_height_w),
                MetadataWrite(22, 3, "Yes" if m.is_peat_for_energy_w else "No"),
                MetadataWrite(23, 3, m.peat_type.name),
                MetadataWrite(24, 3, peat_density),
            ]

        if m.is_without() and luc is not None and self.calculator.peat_extraction_math_wo is not None:
            math = self.calculator.peat_extraction_math_wo
            peat_density = math.peat_density_tier_2_default
            mw += [
                MetadataWrite(25, 4, luc.module_type_start.area),
                MetadataWrite(26, 4, luc.module_type_wo.name),
                MetadataWrite(27, 4, m.drainage_area_wo),
                MetadataWrite(28, 4, m.ditches_area_wo),
                MetadataWrite(29, 4, m.fire_type_wo.name),
                MetadataWrite(30, 4, m.soil_fire_periodicity_wo),
                MetadataWrite(31, 4, m.soil_fire_impact_percentage_wo),
                MetadataWrite(32, 4, m.peat_area_wo),
                MetadataWrite(33, 4, m.peat_extraction_height_wo),
                MetadataWrite(34, 4, "Yes" if m.is_peat_for_energy_wo else "No"),
                MetadataWrite(35, 4, m.peat_type.name),
                MetadataWrite(36, 4, peat_density),
            ]

        mw += [
            MetadataWrite(2, 6, m.land_use_type_thread.format_comments()),
            MetadataWrite(3, 6, m.drainage_area_thread.format_comments()),
            MetadataWrite(4, 6, m.ditches_area_thread.format_comments()),
            MetadataWrite(5, 6, m.fire_type_thread.format_comments()),
            MetadataWrite(6, 6, m.soil_fire_periodicity_thread.format_comments()),
            MetadataWrite(7, 6, m.soil_fire_impact_percentage_thread.format_comments()),
            MetadataWrite(8, 6, m.peat_area_thread.format_comments()),
            MetadataWrite(9, 6, m.peat_extraction_height_thread.format_comments()),
            MetadataWrite(10, 6, m.is_peat_for_energy_thread.format_comments()),
            MetadataWrite(11, 6, m.peat_type_thread.format_comments()),
        ]

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title=str(m.module_type.name),
            result_rows=[],
            metadata_writes=mw,
            total_emissions=_zeros(self._project_duration),
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

@dataclass
class TransportReport(BaseModuleReport):
    module: api_models.Transport

    def __post_init__(self):
        self.calculator = calculators.TransportCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        dur = self._project_duration

        from api.calculators import Result

        fuel_co2 = _zeros(dur)
        fuel_ch4 = _zeros(dur)
        fuel_n2o = _zeros(dur)
        electricity_co2 = _zeros(dur)

        for submodule in m.submodules:
            cached = (submodule.cached_results_by_activity_by_gas["balance"]
                      if submodule.cached_results_by_activity_by_gas is not None else None)
            if cached is not None:
                fuel_co2 = _add(fuel_co2, extract_emissions(cached, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CO2, duration=dur))
                fuel_ch4 = _add(fuel_ch4, extract_emissions(cached, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CH4, duration=dur))
                fuel_n2o = _add(fuel_n2o, extract_emissions(cached, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.N2O, duration=dur))
                electricity_co2 = _add(electricity_co2, extract_emissions(cached, math_utils.ActivityTypes.ELECTRICITY, math_utils.GasTypes.CO2, duration=dur))
                continue

            calculator = calculators.TransportEntryCalculator(submodule)
            try:
                sub_es = Result(*calculator.calculate()).balance.yearly_emissions_by_sector_by_gas
            except Exception as e:
                log.error(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")
                raise NotReadyError(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")

            fuel_co2 = _add(fuel_co2, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CO2, duration=dur))
            fuel_ch4 = _add(fuel_ch4, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CH4, duration=dur))
            fuel_n2o = _add(fuel_n2o, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.N2O, duration=dur))
            electricity_co2 = _add(electricity_co2, extract_emissions(sub_es, math_utils.ActivityTypes.ELECTRICITY, math_utils.GasTypes.CO2, duration=dur))

        total = _add(_add(_add(fuel_n2o, fuel_ch4), fuel_co2), electricity_co2)

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="",
            result_rows=[
                ResultRow("N2O from fuel combustion", fuel_n2o),
                ResultRow("CH4 from fuel combustion", fuel_ch4),
                ResultRow("CO2 from fuel combustion", fuel_co2),
                ResultRow("CO2 from electricity", electricity_co2),
            ],
            metadata_writes=[],
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

@dataclass
class ProcessingReport(BaseModuleReport):
    module: api_models.Processing

    def __post_init__(self):
        self.calculator = calculators.ProcessingCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        dur = self._project_duration

        from api.calculators import Result

        fuel_co2 = _zeros(dur)
        fuel_ch4 = _zeros(dur)
        fuel_n2o = _zeros(dur)
        electricity_co2 = _zeros(dur)
        water_use = _zeros(dur)

        for submodule in m.submodules:
            cached = (submodule.cached_results_by_activity_by_gas["balance"]
                      if submodule.cached_results_by_activity_by_gas is not None else None)
            if cached is not None:
                fuel_co2 = _add(fuel_co2, extract_emissions(cached, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CO2, duration=dur))
                fuel_ch4 = _add(fuel_ch4, extract_emissions(cached, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CH4, duration=dur))
                fuel_n2o = _add(fuel_n2o, extract_emissions(cached, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.N2O, duration=dur))
                electricity_co2 = _add(electricity_co2, extract_emissions(cached, math_utils.ActivityTypes.ELECTRICITY, math_utils.GasTypes.CO2, duration=dur))
                water_use = _add(water_use, extract_emissions(cached, math_utils.ActivityTypes.PROCESSING, math_utils.GasTypes.CO2, duration=dur))
                continue

            calculator = calculators.ProcessingEntryCalculator(submodule)
            try:
                sub_es = Result(*calculator.calculate()).balance.yearly_emissions_by_sector_by_gas
            except Exception as e:
                log.error(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")
                raise NotReadyError(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")

            fuel_co2 = _add(fuel_co2, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CO2, duration=dur))
            fuel_ch4 = _add(fuel_ch4, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.CH4, duration=dur))
            fuel_n2o = _add(fuel_n2o, extract_emissions(sub_es, math_utils.ActivityTypes.FUEL, math_utils.GasTypes.N2O, duration=dur))
            electricity_co2 = _add(electricity_co2, extract_emissions(sub_es, math_utils.ActivityTypes.ELECTRICITY, math_utils.GasTypes.CO2, duration=dur))
            water_use = _add(water_use, extract_emissions(sub_es, math_utils.ActivityTypes.PROCESSING, math_utils.GasTypes.CO2, duration=dur))

        total = _add(_add(_add(_add(fuel_co2, fuel_ch4), fuel_n2o), electricity_co2), water_use)

        cumulative_water = list(np.cumsum(water_use))

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="",
            result_rows=[
                ResultRow("N2O from fuel combustion", fuel_n2o),
                ResultRow("CH4 from fuel combustion", fuel_ch4),
                ResultRow("CO2 from fuel combustion", fuel_co2),
                ResultRow("CO2 from electricity", electricity_co2),
                ResultRow("Cumulative water use in liters", cumulative_water),
                ResultRow("Yearly water use in liters", water_use),
            ],
            metadata_writes=[],
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


# ---------------------------------------------------------------------------
# Packaging
# ---------------------------------------------------------------------------

@dataclass
class PackagingReport(BaseModuleReport):
    module: api_models.Packaging

    def __post_init__(self):
        self.calculator = calculators.PackagingCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        dur = self._project_duration

        from api.calculators import Result

        electricity_co2 = _zeros(dur)
        packaging_co2 = _zeros(dur)

        for submodule in m.submodules:
            cached = (submodule.cached_results_by_activity_by_gas["balance"]
                      if submodule.cached_results_by_activity_by_gas is not None else None)
            if cached is not None:
                electricity_co2 = _add(electricity_co2, extract_emissions(cached, math_utils.ActivityTypes.ELECTRICITY, math_utils.GasTypes.CO2, duration=dur))
                packaging_co2 = _add(packaging_co2, extract_emissions(cached, math_utils.ActivityTypes.PACKAGING, math_utils.GasTypes.CO2, duration=dur))
                continue

            calculator = calculators.PackagingEntryCalculator(submodule)
            try:
                sub_es = Result(*calculator.calculate()).balance.yearly_emissions_by_sector_by_gas
            except Exception as e:
                log.error(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")
                raise NotReadyError(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")

            electricity_co2 = _add(electricity_co2, extract_emissions(sub_es, math_utils.ActivityTypes.ELECTRICITY, math_utils.GasTypes.CO2, duration=dur))
            packaging_co2 = _add(packaging_co2, extract_emissions(sub_es, math_utils.ActivityTypes.PACKAGING, math_utils.GasTypes.CO2, duration=dur))

        total = _add(electricity_co2, packaging_co2)

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="",
            result_rows=[
                ResultRow("CO2 from electricity", electricity_co2),
                ResultRow("CO2 from packaging", packaging_co2),
            ],
            metadata_writes=[],
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items_from_module(activity_title),
        )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

@dataclass
class StorageReport(BaseModuleReport):
    module: api_models.Storage

    def __post_init__(self):
        self.calculator = calculators.StorageCalculator(self.module)
        super().__post_init__()

    def compute(self) -> ModuleResult:
        activity_title = self.module.activity.name
        m = self.module
        dur = self._project_duration

        from api.calculators import Result

        electricity_co2 = _zeros(dur)
        storage_co2 = _zeros(dur)

        for submodule in m.submodules:
            cached = (submodule.cached_results_by_activity_by_gas["balance"]
                      if submodule.cached_results_by_activity_by_gas is not None else None)
            if cached is not None:
                storage_co2 = _add(storage_co2, extract_emissions(cached, math_utils.ActivityTypes.STORAGE, math_utils.GasTypes.CO2, duration=dur))
                electricity_co2 = _add(electricity_co2, extract_emissions(cached, math_utils.ActivityTypes.ELECTRICITY, math_utils.GasTypes.CO2, duration=dur))
                continue

            calculator = calculators.StorageEntryCalculator(submodule)
            try:
                sub_es = Result(*calculator.calculate()).balance.yearly_emissions_by_sector_by_gas
            except Exception as e:
                log.error(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")
                raise NotReadyError(f"Cannot calculate emissions for submodule {submodule.module_type.name}: {e}")

            storage_co2 = _add(storage_co2, extract_emissions(sub_es, math_utils.ActivityTypes.STORAGE, math_utils.GasTypes.CO2, duration=dur))
            electricity_co2 = _add(electricity_co2, extract_emissions(sub_es, math_utils.ActivityTypes.ELECTRICITY, math_utils.GasTypes.CO2, duration=dur))

        total = _add(electricity_co2, storage_co2)

        return ModuleResult(
            title=m.module_type.name,
            metadata_section_title="",
            result_rows=[
                ResultRow("CO2 from electricity", electricity_co2),
                ResultRow("CO2 from storage", storage_co2),
            ],
            metadata_writes=[],
            total_emissions=total,
            is_with=m.is_with(),
            is_without=m.is_without(),
            _inventory_items=self._inventory_items_from_module(activity_title),
        )
