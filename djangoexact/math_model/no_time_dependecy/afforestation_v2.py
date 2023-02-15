import math 
import matplotlib.pyplot as plt
from affo_graphs import yearly_emissions, yearly_breakdown, show_before_after_20, make_plots

def calculate_emissions(ha_w, ha_wo, time_impl, time_cap, initial_biomass, initial_biomass_tier_2, fire_bool, nitrous, methane, 
                    emission_factor_ch4, emission_factor_n2o, combusted_fraction, rate_type, rate_of_change_soil,
                    flu, soc_default, soc_tier_2, dead_wood_c_default,
                    dead_wood_c_tier_2, litter_c_default, litter_c_tier_2, agb_secondary_dm_before_20_years, agb_secondary_dm_after_20_years, 
                    bgb_secondary_dm_before_20_years_param, bgb_secondary_dm_after_20_years_param, agb_secondary_c_before_20_years_tier_2, 
                    agb_secondary_c_after_20_years_tier_2, bgb_secondary_c_before_20_years_tier_2, bgb_secondary_c_after_20_years_tier_2,
                    reference_carbon_stocks_tier_2, abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125
                    ):

                    """"            
                        GENERAL PROJECT PARAMETERS
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
                    
                    units_per_year_w_before_20, units_per_year_w_after_20, years_w = calculate_unit_distribution(rate_type, ha_w, time_impl, time_cap)
                    
                    units_per_year_wo_before_20, units_per_year_wo_after_20, years_wo = calculate_unit_distribution(rate_type, ha_wo, time_impl, time_cap)

                    # CALCULATE NON TIME DEPENDENT COMPONENT, WHICH HAS TO THEN BE SPLIT YEARLY THROUGHOUT THE IMPLEMENTATION TIME (dom, bio_loss, fire)
                    total_non_time_w, total_non_time_wo = afforestation_non_time_dependent(ha_w, ha_wo, initial_biomass, initial_biomass_tier_2, fire_bool, nitrous, methane, 
                                    emission_factor_ch4, emission_factor_n2o, combusted_fraction, dead_wood_c_default,
                                    dead_wood_c_tier_2, litter_c_default, litter_c_tier_2)


                    # COMPUTE YEARLY EMISSIONS FOR TIME DEPENDENT VARIABLES (bio_gain, soil)
                    total_time_dependent_w, total_time_dependent_wo = compute_yearly_time_dependent(units_per_year_w_before_20, units_per_year_w_after_20, units_per_year_wo_before_20, units_per_year_wo_after_20, years_w, ha_w, ha_wo, time_impl, time_cap, initial_biomass, initial_biomass_tier_2, fire_bool, nitrous, methane, 
                                        emission_factor_ch4, emission_factor_n2o, combusted_fraction, rate_type, rate_of_change_soil,
                                        flu, soc_default, soc_tier_2, dead_wood_c_default,
                                        dead_wood_c_tier_2, litter_c_default, litter_c_tier_2, agb_secondary_dm_before_20_years, agb_secondary_dm_after_20_years, 
                                        bgb_secondary_dm_before_20_years_param, bgb_secondary_dm_after_20_years_param, agb_secondary_c_before_20_years_tier_2, 
                                        agb_secondary_c_after_20_years_tier_2, bgb_secondary_c_before_20_years_tier_2, bgb_secondary_c_after_20_years_tier_2,
                                        reference_carbon_stocks_tier_2, abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125)


                    
                    total_w, total_wo = aggregate_emissions(total_non_time_w, total_non_time_wo, total_time_dependent_w, total_time_dependent_wo, time_impl)

                    # print('SOIL: {}'.format((sum([i[1] for i in total_time_dependent_w]))))
                    # print('BIOMASS GAIN: {}'.format((sum([i[0] for i in total_time_dependent_w]))))
                    # print('DOM: {}'.format(total_non_time_w[0]))
                    # print('FIRE: {}'.format(total_non_time_w[2]))
                    # print('BIOMASS LOSS: {}'.format(total_non_time_w[1]))

                    # for i, j in enumerate(units_per_year_w_before_20):
                    #     print('{}:{}'.format(i, j, units_per_year_w_after_20[i]))

                    #yearly_breakdown(total_non_time_w, total_time_dependent_w, time_impl, years_w)
                    make_plots(units_per_year_w_before_20, units_per_year_w_after_20, years_w, total_non_time_w, total_time_dependent_w, time_impl, total_w)

                    return sum(total_w), sum(total_wo), sum(total_w) - sum(total_wo)

def calculate_unit_distribution(rate_type, total_units, time_impl, time_cap):

    units_per_year = range(time_cap + time_impl)
    years = range(0, time_impl + time_cap)
    

    if rate_type == 'I':
        units_per_year = [total_units for i in units_per_year]
        to_subtract = [0 for i in range(20)]
        to_subtract.extend(units_per_year)
        result = [i-j for i, j in zip(units_per_year, to_subtract[0:len(units_per_year)])]
    if rate_type == 'D':
        coefficient = total_units/(time_impl + 1)
        units_per_year = [(i + 1) * coefficient if i <= time_impl else total_units for i in years]
        to_subtract = [0 for i in range(20)]
        to_subtract.extend(units_per_year)
        result = [i-j for i, j in zip(units_per_year, to_subtract[0:len(units_per_year)])]
    if rate_type == 'E':
        coefficient = (time_impl + 1)/math.log(total_units)
        units_per_year = [math.exp(coefficient * i) if i <= time_impl else total_units for i in years]

    return result, to_subtract[0:len(units_per_year)], years

def compute_yearly_time_dependent(units_per_year_w_before_20, units_per_year_w_after_20, units_per_year_wo_before_20, units_per_year_wo_after_20, years_w, ha_w, ha_wo, time_impl, time_cap, initial_biomass, initial_biomass_tier_2, fire_bool, nitrous, methane, 
                    emission_factor_ch4, emission_factor_n2o, combusted_fraction, rate_type, rate_of_change_soil,
                    flu, soc_default, soc_tier_2, dead_wood_c_default,
                    dead_wood_c_tier_2, litter_c_default, litter_c_tier_2, agb_secondary_dm_before_20_years, agb_secondary_dm_after_20_years, 
                    bgb_secondary_dm_before_20_years_param, bgb_secondary_dm_after_20_years_param, agb_secondary_c_before_20_years_tier_2, 
                    agb_secondary_c_after_20_years_tier_2, bgb_secondary_c_before_20_years_tier_2, bgb_secondary_c_after_20_years_tier_2,
                    reference_carbon_stocks_tier_2, abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125):

    # CALCULATE TIME DEPENDENT COMPONENT, TO WHICH WE ADD THE PREVIOUSLY CALCULATED NOT TIME DEPENDENT COMPONENT
    total_time_dependent_w = []
    total_time_dependent_wo = []

    for units_w_before_20, units_w_after_20, units_wo_before_20, units_wo_after_20, year in zip(units_per_year_w_before_20, units_per_year_w_after_20, units_per_year_wo_before_20, units_per_year_wo_after_20, years_w):
        total_w, total_wo = afforestation_time_dependent(units_w_before_20, units_w_after_20, units_wo_before_20, units_wo_after_20, time_impl, time_cap, rate_type, rate_of_change_soil,
                flu, soc_default, soc_tier_2, agb_secondary_dm_before_20_years, agb_secondary_dm_after_20_years, 
                bgb_secondary_dm_before_20_years_param, bgb_secondary_dm_after_20_years_param, agb_secondary_c_before_20_years_tier_2, 
                agb_secondary_c_after_20_years_tier_2, bgb_secondary_c_before_20_years_tier_2, bgb_secondary_c_after_20_years_tier_2,
                reference_carbon_stocks_tier_2, abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125, year <= 20)

        total_time_dependent_w.append(total_w)
        total_time_dependent_wo.append(total_wo)

    total_time_dependent_w, total_time_dependent_wo = verify_biomass(total_time_dependent_w, total_time_dependent_wo, ha_w, ha_wo, reference_carbon_stocks_tier_2, abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125)
    total_time_dependent_w, total_time_dependent_wo = verify_soil(total_time_dependent_w, total_time_dependent_wo, ha_w, ha_wo, soc_default, soc_tier_2, flu)

    return total_time_dependent_w, total_time_dependent_wo

def afforestation_time_dependent(units_w_before_20, units_w_after_20, units_wo_before_20, units_wo_after_20, time_impl, time_cap, rate_type, rate_of_change_soil,
                    flu, soc_default, soc_tier_2, agb_secondary_dm_before_20_years, agb_secondary_dm_after_20_years, 
                    bgb_secondary_dm_before_20_years_param, bgb_secondary_dm_after_20_years_param, agb_secondary_c_before_20_years_tier_2, 
                    agb_secondary_c_after_20_years_tier_2, bgb_secondary_c_before_20_years_tier_2, bgb_secondary_c_after_20_years_tier_2,
                    reference_carbon_stocks_tier_2, abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125, before_20):

    # Biomass Gain 
    
    agb_secondary_c_before_20_years = agb_secondary_dm_before_20_years * 0.47 if not agb_secondary_c_before_20_years_tier_2 else agb_secondary_c_before_20_years_tier_2
    agb_secondary_c_after_20_years = agb_secondary_dm_after_20_years * 0.47 if not agb_secondary_c_after_20_years_tier_2 else agb_secondary_c_after_20_years_tier_2

    bgb_secondary_dm_before_20_years = bgb_secondary_dm_before_20_years_param * agb_secondary_dm_before_20_years
    bgb_secondary_dm_after_20_years = bgb_secondary_dm_after_20_years_param * agb_secondary_dm_after_20_years

    bgb_secondary_c_before_20_years = bgb_secondary_dm_before_20_years * 0.47 if not bgb_secondary_c_before_20_years_tier_2 else bgb_secondary_c_before_20_years_tier_2
    bgb_secondary_c_after_20_years = bgb_secondary_dm_after_20_years * 0.47 if not bgb_secondary_c_after_20_years_tier_2 else bgb_secondary_c_after_20_years_tier_2

    tot_biomass_growth_after_20_years = bgb_secondary_c_after_20_years + agb_secondary_c_after_20_years
    tot_biomass_growth_before_20_years = bgb_secondary_c_before_20_years + agb_secondary_c_before_20_years

    total_biomass_co2_annual_rate_wo = biomass_annual_rate_calculation(units_wo_before_20, units_wo_after_20, tot_biomass_growth_before_20_years, tot_biomass_growth_after_20_years, before_20)
    total_biomass_co2_annual_rate_w = biomass_annual_rate_calculation(units_w_before_20, units_w_after_20, tot_biomass_growth_before_20_years, tot_biomass_growth_after_20_years, before_20)

    # biomass_gain_wo = - max_co2_agb_bgb * (units_wo_before_20 + units_wo_after_20) if total_biomass_co2_annual_rate_wo < ( - ( max_co2_agb_bgb * (units_wo_before_20 + units_wo_after_20))) else total_biomass_co2_annual_rate_wo
    # biomass_gain_w = - max_co2_agb_bgb * (units_w_before_20 + units_w_after_20) if total_biomass_co2_annual_rate_w < ( - ( max_co2_agb_bgb * (units_w_before_20 + units_w_after_20))) else total_biomass_co2_annual_rate_w

    biomass_gain_wo = total_biomass_co2_annual_rate_wo
    biomass_gain_w = total_biomass_co2_annual_rate_w

    
    # Emissions due to soil
    soc_0 = soc_default if not soc_tier_2 else soc_tier_2
    soc = flu * soc_0
    delta_c_mineral_per_ha = soc_0 - soc

    # limited to 20 years
    delta_co2_mineral_per_ha_per_yr = delta_c_mineral_per_ha * (-44/12)/20

    soil_emission_w = soil_emissions(units_w_before_20, delta_co2_mineral_per_ha_per_yr, delta_c_mineral_per_ha)
    soil_emission_wo = soil_emissions(units_wo_before_20, delta_co2_mineral_per_ha_per_yr, delta_c_mineral_per_ha)

    total_w = biomass_gain_w + soil_emission_w
    total_wo = biomass_gain_wo + soil_emission_wo


    return [biomass_gain_w, soil_emission_w], [biomass_gain_wo, soil_emission_wo]

def verify_soil(time_dependent_w, time_dependent_wo, ha_w, ha_wo, soc_default, soc_tier_2, flu):

    soc_0 = soc_default if not soc_tier_2 else soc_tier_2
    soc = flu * soc_0
    delta_c_mineral_per_ha = soc_0 - soc

    biomass_emissions_w = [i[1] for i in time_dependent_w]
    biomass_emissions_wo = [i[1] for i in time_dependent_wo]

    new_soil_emissions_w = soil_new_yearly(biomass_emissions_w, ha_w, delta_c_mineral_per_ha)
    new_soil_emissions_wo = soil_new_yearly(biomass_emissions_wo, ha_wo, delta_c_mineral_per_ha)

    new_time_dependent_w = [[j[0],i] for i,j in zip(new_soil_emissions_w, time_dependent_w)]
    new_time_dependent_wo = [[j[0],i] for i,j in zip(new_soil_emissions_wo, time_dependent_wo)]

    return new_time_dependent_w, new_time_dependent_wo

def soil_new_yearly(soil_emissions, hectars, delta_c_mineral_per_ha):

    maximum = (hectars * delta_c_mineral_per_ha * (-44/12))
    result = sum(soil_emissions)
    if abs(sum(soil_emissions)) < abs(maximum):
        return soil_emissions
    else:
        #print('CIAO')
        runnning_sum = 0
        result = []
        for i in soil_emissions:
            runnning_sum += i
            if abs(runnning_sum) <= abs(maximum):
                result.append(i)
            else:
                result.append(+maximum - runnning_sum + i)
                break

        result.extend([0 for i in range(len(soil_emissions) - len(result))])
        
        return result

def verify_biomass(time_dependent_w, time_dependent_wo, ha_w, ha_wo, reference_carbon_stocks_tier_2,abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125 ):

    max_co2_agb_bgb = reference_carbon_stocks_tier_2 * 44/12 if reference_carbon_stocks_tier_2 else max_co2_above_below_ground(abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125)

    biomass_emissions_w = [i[0] for i in time_dependent_w]
    biomass_emissions_wo = [i[0] for i in time_dependent_wo]

    new_biomass_emissions_w = biomass_new_yearly(biomass_emissions_w, max_co2_agb_bgb, ha_w)
    new_biomass_emissions_wo = biomass_new_yearly(biomass_emissions_wo, max_co2_agb_bgb, ha_wo)

    new_time_dependent_w = [[i,j[1]] for i,j in zip(new_biomass_emissions_w, time_dependent_w)]
    new_time_dependent_wo = [[i,j[1]] for i,j in zip(new_biomass_emissions_wo, time_dependent_wo)]


    return new_time_dependent_w, new_time_dependent_wo

def biomass_new_yearly(biomass_emissions, max_co2_agb_bgb, ha):

    maximum = - max_co2_agb_bgb * ha
    runnning_sum = 0
    result = []
    
    for i in biomass_emissions:
        runnning_sum += i
        if runnning_sum >= maximum:
            result.append(i)
        else:
            result.append(maximum - runnning_sum + i)
            break

    result.extend([0 for i in range(len(biomass_emissions) - len(result))])


    return result

def afforestation_non_time_dependent( ha_w, ha_wo, initial_biomass, initial_biomass_tier_2, fire_bool, nitrous, methane, 
                    emission_factor_ch4, emission_factor_n2o, combusted_fraction, dead_wood_c_default,
                    dead_wood_c_tier_2, litter_c_default, litter_c_tier_2
                    ):


    biomass_converted = initial_biomass_tier_2 if initial_biomass_tier_2 else initial_biomass
    
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


    # Emissions due to fire
    combustion_mass = biomass_converted / 0.4 
    biomass_ch4 = combustion_mass * combusted_fraction * emission_factor_ch4
    biomass_n2o = combustion_mass * combusted_fraction * emission_factor_n2o
    biomass_tco2 = (biomass_ch4 * methane + biomass_n2o * nitrous) / 1000

    fire_emissions_w = ha_w * biomass_tco2 if fire_bool else 0
    fire_emissions_wo = ha_wo * biomass_tco2 if fire_bool else 0


    # Results COMPUTE TOTAL W AND WO HERE
    total_w =  dom_emissions_w + biomass_loss_w  + fire_emissions_w
    total_wo = dom_emissions_wo + biomass_loss_wo + fire_emissions_wo

    return [dom_emissions_w, biomass_loss_w, fire_emissions_w ], [dom_emissions_wo,biomass_loss_wo, fire_emissions_wo ]

def aggregate_emissions(total_non_time_w, total_non_time_wo, total_time_dependent_w, total_time_dependent_wo, time_impl):

    total_w = [sum(j) + sum(total_non_time_w)/(time_impl + 1) if i <= time_impl else sum(j) for i,j in enumerate(total_time_dependent_w)]
    total_wo = [sum(j) + sum(total_non_time_wo)/(time_impl + 1) if i <= time_impl else sum(j) for i,j in enumerate(total_time_dependent_wo)]

    return total_w, total_wo

######### FUNCTIONS FOR MAX AGB + BGB CALCULATION BASED ON REFERENCE CARBON STOCKS
def max_co2_above_below_ground(abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125):

    if abg_biomass <= 125:
        return (abg_biomass + abg_biomass * rate_bgb_agb_s_125) * 0.47 * 44/12
    else:
        return (abg_biomass + abg_biomass * rate_bgb_agb_b_125) * 0.47 * 44/12

######### FUNCTIONS FOR BIOMASS ANNUAL RATE CALCULATION ######################
def biomass_annual_rate_calculation (area_before_20, area_after_20, tot_biomass_growth_before_20_years, tot_biomass_growth_after_20_years, before_20):

    component_before_20_years = area_before_20 * tot_biomass_growth_before_20_years 
    component_after_20_years = tot_biomass_growth_after_20_years * area_after_20 

    result = component_after_20_years + component_before_20_years

    return (result) * (-44/12)

######## FUNCTIONS FOR SOIL EMISSION CALCULATION
def soil_emissions(hectars, delta_co2_mineral_per_ha_per_yr, delta_c_mineral_per_ha):

    computed_value = delta_co2_mineral_per_ha_per_yr * hectars if hectars > 0 else 0
    return computed_value

print(calculate_emissions(100,0, 21,1,35,0,'True',265,28,2.30,0.21,0.8,'D',0.5,0.72,20,0,19.7,0,31.4,0,1,1, 0.39,0.39,0,0,0,0,0,40,0.39,0.24))