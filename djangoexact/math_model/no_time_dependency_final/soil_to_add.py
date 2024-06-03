import math
import traceback

from .general_functions import (
    BaseModule,
    breakdown_according_to_values,
    soil_emissions_2,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

class SoilToAdd(BaseModule):
    def __init__(
        self,
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
        area_start,
        area_end,
        time_impl,
        time_cap,
        rate,
        delay = 0):

        self.soc_start_default = soc_start_default
        self.soc_end_default = soc_end_default
        self.soc_start_tier_2 = soc_start_tier_2
        self.soc_end_tier_2 = soc_end_tier_2
        
        self.fmg_start_default = fmg_start_default
        self.fmg_end_default = fmg_end_default
        self.fmg_start_tier_2 = fmg_start_tier_2
        self.fmg_end_tier_2 = fmg_end_tier_2

        self.flu_start_default = flu_start_default
        self.flu_end_default = flu_end_default
        self.flu_start_tier_2 = flu_start_tier_2
        self.flu_end_tier_2 = flu_end_tier_2

        self.fi_start_default = fi_start_default
        self.fi_end_default = fi_end_default
        self.fi_start_tier_2 = fi_start_tier_2
        self.fi_end_tier_2 = fi_end_tier_2

        self.calculate_soc_som = calculate_soc_som
        self.delay = delay
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate = rate

        self.area_start = area_start
        self.area_end = area_end

        self.hectares_before_20, self.hectares_after_20 = yearly_time_dependent_20_year_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate)
        self.hectares_total = yearly_time_dependent_parameter_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate)

        self.fmg_start = self.fmg_start_tier_2 if self.fmg_start_tier_2 else self.fmg_start_default
        self.fmg_end = self.fmg_end_tier_2 if self.fmg_end_tier_2 else self.fmg_end_default
        self.flu_start = self.flu_start_tier_2 if self.flu_start_tier_2 else self.flu_start_default
        self.flu_end = self.flu_end_tier_2 if self.flu_end_tier_2 else self.flu_end_default
        self.fi_start = self.fi_start_tier_2 if self.fi_start_tier_2 else self.fi_start_default
        self.fi_end = self.fi_end_tier_2 if self.fi_end_tier_2 else self.fi_end_default

        self.soc_start = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start if not self.soc_start_tier_2 else self.soc_start_tier_2
        self.soc_end = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end if not self.soc_end_tier_2 else self.soc_end_tier_2

        self.result = Result(self.time_impl, self.time_cap)

    def calculate_emissions(self):
        try:
            if self.calculate_soc_som:
                self.soil_emissions_yearly, self.soil_emissions_total = soil_emissions_2(self.soc_start, self.soc_end, self.hectares_total, self.area_start, self.area_end, self.hectares_before_20)

                soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.soil_emissions_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

        except Exception as e:
            print("Error in SoilToAdd.calculate_emissions")
            print(e)
            print(traceback.format_exc())
            return 0