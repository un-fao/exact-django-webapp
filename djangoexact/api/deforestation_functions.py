import math

def GHG_emissions(ha_start, ha_end_w, ha_end_wo, time_impl, time_cap, rate_type_soil, rate_of_change_soil, biomass_final_1_year_t_per_ha, 
                  biomass_final_1_year_t_per_ha_tier_2, nitrous, methane, fire_bool, n2o_vegetation, ch4_vegetation, 
                  cf_vegetation, moisture_emission_factor, litter, litter_tier_2, dw, 
                  dw_tier_2, hwp_before_t_dm_per_ha, mangrove_factor, bgb_t_c_per_ha_tier_2, agb_t_c_per_ha_tier_2, flu,
                  agb_t_dm_per_ha_default, bgb_t_dm_per_ha_default_input_parameter, c_n_ratio, soc_after_defo_tier_2, soc_reference, soc_reference_tier_2):

    """
    This function calculates GHG emission
    Inputs ----->  ha_start : hectars at the start
                   ha_end_w : hectars at the end with the project
                   ha_end_wo : hectars at the end without the project
                   time_impl : implementation time
                   time_cap : capitalization time
                   rate_type_soil : rate of change type soil (front end input I/D/E lookup in table present in list expects one of: Linear, Immediate, Exponential)
                   rate_of_change_soil : rate of change for soil (front end input I/D/E lookup in table present in list expects one of: 1/0.5/0.78)
                   biomass_final_1_year_t_per_ha : TABLE 5.9 (IPCC A686) matching Climate Region and Final Use after Deforestation
                   biomass_final_1_year_t_per_ha_tier_2 : tier 2 value, assignment on front end, expects FLOAT or NONE
                   nitrous : Front end input (pre-populated) 1.3 in Excel
                   methane : Front end input (pre-populated) 1.3 in Excel
                   fire_bool : Boolean which represents whether fire has been used in the deforestation process, expects TRUE or FALSE
                   n2o_vegetation : n2o factor of vegetation for combustion, TABLE 2.6 (A871 in IPCC)
                   ch4_vegetation : ch4 factor of vegetation for combustion, TABLE 2.6 (A871 in IPCC)
                   cf_vegetation : cf factor of vegetation for combustion, TABLE 2.6 (A871 in IPCC)
                   moisture_emission_factor : Table 11.1, page 11.11 (B99) obtained matching moisture to row
                   litter : if Mangrove Forest search conc(climate + moist_type) in Data on Mangroves (A1502) else search type of deforestation in Table 2.2 (A640)
                   litter_tier_2 : tier 2 value, assignment on front end, excepts FLOAT value or NONE
                   dw : if Mangrove Forest search conc(climate + moist_type) in Data on Mangroves (A1502) else search type of deforestation in Table 2.2 (A640)
                   dw_tier_2 : tier 2 value, assignment on front end, excepts FLOAT value or NONE
                   hwp_before_t_dm_per_ha : assignment on front end E11
                   mangrove_factor : if vegetation type is Mangrove 0.451 else 0.47 (add table in DB as it may change)
                   bgb_t_c_per_ha_tier_2 : tier 2 value, assignment on front end, excepts FLOAT value or NONE
                   agb_t_c_per_ha_tier_2 : tier 2 value, assignment on front end, excepts FLOAT value or NONE
                   flu : Relative stock change factor for land use (FLU) table 5.5 (A854) matching climate and type of deforestation
                   agb_t_dm_per_ha_default : if Mangrove Forest search conc(climate + moist_type) in Data on Mangroves (A1502) else search type of deforestation in Table 4.12 (A590)
                   bgb_t_dm_per_ha_default_input_parameter : if Mangrove Forest search conc(climate + moist_type) in Data on Mangroves (A1502) else other logic, see for query L9 in Defo, multiplied by agb_t_dm_per_ha_default in package
                   c_n_ratio : Table Default C:N ratio of soil organic matter (A912) SEEMS TO NOT HAVE NECESSARY LOGIC IN EXCEL (QUESTION)
                   soc_after_defo_tier_2 : tier 2 value, assignment on front end, excepts FLOAT value or NONE
                   soc_reference : if Mangrove Forest search conc(climate + moist_type) in Data on Mangroves (A1502) else SOCRef list I14 fixed value 70
                   soc_reference_tier_2 : tier 2 value, assignment on front end, excepts FLOAT value or NONE


    Output -----> a tuple containing: Total Emissions without Project, Total Emissions with Project, Balance (Total with - Total with out)
    """
    bgb_t_dm_per_ha_default = bgb_t_dm_per_ha_default_input_parameter * agb_t_dm_per_ha_default

    agb_t_c_per_ha = agb_t_dm_per_ha_default * mangrove_factor if not agb_t_c_per_ha_tier_2 else agb_t_c_per_ha_tier_2
    bgb_t_c_per_ha = bgb_t_dm_per_ha_default * mangrove_factor if not bgb_t_c_per_ha_tier_2 else bgb_t_c_per_ha_tier_2

    hwp_before_t_c_per_ha = agb_t_dm_per_ha_default * mangrove_factor if hwp_before_t_dm_per_ha > agb_t_dm_per_ha_default else hwp_before_t_dm_per_ha * mangrove_factor

    if dw_tier_2 : dw = dw_tier_2
    if litter_tier_2 : litter = litter_tier_2

    if soc_reference_tier_2: soc_reference = soc_reference_tier_2
    delta_c_mineral_per_ha = soc_reference * flu - soc_reference if not soc_after_defo_tier_2 else soc_after_defo_tier_2 - soc_reference

    fire_t_dm_per_ha = agb_t_dm_per_ha_default - hwp_before_t_dm_per_ha if fire_bool else 0
    # THIS IS CORRECT

    biomass_forest_agb_bgb_t_c_per_ha = agb_t_c_per_ha + bgb_t_c_per_ha - hwp_before_t_c_per_ha

    biomass_forest_dom_t_c_per_ha = litter + dw

    som_luc_kg_n_per_year = 0 if delta_c_mineral_per_ha >= 0 else  - (delta_c_mineral_per_ha/(20*c_n_ratio))*1000

    n2o_n_conversion_factor = 44/28
    soil_kg_n2o = moisture_emission_factor * n2o_n_conversion_factor * som_luc_kg_n_per_year

    fire_kg_n2o = fire_t_dm_per_ha * n2o_vegetation * cf_vegetation if fire_bool else 0
    fire_kg_ch4 = fire_t_dm_per_ha * ch4_vegetation * cf_vegetation if fire_bool else 0 
    # ERROR WITH CH4 VEGETATION AND CF VEGETATION INPUT (I GUESS, AS FIRE_T_DM IS CORRECT)

    delta_co2_mineral_per_ha_per_yr = delta_c_mineral_per_ha * (-44/(12*20))

    biomass_forest_agb_bgb_t_co2_per_ha = biomass_forest_agb_bgb_t_c_per_ha * (44/12)

    if biomass_final_1_year_t_per_ha_tier_2: biomass_final_1_year_t_per_ha = biomass_final_1_year_t_per_ha_tier_2

    biomass_forest_dom_t_co2_per_ha = biomass_forest_dom_t_c_per_ha * (44/12)

    total_ch4_n2o_per_ha = (fire_kg_ch4 * methane + (fire_kg_n2o + soil_kg_n2o) * nitrous)/1000
    print(total_ch4_n2o_per_ha)

    area_defo_wo = 0 if ha_end_wo > ha_start else ha_start - ha_end_wo
    area_defo_w = 0 if ha_end_w > ha_start else ha_start - ha_end_w

    biomass_loss_wo = biomass_forest_agb_bgb_t_co2_per_ha * area_defo_wo
    biomass_loss_w = biomass_forest_agb_bgb_t_co2_per_ha * area_defo_w
    
    biomass_gain_wo = 0 if biomass_loss_wo == 0 else - (biomass_final_1_year_t_per_ha * area_defo_wo * (44/12))
    biomass_gain_w = 0 if biomass_loss_w == 0 else - (biomass_final_1_year_t_per_ha * area_defo_w * (44/12))

    dom_loss_wo = biomass_forest_dom_t_co2_per_ha * area_defo_wo
    dom_loss_w = biomass_forest_dom_t_co2_per_ha * area_defo_w

    soil_wo = soil_emissions(time_impl, time_cap, rate_type_soil, rate_of_change_soil, area_defo_wo, delta_co2_mineral_per_ha_per_yr, delta_c_mineral_per_ha)
    soil_w = soil_emissions(time_impl, time_cap, rate_type_soil, rate_of_change_soil, area_defo_w, delta_co2_mineral_per_ha_per_yr, delta_c_mineral_per_ha)

    fire_fsom_N_wo = total_ch4_n2o_per_ha * area_defo_wo
    fire_fsom_N_w = total_ch4_n2o_per_ha * area_defo_w
    # print(fire_fsom_N_w)
    # HERE IT IS NOT CORRECT
    # print(total_ch4_n2o_per_ha)
    # print(fire_fsom_N_w)

    total_wo = biomass_loss_wo + biomass_gain_wo + dom_loss_wo + soil_wo + fire_fsom_N_wo 
    total_w = biomass_loss_w + biomass_gain_w + dom_loss_w + soil_w + fire_fsom_N_w 


    total_defo = total_w - total_wo

    return (total_w, total_wo, total_defo)

def soil_emissions(time_impl, time_cap, rate_type, rate_of_change_soil, area_defo, delta_co2_mineral_per_ha_per_yr, delta_c_mineral_per_ha):

    time_tot = time_impl + time_cap

    comparison_term_1 = (delta_co2_mineral_per_ha_per_yr * soil_rate_immediate(area_defo, time_tot)) if rate_type == "I" else (delta_co2_mineral_per_ha_per_yr * soil_rate_other(time_tot, time_impl, area_defo, rate_of_change_soil, rate_type))        
    comparison_term_2 = (area_defo * delta_c_mineral_per_ha * (-44/12))
    
    return comparison_term_2 if abs(comparison_term_1) >= abs(comparison_term_2) else comparison_term_1

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
        return time_tot - 20 + 0.217 * time_impl * (math.exp(4.606 * (20 - time_tot/time_impl)) - 1)
    else:
        return pow(time_tot - 20, 2) * (0.5/time_impl)


# ao = GHG_emissions(12, 11, 12, 1, 1, 'D', 0.5, 4.7, None, 265.0, 28.0, True, 0.26, 4.7, 0.45, 0.005, 2.9, None, 36.8, None, 12.0, 0.47, None, None, 0.77, 180.0, 0.22, 15, None, 20, None)
