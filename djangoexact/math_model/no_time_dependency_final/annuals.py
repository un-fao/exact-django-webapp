import traceback

from .general_functions import (
    BaseModule,
    breakdown_according_to_values,
    soil_emissions_2,
    som_emissions,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
    biomass_emissions
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)


class AnnualCropland(BaseModule):
    def __init__(
        self,
        area_start,
        area_end,
        time_impl,
        time_cap,
        rate_end,
        rate_coefficient_end,
        soc_start_default,
        soc_end_default,
        soc_start_tier_2,
        soc_end_tier_2,
        fmg_start_default,
        fmg_end_default,
        fmg_start_tier_2,
        fmg_end_tier_2,
        flu_start_default,
        flu_end_default,
        flu_start_tier_2,
        flu_end_tier_2,
        fi_start_default,
        fi_end_default,
        fi_start_tier_2,
        fi_end_tier_2,
        calculate_soc_som,
        emission_factor_nitrous_som,
        nitrous_constant,
        methane_constant,
        ef_methane_agr_residues_main,
        combustion_factor_main,
        residue_main_tier_2,
        n_estimation_slope_main,
        n_estimation_intercept_main,
        yield_value_main,
        ef_methane_agr_residues_minor,
        combustion_factor_minor,
        residue_minor_tier_2,
        n_estimation_slope_minor,
        n_estimation_intercept_minor,
        yield_value_minor,
        ef_nitrous_agr_residues_main,
        retained_main,
        ef_nitrous_agr_residues_minor,
        retained_minor,
        n_content_ag_main,
        ratio_bg_ag_main,
        n_content_bg_main,
        n_content_ag_minor,
        ratio_bg_ag_minor,
        n_content_bg_minor,
        delay,
        biomass_start_default,
        biomass_end_default,
        biomass_start_tier_2,
        biomass_end_tier_2,
    ):
        self.area_start = area_start
        self.area_end = area_end
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate = rate_end
        self.rate_coefficient = rate_coefficient_end
        self.soc_start_default = soc_start_default
        self.soc_end_default = soc_end_default
        self.soc_start_tier_2 = soc_start_tier_2
        self.soc_end_tier_2 = soc_end_tier_2

        self.fmg_start_default = fmg_start_default  # defaulted to 1 in case there are None, if not float value
        self.fmg_end_default = fmg_end_default  # defaulted to 1 in case there are None, if not float value
        self.fmg_start_tier_2 = fmg_start_tier_2  # tier 2 value, expects float or None
        self.fmg_end_tier_2 = fmg_end_tier_2  # tier 2 value, expects float or None
        self.flu_start_default = flu_start_default  # defaulted to 1 in case there are None, if not float value
        self.flu_end_default = flu_end_default  # defaulted to 1 in case there are None, if not float value
        self.flu_start_tier_2 = flu_start_tier_2  # tier 2 value, expects float or None
        self.flu_end_tier_2 = flu_end_tier_2  # tier 2 value, expects float or None
        self.fi_start_default = fi_start_default  # defaulted to 1 in case there are None, if not float value
        self.fi_end_default = fi_end_default  # defaulted to 1 in case there are None, if not float value
        self.fi_start_tier_2 = fi_start_tier_2  # tier 2 value, expects float or None
        self.fi_end_tier_2 = fi_end_tier_2  # tier 2 value, expects float or None

        self.calculate_soc_som = calculate_soc_som

        self.emission_factor_nitrous_som = emission_factor_nitrous_som
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.ef_methane_agr_residues_main = ef_methane_agr_residues_main
        self.combustion_factor_main = combustion_factor_main
        self.residue_main_tier_2 = residue_main_tier_2
        self.n_estimation_slope_main = n_estimation_slope_main
        self.n_estimation_intercept_main = n_estimation_intercept_main
        self.yield_value_main = yield_value_main
        self.ef_methane_agr_residues_minor = ef_methane_agr_residues_minor
        self.combustion_factor_minor = combustion_factor_minor
        self.residue_minor_tier_2 = residue_minor_tier_2
        self.n_estimation_slope_minor = n_estimation_slope_minor
        self.n_estimation_intercept_minor = n_estimation_intercept_minor
        self.yield_value_minor = yield_value_minor
        self.ef_nitrous_agr_residues_main = ef_nitrous_agr_residues_main
        self.retained_main = retained_main
        self.ef_nitrous_agr_residues_minor = ef_nitrous_agr_residues_minor
        self.retained_minor = retained_minor
        self.n_content_ag_main = n_content_ag_main
        self.ratio_bg_ag_main = ratio_bg_ag_main
        self.n_content_bg_main = n_content_bg_main
        self.n_content_ag_minor = n_content_ag_minor
        self.ratio_bg_ag_minor = ratio_bg_ag_minor
        self.n_content_bg_minor = n_content_bg_minor
        self.delay = delay

        # TODO: Assigned FMG, FLU, FI values. Maybe once everything has been done change this structure
        self.fmg_start = self.fmg_start_tier_2 if self.fmg_start_tier_2 else self.fmg_start_default
        self.fmg_end = self.fmg_end_tier_2 if self.fmg_end_tier_2 else self.fmg_end_default
        self.flu_start = self.flu_start_tier_2 if self.flu_start_tier_2 else self.flu_start_default
        self.flu_end = self.flu_end_tier_2 if self.flu_end_tier_2 else self.flu_end_default
        self.fi_start = self.fi_start_tier_2 if self.fi_start_tier_2 else self.fi_start_default
        self.fi_end = self.fi_end_tier_2 if self.fi_end_tier_2 else self.fi_end_default

        # AUXILIARY VARIABLES FOR SOIL CALCULATION
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate)
        self.total_hectars = yearly_time_dependent_parameter_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate, interim_values=True)

        self.soc_start = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start if not self.soc_start_tier_2 else self.soc_start_tier_2
        self.soc_end = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end if not self.soc_end_tier_2 else self.soc_end_tier_2

        # AUXILIARY VARIABLES FOR BIOMASS CALCULATION
        self.biomass_start = biomass_start_default if not biomass_start_tier_2 else biomass_start_tier_2
        self.biomass_end = biomass_end_default if not biomass_end_tier_2 else biomass_end_tier_2
        # DEFAULTS FOR TIER 2 VALUES INITIALIZATION
        self.soc_start_tier_2_default = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start
        self.soc_end_tier_2_default = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end
        self.f_lu_start_tier_2_default = self.flu_start
        self.f_lu_end_tier_2_default = self.flu_end
        self.f_mg_start_tier_2_default = self.fmg_start
        self.f_mg_end_tier_2_default = self.fmg_end
        self.f_i_start_tier_2_default = self.fi_start
        self.f_i_end_tier_2_default = self.fi_end

        self.residue_main_tier_2_default = None
        self.ag_residue_minor_tier_2_default = None

        if yield_value_main:
            self.ag_residue_main_tier_2_default = yield_value_main * self.n_estimation_slope_main + self.n_estimation_intercept_main
        if yield_value_minor:
            self.ag_residue_minor_tier_2_default = yield_value_minor * self.n_estimation_slope_minor + self.n_estimation_intercept_minor

        # RESULTS
        self.emissions_soil_yearly = []
        self.emissions_soil_total = 0

        self.emissions_som_yearly = []
        self.emissions_som_total = 0

        self.emissions_residue_burning_yearly = []
        self.emissions_residue_burning_total = 0

        self.emissions_biomass_yearly = []
        self.emissions_biomass_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)

    def calculate_emissions(self):
        def calculate_emissions_soil():
            try:
                if self.calculate_soc_som:
                    self.emissions_soil_yearly, self.emissions_soil_total = soil_emissions_2(self.soc_start, self.soc_end, self.total_hectars, self.area_start, self.area_end, self.hectars_before_20)

                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.emissions_soil_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

            except Exception as e:
                traceback.print_exc()

        def calculate_emissions_som():
            try:
                if self.calculate_soc_som:
                    self.emissions_som_yearly, self.emissions_som_total = som_emissions(self.soc_end, self.soc_start, self.emission_factor_nitrous_som, self.nitrous_constant, self.hectars_before_20)

                    som_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in self.emissions_som_yearly], ActivityTypes.SOM, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(som_emission_set)
            except Exception as e:
                traceback.print_exc()

        def calculate_emissions_residue_burning():
            ################## COMPUTATION OF AMOUNT OF KG OF METHANE ###################

            yield_value_main = self.yield_value_main * 1000
            yield_value_minor = self.yield_value_minor * 1000 if self.yield_value_minor else None

            ag_residue_main = self.residue_main_tier_2 * 1000 if self.residue_main_tier_2 else yield_value_main * self.n_estimation_slope_main + self.n_estimation_intercept_main
            ag_residue_tonnes_main = ag_residue_main / 1000
            if self.ef_methane_agr_residues_main:
                main_season_methane = ag_residue_tonnes_main * self.ef_methane_agr_residues_main * self.combustion_factor_main
            else:
                main_season_methane = 0
            ag_residue_minor = self.residue_minor_tier_2 * 1000 if self.residue_minor_tier_2 else yield_value_minor * self.n_estimation_slope_minor + self.n_estimation_intercept_minor if yield_value_minor else 0
            ag_residue_tonnes_minor = ag_residue_minor / 1000
            if self.ef_methane_agr_residues_minor:
                minor_season_methane = ag_residue_tonnes_minor * self.ef_methane_agr_residues_minor * self.combustion_factor_minor
            else:
                minor_season_methane = 0

            kg_methane = main_season_methane + minor_season_methane

            #################### COMPUTATION OF AMOUNT OF KG OF NITROUS ######################
            annual_n_residues_main = ag_residue_main * self.n_content_ag_main + (yield_value_main + ag_residue_main) * self.ratio_bg_ag_main * self.n_content_bg_main
            # COMPUTATION FOR MAIN
            # this means if "Burned"
            if self.ef_nitrous_agr_residues_main:
                main_season_nitrous = ag_residue_tonnes_main * self.ef_nitrous_agr_residues_main * self.combustion_factor_main
            # this means if "Retained"
            elif self.retained_main:
                n2o_n_conversion = 44 / 28
                main_season_nitrous = annual_n_residues_main * self.emission_factor_nitrous_som * n2o_n_conversion
            else:
                main_season_nitrous = 0
            # COMPUTATION FOR MINOR
            annual_n_residues_minor = ag_residue_minor * self.n_content_ag_minor + (yield_value_minor + ag_residue_minor) * self.ratio_bg_ag_minor * self.n_content_bg_minor if yield_value_minor else 0
            # COMPUTATION FOR MAIN
            # this means if "Burned"

            if self.ef_nitrous_agr_residues_minor:
                minor_season_nitrous = ag_residue_tonnes_minor * self.ef_nitrous_agr_residues_minor * self.combustion_factor_minor
            # this means if "Retained" BUT IN REALITY NOT REALLY, AT LEAST IT SEEMS TO WORK (WITHOUT A MINOR)
            elif self.retained_minor:
                n2o_n_conversion = 44 / 28
                minor_season_nitrous = annual_n_residues_minor * self.emission_factor_nitrous_som * n2o_n_conversion
            else:
                minor_season_nitrous = 0

            kg_nitrous = main_season_nitrous + minor_season_nitrous

            co2_crop = (kg_nitrous * self.nitrous_constant + kg_methane * self.methane_constant) / 1000

            total = (sum(self.total_hectars)) * co2_crop

            self.emissions_residue_burning_total = total
            self.emissions_residue_burning_yearly = breakdown_according_to_values(total, self.total_hectars)

            total_nitrous = (sum(self.total_hectars)) * kg_nitrous * self.nitrous_constant / 1000
            total_methane = (sum(self.total_hectars)) * kg_methane * self.methane_constant / 1000

            residue_burning_nitrous_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in breakdown_according_to_values(total_nitrous, self.total_hectars)], ActivityTypes.RESIDUE_BURNING, delay=self.delay)
            residue_burning_methane_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in breakdown_according_to_values(total_methane, self.total_hectars)], ActivityTypes.RESIDUE_BURNING, delay=self.delay)

            self.result.yearly_emissions_by_sector_by_gas.append(residue_burning_nitrous_emission_set)
            self.result.yearly_emissions_by_sector_by_gas.append(residue_burning_methane_emission_set)

        def calculate_biomass_emissions():
            try:
                self.emissions_biomass_yearly, self.emissions_biomass_total = biomass_emissions(self.biomass_start, self.biomass_end, self.area_start, self.area_end, self.rate, self.time_impl, self.time_cap)
                biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.emissions_biomass_yearly], ActivityTypes.BIOMASS, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

            except Exception as e:
                traceback.print_exc()

        calculate_emissions_soil()
        calculate_emissions_som()
        calculate_emissions_residue_burning()
        calculate_biomass_emissions()

        try:
            self.emissions_total_yearly = [sum(x) for x in zip(self.emissions_residue_burning_yearly, self.emissions_soil_yearly, self.emissions_som_yearly)]
            self.total_emissions = sum(self.emissions_total_yearly)
            return self.total_emissions

        except Exception as e:
            traceback.print_exc()
            return None


# inputs = [27, 93, 5, 17, 'D', 0.5, 87.0, None, 0.77, None, 1.0, None, 1.03, None, 0.005, 265.0, 28.0, None, 0.85, None, 0.88, 1.33, 50, None, None, None, None, None, None, None, True, None, False, 0.007, 0.22, 0.006, None, None, None]
# annual = (AnnualCropland(*inputs))

# annual.calculate_emissions()
