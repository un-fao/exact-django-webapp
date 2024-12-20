from generalized_modules import BaseModule, LandModule
from general_functions import (
    yearly_time_dependent_parameter_breakdown,
    yearly_time_dependent_matrix,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_matrix_log_rec_dis,
    create_agb_bgb_matrix,
    create_bgb_matrix_from_agb,
    breakdown_agb_bgb_emissions,
    calculate_rotation_effect,
    multiply_matrix_by_matrix,
    calculate_logging_effect,
    create_litter_deadwood_matrix,
    check_agb_matrices,
    soil_emissions_2,
    som_emissions,
    remove_values_not_on_diagonal,
    plot_matrix_with_values,
    forest_start_logging_matrix
)

from typing import Optional, Self
from ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)
from generalized_modules import LandModule
from dataclasses import dataclass, field
import numpy as np
import traceback

# NOTE: ForestManagement class extends LandModule even though it does not have a biomass_start and end. 
# As these variables have beene set to Optional for Perennial it should work fine.
@dataclass
class ForestManagement(BaseModule):
    """Forest management module"""
    
    ########### VARIABLES FOR W AND WO CASES ############
    is_same_forest_type: bool
    forest_start: Optional[Self]
    
    ########### GENERAL LAND MODULE VARIABLES ############ # NOTE: Can't directly extend LandModule as it has biomass values (consider changing this)
    hectares_start: float
    hectares_end: float

    soc_start_default: float
    soc_end_default: float
    soc_start_tier_2: Optional[float]
    soc_end_tier_2: Optional[float]
    fmg_start_default: float
    fmg_end_default: float
    fmg_start_tier_2: Optional[float]
    fmg_end_tier_2: Optional[float]
    flu_start_default: float
    flu_end_default: float
    flu_start_tier_2: Optional[float]
    flu_end_tier_2: Optional[float]
    fi_start_default: float
    fi_end_default: float
    fi_start_tier_2: Optional[float]
    fi_end_tier_2: Optional[float]
    
    ef_nitrous_som: float
    
    
    ########### AGB and BGB RELATED VARIABLES ############
    agb_yearly_growth_over_20_default : float
    agb_yearly_growth_over_20_tier_2 : float
    agb_yearly_growth_under_20_default : float
    agb_yearly_growth_under_20_tier_2 : float
    bgb_ratio_threshold : float
    bgb_ratio_under_threshold : float
    bgb_ratio_over_threshold : float
    bgb_yearly_growth_under_20_tier_2 : float
    bgb_yearly_growth_over_20_tier_2 : float
    agb_start_default : float
    agb_start_tier_2 : float
    max_agb_value : float
    max_bgb_value: Optional[float] # NOTE: AS OF NOW IT'S NOT USED YET, PREDISPONED FOR FUTURE IMPLEMENTATION

    ########### ROTATION RELATED VARIABLES ############
    rotation_recurrence: int
    rotation_start_year: int
    rotation_percentage_energy: float

    ########### DISTURBANCE RELATED VARIABLES ############
    disturbance_recurrence : list[int]
    disturbance_percentage : list[float]
    disturbance_year_of_start : list[int]

    ########### DEGRADATION RELATED VARIABLES ############
    degradation_percentage : float

    ########### LOGGING RELATED VARIABLES ############
    logging_recurrence : int
    logging_percentage : float
    logging_percentage_energy : float
    logging_year_of_start : int

    ########### LITTER AND DEADWOOD RELATED VARIABLES ############
    litter_20_years_default : float
    litter_20_years_tier_2 : float
    litter_start : float
    litter_max : float
    deadwood_20_years_default : float
    deadwood_20_years_tier_2 : float
    deadwood_start : float
    deadwood_max : float

    ########### EMISSION FACTORS ############
    ef_methane : float
    ef_nitrous : float

    ########### BURNING FACTORS ############
    forest_cf : float
    forest_gef_ch4 : float
    forest_gef_n2o : float
    forest_gef_co2 : float

    ########### CONSTANTS ############
    nitrous_constant : float
    methane_constant : float
    mangrove_factor : float

    def __post_init__(self):
        super().__post_init__()
        
        # TODO: This is like this because to all calculation extents, if the rate is immediate, the implementation time of the project is basically 1 year
        # hence all the time dependent calculations for rotation ecc are to be considered on 1 year and not multiple years. The capitalization then becomes 
        # equivalent to capitalization + implementation + 1
        self.capitalization_time = self.capitalization_time if not self.rate_type == 'immediate' else self.capitalization_time + self.implementation_time + 1
        self.implementation_time = self.implementation_time if not self.rate_type == 'immediate' else 1

        ########### MATRIX ASSIGNMENT ############
        # Hectares at each year of the project
        self.hectares_total = yearly_time_dependent_parameter_breakdown(self.hectares_start, self.hectares_end, self.implementation_time, self.capitalization_time, self.rate_type)
        # Hectares which have reached and have not 20 years of maturity, necessary for soil emissions
        self.hectares_before_20, self.hectares_after_20 = yearly_time_dependent_20_year_breakdown(self.hectares_start, self.hectares_end, self.implementation_time, self.capitalization_time, self.rate_type)
        
        # these two have to be set to absolute values, as if hectares_start > hectares_end, the matrix will have negative values
        self.hectares_matrix = yearly_time_dependent_matrix(self.hectares_start, self.hectares_end, self.implementation_time, self.capitalization_time, self.rate_type)
        self.hectares_for_rot_log_dis = yearly_time_dependent_matrix_log_rec_dis(self.hectares_start, self.hectares_end, self.implementation_time, self.capitalization_time, self.rate_type)
        
        ########### GENERAL VARIABLE ASSIGNMENTS ############
        self.agb_yearly_growth_over_20 = self.agb_yearly_growth_over_20_default if not self.agb_yearly_growth_over_20_tier_2 else self.agb_yearly_growth_over_20_tier_2
        self.agb_yearly_growth_under_20 = self.agb_yearly_growth_under_20_default if not self.agb_yearly_growth_under_20_tier_2 else self.agb_yearly_growth_under_20_tier_2
        self.agb_start = self.agb_start_default if not self.agb_start_tier_2 else self.agb_start_tier_2
        self.bgb_start = self.agb_start * self.bgb_ratio_under_threshold if self.agb_start < self.bgb_ratio_threshold else self.agb_start * self.bgb_ratio_over_threshold
        self.max_bgb_value = self.max_agb_value * self.bgb_ratio_under_threshold if self.max_agb_value < self.bgb_ratio_threshold else self.max_agb_value * self.bgb_ratio_over_threshold
        self.litter_20_years = self.litter_20_years_default if not self.litter_20_years_tier_2 else self.litter_20_years_tier_2
        self.deadwood_20_years = self.deadwood_20_years_default if not self.deadwood_20_years_tier_2 else self.deadwood_20_years_tier_2
        
        ########### GENERALE LAND MODULE ASSIGNMENTS ############
        fmg_start = self.fmg_start_tier_2 or self.fmg_start_default
        fmg_end = self.fmg_end_tier_2 or self.fmg_end_default
        flu_start = self.flu_start_tier_2 or self.flu_start_default
        flu_end = self.flu_end_tier_2 or self.flu_end_default
        fi_start = self.fi_start_tier_2 or self.fi_start_default
        fi_end = self.fi_end_tier_2 or self.fi_end_default
        soc_ref_start = self.soc_start_tier_2 or self.soc_start_default
        soc_ref_end = self.soc_end_tier_2 or self.soc_end_default

        self.soc_start = soc_ref_start * fmg_start * fi_start * flu_start
        self.soc_end = soc_ref_end * fmg_end * fi_end * flu_end

        ########### AGB AND BGB MATRIX CREATION ############
        # NOTE: We have to understand if we're in Afforestation or Forest Remaining Forest (Deforesation Occurs in the Defo module)
        affo_bool = self.hectares_end > self.hectares_start
        self.affo_bool = affo_bool
        
        if self.agb_start == 0:
            # This is the case of afforestation, as we don't have any AGB or BGB at the start
            agb_matrix, delta_agb_matrix = create_agb_bgb_matrix(self.implementation_time, self.capitalization_time, self.agb_yearly_growth_under_20, self.agb_yearly_growth_over_20, self.agb_start, self.rotation_recurrence, affo_bool)
            if self.bgb_yearly_growth_over_20_tier_2 and self.bgb_yearly_growth_under_20_tier_2:
                bgb_matrix, delta_bgb_matrix = create_agb_bgb_matrix(self.implementation_time, self.capitalization_time, self.bgb_yearly_growth_under_20_tier_2, self.bgb_yearly_growth_over_20_tier_2, self.bgb_start, self.rotation_recurrence, affo_bool)
            else:
                bgb_matrix, delta_bgb_matrix = create_bgb_matrix_from_agb(agb_matrix, delta_agb_matrix, self.bgb_ratio_under_threshold, self.bgb_ratio_over_threshold, self.bgb_ratio_threshold, self.bgb_start, self.implementation_time)
            
        else:
            # NOTE: THIS MEANS WE ARE IN FOREST REMAINING FOREST
            # THE ONLY DIFFERENCE BETWEEN THE TWO CASES IS THAT WE DON'T UTILIZE YEARLY GROWTH UNDER 20, BUT ALWAYS OVER 20 AS THE FOREST WAS ALREADY EXISTING. SAME FOR BGB
            if not self.is_same_forest_type:
                agb_matrix, delta_agb_matrix = create_agb_bgb_matrix(self.implementation_time, self.capitalization_time, self.agb_yearly_growth_over_20, self.agb_yearly_growth_over_20, self.agb_start, self.rotation_recurrence, affo_bool)
                if self.bgb_yearly_growth_over_20_tier_2 and self.bgb_yearly_growth_under_20_tier_2:
                    bgb_matrix, delta_bgb_matrix = create_agb_bgb_matrix(self.implementation_time, self.capitalization_time, self.bgb_yearly_growth_over_20_tier_2, self.bgb_yearly_growth_over_20_tier_2, self.bgb_start, self.rotation_recurrence, affo_bool)
                else:
                    bgb_matrix, delta_bgb_matrix = create_bgb_matrix_from_agb(agb_matrix, delta_agb_matrix, self.bgb_ratio_under_threshold, self.bgb_ratio_over_threshold, self.bgb_ratio_threshold, self.bgb_start, self.implementation_time, affo_bool, self.is_same_forest_type)
            else:
                # NOTE: This means we have the same forest type, hence we don't have to create a new agb and bgb matrix, but we can use the one from the previous forest module
                agb_matrix, delta_agb_matrix = create_agb_bgb_matrix(self.implementation_time, self.capitalization_time, self.agb_yearly_growth_over_20, self.agb_yearly_growth_over_20, self.agb_start, self.rotation_recurrence, affo_bool, self.is_same_forest_type, self.forest_start )
                bgb_matrix, delta_bgb_matrix = create_bgb_matrix_from_agb(agb_matrix, delta_agb_matrix, self.bgb_ratio_under_threshold, self.bgb_ratio_over_threshold, self.bgb_ratio_threshold, self.bgb_start, self.implementation_time, affo_bool, self.is_same_forest_type, self.forest_start)
                
                plot_matrix_with_values(self.forest_start.agb_matrix, title="agb matrix from previous module")
                plot_matrix_with_values(self.forest_start.bgb_matrix, title="BGB Matrix from previous module")
                
                plot_matrix_with_values(agb_matrix, title="agb matrix developed from previous module")
                plot_matrix_with_values(bgb_matrix, title="BGB Matrix developed from previous module")

        self.agb_matrix = agb_matrix
        self.bgb_matrix = bgb_matrix
        self.delta_agb_matrix = delta_agb_matrix
        self.delta_bgb_matrix = delta_bgb_matrix
        
    def update_delta_agb_and_bgb_matrix(self, new_delta_agb_matrix, new_delta_bgb_matrix, abg_matrix, bgb_matrix):
        self.delta_agb_matrix = new_delta_agb_matrix
        self.delta_bgb_matrix = new_delta_bgb_matrix
        self.agb_matrix = abg_matrix
        self.bgb_matrix = bgb_matrix
        
    def calculate_emissions(self):
        
        def calculate_rotation():
            
            try:
                
                # NOTE: No emissions for Rotation are generated in the START scenario, new practices are applied. Even though the matrix is not null, 
                # the hectares are null, hence no emissions are generated. The check on affo_bool means it's not the start scenario, no rotation in start
                if self.affo_bool:
                    result_rotation_agb, rotation_matrix_agb, delta_agb_matrix, agb_matrix = calculate_rotation_effect(self.agb_matrix, self.delta_agb_matrix, self.max_agb_value, self.rotation_recurrence, self.rotation_start_year)
                    result_rotation_bgb, rotation_matrix_bgb, delta_bgb_matrix, bgb_matrix = calculate_rotation_effect(self.bgb_matrix, self.delta_bgb_matrix, self.max_bgb_value, self.rotation_recurrence, self.rotation_start_year)
                    
                    plot_matrix_with_values(self.agb_matrix, title="AGB Matrix in rotation")
                    plot_matrix_with_values(self.bgb_matrix, title="BGB Matrix in rotation")
                    
                    plot_matrix_with_values(rotation_matrix_agb, title="Rotation Matrix AGB")
                    plot_matrix_with_values(rotation_matrix_bgb, title="Rotation Matrix BGB")
                    
                    rotation_times_hectares_agb = multiply_matrix_by_matrix(rotation_matrix_agb, self.hectares_for_rot_log_dis)
                    rotation_times_hectares_bgb = multiply_matrix_by_matrix(rotation_matrix_bgb, self.hectares_for_rot_log_dis)

                    (hwp_rotation_agb, hwp_rotation_bgb, nitrous_fire_component_agb, methane_fire_component_agb, nitrous_fire_component_bgb, methane_fire_component_bgb, co2_fire_component_agb, co2_fire_component_bgb) = breakdown_agb_bgb_emissions(rotation_times_hectares_agb, rotation_times_hectares_bgb, self.rotation_percentage_energy, self.forest_cf, self.forest_gef_ch4, self.forest_gef_n2o, self.forest_gef_co2, self.mangrove_factor, self.ef_nitrous, self.ef_methane)

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in hwp_rotation_agb], activity=ActivityTypes.HWP_ROTATION_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in hwp_rotation_bgb], activity=ActivityTypes.HWP_ROTATION_BGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_agb], activity=ActivityTypes.ROTATION_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_agb], activity=ActivityTypes.ROTATION_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_bgb], activity=ActivityTypes.ROTATION_BGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_bgb], activity=ActivityTypes.ROTATION_BGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in co2_fire_component_agb], activity=ActivityTypes.ROTATION_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in co2_fire_component_bgb], activity=ActivityTypes.ROTATION_BGB, delay=self.delay))
                    
                    # NOTE: This is necessary as we need to update the delta matrices with the new values because they are used further on for bgb and agb calculations
                    self.update_delta_agb_and_bgb_matrix(delta_agb_matrix, delta_bgb_matrix, agb_matrix, bgb_matrix)
    
            
            except Exception as e:
                traceback.print_exc()
                raise e
            
        def calculate_disturbance_or_logging():
            
            try:
                # CALCULATION FOR DISTURBANCE
                for recurrence, percentage, percentage_fire, start_year in zip(self.disturbance_recurrence, self.disturbance_percentage, [0 for i in self.disturbance_percentage], self.disturbance_year_of_start):
                    # NOTE: As logging and disturbance are the same, we can use the same function, however as we can see from above the percentage_fire is set to 0 for disturbance, as everything is lost and not burnt
                    result_disturbance_agb, logging_matrix_agb, delta_agb_matrix, agb_matrix = calculate_logging_effect(self.agb_matrix, self.delta_agb_matrix, self.max_agb_value, recurrence, start_year, percentage)
                    result_disturbance_bgb, logging_matrix_bgb, delta_bgb_matrix, bgb_matrix = calculate_logging_effect(self.bgb_matrix, self.delta_bgb_matrix, self.max_bgb_value, recurrence, start_year, percentage)

                    disturbance_times_hectares_agb = multiply_matrix_by_matrix(logging_matrix_agb, self.hectares_for_rot_log_dis)
                    disturbance_times_hectares_bgb = multiply_matrix_by_matrix(logging_matrix_bgb, self.hectares_for_rot_log_dis)

                    (agb_disturbance_component, bgb_disturbance_component, nitrous_fire_component_agb, methane_fire_component_agb, nitrous_fire_component_bgb, methane_fire_component_bgb, co2_fire_component_agb, co2_fire_component_bgb) = breakdown_agb_bgb_emissions(disturbance_times_hectares_agb, disturbance_times_hectares_bgb, percentage_fire, self.forest_cf, self.forest_gef_ch4, self.forest_gef_n2o, self.forest_gef_co2, self.mangrove_factor, self.ef_nitrous, self.ef_methane)

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in agb_disturbance_component], activity=ActivityTypes.DISTURBANCE_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in bgb_disturbance_component], activity=ActivityTypes.DISTURBANCE_BGB, delay=self.delay))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_agb], activity=ActivityTypes.DISTURBANCE_FIRE_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_agb], activity=ActivityTypes.DISTURBANCE_FIRE_AGB, delay=self.delay))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_bgb], activity=ActivityTypes.DISTURBANCE_FIRE_BGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_bgb], activity=ActivityTypes.DISTURBANCE_FIRE_BGB, delay=self.delay))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in co2_fire_component_agb], activity=ActivityTypes.DISTURBANCE_FIRE_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in co2_fire_component_bgb], activity=ActivityTypes.DISTURBANCE_FIRE_BGB, delay=self.delay))

                    # NOTE: This is necessary as we need to update the delta matrices with the new values because they are used further on for bgb and agb calculations
                    self.update_delta_agb_and_bgb_matrix(delta_agb_matrix, delta_bgb_matrix, agb_matrix, bgb_matrix)
                                    
                if self.logging_recurrence:
                    # CALCULATION FOR LOGGING
                    result_logging_agb, logging_matrix_agb, delta_agb_matrix, agb_matrix = calculate_logging_effect(self.agb_matrix, self.delta_agb_matrix, self.max_agb_value, self.logging_recurrence, self.logging_year_of_start, self.logging_percentage)
                    result_logging_bgb, logging_matrix_bgb, delta_bgb_matrix, bgb_matrix = calculate_logging_effect(self.bgb_matrix, self.delta_bgb_matrix, self.max_bgb_value, self.logging_recurrence, self.logging_year_of_start, self.logging_percentage)
                      
                    logging_times_hectares_agb = multiply_matrix_by_matrix(logging_matrix_agb, self.hectares_for_rot_log_dis)
                    logging_times_hectares_bgb = multiply_matrix_by_matrix(logging_matrix_bgb, self.hectares_for_rot_log_dis)

                    (hwp_logging_agb, hwp_logging_bgb, nitrous_fire_component_agb, methane_fire_component_agb, nitrous_fire_component_bgb, methane_fire_component_bgb, co2_fire_component_agb, co2_fire_component_bgb) = breakdown_agb_bgb_emissions(logging_times_hectares_agb, logging_times_hectares_bgb, self.logging_percentage_energy, self.forest_cf, self.forest_gef_ch4, self.forest_gef_n2o, self.forest_gef_co2, self.mangrove_factor, self.ef_nitrous, self.ef_methane)

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in hwp_logging_agb], activity=ActivityTypes.HWP_LOGGING_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in hwp_logging_bgb], activity=ActivityTypes.HWP_LOGGING_BGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_agb], activity=ActivityTypes.LOGGING_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_agb], activity=ActivityTypes.LOGGING_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_bgb], activity=ActivityTypes.LOGGING_BGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_bgb], activity=ActivityTypes.LOGGING_BGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in co2_fire_component_agb], activity=ActivityTypes.LOGGING_AGB, delay=self.delay))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in co2_fire_component_bgb], activity=ActivityTypes.LOGGING_BGB, delay=self.delay))
                    
                # NOTE: This is necessary as we need to update the delta matrices with the new values because they are used further on for bgb and agb calculations
                self.update_delta_agb_and_bgb_matrix(delta_agb_matrix, delta_bgb_matrix, agb_matrix, bgb_matrix)
            
            except Exception as e:
                traceback.print_exc()
                raise e
            
        def calculate_degradation():
            
            try:
                result_degradation_agb, degradation_matrix_agb, delta_agb_matrix, agb_matrix = calculate_logging_effect(self.agb_matrix, self.delta_agb_matrix, self.max_agb_value, 1, 0, self.degradation_percentage, is_degradation=True)
                result_degradation_bgb, degradation_matrix_bgb, delta_bgb_matrix, bgb_matrix = calculate_logging_effect(self.bgb_matrix, self.delta_bgb_matrix, self.max_bgb_value, 1, 0, self.degradation_percentage, is_degradation=True)

                degradation_times_hectares_agb = multiply_matrix_by_matrix(degradation_matrix_agb, self.hectares_for_rot_log_dis)
                degradation_times_hectares_bgb = multiply_matrix_by_matrix(degradation_matrix_bgb, self.hectares_for_rot_log_dis)

                degradation_agb_emissions = [x * -44 / 12 for x in degradation_times_hectares_agb]
                degradation_bgb_emissions = [x * -44 / 12 for x in degradation_times_hectares_bgb]

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in degradation_agb_emissions], activity=ActivityTypes.DEGRADATION_AGB, delay=self.delay))
                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in degradation_bgb_emissions], activity=ActivityTypes.DEGRADATION_BGB, delay=self.delay))

                # NOTE: This is necessary as we need to update the delta matrices with the new values because they are used further on for bgb and agb calculations
                self.update_delta_agb_and_bgb_matrix(delta_agb_matrix, delta_bgb_matrix, agb_matrix, bgb_matrix)
            except Exception as e:
                traceback.print_exc()
                raise e
        
        def calculate_agb_bgb_emissions():
            
            try:
                # NOTE: We start with a check to see if the agb_matrix has negative values, if it does, it means that the parameters for logging and disturbance are such that the agb_matrix has negative values
                if np.any(np.sum(self.agb_matrix < 0), axis=0):
                    raise ValueError(f"Negative values in agb_matrix, check the parameters for logging and disturbance % over 100")

                check_agb_matrices(self.agb_matrix, self.delta_agb_matrix, self.max_agb_value)
                check_agb_matrices(self.bgb_matrix, self.delta_bgb_matrix, self.max_bgb_value)
                
                plot_matrix_with_values(self.agb_matrix, title="AGB Matrix after")
                
                agb_times_hectares = multiply_matrix_by_matrix(self.delta_agb_matrix, self.hectares_matrix)
                yearly_agb_emissions = [x * -44 / 12 for x in agb_times_hectares]

                bgb_times_hectares = multiply_matrix_by_matrix(self.delta_bgb_matrix, self.hectares_matrix)
                yearly_bgb_emissions = [x * -44 / 12 for x in bgb_times_hectares]

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in yearly_agb_emissions], activity=ActivityTypes.AGB_GROWTH, delay=self.delay))
                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in yearly_bgb_emissions], activity=ActivityTypes.BGB_GROWTH, delay=self.delay))

            except Exception as e:
                traceback.print_exc()
                raise
            
        def calculate_litter():
            try:

                litter_matrix, delta_litter_matrix = create_litter_deadwood_matrix(self.implementation_time, self.capitalization_time, self.litter_20_years / 20, self.litter_start, self.litter_max)

                if self.degradation_percentage:
                    # NOTE: This means we have degradation, which has an impact on litter and deadwood as well
                    result_litter, degradation_litter_matrix, delta_litter_matrix, litter_matrix = calculate_logging_effect(litter_matrix, delta_litter_matrix, self.litter_max, 1, 0, self.degradation_percentage, is_degradation=True)

                    degradation_times_hectares_litter = multiply_matrix_by_matrix(degradation_litter_matrix, self.hectares_for_rot_log_dis)
                    degradation_litter_yearly_emissions = [x * -44 / 12 for x in degradation_times_hectares_litter]

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in degradation_litter_yearly_emissions], activity=ActivityTypes.DEGRADATION_LITTER, delay=self.delay))

                else:
                    litter_matrix, delta_litter_matrix = check_agb_matrices(litter_matrix, delta_litter_matrix, self.litter_max)

                yearly_litter_emissions = [x * -44 / 12 for x in multiply_matrix_by_matrix(delta_litter_matrix, self.hectares_matrix)]


                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in yearly_litter_emissions], activity=ActivityTypes.LITTER, delay=self.delay))

            except Exception as e:
                traceback.print_exc()
                raise e
        
        def calculate_deadwood():
            try:
                deadwood_matrix, delta_deadwood_matrix = create_litter_deadwood_matrix(self.implementation_time, self.capitalization_time, self.deadwood_20_years / 20, self.deadwood_start, self.deadwood_max)

                if self.degradation_percentage:
                    # NOTE: This means we have degradation, which has an impact on litter and deadwood as well
                    result_deadwood, deadwood_matrix, delta_deadwood_matrix, deadwood_matrix = calculate_logging_effect(deadwood_matrix, delta_deadwood_matrix, self.deadwood_max, 1, 0, self.degradation_percentage, is_degradation=True)

                    degradation_times_hectares_deadwood = multiply_matrix_by_matrix(deadwood_matrix, self.hectares_for_rot_log_dis)
                    degradation_deadwood_litter_emissions = [x * -44 / 12 for x in degradation_times_hectares_deadwood]

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in degradation_deadwood_litter_emissions], activity=ActivityTypes.DEGRADATION_DEADWOOD, delay=self.delay))

                else:
                    deadwood_matrix, delta_deadwood_matrix = check_agb_matrices(deadwood_matrix, delta_deadwood_matrix, self.deadwood_max)

                yearly_deadwood_emissions = [x * -44 / 12 for x in multiply_matrix_by_matrix(delta_deadwood_matrix, self.hectares_matrix)]

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in yearly_deadwood_emissions], activity=ActivityTypes.DEADWOOD, delay=self.delay))

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_emissions_soil():
            try:
                emissions_soil_yearly, emissions_soil_total = soil_emissions_2(self.soc_start, self.soc_end, self.hectares_total, self.hectares_start, self.hectares_end, self.hectares_before_20)

                soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_soil_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_emissions_som():
            try:
                emissions_som_yearly, emissions_som_total = som_emissions(self.soc_end, self.soc_start, self.ef_nitrous_som, self.nitrous_constant, self.hectares_before_20)

                som_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in emissions_som_yearly], ActivityTypes.SOM, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(som_emission_set)
            except Exception as e:
                traceback.print_exc()
                raise e

         
        # NOTE: Rotation, disturbance-logging and degradation are mutually exclusive. If one is set, the other two are not.
        if self.rotation_recurrence:
            # This means we have rotation, if not rotation_recurrence is None
            calculate_rotation()
        elif self.disturbance_recurrence or self.logging_recurrence:
            # This means we have disturbance or logging, if not disturbance_recurrence or logging_recurrence is None
            calculate_disturbance_or_logging()
        elif self.degradation_percentage:
            # This means we have degradation, if not degradation_percentage is None
            calculate_degradation()
        # NOTE: As the three above have impact of the agb, bgb, delta_agb and delta_bgb matrices, we have to calculate the emissions after all of them
        calculate_agb_bgb_emissions()
        calculate_litter()
        calculate_deadwood()
        calculate_emissions_soil()
        calculate_emissions_som()
        
        



inputs_start = {'capitalization_time': 15, 
          'implementation_time': 10, 
          'rate_type': 'linear', 
          'hectares_start': 1000, 
          'hectares_end': 0, 
          'rotation_recurrence': None, 
          'rotation_start_year': 0, 
          'rotation_percentage_energy': 0.2, 
          'bgb_ratio_threshold': 125.0, 
          'bgb_ratio_under_threshold': 0.284, 
          'bgb_ratio_over_threshold': 0.284, 
          'bgb_yearly_growth_under_20_tier_2': None,
          'bgb_yearly_growth_over_20_tier_2': None, 
          'agb_start_default': 60.39, 
          'agb_start_tier_2': None, 
          'agb_yearly_growth_under_20_default': 2.5, 
          'agb_yearly_growth_under_20_tier_2': None, 
          'agb_yearly_growth_over_20_default':  2.5, 
          'agb_yearly_growth_over_20_tier_2': None, 
          'max_agb_value': 61.56999999999999, 
          'max_bgb_value': None, 
          'disturbance_recurrence': [], 
          'disturbance_percentage': [], 
          'disturbance_year_of_start': [],
          'logging_recurrence': None, 
          'logging_percentage': 0.2, 
          'logging_percentage_energy': 0.5,
          'logging_year_of_start': 0, 
          'litter_20_years_default': 5.9, 
          'litter_start': 5.9, 
          'litter_max': 5.9, 
          'litter_20_years_tier_2': None,
          'deadwood_20_years_default': 8.0, 
          'deadwood_start': 8.0, 
          'deadwood_max': 8.0, 
          'deadwood_20_years_tier_2': None, 
          'soc_start_default': 40.0, 
          'soc_end_default': 40.0, 
          'soc_start_tier_2': None, 
          'soc_end_tier_2': None, 
          'fmg_start_default': 1, 
          'fmg_end_default': 1, 
          'fmg_start_tier_2': None, 
          'fmg_end_tier_2': None, 
          'flu_start_default': 1, 
          'flu_end_default': 1, 
          'flu_start_tier_2': None, 
          'flu_end_tier_2': None, 
          'fi_start_default': 1, 
          'fi_end_default': 1,
          'fi_start_tier_2': None, 
          'fi_end_tier_2': None, 
          'ef_methane': 28.0, 
          'ef_nitrous': 265.0,
          'forest_cf': 0.36, 
          'forest_gef_ch4': 6.8,
          'forest_gef_n2o': 0.2,
          'forest_gef_co2': 1580.0, 
          'mangrove_factor': 0.451,
          'degradation_percentage': 0.0, 
          'ef_nitrous_som': 0.0055, 
          'nitrous_constant': 265.0,
          'methane_constant': 28.0, 
          'delay': 0,
          'is_same_forest_type': False,
          'forest_start': None,}

ao = ForestManagement(**inputs_start)
ao.calculate_emissions()
ao.result.plot_emissions_and_aggregate_by_activity('start')
plot_matrix_with_values(ao.agb_matrix, title="AGB Matrix ao")

inputs_w = {'capitalization_time': 15, 
          'implementation_time': 10, 
          'rate_type': 'linear', 
          'hectares_start': 0, 
          'hectares_end': 1000, 
          'rotation_recurrence': 5, 
          'rotation_start_year': 0, 
          'rotation_percentage_energy': 0.2, 
          'bgb_ratio_threshold': 125.0, 
          'bgb_ratio_under_threshold': 0.284, 
          'bgb_ratio_over_threshold': 0.284, 
          'bgb_yearly_growth_under_20_tier_2': None,
          'bgb_yearly_growth_over_20_tier_2': None, 
          'agb_start_default': 60.39, 
          'agb_start_tier_2': None, 
          'agb_yearly_growth_under_20_default': 2.5, 
          'agb_yearly_growth_under_20_tier_2': None, 
          'agb_yearly_growth_over_20_default':  2.5, 
          'agb_yearly_growth_over_20_tier_2': None, 
          'max_agb_value': 61.56999999999999, 
          'max_bgb_value': None, 
          'disturbance_recurrence': [], 
          'disturbance_percentage': [], 
          'disturbance_year_of_start': [],
          'logging_recurrence': None, 
          'logging_percentage': 0.02, 
          'logging_percentage_energy': 0.5,
          'logging_year_of_start': 0, 
          'litter_20_years_default': 5.9, 
          'litter_start': 5.9, 
          'litter_max': 5.9, 
          'litter_20_years_tier_2': None,
          'deadwood_20_years_default': 8.0, 
          'deadwood_start': 8.0, 
          'deadwood_max': 8.0, 
          'deadwood_20_years_tier_2': None, 
          'soc_start_default': 40.0, 
          'soc_end_default': 40.0, 
          'soc_start_tier_2': None, 
          'soc_end_tier_2': None, 
          'fmg_start_default': 1, 
          'fmg_end_default': 1, 
          'fmg_start_tier_2': None, 
          'fmg_end_tier_2': None, 
          'flu_start_default': 1, 
          'flu_end_default': 1, 
          'flu_start_tier_2': None, 
          'flu_end_tier_2': None, 
          'fi_start_default': 1, 
          'fi_end_default': 1,
          'fi_start_tier_2': None, 
          'fi_end_tier_2': None, 
          'ef_methane': 28.0, 
          'ef_nitrous': 265.0,
          'forest_cf': 0.36, 
          'forest_gef_ch4': 6.8,
          'forest_gef_n2o': 0.2,
          'forest_gef_co2': 1580.0, 
          'mangrove_factor': 0.451,
          'degradation_percentage': 0.0, 
          'ef_nitrous_som': 0.0055, 
          'nitrous_constant': 265.0,
          'methane_constant': 28.0, 
          'delay': 0,
          'is_same_forest_type': True,
          'forest_start': ao,}

ao2 = ForestManagement(**inputs_w)
ao2.calculate_emissions()

ao2.result.plot_emissions_and_aggregate_by_activity('with')

 
 

