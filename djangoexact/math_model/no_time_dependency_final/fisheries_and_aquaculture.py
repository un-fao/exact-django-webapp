from general_functions import yearly_parameter_breakdown, plot_yearly_breakdown, plot_all_functions

def total_emissions_small_or_large_fisheries(time_impl, time_cap, rate_coefficient_w, rate_coefficient_wo, catch_start, catch_w, catch_wo, 
                    ef_diesel_default, ef_diesel_start_tier_2, ef_diesel_w_tier_2, ef_diesel_wo_tier_2,
                    fui_default_start, fui_default_w, fui_default_wo, fui_start_tier_2, fui_w_tier_2, fui_wo_tier_2,  
                    gwp_refrigerant_default, gwp_refrigerant_start_tier_2, gwp_refrigerant_w_tier_2, gwp_refrigerant_wo_tier_2,
                    quantity_lost_refrigerant_default, quantity_lost_refrigerant_start_tier_2, quantity_lost_refrigerant_w_tier_2, quantity_lost_refrigerant_wo_tier_2,
                    percentage_refrigerant_start, percentage_refrigerant_w, percentage_refrigerant_wo, 
                    tonnes_ice_default, tonnes_ice_start_tier_2, tonnes_ice_w_tier_2, tonnes_ice_wo_tier_2,
                    kwh_ice_per_tonne_default, kwh_ice_per_tonne_start_tier_2, kwh_ice_per_tonne_w_tier_2, kwh_ice_per_tonne_wo_tier_2, 
                    operating_margin,
                    percentage_ice_start, percentage_ice_w, percentage_ice_wo):
    
    # SINGLE EMISSION CALCULATION FUNCTIONS AND SUPPORT FUNCTIONS
    
    def emissions_catch(time_impl, time_cap, rate_coefficient, catch_start, catch_end, ef_diesel_default, ef_diesel_start_tier_2, ef_diesel_end_tier_2, fui_default_start, fui_default_end, fui_start_tier_2, fui_end_tier_2):

        ef_diesel_start = ef_diesel_default if not ef_diesel_start_tier_2 else ef_diesel_start_tier_2
        ef_diesel_end = ef_diesel_default if not ef_diesel_end_tier_2 else ef_diesel_end_tier_2

        fui_start = fui_default_start if not fui_start_tier_2 else fui_start_tier_2
        fui_end = fui_default_end if not fui_end_tier_2 else fui_end_tier_2

        ef_start = fui_start * ef_diesel_start / 1000
        ef_end = fui_end * ef_diesel_end / 1000

        annual_start = catch_start * ef_start
        annual_end = catch_end * ef_end

        return yearly_parameter_breakdown(annual_start, annual_end, time_impl, time_cap, rate_coefficient)
    
    def emissions_refrigerant(time_impl, time_cap, rate_coefficient, gwp_refrigerant_default, gwp_refrigerant_start_tier_2, gwp_refrigerant_end_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_start_tier_2, quantity_lost_refrigerant_end_tier_2, catch_start, catch_end, percentage_refrigerant_start, percentage_refrigerant_end):

        gwp_refrigerant_start = gwp_refrigerant_default if not gwp_refrigerant_start_tier_2 else gwp_refrigerant_start_tier_2
        gwp_refrigerant_end = gwp_refrigerant_default if not gwp_refrigerant_end_tier_2 else gwp_refrigerant_end_tier_2

        quantity_lost_refrigerant_start = quantity_lost_refrigerant_default if not quantity_lost_refrigerant_start_tier_2 else quantity_lost_refrigerant_start_tier_2
        quantity_lost_refrigerant_end = quantity_lost_refrigerant_default if not quantity_lost_refrigerant_end_tier_2 else quantity_lost_refrigerant_end_tier_2

        catch_with_refrigerant_start = catch_start * percentage_refrigerant_start
        catch_with_refrigerant_end = catch_end * percentage_refrigerant_end

        annual_start = gwp_refrigerant_start * quantity_lost_refrigerant_start * catch_with_refrigerant_start / 1000
        annual_end = gwp_refrigerant_end * quantity_lost_refrigerant_end * catch_with_refrigerant_end / 1000

        return yearly_parameter_breakdown(annual_start, annual_end, time_impl, time_cap, rate_coefficient)

    def emissions_ice(time_impl, time_cap, rate_coefficient, tonnes_ice_default, kwh_ice_per_tonne_default, operating_margin, kwh_ice_per_tonne_start_tier_2, kwh_ice_per_tonne_end_tier_2, tonnes_ice_start_tier_2, tonnes_ice_end_tier_2, catch_start, catch_end, percentage_ice_start, percentage_ice_end):

        tonnes_ice_start = tonnes_ice_default if not tonnes_ice_start_tier_2 else tonnes_ice_start_tier_2
        tonnes_ice_end = tonnes_ice_default if not tonnes_ice_end_tier_2 else tonnes_ice_end_tier_2

        kwh_ice_per_tonne_start = kwh_ice_per_tonne_default if not kwh_ice_per_tonne_start_tier_2 else kwh_ice_per_tonne_start_tier_2
        kwh_ice_per_tonne_end = kwh_ice_per_tonne_default if not kwh_ice_per_tonne_end_tier_2 else kwh_ice_per_tonne_end_tier_2

        ice_ef_start = tonnes_ice_start * kwh_ice_per_tonne_start * operating_margin / 1000
        ice_ef_end = tonnes_ice_end * kwh_ice_per_tonne_end * operating_margin / 1000

        catch_with_refrigerant_start = catch_start * percentage_ice_start
        catch_with_refrigerant_end = catch_end * percentage_ice_end

        annual_start = ice_ef_start * catch_with_refrigerant_start 
        annual_end = ice_ef_end * catch_with_refrigerant_end

        return yearly_parameter_breakdown(annual_start, annual_end, time_impl, time_cap, rate_coefficient)

    """
    time_impl: project implementation time in years
    time_cap: project capitalization time in years
    rate_coefficient_w: obtained matching rate_type to reference table
    rate_coefficient_wo: obtained matching rate_type to reference table #### MISSING IN EXCEL
    catch_start: catch in tonnes at project start
    catch_w: catch in tonnes with project
    catch_wo: catch in tonnes without project
    ef_diesel_default: default diesel emission factor in tonnes CO2e per square metre. Obtained as average of value in IPCC B1739:B1741
    ef_diesel_tier_2: tier 2 value, expects None or Float
    fui_default_start: in DATABASE_FISH tab A6-K30 match fish category and gear category. If no exact match, match fish category and take column 'Not specified'
    fui_default_w: in DATABASE_FISH tab A6-K30 match fish category and gear category. If no exact match, match fish category and take column 'Not specified'
    fui_default_wo: in DATABASE_FISH tab A6-K30 match fish category and gear category. If no exact match, match fish category and take column 'Not specified'
    fui_start_tier_2: tier 2 value, expects None or Float
    fui_w_tier_2: tier 2 value, expects None or Float
    fui_wo_tier_2: tier 2 value, expects None or Float
    gwp_refrigerant_default: default global warming potential of refrigerant, value is 1810 for both Small and Large Scale Fisheries
    gwp_refrigerant_start_tier_2: tier 2 value, expects None or Float
    gwp_refrigerant_w_tier_2: tier 2 value, expects None or Float
    gwp_refrigerant_wo_tier_2: tier 2 value, expects None or Float
    quantity_lost_refrigerant_default: default quantity of refrigerant lost, value is 0.48734 for Large Scale Fisheries and 0.083 for Small Scale Fisheries
    quantity_lost_refrigerant_tier_2: tier 2 value, expects None or Float
    percentage_refrigerant_start: percentage of catch with refrigerant at start
    percentage_refrigerant_w: percentage of catch with refrigerant with project
    percentage_refrigerant_wo: percentage of catch with refrigerant without project
    tonnes_ice_default: tonne of ice per tonne of catch, 2.8 for Small Scale Fisheries and for Large Scale Fisheries
    tonnes_ice_tier_2: tier 2 value, expects None or Float
    kwh_ice_per_tonne_default: kWh of electricity per tonne of ice, 60 for Small Scale Fisheries for Large Scale Fisheries
    kwh_ice_per_tonne_tier_2: tier 2 value, expects None or Float
    operating_margin: obtained from table in Elec! A2-F252. Match is to be done on tier 2 value COUNTRY OF ORIGIN (front end input in module) if present, if not on Country_selected (global variable in excel for reference) in 1.Description
    percentage_ice_start: percentage of catch preserved with ice at start
    percentage_ice_w: percentage of catch preserved with ice with project
    percentage_ice_wo: percentage of catch preserved with ice without project
    """

    emissions_catch_w = emissions_catch(time_impl, time_cap, rate_coefficient_w, catch_start, catch_w, ef_diesel_default, ef_diesel_start_tier_2, ef_diesel_w_tier_2, fui_default_start, fui_default_w, fui_start_tier_2, fui_w_tier_2) 
    emissions_catch_wo = emissions_catch(time_impl, time_cap, rate_coefficient_wo, catch_start, catch_wo, ef_diesel_default, ef_diesel_start_tier_2, ef_diesel_wo_tier_2, fui_default_start, fui_default_wo, fui_start_tier_2, fui_wo_tier_2)

    emissions_refrigerant_w = emissions_refrigerant(time_impl, time_cap, rate_coefficient_w, gwp_refrigerant_default, gwp_refrigerant_start_tier_2, gwp_refrigerant_w_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_start_tier_2, quantity_lost_refrigerant_w_tier_2, catch_start, catch_w, percentage_refrigerant_start, percentage_refrigerant_w)
    emissions_refrigerant_wo = emissions_refrigerant(time_impl, time_cap, rate_coefficient_wo, gwp_refrigerant_default, gwp_refrigerant_start_tier_2, gwp_refrigerant_wo_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_start_tier_2, quantity_lost_refrigerant_wo_tier_2, catch_start, catch_wo, percentage_refrigerant_start, percentage_refrigerant_wo)

    emissions_ice_w = emissions_ice(time_impl, time_cap, rate_coefficient_w, tonnes_ice_default, kwh_ice_per_tonne_default, operating_margin, kwh_ice_per_tonne_start_tier_2, kwh_ice_per_tonne_w_tier_2, tonnes_ice_start_tier_2, tonnes_ice_w_tier_2, catch_start, catch_w, percentage_ice_start, percentage_ice_w)
    emissions_ice_wo = emissions_ice(time_impl, time_cap, rate_coefficient_wo, tonnes_ice_default, kwh_ice_per_tonne_default, operating_margin, kwh_ice_per_tonne_start_tier_2, kwh_ice_per_tonne_wo_tier_2,tonnes_ice_start_tier_2, tonnes_ice_wo_tier_2, catch_start, catch_wo, percentage_ice_start, percentage_ice_wo)

    total_w = sum(emissions_catch_w) + sum(emissions_refrigerant_w) + sum(emissions_ice_w)
    total_wo = sum(emissions_catch_wo) + sum(emissions_refrigerant_wo) + sum(emissions_ice_wo)
    
    return total_w, total_wo, total_w - total_wo

def total_inland_coastal_aquaculture(production_start, production_w, nitrous_ef_default, nitrous_ef_tier_2, nitrous_constant, time_impl, time_cap, rate_coefficient_w, rate_coefficient_wo, production_wo,feed_start, feed_w, ef_feed_default, ef_feed_tier_2, feed_wo):

    # INTERMEDIATE FUNCTIONS AND SUPPORT FUNCTIONS
    def nitrous_emissions(production_start, production_end, nitrous_ef_default, nitrous_ef_tier_2, nitrous_constant, time_impl, time_cap, rate_coefficient):

        nitrous_ef = nitrous_ef_default if not nitrous_ef_tier_2 else nitrous_ef_tier_2
        nitrous_ef_production = nitrous_ef * 44/28 * nitrous_constant

        nitrous_emissions_end = production_end * nitrous_ef_production
        nitrous_emissions_start = production_start * nitrous_ef_production

        return yearly_parameter_breakdown(nitrous_emissions_start, nitrous_emissions_end, time_impl, time_cap, rate_coefficient)

    def feed_emissions (feed_start, feed_end, ef_feed_default, ef_feed_tier_2, time_impl, time_cap, rate_coefficient):

        # this function is the same as flooded rice ch4 calculation, that's why it says area
        def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):
            if area > area_start:
                return time_cap + time_impl * rate_coefficient
            else:
                return time_impl * (1 - rate_coefficient)

        ef_feed = ef_feed_default if not ef_feed_tier_2 else ef_feed_tier_2

        annual_feed_end = feed_end * ef_feed
        annual_feed_start = feed_start * ef_feed

        return time_dependency(annual_feed_start, annual_feed_end, rate_coefficient, time_impl, time_cap)

    """
    production_start: front end input
    production_w: front end input
    nitrous_ef_default: fixed value 0.00169
    nitrous_ef_tier_2: tier 2 value, expects float or none
    nitrous_constant: input in 1.Description
    time_impl: implementation time
    time_cap: cap time
    rate_coefficient_w: rate coefficient
    rate_coefficient_wo: rate coefficient # MISSING IN EXCEL REFERENCE
    production_wo: front end input
    feed_start: front end input
    feed_w: front end input
    ef_feed_default: fixed value 0
    ef_feed_tier_2: tier 2 value, expects float or none
    feed_wo: front end input
    """

    nitrous_emissions_w = nitrous_emissions(production_start, production_w, nitrous_ef_default, nitrous_ef_tier_2, nitrous_constant, time_impl, time_cap, rate_coefficient_w)
    nitrous_emissions_wo = nitrous_emissions(production_start, production_wo, nitrous_ef_default, nitrous_ef_tier_2, nitrous_constant, time_impl, time_cap, rate_coefficient_wo)

    feed_emissions_w = feed_emissions(feed_start, feed_w, ef_feed_default, ef_feed_tier_2, time_impl, time_cap, rate_coefficient_w)
    feed_emissions_wo = feed_emissions(feed_start, feed_wo, ef_feed_default, ef_feed_tier_2, time_impl, time_cap, rate_coefficient_wo)

    total_w = sum(nitrous_emissions_w) + sum(feed_emissions_w)
    total_wo = sum(nitrous_emissions_wo) + sum(feed_emissions_wo)

    return total_w, total_wo, total_w - total_wo


inputs = [10, 11, 'D', 'D', 5.23659035050339, 71.3662756029244, 44.0123155054382, 2.572333333333333, None, None, None, 697.0, 697.0, 697.0, 19.8011614615062, 31.2816563027116, 43.4530778935223, 1810, None, None, None, 0.48734, None, None, None, 0.388905643541494, 0.0490041343890272, 0.152197266950354, 2.8, None, None, None, 60, None, None, None, 0.296, 0.169438233537953, 0.180905927941485, 0.967017664672948]

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



#inputs_class = [10, 11, 'D', 5.23659035050339, 71.3662756029244, 2.572333333333333, None, None, 697.0, 697.0, 19.8011614615062, 31.2816563027116, 1810, None, None, None, None, None, 0.388905643541494, 0.0490041343890272, 2.8, None, None, 60, None, None,  0.296, 0.169438233537953, 0.180905927941485]
inputs_class = [10, 11, 'D', 5.23659035050339, 71.3662756029244, 2.572333333333333, None, None, 697.0, 697.0, 19.8011614615062, 31.2816563027116, 1810, None, None, 0.48734, None, None, 0.388905643541494, 0.0490041343890272, 2.8, None, None, 60, None, None,  0.296, 0.169438233537953, 0.180905927941485]
inputs = [10, 11, 'D', 'D', 5.23659035050339, 71.3662756029244, 44.0123155054382, 2.572333333333333, None, None, None, 697.0, 697.0, 697.0, 19.8011614615062, 31.2816563027116, 43.4530778935223, 1810, None, None, None, 0.48734, None, None, None, 0.388905643541494, 0.0490041343890272, 0.152197266950354, 2.8, None, None, None, 60, None, None, None, 0.296, 0.169438233537953, 0.180905927941485, 0.967017664672948]

ao = total_emissions_small_or_large_fisheries(*inputs)
print('No time dependency')
print(ao)

fishery_w = Fishery(*inputs_class)
fishery_w.calculate_emissions()
print(fishery_w.evaluate_tier_2_defaults())
print(fishery_w.total_emissions)