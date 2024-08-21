import math
import re
import traceback
from dataclasses import dataclass

from .general_functions import (
    breakdown_according_to_values,
    soil_emissions_2,
    yearly_constant_emissions_breakdown,
    som_emissions,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
    biomass_emissions,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

from .generalized_modules import LandModule

@dataclass
class NotCultivatedLand(LandModule):

    nitrous_constant : float

    def calculate_emissions(
        self,
    ):
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
                emissions_biomass_yearly, emissions_biomass_total = biomass_emissions(self.biomass_start, self.biomass_end, self.hectares_start, self.hectares_end, self.rate_type, self.implementation_time, self.capitalization_time)
                biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_biomass_yearly], ActivityTypes.BIOMASS, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

            except Exception as e:
                traceback.print_exc()

        calculate_soil_emissions()
        calculate_emissions_som()
        calculate_biomass_emissions()

