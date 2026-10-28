"""Harvested wood products (HWP) in use: first-order decay (FOD) pool.

Source: 2019 Refinement to the 2006 IPCC Guidelines, Vol. 4, ch. 12 (Harvested Wood Products).

- Eq. 12.2 (same as eq. 12.1 of the 2006 Guidelines, Vol. 4, ch. 12), per commodity class l:
      C_l(i+1) = e^-k * C_l(i) + [(1 - e^-k) / k] * Inflow_l(i)
      dC_l(i)  = C_l(i+1) - C_l(i)
      k        = ln(2) / HL
- Eq. 12.1: CO2 from the HWP pool = 44/12 * sum_l dC_l(i). EX-ACT reports emissions as positive,
  so a growing pool is reported as a removal: co2(i) = -dC(i) * 44/12 (CRT category 4.G).
- Table 12.3, Tier 1 default half-lives: paper and paperboard 2 years, wood-based panels 25, sawnwood 35.

The share of the inflow not assigned to a commodity class is oxidised in the year of harvest (fuelwood, residues).
IPCC gives no default product shares (Tier 1 takes them from national FAOSTAT production data), so the caller
supplies them. The pool starts empty (C(0) = 0): no inherited pool from harvests before the project, which is the
simplest Tier 1 assumption and keeps the with / without comparison unaffected by pre-project harvests.
"""

import math
from dataclasses import dataclass

from .ghg_emissions_classes import ActivityTypes, Emission, GasTypes, YearlyGasActivityEmissionSet

SAWNWOOD = "sawnwood"
PANELS = "panels"
PAPER = "paper"
PRODUCTS = (SAWNWOOD, PANELS, PAPER)

DEFAULT_HALF_LIVES = {SAWNWOOD: 35.0, PANELS: 25.0, PAPER: 2.0}

C_TO_CO2 = 44 / 12


def decay_constant(half_life: float) -> float:
    if half_life <= 0:
        raise ValueError("HWP half-life must be greater than 0")
    return math.log(2) / half_life


def fod_stocks(inflow: list[float], half_life: float, initial_stock: float = 0.0) -> list[float]:
    """Stock at the end of each year (C(i+1) for i = 0..n-1) for a yearly carbon inflow, eq. 12.2."""
    k = decay_constant(half_life)
    retention = math.exp(-k)
    inflow_factor = (1 - retention) / k
    stocks = []
    stock = initial_stock
    for value in inflow:
        stock = retention * stock + inflow_factor * value
        stocks.append(stock)
    return stocks


@dataclass(frozen=True)
class HwpPool:
    """Yearly HWP pool output, all carbon in tC."""

    stock: dict[str, list[float]]
    stock_change: dict[str, list[float]]
    instant_oxidation: list[float]

    @property
    def total_stock(self) -> list[float]:
        return [sum(values) for values in zip(*self.stock.values())]

    def co2_by_product(self) -> dict[str, list[float]]:
        """tCO2 per year and product, positive = emission, negative = removal into the pool."""
        return {product: [-change * C_TO_CO2 for change in changes] for product, changes in self.stock_change.items()}

    @property
    def co2(self) -> list[float]:
        return [sum(values) for values in zip(*self.co2_by_product().values())]


def hwp_pool(inflow_tc: list[float], shares: dict[str, float], half_lives: dict[str, float] | None = None) -> HwpPool:
    """Split a yearly harvested carbon inflow (tC) into product pools and run the FOD model on each.

    ``shares`` are fractions (0-1) of the inflow going to each product in PRODUCTS; missing products count as 0.
    ``half_lives`` override DEFAULT_HALF_LIVES per product (Tier 2).
    """
    unknown = set(shares) - set(PRODUCTS)
    if unknown:
        raise ValueError(f"Unknown HWP products: {sorted(unknown)}")
    if any(share < 0 for share in shares.values()):
        raise ValueError("HWP product shares cannot be negative")
    total_share = sum(shares.values())
    if total_share > 1 + 1e-9:
        raise ValueError("HWP product shares cannot add up to more than 100%")

    half_lives = {**DEFAULT_HALF_LIVES, **(half_lives or {})}
    stock = {}
    stock_change = {}
    for product in PRODUCTS:
        share = shares.get(product, 0.0)
        stocks = fod_stocks([value * share for value in inflow_tc], half_lives[product])
        stock[product] = stocks
        stock_change[product] = [current - previous for previous, current in zip([0.0] + stocks[:-1], stocks)]

    instant = [value * (1 - total_share) for value in inflow_tc]
    return HwpPool(stock=stock, stock_change=stock_change, instant_oxidation=instant)


def hwp_pool_line(
    inflow_co2: list[float], shares: dict[str, float], half_lives: dict[str, float] | None, already_emitted: bool = True
) -> tuple[list[float], list[float]]:
    """Yearly HWP_POOL CO2 (tCO2, CRT 4.G) and end-of-year pool stock (tC) for a harvested carbon inflow given in tCO2.

    ``already_emitted=True``: the source module already books the inflow as an emission in the year of harvest (forest
    HWP_* lines, perennial biomass loss). Keeping those lines and adding -dC * 44/12 gives the net emission of the decay
    model, the same split CRT uses between 4.A (harvest loss) and 4.G (HWP pool change). Over a long horizon the pool
    empties and the line sums to 0.

    ``already_emitted=False``: the source never emits the inflow (wood harvested before a land use change is subtracted
    from the cleared biomass and was stored forever). The line then carries the whole fate of that carbon:
    (inflow - dC) * 44/12, i.e. the unshared part at once and the rest as it decays. Over a long horizon it sums to the
    inflow.
    """
    pool = hwp_pool([value / C_TO_CO2 for value in inflow_co2], shares, half_lives)
    co2 = pool.co2 if already_emitted else [inflow + change for inflow, change in zip(inflow_co2, pool.co2)]
    return co2, pool.total_stock


def hwp_pool_emission_set(
    inflow_co2: list[float], shares: dict[str, float], half_lives: dict[str, float] | None, delay: int = 0, already_emitted: bool = True
) -> YearlyGasActivityEmissionSet:
    """HWP_POOL result line for a yearly harvested carbon inflow given in tCO2 (see hwp_pool_line)."""
    co2, _stock = hwp_pool_line(inflow_co2, shares, half_lives, already_emitted)
    return co2_emission_set(co2, delay)


def co2_emission_set(co2: list[float], delay: int = 0) -> YearlyGasActivityEmissionSet:
    return YearlyGasActivityEmissionSet(
        year=0,
        gas_type=GasTypes.CO2,
        emissions=[Emission(value, GasTypes.CO2) for value in co2],
        activity=ActivityTypes.HWP_POOL,
        delay=delay,
    )
