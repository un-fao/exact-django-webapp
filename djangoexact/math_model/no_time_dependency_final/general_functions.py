# download a package to calculate logarithm in base e
import math
def yearly_parameter_breakdown(start_value, end_value, years_implementation, years_capitalization, function):

    # UTILIZING THIS FUNCTION WE ARE RETURNING THE MIDDLE VALUE BETWEEN THE CALCULATED VALUES AT THE BEGINNING OF EACH YEAR. 
    # THIS IS DONE SO THAT THE YEARLY BREAKDOWN IS A LIST OF THE SAME LENGTH AS THE NUMBER OF YEARS IMPLEMENTATION + CAPITALIZATION
    # ALSO, THIS WAY THE RESULTS ARE THE SAME AS THE EXCEL RESULTS  
    def average_yearly_value(yearly_breakdown: list):
     
        average_yearly_value = [(yearly_breakdown[i] + yearly_breakdown[i + 1]) / 2 for i in range(len(yearly_breakdown) - 1)]
        
        return average_yearly_value


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
            return average_yearly_value(yearly_breakdown)
    
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
            return average_yearly_value(yearly_breakdown)
    
    if function == 'immediate':

        return average_yearly_value([end_value for i in range(years_implementation + years_capitalization + 1)])


# LIVESTOCK CH4 HEAD GENERAL FUNCTION    
def ch4_head_calculation_general(tam: float, vser: float, ef_prp: float, percentage_prp_default: float, percentage_prp_tier_2: float, ef_system_default: list, ef_system_tier_2: list, ch4_prp_tier_2: float, percentage_system_default: list):
            
        # THIS MEANS THAT THERE IS A TIER 2 VALUE 
        ef_system = ef_system_default if not ef_system_tier_2 else [ef_system_tier_2]

        if not percentage_prp_tier_2:
            ch4_system = [i * (tam/1000) * (vser/1000) * 365 * j/100 for (i,j) in zip(ef_system, percentage_system_default)]
        else: 
            # this recalculates percentages in the system as a function of percentage prp tier 2
            ch4_system = [i * (tam/1000) * (vser/1000) * 365 * j/100 * ((1-percentage_prp_tier_2/100)/(1-percentage_prp_default/100)) for (i,j) in zip(ef_system, percentage_system_default)]
        
        percentage_prp = percentage_prp_default if not percentage_prp_tier_2 else percentage_prp_tier_2
        ch4_prp = ef_prp * (tam/1000) * (vser/1000) * 365 * percentage_prp/100 if not ch4_prp_tier_2 else ch4_prp_tier_2 if not ch4_prp_tier_2 else ch4_prp_tier_2 * percentage_prp/100

        ch4_head = sum(ch4_system) + ch4_prp

        return ch4_head
    

