import math
import traceback

from .generalized_modules import BaseModule

from .general_functions import (
    input_single_calculation,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_parameter_breakdown,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)


class Inputs(BaseModule):
    def __init__(self, unit_start, unit_end, rate_type, ipcc_factor_co2, tier_2_factor_co2, unit_factor_co2, emissions_factor_co2, time_impl, time_cap, ipcc_factor_n2o, tier_2_factor_n2o, unit_factor_n2o, emissions_factor_n2o, ipcc_factor_eq, tier_2_factor_eq, unit_factor_eq, emissions_factor_eq, delay):

        super().__init__(time_impl, time_cap, rate_type, delay)

        self.unit_start = unit_start
        self.unit_end = unit_end

        self.ipcc_factor_co2 = ipcc_factor_co2
        self.tier_2_factor_co2 = tier_2_factor_co2
        self.unit_factor_co2 = unit_factor_co2
        self.emissions_factor_co2 = emissions_factor_co2

        self.ipcc_factor_n2o = ipcc_factor_n2o
        self.tier_2_factor_n2o = tier_2_factor_n2o
        self.unit_factor_n2o = unit_factor_n2o
        self.emissions_factor_n2o = emissions_factor_n2o

        self.ipcc_factor_eq = ipcc_factor_eq
        self.tier_2_factor_eq = tier_2_factor_eq
        self.unit_factor_eq = unit_factor_eq
        self.emissions_factor_eq = emissions_factor_eq


        pass

    def calculate_emissions(self):
        try:
            if self.unit_factor_co2 is None or self.emissions_factor_co2 is None:
                yearly_co2_eq_emissions, total_co2_eq_emissions = [0 for i in range(0, self.implementation_time + self.capitalization_time)], 0
            else:
                yearly_co2_eq_emissions, total_co2_eq_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_co2, self.tier_2_factor_co2, self.unit_factor_co2, self.emissions_factor_co2, self.implementation_time, self.capitalization_time, self.rate_type)

            if self.unit_factor_n2o is None or self.emissions_factor_n2o is None:
                yearly_n2o_emissions, total_n2o_emissions = [0 for i in range(0, self.implementation_time + self.capitalization_time)], 0
            else:
                yearly_n2o_emissions, total_n2o_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_n2o, self.tier_2_factor_n2o, self.unit_factor_n2o, self.emissions_factor_n2o, self.implementation_time, self.capitalization_time, self.rate_type)

            if self.unit_factor_eq is None or self.emissions_factor_eq is None:
                yearly_co2_emissions, total_co2_emissions = [0 for i in range(0, self.implementation_time + self.capitalization_time)], 0
            else:
                yearly_co2_emissions, total_co2_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_eq, self.tier_2_factor_eq, self.unit_factor_eq, self.emissions_factor_eq, self.implementation_time, self.capitalization_time, self.rate_type)

            co2_eq_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in yearly_co2_eq_emissions], ActivityTypes.CO2_EQUIVALENT_VC, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(co2_eq_emission_set)

            co2_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in yearly_co2_emissions], ActivityTypes.CO2_FIELD, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(co2_emission_set)

            n2o_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in yearly_n2o_emissions], ActivityTypes.N20_FIELD, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(n2o_emission_set)

        except Exception as e:
            traceback.print_exc()


class OperationPhaseIrrigation(BaseModule):
    def __init__(self, ef_default, ef_tier_2, total_dynamic_head_tier_2, average_pressure_default, average_pressure_tier_2, pumping_efficiency_default, pumping_efficiency_tier_2, erh_electricity, fuel_density, fuel_net_calorific_values, depth, units_start, units_end, rate_type, time_impl, time_cap, transportation_loss, gwir):
        
        self.units_start = units_start
        self.units_end = units_end
    
        self.ef_default = ef_default  # Match Source of Energy to table EnergyDB G7-H13 column 2
        self.ef_tier_2 = ef_tier_2  # Tier 2 Value
        self.total_dynamic_head_tier_2 = total_dynamic_head_tier_2  # Tier 2 Value
        self.average_pressure_default = average_pressure_default  # Match Irrigation System type to Energy DB Table O7-S12, column 4
        self.average_pressure_tier_2 = average_pressure_tier_2  # Tier 2 Value
        self.pumping_efficiency_default = pumping_efficiency_default  # Fixed value at 45% for all pumps
        self.pumping_efficiency_tier_2 = pumping_efficiency_tier_2  # Tier 2 Value
        self.erh_electricity = erh_electricity  # Fixed value, Energy DB value AJ4 if Electricity else None
        self.fuel_net_calorific_values = fuel_net_calorific_values  # Energy DB Table G6-M13, match row to Fuel Type and Column 'Net Calorific Value'
        self.fuel_density = fuel_density  # Energy DB Table G6-M13, match row to Fuel Type and Column 'Density'
        self.depth = depth  # Front-End Input

        self.transportation_loss = transportation_loss  # Float, Fixed at 0.1 (10%) on Excel (could become front-end Input)
        self.gwir = gwir  # Front-End input Gross Water Irrigation Requirement


    def calculate_emissions(
        self,
    ):
        def ef_calculation(ef_default, ef_tier_2, total_dynamic_head_tier_2, average_pressure_default, average_pressure_tier_2, pumping_efficiency_default, pumping_efficiency_tier_2, erh_electricity, fuel_net_calorific_values, fuel_density, depth, gwir):
            try:
                pumping_efficiency = pumping_efficiency_default if not pumping_efficiency_tier_2 else pumping_efficiency_tier_2
                average_pressure = average_pressure_default if not average_pressure_tier_2 else average_pressure_tier_2
                total_dynamic_head_default = average_pressure * 10.19
                total_dynamic_head = total_dynamic_head_default if not total_dynamic_head_tier_2 else total_dynamic_head_tier_2
                ef = ef_default if not ef_tier_2 else ef_tier_2
                gwir = gwir * 10
                erh = erh_electricity if erh_electricity else 9.81 / (fuel_net_calorific_values * fuel_density) / math.pow(10, 3)

                total_energy = gwir * erh
                A_efficiency = total_energy / pumping_efficiency

                b_depth_tph = A_efficiency * (depth + total_dynamic_head)
                C_tco2 = b_depth_tph * ef  ### this is the equivalent of the ef_ipcc in general calculations for input

                return C_tco2

            except:
                traceback.print_exc()
                return None

        try:
            ef = ef_calculation(self.ef_default, self.ef_tier_2, self.total_dynamic_head_tier_2, self.average_pressure_default, self.average_pressure_tier_2, self.pumping_efficiency_default, self.pumping_efficiency_tier_2, self.erh_electricity, self.fuel_net_calorific_values, self.fuel_density, self.depth, self.gwir)

            # THESE ARE SAVED IN ORDER TO MULTIPLY BY ELECTRICITY MULTIPLIER

            # TODO: CHECK IF THIS CAN BE CHANGED TO HAVING MULTIPLE INPUTS FOR START AND END LIKE FISHERIES ECC (so backend changes from start to end and not start-0 0-end)
            yearly_emissions, _ = input_single_calculation(self.units_start, self.units_end, ef, None, 1, 1, self.implementation_time, self.capitalization_time, self.rate_type)
            yearly_emissions = [x * (1 + self.transportation_loss) for x in yearly_emissions] if self.transportation_loss else yearly_emissions

            irrigation_operational_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in yearly_emissions], ActivityTypes.IRRIGATION_OPERATIONAL, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(irrigation_operational_emission_set)

        except:
            traceback.print_exc()


class Roads(BaseModule):
    def __init__(self, ef_ipcc: float, ef_tier_2, area, time_impl, time_cap, rate_type, delay=0):

        super().__init__(time_impl, time_cap, rate_type, delay)

        self.ef_ipcc = ef_ipcc  # Match Building and Roads type to Energy DB Sheet Table A26-B45
        self.ef_tier_2 = ef_tier_2  # Tier 2 Value
        self.units_end = area  # User Input
        
    def calculate_emissions(self):
        try:
            # NOTE: check this, looks weird
            ef = self.ef_ipcc if self.ef_ipcc else self.ef_tier_2

            self.total_emissions = self.units_end * ef / 1000  # to convert the ef from kg to g
            self.emissions_total_yearly = yearly_constant_emissions_breakdown(self.total_emissions, self.implementation_time, self.capitalization_time)

            roads_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.emissions_total_yearly], ActivityTypes.ROADS, delay=self.delay) 
            self.result.yearly_emissions_by_sector_by_gas.append(roads_emission_set)

        except:
            traceback.print_exc()


class ElectryicityConsumption(BaseModule):
    def __init__(self, emissions_factor, specific_factor_start, specific_factor_end, mwh_start, mwh_end, percent_loss_transportation_start, percent_loss_transportation_end, rate_type, time_impl, time_cap, delay=0):

        super().__init__(time_impl, time_cap, rate_type, delay)

        self.emissions_factor = emissions_factor  # Match Country and Source of Emission Factor to Elec Table (columns 6 or 7)
        self.specific_factor_start = specific_factor_start  # Tier 2 Value
        self.specific_factor_end = specific_factor_end  # Tier 2 Value
        self.mwh_start = mwh_start  # User Input
        self.mwh_end = mwh_end  # User Input
        self.percent_loss_transportation_start = percent_loss_transportation_start  # User Input expects number between 0 and 1
        self.percent_loss_transportation_end = percent_loss_transportation_end

    def calculate_emissions(
        self,
    ):
        try:
            factor_start = self.specific_factor_start if self.specific_factor_start else self.emissions_factor
            factor_end = self.specific_factor_end if self.specific_factor_end else self.emissions_factor

            annual_start = (factor_start * self.mwh_start) * (1 + self.percent_loss_transportation_start)
            annual_end = (factor_end * self.mwh_end) * (1 + self.percent_loss_transportation_end)

            emissions_total_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

            electricity_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_total_yearly], ActivityTypes.ELECTRICITY, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(electricity_emission_set)


        except:
            traceback.print_exc()

class FuelConsumption(BaseModule):
    def __init__(self, emissions_factor, specific_factor, mwh_start, mwh_end, rate_type, time_impl, time_cap, delay=0):

        super().__init__(time_impl, time_cap, rate_type, delay)

        self.emissions_factor = emissions_factor  # Match Fuel Type to table IPCC A1727-B1741
        self.specific_factor = specific_factor  # Tier 2 Value
        self.mwh_start = mwh_start  # User Input
        self.mwh_end = mwh_end  # User Input

    def calculate_emissions(
        self,
    ):
        try:
            factor = self.specific_factor if self.specific_factor else self.emissions_factor

            annual_start = factor * self.mwh_start
            annual_end = factor * self.mwh_end

            emissions_total_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

            fuel_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_total_yearly], ActivityTypes.FUEL, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(fuel_emission_set)

        except:
            traceback.print_exc()

class SolidConsumption(BaseModule):
    def __init__(self, joules_factor, co2_factor, ch4_factor, n2o_factor, account_for_co2_boolean, methane_constant, nitrous_constant, specific_factor, mwh_start, mwh_end, rate_type, time_impl, time_cap, delay=0):

        super().__init__(time_impl, time_cap, rate_type, delay)

        self.joules_factor = joules_factor  # Match Fuel Type to table IPCC A1750 COLUMN C
        self.co2_factor = co2_factor  # Match Fuel Type to table IPCC A1750 COLUMN D
        self.ch4_factor = ch4_factor  # Match Fuel Type to table IPCC A1750 COLUMN E
        self.n2o_factor = n2o_factor  # Match Fuel Type to table IPCC A1750 COLUMN F
        self.account_for_co2_boolean = account_for_co2_boolean  # Tier 2 Value
        self.methane_constant = methane_constant  # Tier 2 Value
        self.nitrous_constant = nitrous_constant  # Tier 2 Value
        self.specific_factor = specific_factor  # Tier 2 Value
        self.mwh_start = mwh_start  # User Input
        self.mwh_end = mwh_end  # User Input
        
        

    def calculate_emissions(
        self,
    ):
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

            emissions_total_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

            solid_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_total_yearly], ActivityTypes.SOLID_CONSUMPTION, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(solid_emission_set)

        except:
            traceback.print_exc()

class NewIrrigation(BaseModule):
    def __init__(self, ef_ref, ef_tier_2, units_start, units_end, time_impl, time_cap, rate_type, delay=0):

        super().__init__(time_impl, time_cap, rate_type, delay)
        
        # TODO: ADD HECTARS START AND REMOVE FROM FINAL
        self.units_start = units_start
        self.units_end = units_end
    
        self.ef_ref = ef_ref  # Match Irrigation Type to Energy DB A7:B16 column 2
        self.ef_tier_2 = ef_tier_2

    def calculate_emissions(
        self,
    ):
        try:
            ef = self.ef_ref if not self.ef_tier_2 else self.ef_tier_2

            self.total_emissions = ef * (self.units_end - self.units_start) / 1000
            emissions_total_yearly = yearly_constant_emissions_breakdown(self.total_emissions, self.implementation_time, self.capitalization_time)

            new_irrigation_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_total_yearly], ActivityTypes.NEW_IRRIGATION, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(new_irrigation_emission_set)

        except:
            traceback.print_exc()
