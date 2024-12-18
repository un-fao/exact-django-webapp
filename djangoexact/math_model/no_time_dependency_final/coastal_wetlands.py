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

from .generalized_modules import LandModule, BaseModule
from dataclasses import dataclass
from typing import Optional

@dataclass
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
    agb_tier_2: Optional[float]
    bgb_tier_2: Optional[float]
    litter_tier_2: Optional[float]
    deadwood_tier_2: Optional[float]
    soil_1m_tier_2: Optional[float]
    EF_drainage_tier_2: Optional[float]
    area_excavated_start: float
    area_excavated_end: float
    area_revegated_start: float
    area_revegated_end: float
    percentage_c_lost_excavation_default: float
    percentage_c_lost_excavation_tier_2: Optional[float]
    ef_rewetting_carbon_default: float
    ef_rewetting_methane_default: float
    ef_rewetting_carbon_tier_2: Optional[float]
    ef_rewetting_methane_tier_2: Optional[float]
    soil_type: float
    methane_constant: float
    mangrove_factor: float

    def __post_init__(self):
        super().__post_init__()

        # HECTARES DRAINED
        # NOTE: set to 0 and self.area_drained_end - self.area_excavated_end as if not we have double counting. No need for checks as area_drained_end is always greater than area_excavated_end
        self.hectares_drained_before_20, self.hectares_drained_after_20 = compute_half_year_cumulative_n_year_maturity(0, self.area_drained_end - self.area_excavated_end, self.implementation_time, self.capitalization_time, self.rate_type)
        self.hectares_drained = compute_yearly_or_half_year_cumulative(0, self.area_drained_end, self.implementation_time, self.capitalization_time, self.rate_type)

        self.hectares_revegetated_before_20, self.hectares_revegetated_after_20 = compute_half_year_cumulative_n_year_maturity(0, self.area_revegated_end, self.implementation_time, self.capitalization_time, self.rate_type)
        self.hectares_revegated = compute_yearly_or_half_year_cumulative(0, self.area_revegated_end, self.implementation_time, self.capitalization_time, self.rate_type)
        
        self.area_start_rewetting = 0 if self.area_drained_start == 0 else max(0, -self.area_drained_end + self.area_drained_start)
        self.area_end_rewetting = 0 if self.area_drained_end == 0 else max(0, -self.area_drained_end + self.area_drained_start)

        # TODO: ask Lorenzo about this variable and how it should be split across the years
        self.hectares_excavated = compute_yearly_or_half_year_cumulative(self.area_excavated_end - self.area_excavated_start, 0, self.implementation_time, self.capitalization_time, self.rate_type)

        # TIER 2 VALUES
        self.agb_tier_2_default = None
        self.bgb_tier_2_default = None
    

    def calculate_emissions(
        self,
    ):
        def calculate_drainage():
            def calculate_biomass():
                try:
                    agb = self.agb_default * 0.451 if not self.agb_tier_2 else self.agb_tier_2
                    bgb = self.bgb_default * agb if not self.bgb_tier_2 else self.bgb_tier_2
                    litter = self.litter_default if not self.litter_tier_2 else self.litter_tier_2
                    deadwood = self.deadwood_default if not self.deadwood_tier_2 else self.deadwood_tier_2

                    # TODO: ask Lorenzo about this variable, should it be 0? Should it be calculated?
                    stock_c_biomass_start = 0
                    area_drained_end = self.area_drained_end
                    # NOT USED IN THE EXCEL, TODO: ask Lorenzo
                    area_drained_start = self.area_drained_start

                    stock_c_biomass_end = (agb + bgb + litter + deadwood) * area_drained_end

                    emissions_biomass_total_drainage = (stock_c_biomass_start - stock_c_biomass_end) * (44 / 12)

                    # soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.emissions_soil_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                    # self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

                    emissions_biomass_yearly = breakdown_proportionally_to_values(emissions_biomass_total_drainage, self.hectares_drained)

                    biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_biomass_yearly], ActivityTypes.BIOMASS, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

                except Exception as e:
                    traceback.print_exc()
                    pass

            def calculate_soil():
                try:
                    soil_1m = self.soil_1m_default if not self.soil_1m_tier_2 else self.soil_1m_tier_2
                    EF_drainage = self.EF_drainage_default if not self.EF_drainage_tier_2 else self.EF_drainage_tier_2

                    maximum_soil_years = 1000 if EF_drainage == 0 else int(soil_1m / EF_drainage)
                    maximum_soil_emissions = soil_1m * 44 / 12

                    drainage_before_n_years, drainage_after_n_years = compute_half_year_cumulative_n_year_maturity(0, 
                                                                                                              self.area_drained_end, 
                                                                                                              self.implementation_time, 
                                                                                                              self.capitalization_time, 
                                                                                                              self.rate_type, 
                                                                                                              number_of_years=maximum_soil_years)

                    # NOTE: This is different to what is done in the excel, however I think it is correct this way. If we were to do it like the excel
                    # we would have to recalculate the hectares according to min(maximum_soil_years, self.implementation_time + self.capitalization_time)
                    # and multiply by sum(that) instead of what we are doing now

                    # The NOTE above is kept for future reference, however the approach was changed. Now we calculate similarly to SOC emissions, as each single 
                    # piece of land can generate emissions only for a maximum years given by the the maximum_soil_years parameter, after that the emissions are not 
                    # generated anymore.

                    calculated = EF_drainage * 44 / 12 * sum(drainage_before_n_years)
                    maximum = max(0, self.area_drained_end) * maximum_soil_emissions

                    total = calculated if abs(calculated) < abs(maximum) else maximum

                    emissions_soil_yearly_drainage = breakdown_proportionally_to_values(total, drainage_before_n_years)

                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_soil_yearly_drainage], ActivityTypes.DRAINAGE, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

                except Exception as e:
                    traceback.print_exc()
                    pass

            calculate_biomass()
            calculate_soil()

        def calculate_extraction_excavation():
            try:
                # THIS VARIABLE IS SET TO 0 AS DEFAULT ON THE EXCEL, ASK LORENZO
                area_excavated_start = self.area_excavated_start

                area_excavated = self.area_excavated_end

                agb = self.agb_default * 0.451 if not self.agb_tier_2 else self.agb_tier_2
                bgb = self.bgb_default * agb if not self.bgb_tier_2 else self.bgb_tier_2
                litter = self.litter_default if not self.litter_tier_2 else self.litter_tier_2
                deadwood = self.deadwood_default if not self.deadwood_tier_2 else self.deadwood_tier_2
                soil_1m = self.soil_1m_default if not self.soil_1m_tier_2 else self.soil_1m_tier_2
                percentage_c_lost_excavation = self.percentage_c_lost_excavation_default if not self.percentage_c_lost_excavation_tier_2 else self.percentage_c_lost_excavation_tier_2

                biomass_c = agb + bgb + litter + deadwood
                soil_c = soil_1m * percentage_c_lost_excavation

                biomass_co2 = biomass_c * 44 / 12
                soil_co2 = soil_c * 44 / 12

                total = (biomass_co2 + soil_co2) * (area_excavated - area_excavated_start)

                total_biomass = biomass_co2 * (area_excavated - area_excavated_start)
                total_soil = soil_co2 * (area_excavated - area_excavated_start)

                emissions_yearly_biomass_extraction_excavation = breakdown_proportionally_to_values(total_biomass, self.hectares_excavated)
                emissions_yearly_soil_extraction_excavation = breakdown_proportionally_to_values(total_soil, self.hectares_excavated)

                biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_yearly_biomass_extraction_excavation], ActivityTypes.BIOMASS, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

                soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_yearly_soil_extraction_excavation], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

                pass
            except Exception as e:
                traceback.print_exc()
                pass
            pass

        def calculate_rewetting_revegetation():

            def calculate_biomass():
                try:
                    agb = self.agb_default * self.mangrove_factor if not self.agb_tier_2 else self.agb_tier_2
                    bgb = self.bgb_default * agb if not self.bgb_tier_2 else self.bgb_tier_2
                    litter = self.litter_default if not self.litter_tier_2 else self.litter_tier_2
                    deadwood = self.deadwood_default if not self.deadwood_tier_2 else self.deadwood_tier_2

                    # ASSIGN TIER 2 VALUE DEFAULT FOR FRONT END, AS IT'S IN TONNES OF CARBON
                    self.agb_tier_2_default = self.agb_default * self.mangrove_factor
                    self.bgb_tier_2_default = self.bgb_default * agb * self.mangrove_factor if not self.agb_tier_2 else self.bgb_default * self.agb_tier_2

                    biomass_emissions_total = -44/12 * (agb + bgb + litter + deadwood) / (20) * sum(self.hectares_revegetated_before_20)

                    yearly_biomass = breakdown_proportionally_to_values(biomass_emissions_total, self.hectares_revegetated_before_20)

                    return yearly_biomass

                except Exception as e:
                    traceback.print_exc()
                    raise e
            
            try:
                self.ef_rewetting_methane_default = 0 if not self.soil_type == "<18" else self.ef_rewetting_methane_default
                ef_rewetting_carbon = self.ef_rewetting_carbon_default if not self.ef_rewetting_carbon_tier_2 else self.ef_rewetting_carbon_tier_2
                ef_rewetting_methane = self.ef_rewetting_methane_default if not self.ef_rewetting_methane_tier_2 else self.ef_rewetting_methane_tier_2

                emissions_yearly_rewetting_carbon = compute_yearly_or_half_year_cumulative(0, 44 / 12 * self.area_end_rewetting * ef_rewetting_carbon, self.implementation_time, self.capitalization_time, self.rate_type)
                emissions_yearly_rewetting_methane = compute_yearly_or_half_year_cumulative(0, self.methane_constant * self.area_end_rewetting * ef_rewetting_methane / 1000, self.implementation_time, self.capitalization_time, self.rate_type)

                total_emission_yearly_rewetting_carbon = sum(emissions_yearly_rewetting_carbon)
                total_emission_yearly_rewetting_methane = sum(emissions_yearly_rewetting_methane)

                emissions_total_rewetting = total_emission_yearly_rewetting_carbon + total_emission_yearly_rewetting_methane

                rewetting_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_yearly_rewetting_carbon], ActivityTypes.REWETTING_REVEGETATION, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(rewetting_emission_set)

                rewetting_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in emissions_yearly_rewetting_methane], ActivityTypes.REWETTING_REVEGETATION, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(rewetting_emission_set)

                biomass_emissions = calculate_biomass()
                biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in biomass_emissions], ActivityTypes.BIOMASS, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

            except Exception as e:
                traceback.print_exc()
                pass

        calculate_drainage()
        calculate_extraction_excavation()
        calculate_rewetting_revegetation()