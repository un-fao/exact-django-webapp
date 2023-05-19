def emissions_calculation(tam: float, vser: float, ef_prp_methane: float, percentage_prp_default: float, percentage_prp_tier_2_start: float, percentage_prp_tier_2_w: float, percentage_prp_tier_2_wo: float,
                          ef_system_methane: list, ch4_prp_tier_2_start: float, ch4_prp_tier_2_w: float, ch4_prp_tier_2_wo: float, n_heads_start: int, n_heads_w: int, n_heads_wo:int, methane_constant: float,
                          rate_w:float, rate_wo:float, time_impl: float, time_cap: float):

    def time_component(start, end, time_impl, time_cap, rate_coefficient):
            if end > start:
                return time_cap + time_impl * rate_coefficient
            else:
                return time_impl * (1 - rate_coefficient)

    def inital_w_wo_calculation(tam: float, vser: float, ef_prp: float, percentage_prp_default: float, percentage_prp_tier_2: float, ef_system: list, ch4_prp_tier_2: float, n_heads: int, emission_constant: float):
        
        def ch4_head_calculation(tam: float, vser: float, ef_prp: float, percentage_prp_default: float, percentage_prp_tier_2: float, ef_system: list, ch4_prp_tier_2: float):

            if not percentage_prp_tier_2:
                ch4_system = [i * (tam/1000) * (vser/1000) * 365 * j/100 for (i,j) in zip(ef_system, percentage_system_default)]
            else: 
                # this recalculates percentages in the system as a function of percentage prp tier 2
                ch4_system = [i * (tam/1000) * (vser/1000) * 365 * j/100 * ((1-percentage_prp_tier_2/100)/(1-percentage_prp_default/100)) for (i,j) in zip(ef_system, percentage_system_default)]
            
            percentage_prp = percentage_prp_default if not percentage_prp_tier_2 else percentage_prp_tier_2
            ch4_prp = ef_prp * (tam/1000) * (vser/1000) * 365 * percentage_prp/100 if not ch4_prp_tier_2 else ch4_prp_tier_2 if not ch4_prp_tier_2 else ch4_prp_tier_2 * percentage_prp/100

            ch4_head = sum(ch4_system) + ch4_prp
            return ch4_head
        
        ch4_head = ch4_head_calculation(tam, vser, ef_prp, percentage_prp_default, percentage_prp_tier_2, ef_system, ch4_prp_tier_2)

        return ch4_head * n_heads / 1000 * emission_constant

    annual_start = inital_w_wo_calculation(tam, vser, ef_prp_methane, percentage_prp_default, percentage_prp_tier_2_start, ef_system_methane, ch4_prp_tier_2_start, n_heads_start, methane_constant)
    annual_w = inital_w_wo_calculation(tam, vser, ef_prp_methane, percentage_prp_default, percentage_prp_tier_2_w, ef_system_methane, ch4_prp_tier_2_w, n_heads_w, methane_constant)
    annual_wo = inital_w_wo_calculation(tam, vser, ef_prp_methane, percentage_prp_default, percentage_prp_tier_2_wo, ef_system_methane, ch4_prp_tier_2_wo, n_heads_wo, methane_constant)

    em_w = min(annual_start, annual_w) * (time_impl + time_cap) + abs(annual_w - annual_start) * time_component(annual_start, annual_w, time_impl, time_cap, rate_w)
    em_wo = min(annual_start, annual_wo) * (time_impl + time_cap) + abs(annual_wo - annual_start) * time_component(annual_start, annual_wo, time_impl, time_cap, rate_wo)

    return em_w, em_wo, em_w - em_wo



# ef_prp = 0.6
# ef_system = [8, 3.2, 16.1]
# percentage_system_default = [20, 29, 6] # solid storage, dry lot, burned for fuel
# tam = 250
# vser = 21.7
# percentage_prp_default = 45
# percentage_prp_tier_2 = None
# ch4_prp_tier_2 = None
# n_heads = 500
# emission_constant = 28

# ao = emissions_calculation(tam, vser, ef_prp, percentage_prp_default, None, None, None, ef_system, None, None, None, 500, 100, 250, emission_constant, 0.5, 0.5, 20, 5 )

# print(ao)