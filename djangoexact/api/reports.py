from dataclasses import dataclass

import xlsxwriter.format
import xlsxwriter.worksheet
import api.models as api_models
import api.calculators as calculators
from typing import Optional
import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils
import numpy as np
import xlsxwriter
from enum import Enum
import logging as log
import os
from django.conf import settings
import openpyxl as pxl
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.styles import Color, PatternFill, Font, Border

log.basicConfig(level=log.DEBUG)


class Colors(Enum):
    LIGHT_ORANGE = "fce4d6"
    LIGHT_BLUE = "d9e1f2"
    LIGHT_BEIGE = "ddd9c4"


class ReportFactory:

    @staticmethod
    def get_report_class(module: api_models.Module | api_models.LandModule):
        if isinstance(module, api_models.PerennialCropland):
            return PerennialCroplandReport
        elif isinstance(module, api_models.AnnualCropland):
            return AnnualCroplandReport
        elif isinstance(module, api_models.LandModule):
            return LandModuleReport
        else:
            raise ValueError("Invalid module type.")


@dataclass
class BaseProjectReport:
    project: api_models.Project
    filename: str = None
    start_year_of_activities: int = None
    last_year_of_accounting: int = None
    implementation_years: int = None
    capitalization_years: int = None
    duration: int = None

    workbook: pxl.Workbook = None
    results_worksheet: Worksheet = None
    metadata_worksheet: Worksheet = None
    additional_indicators_worksheet: Worksheet = None
    activities: list[api_models.Activity] = None

    colors: Colors = Colors

    def __post_init__(self):
        self.activities = self.project.activities.all()
        pass

    def build_report_skeleton(self):
        log.debug(f"Building report skeleton for {self.project.name}")
        self.start_year_of_activities = self.project.start_year_of_activities
        self.last_year_of_accounting = self.project.last_year_of_accounting
        self.implementation_years = self.project.implementation_years
        self.capitalization_years = self.project.capitalization_years
        self.duration = self.implementation_years + self.capitalization_years

        self.filename = os.path.join(settings.BASE_DIR, "reports", f"{str(self.project.name)[:6]}_results.xlsx")

        wb = xlsxwriter.Workbook(self.filename)
        wb.add_worksheet("Results")
        wb.add_worksheet("Metadata")
        wb.add_worksheet("Additional Indicators")
        wb.close()

        self.workbook = pxl.load_workbook(self.filename)
        self.results_worksheet = self.workbook["Results"]
        self.metadata_worksheet = self.workbook["Metadata"]
        self.additional_indicators_worksheet = self.workbook["Additional Indicators"]

        self.results_worksheet.cell(row=1, column=1, value="Activity and GHGs / Years")

        light_orange = PatternFill(start_color=self.colors.LIGHT_ORANGE.value, end_color=self.colors.LIGHT_ORANGE.value, fill_type="solid")

        self.results_worksheet.cell(row=2, column=1, value="Total Carbon Balance")
        self.results_worksheet.cell(row=2, column=1).fill = light_orange

        self.results_worksheet.cell(row=3, column=1, value="Cumulative balance in Tco2-eq")
        self.results_worksheet.cell(row=4, column=1, value="Yearly balance in Tco2-eq")
        self.results_worksheet.cell(row=5, column=1, value="CO2 in biomass")
        self.results_worksheet.cell(row=6, column=1, value="CO2 in soils")
        self.results_worksheet.cell(row=7, column=1, value="Other CO2")
        self.results_worksheet.cell(row=8, column=1, value="CH4")
        self.results_worksheet.cell(row=9, column=1, value="N20")
        self.results_worksheet.cell(row=10, column=1, value="Other GHGs")

        for i, year in enumerate(range(self.start_year_of_activities, self.last_year_of_accounting)):
            self.results_worksheet.cell(row=1, column=i + 2, value=year)

        self.metadata_worksheet.cell(row=1, column=2, value="START")
        self.metadata_worksheet.cell(row=1, column=3, value="WITH")
        self.metadata_worksheet.cell(row=1, column=4, value="WITHOUT")

        self.additional_indicators_worksheet.cell(row=1, column=1, value="Activity and GHGs / Years")

        for i, year in enumerate(range(self.start_year_of_activities, self.last_year_of_accounting)):
            self.additional_indicators_worksheet.cell(row=1, column=i + 2, value=year)

        log.debug(f"Report skeleton for {self.project.name} built.")
        return self.workbook

    def build_report(self):
        self.build_report_skeleton()

        for activity in self.activities:
            activity_report = BaseActivityReport(self, activity)
            activity_report.build_activity_skeleton()

            modules = activity.modules
            log.debug(f"Modules length: {len(modules)}")
            for module in modules:
                ReportClass = ReportFactory.get_report_class(module)
                module_report = ReportClass(module, activity_report)
                module_report.build_report()

        self.workbook.save(self.filename)


@dataclass
class BaseActivityReport:

    project_report: BaseProjectReport
    activity: api_models.Activity

    activity_title: str = None
    start_year_of_activities: int = None
    last_year_of_accounting: int = None
    implementation_years: int = None
    capitalization_years: int = None
    duration: int = None

    workbook: pxl.Workbook = None
    results_worksheet: Worksheet = None
    metadata_worksheet: Worksheet = None
    additional_indicators_worksheet: Worksheet = None

    def __post_init__(self):
        self.workbook = self.project_report.workbook
        self.results_worksheet = self.project_report.results_worksheet
        self.metadata_worksheet = self.project_report.metadata_worksheet
        self.additional_indicators_worksheet = self.project_report.additional_indicators_worksheet

    def build_activity_skeleton(self):
        log.debug(f"Building activity skeleton for {self.activity.name}")
        self.activity_title = self.activity.name
        self.start_year_of_activities = self.activity.project.start_year_of_activities
        self.last_year_of_accounting = self.activity.project.last_year_of_accounting
        self.implementation_years = self.activity.implementation_years
        self.capitalization_years = self.activity.capitalization_years
        self.duration = self.implementation_years + self.capitalization_years

        last_results_row = self.results_worksheet.max_row + 1
        last_metadata_row = self.metadata_worksheet.max_row + 1
        last_additional_indicators_row = self.additional_indicators_worksheet.max_row + 1
        log.debug(f"Last results row: {last_results_row}")
        log.debug(f"Last metadata row: {last_metadata_row}")
        log.debug(f"Last additional indicators row: {last_additional_indicators_row}")

        light_orange = PatternFill(start_color=Colors.LIGHT_ORANGE.value, end_color=Colors.LIGHT_ORANGE.value, fill_type="solid")
        light_blue = PatternFill(start_color=Colors.LIGHT_BLUE.value, end_color=Colors.LIGHT_BLUE.value, fill_type="solid")

        self.results_worksheet.cell(row=last_results_row, column=1, value=str(self.activity_title)[:6])
        self.results_worksheet.cell(row=last_results_row, column=1).fill = light_orange

        self.metadata_worksheet.cell(row=last_metadata_row, column=1, value=str(self.activity_title)[:6])
        self.metadata_worksheet.cell(row=last_metadata_row, column=1).fill = light_orange

        self.additional_indicators_worksheet.cell(row=last_additional_indicators_row, column=1, value=str(self.activity_title)[:6])
        self.additional_indicators_worksheet.cell(row=last_additional_indicators_row, column=1).fill = light_orange

        self.additional_indicators_worksheet.cell(row=last_additional_indicators_row + 1, column=1, value="Land Uses Targeted (ha)")
        self.additional_indicators_worksheet.cell(row=last_additional_indicators_row + 1, column=1).fill = light_blue

        self.additional_indicators_worksheet.cell(row=last_additional_indicators_row + 2, column=1, value="With project")
        self.additional_indicators_worksheet.cell(row=last_additional_indicators_row + 2, column=1, value="With project").fill = PatternFill(start_color=Colors.LIGHT_BEIGE.value, end_color=Colors.LIGHT_BEIGE.value, fill_type="solid")
        self.additional_indicators_worksheet.cell(row=last_additional_indicators_row + 3, column=1, value="Without project")
        self.additional_indicators_worksheet.cell(row=last_additional_indicators_row + 3, column=1, value="Without project").fill = PatternFill(start_color=Colors.LIGHT_BEIGE.value, end_color=Colors.LIGHT_BEIGE.value, fill_type="solid")

        log.debug(f"Activity skeleton for {self.activity.name} built.")

        return self.workbook


@dataclass
class BaseModuleReport:
    module: api_models.Module | api_models.LandModule
    activity_report: BaseActivityReport = None
    module_title: str = None
    units: float = None
    calculator: calculators.BaseCalculator | calculators.LandModuleCalculator = None
    result: dict = None
    emissions_set: list[math_utils.YearlyGasActivityEmissionSet] = None

    start_year_of_activities: int = None
    last_year_of_accounting: int = None
    implementation_years: int = None
    capitalization_years: int = None
    duration: int = None

    workbook: pxl.Workbook = None
    results_worksheet: Worksheet = None
    metadata_worksheet: Worksheet = None
    additional_indicators_worksheet: Worksheet = None

    def __post_init__(self):
        self.result = self.calculator.calculate()

        self.emissions_set = []

        if self.module.is_with():
            self.emissions_set += self.calculator.results_w.yearly_emissions_by_sector_by_gas + self.calculator.results_start_w.yearly_emissions_by_sector_by_gas

        if self.module.is_without():
            self.emissions_set += self.calculator.results_wo.yearly_emissions_by_sector_by_gas + self.calculator.results_start_wo.yearly_emissions_by_sector_by_gas

        if self.activity_report is not None:
            self.workbook = self.activity_report.workbook
            self.results_worksheet = self.activity_report.results_worksheet
            self.metadata_worksheet = self.activity_report.metadata_worksheet
            self.additional_indicators_worksheet = self.activity_report.additional_indicators_worksheet

        self.start_year_of_activities = self.module.activity.project.start_year_of_activities
        self.last_year_of_accounting = self.module.activity.project.last_year_of_accounting
        self.implementation_years = self.module.activity.implementation_years
        self.capitalization_years = self.module.activity.capitalization_years
        self.duration = self.module.activity.implementation_years + self.module.activity.capitalization_years

    def get_result(self):
        return NotImplementedError

    def extract_emissions(self, data, activity_type, gas_type):
        """
        Extracts emissions values from the provided data based on the specified activity type and gas type.

        Args:
            data (list): A list of data entries, where each entry is expected to have 'activity', 'gas_type', and 'emissions' attributes.
            activity_type (str): The type of activity to filter the data entries.
            gas_type (str): The type of gas to filter the data entries.

        Returns:
            list: A list of emission values if a matching entry is found.
            numpy.ndarray: An array of zeros with a length equal to the sum of implementation years and capitalization years if no matching entry is found.
        """
        for entry in data:
            if entry.activity == activity_type and entry.gas_type == gas_type:
                return [e.value for e in entry.emissions]
        return np.zeros(self.module.activity.implementation_years + self.module.activity.capitalization_years)


@dataclass
class LandModuleReport(BaseModuleReport):

    biomass_co2: list[float] = None
    soil_co2: list[float] = None
    soil_n2o: list[float] = None
    fire_n2o: list[float] = None
    fire_ch4: list[float] = None
    emissions_set: list[math_utils.YearlyGasActivityEmissionSet] = None

    units_breakdown: list[float] = None

    units_breakdown_w: list[float] = None
    units_breakdown_wo: list[float] = None

    def __post_init__(self):
        super().__post_init__()

        hectares_length = self.module.activity.implementation_years + self.module.activity.capitalization_years

        break_start_w = getattr(self.calculator.math_start_w, "hectares_total", np.zeros(hectares_length))
        break_start_wo = getattr(self.calculator.math_start_wo, "hectares_total", np.zeros(hectares_length))
        break_w = getattr(self.calculator.math_w, "hectares_total", np.zeros(hectares_length))
        break_wo = getattr(self.calculator.math_wo, "hectares_total", np.zeros(hectares_length))

        log.debug(f"Calculating units breakdown for {self.module.module_type.name}: with")
        log.debug(f"Units breakdown start_w: {break_start_w}")
        log.debug(f"Units breakdown w: {break_w}")
        self.units_breakdown_w = [x + y for x, y in zip(break_start_w, break_w)]

        log.debug(f"Calculating units breakdown for {self.module.module_type.name}: without")
        log.debug(f"Units breakdown start_wo: {break_start_wo}")
        log.debug(f"Units breakdown wo: {break_wo}")
        self.units_breakdown_wo = [x + y for x, y in zip(break_start_wo, break_wo)]

    def get_result(self):
        self.workbook = self.activity_report.workbook
        self.results_worksheet = self.activity_report.results_worksheet
        self.metadata_worksheet = self.activity_report.metadata_worksheet
        self.additional_indicators_worksheet = self.activity_report.additional_indicators_worksheet

        self.module_title = self.module.module_type.name
        self.units = self.module.area

        self.biomass_co2 = self.extract_emissions(self.emissions_set, math_utils.ActivityTypes.BIOMASS, math_utils.GasTypes.CO2)
        self.soil_co2 = self.extract_emissions(self.emissions_set, math_utils.ActivityTypes.SOIL_CO2_CHANGE, math_utils.GasTypes.CO2)
        self.soil_n2o = self.extract_emissions(self.emissions_set, math_utils.ActivityTypes.SOM, math_utils.GasTypes.N2O)
        self.fire_n2o = self.extract_emissions(self.emissions_set, math_utils.ActivityTypes.RESIDUE_BURNING, math_utils.GasTypes.N2O.value)
        self.fire_ch4 = self.extract_emissions(self.emissions_set, math_utils.ActivityTypes.RESIDUE_BURNING, math_utils.GasTypes.CH4)

    def build_report(self):
        log.debug(f"Building base report for {self.module.module_type.name}")
        self.get_result()

        last_results_row = self.results_worksheet.max_row + 1
        last_metadata_row = self.metadata_worksheet.max_row + 1
        last_additional_indicators_row = self.additional_indicators_worksheet.max_row + 1

        light_blue = PatternFill(start_color=Colors.LIGHT_BLUE.value, end_color=Colors.LIGHT_BLUE.value, fill_type="solid")
        light_orange = PatternFill(start_color=Colors.LIGHT_ORANGE.value, end_color=Colors.LIGHT_ORANGE.value, fill_type="solid")

        # Write module name in results sheet
        self.results_worksheet.cell(row=last_results_row, column=1, value=str(self.module_title))
        self.results_worksheet.cell(row=last_results_row, column=1).fill = light_blue

        # Write emissions information
        self.results_worksheet.cell(row=last_results_row + 1, column=1, value="CO2 in biomass")
        self.results_worksheet.cell(row=last_results_row + 2, column=1, value="CO2 in soils")
        self.results_worksheet.cell(row=last_results_row + 3, column=1, value="N2O in soils")
        self.results_worksheet.cell(row=last_results_row + 4, column=1, value="N2O from fires")
        self.results_worksheet.cell(row=last_results_row + 5, column=1, value="CH4 from fires")

        # Write emissions yearly values
        for i, year in enumerate(range(self.start_year_of_activities, self.last_year_of_accounting)):
            self.results_worksheet.cell(row=last_results_row + 1, column=i + 2, value=self.biomass_co2[i])
            self.results_worksheet.cell(row=last_results_row + 2, column=i + 2, value=self.soil_co2[i])
            self.results_worksheet.cell(row=last_results_row + 3, column=i + 2, value=self.soil_n2o[i])
            self.results_worksheet.cell(row=last_results_row + 4, column=i + 2, value=self.fire_n2o[i])
            self.results_worksheet.cell(row=last_results_row + 5, column=i + 2, value=self.fire_ch4[i])

        log.debug(f"Base report for {self.module.module_type.name} built.")
        return self.workbook


@dataclass
class PerennialCroplandReport(LandModuleReport):

    module: api_models.PerennialCropland

    def __post_init__(self):
        self.calculator = calculators.PerennialCroplandCalculator(self.module)
        return super().__post_init__()

    def get_result(self):
        super().get_result()
        log.debug(f"Building report for {self.module.module_type.name}")

        last_results_row = self.results_worksheet.max_row + 1
        last_metadata_row = self.metadata_worksheet.max_row + 1
        last_additional_indicators_row = self.additional_indicators_worksheet.max_row + 1

        light_blue = PatternFill(start_color=Colors.LIGHT_BLUE.value, end_color=Colors.LIGHT_BLUE.value, fill_type="solid")

        self.metadata_worksheet.cell(row=last_metadata_row, column=1, value="Perennial Cropland")
        self.metadata_worksheet.cell(row=last_metadata_row, column=1, value="Perennial Cropland").fill = light_blue

        self.metadata_worksheet.cell(row=last_metadata_row + 1, column=1, value="Hectares")
        self.metadata_worksheet.cell(row=last_metadata_row + 2, column=1, value="Main season crop")
        self.metadata_worksheet.cell(row=last_metadata_row + 3, column=1, value="Tillage management type")
        self.metadata_worksheet.cell(row=last_metadata_row + 4, column=1, value="Organic input type")
        self.metadata_worksheet.cell(row=last_metadata_row + 5, column=1, value="Yield")

        if self.module.is_start():
            self.metadata_worksheet.cell(row=last_metadata_row + 1, column=2, value=self.units)
            self.metadata_worksheet.cell(row=last_metadata_row + 2, column=2, value=self.module.land_use_type_start.name)
            self.metadata_worksheet.cell(row=last_metadata_row + 3, column=2, value=self.module.tillage_management_type_start.name)
            self.metadata_worksheet.cell(row=last_metadata_row + 4, column=2, value=self.module.organic_input_type_start.name)
            self.metadata_worksheet.cell(row=last_metadata_row + 5, column=2, value=self.module.crop_yield_t2_start if self.module.crop_yield_t2_start is not None else "Default")

        if self.module.is_with():
            self.metadata_worksheet.cell(row=last_metadata_row + 1, column=3, value=self.units)
            self.metadata_worksheet.cell(row=last_metadata_row + 2, column=3, value=self.module.land_use_type_w.name)
            self.metadata_worksheet.cell(row=last_metadata_row + 3, column=3, value=self.module.tillage_management_type_w.name)
            self.metadata_worksheet.cell(row=last_metadata_row + 4, column=3, value=self.module.organic_input_type_w.name)
            self.metadata_worksheet.cell(row=last_metadata_row + 5, column=3, value=self.module.crop_yield_t2_w if self.module.crop_yield_t2_w is not None else "Default")

        if self.module.is_without():
            self.metadata_worksheet.cell(row=last_metadata_row + 1, column=4, value=self.units)
            self.metadata_worksheet.cell(row=last_metadata_row + 2, column=4, value=self.module.land_use_type_wo.name)
            self.metadata_worksheet.cell(row=last_metadata_row + 3, column=4, value=self.module.tillage_management_type_wo.name)
            self.metadata_worksheet.cell(row=last_metadata_row + 4, column=4, value=self.module.organic_input_type_wo.name)
            self.metadata_worksheet.cell(row=last_metadata_row + 5, column=4, value=self.module.crop_yield_t2_wo if self.module.crop_yield_t2_wo is not None else "Default")

        with_project_row = None
        for row in self.additional_indicators_worksheet.iter_rows():
            if row[0].value == "With project":
                with_project_row = row[0].row

        self.additional_indicators_worksheet.insert_rows(with_project_row + 1)
        with_project_row = with_project_row + 1

        self.additional_indicators_worksheet.cell(with_project_row, 1, "Perennial Cropland (ha)")
        for i, year in enumerate(range(self.start_year_of_activities, self.last_year_of_accounting)):
            self.additional_indicators_worksheet.cell(with_project_row, i + 2, self.units_breakdown_w[i])

        without_project_row = None
        for row in self.additional_indicators_worksheet.iter_rows():
            if row[0].value == "Without project":
                without_project_row = row[0].row

        self.additional_indicators_worksheet.insert_rows(without_project_row + 1)
        without_project_row = without_project_row + 1

        self.additional_indicators_worksheet.cell(without_project_row, 1, "Perennial Cropland (ha)")
        for i, year in enumerate(range(self.start_year_of_activities, self.last_year_of_accounting)):
            self.additional_indicators_worksheet.cell(without_project_row, i + 2, self.units_breakdown_wo[i])

        log.debug(f"Report for {self.module_title} built.")
        return self.workbook


@dataclass
class AnnualCroplandReport(LandModuleReport):

    module: api_models.AnnualCropland
    activity_report: BaseActivityReport = None

    def __post_init__(self):
        self.calculator = calculators.AnnualCroplandCalculator(self.module)
        return super().__post_init__()

    def get_result(self):
        """
        Additional indicators sheet: hectars indicator is self.hectares_total. Livestock indicator under self.livestock_heads_yearly_breakdown. Catch (fish) under self.tonnes_catch_yearly_breakdown
        """
        super().get_result()
        log.debug(f"Building report for {self.module.module_type.name}")

        if self.activity_report is None:
            wb = xlsxwriter.Workbook("annual_cropland_results.xlsx")
            wb.add_worksheet("Results")
            wb.add_worksheet("Metadata")
            wb.add_worksheet("Additional Indicators")
            wb.close()

            self.workbook = pxl.load_workbook("annual_cropland_results.xlsx")
            self.results_worksheet = self.workbook["Results"]
            self.metadata_worksheet = self.workbook["Metadata"]
            self.additional_indicators_worksheet = self.workbook["Additional Indicators"]

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

        last_results_row = self.results_worksheet.max_row + 1
        last_metadata_row = self.metadata_worksheet.max_row + 1
        last_additional_indicators_row = self.additional_indicators_worksheet.max_row + 1

        self.metadata_worksheet.cell(row=last_metadata_row, column=1, value="Annual Cropland")
        self.metadata_worksheet.cell(row=last_metadata_row, column=1, value="Annual Cropland").fill = PatternFill(start_color=Colors.LIGHT_BLUE.value, end_color=Colors.LIGHT_BLUE.value, fill_type="solid")
        self.metadata_worksheet.cell(row=last_metadata_row + 1, column=1, value="Hectares")
        self.metadata_worksheet.cell(row=last_metadata_row + 2, column=1, value="Main season crop")
        self.metadata_worksheet.cell(row=last_metadata_row + 3, column=1, value="Tillage management type")
        self.metadata_worksheet.cell(row=last_metadata_row + 4, column=1, value="Organic input type")
        self.metadata_worksheet.cell(row=last_metadata_row + 5, column=1, value="Residue management type")
        self.metadata_worksheet.cell(row=last_metadata_row + 6, column=1, value="Yield")
        self.metadata_worksheet.cell(row=last_metadata_row + 7, column=1, value="Minor season crop")
        self.metadata_worksheet.cell(row=last_metadata_row + 8, column=1, value="Minor residue management type")
        self.metadata_worksheet.cell(row=last_metadata_row + 9, column=1, value="Minor yield")

        if self.module.is_start():
            self.metadata_worksheet.cell(row=last_metadata_row + 1, column=2, value=self.units)
            self.metadata_worksheet.cell(row=last_metadata_row + 2, column=2, value=main_season_crop_start)
            self.metadata_worksheet.cell(row=last_metadata_row + 3, column=2, value=tillage_management_type_start)
            self.metadata_worksheet.cell(row=last_metadata_row + 4, column=2, value=organic_input_type_start)
            self.metadata_worksheet.cell(row=last_metadata_row + 5, column=2, value=residue_management_type_start)
            self.metadata_worksheet.cell(row=last_metadata_row + 6, column=2, value=yield_start)
            self.metadata_worksheet.cell(row=last_metadata_row + 7, column=2, value=minor_season_crop_start)
            self.metadata_worksheet.cell(row=last_metadata_row + 8, column=2, value=minor_residue_management_type_start)
            self.metadata_worksheet.cell(row=last_metadata_row + 9, column=2, value=minor_yield_start)

        if self.module.is_with():
            self.metadata_worksheet.cell(row=last_metadata_row + 1, column=3, value=self.units)
            self.metadata_worksheet.cell(row=last_metadata_row + 2, column=3, value=main_season_crop_w)
            self.metadata_worksheet.cell(row=last_metadata_row + 3, column=3, value=tillage_management_type_w)
            self.metadata_worksheet.cell(row=last_metadata_row + 4, column=3, value=organic_input_type_w)
            self.metadata_worksheet.cell(row=last_metadata_row + 5, column=3, value=residue_management_type_w)
            self.metadata_worksheet.cell(row=last_metadata_row + 6, column=3, value=yield_w)
            self.metadata_worksheet.cell(row=last_metadata_row + 7, column=3, value=minor_season_crop_w)
            self.metadata_worksheet.cell(row=last_metadata_row + 8, column=3, value=minor_residue_management_type_w)
            self.metadata_worksheet.cell(row=last_metadata_row + 9, column=3, value=minor_yield_w)

        if self.module.is_without():
            self.metadata_worksheet.cell(row=last_metadata_row + 1, column=4, value=self.units)
            self.metadata_worksheet.cell(row=last_metadata_row + 2, column=4, value=main_season_crop_wo)
            self.metadata_worksheet.cell(row=last_metadata_row + 3, column=4, value=tillage_management_type_wo)
            self.metadata_worksheet.cell(row=last_metadata_row + 4, column=4, value=organic_input_type_wo)
            self.metadata_worksheet.cell(row=last_metadata_row + 5, column=4, value=residue_management_type_wo)
            self.metadata_worksheet.cell(row=last_metadata_row + 6, column=4, value=yield_wo)
            self.metadata_worksheet.cell(row=last_metadata_row + 7, column=4, value=minor_season_crop_wo)
            self.metadata_worksheet.cell(row=last_metadata_row + 8, column=4, value=minor_residue_management_type_wo)
            self.metadata_worksheet.cell(row=last_metadata_row + 9, column=4, value=minor_yield_wo)

        with_project_row = None
        for row in self.additional_indicators_worksheet.iter_rows():
            if row[0].value == "With project":
                with_project_row = row[0].row

        self.additional_indicators_worksheet.insert_rows(with_project_row + 1)
        with_project_row = with_project_row + 1

        self.additional_indicators_worksheet.cell(with_project_row, 1, "Annual Cropland (ha)")
        for i, year in enumerate(range(self.start_year_of_activities, self.last_year_of_accounting)):
            self.additional_indicators_worksheet.cell(with_project_row, i + 2, self.units_breakdown_w[i])

        without_project_row = None
        for row in self.additional_indicators_worksheet.iter_rows():
            if row[0].value == "Without project":
                without_project_row = row[0].row

        self.additional_indicators_worksheet.insert_rows(without_project_row + 1)
        without_project_row = without_project_row + 1

        self.additional_indicators_worksheet.cell(without_project_row, 1, "Annual Cropland (ha)")
        for i, year in enumerate(range(self.start_year_of_activities, self.last_year_of_accounting)):
            self.additional_indicators_worksheet.cell(without_project_row, i + 2, self.units_breakdown_wo[i])

        log.debug(f"Report for {self.module_title} built.")
        return self.workbook
