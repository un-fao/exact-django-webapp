import math
import re
import traceback
from dataclasses import dataclass

from .general_functions import (
    BaseModule,
    breakdown_according_to_values,
    soil_emissions_2,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
    som_emissions,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)


class GrasslandManagement(BaseModule):
    def __init__(
        self,
        area_start,
        area_end,
        time_impl,
        time_cap,
        rate,
        nitrous_constant,
        methane_constant,
        fire_interval,
        fire_used,
        methane_ef,
        nitrous_ef,
        agb_ref,
        agb_tier_2,
        cf_ref,
        cf_tier_2,
        soc_start_default,
        soc_end_default,
        soc_start_tier_2,
        soc_end_tier_2,
        calculate_soc_som,
        fmg_start_default,
        fmg_end_default,
        fmg_start_tier_2,
        fmg_end_tier_2,
        flu_start_default,
        flu_end_default,
        flu_start_tier_2,
        flu_end_tier_2,
        fi_start_default,
        fi_end_default,
        fi_start_tier_2,
        fi_end_tier_2,
        delay,
        ef_nitrous_som,
    ):
        self.area_start = area_start
        self.area_end = area_end
        self.time_impl = time_impl - delay
        self.time_cap = time_cap
        self.rate = rate
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.fire_interval = fire_interval  # front-end input, years between two fires, default is 5 (on front-end)
        self.fire_used = fire_used  # front-end input, states whether fire has been used
        self.methane_ef = methane_ef  # tabulated value IPCC D75 (value for Savanna and Grassland)
        self.nitrous_ef = nitrous_ef  # tabulated value IPCC E75 (value for Savanna and Grassland)
        self.agb_ref = agb_ref  # taken from IPCC A553 matching clim_moist to rows
        self.agb_tier_2 = agb_tier_2  # tier 2 value, expects float or None
        self.cf_ref = cf_ref  # default is 77%, not tabulated
        self.cf_tier_2 = cf_tier_2  # tier 2 value, expects float or None
        self.soc_start_default = soc_start_default
        self.soc_end_default = soc_end_default
        self.soc_start_tier_2 = soc_start_tier_2  # tier 2 value, expects float or None
        self.soc_end_tier_2 = soc_end_tier_2  # tier 2 value, expects float or None

        self.fmg_start_default = fmg_start_default  # defaulted to 1 in case there are None, if not float value
        self.fmg_end_default = fmg_end_default  # defaulted to 1 in case there are None, if not float value
        self.fmg_start_tier_2 = fmg_start_tier_2  # tier 2 value, expects float or None
        self.fmg_end_tier_2 = fmg_end_tier_2  # tier 2 value, expects float or None
        self.flu_start_default = flu_start_default  # defaulted to 1 in case there are None, if not float value
        self.flu_end_default = flu_end_default  # defaulted to 1 in case there are None, if not float value
        self.flu_start_tier_2 = flu_start_tier_2  # tier 2 value, expects float or None
        self.flu_end_tier_2 = flu_end_tier_2  # tier 2 value, expects float or None
        self.fi_start_default = fi_start_default  # defaulted to 1 in case there are None, if not float value
        self.fi_end_default = fi_end_default  # defaulted to 1 in case there are None, if not float value
        self.fi_start_tier_2 = fi_start_tier_2  # tier 2 value, expects float or None
        self.fi_end_tier_2 = fi_end_tier_2  # tier 2 value, expects float or None

        # TODO: Assigned FMG, FLU, FI values. Maybe once everything has been done change this structure
        self.fmg_start = self.fmg_start_tier_2 if self.fmg_start_tier_2 else self.fmg_start_default
        self.fmg_end = self.fmg_end_tier_2 if self.fmg_end_tier_2 else self.fmg_end_default
        self.flu_start = self.flu_start_tier_2 if self.flu_start_tier_2 else self.flu_start_default
        self.flu_end = self.flu_end_tier_2 if self.flu_end_tier_2 else self.flu_end_default
        self.fi_start = self.fi_start_tier_2 if self.fi_start_tier_2 else self.fi_start_default
        self.fi_end = self.fi_end_tier_2 if self.fi_end_tier_2 else self.fi_end_default

        self.delay = delay  # defaulted to 0 in case there are None, if not float value
        self.ef_nitrous_som = ef_nitrous_som  # tabulated value IPCC E75 (value for Savanna and Grassland)

        # Space for the results
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate)
        self.total_hectars = yearly_time_dependent_parameter_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate, interim_values=True)

        self.soc_start = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start if not self.soc_start_tier_2 else self.soc_start_tier_2
        self.soc_end = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end if not self.soc_end_tier_2 else self.soc_end_tier_2
        # DEFAULTS FOR TIER 2 VALUES INITIALIZATION

        # RESULTS
        self.emissions_residue_burning_yearly = []
        self.emissions_residue_burning_total = 0

        self.emissions_soil_yearly = []
        self.emissions_soil_total = 0

        self.emissions_som_yearly = []
        self.emissions_som_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)

        self.calculate_soc_som = calculate_soc_som

        # TIER 2 DEFAULTS
        self.soc_start_tier_2_default = self.soc_start_default * self.fmg_start * self.fi_start * self.flu_start
        self.soc_end_tier_2_default = self.soc_end_default * self.fmg_end * self.fi_end * self.flu_end
        self.agb_tier_2_default = self.agb_ref
        self.combustion_factor_tier_2_default = self.cf_ref

        return

    def calculate_emissions(
        self,
    ):
        def calculate_residue_burning():
            try:
                if not self.fire_used or self.time_impl + self.time_cap < self.fire_interval or self.fire_interval == None:
                    self.emissions_residue_burning_yearly = [0 for i in range(self.time_impl + self.time_cap)]
                    self.emissions_residue_burning_total = 0

                    # NOTE: needed? Or no?
                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(0, GasTypes.N2O) for i in range(self.time_impl + self.time_cap)], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(0, GasTypes.CH4) for i in range(self.time_impl + self.time_cap)], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))

                else:
                    agb = self.agb_ref if not self.agb_tier_2 else self.agb_tier_2
                    cf = self.cf_ref if not self.cf_tier_2 else self.cf_tier_2
                    agb_cf_gef = agb * cf * (self.methane_ef * self.methane_constant + self.nitrous_ef * self.nitrous_constant) / 1000
                    annual_co2 = agb_cf_gef / self.fire_interval

                    total = annual_co2 * sum(self.total_hectars)
                    self.emissions_residue_burning_yearly = breakdown_according_to_values(total, self.total_hectars)
                    self.emissions_residue_burning_total = total

                    annual_nitrous = (agb * cf * self.nitrous_ef * self.nitrous_constant / 1000) / self.fire_interval
                    annual_methane = (agb * cf * self.methane_ef * self.methane_constant / 1000) / self.fire_interval

                    total_nitrous = annual_nitrous * sum(self.total_hectars)
                    total_methane = annual_methane * sum(self.total_hectars)

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in breakdown_according_to_values(total_nitrous, self.total_hectars)], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))

                    self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in breakdown_according_to_values(total_methane, self.total_hectars)], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))
                return
            except:
                traceback.print_exc()
                return

        def calculate_soil_emissions():
            try:
                if self.calculate_soc_som:
                    self.emissions_soil_yearly, self.emissions_soil_total = soil_emissions_2(self.soc_start, self.soc_end, self.total_hectars, self.area_start, self.area_end, self.hectars_before_20)

                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.emissions_soil_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

            except Exception as e:
                traceback.print_exc()

        def calculate_emissions_som():
            try:
                if self.calculate_soc_som:
                    self.emissions_som_yearly, self.emissions_som_total = som_emissions(self.soc_end, self.soc_start, self.ef_nitrous_som, self.nitrous_constant, self.hectars_before_20)

                    som_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in self.emissions_som_yearly], ActivityTypes.SOM, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(som_emission_set)
            except Exception as e:
                traceback.print_exc()

        calculate_residue_burning()
        calculate_soil_emissions()
        calculate_emissions_som()


        try:
            self.emissions_total_yearly = [x + y for x, y in zip(self.emissions_residue_burning_yearly, self.emissions_soil_yearly)]
            self.total_emissions = sum(self.emissions_total_yearly)
            return self.total_emissions

        except Exception as e:
            traceback.print_exc()
            return None
