"""CH4 and N2O from food-processing wastewater (CRT 5.D.2, industrial wastewater).

CH4, 2006 IPCC Guidelines Vol. 5 ch. 6 (unchanged in the 2019 Refinement):
    TOW = P * W * COD                                   (eq. 6.6)
    CH4 = sum_j T_j * (TOW - S) * Bo * MCF_j - R        (eq. 6.4 and 6.5, EF a share-weighted average)
N2O, 2019 Refinement Vol. 5 ch. 6:
    TN = P * W * TN_conc                                (eq. 6.13)
    N2O plants = sum_j T_j * EF_plant_j * TN * 44/28    (eq. 6.11, EF Table 6.8A)
    N effluent = sum_j T_j * (1 - Nrem_j) * TN          (eq. 6.14, Nrem Table 6.10c)
    N2O effluent = N effluent * EF_effluent * 44/28     (eq. 6.12, EF Table 6.8A)

A scenario's annual emissions are computed at its start and end values and interpolated with the activity's change
rate, as the other non-land modules do.
"""

from dataclasses import dataclass, field
from typing import Optional

from .general_functions import compute_yearly_or_half_year_cumulative
from .generalized_modules import BaseModule
from .ghg_emissions_classes import ActivityTypes, Emission, GasTypes, YearlyGasActivityEmissionSet
from .ghg_inventory_class import InventoryPerGasPerActivity

BO_COD = 0.25  # kg CH4 / kg COD, 2006 Vol. 5 Table 6.2
EF_N2O_EFFLUENT = 0.005  # kg N2O-N / kg N, 2019 Refinement Vol. 5 Table 6.8A, Tier 1 discharge
N2O_N_TO_N2O = 44 / 28


@dataclass(frozen=True)
class TreatmentShare:
    share: float
    mcf: float
    ef_n2o_plant: float
    n_removal: float


@dataclass(frozen=True)
class ScenarioInputs:
    production: float  # t product / yr
    wastewater: float  # m3 / t product
    cod: float  # kg COD / m3
    total_n: Optional[float]  # kg N / m3; None when IPCC gives no default and no Tier 2 value is set
    treatment: list[TreatmentShare] = field(default_factory=list)
    sludge_removed: float = 0.0  # kg COD / yr
    ch4_recovered: float = 0.0  # kg CH4 / yr


def annual_emissions(inputs: ScenarioInputs) -> tuple[float, float]:
    """(t CH4 / yr, t N2O / yr) for one scenario state."""
    volume = inputs.production * inputs.wastewater
    organics = max(volume * inputs.cod - inputs.sludge_removed, 0.0)
    ch4 = sum(t.share * organics * BO_COD * t.mcf for t in inputs.treatment) - inputs.ch4_recovered

    nitrogen = volume * (inputs.total_n or 0.0)
    plant = sum(t.share * t.ef_n2o_plant for t in inputs.treatment) * nitrogen
    effluent = sum(t.share * (1 - t.n_removal) for t in inputs.treatment) * nitrogen * EF_N2O_EFFLUENT
    return max(ch4, 0.0) / 1000, (plant + effluent) * N2O_N_TO_N2O / 1000


@dataclass(kw_only=True)
class FoodWastewater(BaseModule):
    start: ScenarioInputs
    end: ScenarioInputs
    gwp_ch4: float
    gwp_n2o: float

    def calculate_emissions(self):
        ch4_start, n2o_start = annual_emissions(self.start)
        ch4_end, n2o_end = annual_emissions(self.end)
        lines = (
            (ActivityTypes.FOOD_WASTEWATER_CH4, GasTypes.CH4, ch4_start * self.gwp_ch4, ch4_end * self.gwp_ch4),
            (ActivityTypes.FOOD_WASTEWATER_N2O, GasTypes.N2O, n2o_start * self.gwp_n2o, n2o_end * self.gwp_n2o),
        )
        for activity, gas, start, end in lines:
            yearly = compute_yearly_or_half_year_cumulative(start, end, self.implementation_time, self.capitalization_time, self.rate_type)
            self.result.yearly_emissions_by_sector_by_gas.append(
                YearlyGasActivityEmissionSet(0, gas, [Emission(e, gas) for e in yearly], activity, delay=self.delay)
            )
            self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(gas, start, activity))
