import math
import traceback

from .general_functions import (
    breakdown_according_to_values,
    soil_emissions_2,
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

from .generalized_modules import LandModule
from dataclasses import dataclass
from typing import Optional

@dataclass
class SoilToAdd(LandModule):

    def calculate_emissions(self):
        try:
            if self.calculate_soc_som:
                self.soil_emissions_yearly, self.soil_emissions_total = soil_emissions_2(self.soc_start, self.soc_end, self.hectares_total, self.hectares_start, self.hectares_end, self.hectares_before_20)

                soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.soil_emissions_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

        except Exception as e:
            print("Error in SoilToAdd.calculate_emissions")
            print(e)
            print(traceback.format_exc())
            return 0