

def w_wo_emissions(ipcc_factor, tier_2_factor, quantity_start, quantity_w, quantity_wo, quantity_multiplication_parameter, emissions_multiplication_parameter, rate_coefficient_w, rate_coefficient_wo, time_impl, time_cap):

    # GENERALIZED FUNCTION FOR ALL INPUTS
    def general_function (ipcc_factor, tier_2_factor, quantity_start, quantity_end, quantity_multiplication_parameter, emissions_multiplication_parameter, rate_coefficient, time_impl, time_cap):

        # NECESSARY TIME DEPENDECY FUNCTION 
        def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):
            if area > area_start:
                return time_cap + time_impl * rate_coefficient
            else:
                return time_impl * (1 - rate_coefficient)

        # CALCULATE EMISSIONS
        quantity_start = quantity_start * quantity_multiplication_parameter if quantity_multiplication_parameter else quantity_start
        quantity_end = quantity_end * quantity_multiplication_parameter if quantity_multiplication_parameter else quantity_end

        factor = tier_2_factor if tier_2_factor else ipcc_factor
        emissions_start = factor * quantity_start * emissions_multiplication_parameter if emissions_multiplication_parameter else factor * quantity_start
        emissions_end = factor * quantity_end * emissions_multiplication_parameter if emissions_multiplication_parameter else factor * quantity_end

        total_emissions = (min(emissions_start, emissions_end) * (time_cap + time_impl) + abs(emissions_end - emissions_start) * time_dependency(emissions_start, emissions_end, rate_coefficient, time_impl, time_cap))

        return total_emissions

    """
    ipcc_factor: factor from ipcc
    tier_2_factor: tier 2 factor from front end input, sometimes available sometimes not. Expects None if not available or not inserted
    quantity_start: reference quantity for emissions calculation, at the start of the project
    quantity_w: reference quantity for emissions calculation, with the project
    quantity_wo: reference quantity for emissions calculation, without the project
    quantity_multiplication_parameter: multiplication parameter for quantity (for tonnes of Urea = 1)
    emissions_multiplication_parameter: multiplication parameter for emissions (Example: for Nitrous Emissions = Nitrous_constant * 44/28, for CO2 Emissions = 44/12 )
    rate_coefficient_w: rate coefficient for emissions calculation, with the project
    rate_coefficient_wo: rate coefficient for emissions calculation, without the project
    time_impl: time for implementation of the project
    time_cap: time for capitalization of the project
    """
    # ACTUAL COMPUTATION
    emissions_w = general_function(ipcc_factor, tier_2_factor, quantity_start, quantity_w, quantity_multiplication_parameter, emissions_multiplication_parameter, rate_coefficient_w, time_impl, time_cap)
    emissions_wo = general_function(ipcc_factor, tier_2_factor, quantity_start, quantity_wo, quantity_multiplication_parameter, emissions_multiplication_parameter,rate_coefficient_wo, time_impl, time_cap)

    return emissions_w, emissions_wo, emissions_w - emissions_wo
