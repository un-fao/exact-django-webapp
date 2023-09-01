import numpy as np
import copy 
from general_functions import yearly_time_dependent_parameter_breakdown
import math

def create_agb_matrix(years_impl, years_cap, delta_agb_yearly):
    """
    Create a matrix of size years_total x years_total where years_total is the sum 
    of years_impl and years_cap. Every position to the right of the diagonal is filled 
    with delta_agb_yearly, as long as the row index is <= years_impl. The rest are filled with nan.
    """
    years_total = years_impl + years_cap
    agb_matrix = np.full((years_total, years_total), np.nan)
    
    # TODO: add logic for different parameters in delta_agb_yearly, before and after 20 years
    for i in range(years_impl):
        agb_matrix[i, i:] = delta_agb_yearly

    return agb_matrix

# def rotation_impact(agb_matrix, recurrence_rotation):
    # """
    # For each row in agb_matrix, start reading from the left. After the first number 
    # that is not nan, count a number of positions equal to recurrence_rotation. Each 
    # number after that should be saved in an equivalent matrix but negated.
    # """
    
    # # Create a matrix of the same size as agb_matrix but filled with zeros
    # rotation_matrix = np.zeros(agb_matrix.shape)

    # # Iterate over the rows of agb_matrix
    # for i in range(agb_matrix.shape[0]):
    #     # Find the first non-nan column for the current row
    #     first_non_nan_col = np.where(~np.isnan(agb_matrix[i, :]))[0]
        
    #     if first_non_nan_col.size > 0:
    #         start_col = first_non_nan_col[0] + recurrence_rotation
    #         # If the starting column index is within bounds, negate the values
    #         if start_col < agb_matrix.shape[1]:
    #             rotation_matrix[i, start_col:] = -agb_matrix[i, start_col:]

    # print(rotation_matrix)
    # return rotation_matrix

def rotation_impact(agb_matrix, recurrence_rotation):
    """
    For each row in agb_matrix, start reading from the left. After the first number 
    that is not nan, count a number of positions equal to recurrence_rotation. The 
    number after that should be negated, then we should have a series of zeros with 
    length equal to recurrence_rotation, and then the next number should be negated 
    and so on.
    """
    
    # Create a matrix of the same size as agb_matrix but filled with zeros
    rotation_matrix = np.zeros(agb_matrix.shape)

    # Iterate over the rows of agb_matrix
    for i in range(agb_matrix.shape[0]):
        # Find the first non-nan column for the current row
        first_non_nan_col = np.where(~np.isnan(agb_matrix[i, :]))[0]
        
        if first_non_nan_col.size > 0:
            col_pointer = first_non_nan_col[0] + recurrence_rotation

            while col_pointer < agb_matrix.shape[1]:
                # If it's not NaN, negate the value and store it
                if not np.isnan(agb_matrix[i, col_pointer]):
                    rotation_matrix[i, col_pointer] = -agb_matrix[i, col_pointer]

                col_pointer += 1  # Move to the next column

                # Skip columns equal to recurrence_rotation
                col_pointer += recurrence_rotation

    return rotation_matrix

def calculate_logging_effect(agb_matrix, recurrence, percentage=1.0):
    """
    For each interval of recurrence, compute the sum of non-nan values in agb_matrix 
    and multiply by a given percentage. Modify the matrix based on calculated values 
    and then return a dictionary where keys are multiples of recurrence and values 
    are the calculated sums for each interval.
    Also, return an equivalent matrix that accumulates the effects with a negative percentage.
    """
    
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

def multiply_matrix_by_list(matrix, lst):
    """
    Multiply each row of the matrix by the respective value in the list.
    
    Args:
    - matrix (numpy.ndarray): A 2D numpy array.
    - lst (list): A list of scalar values.
    
    Returns:
    - numpy.ndarray: A matrix where each row has been multiplied by the respective list value.
    """
    
    # Convert the list to a column matrix
    col_vector = np.array(lst).reshape(-1, 1)
    
    # Multiply matrix by column matrix element-wise, broadcasting the operation across rows
    return matrix * col_vector

def agb_bgb_emissions(years_impl, years_cap, delta_agb_yearly, delta_bgb_yearly, recurrence_rotation, recurrence_logging, percentage_agb_logging, hectares_yearly):
    """
    Calculate the emissions from AGB and BGB for a given set of parameters.
    """
    agb_matrix = create_agb_matrix(years_impl, years_cap, delta_agb_yearly)
    bgb_matrix = create_agb_matrix(years_impl, years_cap, delta_bgb_yearly)

    # TODO: Claudio has to send none if recurrence doesn't happen
    if recurrence_rotation:
        agb_rotation_matrix = rotation_impact(agb_matrix, recurrence_rotation)
        bgb_rotation_matrix = rotation_impact(bgb_matrix, recurrence_rotation)


        agb_matrix = agb_matrix + agb_rotation_matrix
        bgb_matrix = bgb_matrix + bgb_rotation_matrix
    
    if recurrence_logging:
        agb_logging_effect, agb_logging_matrix = calculate_logging_effect(copy.deepcopy(agb_matrix), recurrence_logging, percentage_agb_logging)
        bgb_logging_effect, bgb_logging_matrix = calculate_logging_effect(copy.deepcopy(bgb_matrix), recurrence_logging, percentage_agb_logging)
        agb_matrix = agb_matrix + agb_logging_matrix
        bgb_matrix = bgb_matrix + bgb_logging_matrix
    
    agb_bgb_matrix = agb_matrix + bgb_matrix
    emissions_matrix = multiply_matrix_by_list(agb_bgb_matrix, hectares_yearly)

    return emissions_matrix, np.nansum(emissions_matrix)

def deadwood_litter_emissions(delta_agb_yearly, max_agb_value, max_deadwood_value, max_litter_value, years_impl, years_cap, hectares_yearly):

    # years needed to reach max agb value
    years_to_reach_max = math.ceil(max_agb_value / delta_agb_yearly)

    deadwood_matrix = create_agb_matrix(years_impl, years_cap, max_deadwood_value/years_to_reach_max)
    litter_matrix = create_agb_matrix(years_impl, years_cap, max_litter_value/years_to_reach_max)

    emissions_deadwood_matrix = multiply_matrix_by_list(deadwood_matrix, hectares_yearly)
    emissions_litter_matrix = multiply_matrix_by_list(litter_matrix, hectares_yearly)

    return 


import numpy as np

def calculate_logging_effect(agb_matrix, recurrence, percentage=1.0, rotation=False):
    """
    For each interval of recurrence, compute the sum of non-nan values in agb_matrix 
    and multiply by a given percentage. Modify the matrix based on calculated values 
    and then return a dictionary where keys are multiples of recurrence and values 
    are the calculated sums for each interval.
    Also, return an equivalent matrix that accumulates the effects with a negative percentage.
    """
    
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
        
        if rotation:
            # For rotation case, adjust logging effect in a row-wise manner
            for j in range(0, end_col):
                row_idx = j % recurrence
                agb_matrix[row_idx, j] = agb_matrix[row_idx, j] * (1 - percentage)
                logging_matrix[row_idx, j] = -agb_matrix[row_idx, j] * percentage
        else:
            # Store the changes of the current round (before modifying the original matrix)
            changes = agb_matrix[:, 0:end_col] * percentage
            
            # Modify the values in the matrix for columns before the end_col
            agb_matrix[:, 0:end_col] = agb_matrix[:, 0:end_col] * (1 - percentage)
            
            # Add the changes to the logging_matrix
            logging_matrix[:, 0:end_col] += -changes

    return result, logging_matrix




# deadwood_litter_emissions(10, 100, 50, 40, 5, 5, yearly_time_dependent_parameter_breakdown(0, 100, 5, 5, 'D'))
import numpy as np

import numpy as np

import numpy as np

import numpy as np

import numpy as np

def calculate_rotation_effect(agb_matrix, recurrence, percentage=1.0):
    max_cols = agb_matrix.shape[1]
    max_rows = agb_matrix.shape[0]
    
    # Dictionary to hold the results
    yearly_totals = {}
    
    # Create a matrix to accumulate rotation effects
    rotation_matrix = np.zeros(agb_matrix.shape)

    print(agb_matrix)
    
    for year in range(1, max_cols + 1):
        total_rotation = 0
        
        # Main diagonal rotation
        if year <= max_rows:
            rotated_values = agb_matrix[year-1, :year] * percentage
            total_rotation += np.nansum(rotated_values)
            rotation_matrix[year-1, :year] += -rotated_values
            agb_matrix[year-1, :year] *= (1 - percentage)
        
        # Handle recurrences for all rows before the current one
        for row in range(year-1):
            # Check if it's time for the recurrence of this row
            if (year - row) % recurrence == 0:
                last_rotated_col = np.where(rotation_matrix[row, :year] != 0)[0][-1] + 1
                rotated_values = agb_matrix[row, last_rotated_col:year] * percentage
                total_rotation += np.nansum(rotated_values)
                rotation_matrix[row, last_rotated_col:year] += -rotated_values
                agb_matrix[row, last_rotated_col:year] *= (1 - percentage)
        
        yearly_totals[year] = total_rotation

    print(rotation_matrix)
    print(yearly_totals)
    return yearly_totals, rotation_matrix




# Test
calculate_rotation_effect(create_agb_matrix(5, 5, 10), 2, 1)




