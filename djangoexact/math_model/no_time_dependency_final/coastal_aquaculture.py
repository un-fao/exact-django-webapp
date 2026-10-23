"""Aquaculture ponds on coastal wetland land: pond CH4 and fish N2O.

CH4: IPCC 2019 Refinement, Vol. 4 Ch. 7, Equation 7.12 with Table 7.12 EFs (other constructed
waterbodies: saline ponds > 18 ppt, freshwater and brackish ponds) and the trophic state
adjustment factor alpha of Table 7.11.
N2O: 2013 Wetlands Supplement, Ch. 4, Table 4.15 (kg N2O-N per kg of fish produced).
"""

from dataclasses import dataclass

from .general_functions import compute_yearly_or_half_year_cumulative
from .generalized_modules import BaseModule
from .ghg_emissions_classes import ActivityTypes, Emission, GasTypes, YearlyGasActivityEmissionSet
from .ghg_inventory_class import InventoryPerGasPerActivity

N2O_N_TO_N2O = 44 / 28


def pond_ch4(area: float, ef_ch4: float, alpha: float, gwp_ch4: float) -> float:
    """Annual pond CH4 in tCO2-eq: ha x kg CH4/ha/yr x alpha."""
    return area * ef_ch4 * alpha / 1000 * gwp_ch4


def fish_n2o(area: float, fish_production: float, ef_n2o: float, gwp_n2o: float) -> float:
    """Annual fish N2O in tCO2-eq: ha x kg fish/ha/yr x kg N2O-N/kg fish."""
    return area * fish_production * ef_n2o / 1000 * N2O_N_TO_N2O * gwp_n2o


@dataclass(kw_only=True)
class CoastalAquaculturePonds(BaseModule):
    pond_area_start: float
    pond_area_end: float
    ef_ch4_start: float
    ef_ch4_end: float
    alpha_start: float
    alpha_end: float
    fish_production_start: float
    fish_production_end: float
    ef_n2o_start: float
    ef_n2o_end: float
    gwp_ch4: float
    gwp_n2o: float

    def calculate_emissions(self):
        ch4_start = pond_ch4(self.pond_area_start, self.ef_ch4_start, self.alpha_start, self.gwp_ch4)
        ch4_end = pond_ch4(self.pond_area_end, self.ef_ch4_end, self.alpha_end, self.gwp_ch4)
        n2o_start = fish_n2o(self.pond_area_start, self.fish_production_start, self.ef_n2o_start, self.gwp_n2o)
        n2o_end = fish_n2o(self.pond_area_end, self.fish_production_end, self.ef_n2o_end, self.gwp_n2o)

        # Same activity labels as the Waterbody (pond CH4) and Aquaculture (fish N2O) modules.
        for gas, activity, start, end in (
            (GasTypes.CH4, ActivityTypes.COASTAL_WATERBODIES, ch4_start, ch4_end),
            (GasTypes.N2O, ActivityTypes.N20_FIELD, n2o_start, n2o_end),
        ):
            yearly = compute_yearly_or_half_year_cumulative(start, end, self.implementation_time, self.capitalization_time, self.rate_type)
            self.result.yearly_emissions_by_sector_by_gas.append(
                YearlyGasActivityEmissionSet(0, gas, [Emission(e, gas) for e in yearly], activity, delay=self.delay)
            )
            self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(gas, start, activity))
