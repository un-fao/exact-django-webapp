import traceback
from .general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions

class ForestManagement:

    def __init__(self, area_start, area_end, time_impl, time_cap, rate_type, rate_coefficient_end, 
                    nitrous_constant, methane_constant, degradation_level_end_ref, degradation_level_end_tier_2, 
                    degradation_level_start_ref, degradation_level_start_tier_2,
                    agb_ref, agb_tier_2, bgb_ref, bgb_tier_2, litter_ref, litter_tier_2, deadwood_ref, deadwood_tier_2, 
                    socref, soc_tier_2, luf_default, luf_start_tier_2, luf_end_tier_2, fire_periodicity_end,
                    fire_used_end, percentage_biomass_burnt_end, cf, ef_methane, ef_nitrous ):
        # ----- GENERAL PARAMETERS FRONT END INPUTS, FROM MODULE OR GENERAL DESCRIPTION -----
        self.area_start = area_start
        self.area_end = area_end
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate_type = rate_type
        self.rate = rate_coefficient_end
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        # ----- BIOMASS EMISSIONS -----
        self.degradation_level_end_ref = degradation_level_end_ref
        self.degradation_level_end_tier_2 = degradation_level_end_tier_2
        self.degradation_level_start_ref = degradation_level_start_ref
        self.degradation_level_start_tier_2 = degradation_level_start_tier_2
        self.agb_ref = agb_ref
        self.agb_tier_2 = agb_tier_2
        self.bgb_ref = bgb_ref
        self.bgb_tier_2 = bgb_tier_2
        #    ----- DOM EMISSIONS -----
        self.litter_ref = litter_ref
        self.litter_tier_2 = litter_tier_2
        self.deadwood_ref = deadwood_ref
        self.deadwood_tier_2 = deadwood_tier_2
        self.socref = socref
        self.soc_tier_2 = soc_tier_2
        self.luf_default = luf_default
        self.luf_start_tier_2 = luf_start_tier_2
        self.luf_end_tier_2 = luf_end_tier_2
        #     ----- FIRE EMISSIONS -----
        self.fire_periodicity_end = fire_periodicity_end
        self.fire_used_end = fire_used_end
        self.percentage_biomass_burnt_end = percentage_biomass_burnt_end
        self.cf = cf
        self.ef_methane = ef_methane
        self.ef_nitrous = ef_nitrous

        # AUXILIARY VARIABLES FOR SOIL CALCULATION
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(min(area_start, area_end),max(area_start, area_end),self.time_impl, self.time_cap, self.rate)

        # RESULTS
        self.yearly_biomass_emissions = []
        self.total_biomass_emissions = 0

        self.yearly_dom_emissions = []
        self.total_dom_emissions = 0

        self.yearly_fire_emissions = []
        self.total_fire_emissions = 0

        self.yearly_soc_emissions = []
        self.total_soc_emissions = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0


    def calculate_emissions(self, ):

        def calculate_biomass_emissions():
            try:
                degradation_level_start = self.degradation_level_start_ref if not self.degradation_level_start_tier_2 else self.degradation_level_start_tier_2
                degradation_level_end = self.degradation_level_end_ref if not self.degradation_level_end_tier_2 else self.degradation_level_end_tier_2
                agb = self.agb_ref if not self.agb_tier_2 else self.agb_tier_2
                bgb = self.bgb_ref if not self.bgb_tier_2 else self.bgb_tier_2


                tot_biomass = agb + bgb

                biomass_start = tot_biomass * (1 - degradation_level_start)
                biomass_end = tot_biomass * (1 - degradation_level_end)

                total = (biomass_end - biomass_start) * (-44/12) * self.area_end

                self.total_biomass_emissions = total
                self.yearly_biomass_emissions = yearly_constant_emissions_breakdown(total, self.time_impl, self.time_cap)

            except Exception as e:
                traceback.print_exc()
                
        def calculate_dom_emissions():
            try:
                degradation_level_start = self.degradation_level_start_ref if not self.degradation_level_start_tier_2 else self.degradation_level_start_tier_2
                degradation_level_end = self.degradation_level_end_ref if not self.degradation_level_end_tier_2 else self.degradation_level_end_tier_2 
                litter = self.litter_ref if not self.litter_tier_2 else self.litter_tier_2
                deadwood = self.deadwood_ref if not self.deadwood_tier_2 else self.deadwood_tier_2

                tot_dom = litter + deadwood

                dom_start = tot_dom * (1 - degradation_level_start)
                dom_end = tot_dom * (1 - degradation_level_end)

                total = (dom_end - dom_start) * (-44/12) * self.area_end
                self.total_biomass_emissions = total
                self.yearly_biomass_emissions = yearly_constant_emissions_breakdown(total, self.time_impl, self.time_cap)
                
            except Exception as e:
                traceback.print_exc()
                pass

        def calculate_fire_emissions():
            try:
                if self.fire_periodicity_end > (self.time_impl + self.time_cap) or not self.fire_used_end:  
                    return 0
                else:
                    degradation_level_start = self.degradation_level_start_ref if not self.degradation_level_start_tier_2 else self.degradation_level_start_tier_2
                    degradation_level_end = self.degradation_level_end_ref if not self.degradation_level_end_tier_2 else self.degradation_level_end_tier_2
                    agb = self.agb_ref if not self.agb_tier_2 else self.agb_tier_2
                    bgb = self.bgb_ref if not self.bgb_tier_2 else self.bgb_tier_2

                    tot_biomass = agb + bgb

                    biomass_start = tot_biomass * (1 - degradation_level_start)
                    biomass_end = tot_biomass * (1 - degradation_level_end)

                    biomass_breakdown = yearly_time_dependent_parameter_breakdown(biomass_start, biomass_end, self.time_impl, self.time_cap, self.rate)
                    total_biomass_over_time = sum(biomass_breakdown)
                    
                    kg_methane = 2 * total_biomass_over_time * self.cf * self.ef_methane * self.percentage_biomass_burnt_end / self.fire_periodicity_end
                    kg_nitrous = 2 * total_biomass_over_time * self.cf * self.ef_nitrous * self.percentage_biomass_burnt_end / self.fire_periodicity_end

                    tonnes_co2 = (kg_nitrous * self.nitrous_constant + kg_methane * self.methane_constant)/1000

                    # TODO: check if this can be done by changing the part above and simply using area end broken over time (even though I doubt it)
                    return tonnes_co2 * self.area_end
                
            except Exception as e:
                traceback.print_exc()
                pass

        def calculate_soc_emissions():
            try:
                soc = self.soc_ref if not self.soc_tier_2 else self.soc_tier_2
                luf_start = self.luf_default if not self.luf_start_tier_2 else self.luf_start_tier_2
                luf_end = self.luf_default if not self.luf_end_tier_2 else self.luf_end_tier_2

                soc_start = soc * luf_start
                soc_end = soc * luf_end
                delta_co2_mineral_per_ha_per_yr = (soc_end - soc_start)/20 * (-44/12)

                total = delta_co2_mineral_per_ha_per_yr * sum(self.hectars_before_20)
                self.total_soc_emissions = total
                self.yearly_soc_emissions = breakdown_according_to_values(total, self.hectars_before_20)             
    
                pass
            except Exception as e:
                traceback.print_exc()
                pass

        try:
            calculate_biomass_emissions()
            calculate_dom_emissions()
            calculate_fire_emissions()
            calculate_soc_emissions()

            self.total_emissions = sum(self.yearly_biomass_emissions) + sum(self.yearly_dom_emissions) + sum(self.yearly_fire_emissions) + sum(self.yearly_soc_emissions)
            self.emissions_total_yearly = [i+j+k+l for i,j,k,l in zip(self.yearly_biomass_emissions, self.yearly_dom_emissions, self.yearly_fire_emissions, self.yearly_soc_emissions)]

            return self.total_emissions
        except Exception as e:
            traceback.print_exc()
            return None
            

    def evaluate_tier_2_defaults(self, ):
        pass

