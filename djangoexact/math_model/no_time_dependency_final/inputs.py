from .general_functions import yearly_time_dependent_parameter_breakdown, input_single_calculation, yearly_constant_emissions_breakdown
import math, traceback
class Inputs:

    def __init__(self, unit_start, unit_end, rate_type, ipcc_factor_co2, tier_2_factor_co2, unit_factor_co2, emissions_factor_co2, time_impl, time_cap,
                           ipcc_factor_n2o, tier_2_factor_n2o, unit_factor_n2o, emissions_factor_n2o, ipcc_factor_eq, tier_2_factor_eq, unit_factor_eq, emissions_factor_eq):
        
        self.unit_start = unit_start
        self.unit_end = unit_end
        self.rate_type = rate_type

        self.ipcc_factor_co2 = ipcc_factor_co2
        self.tier_2_factor_co2 = tier_2_factor_co2
        self.unit_factor_co2 = unit_factor_co2
        self.emissions_factor_co2 = emissions_factor_co2

        self.time_impl = time_impl
        self.time_cap = time_cap

        self.ipcc_factor_n2o = ipcc_factor_n2o
        self.tier_2_factor_n2o = tier_2_factor_n2o
        self.unit_factor_n2o = unit_factor_n2o
        self.emissions_factor_n2o = emissions_factor_n2o
        
        self.ipcc_factor_eq = ipcc_factor_eq
        self.tier_2_factor_eq = tier_2_factor_eq
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
        
        try:
            if self.unit_factor_co2 is None or self.emissions_factor_co2 is None:
                self.yearly_co2_eq_emissions, self.total_co2_eq_emissions = [0 for i in range(0, self.time_impl + self.time_cap)], 0
            else:
                self.yearly_co2_eq_emissions, self.total_co2_eq_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_co2, 
                                                                                                    self.tier_2_factor_co2, self.unit_factor_co2, 
                                                                                                    self.emissions_factor_co2, self.time_impl, self.time_cap, self.rate_type)
            
            if self.unit_factor_n2o is None or self.emissions_factor_n2o is None:
                self.yearly_n2o_emissions, self.total_n2o_emissions = [0 for i in range(0, self.time_impl + self.time_cap)], 0
            else:
                self.yearly_n2o_emissions, self.total_n2o_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_n2o,
                                                                                            self.tier_2_factor_n2o, self.unit_factor_n2o, self.emissions_factor_n2o, 
                                                                                            self.time_impl, self.time_cap, self.rate_type)
                

            if self.unit_factor_eq is None or self.emissions_factor_eq is None:
                self.yearly_co2_emissions, self.total_co2_emissions = [0 for i in range(0, self.time_impl + self.time_cap)], 0
            else:
                self.yearly_co2_emissions, self.total_co2_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_eq,
                                                                                               self.tier_2_factor_eq, self.unit_factor_eq, self.emissions_factor_eq, 
                                                                                            self.time_impl, self.time_cap, self.rate_type)

            self.emissions_total_yearly = [sum(x) for x in zip(self.yearly_co2_emissions, self.yearly_n2o_emissions, self.yearly_co2_eq_emissions)]
            self.total_emissions = sum(self.emissions_total_yearly)

            return self.total_emissions
        
        except Exception as e:
            traceback.print_exc()
            return None

    def evaluate_tier_2_defaults():
        pass

class OperationPhaseIrrigation:

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
            
            try:
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
            
            except:
                traceback.print_exc()
                return None
        
        try:
            ef = ef_calculation(self.ef_default, self.ef_tier_2, self.total_dynamic_head_default, self.total_dynamic_head_tier_2, self.average_pressure_default, self.average_pressure_tier_2, self.pumping_efficiency_default, self.pumping_efficiency_tier_2, self.erh, self.depth )

            # THESE ARE SAVED IN ORDER TO MULTIPLY BY ELECTRICITY MULTIPLIER
            yearly_emissions, total_emissions = input_single_calculation(self.units_start, self.units_end, self.rate_type, ef, None, 1, 1, self.time_impl, self.time_cap)
            yearly_emissions = [x * (1 + self.electricity_multiplier_end) for x in yearly_emissions] if self.electricity_multiplier_end else yearly_emissions
            
            self.emissions_total_yearly = yearly_emissions
            self.total_emissions = sum(self.emissions_total_yearly)

            return self.total_emissions
        
        except:
            traceback.print_exc()
            return None

    def evaluate_tier_2_defaults():
        pass

class Roads:

    def __init__(self, ef_ipcc:float, ef_tier_2, units_end, time_impl, time_cap, rate_type):

        self.ef_ipcc = ef_ipcc     # Match Building and Roads type to Energy DB Sheet Table A26-B45
        self.ef_tier_2 = ef_tier_2 # Tier 2 Value
        self.units_end = units_end # Input
        self.time_impl = time_impl # Project Input
        self.time_cap = time_cap   # Project Input
        self.rate_type = rate_type # Rate Type

        #  RESULTS
        self.emissions_total_yearly = []
        self.total_emissions = 0
        
    def calculate_emissions(self):

        try:
            # NOTE: check this, looks weird
            ef = self.ef_ipcc if self.ef_ipcc else self.ef_tier_2

            self.total_emissions = self.units_end * ef / 1000 # to convert the ef from kg to g
            self.emissions_total_yearly = yearly_constant_emissions_breakdown(self.total_emissions, self.time_impl, self.time_cap)

            return self.total_emissions
        
        except:
            traceback.print_exc()

            return None    

    def evaluate_tier_2_defaults():
        pass

class ElectryicityConsumption:

    def __init__(self, emissions_factor, specific_factor, mwh_start, mwh_end, percent_loss_transportation, rate_type, time_impl, time_cap):

        self.emissions_factor = emissions_factor                        # Match Country and Source of Emission Factor to Elec Table (columns 6 or 7)
        self.specific_factor = specific_factor                          # Tier 2 Value
        self.mwh_start = mwh_start                                      # User Input
        self.mwh_end = mwh_end                                          # User Input
        self.percent_loss_transportation = percent_loss_transportation  # User Input expects number between 0 and 1
        self.rate_type = rate_type                                      # Activity Input
        self.time_impl = time_impl                                      # Project/Activity Input
        self.time_cap = time_cap                                        # Project/Activity Input

        # RESULTS
        self.emissions_total_yearly = []
        self.total_emissions = 0

    def calculate_emissions(self,):

        factor = self.specific_factor if self.specific_factor else self.emissions_factor

        annual_start = factor * self.mwh_start
        annual_end = factor * self.mwh_end

        self.emissions_total_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.time_impl, self.time_cap, self.rate_type)

        # Adjust for transmission losses
        self.emissions_total_yearly = [x * (1 + self.percent_loss_transportation) for x in self.emissions_total_yearly]
        
        self.total_emissions = sum(self.emissions_total_yearly)

        return self.total_emissions

    def evaluate_tier_2_defaults():
        pass

class FuelConsumption:

    def __init__(self, emissions_factor, specific_factor, mwh_start, mwh_end, rate_type, time_impl, time_cap):

        self.emissions_factor = emissions_factor    # Match Fuel Type to table IPCC A1727-B1741
        self.specific_factor = specific_factor      # Tier 2 Value
        self.mwh_start = mwh_start                  # User Input
        self.mwh_end = mwh_end                      # User Input
        self.rate_type = rate_type                  # Activity Input
        self.time_impl = time_impl                  # Project/Activity Input
        self.time_cap = time_cap                    # Project/Activity Input

        # RESULTS
        self.emissions_total_yearly = []
        self.total_emissions = 0

    def calculate_emissions(self,):

        try:

            factor = self.specific_factor if self.specific_factor else self.emissions_factor

            annual_start = factor * self.mwh_start
            annual_end = factor * self.mwh_end

            self.emissions_total_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.time_impl, self.time_cap, self.rate_type)
            self.total_emissions = sum(self.emissions_total_yearly)

            return self.total_emissions
        
        except:

            traceback.print_exc()
            
            return None

    def evaluate_tier_2_defaults():
        pass

class SolidConsumption:
    
    def __init__(self, joules_factor, co2_factor, ch4_factor, n2o_factor, account_for_co2_boolean, methane_constant, nitrous_constant, specific_factor, mwh_start, mwh_end, rate_type, time_impl, time_cap):

        self.joules_factor = joules_factor                                  # Match Fuel Type to table IPCC A1750 COLUMN C
        self.co2_factor = co2_factor                                        # Match Fuel Type to table IPCC A1750 COLUMN D
        self.ch4_factor = ch4_factor                                        # Match Fuel Type to table IPCC A1750 COLUMN E
        self.n2o_factor = n2o_factor                                        # Match Fuel Type to table IPCC A1750 COLUMN F
        self.account_for_co2_boolean = account_for_co2_boolean              # Tier 2 Value
        self.methane_constant = methane_constant                            # Tier 2 Value
        self.nitrous_constant = nitrous_constant                            # Tier 2 Value
        self.specific_factor = specific_factor                              # Tier 2 Value
        self.mwh_start = mwh_start                                          # User Input
        self.mwh_end = mwh_end                                              # User Input
        self.rate_type = rate_type                                          # Activity Input
        self.time_impl = time_impl                                          # Project/Activity Input
        self.time_cap = time_cap                                            # Project/Activity Input

        # RESULTS
        self.emissions_total_yearly = []
        self.total_emissions = 0

    def calculate_emissions(self,):

        def calculate_factor(joules_factor, co2_factor, ch4_factor, n2o_factor, account_for_co2_boolean, methane_constant, nitrous_constant):
            
            try:
                if account_for_co2_boolean:
                    return joules_factor * (co2_factor + ch4_factor * methane_constant + n2o_factor * nitrous_constant) / math.pow(10, 6)
                else:
                    return joules_factor * (ch4_factor * methane_constant + n2o_factor * nitrous_constant) / math.pow(10, 6)
            except:
                traceback.print_exc()

        try:
            factor = self.specific_factor if self.specific_factor else calculate_factor(self.joules_factor, self.co2_factor, self.ch4_factor, self.n2o_factor, self.account_for_co2_boolean, self.methane_constant, self.nitrous_constant)

            annual_start = factor * self.mwh_start
            annual_end = factor * self.mwh_end

            self.emissions_total_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.time_impl, self.time_cap, self.rate_type)
            self.total_emissions = sum(self.emissions_total_yearly)

            return self.total_emissions
        
        except:

            traceback.print_exc()

            return None

    def evaluate_tier_2_defaults():
        pass

class NewIrrigation:

    def __init__(self, ef_ref, ef_tier_2, units_start, units_end, time_impl, time_cap, rate_type):

        self.ef_ref = ef_ref       # Match Irrigation Type to Energy DB A7:B16 column 2
        self.ef_tier_2 = ef_tier_2
        # TODO: ADD HECTARS START AND REMOVE FROM FINAL
        self.units_start = units_start
        self.units_end = units_end
        self.time_impl = time_impl # Project Input
        self.time_cap = time_cap   # Project Input
        self.rate_type = rate_type # Rate Type

        # RESULTS
        self.emissions_total_yearly = []
        self.total_emissions = 0

    def calculate_emissions(self,):

        ef = self.ef_ref if not self.ef_tier_2 else self.ef_tier_2

        self.total_emissions = ef * (self.units_end - self.units_start) / 1000
        self.emissions_total_yearly = yearly_constant_emissions_breakdown(self.total_emissions, self.time_impl, self.time_cap)
        
    def evaluate_tier_2_defaults():
        pass

