import math
import traceback

from .general_functions import (
    breakdown_according_to_values,
    soil_emissions_2,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
    som_emissions,
    biomass_emissions
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

from .generalized_modules import LandModule
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class FloodedRice(LandModule):
    EFc_ref: float
    EFc_tier_2: Optional[float]
    SFw_ref: float
    SFw_tier_2: Optional[float]
    SFp_ref: float
    SFp_tier_2: Optional[float]
    cfoa: float
    SFo_tier_2: Optional[float]
    adjusted_daily_ef_methane_tier_2: Optional[float]
    yield_ref: float
    yield_tier_2: Optional[float]
    rice_slope: float
    rice_intercept: float
    straw_tonnes_tier_2: Optional[float]
    methane_ef: float
    rice_cf: float
    nitrous_ef: float
    nitrous_constant: float
    methane_constant: float
    cultivation_period_ref: float
    cultivation_period_tier_2: Optional[float]
    straw_burnt: float
    delay: int 
    is_minor_season: bool = True

    def __post_init__(self):
        super().__post_init__()

        self.EFc = self.EFc_tier_2 or self.EFc_ref
        self.SFw = self.SFw_tier_2 or self.SFw_ref
        self.SFp = self.SFp_tier_2 or self.SFp_ref

        # NOTE: this is a default value that is calculated based on the input values, needed for the frontend
        self.straw_tonnes_tier_2_default = self.yield_ref * self.rice_slope + self.rice_intercept
        self.SFo_tier_2_default = 1 + (self.straw_tonnes_tier_2 or self.straw_tonnes_tier_2_default) * self.cfoa * 0.59
        self.adjusted_daily_ef_methane_tier_2_default = self.EFc * self.SFw * self.SFp * (self.SFo_tier_2 or self.SFo_tier_2_default)


    def calculate_emissions(
        self,
    ):
        def calculate_ch4_emitted():
            try:
                yield_value = self.yield_ref if not self.yield_tier_2 else self.yield_tier_2
                straw_tonnes_ref = yield_value * self.rice_slope + self.rice_intercept if not self.straw_tonnes_tier_2 else self.straw_tonnes_tier_2
                SFo = (1 + straw_tonnes_ref * self.cfoa) ** 0.59 if not self.SFo_tier_2 else self.SFo_tier_2

                if self.hectares_start == 0 and self.hectares_end == 0:
                    adjusted_daily_ef_methane_ref = 0
                else:
                    adjusted_daily_ef_methane_ref = self.EFc * self.SFw * self.SFp * SFo if not self.adjusted_daily_ef_methane_tier_2 else self.adjusted_daily_ef_methane_tier_2

                cultivation_period = self.cultivation_period_ref if not self.cultivation_period_tier_2 else self.cultivation_period_tier_2

                kg_methane_cultivation_period = adjusted_daily_ef_methane_ref * cultivation_period

                ch4_emitted_total = kg_methane_cultivation_period * sum(self.hectares_total) * self.methane_constant / 1000
                ch4_emitted_yearly = breakdown_according_to_values(ch4_emitted_total, self.hectares_total)

                ch4_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in ch4_emitted_yearly], ActivityTypes.CH4_EMITTED_RICE, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(ch4_emission_set)

            except:
                traceback.print_exc()
                return

        def calculate_straw_burning():
            try:
                if not self.straw_burnt or (self.hectares_start == 0 and self.hectares_end == 0):
                    pass

                else:
                    yield_value = self.yield_ref if not self.yield_tier_2 else self.yield_tier_2
                    straw_tonnes_ref = yield_value * self.rice_slope + self.rice_intercept if not self.straw_tonnes_tier_2 else self.straw_tonnes_tier_2
                    straw_methane_co2 = straw_tonnes_ref * self.rice_cf * self.methane_ef * self.methane_constant / 1000
                    straw_nitrous_co2 = straw_tonnes_ref * self.rice_cf * self.nitrous_ef * self.nitrous_constant / 1000

                    total_methane = straw_methane_co2 * sum(self.hectares_total)
                    total_nitrous = straw_nitrous_co2 * sum(self.hectares_total)

                    # TODO: check if this should be breakdown according to hectares_total or hectares_under_20
                    straw_burning_set_methane = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in breakdown_according_to_values(total_methane, self.hectares_total)], ActivityTypes.STRAW_BURNING, delay=self.delay)
                    straw_burning_set_nitrous = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in breakdown_according_to_values(total_nitrous, self.hectares_total)], ActivityTypes.STRAW_BURNING, delay=self.delay)

                    self.result.yearly_emissions_by_sector_by_gas.append(straw_burning_set_methane)
                    self.result.yearly_emissions_by_sector_by_gas.append(straw_burning_set_nitrous)
            except:
                traceback.print_exc()
                return

        def calculate_soil_emissions():
            try:
                if self.calculate_soc_som and not self.is_minor_season:
                    soil_emissions_yearly, soil_emissions_total = soil_emissions_2(self.soc_start, self.soc_end, self.hectares_total, self.hectares_start, self.hectares_end, self.hectares_before_20)

                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in soil_emissions_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

            except:
                traceback.print_exc()
                return

        def calculate_emissions_som():
            try:
                if self.calculate_soc_som and not self.is_minor_season:
                    emissions_som_yearly, emissions_som_total = som_emissions(self.soc_end, self.soc_start, self.ef_nitrous_som, self.nitrous_constant, self.hectares_before_20)

                    som_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in emissions_som_yearly], ActivityTypes.SOM, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(som_emission_set)
            except Exception as e:
                traceback.print_exc()

        def calculate_biomass_emissions():

            # NOTE: should this be calculated only for main season?
            try:
                if self.calculate_biomass:
                    emissions_biomass_yearly, emissions_biomass_total = biomass_emissions(self.biomass_start, self.biomass_end, self.hectares_start, self.hectares_end, self.rate_type, self.implementation_time, self.capitalization_time)
                    biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_biomass_yearly], ActivityTypes.BIOMASS, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)
                else:
                    pass

            except Exception as e:
                traceback.print_exc()

        calculate_ch4_emitted()
        calculate_straw_burning()
        calculate_soil_emissions()
        calculate_emissions_som()
        calculate_biomass_emissions()


# implementation_time = 5
# capitalization_time = 5
# rate_type = "linear"
# delay = 0

# EFc_ref = 0.01
# EFc_tier_2 = None
# SFw_ref = 0.01
# SFw_tier_2 = None
# SFp_ref = 0.01
# SFp_tier_2 = None
# cfoa = 0.01
# SFo_tier_2 = None
# adjusted_daily_ef_methane_tier_2 = None
# yield_ref = 0.01
# yield_tier_2 = None
# rice_slope = 0.01
# rice_intercept = 0.01
# straw_tonnes_tier_2 = None
# methane_ef = 0.01
# rice_cf = 0.01
# nitrous_ef = 0.01
# nitrous_constant = 0.01
# methane_constant = 0.01
# cultivation_period_ref = 0.01
# cultivation_period_tier_2 = None
# straw_burnt = 0.01
# is_minor_season = True

# hectares_start = 0.01
# hectares_end = 0.01
# soc_start_default = 0.01
# soc_end_default = 0.01
# soc_start_tier_2_default = None
# soc_end_tier_2_default = None
# fmg_start_default = 0.01
# fmg_end_default = 0.01
# fmg_start_tier_2_default = None
# fmg_end_tier_2_default = None
# flu_start_default = 0.01
# flu_end_default = 0.01
# flu_start_tier_2_default = None
# flu_end_tier_2_default = None
# fi_start_default = 0.01
# fi_end_default = 0.01
# fi_start_tier_2_default = None
# fi_end_tier_2_default = None
# calculate_soc_som = True
# ef_nitrous_som = 0.01
# biomass_start_default = 0.01
# biomass_end_default = 0.01
# biomass_start_tier_2_default = None
# biomass_end_tier_2_default = None

# flooded_rice = FloodedRice(
#     hectares_start = hectares_start,
#     hectares_end = hectares_end,
#     soc_start_default = soc_start_default,
#     soc_end_default = soc_end_default,
#     soc_start_tier_2_default = soc_start_tier_2_default,
#     soc_end_tier_2_default = soc_end_tier_2_default,
#     fmg_start_default = fmg_start_default,
#     fmg_end_default = fmg_end_default,
#     fmg_start_tier_2_default = fmg_start_tier_2_default,
#     fmg_end_tier_2_default = fmg_end_tier_2_default,
#     flu_start_default = flu_start_default,
#     flu_end_default = flu_end_default,
#     flu_start_tier_2_default = flu_start_tier_2_default,
#     flu_end_tier_2_default = flu_end_tier_2_default,
#     fi_start_default = fi_start_default,
#     fi_end_default = fi_end_default,
#     fi_start_tier_2_default = fi_start_tier_2_default,
#     fi_end_tier_2_default = fi_end_tier_2_default,
#     calculate_soc_som = calculate_soc_som,
#     ef_nitrous_som = ef_nitrous_som,
#     biomass_start_default = biomass_start_default,
#     biomass_end_default = biomass_end_default,
#     biomass_start_tier_2_default = biomass_start_tier_2_default,
#     biomass_end_tier_2_default = biomass_end_tier_2_default,
#     EFc_ref = EFc_ref,
#     EFc_tier_2 = EFc_tier_2,
#     SFw_ref = SFw_ref,
#     SFw_tier_2 = SFw_tier_2,
#     SFp_ref = SFp_ref,
#     SFp_tier_2 = SFp_tier_2,
#     cfoa = cfoa,
#     SFo_tier_2 = SFo_tier_2,
#     adjusted_daily_ef_methane_tier_2 = adjusted_daily_ef_methane_tier_2,
#     yield_ref = yield_ref,
#     yield_tier_2 = yield_tier_2,
#     rice_slope = rice_slope,
#     rice_intercept = rice_intercept,
#     straw_tonnes_tier_2 = straw_tonnes_tier_2,
#     methane_ef = methane_ef,
#     rice_cf = rice_cf,
#     nitrous_ef = nitrous_ef,
#     nitrous_constant = nitrous_constant,
#     methane_constant = methane_constant,
#     cultivation_period_ref = cultivation_period_ref,
#     cultivation_period_tier_2 = cultivation_period_tier_2,
#     straw_burnt = straw_burnt,
#     is_minor_season = is_minor_season,
#     implementation_time = implementation_time,
#     capitalization_time = capitalization_time,
#     rate_type = rate_type,
#     delay = delay
# )

# flooded_rice.calculate_emissions()
# print(flooded_rice.straw_tonnes_tier_2_default)
