import math

def extraction_and_excavation(area_start, percentage_excavated_w, percentage_excavated_wo, agb_default, bgb_default, litter_default, deadwood_default, 
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

def drainage(area_start, area_end, rate_type, rate_coefficient, time_impl, time_cap, agb_default, bgb_default, litter_default, deadwood_default,
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


    stock_c_biomass_end = (agb + bgb + litter + deadwood) * area_end
    total_emissions_biomass = (stock_c_biomass_start - stock_c_biomass_end) * (44/12)

    maximum_soil_years = 1000 if EF_drainage == 0 else int(soil_1m/EF_drainage)
    maximum_soil_emissions = soil_1m * 44/12

    total_soil_emissions = min(maximum_soil_emissions_for_area(area_start, area_end, maximum_soil_emissions), calculated_soil_emissions(EF_drainage, maximum_soil_years, time_impl, time_cap, area_start, area_end,rate_type, rate_coefficient))

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
    ef_rewetting_carbon_default = 0 if not soil_type == '<18' else ef_rewetting_carbon_default

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
                        methane_emission_factor_end_tier_2,  methane_constant, time_cap, time_impl, rate_coefficient):
    
    # this function is the same as flooded rice ch4 calculation, that's why it says area
    def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):
        if area > area_start:
            return time_cap + time_impl * rate_coefficient
        else:
            return time_impl * (1 - rate_coefficient)
    
    trophic_state = trophic_state_default if not trophic_state_tier_2 else trophic_state_tier_2
    methane_emission_factor_end = methane_emission_factor_default if not methane_emission_factor_end_tier_2 else methane_emission_factor_end_tier_2
    methane_emission_factor_start = methane_emission_factor_default if not methane_emission_factor_start_tier_2 else methane_emission_factor_start_tier_2

    yearly_emissions_start = area_start * trophic_state * methane_emission_factor_start / 1000 * methane_constant
    yearly_emissions_end = area_end * trophic_state * methane_emission_factor_end / 1000 * methane_constant

    total_emissions = (min(yearly_emissions_start, yearly_emissions_end) * (time_cap + time_impl) + abs(yearly_emissions_start - yearly_emissions_end) * time_dependency(yearly_emissions_end, yearly_emissions_start, rate_coefficient, time_impl, time_cap))
    
    return total_emissions


extract_losses = extraction_and_excavation(100, 1, 0, 0, 3.65, 0, 0, 226, 0.96, None, None, None, None, None, None)

drainage_losses = drainage(0, 35, 'D', 0.5, 20, 9, 0, 0, 0, 0, 226, 7.9, None, None, None, None, None, None)

rewetting_losses = rewetting_revegetation(0, 0, 0, 0, -0.91, 193.70, None, None, None, None, None, None, '<18', 0, 45, 'D', 0.5, 20, 9, 28)

coastal_losses = coastal_waterbodies(45, 45, 0.7, 30, None, None, None, 28, 20, 9, 0.5)

# EVERYTHING WORKS, JUST ADD A GENERAL FUNCTION FOR WITH AND WITHOUT