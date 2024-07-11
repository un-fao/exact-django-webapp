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
    ElectryicityConsumption,
    FuelConsumption,
    NewIrrigation,
    OperationPhaseIrrigation,
    SolidConsumption,
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
from math_model.no_time_dependency_final.not_cultivated_land import NotCultivatedLand

from api.utilities import getattr_or_default

from . import utilities as utils
from .models import (
    Activity,
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
    attr = getattr(module, f"organic_input_type_{scenario.value}", None)

    try:
        if attr:
            return ipcc.FIData.objects.get(climate=climate, moisture=moisture, organic_input_type=attr)
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
    attr = getattr(module, f"tillage_management_type_{scenario.value}", None)

    try:
        if attr:
            return ipcc.FMGData.objects.get(climate=climate, moisture=moisture, tillage_management_type=attr)
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
    attr = getattr(module, f"land_use_type_{scenario.value}", None)

    try:
        if attr:
            return ipcc.FLUData.objects.get(climate=climate, moisture=moisture, land_use_type=attr)
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
        self.Meta.model = input.__class__
        self.data = input
        self.inputs_start_w = None
        self.inputs_start_wo = None
        self.inputs_start = None
        self.inputs_w = None
        self.inputs_wo = None
        super().__init__()

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
        raise NotImplementedError(f"get_defaults() method must be implemented for {self.__class__.__name__}.")


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

        module_start = getattr(luc.activity, luc.module_type_start.class_name.lower(), None)
        module_w = getattr(luc.activity, luc.module_type_w.class_name.lower(), None)
        module_wo = getattr(luc.activity, luc.module_type_wo.class_name.lower(), None)

        if not module_start or not module_w or not module_wo:
            missing_modules = ["Start" if not module_start else "With" if not module_w else "Without" for module in [module_start, module_w, module_wo] if not module].join(", ")
            raise Exception(f"LandUseChange module must have a start with and without module. Missing {missing_modules} module(s).")

        module_start = module_start.get(land_use_change=luc)
        module_w = module_w.get(land_use_change=luc)
        module_wo = module_wo.get(land_use_change=luc)

        # TODO: DeforestationCalculator now expects the ForestManagement module only. Refactor the calculator accordingly (check T2 values!)
        # results_start = CalculatorFactory().calculate_result(module_start, aggregate_by=aggregate_by)
        results_w, results_wo = self.luc_based_calculation(module_start, module_w, aggregate_by=aggregate_by)

        return (results_w, results_wo)

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
        module_wo: LandModule = getattr(luc.activity, luc.module_type_wo.class_name.lower(), None).first()
        module_w: LandModule = getattr(luc.activity, luc.module_type_w.class_name.lower(), None).first()

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

        try:
            total_biomass_w = ipcc.TotalBiomassAfterDefo.objects.get_or_default(**cmc, land_use_type=module.land_use_type_w)
        except ipcc.TotalBiomassAfterDefo.DoesNotExist:
            raise Exception(f"TotalBiomassAfterDefo for {module.land_use_type_w.name} in {climate.name} climate, {moisture.name} moisture, and {region.name} region does not exist")

        try:
            total_biomass_wo = ipcc.TotalBiomassAfterDefo.objects.get_or_default(**cmc, land_use_type=module.land_use_type_wo)
        except ipcc.TotalBiomassAfterDefo.DoesNotExist:
            raise Exception(f"TotalBiomassAfterDefo for {module.land_use_type_wo.name} in {climate.name} climate, {moisture.name} moisture, and {region.name} region does not exist")

        # NOTE: Maybe merge the mangroves and deforestation IPCC tables into one table?
        # TODO: Review with new forest management data
        if forest.land_use_type_start.name != utils.MANGROVES:

            try:
                litter_dw_w = ipcc.LitterDeadwoodCarbonStock.objects.get(land_use_type=module.land_use_type_w, climate=climate, forest_type=forest.forest_type)
            except ipcc.LitterDeadwoodCarbonStock.DoesNotExist:
                raise Exception(f"LitterDeadwoodCarbonStock for {module.land_use_type_w.name} in {climate.name} climate, {forest.forest_type.name} forest type does not exist")
            try:
                litter_dw_wo = ipcc.LitterDeadwoodCarbonStock.objects.get(land_use_type=module.land_use_type_wo, climate=climate, forest_type=forest.forest_type)
            except ipcc.LitterDeadwoodCarbonStock.DoesNotExist:
                raise Exception(f"LitterDeadwoodCarbonStock for {module.land_use_type_wo.name} in {climate.name} climate, {forest.forest_type.name} forest type does not exist")

            agb_start = ipcc.ForestManagementAGB.objects.filter(climate=climate, region=region, forest_type=forest.forest_type, land_use_type=forest.land_use_type_start, forest_condition_type__name="Secondary >20 Years").first()
            agb_w = 0
            agb_wo = 0

            try:
                agb_w = ipcc.ForestManagementAGB.objects.get(climate=climate, region=region, forest_type=forest.forest_type, land_use_type=forest.land_use_type_w, forest_condition_type__name="Secondary >20 Years")
            except ipcc.ForestManagementAGB.DoesNotExist:
                raise Exception(f"ForestManagementAGB for {forest.land_use_type_w.name} in {climate.name} climate, {region.name} region, {forest.forest_type.name} forest type, and Secondary >20 Years forest condition type does not exist")
            try:
                agb_wo = ipcc.ForestManagementAGB.objects.get(climate=climate, region=region, forest_type=forest.forest_type, land_use_type=forest.land_use_type_wo, forest_condition_type__name="Secondary >20 Years")
            except ipcc.ForestManagementAGB.DoesNotExist:
                raise Exception(f"ForestManagementAGB for {forest.land_use_type_wo.name} in {climate.name} climate, {region.name} region, {forest.forest_type.name} forest type, and Secondary >20 Years forest condition type does not exist")

            bgb_start = ipcc.ForestManagementBGB.objects.get_first_above_threshold(region=region, land_use_type=module.land_use_type_start, threshold=statistics.mean([agb_start.agb_min, agb_start.agb_max]), climate=climate, forest_type=forest.forest_type)
            if not bgb_start:
                raise Exception(f"ForestManagementBGB for {module.land_use_type_start.name} in {climate.name} climate, {region.name} region, and {forest.forest_type.name} forest type does not exist")

            bgb_w = ipcc.ForestManagementBGB.objects.get_first_above_threshold(region=region, land_use_type=module.land_use_type_start, threshold=statistics.mean([agb_w.agb_min, agb_w.agb_max]), climate=climate, forest_type=forest.forest_type)
            if not bgb_w:
                raise Exception(f"ForestManagementBGB for {module.land_use_type_w.name} in {climate.name} climate, {region.name} region, and {forest.forest_type.name} forest type does not exist")

            bgb_wo = ipcc.ForestManagementBGB.objects.get_first_above_threshold(region=region, land_use_type=module.land_use_type_w, threshold=statistics.mean([agb_wo.agb_min, agb_wo.agb_max]), climate=climate, forest_type=forest.forest_type)
            if not bgb_wo:
                raise Exception(f"ForestManagementBGB for {module.land_use_type_wo.name} in {climate.name} climate, {region.name} region, and {forest.forest_type.name} forest type does not exist")
        else:
            mangroves_data = ipcc.DataOnMangrove.objects.get(continent=region)

        combustion_factor_w = ipcc.ForestCombustionFactor.objects.get(land_use_type=module.land_use_type_w, climate=climate, forest_type=forest.forest_type)
        combustion_factor_wo = ipcc.ForestCombustionFactor.objects.get(land_use_type=module.land_use_type_wo, climate=climate, forest_type=forest.forest_type)

        moisture_factor = ipcc.NitrousEmissionFactor.objects.filter(moisture=moisture)
        moisture_factor = moisture_factor.filter(Q(organic_input_type__name__icontains="Other N Inputs") | Q(organic_input_type__name__icontains="All N Inputs")).first()

        flu_start = ipcc.LandUseCarbonStockExchangeFactor.objects.get_or_default(climate=climate, moisture=moisture, land_use_type=module.land_use_type_start)
        flu_w = ipcc.LandUseCarbonStockExchangeFactor.objects.get_or_default(climate=climate, moisture=moisture, land_use_type=module.land_use_type_w)
        flu_wo = ipcc.LandUseCarbonStockExchangeFactor.objects.get_or_default(climate=climate, moisture=moisture, land_use_type=module.land_use_type_wo)

        # BUG: Values for scenarios should be taken from the respective modules
        fi_start = SimpleNamespace(value=1)
        fi_w = SimpleNamespace(value=1)
        fi_wo = SimpleNamespace(value=1)

        fmg_start = SimpleNamespace(value=1)
        fmg_w = SimpleNamespace(value=1)
        fmg_wo = SimpleNamespace(value=1)

        soc_w = soc_ref
        soc_wo = soc_ref

        if luc.module_type_w.name == "Grassland":
            soc_w = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module_w.grassland_management_type_start,
                climate=project.climate,
            )
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
                project.implementation_years,
                project.capitalization_years,
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
                DELAY_W,
            ]

            math_w = MathDeforestation(*self.inputs_w)
            math_w.calculate_emissions()

        if not module.is_business_as_usual():
            self.inputs_wo = [
                0,
                luc.area,
                project.implementation_years,
                project.capitalization_years,
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
                DELAY_WO,
            ]

            math_wo = MathDeforestation(*self.inputs_wo)
            math_wo.calculate_emissions()

        res_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        res_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

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

        input: BiomassModule | LandModule = self.data
        luc: LandUseChange = input.land_use_change
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

        module_start: BiomassModule | LandModule = getattr(input.activity, luc.module_type_start.class_name.lower(), None).first()
        module_w: BiomassModule | LandModule = getattr(input.activity, luc.module_type_w.class_name.lower(), None).first()
        module_wo: BiomassModule | LandModule = getattr(input.activity, luc.module_type_wo.class_name.lower(), None).first()

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
            luc_start = LandUseType.objects.get(name=luc.module_type_start.name)
        except LandUseType.DoesNotExist:
            raise Exception(f"LandUseType for {luc.module_type_start.name} does not exist")

        try:
            luc_w = LandUseType.objects.get(name=luc.module_type_w.name)
        except LandUseType.DoesNotExist:
            raise Exception(f"LandUseType for {luc.module_type_w.name} does not exist")

        try:
            luc_wo = LandUseType.objects.get(name=luc.module_type_wo.name)
        except LandUseType.DoesNotExist:
            raise Exception(f"LandUseType for {luc.module_type_wo.name} does not exist")

        try:
            biomass_initial = ipcc.ForestTotalBiomass.objects.get_or_default(**cmc, land_use_type=luc_start)
        except ipcc.ForestTotalBiomass.DoesNotExist:
            raise Exception(f"ForestTotalBiomass for {luc_start.name} in {climate.name} climate, {moisture.name} moisture, and {continent.name} continent does not exist")

        try:
            biomass_final_w = ipcc.TotalBiomassAfterDefo.objects.get_or_default(**cmc, land_use_type=luc_w)
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
            som = ipcc.LandUseNitrousEmissionFactor.objects.get(moisture=moisture)
        except ipcc.LandUseNitrousEmissionFactor.DoesNotExist:
            raise Exception(f"LandUseNitrousEmissionFactor for {moisture.name} moisture does not exist")

        try:
            combustion_factor_w = ipcc.AfforestationCombustionFactor.objects.get_or_default(land_use_type=luc_w)
        except ipcc.AfforestationCombustionFactor.DoesNotExist:
            raise Exception(f"AfforestationCombustionFactor for {luc_w.name} does not exist")

        try:
            combustion_factor_wo = ipcc.AfforestationCombustionFactor.objects.get_or_default(land_use_type=luc_wo)
        except ipcc.AfforestationCombustionFactor.DoesNotExist:
            raise Exception(f"AfforestationCombustionFactor for {luc_wo.name} does not exist")

        DELAY_W = 0
        DELAY_WO = 0

        inputs_w = [
            biomass_initial.value,
            module_start.get_biomass_t2(utils.ScenarioTypes.START),
            biomass_final_w.value,
            module_w.get_biomass_t2(utils.ScenarioTypes.WITH),
            c_n_ratio,
            som.value,
            combustion_factor_w.value,
            combustion_factor_w.n2o,
            combustion_factor_w.ch4,
            input.activity.project.gw_potential.n2o,
            input.activity.project.gw_potential.ch4,
            luc.is_fire_used_w,
            soc.value,
            soc.value,
            module_start.soc_t2_start,
            module_w.soc_t2_w,
            soc_start.fmg if soc_start else fmg_start.value,
            fmg_final_w.value,
            module_start.fmg_t2_start,  # TODO: Start module has 3 fmg values. What to choose?
            module_w.fmg_t2_w,
            soc_start.flu if soc_start else flu_start.value,
            flu_final_w.value,
            module_start.flu_t2_start,
            module_w.flu_t2_w,
            soc_start.fi if soc_start else fi_start.value,
            fi_final_w.value,
            module_start.fi_t2_start,
            module_w.fi_t2_w,
            CALCULATE_SOC_SOM_W,
            luc.area,
            project.implementation_years,
            project.capitalization_years,
            input.activity.change_rate.name,
            DELAY_W,
        ]

        results_w = MathOtherLandUseChanges(*inputs_w)
        results_w.calculate_emissions()

        inputs_wo = [
            biomass_initial.value,
            module_start.get_biomass_t2(utils.ScenarioTypes.START),
            biomass_final_wo.value,
            module_wo.get_biomass_t2(utils.ScenarioTypes.WITHOUT),
            c_n_ratio,
            som.value,
            combustion_factor_wo.value,
            combustion_factor_wo.ch4,
            combustion_factor_wo.n2o,
            input.activity.project.gw_potential.ch4,
            input.activity.project.gw_potential.n2o,
            luc.is_fire_used_wo,
            soc.value,
            soc.value,
            module_start.soc_t2_start,
            module_wo.soc_t2_wo,
            fmg_start.value,
            fmg_final_wo.value,
            module_start.fmg_t2_start,  # TODO: Start module has 3 fmg (also fi and flu) values. What to choose?
            module_wo.fmg_t2_wo,
            flu_start.value,
            flu_final_wo.value,
            module_start.flu_t2_start,
            module_wo.flu_t2_wo,
            fi_start.value,
            fi_final_wo.value,
            module_start.fi_t2_start,
            module_wo.fi_t2_wo,
            CALCULATE_SOC_SOM_WO,
            luc.area,
            project.implementation_years,
            project.capitalization_years,
            input.activity.change_rate.name,
            DELAY_WO,
        ]

        results_wo = MathOtherLandUseChanges(*inputs_wo)
        results_wo.calculate_emissions()

        res_w = results_w.result if results_w else MathResult(project.implementation_years, project.capitalization_years)
        res_wo = results_wo.result if results_wo else MathResult(project.implementation_years, project.capitalization_years)

        return (res_w, res_wo)

    def defaults(self) -> DefaultData:
        pass


class AnnualCroppingCalculator(BaseCalculator):

    def get_defaults(self, input: Module) -> dict:
        return AnnualCropCalculator(input).get_defaults()

    def calculate(self):
        module: AnnualCropping = self.data

        res_w = MathResult(module.activity.project.implementation_years, module.activity.project.capitalization_years)
        res_wo = MathResult(module.activity.project.implementation_years, module.activity.project.capitalization_years)

        r_w, r_wo = AnnualCropCalculator(module).calculate()

        res_w += r_w
        res_wo += r_wo

        return (res_w, res_wo)


class AnnualCropCalculator(BaseCalculator):
    """
    Calculator for annual cropping modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.fi_start: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=0)
        self.fmg_start: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=0)
        self.flu_start: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=0)
        self.fi_w: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=0)
        self.fmg_w: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=0)
        self.flu_w: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=0)
        self.fi_wo: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=0)
        self.fmg_wo: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=0)
        self.flu_wo: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=0)
        self.biomass_start: SimpleNamespace = SimpleNamespace(value=0)
        self.biomass_w: SimpleNamespace = SimpleNamespace(value=0)
        self.biomass_wo: SimpleNamespace = SimpleNamespace(value=0)
        self.crop_yield_start: SimpleNamespace | ipcc.CropYieldStats = SimpleNamespace(value=0)
        self.crop_yield_w: SimpleNamespace | ipcc.CropYieldStats = SimpleNamespace(value=0)
        self.crop_yield_wo: SimpleNamespace | ipcc.CropYieldStats = SimpleNamespace(value=0)
        self.soc: SimpleNamespace | ipcc.SoilOrganicCarbon = SimpleNamespace(value=0)
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

        self.math_start_w = None
        self.math_start_wo = None
        self.math_w = None
        self.math_wo = None

    def get_defaults(self, calculate=False) -> SimpleNamespace:
        input: AnnualCropping = self.data
        activity: Activity = getattr(input, "parent", input).activity
        project: Project = activity.project
        module_start = module_w = module_wo = input
        luc: LandUseChange = input.land_use_change

        if luc:
            module_start, module_w, module_wo = luc.get_modules()

        if input.status.name == "READY" and calculate:
            self.calculate()

            self.biomass_start = SimpleNamespace(value=getattr_or_default(self.math_start_w, "ag_residue_main_tier_2_default") or getattr_or_default(self.math_start_wo, "ag_residue_main_tier_2_default"))
            self.biomass_w = SimpleNamespace(value=getattr_or_default(self.math_w, "ag_residue_main_tier_2_default") or getattr_or_default(self.math_wo, "ag_residue_main_tier_2_default"))
            self.biomass_wo = SimpleNamespace(value=getattr_or_default(self.math_wo, "ag_residue_main_tier_2_default") or getattr_or_default(self.math_wo, "ag_residue_main_tier_2_default"))
            self.minor_biomass_start = SimpleNamespace(value=getattr_or_default(self.math_start_w, "ag_residue_minor_tier_2_default") or getattr_or_default(self.math_start_wo, "ag_residue_minor_tier_2_default"))
            self.minor_biomass_w = SimpleNamespace(value=getattr_or_default(self.math_w, "ag_residue_minor_tier_2_default") or getattr_or_default(self.math_wo, "ag_residue_minor_tier_2_default"))
            self.minor_biomass_wo = SimpleNamespace(value=getattr_or_default(self.math_wo, "ag_residue_minor_tier_2_default") or getattr_or_default(self.math_wo, "ag_residue_minor_tier_2_default"))

        climate = project.climate
        moisture = project.moisture
        soil_type = project.soil_type

        cm = {"climate": climate, "moisture": moisture}
        region_flt = {"continent": project.country.region}
        soil_flt = {"soil_type": soil_type}
        moisture_flt = {"moisture": moisture}
        lut_start_flt = {"land_use_type": module_start.land_use_type_start}
        lut_w_flt = {"land_use_type": module_w.land_use_type_w}
        lut_wo_flt = {"land_use_type": module_wo.land_use_type_wo}

        agricultural_residues_flt = {"category__name": "Agricultural residues"}
        long_term_cultivated_flt = {"land_use_type__name__icontains": "Long-Term Cultivated"}

        self.fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        self.fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        self.flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        self.fi_w = get_fi_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        self.fmg_w = get_fmg_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        self.flu_w = get_flu_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        self.fi_wo = get_fi_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
        self.fmg_wo = get_fmg_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
        self.flu_wo = get_flu_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)

        self.soc = utils.get_or_raise(ipcc.SoilOrganicCarbon, cm | soil_flt, f"SoilOrganicCarbon for {soil_type.name} soil type in {climate.name} climate and {moisture.name} moisture does not exist")
        self.burning_emission_factor = utils.get_or_raise(ipcc.BurningEmissionFactor, agricultural_residues_flt, "BurningEmissionFactor for Agricultural residues does not exist")

        if input.minor_land_use_type_start or input.minor_land_use_type_w or input.minor_land_use_type_wo:
            self.minor_burning_emission_factor = utils.get_or_raise(ipcc.BurningEmissionFactor, agricultural_residues_flt, "BurningEmissionFactor for Agricultural residues for minor crop does not exist")

        if input.is_luc_remaining_same():

            lut_start = input.land_use_type_start
            minor_lut_start = input.minor_land_use_type_start
            organic_input_flt_start = {"organic_input_type": input.organic_input_type_start}

            self.flu = utils.get_or_raise(ipcc.CroplandFLU, cm | long_term_cultivated_flt, f"CroplandFLU for {lut_start.name} in {climate.name} climate and {moisture.name} moisture does not exist")
            self.fires_start = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_start_flt, f"FiresCombustionFactor for {lut_start.name} does not exist")
            self.n_estimation_factor_start = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_start_flt, f"CropNitrousEstimationDefaultFactor for {lut_start.name} does not exist", method="get_or_grains")
            self.emission_factors_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.crop_yield_start = input.crop_yield_start or utils.get_or_raise(ipcc.CropYieldStats, region_flt | lut_start_flt, f"CropYieldStats for {module_start.land_use_type_start.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_region_average").average

            try:
                self.minor_fires_start = ipcc.FiresCombustionFactor.objects.get(land_use_type=minor_lut_start)
                self.minor_n_estimation_factor_start = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_start)
            except Exception:
                self.minor_fires_start = None
                self.minor_n_estimation_factor_start = None

        if input.is_with():
            lut_w = input.land_use_type_w
            minor_lut_w = input.minor_land_use_type_w

            self.flu = utils.get_or_raise(ipcc.CroplandFLU, cm | long_term_cultivated_flt, f"CroplandFLU for {lut_w.name} in {climate.name} climate and {moisture.name} moisture does not exist")
            self.fires_w = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_w_flt, f"FiresCombustionFactor for {lut_w.name} does not exist")
            self.n_estimation_factor_w = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_w_flt, f"CropNitrousEstimationDefaultFactor for {lut_w.name} does not exist", method="get_or_grains")
            self.emission_factors_w = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.crop_yield_w = input.crop_yield_w or utils.get_or_raise(ipcc.CropYieldStats, region_flt | lut_w_flt, f"CropYieldStats for {module_w.land_use_type_w.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_region_average").average

            try:
                self.minor_fires_w = ipcc.FiresCombustionFactor.objects.get(land_use_type=lut_w)
                self.minor_n_estimation_factor_w = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_w)
            except Exception:
                self.minor_fires_w = None
                self.minor_n_estimation_factor_w = None

        if input.is_business_as_usual():
            lut_start = input.land_use_type_start
            minor_lut_start = input.minor_land_use_type_start

            self.flu = utils.get_or_raise(ipcc.CroplandFLU, cm | long_term_cultivated_flt, f"CroplandFLU for {lut_start.name} in {climate.name} climate and {moisture.name} moisture does not exist")
            self.fires_start = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_start_flt, f"FiresCombustionFactor for {lut_start.name} does not exist")
            self.n_estimation_factor_start = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_start_flt, f"CropNitrousEstimationDefaultFactor for {lut_start.name} does not exist", method="get_or_grains")
            self.emission_factors_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.crop_yield_start = input.crop_yield_start or utils.get_or_raise(ipcc.CropYieldStats, region_flt | lut_start_flt, f"CropYieldStats for {module_start.land_use_type_start.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_region_average").average

            try:
                self.minor_fires_start = ipcc.FiresCombustionFactor.objects.get(land_use_type=minor_lut_start)
                self.minor_n_estimation_factor_start = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_start)
            except Exception:
                self.minor_fires_start = None
                self.minor_n_estimation_factor_start = None

        if input.is_without():
            lut_wo = input.land_use_type_wo
            minor_lut_wo = input.minor_land_use_type_wo

            self.flu = utils.get_or_raise(ipcc.CroplandFLU, cm | long_term_cultivated_flt, f"CroplandFLU for {lut_wo.name} in {climate.name} climate and {moisture.name} moisture does not exist")
            self.fires_wo = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_wo_flt, f"FiresCombustionFactor for {lut_wo.name} does not exist")
            self.n_estimation_factor_wo = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_wo_flt, f"CropNitrousEstimationDefaultFactor for {lut_wo.name} does not exist", method="get_or_grains")
            self.emission_factors_wo = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.crop_yield_wo = input.crop_yield_wo or utils.get_or_raise(ipcc.CropYieldStats, region_flt | lut_wo_flt, f"CropYieldStats for {module_wo.land_use_type_wo.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_region_average").average

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
        module_start = module_w = module_wo = input
        luc: LandUseChange = input.land_use_change

        if luc:
            module_start, module_w, module_wo = luc.get_modules()

        area = luc.area if luc else input.area
        change_rate = input.activity.change_rate

        self.get_defaults()

        if input.is_luc_remaining_same():
            log.debug("Is LUC remaining the same")

            self.inputs_start_w = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                change_rate.value,
                self.soc.value,
                self.soc.value,
                input.soc_t2_start,
                input.soc_t2_w,
                self.fmg_start.value,
                self.fmg_w.value,
                module_start.fmg_t2_start,
                input.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module_start.flu_t2_start,
                input.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module_start.fi_t2_start,
                input.fi_t2_w,
                CALCULATE_SOC_SOM_START_W,
                self.som_start.value,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                self.burning_emission_factor.ch4 if input.residue_management_type_start.name == "Burned" else None,
                self.fires_start.value,
                input.biomass_t2_start,
                self.n_estimation_factor_start.slope,
                self.n_estimation_factor_start.intercept,
                self.crop_yield_start,
                getattr(self.minor_burning_emission_factor, "ch4", None),
                getattr(self.minor_fires_start, "value", None),
                input.minor_biomass_factor_t2_start,
                getattr(self.minor_n_estimation_factor_start, "slope", None),
                getattr(self.minor_n_estimation_factor_start, "intercept", None),
                input.minor_yield_start,
                self.burning_emission_factor.n2o if input.residue_management_type_start.name == "Burned" else None,
                input.residue_management_type_start.name == "Retained",
                getattr(self.minor_burning_emission_factor, "n2o", None),
                getattr(input.minor_residue_management_type_start, "name", None) == "Retained",
                self.n_estimation_factor_start.n_ag_residues,
                self.n_estimation_factor_start.rs_t,
                self.n_estimation_factor_start.n_bg_t,
                getattr(self.minor_n_estimation_factor_start, "n_ag_residues", None),
                getattr(self.minor_n_estimation_factor_start, "rs_t", None),
                getattr(self.minor_n_estimation_factor_start, "n_bg_t", None),
                DELAY_START_W,
            ]
            log.debug("Inputs start w: %s", self.inputs_start_w)

            self.math_start_w = AnnualCropland(*self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if input.is_with():
            log.debug("Is with")

            self.inputs_w = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                change_rate.value,
                self.soc.value,
                self.soc.value,
                input.soc_t2_start,
                input.soc_t2_w,
                self.fmg_start.value,
                self.fmg_w.value,
                module_w.fmg_t2_start,
                input.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module_w.flu_t2_start,
                input.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module_w.fi_t2_start,
                input.fi_t2_w,
                CALCULATE_SOC_SOM_W,
                self.som_w.value,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                self.burning_emission_factor.ch4 if input.residue_management_type_w.name == "Burned" else None,
                self.fires_w.value,
                input.biomass_t2_w,
                self.n_estimation_factor_w.slope,
                self.n_estimation_factor_w.intercept,
                self.crop_yield_w,
                getattr(self.minor_burning_emission_factor, "ch4", None),
                getattr(self.minor_fires_w, "value", None),
                input.minor_biomass_factor_t2_w,
                getattr(self.minor_n_estimation_factor_w, "slope", None),
                getattr(self.minor_n_estimation_factor_w, "intercept", None),
                input.minor_yield_w,
                self.burning_emission_factor.n2o if input.residue_management_type_w.name == "Burned" else None,
                input.residue_management_type_w.name == "Retained",
                getattr(self.minor_burning_emission_factor, "n2o", None),
                getattr(input.minor_residue_management_type_w, "name", None) == "Retained",
                self.n_estimation_factor_w.n_ag_residues,
                self.n_estimation_factor_w.rs_t,
                self.n_estimation_factor_w.n_bg_t,
                getattr(self.minor_n_estimation_factor_w, "n_ag_residues", None),
                getattr(self.minor_n_estimation_factor_w, "rs_t", None),
                getattr(self.minor_n_estimation_factor_w, "n_bg_t", None),
                DELAY_W,
            ]
            log.debug("Inputs w: %s", self.inputs_w)

            self.math_w = AnnualCropland(*self.inputs_w)
            self.math_w.calculate_emissions()

        if input.is_business_as_usual():
            log.debug("Is business as usual")

            self.inputs_start_wo = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                change_rate.value,
                self.soc.value,
                self.soc.value,
                input.soc_t2_start,
                input.soc_t2_wo,
                self.fmg_start.value,
                self.fmg_wo.value,
                input.fmg_t2_start,
                input.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                input.flu_t2_start,
                input.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                input.fi_t2_start,
                input.fi_t2_wo,
                CALCULATE_SOC_SOM_START_WO,
                self.som_start.value,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                self.burning_emission_factor.ch4 if input.residue_management_type_start.name == "Burned" else None,
                self.fires_start.value,
                input.biomass_t2_start,
                self.n_estimation_factor_start.slope,
                self.n_estimation_factor_start.intercept,
                self.crop_yield_start,
                getattr(self.minor_burning_emission_factor, "ch4", None),
                getattr(self.minor_fires_start, "value", None),
                input.minor_biomass_factor_t2_start,
                getattr(self.minor_n_estimation_factor_start, "slope", None),
                getattr(self.minor_n_estimation_factor_start, "intercept", None),
                input.minor_yield_start,
                self.burning_emission_factor.n2o if input.residue_management_type_start.name == "Burned" else None,
                input.residue_management_type_start.name == "Retained",
                getattr(self.minor_burning_emission_factor, "n2o", None),
                getattr(input.minor_residue_management_type_start, "name", None) == "Retained",
                self.n_estimation_factor_start.n_ag_residues,
                self.n_estimation_factor_start.rs_t,
                self.n_estimation_factor_start.n_bg_t,
                getattr(self.minor_n_estimation_factor_start, "n_ag_residues", None),
                getattr(self.minor_n_estimation_factor_start, "rs_t", None),
                getattr(self.minor_n_estimation_factor_start, "n_bg_t", None),
                DELAY_START_WO,
            ]
            log.debug("Inputs start wo: %s", self.inputs_start_wo)

            self.math_start_wo = AnnualCropland(*self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if input.is_without():
            log.debug("Is without")

            self.inputs_wo = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                change_rate.value,
                self.soc.value,
                self.soc.value,
                input.soc_t2_start,
                input.soc_t2_wo,
                self.fmg_start.value,
                self.fmg_wo.value,
                module_wo.fmg_t2_start,
                input.fmg_t2_wo,
                self.flu.value,
                self.flu.value,
                module_wo.flu_t2_start,
                input.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module_wo.fi_t2_start,
                input.fi_t2_wo,
                CALCULATE_SOC_SOM_WO,
                self.som_wo.value,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                self.burning_emission_factor.ch4 if input.residue_management_type_wo.name == "Burned" else None,
                self.fires_wo.value,
                input.biomass_t2_wo,
                self.n_estimation_factor_wo.slope,
                self.n_estimation_factor_wo.intercept,
                self.crop_yield_wo,
                getattr(self.minor_burning_emission_factor, "ch4", None),
                getattr(self.minor_fires_wo, "value", None),
                input.minor_biomass_factor_t2_wo,
                getattr(self.minor_n_estimation_factor_wo, "slope", None),
                getattr(self.minor_n_estimation_factor_wo, "intercept", None),
                input.minor_yield_wo,
                self.burning_emission_factor.n2o if input.residue_management_type_wo.name == "Burned" else None,
                input.residue_management_type_wo.name == "Retained",
                getattr(self.minor_burning_emission_factor, "n2o", None),
                getattr(input.minor_residue_management_type_wo, "name", None) == "Retained",
                self.n_estimation_factor_wo.n_ag_residues,
                self.n_estimation_factor_wo.rs_t,
                self.n_estimation_factor_wo.n_bg_t,
                getattr(self.minor_n_estimation_factor_wo, "n_ag_residues", None),
                getattr(self.minor_n_estimation_factor_wo, "rs_t", None),
                getattr(self.minor_n_estimation_factor_wo, "n_bg_t", None),
                DELAY_WO,
            ]
            log.debug("Inputs wo: %s", self.inputs_wo)

            self.math_wo = AnnualCropland(*self.inputs_wo)
            self.math_wo.calculate_emissions()

        res_start_w = self.math_start_w.result if self.math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        res_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        res_w = self.math_w.result if self.math_w else MathResult(project.implementation_years, project.capitalization_years)
        res_wo = self.math_wo.result if self.math_wo else MathResult(project.implementation_years, project.capitalization_years)

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


class PerennialCropCalculator(BaseCalculator):

    def __init__(self, input) -> None:
        super().__init__(input)

        self.soc: SimpleNamespace | ipcc.SoilOrganicCarbon = SimpleNamespace(value=0)
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
        self.flu_start: ipcc.FLUData | SimpleNamespace = SimpleNamespace(value=0)
        self.flu_w: ipcc.FLUData | SimpleNamespace = SimpleNamespace(value=0)
        self.flu_wo: ipcc.FLUData | SimpleNamespace = SimpleNamespace(value=0)
        self.fi_start: ipcc.FIData | SimpleNamespace = SimpleNamespace(value=0)
        self.fi_w: ipcc.FIData | SimpleNamespace = SimpleNamespace(value=0)
        self.fi_wo: ipcc.FIData | SimpleNamespace = SimpleNamespace(value=0)
        self.fmg_start: ipcc.FMGData | SimpleNamespace = SimpleNamespace(value=0)
        self.fmg_w: ipcc.FMGData | SimpleNamespace = SimpleNamespace(value=0)
        self.fmg_wo: ipcc.FMGData | SimpleNamespace = SimpleNamespace(value=0)
        self.default_fire_periodicity: AnnualCroplandParameter | SimpleNamespace = SimpleNamespace(value=0)

        # Calculated by math model
        self.residue_burned_t2_start: SimpleNamespace = SimpleNamespace(value=0)
        self.residue_burned_t2_w: SimpleNamespace = SimpleNamespace(value=0)
        self.residue_burned_t2_wo: SimpleNamespace = SimpleNamespace(value=0)

        self.math_start_w = None
        self.math_start_wo = None
        self.math_w = None
        self.math_wo = None

    def get_defaults(self, calculate=False) -> dict:

        module: PerennialCropping = self.data
        project = module.activity.project
        activity: Activity = module.activity
        climate = activity.climate_t2 or project.climate
        moisture = activity.moisture_t2 or project.moisture
        region = project.country.region

        soil_flt = {"soil_type": project.soil_type}
        savanna_flt = {"category__name": "Savanna and grassland"}
        organic_input_flt_start = {"organic_input_type": module.organic_input_type_start}
        organic_input_flt_w = {"organic_input_type": module.organic_input_type_w}
        organic_input_flt_wo = {"organic_input_type": module.organic_input_type_wo}
        moisture_flt = {"moisture": moisture}
        climate_flt = {"climate": climate}

        lut_start_flt = {"land_use_type": module.land_use_type_start}
        lut_w_flt = {"land_use_type": module.land_use_type_w}
        lut_wo_flt = {"land_use_type": module.land_use_type_wo}

        cm = {
            "climate": climate,
            "moisture": moisture,
        }

        cmc = {
            "climate": climate,
            "moisture": moisture,
            "continent": region,
        }

        if module.status.name == "READY" and calculate:
            self.calculate()

            self.residue_burned_t2_start = SimpleNamespace(value=getattr(self.math_start_w, "t_biomass_tier_2_default", 0) or getattr(self.math_start_wo, "t_biomass_tier_2_default", 0))
            self.residue_burned_t2_w = SimpleNamespace(value=getattr(self.math_w, "t_biomass_tier_2_default", 0) or getattr(self.math_wo, "t_biomass_tier_2_default", 0))
            self.residue_burned_t2_wo = SimpleNamespace(value=getattr(self.math_w, "t_biomass_tier_2_default", 0) or getattr(self.math_wo, "t_biomass_tier_2_default", 0))

        self.soc = utils.get_or_raise(ipcc.SoilOrganicCarbon, cm | soil_flt, f"SoilOrganicCarbon for {project.soil_type.name} soil type in {climate.name} climate and {moisture.name} moisture does not exist")
        self.burning_emission_factor = utils.get_or_raise(ipcc.BurningEmissionFactor, savanna_flt, "BurningEmissionFactor for Savanna and grassland does not exist")
        self.default_fire_periodicity = AnnualCroplandParameter.objects.get(name="default_fire_periodicity")

        if module.is_luc_remaining_same():
            self.flu_start = get_flu_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.fi_start = get_fi_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.fmg_start = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.default_emission_factor_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.fires_combustion_factor_start = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_start_flt, f"FiresCombustionFactor for {module.land_use_type_start.name} does not exist", method="get_or_default")
            self.ag_default_start = utils.get_or_raise(ipcc.PerennialAGB, cmc | lut_start_flt, f"PerennialAGB for {module.land_use_type_start.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.agb_max_c_start = utils.get_or_raise(ipcc.PerennialMaxAGB, climate_flt | lut_start_flt, f"PerennialMaxAGB for {module.land_use_type_start.name} in {climate.name} climate does not exist", method="get_or_default")
            self.bg_default_start = utils.get_or_raise(ipcc.PerennialBGB, cmc | lut_start_flt, f"PerennialBGB for {module.land_use_type_start.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")

        if module.is_business_as_usual():
            self.flu_start = get_flu_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.fi_start = get_fi_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.fmg_start = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.default_emission_factor_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.fires_combustion_factor_start = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_start_flt, f"FiresCombustionFactor for {module.land_use_type_start.name} does not exist", method="get_or_default")
            self.ag_default_start = utils.get_or_raise(ipcc.PerennialAGB, cmc | lut_start_flt, f"PerennialAGB for {module.land_use_type_start.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.agb_max_c_start = utils.get_or_raise(ipcc.PerennialMaxAGB, climate_flt | lut_start_flt, f"PerennialMaxAGB for {module.land_use_type_start.name} in {climate.name} climate does not exist", method="get_or_default")
            self.bg_default_start = utils.get_or_raise(ipcc.PerennialBGB, cmc | lut_start_flt, f"PerennialBGB for {module.land_use_type_start.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")

        if module.is_with():
            self.default_emission_factor_w = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.fires_combustion_factor_w = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_w_flt, f"FiresCombustionFactor for {module.land_use_type_w.name} does not exist", method="get_or_default")
            self.ag_default_w = utils.get_or_raise(ipcc.PerennialAGB, cmc | lut_w_flt, f"PerennialAGB for {module.land_use_type_w.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.agb_max_c_w = utils.get_or_raise(ipcc.PerennialMaxAGB, climate_flt | lut_w_flt, f"PerennialMaxAGB for {module.land_use_type_w.name} in {climate.name} climate does not exist", method="get_or_default")
            self.bg_default_w = utils.get_or_raise(ipcc.PerennialBGB, cmc | lut_w_flt, f"PerennialBGB for {module.land_use_type_w.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.flu_w = get_flu_data(module, climate, moisture, utils.ScenarioTypes.WITH)
            self.fi_w = get_fi_data(module, climate, moisture, utils.ScenarioTypes.WITH)
            self.fmg_w = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.WITH)

        if module.is_without():
            self.default_emission_factor_wo = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")
            self.fires_combustion_factor_wo = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_wo_flt, f"FiresCombustionFactor for {module.land_use_type_wo.name} does not exist")
            self.ag_default_wo = utils.get_or_raise(ipcc.PerennialAGB, cmc | lut_wo_flt, f"PerennialAGB for {module.land_use_type_wo.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.agb_max_c_wo = utils.get_or_raise(ipcc.PerennialMaxAGB, climate_flt | lut_wo_flt, f"PerennialMaxAGB for {module.land_use_type_wo.name} in {climate.name} climate does not exist", method="get_or_default")
            self.bg_default_wo = utils.get_or_raise(ipcc.PerennialBGB, cmc | lut_wo_flt, f"PerennialBGB for {module.land_use_type_wo.name} in {climate.name} climate and {moisture.name} moisture does not exist", method="get_or_default")
            self.flu_wo = get_flu_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.fi_wo = get_fi_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.fmg_wo = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)

    def calculate(self, aggregate_by=BreakdownTypes.TOTAL) -> list[Result]:
        """
        Calculate emissions for a single PerennialCropping module.
        """
        log.debug("START PerennialCropCalculator.calculate")

        module: PerennialCropping = self.data
        project = module.activity.project
        activity: Activity = module.activity
        luc: LandUseChange = module.land_use_change
        change_rate = activity.change_rate
        # self.grassland_soc = get_grassland_soc(luc)
        # soc_start = self.grassland_soc.value if self.grassland_soc else self.soc.value
        soc_start = self.soc.value
        soc_w = self.soc.value
        soc_wo = self.soc.value
        area = luc.area if luc else module.area

        self.get_defaults()

        if module.is_luc_remaining_same():
            self.inputs_start_w = [
                area,
                0,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.is_biomass_burned_start,
                self.burning_emission_factor.n2o,
                self.som_start.value,
                self.burning_emission_factor.ch4,
                self.fires_combustion_factor_start.value,
                self.default_fire_periodicity.value,
                module.fire_periodicity_t2_start,
                module.residue_burned_t2_start,
                self.ag_default_start.value,
                module.ag_t2_start,
                self.agb_max_c_start.value,
                self.bg_default_start.value,
                module.bg_t2_start,
                soc_start,
                soc_w,
                module.soc_t2_start,
                module.soc_t2_w,
                self.fmg_start.value,
                self.fmg_w.value,
                module.fmg_t2_start,
                module.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module.flu_t2_start,
                module.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module.fi_t2_start,
                module.fi_t2_w,
                CALCULATE_SOC_SOM_START_W,
                DELAY_START_W,
            ]
            log.debug("Inputs start w: %s", self.inputs_start_w)

            self.math_start_w = PerennialCropland(*self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if module.is_business_as_usual():
            self.input_start_wo = [
                area,
                0,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.is_biomass_burned_start,
                self.burning_emission_factor.n2o,
                self.som_start.value,
                self.burning_emission_factor.ch4,
                self.fires_combustion_factor_start.value,
                self.default_fire_periodicity.value,
                module.fire_periodicity_t2_start,
                module.residue_burned_t2_start,
                self.ag_default_start.value,
                module.ag_t2_start,
                self.agb_max_c_start.value,
                self.bg_default_start.value,
                module.bg_t2_start,
                soc_start,
                soc_wo,
                module.soc_t2_start,
                module.soc_t2_wo,
                self.fmg_start.value,
                self.fmg_wo.value,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                module.flu_t2_start,
                module.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module.fi_t2_start,
                module.fi_t2_wo,
                CALCULATE_SOC_SOM_START_WO,
                DELAY_START_WO,
            ]
            log.debug("Input start wo: %s", self.input_start_wo)

            self.math_start_wo = PerennialCropland(*self.input_start_wo)
            self.math_start_wo.calculate_emissions()

        if module.is_with():
            self.inputs_w = [
                0,
                area,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.is_biomass_burned_w,
                self.burning_emission_factor.n2o,
                self.som_w.value,
                self.burning_emission_factor.ch4,
                self.fires_combustion_factor_w.value,
                self.default_fire_periodicity.value,
                module.fire_periodicity_t2_w,
                module.residue_burned_t2_w,
                self.ag_default_w.value,
                module.ag_t2_w,
                self.agb_max_c_w.value,
                self.bg_default_w.value,
                module.bg_t2_w,
                soc_start,
                soc_w,
                module.soc_t2_start,
                module.soc_t2_w,
                self.fmg_start.value,
                self.fmg_w.value,
                module.fmg_t2_start,
                module.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module.flu_t2_start,
                module.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module.fi_t2_start,
                module.fi_t2_w,
                CALCULATE_SOC_SOM_W,
                DELAY_W,
            ]
            log.debug("Inputs w: %s", self.inputs_w)

            self.math_w = PerennialCropland(*self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            self.inputs_wo = [
                0,
                area,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.is_biomass_burned_wo,
                self.burning_emission_factor.n2o,
                self.som_wo.value,
                self.burning_emission_factor.ch4,
                self.fires_combustion_factor_wo.value,
                self.default_fire_periodicity.value,
                module.fire_periodicity_t2_wo,
                module.residue_burned_t2_wo,
                self.ag_default_wo.value,
                module.ag_t2_wo,
                self.agb_max_c_wo.value,
                self.bg_default_wo.value,
                module.bg_t2_wo,
                soc_start,
                soc_wo,
                module.soc_t2_start,
                module.soc_t2_wo,
                self.fmg_start.value,
                self.fmg_wo.value,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                module.flu_t2_start,
                module.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module.fi_t2_start,
                module.fi_t2_wo,
                CALCULATE_SOC_SOM_WO,
                DELAY_WO,
            ]
            log.debug("Inputs wo: %s", self.inputs_wo)

            self.math_wo = PerennialCropland(*self.inputs_wo)
            self.math_wo.calculate_emissions()

        results_start_w = self.math_start_w.result if self.math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        results_w = self.math_w.result if self.math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = self.math_wo.result if self.math_wo else MathResult(project.implementation_years, project.capitalization_years)

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

        res_w = MathResult(module.activity.project.implementation_years, module.activity.project.capitalization_years)
        res_wo = MathResult(module.activity.project.implementation_years, module.activity.project.capitalization_years)

        r_w, r_wo = PerennialCropCalculator(module).calculate()

        res_w += r_w
        res_wo += r_wo

        log.debug("END PerennialCroppingCalculator.calculate")
        return (res_w, res_wo)


class FloodedRiceSeasonCalculator(BaseCalculator):

    def __init__(self, input) -> None:
        super().__init__(input)

        self.math_start_w = None
        self.math_start_wo = None
        self.math_w = None
        self.math_wo = None

        self.soc: SimpleNamespace | ipcc.SoilOrganicCarbon = SimpleNamespace(value=0)
        self.soc_start: SimpleNamespace | ipcc.SoilOrganicCarbon = SimpleNamespace(value=0)
        self.soc_w: SimpleNamespace | ipcc.SoilOrganicCarbon = SimpleNamespace(value=0)
        self.soc_wo: SimpleNamespace | ipcc.SoilOrganicCarbon = SimpleNamespace(value=0)
        self.efc: SimpleNamespace | ipcc.RiceDefaultEmissionFactor = SimpleNamespace(value=0)
        self.yield_ref: SimpleNamespace | ipcc.RiceYield = SimpleNamespace(value=0)
        self.flu_start: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=0)
        self.flu_w: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=0)
        self.flu_wo: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=0)
        self.fmg_start: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=0)
        self.fmg_w: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=0)
        self.fmg_wo: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=0)
        self.fi_start: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=0)
        self.fi_w: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=0)
        self.fi_wo: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=0)
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
        self.som: SimpleNamespace | ipcc.LandUseNitrousEmissionFactor = SimpleNamespace(value=0)

    def calculate(self, is_minor_season=True) -> Result:
        module: FloodedRice = self.data
        module_for_checks = getattr(module, "parent", module)
        activity: Activity = getattr(module, "parent", module).activity
        project: Project = activity.project
        luc: LandUseChange = getattr(module, "parent", module).land_use_change
        area = luc.area if luc else getattr(module, "parent", module).area

        self.get_defaults()

        if module_for_checks.is_luc_remaining_same():
            self.inputs_start_w = [
                *[area, 0],
                self.efc.value,
                module.efc_t2_start,
                self.sfw_start.value,
                module.sfw_t2_start,
                self.sfp_start.value,
                module.sfp_t2_start,
                self.sfo_start.value,
                module.sfo_t2_start,
                module.efi_t2_start,
                self.yield_ref.value,
                module.crop_yield_start,
                self.n_estimation_factor.slope,
                self.n_estimation_factor.intercept,
                module.rice_straw_t2_start,
                self.burning_emission_factor.ch4,
                self.rice_cf.value,
                self.burning_emission_factor.n2o,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.ch4,
                self.efc.cultivation_period,
                module.cultivation_period_t2_start,
                self.soc_start,
                self.soc_w,
                getattr(module, "soc_t2_start", None),
                getattr(module, "soc_t2_w", None),
                self.fmg_start.value,
                self.fmg_w.value,
                module.fmg_t2_start,
                module.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module.flu_t2_start,
                module.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module.fi_t2_start,
                module.fi_t2_w,
                True,
                module.organic_amendment_type_start.name == "Straw Burnt",
                0,  # Delay
                is_minor_season,
            ]

            self.math_start_w = MathFloodedRice(*self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if module_for_checks.is_business_as_usual():
            self.inputs_start_wo = [
                *[area, 0],
                self.efc.value,
                module.efc_t2_start,
                self.sfw_start.value,
                module.sfw_t2_start,
                self.sfp_start.value,
                module.sfp_t2_start,
                self.sfo_start.value,
                module.sfo_t2_start,
                module.efi_t2_start,
                self.yield_ref.value,
                module.crop_yield_start,
                self.n_estimation_factor.slope,
                self.n_estimation_factor.intercept,
                module.rice_straw_t2_start,
                self.burning_emission_factor.ch4,
                self.rice_cf.value,
                self.burning_emission_factor.n2o,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.ch4,
                self.efc.cultivation_period,
                module.cultivation_period_t2_start,
                self.soc_start,
                self.soc_wo,
                getattr(module, "soc_t2_start", None),
                getattr(module, "soc_t2_wo", None),
                self.fmg_start.value,
                self.fmg_wo.value,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                module.flu_t2_start,
                module.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module.fi_t2_start,
                module.fi_t2_wo,
                CALCULATE_SOC_SOM_START_WO,
                module.organic_amendment_type_start.name == "Straw Burnt",
                DELAY_START_WO,
                self.som.value,
                is_minor_season,
            ]

            self.math_start_wo = MathFloodedRice(*self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module_for_checks.is_with():
            self.inputs_w = [
                *[0, area],
                self.efc.value,
                module.efc_t2_w,
                self.sfw_w.value,
                module.sfw_t2_w,
                self.sfp_w.value,
                module.sfp_t2_w,
                self.sfo_w.value,
                module.sfo_t2_w,
                module.efi_t2_w,
                self.yield_ref.value,
                module.crop_yield_w,
                self.n_estimation_factor.slope,
                self.n_estimation_factor.intercept,
                module.rice_straw_t2_w,
                self.burning_emission_factor.ch4,
                self.rice_cf.value,
                self.burning_emission_factor.n2o,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.ch4,
                self.efc.cultivation_period,
                module.cultivation_period_t2_w,
                self.soc_start,
                self.soc_w,
                getattr(module, "soc_t2_start", None),
                getattr(module, "soc_t2_w", None),
                self.fmg_start.value,
                self.fmg_w.value,
                module.fmg_t2_start,
                module.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module.flu_t2_start,
                module.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module.fi_t2_start,
                module.fi_t2_w,
                CALCULATE_SOC_SOM_W,
                module.organic_amendment_type_w.name == "Straw Burnt",
                DELAY_W,
                self.som.value,
                is_minor_season,
            ]

            self.math_w = MathFloodedRice(*self.inputs_w)
            self.math_w.calculate_emissions()

        if module_for_checks.is_without():
            self.inputs_wo = [
                *[0, area],
                self.efc.value,
                module.efc_t2_wo,
                self.sfw_wo.value,
                module.sfw_t2_wo,
                self.sfp_wo.value,
                module.sfp_t2_wo,
                self.sfo_wo.value,
                module.sfo_t2_wo,
                module.efi_t2_wo,
                self.yield_ref.value,
                module.crop_yield_wo,
                self.n_estimation_factor.slope,
                self.n_estimation_factor.intercept,
                module.rice_straw_t2_wo,
                self.burning_emission_factor.ch4,
                self.rice_cf.value,
                self.burning_emission_factor.n2o,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.ch4,
                self.efc.cultivation_period,
                module.cultivation_period_t2_wo,
                self.soc_start,
                self.soc_wo,
                getattr(module, "soc_t2_start", None),
                getattr(module, "soc_t2_wo", None),
                self.fmg_start.value,
                self.fmg_wo.value,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                module.flu_t2_start,
                module.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module.fi_t2_start,
                module.fi_t2_wo,
                CALCULATE_SOC_SOM_WO,
                module.organic_amendment_type_wo.name == "Straw Burnt",
                DELAY_WO,
                self.som.value,
                is_minor_season,
            ]

            self.math_wo = MathFloodedRice(*self.inputs_wo)
            self.math_wo.calculate_emissions()

        results_start_w = self.math_start_w.result if self.math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        results_w = self.math_w.result if self.math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = self.math_wo.result if self.math_wo else MathResult(project.implementation_years, project.capitalization_years)

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

    def get_defaults(self, calculate=False) -> dict:
        module: FloodedRice = self.data
        module_for_checks = getattr(module, "parent", module)
        activity: Activity = getattr(module, "parent", module).activity
        project: Project = activity.project
        luc: LandUseChange = module.land_use_change

        climate: Climate = activity.climate_t2 or project.climate
        moisture: Moisture = activity.moisture_t2 or project.moisture
        region: Region = project.country.region
        soil_type: SoilType = project.soil_type

        climate_flt = {"climate": climate}
        moisture_flt = {"moisture": moisture}
        soil_flt = {"soil_type": soil_type}
        region_flt = {"continent": region}

        if module_for_checks.is_luc_remaining_same():
            h2o_mgmt_before_start_flt = {"water_management_type_before_cultivation": module.water_management_type_before_cultivation_start}
            h2o_mgmt_after_start_flt = {"water_management_type_after_cultivation": module.water_management_type_after_cultivation_start}
            organic_amendment_start_flt = {"organic_amendment_type": module.organic_amendment_type_start}
            self.flu_start = get_flu_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.fmg_start = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.fi_start = get_fi_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.sfw_start = utils.get_or_raise(ipcc.RiceSFW, h2o_mgmt_after_start_flt, f"RiceSFW for {module.water_management_type_after_cultivation_start} does not exist")
            self.sfp_start = utils.get_or_raise(ipcc.RiceSFP, h2o_mgmt_before_start_flt, f"RiceSFP for {module.water_management_type_before_cultivation_start} does not exist")
            self.sfo_start = utils.get_or_raise(ipcc.RiceSFO, organic_amendment_start_flt, f"RiceSFO for {module.organic_amendment_type_start} does not exist")

        if module_for_checks.is_business_as_usual():
            h2o_mgmt_before_start_flt = {"water_management_type_before_cultivation": module.water_management_type_before_cultivation_start}
            h2o_mgmt_after_start_flt = {"water_management_type_after_cultivation": module.water_management_type_after_cultivation_start}
            organic_amendment_start_flt = {"organic_amendment_type": module.organic_amendment_type_start}
            self.flu_start = get_flu_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.fmg_start = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.fi_start = get_fi_data(module, climate, moisture, utils.ScenarioTypes.START)
            self.sfw_start = utils.get_or_raise(ipcc.RiceSFW, h2o_mgmt_after_start_flt, f"RiceSFW for {module.water_management_type_after_cultivation_start} does not exist")
            self.sfp_start = utils.get_or_raise(ipcc.RiceSFP, h2o_mgmt_before_start_flt, f"RiceSFP for {module.water_management_type_before_cultivation_start} does not exist")
            self.sfo_start = utils.get_or_raise(ipcc.RiceSFO, organic_amendment_start_flt, f"RiceSFO for {module.organic_amendment_type_start} does not exist")

        if module_for_checks.is_with():
            h2o_mgmt_before_w_flt = {"water_management_type_before_cultivation": module.water_management_type_before_cultivation_w}
            h2o_mgmt_after_w_flt = {"water_management_type_after_cultivation": module.water_management_type_after_cultivation_w}
            organic_amendment_w_flt = {"organic_amendment_type": module.organic_amendment_type_w}
            self.flu_w = get_flu_data(module, climate, moisture, utils.ScenarioTypes.WITH)
            self.fmg_w = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.WITH)
            self.fi_w = get_fi_data(module, climate, moisture, utils.ScenarioTypes.WITH)
            self.sfw_w = utils.get_or_raise(ipcc.RiceSFW, h2o_mgmt_after_w_flt, f"RiceSFW for {module.water_management_type_after_cultivation_w} does not exist")
            self.sfp_w = utils.get_or_raise(ipcc.RiceSFP, h2o_mgmt_before_w_flt, f"RiceSFP for {module.water_management_type_before_cultivation_w} does not exist")
            self.sfo_w = utils.get_or_raise(ipcc.RiceSFO, organic_amendment_w_flt, f"RiceSFO for {module.organic_amendment_type_w} does not exist")

        if module_for_checks.is_without():
            h2o_mgmt_before_wo_flt = {"water_management_type_before_cultivation": module.water_management_type_before_cultivation_wo}
            h2o_mgmt_after_wo_flt = {"water_management_type_after_cultivation": module.water_management_type_after_cultivation_wo}
            organic_amendment_wo_flt = {"organic_amendment_type": module.organic_amendment_type_wo}
            self.flu_wo = get_flu_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.fmg_wo = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.fi_wo = get_fi_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.sfw_wo = utils.get_or_raise(ipcc.RiceSFW, h2o_mgmt_after_wo_flt, f"RiceSFW for {module.water_management_type_after_cultivation_wo} does not exist")
            self.sfp_wo = utils.get_or_raise(ipcc.RiceSFP, h2o_mgmt_before_wo_flt, f"RiceSFP for {module.water_management_type_before_cultivation_wo} does not exist")
            self.sfo_wo = utils.get_or_raise(ipcc.RiceSFO, organic_amendment_wo_flt, f"RiceSFO for {module.organic_amendment_type_wo} does not exist")

        lut_name_rice_flt = {"land_use_type__name": "Rice"}

        if module.status.name == "READY" and calculate:
            self.calculate()
            self.efi_start.value = getattr(self.math_start_w, "adjusted_daily_ef_methane_tier_2_default", 0) or getattr(self.math_start_wo, "adjusted_daily_ef_methane_tier_2_default", 0)
            self.efi_w.value = getattr(self.math_w, "adjusted_daily_ef_methane_tier_2_default", 0)
            self.efi_wo.value = getattr(self.math_wo, "adjusted_daily_ef_methane_tier_2_default", 0)
            self.straw_burned_start = SimpleNamespace(value=getattr(self.math_start_w, "straw_tonnes_tier_2_default", 0) or getattr(self.math_start_wo, "straw_tonnes_tier_2_default", 0))
            self.straw_burned_w = SimpleNamespace(value=getattr(self.math_w, "straw_tonnes_tier_2_default", 0))
            self.straw_burned_wo = SimpleNamespace(value=getattr(self.math_wo, "straw_tonnes_tier_2_default", 0))
            self.sfo_start.value = getattr(self.math_start_w, "SFo_tier_2_default", 0) or getattr(self.math_start_wo, "SFo_tier_2_default", 0)
            self.sfo_w.value = getattr(self.math_w, "SFo_tier_2_default", 0)
            self.sfo_wo.value = getattr(self.math_wo, "SFo_tier_2_default", 0)

        self.soc = utils.get_or_raise(ipcc.SoilOrganicCarbon, climate_flt | moisture_flt | soil_flt, f"SoilOrganicCarbon for {climate.name}, {moisture.name} and {soil_type.name} does not exist")
        self.som = utils.get_or_raise(ipcc.LandUseNitrousEmissionFactor, moisture_flt, f"LandUseNitrousEmissionFactor for {moisture.name} does not exist")

        # self.grassland_soc = get_grassland_soc(luc)
        # self.soc_start = self.grassland_soc.value if self.grassland_soc else self.soc.value
        self.soc_start = self.soc.value
        if not self.soc_start:
            raise ValueError(f"SoilOrganicCarbon for {climate.name}, {moisture.name} and {soil_type.name} does not exist")
        self.soc_w = self.soc.value
        self.soc_wo = self.soc.value

        self.efc = utils.get_or_raise(ipcc.RiceDefaultEmissionFactor, region_flt, f"RiceDefaultEmissionFactor for {region.name} does not exist")
        self.yield_ref = utils.get_or_raise(ipcc.RiceYield, region_flt, f"RiceYield for {region.name} does not exist")

        self.n_estimation_factor = utils.get_or_raise(ipcc.CropNitrousEstimationDefaultFactor, lut_name_rice_flt, "Default nitrous estimation factor is not defined for rice")
        self.burning_emission_factor = utils.get_or_raise(ipcc.BurningEmissionFactor, {"category__name": "Agricultural residues"}, "Burning emission factor is not defined for agricultural residues")
        self.rice_cf = utils.get_or_raise(ipcc.FiresCombustionFactor, lut_name_rice_flt, "Fires combustion factor is not defined for rice")


class FloodedRiceCalculator(BaseCalculator):
    """
    Calculator for flooded rice.
    """

    def calculate(self) -> Result:
        module: FloodedRice = self.data
        res_w = MathResult(module.activity.project.implementation_years, module.activity.project.capitalization_years)
        res_wo = MathResult(module.activity.project.implementation_years, module.activity.project.capitalization_years)

        r_w, r_wo = FloodedRiceSeasonCalculator(module).calculate(False)

        res_w += r_w
        res_wo += r_wo

        for season in module.minor_seasons.all():
            r_w, r_wo = FloodedRiceSeasonCalculator(season).calculate()
            res_w += r_w
            res_wo += r_wo

        return (res_w, res_wo)

    def get_defaults(self, calculate=calculate) -> dict:
        FloodedRiceSeasonCalculator(input).get_defaults(calculate=calculate)


class GrasslandCalculator(BaseCalculator):
    """
    Calculator for grassland.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        self.ef = SimpleNamespace(value=0)
        self.agb = SimpleNamespace(value=0)
        self.cf = SimpleNamespace(value=0)
        self.soc = SimpleNamespace(value=0)
        self.soc_start = SimpleNamespace(fi=1, fmg=1, flu=1)
        self.soc_w = SimpleNamespace(fi=1, fmg=1, flu=1)
        self.soc_w = SimpleNamespace(fi=1, fmg=1, flu=1)
        self.soc_wo = SimpleNamespace(fi=1, fmg=1, flu=1)
        self.som: SimpleNamespace | ipcc.LandUseNitrousEmissionFactor = SimpleNamespace(value=0)

    def get_defaults(self, calculate=False):
        module: Grassland = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        # duration = activity.duration_t2 or project.implementation_years
        # # TODO: Is this assuming that the activity start_year must be > project start_year?
        # delay = ((activity.start_year_t2 or 0) - project.start_year) or 0
        # capitalization = project.implementation_years - duration + project.capitalization_years

        self.ef = utils.get_or_raise(ipcc.BurningEmissionFactor, {"category__name": "Savanna and grassland"}, "Burning emission factor for savanna and grassland does not exist")
        self.agb = utils.get_or_raise(ipcc.GrasslandAGB, {"climate": project.climate, "moisture": project.moisture}, f"AGB for {project.climate.name} climate and {project.moisture.name} moisture does not exist")
        self.cf = utils.get_or_raise(GrasslandParameter, {"name": "default_combustion_factor"}, "Default combustion factor does not exist")
        self.soc = utils.get_or_raise(ipcc.SoilOrganicCarbon, {"climate": project.climate, "moisture": project.moisture, "soil_type": project.soil_type}, f"Soil organic carbon for {project.climate.name} climate, {project.moisture.name} moisture and {project.soil_type.name} soil type does not exist")
        self.som = utils.get_or_raise(ipcc.LandUseNitrousEmissionFactor, {"moisture": project.moisture}, f"Land use nitrous emission factor for {project.moisture.name} moisture does not exist")

        if is_luc_remaining_same(module) or is_with(module):

        try:
            self.cf = GrasslandParameter.objects.get(name="default_combustion_factor")
        except GrasslandParameter.DoesNotExist:
            raise Exception("Default combustion factor does not exist")

        try:
            self.soc = ipcc.SoilOrganicCarbon.objects.get(climate=project.climate, moisture=project.moisture, soil_type=project.soil_type)
        except ipcc.SoilOrganicCarbon.DoesNotExist:
            raise Exception(f"Soil organic carbon for {project.climate.name} climate, {project.moisture.name} moisture and {project.soil_type.name} soil type does not exist")

        if module.is_luc_remaining_same():

            try:
                self.soc_start = ipcc.GrasslandStockExchangeFactor.objects.get_or_default(grassland_management_type=module.grassland_management_type_start, climate=project.climate)
            except ipcc.GrasslandStockExchangeFactor.DoesNotExist:
                raise Exception(f"Stock exchange factor for {module.grassland_management_type_start.name} in {project.climate.name} climate does not exist")

            try:
                self.soc_w = ipcc.GrasslandStockExchangeFactor.objects.get_or_default(grassland_management_type=module.grassland_management_type_w, climate=project.climate)
            except ipcc.GrasslandStockExchangeFactor.DoesNotExist:
                raise Exception(f"Stock exchange factor for {module.grassland_management_type_w.name} in {project.climate.name} climate does not exist")

        if module.is_with():
            try:
                self.soc_start = ipcc.GrasslandStockExchangeFactor.objects.get_or_default(grassland_management_type=module.grassland_management_type_start, climate=project.climate)
            except ipcc.GrasslandStockExchangeFactor.DoesNotExist:
                raise Exception(f"Stock exchange factor for {module.grassland_management_type_start.name} in {project.climate.name} climate does not exist")

            try:
                self.soc_w = ipcc.GrasslandStockExchangeFactor.objects.get_or_default(grassland_management_type=module.grassland_management_type_w, climate=project.climate)
            except ipcc.GrasslandStockExchangeFactor.DoesNotExist:
                raise Exception(f"Stock exchange factor for {module.grassland_management_type_w.name} in {project.climate.name} climate does not exist")

        if module.is_business_as_usual():

            self.soc_start = utils.get_or_raise(ipcc.GrasslandStockExchangeFactor, {"grassland_management_type": module.grassland_management_type_start, "climate": project.climate}, f"Stock exchange factor for {module.grassland_management_type_start.name} in {project.climate.name} climate does not exist")
            self.soc_wo = utils.get_or_raise(ipcc.GrasslandStockExchangeFactor, {"grassland_management_type": module.grassland_management_type_wo, "climate": project.climate}, f"Stock exchange factor for {module.grassland_management_type_wo.name} in {project.climate.name} climate does not exist")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Grassland module.
        """
        log.debug("START GrasslandCalculator.calculate")

        module: Grassland = self.data
        activity: Activity = module.activity
        project: Project = activity.project
        luc: LandUseChange = module.land_use_change

        # duration = activity.duration_t2 or project.implementation_years
        # # TODO: Is this assuming that the activity start_year must be > project start_year?
        # delay = ((activity.start_year_t2 or 0) - project.start_year) or 0
        # capitalization = project.implementation_years - duration + project.capitalization_years

        change_rate = module.activity.change_rate
        area = luc.area if luc and luc.area else module.area

        self.get_defaults()

        math_start_w = None
        math_start_wo = None
        math_w = None
        math_wo = None

        if module.is_luc_remaining_same():
            log.debug("LUC remaining same")

            self.inputs_start_w = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.fire_periodicity_start,
                module.is_fire_used_start,
                self.ef.ch4,
                self.ef.n2o,
                self.agb.value,
                module.get_biomass_t2(utils.ScenarioTypes.START),
                self.cf.value,
                module.combustion_factor_t2_start,
                self.soc.value,
                self.soc.value,
                module.soc_t2_start,
                module.soc_t2_w,
                CALCULATE_SOC_SOM_START_W,
                self.soc_start.fmg,
                self.soc_w.fmg,
                module.fmg_t2_start,
                module.fmg_t2_w,
                self.soc_start.flu,
                self.soc_w.flu,
                module.flu_t2_start,
                module.flu_t2_w,
                self.soc_start.fi,
                self.soc_w.fi,
                module.fi_t2_start,
                module.fi_t2_w,
                DELAY_START_W,
                self.som.value,
            ]

            log.debug("Inputs start w: %s", self.inputs_start_w)

            math_start_w = MathGrassland(*self.inputs_start_w)
            math_start_w.calculate_emissions()

        if module.is_with():
            log.debug("With")

            self.inputs_w = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.fire_periodicity_w,
                module.is_fire_used_w,
                self.ef.ch4,
                self.ef.n2o,
                self.agb.value,
                module.get_biomass_t2(utils.ScenarioTypes.WITH),
                self.cf.value,
                module.combustion_factor_t2_start,
                self.soc.value,
                self.soc.value,
                module.soc_t2_start,
                module.soc_t2_w,
                CALCULATE_SOC_SOM_W,
                self.soc_start.fmg,
                self.soc_w.fmg,
                module.fmg_t2_start,
                module.fmg_t2_w,
                self.soc_start.flu,
                self.soc_w.flu,
                module.flu_t2_start,
                module.flu_t2_w,
                self.soc_start.fi,
                self.soc_w.fi,
                module.fi_t2_start,
                module.fi_t2_w,
                DELAY_W,
                self.som.value,
            ]

            log.debug("Inputs w: %s", self.inputs_w)

            math_w = MathGrassland(*self.inputs_w)
            math_w.calculate_emissions()

        if module.is_business_as_usual():
            log.debug("Business as usual")

            self.inputs_start_wo = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.fire_periodicity_start,
                module.is_fire_used_start,
                self.ef.ch4,
                self.ef.n2o,
                self.agb.value,
                module.get_biomass_t2(utils.ScenarioTypes.START),
                self.cf.value,
                module.combustion_factor_t2_start,
                self.soc.value,
                self.soc.value,
                module.soc_t2_start,
                module.soc_t2_wo,
                CALCULATE_SOC_SOM_START_WO,
                self.soc_start.fmg,
                self.soc_wo.fmg,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                self.soc_start.flu,
                self.soc_wo.flu,
                module.flu_t2_start,
                module.flu_t2_wo,
                self.soc_start.fi,
                self.soc_wo.fi,
                module.fi_t2_start,
                module.fi_t2_wo,
                DELAY_START_WO,
                self.som.value,
            ]

            log.debug("Inputs start wo: %s", self.inputs_start_wo)

            math_start_wo = MathGrassland(*self.inputs_start_wo)
            math_start_wo.calculate_emissions()

        if module.is_without():
            log.debug("Without")

            self.inputs_wo = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.fire_periodicity_wo,
                module.is_fire_used_wo,
                self.ef.ch4,
                self.ef.n2o,
                self.agb.value,
                module.get_biomass_t2(utils.ScenarioTypes.WITHOUT),
                self.cf.value,
                module.combustion_factor_t2_start,
                self.soc.value,
                self.soc.value,
                module.soc_t2_start,
                module.soc_t2_wo,
                CALCULATE_SOC_SOM_WO,
                self.soc_start.fmg,
                self.soc_wo.fmg,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                self.soc_start.flu,
                self.soc_wo.flu,
                module.flu_t2_start,
                module.flu_t2_wo,
                self.soc_start.fi,
                self.soc_wo.fi,
                module.fi_t2_start,
                module.fi_t2_wo,
                DELAY_WO,
                self.som.value,
            ]

            log.debug("Inputs wo: %s", self.inputs_wo)

            math_wo = MathGrassland(*self.inputs_wo)
            math_wo.calculate_emissions()

        res_start_w = math_start_w.result if math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        res_start_wo = math_start_wo.result if math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        res_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        res_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        log.debug("start_w breakdown")
        res_start_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("w breakdown")
        res_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("start_wo breakdown")
        res_start_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("wo breakdown")
        res_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("Total WITH: %s", (res_w + res_start_w).breakdown(by=BreakdownTypes.TOTAL))
        log.debug("Total WITHOUT: %s", (res_wo + res_start_wo).breakdown(by=BreakdownTypes.TOTAL))

        log.debug("END GrasslandCalculator.calculate")
        return (res_w + res_start_w, res_wo + res_start_wo)

    def defaults(self):
        self.calculate()

        module: Grassland = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if module.is_luc_remaining_same():
            math_start = MathGrassland(*self.inputs_start_w)
            math_start_defaults = math_start.evaluate_tier_2_defaults()
            defaults_start.update(math_start_defaults.start)
            defaults_start.update(math_start_defaults.other)
        elif module.is_business_as_usual():
            math_start = MathGrassland(*self.inputs_start_wo)
            math_start_defaults = math_start.evaluate_tier_2_defaults()
            defaults_start.update(math_start_defaults.start)
            defaults_start.update(math_start_defaults.other)

        if module.is_with():
            math_w = MathGrassland(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.end)
            defaults_w.update(math_w_defaults.other)

        if module.is_without():
            math_wo = MathGrassland(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.end)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


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
            self.inputs_w = [
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                module.total_catch_yr_start,
                module.total_catch_yr_w,
                ef_diesel_default,
                module.energy_emission_factor_t2_start,
                module.energy_emission_factor_t2_w,
                fui_default_start,
                fui_default_w,
                module.fui_start,
                module.fui_w,
                module.refrigerant_gwp,
                module.refrigerant_gwp_t2_start,
                module.refrigerant_gwp_t2_w,
                lost_refrigerant_default,
                module.refrigerant_lost_per_tonne_t2_start,
                module.refrigerant_lost_per_tonne_t2_w,
                module.refrigerant_pc_start,
                module.refrigerant_pc_w,
                tonnes_ice_default,
                module.tonnes_of_ice_t2_start,
                module.tonnes_of_ice_t2_w,
                kw_tonnes,
                module.inshore_ice_production_kwh_per_tonne_t2_start,
                module.inshore_ice_production_kwh_per_tonne_t2_w,
                electricity_emission.operating_margin,
                module.ice_preserved_catch_pc_start,
                module.ice_preserved_catch_pc_w,
            ]
            log.debug("Inputs with: %s", self.inputs_w)

            math_w = MathFishery(*self.inputs_w)
            math_w.calculate_emissions()

        if module.is_without():
            log.debug("IS WITHOUT")
            self.inputs_wo = [
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                module.total_catch_yr_start,
                module.total_catch_yr_wo,
                ef_diesel_default,
                module.energy_emission_factor_t2_start,
                module.energy_emission_factor_t2_wo,
                fui_default_start,
                fui_default_wo,
                module.fui_start,
                module.fui_wo,
                module.refrigerant_gwp,
                module.refrigerant_gwp_t2_start,
                module.refrigerant_gwp_t2_wo,
                lost_refrigerant_default,
                module.refrigerant_lost_per_tonne_t2_start,
                module.refrigerant_lost_per_tonne_t2_wo,
                module.refrigerant_pc_start,
                module.refrigerant_pc_wo,
                tonnes_ice_default,
                module.tonnes_of_ice_t2_start,
                module.tonnes_of_ice_t2_wo,
                kw_tonnes,
                module.inshore_ice_production_kwh_per_tonne_t2_start,
                module.inshore_ice_production_kwh_per_tonne_t2_wo,
                electricity_emission.operating_margin,
                module.ice_preserved_catch_pc_start,
                module.ice_preserved_catch_pc_wo,
            ]
            log.debug("Inputs without: %s", self.inputs_wo)

            math_wo = MathFishery(*self.inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

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
            self.inputs_w = [
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                module.total_catch_yr_start,
                module.total_catch_yr_w,
                ef_diesel_default,
                module.energy_emission_factor_t2_start,
                module.energy_emission_factor_t2_w,
                fui_default_start,
                fui_default_w,
                module.fui_start,
                module.fui_w,
                module.refrigerant_gwp,
                module.refrigerant_gwp_t2_start,
                module.refrigerant_gwp_t2_w,
                lost_refrigerant_default,
                module.refrigerant_lost_per_tonne_t2_start,
                module.refrigerant_lost_per_tonne_t2_w,
                module.refrigerant_pc_start,
                module.refrigerant_pc_w,
                tonnes_ice_default,
                module.tonnes_of_ice_t2_start,
                module.tonnes_of_ice_t2_w,
                kw_tonnes,
                module.inshore_ice_production_kwh_per_tonne_t2_start,
                module.inshore_ice_production_kwh_per_tonne_t2_w,
                electricity_emission.operating_margin,
                module.ice_preserved_catch_pc_start,
                module.ice_preserved_catch_pc_w,
            ]
            log.debug("Inputs with: %s", self.inputs_w)

            math_w = MathFishery(*self.inputs_w)
            math_w.calculate_emissions()

        if module.is_without():
            log.debug("IS WITHOUT")
            self.inputs_wo = [
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                module.total_catch_yr_start,
                module.total_catch_yr_wo,
                ef_diesel_default,
                module.energy_emission_factor_t2_start,
                module.energy_emission_factor_t2_wo,
                fui_default_start,
                fui_default_wo,
                module.fui_start,
                module.fui_wo,
                module.refrigerant_gwp,
                module.refrigerant_gwp_t2_start,
                module.refrigerant_gwp_t2_wo,
                lost_refrigerant_default,
                module.refrigerant_lost_per_tonne_t2_start,
                module.refrigerant_lost_per_tonne_t2_wo,
                module.refrigerant_pc_start,
                module.refrigerant_pc_wo,
                tonnes_ice_default,
                module.tonnes_of_ice_t2_start,
                module.tonnes_of_ice_t2_wo,
                kw_tonnes,
                module.inshore_ice_production_kwh_per_tonne_t2_start,
                module.inshore_ice_production_kwh_per_tonne_t2_wo,
                electricity_emission.operating_margin,
                module.ice_preserved_catch_pc_start,
                module.ice_preserved_catch_pc_wo,
            ]
            log.debug("Inputs without: %s", self.inputs_wo)

            math_wo = MathFishery(*self.inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

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
            math_w = MathFishery(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.end)
            defaults_w.update(math_w_defaults.other)

        if module.is_without():
            math_wo = MathFishery(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.end)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class AquacultureCalculator(BaseCalculator):
    """
    Calculator for aquaculture.
    """

    def get_defaults(self, input: Module) -> dict:
        return super().get_defaults(input)

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Aquaculture module.
        """

        module: Aquaculture = self.data
        change_rate = module.activity.change_rate
        project: Project = module.activity.project

        ELECTRICITY_USED_DEFAULT = 0  # TODO: Add as database parameter

        try:
            NITROUS_EF_DEFAULT = AquacultureParameter.objects.get(name="nitrous_ef_default").value
        except AquacultureParameter.DoesNotExist:
            raise ValueError("Default nitrous emission factor does not exist")

        try:
            # TODO: This will now be used in the inputs module for feed
            FEED_EF_DEFAULT = AquacultureParameter.objects.get(name="feed_ef_default").value
        except AquacultureParameter.DoesNotExist:
            raise ValueError("Default feed emission factor does not exist")

        try:
            elec = ipcc.ElectricityEmission.objects.get(country=project.country)
            log.debug(f"Operating margin: {elec.operating_margin}")
        except ipcc.ElectricityEmission.DoesNotExist:
            raise ValueError(f"Electricity emission for {project.country.name} does not exist")

        math_w = None
        math_wo = None

        if module.is_with():
            log.debug("IS WITH")
            inputs_w = [
                module.annual_production_start,
                module.annual_production_w,
                NITROUS_EF_DEFAULT,
                module.n2o_from_production_t2_start,
                module.n2o_from_production_t2_w,
                project.gw_potential.n2o,
                ELECTRICITY_USED_DEFAULT,
                module.electricity_used_t2_start,
                module.electricity_used_t2_w,
                elec.operating_margin,
                module.electricity_ef_t2_start,
                module.electricity_ef_t2_w,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
            ]
            log.debug("Inputs with: %s", inputs_w)

            math_w = MathAquaculture(*inputs_w)
            math_w.calculate_emissions()

        if module.is_without():
            log.debug("IS WITHOUT")
            inputs_wo = [
                module.annual_production_start,
                module.annual_production_wo,
                NITROUS_EF_DEFAULT,
                module.n2o_from_production_t2_start,
                module.n2o_from_production_t2_wo,
                project.gw_potential.n2o,
                ELECTRICITY_USED_DEFAULT,
                module.electricity_used_t2_start,
                module.electricity_used_t2_wo,
                elec.operating_margin,
                module.electricity_ef_t2_start,
                module.electricity_ef_t2_w,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
            ]
            log.debug("Inputs without: %s", inputs_wo)

            math_wo = MathAquaculture(*inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        log.debug("Results WITH")
        results_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("Results WITHOUT")
        results_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        results_tuple = (results_w, results_wo)

        return results_tuple

    def defaults(self):
        pass


class InputCalculator(BaseCalculator):
    """
    Calculator for Inputs macromodule
    """

    def get_defaults(self, input: Module) -> dict:
        return super().get_defaults(input)

    def calculate(self) -> list[MathResult]:
        module: Input = self.data
        project: Project = module.activity.project

        results_w = MathResult(project.implementation_years, project.capitalization_years)
        results_wo = MathResult(project.implementation_years, project.capitalization_years)

        entries = module.input_entries.all()
        for entry in entries:
            r_w, r_wo = InputEntryCalculator(entry).calculate()

            results_w += r_w
            results_wo += r_wo

        return (results_w, results_wo)

    def defaults(self) -> DefaultData:
        self.calculate()

        input: Input = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        for entry in input.input_entries.all():
            defaults_start_entry, defaults_w_entry, defaults_wo_entry = InputEntryCalculator(entry).defaults()

            defaults_start.update(defaults_start_entry)
            defaults_w.update(defaults_w_entry)
            defaults_wo.update(defaults_wo_entry)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class InputEntryCalculator(BaseCalculator):
    """
    Calculator for single input entries.
    """

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
            self.ref = ipcc.InputReference.objects.get(gw_potential=project.gw_potential, input_type=module.input_type)
        except ipcc.InputReference.DoesNotExist:
            raise ValueError(f"Reference for {module.input_type.name} does not exist for {project.gw_potential.name}.")

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

        self.inputs_w = [
            module.value_start,
            module.value_w,
            activity.change_rate.name,
            self.ef.co2_value if self.ef else None,
            module.co2_emissions_t2,
            self.ref.co2_multiplier,
            self.ref.co2_emissions_multiplier,
            project.implementation_years,
            project.capitalization_years,
            self.ef.n2o_value if self.ef else None,
            module.n2o_emissions_t2,
            self.ref.n2o_quantity_multiplier,
            self.ref.n2o_emissions_multiplier,
            self.ef.co2_eq_value if self.ef else None,
            module.co2_e_emissions_t2,
            self.ref.production_quantity_multiplier,
            self.ref.production_emissions_multiplier,
        ]

        math_w = MathInputs(*self.inputs_w)
        math_w.calculate_emissions()

        self.inputs_wo = [
            module.value_start,
            module.value_wo,
            activity.change_rate.name,
            self.ef.co2_value if self.ef else None,
            module.co2_emissions_t2,
            self.ref.co2_multiplier,
            self.ref.co2_emissions_multiplier,
            project.implementation_years,
            project.capitalization_years,
            self.ef.n2o_value if self.ef else None,
            module.n2o_emissions_t2,
            self.ref.n2o_quantity_multiplier,
            self.ref.n2o_emissions_multiplier,
            self.ef.co2_eq_value if self.ef else None,
            module.co2_e_emissions_t2,
            self.ref.production_quantity_multiplier,
            self.ref.production_emissions_multiplier,
        ]

        math_wo = MathInputs(*self.inputs_wo)
        math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple

    def defaults(self) -> DefaultData:
        self.calculate()

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        math_w = MathInputs(*self.inputs_w)
        math_w_defaults = math_w.evaluate_tier_2_defaults()
        defaults_w.update(math_w_defaults.start)
        defaults_w.update(math_w_defaults.other)

        math_wo = MathInputs(*self.inputs_wo)
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
        res_w = MathResult(
            module.activity.project.implementation_years,
            module.activity.project.capitalization_years,
        )
        res_wo = MathResult(
            module.activity.project.implementation_years,
            module.activity.project.capitalization_years,
        )

        for elec in module.electricities.all():
            r_w, r_wo = ElectricityCalculator(elec).calculate()

            res_w += r_w
            res_wo += r_wo

        for fuel in module.fuels.all():
            r_w, r_wo = FuelCalculator(fuel).calculate()

            res_w += r_w
            res_wo += r_wo

        return (res_w, res_wo)

    def defaults(self) -> DefaultData:
        pass


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

            self.ef_source = "Combined Margin"  # NOTE: Here it should be added to the DB and set as default value in my opinion
            self.ef_country = elec.operating_margin if module.ef_source else elec.combined_margin
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

        try:
            elec = ipcc.ElectricityEmission.objects.get(country=module.country)
            if module.ef_source:  # NOTE: previously was input.ef_source.name == "Operating margin", however it is nullable and is set to None unless selected in the Tier2. This check works and effectively does the same thing
                log.debug(f"Operating margin: {elec.operating_margin}")
            else:
                log.debug(f"Combined margin: {elec.combined_margin}")
        except ipcc.ElectricityEmission.DoesNotExist:
            raise ValueError(f"Electricity emission for {project.country.name} does not exist")

        math_w = None
        math_wo = None

        inputs_w = [
            elec.operating_margin if module.ef_source else elec.combined_margin,
            module.ef_t2_start,
            module.ef_t2_w,
            module.mwh_start,
            module.mwh_w,
            module.transmission_loss_start,
            module.transmission_loss_w,
            change_rate.name,
            project.implementation_years,
            project.capitalization_years,
        ]
        log.debug("Inputs with: %s", inputs_w)

        math_w = ElectryicityConsumption(*inputs_w)
        math_w.calculate_emissions()

        inputs_wo = [
            elec.operating_margin if module.ef_source else elec.combined_margin,
            module.ef_t2_start,
            module.ef_t2_wo,
            module.mwh_start,
            module.mwh_wo,
            module.transmission_loss_start,
            module.transmission_loss_wo,
            change_rate.name,
            project.implementation_years,
            project.capitalization_years,
        ]
        log.debug("Inputs without: %s", inputs_wo)

        math_wo = ElectryicityConsumption(*inputs_wo)
        math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

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

    def get_defaults(self, calculate=False) -> dict:
        input: Fuel = self.data
        activity: Activity = input.parent.activity
        project: Project = activity.project
        change_rate = activity.change_rate

        try:
            self.ef_fuel_t_co2_eq = ipcc.EnergyDefaultEmissionFactor.objects.get(fuel_type=input.fuel_type).t_co2_eq
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            raise ValueError(f"Default emission factor for {input.fuel_type.name} does not exist. Please select tier 2 value.")

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Fuel module.
        """
        log.debug("START FuelCalculator.calculate")

        module: Fuel = self.data
        activity: Activity = module.parent.activity
        project: Project = activity.project
        change_rate = activity.change_rate

        macro_fuel_type = module.fuel_type.macro_fuel_type.name

        try:
            ef = ipcc.EnergyDefaultEmissionFactor.objects.get(fuel_type=module.fuel_type)
            log.debug(f"Default emission factor: {ef.t_co2_eq}")
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            raise ValueError(f"Default emission factor for {module.fuel_type.name} does not exist. Please select tier 2 value.")

        math_w = None
        math_wo = None

        if macro_fuel_type == "Liquid or gaseous":
            log.debug("Liquid or gaseous fuel")
            input_w = [
                ef.t_co2_eq,
                module.ef_t2,
                module.fuel_consumption_start,
                module.fuel_consumption_w,
                change_rate.name,
                project.implementation_years,
                project.capitalization_years,
            ]
            log.debug("Inputs with: %s", input_w)

            math_w = FuelConsumption(*input_w)
            math_w.calculate_emissions()

            input_wo = [
                ef.t_co2_eq,
                module.ef_t2,
                module.fuel_consumption_start,
                module.fuel_consumption_wo,
                change_rate.name,
                project.implementation_years,
                project.capitalization_years,
            ]
            log.debug("Inputs without: %s", input_wo)

            math_wo = FuelConsumption(*input_wo)
            math_wo.calculate_emissions()

        elif macro_fuel_type == "Solid":
            log.debug("Solid fuel")
            input_w = [
                ef.net_calorific_value,
                ef.co2,
                ef.ch4,
                ef.n2o,
                module.account_for_co2,
                project.gw_potential.ch4,
                project.gw_potential.n2o,
                module.ef_t2,
                module.fuel_consumption_start,
                module.fuel_consumption_w,
                activity.change_rate.name,
                project.implementation_years,
                project.capitalization_years,
            ]
            log.debug("Inputs with: %s", input_w)

            math_w = SolidConsumption(*input_w)
            math_w.calculate_emissions()

            input_wo = [
                ef.net_calorific_value,
                ef.co2,
                ef.ch4,
                ef.n2o,
                module.account_for_co2,
                project.gw_potential.ch4,
                project.gw_potential.n2o,
                module.ef_t2,
                module.fuel_consumption_start,
                module.fuel_consumption_wo,
                activity.change_rate.name,
                project.implementation_years,
                project.capitalization_years,
            ]
            log.debug("Inputs without: %s", input_wo)

            math_wo = SolidConsumption(*input_wo)
            math_wo.calculate_emissions()

        else:
            raise ValueError(f"Fuel type {macro_fuel_type} not supported by calculations.")

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        log.debug("Results WITH")
        results_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("Results WITHOUT")
        results_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("END FuelCalculator.calculate")
        log.debug("")
        return results_tuple

    def defaults(self) -> DefaultData:
        pass


class SettlementCalculator(BaseCalculator):
    """
    Calculator for settlements
    """

    def __init__(self, module) -> None:
        super().__init__(module)
        module: Settlement = module

        self.inputs_start_w = []
        self.inputs_start_wo = []
        self.inputs_w = []
        self.inputs_wo = []
        self.soc = SimpleNamespace(value=0)

        self.nitrous_ef = SimpleNamespace(value=0)

        self.ef_start = SimpleNamespace(value=0)
        self.ef_w = SimpleNamespace(value=0)
        self.ef_wo = SimpleNamespace(value=0)

        self.flu_start = SimpleNamespace(value=1)
        self.fi_start = SimpleNamespace(value=1)
        self.fmg_start = SimpleNamespace(value=1)

        self.flu_w = SimpleNamespace(value=1)
        self.fi_w = SimpleNamespace(value=1)
        self.fmg_w = SimpleNamespace(value=1)

        self.flu_wo = SimpleNamespace(value=1)
        self.fi_wo = SimpleNamespace(value=1)
        self.fmg_wo = SimpleNamespace(value=1)

        self.math_start_w = None
        self.math_start_wo = None
        self.math_w = None
        self.math_wo = None

    def get_defaults(self, calculate=False) -> dict:
        log.debug("START SettlementCalculator.get_defaults")
        module: Settlement = self.data
        activity: Activity = module.activity
        project: Project = activity.project
        luc: LandUseChange = module.land_use_change

        climate: Climate = module.activity.climate_t2 or module.activity.project.climate
        moisture: Moisture = module.activity.moisture_t2 or module.activity.project.moisture

        cm = {
            "climate": climate,
            "moisture": moisture,
        }

        self.soc = utils.get_or_raise(ipcc.SOC, cm | {"soil_type": project.soil_type}, f"SOC not found for {climate.name} climate, {moisture.name} moisture and {project.soil_type.name} soil type not found. Please enter tier 2 value.")
        self.nitrous_ef = utils.get_or_raise(ipcc.NitrousEmissionFactor, {"moisture": moisture}, f"Nitrous EF not found for {moisture.name} moisture")

        if module.is_business_as_usual() or module.is_luc_remaining_same():
            self.ef_start: ipcc.SettlementEF = utils.get_or_raise(ipcc.SettlementEF, {"settlement_type": module.settlement_type_start, "climate": climate, "moisture": moisture}, f"Settlement EF not found for {module.settlement_type_start.name}")
            self.flu_start = SimpleNamespace(value=self.ef_start.flu)
            self.fi_start = SimpleNamespace(value=self.ef_start.fi)
            self.fmg_start = SimpleNamespace(value=self.ef_start.fmg)

        if module.is_with():
            self.ef_w: ipcc.SettlementEF = utils.get_or_raise(ipcc.SettlementEF, {"settlement_type": module.settlement_type_w, "climate": climate, "moisture": moisture}, f"Settlement EF not found for {module.settlement_type_w.name}")
            self.flu_w = SimpleNamespace(value=self.ef_w.flu)
            self.fi_w = SimpleNamespace(value=self.ef_w.fi)
            self.fmg_w = SimpleNamespace(value=self.ef_w.fmg)

        if module.is_without():
            self.ef_wo: ipcc.SettlementEF = utils.get_or_raise(ipcc.SettlementEF, {"settlement_type": module.settlement_type_wo, "climate": climate, "moisture": moisture}, f"Settlement EF not found for {module.settlement_type_wo.name}")
            self.flu_wo = SimpleNamespace(value=self.ef_wo.flu)
            self.fi_wo = SimpleNamespace(value=self.ef_wo.fi)
            self.fmg_wo = SimpleNamespace(value=self.ef_wo.fmg)

        if luc and module.settlement_type_start.name.casefold() != "paved settlement":
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
            module.activity.project.implementation_years,
            module.activity.project.capitalization_years,
        )
        res_wo = MathResult(
            module.activity.project.implementation_years,
            module.activity.project.capitalization_years,
        )

        self.get_defaults()

        if module.is_luc_remaining_same():
            log.debug("LUC remaining same")

            self.inputs_start_w = [
                *[module.area, 0],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.nitrous_ef.value,
                self.soc.value,
                self.soc.value,
                module.soc_t2_start,
                module.soc_t2_w,
                False,
                self.fmg_start.value,
                self.fmg_w.value,
                module.fmg_t2_start,
                module.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module.flu_t2_start,
                module.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module.fi_t2_start,
                module.fi_t2_w,
                0,  # Delay
            ]

            self.math_start_w = NotCultivatedLand(*self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if module.is_business_as_usual():

            self.inputs_start_wo = [
                *[module.area, 0],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.nitrous_ef.value,
                self.soc.value,
                self.soc.value,
                module.soc_t2_start,
                module.soc_t2_wo,
                False,
                self.fmg_start.value,
                self.fmg_wo.value,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                module.flu_t2_start,
                module.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module.fi_t2_start,
                module.fi_t2_wo,
                0,  # Delay
            ]

            self.math_start_wo = NotCultivatedLand(*self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module.is_with():

            self.inputs_w = [
                *[0, module.area],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.nitrous_ef.value,
                self.soc.value,  # SOCinitial
                self.soc.value,
                module.soc_t2_start,
                module.soc_t2_w,
                True,
                self.fmg_start.value,
                self.fmg_w.value,
                module.fmg_t2_start,
                module.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module.flu_t2_start,
                module.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module.fi_t2_start,
                module.fi_t2_w,
                0,  # Delay
            ]

            self.math_w = NotCultivatedLand(*self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():

            self.inputs_wo = [
                *[0, module.area],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.nitrous_ef.value,
                self.soc.value,
                self.soc.value,
                module.soc_t2_start,
                module.soc_t2_wo,
                True,
                self.fmg_start.value,
                self.fmg_wo.value,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                module.flu_t2_start,
                module.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module.fi_t2_start,
                module.fi_t2_wo,
                0,  # Delay
            ]

            self.math_wo = NotCultivatedLand(*self.inputs_wo)
            self.math_wo.calculate_emissions()

        results_start_w = self.math_start_w.result if self.math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        results_w = self.math_w.result if self.math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = self.math_wo.result if self.math_wo else MathResult(project.implementation_years, project.capitalization_years)

        res_w += results_start_w
        res_wo += results_start_wo

        res_w += results_w
        res_wo += results_wo

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

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Building module.
        """

        module: Building = self.data
        parent: Settlement = module.parent
        activity: Activity = parent.activity
        project: Project = activity.project

        math_w = None
        math_wo = None

        # TODO: What do we need the start scenario for?
        # TODO: Define if all the fields of an input are required after creation
        ef = utils.get_or_raise(ipcc.BuildingEmissionFactor, {"building_type": module.building_type}, f"Could not find Building EF for {module.building_type}")

        inputs_w = [
            ef.value,
            module.ef_t2_w,
            module.area_m2_w,
            project.implementation_years,
            project.capitalization_years,
            activity.change_rate.name,
        ]

        math_w = MathRoads(*inputs_w)
        math_w.calculate_emissions()

        inputs_wo = [
            ef.value,
            module.ef_t2_wo,
            module.area_m2_wo,
            project.implementation_years,
            project.capitalization_years,
            activity.change_rate.name,
        ]

        math_wo = MathRoads(*inputs_wo)
        math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)


class RoadCalculator(BaseCalculator):
    """
    Calculator for buildings and roads.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Building module.
        """

        module: Road = self.data
        parent: Settlement = module.parent
        activity: Activity = parent.activity
        project: Project = activity.project

        math_w = None
        math_wo = None

        ef = utils.get_or_raise(ipcc.RoadEmissionFactor, {"road_type": module.road_type}, f"Could not find Road EF for {module.road_type.name}")

        # TODO: Tell Peter to add this to the model
        area = module.length_km_w * module.width_m_start

        inputs_w = [
            ef.value,
            module.ef_t2_w,
            area,
            project.implementation_years,
            project.capitalization_years,
            activity.change_rate.name,
        ]

        math_w = MathRoads(*inputs_w)
        math_w.calculate_emissions()

        area = module.length_km_wo * module.width_m_start

        inputs_wo = [
            ef.value,
            module.ef_t2_wo,
            area,
            project.implementation_years,
            project.capitalization_years,
            activity.change_rate.name,
        ]

        math_wo = MathRoads(*inputs_wo)
        math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)


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
        region: Region = project.country.region

        return

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Livestock module.
        """
        log.debug("START LivestockCalculator.calculate")

        module: Livestock = self.data
        activity: Activity = module.activity
        project: Project = activity.project
        country: Country = project.country

        climate: Climate = activity.climate_t2 or project.climate
        moisture: Moisture = activity.moisture_t2 or project.moisture
        region: Region = project.country.region

        LEACHING_MULTI = LivestockParameter.objects.get(name="LEACHING_MULTIPLIER").value
        volatilization_multi = ipcc.ManureManagementVolatilizationMultiplier.objects.get(moisture=moisture)

        print("emission type", utils.EmissionTypes.CH4.value)
        print("livestock category type", module.livestock_category_type)
        print("livestock production type", module.livestock_production_type_start)
        print("climate", climate)
        print("moisture", moisture)
        print("IPCC Region", country.ipcc_region)
        print("manure management type", utils.ManureManagementTypes.PRP.value)

        # TAM Values

        try:
            tam_ch4_start = ipcc.LivestockTAM.objects.get(
                livestock_production_type=module.livestock_production_type_start,
                livestock_category_type=module.livestock_category_type,
                ipcc_region=country.ipcc_region,
            )
        except ipcc.LivestockTAM.DoesNotExist:
            raise ValueError(f"Could not find TAM (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        try:
            tam_ch4_w = ipcc.LivestockTAM.objects.get(
                livestock_production_type=module.livestock_production_type_w,
                livestock_category_type=module.livestock_category_type,
                ipcc_region=country.ipcc_region,
            )
        except ipcc.LivestockTAM.DoesNotExist:
            raise ValueError(f"Could not find TAM (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        try:
            tam_ch4_wo = ipcc.LivestockTAM.objects.get(
                livestock_production_type=module.livestock_production_type_wo,
                livestock_category_type=module.livestock_category_type,
                ipcc_region=country.ipcc_region,
            )
        except ipcc.LivestockTAM.DoesNotExist:
            raise ValueError(f"Could not find TAM (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        # VSER Values

        try:
            vser_ch4_start = ipcc.LivestockVSER.objects.get(
                livestock_production_type=module.livestock_production_type_start,
                livestock_category_type=module.livestock_category_type,
                ipcc_region=country.ipcc_region,
            )
        except ipcc.LivestockVSER.DoesNotExist:
            raise ValueError(f"Could not find VSER (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        try:
            vser_ch4_w = ipcc.LivestockVSER.objects.get(
                livestock_production_type=module.livestock_production_type_w,
                livestock_category_type=module.livestock_category_type,
                ipcc_region=country.ipcc_region,
            )
        except ipcc.LivestockVSER.DoesNotExist:
            raise ValueError(f"Could not find VSER (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        try:
            vser_ch4_wo = ipcc.LivestockVSER.objects.get(
                livestock_production_type=module.livestock_production_type_wo,
                livestock_category_type=module.livestock_category_type,
                ipcc_region=country.ipcc_region,
            )
        except ipcc.LivestockVSER.DoesNotExist:
            raise ValueError(f"Could not find VSER (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        # EF CH4 PRP Values

        try:
            ef_ch4_prp_start = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.CH4.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find EF CH4 PRP (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        try:
            ef_ch4_prp_w = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.CH4.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find EF CH4 PRP (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        try:
            ef_ch4_prp_wo = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.CH4.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find EF CH4 PRP (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        # EF CH4 Systems Values

        try:
            ef_ch4_systems_start = (
                ipcc.LivestockManureEF.objects.filter(
                    emission_type__name=utils.EmissionTypes.CH4.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_start,
                    climate=climate,
                    moisture=moisture,
                )
                .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
                .order_by("manure_management_type__name")
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find EF CH4 Systems (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        try:
            ef_ch4_systems_w = (
                ipcc.LivestockManureEF.objects.filter(
                    emission_type__name=utils.EmissionTypes.CH4.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_w,
                    climate=climate,
                    moisture=moisture,
                )
                .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
                .order_by("manure_management_type__name")
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find EF CH4 Systems (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        try:
            ef_ch4_systems_wo = (
                ipcc.LivestockManureEF.objects.filter(
                    emission_type__name=utils.EmissionTypes.CH4.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_wo,
                    climate=climate,
                    moisture=moisture,
                )
                .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
                .order_by("manure_management_type__name")
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find EF CH4 Systems (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ef_ch4_system_values_start = [system.value for system in ef_ch4_systems_start]
        ef_ch4_system_values_w = [system.value for system in ef_ch4_systems_w]
        ef_ch4_system_values_wo = [system.value for system in ef_ch4_systems_wo]

        # Animal Waste PRP Values

        try:
            animal_waste_prp_start = ipcc.LivestockAWMS.objects.get(
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_start,
                ipcc_region=country.ipcc_region,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockAWMS.DoesNotExist:
            raise ValueError(f"Could not find Animal Waste PRP (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        try:
            animal_waste_prp_w = ipcc.LivestockAWMS.objects.get(
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_w,
                ipcc_region=country.ipcc_region,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockAWMS.DoesNotExist:
            raise ValueError(f"Could not find Animal Waste PRP (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        try:
            animal_waste_prp_wo = ipcc.LivestockAWMS.objects.get(
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                ipcc_region=country.ipcc_region,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockAWMS.DoesNotExist:
            raise ValueError(f"Could not find Animal Waste PRP (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        ##### Animal Waste Management Systems Values #####

        try:
            animal_waste_management_systems_start = (
                ipcc.LivestockAWMS.objects.filter(
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_start,
                    ipcc_region=country.ipcc_region,
                )
                .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
                .order_by("manure_management_type__name")
            )
        except ipcc.LivestockAWMS.DoesNotExist:
            raise ValueError(f"Could not find Animal Waste Management Systems (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        try:
            animal_waste_management_systems_w = (
                ipcc.LivestockAWMS.objects.filter(
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_w,
                    ipcc_region=country.ipcc_region,
                )
                .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
                .order_by("manure_management_type__name")
            )
        except ipcc.LivestockAWMS.DoesNotExist:
            raise ValueError(f"Could not find Animal Waste Management Systems (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        try:
            animal_waste_management_systems_wo = (
                ipcc.LivestockAWMS.objects.filter(
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_wo,
                    ipcc_region=country.ipcc_region,
                )
                .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
                .order_by("manure_management_type__name")
            )
        except ipcc.LivestockAWMS.DoesNotExist:
            raise ValueError(f"Could not find Animal Waste Management Systems (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        # list comprehension to get the animal waste management systems values
        animal_waste_management_systems_values_start = [system.value for system in animal_waste_management_systems_start]
        animal_waste_management_systems_values_w = [system.value for system in animal_waste_management_systems_w]
        animal_waste_management_systems_values_wo = [system.value for system in animal_waste_management_systems_wo]

        ##### Enteric CH4 Values #####

        try:
            ch4_enteric_start = ipcc.MethaneEntericFermentationFactor.objects.get(
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_start,
                ipcc_region=country.ipcc_region,
            )
        except ipcc.MethaneEntericFermentationFactor.DoesNotExist:
            raise ValueError(f"Could not find Enteric CH4 (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        try:
            ch4_enteric_w = ipcc.MethaneEntericFermentationFactor.objects.get(
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_w,
                ipcc_region=country.ipcc_region,
            )
        except ipcc.MethaneEntericFermentationFactor.DoesNotExist:
            raise ValueError(f"Could not find Enteric CH4 (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        try:
            ch4_enteric_wo = ipcc.MethaneEntericFermentationFactor.objects.get(
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                ipcc_region=country.ipcc_region,
            )
        except ipcc.MethaneEntericFermentationFactor.DoesNotExist:
            raise ValueError(f"Could not find Enteric CH4 (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {country.ipcc_region.name}")

        ##### PRP N2O Direct EF Values #####

        try:
            prp_n2o_direct_ef_start = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find PRP N2O Direct EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        try:
            prp_n2o_direct_ef_w = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find PRP N2O Direct EF (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        try:
            prp_n2o_direct_ef_wo = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find PRP N2O Direct EF (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ##### PRP N2O Volatilization EF Values #####

        try:
            prp_n2o_volatilization_ef_start = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find PRP N2O Volatilization EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        try:
            prp_n2o_volatilization_ef_w = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find PRP N2O Volatilization EF (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        try:
            prp_n2o_volatilization_ef_wo = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find PRP N2O Volatilization EF (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ##### PRP N2O Leaching EF Values #####

        try:
            prp_n2o_leaching_ef_start = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find PRP N2O Leaching EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        try:
            prp_n2o_leaching_ef_w = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find PRP N2O Leaching EF (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        try:
            prp_n2o_leaching_ef_wo = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
                manure_management_type__name=utils.ManureManagementTypes.PRP.value,
            )
        except ipcc.LivestockManureEF.DoesNotExist:
            raise ValueError(f"Could not find PRP N2O Leaching EF (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ##### N2O Direct EF Values #####

        ef_n2o_direct_systems_start = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
            .order_by("manure_management_type__name")
        )
        if not ef_n2o_direct_systems_start:
            raise ValueError(f"Could not find N2O Direct EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ef_n2o_direct_systems_w = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
            .order_by("manure_management_type__name")
        )
        if not ef_n2o_direct_systems_w:
            raise ValueError(f"Could not find N2O Direct EF (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ef_n2o_direct_systems_wo = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
            .order_by("manure_management_type__name")
        )
        if not ef_n2o_direct_systems_wo:
            raise ValueError(f"Could not find N2O Direct EF (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ef_n2o_direct_systems_start = [s.value for s in ef_n2o_direct_systems_start]
        ef_n2o_direct_systems_w = [s.value for s in ef_n2o_direct_systems_w]
        ef_n2o_direct_systems_wo = [s.value for s in ef_n2o_direct_systems_wo]

        ##### N2O Volatilization EF Values #####

        ef_n2o_volatilization_systems_start = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
            .order_by("manure_management_type__name")
        )
        if not ef_n2o_volatilization_systems_start:
            raise ValueError(f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ef_n2o_volatilization_systems_w = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
            .order_by("manure_management_type__name")
        )
        if not ef_n2o_volatilization_systems_w:
            raise ValueError(f"Could not find N2O Volatilization EF (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ef_n2o_volatilization_systems_wo = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
            .order_by("manure_management_type__name")
        )
        if not ef_n2o_volatilization_systems_wo:
            raise ValueError(f"Could not find N2O Volatilization EF (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ef_n2o_volatilization_systems_start = [s.value for s in ef_n2o_volatilization_systems_start]
        ef_n2o_volatilization_systems_w = [s.value for s in ef_n2o_volatilization_systems_w]
        ef_n2o_volatilization_systems_wo = [s.value for s in ef_n2o_volatilization_systems_wo]

        ##### N2O Leaching EF Values #####

        ef_n2o_leaching_systems_start = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
            .order_by("manure_management_type__name")
        )
        if not ef_n2o_leaching_systems_start:
            raise ValueError(f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ef_n2o_leaching_systems_w = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
            .order_by("manure_management_type__name")
        )
        if not ef_n2o_leaching_systems_w:
            raise ValueError(f"Could not find N2O Leaching EF (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ef_n2o_leaching_systems_wo = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING.value,
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP.value)
            .order_by("manure_management_type__name")
        )
        if not ef_n2o_leaching_systems_wo:
            raise ValueError(f"Could not find N2O Leaching EF (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        ef_n2o_leaching_systems_start = [s.value for s in ef_n2o_leaching_systems_start]
        ef_n2o_leaching_systems_w = [s.value for s in ef_n2o_leaching_systems_w]
        ef_n2o_leaching_systems_wo = [s.value for s in ef_n2o_leaching_systems_wo]

        ##### NER Values #####

        try:
            ner_start = ipcc.LivestockNER.objects.get(
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_start,
                ipcc_region=project.country.ipcc_region,
            )
        except ipcc.LivestockNER.DoesNotExist:
            raise ValueError(f"Could not find NER (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {project.country.ipcc_region.name}")

        try:
            ner_w = ipcc.LivestockNER.objects.get(
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_w,
                ipcc_region=project.country.ipcc_region,
            )
        except ipcc.LivestockNER.DoesNotExist:
            raise ValueError(f"Could not find NER (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {project.country.ipcc_region.name}")

        try:
            ner_wo = ipcc.LivestockNER.objects.get(
                livestock_category_type=module.livestock_category_type,
                livestock_production_type=module.livestock_production_type_wo,
                ipcc_region=project.country.ipcc_region,
            )
        except ipcc.LivestockNER.DoesNotExist:
            raise ValueError(f"Could not find NER (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {project.country.ipcc_region.name}")

        ##### Complementary Manure Management Values #####

        n2o_ef_t2_start = None
        n2o_volatilization_ef_t2_start = None
        n2o_leaching_ef_t2_start = None
        ch4_ef_t2_start = None
        if module.complementary_manure_management_type_start is not None:

            try:
                n2o_ef_t2_start = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.N2O.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_start,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_start,
                )
                if n2o_ef_t2_start:
                    n2o_ef_t2_start = n2o_ef_t2_start.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find N2O EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            try:
                n2o_volatilization_ef_t2_start = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_start,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_start,
                )
                if n2o_volatilization_ef_t2_start:
                    n2o_volatilization_ef_t2_start = n2o_volatilization_ef_t2_start.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find N2O Volatilization EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            try:
                n2o_leaching_ef_t2_start = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.N2O_LEACHING.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_start,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_start,
                )
                if n2o_leaching_ef_t2_start:
                    n2o_leaching_ef_t2_start = n2o_leaching_ef_t2_start.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find N2O Leaching EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            try:
                ch4_ef_t2_start = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.CH4.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_start,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_start,
                )
                if ch4_ef_t2_start:
                    ch4_ef_t2_start = ch4_ef_t2_start.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find CH4 EF (START) for {module.livestock_production_type_start.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        n2o_ef_t2_w = None
        n2o_volatilization_ef_t2_w = None
        n2o_leaching_ef_t2_w = None
        ch4_ef_t2_w = None
        if module.complementary_manure_management_type_w is not None:
            try:
                n2o_ef_t2_w = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.N2O.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_w,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_w,
                )
                if n2o_ef_t2_w:
                    n2o_ef_t2_w = n2o_ef_t2_w.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find N2O EF (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            try:
                n2o_volatilization_ef_t2_w = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_w,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_w,
                )
                if n2o_volatilization_ef_t2_w:
                    n2o_volatilization_ef_t2_w = n2o_volatilization_ef_t2_w.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find N2O Volatilization EF (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            try:
                n2o_leaching_ef_t2_w = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.N2O_LEACHING.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_w,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_w,
                )
                if n2o_leaching_ef_t2_w:
                    n2o_leaching_ef_t2_w = n2o_leaching_ef_t2_w.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find N2O Leaching EF (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            try:
                ch4_ef_t2_w = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.CH4.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_w,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_w,
                )
                if ch4_ef_t2_w:
                    ch4_ef_t2_w = ch4_ef_t2_w.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find CH4 EF (WITH) for {module.livestock_production_type_w.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        n2o_ef_t2_wo = None
        n2o_volatilization_ef_t2_wo = None
        n2o_leaching_ef_t2_wo = None
        ch4_ef_t2_wo = None
        if module.complementary_manure_management_type_wo is not None:
            try:
                n2o_ef_t2_wo = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.N2O.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_wo,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_wo,
                )
                if n2o_ef_t2_wo:
                    n2o_ef_t2_wo = n2o_ef_t2_wo.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find N2O EF (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            try:
                n2o_volatilization_ef_t2_wo = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_wo,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_wo,
                )
                if n2o_volatilization_ef_t2_wo:
                    n2o_volatilization_ef_t2_wo = n2o_volatilization_ef_t2_wo.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find N2O Volatilization EF (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            try:
                n2o_leaching_ef_t2_wo = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.N2O_LEACHING.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_wo,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_wo,
                )
                if n2o_leaching_ef_t2_wo:
                    n2o_leaching_ef_t2_wo = n2o_leaching_ef_t2_wo.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find N2O Leaching EF (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

            try:
                ch4_ef_t2_wo = ipcc.LivestockManureEF.objects.get(
                    emission_type__name=utils.EmissionTypes.CH4.value,
                    livestock_category_type=module.livestock_category_type,
                    livestock_production_type=module.livestock_production_type_wo,
                    climate=climate,
                    moisture=moisture,
                    manure_management_type=module.complementary_manure_management_type_wo,
                )
                if ch4_ef_t2_wo:
                    ch4_ef_t2_wo = ch4_ef_t2_wo.value
            except ipcc.LivestockManureEF.DoesNotExist:
                raise ValueError(f"Could not find CH4 EF (WITHOUT) for {module.livestock_production_type_wo.name}, {module.livestock_category_type.name}, {climate.name}, {moisture.name}")

        math_w = None
        math_wo = None

        if module.is_with():
            log.debug("Calculating emissions for WITH")

            self.inputs_w = [
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                project.gw_potential.ch4,
                module.heads_number_start,
                module.heads_number_w,
                ch4_enteric_start.value,
                ch4_enteric_w.value,
                module.enteric_fermentation_t2_start,
                module.enteric_fermentation_t2_w,
                ef_ch4_prp_start.value,
                ef_ch4_prp_w.value,
                animal_waste_prp_start.value,
                animal_waste_prp_w.value,
                module.prp_percentage_t2_start,
                module.prp_percentage_t2_w,
                ef_ch4_system_values_start,
                ef_ch4_system_values_w,
                module.prp_ch4_t2_start,
                module.prp_ch4_t2_w,
                ch4_ef_t2_start,  ###
                ch4_ef_t2_w,
                module.emission_factor_ch4_t2_start,
                module.emission_factor_ch4_t2_w,
                animal_waste_management_systems_values_start,
                animal_waste_management_systems_values_w,
                tam_ch4_start.value,
                tam_ch4_w.value,
                vser_ch4_start.value,
                vser_ch4_w.value,
                prp_n2o_direct_ef_start.value,
                prp_n2o_direct_ef_w.value,
                ef_n2o_direct_systems_start,
                ef_n2o_direct_systems_w,
                module.prp_n2o_t2_start,
                module.prp_n2o_t2_w,
                n2o_ef_t2_start,  ###
                n2o_ef_t2_w,
                module.emission_factor_n2o_t2_start,
                module.emission_factor_n2o_t2_w,
                ner_start.value,
                ner_w.value,
                prp_n2o_volatilization_ef_start.value,
                prp_n2o_volatilization_ef_w.value,
                ef_n2o_volatilization_systems_start,
                ef_n2o_volatilization_systems_w,
                module.prp_n2o_t2_start,  # TODO: Maybe add specific t2 for volatilization
                module.prp_n2o_t2_w,
                n2o_volatilization_ef_t2_start,  ###
                n2o_volatilization_ef_t2_w,
                module.emission_factor_n2o_t2_start,
                module.emission_factor_n2o_t2_w,
                prp_n2o_leaching_ef_start.value,
                prp_n2o_leaching_ef_w.value,
                ef_n2o_leaching_systems_start,
                ef_n2o_leaching_systems_w,
                module.prp_n2o_t2_start,  # TODO: Maybe add specific t2 for leaching
                module.prp_n2o_t2_w,
                n2o_leaching_ef_t2_start,  ###
                n2o_leaching_ef_t2_w,
                module.emission_factor_n2o_t2_start,
                module.emission_factor_n2o_t2_w,
                project.gw_potential.n2o,
                volatilization_multi.value,
                LEACHING_MULTI,
            ]

            log.debug(f"Inputs for WITH: {self.inputs_w}")

            math_w = MathLivestock(*self.inputs_w)
            math_w.calculate_emissions()

        if module.is_without():
            log.debug("Calculating emissions for WITHOUT")

            self.inputs_wo = [
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                project.gw_potential.ch4,
                module.heads_number_start,
                module.heads_number_wo,
                ch4_enteric_start.value,
                ch4_enteric_wo.value,
                module.enteric_fermentation_t2_start,
                module.enteric_fermentation_t2_wo,
                ef_ch4_prp_start.value,
                ef_ch4_prp_wo.value,
                animal_waste_prp_start.value,
                animal_waste_prp_wo.value,
                module.prp_percentage_t2_start,
                module.prp_percentage_t2_wo,
                ef_ch4_system_values_start,
                ef_ch4_system_values_wo,
                module.prp_ch4_t2_start,
                module.prp_ch4_t2_wo,
                ch4_ef_t2_start,  ###
                ch4_ef_t2_wo,
                module.emission_factor_ch4_t2_start,
                module.emission_factor_ch4_t2_wo,
                animal_waste_management_systems_values_start,
                animal_waste_management_systems_values_wo,
                tam_ch4_start.value,
                tam_ch4_wo.value,
                vser_ch4_start.value,
                vser_ch4_wo.value,
                prp_n2o_direct_ef_start.value,
                prp_n2o_direct_ef_wo.value,
                ef_n2o_direct_systems_start,
                ef_n2o_direct_systems_wo,
                module.prp_n2o_t2_start,
                module.prp_n2o_t2_wo,
                n2o_ef_t2_start,  ###
                n2o_ef_t2_wo,
                module.emission_factor_n2o_t2_start,
                module.emission_factor_n2o_t2_wo,
                ner_start.value,
                ner_wo.value,
                prp_n2o_volatilization_ef_start.value,
                prp_n2o_volatilization_ef_wo.value,
                ef_n2o_volatilization_systems_start,
                ef_n2o_volatilization_systems_wo,
                module.prp_n2o_t2_start,  # TODO: Maybe add specific t2 for volatilization
                module.prp_n2o_t2_wo,
                n2o_volatilization_ef_t2_start,  ###
                n2o_volatilization_ef_t2_wo,
                module.emission_factor_n2o_t2_start,
                module.emission_factor_n2o_t2_wo,
                prp_n2o_leaching_ef_start.value,
                prp_n2o_leaching_ef_wo.value,
                ef_n2o_leaching_systems_start,
                ef_n2o_leaching_systems_wo,
                module.prp_n2o_t2_start,  # TODO: Maybe add specific t2 for leaching
                module.prp_n2o_t2_wo,
                n2o_leaching_ef_t2_start,  ###
                n2o_leaching_ef_t2_wo,
                module.emission_factor_n2o_t2_start,
                module.emission_factor_n2o_t2_wo,
                project.gw_potential.n2o,
                volatilization_multi.value,
                LEACHING_MULTI,
            ]
            log.debug(f"Inputs for WITHOUT: {self.inputs_wo}")

            math_wo = MathLivestock(*self.inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        log.debug("WITH breakdown")
        results_w.breakdown(by=BreakdownTypes.ACTIVITY)
        log.debug("WITHOUT breakdown")
        results_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug(f"Results for WITH: {results_w}")
        return (results_w, results_wo)

    def defaults(self) -> DefaultData:
        self.calculate()

        module: Livestock = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if is_with(module):
            math_w = MathLivestock(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.start)
            defaults_w.update(math_w_defaults.other)

        if is_without(module):
            math_wo = MathLivestock(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.start)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class IrrigationCalculator(BaseCalculator):
    def calculate(self) -> list[Result]:
        module: Irrigation = self.data
        res_w = MathResult(
            module.activity.project.implementation_years,
            module.activity.project.capitalization_years,
        )
        res_wo = MathResult(
            module.activity.project.implementation_years,
            module.activity.project.capitalization_years,
        )
        for system in module.irrigation_systems.all():
            r_w, r_wo = IrrigationSystemCalculator(system).calculate()
            res_w += r_w
            res_wo += r_wo

        for phase in module.irrigation_phases.all():
            r_w, r_wo = IrrigationPhaseCalculator(phase).calculate()
            res_w += r_w
            res_wo += r_wo

        return (res_w, res_wo)

    def get_defaults(self, input: Module) -> dict:
        return super().get_defaults(input)

    def defaults(self) -> DefaultData:
        return super().defaults()


class IrrigationSystemCalculator(BaseCalculator):
    """
    Calculates the emissions of the irrigation system
    """

    def calculate(self) -> list[Result]:
        """
        Calculates the emissions of the irrigation system
        """

        module: IrrigationSystem = self.data
        activity: Activity = module.parent.activity
        project: Project = activity.project

        try:
            ef = ipcc.IrrigationSystemData.objects.get(irrigation_system_type=module.irrigation_system_type)
        except ipcc.IrrigationSystemData.DoesNotExist:
            raise ValueError(f"Could not find EF for {module.irrigation_system_type.name}")

        math_w = None
        math_wo = None

        inputs_w = [
            ef.value,
            module.ef_t2_start,
            module.ha_start,
            module.ha_w,
            project.implementation_years,
            project.capitalization_years,
            activity.change_rate.name,
        ]

        math_w = NewIrrigation(*inputs_w)
        math_w.calculate_emissions()

        inputs_wo = [
            ef.value,
            module.ef_t2_wo,
            module.ha_start,
            module.ha_wo,
            project.implementation_years,
            project.capitalization_years,
            activity.change_rate.name,
        ]

        math_wo = NewIrrigation(*inputs_wo)
        math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple

    def get_defaults(self, calculate=False) -> dict:

        module: IrrigationSystem = self.data
        activity: Activity = module.parent.activity

        try:
            self.ef = ipcc.IrrigationSystemData.objects.get(irrigation_system_type=module.irrigation_system_type)
        except ipcc.IrrigationSystemData.DoesNotExist:
            raise ValueError(f"Could not find EF for {module.irrigation_system_type.name}")

    def defaults(self) -> DefaultData:

        return super().defaults()


class IrrigationPhaseCalculator(BaseCalculator):
    def calculate(self) -> list[Result]:
        module: IrrigationPhase = self.data
        activity: Activity = module.parent.activity
        project: Project = activity.project

        try:
            ef = ipcc.IrrigationPhaseData.objects.get(fuel_type=module.fuel_type)
        except ipcc.IrrigationPhaseData.DoesNotExist:
            raise ValueError(f"Could not find EF for {module.fuel_type.name}")

        try:
            energy_db = ipcc.EnergyDefaultEmissionFactor.objects.get(fuel_type=module.fuel_type)
        except ipcc.EnergyDefaultEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Energy Default Emission Factor for {module.fuel_type.name}")

        try:
            pressure = ipcc.IrrigationPressureRequirement.objects.get(irrigation_system_type=module.irrigation_system_type)
        except ipcc.IrrigationPressureRequirement.DoesNotExist:
            raise ValueError(f"Could not find Pressure Requirement for {module.irrigation_system_type.name}")

        try:
            erh_electricity = IrrigationParameter.objects.get(name="ERH_ELECTRICITY").value if module.fuel_type.name == "Electricity" else None
        except IrrigationParameter.DoesNotExist:
            raise ValueError(f"Could not find ERH_ELECTRICITY")

        try:
            transportation_loss = IrrigationParameter.objects.get(name="TRANSPORTATION_LOSS")
        except IrrigationParameter.DoesNotExist:
            raise ValueError(f"Could not find TRANSPORTATION_LOSS")

        try:
            pumping_efficiency = IrrigationParameter.objects.get(name="PUMPING_EFFICIENCY")
        except IrrigationParameter.DoesNotExist:
            raise ValueError(f"Could not find PUMPING_EFFICIENCY")

        math_start = None
        math_w = None
        math_wo = None

        inputs_start = [
            ef.emission_factor,
            module.ef_t2_start,
            module.total_dynamic_head_t2,
            pressure.avg_pressure,
            module.average_pressure_t2,
            pumping_efficiency.value,
            module.pumping_efficiency_t2_start,
            erh_electricity,
            energy_db.net_calorific_value,
            energy_db.density,
            module.well_depth,
            module.ha_start,
            0,
            activity.change_rate.name,
            project.implementation_years,
            project.capitalization_years,
            transportation_loss.value if module.fuel_type.name == "Electricity" else 0,
            module.gross_irrigation_water_start,
        ]

        math_start = OperationPhaseIrrigation(*inputs_start)
        math_start.calculate_emissions()

        inputs_w = [
            ef.emission_factor,
            module.ef_t2_w,
            module.total_dynamic_head_t2,
            pressure.avg_pressure,
            module.average_pressure_t2,
            pumping_efficiency.value,
            module.pumping_efficiency_t2_w,
            erh_electricity,
            energy_db.net_calorific_value,
            energy_db.density,
            module.well_depth,
            0,
            module.ha_w,
            activity.change_rate.name,
            project.implementation_years,
            project.capitalization_years,
            transportation_loss.value if module.fuel_type.name == "Electricity" else 0,
            module.gross_irrigation_water_w,
        ]

        math_w = OperationPhaseIrrigation(*inputs_w)
        math_w.calculate_emissions()

        inputs_wo = [
            ef.emission_factor,
            module.ef_t2_wo,
            module.total_dynamic_head_t2,
            pressure.avg_pressure,
            module.average_pressure_t2,
            pumping_efficiency.value,
            module.pumping_efficiency_t2_wo,
            erh_electricity,
            energy_db.net_calorific_value,
            energy_db.density,
            module.well_depth,
            0,
            module.ha_wo,
            activity.change_rate.name,
            project.implementation_years,
            project.capitalization_years,
            transportation_loss.value if module.fuel_type.name == "Electricity" else 0,
            module.gross_irrigation_water_wo,
        ]

        math_wo = OperationPhaseIrrigation(*inputs_wo)
        math_wo.calculate_emissions()

        results_start = math_start.result if math_start else MathResult(project.implementation_years, project.capitalization_years)
        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w + results_start, results_wo + results_start)

        return results_tuple

    def get_defaults(self, input: Module) -> dict:
        return super().get_defaults(input)

    def defaults(self) -> DefaultData:
        return super().defaults()


class CoastalWetlandCalculator(BaseCalculator):
    """
    Calculates the emissions of the coastal wetland
    """

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)

    def calculate(self) -> Result:
        """
        Calculates the emissions of the coastal wetland
        """

        module: CoastalWetland = self.data
        project: Project = module.activity.project

        cm = {
            "climate": project.climate,
            "moisture": project.moisture,
        }

        soil_type_name = module.soil_type_t2.name if module.soil_type_t2 else "Mineral"

        try:
            agb = ipcc.CoastalAGB.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.CoastalAGB.DoesNotExist:
            raise ValueError(f"Could not find AGB for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            bgb = ipcc.CoastalBGB.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.CoastalBGB.DoesNotExist:
            raise ValueError(f"Could not find BGB for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            litter = ipcc.CoastalLitter.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.CoastalLitter.DoesNotExist:
            raise ValueError(f"Could not find Litter for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            dw = ipcc.CoastalDeadwood.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.CoastalDeadwood.DoesNotExist:
            raise ValueError(f"Could not find Deadwood for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            soil_1m = ipcc.DefaultSoilCarbonStock1Meter.objects.get(**cm, land_use_type=module.land_use_type, soil_type__name=soil_type_name)
        except ipcc.DefaultSoilCarbonStock1Meter.DoesNotExist:
            raise ValueError(f"Could not find Soil 1m for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}, {soil_type_name}")

        try:
            ef_drainage = ipcc.DrainageEmissionFactor.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.DrainageEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find EF Drainage for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            pc_c_lost_excavation = CoastalWetlandParameter.objects.get(name="PERCENTAGE_C_LOST_EXCAVATION")
        except CoastalWetlandParameter.DoesNotExist:
            raise ValueError(f"Could not find PC C Lost Excavation")

        try:
            rewetting_c = ipcc.RewettingCarbonFactor.objects.get(**cm, land_use_type=module.land_use_type, soil_type__name=soil_type_name)
        except ipcc.RewettingCarbonFactor.DoesNotExist:
            raise ValueError(f"Could not find Rewetting C for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            rewetting_ch4 = ipcc.RewettingMethaneFactor.objects.get(**cm, land_use_type=module.land_use_type)
        except ipcc.RewettingMethaneFactor.DoesNotExist:
            raise ValueError(f"Could not find Rewetting CH4 for {module.land_use_type.name}, {project.climate.name}, {project.moisture.name}")

        math_w = None
        math_wo = None

        if module.is_with():
            self.inputs_w = [
                module.area,
                module.area_under_drainage_start,
                module.area_under_drainage_w,
                module.activity.change_rate.name,
                project.implementation_years,
                project.capitalization_years,
                agb.value,
                bgb.value,
                litter.value,
                dw.value,
                soil_1m.value,
                ef_drainage.value,
                module.agb_t2_w,
                module.bgb_t2_w,
                module.litter_t2_w,
                module.deadwood_t2_w,
                module.soc_t2_w,
                module.drainage_ef_t2_w,
                module.drained_area_excavated_start,
                module.drained_area_excavated_w,
                module.area_w_restored_vegetation_start,
                module.area_w_restored_vegetation_w,
                pc_c_lost_excavation.value,
                module.pc_c_lost_after_excavation_t2_w,
                rewetting_c.value,
                rewetting_ch4.value,
                module.co2_rewetting_t2_start,
                module.ch4_rewetting_t2_w,
                module.avg_salinity_t2.value if module.avg_salinity_t2 else None,
                project.gw_potential.ch4,
            ]

            math_w = MathCoastalWetland(*self.inputs_w)
            math_w.calculate_emissions()

        if module.is_without():
            self.inputs_wo = [
                module.area,
                module.area_under_drainage_start,
                module.area_under_drainage_wo,
                module.activity.change_rate.name,
                project.implementation_years,
                project.capitalization_years,
                agb.value,
                bgb.value,
                litter.value,
                dw.value,
                soil_1m.value,
                ef_drainage.value,
                module.agb_t2_wo,
                module.bgb_t2_wo,
                module.litter_t2_wo,
                module.deadwood_t2_wo,
                module.soc_t2_wo,
                module.drainage_ef_t2_wo,
                module.drained_area_excavated_start,
                module.drained_area_excavated_wo,
                module.area_w_restored_vegetation_start,
                module.area_w_restored_vegetation_wo,
                pc_c_lost_excavation.value,
                module.pc_c_lost_after_excavation_t2_wo,
                rewetting_c.value,
                rewetting_ch4.value,
                module.co2_rewetting_t2_wo,
                module.ch4_rewetting_t2_wo,
                module.avg_salinity_t2.value if module.avg_salinity_t2 else None,
                project.gw_potential.ch4,
            ]

            math_wo = MathCoastalWetland(*self.inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        log.debug("WITH breakdown")
        results_w.breakdown(by=BreakdownTypes.ACTIVITY)

        log.debug("WITHOUT breakdown")
        results_wo.breakdown(by=BreakdownTypes.ACTIVITY)

        results_tuple = (results_w, results_wo)

        return results_tuple

    def defaults(self) -> DefaultData:
        self.calculate()

        module: CoastalWetland = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if module.is_luc_remaining_same():
            math_start = MathCoastalWetland(*self.inputs_start_w)
            math_start_defaults = math_start.evaluate_tier_2_defaults()
            defaults_start.update(math_start_defaults.start)
            defaults_start.update(math_start_defaults.other)
        elif module.is_business_as_usual():
            math_start_wo = MathCoastalWetland(*self.inputs_start_wo)
            math_start_wo_defaults = math_start_wo.evaluate_tier_2_defaults()
            defaults_start.update(math_start_wo_defaults.start)
            defaults_start.update(math_start_wo_defaults.other)

        if module.is_with():
            math_w = MathCoastalWetland(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.start)
            defaults_w.update(math_w_defaults.other)

        if module.is_without():
            math_wo = MathCoastalWetland(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.start)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class WaterbodyCalculator(BaseCalculator):
    """
    Calculator for waterbody modules.
    """

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)

    def calculate(self) -> Result:
        """
        Calculate emissions for a single Waterbody module.
        """
        module: Waterbody = self.data
        project = module.activity.project

        try:
            methane_emission_factor = ipcc.OtherConstructedWaterbodiesEmissionFactor.objects.get(climate=project.climate, moisture=project.moisture, waterbody_type=module.waterbody_type)
        except ipcc.OtherConstructedWaterbodiesEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Methane Emission Factor for {module.waterbody_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            trophic_state_start = ipcc.TrophicStateFactor.objects.get(trophic_type=module.trophic_type_start)
        except ipcc.TrophicStateFactor.DoesNotExist:
            raise ValueError(f"Could not find Trophic State Factor for {module.trophic_type_start.name}")

        try:
            trophic_state_w = ipcc.TrophicStateFactor.objects.get(trophic_type=module.trophic_type_w)
        except ipcc.TrophicStateFactor.DoesNotExist:
            raise ValueError(f"Could not find Trophic State Factor for {module.trophic_type_w.name}")

        try:
            trophic_state_wo = ipcc.TrophicStateFactor.objects.get(trophic_type=module.trophic_type_wo)
        except ipcc.TrophicStateFactor.DoesNotExist:
            raise ValueError(f"Could not find Trophic State Factor for {module.trophic_type_wo.name}")

        math_start = None
        math_w = None
        math_wo = None

        inputs_start = [
            module.area,
            0,
            trophic_state_start.value,
            methane_emission_factor.value,
            module.alpha_t2_start,
            0,
            module.ch4_ef_t2_start,
            0,
            project.gw_potential.ch4,
            project.capitalization_years,
            project.implementation_years,
            module.activity.change_rate.name,
            module.mean_annual_t2_start,
            0,
        ]

        math_start = MathWaterbodies(*inputs_start)
        math_start.calculate_emissions()

        if module.is_with():
            inputs_w = [
                0,
                module.area,
                trophic_state_w.value,
                methane_emission_factor.value,
                module.alpha_t2_start,
                module.alpha_t2_w,
                module.ch4_ef_t2_start,
                module.ch4_ef_t2_w,
                project.gw_potential.ch4,
                project.capitalization_years,
                project.implementation_years,
                module.activity.change_rate.name,
                module.mean_annual_t2_start,
                module.mean_annual_t2_w,
            ]

            math_w = MathWaterbodies(*inputs_w)
            math_w.calculate_emissions()

        if module.is_without():
            inputs_wo = [
                0,
                module.area,
                trophic_state_wo.value,
                methane_emission_factor.value,
                module.alpha_t2_start,
                module.alpha_t2_wo,
                module.ch4_ef_t2_start,
                module.ch4_ef_t2_wo,
                project.gw_potential.ch4,
                project.capitalization_years,
                project.implementation_years,
                module.activity.change_rate.name,
                module.mean_annual_t2_start,
                module.mean_annual_t2_wo,
            ]

            math_wo = MathWaterbodies(*inputs_wo)
            math_wo.calculate_emissions()

        results_start = math_start.result if math_start else MathResult(project.implementation_years, project.capitalization_years)
        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w + results_start, results_wo + results_start)

        return results_tuple

    def defaults(self) -> DefaultData:
        return super().defaults()


class OrganicSoilCalculator(BaseCalculator):

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)

    def calculate(self) -> Result:
        input: OrganicSoil = self.data
        project: Project = input.activity.project
        luc: LandUseChange = input.land_use_change

        area_affected_by_module = 0
        module_type_start = None
        module_type_w = None
        module_type_wo = None

        if luc:
            module_type_start = luc.module_type_start.name
            module_type_w = luc.module_type_w.name
            module_type_wo = luc.module_type_wo.name
            area_affected_by_module = luc.area
        else:
            parent_module, parent_module_type = utils.find_organic_soil_parent_module(input)
            module_type_start = module_type_w = module_type_wo = parent_module_type.name

            area_affected_by_module = 0 if module_type_start == "ForestManagement" else parent_module.area

        cm = {
            "climate": project.climate,
            "moisture": project.moisture,
        }

        ##### Organic Soil Inputs #####

        try:
            ef_onsite_start = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_start, peat_type=input.peat_type, site_location_type__name="On-Site")
        except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find EF On-Site Start for {module_type_start}, {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            ef_onsite_w = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_w, peat_type=input.peat_type, site_location_type__name="On-Site")
        except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find EF On-Site W for {module_type_w}, {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            ef_onsite_wo = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_wo, peat_type=input.peat_type, site_location_type__name="On-Site")
        except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find EF On-Site WO for {module_type_wo}, {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            ef_offsite_start = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_start, peat_type=input.peat_type, site_location_type__name="Off-Site")
        except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find EF Off-Site Start for {module_type_start}, {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            ef_offsite_w = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_w, peat_type=input.peat_type, site_location_type__name="Off-Site")
        except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find EF Off-Site W for {module_type_w}, {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            ef_offsite_wo = ipcc.OrganicSoilDrainageEmissionFactor.objects.get(**cm, module_type__name=module_type_wo, peat_type=input.peat_type, site_location_type__name="Off-Site")
        except ipcc.OrganicSoilDrainageEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find EF Off-Site WO for {module_type_wo}, {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        fire_used_w = input.fire_type_w is not None
        fire_used_wo = input.fire_type_wo is not None

        if fire_used_w:
            try:
                dry_matter_w = ipcc.OrganicSoilFuelConsumption.objects.get(**cm, fire_type=input.fire_type_w)
            except ipcc.OrganicSoilFuelConsumption.DoesNotExist:
                raise ValueError(f"Could not find Dry Matter W for {input.fire_type_w.name}, {project.climate.name}, {project.moisture.name}")

        if fire_used_wo:
            try:
                dry_matter_wo = ipcc.OrganicSoilFuelConsumption.objects.get(**cm, fire_type=input.fire_type_wo)
            except ipcc.OrganicSoilFuelConsumption.DoesNotExist:
                raise ValueError(f"Could not find Dry Matter WO for {input.fire_type_wo.name}, {project.climate.name}, {project.moisture.name}")

        try:
            fire_ref = ipcc.OrganicSoilGefEmissionFactor.objects.get(**cm)
        except ipcc.OrganicSoilGefEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Fire Reference for {project.climate.name}, {project.moisture.name}")

        try:
            rewetting_start = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=input.peat_type, module_type__name=module_type_start)
        except ipcc.OrganicSoilRewettingEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Rewetting Start for {input.peat_type.name}, {module_type_start}, {project.climate.name}, {project.moisture.name}")

        try:
            rewetting_w = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=input.peat_type, module_type__name=module_type_w)
        except ipcc.OrganicSoilRewettingEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Rewetting W for {input.peat_type.name}, {module_type_w}, {project.climate.name}, {project.moisture.name}")

        try:
            rewetting_wo = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=input.peat_type, module_type__name=module_type_wo)
        except ipcc.OrganicSoilRewettingEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Rewetting WO for {input.peat_type.name}, {module_type_wo}, {project.climate.name}, {project.moisture.name}")

        ##### Peat Extraction Inputs #####

        try:
            onsite_ef_w = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=input.peat_type, site_location_type__name="On-Site")
        except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find On-Site EF W for {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            onsite_ef_wo = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=input.peat_type, site_location_type__name="On-Site")
        except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find On-Site EF WO for {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            offsite_ef_w = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=input.peat_type, site_location_type__name="Off-Site")
        except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Off-Site EF W for {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            offsite_ef_wo = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=input.peat_type, site_location_type__name="Off-Site")
        except ipcc.PeatExtractionEmissionFactor.DoesNotExist:
            raise ValueError(f"Could not find Off-Site EF WO for {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            conversion_factor_w = ipcc.PeatExtractionConversionFactor.objects.get(**cm, peat_type=input.peat_type)
        except ipcc.PeatExtractionConversionFactor.DoesNotExist:
            raise ValueError(f"Could not find Conversion Factor W for {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        try:
            conversion_factor_wo = ipcc.PeatExtractionConversionFactor.objects.get(**cm, peat_type=input.peat_type)
        except ipcc.PeatExtractionConversionFactor.DoesNotExist:
            raise ValueError(f"Could not find Conversion Factor WO for {input.peat_type.name}, {project.climate.name}, {project.moisture.name}")

        ##### Calculate Emissions #####

        total_results_w = MathResult(project.implementation_years, project.capitalization_years)
        total_results_wo = MathResult(project.implementation_years, project.capitalization_years)

        organic_soil_math_w = None
        organic_soil_math_wo = None
        peat_extraction_math_w = None
        peat_extraction_math_wo = None

        organic_soil_inputs_w = [
            input.fire_type_w is not None,
            input.soil_fire_periodicity_w,
            area_affected_by_module,
            dry_matter_w.value if fire_used_w else None,
            input.mean_dry_matter_t2_w,
            input.soil_fire_impact_percentage_w,
            fire_ref.co2,
            input.fire_on_soil_co2_t2_w,
            fire_ref.co,
            input.fire_on_soil_co_t2_w,
            fire_ref.ch4,
            input.fire_on_soil_ch4_t2_w,
            project.gw_potential.ch4,
            input.activity.change_rate.name,
            project.implementation_years,
            project.capitalization_years,
            project.gw_potential.n2o,
            ef_offsite_start.doc,
            input.offsite_doc_drainge_t2_start,
            input.drainage_area_start,
            input.drainage_area_w,
            ef_onsite_start.co2,
            input.onsite_co2_drainge_t2_start,
            input.ditches_area_start,
            input.ditches_area_w,
            ef_onsite_start.ch4,
            input.onsite_ch4_drainge_t2_start,
            ef_offsite_start.ch4,
            input.offsite_ch4_drainge_t2_start,
            ef_onsite_start.n2o,
            input.onsite_n2o_drainge_t2_start,
            ef_offsite_w.doc,
            input.offsite_doc_drainge_t2_start,
            ef_onsite_w.co2,
            input.onsite_co2_drainge_t2_w,
            ef_onsite_w.ch4,
            input.onsite_ch4_drainge_t2_w,
            ef_offsite_w.ch4,
            input.offsite_ch4_drainge_t2_w,
            ef_onsite_w.n2o,
            input.onsite_n2o_drainge_t2_w,
            rewetting_start.doc,
            input.offsite_doc_rewetting_t2_start,
            rewetting_start.co2,
            input.onsite_co2_rewetting_t2_start,
            rewetting_start.ch4,
            input.onsite_ch4_rewetting_t2_start,
            rewetting_start.n2o,
            input.onsite_n2o_rewetting_t2_start,
            rewetting_w.doc,
            input.offsite_doc_rewetting_t2_w,
            rewetting_w.co2,
            input.onsite_co2_rewetting_t2_w,
            rewetting_w.ch4,
            input.onsite_ch4_rewetting_t2_w,
            rewetting_w.n2o,
            input.onsite_n2o_rewetting_t2_w,
            area_affected_by_module,
        ]

        organic_soil_math_w = MathOrganicSoil(*organic_soil_inputs_w)
        organic_soil_math_w.calculate_emissions()

        if input.peat_area_start:
            peat_extraction_inputs_w = [
                input.peat_area_start,
                input.peat_area_w,
                input.peat_ditches_area_start,
                input.peat_ditches_area_w,
                input.activity.change_rate.name,
                onsite_ef_w.co2,
                input.onsite_co2_peat_t2_w,
                onsite_ef_w.ch4,
                None,
                onsite_ef_w.n2o,
                input.onsite_n2o_peat_t2_w,
                offsite_ef_w.doc,
                input.offsite_doc_peat_t2_w,
                offsite_ef_w.ch4,
                input.offsite_ch4_peat_t2_w,
                project.gw_potential.ch4,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                conversion_factor_w.volume,
                input.peat_density_t2_w,
                1,  # TODO: Should be conversion_factor_w.volume,
                conversion_factor_w.weight,
                input.peat_extraction_height_start,
                input.peat_extraction_height_w,
            ]

            peat_extraction_math_w = MathPeatExtraction(*peat_extraction_inputs_w)
            peat_extraction_math_w.calculate_emissions()

        organic_soil_inputs_wo = [
            input.fire_type_wo is not None,
            input.soil_fire_periodicity_wo,
            area_affected_by_module,
            dry_matter_wo.value if fire_used_wo else None,
            input.mean_dry_matter_t2_wo,
            input.soil_fire_impact_percentage_wo,
            fire_ref.co2,
            input.fire_on_soil_co2_t2_wo,
            fire_ref.co,
            input.fire_on_soil_co_t2_wo,
            fire_ref.ch4,
            input.fire_on_soil_ch4_t2_wo,
            project.gw_potential.ch4,
            input.activity.change_rate.name,
            project.implementation_years,
            project.capitalization_years,
            project.gw_potential.n2o,
            ef_offsite_start.doc,
            input.offsite_doc_drainge_t2_start,
            input.drainage_area_start,
            input.drainage_area_wo,
            ef_onsite_start.co2,
            input.onsite_co2_drainge_t2_start,
            input.ditches_area_start,
            input.ditches_area_wo,
            ef_onsite_start.ch4,
            input.onsite_ch4_drainge_t2_start,
            ef_offsite_start.ch4,
            input.offsite_ch4_drainge_t2_start,
            ef_onsite_start.n2o,
            input.onsite_n2o_drainge_t2_start,
            ef_offsite_start.doc,
            input.offsite_doc_drainge_t2_start,
            ef_onsite_wo.co2,
            input.onsite_co2_drainge_t2_wo,
            ef_onsite_wo.ch4,
            input.onsite_ch4_drainge_t2_wo,
            ef_offsite_wo.ch4,
            input.offsite_ch4_drainge_t2_wo,
            ef_onsite_wo.n2o,
            input.onsite_n2o_drainge_t2_wo,
            rewetting_start.doc,
            input.offsite_doc_rewetting_t2_start,
            rewetting_start.co2,
            input.onsite_co2_rewetting_t2_start,
            rewetting_start.ch4,
            input.onsite_ch4_rewetting_t2_start,
            rewetting_start.n2o,
            input.onsite_n2o_rewetting_t2_start,
            rewetting_wo.doc,
            input.offsite_doc_rewetting_t2_wo,
            rewetting_wo.co2,
            input.onsite_co2_rewetting_t2_wo,
            rewetting_wo.ch4,
            input.onsite_ch4_rewetting_t2_wo,
            rewetting_wo.n2o,
            input.onsite_n2o_rewetting_t2_wo,
            area_affected_by_module,
        ]

        organic_soil_math_wo = MathOrganicSoil(*organic_soil_inputs_wo)
        organic_soil_math_wo.calculate_emissions()

        if input.peat_area_start:
            peat_extraction_inputs_wo = [
                input.peat_area_start,
                input.peat_area_wo,
                input.peat_ditches_area_start,
                input.peat_ditches_area_wo,
                input.activity.change_rate.name,
                onsite_ef_wo.co2,
                input.onsite_co2_peat_t2_wo,
                onsite_ef_wo.ch4,
                None,
                onsite_ef_wo.n2o,
                input.onsite_n2o_peat_t2_wo,
                offsite_ef_wo.doc,
                input.offsite_doc_peat_t2_wo,
                offsite_ef_wo.ch4,
                input.offsite_ch4_peat_t2_wo,
                project.gw_potential.ch4,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                conversion_factor_wo.volume,
                input.peat_density_t2_wo,
                1,  # TODO: Should be conversion_factor_wo.volume,
                conversion_factor_wo.weight,
                input.peat_extraction_height_start,
                input.peat_extraction_height_wo,
            ]

            peat_extraction_math_wo = MathPeatExtraction(*peat_extraction_inputs_wo)
            peat_extraction_math_wo.calculate_emissions()

        self.inputs_w = {
            "organic_soil": organic_soil_inputs_w,
            "peat_extraction": peat_extraction_inputs_w,
        }

        self.inputs_wo = {
            "organic_soil": organic_soil_inputs_wo,
            "peat_extraction": peat_extraction_inputs_wo,
        }

        organic_soil_results_w = organic_soil_math_w.result if organic_soil_math_w else MathResult(project.implementation_years, project.capitalization_years)
        organic_soil_results_wo = organic_soil_math_wo.result if organic_soil_math_wo else MathResult(project.implementation_years, project.capitalization_years)

        if input.peat_area_start:
            peat_extraction_results_w = peat_extraction_math_w.result if peat_extraction_math_w else MathResult(project.implementation_years, project.capitalization_years)
            peat_extraction_results_wo = peat_extraction_math_wo.result if peat_extraction_math_wo else MathResult(project.implementation_years, project.capitalization_years)

            total_results_w += organic_soil_results_w + peat_extraction_results_w
            total_results_wo += organic_soil_results_wo + peat_extraction_results_wo

        else:
            total_results_w += organic_soil_results_w
            total_results_wo += organic_soil_results_wo

        results_tuple = (total_results_w, total_results_wo)

        return results_tuple

    def defaults(self) -> DefaultData:
        self.calculate()

        module: OrganicSoil = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if is_with(module):
            math_w = MathOrganicSoil(*self.inputs_w["organic_soil"])
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.start)
            defaults_w.update(math_w_defaults.other)

            math_w = MathPeatExtraction(*self.inputs_w["peat_extraction"])
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.start)
            defaults_w.update(math_w_defaults.other)

        if is_without(module):
            math_wo = MathOrganicSoil(*self.inputs_wo["organic_soil"])
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.start)
            defaults_wo.update(math_wo_defaults.other)

            math_wo = MathPeatExtraction(*self.inputs_wo["peat_extraction"])
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.start)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class ForestManagementCalculator(BaseCalculator):
    """
    # TODO: Review
    """

    def get_defaults(self, calculate=False) -> dict:
        return super().get_defaults(calculate)

    def calculate(self) -> Result:
        """"""

        input: LandModule = self.data
        luc: LandUseChange = input.land_use_change
        project: Project = input.activity.project
        area = luc.area if luc else input.area

        DELAY_START_W = 0
        DELAY_START_WO = 0
        DELAY_W = 0
        DELAY_WO = 0

        # TODO: Review
        if luc:
            # NOTE: This if is useless. It's always True
            land_use_type = input.land_use_type_start if luc.module_type_start.class_name == "ForestManagement" else input.land_use_type_start
            land_use_type = LandUseType.objects.get(name=land_use_type.name)
        else:
            land_use_type = input.land_use_type_start

        forest: ForestManagement = luc.forestmanagement if luc else input

        AGB_GROWTH_NOT_FOUND = f"AGB Growth not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region. Please insert t2 values for AGB Growth Rate for all scenarios."
        BGB_UNDER_20_NOT_FOUND = f"BGB (under 20 years) not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region. Please insert t2 values for BGB (under 20 years) for all scenarios."
        BGB_OVER_20_NOT_FOUND = f"BGB (over 20 years) not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region. Please insert t2 values for BGB (over 20 years) for all scenarios."
        AGB_UNDER_20_NOT_FOUND = f"AGB (under 20 years) not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region. Please insert t2 values for AGB (under 20 years) for all scenarios."
        AGB_OVER_20_NOT_FOUND = f"AGB (over 20 years) not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region. Please insert t2 values for AGB (over 20 years) for all scenarios."
        LITTER_DW_NOT_FOUND = f"Litter/Deadwood Carbon Stock reference value not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region."
        FLU_START_NOT_FOUND = f"FLU reference value not found for ({forest.forest_type.name}) {land_use_type.name} in {project.climate.name} climate, {project.country.region.name} region."
        SOC_NOT_FOUND = f"Soil Organic Carbon reference value not found for the given parameters in {project.climate.name} climate, {project.moisture.name} moisture, {project.soil_type.name} soil type."

        is_afforestation_w = luc and luc.module_type_w.class_name == "ForestManagement"
        is_afforestation_wo = luc and luc.module_type_wo.class_name == "ForestManagement"

        has_t2_growth_start = forest.agb_growth_rate_gt_20_yrs_t2_start and forest.agb_growth_rate_le_20_yrs_t2_start
        has_t2_growth_w = forest.agb_growth_rate_gt_20_yrs_t2_w and forest.agb_growth_rate_le_20_yrs_t2_w
        has_t2_growth_wo = forest.agb_growth_rate_gt_20_yrs_t2_wo and forest.agb_growth_rate_le_20_yrs_t2_wo

        crluft = {
            "climate": project.climate,
            "region": project.country.region,
            "land_use_type": land_use_type,
            "forest_type": forest.forest_type,
        }

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

        forest_options = {"forest_condition_type": forest.forest_condition_type, "from_year": 0}

        try:
            agb_under_20 = ipcc.ForestManagementAGB.objects.get(**crluft, **forest_options)
        except ipcc.ForestManagementAGB.DoesNotExist:
            raise ValueError(AGB_UNDER_20_NOT_FOUND)

        try:
            if forest.forest_condition_type.name == "Secondary":
                forest_options.update({"from_year": 21})

            agb_over_20 = ipcc.ForestManagementAGB.objects.get(**crluft, **forest_options)
        except ipcc.ForestManagementAGB.DoesNotExist:
            raise ValueError(AGB_OVER_20_NOT_FOUND)

        try:
            flu_start = ipcc.AfforestationFLU.objects.get(climate=project.climate, moisture=project.moisture, land_use_type=land_use_type)
        except ipcc.AfforestationFLU.DoesNotExist:
            try:
                flu_start = ipcc.AfforestationFLU.objects.get(climate=project.climate, moisture=project.moisture, land_use_type__name="Agroforestry - Default")
            except ipcc.AfforestationFLU.DoesNotExist:
                raise ValueError(FLU_START_NOT_FOUND)

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
            agb_max_w = statistics.mean([agb_over_20.agb_min, agb_over_20.agb_max]) if project.implementation_years > 20 else statistics.mean([agb_under_20.agb_min, agb_under_20.agb_max])
            agb_growth_under_20_w = statistics.mean([agb_under_20.agb_growth_max, agb_under_20.agb_growth_min])
            agb_growth_over_20_w = agb_growth_under_20_w
            agb_start_w = 0
            flu_w = flu_start
            litter_dw_start_w = SimpleNamespace(litter=0, dw=0)

        if is_afforestation_wo:
            agb_max_wo = statistics.mean([agb_over_20.agb_min, agb_over_20.agb_max]) if project.implementation_years > 20 else statistics.mean([agb_under_20.agb_min, agb_under_20.agb_max])
            agb_growth_under_20_wo = statistics.mean([agb_under_20.agb_growth_max, agb_under_20.agb_growth_min])
            agb_growth_over_20_wo = agb_growth_under_20_wo
            agb_start_wo = 0
            flu_wo = flu_start
            litter_dw_start_wo = SimpleNamespace(litter=0, dw=0)

        disturbances: list[ForestDisturbance] = input.disturbances.all()

        som: ipcc.LandUseNitrousEmissionFactor = utils.get_or_raise(ipcc.LandUseNitrousEmissionFactor, {"moisture": project.moisture}, f"SOM not found for {project.moisture.name} moisture.")

        math_w = None
        math_wo = None

        inputs_w = [
            project.capitalization_years,
            project.implementation_years,
            input.activity.change_rate.name,
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
            1,  # FMG_start
            1,  # FMG_w
            forest.fmg_t2_start,
            forest.fmg_t2_w,
            flu_start.value,
            flu_w.value,
            forest.flu_t2_start,
            forest.flu_t2_w,
            1,  # FI_start
            1,  # FI_w
            forest.fi_t2_start,
            forest.fi_t2_w,
            project.gw_potential.ch4,
            project.gw_potential.n2o,
            1,  # forest_cf
            1,  # forest_gef_ch4
            1,  # forest_gef_n2o
            1,  # forest_gef_co2
            1,  # mangrove_factor (see mangrove implementation elsewhere)
            forest.average_yearly_degradation_percentage_w,
            som.value,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            DELAY_WO,
        ]

        math_w = MathForestManagement(*inputs_w)
        math_w.calculate_emissions()

        inputs_wo = [
            project.capitalization_years,
            project.implementation_years,
            input.activity.change_rate.name,
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
            1,  # FMG_start
            1,  # FMG_w
            forest.fmg_t2_start,
            forest.fmg_t2_w,
            flu_start.value,
            flu_wo.value,
            forest.flu_t2_start,
            forest.flu_t2_wo,
            1,  # FI_start
            1,  # FI_w
            forest.fi_t2_start,
            forest.fi_t2_wo,
            project.gw_potential.ch4,
            project.gw_potential.n2o,
            1,  # forest_cf
            1,  # forest_gef_ch4
            1,  # forest_gef_n2o
            1,  # forest_gef_co2
            1,  # mangrove_factor (see mangrove implementation elsewhere)
            forest.average_yearly_degradation_percentage_w,
            som.value,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            DELAY_WO,
        ]

        math_wo = MathForestManagement(*inputs_wo)
        math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        print("w = ", inputs_w)
        print("wo = ", inputs_wo)

        return results_tuple

    def defaults(self) -> DefaultData:
        return super().defaults()


class DegradedLandCalculator(BaseCalculator):
    """
    Calculator for annual cropping modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        # NOTE: I think these should all be defaulted to 1, instead of 0
        self.fi_start: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=1)
        self.fmg_start: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=1)
        self.flu_start: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=1)
        self.fi_w: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=1)
        self.fmg_w: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=1)
        self.flu_w: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=1)
        self.fi_wo: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=1)
        self.fmg_wo: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=1)
        self.flu_wo: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=1)
        self.som: SimpleNamespace | ipcc.LandUseNitrousEmissionFactor = SimpleNamespace(value=1)

        self.math_start_w = None
        self.math_start_wo = None
        self.math_w = None
        self.math_wo = None

    def calculate(self) -> Result:
        input: DegradedLand = self.data
        activity: Activity = input.activity
        project: Project = activity.project
        luc: LandUseChange = input.land_use_change
        area = luc.area if luc else input.area

        DELAY_START_W = 0
        DELAY_START_WO = 0
        DELAY_W = 0
        DELAY_WO = 0

        self.get_defaults()

        module_start = module_w = module_wo = input

        if luc:
            module_start, module_w, module_wo = luc.get_modules()

        if input.is_luc_remaining_same():
            self.inputs_start_w = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.som.value,
                self.soc.value,
                self.soc.value,
                module_start.soc_t2_start,
                module_w.soc_t2_w,
                CALCULATE_SOC_SOM_START_W,
                self.fmg_start.value,
                self.fmg_w.value,
                module_start.fmg_t2_start,
                module_w.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module_start.flu_t2_start,
                module_w.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module_start.fi_t2_start,
                module_w.fi_t2_w,
                DELAY_START_W,
            ]

            self.math_start_w = MathNotCultivatedLand(*self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if input.is_business_as_usual():
            self.inputs_start_wo = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.som.value,
                self.soc.value,
                self.soc.value,
                module_start.soc_t2_start,
                module_wo.soc_t2_wo,
                CALCULATE_SOC_SOM_START_WO,
                self.fmg_start.value,
                self.fmg_wo.value,
                module_start.fmg_t2_start,
                module_wo.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                module_start.flu_t2_start,
                module_wo.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module_start.fi_t2_start,
                module_wo.fi_t2_wo,
                DELAY_START_WO,
            ]

            self.math_start_wo = MathNotCultivatedLand(*self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if input.is_with():
            self.inputs_w = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.som.value,
                self.soc.value,
                self.soc.value,
                module_start.soc_t2_start,
                module_w.soc_t2_w,
                CALCULATE_SOC_SOM_W,
                self.fmg_start.value,
                self.fmg_w.value,
                module_start.fmg_t2_start,
                module_w.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module_start.flu_t2_start,
                module_w.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module_start.fi_t2_start,
                module_w.fi_t2_w,
                DELAY_W,
            ]

            self.math_w = MathNotCultivatedLand(*self.inputs_w)
            self.math_w.calculate_emissions()

        if input.is_without():
            self.inputs_wo = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.som.value,
                self.soc.value,
                self.soc.value,
                module_start.soc_t2_start,
                module_wo.soc_t2_wo,
                CALCULATE_SOC_SOM_WO,
                self.fmg_start.value,
                self.fmg_wo.value,
                module_start.fmg_t2_start,
                module_wo.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                module_start.flu_t2_start,
                module_wo.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module_start.fi_t2_start,
                module_wo.fi_t2_wo,
                DELAY_WO,
            ]

            self.math_wo = MathNotCultivatedLand(*self.inputs_wo)
            self.math_wo.calculate_emissions()

        results_start_w = self.math_start_w.result if self.math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        results_w = self.math_w.result if self.math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = self.math_wo.result if self.math_wo else MathResult(project.implementation_years, project.capitalization_years)

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

    def get_defaults(self, calculate=False) -> dict:
        module: DegradedLand = self.data
        activity: Activity = module.activity
        project: Project = activity.project
        luc: LandUseChange = module.land_use_change

        climate: Climate = activity.climate_t2 or project.climate
        moisture: Moisture = activity.moisture_t2 or project.moisture
        region: Region = project.country.region
        soil_type: SoilType = project.soil_type

        moisture_flt = {"moisture": moisture}
        soil_flt = {"soil_type": soil_type}
        cm = {"climate": climate, "moisture": moisture}

        module_start = module_w = module_wo = module

        # NOTE: Here we have a hardcoded organic_input_flt. This is due to the fact that it should not be present in the table (it isn't in the Excel)
        retrieved_input = OrganicInputType.objects.get(name="Medium C input")
        organic_input_hardcoded = {"organic_input_type": retrieved_input}

        if luc:
            module_start, module_w, module_wo = luc.get_modules()

        if module.is_luc_remaining_same():
            self.flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.emission_factors_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")

        if module.is_business_as_usual():
            self.flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.emission_factors_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")

        if module.is_with():
            self.flu_w = get_flu_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
            self.fmg_w = get_fmg_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
            self.fi_w = get_fi_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
            self.emission_factors_w = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")

        if module.is_without():
            self.flu_wo = get_flu_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.fmg_wo = get_fmg_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.fi_wo = get_fi_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.emission_factors_wo = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")

        self.soc = utils.get_or_raise(ipcc.SoilOrganicCarbon, cm | soil_flt, f"SoilOrganicCarbon for {soil_type.name} soil type in {climate.name} climate and {moisture.name} moisture does not exist")
        self.som = utils.get_or_raise(ipcc.LandUseNitrousEmissionFactor, moisture_flt, f"LandUseNitrousEmissionFactor for {moisture.name} moisture and Medium C input does not exist")

        if module.status.name == "READY" and calculate:
            self.calculate()


class SetAsideCalculator(BaseCalculator):
    """
    Calculator for annual cropping modules.
    """

    def __init__(self, input) -> None:
        super().__init__(input)

        # NOTE: I think these should all be defaulted to 1, instead of 0
        self.fi_start: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=1)
        self.fmg_start: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=1)
        self.flu_start: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=1)
        self.fi_w: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=1)
        self.fmg_w: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=1)
        self.flu_w: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=1)
        self.fi_wo: SimpleNamespace | ipcc.FIData = SimpleNamespace(value=1)
        self.fmg_wo: SimpleNamespace | ipcc.FMGData = SimpleNamespace(value=1)
        self.flu_wo: SimpleNamespace | ipcc.FLUData = SimpleNamespace(value=1)
        self.som: SimpleNamespace | ipcc.LandUseNitrousEmissionFactor = SimpleNamespace(value=1)

        self.math_start_w = None
        self.math_start_wo = None
        self.math_w = None
        self.math_wo = None

    def calculate(self) -> Result:
        module: SetAside = self.data
        activity: Activity = module.activity
        project: Project = activity.project
        luc: LandUseChange = module.land_use_change
        area = luc.area if luc else module.area

        DELAY_START_W = 0
        DELAY_START_WO = 0
        DELAY_W = 0
        DELAY_WO = 0

        self.get_defaults()

        module_start = module_w = module_wo = module

        if luc:
            module_start, module_w, module_wo = luc.get_modules()

        if module.is_luc_remaining_same():
            self.inputs_start_w = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.som_start.value,
                self.soc.value,
                self.soc.value,
                module_start.soc_t2_start,
                module_w.soc_t2_w,
                CALCULATE_SOC_SOM_START_W,
                self.fmg_start.value,
                self.fmg_w.value,
                module_start.fmg_t2_start,
                module_w.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module_start.flu_t2_start,
                module_w.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module_start.fi_t2_start,
                module_w.fi_t2_w,
                DELAY_START_W,
            ]

            self.math_start_w = MathNotCultivatedLand(*self.inputs_start_w)
            self.math_start_w.calculate_emissions()

        if module.is_business_as_usual():
            self.inputs_start_wo = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.som_start.value,
                self.soc.value,
                self.soc.value,
                module_start.soc_t2_start,
                module_wo.soc_t2_wo,
                CALCULATE_SOC_SOM_START_WO,
                self.fmg_start.value,
                self.fmg_wo.value,
                module_start.fmg_t2_start,
                module_wo.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                module_start.flu_t2_start,
                module_wo.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module_start.fi_t2_start,
                module_wo.fi_t2_wo,
                DELAY_START_WO,
            ]

            self.math_start_wo = MathNotCultivatedLand(*self.inputs_start_wo)
            self.math_start_wo.calculate_emissions()

        if module.is_with():
            self.inputs_w = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.som_w.value,
                self.soc.value,
                self.soc.value,
                module_start.soc_t2_start,
                module_w.soc_t2_w,
                CALCULATE_SOC_SOM_W,
                self.fmg_start.value,
                self.fmg_w.value,
                module_start.fmg_t2_start,
                module_w.fmg_t2_w,
                self.flu_start.value,
                self.flu_w.value,
                module_start.flu_t2_start,
                module_w.flu_t2_w,
                self.fi_start.value,
                self.fi_w.value,
                module_start.fi_t2_start,
                module_w.fi_t2_w,
                DELAY_W,
            ]

            self.math_w = MathNotCultivatedLand(*self.inputs_w)
            self.math_w.calculate_emissions()

        if module.is_without():
            self.inputs_wo = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                activity.change_rate.name,
                project.gw_potential.n2o,
                self.som_wo.value,
                self.soc.value,
                self.soc.value,
                module_start.soc_t2_start,
                module_wo.soc_t2_wo,
                CALCULATE_SOC_SOM_WO,
                self.fmg_start.value,
                self.fmg_wo.value,
                module_start.fmg_t2_start,
                module_wo.fmg_t2_wo,
                self.flu_start.value,
                self.flu_wo.value,
                module_start.flu_t2_start,
                module_wo.flu_t2_wo,
                self.fi_start.value,
                self.fi_wo.value,
                module_start.fi_t2_start,
                module_wo.fi_t2_wo,
                DELAY_WO,
            ]

            self.math_wo = MathNotCultivatedLand(*self.inputs_wo)
            self.math_wo.calculate_emissions()

        results_start_w = self.math_start_w.result if self.math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        results_start_wo = self.math_start_wo.result if self.math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        results_w = self.math_w.result if self.math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = self.math_wo.result if self.math_wo else MathResult(project.implementation_years, project.capitalization_years)

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

    def get_defaults(self, calculate=False) -> dict:
        module: SetAside = self.data
        activity: Activity = module.activity
        project: Project = activity.project
        luc: LandUseChange = module.land_use_change

        climate: Climate = activity.climate_t2 or project.climate
        moisture: Moisture = activity.moisture_t2 or project.moisture
        region: Region = project.country.region
        soil_type: SoilType = project.soil_type

        climate_flt = {"climate": climate}
        moisture_flt = {"moisture": moisture}
        soil_flt = {"soil_type": soil_type}
        region_flt = {"continent": region}
        cm = {"climate": climate, "moisture": moisture}

        module_start = module_w = module_wo = input

        # NOTE: Here we have a hardcoded organic_input_flt. This is due to the fact that it should not be present in the table (it isn't in the Excel)
        retrieved_input = OrganicInputType.objects.get(name="Medium C input")
        organic_input_hardcoded = {"organic_input_type": retrieved_input}

        if luc:
            module_start, module_w, module_wo = luc.get_modules()

        if module.is_luc_remaining_same():
            self.flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.emission_factors_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")

        if module.is_business_as_usual():
            self.flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.START)
            self.emission_factors_start = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")

        if module.is_with():
            self.flu_w = get_flu_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
            self.fmg_w = get_fmg_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
            self.fi_w = get_fi_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
            self.emission_factors_w = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")

        if module.is_without():
            self.flu_wo = get_flu_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.fmg_wo = get_fmg_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.fi_wo = get_fi_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
            self.emission_factors_wo = utils.get_or_raise(ipcc.NitrousEmissionFactor, moisture_flt, f"DefaultEmissionFactor for {moisture.name} moisture does not exist")

        self.soc = utils.get_or_raise(ipcc.SoilOrganicCarbon, cm | soil_flt, f"SoilOrganicCarbon for {soil_type.name} soil type in {climate.name} climate and {moisture.name} moisture does not exist")

        if module.status.name == "READY" and calculate:
            self.calculate()
