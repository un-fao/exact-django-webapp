from .general_functions import yearly_time_dependent_parameter_breakdown, ch4_head_calculation_general, yearly_constant_emissions_breakdown, soil_emissions_delta_soc_known, yearly_time_dependent_20_year_breakdown
import traceback, re
from .ghg_emissions_classes import GasTypes, ActivityTypes, Emission, YearlyGasActivityEmissionSet, Result


class OtherLandUseChanges:

    def __init__(self, initial_lu_biomass, initial_lu_biomass_tier_2, final_lu_biomass, final_lu_biomass_tier_2,
    c_n_ratio, moisture_emission_factor,combustion_factor, emission_factor_nitrous, emission_factor_methane,nitrous_constant, methane_constant,fire_bool,
    socref, initial_flu, final_flu, initial_soc_tier_2, final_soc_tier_2, area, time_impl, time_cap, rate):
        
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
        self.socref = socref
        self.initial_flu = initial_flu
        self.final_flu = final_flu
        self.initial_soc_tier_2 = initial_soc_tier_2
        self.final_soc_tier_2 = final_soc_tier_2
        self.area = area
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate = rate

        # ADDED PARAMETERS FOR CALCULATION
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(0, self.area, self.time_impl, self.time_cap, self.rate)

        # TIER 2 VALUE DEFAULTS

        # RESULTS
        self.yearly_biomass_emissions = []
        self.total_biomass_emissions = 0

        self.yearly_soc_emissions = []
        self.total_soc_emissions = 0

        self.yearly_fire_emissions = []
        self.total_fire_emissions = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)

    def calculate_emissions(self):

        def calculate_biomass():
            
            try:
                initial_biomass = self.initial_lu_biomass if not self.initial_lu_biomass_tier_2 else self.initial_lu_biomass_tier_2
                final_biomass = self.final_lu_biomass if not self.final_lu_biomass_tier_2 else self.final_lu_biomass_tier_2

                delta_c_biomass = (final_biomass - initial_biomass) * (-44/12)

                total = delta_c_biomass * self.area

                self.total_biomass_emissions = total
                self.yearly_biomass_emissions = yearly_constant_emissions_breakdown(total, self.time_impl, self.time_cap)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(
                    year = 0,
                    gas_type = GasTypes.CO2,
                    emissions = [Emission(total, GasTypes.CO2) for i in range(self.time_impl + self.time_cap)],
                    # TODO: ask Lorenzo if Biomass Loss or Gain
                    activity = ActivityTypes.BIOMASS_GAIN
                ))
            
            except Exception as e:
                traceback.print_exc()

        def calculate_soc():

            try:
                initial_soc = self.socref * self.initial_flu if not self.initial_soc_tier_2 else self.initial_soc_tier_2
                final_soc = self.socref * self.final_flu if not self.final_soc_tier_2 else self.final_soc_tier_2

                delta_c_soc_20_years = (final_soc - initial_soc)/20
                delta_co2_soc = delta_c_soc_20_years * (-44/12)

                self.yearly_soc_emissions, self.total_soc_emissions = soil_emissions_delta_soc_known(delta_c_soc_20_years, delta_co2_soc, 0, self.area, self.hectars_before_20)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(
                    year = 0,
                    gas_type = GasTypes.CO2,
                    emissions = [Emission(e, GasTypes.CO2) for e in self.yearly_soc_emissions],
                    activity = ActivityTypes.SOIL_CO2_CHANGE
                ))

            except Exception as e:
                traceback.print_exc()

        def calculate_fire():

            initial_soc = self.socref * self.initial_flu if not self.initial_soc_tier_2 else self.initial_soc_tier_2
            final_soc = self.socref * self.final_flu if not self.final_soc_tier_2 else self.final_soc_tier_2

            delta_c_soc = (final_soc - initial_soc)/20

            initial_biomass = self.initial_lu_biomass if not self.initial_lu_biomass_tier_2 else self.initial_lu_biomass_tier_2
            fire_mb = initial_biomass / 0.4
            fsom = 0 if delta_c_soc >= 0 else - (1000 * delta_c_soc)/self.c_n_ratio

            kg_methane_fire = fire_mb * self.combustion_factor * self.emission_factor_methane if self.fire_bool else 0
            kg_nitrous_fire =  initial_biomass * 2.5 * self.combustion_factor * self.emission_factor_nitrous if self.fire_bool else 0

            kg_nitrous_soil = fsom * self.moisture_emission_factor * (44/28)

            methane_emissions = kg_methane_fire * self.methane_constant
            nitrous_emissions = (kg_nitrous_fire + kg_nitrous_soil) * self.nitrous_constant

            total_em_per_hectar = (methane_emissions + nitrous_emissions)/1000

            self.total_fire_emissions = total_em_per_hectar * self.area
            self.yearly_fire_emissions = yearly_constant_emissions_breakdown(self.total_fire_emissions, self.time_impl, self.time_cap)
            
            # CALCULATE FOR INDIVIDUAL METHANE AND NITROUS EMISSIONS(the calculation on top can be removed in the future)
            methane_em_per_hectar = methane_emissions/1000 
            nitrous_em_per_hectar = nitrous_emissions/1000

            methane_fire_emissions = methane_em_per_hectar * self.area
            nitrous_fire_emissions = nitrous_em_per_hectar * self.area

            yearly_methane_fire_emissions = yearly_constant_emissions_breakdown(methane_fire_emissions, self.time_impl, self.time_cap)
            yearly_nitrous_fire_emissions = yearly_constant_emissions_breakdown(nitrous_fire_emissions, self.time_impl, self.time_cap)

            # TODO: check if this is indeed residue burning
            self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(
                year = 0,
                gas_type = GasTypes.CH4,
                emissions = [Emission(e, GasTypes.CH4) for e in yearly_methane_fire_emissions],
                activity = ActivityTypes.RESIDUE_BURNING
            ))

            self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(
                year = 0,
                gas_type = GasTypes.N2O,
                emissions = [Emission(e, GasTypes.N2O) for e in yearly_nitrous_fire_emissions],
                activity = ActivityTypes.RESIDUE_BURNING
            ))
            
        try:
            calculate_biomass()
            calculate_soc()
            calculate_fire()

            self.emissions_total_yearly = [x + y + z for x,y,z in zip(self.yearly_biomass_emissions, self.yearly_soc_emissions, self.yearly_fire_emissions)]
            self.total_emissions = sum(self.emissions_total_yearly)

        except Exception as e:
            traceback.print_exc()

    def evaluate_tier_2_defaults():
        pass



