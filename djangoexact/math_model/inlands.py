def annexed_module(fire_boolean_end, fire_periodicity_end, area_affected_by_action_end, dry_matter_ref_fire, dry_matter_tier_2_fire, percentage_area_burned_end, ef_co2_ref_fire, ef_co2_tier_2_fire, ef_co_ref_fire, ef_co_tier_2_fire, ef_ch4_ref_fire, ef_ch4_tier_2_fire, methane_constant, rate_coefficient_fire_end, # FIRE EMISSIONS
                    time_impl, time_cap, nitrous_constant,  # GENERAL INFO
                    rate_coefficient_drainage_end, ef_doc_ref_drainage_initial, ef_doc_tier_2_drainage_initial, area_drained_start, area_drained_end, ef_co2_ref_drainage_initial, ef_co2_tier_2_drainage_initial, percentage_ditches_start, percentage_ditches_end, ef_ch4_onsite_ref_drainage_initial, ef_ch4_onsite_tier_2_drainage_initial, ef_ch4_offsite_ref_drainage_initial, ef_ch4_offsite_tier_2_drainage_initial, ef_n2o_ref_drainage_initial, ef_n2o_tier_2_drainage_initial, # DRAINAGE EMISSIONS INITIAL
                    ef_doc_ref_drainage_final, ef_doc_tier_2_drainage_final, ef_co2_ref_drainage_final, ef_co2_tier_2_drainage_final, ef_ch4_onsite_ref_drainage_final, ef_ch4_onsite_tier_2_drainage_final, ef_ch4_offsite_ref_drainage_final, ef_ch4_offsite_tier_2_drainage_final, ef_n2o_ref_drainage_final, ef_n2o_tier_2_drainage_final, # DRAINAGE EMISSIONS FINAL
                    rate_coefficient_rewetting_end, ef_doc_ref_rewetting_initial, ef_doc_tier_2_rewetting_initial, ef_co2_ref_rewetting_initial, ef_co2_tier_2_rewetting_initial, ef_ch4_ref_rewetting_initial, ef_ch4_tier_2_rewetting_initial, ef_n2o_ref_rewetting_initial, ef_n2o_tier_2_rewetting_initial, ef_doc_ref_rewetting_final, ef_doc_tier_2_rewetting_final, ef_co2_ref_rewetting_final, ef_co2_tier_2_rewetting_final, ef_ch4_ref_rewetting_final, ef_ch4_tier_2_rewetting_final, ef_n2o_ref_rewetting_final, ef_n2o_tier_2_rewetting_final, area_rewetted_initial, area_rewetted_final,   # REWETTING EMISSIONS
                    ):

    # FIRE EMISSIONS
    dry_matter_fire = dry_matter_ref_fire if not dry_matter_tier_2_fire else dry_matter_tier_2_fire
    ef_co2_fire = ef_co2_ref_fire if not ef_co2_tier_2_fire else ef_co2_tier_2_fire
    ef_co_fire = ef_co_ref_fire if not ef_co_tier_2_fire else ef_co_tier_2_fire
    ef_ch4_fire = ef_ch4_ref_fire if not ef_ch4_tier_2_fire else ef_ch4_tier_2_fire

    fire_soil_em_end = fire_emissions(fire_boolean_end, time_impl, time_cap, rate_coefficient_fire_end, area_affected_by_action_end, dry_matter_fire, percentage_area_burned_end, ef_co2_fire, ef_co_fire, fire_periodicity_end, ef_ch4_fire, methane_constant)
    # REWETTING EMISSIONS
    ef_doc_rewetting_initial = ef_doc_ref_rewetting_initial if not ef_doc_tier_2_rewetting_initial else ef_doc_tier_2_rewetting_initial
    ef_co2_rewetting_initial = ef_co2_ref_rewetting_initial if not ef_co2_tier_2_rewetting_initial else ef_co2_tier_2_rewetting_initial
    ef_ch4_rewetting_initial = ef_ch4_ref_rewetting_initial if not ef_ch4_tier_2_rewetting_initial else ef_ch4_tier_2_rewetting_initial
    ef_n2o_rewetting_initial = ef_n2o_ref_rewetting_initial if not ef_n2o_tier_2_rewetting_initial else ef_n2o_tier_2_rewetting_initial

    ef_doc_rewetting_final = ef_doc_ref_rewetting_final if not ef_doc_tier_2_rewetting_final else ef_doc_tier_2_rewetting_final
    ef_co2_rewetting_final = ef_co2_ref_rewetting_final if not ef_co2_tier_2_rewetting_final else ef_co2_tier_2_rewetting_final
    ef_ch4_rewetting_final = ef_ch4_ref_rewetting_final if not ef_ch4_tier_2_rewetting_final else ef_ch4_tier_2_rewetting_final
    ef_n2o_rewetting_final = ef_n2o_ref_rewetting_final if not ef_n2o_tier_2_rewetting_final else ef_n2o_tier_2_rewetting_final

    rewetting_initial_final = rewetting_emissions_total(area_rewetted_initial, area_rewetted_final, ef_doc_rewetting_initial, ef_co2_rewetting_initial, ef_ch4_rewetting_initial, ef_n2o_rewetting_initial, methane_constant, nitrous_constant, ef_doc_rewetting_final, ef_co2_rewetting_final, ef_ch4_rewetting_final, ef_n2o_rewetting_final, rate_coefficient_rewetting_end, time_impl, time_cap)
    # DRAINAGE EMISSIONS
    ef_doc_drainage_initial = ef_doc_ref_drainage_initial if not ef_doc_tier_2_drainage_initial else ef_doc_tier_2_drainage_initial
    ef_co2_drainage_initial = ef_co2_ref_drainage_initial if not ef_co2_tier_2_drainage_initial else ef_co2_tier_2_drainage_initial
    ef_ch4_onsite_drainage_initial = ef_ch4_onsite_ref_drainage_initial if not ef_ch4_onsite_tier_2_drainage_initial else ef_ch4_onsite_tier_2_drainage_initial
    ef_ch4_offsite_drainage_initial= ef_ch4_offsite_ref_drainage_initial if not ef_ch4_offsite_tier_2_drainage_initial else ef_ch4_offsite_tier_2_drainage_initial
    ef_n2o_drainage_initial = ef_n2o_ref_drainage_initial if not ef_n2o_tier_2_drainage_initial else ef_n2o_tier_2_drainage_initial

    ef_doc_drainage_final = ef_doc_ref_drainage_final if not ef_doc_tier_2_drainage_final else ef_doc_tier_2_drainage_final
    ef_co2_drainage_final = ef_co2_ref_drainage_final if not ef_co2_tier_2_drainage_final else ef_co2_tier_2_drainage_final
    ef_ch4_onsite_drainage_final = ef_ch4_onsite_ref_drainage_final if not ef_ch4_onsite_tier_2_drainage_final else ef_ch4_onsite_tier_2_drainage_final
    ef_ch4_offsite_drainage_final= ef_ch4_offsite_ref_drainage_final if not ef_ch4_offsite_tier_2_drainage_final else ef_ch4_offsite_tier_2_drainage_final
    ef_n2o_drainage_final = ef_n2o_ref_drainage_final if not ef_n2o_tier_2_drainage_final else ef_n2o_tier_2_drainage_final

    drainage_initial = drainage_emissions_initial(rate_coefficient_drainage_end, time_impl, time_cap, ef_doc_drainage_initial, area_affected_by_action_end, area_drained_start, area_drained_end, ef_co2_drainage_initial, methane_constant, percentage_ditches_start, percentage_ditches_end, ef_ch4_onsite_drainage_initial, ef_ch4_offsite_drainage_initial, ef_n2o_drainage_initial, nitrous_constant)
    drainage_final = drainage_emissions_final(rate_coefficient_drainage_end, time_impl, time_cap, ef_doc_drainage_final, area_affected_by_action_end, area_drained_start, area_drained_end, ef_co2_drainage_final, methane_constant, percentage_ditches_start, percentage_ditches_end, ef_ch4_onsite_drainage_final, ef_ch4_offsite_drainage_final, ef_n2o_drainage_final, nitrous_constant)

    return fire_soil_em_end + drainage_initial + drainage_final + rewetting_initial_final

def time_dependency(rate_coefficient, time_impl, time_cap, units_start, units_end):

    def area_comparison(units_start, units_end, rate_coefficient, time_impl, time_cap):
        if units_end > units_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)
    
    total_emissions = (min(units_start, units_end) * (time_cap + time_impl) + abs(units_end - units_start) * area_comparison(units_start, units_end, rate_coefficient, time_impl, time_cap))

    return total_emissions

# TODO: redo fire emissions
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

def drainage_emissions_initial(rate_coefficient, time_impl, time_cap, ef_doc, area_affected, area_drained_start, area_drained_end, ef_co2, methane_constant, percentage_ditches_start, percentage_ditches_end,
                       ef_ch4_on_site, ef_ch4_off_site, ef_n2o, nitrous_constant
                       ):

    def calculate_emissions_start_end(ef, area_affected_by_action_start, area_affected_by_action_end, percentage_area_multiplier_start, percentage_area_multiplier_end, area_affected_by_module, multiplying_constant):

            em_start = ef * area_affected_by_action_start * multiplying_constant * percentage_area_multiplier_start

            if area_affected_by_module == 0:
                em_end = ef * area_affected_by_module * percentage_area_multiplier_end * multiplying_constant
            elif area_affected_by_action_end < area_affected_by_module:
                em_end = 0
            else:
                em_end = ef * (area_affected_by_module - area_affected_by_action_end) * percentage_area_multiplier_end *  multiplying_constant
    
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

    return sum([total_doc + total_co2, total_ch4_onsite + total_ch4_off_site, total_n2o])

def drainage_emissions_final(rate_coefficient, time_impl, time_cap, ef_doc, area_affected, area_drained_start, area_drained_end, ef_co2, methane_constant, percentage_ditches_start, percentage_ditches_end,
                       ef_ch4_on_site, ef_ch4_off_site, ef_n2o, nitrous_constant
                       ):

    def calculate_emissions_start_end(ef, area_affected_by_action_start, area_affected_by_action_end, percentage_area_multiplier_start, percentage_area_multiplier_end, area_affected_by_module, multiplying_constant):

            em_start = 0

            if area_affected_by_module == 0:
                em_end = 0
            elif area_affected_by_action_end < area_affected_by_module:
                em_end = ef * area_affected_by_action_end * percentage_area_multiplier_end * multiplying_constant
            else:
                em_end = ef * (area_affected_by_action_start) * percentage_area_multiplier_end *  multiplying_constant
    
            return em_start, em_end

    n2ostart, n2oend = calculate_emissions_start_end(ef_n2o, area_affected, area_drained_end, 1, 1, area_affected, 44/28 * nitrous_constant/1000) # 

    ch4_start, ch4_end = calculate_emissions_start_end(ef_ch4_on_site, area_affected, area_drained_end, 1 - percentage_ditches_start, 1 - percentage_ditches_end, area_affected, methane_constant/1000) #
    ch4_start_ditches, ch4_end_ditches = calculate_emissions_start_end(ef_ch4_off_site, area_affected, area_drained_end, percentage_ditches_start, percentage_ditches_end, area_affected, methane_constant/1000) #

    co2_start, co2_end = calculate_emissions_start_end(ef_co2, area_affected, 1, 1, area_drained_end, area_affected, 44/12) #
    doc_start, doc_end = calculate_emissions_start_end(ef_doc, area_affected, 1, 1, area_drained_end, area_affected, 44/12) #


    total_n2o = time_dependency(rate_coefficient, time_impl, time_cap, n2ostart, n2oend)

    total_ch4_onsite = time_dependency(rate_coefficient, time_impl, time_cap, ch4_start, ch4_end)
    total_ch4_off_site = time_dependency(rate_coefficient, time_impl, time_cap, ch4_start_ditches, ch4_end_ditches)

    total_doc = time_dependency(rate_coefficient, time_impl, time_cap, doc_start, doc_end)
    total_co2 = time_dependency(rate_coefficient, time_impl, time_cap, co2_start, co2_end)

    return sum([total_doc + total_co2, total_ch4_onsite + total_ch4_off_site, total_n2o])

def rewetting_emissions_total(area_rewetted_initial, area_rewetted_final, ef_doc_initial, ef_co2_initial, ef_ch4_initial, ef_n2o_initial, methane_constant, nitrous_constant, ef_doc_final, ef_co2_final, ef_ch4_final, ef_n2o_final, rate_coefficient, time_impl, time_cap):

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
    
    rewetting_initial = rewetting_emissions(area_rewetted_initial, ef_doc_initial, ef_co2_initial, ef_ch4_initial, ef_n2o_initial, methane_constant, nitrous_constant, rate_coefficient, time_impl, time_cap)
    rewetting_final = rewetting_emissions(area_rewetted_final, ef_doc_final, ef_co2_final, ef_ch4_final, ef_n2o_final, methane_constant, nitrous_constant, rate_coefficient, time_impl, time_cap)

    return sum([rewetting_initial, rewetting_final])

#  TODO: ask Claudio how to address maximum_area_for_water_management, as it's different for defo, affo, ecc
def w_wo_annexed_module(maximum_area_for_water_management, area_drained_start, area_drained_w, area_drained_wo, area_affected_by_action_w, area_affected_by_action_wo, fire_boolean_w, fire_boolean_wo,
                        fire_periodicity_w, fire_periodicity_wo, percentage_area_burned_w, percentage_area_burned_wo, rate_coefficient_fire_w, rate_coefficient_fire_wo, rate_coefficient_drainage_w, rate_coefficient_drainage_wo,
                        percentage_ditches_w, percentage_ditches_wo,  dry_matter_ref_fire, dry_matter_tier_2_fire, ef_co2_ref_fire, ef_co2_tier_2_fire, ef_co_ref_fire,
                        ef_co_tier_2_fire, ef_ch4_ref_fire, ef_ch4_tier_2_fire, methane_constant, time_impl, time_cap, nitrous_constant, ef_doc_ref_drainage_initial,
                        ef_doc_tier_2_drainage_initial, ef_co2_ref_drainage_initial, ef_co2_tier_2_drainage_initial, percentage_ditches_start, ef_ch4_onsite_ref_drainage_initial,
                        ef_ch4_onsite_tier_2_drainage_initial, ef_ch4_offsite_ref_drainage_initial, ef_ch4_offsite_tier_2_drainage_initial, ef_n2o_ref_drainage_initial, ef_n2o_tier_2_drainage_initial, ef_doc_ref_drainage_final,
                        ef_doc_tier_2_drainage_final, ef_co2_ref_drainage_final, ef_co2_tier_2_drainage_final, ef_ch4_onsite_ref_drainage_final, ef_ch4_onsite_tier_2_drainage_final, ef_ch4_offsite_ref_drainage_final,
                        ef_ch4_offsite_tier_2_drainage_final, ef_n2o_ref_drainage_final, ef_n2o_tier_2_drainage_final, rate_coefficient_rewetting_w, rate_coefficient_rewetting_wo, ef_doc_ref_rewetting_initial, ef_doc_tier_2_rewetting_initial, ef_co2_ref_rewetting_initial,
                        ef_co2_tier_2_rewetting_initial, ef_ch4_ref_rewetting_initial, ef_ch4_tier_2_rewetting_initial, ef_n2o_ref_rewetting_initial, ef_n2o_tier_2_rewetting_initial, ef_doc_ref_rewetting_final, ef_doc_tier_2_rewetting_final,
                        ef_co2_ref_rewetting_final, ef_co2_tier_2_rewetting_final, ef_ch4_ref_rewetting_final, ef_ch4_tier_2_rewetting_final, ef_n2o_ref_rewetting_final, ef_n2o_tier_2_rewetting_final,
                        
                        
                        ):

    area_not_drained_start = maximum_area_for_water_management - area_drained_start
    area_not_drained_w = maximum_area_for_water_management - area_drained_w
    area_not_drained_wo = maximum_area_for_water_management - area_drained_wo

    if area_not_drained_start == maximum_area_for_water_management:
        area_rewet_initial_wo = 0
        area_rewet_final_wo = 0
        area_rewet_final_w = 0
        area_rewet_initial_w = 0
    else:
        area_rewet_initial_wo = max(0, area_not_drained_wo - area_not_drained_start - area_affected_by_action_wo)
        area_rewet_initial_w = max(0, area_not_drained_w - area_not_drained_start - area_affected_by_action_w)
        area_rewet_final_wo = area_not_drained_wo - area_rewet_initial_wo
        area_rewet_final_w = area_not_drained_w - area_rewet_initial_w

    em_w = annexed_module(fire_boolean_w, fire_periodicity_w, area_affected_by_action_w, dry_matter_ref_fire, dry_matter_tier_2_fire, percentage_area_burned_w, ef_co2_ref_fire, ef_co2_tier_2_fire, ef_co_ref_fire,
                        ef_co_tier_2_fire, ef_ch4_ref_fire, ef_ch4_tier_2_fire, methane_constant, rate_coefficient_fire_w, time_impl, time_cap, nitrous_constant, rate_coefficient_drainage_w, ef_doc_ref_drainage_initial,
                        ef_doc_tier_2_drainage_initial, area_drained_start, area_drained_w, ef_co2_ref_drainage_initial, ef_co2_tier_2_drainage_initial, percentage_ditches_start, percentage_ditches_w, ef_ch4_onsite_ref_drainage_initial,
                        ef_ch4_onsite_tier_2_drainage_initial, ef_ch4_offsite_ref_drainage_initial, ef_ch4_offsite_tier_2_drainage_initial, ef_n2o_ref_drainage_initial, ef_n2o_tier_2_drainage_initial, ef_doc_ref_drainage_final,
                        ef_doc_tier_2_drainage_final, ef_co2_ref_drainage_final, ef_co2_tier_2_drainage_final, ef_ch4_onsite_ref_drainage_final, ef_ch4_onsite_tier_2_drainage_final, ef_ch4_offsite_ref_drainage_final,
                        ef_ch4_offsite_tier_2_drainage_final, ef_n2o_ref_drainage_final, ef_n2o_tier_2_drainage_final, rate_coefficient_rewetting_w, ef_doc_ref_rewetting_initial, ef_doc_tier_2_rewetting_initial, ef_co2_ref_rewetting_initial,
                        ef_co2_tier_2_rewetting_initial, ef_ch4_ref_rewetting_initial, ef_ch4_tier_2_rewetting_initial, ef_n2o_ref_rewetting_initial, ef_n2o_tier_2_rewetting_initial, ef_doc_ref_rewetting_final, ef_doc_tier_2_rewetting_final,
                        ef_co2_ref_rewetting_final, ef_co2_tier_2_rewetting_final, ef_ch4_ref_rewetting_final, ef_ch4_tier_2_rewetting_final, ef_n2o_ref_rewetting_final, ef_n2o_tier_2_rewetting_final, area_rewet_initial_w, area_rewet_final_w,
                        )
    
    em_wo = annexed_module(fire_boolean_wo, fire_periodicity_wo, area_affected_by_action_wo, dry_matter_ref_fire, dry_matter_tier_2_fire, percentage_area_burned_wo, ef_co2_ref_fire, ef_co2_tier_2_fire, ef_co_ref_fire,
                           ef_co_tier_2_fire, ef_ch4_ref_fire, ef_ch4_tier_2_fire, methane_constant, rate_coefficient_fire_wo, time_impl, time_cap, nitrous_constant, rate_coefficient_drainage_wo, ef_doc_ref_drainage_initial,
                           ef_doc_tier_2_drainage_initial, area_drained_start, area_drained_wo, ef_co2_ref_drainage_initial, ef_co2_tier_2_drainage_initial, percentage_ditches_start, percentage_ditches_wo, ef_ch4_onsite_ref_drainage_initial,
                           ef_ch4_onsite_tier_2_drainage_initial, ef_ch4_offsite_ref_drainage_initial, ef_ch4_offsite_tier_2_drainage_initial, ef_n2o_ref_drainage_initial, ef_n2o_tier_2_drainage_initial, ef_doc_ref_drainage_final,
                           ef_doc_tier_2_drainage_final, ef_co2_ref_drainage_final, ef_co2_tier_2_drainage_final, ef_ch4_onsite_ref_drainage_final, ef_ch4_onsite_tier_2_drainage_final, ef_ch4_offsite_ref_drainage_final,
                           ef_ch4_offsite_tier_2_drainage_final, ef_n2o_ref_drainage_final, ef_n2o_tier_2_drainage_final, rate_coefficient_rewetting_wo, ef_doc_ref_rewetting_initial, ef_doc_tier_2_rewetting_initial, ef_co2_ref_rewetting_initial,
                           ef_co2_tier_2_rewetting_initial, ef_ch4_ref_rewetting_initial, ef_ch4_tier_2_rewetting_initial, ef_n2o_ref_rewetting_initial, ef_n2o_tier_2_rewetting_initial, ef_doc_ref_rewetting_final, ef_doc_tier_2_rewetting_final,
                           ef_co2_ref_rewetting_final, ef_co2_tier_2_rewetting_final, ef_ch4_ref_rewetting_final, ef_ch4_tier_2_rewetting_final, ef_n2o_ref_rewetting_final, ef_n2o_tier_2_rewetting_final, area_rewet_initial_wo, area_rewet_final_wo,
                           )
    
    return em_w, em_wo, em_w - em_wo


def peat_extraction_w_wo(hectars_start, hectars_w, hectars_wo, percentage_ditches_start, percentage_ditches_w, percentage_ditches_wo, rate_coefficient_w, rate_coefficient_wo, ef_co2_onsite_ref, ef_co2_onsite_tier_2, ef_ch4_onsite_ref, ef_ch4_onsite_tier_2, ef_n2o_onsite_ref, ef_n2o_onsite_tier_2, ef_doc_offsite_ref, 
                         ef_doc_offsite_tier_2, ef_ch4_offsite_ref, ef_ch4_offsite_tier_2,methane_constant, nitrous_constant, time_impl, time_cap, mass_tonnes_ref, mass_tonnes_tier_2, conversion_factor_volume, c_fraction_ref, extraction_height_start, extraction_height_w, extraction_height_wo ):
    
    def drainage_emissions(hectars_start, hectars_end, percentage_ditches_start, percentage_ditches_end, rate_coefficient_end, ef_co2_onsite_ref, ef_co2_onsite_tier_2, ef_ch4_onsite_ref, ef_ch4_onsite_tier_2, ef_n2o_onsite_ref, ef_n2o_onsite_tier_2, ef_doc_offsite_ref, ef_doc_offsite_tier_2, ef_ch4_offsite_ref, ef_ch4_offsite_tier_2, methane_constant, nitrous_constant, 
                               time_impl, time_cap):

        def yearly_emissions_calculation(ef_multiplication_parameter, hectars_start, hectars_end, ef, multiplier_start = 1, multiplier_end = 1):
                return hectars_start * ef * ef_multiplication_parameter * multiplier_start, hectars_end * ef * ef_multiplication_parameter * multiplier_end

        ef_co2_onsite = ef_co2_onsite_ref if not ef_co2_onsite_tier_2 else ef_co2_onsite_tier_2
        ef_ch4_onsite = ef_ch4_onsite_ref if not ef_ch4_onsite_tier_2 else ef_ch4_onsite_tier_2
        ef_n2o_onsite = ef_n2o_onsite_ref if not ef_n2o_onsite_tier_2 else ef_n2o_onsite_tier_2
        ef_doc_offsite = ef_doc_offsite_ref if not ef_doc_offsite_tier_2 else ef_doc_offsite_tier_2
        ef_ch4_offsite = ef_ch4_offsite_ref if not ef_ch4_offsite_tier_2 else ef_ch4_offsite_tier_2

        co2_onsite_emissions_start, co2_onsite_emissions_end = yearly_emissions_calculation(44/12, hectars_start, hectars_end, ef_co2_onsite)
        ch4_onsite_emissions_start, ch4_onsite_emissions_end = yearly_emissions_calculation(methane_constant/1000, hectars_start, hectars_end, ef_ch4_onsite, 1 - percentage_ditches_start, 1 - percentage_ditches_end)
        n2o_onsite_emissions_start, n2o_onsite_emissions_end = yearly_emissions_calculation(nitrous_constant/1000 * 44/28, hectars_start, hectars_end, ef_n2o_onsite)
        doc_offsite_emissions_start, doc_offsite_emissions_end = yearly_emissions_calculation(44/12, hectars_start, hectars_end, ef_doc_offsite)
        ch4_offsite_emissions_start, ch4_offsite_emissions_end = yearly_emissions_calculation(methane_constant/1000, hectars_start, hectars_end, ef_ch4_offsite, percentage_ditches_start, percentage_ditches_end)

        total_co2_doc = time_dependency(rate_coefficient_end, time_impl, time_cap, co2_onsite_emissions_start + doc_offsite_emissions_start, co2_onsite_emissions_end + doc_offsite_emissions_end)
        total_ch4 = time_dependency(rate_coefficient_end, time_impl, time_cap, ch4_onsite_emissions_start + ch4_offsite_emissions_start, ch4_onsite_emissions_end + ch4_offsite_emissions_end)
        total_n2o = time_dependency(rate_coefficient_end, time_impl, time_cap, n2o_onsite_emissions_start, n2o_onsite_emissions_end)

        return sum([total_co2_doc, total_ch4, total_n2o])
    
    def off_site_emissions(hectars_start, hectars_end, rate_coefficient_start, mass_tonnes_ref, mass_tonnes_tier_2, conversion_factor_volume, c_fraction_ref, extraction_height_start, extraction_height_end):

        def yearly_emissions_calculation(ef_multiplication_parameter, hectars_start, hectars_end, ef, multiplier_start = 1, multiplier_end = 1):
                return hectars_start * ef * ef_multiplication_parameter * multiplier_start, hectars_end * ef * ef_multiplication_parameter * multiplier_end
        
        mass_tonnes = mass_tonnes_ref if not mass_tonnes_tier_2 else mass_tonnes_tier_2
        air_dry_weight_start, air_dry_weight_end = yearly_emissions_calculation(10000/100, hectars_start, hectars_end, mass_tonnes, extraction_height_start, extraction_height_end)

        em_start = air_dry_weight_start * conversion_factor_volume * c_fraction_ref * 44/12
        em_end = air_dry_weight_end * conversion_factor_volume * c_fraction_ref * 44/12

        return time_dependency(rate_coefficient_start, time_impl, time_cap, em_start, em_end)


    drain_em_w = drainage_emissions(hectars_start, hectars_w, percentage_ditches_start, percentage_ditches_w, rate_coefficient_w, ef_co2_onsite_ref, ef_co2_onsite_tier_2, ef_ch4_onsite_ref, ef_ch4_onsite_tier_2, ef_n2o_onsite_ref, ef_n2o_onsite_tier_2, ef_doc_offsite_ref, 
                                    ef_doc_offsite_tier_2, ef_ch4_offsite_ref, ef_ch4_offsite_tier_2, methane_constant, nitrous_constant, time_impl, time_cap)
    drain_em_wo = drainage_emissions(hectars_start, hectars_wo, percentage_ditches_start, percentage_ditches_wo, rate_coefficient_wo, ef_co2_onsite_ref, ef_co2_onsite_tier_2, ef_ch4_onsite_ref, ef_ch4_onsite_tier_2, ef_n2o_onsite_ref, ef_n2o_onsite_tier_2, ef_doc_offsite_ref, 
                                     ef_doc_offsite_tier_2, ef_ch4_offsite_ref, ef_ch4_offsite_tier_2, methane_constant, nitrous_constant, time_impl, time_cap)
    
    offsite_em_w = off_site_emissions(hectars_start, hectars_w, rate_coefficient_w, mass_tonnes_ref, mass_tonnes_tier_2, conversion_factor_volume, c_fraction_ref, extraction_height_start, extraction_height_w)
    offsite_em_wo = off_site_emissions(hectars_start, hectars_wo, rate_coefficient_wo, mass_tonnes_ref, mass_tonnes_tier_2, conversion_factor_volume, c_fraction_ref, extraction_height_start, extraction_height_wo)
    

    
    return drain_em_w + offsite_em_w, drain_em_wo + offsite_em_wo, drain_em_w + offsite_em_w - (drain_em_wo + offsite_em_wo)


# ao = peat_extraction_w_wo(500, 32, 30, 0.5, 0.5, 0.5, 0.5, 0.5, 2, None, 0, None, 3.6, None, 0.82, None, 0, None, 28, 265, 20, 5, 0.765, None, 1, 0.34, 50, 50, 50)
# print(ao)

# TODO: TELL CLAUDIO THAT THE SUM OF ALL VALUES ON A COLUMN MUST BE THE SAME
def inland_waterbodies_w_wo(trophic_state_ref, trophic_state_tier_2, chlo_A, ch4_emission_ref, ch4_emission_tier_2_start, ch4_emission_tier_2_w, ch4_emission_tier_2_wo, methane_constant, rate_coefficient_w, rate_coefficient_wo, time_impl, time_cap, hectars_start, hectars_w, hectars_wo):

    def inland_emissions(trophic_state_ref, trophic_state_tier_2, chlo_A, ch4_emission_ref, ch4_emission_tier_2_start, ch4_emission_tier_2_end, methane_constant, rate_coefficient, time_impl, time_cap, hectars_start, hectars_end):
        
        if chlo_A:
            trophic_state = chlo_A * 0.26
        else:
            if trophic_state_tier_2:
                trophic_state = trophic_state_tier_2
            else:
                trophic_state = trophic_state_ref
        
        ch4_emission_start = ch4_emission_ref if not ch4_emission_tier_2_start else ch4_emission_tier_2_start
        ch4_emission_end = ch4_emission_ref if not ch4_emission_tier_2_end else ch4_emission_tier_2_end

        em_start = ch4_emission_start * hectars_start * trophic_state * methane_constant / 1000
        em_end = ch4_emission_end * hectars_end * trophic_state * methane_constant / 1000

        return time_dependency(rate_coefficient, time_impl, time_cap, em_start, em_end)
    
    em_w = inland_emissions(trophic_state_ref, trophic_state_tier_2, chlo_A, ch4_emission_ref, ch4_emission_tier_2_start, ch4_emission_tier_2_w, methane_constant, rate_coefficient_w, time_impl, time_cap, hectars_start, hectars_w)
    em_wo = inland_emissions(trophic_state_ref, trophic_state_tier_2, chlo_A, ch4_emission_ref, ch4_emission_tier_2_start, ch4_emission_tier_2_wo, methane_constant, rate_coefficient_wo, time_impl, time_cap, hectars_start, hectars_wo)

    return em_w, em_wo, em_w - em_wo

      
# ao = inland_aquaculture_w_wo(3, None, None, 183, None, None, None, 28, 0.5, 0.5, 20, 5, 43, 43, 43)
# print(ao)
def default_tier_2_inland_waterbodies(chlo_A, trophic_state_ref, ch4_emission_ref):

    if chlo_A:
        trophic_state = chlo_A * 0.26
    else:
        trophic_state = trophic_state_ref
        
    ch4_emission_start = ch4_emission_ref 
    ch4_emission_w = ch4_emission_ref
    ch4_emission_wo = ch4_emission_ref

    return trophic_state, ch4_emission_start, ch4_emission_w, ch4_emission_wo

def default_tier_2_peat_extraction(ef_co2_onsite_ref, ef_ch4_onsite_ref, ef_n2o_onsite_ref, ef_doc_offsite_ref, ef_ch4_offsite_ref, mass_tonnes_ref):

    ef_co2_onsite = ef_co2_onsite_ref 
    ef_ch4_onsite = ef_ch4_onsite_ref 
    ef_n2o_onsite = ef_n2o_onsite_ref 
    ef_doc_offsite = ef_doc_offsite_ref 
    ef_ch4_offsite = ef_ch4_offsite_ref 
    mass_tonnes = mass_tonnes_ref 

    return ef_co2_onsite, ef_ch4_onsite, ef_n2o_onsite, ef_doc_offsite, ef_ch4_offsite, mass_tonnes


maximum_area_for_water_management = 200
area_drained_start = 100
area_drained_w = 50
area_drained_wo = 30
area_affected_by_action_w = 50
area_affected_by_action_wo = 50
fire_boolean_w = True
fire_boolean_wo = True
fire_periodicity_w = 1
fire_periodicity_wo = 1
percentage_area_burned_w = 0.6
percentage_area_burned_wo = 0.6
rate_coefficient_fire_w = 0.5
rate_coefficient_fire_wo = 0.5
rate_coefficient_drainage_w = 0.5
rate_coefficient_drainage_wo = 0.5
percentage_ditches_w = 0.5
percentage_ditches_wo = 0.5
dry_matter_ref_fire = 155
dry_matter_tier_2_fire = None
ef_co2_ref_fire = 464
ef_co2_tier_2_fire = None
ef_co_ref_fire = 210
ef_co_tier_2_fire = None
ef_ch4_ref_fire = 21
ef_ch4_tier_2_fire = None
methane_constant = 28
time_impl = 20
time_cap = 5
nitrous_constant = 265
ef_doc_ref_drainage_initial = 0.82
ef_doc_tier_2_drainage_initial = None
ef_co2_ref_drainage_initial = 5.3
ef_co2_tier_2_drainage_initial = None
percentage_ditches_start = 0.5
ef_ch4_onsite_ref_drainage_initial = 4.9
ef_ch4_onsite_tier_2_drainage_initial = None
ef_ch4_offsite_ref_drainage_initial = 2259
ef_ch4_offsite_tier_2_drainage_initial = None
ef_n2o_ref_drainage_initial = 2.4
ef_n2o_tier_2_drainage_initial = None
ef_doc_ref_drainage_final = 0.82
ef_doc_tier_2_drainage_final = None
ef_co2_ref_drainage_final = 9.6
ef_co2_tier_2_drainage_final = None
ef_ch4_onsite_ref_drainage_final = 7
ef_ch4_onsite_tier_2_drainage_final = None
ef_ch4_offsite_ref_drainage_final = 2259
ef_ch4_offsite_tier_2_drainage_final = None
ef_n2o_ref_drainage_final = 5
ef_n2o_tier_2_drainage_final = None
rate_coefficient_rewetting_w = 0.5
rate_coefficient_rewetting_wo = 0.5
ef_doc_ref_rewetting_initial = 0.51
ef_doc_tier_2_rewetting_initial = None
ef_co2_ref_rewetting_initial = 0
ef_co2_tier_2_rewetting_initial = None
ef_ch4_ref_rewetting_initial = 41
ef_ch4_tier_2_rewetting_initial = None
ef_n2o_ref_rewetting_initial = 0
ef_n2o_tier_2_rewetting_initial = None
ef_doc_ref_rewetting_final = 0.51
ef_doc_tier_2_rewetting_final = None
ef_co2_ref_rewetting_final = 0 
ef_co2_tier_2_rewetting_final = None
ef_ch4_ref_rewetting_final = 41
ef_ch4_tier_2_rewetting_final = None
ef_n2o_ref_rewetting_final = 0
ef_n2o_tier_2_rewetting_final = None

    
ao =  w_wo_annexed_module(maximum_area_for_water_management, area_drained_start, area_drained_w, area_drained_wo, area_affected_by_action_w, area_affected_by_action_wo, fire_boolean_w, fire_boolean_wo,
                        fire_periodicity_w, fire_periodicity_wo, percentage_area_burned_w, percentage_area_burned_wo, rate_coefficient_fire_w, rate_coefficient_fire_wo, rate_coefficient_drainage_w, rate_coefficient_drainage_wo,
                        percentage_ditches_w, percentage_ditches_wo,  dry_matter_ref_fire, dry_matter_tier_2_fire, ef_co2_ref_fire, ef_co2_tier_2_fire, ef_co_ref_fire,
                        ef_co_tier_2_fire, ef_ch4_ref_fire, ef_ch4_tier_2_fire, methane_constant, time_impl, time_cap, nitrous_constant, ef_doc_ref_drainage_initial,
                        ef_doc_tier_2_drainage_initial, ef_co2_ref_drainage_initial, ef_co2_tier_2_drainage_initial, percentage_ditches_start, ef_ch4_onsite_ref_drainage_initial,
                        ef_ch4_onsite_tier_2_drainage_initial, ef_ch4_offsite_ref_drainage_initial, ef_ch4_offsite_tier_2_drainage_initial, ef_n2o_ref_drainage_initial, ef_n2o_tier_2_drainage_initial, ef_doc_ref_drainage_final,
                        ef_doc_tier_2_drainage_final, ef_co2_ref_drainage_final, ef_co2_tier_2_drainage_final, ef_ch4_onsite_ref_drainage_final, ef_ch4_onsite_tier_2_drainage_final, ef_ch4_offsite_ref_drainage_final,
                        ef_ch4_offsite_tier_2_drainage_final, ef_n2o_ref_drainage_final, ef_n2o_tier_2_drainage_final, rate_coefficient_rewetting_w, rate_coefficient_rewetting_wo, ef_doc_ref_rewetting_initial, ef_doc_tier_2_rewetting_initial, ef_co2_ref_rewetting_initial,
                        ef_co2_tier_2_rewetting_initial, ef_ch4_ref_rewetting_initial, ef_ch4_tier_2_rewetting_initial, ef_n2o_ref_rewetting_initial, ef_n2o_tier_2_rewetting_initial, ef_doc_ref_rewetting_final, ef_doc_tier_2_rewetting_final,
                        ef_co2_ref_rewetting_final, ef_co2_tier_2_rewetting_final, ef_ch4_ref_rewetting_final, ef_ch4_tier_2_rewetting_final, ef_n2o_ref_rewetting_final, ef_n2o_tier_2_rewetting_final,
                        )


    
# final = drainage_emissions_final(0.5, 20, 5, 0.82, 50, 100, 50, 9.6, 28, 0.5, 0.5, 7, 2259, 5, 265)
# initial = drainage_emissions_initial(0.5, 20, 5, 0.82, 50, 100, 50, 5.3 , 28, 0.5, 0.5, 4.9, 2259, 2.4, 265)


# print(final)
# print(initial)
