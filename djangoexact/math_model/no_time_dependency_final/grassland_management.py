import math
import re
import traceback
from dataclasses import dataclass
from typing import Optional

from .general_functions import (
    breakdown_proportionally_to_values,
    soil_emissions,
    compute_half_year_cumulative_n_year_maturity,
    compute_yearly_or_half_year_cumulative,
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

@dataclass
class GrasslandManagement(LandModule):

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

                    if self.fire_interval <= 0:
                        raise ValueError("Fire interval must be greater than 0 if fire is used")
                    
                    agb = self.agb_ref if not self.agb_tier_2 else self.agb_tier_2
                    cf = self.cf_ref if not self.cf_tier_2 else self.cf_tier_2

                    annual_nitrous = ((agb * self.fire_impact * cf * self.nitrous_ef * self.nitrous_constant / 1000) / self.fire_interval) 
                    annual_methane = ((agb * self.fire_impact * cf * self.methane_ef * self.methane_constant / 1000) / self.fire_interval)

                    total_nitrous = annual_nitrous * sum(self.hectares_total)
                    total_methane = annual_methane * sum(self.hectares_total)

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in breakdown_proportionally_to_values(total_nitrous, self.hectares_total)], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in breakdown_proportionally_to_values(total_methane, self.hectares_total)], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))
                return
            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_soil_emissions():
            try:
                if self.calculate_soc_som:
                    emissions_soil_yearly, emissions_soil_total = soil_emissions(self.soc_start, self.soc_end, self.hectares_total, self.hectares_start, self.hectares_end, self.hectares_before_20)

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
                raise e

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
                raise e

        calculate_residue_burning()
        calculate_soil_emissions()
        calculate_emissions_som()
        calculate_biomass_emissions()

