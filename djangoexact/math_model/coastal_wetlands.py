import math
def drainage(area_start, percentage_drained_start, percentage_drained_end, rate_type, rate_coefficient, time_impl, time_cap, agb_default, bgb_default, litter_default, deadwood_default,
            soil_1m_default, EF_drainage_default, agb_tier_2, bgb_tier_2,litter_tier_2, deadwood_tier_2, soil_1m_tier_2, EF_drainage_tier_2):

    ####### HELPER FUNCTIONS
    def maximum_soil_emissions_for_area(area_start, area_end, maximum_soil_emissions):
        return max(area_start, area_end) * maximum_soil_emissions

    def calculated_soil_emissions(EF_drainage, maximum_soil_years, time_impl, time_cap, area_start, area_end,rate_type, rate_coefficient):
        return EF_drainage * 44/12 * (min(area_start, area_end) * min(maximum_soil_years, time_impl + time_cap) + time_dependent_soil(rate_type, rate_coefficient, time_impl, time_cap, maximum_soil_years, area_start, area_end))

    def time_dependent_soil(rate_type, rate_coefficient, time_impl, time_cap, maximum_soil_years, area_start, area_end):
        if rate_type == 'I':
            if area_end > area_start:
                return area_end * min(maximum_soil_years, time_impl + time_cap)
            else:
                return 0
        else:
            if area_start > area_end:
                return (area_start - area_end) * time_dependent_soil_area_start_bigger(time_impl, time_cap, maximum_soil_years, rate_type, rate_coefficient)
            else:
                return (area_end - area_start) * time_dependent_soil_area_end_bigger(time_impl, time_cap, maximum_soil_years, rate_type, rate_coefficient)

    def time_dependent_soil_area_start_bigger(time_impl, time_cap, maximum_soil_years, rate_type, rate_coefficient):
        if time_impl > maximum_soil_years:
            if rate_type == 'D':
                return time_impl - (math.exp(time_impl - maximum_soil_years,2)/(2 * time_impl))
            else:
                return (0.215*time_impl)-(time_impl/4.6)*math.exp(-92.1/time_impl - 0.01)
        else:
            return time_impl * (1 - rate_coefficient)
    
    def time_dependent_soil_area_end_bigger(time_impl, time_cap, maximum_soil_years, rate_type, rate_coefficient):
        if time_impl + time_cap > time_impl + maximum_soil_years:
            return maximum_soil_years
        else:
            if time_impl + time_cap < maximum_soil_years:
                return time_impl * rate_coefficient + time_cap
            else:
                return min(maximum_soil_years, time_impl)


    """
    area_start: area at start of the period, expects float
    area_end: area at end of the period (either w or wo), expects float
    rate_type: type of rate, expects string
    rate_coefficient: coefficient of rate, expects float
    time_impl: implementation time, expects float
    time_cap: time of cap, expects float


    agb_default : match climate moisture and type of vegetation to IPCC A2903, if present return value, else 0
    bgb_default : match climate moisture and type of vegetation to IPCC A2111, if present return value, else 0
    litter_default : match climate moisture and type of vegetation to IPCC A2128, if present return value, else 0
    deadwood_default : match climate moisture and type of vegetation to IPCC A2145, if present return value, else 0 

    soil_1m_default : if type of vegetation == MANGROVE and soil tier == Tier 1:
                                match COUNTRY to table Atwood and take Mg C/ha
                       else:
                            if soil type == 'Mineral':
                                match climate moisture and type of vegetation to IPCC A2162
                            elif soil type == 'Organic':
                                match climate moisture and type of vegetation to IPCC A2179
                            elif soil type == 'Aggregated'
                                match climate moisture and type of vegetation to IPCC A2196
                            else:
                                return 0

    EF_drainage_default : match climate moisture and type of vegetation to IPCC A2213, if present return value, else 0

    agb_tier_2 : tier 2 value, expects float or None
    bgb_tier_2 : tier 2 value, expects float or None
    litter_tier_2 : tier 2 value, expects float or None
    deadwood_tier_2 : tier 2 value, expects float or None
    soil_1m_tier_2 : tier 2 value, expects float or None
    EF_drainage_tier_2 : tier 2 value, expects float or None
    
    """

    agb = agb_default * 0.451 if not agb_tier_2 else agb_tier_2
    bgb = bgb_default * agb if not bgb_tier_2 else bgb_tier_2
    litter = litter_default if not litter_tier_2 else litter_tier_2
    deadwood = deadwood_default if not deadwood_tier_2 else deadwood_tier_2
    soil_1m = soil_1m_default if not soil_1m_tier_2 else soil_1m_tier_2
    EF_drainage = EF_drainage_default if not EF_drainage_tier_2 else EF_drainage_tier_2

    # ask Lorenzo about this variable
    stock_c_biomass_start = 0
    area_drained_end = area_start * percentage_drained_end
    area_drained_start = area_start * percentage_drained_start
    


    stock_c_biomass_end = (agb + bgb + litter + deadwood) * area_drained_end
    total_emissions_biomass = (stock_c_biomass_start - stock_c_biomass_end) * (44/12)

    maximum_soil_years = 1000 if EF_drainage == 0 else int(soil_1m/EF_drainage)
    maximum_soil_emissions = soil_1m * 44/12

    # HERE THERE IS A 0 IN AREA_DRAINED_START ERROR?
    # total_soil_emissions = min(maximum_soil_emissions_for_area(area_drained_start, area_drained_end, maximum_soil_emissions), calculated_soil_emissions(EF_drainage, maximum_soil_years, time_impl, time_cap, area_drained_start, area_drained_end,rate_type, rate_coefficient))
    total_soil_emissions = min(maximum_soil_emissions_for_area(0, area_drained_end, maximum_soil_emissions), calculated_soil_emissions(EF_drainage, maximum_soil_years, time_impl, time_cap, 0, area_drained_end,rate_type, rate_coefficient))


    return total_soil_emissions + total_emissions_biomass

def rewetting_revegetation(agb_default, bgb_default, litter_default, deadwood_default, ef_rewetting_carbon_default, ef_rewetting_methane_default, agb_tier_2, bgb_tier_2, litter_tier_2, 
                            deadwood_tier_2, ef_rewetting_carbon_tier_2, ef_rewetting_methane_tier_2, soil_type, area_start, area_end, rate_type, rate_coefficient, time_impl, time_cap, methane_constant):


    def co2_methane_emissions(time_impl, time_cap, rate_type, rate_coefficient):

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


    """
    agb_default : match climate moisture and type of vegetation to IPCC A2903, if present return value, else 0
    bgb_default : match climate moisture and type of vegetation to IPCC A2111, if present return value, else 0
    litter_default : match climate moisture and type of vegetation to IPCC A2128, if present return value, else 0
    deadwood_default : match climate moisture and type of vegetation to IPCC A2145, if present return value, else 0 
    ef_rewetting_carbon_default : match climate moisture and type of vegetation to IPCC A2230, if present return value, else 0 
    ef_rewetting_methane_default : match climate moisture and type of vegetation to IPCC A2247, if present return value, else 0 (there is logic for this but it will be addressed later)

    agb_tier_2 : tier 2 value, expects float or None
    bgb_tier_2 : tier 2 value, expects float or None
    litter_tier_2 : tier 2 value, expects float or None
    deadwood_tier_2 : tier 2 value, expects float or None
    ef_rewetting_carbon_tier_2 : tier 2 value, expects float or None
    ef_rewetting_methane_tier_2 : tier 2 value, expects float or None

    soil_type: soil type (front end input), expects string
    """
    ef_rewetting_methane_default = 0 if not soil_type == '<18' else ef_rewetting_methane_default

    agb = agb_default * 0.451 if not agb_tier_2 else agb_tier_2
    bgb = bgb_default * agb if not bgb_tier_2 else bgb_tier_2
    litter = litter_default if not litter_tier_2 else litter_tier_2
    deadwood = deadwood_default if not deadwood_tier_2 else deadwood_tier_2
    ef_rewetting_carbon = ef_rewetting_carbon_default if not ef_rewetting_carbon_tier_2 else ef_rewetting_carbon_tier_2
    ef_rewetting_methane = ef_rewetting_methane_default if not ef_rewetting_methane_tier_2 else ef_rewetting_methane_tier_2

    yearly_carbon = area_end * ef_rewetting_carbon
    yearly_methane = area_end * ef_rewetting_methane / 1000

    total_carbon = 44/12 * yearly_carbon * co2_methane_emissions(time_impl, time_cap, rate_type, rate_coefficient)
    total_methane = methane_constant * yearly_methane * co2_methane_emissions(time_impl, time_cap, rate_type, rate_coefficient)

    return total_carbon + total_methane

def coastal_waterbodies(area_start, area_end, trophic_state_default, methane_emission_factor_default, trophic_state_tier_2, methane_emission_factor_start_tier_2, 
                        methane_emission_factor_end_tier_2,  methane_constant, time_cap, time_impl, rate_coefficient, chlo_A,):
    
    # this function is the same as flooded rice ch4 calculation, that's why it says area
    def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):
        if area > area_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)
    
    trophic_state = trophic_state_default if not chlo_A else 0.26 * chlo_A
    trophic_state = trophic_state_default if not trophic_state_tier_2 else trophic_state_tier_2
    methane_emission_factor_end = methane_emission_factor_default if not methane_emission_factor_end_tier_2 else methane_emission_factor_end_tier_2
    methane_emission_factor_start = methane_emission_factor_default if not methane_emission_factor_start_tier_2 else methane_emission_factor_start_tier_2

    yearly_emissions_start = area_start * trophic_state * methane_emission_factor_start / 1000 * methane_constant
    yearly_emissions_end = area_end * trophic_state * methane_emission_factor_end / 1000 * methane_constant

    total_emissions = (min(yearly_emissions_start, yearly_emissions_end) * (time_cap + time_impl) + abs(yearly_emissions_start - yearly_emissions_end) * time_dependency(yearly_emissions_end, yearly_emissions_start, rate_coefficient, time_impl, time_cap))
    
    return total_emissions

def extraction_and_excavation_w_wo(area_start, percentage_excavated_w, percentage_excavated_wo, agb_default, bgb_default, litter_default, deadwood_default, 
                                soil_1m_default, percentage_c_lost_excavation_default, agb_tier_2, bgb_tier_2,
                                litter_tier_2, deadwood_tier_2, soil_1m_tier_2, percentage_c_lost_excavation_tier_2):

    """
    agb_default : match climate moisture and type of vegetation to IPCC A2903, if present return value, else 0
    bgb_default : match climate moisture and type of vegetation to IPCC A2111, if present return value, else 0
    litter_default : match climate moisture and type of vegetation to IPCC A2128, if present return value, else 0
    deadwood_default : match climate moisture and type of vegetation to IPCC A2145, if present return value, else 0 

    soil_1m_default : if type of vegetation == MANGROVE and soil tier == Tier 1:
                                match COUNTRY to table Atwood and take Mg C/ha
                       else:
                            if soil type == 'Mineral':
                                match climate moisture and type of vegetation to IPCC A2162
                            elif soil type == 'Organic':
                                match climate moisture and type of vegetation to IPCC A2179
                            elif soil type == 'Aggregated'
                                match climate moisture and type of vegetation to IPCC A2196
                            else:
                                return 0

    percentage_c_lost_excavation_default : standard value, 96%, discuss and ask whether to include in model directly

    agb_tier_2 : tier 2 value, expects float or None
    bgb_tier_2 : tier 2 value, expects float or None
    litter_tier_2 : tier 2 value, expects float or None
    deadwood_tier_2 : tier 2 value, expects float or None
    soil_1m_tier_2 : tier 2 value, expects float or None
    percentage_c_lost_excavation_tier_2 : tier 2 value, expects float or None
    
    """
    # THIS VARIABLE IS SET TO 0 AS DEFAULT ON THE EXCEL, ASK LORENZO
    area_excavated_start = 0

    area_excavated_w = area_start * percentage_excavated_w
    area_excavated_wo = area_start * percentage_excavated_wo

    agb = agb_default * 0.451 if not agb_tier_2 else agb_tier_2
    bgb = bgb_default * agb if not bgb_tier_2 else bgb_tier_2
    litter = litter_default if not litter_tier_2 else litter_tier_2
    deadwood = deadwood_default if not deadwood_tier_2 else deadwood_tier_2
    soil_1m = soil_1m_default if not soil_1m_tier_2 else soil_1m_tier_2
    percentage_c_lost_excavation = percentage_c_lost_excavation_default if not percentage_c_lost_excavation_tier_2 else percentage_c_lost_excavation_tier_2

    biomass_c = agb + bgb + litter + deadwood
    soil_c = soil_1m * percentage_c_lost_excavation

    biomass_co2 = biomass_c * 44/12
    soil_co2 = soil_c * 44/12

    total_wo = (biomass_co2 + soil_co2) * (area_excavated_wo - area_excavated_start)
    total_w = (biomass_co2 + soil_co2) * (area_excavated_w - area_excavated_start)

    balance = total_w + total_wo

    return total_w, total_wo, balance

def rewetting_w_wo(agb_default_rewetting, bgb_default_rewetting, litter_default_rewetting, deadwood_default_rewetting, EF_rewetting_carbon_default, EF_rewetting_methane_default,
                                        agb_rewetting_tier_2, bgb_rewetting_tier_2, litter_rewetting_tier_2, deadwood_rewetting_tier_2, EF_rewetting_carbon_tier_2, EF_rewetting_methane_tier_2,
                                        soil_type_rewetting, area_start_rewetting, area_rewetting_w, rate_type_rewetting_w, rate_coefficient_rewetting_w, time_impl, time_cap, methane_constant,
                                        area_rewetting_wo, rate_type_rewetting_wo, rate_coefficient_rewetting_wo):
    
    """
    REWETTING:
        agb_default_rewetting: match climate moisture and type of vegetation to IPCC A2903, if present return value, else 0
        bgb_default_rewetting: match climate moisture and type of vegetation to IPCC A2111, if present return value, else 0
        litter_default_rewetting: match climate moisture and type of vegetation to IPCC A2128, if present return value, else 0
        deadwood_default_rewetting: match climate moisture and type of vegetation to IPCC A2145, if present return value, else 0
        EF_rewetting_carbon_default: match climate moisture and type of vegetation to IPCC A2230, if present return value, else 0
        EF_rewetting_methane_default: match climate moisture and type of vegetation to IPCC A2247, if present return value, else 0
        agb_rewetting_tier_2: tier 2 value, expects float or None
        bgb_rewetting_tier_2: tier 2 value, expects float or None
        litter_rewetting_tier_2: tier 2 value, expects float or None
        deadwood_rewetting_tier_2: tier 2 value, expects float or None
        EF_rewetting_carbon_tier_2: tier 2 value, expects float or None
        EF_rewetting_methane_tier_2: tier 2 value, expects float or None
        soil_type_rewetting: front end input
        area_start_rewetting: front end input
        area_rewetting_w: front end input
        rate_type_rewetting_w: front end input
        rate_coefficient_rewetting_w: as always, search for rate type in reference table
        time_impl: input in 1.Description
        time_cap: input in 1.Description
        methane_constant: input in 1.Description
        area_rewetting_wo: front end input
        rate_type_rewetting_wo: front end input
        rate_coefficient_rewetting_wo: as always, search for rate type in reference table
    """

    rewetting_w = rewetting_revegetation(agb_default_rewetting, bgb_default_rewetting, litter_default_rewetting, deadwood_default_rewetting, EF_rewetting_carbon_default, EF_rewetting_methane_default,
                                        agb_rewetting_tier_2, bgb_rewetting_tier_2, litter_rewetting_tier_2, deadwood_rewetting_tier_2, EF_rewetting_carbon_tier_2, EF_rewetting_methane_tier_2,
                                        soil_type_rewetting, area_start_rewetting, area_rewetting_w, rate_type_rewetting_w, rate_coefficient_rewetting_w, time_impl, time_cap, methane_constant)
    
    rewetting_wo = rewetting_revegetation(agb_default_rewetting, bgb_default_rewetting, litter_default_rewetting, deadwood_default_rewetting, EF_rewetting_carbon_default, EF_rewetting_methane_default,
                                        agb_rewetting_tier_2, bgb_rewetting_tier_2, litter_rewetting_tier_2, deadwood_rewetting_tier_2, EF_rewetting_carbon_tier_2, EF_rewetting_methane_tier_2,
                                        soil_type_rewetting, area_start_rewetting, area_rewetting_wo, rate_type_rewetting_wo, rate_coefficient_rewetting_wo, time_impl, time_cap, methane_constant)


    return rewetting_w, rewetting_wo, rewetting_w - rewetting_wo

def coastal_waterbodies_w_wo(area_start_waterbodies, area_w_waterbodies, trophic_state_default, methane_emission_factor_default, trophic_state_tier_2, methane_emission_factor_start_tier_2,
                                                methane_emission_factor_w_tier_2, methane_constant, time_cap, time_impl, rate_coefficient_waterbodies_w,area_wo_waterbodies,
                                                methane_emission_factor_wo_tier_2, rate_coefficient_waterbodies_wo, chlo_A_w ):

    """

    COASTAL WATERBODIES:
        area_start_waterbodies: front end input
        area_w_waterbodies: front end input
        trophic_state_default: 0.7 fixed value
        methane_emission_factor_default: Can be seen in Fish and aqua module. Match climate moisture and waterbody type to IPCC A3204, if present return value, else 0
        trophic_state_tier_2: tier 2 value, expects float or None
        methane_emission_factor_start_tier_2: tier 2 value, expects float or None
        methane_emission_factor_w_tier_2: tier 2 value, expects float or None
        methane_constant: input in 1.Description
        time_cap: input in 1.Description
        time_impl: input in 1.Description
        rate_coefficient_waterbodies_w: as always, search for rate type in reference table
        area_wo_waterbodies: front end input
        methane_emission_factor_wo_tier_2: tier 2 value, expects float or None
        rate_coefficient_waterbodies_wo: as always, search for rate type in reference table
        chlo_A_w: front end input

    """

    costal_waterbodies_w = coastal_waterbodies(area_start_waterbodies, area_w_waterbodies, trophic_state_default, methane_emission_factor_default, trophic_state_tier_2, methane_emission_factor_start_tier_2,
                                                methane_emission_factor_w_tier_2, methane_constant, time_cap, time_impl, rate_coefficient_waterbodies_w, chlo_A_w)

    costal_waterbodies_wo = coastal_waterbodies(area_start_waterbodies, area_wo_waterbodies, trophic_state_default, methane_emission_factor_default, trophic_state_tier_2, methane_emission_factor_start_tier_2,
                                                methane_emission_factor_wo_tier_2, methane_constant, time_cap, time_impl, rate_coefficient_waterbodies_wo, chlo_A_w)  


    return costal_waterbodies_w, costal_waterbodies_wo, costal_waterbodies_w - costal_waterbodies_wo

def drainage_w_wo(area_start_extr_drain, percentage_drained_start, percentage_drained_w, rate_type_drainage_w, rate_coefficient_drainage_w, time_impl, time_cap, agb_default_extraction, bgb_default_extraction,
                            litter_default_extraction, deadwood_default_extraction, soil_1m_default_extraction, EF_drainage_default, agb_tier_2_drainage, bgb_tier_2_drainage, litter_tier_2_drainage,
                            deadwood_tier_2_drainage ,soil_1_m_tier_2_drainage, Ef_drainage_tier_2, percentage_drained_wo, rate_type_drainage_wo, rate_coefficient_drainage_wo):


    """
    area_start_extr_drain: front end input
    percentage_drained_start: front end input
    percentage_drained_w: front end input
    rate_type_drainage_w: front end input
    rate_coefficient_drainage_w: as always, search for rate type in reference table
    time_impl: input in 1.Description
    time_cap: input in 1.Description
    agb_default_extraction: match climate moisture and type of vegetation to IPCC A2093, if present return value, else 0
    bgb_default_extraction: match climate moisture and type of vegetation to IPCC A2111, if present return value, else 0
    litter_default_extraction: match climate moisture and type of vegetation to IPCC A2128, if present return value, else 0
    deadwood_default_extraction: match climate moisture and type of vegetation to IPCC A2145, if present return value, else 0 

    soil_1m_default_extraction: if type of vegetation == MANGROVE and soil tier == Tier 1:
                                        match COUNTRY to table Atwood and take Mg C/ha
                                else:
                                        if soil type == 'Mineral':
                                            match climate moisture and type of vegetation to IPCC A2162
                                        elif soil type == 'Organic':
                                            match climate moisture and type of vegetation to IPCC A2179
                                        elif soil type == 'Aggregated'
                                            match climate moisture and type of vegetation to IPCC A2196
                                        else:
                                            return 0
    EF_drainage_default: match climate moisture and type of vegetation to IPCC A2213, if present return value, else 0
    agb_tier_2_drainage: tier 2 value, expects float or None
    bgb_tier_2_drainage: tier 2 value, expects float or None
    litter_tier_2_drainage: tier 2 value, expects float or None
    deadwood_tier_2_drainage: tier 2 value, expects float or None
    soil_1_m_tier_2_drainage: tier 2 value, expects float or None
    Ef_drainage_tier_2: tier 2 value, expects float or None
    percentage_drained_wo: front end input
    rate_type_drainage_wo: front end input
    rate_coefficient_drainage_wo: as always, search for rate type in reference table
    """

    drainage_w = drainage(area_start_extr_drain, percentage_drained_start, percentage_drained_w, rate_type_drainage_w, rate_coefficient_drainage_w, time_impl, time_cap, agb_default_extraction, bgb_default_extraction,
                            litter_default_extraction, deadwood_default_extraction, soil_1m_default_extraction, EF_drainage_default, agb_tier_2_drainage, bgb_tier_2_drainage, litter_tier_2_drainage,
                            deadwood_tier_2_drainage ,soil_1_m_tier_2_drainage, Ef_drainage_tier_2)

    drainage_wo = drainage(area_start_extr_drain, percentage_drained_start, percentage_drained_wo, rate_type_drainage_wo, rate_coefficient_drainage_wo, time_impl, time_cap, agb_default_extraction, bgb_default_extraction,
                            litter_default_extraction, deadwood_default_extraction, soil_1m_default_extraction, EF_drainage_default, agb_tier_2_drainage,  bgb_tier_2_drainage, litter_tier_2_drainage, deadwood_tier_2_drainage,
                            soil_1_m_tier_2_drainage, Ef_drainage_tier_2)

    return drainage_w, drainage_wo, drainage_w - drainage_wo

def extraction_and_drainage_w_wo(area_start_extr_drain, percentage_excavated_w, percentage_excavated_wo, agb_default_extraction, bgb_default_extraction, litter_default_extraction, deadwood_default_extraction,
                                                            soil_1m_default_extraction, percentage_c_lost_excavation_default, agb_tier_2_extraction, bgb_tier_2_extraction, litter_tier_2_extraction, deadwood_tier_2_extraction,
                                                            soil_1m_tier_2_extraction, percentage_c_lost_excavation_tier_2, percentage_drained_start, percentage_drained_w, rate_type_drainage_w, rate_coefficient_drainage_w, time_impl, time_cap, 
                                                            EF_drainage_default, agb_tier_2_drainage, bgb_tier_2_drainage, litter_tier_2_drainage, deadwood_tier_2_drainage ,soil_1_m_tier_2_drainage, Ef_drainage_tier_2,
                                                            percentage_drained_wo, rate_type_drainage_wo, rate_coefficient_drainage_wo
                                                            ):
    """
    area_start_extr_drain: front end input
    percentage_excavated_w: front end input
    percentage_excavated_wo: front end input
    agb_default_extraction: match climate moisture and type of vegetation to IPCC A2093, if present return value, else 0
    bgb_default_extraction: match climate moisture and type of vegetation to IPCC A2111, if present return value, else 0
    litter_default_extraction: match climate moisture and type of vegetation to IPCC A2128, if present return value, else 0
    deadwood_default_extraction: match climate moisture and type of vegetation to IPCC A2145, if present return value, else 0 

    soil_1m_default_extraction: if type of vegetation == MANGROVE and soil tier == Tier 1:
                                        match COUNTRY to table Atwood and take Mg C/ha
                                else:
                                        if soil type == 'Mineral':
                                            match climate moisture and type of vegetation to IPCC A2162
                                        elif soil type == 'Organic':
                                            match climate moisture and type of vegetation to IPCC A2179
                                        elif soil type == 'Aggregated'
                                            match climate moisture and type of vegetation to IPCC A2196
                                        else:
                                            return 0


    percentage_c_lost_excavation_default: standard value, 96%, discuss and ask whether to include in model directly
    agb_tier_2_extraction: tier 2 value, expects float or None
    bgb_tier_2_extraction: tier 2 value, expects float or None
    litter_tier_2_extraction: tier 2 value, expects float or None
    deadwood_tier_2_extraction: tier 2 value, expects float or None
    soil_1m_tier_2_extraction: tier 2 value, expects float or None
    percentage_c_lost_excavation_tier_2: tier 2 value, expects float or None
    percentage_drained_start: front end input
    percentage_drained_w: front end input
    rate_type_drainage_w: front end input
    rate_coefficient_drainage_w: as usual, obtained matching the rate type to the reference table
    time_impl: front end input
    time_cap: front end input
    EF_drainage_default: match climate moisture and type of vegetation to IPCC A2213, if present return value, else 0
    agb_tier_2_drainage: tier 2 value, expects float or None
    bgb_tier_2_drainage: tier 2 value, expects float or None
    litter_tier_2_drainage: tier 2 value, expects float or None
    deadwood_tier_2_drainage: tier 2 value, expects float or None   
    soil_1_m_tier_2_drainage: tier 2 value, expects float or None
    Ef_drainage_tier_2: tier 2 value, expects float or None
    percentage_drained_wo: front end input
    rate_type_drainage_wo: front end input
    rate_coefficient_drainage_wo: as usual, obtained matching the rate type to the reference table
    """

    extraction_w, extraction_wo, _ = extraction_and_excavation_w_wo(area_start_extr_drain, percentage_excavated_w, percentage_excavated_wo, agb_default_extraction, bgb_default_extraction, litter_default_extraction, deadwood_default_extraction,
                                                            soil_1m_default_extraction, percentage_c_lost_excavation_default, agb_tier_2_extraction, bgb_tier_2_extraction, litter_tier_2_extraction, deadwood_tier_2_extraction,
                                                            soil_1m_tier_2_extraction, percentage_c_lost_excavation_tier_2)
    
    drainage_w, drainage_wo, _ = drainage_w_wo(area_start_extr_drain, percentage_drained_start, percentage_drained_w, rate_type_drainage_w, rate_coefficient_drainage_w, time_impl, time_cap, agb_default_extraction, bgb_default_extraction,
                            litter_default_extraction, deadwood_default_extraction, soil_1m_default_extraction, EF_drainage_default, agb_tier_2_drainage, bgb_tier_2_drainage, litter_tier_2_drainage,
                            deadwood_tier_2_drainage ,soil_1_m_tier_2_drainage, Ef_drainage_tier_2, percentage_drained_wo, rate_type_drainage_wo, rate_coefficient_drainage_wo)


    return drainage_w + extraction_w, drainage_wo + extraction_wo, drainage_w + extraction_w - drainage_wo - extraction_wo

