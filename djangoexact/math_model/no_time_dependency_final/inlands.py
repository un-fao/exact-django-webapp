import math
from .general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions
import traceback

class AnnexedModule:

    def __init__(self, fire_boolean_end, fire_periodicity_end, area_affected_by_action_end, dry_matter_ref_fire, dry_matter_tier_2_fire, percentage_area_burned_end, ef_co2_ref_fire, ef_co2_tier_2_fire, ef_co_ref_fire, ef_co_tier_2_fire, ef_ch4_ref_fire, ef_ch4_tier_2_fire, methane_constant, rate_coefficient_fire_end, # FIRE EMISSIONS
                    time_impl, time_cap, nitrous_constant,  # GENERAL INFO
                    rate_coefficient_drainage_end, ef_doc_ref_drainage_initial, ef_doc_tier_2_drainage_initial, area_drained_start, area_drained_end, ef_co2_ref_drainage_initial, ef_co2_tier_2_drainage_initial, percentage_ditches_start, percentage_ditches_end, ef_ch4_onsite_ref_drainage_initial, ef_ch4_onsite_tier_2_drainage_initial, ef_ch4_offsite_ref_drainage_initial, ef_ch4_offsite_tier_2_drainage_initial, ef_n2o_ref_drainage_initial, ef_n2o_tier_2_drainage_initial, # DRAINAGE EMISSIONS INITIAL
                    ef_doc_ref_drainage_final, ef_doc_tier_2_drainage_final, ef_co2_ref_drainage_final, ef_co2_tier_2_drainage_final, ef_ch4_onsite_ref_drainage_final, ef_ch4_onsite_tier_2_drainage_final, ef_ch4_offsite_ref_drainage_final, ef_ch4_offsite_tier_2_drainage_final, ef_n2o_ref_drainage_final, ef_n2o_tier_2_drainage_final, # DRAINAGE EMISSIONS FINAL
                    ):
        
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
        self.rate_coefficient_fire_end = rate_coefficient_fire_end
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.nitrous_constant = nitrous_constant
        self.rate_coefficient_drainage_end = rate_coefficient_drainage_end
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

        pass

    def calculate_emissions(self,):

        def calculate_fire_emissions():

            # TODO: check if all tier2 values should be assigned in the constructor
            def fire_co2_co_ch4(fire_periodicity, dry_matter, area, rate_coefficient, time_impl, time_cap, percentage_area_burned, ef_co2, ef_co, ef_ch4, methane_constant):

                biomass_start = 0
                biomass_end = area * dry_matter

                total_biomass = sum(yearly_time_dependent_parameter_breakdown(biomass_start, biomass_end, time_impl, time_cap, rate_coefficient, interim_values = True))

                multiplication_parameter_co2_co = (1/fire_periodicity * percentage_area_burned * ef_co2 * 44/12/1000) + (1/fire_periodicity * percentage_area_burned  * ef_co * 2 / 1000)
                multiplication_parameter_ch4 = 1/fire_periodicity * percentage_area_burned * ef_ch4 * methane_constant / 1000

                return total_biomass * multiplication_parameter_co2_co, total_biomass * multiplication_parameter_ch4
            
            try:
                if self.fire_boolean_end or self.fire_periodicity_end > self.time_impl + self.time_cap:
                    co2_co, ch4 = fire_co2_co_ch4(self.fire_periodicity_end, self.dry_matter_ref_fire if not self.dry_matter_tier_2_fire else self.dry_matter_tier_2_fire, self.area_affected_by_action_end, self.rate_coefficient_fire_end, self.time_impl, self.time_cap, self.percentage_area_burned_end, self.ef_co2_ref_fire if not self.ef_co2_tier_2_fire else self.ef_co2_tier_2_fire, self.ef_co_ref_fire if not self.ef_co_tier_2_fire else self.ef_co_tier_2_fire, self.ef_ch4_ref_fire if not self.ef_ch4_tier_2_fire else self.ef_ch4_tier_2_fire, self.methane_constant)
                    # TODO: ask how they should be broken down
                    self.emissions_fire_total = co2_co + ch4
                    self.emissions_fire_yearly = breakdown_according_to_values(self.emissions_fire_total, yearly_time_dependent_parameter_breakdown(0, self.area_affected_by_action_end * self.dry_matter_ref_fire if not self.dry_matter_tier_2_fire else self.area_affected_by_action_end * self.dry_matter_tier_2_fire, self.time_impl, self.time_cap, self.rate_coefficient_fire_end, interim_values = True))
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
                            em_end = ef * area_affected_by_module * percentage_area_multiplier_end * multiplying_constant
                        elif area_affected_by_action_end < area_affected_by_module:
                            em_end = 0
                        else:
                            em_end = ef * (area_affected_by_module - area_affected_by_action_end) * percentage_area_multiplier_end *  multiplying_constant
                
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


                    n2ostart, n2oend = calculate_emissions_start_end(ef_n2o, self.area_drained_start, self.area_drained_end, 1, 1, self.area_affected_by_action_end, 44/28 * self.nitrous_constant/1000)

                    ch4_start, ch4_end = calculate_emissions_start_end(ef_ch4_on_site, self.area_drained_start, self.area_drained_end, 1 - self.percentage_ditches_start, 1 - self.percentage_ditches_end, self.area_affected_by_action_end, self.methane_constant/1000) 
                    ch4_start_ditches, ch4_end_ditches = calculate_emissions_start_end(ef_ch4_off_site, self.area_drained_start, self.area_drained_end, self.percentage_ditches_start, self.percentage_ditches_end, self.area_affected_by_action_end, self.methane_constant/1000)

                    co2_start, co2_end = calculate_emissions_start_end(ef_co2, self.area_drained_start, 1, 1, self.area_drained_end, self.area_affected_by_action_end, 44/12)
                    doc_start, doc_end = calculate_emissions_start_end(ef_doc, self.area_drained_start, 1, 1, self.area_drained_end, self.area_affected_by_action_end, 44/12)


                    total_n2o = yearly_time_dependent_20_year_breakdown(n2ostart, n2oend, self.time_impl, self.time_cap, self.rate_coefficient_drainage_end, interim_values = True)

                    total_ch4_onsite = yearly_time_dependent_20_year_breakdown(ch4_start, ch4_end, self.time_impl, self.time_cap, self.rate_coefficient_drainage_end, interim_values = True)
                    total_ch4_off_site = yearly_time_dependent_20_year_breakdown(ch4_start_ditches, ch4_end_ditches, self.time_impl, self.time_cap, self.rate_coefficient_drainage_end, interim_values = True)

                    total_doc = yearly_time_dependent_20_year_breakdown(doc_start, doc_end, self.time_impl, self.time_cap, self.rate_coefficient_drainage_end, interim_values = True)
                    total_co2 = yearly_time_dependent_20_year_breakdown(co2_start, co2_end, self.time_impl, self.time_cap, self.rate_coefficient_drainage_end, interim_values = True)

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
                            em_end = ef * (area_affected_by_action_start) * percentage_area_multiplier_end *  multiplying_constant
                
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


                    n2ostart, n2oend = calculate_emissions_start_end(ef_n2o, self.area_drained_start, self.area_drained_end, 1, 1, self.area_affected_by_action_end, 44/28 * self.nitrous_constant/1000)

                    ch4_start, ch4_end = calculate_emissions_start_end(ef_ch4_on_site, self.area_drained_start, self.area_drained_end, 1 - self.percentage_ditches_start, 1 - self.percentage_ditches_end, self.area_affected_by_action_end, self.methane_constant/1000) 
                    ch4_start_ditches, ch4_end_ditches = calculate_emissions_start_end(ef_ch4_off_site, self.area_drained_start, self.area_drained_end, self.percentage_ditches_start, self.percentage_ditches_end, self.area_affected_by_action_end, self.methane_constant/1000)

                    co2_start, co2_end = calculate_emissions_start_end(ef_co2, self.area_drained_start, 1, 1, self.area_drained_end, self.area_affected_by_action_end, 44/12)
                    doc_start, doc_end = calculate_emissions_start_end(ef_doc, self.area_drained_start, 1, 1, self.area_drained_end, self.area_affected_by_action_end, 44/12)


                    total_n2o = yearly_time_dependent_20_year_breakdown(n2ostart, n2oend, self.time_impl, self.time_cap, self.rate_coefficient_drainage_end, interim_values = True)

                    total_ch4_onsite = yearly_time_dependent_20_year_breakdown(ch4_start, ch4_end, self.time_impl, self.time_cap, self.rate_coefficient_drainage_end, interim_values = True)
                    total_ch4_off_site = yearly_time_dependent_20_year_breakdown(ch4_start_ditches, ch4_end_ditches, self.time_impl, self.time_cap, self.rate_coefficient_drainage_end, interim_values = True)

                    total_doc = yearly_time_dependent_20_year_breakdown(doc_start, doc_end, self.time_impl, self.time_cap, self.rate_coefficient_drainage_end, interim_values = True)
                    total_co2 = yearly_time_dependent_20_year_breakdown(co2_start, co2_end, self.time_impl, self.time_cap, self.rate_coefficient_drainage_end, interim_values = True)

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
                    co2_doc_y_start, co2_doc_y_end = yearly_emissions_calculation(ef_doc + ef_co2, area_rewetted, 44/12)
                    ch4_y_start, ch4_y_end = yearly_emissions_calculation(ef_ch4, area_rewetted, methane_constant/1000 * 16/12)
                    n2o_n_y_start, n2o_n_y_end = yearly_emissions_calculation(ef_n2o, area_rewetted, nitrous_constant/1000 * 44/28)

                    total_co2_doc = yearly_time_dependent_parameter_breakdown(co2_doc_y_start, co2_doc_y_end, time_impl, time_cap, rate_coefficient, interim_values = True)
                    total_ch4 = yearly_time_dependent_parameter_breakdown(ch4_y_start, ch4_y_end, time_impl, time_cap, rate_coefficient, interim_values = True)
                    total_n2o = yearly_time_dependent_parameter_breakdown(n2o_n_y_start, n2o_n_y_end, time_impl, time_cap, rate_coefficient, interim_values = True)
                    
                    return total_co2_doc, total_ch4, total_n2o, sum(total_co2_doc) + sum(total_ch4) + sum(total_n2o)
                except:
                    traceback.print_exc()
                    return
                
            # TODO: check with Lorenzo why initial and final
            try:
                total_co2_doc_initial, total_ch4_initial, total_n2o_initital, total_rewetting_initial = rewetting_emissions(area_rewetted_initial, ef_doc_initial, ef_co2_initial, ef_ch4_initial, ef_n2o_initial, methane_constant, nitrous_constant, rate_coefficient, time_impl, time_cap)
                total_co2_doc_final, total_ch4_final, total_n2o_final, total_rewetting_final = rewetting_emissions(area_rewetted_final, ef_doc_final, ef_co2_final, ef_ch4_final, ef_n2o_final, methane_constant, nitrous_constant, rate_coefficient, time_impl, time_cap)
                
                total_rewetting = total_rewetting_final + total_rewetting_initial
                self.emissions_rewetting_yearly = [i + j + k + l + m + n for i, j, k, l, m, n in zip(total_co2_doc_initial, total_ch4_initial, total_n2o_initital, total_co2_doc_final, total_ch4_final, total_n2o_final)]
                self.emissions_rewetting_total = total_rewetting
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

            

        
