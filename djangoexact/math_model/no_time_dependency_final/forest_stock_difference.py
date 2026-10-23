"""Forest management, stock-difference approach.

IPCC 2006 Vol. 4, ch. 2, eq. 2.5: delta C = (C_t2 - C_t1) / (t2 - t1), applied per carbon pool.
The user gives the stock of each pool (tC/ha) at the start and at the end of the period; the transition
between the two follows the activity's change rate over the implementation period, then stays at the end
stock during capitalisation. Summed over the period the CO2 equals -(C_end - C_start) x area x 44/12.

Result lines reuse the gain-loss activities so totals, charts and reports need no changes.
"""

from dataclasses import dataclass

from .general_functions import compute_yearly_or_half_year_cumulative
from .generalized_modules import BaseModule
from .ghg_emissions_classes import ActivityTypes, Emission, GasTypes, YearlyGasActivityEmissionSet
from .ghg_inventory_class import InventoryPerGasPerActivity

POOL_ACTIVITIES = {
    "agb": ActivityTypes.AGB_GROWTH,
    "bgb": ActivityTypes.BGB_GROWTH,
    "litter": ActivityTypes.LITTER,
    "deadwood": ActivityTypes.DEADWOOD,
    "soc": ActivityTypes.SOIL_CO2_CHANGE,
}

C_TO_CO2 = 44 / 12


def yearly_change_fractions(implementation_time: int, capitalization_time: int, rate_type: str) -> list[float]:
    """Share of the total stock change that happens in each year (sums to 1)."""
    # A 0 -> 1 trajectory is used instead of start -> end stocks because it is exact for every rate type,
    # including the exponential branch that is wrong for non-zero start values on develop.
    trajectory = compute_yearly_or_half_year_cumulative(0, 1, implementation_time, capitalization_time, rate_type, interim_values=False)
    # "immediate" returns the end value from year 0; pinning year 0 to 0 puts the whole change in year 1.
    trajectory[0] = 0
    return [trajectory[i] - trajectory[i - 1] for i in range(1, len(trajectory))]


@dataclass(kw_only=True)
class ForestStockDifference(BaseModule):
    hectares: float
    stocks_start: dict[str, float]
    stocks_end: dict[str, float]

    def __post_init__(self):
        super().__post_init__()
        for label, stocks in (("start", self.stocks_start), ("end", self.stocks_end)):
            for pool in POOL_ACTIVITIES:
                value = stocks.get(pool)
                if value is None or value < 0:
                    raise ValueError(f"Stock-difference approach needs a non-negative {pool} carbon stock at the {label} of the period (tC/ha), got {value!r}")

    def calculate_emissions(self):
        fractions = yearly_change_fractions(self.implementation_time, self.capitalization_time, self.rate_type)

        for pool, activity in POOL_ACTIVITIES.items():
            total_co2 = -(self.stocks_end[pool] - self.stocks_start[pool]) * self.hectares * C_TO_CO2
            emissions = [Emission(total_co2 * f, GasTypes.CO2) for f in fractions]
            self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(0, GasTypes.CO2, emissions, activity, delay=self.delay))
            self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CO2, self.stocks_start[pool] * self.hectares * C_TO_CO2, activity))
