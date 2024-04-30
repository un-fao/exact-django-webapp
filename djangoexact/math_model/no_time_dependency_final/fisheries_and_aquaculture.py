import re
import traceback

from .general_functions import BaseModule, yearly_time_dependent_parameter_breakdown
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)


class Fishery(BaseModule):
    def __init__(self, time_impl, time_cap, rate_type, catch_start, catch_end, ef_diesel_default, ef_diesel_start_tier_2, ef_diesel_tier_2_end, fui_default_start, fui_default_end, fui_start_tier_2, fui_end_tier_2, gwp_refrigerant_default, gwp_refrigerant_start_tier_2, gwp_refrigerant_end_tier_2, quantity_lost_refrigerant_default, quantity_lost_refrigerant_start_tier_2, quantity_lost_refrigerant_end_tier_2, percentage_refrigerant_start, percentage_refrigerant_end, tonnes_ice_default, tonnes_ice_start_tier_2, tonnes_ice_end_tier_2, kwh_ice_per_tonne_default, kwh_ice_per_tonne_start_tier_2, kwh_ice_per_tonne_end_tier_2, operating_margin, percentage_ice_start, percentage_ice_end, delay=0) -> None:
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
        self.delay = delay

        # DEFINITION OF THE TIER 2 DEFAULTS
        self.ef_diesel_start_tier_2_default = self.ef_diesel_default
        self.ef_diesel_end_tier_2_default = self.ef_diesel_default
        self.fui_start_tier_2_default = self.fui_default_start
        self.fui_end_tier_2_default = self.fui_default_end
        self.gwp_refrigerant_start_tier_2_default = self.gwp_refrigerant_default
        self.gwp_refrigerant_end_tier_2_default = self.gwp_refrigerant_default
        self.quantity_lost_refrigerant_start_tier_2_default = self.quantity_lost_refrigerant_default
        self.quantity_lost_refrigerant_end_tier_2_default = self.quantity_lost_refrigerant_default
        self.tonnes_ice_start_tier_2_default = self.tonnes_ice_default
        self.tonnes_ice_end_tier_2_default = self.tonnes_ice_default
        self.kwh_ice_per_tonne_start_tier_2_default = self.kwh_ice_per_tonne_default
        self.kwh_ice_per_tonne_end_tier_2_default = self.kwh_ice_per_tonne_default

        # RESULTS
        self.emissions_catch_yearly = []
        self.emissions_refrigerant_yearly = []
        self.emissions_ice_yearly = []

        self.emissions_catch_total = 0
        self.emissions_refrigerant_total = 0
        self.emissions_ice_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.implementation_time, self.capitalization_time)

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

                self.emissions_catch_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)
                self.emissions_catch_total = sum(self.emissions_catch_yearly)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(x, GasTypes.CO2) for x in self.emissions_catch_yearly], activity=ActivityTypes.CATCH, delay=self.delay))

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

                self.emissions_refrigerant_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)
                self.emissions_refrigerant_total = sum(self.emissions_refrigerant_yearly)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.OTHER, emissions=[Emission(x, GasTypes.OTHER) for x in self.emissions_refrigerant_yearly], activity=ActivityTypes.REFRIGERANT, delay=self.delay))

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

                self.emissions_ice_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.implementation_time, self.capitalization_time, self.rate_type)
                self.emissions_ice_total = sum(self.emissions_ice_yearly)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.OTHER, emissions=[Emission(x, GasTypes.OTHER) for x in self.emissions_ice_yearly], activity=ActivityTypes.ICE, delay=self.delay))

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
            return

        except Exception as e:
            traceback.print_exc()
            return {}


class CoastalAquaculture:
    def __init__(self, production_start, production_w, nitrous_ef_default, nitrous_ef_start_tier_2, nitrous_ef_end_tier_2, nitrous_constant, time_impl, time_cap, rate_type):
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.production_start = production_start
        self.production_end = production_w
        self.nitrous_ef_default = nitrous_ef_default
        self.nitrous_ef_start_tier_2 = nitrous_ef_start_tier_2
        self.nitrous_ef_end_tier_2 = nitrous_ef_end_tier_2
        self.nitrous_constant = nitrous_constant
        self.rate_type = rate_type

        # DEFINITION OF TIER 2 DEFAULTS
        self.nitrous_ef_tier_2_default = None
        self.ef_feed_tier_2_default = None

        self.emissions_nitrous_yearly = []
        self.emissions_total_yearly = []

        self.emissions_nitrous_total = 0
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)

    def calculate_emissions(self):
        def calculate_nitrous_emissions():
            try:
                nitrous_ef_start = self.nitrous_ef_default if not self.nitrous_ef_start_tier_2 else self.nitrous_ef_start_tier_2
                nitrous_ef_end = self.nitrous_ef_default if not self.nitrous_ef_end_tier_2 else self.nitrous_ef_end_tier_2

                annual_start = nitrous_ef_start * self.production_start * self.nitrous_constant * 44 / 28
                annual_end = nitrous_ef_end * self.production_end * self.nitrous_constant * 44 / 28

                self.emissions_nitrous_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.time_impl, self.time_cap, self.rate_type)
                self.emissions_nitrous_total = sum(self.emissions_nitrous_yearly)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(x, GasTypes.N2O) for x in self.emissions_nitrous_yearly], activity=ActivityTypes.N20_FIELD, delay=0))

            except Exception as e:
                traceback.print_exc()

        calculate_nitrous_emissions()

        try:
            self.emissions_total_yearly = [sum(x) for x in zip(self.emissions_nitrous_yearly)]
            self.total_emissions = sum(self.emissions_total_yearly)
        except Exception as e:
            traceback.print_exc()


# w = [22.0, 45.0, 0.00169, None, None, 265.0, 5, 15, "D"]
# a = CoastalAquaculture(*w)

# a.calculate_emissions()
