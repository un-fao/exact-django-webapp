# download a package to calculate logarithm in base e
import math
import traceback

def average_yearly_value(yearly_breakdown: list):
     
        average_yearly_value = [(yearly_breakdown[i] + yearly_breakdown[i + 1]) / 2 for i in range(len(yearly_breakdown) - 1)]
        
        return average_yearly_value

def yearly_time_dependent_parameter_breakdown(start_value, end_value, years_implementation, years_capitalization, function, interim_values = True):

    # UTILIZING THIS FUNCTION WE ARE RETURNING THE MIDDLE VALUE BETWEEN THE CALCULATED VALUES AT THE BEGINNING OF EACH YEAR. 
    # THIS IS DONE SO THAT THE YEARLY BREAKDOWN IS A LIST OF THE SAME LENGTH AS THE NUMBER OF YEARS IMPLEMENTATION + CAPITALIZATION
    # ALSO, THIS WAY THE RESULTS ARE THE SAME AS THE EXCEL RESULTS  
    


    # EXPONENTIAL CASE
    if function == 'exponential':
            
            # calculate the parameters for the function a*b^x
            a = min(start_value, end_value)
            b = (max(start_value, end_value) / min(start_value, end_value)) ** (1 / years_implementation)


            # Calculate the yearly breakdown
            if start_value < end_value:
                yearly_breakdown = [a * b ** i for i in range(years_implementation + 1)]
            else:
                yearly_breakdown = [a * b ** i for i in range(years_implementation + 1)]
                yearly_breakdown.reverse()

            yearly_breakdown.extend([yearly_breakdown[-1] for i in range(years_capitalization)])

            # return the yearly breakdown
            if interim_values:
                return average_yearly_value(yearly_breakdown)
            else:
                return yearly_breakdown
    
    if function == 'D':
         
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
    
    if function == 'immediate':
        if interim_values:
            return average_yearly_value([end_value for i in range(years_implementation + years_capitalization + 1)])
        else:
            return [end_value for i in range(years_implementation + years_capitalization + 1)]

def yearly_constant_emissions_breakdown(total_emissions, years_implementation, years_capitalization):
    # TODO: add logic for breakdown according to rate type
    # total emissions are broken down across impl with 0 in cap
    yearly_breakdown = [total_emissions / years_implementation for i in range(years_implementation)]
    yearly_breakdown.extend([0 for i in range(years_capitalization)])

    return yearly_breakdown

def yearly_time_dependent_20_year_breakdown(start_value, end_value, years_implementation, years_capitalization, function):
    
    breakdown = yearly_time_dependent_parameter_breakdown(start_value, end_value, years_implementation, years_capitalization, function, interim_values = False)
    
    after_20 = [0 for i in range(20)]
    after_20.extend(breakdown)

    before_20 = [i-j for i, j in zip(breakdown, after_20[0:len(breakdown)])]
    
    return average_yearly_value(before_20), average_yearly_value(after_20)[0:len(breakdown)]

def breakdown_according_to_values(maximum, list_of_proportions):

    result = [maximum * i/sum(list_of_proportions) for i in list_of_proportions]
    return result
# LIVESTOCK CH4 HEAD GENERAL FUNCTION    
def ch4_head_calculation_general(tam: float, vser: float, ef_prp: float, percentage_prp_default: float, percentage_prp_tier_2: float, ef_system_default: list, ef_system_tier_2: list, ch4_prp_tier_2: float, percentage_system_default: list, ch4_system_default, ch4_system_tier_2):
        
        try:
            # THIS MEANS THAT THERE IS A TIER 2 VALUE 
            ef_system = ef_system_default if not ef_system_tier_2 else [ef_system_tier_2]

            if not ch4_system_default and not ch4_system_tier_2:
                if not percentage_prp_tier_2:
                    ch4_system = [i * (tam/1000) * (vser/1000) * 365 * j/100 for (i,j) in zip(ef_system, percentage_system_default)]
                else: 
                    # this recalculates percentages in the system as a function of percentage prp tier 2
                    ch4_system = [i * (tam/1000) * (vser/1000) * 365 * j/100 * ((1-percentage_prp_tier_2/100)/(1-percentage_prp_default/100)) for (i,j) in zip(ef_system, percentage_system_default)]
            
            else:
                ch4_system = [ch4_system_default] if not ch4_system_tier_2 else [ch4_system_tier_2]

            percentage_prp = percentage_prp_default if not percentage_prp_tier_2 else percentage_prp_tier_2
            ch4_prp = ef_prp * (tam/1000) * (vser/1000) * 365 * percentage_prp/100 if not ch4_prp_tier_2 else ch4_prp_tier_2 * percentage_prp/100

            ch4_head = sum(ch4_system) + ch4_prp
            
            return ch4_head
        
        except:
            traceback.print_exc()
            print('Error in ch4_head_calculation_general')
            return None
    
def soil_emissions(hectars_before_20, area_start, area_end,
                   socref, soc_tier_2, f_lu_tier_2, f_i_tier_2, f_mg_tier_2, 
                   f_lu_ref = 1, f_i_ref = 1, f_mg_ref = 1):
    
    # TODO: GENERALIZE SO IT CAN BE USED FOR ALL DIFFERENT KINDS OF CALCULATIONS, MEANING THAT SOCREF, FLU ecc ARE ASSIGNED IN THE MODULE SPECIFIC FUNCTION
    # f_mg and f_i are defaulted to 1 in case they are not inserted
    soc = socref if not soc_tier_2 else soc_tier_2
    f_lu = f_lu_ref if not f_lu_tier_2 else f_lu_tier_2
    f_i = f_i_ref if not f_i_tier_2 else f_i_tier_2
    f_mg = f_mg_ref if not f_mg_tier_2 else f_mg_tier_2
    
    delta_soil_c = (soc * f_lu) * (f_mg * f_i - 1) * (44/12)
    delta_soil_c_20_years = delta_soil_c / 20

    # SLIGHTLY DIFFERENT AS WE HAVE EXTRA PARAMETERS FOR DELTA SOIL C CALCULATION
    maximum = - delta_soil_c * max(area_start, area_end)

    total_hectars_soil = sum(hectars_before_20)
    predicted_emissions = - delta_soil_c_20_years * total_hectars_soil

    emissions = predicted_emissions if abs(predicted_emissions) < abs(maximum) else maximum

    emissions_soil_yearly = breakdown_according_to_values(emissions, hectars_before_20)
    emissions_soil_total = emissions

    return emissions_soil_yearly, emissions_soil_total

# INPUT SINGLE MODULE CALCULATION
def input_single_calculation(unit_start, unit_end, ipcc_factor, tier_2_factor, unit_factor, emissions_factor, time_implementation, time_capitalization, rate_type):
                
            ipcc_or_tier_2_factor = tier_2_factor if tier_2_factor else ipcc_factor

            unit_start = unit_start * unit_factor 
            unit_end = unit_end * unit_factor 

            emissions_start = unit_start * ipcc_or_tier_2_factor * emissions_factor
            emissions_end = unit_end * ipcc_or_tier_2_factor * emissions_factor

            annual_emissions = yearly_time_dependent_parameter_breakdown(emissions_start, emissions_end, time_implementation , time_capitalization, rate_type)

            return annual_emissions, sum(annual_emissions)
