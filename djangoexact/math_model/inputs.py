def input_single_calculation(unit_start, unit_end, rate_coefficient, ipcc_factor, tier_2_factor, unit_factor, emissions_factor, time_impl, time_cap):

    def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):

            if area > area_start:
                return time_cap + time_impl * rate_coefficient
            else:
                return time_impl * (1 - rate_coefficient)
            
    factor = tier_2_factor if tier_2_factor else ipcc_factor

    unit_start = unit_start * unit_factor
    unit_end = unit_end * unit_factor

    emissions_start = unit_start * ipcc_factor * emissions_factor
    emissions_end = unit_end * ipcc_factor * emissions_factor

    total_emissions = (min(emissions_start, emissions_end) * (time_cap + time_impl) + abs(emissions_end - emissions_start) * time_dependency(emissions_start, emissions_end, rate_coefficient, time_impl, time_cap))

    return total_emissions
