import re
import traceback

from .general_functions import (
    BaseModule,
    ch4_head_calculation_general,
    soil_emissions_2,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
    som_emissions,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)


class OtherLandUseChanges(BaseModule):
    def __init__(
        self,
        initial_lu_biomass,
        initial_lu_biomass_tier_2,
        final_lu_biomass,
        final_lu_biomass_tier_2,
        c_n_ratio,
        moisture_emission_factor,
        combustion_factor,
        emission_factor_nitrous,
        emission_factor_methane,
        nitrous_constant,
        methane_constant,
        fire_bool,
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
        area,
        time_impl,
        time_cap,
        rate,
        delay=0,
    ):
        self.initial_lu_biomass = initial_lu_biomass
        self.initial_lu_biomass_tier_2 = initial_lu_biomass_tier_2
        self.final_lu_biomass = final_lu_biomass
        self.final_lu_biomass_tier_2 = final_lu_biomass_tier_2
        self.c_n_ratio = c_n_ratio
        self.moisture_emission_factor = moisture_emission_factor
        self.combustion_factor = combustion_factor
        self.emission_factor_nitrous = emission_factor_nitrous
        self.emission_factor_methane = emission_factor_methane
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.fire_bool = fire_bool

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

        self.area = area
        self.time_impl = time_impl - delay
        self.time_cap = time_cap
        self.rate = rate
        self.delay = delay

        self.fmg_start = self.fmg_start_tier_2 if self.fmg_start_tier_2 else self.fmg_start_default
        self.fmg_end = self.fmg_end_tier_2 if self.fmg_end_tier_2 else self.fmg_end_default
        self.flu_start = self.flu_start_tier_2 if self.flu_start_tier_2 else self.flu_start_default
        self.flu_end = self.flu_end_tier_2 if self.flu_end_tier_2 else self.flu_end_default
        self.fi_start = self.fi_start_tier_2 if self.fi_start_tier_2 else self.fi_start_default
        self.fi_end = self.fi_end_tier_2 if self.fi_end_tier_2 else self.fi_end_default

        # AUXILIARY VARIABLES FOR SOIL CALCULATION
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(0, self.area, self.time_impl, self.time_cap, self.rate)
        self.total_hectars = yearly_time_dependent_parameter_breakdown(0, self.area, self.time_impl, self.time_cap, self.rate, interim_values=True)

        self.soc_start = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start if not self.soc_start_tier_2 else self.soc_start_tier_2
        self.soc_end = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end if not self.soc_end_tier_2 else self.soc_end_tier_2

        self.result = Result(self.time_impl, self.time_cap)

    def calculate_emissions(self):
       
        def calculate_biomass():
            try:
                # TODO: talk to Claudio, there is a problem here where there is a value for biomass change in emissions, even though initial and final should be the same
                initial_biomass = self.initial_lu_biomass if not self.initial_lu_biomass_tier_2 else self.initial_lu_biomass_tier_2
                final_biomass = self.final_lu_biomass if not self.final_lu_biomass_tier_2 else self.final_lu_biomass_tier_2

                delta_c_biomass = (final_biomass - initial_biomass) * (-44 / 12)

                # TODO: add logic for comprehension of amount of hectars addressed in one year (not self.total_hectars) and use that for the breakdown and total
                total = delta_c_biomass * self.area

                self.total_biomass_emissions = total
                # TODO: change so only in implementation years but proportionate to the hectars addressed in that year
                self.yearly_biomass_emissions = yearly_constant_emissions_breakdown(total, self.time_impl, self.time_cap, self.rate)

                self.result.yearly_emissions_by_sector_by_gas.append(
                    YearlyGasActivityEmissionSet(
                        year=0,
                        gas_type=GasTypes.CO2,
                        emissions=[Emission(e, GasTypes.CO2) for e in self.yearly_biomass_emissions],
                        # TODO: ask Lorenzo if Biomass Loss or Gain
                        activity=ActivityTypes.BIOMASS,
                        delay=self.delay,
                    )
                )

            except Exception as e:
                traceback.print_exc()

        def calculate_fire():
            delta_c_soc = (self.soc_end - self.soc_start) / 20

            initial_biomass = self.initial_lu_biomass if not self.initial_lu_biomass_tier_2 else self.initial_lu_biomass_tier_2
            fire_mb = initial_biomass / 0.4

            kg_methane_fire = fire_mb * self.combustion_factor * self.emission_factor_methane if self.fire_bool else 0
            kg_nitrous_fire = initial_biomass * 2.5 * self.combustion_factor * self.emission_factor_nitrous if self.fire_bool else 0

            methane_emissions = kg_methane_fire * self.methane_constant
            nitrous_emissions = kg_nitrous_fire * self.nitrous_constant

            total_em_per_hectar = (methane_emissions + nitrous_emissions) / 1000

            self.total_fire_emissions = total_em_per_hectar * self.area
            self.yearly_fire_emissions = yearly_constant_emissions_breakdown(self.total_fire_emissions, self.time_impl, self.time_cap, self.rate)

            # CALCULATE FOR INDIVIDUAL METHANE AND NITROUS EMISSIONS(the calculation on top can be removed in the future)
            methane_em_per_hectar = methane_emissions / 1000
            nitrous_em_per_hectar = nitrous_emissions / 1000

            # TODO: same as biomass above, breakdown according to hectares addressed in that year
            methane_fire_emissions = methane_em_per_hectar * self.area
            nitrous_fire_emissions = nitrous_em_per_hectar * self.area

            yearly_methane_fire_emissions = yearly_constant_emissions_breakdown(methane_fire_emissions, self.time_impl, self.time_cap)
            yearly_nitrous_fire_emissions = yearly_constant_emissions_breakdown(nitrous_fire_emissions, self.time_impl, self.time_cap)

            self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in yearly_methane_fire_emissions], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))
            self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in yearly_nitrous_fire_emissions], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))

        try:
            calculate_biomass()
            calculate_fire()

        except Exception as e:
            traceback.print_exc()

