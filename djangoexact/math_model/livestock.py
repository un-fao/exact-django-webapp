


def methane_enteric_fermentation(time_impl, time_cap, rate_coefficient, methane_constant, head_number_start, head_number_end, specific_factor_default, specific_factor_start_tier_2, specific_factor_end_tier_2):

    # this function is the same as flooded rice ch4 calculation, that's why it says area
    def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):
        if area > area_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)

    specific_factor_start = specific_factor_default if not specific_factor_start_tier_2 else specific_factor_start_tier_2
    specific_factor_end = specific_factor_default if not specific_factor_end_tier_2 else specific_factor_end_tier_2

    emissions_start = specific_factor_start / 1000 * methane_constant * head_number_start
    emissions_end = specific_factor_end / 1000 * methane_constant * head_number_end

    total_emissions = (min(emissions_start, emissions_end) * (time_cap + time_impl) + abs(emissions_end - emissions_start) * time_dependency(emissions_start, emissions_end, rate_coefficient, time_impl, time_cap))
    
    return total_emissions

def methane_manure_management(time_impl, time_cap, rate_coefficient, methane_constant, head_number_start, head_number_end, ostrich_or_deer_factor, kg_head_year_start, kg_head_year_end, ef_ppr, percentage_ppr_ipcc, percentage_ppr_start, percentage_ppr_end, ef_comp, ef_reg_share):

    def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):
        if area > area_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)


    """
    ostrich_or_deer_factor = 0.22 if 'Deer' else 5.67 if 'Ostrich' else None
    """

    factor_ipcc_start = evaluate_factor(kg_head_year_start, ef_ppr, percentage_ppr_ipcc, percentage_ppr_start, ef_comp, ef_reg_share)
    factor_ipcc_end = evaluate_factor(kg_head_year_end, ef_ppr, percentage_ppr_ipcc, percentage_ppr_end, ef_comp, ef_reg_share)

    factor_start = ostrich_or_deer_factor if ostrich_or_deer_factor else factor_ipcc_start
    factor_end = ostrich_or_deer_factor if ostrich_or_deer_factor else factor_ipcc_end

    emissions_start = factor_start / 1000 * methane_constant * head_number_start
    emissions_end = factor_end / 1000 * methane_constant * head_number_end

    total_emissions = (min(emissions_start, emissions_end) * (time_cap + time_impl) + abs(emissions_end - emissions_start) * time_dependency(emissions_start, emissions_end, rate_coefficient, time_impl, time_cap))
    
    return total_emissions

def methane_manure_management(time_impl, time_cap, rate_coefficient, methane_constant, head_number_start, head_number_end, ostrich_or_deer_factor, kg_head_year_start, kg_head_year_end, ef_ppr, percentage_ppr_ipcc, percentage_ppr_start, percentage_ppr_end, ef_comp, ef_reg_share):

    def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):
        if area > area_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)


    """
    ostrich_or_deer_factor = 0.22 if 'Deer' else 5.67 if 'Ostrich' else None
    """

    factor_ipcc_start = evaluate_factor(kg_head_year_start, ef_ppr, percentage_ppr_ipcc, percentage_ppr_start, ef_comp, ef_reg_share)
    factor_ipcc_end = evaluate_factor(kg_head_year_end, ef_ppr, percentage_ppr_ipcc, percentage_ppr_end, ef_comp, ef_reg_share)

    factor_start = ostrich_or_deer_factor if ostrich_or_deer_factor else factor_ipcc_start
    factor_end = ostrich_or_deer_factor if ostrich_or_deer_factor else factor_ipcc_end

    emissions_start = factor_start / 1000 * methane_constant * head_number_start
    emissions_end = factor_end / 1000 * methane_constant * head_number_end

    total_emissions = (min(emissions_start, emissions_end) * (time_cap + time_impl) + abs(emissions_end - emissions_start) * time_dependency(emissions_start, emissions_end, rate_coefficient, time_impl, time_cap))
    
    return total_emissions

def evaluate_factor(kg_head_year, ef_ppr, percentage_ppr_ipcc, percentage_ppr_end, ef_comp, ef_reg_share):

    if kg_head_year:
        return kg_head_year * percentage_ppr_end + ef_comp * (1 - percentage_ppr_end) + ef_reg_share * (1 - percentage_ppr_end)
    else:
        return ef_ppr / percentage_ppr_ipcc * percentage_ppr_end + ef_comp * (1 - percentage_ppr_end) + ef_reg_share / (1 - percentage_ppr_ipcc) * (1 - percentage_ppr_end)  



# methane_wo = methane_enteric_fermentation(20, 9, 0.5, 28, 500, 15, 81, None, None)

# print(methane_wo)

# fac = evaluate_factor(6, 0, 0, 0.35, 0, 0)

# meth_manure = methane_manure_management(20, 9, 0.5, 28, 500, 15, None, 3, 5, 0, 0, 0.59, 0.45, 0, 0  )
# print(meth_manure)

# CHECK WITH LORENZO
def methane_manure_management(ch4head, ef_prp, ef_system, tam, vser, percentage_prp, percentage_system):

    ch4headprp = ef_prp * tam * vser * 365 * percentage_prp
    ch4headcomp = ef_system * tam * vser * 365 * percentage_system
    ch4head = ch4headprp + ch4headcomp if not ch4head else ch4head

    return ch4head

meth_manure = methane_manure_management(20, 9, 0.5, 28, 500, 15, None, 3, 5, 0, 0, 0.59, 0.45, 0, 0  )
print(meth_manure)
