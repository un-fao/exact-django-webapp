import traceback

from .general_functions import (
    BaseModule,
    breakdown_according_to_values,
    soil_emissions_2,
    som_emissions,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
    biomass_emissions,
    breakdown_according_to_values_for_x_years
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)


class PerennialCropping(BaseModule):
    def __init__(
        self,
        area_start,
        area_end,
        time_impl,
        time_cap,
        rate,
        nitrous_constant,
        methane_constant,
        residue_burnt,
        emission_factor_burning_nitrous_residue,
        ef_nitrous_som,
        emission_factor_burning_methane,
        combustion_factor,
        fire_periodicity_default,
        fire_periodicity_tier_2,
        t_biomass_tier_2,
        agb_rate_default,
        agb_rate_tier_2,
        agb_maximum_c,
        bgb_rate_default,
        bgb_rate_tier_2,
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
        self.rate = rate
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.residue_burnt = residue_burnt
        self.emission_factor_burning_nitrous_residue = emission_factor_burning_nitrous_residue
        self.ef_nitrous_som = ef_nitrous_som
        self.emission_factor_burning_methane = emission_factor_burning_methane
        self.combustion_factor = combustion_factor
        self.fire_periodicity_default = fire_periodicity_default
        self.fire_periodicity_tier_2 = fire_periodicity_tier_2
        self.t_biomass_tier_2 = t_biomass_tier_2
        self.agb_rate_default = agb_rate_default
        self.agb_rate_tier_2 = agb_rate_tier_2
        self.agb_maximum_c = agb_maximum_c
        self.bgb_rate_default = bgb_rate_default
        self.bgb_rate_tier_2 = bgb_rate_tier_2
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
        self.delay = delay

        # TODO: Assigned FMG, FLU, FI values. Maybe once everything has been done change this structure
        self.fmg_start = self.fmg_start_tier_2 if self.fmg_start_tier_2 else self.fmg_start_default
        self.fmg_end = self.fmg_end_tier_2 if self.fmg_end_tier_2 else self.fmg_end_default
        self.flu_start = self.flu_start_tier_2 if self.flu_start_tier_2 else self.flu_start_default
        self.flu_end = self.flu_end_tier_2 if self.flu_end_tier_2 else self.flu_end_default
        self.fi_start = self.fi_start_tier_2 if self.fi_start_tier_2 else self.fi_start_default
        self.fi_end = self.fi_end_tier_2 if self.fi_end_tier_2 else self.fi_end_default

        self.biomass_start = biomass_start_default if not biomass_start_tier_2 else biomass_start_tier_2
        self.biomass_end = biomass_end_default if not biomass_end_tier_2 else biomass_end_tier_2

        # Added values
        self.total_hectars = yearly_time_dependent_parameter_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate)
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate)

        self.soc_start = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start if not self.soc_start_tier_2 else self.soc_start_tier_2
        self.soc_end = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end if not self.soc_end_tier_2 else self.soc_end_tier_2

        # TIER 2 DEFAULTS
        self.soc_start_tier_2_default = self.soc_start_default * self.fmg_start_default * self.flu_start_default * self.fi_start_default
        self.soc_end_tier_2_default = self.soc_end_default * self.fmg_end_default * self.flu_end_default * self.fi_end_default
        self.fmg_start_tier_2_default = self.fmg_start_default * self.flu_start_default * self.fi_start_default
        self.fmg_end_tier_2_default = self.fmg_end_default * self.flu_end_default * self.fi_end_default
        self.flu_start_tier_2_default = self.flu_start_default * self.fi_start_default
        self.flu_end_tier_2_default = self.flu_end_default * self.fi_end_default
        self.fi_start_tier_2_default = self.fi_start_default
        self.fi_end_tier_2_default = self.fi_end_default
        self.agb_rate_tier_2_default = self.agb_rate_default
        self.bgb_rate_tier_2_default = self.bgb_rate_default
        self.t_biomass_tier_2_default = self.agb_rate_default * 0.5 / 0.47 if not self.agb_rate_tier_2 else self.agb_rate_tier_2 * 0.5 / 0.47

        # RESULTS
        self.yearly_residue_emissions = []
        self.total_residue_emissions = 0

        self.yearly_bio_emissions = []
        self.total_bio_emissions = 0

        self.yearly_som_emissions = []
        self.total_som_emissions = 0

        self.yearly_soil_emissions = []
        self.total_soil_emissions = 0

        self.emissions_biomass_yearly = []
        self.emissions_biomass_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)

    def calculate_emissions(
        self,
    ):
        def calculate_residue():
            try:
                fire_periodicity = self.fire_periodicity_default if not self.fire_periodicity_tier_2 else self.fire_periodicity_tier_2
                ag_tc = self.agb_rate_default if not self.agb_rate_tier_2 else self.agb_rate_tier_2
                t_biomass = ag_tc * 0.5 / 0.47 if not self.t_biomass_tier_2 else self.t_biomass_tier_2

                ################## COMPUTATION OF AMOUNT OF KG OF METHANE ###################

                kg_methane = t_biomass * self.emission_factor_burning_methane * self.combustion_factor / fire_periodicity if self.residue_burnt else 0

                #################### COMPUTATION OF AMOUNT OF KG OF NITROUS ######################

                kg_nitrous = t_biomass * self.emission_factor_burning_nitrous_residue * self.combustion_factor / fire_periodicity if self.residue_burnt else 0

                co2_crop = (kg_nitrous * self.nitrous_constant + kg_methane * self.methane_constant) / 1000

                total = sum(self.total_hectars) * co2_crop

                self.yearly_residue_emissions = breakdown_according_to_values(total, self.total_hectars)
                self.total_residue_emissions = total

                residue_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.yearly_residue_emissions], ActivityTypes.RESIDUE_BURNING, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(residue_emission_set)
            except Exception as e:
                traceback.print_exc()

        def calculate_som():
            try:
                if self.calculate_soc_som:
                    self.yearly_som_emissions, self.total_som_emissions = som_emissions(self.soc_end, self.soc_start, self.ef_nitrous_som, self.nitrous_constant, self.hectars_before_20)

                    som_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in self.yearly_som_emissions], ActivityTypes.SOM, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(som_emission_set)

            except Exception as e:
                traceback.print_exc()

        def calculate_soil():
            try:
                if self.calculate_soc_som:
                    self.yearly_soil_emissions, self.total_soil_emissions = soil_emissions_2(self.soc_start, self.soc_end, self.total_hectars, self.area_start, self.area_end, self.hectars_before_20)

                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in self.yearly_soil_emissions], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)
            except Exception as e:
                traceback.print_exc()

        def calculate_biomass_emissions():

            # NOTE: should this be calculated only for main season?
            try:
                if self.biomass_start and self.biomass_end:
                    # NOTE: This means that we have received values for both (or we have tier 2 values for both)
                    self.emissions_biomass_yearly, self.emissions_biomass_total = biomass_emissions(self.biomass_end, self.biomass_start, self.total_hectars, self.area_start, self.area_end, self.hectars_before_20)

                    biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.emissions_biomass_yearly], ActivityTypes.BIOMASS, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

                else:
                    # NOTE: In this case we are in the situation where biomass_final has to be calculated and is not tabulated
                    agb_rate = self.agb_rate_default * 44 / 12 if not self.agb_rate_tier_2 else self.agb_rate_tier_2 * 44 / 12
                    bgb_rate = self.bgb_rate_default * 44 / 12 if not self.bgb_rate_tier_2 else self.bgb_rate_tier_2 * 44 / 12

                    if self.agb_rate_tier_2:
                        max_agb = 0 if self.agb_rate_default < self.agb_rate_tier_2 else self.agb_maximum_c * 44 / 12
                    else:
                        max_agb = self.agb_maximum_c * 44 / 12

                    biomass_accumulation_rate = agb_rate + bgb_rate

                    max_years_growth = max_agb / agb_rate

                    calculated = self.biomass_start + biomass_accumulation_rate * sum(self.total_hectars) 
                    tabular = (max_agb + bgb_rate * max_years_growth) * self.area_end

                    total = -min(calculated, tabular) if (max_agb != 0 and self.area_end != 0) else -calculated


                    # NOTE: maybe this should be broken down over max_years_growth or over all years of project depending on whether calculated or tabular is used
                    self.yearly_bio_emissions = breakdown_according_to_values_for_x_years(total, self.total_hectars)
                    self.total_bio_emissions = total

                    biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.yearly_bio_emissions], ActivityTypes.BIOMASS, delay=self.delay)
                    self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

            except Exception as e:
                traceback.print_exc()

        calculate_residue()
        calculate_som()
        calculate_soil()
        calculate_biomass_emissions()

        try:
            self.emissions_total_yearly = [i + j + k + l for i, j, k, l in zip(self.yearly_residue_emissions, self.yearly_bio_emissions, self.yearly_som_emissions, self.yearly_soil_emissions)]
            self.total_emissions = sum(self.emissions_total_yearly)
            return self.total_emissions
        except Exception as e:
            traceback.print_exc()

