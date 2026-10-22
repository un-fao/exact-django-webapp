"""Reservoirs (flooded land), 2019 Refinement to the 2006 IPCC Guidelines, Vol. 4, Ch. 7.

CH4, Eq. 7.10 (reservoirs > 20 years old, Flooded Land Remaining Flooded Land) and
Eq. 7.15 (<= 20 years old, Land Converted to Flooded Land), Tier 1 simplification of (C):
    F_CH4 = alpha x EF_CH4,age x A x (1 + Rd)        [kg CH4/yr]
CO2, Eq. 7.13, only while the reservoir is <= 20 years old (Land Converted to Flooded Land):
    F_CO2 = A x EF_CO2,age<=20                       [t CO2-C/yr], x 44/12 for CO2
alpha: Eq. 7.11 (0.26 x mean annual Chl-a) or Table 7.11 by trophic class.

Reservoir: a waterbody already flooded at the project start, of a known age.
FloodedLandConversion: land flooded by the project through a land use change, aged per yearly cohort.
"""

import traceback
from dataclasses import dataclass
from typing import Optional

from .general_functions import compute_yearly_or_half_year_cumulative
from .generalized_modules import BaseModule
from .ghg_emissions_classes import ActivityTypes, Emission, GasTypes, YearlyGasActivityEmissionSet
from .ghg_inventory_class import InventoryPerGasPerActivity

RD_DEFAULT = 0.09  # Table 7.10, median ratio of downstream to surface CH4 flux
LAND_CONVERTED_YEARS = 20
CHL_A_TO_ALPHA = 0.26  # Eq. 7.11
C_TO_CO2 = 44 / 12
# Table 7.11 oligotrophic alpha, also used when no trophic class is known (NEXT "Default").
RESERVOIR_DEFAULT_ALPHA = 0.7


def trophic_alpha(alpha_tier_2: Optional[float], chl_a: Optional[float], alpha_default: float) -> float:
    """Trophic adjustment factor: explicit Tier 2 alpha, else Eq. 7.11 from Chl-a, else the class default."""
    if alpha_tier_2 is not None:
        return alpha_tier_2
    if chl_a is not None:
        return CHL_A_TO_ALPHA * chl_a
    return alpha_default


@dataclass(kw_only=True)
class Reservoir(BaseModule):
    area_start: float
    area_end: float
    alpha_start: float
    alpha_end: float
    # Years since flooding at the first year of this emission series (activity delay already added).
    age_at_series_start: int
    ch4_ef_age_le_20: float
    ch4_ef_age_gt_20: float
    co2_c_ef_age_le_20: float
    rd: float
    methane_constant: float

    def is_land_converted(self, year_index: int) -> bool:
        return self.age_at_series_start + year_index < LAND_CONVERTED_YEARS

    def ch4_ef(self, year_index: int) -> float:
        return self.ch4_ef_age_le_20 if self.is_land_converted(year_index) else self.ch4_ef_age_gt_20

    def co2_c_ef(self, year_index: int) -> float:
        return self.co2_c_ef_age_le_20 if self.is_land_converted(year_index) else 0.0

    def calculate_emissions(self):
        try:
            # compute_yearly_or_half_year_cumulative is linear in its inputs when one end is 0 (one of
            # area_start / area_end always is, as for CoastalWaterbodies), so the per-year EF can be applied after it.
            alpha_area = compute_yearly_or_half_year_cumulative(self.area_start * self.alpha_start, self.area_end * self.alpha_end, self.implementation_time, self.capitalization_time, self.rate_type)
            area = compute_yearly_or_half_year_cumulative(self.area_start, self.area_end, self.implementation_time, self.capitalization_time, self.rate_type)

            ch4_factor = (1 + self.rd) / 1000 * self.methane_constant
            self.ch4_yearly = [x * self.ch4_ef(i) * ch4_factor for i, x in enumerate(alpha_area)]
            self.co2_yearly = [a * self.co2_c_ef(i) * C_TO_CO2 for i, a in enumerate(area)]

            self.result.yearly_emissions_by_sector_by_gas.append(
                YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in self.ch4_yearly], ActivityTypes.FLOODED_LAND_CH4, delay=self.delay)
            )
            self.result.yearly_emissions_by_sector_by_gas.append(
                YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.co2_yearly], ActivityTypes.FLOODED_LAND_CO2, delay=self.delay)
            )

            self.inventory.emissions_by_sector_by_gas(InventoryPerGasPerActivity(GasTypes.CH4, self.area_start * self.alpha_start * self.ch4_ef(0) * ch4_factor, ActivityTypes.FLOODED_LAND_CH4))
            self.inventory.emissions_by_sector_by_gas(InventoryPerGasPerActivity(GasTypes.CO2, self.area_start * self.co2_c_ef(0) * C_TO_CO2, ActivityTypes.FLOODED_LAND_CO2))
        except Exception as e:
            traceback.print_exc()
            raise e


@dataclass(kw_only=True)
class FloodedLandConversion(BaseModule):
    area: float
    alpha: float
    ch4_ef_age_le_20: float
    ch4_ef_age_gt_20: float
    co2_c_ef_age_le_20: float
    rd: float
    methane_constant: float

    def calculate_emissions(self):
        # Each year's newly flooded area stays "land converted to flooded land" for 20 years from its own
        # flooding, so the area older than 20 in year t is the flooded area of year t - 20.
        flooded = compute_yearly_or_half_year_cumulative(0, self.area, self.implementation_time, self.capitalization_time, self.rate_type)
        aged = [flooded[i - LAND_CONVERTED_YEARS] if i >= LAND_CONVERTED_YEARS else 0.0 for i in range(len(flooded))]
        young = [f - a for f, a in zip(flooded, aged)]

        ch4_factor = self.alpha * (1 + self.rd) / 1000 * self.methane_constant
        ch4 = [(y * self.ch4_ef_age_le_20 + a * self.ch4_ef_age_gt_20) * ch4_factor for y, a in zip(young, aged)]
        co2 = [y * self.co2_c_ef_age_le_20 * C_TO_CO2 for y in young]

        self.result.yearly_emissions_by_sector_by_gas.append(
            YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in ch4], ActivityTypes.FLOODED_LAND_CH4, delay=self.delay)
        )
        self.result.yearly_emissions_by_sector_by_gas.append(
            YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in co2], ActivityTypes.FLOODED_LAND_CO2, delay=self.delay)
        )
        self.inventory.emissions_by_sector_by_gas(InventoryPerGasPerActivity(GasTypes.CH4, 0, ActivityTypes.FLOODED_LAND_CH4))
        self.inventory.emissions_by_sector_by_gas(InventoryPerGasPerActivity(GasTypes.CO2, 0, ActivityTypes.FLOODED_LAND_CO2))
