from general_functions import yearly_time_dependent_parameter_breakdown, input_single_calculation, yearly_constant_emissions_breakdown

class Inputs:

    def __init__(self, unit_start, unit_end, rate_type, ipcc_factor_co2_eq, tier_2_factor_co2_eq, unit_factor_co2_eq, emissions_factor_co2_eq, time_impl, time_cap,
                           ipcc_factor_n2o, tier_2_factor_n2o, unit_factor_n2o, emissions_factor_n2o, unit_factor_eq, emissions_factor_eq):
        
        self.unit_start = unit_start
        self.unit_end = unit_end
        self.rate_type = rate_type
        self.ipcc_factor_co2_eq = ipcc_factor_co2_eq
        self.tier_2_factor_co2_eq = tier_2_factor_co2_eq
        self.unit_factor_co2_eq = unit_factor_co2_eq
        self.emissions_factor_co2_eq = emissions_factor_co2_eq
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.ipcc_factor_n2o = ipcc_factor_n2o
        self.tier_2_factor_n2o = tier_2_factor_n2o
        self.unit_factor_n2o = unit_factor_n2o
        self.emissions_factor_n2o = emissions_factor_n2o
        self.unit_factor_eq = unit_factor_eq
        self.emissions_factor_eq = emissions_factor_eq
        

        # RESULTS
        self.yearly_co2_emissions = []
        self.yearly_n2o_emissions = []
        self.yearly_co2_eq_emissions = []
        self.emissions_total_yearly = []

        self.total_co2_emissions = 0
        self.total_n2o_emissions = 0
        self.total_co2_eq_emissions = 0
        self.total_emissions = 0

        pass

    def calculate_emissions(self):
        
        if self.unit_factor_co2_eq is None or self.emissions_factor_co2_eq is None:
            self.yearly_co2_eq_emissions, self.total_co2_eq_emissions = [], 0
        else:
            self.yearly_co2_eq_emissions, self.total_co2_eq_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_co2_eq, 
                                                                                                 self.tier_2_factor_co2_eq, self.unit_factor_co2_eq, 
                                                                                                 self.emissions_factor_co2_eq, self.time_impl, self.time_cap, self.rate_type)
        
        if self.unit_factor_n2o is None or self.emissions_factor_n2o is None:
            self.yearly_n2o_emissions, self.total_n2o_emissions = [], 0
        else:
            self.yearly_n2o_emissions, self.total_n2o_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_n2o,
                                                                                        self.tier_2_factor_n2o, self.unit_factor_n2o, self.emissions_factor_n2o, 
                                                                                        self.time_impl, self.time_cap, self.rate_type)
            

        if self.unit_factor_eq is None or self.emissions_factor_eq is None:
            self.yearly_co2_emissions, self.total_co2_emissions = [], 0
        else:
            self.yearly_co2_emissions, self.total_co2_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_co2_eq, 
                                                                                           self.tier_2_factor_co2_eq, self.unit_factor_eq, self.emissions_factor_eq,
                                                                                           self.time_impl, self.time_cap, self.rate_type)

        self.emissions_total_yearly = [sum(x) for x in zip(self.yearly_co2_emissions, self.yearly_n2o_emissions, self.yearly_co2_eq_emissions)]
        self.total_emissions = sum(self.emissions_total_yearly)

        return self.total_emissions
        

    def evaluate_tier_2_defaults():
        pass

class Irrigation:

    def __init__(self, ef_default, ef_tier_2, total_dynamic_head_default, total_dynamic_head_tier_2, average_pressure_default, average_pressure_tier_2, 
                 pumping_efficiency_default, pumping_efficiency_tier_2, erh, depth,
                 units_start, units_end, rate_type, time_impl, time_cap, 
                 electricity_multiplier_end):
        
        self.ef_default = ef_default
        self.ef_tier_2 = ef_tier_2
        self.total_dynamic_head_default = total_dynamic_head_default
        self.total_dynamic_head_tier_2 = total_dynamic_head_tier_2
        self.average_pressure_default = average_pressure_default
        self.average_pressure_tier_2 = average_pressure_tier_2
        self.pumping_efficiency_default = pumping_efficiency_default
        self.pumping_efficiency_tier_2 = pumping_efficiency_tier_2
        self.erh = erh
        self.depth = depth
        self.units_start = units_start
        self.units_end = units_end
        self.rate_type = rate_type
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.electricity_multiplier_end = electricity_multiplier_end

        # RESULTS
        self.emissions_total_yearly = []
        self.total_emissions = 0

    def calculate_emissions(self,):

        def ef_calculation(ef_default, ef_tier_2, total_dynamic_head_default, total_dynamic_head_tier_2, average_pressure_default, average_pressure_tier_2, pumping_efficiency_default, pumping_efficiency_tier_2, erh, depth ):
            pumping_efficiency = pumping_efficiency_default if not pumping_efficiency_tier_2 else pumping_efficiency_tier_2
            average_pressure = average_pressure_default if not average_pressure_tier_2 else average_pressure_tier_2
            total_dynamic_head_default = average_pressure * 10
            total_dynamic_head = total_dynamic_head_default if not total_dynamic_head_tier_2 else total_dynamic_head_tier_2
            ef = ef_default if not ef_tier_2 else ef_tier_2
            gwir = gwir * 10

            total_energy = gwir * erh
            A_efficiency = total_energy / pumping_efficiency

            b_depth_tph = A_efficiency * (depth + total_dynamic_head)
            C_tco2 = b_depth_tph * ef ### this is the equivalent of the ef_ipcc in general calculations for input

            return C_tco2
        
        ef = ef_calculation(self.ef_default, self.ef_tier_2, self.total_dynamic_head_default, self.total_dynamic_head_tier_2, self.average_pressure_default, self.average_pressure_tier_2, self.pumping_efficiency_default, self.pumping_efficiency_tier_2, self.erh, self.depth )

        # THESE ARE SAVED IN ORDER TO MULTIPLY BY ELECTRICITY MULTIPLIER
        yearly_emissions, total_emissions = input_single_calculation(self.units_start, self.units_end, self.rate_type, ef, None, 1, 1, self.time_impl, self.time_cap)
        yearly_emissions = [x * (1 + self.electricity_multiplier_end) for x in yearly_emissions] if self.electricity_multiplier_end else yearly_emissions
        
        self.emissions_total_yearly = yearly_emissions
        self.total_emissions = sum(self.emissions_total_yearly)

        return self.total_emissions

    def evaluate_tier_2_defaults():
        pass

class Roads:

    def __init__(self, ef_ipcc:float, ef_tier_2, units_end, time_impl, time_cap, rate_type):

        self.ef_ipcc = ef_ipcc
        self.ef_tier_2 = ef_tier_2
        self.units_end = units_end
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate_type = rate_type

        #  RESULTS
        self.emissions_total_yearly = []
        self.total_emissions = 0
        
    def calculate_emissions(self):

        # NOTE: check this, looks weird
        ef = self.ef_ipcc if self.ef_ipcc else self.ef_tier_2

        self.total_emissions = self.units_end * ef / 1000 # to convert the ef from kg to g
        self.emissions_total_yearly = yearly_constant_emissions_breakdown(self.total_emissions, self.time_impl, self.time_cap)

        return self.emissions_total

    def evaluate_tier_2_defaults():
        pass

class EnergyConsumption:

    def __init__(self, emissions_factor, specific_factor, mwh_start, mwh_end, rate_type, time_impl, time_cap):

        self.emissions_factor = emissions_factor
        self.specific_factor = specific_factor
        self.mwh_start = mwh_start
        self.mwh_end = mwh_end
        self.rate_type = rate_type
        self.time_impl = time_impl
        self.time_cap = time_cap

        # RESULTS
        self.emissions_total_yearly = []
        self.total_emissions = 0

    def calculate_emissions(self,):

        factor = self.specific_factor if self.specific_factor else self.emissions_factor

        annual_start = factor * self.mwh_start
        annual_end = factor * self.mwh_end

        self.emissions_total_yearly = yearly_time_dependent_parameter_breakdown(self.time_impl, self.time_cap, annual_start, annual_end, self.rate_type)
        self.total_emissions = sum(self.emissions_total_yearly)

        return self.total_emissions

    def evaluate_tier_2_defaults():
        pass