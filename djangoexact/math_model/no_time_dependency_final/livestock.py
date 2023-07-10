from general_functions import yearly_parameter_breakdown, plot_yearly_breakdown, plot_all_functions, ch4_head_calculation_general
import traceback, re
class Livestock():

    def __init__(self, time_impl, time_cap, methane_constant, head_number_start, head_number_end, 
                   rate_type_mef, specific_factor_default, specific_factor_start_tier_2, specific_factor_end_tier_2, # METHANE ENTERIC FERMENTATION EMISSIONS PARAMETERS
                   ef_prp_methane, percentage_prp_default, percentage_prp_tier_2_start, percentage_prp_tier_2_end, ef_system_methane, ch4_prp_tier_2_start, ch4_prp_tier_2_end, 
                   percentage_system_default, rate_type_mmm, tam, vser, # METHANE MANURE MANAGEMENT EMISSIONS PARAMETERS
                   ef_prp_nitrous_direct, ef_system_nitrous_direct, n2o_prp_tier_2_start_direct, n2o_prp_tier_2_end_direct, rate_type_nmm, ner, # NITROUS OXIDE MANURE MANAGEMENT EMISSIONS PARAMETERS DIRECT
                   ef_prp_nitrous_indirect_volatization, ef_system_nitrous_indirect_volatization, n2o_prp_tier_2_start_indirect_volatization, n2o_prp_tier_2_end_indirect_volatization,  # NITROUS OXIDE MANURE MANAGEMENT EMISSIONS PARAMETERS INDIRECT VOLATIZATION
                   ef_prp_nitrous_indirect_leaching, ef_system_nitrous_indirect_leaching, n2o_prp_tier_2_start_indirect_leaching, n2o_prp_tier_2_end_indirect_leaching # NITROUS OXIDE MANURE MANAGEMENT EMISSIONS PARAMETERS INDIRECT LEACHING
                 ):
        
        # INPUT PARAMETERS
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.methane_constant = methane_constant
        self.head_number_start = head_number_start
        self.head_number_end = head_number_end
        self.rate_type_mef = rate_type_mef
        self.specific_factor_default = specific_factor_default
        self.specific_factor_start_tier_2 = specific_factor_start_tier_2
        self.specific_factor_end_tier_2 = specific_factor_end_tier_2
        self.ef_prp_methane = ef_prp_methane
        self.percentage_prp_default = percentage_prp_default
        self.percentage_prp_tier_2_start = percentage_prp_tier_2_start
        self.percentage_prp_tier_2_end = percentage_prp_tier_2_end
        self.ef_system_methane = ef_system_methane
        self.ch4_prp_tier_2_start = ch4_prp_tier_2_start
        self.ch4_prp_tier_2_end = ch4_prp_tier_2_end
        self.percentage_system_default = percentage_system_default
        self.rate_type_mmm = rate_type_mmm
        self.tam = tam
        self.vser = vser
        self.ef_prp_nitrous_direct = ef_prp_nitrous_direct
        self.ef_system_nitrous_direct = ef_system_nitrous_direct
        self.n2o_prp_tier_2_start_direct = n2o_prp_tier_2_start_direct
        self.n2o_prp_tier_2_end_direct = n2o_prp_tier_2_end_direct
        self.rate_type_nmm = rate_type_nmm
        self.ner = ner
        self.ef_prp_nitrous_indirect_volatization = ef_prp_nitrous_indirect_volatization
        self.ef_system_nitrous_indirect_volatization = ef_system_nitrous_indirect_volatization
        self.n2o_prp_tier_2_start_indirect_volatization = n2o_prp_tier_2_start_indirect_volatization
        self.n2o_prp_tier_2_end_indirect_volatization = n2o_prp_tier_2_end_indirect_volatization
        self.ef_prp_nitrous_indirect_leaching = ef_prp_nitrous_indirect_leaching
        self.ef_system_nitrous_indirect_leaching = ef_system_nitrous_indirect_leaching
        self.n2o_prp_tier_2_start_indirect_leaching = n2o_prp_tier_2_start_indirect_leaching
        self.n2o_prp_tier_2_end_indirect_leaching = n2o_prp_tier_2_end_indirect_leaching

        # TIER 2 DEFAULTS

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
    
    def calculate_emissions(self):

        def calculate_methane_enteric_fermentation_emissions():
            
            try:
                specific_factor_start = self.specific_factor_default if not self.specific_factor_start_tier_2 else self.specific_factor_start_tier_2
                specific_factor_end = self.specific_factor_default if not self.specific_factor_end_tier_2 else self.specific_factor_end_tier_2

                emissions_start = specific_factor_start / 1000 * self.methane_constant * self.head_number_start
                emissions_end = specific_factor_end / 1000 * self.methane_constant * self.head_number_end

                self.mef_emissions_yearly = yearly_parameter_breakdown(self.time_impl, self.time_cap, emissions_start, emissions_end, self.rate_type_mef)
                self.mef_emissions = sum(self.mef_emissions_yearly)

            except Exception as e:
                traceback.print_exc()
        
        def calculate_methane_manure_management_emissions():
                
                try:
                    ch4_head_start = ch4_head_calculation_general(self.tam, self.vser, self.ef_prp_methane, self.percentage_prp_default, self.percentage_prp_tier_2_start, self.ef_system_methane, self.ch4_prp_tier_2_start, self.percentage_system_default)
                    ch4_head_end = ch4_head_calculation_general(self.tam, self.vser, self.ef_prp_methane, self.percentage_prp_default, self.percentage_prp_tier_2_end, self.ef_system_methane, self.ch4_prp_tier_2_end, self.percentage_system_default)
    
                    self.mmm_emissions_yearly = yearly_parameter_breakdown(self.time_impl, self.time_cap, ch4_head_start, ch4_head_end, self.rate_type_mmm)
                    self.mmm_emissions = sum(self.mmm_emissions_yearly)
    
                except Exception as e:
                    traceback.print_exc()

        def calculate_nitrous_manure_management_direct():
            
            try:
                n2o_head_start = ch4_head_calculation_general(self.tam, self.ner, self.ef_prp_nitrous_direct, self.percentage_prp_default, self.percentage_prp_tier_2_start, self.ef_system_nitrous_direct, self.n2o_prp_tier_2_start_direct, self.percentage_system_default)
                n2o_head_end = ch4_head_calculation_general(self.tam, self.ner, self.ef_prp_nitrous_direct, self.percentage_prp_default, self.percentage_prp_tier_2_end, self.ef_system_nitrous_direct, self.n2o_prp_tier_2_end_direct, self.percentage_system_default)

                self.nmm_emissions_yearly = yearly_parameter_breakdown(self.time_impl, self.time_cap, n2o_head_start, n2o_head_end, self.rate_type_nmm)
                self.nmm_emissions = sum(self.nmm_emissions_yearly)

            except Exception as e:
                traceback.print_exc()
            
        def calculate_nitrous_manure_management_indirect_volatization():

            try:
                n2o_head_start = ch4_head_calculation_general(self.tam, self.ner, self.ef_prp_nitrous_indirect_volatization, self.percentage_prp_default, self.percentage_prp_tier_2_start, self.ef_system_nitrous_indirect_volatization, self.n2o_prp_tier_2_start_indirect_volatization, self.percentage_system_default)
                n2o_head_end = ch4_head_calculation_general(self.tam, self.ner, self.ef_prp_nitrous_indirect_volatization, self.percentage_prp_default, self.percentage_prp_tier_2_end, self.ef_system_nitrous_indirect_volatization, self.n2o_prp_tier_2_end_indirect_volatization, self.percentage_system_default)

                self.nmm_indirect_volatization_emissions_yearly = yearly_parameter_breakdown(self.time_impl, self.time_cap, n2o_head_start, n2o_head_end, self.rate_type_nmm)
                self.nmm_indirect_volatization_emissions = sum(self.nmm_indirect_volatization_emissions_yearly)

            except Exception as e:
                traceback.print_exc()

        def calculate_nitrous_manure_management_indirect_leaching():

            try:
                n2o_head_start = ch4_head_calculation_general(self.tam, self.ner, self.ef_prp_nitrous_indirect_leaching, self.percentage_prp_default, self.percentage_prp_tier_2_start, self.ef_system_nitrous_indirect_leaching, self.n2o_prp_tier_2_start_indirect_leaching, self.percentage_system_default)
                n2o_head_end = ch4_head_calculation_general(self.tam, self.ner, self.ef_prp_nitrous_indirect_leaching, self.percentage_prp_default, self.percentage_prp_tier_2_end, self.ef_system_nitrous_indirect_leaching, self.n2o_prp_tier_2_end_indirect_leaching, self.percentage_system_default)

                self.nmm_indirect_leaching_emissions_yearly = yearly_parameter_breakdown(self.time_impl, self.time_cap, n2o_head_start, n2o_head_end, self.rate_type_nmm)
                self.nmm_indirect_leaching_emissions = sum(self.nmm_indirect_leaching_emissions_yearly)

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
        except Exception as e:
            traceback.print_exc()
    
    def evaluate_tier_2_defaults(self):
        # TODO: Add tier 2 defaults based on the front end
        pass
