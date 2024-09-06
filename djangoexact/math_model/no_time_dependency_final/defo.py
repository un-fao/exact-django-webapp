import re
import traceback

from .general_functions import (
    BaseModule,
    breakdown_according_to_values,
    soil_emissions,
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


class Deforestation(BaseModule):
    def __init__(self, ha_start, ha_end, time_impl, time_cap, rate_type_soil, biomass_final_1_year_t_per_ha, biomass_final_1_year_t_per_ha_tier_2, nitrous_constant, methane_constant, fire_bool, n2o_vegetation, ch4_vegetation, cf_vegetation, moisture_emission_factor, litter, litter_tier_2, dw, dw_tier_2, hwp_before_t_dm_per_ha, mangrove_factor, bgb_t_c_per_ha_tier_2, agb_t_c_per_ha_tier_2, agb_t_dm_per_ha_default, bgb_t_dm_per_ha_default_input_parameter, c_n_ratio, soc_after_defo_tier_2, soc_reference_default, soc_reference_tier_2, fmg_start_tier_2, fmg_end_tier_2, fi_start_tier_2, fi_end_tier_2, flu_start_tier_2, flu_end_tier_2, soc_start_tier_2, soc_end_tier_2, fmg_start_default, fmg_end_default, fi_start_default, fi_end_default, flu_start_default, flu_end_default, soc_start_default, soc_end_default, calculate_soc_som, delay):
        self.ha_start = ha_start
        self.ha_end = ha_end
        self.area_deforested = abs(ha_end - ha_start)
        self.time_impl = time_impl
        self.time_cap = time_cap
        self.rate_type_soil = rate_type_soil
        self.biomass_final_1_year_t_per_ha_default = biomass_final_1_year_t_per_ha
        self.biomass_final_1_year_t_per_ha_tier_2 = biomass_final_1_year_t_per_ha_tier_2
        self.nitrous_constant = nitrous_constant
        self.methane_constant = methane_constant
        self.fire_bool = fire_bool
        self.n2o_vegetation = n2o_vegetation
        self.ch4_vegetation = ch4_vegetation
        self.cf_vegetation = cf_vegetation
        self.moisture_emission_factor = moisture_emission_factor
        self.litter = litter
        self.litter_tier_2 = litter_tier_2
        self.dw = dw
        self.dw_tier_2 = dw_tier_2
        self.hwp_before_t_dm_per_ha = hwp_before_t_dm_per_ha
        self.mangrove_factor = mangrove_factor
        self.bgb_t_c_per_ha_tier_2 = bgb_t_c_per_ha_tier_2
        self.agb_t_c_per_ha_tier_2 = agb_t_c_per_ha_tier_2
        self.agb_t_dm_per_ha_default = agb_t_dm_per_ha_default
        self.bgb_t_dm_per_ha_default_input_parameter = bgb_t_dm_per_ha_default_input_parameter
        self.c_n_ratio = c_n_ratio
        self.soc_after_defo_tier_2 = soc_after_defo_tier_2
        self.soc_reference_default = soc_reference_default
        self.soc_reference_tier_2 = soc_reference_tier_2
        self.fmg_start_tier_2 = fmg_start_tier_2
        self.fmg_end_tier_2 = fmg_end_tier_2
        self.fi_start_tier_2 = fi_start_tier_2
        self.fi_end_tier_2 = fi_end_tier_2
        self.flu_start_tier_2 = flu_start_tier_2
        self.flu_end_tier_2 = flu_end_tier_2
        self.soc_start_tier_2 = soc_start_tier_2
        self.soc_end_tier_2 = soc_end_tier_2
        self.fmg_start_default = fmg_start_default
        self.fmg_end_default = fmg_end_default
        self.fi_start_default = fi_start_default
        self.fi_end_default = fi_end_default
        self.flu_start_default = flu_start_default
        self.flu_end_default = flu_end_default
        self.soc_start_default = soc_start_default
        self.soc_end_default = soc_end_default
        self.calculate_soc_som = calculate_soc_som
        self.delay = delay

        # TODO: Assigned FMG, FLU, FI values. Maybe once everything has been done change this structure
        self.fmg_start = self.fmg_start_tier_2 if self.fmg_start_tier_2 else self.fmg_start_default
        self.fmg_end = self.fmg_end_tier_2 if self.fmg_end_tier_2 else self.fmg_end_default
        self.flu_start = self.flu_start_tier_2 if self.flu_start_tier_2 else self.flu_start_default
        self.flu_end = self.flu_end_tier_2 if self.flu_end_tier_2 else self.flu_end_default
        self.fi_start = self.fi_start_tier_2 if self.fi_start_tier_2 else self.fi_start_default
        self.fi_end = self.fi_end_tier_2 if self.fi_end_tier_2 else self.fi_end_default

        self.soc_start = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start if not self.soc_start_tier_2 else self.soc_start_tier_2 * self.fmg_start * self.flu_start * self.fi_start
        self.soc_end = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end if not self.soc_end_tier_2 else self.soc_end_tier_2 * self.fmg_end * self.flu_end * self.fi_end

        # AUXILIARY VARIABLES FOR SOIL CALCULATION
        self.hectars_before_20, self.hectars_after_20 = yearly_time_dependent_20_year_breakdown(0, self.area_deforested, self.time_impl, self.time_cap, self.rate_type_soil)
        self.total_hectares = yearly_time_dependent_parameter_breakdown(self.area_deforested, 0, self.time_impl, self.time_cap, self.rate_type_soil)
        # self.hectars_before_20 = yearly_time_dependent_20_year_breakdown(0, self.area_deforested, self.time_impl, self.time_cap, self.rate_type_soil)

        # TIER 2 VALUES
        self.agb_t_c_tier_2_default = self.agb_t_dm_per_ha_default * self.mangrove_factor
        self.bgb_t_c_tier_2_default = self.bgb_t_dm_per_ha_default_input_parameter * self.agb_t_dm_per_ha_default * self.mangrove_factor
        self.hwp_before_t_c_tier_2_default = self.agb_t_dm_per_ha_default * self.mangrove_factor if self.hwp_before_t_dm_per_ha > self.agb_t_dm_per_ha_default else self.hwp_before_t_dm_per_ha * self.mangrove_factor
        self.biomass_final_1_year_t_per_ha_tier_2_tier_2_default = self.biomass_final_1_year_t_per_ha_default
        self.litter_tier_2_default = self.litter if not self.litter_tier_2 else self.litter_tier_2
        self.dw_tier_2_default = self.dw if not self.dw_tier_2 else self.dw_tier_2
        self.soc_start_tier_2_default = self.soc_start_default * self.fmg_start * self.flu_start * self.fi_start
        self.soc_end_tier_2_default = self.soc_end_default * self.fmg_end * self.flu_end * self.fi_end

        # RESULTS
        self.emissions_biomass_gain_yearly = []
        self.emissions_biomass_gain_total = 0

        self.emissions_biomass_loss_yearly = []
        self.emissions_biomass_loss_total = 0

        self.emissions_dom_yearly = []
        self.emissions_dom_total = 0

        self.emissions_soil_yearly = []
        self.emissions_soil_total = 0

        self.emissions_fire_fsom_yearly = []
        self.emissions_fire_fsom_total = 0

        self.emissions_som_yearly = []
        self.emissions_som_total = 0

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)

    def calculate_emissions(self):
        def calculate_biomass_loss_emissions():
            try:
                bgb_t_dm_per_ha_default = self.bgb_t_dm_per_ha_default_input_parameter * self.agb_t_dm_per_ha_default

                agb_t_c = self.agb_t_dm_per_ha_default * self.mangrove_factor if not self.agb_t_c_per_ha_tier_2 else self.agb_t_c_per_ha_tier_2
                bgb_t_c = bgb_t_dm_per_ha_default * self.mangrove_factor if not self.bgb_t_c_per_ha_tier_2 else self.bgb_t_c_per_ha_tier_2

                hwp_before_t_c = self.agb_t_dm_per_ha_default * self.mangrove_factor if self.hwp_before_t_dm_per_ha > self.agb_t_dm_per_ha_default else self.hwp_before_t_dm_per_ha * self.mangrove_factor

                biomass_forest_agb_bgb_t_c = agb_t_c + bgb_t_c - hwp_before_t_c

                biomass_forest_agb_bgb_t_co2 = biomass_forest_agb_bgb_t_c * (44 / 12)

                biomass_loss = biomass_forest_agb_bgb_t_co2 * self.area_deforested

                self.emissions_biomass_loss_yearly = yearly_constant_emissions_breakdown(biomass_loss, self.time_impl, self.time_cap, self.rate_type_soil)
                self.emissions_biomass_loss_total = biomass_loss

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.emissions_biomass_loss_yearly], activity=ActivityTypes.BIOMASS))

            except Exception as e:
                traceback.print_exc()

        def calculate_biomass_gain_emissions():
            try:
                if self.biomass_final_1_year_t_per_ha_tier_2:
                    biomass_final_1_year_t_per_ha = self.biomass_final_1_year_t_per_ha_tier_2
                else:
                    biomass_final_1_year_t_per_ha = self.biomass_final_1_year_t_per_ha_default

                self.emissions_biomass_gain_total = 0 if self.emissions_biomass_loss_total == 0 else -(biomass_final_1_year_t_per_ha * self.area_deforested * (44 / 12))
                self.emissions_biomass_gain_yearly = yearly_constant_emissions_breakdown(self.emissions_biomass_gain_total, self.time_impl, self.time_cap, self.rate_type_soil)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.emissions_biomass_gain_yearly], activity=ActivityTypes.BIOMASS))

            except Exception as e:
                traceback.print_exc()

        def calculate_dom_emissions():
            try:
                litter = self.litter if not self.litter_tier_2 else self.litter_tier_2
                dw = self.dw if not self.dw_tier_2 else self.dw_tier_2

                biomass_forest_dom_t_c_per_ha = litter + dw
                biomass_forest_dom_t_co2_per_ha = biomass_forest_dom_t_c_per_ha * (44 / 12)

                dom_loss = biomass_forest_dom_t_co2_per_ha * self.area_deforested
                self.emissions_dom_yearly = yearly_constant_emissions_breakdown(dom_loss, self.time_impl, self.time_cap, self.rate_type_soil)
                self.emissions_dom_total = dom_loss

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CO2, emissions=[Emission(e, GasTypes.CO2) for e in self.emissions_dom_yearly], activity=ActivityTypes.DOM))

            except Exception as e:
                traceback.print_exc()

        def calculate_fire_emissions():
            try:
                fire_t_dm_per_ha = self.agb_t_dm_per_ha_default - self.hwp_before_t_dm_per_ha if self.fire_bool else 0

                fire_kg_n2o = fire_t_dm_per_ha * self.n2o_vegetation * self.cf_vegetation if self.fire_bool else 0
                fire_kg_ch4 = fire_t_dm_per_ha * self.ch4_vegetation * self.cf_vegetation if self.fire_bool else 0

                total_ch4_n2o_per_ha = (fire_kg_ch4 * self.methane_constant + fire_kg_n2o * self.nitrous_constant) / 1000

                fire_N_w = total_ch4_n2o_per_ha * self.area_deforested

                self.emissions_fire_fsom_yearly = yearly_constant_emissions_breakdown(fire_N_w, self.time_impl, self.time_cap, self.rate_type_soil)
                self.emissions_fire_fsom_total = fire_N_w

                total_ch4_per_ha = fire_kg_ch4 * self.methane_constant / 1000
                total_n2o_per_ha = fire_kg_n2o * self.nitrous_constant / 1000

                emissions_ch4 = yearly_constant_emissions_breakdown(total_ch4_per_ha * self.area_deforested, self.time_impl, self.time_cap, self.rate_type_soil)
                emissions_n2o = yearly_constant_emissions_breakdown(total_n2o_per_ha * self.area_deforested, self.time_impl, self.time_cap, self.rate_type_soil)

                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.CH4, emissions=[Emission(e, GasTypes.CH4) for e in emissions_ch4], activity=ActivityTypes.RESIDUE_BURNING))
                self.result.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(year=0, gas_type=GasTypes.N2O, emissions=[Emission(e, GasTypes.N2O) for e in emissions_n2o], activity=ActivityTypes.RESIDUE_BURNING))

            except Exception as e:
                traceback.print_exc()

        calculate_biomass_loss_emissions()
        calculate_biomass_gain_emissions()
        calculate_dom_emissions()
        calculate_fire_emissions()

        try:
            self.emissions_total_yearly = [sum(x) for x in zip(self.emissions_biomass_gain_yearly, self.emissions_biomass_loss_yearly, self.emissions_dom_yearly, self.emissions_soil_yearly, self.emissions_fire_fsom_yearly)]
            self.total_emissions = sum(self.emissions_total_yearly)
            return self.total_emissions

        except Exception as e:
            traceback.print_exc()
            return None
