import math

def calculate_total_emissions(area_start, area_w, area_wo, time_impl, time_cap, rate_w, rate_coefficient_w, rate_wo, rate_coefficient_wo, nitrous_constant, methane_constant,
                            fire_interval_w, fire_interval_wo, fire_used_w, fire_used_wo, methane_ef, nitrous_ef, agb_ref, agb_tier_2, cf_ref, cf_tier_2,
                            soc_start_ref, soc_start_tier_2, soc_end_ref_w, soc_end_ref_wo, soc_end_tier_2_w, soc_end_tier_2_wo):
    '''
    ######## GENERAL PARAMETERS ########
    area_start
    area_w
    area_wo
    time_impl
    time_cap
    rate_w
    rate_coefficient_w
    rate_wo
    rate_coefficient_wo
    nitrous_constant
    methane_constant

    ######## RESIDUE BURNING ###########
    fire_interval_w: front-end input, years between two fires, default is 5 (on front-end)
    fire_interval_wo: front-end input, years between two fires, default is 5 (on front-end)
    fire_used_w: front-end input, states whether fire has been used
    fire_used_wo: front-end input, states whether fire has been used
    methane_ef: tabulated value IPCC D75 (value for Savanna and Grassland)
    nitrous_ef: tabulated value IPCC E75 (value for Savanna and Grassland)
    agb_ref: taken from IPCC A553 matching clim_moist to rows
    agb_tier_2: tier 2 value, expects float or None
    cf_ref: default is 77%, not tabulated
    cf_tier_2: tier 2 value, expects float or None   

    ########## SOIL EMISSIONS ##########
    soc_start_ref: lookup state_start in table in grass! W28-Y33
    soc_start_tier_2: tier 2 value, expects float or None
    soc_end_ref_w: lookup state_end_w in table in grass! W28-Y33
    soc_end_ref_wo: lookup state_end_wo in table in grass! W28-Y33
    soc_end_tier_2_w: tier 2 value, expects float or None
    soc_end_tier_2_wo: tier 2 value, expects float or None
    '''
    total_w = calculate_w_or_wo (area_start, area_w, time_impl, time_cap, rate_w, rate_coefficient_w, nitrous_constant, methane_constant,
                    soc_start_ref, soc_start_tier_2, soc_end_ref_w, soc_end_tier_2_w,
                    fire_interval_w, fire_used_w, methane_ef, nitrous_ef, agb_ref, agb_tier_2, cf_ref, cf_tier_2)
    total_wo = calculate_w_or_wo (area_start, area_wo, time_impl, time_cap, rate_wo, rate_coefficient_wo, nitrous_constant, methane_constant,
                    soc_start_ref, soc_start_tier_2, soc_end_ref_wo, soc_end_tier_2_wo,
                    fire_interval_wo, fire_used_wo, methane_ef, nitrous_ef, agb_ref, agb_tier_2, cf_ref, cf_tier_2)

    return (total_w, total_wo, total_w - total_wo)

def calculate_w_or_wo (area_start, area_end, time_impl, time_cap, rate_type, rate_coefficient, nitrous_constant, methane_constant,
                       soc_start_ref, soc_start_tier_2, soc_end_ref, soc_end_tier_2,
                       fire_interval, fire_used, methane_ef, nitrous_ef, agb_ref, agb_tier_2, cf_ref, cf_tier_2):

    # SINGLE COMPONENT CALCULATION FUNCTIONS
    def calculate_soil_emissions(time_impl, time_cap, rate_type, rate_of_change_soil, area_start, area, soc_start_ref, soc_start_tier_2, soc_end_ref, soc_end_tier_2):

    ################ HELPER FUNCTIONS #####################
        def soil_rate_immediate(area_defo, time_tot):
            return area_defo * min(20, time_tot) if area_defo > 0 else 0

        def soil_rate_other(time_tot, time_impl, area_defo, rate_of_change_soil, rate_type):
            return area_defo * middle_if_other(time_tot, time_impl, rate_of_change_soil, rate_type)

        def middle_if_other(time_tot, time_impl, rate_of_change_soil, rate_type):

            if time_tot > time_impl + 20:
                return 20
            else:
                if time_tot < 20:
                    return time_impl * rate_of_change_soil + time_tot - time_impl
                else: 
                    return min(20, time_impl) * rate_of_change_soil + time_tot - min(20, time_impl) - outer_if_other(rate_type, time_tot, time_impl)


        def outer_if_other(rate_type, time_tot, time_impl):

            if rate_type == "E":
                return time_tot - 20 + 0.217 * time_impl * (math.exp(4.606 * ((20 - time_tot)/time_impl)) - 1)
            else:
                return pow(time_tot - 20, 2) * (0.5/time_impl)

        ################## END OF HELPER FUNCTIONS AND START OF ACTUAL CALCULATION ###############
        soc_start = soc_start_ref if not soc_start_tier_2 else soc_start_tier_2
        soc_end = soc_end_ref if not soc_end_tier_2 else soc_end_tier_2
        delta_co2_mineral_per_ha_per_yr = - (soc_end - soc_start) / 20 * (44/12)


        time_tot = time_impl + time_cap
        calculated = (delta_co2_mineral_per_ha_per_yr * soil_rate_immediate(area, time_tot)) if rate_type == "I" else (delta_co2_mineral_per_ha_per_yr * soil_rate_other(time_tot, time_impl, area, rate_of_change_soil, rate_type))        
        tabular = (max(area_start, area) * delta_co2_mineral_per_ha_per_yr * 20)
        
        return tabular if abs(calculated) >= abs(tabular) else calculated

    def residue_burning(area_start, area, time_impl, time_cap, rate_coefficient, nitrous_constant, methane_constant, fire_interval, 
                        fire_used, methane_ef, nitrous_ef, agb_ref, agb_tier_2, cf_ref, cf_tier_2
                                                                ):
        # SUPPORT FUNCTIONS 
        def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):

            if area > area_start:
                return time_cap + time_impl * rate_coefficient
            else:
                return time_impl * (1 - rate_coefficient)


        if time_impl + time_cap < fire_interval or not fire_used:
            return 0
        else:
            agb = agb_ref if not agb_tier_2 else agb_tier_2
            cf = cf_ref if not cf_tier_2 else cf_tier_2
            agb_cf_gef = agb * cf * (methane_ef * methane_constant + nitrous_ef * nitrous_constant) / 1000
            annual_co2 = agb_cf_gef / fire_interval

            total = (min(area_start, area) * (time_cap + time_impl) + abs(area - area_start) * time_dependency(area_start, area, rate_coefficient, time_impl, time_cap)) * annual_co2

            return total
    
    soil = calculate_soil_emissions(time_impl, time_cap, rate_type, rate_coefficient, area_start, area_end, soc_start_ref, soc_start_tier_2, soc_end_ref, soc_end_tier_2)
    residue = residue_burning(area_start, area_end, time_impl, time_cap, rate_coefficient, nitrous_constant, methane_constant, fire_interval, 
                    fire_used, methane_ef, nitrous_ef, agb_ref, agb_tier_2, cf_ref, cf_tier_2)

    return soil + residue
                                                               

# emissions = calculate_total_emissions(100, 100, 100, 20, 9, 'D', 0.5, 'D', 0.5, 265, 28, 5, 8, True, True, 2.3, 0.21, 6.2, None, 0.77, None, 41.4, None, 46, 46, None, None  )
