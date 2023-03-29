def input_single_calculation(unit_start, unit_end, rate_coefficient, ipcc_factor, tier_2_factor, unit_factor, emissions_factor, time_impl, time_cap):

        def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):

                if area > area_start:
                    return time_cap + time_impl * rate_coefficient
                else:
                    return time_impl * (1 - rate_coefficient)
            
        ipcc_or_tier_2_factor = tier_2_factor if tier_2_factor else ipcc_factor

        unit_start = unit_start * unit_factor * ipcc_or_tier_2_factor
        unit_end = unit_end * unit_factor * ipcc_or_tier_2_factor

        emissions_start = unit_start * ipcc_factor * emissions_factor
        emissions_end = unit_end * ipcc_factor * emissions_factor

        total_emissions = (min(emissions_start, emissions_end) * (time_cap + time_impl) + abs(emissions_end - emissions_start) * time_dependency(emissions_start, emissions_end, rate_coefficient, time_impl, time_cap))

        return total_emissions

def input_w_wo_calculation(unit_start, unit_w, unit_wo, rate_coefficient_w, rate_coefficient_wo, ipcc_factor, tier_2_factor, unit_factor, emissions_factor, time_impl, time_cap):
        
    em_w = input_single_calculation(unit_start, unit_w, rate_coefficient_w, ipcc_factor, tier_2_factor, unit_factor, emissions_factor, time_impl, time_cap)
    em_wo = input_single_calculation(unit_start, unit_wo, rate_coefficient_wo, ipcc_factor, tier_2_factor, unit_factor, emissions_factor, time_impl, time_cap)

    return em_w, em_wo


def new_irrigation_system(ef_ipcc, ef_tier_2, units_end):
     
     """
     ef_ipcc: taken from EnergyDB A8-B16
     """
     
     ef = ef_ipcc if ef_ipcc else ef_tier_2

     annual_emissions = units_end * ef / 1000

     return annual_emissions

def operational_irrigation(ef_default, ef_tier_2, total_dynamic_head_default, total_dynamic_head_tier_2, average_pressure_default, average_pressure_tier_2, pumping_efficiency_default, pumping_efficiency_tier_2, erh, depth,
                           units_start, units_w, units_wo, rate_w, rate_wo, time_impl, time_cap, electricity_multiplier_w, electricity_multiplier_wo):

    """
    ef_default: taken from EnergyDB G7H-H13 matching SourceOfEnergy
    total_dynamic_head_default: taken from EnergyDB G7H-H13 matching SourceOfEnergy
    average_pressure_default: taken from EnergyDB O7-S12 matching SourceOfEnergy
    pumping_efficiency_default: 0.45 (aka 45%)
    erh: if source_of_energy == 'electricity' then 0,00000272500 else 9.81 / (net_calorific_values * density) * 0.001
    electricity_multiplier_w: 10% if source_of_energy == 'electricity' else None
    electricity_multiplier_wo: 10% if source_of_energy == 'electricity' else None
    """

    def ef_calculation(ef_default, ef_tier_2, total_dynamic_head_default, total_dynamic_head_tier_2, average_pressure_default, average_pressure_tier_2, pumping_efficiency_default, pumping_efficiency_tier_2, erh, depth ):
        pumping_efficiency = pumping_efficiency_default if not pumping_efficiency_tier_2 else pumping_efficiency_tier_2
        average_pressure = average_pressure_default if not average_pressure_tier_2 else average_pressure_tier_2
        total_dynamic_head_default = average_pressure * 10
        total_dynamic_head = total_dynamic_head_default if not total_dynamic_head_tier_2 else total_dynamic_head_tier_2
        ef = ef_default if not ef_tier_2 else ef_tier_2
        gwir = gwir * 10

        total_energy = gwir * erh
        A_efficiency = total_energy / pumping_efficiency

        b_depth_tph = A_efficiency * (depth + total_dynamic_head)
        C_tco2 = b_depth_tph * ef ### this is the equivalent of the ef_ipcc in general calculations for input

        return C_tco2
    
    ef = ef_calculation(ef_default, ef_tier_2, total_dynamic_head_default, total_dynamic_head_tier_2, average_pressure_default, average_pressure_tier_2, pumping_efficiency_default, pumping_efficiency_tier_2, erh, depth )

    emissions_w = input_single_calculation(units_start, units_w, rate_w, ef, None, 1, 1, time_impl, time_cap)
    emissions_wo = input_single_calculation(units_start, units_wo, rate_wo, ef, None, 1, 1, time_impl, time_cap)

    emissions_w = emissions_w * (1 + electricity_multiplier_w) if electricity_multiplier_w else emissions_w
    emissions_wo = emissions_wo * (1 + electricity_multiplier_wo) if electricity_multiplier_wo else emissions_wo

    return emissions_w, emissions_wo, emissions_w - emissions_wo


    
     