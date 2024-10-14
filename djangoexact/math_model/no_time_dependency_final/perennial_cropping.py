import traceback

from .general_functions import (
    breakdown_according_to_values,
    soil_emissions_2,
    som_emissions,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
    biomass_emissions,
    breakdown_according_to_values_for_x_years
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

from .generalized_modules import LandModule
from typing import Optional
from dataclasses import dataclass


@dataclass
class PerennialCropland(LandModule):

    nitrous_constant: float
    methane_constant: float
    residue_burnt: float
    emission_factor_burning_nitrous_residue: float
    ef_nitrous_som: float
    emission_factor_burning_methane: float
    combustion_factor: float
    fire_periodicity_default: float
    fire_periodicity_tier_2: Optional[float]
    t_biomass_tier_2: Optional[float]
    agb_rate_default: float
    agb_rate_tier_2: Optional[float]
    agb_maximum_c: float
    bgb_rate_default: float
    bgb_rate_tier_2: Optional[float]
    end_module_has_growth: bool

    def __post_init__(self):
        super().__post_init__()

        # Tier 2 value
        self.residue_availability_tier_2_default = None

    def calculate_emissions(
        self,
    ):
        def calculate_residue():
            try:
                fire_periodicity = self.fire_periodicity_default if not self.fire_periodicity_tier_2 else self.fire_periodicity_tier_2
                ag_tc = self.agb_rate_default if not self.agb_rate_tier_2 else self.agb_rate_tier_2
                t_biomass = ag_tc * 0.5 / 0.47 if not self.t_biomass_tier_2 else self.t_biomass_tier_2  # Default
                self.residue_availability_tier_2_default = t_biomass

                ################## COMPUTATION OF AMOUNT OF KG OF METHANE ###################

                kg_methane = t_biomass * self.emission_factor_burning_methane * self.combustion_factor / fire_periodicity if self.residue_burnt else 0

                #################### COMPUTATION OF AMOUNT OF KG OF NITROUS ######################

                kg_nitrous = t_biomass * self.emission_factor_burning_nitrous_residue * self.combustion_factor / fire_periodicity if self.residue_burnt else 0

                #################### COMPUTATION OF TOTAL NITROUS AND METHANE EMISSIONS ######################

                nitrous_component = kg_nitrous * self.nitrous_constant / 1000
                methane_component = kg_methane * self.methane_constant / 1000

                total_nitrous = sum(self.hectares_total) * nitrous_component
                total_methane = sum(self.hectares_total) * methane_component

                yearly_nitrous_emissions = breakdown_according_to_values(total_nitrous, self.hectares_total)
                yearly_methane_emissions = breakdown_according_to_values(total_methane, self.hectares_total)

                nitrous_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in yearly_nitrous_emissions], ActivityTypes.RESIDUE_BURNING, delay=self.delay)
                methane_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in yearly_methane_emissions], ActivityTypes.RESIDUE_BURNING, delay=self.delay)
                
                self.result.yearly_emissions_by_sector_by_gas.append(nitrous_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(methane_emission_set)
            except Exception as e:
                traceback.print_exc()

        def calculate_som():
            try:
                if self.calculate_soc_som:
                    yearly_som_emissions, total_som_emissions = som_emissions(self.soc_end, self.soc_start, self.ef_nitrous_som, self.nitrous_constant, self.hectares_before_20)

                    som_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in yearly_som_emissions], ActivityTypes.SOM, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(som_emission_set)

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_soil():
            try:
                if self.calculate_soc_som:
                    yearly_soil_emissions, total_soil_emissions = soil_emissions_2(self.soc_start, self.soc_end, self.hectares_total, self.hectares_start, self.hectares_end, self.hectares_before_20)

                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in yearly_soil_emissions], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)
            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_biomass_emissions():

            # NOTE: should this be calculated only for main season?
            try:
                if self.calculate_biomass:
                    if not self.end_module_has_growth:
                        # NOTE: This means that we have received values for both (or we have tier 2 values for both)
                        emissions_biomass_yearly, emissions_biomass_total = biomass_emissions(self.biomass_end, self.biomass_start, self.hectares_start, self.hectares_end, self.rate_type, self.implementation_time, self.capitalization_time)

                        biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_biomass_yearly], ActivityTypes.BIOMASS, delay=self.delay)
                        self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

                    else:
                        # NOTE: In this case we are in the situation where biomass_final has to be calculated and is not tabulated
                        agb_rate = self.agb_rate_default * 44 / 12 if not self.agb_rate_tier_2 else self.agb_rate_tier_2 * 44 / 12
                        bgb_rate = self.bgb_rate_default * 44 / 12 if not self.bgb_rate_tier_2 else self.bgb_rate_tier_2 * 44 / 12

                        if self.agb_rate_tier_2:    
                            max_agb = 0 if self.agb_rate_default < self.agb_rate_tier_2 else self.agb_maximum_c * 44 / 12
                        else:
                            max_agb = self.agb_maximum_c * 44 / 12

                        biomass_accumulation_rate = agb_rate + bgb_rate

                        max_years_growth = max_agb / agb_rate

                        calculated = self.biomass_start + biomass_accumulation_rate * sum(self.hectares_total) 
                        tabular = (max_agb + bgb_rate * max_years_growth) * self.hectares_end

                        total = -min(calculated, tabular) if (max_agb != 0 and self.hectares_end != 0) else -calculated


                        # NOTE: maybe this should be broken down over max_years_growth or over all years of project depending on whether calculated or tabular is used
                        yearly_bio_emissions = breakdown_according_to_values_for_x_years(total, self.hectares_total, len(self.hectares_total))

                        biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in yearly_bio_emissions], ActivityTypes.BIOMASS, delay=self.delay)
                        self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)
                else:
                    pass

            except Exception as e:
                traceback.print_exc()
                raise e

        calculate_residue()
        calculate_som()
        calculate_soil()
        calculate_biomass_emissions()
