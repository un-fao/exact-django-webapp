"""Solid waste: disposal on land, biological treatment, incineration and open burning.

Sources (2006 IPCC Guidelines, Vol. 5, with the 2019 Refinement where it updated a value):

- Solid waste disposal sites (SWDS), ch. 3, first-order decay (FOD), per waste type j and site type s:
      DDOCm_d(T)  = W(T) * DOC_j * DOCf * MCF_s                       (eq. 3.2)
      DDOCm_a(T)  = DDOCm_d(T) + DDOCm_a(T-1) * e^-k_j                 (eq. 3.4)
      decomp(T)   = DDOCm_a(T-1) * (1 - e^-k_j)                        (eq. 3.5)
      CH4 gen(T)  = decomp(T) * F * 16/12                              (eq. 3.6)
      CH4 emit(T) = (CH4 gen(T) - R(T)) * (1 - OX_s)                   (eq. 3.1)
  The reaction starts on 1 January of the year after disposal (default six-month delay, section 3.2.3 and
  Annex 3A.1, M = 13), so waste deposited in year T decomposes from T+1. DOCf = 0.5 and F = 0.5 (section 3.2.3).
  R is given as a fraction of the generated CH4. Waste deposited before the project start is not modelled: it is the
  same in the with and without scenarios, so it cancels out of the balance.
- Biological treatment, ch. 4, eq. 4.1 and 4.2: CH4 = M * EF_CH4 * 1e-3 - R, N2O = M * EF_N2O * 1e-3
  (EF in g per kg wet waste, Table 4.1). R is given as a fraction of the CH4 computed with the EF.
- Incineration and open burning, ch. 5: fossil CO2 = sum_j M_j * dm_j * CF_j * FCF_j * OF * 44/12 (eq. 5.2),
  biogenic CO2 is not counted. CH4 = M * EF (eq. 5.4), N2O = M * EF (eq. 5.5); open burning N2O is per tonne of dry
  matter (Table 5.6).

Every mass flow interpolates from the start to the end of the implementation phase with the activity's dynamic, like
the other non-land modules: the start value is amount * composition share * route share with the start-scenario
inputs, the end value the same with the with / without inputs.
"""

import math
from dataclasses import dataclass, field

from .general_functions import compute_yearly_or_half_year_cumulative
from .generalized_modules import BaseModule
from .ghg_emissions_classes import ActivityTypes, Emission, GasTypes, YearlyGasActivityEmissionSet
from .ghg_inventory_class import InventoryPerGasPerActivity

WASTE_TYPES = ("food", "garden", "paper", "wood", "textiles", "nappies", "rubber_leather", "plastics", "metal", "glass", "other")

SWDS_ROUTES = (
    "swds_managed_anaerobic",
    "swds_managed_semi_aerobic",
    "swds_unmanaged_deep",
    "swds_unmanaged_shallow",
    "swds_uncategorised",
    "open_dumping",
)
COMPOSTING = "composting"
ANAEROBIC_DIGESTION = "anaerobic_digestion"
INCINERATION = "incineration"
OPEN_BURNING = "open_burning"
OTHER_ROUTE = "other"
ROUTES = SWDS_ROUTES + (COMPOSTING, ANAEROBIC_DIGESTION, INCINERATION, OPEN_BURNING, OTHER_ROUTE)

# Route groups of the food-waste block read by the food-waste indicators; all SWDS types and open dumping are "swds".
FOOD_WASTE_ROUTE_GROUPS = ("swds", COMPOSTING, ANAEROBIC_DIGESTION, INCINERATION, OPEN_BURNING, OTHER_ROUTE)

DOCF = 0.5
F_CH4 = 0.5
C_TO_CH4 = 16 / 12
C_TO_CO2 = 44 / 12


@dataclass(frozen=True)
class WasteComponentFactors:
    """Table 2.4 values as fractions, plus the Table 3.3 decay rate k (1/yr) for the site's climate zone."""

    doc: float
    dry_matter: float
    carbon: float
    fossil_carbon: float
    k: float


@dataclass(frozen=True)
class TreatmentFactors:
    """Emission factors for one scenario end (Tier 1 or Tier 2 overrides).

    composting / AD: g gas per kg wet waste; incineration and open burning CH4: g per t wet waste;
    incineration N2O: g per t wet waste; open burning N2O: g per t dry matter; oxidation factors as fractions.
    """

    composting_ch4: float
    composting_n2o: float
    ad_ch4: float
    incineration_ch4: float
    incineration_n2o: float
    incineration_of: float
    open_burning_ch4: float
    open_burning_n2o: float
    open_burning_of: float


def first_order_decay(deposited: list[float], k: float) -> list[float]:
    """DDOCm decomposed in each year for a series of yearly DDOCm deposits, eq. 3.4 and 3.5 (M = 13)."""
    retention = math.exp(-k)
    accumulated = 0.0
    decomposed = []
    for value in deposited:
        decomposed.append(accumulated * (1 - retention))
        accumulated = accumulated * retention + value
    return decomposed


def route_masses(amount: float, composition: dict[str, float], routes: dict[str, float]) -> dict[str, dict[str, float]]:
    """Tonnes of wet waste per route and waste type in one year."""
    return {route: {waste: amount * composition.get(waste, 0.0) * routes.get(route, 0.0) for waste in WASTE_TYPES} for route in ROUTES}


@dataclass(kw_only=True)
class SolidWaste(BaseModule):
    """One scenario (start -> with, or start -> without) of a solid waste stream. Masses in t wet weight per year."""

    amount_start: float
    amount_end: float
    composition_start: dict[str, float]
    composition_end: dict[str, float]
    routes_start: dict[str, float]
    routes_end: dict[str, float]
    swds_recovery_start: float = 0.0
    swds_recovery_end: float = 0.0
    ad_recovery_start: float = 0.0
    ad_recovery_end: float = 0.0
    components: dict[str, WasteComponentFactors]
    mcf: dict[str, float]
    ox: dict[str, float]
    factors_start: TreatmentFactors
    factors_end: TreatmentFactors
    gwp_ch4: float
    gwp_n2o: float
    food_waste_by_route: dict[str, list[float]] = field(default_factory=dict)

    def _series(self, start: float, end: float) -> list[float]:
        return compute_yearly_or_half_year_cumulative(start, end, self.implementation_time, self.capitalization_time, self.rate_type)

    def _add(self, activity: ActivityTypes, gas: GasTypes, series: list[float], start_value: float) -> None:
        self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(0, gas, [Emission(value, gas) for value in series], activity, delay=self.delay))
        self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(gas, start_value, activity))

    def calculate_emissions(self) -> None:
        start = route_masses(self.amount_start, self.composition_start, self.routes_start)
        end = route_masses(self.amount_end, self.composition_end, self.routes_end)

        self._food_waste(start, end)
        self._swds(start, end)
        self._biological(start, end)
        self._combustion(start, end, INCINERATION, ActivityTypes.WASTE_INCINERATION)
        self._combustion(start, end, OPEN_BURNING, ActivityTypes.WASTE_OPEN_BURNING)

    def _food_waste(self, start, end) -> None:
        groups = {group: [0.0] * (self.implementation_time + self.capitalization_time) for group in FOOD_WASTE_ROUTE_GROUPS}
        for route in ROUTES:
            group = "swds" if route in SWDS_ROUTES else route
            series = self._series(start[route]["food"], end[route]["food"])
            groups[group] = [a + b for a, b in zip(groups[group], series)]
        self.food_waste_by_route = {group: [0.0] * self.delay + values for group, values in groups.items()}

    def _swds(self, start, end) -> None:
        recovery = self._series(self.swds_recovery_start, self.swds_recovery_end)
        emitted = [0.0] * len(recovery)
        steady_state_start = 0.0
        for route in SWDS_ROUTES:
            for waste, factors in self.components.items():
                ddocm_per_t = factors.doc * DOCF * self.mcf[route]
                if ddocm_per_t == 0:
                    continue
                deposited = [mass * ddocm_per_t for mass in self._series(start[route][waste], end[route][waste])]
                decomposed = first_order_decay(deposited, factors.k) if factors.k > 0 else [0.0] * len(deposited)
                emitted = [e + d * F_CH4 * C_TO_CH4 * (1 - r) * (1 - self.ox[route]) for e, d, r in zip(emitted, decomposed, recovery)]
                if factors.k > 0:
                    # A constant deposit decomposes at the rate it is deposited once the FOD stock is in equilibrium.
                    steady_state_start += start[route][waste] * ddocm_per_t * F_CH4 * C_TO_CH4 * (1 - self.swds_recovery_start) * (1 - self.ox[route])
        self._add(ActivityTypes.SOLID_WASTE_DISPOSAL, GasTypes.CH4, [value * self.gwp_ch4 for value in emitted], steady_state_start * self.gwp_ch4)

    def _biological(self, start, end) -> None:
        def total(masses, route):
            return sum(masses[route].values())

        compost_start, compost_end = total(start, COMPOSTING), total(end, COMPOSTING)
        ad_start, ad_end = total(start, ANAEROBIC_DIGESTION), total(end, ANAEROBIC_DIGESTION)
        fs, fe = self.factors_start, self.factors_end

        lines = (
            (ActivityTypes.COMPOSTING, GasTypes.CH4, compost_start * fs.composting_ch4 * 1e-3 * self.gwp_ch4, compost_end * fe.composting_ch4 * 1e-3 * self.gwp_ch4),
            (ActivityTypes.COMPOSTING, GasTypes.N2O, compost_start * fs.composting_n2o * 1e-3 * self.gwp_n2o, compost_end * fe.composting_n2o * 1e-3 * self.gwp_n2o),
            (
                ActivityTypes.ANAEROBIC_DIGESTION,
                GasTypes.CH4,
                ad_start * fs.ad_ch4 * 1e-3 * (1 - self.ad_recovery_start) * self.gwp_ch4,
                ad_end * fe.ad_ch4 * 1e-3 * (1 - self.ad_recovery_end) * self.gwp_ch4,
            ),
        )
        for activity, gas, value_start, value_end in lines:
            self._add(activity, gas, self._series(value_start, value_end), value_start)

    def _combustion(self, start, end, route: str, activity: ActivityTypes) -> None:
        def per_scenario(masses, f: TreatmentFactors):
            wet = sum(masses[route].values())
            dry = sum(masses[route][waste] * c.dry_matter for waste, c in self.components.items())
            of = f.incineration_of if route == INCINERATION else f.open_burning_of
            fossil_co2 = sum(masses[route][waste] * c.dry_matter * c.carbon * c.fossil_carbon for waste, c in self.components.items()) * of * C_TO_CO2
            if route == INCINERATION:
                ch4, n2o = wet * f.incineration_ch4 * 1e-6, wet * f.incineration_n2o * 1e-6
            else:
                ch4, n2o = wet * f.open_burning_ch4 * 1e-6, dry * f.open_burning_n2o * 1e-6
            return {GasTypes.CO2: fossil_co2, GasTypes.CH4: ch4 * self.gwp_ch4, GasTypes.N2O: n2o * self.gwp_n2o}

        values_start = per_scenario(start, self.factors_start)
        values_end = per_scenario(end, self.factors_end)
        for gas in (GasTypes.CO2, GasTypes.CH4, GasTypes.N2O):
            self._add(activity, gas, self._series(values_start[gas], values_end[gas]), values_start[gas])
