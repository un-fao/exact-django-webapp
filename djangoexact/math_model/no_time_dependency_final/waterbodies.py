import traceback
from .general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions
from .ghg_emissions_classes import YearlyGasActivityEmissionSet, Emission, GasTypes, ActivityTypes, Result

from .generalized_modules import BaseModule
from dataclasses import dataclass
from typing import Optional

@dataclass
class CoastalWaterbodies(BaseModule):

    area_start : float
    area_end : float
    trophic_state_default : float
    methane_emission_factor_default : float
    trophic_state_tier_2_start : Optional[float]
    trophic_state_tier_2_end : Optional[float]
    methane_emission_factor_start_tier_2 : Optional[float]
    methane_emission_factor_end_tier_2 : Optional[float]
    methane_constant : float

    chlo_A_start : Optional[float]
    chlo_A_end : Optional[float]

    def __post_init__(self):
        super().__post_init__()

        self.hectares = yearly_time_dependent_parameter_breakdown(self.area_start, self.area_end, self.implementation_time, self.capitalization_time, self.rate_type)
    

    def calculate_emissions(self, ):

        try:

            trophic_state_start = self.trophic_state_default if not self.chlo_A_start else 0.26 * self.chlo_A_start
            trophic_state_start = self.trophic_state_default if not self.trophic_state_tier_2_start else self.trophic_state_tier_2_start

            trophic_state_end = self.trophic_state_default if not self.chlo_A_end else 0.26 * self.chlo_A_end
            trophic_state_end = self.trophic_state_default if not self.trophic_state_tier_2_end else self.trophic_state_tier_2_end

            methane_emission_factor_end = self.methane_emission_factor_default if not self.methane_emission_factor_end_tier_2 else self.methane_emission_factor_end_tier_2
            methane_emission_factor_start = self.methane_emission_factor_default if not self.methane_emission_factor_start_tier_2 else self.methane_emission_factor_start_tier_2

            yearly_emissions_start = self.area_start * trophic_state_start * methane_emission_factor_start / 1000 * self.methane_constant
            yearly_emissions_end = self.area_end * trophic_state_end * methane_emission_factor_end / 1000 * self.methane_constant

            self.emissions_yearly = yearly_time_dependent_parameter_breakdown(yearly_emissions_start, yearly_emissions_end, self.implementation_time, self.capitalization_time, self.rate_type)
            self.total_emissions = sum(self.emissions_yearly)

            # offsite_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.offsite_emissions_yearly], ActivityTypes.OFFSITE_PEAT, delay=self.delay)
            # self.result.yearly_emissions_by_sector_by_gas.append(offsite_emission_set)

            emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in self.emissions_yearly], ActivityTypes.COASTAL_WATERBODIES, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(emission_set)
            
        except Exception as e:
            traceback.print_exc()
            raise e
        
