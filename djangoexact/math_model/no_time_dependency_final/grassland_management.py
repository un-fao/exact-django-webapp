import math
import re
import traceback
from dataclasses import dataclass
from typing import Optional

from .general_functions import (
    breakdown_according_to_values,
    soil_emissions_2,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
    som_emissions,
    biomass_emissions
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

from .generalized_modules import BaseModule, LandModule

class GrasslandManagement(BaseModule):
    def __init__(
        self,
        area_start,
        area_end,
        time_impl,
        time_cap,
        rate,
        nitrous_constant,
        methane_constant,
        fire_interval,
        fire_used,
        methane_ef,
        nitrous_ef,
        agb_ref,
        agb_tier_2,
        cf_ref,
        cf_tier_2,
        soc_start_default,
        soc_end_default,
        soc_start_tier_2,
        soc_end_tier_2,
        calculate_soc_som,
        fmg_start_default,
        fmg_end_default,
        fmg_start_tier_2,
        fmg_end_tier_2,
        flu_start_default,
        flu_end_default,
        flu_start_tier_2,
        flu_end_tier_2,
        fi_start_default,
        fi_end_default,
        fi_start_tier_2,
        fi_end_tier_2,
        delay,
        ef_nitrous_som,
        biomass_start_default,
        biomass_end_default,
        biomass_start_tier_2,
        biomass_end_tier_2,
        fire_impact,
    ):
        self.area_start = area_start
        self.area_end = area_end
        self.time_impl = time_impl - delay
        self.time_cap = time_cap
        self.rate = rate
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.fire_interval = fire_interval  # front-end input, years between two fires, default is 5 (on front-end)
        self.fire_used = fire_used  # front-end input, states whether fire has been used
        self.methane_ef = methane_ef  # tabulated value IPCC D75 (value for Savanna and Grassland)
        self.nitrous_ef = nitrous_ef  # tabulated value IPCC E75 (value for Savanna and Grassland)
        self.agb_ref = agb_ref  # taken from IPCC A553 matching clim_moist to rows
        self.agb_tier_2 = agb_tier_2  # tier 2 value, expects float or None
        self.cf_ref = cf_ref  # default is 77%, not tabulated
        self.cf_tier_2 = cf_tier_2  # tier 2 value, expects float or None
        self.soc_start_default = soc_start_default
        self.soc_end_default = soc_end_default
        self.soc_start_tier_2 = soc_start_tier_2  # tier 2 value, expects float or None
        self.soc_end_tier_2 = soc_end_tier_2  # tier 2 value, expects float or None

    nitrous_constant: float
    methane_constant: float
    fire_interval: float
    fire_used: bool
    fire_impact: float
    methane_ef: float
    nitrous_ef: float
    agb_ref: float
    agb_tier_2: float
    cf_ref: float
    cf_tier_2: Optional[float]
    

    def calculate_emissions(
        self,
    ):
        def calculate_residue_burning():
            try:
                if not self.fire_used or self.implementation_time + self.capitalization_time < self.fire_interval or self.fire_interval == None:
                    pass
                else:
                    agb = self.agb_ref if not self.agb_tier_2 else self.agb_tier_2
                    cf = self.cf_ref if not self.cf_tier_2 else self.cf_tier_2

                    annual_nitrous = ((agb * self.fire_impact * cf * self.nitrous_ef * self.nitrous_constant / 1000) / self.fire_interval) 
                    annual_methane = ((agb * self.fire_impact * cf * self.methane_ef * self.methane_constant / 1000) / self.fire_interval)

                    annual_nitrous = ((agb * cf * self.nitrous_ef * self.nitrous_constant / 1000) / self.fire_interval) * self.fire_impact
                    annual_methane = ((agb * cf * self.methane_ef * self.methane_constant / 1000) / self.fire_interval) * self.fire_impact

                    total_nitrous = annual_nitrous * sum(self.total_hectars)
                    total_methane = annual_methane * sum(self.total_hectars)

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in breakdown_according_to_values(total_nitrous, self.total_hectars)], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in breakdown_according_to_values(total_methane, self.total_hectars)], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))
                return
            except:
                traceback.print_exc()
                return

        def calculate_soil_emissions():
            try:
                if self.calculate_soc_som:
                    emissions_soil_yearly, emissions_soil_total = soil_emissions_2(self.soc_start, self.soc_end, self.hectares_total, self.hectares_start, self.hectares_end, self.hectares_before_20)

                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_soil_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

            except Exception as e:
                traceback.print_exc()

        def calculate_emissions_som():
            try:
                if self.calculate_soc_som:
                    emissions_som_yearly, emissions_som_total = som_emissions(self.soc_end, self.soc_start, self.ef_nitrous_som, self.nitrous_constant, self.hectares_before_20)

                    som_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in emissions_som_yearly], ActivityTypes.SOM, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(som_emission_set)
            except Exception as e:
                traceback.print_exc()

        def calculate_biomass_emissions():
            try:
                if self.calculate_biomass:
                    emissions_biomass_yearly, emissions_biomass_total = biomass_emissions(self.biomass_start, self.biomass_end, self.hectares_start, self.hectares_end, self.rate_type, self.implementation_time, self.capitalization_time)
                    biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_biomass_yearly], ActivityTypes.BIOMASS, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)
                else:
                    pass

            except Exception as e:
                traceback.print_exc()

        calculate_residue_burning()
        calculate_soil_emissions()
        calculate_emissions_som()
        calculate_biomass_emissions()

