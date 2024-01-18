import copy
import sys
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import SimpleNamespace

from django.db.models import Q
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
    Electricity,
    Energy,
    FloodedRice,
    ForestManagement,
    Fuel,
    Grassland,
    GrasslandParameter,
    Input,
    InputEntry,
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
    OrganicSoil,
    PerennialCropping,
    Project,
    Region,
    Road,
    Settlement,
    SmallFishery,
    SmallFisheryParameter,
    SoilType,
    StatusType,
    Waterbody,
)


def is_luc_remaining_same(module: LandModule) -> bool:
    """
    Checks if the land use change for a given module remains the same.

    Args:
        module (LandModule): The land module to check.

    Returns:
        bool: True if the land use change remains the same, False otherwise.
    """
    luc: LandUseChange = module.land_use_change
    return not luc or (luc and luc.module_type_start.class_name == module.__class__.__name__ and luc.module_type_w.class_name == module.__class__.__name__)


def is_business_as_usual(module: LandModule) -> bool:
    """
    Checks if the given module represents a business-as-usual scenario.

    Args:
        module (LandModule): The land module to check.

    Returns:
        bool: True if the module represents a business-as-usual scenario, False otherwise.
    """
    luc: LandUseChange = module.land_use_change
    return not luc or (luc and luc.module_type_start.class_name == module.__class__.__name__ and luc.module_type_wo.class_name == module.__class__.__name__)


def is_without(module: LandModule) -> bool:
    """
    Checks if the given module is without a land use change or if the module type without land use change matches the module's class name.

    Args:
        module (LandModule): The module to check.

    Returns:
        bool: True if the module is associated with the land use change or if the provided module types the LandUseChange "WITHOUT" scenario. False otherwise.
    """
    luc: LandUseChange = module.land_use_change
    return not luc or (luc.module_type_wo.class_name == module.__class__.__name__)


def is_with(module: LandModule) -> bool:
    """
    Checks if the given module is associated with a specific land use change.

    Args:
        module (LandModule): The module to check.

    Returns:
        bool: True if the module is associated with the land use change or if the provided module types the LandUseChange "WITH" scenario. False otherwise.
    """
    luc: LandUseChange = module.land_use_change
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
    if attr:
        return ipcc.FIData.objects.get(climate=climate, moisture=moisture, organic_input_type=attr)
    else:
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
    if attr:
        return ipcc.FMGData.objects.get(climate=climate, moisture=moisture, tillage_management_type=attr)
    else:
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
    if attr:
        return ipcc.FLUData.objects.get(climate=climate, moisture=moisture, land_use_type=attr)
    else:
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
    grassland_soc = None
    module_start: Grassland = getattr(luc.activity, luc.module_type_start.class_name.lower(), None).first()
    if luc.module_type_start.name == "Grassland" and module_start:
        grassland_soc = ipcc.GrasslandStockExchangeFactor.objects.get(
            grassland_management_type=module_start.grassland_management_type_start,
            climate=luc.activity.project.climate,
        )

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
        breakdown = (
            self.total_w.breakdown(by=by),
            self.total_wo.breakdown(by=by),
            self.balance.breakdown(by=by),
        )
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
        """
        CalculatorClass = getattr(sys.modules[__name__], f"{input.__class__.__name__}Calculator", None)
        if not CalculatorClass:
            raise Exception(f"No calculator found for {input.__class__.__name__}")
        return CalculatorClass

    def calculate_result(self, input, aggregate_by=BreakdownTypes.TOTAL):
        """
        Calculates the results for a given module.
        """
        try:
            calculator: BaseCalculator = self.__get_calculator(input)(input)
            result: tuple[MathResult] = calculator.calculate()
            return Result(*result).breakdown(by=aggregate_by)

        except Exception as e:
            traceback.print_exc()
            raise Exception(f"Error in {input.__class__.__name__}: {e}")

    def get_defaults(self, input):
        """
        Gets the default values for a given module.
        """
        try:
            calculator: BaseCalculator = self.__get_calculator(input)(input)
            return calculator.defaults()

        except Exception as e:
            traceback.print_exc()
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
            modules = get_luc_modules(luc)

            if not all(modules):
                raise Exception("At least one module is missing")

            if any(module.status != StatusType.objects.get(name="READY") for module in modules):
                raise Exception("At least one module is not ready to perform the calculation")

    @abstractmethod
    def defaults(self) -> DefaultData:
        """
        Get the default values for a given module.
        """
        pass


class LandUseChangeCalculator(BaseCalculator):
    """
    Calculator for land use change modules.
    """

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

        input: LandUseChange = self.data

        module_start = getattr(input.activity, input.module_type_start.class_name.lower(), None)
        module_w = getattr(input.activity, input.module_type_w.class_name.lower(), None)
        module_wo = getattr(input.activity, input.module_type_wo.class_name.lower(), None)

        if not module_start or not module_w or not module_wo:
            missing_modules = ["Start" if not module_start else "With" if not module_w else "Without" for module in [module_start, module_w, module_wo] if not module].join(", ")
            raise Exception(f"LandUseChange module must have a start with and without module. Missing {missing_modules} module(s).")

        module_start = module_start.get(land_use_change=input)
        module_w = module_w.get(land_use_change=input)
        module_wo = module_wo.get(land_use_change=input)

        # TODO: DeforestationCalculator now expects the ForestManagement module only. Refactor the calculator accordingly (check T2 values!)
        # results_start = CalculatorFactory().calculate_result(module_start, aggregate_by=aggregate_by)
        results_w, results_wo = self.luc_based_calculation(module_start, module_w, aggregate_by=aggregate_by)

        return (results_w, results_wo)


class DeforestationCalculator(BaseCalculator):
    """
    TODO: Refactor with new logic
    Calculator for deforestation modules.
    """

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
        continent = project.country.region
        soil_type = project.soil_type

        forest: ForestManagement = module.activity.forestmanagement

        # TODO: Maybe generalise this on a higher level
        if not forest:
            raise Exception("Forest module is missing")
        if module.status != StatusType.objects.get(name="READY"):
            raise Exception("Forest module is not complete")

        cmc = {
            "climate": climate,
            "moisture": moisture,
            "continent": continent,
        }

        mangroves_data = None

        soc_ref = ipcc.SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type)

        total_biomass_start = ipcc.TotalBiomassAfterDefo.objects.get(**cmc, land_use_type=module.land_use_type_start)
        total_biomass_end = ipcc.TotalBiomassAfterDefo.objects.get(**cmc, land_use_type=module.land_use_type_w)

        # NOTE: Maybe merge the mangroves and deforestation IPCC tables into one table?
        if self.data.vegetation_type != utils.MANGROVES:
            defo_table_start = ipcc.LitterDeadwoodCarbonStock.objects.get(vegetation_type=module.land_use_type_start)
            defo_table_end = ipcc.LitterDeadwoodCarbonStock.objects.get(vegetation_type=module.land_use_type_w)

            ag_biomass_start = ipcc.AboveGroundBiomass.objects.get(continent=continent, vegetation_type=module.land_use_type_start)
            ag_biomass_end = ipcc.AboveGroundBiomass.objects.get(continent=continent, vegetation_type=module.land_use_type_w)

            bg_biomass_start = ipcc.BelowGroundBiomass.objects.get_first_above_threshold(
                continent=continent,
                vegetation_type=module.land_use_type_start,
                threshold=ag_biomass_start.value,
            )
            bg_biomass_end = ipcc.BelowGroundBiomass.objects.get_first_above_threshold(
                continent=continent,
                vegetation_type=module.land_use_type_w,
                threshold=ag_biomass_end.value,
            )
        else:
            mangroves_data = ipcc.DataOnMangrove.objects.get(continent=continent)

        combustion_factor_start = ipcc.CombustionFactor.objects.get(vegetation_type=module.land_use_type_start)
        combustion_factor_end = ipcc.CombustionFactor.objects.get(vegetation_type=module.land_use_type_w)

        moisture_factor = ipcc.DefaultEmissionFactor.objects.filter(moisture=moisture)
        moisture_factor = moisture_factor.filter(Q(input__name__icontains="Other N Inputs") | Q(input__name__icontains="All N Inputs")).first()

        flu_start = ipcc.LandUseCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=module.land_use_type_start)
        flu_end = ipcc.LandUseCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=module.land_use_type_w)

        self.inputs_start = [
            luc.area,
            0,
            project.implementation_years,
            project.capitalization_years,
            change_rate.name,
            total_biomass_start.value,
            forest.get_biomass_t2(utils.ScenarioTypes.START),
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            luc.is_fire_used_start,
            combustion_factor_start.n2o,
            combustion_factor_start.ch4,
            combustion_factor_start.value,
            moisture_factor.value,
            defo_table_start.litter if mangroves_data is None else mangroves_data.litter,
            forest.litter_t2_start,
            defo_table_start.dw if mangroves_data is None else mangroves_data.dw,
            forest.deadwood_t2_start,
            module.hwp_start,  # TODO: What's hwp in the new forest?
            utils.MANGROVE_FACTOR if mangroves_data is not None else utils.NON_MANGROVE_FACTOR,
            forest.agb_t2_start,
            forest.bgb_t2_start,
            flu_start.value,
            mangroves_data.agb_c if mangroves_data is not None else ag_biomass_start.value,
            mangroves_data.bgb if mangroves_data is not None else bg_biomass_start.value,
            utils.CN_RATIO_GRASSLAND,  # TODO: Ratio might be different, see OtherLandUseCalculator
            module.soc_after_defo_t2_start,  # TODO: soil after defo t2
            soc_ref.value,
            project.soc_ref_t2,
        ]

        self.inputs_w = [
            0,
            luc.area,
            project.implementation_years,
            project.capitalization_years,
            change_rate.name,
            total_biomass_end.value,
            forest.get_biomass_t2(utils.ScenarioTypes.WITH),
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            luc.is_fire_used_w,
            combustion_factor_end.n2o,
            combustion_factor_end.ch4,
            combustion_factor_end.value,
            moisture_factor.value,
            defo_table_end.litter if mangroves_data is None else mangroves_data.litter,
            forest.litter_t2_w,
            defo_table_end.dw if mangroves_data is None else mangroves_data.dw,
            forest.deadwood_t2_w,
            module.hwp_end,
            utils.MANGROVE_FACTOR if mangroves_data is not None else utils.NON_MANGROVE_FACTOR,
            forest.agb_t2_w,
            forest.bgb_t2_w,
            flu_end.value,
            mangroves_data.agb_c if mangroves_data is not None else ag_biomass_end.value,
            mangroves_data.bgb if mangroves_data is not None else bg_biomass_end.value,
            utils.CN_RATIO_GRASSLAND,
            module.soc_after_defo_t2_end,  # soil after defo t2
            soc_ref.value,
            project.soc_ref_t2,
        ]

        self.inputs_wo = [
            0,
            luc.area,
            project.implementation_years,
            project.capitalization_years,
            change_rate.name,
            total_biomass_start.value,
            forest.get_biomass_t2(utils.ScenarioTypes.WITHOUT),
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            luc.is_fire_used_start,
            combustion_factor_start.n2o,
            combustion_factor_start.ch4,
            combustion_factor_start.value,
            moisture_factor.value,
            defo_table_start.litter if mangroves_data is None else mangroves_data.litter,
            forest.litter_t2_wo,
            defo_table_start.dw if mangroves_data is None else mangroves_data.dw,
            forest.deadwood_t2_wo,
            module.hwp_start,
            utils.MANGROVE_FACTOR if mangroves_data is not None else utils.NON_MANGROVE_FACTOR,
            forest.agb_t2_wo,
            forest.bgb_t2_wo,
            flu_start.value,
            mangroves_data.agb_c if mangroves_data is not None else ag_biomass_start.value,
            mangroves_data.bgb if mangroves_data is not None else bg_biomass_start.value,
            utils.CN_RATIO_GRASSLAND,
            module.soc_after_defo_t2_start,  # soil after defo t2
            soc_ref.value,
            project.soc_ref_t2,
        ]

        math_start = MathDeforestation(*self.inputs_start)
        math_w = MathDeforestation(*self.inputs_w)
        math_wo = MathDeforestation(*self.inputs_wo)

        math_start.calculate_emissions()
        math_w.calculate_emissions()
        math_wo.calculate_emissions()

        res_start = math_start.result if math_start else MathResult(project.implementation_years, project.capitalization_years)
        res_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        res_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        return (res_w + res_start, res_wo + res_start)

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

        luc_start = LandUseType.objects.get(name=luc.module_type_start.name)
        luc_w = LandUseType.objects.get(name=luc.module_type_w.name)
        luc_wo = LandUseType.objects.get(name=luc.module_type_wo.name)

        biomass_initial = ipcc.ForestTotalBiomass.objects.get_or_default(**cmc, land_use_type=luc_start)
        biomass_final_w = ipcc.TotalBiomassAfterDefo.objects.get_or_default(**cmc, land_use_type=luc_w)
        biomass_final_wo = ipcc.TotalBiomassAfterDefo.objects.get_or_default(**cmc, land_use_type=luc_wo)

        soc = ipcc.SoilOrganicCarbon.objects.get(**cm, soil_type=project.soil_type)

        fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        fmg_final_w = get_fmg_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        fmg_final_wo = get_fmg_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)

        flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        flu_final_w = get_flu_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        flu_final_wo = get_flu_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)

        fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        fi_final_w = get_fi_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        fi_final_wo = get_fi_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)

        c_n_ratio = utils.CN_RATIO_GRASSLAND if luc.module_type_start.class_name in ["Grassland", "ForestManagement"] else utils.CN_RATIO_CROP

        moisture_factor = ipcc.NitrousEmissionFactor.objects.get(moisture=moisture, name__icontains="Other N Inputs")

        combustion_factor_w = ipcc.AfforestationCombustionFactor.objects.get_or_default(land_use_type=luc_w)
        combustion_factor_wo = ipcc.AfforestationCombustionFactor.objects.get_or_default(land_use_type=luc_wo)

        inputs_w = [
            biomass_initial.value,
            module_start.get_biomass_t2(utils.ScenarioTypes.START),
            biomass_final_w.value,
            module_w.get_biomass_t2(utils.ScenarioTypes.WITH),
            c_n_ratio,
            moisture_factor.value,
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
            False,
            luc.area,
            project.implementation_years,
            project.capitalization_years,
            input.activity.change_rate.name,
            0,
        ]

        results_w = MathOtherLandUseChanges(*inputs_w)
        results_w.calculate_emissions()

        inputs_wo = [
            biomass_initial.value,
            module_start.get_biomass_t2(utils.ScenarioTypes.START),
            biomass_final_wo.value,
            module_wo.get_biomass_t2(utils.ScenarioTypes.WITHOUT),
            c_n_ratio,
            moisture_factor.value,
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
            False,
            luc.area,
            project.implementation_years,
            project.capitalization_years,
            input.activity.change_rate.name,
            0,
        ]

        results_wo = MathOtherLandUseChanges(*inputs_wo)
        results_wo.calculate_emissions()

        res_w = results_w.result if results_w else MathResult(project.implementation_years, project.capitalization_years)
        res_wo = results_wo.result if results_wo else MathResult(project.implementation_years, project.capitalization_years)

        return (res_w, res_wo)


class AnnualCroppingCalculator(BaseCalculator):
    """
    Calculator for annual cropping modules.
    """

    def calculate(self, aggregate_by=BreakdownTypes.TOTAL) -> tuple[MathResult]:
        """
        Calculate emissions for a single AnnualCropping module.
        """

        input: AnnualCropping = self.data
        project: Project = input.activity.project
        luc: LandUseChange = input.land_use_change
        module_start, module_w, module_wo = get_luc_modules(luc)

        area = luc.area if luc else input.area
        change_rate = input.activity.change_rate
        climate = project.climate
        moisture = project.moisture
        soil_type = project.soil_type

        cm = {"climate": climate, "moisture": moisture}

        fi_start = get_fi_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        fmg_start = get_fmg_data(module_start, climate, moisture, utils.ScenarioTypes.START)
        flu_start = get_flu_data(module_start, climate, moisture, utils.ScenarioTypes.START)

        fi_w = get_fi_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        fmg_w = get_fmg_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)
        flu_w = get_flu_data(module_w, climate, moisture, utils.ScenarioTypes.WITH)

        fi_wo = get_fi_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
        fmg_wo = get_fmg_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)
        flu_wo = get_flu_data(module_wo, climate, moisture, utils.ScenarioTypes.WITHOUT)

        crop_yield_start = input.crop_yield_start if input.crop_yield_start else ipcc.CropYieldStats.objects.get_or_region_average(continent=project.country.region, land_use_type=input.land_use_type_start).average
        crop_yield_w = input.crop_yield_w if input.crop_yield_w else ipcc.CropYieldStats.objects.get_or_region_average(continent=project.country.region, land_use_type=input.land_use_type_w).average
        crop_yield_wo = input.crop_yield_wo if input.crop_yield_wo else ipcc.CropYieldStats.objects.get_or_region_average(continent=project.country.region, land_use_type=input.land_use_type_wo).average

        # General
        soc = ipcc.SoilOrganicCarbon.objects.get(**cm, soil_type=soil_type)
        flu = ipcc.CroplandFLU.objects.get(**cm, land_use_type__name__icontains="Long-Term Cultivated")
        burning_emission_factor = ipcc.BurningEmissionFactor.objects.get(category__name="Agricultural residues")

        minor_burning_emission_factor = None
        if input.minor_land_use_type_start or input.minor_land_use_type_w or input.minor_land_use_type_wo:
            minor_burning_emission_factor = ipcc.BurningEmissionFactor.objects.get(category__name="Agricultural residues")

        math_start_w = None
        math_start_wo = None
        math_w = None
        math_wo = None

        if is_luc_remaining_same(input):
            lut_start = input.land_use_type_start
            minor_lut_start = input.minor_land_use_type_start
            fires_start = ipcc.FiresCombustionFactor.objects.get(land_use_type=lut_start)
            n_estimation_factor_start = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=lut_start)

            try:
                minor_fires_start = ipcc.FiresCombustionFactor.objects.get(land_use_type=minor_lut_start)
                minor_n_estimation_factor_start = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_start)
            except Exception:
                minor_fires_start = None
                minor_n_estimation_factor_start = None

            emission_factors_start = ipcc.DefaultEmissionFactor.objects.get(moisture=moisture, organic_input_type=input.organic_input_type_start)

            inputs_start_w = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                change_rate.value,
                soc.value,
                soc.value,
                input.soc_t2_start,
                input.soc_t2_w,
                fmg_start.value,
                fmg_w.value,
                module_start.fmg_t2_start,
                input.fmg_t2_w,
                flu_start.value,
                flu_w.value,
                module_start.flu_t2_start,
                input.flu_t2_w,
                fi_start.value,
                fi_w.value,
                module_start.fi_t2_start,
                input.fi_t2_w,
                False,
                emission_factors_start.value,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                burning_emission_factor.ch4 if input.residue_management_type_start.name == "Burned" else None,
                fires_start.value,
                input.main_biomass_factor_t2_start,
                n_estimation_factor_start.slope,
                n_estimation_factor_start.intercept,
                crop_yield_start,
                getattr(minor_burning_emission_factor, "ch4", None),
                getattr(minor_fires_start, "value", None),
                input.minor_biomass_factor_t2_start,
                getattr(minor_n_estimation_factor_start, "slope", None),
                getattr(minor_n_estimation_factor_start, "intercept", None),
                input.minor_yield_start,
                burning_emission_factor.n2o if input.residue_management_type_start.name == "Burned" else None,
                input.residue_management_type_start.name == "Retained",
                getattr(minor_burning_emission_factor, "n2o", None),
                getattr(input.minor_residue_management_type_start, "name", None) == "Retained",
                n_estimation_factor_start.n_ag_residues,
                n_estimation_factor_start.rs_t,
                n_estimation_factor_start.n_bg_t,
                getattr(minor_n_estimation_factor_start, "n_ag_residues", None),
                getattr(minor_n_estimation_factor_start, "rs_t", None),
                getattr(minor_n_estimation_factor_start, "n_bg_t", None),
                0,
            ]

            math_start_w = AnnualCropland(*inputs_start_w)
            math_start_w.calculate_emissions()

        if is_with(input):
            lut_w = input.land_use_type_w
            minor_lut_w = input.minor_land_use_type_w
            fires_w = ipcc.FiresCombustionFactor.objects.get(land_use_type=lut_w)
            n_estimation_factor_w = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=lut_w)

            try:
                minor_fires_w = ipcc.FiresCombustionFactor.objects.get(land_use_type=lut_w)

                minor_n_estimation_factor_w = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_w)
            except Exception:
                minor_fires_w = None

                minor_n_estimation_factor_w = None

            emission_factors_w = ipcc.DefaultEmissionFactor.objects.get(moisture=moisture, organic_input_type=input.organic_input_type_w)

            inputs_w = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                change_rate.value,
                soc.value,
                soc.value,
                input.soc_t2_start,
                input.soc_t2_w,
                fmg_start.value,
                fmg_w.value,
                module_start.fmg_t2_start,
                input.fmg_t2_w,
                flu_start.value,
                flu_w.value,
                module_start.flu_t2_start,
                input.flu_t2_w,
                fi_start.value,
                fi_w.value,
                module_start.fi_t2_start,
                input.fi_t2_w,
                True,
                emission_factors_w.value,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                burning_emission_factor.ch4 if input.residue_management_type_w.name == "Burned" else None,
                fires_w.value,
                input.main_biomass_factor_t2_start,
                n_estimation_factor_w.slope,
                n_estimation_factor_w.intercept,
                crop_yield_w,
                getattr(minor_burning_emission_factor, "ch4", None),
                getattr(minor_fires_w, "value", None),
                input.minor_biomass_factor_t2_w,
                getattr(minor_n_estimation_factor_w, "slope", None),
                getattr(minor_n_estimation_factor_w, "intercept", None),
                input.minor_yield_w,
                burning_emission_factor.n2o if input.residue_management_type_w.name == "Burned" else None,
                input.residue_management_type_w.name == "Retained",
                getattr(minor_burning_emission_factor, "n2o", None),
                getattr(input.minor_residue_management_type_w, "name", None) == "Retained",
                n_estimation_factor_w.n_ag_residues,
                n_estimation_factor_w.rs_t,
                n_estimation_factor_w.n_bg_t,
                getattr(minor_n_estimation_factor_w, "n_ag_residues", None),
                getattr(minor_n_estimation_factor_w, "rs_t", None),
                getattr(minor_n_estimation_factor_w, "n_bg_t", None),
                0,
            ]

            math_w = AnnualCropland(*inputs_w)
            math_w.calculate_emissions()

        if is_business_as_usual(input):
            lut_start = input.land_use_type_start
            lut_wo = input.land_use_type_wo
            minor_lut_start = input.minor_land_use_type_start
            fires_start = ipcc.FiresCombustionFactor.objects.get(land_use_type=lut_start)
            n_estimation_factor_start = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=lut_start)

            try:
                minor_fires_start = ipcc.FiresCombustionFactor.objects.get(land_use_type=minor_lut_start)
                minor_n_estimation_factor_start = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_start)
            except Exception:
                minor_fires_start = None
                minor_n_estimation_factor_start = None

            emission_factors_start = ipcc.DefaultEmissionFactor.objects.get(moisture=moisture, organic_input_type=input.organic_input_type_start)

            inputs_start_wo = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                change_rate.value,
                soc.value,
                soc.value,
                input.soc_t2_start,
                input.soc_t2_wo,
                fmg_start.value,
                fmg_wo.value,
                input.fmg_t2_start,
                input.fmg_t2_wo,
                flu_start.value,
                flu_wo.value,
                input.flu_t2_start,
                input.flu_t2_wo,
                fi_start.value,
                fi_wo.value,
                input.fi_t2_start,
                input.fi_t2_wo,
                False,
                emission_factors_start.value,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                burning_emission_factor.ch4 if input.residue_management_type_start.name == "Burned" else None,
                fires_start.value,
                input.main_biomass_factor_t2_start,
                n_estimation_factor_start.slope,
                n_estimation_factor_start.intercept,
                crop_yield_start,
                getattr(minor_burning_emission_factor, "ch4", None),
                getattr(minor_fires_start, "value", None),
                input.minor_biomass_factor_t2_start,
                getattr(minor_n_estimation_factor_start, "slope", None),
                getattr(minor_n_estimation_factor_start, "intercept", None),
                input.minor_yield_start,
                burning_emission_factor.n2o if input.residue_management_type_start.name == "Burned" else None,
                input.residue_management_type_start.name == "Retained",
                getattr(minor_burning_emission_factor, "n2o", None),
                getattr(input.minor_residue_management_type_start, "name", None) == "Retained",
                n_estimation_factor_start.n_ag_residues,
                n_estimation_factor_start.rs_t,
                n_estimation_factor_start.n_bg_t,
                getattr(minor_n_estimation_factor_start, "n_ag_residues", None),
                getattr(minor_n_estimation_factor_start, "rs_t", None),
                getattr(minor_n_estimation_factor_start, "n_bg_t", None),
                0,
            ]

            math_start_wo = AnnualCropland(*inputs_start_wo)
            math_start_wo.calculate_emissions()

        if is_without(input):
            lut_start = input.land_use_type_start
            lut_wo = input.land_use_type_wo

            minor_lut_start = input.minor_land_use_type_start
            minor_lut_wo = input.minor_land_use_type_wo

            fires_wo = ipcc.FiresCombustionFactor.objects.get(land_use_type=lut_wo)
            n_estimation_factor_wo = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=lut_wo)

            try:
                minor_fires_wo = ipcc.FiresCombustionFactor.objects.get(land_use_type=lut_wo)

                minor_n_estimation_factor_wo = ipcc.CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_lut_wo)

            except Exception:
                minor_fires_wo = None

                minor_n_estimation_factor_wo = None

            emission_factors_wo = ipcc.DefaultEmissionFactor.objects.get(moisture=moisture, organic_input_type=input.organic_input_type_wo)

            inputs_wo = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                change_rate.value,
                soc.value,
                soc.value,
                input.soc_t2_start,
                input.soc_t2_wo,
                fmg_start.value,
                fmg_wo.value,
                module_start.fmg_t2_start,
                input.fmg_t2_wo,
                flu.value,
                flu.value,
                module_start.flu_t2_start,
                input.flu_t2_wo,
                fi_start.value,
                fi_wo.value,
                module_start.fi_t2_start,
                input.fi_t2_wo,
                True,
                emission_factors_wo.value,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                burning_emission_factor.ch4 if input.residue_management_type_start.name == "Burned" else None,
                fires_wo.value,
                input.main_biomass_factor_t2_start,
                n_estimation_factor_wo.slope,
                n_estimation_factor_wo.intercept,
                crop_yield_wo,
                getattr(minor_burning_emission_factor, "ch4", None),
                getattr(minor_fires_wo, "value", None),
                input.minor_biomass_factor_t2_wo,
                getattr(minor_n_estimation_factor_wo, "slope", None),
                getattr(minor_n_estimation_factor_wo, "intercept", None),
                input.minor_yield_wo,
                burning_emission_factor.n2o if input.residue_management_type_wo.name == "Burned" else None,
                input.residue_management_type_wo.name == "Retained",
                getattr(minor_burning_emission_factor, "n2o", None),
                getattr(input.minor_residue_management_type_wo, "name", None) == "Retained",
                n_estimation_factor_wo.n_ag_residues,
                n_estimation_factor_wo.rs_t,
                n_estimation_factor_wo.n_bg_t,
                getattr(minor_n_estimation_factor_wo, "n_ag_residues", None),
                getattr(minor_n_estimation_factor_wo, "rs_t", None),
                getattr(minor_n_estimation_factor_wo, "n_bg_t", None),
                0,
            ]

            math_wo = AnnualCropland(*inputs_wo)
            math_wo.calculate_emissions()

        res_start_w = math_start_w.result if math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        res_start_wo = math_start_wo.result if math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        res_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        res_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        return (res_w + res_start_w, res_wo + res_start_wo)

    def defaults(self) -> DefaultData:
        self.calculate()

        module: AnnualCropping = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if is_luc_remaining_same(module):
            math_start = AnnualCropland(*self.inputs_start_w)
            math_start_defaults = math_start.evaluate_tier_2_defaults()
            defaults_start.update(math_start_defaults.start)
            defaults_start.update(math_start_defaults.other)
        elif is_business_as_usual(module):
            math_start_wo = AnnualCropland(*self.inputs_start_wo)
            math_start_wo_defaults = math_start_wo.evaluate_tier_2_defaults()
            defaults_start.update(math_start_wo_defaults.start)
            defaults_start.update(math_start_wo_defaults.other)

        if is_with(module):
            math_w = AnnualCropland(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.start)
            defaults_w.update(math_w_defaults.other)

        if is_without(module):
            math_wo = AnnualCropland(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.start)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class PerennialCroppingCalculator(BaseCalculator):
    """
    Calculator for perennial cropping.
    """

    def calculate(self, aggregate_by=BreakdownTypes.TOTAL) -> list[Result]:
        """
        Calculate emissions for a single PerennialCropping module.
        """

        module: PerennialCropping = self.data
        project = module.activity.project
        activity: Activity = module.activity
        luc: LandUseChange = module.land_use_change
        climate = activity.climate_t2 or project.climate
        moisture = activity.moisture_t2 or project.moisture
        region = project.country.region
        change_rate = activity.change_rate

        soc = ipcc.SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=project.soil_type)
        grassland_soc = get_grassland_soc(luc)

        soc_start = grassland_soc.value if grassland_soc else soc.value
        soc_w = soc.value
        soc_wo = soc.value

        area = luc.area if luc else module.area

        cmc = {
            "climate": climate,
            "moisture": moisture,
            "continent": region,
        }

        burning_emission_factor = ipcc.BurningEmissionFactor.objects.get(category__name="Savanna and grassland")

        fires_combustion_factor_start = ipcc.FiresCombustionFactor.objects.get_or_other(land_use_type=module.land_use_type_start)
        fires_combustion_factor_w = ipcc.FiresCombustionFactor.objects.get_or_other(land_use_type=module.land_use_type_w)
        fires_combustion_factor_wo = ipcc.FiresCombustionFactor.objects.get_or_other(land_use_type=module.land_use_type_wo)

        ag_default_start = ipcc.PerennialAGB.objects.get_or_default(**cmc, land_use_type=module.land_use_type_start)
        ag_default_w = ipcc.PerennialAGB.objects.get_or_default(**cmc, land_use_type=module.land_use_type_w)
        ag_default_wo = ipcc.PerennialAGB.objects.get_or_default(**cmc, land_use_type=module.land_use_type_wo)

        agb_max_c_start = ipcc.PerennialMaxAGB.objects.get(climate=climate, land_use_type=module.land_use_type_start)
        agb_max_c_w = ipcc.PerennialMaxAGB.objects.get(climate=climate, land_use_type=module.land_use_type_w)
        agb_max_c_wo = ipcc.PerennialMaxAGB.objects.get(climate=climate, land_use_type=module.land_use_type_wo)

        bg_default_start = ipcc.PerennialBGB.objects.get_or_default(**cmc, land_use_type=module.land_use_type_start)
        bg_default_w = ipcc.PerennialBGB.objects.get_or_default(**cmc, land_use_type=module.land_use_type_w)
        bg_default_wo = ipcc.PerennialBGB.objects.get_or_default(**cmc, land_use_type=module.land_use_type_wo)

        flu_start = get_flu_data(module, climate, moisture, utils.ScenarioTypes.START)
        flu_w = get_flu_data(module, climate, moisture, utils.ScenarioTypes.WITH)
        flu_wo = get_flu_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)

        fi_start = get_fi_data(module, climate, moisture, utils.ScenarioTypes.START)
        fi_w = get_fi_data(module, climate, moisture, utils.ScenarioTypes.WITH)
        fi_wo = get_fi_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)

        fmg_start = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.START)
        fmg_w = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.WITH)
        fmg_wo = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)

        default_fire_periodicity = AnnualCroplandParameter.objects.get(name="default_fire_periodicity")

        math_start_w = None
        math_start_wo = None
        math_w = None
        math_wo = None

        if is_luc_remaining_same(module):
            inputs_start_w = [
                area,
                0,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.is_biomass_burned_start,
                burning_emission_factor.n2o,
                burning_emission_factor.ch4,
                fires_combustion_factor_start.value,
                default_fire_periodicity.value,
                module.fire_periodicity_t2_start,
                module.residue_burned_t2_start,
                ag_default_start.value,
                module.ag_t2_start,
                agb_max_c_start.value,
                bg_default_start.value,
                module.bg_t2_start,
                soc_start,
                soc_w,
                module.soc_t2_start,
                module.soc_t2_w,
                fmg_start.value,
                fmg_w.value,
                module.fmg_t2_start,
                module.fmg_t2_w,
                flu_start.value,
                flu_w.value,
                module.flu_t2_start,
                module.flu_t2_w,
                fi_start.value,
                fi_w.value,
                module.fi_t2_start,
                module.fi_t2_w,
                False,
                0,  # Delay
            ]

            math_start_w = PerennialCropland(*inputs_start_w)
            math_start_w.calculate_emissions()

        if is_business_as_usual(module):
            input_start_wo = [
                area,
                0,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.is_biomass_burned_start,
                burning_emission_factor.n2o,
                burning_emission_factor.ch4,
                fires_combustion_factor_start.value,
                default_fire_periodicity.value,
                module.fire_periodicity_t2_start,
                module.residue_burned_t2_start,
                ag_default_start.value,
                module.ag_t2_start,
                agb_max_c_start.value,
                bg_default_start.value,
                module.bg_t2_start,
                soc_start,
                soc_wo,
                module.soc_t2_start,
                module.soc_t2_wo,
                fmg_start.value,
                fmg_wo.value,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                flu_start.value,
                flu_wo.value,
                module.flu_t2_start,
                module.flu_t2_wo,
                fi_start.value,
                fi_wo.value,
                module.fi_t2_start,
                module.fi_t2_wo,
                False,
                0,  # Delay
            ]

            math_start_wo = PerennialCropland(*input_start_wo)
            math_start_wo.calculate_emissions()

        if is_with(module):
            inputs_w = [
                0,
                area,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.is_biomass_burned_w,
                burning_emission_factor.n2o,
                burning_emission_factor.ch4,
                fires_combustion_factor_w.value,
                default_fire_periodicity.value,
                module.fire_periodicity_t2_w,
                module.residue_burned_t2_w,
                ag_default_w.value,
                module.ag_t2_w,
                agb_max_c_w.value,
                bg_default_w.value,
                module.bg_t2_w,
                soc_start,
                soc_w,
                module.soc_t2_start,
                module.soc_t2_w,
                fmg_start.value,
                fmg_w.value,
                module.fmg_t2_start,
                module.fmg_t2_w,
                flu_start.value,
                flu_w.value,
                module.flu_t2_start,
                module.flu_t2_w,
                fi_start.value,
                fi_w.value,
                module.fi_t2_start,
                module.fi_t2_w,
                True,
                0,  # Delay
            ]

            math_w = PerennialCropland(*inputs_w)
            math_w.calculate_emissions()

        if is_without(module):
            inputs_wo = [
                0,
                area,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.is_biomass_burned_wo,
                burning_emission_factor.n2o,
                burning_emission_factor.ch4,
                fires_combustion_factor_wo.value,
                default_fire_periodicity.value,
                module.fire_periodicity_t2_wo,
                module.residue_burned_t2_wo,
                ag_default_wo.value,
                module.ag_t2_wo,
                agb_max_c_wo.value,
                bg_default_wo.value,
                module.bg_t2_wo,
                soc_start,
                soc_wo,
                module.soc_t2_start,
                module.soc_t2_wo,
                fmg_start.value,
                fmg_wo.value,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                flu_start.value,
                flu_wo.value,
                module.flu_t2_start,
                module.flu_t2_wo,
                fi_start.value,
                fi_wo.value,
                module.fi_t2_start,
                module.fi_t2_wo,
                False,
                0,  # Delay
            ]

            math_wo = PerennialCropland(*inputs_wo)
            math_wo.calculate_emissions()

        results_start_w = math_start_w.result if math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        results_start_wo = math_start_wo.result if math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w + results_start_w, results_wo + results_start_wo)

        return results_tuple


class FloodedRiceCalculator(BaseCalculator):
    """
    Calculator for flooded rice.
    """

    def calculate(self) -> Result:
        module: FloodedRice = self.data
        activity: Activity = module.activity
        project: Project = activity.project
        luc: LandUseChange = module.land_use_change
        area = luc.area if luc.area else module.area

        climate: Climate = activity.climate_t2 or project.climate
        moisture: Moisture = activity.moisture_t2 or project.moisture
        region: Region = project.country.region
        soil_type: SoilType = project.soil_type

        soc = ipcc.SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type)
        grassland_soc = get_grassland_soc(luc)

        rice_ef = ipcc.RiceDefaultEmissionFactor.objects.get(continent=region)
        yield_ref = ipcc.RiceYield.objects.get(continent=region)

        soc_start = grassland_soc.value if grassland_soc else soc.value
        soc_w = soc.value
        soc_wo = soc.value

        flu_start = get_flu_data(module, climate, moisture, utils.ScenarioTypes.START)
        flu_w = get_flu_data(module, climate, moisture, utils.ScenarioTypes.WITH)
        flu_wo = get_flu_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)

        fmg_start = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.START)
        fmg_w = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.WITH)
        fmg_wo = get_fmg_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)

        fi_start = get_fi_data(module, climate, moisture, utils.ScenarioTypes.START)
        fi_w = get_fi_data(module, climate, moisture, utils.ScenarioTypes.WITH)
        fi_wo = get_fi_data(module, climate, moisture, utils.ScenarioTypes.WITHOUT)

        sfw_start = ipcc.RiceSFW.objects.get(water_management_type_after_cultivation=module.water_management_type_after_cultivation_start)
        sfw_w = ipcc.RiceSFW.objects.get(water_management_type_after_cultivation=module.water_management_type_after_cultivation_w)
        sfw_wo = ipcc.RiceSFW.objects.get(water_management_type_after_cultivation=module.water_management_type_after_cultivation_wo)

        sfp_start = ipcc.RiceSFP.objects.get(water_management_type_before_cultivation=module.water_management_type_before_cultivation_start)
        sfp_w = ipcc.RiceSFP.objects.get(water_management_type_before_cultivation=module.water_management_type_before_cultivation_w)
        sfp_wo = ipcc.RiceSFP.objects.get(water_management_type_before_cultivation=module.water_management_type_before_cultivation_wo)

        cfoa_start = ipcc.RiceSFO.objects.get(organic_amendment_type=module.organic_amendment_type_start)
        cfoa_w = ipcc.RiceSFO.objects.get(organic_amendment_type=module.organic_amendment_type_w)
        cfoa_wo = ipcc.RiceSFO.objects.get(organic_amendment_type=module.organic_amendment_type_wo)

        n_estimation_factor = ipcc.CropNitrousEstimationDefaultFactor.objects.get(land_use_type__name="Rice")
        burning_emission_factor = ipcc.BurningEmissionFactor.objects.get(category__name="Agricultural residues")
        rice_cf = ipcc.FiresCombustionFactor.objects.get(land_use_type__name="Rice")

        math_start_w = None
        math_start_wo = None
        math_w = None
        math_wo = None

        if is_luc_remaining_same(module):
            self.inputs_start_w = [
                *[area, 0],
                rice_ef.value,
                module.efc_t2_start,
                sfw_start.value,
                module.sfw_t2_start,
                sfp_start.value,
                module.sfp_t2_start,
                cfoa_start.value,
                module.sfo_t2_start,
                module.efi_t2_start,
                yield_ref.value,
                module.crop_yield_start,
                n_estimation_factor.slope,
                n_estimation_factor.intercept,
                module.rice_straw_t2_start,
                burning_emission_factor.ch4,
                rice_cf.value,
                burning_emission_factor.n2o,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                project.gw_potential.ch4,
                rice_ef.cultivation_period,
                module.cultivation_period_start,
                soc_start,
                soc_w,
                module.soc_t2_start,
                module.soc_t2_w,
                fmg_start.value,
                fmg_w.value,
                module.fmg_t2_start,
                module.fmg_t2_w,
                flu_start.value,
                flu_w.value,
                module.flu_t2_start,
                module.flu_t2_w,
                fi_start.value,
                fi_w.value,
                module.fi_t2_start,
                module.fi_t2_w,
                True,
                0,  # Delay
            ]

            math_start_w = MathFloodedRice(*self.inputs_start_w)
            math_start_w.calculate_emissions()

        if is_business_as_usual(module):
            self.inputs_start_wo = [
                *[area, 0],
                rice_ef.value,
                module.efc_t2_start,
                sfw_start.value,
                module.sfw_t2_start,
                sfp_start.value,
                module.sfp_t2_start,
                cfoa_start.value,
                module.sfo_t2_start,
                module.efi_t2_start,
                yield_ref.value,
                module.crop_yield_start,
                n_estimation_factor.slope,
                n_estimation_factor.intercept,
                module.rice_straw_t2_start,
                burning_emission_factor.ch4,
                rice_cf.value,
                burning_emission_factor.n2o,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                project.gw_potential.ch4,
                rice_ef.cultivation_period,
                module.cultivation_period_start,
                soc_start,
                soc_wo,
                module.soc_t2_start,
                module.soc_t2_wo,
                fmg_start.value,
                fmg_wo.value,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                flu_start.value,
                flu_wo.value,
                module.flu_t2_start,
                module.flu_t2_wo,
                fi_start.value,
                fi_wo.value,
                module.fi_t2_start,
                module.fi_t2_wo,
                True,
                0,  # Delay
            ]

            math_start_wo = MathFloodedRice(*self.inputs_start_wo)
            math_start_wo.calculate_emissions()

        if is_with(module):
            self.inputs_w = [
                *[0, area],
                rice_ef.value,
                module.efc_t2_w,
                sfw_w.value,
                module.sfw_t2_w,
                sfp_w.value,
                module.sfp_t2_w,
                cfoa_w.value,
                module.sfo_t2_w,
                module.efi_t2_w,
                yield_ref.value,
                module.crop_yield_w,
                n_estimation_factor.slope,
                n_estimation_factor.intercept,
                module.rice_straw_t2_w,
                burning_emission_factor.ch4,
                rice_cf.value,
                burning_emission_factor.n2o,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                project.gw_potential.ch4,
                rice_ef.cultivation_period,
                module.cultivation_period_w,
                soc_start,
                soc_w,
                module.soc_t2_start,
                module.soc_t2_w,
                fmg_start.value,
                fmg_w.value,
                module.fmg_t2_start,
                module.fmg_t2_w,
                flu_start.value,
                flu_w.value,
                module.flu_t2_start,
                module.flu_t2_w,
                fi_start.value,
                fi_w.value,
                module.fi_t2_start,
                module.fi_t2_w,
                True,
                0,  # Delay
            ]

            math_w = MathFloodedRice(*self.inputs_w)
            math_w.calculate_emissions()

        if is_without(module):
            self.inputs_wo = [
                *[0, area],
                rice_ef.value,
                module.efc_t2_wo,
                sfw_wo.value,
                module.sfw_t2_wo,
                sfp_wo.value,
                module.sfp_t2_wo,
                cfoa_wo.value,
                module.sfo_t2_wo,
                module.efi_t2_wo,
                yield_ref.value,
                module.crop_yield_wo,
                n_estimation_factor.slope,
                n_estimation_factor.intercept,
                module.rice_straw_t2_wo,
                burning_emission_factor.ch4,
                rice_cf.value,
                burning_emission_factor.n2o,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                project.gw_potential.ch4,
                rice_ef.cultivation_period,
                module.cultivation_period_wo,
                soc_start,
                soc_wo,
                module.soc_t2_start,
                module.soc_t2_wo,
                fmg_start.value,
                fmg_wo.value,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                flu_start.value,
                flu_wo.value,
                module.flu_t2_start,
                module.flu_t2_wo,
                fi_start.value,
                fi_wo.value,
                module.fi_t2_start,
                module.fi_t2_wo,
                False,
                0,  # Delay
            ]

            math_wo = MathFloodedRice(*self.inputs_wo)
            math_wo.calculate_emissions()

        results_start_w = math_start_w.result if math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        results_start_wo = math_start_wo.result if math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w + results_start_w, results_wo + results_start_wo)

        return results_tuple

    def defaults(self) -> DefaultData:
        self.calculate()

        module: FloodedRice = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if is_luc_remaining_same(module):
            math_start = MathFloodedRice(*self.inputs_start_w)
            math_start_defaults = math_start.evaluate_tier_2_defaults()
            defaults_start.update(math_start_defaults.start)
            defaults_start.update(math_start_defaults.other)
        elif is_business_as_usual(module):
            math_start_wo = MathFloodedRice(*self.inputs_start_wo)
            math_start_wo_defaults = math_start_wo.evaluate_tier_2_defaults()
            defaults_start.update(math_start_wo_defaults.start)
            defaults_start.update(math_start_wo_defaults.other)

        if is_with(module):
            math_w = MathFloodedRice(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.start)
            defaults_w.update(math_w_defaults.other)

        if is_without(module):
            math_wo = MathFloodedRice(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.start)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class GrasslandCalculator(BaseCalculator):
    """
    Calculator for grassland.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Grassland module.
        """

        module: Grassland = self.data
        activity: Activity = module.activity
        project: Project = activity.project
        luc: LandUseChange = module.land_use_change

        # duration = activity.duration_t2 or project.implementation_years
        # # TODO: Is this assuming that the activity start_year must be > project start_year?
        # delay = ((activity.start_year_t2 or 0) - project.start_year) or 0
        # capitalization = project.implementation_years - duration + project.capitalization_years

        change_rate = module.activity.change_rate
        ef = ipcc.BurningEmissionFactor.objects.get(category__name="Savanna and grassland")
        agb = ipcc.GrasslandAGB.objects.get(climate=project.climate, moisture=project.moisture)
        cf = GrasslandParameter.objects.get(name="default_combustion_factor").value
        soc = ipcc.SoilOrganicCarbon.objects.get(climate=project.climate, moisture=project.moisture, soil_type=project.soil_type)

        area = luc.area if luc and luc.area else module.area

        math_start_w = None
        math_start_wo = None
        math_w = None
        math_wo = None

        if is_luc_remaining_same(module):
            soc_start = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module.grassland_management_type_start,
                climate=project.climate,
            )
            soc_w = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module.grassland_management_type_w,
                climate=project.climate,
            )

            self.inputs_start_w = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.fire_periodicity_start,
                module.is_fire_used_start,
                ef.ch4,
                ef.n2o,
                agb.value,
                module.get_biomass_t2(utils.ScenarioTypes.START),
                cf,
                module.combustion_factor_t2_start,
                soc.value,
                soc.value,
                module.soc_t2_start,
                module.soc_t2_w,
                False,
                soc_start.fmg,
                soc_w.fmg,
                module.fmg_t2_start,
                module.fmg_t2_w,
                soc_start.flu,
                soc_w.flu,
                module.flu_t2_start,
                module.flu_t2_w,
                soc_start.fi,
                soc_w.fi,
                module.fi_t2_start,
                module.fi_t2_w,
                0,
            ]

            math_start_w = MathGrassland(*self.inputs_start_w)
            math_start_w.calculate_emissions()

        if is_with(module):
            soc_start = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module.grassland_management_type_start,
                climate=project.climate,
            )
            soc_w = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module.grassland_management_type_w,
                climate=project.climate,
            )

            self.inputs_w = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.fire_periodicity_w,
                module.is_fire_used_w,
                ef.ch4,
                ef.n2o,
                agb.value,
                module.get_biomass_t2(utils.ScenarioTypes.WITH),
                cf,
                module.combustion_factor_t2_start,
                soc.value,
                soc.value,
                module.soc_t2_start,
                module.soc_t2_w,
                True,
                soc_start.fmg,
                soc_w.fmg,
                module.fmg_t2_start,
                module.fmg_t2_w,
                soc_start.flu,
                soc_w.flu,
                module.flu_t2_start,
                module.flu_t2_w,
                soc_start.fi,
                soc_w.fi,
                module.fi_t2_start,
                module.fi_t2_w,
                0,
            ]

            math_w = MathGrassland(*self.inputs_w)
            math_w.calculate_emissions()

        if is_business_as_usual(module):
            soc_start = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module.grassland_management_type_start,
                climate=project.climate,
            )
            soc_wo = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module.grassland_management_type_wo,
                climate=project.climate,
            )

            self.inputs_start_wo = [
                *[area, 0],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.fire_periodicity_start,
                module.is_fire_used_start,
                ef.ch4,
                ef.n2o,
                agb.value,
                module.get_biomass_t2(utils.ScenarioTypes.START),
                cf,
                module.combustion_factor_t2_start,
                soc.value,
                soc.value,
                module.soc_t2_start,
                module.soc_t2_wo,
                False,
                soc_start.fmg,
                soc_wo.fmg,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                soc_start.flu,
                soc_wo.flu,
                module.flu_t2_start,
                module.flu_t2_wo,
                soc_start.fi,
                soc_wo.fi,
                module.fi_t2_start,
                module.fi_t2_wo,
                0,
            ]

            math_start_wo = MathGrassland(*self.inputs_start_wo)
            math_start_wo.calculate_emissions()

        if is_without(module):
            soc_start = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module.grassland_management_type_start,
                climate=project.climate,
            )
            soc_wo = ipcc.GrasslandStockExchangeFactor.objects.get(
                grassland_management_type=module.grassland_management_type_wo,
                climate=project.climate,
            )

            self.inputs_wo = [
                *[0, area],
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
                project.gw_potential.n2o,
                project.gw_potential.ch4,
                module.fire_periodicity_wo,
                module.is_fire_used_wo,
                ef.ch4,
                ef.n2o,
                agb.value,
                module.get_biomass_t2(utils.ScenarioTypes.WITHOUT),
                cf,
                module.combustion_factor_t2_start,
                soc.value,
                soc.value,
                module.soc_t2_start,
                module.soc_t2_wo,
                True,
                soc_start.fmg,
                soc_wo.fmg,
                module.fmg_t2_start,
                module.fmg_t2_wo,
                soc_start.flu,
                soc_wo.flu,
                module.flu_t2_start,
                module.flu_t2_wo,
                soc_start.fi,
                soc_wo.fi,
                module.fi_t2_start,
                module.fi_t2_wo,
                0,
            ]

            math_wo = MathGrassland(*self.inputs_wo)
            math_wo.calculate_emissions()

        res_start_w = math_start_w.result if math_start_w else MathResult(project.implementation_years, project.capitalization_years)
        res_start_wo = math_start_wo.result if math_start_wo else MathResult(project.implementation_years, project.capitalization_years)
        res_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        res_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        return (res_w + res_start_w, res_wo + res_start_wo)

    def defaults(self):
        self.calculate()

        module: Grassland = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if is_luc_remaining_same(module):
            math_start = MathGrassland(*self.inputs_start_w)
            math_start_defaults = math_start.evaluate_tier_2_defaults()
            defaults_start.update(math_start_defaults.start)
            defaults_start.update(math_start_defaults.other)
        elif is_business_as_usual(module):
            math_start = MathGrassland(*self.inputs_start_wo)
            math_start_defaults = math_start.evaluate_tier_2_defaults()
            defaults_start.update(math_start_defaults.start)
            defaults_start.update(math_start_defaults.other)

        if is_with(module):
            math_w = MathGrassland(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.end)
            defaults_w.update(math_w_defaults.other)

        if is_without(module):
            math_wo = MathGrassland(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.end)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class SmallFisheryCalculator(BaseCalculator):
    """
    Calculator for small fishery.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single SmallFishery module.
        """

        module: SmallFishery = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        ef_diesel_default_list = ipcc.EnergyDefaultEmissionFactor.objects.filter(fuel_type__fuel_use_type__name__contains="Off-Road")

        # Average of all default emission factors for gasoil/diesel
        ef_diesel_default = sum([ef.t_co2_eq for ef in ef_diesel_default_list]) / len(ef_diesel_default_list)

        fui_default_start = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_start)
        fui_default_w = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_w)
        fui_default_wo = ipcc.SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_wo)

        lost_refrigerant_default = SmallFisheryParameter.objects.get(name="lost_refrigerant_default").value
        tonnes_ice_default = SmallFisheryParameter.objects.get(name="tonnes_ice_default").value
        kw_tonnes = SmallFisheryParameter.objects.get(name="kw_tonnes").value

        electricity_emission = ipcc.ElectricityEmission.objects.get(country=project.country, continent=project.country.region)

        math_w = None
        math_wo = None

        if is_with(module):
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

            math_w = MathFishery(*self.inputs_w)
            math_w.calculate_emissions()

        if is_without(module):
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

            math_wo = MathFishery(*self.inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple

    def defaults(self):
        self.calculate()

        module: SmallFishery = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if is_with(module):
            math_w = MathFishery(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.end)
            defaults_w.update(math_w_defaults.other)

        if is_without(module):
            math_wo = MathFishery(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.end)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class LargeFisheryCalculator(BaseCalculator):
    """
    Calculator for large fishery.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single LargeFishery module.
        """

        module: LargeFishery = self.data
        project = module.activity.project
        ef_diesel_default_list = ipcc.EnergyDefaultEmissionFactor.objects.filter(fuel_type__fuel_use_type__name__contains="Off-Road")

        # Average of all default emission factors for gasoil/diesel
        ef_diesel_default = sum([ef.t_co2_eq for ef in ef_diesel_default_list]) / len(ef_diesel_default_list)

        fui_default_start = ipcc.LargeFisheryFUI.objects.get_value_or_average(
            fish_type=module.fish_type,
            gear_type=module.gear_type_start,
        )
        fui_default_w = ipcc.LargeFisheryFUI.objects.get_value_or_average(
            fish_type=module.fish_type,
            gear_type=module.gear_type_w,
        )
        fui_default_wo = ipcc.LargeFisheryFUI.objects.get_value_or_average(
            fish_type=module.fish_type,
            gear_type=module.gear_type_wo,
        )

        lost_refrigerant_default = LargeFisheryParameter.objects.get(name="lost_refrigerant_default").value
        tonnes_ice_default = LargeFisheryParameter.objects.get(name="tonnes_ice_default").value
        kw_tonnes = LargeFisheryParameter.objects.get(name="kw_tonnes").value

        electricity_country = module.inshore_ice_production_country_t2 if module.inshore_ice_production_country_t2 else project.country

        electricity_emission = ipcc.ElectricityEmission.objects.get(country=electricity_country, continent=project.country.region)

        math_w = None
        math_wo = None

        if is_with(module):
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

            math_w = MathFishery(*self.inputs_w)
            math_w.calculate_emissions()

        if is_without(module):
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

            math_wo = MathFishery(*self.inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple

    def defaults(self):
        self.calculate()

        module: LargeFishery = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if is_with(module):
            math_w = MathFishery(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.end)
            defaults_w.update(math_w_defaults.other)

        if is_without(module):
            math_wo = MathFishery(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.end)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class AquacultureCalculator(BaseCalculator):
    """
    Calculator for aquaculture.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Aquaculture module.
        """

        module: Aquaculture = self.data
        change_rate = module.activity.change_rate
        project: Project = module.activity.project

        NITROUS_EF_DEFAULT = AquacultureParameter.objects.get(name="nitrous_ef_default").value

        # TODO: This will now be used in the inputs module for feed
        FEED_EF_DEFAULT = AquacultureParameter.objects.get(name="feed_ef_default").value

        math_w = None
        math_wo = None

        if is_with(module):
            inputs_w = [
                module.annual_production_start,
                module.annual_production_w,
                NITROUS_EF_DEFAULT,
                module.n2o_from_production_t2_start,
                module.n2o_from_production_t2_w,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
            ]

            math_w = MathAquaculture(*inputs_w)
            math_w.calculate_emissions()

        if is_without(module):
            inputs_wo = [
                module.annual_production_start,
                module.annual_production_wo,
                NITROUS_EF_DEFAULT,
                module.n2o_from_production_t2_start,
                module.n2o_from_production_t2_wo,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                change_rate.name,
            ]

            math_wo = MathAquaculture(*inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple


class InputCalculator(BaseCalculator):
    """
    Calculator for Inputs macromodule
    """

    def calculate(self) -> list[MathResult]:
        input: Input = self.data
        project: Project = input.activity.project

        results_w = MathResult(project.implementation_years, project.capitalization_years)
        results_wo = MathResult(project.implementation_years, project.capitalization_years)

        for entry in input.input_entries.all():
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

    def calculate(self) -> list[Result]:
        module: InputEntry = self.data
        activity: Activity = module.parent.activity
        project: Project = activity.project

        ref = ipcc.InputReference.objects.get(gw_potential=project.gw_potential, input_type=module.input_type)
        ef = ipcc.InputEmissionFactor.objects.get(input_type=module.input_type, climate=project.climate, moisture=project.moisture)

        math_w = None
        math_wo = None

        if is_with(module):
            inputs_w = [
                module.value_start,
                module.value_w,
                activity.change_rate.name,
                ef.co2_value,
                module.co2_emissions_t2,
                ref.co2_multiplier,
                ref.co2_emissions_multiplier,
                project.implementation_years,
                project.capitalization_years,
                ef.n2o_value,
                module.n2o_emissions_t2,
                ref.n2o_quantity_multiplier,
                ref.n2o_emissions_multiplier,
                ef.co2_eq_value,
                module.co2_e_emissions_t2,
                ref.production_quantity_multiplier,
                ref.production_emissions_multiplier,
            ]

            math_w = MathInputs(*inputs_w)
            math_w = math_w.calculate_emissions()

        if is_without(module):
            inputs_wo = [
                module.value_start,
                module.value_wo,
                activity.change_rate.name,
                ef.co2_value,
                module.co2_emissions_t2,
                ref.co2_multiplier,
                ref.co2_emissions_multiplier,
                project.implementation_years,
                project.capitalization_years,
                ef.n2o_value,
                module.n2o_emissions_t2,
                ref.n2o_quantity_multiplier,
                ref.n2o_emissions_multiplier,
                ef.co2_eq_value,
                module.co2_e_emissions_t2,
                ref.production_quantity_multiplier,
                ref.production_emissions_multiplier,
            ]

            math_wo = MathInputs(*inputs_wo)
            math_wo = math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple

    def defaults(self) -> DefaultData:
        self.calculate()

        module: InputEntry = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if is_with(module):
            math_w = MathInputs(*self.inputs_w)
            math_w_defaults = math_w.evaluate_tier_2_defaults()
            defaults_w.update(math_w_defaults.start)
            defaults_w.update(math_w_defaults.other)

        if is_without(module):
            math_wo = MathInputs(*self.inputs_wo)
            math_wo_defaults = math_wo.evaluate_tier_2_defaults()
            defaults_wo.update(math_wo_defaults.start)
            defaults_wo.update(math_wo_defaults.other)

        return DefaultData(defaults_start, defaults_w, defaults_wo)


class EnergyCalculator(BaseCalculator):
    """
    Calculator for Energy module
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Energy module.
        """

        input: Energy = self.data
        res_w = MathResult(
            input.activity.project.implementation_years,
            input.activity.project.capitalization_years,
        )
        res_wo = MathResult(
            input.activity.project.implementation_years,
            input.activity.project.capitalization_years,
        )

        for elec in input.electricities:
            r_w, r_wo = ElectricityCalculator(elec).calculate()

            res_w += r_w
            res_wo += r_wo

        for fuel in input.fuels:
            r_w, r_wo = FuelCalculator(fuel).calculate()

            res_w += r_w
            res_wo += r_wo

        return (res_w, res_wo)


class ElectricityCalculator(BaseCalculator):
    """
    Calculator for energy.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Energy module.
        """

        input: Electricity = self.data
        activity: Activity = input.parent.activity
        project: Project = self.data.activity.project
        change_rate = activity.change_rate

        elec = ipcc.ElectricityEmission.objects.get(country=project.country)

        math_w = None
        math_wo = None

        if is_with(input):
            inputs_w = [
                elec.operating_margin if input.ef_source.name == "Operating Margin" else elec.combined_margin,
                input.ef_t2,
                input.mwh_start,
                input.mwh_w,
                input.transmission_loss,
                change_rate.name,
                project.implementation_years,
                project.capitalization_years,
            ]

            math_w = ElectryicityConsumption(*inputs_w)
            math_w.calculate_emissions()

        if is_without(input):
            inputs_wo = [
                elec.operating_margin if input.ef_source.name == "Operating Margin" else elec.combined_margin,
                input.ef_t2,
                input.mwh_start,
                input.mwh_wo,
                input.transmission_loss,
                change_rate.name,
                project.implementation_years,
                project.capitalization_years,
            ]

            math_wo = ElectryicityConsumption(*inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple


class FuelCalculator(BaseCalculator):
    """
    Calculator for fuel
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Fuel module.
        """

        input: Fuel = self.data
        activity: Activity = input.parent.activity
        project: Project = activity.project
        change_rate = activity.change_rate

        macro_fuel_type = input.fuel_type.macro_fuel_type.name
        ef = ipcc.EnergyDefaultEmissionFactor.objects.get(fuel_type=input.fuel_type)

        math_w = None
        math_wo = None

        if macro_fuel_type == "Liquid":
            if is_with(input):
                input_w = [
                    ef.t_co2_eq,
                    input.ef_t2,
                    input.fuel_start,
                    input.fuel_w,
                    change_rate.name,
                    project.implementation_years,
                    project.capitalization_years,
                ]

                math_w = FuelConsumption(*input_w)
                math_w.calculate_emissions()

            if is_without(input):
                input_wo = [
                    ef.t_co2_eq,
                    input.ef_t2,
                    input.fuel_start,
                    input.fuel_wo,
                    change_rate.name,
                    project.implementation_years,
                    project.capitalization_years,
                ]

                math_wo = FuelConsumption(*input_wo)
                math_wo.calculate_emissions()

        elif macro_fuel_type == "Solid":
            if is_with(input):
                input_w = [
                    ef.net_calorific_value,
                    ef.co2,
                    ef.ch4,
                    ef.n2o,
                    input.account_for_co2,
                    project.gw_potential.ch4,
                    project.gw_potential.n2o,
                    input.ef_t2,
                    input.fuel_start,
                    input.fuel_w,
                    input.activity.change_rate.name,
                    project.implementation_years,
                    project.capitalization_years,
                ]

                math_w = SolidConsumption(*input_w)
                math_w.calculate_emissions()

            if is_without(input):
                input_wo = [
                    ef.net_calorific_value,
                    ef.co2,
                    ef.ch4,
                    ef.n2o,
                    input.account_for_co2,
                    project.gw_potential.ch4,
                    project.gw_potential.n2o,
                    input.ef_t2,
                    input.fuel_start,
                    input.fuel_wo,
                    input.activity.change_rate.name,
                    project.implementation_years,
                    project.capitalization_years,
                ]

                math_wo = SolidConsumption(*input_wo)
                math_wo.calculate_emissions()

        else:
            raise ValueError(f"Fuel type {macro_fuel_type} not supported by calculations.")

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple


class SettlementCalculator(BaseCalculator):
    """
    Calculator for settlements
    """

    def calculate(self) -> Result:
        input: Settlement = self.data
        res_w = MathResult(
            input.activity.project.implementation_years,
            input.activity.project.capitalization_years,
        )
        res_wo = MathResult(
            input.activity.project.implementation_years,
            input.activity.project.capitalization_years,
        )

        for building in input.buildings.all():
            r_w, r_wo = BuildingCalculator(building).calculate()

            res_w += r_w
            res_wo += r_wo

        for road in input.roads.all():
            r_w, r_wo = RoadCalculator(road).calculate()

            res_w += r_w
            res_wo += r_wo

        return (res_w, res_wo)


class BuildingCalculator(BaseCalculator):
    """
    Calculator for buildings and roads.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Building module.
        """

        input: Building = self.data
        project: Project = input.activity.project

        ef_w: ipcc.BuildingEmissionFactor = ipcc.BuildingEmissionFactor.objects.get(building_type=input.building_type_w)
        ef_wo: ipcc.BuildingEmissionFactor = ipcc.BuildingEmissionFactor.objects.get(building_type=input.building_type_wo)

        math_w = None
        math_wo = None

        if is_with(input):
            inputs_w = [
                ef_w.value,
                input.ef_t2_w,
                input.area_m2_w,
                project.implementation_years,
                project.capitalization_years,
                input.activity.change_rate.name,
            ]

            math_w = MathRoads(*inputs_w)
            math_w.calculate_emissions()

        if is_without(input):
            inputs_wo = [
                ef_wo.value,
                input.ef_t2_wo,
                input.area_m2_wo,
                project.implementation_years,
                project.capitalization_years,
                input.activity.change_rate.name,
            ]

            math_wo = MathRoads(*inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple


class RoadCalculator(BaseCalculator):
    """
    Calculator for buildings and roads.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Building module.
        """

        input: Road = self.data
        project: Project = input.activity.project

        ef_w: ipcc.RoadEmissionFactor = ipcc.RoadEmissionFactor.objects.get(road_type=input.road_type_w)
        ef_wo: ipcc.RoadEmissionFactor = ipcc.RoadEmissionFactor.objects.get(road_type=input.road_type_wo)

        math_w = None
        math_wo = None

        if is_with(input):
            inputs_w = [
                ef_w.value,
                input.ef_t2_w,
                input.area_m2_w,
                project.implementation_years,
                project.capitalization_years,
                input.activity.change_rate.name,
            ]

            math_w = MathRoads(*inputs_w)
            math_w.calculate_emissions()

        if is_without(input):
            inputs_wo = [
                ef_wo.value,
                input.ef_t2_wo,
                input.area_m2_wo,
                project.implementation_years,
                project.capitalization_years,
                input.activity.change_rate.name,
            ]

            math_wo = MathRoads(*inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple


class LivestockCalculator(BaseCalculator):
    """
    Calculator for livestock

    # NOTE: The order_by=manure_management_type__name is to ensure that we are getting the correct order of the entities.
    This is because for each scenario the mathematical model is expecting a precise order,
    where each entry of [LivestockManureEF] matches an entry of [LivestockAnimalWasteManagementSystem]
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Livestock module.
        """

        module: Livestock = self.data
        activity: Activity = module.activity
        project: Project = activity.project

        climate: Climate = activity.climate_t2 or project.climate
        moisture: Moisture = activity.moisture_t2 or project.moisture
        region: Region = project.country.region

        LEACHING_MULTI = LivestockParameter.objects.get(name="LEACHING_MULTIPLIER").value
        volatilization_multi = ipcc.ManureManagementVolatilizationMultiplier.objects.get(moisture=moisture)

        # TAM Values
        tam_ch4_start = ipcc.LivestockTAM.objects.get(
            livestock_production_type=module.livestock_production_type_start,
            livestock_category_type=module.livestock_category_type_start,
            ipcc_region=region,
        )
        tam_ch4_w = ipcc.LivestockTAM.objects.get(
            livestock_production_type=module.livestock_production_type_w,
            livestock_category_type=module.livestock_category_type_w,
            ipcc_region=region,
        )
        tam_ch4_wo = ipcc.LivestockTAM.objects.get(
            livestock_production_type=module.livestock_production_type_wo,
            livestock_category_type=module.livestock_category_type_wo,
            ipcc_region=region,
        )

        # VSER Values
        vser_ch4_start = ipcc.LivestockVSER.objects.get(
            livestock_production_type=module.livestock_production_type_start,
            livestock_category_type=module.livestock_category_type_start,
            ipcc_region=region,
        )
        vser_ch4_w = ipcc.LivestockVSER.objects.get(
            livestock_production_type=module.livestock_production_type_w,
            livestock_category_type=module.livestock_category_type_w,
            ipcc_region=region,
        )
        vser_ch4_wo = ipcc.LivestockVSER.objects.get(
            livestock_production_type=module.livestock_production_type_wo,
            livestock_category_type=module.livestock_category_type_wo,
            ipcc_region=region,
        )

        # EF CH4 PRP Values
        ef_ch4_prp_start = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.CH4,
            livestock_category_type=module.livestock_category_type_start,
            livestock_production_type=module.livestock_production_type_start,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        ef_ch4_prp_w = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.CH4,
            livestock_category_type=module.livestock_category_type_w,
            livestock_production_type=module.livestock_production_type_w,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        ef_ch4_prp_wo = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.CH4,
            livestock_category_type=module.livestock_category_type_wo,
            livestock_production_type=module.livestock_production_type_wo,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        # EF CH4 Systems Values
        ef_ch4_systems_start = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.CH4,
                livestock_category_type=module.livestock_category_type_start,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_ch4_systems_w = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.CH4,
                livestock_category_type=module.livestock_category_type_w,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_ch4_systems_wo = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.CH4,
                livestock_category_type=module.livestock_category_type_wo,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_ch4_system_values_start = [system.value for system in ef_ch4_systems_start]
        ef_ch4_system_values_w = [system.value for system in ef_ch4_systems_w]
        ef_ch4_system_values_wo = [system.value for system in ef_ch4_systems_wo]

        # Animal Waste PRP Values
        animal_waste_prp_start = ipcc.LivestockAnimalWasteManagementSystem.objects.get(
            livestock_category_type=module.livestock_category_type_start,
            livestock_production_type=module.livestock_production_type_start,
            ipcc_region=region,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        animal_waste_prp_w = ipcc.LivestockAnimalWasteManagementSystem.objects.get(
            livestock_category_type=module.livestock_category_type_w,
            livestock_production_type=module.livestock_production_type_w,
            ipcc_region=region,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        animal_waste_prp_wo = ipcc.LivestockAnimalWasteManagementSystem.objects.get(
            livestock_category_type=module.livestock_category_type_wo,
            livestock_production_type=module.livestock_production_type_wo,
            ipcc_region=region,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        ##### Animal Waste Management Systems Values #####

        animal_waste_management_systems_start = (
            ipcc.LivestockAnimalWasteManagementSystem.objects.filter(
                livestock_category_type=module.livestock_category_type_start,
                livestock_production_type=module.livestock_production_type_start,
                ipcc_region=region,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        animal_waste_management_systems_w = (
            ipcc.LivestockAnimalWasteManagementSystem.objects.filter(
                livestock_category_type=module.livestock_category_type_w,
                livestock_production_type=module.livestock_production_type_w,
                ipcc_region=region,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        animal_waste_management_systems_wo = (
            ipcc.LivestockAnimalWasteManagementSystem.objects.filter(
                livestock_category_type=module.livestock_category_type_wo,
                livestock_production_type=module.livestock_production_type_wo,
                ipcc_region=region,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        # list comprehension to get the animal waste management systems values
        animal_waste_management_systems_values_start = [system.value for system in animal_waste_management_systems_start]
        animal_waste_management_systems_values_w = [system.value for system in animal_waste_management_systems_w]
        animal_waste_management_systems_values_wo = [system.value for system in animal_waste_management_systems_wo]

        ##### Enteric CH4 Values #####

        ch4_enteric_start = ipcc.MethaneEntericFermentationFactor.objects.get(
            livestock_category_type=module.livestock_category_type_start,
            livestock_production_type=module.livestock_production_type_start,
            ipcc_region=region,
        )

        ch4_enteric_w = ipcc.MethaneEntericFermentationFactor.objects.get(
            livestock_category_type=module.livestock_category_type_w,
            livestock_production_type=module.livestock_production_type_w,
            ipcc_region=region,
        )

        ch4_enteric_wo = ipcc.MethaneEntericFermentationFactor.objects.get(
            livestock_category_type=module.livestock_category_type_wo,
            livestock_production_type=module.livestock_production_type_wo,
            ipcc_region=region,
        )

        ##### PRP N2O Direct EF Values #####

        prp_n2o_direct_ef_start = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.N2O,
            livestock_category_type=module.livestock_category_type_start,
            livestock_production_type=module.livestock_production_type_start,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        prp_n2o_direct_ef_w = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.N2O,
            livestock_category_type=module.livestock_category_type_w,
            livestock_production_type=module.livestock_production_type_w,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        prp_n2o_direct_ef_wo = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.N2O,
            livestock_category_type=module.livestock_category_type_wo,
            livestock_production_type=module.livestock_production_type_wo,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        ##### PRP N2O Volatilization EF Values #####

        prp_n2o_volatilization_ef_start = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION,
            livestock_category_type=module.livestock_category_type_start,
            livestock_production_type=module.livestock_production_type_start,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        prp_n2o_volatilization_ef_w = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION,
            livestock_category_type=module.livestock_category_type_w,
            livestock_production_type=module.livestock_production_type_w,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        prp_n2o_volatilization_ef_wo = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION,
            livestock_category_type=module.livestock_category_type_wo,
            livestock_production_type=module.livestock_production_type_wo,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        ##### PRP N2O Leaching EF Values #####

        prp_n2o_leaching_ef_start = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.N2O_LEACHING,
            livestock_category_type=module.livestock_category_type_wo,
            livestock_production_type=module.livestock_production_type_wo,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        prp_n2o_leaching_ef_w = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.N2O_LEACHING,
            livestock_category_type=module.livestock_category_type_wo,
            livestock_production_type=module.livestock_production_type_wo,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        prp_n2o_leaching_ef_wo = ipcc.LivestockManureEF.objects.get(
            emission_type__name=utils.EmissionTypes.N2O_LEACHING,
            livestock_category_type=module.livestock_category_type_wo,
            livestock_production_type=module.livestock_production_type_wo,
            climate=climate,
            moisture=moisture,
            manure_management_type__name=utils.ManureManagementTypes.PRP,
        )

        ##### N2O Direct EF Values #####

        ef_n2o_direct_systems_start = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O,
                livestock_category_type=module.livestock_category_type_start,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_direct_systems_w = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O,
                livestock_category_type=module.livestock_category_type_w,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_direct_systems_wo = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O,
                livestock_category_type=module.livestock_category_type_wo,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_direct_systems_start = [s.value for s in ef_n2o_direct_systems_start]
        ef_n2o_direct_systems_w = [s.value for s in ef_n2o_direct_systems_w]
        ef_n2o_direct_systems_wo = [s.value for s in ef_n2o_direct_systems_wo]

        ##### N2O Volatilization EF Values #####

        ef_n2o_volatilization_systems_start = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=module.livestock_category_type_start,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_volatilization_systems_w = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=module.livestock_category_type_w,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_volatilization_systems_wo = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=module.livestock_category_type_wo,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_volatilization_systems_start = [s.value for s in ef_n2o_volatilization_systems_start]
        ef_n2o_volatilization_systems_w = [s.value for s in ef_n2o_volatilization_systems_w]
        ef_n2o_volatilization_systems_wo = [s.value for s in ef_n2o_volatilization_systems_wo]

        ##### N2O Leaching EF Values #####

        ef_n2o_leaching_systems_start = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING,
                livestock_category_type=module.livestock_category_type_start,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_leaching_systems_w = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING,
                livestock_category_type=module.livestock_category_type_w,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_leaching_systems_wo = (
            ipcc.LivestockManureEF.objects.filter(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING,
                livestock_category_type=module.livestock_category_type_wo,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
            )
            .exclude(manure_management_type__name=utils.ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_leaching_systems_start = [s.value for s in ef_n2o_leaching_systems_start]
        ef_n2o_leaching_systems_w = [s.value for s in ef_n2o_leaching_systems_w]
        ef_n2o_leaching_systems_wo = [s.value for s in ef_n2o_leaching_systems_wo]

        ##### NER Values #####

        ner_start = ipcc.LivestockNER.objects.get(
            livestock_category_type=module.livestock_category_type_start,
            livestock_production_type=module.livestock_production_type_start,
            ipcc_region=project.country.ipcc_region,
        )

        ner_w = ipcc.LivestockNER.objects.get(
            livestock_category_type=module.livestock_category_type_w,
            livestock_production_type=module.livestock_production_type_w,
            ipcc_region=project.country.ipcc_region,
        )

        ner_wo = ipcc.LivestockNER.objects.get(
            livestock_category_type=module.livestock_category_type_wo,
            livestock_production_type=module.livestock_production_type_wo,
            ipcc_region=project.country.ipcc_region,
        )

        ##### Complementary Manure Management Values #####

        n2o_ef_t2_start = None
        n2o_volatilization_ef_t2_start = None
        n2o_leaching_ef_t2_start = None
        ch4_ef_t2_start = None
        if module.complementary_manure_management_type_start is not None:
            n2o_ef_t2_start = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O,
                livestock_category_type=module.livestock_category_type_start,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_start,
            )
            if n2o_ef_t2_start:
                n2o_ef_t2_start = n2o_ef_t2_start.value

            n2o_volatilization_ef_t2_start = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=module.livestock_category_type_start,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_start,
            )
            if n2o_volatilization_ef_t2_start:
                n2o_volatilization_ef_t2_start = n2o_volatilization_ef_t2_start.value

            n2o_leaching_ef_t2_start = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING,
                livestock_category_type=module.livestock_category_type_start,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_start,
            )
            if n2o_leaching_ef_t2_start:
                n2o_leaching_ef_t2_start = n2o_leaching_ef_t2_start.value

            ch4_ef_t2_start = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.CH4,
                livestock_category_type=module.livestock_category_type_start,
                livestock_production_type=module.livestock_production_type_start,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_start,
            )
            if ch4_ef_t2_start:
                ch4_ef_t2_start = ch4_ef_t2_start.value

        n2o_ef_t2_w = None
        n2o_volatilization_ef_t2_w = None
        n2o_leaching_ef_t2_w = None
        ch4_ef_t2_w = None
        if module.complementary_manure_management_type_w is not None:
            n2o_ef_t2_w = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O,
                livestock_category_type=module.livestock_category_type_w,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_w,
            )
            if n2o_ef_t2_w:
                n2o_ef_t2_w = n2o_ef_t2_w.value

            n2o_volatilization_ef_t2_w = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=module.livestock_category_type_w,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_w,
            )
            if n2o_volatilization_ef_t2_w:
                n2o_volatilization_ef_t2_w = n2o_volatilization_ef_t2_w.value

            n2o_leaching_ef_t2_w = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING,
                livestock_category_type=module.livestock_category_type_w,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_w,
            )
            if n2o_leaching_ef_t2_w:
                n2o_leaching_ef_t2_w = n2o_leaching_ef_t2_w.value

            ch4_ef_t2_w = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.CH4,
                livestock_category_type=module.livestock_category_type_w,
                livestock_production_type=module.livestock_production_type_w,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_w,
            )
            if ch4_ef_t2_w:
                ch4_ef_t2_w = ch4_ef_t2_w.value

        n2o_ef_t2_wo = None
        n2o_volatilization_ef_t2_wo = None
        n2o_leaching_ef_t2_wo = None
        ch4_ef_t2_wo = None
        if module.complementary_manure_management_type_wo is not None:
            n2o_ef_t2_wo = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O,
                livestock_category_type=module.livestock_category_type_wo,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_wo,
            )
            if n2o_ef_t2_wo:
                n2o_ef_t2_wo = n2o_ef_t2_wo.value

            n2o_volatilization_ef_t2_wo = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=module.livestock_category_type_wo,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_wo,
            )
            if n2o_volatilization_ef_t2_wo:
                n2o_volatilization_ef_t2_wo = n2o_volatilization_ef_t2_wo.value

            n2o_leaching_ef_t2_wo = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.N2O_LEACHING,
                livestock_category_type=module.livestock_category_type_wo,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_wo,
            )
            if n2o_leaching_ef_t2_wo:
                n2o_leaching_ef_t2_wo = n2o_leaching_ef_t2_wo.value

            ch4_ef_t2_wo = ipcc.LivestockManureEF.objects.get(
                emission_type__name=utils.EmissionTypes.CH4,
                livestock_category_type=module.livestock_category_type_wo,
                livestock_production_type=module.livestock_production_type_wo,
                climate=climate,
                moisture=moisture,
                manure_management_type=module.complementary_manure_management_type_wo,
            )
            if ch4_ef_t2_wo:
                ch4_ef_t2_wo = ch4_ef_t2_wo.value

        math_w = None
        math_wo = None

        if is_with(module):
            self.inputs_w = [
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                project.gw_potential.ch4,
                module.heads_number_start,
                module.heads_number_w,
                ch4_enteric_start.value,
                ch4_enteric_w.value,
                module.enteric_fermentation_start_t2,
                module.enteric_fermentation_w_t2,
                ef_ch4_prp_start.value,
                ef_ch4_prp_w.value,
                animal_waste_prp_start.value,
                animal_waste_prp_w.value,
                module.prp_percentage_start_t2,
                module.prp_percentage_w_t2,
                ef_ch4_system_values_start,
                ef_ch4_system_values_w,
                module.prp_ch4_start_t2,
                module.prp_ch4_w_t2,
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
                module.prp_n2o_start_t2,
                module.prp_n2o_w_t2,
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
                module.prp_n2o_start_t2,  # TODO: Maybe add specific t2 for volatilization
                module.prp_n2o_w_t2,
                n2o_volatilization_ef_t2_start,  ###
                n2o_volatilization_ef_t2_w,
                module.emission_factor_n2o_t2_start,
                module.emission_factor_n2o_t2_w,
                prp_n2o_leaching_ef_start.value,
                prp_n2o_leaching_ef_w.value,
                ef_n2o_leaching_systems_start,
                ef_n2o_leaching_systems_w,
                module.prp_n2o_start_t2,  # TODO: Maybe add specific t2 for leaching
                module.prp_n2o_w_t2,
                n2o_leaching_ef_t2_start,  ###
                n2o_leaching_ef_t2_w,
                module.emission_factor_n2o_t2_start,
                module.emission_factor_n2o_t2_w,
                project.gw_potential.n2o,
                volatilization_multi.value,
                LEACHING_MULTI,
            ]

            math_w = MathLivestock(*self.inputs_w)
            math_w.calculate_emissions()

        if is_without(module):
            self.inputs_wo = [
                project.implementation_years,
                project.capitalization_years,
                module.activity.change_rate.name,
                project.gw_potential.ch4,
                module.heads_number_start,
                module.heads_number_wo,
                ch4_enteric_start.value,
                ch4_enteric_wo.value,
                module.enteric_fermentation_start_t2,
                module.enteric_fermentation_wo_t2,
                ef_ch4_prp_start.value,
                ef_ch4_prp_wo.value,
                animal_waste_prp_start.value,
                animal_waste_prp_wo.value,
                module.prp_percentage_start_t2,
                module.prp_percentage_wo_t2,
                ef_ch4_system_values_start,
                ef_ch4_system_values_wo,
                module.prp_ch4_start_t2,
                module.prp_ch4_wo_t2,
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
                module.prp_n2o_start_t2,
                module.prp_n2o_wo_t2,
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
                module.prp_n2o_start_t2,  # TODO: Maybe add specific t2 for volatilization
                module.prp_n2o_wo_t2,
                n2o_volatilization_ef_t2_start,  ###
                n2o_volatilization_ef_t2_wo,
                module.emission_factor_n2o_t2_start,
                module.emission_factor_n2o_t2_wo,
                prp_n2o_leaching_ef_start.value,
                prp_n2o_leaching_ef_wo.value,
                ef_n2o_leaching_systems_start,
                ef_n2o_leaching_systems_wo,
                module.prp_n2o_start_t2,  # TODO: Maybe add specific t2 for leaching
                module.prp_n2o_wo_t2,
                n2o_leaching_ef_t2_start,  ###
                n2o_leaching_ef_t2_wo,
                module.emission_factor_n2o_t2_start,
                module.emission_factor_n2o_t2_wo,
                project.gw_potential.n2o,
                volatilization_multi.value,
                LEACHING_MULTI,
            ]

            math_wo = MathLivestock(*self.inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return Result(*results_tuple)

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
        input: Irrigation = self.data
        res_w = MathResult(
            input.activity.project.implementation_years,
            input.activity.project.capitalization_years,
        )
        res_wo = MathResult(
            input.activity.project.implementation_years,
            input.activity.project.capitalization_years,
        )
        for system in input.irrigation_systems:
            r_w, r_wo = IrrigationSystemCalculator(system).calculate()
            res_w += r_w
            res_wo += r_wo

        for phase in input.irrigation_phases:
            r_w, r_wo = IrrigationPhaseCalculator(phase).calculate()
            res_w += r_w
            res_wo += r_wo

        return (res_w, res_wo)


class IrrigationSystemCalculator(BaseCalculator):
    """
    Calculates the emissions of the irrigation system
    """

    def calculate(self) -> list[Result]:
        """
        Calculates the emissions of the irrigation system
        """

        _input: IrrigationSystem = self.data
        project: Project = _input.activity.project

        ef = ipcc.IrrigationSystemData.objects.get(irrigation_system_type=_input.irrigation_system_type)

        math_w = None
        math_wo = None

        if is_with(_input):
            inputs_w = [
                ef.value,
                _input.ef_t2_start,
                _input.ha_start,
                _input.ha_w,
                project.implementation_years,
                project.capitalization_years,
                _input.activity.change_rate.name,
            ]

            math_w = NewIrrigation(*inputs_w)
            math_w.calculate_emissions()

        if is_without(_input):
            inputs_wo = [
                ef.value,
                _input.ef_t2_wo,
                _input.ha_start,
                _input.ha_wo,
                project.implementation_years,
                project.capitalization_years,
                _input.activity.change_rate.name,
            ]

            math_wo = NewIrrigation(*inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple


class IrrigationPhaseCalculator(BaseCalculator):
    def calculate(self) -> list[Result]:
        input: IrrigationPhase = self.data
        project: Project = input.activity.project

        ef = ipcc.IrrigationPhaseData.objects.get(fuel_type=input.fuel_type)
        energy_db = ipcc.EnergyDefaultEmissionFactor.objects.get(fuel_type=input.fuel_type)
        pressure = ipcc.IrrigationPressureRequirement.objects.get(irrigation_system_type=input.irrigation_system_type)

        erh_electricity = IrrigationParameter.objects.get(name="ERH_ELECTRICITY").value if input.fuel_type.name == "Electricity" else None
        transportation_loss = IrrigationParameter.objects.get(name="TRANSPORTATION_LOSS")
        pumping_efficiency = IrrigationParameter.objects.get(name="PUMPING_EFFICIENCY")

        math_start = None
        math_w = None
        math_wo = None

        inputs_start = [
            ef.emission_factor,
            input.ef_t2_start,
            input.total_dynamic_head_t2,
            pressure.avg_pressure,
            input.average_pressure_t2,
            pumping_efficiency.value,
            input.pumping_efficiency_t2_start,
            erh_electricity,
            energy_db.net_calorific_value,
            energy_db.density,
            input.well_depth,
            input.ha_start,
            0,
            input.activity.change_rate.name,
            project.implementation_years,
            project.capitalization_years,
            transportation_loss.value if input.fuel_type.name == "Electricity" else 0,
            input.gross_irrigation_water_start,
        ]

        math_start = OperationPhaseIrrigation(*inputs_start)
        math_start.calculate_emissions()

        if is_with(input):
            inputs_w = [
                ef.emission_factor,
                input.ef_t2_w,
                input.total_dynamic_head_t2,
                pressure.avg_pressure,
                input.average_pressure_t2,
                pumping_efficiency.value,
                input.pumping_efficiency_t2_w,
                erh_electricity,
                energy_db.net_calorific_value,
                energy_db.density,
                input.well_depth,
                0,
                input.ha_w,
                input.activity.change_rate.name,
                project.implementation_years,
                project.capitalization_years,
                transportation_loss.value if input.fuel_type.name == "Electricity" else 0,
                input.gross_irrigation_water_w,
            ]

            math_w = OperationPhaseIrrigation(*inputs_w)
            math_w.calculate_emissions()

        if is_without(input):
            inputs_wo = [
                ef.emission_factor,
                input.ef_t2_wo,
                input.total_dynamic_head_t2,
                pressure.avg_pressure,
                input.average_pressure_t2,
                pumping_efficiency.value,
                input.pumping_efficiency_t2_wo,
                erh_electricity,
                energy_db.net_calorific_value,
                energy_db.density,
                input.well_depth,
                0,
                input.ha_wo,
                input.activity.change_rate.name,
                project.implementation_years,
                project.capitalization_years,
                transportation_loss.value if input.fuel_type.name == "Electricity" else 0,
                input.gross_irrigation_water_wo,
            ]

            math_wo = OperationPhaseIrrigation(*inputs_wo)
            math_wo.calculate_emissions()

        results_start = math_start.result if math_start else MathResult(project.implementation_years, project.capitalization_years)
        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w + results_start, results_wo + results_start)

        return results_tuple


class CoastalWetlandCalculator(BaseCalculator):
    """
    Calculates the emissions of the coastal wetland
    """

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

        soil_type_name = module.soil_type_t2.name if module.soil_type_t2 else "Mineral Soil"

        agb = ipcc.CoastalAGB.objects.get(**cm, vegetation_type=module.vegetation_type)
        bgb = ipcc.CoastalBGB.objects.get(**cm, vegetation_type=module.vegetation_type)
        litter = ipcc.CoastalLitter.objects.get(**cm, vegetation_type=module.vegetation_type)
        dw = ipcc.CoastalDeadwood.objects.get(**cm, vegetation_type=module.vegetation_type)
        soil_1m = ipcc.DefaultSoilCarbonStock1Meter.objects.get(**cm, vegetation_type=module.vegetation_type, soil_type__name=soil_type_name)
        ef_drainage = ipcc.DrainageEmissionFactor.objects.get(**cm, vegetation_type=module.vegetation_type)
        pc_c_lost_excavation = CoastalWetlandParameter.objects.get(name="PERCENTAGE_C_LOST_EXCAVATION")

        rewetting_c = ipcc.RewettingCarbonFactor.objects.get(**cm, vegetation_type=module.vegetation_type)
        rewetting_ch4 = ipcc.RewettingMethaneFactor.objects.get(**cm, vegetation_type=module.vegetation_type)

        math_w = None
        math_wo = None

        if is_with(module):
            inputs_w = [
                module.ha_start,
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
                pc_c_lost_excavation.value,
                module.pc_c_lost_after_excavation_t2_w,
                rewetting_c.value,
                rewetting_ch4.value,
                module.co2_rewetting_t2_start,
                module.ch4_rewetting_t2_w,
                module.avg_salinity_t2.value,
                project.gw_potential.ch4,
            ]

            math_w = MathCoastalWetland(*inputs_w)
            math_w.calculate_emissions()

        if is_without(module):
            inputs_wo = [
                module.ha_start,
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
                pc_c_lost_excavation.value,
                module.pc_c_lost_after_excavation_t2_wo,
                rewetting_c.value,
                rewetting_ch4.value,
                module.co2_rewetting_t2_wo,
                module.ch4_rewetting_t2_wo,
                module.avg_salinity_t2.value,
                project.gw_potential.ch4,
            ]

            math_wo = MathCoastalWetland(*inputs_wo)
            math_wo.calculate_emissions()

        results_w = math_w.result if math_w else MathResult(project.implementation_years, project.capitalization_years)
        results_wo = math_wo.result if math_wo else MathResult(project.implementation_years, project.capitalization_years)

        results_tuple = (results_w, results_wo)

        return results_tuple

    def defaults(self) -> DefaultData:
        self.calculate()

        module: CoastalWetland = self.data

        defaults_start = {}
        defaults_w = {}
        defaults_wo = {}

        if is_luc_remaining_same(module):
            math_start = MathCoastalWetland(*self.inputs_start_w)
            math_start_defaults = math_start.evaluate_tier_2_defaults()
            defaults_start.update(math_start_defaults.start)
            defaults_start.update(math_start_defaults.other)
        elif is_business_as_usual(module):
            math_start_wo = MathCoastalWetland(*self.inputs_start_wo)
            math_start_wo_defaults = math_start_wo.evaluate_tier_2_defaults()
            defaults_start.update(math_start_wo_defaults.start)
            defaults_start.update(math_start_wo_defaults.other)

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


class WaterbodyCalculator(BaseCalculator):
    """
    Calculator for waterbody modules.
    """

    def calculate(self) -> Result:
        """
        Calculate emissions for a single Waterbody module.
        """
        module: Waterbody = self.data
        project = module.activity.project
        methane_emission_factor = ipcc.OtherConstructedWaterbodiesEmissionFactor.objects.get(
            climate=project.climate,
            moisture=project.moisture,
            waterbody_type=module.waterbody_type,
        )

        trophic_state_start = ipcc.TrophicStateFactor.objects.get(trophic_type=module.trophic_type_start)
        trophic_state_w = ipcc.TrophicStateFactor.objects.get(trophic_type=module.trophic_type_w)
        trophic_state_wo = ipcc.TrophicStateFactor.objects.get(trophic_type=module.trophic_type_wo)

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

        if is_with(module):
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

        if is_without(module):
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


class OrganicSoilCalculator(BaseCalculator):
    def calculate(self) -> Result:
        input: OrganicSoil = self.data
        project: Project = input.activity.project
        luc: LandUseChange = input.land_use_change

        if not luc:
            raise ValueError("Organic Soil is missing a land use from a parent module")

        relative_class = luc.land_use_type_w.module_type.name

        if luc.land_use_type_start.module_type.name == "ForestManagement":
            area_affected_by_module = 0

        cmt = {
            "climate": project.climate,
            "moisture": project.moisture,
            "module_type_name": relative_class,
        }

        cm = {
            "climate": project.climate,
            "moisture": project.moisture,
        }

        ##### Organic Soil Inputs #####

        ef_onsite_start = ipcc.OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(**cm, module_type_name=luc.land_use_type_start.module_type.name, peat_type=input.peat_type_start, site_location_type_name="On-Site")
        ef_onsite_w = ipcc.OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(**cmt, peat_type=input.peat_type_w, site_location_type_name="On-Site")
        ef_onsite_wo = ipcc.OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(**cmt, peat_type=input.peat_type_wo, site_location_type_name="On-Site")

        ef_offsite_start = ipcc.OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(**cmt, peat_type=input.peat_type_start, site_location_type_name="Off-Site")
        ef_offsite_w = ipcc.OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(**cmt, peat_type=input.peat_type_w, site_location_type_name="Off-Site")
        ef_offsite_wo = ipcc.OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(**cmt, peat_type=input.peat_type_wo, site_location_type_name="Off-Site")

        dry_matter_w = ipcc.OrganicSoilFuelConsumption.objects.get(**cm, fire_type=input.fire_type_w)
        dry_matter_wo = ipcc.OrganicSoilFuelConsumption.objects.get(**cm, fire_type=input.fire_type_wo)

        fire_ref = ipcc.OrganicSoilGefEmissionFactor.objects.get(**cm)

        rewetting_start = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=input.peat_type_start, module_type__name=relative_class)
        rewetting_w = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=input.peat_type_w, module_type__name=relative_class)
        rewetting_wo = ipcc.OrganicSoilRewettingEmissionFactor.objects.get(**cm, peat_type=input.peat_type_wo, module_type__name=relative_class)

        ##### Peat Extraction Inputs #####

        onsite_ef_w = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=input.peat_type_w, site_location_type__name="On-Site")
        onsite_ef_wo = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=input.peat_type_wo, site_location_type__name="On-Site")

        offsite_ef_w = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=input.peat_type_w, site_location_type__name="Off-Site")
        offsite_ef_wo = ipcc.PeatExtractionEmissionFactor.objects.get(**cm, peat_type=input.peat_type_wo, site_location_type__name="Off-Site")

        conversion_factor_w = ipcc.PeatExtractionConversionFactor.objects.get(**cm, peat_type=input.peat_type_w)
        conversion_factor_wo = ipcc.PeatExtractionConversionFactor.objects.get(**cm, peat_type=input.peat_type_wo)

        ##### Calculate Emissions #####

        total_results_w = MathResult(project.implementation_years, project.capitalization_years)
        total_results_wo = MathResult(project.implementation_years, project.capitalization_years)

        organic_soil_math_w = None
        organic_soil_math_wo = None
        peat_extraction_math_w = None
        peat_extraction_math_wo = None

        if is_with(input):
            organic_soil_inputs_w = [
                input.fire_type_w is not None,
                input.soil_fire_periodicity_w,
                area_affected_by_module,
                dry_matter_w.value,
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
                luc.area,
            ]

            organic_soil_math_w = MathOrganicSoil(*organic_soil_inputs_w)
            organic_soil_math_w.calculate_emissions()

            peat_extraction_inputs_w = [
                input.peat_area_start,
                input.peat_area_w,
                input.peat_ditches_area_start,
                input.peat_ditches_area_w,
                input.activity.change_rate.name,
                onsite_ef_w.co2,
                input.onsite_co2_peat_t2,
                onsite_ef_w.ch4,
                input.onsite_ch4_peat_t2,
                onsite_ef_w.n2o,
                input.onsite_n2o_peat_t2,
                offsite_ef_w.doc,
                input.offsite_doc_peat_t2,
                offsite_ef_w.ch4,
                input.offsite_ch4_peat_t2,
                project.gw_potential.ch4,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                conversion_factor_w.volume,
                input.peat_density_t2,
                1,  # TODO: Should be conversion_factor_w.volume,
                conversion_factor_w.weight,
                input.peat_extraction_height_start,
                input.peat_extraction_height_w,
            ]

            peat_extraction_math_w = MathPeatExtraction(*peat_extraction_inputs_w)
            peat_extraction_math_w.calculate_emissions()

        if is_without(input):
            organic_soil_inputs_wo = [
                input.fire_type_wo is not None,
                input.soil_fire_periodicity_wo,
                area_affected_by_module,
                dry_matter_wo.value,
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
                luc.area,
            ]

            organic_soil_math_wo = MathOrganicSoil(*organic_soil_inputs_wo)
            organic_soil_math_wo.calculate_emissions()

            peat_extraction_inputs_wo = [
                input.peat_area_start,
                input.peat_area_wo,
                input.peat_ditches_area_start,
                input.peat_ditches_area_wo,
                input.activity.change_rate.name,
                onsite_ef_wo.co2,
                input.onsite_co2_peat_t2,
                onsite_ef_wo.ch4,
                input.onsite_ch4_peat_t2,
                onsite_ef_wo.n2o,
                input.onsite_n2o_peat_t2,
                offsite_ef_wo.doc,
                input.offsite_doc_peat_t2,
                offsite_ef_wo.ch4,
                input.offsite_ch4_peat_t2,
                project.gw_potential.ch4,
                project.gw_potential.n2o,
                project.implementation_years,
                project.capitalization_years,
                conversion_factor_wo.volume,
                input.peat_density_t2,
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

        peat_extraction_results_w = peat_extraction_math_w.result if peat_extraction_math_w else MathResult(project.implementation_years, project.capitalization_years)
        peat_extraction_results_wo = peat_extraction_math_wo.result if peat_extraction_math_wo else MathResult(project.implementation_years, project.capitalization_years)

        total_results_w += organic_soil_results_w + peat_extraction_results_w
        total_results_wo += organic_soil_results_wo + peat_extraction_results_wo

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

    def calculate(self) -> Result:
        """"""

        input: LandModule | LandModuleNoScenarios = self.data
        luc: LandUseChange = input.land_use_change
        project: Project = input.activity.project

        # TODO: Review
        land_use_type = input.land_use_type if luc.module_type_start.class_name == "ForestManagement" else input.land_use_type_start
        land_use_type = LandUseType.objects.get(name=land_use_type.name)

        cvt = {
            "continent": project.country.region,
            "vegetation_type": land_use_type,
        }  # TODO: Change to land use type

        # ag_net_biomass_start = AboveGroundNetBiomassGrowth.objects.get(**cvt) # TODO: Change to land use type
        # ag_net_biomass_end = AboveGroundNetBiomassGrowth.objects.get(**cvt) # TODO: Change to land use type

        # le_20yrs_start = ag_net_biomass_start.value_upto_20_years
        # le_20yrs_end = ag_net_biomass_end.value_upto_20_years

        # gt_20yrs_start = ag_net_biomass_start.value_after_20_years
        # gt_20yrs_end = ag_net_biomass_end.value_after_20_years

        # bgb_before_20_yrs_start: BelowGroundBiomass = BelowGroundBiomass.objects.get_max_below_threshold(**cvt, threshold=le_20yrs_start) # TODO: Change to land use type
        # bgb_before_20_yrs_end: BelowGroundBiomass = BelowGroundBiomass.objects.get_max_below_threshold(**cvt, threshold=le_20yrs_end) # TODO: Change to land use type

        # bgb_after_20_yrs_start: BelowGroundBiomass = BelowGroundBiomass.objects.get_max_below_threshold(**cvt, threshold=gt_20yrs_start) # TODO: Change to land use type
        # bgb_after_20_yrs_end: BelowGroundBiomass = BelowGroundBiomass.objects.get_max_below_threshold(**cvt, threshold=gt_20yrs_end) # TODO: Change to land use type

        # agb_under_20 = ForestManagementAGB.objects.get(
        #     **cvt,
        #     forest_condition_type__name = input.forest_condition_type,
        #     forest_type__name = input.forest_type,
        # )

        # ForestManagement start/w/wo forest is the same
        # forest_condition_type is based on implementation years (< 20, > 20)
        """
        Per secondary, se parliamo di AFFORESTATION dovremmo usare i valori per Secondary < 20 per AGB growth. AGB max dovrebbe essere Secondary<20 (per i progetti di meno di 20 anni) e Secondary>20 (se i progetti durano da 21 anni in su)
        Se parliamo di forest management invece usiamo i valori di Secondary > 20 sia per AGB growth che per AGB max.
        """

        # agb_over_20 = ForestManagementAGB.objects.get(
        #     **cvt,
        #     forest_condition_type__name = "Secondary >20",
        #     forest_type__name = input.forest_type,
        # )

        # litter_dw_start = LitterDeadwoodCarbonStock.objects.get(vegetation_type=land_use_type) # TODO: Change to land use type
        # litter_dw_end = LitterDeadwoodCarbonStock.objects.get(vegetation_type=land_use_type) # TODO: Change to land use type

        # disturbances: list[ForestDisturbance] = input.disturbances.all()

        # inputs_start = [
        #     project.capitalization_duration_yrs,
        #     project.implementation_duration_yrs,
        #     input.activity.change_rate.name,
        #     luc.area,
        #     0,
        #     input.rotation_length_yrs_start,
        #     input.rotation_start_year_t2_start,
        #     input.rotation_percentage_biomass_for_energy_start,

        #     utils.avg([agb_over_20.agb_growth_max, agb_over_20.agb_growth_min]),
        #     utils.avg([agb_under_20.agb_growth_max, agb_under_20.agb_growth_min]),

        #     bgb_before_20_yrs_start.threshold,
        #     bgb_before_20_yrs_start.value,
        #     bgb_after_20_yrs_start.value,

        #     input.bgb_growth_rate_le_20_yrs_t2_start,
        #     input.bgb_growth_rate_gt_20_yrs_t2_start,

        #     utils.avg([agb_over_20.agb_max, agb_over_20.agb_min]), # giusto
        #     utils.avg([agb_under_20.agb_max, agb_under_20.agb_min]),

        #     agb_over_20.agb_max,

        #     [d.recurrence_yrs_start for d in disturbances],
        #     [d.percentage_biomass_destruction_start for d in disturbances],
        #     [d.start_year_t2_start for d in disturbances],

        #     input.logging_recurrence_yrs_start,
        #     input.logging_percentage_agb_logged_start,
        #     input.logging_percentage_biomass_for_energy_start,
        #     input.logging_start_year_t2_start,

        #     litter_dw_start.litter,
        #     litter_dw_start.dw,

        #     project.soc_ref.value,

        #     input.land_use_factor_t2_start,
        #     None, # fi_t2_start,
        #     None, # fmg_t2_start,
        #     1, # flu_start
        #     1, # fi_start,
        #     1, # fmg_start,

        #     project.gw_potential.ch4,
        #     project.gw_potential.n2o,
        # ]

        return Result()
