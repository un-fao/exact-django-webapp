import re
import traceback

from .general_functions import (
    BaseModule,
    ch4_head_calculation_general,
    yearly_time_dependent_parameter_breakdown,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)


class Livestock(BaseModule):
    def __init__(
        self,
        time_impl,
        time_cap,
        rate,
        methane_constant,
        head_number_start,
        head_number_end,
        specific_factor_default_start,
        specific_factor_default_end,
        specific_factor_start_tier_2,
        specific_factor_end_tier_2,  # METHANE ENTERIC FERMENTATION EMISSIONS PARAMETERS
        ef_prp_methane_start,
        ef_prp_methane_end,
        percentage_prp_default_start,
        percentage_prp_default_end,
        percentage_prp_tier_2_start,
        percentage_prp_tier_2_end,
        ef_system_methane_start,
        ef_system_methane_end,
        ch4_prp_tier_2_start,
        ch4_prp_tier_2_end,
        ch4_system_default_start,
        ch4_system_default_end,
        ch4_system_tier_2_start,
        ch4_system_tier_2_end,  # METHANE MANURE MANAGEMENT EMISSIONS PARAMETERS
        percentage_system_default_start,
        percentage_system_default_end,
        tam_start,
        tam_end,
        vser_start,
        vser_end,  # METHANE MANURE MANAGEMENT EMISSIONS PARAMETERS
        ef_prp_nitrous_direct_start,
        ef_prp_nitrous_direct_end,
        ef_system_nitrous_direct_start,
        ef_system_nitrous_direct_end,
        n2o_prp_tier_2_start_direct,
        n2o_prp_tier_2_end_direct,
        n2o_system_direct_default_start,
        n2o_system_direct_default_end,
        n2o_system_direct_tier_2_start,
        n2o_system_direct_tier_2_end,
        ner_start,
        ner_end,  # NITROUS OXIDE MANURE MANAGEMENT EMISSIONS PARAMETERS DIRECT
        ef_prp_nitrous_indirect_volatization_start,
        ef_prp_nitrous_indirect_volatization_end,
        ef_system_nitrous_indirect_volatization_start,
        ef_system_nitrous_indirect_volatization_end,
        n2o_prp_tier_2_start_indirect_volatization,
        n2o_prp_tier_2_end_indirect_volatization,
        n20_system_indirect_volatization_default_start,
        n20_system_indirect_volatization_default_end,
        n20_system_indirect_volatization_tier_2_start,
        n20_system_indirect_volatization_tier_2_end,  # NITROUS OXIDE MANURE MANAGEMENT EMISSIONS PARAMETERS INDIRECT VOLATIZATION
        ef_prp_nitrous_indirect_leaching_start,
        ef_prp_nitrous_indirect_leaching_end,
        ef_system_nitrous_indirect_leaching_start,
        ef_system_nitrous_indirect_leaching_end,
        n2o_prp_tier_2_start_indirect_leaching,
        n2o_prp_tier_2_end_indirect_leaching,
        n20_system_indirect_leaching_default_start,
        n20_system_indirect_leaching_default_end,
        n20_system_indirect_leaching_tier_2_start,
        n20_system_indirect_leaching_tier_2_end,  # NITROUS OXIDE MANURE MANAGEMENT EMISSIONS PARAMETERS INDIRECT LEACHING
        nitrous_constant,
        volatilization_multiplier,
        leaching_multiplier,
    ):
        # INPUT PARAMETERS
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate = rate
        self.methane_constant = methane_constant
        self.head_number_start = head_number_start
        self.head_number_end = head_number_end

        self.specific_factor_default_start = specific_factor_default_start
        self.specific_factor_default_end = specific_factor_default_end
        self.specific_factor_start_tier_2 = specific_factor_start_tier_2
        self.specific_factor_end_tier_2 = specific_factor_end_tier_2

        self.ef_prp_methane_start = ef_prp_methane_start
        self.ef_prp_methane_end = ef_prp_methane_end
        self.percentage_prp_default_start = percentage_prp_default_start
        self.percentage_prp_default_end = percentage_prp_default_end
        self.percentage_prp_tier_2_start = percentage_prp_tier_2_start
        self.percentage_prp_tier_2_end = percentage_prp_tier_2_end
        self.ef_system_methane_start = ef_system_methane_start
        self.ef_system_methane_end = ef_system_methane_end
        self.ch4_prp_tier_2_start = ch4_prp_tier_2_start
        self.ch4_prp_tier_2_end = ch4_prp_tier_2_end
        self.ch4_system_default_start = ch4_system_default_start
        self.ch4_system_default_end = ch4_system_default_end
        self.ch4_system_tier_2_start = ch4_system_tier_2_start
        self.ch4_system_tier_2_end = ch4_system_tier_2_end

        self.percentage_system_default_start = percentage_system_default_start
        self.percentage_system_default_end = percentage_system_default_end
        self.tam_start = tam_start
        self.tam_end = tam_end
        self.vser_start = vser_start
        self.vser_end = vser_end

        self.ef_prp_nitrous_direct_start = ef_prp_nitrous_direct_start
        self.ef_prp_nitrous_direct_end = ef_prp_nitrous_direct_end
        self.ef_system_nitrous_direct_start = ef_system_nitrous_direct_start
        self.ef_system_nitrous_direct_end = ef_system_nitrous_direct_end
        self.n2o_prp_tier_2_start_direct = n2o_prp_tier_2_start_direct
        self.n2o_prp_tier_2_end_direct = n2o_prp_tier_2_end_direct
        self.n2o_system_direct_default_start = n2o_system_direct_default_start
        self.n2o_system_direct_default_end = n2o_system_direct_default_end
        self.n2o_system_direct_tier_2_start = n2o_system_direct_tier_2_start
        self.n2o_system_direct_tier_2_end = n2o_system_direct_tier_2_end
        self.ner_start = ner_start
        self.ner_end = ner_end

        self.ef_prp_nitrous_indirect_volatization_start = ef_prp_nitrous_indirect_volatization_start
        self.ef_prp_nitrous_indirect_volatization_end = ef_prp_nitrous_indirect_volatization_end
        self.ef_system_nitrous_indirect_volatization_start = ef_system_nitrous_indirect_volatization_start
        self.ef_system_nitrous_indirect_volatization_end = ef_system_nitrous_indirect_volatization_end
        # TODO: on notion is not there. Is it same for vol/leach/direct?
        self.n2o_prp_tier_2_start_indirect_volatization = n2o_prp_tier_2_start_indirect_volatization
        self.n2o_prp_tier_2_end_indirect_volatization = n2o_prp_tier_2_end_indirect_volatization

        self.n20_system_indirect_volatization_default_start = n20_system_indirect_volatization_default_start
        self.n20_system_indirect_volatization_default_end = n20_system_indirect_volatization_default_end
        self.n20_system_indirect_volatization_tier_2_start = n20_system_indirect_volatization_tier_2_start
        self.n20_system_indirect_volatization_tier_2_end = n20_system_indirect_volatization_tier_2_end

        self.ef_prp_nitrous_indirect_leaching_start = ef_prp_nitrous_indirect_leaching_start
        self.ef_prp_nitrous_indirect_leaching_end = ef_prp_nitrous_indirect_leaching_end
        self.ef_system_nitrous_indirect_leaching_start = ef_system_nitrous_indirect_leaching_start
        self.ef_system_nitrous_indirect_leaching_end = ef_system_nitrous_indirect_leaching_end
        self.n2o_prp_tier_2_start_indirect_leaching = n2o_prp_tier_2_start_indirect_leaching
        self.n2o_prp_tier_2_end_indirect_leaching = n2o_prp_tier_2_end_indirect_leaching
        self.n20_system_indirect_leaching_default_start = n20_system_indirect_leaching_default_start
        self.n20_system_indirect_leaching_default_end = n20_system_indirect_leaching_default_end
        self.n20_system_indirect_leaching_tier_2_start = n20_system_indirect_leaching_tier_2_start
        self.n20_system_indirect_leaching_tier_2_end = n20_system_indirect_leaching_tier_2_end

        self.nitrous_constant = nitrous_constant
        self.volatilization_multiplier = volatilization_multiplier
        self.leaching_multiplier = leaching_multiplier

        # TIER 2 DEFAULTS
        self.specific_factor_start_tier_2_default = self.specific_factor_default_start
        self.specific_factor_end_tier_2_default = self.specific_factor_default_end
        self.percentage_prp_start_tier_2_default = self.percentage_prp_default_start
        self.percentage_prp_end_tier_2_default = self.percentage_prp_default_end

        self.ch4_prp_start_tier_2_default = self.ch4_system_default_start
        self.ch4_prp_end_tier_2_default = self.ch4_system_default_end
        self.ch4_system_start_tier_2_default = self.ch4_system_default_start
        self.ch4_system_end_tier_2_default = self.ch4_system_default_end

        self.n2o_prp_direct_start_tier_2_default = self.n2o_system_direct_default_start
        self.n2o_prp_direct_end_tier_2_default = self.n2o_system_direct_default_end
        self.n2o_system_direct_start_tier_2_default = self.n2o_system_direct_default_start
        self.n2o_system_direct_end_tier_2_default = self.n2o_system_direct_default_end

        # self.n2o_prp_indirect_volatization_start_tier_2_default = self.n20_system_indirect_volatization_default_start
        # self.n2o_prp_indirect_volatization_end_tier_2_default = self.n20_system_indirect_volatization_default_end
        self.n2o_system_indirect_volatization_start_tier_2_default = self.n20_system_indirect_volatization_default_start
        self.n2o_system_indirect_volatization_end_tier_2_default = self.n20_system_indirect_volatization_default_end

        self.n2o_prp_indirect_leaching_start_tier_2_default = self.ef_system_nitrous_indirect_leaching_start
        self.n2o_prp_indirect_leaching_end_tier_2_default = self.ef_system_nitrous_indirect_leaching_end
        self.n2o_system_indirect_leaching_start_tier_2_default = self.n20_system_indirect_leaching_default_start
        self.n2o_system_indirect_leaching_end_tier_2_default = self.n20_system_indirect_leaching_default_end

        # RESULTS
        self.mef_emissions_yearly = []
        self.mef_emissions = 0

        self.mmm_emissions_yearly = []
        self.mmm_emissions = 0

        self.nmm_direct_emissions_yearly = []
        self.nmm_direct_emissions = 0

        self.nmm_indirect_volatization_emissions_yearly = []
        self.nmm_indirect_volatization_emissions = 0

        self.nmm_indirect_leaching_emissions_yearly = []
        self.nmm_indirect_leaching_emissions = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(time_impl, time_cap)

    def calculate_emissions(self):
        def calculate_methane_enteric_fermentation_emissions():
            try:
                specific_factor_start = self.specific_factor_default_start if not self.specific_factor_start_tier_2 else self.specific_factor_start_tier_2
                specific_factor_end = self.specific_factor_default_end if not self.specific_factor_end_tier_2 else self.specific_factor_end_tier_2

                emissions_start = specific_factor_start / 1000 * self.methane_constant * self.head_number_start
                emissions_end = specific_factor_end / 1000 * self.methane_constant * self.head_number_end

                self.mef_emissions_yearly = yearly_time_dependent_parameter_breakdown(emissions_start, emissions_end, self.time_impl, self.time_cap, self.rate)
                self.mef_emissions = sum(self.mef_emissions_yearly)

                mef_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in self.mef_emissions_yearly], ActivityTypes.METHANE_ENTERIC_FERMENTATION, delay=0)
                self.result.yearly_emissions_by_sector_by_gas.append(mef_emission_set)

            except Exception as e:
                traceback.print_exc()

        def calculate_methane_manure_management_emissions():
            try:
                if len(self.ef_system_methane_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_methane_start and percentage_system_default_start should be same")
                
                ch4_head_start = ch4_head_calculation_general(self.tam_start, self.vser_start, self.ef_prp_methane_start, self.percentage_prp_default_start, self.percentage_prp_tier_2_start, self.ef_system_methane_start, self.ch4_prp_tier_2_start, self.percentage_system_default_start, self.ch4_system_default_start, self.ch4_system_tier_2_start, 1000)
                ch4_head_end = ch4_head_calculation_general(self.tam_end, self.vser_end, self.ef_prp_methane_end, self.percentage_prp_default_end, self.percentage_prp_tier_2_end, self.ef_system_methane_end, self.ch4_prp_tier_2_end, self.percentage_system_default_end, self.ch4_system_default_end, self.ch4_system_tier_2_end, 1000)

                annual_start = ch4_head_start * self.head_number_start / 1000 * self.methane_constant
                annual_end = ch4_head_end * self.head_number_end / 1000 * self.methane_constant

                self.mmm_emissions_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.time_impl, self.time_cap, self.rate)
                self.mmm_emissions = sum(self.mmm_emissions_yearly)

                mmm_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in self.mmm_emissions_yearly], ActivityTypes.METHANE_MANURE_MANAGEMENT, delay=0)
                self.result.yearly_emissions_by_sector_by_gas.append(mmm_emission_set)

            except Exception as e:
                traceback.print_exc()

        def calculate_nitrous_manure_management_direct():
            try:
                if len(self.ef_system_nitrous_direct_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_nitrous_direct_start and percentage_system_default_start should be same")
                
                n2o_head_start = ch4_head_calculation_general(self.tam_start, self.ner_start, self.ef_prp_nitrous_direct_start, self.percentage_prp_default_start, self.percentage_prp_tier_2_start, self.ef_system_nitrous_direct_start, self.n2o_prp_tier_2_start_direct, self.percentage_system_default_start, self.n2o_system_direct_default_start, self.n2o_system_direct_tier_2_start)
                n2o_head_end = ch4_head_calculation_general(self.tam_end, self.ner_end, self.ef_prp_nitrous_direct_end, self.percentage_prp_default_end, self.percentage_prp_tier_2_end, self.ef_system_nitrous_direct_end, self.n2o_prp_tier_2_end_direct, self.percentage_system_default_end, self.n2o_system_direct_default_end, self.n2o_system_direct_tier_2_end)

                annual_start = n2o_head_start * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant
                annual_end = n2o_head_end * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant

                self.nmm_direct_emissions_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.time_impl, self.time_cap, self.rate)
                self.nmm_direct_emissions = sum(self.nmm_direct_emissions_yearly)

                nmm_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in self.nmm_direct_emissions_yearly], ActivityTypes.NITROUS_MANURE_MANAGEMENT, delay=0)
                self.result.yearly_emissions_by_sector_by_gas.append(nmm_emission_set)

            except Exception as e:
                traceback.print_exc()

        def calculate_nitrous_manure_management_indirect_volatization():
            try:

                if len(self.ef_system_nitrous_indirect_volatization_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_nitrous_indirect_volatization_start and percentage_system_default_start should be same")
                
                n2o_head_start = ch4_head_calculation_general(self.tam_start, self.ner_start, self.ef_prp_nitrous_indirect_volatization_start, self.percentage_prp_default_start, self.percentage_prp_tier_2_start, self.ef_system_nitrous_indirect_volatization_start, self.n2o_prp_tier_2_start_indirect_volatization, self.percentage_system_default_start, self.n20_system_indirect_volatization_default_start, self.n20_system_indirect_volatization_tier_2_start)
                n2o_head_end = ch4_head_calculation_general(self.tam_end, self.ner_end, self.ef_prp_nitrous_indirect_volatization_end, self.percentage_prp_default_end, self.percentage_prp_tier_2_end, self.ef_system_nitrous_indirect_volatization_end, self.n2o_prp_tier_2_end_indirect_volatization, self.percentage_system_default_end, self.n20_system_indirect_volatization_default_end, self.n20_system_indirect_volatization_tier_2_end)

                annual_start = n2o_head_start * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant * self.volatilization_multiplier
                annual_end = n2o_head_end * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant * self.volatilization_multiplier

                self.nmm_indirect_volatization_emissions_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.time_impl, self.time_cap, self.rate)
                self.nmm_indirect_volatization_emissions = sum(self.nmm_indirect_volatization_emissions_yearly)

                nmm_indirect_volatization_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in self.nmm_indirect_volatization_emissions_yearly], ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION, delay=0)

                self.result.yearly_emissions_by_sector_by_gas.append(nmm_indirect_volatization_emission_set)

            except Exception as e:
                traceback.print_exc()

        def calculate_nitrous_manure_management_indirect_leaching():
            try:

                if len(self.ef_system_nitrous_indirect_leaching_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_nitrous_indirect_leaching_start and percentage_system_default_start should be same")
                
                n2o_head_start = ch4_head_calculation_general(self.tam_start, self.ner_start, self.ef_prp_nitrous_indirect_leaching_start, self.percentage_prp_default_start, self.percentage_prp_tier_2_start, self.ef_system_nitrous_indirect_leaching_start, self.n2o_prp_tier_2_start_indirect_leaching, self.percentage_system_default_start, self.n20_system_indirect_leaching_default_start, self.n20_system_indirect_leaching_tier_2_start)
                n2o_head_end = ch4_head_calculation_general(self.tam_end, self.ner_end, self.ef_prp_nitrous_indirect_leaching_end, self.percentage_prp_default_end, self.percentage_prp_tier_2_end, self.ef_system_nitrous_indirect_leaching_end, self.n2o_prp_tier_2_end_indirect_leaching, self.percentage_system_default_end, self.n20_system_indirect_leaching_default_end, self.n20_system_indirect_leaching_tier_2_end)

                annual_start = n2o_head_start * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant * self.leaching_multiplier
                annual_end = n2o_head_end * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant * self.leaching_multiplier

                self.nmm_indirect_leaching_emissions_yearly = yearly_time_dependent_parameter_breakdown(annual_start, annual_end, self.time_impl, self.time_cap, self.rate)
                self.nmm_indirect_leaching_emissions = sum(self.nmm_indirect_leaching_emissions_yearly)

                nmm_indirect_leaching_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in self.nmm_indirect_leaching_emissions_yearly], ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING, delay=0)

                self.result.yearly_emissions_by_sector_by_gas.append(nmm_indirect_leaching_emission_set)

            except Exception as e:
                traceback.print_exc()

        calculate_methane_enteric_fermentation_emissions()
        calculate_methane_manure_management_emissions()
        calculate_nitrous_manure_management_direct()
        calculate_nitrous_manure_management_indirect_volatization()
        calculate_nitrous_manure_management_indirect_leaching()
        try:
            self.emissions_total_yearly = [sum(x) for x in zip(self.mef_emissions_yearly, self.mmm_emissions_yearly, self.nmm_direct_emissions_yearly, self.nmm_indirect_volatization_emissions_yearly, self.nmm_indirect_leaching_emissions_yearly)]
            self.total_emissions = sum(self.emissions_total_yearly)

            return self.total_emissions
        except Exception as e:
            traceback.print_exc()

