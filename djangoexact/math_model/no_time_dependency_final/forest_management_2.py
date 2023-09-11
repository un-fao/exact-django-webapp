import numpy as np
import copy 
from general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions, yearly_time_dependent_increase_half_year, yearly_time_dependent_full_year, yearly_time_dependent_matrix
import traceback
import pprint

def create_agb_matrix(years_impl, years_cap, delta_agb_yearly_below_20, delta_agb_yearly_after_20, max_agb_value, agb_start):
    """
    Create a matrix of size years_total x years_total where years_total is the sum 
    of years_impl and years_cap. Every position to the right of the diagonal is filled 
    with delta_agb_yearly, as long as the row index is <= years_impl. The rest are filled with nan.
    """
    years_total = years_impl + years_cap
    agb_matrix = np.full((years_total, years_total), 0)
    
    for i in range(years_impl):
        # Determine the end index for delta_agb_yearly_below_20
        end_index_below_20 = min(i + 20, years_total)
        
        # Fill with delta_agb_yearly_below_20 for the first 20 years
        agb_matrix[i, i:end_index_below_20] = delta_agb_yearly_below_20
        
        # Fill with delta_agb_yearly_after_20 for the subsequent years
        if end_index_below_20 < years_total:
            agb_matrix[i, end_index_below_20:] = delta_agb_yearly_after_20

        # sum agb_start to all values
        agb_matrix[i, :] += agb_start
        # Adjust values based on max_agb_value
        running_sum = 0
        for j in range(i, years_total):
            running_sum += agb_matrix[i, j]
            if running_sum > max_agb_value:
                # Adjust the current value and set subsequent values to 0
                agb_matrix[i, j] = max_agb_value - (running_sum - agb_matrix[i, j])
                agb_matrix[i, j+1:] = 0
                break

    return agb_matrix

def calculate_logging_effect(agb_matrix_original, recurrence, percentage=1.0):
    """
    For each interval of recurrence, compute the sum of non-nan values in agb_matrix 
    and multiply by a given percentage. Modify the matrix based on calculated values 
    and then return a dictionary where keys are multiples of recurrence and values 
    are the calculated sums for each interval.
    Also, return an equivalent matrix that accumulates the effects with a negative percentage.
    """
    agb_matrix = copy.deepcopy(agb_matrix_original)
    # Determine the maximum number of intervals given the shape of the matrix
    max_intervals = agb_matrix.shape[1] // recurrence
    
    # Dictionary to hold the results
    result = {}
    
    # Create a matrix to accumulate logging effects
    logging_matrix = np.zeros(agb_matrix.shape)
    
    for i in range(1, max_intervals + 1):
        end_col = i * recurrence
        
        # Calculate the sum of non-nan values for the current interval starting from column 0
        interval_sum = np.nansum(agb_matrix[:, 0:end_col])
        
        # Multiply by the given percentage and save to the result
        result[end_col] = interval_sum * percentage
        
        # Store the changes of the current round (before modifying the original matrix)
        changes = agb_matrix[:, 0:end_col] * percentage
        
        # Modify the values in the matrix for columns before the end_col
        agb_matrix[:, 0:end_col] = agb_matrix[:, 0:end_col] * (1 - percentage)
        
        # Add the changes to the logging_matrix
        logging_matrix[:, 0:end_col] += -changes

    return result, logging_matrix

def multiply_matrix_by_matrix(matrix1, matrix2):
    if matrix1.shape != matrix2.shape:
        raise ValueError("Both matrices must have the same dimensions!")
    
    # Element-wise multiplication
    multiplied_matrix = np.multiply(matrix1, matrix2)
    
    # Sum each column
    result = np.sum(multiplied_matrix, axis=0)

    return result

def calculate_rotation_effect(agb_matrix, recurrence, percentage=1):

    maximum_column = agb_matrix.shape[1]
    maximum_row = agb_matrix.shape[0]

    # let's approach this row wise and keep track of the changes
    results = {}
    
    rotation_impact = np.zeros(agb_matrix.shape)

    row_start = 0
    for row_index in range(maximum_row):
        row = agb_matrix[row_index]
        # sum up the values from column 0 to column recurrence excluded, then multiply by percentage
        i = 1
        while row_start + recurrence * i < maximum_column:
            # TODO: make the function a bit NICERRRRR
            if results.get(row_start + recurrence * i) is None:
                results[row_start + recurrence * i] = - np.nansum(row[row_start +recurrence*(i-1):row_start +recurrence*i]) * percentage
                # put negated value in rotation_impact
                rotation_impact[row_index,  row_start +recurrence*(i-1):row_start +recurrence*i ] = - agb_matrix[row_index, row_start +recurrence*(i-1):row_start +recurrence*i]
            else:
                results[row_start + recurrence * i] += - np.nansum(row[row_start +recurrence*(i-1):row_start +recurrence*i]) * percentage
                rotation_impact[row_index,  row_start +recurrence*(i-1):row_start +recurrence*i ] = - agb_matrix[row_index, row_start +recurrence*(i-1):row_start +recurrence*i]
                
            i += 1
        row_start += 1
    
    # order results by key
    results = dict(sorted(results.items()))
    return results, rotation_impact

class ForestManagement:

    def __init__(self, years_cap, years_impl, rate, hectares_start, hectares_end, rotation_recurrence, bgb_yearly_growth_under_20, agb_start,  agb_yearly_growth_under_20, agb_yearly_growth_over_20, max_agb_value, 
                disturbance_or_logging_recurrence: list, disturbance_or_logging_percentage: list, litter_20_years, deadwood_20_years, socref, soc_tier_2, f_lu_tier_2, f_i_tier_2, f_mg_tier_2, f_lu_ref, f_i_ref, f_mg_ref):
        
        self.years_cap = years_cap
        self.years_impl = years_impl
        self.rate = rate
        self.hectares_start = hectares_start
        self.hectares_end = hectares_end
        self.rotation_recurrence = rotation_recurrence

        self.bgb_yearly_growth_under_20 = bgb_yearly_growth_under_20
        self.agb_start = agb_start
        self.agb_yearly_growth_under_20 = agb_yearly_growth_under_20
        self.agb_yearly_growth_over_20 = agb_yearly_growth_over_20
        self.max_agb_value = max_agb_value
        self.disturbance_or_logging_recurrence = disturbance_or_logging_recurrence
        self.disturbance_or_logging_percentage = disturbance_or_logging_percentage

        self.litter_20_years = litter_20_years
        self.deadwood_20_years = deadwood_20_years 

        self.socref = socref
        self.soc_tier_2 = soc_tier_2
        self.f_lu_tier_2 = f_lu_tier_2
        self.f_i_tier_2 = f_i_tier_2
        self.f_mg_tier_2 = f_mg_tier_2
        self.f_lu_ref = f_lu_ref
        self.f_i_ref = f_i_ref
        self.f_mg_ref = f_mg_ref

        # Hectares breakdown
        self.hectares_total = yearly_time_dependent_parameter_breakdown(self.hectares_start, self.hectares_end, self.years_impl, self.years_cap, self.rate)
        self.hectares_before_20, self.hectares_after_20 = yearly_time_dependent_20_year_breakdown(self.hectares_start, self.hectares_end, self.years_impl, self.years_cap, self.rate)
        self.hectares_matrix = yearly_time_dependent_matrix(self.hectares_start, self.hectares_end, self.years_impl, self.years_cap, self.rate)
        # RESULTS
        self.yearly_agb_emissions = []
        self.total_agb_emissions = 0

        self.yearly_bgb_emissions = []
        self.total_bgb_emissions = 0

        self.yearly_litter_emissions = []
        self.total_litter_emissions = 0

        self.yearly_deadwood_emissions = []
        self.total_deadwood_emissions = 0

        self.yearly_disturbance_emissions = [] # NOTE: THIS IS A LIST OF LISTS
        self.total_disturbance_emissions = 0

        self.yearly_rotation_emissions = []
        self.total_rotation_emissions = 0

        self.yearly_soc_emissions = []
        self.total_soc_emissions = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        pass

    def calculate_emissions(self,):

        def calculate_agb_bgb_rotation_disturbance_emissions():

            try:

                # calculate agb matrix
                agb_matrix = create_agb_matrix(self.years_impl, self.years_cap, self.agb_yearly_growth_under_20, self.agb_yearly_growth_over_20, self.max_agb_value, self.agb_start)
                # if there is rotation there is not logging or disturbance
                rotation_results = []
                logging_disturbance_results = []
                
                if self.rotation_recurrence:
                    result_rotation, rotation_matrix = calculate_rotation_effect(agb_matrix, self.rotation_recurrence, percentage=1)
                    rotation_results.append(result_rotation)
                    agb_changed = agb_matrix + rotation_matrix
                
                else:
                    for recurrence, percentage in zip(self.disturbance_or_logging_recurrence, self.disturbance_or_logging_percentage):
                        result_logging_disturbance, logging_matrix = calculate_logging_effect(agb_matrix, recurrence, percentage)
                        logging_disturbance_results.append(result_logging_disturbance)
                        agb_changed = agb_matrix + logging_matrix
                
                # check if agb_matrix has negative values
                if np.any(agb_changed < 0):
                    raise ValueError(f'Negative values in agb_matrix, check the parameters for logging and disturbance % over 100')
                
                
                
                agb_times_hectares = multiply_matrix_by_matrix(agb_matrix, self.hectares_matrix)
                yearly_agb_emissions = [x * -44/12 for x in agb_times_hectares]
                self.yearly_agb_emissions = yearly_agb_emissions
                self.total_agb_emissions = sum(yearly_agb_emissions)

                agb_bgb_rate = self.agb_yearly_growth_under_20/self.bgb_yearly_growth_under_20

                self.yearly_bgb_emissions = [x * agb_bgb_rate for x in yearly_agb_emissions]
                self.total_bgb_emissions = sum(self.yearly_bgb_emissions)

                # calculate rotation emissions
                rotation_yearly_emissions = [0 for i in range(self.years_impl + self.years_cap)]
                for result in rotation_results:
                    for key, value in result.items():
                        rotation_yearly_emissions[key] += value * -44/12

                self.total_rotation_emissions = sum(rotation_yearly_emissions)
                self.yearly_rotation_emissions = rotation_yearly_emissions
                
                # calculate logging and disturbance emissions
                logging_disturbance_yearly_emissions = [[0 for i in range(self.years_impl + self.years_cap)] for j in range(len(self.disturbance_or_logging_recurrence))] 
                for i in range(len(logging_disturbance_results)):
                    for key, value in logging_disturbance_results[i].items():
                        logging_disturbance_yearly_emissions[i][key] += value * -44/12

                self.yearly_disturbance_emissions = logging_disturbance_yearly_emissions
                # sum up the emissions
                self.total_disturbance_emissions = sum([ sum(x) for x in logging_disturbance_yearly_emissions])


            
            except Exception as e:
                traceback.print_exc()
                return

        def calculate_litter():
            try:
                litter_matrix = create_agb_matrix(self.years_impl, self.years_cap, self.litter_20_years/20, 0, self.litter_20_years, 0)
                self.yearly_litter_emissions = [x * -44/12 for x in multiply_matrix_by_matrix(litter_matrix, self.hectares_matrix)]
                self.total_litter_emissions = sum(self.yearly_litter_emissions)
            except Exception as e:
                traceback.print_exc()
                return

        def calculate_deadwood():
            try:
                deadwood_matrix = create_agb_matrix(self.years_impl, self.years_cap, self.deadwood_20_years/20, 0, self.deadwood_20_years, 0)
                self.yearly_deadwood_emissions = [x * -44/12 for x in multiply_matrix_by_matrix(deadwood_matrix, self.hectares_matrix)]
                self.total_deadwood_emissions = sum(self.yearly_deadwood_emissions)
            except Exception as e:
                traceback.print_exc()
                return

        def calculate_soc():
            try:
                self.yearly_soc_emissions, self.total_soc_emissions  = soil_emissions(self.hectares_before_20, self.hectares_start, self.hectares_end, self.socref, self.soc_tier_2, self.f_lu_tier_2, 
                                                                                                                    self.f_i_tier_2, self.f_mg_tier_2, self.f_lu_ref, self.f_i_ref, self.f_mg_ref)
            except Exception as e:
                traceback.print_exc()
                return


        calculate_agb_bgb_rotation_disturbance_emissions()
        calculate_litter()
        calculate_deadwood()
        calculate_soc()

        # print results
        pprint.pprint('agb')
        pprint.pprint(self.yearly_agb_emissions)
        pprint.pprint('bgb')
        pprint.pprint(self.yearly_bgb_emissions)
        pprint.pprint('litter')
        pprint.pprint(self.yearly_litter_emissions)
        pprint.pprint('deadwood')
        pprint.pprint(self.yearly_deadwood_emissions)
        pprint.pprint('rotation')
        pprint.pprint(self.yearly_rotation_emissions)
        pprint.pprint('soc')
        pprint.pprint(self.yearly_soc_emissions)
        pprint.pprint('disturbance')
        pprint.pprint(self.yearly_disturbance_emissions)

        try:
            # ADD ALL EXPECT FOR DISTURBANCE EMISSIONS
            self.emissions_total_yearly = [i + j + k + l + m + n for i, j ,k, l, m, n in zip(self.yearly_agb_emissions, self.yearly_bgb_emissions, self.yearly_litter_emissions, self.yearly_deadwood_emissions, self.yearly_rotation_emissions, self.yearly_soc_emissions)]
            # ADD DISTURBANCE EMISSIONS
            for i in self.yearly_disturbance_emissions:
                for j, k in enumerate(i):
                    self.emissions_total_yearly[j] += k
        
            self.total_emissions = sum(self.emissions_total_yearly)
        except Exception as e:
            traceback.print_exc()
            return
        
years_cap = 0
years_impl = 5
rate = 'D'
hectares_start = 0
hectares_end = 500
rotation_recurrence = 5
bgb_yearly_growth_under_20 = 1
agb_start = 0
agb_yearly_growth_under_20 = 2
agb_yearly_growth_over_20 = 1
max_agb_value = 100
disturbance_or_logging_recurrence = [5, 10]
disturbance_or_logging_percentage = [0.2, 0.3]
litter_20_years = 20
deadwood_20_years = 20
socref = 20
soc_tier_2 = 1
f_lu_tier_2 = 1
f_i_tier_2 = 1
f_mg_tier_2 = 1
f_lu_ref = 1
f_i_ref = 1
f_mg_ref = 1

ForestManagements = ForestManagement(years_cap, years_impl, rate, hectares_start, hectares_end, rotation_recurrence, bgb_yearly_growth_under_20, agb_start,  agb_yearly_growth_under_20, agb_yearly_growth_over_20, max_agb_value,
                                     disturbance_or_logging_recurrence, disturbance_or_logging_percentage, litter_20_years, deadwood_20_years, socref, soc_tier_2, f_lu_tier_2, f_i_tier_2, f_mg_tier_2, f_lu_ref, f_i_ref, f_mg_ref)
ForestManagements.calculate_emissions()






