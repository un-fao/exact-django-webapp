import math
import traceback

from .general_functions import (
    breakdown_proportionally_to_values,
    soil_emissions,
    breakdown_equally_across_years,
    compute_half_year_cumulative_n_year_maturity,
    compute_yearly_or_half_year_cumulative,
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
                self.soil_emissions_yearly, self.soil_emissions_total = soil_emissions(self.soc_start, self.soc_end, self.hectares_total, self.hectares_start, self.hectares_end, self.hectares_before_20)

                soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.soil_emissions_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

        except Exception as e:
            print("Error in SoilToAdd.calculate_emissions")
            print(e)
            print(traceback.format_exc())
            raise e