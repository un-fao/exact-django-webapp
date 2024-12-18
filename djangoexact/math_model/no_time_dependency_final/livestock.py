import re
import traceback

from .general_functions import (
    gas_head_calculation,
    compute_yearly_or_half_year_cumulative,
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
from typing import Optional, List


@dataclass
class Livestock(BaseModule):

    methane_constant: float
    head_number_start: float
    head_number_end: float
    specific_factor_default_start: float
    specific_factor_default_end: float
    specific_factor_start_tier_2: Optional[float]
    specific_factor_end_tier_2: Optional[float]
    ef_prp_methane_start: float
    ef_prp_methane_end: float
    percentage_prp_default_start: float
    percentage_prp_default_end: float
    percentage_prp_tier_2_start: Optional[float]
    percentage_prp_tier_2_end: Optional[float]
    ef_system_methane_start: List[float]
    ef_system_methane_end: List[float]
    ch4_prp_tier_2_start: Optional[float]
    ch4_prp_tier_2_end: Optional[float]
    ch4_system_default_start: float
    ch4_system_default_end: float
    ch4_system_tier_2_start: Optional[float]
    ch4_system_tier_2_end: Optional[float]
    percentage_system_default_start: List[float]
    percentage_system_default_end: float
    tam_start: float
    tam_end: float
    vser_start: float
    vser_end: float
    ef_prp_nitrous_direct_start: float
    ef_prp_nitrous_direct_end: float
    ef_system_nitrous_direct_start: List[float]
    ef_system_nitrous_direct_end: float
    n2o_prp_tier_2_start_direct: Optional[float]
    n2o_prp_tier_2_end_direct: Optional[float]
    n2o_system_direct_default_start: float
    n2o_system_direct_default_end: float
    n2o_system_direct_tier_2_start: Optional[float]
    n2o_system_direct_tier_2_end: Optional[float]
    ner_start: float
    ner_end: float
    ef_prp_nitrous_indirect_volatization_start: float
    ef_prp_nitrous_indirect_volatization_end: float
    ef_system_nitrous_indirect_volatization_start: List[float]
    ef_system_nitrous_indirect_volatization_end: float
    n2o_prp_tier_2_start_indirect_volatization: Optional[float]
    n2o_prp_tier_2_end_indirect_volatization: Optional[float]
    n20_system_indirect_volatization_default_start: float
    n20_system_indirect_volatization_default_end: float
    n20_system_indirect_volatization_tier_2_start: Optional[float]
    n20_system_indirect_volatization_tier_2_end: Optional[float]
    ef_prp_nitrous_indirect_leaching_start: float
    ef_prp_nitrous_indirect_leaching_end: float
    ef_system_nitrous_indirect_leaching_start: List[float]
    ef_system_nitrous_indirect_leaching_end: float
    n2o_prp_tier_2_start_indirect_leaching: Optional[float]
    n2o_prp_tier_2_end_indirect_leaching: Optional[float]
    n20_system_indirect_leaching_default_start: float
    n20_system_indirect_leaching_default_end: float
    n20_system_indirect_leaching_tier_2_start: Optional[float]
    n20_system_indirect_leaching_tier_2_end: Optional[float]
    nitrous_constant: float
    volatilization_multiplier: float
    leaching_multiplier: float

    def __post_init__(self):
        super().__post_init__()

        self.ch4_system_head_start_tier_2_default = None
        self.percentage_prp_start_tier_2_default = None
        self.ch4_system_head_end_tier_2_default = None
        self.percentage_prp_end_tier_2_default = None

        self.n2o_system_direct_head_start_tier_2_default = None
        self.n2o_prp_direct_head_start_tier_2_default = None
        self.n2o_system_direct_head_end_tier_2_default = None
        self.n2o_prp_direct_head_end_tier_2_default = None

        self.livestock_heads_yearly_breakdown = compute_yearly_or_half_year_cumulative(self.head_number_start, self.head_number_end, self.implementation_time, self.capitalization_time, self.rate_type)


    def calculate_emissions(self):
        def calculate_methane_enteric_fermentation_emissions():
            try:
                specific_factor_start = self.specific_factor_default_start if not self.specific_factor_start_tier_2 else self.specific_factor_start_tier_2
                specific_factor_end = self.specific_factor_default_end if not self.specific_factor_end_tier_2 else self.specific_factor_end_tier_2

                emissions_start = specific_factor_start / 1000 * self.methane_constant * self.head_number_start
                emissions_end = specific_factor_end / 1000 * self.methane_constant * self.head_number_end

                mef_emissions_yearly = compute_yearly_or_half_year_cumulative(emissions_start, emissions_end, self.implementation_time, self.capitalization_time, self.rate_type)

                mef_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in mef_emissions_yearly], ActivityTypes.METHANE_ENTERIC_FERMENTATION, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(mef_emission_set)

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_methane_manure_management_emissions():
            try:
                if len(self.ef_system_methane_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_methane_start and percentage_system_default_start should be same")
                
                ch4_head_start, ch4_system_head_start, percentage_prp_start = gas_head_calculation(self.tam_start, self.vser_start, self.ef_prp_methane_start, self.percentage_prp_default_start, self.percentage_prp_tier_2_start, self.ef_system_methane_start, self.ch4_prp_tier_2_start, self.percentage_system_default_start, self.ch4_system_default_start, self.ch4_system_tier_2_start, 1000)
                ch4_head_end, ch4_system_head_end, percentage_prp_end = gas_head_calculation(self.tam_end, self.vser_end, self.ef_prp_methane_end, self.percentage_prp_default_end, self.percentage_prp_tier_2_end, self.ef_system_methane_end, self.ch4_prp_tier_2_end, self.percentage_system_default_end, self.ch4_system_default_end, self.ch4_system_tier_2_end, 1000)
                
                # NOTE: in future change name of percentage_prp_tier_2_default as it represents ch4_prp (TIER 2 Assignment)
                self.ch4_system_head_start_tier_2_default = ch4_system_head_start
                self.percentage_prp_start_tier_2_default = percentage_prp_start
                self.ch4_system_head_end_tier_2_default = ch4_system_head_end
                self.percentage_prp_end_tier_2_default = percentage_prp_end

                # Calculate emissions, broken down between prp and system
                annual_start_system = sum(ch4_system_head_start) * self.head_number_start / 1000 * self.methane_constant
                annual_end_system = sum(ch4_system_head_end) * self.head_number_end / 1000 * self.methane_constant

                mmm_emissions_system_yearly = compute_yearly_or_half_year_cumulative(annual_start_system, annual_end_system, self.implementation_time, self.capitalization_time, self.rate_type)

                annual_start_prp = percentage_prp_start * self.head_number_start / 1000 * self.methane_constant
                annual_end_prp = percentage_prp_end * self.head_number_end / 1000 * self.methane_constant

                mmm_emissions_prp_yearly = compute_yearly_or_half_year_cumulative(annual_start_prp, annual_end_prp, self.implementation_time, self.capitalization_time, self.rate_type)

                mmm_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in mmm_emissions_system_yearly], ActivityTypes.METHANE_MANURE_MANAGEMENT_SYSTEM, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(mmm_emission_set)

                mmm_emission_set_prp = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in mmm_emissions_prp_yearly], ActivityTypes.METHANE_MANURE_MANAGEMENT_PRP, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(mmm_emission_set_prp)

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_nitrous_manure_management_direct():
            try:
                if len(self.ef_system_nitrous_direct_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_nitrous_direct_start and percentage_system_default_start should be same")
                
                n2o_head_start, n2o_system_direct_head_start, n2o_prp_direct_head_start  = gas_head_calculation(self.tam_start, self.ner_start, self.ef_prp_nitrous_direct_start, self.percentage_prp_default_start, self.percentage_prp_tier_2_start, self.ef_system_nitrous_direct_start, self.n2o_prp_tier_2_start_direct, self.percentage_system_default_start, self.n2o_system_direct_default_start, self.n2o_system_direct_tier_2_start)
                n2o_head_end, n2o_system_direct_head_end, n2o_prp_direct_head_end = gas_head_calculation(self.tam_end, self.ner_end, self.ef_prp_nitrous_direct_end, self.percentage_prp_default_end, self.percentage_prp_tier_2_end, self.ef_system_nitrous_direct_end, self.n2o_prp_tier_2_end_direct, self.percentage_system_default_end, self.n2o_system_direct_default_end, self.n2o_system_direct_tier_2_end)

                self.n2o_system_direct_head_start_tier_2_default = n2o_system_direct_head_start
                self.n2o_prp_direct_head_start_tier_2_default = n2o_prp_direct_head_start
                self.n2o_system_direct_head_end_tier_2_default = n2o_system_direct_head_end
                self.n2o_prp_direct_head_end_tier_2_default = n2o_prp_direct_head_end

                # SYSTEM AND PRP EMISSIONS

                annual_start_system_n2o = sum(n2o_system_direct_head_start) * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant
                annual_end_system_n2o = sum(n2o_system_direct_head_end) * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant

                nmm_direct_emissions_yearly = compute_yearly_or_half_year_cumulative(annual_start_system_n2o, annual_end_system_n2o, self.implementation_time, self.capitalization_time, self.rate_type)

                nmm_emission_set_system = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in nmm_direct_emissions_yearly], ActivityTypes.NITROUS_MANURE_MANAGEMENT_SYSTEM, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(nmm_emission_set_system)

                annual_start_prp_n2o = n2o_prp_direct_head_start * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant
                annual_end_prp_n2o = n2o_prp_direct_head_end * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant

                nmm_emissions_prp_yearly = compute_yearly_or_half_year_cumulative(annual_start_prp_n2o, annual_end_prp_n2o, self.implementation_time, self.capitalization_time, self.rate_type)

                nmm_emission_set_prp = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in nmm_emissions_prp_yearly], ActivityTypes.NITROUS_MANURE_MANAGEMENT_PRP, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(nmm_emission_set_prp)

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_nitrous_manure_management_indirect_volatization():
            try:

                if len(self.ef_system_nitrous_indirect_volatization_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_nitrous_indirect_volatization_start and percentage_system_default_start should be same")
                
                n2o_head_start, n2o_head_system_start, n2o_head_prp_start = gas_head_calculation(self.tam_start, self.ner_start, self.ef_prp_nitrous_indirect_volatization_start, self.percentage_prp_default_start, self.percentage_prp_tier_2_start, self.ef_system_nitrous_indirect_volatization_start, self.n2o_prp_tier_2_start_indirect_volatization, self.percentage_system_default_start, self.n20_system_indirect_volatization_default_start, self.n20_system_indirect_volatization_tier_2_start)
                n2o_head_end, n2o_heah_system_end, n2o_head_prp_end = gas_head_calculation(self.tam_end, self.ner_end, self.ef_prp_nitrous_indirect_volatization_end, self.percentage_prp_default_end, self.percentage_prp_tier_2_end, self.ef_system_nitrous_indirect_volatization_end, self.n2o_prp_tier_2_end_indirect_volatization, self.percentage_system_default_end, self.n20_system_indirect_volatization_default_end, self.n20_system_indirect_volatization_tier_2_end)

                annual_start_system = sum(n2o_head_system_start) * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant * self.volatilization_multiplier
                annual_end_system = sum(n2o_heah_system_end) * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant * self.volatilization_multiplier


                # NOTE MAYBE A GENERALIZED FUNCTION CAN BE DONE FOR THIS NOW?
                nmm_indirect_volatization_emissions_yearly_system = compute_yearly_or_half_year_cumulative(annual_start_system, annual_end_system, self.implementation_time, self.capitalization_time, self.rate_type)

                nmm_indirect_volatization_emission_set_system = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in nmm_indirect_volatization_emissions_yearly_system], ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_SYSTEM, delay=self.delay)

                self.result.yearly_emissions_by_sector_by_gas.append(nmm_indirect_volatization_emission_set_system)

                annual_start_prp = n2o_head_prp_start * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant * self.volatilization_multiplier
                annual_end_prp = n2o_head_prp_end * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant * self.volatilization_multiplier

                nmm_indirect_volatization_emissions_yearly_prp = compute_yearly_or_half_year_cumulative(annual_start_prp, annual_end_prp, self.implementation_time, self.capitalization_time, self.rate_type)

                nmm_indirect_volatization_emission_set_prp = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in nmm_indirect_volatization_emissions_yearly_prp], ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_PRP, delay=self.delay)

                self.result.yearly_emissions_by_sector_by_gas.append(nmm_indirect_volatization_emission_set_prp)


            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_nitrous_manure_management_indirect_leaching():
            try:

                if len(self.ef_system_nitrous_indirect_leaching_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_nitrous_indirect_leaching_start and percentage_system_default_start should be same")
                
                n2o_head_start, n2o_system_start, n2o_prp_start = gas_head_calculation(self.tam_start, self.ner_start, self.ef_prp_nitrous_indirect_leaching_start, self.percentage_prp_default_start, self.percentage_prp_tier_2_start, self.ef_system_nitrous_indirect_leaching_start, self.n2o_prp_tier_2_start_indirect_leaching, self.percentage_system_default_start, self.n20_system_indirect_leaching_default_start, self.n20_system_indirect_leaching_tier_2_start)
                n2o_head_end, n2o_system_end, n2o_prp_end = gas_head_calculation(self.tam_end, self.ner_end, self.ef_prp_nitrous_indirect_leaching_end, self.percentage_prp_default_end, self.percentage_prp_tier_2_end, self.ef_system_nitrous_indirect_leaching_end, self.n2o_prp_tier_2_end_indirect_leaching, self.percentage_system_default_end, self.n20_system_indirect_leaching_default_end, self.n20_system_indirect_leaching_tier_2_end)

                annual_start_system = sum(n2o_system_start) * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant * self.leaching_multiplier
                annual_end_system = sum(n2o_system_end) * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant * self.leaching_multiplier

                nmm_indirect_leaching_emissions_yearly_system = compute_yearly_or_half_year_cumulative(annual_start_system, annual_end_system, self.implementation_time, self.capitalization_time, self.rate_type)

                nmm_indirect_leaching_emission_set_system = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in nmm_indirect_leaching_emissions_yearly_system], ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM, delay=self.delay)

                self.result.yearly_emissions_by_sector_by_gas.append(nmm_indirect_leaching_emission_set_system)

                annual_start_prp = n2o_prp_start * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant * self.leaching_multiplier
                annual_end_prp = n2o_prp_end * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant * self.leaching_multiplier

                nmm_indirect_leaching_emissions_yearly_prp = compute_yearly_or_half_year_cumulative(annual_start_prp, annual_end_prp, self.implementation_time, self.capitalization_time, self.rate_type)

                nmm_indirect_leaching_emission_set_prp = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in nmm_indirect_leaching_emissions_yearly_prp], ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_PRP, delay=self.delay)

                self.result.yearly_emissions_by_sector_by_gas.append(nmm_indirect_leaching_emission_set_prp)

            except Exception as e:
                traceback.print_exc()
                raise e

        calculate_methane_enteric_fermentation_emissions()
        calculate_methane_manure_management_emissions()
        calculate_nitrous_manure_management_direct()
        calculate_nitrous_manure_management_indirect_volatization()
        calculate_nitrous_manure_management_indirect_leaching()




