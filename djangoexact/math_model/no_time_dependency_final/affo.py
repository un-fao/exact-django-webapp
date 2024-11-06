import traceback
from .general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions

class Afforestation:

    def __init__(self, hectars_end, time_impl, time_cap, initial_biomass, initial_biomass_tier_2, fire_bool, nitrous, methane, 
                    emission_factor_ch4, emission_factor_n2o, combusted_fraction, rate_type, rate,
                    flu, soc_default, soc_tier_2, dead_wood_c_default,
                    dead_wood_c_tier_2, litter_c_default, litter_c_tier_2, agb_secondary_dm_before_20_years, agb_secondary_dm_after_20_years, 
                    bgb_secondary_dm_before_20_years_param, bgb_secondary_dm_after_20_years_param, agb_secondary_c_before_20_years_tier_2, 
                    agb_secondary_c_after_20_years_tier_2, bgb_secondary_c_before_20_years_tier_2, bgb_secondary_c_after_20_years_tier_2,
                    reference_carbon_stocks_tier_2, abg_biomass, rate_bgb_agb_s_125, rate_bgb_agb_b_125
                    ):
        
        self.hectars_end = hectars_end 
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.initial_biomass = initial_biomass
        self.initial_biomass_tier_2 = initial_biomass_tier_2
        self.fire_bool = fire_bool
        self.nitrous = nitrous
        self.methane = methane
        self.emission_factor_ch4 = emission_factor_ch4
        self.emission_factor_n2o = emission_factor_n2o
        self.combusted_fraction = combusted_fraction
        self.rate_type = rate_type
        self.rate = rate
        self.flu = flu
        self.soc_default = soc_default
        self.soc_tier_2 = soc_tier_2
        self.dead_wood_c_default = dead_wood_c_default
        self.dead_wood_c_tier_2 = dead_wood_c_tier_2
        self.litter_c_default = litter_c_default
        self.litter_c_tier_2 = litter_c_tier_2
        self.agb_secondary_dm_before_20_years = agb_secondary_dm_before_20_years
        self.agb_secondary_dm_after_20_years = agb_secondary_dm_after_20_years
        self.bgb_secondary_dm_before_20_years_param = bgb_secondary_dm_before_20_years_param
        self.bgb_secondary_dm_after_20_years_param = bgb_secondary_dm_after_20_years_param  
        self.agb_secondary_c_before_20_years_tier_2 = agb_secondary_c_before_20_years_tier_2
        self.agb_secondary_c_after_20_years_tier_2 = agb_secondary_c_after_20_years_tier_2
        self.bgb_secondary_c_before_20_years_tier_2 = bgb_secondary_c_before_20_years_tier_2
        self.bgb_secondary_c_after_20_years_tier_2 = bgb_secondary_c_after_20_years_tier_2
        self.reference_carbon_stocks_tier_2 = reference_carbon_stocks_tier_2
        self.abg_biomass = abg_biomass
        self.rate_bgb_agb_s_125 = rate_bgb_agb_s_125
        self.rate_bgb_agb_b_125 = rate_bgb_agb_b_125

        # Breakdown of hectars
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(0, self.hectars_end, self.time_impl, self.time_cap, self.rate)

        # Results
        self.yearly_biomass_gain_emissions = []
        self.total_biomass_gain_emissions = 0

        self.yearly_dom_emissions = []
        self.total_dom_emissions = 0

        self.yearly_biomass_loss_emissions = []
        self.total_biomass_loss_emissions = 0

        self.yearly_soil_emissions = []
        self.total_soil_emissions = 0

        self.yearly_fire_emissions = []
        self.total_fire_emissions = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

    def calculate_emissions(self):

        def calculate_biomass_gain():

            def max_co2_above_below_ground(agb_biomass, rate_under_125, rate_over_125):

                if agb_biomass <= 125:
                    return (agb_biomass + agb_biomass * rate_under_125) * 0.47 * 44/12
                else:
                    return (agb_biomass + agb_biomass * rate_over_125) * 0.47 * 44/12
                
            try:
                max_co2_agb_bgb = self.reference_carbon_stocks_tier_2 * 44/12 if self.reference_carbon_stocks_tier_2 else max_co2_above_below_ground(self.abg_biomass, self.rate_bgb_agb_s_125, self.rate_bgb_agb_b_125)
        
                agb_secondary_c_before_20_years = self.agb_secondary_dm_before_20_years * 0.47 if not self.agb_secondary_c_before_20_years_tier_2 else self.agb_secondary_c_before_20_years_tier_2
                agb_secondary_c_after_20_years = self.agb_secondary_dm_after_20_years * 0.47 if not self.agb_secondary_c_after_20_years_tier_2 else self.agb_secondary_c_after_20_years_tier_2

                bgb_secondary_dm_before_20_years = self.bgb_secondary_dm_before_20_years_param * self.agb_secondary_dm_before_20_years
                bgb_secondary_dm_after_20_years = self.bgb_secondary_dm_after_20_years_param * self.agb_secondary_dm_after_20_years

                bgb_secondary_c_before_20_years = bgb_secondary_dm_before_20_years * 0.47 if not self.bgb_secondary_c_before_20_years_tier_2 else self.bgb_secondary_c_before_20_years_tier_2
                bgb_secondary_c_after_20_years = bgb_secondary_dm_after_20_years * 0.47 if not self.bgb_secondary_c_after_20_years_tier_2 else self.bgb_secondary_c_after_20_years_tier_2

                tot_biomass_growth_after_20_years = bgb_secondary_c_after_20_years + agb_secondary_c_after_20_years
                tot_biomass_growth_before_20_years = bgb_secondary_c_before_20_years + agb_secondary_c_before_20_years

                total_area_after_20_years = sum(self.hectars_after_20) * tot_biomass_growth_after_20_years
                total_area_before_20_years = sum(self.hectars_before_20) * tot_biomass_growth_before_20_years
                
                yearly_before_20 = breakdown_according_to_values(total_area_before_20_years, self.hectars_before_20)
                yearly_after_20 = breakdown_according_to_values(total_area_after_20_years, self.hectars_after_20)

                total_yearly = [i + j for i, j in zip(yearly_before_20, yearly_after_20)]

                # If the emissions are bigger than the maximum we consider the maximum and breakdown the values accordingly
                if sum(total_yearly) > max_co2_agb_bgb:
                    total_yearly = breakdown_according_to_values(max_co2_agb_bgb, total_yearly)

                self.yearly_biomass_gain_emissions = total_yearly
                self.total_biomass_gain_emissions = sum(total_yearly)
            
            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_dom_emissions():

            try:
                dead_wood_c = self.dead_wood_c_tier_2 if self.dead_wood_c_tier_2 else self.dead_wood_c_default
                litter_c = self.litter_c_tier_2 if self.litter_c_tier_2 else self.litter_c_default
                dom_c = dead_wood_c + litter_c
                dom_co2 = dom_c * (-44/12)
                dom_emissions = dom_co2 * self.hectars_end

                self.yearly_dom_emissions = yearly_constant_emissions_breakdown(dom_emissions, self.time_impl, self.time_cap)
                self.total_dom_emissions = sum(self.yearly_dom_emissions)
            
            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_biomass_loss():

            try:
                biomass_converted = self.initial_biomass_tier_2 if self.initial_biomass_tier_2 else self.initial_biomass
                biomass_loss = biomass_converted * self.hectars_end * (44/12)

                self.yearly_biomass_loss_emissions = yearly_constant_emissions_breakdown(biomass_loss, self.time_impl, self.time_cap)
                self.total_biomass_loss_emissions = sum(self.yearly_biomass_loss_emissions)

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_soil_emissions():

            try:
                self.yearly_soil_emissions, self.total_soil_emissions = soil_emissions(self.hectars_before_20, 0, self.hectars_end, self.soc_default, self.soc_tier_2, None, None, None, self.flu)
            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_fire_emissions():

            try:
                biomass_converted = self.initial_biomass_tier_2 if self.initial_biomass_tier_2 else self.initial_biomass

                combustion_mass = biomass_converted / 0.4 
                biomass_ch4 = combustion_mass * self.combusted_fraction * self.emission_factor_ch4
                biomass_n2o = combustion_mass * self.combusted_fraction * self.emission_factor_n2o
                biomass_tco2 = (biomass_ch4 * self.methane + biomass_n2o * self.nitrous) / 1000

                fire_emissions_w = self.hectars_end * biomass_tco2 if self.fire_bool else 0
                
                self.yearly_fire_emissions = yearly_constant_emissions_breakdown(fire_emissions_w, self.time_impl, self.time_cap)
                self.total_fire_emissions = sum(self.yearly_fire_emissions)
            
            except Exception as e:
                traceback.print_exc()
                raise e

        calculate_biomass_gain()
        calculate_dom_emissions()
        calculate_biomass_loss()
        calculate_soil_emissions()
        calculate_fire_emissions()

        try:
            self.emissions_total_yearly = [i + j + k + l + n for i, j, k, l, n in zip(self.yearly_biomass_gain_emissions, self.yearly_dom_emissions, self.yearly_biomass_loss_emissions, self.yearly_soil_emissions, self.yearly_fire_emissions)]
            self.total_emissions = sum(self.emissions_total_yearly)

            return self.total_emissions

        except Exception as e:
            traceback.print_exc()
            raise e

    def evaluate_tier_2():
        pass


