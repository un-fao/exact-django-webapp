import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

def yearly_emissions(yearly_total, years):

    color_palette = sns.color_palette('pastel')
    fig = plt.figure(figsize =(15, 10))
    bars = plt.bar(years, yearly_total, color = color_palette[2])

    plt.xlabel('Year')
    plt.ylabel('Yearly Emission (tCO2-e)')
    plt.title('Total Emissions Year by Year for Afforestation')

    for (rect,i) in zip(bars,range(0, len(yearly_total))):
        height = rect.get_height()
        plt.text(rect.get_x() + rect.get_width()/2.0, height, '%d' % int(height), ha='center', va='bottom')

    plt.xticks(years)

    plt.savefig('graphs/yearly_emissions.png')

def yearly_breakdown(total_non_time_w, total_time_dependent_w, time_impl, years):

    dom = np.array([(total_non_time_w[0]/(time_impl)) if i < time_impl else 0 for i in years ])
    bio_loss = np.array([(total_non_time_w[1]/(time_impl)) if i < time_impl else 0 for i in years ])
    fire = np.array([(total_non_time_w[2]/(time_impl)) if i < time_impl else 0 for i in years ])
    soil = np.array([i[1] for i in total_time_dependent_w])
    bio_gain = np.array([i[0] for i in total_time_dependent_w])

    # print(bio_gain)

    data = np.array([dom, bio_loss, fire, soil, bio_gain])

    data_shape = np.shape(data)

    cumulated_data = get_cumulated_array(data, min=0)
    cumulated_data_neg = get_cumulated_array(data, max=0)

    # Re-merge negative and positive data.
    row_mask = (data<0)
    cumulated_data[row_mask] = cumulated_data_neg[row_mask]
    data_stack = cumulated_data

    names = ['DOM Gain', 'Biomass Loss', 'Fire Emissions', 'Soil Emissions', 'Biomass Gain']

    fig = plt.figure(figsize =(15, 10))
    ax = plt.subplot(111)

    color_palette = sns.color_palette('pastel')

    for i in np.arange(0, data_shape[0]):
        ax.bar(np.arange(data_shape[1]), data[i], bottom=data_stack[i], color=color_palette[i], label = names[i])
    
    plt.xlabel('Year')
    plt.xticks(years)

    plt.ylabel('Yearly Emission (tCO2-e)')
    plt.legend()
    plt.title('Break-Down of Emissions Year by Year for Afforestation')

    plt.savefig('graphs/yearly_breakdown.png')
# Take negative and positive data apart and cumulate
def get_cumulated_array(data, **kwargs):
    cum = data.clip(**kwargs)
    cum = np.cumsum(cum, axis=0)
    d = np.zeros(np.shape(data))
    d[1:] = cum[:-1]
    return d  

def show_before_after_20(units_per_year_w_before_20, units_per_year_w_after_20, years_w):

    dom = np.array(units_per_year_w_before_20)
    bio_loss = np.array(units_per_year_w_after_20)
    

    # print(bio_gain)

    data = np.array([dom, bio_loss])

    data_shape = np.shape(data)

    cumulated_data = get_cumulated_array(data, min=0)
    cumulated_data_neg = get_cumulated_array(data, max=0)

    # Re-merge negative and positive data.
    row_mask = (data<0)
    cumulated_data[row_mask] = cumulated_data_neg[row_mask]
    data_stack = cumulated_data

    names = ['Area Before 20', 'Area After 20']

    fig = plt.figure(figsize =(15, 10))
    ax = plt.subplot(111)

    color_palette = sns.color_palette('pastel')

    for i in np.arange(0, data_shape[0]):
        ax.bar(np.arange(data_shape[1]), data[i], bottom=data_stack[i], color=color_palette[i], label = names[i])
    
    plt.xticks([i+1 for i in years_w])
    plt.xlabel('Year')
    plt.ylabel('Cumulative Area')
    plt.legend()
    plt.title('Break-Down of Area by time of Plantation')

    plt.savefig('graphs/area_before_after_20.png')

def make_plots(units_per_year_w_before_20, units_per_year_w_after_20, years_w, total_non_time_w, total_time_dependent_w, time_impl, total_w):

    yearly_emissions(total_w, years_w)
    yearly_breakdown(total_non_time_w, total_time_dependent_w, time_impl, years_w)
    show_before_after_20(units_per_year_w_before_20, units_per_year_w_after_20, years_w)