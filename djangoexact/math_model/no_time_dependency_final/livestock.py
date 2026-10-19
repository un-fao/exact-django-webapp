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
from .manure_nitrogen import (
    BEDDING_SYSTEMS,
    DIGESTER,
    codigestate_n2o_n,
    effective_system_shares,
    managed_manure_n_available,
    share_of,
)

from dataclasses import dataclass
from typing import Optional, List
from .ghg_inventory_class import InventoryPerGasPerActivity


@dataclass(kw_only=True)
class Livestock(BaseModule):
    methane_constant: float
    head_number_start: float
    head_number_end: float
    specific_factor_default_start: float
    specific_factor_default_end: float
    specific_factor_start_tier_2: Optional[float] = None
    specific_factor_end_tier_2: Optional[float] = None
    ef_prp_methane_start: float
    ef_prp_methane_end: float
    percentage_prp_default_start: float
    percentage_prp_default_end: float
    percentage_prp_tier_2_start: Optional[float] = None
    percentage_prp_tier_2_end: Optional[float] = None
    ef_system_methane_start: List[float]
    ef_system_methane_end: List[float]
    ch4_prp_tier_2_start: Optional[float] = None
    ch4_prp_tier_2_end: Optional[float] = None
    ch4_system_default_start: float
    ch4_system_default_end: float
    ch4_system_tier_2_start: Optional[float] = None
    ch4_system_tier_2_end: Optional[float] = None
    percentage_system_default_start: List[float]
    percentage_system_default_end: List[float]
    tam_start: float
    tam_end: float
    vser_start: float
    vser_end: float
    ef_prp_nitrous_direct_start: float
    ef_prp_nitrous_direct_end: float
    ef_system_nitrous_direct_start: List[float]
    ef_system_nitrous_direct_end: float
    n2o_prp_tier_2_start_direct: Optional[float] = None
    n2o_prp_tier_2_end_direct: Optional[float] = None
    n2o_system_direct_default_start: float
    n2o_system_direct_default_end: float
    n2o_system_direct_tier_2_start: Optional[float] = None
    n2o_system_direct_tier_2_end: Optional[float] = None
    ner_start: float
    ner_end: float
    ef_prp_nitrous_indirect_volatization_start: float
    ef_prp_nitrous_indirect_volatization_end: float
    ef_system_nitrous_indirect_volatization_start: List[float]
    ef_system_nitrous_indirect_volatization_end: float
    n2o_prp_tier_2_start_indirect_volatization: Optional[float] = None
    n2o_prp_tier_2_end_indirect_volatization: Optional[float] = None
    n20_system_indirect_volatization_default_start: float
    n20_system_indirect_volatization_default_end: float
    n20_system_indirect_volatization_tier_2_start: Optional[float] = None
    n20_system_indirect_volatization_tier_2_end: Optional[float] = None
    ef_prp_nitrous_indirect_leaching_start: float
    ef_prp_nitrous_indirect_leaching_end: float
    ef_system_nitrous_indirect_leaching_start: List[float]
    ef_system_nitrous_indirect_leaching_end: float
    n2o_prp_tier_2_start_indirect_leaching: Optional[float] = None
    n2o_prp_tier_2_end_indirect_leaching: Optional[float] = None
    n20_system_indirect_leaching_default_start: float
    n20_system_indirect_leaching_default_end: float
    n20_system_indirect_leaching_tier_2_start: Optional[float] = None
    n20_system_indirect_leaching_tier_2_end: Optional[float] = None
    nitrous_constant: float
    volatilization_multiplier: float
    leaching_multiplier: float
    # Names of the managed systems, aligned with percentage_system_default_*; needed to place co-digestate and bedding N.
    manure_system_names_start: Optional[List[Optional[str]]] = None
    manure_system_names_end: Optional[List[Optional[str]]] = None
    codigestate_n_start: Optional[float] = None
    codigestate_n_end: Optional[float] = None
    bedding_n_start: Optional[float] = None
    bedding_n_end: Optional[float] = None

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

        self.managed_manure_n_available_start = None
        self.managed_manure_n_available_end = None

    def _manure_n_period(self, names, percentage_system, percentage_prp_default, percentage_prp_tier_2, ef3, frac_gas, frac_leach, n_cdg, n_bedding, heads, tam, ner):
        """Co-digestate N2O-N (direct, volatilised, leached; kg N2O-N/yr) and managed manure N available (kg N/yr) for one period."""
        shares = effective_system_shares(percentage_system, percentage_prp_default, percentage_prp_tier_2)
        names = names or [None] * len(shares)
        if n_cdg and share_of(names, shares, [DIGESTER]) == 0:
            raise ValueError("Co-digestate N needs a share of manure managed in an anaerobic digester.")
        if n_bedding and share_of(names, shares, BEDDING_SYSTEMS) == 0:
            raise ValueError("Co-bedding N needs a share of manure in solid storage or deep bedding.")

        cdg_n2o_n = (0.0, 0.0, 0.0)
        if n_cdg:
            i = names.index(DIGESTER)
            cdg_n2o_n = codigestate_n2o_n(n_cdg, ef3[i], frac_gas[i], frac_leach[i], self.volatilization_multiplier, self.leaching_multiplier)

        nex = tam / 1000 * ner * 365
        available = managed_manure_n_available(heads, nex, names, shares, ef3, frac_gas, frac_leach, n_cdg or 0.0, n_bedding or 0.0)
        return cdg_n2o_n, available

    def calculate_emissions(self):
        def calculate_methane_enteric_fermentation_emissions():
            try:
                specific_factor_start = self.specific_factor_default_start if self.specific_factor_start_tier_2 is None else self.specific_factor_start_tier_2
                specific_factor_end = self.specific_factor_default_end if self.specific_factor_end_tier_2 is None else self.specific_factor_end_tier_2

                emissions_start = specific_factor_start / 1000 * self.methane_constant * self.head_number_start
                emissions_end = specific_factor_end / 1000 * self.methane_constant * self.head_number_end

                mef_emissions_yearly = compute_yearly_or_half_year_cumulative(emissions_start, emissions_end, self.implementation_time, self.capitalization_time, self.rate_type)

                mef_emission_set = YearlyGasActivityEmissionSet(
                    0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in mef_emissions_yearly], ActivityTypes.METHANE_ENTERIC_FERMENTATION, delay=self.delay
                )
                self.result.yearly_emissions_by_sector_by_gas.append(mef_emission_set)
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CH4, emissions_start, ActivityTypes.METHANE_ENTERIC_FERMENTATION))

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_methane_manure_management_emissions():
            try:
                if len(self.ef_system_methane_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_methane_start and percentage_system_default_start should be same")

                ch4_head_start, ch4_system_head_start, percentage_prp_start = gas_head_calculation(
                    self.tam_start,
                    self.vser_start,
                    self.ef_prp_methane_start,
                    self.percentage_prp_default_start,
                    self.percentage_prp_tier_2_start,
                    self.ef_system_methane_start,
                    self.ch4_prp_tier_2_start,
                    self.percentage_system_default_start,
                    self.ch4_system_default_start,
                    self.ch4_system_tier_2_start,
                    1000,
                )
                ch4_head_end, ch4_system_head_end, percentage_prp_end = gas_head_calculation(
                    self.tam_end,
                    self.vser_end,
                    self.ef_prp_methane_end,
                    self.percentage_prp_default_end,
                    self.percentage_prp_tier_2_end,
                    self.ef_system_methane_end,
                    self.ch4_prp_tier_2_end,
                    self.percentage_system_default_end,
                    self.ch4_system_default_end,
                    self.ch4_system_tier_2_end,
                    1000,
                )

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

                mmm_emission_set = YearlyGasActivityEmissionSet(
                    0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in mmm_emissions_system_yearly], ActivityTypes.METHANE_MANURE_MANAGEMENT_SYSTEM, delay=self.delay
                )
                self.result.yearly_emissions_by_sector_by_gas.append(mmm_emission_set)
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CH4, annual_start_system, ActivityTypes.METHANE_MANURE_MANAGEMENT_SYSTEM))

                mmm_emission_set_prp = YearlyGasActivityEmissionSet(
                    0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in mmm_emissions_prp_yearly], ActivityTypes.METHANE_MANURE_MANAGEMENT_PRP, delay=self.delay
                )
                self.result.yearly_emissions_by_sector_by_gas.append(mmm_emission_set_prp)
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CH4, annual_start_prp, ActivityTypes.METHANE_MANURE_MANAGEMENT_PRP))

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_nitrous_manure_management_direct():
            try:
                if len(self.ef_system_nitrous_direct_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_nitrous_direct_start and percentage_system_default_start should be same")

                n2o_head_start, n2o_system_direct_head_start, n2o_prp_direct_head_start = gas_head_calculation(
                    self.tam_start,
                    self.ner_start,
                    self.ef_prp_nitrous_direct_start,
                    self.percentage_prp_default_start,
                    self.percentage_prp_tier_2_start,
                    self.ef_system_nitrous_direct_start,
                    self.n2o_prp_tier_2_start_direct,
                    self.percentage_system_default_start,
                    self.n2o_system_direct_default_start,
                    self.n2o_system_direct_tier_2_start,
                )
                n2o_head_end, n2o_system_direct_head_end, n2o_prp_direct_head_end = gas_head_calculation(
                    self.tam_end,
                    self.ner_end,
                    self.ef_prp_nitrous_direct_end,
                    self.percentage_prp_default_end,
                    self.percentage_prp_tier_2_end,
                    self.ef_system_nitrous_direct_end,
                    self.n2o_prp_tier_2_end_direct,
                    self.percentage_system_default_end,
                    self.n2o_system_direct_default_end,
                    self.n2o_system_direct_tier_2_end,
                )

                self.n2o_system_direct_head_start_tier_2_default = n2o_system_direct_head_start
                self.n2o_prp_direct_head_start_tier_2_default = n2o_prp_direct_head_start
                self.n2o_system_direct_head_end_tier_2_default = n2o_system_direct_head_end
                self.n2o_prp_direct_head_end_tier_2_default = n2o_prp_direct_head_end

                # SYSTEM AND PRP EMISSIONS

                annual_start_system_n2o = sum(n2o_system_direct_head_start) * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant + cdg_start[0] / 1000 * 44 / 28 * self.nitrous_constant
                annual_end_system_n2o = sum(n2o_system_direct_head_end) * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant + cdg_end[0] / 1000 * 44 / 28 * self.nitrous_constant

                nmm_direct_emissions_yearly = compute_yearly_or_half_year_cumulative(annual_start_system_n2o, annual_end_system_n2o, self.implementation_time, self.capitalization_time, self.rate_type)

                nmm_emission_set_system = YearlyGasActivityEmissionSet(
                    0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in nmm_direct_emissions_yearly], ActivityTypes.NITROUS_MANURE_MANAGEMENT_SYSTEM, delay=self.delay
                )
                self.result.yearly_emissions_by_sector_by_gas.append(nmm_emission_set_system)
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.N2O, annual_start_system_n2o, ActivityTypes.NITROUS_MANURE_MANAGEMENT_SYSTEM))

                annual_start_prp_n2o = n2o_prp_direct_head_start * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant
                annual_end_prp_n2o = n2o_prp_direct_head_end * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant

                nmm_emissions_prp_yearly = compute_yearly_or_half_year_cumulative(annual_start_prp_n2o, annual_end_prp_n2o, self.implementation_time, self.capitalization_time, self.rate_type)

                nmm_emission_set_prp = YearlyGasActivityEmissionSet(
                    0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in nmm_emissions_prp_yearly], ActivityTypes.NITROUS_MANURE_MANAGEMENT_PRP, delay=self.delay
                )
                self.result.yearly_emissions_by_sector_by_gas.append(nmm_emission_set_prp)
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.N2O, annual_start_prp_n2o, ActivityTypes.NITROUS_MANURE_MANAGEMENT_PRP))

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_nitrous_manure_management_indirect_volatization():
            try:
                if len(self.ef_system_nitrous_indirect_volatization_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_nitrous_indirect_volatization_start and percentage_system_default_start should be same")

                n2o_head_start, n2o_head_system_start, n2o_head_prp_start = gas_head_calculation(
                    self.tam_start,
                    self.ner_start,
                    self.ef_prp_nitrous_indirect_volatization_start,
                    self.percentage_prp_default_start,
                    self.percentage_prp_tier_2_start,
                    self.ef_system_nitrous_indirect_volatization_start,
                    self.n2o_prp_tier_2_start_indirect_volatization,
                    self.percentage_system_default_start,
                    self.n20_system_indirect_volatization_default_start,
                    self.n20_system_indirect_volatization_tier_2_start,
                )
                n2o_head_end, n2o_heah_system_end, n2o_head_prp_end = gas_head_calculation(
                    self.tam_end,
                    self.ner_end,
                    self.ef_prp_nitrous_indirect_volatization_end,
                    self.percentage_prp_default_end,
                    self.percentage_prp_tier_2_end,
                    self.ef_system_nitrous_indirect_volatization_end,
                    self.n2o_prp_tier_2_end_indirect_volatization,
                    self.percentage_system_default_end,
                    self.n20_system_indirect_volatization_default_end,
                    self.n20_system_indirect_volatization_tier_2_end,
                )

                annual_start_system = sum(n2o_head_system_start) * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant * self.volatilization_multiplier + cdg_start[1] / 1000 * 44 / 28 * self.nitrous_constant
                annual_end_system = sum(n2o_heah_system_end) * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant * self.volatilization_multiplier + cdg_end[1] / 1000 * 44 / 28 * self.nitrous_constant

                # NOTE MAYBE A GENERALIZED FUNCTION CAN BE DONE FOR THIS NOW?
                nmm_indirect_volatization_emissions_yearly_system = compute_yearly_or_half_year_cumulative(
                    annual_start_system, annual_end_system, self.implementation_time, self.capitalization_time, self.rate_type
                )

                nmm_indirect_volatization_emission_set_system = YearlyGasActivityEmissionSet(
                    0,
                    GasTypes.N2O,
                    [Emission(e, GasTypes.N2O) for e in nmm_indirect_volatization_emissions_yearly_system],
                    ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_SYSTEM,
                    delay=self.delay,
                )

                self.result.yearly_emissions_by_sector_by_gas.append(nmm_indirect_volatization_emission_set_system)
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.N2O, 0, ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_SYSTEM))

                annual_start_prp = n2o_head_prp_start * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant * self.volatilization_multiplier
                annual_end_prp = n2o_head_prp_end * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant * self.volatilization_multiplier

                nmm_indirect_volatization_emissions_yearly_prp = compute_yearly_or_half_year_cumulative(
                    annual_start_prp, annual_end_prp, self.implementation_time, self.capitalization_time, self.rate_type
                )

                nmm_indirect_volatization_emission_set_prp = YearlyGasActivityEmissionSet(
                    0,
                    GasTypes.N2O,
                    [Emission(e, GasTypes.N2O) for e in nmm_indirect_volatization_emissions_yearly_prp],
                    ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_PRP,
                    delay=self.delay,
                )

                self.result.yearly_emissions_by_sector_by_gas.append(nmm_indirect_volatization_emission_set_prp)
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.N2O, 0, ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_PRP))

            except Exception as e:
                traceback.print_exc()
                raise e

        def calculate_nitrous_manure_management_indirect_leaching():
            try:
                if len(self.ef_system_nitrous_indirect_leaching_start) != len(self.percentage_system_default_start):
                    raise Exception("Length of ef_system_nitrous_indirect_leaching_start and percentage_system_default_start should be same")

                n2o_head_start, n2o_system_start, n2o_prp_start = gas_head_calculation(
                    self.tam_start,
                    self.ner_start,
                    self.ef_prp_nitrous_indirect_leaching_start,
                    self.percentage_prp_default_start,
                    self.percentage_prp_tier_2_start,
                    self.ef_system_nitrous_indirect_leaching_start,
                    self.n2o_prp_tier_2_start_indirect_leaching,
                    self.percentage_system_default_start,
                    self.n20_system_indirect_leaching_default_start,
                    self.n20_system_indirect_leaching_tier_2_start,
                )
                n2o_head_end, n2o_system_end, n2o_prp_end = gas_head_calculation(
                    self.tam_end,
                    self.ner_end,
                    self.ef_prp_nitrous_indirect_leaching_end,
                    self.percentage_prp_default_end,
                    self.percentage_prp_tier_2_end,
                    self.ef_system_nitrous_indirect_leaching_end,
                    self.n2o_prp_tier_2_end_indirect_leaching,
                    self.percentage_system_default_end,
                    self.n20_system_indirect_leaching_default_end,
                    self.n20_system_indirect_leaching_tier_2_end,
                )

                annual_start_system = sum(n2o_system_start) * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant * self.leaching_multiplier + cdg_start[2] / 1000 * 44 / 28 * self.nitrous_constant
                annual_end_system = sum(n2o_system_end) * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant * self.leaching_multiplier + cdg_end[2] / 1000 * 44 / 28 * self.nitrous_constant

                nmm_indirect_leaching_emissions_yearly_system = compute_yearly_or_half_year_cumulative(
                    annual_start_system, annual_end_system, self.implementation_time, self.capitalization_time, self.rate_type
                )

                nmm_indirect_leaching_emission_set_system = YearlyGasActivityEmissionSet(
                    0,
                    GasTypes.N2O,
                    [Emission(e, GasTypes.N2O) for e in nmm_indirect_leaching_emissions_yearly_system],
                    ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM,
                    delay=self.delay,
                )

                self.result.yearly_emissions_by_sector_by_gas.append(nmm_indirect_leaching_emission_set_system)
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.N2O, 0, ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM))

                annual_start_prp = n2o_prp_start * self.head_number_start / 1000 * 44 / 28 * self.nitrous_constant * self.leaching_multiplier
                annual_end_prp = n2o_prp_end * self.head_number_end / 1000 * 44 / 28 * self.nitrous_constant * self.leaching_multiplier

                nmm_indirect_leaching_emissions_yearly_prp = compute_yearly_or_half_year_cumulative(
                    annual_start_prp, annual_end_prp, self.implementation_time, self.capitalization_time, self.rate_type
                )

                nmm_indirect_leaching_emission_set_prp = YearlyGasActivityEmissionSet(
                    0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in nmm_indirect_leaching_emissions_yearly_prp], ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_PRP, delay=self.delay
                )

                self.result.yearly_emissions_by_sector_by_gas.append(nmm_indirect_leaching_emission_set_prp)
                self.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.N2O, 0, ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_PRP))

            except Exception as e:
                traceback.print_exc()
                raise e

        cdg_start, self.managed_manure_n_available_start = self._manure_n_period(
            self.manure_system_names_start,
            self.percentage_system_default_start,
            self.percentage_prp_default_start,
            self.percentage_prp_tier_2_start,
            self.ef_system_nitrous_direct_start,
            self.ef_system_nitrous_indirect_volatization_start,
            self.ef_system_nitrous_indirect_leaching_start,
            self.codigestate_n_start,
            self.bedding_n_start,
            self.head_number_start,
            self.tam_start,
            self.ner_start,
        )
        cdg_end, self.managed_manure_n_available_end = self._manure_n_period(
            self.manure_system_names_end,
            self.percentage_system_default_end,
            self.percentage_prp_default_end,
            self.percentage_prp_tier_2_end,
            self.ef_system_nitrous_direct_end,
            self.ef_system_nitrous_indirect_volatization_end,
            self.ef_system_nitrous_indirect_leaching_end,
            self.codigestate_n_end,
            self.bedding_n_end,
            self.head_number_end,
            self.tam_end,
            self.ner_end,
        )

        calculate_methane_enteric_fermentation_emissions()
        calculate_methane_manure_management_emissions()
        calculate_nitrous_manure_management_direct()
        calculate_nitrous_manure_management_indirect_volatization()
        calculate_nitrous_manure_management_indirect_leaching()
