def annexed_module(fire_boolean, time_impl, time_cap, rate_coefficient, dry_matter_default, dry_matter_tier_2, percentage_area_burned, ef_co2_default, ef_co2_tier_2, ef_co_default, ef_co_tier_2,
                            fire_periodicity, ef_ch4_default, ef_ch4_tier_2, methane_constant, area_affected_by_action):

    # TIER 2 VALUE DEFINITION FOR FIRE
    dry_matter = dry_matter_default if not dry_matter_tier_2 else dry_matter_tier_2
    ef_co2 = ef_co2_default if not ef_co2_tier_2 else ef_co2_tier_2
    ef_co = ef_co_default if not ef_co_tier_2 else ef_co_tier_2
    ef_ch4 = ef_ch4_default if not ef_ch4_tier_2 else ef_ch4_tier_2
    # ADD TIER 2 VALUES FOR DRAINAGE





    fire_soil = fire_emissions(fire_boolean, time_impl, time_cap, rate_coefficient, area_affected_by_action, dry_matter, percentage_area_burned, ef_co2, ef_co, fire_periodicity, ef_ch4, methane_constant)

    return fire_soil + drainage + rewetting

def time_dependency(rate_coefficient, time_impl, time_cap, units_start, units_end):

    def area_comparison(units_start, units_end, rate_coefficient, time_impl, time_cap):
        if units_end > units_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)
    
    total_emissions = (min(units_start, units_end) * (time_cap + time_impl) + abs(units_end - units_start) * area_comparison(units_start, units_end, rate_coefficient, time_impl, time_cap))

    return total_emissions

def fire_emissions(fire_boolean, time_impl, time_cap, rate_coefficient, area, dry_matter, percentage_area_burned, ef_co2, ef_co, fire_periodicity, ef_ch4, methane_constant):

    def fire_co2_co_ch4(fire_periodicity, dry_matter, area, rate_coefficient, time_impl, time_cap, percentage_area_burned, ef_co2, ef_co, ef_ch4, methane_constant):

        biomass_start = 0
        biomass_end = area * dry_matter

        total_biomass = time_dependency(rate_coefficient, time_impl, time_cap, biomass_start, biomass_end)

        multiplication_parameter_co2_co = (1/fire_periodicity * percentage_area_burned * ef_co2 * 44/12/1000) + (1/fire_periodicity * percentage_area_burned  * ef_co * 2 / 1000)
        multiplication_parameter_ch4 = 1/fire_periodicity * percentage_area_burned * ef_ch4 * methane_constant / 1000

        return total_biomass * multiplication_parameter_co2_co, total_biomass * multiplication_parameter_ch4
    
    
    if fire_boolean or fire_periodicity > time_cap + time_impl:
        co2_co, ch4 = fire_co2_co_ch4(fire_periodicity, dry_matter, area, rate_coefficient, time_impl, time_cap, percentage_area_burned, ef_co2, ef_co, ef_ch4, methane_constant)
        return co2_co + ch4
    else:
        return 0

def drainage_emissions_final(rate_coefficient, time_impl, time_cap, ef_doc, area_affected, area_drained_start, area_drained_end, ef_co2, methane_constant, percentage_ditches_start, percentage_ditches_end,
                       ef_ch4_on_site, ef_ch4_off_site, ef_n2o, nitrous_constant
                       ):

    def calculate_emissions_start_end(ef, area_affected_by_action_start, area_affected_by_action_end, percentage_area_multiplier_start, percentage_area_multiplier_end, area_affected_by_module, multiplying_constant):

            em_start = ef * area_affected_by_action_start * multiplying_constant * percentage_area_multiplier_start

            if area_affected == 0:
                em_end = ef * area_affected_by_action_end * percentage_area_multiplier_end * multiplying_constant
            elif area_affected_by_action_end < area_affected_by_module:
                em_end = 0
            else:
                em_end = ef * (area_affected_by_action_end - area_affected_by_action_start) * percentage_area_multiplier_end *  multiplying_constant
    
            return em_start, em_end

    n2ostart, n2oend = calculate_emissions_start_end(ef_n2o, area_drained_start, area_drained_end, 1, 1, area_affected, 44/28 * nitrous_constant/1000)

    ch4_start, ch4_end = calculate_emissions_start_end(ef_ch4_on_site, area_drained_start, area_drained_end, 1 - percentage_ditches_start, 1 - percentage_ditches_end, area_affected, methane_constant/1000) 
    ch4_start_ditches, ch4_end_ditches = calculate_emissions_start_end(ef_ch4_off_site, area_drained_start, area_drained_end, percentage_ditches_start, percentage_ditches_end, area_affected, methane_constant/1000)

    co2_start, co2_end = calculate_emissions_start_end(ef_co2, area_drained_start, 1, 1, area_drained_end, area_affected, 44/12)
    doc_start, doc_end = calculate_emissions_start_end(ef_doc, area_drained_start, 1, 1, area_drained_end, area_affected, 44/12)


    total_n2o = time_dependency(rate_coefficient, time_impl, time_cap, n2ostart, n2oend)

    total_ch4_onsite = time_dependency(rate_coefficient, time_impl, time_cap, ch4_start, ch4_end)
    total_ch4_off_site = time_dependency(rate_coefficient, time_impl, time_cap, ch4_start_ditches, ch4_end_ditches)

    total_doc = time_dependency(rate_coefficient, time_impl, time_cap, doc_start, doc_end)
    total_co2 = time_dependency(rate_coefficient, time_impl, time_cap, co2_start, co2_end)

    return total_doc + total_co2, total_ch4_onsite + total_ch4_off_site, total_n2o

def drainage_emissions_initial(rate_coefficient, time_impl, time_cap, ef_doc, area_affected, area_drained_start, area_drained_end, ef_co2, methane_constant, percentage_ditches_start, percentage_ditches_end,
                       ef_ch4_on_site, ef_ch4_off_site, ef_n2o, nitrous_constant
                       ):

    def calculate_emissions_start_end(ef, area_affected_by_action_start, area_affected_by_action_end, percentage_area_multiplier_start, percentage_area_multiplier_end, area_affected_by_module, multiplying_constant):

            em_start = 0

            if area_affected == 0:
                em_end = 0
            elif area_affected_by_action_end < area_affected_by_module:
                em_end = ef * area_affected_by_action_end * percentage_area_multiplier_end * multiplying_constant
            else:
                em_end = ef * (area_affected_by_action_end - area_affected_by_action_start) * percentage_area_multiplier_end *  multiplying_constant
    
            return em_start, em_end

    n2ostart, n2oend = calculate_emissions_start_end(ef_n2o, area_drained_start, area_drained_end, 1, 1, area_affected, 44/28 * nitrous_constant/1000)

    ch4_start, ch4_end = calculate_emissions_start_end(ef_ch4_on_site, area_drained_start, area_drained_end, 1 - percentage_ditches_start, 1 - percentage_ditches_end, area_affected, methane_constant/1000) 
    ch4_start_ditches, ch4_end_ditches = calculate_emissions_start_end(ef_ch4_off_site, area_drained_start, area_drained_end, percentage_ditches_start, percentage_ditches_end, area_affected, methane_constant/1000)

    co2_start, co2_end = calculate_emissions_start_end(ef_co2, area_drained_start, 1, 1, area_drained_end, area_affected, 44/12)
    doc_start, doc_end = calculate_emissions_start_end(ef_doc, area_drained_start, 1, 1, area_drained_end, area_affected, 44/12)


    total_n2o = time_dependency(rate_coefficient, time_impl, time_cap, n2ostart, n2oend)

    total_ch4_onsite = time_dependency(rate_coefficient, time_impl, time_cap, ch4_start, ch4_end)
    total_ch4_off_site = time_dependency(rate_coefficient, time_impl, time_cap, ch4_start_ditches, ch4_end_ditches)

    total_doc = time_dependency(rate_coefficient, time_impl, time_cap, doc_start, doc_end)
    total_co2 = time_dependency(rate_coefficient, time_impl, time_cap, co2_start, co2_end)

    return total_doc + total_co2, total_ch4_onsite + total_ch4_off_site, total_n2o

def rewetting_emissions_total(area_rewetted, ef_doc_initial, ef_co2_initial, ef_ch4_initial, ef_n2o_initial, methane_constant, nitrous_constant, area_not_rewetted, ef_doc_final, ef_co2_final, ef_ch4_final, ef_n2o_final, rate_coefficient, time_impl, time_cap):

    def rewetting_emissions(area_rewetted, ef_doc, ef_co2, ef_ch4, ef_n2o, methane_constant, nitrous_constant, rate_coefficient, time_impl, time_cap):
        
        def yearly_emissions_calculation(multiplication_parameter, area_affected_action, ef):
            return 0, multiplication_parameter * area_affected_action * ef
        
        co2_doc_y_start, co2_doc_y_end = yearly_emissions_calculation(ef_doc + ef_co2, area_rewetted, 44/12)
        ch4_y_start, ch4_y_end = yearly_emissions_calculation(ef_ch4, area_rewetted, methane_constant/1000 * 16/12)
        n2o_n_y_start, n2o_n_y_end = yearly_emissions_calculation(ef_n2o, area_rewetted, nitrous_constant/1000 * 44/28)

        total_co2_doc = time_dependency(rate_coefficient, time_impl, time_cap, co2_doc_y_start, co2_doc_y_end)
        total_ch4 = time_dependency(rate_coefficient, time_impl, time_cap, ch4_y_start, ch4_y_end)
        total_n2o = time_dependency(rate_coefficient, time_impl, time_cap, n2o_n_y_start, n2o_n_y_end)

        return sum([total_co2_doc, total_ch4, total_n2o])
    
    rewetting_initial = rewetting_emissions(area_rewetted, ef_doc_initial, ef_co2_initial, ef_ch4_initial, ef_n2o_initial, methane_constant, nitrous_constant, rate_coefficient, time_impl, time_cap)
    rewetting_final = rewetting_emissions(area_not_rewetted - area_rewetted, ef_doc_final, ef_co2_final, ef_ch4_final, ef_n2o_final, methane_constant, nitrous_constant, rate_coefficient, time_impl, time_cap)

    return sum([rewetting_initial, rewetting_final])

def rewetting_w_wo():
    return
def drainage_w_wo():
    return
def fire_w_wo():
    return
