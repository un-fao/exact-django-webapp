from abc import ABC
from .general_functions import Tier2Defaults
import re
import traceback
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

from .general_functions import (
    breakdown_according_to_values,
    soil_emissions_2,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
    som_emissions,
    biomass_emissions
)

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class BaseModule:
    implementation_time: int
    capitalization_time: int
    rate_type: str
    delay: int 

    def __post_init__(self):
        self.result = Result(self.implementation_time, self.capitalization_time)

    def evaluate_tier_2_defaults(self):
        try:
            t2_start = {re.sub("_start_tier_2_default", "", k): v for k, v in self.__dict__.items() if "start_tier_2_default" in k}
            t2_end = {re.sub("_end_tier_2_default", "", k): v for k, v in self.__dict__.items() if "end_tier_2_default" in k}
            t2_other = {re.sub("_tier_2_default", "", k): v for k, v in self.__dict__.items() if "_tier_2_default" in k and "start" not in k and "end" not in k}

            return Tier2Defaults(t2_start, t2_end, t2_other)
        except Exception as e:
            traceback.print_exc()
            return {}
        

@dataclass
class LandModule(BaseModule):
    hectares_start: float
    hectares_end: float

    soc_start_default: float
    soc_end_default: float
    soc_start_tier_2: Optional[float]
    soc_end_tier_2: Optional[float]
    fmg_start_default: float
    fmg_end_default: float
    fmg_start_tier_2: Optional[float]
    fmg_end_tier_2: Optional[float]
    flu_start_default: float
    flu_end_default: float
    flu_start_tier_2: Optional[float]
    flu_end_tier_2: Optional[float]
    fi_start_default: float
    fi_end_default: float
    fi_start_tier_2: Optional[float]
    fi_end_tier_2: Optional[float]

    calculate_soc_som: bool
    ef_nitrous_som: float

    # NOTE: biomass_start and biomass_end are set to Optional[float] only because in Perennial Biomass Emissions it is necessary for the calculations (if self.biomass_start and self.biomass_end:)
    # maybe we can send a parameter to the perennial or perennial.calculate_emissions() to avoid this
    biomass_start_default: Optional[float]
    biomass_end_default: Optional[float]
    biomass_start_tier_2: Optional[float]
    biomass_end_tier_2: Optional[float]

    def __post_init__(self):
        super().__post_init__()

        fmg_start = self.fmg_start_tier_2 or self.fmg_start_default
        fmg_end = self.fmg_end_tier_2 or self.fmg_end_default
        flu_start = self.flu_start_tier_2 or self.flu_start_default
        flu_end = self.flu_end_tier_2 or self.flu_end_default
        fi_start = self.fi_start_tier_2 or self.fi_start_default
        fi_end = self.fi_end_tier_2 or self.fi_end_default
        soc_ref_start = self.soc_start_tier_2 or self.soc_start_default
        soc_ref_end = self.soc_end_tier_2 or self.soc_end_default

        self.soc_start = soc_ref_start * fmg_start * fi_start * flu_start
        self.soc_end = soc_ref_end * fmg_end * fi_end * flu_end

        self.biomass_start = self.biomass_start_tier_2 or self.biomass_start_default
        self.biomass_end = self.biomass_end_tier_2 or self.biomass_end_default

        self.hectares_before_20, self.hectares_after_20 = yearly_time_dependent_20_year_breakdown(self.hectares_start, self.hectares_end, self.implementation_time, self.capitalization_time, self.rate_type)
        self.hectares_total = yearly_time_dependent_parameter_breakdown(self.hectares_start, self.hectares_end, self.implementation_time, self.capitalization_time, self.rate_type)

    # TODO: Consider moving som_calculation, soil_calculation and biomass_calculation to here