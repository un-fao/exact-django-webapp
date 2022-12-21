import math

def afforestation(ha_w, ha_wo, time_impl, time_cap, initial_biomass, initial_biomass_tier_2, fire_bool, nitrous, methane, 
                    emission_factor_ch4, emission_factor_n2o, combusted_fraction, rate_type, rate_of_change_soil,
                    flu, soc_default, soc_tier_2, dead_wood_c_default,
                    dead_wood_c_tier_2, litter_c_default, litter_c_tier_2, agb_secondary_dm_before_20_years, agb_secondary_dm_after_20_years, 
                    bgb_secondary_dm_before_20_years_param, bgb_secondary_dm_after_20_years_param, agb_secondary_c_before_20_years_tier_2, 
                    agb_secondary_c_after_20_years_tier_2, bgb_secondary_c_before_20_years_tier_2, bgb_secondary_c_after_20_years_tier_2,
                    reference_carbon_stocks_tier_2, abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125
                    ):
    """"            
                   GENERAL PROJECT PARAMETERS
                   ha_start : hectars at the start
                   ha_w : hectars at the end with the project
                   ha_wo : hectars at the end without the project
                   time_impl : implementation time
                   time_cap : capitalization time
                   initial_biomass : search for climate region in rows and converted_land in table IPCC A1521 (Biomass above + below to use for Afforestation)
                   initial_biomass_tier_2 : tier 2 value, expects either Float or None

                   FIRE COMPUTATION PARAMETERS
                   fire_bool : whether fire was used, expects True or False
                   nitrous : Front end input 1.3 in Excel
                   methane : Front end input 1.3 in Excel
                   emission_factor_ch4 : Search for land converted in Combustion factor values for fires in a range of vegetation types, table IPCC A1473, ch4 value 
                   emission_factor_n2o : Search for land converted in Combustion factor values for fires in a range of vegetation types, table IPCC A1473, n2o value
                   combusted_fraction : Search for land converted in Combustion factor values for fires in a range of vegetation types, table IPCC A1473, cf value

                   SOIL COMPUTATION PARAMETERS
                   rate_type : expects one of I / E / D 
                   rate_of_change_soil : taken searching for rate type in list K49
                   flu : taken from table IPCC 1689 matching climate region on rows and converted land on columns
                   soc_default : SOCref
                   soc_tier_2 : tier 2 value, expects either Float input from user or None


                   DOM COMPUTATION PARAMETERS
                   dead_wood_c_default : taken searching for final land use in TABLE 2.2 (A643) and dead wood column
                   dead_wood_c_tier_2 : tier 2 value, expects either Float input from user or None
                   litter_c_default: taken searching for final land use in TABLE 2.2 (A643) and litter column
                   litter_c_tier_2 : tier 2 value, expects either Float input from user or None

                   BIOMASS COMPUTATION PARAMETERS
                   agb_secondary_dm_before_20_years : match final land use+continent to IPCC C924 column 3
                   agb_secondary_dm_after_20_years : match final land use+continent to IPCC C924 column 2
                   bgb_secondary_dm_before_20_years : if agb_secondary_dm_before_20_years < 125 or < 75 match continent and final land use to IPCC 618 \\\\\ TO MULTIPLY BY agb_secondary_dm_before_20_years
                   bgb_secondary_dm_after_20_years : if agb_secondary_dm_after_20_years < 125 or < 75 match continent and final land use to IPCC 618 \\\\ TO MULTIPLY BY agb_secondary_dm_after_20_years
                   agb_secondary_c_before_20_years_tier_2 : tier 2 value, expects either Float input from user or None
                   agb_secondary_c_after_20_years_tier_2 : tier 2 value, expects either Float input from user or None
                   bgb_secondary_c_before_20_years_tier_2 : tier 2 value, expects either Float input from user or None
                   bgb_secondary_c_after_20_years_tier_2 : tier 2 value, expects either Float input from user or None
                   reference_carbon_stocks_tier_2 : tier 2 value, expects either Float input from user or None

                   # TO ADD TO INPUTS
                   abg_biomass : above ground bio-mass A591 match region and final land use
                   rate_bgb_agb_s_125 : ratio of below ground bio to above ground bio A618 match region and final land use - smaller 125
                   rate_bgb_agb_b_125 : ratio of below ground bio to above ground bio A618 match region and final land use - larger 125

    """

    biomass_converted = initial_biomass_tier_2 if initial_biomass_tier_2 else initial_biomass

    # Biomass Gain 
    max_co2_agb_bgb = reference_carbon_stocks_tier_2 * 44/12 if reference_carbon_stocks_tier_2 else max_co2_above_below_ground(abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125)
    
    agb_secondary_c_before_20_years = agb_secondary_dm_before_20_years * 0.47 if not agb_secondary_c_before_20_years_tier_2 else agb_secondary_c_before_20_years_tier_2
    agb_secondary_c_after_20_years = agb_secondary_dm_after_20_years * 0.47 if not agb_secondary_c_after_20_years_tier_2 else agb_secondary_c_after_20_years_tier_2

    bgb_secondary_dm_before_20_years = bgb_secondary_dm_before_20_years_param * agb_secondary_dm_before_20_years
    bgb_secondary_dm_after_20_years = bgb_secondary_dm_after_20_years_param * agb_secondary_dm_after_20_years


    bgb_secondary_c_before_20_years = bgb_secondary_dm_before_20_years * 0.47 if not bgb_secondary_c_before_20_years_tier_2 else bgb_secondary_c_before_20_years_tier_2
    bgb_secondary_c_after_20_years = bgb_secondary_dm_after_20_years * 0.47 if not bgb_secondary_c_after_20_years_tier_2 else bgb_secondary_c_after_20_years_tier_2

    tot_biomass_growth_after_20_years = bgb_secondary_c_after_20_years + agb_secondary_c_after_20_years
    tot_biomass_growth_before_20_years = bgb_secondary_c_before_20_years + agb_secondary_c_before_20_years

    total_biomass_co2_annual_rate_wo = biomass_annual_rate_calculation(ha_wo, time_impl, time_cap, rate_type, rate_of_change_soil, tot_biomass_growth_before_20_years, tot_biomass_growth_after_20_years)
    total_biomass_co2_annual_rate_w = biomass_annual_rate_calculation(ha_w, time_impl, time_cap, rate_type, rate_of_change_soil, tot_biomass_growth_before_20_years, tot_biomass_growth_after_20_years)

    biomass_gain_wo = - max_co2_agb_bgb * ha_wo if total_biomass_co2_annual_rate_wo < ( - ( max_co2_agb_bgb * ha_wo)) else total_biomass_co2_annual_rate_wo
    biomass_gain_w = - max_co2_agb_bgb * ha_w if total_biomass_co2_annual_rate_w < ( - ( max_co2_agb_bgb * ha_w)) else total_biomass_co2_annual_rate_w
    
    # DOM Gain (Deadwood + Litter)
    dead_wood_c = dead_wood_c_tier_2 if dead_wood_c_tier_2 else dead_wood_c_default
    litter_c = litter_c_tier_2 if litter_c_tier_2 else litter_c_default
    dom_c = dead_wood_c + litter_c
    dom_co2 = dom_c * (-44/12)
    dom_emissions_w = dom_co2 * ha_w
    dom_emissions_wo = dom_co2 * ha_wo

    # Biomass Loss
    biomass_loss_wo = biomass_converted * ha_wo * (44/12)
    biomass_loss_w = biomass_converted * ha_w * (44/12)

    # Emissions due to soil
    soc_0 = soc_default if not soc_tier_2 else soc_tier_2
    soc = flu * soc_0
    delta_c_mineral_per_ha = soc_0 - soc

    # limited to 20 years
    delta_co2_mineral_per_ha_per_yr = delta_c_mineral_per_ha * (-44/12)/20


    soil_emission_w = soil_emissions(time_impl, time_cap, rate_type, rate_of_change_soil, ha_w, delta_co2_mineral_per_ha_per_yr, delta_c_mineral_per_ha)
    soil_emission_wo = soil_emissions(time_impl, time_cap, rate_type, rate_of_change_soil, ha_wo, delta_co2_mineral_per_ha_per_yr, delta_c_mineral_per_ha)

    # Emissions due to fire
    combustion_mass = biomass_converted / 0.4 
    biomass_ch4 = combustion_mass * combusted_fraction * emission_factor_ch4
    biomass_n2o = combustion_mass * combusted_fraction * emission_factor_n2o
    biomass_tco2 = (biomass_ch4 * methane + biomass_n2o * nitrous) / 1000

    fire_emissions_w = ha_w * biomass_tco2 if fire_bool else 0
    fire_emissions_wo = ha_wo * biomass_tco2 if fire_bool else 0


    # Results COMPUTE TOTAL W AND WO HERE
    total_w = biomass_gain_w + dom_emissions_w + biomass_loss_w + soil_emission_w + fire_emissions_w
    total_wo = biomass_gain_wo + dom_emissions_wo + biomass_loss_wo + soil_emission_wo + fire_emissions_wo


    balance = total_w - total_wo


    return total_w, total_wo, balance


######### FUNCTIONS FOR MAX AGB + BGB CALCULATION BASED ON REFERENCE CARBON STOCKS
def max_co2_above_below_ground(parametro_1, parametro_2, parametro_3):

    if parametro_1 <= 125:
        return (parametro_1 + parametro_1 * parametro_2) * 0.47 * 44/12
    else:
        return (parametro_1 + parametro_1 * parametro_3) * 0.47 * 44/12




######### FUNCTIONS FOR BIOMASS ANNUAL RATE CALCULATION ######################
def biomass_annual_rate_calculation (area, time_impl, time_cap, rate_type, rate_of_change_soil, tot_biomass_growth_before_20_years, tot_biomass_growth_after_20_years):

    time_tot = time_impl + time_cap

    component_before_20_years = area * tot_biomass_growth_before_20_years * min(20, time_tot) if rate_type == 'I' else tot_biomass_growth_before_20_years * area * time_component_before_20(time_tot, time_impl, rate_of_change_soil, rate_type)
    component_after_20_years = tot_biomass_growth_after_20_years * area * (time_tot - min(20, time_tot)) if rate_type == 'I' else tot_biomass_growth_after_20_years * area * time_component_after_20(time_tot, time_impl, rate_of_change_soil, rate_type)

    print(area * time_component_after_20(time_tot, time_impl, rate_of_change_soil, rate_type))

    return (component_before_20_years + component_after_20_years) * (-44/12)

# FOR CALCULATION BEFORE 20 YEARS ============

# SAME AS SOIL EMISSION MIDDLE IF OTHER, ALSO CALLS OUTER IF OTHER ##############
def time_component_before_20(time_tot, time_impl, rate_of_change_soil, rate_type):
    
    if time_tot > time_impl + 20:
        return 20
    else:
        if time_tot < 20:
            return time_impl * rate_of_change_soil + time_tot - time_impl
        else: 
            return min(20, time_impl) * rate_of_change_soil + time_tot - min(20, time_impl) - outer_if_other(rate_type, time_tot, time_impl)

# FOR CALCULATION AFTER 20 YEARS
def time_component_after_20(time_tot, time_impl, rate_of_change_soil, rate_type):

    if time_tot > time_impl + 20:
        return time_impl * rate_of_change_soil + time_tot - time_impl - 20
    else:
        if time_tot < 20:
            return 0
        else: 
            return outer_if_other_after_20(rate_type, time_tot, time_impl)

def outer_if_other_after_20(rate_type, time_tot, time_impl):

    if rate_type == "E":
        return time_tot - 20 + 0.217 * time_impl * (math.exp(4.606 * ((20 - time_tot)/time_impl)) - 1)
    else:
        return pow(time_tot - 20, 2) * (0.5/time_impl)


######## FUNCTIONS FOR SOIL EMISSION CALCULATION
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
        return time_tot - 20 + 0.217 * time_impl * (math.exp(4.606 * ((20 - time_tot)/time_impl)) - 1)
    else:
        return pow(time_tot - 20, 2) * (0.5/time_impl)
