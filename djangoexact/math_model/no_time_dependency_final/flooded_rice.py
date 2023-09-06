import math
from .general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions
import traceback

class FloodedRice:

    def __init__(self, area_start, area_end, EFc_ref, EFc_tier_2, SFw_ref, SFw_tier_2, SFp_ref, SFp_tier_2, cfoa, SFo_tier_2, rice_straw, rice_straw_tier_2, yield_ref, yield_tier_2, rice_slope, rice_intercept, straw_tonnes_tier_2, methane_ef, rice_cf, nitrous_ef, nitrous_constant,
                        time_impl, time_cap, rate, methane_constant, cultivation_period_ref, cultivation_period_tier_2,  socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2,
                        ):
        
        self.area_start = area_start
        self.area_end = area_end
        self.EFc_ref = EFc_ref
        self.EFc_tier_2 = EFc_tier_2
        self.SFw_ref = SFw_ref
        self.SFw_tier_2 = SFw_tier_2
        self.SFp_ref = SFp_ref
        self.SFp_tier_2 = SFp_tier_2
        self.cfoa = cfoa
        self.SFo_tier_2 = SFo_tier_2
        self.rice_straw = rice_straw
        self.rice_straw_tier_2 = rice_straw_tier_2
        self.yield_ref = yield_ref
        self.yield_tier_2 = yield_tier_2
        self.rice_slope = rice_slope
        self.rice_intercept = rice_intercept
        self.straw_tonnes_tier_2 = straw_tonnes_tier_2
        self.methane_ef = methane_ef
        self.rice_cf = rice_cf
        self.nitrous_ef = nitrous_ef
        self.nitrous_constant = nitrous_constant
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate = rate
        self.methane_constant = methane_constant
        self.cultivation_period_ref = cultivation_period_ref
        self.cultivation_period_tier_2 = cultivation_period_tier_2
        self.socref = socref
        self.soc_tier_2 = soc_tier_2
        self.f_lu_ref = f_lu_ref
        self.f_lu_tier_2 = f_lu_tier_2
        self.f_i_ref = f_i_ref
        self.f_i_tier_2 = f_i_tier_2
        self.f_mg_ref = f_mg_ref
        self.f_mg_tier_2 = f_mg_tier_2

        # HECTARES
        self.hectares_before_20, self.hectares_after_20 = yearly_time_dependent_20_year_breakdown(area_start, area_end ,self.time_impl, self.time_cap, self.rate)
        self.hectares_total = yearly_time_dependent_parameter_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate)

        # RESULTS
        self.ch4_emitted_yearly = []
        self.ch4_emitted_total = 0

        self.straw_burning_yearly = []
        self.straw_burning_total = 0

        self.soil_emissions_yearly = []
        self.soil_emissions_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0



    def calculate_emissions(self,):

        def calculate_ch4_emitted():
            
            try:
                # TODO: maybe this could be moved to the constructor
                EFc = self.EFc_ref if not self.EFc_tier_2 else self.EFc_tier_2
                SFw = self.SFw_ref if not self.SFw_tier_2 else self.SFw_tier_2
                SFp = self.SFp_ref if not self.SFp_tier_2 else self.SFp_tier_2
                yield_value = self.yield_ref if not self.yield_tier_2 else self.yield_tier_2
                straw_tonnes_ref = yield_value * self.rice_slope + self.rice_intercept if not self.straw_tonnes_tier_2 else self.straw_tonnes_tier_2
                SFo = 1 + straw_tonnes_ref * self.cfoa * 0.59 if not self.SFo_tier_2 else self.SFo_tier_2

                if self.area_start == 0 and self.area_end == 0:
                    adjusted_daily_ef_methane_ref = 0
                else:
                    adjusted_daily_ef_methane_ref = EFc * SFw * SFp * SFo

                cultivation_period = self.cultivation_period_ref if not self.cultivation_period_tier_2 else self.cultivation_period_tier_2

                kg_methane_cultivation_period = adjusted_daily_ef_methane_ref * cultivation_period

                self.ch4_emitted_total = kg_methane_cultivation_period * sum(self.hectares_total) * self.methane_constant / 1000
                self.ch4_emitted_yearly = breakdown_according_to_values(self.ch4_emitted_total, self.hectares_total)
            
            except:
                traceback.print_exc()
                return
            
        def calculate_straw_burning():

            try:
                if self.area_start == 0 and self.area_end == 0:
                    self.straw_burning_yearly = [0 for i in range(self.time_impl + self.time_cap)]
                    self.straw_burning_total = 0
                
                else:
                    yield_value = self.yield_ref if not self.yield_tier_2 else self.yield_tier_2
                    straw_tonnes_ref = yield_value * self.rice_slope + self.rice_intercept if not self.straw_tonnes_tier_2 else self.straw_tonnes_tier_2
                    straw_methane_co2 = straw_tonnes_ref * self.rice_cf * self.methane_ef * self.methane_constant / 1000
                    straw_nitrous_co2 = straw_tonnes_ref * self.rice_cf * self.nitrous_ef * self.nitrous_constant / 1000

                    annual_co2 = straw_methane_co2 + straw_nitrous_co2

                    total = annual_co2 * sum(self.hectares_total)
                    self.straw_burning_yearly = breakdown_according_to_values(total, self.hectares_total)
                    self.straw_burning_total = sum(self.straw_burning_yearly)

            except:
                traceback.print_exc()
                return
            
        def calculate_soil_emissions():

            try:
                self.soil_emissions_yearly, self.soil_emissions_total  = soil_emissions(self.hectares_before_20, self.area_start, self.area_end, self.socref, self.soc_tier_2, self.f_lu_tier_2, 
                                                                                                                    self.f_i_tier_2, self.f_mg_tier_2, self.f_lu_ref, self.f_i_ref, self.f_mg_ref)
            except:
                traceback.print_exc()
                return
            
        calculate_ch4_emitted()
        calculate_straw_burning()
        calculate_soil_emissions()

        self.emissions_total_yearly = [i + j + k for i, j, k in zip(self.ch4_emitted_yearly, self.straw_burning_yearly, self.soil_emissions_yearly)]
        self.total_emissions = self.ch4_emitted_total + self.straw_burning_total + self.soil_emissions_total



    def evaluate_tier_2_defaults():
        pass
