import traceback

from .general_functions import breakdown_according_to_values, soil_emissions_2, som_emissions, yearly_constant_emissions_breakdown, yearly_time_dependent_20_year_breakdown, yearly_time_dependent_parameter_breakdown, biomass_emissions
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
class AnnualCropland(LandModule):

    nitrous_constant: float
    methane_constant: float
    ef_methane_agr_residues_main: float
    combustion_factor_main: float
    residue_main_tier_2: Optional[float]
    n_estimation_slope_main: float
    n_estimation_intercept_main: float
    yield_value_main: float
    ef_methane_agr_residues_minor: float
    combustion_factor_minor: float
    residue_minor_tier_2: Optional[float]
    n_estimation_slope_minor: float
    n_estimation_intercept_minor: float
    yield_value_minor: float
    ef_nitrous_agr_residues_main: float
    retained_main: bool
    ef_nitrous_agr_residues_minor: float
    retained_minor: bool
    n_content_ag_main: float
    ratio_bg_ag_main: float
    n_content_bg_main: float
    n_content_ag_minor: float
    ratio_bg_ag_minor: float
    n_content_bg_minor: float
    yield_main_tier_2: Optional[float]
    yield_minor_tier_2: Optional[float]

    def __post_init__(self):
        super().__post_init__()

        self.yield_main = self.yield_main_tier_2 or self.yield_value_main
        self.yield_minor = self.yield_minor_tier_2 or self.yield_value_minor

        # NOTE: this is a default value that is calculated based on the input values, needed for the frontend
        self.ag_residue_main_tier_2_default = self.yield_main * self.n_estimation_slope_main + self.n_estimation_intercept_main
        self.ag_residue_minor_tier_2_default = self.yield_minor * self.n_estimation_slope_minor + self.n_estimation_intercept_minor
        
    def calculate_emissions(self):
        def calculate_emissions_soil():
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

        def calculate_emissions_residue_burning():
            ################## COMPUTATION OF AMOUNT OF KG OF METHANE ###################

            yield_value_main = self.yield_main * 1000
            yield_value_minor = self.yield_value_minor * 1000 if self.yield_value_minor else None

            ag_residue_main = self.residue_main_tier_2 * 1000 if self.residue_main_tier_2 else yield_value_main * self.n_estimation_slope_main + self.n_estimation_intercept_main
            ag_residue_tonnes_main = ag_residue_main / 1000
            if self.ef_methane_agr_residues_main:
                main_season_methane = ag_residue_tonnes_main * self.ef_methane_agr_residues_main * self.combustion_factor_main
            else:
                main_season_methane = 0
            ag_residue_minor = self.residue_minor_tier_2 * 1000 if self.residue_minor_tier_2 else yield_value_minor * self.n_estimation_slope_minor + self.n_estimation_intercept_minor if yield_value_minor else 0
            ag_residue_tonnes_minor = ag_residue_minor / 1000
            if self.ef_methane_agr_residues_minor:
                minor_season_methane = ag_residue_tonnes_minor * self.ef_methane_agr_residues_minor * self.combustion_factor_minor
            else:
                minor_season_methane = 0

            kg_methane = main_season_methane + minor_season_methane

            #################### COMPUTATION OF AMOUNT OF KG OF NITROUS ######################
            annual_n_residues_main = ag_residue_main * self.n_content_ag_main + (yield_value_main + ag_residue_main) * self.ratio_bg_ag_main * self.n_content_bg_main
            # COMPUTATION FOR MAIN
            # this means if "Burned"
            if self.ef_nitrous_agr_residues_main:
                main_season_nitrous = ag_residue_tonnes_main * self.ef_nitrous_agr_residues_main * self.combustion_factor_main
            # this means if "Retained"
            elif self.retained_main:
                n2o_n_conversion = 44 / 28
                main_season_nitrous = annual_n_residues_main * self.ef_nitrous_som * n2o_n_conversion
            else:
                main_season_nitrous = 0
            # COMPUTATION FOR MINOR
            annual_n_residues_minor = ag_residue_minor * self.n_content_ag_minor + (yield_value_minor + ag_residue_minor) * self.ratio_bg_ag_minor * self.n_content_bg_minor if yield_value_minor else 0
            # COMPUTATION FOR MAIN
            # this means if "Burned"

            if self.ef_nitrous_agr_residues_minor:
                minor_season_nitrous = ag_residue_tonnes_minor * self.ef_nitrous_agr_residues_minor * self.combustion_factor_minor
            # this means if "Retained" BUT IN REALITY NOT REALLY, AT LEAST IT SEEMS TO WORK (WITHOUT A MINOR)
            elif self.retained_minor:
                n2o_n_conversion = 44 / 28
                minor_season_nitrous = annual_n_residues_minor * self.ef_nitrous_som * n2o_n_conversion
            else:
                minor_season_nitrous = 0

            kg_nitrous = main_season_nitrous + minor_season_nitrous

            #################### COMPUTATION OF TOTAL EMISSIONS ######################
            total_nitrous = (sum(self.hectares_total)) * kg_nitrous * self.nitrous_constant / 1000
            total_methane = (sum(self.hectares_total)) * kg_methane * self.methane_constant / 1000

            residue_burning_nitrous_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in breakdown_according_to_values(total_nitrous, self.hectares_total)], ActivityTypes.RESIDUE_BURNING, delay=self.delay)
            residue_burning_methane_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in breakdown_according_to_values(total_methane, self.hectares_total)], ActivityTypes.RESIDUE_BURNING, delay=self.delay)

            self.result.yearly_emissions_by_sector_by_gas.append(residue_burning_nitrous_emission_set)
            self.result.yearly_emissions_by_sector_by_gas.append(residue_burning_methane_emission_set)

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

        calculate_emissions_soil()
        calculate_emissions_som()
        calculate_emissions_residue_burning()
        calculate_biomass_emissions()
