import re
import traceback

from .general_functions import (
    breakdown_proportionally_to_values,
    soil_emissions,
    breakdown_equally_across_years,
    compute_half_year_cumulative_n_year_maturity,
    compute_yearly_or_half_year_cumulative,
    som_emissions,
    compute_yearly_delta
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

from .generalized_modules import BaseModule

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Defo(BaseModule):

    ha_start: float
    ha_end: float
    biomass_final_1_year_t_per_ha_default: float
    biomass_final_1_year_t_per_ha_tier_2: Optional[float]
    nitrous_constant: float
    methane_constant: float
    fire_bool: bool
    n2o_vegetation: float
    ch4_vegetation: float
    cf_vegetation: float
    moisture_emission_factor: float
    litter: float
    litter_tier_2: Optional[float]
    dw: float
    dw_tier_2: Optional[float]
    hwp_before_t_dm_per_ha: float
    mangrove_factor: float
    bgb_t_c_per_ha_tier_2: Optional[float]
    agb_t_c_per_ha_tier_2: Optional[float]
    agb_t_c_per_ha_default: float
    bgb_t_c_per_ha_default_input_parameter: float
    c_n_ratio: float
    soc_after_defo_tier_2: Optional[float]
    soc_reference_default: float
    soc_reference_tier_2: Optional[float]
    fmg_start_tier_2: Optional[float]
    fmg_end_tier_2: Optional[float]
    fi_start_tier_2: Optional[float]
    fi_end_tier_2: Optional[float]
    flu_start_tier_2: Optional[float]
    flu_end_tier_2: Optional[float]
    soc_start_tier_2: Optional[float]
    soc_end_tier_2: Optional[float]
    fmg_start_default: float
    fmg_end_default: float
    fi_start_default: float
    fi_end_default: float
    flu_start_default: float
    flu_end_default: float
    soc_start_default: float
    soc_end_default: float
    calculate_soc_som: bool

    # NOTE: This is a check that implies that the final module has growth. Meaning it is either Perennial or Forest
    # in this case the growth is calculated in the final module, hence the final_biomass has to be set to 0
    end_module_has_growth: bool

    def __post_init__(self):
        super().__post_init__()

        self.area_deforested = abs(self.ha_end - self.ha_start)
        # TODO: Assigned FMG, FLU, FI values. Maybe once everything has been done change this structure
        self.fmg_start = self.fmg_start_tier_2 if self.fmg_start_tier_2 else self.fmg_start_default
        self.fmg_end = self.fmg_end_tier_2 if self.fmg_end_tier_2 else self.fmg_end_default
        self.flu_start = self.flu_start_tier_2 if self.flu_start_tier_2 else self.flu_start_default
        self.flu_end = self.flu_end_tier_2 if self.flu_end_tier_2 else self.flu_end_default
        self.fi_start = self.fi_start_tier_2 if self.fi_start_tier_2 else self.fi_start_default
        self.fi_end = self.fi_end_tier_2 if self.fi_end_tier_2 else self.fi_end_default

        self.soc_start = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start if not self.soc_start_tier_2 else self.soc_start_tier_2 * self.fmg_start * self.flu_start * self.fi_start
        self.soc_end = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end if not self.soc_end_tier_2 else self.soc_end_tier_2 * self.fmg_end * self.flu_end * self.fi_end

        # AUXILIARY VARIABLES FOR SOIL CALCULATION
        self.hectares_before_20, self.hectares_after_20 = compute_half_year_cumulative_n_year_maturity(0, self.area_deforested, self.implementation_time, self.capitalization_time, self.rate_type)
        self.total_hectares = compute_yearly_or_half_year_cumulative(self.area_deforested, 0, self.implementation_time, self.capitalization_time, self.rate_type)
        self.delta_hectares = compute_yearly_delta(self.area_deforested, 0, self.implementation_time, self.capitalization_time, self.rate_type)
        
        
    def calculate_emissions(self):

        def calculate_biomass():
            try:
                # NOTE: try to make the variable names similar to OLUC
                bgb_t_c_per_ha_default = self.bgb_t_c_per_ha_default_input_parameter * self.agb_t_c_per_ha_default

                agb_t_c = self.agb_t_c_per_ha_default if not self.agb_t_c_per_ha_tier_2 else self.agb_t_c_per_ha_tier_2
                bgb_t_c = bgb_t_c_per_ha_default if not self.bgb_t_c_per_ha_tier_2 else self.bgb_t_c_per_ha_tier_2

                hwp_before_t_c = self.agb_t_c_per_ha_default if self.hwp_before_t_dm_per_ha * self.mangrove_factor > self.agb_t_c_per_ha_default else self.hwp_before_t_dm_per_ha * self.mangrove_factor

                if self.biomass_final_1_year_t_per_ha_tier_2:
                    biomass_final_1_year_t_per_ha = self.biomass_final_1_year_t_per_ha_tier_2
                else:
                    biomass_final_1_year_t_per_ha = self.biomass_final_1_year_t_per_ha_default

                # NOTE: Special case for Perennial and Forest as final land uses
                if self.end_module_has_growth:
                    biomass_final_1_year_t_per_ha = 0

                initial_biomass = agb_t_c + bgb_t_c - hwp_before_t_c
                final_biomass = biomass_final_1_year_t_per_ha

                biomass_forest_agb_bgb_t_co2 = (final_biomass - initial_biomass) * (-44 / 12)

                biomass_loss = biomass_forest_agb_bgb_t_co2 * self.area_deforested

                emissions_biomass_loss_yearly = breakdown_proportionally_to_values(biomass_loss, self.delta_hectares)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in emissions_biomass_loss_yearly], activity=ActivityTypes.BIOMASS, delay=self.delay))

            except Exception as e:
                traceback.print_exc()

        def calculate_dom_emissions():
            try:
                litter = self.litter if not self.litter_tier_2 else self.litter_tier_2
                dw = self.dw if not self.dw_tier_2 else self.dw_tier_2

                biomass_forest_dom_t_c_per_ha = litter + dw
                biomass_forest_dom_t_co2_per_ha = biomass_forest_dom_t_c_per_ha * (44 / 12)

                dom_loss = biomass_forest_dom_t_co2_per_ha * self.area_deforested
                
                emissions_dom_yearly = breakdown_proportionally_to_values(dom_loss, self.delta_hectares)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in emissions_dom_yearly], activity=ActivityTypes.DOM, delay=self.delay))

            except Exception as e:
                traceback.print_exc()

        def calculate_fire_emissions():
            try:
                fire_t_c_per_ha = self.agb_t_c_per_ha_default - self.hwp_before_t_dm_per_ha * self.mangrove_factor if self.fire_bool else 0

                fire_kg_n2o = fire_t_c_per_ha * self.n2o_vegetation * self.cf_vegetation if self.fire_bool else 0
                fire_kg_ch4 = fire_t_c_per_ha * self.ch4_vegetation * self.cf_vegetation if self.fire_bool else 0

                total_ch4_per_ha = fire_kg_ch4 * self.methane_constant / 1000
                total_n2o_per_ha = fire_kg_n2o * self.nitrous_constant / 1000
                
                total_ch4 = total_ch4_per_ha * self.area_deforested
                total_n2o = total_n2o_per_ha * self.area_deforested

                emissions_ch4 = breakdown_proportionally_to_values(total_ch4, self.delta_hectares)
                emissions_n2o = breakdown_proportionally_to_values(total_n2o, self.delta_hectares)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in emissions_ch4], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))
                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in emissions_n2o], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))

            except Exception as e:
                traceback.print_exc()

        calculate_biomass()
        calculate_dom_emissions()
        calculate_fire_emissions()
