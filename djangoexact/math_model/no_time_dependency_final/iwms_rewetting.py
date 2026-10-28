"""CH4 from rewetted inland wetland mineral soils (IWMS), IPCC 2013 Wetlands Supplement, chapter 5.

    CH4 = A_rewetted * EF_CH4 / 1000 * GWP_CH4        (Equation 5.1, t CO2e / yr)

EF_CH4 in kg CH4 / ha / yr (Table 5.4 by climate, or a Tier 2 value). The annual emission is computed at the start
and end rewetted areas and interpolated with the activity's change rate, as the other non-land modules do.
"""

from dataclasses import dataclass

from .general_functions import compute_yearly_or_half_year_cumulative
from .generalized_modules import BaseModule
from .ghg_emissions_classes import ActivityTypes, Emission, GasTypes, YearlyGasActivityEmissionSet
from .ghg_inventory_class import InventoryPerGasPerActivity


def annual_ch4(area: float, ef_ch4: float, gwp_ch4: float) -> float:
    """t CO2e / yr."""
    return area * ef_ch4 / 1000 * gwp_ch4


@dataclass(kw_only=True)
class IwmsRewetting(BaseModule):
    area_start: float
    area_end: float
    ef_ch4_start: float
    ef_ch4_end: float
    gwp_ch4: float

    def calculate_emissions(self):
        start = annual_ch4(self.area_start, self.ef_ch4_start, self.gwp_ch4)
        end = annual_ch4(self.area_end, self.ef_ch4_end, self.gwp_ch4)
        yearly = compute_yearly_or_half_year_cumulative(start, end, self.implementation_time, self.capitalization_time, self.rate_type)
        self.result.yearly_emissions_by_sector_by_gas.append(
            YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in yearly], ActivityTypes.IWMS_REWETTING_CH4, delay=self.delay)
        )
        self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CH4, start, ActivityTypes.IWMS_REWETTING_CH4))
