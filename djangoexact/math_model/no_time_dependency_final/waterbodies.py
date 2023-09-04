import traceback
from general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions

class CoastalWaterbodies:

    def __init__(self, area_start, area_end, trophic_state_default, methane_emission_factor_default, trophic_state_tier_2, methane_emission_factor_start_tier_2, 
                methane_emission_factor_end_tier_2,  methane_constant, time_cap, time_impl, rate, chlo_A,):
        
        self.area_start = area_start
        self.area_end = area_end
        self.trophic_state_default = trophic_state_default
        self.methane_emission_factor_default = methane_emission_factor_default
        self.trophic_state_tier_2 = trophic_state_tier_2
        self.methane_emission_factor_start_tier_2 = methane_emission_factor_start_tier_2
        self.methane_emission_factor_end_tier_2 = methane_emission_factor_end_tier_2
        self.methane_constant = methane_constant
        self.time_cap = time_cap
        self.time_impl = time_impl
        self.rate = rate
        self.chlo_A = chlo_A

        # HECTARES BREAKDOWN
        self.hectares = yearly_time_dependent_parameter_breakdown(self.area_start, self.area_end, self.time_impl, self.time_cap, self.rate)
        
        # RESULTS
        self.emissions_yearly = []
        self.total_emissions = 0

        pass

    def calculate_emissions(self, ):

        try:

            # TODO: see if on FIGMA there are more start-end values, in that case they can just be added and calculation can be done on two rows
            trophic_state = self.trophic_state_default if not self.chlo_A else 0.26 * self.chlo_A
            trophic_state = self.trophic_state_default if not self.trophic_state_tier_2 else self.trophic_state_tier_2
            methane_emission_factor_end = self.methane_emission_factor_default if not self.methane_emission_factor_end_tier_2 else self.methane_emission_factor_end_tier_2
            methane_emission_factor_start = self.methane_emission_factor_default if not self.methane_emission_factor_start_tier_2 else self.methane_emission_factor_start_tier_2

            yearly_emissions_start = self.area_start * trophic_state * methane_emission_factor_start / 1000 * self.methane_constant
            yearly_emissions_end = self.area_end * trophic_state * methane_emission_factor_end / 1000 * self.methane_constant

            self.emissions_yearly = yearly_time_dependent_parameter_breakdown(yearly_emissions_start, yearly_emissions_end, self.time_impl, self.time_cap, self.rate)
            self.total_emissions = sum(self.emissions_yearly)
        except Exception as e:
            traceback.print_exc()
            pass
        
