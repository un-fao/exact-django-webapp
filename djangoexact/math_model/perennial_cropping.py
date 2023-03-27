import math

def calculate_emissions(area_start, area_w, area_wo, time_impl, time_cap, rate_type_w, rate_coefficient_w,rate_type_wo, rate_coefficient_wo,
                    nitrous_constant, methane_constant, residue_burnt, emission_factor_burning_nitrous,
                    emission_factor_burning_methane, combustion_factor, fire_periodicity_default, fire_periodicity_tier_2, t_biomass_tier_2, 
                    agb_rate_default, agb_rate_tier_2, agb_maximum_c, bgb_rate_default, bgb_rate_tier_2,
                    socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2,
                    ):
    '''
    ##### PARAMETERS USED FOR COMPUTATION #######
    # GENERAL
    area_start
    area_w
    area_wo
    time_impl
    time_cap
    rate_type_w
    rate_coefficient_w
    rate_type_wo
    rate_coefficient_wo
    nitrous_constant: taken from 1.Description 
    methane_constant: taken from 1.Description
    # Residue Calculation
    residue_burnt: input from front-end, states whether the residues have been burnt or not
    emission_factor_burning_nitrous: stable value, no logic, maybe ASK? IPCC E75
    emission_factor_burning_methane: stable value, no logic, maybe ASK? IPCC E75
    combustion_factor: IPCC B89
    fire_periodicity_deafult: stable value, no logic, always = 1
    fire_periodicity_tier_2: tier 2 value, expects INT or None
    t_biomass_tier_2: tier 2 value, expects Float or None
    agb_rate_default: taken from IPCC E105 matching clim_moist_cont to rows and CROP TYPE to columns ------ COULD BE THE SAME AS AG_TC_DEFAULT
    agb_rate_tier_2: tier 2 value, expects Float or None
    # Total Biomass CO2 Calculation
    agb_maximum_c: taken from IPCC A3235 matching climate to rows and CROP TYPE to columns
    bgb_rate_default: taken from IPCC E308 matching clim_moist_cont to rows and CROP TYPE to columns
    bgb_rate_tier_2: tier 2 value, expects Float or None
    # Som and Soil Calculation
    socref: standard value listed in 1.Description
    soc_tier_2: tier 2 value, excepts None or Float value 
    f_lu_ref: taken from IPCC A57 matching CLIMATE REGION and taking colum Perennial/Tree crop
    f_lu_tier_2: tier 2 value, expects None or Float value
    f_i_ref: taken from IPCC A57 matching CLIMATE REGION to rows and INPUT OF ORGANIC MATERIAL to columns
    f_i_tier_2: tier 2 value, expects None or Float value
    f_mg_ref: taken from IPCC A57 matching CLIMATE REGION to rows and TILLAGE MANAGEMENT to columns
    f_mg_tier_2: tier 2 value, expects None or Float value


    
    '''
    residue_emissions_w = residue_burning(area_start, area_w, time_impl, time_cap, rate_coefficient_w, nitrous_constant, methane_constant, residue_burnt, emission_factor_burning_nitrous,
                    emission_factor_burning_methane, combustion_factor, fire_periodicity_default, fire_periodicity_tier_2, t_biomass_tier_2, agb_rate_default, agb_rate_tier_2)
    total_bio_emissions_w = total_biomass_co2(area_start, area_w, time_impl, time_cap, rate_type_w, rate_coefficient_w, agb_rate_default, agb_rate_tier_2, agb_maximum_c, bgb_rate_default, bgb_rate_tier_2)
    som_emissions_w = som(area_start, area_w, time_impl, time_cap, rate_coefficient_w, rate_type_w, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2)
    soil_emissions_w = soil_co2_change (area_start, area_w, time_impl, time_cap, rate_coefficient_w, rate_type_w, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2)

    residue_emissions_wo = residue_burning(area_start, area_wo, time_impl, time_cap, rate_coefficient_wo, nitrous_constant, methane_constant, residue_burnt, emission_factor_burning_nitrous,
                    emission_factor_burning_methane, combustion_factor, fire_periodicity_default, fire_periodicity_tier_2, t_biomass_tier_2, agb_rate_default, agb_rate_tier_2)
    total_bio_emissions_wo = total_biomass_co2(area_start, area_wo, time_impl, time_cap, rate_type_wo, rate_coefficient_wo, agb_rate_default, agb_rate_tier_2, agb_maximum_c, bgb_rate_default, bgb_rate_tier_2)
    som_emissions_wo = som(area_start, area_wo, time_impl, time_cap, rate_coefficient_wo, rate_type_wo, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2)
    soil_emissions_wo = soil_co2_change (area_start, area_wo, time_impl, time_cap, rate_coefficient_wo, rate_type_wo, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2)

    total_w = residue_emissions_w + total_bio_emissions_w + som_emissions_w + soil_emissions_w
    total_wo = residue_emissions_wo + total_bio_emissions_wo + som_emissions_wo + soil_emissions_wo

    ciao = 2

    return total_w, total_wo, total_w - total_wo

def soil_co2_change(area_start, area, time_impl, time_cap, rate_coefficient, rate_type, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2):

    def immediate_soil(area, area_start, time_impl, time_cap):
        return area * min(20, time_impl + time_cap) if area > area_start else 0

    def not_immediate_soil(area, area_start, time_impl, time_cap, rate_type, rate_coefficient):

        # SUPPORT FUNCTION
        def not_immediate_area_start_bigger_area(time_impl, time_cap, rate_type, rate_coefficient):
            if time_impl > 20:
                if rate_type == 'D':
                    return time_impl - (pow(time_impl - 20, 2)/ (2 * time_impl))
                else:
                    return 0.215 * time_impl - (time_impl/4.6 * math.exp(-92.1/time_impl) - 0.01)
            else:
                return time_impl * (1 - rate_coefficient)
    
        def not_immediate_area_start_smaller_area(time_impl, time_cap, rate_type, rate_coefficient):

            # SUPPORT FUNCTION
            def exponential_correction(time_impl, time_cap, rate_type):
                if rate_type == 'E':
                    return time_impl + time_cap - 20 + 0.217 * time_impl * math.exp(4.606 * (20 - time_impl - time_cap)/(time_impl) - 1)
                else:
                    return math.pow(time_impl + time_cap -20, 2) * (0.5/time_impl)

            # ACTUAL CALCULATION

            if time_cap >  20:
                return 20
            else:
                if time_impl + time_cap < 20:
                    return time_impl * rate_coefficient + time_cap
                else:
                    return min(20, time_impl * rate_coefficient) + time_impl + time_cap - min(20, time_impl) - exponential_correction(time_impl, time_cap, rate_type)


        # ACTUAL COMPUTATION
        if area_start > area:
           return (area_start - area) * not_immediate_area_start_bigger_area(time_impl, time_cap, rate_type, rate_coefficient)
        else:
            return (area - area_start) * not_immediate_area_start_smaller_area(time_impl, time_cap, rate_type, rate_coefficient)
        

    # ASSIGNMENT OF TIER 2 VALUES
    soc = socref if not soc_tier_2 else soc_tier_2
    f_lu = f_lu_ref if not f_lu_tier_2 else f_lu_tier_2
    f_i = f_i_ref if not f_i_tier_2 else f_i_tier_2
    f_mg = f_mg_ref if not f_mg_tier_2 else f_mg_tier_2

    delta_soil_c = (soc * f_lu) * (f_mg * f_i - 1) * (44/12)
    delta_soil_c_20_years = delta_soil_c / 20

    maximum = - delta_soil_c * max(area_start, area)
    calculated_time_ind =  min(area, area_start) * min (20, time_impl + time_cap)
    calculated_time_dep = immediate_soil(area, area_start, time_impl, time_cap) if rate_type == 'I' else not_immediate_soil(area, area_start, time_impl, time_cap, rate_type, rate_coefficient)
    calculated = - delta_soil_c_20_years * (calculated_time_dep + calculated_time_ind)

    return maximum if abs(calculated) > abs(maximum) else calculated

def som (area_start, area, time_impl, time_cap, rate_coefficient, rate_type, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2):

    def immediate(area, area_start, time_impl, time_cap):
        return (area - area_start) * min(20, time_impl + time_cap) if area > area_start else 0

    def not_immediate(area, area_start, time_impl, time_cap, rate_type, rate_coefficient):

        # SUPPORT FUNCTION
        def not_immediate_area_start_bigger_area(time_impl, time_cap, rate_type, rate_coefficient):

            if time_impl > 20:
                if rate_type == 'D':
                    return time_impl - (pow(time_impl - 20, 2)/ (2 * time_impl))
                else:
                    return 0.215 * time_impl - (time_impl/4.6 * math.exp(-92.1/time_impl) - 0.01)
            else:
                return time_impl * (1 - rate_coefficient)
            
    
        def not_immediate_area_start_smaller_area(time_impl, time_cap, rate_type, rate_coefficient):

            # SUPPORT FUNCTION
            def exponential_correction(time_impl, time_cap, rate_type):
                if rate_type == 'E':
                    return time_impl + time_cap - 20 + 0.217 * time_impl * math.exp(4.606 * (20 - time_impl - time_cap)/(time_impl) - 1)
                else:
                    return math.pow(time_impl + time_cap -20, 2) * (0.5/time_impl)

            # ACTUAL CALCULATION

            if time_cap >  20:
                return 20
            else:
                if time_impl + time_cap < 20:
                    return time_impl * rate_coefficient + time_cap
                else:
                    return min(20, time_impl * rate_coefficient) + time_impl + time_cap - min(20, time_impl) - exponential_correction(time_impl, time_cap, rate_type)


        # ACTUAL COMPUTATION
        if area_start > area:
           return (area_start - area) * not_immediate_area_start_bigger_area(time_impl, time_cap, rate_type, rate_coefficient)
        else:
            return (area - area_start) * not_immediate_area_start_smaller_area(time_impl, time_cap, rate_type, rate_coefficient)
    
    # ASSIGNMENT OF TIER 2 VALUES
    soc = socref if not soc_tier_2 else soc_tier_2
    f_lu = f_lu_ref if not f_lu_tier_2 else f_lu_tier_2
    f_i = f_i_ref if not f_i_tier_2 else f_i_tier_2
    f_mg = f_mg_ref if not f_mg_tier_2 else f_mg_tier_2

    # ACTUAL COMPUTATION

    reference_soc = soc * f_lu
    maximum_soc_20_years = soc * f_i * f_mg * f_lu 
    n2o_n_conversion = 44/28


    som_n2o = 0 if maximum_soc_20_years > reference_soc else (reference_soc - maximum_soc_20_years) * 5  * n2o_n_conversion / 1000
    
    time_dep =  immediate(area, area_start, time_impl, time_cap) if rate_type == 'I' else not_immediate(area, area_start, time_impl, time_cap, rate_type, rate_coefficient)

    total = som_n2o * (min(area, area_start) * min(20, time_cap + time_impl) + time_dep)


    return total

def residue_burning(area_start, area, time_impl, time_cap, rate_coefficient, nitrous_constant, methane_constant, residue_burnt, emission_factor_burning_nitrous,
                    emission_factor_burning_methane, combustion_factor, fire_periodicity_default, fire_periodicity_tier_2, t_biomass_tier_2, ag_tc_default, ag_tc_tier_2):

    # SUPPORT FUNCTIONS 
    def func1(area_start, area, rate_coefficient, time_impl, time_cap):

        if area > area_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)


    # ACTUAL COMPUTATION
    # emission_factor_burning_nitrous stable value IPCC E75
    # emission_factor_burning_methane stable value IPCC D75
    # fire periodicity = 1 if no tier_2 else tier_2
    # combustion_factor is always IPCC B89
    # ag_tc_default IPCC E107 matching clim_moist_continent to rows and TYPE OF CROP to columns 
    # Necessary Parameter Assignment
    fire_periodicity = fire_periodicity_default if not fire_periodicity_tier_2 else fire_periodicity_tier_2
    ag_tc = ag_tc_default if not ag_tc_tier_2 else ag_tc_tier_2
    t_biomass = ag_tc * 0.5 /0.47 if not t_biomass_tier_2 else t_biomass_tier_2

    ################## COMPUTATION OF AMOUNT OF KG OF METHANE ###################

    kg_methane = t_biomass * emission_factor_burning_methane * combustion_factor / fire_periodicity if residue_burnt else 0
    
    #################### COMPUTATION OF AMOUNT OF KG OF NITROUS ######################
    
    kg_nitrous = t_biomass * emission_factor_burning_nitrous * combustion_factor / fire_periodicity if residue_burnt else 0



    co2_crop = (kg_nitrous * nitrous_constant + kg_methane * methane_constant)/1000

    total = (min(area_start, area) * (time_cap + time_impl) + abs(area - area_start) * func1(area_start, area, rate_coefficient, time_impl, time_cap)) * co2_crop

    return total

def total_biomass_co2 (area_start, area, time_impl, time_cap, rate_type, rate_coefficient, agb_rate_default, agb_rate_tier_2, agb_maximum_c, bgb_rate_default, bgb_rate_tier_2):
    
    
    def immediate(area, area_start, time_impl, time_cap):
        return (area - area_start) * min(20, time_impl + time_cap) if area > area_start else 0

    def not_immediate(area, area_start, time_impl, time_cap, rate_type, rate_coefficient):

        # SUPPORT FUNCTION
        def not_immediate_area_start_bigger_area(time_impl, time_cap, rate_type, rate_coefficient):

            if time_impl > 20:
                if rate_type == 'D':
                    return time_impl - (pow(time_impl - 20, 2)/ (2 * time_impl))
                else:
                    return 0.215 * time_impl - (time_impl/4.6 * math.exp(-92.1/time_impl) - 0.01)
            else:
                return time_impl * (1 - rate_coefficient)
            
    
        def not_immediate_area_start_smaller_area(time_impl, time_cap, rate_type, rate_coefficient):

            # SUPPORT FUNCTION
            def exponential_correction(time_impl, time_cap, rate_type):
                if rate_type == 'E':
                    return time_impl + time_cap - 20 + 0.217 * time_impl * math.exp(4.606 * (20 - time_impl - time_cap)/(time_impl) - 1)
                else:
                    return math.pow(time_impl + time_cap -20, 2) * (0.5/time_impl)

            # ACTUAL CALCULATION

            if time_cap >  20:
                return 20
            else:
                if time_impl + time_cap < 20:
                    return time_impl * rate_coefficient + time_cap
                else:
                    return min(20, time_impl * rate_coefficient) + time_impl + time_cap - min(20, time_impl) - exponential_correction(time_impl, time_cap, rate_type)


        # ACTUAL COMPUTATION
        if area_start > area:
           return (area_start - area) * not_immediate_area_start_bigger_area(time_impl, time_cap, rate_type, rate_coefficient)
        else:
            return (area - area_start) * not_immediate_area_start_smaller_area(time_impl, time_cap, rate_type, rate_coefficient)
    
    # ACTUAL COMPUTATION
    # agb_rate_default: IPCC E308 matching CLIM_MOIST_CONT to rows and AGRO-FORESTRY system to columns
    # bgb_rate_default: IPCC E105 matching CLIM_MOIST_CONT to rows and AGRO-FORESTRY system to columns
    # agb_maximum_c: IPCC A3235 matching CLIMATE and AGRO-FORESTRY SYSTEM
    agb_rate = agb_rate_default * 44/12 if not agb_rate_tier_2 else agb_rate_tier_2 * 44/12
    bgb_rate = bgb_rate_default * 44/12 if not bgb_rate_tier_2 else bgb_rate_tier_2 * 44/12

    max_agb = 0 if agb_rate_tier_2 else agb_maximum_c * 44/12
    biomass_accumulation_rate = agb_rate + bgb_rate

    max_years_growth = max_agb/agb_rate 

    time_dep = immediate(area, area_start, time_impl, time_cap) if rate_type == 'I' else not_immediate(area, area_start, time_impl, time_cap, rate_type, rate_coefficient)
    calculated = biomass_accumulation_rate * (min (area, area_start) * min(20, time_cap + time_impl) + time_dep)
    tabular = (max_agb + bgb_rate * max_years_growth) * area
    
    return - min(calculated, tabular) if max_agb != 0 else calculated

# em = calculate_emissions(12, 12, 12, 20, 9, 'D', 0.5, 'D', 0.5, 265, 28, True, 0.21, 2.3, 0.85, 1, None, None, 3.16, None, 48, 0.71, None, 46, None, 1.01, None, 0.92, None, 1.04, None)

defo = calculate_emissions(0, 10, 1, 20, 9, 'D', 0.5, 'D', 0.5, 265, 28, True, 0.21, 2.3, 0.85, 1, None, None, 3.16, None, 48, 0.71, None, 46, None, 1.01, None, 0.92, None, 1.04, None)

print(defo)