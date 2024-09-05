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
from math_model.no_time_dependency_final.annuals import AnnualCropland
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
    PerennialCropping as PerennialCropland,
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
    AnnualCropping,
    Aquaculture,
    AquacultureParameter,
    BiomassModule,
    Building,
    Climate,
    CoastalWetland,
    CoastalWetlandParameter,
    Country,
    DegradedLand,
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
    PerennialCropping,
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
)

CALCULATE_SOC_SOM_START_W = False
CALCULATE_SOC_SOM_START_WO = False
CALCULATE_SOC_SOM_W = True
CALCULATE_SOC_SOM_WO = True


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
            return Result(*result).breakdown(by=aggregate_by)

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

    @abstractmethod
    def calculate(self, input: Module, aggregate_by=BreakdownTypes.TOTAL) -> Result:
        """
        Calculate emissions for a single module.
        """

        if input.__class__ == LandUseChange or input.luc:
            luc: LandUseChange = input if input.__class__ == LandUseChange else input.luc
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

        self.soc: ipcc.SoilOrganicCarbon | SimpleNamespace = SimpleNamespace(value=0)
        self.som: ipcc.NitrousEmissionFactor | SimpleNamespace = SimpleNamespace(value=0)

        self.fi_start: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=1)
        self.fmg_start: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=1)
        self.flu_start: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=1)
        self.fi_w: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=1)
        self.fmg_w: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=1)
        self.flu_w: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=1)
        self.fi_wo: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=1)
        self.fmg_wo: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=1)
        self.flu_wo: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=1)

        self.module: LandModule | SingleBiomassModule = module
        self.luc: LandUseChange = self.module.land_use_change
        self.activity: Activity = getattr(module, "parent", module).activity
        self.project: Project = self.activity.project

        self.climate: Climate = self.activity.climate_t2 or self.project.climate
        self.moisture: Moisture = self.activity.moisture_t2 or self.project.moisture
        self.region: Region = self.project.country.region
        self.change_rate: ChangeRate = self.activity.change_rate

        self.area = self.luc.area if self.luc else getattr(module, "parent", module).area

        self.module_start = self.module_w = self.module_wo = self.module

        self.module_start: LandModule | SingleBiomassModule
        self.module_w: LandModule | SingleBiomassModule
        self.module_wo: LandModule | SingleBiomassModule

        if self.luc:
            self.module_start, self.module_w, self.module_wo = self.luc.get_modules()

    def calculate(self, module: Module, aggregate_by=BreakdownTypes.TOTAL) -> Result:
        return super().calculate(module, aggregate_by)

    def get_defaults(self, calculate=False) -> dict:

        climate_flt = {"climate": self.project.climate}
        moisture_flt = {"moisture": self.project.moisture}
        soil_flt = {"soil_type": self.project.soil_type}

        self.soc = ipcc.SoilOrganicCarbon.objects.filter(**climate_flt, **moisture_flt, **soil_flt).first()

        missing_scenarios = []

        if not self.soc:
            if self.module.is_start() and self.module.soc_t2_start is None:
                missing_scenarios.append("Start")
            if self.module.is_with() and self.module.soc_t2_w is None:
                missing_scenarios.append("With")
            if self.module.is_without() and self.module.soc_t2_wo is None:
                missing_scenarios.append("Without")

            if missing_scenarios:
                raise Exception(f"SOC for {self.project.climate.name} climate, {self.project.moisture.name} moisture, and {self.project.soil_type.name} soil type is missing. Please insert T2 values for the following scenarios: {', '.join(missing_scenarios)}")

        self.soc_start = getattr(self, "soc", SimpleNamespace(value=self.module.soc_t2_start))
        self.soc_w = getattr(self, "soc", SimpleNamespace(value=self.module.soc_t2_w))
        self.soc_wo = getattr(self, "soc", SimpleNamespace(value=self.module.soc_t2_wo))

        self.som = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {self.project.moisture.name} moisture does not exist")

        self.fi_start = get_fi_data(self.module_start, self.project.climate, self.project.moisture, utils.ScenarioTypes.START)
        self.fmg_start = get_fmg_data(self.module_start, self.project.climate, self.project.moisture, utils.ScenarioTypes.START)
        self.flu_start = get_flu_data(self.module_start, self.project.climate, self.project.moisture, utils.ScenarioTypes.START)
        self.fi_w = get_fi_data(self.module_w, self.project.climate, self.project.moisture, utils.ScenarioTypes.WITH)
        self.fmg_w = get_fmg_data(self.module_w, self.project.climate, self.project.moisture, utils.ScenarioTypes.WITH)
        self.flu_w = get_flu_data(self.module_w, self.project.climate, self.project.moisture, utils.ScenarioTypes.WITH)
        self.fi_wo = get_fi_data(self.module_wo, self.project.climate, self.project.moisture, utils.ScenarioTypes.WITHOUT)
        self.fmg_wo = get_fmg_data(self.module_wo, self.project.climate, self.project.moisture, utils.ScenarioTypes.WITHOUT)
        self.flu_wo = get_flu_data(self.module_wo, self.project.climate, self.project.moisture, utils.ScenarioTypes.WITHOUT)


class LandUseChangeCalculator(BaseCalculator):
    """
    Calculator for land use change modules.
    """

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)

    def luc_based_calculation(self, module_start: Module, module_end: Module, aggregate_by=BreakdownTypes.TOTAL) -> Result:
        if type(module_start) == ForestManagement:
            return DeforestationCalculator(module_start).calculate()

        if type(module_end) == ForestManagement:
            return ForestManagementCalculator(module_end).calculate()

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

        # module_start = module_start.get(land_use_change=luc)
        # module_w = module_w.get(land_use_change=luc)
        # module_wo = module_wo.get(land_use_change=luc)

        # TODO: DeforestationCalculator now expects the ForestManagement module only. Refactor the calculator accordingly (check T2 values!)
        # results_start = CalculatorFactory().calculate_result(module_start, aggregate_by=aggregate_by)
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
                forest.get_biomass_t2(utils.ScenarioTypes.START),
                project.gw_potential.n2o,
                project.gw_potential.ch4,
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
                forest.get_biomass_t2(utils.ScenarioTypes.START),
                project.gw_potential.n2o,
                project.gw_potential.ch4,
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
            ]

            math_wo = MathDeforestation(*self.inputs_wo)
            math_wo.calculate_emissions()

        res_w = math_w.result if math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        res_wo = math_wo.result if math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        res_w.plot_emissions_and_aggregate_by_activity("with")

        return (res_w, res_wo)

    def defaults(self) -> DefaultData:
        self.calculate()

        module: CoastalWetland = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        math_start = MathCoastalWetland(*self.inputs_start)
        math_start_defaults = math_start.evaluate_tier_2_defaults()
        defaults_start.update(math_start_defaults.start)
        defaults_start.update(math_start_defaults.other)

        if is_with(module):
            math_w = MathCoastalWetland(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.start)
            defaults_w.update(math_w_defaults.other)

        if is_without(module):
            math_wo = MathCoastalWetland(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.start)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


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

        module_start: BiomassModule | LandModule = getattr(module.activity, luc.module_type_start.class_name.lower(), None).first()
        module_w: BiomassModule | LandModule = getattr(module.activity, luc.module_type_w.class_name.lower(), None).first()
        module_wo: BiomassModule | LandModule = getattr(module.activity, luc.module_type_wo.class_name.lower(), None).first()

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
            luc_w = module_start.land_use_type_w if module_start.land_use_type_w else LandUseType.objects.get(name=luc.module_type_w.name)
        except LandUseType.DoesNotExist:
            raise Exception(f"LandUseType for {luc.module_type_w.name} does not exist")

        try:
            luc_wo = module_start.land_use_type_wo if module_start.land_use_type_wo else LandUseType.objects.get(name=luc.module_type_wo.name)
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

        if module.is_with():
            inputs_w = {
                "initial_lu_biomass": biomass_initial.value,
                "initial_lu_biomass_tier_2": module_start.get_biomass_t2(utils.ScenarioTypes.START),
                "final_lu_biomass": biomass_final_w.value,
                "final_lu_biomass_tier_2": module_w.get_biomass_t2(utils.ScenarioTypes.WITH),
                "c_n_ratio": c_n_ratio,
                "moisture_emission_factor": som.value,
                "combustion_factor": combustion_factor_w.value,
                "emission_factor_nitrous": combustion_factor_w.n2o,
                "emission_factor_methane": combustion_factor_w.ch4,
                "nitrous_constant": module.activity.project.gw_potential.n2o,
                "methane_constant": module.activity.project.gw_potential.ch4,
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

        if module.is_without():
            inputs_wo = {
                "initial_lu_biomass": biomass_initial.value,
                "initial_lu_biomass_tier_2": module_start.get_biomass_t2(utils.ScenarioTypes.START),
                "final_lu_biomass": biomass_final_wo.value,
                "final_lu_biomass_tier_2": module_wo.get_biomass_t2(utils.ScenarioTypes.WITHOUT),
                "c_n_ratio": c_n_ratio,
                "moisture_emission_factor": som.value,
                "combustion_factor": combustion_factor_wo.value,
                "emission_factor_nitrous": combustion_factor_wo.n2o,
                "emission_factor_methane": combustion_factor_wo.ch4,
                "nitrous_constant": module.activity.project.gw_potential.n2o,
                "methane_constant": module.activity.project.gw_potential.ch4,
                "fire_bool": luc.is_fire_used_wo,
                "soc_start_default": soc.value,
                "soc_end_default": soc.value,
                "soc_start_tier_2": module_start.soc_t2_start,
                "soc_end_tier_2": module_wo.soc_t2_wo,
                "fmg_start_default": fmg_start.value,
                "fmg_end_default": fmg_final_wo.value,
                "fmg_start_tier_2": module_start.fmg_t2_start,  # TODO: Start module has 3 fmg (also fi and flu) values. What to choose?
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

        return (res_w, res_wo)

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)


class AnnualCroppingCalculator(BaseCalculator):

    def get_defaults(self, input: Module) -> dict:
        return AnnualCropCalculator(input).get_defaults()

    def calculate(self):
        module: AnnualCropping = self.data

        res_w = MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        res_wo = MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        r_w, r_wo = AnnualCropCalculator(module).calculate()

        res_w += r_w
        res_wo += r_wo

        return (res_w, res_wo)


class AnnualCropCalculator(LandModuleCalculator):
    """
    Calculator for annual cropping modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.biomass_start: SimpleNamespace = SimpleNamespace(value=0)
        self.biomass_w: SimpleNamespace = SimpleNamespace(value=0)
        self.biomass_wo: SimpleNamespace = SimpleNamespace(value=0)
        self.crop_yield_start: SimpleNamespace | ipcc.CropYieldStats = SimpleNamespace(value=0)
        self.crop_yield_w: SimpleNamespace | ipcc.CropYieldStats = SimpleNamespace(value=0)
        self.crop_yield_wo: SimpleNamespace | ipcc.CropYieldStats = SimpleNamespace(value=0)
        self.flu: SimpleNamespace | ipcc.CroplandFLU = SimpleNamespace(value=0)
        self.default_emission_factor_start: SimpleNamespace | ipcc.NitrousEmissionFactor = SimpleNamespace(value=0)
        self.default_emission_factor_w: SimpleNamespace | ipcc.NitrousEmissionFactor = SimpleNamespace(value=0)
        self.default_emission_factor_wo: SimpleNamespace | ipcc.NitrousEmissionFactor = SimpleNamespace(value=0)
        self.burning_emission_factor: SimpleNamespace | ipcc.BurningEmissionFactor = SimpleNamespace(value=0)
        self.minor_burning_emission_factor: SimpleNamespace | ipcc.BurningEmissionFactor = SimpleNamespace(value=0)
        self.fires_start: SimpleNamespace | ipcc.FiresCombustionFactor = SimpleNamespace(value=0)
        self.fires_w: SimpleNamespace | ipcc.FiresCombustionFactor = SimpleNamespace(value=0)
        self.fires_wo: SimpleNamespace | ipcc.FiresCombustionFactor = SimpleNamespace(value=0)
        self.n_estimation_factor_start: SimpleNamespace | ipcc.CropNitrousEstimationDefaultFactor = SimpleNamespace(value=0)
        self.n_estimation_factor_w: SimpleNamespace | ipcc.CropNitrousEstimationDefaultFactor = SimpleNamespace(value=0)
        self.n_estimation_factor_wo: SimpleNamespace | ipcc.CropNitrousEstimationDefaultFactor = SimpleNamespace(value=0)
        self.minor_fires_start: SimpleNamespace | ipcc.FiresCombustionFactor = SimpleNamespace(value=0)
        self.minor_fires_w: SimpleNamespace | ipcc.FiresCombustionFactor = SimpleNamespace(value=0)
        self.minor_fires_wo: SimpleNamespace | ipcc.FiresCombustionFactor = SimpleNamespace(value=0)
        self.minor_n_estimation_factor_start: SimpleNamespace | ipcc.CropNitrousEstimationDefaultFactor = SimpleNamespace(value=0)
        self.minor_n_estimation_factor_w: SimpleNamespace | ipcc.CropNitrousEstimationDefaultFactor = SimpleNamespace(value=0)
        self.minor_n_estimation_factor_wo: SimpleNamespace | ipcc.CropNitrousEstimationDefaultFactor = SimpleNamespace(value=0)
        self.minor_biomass_start: SimpleNamespace = SimpleNamespace(value=0)
        self.minor_biomass_w: SimpleNamespace = SimpleNamespace(value=0)
        self.minor_biomass_wo: SimpleNamespace = SimpleNamespace(value=0)

        self.biomass_ef_start: SimpleNamespace | ipcc.ForestTotalBiomass = SimpleNamespace(value=0)
        self.biomass_ef_w: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)
        self.biomass_ef_wo: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)

        self.residue_availability_t2_start: SimpleNamespace = SimpleNamespace(value=0)
        self.residue_availability_t2_w: SimpleNamespace = SimpleNamespace(value=0)
        self.residue_availability_t2_wo: SimpleNamespace = SimpleNamespace(value=0)

        self.minor_residue_availability_t2_start: SimpleNamespace = SimpleNamespace(value=0)
        self.minor_residue_availability_t2_w: SimpleNamespace = SimpleNamespace(value=0)
        self.minor_residue_availability_t2_wo: SimpleNamespace = SimpleNamespace(value=0)

    def get_defaults(self, calculate=False) -> SimpleNamespace:
        super().get_defaults(calculate)

        module: AnnualCropping = self.data

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
        region_flt = {"continent": self.region}
        moisture_flt = {"moisture": moisture}
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

            self.flu = utils.get_or_raise(ipcc.CroplandFLU, cm | long_term_cultivated_flt, f"CroplandFLU for {lut_start.name} in {climate.name} climate and {moisture.name} moisture does not exist")
            self.fires_start = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_start_flt, f"FiresCombustionFactor for {lut_start.name} does not exist")
            self.n_estimation_factor_start = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_start_flt, f"CropNitrousEstimationDefaultFactor for {lut_start.name} does not exist", method="get_or_grains")
            self.emission_factors_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.crop_yield_start = module.crop_yield_start or utils.get_or_raise(ipcc.CropYieldStats, region_flt | lut_start_flt, f"CropYieldStats for {self.module_start.land_use_type_start.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_region_average").average
            self.biomass_ef_start = utils.get_or_raise(ipcc.ForestTotalBiomass, cm | region_flt | lut_start_flt, f"ForestTotalBiomass for {lut_start.name} in {climate.name} climate, {moisture.name} moisture in {self.project.country.region.name} region does not exist")

            try:
                self.minor_fires_start = ipcc.FiresCombustionFactor.objects.get(land_use_type=minor_lut_start)
                self.minor_n_estimation_factor_start = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_start)
            except Exception:
                self.minor_fires_start = None
                self.minor_n_estimation_factor_start = None

        if module.is_with():
            lut_w = module.land_use_type_w
            minor_lut_w = module.minor_land_use_type_w

            self.flu = utils.get_or_raise(ipcc.CroplandFLU, cm | long_term_cultivated_flt, f"CroplandFLU for {lut_w.name} in {climate.name} climate and {moisture.name} moisture does not exist")
            self.fires_w = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_w_flt, f"FiresCombustionFactor for {lut_w.name} does not exist")
            self.n_estimation_factor_w = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_w_flt, f"CropNitrousEstimationDefaultFactor for {lut_w.name} does not exist", method="get_or_grains")
            self.emission_factors_w = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.crop_yield_w = module.crop_yield_w or utils.get_or_raise(ipcc.CropYieldStats, region_flt | lut_w_flt, f"CropYieldStats for {self.module_w.land_use_type_w.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_region_average").average
            self.biomass_ef_w = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, cm | region_flt | lut_w_flt, f"ForestTotalBiomass for {lut_w.name} in {climate.name} climate, {moisture.name} moisture in {self.project.country.region.name} region does not exist")

            try:
                self.minor_fires_w = ipcc.FiresCombustionFactor.objects.get(land_use_type=minor_lut_w)
                self.minor_n_estimation_factor_w = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_w)
            except Exception:
                self.minor_fires_w = None
                self.minor_n_estimation_factor_w = None

        if module.is_without():
            lut_wo = module.land_use_type_wo
            minor_lut_wo = module.minor_land_use_type_wo

            self.flu = utils.get_or_raise(ipcc.CroplandFLU, cm | long_term_cultivated_flt, f"CroplandFLU for {lut_wo.name} in {climate.name} climate and {moisture.name} moisture does not exist")
            self.fires_wo = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_wo_flt, f"FiresCombustionFactor for {lut_wo.name} does not exist")
            self.n_estimation_factor_wo = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_wo_flt, f"CropNitrousEstimationDefaultFactor for {lut_wo.name} does not exist", method="get_or_grains")
            self.emission_factors_wo = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.crop_yield_wo = module.crop_yield_wo or utils.get_or_raise(ipcc.CropYieldStats, region_flt | lut_wo_flt, f"CropYieldStats for {self.module_wo.land_use_type_wo.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_region_average").average
            self.biomass_ef_wo = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, cm | region_flt | lut_wo_flt, f"ForestTotalBiomass for {lut_wo.name} in {climate.name} climate, {moisture.name} moisture in {self.project.country.region.name} region does not exist")

            try:
                self.minor_fires_wo = ipcc.FiresCombustionFactor.objects.get(land_use_type=lut_wo)
                self.minor_n_estimation_factor_wo = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_wo)
            except Exception:
                self.minor_fires_wo = None
                self.minor_n_estimation_factor_wo = None

    def calculate(self, aggregate_by=BreakdownTypes.TOTAL) -> tuple[MathResult]:
        """
        Calculate emissions for a single AnnualCropping module.
        """
        log.debug("START AnnualCropCalculator.calculate")

        input: AnnualCropping = self.data
        project: Project = input.activity.project
        luc: LandUseChange = input.land_use_change

        change_rate = input.activity.change_rate

        self.get_defaults()

        if input.is_luc_remaining_same():
            log.debug("Is LUC remaining the same")

            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "ef_methane_agr_residues_main": self.burning_emission_factor.ch4 if input.residue_management_type_start.name == "Burned" else None,
                "combustion_factor_main": self.fires_start.value,
                "residue_main_tier_2": self.module_w.biomass_t2_start,
                "n_estimation_slope_main": self.n_estimation_factor_start.slope,
                "n_estimation_intercept_main": self.n_estimation_factor_start.intercept,
                "yield_value_main": self.crop_yield_start,
                "ef_methane_agr_residues_minor": getattr(self.minor_burning_emission_factor, "ch4", None),
                "combustion_factor_minor": getattr(self.minor_fires_start, "value", None),
                "residue_minor_tier_2": input.minor_biomass_factor_t2_start,
                "n_estimation_slope_minor": getattr(self.minor_n_estimation_factor_start, "slope", None),
                "n_estimation_intercept_minor": getattr(self.minor_n_estimation_factor_start, "intercept", None),
                "yield_value_minor": input.minor_yield_start,
                "ef_nitrous_agr_residues_main": self.burning_emission_factor.n2o if input.residue_management_type_start.name == "Burned" else None,
                "retained_main": input.residue_management_type_start.name == "Retained",
                "ef_nitrous_agr_residues_minor": getattr(self.minor_burning_emission_factor, "n2o", None),
                "retained_minor": getattr(input.minor_residue_management_type_start, "name", None) == "Retained",
                "n_content_ag_main": self.n_estimation_factor_start.n_ag_residues,
                "ratio_bg_ag_main": self.n_estimation_factor_start.rs_t,
                "n_content_bg_main": self.n_estimation_factor_start.n_bg_t,
                "n_content_ag_minor": getattr(self.minor_n_estimation_factor_start, "n_ag_residues", None),
                "ratio_bg_ag_minor": getattr(self.minor_n_estimation_factor_start, "rs_t", None),
                "n_content_bg_minor": getattr(self.minor_n_estimation_factor_start, "n_bg_t", None),
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": self.module_w.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }
            log.debug("Inputs start w: %s", self.inputs_start_w)

            self.math_start_w = AnnualCropland(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if input.is_with():
            log.debug("Is with")

            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "ef_methane_agr_residues_main": self.burning_emission_factor.ch4 if input.residue_management_type_w.name == "Burned" else None,
                "combustion_factor_main": self.fires_w.value,
                "residue_main_tier_2": input.biomass_t2_w,
                "n_estimation_slope_main": self.n_estimation_factor_w.slope,
                "n_estimation_intercept_main": self.n_estimation_factor_w.intercept,
                "yield_value_main": self.crop_yield_w,
                "ef_methane_agr_residues_minor": getattr(self.minor_burning_emission_factor, "ch4", None),
                "combustion_factor_minor": getattr(self.minor_fires_w, "value", None),
                "residue_minor_tier_2": input.minor_biomass_factor_t2_w,
                "n_estimation_slope_minor": getattr(self.minor_n_estimation_factor_w, "slope", None),
                "n_estimation_intercept_minor": getattr(self.minor_n_estimation_factor_w, "intercept", None),
                "yield_value_minor": input.minor_yield_w,
                "ef_nitrous_agr_residues_main": self.burning_emission_factor.n2o if input.residue_management_type_w.name == "Burned" else None,
                "retained_main": input.residue_management_type_w.name == "Retained",
                "ef_nitrous_agr_residues_minor": getattr(self.minor_burning_emission_factor, "n2o", None),
                "retained_minor": getattr(input.minor_residue_management_type_w, "name", None) == "Retained",
                "n_content_ag_main": self.n_estimation_factor_w.n_ag_residues,
                "ratio_bg_ag_main": self.n_estimation_factor_w.rs_t,
                "n_content_bg_main": self.n_estimation_factor_w.n_bg_t,
                "n_content_ag_minor": getattr(self.minor_n_estimation_factor_w, "n_ag_residues", None),
                "ratio_bg_ag_minor": getattr(self.minor_n_estimation_factor_w, "rs_t", None),
                "n_content_bg_minor": getattr(self.minor_n_estimation_factor_w, "n_bg_t", None),
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": self.module_w.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }
            log.debug("Inputs w: %s", self.inputs_w)

            self.math_w = AnnualCropland(**self.inputs_w)
            self.math_w.calculate_emissions()

        if input.is_business_as_usual():
            log.debug("Is business as usual")

            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "ef_methane_agr_residues_main": self.burning_emission_factor.ch4 if input.residue_management_type_start.name == "Burned" else None,
                "combustion_factor_main": self.fires_start.value,
                "residue_main_tier_2": self.module_start.biomass_t2_start,
                "n_estimation_slope_main": self.n_estimation_factor_start.slope,
                "n_estimation_intercept_main": self.n_estimation_factor_start.intercept,
                "yield_value_main": self.crop_yield_start,
                "ef_methane_agr_residues_minor": getattr(self.minor_burning_emission_factor, "ch4", None),
                "combustion_factor_minor": getattr(self.minor_fires_start, "value", None),
                "residue_minor_tier_2": input.minor_biomass_factor_t2_start,
                "n_estimation_slope_minor": getattr(self.minor_n_estimation_factor_start, "slope", None),
                "n_estimation_intercept_minor": getattr(self.minor_n_estimation_factor_start, "intercept", None),
                "yield_value_minor": input.minor_yield_start,
                "ef_nitrous_agr_residues_main": self.burning_emission_factor.n2o if input.residue_management_type_start.name == "Burned" else None,
                "retained_main": input.residue_management_type_start.name == "Retained",
                "ef_nitrous_agr_residues_minor": getattr(self.minor_burning_emission_factor, "n2o", None),
                "retained_minor": getattr(input.minor_residue_management_type_start, "name", None) == "Retained",
                "n_content_ag_main": self.n_estimation_factor_start.n_ag_residues,
                "ratio_bg_ag_main": self.n_estimation_factor_start.rs_t,
                "n_content_bg_main": self.n_estimation_factor_start.n_bg_t,
                "n_content_ag_minor": getattr(self.minor_n_estimation_factor_start, "n_ag_residues", None),
                "ratio_bg_ag_minor": getattr(self.minor_n_estimation_factor_start, "rs_t", None),
                "n_content_bg_minor": getattr(self.minor_n_estimation_factor_start, "n_bg_t", None),
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }
            log.debug("Inputs start wo: %s", self.inputs_start_wo)

            self.math_start_wo = AnnualCropland(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if input.is_without():
            log.debug("Is without")

            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "ef_methane_agr_residues_main": self.burning_emission_factor.ch4 if input.residue_management_type_wo.name == "Burned" else None,
                "combustion_factor_main": self.fires_wo.value,
                "residue_main_tier_2": self.module_wo.biomass_t2_wo,
                "n_estimation_slope_main": self.n_estimation_factor_wo.slope,
                "n_estimation_intercept_main": self.n_estimation_factor_wo.intercept,
                "yield_value_main": self.crop_yield_wo,
                "ef_methane_agr_residues_minor": getattr(self.minor_burning_emission_factor, "ch4", None),
                "combustion_factor_minor": getattr(self.minor_fires_wo, "value", None),
                "residue_minor_tier_2": input.minor_biomass_factor_t2_wo,
                "n_estimation_slope_minor": getattr(self.minor_n_estimation_factor_wo, "slope", None),
                "n_estimation_intercept_minor": getattr(self.minor_n_estimation_factor_wo, "intercept", None),
                "yield_value_minor": input.minor_yield_wo,
                "ef_nitrous_agr_residues_main": self.burning_emission_factor.n2o if input.residue_management_type_wo.name == "Burned" else None,
                "retained_main": input.residue_management_type_wo.name == "Retained",
                "ef_nitrous_agr_residues_minor": getattr(self.minor_burning_emission_factor, "n2o", None),
                "retained_minor": getattr(input.minor_residue_management_type_wo, "name", None) == "Retained",
                "n_content_ag_main": self.n_estimation_factor_wo.n_ag_residues,
                "ratio_bg_ag_main": self.n_estimation_factor_wo.rs_t,
                "n_content_bg_main": self.n_estimation_factor_wo.n_bg_t,
                "n_content_ag_minor": getattr(self.minor_n_estimation_factor_wo, "n_ag_residues", None),
                "ratio_bg_ag_minor": getattr(self.minor_n_estimation_factor_wo, "rs_t", None),
                "n_content_bg_minor": getattr(self.minor_n_estimation_factor_wo, "n_bg_t", None),
                "delay": self.activity.delay,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }
            log.debug("Inputs wo: %s", self.inputs_wo)

            self.math_wo = AnnualCropland(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        res_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        res_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        res_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        res_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        log.debug("start_w breakdown")
        res_start_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("start_wo breakdown")
        res_start_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("w breakdown")
        res_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("wo breakdown")
        res_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("END AnnualCropCalculator.calculate")

        return (res_w + res_start_w, res_wo + res_start_wo)


class PerennialCropCalculator(LandModuleCalculator):

    def __init__(self, input) -> None:
        super().__init__(input)

        self.burning_emission_factor: SimpleNamespace | ipcc.BurningEmissionFactor = SimpleNamespace(value=0)
        self.default_emission_factor_start: ipcc.NitrousEmissionFactor | SimpleNamespace = SimpleNamespace(value=0)
        self.default_emission_factor_w: ipcc.NitrousEmissionFactor | SimpleNamespace = SimpleNamespace(value=0)
        self.default_emission_factor_wo: ipcc.NitrousEmissionFactor | SimpleNamespace = SimpleNamespace(value=0)
        self.fires_combustion_factor_start: ipcc.FiresCombustionFactor | SimpleNamespace = SimpleNamespace(value=0)
        self.fires_combustion_factor_w: ipcc.FiresCombustionFactor | SimpleNamespace = SimpleNamespace(value=0)
        self.fires_combustion_factor_wo: ipcc.FiresCombustionFactor | SimpleNamespace = SimpleNamespace(value=0)
        self.ag_default_start: ipcc.PerennialAGB | SimpleNamespace = SimpleNamespace(value=0)
        self.ag_default_w: ipcc.PerennialAGB | SimpleNamespace = SimpleNamespace(value=0)
        self.ag_default_wo: ipcc.PerennialAGB | SimpleNamespace = SimpleNamespace(value=0)
        self.agb_max_c_start: ipcc.PerennialMaxAGB | SimpleNamespace = SimpleNamespace(value=0)
        self.agb_max_c_w: ipcc.PerennialMaxAGB | SimpleNamespace = SimpleNamespace(value=0)
        self.agb_max_c_wo: ipcc.PerennialMaxAGB | SimpleNamespace = SimpleNamespace(value=0)
        self.bg_default_start: ipcc.PerennialBGB | SimpleNamespace = SimpleNamespace(value=0)
        self.bg_default_w: ipcc.PerennialBGB | SimpleNamespace = SimpleNamespace(value=0)
        self.bg_default_wo: ipcc.PerennialBGB | SimpleNamespace = SimpleNamespace(value=0)
        self.biomass_ef_start: ipcc.ForestTotalBiomass | SimpleNamespace = SimpleNamespace(value=0)
        self.biomass_ef_w: ipcc.TotalBiomassAfterDefo | SimpleNamespace = SimpleNamespace(value=0)
        self.biomass_ef_wo: ipcc.TotalBiomassAfterDefo | SimpleNamespace = SimpleNamespace(value=0)

        # Calculated by math model
        self.residue_burned_t2_start: SimpleNamespace = SimpleNamespace(value=0)
        self.residue_burned_t2_w: SimpleNamespace = SimpleNamespace(value=0)
        self.residue_burned_t2_wo: SimpleNamespace = SimpleNamespace(value=0)

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: PerennialCropping = self.data
        climate = self.climate
        moisture = self.moisture
        region = self.region

        savanna_flt = {"category__name": "Savanna and grassland"}
        moisture_flt = {"moisture": moisture}
        climate_flt = {"climate": climate}

        lut_start_flt = {"land_use_type": module.land_use_type_start}
        lut_w_flt = {"land_use_type": module.land_use_type_w}
        lut_wo_flt = {"land_use_type": module.land_use_type_wo}

        cmc = {
            "climate": climate,
            "moisture": moisture,
            "continent": region,
        }

        if module.is_ready() and calculate:
            self.calculate()

            self.residue_burned_t2_start = SimpleNamespace(value=getattr(self.math_start_w, "t_biomass_tier_2_default", 0) or getattr(self.math_start_wo, "t_biomass_tier_2_default", 0))
            self.residue_burned_t2_w = SimpleNamespace(value=getattr(self.math_w, "t_biomass_tier_2_default", 0) or getattr(self.math_wo, "t_biomass_tier_2_default", 0))
            self.residue_burned_t2_wo = SimpleNamespace(value=getattr(self.math_w, "t_biomass_tier_2_default", 0) or getattr(self.math_wo, "t_biomass_tier_2_default", 0))

        self.burning_emission_factor = utils.get_or_raise(ipcc.BurningEmissionFactor, savanna_flt, "BurningEmissionFactor for Savanna and grassland does not exist")
        self.default_fire_periodicity = AnnualCroplandParameter.objects.get(name="default_fire_periodicity")

        if module.is_start():
            self.default_emission_factor_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.fires_combustion_factor_start = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_start_flt, f"FiresCombustionFactor for {module.land_use_type_start.name} does not exist", method="get_or_default")
            self.ag_default_start = utils.get_or_raise(ipcc.PerennialAGB, cmc | lut_start_flt, f"PerennialAGB for {module.land_use_type_start.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.agb_max_c_start = utils.get_or_raise(ipcc.PerennialMaxAGB, climate_flt | lut_start_flt, f"PerennialMaxAGB for {module.land_use_type_start.name} in {climate.name} climate does not exist", method="get_or_default")
            self.bg_default_start = utils.get_or_raise(ipcc.PerennialBGB, cmc | lut_start_flt, f"PerennialBGB for {module.land_use_type_start.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.biomass_ef_start = utils.get_or_raise(ipcc.ForestTotalBiomass, cmc | lut_start_flt, f"ForestTotalBiomass for {module.land_use_type_start.name} in {climate.name} climate, {moisture.name} moisture in {region.name} region does not exist", method="get_or_default")
        if module.is_with():
            self.default_emission_factor_w = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.fires_combustion_factor_w = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_w_flt, f"FiresCombustionFactor for {module.land_use_type_w.name} does not exist", method="get_or_default")
            self.ag_default_w = utils.get_or_raise(ipcc.PerennialAGB, cmc | lut_w_flt, f"PerennialAGB for {module.land_use_type_w.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.agb_max_c_w = utils.get_or_raise(ipcc.PerennialMaxAGB, climate_flt | lut_w_flt, f"PerennialMaxAGB for {module.land_use_type_w.name} in {climate.name} climate does not exist", method="get_or_default")
            self.bg_default_w = utils.get_or_raise(ipcc.PerennialBGB, cmc | lut_w_flt, f"PerennialBGB for {module.land_use_type_w.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.biomass_ef_w = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, cmc | lut_w_flt, f"ForestTotalBiomass for {module.land_use_type_w.name} in {climate.name} climate, {moisture.name} moisture in {region.name} region does not exist", method="get_or_default")
        if module.is_without():
            self.default_emission_factor_wo = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.fires_combustion_factor_wo = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_wo_flt, f"FiresCombustionFactor for {module.land_use_type_wo.name} does not exist")
            self.ag_default_wo = utils.get_or_raise(ipcc.PerennialAGB, cmc | lut_wo_flt, f"PerennialAGB for {module.land_use_type_wo.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.agb_max_c_wo = utils.get_or_raise(ipcc.PerennialMaxAGB, climate_flt | lut_wo_flt, f"PerennialMaxAGB for {module.land_use_type_wo.name} in {climate.name} climate does not exist", method="get_or_default")
            self.bg_default_wo = utils.get_or_raise(ipcc.PerennialBGB, cmc | lut_wo_flt, f"PerennialBGB for {module.land_use_type_wo.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.biomass_ef_wo = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, cmc | lut_wo_flt, f"ForestTotalBiomass for {module.land_use_type_wo.name} in {climate.name} climate, {moisture.name} moisture in {region.name} region does not exist", method="get_or_default")

    def calculate(self, aggregate_by=BreakdownTypes.TOTAL) -> list[Result]:
        """
        Calculate emissions for a single PerennialCropping module.
        """
        log.debug("START PerennialCropCalculator.calculate")

        module: PerennialCropping = self.data
        project = module.activity.project
        activity: Activity = module.activity
        change_rate = activity.change_rate

        self.get_defaults()

        if module.is_luc_remaining_same():
            inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "residue_burnt": module.is_biomass_burned_start,
                "emission_factor_burning_nitrous_residue": self.burning_emission_factor.n2o,
                "ef_nitrous_som": self.som.value,
                "emission_factor_burning_methane": self.burning_emission_factor.ch4,
                "combustion_factor": self.fires_combustion_factor_start.value,
                "fire_periodicity_default": self.default_fire_periodicity.value,
                "fire_periodicity_tier_2": module.fire_periodicity_t2_start,
                "t_biomass_tier_2": module.residue_burned_t2_start,
                "agb_rate_default": self.ag_default_start.value,
                "agb_rate_tier_2": module.ag_t2_start,
                "agb_maximum_c": self.agb_max_c_start.value,
                "bgb_rate_default": self.bg_default_start.value,
                "bgb_rate_tier_2": module.bg_t2_start,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
                "soc_start_tier_2": module.soc_t2_start,
                "soc_end_tier_2": module.soc_t2_w,
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
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }
            log.debug("Inputs start w: %s", inputs_start_w)

            self.math_start_w = PerennialCropland(**inputs_start_w)
            self.math_start_w.calculate_emissions()

        if module.is_business_as_usual():
            inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "residue_burnt": module.is_biomass_burned_start,
                "emission_factor_burning_nitrous_residue": self.burning_emission_factor.n2o,
                "ef_nitrous_som": self.som.value,
                "emission_factor_burning_methane": self.burning_emission_factor.ch4,
                "combustion_factor": self.fires_combustion_factor_start.value,
                "fire_periodicity_default": self.default_fire_periodicity.value,
                "fire_periodicity_tier_2": module.fire_periodicity_t2_start,
                "t_biomass_tier_2": module.residue_burned_t2_start,
                "agb_rate_default": self.ag_default_start.value,
                "agb_rate_tier_2": module.ag_t2_start,
                "agb_maximum_c": self.agb_max_c_start.value,
                "bgb_rate_default": self.bg_default_start.value,
                "bgb_rate_tier_2": module.bg_t2_start,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }
            log.debug("Input start wo: %s", inputs_start_wo)

            self.math_start_wo = PerennialCropland(**inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module.is_with():
            inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "residue_burnt": module.is_biomass_burned_w,
                "emission_factor_burning_nitrous_residue": self.burning_emission_factor.n2o,
                "ef_nitrous_som": self.som.value,
                "emission_factor_burning_methane": self.burning_emission_factor.ch4,
                "combustion_factor": self.fires_combustion_factor_w.value,
                "fire_periodicity_default": self.default_fire_periodicity.value,
                "fire_periodicity_tier_2": module.fire_periodicity_t2_w,
                "t_biomass_tier_2": module.residue_burned_t2_w,
                "agb_rate_default": self.ag_default_w.value,
                "agb_rate_tier_2": module.ag_t2_w,
                "agb_maximum_c": self.agb_max_c_w.value,
                "bgb_rate_default": self.bg_default_w.value,
                "bgb_rate_tier_2": module.bg_t2_w,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }
            log.debug("Inputs w: %s", inputs_w)

            self.math_w = PerennialCropland(**inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "residue_burnt": module.is_biomass_burned_wo,
                "emission_factor_burning_nitrous_residue": self.burning_emission_factor.n2o,
                "ef_nitrous_som": self.som.value,
                "emission_factor_burning_methane": self.burning_emission_factor.ch4,
                "combustion_factor": self.fires_combustion_factor_wo.value,
                "fire_periodicity_default": self.default_fire_periodicity.value,
                "fire_periodicity_tier_2": module.fire_periodicity_t2_wo,
                "t_biomass_tier_2": module.residue_burned_t2_wo,
                "agb_rate_default": self.ag_default_wo.value,
                "agb_rate_tier_2": module.ag_t2_wo,
                "agb_maximum_c": self.agb_max_c_wo.value,
                "bgb_rate_default": self.bg_default_wo.value,
                "bgb_rate_tier_2": module.bg_t2_wo,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }
            log.debug("Inputs wo: %s", inputs_wo)

            self.math_wo = PerennialCropland(**inputs_wo)
            self.math_wo.calculate_emissions()

        results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        log.debug("start_w breakdown")
        results_start_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("start_wo breakdown")
        results_start_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("w breakdown")
        results_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("wo breakdown")
        results_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        results_tuple = (results_w + results_start_w, results_wo + results_start_wo)

        return results_tuple


class PerennialCroppingCalculator(BaseCalculator):
    """
    Calculator for perennial cropping.
    """

    def get_defaults(self, calculate=False) -> dict:
        return PerennialCropCalculator(input).get_defaults(calculate=calculate)

    def calculate(self):
        log.debug("START PerennialCroppingCalculator.calculate")

        module: PerennialCropping = self.data

        res_w = MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        res_wo = MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        r_w, r_wo = PerennialCropCalculator(module).calculate()

        res_w += r_w
        res_wo += r_wo

        log.debug("END PerennialCroppingCalculator.calculate")
        return (res_w, res_wo)


class FloodedRiceSeasonCalculator(LandModuleCalculator):

    def __init__(self, input) -> None:
        super().__init__(input)

        self.efc: SimpleNamespace | ipcc.RiceDefaultEmissionFactor = SimpleNamespace(value=0)
        self.yield_ref: SimpleNamespace | ipcc.RiceYield = SimpleNamespace(value=0)
        self.sfw_start: SimpleNamespace | ipcc.RiceSFW = SimpleNamespace(value=0)
        self.sfw_w: SimpleNamespace | ipcc.RiceSFW = SimpleNamespace(value=0)
        self.sfw_wo: SimpleNamespace | ipcc.RiceSFW = SimpleNamespace(value=0)
        self.sfp_start: SimpleNamespace | ipcc.RiceSFP = SimpleNamespace(value=0)
        self.sfp_w: SimpleNamespace | ipcc.RiceSFP = SimpleNamespace(value=0)
        self.sfp_wo: SimpleNamespace | ipcc.RiceSFP = SimpleNamespace(value=0)
        self.sfo_start: SimpleNamespace | ipcc.RiceSFO = SimpleNamespace(value=0)
        self.sfo_w: SimpleNamespace | ipcc.RiceSFO = SimpleNamespace(value=0)
        self.sfo_wo: SimpleNamespace | ipcc.RiceSFO = SimpleNamespace(value=0)
        self.efi_start: SimpleNamespace = SimpleNamespace(value=0)
        self.efi_w: SimpleNamespace = SimpleNamespace(value=0)
        self.efi_wo: SimpleNamespace = SimpleNamespace(value=0)
        self.n_estimation_factor: SimpleNamespace | ipcc.CropNitrousEstimationDefaultFactor = SimpleNamespace(value=0)
        self.burning_emission_factor: SimpleNamespace | ipcc.BurningEmissionFactor = SimpleNamespace(value=0)
        self.rice_cf: SimpleNamespace | ipcc.FiresCombustionFactor = SimpleNamespace(value=0)
        self.straw_burned_start: SimpleNamespace = SimpleNamespace(value=0)
        self.straw_burned_w: SimpleNamespace = SimpleNamespace(value=0)
        self.straw_burned_wo: SimpleNamespace = SimpleNamespace(value=0)

        self.biomass_ef_start: SimpleNamespace | ipcc.ForestTotalBiomass = SimpleNamespace(value=0)
        self.biomass_ef_w: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)
        self.biomass_ef_wo: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)

        self.som: SimpleNamespace | ipcc.NitrousEmissionFactor = SimpleNamespace(value=0)

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: FloodedRice | MinorSeasonFloodedRice = self.data
        module_for_checks = getattr(module, "parent", module)

        climate_flt = {"climate": self.climate}
        moisture_flt = {"moisture": self.moisture}
        region_flt = {"continent": self.region}

        if module_for_checks.is_start():
            h2o_mgmt_before_start_flt = {"water_management_type_before_cultivation": module.water_management_type_before_cultivation_start}
            h2o_mgmt_after_start_flt = {"water_management_type_after_cultivation": module.water_management_type_after_cultivation_start}
            organic_amendment_start_flt = {"organic_amendment_type": module.organic_amendment_type_start}
            self.sfw_start = utils.get_or_raise(ipcc.RiceSFW, h2o_mgmt_after_start_flt, f"RiceSFW for {module.water_management_type_after_cultivation_start} does not exist")
            self.sfp_start = utils.get_or_raise(ipcc.RiceSFP, h2o_mgmt_before_start_flt, f"RiceSFP for {module.water_management_type_before_cultivation_start} does not exist")
            self.sfo_start = utils.get_or_raise(ipcc.RiceSFO, organic_amendment_start_flt, f"RiceSFO for {module.organic_amendment_type_start} does not exist")

        if module_for_checks.is_with():
            h2o_mgmt_before_w_flt = {"water_management_type_before_cultivation": module.water_management_type_before_cultivation_w}
            h2o_mgmt_after_w_flt = {"water_management_type_after_cultivation": module.water_management_type_after_cultivation_w}
            organic_amendment_w_flt = {"organic_amendment_type": module.organic_amendment_type_w}
            self.sfw_w = utils.get_or_raise(ipcc.RiceSFW, h2o_mgmt_after_w_flt, f"RiceSFW for {module.water_management_type_after_cultivation_w} does not exist")
            self.sfp_w = utils.get_or_raise(ipcc.RiceSFP, h2o_mgmt_before_w_flt, f"RiceSFP for {module.water_management_type_before_cultivation_w} does not exist")
            self.sfo_w = utils.get_or_raise(ipcc.RiceSFO, organic_amendment_w_flt, f"RiceSFO for {module.organic_amendment_type_w} does not exist")
            self.biomass_ef_w = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, climate_flt | moisture_flt | region_flt | {"land_use_type": module.land_use_type_w}, f"ForestTotalBiomass for {self.climate.name} in {self.region.name} does not exist")

        if module_for_checks.is_without():
            h2o_mgmt_before_wo_flt = {"water_management_type_before_cultivation": module.water_management_type_before_cultivation_wo}
            h2o_mgmt_after_wo_flt = {"water_management_type_after_cultivation": module.water_management_type_after_cultivation_wo}
            organic_amendment_wo_flt = {"organic_amendment_type": module.organic_amendment_type_wo}
            self.sfw_wo = utils.get_or_raise(ipcc.RiceSFW, h2o_mgmt_after_wo_flt, f"RiceSFW for {module.water_management_type_after_cultivation_wo} does not exist")
            self.sfp_wo = utils.get_or_raise(ipcc.RiceSFP, h2o_mgmt_before_wo_flt, f"RiceSFP for {module.water_management_type_before_cultivation_wo} does not exist")
            self.sfo_wo = utils.get_or_raise(ipcc.RiceSFO, organic_amendment_wo_flt, f"RiceSFO for {module.organic_amendment_type_wo} does not exist")
            self.biomass_ef_wo = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, climate_flt | moisture_flt | region_flt | {"land_use_type": module.land_use_type_wo}, f"ForestTotalBiomass for {self.climate.name} in {self.region.name} does not exist")

        if module.is_ready() and calculate:
            self.calculate()
            self.efi_start.value = getattr(self.math_start_w, "adjusted_daily_ef_methane_tier_2_default", 0) or getattr(self.math_start_wo, "adjusted_daily_ef_methane_tier_2_default", 0)
            self.efi_w.value = getattr(self.math_w, "adjusted_daily_ef_methane_tier_2_default", 0)
            self.efi_wo.value = getattr(self.math_wo, "adjusted_daily_ef_methane_tier_2_default", 0)
            self.straw_burned_start.value = getattr(self.math_start_w, "straw_tonnes_tier_2_default", 0) or getattr(self.math_start_wo, "straw_tonnes_tier_2_default", 0)
            self.straw_burned_w.value = getattr(self.math_w, "straw_tonnes_tier_2_default", 0)
            self.straw_burned_wo.value = getattr(self.math_wo, "straw_tonnes_tier_2_default", 0)
            self.sfo_start.value = getattr(self.math_start_w, "SFo_tier_2_default", 0) or getattr(self.math_start_wo, "SFo_tier_2_default", 0)
            self.sfo_w.value = getattr(self.math_w, "SFo_tier_2_default", 0)
            self.sfo_wo.value = getattr(self.math_wo, "SFo_tier_2_default", 0)

        self.efc = utils.get_or_raise(ipcc.RiceDefaultEmissionFactor, region_flt, f"RiceDefaultEmissionFactor for {self.region.name} does not exist")
        self.yield_ref = utils.get_or_raise(ipcc.RiceYield, region_flt, f"RiceYield for {self.region.name} does not exist")

        lut_name_rice_flt = {"land_use_type__name": "Rice"}

        self.n_estimation_factor = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_name_rice_flt, "Default nitrous estimation factor is not defined for rice")
        self.burning_emission_factor = utils.get_or_raise(ipcc.BurningEmissionFactor, {"category__name": "Agricultural residues"}, "Burning emission factor is not defined for agricultural residues")
        self.rice_cf = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_name_rice_flt, "Fires combustion factor is not defined for rice")

    def calculate(self, aggregate_by=BreakdownTypes.TOTAL) -> list[Result]:
        module: FloodedRice = self.data  # TODO: Remove in favor of self.module
        # If it's a minor season, use the parent module
        module_for_checks = getattr(module, "parent", module)
        is_minor_season = module_for_checks.is_minor_season()

        self.get_defaults()

        if module_for_checks.is_luc_remaining_same():
            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "EFc_ref": self.efc.value,
                "EFc_tier_2": module.efc_t2_start,
                "SFw_ref": self.sfw_start.value,
                "SFw_tier_2": module.sfw_t2_start,
                "SFp_ref": self.sfp_start.value,
                "SFp_tier_2": module.sfp_t2_start,
                "cfoa": self.sfo_start.value,
                "SFo_tier_2": module.sfo_t2_start,
                "adjusted_daily_ef_methane_tier_2": module.efi_t2_start,
                "yield_ref": self.yield_ref.value,
                "yield_tier_2": module.crop_yield_start,
                "rice_slope": self.n_estimation_factor.slope,
                "rice_intercept": self.n_estimation_factor.intercept,
                "straw_tonnes_tier_2": module.rice_straw_t2_start,
                "methane_ef": self.burning_emission_factor.ch4,
                "rice_cf": self.rice_cf.value,
                "nitrous_ef": self.burning_emission_factor.n2o,
                "nitrous_constant": self.project.gw_potential.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.activity.change_rate.name,
                "methane_constant": self.project.gw_potential.ch4,
                "cultivation_period_ref": self.efc.cultivation_period,
                "cultivation_period_tier_2": module.cultivation_period_t2_start,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
                "soc_start_tier_2": getattr(module, "soc_t2_start", None),
                "soc_end_tier_2": getattr(module, "soc_t2_w", None),
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
                "calculate_soc_som": True,  # As per original code's TODO
                "straw_burnt": module.organic_amendment_type_start.name == "Straw Burnt",
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_w,
                "is_minor_season": is_minor_season,
            }

            self.math_start_w = MathFloodedRice(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if module_for_checks.is_business_as_usual():
            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "EFc_ref": self.efc.value,
                "EFc_tier_2": module.efc_t2_start,
                "SFw_ref": self.sfw_start.value,
                "SFw_tier_2": module.sfw_t2_start,
                "SFp_ref": self.sfp_start.value,
                "SFp_tier_2": module.sfp_t2_start,
                "cfoa": self.sfo_start.value,
                "SFo_tier_2": module.sfo_t2_start,
                "adjusted_daily_ef_methane_tier_2": module.efi_t2_start,
                "yield_ref": self.yield_ref.value,
                "yield_tier_2": module.crop_yield_start,
                "rice_slope": self.n_estimation_factor.slope,
                "rice_intercept": self.n_estimation_factor.intercept,
                "straw_tonnes_tier_2": module.rice_straw_t2_start,
                "methane_ef": self.burning_emission_factor.ch4,
                "rice_cf": self.rice_cf.value,
                "nitrous_ef": self.burning_emission_factor.n2o,
                "nitrous_constant": self.project.gw_potential.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.activity.change_rate.name,
                "methane_constant": self.project.gw_potential.ch4,
                "cultivation_period_ref": self.efc.cultivation_period,
                "cultivation_period_tier_2": module.cultivation_period_t2_start,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
                "soc_start_tier_2": getattr(module, "soc_t2_start", None),
                "soc_end_tier_2": getattr(module, "soc_t2_wo", None),
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
                "calculate_soc_som": CALCULATE_SOC_SOM_START_WO,
                "straw_burnt": module.organic_amendment_type_start.name == "Straw Burnt",
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_wo,
                "is_minor_season": is_minor_season,
            }

            self.math_start_wo = MathFloodedRice(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module_for_checks.is_with():
            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "EFc_ref": self.efc.value,
                "EFc_tier_2": module.efc_t2_w,
                "SFw_ref": self.sfw_w.value,
                "SFw_tier_2": module.sfw_t2_w,
                "SFp_ref": self.sfp_w.value,
                "SFp_tier_2": module.sfp_t2_w,
                "cfoa": self.sfo_w.value,
                "SFo_tier_2": module.sfo_t2_w,
                "adjusted_daily_ef_methane_tier_2": module.efi_t2_w,
                "yield_ref": self.yield_ref.value,
                "yield_tier_2": module.crop_yield_w,
                "rice_slope": self.n_estimation_factor.slope,
                "rice_intercept": self.n_estimation_factor.intercept,
                "straw_tonnes_tier_2": module.rice_straw_t2_w,
                "methane_ef": self.burning_emission_factor.ch4,
                "rice_cf": self.rice_cf.value,
                "nitrous_ef": self.burning_emission_factor.n2o,
                "nitrous_constant": self.project.gw_potential.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.activity.change_rate.name,
                "methane_constant": self.project.gw_potential.ch4,
                "cultivation_period_ref": self.efc.cultivation_period,
                "cultivation_period_tier_2": module.cultivation_period_t2_w,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
                "soc_start_tier_2": getattr(module, "soc_t2_start", None),
                "soc_end_tier_2": getattr(module, "soc_t2_w", None),
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
                "calculate_soc_som": CALCULATE_SOC_SOM_W,
                "straw_burnt": module.organic_amendment_type_w.name == "Straw Burnt",
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_w,
                "is_minor_season": is_minor_season,
            }

            self.math_w = MathFloodedRice(**self.inputs_w)
            self.math_w.calculate_emissions()

        if module_for_checks.is_without():
            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "EFc_ref": self.efc.value,
                "EFc_tier_2": module.efc_t2_wo,
                "SFw_ref": self.sfw_wo.value,
                "SFw_tier_2": module.sfw_t2_wo,
                "SFp_ref": self.sfp_wo.value,
                "SFp_tier_2": module.sfp_t2_wo,
                "cfoa": self.sfo_wo.value,
                "SFo_tier_2": module.sfo_t2_wo,
                "adjusted_daily_ef_methane_tier_2": module.efi_t2_wo,
                "yield_ref": self.yield_ref.value,
                "yield_tier_2": module.crop_yield_wo,
                "rice_slope": self.n_estimation_factor.slope,
                "rice_intercept": self.n_estimation_factor.intercept,
                "straw_tonnes_tier_2": module.rice_straw_t2_wo,
                "methane_ef": self.burning_emission_factor.ch4,
                "rice_cf": self.rice_cf.value,
                "nitrous_ef": self.burning_emission_factor.n2o,
                "nitrous_constant": self.project.gw_potential.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.activity.change_rate.name,
                "methane_constant": self.project.gw_potential.ch4,
                "cultivation_period_ref": self.efc.cultivation_period,
                "cultivation_period_tier_2": module.cultivation_period_t2_wo,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
                "soc_start_tier_2": getattr(module, "soc_t2_start", None),
                "soc_end_tier_2": getattr(module, "soc_t2_wo", None),
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
                "calculate_soc_som": CALCULATE_SOC_SOM_WO,
                "straw_burnt": module.organic_amendment_type_wo.name == "Straw Burnt",
                "delay": self.activity.delay,
                "ef_nitrous_som": self.som.value,
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_wo,
                "is_minor_season": is_minor_season,
            }

            self.math_wo = MathFloodedRice(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

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

        r_w, r_wo = FloodedRiceSeasonCalculator(module).calculate(False)

        self.results_w += r_w
        self.results_wo += r_wo

        for season in module.minor_seasons.all():
            r_w, r_wo = FloodedRiceSeasonCalculator(season).calculate()
            self.results_w += r_w
            self.results_wo += r_wo

        return (self.results_w, self.results_wo)

    def get_defaults(self, calculate=calculate) -> dict:
        FloodedRiceSeasonCalculator(input).get_defaults(calculate=calculate)


class GrasslandCalculator(LandModuleCalculator):
    """
    Calculator for grassland.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.ef: SimpleNamespace | ipcc.BurningEmissionFactor = SimpleNamespace(value=0)
        self.agb: SimpleNamespace | ipcc.GrasslandAGB = SimpleNamespace(value=0)
        self.cf: SimpleNamespace | GrasslandParameter = SimpleNamespace(value=0)
        self.biomass_ef_start: SimpleNamespace | ipcc.ForestTotalBiomass = SimpleNamespace(value=0)
        self.biomass_ef_w: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)
        self.biomass_ef_wo: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)

    def get_defaults(self, calculate=False):
        super().get_defaults(calculate)

        module: Grassland = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        # duration = activity.duration_t2 or self.activity.implementation_years
        # # TODO: Is this assuming that the activity start_year must be > project start_year?
        # delay = ((activity.start_year_t2 or 0) - project.start_year) or 0
        # capitalization = self.activity.implementation_years - duration + self.activity.capitalization_years

        self.ef = utils.get_or_raise(ipcc.BurningEmissionFactor, {"category__name": "Savanna and grassland"}, "Burning emission factor for savanna and grassland does not exist")
        self.agb = utils.get_or_raise(ipcc.GrasslandAGB, {"climate": project.climate, "moisture": project.moisture}, f"AGB for {project.climate.name} climate and {project.moisture.name} moisture does not exist")
        self.cf = utils.get_or_raise(GrasslandParameter, {"name": "default_combustion_factor"}, "Default combustion factor does not exist")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Grassland module.
        """
        log.debug("START GrasslandCalculator.calculate")

        module: Grassland = self.module
        activity: Activity = module.activity
        project: Project = activity.project

        # duration = activity.duration_t2 or self.activity.implementation_years
        # # TODO: Is this assuming that the activity start_year must be > project start_year?
        # delay = ((activity.start_year_t2 or 0) - project.start_year) or 0
        # capitalization = self.activity.implementation_years - duration + self.activity.capitalization_years

        self.get_defaults()

        if module.is_luc_remaining_same():
            log.debug("LUC remaining same")

            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "fire_interval": module.fire_periodicity_start,
                "fire_used": module.is_fire_used_start,
                "methane_ef": self.ef.ch4,
                "nitrous_ef": self.ef.n2o,
                "agb_ref": self.agb.value,
                "agb_tier_2": module.get_biomass_t2(utils.ScenarioTypes.START),
                "cf_ref": self.cf.value,
                "cf_tier_2": module.combustion_factor_t2_start,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_w,
                "fire_impact": module.fire_impact_start,
            }

            log.debug("Inputs start w: %s", self.inputs_start_w)

            self.math_start_w = MathGrassland(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if module.is_with():
            log.debug("With")

            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "fire_interval": module.fire_periodicity_w,
                "fire_used": module.is_fire_used_w,
                "methane_ef": self.ef.ch4,
                "nitrous_ef": self.ef.n2o,
                "agb_ref": self.agb.value,
                "agb_tier_2": module.get_biomass_t2(utils.ScenarioTypes.WITH),
                "cf_ref": self.cf.value,
                "cf_tier_2": module.combustion_factor_t2_start,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_w,
                "fire_impact": module.fire_impact_w,
            }

            log.debug("Inputs w: %s", self.inputs_w)

            self.math_w = MathGrassland(**self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_business_as_usual():
            log.debug("Business as usual")

            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "fire_interval": module.fire_periodicity_start,
                "fire_used": module.is_fire_used_start,
                "methane_ef": self.ef.ch4,
                "nitrous_ef": self.ef.n2o,
                "agb_ref": self.agb.value,
                "agb_tier_2": module.get_biomass_t2(utils.ScenarioTypes.START),
                "cf_ref": self.cf.value,
                "cf_tier_2": module.combustion_factor_t2_start,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_wo,
                "fire_impact": module.fire_impact_start,
            }

            log.debug("Inputs start wo: %s", self.inputs_start_wo)

            self.math_start_wo = MathGrassland(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module.is_without():
            log.debug("Without")

            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": self.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "methane_constant": project.gw_potential.ch4,
                "fire_interval": module.fire_periodicity_wo,
                "fire_used": module.is_fire_used_wo,
                "methane_ef": self.ef.ch4,
                "nitrous_ef": self.ef.n2o,
                "agb_ref": self.agb.value,
                "agb_tier_2": module.get_biomass_t2(utils.ScenarioTypes.WITHOUT),
                "cf_ref": self.cf.value,
                "cf_tier_2": module.combustion_factor_t2_start,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_wo,
                "fire_impact": module.fire_impact_wo,
            }

            log.debug("Inputs wo: %s", self.inputs_wo)

            self.math_wo = MathGrassland(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        log.debug("END GrasslandCalculator.calculate")
        return (self.results_w + self.results_start_w, self.results_wo + self.results_start_wo)


class SmallFisheryCalculator(BaseCalculator):
    """
    Calculator for small fishery.
    """

    def get_defaults(self, calculate=False) -> dict:
        module: SmallFishery = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        try:
            ef_diesel_default_list = ipcc.EnergyDefaultEmissionFactor.objects.filter(fuel_type__fuel_use_type__name__contains="Off-Road")
            # Average of all default emission factors for gasoil/diesel
            self.ef_diesel_default = sum([ef.t_co2_eq for ef in ef_diesel_default_list]) / len(ef_diesel_default_list)
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            raise ValueError("Default emission factors for off-road diesel do not exist")

        try:
            self.lost_refrigerant_default = SmallFisheryParameter.objects.get(name="lost_refrigerant_default").value
        except SmallFisheryParameter.DoesNotExist:
            raise ValueError("Default lost refrigerant does not exist")

        try:
            self.tonnes_ice_default = SmallFisheryParameter.objects.get(name="tonnes_ice_default").value
        except SmallFisheryParameter.DoesNotExist:
            raise ValueError("Default tonnes of ice does not exist")

        try:
            self.kw_tonnes = SmallFisheryParameter.objects.get(name="kw_tonnes").value
        except SmallFisheryParameter.DoesNotExist:
            raise ValueError("Default kw per tonne does not exist")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single SmallFishery module.
        """
        log.debug("START SmallFisheryCalculator.calculate")

        module: SmallFishery = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        try:
            ef_diesel_default_list = ipcc.EnergyDefaultEmissionFactor.objects.filter(fuel_type__fuel_use_type__name__contains="Off-Road")
            # Average of all default emission factors for gasoil/diesel
            ef_diesel_default = sum([ef.t_co2_eq for ef in ef_diesel_default_list]) / len(ef_diesel_default_list)
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            raise ValueError("Default emission factors for off-road diesel do not exist")

        try:
            fui_default_start = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_start)
        except ipcc.SmallFisheryFUI.DoesNotExist:
            fui_default_start = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_start)

        try:
            fui_default_w = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_w)
        except ipcc.SmallFisheryFUI.DoesNotExist:
            fui_default_w = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_w)

        try:
            fui_default_wo = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_wo)
        except ipcc.SmallFisheryFUI.DoesNotExist:
            fui_default_wo = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_wo)

        try:
            lost_refrigerant_default = SmallFisheryParameter.objects.get(name="lost_refrigerant_default").value
        except SmallFisheryParameter.DoesNotExist:
            raise ValueError("Default lost refrigerant does not exist")

        try:
            tonnes_ice_default = SmallFisheryParameter.objects.get(name="tonnes_ice_default").value
        except SmallFisheryParameter.DoesNotExist:
            raise ValueError("Default tonnes of ice does not exist")

        try:
            kw_tonnes = SmallFisheryParameter.objects.get(name="kw_tonnes").value
        except SmallFisheryParameter.DoesNotExist:
            raise ValueError("Default kw per tonne does not exist")

        try:
            electricity_emission = ipcc.ElectricityEmission.objects.get(country=project.country)
        except ipcc.ElectricityEmission.DoesNotExist:
            raise ValueError(f"Electricity emission for {project.country.name} does not exist")

        math_w = None
        math_wo = None

        if module.is_with():
            log.debug("IS WITH")
            self.inputs_w = {
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": module.activity.change_rate.name,
                "catch_start": module.total_catch_yr_start,
                "catch_end": module.total_catch_yr_w,
                "ef_diesel_default": ef_diesel_default,
                "ef_diesel_start_tier_2": module.energy_emission_factor_t2_start,
                "ef_diesel_tier_2_end": module.energy_emission_factor_t2_w,
                "fui_default_start": fui_default_start,
                "fui_default_end": fui_default_w,
                "fui_start_tier_2": module.fui_start,
                "fui_end_tier_2": module.fui_w,
                "gwp_refrigerant_default": module.refrigerant_gwp,
                "gwp_refrigerant_start_tier_2": module.refrigerant_gwp_t2_start,
                "gwp_refrigerant_end_tier_2": module.refrigerant_gwp_t2_w,
                "quantity_lost_refrigerant_default": lost_refrigerant_default,
                "quantity_lost_refrigerant_start_tier_2": module.refrigerant_lost_per_tonne_t2_start,
                "quantity_lost_refrigerant_end_tier_2": module.refrigerant_lost_per_tonne_t2_w,
                "percentage_refrigerant_start": module.refrigerant_pc_start,
                "percentage_refrigerant_end": module.refrigerant_pc_w,
                "tonnes_ice_default": tonnes_ice_default,
                "tonnes_ice_start_tier_2": module.tonnes_of_ice_t2_start,
                "tonnes_ice_end_tier_2": module.tonnes_of_ice_t2_w,
                "kwh_ice_per_tonne_default": kw_tonnes,
                "kwh_ice_per_tonne_start_tier_2": module.inshore_ice_production_kwh_per_tonne_t2_start,
                "kwh_ice_per_tonne_end_tier_2": module.inshore_ice_production_kwh_per_tonne_t2_w,
                "operating_margin": electricity_emission.operating_margin,
                "percentage_ice_start": module.ice_preserved_catch_pc_start,
                "percentage_ice_end": module.ice_preserved_catch_pc_w,
                "delay": self.activity.delay,
            }
            log.debug("Inputs with: %s", self.inputs_w)

            math_w = MathFishery(**self.inputs_w)
            math_w.calculate_emissions()

        if module.is_without():
            log.debug("IS WITHOUT")
            self.inputs_wo = {
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": module.activity.change_rate.name,
                "catch_start": module.total_catch_yr_start,
                "catch_end": module.total_catch_yr_wo,
                "ef_diesel_default": ef_diesel_default,
                "ef_diesel_start_tier_2": module.energy_emission_factor_t2_start,
                "ef_diesel_tier_2_end": module.energy_emission_factor_t2_wo,
                "fui_default_start": fui_default_start,
                "fui_default_end": fui_default_wo,
                "fui_start_tier_2": module.fui_start,
                "fui_end_tier_2": module.fui_wo,
                "gwp_refrigerant_default": module.refrigerant_gwp,
                "gwp_refrigerant_start_tier_2": module.refrigerant_gwp_t2_start,
                "gwp_refrigerant_end_tier_2": module.refrigerant_gwp_t2_wo,
                "quantity_lost_refrigerant_default": lost_refrigerant_default,
                "quantity_lost_refrigerant_start_tier_2": module.refrigerant_lost_per_tonne_t2_start,
                "quantity_lost_refrigerant_end_tier_2": module.refrigerant_lost_per_tonne_t2_wo,
                "percentage_refrigerant_start": module.refrigerant_pc_start,
                "percentage_refrigerant_end": module.refrigerant_pc_wo,
                "tonnes_ice_default": tonnes_ice_default,
                "tonnes_ice_start_tier_2": module.tonnes_of_ice_t2_start,
                "tonnes_ice_end_tier_2": module.tonnes_of_ice_t2_wo,
                "kwh_ice_per_tonne_default": kw_tonnes,
                "kwh_ice_per_tonne_start_tier_2": module.inshore_ice_production_kwh_per_tonne_t2_start,
                "kwh_ice_per_tonne_end_tier_2": module.inshore_ice_production_kwh_per_tonne_t2_wo,
                "operating_margin": electricity_emission.operating_margin,
                "percentage_ice_start": module.ice_preserved_catch_pc_start,
                "percentage_ice_end": module.ice_preserved_catch_pc_wo,
                "delay": self.activity.delay,
            }
            log.debug("Inputs without: %s", self.inputs_wo)

            math_wo = MathFishery(**self.inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        log.debug("Results WITH")
        results_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("Results WITHOUT")
        results_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        results_tuple = (results_w, results_wo)

        log.debug("END SmallFisheryCalculator.calculate")
        return results_tuple

    # def get_defaults(self):
    #     self.calculate()

    #     module: SmallFishery = self.data

    #     defaults_start = {}
    #     defaults_w = {}
    #     defaults_wo = {}

    #     if is_with(module):
    #         math_w = MathFishery(*self.inputs_w)
    #         math_w_defaults = math_w.evaluate_tier_2_defaults()
    #         defaults_w.update(math_w_defaults.end)
    #         defaults_w.update(math_w_defaults.other)

    #     if is_without(module):
    #         math_wo = MathFishery(*self.inputs_wo)
    #         math_wo_defaults = math_wo.evaluate_tier_2_defaults()
    #         defaults_wo.update(math_wo_defaults.end)
    #         defaults_wo.update(math_wo_defaults.other)

    #     return DefaultData(defaults_start, defaults_w, defaults_wo)


class LargeFisheryCalculator(BaseCalculator):
    """
    Calculator for large fishery.
    """

    def get_defaults(self, calculate=False) -> dict:
        module: LargeFishery = self.data
        project = module.activity.project

        try:
            ef_diesel_default_list = ipcc.EnergyDefaultEmissionFactor.objects.filter(fuel_type__fuel_use_type__name__contains="Off-Road")
            # Average of all default emission factors for gasoil/diesel
            self.ef_diesel_default = sum([ef.t_co2_eq for ef in ef_diesel_default_list]) / len(ef_diesel_default_list)
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            raise ValueError("Default emission factors for off-road diesel do not exist")

        try:
            self.lost_refrigerant_default = LargeFisheryParameter.objects.get(name="lost_refrigerant_default").value
        except LargeFisheryParameter.DoesNotExist:
            raise ValueError("Default lost refrigerant does not exist")

        try:
            self.tonnes_ice_default = LargeFisheryParameter.objects.get(name="tonnes_ice_default").value
        except LargeFisheryParameter.DoesNotExist:
            raise ValueError("Default tonnes of ice does not exist")

        try:
            self.kw_tonnes = LargeFisheryParameter.objects.get(name="kw_tonnes").value
        except LargeFisheryParameter.DoesNotExist:
            raise ValueError("Default kw per tonne does not exist")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single LargeFishery module.
        """
        log.debug("START LargeFisheryCalculator.calculate")

        module: LargeFishery = self.data
        project = module.activity.project

        try:
            ef_diesel_default_list = ipcc.EnergyDefaultEmissionFactor.objects.filter(fuel_type__fuel_use_type__name__contains="Off-Road")
            # Average of all default emission factors for gasoil/diesel
            ef_diesel_default = sum([ef.t_co2_eq for ef in ef_diesel_default_list]) / len(ef_diesel_default_list)
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            raise ValueError("Default emission factors for off-road diesel do not exist")

        try:
            fui_default_start = ipcc.LargeFisheryFUI.objects.get_value_or_average(fish_type=module.fish_type, gear_type=module.gear_type_start)
        except ipcc.LargeFisheryFUI.DoesNotExist:
            raise ValueError(f"Fishery FUI for {module.fish_type.name} and {module.gear_type_start.name} does not exist")

        try:
            fui_default_w = ipcc.LargeFisheryFUI.objects.get_value_or_average(fish_type=module.fish_type, gear_type=module.gear_type_w)
        except ipcc.LargeFisheryFUI.DoesNotExist:
            raise ValueError(f"Fishery FUI for {module.fish_type.name} and {module.gear_type_w.name} does not exist")

        try:
            fui_default_wo = ipcc.LargeFisheryFUI.objects.get_value_or_average(fish_type=module.fish_type, gear_type=module.gear_type_wo)
        except ipcc.LargeFisheryFUI.DoesNotExist:
            raise ValueError(f"Fishery FUI for {module.fish_type.name} and {module.gear_type_wo.name} does not exist")

        try:
            lost_refrigerant_default = LargeFisheryParameter.objects.get(name="lost_refrigerant_default").value
        except LargeFisheryParameter.DoesNotExist:
            raise ValueError("Default lost refrigerant does not exist")

        try:
            tonnes_ice_default = LargeFisheryParameter.objects.get(name="tonnes_ice_default").value
        except LargeFisheryParameter.DoesNotExist:
            raise ValueError("Default tonnes of ice does not exist")

        try:
            kw_tonnes = LargeFisheryParameter.objects.get(name="kw_tonnes").value
        except LargeFisheryParameter.DoesNotExist:
            raise ValueError("Default kw per tonne does not exist")

        try:
            electricity_country = module.inshore_ice_production_country_t2 if module.inshore_ice_production_country_t2 else project.country
            electricity_emission = ipcc.ElectricityEmission.objects.get(country=electricity_country)
        except ipcc.ElectricityEmission.DoesNotExist:
            raise ValueError(f"Electricity emission for {electricity_country.name} does not exist")

        math_w = None
        math_wo = None

        if module.is_with():
            log.debug("IS WITH")
            self.inputs_w = {
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": module.activity.change_rate.name,
                "catch_start": module.total_catch_yr_start,
                "catch_end": module.total_catch_yr_w,
                "ef_diesel_default": ef_diesel_default,
                "ef_diesel_start_tier_2": module.energy_emission_factor_t2_start,
                "ef_diesel_tier_2_end": module.energy_emission_factor_t2_w,
                "fui_default_start": fui_default_start,
                "fui_default_end": fui_default_w,
                "fui_start_tier_2": module.fui_start,
                "fui_end_tier_2": module.fui_w,
                "gwp_refrigerant_default": module.refrigerant_gwp,
                "gwp_refrigerant_start_tier_2": module.refrigerant_gwp_t2_start,
                "gwp_refrigerant_end_tier_2": module.refrigerant_gwp_t2_w,
                "quantity_lost_refrigerant_default": lost_refrigerant_default,
                "quantity_lost_refrigerant_start_tier_2": module.refrigerant_lost_per_tonne_t2_start,
                "quantity_lost_refrigerant_end_tier_2": module.refrigerant_lost_per_tonne_t2_w,
                "percentage_refrigerant_start": module.refrigerant_pc_start,
                "percentage_refrigerant_end": module.refrigerant_pc_w,
                "tonnes_ice_default": tonnes_ice_default,
                "tonnes_ice_start_tier_2": module.tonnes_of_ice_t2_start,
                "tonnes_ice_end_tier_2": module.tonnes_of_ice_t2_w,
                "kwh_ice_per_tonne_default": kw_tonnes,
                "kwh_ice_per_tonne_start_tier_2": module.inshore_ice_production_kwh_per_tonne_t2_start,
                "kwh_ice_per_tonne_end_tier_2": module.inshore_ice_production_kwh_per_tonne_t2_w,
                "operating_margin": electricity_emission.operating_margin,
                "percentage_ice_start": module.ice_preserved_catch_pc_start,
                "percentage_ice_end": module.ice_preserved_catch_pc_w,
                "delay": self.activity.delay,
            }
            log.debug("Inputs with: %s", self.inputs_w)

            math_w = MathFishery(**self.inputs_w)
            math_w.calculate_emissions()

        if module.is_without():
            log.debug("IS WITHOUT")
            self.inputs_wo = {
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": module.activity.change_rate.name,
                "catch_start": module.total_catch_yr_start,
                "catch_end": module.total_catch_yr_wo,
                "ef_diesel_default": ef_diesel_default,
                "ef_diesel_start_tier_2": module.energy_emission_factor_t2_start,
                "ef_diesel_tier_2_end": module.energy_emission_factor_t2_wo,
                "fui_default_start": fui_default_start,
                "fui_default_end": fui_default_wo,
                "fui_start_tier_2": module.fui_start,
                "fui_end_tier_2": module.fui_wo,
                "gwp_refrigerant_default": module.refrigerant_gwp,
                "gwp_refrigerant_start_tier_2": module.refrigerant_gwp_t2_start,
                "gwp_refrigerant_end_tier_2": module.refrigerant_gwp_t2_wo,
                "quantity_lost_refrigerant_default": lost_refrigerant_default,
                "quantity_lost_refrigerant_start_tier_2": module.refrigerant_lost_per_tonne_t2_start,
                "quantity_lost_refrigerant_end_tier_2": module.refrigerant_lost_per_tonne_t2_wo,
                "percentage_refrigerant_start": module.refrigerant_pc_start,
                "percentage_refrigerant_end": module.refrigerant_pc_wo,
                "tonnes_ice_default": tonnes_ice_default,
                "tonnes_ice_start_tier_2": module.tonnes_of_ice_t2_start,
                "tonnes_ice_end_tier_2": module.tonnes_of_ice_t2_wo,
                "kwh_ice_per_tonne_default": kw_tonnes,
                "kwh_ice_per_tonne_start_tier_2": module.inshore_ice_production_kwh_per_tonne_t2_start,
                "kwh_ice_per_tonne_end_tier_2": module.inshore_ice_production_kwh_per_tonne_t2_wo,
                "operating_margin": electricity_emission.operating_margin,
                "percentage_ice_start": module.ice_preserved_catch_pc_start,
                "percentage_ice_end": module.ice_preserved_catch_pc_wo,
                "delay": self.activity.delay,
            }
            log.debug("Inputs without: %s", self.inputs_wo)

            math_wo = MathFishery(**self.inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        log.debug("Results WITH")
        results_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("Results WITHOUT")
        results_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        results_tuple = (results_w, results_wo)

        log.debug("END LargeFisheryCalculator.calculate")
        return results_tuple

    def defaults(self):
        self.calculate()

        module: LargeFishery = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if module.is_with():
            math_w = MathFishery(**self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.end)
            defaults_w.update(math_w_defaults.other)

        if module.is_without():
            math_wo = MathFishery(**self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.end)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


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
            self.NITROUS_EF_DEFAULT = AquacultureParameter.objects.get(name="nitrous_ef_default").value
        except AquacultureParameter.DoesNotExist:
            raise ValueError("Default nitrous emission factor does not exist")

        try:
            # TODO: This will now be used in the inputs module for feed
            self.FEED_EF_DEFAULT = AquacultureParameter.objects.get(name="feed_ef_default").value
        except AquacultureParameter.DoesNotExist:
            raise ValueError("Default feed emission factor does not exist")

        try:
            self.elec = ipcc.ElectricityEmission.objects.get(country=project.country)
            log.debug(f"Operating margin: {self.elec.operating_margin}")
        except ipcc.ElectricityEmission.DoesNotExist:
            raise ValueError(f"Electricity emission for {project.country.name} does not exist")

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
                "nitrous_constant": project.gw_potential.n2o,
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
                "nitrous_constant": project.gw_potential.n2o,
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
        project: Project = module.activity.project

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

        self.ref = SimpleNamespace(co2_multiplier=0, co2_emissions_multiplier=0, n2o_quantity_multiplier=0, n2o_emissions_multiplier=0, production_quantity_multiplier=0, production_emissions_multiplier=0)
        self.ef = SimpleNamespace(co2_value=0, n2o_value=0, co2_eq_value=0)

    def get_defaults(self, calculate=False) -> dict:

        module: InputEntry = self.data
        activity: Activity = module.parent.activity
        project: Project = activity.project

        input_type: InputType = module.input_type

        needs_co2_ref = input_type.has_co2_emissions and not module.co2_emissions_t2
        needs_n2o_ref = input_type.has_n2o_emissions and not module.n2o_emissions_t2
        needs_co2_e_ref = input_type.has_co2_e_emissions and not module.co2_e_emissions_t2

        if module.status.name == "READY" and calculate:
            self.calculate()

        try:
            self.ref = ipcc.InputReference.objects.get(input_type=module.input_type)
        except ipcc.InputReference.DoesNotExist:
            raise ValueError(f"Reference for {module.input_type.name} does not exist.")

        try:
            self.ef = ipcc.InputEmissionFactor.objects.get(input_type=module.input_type, climate=project.climate, moisture=project.moisture)
        except ipcc.InputEmissionFactor.DoesNotExist:
            self.ef = None
            if needs_co2_ref or needs_n2o_ref or needs_co2_e_ref:
                raise ValueError(f"Emission factor for {module.input_type.name} does not exist for {project.climate.name} and {project.moisture.name}. Please define tier 2 values.")

        self.math_w = None
        self.math_wo = None

    def calculate(self) -> list[Result]:
        module: InputEntry = self.data
        activity: Activity = module.parent.activity
        project: Project = activity.project

        self.get_defaults()

        self.inputs_w = {
            "unit_start": module.value_start,
            "unit_end": module.value_w,
            "rate_type": activity.change_rate.name,
            "ipcc_factor_co2": self.ef.co2_value if self.ef else None,
            "tier_2_factor_co2": module.co2_emissions_t2,
            "unit_factor_co2": self.ref.co2_multiplier,
            "emissions_factor_co2": self.ref.co2_emissions_multiplier,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "ipcc_factor_n2o": self.ef.n2o_value if self.ef else None,
            "tier_2_factor_n2o": module.n2o_emissions_t2,
            "unit_factor_n2o": self.ref.n2o_quantity_multiplier,
            "emissions_factor_n2o": self.ref.n2o_emissions_multiplier,
            "ipcc_factor_eq": self.ef.co2_eq_value if self.ef else None,
            "tier_2_factor_eq": module.co2_e_emissions_t2,
            "unit_factor_eq": self.ref.production_quantity_multiplier,
            "emissions_factor_eq": self.ref.production_emissions_multiplier,
            "delay": self.activity.delay,
        }
        log.debug("Inputs with: %s", self.inputs_w)

        self.math_w = MathInputs(**self.inputs_w)
        self.math_w.calculate_emissions()

        self.inputs_wo = {
            "unit_start": module.value_start,
            "unit_end": module.value_wo,
            "rate_type": activity.change_rate.name,
            "ipcc_factor_co2": self.ef.co2_value if self.ef else None,
            "tier_2_factor_co2": module.co2_emissions_t2,
            "unit_factor_co2": self.ref.co2_multiplier,
            "emissions_factor_co2": self.ref.co2_emissions_multiplier,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "ipcc_factor_n2o": self.ef.n2o_value if self.ef else None,
            "tier_2_factor_n2o": module.n2o_emissions_t2,
            "unit_factor_n2o": self.ref.n2o_quantity_multiplier,
            "emissions_factor_n2o": self.ref.n2o_emissions_multiplier,
            "ipcc_factor_eq": self.ef.co2_eq_value if self.ef else None,
            "tier_2_factor_eq": module.co2_e_emissions_t2,
            "unit_factor_eq": self.ref.production_quantity_multiplier,
            "emissions_factor_eq": self.ref.production_emissions_multiplier,
            "delay": self.activity.delay,
        }
        log.debug("Inputs without: %s", self.inputs_wo)

        self.math_wo = MathInputs(**self.inputs_wo)
        self.math_wo.calculate_emissions()

        results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (results_w, results_wo)

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

    def get_defaults(self, calculate=False) -> dict:
        module: Electricity = self.data
        activity: Activity = module.parent.activity
        project: Project = activity.project

        try:
            elec = ipcc.ElectricityEmission.objects.get(country=module.country)

            self.ef_source = "Combined Margin" if "Combined margin" in module.ef_source.name else "Operating Margin"

            if self.ef_source == "Operating Margin":
                log.debug(f"Operating margin: {elec.operating_margin}")
                self.ef_country = elec.operating_margin
            else:
                log.debug(f"Combined margin: {elec.combined_margin}")
                self.ef_country = elec.combined_margin

            self.transmission_loss = 0.1  # NOTE: don't know how this should be done in the best way, hardcoded for now, but can't be retrieved from the DB (maybe create a value in the DB for this as well?)

        except ipcc.ElectricityEmission.DoesNotExist:
            raise ValueError(f"Electricity emission for {project.country.name} does not exist")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Energy module.
        """
        log.debug("START ElectricityCalculator.calculate")

        module: Electricity = self.data
        activity: Activity = module.parent.activity
        project: Project = activity.project
        change_rate = activity.change_rate

        margin = None

        try:
            elec = ipcc.ElectricityEmission.objects.get(country=module.country)
            if "Operating Margin" in module.ef_source:
                log.debug(f"Operating margin: {elec.operating_margin}")
                margin = elec.operating_margin
            else:
                log.debug(f"Combined margin: {elec.combined_margin}")
                margin = elec.combined_margin
        except ipcc.ElectricityEmission.DoesNotExist:
            raise ValueError(f"Electricity emission for {project.country.name} does not exist")

        inputs_w = {
            "emissions_factor": margin,
            "specific_factor_start": module.ef_t2_start,
            "specific_factor_end": module.ef_t2_w,
            "mwh_start": module.mwh_start,
            "mwh_end": module.mwh_w,
            "percent_loss_transportation_start": module.transmission_loss_start,
            "percent_loss_transportation_end": module.transmission_loss_w,
            "rate_type": change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
        }
        log.debug("Inputs with: %s", inputs_w)

        math_w = ElectricityConsumption(**inputs_w)
        math_w.calculate_emissions()

        inputs_wo = {
            "emissions_factor": margin,
            "specific_factor_start": module.ef_t2_start,
            "specific_factor_end": module.ef_t2_wo,
            "mwh_start": module.mwh_start,
            "mwh_end": module.mwh_wo,
            "percent_loss_transportation_start": module.transmission_loss_start,
            "percent_loss_transportation_end": module.transmission_loss_wo,
            "rate_type": change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
        }
        log.debug("Inputs without: %s", inputs_wo)

        math_wo = ElectricityConsumption(**inputs_wo)
        math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (results_w, results_wo)

        log.debug("Results WITH")
        results_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("Results WITHOUT")
        results_wo.breakdown(by=BreakdownTypes.ACTIVITY)

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

        self.ef = ipcc.EnergyDefaultEmissionFactor(fuel_type=None, co2=0, ch4=0, n2o=0)

    def get_defaults(self, calculate=False) -> dict:
        self.module: Fuel

        try:
            self.ef = ipcc.EnergyDefaultEmissionFactor.objects.get(fuel_type=self.module.fuel_type)
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            raise ValueError(f"Default emission factor for {self.module.fuel_type.name} does not exist. Please select tier 2 value.")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Fuel module.
        """
        log.debug("START FuelCalculator.calculate")

        self.get_defaults()

        change_rate = self.activity.change_rate
        methane_constant = self.project.gw_potential.ch4

        log.debug(f"Fuel Type: {self.module.fuel_type.name}")

        if self.module.fuel_type.name in ["Peat", "Charcoal"]:
            methane_constant = self.project.gw_potential.ch4_fossil

        inputs_w = {
            "emissions_factor_co2": self.ef.co2,
            "specific_factor_co2": self.module.ef_co2_t2_w,
            "emissions_factor_ch4": self.ef.ch4,
            "specific_factor_ch4": self.module.ef_ch4_t2_w,
            "emissions_factor_n2o": self.ef.n2o,
            "specific_factor_n2o": self.module.ef_n2o_t2_w,
            "mwh_start": self.module.fuel_consumption_start,
            "mwh_end": self.module.fuel_consumption_w,
            "rate_type": change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "methane_constant": methane_constant,
            "nitrous_constant": self.project.gw_potential.n2o,
            "delay": self.activity.delay,
        }
        log.debug("Inputs with: %s", inputs_w)

        self.math_w = SolidAndLiquidFuelsConsumption(**inputs_w)
        self.math_w.calculate_emissions()

        inputs_wo = {
            "emissions_factor_co2": self.ef.co2,
            "specific_factor_co2": self.module.ef_co2_t2_wo,
            "emissions_factor_ch4": self.ef.ch4,
            "specific_factor_ch4": self.module.ef_ch4_t2_wo,
            "emissions_factor_n2o": self.ef.n2o,
            "specific_factor_n2o": self.module.ef_n2o_t2_wo,
            "mwh_start": self.module.fuel_consumption_start,
            "mwh_end": self.module.fuel_consumption_wo,
            "rate_type": change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "methane_constant": methane_constant,
            "nitrous_constant": self.project.gw_potential.n2o,
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
        module: Settlement = module

        self.nitrous_ef = SimpleNamespace(value=0)

        self.ef_start = SimpleNamespace(flu=0, fmg=0, fi=0, biomass=0)
        self.ef_w = SimpleNamespace(flu=0, fmg=0, fi=0, biomass=0)
        self.ef_wo = SimpleNamespace(flu=0, fmg=0, fi=0, biomass=0)

        # self.biomass_ef_start: SimpleNamespace | ipcc.ForestTotalBiomass = SimpleNamespace(value=0)
        # self.biomass_ef_w: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)
        # self.biomass_ef_wo: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)

    def get_defaults(self, calculate=False) -> dict:
        log.debug("START SettlementCalculator.get_defaults")
        super().get_defaults(calculate)

        module: Settlement = self.data
        activity: Activity = module.activity
        luc: LandUseChange = module.land_use_change

        climate: Climate = module.activity.climate_t2 or module.activity.project.climate
        moisture: Moisture = module.activity.moisture_t2 or module.activity.project.moisture

        self.nitrous_ef = utils.get_or_raise(ipcc.NitrousEmissionFactor, {"moisture": moisture}, f"Nitrous EF not found for {moisture.name} moisture")

        # TODO: Detach .biomass from SettlementEF and put it in ForestTotalBiomass
        # TODO: Same thing for flu,fi,fmg
        if module.is_business_as_usual() or module.is_luc_remaining_same():
            self.ef_start: ipcc.SettlementEF = utils.get_or_raise(ipcc.SettlementEF, {"settlement_type": module.settlement_type_start, "climate": climate, "moisture": moisture}, f"Settlement EF not found for {module.settlement_type_start.name}")
            self.flu_start = SimpleNamespace(value=self.ef_start.flu)
            self.fi_start = SimpleNamespace(value=self.ef_start.fi)
            self.fmg_start = SimpleNamespace(value=self.ef_start.fmg)
            # self.biomass_ef_start = utils.get_or_raise(ipcc.ForestTotalBiomass, cm | {"continent": project.country.region, "land_use_type": module.land_use_type_start}, f"Forest total biomass not found for {climate.name} climate, {moisture.name} moisture, {project.country.region.name} region and {module.land_use_type_start.name} land use type")

        if module.is_with():
            self.ef_w: ipcc.SettlementEF = utils.get_or_raise(ipcc.SettlementEF, {"settlement_type": module.settlement_type_w, "climate": climate, "moisture": moisture}, f"Settlement EF not found for {module.settlement_type_w.name}")
            self.flu_w = SimpleNamespace(value=self.ef_w.flu)
            self.fi_w = SimpleNamespace(value=self.ef_w.fi)
            self.fmg_w = SimpleNamespace(value=self.ef_w.fmg)
            # self.biomass_ef_w = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, cm | {"continent": project.country.region, "land_use_type": module.land_use_type_w}, f"Forest total biomass not found for {climate.name} climate, {moisture.name} moisture, {project.country.region.name} region and {module.land_use_type_w.name} land use type")

        if module.is_without():
            self.ef_wo: ipcc.SettlementEF = utils.get_or_raise(ipcc.SettlementEF, {"settlement_type": module.settlement_type_wo, "climate": climate, "moisture": moisture}, f"Settlement EF not found for {module.settlement_type_wo.name}")
            self.flu_wo = SimpleNamespace(value=self.ef_wo.flu)
            self.fi_wo = SimpleNamespace(value=self.ef_wo.fi)
            self.fmg_wo = SimpleNamespace(value=self.ef_wo.fmg)
            # self.biomass_ef_wo = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, cm | {"continent": project.country.region, "land_use_type": module.land_use_type_wo}, f"Forest total biomass not found for {climate.name} climate, {moisture.name} moisture, {project.country.region.name} region and {module.land_use_type_wo.name} land use type")

        if luc and module.is_start() and module.settlement_type_start.name.casefold() != "paved settlement":
            module_start, module_w, module_wo = luc.get_modules()

            is_paved_w = module.is_with() and module.settlement_type_w.name.casefold() == "paved settlement"
            is_paved_wo = module.is_without() and module.settlement_type_wo.name.casefold() == "paved settlement"

            if is_paved_w or is_paved_wo:
                flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.WITHOUT)
                fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.WITHOUT)
                fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.WITHOUT)

                self.soc.value = self.soc.value * flu_start * fi_start * fmg_start  # SOCinitial

        log.debug("END SettlementCalculator.get_defaults")

    def calculate(self) -> Result:
        log.debug("START SettlementCalculator.calculate")
        module: Settlement = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        res_w = MathResult(
            self.activity.implementation_years,
            self.activity.capitalization_years,
        )
        res_wo = MathResult(
            self.activity.implementation_years,
            self.activity.capitalization_years,
        )

        self.get_defaults()

        if module.is_luc_remaining_same():
            log.debug("LUC remaining same")

            inputs_start_w = {
                "hectares_start": module.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.nitrous_ef.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }

            self.math_start_w = MathNotCultivatedLand(**inputs_start_w)
            self.math_start_w.calculate_emissions()

        if module.is_business_as_usual():

            inputs_start_wo = {
                "hectares_start": module.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.nitrous_ef.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }

            self.math_start_wo = MathNotCultivatedLand(**inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module.is_with():

            inputs_w = {
                "hectares_start": 0,
                "hectares_end": module.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.nitrous_ef.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_default": self.ef_start.biomass,
                "biomass_end_default": self.ef_w.biomass,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_w.biomass_t2_w,
            }

            self.math_w = MathNotCultivatedLand(**inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():

            inputs_wo = {
                "hectares_start": 0,
                "hectares_end": module.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.nitrous_ef.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_default": self.ef_start.biomass,
                "biomass_end_default": self.ef_wo.biomass,
                "biomass_start_tier_2": self.module_start.biomass_t2_start,
                "biomass_end_tier_2": self.module_wo.biomass_t2_wo,
            }

            self.math_wo = MathNotCultivatedLand(**inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        res_w += self.results_start_w
        res_wo += self.results_start_wo

        res_w += self.results_w
        res_wo += self.results_wo

        for building in module.buildings.all():
            r_w, r_wo = BuildingCalculator(building).calculate()

            res_w += r_w
            res_wo += r_wo

        for road in module.roads.all():
            r_w, r_wo = RoadCalculator(road).calculate()

            res_w += r_w
            res_wo += r_wo

        log.debug("END SettlementCalculator.calculate")
        return (res_w, res_wo)


class BuildingCalculator(BaseCalculator):
    """
    Calculator for buildings and roads.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.ef: ipcc.BuildingEmissionFactor = None

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: Building = self.data

        # TODO: What do we need the start scenario for?
        # TODO: Define if all the fields of an input are required after creation
        self.ef = utils.get_or_raise(ipcc.BuildingEmissionFactor, {"building_type": module.building_type}, f"Could not find Building EF for {module.building_type}")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Building module.
        """

        module: Building = self.data
        parent: Settlement = module.parent
        activity: Activity = parent.activity
        project: Project = activity.project

        self.get_defaults()

        self.results_w = MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if module.is_with():
            self.inputs_w = {
                "ef_ipcc": self.ef.value,
                "ef_tier_2": module.ef_t2_w,
                "area": module.area_m2_w,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
            }

            self.math_w = MathRoads(**self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            self.inputs_wo = {
                "ef_ipcc": self.ef.value,
                "ef_tier_2": module.ef_t2_wo,
                "area": module.area_m2_wo,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
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

        self.ef: ipcc.RoadEmissionFactor = None

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: Road = self.data
        self.ef = utils.get_or_raise(ipcc.RoadEmissionFactor, {"road_type": module.road_type}, f"Could not find Road EF for {module.road_type.name}")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Road module.
        """

        module: Road = self.data
        parent: Settlement = module.parent
        activity: Activity = parent.activity
        project: Project = activity.project

        self.get_defaults()

        self.results_w = MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        if module.is_with():
            self.inputs_w = {
                "ef_ipcc": self.ef.value,
                "ef_tier_2": module.ef_t2_w,
                "area": module.length_km_w * module.width_m_w,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
            }

            self.math_w = MathRoads(**self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            self.inputs_wo = {
                "ef_ipcc": self.ef.value,
                "ef_tier_2": module.ef_t2_wo,
                "area": module.length_km_wo * module.width_m_wo,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
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

            # Animal Waste PRP
            self.animal_waste_prp_start = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt | prp | {"manure_management_type__name": utils.ManureManagementTypes.PRP.value}, f"Could not find Animal Waste PRP (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # Animal Waste PRP of other systems
            self.animal_waste_management_systems_start = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt, f"Could not find Animal Waste Management Systems (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.animal_waste_management_systems_values_start = [system.value for system in self.animal_waste_management_systems_start]

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

            # PRP N2O Volatilization EF of other systems
            self.ef_n2o_volatilization_systems_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | volatilization, f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_volatilization_systems_start = [s.value for s in self.ef_n2o_volatilization_systems_start]

            # PRP N2O Leaching EF of other systems
            self.ef_n2o_leaching_systems_start = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | leaching, f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_leaching_systems_start = [s.value for s in self.ef_n2o_leaching_systems_start]

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

            # Animal Waste PRP
            self.animal_waste_prp_w = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt | prp | {"manure_management_type__name": utils.ManureManagementTypes.PRP.value}, f"Could not find Animal Waste PRP (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # Animal Waste PRP of other systems
            self.animal_waste_management_systems_w = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt, f"Could not find Animal Waste Management Systems (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.animal_waste_management_systems_values_w = [system.value for system in self.animal_waste_management_systems_w]

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

            # PRP N2O Volatilization EF of other systems
            self.ef_n2o_volatilization_systems_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | volatilization, f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_volatilization_systems_w = [s.value for s in self.ef_n2o_volatilization_systems_w]

            # PRP N2O Leaching EF of other systems
            self.ef_n2o_leaching_systems_w = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | leaching, f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_leaching_systems_w = [s.value for s in self.ef_n2o_leaching_systems_w]

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

            # Animal Waste PRP
            self.animal_waste_prp_wo = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt | prp | {"manure_management_type__name": utils.ManureManagementTypes.PRP.value}, f"Could not find Animal Waste PRP (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

            # Animal Waste PRP of other systems
            self.animal_waste_management_systems_wo = utils.get_or_raise(ipcc.LivestockAWMS, production_category_region_flt, f"Could not find Animal Waste Management Systems (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.animal_waste_management_systems_values_wo = [system.value for system in self.animal_waste_management_systems_wo]

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

            # PRP N2O Volatilization EF of other systems
            self.ef_n2o_volatilization_systems_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | volatilization, f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_volatilization_systems_wo = [s.value for s in self.ef_n2o_volatilization_systems_wo]

            # PRP N2O Leaching EF of other systems
            self.ef_n2o_leaching_systems_wo = utils.get_or_raise(ipcc.LivestockManureEF, manure_ef_flt | leaching, f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}", method="filter").exclude(**prp).order_by("manure_management_type__name")
            self.ef_n2o_leaching_systems_wo = [s.value for s in self.ef_n2o_leaching_systems_wo]

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
                "methane_constant": project.gw_potential.ch4,
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
                "percentage_prp_tier_2_start": module.prp_percentage_t2_start,
                "percentage_prp_tier_2_end": module.prp_percentage_t2_w,
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
                "nitrous_constant": project.gw_potential.n2o,
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
                "methane_constant": project.gw_potential.ch4,
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
                "percentage_prp_tier_2_start": module.prp_percentage_t2_start,
                "percentage_prp_tier_2_end": module.prp_percentage_t2_wo,
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
                "nitrous_constant": project.gw_potential.n2o,
                "volatilization_multiplier": self.volatilization_multi.value,
                "leaching_multiplier": self.LEACHING_MULTI,
                "delay": self.activity.delay,
            }

            log.debug(f"Inputs for WITHOUT: {inputs_wo}")

            self.math_wo = MathLivestock(**inputs_wo)
            self.math_wo.calculate_emissions()

        results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        log.debug("WITH breakdown")
        results_w.breakdown(by=BreakdownTypes.ACTIVITY)
        log.debug("WITHOUT breakdown")
        results_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug(f"Results for WITH: {results_w}")
        log.debug(f"Results for WITHOUT: {results_wo}")
        return (results_w, results_wo)


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

        return (self.results_w, self.results_wo)

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)


class IrrigationSystemCalculator(BaseCalculator):
    """
    Calculates the emissions of the irrigation system.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.ef = SimpleNamespace(value=0)

        self.inputs_w = {}
        self.inputs_wo = {}

        self.math_w = None
        self.math_wo = None

        self.results_w = None
        self.results_wo = None

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: IrrigationSystem = self.data

        try:
            self.ef = ipcc.IrrigationSystemData.objects.get(irrigation_system_type=module.irrigation_system_type)
        except ipcc.IrrigationSystemData.DoesNotExist:
            raise ValueError(f"Could not find EF for {module.irrigation_system_type.name}")

    def calculate(self) -> list[Result]:
        """
        Calculates the emissions of the irrigation system.
        """

        module: IrrigationSystem = self.data
        activity: Activity = module.parent.activity
        project: Project = activity.project

        self.get_defaults()

        self.inputs_w = {
            "ef_ref": self.ef.value,
            "ef_tier_2": module.ef_t2_start,
            "units_start": module.ha_start,
            "units_end": module.ha_w,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "rate_type": activity.change_rate.name,
            "delay": self.activity.delay,
        }

        self.math_w = NewIrrigation(**self.inputs_w)
        self.math_w.calculate_emissions()

        self.inputs_wo = {
            "ef_ref": self.ef.value,
            "ef_tier_2": module.ef_t2_wo,
            "units_start": module.ha_start,
            "units_end": module.ha_wo,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "rate_type": activity.change_rate.name,
            "delay": self.activity.delay,
        }

        self.math_wo = NewIrrigation(**self.inputs_wo)
        self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w, self.results_wo)

        return results_tuple


class IrrigationPhaseCalculator(BaseCalculator):

    def __init__(self, input) -> None:
        super().__init__(input)

        self.ef = SimpleNamespace(value=0)
        self.energy_db = SimpleNamespace(net_calorific_value=0, density=0)
        self.pressure = SimpleNamespace(avg_pressure=0)
        self.erh_electricity = SimpleNamespace(value=0)
        self.transportation_loss = SimpleNamespace(value=0)
        self.pumping_efficiency = SimpleNamespace(value=0)

        self.inputs_start = {}
        self.inputs_w = {}
        self.inputs_wo = {}

        self.math_start = None
        self.math_w = None
        self.math_wo = None

        self.results_start = None
        self.results_w = None
        self.results_wo = None

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: IrrigationPhase = self.data

        try:
            self.ef = ipcc.IrrigationPhaseData.objects.get(fuel_type=module.fuel_type)
        except ipcc.IrrigationPhaseData.DoesNotExist:
            raise ValueError(f"Could not find EF for {module.fuel_type.name}")

        try:
            self.energy_db = ipcc.EnergyDefaultEmissionFactor.objects.get(fuel_type=module.fuel_type)
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Energy Default Emission Factor for {module.fuel_type.name}. Please insert tier 2 values")

        try:
            self.pressure = ipcc.IrrigationPressureRequirement.objects.get(irrigation_system_type=module.irrigation_system_type)
            if self.pressure.bar_start is None or self.pressure.bar_end is None:
                raise ValueError(f"Please insert the tier 2 pressure requirement for {module.irrigation_system_type.name}")
        except ipcc.IrrigationPressureRequirement.DoesNotExist:
            raise ValueError(f"Could not find Pressure Requirement for {module.irrigation_system_type.name}")

        try:
            self.erh_electricity = IrrigationParameter.objects.get(name="ERH_ELECTRICITY").value if module.fuel_type.name == "Electricity" else None
        except IrrigationParameter.DoesNotExist:
            raise ValueError(f"Could not find ERH_ELECTRICITY")

        try:
            self.transportation_loss = IrrigationParameter.objects.get(name="TRANSPORTATION_LOSS")
        except IrrigationParameter.DoesNotExist:
            raise ValueError(f"Could not find TRANSPORTATION_LOSS")

        try:
            self.pumping_efficiency = IrrigationParameter.objects.get(name="PUMPING_EFFICIENCY")
        except IrrigationParameter.DoesNotExist:
            raise ValueError(f"Could not find PUMPING_EFFICIENCY")

    def calculate(self) -> list[Result]:
        module: IrrigationPhase = self.data
        activity: Activity = module.parent.activity
        project: Project = activity.project

        self.get_defaults()

        self.inputs_start = {
            "ef_default": self.ef.emission_factor,
            "ef_tier_2": module.ef_t2_start,
            "total_dynamic_head_tier_2": module.total_dynamic_head_t2,
            "average_pressure_default": self.pressure.avg_pressure,
            "average_pressure_tier_2": module.average_pressure_t2,
            "pumping_efficiency_default": self.pumping_efficiency.value,
            "pumping_efficiency_tier_2": module.pumping_efficiency_t2_start,
            "erh_electricity": self.erh_electricity,
            "fuel_net_calorific_values": self.energy_db.net_calorific_value,
            "fuel_density": self.energy_db.density,
            "depth": module.well_depth,
            "units_start": module.ha_start,
            "units_end": 0,
            "rate_type": activity.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "transportation_loss": self.transportation_loss.value if module.fuel_type.name == "Electricity" else 0,
            "gwir": module.gross_irrigation_water_start,
            "delay": self.activity.delay,
        }

        self.math_start = OperationPhaseIrrigation(**self.inputs_start)
        self.math_start.calculate_emissions()

        self.inputs_w = {
            "ef_default": self.ef.emission_factor,
            "ef_tier_2": module.ef_t2_w,
            "total_dynamic_head_tier_2": module.total_dynamic_head_t2,
            "average_pressure_default": self.pressure.avg_pressure,
            "average_pressure_tier_2": module.average_pressure_t2,
            "pumping_efficiency_default": self.pumping_efficiency.value,
            "pumping_efficiency_tier_2": module.pumping_efficiency_t2_w,
            "erh_electricity": self.erh_electricity,
            "fuel_net_calorific_values": self.energy_db.net_calorific_value,
            "fuel_density": self.energy_db.density,
            "depth": module.well_depth,
            "units_start": 0,
            "units_end": module.ha_w,
            "rate_type": activity.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "transportation_loss": self.transportation_loss.value if module.fuel_type.name == "Electricity" else 0,
            "gwir": module.gross_irrigation_water_w,
            "delay": self.activity.delay,
        }

        self.math_w = OperationPhaseIrrigation(**self.inputs_w)
        self.math_w.calculate_emissions()

        self.inputs_wo = {
            "ef_default": self.ef.emission_factor,
            "ef_tier_2": module.ef_t2_wo,
            "total_dynamic_head_tier_2": module.total_dynamic_head_t2,
            "average_pressure_default": self.pressure.avg_pressure,
            "average_pressure_tier_2": module.average_pressure_t2,
            "pumping_efficiency_default": self.pumping_efficiency.value,
            "pumping_efficiency_tier_2": module.pumping_efficiency_t2_wo,
            "erh_electricity": self.erh_electricity,
            "fuel_net_calorific_values": self.energy_db.net_calorific_value,
            "fuel_density": self.energy_db.density,
            "depth": module.well_depth,
            "units_start": 0,
            "units_end": module.ha_wo,
            "rate_type": activity.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "transportation_loss": self.transportation_loss.value if module.fuel_type.name == "Electricity" else 0,
            "gwir": module.gross_irrigation_water_wo,
            "delay": self.activity.delay,
        }

        self.math_wo = OperationPhaseIrrigation(**self.inputs_wo)
        self.math_wo.calculate_emissions()

        self.results_start = self.math_start.result if self.math_start else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w + self.results_start, self.results_wo + self.results_start)

        return results_tuple


class CoastalWetlandCalculator(BaseCalculator):
    """
    Calculates the emissions of the coastal wetland
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.agb = SimpleNamespace(value=0)
        self.bgb = SimpleNamespace(value=0)
        self.litter = SimpleNamespace(value=0)
        self.dw = SimpleNamespace(value=0)
        self.soil_1m = SimpleNamespace(value=0)
        self.ef_drainage = SimpleNamespace(value=0)
        self.pc_c_lost_excavation = SimpleNamespace(value=0)
        self.rewetting_c = SimpleNamespace(value=0)
        self.rewetting_ch4 = SimpleNamespace(value=0)

        self.soil_type_name = ""

        self.inputs_w = {}
        self.inputs_wo = {}

        self.math_w = None
        self.math_wo = None

        self.results_w = None
        self.results_wo = None

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: CoastalWetland = self.data
        project: Project = module.activity.project

        cm = {
            "climate": project.climate,
            "moisture": project.moisture,
        }

        self.soil_type_name = module.soil_type_t2.name if module.soil_type_t2 else "Mineral"
        self.salinity_type = module.avg_salinity_t2 if module.avg_salinity_t2 else SalinityType.objects.get(value=">18")

        try:
            self.agb = ipcc.CoastalAGB.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.CoastalAGB.DoesNotExist:
            raise ValueError(f"Could not find AGB for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}. Please insert tier 2 values for the relevant scenarios.")

        try:
            self.bgb = ipcc.CoastalBGB.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.CoastalBGB.DoesNotExist:
            raise ValueError(f"Could not find BGB for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}. Please insert tier 2 values for the relevant scenarios.")

        try:
            self.litter = ipcc.CoastalLitter.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.CoastalLitter.DoesNotExist:
            raise ValueError(f"Could not find Litter for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}. Please insert tier 2 values for the relevant scenarios.")

        try:
            self.dw = ipcc.CoastalDeadwood.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.CoastalDeadwood.DoesNotExist:
            raise ValueError(f"Could not find Deadwood for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}. Please insert tier 2 values for the relevant scenarios.")

        try:
            self.soil_1m = ipcc.DefaultSoilCarbonStock.objects.get(**cm, land_use_type=module.land_use_type, soil_type__name=self.soil_type_name)
        except ipcc.DefaultSoilCarbonStock.DoesNotExist:
            raise ValueError(f"Could not find Soil 1m for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}, {self.soil_type_name}")

        try:
            self.ef_drainage = ipcc.DrainageEmissionFactor.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.DrainageEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find EF Drainage for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}. Please insert tier 2 values for the relevant scenarios.")

        try:
            self.pc_c_lost_excavation = CoastalWetlandParameter.objects.get(name="PERCENTAGE_C_LOST_EXCAVATION")
        except CoastalWetlandParameter.DoesNotExist:
            raise ValueError(f"Could not find PC C Lost Excavation")

        try:
            self.rewetting_c = ipcc.RewettingCarbonFactor.objects.get(**cm, land_use_type=module.land_use_type, soil_type__name=self.soil_type_name)
        except ipcc.RewettingCarbonFactor.DoesNotExist:
            raise ValueError(f"Could not find Rewetting C for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}. Please insert tier 2 values for the relevant scenarios.")

        try:
            self.rewetting_ch4 = ipcc.RewettingMethaneFactor.objects.get(**cm, land_use_type=module.land_use_type, salinity=self.salinity_type)
        except ipcc.RewettingMethaneFactor.DoesNotExist:
            raise ValueError(f"Could not find Rewetting CH4 for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}. Please insert tier 2 values for the relevant scenarios.")

    def calculate(self) -> Result:
        """
        Calculates the emissions of the coastal wetland
        """

        module: CoastalWetland = self.data
        project: Project = module.activity.project

        self.get_defaults()

        if module.is_with():
            self.inputs_w = {
                "maximum_area_for_water_management": module.area,
                "area_drained_start": module.area_under_drainage_start,
                "area_drained_end": module.area_under_drainage_w,
                "rate_type": module.activity.change_rate.name,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "agb_default": self.agb.value,
                "bgb_default": self.bgb.value,
                "litter_default": self.litter.value,
                "deadwood_default": self.dw.value,
                "soil_1m_default": self.soil_1m.value,
                "EF_drainage_default": self.ef_drainage.value,
                "agb_tier_2": module.agb_t2_w,
                "bgb_tier_2": module.bgb_t2_w,
                "litter_tier_2": module.litter_t2_w,
                "deadwood_tier_2": module.deadwood_t2_w,
                "soil_1m_tier_2": module.soc_t2_w,
                "EF_drainage_tier_2": module.drainage_ef_t2_w,
                "area_excavated_start": module.drained_area_excavated_start,
                "area_excavated_end": module.drained_area_excavated_w,
                "area_revegated_start": module.area_w_restored_vegetation_start,
                "area_revegated_end": module.area_w_restored_vegetation_w,
                "percentage_c_lost_excavation_default": self.pc_c_lost_excavation.value,
                "percentage_c_lost_excavation_tier_2": module.pc_c_lost_after_excavation_t2_w,
                "ef_rewetting_carbon_default": self.rewetting_c.value,
                "ef_rewetting_methane_default": self.rewetting_ch4.value,
                "ef_rewetting_carbon_tier_2": module.co2_rewetting_t2_start,
                "ef_rewetting_methane_tier_2": module.ch4_rewetting_t2_w,
                "soil_type": module.avg_salinity_t2.value if module.avg_salinity_t2 else None,
                "methane_constant": project.gw_potential.ch4,
                "delay": self.activity.delay,
            }

            self.math_w = MathCoastalWetland(**self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            self.inputs_wo = {
                "maximum_area_for_water_management": module.area,
                "area_drained_start": module.area_under_drainage_start,
                "area_drained_end": module.area_under_drainage_wo,
                "rate_type": module.activity.change_rate.name,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "agb_default": self.agb.value,
                "bgb_default": self.bgb.value,
                "litter_default": self.litter.value,
                "deadwood_default": self.dw.value,
                "soil_1m_default": self.soil_1m.value,
                "EF_drainage_default": self.ef_drainage.value,
                "agb_tier_2": module.agb_t2_wo,
                "bgb_tier_2": module.bgb_t2_wo,
                "litter_tier_2": module.litter_t2_wo,
                "deadwood_tier_2": module.deadwood_t2_wo,
                "soil_1m_tier_2": module.soc_t2_wo,
                "EF_drainage_tier_2": module.drainage_ef_t2_wo,
                "area_excavated_start": module.drained_area_excavated_start,
                "area_excavated_end": module.drained_area_excavated_wo,
                "area_revegated_start": module.area_w_restored_vegetation_start,
                "area_revegated_end": module.area_w_restored_vegetation_wo,
                "percentage_c_lost_excavation_default": self.pc_c_lost_excavation.value,
                "percentage_c_lost_excavation_tier_2": module.pc_c_lost_after_excavation_t2_wo,
                "ef_rewetting_carbon_default": self.rewetting_c.value,
                "ef_rewetting_methane_default": self.rewetting_ch4.value,
                "ef_rewetting_carbon_tier_2": module.co2_rewetting_t2_wo,
                "ef_rewetting_methane_tier_2": module.ch4_rewetting_t2_wo,
                "soil_type": module.avg_salinity_t2.value if module.avg_salinity_t2 else None,
                "methane_constant": project.gw_potential.ch4,
                "delay": self.activity.delay,
            }

            self.math_wo = MathCoastalWetland(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w, self.results_wo)

        return results_tuple

    def defaults(self) -> DefaultData:
        self.calculate()

        module: CoastalWetland = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if module.is_luc_remaining_same():
            math_start = MathCoastalWetland(**self.inputs_w)
            math_start_defaults = math_start.evaluate_tier_2_defaults()
            defaults_start.update(math_start_defaults.start)
            defaults_start.update(math_start_defaults.other)
        elif module.is_business_as_usual():
            math_start_wo = MathCoastalWetland(**self.inputs_wo)
            math_start_wo_defaults = math_start_wo.evaluate_tier_2_defaults()
            defaults_start.update(math_start_wo_defaults.start)
            defaults_start.update(math_start_wo_defaults.other)

        if module.is_with():
            math_w = MathCoastalWetland(**self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.start)
            defaults_w.update(math_w_defaults.other)

        if module.is_without():
            math_wo = MathCoastalWetland(**self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.start)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class WaterbodyCalculator(BaseCalculator):
    """
    Calculator for waterbody modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.methane_emission_factor = SimpleNamespace(value=0)
        self.trophic_state_start = SimpleNamespace(value=0)
        self.trophic_state_w = SimpleNamespace(value=0)
        self.trophic_state_wo = SimpleNamespace(value=0)

        self.inputs_start = []
        self.inputs_w = []
        self.inputs_wo = []

        self.math_start = None
        self.math_w = None
        self.math_wo = None

        self.results_start = None
        self.results_w = None
        self.results_wo = None

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: Waterbody = self.data
        project = module.activity.project

        try:
            self.methane_emission_factor = ipcc.OtherConstructedWaterbodiesEmissionFactor.objects.get(climate=project.climate, moisture=project.moisture, waterbody_type=module.waterbody_type)
        except ipcc.OtherConstructedWaterbodiesEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Methane Emission Factor for {module.waterbody_type.name}, {project.climate.name}, {project.moisture.name}")

        if module.is_start():
            try:
                self.trophic_state_start = ipcc.TrophicStateFactor.objects.get(trophic_type=module.trophic_type_start)
            except ipcc.TrophicStateFactor.DoesNotExist:
                raise ValueError(f"Could not find Trophic State Factor for {module.trophic_type_start.name}")

        if module.is_with():
            try:
                self.trophic_state_w = ipcc.TrophicStateFactor.objects.get(trophic_type=module.trophic_type_w)
            except ipcc.TrophicStateFactor.DoesNotExist:
                raise ValueError(f"Could not find Trophic State Factor for {module.trophic_type_w.name}")

        if module.is_without():
            try:
                self.trophic_state_wo = ipcc.TrophicStateFactor.objects.get(trophic_type=module.trophic_type_wo)
            except ipcc.TrophicStateFactor.DoesNotExist:
                raise ValueError(f"Could not find Trophic State Factor for {module.trophic_type_wo.name}")

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
            "methane_constant": project.gw_potential.ch4,
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
                "methane_constant": project.gw_potential.ch4,
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
                "methane_constant": project.gw_potential.ch4,
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

        self.ef_onsite_start = SimpleNamespace(value=0)
        self.ef_onsite_w = SimpleNamespace(value=0)
        self.ef_onsite_wo = SimpleNamespace(value=0)

        self.ef_offsite_start = SimpleNamespace(value=0)
        self.ef_offsite_w = SimpleNamespace(value=0)
        self.ef_offsite_wo = SimpleNamespace(value=0)

        self.dry_matter_w = SimpleNamespace(value=0)
        self.dry_matter_wo = SimpleNamespace(value=0)

        self.fire_ref = SimpleNamespace(value=0)

        self.rewetting_start = SimpleNamespace(value=0)
        self.rewetting_w = SimpleNamespace(value=0)
        self.rewetting_wo = SimpleNamespace(value=0)

        self.onsite_ef_w = SimpleNamespace(value=0)
        self.onsite_ef_wo = SimpleNamespace(value=0)

        self.offsite_ef_w = SimpleNamespace(value=0)
        self.offsite_ef_wo = SimpleNamespace(value=0)

        self.conversion_factor_w = SimpleNamespace(value=0)
        self.conversion_factor_wo = SimpleNamespace(value=0)

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
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find EF On-Site Start for {module_type_start}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.ef_offsite_start = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_start, peat_type=module.peat_type, site_location_type__name="Off-Site")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find EF Off-Site Start for {module_type_start}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.rewetting_start = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=module.peat_type, module_type__name=module_type_start)
            except ipcc.OrganicSoilRewettingEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find Rewetting Start for {module.peat_type.name}, {module_type_start}, {project.climate.name}, {project.moisture.name}")

        if module.is_with():
            try:
                self.ef_onsite_w = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_w, peat_type=module.peat_type, site_location_type__name="On-Site")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find EF On-Site W for {module_type_w}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.ef_offsite_w = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_w, peat_type=module.peat_type, site_location_type__name="Off-Site")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find EF Off-Site W for {module_type_w}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")
            self.fire_used_w = module.fire_type_w is not None
            if self.fire_used_w:
                try:
                    self.dry_matter_w = ipcc.OrganicSoilFuelConsumption.objects.get(**cm, fire_type=module.fire_type_w)
                except ipcc.OrganicSoilFuelConsumption.DoesNotExist:
                    raise ValueError(f"Could not find Dry Matter W for {module.fire_type_w.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.rewetting_w = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=module.peat_type, module_type__name=module_type_w)
            except ipcc.OrganicSoilRewettingEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find Rewetting W for {module.peat_type.name}, {module_type_w}, {project.climate.name}, {project.moisture.name}")
            try:
                self.onsite_ef_w = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=module.peat_type, site_location_type__name="On-Site")
            except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find On-Site EF W for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.offsite_ef_w = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=module.peat_type, site_location_type__name="Off-Site")
            except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find Off-Site EF W for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.conversion_factor_w = ipcc.PeatExtractionConversionFactor.objects.get(**cm, peat_type=module.peat_type)
            except ipcc.PeatExtractionConversionFactor.DoesNotExist:
                raise ValueError(f"Could not find Conversion Factor W for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        if module.is_without():
            try:
                self.ef_onsite_wo = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_wo, peat_type=module.peat_type, site_location_type__name="On-Site")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find EF On-Site WO for {module_type_wo}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.ef_offsite_wo = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_wo, peat_type=module.peat_type, site_location_type__name="Off-Site")
            except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find EF Off-Site WO for {module_type_wo}, {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")
            self.fire_used_wo = module.fire_type_wo is not None
            if self.fire_used_wo:
                try:
                    self.dry_matter_wo = ipcc.OrganicSoilFuelConsumption.objects.get(**cm, fire_type=module.fire_type_wo)
                except ipcc.OrganicSoilFuelConsumption.DoesNotExist:
                    raise ValueError(f"Could not find Dry Matter WO for {module.fire_type_wo.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.rewetting_wo = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=module.peat_type, module_type__name=module_type_wo)
            except ipcc.OrganicSoilRewettingEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find Rewetting WO for {module.peat_type.name}, {module_type_wo}, {project.climate.name}, {project.moisture.name}")

            ##### Peat Extraction Inputs #####
            try:
                self.onsite_ef_wo = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=module.peat_type, site_location_type__name="On-Site")
            except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find On-Site EF WO for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.offsite_ef_wo = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=module.peat_type, site_location_type__name="Off-Site")
            except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
                raise ValueError(f"Could not find Off-Site EF WO for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")
            try:
                self.conversion_factor_wo = ipcc.PeatExtractionConversionFactor.objects.get(**cm, peat_type=module.peat_type)
            except ipcc.PeatExtractionConversionFactor.DoesNotExist:
                raise ValueError(f"Could not find Conversion Factor WO for {module.peat_type.name}, {project.climate.name}, {project.moisture.name}")

    def calculate(self) -> Result:
        super().calculate()

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
            "dry_matter_ref_fire": self.dry_matter_w.value if self.fire_used_w else None,
            "dry_matter_tier_2_fire": input.mean_dry_matter_t2_w,
            "percentage_area_burned_end": input.soil_fire_impact_percentage_w,
            "ef_co2_ref_fire": self.fire_ref.co2,
            "ef_co2_tier_2_fire": input.fire_on_soil_co2_t2_w,
            "ef_co_ref_fire": self.fire_ref.co,
            "ef_co_tier_2_fire": input.fire_on_soil_co_t2_w,
            "ef_ch4_ref_fire": self.fire_ref.ch4,
            "ef_ch4_tier_2_fire": input.fire_on_soil_ch4_t2_w,
            "methane_constant": project.gw_potential.ch4,
            "rate_type": input.activity.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "nitrous_constant": project.gw_potential.n2o,
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
                "methane_constant": project.gw_potential.ch4,
                "nitrous_constant": project.gw_potential.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "conversion_factor_volume": self.conversion_factor_w.volume,
                "peat_density_tier_2_start": input.peat_density_t2_w,
                "conversion_factor_weight": self.conversion_factor_w.weight,
                "peat_extraction_height_start": input.peat_extraction_height_start,
                "peat_extraction_height_end": input.peat_extraction_height_w,
            }

            self.peat_extraction_math_w = MathPeatExtraction(**self.peat_extraction_inputs_w)
            self.peat_extraction_math_w.calculate_emissions()

        self.organic_soil_inputs_wo = {
            "fire_boolean_end": input.fire_type_wo is not None,
            "fire_periodicity_end": input.soil_fire_periodicity_wo,
            "area_affected_by_action_end": self.area_affected_by_module,
            "dry_matter_ref_fire": self.dry_matter_wo.value if self.fire_used_wo else None,
            "dry_matter_tier_2_fire": input.mean_dry_matter_t2_wo,
            "percentage_area_burned_end": input.soil_fire_impact_percentage_wo,
            "ef_co2_ref_fire": self.fire_ref.co2,
            "ef_co2_tier_2_fire": input.fire_on_soil_co2_t2_wo,
            "ef_co_ref_fire": self.fire_ref.co,
            "ef_co_tier_2_fire": input.fire_on_soil_co_t2_wo,
            "ef_ch4_ref_fire": self.fire_ref.ch4,
            "ef_ch4_tier_2_fire": input.fire_on_soil_ch4_t2_wo,
            "methane_constant": project.gw_potential.ch4,
            "rate_type": input.activity.change_rate.name,
            "implementation_time": self.activity.implementation_years,
            "capitalization_time": self.activity.capitalization_years,
            "nitrous_constant": project.gw_potential.n2o,
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
                "methane_constant": project.gw_potential.ch4,
                "nitrous_constant": project.gw_potential.n2o,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "weight_peat": self.conversion_factor_wo.weight,
                "mass_tonnes_tier_2": input.peat_density_t2_wo,
                "conversion_factor_volume": self.conversion_factor_wo.volume,
                "c_fraction_ref": 1,  # TODO: Should be conversion_factor_wo.volume,
                "extraction_height_start": input.peat_extraction_height_start,
                "extraction_height_end": input.peat_extraction_height_wo,
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


class ForestManagementCalculator(BaseCalculator):
    """
    # TODO: Review
    """

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)

    def calculate(self) -> Result:
        """"""

        module: LandModule = self.data
        luc: LandUseChange = module.land_use_change
        project: Project = module.activity.project
        area = luc.area if luc else module.area

        # TODO: Review
        land_use_type = module.land_use_type_start
        if luc:
            # NOTE: This if is useless. It's always True
            land_use_type = module.land_use_type_start if luc.module_type_start.class_name == "ForestManagement" else module.land_use_type_start
            land_use_type = LandUseType.objects.get(name=land_use_type.name)

        forest: ForestManagement = luc.forestmanagement if luc else module

        AGB_GROWTH_NOT_FOUND = f"AGB Growth not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region. Please insert t2 values for AGB Growth Rate for all scenarios."
        BGB_UNDER_20_NOT_FOUND = f"BGB (under 20 years) not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region. Please insert t2 values for BGB (under 20 years) for all scenarios."
        BGB_OVER_20_NOT_FOUND = f"BGB (over 20 years) not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region. Please insert t2 values for BGB (over 20 years) for all scenarios."
        LITTER_DW_NOT_FOUND = f"Litter/Deadwood Carbon Stock reference value not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region."
        SOC_NOT_FOUND = f"Soil Organic Carbon reference value not found for the given parameters in {project.climate.name} climate, {project.moisture.name} moisture, {project.soil_type.name} soil type."

        is_afforestation_w = luc and luc.module_type_w.class_name == "ForestManagement" and luc.module_type_start.class_name != "ForestManagement"
        is_afforestation_wo = luc and luc.module_type_wo.class_name == "ForestManagement" and luc.module_type_start.class_name != "ForestManagement"

        has_t2_growth_start = forest.agb_growth_rate_gt_20_yrs_t2_start and forest.agb_growth_rate_le_20_yrs_t2_start
        has_t2_growth_w = forest.agb_growth_rate_gt_20_yrs_t2_w and forest.agb_growth_rate_le_20_yrs_t2_w
        has_t2_growth_wo = forest.agb_growth_rate_gt_20_yrs_t2_wo and forest.agb_growth_rate_le_20_yrs_t2_wo

        crluft = {
            "climate": project.climate,
            "region": project.country.region,
            "land_use_type": land_use_type,
            "forest_type": forest.forest_type,
        }

        module_start = module_w = module_wo = module

        if luc:
            module_start, module_w, module_wo = luc.get_modules()

        flu_start = get_flu_data(module_start, project.climate, project.moisture, utils.ScenarioTypes.START)

        fi_start = get_fi_data(module_start, project.climate, project.moisture, utils.ScenarioTypes.START)
        fi_w = get_fi_data(module_w, project.climate, project.moisture, utils.ScenarioTypes.WITH)
        fi_wo = get_fi_data(module_wo, project.climate, project.moisture, utils.ScenarioTypes.WITHOUT)

        fmg_start = get_fmg_data(module_start, project.climate, project.moisture, utils.ScenarioTypes.START)
        fmg_w = get_fmg_data(module_w, project.climate, project.moisture, utils.ScenarioTypes.WITH)
        fmg_wo = get_fmg_data(module_wo, project.climate, project.moisture, utils.ScenarioTypes.WITHOUT)

        # NOTE: For non-forest is ipcc.AfforestationCombustionFactor (used in OLUC?)
        combustion_factor_w: ipcc.ForestCombustionFactor = utils.get_or_raise(ipcc.ForestCombustionFactor, {"land_use_type": module.land_use_type_w, "climate": project.climate, "forest_type": forest.forest_type}, f"Combustion Factor W not found for {module.land_use_type_w.name}, {project.climate.name}, {forest.forest_type.name}")
        combustion_factor_wo: ipcc.ForestCombustionFactor = utils.get_or_raise(ipcc.ForestCombustionFactor, {"land_use_type": module.land_use_type_wo, "climate": project.climate, "forest_type": forest.forest_type}, f"Combustion Factor WO not found for {module.land_use_type_wo.name}, {project.climate.name}, {forest.forest_type.name}")

        mangroves_data = None
        try:
            mangroves_data = ipcc.DataOnMangrove.objects.get(climate=project.climate, moisture=project.moisture)
        except ipcc.DataOnMangrove.DoesNotExist:
            pass

        try:
            socref = ipcc.SoilOrganicCarbon.objects.get(climate=project.climate, moisture=project.moisture, soil_type=project.soil_type)
        except ipcc.SoilOrganicCarbon.DoesNotExist:
            socref = None

        if not socref and not project.soc_ref_t2:
            raise ValueError(SOC_NOT_FOUND)

        try:
            litter_dw = ipcc.LitterDeadwoodCarbonStock.objects.get(climate=project.climate, forest_type=forest.forest_type, land_use_type=land_use_type)
        except ipcc.LitterDeadwoodCarbonStock.DoesNotExist:
            raise ValueError(LITTER_DW_NOT_FOUND)

        try:
            agb_growth = ipcc.ForestManagementAGBGrowth.objects.get(**crluft)
        except ipcc.ForestManagementAGBGrowth.DoesNotExist:
            agb_growth = None

        if not agb_growth and (not has_t2_growth_start or not has_t2_growth_w or not has_t2_growth_wo):
            raise ValueError(AGB_GROWTH_NOT_FOUND)

        before_2_yrs = agb_growth.value_upto_20_years
        after_20_yrs = agb_growth.value_after_20_years

        bgb_before_20_yrs = ipcc.ForestManagementBGB.objects.get_max_below_threshold(**crluft, threshold=before_2_yrs)
        if not bgb_before_20_yrs:
            raise ValueError(BGB_UNDER_20_NOT_FOUND)

        bgb_after_20_yrs = ipcc.ForestManagementBGB.objects.get_max_below_threshold(**crluft, threshold=after_20_yrs)
        if not bgb_after_20_yrs:
            raise ValueError(BGB_OVER_20_NOT_FOUND)

        # ForestManagement start/w/wo forest is the same
        # forest_condition_type is based on implementation years (< 20, > 20)
        """
        Per secondary, se parliamo di AFFORESTATION dovremmo usare i valori per Secondary < 20 per AGB growth. AGB max dovrebbe essere Secondary<20 (per i progetti di meno di 20 anni) e Secondary>20 (se i progetti durano da 21 anni in su)
        Se parliamo di forest management invece usiamo i valori di Secondary > 20 sia per AGB growth che per AGB max.
        """

        agb_under_20 = forest.get_agb_growth_ref(land_use_type=land_use_type, from_year=0)
        agb_over_20 = forest.get_agb_growth_ref(land_use_type=land_use_type, from_year=21 if "Secondary" in forest.forest_condition_type.name else 0)

        # START - Reference Values for forest remaining forest
        agb_max_w = statistics.mean([agb_over_20.agb_min, agb_over_20.agb_max])
        agb_growth_over_20_w = statistics.mean([agb_over_20.agb_growth_max, agb_over_20.agb_growth_min])
        agb_growth_under_20_w = agb_growth_over_20_w
        agb_start_w = agb_max_w
        flu_w = SimpleNamespace(value=1)
        litter_dw_start_w = litter_dw
        litter_dw_max_w = litter_dw

        # TODO: What reference values do I choose for the start scenario?
        # TODO: Add litter start, litter end. Affo -> start=0, end=reference_values. Forest -> start=reference_values, end=refernce_values

        agb_max_wo = statistics.mean([agb_over_20.agb_min, agb_over_20.agb_max])
        agb_growth_over_20_wo = statistics.mean([agb_over_20.agb_growth_max, agb_over_20.agb_growth_min])
        agb_growth_under_20_wo = agb_growth_over_20_wo
        agb_start_wo = agb_max_wo
        flu_wo = SimpleNamespace(value=1)
        litter_dw_start_wo = litter_dw
        litter_dw_max_wo = litter_dw
        # END - Reference Values for forest remaining forest

        if is_afforestation_w:
            agb_max_w = statistics.mean([agb_over_20.agb_min, agb_over_20.agb_max]) if self.activity.implementation_years > 20 else statistics.mean([agb_under_20.agb_min, agb_under_20.agb_max])
            agb_growth_under_20_w = statistics.mean([agb_under_20.agb_growth_max, agb_under_20.agb_growth_min])
            agb_growth_over_20_w = agb_growth_under_20_w
            agb_start_w = 0
            flu_w = flu_start
            litter_dw_start_w = SimpleNamespace(litter=0, dw=0)

        if is_afforestation_wo:
            agb_max_wo = statistics.mean([agb_over_20.agb_min, agb_over_20.agb_max]) if self.activity.implementation_years > 20 else statistics.mean([agb_under_20.agb_min, agb_under_20.agb_max])
            agb_growth_under_20_wo = statistics.mean([agb_under_20.agb_growth_max, agb_under_20.agb_growth_min])
            agb_growth_over_20_wo = agb_growth_under_20_wo
            agb_start_wo = 0
            flu_wo = flu_start
            litter_dw_start_wo = SimpleNamespace(litter=0, dw=0)

        disturbances: list[ForestDisturbance] = module.disturbances.all()

        som: ipcc.NitrousEmissionFactor = utils.get_or_raise(ipcc.NitrousEmissionFactor, {"moisture": project.moisture}, f"SOM not found for {project.moisture.name} moisture.")

        math_w = None
        math_wo = None

        if module.is_with():

            inputs_w = [
                self.activity.capitalization_years,
                self.activity.implementation_years,
                module.activity.change_rate.name,
                0,
                area,
                forest.rotation_length_yrs_w,
                forest.rotation_start_year_t2_w,
                forest.rotation_percentage_biomass_for_energy_w,
                bgb_before_20_yrs.threshold,
                bgb_before_20_yrs.value,
                bgb_after_20_yrs.value,
                forest.bgb_growth_rate_le_20_yrs_t2_w,
                forest.bgb_growth_rate_gt_20_yrs_t2_w,
                agb_start_w,
                forest.agb_t2_w,
                agb_growth_under_20_w,
                forest.agb_growth_rate_le_20_yrs_t2_w,
                agb_growth_over_20_w,
                forest.agb_growth_rate_gt_20_yrs_t2_w,
                agb_max_w,
                None,  # TODO: max_bgb_value ?? Unused in math model
                list(disturbances.values_list("recurrence_yrs_w", flat=True)),
                list(disturbances.values_list("percentage_biomass_destruction_w", flat=True)),
                list(disturbances.values_list("start_year_t2_w", flat=True)),
                forest.logging_recurrence_yrs_w,
                forest.logging_percentage_agb_logged_w,
                forest.logging_percentage_biomass_for_energy_w,
                forest.logging_start_year_t2_w,
                litter_dw.litter,
                litter_dw_start_w.litter,
                litter_dw_max_w.litter,
                forest.litter_t2_w,
                litter_dw.dw,
                litter_dw_start_w.dw,
                litter_dw_max_w.dw,
                forest.deadwood_t2_w,
                socref.value,  ##### REFACTOR STARTS HERE
                socref.value,
                project.soc_ref_t2,
                project.soc_ref_t2,
                fmg_start.value,
                fmg_w.value,
                forest.fmg_t2_start,
                forest.fmg_t2_w,
                flu_start.value,
                flu_w.value,
                forest.flu_t2_start,
                forest.flu_t2_w,
                fi_start.value,
                fi_w.value,
                forest.fi_t2_start,
                forest.fi_t2_w,
                project.gw_potential.ch4,
                project.gw_potential.n2o,
                combustion_factor_w.value,
                combustion_factor_w.ch4,
                combustion_factor_w.n2o,
                combustion_factor_w.co2,
                utils.MANGROVE_FACTOR if mangroves_data is not None else utils.NON_MANGROVE_FACTOR,
                forest.average_yearly_degradation_percentage_w,
                som.value,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                self.activity.delay,
            ]

            math_w = MathForestManagement(*inputs_w)
            math_w.calculate_emissions()

        if module.is_without():

            inputs_wo = [
                self.activity.capitalization_years,
                self.activity.implementation_years,
                module.activity.change_rate.name,
                0,
                area,
                forest.rotation_length_yrs_wo,
                forest.rotation_start_year_t2_wo,
                forest.rotation_percentage_biomass_for_energy_wo,
                bgb_before_20_yrs.threshold,
                bgb_before_20_yrs.value,
                bgb_after_20_yrs.value,
                forest.bgb_growth_rate_le_20_yrs_t2_wo,
                forest.bgb_growth_rate_gt_20_yrs_t2_wo,
                agb_start_wo,
                forest.agb_t2_wo,
                agb_growth_under_20_wo,
                forest.agb_growth_rate_le_20_yrs_t2_wo,
                agb_growth_over_20_wo,
                forest.agb_growth_rate_gt_20_yrs_t2_wo,
                agb_max_wo,
                None,  # TODO: max_bgb_value ?? Unused in math model
                list(disturbances.values_list("recurrence_yrs_wo", flat=True)),
                list(disturbances.values_list("percentage_biomass_destruction_wo", flat=True)),
                list(disturbances.values_list("start_year_t2_wo", flat=True)),
                forest.logging_recurrence_yrs_wo,
                forest.logging_percentage_agb_logged_wo,
                forest.logging_percentage_biomass_for_energy_wo,
                forest.logging_start_year_t2_wo,
                litter_dw.litter,
                litter_dw_start_wo.litter,
                litter_dw_max_wo.litter,
                forest.litter_t2_wo,
                litter_dw.dw,
                litter_dw_start_wo.dw,
                litter_dw_max_wo.dw,
                forest.deadwood_t2_wo,
                socref.value,
                socref.value,
                project.soc_ref_t2,
                project.soc_ref_t2,
                fmg_start.value,
                fmg_wo.value,
                forest.fmg_t2_start,
                forest.fmg_t2_wo,
                flu_start.value,
                flu_wo.value,
                forest.flu_t2_start,
                forest.flu_t2_wo,
                fi_start.value,
                fi_wo.value,
                forest.fi_t2_start,
                forest.fi_t2_wo,
                project.gw_potential.ch4,
                project.gw_potential.n2o,
                combustion_factor_wo.value,
                combustion_factor_wo.ch4,
                combustion_factor_wo.n2o,
                combustion_factor_wo.co2,
                utils.MANGROVE_FACTOR if mangroves_data is not None else utils.NON_MANGROVE_FACTOR,
                forest.average_yearly_degradation_percentage_w,
                som.value,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                self.activity.delay,
            ]

            math_wo = MathForestManagement(*inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (results_w, results_wo)

        results_w.plot_emissions_and_aggregate_by_activity("forest_with")
        results_wo.plot_emissions_and_aggregate_by_activity("forest_without")

        return results_tuple

    def defaults(self) -> DefaultData:
        return super().defaults()


class DegradedLandCalculator(LandModuleCalculator):
    """
    Calculator for annual cropping modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.biomass_ef_start: SimpleNamespace | ipcc.ForestTotalBiomass = SimpleNamespace(value=0)
        self.biomass_ef_w: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)
        self.biomass_ef_wo: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)

    def calculate(self) -> Result:
        module: DegradedLand = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        self.get_defaults()

        if module.is_luc_remaining_same():
            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_w,
            }

            self.math_start_w = MathNotCultivatedLand(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if module.is_business_as_usual():
            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_wo,
            }

            self.math_start_wo = MathNotCultivatedLand(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module.is_with():
            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_w,
            }

            self.math_w = MathNotCultivatedLand(**self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_wo,
            }

            self.math_wo = MathNotCultivatedLand(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w + self.results_start_w, self.results_wo + self.results_start_wo)

        return results_tuple

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: DegradedLand = self.data
        activity: Activity = module.activity
        project: Project = activity.project
        luc: LandUseChange = module.land_use_change

        climate: Climate = activity.climate_t2 or project.climate
        moisture: Moisture = activity.moisture_t2 or project.moisture
        soil_type: SoilType = project.soil_type

        moisture_flt = {"moisture": moisture}
        soil_flt = {"soil_type": soil_type}
        cm = {"climate": climate, "moisture": moisture}

        module_start = module_w = module_wo = module

        if luc:
            module_start, module_w, module_wo = luc.get_modules()

        if module.is_luc_remaining_same() or module.is_business_as_usual():
            self.flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.emission_factors_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.biomass_ef_start = utils.get_or_raise(ipcc.ForestTotalBiomass, cm | {"continent": project.country.region, "land_use_type": module.land_use_type_start}, f"ForestTotalBiomass for {module.land_use_type_start.name} land use type in {project.climate.name} climate and {moisture.name} moisture in {project.country.region.name} region does not exist")

        if module.is_with():
            self.flu_w = get_flu_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
            self.fmg_w = get_fmg_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
            self.fi_w = get_fi_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
            self.emission_factors_w = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.biomass_ef_w = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, cm | {"continent": project.country.region, "land_use_type": module.land_use_type_w}, f"ForestTotalBiomass for {module.land_use_type_w.name} land use type in {project.climate.name} climate and {moisture.name} moisture in {project.country.region.name} region does not exist")

        if module.is_without():
            self.flu_wo = get_flu_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.fmg_wo = get_fmg_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.fi_wo = get_fi_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.emission_factors_wo = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.biomass_ef_wo = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, cm | {"continent": project.country.region, "land_use_type": module.land_use_type_wo}, f"ForestTotalBiomass for {module.land_use_type_wo.name} land use type in {project.climate.name} climate and {moisture.name} moisture in {project.country.region.name} region does not exist")

        if module.is_ready() and calculate:
            self.calculate()


class SetAsideCalculator(LandModuleCalculator):
    """
    Calculator for annual cropping modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.biomass_ef_start: SimpleNamespace | ipcc.ForestTotalBiomass = SimpleNamespace(value=0)
        self.biomass_ef_w: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)
        self.biomass_ef_wo: SimpleNamespace | ipcc.TotalBiomassAfterDefo = SimpleNamespace(value=0)

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)

        module: SetAside = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        moisture_flt = {"moisture": self.moisture}
        cm = {"climate": self.climate, "moisture": self.moisture}

        if module.is_luc_remaining_same() or module.is_business_as_usual():
            self.emission_factors_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {self.moisture.name} moisture does not exist")
            self.biomass_ef_start = utils.get_or_raise(ipcc.ForestTotalBiomass, cm | {"continent": project.country.region, "land_use_type": module.land_use_type_start}, f"ForestTotalBiomass for {module.land_use_type_start.name} land use type in {project.climate.name} climate and {self.moisture.name} moisture in {project.country.region.name} region does not exist")

        if module.is_with():
            self.emission_factors_w = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {self.moisture.name} moisture does not exist")
            self.biomass_ef_w = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, cm | {"continent": project.country.region, "land_use_type": module.land_use_type_w}, f"ForestTotalBiomass for {module.land_use_type_w.name} land use type in {project.climate.name} climate and {self.moisture.name} moisture in {project.country.region.name} region does not exist")

        if module.is_without():
            self.emission_factors_wo = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {self.moisture.name} moisture does not exist")
            self.biomass_ef_wo = utils.get_or_raise(ipcc.TotalBiomassAfterDefo, cm | {"continent": project.country.region, "land_use_type": module.land_use_type_wo}, f"ForestTotalBiomass for {module.land_use_type_wo.name} land use type in {project.climate.name} climate and {self.moisture.name} moisture in {project.country.region.name} region does not exist")

        if module.is_ready() and calculate:
            self.calculate()

    def calculate(self) -> Result:
        module: SetAside = self.module
        activity: Activity = module.activity
        project: Project = activity.project

        self.get_defaults()

        if module.is_luc_remaining_same():
            self.inputs_start_w = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_w,
            }

            self.math_start_w = MathNotCultivatedLand(**self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if module.is_business_as_usual():
            self.inputs_start_wo = {
                "hectares_start": self.area,
                "hectares_end": 0,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_wo,
            }

            self.math_start_wo = MathNotCultivatedLand(**self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module.is_with():
            self.inputs_w = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_w.value,
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_w,
            }

            self.math_w = MathNotCultivatedLand(**self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            self.inputs_wo = {
                "hectares_start": 0,
                "hectares_end": self.area,
                "implementation_time": self.activity.implementation_years,
                "capitalization_time": self.activity.capitalization_years,
                "rate_type": activity.change_rate.name,
                "nitrous_constant": project.gw_potential.n2o,
                "ef_nitrous_som": self.som.value,
                "soc_start_default": self.soc.value,
                "soc_end_default": self.soc.value,
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
                "biomass_start_default": self.biomass_ef_start.value,
                "biomass_end_default": self.biomass_ef_wo.value,
                "biomass_start_tier_2": module.biomass_t2_start,
                "biomass_end_tier_2": module.biomass_t2_wo,
            }

            self.math_wo = MathNotCultivatedLand(**self.inputs_wo)
            self.math_wo.calculate_emissions()

        self.results_start_w = self.math_start_w.result if self.math_start_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_w = self.math_w.result if self.math_w else MathResult(self.activity.implementation_years, self.activity.capitalization_years)
        self.results_wo = self.math_wo.result if self.math_wo else MathResult(self.activity.implementation_years, self.activity.capitalization_years)

        results_tuple = (self.results_w + self.results_start_w, self.results_wo + self.results_start_wo)

        return results_tuple
