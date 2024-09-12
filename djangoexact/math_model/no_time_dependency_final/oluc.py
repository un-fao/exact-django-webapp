import re
import traceback

from .general_functions import (
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

from .generalized_modules import BaseModule

from dataclasses import dataclass
from typing import Optional


@dataclass
class OtherLandUseChanges(BaseModule):

    # NOTE: I can't utilize LandModule for this as it does not have area_start and area_end. Maybe we could change LandModule? Not worth it I think
    initial_lu_biomass: float
    initial_lu_biomass_tier_2: Optional[float]
    final_lu_biomass: float
    final_lu_biomass_tier_2: Optional[float]
    c_n_ratio: float
    moisture_emission_factor: float
    combustion_factor: float
    emission_factor_nitrous: float
    emission_factor_methane: float
    nitrous_constant: float
    methane_constant: float
    fire_bool: bool
    soc_start_default: float
    soc_end_default: float
    soc_start_tier_2: Optional[float]
    soc_end_tier_2: Optional[float]
    fmg_start_default: float
    fmg_end_default: float
    fmg_start_tier_2: Optional[float]
    fmg_end_tier_2: Optional[float]
    flu_start_default: float
    flu_end_default: float
    flu_start_tier_2: Optional[float]
    flu_end_tier_2: Optional[float]
    fi_start_default: float
    fi_end_default: float
    fi_start_tier_2: Optional[float]
    fi_end_tier_2: Optional[float]
    calculate_soc_som: bool
    area: float
    dry_matter_end: float

    # NOTE: This is a check that implies that the final module has growth. Meaning it is either Perennial or Forest
    # in this case the growth is calculated in the final module, hence the final_biomass has to be set to 0
    end_module_has_growth : bool

    def __post_init__(self):
        super().__post_init__()

        fmg_start = self.fmg_start_tier_2 or self.fmg_start_default
        fmg_end = self.fmg_end_tier_2 or self.fmg_end_default
        flu_start = self.flu_start_tier_2 or self.flu_start_default
        flu_end = self.flu_end_tier_2 or self.flu_end_default
        fi_start = self.fi_start_tier_2 or self.fi_start_default
        fi_end = self.fi_end_tier_2 or self.fi_end_default
        soc_ref_start = self.soc_start_tier_2 or self.soc_start_default
        soc_ref_end = self.soc_end_tier_2 or self.soc_end_default

        self.soc_start = soc_ref_start * fmg_start * fi_start * flu_start
        self.soc_end = soc_ref_end * fmg_end * fi_end * flu_end
        

    def calculate_emissions(self):
        
        def calculate_biomass():
            try:
                # TODO: talk to Claudio, there is a problem here where there is a value for biomass change in emissions, even though initial and final should be the same
                initial_biomass_without_removal = self.initial_lu_biomass if not self.initial_lu_biomass_tier_2 else self.initial_lu_biomass_tier_2
                initial_biomass_without_removal = self.initial_lu_biomass if not self.initial_lu_biomass_tier_2 else self.initial_lu_biomass_tier_2
                final_biomass = self.final_lu_biomass if not self.final_lu_biomass_tier_2 else self.final_lu_biomass_tier_2

                # NOTE: here we can see the impact of end_module_has_growth, if it is true, the final_biomass is set to 0, it is Perennial or Forest
                if self.end_module_has_growth:
                    final_biomass = 0
                
                conversion_factor_dry_matter = 0.47

                initial_biomass = initial_biomass_without_removal - self.dry_matter_end * conversion_factor_dry_matter

                if initial_biomass < 0:
                    raise ValueError("Initial biomass cannot be negative, dry_matter * 0.47 (conversion factor) should be less than initial biomass")

                conversion_factor_dry_matter = 0.47

                initial_biomass = initial_biomass_without_removal - self.dry_matter_end * conversion_factor_dry_matter

                if initial_biomass < 0:
                    raise ValueError("Initial biomass cannot be negative, dry_matter * 0.47 (conversion factor) should be less than initial biomass")

                delta_c_biomass = (final_biomass - initial_biomass) * (-44 / 12)

                # TODO: add logic for comprehension of amount of hectars addressed in one year (not self.total_hectars) and use that for the breakdown and total
                total = delta_c_biomass * self.area

                total_biomass_emissions = total
                # TODO: change so only in implementation years but proportionate to the hectars addressed in that year
                yearly_biomass_emissions = yearly_constant_emissions_breakdown(total, self.implementation_time, self.capitalization_time, self.rate_type)

                self.result.yearly_emissions_by_sector_by_gas.append(
                    YearlyGasActivityEmissionSet(
                        year=0,
                        gas_type=GasTypes.CO2,
                        emissions=[Emission(e, GasTypes.CO2) for e in yearly_biomass_emissions],
                        # TODO: ask Lorenzo if Biomass Loss or Gain
                        activity=ActivityTypes.BIOMASS,
                        delay=self.delay,
                    )
                )

            except Exception as e:
                traceback.print_exc()

        def calculate_fire():
            delta_c_soc = (self.soc_end - self.soc_start) / 20

            initial_biomass_without_removal = self.initial_lu_biomass if not self.initial_lu_biomass_tier_2 else self.initial_lu_biomass_tier_2

            conversion_factor_dry_matter = 0.47

            initial_biomass = initial_biomass_without_removal - self.dry_matter_end * conversion_factor_dry_matter

            fire_mb = initial_biomass / 0.4

            kg_methane_fire = fire_mb * self.combustion_factor * self.emission_factor_methane if self.fire_bool else 0
            kg_nitrous_fire = initial_biomass * 2.5 * self.combustion_factor * self.emission_factor_nitrous if self.fire_bool else 0

            methane_emissions = kg_methane_fire * self.methane_constant
            nitrous_emissions = kg_nitrous_fire * self.nitrous_constant

            total_em_per_hectar = (methane_emissions + nitrous_emissions) / 1000

            total_fire_emissions = total_em_per_hectar * self.area
            yearly_fire_emissions = yearly_constant_emissions_breakdown(total_fire_emissions, self.implementation_time, self.capitalization_time, self.implementation_time)

            # CALCULATE FOR INDIVIDUAL METHANE AND NITROUS EMISSIONS(the calculation on top can be removed in the future)
            methane_em_per_hectar = methane_emissions / 1000
            nitrous_em_per_hectar = nitrous_emissions / 1000

            # TODO: same as biomass above, breakdown according to hectares addressed in that year
            methane_fire_emissions = methane_em_per_hectar * self.area
            nitrous_fire_emissions = nitrous_em_per_hectar * self.area

            yearly_methane_fire_emissions = yearly_constant_emissions_breakdown(methane_fire_emissions, self.implementation_time, self.capitalization_time, self.rate_type)
            yearly_nitrous_fire_emissions = yearly_constant_emissions_breakdown(nitrous_fire_emissions, self.implementation_time, self.capitalization_time, self.rate_type)

            self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in yearly_methane_fire_emissions], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))
            self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in yearly_nitrous_fire_emissions], activity=ActivityTypes.RESIDUE_BURNING, delay=self.delay))

        try:
            calculate_biomass()
            calculate_fire()

        except Exception as e:
            traceback.print_exc()
