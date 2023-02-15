
def total_emissions(time_impl, time_cap, rate_coefficient, catch_start, catch_w, catch_wo, ef_diesel, fui_default, fui_start_tier_2, fui_end_tier_2, gwp_refrigerant_default,
                    gwp_refrigerant_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_tier_2, percentage_refrigerant_start, percentage_refrigerant_w, 
                    percentage_refrigerant_wo, tonnes_ice_default, tonnes_ice_tier_2,  kwh_ice_per_tonne_default, kwh_ice_per_tonne_tier_2, operating_margin,
                    percentage_ice_w, percentage_ice_wo):

    emissions_catch_w = emissions_catch(time_impl, time_cap, rate_coefficient, catch_start, catch_w, ef_diesel, fui_default, fui_start_tier_2, fui_end_tier_2) 
    emissions_catch_wo = emissions_catch(time_impl, time_cap, rate_coefficient, catch_start, catch_wo, ef_diesel, fui_default, fui_start_tier_2, fui_end_tier_2)

    emissions_refrigerant_w = emissions_refrigerant(time_impl, time_cap, rate_coefficient, gwp_refrigerant_default, gwp_refrigerant_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_tier_2, catch_start, catch_w, percentage_refrigerant_start, percentage_refrigerant_w)
    emissions_refrigerant_wo = emissions_refrigerant(time_impl, time_cap, rate_coefficient, gwp_refrigerant_default, gwp_refrigerant_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_tier_2, catch_start, catch_wo, percentage_refrigerant_start, percentage_refrigerant_wo)

    emissions_ice_w = emissions_ice(time_impl, time_cap, rate_coefficient, tonnes_ice_default, kwh_ice_per_tonne_default, operating_margin, kwh_ice_per_tonne_tier_2, tonnes_ice_tier_2, catch_start, catch_w, percentage_ice_w, percentage_ice_w)
    emissions_ice_wo = emissions_ice(time_impl, time_cap, rate_coefficient, tonnes_ice_default, kwh_ice_per_tonne_default, operating_margin, kwh_ice_per_tonne_tier_2,    tonnes_ice_tier_2, catch_start, catch_wo, percentage_ice_wo, percentage_ice_wo)

    total_w = emissions_catch_w + emissions_refrigerant_w + emissions_ice_w
    total_wo = emissions_catch_wo + emissions_refrigerant_wo + emissions_ice_wo

    return total_w, total_wo, total_w - total_wo



def emissions_catch(time_impl, time_cap, rate_coefficient, catch_start, catch_end, ef_diesel, fui_default, fui_start_tier_2, fui_end_tier_2):

    fui_start = fui_default if not fui_start_tier_2 else fui_start_tier_2
    fui_end = fui_default if not fui_end_tier_2 else fui_end_tier_2

    ef_start = fui_start * ef_diesel / 1000
    ef_end = fui_end * ef_diesel / 1000

    annual_start = catch_start * ef_start
    annual_end = catch_end * ef_end

    return min(annual_start, annual_end) * (time_impl + time_cap) + abs(annual_end - annual_start) * time_component(annual_start, annual_end, time_impl, time_cap, rate_coefficient)

def emissions_refrigerant(time_impl, time_cap, rate_coefficient, gwp_refrigerant_default, gwp_refrigerant_tier_2, quantity_lost_refrigerant_default,                            quantity_lost_refrigerant_tier_2, catch_start, catch_end, percentage_refrigerant_start, percentage_refrigerant_end):

    gwp_refrigerant = gwp_refrigerant_default if not gwp_refrigerant_tier_2 else gwp_refrigerant_tier_2
    quantity_lost_refrigerant = quantity_lost_refrigerant_default if not quantity_lost_refrigerant_tier_2 else quantity_lost_refrigerant_tier_2

    catch_with_refrigerant_start = catch_start * percentage_refrigerant_start
    catch_with_refrigerant_end = catch_end * percentage_refrigerant_end

    annual_start = gwp_refrigerant * quantity_lost_refrigerant * catch_with_refrigerant_start / 1000
    annual_end = gwp_refrigerant * quantity_lost_refrigerant * catch_with_refrigerant_end / 1000

    return min(annual_start, annual_end) * (time_impl + time_cap) + abs(annual_end - annual_start) * time_component(annual_start, annual_end, time_impl, time_cap, rate_coefficient)

def emissions_ice(time_impl, time_cap, rate_coefficient, tonnes_ice_default, kwh_ice_per_tonne_default, operating_margin, kwh_ice_per_tonne_tier_2, tonnes_ice_tier_2, catch_start, catch_end, percentage_ice_start, percentage_ice_end):

    tonnes_ice = tonnes_ice_default if not tonnes_ice_tier_2 else tonnes_ice_tier_2
    kwh_ice_per_tonne = kwh_ice_per_tonne_default if not kwh_ice_per_tonne_tier_2 else kwh_ice_per_tonne_tier_2

    ice_ef = tonnes_ice * kwh_ice_per_tonne * operating_margin / 1000

    catch_with_refrigerant_start = catch_start * percentage_ice_start
    catch_with_refrigerant_end = catch_end * percentage_ice_end

    annual_start = ice_ef * catch_with_refrigerant_start 
    annual_end = ice_ef * catch_with_refrigerant_end

    return min(annual_start, annual_end) * (time_impl + time_cap) + abs(annual_end - annual_start) * time_component(annual_start, annual_end, time_impl, time_cap, rate_coefficient)

def time_component(start, end, time_impl, time_cap, rate_coefficient):
        if end > start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)