import re
import traceback

from .general_functions import compute_yearly_or_half_year_cumulative
from .generalized_modules import BaseModule
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
class Fishery(BaseModule):
    catch_start: float
    catch_end: float
    ef_diesel_default_co2: float
    ef_diesel_co2_start_tier_2: Optional[float]
    ef_diesel_co2_end_tier_2: Optional[float]
    ef_diesel_default_n2o: float
    ef_diesel_n2o_start_tier_2: Optional[float]
    ef_diesel_n2o_end_tier_2: Optional[float]
    ef_diesel_default_ch4: float
    ef_diesel_ch4_start_tier_2: Optional[float]
    ef_diesel_ch4_end_tier_2: Optional[float]
    fui_default_start: float
    fui_default_end: float
    fui_start_tier_2: Optional[float]
    fui_end_tier_2: Optional[float]
    gwp_refrigerant_default: float
    gwp_refrigerant_start_tier_2: Optional[float]
    gwp_refrigerant_end_tier_2: Optional[float]
    quantity_lost_refrigerant_default: float
    quantity_lost_refrigerant_start_tier_2: Optional[float]
    quantity_lost_refrigerant_end_tier_2: Optional[float]
    percentage_refrigerant_start: float
    percentage_refrigerant_end: float
    tonnes_ice_default: float
    tonnes_ice_start_tier_2: Optional[float]
    tonnes_ice_end_tier_2: Optional[float]
    kwh_ice_per_tonne_default: float
    kwh_ice_per_tonne_start_tier_2: Optional[float]
    kwh_ice_per_tonne_end_tier_2: Optional[float]
    operating_margin: float
    percentage_ice_start: float
    percentage_ice_end: float

    def __post_init__(self):
        super().__post_init__()

        self.tonnes_catch_yearly_breakdown = compute_yearly_or_half_year_cumulative(self.catch_start, self.catch_end, self.implementation_time, self.capitalization_time, self.rate_type)

    def calculate_emissions(self):
        def calculate_catch_emissions():
            try:
                ef_diesel_co2_start = self.ef_diesel_co2_start_tier_2 or self.ef_diesel_default_co2
                ef_diesel_co2_end = self.ef_diesel_co2_end_tier_2 or self.ef_diesel_default_co2

                ef_diesel_n2o_start = self.ef_diesel_n2o_start_tier_2 or self.ef_diesel_default_n2o
                ef_diesel_n2o_end = self.ef_diesel_n2o_end_tier_2 or self.ef_diesel_default_n2o

                ef_diesel_ch4_start = self.ef_diesel_ch4_start_tier_2 or self.ef_diesel_default_ch4
                ef_diesel_ch4_end = self.ef_diesel_ch4_end_tier_2 or self.ef_diesel_default_ch4

                fui_start = self.fui_start_tier_2 or self.fui_default_start
                fui_end = self.fui_end_tier_2 or self.fui_default_end

                # co2 calculation

                ef_co2_start = fui_start * ef_diesel_co2_start / 1000
                ef_co2_end = fui_end * ef_diesel_co2_end / 1000

                annual_co2_start = self.catch_start * ef_co2_start
                annual_co2_end = self.catch_end * ef_co2_end

                emissions_co2_catch_yearly = compute_yearly_or_half_year_cumulative(annual_co2_start, annual_co2_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(x, GasTypes.CO2) for x in emissions_co2_catch_yearly], activity=ActivityTypes.CATCH, delay=self.delay))

                # n2o calculation

                ef_n2o_start = fui_start * ef_diesel_n2o_start / 1000
                ef_n2o_end = fui_end * ef_diesel_n2o_end / 1000

                annual_n2o_start = self.catch_start * ef_n2o_start
                annual_n2o_end = self.catch_end * ef_n2o_end

                emissions_n2o_catch_yearly = compute_yearly_or_half_year_cumulative(annual_n2o_start, annual_n2o_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(x, GasTypes.N2O) for x in emissions_n2o_catch_yearly], activity=ActivityTypes.CATCH, delay=self.delay))

                # ch4 calculation

                ef_ch4_start = fui_start * ef_diesel_ch4_start / 1000
                ef_ch4_end = fui_end * ef_diesel_ch4_end / 1000

                annual_ch4_start = self.catch_start * ef_ch4_start
                annual_ch4_end = self.catch_end * ef_ch4_end

                emissions_ch4_catch_yearly = compute_yearly_or_half_year_cumulative(annual_ch4_start, annual_ch4_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(x, GasTypes.CH4) for x in emissions_ch4_catch_yearly], activity=ActivityTypes.CATCH, delay=self.delay))

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_refrigerant_emissions():
            try:
                gwp_refrigerant_start = self.gwp_refrigerant_start_tier_2 or self.gwp_refrigerant_default
                gwp_refrigerant_end = self.gwp_refrigerant_end_tier_2 or self.gwp_refrigerant_default

                quantity_lost_refrigerant_start = self.quantity_lost_refrigerant_start_tier_2 or self.quantity_lost_refrigerant_default
                quantity_lost_refrigerant_end = self.quantity_lost_refrigerant_end_tier_2 or self.quantity_lost_refrigerant_default

                catch_with_refrigerant_start = self.catch_start * self.percentage_refrigerant_start
                catch_with_refrigerant_end = self.catch_end * self.percentage_refrigerant_end

                annual_start = gwp_refrigerant_start * quantity_lost_refrigerant_start * catch_with_refrigerant_start / 1000
                annual_end = gwp_refrigerant_end * quantity_lost_refrigerant_end * catch_with_refrigerant_end / 1000

                emissions_refrigerant_yearly = compute_yearly_or_half_year_cumulative(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.OTHER, emissions=[Emission(x, GasTypes.OTHER) for x in emissions_refrigerant_yearly], activity=ActivityTypes.REFRIGERANT, delay=self.delay))
            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_ice_emissions():
            try:
                tonnes_ice_start = self.tonnes_ice_start_tier_2 or self.tonnes_ice_default
                tonnes_ice_end = self.tonnes_ice_end_tier_2 or self.tonnes_ice_default

                kwh_ice_per_tonne_start = self.kwh_ice_per_tonne_start_tier_2 or self.kwh_ice_per_tonne_default
                kwh_ice_per_tonne_end = self.kwh_ice_per_tonne_end_tier_2 or self.kwh_ice_per_tonne_default

                ice_ef_start = tonnes_ice_start * kwh_ice_per_tonne_start * self.operating_margin / 1000
                ice_ef_end = tonnes_ice_end * kwh_ice_per_tonne_end * self.operating_margin / 1000

                catch_with_refrigerant_start = self.catch_start * self.percentage_ice_start
                catch_with_refrigerant_end = self.catch_end * self.percentage_ice_end

                annual_start = ice_ef_start * catch_with_refrigerant_start
                annual_end = ice_ef_end * catch_with_refrigerant_end

                emissions_ice_yearly = compute_yearly_or_half_year_cumulative(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.OTHER, emissions=[Emission(x, GasTypes.OTHER) for x in emissions_ice_yearly], activity=ActivityTypes.ICE, delay=self.delay))
            except Exception as e:
                traceback.print_exc()
                raise e

        calculate_catch_emissions()
        calculate_refrigerant_emissions()
        calculate_ice_emissions()


@dataclass
class CoastalAquaculture(BaseModule):
    production_start: float
    production_end: float
    nitrous_ef_default: float
    nitrous_ef_start_tier_2: float
    nitrous_ef_end_tier_2: float
    nitrous_constant: float
    electricity_used_default: float
    electricity_used_start_tier_2: float
    electricity_used_end_tier_2: float
    ef_electricity_default: float
    ef_electricity_start_tier_2: float
    ef_electricity_end_tier_2: float

    def calculate_emissions(self):
        def calculate_nitrous_emissions():
            try:
                nitrous_ef_start = self.nitrous_ef_start_tier_2 or self.nitrous_ef_default
                nitrous_ef_end = self.nitrous_ef_end_tier_2 or self.nitrous_ef_default

                annual_start = nitrous_ef_start * self.production_start * self.nitrous_constant * 44 / 28
                annual_end = nitrous_ef_end * self.production_end * self.nitrous_constant * 44 / 28

                emissions_nitrous_yearly = compute_yearly_or_half_year_cumulative(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(x, GasTypes.N2O) for x in emissions_nitrous_yearly], activity=ActivityTypes.N20_FIELD, delay=self.delay))

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_co2_emissions():
            try:
                electricity_used_start = self.electricity_used_start_tier_2 or self.electricity_used_default
                electricity_used_end = self.electricity_used_end_tier_2 or self.electricity_used_default
                ef_electricity_start = self.ef_electricity_start_tier_2 or self.ef_electricity_default
                ef_electricity_end = self.ef_electricity_end_tier_2 or self.ef_electricity_default

                annual_start = electricity_used_start * self.production_start * ef_electricity_start
                annual_end = electricity_used_end * self.production_end * ef_electricity_end

                emissions_co2_yearly = compute_yearly_or_half_year_cumulative(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(x, GasTypes.CO2) for x in emissions_co2_yearly], activity=ActivityTypes.ELECTRICITY, delay=self.delay))

            except Exception as e:
                traceback.print_exc()
                raise e

        calculate_nitrous_emissions()
        calculate_co2_emissions()


# # TEST FISHERIES
# implementation_time = 5
# capitalization_time = 10
# rate_type = "linear"
# delay = 0

# catch_start = 100
# catch_end = 200
# ef_diesel_default = 10
# ef_diesel_start_tier_2 = None
# ef_diesel_tier_2_end = None
# fui_default_start = 5
# fui_default_end = 10
# fui_start_tier_2 = None
# fui_end_tier_2 = None
# gwp_refrigerant_default = 100
# gwp_refrigerant_start_tier_2 = None
# gwp_refrigerant_end_tier_2 = None
# quantity_lost_refrigerant_default = 10
# quantity_lost_refrigerant_start_tier_2 = None
# quantity_lost_refrigerant_end_tier_2 = None
# percentage_refrigerant_start = 0.1
# percentage_refrigerant_end = 0.2
# tonnes_ice_default = 100
# tonnes_ice_start_tier_2 = None
# tonnes_ice_end_tier_2 = None
# kwh_ice_per_tonne_default = 10
# kwh_ice_per_tonne_start_tier_2 = None
# kwh_ice_per_tonne_end_tier_2 = None
# operating_margin = 0.1
# percentage_ice_start = 0.1
# percentage_ice_end = 0.2

# fishery = Fishery(
#     implementation_time = implementation_time,
#     capitalization_time = capitalization_time,
#     rate_type = rate_type,
#     delay = delay,
#     catch_start = catch_start,
#     catch_end = catch_end,
#     ef_diesel_default = ef_diesel_default,
#     ef_diesel_start_tier_2 = ef_diesel_start_tier_2,
#     ef_diesel_tier_2_end = ef_diesel_tier_2_end,
#     fui_default_start = fui_default_start,
#     fui_default_end = fui_default_end,
#     fui_start_tier_2 = fui_start_tier_2,
#     fui_end_tier_2 = fui_end_tier_2,
#     gwp_refrigerant_default = gwp_refrigerant_default,
#     gwp_refrigerant_start_tier_2 = gwp_refrigerant_start_tier_2,
#     gwp_refrigerant_end_tier_2 = gwp_refrigerant_end_tier_2,
#     quantity_lost_refrigerant_default = quantity_lost_refrigerant_default,
#     quantity_lost_refrigerant_start_tier_2 = quantity_lost_refrigerant_start_tier_2,
#     quantity_lost_refrigerant_end_tier_2 = quantity_lost_refrigerant_end_tier_2,
#     percentage_refrigerant_start = percentage_refrigerant_start,
#     percentage_refrigerant_end = percentage_refrigerant_end,
#     tonnes_ice_default = tonnes_ice_default,
#     tonnes_ice_start_tier_2 = tonnes_ice_start_tier_2,
#     tonnes_ice_end_tier_2 = tonnes_ice_end_tier_2,
#     kwh_ice_per_tonne_default = kwh_ice_per_tonne_default,
#     kwh_ice_per_tonne_start_tier_2 = kwh_ice_per_tonne_start_tier_2,
#     kwh_ice_per_tonne_end_tier_2 = kwh_ice_per_tonne_end_tier_2,
#     operating_margin = operating_margin,
#     percentage_ice_start = percentage_ice_start,
#     percentage_ice_end = percentage_ice_end
# )

# fishery.calculate_emissions()
