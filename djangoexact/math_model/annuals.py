import math
from enum import Enum

def calculate_emissions_annual_to_annual(nitrous_constant, methane_constant, ):
    """
    ========== LIST OF PARAMETERS ===========

    ####### RESIDUE BURNING ######### 4
    ---->nitrous_constant: taken from 1.Description
    methane_constant: taken from 1.Description
    ef_methane_agr_residues_main: return IPCC D76 if RESIDUE MANAGEMENT == Burned else None
    combustion_factor_main: if MAIN SEASON CROP in input == 'Maize' or 'Wheat' return IPCC A85 matching main season crop to row, else return IPCC B89
    residue_main_tier_2: tier 2 value, expects float or None
    n_estimation_slope_main: second column in IPCC A10 matching row to Grains if CROP TYPE == Default else match CROP TYPE
    n_estimation_intercept_main: third column in IPCC A10 matching row to Grains if CROP TYPE == Default else match CROP TYPE
    yield_value_main: value inserted in front end if it exists if not average yield from STATS_YIELD_TON_PER_HA matching concatenate(continent, column two in LIST_REGION_COUNTRY C29 matching CROP TYPE) p.s. CROP TYPE can also be default
    # SAME AS ABOVE, ONLY NOW WITH MINOR CROP TYPE and INSERTED VALUES
    ef_methane_agr_residues_minor: return IPCC D76 if RESIDUE MANAGEMENT == Burned else None
    combustion_factor_minor: if MINOR SEASON CROP in input == 'Maize' or 'Wheat' return IPCC A85 matching main season crop to row, else return IPCC B89
    residue_minor_tier_2: tier 2 value, expects float or None
    n_estimation_slope_minor: second column in IPCC A10 matching row to Grains if CROP TYPE == Default else match CROP TYPE
    n_estimation_intercept_minor: third column in IPCC A10 matching row to Grains if CROP TYPE == Default else match CROP TYPE
    yield_value_minor: value inserted in front end if it exists if not average yield from STATS_YIELD_TON_PER_HA matching concatenate(continent, column two in LIST_REGION_COUNTRY C29 matching CROP TYPE) p.s. CROP TYPE can also be default
    # PARAMETERS FOR NITROUS EVALUATION
    ef_nitrous_agr_residues_main: return IPCC E76 if RESIDUE MANAGEMENT MAIN == Burned else None 
    retained_main: boolean which states whether the residues have been retained for MAIN CROP
    ef_nitrous_agr_residues_minor: return IPCC E76 if RESIDUE MANAGEMENT MINOR == Burned else None 
    retained_minor: boolean which states whether the residues have been retained for MINOR CROP
    n_content_ag_main: if CROP TYPE MAIN == 'Oilseeds' or 'Vegetables' or 'Default' return Grains value of table IPCC A8 column 4 else return matching CROP TYPE to rows
    ratio_bg_ag_main: if CROP TYPE MAIN == 'Oilseeds' or 'Vegetables' or 'Default' return Grains value of table IPCC A8 column 5 else return matching CROP TYPE to rows
    n_content_bg_main: if CROP TYPE MAIN== 'Oilseeds' or 'Vegetables' or 'Default' return Grains value of table IPCC A8 column 6 else return matching CROP TYPE to rows
    n_content_ag_minor: if CROP TYPE MINOR == 'Oilseeds' or 'Vegetables' or 'Default' return Grains value of table IPCC A8 column 4 else return matching CROP TYPE to rows
    ratio_bg_ag_minor: if CROP TYPE MINOR == 'Oilseeds' or 'Vegetables' or 'Default' return Grains value of table IPCC A8 column 5 else return matching CROP TYPE to rows
    n_content_bg_minor: if CROP TYPE MINOR== 'Oilseeds' or 'Vegetables' or 'Default' return Grains value of table IPCC A8 column 6 else return matching CROP TYPE to rows
    ---->emission_factor_nitrous: return value from IPCC B99-C101 matching moist_type to rows and returning column 2 (3 overall)

 
    ####### SOM #########  3
    ----> socref: standard value listed in 1.Description
    ---->soc_tier_2: tier 2 value, excepts None or Float value 
    ---->f_lu_ref: taken from IPCC A57 matching CLIMATE REGION and taking colum Long-term cultivated
    ---->f_lu_tier_2: tier 2 value, expects None or Float value
    ---->f_i_ref: taken from IPCC A57 matching CLIMATE REGION to rows and INPUT OF ORGANIC MATERIAL to columns
    ---->f_i_tier_2: tier 2 value, expects None or Float value
    ---->f_mg_ref: taken from IPCC A57 matching CLIMATE REGION to rows and TILLAGE MANAGEMENT to columns
    ---->f_mg_tier_2: tier 2 value, expects None or Float value
    emission_factor_nitrous: return value from IPCC B99-C101 matching moist_type to rows and returning column 2 (3 overall)
    nitrous_constant: Nitrous constant, value taken from 1.Description
    
    ####### SOIL ######### 2
    socref: 46
    soc_tier_2: tier 2 value, excepts None or Float value 
    f_lu_ref: taken from IPCC A57 matching CLIMATE REGION and taking colum Long-term cultivated
    f_lu_tier_2: tier 2 value, expects None or Float value
    f_i_ref: taken from IPCC A57 matching CLIMATE REGION to rows and INPUT OF ORGANIC MATERIAL to columns
    f_i_tier_2: tier 2 value, expects None or Float value
    f_mg_ref: taken from IPCC A57 matching CLIMATE REGION to rows and TILLAGE MANAGEMENT to columns
    f_mg_tier_2: tier 2 value, expects None or Float value

    ######## GENERAL ###########  1
    area_start
    area_w
    area_wo
    time_impl
    time_cap
    rate_w
    rate_coefficient_w
    rate_wo
    rate_coefficient_wo
    

    """

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

    # delta_soil_c = (soc * f_lu * f_mg * f_i - soc) * (44/12)
    delta_soil_c = (soc * f_lu) * (f_mg * f_i - 1) * (44/12)
    delta_soil_c_20_years = delta_soil_c / 20

    maximum = - delta_soil_c * max(area_start, area)
    calculated_time_ind = min(area, area_start) * min (20, time_impl + time_cap)
    calculated_time_dep = immediate_soil(area, area_start, time_impl, time_cap) if rate_type == 'I' else not_immediate_soil(area, area_start, time_impl, time_cap, rate_type, rate_coefficient)
    calculated = (calculated_time_dep + calculated_time_ind) * (- delta_soil_c_20_years) 


    return maximum if abs(calculated) > abs(maximum) else calculated

def som (area_start, area, time_impl, time_cap, rate_coefficient, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2, emission_factor_nitrous, nitrous_constant):

    # SUPPORT FUNCTIONS 
    def func1(area_start, area, rate_coefficient, time_impl, time_cap):

        if area > area_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)
    
    # ASSIGNMENT OF TIER 2 VALUES
    soc = socref if not soc_tier_2 else soc_tier_2
    f_lu = f_lu_ref if not f_lu_tier_2 else f_lu_tier_2
    f_i = f_i_ref if not f_i_tier_2 else f_i_tier_2
    f_mg = f_mg_ref if not f_mg_tier_2 else f_mg_tier_2

    # ACTUAL COMPUTATION

    reference_soc = soc * f_lu
    
    maximum_soc_20_years = soc * f_i * f_mg * f_lu 
    n2o_n_conversion = 44/28

    som_n2o = 0 if maximum_soc_20_years >= reference_soc else ((maximum_soc_20_years - reference_soc)/20/10*1000)  * emission_factor_nitrous * n2o_n_conversion * (nitrous_constant/1000)

    total = - (min(area_start, area) * (time_cap + time_impl) + abs(area - area_start) * func1(area_start, area, rate_coefficient, time_impl, time_cap)) *  som_n2o 

    return total

def residue_burning(area_start, area, time_impl, time_cap, rate_coefficient, nitrous_constant, methane_constant, ef_methane_agr_residues_main, combustion_factor_main, 
                    residue_main_tier_2 , n_estimation_slope_main, n_estimation_intercept_main, yield_value_main,ef_methane_agr_residues_minor, combustion_factor_minor,residue_minor_tier_2,
                    n_estimation_slope_minor, n_estimation_intercept_minor, yield_value_minor, ef_nitrous_agr_residues_main, retained_main, ef_nitrous_agr_residues_minor, retained_minor,
                    n_content_ag_main, ratio_bg_ag_main, n_content_bg_main, n_content_ag_minor, ratio_bg_ag_minor, n_content_bg_minor, emission_factor_nitrous
                                                               ):

    # SUPPORT FUNCTIONS 
    def func1(area_start, area, rate_coefficient, time_impl, time_cap):

        if area > area_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)


    # ACTUAL COMPUTATION

    ################## COMPUTATION OF AMOUNT OF KG OF METHANE ###################

    yield_value_main = yield_value_main * 1000
    yield_value_minor = yield_value_minor * 1000 if yield_value_minor else None

    ag_residue_main = residue_main_tier_2 * 1000 if residue_main_tier_2 else yield_value_main * n_estimation_slope_main + n_estimation_intercept_main
    ag_residue_tonnes_main = ag_residue_main / 1000
    if ef_methane_agr_residues_main: 
        main_season_methane = ag_residue_tonnes_main * ef_methane_agr_residues_main * combustion_factor_main
    else:
        main_season_methane = 0
    ag_residue_minor = residue_minor_tier_2 * 1000 if residue_minor_tier_2 else yield_value_minor * n_estimation_slope_minor + n_estimation_intercept_minor if yield_value_minor else 0
    ag_residue_tonnes_minor = ag_residue_minor / 1000 
    if ef_methane_agr_residues_minor:
        minor_season_methane = ag_residue_tonnes_minor * ef_methane_agr_residues_minor * combustion_factor_minor
    else:
        minor_season_methane = 0
    
    kg_methane = main_season_methane + minor_season_methane
    
    #################### COMPUTATION OF AMOUNT OF KG OF NITROUS ######################
    annual_n_residues_main = ag_residue_main * n_content_ag_main + (yield_value_main + ag_residue_main) * ratio_bg_ag_main * n_content_bg_main
    # COMPUTATION FOR MAIN
    # this means if "Burned"
    if ef_nitrous_agr_residues_main:
        main_season_nitrous = ag_residue_tonnes_main * ef_nitrous_agr_residues_main * combustion_factor_main
    # this means if "Retained"
    elif retained_main:
        n2o_n_conversion = 44/28
        main_season_nitrous = annual_n_residues_main * emission_factor_nitrous * n2o_n_conversion
    else:
        main_season_nitrous = 0
    # COMPUTATION FOR MINOR
    annual_n_residues_minor = ag_residue_minor * n_content_ag_minor + (yield_value_minor + ag_residue_minor) * ratio_bg_ag_minor * n_content_bg_minor if yield_value_minor else 0
    # COMPUTATION FOR MAIN
    # this means if "Burned"

    if ef_nitrous_agr_residues_minor:
        minor_season_nitrous = ag_residue_tonnes_minor * ef_nitrous_agr_residues_minor * combustion_factor_minor
    # this means if "Retained" BUT IN REALITY NOT REALLY, AT LEAST IT SEEMS TO WORK (WITHOUT A MINOR)
    elif retained_minor:
        n2o_n_conversion = 44/28
        minor_season_nitrous = annual_n_residues_minor * emission_factor_nitrous * n2o_n_conversion
    else:
        minor_season_nitrous = 0

    kg_nitrous = main_season_nitrous + minor_season_nitrous



    co2_crop = (kg_nitrous * nitrous_constant + kg_methane * methane_constant)/1000

    _min = min(area_start, area) * (time_cap + time_impl)
    _abs = abs(area - area_start) * func1(area_start, area, rate_coefficient, time_impl, time_cap)

    min__abs = _min + _abs

    total = (min__abs) * co2_crop

    return total

def calculate_emissions(area_start, area_w, area_wo, time_impl, time_cap, rate_w, rate_coefficient_w, rate_wo, rate_coefficient_wo, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2,
                            emission_factor_nitrous, nitrous_constant, methane_constant, ef_methane_agr_residues_main, combustion_factor_main, 
                            residue_main_tier_2 , n_estimation_slope_main, n_estimation_intercept_main, yield_value_main,ef_methane_agr_residues_minor, combustion_factor_minor,residue_minor_tier_2,
                            n_estimation_slope_minor, n_estimation_intercept_minor, yield_value_minor, ef_nitrous_agr_residues_main, retained_main, ef_nitrous_agr_residues_minor, retained_minor,
                            n_content_ag_main, ratio_bg_ag_main, n_content_bg_main, n_content_ag_minor, ratio_bg_ag_minor, n_content_bg_minor
                            ):

    soil_w = soil_co2_change(area_start, area_w, time_impl, time_cap, rate_coefficient_w, rate_w, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2)
    soil_wo = soil_co2_change(area_start, area_wo, time_impl, time_cap, rate_coefficient_wo, rate_wo, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2)

    som_w = som (area_start, area_w, time_impl, time_cap, rate_coefficient_w, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2, emission_factor_nitrous, nitrous_constant)
    som_wo = som (area_start, area_wo, time_impl, time_cap, rate_coefficient_wo, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2, emission_factor_nitrous, nitrous_constant)

    residue_w = residue_burning(area_start, area_w, time_impl, time_cap, rate_coefficient_w, nitrous_constant, methane_constant, ef_methane_agr_residues_main, combustion_factor_main, 
                    residue_main_tier_2 , n_estimation_slope_main, n_estimation_intercept_main, yield_value_main,ef_methane_agr_residues_minor, combustion_factor_minor,residue_minor_tier_2,
                    n_estimation_slope_minor, n_estimation_intercept_minor, yield_value_minor, ef_nitrous_agr_residues_main, retained_main, ef_nitrous_agr_residues_minor, retained_minor,
                    n_content_ag_main, ratio_bg_ag_main, n_content_bg_main, n_content_ag_minor, ratio_bg_ag_minor, n_content_bg_minor, emission_factor_nitrous)
    residue_wo = residue_burning(area_start, area_wo, time_impl, time_cap, rate_coefficient_wo, nitrous_constant, methane_constant, ef_methane_agr_residues_main, combustion_factor_main, 
                    residue_main_tier_2 , n_estimation_slope_main, n_estimation_intercept_main, yield_value_main,ef_methane_agr_residues_minor, combustion_factor_minor,residue_minor_tier_2,
                    n_estimation_slope_minor, n_estimation_intercept_minor, yield_value_minor, ef_nitrous_agr_residues_main, retained_main, ef_nitrous_agr_residues_minor, retained_minor,
                    n_content_ag_main, ratio_bg_ag_main, n_content_bg_main, n_content_ag_minor, ratio_bg_ag_minor, n_content_bg_minor, emission_factor_nitrous)

    total_w = soil_w + som_w + residue_w
    total_wo = soil_wo + som_wo + residue_wo



    return total_w, total_wo, total_w - total_wo

def default_tier_2 (socref, f_lu_ref, f_i_ref, f_mg_ref, n_estimation_slope_main, n_estimation_intercept_main, yield_value_main, n_estimation_slope_minor, n_estimation_intercept_minor, yield_value_minor):

    soc = socref
    f_lu = f_lu_ref
    f_i = f_i_ref
    f_mg = f_mg_ref

    ag_residue_main = yield_value_main * n_estimation_slope_main + n_estimation_intercept_main
    ag_residue_minor = yield_value_minor * n_estimation_slope_minor + n_estimation_intercept_minor if yield_value_minor else 0

    return soc, f_lu, f_i, f_mg, ag_residue_main, ag_residue_minor

# ao = residue_burning(12,12,20, 9, 0.5, 265, 28, 2.7, 0.85, None, 1.13, 0.85, 50, None, 0.85, 0, None, None, None, 0.07, False, None, False, 0.008, 0.19, 0.008, None, None, None, 0.006 )

# som_test = som(12, 12, 20, 9, 0.5, 46, None, 0.83, None, 1.11, None, 1.04, None, 0.006, 265)

# soil = soil_co2_change(12, 12, 20, 9, 0.5, 'D', 46, None, 0.83, None, 1.11, None, 1.04, None )

# inputs = [27, 93, 36, 5, 17, 'D', 0.5, 'D', 0.5, 87.0, None, 0.77, None, 1.0, None, 1.03, None, 0.005, 265.0, 28.0, None, 0.85, None, 0.88, 1.33, 50, None, None, None, None, None, None, None, True, None, False, 0.007, 0.22, 0.006, None, None, None]
# print(calculate_emissions(*inputs))