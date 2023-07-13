from general_functions import yearly_parameter_breakdown, plot_yearly_breakdown, plot_all_functions
import traceback
import re

class Fishery:

    def __init__(self, time_impl, time_cap, rate_type, catch_start, catch_end, ef_diesel_default, ef_diesel_start_tier_2, ef_diesel_tier_2_end, fui_default_start, fui_default_end, fui_start_tier_2, fui_end_tier_2, gwp_refrigerant_default, gwp_refrigerant_start_tier_2,
                 gwp_refrigerant_end_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_start_tier_2, quantity_lost_refrigerant_end_tier_2, percentage_refrigerant_start, percentage_refrigerant_end, tonnes_ice_default, tonnes_ice_start_tier_2, tonnes_ice_end_tier_2, 
                 kwh_ice_per_tonne_default, kwh_ice_per_tonne_start_tier_2, kwh_ice_per_tonne_end_tier_2, operating_margin, percentage_ice_start, percentage_ice_end) -> None:
        
        # DEFINITIONS OF PARAMETERS
        self.implementation_time = time_impl
        self.capitalization_time = time_cap
        self.rate_type = rate_type
        self.catch_start = catch_start
        self.catch_end = catch_end
        self.ef_diesel_default = ef_diesel_default
        self.ef_diesel_start_tier_2 = ef_diesel_start_tier_2
        self.ef_diesel_tier_2_end = ef_diesel_tier_2_end
        self.fui_default_start = fui_default_start
        self.fui_default_end = fui_default_end
        self.fui_start_tier_2 = fui_start_tier_2
        self.fui_end_tier_2 = fui_end_tier_2
        self.gwp_refrigerant_default = gwp_refrigerant_default
        self.gwp_refrigerant_start_tier_2 = gwp_refrigerant_start_tier_2
        self.gwp_refrigerant_end_tier_2 = gwp_refrigerant_end_tier_2
        self.quantity_lost_refrigerant_default = quantity_lost_refrigerant_default
        self.quantity_lost_refrigerant_start_tier_2 = quantity_lost_refrigerant_start_tier_2
        self.quantity_lost_refrigerant_end_tier_2 = quantity_lost_refrigerant_end_tier_2
        self.percentage_refrigerant_start = percentage_refrigerant_start
        self.percentage_refrigerant_end = percentage_refrigerant_end
        self.tonnes_ice_default = tonnes_ice_default
        self.tonnes_ice_start_tier_2 = tonnes_ice_start_tier_2
        self.tonnes_ice_end_tier_2 = tonnes_ice_end_tier_2
        self.kwh_ice_per_tonne_default = kwh_ice_per_tonne_default
        self.kwh_ice_per_tonne_start_tier_2 = kwh_ice_per_tonne_start_tier_2
        self.kwh_ice_per_tonne_end_tier_2 = kwh_ice_per_tonne_end_tier_2
        self.operating_margin = operating_margin
        self.percentage_ice_start = percentage_ice_start
        self.percentage_ice_end = percentage_ice_end
        
        # DEFINITION OF THE TIER 2 DEFAULTS
        self.ef_diesel_tier_2_default = None 
        self.fui_start_tier_2_default = None
        self.fui_end_tier_2_default = None
       
        self.gwp_refrigerant_tier_2_default = None
        self.quantity_lost_refrigerant_tier_2_default = None

        self.tonnes_ice_tier_2_default = None 
        self.kwh_ice_per_tonne_tier_2_default = None 

        # RESULTS
        self.emissions_catch_yearly = []
        self.emissions_refrigerant_yearly = []
        self.emissions_ice_yearly = []

        self.emissions_catch_total = 0
        self.emissions_refrigerant_total = 0
        self.emissions_ice_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

    def calculate_emissions(self):
        
        def calculate_catch_emissions():
            
            try:
                ef_diesel_start = self.ef_diesel_default if not self.ef_diesel_start_tier_2 else self.ef_diesel_start_tier_2
                ef_diesel_end = self.ef_diesel_default if not self.ef_diesel_tier_2_end else self.ef_diesel_tier_2_end

                fui_start = self.fui_default_start if not self.fui_start_tier_2 else self.fui_start_tier_2
                fui_end = self.fui_default_end if not self.fui_end_tier_2 else self.fui_end_tier_2

                ef_start = fui_start * ef_diesel_start / 1000
                ef_end = fui_end * ef_diesel_end / 1000

                annual_start = self.catch_start * ef_start
                annual_end = self.catch_end * ef_end

                self.emissions_catch_yearly = yearly_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)
                self.emissions_catch_total = sum(self.emissions_catch_yearly)
            except Exception as e:
                traceback.print_exc()

        def calculate_refrigerant_emissions():
            
            try:
                gwp_refrigerant_start = self.gwp_refrigerant_default if not self.gwp_refrigerant_start_tier_2 else self.gwp_refrigerant_start_tier_2
                gwp_refrigerant_end = self.gwp_refrigerant_default if not self.gwp_refrigerant_end_tier_2 else self.gwp_refrigerant_end_tier_2

                quantity_lost_refrigerant_start = self.quantity_lost_refrigerant_default if not self.quantity_lost_refrigerant_start_tier_2 else self.quantity_lost_refrigerant_start_tier_2
                quantity_lost_refrigerant_end = self.quantity_lost_refrigerant_default if not self.quantity_lost_refrigerant_end_tier_2 else self.quantity_lost_refrigerant_end_tier_2

                catch_with_refrigerant_start = self.catch_start * self.percentage_refrigerant_start
                catch_with_refrigerant_end = self.catch_end * self.percentage_refrigerant_end

                annual_start = gwp_refrigerant_start * quantity_lost_refrigerant_start * catch_with_refrigerant_start / 1000
                annual_end = gwp_refrigerant_end * quantity_lost_refrigerant_end * catch_with_refrigerant_end / 1000

                
                self.emissions_refrigerant_yearly = yearly_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)
                self.emissions_refrigerant_total = sum(self.emissions_refrigerant_yearly)
            except Exception as e:
                traceback.print_exc()

        def calculate_ice_emissions():
            
            try:
                tonnes_ice_start = self.tonnes_ice_default if not self.tonnes_ice_start_tier_2 else self.tonnes_ice_start_tier_2
                tonnes_ice_end = self.tonnes_ice_default if not self.tonnes_ice_end_tier_2 else self.tonnes_ice_end_tier_2

                kwh_ice_per_tonne_start = self.kwh_ice_per_tonne_default if not self.kwh_ice_per_tonne_start_tier_2 else self.kwh_ice_per_tonne_start_tier_2
                kwh_ice_per_tonne_end = self.kwh_ice_per_tonne_default if not self.kwh_ice_per_tonne_end_tier_2 else self.kwh_ice_per_tonne_end_tier_2

                ice_ef_start = tonnes_ice_start * kwh_ice_per_tonne_start * self.operating_margin / 1000
                ice_ef_end = tonnes_ice_end * kwh_ice_per_tonne_end * self.operating_margin / 1000

                catch_with_refrigerant_start = self.catch_start * self.percentage_ice_start
                catch_with_refrigerant_end = self.catch_end * self.percentage_ice_end

                annual_start = ice_ef_start * catch_with_refrigerant_start 
                annual_end = ice_ef_end * catch_with_refrigerant_end

                self.emissions_ice_yearly = yearly_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)
                self.emissions_ice_total = sum(self.emissions_ice_yearly)
            except Exception as e:
                traceback.print_exc()

        
        calculate_catch_emissions()
        calculate_refrigerant_emissions()
        calculate_ice_emissions()

        try:
            self.emissions_total_yearly = [sum(x) for x in zip(self.emissions_catch_yearly, self.emissions_refrigerant_yearly, self.emissions_ice_yearly)]
            self.total_emissions = sum(self.emissions_total_yearly)
        except Exception as e:
            traceback.print_exc()

    def evaluate_tier_2_defaults(self):

        try:
            self.ef_diesel_tier_2_default = self.ef_diesel_default
            self.fui_start_tier_2_default = self.fui_default_start
            self.fui_end_tier_2_default = self.fui_default_end
        
            self.gwp_refrigerant_tier_2_default = self.gwp_refrigerant_default
            self.quantity_lost_refrigerant_tier_2_default = self.quantity_lost_refrigerant_default

            self.tonnes_ice_tier_2_default = self.tonnes_ice_default 
            self.kwh_ice_per_tonne_tier_2_default = self.kwh_ice_per_tonne_default 

            # create a dictionary with the name of the variable (removing tier 2 default and capitalizing the first letter) and the value of the variable
            return {re.sub('_tier_2_default', '', k): v for k, v in self.__dict__.items() if '_tier_2_default' in k}

        except Exception as e:
            traceback.print_exc()
            return {}

class CoastalAquaculture():

    def __init__(self, production_start, production_w, nitrous_ef_default, nitrous_ef_tier_2, nitrous_constant, time_impl, time_cap, rate_type, feed_start, feed_w, ef_feed_default, ef_feed_tier_2):

        self.time_impl = time_impl
        self.time_cap = time_cap
        self.production_start = production_start
        self.production_end = production_w
        self.nitrous_ef_default = nitrous_ef_default
        self.nitrous_ef_tier_2 = nitrous_ef_tier_2
        self.nitrous_constant = nitrous_constant
        self.rate_type = rate_type
        self.feed_start = feed_start
        self.feed_end = feed_w
        self.ef_feed_default = ef_feed_default
        self.ef_feed_tier_2 = ef_feed_tier_2

        # DEFINITION OF TIER 2 DEFAULTS
        self.nitrous_ef_tier_2_default = None
        self.ef_feed_tier_2_default = None 

        self.emissions_nitrous_yearly = []
        self.emissions_feed_yearly = []
        self.emissions_total_yearly = []

        self.emissions_nitrous_total = 0
        self.emissions_feed_total = 0
        self.total_emissions = 0

    def calculate_emissions(self):
            
        def calculate_nitrous_emissions():
            try:
                nitrous_ef_start = self.nitrous_ef_default
                nitrous_ef_end = self.nitrous_ef_tier_2

                annual_start = nitrous_ef_start * self.production_start * self.nitrous_constant
                annual_end = nitrous_ef_end * self.production_end * self.nitrous_constant

                self.emissions_nitrous_yearly = yearly_parameter_breakdown(annual_start, annual_end, self.time_impl, self.time_cap, self.rate_type)
                self.emissions_nitrous_total = sum(self.emissions_nitrous_yearly)
            except Exception as e:
                traceback.print_exc()

        def calculate_feed_emissions():
            try:
                ef_feed_start = self.ef_feed_default
                ef_feed_end = self.ef_feed_tier_2

                annual_start = ef_feed_start * self.feed_start
                annual_end = ef_feed_end * self.feed_end

                self.emissions_feed_yearly = yearly_parameter_breakdown(annual_start, annual_end, self.time_impl, self.time_cap, self.rate_type)
                self.emissions_feed_total = sum(self.emissions_feed_yearly)
            except Exception as e:
                traceback.print_exc()

        calculate_nitrous_emissions()
        calculate_feed_emissions()

        try:
            self.emissions_total_yearly = [sum(x) for x in zip(self.emissions_nitrous_yearly, self.emissions_feed_yearly)]
            self.total_emissions = sum(self.emissions_total_yearly)
        except Exception as e:
            traceback.print_exc()

    def evaluate_tier_2_defaults(self):

        try:
            self.nitrous_ef_tier_2_default = self.nitrous_ef_default
            self.ef_feed_tier_2_default = self.ef_feed_default
            
            return {re.sub('_tier_2_default', '', k): v for k, v in self.__dict__.items() if '_tier_2_default' in k}

        except Exception as e:
            traceback.print_exc()
            return {}

        
# inputs_class = [10, 11, 'D', 5.23659035050339, 71.3662756029244, 2.572333333333333, None, None, 697.0, 697.0, 19.8011614615062, 31.2816563027116, 1810, None, None, None, None, None, 0.388905643541494, 0.0490041343890272, 2.8, None, None, 60, None, None,  0.296, 0.169438233537953, 0.180905927941485]
# inputs_class = [10, 11, 'D', 5.23659035050339, 71.3662756029244, 2.572333333333333, None, None, 697.0, 697.0, 19.8011614615062, 31.2816563027116, 1810, None, None, 0.48734, None, None, 0.388905643541494, 0.0490041343890272, 2.8, None, None, 60, None, None,  0.296, 0.169438233537953, 0.180905927941485]
# inputs = [10, 11, 'D', 'D', 5.23659035050339, 71.3662756029244, 44.0123155054382, 2.572333333333333, None, None, None, 697.0, 697.0, 697.0, 19.8011614615062, 31.2816563027116, 43.4530778935223, 1810, None, None, None, 0.48734, None, None, None, 0.388905643541494, 0.0490041343890272, 0.152197266950354, 2.8, None, None, None, 60, None, None, None, 0.296, 0.169438233537953, 0.180905927941485, 0.967017664672948]

# ao = total_emissions_small_or_large_fisheries(*inputs)
# print('No time dependency')
# print(ao)

# fishery_w = Fishery(*inputs_class)
# fishery_w.calculate_emissions()
# print(fishery_w.evaluate_tier_2_defaults())
# print(fishery_w.total_emissions)


