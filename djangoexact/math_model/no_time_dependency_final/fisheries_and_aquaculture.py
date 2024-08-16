import re
import traceback

from .general_functions import yearly_time_dependent_parameter_breakdown
from .generalized_modules import BaseModule
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)


class Fishery(BaseModule):
    def __init__(self, time_impl, time_cap, rate_type, catch_start, catch_end, ef_diesel_default, ef_diesel_start_tier_2, ef_diesel_tier_2_end, fui_default_start, fui_default_end, fui_start_tier_2, fui_end_tier_2, gwp_refrigerant_default, gwp_refrigerant_start_tier_2, gwp_refrigerant_end_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_start_tier_2, quantity_lost_refrigerant_end_tier_2, percentage_refrigerant_start, percentage_refrigerant_end, tonnes_ice_default, tonnes_ice_start_tier_2, tonnes_ice_end_tier_2, kwh_ice_per_tonne_default, kwh_ice_per_tonne_start_tier_2, kwh_ice_per_tonne_end_tier_2, operating_margin, percentage_ice_start, percentage_ice_end, delay=0) -> None:
        
        super().__init__(time_impl, time_cap, rate_type, delay)

        # DEFINITIONS OF PARAMETERS
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

                emissions_catch_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(x, GasTypes.CO2) for x in emissions_catch_yearly], activity=ActivityTypes.CATCH, delay=self.delay))

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

                emissions_refrigerant_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.OTHER, emissions=[Emission(x, GasTypes.OTHER) for x in emissions_refrigerant_yearly], activity=ActivityTypes.REFRIGERANT, delay=self.delay))

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

                emissions_ice_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.OTHER, emissions=[Emission(x, GasTypes.OTHER) for x in emissions_ice_yearly], activity=ActivityTypes.ICE, delay=self.delay))

            except Exception as e:
                traceback.print_exc()

        calculate_catch_emissions()
        calculate_refrigerant_emissions()
        calculate_ice_emissions()

class CoastalAquaculture(BaseModule):
    def __init__(self, production_start, production_w, nitrous_ef_default, nitrous_ef_start_tier_2, nitrous_ef_end_tier_2, nitrous_constant, 
                 electricity_used_default, electricity_used_start_tier_2, electricity_used_end_tier_2, ef_electricity_default, ef_electricity_start_tier_2, ef_electricity_end_tier_2,
                 time_impl, time_cap, rate_type, delay=0) -> None:
        
        super().__init__(time_impl, time_cap, rate_type, delay)

        self.production_start = production_start
        self.production_end = production_w
        self.nitrous_ef_default = nitrous_ef_default
        self.nitrous_ef_start_tier_2 = nitrous_ef_start_tier_2
        self.nitrous_ef_end_tier_2 = nitrous_ef_end_tier_2
        self.nitrous_constant = nitrous_constant
        self.electricity_used_default = electricity_used_default
        self.electricity_used_start_tier_2 = electricity_used_start_tier_2
        self.electricity_used_end_tier_2 = electricity_used_end_tier_2
        self.ef_electricity_default = ef_electricity_default
        self.ef_electricity_start_tier_2 = ef_electricity_start_tier_2
        self.ef_electricity_end_tier_2 = ef_electricity_end_tier_2


    def calculate_emissions(self):
        def calculate_nitrous_emissions():
            try:
                nitrous_ef_start = self.nitrous_ef_default if not self.nitrous_ef_start_tier_2 else self.nitrous_ef_start_tier_2
                nitrous_ef_end = self.nitrous_ef_default if not self.nitrous_ef_end_tier_2 else self.nitrous_ef_end_tier_2

                annual_start = nitrous_ef_start * self.production_start * self.nitrous_constant * 44 / 28
                annual_end = nitrous_ef_end * self.production_end * self.nitrous_constant * 44 / 28

                emissions_nitrous_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(x, GasTypes.N2O) for x in emissions_nitrous_yearly], activity=ActivityTypes.N20_FIELD, delay=0))

            except Exception as e:
                traceback.print_exc()

        def calculate_co2_emissions():
            try:
                electricity_used_start = self.electricity_used_default if not self.electricity_used_start_tier_2 else self.electricity_used_start_tier_2
                electricity_used_end = self.electricity_used_default if not self.electricity_used_end_tier_2 else self.electricity_used_end_tier_2
                ef_electricity_start = self.ef_electricity_default if not self.ef_electricity_start_tier_2 else self.ef_electricity_start_tier_2
                ef_electricity_end = self.ef_electricity_default if not self.ef_electricity_end_tier_2 else self.ef_electricity_end_tier_2

                annual_start = electricity_used_start * self.production_start * ef_electricity_start
                annual_end = electricity_used_end * self.production_end * ef_electricity_end

                emissions_co2_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(x, GasTypes.CO2) for x in emissions_co2_yearly], activity=ActivityTypes.ELECTRICITY, delay=0))

            except Exception as e:
                traceback.print_exc()

        calculate_nitrous_emissions()
        calculate_co2_emissions()
