import copy
import traceback

import matplotlib.pyplot as plt
import numpy as np

from .general_functions import (
    BaseModule,
    breakdown_according_to_values,
    soil_emissions_2,
    som_emissions,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_full_year,
    yearly_time_dependent_increase_half_year,
    yearly_time_dependent_matrix,
    yearly_time_dependent_parameter_breakdown,
    yearly_time_dependent_matrix_log_rec_dis
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)



class ForestManagement(BaseModule):
    def __init__(
        self,
        years_cap,
        years_impl,
        rate,
        hectares_start,
        hectares_end,
        rotation_recurrence,
        rotation_start_year,
        rotation_percentage_energy,
        bgb_ratio_threshold,
        bgb_ratio_under_threshold,
        bgb_ratio_over_threshold,
        bgb_yearly_growth_under_20_tier_2,
        bgb_yearly_growth_over_20_tier_2,
        agb_start_default,
        agb_start_tier_2,
        agb_yearly_growth_under_20_default,
        agb_yearly_growth_under_20_tier_2,
        agb_yearly_growth_over_20_default,
        agb_yearly_growth_over_20_tier_2,
        max_agb_value,
        max_bgb_value,
        disturbance_recurrence: list,
        disturbance_percentage: list,
        disturbance_year_of_start: list,
        logging_recurrence,
        logging_percentage,
        logging_percentage_energy,
        logging_year_of_start,
        litter_20_years_default,
        litter_start,  # -----> added litter start, initial value, if forest is already there it is value of litter if afforestation it is 0
        litter_max,  # -----> added litter max, maximum value of litter, value of forest being present
        litter_20_years_tier_2,
        deadwood_20_years_default,
        deadwood_start,  # -----> added deadwood start, initial value, if forest is already there it is value of deadwood if afforestation it is 0
        deadwood_max,  # -----> added deadwood max, maximum value of deadwood, value of forest being present
        deadwood_20_years_tier_2,
        soc_start_default,
        soc_end_default,
        soc_start_tier_2,
        soc_end_tier_2,
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
        ef_methane,
        ef_nitrous,
        forest_cf, 
        forest_gef_ch4,
        forest_gef_n2o,
        forest_gef_co2,
        mangrove_factor, # set to 0.47 if not mangrove else 0.451
        degradation_percentage,
        ef_nitrous_som,
        nitrous_constant,
        methane_constant,
        delay
    ):
        self.years_cap = years_cap if not rate == 'immediate' else years_cap + years_impl - 1
        self.years_impl = years_impl if not rate == 'immediate' else 1
        self.rate = rate
        self.hectares_start = hectares_start
        self.hectares_end = hectares_end
        self.rotation_recurrence = rotation_recurrence
        self.rotation_start_year = rotation_start_year
        self.rotation_percentage_energy = rotation_percentage_energy

        self.agb_yearly_growth_over_20 = agb_yearly_growth_over_20_default if not agb_yearly_growth_over_20_tier_2 else agb_yearly_growth_over_20_tier_2
        self.agb_yearly_growth_under_20 = agb_yearly_growth_under_20_default if not agb_yearly_growth_under_20_tier_2 else agb_yearly_growth_under_20_tier_2

        self.bgb_ratio_threshold = bgb_ratio_threshold
        self.bgb_ratio_under_threshold = bgb_ratio_under_threshold
        self.bgb_ratio_over_threshold = bgb_ratio_over_threshold

        self.bgb_yearly_growth_under_20_tier_2 = bgb_yearly_growth_under_20_tier_2
        self.bgb_yearly_growth_over_20_tier_2 = bgb_yearly_growth_over_20_tier_2

        self.agb_start = agb_start_default if not agb_start_tier_2 else agb_start_tier_2
        self.bgb_start = self.agb_start * self.bgb_ratio_under_threshold if self.agb_start < self.bgb_ratio_threshold else self.agb_start * self.bgb_ratio_over_threshold

        self.max_agb_value = max_agb_value
        self.max_bgb_value = self.max_agb_value * self.bgb_ratio_under_threshold if self.max_agb_value < self.bgb_ratio_threshold else self.max_agb_value * self.bgb_ratio_over_threshold

        self.disturbance_recurrence = disturbance_recurrence
        self.disturbance_percentage = disturbance_percentage
        self.disturbance_year_of_start = disturbance_year_of_start
        self.logging_recurrence = logging_recurrence
        self.logging_percentage = logging_percentage
        self.logging_percentage_energy = logging_percentage_energy
        self.logging_year_of_start = logging_year_of_start

        self.litter_20_years = litter_20_years_default if not litter_20_years_tier_2 else litter_20_years_tier_2
        self.litter_start = litter_start
        self.litter_max = litter_max
        self.deadwood_20_years = deadwood_20_years_default if not deadwood_20_years_tier_2 else deadwood_20_years_tier_2
        self.deadwood_start = deadwood_start
        self.deadwood_max = deadwood_max

        self.soc_start_default = soc_start_default
        self.soc_end_default = soc_end_default
        self.soc_start_tier_2 = soc_start_tier_2
        self.soc_end_tier_2 = soc_end_tier_2
        self.fmg_start_default = fmg_start_default  # defaulted to 1 in case there are None, if not float value
        self.fmg_end_default = fmg_end_default  # defaulted to 1 in case there are None, if not float value
        self.fmg_start_tier_2 = fmg_start_tier_2  # tier 2 value, expects float or None
        self.fmg_end_tier_2 = fmg_end_tier_2  # tier 2 value, expects float or None
        self.flu_start_default = flu_start_default  # defaulted to 1 in case there are None, if not float value
        self.flu_end_default = flu_end_default  # defaulted to 1 in case there are None, if not float value
        self.flu_start_tier_2 = flu_start_tier_2  # tier 2 value, expects float or None
        self.flu_end_tier_2 = flu_end_tier_2  # tier 2 value, expects float or None
        self.fi_start_default = fi_start_default  # defaulted to 1 in case there are None, if not float value
        self.fi_end_default = fi_end_default  # defaulted to 1 in case there are None, if not float value
        self.fi_start_tier_2 = fi_start_tier_2  # tier 2 value, expects float or None
        self.fi_end_tier_2 = fi_end_tier_2  # tier 2 value, expects float or None

        self.soc_start = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start if not self.soc_start_tier_2 else self.soc_start_tier_2
        self.soc_end = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end if not self.soc_end_tier_2 else self.soc_end_tier_2

        self.ef_methane = ef_methane
        self.ef_nitrous = ef_nitrous

        self.forest_cf = forest_cf
        self.forest_gef_ch4 = forest_gef_ch4
        self.forest_gef_n2o = forest_gef_n2o
        self.forest_gef_co2 = forest_gef_co2

        self.mangrove_factor = mangrove_factor
        self.degradation_percentage = degradation_percentage

        self.ef_nitrous_som = ef_nitrous_som
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.delay = delay


        # Hectares breakdown
        self.hectares_total = yearly_time_dependent_parameter_breakdown(self.hectares_start, self.hectares_end, self.years_impl, self.years_cap, self.rate)
        self.hectares_before_20, self.hectares_after_20 = yearly_time_dependent_20_year_breakdown(self.hectares_start, self.hectares_end, self.years_impl, self.years_cap, self.rate)
        self.hectares_matrix = yearly_time_dependent_matrix(self.hectares_start, self.hectares_end, self.years_impl, self.years_cap, self.rate)
        self.hectares_for_rot_log_dis = yearly_time_dependent_matrix_log_rec_dis(self.hectares_start, self.hectares_end, self.years_impl, self.years_cap, self.rate)

        # RESULTS
        self.yearly_agb_emissions = []
        self.total_agb_emissions = 0

        self.yearly_bgb_emissions = []
        self.total_bgb_emissions = 0

        self.yearly_litter_emissions = []
        self.total_litter_emissions = 0

        self.yearly_deadwood_emissions = []
        self.total_deadwood_emissions = 0

        self.yearly_disturbance_emissions = []  # NOTE: THIS IS A LIST OF LISTS
        self.total_disturbance_emissions = []

        self.yearly_rotation_emissions = []
        self.total_rotation_emissions = 0

        self.yearly_fire_rotation_emissions = []
        self.total_fire_rotation_emissions = 0

        self.yearly_fire_disturbance_emissions = []
        self.total_fire_disturbance_emissions = 0

        self.yearly_soc_emissions = []
        self.total_soc_emissions = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.years_impl, self.years_cap)

        pass
    
    def calculate_emissions(
        self,
    ):
        def calculate_agb_bgb_rotation_disturbance_emissions():

            def breakdown_agb_bgb_emissions(rotation_times_hectares_agb, rotation_times_hectares_bgb, percentage_energy,
                                            forest_cf, forest_gef_ch4, forest_gef_n2o, forest_gef_co2, mangrove_factor):
                
                # TODO: forest_gef_co2 is not used as of now

                agb_action_component = [x * - 44 / 12 * (1 - percentage_energy) for x in rotation_times_hectares_agb]
                bgb_action_component = [x * - 44 / 12 * (1 - percentage_energy) for x in rotation_times_hectares_bgb]
                nitrous_fire_component_agb = [x / mangrove_factor * - 44 / 12 * percentage_energy * forest_cf * forest_gef_n2o * self.ef_nitrous / 1000 for x in rotation_times_hectares_agb]
                methane_fire_component_agb = [x / mangrove_factor * - 44 / 12 * percentage_energy * forest_cf * forest_gef_ch4 * self.ef_methane / 1000 for x in rotation_times_hectares_agb]
                nitrous_fire_component_bgb = [x / mangrove_factor * - 44 / 12 * percentage_energy * forest_cf * forest_gef_n2o * self.ef_nitrous / 1000 for x in rotation_times_hectares_bgb]
                methane_fire_component_bgb = [x / mangrove_factor * - 44 / 12 * percentage_energy * forest_cf * forest_gef_ch4 * self.ef_methane / 1000 for x in rotation_times_hectares_bgb]

                return agb_action_component, bgb_action_component, nitrous_fire_component_agb, methane_fire_component_agb, nitrous_fire_component_bgb, methane_fire_component_bgb
            
            try:
                
                # calculate agb matrix
                agb_matrix, delta_agb_matrix = create_agb_matrix(self.years_impl, self.years_cap, self.agb_yearly_growth_under_20, self.agb_yearly_growth_over_20, self.agb_start)
                if self.bgb_yearly_growth_over_20_tier_2 and self.bgb_yearly_growth_under_20_tier_2:
                    bgb_matrix, delta_bgb_matrix = create_agb_matrix(self.years_impl, self.years_cap, self.bgb_yearly_growth_under_20_tier_2, self.bgb_yearly_growth_over_20_tier_2, self.bgb_start)
                else:
                    bgb_matrix, delta_bgb_matrix = create_bgb_matrix_from_agb(agb_matrix, delta_agb_matrix, self.bgb_ratio_under_threshold, self.bgb_ratio_over_threshold, self.bgb_ratio_threshold, self.bgb_start, self.years_impl)

                # NOTE: THIS MEANS WE HAVE ROTATION
                if self.rotation_recurrence:
                    # CALCULATION FOR ROTATION
                    result_rotation_agb, rotation_matrix_agb, delta_agb_matrix = calculate_rotation_effect(agb_matrix, delta_agb_matrix, self.max_agb_value, self.rotation_recurrence, self.rotation_start_year)
                    result_rotation_bgb, rotation_matrix_bgb, delta_bgb_matrix = calculate_rotation_effect(bgb_matrix, delta_bgb_matrix, self.max_bgb_value, self.rotation_recurrence, self.rotation_start_year)

                    rotation_times_hectares_agb = multiply_matrix_by_matrix(rotation_matrix_agb, self.hectares_for_rot_log_dis)
                    rotation_times_hectares_bgb = multiply_matrix_by_matrix(rotation_matrix_bgb, self.hectares_for_rot_log_dis)

                    ao = sum(rotation_times_hectares_agb)

                    (
                        agb_rotation_component, 
                        bgb_rotation_component,
                        nitrous_fire_component_agb, 
                        methane_fire_component_agb,
                        nitrous_fire_component_bgb, 
                        methane_fire_component_bgb
                     ) = breakdown_agb_bgb_emissions(rotation_times_hectares_agb, rotation_times_hectares_bgb, self.rotation_percentage_energy, 
                                                     self.forest_cf, self.forest_gef_ch4, self.forest_gef_n2o, self.forest_gef_co2, self.mangrove_factor)

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in agb_rotation_component], activity=ActivityTypes.ROTATION_AGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in bgb_rotation_component], activity=ActivityTypes.ROTATION_BGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_agb], activity=ActivityTypes.ROTATION_AGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_agb], activity=ActivityTypes.ROTATION_AGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_bgb], activity=ActivityTypes.ROTATION_BGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_bgb], activity=ActivityTypes.ROTATION_BGB))

                # NOTE: THIS MEANS WE HAVE DISTURBANCE or LOGGING, WHICH ARE TREATED EQUALLY IN CALCULATION
                elif self.disturbance_recurrence or self.logging_recurrence:
                    # CALCULATION FOR DISTURBANCE
                    for recurrence, percentage, percentage_fire, start_year in zip(self.disturbance_recurrence, self.disturbance_percentage, [0 for i in self.disturbance_percentage], self.disturbance_year_of_start):
                        # NOTE: As logging and disturbance are the same, we can use the same function

                        result_disturbance_agb, logging_matrix_agb, delta_agb_matrix = calculate_logging_effect(agb_matrix, delta_agb_matrix, self.max_agb_value, recurrence, start_year, percentage)
                        result_disturbance_bgb, logging_matrix_bgb, delta_bgb_matrix = calculate_logging_effect(bgb_matrix, delta_bgb_matrix, self.max_bgb_value, recurrence, start_year, percentage)

                        disturbance_times_hectares_agb = multiply_matrix_by_matrix(logging_matrix_agb, self.hectares_for_rot_log_dis)
                        disturbance_times_hectares_bgb = multiply_matrix_by_matrix(logging_matrix_bgb, self.hectares_for_rot_log_dis)

                        (
                            agb_logging_component, 
                            bgb_logging_component,
                            nitrous_fire_component_agb, 
                            methane_fire_component_agb,
                            nitrous_fire_component_bgb, 
                            methane_fire_component_bgb
                        ) = breakdown_agb_bgb_emissions(disturbance_times_hectares_agb, disturbance_times_hectares_bgb, percentage_fire,
                                                        self.forest_cf, self.forest_gef_ch4, self.forest_gef_n2o, self.forest_gef_co2, self.mangrove_factor)

                        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in agb_logging_component], activity=ActivityTypes.DISTURBANCE_AGB))
                        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in bgb_logging_component], activity=ActivityTypes.DISTURBANCE_BGB))

                        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_agb], activity=ActivityTypes.DISTURBANCE_AGB))
                        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_agb], activity=ActivityTypes.DISTURBANCE_AGB))

                        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_bgb], activity=ActivityTypes.DISTURBANCE_BGB))
                        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_bgb], activity=ActivityTypes.DISTURBANCE_BGB))

                    # CALCULATION FOR LOGGING
                    result_logging_agb, logging_matrix_agb, delta_agb_matrix = calculate_logging_effect(agb_matrix, delta_agb_matrix, self.max_agb_value, self.logging_recurrence, self.logging_year_of_start, self.logging_percentage)
                    result_logging_bgb, logging_matrix_bgb, delta_bgb_matrix = calculate_logging_effect(bgb_matrix, delta_bgb_matrix, self.max_bgb_value, self.logging_recurrence, self.logging_year_of_start, self.logging_percentage)
                    
                    logging_times_hectares_agb = multiply_matrix_by_matrix(logging_matrix_agb, self.hectares_for_rot_log_dis)
                    logging_times_hectares_bgb = multiply_matrix_by_matrix(logging_matrix_bgb, self.hectares_for_rot_log_dis)


                    (
                        agb_logging_component, 
                        bgb_logging_component,
                        nitrous_fire_component_agb, 
                        methane_fire_component_agb,
                        nitrous_fire_component_bgb, 
                        methane_fire_component_bgb
                    ) = breakdown_agb_bgb_emissions(logging_times_hectares_agb, logging_times_hectares_bgb, self.logging_percentage_energy,
                                                    self.forest_cf, self.forest_gef_ch4, self.forest_gef_n2o, self.forest_gef_co2, self.mangrove_factor)

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in agb_logging_component], activity=ActivityTypes.LOGGING_AGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in bgb_logging_component], activity=ActivityTypes.LOGGING_BGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_agb], activity=ActivityTypes.LOGGING_AGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_agb], activity=ActivityTypes.LOGGING_AGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component_bgb], activity=ActivityTypes.LOGGING_BGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component_bgb], activity=ActivityTypes.LOGGING_BGB))

                # NOTE: THIS MEANS WE HAVE NO ROTATION, NO DISTURBANCE, NO LOGGING. HENCE WE CAN HAVE DEGRADATION
                elif self.degradation_percentage:
                    
                    result_degradation_agb, degradation_matrix_agb, delta_agb_matrix = calculate_logging_effect(agb_matrix, delta_agb_matrix, self.max_agb_value, 1, 0, self.degradation_percentage)
                    result_degradation_bgb, degradation_matrix_bgb, delta_bgb_matrix = calculate_logging_effect(bgb_matrix, delta_bgb_matrix, self.max_bgb_value, 1, 0, self.degradation_percentage)

                    degradation_times_hectares_agb = multiply_matrix_by_matrix(degradation_matrix_agb, self.hectares_for_rot_log_dis)
                    degradation_times_hectares_bgb = multiply_matrix_by_matrix(degradation_matrix_bgb, self.hectares_for_rot_log_dis)

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in degradation_times_hectares_agb], activity=ActivityTypes.DEGRADATION_AGB))
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in degradation_times_hectares_bgb], activity=ActivityTypes.DEGRADATION_BGB))

                    plot_annotated_matrix(degradation_matrix_agb, "degradation agb matrix")

                
                # check if agb_matrix has negative values
                if np.any(np.sum(agb_matrix < 0), axis=0):
                    raise ValueError(f"Negative values in agb_matrix, check the parameters for logging and disturbance % over 100")

                agb_times_hectares = multiply_matrix_by_matrix(delta_agb_matrix, self.hectares_matrix)
                yearly_agb_emissions = [x * -44 / 12 for x in agb_times_hectares]
                self.yearly_agb_emissions = yearly_agb_emissions
                self.total_agb_emissions = sum(yearly_agb_emissions)

                bgb_times_hectares = multiply_matrix_by_matrix(delta_bgb_matrix, self.hectares_matrix)
                yearly_bgb_emissions = [x * -44 / 12 for x in bgb_times_hectares]
                self.yearly_bgb_emissions = yearly_bgb_emissions
                self.total_bgb_emissions = sum(yearly_bgb_emissions)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.yearly_agb_emissions], activity=ActivityTypes.AGB_GROWTH))

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.yearly_bgb_emissions], activity=ActivityTypes.BGB_GROWTH))

            except Exception as e:
                traceback.print_exc()
                return

        def calculate_litter():
            try:

                litter_matrix, delta_litter_matrix = create_litter_deadwood_matrix(self.years_impl, self.years_cap, self.litter_20_years / 20, self.litter_20_years / 20, self.litter_start, self.litter_max)

                if self.degradation_percentage:
                    # NOTE: This means we have degradation, which has an impact on litter and deadwood as well
                    result_litter, degradation_litter_matrix, delta_litter_matrix = calculate_logging_effect(litter_matrix, delta_litter_matrix, self.litter_max, 1, 0, self.degradation_percentage)

                    degradation_times_hectares_litter = multiply_matrix_by_matrix(degradation_litter_matrix, self.hectares_for_rot_log_dis)
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in degradation_times_hectares_litter], activity=ActivityTypes.DEGRADATION_LITTER))

                    plot_annotated_matrix(degradation_litter_matrix, "degradation litter matrix")

                
                self.yearly_litter_emissions = [x * -44 / 12 for x in multiply_matrix_by_matrix(delta_litter_matrix, self.hectares_matrix)]
                self.total_litter_emissions = sum(self.yearly_litter_emissions)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.yearly_litter_emissions], activity=ActivityTypes.LITTER))

            except Exception as e:
                traceback.print_exc()
                return

        def calculate_deadwood():
            try:
                deadwood_matrix, delta_deadwood_matrix = create_litter_deadwood_matrix(self.years_impl, self.years_cap, self.deadwood_20_years / 20, self.deadwood_20_years / 20, self.deadwood_start, self.deadwood_max)

                if self.degradation_percentage:
                    # NOTE: This means we have degradation, which has an impact on litter and deadwood as well
                    result_deadwood, deadwood_matrix, delta_deadwood_matrix = calculate_logging_effect(deadwood_matrix, delta_deadwood_matrix, self.deadwood_max, 1, 0, self.degradation_percentage)

                    degradation_times_hectares_deadwood = multiply_matrix_by_matrix(deadwood_matrix, self.hectares_for_rot_log_dis)
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in degradation_times_hectares_deadwood], activity=ActivityTypes.DEGRADATION_DEADWOOD))

                self.yearly_deadwood_emissions = [x * -44 / 12 for x in multiply_matrix_by_matrix(delta_deadwood_matrix, self.hectares_matrix)]
                self.total_deadwood_emissions = sum(self.yearly_deadwood_emissions)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.yearly_deadwood_emissions], activity=ActivityTypes.DEADWOOD))

            except Exception as e:
                traceback.print_exc()
                return

        def calculate_emissions_soil():
            try:
                emissions_soil_yearly, emissions_soil_total = soil_emissions_2(self.soc_start, self.soc_end, self.hectares_total, self.hectares_start, self.hectares_end, self.hectares_before_20)

                soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_soil_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

            except Exception as e:
                traceback.print_exc()

        def calculate_emissions_som():
            try:
                emissions_som_yearly, emissions_som_total = som_emissions(self.soc_end, self.soc_start, self.ef_nitrous_som, self.nitrous_constant, self.hectares_before_20)

                som_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in emissions_som_yearly], ActivityTypes.SOM, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(som_emission_set)
            except Exception as e:
                traceback.print_exc()

        def create_agb_matrix(years_impl, years_cap, delta_agb_yearly_below_20, delta_agb_yearly_after_20, agb_start):

            try:

                if rotation_recurrence and rotation_recurrence < 20:
                    # NOTE: This is due to the fact that it does not have time to grow past 20 years. EVER. As it's relative to the patch of land. Biomass under any 
                    # hectar never grows to be 20 years old. Always killed before hand
                    delta_agb_yearly_after_20 = delta_agb_yearly_below_20


                years_total = years_impl + years_cap
                delta_agb_matrix = np.full((years_impl, years_total), 0.0)
                agb_matrix = np.full((years_impl, years_total), 0.0)

                # NOTE: IN THE CASE OF DEFORESTATION THERE IS NO GROWTH
                # if hectares_start == hectares_end or hectares_start < hectares_end:
                for i in range(years_impl):
                    # CREATING DELTA AGB MATRIX
                    end_index_below_20 = min(i + 20, years_total)
                    delta_agb_matrix[i, i:end_index_below_20] = delta_agb_yearly_below_20
                    if end_index_below_20 < years_total:
                        delta_agb_matrix[i, end_index_below_20:] = delta_agb_yearly_after_20

                for i in range(years_impl):
                    for j in range(i, years_total):
                        agb_matrix[i, j] = agb_start + delta_agb_matrix[i][j] + np.sum(delta_agb_matrix[i, i:j])

                return agb_matrix, delta_agb_matrix
            except Exception as e:
                traceback.print_exc()
                return

        def create_litter_deadwood_matrix(years_impl, years_cap, delta_agb_yearly_below_20, delta_agb_yearly_after_20, agb_start, max_agb_value):

            try:
                years_total = years_impl + years_cap
                delta_agb_matrix = np.full((years_impl, years_total), 0.0)
                agb_matrix = np.full((years_impl, years_total), 0.0)

                # NOTE: IN THE CASE OF DEFORESTATION THERE IS NO GROWTH
                # if hectares_start == hectares_end or hectares_start < hectares_end:
                for i in range(years_impl):
                    # CREATING DELTA AGB MATRIX
                    end_index_below_20 = min(i + 20, years_total)
                    delta_agb_matrix[i, i:end_index_below_20] = delta_agb_yearly_below_20
                    if end_index_below_20 < years_total:
                        delta_agb_matrix[i, end_index_below_20:] = delta_agb_yearly_after_20

                for i in range(years_impl):
                    for j in range(i, years_total):
                        agb_matrix[i, j] = agb_start + delta_agb_matrix[i][j] + np.sum(delta_agb_matrix[i, i:j])

                agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)

                return agb_matrix, delta_agb_matrix
            
            except Exception as e:
                traceback.print_exc()
                return

        def create_bgb_matrix_from_agb(agb_matrix, delta_agb_matrix, bgb_ratio_under_threshold, bgb_ratio_over_threshold, threshold, bgb_start, time_impl):

            try:
                delta_bgb_matrix = delta_agb_matrix * bgb_ratio_under_threshold
                bgb_matrix = np.full((agb_matrix.shape[0], agb_matrix.shape[1]), 0.0)

                for i in range(time_impl):
                    for j in range(i, agb_matrix.shape[1]):
                        value_to_assign = bgb_start + delta_bgb_matrix[i][j] + np.sum(delta_bgb_matrix[i, i:j])
                        if value_to_assign > threshold:
                            delta_bgb_matrix[i][j] = delta_bgb_matrix[i][j] * bgb_ratio_over_threshold
                            value_to_assign = bgb_start + delta_bgb_matrix[i][j] + np.sum(delta_bgb_matrix[i, i:j])
                        bgb_matrix[i][j] = value_to_assign

                return bgb_matrix, delta_bgb_matrix
            
            except Exception as e:
                traceback.print_exc()
                return

        def check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value):

            try:
                for i in range(agb_matrix.shape[0]):
                    for j in range(i, agb_matrix.shape[1]):
                        if agb_matrix[i][j] > max_agb_value:
                            # Update agb_matrix
                            agb_matrix[i][j:] = max_agb_value

                            # Update delta_agb_matrix
                            if j == 0 or i == j:
                                delta_agb_matrix[i][j] = 0
                            else:
                                delta_agb_matrix[i][j] = max_agb_value - agb_matrix[i][j - 1]

                            delta_agb_matrix[i][j + 1 :] = 0
                            break

                return agb_matrix, delta_agb_matrix
            
            except Exception as e:
                traceback.print_exc()
                return

        def update_agb_matrix_rotation(agb_matrix, delta_agb_matrix, original_delta_agb_matrix, max_agb_value, rotation_impact, row, column, row_at_maximum):

            try:
                # sum agb_matrix and rotation_impact only for the row and from the column of interest to the end
                agb_matrix[row, column:] = agb_matrix[row, column:] + rotation_impact[row, column:]
                # iterate over all rows in agb_matrix, if there is a value in the row smaller than the max_agb_value, change the delta_agb_matrix from position i to i:end to the original_delta_agb_matrix
                for j in range(column, agb_matrix.shape[1]):
                    if agb_matrix[row][j] < max_agb_value:
                        delta_agb_matrix[row][j:] = original_delta_agb_matrix[row][j:]
                        # This means that there is a change in the agb_matrix so that we have to keep growing in delta_agb_matrix. Add for each value of
                        for m in range(j, agb_matrix.shape[1]):
                            if m == agb_matrix.shape[1]:
                                agb_matrix[row][m] = agb_matrix[row][m] + np.sum(delta_agb_matrix[row][j:m])
                            else:
                                agb_matrix[row][m] = agb_matrix[row][m] + np.sum(delta_agb_matrix[row][j : m + 1])
                        break

                return agb_matrix, delta_agb_matrix
            
            except Exception as e:
                traceback.print_exc()
                return

        def update_agb_matrix_logging(agb_matrix, delta_agb_matrix, original_delta_agb_matrix, max_agb_value, logging_impact, column, logging_recurrence):

            try:
                # take the value for each row on the column, that is much we are cutting down, subtract it from the agb_matrix across the row
                for row in range(0, min(agb_matrix.shape[0], column + 1)):
                    agb_matrix[row, column:] = agb_matrix[row, column:] + logging_impact[row, column]
                    # now set all values after the column to agb_matrix[row, column]
                    agb_matrix[row, column:] = agb_matrix[row, column]

                    for j in range(column, agb_matrix.shape[1]):
                        if agb_matrix[row][j] < max_agb_value:
                            delta_agb_matrix[row][j:] = original_delta_agb_matrix[row][j:]
                            # This means that there is a change in the agb_matrix so that we have to keep growing in delta_agb_matrix. Add for each value of                            
                            for m in range(j, min (agb_matrix.shape[1], j + logging_recurrence + 1)):
                                if m == agb_matrix.shape[1]:
                                    agb_matrix[row][m] = agb_matrix[row][m] + np.sum(delta_agb_matrix[row][j:m])
                                else:
                                    agb_matrix[row][m] = agb_matrix[row][m] + np.sum(delta_agb_matrix[row][j : m + 1])
                            break

                check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)

                return agb_matrix, delta_agb_matrix
            
            except Exception as e:
                traceback.print_exc()
                return

        def calculate_rotation_effect(original_agb_matrix, original_delta_agb_matrix, max_agb_value, recurrence, start_year, percentage=1):

            try:
                maximum_column = original_agb_matrix.shape[1]
                maximum_row = original_agb_matrix.shape[0]

                # let's approach this row wise and keep track of the changes
                results = {}

                rotation_impact = np.zeros(original_agb_matrix.shape)
                rotation_matrix = np.zeros(original_agb_matrix.shape)
                agb_matrix = copy.deepcopy(original_agb_matrix)
                delta_agb_matrix = copy.deepcopy(original_delta_agb_matrix)

                # THIS MEANS WE START WITH A FULL FOREST, WHERE VALUE = MAX_AGB_VALUE
                for row_index in range(maximum_row):
                    if agb_matrix[row_index][row_index] >= max_agb_value:
                        # subtract this to all value in the row, right of the diagonal
                        agb_matrix[row_index][row_index:] -= max_agb_value
                        rotation_matrix[row_index][row_index] = -max_agb_value
                        results[row_index] = -max_agb_value * percentage
                        rotation_impact[row_index, row_index] = -max_agb_value

                agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)

                row_start = 0
                # TODO: if an area is rotated, then the clock for agb_below and after_20 is reset to 0
                for row_index in range(maximum_row):
                    # sum up the values from column 0 to column recurrence excluded, then multiply by percentage
                    i = 1
                    while row_start + start_year + recurrence * i < maximum_column:
                        row = agb_matrix[row_index]
                        agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)

                        row_at_maximum = max(agb_matrix[row_index]) == max_agb_value
                        # TODO: make the function a bit NICERRRRR
                        if results.get(row_start + recurrence * i) is None:
                            results[row_start + recurrence * i] = -row[row_start + recurrence * i - 1] * percentage
                            rotation_impact[row_index, row_start + recurrence * i :] = -agb_matrix[row_index, row_start + recurrence * i :]
                            rotation_matrix[row_index, row_start + recurrence * i] = -agb_matrix[row_index, row_start + recurrence * i - 1]
                        else:
                            results[row_start + recurrence * i] += -row[row_start + recurrence * i - 1] * percentage
                            rotation_impact[row_index, row_start + recurrence * i :] = -agb_matrix[row_index, row_start + recurrence * i :]
                            rotation_matrix[row_index, row_start + recurrence * i] = -agb_matrix[row_index, row_start + recurrence * i - 1]

                        agb_matrix, delta_agb_matrix = update_agb_matrix_rotation(agb_matrix, delta_agb_matrix, original_delta_agb_matrix, max_agb_value, rotation_impact, row_index, row_start + recurrence * i, row_at_maximum)
                        agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)

                        i += 1
                    row_start += 1

                # order results by key
                results = dict(sorted(results.items()))

                # add to each year
                return results, rotation_matrix, delta_agb_matrix
            
            except Exception as e:
                traceback.print_exc()
                return

        def calculate_logging_effect(original_agb_matrix, original_delta_agb_matrix, max_agb_value, recurrence, start_year, percentage):
            
            try:
                agb_matrix = copy.deepcopy(original_agb_matrix)
                delta_agb_matrix = copy.deepcopy(original_delta_agb_matrix)
                # Determine the maximum number of intervals given the shape of the matrix
                max_intervals = (agb_matrix.shape[1] - start_year) // recurrence
                # Dictionary to hold the results
                result = {}
                # Create a matrix to accumulate logging effects
                logging_impact = np.full(agb_matrix.shape, 0.0)

                for i in range(0, max_intervals):
                    # Check if the agb_matrix is still below the maximum value
                    agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)

                    # i represents the column of our matrix. When there is logging we are cutting down a percentage of the forest present in year i
                    # We are cutting down a percentage of the forest present in year i
                    # NOTE: applied change here to include year of start (no idea if correct)

                    if i <= agb_matrix.shape[1]:
                        logging_impact[:, i * recurrence + start_year] = -agb_matrix[:, i * recurrence + start_year] * percentage
                    else:
                        ao =  i * recurrence - 1 + start_year
                        logging_impact[:, i * recurrence + start_year] = -agb_matrix[:, i * recurrence - 1 + start_year] * percentage


                    # Update the agb_matrix
                    agb_matrix, delta_agb_matrix = update_agb_matrix_logging(agb_matrix, delta_agb_matrix, original_delta_agb_matrix, max_agb_value, logging_impact, i * recurrence, recurrence)
                    agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)
                    
                
                
                return result, logging_impact, delta_agb_matrix
            
            except Exception as e:
                traceback.print_exc()
                return

        def multiply_matrix_by_matrix(matrix1, matrix2):
            
            try:
                if matrix1.shape != matrix2.shape:
                    raise ValueError("Both matrices must have the same dimensions!")

                # Element-wise multiplication
                multiplied_matrix = np.multiply(matrix1, matrix2)

                # Sum each column
                result = np.sum(multiplied_matrix, axis=0)

                return result
            
            except Exception as e:
                traceback.print_exc()
                return

        def plot_annotated_matrix(matrix, title):
            """
            Plot a given matrix (list of lists) with each value annotated in the corresponding cell,
            rounding the numbers to two decimal points.

            Parameters:
            - matrix: List of lists representing the matrix to plot.
            """
            # Convert the matrix to a NumPy array for ease of use
            np_matrix = np.array(matrix)

            # Determine the size of the matrix
            nrows, ncols = np_matrix.shape

            # Create the plot
            fig, ax = plt.subplots()
            # Using matshow to display the matrix
            cax = ax.matshow(np_matrix, cmap="Dark2")

            # Add a color bar
            fig.colorbar(cax)

            # Annotate each cell with the corresponding value, rounded to two decimal places
            for i in range(nrows):
                for j in range(ncols):
                    # Format the number with two decimal places for annotation
                    value = f"{np_matrix[i, j]:.2f}"
                    ax.text(j, i, value, va="center", ha="center", color="white")

            # Optionally, adjust x and y ticks if needed
            ax.set_xticks(np.arange(ncols))
            ax.set_yticks(np.arange(nrows))
            ax.set_xticklabels(range(ncols))
            ax.set_yticklabels(range(nrows))

            # Add labels and title if needed
            plt.xlabel("Column Index")
            plt.ylabel("Row Index")
            plt.title("Annotated Matrix of " + title)



            # Show the plot
            plt.show()

        def plot_matrix(matrix):

            # Number of rows and columns in the matrix
            num_rows, num_cols = matrix.shape

            # X-axis labels (years)
            years = np.arange(num_cols)

            # Initialize an array to keep track of the cumulative height of bars
            cumulative_height = np.zeros(num_cols)

            # Loop through each row to plot bars
            for row in range(num_rows):
                # Skip row if all values are zero
                if np.all(matrix[row] == 0):
                    continue

                plt.bar(years, matrix[row], bottom=cumulative_height, label=f"Hectares from year {row}")

                # Add text labels inside bars
                for i, (value, cum_value) in enumerate(zip(matrix[row], cumulative_height)):
                    if value != 0:  # Skip label if value is zero
                        plt.text(i, cum_value + value / 2, str(round(value, 2)), ha="center", va="center")

                # Update cumulative height
                cumulative_height += matrix[row]

            # Add legend
            plt.legend()

            # Add axis labels
            plt.xlabel("Years")
            plt.ylabel("Value")

            # Add x-axis tick labels
            plt.xticks(np.arange(num_cols), [str(i) for i in range(num_cols)])

            # Show the plot
            plt.show()


        calculate_agb_bgb_rotation_disturbance_emissions()
        calculate_litter()
        calculate_deadwood()
        calculate_emissions_soil()
        calculate_emissions_som()

# years_cap = 15
# years_impl = 5
# rate = 'D'
# hectares_start = 0
# hectares_end = 100
# rotation_recurrence = None
# rotation_start_year = 0
# rotation_percentage_energy = 0.3
# bgb_ratio_threshold = 125
# bgb_ratio_under_threshold = 0.3
# bgb_ratio_over_threshold = 0.27
# bgb_yearly_growth_under_20_tier_2 = None
# bgb_yearly_growth_over_20_tier_2 = None
# agb_start_default = 67
# agb_start_tier_2 = None
# agb_yearly_growth_under_20_default = 3.5
# agb_yearly_growth_under_20_tier_2 = None
# agb_yearly_growth_over_20_default = 2.5
# agb_yearly_growth_over_20_tier_2 = None
# max_agb_value = 67
# max_bgb_value = max_agb_value * bgb_ratio_under_threshold
# disturbance_recurrence = []
# disturbance_percentage = []
# disturbance_year_of_start = []
# logging_recurrence = None
# logging_percentage = 0.7
# logging_percentage_energy = 0
# logging_year_of_start = 0
# litter_20_years_default = 43.9
# litter_start = 43.9
# litter_max = 43.9
# litter_20_years_tier_2 = None
# deadwood_20_years_default = 43.4
# deadwood_start = 43.9
# deadwood_max = 43.4
# deadwood_20_years_tier_2 = None
# socref_default = 27
# soc_tier_2 = None
# f_lu_tier_2 = None
# f_i_tier_2 = None
# f_mg_tier_2 = None
# f_lu_ref = 1
# f_i_ref = 1
# f_mg_ref = 1
# ef_methane = 28
# ef_nitrous = 265
# forest_cf = 0.32
# forest_gef_ch4 = 6.8
# forest_gef_n2o = 0.2
# forest_gef_co2 = None
# mangrove_factor = 0.47
# degradation_percentage = 0.2

# # create instance of the class

# forest_management = ForestManagement(
#     years_cap,
#     years_impl,
#     rate,
#     hectares_start,
#     hectares_end,
#     rotation_recurrence,
#     rotation_start_year,
#     rotation_percentage_energy,
#     bgb_ratio_threshold,
#     bgb_ratio_under_threshold,
#     bgb_ratio_over_threshold,
#     bgb_yearly_growth_under_20_tier_2,
#     bgb_yearly_growth_over_20_tier_2,
#     agb_start_default,
#     agb_start_tier_2,
#     agb_yearly_growth_under_20_default,
#     agb_yearly_growth_under_20_tier_2,
#     agb_yearly_growth_over_20_default,
#     agb_yearly_growth_over_20_tier_2,
#     max_agb_value,
#     max_bgb_value,
#     disturbance_recurrence,
#     disturbance_percentage,
#     disturbance_year_of_start,
#     logging_recurrence,
#     logging_percentage,
#     logging_percentage_energy,
#     logging_year_of_start,
#     litter_20_years_default,
#     litter_start,
#     litter_max,
#     litter_20_years_tier_2,
#     deadwood_20_years_default,
#     deadwood_start,
#     deadwood_max,
#     deadwood_20_years_tier_2,
#     socref_default,
#     soc_tier_2,
#     f_lu_tier_2,
#     f_i_tier_2,
#     f_mg_tier_2,
#     f_lu_ref,
#     f_i_ref,
#     f_mg_ref,
#     ef_methane,
#     ef_nitrous,
#     forest_cf,
#     forest_gef_ch4,
#     forest_gef_n2o,
#     forest_gef_co2,
#     mangrove_factor,
#     degradation_percentage
# )

# forest_management.calculate_emissions()

# forest_management.result.plot_emissions_and_aggregate_by_activity()




