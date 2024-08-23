# download a package to calculate logarithm in base e
import math
import re
import traceback
from dataclasses import dataclass

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

    return yearly_breakdown


def yearly_time_dependent_20_year_breakdown(start_value, end_value, years_implementation, years_capitalization, function):
    breakdown = yearly_time_dependent_parameter_breakdown(start_value, end_value, years_implementation, years_capitalization, function, interim_values=False)

    after_20 = [0 for i in range(21)]
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


# TODO: these functions basically only work with 'D' as a rate. has to be generalized
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
def ch4_head_calculation_general(tam: float, vser: float, ef_prp: float, percentage_prp_default: float, percentage_prp_tier_2: float | None, ef_system_default: list, ch4_prp_tier_2: float, percentage_system_default: list, ef_single_system, ch4_system_tier_2, ch4_dividing_parameter=1):

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

    except:
        traceback.print_exc()
        print("Error in ch4_head_calculation_general")
        return None



def soil_emissions(hectars_before_20, area_start, area_end, socref, soc_tier_2, f_lu_tier_2, f_i_tier_2, f_mg_tier_2, f_lu_ref=1, f_i_ref=1, f_mg_ref=1):
    # TODO: GENERALIZE SO IT CAN BE USED FOR ALL DIFFERENT KINDS OF CALCULATIONS, MEANING THAT SOCREF, FLU ecc ARE ASSIGNED IN THE MODULE SPECIFIC FUNCTION
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

    # TODO: ask if this should be broken down proportionally, in that case we have to take an approach similar to the one used in the soil calculation
    emissions_som_yearly = breakdown_according_to_values(total, hectares_before_20)
    emissions_som_total = total

    return emissions_som_yearly, emissions_som_total


def biomass_emissions(
    biomass_final,
    biomass_initial,
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

    except:
        traceback.print_exc()
        return [], []

    return annual_emissions, sum(annual_emissions)


def input_single_calculation_different_ef(unit_start, unit_end, ipcc_factor, tier_2_factor, unit_factor, emission_factor_start, emission_factor_end, time_implementation, time_capitalization, rate_type):
    try:
        ipcc_or_tier_2_factor = tier_2_factor if tier_2_factor else ipcc_factor

        unit_start = unit_start * unit_factor
        unit_end = unit_end * unit_factor

        emissions_start = unit_start * ipcc_or_tier_2_factor * emission_factor_start
        emissions_end = unit_end * ipcc_or_tier_2_factor * emission_factor_end

        annual_emissions = yearly_time_dependent_parameter_breakdown(emissions_start, emissions_end, time_implementation, time_capitalization, rate_type)

    except:
        traceback.print_exc()
        return None

    return annual_emissions, sum(annual_emissions)


def soil_emissions_delta_soc_known(delta_soil_c, delta_soil_c_20_years, area_start, area_end, hectars_before_20):
    maximum = delta_soil_c_20_years * max(area_start, area_end) * 20

    total_hectars_soil = sum(hectars_before_20)

    predicted_emissions = delta_soil_c_20_years * total_hectars_soil

    emissions = predicted_emissions if abs(predicted_emissions) < abs(maximum) else maximum

    emissions_soil_yearly = breakdown_according_to_values(emissions, hectars_before_20)
    emissions_soil_total = emissions

    return emissions_soil_yearly, emissions_soil_total


@dataclass
class Tier2Defaults:
    start: dict
    end: dict
    other: dict


