import math

def calculate_emissions(area_start, area_w, area_wo):

    EFc = EFc_ref if not EFc_tier_2 else EFc_tier_2
    SFw = SFw_ref if not SFw_tier_2 else SFw_tier_2
    SFp = SFp_ref if not SFp_tier_2 else SFp_tier_2
    SFo = SFo_ref if not SFo_tier_2 else SFo_tier_2
    rice_yield = yield_ref if not yield_tier_2 else yield_tier_2

    if area_start == 0 and area_w == 0 and area_wo == 0:
        adjusted_daily_ef_methane_ref = 0
        straw_tonnes_ref = 0
    else:
        adjusted_daily_ef_methane_ref = EFc * SFw * SFp * SFo
        straw_tonnes_ref = rice_yield * rice_slope + rice_intercept

    
    

    return

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
                time_impl * (1 - rate_coefficient)
            return
    
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
    calculated_time_ind = - delta_soil_c_20_years * min(area, area_start) * min (20, time_impl + time_cap)
    calculated_time_dep = immediate_soil(area, area_start, time_impl, time_cap) if rate_type == 'I' else not_immediate_soil(area, area_start, time_impl, time_cap, rate_type, rate_coefficient)
    calculated = calculated_time_dep + calculated_time_ind


    return maximum if abs(calculated) > maximum else calculated

def ch4_emitted(area_start, area, time_impl, time_cap, rate_coefficient, methane_constant, cultivation_period_ref, 
                cultivation_period_tier_2, daily_ef_methane_default, daily_ef_methane_tier_2):

    def area_time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):
        if area > area_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)

    cultivation_period = cultivation_period_ref if not cultivation_period_tier_2 else cultivation_period_tier_2
    daily_ef_methane = daily_ef_methane_default if not daily_ef_methane_tier_2 else daily_ef_methane_tier_2

    kg_methane_cultivation_period = daily_ef_methane * cultivation_period

    return (min(area_start, area) * (time_cap + time_impl) + abs(area_start - area) * area_time_dependency(area_start, area, rate_coefficient, time_impl, time_cap)) * kg_methane_cultivation_period * methane_constant / 1000

def straw_burning(area_start, area, time_impl, time_cap, rate_coefficient, straw_burnt, rice_cf, methane_ef, methane_constant, 
                  nitrous_ef, nitrous_constant, straw_tonnes_ref, straw_tonnes_tier_2):
    '''
    straw_burnt: answer front-end, expects True or False
    rice_cf: standard value IPCC B87
    methane_ef: standard value IPCC D76
    nitrous_ef: standard value IPCC E76
    straw_tonnes_ref: if area_start, area_w, area_wo == 0 return 0 else CAN BE DONE ON GENERAL FUNCTION. else YIELD * rice_slope + rice_intercept
    straw_tonnes_tier_2: tier_2_value, expects Float or None
    
    '''

    def area_time_dependency(area_start, area, rate_coefficient):
        if area > area_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)

    if not straw_burnt:
        return 0
    else:
        straw_tonnes = straw_tonnes_ref if not straw_tonnes_tier_2 else straw_tonnes_tier_2
        straw_methane_co2 = straw_tonnes * rice_cf * methane_ef * methane_constant / 1000
        straw_nitrous_co2 = straw_tonnes * rice_cf * nitrous_ef * nitrous_constant / 1000
        
        return (min(area_start, area) * (time_cap + time_impl) + abs(area_start - area) * area_time_dependency(area_start, area, rate_coefficient)) * (straw_methane_co2 + straw_nitrous_co2)

straw = straw_burning(100, 100, 20, 9, 0.5, True, 0.8, 2.7, 28, 0.07, 265, 45.2, None )

ch4 = ch4_emitted(100, 100, 20, 9, 0.5, 28, 113, None, 1.05910000, None)

soil = soil_co2_change(100, 100, 20, 9, 'D', 0.5, 46, None, 1.35, None, )