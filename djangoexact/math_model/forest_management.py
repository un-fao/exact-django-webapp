import math


def total_biomass_emissions(area_start, area_end, degradation_level_end_ref, degradation_level_end_tier_2, 
                            degradation_level_start_ref, degradation_level_start_tier_2, agb_ref, agb_tier_2, 
                            bgb_ref, bgb_tier_2 ):
    '''
    degradation_level_end_ref: match degradation level end string to list! O7-P13
    degradation_level_end_tier_2: tier 2 value, expects None or Float
    degradation_level_start_ref: match degradation level start string to list! O7-P13
    degradation_level_start_tier_2: tier 2 value, expects None or Float
    agb_ref: if TYPE_VEGETATION == Mangrove Forest, match clim_moist to IPCC A1502, else match CONTINENT and TYPE OF VEGETATION to IPCC A591 and multiply by 0.47 ---> maybe send a tuple, with true false?
    agb_tier_2: tier 2 value, expects None or Float
    bgb_ref:
    bgb_tier_2: tier 2 value, expects None or Float

    '''

    degradation_level_start = degradation_level_start_ref if not degradation_level_start_tier_2 else degradation_level_start_tier_2
    degradation_level_end = degradation_level_end_ref if not degradation_level_end_tier_2 else degradation_level_end_tier_2
    agb = agb_ref if not agb_tier_2 else agb_tier_2
    bgb = bgb_ref if not bgb_tier_2 else bgb_tier_2


    tot_biomass = agb + bgb

    biomass_start = tot_biomass * (1 - degradation_level_start)
    biomass_end = tot_biomass * (1 - degradation_level_end)

    return (biomass_end - biomass_start) * (-44/12) * area_end

def dom_emissions(area_end, degradation_level_end_ref, degradation_level_end_tier_2, 
                degradation_level_start_ref, degradation_level_start_tier_2, litter_ref, litter_tier_2,
                deadwood_ref, deadwood_tier_2 ):
    
    '''
    degradation_level_end_ref: match degradation level end string to list! O7-P13
    degradation_level_end_tier_2: tier 2 value, expects None or Float
    degradation_level_start_ref: match degradation level start string to list! O7-P13
    degradation_level_start_tier_2: tier 2 value, expects None or Float
    litter_ref: if VEGETATION_TYPE == Mangrove Forest match clim_moist to IPCC A1502 else match VEGETATION_TYPE to IPCC A643
    litter_tier_2: tier 2 value, expects None or Float
    deadwood_ref: if VEGETATION_TYPE == Mangrove Forest match clim_moist to IPCC A1502 else match VEGETATION_TYPE to IPCC A643
    deadwood_tier_2: tier 2 value, expects None or Float
    '''

    degradation_level_start = degradation_level_start_ref if not degradation_level_start_tier_2 else degradation_level_start_tier_2
    degradation_level_end = degradation_level_end_ref if not degradation_level_end_tier_2 else degradation_level_end_tier_2 
    litter = litter_ref if not litter_tier_2 else litter_tier_2
    deadwood = deadwood_ref if not deadwood_tier_2 else deadwood_tier_2

    tot_dom = litter + deadwood

    dom_start = tot_dom * (1 - degradation_level_start)
    dom_end = tot_dom * (1 - degradation_level_end)

    return (dom_end - dom_start) * (-44/12) * area_end

def soc_emissions(area_end, time_impl, time_cap, rate_type, rate_coefficient, soc_ref, soc_tier_2, 
                  luf_default, luf_start_tier_2, luf_end_tier_2 ):
    
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

    '''
    soc_ref: if VEGETATION_TYPE == Mangrove Forest match clim_moist to IPCC A1502 else return SocRef (1.Description input)
    soc_tier_2: tier 2 value, expects float or None
    luf_default: defaults to 1
    luf_start_tier_2: tier 2 value, expects float or None
    luf_end_tier_2: tier 2 value, expects float or None
    REMEMBER THERE ARE END WITH AND WITHOUT
    '''
    ################## END OF HELPER FUNCTIONS AND START OF ACTUAL CALCULATION ###############
    soc = soc_ref if not soc_tier_2 else soc_tier_2
    luf_start = luf_default if not luf_start_tier_2 else luf_start_tier_2
    luf_end = luf_default if not luf_end_tier_2 else luf_end_tier_2

    soc_start = soc * luf_start
    soc_end = soc * luf_end
    delta_co2_mineral_per_ha_per_yr = (soc_end - soc_start)/20 * (-44/12)
    time_tot = time_impl + time_cap

    calculated = (delta_co2_mineral_per_ha_per_yr * soil_rate_immediate(area_end, time_tot)) if rate_type == "I" else (delta_co2_mineral_per_ha_per_yr * soil_rate_other(time_tot, time_impl, area_end, rate_coefficient, rate_type))        
    
    
    return calculated

def fire_emissions(area_end, time_impl, time_cap, rate_coefficient, methane_constant, nitrous_constant,  
                   fire_periodicity, fire_used, cf, ef_methane, ef_nitrous, percentage_biomass_burnt,
                   degradation_level_end_ref, degradation_level_end_tier_2, 
                   degradation_level_start_ref, degradation_level_start_tier_2, agb_ref, agb_tier_2, 
                   bgb_ref, bgb_tier_2 ):

    '''
    fire_periodicity: how often fires are used to destroy biomass
    fire_used: boolean, front-end input, states whether fire is used
    cf: taken from IPCC A871 matching vegetation type
    ef_methane: from IPCC A871 matching vegetation type
    ef_nitrous: from IPCC A871 matching vegetation type
    percentage_biomass_burnt: front-end input, between 0 and 1, states how much of the biomass is burnt
    '''

    def mass_comparison(mass_start, mass_end, time_impl, time_cap, rate_coefficient):
        if mass_end > mass_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)
    
    if fire_periodicity > (time_impl + time_cap) or not fire_used:  
        return 0
    else:
        degradation_level_start = degradation_level_start_ref if not degradation_level_start_tier_2 else degradation_level_start_tier_2
        degradation_level_end = degradation_level_end_ref if not degradation_level_end_tier_2 else degradation_level_end_tier_2
        agb = agb_ref if not agb_tier_2 else agb_tier_2
        bgb = bgb_ref if not bgb_tier_2 else bgb_tier_2

        tot_biomass = agb + bgb

        biomass_start = tot_biomass * (1 - degradation_level_start)
        biomass_end = tot_biomass * (1 - degradation_level_end)
        
        kg_methane = 2 * (min(biomass_start, biomass_end) * (time_cap + time_impl) + abs(biomass_start - biomass_end) * mass_comparison(biomass_start, biomass_end, time_impl, time_cap, rate_coefficient)) * cf * ef_methane * percentage_biomass_burnt / fire_periodicity
        kg_nitrous = 2 * (min(biomass_start, biomass_end) * (time_cap + time_impl) + abs(biomass_start - biomass_end) * mass_comparison(biomass_start, biomass_end, time_impl, time_cap, rate_coefficient)) * cf * ef_nitrous * percentage_biomass_burnt / fire_periodicity

        tonnes_co2 = (kg_nitrous * nitrous_constant + kg_methane * methane_constant)/1000

        return tonnes_co2 * area_end

def calculate_emissions(area_start, area_w, area_wo, time_impl, time_cap, rate_type_w, rate_type_wo, rate_coefficient_w, rate_coefficient_wo, 
                    nitrous_constant, methane_constant, degradation_level_w_ref, degradation_level_w_tier_2, 
                    degradation_level_wo_ref, degradation_level_wo_tier_2, degradation_level_start_ref, degradation_level_start_tier_2,
                    agb_ref, agb_tier_2, bgb_ref, bgb_tier_2, litter_ref, litter_tier_2, deadwood_ref, deadwood_tier_2, 
                    socref, soc_tier_2, luf_default, luf_start_tier_2, luf_end_w_tier_2, luf_end_wo_tier_2, fire_periodicity_w,
                    fire_periodicity_wo, fire_used_w, fire_used_wo, percentage_biomass_burnt_w, percentage_biomass_burnt_wo, 
                    cf, ef_methane, ef_nitrous):

    '''
    ----- GENERAL PARAMETERS FRONT END INPUTS, FROM MODULE OR GENERAL DESCRIPTION -----
    area_start
    area_w 
    area_wo
    time_impl
    time_cap
    rate_type_w
    rate_type_wo
    rate_coefficient_w
    rate_coefficient_wo
    nitrous_constant
    methane_constant

    ----- BIOMASS EMISSIONS -----
    degradation_level_w_ref: match degradation level end_w string to list! O7-P13
    degradation_level_w_tier_2: tier 2 value, expects Float or None
    degradation_level_wo_ref: match degradation level end_wo string to list! O7-P13
    degradation_level_wo_tier_2: tier 2 value, expects Float or None
    degradation_level_start_ref: match degradation level start string to list! O7-P13
    degradation_level_start_tier_2: tier 2 value, expects Float or None
    agb_ref: if TYPE_VEGETATION == Mangrove Forest, match clim_moist to IPCC A1502, else match CONTINENT and TYPE OF VEGETATION to IPCC A591 and multiply by 0.47 ---> maybe send a tuple, with true false?
    agb_tier_2: tier 2 value, expects Float or None
    bgb_ref: COMPLICATO
    bgb_tier_2: tier 2 value, expects Float or None

    ----- DOM EMISSIONS -----
    litter_ref: if VEGETATION_TYPE == Mangrove Forest match clim_moist to IPCC A1502 else match VEGETATION_TYPE to IPCC A643
    litter_tier_2: tier 2 value, expects Float or None
    deadwood_ref: if VEGETATION_TYPE == Mangrove Forest match clim_moist to IPCC A1502 else match VEGETATION_TYPE to IPCC A643
    deadwood_tier_2: tier 2 value, expects Float or None
    socref
    soc_tier_2: tier 2 value, expects Float or None
    luf_default: 1 DEFAULT VALUE IS ALWAYS 1
    luf_start_tier_2: tier 2 value, expects Float or None
    luf_end_w_tier_2: tier 2 value, expects Float or None
    luf_end_wo_tier_2: tier 2 value, expects Float or None

    ----- FIRE EMISSIONS -----
    fire_periodicity_w: front end input
    fire_periodicity_wo: front end input
    fire_used_w: front end input, expects True or False
    fire_used_wo: front end input, expects True or False
    percentage_biomass_burnt_w: front end input
    percentage_biomass_burnt_wo: front end input
    cf: taken from IPCC A871 matching vegetation type
    ef_methane: from IPCC A871 matching vegetation type and corresponding column
    ef_nitrous: from IPCC A871 matching vegetation type and corresponding column
    
    
    
    '''
    
    biomass_w = total_biomass_emissions(area_start, area_w, degradation_level_w_ref, degradation_level_w_tier_2, 
                            degradation_level_start_ref, degradation_level_start_tier_2, agb_ref, agb_tier_2, 
                            bgb_ref, bgb_tier_2 )
    biomass_wo = total_biomass_emissions(area_start, area_wo, degradation_level_wo_ref, degradation_level_wo_tier_2, 
                            degradation_level_start_ref, degradation_level_start_tier_2, agb_ref, agb_tier_2, 
                            bgb_ref, bgb_tier_2 )

    dom_w = dom_emissions(area_w, degradation_level_w_ref, degradation_level_w_tier_2, 
                degradation_level_start_ref, degradation_level_start_tier_2, litter_ref, litter_tier_2,
                deadwood_ref, deadwood_tier_2 )
    dom_wo = dom_emissions(area_wo, degradation_level_wo_ref, degradation_level_wo_tier_2, 
                degradation_level_start_ref, degradation_level_start_tier_2, litter_ref, litter_tier_2,
                deadwood_ref, deadwood_tier_2 )
    
    soc_w = soc_emissions(area_w, time_impl, time_cap, rate_type_w, rate_coefficient_w, socref, soc_tier_2,
                  luf_default, luf_start_tier_2, luf_end_w_tier_2)
    soc_wo = soc_emissions(area_wo, time_impl, time_cap, rate_type_wo, rate_coefficient_wo, socref, soc_tier_2,
                  luf_default, luf_start_tier_2, luf_end_wo_tier_2)

    fire_w = fire_emissions(area_w, time_impl, time_cap, rate_coefficient_w, methane_constant, nitrous_constant,  
                   fire_periodicity_w, fire_used_w, cf, ef_methane, ef_nitrous, percentage_biomass_burnt_w,
                   degradation_level_w_ref, degradation_level_w_tier_2, 
                   degradation_level_start_ref, degradation_level_start_tier_2, agb_ref, agb_tier_2, 
                   bgb_ref, bgb_tier_2 )
    fire_wo = fire_emissions(area_wo, time_impl, time_cap, rate_coefficient_wo, methane_constant, nitrous_constant,  
                   fire_periodicity_wo, fire_used_wo, cf, ef_methane, ef_nitrous, percentage_biomass_burnt_wo,
                   degradation_level_wo_ref, degradation_level_wo_tier_2, 
                   degradation_level_start_ref, degradation_level_start_tier_2, agb_ref, agb_tier_2, 
                   bgb_ref, bgb_tier_2 )

    total_w = biomass_w + dom_w + soc_w + fire_w
    total_wo = biomass_wo + dom_wo + soc_wo + fire_wo

    CIAO = 2
    return (total_w, total_wo, total_w-total_wo)

ao = calculate_emissions(400, 400, 400, 20, 9, 'D', 'D', 0.5, 0.5, 265, 28, 0.8, None, 0.4, None, 0.4, None, 86.592, None, 42.43008, None, 0.7, None, 10.7, None, 46, None, 1, None, None, None, 15, 5, True, True, 0.5, 0.2, 0.32, 6.8, 0.2)

print(ao)