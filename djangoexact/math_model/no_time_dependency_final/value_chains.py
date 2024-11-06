import math
import traceback

from .general_functions import (
    breakdown_according_to_values,
    soil_emissions,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

from dataclasses import dataclass, field
from typing import Optional
from .generalized_modules import BaseModule

@dataclass
class ValueChain(BaseModule):
    
    # Emission factors
    emission_factor_start_default: float
    emission_factor_end_default: float
    emission_factor_start_tier_2: float
    emission_factor_end_tier_2: float
    
    # Total Quantity of Input is calculated as units * input_quantity
    units_start: float
    units_end: float
    input_quantity_start: float
    input_quantity_end: float
    input_coefficient_multiplier: float
    
    # Transmission loss
    transmission_loss_start: float
    transmission_loss_end: float
    
    activity_type: ActivityTypes
    
    def __post_init__(self):
        super().__post_init__()
        
        self.emission_factor_start = self.emission_factor_start_tier_2 or self.emission_factor_start_default
        self.emission_factor_end = self.emission_factor_end_tier_2 or self.emission_factor_end_default
    
    def calculate_emissions(self):
        
        total_quantity_start = self.units_start * self.input_quantity_start * self.input_coefficient_multiplier
        total_quantity_end = self.units_end * self.input_quantity_end * self.input_coefficient_multiplier
        
        emissions_start = total_quantity_start * self.emission_factor_start
        emissions_end = total_quantity_end * self.emission_factor_end
        
        emissions_yearly = yearly_time_dependent_parameter_breakdown(emissions_start, emissions_end, self.implementation_time, self.capitalization_time, self.rate_type)
        
        emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_yearly], self.activity_type, delay=self.delay)
        self.result.yearly_emissions_by_sector_by_gas.append(emission_set)
        
        
    
    
    
    
    