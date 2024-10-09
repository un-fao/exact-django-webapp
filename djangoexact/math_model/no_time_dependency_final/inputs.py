import math
import traceback

from .generalized_modules import BaseModule

from .general_functions import input_single_calculation, yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, breakdown_according_to_values
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

from dataclasses import dataclass
from typing import Optional


@dataclass
class Inputs(BaseModule):
    unit_start: float
    unit_end: float
    ipcc_factor_co2: float
    tier_2_factor_co2: Optional[float]
    unit_factor_co2: float
    emissions_factor_co2: float
    ipcc_factor_n2o: float
    tier_2_factor_n2o: Optional[float]
    unit_factor_n2o: float
    emissions_factor_n2o: float
    ipcc_factor_eq: float
    tier_2_factor_eq: Optional[float]
    unit_factor_eq: float
    emissions_factor_eq: float

    def calculate_emissions(self):
        try:
            if self.unit_factor_co2 is None or self.emissions_factor_co2 is None or self.ipcc_factor_co2 is None:
                yearly_co2_eq_emissions = total_co2_eq_emissions = []
            else:
                yearly_co2_eq_emissions, total_co2_eq_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_co2, self.tier_2_factor_co2, self.unit_factor_co2, self.emissions_factor_co2, self.implementation_time, self.capitalization_time, self.rate_type)

            if self.unit_factor_n2o is None or self.emissions_factor_n2o is None or self.ipcc_factor_n2o is None:
                yearly_n2o_emissions = total_n2o_emissions = []
            else:
                yearly_n2o_emissions, total_n2o_emissions = input_single_calculation(self.unit_start, self.unit_end, self.ipcc_factor_n2o, self.tier_2_factor_n2o, self.unit_factor_n2o, self.emissions_factor_n2o, self.implementation_time, self.capitalization_time, self.rate_type)

            if self.unit_factor_eq is None or self.emissions_factor_eq is None or self.ipcc_factor_eq is None:
                yearly_co2_emissions = total_co2_emissions = []
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
            raise e


@dataclass
class OperationPhaseIrrigation(BaseModule):
    ef_co2_default: float
    ef_co2_tier_2: Optional[float]
    ef_n2o_default: float
    ef_n2o_tier_2: Optional[float]
    ef_ch4_default: float
    ef_ch4_tier_2: Optional[float]
    total_dynamic_head_tier_2: Optional[float]
    average_pressure_default: float
    average_pressure_tier_2: Optional[float]
    pumping_efficiency_default: float
    pumping_efficiency_tier_2: Optional[float]
    erh_electricity: float
    fuel_density: float
    fuel_net_calorific_values: float
    depth: float
    units_start: float
    units_end: float
    transportation_loss: float
    gwir: float

    def calculate_emissions(
        self,
    ):
        def ef_calculation(ef_co2_default, ef_co2_tier_2, ef_n2o_default, ef_n2o_tier_2, ef_ch4_default, ef_ch4_tier_2, total_dynamic_head_tier_2, average_pressure_default, average_pressure_tier_2, pumping_efficiency_default, pumping_efficiency_tier_2, erh_electricity, fuel_net_calorific_values, fuel_density, depth, gwir):
            try:
                pumping_efficiency = self.pumping_efficiency_tier_2 or self.pumping_efficiency_default
                average_pressure = self.average_pressure_tier_2 or self.average_pressure_default
                total_dynamic_head_default = average_pressure * 10.19
                total_dynamic_head = total_dynamic_head_tier_2 or total_dynamic_head_default
                ef_co2 = ef_co2_tier_2 or ef_co2_default
                ef_n2o = ef_n2o_tier_2 or ef_n2o_default
                ef_ch4 = ef_ch4_tier_2 or ef_ch4_default
                gwir = gwir * 10
                erh = erh_electricity if erh_electricity else 9.81 / (fuel_net_calorific_values * fuel_density) / math.pow(10, 3)

                total_energy = gwir * erh
                A_efficiency = total_energy / pumping_efficiency

                b_depth_tph = A_efficiency * (depth + total_dynamic_head)
                C_tco2_co2 = b_depth_tph * ef_co2  ### this is the equivalent of the ef_ipcc in general calculations for input
                C_tco2_n2o = b_depth_tph * ef_n2o
                C_tco2_ch4 = b_depth_tph * ef_ch4

                return C_tco2_co2, C_tco2_n2o, C_tco2_ch4

            except Exception as e:
                traceback.print_exc()
                raise e

        try:
            ef_co2, ef_n2o, ef_ch4 = ef_calculation(self.ef_co2_default, self.ef_co2_tier_2, self.ef_n2o_default, self.ef_n2o_tier_2, self.ef_ch4_default, self.ef_ch4_tier_2, self.total_dynamic_head_tier_2, self.average_pressure_default, self.average_pressure_tier_2, self.pumping_efficiency_default, self.pumping_efficiency_tier_2, self.erh_electricity, self.fuel_net_calorific_values, self.fuel_density, self.depth, self.gwir)

            # THESE ARE SAVED IN ORDER TO MULTIPLY BY ELECTRICITY MULTIPLIER

            # TODO: CHECK IF THIS CAN BE CHANGED TO HAVING MULTIPLE INPUTS FOR START AND END LIKE FISHERIES ECC (so backend changes from start to end and not start-0 0-end)
            yearly_emissions_co2, _ = input_single_calculation(self.units_start, self.units_end, ef_co2, None, 1, 1, self.implementation_time, self.capitalization_time, self.rate_type)
            yearly_emissions_co2 = [x * (1 + self.transportation_loss) for x in yearly_emissions_co2] if self.transportation_loss else yearly_emissions_co2

            yearly_emissions_n2o, _ = input_single_calculation(self.units_start, self.units_end, ef_n2o, None, 1, 1, self.implementation_time, self.capitalization_time, self.rate_type)
            yearly_emissions_n2o = [x * (1 + self.transportation_loss) for x in yearly_emissions_n2o] if self.transportation_loss else yearly_emissions_n2o

            yearly_emissions_ch4, _ = input_single_calculation(self.units_start, self.units_end, ef_ch4, None, 1, 1, self.implementation_time, self.capitalization_time, self.rate_type)
            yearly_emissions_ch4 = [x * (1 + self.transportation_loss) for x in yearly_emissions_ch4] if self.transportation_loss else yearly_emissions_ch4

            irrigation_operational_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in yearly_emissions_co2], ActivityTypes.IRRIGATION_OPERATIONAL, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(irrigation_operational_emission_set)

            irrigation_operational_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in yearly_emissions_n2o], ActivityTypes.IRRIGATION_OPERATIONAL, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(irrigation_operational_emission_set)

            irrigation_operational_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in yearly_emissions_ch4], ActivityTypes.IRRIGATION_OPERATIONAL, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(irrigation_operational_emission_set)

        except Exception as e:
            traceback.print_exc()
            raise e


@dataclass
class Roads(BaseModule):

    ef_ipcc: float
    ef_tier_2: Optional[float]
    units_end: float  # This will be used to set `units_end`

    def calculate_emissions(self):
        try:
            # NOTE: check this, looks weird
            ef = self.ef_tier_2 or self.ef_ipcc

            self.total_emissions = self.units_end * ef / 1000  # to convert the ef from kg to g
            yearly_units = yearly_time_dependent_parameter_breakdown(0, self.units_end, self.implementation_time, self.capitalization_time, self.rate_type)
            self.emissions_total_yearly = breakdown_according_to_values(self.total_emissions, yearly_units)

            roads_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.emissions_total_yearly], ActivityTypes.ROADS, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(roads_emission_set)

        except Exception as e:
            traceback.print_exc()
            raise e


@dataclass
class ElectricityConsumption(BaseModule):

    emissions_factor: float
    specific_factor_start: Optional[float]
    specific_factor_end: Optional[float]
    mwh_start: float
    mwh_end: float
    percent_loss_transportation_start: float
    percent_loss_transportation_end: float

    def calculate_emissions(
        self,
    ):
        try:
            factor_start = self.specific_factor_start or self.emissions_factor
            factor_end = self.specific_factor_end or self.emissions_factor

            annual_start = (factor_start * self.mwh_start) * (1 + self.percent_loss_transportation_start)
            annual_end = (factor_end * self.mwh_end) * (1 + self.percent_loss_transportation_end)

            emissions_total_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

            electricity_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_total_yearly], ActivityTypes.ELECTRICITY, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(electricity_emission_set)

        except Exception as e:
            traceback.print_exc()
            raise e


@dataclass
class SolidAndLiquidFuelsConsumption(BaseModule):
    # Now we have co2, ch4 and n2o factors
    emissions_factor_co2: float
    specific_factor_co2: Optional[float]
    emissions_factor_ch4: float
    specific_factor_ch4: Optional[float]
    emissions_factor_n2o: float
    specific_factor_n2o: Optional[float]
    mwh_start: float
    mwh_end: float
    nitrous_constant: float
    methane_constant: float

    def calculate_emissions(
        self,
    ):
        try:
            factor_co2 = self.specific_factor_co2 or self.emissions_factor_co2
            factor_ch4 = self.specific_factor_ch4 or self.emissions_factor_ch4
            factor_n2o = self.specific_factor_n2o or self.emissions_factor_n2o

            annual_start_co2 = factor_co2 * self.mwh_start
            annual_end_co2 = factor_co2 * self.mwh_end

            annual_start_ch4 = factor_ch4 * self.mwh_start * self.methane_constant
            annual_end_ch4 = factor_ch4 * self.mwh_end * self.methane_constant

            annual_start_n2o = factor_n2o * self.mwh_start * self.nitrous_constant
            annual_end_n2o = factor_n2o * self.mwh_end * self.nitrous_constant

            emissions_co2_yearly = yearly_time_dependent_parameter_breakdown(annual_start_co2, annual_end_co2, self.implementation_time, self.capitalization_time, self.rate_type)
            emissions_ch4_yearly = yearly_time_dependent_parameter_breakdown(annual_start_ch4, annual_end_ch4, self.implementation_time, self.capitalization_time, self.rate_type)
            emissions_n2o_yearly = yearly_time_dependent_parameter_breakdown(annual_start_n2o, annual_end_n2o, self.implementation_time, self.capitalization_time, self.rate_type)

            fuel_emission_set_co2 = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_co2_yearly], ActivityTypes.FUEL, delay=self.delay)
            fuel_emission_set_ch4 = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in emissions_ch4_yearly], ActivityTypes.FUEL, delay=self.delay)
            fuel_emission_set_n2o = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in emissions_n2o_yearly], ActivityTypes.FUEL, delay=self.delay)

            self.result.yearly_emissions_by_sector_by_gas.append(fuel_emission_set_co2)
            self.result.yearly_emissions_by_sector_by_gas.append(fuel_emission_set_ch4)
            self.result.yearly_emissions_by_sector_by_gas.append(fuel_emission_set_n2o)

        except Exception as e:
            traceback.print_exc()
            raise e


@dataclass
class NewIrrigation(BaseModule):
    ef_ref: float
    ef_tier_2: Optional[float]
    units_start: float
    units_end: float

    def calculate_emissions(
        self,
    ):
        try:
            ef = self.ef_tier_2 or self.ef_ref

            self.total_emissions = ef * (self.units_end - self.units_start) / 1000  # to convert the ef from kg to g
            yearly_units = yearly_time_dependent_parameter_breakdown(self.units_start, self.units_end, self.implementation_time, self.capitalization_time, self.rate_type)
            emissions_total_yearly = breakdown_according_to_values(self.total_emissions, yearly_units)

            new_irrigation_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_total_yearly], ActivityTypes.NEW_IRRIGATION, delay=self.delay)
            self.result.yearly_emissions_by_sector_by_gas.append(new_irrigation_emission_set)

        except Exception as e:
            traceback.print_exc()
            raise e
