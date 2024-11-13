# download a package to calculate logarithm in base e
import math
import re
import traceback
from dataclasses import dataclass
import copy
import numpy as np


def average_yearly_value(yearly_breakdown: list):
    average_yearly_value = [(yearly_breakdown[i] + yearly_breakdown[i + 1]) / 2 for i in range(len(yearly_breakdown) - 1)]

    return average_yearly_value


def yearly_time_dependent_parameter_breakdown(start_value, end_value, years_implementation, years_capitalization, function, interim_values=True):

    # IMPORTANT NOTE:
    # UTILIZING THIS FUNCTION WE ARE RETURNING THE MIDDLE VALUE BETWEEN THE CALCULATED VALUES AT THE BEGINNING OF EACH YEAR.
    # THIS IS DONE SO THAT THE YEARLY BREAKDOWN IS A LIST OF THE SAME LENGTH AS THE NUMBER OF YEARS IMPLEMENTATION + CAPITALIZATION
    # ALSO, THIS WAY THE RESULTS ARE THE SAME AS THE EXCEL RESULTS

    # Exponential case
    if function == "exponential":
        # NOTE: the function is y = b + a * e^(kx) where k = -0.519349 this was calculated as the integral between 0 and 1 of a*e^(bx) = 0.78
        # where 0.78 was selected from the exact team, as it shows natural decay
        k = -0.519349
        a = end_value / (math.exp(k * years_implementation) - 1)
        b = start_value - a

        if start_value < end_value:
            yearly_breakdown = [b + a * math.exp(k * i) for i in range(years_implementation + 1)]
        else:
            yearly_breakdown = [b + a * math.exp(k * i) for i in range(years_implementation + 1)]
            yearly_breakdown.reverse()

        yearly_breakdown.extend([yearly_breakdown[-1] for i in range(years_capitalization)])

        # return the yearly breakdown
        if interim_values:
            return average_yearly_value(yearly_breakdown)
        else:
            yearly_breakdown

        return yearly_breakdown

    elif function == "linear":
        # calculate the parameters for the function a + bx
        a = min(start_value, end_value)
        b = (abs(start_value - end_value)) / years_implementation

        # Calculate the yearly breakdown
        if start_value < end_value:
            yearly_breakdown = [a + b * i for i in range(years_implementation + 1)]
        else:
            yearly_breakdown = [a + b * i for i in range(years_implementation + 1)]
            yearly_breakdown.reverse()

        yearly_breakdown.extend([yearly_breakdown[-1] for i in range(years_capitalization)])

        # return the yearly breakdown
        if interim_values:
            return average_yearly_value(yearly_breakdown)
        else:
            return yearly_breakdown

    elif function == "immediate":
        if interim_values:
            return average_yearly_value([end_value for i in range(years_implementation + years_capitalization + 1)])
        else:
            return [end_value for i in range(years_implementation + years_capitalization + 1)]

    else:
        raise Exception(f'Function "{function}" not recognized')


def yearly_time_dependent_parameter_breakdown_new_test(start_value, end_value, years_implementation, years_capitalization, function, interim_values=True):
    # UTILIZING THIS FUNCTION WE ARE RETURNING THE MIDDLE VALUE BETWEEN THE CALCULATED VALUES AT THE BEGINNING OF EACH YEAR.
    # THIS IS DONE SO THAT THE YEARLY BREAKDOWN IS A LIST OF THE SAME LENGTH AS THE NUMBER OF YEARS IMPLEMENTATION + CAPITALIZATION
    # ALSO, THIS WAY THE RESULTS ARE THE SAME AS THE EXCEL RESULTS

    # EXPONENTIAL CASE
    if function == "exponential":
        # calculate the parameters for the function a*b^x
        a = min(start_value, end_value)
        b = (max(start_value, end_value) / min(start_value, end_value)) ** (1 / years_implementation)

        # Calculate the yearly breakdown
        if start_value < end_value:
            yearly_breakdown = [a * b**i for i in range(years_implementation + 1)]
        else:
            yearly_breakdown = [a * b**i for i in range(years_implementation + 1)]
            yearly_breakdown.reverse()

        yearly_breakdown.extend([yearly_breakdown[-1] for i in range(years_capitalization)])

        # return the yearly breakdown
        if interim_values:
            return average_yearly_value(yearly_breakdown)
        else:
            return yearly_breakdown

    elif function == "D":
        # calculate the parameters for the function a + bx
        a = min(start_value, end_value)
        b = (abs(start_value - end_value)) / years_implementation

        # Calculate the yearly breakdown
        if start_value < end_value:
            yearly_breakdown = [a + b * i for i in range(1, years_implementation + 1)]
        else:
            yearly_breakdown = [a + b * i for i in range(1, years_implementation + 1)]
            yearly_breakdown.reverse()

        yearly_breakdown.extend([yearly_breakdown[-1] for i in range(years_capitalization)])

        # return the yearly breakdown
        if interim_values:
            return average_yearly_value(yearly_breakdown)
        else:
            return yearly_breakdown

    elif function == "immediate":
        if interim_values:
            return average_yearly_value([end_value for i in range(years_implementation + years_capitalization + 1)])
        else:
            return [end_value for i in range(years_implementation + years_capitalization + 1)]

    else:
        raise Exception(f'Function "{function}" not recognized')


def yearly_constant_emissions_breakdown(total_emissions, years_implementation, years_capitalization, rate_type):

    if rate_type == "linear":
        yearly_breakdown = [total_emissions / years_implementation for _ in range(years_implementation)]
        yearly_breakdown.extend([0 for _ in range(years_capitalization)])

    elif rate_type == "exponential":
        # NOTE: this is changed to -k (as k=-0.519349) as I believe we should have a larger part towards to end than the beginning
        k = -0.519349  # growth rate determined from the previous calculation
        # Calculate the total area under the exponential curve from 0 to years_implementation
        total_area = (math.exp(k * years_implementation) - 1) / k

        yearly_breakdown = []
        for year in range(1, years_implementation + 1):
            # Calculate the area for each year interval
            area_start = (math.exp(k * (year - 1)) - 1) / k
            area_end = (math.exp(k * year) - 1) / k
            yearly_emissions = total_emissions * (area_end - area_start) / total_area
            yearly_breakdown.append(yearly_emissions)

        yearly_breakdown.extend([0 for _ in range(years_capitalization)])

    elif rate_type == "immediate":
        yearly_breakdown = [total_emissions] + [0 for _ in range(years_implementation - 1)]
        yearly_breakdown.extend([0 for _ in range(years_capitalization)])

    else:
        raise Exception(f'Function "{rate_type}" not recognized')

    return yearly_breakdown


def yearly_time_dependent_20_year_breakdown(start_value, end_value, years_implementation, years_capitalization, function, number_of_years=20):
    # NOTE: this function is used to calculate the average yearly value of the breakdown for soil, but not it is also used for other cases, hence why number_of_years is added instead of only 20
    breakdown = yearly_time_dependent_parameter_breakdown(start_value, end_value, years_implementation, years_capitalization, function, interim_values=False)

    after_20 = [0 for i in range(number_of_years + 1)]
    after_20.extend(breakdown)

    before_20 = [i - j for i, j in zip(breakdown, after_20[0 : len(breakdown)])]

    # NOTE: remove all negative values and replace them with 0
    before_20 = [0 if i < 0 else i for i in before_20]

    average_before_20 = average_yearly_value(before_20)
    average_after_20 = average_yearly_value(after_20)[0 : len(breakdown) - 1]

    return average_before_20, average_after_20


def yearly_time_dependent_20_year_breakdown_new_test(start_value, end_value, years_implementation, years_capitalization, function):

    breakdown = yearly_time_dependent_parameter_breakdown_new_test(start_value, end_value, years_implementation, years_capitalization, function, interim_values=False)

    after_20 = [0 for i in range(21)]
    after_20.extend(breakdown)

    before_20 = [i - j for i, j in zip(breakdown, after_20[0 : len(breakdown)])]

    # NOTE: remove all negative values and replace them with 0
    before_20 = [0 if i < 0 else i for i in before_20]

    # average_before_20 = average_yearly_value(before_20)
    # average_after_20 = average_yearly_value(after_20)[0 : len(breakdown) - 1]

    return before_20, after_20


def breakdown_according_to_values(maximum, list_of_proportions):
    if sum(list_of_proportions) == 0:
        return [0 for i in list_of_proportions]
    else:
        result = [maximum * i / sum(list_of_proportions) for i in list_of_proportions]
        return result


def breakdown_according_to_values_for_x_years(maximum, list_of_proportions, years):
    # The breakdown has to be done for x years of the project, after which it is 0
    # set list of proportions to 0 after x years
    list_of_proportions_new = [0 for i in range(len(list_of_proportions))]
    for i in range(years):
        list_of_proportions_new[i] = list_of_proportions[i]

    if sum(list_of_proportions_new) == 0:
        return [0 for i in list_of_proportions_new]
    else:
        result = [maximum * i / sum(list_of_proportions_new) for i in list_of_proportions_new]
        return result


def yearly_time_dependent_increase(start_value, end_value, years_implementation, years_capitalization, function):
    result_interim = yearly_time_dependent_parameter_breakdown(start_value, end_value, years_implementation, years_capitalization, function, interim_values=True)
    result_not_interim = yearly_time_dependent_parameter_breakdown(start_value, end_value, years_implementation, years_capitalization, function, interim_values=False)

    # subtract result_interim with each equivalent value in result_not_interim
    result = [i - j for i, j in zip(result_interim, result_not_interim)]

    return result


def yearly_time_dependent_increase_full_year(start_value, end_value, years_implementation, years_capitalization, function):
    values_at_year = yearly_time_dependent_parameter_breakdown(start_value, end_value, years_implementation, years_capitalization, function, interim_values=False)
    delta_yearly = [values_at_year[i] - values_at_year[i - 1] for i in range(1, len(values_at_year))]

    return delta_yearly


import matplotlib.pyplot as plt


def yearly_time_dependent_matrix(start_value, end_value, years_implementation, years_capitalization, function, interim_values=True):

    if function == "linear":
        years_total = years_implementation + years_capitalization

        half_year = yearly_time_dependent_increase(start_value, end_value, years_implementation, years_capitalization, function)
        full_year = yearly_time_dependent_increase_full_year(start_value, end_value, years_implementation, years_capitalization, function)

        matrix = np.full((years_implementation, years_total), 0.0)
        n = len(half_year)

        for i in range(matrix.shape[0]):
            matrix[i][i] = half_year[0]
            for j in range(i + 1, n):
                matrix[i][j] = full_year[0]

        # NOTE: now it does what is needed, but it is not very readable. Has to be fixed further on

        return matrix

    elif function == "immediate":
        years_total = years_implementation + years_capitalization

        matrix = np.full((years_implementation, years_total), end_value)

        return matrix

    elif function == "exponential":
        # NOTE: same as Linear, but kept on a different function for readability
        years_total = years_implementation + years_capitalization

        half_year = yearly_time_dependent_increase(start_value, end_value, years_implementation, years_capitalization, function)
        full_year = yearly_time_dependent_increase_full_year(start_value, end_value, years_implementation, years_capitalization, function)

        matrix = np.full((years_implementation, years_total), 0.0)
        n = len(half_year)

        for i in range(matrix.shape[0]):
            matrix[i][i] = half_year[0]
            for j in range(i + 1, n):
                matrix[i][j] = full_year[0]

        # NOTE: now it does what is needed, but it is not very readable. Has to be fixed further on

        return matrix

    else:
        raise Exception(f'Function "{function}" not recognized')


def yearly_time_dependent_matrix_log_rec_dis(start_value, end_value, years_implementation, years_capitalization, function, interim_values=True):

    if function == "linear":
        # NOTE: Basically the same as above, however rather than having the values of half a year of hectares across the diagonal (i.e. we intervene at half of the year),
        # we have the value of a full year at each cell. This is due to the fact that we are cutting all the hectares at the beginning of the year
        years_total = years_implementation + years_capitalization

        full_year = yearly_time_dependent_increase_full_year(start_value, end_value, years_implementation, years_capitalization, function)

        matrix = np.full((years_implementation, years_total), 0.0)
        n = len(full_year)

        for i in range(matrix.shape[0]):
            for j in range(i, n):
                matrix[i][j] = full_year[1]

        return matrix

    elif function == "immediate":
        years_total = years_implementation + years_capitalization

        matrix = np.full((years_implementation, years_total), end_value)

        return matrix

    elif function == "exponential":

        # NOTE: Basically the same as above, however rather than having the values of half a year of hectares across the diagonal (i.e. we intervene at half of the year),
        # we have the value of a full year at each cell. This is due to the fact that we are cutting all the hectares at the beginning of the year.
        # Again, same as above for linear just kept separate for readability
        years_total = years_implementation + years_capitalization

        full_year = yearly_time_dependent_increase_full_year(start_value, end_value, years_implementation, years_capitalization, function)

        matrix = np.full((years_implementation, years_total), 0.0)
        n = len(full_year)

        for i in range(matrix.shape[0]):
            for j in range(i, n):
                matrix[i][j] = full_year[1]

        return matrix

    else:
        raise Exception(f'Function "{function}" not recognized')


# LIVESTOCK CH4 HEAD GENERAL FUNCTION
# LIVESTOCK CH4 HEAD GENERAL FUNCTION
def ch4_head_calculation_general(tam: float, vser: float, ef_prp: float, 
                                 percentage_prp_default: float, percentage_prp_tier_2: float | None, 
                                 ef_system_default: list, ch4_prp_tier_2: float, percentage_system_default: list, 
                                 ef_single_system, ch4_system_tier_2, ch4_dividing_parameter=1):

    try:
        # TODO: check how various tier 2 inputs of ef_system have to be handled
        if ch4_system_tier_2 is None:
            ef_system = ef_system_default if ef_single_system is None else [ef_single_system]

            if percentage_prp_tier_2 is None:
                ch4_system = [i * (tam / 1000) * (vser) / ch4_dividing_parameter * 365 * j / 100 for (i, j) in zip(ef_system, percentage_system_default)]
            else:
                # this recalculates percentages in the system as a function of percentage prp tier 2
                ch4_system = [i * (tam / 1000) * vser / ch4_dividing_parameter * 365 * j / 100 * ((1 - percentage_prp_tier_2 / 100) / (1 - percentage_prp_default / 100)) for (i, j) in zip(ef_system, percentage_system_default)]

        else:
            # TODO: check if this has to be recalculated as a function of percentage prp tier 2
            ch4_system = [ch4_system_tier_2]

        percentage_prp = percentage_prp_default if percentage_prp_tier_2 is None else percentage_prp_tier_2

        # TODO: add tier 2 value for ef_prp
        ch4_prp = ef_prp * (tam / 1000) * vser / ch4_dividing_parameter * 365 * percentage_prp / 100 if not ch4_prp_tier_2 else ch4_prp_tier_2 * percentage_prp / 100

        ch4_head = sum(ch4_system) + ch4_prp

        return ch4_head, ch4_system, ch4_prp

    except Exception as e:
        traceback.print_exc()
        print("Error in ch4_head_calculation_general")
        raise e


def soil_emissions(hectars_before_20, area_start, area_end, socref, soc_tier_2, f_lu_tier_2, f_i_tier_2, f_mg_tier_2, f_lu_ref=1, f_i_ref=1, f_mg_ref=1):
    # f_mg and f_i are defaulted to 1 in case they are not inserted
    soc = socref if not soc_tier_2 else soc_tier_2
    f_lu = f_lu_ref if not f_lu_tier_2 else f_lu_tier_2
    f_i = f_i_ref if not f_i_tier_2 else f_i_tier_2
    f_mg = f_mg_ref if not f_mg_tier_2 else f_mg_tier_2

    delta_soil_c = (soc * f_lu) * (f_mg * f_i - 1) * (44 / 12)
    delta_soil_c_20_years = delta_soil_c / 20

    # SLIGHTLY DIFFERENT AS WE HAVE EXTRA PARAMETERS FOR DELTA SOIL C CALCULATION
    maximum = -delta_soil_c * max(area_start, area_end)

    total_hectars_soil = sum(hectars_before_20)
    predicted_emissions = -delta_soil_c_20_years * total_hectars_soil

    emissions = predicted_emissions if abs(predicted_emissions) < abs(maximum) else maximum

    emissions_soil_yearly = breakdown_according_to_values(emissions, hectars_before_20)
    emissions_soil_total = emissions

    return emissions_soil_yearly, emissions_soil_total


def soil_emissions_2(soc_start, soc_end, total_hectares, area_start, area_end, hectares_before_20):
    delta_co2_mineral_per_ha_per_yr = -(soc_end - soc_start) / 20 * (44 / 12)

    sum_total_hectars = sum(total_hectares)
    calculated = delta_co2_mineral_per_ha_per_yr * sum_total_hectars
    tabular = max(area_start, area_end) * delta_co2_mineral_per_ha_per_yr * 20

    total = tabular if abs(calculated) >= abs(tabular) else calculated

    emissions_soil_yearly = breakdown_according_to_values(total, hectares_before_20)
    emissions_soil_total = total

    return emissions_soil_yearly, emissions_soil_total


def som_emissions(soc_final, soc_initial, emission_factor_nitrous, nitrous_constant, hectares_before_20):
    n2o_n_conversion = 44 / 28

    # TODO: the divided by 10 has to be parametrized (take it from Claudio C:N ratio)
    som_n2o = 0 if soc_final >= soc_initial else ((soc_final - soc_initial) / 20 / 10 * 1000) * emission_factor_nitrous * n2o_n_conversion * (nitrous_constant / 1000)

    total = -sum(hectares_before_20) * som_n2o

    emissions_som_yearly = breakdown_according_to_values(total, hectares_before_20)
    emissions_som_total = total

    return emissions_som_yearly, emissions_som_total


def biomass_emissions(
    biomass_initial,
    biomass_final,
    hectares_start,
    hectares_end,
    rate_type,
    time_implementation,
    time_capitalization,
):

    yearly_variation_hectares = yearly_time_dependent_increase_full_year(hectares_start, hectares_end, time_implementation, time_capitalization, rate_type)

    biomass_variation = biomass_final - biomass_initial

    biomass_emissions_total = biomass_variation * -(44 / 12) * sum(yearly_variation_hectares)
    biomass_emissions_yearly = breakdown_according_to_values(biomass_emissions_total, yearly_variation_hectares)

    return biomass_emissions_yearly, biomass_emissions_total


# INPUT SINGLE MODULE CALCULATION
def input_single_calculation(unit_start, unit_end, ipcc_factor, tier_2_factor, unit_factor, emissions_factor, time_implementation, time_capitalization, rate_type):
    try:
        ipcc_or_tier_2_factor = tier_2_factor or ipcc_factor

        unit_start = unit_start * unit_factor
        unit_end = unit_end * unit_factor

        emissions_start = unit_start * ipcc_or_tier_2_factor * emissions_factor
        emissions_end = unit_end * ipcc_or_tier_2_factor * emissions_factor

        annual_emissions = yearly_time_dependent_parameter_breakdown(emissions_start, emissions_end, time_implementation, time_capitalization, rate_type)

    except Exception as e:
        traceback.print_exc()
        raise e
        

    return annual_emissions, sum(annual_emissions)


def input_single_calculation_different_ef(unit_start, unit_end, ipcc_factor, tier_2_factor, unit_factor, emission_factor_start, emission_factor_end, time_implementation, time_capitalization, rate_type):
    try:
        ipcc_or_tier_2_factor = tier_2_factor if tier_2_factor else ipcc_factor

        unit_start = unit_start * unit_factor
        unit_end = unit_end * unit_factor

        emissions_start = unit_start * ipcc_or_tier_2_factor * emission_factor_start
        emissions_end = unit_end * ipcc_or_tier_2_factor * emission_factor_end

        annual_emissions = yearly_time_dependent_parameter_breakdown(emissions_start, emissions_end, time_implementation, time_capitalization, rate_type)

    except Exception as e:
        traceback.print_exc()
        raise e

    return annual_emissions, sum(annual_emissions)


def soil_emissions_delta_soc_known(delta_soil_c, delta_soil_c_20_years, area_start, area_end, hectars_before_20):
    maximum = delta_soil_c_20_years * max(area_start, area_end) * 20

    total_hectars_soil = sum(hectars_before_20)

    predicted_emissions = delta_soil_c_20_years * total_hectars_soil

    emissions = predicted_emissions if abs(predicted_emissions) < abs(maximum) else maximum

    emissions_soil_yearly = breakdown_according_to_values(emissions, hectars_before_20)
    emissions_soil_total = emissions

    return emissions_soil_yearly, emissions_soil_total

############# FOREST MANAGEMENT FUNCTIONS #############
def breakdown_agb_bgb_emissions(rotation_times_hectares_agb, rotation_times_hectares_bgb, percentage_energy, forest_cf, forest_gef_ch4, forest_gef_n2o, forest_gef_co2, mangrove_factor, ef_nitrous, ef_methane):

    # TODO: forest_gef_co2 is not used as of now

    harvested_wood_product_agb = [x * -44 / 12 * (1 - percentage_energy) for x in rotation_times_hectares_agb]
    harvested_wood_product_bgb = [x * -44 / 12 * (1 - percentage_energy) for x in rotation_times_hectares_bgb]
    nitrous_fire_component_agb = [x * -44 / 12 * percentage_energy * forest_cf * forest_gef_n2o * ef_nitrous / 1000 for x in rotation_times_hectares_agb]
    methane_fire_component_agb = [x * -44 / 12 * percentage_energy * forest_cf * forest_gef_ch4 * ef_methane / 1000 for x in rotation_times_hectares_agb]
    nitrous_fire_component_bgb = [x * -44 / 12 * percentage_energy * forest_cf * forest_gef_n2o * ef_nitrous / 1000 for x in rotation_times_hectares_bgb]
    methane_fire_component_bgb = [x * -44 / 12 * percentage_energy * forest_cf * forest_gef_ch4 * ef_methane / 1000 for x in rotation_times_hectares_bgb]
    co2_fire_component_agb = [x * -44 / 12 * percentage_energy for x in rotation_times_hectares_agb]
    co2_fire_component_bgb = [x * -44 / 12 * percentage_energy for x in rotation_times_hectares_bgb]

    return harvested_wood_product_agb, harvested_wood_product_bgb, nitrous_fire_component_agb, methane_fire_component_agb, nitrous_fire_component_bgb, methane_fire_component_bgb, co2_fire_component_agb, co2_fire_component_bgb

def create_agb_bgb_matrix(years_impl, years_cap, delta_agb_yearly_below_20, delta_agb_yearly_after_20, agb_start, rotation_recurrence):

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
        raise e
    
    
def create_bgb_matrix_from_agb(agb_matrix, delta_agb_matrix, bgb_ratio_under_threshold, bgb_ratio_over_threshold, threshold, bgb_start, time_impl):

    try:
        delta_bgb_matrix = delta_agb_matrix * bgb_ratio_under_threshold
        bgb_matrix = np.full((agb_matrix.shape[0], agb_matrix.shape[1]), 0.0)

        for i in range(time_impl):
            for j in range(i, agb_matrix.shape[1]):
                value_to_assign = bgb_start + delta_bgb_matrix[i][j] + np.sum(delta_bgb_matrix[i, i:j])
                if value_to_assign > threshold:
                    delta_bgb_matrix[i][j] = delta_bgb_matrix[i][j]/bgb_ratio_under_threshold * bgb_ratio_over_threshold
                    value_to_assign = bgb_start + delta_bgb_matrix[i][j] + np.sum(delta_bgb_matrix[i, i:j])
                bgb_matrix[i][j] = value_to_assign

        return bgb_matrix, delta_bgb_matrix

    except Exception as e:
        traceback.print_exc()
        raise e
    
def check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value):
    
    # check for any negative values in the agb_matrix
    if np.any(agb_matrix < 0):
        raise Exception("Negative values in agb_matrix, percentage disturbance + percentage logging is > 100%")

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
        raise e

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
        raise e

def update_agb_matrix_logging(agb_matrix, delta_agb_matrix, original_delta_agb_matrix, max_agb_value, logging_impact, column, logging_recurrence, is_degradation):

    try:
        # take the value for each row on the column, that is much we are cutting down, subtract it from the agb_matrix across the row
        for row in range(0, min(agb_matrix.shape[0], column + 1)):
            agb_matrix[row, column:] = agb_matrix[row, column:] + logging_impact[row, column]
            # now set all values after the column to agb_matrix[row, column]
            agb_matrix[row, column:] = agb_matrix[row, column]

            for j in range(column, agb_matrix.shape[1]):
                if agb_matrix[row][j] < max_agb_value:
                    if is_degradation:
                        delta_agb_matrix[row][j] = original_delta_agb_matrix[row][j]
                    else:
                        delta_agb_matrix[row][j:] = original_delta_agb_matrix[row][j:]
                    # This means that there is a change in the agb_matrix so that we have to keep growing in delta_agb_matrix. Add for each value of
                    for m in range(j, min(agb_matrix.shape[1], j + logging_recurrence + 1)):
                        if m == agb_matrix.shape[1]:
                            agb_matrix[row][m] = agb_matrix[row][m] + np.sum(delta_agb_matrix[row][j:m])
                        else:
                            agb_matrix[row][m] = agb_matrix[row][m] + np.sum(delta_agb_matrix[row][j : m + 1])
                    break

        check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)

        return agb_matrix, delta_agb_matrix

    except Exception as e:
        traceback.print_exc()
        raise e
    
    
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
        raise e

def calculate_logging_effect(original_agb_matrix, original_delta_agb_matrix, max_agb_value, recurrence, start_year, percentage, is_degradation=False):

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
                ao = i * recurrence - 1 + start_year
                logging_impact[:, i * recurrence + start_year] = -agb_matrix[:, i * recurrence - 1 + start_year] * percentage

            # Update the agb_matrix
            agb_matrix, delta_agb_matrix = update_agb_matrix_logging(agb_matrix, delta_agb_matrix, original_delta_agb_matrix, max_agb_value, logging_impact, i * recurrence, recurrence, is_degradation)
            agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)

            # NOTE: as of now result is always empty, add necessary logic or remove it, as it's not used anywhere   

        return result, logging_impact, delta_agb_matrix

    except Exception as e:
        traceback.print_exc()
        raise e

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
        raise e

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

        # agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)

        return agb_matrix, delta_agb_matrix

    except Exception as e:
        traceback.print_exc()
        raise e