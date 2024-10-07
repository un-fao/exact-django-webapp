import math
import traceback

from .general_functions import (
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

from dataclasses import dataclass, field
from typing import Optional
from .generalized_modules import BaseModule

@dataclass
class AnnexedModule(BaseModule):

    fire_boolean_end: float
    fire_periodicity_end: float
    area_affected_by_action_end: float
    dry_matter_ref_fire: float
    dry_matter_tier_2_fire: Optional[float]
    percentage_area_burned_end: float
    ef_co2_ref_fire: float
    ef_co2_tier_2_fire: Optional[float]
    ef_co_ref_fire: float
    ef_co_tier_2_fire: Optional[float]
    ef_ch4_ref_fire: float
    ef_ch4_tier_2_fire: Optional[float]
    methane_constant: float
    nitrous_constant: float  # GENERAL INFO
    ef_doc_ref_drainage_initial: float
    ef_doc_tier_2_drainage_initial: Optional[float]
    area_drained_start: float
    area_drained_end: float
    ef_co2_ref_drainage_initial: float
    ef_co2_tier_2_drainage_initial: Optional[float]
    percentage_ditches_start: float
    percentage_ditches_end: float
    ef_ch4_onsite_ref_drainage_initial: float
    ef_ch4_onsite_tier_2_drainage_initial: Optional[float]
    ef_ch4_offsite_ref_drainage_initial: float
    ef_ch4_offsite_tier_2_drainage_initial: Optional[float]
    ef_n2o_ref_drainage_initial: float
    ef_n2o_tier_2_drainage_initial: Optional[float]  # DRAINAGE EMISSIONS INITIAL
    ef_doc_ref_drainage_final: float
    ef_doc_tier_2_drainage_final: Optional[float]
    ef_co2_ref_drainage_final: float
    ef_co2_tier_2_drainage_final: Optional[float]
    ef_ch4_onsite_ref_drainage_final: float
    ef_ch4_onsite_tier_2_drainage_final: Optional[float]
    ef_ch4_offsite_ref_drainage_final: float
    ef_ch4_offsite_tier_2_drainage_final: Optional[float]
    ef_n2o_ref_drainage_final: float
    ef_n2o_tier_2_drainage_final: Optional[float]  # DRAINAGE EMISSIONS FINAL
    ef_doc_rewetting_initial: float
    ef_doc_rewetting_initial_tier_2: Optional[float]
    ef_co2_rewetting_initial: float
    ef_co2_rewetting_initial_tier_2: Optional[float]
    ef_ch4_rewetting_initial: float
    ef_ch4_rewetting_initial_tier_2: Optional[float]
    ef_n2o_rewetting_initial: float
    ef_n2o_rewetting_initial_tier_2: Optional[float]  # REWETTING EMISSIONS INITIAL
    ef_doc_rewetting_final: float
    ef_doc_rewetting_final_tier_2: Optional[float]
    ef_co2_rewetting_final: float
    ef_co2_rewetting_final_tier_2: Optional[float]
    ef_ch4_rewetting_final: float
    ef_ch4_rewetting_final_tier_2: Optional[float]
    ef_n2o_rewetting_final: float
    ef_n2o_rewetting_final_tier_2: Optional[float]  # REWETTING EMISSIONS FINAL
    maximum_area_for_water_management: float


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

                if self.fire_boolean_end and self.fire_periodicity_end < self.implementation_time + self.capitalization_time and self.area_affected_by_action_end != 0 and dry_matter_ref_fire != 0:
                    co2, co, ch4 = fire_co2_co_ch4(self.fire_periodicity_end, dry_matter_ref_fire, self.area_affected_by_action_end, self.rate_type, self.implementation_time, self.capitalization_time, self.percentage_area_burned_end, self.ef_co2_ref_fire if not self.ef_co2_tier_2_fire else self.ef_co2_tier_2_fire, self.ef_co_ref_fire if not self.ef_co_tier_2_fire else self.ef_co_tier_2_fire, self.ef_ch4_ref_fire if not self.ef_ch4_tier_2_fire else self.ef_ch4_tier_2_fire, self.methane_constant)

                    emissions_co2_yearly = breakdown_according_to_values(co2, yearly_time_dependent_parameter_breakdown(0, self.area_affected_by_action_end * dry_matter_ref_fire, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True))
                    emissions_co_yearly = breakdown_according_to_values(co, yearly_time_dependent_parameter_breakdown(0, self.area_affected_by_action_end * dry_matter_ref_fire, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True))
                    emissions_ch4_yearly = breakdown_according_to_values(ch4, yearly_time_dependent_parameter_breakdown(0, self.area_affected_by_action_end * dry_matter_ref_fire, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True))

                    co2_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_co2_yearly], ActivityTypes.FIRE_ON_SOIL, delay=self.delay)
                    co_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO, [Emission(e, GasTypes.CO) for e in emissions_co_yearly], ActivityTypes.FIRE_ON_SOIL, delay=self.delay)
                    ch4_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in emissions_ch4_yearly], ActivityTypes.FIRE_ON_SOIL, delay=self.delay)

                    self.result.yearly_emissions_by_sector_by_gas.append(co2_emission_set)
                    self.result.yearly_emissions_by_sector_by_gas.append(co_emission_set)
                    self.result.yearly_emissions_by_sector_by_gas.append(ch4_emission_set)

            except Exception as e:
                traceback.print_exc()
                raise e

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
                        # No return as I want it to crash if there is an error

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

                    total_n2o = yearly_time_dependent_parameter_breakdown(n2ostart, n2oend, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)

                    total_ch4_onsite = yearly_time_dependent_parameter_breakdown(ch4_start, ch4_end, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)
                    total_ch4_off_site = yearly_time_dependent_parameter_breakdown(ch4_start_ditches, ch4_end_ditches, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)

                    total_doc = yearly_time_dependent_parameter_breakdown(doc_start, doc_end, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)
                    total_co2 = yearly_time_dependent_parameter_breakdown(co2_start, co2_end, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)

                    return total_n2o, total_ch4_onsite, total_ch4_off_site, total_doc, total_co2, sum(total_n2o) + sum(total_ch4_onsite) + sum(total_ch4_off_site) + sum(total_doc) + sum(total_co2)

                except Exception as e:
                    traceback.print_exc()
                    raise e

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
                    except Exception as e:
                        traceback.print_exc()
                        # No return as I want it to crash if there is an error
                        raise e


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

                    total_n2o = yearly_time_dependent_parameter_breakdown(n2ostart, n2oend, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)

                    total_ch4_onsite = yearly_time_dependent_parameter_breakdown(ch4_start, ch4_end, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)
                    total_ch4_off_site = yearly_time_dependent_parameter_breakdown(ch4_start_ditches, ch4_end_ditches, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)

                    total_doc = yearly_time_dependent_parameter_breakdown(doc_start, doc_end, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)
                    total_co2 = yearly_time_dependent_parameter_breakdown(co2_start, co2_end, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)

                    return total_n2o, total_ch4_onsite, total_ch4_off_site, total_doc, total_co2, sum(total_n2o) + sum(total_ch4_onsite) + sum(total_ch4_off_site) + sum(total_doc) + sum(total_co2)

                except Exception as e:
                    traceback.print_exc()
                    raise e

            try:
                n2o_initial, ch4_onsite_initial, ch4_offsite_initial, doc_initial, co2_initial, total_initial = calculate_drainage_initial()
                n2o_final, ch4_onsite_final, ch4_offsite_final, doc_final, co2_final, total_final = calculate_drainage_final()

                n2o_total = [i + j for i, j in zip(n2o_initial, n2o_final)]
                ch4_onsite_total = [i + j for i, j in zip(ch4_onsite_initial, ch4_onsite_final)]
                ch4_offsite_total = [i + j for i, j in zip(ch4_offsite_initial, ch4_offsite_final)]
                doc_total = [i + j for i, j in zip(doc_initial, doc_final)]
                co2_total = [i + j for i, j in zip(co2_initial, co2_final)]

                co2_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in co2_total], ActivityTypes.DRAINAGE, delay=self.delay)
                doc_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.DOC, [Emission(e, GasTypes.DOC) for e in doc_total], ActivityTypes.DRAINAGE, delay=self.delay)
                ch4_onsite_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in ch4_onsite_total], ActivityTypes.DRAINAGE, delay=self.delay)
                ch4_offsite_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in ch4_offsite_total], ActivityTypes.DRAINAGE, delay=self.delay)
                n2o_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in n2o_total], ActivityTypes.DRAINAGE, delay=self.delay)

                self.result.yearly_emissions_by_sector_by_gas.append(co2_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(doc_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(ch4_onsite_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(ch4_offsite_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(n2o_emission_set)

            except Exception as e:
                traceback.print_exc()
                raise e

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
                except Exception as e:
                    traceback.print_exc()
                    raise e

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

                total_co2_doc_initial, total_ch4_initial, total_n2o_initital, total_rewetting_initial = rewetting_emissions(area_rewet_initial, ef_doc_rewetting_initial, ef_co2_rewetting_initial, ef_ch4_rewetting_initial, ef_n2o_rewetting_initial, self.methane_constant, self.nitrous_constant, self.rate_type, self.implementation_time, self.capitalization_time)
                total_co2_doc_final, total_ch4_final, total_n2o_final, total_rewetting_final = rewetting_emissions(area_rewet_final, ef_doc_rewetting_final, ef_co2_rewetting_final, ef_ch4_rewetting_final, ef_n2o_rewetting_final, self.methane_constant, self.nitrous_constant, self.rate_type, self.implementation_time, self.capitalization_time)

                co2_doc_emission_set_initial = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in total_co2_doc_initial], ActivityTypes.REWETTING, delay=self.delay)
                ch4_emission_set_initial = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in total_ch4_initial], ActivityTypes.REWETTING, delay=self.delay)
                n2o_emission_set_initial = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in total_n2o_initital], ActivityTypes.REWETTING, delay=self.delay)

                co2_doc_emission_set_final = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in total_co2_doc_final], ActivityTypes.REWETTING, delay=self.delay)
                ch4_emission_set_final = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in total_ch4_final], ActivityTypes.REWETTING, delay=self.delay)
                n2o_emission_set_final = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in total_n2o_final], ActivityTypes.REWETTING, delay=self.delay)

                self.result.yearly_emissions_by_sector_by_gas.append(co2_doc_emission_set_initial)
                self.result.yearly_emissions_by_sector_by_gas.append(ch4_emission_set_initial)
                self.result.yearly_emissions_by_sector_by_gas.append(n2o_emission_set_initial)

                self.result.yearly_emissions_by_sector_by_gas.append(co2_doc_emission_set_final)
                self.result.yearly_emissions_by_sector_by_gas.append(ch4_emission_set_final)
                self.result.yearly_emissions_by_sector_by_gas.append(n2o_emission_set_final)

            except Exception as e:
                traceback.print_exc()
                raise e

        try:
            calculate_fire_emissions()
            calculate_drainage_emissions()
            calculate_rewetting_emissions()
            
        except  Exception as e:
            traceback.print_exc()
            raise

@dataclass
class PeatExtraction(BaseModule):
        
    hectares_end  : float
    hectares_start  : float
    percentage_ditches_start  : float
    percentage_ditches_end  : float
    ef_co2_onsite_ref  : float
    ef_co2_onsite_tier_2  : Optional[float]
    ef_ch4_onsite_ref  : float
    ef_ch4_onsite_tier_2  : Optional[float]
    ef_n2o_onsite_ref  : float
    ef_n2o_onsite_tier_2  : Optional[float]
    ef_doc_offsite_ref  : float
    ef_doc_offsite_tier_2  : Optional[float]
    ef_ch4_offsite_ref  : float
    ef_ch4_offsite_tier_2 : Optional[float]
    methane_constant  : float
    nitrous_constant  : float
    weight_peat : float
    mass_tonnes_tier_2  : Optional[float]
    conversion_factor_volume  : float
    c_fraction_ref  : float
    extraction_height_start  : float
    extraction_height_end : float


    def calculate_emissions(self):
        def drainage_emissions():
            def yearly_emissions_calculation(ef_multiplication_parameter, hectars_start, hectars_end, ef, multiplier_start=1.0, multiplier_end=1.0):
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

                drainage_co2_doc_yearly = yearly_time_dependent_parameter_breakdown(co2_onsite_emissions_start + doc_offsite_emissions_start, co2_onsite_emissions_end + doc_offsite_emissions_end, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)
                drainage_ch4_yearly = yearly_time_dependent_parameter_breakdown(ch4_onsite_emissions_start + ch4_offsite_emissions_start, ch4_onsite_emissions_end + ch4_offsite_emissions_end, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)
                drainage_n2o_yearly = yearly_time_dependent_parameter_breakdown(n2o_onsite_emissions_start, n2o_onsite_emissions_end, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)

                drainage_peat_co2_doc_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in drainage_co2_doc_yearly], ActivityTypes.DRAINAGE_PEAT, delay=self.delay)
                drainage_peat_ch4_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in drainage_ch4_yearly], ActivityTypes.DRAINAGE_PEAT, delay=self.delay)
                drainage_peat_n2o_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.N2O, [Emission(e, GasTypes.N2O) for e in drainage_n2o_yearly], ActivityTypes.DRAINAGE_PEAT, delay=self.delay)

                self.result.yearly_emissions_by_sector_by_gas.append(drainage_peat_co2_doc_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(drainage_peat_ch4_emission_set)
                self.result.yearly_emissions_by_sector_by_gas.append(drainage_peat_n2o_emission_set)

            except Exception as e:
                traceback.print_exc()
                raise e

        def off_site_emissions():
            def yearly_emissions_calculation(mass_tonnes, hectares_start, hectares_end, height_of_extraction_start, height_of_extraction_end):
                return mass_tonnes * hectares_start * height_of_extraction_start * 100, mass_tonnes * hectares_end * height_of_extraction_end * 100

            try:
                mass_tonnes = self.weight_peat * self.conversion_factor_volume / self.c_fraction_ref if not self.mass_tonnes_tier_2 else self.mass_tonnes_tier_2
                air_dry_weight_start, air_dry_weight_end = yearly_emissions_calculation(mass_tonnes, self.hectares_start, self.hectares_end, self.extraction_height_start, self.extraction_height_end)

                em_start = air_dry_weight_start * self.c_fraction_ref * 44 / 12
                em_end = air_dry_weight_end * self.c_fraction_ref * 44 / 12

                offsite_emissions_yearly = yearly_time_dependent_parameter_breakdown(em_start, em_end, self.implementation_time, self.capitalization_time, self.rate_type, interim_values=True)
                offsite_emissions_total = sum(offsite_emissions_yearly)

                offsite_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in offsite_emissions_yearly], ActivityTypes.OFFSITE_PEAT, delay=self.delay)
                self.result.yearly_emissions_by_sector_by_gas.append(offsite_emission_set)

            except Exception as e:
                traceback.print_exc()
                raise e

        drainage_emissions()
        off_site_emissions()
