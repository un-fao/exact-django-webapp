from django.db.models import Model
from .models import (
    Deforestation,
    Afforestation,
    OtherLandUse,
    Project,
    Input,
    Building,
    Livestock,
    AnnualCropping,
    AnnualCroplandParameter,
    CropType,
    LivestockParameter,
    Electricity,
    Fuel,
    IrrigationSystem,
    IrrigationPhase,
    IrrigationParameter,
    SmallFisheryParameter,
    LargeFisheryParameter,
    PerennialCropping,
    Aquaculture,
    AquacultureParameter,
    Grassland,
    GrasslandParameter,
    SmallFishery,
    LargeFishery,
    FloodedRice,
    CoastalWetland,
    CoastalWetlandParameter,
    Waterbody,
    OrganicSoil,
    ModuleType,
    Road,
    Settlement,
)
from math_model import (
    defo,
    affo,
    oluc,
    perennial_cropping,
    coastal_wetlands,
    grassland_management,
    fisheries_and_aquaculture,
    forest_management,
)
from math_model.no_time_dependency_final.annuals import AnnualCropland
from math_model.no_time_dependency_final.perennial_cropping import PerennialCropping as PerennialCropland
from math_model import inputs as math_inputs
from ipcc.models import *
from .utilities import *
from abc import ABC, abstractmethod
import sys
from math_model.no_time_dependency_final.defo import Deforestation as MathDeforestation
from math_model.no_time_dependency_final.waterbodies import CoastalWaterbodies as MathWaterbodies
from math_model.no_time_dependency_final.livestock import Livestock as MathLivestock
from math_model.no_time_dependency_final.grassland_management import GrasslandManagement as MathGrassland
from math_model.no_time_dependency_final.inputs import Roads as MathRoads
from math_model.no_time_dependency_final.coastal_wetlands import CoastalWetland as MathCoastalWetland
from math_model.no_time_dependency_final.fisheries_and_aquaculture import (
    CoastalAquaculture as MathAquaculture,
    Fishery as MathFishery,
)
from math_model.no_time_dependency_final.flooded_rice import FloodedRice as MathFloodedRice
from math_model.no_time_dependency_final.inputs import (
    Inputs as MathInputs,
    FuelConsumption,
    SolidConsumption,
    ElectryicityConsumption,
    NewIrrigation,
    OperationPhaseIrrigation,
)
import traceback

class Result:
    """
    Base class for all results.
    """
    def __init__(self, total_w=0, total_wo=0, balance=0):
        self.total_w = total_w
        self.total_wo = total_wo
        self.balance = balance
    
    def __str__(self):
        return f"total_w: {self.total_w}, total_wo: {self.total_wo}, balance: {self.balance}"
    
    def add(self, result):
        if not isinstance(result, self.__class__):
            raise TypeError(f"Cannot add {type(result)} to {type(self)}. Must use a {type(self)} instance.")
        
        self.total_w += result.total_w
        self.total_wo += result.total_wo
        self.balance += result.balance

class CalculatorFactory:
    def calculate_result(self, input):
        """
        Calculates the results for a given module.
        """
        try:
            calculator_name = input.__class__.__name__ + "Calculator"
            # Finds and instantiates the calculator class for the given module
            calculator: BaseCalculator = getattr(sys.modules[__name__], calculator_name)(input)
            return calculator.calculate()
        except AttributeError as e:
            traceback.print_exc()
            raise Exception(f"Module '{input.__class__.__name__}' not (yet) supported.")
        except Exception as ex:
            traceback.print_exc()
            raise ex

class BaseCalculator(ABC):
    """
    Abstract base class for all calculators.
    """

    class Meta:
        model = None

    def __init__(self, input) -> None:
        self.Meta.model = input.__class__
        self.data = input
        super().__init__()

    @abstractmethod
    def calculate(self, input: Model) -> Result:
        """
        Calculate emissions for a single module.
        """
        pass

class DeforestationCalculator(BaseCalculator):
    """
    TODO: Refactor with new logic
    Calculator for deforestation modules.
    """

    def calculate(self) -> Result:
        """
        Calculate emissions for a single Deforestation module.
        """

        module: Deforestation = self.data
        project: Project = module.activity.project
        change_rate = module.activity.change_rate
        climate = project.climate
        moisture = project.moisture
        continent = project.continent
        soil_type = project.soil_type

        cmc = {
            "climate": climate,
            "moisture": moisture,
            "continent": continent,
        }

        mangroves_data = None

        soc_ref = SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type)

        total_biomass_start = TotalBiomassAfterDefo.objects.get(**cmc, land_use_type=module.land_use_type_start)
        total_biomass_w = TotalBiomassAfterDefo.objects.get(**cmc, land_use_type=module.land_use_type_w)
        total_biomass_wo = TotalBiomassAfterDefo.objects.get(**cmc, land_use_type=module.land_use_type_wo)

        # NOTE: Maybe merge the mangroves and deforestation IPCC tables into one table?
        if self.data.vegetation_type != MANGROVES:
            defo_table_start = LitterDeadwoodCarbonStock.objects.get(vegetation_type=module.vegetation_type_start)
            defo_table_w = LitterDeadwoodCarbonStock.objects.get(vegetation_type=module.vegetation_type_w)
            defo_table_wo = LitterDeadwoodCarbonStock.objects.get(vegetation_type=module.vegetation_type_wo)

            ag_biomass_start = AboveGroundBiomass.objects.get(continent=continent, vegetation_type=module.vegetation_type_start)
            ag_biomass_w = AboveGroundBiomass.objects.get(continent=continent, vegetation_type=module.vegetation_type_w)
            ag_biomass_wo = AboveGroundBiomass.objects.get(continent=continent, vegetation_type=module.vegetation_type_wo)

            bg_biomass_start = BelowGroundBiomass.objects.get_first_above_threshold(continent=continent, vegetation_type=module.vegetation_type_start, threshold=ag_biomass_start.value)
            bg_biomass_w = BelowGroundBiomass.objects.get_first_above_threshold(continent=continent, vegetation_type=module.vegetation_type_w, threshold=ag_biomass_w.value)
            bg_biomass_wo = BelowGroundBiomass.objects.get_first_above_threshold(continent=continent, vegetation_type=module.vegetation_type_wo, threshold=ag_biomass_wo.value)

            # TODO: Delete if above query works
            # bg_biomass_start = bg_biomass_start.filter(Q(threshold__gt=ag_biomass_start.value) | Q(threshold__isnull=True)).order_by("threshold").first()
        else:
            mangroves_data = DataOnMangrove.objects.get(continent=continent)

        combustion_factor_start = CombustionFactor.objects.get(vegetation_type=module.vegetation_type_start)
        combustion_factor_w = CombustionFactor.objects.get(vegetation_type=module.vegetation_type_w)
        combustion_factor_wo = CombustionFactor.objects.get(vegetation_type=module.vegetation_type_wo)

        # TODO: Review this query
        moisture_factor = DefaultEmissionFactor.objects.filter(moisture=moisture)
        moisture_factor = moisture_factor.filter(Q(input__name__icontains="Other N Inputs") | Q(input__name__icontains="All N Inputs")).first()

        flu_start = LandUseCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=module.land_use_type_start)
        flu_w = LandUseCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=module.land_use_type_w)
        flu_wo = LandUseCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=module.land_use_type_wo)


        inputs_start = [
            module.ha_start,
            0,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            change_rate.name, # TODO: Remove from math model
            total_biomass_start.value,
            module.final_rcs_biomass_t2_start,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            module.is_fire_used_start,
            combustion_factor_start.n2o,
            combustion_factor_start.ch4,
            combustion_factor_start.value,
            moisture_factor.value,
            defo_table_start.litter if mangroves_data is None else mangroves_data.litter,
            module.rcs_litter_t2_start,
            defo_table_start.dw if mangroves_data is None else mangroves_data.dw,
            module.rcs_deadwood_t2_start,
            module.hwp_start,
            MANGROVE_FACTOR if mangroves_data is not None else NON_MANGROVE_FACTOR,
            module.rcs_bg_t2_start,
            module.rcs_ag_t2_start,
            flu_start.value,
            mangroves_data.agb_c if mangroves_data is not None else ag_biomass_start.value,
            mangroves_data.bgb if mangroves_data is not None else bg_biomass_start.value,
            CN_RATIO_GRASSLAND,
            module.soc_after_defo_t2_start, # soil after defo t2
            soc_ref.value,
            module.rcs_soil_c_t2_start, # soil t2
        ]


        inputs_w = [
            0,
            module.ha_w,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            change_rate.name, # TODO: Remove from math model
            total_biomass_w.value,
            module.final_rcs_biomass_t2_w,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            module.is_fire_used_w,
            combustion_factor_w.n2o,
            combustion_factor_w.ch4,
            combustion_factor_w.value,
            moisture_factor.value,
            defo_table_w.litter if mangroves_data is None else mangroves_data.litter,
            module.rcs_litter_t2_w,
            defo_table_w.dw if mangroves_data is None else mangroves_data.dw,
            module.rcs_deadwood_t2_w,
            module.hwp_w,
            MANGROVE_FACTOR if mangroves_data is not None else NON_MANGROVE_FACTOR,
            module.rcs_bg_t2_w,
            module.rcs_ag_t2_w,
            flu_w.value,
            mangroves_data.agb_c if mangroves_data is not None else ag_biomass_w.value,
            mangroves_data.bgb if mangroves_data is not None else bg_biomass_w.value,
            CN_RATIO_GRASSLAND,
            module.soc_after_defo_t2_w, # soil after defo t2
            soc_ref.value,
            module.rcs_soil_c_t2_w, # soil t2
        ]


        inputs_wo = [
            0,
            module.ha_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            change_rate.name, # TODO: Remove from math model
            total_biomass_wo.value,
            module.final_rcs_biomass_t2_wo,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            module.is_fire_used_wo,
            combustion_factor_wo.n2o,
            combustion_factor_wo.ch4,
            combustion_factor_wo.value,
            moisture_factor.value,
            defo_table_wo.litter if mangroves_data is None else mangroves_data.litter,
            module.rcs_litter_t2_wo,
            defo_table_wo.dw if mangroves_data is None else mangroves_data.dw,
            module.rcs_deadwood_t2_wo,
            module.hwp_wo,
            MANGROVE_FACTOR if mangroves_data is not None else NON_MANGROVE_FACTOR,
            module.rcs_bg_t2_wo,
            module.rcs_ag_t2_wo,
            flu_wo.value,
            mangroves_data.agb_c if mangroves_data is not None else ag_biomass_wo.value,
            mangroves_data.bgb if mangroves_data is not None else bg_biomass_wo.value,
            CN_RATIO_GRASSLAND,
            module.soc_after_defo_t2_wo, # soil after defo t2
            soc_ref.value,
            module.rcs_soil_c_t2_wo, # soil t2
        ]

        results_start = MathDeforestation(*inputs_start).calculate_emissions()
        results_w = MathDeforestation(*inputs_w).calculate_emissions()
        results_wo = MathDeforestation(*inputs_wo).calculate_emissions()

        return Result(results_w+results_start, results_wo+results_start, results_w - results_wo)

class AfforestationCalculator(BaseCalculator):
    """
    TODO: Remove
    Calculator for afforestation modules.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Afforestation module.
        """

        project = self.data.activity.project
        lut = self.data.land_use_type
        vt = self.data.vegetation_type
        continent = project.continent

        cml = {
            "climate": project.climate,
            "moisture": project.moisture,
            "land_use_type": lut,
        }

        cvt = {"continent": continent, "vegetation_type": vt}

        initial_biomass = ForestTotalBiomass.objects.get(**cml, continent=continent)
        combustion_factor = AfforestationCombustionFactor.objects.get(
            land_use_type=lut
        )

        # NOTE: Maybe merge all LandUseStockExchangeFactors and filter by model?
        flu = AfforestationLandUseStockExchangeFactor.objects.get(**cml)
        litter_dw = LitterDeadwoodCarbonStock.objects.get(vegetation_type=vt)
        ag_net_biomass = AboveGroundNetBiomassGrowth.objects.get(**cvt)

        le_20yrs = ag_net_biomass.value_upto_20_years
        gt_20yrs = ag_net_biomass.value_after_20_years

        bg_biomass_before_20_yrs = BelowGroundBiomass.objects.get_max_below_threshold(
            **cvt, threshold=le_20yrs
        )
        bg_biomass_after_20_yrs = BelowGroundBiomass.objects.get_max_below_threshold(
            **cvt, threshold=gt_20yrs
        )

        ag_biomass = AboveGroundBiomass.objects.get(**cvt)
        bg_biomass_le_125 = BelowGroundBiomass.objects.get_lowest_value(**cvt)
        bg_biomass_gt_125 = BelowGroundBiomass.objects.get_highest_value(**cvt)

        inputs = [
            self.data.ha_w,
            self.data.ha_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            initial_biomass.value,
            self.data.initial_biomass_t2,
            self.data.is_fire_used,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            combustion_factor.ch4,
            combustion_factor.n2o,
            combustion_factor.value,
            self.data.ha_w_rate.name,
            self.data.ha_w_rate.value,
            flu.value,
            project.soc_ref.value,
            project.soc_ref_t2,
            litter_dw.dw,
            self.data.final_dw_t2,
            litter_dw.litter,
            self.data.final_litter_t2,
            ag_net_biomass.value_upto_20_years,
            ag_net_biomass.value_after_20_years,
            bg_biomass_before_20_yrs.value,
            bg_biomass_after_20_yrs.value,
            self.data.final_ag_biomass_le_20yrs_t2,
            self.data.final_ag_biomass_gt_20yrs_t2,
            self.data.final_bg_biomass_le_20yrs_t2,
            self.data.final_bg_biomass_gt_20yrs_t2,
            self.data.final_rcs_t2,
            ag_biomass.value,
            bg_biomass_le_125.value,
            bg_biomass_gt_125.value,
        ]

        return Result(*affo.afforestation(*inputs))

class OtherLandUseCalculator(BaseCalculator):
    """
    TODO: Redo
    Calculator for other land use modules.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single OtherLandUse module.
        """

        project = self.data.activity.project
        climate = project.climate
        moisture = project.moisture
        continent = project.continent
        final_land_use_type = self.data.final_land_use_type
        initial_land_use = self.data.initial_land_use_type

        initial_biomass = ForestTotalBiomass.objects.get(
            climate=project.climate,
            moisture=project.moisture,
            continent=project.continent,
            land_use_type=initial_land_use,
        )

        total_biomass = TotalBiomassAfterDefo.objects.get(
            climate=climate,
            moisture=moisture,
            continent=continent,
            land_use_type=final_land_use_type,
        )

        flu_initial = AfforestationLandUseStockExchangeFactor.objects.get(
            climate=project.climate,
            moisture=project.moisture,
            land_use_type=initial_land_use,
        )

        flu_final = LandUseCarbonStockExchangeFactor.objects.get(
            climate=climate, moisture=moisture, land_use_type=final_land_use_type
        )

        c_n_ratio = CN_RATIO_GRASSLAND if initial_land_use.name == "Grassland" else CN_RATIO_FOREST

        moisture_factor = DefaultEmissionFactor.objects.get(
            moisture=moisture, input__name__icontains="Other N Inputs"
        )
        combustion_factor = AfforestationCombustionFactor.objects.get(
            land_use_type=initial_land_use
        )

        inputs = [
            initial_biomass.value,
            total_biomass.value,
            self.data.initial_biomass_t2,
            self.data.final_biomass_t2,
            project.soc_ref.value,
            flu_initial.value,
            flu_final.value,
            project.soc_ref_t2,
            self.data.final_soil_carbon_t2,  # TODO: Final socref?
            c_n_ratio,
            moisture_factor.value,
            combustion_factor.value,
            combustion_factor.n2o,
            combustion_factor.ch4,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            self.data.is_fire_used,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            self.data.ha_w_rate.name,
            self.data.ha_w_rate.value,
            self.data.ha_wo_rate.name,
            self.data.ha_wo_rate.value,
            self.data.ha_w,
            self.data.ha_wo,
        ]

        return Result(*oluc.calculate_w_wo_balance(*inputs))

class AnnualCroppingCalculator(BaseCalculator):
    """
    Calculator for annual cropping modules.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single AnnualCropping module.
        """

        input: AnnualCropping = self.data
        project: Project = input.activity.project
        change_rate = input.activity.change_rate
        climate = project.climate
        moisture = project.moisture

        cm = {
            "climate": climate,
            "moisture": moisture,
        }

        crop_type_start = input.crop_type_start
        crop_type_w = input.crop_type_w
        crop_type_wo = input.crop_type_wo

        minor_crop_type_start = input.minor_crop_type_start
        minor_crop_type_w = input.minor_crop_type_w
        minor_crop_type_wo = input.minor_crop_type_wo

        relative, relation = get_assessment_or_parent(self.data)
        is_parent = relation == "parent"

        burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Agricultural residues")

        fires_combustion_factor_start = FiresCombustionFactor.objects.get(crop_type=crop_type_start)
        fires_combustion_factor_w = FiresCombustionFactor.objects.get(crop_type=crop_type_w)
        fires_combustion_factor_wo = FiresCombustionFactor.objects.get(crop_type=crop_type_wo)

        n_estimation_factor_start = CropNitrousEstimationDefaultFactor.objects.get_or_grains(crop_type=crop_type_start)
        n_estimation_factor_w = CropNitrousEstimationDefaultFactor.objects.get_or_grains(crop_type=crop_type_w)
        n_estimation_factor_wo = CropNitrousEstimationDefaultFactor.objects.get_or_grains(crop_type=crop_type_wo)

        # Minor crop
        try:
            minor_combustion_factor_start = FiresCombustionFactor.objects.get(crop_type=crop_type_start)
            minor_combustion_factor_w = FiresCombustionFactor.objects.get(crop_type=crop_type_w)
            minor_combustion_factor_wo = FiresCombustionFactor.objects.get(crop_type=crop_type_wo)

            minor_burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Agricultural residues")

            minor_n_estimation_factor_start = CropNitrousEstimationDefaultFactor.objects.get_or_grains(crop_type=minor_crop_type_start)
            minor_n_estimation_factor_w = CropNitrousEstimationDefaultFactor.objects.get_or_grains(crop_type=minor_crop_type_w)
            minor_n_estimation_factor_wo = CropNitrousEstimationDefaultFactor.objects.get_or_grains(crop_type=minor_crop_type_wo)

        except:
            # If only one of the above operations fails, all minor variables must be set to None for the math model to workx
            minor_burning_emission_factor = None

            minor_combustion_factor_start = None
            minor_combustion_factor_w = None
            minor_combustion_factor_wo = None

            minor_n_estimation_factor_start = None
            minor_n_estimation_factor_w = None
            minor_n_estimation_factor_wo = None

        emission_factors_start = DefaultEmissionFactor.objects.get(moisture=moisture, organic_input_type=input.organic_input_type_start)
        emission_factors_w = DefaultEmissionFactor.objects.get(moisture=moisture, organic_input_type=input.organic_input_type_w)
        emission_factors_wo = DefaultEmissionFactor.objects.get(moisture=moisture, organic_input_type=input.organic_input_type_wo)

        flu = CroplandFLU.objects.get(**cm, crop_type__name="Long-Term Cultivated")

        fi_start = CroplandFI.objects.get(**cm,organic_input_type=input.organic_input_type_start)
        fi_w = CroplandFI.objects.get(**cm, organic_input_type=input.organic_input_type_w)
        fi_wo = CroplandFI.objects.get(**cm,organic_input_type=input.organic_input_type_wo)

        fmg_start = CroplandFMG.objects.get(**cm,tillage_management_type=input.tillage_management_type_start)
        fmg_w = CroplandFMG.objects.get(**cm,tillage_management_type=input.tillage_management_type_w)
        fmg_wo = CroplandFMG.objects.get(**cm,tillage_management_type=input.tillage_management_type_wo)

        crop_yield_start = (
            input.crop_yield_start
            if input.crop_yield_start
            else CropYieldStats.objects.get_or_region_average(
                continent=project.continent, crop_type=crop_type_start
            ).average
        )
        crop_yield_w = (
            input.crop_yield_w
            if input.crop_yield_w
            else CropYieldStats.objects.get_or_region_average(
                continent=project.continent, crop_type=crop_type_w
            ).average
        )
        crop_yield_wo = (
            input.crop_yield_wo
            if input.crop_yield_wo
            else CropYieldStats.objects.get_or_region_average(
                continent=project.continent, crop_type=crop_type_wo
            ).average
        )

        ha_data_start = [input.ha_start, 0]
        ha_data_w = [0, input.ha_w]
        ha_data_wo = [0, input.ha_wo]

        inputs_start = [
            *ha_data_start,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            change_rate.value,
            project.soc_ref.value,
            input.soc_ref_t2_start,
            flu.value,
            input.main_land_use_factor_t2_start,
            fi_start.value,
            input.main_organic_input_factor_t2_start,
            fmg_start.value,
            input.main_tillage_factor_t2_start,
            emission_factors_start.value,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            # TODO: Add residue_management_type attribute to model for cleaner logic
            burning_emission_factor.ch4
            if input.residue_management_type_start.name == "Burned"
            else None,
            fires_combustion_factor_start.value,
            input.main_biomass_factor_t2_start,
            n_estimation_factor_start.slope,
            n_estimation_factor_start.intercept,
            crop_yield_start,
            # TODO: Review looking for cleaner logic
            getattr(minor_burning_emission_factor, "ch4", None),
            getattr(minor_combustion_factor_start, "value", None),
            input.minor_biomass_factor_t2_start,
            getattr(minor_n_estimation_factor_start, "slope", None),
            getattr(minor_n_estimation_factor_start, "intercept", None),
            input.minor_yield_start,
            burning_emission_factor.n2o
            if input.residue_management_type_start.name == "Burned"
            else None,
            input.residue_management_type_start.name == "Retained",
            getattr(minor_burning_emission_factor, "n2o", None),
            getattr(input.minor_residue_management_type_start, "name", None)
            == "Retained",
            n_estimation_factor_start.n_ag_residues,
            n_estimation_factor_start.rs_t,
            n_estimation_factor_start.n_bg_t,
            getattr(minor_n_estimation_factor_start, "n_ag_residues", None),
            getattr(minor_n_estimation_factor_start, "rs_t", None),
            getattr(minor_n_estimation_factor_start, "n_bg_t", None),
        ]

        inputs_w = [
            *ha_data_w,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            change_rate.value,
            project.soc_ref.value,
            input.soc_ref_t2_w,
            flu.value,
            input.main_land_use_factor_t2_w,
            fi_w.value,
            input.main_organic_input_factor_t2_w,
            fmg_w.value,
            input.main_tillage_factor_t2_w,
            emission_factors_w.value,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            burning_emission_factor.ch4
            if input.residue_management_type_w.name == "Burned"
            else None,
            fires_combustion_factor_w.value,
            input.main_biomass_factor_t2_w,
            n_estimation_factor_w.slope,
            n_estimation_factor_w.intercept,
            crop_yield_w,
            getattr(minor_burning_emission_factor, "ch4", None),
            getattr(minor_combustion_factor_w, "value", None),
            input.minor_biomass_factor_t2_w,
            getattr(minor_n_estimation_factor_w, "slope", None),
            getattr(minor_n_estimation_factor_w, "intercept", None),
            input.minor_yield_w,
            burning_emission_factor.n2o
            if input.residue_management_type_w.name == "Burned"
            else None,
            input.residue_management_type_w.name == "Retained",
            getattr(minor_burning_emission_factor, "n2o", None),
            getattr(input.minor_residue_management_type_w, "name", None) == "Retained",
            n_estimation_factor_w.n_ag_residues,
            n_estimation_factor_w.rs_t,
            n_estimation_factor_w.n_bg_t,
            getattr(minor_n_estimation_factor_w, "n_ag_residues", None),
            getattr(minor_n_estimation_factor_w, "rs_t", None),
            getattr(minor_n_estimation_factor_w, "n_bg_t", None),
        ]

        inputs_wo = [
            *ha_data_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            change_rate.value,
            project.soc_ref.value,
            input.soc_ref_t2_wo,
            flu.value,
            input.main_land_use_factor_t2_wo,
            fi_wo.value,
            input.main_organic_input_factor_t2_wo,
            fmg_wo.value,
            input.main_tillage_factor_t2_wo,
            emission_factors_wo.value,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            burning_emission_factor.ch4
            if input.residue_management_type_wo.name == "Burned"
            else None,
            fires_combustion_factor_wo.value,
            input.main_biomass_factor_t2_wo,
            n_estimation_factor_wo.slope,
            n_estimation_factor_wo.intercept,
            crop_yield_wo,
            getattr(minor_burning_emission_factor, "ch4", None),
            getattr(minor_combustion_factor_wo, "value", None),
            input.minor_biomass_factor_t2_wo,
            getattr(minor_n_estimation_factor_wo, "slope", None),
            getattr(minor_n_estimation_factor_wo, "intercept", None),
            input.minor_yield_wo,
            burning_emission_factor.n2o
            if input.residue_management_type_wo.name == "Burned"
            else None,
            input.residue_management_type_wo.name == "Retained",
            getattr(minor_burning_emission_factor, "n2o", None),
            getattr(input.minor_residue_management_type_wo, "name", None) == "Retained",
            n_estimation_factor_wo.n_ag_residues,
            n_estimation_factor_wo.rs_t,
            n_estimation_factor_wo.n_bg_t,
            getattr(minor_n_estimation_factor_wo, "n_ag_residues", None),
            getattr(minor_n_estimation_factor_wo, "rs_t", None),
            getattr(minor_n_estimation_factor_wo, "n_bg_t", None),
        ]

        results_start = AnnualCropland(*inputs_start).calculate_emissions()
        results_w = AnnualCropland(*inputs_w).calculate_emissions()
        results_wo = AnnualCropland(*inputs_wo).calculate_emissions()

        results = Result(results_w+results_start, results_wo+results_start, results_w-results_wo)

        return results

class PerennialCroppingCalculator(BaseCalculator):
    """
    Calculator for perennial cropping.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single PerennialCropping module.
        """

        project = self.data.activity.project
        module: PerennialCropping = self.data
        climate = project.climate
        moisture = project.moisture
        continent = project.continent
        parent, _ = get_assessment_or_parent(module)
        change_rate = module.activity.change_rate

        cm = {
            "climate": climate,
            "moisture": moisture,
        }

        cmc = {
            "climate": climate,
            "moisture": moisture,
            "continent": continent,
        }

        burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Savanna and grassland")

        # TODO: Replace 'other' with all the other crop_types in db
        fires_combustion_factor_start = FiresCombustionFactor.objects.get_or_other(crop_type=module.crop_type_start)
        fires_combustion_factor_w = FiresCombustionFactor.objects.get_or_other(crop_type=module.crop_type_w)
        fires_combustion_factor_wo = FiresCombustionFactor.objects.get_or_other(crop_type=module.crop_type_wo)

        ag_default_start = PerennialAGB.objects.get_or_default(**cmc,crop_type=module.crop_type_start)
        ag_default_w = PerennialAGB.objects.get_or_default(**cmc,crop_type=module.crop_type_w)
        ag_default_wo = PerennialAGB.objects.get_or_default(**cmc,crop_type=module.crop_type_wo)

        agb_max_c_start = PerennialMaxAGB.objects.get(climate=climate, crop_type=module.crop_type_start)
        agb_max_c_w = PerennialMaxAGB.objects.get(climate=climate, crop_type=module.crop_type_w)
        agb_max_c_wo = PerennialMaxAGB.objects.get(climate=climate, crop_type=module.crop_type_wo)

        bg_default_start = PerennialBGB.objects.get_or_default(**cmc,crop_type=module.crop_type_start)
        bg_default_w = PerennialBGB.objects.get_or_default(**cmc,crop_type=module.crop_type_w)
        bg_default_wo = PerennialBGB.objects.get_or_default(**cmc,crop_type=module.crop_type_wo)

        if parent:
            # TODO: initial_land_use and final_land_use change based on what's initial and whats final. Differentiate in LUC_From | LUC_To
            # NOTE: Maybe not? It's possible that the correct one is always final_land_use_type. Ask EX-ACT Team
            flu = AfforestationFLU.objects.get(**cm,land_use_type=parent.final_land_use_type)
        else:
            flu = CroplandFLU.objects.get(**cm,crop_type__name="Perennial/Tree Crop")

        fi_start = CroplandFI.objects.get(**cm,organic_input_type=module.organic_input_type_start)
        fi_w = CroplandFI.objects.get(**cm,organic_input_type=module.organic_input_type_w)
        fi_wo = CroplandFI.objects.get(**cm,organic_input_type=module.organic_input_type_wo)

        fmg_start = CroplandFMG.objects.get(**cm,tillage_management_type=module.tillage_management_type_start)
        fmg_w = CroplandFMG.objects.get(**cm,tillage_management_type=module.tillage_management_type_w)
        fmg_wo = CroplandFMG.objects.get(**cm,tillage_management_type=module.tillage_management_type_wo)

        default_fire_periodicity = AnnualCroplandParameter.objects.get_or_default(name="default_fire_periodicity")

        inputs_start = [
            module.ha_start,
            0,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            module.is_biomass_burned_start,
            burning_emission_factor.ch4,
            burning_emission_factor.n2o,
            fires_combustion_factor_start.value,
            default_fire_periodicity.value,
            module.fire_periodicity_t2_start,
            module.residue_burned_t2_start,
            ag_default_start.value,
            module.ag_t2_start,
            agb_max_c_start.value,
            bg_default_start.value,
            module.bg_t2_start,
            project.soc_ref.value,
            module.soc_t2_start,
            flu.value,
            module.flu_t2_start,
            fi_start.value,
            module.input_factor_t2_start,
            fmg_start.value,
            module.tillage_factor_t2_start
        ]

        inputs_w = [
            0,
            module.ha_w,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            module.is_biomass_burned_w,
            burning_emission_factor.ch4,
            burning_emission_factor.n2o,
            fires_combustion_factor_w.value,
            default_fire_periodicity.value,
            module.fire_periodicity_t2_w,
            module.residue_burned_t2_w,
            ag_default_w.value,
            module.ag_t2_w,
            agb_max_c_w.value,
            bg_default_w.value,
            module.bg_t2_w,
            project.soc_ref.value,
            module.soc_t2_w,
            flu.value,
            module.flu_t2_w,
            fi_w.value,
            module.input_factor_t2_w,
            fmg_w.value,
            module.tillage_factor_t2_w
        ]

        inputs_wo = [
            0,
            module.ha_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            module.is_biomass_burned_wo,
            burning_emission_factor.ch4,
            burning_emission_factor.n2o,
            fires_combustion_factor_wo.value,
            default_fire_periodicity.value,
            module.fire_periodicity_t2_wo,
            module.residue_burned_t2_wo,
            ag_default_wo.value,
            module.ag_t2_wo,
            agb_max_c_wo.value,
            bg_default_wo.value,
            module.bg_t2_wo,
            project.soc_ref.value,
            module.soc_t2_wo,
            flu.value,
            module.flu_t2_wo,
            fi_wo.value,
            module.input_factor_t2_wo,
            fmg_wo.value,
            module.tillage_factor_t2_wo
        ]

        results_start = PerennialCropland(*inputs_start).calculate_emissions()
        results_w = PerennialCropland(*inputs_w).calculate_emissions()
        results_wo = PerennialCropland(*inputs_wo).calculate_emissions()

        # BUG: Results for perennial crops do not add up. Wait for Lorenzo's unlocked Excel files
        return Result(results_w+results_start, results_wo+results_start, results_w-results_wo)

class FloodedRiceCalculator(BaseCalculator):
    """
    Calculator for flooded rice.
    """

    def calculate(self) -> Result:

        input: FloodedRice = self.data
        project: Project = input.activity.project
        
        flu = LandUseCarbonStockExchangeFactor.objects.get(land_use_type__name="Flooded Rice", climate=project.climate, moisture=project.moisture)
        efc = RiceDefaultEmissionFactor.objects.get(continent=project.country.continent,)
        yield_ref = RiceYield.objects.get(continent=project.continent)

        sfw_start = RiceSFW.objects.get(water_management_type_after_cultivation=input.water_management_type_after_cultivation_start)
        sfw_w = RiceSFW.objects.get(water_management_type_after_cultivation=input.water_management_type_after_cultivation_w)
        sfw_wo = RiceSFW.objects.get(water_management_type_after_cultivation=input.water_management_type_after_cultivation_wo)

        sfp_start = RiceSFP.objects.get(water_management_type_before_cultivation=input.water_management_type_before_cultivation_start)
        sfp_w = RiceSFP.objects.get(water_management_type_before_cultivation=input.water_management_type_before_cultivation_w)
        sfp_wo = RiceSFP.objects.get(water_management_type_before_cultivation=input.water_management_type_before_cultivation_wo)

        cfoa_start = RiceSFO.objects.get(organic_amendment_type=input.organic_amendment_type_start)
        cfoa_w = RiceSFO.objects.get(organic_amendment_type=input.organic_amendment_type_w)
        cfoa_wo = RiceSFO.objects.get(organic_amendment_type=input.organic_amendment_type_wo)

        n_estimation_factor = CropNitrousEstimationDefaultFactor.objects.get(crop_type__name="Rice")
        burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Agricultural residues")
        rice_cf = FiresCombustionFactor.objects.get(crop_type__name="Rice")

        inputs_start = [
            input.ha_start,
            0,
            efc.value,
            input.efc_t2_start,
            sfw_start.value,
            input.sfw_t2_start,
            sfp_start.value,
            input.sfp_t2_start,
            cfoa_start.value,
            input.sfo_t2_start,
            input.efi_t2_start,
            yield_ref.value,
            input.crop_yield_start,
            n_estimation_factor.slope,
            n_estimation_factor.intercept,
            input.rice_straw_t2_start,
            burning_emission_factor.ch4,
            rice_cf.value,
            burning_emission_factor.n2o,
            project.gw_potential.n2o,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate.name,
            project.gw_potential.ch4,
            efc.cultivation_period,
            input.cultivation_period_start,
            project.soc_ref.value,
            project.soc_ref_t2,
            flu.value,
            input.land_use_factor_t2_start,
            1, # TODO: Fi. Will be added in the future
            None, # Fi t2
            1, # TODO: Fmg. Will be added in the future
            None, # Fmg t2
        ]

        inputs_w = [
            0,
            input.ha_w,
            efc.value,
            input.efc_t2_w,
            sfw_w.value,
            input.sfw_t2_w,
            sfp_w.value,
            input.sfp_t2_w,
            cfoa_w.value,
            input.sfo_t2_w,
            input.efi_t2_w,
            yield_ref.value,
            input.crop_yield_w,
            n_estimation_factor.slope,
            n_estimation_factor.intercept,
            input.rice_straw_t2_w,
            burning_emission_factor.ch4,
            rice_cf.value,
            burning_emission_factor.n2o,
            project.gw_potential.n2o,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate.name,
            project.gw_potential.ch4,
            efc.cultivation_period,
            input.cultivation_period_w,
            project.soc_ref.value,
            project.soc_ref_t2,
            flu.value,
            input.land_use_factor_t2_w,
            1, # TODO: Fi. Will be added in the future
            None, # Fi t2
            1, # TODO: Fmg. Will be added in the future
            None, # Fmg t2
        ]

        inputs_wo = [
            0,
            input.ha_wo,
            efc.value,
            input.efc_t2_wo,
            sfw_wo.value,
            input.sfw_t2_wo,
            sfp_wo.value,
            input.sfp_t2_wo,
            cfoa_wo.value,
            input.sfo_t2_wo,
            input.efi_t2_wo,
            yield_ref.value,
            input.crop_yield_wo,
            n_estimation_factor.slope,
            n_estimation_factor.intercept,
            input.rice_straw_t2_wo,
            burning_emission_factor.ch4,
            rice_cf.value,
            burning_emission_factor.n2o,
            project.gw_potential.n2o,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate.name,
            project.gw_potential.ch4,
            efc.cultivation_period,
            input.cultivation_period_wo,
            project.soc_ref.value,
            project.soc_ref_t2,
            flu.value,
            input.land_use_factor_t2_wo,
            1, # TODO: Fi. Will be added in the future
            None, # Fi t2
            1, # TODO: Fmg. Will be added in the future
            None, # Fmg t2
        ]

        math_start = MathFloodedRice(*inputs_start)
        math_w = MathFloodedRice(*inputs_w)
        math_wo = MathFloodedRice(*inputs_wo)

        math_start.calculate_emissions()
        math_w.calculate_emissions()
        math_wo.calculate_emissions()

        results_start = math_start.total_emissions
        results_w = math_w.total_emissions
        results_wo = math_wo.total_emissions

        return Result(results_w+results_start, results_wo+results_start, results_w-results_wo)

class GrasslandCalculator(BaseCalculator):
    """
    Calculator for grassland.
    # TODO: Implement class-based math model
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Grassland module.
        """

        module: Grassland = self.data
        project = module.activity.project
        change_rate = module.activity.change_rate
        ef = BurningEmissionFactor.objects.get(category__name="Savanna and grassland")
        agb = GrasslandAGB.objects.get(climate=project.climate, moisture=project.moisture)
        cf = GrasslandParameter.objects.get(name="default_combustion_factor").value

        soc_start = GrasslandStockExchangeFactor.objects.get(grassland_management_type=module.grassland_management_type_start, climate=project.climate)
        soc_w = GrasslandStockExchangeFactor.objects.get(grassland_management_type=module.grassland_management_type_w, climate=project.climate)
        soc_wo = GrasslandStockExchangeFactor.objects.get(grassland_management_type=module.grassland_management_type_wo, climate=project.climate)

        inputs_w = [
            0,
            module.ha_w,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            module.fire_periodicity_w,
            module.is_fire_used_w,
            ef.ch4,
            ef.n2o,
            agb.value,
            module.agb_t2_w,
            cf,
            module.combustion_factor_t2_start,
            project.soc_ref.value,
            module.soil_carbon_t2_start,
            module.soil_carbon_t2_w,
            soc_start.fmg,
            soc_w.fmg,
            soc_start.flu,
            soc_w.flu,
            soc_start.fi,
            soc_w.fi,
        ]

        inputs_wo = [
            0,
            module.ha_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            module.fire_periodicity_wo,
            module.is_fire_used_wo,
            ef.ch4,
            ef.n2o,
            agb.value,
            module.agb_t2_wo,
            cf,
            module.combustion_factor_t2_start,
            project.soc_ref.value,
            module.soil_carbon_t2_start,
            module.soil_carbon_t2_wo,
            soc_start.fmg,
            soc_wo.fmg,
            soc_start.flu,
            soc_wo.flu,
            soc_start.fi,
            soc_wo.fi,
        ]

        math_w = MathGrassland(*inputs_w)
        math_wo = MathGrassland(*inputs_wo)

        math_w.calculate_emissions()
        math_wo.calculate_emissions()

        results_w = math_w.total_emissions
        results_wo = math_wo.total_emissions

        return Result(results_w, results_wo, results_w-results_wo)

class SmallFisheryCalculator(BaseCalculator):
    """
    Calculator for small fishery.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single SmallFishery module.
        """

        module: SmallFishery = self.data
        project = module.activity.project

        ef_diesel_default_list = EnergyDefaultEmissionFactor.objects.filter(fuel_type__fuel_use_type__name__contains="Off-Road")

        # Average of all default emission factors for gasoil/diesel
        ef_diesel_default = sum([ef.t_co2_eq for ef in ef_diesel_default_list]) / len(ef_diesel_default_list)

        fui_default_start = SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_start)
        fui_default_w = SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_w)
        fui_default_wo = SmallFisheryFUI.objects.get_value_or_average(fishery_type=module.fishery_type, gear_type=module.gear_type_wo)

        lost_refrigerant_default = SmallFisheryParameter.objects.get(name="lost_refrigerant_default").value
        tonnes_ice_default = SmallFisheryParameter.objects.get(name="tonnes_ice_default").value
        kw_tonnes = SmallFisheryParameter.objects.get(name="kw_tonnes").value

        electricity_emission = ElectricityEmission.objects.get(country=project.country, continent=project.continent)

        inputs_w = [
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
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

        inputs_wo = [
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
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

        math_w = MathFishery(*inputs_w)
        math_wo = MathFishery(*inputs_wo)

        math_w.calculate_emissions()
        math_wo.calculate_emissions()

        results_w = math_w.total_emissions
        results_wo = math_wo.total_emissions

        return Result(results_w, results_wo, results_w-results_wo)

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
        ef_diesel_default_list = EnergyDefaultEmissionFactor.objects.filter(
            fuel_type__fuel_use_type__name__contains="Off-Road"
        )

        # Average of all default emission factors for gasoil/diesel
        ef_diesel_default = sum(
            [ef.t_co2_eq for ef in ef_diesel_default_list]
        ) / len(ef_diesel_default_list)

        fui_default_start = LargeFisheryFUI.objects.get_value_or_average(
            fish_type=module.fish_type,
            gear_type=module.gear_type_start,
        )
        fui_default_w = LargeFisheryFUI.objects.get_value_or_average(
            fish_type=module.fish_type,
            gear_type=module.gear_type_w,
        )
        fui_default_wo = LargeFisheryFUI.objects.get_value_or_average(
            fish_type=module.fish_type,
            gear_type=module.gear_type_wo,
        )

        lost_refrigerant_default = LargeFisheryParameter.objects.get(name="lost_refrigerant_default").value
        tonnes_ice_default = LargeFisheryParameter.objects.get(name="tonnes_ice_default").value
        kw_tonnes = LargeFisheryParameter.objects.get(name="kw_tonnes").value

        electricity_country = (
            module.inshore_ice_production_country_t2
            if module.inshore_ice_production_country_t2
            else project.country
        )

        electricity_emission = ElectricityEmission.objects.get(
            country=electricity_country, continent=project.continent
        )

        #  TODO: Change fui to T2

        inputs_w = [
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
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

        inputs_wo = [
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
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

        math_w = MathFishery(*inputs_w)
        math_wo = MathFishery(*inputs_wo)

        math_w.calculate_emissions()
        math_wo.calculate_emissions()

        results_w = math_w.total_emissions
        results_wo = math_wo.total_emissions

        return Result(results_w, results_wo, results_w-results_wo)

class ForestCalculator(BaseCalculator):
    """
    TODO: Redo
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Forest module.
        """

        project: Project = self.data.activity.project
        data = None
        agb = None
        bgb = None
        soc = None
        LAND_INPUT_FACTOR_DEFAULT = 1
        AGB_MULTIPLICATION_FACTOR = 0.47

        if self.data.vegetation_type.name == "Mangrove Forest":
            data = DataOnMangrove.objects.get(
                climate=project.climate, moisture=project.moisture
            )
            agb = data.agb_c
            bgb = data.bgb
            soc = data.soc_ref
        else:
            data = LitterDeadwoodCarbonStock.objects.get(
                vegetation_type=self.data.vegetation_type
            )
            f_agb = ForestAGB.objects.get(
                continent=project.continent, vegetation_type=self.data.vegetation_type
            )
            f_bgb = BelowGroundBiomass.objects.get_max_below_threshold(
                continent=project.continent,
                vegetation_type=self.data.vegetation_type,
                threshold=f_agb.value,
            )

            agb = f_agb.value * AGB_MULTIPLICATION_FACTOR
            bgb = f_bgb.value * agb
            soc = project.soc_ref.value

        cf: CombustionFactor = CombustionFactor.objects.get(
            vegetation_type=self.data.vegetation_type
        )

        inputs = [
            self.data.ha_start,
            self.data.ha_w,
            self.data.ha_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            self.data.ha_w_rate.name,
            self.data.ha_wo_rate.name,
            self.data.ha_w_rate.value,
            self.data.ha_wo_rate.value,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            self.data.degradation_level_w.value,
            self.data.degradation_level_w_t2.value
            if self.data.degradation_level_w_t2
            else None,
            self.data.degradation_level_wo.value,
            self.data.degradation_level_wo_t2.value
            if self.data.degradation_level_wo_t2
            else None,
            self.data.degradation_level_start.value,
            self.data.degradation_level_start_t2.value
            if self.data.degradation_level_start_t2
            else None,
            agb,
            self.data.ag_carbon_t2,
            bgb,
            self.data.bg_carbon_t2,
            data.litter,
            self.data.litter_t2,
            data.dw,
            self.data.deadwood_t2,
            soc,
            self.data.soil_carbon_t2,
            LAND_INPUT_FACTOR_DEFAULT,
            self.data.land_input_factor_start_t2,
            self.data.land_input_factor_w_t2,
            self.data.land_input_factor_wo_t2,
            self.data.fire_periodicity_w,
            self.data.fire_periodicity_wo,
            self.data.is_fire_used_w,
            self.data.is_fire_used_wo,
            self.data.fire_impact_percentage_w,
            self.data.fire_impact_percentage_wo,
            cf.value,
            cf.ch4,
            cf.n2o,
        ]

        return Result(*forest_management.calculate_emissions(*inputs))

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

        inputs_w = [
            module.annual_production_start,
            module.annual_production_w,
            NITROUS_EF_DEFAULT,
            module.n2o_from_production_t2_start,
            module.n2o_from_production_t2_w,
            project.gw_potential.n2o,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
        ]

        inputs_wo = [
            module.annual_production_start,
            module.annual_production_wo,
            NITROUS_EF_DEFAULT,
            module.n2o_from_production_t2_start,
            module.n2o_from_production_t2_wo,
            project.gw_potential.n2o,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            change_rate.name,
        ]

        results_w = MathAquaculture(*inputs_w)
        results_w.calculate_emissions()

        results_wo = MathAquaculture(*inputs_wo)
        results_wo.calculate_emissions()

        emissions_w = results_w.total_emissions
        emissions_wo = results_wo.total_emissions

        return Result(emissions_w, emissions_wo, emissions_w - emissions_wo)

class InputCalculator(BaseCalculator):
    """
    Calculator for inputs.
    """

    def calculate(self) -> list[Result]:
        project: Project = self.data.activity.project
        input: Input = self.data

        ref = InputReference.objects.get(
            gw_potential=project.gw_potential, input_type=self.data.input_type
        )

        ef = InputEmissionFactor.objects.get(
            input_type=self.data.input_type,
            climate=project.climate,
            moisture=project.moisture,
        )

        inputs_w = [
            input.value_start,
            input.value_w,
            input.value_w_rate.name,
            ef.co2_value,
            input.co2_emissions_t2,
            ref.co2_multiplier,
            ref.co2_emissions_multiplier,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            ef.n2o_value,
            input.n2o_emissions_t2,
            ref.n2o_quantity_multiplier,
            ref.n2o_emissions_multiplier,
            ef.co2_eq_value,
            input.co2_e_emissions_t2,
            ref.production_quantity_multiplier,
            ref.production_emissions_multiplier,
        ]

        inputs_wo = [
            input.value_start,
            input.value_wo,
            input.value_wo_rate.name,
            ef.co2_value,
            input.co2_emissions_t2,
            ref.co2_multiplier,
            ref.co2_emissions_multiplier,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            ef.n2o_value,
            input.n2o_emissions_t2,
            ref.n2o_quantity_multiplier,
            ref.n2o_emissions_multiplier,
            ef.co2_eq_value,
            input.co2_e_emissions_t2,
            ref.production_quantity_multiplier,
            ref.production_emissions_multiplier,
        ]

        results_w = MathInputs(*inputs_w).calculate_emissions()
        results_wo = MathInputs(*inputs_wo).calculate_emissions()

        results = [results_w, results_wo, results_w - results_wo]

        return Result(*results)

class ElectricityCalculator(BaseCalculator):
    """
    #TODO: Calculator for energy.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Energy module.
        """

        input: Electricity = self.data
        project: Project = self.data.activity.project

        elec: ElectricityEmission = ElectricityEmission.objects.get(
            country=project.country,
            continent=project.country.continent,  # TODO: Remove continent from model and from project
        )

        inputs_w = [
            elec.operating_margin
            if input.ef_source.name == "Operating Margin"
            else elec.combined_margin,
            input.ef_t2,
            input.mwh_start,
            input.mwh_w,
            input.transmission_loss,
            input.activity.change_rate.name,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
        ]

        res_w = ElectryicityConsumption(*inputs_w).calculate_emissions()

        inputs_wo = [
            elec.operating_margin
            if input.ef_source.name == "Operating Margin"
            else elec.combined_margin,
            input.ef_t2,
            input.mwh_start,
            input.mwh_wo,
            input.transmission_loss,
            input.activity.change_rate.name,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
        ]

        res_wo = ElectryicityConsumption(*inputs_wo).calculate_emissions()

        return Result(res_w, res_wo, res_w - res_wo)

    # FuelType can be solid or liquid. Call different classes based on that

class FuelCalculator(BaseCalculator):
    """
    Calculator for fuel
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Fuel module.
        """

        input: Fuel = self.data
        project: Project = self.data.activity.project

        macro_fuel_type = input.fuel_type.macro_fuel_type.name

        ef = EnergyDefaultEmissionFactor.objects.get(
            fuel_type=input.fuel_type,
        )

        if macro_fuel_type == "Liquid":
            input_w = [
                ef.t_co2_eq,
                input.ef_t2,
                input.fuel_start,
                input.fuel_w,
                input.activity.change_rate.name,
                project.implementation_duration_yrs,
                project.capitalization_duration_yrs,
            ]

            input_wo = [
                ef.t_co2_eq,
                input.ef_t2,
                input.fuel_start,
                input.fuel_wo,
                input.activity.change_rate.name,
                project.implementation_duration_yrs,
                project.capitalization_duration_yrs,
            ]

            res_w = FuelConsumption(*input_w).calculate_emissions()
            res_wo = FuelConsumption(*input_wo).calculate_emissions()

            return Result(res_w, res_wo, res_w - res_wo)

        elif macro_fuel_type == "Solid":
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
                project.implementation_duration_yrs,
                project.capitalization_duration_yrs,
            ]

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
                project.implementation_duration_yrs,
                project.capitalization_duration_yrs,
            ]

            res_w = SolidConsumption(*input_w).calculate_emissions()
            res_wo = SolidConsumption(*input_wo).calculate_emissions()

            return Result(res_w, res_wo, res_w - res_wo)

        return Result(0, 0, 0)
    
class SettlementCalculator(BaseCalculator):
    """
    Calculator for settlements
    """

    def calculate(self) -> Result:
        input: Settlement = self.data
        result = Result()

        for building in input.buildings.all():
            result.add(BuildingCalculator(building).calculate())

        for road in input.roads.all():
            result.add(RoadCalculator(road).calculate())

        return result
    
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

        ef_w: BuildingEmissionFactor = BuildingEmissionFactor.objects.get(building_type=input.building_type_w)
        ef_wo: BuildingEmissionFactor = BuildingEmissionFactor.objects.get(building_type=input.building_type_wo)

        inputs_w = [
            ef_w.value,
            input.ef_t2_w,
            input.area_m2_w,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate.name,
        ]

        inputs_wo = [
            ef_wo.value,
            input.ef_t2_wo,
            input.area_m2_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate.name,
        ]

        math_w = MathRoads(*inputs_w)
        math_wo = MathRoads(*inputs_wo)

        math_w.calculate_emissions()
        math_wo.calculate_emissions()

        results_w = math_w.total_emissions
        results_wo = math_wo.total_emissions

        return Result(results_w, results_wo, results_w - results_wo)
    
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

        ef_w: RoadEmissionFactor = RoadEmissionFactor.objects.get(road_type=input.road_type_w)
        ef_wo: RoadEmissionFactor = RoadEmissionFactor.objects.get(road_type=input.road_type_wo)

        inputs_w = [
            ef_w.value,
            input.ef_t2_w,
            input.area_m2_w,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate.name,
        ]

        inputs_wo = [
            ef_wo.value,
            input.ef_t2_wo,
            input.area_m2_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate.name,
        ]

        math_w = MathRoads(*inputs_w)
        math_wo = MathRoads(*inputs_wo)

        math_w.calculate_emissions()
        math_wo.calculate_emissions()

        results_w = math_w.total_emissions
        results_wo = math_wo.total_emissions

        return Result(results_w, results_wo, results_w - results_wo)

class LivestockCalculator(BaseCalculator):
    """
    Calculator for livestock
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Livestock module.
        """

        project: Project = self.data.activity.project
        input: Livestock = self.data

        tam_ch4_start = LivestockTAM.objects.get(
            livestock_production_type=input.livestock_production_type_start,
            livestock_category_type=input.livestock_category_type_start,
            ipcc_region=input.activity.project.country.ipcc_region,
        )

        tam_ch4_w = LivestockTAM.objects.get(
            livestock_production_type=input.livestock_production_type_w,
            livestock_category_type=input.livestock_category_type_w,
            ipcc_region=input.activity.project.country.ipcc_region,
        )

        tam_ch4_wo = LivestockTAM.objects.get(
            livestock_production_type=input.livestock_production_type_wo,
            livestock_category_type=input.livestock_category_type_wo,
            ipcc_region=input.activity.project.country.ipcc_region,
        )

        vser_ch4_start = LivestockVSER.objects.get(
            livestock_production_type=input.livestock_production_type_start,
            livestock_category_type=input.livestock_category_type_start,
            ipcc_region=input.activity.project.country.ipcc_region,
        )

        vser_ch4_w = LivestockVSER.objects.get(
            livestock_production_type=input.livestock_production_type_w,
            livestock_category_type=input.livestock_category_type_w,
            ipcc_region=input.activity.project.country.ipcc_region,
        )

        vser_ch4_wo = LivestockVSER.objects.get(
            livestock_production_type=input.livestock_production_type_wo,
            livestock_category_type=input.livestock_category_type_wo,
            ipcc_region=input.activity.project.country.ipcc_region,
        )

        ef_ch4_prp_start = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.CH4,
            livestock_category_type=input.livestock_category_type_start,
            livestock_production_type=input.livestock_production_type_start,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        ef_ch4_prp_w = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.CH4,
            livestock_category_type=input.livestock_category_type_w,
            livestock_production_type=input.livestock_production_type_w,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        ef_ch4_prp_wo = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.CH4,
            livestock_category_type=input.livestock_category_type_wo,
            livestock_production_type=input.livestock_production_type_wo,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        ef_ch4_systems_start = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.CH4,
                livestock_category_type=input.livestock_category_type_start,
                livestock_production_type=input.livestock_production_type_start,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_ch4_systems_w = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.CH4,
                livestock_category_type=input.livestock_category_type_w,
                livestock_production_type=input.livestock_production_type_w,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_ch4_systems_wo = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.CH4,
                livestock_category_type=input.livestock_category_type_wo,
                livestock_production_type=input.livestock_production_type_wo,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_ch4_system_values_start = [system.value for system in ef_ch4_systems_start]
        ef_ch4_system_values_w = [system.value for system in ef_ch4_systems_w]
        ef_ch4_system_values_wo = [system.value for system in ef_ch4_systems_wo]

        animal_waste_prp_start = LivestockAnimalWasteManagementSystem.objects.get(
            livestock_category_type=input.livestock_category_type_start,
            livestock_production_type=input.livestock_production_type_start,
            ipcc_region=input.activity.project.country.ipcc_region,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        animal_waste_prp_w = LivestockAnimalWasteManagementSystem.objects.get(
            livestock_category_type=input.livestock_category_type_w,
            livestock_production_type=input.livestock_production_type_w,
            ipcc_region=input.activity.project.country.ipcc_region,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        animal_waste_prp_wo = LivestockAnimalWasteManagementSystem.objects.get(
            livestock_category_type=input.livestock_category_type_wo,
            livestock_production_type=input.livestock_production_type_wo,
            ipcc_region=input.activity.project.country.ipcc_region,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        animal_waste_management_systems_start = (
            LivestockAnimalWasteManagementSystem.objects.filter(
                livestock_category_type=input.livestock_category_type_start,
                livestock_production_type=input.livestock_production_type_start,
                ipcc_region=input.activity.project.country.ipcc_region,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        animal_waste_management_systems_w = (
            LivestockAnimalWasteManagementSystem.objects.filter(
                livestock_category_type=input.livestock_category_type_w,
                livestock_production_type=input.livestock_production_type_w,
                ipcc_region=input.activity.project.country.ipcc_region,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        animal_waste_management_systems_wo = (
            LivestockAnimalWasteManagementSystem.objects.filter(
                livestock_category_type=input.livestock_category_type_wo,
                livestock_production_type=input.livestock_production_type_wo,
                ipcc_region=input.activity.project.country.ipcc_region,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        # list comprehension to get the animal waste management systems values
        animal_waste_management_systems_values_start = [
            system.value for system in animal_waste_management_systems_start
        ]
        animal_waste_management_systems_values_w = [
            system.value for system in animal_waste_management_systems_w
        ]
        animal_waste_management_systems_values_wo = [
            system.value for system in animal_waste_management_systems_wo
        ]

        ch4_enteric_start = MethaneEntericFermentationFactor.objects.get(
            livestock_category_type=input.livestock_category_type_start,
            livestock_production_type=input.livestock_production_type_start,
            ipcc_region=input.activity.project.country.ipcc_region,
        )

        ch4_enteric_w = MethaneEntericFermentationFactor.objects.get(
            livestock_category_type=input.livestock_category_type_w,
            livestock_production_type=input.livestock_production_type_w,
            ipcc_region=input.activity.project.country.ipcc_region,
        )

        ch4_enteric_wo = MethaneEntericFermentationFactor.objects.get(
            livestock_category_type=input.livestock_category_type_wo,
            livestock_production_type=input.livestock_production_type_wo,
            ipcc_region=input.activity.project.country.ipcc_region,
        )

        prp_n2o_direct_ef_start = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.N2O,
            livestock_category_type=input.livestock_category_type_start,
            livestock_production_type=input.livestock_production_type_start,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        prp_n2o_direct_ef_w = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.N2O,
            livestock_category_type=input.livestock_category_type_w,
            livestock_production_type=input.livestock_production_type_w,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        prp_n2o_direct_ef_wo = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.N2O,
            livestock_category_type=input.livestock_category_type_wo,
            livestock_production_type=input.livestock_production_type_wo,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        prp_n2o_volatilization_ef_start = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.N2O_VOLATILIZATION,
            livestock_category_type=input.livestock_category_type_start,
            livestock_production_type=input.livestock_production_type_start,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        prp_n2o_volatilization_ef_w = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.N2O_VOLATILIZATION,
            livestock_category_type=input.livestock_category_type_w,
            livestock_production_type=input.livestock_production_type_w,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        prp_n2o_volatilization_ef_wo = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.N2O_VOLATILIZATION,
            livestock_category_type=input.livestock_category_type_wo,
            livestock_production_type=input.livestock_production_type_wo,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        prp_n2o_leaching_ef_start = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.N2O_LEACHING,
            livestock_category_type=input.livestock_category_type_wo,
            livestock_production_type=input.livestock_production_type_wo,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        prp_n2o_leaching_ef_w = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.N2O_LEACHING,
            livestock_category_type=input.livestock_category_type_wo,
            livestock_production_type=input.livestock_production_type_wo,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        prp_n2o_leaching_ef_wo = LivestockManureEF.objects.get(
            emission_type__name=EmissionTypes.N2O_LEACHING,
            livestock_category_type=input.livestock_category_type_wo,
            livestock_production_type=input.livestock_production_type_wo,
            climate=project.climate,
            moisture=project.moisture,
            manure_management_type__name=ManureManagementTypes.PRP,
        )

        ef_n2o_direct_systems_start = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.N2O,
                livestock_category_type=input.livestock_category_type_start,
                livestock_production_type=input.livestock_production_type_start,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_direct_systems_w = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.N2O,
                livestock_category_type=input.livestock_category_type_w,
                livestock_production_type=input.livestock_production_type_w,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_direct_systems_wo = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.N2O,
                livestock_category_type=input.livestock_category_type_wo,
                livestock_production_type=input.livestock_production_type_wo,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_direct_systems_start = [s.value for s in ef_n2o_direct_systems_start]
        ef_n2o_direct_systems_w = [s.value for s in ef_n2o_direct_systems_w]
        ef_n2o_direct_systems_wo = [s.value for s in ef_n2o_direct_systems_wo]

        ef_n2o_volatilization_systems_start = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=input.livestock_category_type_start,
                livestock_production_type=input.livestock_production_type_start,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_volatilization_systems_w = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=input.livestock_category_type_w,
                livestock_production_type=input.livestock_production_type_w,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_volatilization_systems_wo = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=input.livestock_category_type_wo,
                livestock_production_type=input.livestock_production_type_wo,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_volatilization_systems_start = [
            s.value for s in ef_n2o_volatilization_systems_start
        ]
        ef_n2o_volatilization_systems_w = [
            s.value for s in ef_n2o_volatilization_systems_w
        ]
        ef_n2o_volatilization_systems_wo = [
            s.value for s in ef_n2o_volatilization_systems_wo
        ]

        ef_n2o_leaching_systems_start = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.N2O_LEACHING,
                livestock_category_type=input.livestock_category_type_start,
                livestock_production_type=input.livestock_production_type_start,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_leaching_systems_w = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.N2O_LEACHING,
                livestock_category_type=input.livestock_category_type_w,
                livestock_production_type=input.livestock_production_type_w,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_leaching_systems_wo = (
            LivestockManureEF.objects.filter(
                emission_type__name=EmissionTypes.N2O_LEACHING,
                livestock_category_type=input.livestock_category_type_wo,
                livestock_production_type=input.livestock_production_type_wo,
                climate=project.climate,
                moisture=project.moisture,
            )
            .exclude(manure_management_type__name=ManureManagementTypes.PRP)
            .order_by("manure_management_type__name")
        )

        ef_n2o_leaching_systems_start = [s.value for s in ef_n2o_leaching_systems_start]
        ef_n2o_leaching_systems_w = [s.value for s in ef_n2o_leaching_systems_w]
        ef_n2o_leaching_systems_wo = [s.value for s in ef_n2o_leaching_systems_wo]

        ner_start = LivestockNER.objects.get(
            livestock_category_type=input.livestock_category_type_start,
            livestock_production_type=input.livestock_production_type_start,
            ipcc_region=project.country.ipcc_region,
        )

        ner_w = LivestockNER.objects.get(
            livestock_category_type=input.livestock_category_type_w,
            livestock_production_type=input.livestock_production_type_w,
            ipcc_region=project.country.ipcc_region,
        )

        ner_wo = LivestockNER.objects.get(
            livestock_category_type=input.livestock_category_type_wo,
            livestock_production_type=input.livestock_production_type_wo,
            ipcc_region=project.country.ipcc_region,
        )

        n2o_ef_t2_start = None
        n2o_volatilization_ef_t2_start = None
        n2o_leaching_ef_t2_start = None
        ch4_ef_t2_start = None
        if input.manure_management_type_t2_start is not None:
            n2o_ef_t2_start = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.N2O,
                livestock_category_type=input.livestock_category_type_start,
                livestock_production_type=input.livestock_production_type_start,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_start,
            )
            if n2o_ef_t2_start:
                n2o_ef_t2_start = n2o_ef_t2_start.value

            n2o_volatilization_ef_t2_start = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=input.livestock_category_type_start,
                livestock_production_type=input.livestock_production_type_start,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_start,
            )
            if n2o_volatilization_ef_t2_start:
                n2o_volatilization_ef_t2_start = n2o_volatilization_ef_t2_start.value

            n2o_leaching_ef_t2_start = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.N2O_LEACHING,
                livestock_category_type=input.livestock_category_type_start,
                livestock_production_type=input.livestock_production_type_start,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_start,
            )
            if n2o_leaching_ef_t2_start:
                n2o_leaching_ef_t2_start = n2o_leaching_ef_t2_start.value

            ch4_ef_t2_start = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.CH4,
                livestock_category_type=input.livestock_category_type_start,
                livestock_production_type=input.livestock_production_type_start,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_start,
            )
            if ch4_ef_t2_start:
                ch4_ef_t2_start = ch4_ef_t2_start.value

        n2o_ef_t2_w = None
        n2o_volatilization_ef_t2_w = None
        n2o_leaching_ef_t2_w = None
        ch4_ef_t2_w = None
        if input.manure_management_type_t2_w is not None:
            n2o_ef_t2_w = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.N2O,
                livestock_category_type=input.livestock_category_type_w,
                livestock_production_type=input.livestock_production_type_w,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_w,
            )
            if n2o_ef_t2_w:
                n2o_ef_t2_w = n2o_ef_t2_w.value

            n2o_volatilization_ef_t2_w = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=input.livestock_category_type_w,
                livestock_production_type=input.livestock_production_type_w,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_w,
            )
            if n2o_volatilization_ef_t2_w:
                n2o_volatilization_ef_t2_w = n2o_volatilization_ef_t2_w.value

            n2o_leaching_ef_t2_w = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.N2O_LEACHING,
                livestock_category_type=input.livestock_category_type_w,
                livestock_production_type=input.livestock_production_type_w,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_w,
            )
            if n2o_leaching_ef_t2_w:
                n2o_leaching_ef_t2_w = n2o_leaching_ef_t2_w.value

            ch4_ef_t2_w = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.CH4,
                livestock_category_type=input.livestock_category_type_w,
                livestock_production_type=input.livestock_production_type_w,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_w,
            )
            if ch4_ef_t2_w:
                ch4_ef_t2_w = ch4_ef_t2_w.value

        n2o_ef_t2_wo = None
        n2o_volatilization_ef_t2_wo = None
        n2o_leaching_ef_t2_wo = None
        ch4_ef_t2_wo = None
        if input.manure_management_type_t2_wo is not None:
            n2o_ef_t2_wo = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.N2O,
                livestock_category_type=input.livestock_category_type_wo,
                livestock_production_type=input.livestock_production_type_wo,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_wo,
            )
            if n2o_ef_t2_wo:
                n2o_ef_t2_wo = n2o_ef_t2_wo.value

            n2o_volatilization_ef_t2_wo = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.N2O_VOLATILIZATION,
                livestock_category_type=input.livestock_category_type_wo,
                livestock_production_type=input.livestock_production_type_wo,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_wo,
            )
            if n2o_volatilization_ef_t2_wo:
                n2o_volatilization_ef_t2_wo = n2o_volatilization_ef_t2_wo.value

            n2o_leaching_ef_t2_wo = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.N2O_LEACHING,
                livestock_category_type=input.livestock_category_type_wo,
                livestock_production_type=input.livestock_production_type_wo,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_wo,
            )
            if n2o_leaching_ef_t2_wo:
                n2o_leaching_ef_t2_wo = n2o_leaching_ef_t2_wo.value

            ch4_ef_t2_wo = LivestockManureEF.objects.get(
                emission_type__name=EmissionTypes.CH4,
                livestock_category_type=input.livestock_category_type_wo,
                livestock_production_type=input.livestock_production_type_wo,
                climate=project.climate,
                moisture=project.moisture,
                manure_management_type=input.manure_management_type_t2_wo,
            )
            if ch4_ef_t2_wo:
                ch4_ef_t2_wo = ch4_ef_t2_wo.value

        LEACHING_MULTI = LivestockParameter.objects.get(name="LEACHING_MULTIPLIER").value

        volatilization_multi = ManureManagementVolatilizationMultiplier.objects.get(moisture=project.moisture,)

        i_w = [
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate.name,
            project.gw_potential.ch4,
            input.heads_number_start,
            input.heads_number_w,
            ch4_enteric_start.value,
            ch4_enteric_w.value,
            input.enteric_fermentation_start_t2,
            input.enteric_fermentation_w_t2,
            ef_ch4_prp_start.value,
            ef_ch4_prp_w.value,
            animal_waste_prp_start.value,
            animal_waste_prp_w.value,
            input.prp_percentage_start_t2,
            input.prp_percentage_w_t2,
            ef_ch4_system_values_start,
            ef_ch4_system_values_w,
            input.prp_ch4_start_t2,
            input.prp_ch4_w_t2,
            ch4_ef_t2_start,  ###
            ch4_ef_t2_w,
            input.emission_factor_ch4_t2_start,
            input.emission_factor_ch4_t2_w,
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
            input.prp_n2o_start_t2,
            input.prp_n2o_w_t2,
            n2o_ef_t2_start,  ###
            n2o_ef_t2_w,
            input.emission_factor_n2o_t2_start,
            input.emission_factor_n2o_t2_w,
            ner_start.value,
            ner_w.value,
            prp_n2o_volatilization_ef_start.value,
            prp_n2o_volatilization_ef_w.value,
            ef_n2o_volatilization_systems_start,
            ef_n2o_volatilization_systems_w,
            input.prp_n2o_start_t2,  # TODO: Maybe add specific t2 for volatilization
            input.prp_n2o_w_t2,
            n2o_volatilization_ef_t2_start,  ###
            n2o_volatilization_ef_t2_w,
            input.emission_factor_n2o_t2_start,
            input.emission_factor_n2o_t2_w,
            prp_n2o_leaching_ef_start.value,
            prp_n2o_leaching_ef_w.value,
            ef_n2o_leaching_systems_start,
            ef_n2o_leaching_systems_w,
            input.prp_n2o_start_t2,  # TODO: Maybe add specific t2 for leaching
            input.prp_n2o_w_t2,
            n2o_leaching_ef_t2_start,  ###
            n2o_leaching_ef_t2_w,
            input.emission_factor_n2o_t2_start,
            input.emission_factor_n2o_t2_w,
            project.gw_potential.n2o,
            volatilization_multi.value,
            LEACHING_MULTI,
        ]

        i_wo = [
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate.name,
            project.gw_potential.ch4,
            input.heads_number_start,
            input.heads_number_wo,
            ch4_enteric_start.value,
            ch4_enteric_wo.value,
            input.enteric_fermentation_start_t2,
            input.enteric_fermentation_wo_t2,
            ef_ch4_prp_start.value,
            ef_ch4_prp_wo.value,
            animal_waste_prp_start.value,
            animal_waste_prp_wo.value,
            input.prp_percentage_start_t2,
            input.prp_percentage_wo_t2,
            ef_ch4_system_values_start,
            ef_ch4_system_values_wo,
            input.prp_ch4_start_t2,
            input.prp_ch4_wo_t2,
            ch4_ef_t2_start,  ###
            ch4_ef_t2_wo,
            input.emission_factor_ch4_t2_start,
            input.emission_factor_ch4_t2_wo,
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
            input.prp_n2o_start_t2,
            input.prp_n2o_wo_t2,
            n2o_ef_t2_start,  ###
            n2o_ef_t2_wo,
            input.emission_factor_n2o_t2_start,
            input.emission_factor_n2o_t2_wo,
            ner_start.value,
            ner_wo.value,
            prp_n2o_volatilization_ef_start.value,
            prp_n2o_volatilization_ef_wo.value,
            ef_n2o_volatilization_systems_start,
            ef_n2o_volatilization_systems_wo,
            input.prp_n2o_start_t2,  # TODO: Maybe add specific t2 for volatilization
            input.prp_n2o_wo_t2,
            n2o_volatilization_ef_t2_start,  ###
            n2o_volatilization_ef_t2_wo,
            input.emission_factor_n2o_t2_start,
            input.emission_factor_n2o_t2_wo,
            prp_n2o_leaching_ef_start.value,
            prp_n2o_leaching_ef_wo.value,
            ef_n2o_leaching_systems_start,
            ef_n2o_leaching_systems_wo,
            input.prp_n2o_start_t2,  # TODO: Maybe add specific t2 for leaching
            input.prp_n2o_wo_t2,
            n2o_leaching_ef_t2_start,  ###
            n2o_leaching_ef_t2_wo,
            input.emission_factor_n2o_t2_start,
            input.emission_factor_n2o_t2_wo,
            project.gw_potential.n2o,
            volatilization_multi.value,
            LEACHING_MULTI,
        ]

        results_w = MathLivestock(*i_w).calculate_emissions()
        results_wo = MathLivestock(*i_wo).calculate_emissions()

        return Result(results_w, results_wo, results_w - results_wo)

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

        ef = IrrigationSystemData.objects.get(
            irrigation_system_type=_input.irrigation_system_type
        )

        inputs_w = [
            ef.value,
            _input.ef_t2_start,
            _input.ha_start,
            _input.ha_w,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            _input.activity.change_rate.name,
        ]

        results_w = NewIrrigation(*inputs_w).calculate_emissions()

        inputs_wo = [
            ef.value,
            _input.ef_t2_wo,
            _input.ha_start,
            _input.ha_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            _input.activity.change_rate.name,
        ]

        results_wo = NewIrrigation(*inputs_wo).calculate_emissions()

        return Result(results_w, results_wo, results_w - results_wo)

class IrrigationPhaseCalculator(BaseCalculator):

    def calculate(self) -> list[Result]:

        input: IrrigationPhase = self.data
        project: Project = input.activity.project

        ef = IrrigationPhaseData.objects.get(fuel_type=input.fuel_type)
        energy_db = EnergyDefaultEmissionFactor.objects.get(fuel_type=input.fuel_type)
        pressure = IrrigationPressureRequirement.objects.get(irrigation_system_type=input.irrigation_system_type)

        erh_electricity = IrrigationParameter.objects.get(name="ERH_ELECTRICITY").value if input.fuel_type.name == "Electricity" else None
        transportation_loss = IrrigationParameter.objects.get(name="TRANSPORTATION_LOSS")
        pumping_efficiency = IrrigationParameter.objects.get(name="PUMPING_EFFICIENCY")

        inputs_from_start = [
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
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            transportation_loss.value if input.fuel_type.name == "Electricity" else 0,
            input.gross_irrigation_water_start,
        ]

        results_start = OperationPhaseIrrigation(*inputs_from_start).calculate_emissions()

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
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            transportation_loss.value if input.fuel_type.name == "Electricity" else 0,
            input.gross_irrigation_water_w,
        ]

        results_w = OperationPhaseIrrigation(*inputs_w).calculate_emissions()

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
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            transportation_loss.value if input.fuel_type.name == "Electricity" else 0,
            input.gross_irrigation_water_wo,
        ]

        results_wo = OperationPhaseIrrigation(*inputs_wo).calculate_emissions()

        return Result(results_w+results_start, results_wo+results_start, results_w - results_wo)

class CoastalWetlandCalculator(BaseCalculator):
    """
    TODO: Redo
    Calculates the emissions of the coastal wetland
    """

    def calculate(self) -> Result:
        """
        Calculates the emissions of the coastal wetland
        """

        input: CoastalWetland = self.data
        project: Project = input.activity.project

        cm = {
            "climate": project.climate,
            "moisture": project.moisture,
        }

        soil_type_name = input.soil_type_t2.name if input.soil_type_t2 else "Mineral Soil"

        agb = CoastalAGB.objects.get(**cm, vegetation_type=input.vegetation_type)
        bgb = CoastalBGB.objects.get(**cm, vegetation_type=input.vegetation_type)
        litter = CoastalLitter.objects.get(**cm, vegetation_type=input.vegetation_type)
        dw = CoastalDeadwood.objects.get(**cm, vegetation_type=input.vegetation_type)
        soil_1m = DefaultSoilCarbonStock1Meter.objects.get(**cm, vegetation_type=input.vegetation_type, soil_type__name=soil_type_name)
        ef_drainage = DrainageEmissionFactor.objects.get(**cm, vegetation_type=input.vegetation_type)
        pc_c_lost_excavation = CoastalWetlandParameter.objects.get(name="PERCENTAGE_C_LOST_EXCAVATION")

        rewetting_c = RewettingCarbonFactor.objects.get(**cm, vegetation_type=input.vegetation_type)
        rewetting_ch4 = RewettingMethaneFactor.objects.get(**cm, vegetation_type=input.vegetation_type)

        inputs_w = [
            input.ha_start,
            input.area_under_drainage_start,
            input.area_under_drainage_w,
            input.activity.change_rate.name,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            agb.value,
            bgb.value,
            litter.value,
            dw.value,
            soil_1m.value,
            ef_drainage.value,
            input.agb_t2_w,
            input.bgb_t2_w,
            input.litter_t2_w,
            input.deadwood_t2_w,
            input.soc_t2_w,
            input.drainage_ef_t2_w,
            input.drained_area_excavated_start,
            input.drained_area_excavated_w,
            pc_c_lost_excavation.value,
            input.pc_c_lost_after_excavation_t2_w,
            rewetting_c.value,
            rewetting_ch4.value,
            input.co2_rewetting_t2_start,
            input.ch4_rewetting_t2_w,
            input.avg_salinity_t2.value,
            project.gw_potential.ch4,
        ]

        inputs_wo = [
            input.ha_start,
            input.area_under_drainage_start,
            input.area_under_drainage_wo,
            input.activity.change_rate.name,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            agb.value,
            bgb.value,
            litter.value,
            dw.value,
            soil_1m.value,
            ef_drainage.value,
            input.agb_t2_wo,
            input.bgb_t2_wo,
            input.litter_t2_wo,
            input.deadwood_t2_wo,
            input.soc_t2_wo,
            input.drainage_ef_t2_wo,
            input.drained_area_excavated_start,
            input.drained_area_excavated_wo,
            pc_c_lost_excavation.value,
            input.pc_c_lost_after_excavation_t2_wo,
            rewetting_c.value,
            rewetting_ch4.value,
            input.co2_rewetting_t2_wo,
            input.ch4_rewetting_t2_wo,
            input.avg_salinity_t2.value,
            project.gw_potential.ch4,
        ]

        math_w = MathCoastalWetland(*inputs_w)
        math_wo = MathCoastalWetland(*inputs_wo)

        math_w.calculate_emissions()
        math_wo.calculate_emissions()

        results_w = math_w.total_emissions
        results_wo = math_wo.total_emissions

        return Result(results_w, results_wo, results_w - results_wo)

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
        methane_emission_factor = OtherConstructedWaterbodiesEmissionFactor.objects.get(
            climate=project.climate,
            moisture=project.moisture,
            waterbody_type=module.waterbody_type,
        )

        trophic_state_start = TrophicStateFactor.objects.get(trophic_type=module.trophic_type_start)
        trophic_state_w = TrophicStateFactor.objects.get(trophic_type=module.trophic_type_w)
        trophic_state_wo = TrophicStateFactor.objects.get(trophic_type=module.trophic_type_wo)


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
            project.capitalization_duration_yrs,
            project.implementation_duration_yrs,
            module.activity.change_rate.name,
            module.mean_annual_t2_start,
            0,
        ]

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
            project.capitalization_duration_yrs,
            project.implementation_duration_yrs,
            module.activity.change_rate.name,
            module.mean_annual_t2_start,
            module.mean_annual_t2_w,
        ]

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
            project.capitalization_duration_yrs,
            project.implementation_duration_yrs,
            module.activity.change_rate.name,
            module.mean_annual_t2_start,
            module.mean_annual_t2_wo,
        ]

        math_start = MathWaterbodies(*inputs_start)
        math_w = MathWaterbodies(*inputs_w)
        math_wo = MathWaterbodies(*inputs_wo)

        math_start.calculate_emissions()
        math_w.calculate_emissions()
        math_wo.calculate_emissions()

        results_start = math_start.total_emissions
        results_w = math_w.total_emissions
        results_wo = math_wo.total_emissions

        return Result(results_w+results_start, results_wo+results_start, results_w - results_wo)



##### TO BE REMOVED #####

class ExtractionCalculator(BaseCalculator):
    """
    TODO: Redo or remove
    Calculator for extraction modules.
    """

    def calculate(self) -> list[Result]:
        """
        Calculates the results for an extraction module.
        """

        # Extraction
        project = self.data.activity.project
        climate = project.climate
        moisture = project.moisture
        vegetation_type = self.data.vegetation_type

        criteria = {
            "climate": climate,
            "moisture": moisture,
            "vegetation_type": vegetation_type,
        }

        agb = CoastalAGB.objects.get(**criteria)
        bgb = CoastalBGB.objects.get(**criteria)
        litter = CoastalLitter.objects.get(**criteria)
        dw = CoastalDeadwood.objects.get(**criteria)

        soil_1m = None

        if vegetation_type.name == MANGROVES:
            atwood = Atwood.objects.get(country=project.country)
            soil_1m = atwood.mg_c_ha
        else:
            try:
                cs_criteria = {
                    "climate": climate,
                    "moisture": moisture,
                    "vegetation_type": vegetation_type,
                    "soil_type": self.data.extraction_soil_type_t2,
                }
                soil_1m = DefaultSoilCarbonStock.objects.get(**cs_criteria).value
            except DefaultSoilCarbonStock.DoesNotExist:
                # TODO: Insert default values for other soil_types at 0 in db
                soil_1m = 0

        extraction_inputs = [
            self.data.ha_start,
            self.data.ha_w_excavated_percentage,
            self.data.ha_wo_excavated_percentage,
            agb.value,
            bgb.value,
            litter.value,
            dw.value,
            soil_1m,
            0.96,  # TODO: Add to db
            self.data.extraction_ag_t2,
            self.data.extraction_bg_t2,
            self.data.extraction_litter_t2,
            self.data.extraction_deadwood_t2,
            self.data.extraction_soil_t2,
            self.data.c_after_excavation_t2,
        ]

        extraction_result = Result(
            *coastal_wetlands.extraction_and_excavation_w_wo(*extraction_inputs)
        )

        # Drainage
        if vegetation_type.name == MANGROVES:
            atwood = Atwood.objects.get(country=project.country)
            soil_1m = atwood.mg_c_ha
        else:
            try:
                cs_criteria = {
                    "climate": climate,
                    "moisture": moisture,
                    "vegetation_type": vegetation_type,
                    "soil_type": self.data.drainage_soil_type_t2,
                }
                soil_1m = DefaultSoilCarbonStock.objects.get(**cs_criteria).value
            except DefaultSoilCarbonStock.DoesNotExist:
                # TODO: Insert default values for other soil_types at 0 in db
                soil_1m = 0

        drainage_ef = DrainageEmissionFactor.objects.get(
            climate=climate, moisture=moisture, vegetation_type=vegetation_type
        )

        drainage_inputs = [
            self.data.ha_start,
            self.data.drainage_percentage_start,
            self.data.drainage_percentage_w,
            self.data.drainage_percentage_w_rate.name,
            self.data.drainage_percentage_w_rate.value,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            agb.value,
            bgb.value,
            litter.value,
            dw.value,
            soil_1m,
            drainage_ef.value,
            self.data.drainage_ag_t2,
            self.data.drainage_bg_t2,
            self.data.drainage_litter_t2,
            self.data.drainage_deadwood_t2,
            self.data.drainage_soil_t2,
            self.data.ef_drainage_t2,
            self.data.drainage_percentage_wo,
            self.data.drainage_percentage_wo_rate.name,
            self.data.drainage_percentage_wo_rate.value,
        ]

        drainage_result = Result(*coastal_wetlands.drainage_w_wo(*drainage_inputs))

        return [extraction_result, drainage_result]

class CoastalWaterbodyCalculator(BaseCalculator):
    """
    TODO: Wait math model for redo or remove
    Calculator for coastal waterbody modules.
    """

    def calculate(self) -> Result:
        project = self.data.activity.project
        methane_emission_factor = OtherConstructedWaterbodiesEmissionFactor.objects.get(
            climate=project.climate,
            moisture=project.moisture,
            waterbody_type=self.data.waterbody_type,
        )

        inputs = [
            self.data.ha_start,
            self.data.ha_w,
            TROPHIC_STATE,
            methane_emission_factor.value,
            self.data.trophic_alpha_t2,
            self.data.ch4_start_t2,
            self.data.ch4_w_t2,
            project.gw_potential.ch4,
            project.capitalization_duration_yrs,
            project.implementation_duration_yrs,
            self.data.ha_w_rate.value,
            self.data.ha_wo,
            self.data.ch4_wo_t2,
            self.data.ha_wo_rate.value,
            self.data.trophic_mean_annual_t2,
        ]

        return Result(*coastal_wetlands.coastal_waterbodies_w_wo(*inputs))
    
class RewettingCalculator(BaseCalculator):
    """
    TODO: Redo or remove
    Calculator for rewetting modules.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Rewetting module.
        """

        project = self.data.activity.project
        climate = project.climate
        moisture = project.moisture
        vegetation_type = self.data.vegetation_type

        criteria = {
            "climate": climate,
            "moisture": moisture,
            "vegetation_type": vegetation_type,
        }

        agb = CoastalAGB.objects.get(**criteria)
        bgb = CoastalBGB.objects.get(**criteria)
        litter = CoastalLitter.objects.get(**criteria)
        dw = CoastalDeadwood.objects.get(**criteria)
        carbon = RewettingCarbonFactor.objects.get(**criteria)
        methane = RewettingMethaneFactor.objects.get(**criteria)

        inputs = [
            agb.value,
            bgb.value,
            litter.value,
            dw.value,
            carbon.value,
            methane.value,
            self.data.ag_t2,
            self.data.bg_t2,
            self.data.litter_t2,
            self.data.deadwood_t2,
            self.data.ef_co2_t2,
            self.data.ef_ch4_t2,
            self.data.avg_salinity_t2.value,
            0,  # area_start does not exist for rewetting
            self.data.ha_w,
            self.data.ha_w_rate.name,
            self.data.ha_w_rate.value,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            project.gw_potential.ch4,
            self.data.ha_wo,
            self.data.ha_wo_rate.name,
            self.data.ha_wo_rate.value,
        ]

        return Result(*coastal_wetlands.rewetting_w_wo(*inputs))

class OrganicSoilCalculator(BaseCalculator):

    def calculate(self) -> Result:
        input: OrganicSoil = self.data
        project: Project = input.activity.project

        relative, relation = get_assessment_or_parent(input)
        
        if not relative:
            raise ValueError("Organic Soil is missing a land use from a parent module")

        relative_class = relative.__class__.__name__

        cmt = {
            "climate": project.climate,
            "moisture": project.moisture,
            "module_type__name": relative_class,
        }
        
        ef_onsite_start = OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(
            **cmt,
            peat_type=input.peat_type_start,
            site_location_type__name="On-Site",
        )

        ef_onsite_w = OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(
            **cmt,
            peat_type=input.peat_type_w,
            site_location_type__name="On-Site",
        )

        ef_onsite_wo = OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(
            **cmt,
            peat_type=input.peat_type_wo,
            site_location_type__name="On-Site",
        )

        ef_offsite_start = OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(
            **cmt,
            peat_type=input.peat_type_start,
            site_location_type__name="Off-Site",
        )

        ef_offsite_w = OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(
            **cmt,
            peat_type=input.peat_type_w,
            site_location_type__name="Off-Site",
        )

        ef_offsite_wo = OrganicSoilDrainageEmissionFactor.objects.get_or_other_luc(
            **cmt,
            peat_type=input.peat_type_wo,
            site_location_type__name="Off-Site",
        )

        inputs_w = [
            input.is_fire_on_soil_w,
            input.soil_fire_periodicity_w,
            input.drainage_area_w,
        ]