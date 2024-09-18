from dataclasses import dataclass
import api.models as api_models
import api.calculators as calculators
from typing import Optional
import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils
import numpy as np


@dataclass
class BaseModuleReport:
    module: api_models.Module | api_models.LandModule

    calculator: Optional[calculators.BaseCalculator] | Optional[calculators.LandModuleCalculator] = None
    result: Optional[dict] = None

    def __post_init__(self):
        self.result = self.calculator.calculate()

    def get_result(self):
        return NotImplementedError


@dataclass
class AnnualCroplandReport(BaseModuleReport):

    module: api_models.AnnualCropland

    def __post_init__(self):
        self.calculator = calculators.AnnualCroplandCalculator(self.module)
        return super().__post_init__()

    def extract_emissions(self, data, activity_type, gas_type):
        for entry in data:
            if entry.activity == activity_type and entry.gas_type == gas_type:
                return [e.value for e in entry.emissions]
        return np.zeros(self.module.activity.implementation_years + self.module.activity.capitalization_years)

    def get_result(self):
        """
        class YearlyGasActivityEmissionSet(YearlyGasEmissionSet):

            def __init__(self, year, gas_type, emissions, activity, delay=0):
                super().__init__(year, gas_type, emissions, delay)
                # Can be a sub-activity, e.g. "Fire on Soil"
                self.activity: ActivityTypes = activity

            def to_dict(self):
                return {"year": self.year, "gas_type": {"name": self.gas_type.name if self.gas_type else None}, "emissions": [emission.to_dict() for emission in self.emissions], "activity": self.activity}
        """

        """
        Additional indicators sheet: hectars indicator is self.hectares_total. Livestock indicator under self.livestock_heads_yearly_breakdown. Catch (fish) under self.tonnes_catch_yearly_breakdown
        """

        module_title = self.module.module_type.name
        hectares = self.module.area
        main_season_crop_start = self.module.land_use_type_start.name
        main_season_crop_w = self.module.land_use_type_w.name
        main_season_crop_wo = self.module.land_use_type_wo.name

        tillage_management_type_start = self.module.tillage_management_type_start.name
        tillage_management_type_w = self.module.tillage_management_type_w.name
        tillage_management_type_wo = self.module.tillage_management_type_wo.name

        organic_input_type_start = self.module.organic_input_type_start.name
        organic_input_type_w = self.module.organic_input_type_w.name
        organic_input_type_wo = self.module.organic_input_type_wo.name

        residue_management_type_start = self.module.residue_management_type_start.name
        residue_management_type_w = self.module.residue_management_type_w.name
        residue_management_type_wo = self.module.residue_management_type_wo.name

        yield_start = "Default" if self.module.crop_yield_t2_start is None else self.module.crop_yield_t2_start
        yield_w = "Default" if self.module.crop_yield_t2_w is None else self.module.crop_yield_t2_w
        yield_wo = "Default" if self.module.crop_yield_t2_wo is None else self.module.crop_yield_t2_wo

        minor_season_crop_start = getattr(self.module.minor_land_use_type_start, "name", "None")
        minor_season_crop_w = getattr(self.module.minor_land_use_type_w, "name", "None")
        minor_season_crop_wo = getattr(self.module.minor_land_use_type_wo, "name", "None")

        minor_residue_management_type_start = getattr(self.module.minor_residue_management_type_start, "name", "None")
        minor_residue_management_type_w = getattr(self.module.minor_residue_management_type_w, "name", "None")
        minor_residue_management_type_wo = getattr(self.module.minor_residue_management_type_wo, "name", "None")

        minor_yield_start = "Default" if self.module.minor_yield_start is None else self.module.minor_yield_start
        minor_yield_w = "Default" if self.module.minor_yield_w is None else self.module.minor_yield_w
        minor_yield_wo = "Default" if self.module.minor_yield_wo is None else self.module.minor_yield_wo

        annual_hectares = self.calculator.math_w.hectares_total

        emissions_set: list[math_utils.YearlyGasActivityEmissionSet] = self.calculator.results_w.yearly_emissions_by_sector_by_gas
        biomass_co2 = self.extract_emissions(emissions_set, math_utils.ActivityTypes.BIOMASS, math_utils.GasTypes.CO2)
        soil_co2 = self.extract_emissions(emissions_set, math_utils.ActivityTypes.SOIL_CO2_CHANGE, math_utils.GasTypes.CO2)
        soil_n2o = self.extract_emissions(emissions_set, math_utils.ActivityTypes.SOM, math_utils.GasTypes.N2O)
        # fire_co2 = self.extract_emissions(emissions_set, math_utils.ActivityTypes.FIRE_ON_SOIL, math_utils.GasTypes.CO2.value)
        fire_n2o = self.extract_emissions(emissions_set, math_utils.ActivityTypes.RESIDUE_BURNING, math_utils.GasTypes.N2O.value)
        fire_ch4 = self.extract_emissions(emissions_set, math_utils.ActivityTypes.RESIDUE_BURNING, math_utils.GasTypes.CH4)

        print(f"Start year of activities: {self.module.activity.project.start_year_of_activities}")
        print(f"Last year of accounting: {self.module.activity.project.last_year_of_accounting}")
        print(f"Implementation years: {self.module.activity.implementation_years}")
        print(f"Capitalization years: {self.module.activity.capitalization_years}")
        print(f"Total years: {self.module.activity.implementation_years + self.module.activity.capitalization_years}")
        print("\n")

        print(f"{module_title} - Hectares:", hectares)
        print(f"{module_title} - Main season crop start:", main_season_crop_start)
        print(f"{module_title} - Main season crop w:", main_season_crop_w)
        print(f"{module_title} - Main season crop wo:", main_season_crop_wo)
        print("\n")
        print(f"{module_title} - Tillage management type start:", tillage_management_type_start)
        print(f"{module_title} - Tillage management type w:", tillage_management_type_w)
        print(f"{module_title} - Tillage management type wo:", tillage_management_type_wo)
        print("\n")
        print(f"{module_title} - Organic input type start:", organic_input_type_start)
        print(f"{module_title} - Organic input type w:", organic_input_type_w)
        print(f"{module_title} - Organic input type wo:", organic_input_type_wo)
        print("\n")
        print(f"{module_title} - Residue management type start:", residue_management_type_start)
        print(f"{module_title} - Residue management type w:", residue_management_type_w)
        print(f"{module_title} - Residue management type wo:", residue_management_type_wo)
        print("\n")
        print(f"{module_title} - Yield start:", yield_start)
        print(f"{module_title} - Yield w:", yield_w)
        print(f"{module_title} - Yield wo:", yield_wo)
        print("\n")
        print(f"{module_title} - Minor season crop start:", minor_season_crop_start)
        print(f"{module_title} - Minor season crop w:", minor_season_crop_w)
        print(f"{module_title} - Minor season crop wo:", minor_season_crop_wo)
        print("\n")
        print(f"{module_title} - Minor residue management type start:", minor_residue_management_type_start)
        print(f"{module_title} - Minor residue management type w:", minor_residue_management_type_w)
        print(f"{module_title} - Minor residue management type wo:", minor_residue_management_type_wo)
        print("\n")
        print(f"{module_title} - Minor yield start:", minor_yield_start)
        print(f"{module_title} - Minor yield w:", minor_yield_w)
        print(f"{module_title} - Minor yield wo:", minor_yield_wo)
        print("\n")
        print(f"{module_title} - Annual hectares:", annual_hectares)
        print("\n")
        print(f"{module_title} - CO2 in soils:", soil_co2)
        print(f"{module_title} - CO2 in biomass:", biomass_co2)
        print(f"{module_title} - N2O in soils:", soil_n2o)
        # print(f"{module_title} - CO2 from fires:", fire_co2)
        print(f"{module_title} - N2O from fires:", fire_n2o)
        print(f"{module_title} - CH4 from fires:", fire_ch4)

        import xlsxwriter

        workbook = xlsxwriter.Workbook("annual_cropland_results.xlsx")
        worksheet = workbook.add_worksheet("Results")

        light_orange = workbook.add_format({"bg_color": "#fce4d6"})
        light_blue = workbook.add_format({"bg_color": "#d9e1f2"})

        worksheet.write(0, 0, "Activity and GHGs / Years")
        worksheet.write(1, 0, str(self.module.activity.name), light_orange)
        worksheet.write(2, 0, "Annual Cropland", light_blue)
        worksheet.write(3, 0, "CO2 in biomass")
        worksheet.write(4, 0, "CO2 in soils")
        worksheet.write(5, 0, "N2O in soils")
        worksheet.write(6, 0, "N2O from fires")
        worksheet.write(7, 0, "CH4 from fires")

        for i, year in enumerate(range(self.module.activity.project.start_year_of_activities, self.module.activity.project.last_year_of_accounting)):
            worksheet.write(0, i + 1, year)
            worksheet.write(3, i + 1, biomass_co2[i])
            worksheet.write(4, i + 1, soil_co2[i])
            worksheet.write(5, i + 1, soil_n2o[i])
            worksheet.write(6, i + 1, fire_n2o[i])
            worksheet.write(7, i + 1, fire_ch4[i])

        worksheet = workbook.add_worksheet("Metadata")

        worksheet.write(0, 0, str(self.module.activity.name), light_orange)
        worksheet.write(0, 1, "START")
        worksheet.write(0, 2, "WITH")
        worksheet.write(0, 3, "WITHOUT")

        worksheet.write(1, 0, "Annual Cropland", light_blue)
        worksheet.write(2, 0, "Hectares")
        worksheet.write(3, 0, "Main season crop")
        worksheet.write(4, 0, "Tillage management type")
        worksheet.write(5, 0, "Organic input type")
        worksheet.write(6, 0, "Residue management type")
        worksheet.write(7, 0, "Yield")
        worksheet.write(8, 0, "Minor season crop")
        worksheet.write(9, 0, "Minor residue management type")
        worksheet.write(10, 0, "Minor yield")

        worksheet.write(2, 1, hectares)
        worksheet.write(3, 1, main_season_crop_start)
        worksheet.write(4, 1, tillage_management_type_start)
        worksheet.write(5, 1, organic_input_type_start)
        worksheet.write(6, 1, residue_management_type_start)
        worksheet.write(7, 1, yield_start)
        worksheet.write(8, 1, minor_season_crop_start)
        worksheet.write(9, 1, minor_residue_management_type_start)
        worksheet.write(10, 1, minor_yield_start)

        worksheet.write(2, 2, hectares)
        worksheet.write(3, 2, main_season_crop_w)
        worksheet.write(4, 2, tillage_management_type_w)
        worksheet.write(5, 2, organic_input_type_w)
        worksheet.write(6, 2, residue_management_type_w)
        worksheet.write(7, 2, yield_w)
        worksheet.write(8, 2, minor_season_crop_w)
        worksheet.write(9, 2, minor_residue_management_type_w)
        worksheet.write(10, 2, minor_yield_w)

        worksheet.write(2, 3, hectares)
        worksheet.write(3, 3, main_season_crop_wo)
        worksheet.write(4, 3, tillage_management_type_wo)
        worksheet.write(5, 3, organic_input_type_wo)
        worksheet.write(6, 3, residue_management_type_wo)
        worksheet.write(7, 3, yield_wo)
        worksheet.write(8, 3, minor_season_crop_wo)
        worksheet.write(9, 3, minor_residue_management_type_wo)
        worksheet.write(10, 3, minor_yield_wo)

        worksheet = workbook.add_worksheet("Additional Indicators")

        worksheet.write(0, 0, "Activity and GHGs / Years")
        for i, year in enumerate(range(self.module.activity.project.start_year_of_activities, self.module.activity.project.last_year_of_accounting)):
            worksheet.write(0, i + 1, year)

        worksheet.write(1, 0, "Units Targeted", light_orange)
        # worksheet.write(1, 1, "hectares")

        worksheet.write(2, 0, "Land Uses Targeted (ha)", light_blue)
        worksheet.write(3, 0, "Annual Cropland")
        for i, year in enumerate(range(self.module.activity.project.start_year_of_activities, self.module.activity.project.last_year_of_accounting)):
            worksheet.write(3, i + 1, annual_hectares[i])

        workbook.close()
