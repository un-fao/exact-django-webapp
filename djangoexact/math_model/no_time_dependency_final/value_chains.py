import math
import traceback

from .general_functions import compute_yearly_or_half_year_cumulative
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)

from dataclasses import dataclass, field
from typing import Optional
from .generalized_modules import BaseModule
from ghg_inventory_class import InventoryPerGasperActivity


@dataclass(kw_only=True)
class ValueChain(BaseModule):
    # Emission factors
    emission_factor_start_default: float
    emission_factor_end_default: float
    emission_factor_start_tier_2: Optional[float] = None
    emission_factor_end_tier_2: Optional[float] = None

    # Input quantities
    input_quantity_start: float
    input_quantity_end: float

    activity_type: ActivityTypes

    def __post_init__(self):
        super().__post_init__()

        self.emission_factor_start = self.emission_factor_start_tier_2 if self.emission_factor_start_tier_2 is not None else self.emission_factor_start_default
        self.emission_factor_end = self.emission_factor_end_tier_2 if self.emission_factor_end_tier_2 is not None else self.emission_factor_end_default

    def calculate_emissions(self):
        emissions_start = self.input_quantity_start * self.emission_factor_start
        emissions_end = self.input_quantity_end * self.emission_factor_end

        emissions_yearly = compute_yearly_or_half_year_cumulative(emissions_start, emissions_end, self.implementation_time, self.capitalization_time, self.rate_type)

        emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_yearly], self.activity_type, delay=self.delay)
        self.result.yearly_emissions_by_sector_by_gas.append(emission_set)
        inventory = InventoryPerGasperActivity(GasTypes.CO2, emissions_start, self.activity_type)
        self.inventory.emissions_by_sector_by_gas(inventory)
