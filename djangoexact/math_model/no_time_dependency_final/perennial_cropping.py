import traceback
from .general_functions import yearly_constant_emissions_breakdown, yearly_time_dependent_parameter_breakdown, yearly_time_dependent_20_year_breakdown, breakdown_according_to_values, soil_emissions

class PerennialCropping:

    def __init__(self, area_start, area_end, time_impl, time_cap, rate, 
                    nitrous_constant, methane_constant, residue_burnt, emission_factor_burning_nitrous,
                    emission_factor_burning_methane, combustion_factor, fire_periodicity_default, fire_periodicity_tier_2, t_biomass_tier_2, 
                    agb_rate_default, agb_rate_tier_2, agb_maximum_c, bgb_rate_default, bgb_rate_tier_2,
                    socref, soc_tier_2, f_lu_ref, f_lu_tier_2, f_i_ref, f_i_tier_2, f_mg_ref, f_mg_tier_2,
                    ):
        
        self.area_start = area_start
        self.area_end = area_end
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate = rate
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.residue_burnt = residue_burnt
        self.emission_factor_burning_nitrous = emission_factor_burning_nitrous
        self.emission_factor_burning_methane = emission_factor_burning_methane
        self.combustion_factor = combustion_factor
        self.fire_periodicity_default = fire_periodicity_default
        self.fire_periodicity_tier_2 = fire_periodicity_tier_2
        self.t_biomass_tier_2 = t_biomass_tier_2
        self.agb_rate_default = agb_rate_default
        self.agb_rate_tier_2 = agb_rate_tier_2
        self.agb_maximum_c = agb_maximum_c
        self.bgb_rate_default = bgb_rate_default
        self.bgb_rate_tier_2 = bgb_rate_tier_2
        self.socref = socref
        self.soc_tier_2 = soc_tier_2
        self.f_lu_ref = f_lu_ref
        self.f_lu_tier_2 = f_lu_tier_2
        self.f_i_ref = f_i_ref
        self.f_i_tier_2 = f_i_tier_2
        self.f_mg_ref = f_mg_ref
        self.f_mg_tier_2 = f_mg_tier_2

        # Added values
        self.total_hectars = yearly_time_dependent_parameter_breakdown(area_start, area_end,self.time_impl, self.time_cap, self.rate)
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(area_start, area_end, self.time_impl, self.time_cap, self.rate)

        # RESULTS
        self.yearly_residue_emissions = []
        self.total_residue_emissions = 0

        self.yearly_bio_emissions = []
        self.total_bio_emissions = 0

        self.yearly_som_emissions = []
        self.total_som_emissions = 0

        self.yearly_soil_emissions = []
        self.total_soil_emissions = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

    def calculate_emissions(self,):

        def calculate_residue():
            
            try:
                fire_periodicity = self.fire_periodicity_default if not self.fire_periodicity_tier_2 else self.fire_periodicity_tier_2
                ag_tc = self.agb_rate_default if not self.agb_rate_tier_2 else self.agb_rate_tier_2
                t_biomass = ag_tc * 0.5 /0.47 if not self.t_biomass_tier_2 else self.t_biomass_tier_2

                ################## COMPUTATION OF AMOUNT OF KG OF METHANE ###################

                kg_methane = t_biomass * self.emission_factor_burning_methane * self.combustion_factor / fire_periodicity if self.residue_burnt else 0
                
                #################### COMPUTATION OF AMOUNT OF KG OF NITROUS ######################
                
                kg_nitrous = t_biomass * self.emission_factor_burning_nitrous * self.combustion_factor / fire_periodicity if self.residue_burnt else 0

                co2_crop = (kg_nitrous * self.nitrous_constant + kg_methane * self.methane_constant)/1000

                total = sum(self.total_hectars) * co2_crop

                self.yearly_residue_emissions = breakdown_according_to_values(total, self.total_hectars)
                self.total_residue_emissions = total
            except Exception as e:
                traceback.print_exc()

        def calculate_bio():

            try:
                agb_rate = self.agb_rate_default * 44/12 if not self.agb_rate_tier_2 else self.agb_rate_tier_2 * 44/12
                bgb_rate = self.bgb_rate_default * 44/12 if not self.bgb_rate_tier_2 else self.bgb_rate_tier_2 * 44/12
                
                if self.agb_rate_tier_2:
                    max_agb = 0 if self.agb_rate_default < self.agb_rate_tier_2 else self.agb_maximum_c * 44/12
                else:
                    max_agb = self.agb_maximum_c * 44/12
                
                biomass_accumulation_rate = agb_rate + bgb_rate

                max_years_growth = max_agb/agb_rate 

                calculated = biomass_accumulation_rate * sum(self.total_hectars)

                tabular = (max_agb + bgb_rate * max_years_growth) * self.area_end

                total = - min(calculated, tabular) if (max_agb != 0 and self.area_end != 0) else - calculated

                self.yearly_bio_emissions = breakdown_according_to_values(total, self.total_hectars)
                self.total_bio_emissions = total
            
            except Exception as e:
                traceback.print_exc()

        def calculate_som():
            
            try:
                # ASSIGNMENT OF TIER 2 VALUES
                soc = self.socref if not self.soc_tier_2 else self.soc_tier_2
                f_lu = self.f_lu_ref if not self.f_lu_tier_2 else self.f_lu_tier_2
                f_i = self.f_i_ref if not self.f_i_tier_2 else self.f_i_tier_2
                f_mg = self.f_mg_ref if not self.f_mg_tier_2 else self.f_mg_tier_2

                # ACTUAL COMPUTATION

                reference_soc = soc * f_lu
                maximum_soc_20_years = soc * f_i * f_mg * f_lu 
                n2o_n_conversion = 44/28


                som_n2o = 0 if maximum_soc_20_years > reference_soc else (reference_soc - maximum_soc_20_years) * 5  * n2o_n_conversion / 1000
                
                total = - som_n2o * sum(self.total_hectars)

                self.yearly_som_emissions = breakdown_according_to_values(total, self.total_hectars)
                self.total_som_emissions = total

            except Exception as e:
                traceback.print_exc()

        def calculate_soil():

            try:
                self.yearly_soil_emissions, self.total_soil_emissions = soil_emissions(self.hectars_before_20, self.area_start, self.area_end,
                                    self.socref, self.soc_tier_2, self.f_lu_tier_2, self.f_i_tier_2, self.f_mg_tier_2, 
                                    self.f_lu_ref, self.f_i_ref, self.f_mg_ref)
            except Exception as e:
                traceback.print_exc()
        
        calculate_residue()
        calculate_bio()
        calculate_som()
        calculate_soil()

        try:
            self.emissions_total_yearly = [i+j+k+l for i,j,k,l in zip(self.yearly_residue_emissions, self.yearly_bio_emissions, self.yearly_som_emissions, self.yearly_soil_emissions)]
            self.total_emissions = sum(self.emissions_total_yearly)
            return self.total_emissions
        except Exception as e:
            traceback.print_exc()

    def evaluate_tier_2_defaults():
        pass
        

# wo = [0, 88.0, 5, 15, 'D', 265.0, 28.0, False, 2.3, 0.21, 0.85, 1, None, None, 2.97, None, 27.3, 0.77, None, 76.0, None, 0.72, None, 1.44, None, 1.04, None]
# peren_start = PerennialCropping(*wo)
# peren_start.calculate_emissions()
# print(peren_start.total_emissions)
# print(peren_start.emissions_total_yearly)
