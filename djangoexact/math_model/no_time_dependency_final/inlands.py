import math
import traceback

from .general_functions import (
    BaseModule,
    breakdown_according_to_values,
    soil_emissions,
    yearly_constant_emissions_breakdown,
    yearly_time_dependent_20_year_breakdown,
    yearly_time_dependent_parameter_breakdown,
)
from .ghg_emissions_classes import (
    ActivityTypes,
    Emission,
    GasTypes,
    Result,
    YearlyGasActivityEmissionSet,
)


class AnnexedModule(BaseModule):
    def __init__(
        self,
        fire_boolean_end,
        fire_periodicity_end,
        area_affected_by_action_end,
        dry_matter_ref_fire,
        dry_matter_tier_2_fire,
        percentage_area_burned_end,
        ef_co2_ref_fire,
        ef_co2_tier_2_fire,
        ef_co_ref_fire,
        ef_co_tier_2_fire,
        ef_ch4_ref_fire,
        ef_ch4_tier_2_fire,
        methane_constant,
        rate,  # FIRE EMISSIONS
        time_impl,
        time_cap,
        nitrous_constant,  # GENERAL INFO
        ef_doc_ref_drainage_initial,
        ef_doc_tier_2_drainage_initial,
        area_drained_start,
        area_drained_end,
        ef_co2_ref_drainage_initial,
        ef_co2_tier_2_drainage_initial,
        percentage_ditches_start,
        percentage_ditches_end,
        ef_ch4_onsite_ref_drainage_initial,
        ef_ch4_onsite_tier_2_drainage_initial,
        ef_ch4_offsite_ref_drainage_initial,
        ef_ch4_offsite_tier_2_drainage_initial,
        ef_n2o_ref_drainage_initial,
        ef_n2o_tier_2_drainage_initial,  # DRAINAGE EMISSIONS INITIAL
        ef_doc_ref_drainage_final,
        ef_doc_tier_2_drainage_final,
        ef_co2_ref_drainage_final,
        ef_co2_tier_2_drainage_final,
        ef_ch4_onsite_ref_drainage_final,
        ef_ch4_onsite_tier_2_drainage_final,
        ef_ch4_offsite_ref_drainage_final,
        ef_ch4_offsite_tier_2_drainage_final,
        ef_n2o_ref_drainage_final,
        ef_n2o_tier_2_drainage_final,  # DRAINAGE EMISSIONS FINAL
        ef_doc_rewetting_initial,
        ef_doc_rewetting_initial_tier_2,
        ef_co2_rewetting_initial,
        ef_co2_rewetting_initial_tier_2,
        ef_ch4_rewetting_initial,
        ef_ch4_rewetting_initial_tier_2,
        ef_n2o_rewetting_initial,
        ef_n2o_rewetting_initial_tier_2,  # REWETTING EMISSIONS INITIAL
        ef_doc_rewetting_final,
        ef_doc_rewetting_final_tier_2,
        ef_co2_rewetting_final,
        ef_co2_rewetting_final_tier_2,
        ef_ch4_rewetting_final,
        ef_ch4_rewetting_final_tier_2,
        ef_n2o_rewetting_final,
        ef_n2o_rewetting_final_tier_2,  # REWETTING EMISSIONS FINAL
        maximum_area_for_water_management,
    ):  # GENERAL INFO
        self.fire_boolean_end = fire_boolean_end
        self.fire_periodicity_end = fire_periodicity_end
        self.area_affected_by_action_end = area_affected_by_action_end
        self.dry_matter_ref_fire = dry_matter_ref_fire
        self.dry_matter_tier_2_fire = dry_matter_tier_2_fire
        self.percentage_area_burned_end = percentage_area_burned_end
        self.ef_co2_ref_fire = ef_co2_ref_fire
        self.ef_co2_tier_2_fire = ef_co2_tier_2_fire
        self.ef_co_ref_fire = ef_co_ref_fire
        self.ef_co_tier_2_fire = ef_co_tier_2_fire
        self.ef_ch4_ref_fire = ef_ch4_ref_fire
        self.ef_ch4_tier_2_fire = ef_ch4_tier_2_fire
        self.methane_constant = methane_constant
        self.rate = rate
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.nitrous_constant = nitrous_constant
        self.ef_doc_ref_drainage_initial = ef_doc_ref_drainage_initial
        self.ef_doc_tier_2_drainage_initial = ef_doc_tier_2_drainage_initial
        self.area_drained_start = area_drained_start
        self.area_drained_end = area_drained_end
        self.ef_co2_ref_drainage_initial = ef_co2_ref_drainage_initial
        self.ef_co2_tier_2_drainage_initial = ef_co2_tier_2_drainage_initial
        self.percentage_ditches_start = percentage_ditches_start
        self.percentage_ditches_end = percentage_ditches_end
        self.ef_ch4_onsite_ref_drainage_initial = ef_ch4_onsite_ref_drainage_initial
        self.ef_ch4_onsite_tier_2_drainage_initial = ef_ch4_onsite_tier_2_drainage_initial
        self.ef_ch4_offsite_ref_drainage_initial = ef_ch4_offsite_ref_drainage_initial
        self.ef_ch4_offsite_tier_2_drainage_initial = ef_ch4_offsite_tier_2_drainage_initial
        self.ef_n2o_ref_drainage_initial = ef_n2o_ref_drainage_initial
        self.ef_n2o_tier_2_drainage_initial = ef_n2o_tier_2_drainage_initial
        self.ef_doc_ref_drainage_final = ef_doc_ref_drainage_final
        self.ef_doc_tier_2_drainage_final = ef_doc_tier_2_drainage_final
        self.ef_co2_ref_drainage_final = ef_co2_ref_drainage_final
        self.ef_co2_tier_2_drainage_final = ef_co2_tier_2_drainage_final
        self.ef_ch4_onsite_ref_drainage_final = ef_ch4_onsite_ref_drainage_final
        self.ef_ch4_onsite_tier_2_drainage_final = ef_ch4_onsite_tier_2_drainage_final
        self.ef_ch4_offsite_ref_drainage_final = ef_ch4_offsite_ref_drainage_final
        self.ef_ch4_offsite_tier_2_drainage_final = ef_ch4_offsite_tier_2_drainage_final
        self.ef_n2o_ref_drainage_final = ef_n2o_ref_drainage_final
        self.ef_n2o_tier_2_drainage_final = ef_n2o_tier_2_drainage_final
        self.ef_doc_rewetting_initial = ef_doc_rewetting_initial
        self.ef_doc_rewetting_initial_tier_2 = ef_doc_rewetting_initial_tier_2
        self.ef_co2_rewetting_initial = ef_co2_rewetting_initial
        self.ef_co2_rewetting_initial_tier_2 = ef_co2_rewetting_initial_tier_2
        self.ef_ch4_rewetting_initial = ef_ch4_rewetting_initial
        self.ef_ch4_rewetting_initial_tier_2 = ef_ch4_rewetting_initial_tier_2
        self.ef_n2o_rewetting_initial = ef_n2o_rewetting_initial
        self.ef_n2o_rewetting_initial_tier_2 = ef_n2o_rewetting_initial_tier_2
        self.ef_doc_rewetting_final = ef_doc_rewetting_final
        self.ef_doc_rewetting_final_tier_2 = ef_doc_rewetting_final_tier_2
        self.ef_co2_rewetting_final = ef_co2_rewetting_final
        self.ef_co2_rewetting_final_tier_2 = ef_co2_rewetting_final_tier_2
        self.ef_ch4_rewetting_final = ef_ch4_rewetting_final
        self.ef_ch4_rewetting_final_tier_2 = ef_ch4_rewetting_final_tier_2
        self.ef_n2o_rewetting_final = ef_n2o_rewetting_final
        self.ef_n2o_rewetting_final_tier_2 = ef_n2o_rewetting_final_tier_2

        self.maximum_area_for_water_management = maximum_area_for_water_management

        # TIER 2 DEFAULTS
        self.dry_matter_fire_tier_2_default = self.dry_matter_ref_fire

        """
        ef_doc_rewetting_initial = self.ef_doc_rewetting_initial if not self.ef_doc_rewetting_initial_tier_2 else self.ef_doc_rewetting_initial_tier_2
        ef_co2_rewetting_initial = self.ef_co2_rewetting_initial if not self.ef_co2_rewetting_initial_tier_2 else self.ef_co2_rewetting_initial_tier_2
        ef_ch4_rewetting_initial = self.ef_ch4_rewetting_initial if not self.ef_ch4_rewetting_initial_tier_2 else self.ef_ch4_rewetting_initial_tier_2
        ef_n2o_rewetting_initial = self.ef_n2o_rewetting_initial if not self.ef_n2o_rewetting_initial_tier_2 else self.ef_n2o_rewetting_initial_tier_2

        ef_doc_rewetting_final = self.ef_doc_rewetting_final if not self.ef_doc_rewetting_final_tier_2 else self.ef_doc_rewetting_final_tier_2
        ef_co2_rewetting_final = self.ef_co2_rewetting_final if not self.ef_co2_rewetting_final_tier_2 else self.ef_co2_rewetting_final_tier_2
        ef_ch4_rewetting_final = self.ef_ch4_rewetting_final if not self.ef_ch4_rewetting_final_tier_2 else self.ef_ch4_rewetting_final_tier_2
        ef_n2o_rewetting_final = self.ef_n2o_rewetting_final if not self.ef_n2o_rewetting_final_tier_2 else self.ef_n2o_rewetting_final_tier_2
        """
        self.ef_n2o_start_tier_2_default = self.ef_n2o_ref_drainage_initial
        self.ef_ch4_onsite_start_tier_2_default = self.ef_ch4_onsite_ref_drainage_initial
        self.ef_ch4_offsite_start_tier_2_default = self.ef_ch4_offsite_ref_drainage_initial
        self.ef_co2_start_tier_2_default = self.ef_co2_ref_drainage_initial
        self.ef_doc_start_tier_2_default = self.ef_doc_ref_drainage_initial
        self.ed_n2o_end_tier_2_default = self.ef_n2o_ref_drainage_final
        self.ef_ch4_onsite_end_tier_2_default = self.ef_ch4_onsite_ref_drainage_final
        self.ef_ch4_offsite_end_tier_2_default = self.ef_ch4_offsite_ref_drainage_final
        self.ef_co2_end_tier_2_default = self.ef_co2_ref_drainage_final
        self.ef_doc_end_tier_2_default = self.ef_doc_ref_drainage_final

        self.ef_doc_rewetting_start_tier_2_default = self.ef_doc_rewetting_initial
        self.ef_co2_rewetting_start_tier_2_default = self.ef_co2_rewetting_initial
        self.ef_ch4_rewetting_start_tier_2_default = self.ef_ch4_rewetting_initial
        self.ef_n2o_rewetting_start_tier_2_default = self.ef_n2o_rewetting_initial
        self.ef_doc_rewetting_end_tier_2_default = self.ef_doc_rewetting_final
        self.ef_co2_rewetting_end_tier_2_default = self.ef_co2_rewetting_final
        self.ef_ch4_rewetting_end_tier_2_default = self.ef_ch4_rewetting_final
        self.ef_n2o_rewetting_end_tier_2_default = self.ef_n2o_rewetting_final

        # RESULTS

        # TODO: ADD ALL RESULTS BREAKDOWNS

        self.emissions_rewetting_yearly = []
        self.emissions_rewetting_total = 0

        self.emissions_drainage_yearly = []
        self.emissions_drainage_total = 0

        self.emissions_fire_yearly = []
        self.emissions_fire_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)
        pass

    def calculate_emissions(
        self,
    ):
        def calculate_fire_emissions():
            # TODO: check if all tier2 values should be assigned in the constructor
            def fire_co2_co_ch4(fire_periodicity, dry_matter, area, rate_coefficient, time_impl, time_cap, percentage_area_burned, ef_co2, ef_co, ef_ch4, methane_constant):
                biomass_start = 0
                biomass_end = area * dry_matter

                biomass_yearly = yearly_time_dependent_parameter_breakdown(biomass_start, biomass_end, time_impl, time_cap, rate_coefficient, interim_values=True)
                total_biomass = sum(biomass_yearly)

                multiplication_parameter_co2_co = (1 / fire_periodicity * percentage_area_burned * ef_co2 * 44 / 12 / 1000) + (1 / fire_periodicity * percentage_area_burned * ef_co * 2 / 1000)

                multiplication_parameter_co2 = 1 / fire_periodicity * percentage_area_burned * ef_co2 * 44 / 12 / 1000
                multiplication_parameter_co = 1 / fire_periodicity * percentage_area_burned * ef_co * 2 / 1000
                multiplication_parameter_ch4 = 1 / fire_periodicity * percentage_area_burned * ef_ch4 * methane_constant / 1000

                return total_biomass * multiplication_parameter_co2, total_biomass * multiplication_parameter_co, total_biomass * multiplication_parameter_ch4

            try:
                dry_matter_ref_fire = self.dry_matter_ref_fire if not self.dry_matter_tier_2_fire else self.dry_matter_tier_2_fire

                if self.fire_boolean_end and self.fire_periodicity_end < self.time_impl + self.time_cap and self.area_affected_by_action_end != 0 and dry_matter_ref_fire != 0:
                    co2, co, ch4 = fire_co2_co_ch4(self.fire_periodicity_end, dry_matter_ref_fire, self.area_affected_by_action_end, self.rate, self.time_impl, self.time_cap, self.percentage_area_burned_end, self.ef_co2_ref_fire if not self.ef_co2_tier_2_fire else self.ef_co2_tier_2_fire, self.ef_co_ref_fire if not self.ef_co_tier_2_fire else self.ef_co_tier_2_fire, self.ef_ch4_ref_fire if not self.ef_ch4_tier_2_fire else self.ef_ch4_tier_2_fire, self.methane_constant)
                    # TODO: ask how they should be broken down
                    self.emissions_fire_total = co2 + co + ch4
                    self.emissions_fire_yearly = breakdown_according_to_values(self.emissions_fire_total, yearly_time_dependent_parameter_breakdown(0, self.area_affected_by_action_end * dry_matter_ref_fire, self.time_impl, self.time_cap, self.rate, interim_values=True))

                    emissions_co2_yearly = breakdown_according_to_values(co2, yearly_time_dependent_parameter_breakdown(0, self.area_affected_by_action_end * dry_matter_ref_fire, self.time_impl, self.time_cap, self.rate, interim_values=True))
                    emissions_co_yearly = breakdown_according_to_values(co, yearly_time_dependent_parameter_breakdown(0, self.area_affected_by_action_end * dry_matter_ref_fire, self.time_impl, self.time_cap, self.rate, interim_values=True))
                    emissions_ch4_yearly = breakdown_according_to_values(ch4, yearly_time_dependent_parameter_breakdown(0, self.area_affected_by_action_end * dry_matter_ref_fire, self.time_impl, self.time_cap, self.rate, interim_values=True))

                    # residue_burning_nitrous_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in breakdown_according_to_values(total_nitrous, self.total_hectars)], ActivityTypes.RESIDUE_BURNING, delay=self.delay)
                    # residue_burning_methane_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in breakdown_according_to_values(total_methane, self.total_hectars)], ActivityTypes.RESIDUE_BURNING, delay=self.delay)

                    # self.result.yearly_emissions_by_sector_by_gas.append(residue_burning_nitrous_emission_set)
                    # self.result.yearly_emissions_by_sector_by_gas.append(residue_burning_methane_emission_set)

                    co2_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_co2_yearly], ActivityTypes.FIRE_ON_SOIL, delay=0)
                    co_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO, [Emission(e, GasTypes.CO) for e in emissions_co_yearly], ActivityTypes.FIRE_ON_SOIL, delay=0)
                    ch4_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in emissions_ch4_yearly], ActivityTypes.FIRE_ON_SOIL, delay=0)

                    self.result.yearly_emissions_by_sector_by_gas.append(co2_emission_set)
                    self.result.yearly_emissions_by_sector_by_gas.append(co_emission_set)
                    self.result.yearly_emissions_by_sector_by_gas.append(ch4_emission_set)

                else:
                    self.emissions_fire_yearly = [0 for i in range(self.time_impl + self.time_cap)]
                    self.emissions_fire_total = 0

            except:
                traceback.print_exc()
                return

        def calculate_drainage_emissions():
            def calculate_drainage_initial():
                def calculate_emissions_start_end(ef, area_affected_by_action_start, area_affected_by_action_end, percentage_area_multiplier_start, percentage_area_multiplier_end, area_affected_by_module, multiplying_constant):
                    try:
                        em_start = ef * area_affected_by_action_start * multiplying_constant * percentage_area_multiplier_start

                        if area_affected_by_module == 0:
                            em_end = ef * area_affected_by_action_end * percentage_area_multiplier_end * multiplying_constant
                        elif area_affected_by_action_end < area_affected_by_module:
                            em_end = 0
                        else:
                            em_end = ef * (area_affected_by_module - area_affected_by_action_end) * percentage_area_multiplier_end * multiplying_constant

                        return em_start, em_end
                    except:
                        traceback.print_exc()
                        return

                try:
                    ef_n2o = self.ef_n2o_ref_drainage_initial if not self.ef_n2o_tier_2_drainage_initial else self.ef_n2o_tier_2_drainage_initial
                    ef_ch4_on_site = self.ef_ch4_onsite_ref_drainage_initial if not self.ef_ch4_onsite_tier_2_drainage_initial else self.ef_ch4_onsite_tier_2_drainage_initial
                    ef_ch4_off_site = self.ef_ch4_offsite_ref_drainage_initial if not self.ef_ch4_offsite_tier_2_drainage_initial else self.ef_ch4_offsite_tier_2_drainage_initial
                    ef_co2 = self.ef_co2_ref_drainage_initial if not self.ef_co2_tier_2_drainage_initial else self.ef_co2_tier_2_drainage_initial
                    ef_doc = self.ef_doc_ref_drainage_initial if not self.ef_doc_tier_2_drainage_initial else self.ef_doc_tier_2_drainage_initial

                    n2ostart, n2oend = calculate_emissions_start_end(ef_n2o, self.area_drained_start, self.area_drained_end, 1, 1, self.area_affected_by_action_end, 44 / 28 * self.nitrous_constant / 1000)

                    ch4_start, ch4_end = calculate_emissions_start_end(ef_ch4_on_site, self.area_drained_start, self.area_drained_end, 1 - self.percentage_ditches_start, 1 - self.percentage_ditches_end, self.area_affected_by_action_end, self.methane_constant / 1000)
                    ch4_start_ditches, ch4_end_ditches = calculate_emissions_start_end(ef_ch4_off_site, self.area_drained_start, self.area_drained_end, self.percentage_ditches_start, self.percentage_ditches_end, self.area_affected_by_action_end, self.methane_constant / 1000)

                    co2_start, co2_end = calculate_emissions_start_end(ef_co2, self.area_drained_start, 1, 1, self.area_drained_end, self.area_affected_by_action_end, 44 / 12)
                    doc_start, doc_end = calculate_emissions_start_end(ef_doc, self.area_drained_start, 1, 1, self.area_drained_end, self.area_affected_by_action_end, 44 / 12)

                    total_n2o = yearly_time_dependent_parameter_breakdown(n2ostart, n2oend, self.time_impl, self.time_cap, self.rate, interim_values=True)

                    total_ch4_onsite = yearly_time_dependent_parameter_breakdown(ch4_start, ch4_end, self.time_impl, self.time_cap, self.rate, interim_values=True)
                    total_ch4_off_site = yearly_time_dependent_parameter_breakdown(ch4_start_ditches, ch4_end_ditches, self.time_impl, self.time_cap, self.rate, interim_values=True)

                    total_doc = yearly_time_dependent_parameter_breakdown(doc_start, doc_end, self.time_impl, self.time_cap, self.rate, interim_values=True)
                    total_co2 = yearly_time_dependent_parameter_breakdown(co2_start, co2_end, self.time_impl, self.time_cap, self.rate, interim_values=True)

                    return total_n2o, total_ch4_onsite, total_ch4_off_site, total_doc, total_co2, sum(total_n2o) + sum(total_ch4_onsite) + sum(total_ch4_off_site) + sum(total_doc) + sum(total_co2)

                except:
                    traceback.print_exc()
                    return

            def calculate_drainage_final():
                def calculate_emissions_start_end(ef, area_affected_by_action_start, area_affected_by_action_end, percentage_area_multiplier_start, percentage_area_multiplier_end, area_affected_by_module, multiplying_constant):
                    try:
                        em_start = 0

                        if area_affected_by_module == 0:
                            em_end = 0
                        elif area_affected_by_action_end < area_affected_by_module:
                            em_end = ef * area_affected_by_action_end * percentage_area_multiplier_end * multiplying_constant
                        else:
                            em_end = ef * (area_affected_by_action_start) * percentage_area_multiplier_end * multiplying_constant

                        return em_start, em_end
                    except:
                        traceback.print_exc()
                        return

                try:
                    # TODO: check why I need initial and final, only calculate_emissions_start_end is different???
                    # TODO: assign ef values in constructor
                    ef_n2o = self.ef_n2o_ref_drainage_final if not self.ef_n2o_tier_2_drainage_final else self.ef_n2o_tier_2_drainage_final
                    ef_ch4_on_site = self.ef_ch4_onsite_ref_drainage_final if not self.ef_ch4_onsite_tier_2_drainage_final else self.ef_ch4_onsite_tier_2_drainage_final
                    ef_ch4_off_site = self.ef_ch4_offsite_ref_drainage_final if not self.ef_ch4_offsite_tier_2_drainage_final else self.ef_ch4_offsite_tier_2_drainage_final
                    ef_co2 = self.ef_co2_ref_drainage_final if not self.ef_co2_tier_2_drainage_final else self.ef_co2_tier_2_drainage_final
                    ef_doc = self.ef_doc_ref_drainage_final if not self.ef_doc_tier_2_drainage_final else self.ef_doc_tier_2_drainage_final

                    n2ostart, n2oend = calculate_emissions_start_end(ef_n2o, self.area_drained_start, self.area_drained_end, 1, 1, self.area_affected_by_action_end, 44 / 28 * self.nitrous_constant / 1000)

                    ch4_start, ch4_end = calculate_emissions_start_end(ef_ch4_on_site, self.area_drained_start, self.area_drained_end, 1 - self.percentage_ditches_start, 1 - self.percentage_ditches_end, self.area_affected_by_action_end, self.methane_constant / 1000)
                    ch4_start_ditches, ch4_end_ditches = calculate_emissions_start_end(ef_ch4_off_site, self.area_drained_start, self.area_drained_end, self.percentage_ditches_start, self.percentage_ditches_end, self.area_affected_by_action_end, self.methane_constant / 1000)

                    co2_start, co2_end = calculate_emissions_start_end(ef_co2, self.area_drained_start, 1, 1, self.area_drained_end, self.area_affected_by_action_end, 44 / 12)
                    doc_start, doc_end = calculate_emissions_start_end(ef_doc, self.area_drained_start, 1, 1, self.area_drained_end, self.area_affected_by_action_end, 44 / 12)

                    total_n2o = yearly_time_dependent_parameter_breakdown(n2ostart, n2oend, self.time_impl, self.time_cap, self.rate, interim_values=True)

                    total_ch4_onsite = yearly_time_dependent_parameter_breakdown(ch4_start, ch4_end, self.time_impl, self.time_cap, self.rate, interim_values=True)
                    total_ch4_off_site = yearly_time_dependent_parameter_breakdown(ch4_start_ditches, ch4_end_ditches, self.time_impl, self.time_cap, self.rate, interim_values=True)

                    total_doc = yearly_time_dependent_parameter_breakdown(doc_start, doc_end, self.time_impl, self.time_cap, self.rate, interim_values=True)
                    total_co2 = yearly_time_dependent_parameter_breakdown(co2_start, co2_end, self.time_impl, self.time_cap, self.rate, interim_values=True)

                    return total_n2o, total_ch4_onsite, total_ch4_off_site, total_doc, total_co2, sum(total_n2o) + sum(total_ch4_onsite) + sum(total_ch4_off_site) + sum(total_doc) + sum(total_co2)

                except:
                    traceback.print_exc()
                    return

            try:
                n2o_initial, ch4_onsite_initial, ch4_offsite_initial, doc_initial, co2_initial, total_initial = calculate_drainage_initial()
                n2o_final, ch4_onsite_final, ch4_offsite_final, doc_final, co2_final, total_final = calculate_drainage_final()

                n2o_total = [i + j for i, j in zip(n2o_initial, n2o_final)]
                ch4_onsite_total = [i + j for i, j in zip(ch4_onsite_initial, ch4_onsite_final)]
                ch4_offsite_total = [i + j for i, j in zip(ch4_offsite_initial, ch4_offsite_final)]
                doc_total = [i + j for i, j in zip(doc_initial, doc_final)]
                co2_total = [i + j for i, j in zip(co2_initial, co2_final)]

                co2_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in co2_total], ActivityTypes.DRAINAGE, delay=0)
                doc_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.DOC, [Emission(e, GasTypes.DOC) for e in doc_total], ActivityTypes.DRAINAGE, delay=0)
                ch4_onsite_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in ch4_onsite_total], ActivityTypes.DRAINAGE, delay=0)
                ch4_offsite_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in ch4_offsite_total], ActivityTypes.DRAINAGE, delay=0)
                n2o_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in n2o_total], ActivityTypes.DRAINAGE, delay=0)

                self.result.yearly_emissions_by_sector_by_gas.append(co2_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(doc_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(ch4_onsite_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(ch4_offsite_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(n2o_emission_set)

                self.emissions_drainage_yearly = [i + j + k + l + m for i, j, k, l, m in zip(n2o_total, ch4_onsite_total, ch4_offsite_total, doc_total, co2_total)]
                self.emissions_drainage_total = total_initial + total_final

            except:
                traceback.print_exc()
                return

        def calculate_rewetting_emissions():
            def rewetting_emissions(area_rewetted, ef_doc, ef_co2, ef_ch4, ef_n2o, methane_constant, nitrous_constant, rate_coefficient, time_impl, time_cap):
                def yearly_emissions_calculation(multiplication_parameter, area_affected_action, ef):
                    return 0, multiplication_parameter * area_affected_action * ef

                try:
                    co2_doc_y_start, co2_doc_y_end = yearly_emissions_calculation(ef_doc + ef_co2, area_rewetted, 44 / 12)
                    ch4_y_start, ch4_y_end = yearly_emissions_calculation(ef_ch4, area_rewetted, methane_constant / 1000 * 16 / 12)
                    n2o_n_y_start, n2o_n_y_end = yearly_emissions_calculation(ef_n2o, area_rewetted, nitrous_constant / 1000 * 44 / 28)

                    total_co2_doc = yearly_time_dependent_parameter_breakdown(co2_doc_y_start, co2_doc_y_end, time_impl, time_cap, rate_coefficient, interim_values=True)
                    total_ch4 = yearly_time_dependent_parameter_breakdown(ch4_y_start, ch4_y_end, time_impl, time_cap, rate_coefficient, interim_values=True)
                    total_n2o = yearly_time_dependent_parameter_breakdown(n2o_n_y_start, n2o_n_y_end, time_impl, time_cap, rate_coefficient, interim_values=True)

                    return total_co2_doc, total_ch4, total_n2o, sum(total_co2_doc) + sum(total_ch4) + sum(total_n2o)
                except:
                    traceback.print_exc()
                    return

            # TODO: check with Lorenzo why initial and final
            try:
                area_not_drained_start = self.maximum_area_for_water_management - self.area_drained_start
                area_not_drained_end = self.maximum_area_for_water_management - self.area_drained_end

                if area_not_drained_start == self.maximum_area_for_water_management:
                    area_rewet_final = 0
                    area_rewet_initial = 0
                else:
                    area_rewet_initial = max(0, area_not_drained_end - area_not_drained_start - self.area_affected_by_action_end)
                    area_rewet_final = max(0, area_not_drained_end - area_not_drained_start)

                ef_doc_rewetting_initial = self.ef_doc_rewetting_initial if not self.ef_doc_rewetting_initial_tier_2 else self.ef_doc_rewetting_initial_tier_2
                ef_co2_rewetting_initial = self.ef_co2_rewetting_initial if not self.ef_co2_rewetting_initial_tier_2 else self.ef_co2_rewetting_initial_tier_2
                ef_ch4_rewetting_initial = self.ef_ch4_rewetting_initial if not self.ef_ch4_rewetting_initial_tier_2 else self.ef_ch4_rewetting_initial_tier_2
                ef_n2o_rewetting_initial = self.ef_n2o_rewetting_initial if not self.ef_n2o_rewetting_initial_tier_2 else self.ef_n2o_rewetting_initial_tier_2

                ef_doc_rewetting_final = self.ef_doc_rewetting_final if not self.ef_doc_rewetting_final_tier_2 else self.ef_doc_rewetting_final_tier_2
                ef_co2_rewetting_final = self.ef_co2_rewetting_final if not self.ef_co2_rewetting_final_tier_2 else self.ef_co2_rewetting_final_tier_2
                ef_ch4_rewetting_final = self.ef_ch4_rewetting_final if not self.ef_ch4_rewetting_final_tier_2 else self.ef_ch4_rewetting_final_tier_2
                ef_n2o_rewetting_final = self.ef_n2o_rewetting_final if not self.ef_n2o_rewetting_final_tier_2 else self.ef_n2o_rewetting_final_tier_2

                total_co2_doc_initial, total_ch4_initial, total_n2o_initital, total_rewetting_initial = rewetting_emissions(area_rewet_initial, ef_doc_rewetting_initial, ef_co2_rewetting_initial, ef_ch4_rewetting_initial, ef_n2o_rewetting_initial, self.methane_constant, self.nitrous_constant, self.rate, self.time_impl, self.time_cap)
                total_co2_doc_final, total_ch4_final, total_n2o_final, total_rewetting_final = rewetting_emissions(area_rewet_final, ef_doc_rewetting_final, ef_co2_rewetting_final, ef_ch4_rewetting_final, ef_n2o_rewetting_final, self.methane_constant, self.nitrous_constant, self.rate, self.time_impl, self.time_cap)

                total_rewetting = total_rewetting_final + total_rewetting_initial
                self.emissions_rewetting_yearly = [i + j + k + l + m + n for i, j, k, l, m, n in zip(total_co2_doc_initial, total_ch4_initial, total_n2o_initital, total_co2_doc_final, total_ch4_final, total_n2o_final)]
                self.emissions_rewetting_total = total_rewetting

                co2_doc_emission_set_initial = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in total_co2_doc_initial], ActivityTypes.REWETTING, delay=0)
                ch4_emission_set_initial = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in total_ch4_initial], ActivityTypes.REWETTING, delay=0)
                n2o_emission_set_initial = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in total_n2o_initital], ActivityTypes.REWETTING, delay=0)

                co2_doc_emission_set_final = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in total_co2_doc_final], ActivityTypes.REWETTING, delay=0)
                ch4_emission_set_final = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in total_ch4_final], ActivityTypes.REWETTING, delay=0)
                n2o_emission_set_final = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in total_n2o_final], ActivityTypes.REWETTING, delay=0)

                self.result.yearly_emissions_by_sector_by_gas.append(co2_doc_emission_set_initial)
                self.result.yearly_emissions_by_sector_by_gas.append(ch4_emission_set_initial)
                self.result.yearly_emissions_by_sector_by_gas.append(n2o_emission_set_initial)

                self.result.yearly_emissions_by_sector_by_gas.append(co2_doc_emission_set_final)
                self.result.yearly_emissions_by_sector_by_gas.append(ch4_emission_set_final)
                self.result.yearly_emissions_by_sector_by_gas.append(n2o_emission_set_final)

            except:
                traceback.print_exc()
                return

        try:
            calculate_fire_emissions()
            calculate_drainage_emissions()
            calculate_rewetting_emissions()
            self.emissions_total_yearly = [i + j + k for i, j, k in zip(self.emissions_fire_yearly, self.emissions_drainage_yearly, self.emissions_rewetting_yearly)]
            self.total_emissions = self.emissions_fire_total + self.emissions_drainage_total + self.emissions_rewetting_total
        except:
            traceback.print_exc()
            return


class PeatExtraction(BaseModule):
    def __init__(self, hectares_start, hectares_end, percentage_ditches_start, percentage_ditches_end, rate_coefficient_end, ef_co2_onsite_ref, ef_co2_onsite_tier_2, ef_ch4_onsite_ref, ef_ch4_onsite_tier_2, ef_n2o_onsite_ref, ef_n2o_onsite_tier_2, ef_doc_offsite_ref, ef_doc_offsite_tier_2, ef_ch4_offsite_ref, ef_ch4_offsite_tier_2, methane_constant, nitrous_constant, time_impl, time_cap, weight_peat, mass_tonnes_tier_2, conversion_factor_volume, c_fraction_ref, extraction_height_start, extraction_height_end):
        self.hectares_start = hectares_start
        self.hectares_end = hectares_end
        self.percentage_ditches_start = percentage_ditches_start
        self.percentage_ditches_end = percentage_ditches_end
        self.rate_coefficient_end = rate_coefficient_end
        self.ef_co2_onsite_ref = ef_co2_onsite_ref
        self.ef_co2_onsite_tier_2 = ef_co2_onsite_tier_2
        self.ef_ch4_onsite_ref = ef_ch4_onsite_ref
        self.ef_ch4_onsite_tier_2 = ef_ch4_onsite_tier_2
        self.ef_n2o_onsite_ref = ef_n2o_onsite_ref
        self.ef_n2o_onsite_tier_2 = ef_n2o_onsite_tier_2
        self.ef_doc_offsite_ref = ef_doc_offsite_ref
        self.ef_doc_offsite_tier_2 = ef_doc_offsite_tier_2
        self.ef_ch4_offsite_ref = ef_ch4_offsite_ref
        self.ef_ch4_offsite_tier_2 = ef_ch4_offsite_tier_2
        self.methane_constant = methane_constant
        self.nitrous_constant = nitrous_constant
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.weight_peat = weight_peat
        self.mass_tonnes_tier_2 = mass_tonnes_tier_2
        self.conversion_factor_volume = conversion_factor_volume
        self.c_fraction_ref = c_fraction_ref
        self.extraction_height_start = extraction_height_start
        self.extraction_height_end = extraction_height_end

        # RESULTS
        self.drainage_co2_doc_yearly = []
        self.drainage_co2_doc_total = 0

        self.drainage_ch4_yearly = []
        self.drainage_ch4_total = 0

        self.drainage_n2o_yearly = []
        self.drainage_n2o_total = 0

        self.drainage_total_yearly = []
        self.drainage_total = 0

        self.offsite_emissions_yearly = []
        self.offsite_emissions_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)

    def calculate_emissions(self):
        def drainage_emissions():
            def yearly_emissions_calculation(ef_multiplication_parameter, hectars_start, hectars_end, ef, multiplier_start=1, multiplier_end=1):
                return hectars_start * ef * ef_multiplication_parameter * multiplier_start, hectars_end * ef * ef_multiplication_parameter * multiplier_end

            try:
                ef_co2_onsite = self.ef_co2_onsite_ref if not self.ef_co2_onsite_tier_2 else self.ef_co2_onsite_tier_2
                ef_ch4_onsite = self.ef_ch4_onsite_ref if not self.ef_ch4_onsite_tier_2 else self.ef_ch4_onsite_tier_2
                ef_n2o_onsite = self.ef_n2o_onsite_ref if not self.ef_n2o_onsite_tier_2 else self.ef_n2o_onsite_tier_2
                ef_doc_offsite = self.ef_doc_offsite_ref if not self.ef_doc_offsite_tier_2 else self.ef_doc_offsite_tier_2
                ef_ch4_offsite = self.ef_ch4_offsite_ref if not self.ef_ch4_offsite_tier_2 else self.ef_ch4_offsite_tier_2

                co2_onsite_emissions_start, co2_onsite_emissions_end = yearly_emissions_calculation(44 / 12, self.hectares_start, self.hectares_end, ef_co2_onsite)
                ch4_onsite_emissions_start, ch4_onsite_emissions_end = yearly_emissions_calculation(self.methane_constant / 1000, self.hectares_start, self.hectares_end, ef_ch4_onsite, 1 - self.percentage_ditches_start, 1 - self.percentage_ditches_end)
                n2o_onsite_emissions_start, n2o_onsite_emissions_end = yearly_emissions_calculation(self.nitrous_constant / 1000 * 44 / 28, self.hectares_start, self.hectares_end, ef_n2o_onsite)
                doc_offsite_emissions_start, doc_offsite_emissions_end = yearly_emissions_calculation(44 / 12, self.hectares_start, self.hectares_end, ef_doc_offsite)
                ch4_offsite_emissions_start, ch4_offsite_emissions_end = yearly_emissions_calculation(self.methane_constant / 1000, self.hectares_start, self.hectares_end, ef_ch4_offsite, self.percentage_ditches_start, self.percentage_ditches_end)

                self.drainage_co2_doc_yearly = yearly_time_dependent_parameter_breakdown(co2_onsite_emissions_start + doc_offsite_emissions_start, co2_onsite_emissions_end + doc_offsite_emissions_end, self.time_impl, self.time_cap, self.rate_coefficient_end, interim_values=True)
                self.drainage_ch4_yearly = yearly_time_dependent_parameter_breakdown(ch4_onsite_emissions_start + ch4_offsite_emissions_start, ch4_onsite_emissions_end + ch4_offsite_emissions_end, self.time_impl, self.time_cap, self.rate_coefficient_end, interim_values=True)
                self.drainage_n2o_yearly = yearly_time_dependent_parameter_breakdown(n2o_onsite_emissions_start, n2o_onsite_emissions_end, self.time_impl, self.time_cap, self.rate_coefficient_end, interim_values=True)

                self.drainage_co2_doc_total = sum(self.drainage_co2_doc_yearly)
                self.drainage_ch4_total = sum(self.drainage_ch4_yearly)
                self.drainage_n2o_total = sum(self.drainage_n2o_yearly)

                self.drainage_total_yearly = [i + j + k for i, j, k in zip(self.drainage_co2_doc_yearly, self.drainage_ch4_yearly, self.drainage_n2o_yearly)]
                self.drainage_total = self.drainage_co2_doc_total + self.drainage_ch4_total + self.drainage_n2o_total

                drainage_peat_co2_doc_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.drainage_co2_doc_yearly], ActivityTypes.DRAINAGE_PEAT, delay=0)
                drainage_peat_ch4_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in self.drainage_ch4_yearly], ActivityTypes.DRAINAGE_PEAT, delay=0)
                drainage_peat_n2o_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in self.drainage_n2o_yearly], ActivityTypes.DRAINAGE_PEAT, delay=0)

            except:
                traceback.print_exc()
                return

        def off_site_emissions():
            def yearly_emissions_calculation(mass_tonnes, hectares_start, hectares_end, height_of_extraction_start, height_of_extraction_end):
                return mass_tonnes * hectares_start * height_of_extraction_start * 100, mass_tonnes * hectares_end * height_of_extraction_end * 100

            try:
                mass_tonnes = self.weight_peat * self.conversion_factor_volume / self.c_fraction_ref if not self.mass_tonnes_tier_2 else self.mass_tonnes_tier_2
                air_dry_weight_start, air_dry_weight_end = yearly_emissions_calculation(mass_tonnes, self.hectares_start, self.hectares_end, self.extraction_height_start, self.extraction_height_end)

                em_start = air_dry_weight_start * self.c_fraction_ref * 44 / 12
                em_end = air_dry_weight_end * self.c_fraction_ref * 44 / 12

                self.offsite_emissions_yearly = yearly_time_dependent_parameter_breakdown(em_start, em_end, self.time_impl, self.time_cap, self.rate_coefficient_end, interim_values=True)
                self.offsite_emissions_total = sum(self.offsite_emissions_yearly)

                offsite_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.offsite_emissions_yearly], ActivityTypes.OFFSITE_PEAT, delay=0)
                self.result.yearly_emissions_by_sector_by_gas.append(offsite_emission_set)

            except:
                traceback.print_exc()
                return

        drainage_emissions()
        off_site_emissions()

        try:
            self.emissions_total_yearly = [i + j for i, j in zip(self.drainage_total_yearly, self.offsite_emissions_yearly)]
            self.total_emissions = self.drainage_total + self.offsite_emissions_total
        except:
            traceback.print_exc()
            return
