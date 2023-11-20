from .general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions
import traceback, re
from .ghg_emissions_classes import GasTypes, ActivityTypes, Emission, YearlyActivityEmissionSet, Result

class Deforestation():

    def __init__(self, ha_start, ha_end,time_impl,time_cap,rate_type_soil,biomass_final_1_year_t_per_ha,biomass_final_1_year_t_per_ha_tier_2,
        nitrous_constant, methane_constant,fire_bool,n2o_vegetation,ch4_vegetation,cf_vegetation,moisture_emission_factor,
        litter,litter_tier_2,dw,dw_tier_2,hwp_before_t_dm_per_ha,mangrove_factor,bgb_t_c_per_ha_tier_2,
        agb_t_c_per_ha_tier_2,flu,agb_t_dm_per_ha_default,bgb_t_dm_per_ha_default_input_parameter,c_n_ratio,
        soc_after_defo_tier_2,soc_reference_default,soc_reference_tier_2):

        self.ha_start = ha_start
        self.ha_end = ha_end
        self.area_deforested = abs(ha_end - ha_start)
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate_type_soil = rate_type_soil
        self.biomass_final_1_year_t_per_ha_default = biomass_final_1_year_t_per_ha
        self.biomass_final_1_year_t_per_ha_tier_2 = biomass_final_1_year_t_per_ha_tier_2
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.fire_bool = fire_bool
        self.n2o_vegetation = n2o_vegetation
        self.ch4_vegetation = ch4_vegetation
        self.cf_vegetation = cf_vegetation
        self.moisture_emission_factor = moisture_emission_factor
        self.litter = litter
        self.litter_tier_2 = litter_tier_2
        self.dw = dw
        self.dw_tier_2 = dw_tier_2
        self.hwp_before_t_dm_per_ha = hwp_before_t_dm_per_ha
        self.mangrove_factor = mangrove_factor
        self.bgb_t_c_per_ha_tier_2 = bgb_t_c_per_ha_tier_2
        self.agb_t_c_per_ha_tier_2 = agb_t_c_per_ha_tier_2
        self.flu = flu
        self.agb_t_dm_per_ha_default = agb_t_dm_per_ha_default
        self.bgb_t_dm_per_ha_default_input_parameter = bgb_t_dm_per_ha_default_input_parameter
        self.c_n_ratio = c_n_ratio
        self.soc_after_defo_tier_2 = soc_after_defo_tier_2
        self.soc_reference_default = soc_reference_default
        self.soc_reference_tier_2 = soc_reference_tier_2

        # TIER 2 DEFAULT VALUES
        self.agb_tier_2_default = None
        self.bgb_tier_2_default = None
        self.litter_tier_2_default = None
        self.dw_tier_2_default = None
        self.soc_start_tier_2_default = None
        self.soc_final_tier_2_default = None
        self.flu_start_tier_2_default = None
        self.flu_final_tier_2_default = None
        self.biomass_final_tier_2_default = None

        # AUXILIARY VARIABLES FOR SOIL CALCULATION
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(0, self.area_deforested, self.time_impl, self.time_cap, self.rate_type_soil)
        #self.hectars_before_20 = yearly_time_dependent_20_year_breakdown(0, self.area_deforested, self.time_impl, self.time_cap, self.rate_type_soil)

        # RESULTS
        self.emissions_biomass_gain_yearly = []
        self.emissions_biomass_gain_total = 0

        self.emissions_biomass_loss_yearly = []
        self.emissions_biomass_loss_total = 0

        self.emissions_dom_yearly = []
        self.emissions_dom_total = 0

        self.emissions_soil_yearly = []
        self.emissions_soil_total = 0

        self.emissions_fire_fsom_yearly = []
        self.emissions_fire_fsom_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)

    def calculate_emissions(self):

        def calculate_biomass_loss_emissions():

            try:
                bgb_t_dm_per_ha_default = (
                    self.bgb_t_dm_per_ha_default_input_parameter * self.agb_t_dm_per_ha_default
                )
                
                agb_t_c = (
                    self.agb_t_dm_per_ha_default * self.mangrove_factor
                    if not self.agb_t_c_per_ha_tier_2
                    else self.agb_t_c_per_ha_tier_2
                )
                bgb_t_c = (
                    bgb_t_dm_per_ha_default * self.mangrove_factor
                    if not self.bgb_t_c_per_ha_tier_2
                    else self.bgb_t_c_per_ha_tier_2
                )

                hwp_before_t_c = (
                    self.agb_t_dm_per_ha_default * self.mangrove_factor
                    if self.hwp_before_t_dm_per_ha > self.agb_t_dm_per_ha_default
                    else self.hwp_before_t_dm_per_ha * self.mangrove_factor
                )

                biomass_forest_agb_bgb_t_c = agb_t_c + bgb_t_c - hwp_before_t_c
                
                biomass_forest_agb_bgb_t_co2 = biomass_forest_agb_bgb_t_c * (44 / 12)

                biomass_loss = biomass_forest_agb_bgb_t_co2 * self.area_deforested

                self.emissions_biomass_loss_yearly = yearly_constant_emissions_breakdown(biomass_loss, self.time_impl, self.time_cap)
                self.emissions_biomass_loss_total = biomass_loss
            except Exception as e:
                traceback.print_exc()
                
        def calculate_biomass_gain_emissions():

            try:
                if self.biomass_final_1_year_t_per_ha_tier_2:
                    biomass_final_1_year_t_per_ha = self.biomass_final_1_year_t_per_ha_tier_2
                else:
                    biomass_final_1_year_t_per_ha = self.biomass_final_1_year_t_per_ha_default

                self.emissions_biomass_gain_total = 0 if self.emissions_biomass_loss_total == 0 else -(biomass_final_1_year_t_per_ha * self.area_deforested * (44 / 12))
                self.emissions_biomass_gain_yearly = yearly_constant_emissions_breakdown(self.emissions_biomass_gain_total, self.time_impl, self.time_cap)
            
            except Exception as e:
                traceback.print_exc()

        def calculate_dom_emissions():
            try:
                litter = self.litter if not self.litter_tier_2 else self.litter_tier_2
                dw = self.dw if not self.dw_tier_2 else self.dw_tier_2

                biomass_forest_dom_t_c_per_ha = litter + dw
                biomass_forest_dom_t_co2_per_ha = biomass_forest_dom_t_c_per_ha * (44 / 12)

                dom_loss = biomass_forest_dom_t_co2_per_ha * self.area_deforested
                self.emissions_dom_yearly = yearly_constant_emissions_breakdown(dom_loss, self.time_impl, self.time_cap)
                self.emissions_dom_total = dom_loss

            except Exception as e:
                traceback.print_exc()

        def calculate_soil_emissions():
            try:
                self.emissions_soil_yearly, self.emissions_soil_total = soil_emissions(self.hectars_before_20, 0, self.area_deforested, self.soc_reference_default, self.soc_reference_tier_2, None, None, None, self.flu)

            except Exception as e:
                traceback.print_exc()

        def calculate_fire_fsom_emissions():
            try: 
                fire_t_dm_per_ha = (
                    self.agb_t_dm_per_ha_default - self.hwp_before_t_dm_per_ha if self.fire_bool else 0
                )

                soc_reference = self.soc_reference_tier_2 if self.soc_reference_tier_2 else self.soc_reference_default
                delta_c_mineral_per_ha = (
                    soc_reference * self.flu - soc_reference
                    if not self.soc_after_defo_tier_2
                    else self.soc_after_defo_tier_2 - soc_reference
                )

                som_luc_kg_n_per_year = (
                    0
                    if delta_c_mineral_per_ha >= 0
                    else -(delta_c_mineral_per_ha / (20 * self.c_n_ratio)) * 1000
                )
                
                soil_kg_n2o = (
                    self.moisture_emission_factor * 44/28 * som_luc_kg_n_per_year
                )
                
                fire_kg_n2o = fire_t_dm_per_ha * self.n2o_vegetation * self.cf_vegetation if self.fire_bool else 0
                fire_kg_ch4 = fire_t_dm_per_ha * self.ch4_vegetation * self.cf_vegetation if self.fire_bool else 0

                total_ch4_n2o_per_ha = (
                    fire_kg_ch4 * self.methane_constant + (fire_kg_n2o + soil_kg_n2o) * self.nitrous_constant
                ) / 1000
                
                fire_fsom_N_w = total_ch4_n2o_per_ha * self.area_deforested

                self.emissions_fire_fsom_yearly = yearly_constant_emissions_breakdown(fire_fsom_N_w, self.time_impl, self.time_cap)
                self.emissions_fire_fsom_total = fire_fsom_N_w
            
            except Exception as e:
                traceback.print_exc()

        
        calculate_biomass_loss_emissions()
        calculate_biomass_gain_emissions()
        calculate_dom_emissions()
        calculate_soil_emissions()
        calculate_fire_fsom_emissions()

        try:
            self.emissions_total_yearly = [sum(x) for x in zip(self.emissions_biomass_gain_yearly, self.emissions_biomass_loss_yearly, self.emissions_dom_yearly, self.emissions_soil_yearly, self.emissions_fire_fsom_yearly)]
            self.total_emissions = sum(self.emissions_total_yearly)
            return self.total_emissions
        
        except Exception as e:
            traceback.print_exc()
            return None

    def evaluate_tier_2_defaults(self):

        try: 
            # TODO: evaluate tier 2 defaults based on the front-end necessities

            return {re.sub('_tier_2_default', '', k): v for k, v in self.__dict__.items() if '_tier_2_default' in k}

        except Exception as e:
            traceback.print_exc()
            return {}
        
        
