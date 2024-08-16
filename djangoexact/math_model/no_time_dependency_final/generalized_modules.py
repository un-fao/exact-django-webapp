from abc import ABC
from general_functions import Tier2Defaults
import re
import traceback
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

from dataclasses import dataclass, field

@dataclass
class BaseModule:
    implementation_time: int
    capitalization_time: int
    rate_type: str
    delay: int = 0

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