import traceback

from .general_functions import (
    breakdown_proportionally_to_values,
    compute_half_year_cumulative_n_year_maturity,
    compute_yearly_or_half_year_cumulative,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)
from .ghg_inventory_class import InventoryPerGasPerActivity
from .generalized_modules import BaseModule
from dataclasses import dataclass
from typing import Optional

# Area already drained at project start is assumed to have been draining this long,
# so its soil carbon is that much closer to depletion.
PRE_PROJECT_DRAINAGE_YEARS = 20


@dataclass(kw_only=True)
class CoastalWetland(BaseModule):
    maximum_area_for_water_management: float
    area_drained_start: float
    area_drained_end: float
    agb_default: float
    bgb_default: float
    litter_default: float
    deadwood_default: float
    soil_1m_default: float
    EF_drainage_default: float
    agb_tier_2: Optional[float] = None
    bgb_tier_2: Optional[float] = None
    litter_tier_2: Optional[float] = None
    deadwood_tier_2: Optional[float] = None
    soil_1m_tier_2: Optional[float] = None
    EF_drainage_tier_2: Optional[float] = None
    area_excavated_start: float
    area_excavated_end: float
    area_revegated_start: float
    area_revegated_end: float
    percentage_c_lost_excavation_default: float
    percentage_c_lost_excavation_tier_2: Optional[float] = None
    ef_rewetting_carbon_default: float
    ef_rewetting_methane_default: float
    ef_rewetting_carbon_tier_2: Optional[float] = None
    ef_rewetting_methane_tier_2: Optional[float] = None
    methane_constant: float
    mangrove_factor: float

    def __post_init__(self):
        super().__post_init__()

        # Excavated land is handled by excavation alone, so drainage only counts drained land that is not excavated.
        # Clamped because AEX <= AD is only validated in the front end.
        self.net_drained_start = max(0, self.area_drained_start - self.area_excavated_start)
        self.net_drained_end = max(0, self.area_drained_end - self.area_excavated_end)
        self.newly_drained_area = max(0, self.net_drained_end - self.net_drained_start)

        # The net areas above imply that excavation takes land the project newly drains first, then land that
        # was already drained at the start. Excavation emissions follow the same split.
        newly_excavated_area = max(0, self.area_excavated_end - self.area_excavated_start)
        self.excavated_on_newly_drained = min(newly_excavated_area, max(0, self.area_drained_end - self.area_drained_start))
        self.excavated_on_pre_drained = newly_excavated_area - self.excavated_on_newly_drained

        self.hectares_drained = compute_yearly_or_half_year_cumulative(0, self.area_drained_end, self.implementation_time, self.capitalization_time, self.rate_type)

        self.hectares_revegetated_before_20, self.hectares_revegetated_after_20 = compute_half_year_cumulative_n_year_maturity(
            0, self.area_revegated_end, self.implementation_time, self.capitalization_time, self.rate_type
        )
        self.hectares_revegated = compute_yearly_or_half_year_cumulative(0, self.area_revegated_end, self.implementation_time, self.capitalization_time, self.rate_type)

        self.area_start_rewetting = max(0, -self.area_drained_end + self.area_drained_start)
        self.area_end_rewetting = max(0, -self.area_drained_end + self.area_drained_start)

        # TODO: ask Lorenzo about this variable and how it should be split across the years
        self.hectares_excavated = compute_yearly_or_half_year_cumulative(self.area_excavated_end - self.area_excavated_start, 0, self.implementation_time, self.capitalization_time, self.rate_type)

        # TIER 2 VALUES
        self.agb_tier_2_default = None
        self.bgb_tier_2_default = None

    def soil_stocks(self):
        """Return (soil_1m, EF_drainage, pre_drained_soil_1m): the full 1m stock, the drainage EF, and the stock
        left on land assumed to have drained for PRE_PROJECT_DRAINAGE_YEARS before the project."""
        soil_1m = self.soil_1m_default if self.soil_1m_tier_2 is None else self.soil_1m_tier_2
        EF_drainage = self.EF_drainage_default if self.EF_drainage_tier_2 is None else self.EF_drainage_tier_2
        pre_drained_soil_1m = max(0, soil_1m - PRE_PROJECT_DRAINAGE_YEARS * EF_drainage)
        return soil_1m, EF_drainage, pre_drained_soil_1m

    def calculate_emissions(
        self,
    ):
        def calculate_drainage():
            def calculate_biomass():
                try:
                    agb = self.agb_default * 0.451 if self.agb_tier_2 is None else self.agb_tier_2
                    bgb = self.bgb_default * agb if self.bgb_tier_2 is None else self.bgb_tier_2
                    litter = self.litter_default if self.litter_tier_2 is None else self.litter_tier_2
                    deadwood = self.deadwood_default if self.deadwood_tier_2 is None else self.deadwood_tier_2

                    # Drained land loses all its biomass. Land already drained at the start lost it before the
                    # project, so only the newly drained (and not excavated) area counts.
                    emissions_biomass_total_drainage = (agb + bgb + litter + deadwood) * self.newly_drained_area * (44 / 12)

                    emissions_biomass_yearly = breakdown_proportionally_to_values(emissions_biomass_total_drainage, self.hectares_drained)

                    biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_biomass_yearly], ActivityTypes.BIOMASS, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

                    inventory = InventoryPerGasPerActivity(gas_type=GasTypes.CO2, value=0, activity=ActivityTypes.BIOMASS)
                    self.inventory.emissions_by_sector_by_gas.append(inventory)

                except Exception as e:
                    traceback.print_exc()
                    pass

            def calculate_soil():
                try:
                    soil_1m, EF_drainage, pre_drained_soil_1m = self.soil_stocks()

                    maximum_soil_years = 1000 if EF_drainage == 0 else int(soil_1m / EF_drainage)
                    pre_drained_soil_years = max(0, maximum_soil_years - PRE_PROJECT_DRAINAGE_YEARS)

                    # Each hectare emits EF_drainage per year until its 1m stock is gone. Two cohorts, because they
                    # have different stocks left: area drained before the project (partly depleted, present from
                    # year 0, shrinks when rewetted or excavated) and area newly drained by the project (full stock,
                    # ramps in).
                    timing = (self.implementation_time, self.capitalization_time, self.rate_type)

                    pre_drained_emitting, _ = compute_half_year_cumulative_n_year_maturity(
                        self.net_drained_start, min(self.net_drained_start, self.net_drained_end), *timing, number_of_years=pre_drained_soil_years
                    )
                    newly_drained_emitting, _ = compute_half_year_cumulative_n_year_maturity(0, self.newly_drained_area, *timing, number_of_years=maximum_soil_years)
                    drainage_before_n_years = [a + b for a, b in zip(pre_drained_emitting, newly_drained_emitting)]

                    calculated = EF_drainage * 44 / 12 * sum(drainage_before_n_years)
                    maximum = (self.net_drained_start * pre_drained_soil_1m + self.newly_drained_area * soil_1m) * 44 / 12

                    total = calculated if abs(calculated) < abs(maximum) else maximum

                    emissions_soil_yearly_drainage = breakdown_proportionally_to_values(total, drainage_before_n_years)

                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_soil_yearly_drainage], ActivityTypes.DRAINAGE, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)
                    inventory = InventoryPerGasPerActivity(gas_type=GasTypes.CO2, value=0, activity=ActivityTypes.DRAINAGE)
                    self.inventory.emissions_by_sector_by_gas.append(inventory)

                except Exception as e:
                    traceback.print_exc()
                    pass

            calculate_biomass()
            calculate_soil()

        def calculate_extraction_excavation():
            try:
                agb = self.agb_default * 0.451 if self.agb_tier_2 is None else self.agb_tier_2
                bgb = self.bgb_default * agb if self.bgb_tier_2 is None else self.bgb_tier_2
                litter = self.litter_default if self.litter_tier_2 is None else self.litter_tier_2
                deadwood = self.deadwood_default if self.deadwood_tier_2 is None else self.deadwood_tier_2
                soil_1m, _, pre_drained_soil_1m = self.soil_stocks()
                percentage_c_lost_excavation = self.percentage_c_lost_excavation_default if self.percentage_c_lost_excavation_tier_2 is None else self.percentage_c_lost_excavation_tier_2

                biomass_c = agb + bgb + litter + deadwood
                soil_c = soil_1m * percentage_c_lost_excavation

                biomass_co2 = biomass_c * 44 / 12
                soil_co2 = soil_c * 44 / 12

                # Land already drained at the start has no biomass left and a depleted soil stock (see drainage).
                total_biomass = biomass_co2 * self.excavated_on_newly_drained
                total_soil = percentage_c_lost_excavation * 44 / 12 * (
                    self.excavated_on_newly_drained * soil_1m + self.excavated_on_pre_drained * pre_drained_soil_1m
                )

                emissions_yearly_biomass_extraction_excavation = breakdown_proportionally_to_values(total_biomass, self.hectares_excavated)
                emissions_yearly_soil_extraction_excavation = breakdown_proportionally_to_values(total_soil, self.hectares_excavated)

                biomass_emission_set = YearlyGasActivityEmissionSet(
                    0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_yearly_biomass_extraction_excavation], ActivityTypes.BIOMASS, delay=self.delay
                )
                self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)
                soil_emission_set = YearlyGasActivityEmissionSet(
                    0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_yearly_soil_extraction_excavation], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay
                )
                self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

                inventory_biomass = InventoryPerGasPerActivity(gas_type=GasTypes.CO2, value=biomass_co2, activity=ActivityTypes.BIOMASS)
                inventory_soil = InventoryPerGasPerActivity(gas_type=GasTypes.CO2, value=soil_co2, activity=ActivityTypes.SOIL_CO2_CHANGE)
                self.inventory.emissions_by_sector_by_gas.append(inventory_biomass)
                self.inventory.emissions_by_sector_by_gas.append(inventory_soil)
                pass
            except Exception as e:
                traceback.print_exc()
                pass
            pass

        def calculate_rewetting_revegetation():
            def calculate_biomass():
                try:
                    agb = self.agb_default * self.mangrove_factor if self.agb_tier_2 is None else self.agb_tier_2
                    bgb = self.bgb_default * agb if self.bgb_tier_2 is None else self.bgb_tier_2
                    litter = self.litter_default if self.litter_tier_2 is None else self.litter_tier_2
                    deadwood = self.deadwood_default if self.deadwood_tier_2 is None else self.deadwood_tier_2

                    # ASSIGN TIER 2 VALUE DEFAULT FOR FRONT END, AS IT'S IN TONNES OF CARBON
                    self.agb_tier_2_default = self.agb_default * self.mangrove_factor
                    self.bgb_tier_2_default = self.bgb_default * agb if self.agb_tier_2 is None else self.bgb_default * self.agb_tier_2

                    biomass_emissions_total = -44 / 12 * (agb + bgb + litter + deadwood) / (20) * sum(self.hectares_revegetated_before_20)

                    yearly_biomass = breakdown_proportionally_to_values(biomass_emissions_total, self.hectares_revegetated_before_20)

                    return yearly_biomass

                except Exception as e:
                    traceback.print_exc()
                    raise e

            try:
                # IPCC Wetlands Supplement, ch. 4 p. 4.28: at Tier 1 the rewetting CO2 factor applies only where
                # vegetation is re-established by replanting or reseeding; rewetting alone or natural recolonization
                # gets 0. A Tier 2 factor is the user's own estimate (e.g. for natural recolonization), so it applies
                # to the whole rewetted area. CH4 applies to the whole rewetted area either way.
                if self.ef_rewetting_carbon_tier_2 is None:
                    ef_rewetting_carbon = self.ef_rewetting_carbon_default
                    rewetting_carbon_area = min(max(0, self.area_revegated_end), self.area_end_rewetting)
                else:
                    ef_rewetting_carbon = self.ef_rewetting_carbon_tier_2
                    rewetting_carbon_area = self.area_end_rewetting
                ef_rewetting_methane = self.ef_rewetting_methane_default if self.ef_rewetting_methane_tier_2 is None else self.ef_rewetting_methane_tier_2

                emissions_yearly_rewetting_carbon = compute_yearly_or_half_year_cumulative(
                    0, 44 / 12 * rewetting_carbon_area * ef_rewetting_carbon, self.implementation_time, self.capitalization_time, self.rate_type
                )
                emissions_yearly_rewetting_methane = compute_yearly_or_half_year_cumulative(
                    0, self.methane_constant * self.area_end_rewetting * ef_rewetting_methane / 1000, self.implementation_time, self.capitalization_time, self.rate_type
                )

                total_emission_yearly_rewetting_carbon = sum(emissions_yearly_rewetting_carbon)
                total_emission_yearly_rewetting_methane = sum(emissions_yearly_rewetting_methane)

                emissions_total_rewetting = total_emission_yearly_rewetting_carbon + total_emission_yearly_rewetting_methane

                rewetting_emission_set = YearlyGasActivityEmissionSet(
                    0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_yearly_rewetting_carbon], ActivityTypes.REWETTING_REVEGETATION, delay=self.delay
                )
                self.result.yearly_emissions_by_sector_by_gas.append(rewetting_emission_set)

                rewetting_emission_set = YearlyGasActivityEmissionSet(
                    0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in emissions_yearly_rewetting_methane], ActivityTypes.REWETTING_REVEGETATION, delay=self.delay
                )
                self.result.yearly_emissions_by_sector_by_gas.append(rewetting_emission_set)

                biomass_emissions = calculate_biomass()
                biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in biomass_emissions], ActivityTypes.BIOMASS, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CO2, 0, ActivityTypes.REWETTING_REVEGETATION))
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CH4, 0, ActivityTypes.REWETTING_REVEGETATION))
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CO2, 0, ActivityTypes.BIOMASS))

            except Exception as e:
                traceback.print_exc()
                pass

        calculate_drainage()
        calculate_extraction_excavation()
        calculate_rewetting_revegetation()
