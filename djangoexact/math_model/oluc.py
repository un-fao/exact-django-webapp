import math

def calculate_w_wo_balance(initial_lu_biomass, final_lu_biomass, initial_lu_biomass_tier_2, final_lu_biomass_tier_2,
    socref, initial_flu, final_flu, initial_soc_tier_2, final_soc_tier_2, 
    c_n_ratio, moisture_emission_factor,combustion_factor, emission_factor_nitrous, emission_factor_methane,nitrous_constant, methane_constant,fire_bool,
    time_impl, time_cap, rate_type_w, rate_coefficient_w, rate_type_wo, rate_coefficient_wo, area_w, area_wo):

    """
    INPUTS FOR OTHER LUC CALCULATION

    ======  BIOMASS CALCULATION ========
    initial_lu_biomass: TABLE 5.9 IPCC A1521 matching climate region on rows and initial LU on columns
    final_lu_biomass: TABLE 5.9 IPCC A686 matching climate region on rows and final LU on columns
    initial_lu_biomass_tier_2: TIER 2 value, expects eith None or Float 
    final_lu_biomass_tier_2: TIER 2 value, expects either None or Float

    ======  SOC CALCULATION ========
    socref: standard value present in list I14
    initial_flu: TABLE 5.5 IPCC A1689 matching climate region on rows and initial LU on columns
    final_flu: TABLE 5.5 IPCC A854 matching climate region on rows and final LU on columns
    initial_soc_tier_2 : TIER 2 value, expects either None or Float
    final_soc_tier_2: TIER 2 value, expects either None or Float

    ====== FIRE CALCULATION =========
    c_n_ratio: IPCC A912 if initial_lu == Grassland 15, else 10
    moisture_emission_factor: TABLE 11.1 IPCC FROM 99 TO 101 matching moisture_type to rows
    combustion_factor : Search for land converted in Combustion factor values for fires in a range of vegetation types, table IPCC A1473, cf value
    emission_factor_nitrous : Search for land converted in Combustion factor values for fires in a range of vegetation types, table IPCC A1473, n2o value
    emission_factor_methane: Search for land converted in Combustion factor values for fires in a range of vegetation types, table IPCC A1473, ch4 value 
    nitrous_constant: Front end input 1.3 in Excel
    methane_constant: Front end input 1.3 in Excel
    fire_bool: states whether fire was used, Front end input

    ====== GENERAL INFO ========
    time_impl: time of implementation of the activity
    time_cap: time of capitalization of the activity
    rate_type_w: accepts one of 'L', 'I', 'E'
    rate_coefficient_w: taken searching for rate type in list K49
    rate_type_wo: accepts one of 'L', 'I', 'E'
    rate_coefficient_wo: taken searching for rate type in list K49
    area_w: area affected with the Project
    area_wo: area affected without the Project
    
    """

    emission_w = single_emissions(initial_lu_biomass, initial_lu_biomass_tier_2, final_lu_biomass, final_lu_biomass_tier_2,
        c_n_ratio, moisture_emission_factor,combustion_factor, emission_factor_nitrous, emission_factor_methane,nitrous_constant, methane_constant,fire_bool,
        socref, initial_flu, final_flu, initial_soc_tier_2, final_soc_tier_2, area_w, time_impl, time_cap, rate_type_w, rate_coefficient_w)

    emission_wo = single_emissions(initial_lu_biomass, initial_lu_biomass_tier_2, final_lu_biomass, final_lu_biomass_tier_2,
        c_n_ratio, moisture_emission_factor,combustion_factor, emission_factor_nitrous, emission_factor_methane,nitrous_constant, methane_constant,fire_bool,
        socref, initial_flu, final_flu, initial_soc_tier_2, final_soc_tier_2, area_wo, time_impl, time_cap, rate_type_wo, rate_coefficient_wo)

    return (emission_w, emission_wo, emission_w - emission_wo)

def single_emissions(initial_lu_biomass, initial_lu_biomass_tier_2, final_lu_biomass, final_lu_biomass_tier_2,
    c_n_ratio, moisture_emission_factor,combustion_factor, emission_factor_nitrous, emission_factor_methane,nitrous_constant, methane_constant,fire_bool,
    socref, initial_flu, final_flu, initial_soc_tier_2, final_soc_tier_2, area, time_impl, time_cap, rate_type, rate_coefficient):

    biomass_emissions = biomass_change(initial_lu_biomass, initial_lu_biomass_tier_2, final_lu_biomass, final_lu_biomass_tier_2, area)
    soc_component = soc_emissions(socref, initial_flu, final_flu, initial_soc_tier_2, final_soc_tier_2, time_impl, time_cap, rate_type, rate_coefficient, area)
    fire = fire_n_mineralised (socref,initial_flu,final_flu, initial_soc_tier_2,final_soc_tier_2,initial_lu_biomass,initial_lu_biomass_tier_2,c_n_ratio, 
                moisture_emission_factor,combustion_factor, emission_factor_nitrous, emission_factor_methane,nitrous_constant, methane_constant,  area, fire_bool)

    return biomass_emissions + fire + soc_component


def biomass_change (initial_lu_biomass, initial_lu_biomass_tier_2, final_lu_biomass, final_lu_biomass_tier_2, area):

    initial_biomass = initial_lu_biomass if not initial_lu_biomass_tier_2 else initial_lu_biomass_tier_2
    final_biomass = final_lu_biomass if not final_lu_biomass_tier_2 else final_lu_biomass_tier_2

    delta_c_biomass = (final_biomass - initial_biomass) * (-44/12)

    return delta_c_biomass * area

def fire_n_mineralised ( socref,initial_flu,final_flu, initial_soc_tier_2,final_soc_tier_2,initial_lu_biomass,initial_lu_biomass_tier_2,c_n_ratio, 
    moisture_emission_factor,combustion_factor, emission_factor_nitrous, emission_factor_methane,nitrous_constant, methane_constant,  area, fire_bool):

    initial_soc = socref * initial_flu if not initial_soc_tier_2 else initial_soc_tier_2
    final_soc = socref * final_flu if not final_soc_tier_2 else final_soc_tier_2

    delta_c_soc = (final_soc - initial_soc)/20

    initial_biomass = initial_lu_biomass if not initial_lu_biomass_tier_2 else initial_lu_biomass_tier_2
    fire_mb = initial_biomass / 0.4
    fsom = 0 if delta_c_soc >= 0 else - (1000 * delta_c_soc)/c_n_ratio

    kg_methane_fire = fire_mb * combustion_factor * emission_factor_methane if fire_bool else 0
    kg_nitrous_fire =  initial_biomass * 2.5 * combustion_factor * emission_factor_nitrous if fire_bool else 0

    kg_nitrous_soil = fsom * moisture_emission_factor * (44/28)

    methane_emissions = kg_methane_fire * methane_constant
    nitrous_emissions = (kg_nitrous_fire + kg_nitrous_soil) * nitrous_constant

    total_fire = (methane_emissions + nitrous_emissions)/1000

    return total_fire * area

def soc_emissions (socref, initial_flu, final_flu, initial_soc_tier_2, final_soc_tier_2, time_impl, time_cap, rate_type, rate_coefficient, area):

    initial_soc = socref * initial_flu if not initial_soc_tier_2 else initial_soc_tier_2
    final_soc = socref * final_flu if not final_soc_tier_2 else final_soc_tier_2

    delta_c_soc = (final_soc - initial_soc)/20
    delta_co2_soc = delta_c_soc * (-44/12)

    return calculate_soil_emissions(time_impl, time_cap, rate_type, rate_coefficient, area, delta_co2_soc, delta_c_soc)


def calculate_soil_emissions(time_impl, time_cap, rate_type, rate_of_change_soil, area_defo, delta_co2_mineral_per_ha_per_yr, delta_c_mineral_per_ha):

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

    time_tot = time_impl + time_cap

    calculated = (delta_co2_mineral_per_ha_per_yr * soil_rate_immediate(area_defo, time_tot)) if rate_type == "I" else (delta_co2_mineral_per_ha_per_yr * soil_rate_other(time_tot, time_impl, area_defo, rate_of_change_soil, rate_type))        
    tabular = (area_defo * delta_co2_mineral_per_ha_per_yr * 20)
    
    return tabular if abs(calculated) >= abs(tabular) else calculated

    