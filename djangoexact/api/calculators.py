import copy
import json
import logging as log
import math
import statistics
import sys
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import SimpleNamespace
from django.apps import apps

from django.db.models import Q
import django.db.models as models
from ipcc import models as ipcc
from math_model.no_time_dependency_final.annuals import AnnualCropland as MathAnnualCropland
from math_model.no_time_dependency_final.coastal_wetlands import (
    CoastalWetland as MathCoastalWetland,
)
from math_model.no_time_dependency_final.defo import Deforestation as MathDeforestation
from math_model.no_time_dependency_final.fisheries_and_aquaculture import (
    CoastalAquaculture as MathAquaculture,
)
from math_model.no_time_dependency_final.fisheries_and_aquaculture import (
    Fishery as MathFishery,
)
from math_model.no_time_dependency_final.flooded_rice import (
    FloodedRice as MathFloodedRice,
)
from math_model.no_time_dependency_final.forest_management import (
    ForestManagement as MathForestManagement,
)
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes
from math_model.no_time_dependency_final.ghg_emissions_classes import (
    Result as MathResult,
)
from math_model.no_time_dependency_final.grassland_management import (
    GrasslandManagement as MathGrassland,
)
from math_model.no_time_dependency_final.inlands import AnnexedModule as MathOrganicSoil
from math_model.no_time_dependency_final.inlands import (
    PeatExtraction as MathPeatExtraction,
)
from math_model.no_time_dependency_final.inputs import (
    ElectricityConsumption,
    SolidAndLiquidFuelsConsumption,
    NewIrrigation,
    OperationPhaseIrrigation,
)
from math_model.no_time_dependency_final.inputs import Inputs as MathInputs
from math_model.no_time_dependency_final.inputs import Roads as MathRoads
from math_model.no_time_dependency_final.livestock import Livestock as MathLivestock
from math_model.no_time_dependency_final.oluc import (
    OtherLandUseChanges as MathOtherLandUseChanges,
)
from math_model.no_time_dependency_final.perennial_cropping import (
    PerennialCropland as MathPerennialCropland,
)
from math_model.no_time_dependency_final.waterbodies import (
    CoastalWaterbodies as MathWaterbodies,
)

from math_model.no_time_dependency_final.not_cultivated_land import (
    NotCultivatedLand as MathNotCultivatedLand,
)

from api.utilities import getattr_or_default

from . import utilities as utils
from .models import (
    Activity,
    Submodule,
    AnnualCroplandParameter,
    AnnualCropland,
    Aquaculture,
    AquacultureParameter,
    BiomassModule,
    Building,
    Climate,
    CoastalWetland,
    CoastalWetlandParameter,
    Country,
    OtherLand,
    Electricity,
    Energy,
    FloodedRice,
    ForestDisturbance,
    ForestManagement,
    Fuel,
    Grassland,
    GrasslandParameter,
    Input,
    InputEntry,
    InputType,
    SalinityType,
    Irrigation,
    IrrigationParameter,
    IrrigationPhase,
    IrrigationSystem,
    LandModule,
    LandModuleNoScenarios,
    LandUseChange,
    LandUseType,
    LargeFishery,
    LargeFisheryParameter,
    Livestock,
    LivestockParameter,
    Module,
    Moisture,
    OrganicInputType,
    OrganicSoil,
    PerennialCropland,
    Project,
    Region,
    Road,
    Settlement,
    SetAside,
    SmallFishery,
    SmallFisheryParameter,
    SoilType,
    StatusType,
    Waterbody,
    ModuleType,
    MinorSeasonFloodedRice,
    SingleBiomassModule,
    ChangeRate,
    AboveBelowGroundBiomassModule,
)
from api.utilities import DefaultValue

CALCULATE_SOC_SOM_START_W = False
CALCULATE_SOC_SOM_START_WO = False
CALCULATE_SOC_SOM_W = True
CALCULATE_SOC_SOM_WO = True

PLOT_GRAPHS = False


def is_luc_remaining_same(module: LandModule) -> bool:
    """
    Checks if the land use change for a given module remains the same.

    Args:
        module (LandModule): The land module to check.

    Returns:
        bool: True if the land use change remains the same, False otherwise.
    """
    log.debug("Is LUC remaining the same")
    luc: LandUseChange = getattr(module, "land_use_change", None)
    return not luc or (luc and luc.module_type_start.class_name == module.__class__.__name__ and luc.module_type_w.class_name == module.__class__.__name__)


def is_business_as_usual(module: LandModule) -> bool:
    """
    Checks if the given module represents a business-as-usual scenario.

    Args:
        module (LandModule): The land module to check.

    Returns:
        bool: True if the module represents a business-as-usual scenario, False otherwise.
    """
    log.debug("Is business as usual")
    luc: LandUseChange = getattr(module, "land_use_change", None)
    return not luc or (luc and luc.module_type_start.class_name == module.__class__.__name__ and luc.module_type_wo.class_name == module.__class__.__name__)


def is_without(module: LandModule) -> bool:
    """
    Checks if the given module is without a land use change or if the module type without land use change matches the module's class name.

    Args:
        module (LandModule): The module to check.

    Returns:
        bool: True if the module is associated with the land use change or if the provided module types the LandUseChange "WITHOUT" scenario. False otherwise.
    """
    log.debug("Is without")
    luc: LandUseChange = getattr(module, "land_use_change", None)
    return not luc or (luc.module_type_wo.class_name == module.__class__.__name__)


def is_with(module: LandModule) -> bool:
    """
    Checks if the given module is associated with a specific land use change.

    Args:
        module (LandModule): The module to check.

    Returns:
        bool: True if the module is associated with the land use change or if the provided module types the LandUseChange "WITH" scenario. False otherwise.
    """
    log.debug("Is with")
    luc: LandUseChange = getattr(module, "land_use_change", None)
    return not luc or (luc.module_type_w.class_name == module.__class__.__name__)


def get_fi_data(module: LandModule, climate: Climate, moisture: Moisture, scenario: utils.ScenarioTypes):
    """
    Retrieve the FI data based on the given parameters.

    Args:
        module (LandModule): The land module.
        climate (Climate): The climate.
        moisture (Moisture): The moisture.
        scenario (utils.ScenarioTypes): The scenario type.

    Returns:
        FIData or SimpleNamespace: The FI data object if found,
        or a SimpleNamespace object with a value of 1 if no match is found.
    """
    key = f"organic_input_type"
    attr = getattr(module, f"organic_input_type_{scenario.value}", None)
    if not attr:
        key = f"grassland_management_type"
        attr = getattr(module, f"grassland_management_type_{scenario.value}", None)

    try:
        if attr:
            _filter = {key: attr}
            return ipcc.FIData.objects.get(climate=climate, moisture=moisture, **_filter)
    except ipcc.FIData.DoesNotExist:
        pass

    return SimpleNamespace(value=1)


def get_fmg_data(module: LandModule, climate: Climate, moisture: Moisture, scenario: utils.ScenarioTypes):
    """
    Retrieve FMG data based on the provided parameters.

    Args:
        module (LandModule): The land module.
        climate (Climate): The climate.
        moisture (Moisture): The moisture.
        scenario (utils.ScenarioTypes): The scenario type.

    Returns:
        FMGData: The FMG data object matching the provided parameters,
        or a SimpleNamespace object with a value of 1 if no match is found.
    """
    key = f"tillage_management_type"
    attr = getattr(module, f"tillage_management_type_{scenario.value}", None)
    if not attr:
        key = f"grassland_management_type"
        attr = getattr(module, f"grassland_management_type_{scenario.value}", None)

    try:
        if attr:
            _filter = {key: attr}
            return ipcc.FMGData.objects.get(climate=climate, moisture=moisture, **_filter)
    except ipcc.FMGData.DoesNotExist:
        pass

    return SimpleNamespace(value=1)


def get_flu_data(module: LandModule, climate: Climate, moisture: Moisture, scenario: utils.ScenarioTypes):
    """
    Retrieve the FluData object based on the given parameters.

    Args:
        module (LandModule): The LandModule object.
        climate (Climate): The Climate object.
        moisture (Moisture): The Moisture object.
        scenario (utils.ScenarioTypes): The scenario type.

    Returns:
        FluData: The FluData object matching the given parameters,
        or a SimpleNamespace object with a value of 1 if no match is found.
    """
    key = f"land_use_type"
    attr = getattr(module, f"land_use_type_{scenario.value}", None)
    if not attr:
        key = f"grassland_management_type"
        attr = getattr(module, f"grassland_management_type_{scenario.value}", None)

    try:
        if attr:
            _filter = {key: attr}
            return ipcc.FLUData.objects.get(climate=climate, moisture=moisture, **_filter)
    except ipcc.FLUData.DoesNotExist:
        log.debug(f"FLUData for {attr} in {climate.name} climate and {moisture.name} moisture does not exist")
        pass

    return SimpleNamespace(value=1)


def get_luc_modules(luc: LandUseChange) -> tuple[LandModule]:
    """
    Retrieves the land use change modules associated with each scenario of a given LandUseChange object.

    Args:
        luc (LandUseChange): The LandUseChange object.

    Returns:
        tuple[LandModule]: A tuple containing the land use change modules for each scenario.

    Raises:
        Exception: If at least one module is missing.
    """
    modules = (
        getattr(luc.activity, luc.module_type_start.class_name.lower(), None).first(),
        getattr(luc.activity, luc.module_type_w.class_name.lower(), None).first(),
        getattr(luc.activity, luc.module_type_wo.class_name.lower(), None).first(),
    )

    if not all(modules):
        raise Exception("At least one module is missing")

    return modules


def get_grassland_soc(luc: LandUseChange) -> ipcc.GrasslandStockExchangeFactor | None:
    """
    Get the soil organic carbon (SOC) for grassland
    if there's a land use change and the start module is a grassland module.

    Args:
        luc (LandUseChange): The land use change object.

    Returns:
        grassland_soc (GrasslandStockExchangeFactor): The grassland SOC object.
    """
    # NOTE: This approach is wrong at the moment. Instead of having tabulated set values
    # for SOC we should have tabulated values for multipliers to the SOC. What
    # was done now is with multipliers, only just with one SOC reference value.
    grassland_soc = None

    if not luc or not luc.activity:
        return grassland_soc

    module_start: Grassland = getattr(luc.activity, luc.module_type_start.class_name.lower(), None).first()
    if luc.module_type_start.name == "Grassland" and module_start:

        if module_start.status.name != "READY":
            raise Exception("Cannot retrieve Grassland SOC as the starting Grassland module is not ready to perform the calculation")

        try:
            grassland_soc = ipcc.GrasslandSOC.objects.get(
                grassland_management_type=module_start.grassland_management_type_start,
            )
        except ipcc.GrasslandSOC.DoesNotExist:
            raise Exception(f"GrasslandStockExchangeFactor for {module_start.grassland_management_type_start.name} in {luc.activity.project.climate.name} climate does not exist")

    return grassland_soc


class Result:
    """
    Base class for all results.
    """

    def __init__(self, w: MathResult, wo: MathResult, balance: MathResult = None) -> None:
        self.total_w = w
        self.total_wo = wo
        self.balance = copy.deepcopy(w) - copy.deepcopy(wo) if balance is None else copy.deepcopy(balance)

    def __str__(self):
        return f"total_w: {self.total_w}, total_wo: {self.total_wo}, balance: {self.balance}"

    def add(self, result):
        if not isinstance(result, self.__class__):
            raise TypeError(f"Cannot add {type(result)} to {type(self)}. Must use a {type(self)} instance.")

        self.total_w += result.total_w
        self.total_wo += result.total_wo
        self.balance = self.total_w - self.total_wo

        return self

    def __add__(self, other):
        return self.add(other)

    def breakdown(self, by=BreakdownTypes.TOTAL):
        log.debug("START Result.breakdown")
        log.debug(f"Breakdown by: {by}")

        breakdown = (
            self.total_w.breakdown(by=by),
            self.total_wo.breakdown(by=by),
            self.balance.breakdown(by=by),
        )

        log.debug("END Result.breakdown")
        log.debug("")
        return breakdown


@dataclass
class DefaultData:
    """ """

    start: dict
    w: dict
    wo: dict


class CalculatorFactory:
    def __get_calculator(self, input):
        """
        Finds the calculator class for a given module.

        Args:
            input: The input module for which the calculator class needs to be found.

        Returns:
            CalculatorClass: The calculator class corresponding to the input module.

        Raises:
            Exception: If no calculator class is found for the input module.
        """
        CalculatorClass = getattr(sys.modules[__name__], f"{input.__class__.__name__}Calculator", None)
        if CalculatorClass is None:
            raise Exception(f"No calculator found for {input.__class__.__name__}")
        return CalculatorClass

    def calculate_result(self, input, aggregate_by=BreakdownTypes.TOTAL):
        """
        Calculates the results for a given module.

        Args:
            input: The input data for the calculation.
            aggregate_by (optional): The breakdown type to aggregate the results by. Defaults to BreakdownTypes.TOTAL.

        Returns:
            The calculated result, broken down by the specified breakdown type.

        Raises:
            Exception: If an error occurs during the calculation.
        """
        try:
            calculator: BaseCalculator = self.__get_calculator(input)(input)
            result: tuple[MathResult] = calculator.calculate()
            return (
                Result(*result).breakdown(by=BreakdownTypes.TOTAL),
                Result(*result).breakdown(by=BreakdownTypes.ACTIVITY),
                Result(*result).breakdown(by=BreakdownTypes.GAS),
                Result(*result).breakdown(by=BreakdownTypes.ACTIVITY_GAS),
            )

        except Exception as e:
            raise Exception(f"Error in {input.__class__.__name__}: {e}")

    def get_defaults(self, input):
        """
        Gets the default values for a given module.

        Args:
            input: The input module for which to retrieve the default values.

        Returns:
            A dictionary containing the default values for the given module.

        Raises:
            Exception: If an error occurs while retrieving the default values.
        """
        try:
            calculator: BaseCalculator = self.__get_calculator(input)(input)
            return calculator.defaults()

        except Exception as e:
            raise Exception(f"Error in {input.__class__.__name__}: {e}")


class BaseCalculator(ABC):
    """
    Abstract base class for all calculators.
    """

    class Meta:
        model = None

    def __init__(self, input) -> None:
        super().__init__()

        self.Meta.model = input.__class__
        self.data: Module = input  # TODO: Remove

        self.inputs_start_w = None
        self.inputs_start_wo = None
        self.inputs_start = None
        self.inputs_w = None
        self.inputs_wo = None

        self.math_start_w = None
        self.math_start_wo = None
        self.math_start = None
        self.math_w = None
        self.math_wo = None

        self.results_start_w = None
        self.results_start_wo = None
        self.results_start = None
        self.results_w = None
        self.results_wo = None

        self.project: Project = getattr(self.data, "parent", self.data).activity.project
        self.activity: Activity = getattr(self.data, "parent", self.data).activity
        self.module: Module | Submodule = self.data
        self.area = getattr(self.module, "parent", getattr(self.module, "area", None))

        self.climate: Climate = self.activity.climate_t2 or self.project.climate
        self.moisture: Moisture = self.activity.moisture_t2 or self.project.moisture
        self.soil_type: SoilType = self.activity.soil_type_t2 or self.project.soil_type
        self.country: Country = self.project.country
        self.region: Region = self.project.country.region
        self.change_rate: ChangeRate = self.activity.change_rate

    @abstractmethod
    def calculate(self, input: Module, aggregate_by=BreakdownTypes.TOTAL) -> Result:
        """
        Calculate emissions for a single module.
        """

        if input.__class__ == LandUseChange:
            luc: LandUseChange = input
            modules = luc.get_modules()

            if not all(modules):
                raise Exception("At least one module is missing")

            if any(module.status != StatusType.objects.get(name="READY") for module in modules):
                raise Exception("At least one module is not ready to perform the calculation")

    @abstractmethod
    def get_defaults(self, calculate=False) -> dict:
        """
        Get the default values for a given module.
        """
        self.data: Module

        if self.data.is_ready() and calculate:
            self.calculate()


class LandModuleCalculator(BaseCalculator):
    def __init__(self, module: LandModule) -> None:
        super().__init__(module)

        self.soc: ipcc.SoilOrganicCarbon = ipcc.SoilOrganicCarbon()
        self.som: ipcc.NitrousEmissionFactor = ipcc.NitrousEmissionFactor(value=0)

        self.fi_start: ipcc.FIData = ipcc.FIData(value=0)
        self.fmg_start: ipcc.FMGData = ipcc.FMGData(value=0)
        self.flu_start: ipcc.FLUData = ipcc.FLUData(value=0)
        self.fi_w: ipcc.FIData = ipcc.FIData(value=0)
        self.fmg_w: ipcc.FMGData = ipcc.FMGData(value=0)
        self.flu_w: ipcc.FLUData = ipcc.FLUData(value=0)
        self.fi_wo: ipcc.FIData = ipcc.FIData(value=0)
        self.fmg_wo: ipcc.FMGData = ipcc.FMGData(value=0)
        self.flu_wo: ipcc.FLUData = ipcc.FLUData(value=0)

        self.module: LandModule | SingleBiomassModule = module
        self.luc: LandUseChange = self.module.land_use_change
        self.activity: Activity = getattr(module, "parent", module).activity
        self.project: Project = self.activity.project
        self.area = self.luc.area if self.luc else getattr(module, "parent", module).area

        self.module_start = self.module_w = self.module_wo = self.module

        self.module_start: LandModule | SingleBiomassModule
        self.module_w: LandModule | SingleBiomassModule
        self.module_wo: LandModule | SingleBiomassModule

        self.biomass_ef_start: ipcc.ForestTotalBiomass = ipcc.ForestTotalBiomass(value=0)

        self.biomass_ef_start_w: ipcc.TotalBiomassAfterDefo = ipcc.TotalBiomassAfterDefo(value=0)
        self.biomass_ef_start_wo: ipcc.TotalBiomassAfterDefo = ipcc.TotalBiomassAfterDefo(value=0)
        self.biomass_ef_w: ipcc.TotalBiomassAfterDefo = ipcc.TotalBiomassAfterDefo(value=0)
        self.biomass_ef_wo: ipcc.TotalBiomassAfterDefo = ipcc.TotalBiomassAfterDefo(value=0)

        self.calculate_biomass_start_w = False
        self.calculate_biomass_start_wo = False
        self.calculate_biomass_w = not (self.module.is_start() and self.module.is_with())
        self.calculate_biomass_wo = not (self.module.is_start() and self.module.is_without())

        self.soc_start = self.soc_w = self.soc_wo = ipcc.SoilOrganicCarbon()

        if self.luc:
            self.module_start, self.module_w, self.module_wo = self.luc.get_modules()

    def calculate(self, module: Module, aggregate_by=BreakdownTypes.TOTAL) -> Result:
        return super().calculate(module, aggregate_by)

    def get_defaults(self, calculate=False) -> dict:

        moisture_flt = {"moisture": self.moisture}

        try:
            self.soc = ipcc.SoilOrganicCarbon.objects.get(climate=self.climate, moisture=self.moisture, soil_type=self.soil_type)
            self.soc_start = self.soc_w = self.soc_wo = self.soc
        except ipcc.SoilOrganicCarbon.DoesNotExist:
            missing_scenarios = []

            # NOTE: Hierarchical order of precedence for SOC: Project < Activity < Module
            if self.project.soc_ref_t2 is not None:
                self.soc_start = self.soc_w = self.soc_wo = SimpleNamespace(value=self.project.soc_ref_t2)

            if self.activity.soc_t2 is not None:
                self.soc_start = self.soc_w = self.soc_wo = SimpleNamespace(value=self.activity.soc_t2)

            if self.module.soc_t2_start is not None:
                self.soc_start = SimpleNamespace(value=self.module.soc_t2_start)

            if self.module.soc_t2_w is not None:
                self.soc_w = SimpleNamespace(value=self.module.soc_t2_w)

            if self.module.soc_t2_wo is not None:
                self.soc_wo = SimpleNamespace(value=self.module.soc_t2_wo)

            if self.soc.value is None and not all(x.value is not None for x in [self.soc_start, self.soc_w, self.soc_wo]):
                if self.module.is_start() and self.soc_start.value is None:
                    missing_scenarios.append("Start")
                if self.module.is_with() and self.soc_w.value is None:
                    missing_scenarios.append("With")
                if self.module.is_without() and self.soc_wo.value is None:
                    missing_scenarios.append("Without")

                if missing_scenarios:
                    raise Exception(f"SOC for {self.climate.name} climate, {self.moisture.name} moisture, and {self.soil_type.name} soil type is missing. Please insert T2 values for the following scenarios: {', '.join(missing_scenarios)}")

        self.som = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {self.climate.name} moisture does not exist")

        self.fi_start = get_fi_data(self.module_start, self.climate, self.moisture, utils.ScenarioTypes.START)
        self.fmg_start = get_fmg_data(self.module_start, self.climate, self.moisture, utils.ScenarioTypes.START)
        self.flu_start = get_flu_data(self.module_start, self.climate, self.moisture, utils.ScenarioTypes.START)
        self.fi_w = get_fi_data(self.module_w, self.climate, self.moisture, utils.ScenarioTypes.WITH)
        self.fmg_w = get_fmg_data(self.module_w, self.climate, self.moisture, utils.ScenarioTypes.WITH)
        self.flu_w = get_flu_data(self.module_w, self.climate, self.moisture, utils.ScenarioTypes.WITH)
        self.fi_wo = get_fi_data(self.module_wo, self.climate, self.moisture, utils.ScenarioTypes.WITHOUT)
        self.fmg_wo = get_fmg_data(self.module_wo, self.climate, self.moisture, utils.ScenarioTypes.WITHOUT)
        self.flu_wo = get_flu_data(self.module_wo, self.climate, self.moisture, utils.ScenarioTypes.WITHOUT)

        if isinstance(self.module, SingleBiomassModule) and not isinstance(self.module, Settlement):  # TODO: Incorporate SettlementEF with relevant IPCC tables
            if self.module.is_start() and self.module.is_with():
                self.biomass_ef_start_w = self.module_start.get_biomass_ef(utils.ScenarioTypes.START)
            if self.module.is_start() and self.module.is_without():
                self.biomass_ef_start_wo = self.module_start.get_biomass_ef(utils.ScenarioTypes.START)
            if self.module.is_with():
                self.biomass_ef_w = self.module_w.get_biomass_ef(utils.ScenarioTypes.WITH)
            if self.module.is_without():
                self.biomass_ef_wo = self.module_wo.get_biomass_ef(utils.ScenarioTypes.WITHOUT)


class LandUseChangeCalculator(BaseCalculator):
    """
    Calculator for land use change modules.
    """

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)

    def luc_based_calculation(self, module_start: LandModule | SingleBiomassModule, module_end: LandModule | SingleBiomassModule, aggregate_by=BreakdownTypes.TOTAL) -> Result:

        if type(module_start) == ForestManagement:
            return DeforestationCalculator(module_start).calculate()

        return OtherLandUseCalculator(module_end).calculate()

    def calculate(self, aggregate_by=BreakdownTypes.TOTAL) -> Result:
        """
        Calculate emissions for a single LandUseChange module.
        """

        luc: LandUseChange = self.data

        module_start, module_w, module_wo = luc.get_modules()

        if not module_start or not module_w or not module_wo:
            missing_modules = ["Start" if not module_start else "With" if not module_w else "Without" for module in [module_start, module_w, module_wo] if not module].join(", ")
            raise Exception(f"LandUseChange module must have a start with and without module. Missing {missing_modules} module(s).")

        self.results_w, self.results_wo = self.luc_based_calculation(module_start, module_w, aggregate_by=aggregate_by)

        return (self.results_w, self.results_wo)

    def defaults(self) -> DefaultData:
        pass


class DeforestationCalculator(BaseCalculator):
    """
    TODO: Refactor with new logic
    Calculator for deforestation modules.
    """

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)

    def calculate(self) -> Result:
        """
        Calculate emissions for a single Deforestation module.
        """

        module: LandModule = self.data
        luc: LandUseChange = module.land_use_change
        project: Project = module.activity.project
        change_rate = module.activity.change_rate
        climate = project.climate
        moisture = project.moisture
        region = project.country.region
        soil_type = project.soil_type

        forest: ForestManagement = module.activity.forestmanagement.first()

        module_start, module_w, module_wo = luc.get_modules()
        module_start: LandModule
        module_w: LandModule
        module_wo: LandModule

        # TODO: Maybe generalise this on a higher level
        if not forest:
            raise Exception("Forest module is missing")
        if module.status != StatusType.objects.get(name="READY"):
            raise Exception("Forest module is not complete")

        cmc = {
            "climate": climate,
            "moisture": moisture,
            "continent": region,
        }

        mangroves_data = None

        dry_matter_w = luc.dry_matter_w if luc else None
        dry_matter_wo = luc.dry_matter_wo if luc else None

        soc_ref = ipcc.SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type)
        som = ipcc.NitrousEmissionFactor.objects.get(moisture=moisture)

        if module_w.module_type.class_name == "ForestManagement":
            total_biomass_w = SimpleNamespace(value=0)
        else:
            try:
                total_biomass_w = ipcc.TotalBiomassAfterDefo.objects.get_or_default(**cmc, land_use_type=module_w.land_use_type_w)
            except ipcc.TotalBiomassAfterDefo.DoesNotExist:
                raise Exception(f"TotalBiomassAfterDefo for {module.land_use_type_w.name} in {climate.name} climate, {moisture.name} moisture, and {region.name} region does not exist")

        if module_wo.module_type.class_name == "ForestManagement":
            total_biomass_wo = SimpleNamespace(value=0)
        else:
            try:
                total_biomass_wo = ipcc.TotalBiomassAfterDefo.objects.get_or_default(**cmc, land_use_type=module_wo.land_use_type_wo)
            except ipcc.TotalBiomassAfterDefo.DoesNotExist:
                raise Exception(f"TotalBiomassAfterDefo for {module.land_use_type_wo.name} in {climate.name} climate, {moisture.name} moisture, and {region.name} region does not exist")

        # NOTE: Maybe merge the mangroves and deforestation IPCC tables into one table?
        # TODO: Review with new forest management data
        if forest.land_use_type_start.name != utils.MANGROVES:
            try:
                agb_start = ipcc.ForestManagementAGB.objects.get(climate=climate, region=region, forest_type=forest.forest_type, land_use_type=forest.land_use_type_start, forest_condition_type=forest.forest_condition_type)
            except ipcc.ForestManagementAGB.DoesNotExist:
                raise Exception(f"ForestManagementAGB for {forest.forest_type.name} {forest.forest_condition_type.name} {forest.land_use_type_start.name} in {climate.name} climate, {region.name} region, forest type does not exist")
            mean = statistics.mean([agb_start.agb_min, agb_start.agb_max])
            bgb_start = ipcc.ForestManagementBGB.objects.get_first_above_threshold(region=region, land_use_type=module.land_use_type_start, threshold=mean, climate=climate, forest_type=forest.forest_type)
            if not bgb_start:
                raise Exception(f"ForestManagementBGB for {module.land_use_type_start.name} in {climate.name} climate, {region.name} region, and {forest.forest_type.name} forest type does not exist")
            if module_w.module_type.class_name == "ForestManagement":
                litter_dw_w = SimpleNamespace(litter=0, dw=0)
                agb_w = SimpleNamespace(value=0)
                bgb_w = SimpleNamespace(value=0)
            else:
                try:
                    litter_dw_w = ipcc.LitterDeadwoodCarbonStock.objects.get(land_use_type=module.land_use_type_w, climate=climate, forest_type=forest.forest_type)
                except ipcc.LitterDeadwoodCarbonStock.DoesNotExist:
                    raise Exception(f"LitterDeadwoodCarbonStock for {module.land_use_type_w.name} in {climate.name} climate, {forest.forest_type.name} forest type does not exist")
                try:
                    agb_w = ipcc.ForestManagementAGB.objects.get(climate=climate, region=region, forest_type=forest.forest_type, land_use_type=forest.land_use_type_w, forest_condition_type=forest.forest_condition_type)
                except ipcc.ForestManagementAGB.DoesNotExist:
                    raise Exception(f"ForestManagementAGB for {forest.land_use_type_w.name} in {climate.name} climate, {region.name} region, {forest.forest_type.name} forest type, and Secondary >20 Years forest condition type does not exist")
                bgb_w = ipcc.ForestManagementBGB.objects.get_first_above_threshold(region=region, land_use_type=module.land_use_type_start, threshold=statistics.mean([agb_w.agb_min, agb_w.agb_max]), climate=climate, forest_type=forest.forest_type)
                if not bgb_w:
                    raise Exception(f"ForestManagementBGB for {module.land_use_type_w.name} in {climate.name} climate, {region.name} region, and {forest.forest_type.name} forest type does not exist")
            if module_wo.module_type.class_name == "ForestManagement":
                litter_dw_wo = SimpleNamespace(litter=0, dw=0)
                agb_wo = SimpleNamespace(value=0)
                bgb_wo = SimpleNamespace(value=0)
            else:
                try:
                    litter_dw_wo = ipcc.LitterDeadwoodCarbonStock.objects.get(land_use_type=module.land_use_type_wo, climate=climate, forest_type=forest.forest_type)
                except ipcc.LitterDeadwoodCarbonStock.DoesNotExist:
                    raise Exception(f"LitterDeadwoodCarbonStock for {module.land_use_type_wo.name} in {climate.name} climate, {forest.forest_type.name} forest type does not exist")
                try:
                    agb_wo = ipcc.ForestManagementAGB.objects.get(climate=climate, region=region, forest_type=forest.forest_type, land_use_type=forest.land_use_type_wo, forest_condition_type=forest.forest_condition_type)
                except ipcc.ForestManagementAGB.DoesNotExist:
                    raise Exception(f"ForestManagementAGB for {forest.land_use_type_wo.name} in {climate.name} climate, {region.name} region, {forest.forest_type.name} forest type, and Secondary >20 Years forest condition type does not exist")
                bgb_wo = ipcc.ForestManagementBGB.objects.get_first_above_threshold(region=region, land_use_type=module.land_use_type_w, threshold=statistics.mean([agb_wo.agb_min, agb_wo.agb_max]), climate=climate, forest_type=forest.forest_type)
                if not bgb_wo:
                    raise Exception(f"ForestManagementBGB for {module.land_use_type_wo.name} in {climate.name} climate, {region.name} region, and {forest.forest_type.name} forest type does not exist")
        else:
            mangroves_data = ipcc.DataOnMangrove.objects.get(continent=region)

        combustion_factor_w = ipcc.ForestCombustionFactor.objects.get(land_use_type=module.land_use_type_w, climate=climate, forest_type=forest.forest_type)
        combustion_factor_wo = ipcc.ForestCombustionFactor.objects.get(land_use_type=module.land_use_type_wo, climate=climate, forest_type=forest.forest_type)

        module_start = module_w = module_wo = module
        if luc:
            module_start, module_w, module_wo = luc.get_modules()

        flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        flu_w = get_flu_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        flu_wo = get_flu_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)

        fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        fi_w = get_fi_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        fi_wo = get_fi_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)

        fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        fmg_w = get_fmg_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        fmg_wo = get_fmg_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)

        soc_w = soc_ref
        soc_wo = soc_ref

        if luc.module_type_w.name == "Grassland":
            soc_w = ipcc.GrasslandStockExchangeFactor.objects.get(grassland_management_type=module_w.grassland_management_type_start, climate=project.climate)
            flu_w = SimpleNamespace(value=soc_w.flu)
            fi_w = SimpleNamespace(value=soc_w.fi)
            fmg_w = SimpleNamespace(value=soc_w.fmg)
            soc_w = SimpleNamespace(value=soc_w.flu * soc_w.fi * soc_w.fmg)

        if luc.module_type_wo.name == "Grassland":
            soc_wo = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module_wo.grassland_management_type_start,
                climate=project.climate,
            )
            flu_wo = SimpleNamespace(value=soc_wo.flu)
            fi_wo = SimpleNamespace(value=soc_wo.fi)
            fmg_wo = SimpleNamespace(value=soc_wo.fmg)
            soc_wo = SimpleNamespace(value=soc_wo.flu * soc_wo.fi * soc_wo.fmg)

        math_w = None
        math_wo = None

        if not module.is_luc_remaining_same():
            self.inputs_w = [
                0,
                luc.area,
                self.activity.implementation_years,
                self.activity.capitalization_years,
                change_rate.name,
                total_biomass_w.value,
                forest.biomass_t2_start,
                project.gwp.n2o,
                project.gwp.ch4,
                luc.is_fire_used_start,
                combustion_factor_w.n2o,
                combustion_factor_w.ch4,
                combustion_factor_w.value,
                som.value,
                litter_dw_w.litter if mangroves_data is None else mangroves_data.litter,
                forest.litter_t2_start,
                litter_dw_w.dw if mangroves_data is None else mangroves_data.dw,
                forest.deadwood_t2_start,
                dry_matter_w,
                utils.MANGROVE_FACTOR if mangroves_data is not None else utils.NON_MANGROVE_FACTOR,
                forest.bgb_t2_start,
                forest.agb_t2_start,
                statistics.mean([agb_w.agb_min, agb_w.agb_max]),
                bgb_w.value,
                utils.CN_RATIO_GRASSLAND,  # TODO: Ratio might be different, see OtherLandUseCalculator
                module_w.soc_t2_start,  # NOTE: SOC After Defo T2
                soc_ref.value,
                project.soc_ref_t2,
                module.fmg_t2_start,
                module.fmg_t2_w,
                module.fi_t2_start,
                module.fi_t2_w,
                module.flu_t2_start,
                module.flu_t2_w,
                forest.soc_t2_start,
                module_w.soc_t2_w,
                fmg_start.value,
                fmg_w.value,
                fi_start.value,
                fi_w.value,
                flu_start.value,
                flu_w.value,
                soc_ref.value,
                soc_w.value,
                CALCULATE_SOC_SOM_W,
                self.activity.delay,
                module_w.is_perennial() or module_w.is_forest(),
            ]

            math_w = MathDeforestation(*self.inputs_w)
            math_w.calculate_emissions()

        if not module.is_business_as_usual():
            self.inputs_wo = [
                0,
                luc.area,
                self.activity.implementation_years,
                self.activity.capitalization_years,
                change_rate.name,
                total_biomass_wo.value,
                forest.biomass_t2_start,
                project.gwp.n2o,
                project.gwp.ch4,
                luc.is_fire_used_start,
                combustion_factor_wo.n2o,
                combustion_factor_wo.ch4,
                combustion_factor_wo.value,
                som.value,
                litter_dw_wo.litter if mangroves_data is None else mangroves_data.litter,
                forest.litter_t2_start,
                litter_dw_wo.dw if mangroves_data is None else mangroves_data.dw,
                forest.deadwood_t2_start,
                dry_matter_wo,
                utils.MANGROVE_FACTOR if mangroves_data is not None else utils.NON_MANGROVE_FACTOR,
                forest.bgb_t2_start,
                forest.agb_t2_start,
                statistics.mean([agb_wo.agb_min, agb_wo.agb_max]),
                bgb_wo.value,
                utils.CN_RATIO_GRASSLAND,
                module_wo.soc_t2_start,  # NOTE: SOC After Defo T2
                soc_ref.value,
                project.soc_ref_t2,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                module.fi_t2_start,
                module.fi_t2_wo,
                module.flu_t2_start,
                module.flu_t2_wo,
                forest.soc_t2_start,
                module_wo.soc_t2_wo,
                fmg_start.value,
                fmg_wo.value,
                fi_start.value,
                fi_wo.value,
                flu_start.value,
                flu_wo.value,
                soc_ref.value,
                soc_wo.value,
                CALCULATE_SOC_SOM_WO,
                self.activity.delay,
                module_wo.is_perennial() or module_wo.is_forest(),
            ]

            math_wo = MathDeforestation(*self.inputs_wo)
            math_wo.calculate_emissions()

        res_w = math_w.result if math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        res_wo = math_wo.result if math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        return (res_w, res_wo)


class OtherLandUseCalculator(BaseCalculator):
    """
    Calculator for other land use modules.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single OtherLandUse module.
        """

        module: BiomassModule | LandModule = self.data
        luc: LandUseChange = module.land_use_change
        project: Project = self.data.activity.project
        climate = project.climate
        moisture = project.moisture
        continent = project.country.region

        soc = ipcc.SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=project.soil_type)

        cm = {
            "climate": climate,
            "moisture": moisture,
        }

        cmc = {
            "climate": climate,
            "moisture": moisture,
            "continent": continent,
        }

        module_start, module_w, module_wo = luc.get_modules()
        module_start: SingleBiomassModule | AboveBelowGroundBiomassModule
        module_w: SingleBiomassModule | AboveBelowGroundBiomassModule
        module_wo: SingleBiomassModule | AboveBelowGroundBiomassModule

        ready = all(module.status == StatusType.objects.get(name="READY") for module in [module_start, module_w, module_wo])
        if not ready:
            raise Exception("All modules associated with the land use change must be ready to perform the calculation")

        soc_start = None
        if luc.module_type_start.name == "Grassland":
            # Grassland SOCs
            soc_start = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module_start.grassland_management_type_start,
                climate=project.climate,
            )

        try:
            luc_start = module_start.land_use_type_start if module_start.land_use_type_start else LandUseType.objects.get(name=luc.module_type_start.name)
        except LandUseType.DoesNotExist:
            raise Exception(f"LandUseType for {luc.module_type_start.name} does not exist")

        try:
            luc_w = module_w.land_use_type_w if module_w.land_use_type_w else LandUseType.objects.get(name=luc.module_type_w.name)
        except LandUseType.DoesNotExist:
            raise Exception(f"LandUseType for {luc.module_type_w.name} does not exist")

        try:
            luc_wo = module_wo.land_use_type_wo if module_wo.land_use_type_wo else LandUseType.objects.get(name=luc.module_type_wo.name)
        except LandUseType.DoesNotExist:
            raise Exception(f"LandUseType for {luc.module_type_wo.name} does not exist")

        try:
            biomass_initial = ipcc.ForestTotalBiomass.objects.get_or_default(**cmc, land_use_type=luc_start)
        except ipcc.ForestTotalBiomass.DoesNotExist:
            raise Exception(f"ForestTotalBiomass for {luc_start.name} in {climate.name} climate, {moisture.name} moisture, and {continent.name} continent does not exist")

        try:
            # biomass_final_w = ipcc.TotalBiomassAfterDefo.objects.get_or_default(**cmc, land_use_type=luc_w)
            # NOTE: Always zero
            biomass_final_w = SimpleNamespace(value=0)
        except ipcc.TotalBiomassAfterDefo.DoesNotExist:
            raise Exception(f"TotalBiomassAfterDefo for {luc_w.name} in {climate.name} climate, {moisture.name} moisture, and {continent.name} continent does not exist")

        try:
            biomass_final_wo = ipcc.TotalBiomassAfterDefo.objects.get_or_default(**cmc, land_use_type=luc_wo)
        except ipcc.TotalBiomassAfterDefo.DoesNotExist:
            raise Exception(f"TotalBiomassAfterDefo for {luc_wo.name} in {climate.name} climate, {moisture.name} moisture, and {continent.name} continent does not exist")

        soc = ipcc.SoilOrganicCarbon.objects.get(**cm, soil_type=project.soil_type)

        try:
            fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        except ipcc.FMGData.DoesNotExist:
            raise Exception(f"FMGData for {module_start.tillage_management_type_start.name} in {climate.name} climate, {moisture.name} moisture does not exist")

        try:
            fmg_final_w = get_fmg_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        except ipcc.FMGData.DoesNotExist:
            raise Exception(f"FMGData for {module_w.tillage_management_type_w.name} in {climate.name} climate, {moisture.name} moisture does not exist")

        try:
            fmg_final_wo = get_fmg_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
        except ipcc.FMGData.DoesNotExist:
            raise Exception(f"FMGData for {module_wo.tillage_management_type_wo.name} in {climate.name} climate, {moisture.name} moisture does not exist")

        try:
            flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        except ipcc.FLUData.DoesNotExist:
            raise Exception(f"FLUData for {module_start.land_use_type_start.name} in {climate.name} climate, {moisture.name} moisture does not exist")

        try:
            flu_final_w = get_flu_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        except ipcc.FLUData.DoesNotExist:
            raise Exception(f"FLUData for {module_w.land_use_type_w.name} in {climate.name} climate, {moisture.name} moisture does not exist")

        try:
            flu_final_wo = get_flu_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
        except ipcc.FLUData.DoesNotExist:
            raise Exception(f"FLUData for {module_wo.land_use_type_wo.name} in {climate.name} climate, {moisture.name} moisture does not exist")

        try:
            fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        except ipcc.FIData.DoesNotExist:
            raise Exception(f"FIData for {module_start.organic_input_type_start.name} in {climate.name} climate, {moisture.name} moisture does not exist")

        try:
            fi_final_w = get_fi_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        except ipcc.FIData.DoesNotExist:
            raise Exception(f"FIData for {module_w.organic_input_type_w.name} in {climate.name} climate, {moisture.name} moisture does not exist")

        try:
            fi_final_wo = get_fi_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
        except ipcc.FIData.DoesNotExist:
            raise Exception(f"FIData for {module_wo.organic_input_type_wo.name} in {climate.name} climate, {moisture.name} moisture does not exist")

        c_n_ratio = utils.CN_RATIO_GRASSLAND if luc.module_type_start.class_name in ["Grassland", "ForestManagement"] else utils.CN_RATIO_CROP

        try:
            som = ipcc.NitrousEmissionFactor.objects.get(moisture=moisture)
        except ipcc.NitrousEmissionFactor.DoesNotExist:
            raise Exception(f"LandUseNitrousEmissionFactor for {moisture.name} moisture does not exist")

        try:
            combustion_factor_w = ipcc.AfforestationCombustionFactor.objects.get_or_default(land_use_type=luc_w)
        except ipcc.AfforestationCombustionFactor.DoesNotExist:
            raise Exception(f"AfforestationCombustionFactor for {luc_w.name} does not exist")

        try:
            combustion_factor_wo = ipcc.AfforestationCombustionFactor.objects.get_or_default(land_use_type=luc_wo)
        except ipcc.AfforestationCombustionFactor.DoesNotExist:
            raise Exception(f"AfforestationCombustionFactor for {luc_wo.name} does not exist")

        if not module_w.is_luc_remaining_same():
            inputs_w = {
                "end_module_has_growth": module_w.is_perennial() or module_w.is_forest(),
                "initial_lu_biomass": biomass_initial.value,
                "initial_lu_biomass_tier_2": module_start.biomass_t2_start,
                "final_lu_biomass": biomass_final_w.value,
                "final_lu_biomass_tier_2": module_w.biomass_t2_w,
                "c_n_ratio": c_n_ratio,
                "moisture_emission_factor": som.value,
                "combustion_factor": combustion_factor_w.value,
                "emission_factor_nitrous": combustion_factor_w.n2o,
                "emission_factor_methane": combustion_factor_w.ch4,
                "nitrous_constant": module.activity.project.gwp.n2o,
                "methane_constant": module.activity.project.gwp.ch4,
                "fire_bool": luc.is_fire_used_w,
                "soc_start_default": soc.value,
                "soc_end_default": soc.value,
                "soc_start_tier_2": module_start.soc_t2_start,
                "soc_end_tier_2": module_w.soc_t2_w,
                "fmg_start_default": soc_start.fmg if soc_start else fmg_start.value,
                "fmg_end_default": fmg_final_w.value,
                "fmg_start_tier_2": module_start.fmg_t2_start,  # TODO: Start module has 3 fmg (also fi and flu) values. What to choose?
                "fmg_end_tier_2": module_w.fmg_t2_w,
                "flu_start_default": soc_start.flu if soc_start else flu_start.value,
                "flu_end_default": flu_final_w.value,
                "flu_start_tier_2": module_start.flu_t2_start,
                "flu_end_tier_2": module_w.flu_t2_w,
                "fi_start_default": soc_start.fi if soc_start else fi_start.value,
                "fi_end_default": fi_final_w.value,
                "fi_start_tier_2": module_start.fi_t2_start,
                "fi_end_tier_2": module_w.fi_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_W,
                "area": luc.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": module.activity.change_rate.name,
                "dry_matter_end": luc.dry_matter_w,
                "delay": self.activity.delay,
            }

            self.results_w = MathOtherLandUseChanges(**inputs_w)
            self.results_w.calculate_emissions()

        if not module_wo.is_business_as_usual():
            inputs_wo = {
                "end_module_has_growth": module_wo.is_perennial() or module_wo.is_forest(),
                "initial_lu_biomass": biomass_initial.value,
                "initial_lu_biomass_tier_2": module_start.biomass_t2_start,
                "final_lu_biomass": biomass_final_wo.value,
                "final_lu_biomass_tier_2": module_wo.biomass_t2_wo,
                "c_n_ratio": c_n_ratio,
                "moisture_emission_factor": som.value,
                "combustion_factor": combustion_factor_wo.value,
                "emission_factor_nitrous": combustion_factor_wo.n2o,
                "emission_factor_methane": combustion_factor_wo.ch4,
                "nitrous_constant": module.activity.project.gwp.n2o,
                "methane_constant": module.activity.project.gwp.ch4,
                "fire_bool": luc.is_fire_used_wo,
                "soc_start_default": soc.value,
                "soc_end_default": soc.value,
                "soc_start_tier_2": module_start.soc_t2_start,
                "soc_end_tier_2": module_wo.soc_t2_wo,
                "fmg_start_default": fmg_start.value,
                "fmg_end_default": fmg_final_wo.value,
                "fmg_start_tier_2": module_start.fmg_t2_start,
                "fmg_end_tier_2": module_wo.fmg_t2_wo,
                "flu_start_default": flu_start.value,
                "flu_end_default": flu_final_wo.value,
                "flu_start_tier_2": module_start.flu_t2_start,
                "flu_end_tier_2": module_wo.flu_t2_wo,
                "fi_start_default": fi_start.value,
                "fi_end_default": fi_final_wo.value,
                "fi_start_tier_2": module_start.fi_t2_start,
                "fi_end_tier_2": module_wo.fi_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_WO,
                "area": luc.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": module.activity.change_rate.name,
                "dry_matter_end": luc.dry_matter_wo,
                "delay": self.activity.delay,
            }

            self.results_wo = MathOtherLandUseChanges(**inputs_wo)
            self.results_wo.calculate_emissions()

        res_w = self.results_w.result if self.results_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        res_wo = self.results_wo.result if self.results_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            res_w.plot_emissions_and_aggregate_by_activity("oluc_w")
            res_wo.plot_emissions_and_aggregate_by_activity("oluc_wo")

        return (res_w, res_wo)

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)


class AnnualCropCalculator(LandModuleCalculator):
    """
    Calculator for annual cropping modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.biomass_start: ipcc.ForestTotalBiomass = ipcc.ForestTotalBiomass()
        self.biomass_w: ipcc.TotalBiomassAfterDefo = ipcc.TotalBiomassAfterDefo()
        self.biomass_wo: ipcc.TotalBiomassAfterDefo = ipcc.TotalBiomassAfterDefo()
        self.crop_yield_start: ipcc.CropYieldStats = ipcc.CropYieldStats()
        self.crop_yield_w: ipcc.CropYieldStats = ipcc.CropYieldStats()
        self.crop_yield_wo: ipcc.CropYieldStats = ipcc.CropYieldStats()
        self.flu: ipcc.CroplandFLU = ipcc.CroplandFLU()
        self.burning_emission_factor: ipcc.BurningEmissionFactor = ipcc.BurningEmissionFactor()
        self.minor_burning_emission_factor: ipcc.BurningEmissionFactor = ipcc.BurningEmissionFactor()
        self.fires_start: ipcc.FiresCombustionFactor = ipcc.FiresCombustionFactor()
        self.fires_w: ipcc.FiresCombustionFactor = ipcc.FiresCombustionFactor()
        self.fires_wo: ipcc.FiresCombustionFactor = ipcc.FiresCombustionFactor()
        self.n_estimation_factor_start: ipcc.CropNitrousEstimationDefaultFactor = ipcc.CropNitrousEstimationDefaultFactor()
        self.n_estimation_factor_w: ipcc.CropNitrousEstimationDefaultFactor = ipcc.CropNitrousEstimationDefaultFactor()
        self.n_estimation_factor_wo: ipcc.CropNitrousEstimationDefaultFactor = ipcc.CropNitrousEstimationDefaultFactor()
        self.minor_fires_start: ipcc.FiresCombustionFactor = ipcc.FiresCombustionFactor()
        self.minor_fires_w: ipcc.FiresCombustionFactor = ipcc.FiresCombustionFactor()
        self.minor_fires_wo: ipcc.FiresCombustionFactor = ipcc.FiresCombustionFactor()
        self.minor_n_estimation_factor_start: ipcc.CropNitrousEstimationDefaultFactor = ipcc.CropNitrousEstimationDefaultFactor()
        self.minor_n_estimation_factor_w: ipcc.CropNitrousEstimationDefaultFactor = ipcc.CropNitrousEstimationDefaultFactor()
        self.minor_n_estimation_factor_wo: ipcc.CropNitrousEstimationDefaultFactor = ipcc.CropNitrousEstimationDefaultFactor()
        self.minor_biomass_start: ipcc.ForestTotalBiomass = ipcc.ForestTotalBiomass()
        self.minor_biomass_w: ipcc.TotalBiomassAfterDefo = ipcc.TotalBiomassAfterDefo()
        self.minor_biomass_wo: ipcc.TotalBiomassAfterDefo = ipcc.TotalBiomassAfterDefo()

        self.residue_availability_t2_start: SimpleNamespace = SimpleNamespace(value=0)
        self.residue_availability_t2_w: SimpleNamespace = SimpleNamespace(value=0)
        self.residue_availability_t2_wo: SimpleNamespace = SimpleNamespace(value=0)

        self.minor_residue_availability_t2_start: SimpleNamespace = SimpleNamespace(value=0)
        self.minor_residue_availability_t2_w: SimpleNamespace = SimpleNamespace(value=0)
        self.minor_residue_availability_t2_wo: SimpleNamespace = SimpleNamespace(value=0)

    def get_defaults(self, calculate=False) -> SimpleNamespace:
        super().get_defaults(calculate)

        module: AnnualCropland = self.data

        lut_start = self.module_start.land_use_type_start
        lut_w = self.module_w.land_use_type_w
        lut_wo = self.module_wo.land_use_type_wo

        if module.is_ready() and calculate:
            self.calculate()

            self.residue_availability_t2_start = SimpleNamespace(value=getattr_or_default(self.math_start_w, "ag_residue_main_tier_2_default") or getattr_or_default(self.math_start_wo, "ag_residue_main_tier_2_default"))
            self.residue_availability_t2_w = SimpleNamespace(value=getattr_or_default(self.math_w, "ag_residue_main_tier_2_default") or getattr_or_default(self.math_wo, "ag_residue_main_tier_2_default"))
            self.residue_availability_t2_wo = SimpleNamespace(value=getattr_or_default(self.math_wo, "ag_residue_main_tier_2_default") or getattr_or_default(self.math_wo, "ag_residue_main_tier_2_default"))
            self.minor_residue_availability_t2_start = SimpleNamespace(value=getattr_or_default(self.math_start_w, "ag_residue_minor_tier_2_default") or getattr_or_default(self.math_start_wo, "ag_residue_minor_tier_2_default"))
            self.minor_residue_availability_t2_w = SimpleNamespace(value=getattr_or_default(self.math_w, "ag_residue_minor_tier_2_default") or getattr_or_default(self.math_wo, "ag_residue_minor_tier_2_default"))
            self.minor_residue_availability_t2_wo = SimpleNamespace(value=getattr_or_default(self.math_wo, "ag_residue_minor_tier_2_default") or getattr_or_default(self.math_wo, "ag_residue_minor_tier_2_default"))

        climate = self.climate
        moisture = self.moisture

        cm = {"climate": climate, "moisture": moisture}
        lut_start_flt = {"land_use_type": self.module_start.land_use_type_start}
        lut_w_flt = {"land_use_type": self.module_w.land_use_type_w}
        lut_wo_flt = {"land_use_type": self.module_wo.land_use_type_wo}

        agricultural_residues_flt = {"category__name": "Agricultural residues"}
        long_term_cultivated_flt = {"land_use_type__name__icontains": "Long-Term Cultivated"}

        self.burning_emission_factor = utils.get_or_raise(ipcc.BurningEmissionFactor, agricultural_residues_flt, "BurningEmissionFactor for Agricultural residues does not exist")

        if module.minor_land_use_type_start or module.minor_land_use_type_w or module.minor_land_use_type_wo:
            self.minor_burning_emission_factor = utils.get_or_raise(ipcc.BurningEmissionFactor, agricultural_residues_flt, "BurningEmissionFactor for Agricultural residues for minor crop does not exist")

        if module.is_start():
            lut_start = module.land_use_type_start
            minor_lut_start = module.minor_land_use_type_start

            try:
                self.flu = ipcc.CroplandFLU.objects.get(**cm, **long_term_cultivated_flt)
            except ipcc.CroplandFLU.DoesNotExist:
                if module.flu_t2_start is None:
                    raise Exception(f"CroplandFLU for {lut_start.name} in {climate.name} climate and {moisture.name} moisture does not exist")

            self.fires_start = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_start_flt, f"FiresCombustionFactor for {lut_start.name} does not exist")
            self.n_estimation_factor_start = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_start_flt, f"CropNitrousEstimationDefaultFactor for {lut_start.name} does not exist", method="get_or_grains")

            try:
                self.crop_yield_start = ipcc.CropYieldStats.objects.get(continent=self.region, land_use_type=lut_start)
            except ipcc.CropYieldStats.DoesNotExist:
                if module.crop_yield_t2_start is None:
                    raise Exception(f"CropYieldStats for {lut_start.name}, {climate.name} {moisture.name} in {self.region.name} does not exist for start scenario.")

            if minor_lut_start is not None:
                try:
                    self.minor_fires_start = ipcc.FiresCombustionFactor.objects.get(land_use_type=minor_lut_start)
                except ipcc.FiresCombustionFactor.DoesNotExist:
                    raise Exception(f"FiresCombustionFactor for {minor_lut_start.name} does not exist")

                try:
                    self.minor_n_estimation_factor_start = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_start)
                except ipcc.CropNitrousEstimationDefaultFactor.DoesNotExist:
                    raise Exception(f"CropNitrousEstimationDefaultFactor for {minor_lut_start.name} does not exist")
            elif self.module.minor_yield_start is not None:
                raise Exception(f"Yield for minor season of {self.module.module_type.name} is specified but the minor crop is missing for the start scenario")

        if module.is_with():
            lut_w = module.land_use_type_w
            minor_lut_w = module.minor_land_use_type_w

            try:
                self.flu = ipcc.CroplandFLU.objects.get(**cm, **long_term_cultivated_flt)
            except ipcc.CroplandFLU.DoesNotExist:
                if module.flu_t2_w is None:
                    raise Exception(f"CroplandFLU for {lut_w.name} in {climate.name} climate and {moisture.name} moisture does not exist")

            self.fires_w = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_w_flt, f"FiresCombustionFactor for {lut_w.name} does not exist")
            self.n_estimation_factor_w = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_w_flt, f"CropNitrousEstimationDefaultFactor for {lut_w.name} does not exist", method="get_or_grains")

            try:
                self.crop_yield_w = ipcc.CropYieldStats.objects.get(continent=self.region, land_use_type=lut_w)
            except ipcc.CropYieldStats.DoesNotExist:
                if module.crop_yield_t2_w is None:
                    raise Exception(f"CropYieldStats for {lut_w.name}, {climate.name} {moisture.name} in {self.region.name} does not exist for with scenario.")

            if minor_lut_w is not None:
                try:
                    self.minor_fires_w = ipcc.FiresCombustionFactor.objects.get(land_use_type=minor_lut_w)
                except ipcc.FiresCombustionFactor.DoesNotExist:
                    raise Exception(f"FiresCombustionFactor for {minor_lut_w.name} does not exist")

                try:
                    self.minor_n_estimation_factor_w = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_w)
                except ipcc.CropNitrousEstimationDefaultFactor.DoesNotExist:
                    raise Exception(f"CropNitrousEstimationDefaultFactor for {minor_lut_w.name} does not exist")
            elif self.module.minor_yield_w is not None:
                raise Exception(f"Yield for minor season of {self.module.module_type.name} is specified but the minor crop is missing for the with scenario")

        if module.is_without():
            lut_wo = module.land_use_type_wo
            minor_lut_wo = module.minor_land_use_type_wo

            try:
                self.flu = ipcc.CroplandFLU.objects.get(**cm, **long_term_cultivated_flt)
            except ipcc.CroplandFLU.DoesNotExist:
                if module.flu_t2_wo is None:
                    raise Exception(f"CroplandFLU for {lut_wo.name} in {climate.name} climate and {moisture.name} moisture does not exist")

            self.fires_wo = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_wo_flt, f"FiresCombustionFactor for {lut_wo.name} does not exist")
            self.n_estimation_factor_wo = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_wo_flt, f"CropNitrousEstimationDefaultFactor for {lut_wo.name} does not exist", method="get_or_grains")

            try:
                self.crop_yield_wo = ipcc.CropYieldStats.objects.get(continent=self.region, land_use_type=lut_wo)
            except ipcc.CropYieldStats.DoesNotExist:
                if module.crop_yield_t2_wo is None:
                    raise Exception(f"CropYieldStats for {lut_wo.name}, {climate.name} {moisture.name} in {self.region.name} does not exist for without scenario.")

            if minor_lut_wo is not None:
                try:
                    self.minor_fires_wo = ipcc.FiresCombustionFactor.objects.get(land_use_type=lut_wo)
                except ipcc.FiresCombustionFactor.DoesNotExist:
                    raise Exception(f"FiresCombustionFactor for {minor_lut_wo.name} does not exist")

                try:
                    self.minor_n_estimation_factor_wo = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_wo)
                except ipcc.CropNitrousEstimationDefaultFactor.DoesNotExist:
                    raise Exception(f"CropNitrousEstimationDefaultFactor for {minor_lut_wo.name} does not exist")
            elif self.module.minor_yield_wo is not None:
                raise Exception(f"Yield for minor season of {self.module.module_type.name} is specified but the minor crop is missing for the without scenario")

    def calculate(self, aggregate_by=BreakdownTypes.TOTAL) -> tuple[MathResult]:
        """
        Calculate emissions for a single AnnualCropland module.
        """
        log.debug("START AnnualCropCalculator.calculate")

        self.module: AnnualCropland
        project: Project = self.module.activity.project

        change_rate = self.module.activity.change_rate

        self.get_defaults()

        if self.module.is_start():
            log.debug("Start")

            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_w.soc_t2_w,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_w.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_w.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_w.fi_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_W,
                "ef_nitrous_som": self.som.value,
                "nitrous_constant": project.gwp.n2o,
                "methane_constant": project.gwp.ch4,
                "ef_methane_agr_residues_main": self.burning_emission_factor.ch4 if self.module.residue_management_type_start.name == "Burned" else None,
                "combustion_factor_main": self.fires_start.value,
                "residue_main_tier_2": self.module.residue_availability_t2_start,
                "n_estimation_slope_main": self.n_estimation_factor_start.slope,
                "n_estimation_intercept_main": self.n_estimation_factor_start.intercept,
                "yield_value_main": self.crop_yield_start.average,
                "yield_main_tier_2": self.module.crop_yield_t2_w,
                "ef_methane_agr_residues_minor": self.minor_burning_emission_factor.ch4,
                "combustion_factor_minor": self.minor_fires_start.value,
                "residue_minor_tier_2": self.module.minor_biomass_factor_t2_start,
                "n_estimation_slope_minor": self.minor_n_estimation_factor_start.slope,
                "n_estimation_intercept_minor": self.minor_n_estimation_factor_start.intercept,
                "yield_value_minor": self.module.minor_yield_w,
                "yield_minor_tier_2": self.module.crop_yield_t2_w,
                "ef_nitrous_agr_residues_main": self.burning_emission_factor.n2o if self.module.residue_management_type_start.name == "Burned" else None,
                "retained_main": self.module.residue_management_type_start.name == "Retained",
                "ef_nitrous_agr_residues_minor": self.minor_burning_emission_factor.n2o,
                "retained_minor": self.module.minor_residue_management_type_start.name == "Retained" if self.module.minor_residue_management_type_start else None,
                "n_content_ag_main": self.n_estimation_factor_start.n_ag_residues,
                "ratio_bg_ag_main": self.n_estimation_factor_start.rs_t,
                "n_content_bg_main": self.n_estimation_factor_start.n_bg_t,
                "n_content_ag_minor": self.minor_n_estimation_factor_start.n_ag_residues,
                "ratio_bg_ag_minor": self.minor_n_estimation_factor_start.rs_t,
                "n_content_bg_minor": self.minor_n_estimation_factor_start.n_bg_t,
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start_w.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "calculate_biomass": self.calculate_biomass_start_w,
                "biomass_start_tier_2": self.module_w.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }
            log.debug("Inputs start w: %s", self.inputs_start_w)

            self.math_start_w = MathAnnualCropland(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_wo.soc_t2_wo,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_wo.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_wo.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_wo.fi_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_WO,
                "ef_nitrous_som": self.som.value,
                "nitrous_constant": project.gwp.n2o,
                "methane_constant": project.gwp.ch4,
                "ef_methane_agr_residues_main": self.burning_emission_factor.ch4 if self.module.residue_management_type_start.name == "Burned" else None,
                "combustion_factor_main": self.fires_start.value,
                "residue_main_tier_2": self.module.residue_availability_t2_start,
                "n_estimation_slope_main": self.n_estimation_factor_start.slope,
                "n_estimation_intercept_main": self.n_estimation_factor_start.intercept,
                "yield_value_main": self.crop_yield_start.average,
                "yield_main_tier_2": self.module.crop_yield_t2_wo,
                "ef_methane_agr_residues_minor": self.minor_burning_emission_factor.ch4,
                "combustion_factor_minor": self.minor_fires_start.value,
                "residue_minor_tier_2": self.module.minor_biomass_factor_t2_start,
                "n_estimation_slope_minor": self.minor_n_estimation_factor_start.slope,
                "n_estimation_intercept_minor": self.minor_n_estimation_factor_start.intercept,
                "yield_value_minor": self.module.minor_yield_wo,
                "yield_minor_tier_2": self.module.crop_yield_t2_wo,
                "ef_nitrous_agr_residues_main": self.burning_emission_factor.n2o if self.module.residue_management_type_start.name == "Burned" else None,
                "retained_main": self.module.residue_management_type_start.name == "Retained",
                "ef_nitrous_agr_residues_minor": self.minor_burning_emission_factor.n2o,
                "retained_minor": self.module.minor_residue_management_type_start.name == "Retained" if self.module.minor_residue_management_type_start else None,
                "n_content_ag_main": self.n_estimation_factor_start.n_ag_residues,
                "ratio_bg_ag_main": self.n_estimation_factor_start.rs_t,
                "n_content_bg_main": self.n_estimation_factor_start.n_bg_t,
                "n_content_ag_minor": self.minor_n_estimation_factor_start.n_ag_residues,
                "ratio_bg_ag_minor": self.minor_n_estimation_factor_start.rs_t,
                "n_content_bg_minor": self.minor_n_estimation_factor_start.n_bg_t,
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start_wo.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "calculate_biomass": self.calculate_biomass_start_wo,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }
            log.debug("Inputs start wo: %s", self.inputs_start_wo)

            self.math_start_wo = MathAnnualCropland(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if self.module.is_with():
            log.debug("Is with")

            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_w.soc_t2_w,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_w.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_w.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_w.fi_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_W,
                "ef_nitrous_som": self.som.value,
                "nitrous_constant": project.gwp.n2o,
                "methane_constant": project.gwp.ch4,
                "ef_methane_agr_residues_main": self.burning_emission_factor.ch4 if self.module.residue_management_type_w.name == "Burned" else None,
                "combustion_factor_main": self.fires_w.value,
                "residue_main_tier_2": self.module.residue_availability_t2_w,
                "n_estimation_slope_main": self.n_estimation_factor_w.slope,
                "n_estimation_intercept_main": self.n_estimation_factor_w.intercept,
                "yield_value_main": self.crop_yield_w.average,
                "yield_main_tier_2": self.module.crop_yield_t2_w,
                "ef_methane_agr_residues_minor": self.minor_burning_emission_factor.ch4,
                "combustion_factor_minor": self.minor_fires_w.value,
                "residue_minor_tier_2": self.module.minor_biomass_factor_t2_w,
                "n_estimation_slope_minor": self.minor_n_estimation_factor_w.slope,
                "n_estimation_intercept_minor": self.minor_n_estimation_factor_w.intercept,
                "yield_value_minor": self.module.minor_yield_w,
                "yield_minor_tier_2": self.module.crop_yield_t2_w,
                "ef_nitrous_agr_residues_main": self.burning_emission_factor.n2o if self.module.residue_management_type_w.name == "Burned" else None,
                "retained_main": self.module.residue_management_type_w.name == "Retained",
                "ef_nitrous_agr_residues_minor": self.minor_burning_emission_factor.n2o,
                "retained_minor": self.module.minor_residue_management_type_w.name == "Retained" if self.module.minor_residue_management_type_w else None,
                "n_content_ag_main": self.n_estimation_factor_w.n_ag_residues,
                "ratio_bg_ag_main": self.n_estimation_factor_w.rs_t,
                "n_content_bg_main": self.n_estimation_factor_w.n_bg_t,
                "n_content_ag_minor": self.minor_n_estimation_factor_w.n_ag_residues,
                "ratio_bg_ag_minor": self.minor_n_estimation_factor_w.rs_t,
                "n_content_bg_minor": self.minor_n_estimation_factor_w.n_bg_t,
                "delay": self.activity.delay,
                "calculate_biomass": self.calculate_biomass_w,
                "biomass_start_default": self.biomass_ef_start_w.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }
            log.debug("Inputs w: %s", self.inputs_w)

            self.math_w = MathAnnualCropland(**self.inputs_w)
            self.math_w.calculate_emissions()

        if self.module.is_without():
            log.debug("Is without")

            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_wo.soc_t2_wo,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_wo.fmg_t2_wo,
                "flu_start_default": self.flu.value,
                "flu_end_default": self.flu.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_wo.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_wo.fi_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_WO,
                "ef_nitrous_som": self.som.value,
                "nitrous_constant": project.gwp.n2o,
                "methane_constant": project.gwp.ch4,
                "ef_methane_agr_residues_main": self.burning_emission_factor.ch4 if self.module.residue_management_type_wo.name == "Burned" else None,
                "combustion_factor_main": self.fires_wo.value,
                "residue_main_tier_2": self.module.residue_availability_t2_wo,
                "n_estimation_slope_main": self.n_estimation_factor_wo.slope,
                "n_estimation_intercept_main": self.n_estimation_factor_wo.intercept,
                "yield_value_main": self.crop_yield_wo.average,
                "yield_main_tier_2": self.module.crop_yield_t2_wo,
                "ef_methane_agr_residues_minor": self.minor_burning_emission_factor.ch4,
                "combustion_factor_minor": self.minor_fires_wo.value,
                "residue_minor_tier_2": self.module.minor_biomass_factor_t2_wo,
                "n_estimation_slope_minor": self.minor_n_estimation_factor_wo.slope,
                "n_estimation_intercept_minor": self.minor_n_estimation_factor_wo.intercept,
                "yield_value_minor": self.module.minor_yield_wo,
                "yield_minor_tier_2": self.module.crop_yield_t2_wo,
                "ef_nitrous_agr_residues_main": self.burning_emission_factor.n2o if self.module.residue_management_type_wo.name == "Burned" else None,
                "retained_main": self.module.residue_management_type_wo.name == "Retained",
                "ef_nitrous_agr_residues_minor": self.minor_burning_emission_factor.n2o,
                "retained_minor": self.module.minor_residue_management_type_wo.name == "Retained" if self.module.minor_residue_management_type_wo else None,
                "n_content_ag_main": self.n_estimation_factor_wo.n_ag_residues,
                "ratio_bg_ag_main": self.n_estimation_factor_wo.rs_t,
                "n_content_bg_main": self.n_estimation_factor_wo.n_bg_t,
                "n_content_ag_minor": self.minor_n_estimation_factor_wo.n_ag_residues,
                "ratio_bg_ag_minor": self.minor_n_estimation_factor_wo.rs_t,
                "n_content_bg_minor": self.minor_n_estimation_factor_wo.n_bg_t,
                "delay": self.activity.delay,
                "calculate_biomass": self.calculate_biomass_wo,
                "biomass_start_default": self.biomass_ef_start_wo.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }
            log.debug("Inputs wo: %s", self.inputs_wo)

            self.math_wo = MathAnnualCropland(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_start_w.plot_emissions_and_aggregate_by_activity("annual_start_w")
            self.results_start_wo.plot_emissions_and_aggregate_by_activity("annual_start_wo")
            self.results_w.plot_emissions_and_aggregate_by_activity("annual_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("annual_wo")

        log.debug("END AnnualCropCalculator.calculate")

        return (self.results_w + self.results_start_w, self.results_wo + self.results_start_wo)


class AnnualCroplandCalculator(AnnualCropCalculator):
    pass


class PerennialCropCalculator(LandModuleCalculator):

    def __init__(self, input) -> None:
        super().__init__(input)

        self.module: PerennialCropland

        self.burning_emission_factor: ipcc.BurningEmissionFactor = ipcc.BurningEmissionFactor()
        self.fires_combustion_factor_start: ipcc.FiresCombustionFactor = ipcc.FiresCombustionFactor()
        self.fires_combustion_factor_w: ipcc.FiresCombustionFactor = ipcc.FiresCombustionFactor()
        self.fires_combustion_factor_wo: ipcc.FiresCombustionFactor = ipcc.FiresCombustionFactor()
        self.agb_start_default: ipcc.PerennialAGB = ipcc.PerennialAGB()
        self.agb_w_default: ipcc.PerennialAGB = ipcc.PerennialAGB()
        self.ag_default_wo: ipcc.PerennialAGB = ipcc.PerennialAGB()
        self.agb_max_start_default: ipcc.PerennialMaxAGB = ipcc.PerennialMaxAGB()
        self.agb_max_w_default: ipcc.PerennialMaxAGB = ipcc.PerennialMaxAGB()
        self.agb_max_wo_default: ipcc.PerennialMaxAGB = ipcc.PerennialMaxAGB()
        self.bgb_start_default: ipcc.PerennialBGB = ipcc.PerennialBGB()
        self.bgb_w_default: ipcc.PerennialBGB = ipcc.PerennialBGB()
        self.bg_default_wo: ipcc.PerennialBGB = ipcc.PerennialBGB()

        # Calculated by math model
        self.residue_availability_t2_start: SimpleNamespace = SimpleNamespace(value=0)
        self.residue_availability_t2_w: SimpleNamespace = SimpleNamespace(value=0)
        self.residue_availability_t2_wo: SimpleNamespace = SimpleNamespace(value=0)

        self.end_module_has_growth_start_w = False
        self.end_module_has_growth_start_wo = False
        self.end_module_has_growth_w = False
        self.end_module_has_growth_wo = False

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        savanna_flt = {"category__name": "Savanna and grassland"}

        lut_start_flt = {"land_use_type": self.module.land_use_type_start}
        lut_w_flt = {"land_use_type": self.module.land_use_type_w}
        lut_wo_flt = {"land_use_type": self.module.land_use_type_wo}

        cmc = {
            "climate": self.climate,
            "moisture": self.moisture,
            "continent": self.region,
        }

        if self.module.is_ready() and calculate:
            self.calculate()

            self.residue_availability_t2_start = SimpleNamespace(value=getattr(self.math_start_w, "biomass_availability_tier_2_default", 0) or getattr(self.math_start_wo, "biomass_availability_tier_2_default", 0))
            self.residue_availability_t2_w = SimpleNamespace(value=getattr(self.math_w, "biomass_availability_tier_2_default", 0) or getattr(self.math_wo, "biomass_availability_tier_2_default", 0))
            self.residue_availability_t2_wo = SimpleNamespace(value=getattr(self.math_w, "biomass_availability_tier_2_default", 0) or getattr(self.math_wo, "biomass_availability_tier_2_default", 0))

        self.burning_emission_factor = utils.get_or_raise(ipcc.BurningEmissionFactor, savanna_flt, "BurningEmissionFactor for Savanna and grassland does not exist")
        self.default_fire_periodicity = AnnualCroplandParameter.objects.get(name="default_fire_periodicity")

        if self.module.is_start():
            self.fires_combustion_factor_start = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_start_flt, f"FiresCombustionFactor for {self.module.land_use_type_start.name} does not exist", method="get_or_default")

            try:
                self.agb_start_default = ipcc.PerennialAGB.objects.get(climate=self.climate, moisture=self.moisture, continent=self.region, land_use_type=self.module.land_use_type_start)
            except ipcc.PerennialAGB.DoesNotExist:
                if self.module.agb_t2_start is None:
                    raise Exception(f"PerennialAGB for {self.module.land_use_type_start.name} in {self.climate.name} climate does not exist for start scenario. Please provide Tier 2 values.")

            try:
                self.agb_max_start_default = ipcc.PerennialMaxAGB.objects.get(climate=self.climate, land_use_type=self.module.land_use_type_start)
            except ipcc.PerennialMaxAGB.DoesNotExist:
                if self.module.agb_max_t2_start is None:
                    raise Exception(f"PerennialMaxAGB for {self.module.land_use_type_start.name} in {self.climate.name} climate does not exist for start scenario. Please provide Tier 2 values.")

            try:
                self.bgb_start_default = ipcc.PerennialBGB.objects.get(climate=self.climate, moisture=self.moisture, continent=self.region, land_use_type=self.module.land_use_type_start)
            except ipcc.PerennialBGB.DoesNotExist:
                if self.module.bgb_t2_start is None:
                    raise Exception(f"PerennialBGB for {self.module.land_use_type_start.name} in {self.climate.name} climate does not exist for start scenario. Please provide Tier 2 values.")

        if self.module.is_with():
            self.fires_combustion_factor_w = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_w_flt, f"FiresCombustionFactor for {self.module.land_use_type_w.name} does not exist", method="get_or_default")

            try:
                self.agb_w_default = ipcc.PerennialAGB.objects.get(climate=self.climate, moisture=self.moisture, continent=self.region, land_use_type=self.module.land_use_type_w)
            except ipcc.PerennialAGB.DoesNotExist:
                if self.module.agb_t2_w is None:
                    raise Exception(f"PerennialAGB for {self.module.land_use_type_w.name} in {self.climate.name} climate does not exist for with scenario. Please provide Tier 2 values.")

            try:
                self.agb_max_w_default = ipcc.PerennialMaxAGB.objects.get(climate=self.climate, land_use_type=self.module.land_use_type_w)
            except ipcc.PerennialMaxAGB.DoesNotExist:
                if self.module.agb_max_t2_w is None:
                    raise Exception(f"PerennialMaxAGB for {self.module.land_use_type_w.name} in {self.climate.name} climate does not exist for with scenario. Please provide Tier 2 values.")

            try:
                self.bgb_w_default = ipcc.PerennialBGB.objects.get(climate=self.climate, moisture=self.moisture, continent=self.region, land_use_type=self.module.land_use_type_w)
            except ipcc.PerennialBGB.DoesNotExist:
                if self.module.bgb_t2_w is None:
                    raise Exception(f"PerennialBGB for {self.module.land_use_type_w.name} in {self.climate.name} climate does not exist for with scenario. Please provide Tier 2 values.")

        if self.module.is_without():
            self.fires_combustion_factor_wo = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_wo_flt, f"FiresCombustionFactor for {self.module.land_use_type_wo.name} does not exist")

            try:
                self.ag_default_wo = ipcc.PerennialAGB.objects.get(climate=self.climate, moisture=self.moisture, continent=self.region, land_use_type=self.module.land_use_type_wo)
            except ipcc.PerennialAGB.DoesNotExist:
                if self.module.agb_t2_wo is None:
                    raise Exception(f"PerennialAGB for {self.module.land_use_type_wo.name} in {self.climate.name} climate does not exist for without scenario. Please provide Tier 2 values.")

            try:
                self.agb_max_wo_default = ipcc.PerennialMaxAGB.objects.get(climate=self.climate, land_use_type=self.module.land_use_type_wo)
            except ipcc.PerennialMaxAGB.DoesNotExist:
                if self.module.agb_max_t2_wo is None:
                    raise Exception(f"PerennialMaxAGB for {self.module.land_use_type_wo.name} in {self.climate.name} climate does not exist for without scenario. Please provide Tier 2 values.")

            try:
                self.bg_default_wo = ipcc.PerennialBGB.objects.get(climate=self.climate, moisture=self.moisture, continent=self.region, land_use_type=self.module.land_use_type_wo)
            except ipcc.PerennialBGB.DoesNotExist:
                if self.module.bgb_t2_wo is None:
                    raise Exception(f"PerennialBGB for {self.module.land_use_type_wo.name} in {self.climate.name} climate does not exist for without scenario. Please provide Tier 2 values.")

        # Perennial from LUC
        if self.module_start.module_type.is_luc and self.module.is_with() and not self.module.is_start():
            self.biomass_ef_start.value = 0
            self.biomass_ef_w.value = 0
            self.end_module_has_growth_w = True

        if self.module_start.module_type.is_luc and self.module.is_without() and not self.module.is_start():
            self.biomass_ef_start.value = 0
            self.biomass_ef_wo.value = 0
            self.end_module_has_growth_wo = True

        # Perennial to LUC
        if self.module.is_start() and not self.module.is_with() and self.module_w.module_type.is_luc:
            self.biomass_ef_w.value = 0
            self.biomass_ef_wo.value = 0

        if self.module.is_start() and not self.module.is_without() and self.module_wo.module_type.is_luc:
            self.biomass_ef_wo.value = 0

        # Other changes to systems in maturity
        if self.module.is_start() and self.module.is_with():
            self.end_module_has_growth_w = False
            self.biomass_ef_w = self.biomass_ef_start

        if self.module.is_start() and self.module.is_without():
            self.end_module_has_growth_wo = False
            self.biomass_ef_wo = self.biomass_ef_start

    def calculate(self, aggregate_by=BreakdownTypes.TOTAL) -> list[Result]:
        """
        Calculate emissions for a single PerennialCropland module.
        """
        log.debug("START PerennialCropCalculator.calculate")

        self.get_defaults()

        if self.module.is_start():

            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "methane_constant": self.project.gwp.ch4,
                "residue_burnt": self.module.is_biomass_burned_start,
                "emission_factor_burning_nitrous_residue": self.burning_emission_factor.n2o,
                "ef_nitrous_som": self.som.value,
                "emission_factor_burning_methane": self.burning_emission_factor.ch4,
                "combustion_factor": self.fires_combustion_factor_start.value,
                "fire_periodicity_default": self.default_fire_periodicity.value,
                "fire_periodicity_tier_2": self.module.fire_periodicity_t2_start,
                "t_biomass_tier_2": self.module.residue_availability_t2_start,
                "agb_rate_default": self.agb_start_default.value,
                "agb_rate_tier_2": self.module.agb_t2_start,
                "agb_maximum_c": self.agb_max_start_default.value,
                "bgb_rate_default": self.bgb_start_default.value,
                "bgb_rate_tier_2": self.module.bgb_t2_start,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": self.module.soc_t2_start,
                "soc_end_tier_2": self.module.soc_t2_w,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_w.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_w.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_w.fi_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_W,
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "calculate_biomass": self.module.is_start() and self.module.is_with(),
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
                "end_module_has_growth": self.end_module_has_growth_start_w,
            }
            log.debug("Inputs start w: %s", self.inputs_start_w)

            self.math_start_w = MathPerennialCropland(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "methane_constant": self.project.gwp.ch4,
                "residue_burnt": self.module.is_biomass_burned_start,
                "emission_factor_burning_nitrous_residue": self.burning_emission_factor.n2o,
                "ef_nitrous_som": self.som.value,
                "emission_factor_burning_methane": self.burning_emission_factor.ch4,
                "combustion_factor": self.fires_combustion_factor_start.value,
                "fire_periodicity_default": self.default_fire_periodicity.value,
                "fire_periodicity_tier_2": self.module.fire_periodicity_t2_start,
                "t_biomass_tier_2": self.module.residue_availability_t2_start,
                "agb_rate_default": self.agb_start_default.value,
                "agb_rate_tier_2": self.module.agb_t2_start,
                "agb_maximum_c": self.agb_max_start_default.value,
                "bgb_rate_default": self.bgb_start_default.value,
                "bgb_rate_tier_2": self.module.bgb_t2_start,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_wo.soc_t2_wo,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_wo.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_wo.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_wo.fi_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_WO,
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "calculate_biomass": self.module.is_start() and self.module.is_without(),
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
                "end_module_has_growth": self.end_module_has_growth_start_wo,
            }
            log.debug("Input start wo: %s", self.inputs_start_wo)

            self.math_start_wo = MathPerennialCropland(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if self.module.is_with():
            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "methane_constant": self.project.gwp.ch4,
                "residue_burnt": self.module.is_biomass_burned_w,
                "emission_factor_burning_nitrous_residue": self.burning_emission_factor.n2o,
                "ef_nitrous_som": self.som.value,
                "emission_factor_burning_methane": self.burning_emission_factor.ch4,
                "combustion_factor": self.fires_combustion_factor_w.value,
                "fire_periodicity_default": self.default_fire_periodicity.value,
                "fire_periodicity_tier_2": self.module.fire_periodicity_t2_w,
                "t_biomass_tier_2": self.module.residue_availability_t2_w,
                "agb_rate_default": self.agb_w_default.value,
                "agb_rate_tier_2": self.module.agb_t2_w,
                "agb_maximum_c": self.agb_max_w_default.value,
                "bgb_rate_default": self.bgb_w_default.value,
                "bgb_rate_tier_2": self.module.bgb_t2_w,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_w.soc_t2_w,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_w.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_w.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_w.fi_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_W,
                "delay": self.activity.delay,
                "calculate_biomass": True,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
                "end_module_has_growth": self.end_module_has_growth_w,
            }
            log.debug("Inputs w: %s", self.inputs_w)

            self.math_w = MathPerennialCropland(**self.inputs_w)
            self.math_w.calculate_emissions()

        if self.module.is_without():
            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "methane_constant": self.project.gwp.ch4,
                "residue_burnt": self.module.is_biomass_burned_wo,
                "emission_factor_burning_nitrous_residue": self.burning_emission_factor.n2o,
                "ef_nitrous_som": self.som.value,
                "emission_factor_burning_methane": self.burning_emission_factor.ch4,
                "combustion_factor": self.fires_combustion_factor_wo.value,
                "fire_periodicity_default": self.default_fire_periodicity.value,
                "fire_periodicity_tier_2": self.module.fire_periodicity_t2_wo,
                "t_biomass_tier_2": self.module.residue_availability_t2_wo,
                "agb_rate_default": self.ag_default_wo.value,
                "agb_rate_tier_2": self.module.agb_t2_wo,
                "agb_maximum_c": self.agb_max_wo_default.value,
                "bgb_rate_default": self.bg_default_wo.value,
                "bgb_rate_tier_2": self.module.bgb_t2_wo,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_wo.soc_t2_wo,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_wo.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_wo.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_wo.fi_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_WO,
                "delay": self.activity.delay,
                "calculate_biomass": True,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
                "end_module_has_growth": self.end_module_has_growth_wo,
            }
            log.debug("Inputs wo: %s", self.inputs_wo)

            self.math_wo = MathPerennialCropland(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_start_w.plot_emissions_and_aggregate_by_activity("perennial_start_w")
            self.results_start_wo.plot_emissions_and_aggregate_by_activity("perennial_start_wo")
            self.results_w.plot_emissions_and_aggregate_by_activity("perennial_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("perennial_wo")

        results_tuple = (self.results_w + self.results_start_w, self.results_wo + self.results_start_wo)

        return results_tuple


class PerennialCroplandCalculator(PerennialCropCalculator):
    """
    Calculator for perennial cropping.
    """

    pass


class FloodedRiceSeasonCalculator(LandModuleCalculator):

    def __init__(self, input) -> None:
        super().__init__(input)

        self.module: FloodedRice | MinorSeasonFloodedRice

        self.efc_default: ipcc.RiceDefaultEmissionFactor = ipcc.RiceDefaultEmissionFactor()
        self.yield_default: ipcc.RiceYield = ipcc.RiceYield()
        self.sfw_start_default: ipcc.RiceSFW = ipcc.RiceSFW()
        self.sfw_w_default: ipcc.RiceSFW = ipcc.RiceSFW()
        self.sfw_wo_default: ipcc.RiceSFW = ipcc.RiceSFW()
        self.sfp_start_default: ipcc.RiceSFP = ipcc.RiceSFP()
        self.sfp_w_default: ipcc.RiceSFP = ipcc.RiceSFP()
        self.sfp_wo_default: ipcc.RiceSFP = ipcc.RiceSFP()
        self.sfo_start_default: ipcc.RiceSFO = ipcc.RiceSFO()
        self.sfo_w_default: ipcc.RiceSFO = ipcc.RiceSFO()
        self.sfo_wo_default: ipcc.RiceSFO = ipcc.RiceSFO()

        self.n_estimation_factor_default: ipcc.CropNitrousEstimationDefaultFactor = ipcc.CropNitrousEstimationDefaultFactor()
        self.burning_emission_factor_default: ipcc.BurningEmissionFactor = ipcc.BurningEmissionFactor()
        self.rice_cf_default: ipcc.FiresCombustionFactor = ipcc.FiresCombustionFactor()

        self.efi_start_default: DefaultValue = DefaultValue()
        self.efi_w_default: DefaultValue = DefaultValue()
        self.efi_wo_default: DefaultValue = DefaultValue()
        self.straw_burned_start_default: DefaultValue = DefaultValue()
        self.straw_burned_w_default: DefaultValue = DefaultValue()
        self.straw_burned_wo_default: DefaultValue = DefaultValue()

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module_for_checks = getattr(self.module, "parent", self.module)

        if module_for_checks.is_start():
            try:
                self.sfw_start_default = ipcc.RiceSFW.objects.get(water_management_type_after_cultivation=self.module.water_management_type_after_cultivation_start)
            except ipcc.RiceSFW.DoesNotExist:
                if self.module.sfw_t2_start is None:
                    raise Exception(f"RiceSFW for {self.module.water_management_type_after_cultivation_start} does not exist for start scenario. Please provide Tier 2 values.")

            try:
                self.sfp_start_default = ipcc.RiceSFP.objects.get(water_management_type_before_cultivation=self.module.water_management_type_before_cultivation_start)
            except ipcc.RiceSFP.DoesNotExist:
                if self.module.sfp_t2_start is None:
                    raise Exception(f"RiceSFP for {self.module.water_management_type_before_cultivation_start} does not exist for start scenario. Please provide Tier 2 values.")

            try:
                self.sfo_start_default = ipcc.RiceSFO.objects.get(organic_amendment_type=self.module.organic_amendment_type_start)
            except ipcc.RiceSFO.DoesNotExist:
                if self.module.sfo_t2_start is None:
                    raise Exception(f"RiceSFO for {self.module.organic_amendment_type_start} does not exist for start scenario. Please provide Tier 2 values.")

        if module_for_checks.is_with():
            try:
                self.sfw_w_default = ipcc.RiceSFW.objects.get(water_management_type_after_cultivation=self.module.water_management_type_after_cultivation_w)
            except ipcc.RiceSFW.DoesNotExist:
                if self.module.sfw_t2_w is None:
                    raise Exception(f"RiceSFW for {self.module.water_management_type_after_cultivation_w} does not exist for with scenario. Please provide Tier 2 values.")

            try:
                self.sfp_w_default = ipcc.RiceSFP.objects.get(water_management_type_before_cultivation=self.module.water_management_type_before_cultivation_w)
            except ipcc.RiceSFP.DoesNotExist:
                if self.module.sfp_t2_w is None:
                    raise Exception(f"RiceSFP for {self.module.water_management_type_before_cultivation_w} does not exist for with scenario. Please provide Tier 2 values.")

            try:
                self.sfo_w_default = ipcc.RiceSFO.objects.get(organic_amendment_type=self.module.organic_amendment_type_w)
            except ipcc.RiceSFO.DoesNotExist:
                if self.module.sfo_t2_w is None:
                    raise Exception(f"RiceSFO for {self.module.organic_amendment_type_w} does not exist for with scenario. Please provide Tier 2 values.")

        if module_for_checks.is_without():
            try:
                self.sfw_wo_default = ipcc.RiceSFW.objects.get(water_management_type_after_cultivation=self.module.water_management_type_after_cultivation_wo)
            except ipcc.RiceSFW.DoesNotExist:
                if self.module.sfw_t2_wo is None:
                    raise Exception(f"RiceSFW for {self.module.water_management_type_after_cultivation_wo} does not exist for without scenario. Please provide Tier 2 values.")

            try:
                self.sfp_wo_default = ipcc.RiceSFP.objects.get(water_management_type_before_cultivation=self.module.water_management_type_before_cultivation_wo)
            except ipcc.RiceSFP.DoesNotExist:
                if self.module.sfp_t2_wo is None:
                    raise Exception(f"RiceSFP for {self.module.water_management_type_before_cultivation_wo} does not exist for without scenario. Please provide Tier 2 values.")

            try:
                self.sfo_wo_default = ipcc.RiceSFO.objects.get(organic_amendment_type=self.module.organic_amendment_type_wo)
            except ipcc.RiceSFO.DoesNotExist:
                if self.module.sfo_t2_wo is None:
                    raise Exception(f"RiceSFO for {self.module.organic_amendment_type_wo} does not exist for without scenario. Please provide Tier 2 values.")

        if self.module.is_ready() and calculate:
            self.calculate()
            self.efi_start_default.value = getattr(self.math_start_w, "adjusted_daily_ef_methane_tier_2_default", 0) or getattr(self.math_start_wo, "adjusted_daily_ef_methane_tier_2_default", 0)
            self.efi_w_default.value = getattr(self.math_w, "adjusted_daily_ef_methane_tier_2_default", 0)
            self.efi_wo_default.value = getattr(self.math_wo, "adjusted_daily_ef_methane_tier_2_default", 0)
            self.straw_burned_start_default.value = getattr(self.math_start_w, "straw_tonnes_tier_2_default", 0) or getattr(self.math_start_wo, "straw_tonnes_tier_2_default", 0)
            self.straw_burned_w_default.value = getattr(self.math_w, "straw_tonnes_tier_2_default", 0)
            self.straw_burned_wo_default.value = getattr(self.math_wo, "straw_tonnes_tier_2_default", 0)
            self.sfo_start_default.value = getattr(self.math_start_w, "SFo_tier_2_default", 0) or getattr(self.math_start_wo, "SFo_tier_2_default", 0)
            self.sfo_w_default.value = getattr(self.math_w, "SFo_tier_2_default", 0)
            self.sfo_wo_default.value = getattr(self.math_wo, "SFo_tier_2_default", 0)

        try:
            self.efc_default = ipcc.RiceDefaultEmissionFactor.objects.get(continent=self.region)
        except ipcc.RiceDefaultEmissionFactor.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "efc_t2")
            if missing_scenarios:
                raise Exception(f"RiceDefaultEmissionFactor for {self.region.name} does not exist. Please provide Tier 2 values for scenarios: {', '.join(missing_scenarios)}")

        try:
            self.yield_default = ipcc.RiceYield.objects.get(continent=self.region)
        except ipcc.RiceYield.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "crop_yield_t2")
            if missing_scenarios:
                raise Exception(f"RiceYield for {self.region.name} does not exist. Please provide Tier 2 values for scenarios: {', '.join(missing_scenarios)}")

        lut_name_rice_flt = {"land_use_type__name": "Rice"}

        try:
            self.n_estimation_factor_default = ipcc.CropNitrousEstimationDefaultFactor.objects.get(**lut_name_rice_flt)
        except ipcc.CropNitrousEstimationDefaultFactor.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "rice_straw_t2")
            if missing_scenarios:
                raise Exception(f"Default nitrous estimation factor is not defined for rice. Please provide Tier 2 values for scenarios: {', '.join(missing_scenarios)}")

        self.burning_emission_factor_default = utils.get_or_raise(ipcc.BurningEmissionFactor, {"category__name": "Agricultural residues"}, "Burning emission factor is not defined for agricultural residues")
        self.rice_cf_default = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_name_rice_flt, "Fires combustion factor is not defined for rice")

    def calculate(self, aggregate_by=BreakdownTypes.TOTAL) -> list[Result]:
        # If it's a minor season, use the parent module
        module_for_checks = getattr(self.module, "parent", self.module)
        is_minor_season = self.module.is_minor_season()

        if is_minor_season:
            self.module_start = self.module_w = self.module_wo = self.module.parent
            self.luc = self.module.parent.land_use_change
            if self.luc:
                self.module_start, self.module_w, self.module_wo = self.luc.get_modules()

        self.get_defaults()

        if module_for_checks.is_start():
            log.debug("Start")
            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "EFc_ref": self.efc_default.value,
                "EFc_tier_2": self.module.efc_t2_start,
                "SFw_ref": self.sfw_start_default.value,
                "SFw_tier_2": self.module.sfw_t2_start,
                "SFp_ref": self.sfp_start_default.value,
                "SFp_tier_2": self.module.sfp_t2_start,
                "cfoa": self.sfo_start_default.value,
                "SFo_tier_2": self.module.sfo_t2_start,
                "adjusted_daily_ef_methane_tier_2": self.module.efi_t2_start,
                "yield_ref": self.yield_default.value,
                "yield_tier_2": self.module.crop_yield_t2_start,
                "rice_slope": self.n_estimation_factor_default.slope,
                "rice_intercept": self.n_estimation_factor_default.intercept,
                "straw_tonnes_tier_2": self.module.rice_straw_t2_start,
                "methane_ef": self.burning_emission_factor_default.ch4,
                "rice_cf": self.rice_cf_default.value,
                "nitrous_ef": self.burning_emission_factor_default.n2o,
                "nitrous_constant": self.project.gwp.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.activity.change_rate.name,
                "methane_constant": self.project.gwp.ch4,
                "cultivation_period_ref": self.efc_default.cultivation_period,
                "cultivation_period_tier_2": self.module.cultivation_period_t2_start,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": getattr(self.module, "soc_t2_start", None),
                "soc_end_tier_2": getattr(self.module, "soc_t2_w", None),
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module.fmg_t2_start,
                "fmg_end_tier_2": self.module.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module.flu_t2_start,
                "flu_end_tier_2": self.module.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module.fi_t2_start,
                "fi_end_tier_2": self.module.fi_t2_w,
                "calculate_soc_som": True,
                "straw_burnt": self.module.organic_amendment_type_start.name == "Straw Burnt",
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "calculate_biomass": self.calculate_biomass_start_w,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
                "is_minor_season": is_minor_season,
            }

            self.math_start_w = MathFloodedRice(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "EFc_ref": self.efc_default.value,
                "EFc_tier_2": self.module.efc_t2_start,
                "SFw_ref": self.sfw_start_default.value,
                "SFw_tier_2": self.module.sfw_t2_start,
                "SFp_ref": self.sfp_start_default.value,
                "SFp_tier_2": self.module.sfp_t2_start,
                "cfoa": self.sfo_start_default.value,
                "SFo_tier_2": self.module.sfo_t2_start,
                "adjusted_daily_ef_methane_tier_2": self.module.efi_t2_start,
                "yield_ref": self.yield_default.value,
                "yield_tier_2": self.module.crop_yield_t2_start,
                "rice_slope": self.n_estimation_factor_default.slope,
                "rice_intercept": self.n_estimation_factor_default.intercept,
                "straw_tonnes_tier_2": self.module.rice_straw_t2_start,
                "methane_ef": self.burning_emission_factor_default.ch4,
                "rice_cf": self.rice_cf_default.value,
                "nitrous_ef": self.burning_emission_factor_default.n2o,
                "nitrous_constant": self.project.gwp.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.activity.change_rate.name,
                "methane_constant": self.project.gwp.ch4,
                "cultivation_period_ref": self.efc_default.cultivation_period,
                "cultivation_period_tier_2": self.module.cultivation_period_t2_start,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": getattr(self.module, "soc_t2_start", None),
                "soc_end_tier_2": getattr(self.module, "soc_t2_wo", None),
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module.fmg_t2_start,
                "fmg_end_tier_2": self.module.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module.flu_t2_start,
                "flu_end_tier_2": self.module.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module.fi_t2_start,
                "fi_end_tier_2": self.module.fi_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_WO,
                "straw_burnt": self.module.organic_amendment_type_start.name == "Straw Burnt",
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "calculate_biomass": self.calculate_biomass_start_wo,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
                "is_minor_season": is_minor_season,
            }

            self.math_start_wo = MathFloodedRice(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module_for_checks.is_with():
            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "EFc_ref": self.efc_default.value,
                "EFc_tier_2": self.module.efc_t2_w,
                "SFw_ref": self.sfw_w_default.value,
                "SFw_tier_2": self.module.sfw_t2_w,
                "SFp_ref": self.sfp_w_default.value,
                "SFp_tier_2": self.module.sfp_t2_w,
                "cfoa": self.sfo_w_default.value,
                "SFo_tier_2": self.module.sfo_t2_w,
                "adjusted_daily_ef_methane_tier_2": self.module.efi_t2_w,
                "yield_ref": self.yield_default.value,
                "yield_tier_2": self.module.crop_yield_t2_w,
                "rice_slope": self.n_estimation_factor_default.slope,
                "rice_intercept": self.n_estimation_factor_default.intercept,
                "straw_tonnes_tier_2": self.module.rice_straw_t2_w,
                "methane_ef": self.burning_emission_factor_default.ch4,
                "rice_cf": self.rice_cf_default.value,
                "nitrous_ef": self.burning_emission_factor_default.n2o,
                "nitrous_constant": self.project.gwp.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.activity.change_rate.name,
                "methane_constant": self.project.gwp.ch4,
                "cultivation_period_ref": self.efc_default.cultivation_period,
                "cultivation_period_tier_2": self.module.cultivation_period_t2_w,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": getattr(self.module, "soc_t2_start", None),
                "soc_end_tier_2": getattr(self.module, "soc_t2_w", None),
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module.fmg_t2_start,
                "fmg_end_tier_2": self.module.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module.flu_t2_start,
                "flu_end_tier_2": self.module.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module.fi_t2_start,
                "fi_end_tier_2": self.module.fi_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_W,
                "straw_burnt": self.module.organic_amendment_type_w.name == "Straw Burnt",
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "calculate_biomass": self.calculate_biomass_w,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
                "is_minor_season": is_minor_season,
            }

            self.math_w = MathFloodedRice(**self.inputs_w)
            self.math_w.calculate_emissions()

        if module_for_checks.is_without():
            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "EFc_ref": self.efc_default.value,
                "EFc_tier_2": self.module.efc_t2_wo,
                "SFw_ref": self.sfw_wo_default.value,
                "SFw_tier_2": self.module.sfw_t2_wo,
                "SFp_ref": self.sfp_wo_default.value,
                "SFp_tier_2": self.module.sfp_t2_wo,
                "cfoa": self.sfo_wo_default.value,
                "SFo_tier_2": self.module.sfo_t2_wo,
                "adjusted_daily_ef_methane_tier_2": self.module.efi_t2_wo,
                "yield_ref": self.yield_default.value,
                "yield_tier_2": self.module.crop_yield_t2_wo,
                "rice_slope": self.n_estimation_factor_default.slope,
                "rice_intercept": self.n_estimation_factor_default.intercept,
                "straw_tonnes_tier_2": self.module.rice_straw_t2_wo,
                "methane_ef": self.burning_emission_factor_default.ch4,
                "rice_cf": self.rice_cf_default.value,
                "nitrous_ef": self.burning_emission_factor_default.n2o,
                "nitrous_constant": self.project.gwp.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.activity.change_rate.name,
                "methane_constant": self.project.gwp.ch4,
                "cultivation_period_ref": self.efc_default.cultivation_period,
                "cultivation_period_tier_2": self.module.cultivation_period_t2_wo,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": getattr(self.module, "soc_t2_start", None),
                "soc_end_tier_2": getattr(self.module, "soc_t2_wo", None),
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module.fmg_t2_start,
                "fmg_end_tier_2": self.module.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module.flu_t2_start,
                "flu_end_tier_2": self.module.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module.fi_t2_start,
                "fi_end_tier_2": self.module.fi_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_WO,
                "straw_burnt": self.module.organic_amendment_type_wo.name == "Straw Burnt",
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "calculate_biomass": self.calculate_biomass_wo,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": self.module_start.get_biomass_t2(utils.ScenarioTypes.START),
                "biomass_end_tier_2": self.module_wo.get_biomass_t2(utils.ScenarioTypes.WITHOUT),
                "is_minor_season": is_minor_season,
            }

            self.math_wo = MathFloodedRice(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_start_w.plot_emissions_and_aggregate_by_activity("flooded_rice_start_w")
            self.results_start_wo.plot_emissions_and_aggregate_by_activity("flooded_rice_start_wo")
            self.results_w.plot_emissions_and_aggregate_by_activity("flooded_rice_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("flooded_rice_wo")

        results_tuple = (self.results_w + self.results_start_w, self.results_wo + self.results_start_wo)

        return results_tuple


class FloodedRiceCalculator(BaseCalculator):
    """
    Calculator for flooded rice.
    """

    def calculate(self) -> Result:
        module: FloodedRice = self.data
        self.results_w = MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        r_w, r_wo = FloodedRiceSeasonCalculator(module).calculate()

        self.results_w += r_w
        self.results_wo += r_wo

        for season in module.minor_seasons.all():
            r_w, r_wo = FloodedRiceSeasonCalculator(season).calculate()
            self.results_w += r_w
            self.results_wo += r_wo

        return (self.results_w, self.results_wo)

    def get_defaults(self, calculate=False) -> dict:
        FloodedRiceSeasonCalculator(self.module).get_defaults(calculate=calculate)


class GrasslandCalculator(LandModuleCalculator):
    """
    Calculator for grassland.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.ef: SimpleNamespace | ipcc.BurningEmissionFactor = SimpleNamespace(value=0)
        self.biomass: SimpleNamespace | ipcc.GrasslandBiomass = SimpleNamespace(value=0)
        self.cf: SimpleNamespace | GrasslandParameter = SimpleNamespace(value=0)

    def get_defaults(self, calculate=False):
        super().get_defaults(calculate)

        module: Grassland = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        self.ef = utils.get_or_raise(ipcc.BurningEmissionFactor, {"category__name": "Savanna and grassland"}, "Burning emission factor for savanna and grassland does not exist")

        self.biomass = ipcc.GrasslandBiomass.objects.filter(climate=project.climate, moisture=project.moisture).first()
        if self.biomass is None or self.biomass.agb_t_c_ha is None:
            # NOTE: Right now this is the only check that's needed, as BGB is not used in the calculations
            missing_scenarios = utils.find_empty_scenarios(module, "agb_t2")
            if missing_scenarios:
                raise Exception(f"AGB for {project.climate.name} climate and {project.moisture.name} moisture does not exist. Please provide Tier 2 values for scenarios: {', '.join(missing_scenarios)}")

        try:
            self.cf = GrasslandParameter.objects.get(name="default_combustion_factor")
        except GrasslandParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(module, "combustion_factor_t2")
            if missing_scenarios:
                raise Exception(f"Default combustion factor does not exist. Please provide Tier 2 values for scenarios: {', '.join(missing_scenarios)}")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Grassland module.
        """
        log.debug("START GrasslandCalculator.calculate")

        module: Grassland = self.module
        activity: Activity = module.activity
        project: Project = activity.project

        self.get_defaults()

        if module.is_start():
            log.debug("Start")
            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": project.gwp.n2o,
                "methane_constant": project.gwp.ch4,
                "fire_interval": module.fire_periodicity_start,
                "fire_used": module.is_fire_used_start,
                "methane_ef": self.ef.ch4,
                "nitrous_ef": self.ef.n2o,
                "agb_ref": self.biomass.agb_t_c_ha,
                "agb_tier_2": module.agb_t2_start,
                "cf_ref": self.cf.value,
                "cf_tier_2": module.combustion_factor_t2_start,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": module.soc_t2_start,
                "soc_end_tier_2": module.soc_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_W,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": module.fmg_t2_start,
                "fmg_end_tier_2": module.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": module.flu_t2_start,
                "flu_end_tier_2": module.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": module.fi_t2_start,
                "fi_end_tier_2": module.fi_t2_w,
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "calculate_biomass": self.calculate_biomass_start_w,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
                "fire_impact": module.fire_impact_start,
            }

            log.debug("Inputs start w: %s", self.inputs_start_w)

            self.math_start_w = MathGrassland(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": project.gwp.n2o,
                "methane_constant": project.gwp.ch4,
                "fire_interval": module.fire_periodicity_start,
                "fire_used": module.is_fire_used_start,
                "methane_ef": self.ef.ch4,
                "nitrous_ef": self.ef.n2o,
                "agb_ref": self.biomass.agb_t_c_ha,
                "agb_tier_2": module.agb_t2_start,
                "cf_ref": self.cf.value,
                "cf_tier_2": module.combustion_factor_t2_start,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": module.soc_t2_start,
                "soc_end_tier_2": module.soc_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_WO,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": module.fmg_t2_start,
                "fmg_end_tier_2": module.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": module.flu_t2_start,
                "flu_end_tier_2": module.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": module.fi_t2_start,
                "fi_end_tier_2": module.fi_t2_wo,
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "calculate_biomass": self.calculate_biomass_start_wo,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
                "fire_impact": module.fire_impact_start,
            }

            log.debug("Inputs start wo: %s", self.inputs_start_wo)

            self.math_start_wo = MathGrassland(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module.is_with():
            log.debug("With")

            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": project.gwp.n2o,
                "methane_constant": project.gwp.ch4,
                "fire_interval": module.fire_periodicity_w,
                "fire_used": module.is_fire_used_w,
                "methane_ef": self.ef.ch4,
                "nitrous_ef": self.ef.n2o,
                "agb_ref": self.biomass.agb_t_c_ha,
                "agb_tier_2": module.agb_t2_w,
                "cf_ref": self.cf.value,
                "cf_tier_2": module.combustion_factor_t2_w,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": module.soc_t2_start,
                "soc_end_tier_2": module.soc_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_W,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": module.fmg_t2_start,
                "fmg_end_tier_2": module.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": module.flu_t2_start,
                "flu_end_tier_2": module.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": module.fi_t2_start,
                "fi_end_tier_2": module.fi_t2_w,
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "calculate_biomass": self.calculate_biomass_w,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
                "fire_impact": module.fire_impact_w,
            }

            log.debug("Inputs w: %s", self.inputs_w)

            self.math_w = MathGrassland(**self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            log.debug("Without")

            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": project.gwp.n2o,
                "methane_constant": project.gwp.ch4,
                "fire_interval": module.fire_periodicity_wo,
                "fire_used": module.is_fire_used_wo,
                "methane_ef": self.ef.ch4,
                "nitrous_ef": self.ef.n2o,
                "agb_ref": self.biomass.agb_t_c_ha,
                "agb_tier_2": module.agb_t2_wo,
                "cf_ref": self.cf.value,
                "cf_tier_2": module.combustion_factor_t2_wo,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": module.soc_t2_start,
                "soc_end_tier_2": module.soc_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_WO,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": module.fmg_t2_start,
                "fmg_end_tier_2": module.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": module.flu_t2_start,
                "flu_end_tier_2": module.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": module.fi_t2_start,
                "fi_end_tier_2": module.fi_t2_wo,
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "calculate_biomass": self.calculate_biomass_wo,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
                "fire_impact": module.fire_impact_wo,
            }

            log.debug("Inputs wo: %s", self.inputs_wo)

            self.math_wo = MathGrassland(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_start_w.plot_emissions_and_aggregate_by_activity("grassland_start_w")
            self.results_start_wo.plot_emissions_and_aggregate_by_activity("grassland_start_wo")
            self.results_w.plot_emissions_and_aggregate_by_activity("grassland_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("grassland_wo")

        log.debug("END GrasslandCalculator.calculate")
        return (self.results_w + self.results_start_w, self.results_wo + self.results_start_wo)


class SmallFisheryCalculator(BaseCalculator):
    """
    Calculator for small fishery.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.module: SmallFishery

        self.energy_ef_default: ipcc.EnergyDefaultEmissionFactor = None
        self.energy_ef_default_co2: float = 0
        self.energy_ef_default_ch4: float = 0
        self.energy_ef_default_n2o: float = 0
        self.electricity_emission: ipcc.ElectricityEmission = None
        self.lost_refrigerant_default: float = 0
        self.tonnes_ice_default: float = 0
        self.kw_tonnes: float = 0

        self.fui_start: ipcc.SmallFisheryFUI = None
        self.fui_w: ipcc.SmallFisheryFUI = None
        self.fui_wo: ipcc.SmallFisheryFUI = None

        self.relevant_scenarios = self.module.get_relevant_scenarios()

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        try:
            self.energy_ef_default = ipcc.EnergyDefaultEmissionFactor.objects.filter(fuel_type__fuel_use_type__name__contains="Off-Road")
            # Average of all default emission factors for gasoil/diesel
            self.energy_ef_default_co2 = sum([ef.co2 for ef in self.energy_ef_default]) / len(self.energy_ef_default)
            self.energy_ef_default_ch4 = sum([ef.ch4 for ef in self.energy_ef_default]) / len(self.energy_ef_default)
            self.energy_ef_default_n2o = sum([ef.n2o for ef in self.energy_ef_default]) / len(self.energy_ef_default)
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            raise ValueError("Default emission factors for off-road diesel do not exist")

        try:
            self.lost_refrigerant_default = SmallFisheryParameter.objects.get(name="lost_refrigerant_default").value
        except SmallFisheryParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "refrigerant_lost_per_tonne_t2")
            if missing_scenarios:
                raise ValueError(f"Default lost refrigerant does not exist. Please provide a tier 2 value for lost refrigerant for scenarios: {', '.join(missing_scenarios)}")

        try:
            self.tonnes_ice_default = SmallFisheryParameter.objects.get(name="tonnes_ice_default").value
        except SmallFisheryParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "tonnes_of_ice_t2")
            if missing_scenarios:
                raise ValueError(f"Default tonnes of ice does not exist. Please provide a tier 2 value for tonnes of ice for scenarios: {', '.join(missing_scenarios)}")

        try:
            self.kw_tonnes = SmallFisheryParameter.objects.get(name="kw_tonnes").value
        except SmallFisheryParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "inshore_ice_production_kwh_per_tonne_t2")
            if missing_scenarios:
                raise ValueError(f"Default kw per tonne does not exist. Please provide a tier 2 value for kw per tonne for scenarios: {', '.join(missing_scenarios)}")

        try:
            self.fui_start = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=self.module.fishery_type, gear_type=self.module.gear_type_start)
        except ipcc.SmallFisheryFUI.DoesNotExist:
            if self.module.fui_t2_start is None:
                raise ValueError("Default FUI does not exist. Please provide a tier 2 value for FUI for the relevant scenarios.")

        try:
            self.fui_w = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=self.module.fishery_type, gear_type=self.module.gear_type_w)
        except ipcc.SmallFisheryFUI.DoesNotExist:
            if self.module.fui_t2_w is None:
                raise ValueError("Default FUI does not exist. Please provide a tier 2 value for FUI for the relevant scenarios.")

        try:
            self.fui_wo = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=self.module.fishery_type, gear_type=self.module.gear_type_wo)
        except ipcc.SmallFisheryFUI.DoesNotExist:
            if self.module.fui_t2_wo is None:
                raise ValueError("Default FUI does not exist. Please provide a tier 2 value for FUI for the relevant scenarios.")

        try:
            self.electricity_emission = ipcc.ElectricityEmission.objects.get(country=self.country)
        except ipcc.ElectricityEmission.DoesNotExist:
            raise ValueError(f"Electricity emission for {self.country.name} does not exist")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single SmallFishery module.
        """
        log.debug("START SmallFisheryCalculator.calculate")

        self.get_defaults()

        if self.module.is_with():
            log.debug("IS WITH")
            self.inputs_w = {
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.module.activity.change_rate.name,
                "catch_start": self.module.total_catch_yr_start,
                "catch_end": self.module.total_catch_yr_w,
                "ef_diesel_default_co2": self.energy_ef_default_co2,
                "ef_diesel_co2_start_tier_2": self.module.energy_ef_co2_t2_start,
                "ef_diesel_co2_end_tier_2": self.module.energy_ef_co2_t2_w,
                "ef_diesel_default_n2o": self.energy_ef_default_n2o,
                "ef_diesel_n2o_start_tier_2": self.module.energy_ef_n2o_t2_start,
                "ef_diesel_n2o_end_tier_2": self.module.energy_ef_n2o_t2_w,
                "ef_diesel_default_ch4": self.energy_ef_default_ch4,
                "ef_diesel_ch4_start_tier_2": self.module.energy_ef_ch4_t2_start,
                "ef_diesel_ch4_end_tier_2": self.module.energy_ef_ch4_t2_w,
                "fui_default_start": self.fui_start,
                "fui_default_end": self.fui_w,
                "fui_start_tier_2": self.module.fui_t2_start,
                "fui_end_tier_2": self.module.fui_t2_w,
                "gwp_refrigerant_default": self.module.refrigerant_gwp,
                "gwp_refrigerant_start_tier_2": self.module.refrigerant_gwp_t2_start,
                "gwp_refrigerant_end_tier_2": self.module.refrigerant_gwp_t2_w,
                "quantity_lost_refrigerant_default": self.lost_refrigerant_default,
                "quantity_lost_refrigerant_start_tier_2": self.module.refrigerant_lost_per_tonne_t2_start,
                "quantity_lost_refrigerant_end_tier_2": self.module.refrigerant_lost_per_tonne_t2_w,
                "percentage_refrigerant_start": self.module.refrigerant_pc_start,
                "percentage_refrigerant_end": self.module.refrigerant_pc_w,
                "tonnes_ice_default": self.tonnes_ice_default,
                "tonnes_ice_start_tier_2": self.module.tonnes_of_ice_t2_start,
                "tonnes_ice_end_tier_2": self.module.tonnes_of_ice_t2_w,
                "kwh_ice_per_tonne_default": self.kw_tonnes,
                "kwh_ice_per_tonne_start_tier_2": self.module.inshore_ice_production_kwh_per_tonne_t2_start,
                "kwh_ice_per_tonne_end_tier_2": self.module.inshore_ice_production_kwh_per_tonne_t2_w,
                "operating_margin": self.electricity_emission.operating_margin,
                "percentage_ice_start": self.module.ice_preserved_catch_pc_start,
                "percentage_ice_end": self.module.ice_preserved_catch_pc_w,
                "delay": self.activity.delay,
            }
            log.debug("Inputs with: %s", self.inputs_w)

            self.math_w = MathFishery(**self.inputs_w)
            self.math_w.calculate_emissions()

        if self.module.is_without():
            log.debug("IS WITHOUT")
            self.inputs_wo = {
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.module.activity.change_rate.name,
                "catch_start": self.module.total_catch_yr_start,
                "catch_end": self.module.total_catch_yr_wo,
                "ef_diesel_default_co2": self.energy_ef_default_co2,
                "ef_diesel_co2_start_tier_2": self.module.energy_ef_co2_t2_start,
                "ef_diesel_co2_end_tier_2": self.module.energy_ef_co2_t2_wo,
                "ef_diesel_default_n2o": self.energy_ef_default_n2o,
                "ef_diesel_n2o_start_tier_2": self.module.energy_ef_n2o_t2_start,
                "ef_diesel_n2o_end_tier_2": self.module.energy_ef_n2o_t2_wo,
                "ef_diesel_default_ch4": self.energy_ef_default_ch4,
                "ef_diesel_ch4_start_tier_2": self.module.energy_ef_ch4_t2_start,
                "ef_diesel_ch4_end_tier_2": self.module.energy_ef_ch4_t2_wo,
                "fui_default_start": self.fui_start,
                "fui_default_end": self.fui_wo,
                "fui_start_tier_2": self.module.fui_t2_start,
                "fui_end_tier_2": self.module.fui_t2_wo,
                "gwp_refrigerant_default": self.module.refrigerant_gwp,
                "gwp_refrigerant_start_tier_2": self.module.refrigerant_gwp_t2_start,
                "gwp_refrigerant_end_tier_2": self.module.refrigerant_gwp_t2_wo,
                "quantity_lost_refrigerant_default": self.lost_refrigerant_default,
                "quantity_lost_refrigerant_start_tier_2": self.module.refrigerant_lost_per_tonne_t2_start,
                "quantity_lost_refrigerant_end_tier_2": self.module.refrigerant_lost_per_tonne_t2_wo,
                "percentage_refrigerant_start": self.module.refrigerant_pc_start,
                "percentage_refrigerant_end": self.module.refrigerant_pc_wo,
                "tonnes_ice_default": self.tonnes_ice_default,
                "tonnes_ice_start_tier_2": self.module.tonnes_of_ice_t2_start,
                "tonnes_ice_end_tier_2": self.module.tonnes_of_ice_t2_wo,
                "kwh_ice_per_tonne_default": self.kw_tonnes,
                "kwh_ice_per_tonne_start_tier_2": self.module.inshore_ice_production_kwh_per_tonne_t2_start,
                "kwh_ice_per_tonne_end_tier_2": self.module.inshore_ice_production_kwh_per_tonne_t2_wo,
                "operating_margin": self.electricity_emission.operating_margin,
                "percentage_ice_start": self.module.ice_preserved_catch_pc_start,
                "percentage_ice_end": self.module.ice_preserved_catch_pc_wo,
                "delay": self.activity.delay,
            }
            log.debug("Inputs without: %s", self.inputs_wo)

            self.math_wo = MathFishery(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_w.plot_emissions_and_aggregate_by_activity("small_fishery_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("small_fishery_wo")

        log.debug("END SmallFisheryCalculator.calculate")
        return (self.results_w, self.results_wo)


class LargeFisheryCalculator(BaseCalculator):
    """
    Calculator for large fishery.
    """

    def init(self, input) -> None:
        super().init(input)

        self.module: LargeFishery

        self.energy_ef_default: ipcc.EnergyDefaultEmissionFactor = None
        self.energy_ef_default_co2: float = 0
        self.energy_ef_default_ch4: float = 0
        self.energy_ef_default_n2o: float = 0
        self.fui_default_start: ipcc.LargeFisheryFUI = None
        self.fui_default_w: ipcc.LargeFisheryFUI = None
        self.fui_default_wo: ipcc.LargeFisheryFUI = None
        self.lost_refrigerant_default: float = 0
        self.tonnes_ice_default: float = 0
        self.kw_tonnes: float = 0
        self.electricity_country: Country = None
        self.electricity_emission: ipcc.ElectricityEmission = None

        self.relevant_scenarios = self.module.get_relevant_scenarios()

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        try:
            self.energy_ef_default = ipcc.EnergyDefaultEmissionFactor.objects.filter(fuel_type__fuel_use_type__name__contains="Off-Road")
            # Average of all default emission factors for gasoil/diesel
            self.energy_ef_default_co2 = sum([ef.co2 for ef in self.energy_ef_default]) / len(self.energy_ef_default)
            self.energy_ef_default_ch4 = sum([ef.ch4 for ef in self.energy_ef_default]) / len(self.energy_ef_default)
            self.energy_ef_default_n2o = sum([ef.n2o for ef in self.energy_ef_default]) / len(self.energy_ef_default)
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            missing_scenarios_co2 = utils.find_empty_scenarios(self.module, "energy_ef_co2_t2")
            missing_scenarios_ch4 = utils.find_empty_scenarios(self.module, "energy_ef_ch4_t2")
            missing_scenarios_n2o = utils.find_empty_scenarios(self.module, "energy_ef_n2o_t2")

            if missing_scenarios_co2:
                raise ValueError(f"Default emission factors for off-road diesel do not exist. Please provide a tier 2 value for CO2 emission factor for scenarios: {', '.join(missing_scenarios_co2)}")
            if missing_scenarios_ch4:
                raise ValueError(f"Default emission factors for off-road diesel do not exist. Please provide a tier 2 value for CH4 emission factor for scenarios: {', '.join(missing_scenarios_ch4)}")
            if missing_scenarios_n2o:
                raise ValueError(f"Default emission factors for off-road diesel do not exist. Please provide a tier 2 value for N2O emission factor for scenarios: {', '.join(missing_scenarios_n2o)}")

        try:
            self.fui_default_start = ipcc.LargeFisheryFUI.objects.get_value_or_average(fish_type=self.module.fish_type, gear_type=self.module.gear_type_start)
        except ipcc.LargeFisheryFUI.DoesNotExist:
            if self.module.fui_t2_start is None:
                raise ValueError(f"Default FUI for {self.module.fish_type.name} and {self.module.gear_type_start.name} does not exist. Please provide a tier 2 value for FUI for the relevant scenarios.")

        try:
            self.fui_default_w = ipcc.LargeFisheryFUI.objects.get_value_or_average(fish_type=self.module.fish_type, gear_type=self.module.gear_type_w)
        except ipcc.LargeFisheryFUI.DoesNotExist:
            if self.module.fui_t2_w is None:
                raise ValueError(f"Default FUI for {self.module.fish_type.name} and {self.module.gear_type_w.name} does not exist. Please provide a tier 2 value for FUI for the relevant scenarios.")

        try:
            self.fui_default_wo = ipcc.LargeFisheryFUI.objects.get_value_or_average(fish_type=self.module.fish_type, gear_type=self.module.gear_type_wo)
        except ipcc.LargeFisheryFUI.DoesNotExist:
            if self.module.fui_t2_wo is None:
                raise ValueError(f"Default FUI for {self.module.fish_type.name} and {self.module.gear_type_wo.name} does not exist. Please provide a tier 2 value for FUI for the relevant scenarios.")

        try:
            self.lost_refrigerant_default = LargeFisheryParameter.objects.get(name="lost_refrigerant_default").value
        except LargeFisheryParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "refrigerant_lost_per_tonne_t2")
            if missing_scenarios:
                raise ValueError(f"Default lost refrigerant does not exist. Please provide a tier 2 value for lost refrigerant for scenarios: {', '.join(missing_scenarios)}")

        try:
            self.tonnes_ice_default = LargeFisheryParameter.objects.get(name="tonnes_ice_default").value
        except LargeFisheryParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "tonnes_of_ice_t2")
            if missing_scenarios:
                raise ValueError(f"Default tonnes of ice does not exist. Please provide a tier 2 value for tonnes of ice for scenarios: {', '.join(missing_scenarios)}")

        try:
            self.kw_tonnes = LargeFisheryParameter.objects.get(name="kw_tonnes").value
        except LargeFisheryParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "inshore_ice_production_kwh_per_tonne_t2")
            if missing_scenarios:
                raise ValueError(f"Default kw per tonne does not exist. Please provide a tier 2 value for kw per tonne for scenarios: {', '.join(missing_scenarios)}")

        try:
            self.electricity_country = self.module.inshore_ice_production_country_t2 if self.module.inshore_ice_production_country_t2 else self.country
            self.electricity_emission = ipcc.ElectricityEmission.objects.get(country=self.electricity_country)
        except ipcc.ElectricityEmission.DoesNotExist:
            raise ValueError(f"Electricity emission for {self.electricity_country.name} does not exist")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single LargeFishery module.
        """
        log.debug("START LargeFisheryCalculator.calculate")

        self.get_defaults()

        if self.module.is_with():
            log.debug("IS WITH")
            self.inputs_w = {
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.module.activity.change_rate.name,
                "catch_start": self.module.total_catch_yr_start,
                "catch_end": self.module.total_catch_yr_w,
                "ef_diesel_default_co2": self.energy_ef_default_co2,
                "ef_diesel_co2_start_tier_2": self.module.energy_ef_co2_t2_start,
                "ef_diesel_co2_end_tier_2": self.module.energy_ef_co2_t2_w,
                "ef_diesel_default_n2o": self.energy_ef_default_n2o,
                "ef_diesel_n2o_start_tier_2": self.module.energy_ef_n2o_t2_start,
                "ef_diesel_n2o_end_tier_2": self.module.energy_ef_n2o_t2_w,
                "ef_diesel_default_ch4": self.energy_ef_default_ch4,
                "ef_diesel_ch4_start_tier_2": self.module.energy_ef_ch4_t2_start,
                "ef_diesel_ch4_end_tier_2": self.module.energy_ef_ch4_t2_w,
                "fui_default_start": self.fui_default_start,
                "fui_default_end": self.fui_default_w,
                "fui_start_tier_2": self.module.fui_t2_start,
                "fui_end_tier_2": self.module.fui_t2_w,
                "gwp_refrigerant_default": self.module.refrigerant_gwp,
                "gwp_refrigerant_start_tier_2": self.module.refrigerant_gwp_t2_start,
                "gwp_refrigerant_end_tier_2": self.module.refrigerant_gwp_t2_w,
                "quantity_lost_refrigerant_default": self.lost_refrigerant_default,
                "quantity_lost_refrigerant_start_tier_2": self.module.refrigerant_lost_per_tonne_t2_start,
                "quantity_lost_refrigerant_end_tier_2": self.module.refrigerant_lost_per_tonne_t2_w,
                "percentage_refrigerant_start": self.module.refrigerant_pc_start,
                "percentage_refrigerant_end": self.module.refrigerant_pc_w,
                "tonnes_ice_default": self.tonnes_ice_default,
                "tonnes_ice_start_tier_2": self.module.tonnes_of_ice_t2_start,
                "tonnes_ice_end_tier_2": self.module.tonnes_of_ice_t2_w,
                "kwh_ice_per_tonne_default": self.kw_tonnes,
                "kwh_ice_per_tonne_start_tier_2": self.module.inshore_ice_production_kwh_per_tonne_t2_start,
                "kwh_ice_per_tonne_end_tier_2": self.module.inshore_ice_production_kwh_per_tonne_t2_w,
                "operating_margin": self.electricity_emission.operating_margin,
                "percentage_ice_start": self.module.ice_preserved_catch_pc_start,
                "percentage_ice_end": self.module.ice_preserved_catch_pc_w,
                "delay": self.activity.delay,
            }
            log.debug("Inputs with: %s", self.inputs_w)

            self.math_w = MathFishery(**self.inputs_w)
            self.math_w.calculate_emissions()

        if self.module.is_without():
            log.debug("IS WITHOUT")
            self.inputs_wo = {
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.module.activity.change_rate.name,
                "catch_start": self.module.total_catch_yr_start,
                "catch_end": self.module.total_catch_yr_wo,
                "ef_diesel_default_co2": self.energy_ef_default_co2,
                "ef_diesel_co2_start_tier_2": self.module.energy_ef_co2_t2_start,
                "ef_diesel_co2_end_tier_2": self.module.energy_ef_co2_t2_w,
                "ef_diesel_default_n2o": self.energy_ef_default_n2o,
                "ef_diesel_n2o_start_tier_2": self.module.energy_ef_n2o_t2_start,
                "ef_diesel_n2o_end_tier_2": self.module.energy_ef_n2o_t2_w,
                "ef_diesel_default_ch4": self.energy_ef_default_ch4,
                "ef_diesel_ch4_start_tier_2": self.module.energy_ef_ch4_t2_start,
                "ef_diesel_ch4_end_tier_2": self.module.energy_ef_ch4_t2_w,
                "fui_default_start": self.fui_default_start,
                "fui_default_end": self.fui_default_wo,
                "fui_start_tier_2": self.module.fui_t2_start,
                "fui_end_tier_2": self.module.fui_t2_wo,
                "gwp_refrigerant_default": self.module.refrigerant_gwp,
                "gwp_refrigerant_start_tier_2": self.module.refrigerant_gwp_t2_start,
                "gwp_refrigerant_end_tier_2": self.module.refrigerant_gwp_t2_wo,
                "quantity_lost_refrigerant_default": self.lost_refrigerant_default,
                "quantity_lost_refrigerant_start_tier_2": self.module.refrigerant_lost_per_tonne_t2_start,
                "quantity_lost_refrigerant_end_tier_2": self.module.refrigerant_lost_per_tonne_t2_wo,
                "percentage_refrigerant_start": self.module.refrigerant_pc_start,
                "percentage_refrigerant_end": self.module.refrigerant_pc_wo,
                "tonnes_ice_default": self.tonnes_ice_default,
                "tonnes_ice_start_tier_2": self.module.tonnes_of_ice_t2_start,
                "tonnes_ice_end_tier_2": self.module.tonnes_of_ice_t2_wo,
                "kwh_ice_per_tonne_default": self.kw_tonnes,
                "kwh_ice_per_tonne_start_tier_2": self.module.inshore_ice_production_kwh_per_tonne_t2_start,
                "kwh_ice_per_tonne_end_tier_2": self.module.inshore_ice_production_kwh_per_tonne_t2_wo,
                "operating_margin": self.electricity_emission.operating_margin,
                "percentage_ice_start": self.module.ice_preserved_catch_pc_start,
                "percentage_ice_end": self.module.ice_preserved_catch_pc_wo,
                "delay": self.activity.delay,
            }
            log.debug("Inputs without: %s", self.inputs_wo)

            self.math_wo = MathFishery(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_w.plot_emissions_and_aggregate_by_activity("large_fishery_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("large_fishery_wo")

        results_tuple = (self.results_w, self.results_wo)

        log.debug("END LargeFisheryCalculator.calculate")
        return results_tuple


class AquacultureCalculator(BaseCalculator):
    """
    Calculator for aquaculture.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.ELECTRICITY_USED_DEFAULT = 0  # TODO: Add as database parameter
        self.NITROUS_EF_DEFAULT = 0
        self.FEED_EF_DEFAULT = 0

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: Aquaculture = self.data
        project: Project = module.activity.project

        try:
            self.ELECTRICITY_USED_DEFAULT = AquacultureParameter.objects.get(name="electricity_used_default").value
        except AquacultureParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(module, "electricity_used_t2")
            if missing_scenarios:
                raise ValueError(f"Default electricity used does not exist. Please provide a tier 2 value for electricity used for scenarios: {', '.join(missing_scenarios)}")

        try:
            self.NITROUS_EF_DEFAULT = AquacultureParameter.objects.get(name="nitrous_ef_default").value
        except AquacultureParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(module, "n2o_from_production_t2")
            if missing_scenarios:
                raise ValueError(f"Default nitrous emission factor does not exist. Please provide a tier 2 value for nitrous emission factor for scenarios: {', '.join(missing_scenarios)}")

        try:
            # TODO: This will now be used in the inputs module for feed
            self.FEED_EF_DEFAULT = AquacultureParameter.objects.get(name="feed_ef_default").value
        except AquacultureParameter.DoesNotExist:
            raise ValueError("Default feed emission factor does not exist")

        try:
            self.elec = ipcc.ElectricityEmission.objects.get(country=self.country)
        except ipcc.ElectricityEmission.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(module, "electricity_ef_t2")
            if missing_scenarios:
                raise ValueError(f"Electricity emission for {self.country.name} does not exist. Please provide a tier 2 value for electricity emission for scenarios: {', '.join(missing_scenarios)}")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Aquaculture module.
        """

        module: Aquaculture = self.data
        change_rate = module.activity.change_rate
        project: Project = module.activity.project

        self.get_defaults()

        if module.is_with():
            log.debug("IS WITH")
            self.inputs_w = {
                "production_start": module.annual_production_start,
                "production_end": module.annual_production_w,
                "nitrous_ef_default": self.NITROUS_EF_DEFAULT,
                "nitrous_ef_start_tier_2": module.n2o_from_production_t2_start,
                "nitrous_ef_end_tier_2": module.n2o_from_production_t2_w,
                "nitrous_constant": project.gwp.n2o,
                "electricity_used_default": self.ELECTRICITY_USED_DEFAULT,
                "electricity_used_start_tier_2": module.electricity_used_t2_start,
                "electricity_used_end_tier_2": module.electricity_used_t2_w,
                "ef_electricity_default": self.elec.operating_margin,
                "ef_electricity_start_tier_2": module.electricity_ef_t2_start,
                "ef_electricity_end_tier_2": module.electricity_ef_t2_w,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "delay": self.activity.delay,
            }
            log.debug("Inputs with: %s", self.inputs_w)

            self.math_w = MathAquaculture(**self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            log.debug("IS WITHOUT")
            self.inputs_wo = {
                "production_start": module.annual_production_start,
                "production_end": module.annual_production_wo,
                "nitrous_ef_default": self.NITROUS_EF_DEFAULT,
                "nitrous_ef_start_tier_2": module.n2o_from_production_t2_start,
                "nitrous_ef_end_tier_2": module.n2o_from_production_t2_wo,
                "nitrous_constant": project.gwp.n2o,
                "electricity_used_default": self.ELECTRICITY_USED_DEFAULT,
                "electricity_used_start_tier_2": module.electricity_used_t2_start,
                "electricity_used_end_tier_2": module.electricity_used_t2_wo,
                "ef_electricity_default": self.elec.operating_margin,
                "ef_electricity_start_tier_2": module.electricity_ef_t2_start,
                "ef_electricity_end_tier_2": module.electricity_ef_t2_w,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "delay": self.activity.delay,
            }
            log.debug("Inputs without: %s", self.inputs_wo)

            self.math_wo = MathAquaculture(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w, self.results_wo)

        return results_tuple


class InputCalculator(BaseCalculator):
    """
    Calculator for Inputs macromodule
    """

    def get_defaults(self, input: Module) -> dict:
        return super().get_defaults(input)

    def calculate(self) -> list[MathResult]:
        module: Input = self.data

        self.results_w = MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        entries = module.input_entries.all()
        for entry in entries:
            r_w, r_wo = InputEntryCalculator(entry).calculate()

            self.results_w += r_w
            self.results_wo += r_wo

        return (self.results_w, self.results_wo)


class InputEntryCalculator(BaseCalculator):
    """
    Calculator for single input entries.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.module: InputEntry

        self.ref = SimpleNamespace(co2_multiplier=0, co2_emissions_multiplier=0, n2o_quantity_multiplier=0, n2o_emissions_multiplier=0, production_quantity_multiplier=0, production_emissions_multiplier=0)
        self.ef = SimpleNamespace(co2_value=0, n2o_value=0, co2_eq_value=0)

        self.needs_co2_ref = None
        self.needs_n2o_ref = None
        self.needs_co2_e_ref = None

    def get_defaults(self, calculate=False) -> dict:

        input_type: InputType = self.module.input_type

        self.needs_co2_ref = input_type.has_co2_emissions and not self.module.co2_emissions_t2
        self.needs_n2o_ref = input_type.has_n2o_emissions and not self.module.n2o_emissions_t2
        self.needs_co2_e_ref = input_type.has_co2_e_emissions and not self.module.co2_e_emissions_t2

        if self.module.status.name == "READY" and calculate:
            self.calculate()

        try:
            self.ref = ipcc.InputReference.objects.get(input_type=self.module.input_type)
        except ipcc.InputReference.DoesNotExist:
            raise ValueError(f"Reference for {self.module.input_type.name} does not exist.")

        self.ef = ipcc.InputEmissionFactor.objects.filter(input_type=self.module.input_type, climate=self.project.climate, moisture=self.project.moisture).first()

        if self.ef:
            if self.ef.co2_value is None and self.needs_co2_ref:
                raise ValueError(f"CO2 emission factor for {self.module.input_type.name} does not exist for {self.project.climate.name} and {self.project.moisture.name}. Please define tier 2 values.")
            if self.ef.n2o_value is None and self.needs_n2o_ref:
                raise ValueError(f"N2O emission factor for {self.module.input_type.name} does not exist for {self.project.climate.name} and {self.project.moisture.name}. Please define tier 2 values.")
            if self.ef.co2_eq_value is None and self.needs_co2_e_ref:
                raise ValueError(f"CO2-eq emission factor for {self.module.input_type.name} does not exist for {self.project.climate.name} and {self.project.moisture.name}. Please define tier 2 values.")
        else:
            if self.needs_co2_ref:
                raise ValueError(f"CO2 emission factor for {self.module.input_type.name} does not exist for {self.project.climate.name} and {self.project.moisture.name}. Please define tier 2 values.")
            if self.needs_n2o_ref:
                raise ValueError(f"N2O emission factor for {self.module.input_type.name} does not exist for {self.project.climate.name} and {self.project.moisture.name}. Please define tier 2 values.")
            if self.needs_co2_e_ref:
                raise ValueError(f"CO2-eq emission factor for {self.module.input_type.name} does not exist for {self.project.climate.name} and {self.project.moisture.name}. Please define tier 2 values.")

        self.math_w = None
        self.math_wo = None

    def calculate(self) -> list[Result]:
        self.get_defaults()

        self.inputs_w = {
            "unit_start": self.module.value_start,
            "unit_end": self.module.value_w,
            "rate_type": self.activity.change_rate.name,
            "ipcc_factor_co2": self.ef.co2_value if self.needs_co2_ref else 0,
            "tier_2_factor_co2": self.module.co2_emissions_t2,
            "unit_factor_co2": self.ref.co2_multiplier,
            "emissions_factor_co2": self.ref.co2_emissions_multiplier,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "ipcc_factor_n2o": self.ef.n2o_value if self.needs_n2o_ref else 0,
            "tier_2_factor_n2o": self.module.n2o_emissions_t2,
            "unit_factor_n2o": self.ref.n2o_quantity_multiplier,
            "emissions_factor_n2o": self.ref.n2o_emissions_multiplier,
            "ipcc_factor_eq": self.ef.co2_eq_value if self.needs_co2_e_ref else 0,
            "tier_2_factor_eq": self.module.co2_e_emissions_t2,
            "unit_factor_eq": self.ref.production_quantity_multiplier,
            "emissions_factor_eq": self.ref.production_emissions_multiplier,
            "delay": self.activity.delay,
        }
        log.debug("Inputs with: %s", self.inputs_w)

        self.math_w = MathInputs(**self.inputs_w)
        self.math_w.calculate_emissions()

        self.inputs_wo = {
            "unit_start": self.module.value_start,
            "unit_end": self.module.value_wo,
            "rate_type": self.activity.change_rate.name,
            "ipcc_factor_co2": self.ef.co2_value if self.needs_co2_ref else 0,
            "tier_2_factor_co2": self.module.co2_emissions_t2,
            "unit_factor_co2": self.ref.co2_multiplier,
            "emissions_factor_co2": self.ref.co2_emissions_multiplier,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "ipcc_factor_n2o": self.ef.n2o_value if self.needs_n2o_ref else 0,
            "tier_2_factor_n2o": self.module.n2o_emissions_t2,
            "unit_factor_n2o": self.ref.n2o_quantity_multiplier,
            "emissions_factor_n2o": self.ref.n2o_emissions_multiplier,
            "ipcc_factor_eq": self.ef.co2_eq_value if self.needs_co2_e_ref else 0,
            "tier_2_factor_eq": self.module.co2_e_emissions_t2,
            "unit_factor_eq": self.ref.production_quantity_multiplier,
            "emissions_factor_eq": self.ref.production_emissions_multiplier,
            "delay": self.activity.delay,
        }
        log.debug("Inputs without: %s", self.inputs_wo)

        self.math_wo = MathInputs(**self.inputs_wo)
        self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w, self.results_wo)

        return results_tuple

    def defaults(self) -> DefaultData:
        self.calculate()

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        math_w = MathInputs(**self.inputs_w)
        math_w_defaults = math_w.evaluate_tier_2_defaults()
        defaults_w.update(math_w_defaults.start)
        defaults_w.update(math_w_defaults.other)

        math_wo = MathInputs(**self.inputs_wo)
        math_wo_defaults = math_wo.evaluate_tier_2_defaults()
        defaults_wo.update(math_wo_defaults.start)
        defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class EnergyCalculator(BaseCalculator):
    """
    Calculator for Energy module
    """

    def get_defaults(self, input: Module) -> dict:
        return super().get_defaults(input)

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Energy module.
        """

        module: Energy = self.data
        self.results_w = MathResult(
            self.activity.implementation_years,
            self.activity.capitalization_years,
        )
        self.results_wo = MathResult(
            self.activity.implementation_years,
            self.activity.capitalization_years,
        )

        for elec in module.electricities.all():
            r_w, r_wo = ElectricityCalculator(elec).calculate()

            self.results_w += r_w
            self.results_wo += r_wo

        for fuel in module.fuels.all():
            r_w, r_wo = FuelCalculator(fuel).calculate()

            self.results_w += r_w
            self.results_wo += r_wo

        return (self.results_w, self.results_wo)


class ElectricityCalculator(BaseCalculator):
    """
    Calculator for energy.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.module: Electricity

        self.TRANSMISSION_LOSS = 0.1  # TODO: Add to database parameters
        self.electricity_ef_default: ipcc.ElectricityEmission = ipcc.ElectricityEmission()
        self.electricity_ef_selected: DefaultValue = DefaultValue()

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        try:
            self.electricity_ef_default = ipcc.ElectricityEmission.objects.get(country=self.country)

            if self.module.ef_source.name == "Operating Margin":
                self.electricity_ef_selected.value = self.electricity_ef_default.operating_margin
            else:
                self.electricity_ef_selected.value = self.electricity_ef_default.combined_margin

        except ipcc.ElectricityEmission.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "electricity_ef_t2")
            if missing_scenarios:
                raise ValueError(f"Electricity Emission Factor for {self.country.name} does not exist. Please provide a tier 2 value for scenarios: {', '.join(missing_scenarios)}")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Energy module.
        """
        log.debug("START ElectricityCalculator.calculate")

        self.get_defaults()

        self.inputs_w = {
            "emissions_factor": self.electricity_ef_selected.value,
            "specific_factor_start": self.module.electricity_ef_t2_start,
            "specific_factor_end": self.module.electricity_ef_t2_w,
            "mwh_start": self.module.mwh_start,
            "mwh_end": self.module.mwh_w,
            "percent_loss_transportation_start": self.module.transmission_loss_start,
            "percent_loss_transportation_end": self.module.transmission_loss_w,
            "rate_type": self.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "delay": self.activity.delay,
        }
        log.debug("Inputs with: %s", self.inputs_w)

        self.math_w = ElectricityConsumption(**self.inputs_w)
        self.math_w.calculate_emissions()

        self.inputs_wo = {
            "emissions_factor": self.electricity_ef_selected.value,
            "specific_factor_start": self.module.electricity_ef_t2_start,
            "specific_factor_end": self.module.electricity_ef_t2_wo,
            "mwh_start": self.module.mwh_start,
            "mwh_end": self.module.mwh_wo,
            "percent_loss_transportation_start": self.module.transmission_loss_start,
            "percent_loss_transportation_end": self.module.transmission_loss_wo,
            "rate_type": self.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "delay": self.activity.delay,
        }
        log.debug("Inputs without: %s", self.inputs_wo)

        self.math_wo = ElectricityConsumption(**self.inputs_wo)
        self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w, self.results_wo)

        log.debug("END ElectricityCalculator.calculate")
        log.debug("")
        return results_tuple

    def defaults(self) -> DefaultData:
        pass


class FuelCalculator(BaseCalculator):
    """
    Calculator for fuel
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.module: Fuel
        self.energy_ef_default: ipcc.EnergyDefaultEmissionFactor = ipcc.EnergyDefaultEmissionFactor()

        self.methane_constant = self.project.gwp.ch4
        if self.module.fuel_type.name in ["Peat", "Charcoal"]:
            self.methane_constant = self.project.gwp.ch4_fossil

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        try:
            self.energy_ef_default = ipcc.EnergyDefaultEmissionFactor.objects.get(fuel_type=self.module.fuel_type, fuel_use_type=self.module.fuel_type.fuel_use_type)

            if self.energy_ef_default:
                if self.energy_ef_default.co2 is None and self.module.energy_ef_co2_t2 is None:
                    raise ValueError(f"Default CO2 emission factor for {self.module.fuel_type.name} does not exist. Please provide a tier 2 value.")
                if self.energy_ef_default.ch4 is None and self.module.energy_ef_ch4_t2 is None:
                    raise ValueError(f"Default CH4 emission factor for {self.module.fuel_type.name} does not exist. Please provide a tier 2 value.")
                if self.energy_ef_default.n2o is None and self.module.energy_ef_n2o_t2 is None:
                    raise ValueError(f"Default N2O emission factor for {self.module.fuel_type.name} does not exist. Please provide a tier 2 value.")

        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            if self.module.energy_ef_co2_t2 is None:
                raise ValueError(f"CO2 emission factor for {self.module.fuel_type.name} does not exist. Please provide a tier 2 value.")
            if self.module.energy_ef_ch4_t2 is None:
                raise ValueError(f"CH4 emission factor for {self.module.fuel_type.name} does not exist. Please provide a tier 2 value.")
            if self.module.energy_ef_n2o_t2 is None:
                raise ValueError(f"N2O emission factor for {self.module.fuel_type.name} does not exist. Please provide a tier 2 value.")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Fuel module.
        """
        log.debug("START FuelCalculator.calculate")

        self.get_defaults()

        inputs_w = {
            "emissions_factor_co2": self.energy_ef_default.co2,
            "specific_factor_co2": self.module.energy_ef_co2_t2,
            "emissions_factor_ch4": self.energy_ef_default.ch4,
            "specific_factor_ch4": self.module.energy_ef_ch4_t2,
            "emissions_factor_n2o": self.energy_ef_default.n2o,
            "specific_factor_n2o": self.module.energy_ef_n2o_t2,
            "mwh_start": self.module.fuel_consumption_start,
            "mwh_end": self.module.fuel_consumption_w,
            "rate_type": self.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "methane_constant": self.methane_constant,
            "nitrous_constant": self.project.gwp.n2o,
            "delay": self.activity.delay,
        }
        log.debug("Inputs with: %s", inputs_w)

        self.math_w = SolidAndLiquidFuelsConsumption(**inputs_w)
        self.math_w.calculate_emissions()

        inputs_wo = {
            "emissions_factor_co2": self.energy_ef_default.co2,
            "specific_factor_co2": self.module.energy_ef_co2_t2,
            "emissions_factor_ch4": self.energy_ef_default.ch4,
            "specific_factor_ch4": self.module.energy_ef_ch4_t2,
            "emissions_factor_n2o": self.energy_ef_default.n2o,
            "specific_factor_n2o": self.module.energy_ef_n2o_t2,
            "mwh_start": self.module.fuel_consumption_start,
            "mwh_end": self.module.fuel_consumption_wo,
            "rate_type": self.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "methane_constant": self.methane_constant,
            "nitrous_constant": self.project.gwp.n2o,
            "delay": self.activity.delay,
        }
        log.debug("Inputs without: %s", inputs_wo)

        self.math_wo = SolidAndLiquidFuelsConsumption(**inputs_wo)
        self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w, self.results_wo)

        log.debug("END FuelCalculator.calculate")
        return results_tuple


class SettlementCalculator(LandModuleCalculator):
    """
    Calculator for settlements
    """

    def __init__(self, module) -> None:
        super().__init__(module)
        self.module: Settlement

        self.ef_start: ipcc.SettlementEF = ipcc.SettlementEF()
        self.ef_w: ipcc.SettlementEF = ipcc.SettlementEF()
        self.ef_wo: ipcc.SettlementEF = ipcc.SettlementEF()

    def get_defaults(self, calculate=False) -> dict:
        log.debug("START SettlementCalculator.get_defaults")
        super().get_defaults(calculate)

        """
        # NOTE: Since biomass for Settlement is in another IPCC table, detached from the other biomass references for the other modules (e.g. ForestTotalBiomass),
        I wonder if in a LUC scenario the reference values would be wrong, since the Settlement would only be able to access its own biomass reference values.
        08/10/2024: Lorenzo Maestripieri said that this logic is fine, since the biomass reference values are specific to the module.
        """
        if self.module.is_start():
            self.ef_start: ipcc.SettlementEF = utils.get_or_raise(ipcc.SettlementEF, {"settlement_type": self.module.settlement_type_start, "climate": self.climate, "moisture": self.moisture}, f"Settlement EF not found for {self.module.settlement_type_start.name}")
            self.flu_start = DefaultValue(self.ef_start.flu)
            self.fi_start = DefaultValue(self.ef_start.fi)
            self.fmg_start = DefaultValue(self.ef_start.fmg)

        if self.module.is_with():
            self.ef_w: ipcc.SettlementEF = utils.get_or_raise(ipcc.SettlementEF, {"settlement_type": self.module.settlement_type_w, "climate": self.climate, "moisture": self.moisture}, f"Settlement EF not found for {self.module.settlement_type_w.name}")
            self.flu_w = DefaultValue(self.ef_w.flu)
            self.fi_w = DefaultValue(self.ef_w.fi)
            self.fmg_w = DefaultValue(self.ef_w.fmg)

        if self.module.is_without():
            self.ef_wo: ipcc.SettlementEF = utils.get_or_raise(ipcc.SettlementEF, {"settlement_type": self.module.settlement_type_wo, "climate": self.climate, "moisture": self.moisture}, f"Settlement EF not found for {self.module.settlement_type_wo.name}")
            self.flu_wo = DefaultValue(self.ef_wo.flu)
            self.fi_wo = DefaultValue(self.ef_wo.fi)
            self.fmg_wo = DefaultValue(self.ef_wo.fmg)

        # SOCinitial in case of non-paved settlement (start) to paved settlement (end)
        if self.luc and self.module.is_start() and self.module.settlement_type_start.name.casefold() != "paved settlement":
            is_paved_w = self.module.is_with() and self.module.settlement_type_w.name.casefold() == "paved settlement"
            is_paved_wo = self.module.is_without() and self.module.settlement_type_wo.name.casefold() == "paved settlement"

            if is_paved_w or is_paved_wo:
                self.flu_start = get_flu_data(self.module_start, self.climate, self.moisture, utils.ScenarioTypes.WITHOUT)
                self.fi_start = get_fi_data(self.module_start, self.climate, self.moisture, utils.ScenarioTypes.WITHOUT)
                self.fmg_start = get_fmg_data(self.module_start, self.climate, self.moisture, utils.ScenarioTypes.WITHOUT)

                self.soc_start.value = self.soc_start.value * self.flu_start.value * self.fi_start.value * self.fmg_start.value  # SOCinitial

        log.debug("END SettlementCalculator.get_defaults")

    def calculate(self) -> Result:
        log.debug("START SettlementCalculator.calculate")

        self.get_defaults()

        if self.module.is_start():
            log.debug("Start")

            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_w.soc_t2_w,
                "calculate_soc_som": False,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_w.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_w.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_w.fi_t2_w,
                "delay": self.activity.delay,
                "biomass_start_default": self.ef_start.biomass,
                "biomass_end_default": self.ef_w.biomass,
                "calculate_biomass": self.calculate_biomass_start_w,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }

            self.math_start_w = MathNotCultivatedLand(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_wo.soc_t2_wo,
                "calculate_soc_som": False,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_wo.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_wo.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_wo.fi_t2_wo,
                "delay": self.activity.delay,
                "biomass_start_default": self.ef_start.biomass,
                "biomass_end_default": self.ef_wo.biomass,
                "calculate_biomass": self.calculate_biomass_start_wo,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }

            self.math_start_wo = MathNotCultivatedLand(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if self.module.is_with():

            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_w.soc_t2_w,
                "calculate_soc_som": True,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_w.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_w.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_w.fi_t2_w,
                "delay": self.activity.delay,
                "calculate_biomass": self.calculate_biomass_w,
                "biomass_start_default": self.ef_start.biomass,
                "biomass_end_default": self.ef_w.biomass,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }

            self.math_w = MathNotCultivatedLand(**self.inputs_w)
            self.math_w.calculate_emissions()

        if self.module.is_without():

            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_wo.soc_t2_wo,
                "calculate_soc_som": True,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_wo.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_wo.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_wo.fi_t2_wo,
                "delay": self.activity.delay,
                "calculate_biomass": self.calculate_biomass_wo,
                "biomass_start_default": self.ef_start.biomass,
                "biomass_end_default": self.ef_wo.biomass,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }

            self.math_wo = MathNotCultivatedLand(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_start_w.plot_emissions_and_aggregate_by_activity("settlement_start_w")
            self.results_start_wo.plot_emissions_and_aggregate_by_activity("settlement_start_wo")
            self.results_w.plot_emissions_and_aggregate_by_activity("settlement_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("settlement_wo")

        self.results_w += self.results_start_w
        self.results_wo += self.results_start_wo

        self.results_w += self.results_w
        self.results_wo += self.results_wo

        for building in self.module.buildings.all():
            r_w, r_wo = BuildingCalculator(building).calculate()

            self.results_w += r_w
            self.results_wo += r_wo

        for road in self.module.roads.all():
            r_w, r_wo = RoadCalculator(road).calculate()

            self.results_w += r_w
            self.results_wo += r_wo

        log.debug("END SettlementCalculator.calculate")
        return (self.results_w, self.results_wo)


class BuildingCalculator(BaseCalculator):
    """
    Calculator for buildings and roads.
    """

    def __init__(self, input) -> None:
        super().__init__(input)
        self.module: Building

        self.ef: ipcc.BuildingEmissionFactor = ipcc.BuildingEmissionFactor()

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        # TODO: What do we need the start scenario for?
        # TODO: Define if all the fields of an input are required after creation
        try:
            self.ef = ipcc.BuildingEmissionFactor.objects.get(building_type=self.module.building_type)
        except ipcc.BuildingEmissionFactor.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "ef_t2")
            if missing_scenarios:
                raise ValueError(f"Building Emission Factor for {self.module.building_type.name} does not exist. Please provide a tier 2 value for scenarios: {', '.join(missing_scenarios)}")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Building module.
        """

        self.get_defaults()

        if self.module.is_with():
            self.inputs_w = {
                "ef_ipcc": self.ef.value,
                "ef_tier_2": self.module.ef_t2_w,
                "units_end": self.module.area_m2_w,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "delay": self.activity.delay,
            }

            self.math_w = MathRoads(**self.inputs_w)
            self.math_w.calculate_emissions()

        if self.module.is_without():
            self.inputs_wo = {
                "ef_ipcc": self.ef.value,
                "ef_tier_2": self.module.ef_t2_wo,
                "units_end": self.module.area_m2_wo,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "delay": self.activity.delay,
            }

            self.math_wo = MathRoads(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w, self.results_wo)

        return results_tuple


class RoadCalculator(BaseCalculator):
    """
    Calculator for buildings and roads.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.module: Road
        self.parent: Settlement = self.module.parent

        self.ef: ipcc.RoadEmissionFactor = ipcc.RoadEmissionFactor()

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        try:
            self.ef = ipcc.RoadEmissionFactor.objects.get(road_type=self.module.road_type)
        except ipcc.RoadEmissionFactor.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "ef_t2")
            if missing_scenarios:
                raise ValueError(f"Road Emission Factor for {self.module.road_type.name} does not exist. Please provide a tier 2 value for scenarios: {', '.join(missing_scenarios)}")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Road module.
        """

        self.get_defaults()

        self.results_w = MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if self.parent.is_with():
            self.inputs_w = {
                "ef_ipcc": self.ef.value,
                "ef_tier_2": self.module.ef_t2_w,
                "units_end": self.module.length_km_w * self.module.width_m_w,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "delay": self.activity.delay,
            }

            self.math_w = MathRoads(**self.inputs_w)
            self.math_w.calculate_emissions()

        if self.parent.is_without():
            self.inputs_wo = {
                "ef_ipcc": self.ef.value,
                "ef_tier_2": self.module.ef_t2_wo,
                "units_end": self.module.length_km_wo * self.module.width_m_wo,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "delay": self.activity.delay,
            }

            self.math_wo = MathRoads(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w, self.results_wo)

        return results_tuple


class LivestockCalculator(BaseCalculator):
    """
    Calculator for livestock

    # NOTE: The order_by=manure_management_type__name is to ensure that we are getting the correct order of the entities.
    This is because for each scenario the mathematical model is expecting a precise order,
    where each entry of [LivestockManureEF] matches an entry of [LivestockAnimalWasteManagementSystem]
    """

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: Livestock = self.data
        activity: Activity = module.activity
        project: Project = activity.project
        country: Country = project.country

        climate: Climate = activity.climate_t2 or project.climate
        moisture: Moisture = activity.moisture_t2 or project.moisture

        self.LEACHING_MULTI = LivestockParameter.objects.get(name="LEACHING_MULTIPLIER").value
        self.volatilization_multi = ipcc.ManureManagementVolatilizationMultiplier.objects.get(moisture=moisture)

        if module.is_start():

            production_category_region_flt = {
                "livestock_production_type": module.livestock_production_type_start,
                "livestock_category_type": module.livestock_category_type,
                "ipcc_region": country.ipcc_region,
            }

            manure_ef_flt = {
                "livestock_category_type": module.livestock_category_type,
                "livestock_production_type": module.livestock_production_type_start,
                "climate": climate,
                "moisture": moisture,
            }

            ch4 = {
                "emission_type__name": utils.EmissionTypes.CH4.value,
            }

            n2o = {
                "emission_type__name": utils.EmissionTypes.N2O.value,
            }

            volatilization = {
                "emission_type__name": utils.EmissionTypes.N2O_VOLATILIZATION.value,
            }

            leaching = {
                "emission_type__name": utils.EmissionTypes.N2O_LEACHING.value,
            }

            prp = {
                "manure_management_type__name": utils.ManureManagementTypes.PRP.value,
            }

            # TAM
            self.tam_ch4_start = utils.get_or_raise(ipcc.LivestockTAM, production_category_region_flt, f"Could not find TAM (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # VSER
            self.vser_ch4_start = utils.get_or_raise(ipcc.LivestockVSER, production_category_region_flt, f"Could not find VSER (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # EF CH4 PRP
            self.ef_ch4_prp_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | ch4 | prp, f"Could not find EF CH4 PRP (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # EF CH4 PRP of other systems
            self.ef_ch4_systems_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | ch4, f"Could not find EF CH4 Systems (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_ch4_system_values_start = [system.value for system in self.ef_ch4_systems_start]
            # Set all None values to 0
            self.ef_ch4_system_values_start = [0 if v is None else v for v in self.ef_ch4_system_values_start]

            # Animal Waste PRP
            self.animal_waste_prp_start = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt | prp | {"manure_management_type__name": utils.ManureManagementTypes.PRP.value}, f"Could not find Animal Waste PRP (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # Animal Waste PRP of other systems
            self.animal_waste_management_systems_start = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt, f"Could not find Animal Waste Management Systems (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.animal_waste_management_systems_values_start = [system.value for system in self.animal_waste_management_systems_start]
            # Set all None values to 0
            self.animal_waste_management_systems_values_start = [0 if v is None else v for v in self.animal_waste_management_systems_values_start]

            # Enteric CH4
            self.enteric_ch4_start = utils.get_or_raise(ipcc.MethaneEntericFermentationFactor, production_category_region_flt, f"Could not find Enteric CH4 (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # PRP N2O Direct EF
            self.prp_n2o_direct_ef_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | n2o | prp, f"Could not find PRP N2O Direct EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # PRP N2O Volatilization EF
            self.prp_n2o_volatilization_ef_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | prp | volatilization, f"Could not find PRP N2O Volatilization EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # PRP N2O Leaching EF
            self.prp_n2o_leaching_ef_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | prp | leaching, f"Could not find PRP N2O Leaching EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # PRP N2O Direct EF of other systems
            self.ef_n2o_direct_systems_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | n2o, f"Could not find N2O Direct EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_direct_systems_start = [s.value for s in self.ef_n2o_direct_systems_start]
            # Set all None values to 0
            self.ef_n2o_direct_systems_start = [0 if v is None else v for v in self.ef_n2o_direct_systems_start]

            # PRP N2O Volatilization EF of other systems
            self.ef_n2o_volatilization_systems_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | volatilization, f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_volatilization_systems_start = [s.value for s in self.ef_n2o_volatilization_systems_start]
            # Set all None values to 0
            self.ef_n2o_volatilization_systems_start = [0 if v is None else v for v in self.ef_n2o_volatilization_systems_start]

            # PRP N2O Leaching EF of other systems
            self.ef_n2o_leaching_systems_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | leaching, f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_leaching_systems_start = [s.value for s in self.ef_n2o_leaching_systems_start]
            # Set all None values to 0
            self.ef_n2o_leaching_systems_start = [0 if v is None else v for v in self.ef_n2o_leaching_systems_start]

            # NER
            self.ner_start = utils.get_or_raise(ipcc.LivestockNER, production_category_region_flt, f"Could not find NER (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # Complementary Manure Management

            self.n2o_ef_t2_start = None
            self.n2o_volatilization_ef_t2_start = None
            self.n2o_leaching_ef_t2_start = None
            self.ch4_ef_t2_start = None

            complementary_mm = {"manure_management_type": module.complementary_manure_management_type_start}

            if module.complementary_manure_management_type_start is not None:

                self.n2o_ef_t2_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | n2o | complementary_mm, f"Could not find N2O EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.n2o_ef_t2_start:
                    self.n2o_ef_t2_start = self.n2o_ef_t2_start.value

                self.n2o_volatilization_ef_t2_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | volatilization | complementary_mm, f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.n2o_volatilization_ef_t2_start:
                    self.n2o_volatilization_ef_t2_start = self.n2o_volatilization_ef_t2_start.value

                self.n2o_leaching_ef_t2_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | leaching | complementary_mm, f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.n2o_leaching_ef_t2_start:
                    self.n2o_leaching_ef_t2_start = self.n2o_leaching_ef_t2_start.value

                self.ch4_ef_t2_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | ch4 | complementary_mm, f"Could not find CH4 EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.ch4_ef_t2_start:
                    self.ch4_ef_t2_start = self.ch4_ef_t2_start.value

        if module.is_with():

            production_category_region_flt = {
                "livestock_production_type": module.livestock_production_type_w,
                "livestock_category_type": module.livestock_category_type,
                "ipcc_region": country.ipcc_region,
            }

            manure_ef_flt = {
                "livestock_category_type": module.livestock_category_type,
                "livestock_production_type": module.livestock_production_type_w,
                "climate": climate,
                "moisture": moisture,
            }

            ch4 = {
                "emission_type__name": utils.EmissionTypes.CH4.value,
            }

            n2o = {
                "emission_type__name": utils.EmissionTypes.N2O.value,
            }

            volatilization = {
                "emission_type__name": utils.EmissionTypes.N2O_VOLATILIZATION.value,
            }

            leaching = {
                "emission_type__name": utils.EmissionTypes.N2O_LEACHING.value,
            }

            prp = {
                "manure_management_type__name": utils.ManureManagementTypes.PRP.value,
            }

            # TAM
            self.tam_ch4_w = utils.get_or_raise(ipcc.LivestockTAM, production_category_region_flt, f"Could not find TAM (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # VSER
            self.vser_ch4_w = utils.get_or_raise(ipcc.LivestockVSER, production_category_region_flt, f"Could not find VSER (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # EF CH4 PRP
            self.ef_ch4_prp_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | ch4 | prp, f"Could not find EF CH4 PRP (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # EF CH4 PRP of other systems
            self.ef_ch4_systems_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | ch4, f"Could not find EF CH4 Systems (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_ch4_system_values_w = [system.value for system in self.ef_ch4_systems_w]
            # Set all None values to 0
            self.ef_ch4_system_values_w = [0 if v is None else v for v in self.ef_ch4_system_values_w]

            # Animal Waste PRP
            self.animal_waste_prp_w = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt | prp | {"manure_management_type__name": utils.ManureManagementTypes.PRP.value}, f"Could not find Animal Waste PRP (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # Animal Waste PRP of other systems
            self.animal_waste_management_systems_w = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt, f"Could not find Animal Waste Management Systems (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.animal_waste_management_systems_values_w = [system.value for system in self.animal_waste_management_systems_w]
            # Set all None values to 0
            self.animal_waste_management_systems_values_w = [0 if v is None else v for v in self.animal_waste_management_systems_values_w]

            # Enteric CH4
            self.enteric_ch4_w = utils.get_or_raise(ipcc.MethaneEntericFermentationFactor, production_category_region_flt, f"Could not find Enteric CH4 (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # PRP N2O Direct EF
            self.prp_n2o_direct_ef_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | n2o | prp, f"Could not find PRP N2O Direct EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # PRP N2O Volatilization EF
            self.prp_n2o_volatilization_ef_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | prp | volatilization, f"Could not find PRP N2O Volatilization EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # PRP N2O Leaching EF
            self.prp_n2o_leaching_ef_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | prp | leaching, f"Could not find PRP N2O Leaching EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # PRP N2O Direct EF of other systems
            self.ef_n2o_direct_systems_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | n2o, f"Could not find N2O Direct EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_direct_systems_w = [s.value for s in self.ef_n2o_direct_systems_w]
            # Set all None values to 0
            self.ef_n2o_direct_systems_w = [0 if v is None else v for v in self.ef_n2o_direct_systems_w]

            # PRP N2O Volatilization EF of other systems
            self.ef_n2o_volatilization_systems_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | volatilization, f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_volatilization_systems_w = [s.value for s in self.ef_n2o_volatilization_systems_w]
            # Set all None values to 0
            self.ef_n2o_volatilization_systems_w = [0 if v is None else v for v in self.ef_n2o_volatilization_systems_w]

            # PRP N2O Leaching EF of other systems
            self.ef_n2o_leaching_systems_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | leaching, f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_leaching_systems_w = [s.value for s in self.ef_n2o_leaching_systems_w]
            # Set all None values to 0
            self.ef_n2o_leaching_systems_w = [0 if v is None else v for v in self.ef_n2o_leaching_systems_w]

            # NER
            self.ner_w = utils.get_or_raise(ipcc.LivestockNER, production_category_region_flt, f"Could not find NER (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # Complementary Manure Management

            self.n2o_ef_t2_w = None
            self.n2o_volatilization_ef_t2_w = None
            self.n2o_leaching_ef_t2_w = None
            self.ch4_ef_t2_w = None

            complementary_mm = {"manure_management_type": module.complementary_manure_management_type_w}

            if module.complementary_manure_management_type_w is not None:

                self.n2o_ef_t2_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | n2o | complementary_mm, f"Could not find N2O EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.n2o_ef_t2_w:
                    self.n2o_ef_t2_w = self.n2o_ef_t2_w.value

                self.n2o_volatilization_ef_t2_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | volatilization | complementary_mm, f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.n2o_volatilization_ef_t2_w:
                    self.n2o_volatilization_ef_t2_w = self.n2o_volatilization_ef_t2_w.value

                self.n2o_leaching_ef_t2_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | leaching | complementary_mm, f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.n2o_leaching_ef_t2_w:
                    self.n2o_leaching_ef_t2_w = self.n2o_leaching_ef_t2_w.value

                self.ch4_ef_t2_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | ch4 | complementary_mm, f"Could not find CH4 EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.ch4_ef_t2_w:
                    self.ch4_ef_t2_w = self.ch4_ef_t2_w.value

        if module.is_without():

            production_category_region_flt = {
                "livestock_production_type": module.livestock_production_type_wo,
                "livestock_category_type": module.livestock_category_type,
                "ipcc_region": country.ipcc_region,
            }

            manure_ef_flt = {
                "livestock_category_type": module.livestock_category_type,
                "livestock_production_type": module.livestock_production_type_wo,
                "climate": climate,
                "moisture": moisture,
            }

            ch4 = {
                "emission_type__name": utils.EmissionTypes.CH4.value,
            }

            n2o = {
                "emission_type__name": utils.EmissionTypes.N2O.value,
            }

            volatilization = {
                "emission_type__name": utils.EmissionTypes.N2O_VOLATILIZATION.value,
            }

            leaching = {
                "emission_type__name": utils.EmissionTypes.N2O_LEACHING.value,
            }

            prp = {
                "manure_management_type__name": utils.ManureManagementTypes.PRP.value,
            }

            # TAM
            self.tam_ch4_wo = utils.get_or_raise(ipcc.LivestockTAM, production_category_region_flt, f"Could not find TAM (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # VSER
            self.vser_ch4_wo = utils.get_or_raise(ipcc.LivestockVSER, production_category_region_flt, f"Could not find VSER (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # EF CH4 PRP
            self.ef_ch4_prp_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | ch4 | prp, f"Could not find EF CH4 PRP (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # EF CH4 PRP of other systems
            self.ef_ch4_systems_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | ch4, f"Could not find EF CH4 Systems (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_ch4_system_values_wo = [system.value for system in self.ef_ch4_systems_wo]
            # Set all None values to 0
            self.ef_ch4_system_values_wo = [0 if v is None else v for v in self.ef_ch4_system_values_wo]

            # Animal Waste PRP
            self.animal_waste_prp_wo = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt | prp | {"manure_management_type__name": utils.ManureManagementTypes.PRP.value}, f"Could not find Animal Waste PRP (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # Animal Waste PRP of other systems
            self.animal_waste_management_systems_wo = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt, f"Could not find Animal Waste Management Systems (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.animal_waste_management_systems_values_wo = [system.value for system in self.animal_waste_management_systems_wo]
            # Set all None values to 0
            self.animal_waste_management_systems_values_wo = [0 if v is None else v for v in self.animal_waste_management_systems_values_wo]

            # Enteric CH4
            self.enteric_ch4_wo = utils.get_or_raise(ipcc.MethaneEntericFermentationFactor, production_category_region_flt, f"Could not find Enteric CH4 (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # PRP N2O Direct EF
            self.prp_n2o_direct_ef_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | n2o | prp, f"Could not find PRP N2O Direct EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # PRP N2O Volatilization EF
            self.prp_n2o_volatilization_ef_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | prp | volatilization, f"Could not find PRP N2O Volatilization EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # PRP N2O Leaching EF
            self.prp_n2o_leaching_ef_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | prp | leaching, f"Could not find PRP N2O Leaching EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            # PRP N2O Direct EF of other systems
            self.ef_n2o_direct_systems_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | n2o, f"Could not find N2O Direct EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_direct_systems_wo = [s.value for s in self.ef_n2o_direct_systems_wo]
            # Set all None values to 0
            self.ef_n2o_direct_systems_wo = [0 if v is None else v for v in self.ef_n2o_direct_systems_wo]

            # PRP N2O Volatilization EF of other systems
            self.ef_n2o_volatilization_systems_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | volatilization, f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_volatilization_systems_wo = [s.value for s in self.ef_n2o_volatilization_systems_wo]
            # Set all None values to 0
            self.ef_n2o_volatilization_systems_wo = [0 if v is None else v for v in self.ef_n2o_volatilization_systems_wo]

            # PRP N2O Leaching EF of other systems
            self.ef_n2o_leaching_systems_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | leaching, f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_leaching_systems_wo = [s.value for s in self.ef_n2o_leaching_systems_wo]
            # Set all None values to 0
            self.ef_n2o_leaching_systems_wo = [0 if v is None else v for v in self.ef_n2o_leaching_systems_wo]

            # NER
            self.ner_wo = utils.get_or_raise(ipcc.LivestockNER, production_category_region_flt, f"Could not find NER (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # Complementary Manure Management

            self.n2o_ef_t2_wo = None
            self.n2o_volatilization_ef_t2_wo = None
            self.n2o_leaching_ef_t2_wo = None
            self.ch4_ef_t2_wo = None

            complementary_mm = {"manure_management_type": module.complementary_manure_management_type_wo}

            if module.complementary_manure_management_type_wo is not None:

                self.n2o_ef_t2_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | n2o | complementary_mm, f"Could not find N2O EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.n2o_ef_t2_wo:
                    self.n2o_ef_t2_wo = self.n2o_ef_t2_wo.value

                self.n2o_volatilization_ef_t2_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | volatilization | complementary_mm, f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.n2o_volatilization_ef_t2_wo:
                    self.n2o_volatilization_ef_t2_wo = self.n2o_volatilization_ef_t2_wo.value

                self.n2o_leaching_ef_t2_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | leaching | complementary_mm, f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.n2o_leaching_ef_t2_wo:
                    self.n2o_leaching_ef_t2_wo = self.n2o_leaching_ef_t2_wo.value

                self.ch4_ef_t2_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | ch4 | complementary_mm, f"Could not find CH4 EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")
                if self.ch4_ef_t2_wo:
                    self.ch4_ef_t2_wo = self.ch4_ef_t2_wo.value

        return

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Livestock module.
        """
        log.debug("START LivestockCalculator.calculate")

        module: Livestock = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        self.math_w = None
        self.math_wo = None

        self.get_defaults()

        if module.is_with():
            log.debug("Calculating emissions for WITH")

            inputs_w = {
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": module.activity.change_rate.name,
                "methane_constant": project.gwp.ch4,
                "head_number_start": module.heads_number_start,
                "head_number_end": module.heads_number_w,
                "specific_factor_default_start": self.enteric_ch4_start.value,
                "specific_factor_default_end": self.enteric_ch4_w.value,
                "specific_factor_start_tier_2": module.enteric_fermentation_t2_start,
                "specific_factor_end_tier_2": module.enteric_fermentation_t2_w,
                "ef_prp_methane_start": self.ef_ch4_prp_start.value,
                "ef_prp_methane_end": self.ef_ch4_prp_w.value,
                "percentage_prp_default_start": self.animal_waste_prp_start.value,
                "percentage_prp_default_end": self.animal_waste_prp_w.value,
                "percentage_prp_tier_2_start": module.prp_percentage_t2_start * 100 if module.prp_percentage_t2_start else None,
                "percentage_prp_tier_2_end": module.prp_percentage_t2_w * 100 if module.prp_percentage_t2_w else None,
                "ef_system_methane_start": self.ef_ch4_system_values_start,
                "ef_system_methane_end": self.ef_ch4_system_values_w,
                "ch4_prp_tier_2_start": module.prp_ch4_t2_start,
                "ch4_prp_tier_2_end": module.prp_ch4_t2_w,
                "ch4_system_default_start": self.ch4_ef_t2_start,
                "ch4_system_default_end": self.ch4_ef_t2_w,
                "ch4_system_tier_2_start": module.emission_factor_ch4_t2_start,
                "ch4_system_tier_2_end": module.emission_factor_ch4_t2_w,
                "percentage_system_default_start": self.animal_waste_management_systems_values_start,
                "percentage_system_default_end": self.animal_waste_management_systems_values_w,
                "tam_start": self.tam_ch4_start.value,
                "tam_end": self.tam_ch4_w.value,
                "vser_start": self.vser_ch4_start.value,
                "vser_end": self.vser_ch4_w.value,
                "ef_prp_nitrous_direct_start": self.prp_n2o_direct_ef_start.value,
                "ef_prp_nitrous_direct_end": self.prp_n2o_direct_ef_w.value,
                "ef_system_nitrous_direct_start": self.ef_n2o_direct_systems_start,
                "ef_system_nitrous_direct_end": self.ef_n2o_direct_systems_w,
                "n2o_prp_tier_2_start_direct": module.prp_n2o_t2_start,
                "n2o_prp_tier_2_end_direct": module.prp_n2o_t2_w,
                "n2o_system_direct_default_start": self.n2o_ef_t2_start,
                "n2o_system_direct_default_end": self.n2o_ef_t2_w,
                "n2o_system_direct_tier_2_start": module.emission_factor_n2o_t2_start,
                "n2o_system_direct_tier_2_end": module.emission_factor_n2o_t2_w,
                "ner_start": self.ner_start.value,
                "ner_end": self.ner_w.value,
                "ef_prp_nitrous_indirect_volatization_start": self.prp_n2o_volatilization_ef_start.value,
                "ef_prp_nitrous_indirect_volatization_end": self.prp_n2o_volatilization_ef_w.value,
                "ef_system_nitrous_indirect_volatization_start": self.ef_n2o_volatilization_systems_start,
                "ef_system_nitrous_indirect_volatization_end": self.ef_n2o_volatilization_systems_w,
                "n2o_prp_tier_2_start_indirect_volatization": module.prp_n2o_t2_start,
                "n2o_prp_tier_2_end_indirect_volatization": module.prp_n2o_t2_w,
                "n20_system_indirect_volatization_default_start": self.n2o_volatilization_ef_t2_start,
                "n20_system_indirect_volatization_default_end": self.n2o_volatilization_ef_t2_w,
                "n20_system_indirect_volatization_tier_2_start": module.emission_factor_n2o_t2_start,
                "n20_system_indirect_volatization_tier_2_end": module.emission_factor_n2o_t2_w,
                "ef_prp_nitrous_indirect_leaching_start": self.prp_n2o_leaching_ef_start.value,
                "ef_prp_nitrous_indirect_leaching_end": self.prp_n2o_leaching_ef_w.value,
                "ef_system_nitrous_indirect_leaching_start": self.ef_n2o_leaching_systems_start,
                "ef_system_nitrous_indirect_leaching_end": self.ef_n2o_leaching_systems_w,
                "n2o_prp_tier_2_start_indirect_leaching": module.prp_n2o_t2_start,
                "n2o_prp_tier_2_end_indirect_leaching": module.prp_n2o_t2_w,
                "n20_system_indirect_leaching_default_start": self.n2o_leaching_ef_t2_start,
                "n20_system_indirect_leaching_default_end": self.n2o_leaching_ef_t2_w,
                "n20_system_indirect_leaching_tier_2_start": module.emission_factor_n2o_t2_start,
                "n20_system_indirect_leaching_tier_2_end": module.emission_factor_n2o_t2_w,
                "nitrous_constant": project.gwp.n2o,
                "volatilization_multiplier": self.volatilization_multi.value,
                "leaching_multiplier": self.LEACHING_MULTI,
                "delay": self.activity.delay,
            }

            log.debug(f"Inputs for WITH: {inputs_w}")

            self.math_w = MathLivestock(**inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            log.debug("Calculating emissions for WITHOUT")

            inputs_wo = {
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": module.activity.change_rate.name,
                "methane_constant": project.gwp.ch4,
                "head_number_start": module.heads_number_start,
                "head_number_end": module.heads_number_wo,
                "specific_factor_default_start": self.enteric_ch4_start.value,
                "specific_factor_default_end": self.enteric_ch4_wo.value,
                "specific_factor_start_tier_2": module.enteric_fermentation_t2_start,
                "specific_factor_end_tier_2": module.enteric_fermentation_t2_wo,
                "ef_prp_methane_start": self.ef_ch4_prp_start.value,
                "ef_prp_methane_end": self.ef_ch4_prp_wo.value,
                "percentage_prp_default_start": self.animal_waste_prp_start.value,
                "percentage_prp_default_end": self.animal_waste_prp_wo.value,
                "percentage_prp_tier_2_start": module.prp_percentage_t2_start * 100 if module.prp_percentage_t2_start else None,
                "percentage_prp_tier_2_end": module.prp_percentage_t2_wo * 100 if module.prp_percentage_t2_wo else None,
                "ef_system_methane_start": self.ef_ch4_system_values_start,
                "ef_system_methane_end": self.ef_ch4_system_values_wo,
                "ch4_prp_tier_2_start": module.prp_ch4_t2_start,
                "ch4_prp_tier_2_end": module.prp_ch4_t2_wo,
                "ch4_system_default_start": self.ch4_ef_t2_start,
                "ch4_system_default_end": self.ch4_ef_t2_wo,
                "ch4_system_tier_2_start": module.emission_factor_ch4_t2_start,
                "ch4_system_tier_2_end": module.emission_factor_ch4_t2_wo,
                "percentage_system_default_start": self.animal_waste_management_systems_values_start,
                "percentage_system_default_end": self.animal_waste_management_systems_values_wo,
                "tam_start": self.tam_ch4_start.value,
                "tam_end": self.tam_ch4_wo.value,
                "vser_start": self.vser_ch4_start.value,
                "vser_end": self.vser_ch4_wo.value,
                "ef_prp_nitrous_direct_start": self.prp_n2o_direct_ef_start.value,
                "ef_prp_nitrous_direct_end": self.prp_n2o_direct_ef_wo.value,
                "ef_system_nitrous_direct_start": self.ef_n2o_direct_systems_start,
                "ef_system_nitrous_direct_end": self.ef_n2o_direct_systems_wo,
                "n2o_prp_tier_2_start_direct": module.prp_n2o_t2_start,
                "n2o_prp_tier_2_end_direct": module.prp_n2o_t2_wo,
                "n2o_system_direct_default_start": self.n2o_ef_t2_start,
                "n2o_system_direct_default_end": self.n2o_ef_t2_wo,
                "n2o_system_direct_tier_2_start": module.emission_factor_n2o_t2_start,
                "n2o_system_direct_tier_2_end": module.emission_factor_n2o_t2_wo,
                "ner_start": self.ner_start.value,
                "ner_end": self.ner_wo.value,
                "ef_prp_nitrous_indirect_volatization_start": self.prp_n2o_volatilization_ef_start.value,
                "ef_prp_nitrous_indirect_volatization_end": self.prp_n2o_volatilization_ef_wo.value,
                "ef_system_nitrous_indirect_volatization_start": self.ef_n2o_volatilization_systems_start,
                "ef_system_nitrous_indirect_volatization_end": self.ef_n2o_volatilization_systems_wo,
                "n2o_prp_tier_2_start_indirect_volatization": module.prp_n2o_t2_start,
                "n2o_prp_tier_2_end_indirect_volatization": module.prp_n2o_t2_wo,
                "n20_system_indirect_volatization_default_start": self.n2o_volatilization_ef_t2_start,
                "n20_system_indirect_volatization_default_end": self.n2o_volatilization_ef_t2_wo,
                "n20_system_indirect_volatization_tier_2_start": module.emission_factor_n2o_t2_start,
                "n20_system_indirect_volatization_tier_2_end": module.emission_factor_n2o_t2_wo,
                "ef_prp_nitrous_indirect_leaching_start": self.prp_n2o_leaching_ef_start.value,
                "ef_prp_nitrous_indirect_leaching_end": self.prp_n2o_leaching_ef_wo.value,
                "ef_system_nitrous_indirect_leaching_start": self.ef_n2o_leaching_systems_start,
                "ef_system_nitrous_indirect_leaching_end": self.ef_n2o_leaching_systems_wo,
                "n2o_prp_tier_2_start_indirect_leaching": module.prp_n2o_t2_start,
                "n2o_prp_tier_2_end_indirect_leaching": module.prp_n2o_t2_wo,
                "n20_system_indirect_leaching_default_start": self.n2o_leaching_ef_t2_start,
                "n20_system_indirect_leaching_default_end": self.n2o_leaching_ef_t2_wo,
                "n20_system_indirect_leaching_tier_2_start": module.emission_factor_n2o_t2_start,
                "n20_system_indirect_leaching_tier_2_end": module.emission_factor_n2o_t2_wo,
                "nitrous_constant": project.gwp.n2o,
                "volatilization_multiplier": self.volatilization_multi.value,
                "leaching_multiplier": self.LEACHING_MULTI,
                "delay": self.activity.delay,
            }

            log.debug(f"Inputs for WITHOUT: {inputs_wo}")

            self.math_wo = MathLivestock(**inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_w.plot_emissions_and_aggregate_by_activity("livestock_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("livestock_wo")

        return (self.results_w, self.results_wo)


class IrrigationCalculator(BaseCalculator):
    def calculate(self) -> list[Result]:
        module: Irrigation = self.data
        self.results_w = MathResult(
            self.activity.implementation_years,
            self.activity.capitalization_years,
        )
        self.results_wo = MathResult(
            self.activity.implementation_years,
            self.activity.capitalization_years,
        )
        for system in module.irrigation_systems.all():
            r_w, r_wo = IrrigationSystemCalculator(system).calculate()
            self.results_w += r_w
            self.results_wo += r_wo

        for phase in module.irrigation_phases.all():
            r_w, r_wo = IrrigationPhaseCalculator(phase).calculate()
            self.results_w += r_w
            self.results_wo += r_wo

        if PLOT_GRAPHS:
            self.results_w.plot_emissions_and_aggregate_by_activity("irrigation_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("irrigation_wo")

        return (self.results_w, self.results_wo)

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)


class IrrigationSystemCalculator(BaseCalculator):
    """
    Calculates the emissions of the irrigation system.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.module: IrrigationSystem
        self.ef: ipcc.IrrigationSystemData = ipcc.IrrigationSystemData()

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        try:
            self.ef = ipcc.IrrigationSystemData.objects.get(irrigation_system_type=self.module.irrigation_system_type)
        except ipcc.IrrigationSystemData.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "ef_t2")
            if missing_scenarios:
                raise ValueError(f"Emission Factor for {self.module.irrigation_system_type.name} is missing. Please provide a tier 2 value for the following scenarios: {', '.join(missing_scenarios)}")

    def calculate(self) -> list[Result]:
        """
        Calculates the emissions of the irrigation system.
        """

        self.get_defaults()

        self.inputs_w = {
            "ef_ref": self.ef.value,
            "ef_tier_2": self.module.ef_t2_start,
            "units_start": self.module.ha_start,
            "units_end": self.module.ha_w,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "rate_type": self.change_rate.name,
            "delay": self.activity.delay,
        }

        self.math_w = NewIrrigation(**self.inputs_w)
        self.math_w.calculate_emissions()

        self.inputs_wo = {
            "ef_ref": self.ef.value,
            "ef_tier_2": self.module.ef_t2_wo,
            "units_start": self.module.ha_start,
            "units_end": self.module.ha_wo,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "rate_type": self.change_rate.name,
            "delay": self.activity.delay,
        }

        self.math_wo = NewIrrigation(**self.inputs_wo)
        self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_w.plot_emissions_and_aggregate_by_activity("irrigation_system_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("irrigation_system_wo")

        results_tuple = (self.results_w, self.results_wo)

        return results_tuple


class IrrigationPhaseCalculator(BaseCalculator):

    def __init__(self, input) -> None:
        super().__init__(input)

        self.module: IrrigationPhase

        self.ef_default: ipcc.IrrigationPhaseData = ipcc.IrrigationPhaseData()
        self.energy_ef_default = ipcc.EnergyDefaultEmissionFactor()
        self.pressure_default = ipcc.IrrigationPressureRequirement()
        self.erh_electricity_default = IrrigationParameter()
        self.transportation_loss_default = IrrigationParameter()
        self.pumping_efficiency_default = IrrigationParameter()

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        try:
            self.ef_default = ipcc.IrrigationPhaseData.objects.get(fuel_type=self.module.fuel_type)
        except ipcc.IrrigationPhaseData.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "ef_t2")
            if missing_scenarios:
                raise ValueError(f"Emission Factor for {self.module.fuel_type.name} is missing in the following scenarios: {', '.join(missing_scenarios)}")

        try:
            self.pressure_default = ipcc.IrrigationPressureRequirement.objects.get(irrigation_system_type=self.module.irrigation_system_type)
        except ipcc.IrrigationPressureRequirement.DoesNotExist:
            if self.module.average_pressure_t2 is None:
                raise ValueError(f"Pressure Requirement for {self.module.irrigation_system_type.name} is missing. Please provide a tier 2 value.")

        try:
            self.pumping_efficiency_default = IrrigationParameter.objects.get(name="PUMPING_EFFICIENCY")
        except IrrigationParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "pumping_efficiency_t2")
            if missing_scenarios:
                raise ValueError(f"Pumping Efficiency is missing. Please provide a tier 2 value for the following scenarios: {', '.join(missing_scenarios)}")

        self.erh_electricity_default: IrrigationParameter = utils.get_or_raise(IrrigationParameter, {"name": "ERH_ELECTRICITY"}, f"Could not find ERH_ELECTRICITY")
        self.transportation_loss_default: IrrigationParameter = utils.get_or_raise(IrrigationParameter, {"name": "TRANSPORTATION_LOSS"}, f"Could not find TRANSPORTATION_LOSS")

    def calculate(self) -> list[Result]:
        self.get_defaults()

        self.inputs_start = {
            "ef_co2_default": self.ef_default.co2_emissions,
            "ef_co2_tier_2": self.module.ef_co2_t2_start,
            "ef_ch4_default": self.ef_default.ch4_emissions,
            "ef_ch4_tier_2": self.module.ef_ch4_t2_start,
            "ef_n2o_default": self.ef_default.n2o_emissions,
            "ef_n2o_tier_2": self.module.ef_n2o_t2_start,
            "total_dynamic_head_tier_2": self.module.total_dynamic_head_t2,
            "average_pressure_default": self.pressure_default.avg_pressure,
            "average_pressure_tier_2": self.module.average_pressure_t2,
            "pumping_efficiency_default": self.pumping_efficiency_default.value,
            "pumping_efficiency_tier_2": self.module.pumping_efficiency_t2_start,
            "erh_electricity": self.erh_electricity_default.value,
            "fuel_net_calorific_values": self.ef_default.calorific_value,
            "fuel_density": self.ef_default.density,
            "depth": self.module.well_depth,
            "units_start": self.module.ha_start,
            "units_end": 0,
            "rate_type": self.activity.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "transportation_loss": self.transportation_loss_default.value if self.module.fuel_type.name == "Electricity" else 0,
            "gwir": self.module.gross_irrigation_water_start,
            "delay": self.activity.delay,
        }

        self.math_start = OperationPhaseIrrigation(**self.inputs_start)
        self.math_start.calculate_emissions()

        self.inputs_w = {
            "ef_co2_default": self.ef_default.co2_emissions,
            "ef_co2_tier_2": self.module.ef_co2_t2_w,
            "ef_ch4_default": self.ef_default.ch4_emissions,
            "ef_ch4_tier_2": self.module.ef_ch4_t2_w,
            "ef_n2o_default": self.ef_default.n2o_emissions,
            "ef_n2o_tier_2": self.module.ef_n2o_t2_w,
            "total_dynamic_head_tier_2": self.module.total_dynamic_head_t2,
            "average_pressure_default": self.pressure_default.avg_pressure,
            "average_pressure_tier_2": self.module.average_pressure_t2,
            "pumping_efficiency_default": self.pumping_efficiency_default.value,
            "pumping_efficiency_tier_2": self.module.pumping_efficiency_t2_w,
            "erh_electricity": self.erh_electricity_default.value,
            "fuel_net_calorific_values": self.ef_default.calorific_value,
            "fuel_density": self.ef_default.density,
            "depth": self.module.well_depth,
            "units_start": 0,
            "units_end": self.module.ha_w,
            "rate_type": self.activity.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "transportation_loss": self.transportation_loss_default.value if self.module.fuel_type.name == "Electricity" else 0,
            "gwir": self.module.gross_irrigation_water_w,
            "delay": self.activity.delay,
        }

        self.math_w = OperationPhaseIrrigation(**self.inputs_w)
        self.math_w.calculate_emissions()

        self.inputs_wo = {
            "ef_co2_default": self.ef_default.co2_emissions,
            "ef_co2_tier_2": self.module.ef_co2_t2_wo,
            "ef_ch4_default": self.ef_default.ch4_emissions,
            "ef_ch4_tier_2": self.module.ef_ch4_t2_wo,
            "ef_n2o_default": self.ef_default.n2o_emissions,
            "ef_n2o_tier_2": self.module.ef_n2o_t2_wo,
            "total_dynamic_head_tier_2": self.module.total_dynamic_head_t2,
            "average_pressure_default": self.pressure_default.avg_pressure,
            "average_pressure_tier_2": self.module.average_pressure_t2,
            "pumping_efficiency_default": self.pumping_efficiency_default.value,
            "pumping_efficiency_tier_2": self.module.pumping_efficiency_t2_wo,
            "erh_electricity": self.erh_electricity_default.value,
            "fuel_net_calorific_values": self.ef_default.calorific_value,
            "fuel_density": self.ef_default.density,
            "depth": self.module.well_depth,
            "units_start": 0,
            "units_end": self.module.ha_wo,
            "rate_type": self.activity.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "transportation_loss": self.transportation_loss_default.value if self.module.fuel_type.name == "Electricity" else 0,
            "gwir": self.module.gross_irrigation_water_wo,
            "delay": self.activity.delay,
        }

        self.math_wo = OperationPhaseIrrigation(**self.inputs_wo)
        self.math_wo.calculate_emissions()

        self.results_start = self.math_start.result if self.math_start else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_start.plot_emissions_and_aggregate_by_activity("irrigation_phase_start")
            self.results_w.plot_emissions_and_aggregate_by_activity("irrigation_phase_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("irrigation_phase_wo")

        results_tuple = (self.results_w + self.results_start, self.results_wo + self.results_start)

        return results_tuple


class CoastalWetlandCalculator(BaseCalculator):
    """
    Calculates the emissions of the coastal wetland
    """

    def __init__(self, input) -> None:
        super().__init__(input)
        self.module: CoastalWetland

        self.agb = ipcc.CoastalAGB()
        self.bgb = ipcc.CoastalBGB()
        self.litter = ipcc.CoastalLitter()
        self.dw = ipcc.CoastalDeadwood()
        self.soil_1m = ipcc.DefaultSoilCarbonStock()
        self.ef_drainage = ipcc.DrainageEmissionFactor()
        self.pc_c_lost_excavation = CoastalWetlandParameter()
        self.rewetting_c = ipcc.RewettingCarbonFactor()
        self.rewetting_ch4 = ipcc.RewettingMethaneFactor()

        self.soil_type_name = ""

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        cm = {
            "climate": self.climate,
            "moisture": self.moisture,
        }

        self.soil_type_name = self.module.soil_type_t2.name if self.module.soil_type_t2 else "Mineral"
        self.salinity_type = self.module.avg_salinity_t2 if self.module.avg_salinity_t2 else SalinityType.objects.get(value=">18")

        try:
            self.agb = ipcc.CoastalAGB.objects.get(**cm, land_use_type=self.module.land_use_type)
        except ipcc.CoastalAGB.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "agb_t2")
            if missing_scenarios:
                raise ValueError(f"AGB for {self.module.land_use_type.name} is missing. Please provide a tier 2 value for the following scenarios: {', '.join(missing_scenarios)}")

        try:
            self.bgb = ipcc.CoastalBGB.objects.get(**cm, land_use_type=self.module.land_use_type)
        except ipcc.CoastalBGB.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "bgb_t2")
            if missing_scenarios:
                raise ValueError(f"BGB for {self.module.land_use_type.name} is missing. Please provide a tier 2 value for the following scenarios: {', '.join(missing_scenarios)}")

        try:
            self.litter = ipcc.CoastalLitter.objects.get(**cm, land_use_type=self.module.land_use_type)
        except ipcc.CoastalLitter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "litter_t2")
            if missing_scenarios:
                raise ValueError(f"Litter for {self.module.land_use_type.name} is missing. Please provide a tier 2 value for the following scenarios: {', '.join(missing_scenarios)}")

        try:
            self.dw = ipcc.CoastalDeadwood.objects.get(**cm, land_use_type=self.module.land_use_type)
        except ipcc.CoastalDeadwood.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "deadwood_t2")
            if missing_scenarios:
                raise ValueError(f"Deadwood for {self.module.land_use_type.name} is missing. Please provide a tier 2 value for the following scenarios: {', '.join(missing_scenarios)}")

        try:
            self.soil_1m = ipcc.DefaultSoilCarbonStock.objects.get(**cm, land_use_type=self.module.land_use_type, soil_type__name=self.soil_type_name)
        except ipcc.DefaultSoilCarbonStock.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "soc_t2")
            if missing_scenarios:
                raise ValueError(f"Soil 1m for {self.module.land_use_type.name} is missing. Please provide a tier 2 value for the following scenarios: {', '.join(missing_scenarios)}")

        try:
            self.ef_drainage = ipcc.DrainageEmissionFactor.objects.get(**cm, land_use_type=self.module.land_use_type)
        except ipcc.DrainageEmissionFactor.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "drainage_ef_t2")
            if missing_scenarios:
                raise ValueError(f"Drainage Emission Factor for {self.module.land_use_type.name} is missing. Please provide a tier 2 value for the following scenarios: {', '.join(missing_scenarios)}")

        try:
            self.pc_c_lost_excavation = CoastalWetlandParameter.objects.get(name="PERCENTAGE_C_LOST_EXCAVATION")
        except CoastalWetlandParameter.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "pc_c_lost_after_excavation_t2")
            if missing_scenarios:
                raise ValueError(f"Percentage C Lost After Excavation is missing. Please provide a tier 2 value for the following scenarios: {', '.join(missing_scenarios)}")

        try:
            self.rewetting_c = ipcc.RewettingCarbonFactor.objects.get(**cm, land_use_type=self.module.land_use_type, soil_type__name=self.soil_type_name)
        except ipcc.RewettingCarbonFactor.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "co2_rewetting_t2")
            if missing_scenarios:
                raise ValueError(f"Rewetting CO2 for {self.odule.land_use_type.name}, {self.project.climate.name}, {self.project.moisture.name}. Please insert tier 2 values for the relevant scenarios.")

        try:
            self.rewetting_ch4 = ipcc.RewettingMethaneFactor.objects.get(**cm, land_use_type=self.module.land_use_type, salinity=self.salinity_type)
        except ipcc.RewettingMethaneFactor.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "ch4_rewetting_t2")
            if missing_scenarios:
                raise ValueError(f"Rewetting CH4 for {self.module.land_use_type.name}, {self.project.climate.name}, {self.project.moisture.name}. Please insert tier 2 values for the relevant scenarios.")

    def calculate(self) -> Result:
        """
        Calculates the emissions of the coastal wetland
        """

        self.get_defaults()

        if self.module.is_with():
            self.inputs_w = {
                "maximum_area_for_water_management": self.area,
                "area_drained_start": self.module.area_under_drainage_start,
                "area_drained_end": self.module.area_under_drainage_w,
                "rate_type": self.module.activity.change_rate.name,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "agb_default": self.agb.value,
                "bgb_default": self.bgb.value,
                "litter_default": self.litter.value,
                "deadwood_default": self.dw.value,
                "soil_1m_default": self.soil_1m.value,
                "EF_drainage_default": self.ef_drainage.value,
                "agb_tier_2": self.module.agb_t2_w,
                "bgb_tier_2": self.module.bgb_t2_w,
                "litter_tier_2": self.module.litter_t2_w,
                "deadwood_tier_2": self.module.deadwood_t2_w,
                "soil_1m_tier_2": self.module.soc_t2_w,
                "EF_drainage_tier_2": self.module.drainage_ef_t2_w,
                "area_excavated_start": self.module.drained_area_excavated_start,
                "area_excavated_end": self.module.drained_area_excavated_w,
                "area_revegated_start": self.module.area_w_restored_vegetation_start,
                "area_revegated_end": self.module.area_w_restored_vegetation_w,
                "percentage_c_lost_excavation_default": self.pc_c_lost_excavation.value,
                "percentage_c_lost_excavation_tier_2": self.module.pc_c_lost_after_excavation_t2_w,
                "ef_rewetting_carbon_default": self.rewetting_c.value,
                "ef_rewetting_methane_default": self.rewetting_ch4.value,
                "ef_rewetting_carbon_tier_2": self.module.co2_rewetting_t2_start,
                "ef_rewetting_methane_tier_2": self.module.ch4_rewetting_t2_w,
                "soil_type": self.module.avg_salinity_t2.value if self.module.avg_salinity_t2 else None,
                "methane_constant": self.project.gwp.ch4,
                "delay": self.activity.delay,
            }

            self.math_w = MathCoastalWetland(**self.inputs_w)
            self.math_w.calculate_emissions()

        if self.module.is_without():
            self.inputs_wo = {
                "maximum_area_for_water_management": self.area,
                "area_drained_start": self.module.area_under_drainage_start,
                "area_drained_end": self.module.area_under_drainage_wo,
                "rate_type": self.module.activity.change_rate.name,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "agb_default": self.agb.value,
                "bgb_default": self.bgb.value,
                "litter_default": self.litter.value,
                "deadwood_default": self.dw.value,
                "soil_1m_default": self.soil_1m.value,
                "EF_drainage_default": self.ef_drainage.value,
                "agb_tier_2": self.module.agb_t2_wo,
                "bgb_tier_2": self.module.bgb_t2_wo,
                "litter_tier_2": self.module.litter_t2_wo,
                "deadwood_tier_2": self.module.deadwood_t2_wo,
                "soil_1m_tier_2": self.module.soc_t2_wo,
                "EF_drainage_tier_2": self.module.drainage_ef_t2_wo,
                "area_excavated_start": self.module.drained_area_excavated_start,
                "area_excavated_end": self.module.drained_area_excavated_wo,
                "area_revegated_start": self.module.area_w_restored_vegetation_start,
                "area_revegated_end": self.module.area_w_restored_vegetation_wo,
                "percentage_c_lost_excavation_default": self.pc_c_lost_excavation.value,
                "percentage_c_lost_excavation_tier_2": self.module.pc_c_lost_after_excavation_t2_wo,
                "ef_rewetting_carbon_default": self.rewetting_c.value,
                "ef_rewetting_methane_default": self.rewetting_ch4.value,
                "ef_rewetting_carbon_tier_2": self.module.co2_rewetting_t2_wo,
                "ef_rewetting_methane_tier_2": self.module.ch4_rewetting_t2_wo,
                "soil_type": self.module.avg_salinity_t2.value if self.module.avg_salinity_t2 else None,
                "methane_constant": self.project.gwp.ch4,
                "delay": self.activity.delay,
            }

            self.math_wo = MathCoastalWetland(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w, self.results_wo)

        return results_tuple


class WaterbodyCalculator(BaseCalculator):
    """
    Calculator for waterbody modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)
        self.module: Waterbody

        self.methane_emission_factor = ipcc.OtherConstructedWaterbodiesEmissionFactor()
        self.trophic_state_start = ipcc.TrophicStateFactor()
        self.trophic_state_w = ipcc.TrophicStateFactor()
        self.trophic_state_wo = ipcc.TrophicStateFactor()

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        try:
            self.methane_emission_factor = ipcc.OtherConstructedWaterbodiesEmissionFactor.objects.get(climate=self.climate, moisture=self.moisture, waterbody_type=self.module.waterbody_type)
        except ipcc.OtherConstructedWaterbodiesEmissionFactor.DoesNotExist:
            missing_scenarios = utils.find_empty_scenarios(self.module, "ch4_ef_t2")
            if missing_scenarios:
                raise ValueError(f"Methane Emission Factor for {self.module.waterbody_type.name} is missing. Please provide a tier 2 value for the following scenarios: {', '.join(missing_scenarios)}")

        if self.module.is_start():
            try:
                self.trophic_state_start = ipcc.TrophicStateFactor.objects.get(trophic_type=self.module.trophic_type_start)
            except ipcc.TrophicStateFactor.DoesNotExist:
                if self.module.alpha_t2_start is None:
                    raise ValueError(f"Could not find Trophic State Factor for {self.module.trophic_type_start.name}. Please provide a tier 2 value for the starting scenario.")

        if self.module.is_with():
            try:
                self.trophic_state_w = ipcc.TrophicStateFactor.objects.get(trophic_type=self.module.trophic_type_w)
            except ipcc.TrophicStateFactor.DoesNotExist:
                if self.module.alpha_t2_w is None:
                    raise ValueError(f"Could not find Trophic State Factor for {self.module.trophic_type_w.name}. Please provide a tier 2 value for the 'with' scenario.")

        if self.module.is_without():
            try:
                self.trophic_state_wo = ipcc.TrophicStateFactor.objects.get(trophic_type=self.module.trophic_type_wo)
            except ipcc.TrophicStateFactor.DoesNotExist:
                if self.module.alpha_t2_wo is None:
                    raise ValueError(f"Could not find Trophic State Factor for {self.module.trophic_type_wo.name}. Please provide a tier 2 value for the 'without' scenario.")

    def calculate(self) -> Result:
        """
        Calculate emissions for a single Waterbody module.
        """

        module: Waterbody = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        self.get_defaults()

        # Inputs for the starting scenario
        inputs_start = {
            "area_start": module.area,
            "area_end": 0,
            "trophic_state_default": self.trophic_state_start.value,
            "methane_emission_factor_default": self.methane_emission_factor.value,
            "trophic_state_tier_2_start": module.alpha_t2_start,
            "trophic_state_tier_2_end": 0,
            "methane_emission_factor_start_tier_2": module.ch4_ef_t2_start,
            "methane_emission_factor_end_tier_2": 0,
            "methane_constant": project.gwp.ch4,
            "capitalization_time": self.activity.capitalization_years,
            "implementation_time": self.activity.implementation_years,
            "rate_type": module.activity.change_rate.name,
            "chlo_A_start": module.mean_annual_t2_start,
            "chlo_A_end": 0,
            "delay": self.activity.delay,
        }

        self.math_start = MathWaterbodies(**inputs_start)
        self.math_start.calculate_emissions()

        if module.is_with():
            # Inputs for the "with" scenario
            inputs_w = {
                "area_start": 0,
                "area_end": module.area,
                "trophic_state_default": self.trophic_state_w.value,
                "methane_emission_factor_default": self.methane_emission_factor.value,
                "trophic_state_tier_2_start": module.alpha_t2_start,
                "trophic_state_tier_2_end": module.alpha_t2_w,
                "methane_emission_factor_start_tier_2": module.ch4_ef_t2_start,
                "methane_emission_factor_end_tier_2": module.ch4_ef_t2_w,
                "methane_constant": project.gwp.ch4,
                "capitalization_time": self.activity.capitalization_years,
                "implementation_time": self.activity.implementation_years,
                "rate_type": module.activity.change_rate.name,
                "chlo_A_start": module.mean_annual_t2_start,
                "chlo_A_end": module.mean_annual_t2_w,
                "delay": self.activity.delay,
            }

            self.math_w = MathWaterbodies(**inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            # Inputs for the "without" scenario
            inputs_wo = {
                "area_start": 0,
                "area_end": module.area,
                "trophic_state_default": self.trophic_state_wo.value,
                "methane_emission_factor_default": self.methane_emission_factor.value,
                "trophic_state_tier_2_start": module.alpha_t2_start,
                "trophic_state_tier_2_end": module.alpha_t2_wo,
                "methane_emission_factor_start_tier_2": module.ch4_ef_t2_start,
                "methane_emission_factor_end_tier_2": module.ch4_ef_t2_wo,
                "methane_constant": project.gwp.ch4,
                "capitalization_time": self.activity.capitalization_years,
                "implementation_time": self.activity.implementation_years,
                "rate_type": module.activity.change_rate.name,
                "chlo_A_start": module.mean_annual_t2_start,
                "chlo_A_end": module.mean_annual_t2_wo,
                "delay": self.activity.delay,
            }

            self.math_wo = MathWaterbodies(**inputs_wo)
            self.math_wo.calculate_emissions()

        # Collect results
        self.results_start = self.math_start.result if self.math_start else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        # Combine results
        results_tuple = (self.results_w + self.results_start, self.results_wo + self.results_start)

        return results_tuple


class OrganicSoilCalculator(BaseCalculator):

    def __init__(self, input) -> None:
        super().__init__(input)

        self.module: OrganicSoil

        self.ef_onsite_start = ipcc.OrganicSoilDrainageEmissionFactor()
        self.ef_onsite_w = ipcc.OrganicSoilDrainageEmissionFactor()
        self.ef_onsite_wo = ipcc.OrganicSoilDrainageEmissionFactor()

        self.ef_offsite_start = ipcc.OrganicSoilDrainageEmissionFactor()
        self.ef_offsite_w = ipcc.OrganicSoilDrainageEmissionFactor()
        self.ef_offsite_wo = ipcc.OrganicSoilDrainageEmissionFactor()

        self.dry_matter_w = ipcc.OrganicSoilFuelConsumption()
        self.dry_matter_wo = ipcc.OrganicSoilFuelConsumption()

        self.fire_ref = ipcc.OrganicSoilGefEmissionFactor()

        self.rewetting_start = ipcc.OrganicSoilRewettingEmissionFactor()
        self.rewetting_w = ipcc.OrganicSoilRewettingEmissionFactor()
        self.rewetting_wo = ipcc.OrganicSoilRewettingEmissionFactor()

        self.onsite_ef_w = ipcc.OrganicSoilDrainageEmissionFactor()
        self.onsite_ef_wo = ipcc.OrganicSoilDrainageEmissionFactor()

        self.offsite_ef_w = ipcc.OrganicSoilDrainageEmissionFactor()
        self.offsite_ef_wo = ipcc.OrganicSoilDrainageEmissionFactor()

        self.conversion_factor_w = ipcc.PeatExtractionConversionFactor()
        self.conversion_factor_wo = ipcc.PeatExtractionConversionFactor()

        self.organic_soil_math_w = None
        self.organic_soil_math_wo = None
        self.peat_extraction_math_w = None
        self.peat_extraction_math_wo = None

        self.organic_soil_inputs_w = {}
        self.organic_soil_inputs_wo = {}
        self.peat_extraction_inputs_w = {}
        self.peat_extraction_inputs_wo = {}

        self.organic_soil_results_w = None
        self.organic_soil_results_wo = None

        self.peat_extraction_results_w = None
        self.peat_extraction_results_wo = None

        self.area_affected_by_module = 0

        self.is_fire_used_w = False
        self.is_fire_used_wo = False

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: OrganicSoil = self.data
        project: Project = module.activity.project
        luc: LandUseChange = module.land_use_change

        if luc:
            module_type_start = luc.module_type_start.name
            module_type_w = luc.module_type_w.name
            module_type_wo = luc.module_type_wo.name
            self.area_affected_by_module = luc.area
        else:
            parent_module, parent_module_type = utils.find_organic_soil_parent_module(module)
            module_type_start = module_type_w = module_type_wo = parent_module_type.name

            self.area_affected_by_module = 0 if module_type_start == "ForestManagement" else parent_module.area

        cm = {
            "climate": project.climate,
            "moisture": project.moisture,
        }

        ##### Organic Soil Inputs #####
        try:
            self.fire_ref = ipcc.OrganicSoilGefEmissionFactor.objects.get(**cm)
        except ipcc.OrganicSoilGefEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Fire Reference for {project.climate.name}, {project.moisture.name}")

        if module.is_start():
            try:
                self.ef_onsite_start = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_start, peat_type=module.peat_type, site_location_type__name="On-Site")
                if self.ef_onsite_start.co2 is None and module.onsite_co2_drainge_t2_start is None:
                    raise ValueError(f"Could not find CO2 value of EF On-Site Start for {module_type_start}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.ef_onsite_start.ch4 is None and module.onsite_ch4_drainge_t2_start is None:
                    raise ValueError(f"Could not find CH4 value of EF On-Site Start for {module_type_start}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.ef_onsite_start.n2o is None and module.onsite_n2o_drainge_t2_start is None:
                    raise ValueError(f"Could not find N2O value of EF On-Site Start for {module_type_start}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.onsite_co2_drainage_t2_start, module.onsite_ch4_drainge_t2_start, module.onsite_n2o_drainage_t2_start])
                if missing_t2_gases:
                    raise ValueError(f"Could not find EF On-Site Start for {module_type_start}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            try:
                self.ef_offsite_start = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_start, peat_type=module.peat_type, site_location_type__name="Off-Site")
                if self.ef_offsite_start.doc is None and module.offsite_doc_drainge_t2_start is None:
                    raise ValueError(f"Could not find DOC value of EF Off-Site Start for {module_type_start}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.ef_offsite_start.ch4 is None and module.offsite_ch4_drainge_t2_start is None:
                    raise ValueError(f"Could not find CH4 value of EF Off-Site Start for {module_type_start}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.offsite_doc_drainge_t2_start, module.offsite_ch4_drainge_t2_start])
                if missing_t2_gases:
                    raise ValueError(f"Could not find EF Off-Site Start for {module_type_start}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            try:
                self.rewetting_start = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=module.peat_type, module_type__name=module_type_start)
                if self.rewetting_start.co2 is None and module.onsite_co2_rewetting_t2_start is None:
                    raise ValueError(f"Could not find CO2 value of Rewetting Start for {module.peat_type.name}, {module_type_start}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.rewetting_start.ch4 is None and module.onsite_ch4_rewetting_t2_start is None:
                    raise ValueError(f"Could not find CH4 value of Rewetting Start for {module.peat_type.name}, {module_type_start}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.rewetting_start.n2o is None and module.onsite_n2o_rewetting_t2_start is None:
                    raise ValueError(f"Could not find N2O value of Rewetting Start for {module.peat_type.name}, {module_type_start}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.rewetting_start.doc is None and module.offsite_doc_rewetting_t2_start is None:
                    raise ValueError(f"Could not find DOC value of Rewetting Start for {module.peat_type.name}, {module_type_start}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.OrganicSoilRewettingEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.onsite_co2_rewetting_t2_start, module.onsite_ch4_rewetting_t2_start, module.onsite_n2o_rewetting_t2_start, module.offsite_doc_rewetting_t2_start])
                if missing_t2_gases:
                    raise ValueError(f"Could not find Rewetting EF Start for {module.peat_type.name}, {module_type_start}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

        if module.is_with():
            try:
                self.ef_onsite_w = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_w, peat_type=module.peat_type, site_location_type__name="On-Site")
                if self.ef_onsite_w.co2 is None and module.onsite_co2_drainge_t2_w is None:
                    raise ValueError(f"Could not find CO2 value of EF On-Site W for {module_type_w}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.ef_onsite_w.ch4 is None and module.onsite_ch4_drainge_t2_w is None:
                    raise ValueError(f"Could not find CH4 value of EF On-Site W for {module_type_w}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.ef_onsite_w.n2o is None and module.onsite_n2o_drainge_t2_w is None:
                    raise ValueError(f"Could not find N2O value of EF On-Site W for {module_type_w}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.onsite_co2_drainge_t2_w, module.onsite_ch4_drainge_t2_w, module.onsite_n2o_drainge_t2_w])
                if missing_t2_gases:
                    raise ValueError(f"Could not find EF On-Site W for {module_type_w}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            try:
                self.ef_offsite_w = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_w, peat_type=module.peat_type, site_location_type__name="Off-Site")
                if self.ef_offsite_w.doc is None and module.offsite_doc_drainge_t2_w is None:
                    raise ValueError(f"Could not find DOC value of EF Off-Site W for {module_type_w}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.ef_offsite_w.ch4 is None and module.offsite_ch4_drainge_t2_w is None:
                    raise ValueError(f"Could not find CH4 value of EF Off-Site W for {module_type_w}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.offsite_doc_drainge_t2_w, module.offsite_ch4_drainge_t2_w])
                if missing_t2_gases:
                    raise ValueError(f"Could not find EF Off-Site W for {module_type_w}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            self.is_fire_used_w = module.fire_type_w is not None
            if self.is_fire_used_w:
                try:
                    self.dry_matter_w = ipcc.OrganicSoilFuelConsumption.objects.get(**cm, fire_type=module.fire_type_w)
                except ipcc.OrganicSoilFuelConsumption.DoesNotExist:
                    if self.module.mean_dry_matter_t2_w is None:
                        raise ValueError(f"Could not find Dry Matter W for {module.fire_type_w.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.rewetting_w = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=module.peat_type, module_type__name=module_type_w)
                if self.rewetting_w.co2 is None and module.onsite_co2_rewetting_t2_w is None:
                    raise ValueError(f"Could not find CO2 value of Rewetting W for {module.peat_type.name}, {module_type_w}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.rewetting_w.ch4 is None and module.onsite_ch4_rewetting_t2_w is None:
                    raise ValueError(f"Could not find CH4 value of Rewetting W for {module.peat_type.name}, {module_type_w}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.rewetting_w.n2o is None and module.onsite_n2o_rewetting_t2_w is None:
                    raise ValueError(f"Could not find N2O value of Rewetting W for {module.peat_type.name}, {module_type_w}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.rewetting_w.doc is None and module.offsite_doc_rewetting_t2_w is None:
                    raise ValueError(f"Could not find DOC value of Rewetting W for {module.peat_type.name}, {module_type_w}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.OrganicSoilRewettingEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.onsite_co2_rewetting_t2_w, module.onsite_ch4_rewetting_t2_w, module.onsite_n2o_rewetting_t2_w, module.offsite_doc_rewetting_t2_w])
                if missing_t2_gases:
                    raise ValueError(f"Could not find Rewetting W for {module.peat_type.name}, {module_type_w}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            try:
                self.onsite_ef_w = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=module.peat_type, site_location_type__name="On-Site")
                if self.onsite_ef_w.co2 is None and module.onsite_co2_peat_t2_w is None:
                    raise ValueError(f"Could not find CO2 value of On-Site EF W for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.onsite_ef_w.n2o is None and module.onsite_n2o_peat_t2_w is None:
                    raise ValueError(f"Could not find N2O value of On-Site EF W for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.onsite_co2_peat_t2_w, module.onsite_n2o_peat_t2_w])
                if missing_t2_gases:
                    raise ValueError(f"Could not find On-Site EF W for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            try:
                self.offsite_ef_w = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=module.peat_type, site_location_type__name="Off-Site")
                if self.offsite_ef_w.doc is None and module.offsite_doc_peat_t2_w is None:
                    raise ValueError(f"Could not find DOC value of Off-Site EF W for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.offsite_ef_w.ch4 is None and module.offsite_ch4_peat_t2_w is None:
                    raise ValueError(f"Could not find CH4 value of Off-Site EF W for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.offsite_doc_peat_t2_w, module.offsite_ch4_peat_t2_w])
                if missing_t2_gases:
                    raise ValueError(f"Could not find Off-Site EF With for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            try:
                self.conversion_factor_w = ipcc.PeatExtractionConversionFactor.objects.get(**cm, peat_type=module.peat_type)
            except ipcc.PeatExtractionConversionFactor.DoesNotExist:
                if module.peat_density_t2_w is None:
                    raise ValueError(f"Could not find Conversion Factor With for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

        if module.is_without():
            try:
                self.ef_onsite_wo = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_wo, peat_type=module.peat_type, site_location_type__name="On-Site")
                if self.ef_onsite_wo.co2 is None and module.onsite_co2_drainge_t2_wo is None:
                    raise ValueError(f"Could not find CO2 value of EF On-Site WO for {module_type_wo}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.ef_onsite_wo.ch4 is None and module.onsite_ch4_drainge_t2_wo is None:
                    raise ValueError(f"Could not find CH4 value of EF On-Site WO for {module_type_wo}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.ef_onsite_wo.n2o is None and module.onsite_n2o_drainge_t2_wo is None:
                    raise ValueError(f"Could not find N2O value of EF On-Site WO for {module_type_wo}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.onsite_co2_drainge_t2_wo, module.onsite_ch4_drainge_t2_wo, module.onsite_n2o_drainge_t2_wo])
                if missing_t2_gases:
                    raise ValueError(f"Could not find EF On-Site WO for {module_type_wo}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            try:
                self.ef_offsite_wo = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_wo, peat_type=module.peat_type, site_location_type__name="Off-Site")
                if self.ef_offsite_wo.doc is None and module.offsite_doc_drainge_t2_wo is None:
                    raise ValueError(f"Could not find DOC value of EF Off-Site WO for {module_type_wo}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.ef_offsite_wo.ch4 is None and module.offsite_ch4_drainge_t2_wo is None:
                    raise ValueError(f"Could not find CH4 value of EF Off-Site WO for {module_type_wo}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.offsite_doc_drainge_t2_wo, module.offsite_ch4_drainge_t2_wo])
                if missing_t2_gases:
                    raise ValueError(f"Could not find EF Off-Site WO for {module_type_wo}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            self.is_fire_used_wo = module.fire_type_wo is not None
            if self.is_fire_used_wo:
                try:
                    self.dry_matter_wo = ipcc.OrganicSoilFuelConsumption.objects.get(**cm, fire_type=module.fire_type_wo)
                except ipcc.OrganicSoilFuelConsumption.DoesNotExist:
                    if self.module.mean_dry_matter_t2_wo is None:
                        raise ValueError(f"Could not find Dry Matter WO for {module.fire_type_wo.name}, {project.climate.name}, {project.moisture.name}")

            try:
                self.rewetting_wo = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=module.peat_type, module_type__name=module_type_wo)
                if self.rewetting_wo.co2 is None and module.onsite_co2_rewetting_t2_wo is None:
                    raise ValueError(f"Could not find CO2 value of Rewetting WO for {module.peat_type.name}, {module_type_wo}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.rewetting_wo.ch4 is None and module.onsite_ch4_rewetting_t2_wo is None:
                    raise ValueError(f"Could not find CH4 value of Rewetting WO for {module.peat_type.name}, {module_type_wo}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.rewetting_wo.n2o is None and module.onsite_n2o_rewetting_t2_wo is None:
                    raise ValueError(f"Could not find N2O value of Rewetting WO for {module.peat_type.name}, {module_type_wo}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.rewetting_wo.doc is None and module.offsite_doc_rewetting_t2_wo is None:
                    raise ValueError(f"Could not find DOC value of Rewetting WO for {module.peat_type.name}, {module_type_wo}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.OrganicSoilRewettingEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.onsite_co2_rewetting_t2_wo, module.onsite_ch4_rewetting_t2_wo, module.onsite_n2o_rewetting_t2_wo, module.offsite_doc_rewetting_t2_wo])
                if missing_t2_gases:
                    raise ValueError(f"Could not find Rewetting WO for {module.peat_type.name}, {module_type_wo}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            ##### Peat Extraction Inputs #####
            try:
                self.onsite_ef_wo = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=module.peat_type, site_location_type__name="On-Site")
                if self.onsite_ef_wo.co2 is None and module.onsite_co2_peat_t2_wo is None:
                    raise ValueError(f"Could not find CO2 value of On-Site EF WO for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.onsite_ef_wo.n2o is None and module.onsite_n2o_peat_t2_wo is None:
                    raise ValueError(f"Could not find N2O value of On-Site EF WO for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.onsite_co2_peat_t2_wo, module.onsite_n2o_peat_t2_wo])
                if missing_t2_gases:
                    raise ValueError(f"Could not find On-Site EF WO for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            try:
                self.offsite_ef_wo = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=module.peat_type, site_location_type__name="Off-Site")
                if self.offsite_ef_wo.doc is None and module.offsite_doc_peat_t2_wo is None:
                    raise ValueError(f"Could not find DOC value of Off-Site EF WO for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
                if self.offsite_ef_wo.ch4 is None and module.offsite_ch4_peat_t2_wo is None:
                    raise ValueError(f"Could not find CH4 value of Off-Site EF WO for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")
            except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
                missing_t2_gases = filter(lambda x: x is None, [module.offsite_doc_peat_t2_wo, module.offsite_ch4_peat_t2_wo])
                if missing_t2_gases:
                    raise ValueError(f"Could not find Off-Site EF WO for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}. Please provide tier 2 values.")

            try:
                self.conversion_factor_wo = ipcc.PeatExtractionConversionFactor.objects.get(**cm, peat_type=module.peat_type)
            except ipcc.PeatExtractionConversionFactor.DoesNotExist:
                raise ValueError(f"Could not find Conversion Factor WO for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")

    def calculate(self) -> Result:
        super().calculate(self.module)

        input: OrganicSoil = self.data
        project: Project = input.activity.project

        self.get_defaults()

        ##### Calculate Emissions #####

        self.results_w = MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        self.organic_soil_math_w = None
        self.organic_soil_math_wo = None
        self.peat_extraction_math_w = None
        self.peat_extraction_math_wo = None

        self.organic_soil_inputs_w = {
            "fire_boolean_end": input.fire_type_w is not None,
            "fire_periodicity_end": input.soil_fire_periodicity_w,
            "area_affected_by_action_end": self.area_affected_by_module,
            "dry_matter_ref_fire": self.dry_matter_w.value if self.is_fire_used_w else None,
            "dry_matter_tier_2_fire": input.mean_dry_matter_t2_w,
            "percentage_area_burned_end": input.soil_fire_impact_percentage_w,
            "ef_co2_ref_fire": self.fire_ref.co2,
            "ef_co2_tier_2_fire": input.fire_on_soil_co2_t2_w,
            "ef_co_ref_fire": self.fire_ref.co,
            "ef_co_tier_2_fire": input.fire_on_soil_co_t2_w,
            "ef_ch4_ref_fire": self.fire_ref.ch4,
            "ef_ch4_tier_2_fire": input.fire_on_soil_ch4_t2_w,
            "methane_constant": project.gwp.ch4,
            "rate_type": input.activity.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "nitrous_constant": project.gwp.n2o,
            "ef_doc_ref_drainage_initial": self.ef_offsite_start.doc,
            "ef_doc_tier_2_drainage_initial": input.offsite_doc_drainge_t2_start,
            "area_drained_start": input.drainage_area_start,
            "area_drained_end": input.drainage_area_w,
            "ef_co2_ref_drainage_initial": self.ef_onsite_start.co2,
            "ef_co2_tier_2_drainage_initial": input.onsite_co2_drainge_t2_start,
            "percentage_ditches_start": input.ditches_area_start,
            "percentage_ditches_end": input.ditches_area_w,
            "ef_ch4_onsite_ref_drainage_initial": self.ef_onsite_start.ch4,
            "ef_ch4_onsite_tier_2_drainage_initial": input.onsite_ch4_drainge_t2_start,
            "ef_ch4_offsite_ref_drainage_initial": self.ef_offsite_start.ch4,
            "ef_ch4_offsite_tier_2_drainage_initial": input.offsite_ch4_drainge_t2_start,
            "ef_n2o_ref_drainage_initial": self.ef_onsite_start.n2o,
            "ef_n2o_tier_2_drainage_initial": input.onsite_n2o_drainge_t2_start,
            "ef_doc_ref_drainage_final": self.ef_offsite_w.doc,
            "ef_doc_tier_2_drainage_final": input.offsite_doc_drainge_t2_w,
            "ef_co2_ref_drainage_final": self.ef_onsite_w.co2,
            "ef_co2_tier_2_drainage_final": input.onsite_co2_drainge_t2_w,
            "ef_ch4_onsite_ref_drainage_final": self.ef_onsite_w.ch4,
            "ef_ch4_onsite_tier_2_drainage_final": input.onsite_ch4_drainge_t2_w,
            "ef_ch4_offsite_ref_drainage_final": self.ef_offsite_w.ch4,
            "ef_ch4_offsite_tier_2_drainage_final": input.offsite_ch4_drainge_t2_w,
            "ef_n2o_ref_drainage_final": self.ef_onsite_w.n2o,
            "ef_n2o_tier_2_drainage_final": input.onsite_n2o_drainge_t2_w,
            "ef_doc_rewetting_initial": self.rewetting_start.doc,
            "ef_doc_rewetting_initial_tier_2": input.offsite_doc_rewetting_t2_start,
            "ef_co2_rewetting_initial": self.rewetting_start.co2,
            "ef_co2_rewetting_initial_tier_2": input.onsite_co2_rewetting_t2_start,
            "ef_ch4_rewetting_initial": self.rewetting_start.ch4,
            "ef_ch4_rewetting_initial_tier_2": input.onsite_ch4_rewetting_t2_start,
            "ef_n2o_rewetting_initial": self.rewetting_start.n2o,
            "ef_n2o_rewetting_initial_tier_2": input.onsite_n2o_rewetting_t2_start,
            "ef_doc_rewetting_final": self.rewetting_w.doc,
            "ef_doc_rewetting_final_tier_2": input.offsite_doc_rewetting_t2_w,
            "ef_co2_rewetting_final": self.rewetting_w.co2,
            "ef_co2_rewetting_final_tier_2": input.onsite_co2_rewetting_t2_w,
            "ef_ch4_rewetting_final": self.rewetting_w.ch4,
            "ef_ch4_rewetting_final_tier_2": input.onsite_ch4_rewetting_t2_w,
            "ef_n2o_rewetting_final": self.rewetting_w.n2o,
            "ef_n2o_rewetting_final_tier_2": input.onsite_n2o_rewetting_t2_w,
            "maximum_area_for_water_management": self.area_affected_by_module,
            "delay": self.activity.delay,
        }

        self.organic_soil_math_w = MathOrganicSoil(**self.organic_soil_inputs_w)
        self.organic_soil_math_w.calculate_emissions()

        if input.peat_area_start:
            self.peat_extraction_inputs_w = {
                "peat_area_start": input.peat_area_start,
                "peat_area_end": input.peat_area_w,
                "percentage_ditches_start": input.peat_ditches_area_start,
                "percentage_ditches_end": input.peat_ditches_area_w,
                "rate_type": input.activity.change_rate.name,
                "ef_co2_tier_2_start": self.onsite_ef_w.co2,
                "ef_co2_tier_2_end": input.onsite_co2_peat_t2_w,
                "ef_ch4_onsite_tier_2_start": self.onsite_ef_w.ch4,
                "ef_ch4_onsite_tier_2_end": None,
                "ef_n2o_tier_2_start": self.onsite_ef_w.n2o,
                "ef_n2o_tier_2_end": input.onsite_n2o_peat_t2_w,
                "ef_doc_tier_2_start": self.offsite_ef_w.doc,
                "ef_doc_tier_2_end": input.offsite_doc_peat_t2_w,
                "ef_ch4_offsite_tier_2_start": self.offsite_ef_w.ch4,
                "ef_ch4_offsite_tier_2_end": input.offsite_ch4_peat_t2_w,
                "methane_constant": project.gwp.ch4,
                "nitrous_constant": project.gwp.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "conversion_factor_volume": self.conversion_factor_w.volume,
                "peat_density_tier_2_start": input.peat_density_t2_w,
                "conversion_factor_weight": self.conversion_factor_w.weight,
                "peat_extraction_height_start": input.peat_extraction_height_start,
                "peat_extraction_height_end": input.peat_extraction_height_w,
                "delay": self.activity.delay,
            }

            self.peat_extraction_math_w = MathPeatExtraction(**self.peat_extraction_inputs_w)
            self.peat_extraction_math_w.calculate_emissions()

        self.organic_soil_inputs_wo = {
            "fire_boolean_end": input.fire_type_wo is not None,
            "fire_periodicity_end": input.soil_fire_periodicity_wo,
            "area_affected_by_action_end": self.area_affected_by_module,
            "dry_matter_ref_fire": self.dry_matter_wo.value if self.is_fire_used_wo else None,
            "dry_matter_tier_2_fire": input.mean_dry_matter_t2_wo,
            "percentage_area_burned_end": input.soil_fire_impact_percentage_wo,
            "ef_co2_ref_fire": self.fire_ref.co2,
            "ef_co2_tier_2_fire": input.fire_on_soil_co2_t2_wo,
            "ef_co_ref_fire": self.fire_ref.co,
            "ef_co_tier_2_fire": input.fire_on_soil_co_t2_wo,
            "ef_ch4_ref_fire": self.fire_ref.ch4,
            "ef_ch4_tier_2_fire": input.fire_on_soil_ch4_t2_wo,
            "methane_constant": project.gwp.ch4,
            "rate_type": input.activity.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "nitrous_constant": project.gwp.n2o,
            "ef_doc_ref_drainage_initial": self.ef_offsite_start.doc,
            "ef_doc_tier_2_drainage_initial": input.offsite_doc_drainge_t2_start,
            "area_drained_start": input.drainage_area_start,
            "area_drained_end": input.drainage_area_wo,
            "ef_co2_ref_drainage_initial": self.ef_onsite_start.co2,
            "ef_co2_tier_2_drainage_initial": input.onsite_co2_drainge_t2_start,
            "percentage_ditches_start": input.ditches_area_start,
            "percentage_ditches_end": input.ditches_area_wo,
            "ef_ch4_onsite_ref_drainage_initial": self.ef_onsite_start.ch4,
            "ef_ch4_onsite_tier_2_drainage_initial": input.onsite_ch4_drainge_t2_start,
            "ef_ch4_offsite_ref_drainage_initial": self.ef_offsite_start.ch4,
            "ef_ch4_offsite_tier_2_drainage_initial": input.offsite_ch4_drainge_t2_start,
            "ef_n2o_ref_drainage_initial": self.ef_onsite_start.n2o,
            "ef_n2o_tier_2_drainage_initial": input.onsite_n2o_drainge_t2_start,
            "ef_doc_ref_drainage_final": self.ef_offsite_wo.doc,
            "ef_doc_tier_2_drainage_final": input.offsite_doc_drainge_t2_wo,
            "ef_co2_ref_drainage_final": self.ef_onsite_wo.co2,
            "ef_co2_tier_2_drainage_final": input.onsite_co2_drainge_t2_wo,
            "ef_ch4_onsite_ref_drainage_final": self.ef_onsite_wo.ch4,
            "ef_ch4_onsite_tier_2_drainage_final": input.onsite_ch4_drainge_t2_wo,
            "ef_ch4_offsite_ref_drainage_final": self.ef_offsite_wo.ch4,
            "ef_ch4_offsite_tier_2_drainage_final": input.offsite_ch4_drainge_t2_wo,
            "ef_n2o_ref_drainage_final": self.ef_onsite_wo.n2o,
            "ef_n2o_tier_2_drainage_final": input.onsite_n2o_drainge_t2_wo,
            "ef_doc_rewetting_initial": self.rewetting_start.doc,
            "ef_doc_rewetting_initial_tier_2": input.offsite_doc_rewetting_t2_start,
            "ef_co2_rewetting_initial": self.rewetting_start.co2,
            "ef_co2_rewetting_initial_tier_2": input.onsite_co2_rewetting_t2_start,
            "ef_ch4_rewetting_initial": self.rewetting_start.ch4,
            "ef_ch4_rewetting_initial_tier_2": input.onsite_ch4_rewetting_t2_start,
            "ef_n2o_rewetting_initial": self.rewetting_start.n2o,
            "ef_n2o_rewetting_initial_tier_2": input.onsite_n2o_rewetting_t2_start,
            "ef_doc_rewetting_final": self.rewetting_wo.doc,
            "ef_doc_rewetting_final_tier_2": input.offsite_doc_rewetting_t2_wo,
            "ef_co2_rewetting_final": self.rewetting_wo.co2,
            "ef_co2_rewetting_final_tier_2": input.onsite_co2_rewetting_t2_wo,
            "ef_ch4_rewetting_final": self.rewetting_wo.ch4,
            "ef_ch4_rewetting_final_tier_2": input.onsite_ch4_rewetting_t2_wo,
            "ef_n2o_rewetting_final": self.rewetting_wo.n2o,
            "ef_n2o_rewetting_final_tier_2": input.onsite_n2o_rewetting_t2_wo,
            "maximum_area_for_water_management": self.area_affected_by_module,
            "delay": self.activity.delay,
        }

        self.organic_soil_math_wo = MathOrganicSoil(**self.organic_soil_inputs_wo)
        self.organic_soil_math_wo.calculate_emissions()

        if input.peat_area_start:
            self.peat_extraction_inputs_wo = {
                "hectares_start": input.peat_area_start,
                "hectares_end": input.peat_area_wo,
                "percentage_ditches_start": input.peat_ditches_area_start,
                "percentage_ditches_end": input.peat_ditches_area_wo,
                "rate_type": input.activity.change_rate.name,
                "ef_co2_onsite_ref": self.onsite_ef_wo.co2,
                "ef_co2_onsite_tier_2": input.onsite_co2_peat_t2_wo,
                "ef_ch4_onsite_ref": self.onsite_ef_wo.ch4,
                "ef_ch4_onsite_tier_2": None,  # NOTE: Set to None, why?
                "ef_n2o_onsite_ref": self.onsite_ef_wo.n2o,
                "ef_n2o_onsite_tier_2": input.onsite_n2o_peat_t2_wo,
                "ef_doc_offsite_ref": self.offsite_ef_wo.doc,
                "ef_doc_offsite_tier_2": input.offsite_doc_peat_t2_wo,
                "ef_ch4_offsite_ref": self.offsite_ef_wo.ch4,
                "ef_ch4_offsite_tier_2": input.offsite_ch4_peat_t2_wo,
                "methane_constant": project.gwp.ch4,
                "nitrous_constant": project.gwp.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "weight_peat": self.conversion_factor_wo.weight,
                "mass_tonnes_tier_2": input.peat_density_t2_wo,
                "conversion_factor_volume": self.conversion_factor_wo.volume,
                "c_fraction_ref": 1,  # TODO: Should be conversion_factor_wo.volume,
                "extraction_height_start": input.peat_extraction_height_start,
                "extraction_height_end": input.peat_extraction_height_wo,
                "delay": self.activity.delay,
            }

            self.peat_extraction_math_wo = MathPeatExtraction(**self.peat_extraction_inputs_wo)
            self.peat_extraction_math_wo.calculate_emissions()

        self.inputs_w = {
            "organic_soil": self.organic_soil_inputs_w,
            "peat_extraction": self.peat_extraction_inputs_w,
        }

        self.inputs_wo = {
            "organic_soil": self.organic_soil_inputs_wo,
            "peat_extraction": self.peat_extraction_inputs_wo,
        }

        self.organic_soil_results_w = self.organic_soil_math_w.result if self.organic_soil_math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.organic_soil_results_wo = self.organic_soil_math_wo.result if self.organic_soil_math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if input.peat_area_start:
            self.peat_extraction_results_w = self.peat_extraction_math_w.result if self.peat_extraction_math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
            self.peat_extraction_results_wo = self.peat_extraction_math_wo.result if self.peat_extraction_math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

            self.results_w += self.organic_soil_results_w + self.peat_extraction_results_w
            self.results_wo += self.organic_soil_results_wo + self.peat_extraction_results_wo

        else:
            self.results_w += self.organic_soil_results_w
            self.results_wo += self.organic_soil_results_wo

        results_tuple = (self.results_w, self.results_wo)

        return results_tuple


class ForestManagementCalculator(LandModuleCalculator):
    """
    # TODO: Review
    """

    def __init__(self, module: LandModule) -> None:
        super().__init__(module)

        self.forest: ForestManagement = self.luc.forestmanagement if self.luc else self.module

        self.is_afforestation_w = False
        self.is_afforestation_wo = False

        self.has_t2_growth_start = False
        self.has_t2_growth_w = False
        self.has_t2_growth_wo = False

        self.mangroves_data = ipcc.DataOnMangrove()
        self.litter_dw = ipcc.LitterDeadwoodCarbonStock()
        self.agb_growth = ipcc.ForestManagementAGBGrowth()
        self.bgb_before_20_yrs = ipcc.ForestManagementBGB()
        self.bgb_after_20_yrs = ipcc.ForestManagementBGB()
        self.agb_under_20_yrs = ipcc.ForestManagementAGB()
        self.agb_over_20_yrs = ipcc.ForestManagementAGB()

        self.agb_max_w = None
        self.agb_growth_over_20_w = None
        self.agb_growth_under_20_w = None
        self.agb_start_w = None
        self.litter_dw_start_w = None
        self.litter_dw_max_w = None

        self.agb_max_wo = None
        self.agb_growth_over_20_wo = None
        self.agb_growth_under_20_wo = None
        self.agb_start_wo = None
        self.litter_dw_start_wo = None
        self.litter_dw_max_wo = None

        self.agb_under_20_w = None
        self.agb_over_20_w = None

        self.agb_under_20_wo = None
        self.agb_over_20_wo = None

        self.disturbances = None

    def get_defaults(self, calculate=False) -> dict:
        land_use_type = self.module.land_use_type_start

        self.is_afforestation_w = self.luc and self.luc.module_type_w.class_name == "ForestManagement" and self.luc.module_type_start.class_name != "ForestManagement"
        self.is_afforestation_wo = self.luc and self.luc.module_type_wo.class_name == "ForestManagement" and self.luc.module_type_start.class_name != "ForestManagement"

        self.has_t2_growth_start = self.forest.agb_growth_rate_gt_20_yrs_t2_start and self.forest.agb_growth_rate_le_20_yrs_t2_start
        self.has_t2_growth_w = self.forest.agb_growth_rate_gt_20_yrs_t2_w and self.forest.agb_growth_rate_le_20_yrs_t2_w
        self.has_t2_growth_wo = self.forest.agb_growth_rate_gt_20_yrs_t2_wo and self.forest.agb_growth_rate_le_20_yrs_t2_wo

        crluft = {
            "climate": self.climate,
            "region": self.region,
            "land_use_type": land_use_type,
            "forest_type": self.forest.forest_type,
        }

        AGB_GROWTH_NOT_FOUND = f"AGB Growth not found for ({self.forest.forest_type.name}) {land_use_type.name} in {self.climate.name} climate, {self.region.name} region. Please insert t2 values for AGB Growth Rate for all scenarios."
        BGB_UNDER_20_NOT_FOUND = f"BGB (under 20 years) not found for ({self.forest.forest_type.name}) {land_use_type.name} in {self.climate.name} climate, {self.region.name} region. Please insert t2 values for BGB (under 20 years) for all scenarios."
        BGB_OVER_20_NOT_FOUND = f"BGB (over 20 years) not found for ({self.forest.forest_type.name}) {land_use_type.name} in {self.climate.name} climate, {self.region.name} region. Please insert t2 values for BGB (over 20 years) for all scenarios."
        LITTER_DW_NOT_FOUND = f"Litter/Deadwood Carbon Stock reference value not found for ({self.forest.forest_type.name}) {land_use_type.name} in {self.climate.name} climate, {self.region.name} region."

        # NOTE: For non-forest is ipcc.AfforestationCombustionFactor (used in OLUC?)
        self.combustion_factor_w: ipcc.ForestCombustionFactor = utils.get_or_raise(ipcc.ForestCombustionFactor, {"land_use_type": self.module.land_use_type_w, "climate": self.climate, "forest_type": self.forest.forest_type}, f"Combustion Factor W not found for {self.module.land_use_type_w.name}, {self.climate.name}, {self.forest.forest_type.name}")
        self.combustion_factor_wo: ipcc.ForestCombustionFactor = utils.get_or_raise(ipcc.ForestCombustionFactor, {"land_use_type": self.module.land_use_type_wo, "climate": self.climate, "forest_type": self.forest.forest_type}, f"Combustion Factor WO not found for {self.module.land_use_type_wo.name}, {self.climate.name}, {self.forest.forest_type.name}")

        if self.forest.land_use_type_start.name == "Mangrove Forest":
            try:
                self.mangroves_data = ipcc.DataOnMangrove.objects.get(climate=self.climate, moisture=self.climate)
            except ipcc.DataOnMangrove.DoesNotExist:
                pass

        try:
            self.litter_dw = ipcc.LitterDeadwoodCarbonStock.objects.get(climate=self.climate, forest_type=self.forest.forest_type, land_use_type=land_use_type)
        except ipcc.LitterDeadwoodCarbonStock.DoesNotExist:
            raise ValueError(LITTER_DW_NOT_FOUND)

        try:
            self.agb_growth = ipcc.ForestManagementAGBGrowth.objects.get(**crluft)
        except ipcc.ForestManagementAGBGrowth.DoesNotExist:
            self.agb_growth = None

        if not self.agb_growth and (not self.has_t2_growth_start or not self.has_t2_growth_w or not self.has_t2_growth_wo):
            raise ValueError(AGB_GROWTH_NOT_FOUND)

        before_2_yrs = self.agb_growth.value_upto_20_years
        after_20_yrs = self.agb_growth.value_after_20_years

        self.bgb_before_20_yrs = ipcc.ForestManagementBGB.objects.get_max_below_threshold(**crluft, threshold=before_2_yrs)
        if not self.bgb_before_20_yrs:
            raise ValueError(BGB_UNDER_20_NOT_FOUND)

        self.bgb_after_20_yrs = ipcc.ForestManagementBGB.objects.get_max_below_threshold(**crluft, threshold=after_20_yrs)
        if not self.bgb_after_20_yrs:
            raise ValueError(BGB_OVER_20_NOT_FOUND)

        self.agb_under_20 = self.forest.get_agb_growth_ref(land_use_type=land_use_type, from_year=0)
        self.agb_under_20_w = self.agb_under_20_wo = self.agb_under_20

        # Check AGB under 20 years for with scenario
        if self.module.is_with() and (self.agb_under_20 is None or any(x is None for x in [self.agb_under_20.agb_min, self.agb_under_20.agb_max])) and self.forest.agb_t2_w is None:
            raise ValueError(f"Reference values for AGB under 20 years for {self.climate.name} {self.forest.forest_condition_type.name} {self.forest.forest_type.name} {land_use_type.name}, in {self.region.name} are missing. Please fill the relevant tier 2 values.")

        # Check AGB under 20 years for without scenario
        if self.module.is_without() and (self.agb_under_20 is None or any(x is None for x in [self.agb_under_20.agb_min, self.agb_under_20.agb_max])) and self.forest.agb_t2_wo is None:
            raise ValueError(f"Reference values for AGB under 20 years for {self.climate.name} {self.forest.forest_condition_type.name} {self.forest.forest_type.name} {land_use_type.name}, in {self.region.name} are missing. Please fill the relevant tier 2 values.")

        # Check AGB growth under 20 years for with scenario
        if self.module.is_with() and (self.agb_under_20 is None or any(x is None for x in [self.agb_under_20.agb_growth_min, self.agb_under_20.agb_growth_max])) and self.forest.agb_growth_rate_le_20_yrs_t2_w is None:
            raise ValueError(f"Reference values for AGB growth under 20 years for {self.climate.name} {self.forest.forest_condition_type.name} {self.forest.forest_type.name} {land_use_type.name}, in {self.region.name} are missing. Please fill the relevant tier 2 values.")

        # Check AGB growth under 20 years for without scenario
        if self.module.is_without() and (self.agb_under_20 is None or any(x is None for x in [self.agb_under_20.agb_growth_min, self.agb_under_20.agb_growth_max])) and self.forest.agb_growth_rate_le_20_yrs_t2_wo is None:
            raise ValueError(f"Reference values for AGB growth under 20 years for {self.climate.name} {self.forest.forest_condition_type.name} {self.forest.forest_type.name} {land_use_type.name}, in {self.region.name} are missing. Please fill the relevant tier 2 values.")

        self.agb_over_20 = self.forest.get_agb_growth_ref(land_use_type=land_use_type, from_year=21 if "Secondary" in self.forest.forest_condition_type.name else 0)
        self.agb_over_20_w = self.agb_over_20_wo = self.agb_over_20

        # Check AGB over 20 years for with scenario
        if self.module.is_with() and (self.agb_over_20 is None or any(x is None for x in [self.agb_over_20.agb_min, self.agb_over_20.agb_max])) and self.forest.agb_t2_w is None:
            raise ValueError(f"Reference values for AGB over 20 years for {self.climate.name} {self.forest.forest_condition_type.name} {self.forest.forest_type.name} {land_use_type.name}, in {self.region.name} are missing. Please fill the relevant tier 2 values.")

        # Check AGB over 20 years for without scenario
        if self.module.is_without() and (self.agb_over_20 is None or any(x is None for x in [self.agb_over_20.agb_min, self.agb_over_20.agb_max])) and self.forest.agb_t2_wo is None:
            raise ValueError(f"Reference values for AGB over 20 years for {self.climate.name} {self.forest.forest_condition_type.name} {self.forest.forest_type.name} {land_use_type.name}, in {self.region.name} are missing. Please fill the relevant tier 2 values.")

        # Check AGB growth over 20 years for with scenario
        if self.module.is_with() and (self.agb_over_20 is None or any(x is None for x in [self.agb_over_20.agb_growth_min, self.agb_over_20.agb_growth_max])) and self.forest.agb_growth_rate_gt_20_yrs_t2_w is None:
            raise ValueError(f"Reference values for AGB growth over 20 years for {self.climate.name} {self.forest.forest_condition_type.name} {self.forest.forest_type.name} {land_use_type.name}, in {self.region.name} are missing. Please fill the relevant tier 2 values.")

        # Check AGB growth over 20 years for without scenario
        if self.module.is_without() and (self.agb_over_20 is None or any(x is None for x in [self.agb_over_20.agb_growth_min, self.agb_over_20.agb_growth_max])) and self.forest.agb_growth_rate_gt_20_yrs_t2_wo is None:
            raise ValueError(f"Reference values for AGB growth over 20 years for {self.climate.name} {self.forest.forest_condition_type.name} {self.forest.forest_type.name} {land_use_type.name}, in {self.region.name} are missing. Please fill the relevant tier 2 values.")

        # START - Reference Values for forest remaining forest
        self.agb_max_w = statistics.mean([self.agb_over_20_w.agb_min, self.agb_over_20_w.agb_max]) if all([self.agb_over_20_w.agb_min, self.agb_over_20_w.agb_max]) else self.forest.agb_t2_w
        self.agb_growth_over_20_w = statistics.mean([self.agb_over_20_w.agb_growth_max, self.agb_over_20_w.agb_growth_min]) if all([self.agb_over_20_w.agb_growth_max, self.agb_over_20_w.agb_growth_min]) else self.forest.agb_growth_rate_gt_20_yrs_t2_w
        self.agb_growth_under_20_w = 0
        self.agb_start_w = self.agb_max_w
        self.litter_dw_start_w = self.litter_dw
        self.litter_dw_max_w = self.litter_dw

        # TODO: What reference values do I choose for the start scenario?
        # TODO: Add litter start, litter end. Affo -> start=0, end=reference_values. Forest -> start=reference_values, end=refernce_values

        self.agb_max_wo = statistics.mean([self.agb_over_20_wo.agb_min, self.agb_over_20_wo.agb_max]) if all([self.agb_over_20_wo.agb_min, self.agb_over_20_wo.agb_max]) else self.forest.agb_t2_wo
        self.agb_growth_over_20_wo = statistics.mean([self.agb_over_20_wo.agb_growth_max, self.agb_over_20_wo.agb_growth_min]) if all([self.agb_over_20_wo.agb_growth_max, self.agb_over_20_wo.agb_growth_min]) else self.forest.agb_growth_rate_gt_20_yrs_t2_wo
        self.agb_growth_under_20_wo = 0
        self.agb_start_wo = self.agb_max_wo
        self.litter_dw_start_wo = self.litter_dw
        self.litter_dw_max_wo = self.litter_dw
        # END - Reference Values for forest remaining forest

        if self.is_afforestation_w:
            self.agb_max_w = statistics.mean([self.agb_over_20_w.agb_min, self.agb_over_20_w.agb_max]) if self.activity.implementation_years > 20 else statistics.mean([self.agb_under_20_w.agb_min, self.agb_under_20_w.agb_max]) if all([self.agb_under_20_w.agb_min, self.agb_under_20_w.agb_max]) else self.forest.agb_t2_w
            self.agb_growth_under_20_w = statistics.mean([self.agb_under_20_w.agb_growth_max, self.agb_under_20_w.agb_growth_min]) if all([self.agb_under_20_w.agb_growth_max, self.agb_under_20_w.agb_growth_min]) else self.forest.agb_growth_rate_le_20_yrs_t2_w
            self.agb_start_w = 0
            self.litter_dw_start_w = SimpleNamespace(litter=0, dw=0)

        if self.is_afforestation_wo:
            self.agb_max_wo = statistics.mean([self.agb_over_20_wo.agb_min, self.agb_over_20_wo.agb_max]) if self.activity.implementation_years > 20 else statistics.mean([self.agb_under_20_wo.agb_min, self.agb_under_20_wo.agb_max]) if all([self.agb_under_20_wo.agb_min, self.agb_under_20_wo.agb_max]) else self.forest.agb_t2_wo
            self.agb_growth_under_20_wo = statistics.mean([self.agb_under_20_wo.agb_growth_max, self.agb_under_20_wo.agb_growth_min]) if all([self.agb_under_20_wo.agb_growth_max, self.agb_under_20_wo.agb_growth_min]) else self.forest.agb_growth_rate_le_20_yrs_t2_wo
            self.agb_start_wo = 0
            self.litter_dw_start_wo = SimpleNamespace(litter=0, dw=0)

        self.disturbances: list[ForestDisturbance] = self.module.disturbances.all()

        return super().get_defaults(calculate)

    def calculate(self) -> Result:
        super().calculate(self)

        self.get_defaults()

        if self.module.is_with():

            self.inputs_w = [
                self.activity.capitalization_years,
                self.activity.implementation_years,
                self.module.activity.change_rate.name,
                0,
                self.area,
                self.forest.rotation_length_yrs_w,
                self.forest.rotation_start_year_t2_w,
                self.forest.rotation_percentage_biomass_for_energy_w,
                self.bgb_before_20_yrs.threshold,
                self.bgb_before_20_yrs.value,
                self.bgb_after_20_yrs.value,
                self.forest.bgb_growth_rate_le_20_yrs_t2_w,
                self.forest.bgb_growth_rate_gt_20_yrs_t2_w,
                self.agb_start_w,
                self.forest.agb_t2_w,
                self.agb_growth_under_20_w,
                self.forest.agb_growth_rate_le_20_yrs_t2_w,
                self.agb_growth_over_20_w,
                self.forest.agb_growth_rate_gt_20_yrs_t2_w,
                self.agb_max_w,
                None,  # TODO: max_bgb_value ?? Unused in math model
                list(self.disturbances.values_list("recurrence_yrs_w", flat=True)),
                list(self.disturbances.values_list("percentage_biomass_destruction_w", flat=True)),
                list(self.disturbances.values_list("start_year_t2_w", flat=True)),
                self.forest.logging_recurrence_yrs_w,
                self.forest.logging_percentage_agb_logged_w,
                self.forest.logging_percentage_biomass_for_energy_w,
                self.forest.logging_start_year_t2_w,
                self.litter_dw.litter,
                self.litter_dw_start_w.litter,
                self.litter_dw_max_w.litter,
                self.forest.litter_t2_w,
                self.litter_dw.dw,
                self.litter_dw_start_w.dw,
                self.litter_dw_max_w.dw,
                self.forest.deadwood_t2_w,
                self.soc_start.value,
                self.soc_w.value,
                self.module.soc_t2_start,
                self.module.soc_t2_w,
                self.fmg_start.value,
                self.fmg_w.value,
                self.forest.fmg_t2_start,
                self.forest.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                self.forest.flu_t2_start,
                self.forest.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                self.forest.fi_t2_start,
                self.forest.fi_t2_w,
                self.project.gwp.ch4,
                self.project.gwp.n2o,
                self.combustion_factor_w.value,
                self.combustion_factor_w.ch4,
                self.combustion_factor_w.n2o,
                self.combustion_factor_w.co2,
                utils.MANGROVE_FACTOR if self.mangroves_data is not None else utils.NON_MANGROVE_FACTOR,
                self.forest.average_yearly_degradation_percentage_w,
                self.som.value,
                self.project.gwp.n2o,
                self.project.gwp.ch4,
                self.activity.delay,
            ]

            log.debug(f"Forest inputs with: {self.inputs_w}")

            self.math_w = MathForestManagement(*self.inputs_w)
            self.math_w.calculate_emissions()

        if self.module.is_without():

            self.inputs_wo = [
                self.activity.capitalization_years,
                self.activity.implementation_years,
                self.module.activity.change_rate.name,
                0,
                self.area,
                self.forest.rotation_length_yrs_wo,
                self.forest.rotation_start_year_t2_wo,
                self.forest.rotation_percentage_biomass_for_energy_wo,
                self.bgb_before_20_yrs.threshold,
                self.bgb_before_20_yrs.value,
                self.bgb_after_20_yrs.value,
                self.forest.bgb_growth_rate_le_20_yrs_t2_wo,
                self.forest.bgb_growth_rate_gt_20_yrs_t2_wo,
                self.agb_start_wo,
                self.forest.agb_t2_wo,
                self.agb_growth_under_20_wo,
                self.forest.agb_growth_rate_le_20_yrs_t2_wo,
                self.agb_growth_over_20_wo,
                self.forest.agb_growth_rate_gt_20_yrs_t2_wo,
                self.agb_max_wo,
                None,  # TODO: max_bgb_value ?? Unused in math model
                list(self.disturbances.values_list("recurrence_yrs_wo", flat=True)),
                list(self.disturbances.values_list("percentage_biomass_destruction_wo", flat=True)),
                list(self.disturbances.values_list("start_year_t2_wo", flat=True)),
                self.forest.logging_recurrence_yrs_wo,
                self.forest.logging_percentage_agb_logged_wo,
                self.forest.logging_percentage_biomass_for_energy_wo,
                self.forest.logging_start_year_t2_wo,
                self.litter_dw.litter,
                self.litter_dw_start_wo.litter,
                self.litter_dw_max_wo.litter,
                self.forest.litter_t2_wo,
                self.litter_dw.dw,
                self.litter_dw_start_wo.dw,
                self.litter_dw_max_wo.dw,
                self.forest.deadwood_t2_wo,
                self.soc_start.value,
                self.soc_wo.value,
                self.module.soc_t2_start,
                self.module.soc_t2_wo,
                self.fmg_start.value,
                self.fmg_wo.value,
                self.forest.fmg_t2_start,
                self.forest.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                self.forest.flu_t2_start,
                self.forest.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                self.forest.fi_t2_start,
                self.forest.fi_t2_wo,
                self.project.gwp.ch4,
                self.project.gwp.n2o,
                self.combustion_factor_wo.value,
                self.combustion_factor_wo.ch4,
                self.combustion_factor_wo.n2o,
                self.combustion_factor_wo.co2,
                utils.MANGROVE_FACTOR if self.mangroves_data is not None else utils.NON_MANGROVE_FACTOR,
                self.forest.average_yearly_degradation_percentage_w,
                self.som.value,
                self.project.gwp.n2o,
                self.project.gwp.ch4,
                self.activity.delay,
            ]

            log.debug(f"Forest inputs without: {self.inputs_wo}")

            self.math_wo = MathForestManagement(*self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if PLOT_GRAPHS:
            self.results_w.plot_emissions_and_aggregate_by_activity("forest_w")
            self.results_wo.plot_emissions_and_aggregate_by_activity("forest_wo")

        results_tuple = (self.results_w, self.results_wo)

        return results_tuple

    def defaults(self) -> DefaultData:
        return super().defaults()


class OtherLandCalculator(LandModuleCalculator):
    """
    Calculator for annual cropping modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

    def calculate(self) -> Result:
        self.get_defaults()

        if self.module.is_start():
            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_w.soc_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_W,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_w.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_w.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_w.fi_t2_w,
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "calculate_biomass": self.calculate_biomass_start_w,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }

            log.debug(f"Inputs start w: {self.inputs_start_w}")

            self.math_start_w = MathNotCultivatedLand(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_wo.soc_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_WO,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_wo.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_wo.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_wo.fi_t2_wo,
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "calculate_biomass": self.calculate_biomass_start_wo,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }

            log.debug(f"Inputs start wo: {self.inputs_start_wo}")

            self.math_start_wo = MathNotCultivatedLand(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if self.module.is_with():
            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_w.soc_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_W,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_w.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_w.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_w.fi_t2_w,
                "delay": self.activity.delay,
                "calculate_biomass": self.calculate_biomass_w,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }

            log.debug(f"Inputs w: {self.inputs_w}")

            self.math_w = MathNotCultivatedLand(**self.inputs_w)
            self.math_w.calculate_emissions()

        if self.module.is_without():
            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_wo.soc_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_WO,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_wo.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_wo.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_wo.fi_t2_wo,
                "delay": self.activity.delay,
                "calculate_biomass": self.calculate_biomass_wo,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }

            log.debug(f"Inputs wo: {self.inputs_wo}")

            self.math_wo = MathNotCultivatedLand(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w + self.results_start_w, self.results_wo + self.results_start_wo)

        return results_tuple


class SetAsideCalculator(LandModuleCalculator):
    """
    Calculator for annual cropping modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)
        self.module: SetAside

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

    def calculate(self) -> Result:
        self.get_defaults()

        if self.module.is_start():
            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_w.soc_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_W,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_w.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_w.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_w.fi_t2_w,
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "calculate_biomass": self.calculate_biomass_start_w,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }

            self.math_start_w = MathNotCultivatedLand(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_wo.soc_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_START_WO,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_wo.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_wo.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_wo.fi_t2_wo,
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "calculate_biomass": self.calculate_biomass_start_wo,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }

            self.math_start_wo = MathNotCultivatedLand(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if self.module.is_with():
            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_w.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_w.soc_t2_w,
                "calculate_soc_som": CALCULATE_SOC_SOM_W,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_w.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_w.fmg_t2_w,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_w.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_w.flu_t2_w,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_w.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_w.fi_t2_w,
                "delay": self.activity.delay,
                "calculate_biomass": self.calculate_biomass_w,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }

            self.math_w = MathNotCultivatedLand(**self.inputs_w)
            self.math_w.calculate_emissions()

        if self.module.is_without():
            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": self.project.gwp.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc_start.value,
                "soc_end_default": self.soc_wo.value,
                "soc_start_tier_2": self.module_start.soc_t2_start,
                "soc_end_tier_2": self.module_wo.soc_t2_wo,
                "calculate_soc_som": CALCULATE_SOC_SOM_WO,
                "fmg_start_default": self.fmg_start.value,
                "fmg_end_default": self.fmg_wo.value,
                "fmg_start_tier_2": self.module_start.fmg_t2_start,
                "fmg_end_tier_2": self.module_wo.fmg_t2_wo,
                "flu_start_default": self.flu_start.value,
                "flu_end_default": self.flu_wo.value,
                "flu_start_tier_2": self.module_start.flu_t2_start,
                "flu_end_tier_2": self.module_wo.flu_t2_wo,
                "fi_start_default": self.fi_start.value,
                "fi_end_default": self.fi_wo.value,
                "fi_start_tier_2": self.module_start.fi_t2_start,
                "fi_end_tier_2": self.module_wo.fi_t2_w,
                "delay": self.activity.delay,
                "calculate_biomass": self.calculate_biomass_wo,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }

            self.math_wo = MathNotCultivatedLand(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w + self.results_start_w, self.results_wo + self.results_start_wo)

        return results_tuple
