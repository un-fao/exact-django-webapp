import traceback

from .general_functions import (
    breakdown_proportionally_to_values,
    soil_emissions,
    som_emissions,
    compute_half_year_cumulative_n_year_maturity,
    compute_yearly_or_half_year_cumulative,
    biomass_emissions,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)
from .ghg_inventory_class import InventoryPerGasPerActivity
from .generalized_modules import LandModule

from dataclasses import dataclass
from typing import Optional


@dataclass(kw_only=True)
class AnnualCropland(LandModule):
    nitrous_constant: float
    methane_constant: float
    ef_methane_agr_residues_main: float
    combustion_factor_main: float
    residue_main_tier_2: Optional[float] = None
    n_estimation_slope_main: float
    n_estimation_intercept_main: float
    yield_value_main: float
    ef_methane_agr_residues_minor: Optional[float] = None
    combustion_factor_minor: Optional[float] = None
    residue_minor_tier_2: Optional[float] = None
    n_estimation_slope_minor: float
    n_estimation_intercept_minor: Optional[float] = None
    yield_value_minor: Optional[float] = None
    ef_nitrous_agr_residues_main: float
    retained_main: bool
    ef_nitrous_agr_residues_minor: Optional[float] = None
    retained_minor: Optional[bool] = None
    n_content_ag_main: float
    ratio_bg_ag_main: float
    n_content_bg_main: float
    dm_content_main: float
    n_content_ag_minor: Optional[float] = None
    ratio_bg_ag_minor: Optional[float] = None
    n_content_bg_minor: Optional[float] = None
    dm_content_minor: Optional[float] = None
    yield_main_tier_2: Optional[float] = None
    yield_minor_tier_2: Optional[float] = None

    def __post_init__(self):
        super().__post_init__()

        self.yield_main = self.yield_main_tier_2 if self.yield_main_tier_2 is not None else self.yield_value_main
        self.yield_minor = self.yield_minor_tier_2 if self.yield_minor_tier_2 is not None else self.yield_value_minor

        # NOTE: this is a default value that is calculated based on the input values, needed for the frontend
        if self.yield_value_main is not None:
            if self.n_estimation_slope_main is None:
                raise ValueError("n_estimation_slope_main is required if yield_value_main is provided")
            if self.n_estimation_intercept_main is None:
                raise ValueError("n_estimation_intercept_main is required if yield_value_main is provided")

            self.ag_residue_main_tier_2_default = self.yield_main * self.n_estimation_slope_main + self.n_estimation_intercept_main
        if self.yield_value_minor is not None:
            if self.n_estimation_slope_minor is None:
                raise ValueError("n_estimation_slope_minor is required if yield_value_minor is provided")
            if self.n_estimation_intercept_minor is None:
                raise ValueError("n_estimation_intercept_minor is required if yield_value_minor is provided")

            self.ag_residue_minor_tier_2_default = self.yield_minor * self.n_estimation_slope_minor + self.n_estimation_intercept_minor

    def calculate_emissions(self):
        def calculate_emissions_soil():
            try:
                if self.calculate_soc_som:
                    emissions_soil_yearly, emissions_soil_total = soil_emissions(self.soc_start, self.soc_end, self.hectares_total, self.hectares_start, self.hectares_end, self.hectares_before_20)
                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_soil_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CO2, self.soc_start * self.hectares_start * 44/12, ActivityTypes.SOIL_CO2_CHANGE))

            except Exception as e:
                traceback.print_exc()

        def calculate_emissions_som():
            try:
                if self.calculate_soc_som:
                    emissions_som_yearly, emissions_som_total = som_emissions(self.soc_end, self.soc_start, self.ef_nitrous_som, self.nitrous_constant, self.hectares_before_20)
                    som_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in emissions_som_yearly], ActivityTypes.SOM, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(som_emission_set)

                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.N2O, 0, ActivityTypes.SOM))

            except Exception as e:
                traceback.print_exc()

        def calculate_main_season_emissions():
            """Calculate methane and nitrous emissions for main season"""
            yield_value_main = self.yield_main * 1000

            # Calculate agricultural residue for main season
            ag_residue_main = self.residue_main_tier_2 * 1000 if self.residue_main_tier_2 else yield_value_main * self.dm_content_main * self.n_estimation_slope_main + self.n_estimation_intercept_main
            ag_residue_tonnes_main = ag_residue_main / 1000

            # Calculate methane emissions for main season
            if self.ef_methane_agr_residues_main:
                main_season_methane = ag_residue_tonnes_main * self.ef_methane_agr_residues_main * self.combustion_factor_main
            else:
                main_season_methane = 0

            # Calculate nitrous emissions for main season
            annual_n_residues_main = ag_residue_main * self.n_content_ag_main + (yield_value_main + ag_residue_main) * self.ratio_bg_ag_main * self.n_content_bg_main

            # Check if burned
            if self.ef_nitrous_agr_residues_main:
                main_season_nitrous = ag_residue_tonnes_main * self.ef_nitrous_agr_residues_main * self.combustion_factor_main
            # Check if retained
            elif self.retained_main:
                n2o_n_conversion = 44 / 28
                main_season_nitrous = annual_n_residues_main * self.ef_nitrous_som * n2o_n_conversion
            else:
                main_season_nitrous = 0

            return main_season_methane, main_season_nitrous

        def calculate_minor_season_emissions():
            """Calculate methane and nitrous emissions for minor season"""
            yield_value_minor = self.yield_value_minor * 1000 if self.yield_value_minor else None

            # Calculate agricultural residue for minor season
            ag_residue_minor = (
                self.residue_minor_tier_2 * 1000 if self.residue_minor_tier_2 else yield_value_minor * self.dm_content_minor * self.n_estimation_slope_minor + self.n_estimation_intercept_minor if yield_value_minor else 0
            )
            ag_residue_tonnes_minor = ag_residue_minor / 1000

            # Calculate methane emissions for minor season
            if self.ef_methane_agr_residues_minor:
                minor_season_methane = ag_residue_tonnes_minor * self.ef_methane_agr_residues_minor * self.combustion_factor_minor
            else:
                minor_season_methane = 0

            # Calculate nitrous emissions for minor season
            annual_n_residues_minor = ag_residue_minor * self.n_content_ag_minor + (yield_value_minor + ag_residue_minor) * self.ratio_bg_ag_minor * self.n_content_bg_minor if yield_value_minor else 0

            # Check if burned
            if self.ef_nitrous_agr_residues_minor:
                minor_season_nitrous = ag_residue_tonnes_minor * self.ef_nitrous_agr_residues_minor * self.combustion_factor_minor
            # Check if retained
            elif self.retained_minor:
                n2o_n_conversion = 44 / 28
                minor_season_nitrous = annual_n_residues_minor * self.ef_nitrous_som * n2o_n_conversion
            else:
                minor_season_nitrous = 0

            return minor_season_methane, minor_season_nitrous

        def calculate_emissions_residue_burning():
            """Calculate total residue burning emissions from main and minor seasons"""
            # Calculate emissions for both seasons
            main_season_methane, main_season_nitrous = calculate_main_season_emissions()

            if self.yield_value_minor is None:
                minor_season_methane = 0
                minor_season_nitrous = 0
            else:
                # Calculate emissions for minor season only if yield_value_minor is provided
                minor_season_methane, minor_season_nitrous = calculate_minor_season_emissions()

            # Combine seasonal emissions
            kg_methane = main_season_methane + minor_season_methane
            kg_nitrous = main_season_nitrous + minor_season_nitrous

            # Calculate total emissions
            total_nitrous = (sum(self.hectares_total)) * kg_nitrous * self.nitrous_constant / 1000
            total_methane = (sum(self.hectares_total)) * kg_methane * self.methane_constant / 1000

            residue_burning_nitrous_emission_set = YearlyGasActivityEmissionSet(
                0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in breakdown_proportionally_to_values(total_nitrous, self.hectares_total)], ActivityTypes.RESIDUE_BURNING, delay=self.delay
            )
            residue_burning_methane_emission_set = YearlyGasActivityEmissionSet(
                0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in breakdown_proportionally_to_values(total_methane, self.hectares_total)], ActivityTypes.RESIDUE_BURNING, delay=self.delay
            )

            self.result.yearly_emissions_by_sector_by_gas.append(residue_burning_nitrous_emission_set)
            self.result.yearly_emissions_by_sector_by_gas.append(residue_burning_methane_emission_set)

            inventory_nitrous = self.hectares_start * kg_nitrous * self.nitrous_constant / 1000
            inventory_methane = self.hectares_start * kg_methane * self.methane_constant / 1000
            self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.N2O, inventory_nitrous, ActivityTypes.RESIDUE_BURNING))
            self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CH4, inventory_methane, ActivityTypes.RESIDUE_BURNING))

        def calculate_biomass_emissions():
            try:
                if self.calculate_biomass:
                    emissions_biomass_yearly, emissions_biomass_total = biomass_emissions(
                        self.biomass_start, self.biomass_end, self.hectares_start, self.hectares_end, self.rate_type, self.implementation_time, self.capitalization_time
                    )
                    biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_biomass_yearly], ActivityTypes.BIOMASS, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

                    # TODO Peter: Is this the half-year business
                    inventory = InventoryPerGasPerActivity(GasTypes.CO2, self.biomass_start * self.hectares_start* 44/12, ActivityTypes.BIOMASS)
                    self.inventory.emissions_by_sector_by_gas.append(inventory)

                else:
                    pass

            except Exception as e:
                traceback.print_exc()

        calculate_emissions_soil()
        calculate_emissions_som()
        calculate_emissions_residue_burning()
        calculate_biomass_emissions()
