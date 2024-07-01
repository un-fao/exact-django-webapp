import math
import traceback

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


class FloodedRice(BaseModule):
    def __init__(
        self,
        area_start,
        area_end,
        EFc_ref,
        EFc_tier_2,
        SFw_ref,
        SFw_tier_2,
        SFp_ref,
        SFp_tier_2,
        cfoa,
        SFo_tier_2,
        adjusted_daily_ef_methane_tier_2,
        yield_ref,
        yield_tier_2,
        rice_slope,
        rice_intercept,
        straw_tonnes_tier_2,
        methane_ef,
        rice_cf,
        nitrous_ef,
        nitrous_constant,
        time_impl,
        time_cap,
        rate,
        methane_constant,
        cultivation_period_ref,
        cultivation_period_tier_2,
        soc_start_default,
        soc_end_default,
        soc_start_tier_2,
        soc_end_tier_2,
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
        calculate_soc_som,
        straw_burnt,
        delay,
        ef_nitrous_som,
        is_minor_season=True,
    ):
        self.area_start = area_start
        self.area_end = area_end
        self.EFc_ref = EFc_ref
        self.EFc_tier_2 = EFc_tier_2
        self.SFw_ref = SFw_ref
        self.SFw_tier_2 = SFw_tier_2
        self.SFp_ref = SFp_ref
        self.SFp_tier_2 = SFp_tier_2
        self.cfoa = cfoa
        self.SFo_tier_2 = SFo_tier_2
        self.adjusted_daily_ef_methane_tier_2 = adjusted_daily_ef_methane_tier_2
        self.yield_ref = yield_ref
        self.yield_tier_2 = yield_tier_2
        self.rice_slope = rice_slope
        self.rice_intercept = rice_intercept
        self.straw_tonnes_tier_2 = straw_tonnes_tier_2
        self.methane_ef = methane_ef
        self.rice_cf = rice_cf
        self.nitrous_ef = nitrous_ef
        self.nitrous_constant = nitrous_constant
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate = rate
        self.methane_constant = methane_constant
        self.cultivation_period_ref = cultivation_period_ref
        self.cultivation_period_tier_2 = cultivation_period_tier_2

        self.soc_start_default = soc_start_default
        self.soc_end_default = soc_end_default
        self.soc_start_tier_2 = soc_start_tier_2
        self.soc_end_tier_2 = soc_end_tier_2

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

        self.ef_nitrous_som = ef_nitrous_som

        self.calculate_soc_som = calculate_soc_som

        self.straw_burnt = straw_burnt

        self.delay = delay

        # NOTE: in the case in which it is a minor season, soil and som emissions are not to be calculated
        self.is_minor_season = is_minor_season

        # TODO: Assigned FMG, FLU, FI values. Maybe once everything has been done change this structure
        self.fmg_start = self.fmg_start_tier_2 if self.fmg_start_tier_2 else self.fmg_start_default
        self.fmg_end = self.fmg_end_tier_2 if self.fmg_end_tier_2 else self.fmg_end_default
        self.flu_start = self.flu_start_tier_2 if self.flu_start_tier_2 else self.flu_start_default
        self.flu_end = self.flu_end_tier_2 if self.flu_end_tier_2 else self.flu_end_default
        self.fi_start = self.fi_start_tier_2 if self.fi_start_tier_2 else self.fi_start_default
        self.fi_end = self.fi_end_tier_2 if self.fi_end_tier_2 else self.fi_end_default

        # TIER 2 DEFAULTS
        # TODO: THIS CAN BE MADE BETTER, BUT HOW?
        efc_placeholder = self.EFc_ref if not self.EFc_tier_2 else self.EFc_tier_2
        sfw_placeholder = self.SFw_ref if not self.SFw_tier_2 else self.SFw_tier_2
        sfp_placeholder = self.SFp_ref if not self.SFp_tier_2 else self.SFp_tier_2

        self.EFc_tier_2_default = self.EFc_ref
        self.SFw_tier_2_default = self.SFw_ref
        self.SFp_tier_2_default = self.SFp_ref
        self.straw_tonnes_tier_2_default = self.yield_ref * self.rice_slope + self.rice_intercept
        self.SFo_tier_2_default = 1 + self.straw_tonnes_tier_2 * self.cfoa * 0.59 if self.straw_tonnes_tier_2 else 1 + self.straw_tonnes_tier_2_default * self.cfoa * 0.59
        self.adjusted_daily_ef_methane_tier_2_default = efc_placeholder * sfw_placeholder * sfp_placeholder * self.SFo_tier_2_default

        # HECTARES
        self.hectares_before_20, self.hectares_after_20 = yearly_time_dependent_20_year_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate)
        self.hectares_total = yearly_time_dependent_parameter_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate)

        self.soc_start = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start if not self.soc_start_tier_2 else self.soc_start_tier_2
        self.soc_end = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end if not self.soc_end_tier_2 else self.soc_end_tier_2

        # RESULTS
        self.ch4_emitted_yearly = []
        self.ch4_emitted_total = 0

        self.straw_burning_yearly = []
        self.straw_burning_total = 0

        self.soil_emissions_yearly = []
        self.soil_emissions_total = 0

        self.emissions_som_yearly = []
        self.emissions_som_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)

    def calculate_emissions(
        self,
    ):
        def calculate_ch4_emitted():
            try:
                # TODO: maybe this could be moved to the constructor
                EFc = self.EFc_ref if not self.EFc_tier_2 else self.EFc_tier_2
                SFw = self.SFw_ref if not self.SFw_tier_2 else self.SFw_tier_2
                SFp = self.SFp_ref if not self.SFp_tier_2 else self.SFp_tier_2
                yield_value = self.yield_ref if not self.yield_tier_2 else self.yield_tier_2
                straw_tonnes_ref = yield_value * self.rice_slope + self.rice_intercept if not self.straw_tonnes_tier_2 else self.straw_tonnes_tier_2
                SFo = (1 + straw_tonnes_ref * self.cfoa) ** 0.59 if not self.SFo_tier_2 else self.SFo_tier_2

                if self.area_start == 0 and self.area_end == 0:
                    adjusted_daily_ef_methane_ref = 0
                else:
                    adjusted_daily_ef_methane_ref = EFc * SFw * SFp * SFo if not self.adjusted_daily_ef_methane_tier_2 else self.adjusted_daily_ef_methane_tier_2

                cultivation_period = self.cultivation_period_ref if not self.cultivation_period_tier_2 else self.cultivation_period_tier_2

                kg_methane_cultivation_period = adjusted_daily_ef_methane_ref * cultivation_period

                self.ch4_emitted_total = kg_methane_cultivation_period * sum(self.hectares_total) * self.methane_constant / 1000
                self.ch4_emitted_yearly = breakdown_according_to_values(self.ch4_emitted_total, self.hectares_total)

                ch4_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in self.ch4_emitted_yearly], ActivityTypes.CH4_EMITTED_RICE, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(ch4_emission_set)

            except:
                traceback.print_exc()
                return

        def calculate_straw_burning():
            try:
                if not self.straw_burnt or (self.area_start == 0 and self.area_end == 0):
                    self.straw_burning_yearly = [0 for i in range(self.time_impl + self.time_cap)]
                    self.straw_burning_total = 0

                else:
                    yield_value = self.yield_ref if not self.yield_tier_2 else self.yield_tier_2
                    straw_tonnes_ref = yield_value * self.rice_slope + self.rice_intercept if not self.straw_tonnes_tier_2 else self.straw_tonnes_tier_2
                    straw_methane_co2 = straw_tonnes_ref * self.rice_cf * self.methane_ef * self.methane_constant / 1000
                    straw_nitrous_co2 = straw_tonnes_ref * self.rice_cf * self.nitrous_ef * self.nitrous_constant / 1000

                    annual_co2 = straw_methane_co2 + straw_nitrous_co2

                    total = annual_co2 * sum(self.hectares_total)
                    self.straw_burning_yearly = breakdown_according_to_values(total, self.hectares_total)
                    self.straw_burning_total = sum(self.straw_burning_yearly)

                    total_methane = straw_methane_co2 * sum(self.hectares_total)
                    total_nitrous = straw_nitrous_co2 * sum(self.hectares_total)

                    straw_burning_set_methane = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(total_methane, GasTypes.CH4)], ActivityTypes.STRAW_BURNING, delay=self.delay)
                    straw_burning_set_nitrous = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(total_nitrous, GasTypes.N2O)], ActivityTypes.STRAW_BURNING, delay=self.delay)

                    self.result.yearly_emissions_by_sector_by_gas.append(straw_burning_set_methane)
                    self.result.yearly_emissions_by_sector_by_gas.append(straw_burning_set_nitrous)
            except:
                traceback.print_exc()
                return

        def calculate_soil_emissions():
            try:
                if self.calculate_soc_som and not self.is_minor_season:
                    self.soil_emissions_yearly, self.soil_emissions_total = soil_emissions_2(self.soc_start, self.soc_end, self.hectares_total, self.area_start, self.area_end, self.hectares_before_20)

                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.soil_emissions_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

            except:
                traceback.print_exc()
                return

        def calculate_emissions_som():
            try:
                if self.calculate_soc_som and not self.is_minor_season:
                    self.emissions_som_yearly, self.emissions_som_total = som_emissions(self.soc_end, self.soc_start, self.ef_nitrous_som, self.nitrous_constant, self.hectares_before_20)

                    som_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in self.emissions_som_yearly], ActivityTypes.SOM, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(som_emission_set)
            except Exception as e:
                traceback.print_exc()

        calculate_ch4_emitted()
        calculate_straw_burning()
        calculate_soil_emissions()
        calculate_emissions_som()

        self.emissions_total_yearly = [i + j + k for i, j, k in zip(self.ch4_emitted_yearly, self.straw_burning_yearly, self.soil_emissions_yearly)]
        self.total_emissions = self.ch4_emitted_total + self.straw_burning_total + self.soil_emissions_total
