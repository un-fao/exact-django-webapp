import math

def total_emissions_small_or_large_fisheries(time_impl, time_cap, rate_coefficient_w, rate_coefficient_wo, catch_start, catch_w, catch_wo, ef_diesel_default, ef_diesel_tier_2, fui_default, fui_start_tier_2, fui_w_tier_2, fui_wo_tier_2,  gwp_refrigerant_default,
                    gwp_refrigerant_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_tier_2, percentage_refrigerant_start, percentage_refrigerant_w, 
                    percentage_refrigerant_wo, tonnes_ice_default, tonnes_ice_tier_2,  kwh_ice_per_tonne_default, kwh_ice_per_tonne_tier_2, operating_margin,
                    percentage_ice_start, percentage_ice_w, percentage_ice_wo):
    
    # SINGLE EMISSION CALCULATION FUNCTIONS AND SUPPORT FUNCTIONS
    
    def emissions_catch(time_impl, time_cap, rate_coefficient, catch_start, catch_end, ef_diesel_default, ef_diesel_tier_2, fui_default, fui_start_tier_2, fui_end_tier_2):

        ef_diesel = ef_diesel_default if not ef_diesel_tier_2 else ef_diesel_tier_2

        fui_start = fui_default if not fui_start_tier_2 else fui_start_tier_2
        fui_end = fui_default if not fui_end_tier_2 else fui_end_tier_2

        ef_start = fui_start * ef_diesel / 1000
        ef_end = fui_end * ef_diesel / 1000

        annual_start = catch_start * ef_start
        annual_end = catch_end * ef_end

        rate_type = 'D'

        
        yearly = calculate_unit_distribution(rate_type, annual_start, annual_end, time_impl, time_cap)
       
        return yearly

    def emissions_refrigerant(time_impl, time_cap, rate_coefficient, gwp_refrigerant_default, gwp_refrigerant_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_tier_2, catch_start, catch_end, percentage_refrigerant_start, percentage_refrigerant_end):

        gwp_refrigerant = gwp_refrigerant_default if not gwp_refrigerant_tier_2 else gwp_refrigerant_tier_2
        quantity_lost_refrigerant = quantity_lost_refrigerant_default if not quantity_lost_refrigerant_tier_2 else quantity_lost_refrigerant_tier_2

        catch_with_refrigerant_start = catch_start * percentage_refrigerant_start
        catch_with_refrigerant_end = catch_end * percentage_refrigerant_end

        annual_start = gwp_refrigerant * quantity_lost_refrigerant * catch_with_refrigerant_start / 1000
        annual_end = gwp_refrigerant * quantity_lost_refrigerant * catch_with_refrigerant_end / 1000

        rate_type = 'D'
        yearly = calculate_unit_distribution(rate_type, annual_start, annual_end, time_impl, time_cap)

        return yearly

    def emissions_ice(time_impl, time_cap, rate_coefficient, tonnes_ice_default, kwh_ice_per_tonne_default, operating_margin, kwh_ice_per_tonne_tier_2, tonnes_ice_tier_2, catch_start, catch_end, percentage_ice_start, percentage_ice_end):

        tonnes_ice = tonnes_ice_default if not tonnes_ice_tier_2 else tonnes_ice_tier_2
        kwh_ice_per_tonne = kwh_ice_per_tonne_default if not kwh_ice_per_tonne_tier_2 else kwh_ice_per_tonne_tier_2

        ice_ef = tonnes_ice * kwh_ice_per_tonne * operating_margin / 1000

        catch_with_refrigerant_start = catch_start * percentage_ice_start
        catch_with_refrigerant_end = catch_end * percentage_ice_end

        annual_start = ice_ef * catch_with_refrigerant_start 
        annual_end = ice_ef * catch_with_refrigerant_end

        rate_type = 'D'
        yearly = calculate_unit_distribution(rate_type, annual_start, annual_end, time_impl, time_cap)

        return yearly

    def time_component(start, end, time_impl, time_cap, rate_coefficient):
            if end > start:
                return time_cap + time_impl * rate_coefficient
            else:
                return time_impl * (1 - rate_coefficient)



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
    fui_default: in DATABASE_FISH tab A6-K30 match fish category and gear category. If no exact match, match fish category and take column 'Not specified'
    fui_start_tier_2: tier 2 value, expects None or Float
    fui_w_tier_2: tier 2 value, expects None or Float
    fui_wo_tier_2: tier 2 value, expects None or Float
    gwp_refrigerant_default: default global warming potential of refrigerant, value is 1810 for both Small and Large Scale Fisheries
    gwp_refrigerant_tier_2: tier 2 value, expects None or Float
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

    emissions_catch_w = emissions_catch(time_impl, time_cap, rate_coefficient_w, catch_start, catch_w, ef_diesel_default, ef_diesel_tier_2, fui_default, fui_start_tier_2, fui_w_tier_2) 
    emissions_catch_wo = emissions_catch(time_impl, time_cap, rate_coefficient_wo, catch_start, catch_wo, ef_diesel_default, ef_diesel_tier_2, fui_default, fui_start_tier_2, fui_wo_tier_2)

    emissions_refrigerant_w = emissions_refrigerant(time_impl, time_cap, rate_coefficient_w, gwp_refrigerant_default, gwp_refrigerant_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_tier_2, catch_start, catch_w, percentage_refrigerant_start, percentage_refrigerant_w)
    emissions_refrigerant_wo = emissions_refrigerant(time_impl, time_cap, rate_coefficient_wo, gwp_refrigerant_default, gwp_refrigerant_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_tier_2, catch_start, catch_wo, percentage_refrigerant_start, percentage_refrigerant_wo)

    emissions_ice_w = emissions_ice(time_impl, time_cap, rate_coefficient_w, tonnes_ice_default, kwh_ice_per_tonne_default, operating_margin, kwh_ice_per_tonne_tier_2, tonnes_ice_tier_2, catch_start, catch_w, percentage_ice_start, percentage_ice_w)
    emissions_ice_wo = emissions_ice(time_impl, time_cap, rate_coefficient_wo, tonnes_ice_default, kwh_ice_per_tonne_default, operating_margin, kwh_ice_per_tonne_tier_2,tonnes_ice_tier_2, catch_start, catch_wo, percentage_ice_start, percentage_ice_wo)

    total_w = sum(emissions_catch_w) + sum(emissions_refrigerant_w) + sum(emissions_ice_w)
    total_wo = sum(emissions_catch_wo) + sum(emissions_refrigerant_wo) + sum(emissions_ice_wo)

    ice = sum(emissions_ice_w)
    refrigerant = sum(emissions_refrigerant_w)
    catch = sum(emissions_catch_w)

    ice_wo = sum(emissions_ice_wo)
    refrigerant_wo = sum(emissions_refrigerant_wo)
    catch_wo = sum(emissions_catch_wo)

    yearly_breakdown(emissions_catch_w, emissions_refrigerant_w, emissions_refrigerant_w, 'with_project', total_w)
    yearly_breakdown(emissions_catch_wo, emissions_refrigerant_wo, emissions_refrigerant_wo, 'without_project', total_wo)

                                                                             
    return total_w, total_wo, total_w - total_wo

def total_inland_coastal_aquaculture(production_start, production_w, nitrous_ef_default, nitrous_ef_tier_2, nitrous_constant, time_impl, time_cap, rate_coefficient_w, rate_coefficient_wo, production_wo,feed_start, feed_w, ef_feed_default, ef_feed_tier_2, feed_wo):

    # INTERMEDIATE FUNCTIONS AND SUPPORT FUNCTIONS
    def nitrous_emissions(production_start, production_end, nitrous_ef_default, nitrous_ef_tier_2, nitrous_constant, time_impl, time_cap, rate_coefficient):

        # this function is the same as flooded rice ch4 calculation, that's why it says area
        def time_dependency(area_start, area, rate_coefficient, time_impl, time_cap):
            if area > area_start:
                return time_cap + time_impl * rate_coefficient
            else:
                return time_impl * (1 - rate_coefficient)

        nitrous_ef = nitrous_ef_default if not nitrous_ef_tier_2 else nitrous_ef_tier_2
        nitrous_ef_production = nitrous_ef * 44/28 * nitrous_constant

        nitrous_emissions_end = production_end * nitrous_ef_production
        nitrous_emissions_start = production_start * nitrous_ef_production

        total_nitrous = (min(nitrous_emissions_start, nitrous_emissions_end) * (time_cap + time_impl) + abs(nitrous_emissions_end - nitrous_emissions_start) * time_dependency(nitrous_emissions_start, nitrous_emissions_end, rate_coefficient, time_impl, time_cap))
        
        return total_nitrous

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

        total_feed = (min(annual_feed_start, annual_feed_end) * (time_cap + time_impl) + abs(annual_feed_start - annual_feed_end) * time_dependency(annual_feed_start, annual_feed_end, rate_coefficient, time_impl, time_cap))

        return total_feed

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

    total_w = nitrous_emissions_w + feed_emissions_w
    total_wo = nitrous_emissions_wo + feed_emissions_wo

    return total_w, total_wo, total_w - total_wo

def calculate_unit_distribution(rate_type, units_start ,units_end, time_impl, time_cap):

    if rate_type == 'D':

        """
        With a linear rate type we can consider yearly emissions to go from an annual emission value at time 0 to an final annual emissions value in a time period of time_impl years. 
        The emissions then remain constant throughout all capitalization years (time_cap).
        In order to evaluate how this happens in a linear matter we can consider the slope of the line that connects the two points (0, units_start) and (time_impl, units_end).
        Below we can see how m is calculated, with m representing the slope of the line. after that the values of emissions at each year are calculated by using the formula y = mx + b, where m is the slope of the line and b is the y-intercept.

        The total emissions can then be calculated as the integral between year[i] and year[i+1] of the function y = mx + b, where m is the slope of the line and b is the y-intercept, to which we add the emissions at the year [i+1] if increasing


        | annual_emissions
        |
        |\
        | \
        |  \
        |   \
        |    \
        |     \ ________________________________
        --------------------------------------------> time
               | time implementation            | time capitalization
        """


        m = math.atan((units_end - units_start) / time_impl)
        y = [math.tan(m) * i + units_start for i in range(0, time_impl +1)]

        if units_start > units_end:
            y = [y[i]-abs((y[i] - y[i+1]))/2 for i in range(0, len(y) - 1)]

        else: 
            y = [y[i]+abs((y[i] - y[i+1]))/2 for i in range(0, len(y) - 1)]

        y.extend([units_end for i in range(0, time_cap)])



    return y


import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def get_cumulated_array(data, **kwargs):
    cum = data.clip(**kwargs)
    cum = np.cumsum(cum, axis=0)
    d = np.zeros(np.shape(data))
    d[1:] = cum[:-1]
    return d  

def yearly_breakdown(catch, refrigerant, ice, w_wo, total):

    plt.style.use('Solarize_Light2')

    years = range(len(catch))
    data = np.array([catch, refrigerant, ice])

    data_shape = np.shape(data)

    cumulated_data = get_cumulated_array(data, min=0)
    cumulated_data_neg = get_cumulated_array(data, max=0)

    # Re-merge negative and positive data.
    row_mask = (data<0)
    cumulated_data[row_mask] = cumulated_data_neg[row_mask]
    data_stack = cumulated_data

    names = ['Catch Emissions', 'Refrigerant Emissions', 'Ice Emissions']

    fig = plt.figure(figsize =(15, 10))
    ax = plt.subplot(111)

    color_palette = sns.color_palette('pastel')

    for i in np.arange(0, data_shape[0]):
        ax.bar(np.arange(data_shape[1]), data[i], bottom=data_stack[i], color=color_palette[i], label = names[i])
    
    plt.xlabel('Year')
    plt.xticks(years, [str(i + 1) for i in years])

    plt.ylabel('Yearly Emission (tCO2-e)')
    plt.legend()
    plt.title('Break-Down of Emissions, total emissions: ' + str(total) + ' tCO2-e')

    plt.savefig(f'yearly_breakdown_{w_wo}_correct.png')


em = total_emissions_small_or_large_fisheries(20, 9, 0.5, 0.5, 500, 450, 1000, 2.572333333334, None, 73, None, 45, 73, 1810, None, 0.083, None, 0.5, 0.8, 0.8, 2.8, None, 60,  None, 0.573978947, 0.5, 0.8, 0.7)
print(em)


# em = total_inland_coastal_aquaculture(757, 213, 0.00169, None, 265, 20, 9, 0.5, 0.5, 45, 500, 453, 0, None, 456)
# print(em)