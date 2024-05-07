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


class CoastalWetland(BaseModule):
    def __init__(
        self,
        maximum_area_for_water_management,
        area_drained_start,
        area_drained_end,
        rate_type,
        time_impl,
        time_cap,
        agb_default,
        bgb_default,
        litter_default,
        deadwood_default,
        soil_1m_default,
        EF_drainage_default,
        agb_tier_2,
        bgb_tier_2,
        litter_tier_2,
        deadwood_tier_2,
        soil_1m_tier_2,
        EF_drainage_tier_2,
        area_excavated_start,
        area_excavated_end,
        area_revegated_start,
        area_revegated_end,
        percentage_c_lost_excavation_default,
        percentage_c_lost_excavation_tier_2,
        ef_rewetting_carbon_default,
        ef_rewetting_methane_default,
        ef_rewetting_carbon_tier_2,
        ef_rewetting_methane_tier_2,
        soil_type,
        methane_constant,
    ):
        self.maximum_area_for_water_management = maximum_area_for_water_management  # front_end input
        self.area_drained_start = area_drained_start  # area drained start, expects float
        self.area_drained_end = area_drained_end  # area drained end, expects float
        self.rate_type = rate_type  # rate type, expects string
        self.time_impl = time_impl  # time implementation, expects int front end input
        self.time_cap = time_cap  # time capitalization, expects int front end input
        self.agb_default = agb_default  # match climate moisture and type of vegetation to IPCC A2903, if present return value, else 0
        self.bgb_default = bgb_default  # match climate moisture and type of vegetation to IPCC A2111, if present return value, else 0
        self.litter_default = litter_default  # match climate moisture and type of vegetation to IPCC A2128, if present return value, else 0
        self.deadwood_default = deadwood_default  # match climate moisture and type of vegetation to IPCC A2145, if present return value, else 0
        self.soil_1m_default = soil_1m_default  # if type of vegetation == MANGROVE and soil tier == Tier 1:
        #             match COUNTRY to table Atwood and take Mg C/ha
        # else:
        #         if soil type == 'Mineral':
        #             match climate moisture and type of vegetation to IPCC A2162
        #         elif soil type == 'Organic':
        #             match climate moisture and type of vegetation to IPCC A2179
        #         elif soil type == 'Aggregated'
        #             match climate moisture and type of vegetation to IPCC A2196
        #         else:
        #             return 0

        self.EF_drainage_default = EF_drainage_default  # match climate moisture and type of vegetation to IPCC A2213, if present return value, else 0
        self.agb_tier_2 = agb_tier_2
        self.bgb_tier_2 = bgb_tier_2
        self.litter_tier_2 = litter_tier_2
        self.deadwood_tier_2 = deadwood_tier_2
        self.soil_1m_tier_2 = soil_1m_tier_2
        self.EF_drainage_tier_2 = EF_drainage_tier_2

        self.area_excavated_start = area_excavated_start  # area of excavation at start
        self.area_excavated_end = area_excavated_end  # area excavated, front end input expects float
        self.percentage_c_lost_excavation_default = percentage_c_lost_excavation_default  # standard value, 96%, discuss and ask whether to include in model directly
        self.percentage_c_lost_excavation_tier_2 = percentage_c_lost_excavation_tier_2

        self.ef_rewetting_carbon_default = ef_rewetting_carbon_default  # match climate moisture and type of vegetation to IPCC A2230, if present return value, else 0
        self.ef_rewetting_methane_default = ef_rewetting_methane_default  # match climate moisture and type of vegetation to IPCC A2247, if present return value, else 0
        self.ef_rewetting_carbon_tier_2 = ef_rewetting_carbon_tier_2
        self.ef_rewetting_methane_tier_2 = ef_rewetting_methane_tier_2
        self.soil_type = soil_type  # front end input expects string
        self.area_start_rewetting = 0 if self.area_drained_start == 0 else max(0, -self.area_drained_end + self.area_drained_start)
        self.area_end_rewetting = 0 if self.area_drained_end == 0 else max(0, -self.area_drained_end + self.area_drained_start)

        self.area_revegated_start = area_revegated_start  # area revegetated start, expects float
        self.area_revegated_end = area_revegated_end    # area revegetated end, expects float

        self.methane_constant = methane_constant  # front end input

        # HECTARES DRAINED
        # TODO: ask Lorenzo why this is done
        # NOTE: set to 0 and self.area_drained_end - self.area_excavated_end as if not we have double counting. No need for checks as area_drained_end is always greater than area_excavated_end
        self.hectares_drained_before_20, self.hectares_drained_after_20 = yearly_time_dependent_20_year_breakdown(0, self.area_drained_end - self.area_excavated_end, self.time_impl, self.time_cap, self.rate_type)
        self.hectares_drained = yearly_time_dependent_parameter_breakdown(0, self.area_drained_end, self.time_impl, self.time_cap, self.rate_type)

        self.hectares_revegetated_before_20, self.hectares_revegetated_after_20 = yearly_time_dependent_20_year_breakdown(0, self.area_revegated_end - self.area_revegated_start, self.time_impl, self.time_cap, self.rate_type)
        self.hectares_revegated = yearly_time_dependent_parameter_breakdown(0, self.area_revegated_end, self.time_impl, self.time_cap, self.rate_type)
        # TIER 2 DEFAULTS
        self.agb_tier_2_default = self.agb_default * 0.451
        self.bgb_tier_2_default = self.bgb_default * self.agb_tier_2_default
        self.litter_tier_2_default = self.litter_default
        self.deadwood_tier_2_default = self.deadwood_default
        self.soil_1m_tier_2_default = self.soil_1m_default
        self.EF_drainage_tier_2_default = self.EF_drainage_default
        self.percentage_c_lost_excavation_tier_2_default = self.percentage_c_lost_excavation_default
        self.ef_rewetting_carbon_tier_2_default = self.ef_rewetting_carbon_default
        self.ef_rewetting_methane_tier_2_default = self.ef_rewetting_methane_default

        # RESULTS
        self.emissions_biomass_yearly_drainage = []
        self.emissions_biomass_total_drainage = 0

        self.emissions_soil_yearly_drainage = []
        self.emissions_soil_total_drainage = 0

        # TODO: add emissions yearly drainage
        self.emissions_total_drainage = 0

        # TODO: add emissions yearly extraction
        self.emissions_total_extraction_excavation = 0
        self.emissions_yearly_extraction_excavation = []

        # TODO: add emissions yearly rewetting
        self.emissions_total_rewetting = 0
        self.emissions_yearly_rewetting_carbon = []
        self.emissions_yearly_rewetting_methane = []

        self.emissions_total_yearly = []
        self.total_emissions = 0

        self.result = Result(self.time_impl, self.time_cap)

        pass

    def calculate_emissions(
        self,
    ):
        def calculate_drainage():
            def calculate_biomass():
                try:
                    agb = self.agb_default * 0.451 if not self.agb_tier_2 else self.agb_tier_2
                    bgb = self.bgb_default * agb if not self.bgb_tier_2 else self.bgb_tier_2
                    litter = self.litter_default if not self.litter_tier_2 else self.litter_tier_2
                    deadwood = self.deadwood_default if not self.deadwood_tier_2 else self.deadwood_tier_2

                    # TODO: ask Lorenzo about this variable, should it be 0? Should it be calculated?
                    stock_c_biomass_start = 0
                    area_drained_end = self.area_drained_end
                    # NOT USED IN THE EXCEL, TODO: ask Lorenzo
                    area_drained_start = self.area_drained_start

                    stock_c_biomass_end = (agb + bgb + litter + deadwood) * area_drained_end

                    self.emissions_biomass_total_drainage = (stock_c_biomass_start - stock_c_biomass_end) * (44 / 12)

                    # soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.emissions_soil_yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=self.delay)
                    # self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

                    biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(self.emissions_biomass_total_drainage, GasTypes.CO2)], ActivityTypes.BIOMASS, delay=0)
                    self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

                except Exception as e:
                    traceback.print_exc()
                    pass

            def calculate_soil():
                try:
                    soil_1m = self.soil_1m_default if not self.soil_1m_tier_2 else self.soil_1m_tier_2
                    EF_drainage = self.EF_drainage_default if not self.EF_drainage_tier_2 else self.EF_drainage_tier_2

                    maximum_soil_years = 1000 if EF_drainage == 0 else int(soil_1m / EF_drainage)
                    maximum_soil_emissions = soil_1m * 44 / 12

                    # TODO: ask lorenzo: HERE THERE IS A 0 IN AREA_DRAINED_START ERROR?
                    calculated = EF_drainage * 44 / 12 * sum(self.hectares_drained)
                    maximum = max(0, self.area_drained_end) * maximum_soil_emissions

                    total = calculated if abs(calculated) < abs(maximum) else maximum

                    self.emissions_soil_total_drainage = total
                    self.emissions_soil_yearly_drainage = breakdown_according_to_values(total, self.hectares_drained)

                    soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.emissions_soil_yearly_drainage], ActivityTypes.SOIL_CO2_CHANGE, delay=0)
                    self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

                except Exception as e:
                    traceback.print_exc()
                    pass

            calculate_biomass()
            calculate_soil()

            self.emissions_total_drainage = self.emissions_biomass_total_drainage + self.emissions_soil_total_drainage

        def calculate_extraction_excavation():
            try:
                # THIS VARIABLE IS SET TO 0 AS DEFAULT ON THE EXCEL, ASK LORENZO
                area_excavated_start = self.area_excavated_start

                area_excavated = self.area_excavated_end

                agb = self.agb_default * 0.451 if not self.agb_tier_2 else self.agb_tier_2
                bgb = self.bgb_default * agb if not self.bgb_tier_2 else self.bgb_tier_2
                litter = self.litter_default if not self.litter_tier_2 else self.litter_tier_2
                deadwood = self.deadwood_default if not self.deadwood_tier_2 else self.deadwood_tier_2
                soil_1m = self.soil_1m_default if not self.soil_1m_tier_2 else self.soil_1m_tier_2
                percentage_c_lost_excavation = self.percentage_c_lost_excavation_default if not self.percentage_c_lost_excavation_tier_2 else self.percentage_c_lost_excavation_tier_2

                biomass_c = agb + bgb + litter + deadwood
                soil_c = soil_1m * percentage_c_lost_excavation

                biomass_co2 = biomass_c * 44 / 12
                soil_co2 = soil_c * 44 / 12

                total = (biomass_co2 + soil_co2) * (area_excavated - area_excavated_start)

                total_biomass = biomass_co2 * (area_excavated - area_excavated_start)
                total_soil = soil_co2 * (area_excavated - area_excavated_start)
                # TODO: ask Lorenzo about this variable and how it should be split across the years

                hectares_excavated = yearly_time_dependent_parameter_breakdown(area_excavated - area_excavated_start, 0, self.time_impl, self.time_cap, self.rate_type)
                self.emissions_total_extraction_excavation = total

                self.emissions_yearly_extraction_excavation = breakdown_according_to_values(total, hectares_excavated)

                emissions_yearly_biomass_extraction_excavation = breakdown_according_to_values(total_biomass, hectares_excavated)
                emissions_yearly_soil_extraction_excavation = breakdown_according_to_values(total_soil, hectares_excavated)

                biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_yearly_biomass_extraction_excavation], ActivityTypes.BIOMASS, delay=0)
                self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

                soil_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in emissions_yearly_soil_extraction_excavation], ActivityTypes.SOIL_CO2_CHANGE, delay=0)
                self.result.yearly_emissions_by_sector_by_gas.append(soil_emission_set)

                pass
            except Exception as e:
                traceback.print_exc()
                pass
            pass

        def calculate_rewetting_revegetation():

            def calculate_biomass():
                try:
                    agb = self.agb_default * 0.451 if not self.agb_tier_2 else self.agb_tier_2
                    bgb = self.bgb_default * agb if not self.bgb_tier_2 else self.bgb_tier_2
                    litter = self.litter_default if not self.litter_tier_2 else self.litter_tier_2
                    deadwood = self.deadwood_default if not self.deadwood_tier_2 else self.deadwood_tier_2

                    biomass_emissions_total = (agb + bgb + litter + deadwood) / (20) * sum(self.hectares_revegetated_before_20)

                    yearly_biomass = breakdown_according_to_values(biomass_emissions_total, self.hectares_revegetated_before_20)

                    return yearly_biomass

                except:
                    traceback.print_exc()
                    pass
            
            try:
                self.ef_rewetting_methane_default = 0 if not self.soil_type == "<18" else self.ef_rewetting_methane_default
                ef_rewetting_carbon = self.ef_rewetting_carbon_default if not self.ef_rewetting_carbon_tier_2 else self.ef_rewetting_carbon_tier_2
                ef_rewetting_methane = self.ef_rewetting_methane_default if not self.ef_rewetting_methane_tier_2 else self.ef_rewetting_methane_tier_2

                self.emissions_yearly_rewetting_carbon = yearly_time_dependent_parameter_breakdown(0, 44 / 12 * self.area_end_rewetting * ef_rewetting_carbon, self.time_impl, self.time_cap, self.rate_type)
                self.emissions_yearly_rewetting_methane = yearly_time_dependent_parameter_breakdown(0, self.methane_constant * self.area_end_rewetting * ef_rewetting_methane / 1000, self.time_impl, self.time_cap, self.rate_type)

                total_emission_yearly_rewetting_carbon = sum(self.emissions_yearly_rewetting_carbon)
                total_emission_yearly_rewetting_methane = sum(self.emissions_yearly_rewetting_methane)

                self.emissions_total_rewetting = total_emission_yearly_rewetting_carbon + total_emission_yearly_rewetting_methane

                rewetting_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in self.emissions_yearly_rewetting_carbon], ActivityTypes.REWETTING_REVEGETATION, delay=0)
                self.result.yearly_emissions_by_sector_by_gas.append(rewetting_emission_set)

                rewetting_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in self.emissions_yearly_rewetting_methane], ActivityTypes.REWETTING_REVEGETATION, delay=0)
                self.result.yearly_emissions_by_sector_by_gas.append(rewetting_emission_set)

                biomass_emissions = calculate_biomass()
                biomass_emission_set = YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in biomass_emissions], ActivityTypes.BIOMASS, delay=0)
                self.result.yearly_emissions_by_sector_by_gas.append(biomass_emission_set)

            except Exception as e:
                traceback.print_exc()
                pass

        calculate_drainage()
        calculate_extraction_excavation()
        calculate_rewetting_revegetation()

        self.total_emissions = self.emissions_total_drainage + self.emissions_total_extraction_excavation + self.emissions_total_rewetting
        # TODO: add other components
        self.emissions_total_yearly = [i + j + k for i, j, k in zip(self.emissions_biomass_yearly_drainage, self.emissions_soil_yearly_drainage, self.emissions_yearly_rewetting_carbon)]
