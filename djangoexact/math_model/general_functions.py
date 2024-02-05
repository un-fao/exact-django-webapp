# download a package to calculate logarithm in base e
import math


def yearly_parameter_breakdown(start_value, end_value, years_implementation, years_capitalization, function):
    # EXPONENTIAL CASE
    if function == "exponential":
        # calculate the parameters for the function a*b^x
        a = min(start_value, end_value)
        b = (max(start_value, end_value) / min(start_value, end_value)) ** (1 / years_implementation)

        # Calculate the yearly breakdown
        if start_value < end_value:
            yearly_breakdown = [a * b**i for i in range(years_implementation + 1)]
        else:
            yearly_breakdown = [a * b**i for i in range(years_implementation + 1)]
            yearly_breakdown.reverse()

        yearly_breakdown.extend([yearly_breakdown[-1] for i in range(years_capitalization)])

        # return the yearly breakdown
        return yearly_breakdown

    if function == "linear":
        # calculate the parameters for the function a + bx
        a = min(start_value, end_value)
        b = (abs(start_value - end_value)) / years_implementation

        # Calculate the yearly breakdown
        if start_value < end_value:
            yearly_breakdown = [a + b * i for i in range(years_implementation + 1)]
        else:
            yearly_breakdown = [a + b * i for i in range(years_implementation + 1)]
            yearly_breakdown.reverse()

        yearly_breakdown.extend([yearly_breakdown[-1] for i in range(years_capitalization)])

        # return the yearly breakdown
        return yearly_breakdown

    if function == "immediate":
        return [end_value for i in range(years_implementation + years_capitalization + 1)]


# create a function to plot the yearly breakdown using matplotlib, x axis is the year (range(years_implementation + years_capitalization + 1)) and the y axis is the yearly breakdown
def plot_yearly_breakdown(yearly_breakdown):
    import matplotlib.pyplot as plt

    plt.plot(range(len(yearly_breakdown)), yearly_breakdown)
    plt.xticks(range(len(yearly_breakdown)), range(len(yearly_breakdown)))
    plt.show()


# make a function the same as the above where the input variables are 3, exponential, linear and immediate. All three are plotted on the y axis, with the x axis being the year. Plot as a line graph
def plot_all_functions(yearly_breakdown_exponential, yearly_breakdown_linear, yearly_breakdown_immediate):
    import matplotlib.pyplot as plt

    plt.plot(range(len(yearly_breakdown_exponential)), yearly_breakdown_exponential, label="Exponential")
    plt.plot(range(len(yearly_breakdown_linear)), yearly_breakdown_linear, label="Linear")
    plt.plot(range(len(yearly_breakdown_immediate)), yearly_breakdown_immediate, label="Immediate")
    plt.xticks(range(len(yearly_breakdown_exponential)), range(len(yearly_breakdown_exponential)))
    plt.legend()
    plt.show()


# exponential = yearly_parameter_breakdown(200, 1000, 20, 5, 'exponential')
# print(exponential)
# linear = yearly_parameter_breakdown(200, 1000, 20, 5, 'linear')
# print(linear)
# immediate = yearly_parameter_breakdown(200, 1000, 20, 5, 'immediate')
# print(immediate)

# plot_all_functions(exponential, linear, immediate)
