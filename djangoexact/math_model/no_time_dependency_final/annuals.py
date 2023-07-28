import traceback
from general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions

class AnnualCropland:

    def __init__(self, area_start, area_end, time_impl, time_cap, rate_end, rate_coefficient_end, socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2,
                            emission_factor_nitrous, nitrous_constant, methane_constant, ef_methane_agr_residues_main, combustion_factor_main, 
                            residue_main_tier_2, n_estimation_slope_main, n_estimation_intercept_main, yield_value_main, ef_methane_agr_residues_minor, combustion_factor_minor,residue_minor_tier_2,
                            n_estimation_slope_minor, n_estimation_intercept_minor, yield_value_minor, ef_nitrous_agr_residues_main, retained_main, ef_nitrous_agr_residues_minor, retained_minor,
                            n_content_ag_main, ratio_bg_ag_main, n_content_bg_main, n_content_ag_minor, ratio_bg_ag_minor, n_content_bg_minor
                            ):
        
        self.area_start = area_start
        self.area_end = area_end
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate = rate_end
        self.rate_coefficient = rate_coefficient_end
        self.socref = socref
        self.soc_tier_2 = soc_tier_2
        self.f_lu_ref = f_lu_ref
        self.f_lu_tier_2 = f_lu_tier_2
        self.f_i_ref = f_i_ref
        self.f_i_tier_2 = f_i_tier_2
        self.f_mg_ref = f_mg_ref
        self.f_mg_tier_2 = f_mg_tier_2
        self.emission_factor_nitrous = emission_factor_nitrous
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.ef_methane_agr_residues_main = ef_methane_agr_residues_main
        self.combustion_factor_main = combustion_factor_main
        self.residue_main_tier_2 = residue_main_tier_2
        self.n_estimation_slope_main = n_estimation_slope_main
        self.n_estimation_intercept_main = n_estimation_intercept_main
        self.yield_value_main = yield_value_main
        self.ef_methane_agr_residues_minor = ef_methane_agr_residues_minor
        self.combustion_factor_minor = combustion_factor_minor
        self.residue_minor_tier_2 = residue_minor_tier_2
        self.n_estimation_slope_minor = n_estimation_slope_minor
        self.n_estimation_intercept_minor = n_estimation_intercept_minor
        self.yield_value_minor = yield_value_minor
        self.ef_nitrous_agr_residues_main = ef_nitrous_agr_residues_main
        self.retained_main = retained_main
        self.ef_nitrous_agr_residues_minor = ef_nitrous_agr_residues_minor
        self.retained_minor = retained_minor
        self.n_content_ag_main = n_content_ag_main
        self.ratio_bg_ag_main = ratio_bg_ag_main
        self.n_content_bg_main = n_content_bg_main
        self.n_content_ag_minor = n_content_ag_minor
        self.ratio_bg_ag_minor = ratio_bg_ag_minor
        self.n_content_bg_minor = n_content_bg_minor

        # AUXILIARY VARIABLES FOR SOIL CALCULATION
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(min(area_start, area_end),max(area_start, area_end),self.time_impl, self.time_cap, self.rate)
        self.total_hectars = yearly_time_dependent_parameter_breakdown(min(area_start, area_end),max(area_start, area_end),self.time_impl, self.time_cap, self.rate, interim_values = True)
        # DEFAULTS FOR TIER 2 VALUES INITIALIZATION

        # RESULTS
        self.emissions_soil_yearly = []
        self.emissions_soil_total = 0

        self.emissions_som_yearly = []
        self.emissions_som_total = 0

        self.emissions_residue_burning_yearly = []
        self.emissions_residue_burning_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0
        
    def calculate_emissions(self):

        def calculate_emissions_soil():

            try:

                self.emissions_soil_yearly, self.emissions_soil_total = soil_emissions(self.hectars_before_20, min(self.area_start, self.area_end), max(self.area_start, self.area_end), self.socref,
                                        self.soc_tier_2, self.f_lu_tier_2, self.f_i_tier_2, self.f_mg_tier_2, self.f_lu_ref, self.f_i_ref, self.f_mg_ref)

            except Exception as e:
                traceback.print_exc()

        def calculate_emissions_som():
            try:
                # SUPPORT FUNCTIONS 
                def func1(area_start, area, rate_coefficient, time_impl, time_cap):

                    if area > area_start:
                        return time_cap + time_impl * rate_coefficient
                    else:
                        return time_impl * (1 - rate_coefficient)
                
                # ASSIGNMENT OF TIER 2 VALUES
                soc = self.socref if not self.soc_tier_2 else self.soc_tier_2
                f_lu = self.f_lu_ref if not self.f_lu_tier_2 else self.f_lu_tier_2
                f_i = self.f_i_ref if not self.f_i_tier_2 else self.f_i_tier_2
                f_mg = self.f_mg_ref if not self.f_mg_tier_2 else self.f_mg_tier_2

                # ACTUAL COMPUTATION

                reference_soc = soc * f_lu
                
                maximum_soc_20_years = soc * f_i * f_mg * f_lu 
                n2o_n_conversion = 44/28

                som_n2o = 0 if maximum_soc_20_years >= reference_soc else ((maximum_soc_20_years - reference_soc)/20/10*1000)  * self.emission_factor_nitrous * n2o_n_conversion * (self.nitrous_constant/1000)

                total = sum(self.total_hectars) * som_n2o

                # TODO: ask if this should be broken down proportionally, in that case we have to take an approach similar to the one used in the soil calculation
                self.emissions_som_yearly = yearly_constant_emissions_breakdown(total, self.time_impl, self.time_cap)
                self.emissions_som_total = total

            
            except Exception as e:
                traceback.print_exc()

        def calculate_emissions_residue_burning():

            ################## COMPUTATION OF AMOUNT OF KG OF METHANE ###################

            yield_value_main = self.yield_value_main * 1000
            yield_value_minor = self.yield_value_minor * 1000 if self.yield_value_minor else None

            ag_residue_main = self.residue_main_tier_2 * 1000 if self.residue_main_tier_2 else yield_value_main * self.n_estimation_slope_main + self.n_estimation_intercept_main
            ag_residue_tonnes_main = ag_residue_main / 1000
            if self.ef_methane_agr_residues_main: 
                main_season_methane = ag_residue_tonnes_main * self.ef_methane_agr_residues_main * self.combustion_factor_main
            else:
                main_season_methane = 0
            ag_residue_minor = self.residue_minor_tier_2 * 1000 if self.residue_minor_tier_2 else yield_value_minor * self.n_estimation_slope_minor + self.n_estimation_intercept_minor if yield_value_minor else 0
            ag_residue_tonnes_minor = ag_residue_minor / 1000 
            if self.ef_methane_agr_residues_minor:
                minor_season_methane = ag_residue_tonnes_minor * self.ef_methane_agr_residues_minor * self.combustion_factor_minor
            else:
                minor_season_methane = 0
            
            kg_methane = main_season_methane + minor_season_methane
            
            #################### COMPUTATION OF AMOUNT OF KG OF NITROUS ######################
            annual_n_residues_main = ag_residue_main * self.n_content_ag_main + (yield_value_main + ag_residue_main) * self.ratio_bg_ag_main * self.n_content_bg_main
            # COMPUTATION FOR MAIN
            # this means if "Burned"
            if self.ef_nitrous_agr_residues_main:
                main_season_nitrous = ag_residue_tonnes_main * self.ef_nitrous_agr_residues_main * self.combustion_factor_main
            # this means if "Retained"
            elif self.retained_main:
                n2o_n_conversion = 44/28
                main_season_nitrous = annual_n_residues_main * self.emission_factor_nitrous * n2o_n_conversion
            else:
                main_season_nitrous = 0
            # COMPUTATION FOR MINOR
            annual_n_residues_minor = ag_residue_minor * self.n_content_ag_minor + (yield_value_minor + ag_residue_minor) * self.ratio_bg_ag_minor * self.n_content_bg_minor if yield_value_minor else 0
            # COMPUTATION FOR MAIN
            # this means if "Burned"

            if self.ef_nitrous_agr_residues_minor:
                minor_season_nitrous = ag_residue_tonnes_minor * self.ef_nitrous_agr_residues_minor * self.combustion_factor_minor
            # this means if "Retained" BUT IN REALITY NOT REALLY, AT LEAST IT SEEMS TO WORK (WITHOUT A MINOR)
            elif self.retained_minor:
                n2o_n_conversion = 44/28
                minor_season_nitrous = annual_n_residues_minor * self.emission_factor_nitrous * n2o_n_conversion
            else:
                minor_season_nitrous = 0

            kg_nitrous = main_season_nitrous + minor_season_nitrous

            co2_crop = (kg_nitrous * self.nitrous_constant + kg_methane * self.methane_constant)/1000

            total = (sum(self.total_hectars)) * co2_crop
            
            # TODO: again check if func1 is necessary, same as above. Could be that it is sufficient to use sum of before and after 20
            self.emissions_residue_burning_total = total
            self.emissions_residue_burning_yearly = yearly_constant_emissions_breakdown(total, self.time_impl, self.time_cap)


        calculate_emissions_soil()
        calculate_emissions_som()
        calculate_emissions_residue_burning()
        
        try:
            self.emissions_total_yearly = [sum(x) for x in zip(self.emissions_residue_burning_yearly, self.emissions_soil_yearly, self.emissions_som_yearly)]
            self.total_emissions = sum(self.emissions_total_yearly)
            return self.total_emissions

        except Exception as e:
            traceback.print_exc()
            return None

    def evaluate_tier_2_defaults(self):
        pass

# inputs = [27, 93, 5, 17, 'D', 0.5, 87.0, None, 0.77, None, 1.0, None, 1.03, None, 0.005, 265.0, 28.0, None, 0.85, None, 0.88, 1.33, 50, None, None, None, None, None, None, None, True, None, False, 0.007, 0.22, 0.006, None, None, None]
# annual = (AnnualCropland(*inputs))

# annual.calculate_emissions()
