import math
from .general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions
import traceback

class GrasslandManagement:

    def __init__(self, area_start, area_end, time_impl, time_cap, rate, nitrous_constant, methane_constant,
                            fire_interval, fire_used, methane_ef, nitrous_ef, agb_ref, agb_tier_2, cf_ref, cf_tier_2,
                            soc_start_ref, soc_start_tier_2, soc_end_ref, soc_end_tier_2):
        
        self.area_start = area_start
        self.area_end = area_end
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate = rate
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.fire_interval = fire_interval # front-end input, years between two fires, default is 5 (on front-end)
        self.fire_used = fire_used # front-end input, states whether fire has been used
        self.methane_ef = methane_ef # tabulated value IPCC D75 (value for Savanna and Grassland)
        self.nitrous_ef = nitrous_ef # tabulated value IPCC E75 (value for Savanna and Grassland)
        self.agb_ref = agb_ref # taken from IPCC A553 matching clim_moist to rows
        self.agb_tier_2 = agb_tier_2 # tier 2 value, expects float or None
        self.cf_ref = cf_ref # default is 77%, not tabulated
        self.cf_tier_2 = cf_tier_2 # tier 2 value, expects float or None   
        self.soc_start_ref = soc_start_ref # lookup state_start in table in grass! W28-Y33
        self.soc_start_tier_2 = soc_start_tier_2 # tier 2 value, expects float or None
        self.soc_end_ref = soc_end_ref # lookup state_end_w in table in grass! W28-Y33
        self.soc_end_tier_2 = soc_end_tier_2 # tier 2 value, expects float or None

        # Space for the results
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(area_start, area_end ,self.time_impl, self.time_cap, self.rate)
        self.total_hectars = yearly_time_dependent_parameter_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate, interim_values = True)
        # DEFAULTS FOR TIER 2 VALUES INITIALIZATION

        # RESULTS
        self.emissions_residue_burning_yearly = []
        self.emissions_residue_burning_total = 0

        self.emissions_soil_yearly = []
        self.emissions_soil_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        return
    
    def calculate_emissions(self,):

        def calculate_residue_burning():
            
            try:
                if self.time_impl + self.time_cap < self.fire_interval or not self.fire_used:
                    self.emissions_residue_burning_yearly = [0 for i in range(self.time_impl + self.time_cap)]
                    self.emissions_residue_burning_total = 0
                
                else:
                    agb = self.agb_ref if not self.agb_tier_2 else self.agb_tier_2
                    cf = self.cf_ref if not self.cf_tier_2 else self.cf_tier_2
                    agb_cf_gef = agb * cf * (self.methane_ef * self.methane_constant + self.nitrous_ef * self.nitrous_constant) / 1000
                    annual_co2 = agb_cf_gef / self.fire_interval

                    total = annual_co2 * sum(self.total_hectars)
                    self.emissions_residue_burning_yearly = breakdown_according_to_values(total, self.total_hectars)
                    self.emissions_residue_burning_total = total
                return
            except:
                traceback.print_exc()
                return 
            
        def calculate_soil_emissions():

            try:
                soc_start = self.soc_start_ref if not self.soc_start_tier_2 else self.soc_start_tier_2
                soc_end = self.soc_end_ref if not self.soc_end_tier_2 else self.soc_end_tier_2
                delta_co2_mineral_per_ha_per_yr = - (soc_end - soc_start) / 20 * (44/12)


                calculated = delta_co2_mineral_per_ha_per_yr * sum(self.total_hectars)
                tabular = max(self.area_start, self.area_end) * delta_co2_mineral_per_ha_per_yr * 20
                
                total = tabular if abs(calculated) >= abs(tabular) else calculated

                self.emissions_soil_yearly = breakdown_according_to_values(total, self.total_hectars)
                self.emissions_soil_total = total
                return
            except:
                traceback.print_exc()
                return

            
        calculate_residue_burning()
        calculate_soil_emissions()

        try:
            self.emissions_total_yearly = [x + y for x, y in zip(self.emissions_residue_burning_yearly, self.emissions_soil_yearly)]
            self.total_emissions = sum(self.emissions_total_yearly)
            return self.total_emissions

        except Exception as e:
            traceback.print_exc()
            return None

    def evaluate_tier_2_defaults():
        pass

