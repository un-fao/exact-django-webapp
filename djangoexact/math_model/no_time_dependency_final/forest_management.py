import copy
import traceback

import matplotlib.pyplot as plt
import numpy as np

from .general_functions import (
    breakdown_according_to_values,
    soil_emissions,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_full_year,
    yearly_time_dependent_increase_half_year,
    yearly_time_dependent_matrix,
    yearly_time_dependent_parameter_breakdown,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)


def create_agb_matrix(years_impl, years_cap, delta_agb_yearly_below_20, delta_agb_yearly_after_20, agb_start):
    years_total = years_impl + years_cap
    delta_agb_matrix = np.full((years_total, years_total), 0.0)
    agb_matrix = np.full((years_total, years_total), 0.0)

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

    # NOTE: no check is made to verify that the agb is not over the maximum value possible
    return agb_matrix, delta_agb_matrix


def create_bgb_matrix_from_agb(agb_matrix, delta_agb_matrix, bgb_ratio_under_threshold, bgb_ratio_over_threshold, threshold, bgb_start):
    delta_bgb_matrix = delta_agb_matrix * bgb_ratio_under_threshold
    bgb_matrix = np.full((agb_matrix.shape[0], agb_matrix.shape[1]), 0.0)

    for i in range(agb_matrix.shape[0]):
        for j in range(i, agb_matrix.shape[1]):
            value_to_assign = bgb_start + delta_bgb_matrix[i][j] + np.sum(delta_bgb_matrix[i, i:j])
            if value_to_assign > threshold:
                delta_bgb_matrix[i][j] = delta_bgb_matrix[i][j] * bgb_ratio_over_threshold
                value_to_assign = bgb_start + delta_bgb_matrix[i][j] + np.sum(delta_bgb_matrix[i, i:j])
            bgb_matrix[i][j] = value_to_assign

    return bgb_matrix, delta_bgb_matrix


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
                plt.text(i, cum_value + value / 2, str(value), ha="center", va="center")

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


def check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value):
    for i in range(agb_matrix.shape[0]):
        for j in range(i, agb_matrix.shape[1]):
            if agb_matrix[i][j] > max_agb_value:
                # Update agb_matrix
                agb_matrix[i][j:] = max_agb_value

                # Update delta_agb_matrix
                if j == 0:
                    delta_agb_matrix[i][j] = 0
                else:
                    delta_agb_matrix[i][j] = max_agb_value - agb_matrix[i][j - 1]

                delta_agb_matrix[i][j + 1 :] = 0
                break

    return agb_matrix, delta_agb_matrix


def update_agb_matrix_rotation(agb_matrix, delta_agb_matrix, original_delta_agb_matrix, max_agb_value, rotation_impact, row, column, row_at_maximum):
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


def update_agb_matrix_logging(agb_matrix, delta_agb_matrix, original_delta_agb_matrix, max_agb_value, logging_impact, column):
    # take the value for each row on the column, that is much we are cutting down, subtract it from the agb_matrix across the row
    for row in range(agb_matrix.shape[0]):
        hit_max = max(agb_matrix[row, :]) == max_agb_value
        agb_matrix[row, column:] = agb_matrix[row, column:] + logging_impact[row, column]

        if hit_max:
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


def calculate_rotation_effect(original_agb_matrix, original_delta_agb_matrix, max_agb_value, recurrence, start_year, percentage=1):
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

    # plot_matrix(agb_matrix)
    # plot_matrix(rotation_matrix)
    # order results by key
    results = dict(sorted(results.items()))

    # add to each year
    return results, rotation_matrix, delta_agb_matrix


def calculate_logging_effect(original_agb_matrix, original_delta_agb_matrix, max_agb_value, recurrence, start_year, percentage):
    agb_matrix = copy.deepcopy(original_agb_matrix)
    delta_agb_matrix = copy.deepcopy(original_delta_agb_matrix)
    # Determine the maximum number of intervals given the shape of the matrix
    max_intervals = (agb_matrix.shape[1] - start_year) // recurrence
    # Dictionary to hold the results
    result = {}
    # Create a matrix to accumulate logging effects
    logging_impact = np.full(agb_matrix.shape, 0.0)

    for i in range(1, max_intervals + 1):
        # Check if the agb_matrix is still below the maximum value
        agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)
        # i represents the column of our matrix. When there is logging we are cutting down a percentage of the forest present in year i
        # We are cutting down a percentage of the forest present in year i
        # NOTE: applied change here to include year of start (no idea if correct)
        logging_impact[:, i * recurrence - 1 + start_year] = -agb_matrix[:, i * recurrence - 2 + start_year] * percentage

        # Update the agb_matrix
        agb_matrix, delta_agb_matrix = update_agb_matrix_logging(agb_matrix, delta_agb_matrix, original_delta_agb_matrix, max_agb_value, logging_impact, i * recurrence - 1)
        agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, max_agb_value)

    return result, logging_impact, delta_agb_matrix


def multiply_matrix_by_matrix(matrix1, matrix2):
    if matrix1.shape != matrix2.shape:
        raise ValueError("Both matrices must have the same dimensions!")

    # Element-wise multiplication
    multiplied_matrix = np.multiply(matrix1, matrix2)

    # Sum each column
    result = np.sum(multiplied_matrix, axis=0)

    return result


# NOTE: LITTER AND DEADWOOD DON'T CARE, THEY KEEP ON GROWING
# TODO: TALK AGAIN ABOUT LITTER AND DEADWOOD, NOW SET TO KEEP ON GROWING OR EXISTING REGARDLESS OF ROTATION AND LOGGING, MAY CHANGE IN FUTURE
# agb_matrix, delta_agb_matrix = create_agb_matrix(5, 5, 10, 17, 88)
# #results, rotation_impact = calculate_rotation_effect(agb_matrix, delta_agb_matrix, 100, 5, 1)
# results, logging_matrix, agb_matrix = calculate_logging_effect(agb_matrix, delta_agb_matrix, 100, 5, 0.5)


class ForestManagement:
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
        litter_20_years_tier_2,
        deadwood_20_years_default,
        deadwood_20_years_tier_2,
        socref_default,
        soc_tier_2,
        f_lu_tier_2,
        f_i_tier_2,
        f_mg_tier_2,
        f_lu_ref,
        f_i_ref,
        f_mg_ref,
        ef_methane,
        ef_nitrous,
    ):
        # TODO: add year of start logic for rotation and disturbance
        self.years_cap = years_cap
        self.years_impl = years_impl
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
        self.deadwood_20_years = deadwood_20_years_default if not deadwood_20_years_tier_2 else deadwood_20_years_tier_2

        self.socref = socref_default if not soc_tier_2 else soc_tier_2
        self.soc_tier_2 = soc_tier_2
        self.f_lu_tier_2 = f_lu_tier_2
        self.f_i_tier_2 = f_i_tier_2
        self.f_mg_tier_2 = f_mg_tier_2
        self.f_lu_ref = f_lu_ref
        self.f_i_ref = f_i_ref
        self.f_mg_ref = f_mg_ref

        self.ef_methane = ef_methane
        self.ef_nitrous = ef_nitrous

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
            try:
                # calculate agb matrix
                agb_matrix, delta_agb_matrix = create_agb_matrix(self.years_impl, self.years_cap, self.agb_yearly_growth_under_20, self.agb_yearly_growth_over_20, self.agb_start)
                if self.bgb_yearly_growth_over_20_tier_2 and self.bgb_yearly_growth_under_20_tier_2:
                    bgb_matrix, delta_bgb_matrix = create_agb_matrix(self.years_impl, self.years_cap, self.bgb_yearly_growth_under_20_tier_2, self.bgb_yearly_growth_over_20_tier_2, self.bgb_start)
                else:
                    bgb_matrix, delta_bgb_matrix = create_bgb_matrix_from_agb(agb_matrix, delta_agb_matrix, self.bgb_ratio_under_threshold, self.bgb_ratio_over_threshold, self.bgb_ratio_threshold, self.bgb_start)

                # agb_matrix, delta_agb_matrix = check_agb_matrices(agb_matrix, delta_agb_matrix, self.max_agb_value)
                # if there is rotation there is not logging or disturbance

                if self.rotation_recurrence:
                    result_rotation_agb, rotation_matrix_agb, delta_agb_matrix = calculate_rotation_effect(agb_matrix, delta_agb_matrix, self.max_agb_value, self.rotation_recurrence, self.rotation_start_year)
                    result_rotation_bgb, rotation_matrix_bgb, delta_bgb_matrix = calculate_rotation_effect(bgb_matrix, delta_bgb_matrix, self.max_bgb_value, self.rotation_recurrence, self.rotation_start_year)

                    rotation_times_hectares_agb = multiply_matrix_by_matrix(rotation_matrix_agb, self.hectares_matrix)
                    rotation_times_hectares_bgb = multiply_matrix_by_matrix(rotation_matrix_bgb, self.hectares_matrix)

                    # NOTE: which one is it??!?!? This one or the one below
                    rotation_yearly_emissions_agb = [x * -44 / 12 * (1 - self.rotation_percentage_energy) for x in rotation_times_hectares_agb]
                    # TODO:check if this is correct
                    rotation_yearly_emissions_bgb = [x * -44 / 12 * (1 - self.rotation_percentage_energy) for x in rotation_times_hectares_bgb]

                    agb_fire_component = [x * -44 / 12 * self.rotation_percentage_energy for x in rotation_times_hectares_agb]
                    bgb_fire_component = [x * -44 / 12 * self.rotation_percentage_energy for x in rotation_times_hectares_bgb]
                    nitrous_fire_component = [x * -44 / 12 * self.rotation_percentage_energy * self.ef_nitrous for x in rotation_times_hectares_agb]
                    methane_fire_component = [x * -44 / 12 * self.rotation_percentage_energy * self.ef_methane for x in rotation_times_hectares_agb]

                    self.yearly_fire_rotation_emissions = [x + y + z + w for x, y, z, w in zip(agb_fire_component, bgb_fire_component, nitrous_fire_component, methane_fire_component)]
                    self.total_fire_rotation_emissions = sum(self.yearly_fire_rotation_emissions)

                    rotation_yearly_emissions = [x + y for x, y in zip(rotation_yearly_emissions_agb, rotation_yearly_emissions_bgb)]

                    self.total_rotation_emissions = sum(rotation_yearly_emissions)
                    self.yearly_rotation_emissions = rotation_yearly_emissions

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in agb_fire_component], activity=ActivityTypes.ROTATION))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in bgb_fire_component], activity=ActivityTypes.ROTATION))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component], activity=ActivityTypes.ROTATION))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component], activity=ActivityTypes.ROTATION))

                else:
                    # NOTE: here we can add percentage_fire easily, for now defaulted to 0
                    for recurrence, percentage, percentage_fire, start_year in zip(self.disturbance_recurrence, self.disturbance_percentage, [0 for i in self.disturbance_percentage], self.disturbance_year_of_start):
                        # NOTE: As logging and disturbance are the same, we can use the same function, also the variable names can be logging due to this
                        result_disturbance_agb, logging_matrix_agb, delta_agb_matrix = calculate_logging_effect(agb_matrix, delta_agb_matrix, self.max_agb_value, recurrence, start_year, percentage)
                        result_disturbance_bgb, logging_matrix_bgb, delta_bgb_matrix = calculate_logging_effect(bgb_matrix, delta_bgb_matrix, self.max_bgb_value, recurrence, start_year, percentage)

                        logging_times_hectares_agb = multiply_matrix_by_matrix(logging_matrix_agb, self.hectares_matrix)
                        logging_times_hectares_bgb = multiply_matrix_by_matrix(logging_matrix_bgb, self.hectares_matrix)

                        agb_fire_component = [x * -44 / 12 * percentage_fire for x in logging_times_hectares_agb]
                        bgb_fire_component = [x * -44 / 12 * percentage_fire for x in logging_times_hectares_bgb]
                        nitrous_fire_component = [x * -44 / 12 * percentage_fire * self.ef_nitrous for x in logging_times_hectares_agb]
                        methane_fire_component = [x * -44 / 12 * percentage_fire * self.ef_methane for x in logging_times_hectares_agb]

                        self.yearly_fire_disturbance_emissions.append([x + y + z + w for x, y, z, w in zip(agb_fire_component, bgb_fire_component, nitrous_fire_component, methane_fire_component)])
                        self.total_fire_disturbance_emissions = sum(self.yearly_fire_disturbance_emissions[-1])

                        logging_yearly_emissions_agb = [x * -44 / 12 for x in logging_times_hectares_agb]
                        logging_yearly_emissions_bgb = [x * -44 / 12 for x in logging_times_hectares_bgb]

                        logging_yearly_emissions = [x + y for x, y in zip(logging_yearly_emissions_agb, logging_yearly_emissions_bgb)]

                        self.yearly_disturbance_emissions.append(logging_yearly_emissions)
                        self.total_disturbance_emissions.append(sum(self.yearly_disturbance_emissions[-1]))

                        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in logging_yearly_emissions], activity=ActivityTypes.DISTURBANCE))

                        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.yearly_fire_disturbance_emissions[-1]], activity=ActivityTypes.DISTURBANCE))

                        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component], activity=ActivityTypes.DISTURBANCE))

                        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component], activity=ActivityTypes.DISTURBANCE))

                    result_logging_agb, logging_matrix_agb, delta_agb_matrix = calculate_logging_effect(agb_matrix, delta_agb_matrix, self.max_agb_value, self.logging_recurrence, self.logging_year_of_start, self.logging_percentage)
                    result_logging_bgb, logging_matrix_bgb, delta_bgb_matrix = calculate_logging_effect(bgb_matrix, delta_bgb_matrix, self.max_bgb_value, self.logging_recurrence, self.logging_year_of_start, self.logging_percentage)

                    logging_times_hectares_agb = multiply_matrix_by_matrix(logging_matrix_agb, self.hectares_matrix)
                    logging_times_hectares_bgb = multiply_matrix_by_matrix(logging_matrix_bgb, self.hectares_matrix)

                    agb_fire_component = [x * -44 / 12 * self.logging_percentage_energy for x in logging_times_hectares_agb]
                    bgb_fire_component = [x * -44 / 12 * self.logging_percentage_energy for x in logging_times_hectares_bgb]
                    nitrous_fire_component = [x * -44 / 12 * self.logging_percentage_energy * self.ef_nitrous for x in logging_times_hectares_agb]
                    methane_fire_component = [x * -44 / 12 * self.logging_percentage_energy * self.ef_methane for x in logging_times_hectares_agb]

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in agb_fire_component], activity=ActivityTypes.LOGGING))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in bgb_fire_component], activity=ActivityTypes.LOGGING))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in nitrous_fire_component], activity=ActivityTypes.LOGGING))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in methane_fire_component], activity=ActivityTypes.LOGGING))

                # TODO: find a way to check if agb_matrix has negative values just not this wa
                # check if agb_matrix has negative values
                if np.any(np.sum(agb_matrix < 0), axis=0):
                    raise ValueError(f"Negative values in agb_matrix, check the parameters for logging and disturbance % over 100")

                # agb_times_hectares = multiply_matrix_by_matrix(delta_agb_matrix, self.hectares_matrix)
                # yearly_agb_emissions = [x * -44/12 for x in agb_times_hectares]
                # self.yearly_agb_emissions = yearly_agb_emissions
                # self.total_agb_emissions = sum(yearly_agb_emissions)

                # bgb_times_hectares = multiply_matrix_by_matrix(delta_bgb_matrix, self.hectares_matrix)
                # yearly_bgb_emissions = [x * -44/12 for x in bgb_times_hectares]
                # self.yearly_bgb_emissions = yearly_bgb_emissions
                # self.total_bgb_emissions = sum(yearly_bgb_emissions)

                # self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(
                #                     year = 0,
                #                     gas_type = GasTypes.CO2,
                #                     emissions = [Emission(e, GasTypes.CO2) for e in self.yearly_agb_emissions],
                #                     activity = ActivityTypes.ROTATION_AGB
                #                 ))

                # self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(
                #                     year = 0,
                #                     gas_type = GasTypes.CO2,
                #                     emissions = [Emission(e, GasTypes.CO2) for e in self.yearly_bgb_emissions],
                #                     activity = ActivityTypes.ROTATION_BGB
                #                 ))

            except Exception as e:
                traceback.print_exc()
                return

        def calculate_litter():
            try:
                litter_matrix, delta_litter_matrix = create_agb_matrix(self.years_impl, self.years_cap, self.litter_20_years/20, self.litter_20_years/20, 0)
                self.yearly_litter_emissions = [x * -44/12 for x in multiply_matrix_by_matrix(delta_litter_matrix, self.hectares_matrix)]
                self.total_litter_emissions = sum(self.yearly_litter_emissions)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.yearly_litter_emissions], activity=ActivityTypes.LITTER))

            except Exception as e:
                traceback.print_exc()
                return

        def calculate_deadwood():
            try:
                deadwood_matrix, delta_deadwood_matrix = create_agb_matrix(self.years_impl, self.years_cap, self.deadwood_20_years/20, self.deadwood_20_years/20, 0)
                self.yearly_deadwood_emissions = [x * -44/12 for x in multiply_matrix_by_matrix(delta_deadwood_matrix, self.hectares_matrix)]
                self.total_deadwood_emissions = sum(self.yearly_deadwood_emissions)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.yearly_deadwood_emissions], activity=ActivityTypes.DEADWOOD))

            except Exception as e:
                traceback.print_exc()
                return

        def calculate_soc():
            try:
                self.yearly_soc_emissions, self.total_soc_emissions = soil_emissions(self.hectares_before_20, self.hectares_start, self.hectares_end, self.socref, self.soc_tier_2, self.f_lu_tier_2, self.f_i_tier_2, self.f_mg_tier_2, self.f_lu_ref, self.f_i_ref, self.f_mg_ref)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.yearly_soc_emissions], activity=ActivityTypes.SOIL_CO2_CHANGE))

            except Exception as e:
                traceback.print_exc()
                return

        calculate_agb_bgb_rotation_disturbance_emissions()
        calculate_litter()
        calculate_deadwood()
        calculate_soc()

        try:
            # ADD ALL EXPECT FOR DISTURBANCE EMISSIONS
            # self.emissions_total_yearly = [i + j + k + l + m + n for i, j ,k, l, m, n in zip(self.yearly_agb_emissions, self.yearly_bgb_emissions, self.yearly_litter_emissions, self.yearly_deadwood_emissions, self.yearly_rotation_emissions, self.yearly_soc_emissions)]
            self.emissions_total_yearly = [i + j + k + l + m + n + o for i, j, k, l, m, n, o in zip(self.yearly_agb_emissions, self.yearly_bgb_emissions, self.yearly_litter_emissions, self.yearly_deadwood_emissions, self.yearly_rotation_emissions, self.yearly_soc_emissions, self.yearly_fire_rotation_emissions)]

            # ADD DISTURBANCE EMISSIONS
            # for i in self.yearly_disturbance_emissions:
            #     for j, k in enumerate(i):
            #         self.emissions_total_yearly[j] += k
            for i, j in zip(self.yearly_disturbance_emissions, self.yearly_fire_disturbance_emissions):
                for k, l in enumerate(i):
                    self.emissions_total_yearly[k] += l
                    self.emissions_total_yearly[k] += j[k]

            self.total_emissions = sum(self.emissions_total_yearly)
        except Exception as e:
            traceback.print_exc()
            return
