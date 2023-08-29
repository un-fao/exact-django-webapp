from .models import (
    Deforestation,
    Afforestation,
    OtherLandUse,
    Project,
    Input,
    Building,
    Livestock,
    AnnualCropping,
    CropType,
    LivestockParameter,
    Electricity,
    Fuel,
    IrrigationSystem,
    IrrigationPhase,
    IrrigationParameter,
    SmallFisheryParameter,
    LargeFisheryParameter,
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
from math_model import inputs as math_inputs
from ipcc.models import *
from .utilities import *
from abc import ABC, abstractmethod
import sys
from math_model.no_time_dependency_final.livestock import Livestock as MathLivestock
from math_model.no_time_dependency_final.inputs import Inputs as MathInputs
from math_model.no_time_dependency_final.inputs import (
    FuelConsumption,
    SolidConsumption,
    ElectryicityConsumption,
    NewIrrigation,
    OperationPhaseIrrigation,
)

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
            calculator: BaseCalculator = getattr(
                sys.modules[__name__], calculator_name
            )(input)
            return calculator.calculate()
        except AttributeError as e:
            print(f"Calculator error: {e}")
            raise Exception(f"Module '{input.__class__.__name__}' not (yet) supported.")
        except Exception as ex:
            print(ex)
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
    Calculator for deforestation modules.
    """

    def calculate(self) -> Result:
        """
        Calculate emissions for a single Deforestation module.
        """

        project = self.data.activity.project
        climate = project.climate
        moisture = project.moisture
        continent = project.continent
        soil_type = project.soil_type
        land_use_type = self.data.land_use_type
        vegetation_type = self.data.vegetation_type

        mangroves_data = None
        defo_table = None

        # Get the IPCC data
        soc_ref = SoilOrganicCarbon.objects.get(
            climate=climate, moisture=moisture, soil_type=soil_type
        )
        total_biomass = TotalBiomassAfterDefo.objects.get(
            climate=climate,
            moisture=moisture,
            continent=continent,
            land_use_type=land_use_type,
        )

        # NOTE: Maybe merge the mangroves and deforestation IPCC tables into one table?
        if self.data.vegetation_type != MANGROVES:
            defo_table = LitterDeadwoodCarbonStock.objects.get(
                vegetation_type=vegetation_type
            )
            ag_biomass = AboveGroundBiomass.objects.get(
                continent=continent, vegetation_type=vegetation_type
            )
            bg_biomass = BelowGroundBiomass.objects.filter(
                continent=continent, vegetation_type=vegetation_type
            )

            # Gets the row matching the lowest threshold value above the ag_biomass threshold limit
            # NOTE: If a new, highest threshold is added to the db, this can return the wrong value unless the old highest threshold is set to a proper value
            # NOTE: This method could be added to the previous one, resulting in a single query but higher cognitive complexity
            # NOTE: For more than ~50 inputs, 25% improvement in performance by merging with the query above.
            bg_biomass = (
                bg_biomass.filter(
                    Q(threshold__gt=ag_biomass.value) | Q(threshold__isnull=True)
                )
                .order_by("threshold")
                .first()
            )
        else:
            mangroves_data = DataOnMangroves.objects.get(continent=continent)

        combustion_factor = CombustionFactorValues.objects.get(
            vegetation_type=vegetation_type
        )
        moisture_factor = DefaultEmissionFactor.objects.filter(moisture=moisture)
        moisture_factor = moisture_factor.filter(
            Q(input__name__icontains="Other N Inputs")
            | Q(input__name__icontains="All N Inputs")
        ).first()
        flu = LandUseCarbonStockExchangeFactor.objects.get(
            climate=climate, moisture=moisture, land_use_type=land_use_type
        )

        inputs = [
            self.data.ha_start,
            self.data.ha_w,
            self.data.ha_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            self.data.ha_w_rate.name,
            self.data.ha_w_rate.value,
            total_biomass.value if total_biomass.value is not None else 0,
            self.data.final_rcs_biomass_t2,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            self.data.is_fire_used,
            combustion_factor.n2o,
            combustion_factor.ch4,
            combustion_factor.value,
            moisture_factor.value,
            defo_table.litter if mangroves_data is None else mangroves_data.litter,
            self.data.rcs_litter_t2,
            defo_table.dw if mangroves_data is None else mangroves_data.dw,
            self.data.rcs_deadwood_t2,
            self.data.hwp,
            MANGROVE_FACTOR if mangroves_data is not None else NON_MANGROVE_FACTOR,
            self.data.rcs_bg_t2,
            self.data.rcs_ag_t2,
            flu.value,
            mangroves_data.agb_c if mangroves_data is not None else ag_biomass.value,
            mangroves_data.bgb if mangroves_data is not None else bg_biomass.value,
            CN_RATIO_GRASSLAND,
            self.data.final_rcs_soil_c_t2,  # soil after defo t2
            soc_ref.value if soc_ref.value is not None else 0,
            self.data.rcs_soil_c_t2,  # soil t2
        ]

        results = defo.GHG_emissions(*inputs)

        return Result(*results)


class ExtractionCalculator(BaseCalculator):
    """
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

        agb = CoastalAboveGroundBiomass.objects.get(**criteria)
        bgb = CoastalBGAGRatio.objects.get(**criteria)
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
    Calculator for coastal waterbody modules.
    """

    def calculate(self) -> list[Result]:
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

        agb = CoastalAboveGroundBiomass.objects.get(**criteria)
        bgb = CoastalBGAGRatio.objects.get(**criteria)
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


class AfforestationCalculator(BaseCalculator):
    """
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
        combustion_factor = AfforestationCombustionFactorValues.objects.get(
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

        c_n_ratio = (
            CN_RATIO_GRASSLAND
            if initial_land_use.name == "Grassland"
            else CN_RATIO_FOREST
        )

        moisture_factor = DefaultEmissionFactor.objects.get(
            moisture=moisture, input__name__icontains="Other N Inputs"
        )
        combustion_factor = AfforestationCombustionFactorValues.objects.get(
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

        project: Project = self.data.activity.project
        climate = project.climate
        moisture = project.moisture
        crop_type_start = input.crop_type_start
        crop_type_w = input.crop_type_w
        crop_type_wo = input.crop_type_wo
        minor_crop_type_start = input.minor_crop_type_start
        minor_crop_type_w = input.minor_crop_type_w
        minor_crop_type_wo = input.minor_crop_type_wo

        relative, relation = get_assessment_or_parent(self.data)
        is_parent = relation == "parent"

        burning_emission_factor = BurningEmissionFactor.objects.get(
            category__name="Agricultural residues"
        )

        fires_combustion_factor_start = FiresCombustionFactor.objects.get(
            crop_type=crop_type_start
        )
        fires_combustion_factor_w = FiresCombustionFactor.objects.get(
            crop_type=crop_type_w
        )
        fires_combustion_factor_wo = FiresCombustionFactor.objects.get(
            crop_type=crop_type_wo
        )

        n_estimation_factor_start = (
            CropNitrousEstimationDefaultFactor.objects.get_or_grains(
                crop_type=crop_type_start
            )
        )
        n_estimation_factor_w = (
            CropNitrousEstimationDefaultFactor.objects.get_or_grains(
                crop_type=crop_type_w
            )
        )
        n_estimation_factor_wo = (
            CropNitrousEstimationDefaultFactor.objects.get_or_grains(
                crop_type=crop_type_wo
            )
        )

        # Minor crop
        try:
            minor_combustion_factor_start = FiresCombustionFactor.objects.get(
                crop_type=crop_type_start
            )
            minor_combustion_factor_w = FiresCombustionFactor.objects.get(
                crop_type=crop_type_w
            )
            minor_combustion_factor_wo = FiresCombustionFactor.objects.get(
                crop_type=crop_type_wo
            )

            minor_burning_emission_factor = BurningEmissionFactor.objects.get(
                category__name="Agricultural residues"
            )

            minor_n_estimation_factor_start = (
                CropNitrousEstimationDefaultFactor.objects.get_or_grains(
                    crop_type=minor_crop_type_start
                )
            )
            minor_n_estimation_factor_w = (
                CropNitrousEstimationDefaultFactor.objects.get_or_grains(
                    crop_type=minor_crop_type_w
                )
            )
            minor_n_estimation_factor_wo = (
                CropNitrousEstimationDefaultFactor.objects.get_or_grains(
                    crop_type=minor_crop_type_wo
                )
            )
        except:
            # If only one of the above operations fails, all minor variables must be set to None
            minor_burning_emission_factor = None

            minor_combustion_factor_start = None
            minor_combustion_factor_w = None
            minor_combustion_factor_wo = None

            minor_n_estimation_factor_start = None
            minor_n_estimation_factor_w = None
            minor_n_estimation_factor_wo = None

        emission_factors_start = DefaultEmissionFactor.objects.get(
            moisture=moisture, organic_input_type=input.organic_input_type_start
        )
        emission_factors_w = DefaultEmissionFactor.objects.get(
            moisture=moisture, organic_input_type=input.organic_input_type_w
        )
        emission_factors_wo = DefaultEmissionFactor.objects.get(
            moisture=moisture, organic_input_type=input.organic_input_type_wo
        )

        flu = CroplandFLU.objects.get(
            climate=climate,
            moisture=moisture,
            crop_type__name="Long-Term Cultivated",
        )

        fi_start = CroplandFI.objects.get(
            climate=climate,
            moisture=moisture,
            organic_input_type=input.organic_input_type_start,
        )
        fi_w = CroplandFI.objects.get(
            climate=climate,
            moisture=moisture,
            organic_input_type=input.organic_input_type_w,
        )
        fi_wo = CroplandFI.objects.get(
            climate=climate,
            moisture=moisture,
            organic_input_type=input.organic_input_type_wo,
        )

        fmg_start = CroplandFMG.objects.get(
            climate=climate,
            moisture=moisture,
            tillage_management_type=input.tillage_management_type_start,
        )
        fmg_w = CroplandFMG.objects.get(
            climate=climate,
            moisture=moisture,
            tillage_management_type=input.tillage_management_type_w,
        )
        fmg_wo = CroplandFMG.objects.get(
            climate=climate,
            moisture=moisture,
            tillage_management_type=input.tillage_management_type_wo,
        )

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

        ha_data_start = [input.ha_start, input.ha_start]
        ha_data_w = [input.ha_start, input.ha_w]
        ha_data_wo = [input.ha_start, input.ha_wo]

        # NOTE: Is this still needed?
        # if is_parent:
        #     if relative.__class__.__name__ == Deforestation.__name__:
        #         ha_data_start = [0, relative.ha_w]
        #         ha_data_w = [0, relative.ha_w]
        #         ha_data_wo = [0, relative.ha_w]
        #     elif relative.__class__.__name__ == Afforestation.__name__:
        #         ha_data_start = [relative.ha_w, relative.ha_w]
        #         ha_data_w = [relative.ha_w, relative.ha_w]
        #         ha_data_wo = [relative.ha_w, relative.ha_w]

        inputs_start = [
            *ha_data_start,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.ha_w_rate.name,  # NOTE: This will be handled on activity-level
            input.ha_w_rate.value,
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
            input.ha_w_rate.name,  # NOTE: This will be handled on activity-level
            input.ha_w_rate.value,
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
            input.ha_wo_rate.name,  # NOTE: This will be handled on activity-level
            input.ha_wo_rate.value,
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

        emissions_start = AnnualCropland(*inputs_start).calculate_emissions()
        emissions_w = AnnualCropland(*inputs_w).calculate_emissions()
        emissions_wo = AnnualCropland(*inputs_wo).calculate_emissions()

        res_w = emissions_w - emissions_start
        res_wo = emissions_wo - emissions_start

        return Result(res_w, res_wo, res_w - res_wo)


class PerennialCroppingCalculator(BaseCalculator):
    """
    Calculator for perennial cropping.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single PerennialCropping module.
        """

        project = self.data.activity.project
        climate = project.climate
        moisture = project.moisture
        continent = project.continent
        crop_type = self.data.crop_type
        parent, _ = get_assessment_or_parent(self.data)

        burning_emission_factor = BurningEmissionFactor.objects.get(
            category__name="Savanna and grassland"
        )

        # TODO: Replace 'other' with all the other land_use_types in db
        fires_combustion_factor = FiresCombustionFactor.objects.get_or_other(
            crop_type=crop_type
        )
        ag_default = PerennialAGB.objects.get_or_default(
            climate=climate,
            moisture=moisture,
            continent=continent,
            land_use_type=crop_type,
        )
        agb_max_c = PerennialMaxAGB.objects.get(
            climate=climate, land_use_type=crop_type
        )
        bg_default = PerennialBGB.objects.get_or_default(
            climate=climate,
            moisture=moisture,
            continent=continent,
            land_use_type=crop_type,
        )

        if parent:
            # TODO: initial_land_use and final_land_use change based on what's initial and whats final. Differentiate in LUC_From | LUC_To
            # NOTE: Maybe not? It's possible that the correct one is always final_land_use_type. Ask EX-ACT Team
            flu = AfforestationFLU.objects.get(
                climate=climate,
                moisture=moisture,
                land_use_type=parent.final_land_use_type,
            )
        else:
            flu = CroplandFLU.objects.get(
                climate=climate,
                moisture=moisture,
                crop_type__name="Perennial/Tree Crop",
            )

        fi = CroplandFI.objects.get(
            climate=climate,
            moisture=moisture,
            organic_input_type=self.data.organic_input_type,
        )
        fmg = CroplandFMG.objects.get(
            climate=climate,
            moisture=moisture,
            tillage_management_type=self.data.tillage_management_type,
        )

        inputs = [
            self.data.ha_start,
            self.data.ha_w,
            self.data.ha_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            self.data.ha_w_rate.name if parent else "D",
            self.data.ha_w_rate.value if parent else 0.5,
            self.data.ha_wo_rate.name if parent else "D",
            self.data.ha_wo_rate.value if parent else 0.5,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            self.data.is_biomass_burned,
            burning_emission_factor.n2o,
            burning_emission_factor.ch4,
            fires_combustion_factor.value,
            1,  # Default
            self.data.fire_periodicity_t2,
            self.data.residue_burned_t2,
            ag_default.value,
            self.data.ag_t2,
            agb_max_c.value,
            bg_default.value,
            self.data.bg_t2,
            project.soc_ref.value,
            self.data.soc_t2 if parent else 1,
            flu.value if parent else 1,
            self.data.flu_t2,
            fi.value,
            self.data.input_factor_t2,
            fmg.value,
            self.data.tillage_factor_t2,
        ]
        # BUG: Results for perennial crops do not add up. Wait for Lorenzo's unlocked Excel files
        return Result(*perennial_cropping.calculate_emissions(*inputs))


class GrasslandCalculator(BaseCalculator):
    """
    Calculator for grassland.
    # TODO: Implement class-based math model
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Grassland module.
        """

        project = self.data.activity.project
        ef = BurningEmissionFactor.objects.get(category__name="Savanna and grassland")
        agb = GrasslandAGB.objects.get(
            climate=project.climate, moisture=project.moisture
        )
        cf = 0.77
        proj_soc = project.soc_ref.value

        relative, relation = get_assessment_or_parent(self.data)
        is_parent = relation == "parent"

        # NOTE: Default values at start are for 'Non-Degraded' land
        soc_start = GrasslandStockExchangeFactor.objects.filter(
            grassland_management_type=self.data.grassland_management_type_start,
            climate=project.climate,
        ).first()

        soc_w = GrasslandStockExchangeFactor.objects.filter(
            grassland_management_type=self.data.grassland_management_type_w,
            climate=project.climate,
        ).first()

        soc_wo = GrasslandStockExchangeFactor.objects.filter(
            grassland_management_type=self.data.grassland_management_type_wo,
            climate=project.climate,
        ).first()

        soc_start = (
            proj_soc * soc_start.fmg * soc_start.flu * soc_start.fi
            if soc_start
            else project.soc_ref.value
        )
        soc_w = (
            proj_soc * soc_w.fmg * soc_w.flu * soc_w.fi
            if soc_w
            else project.soc_ref.value
        )
        soc_wo = (
            proj_soc * soc_wo.fmg * soc_wo.flu * soc_wo.fi
            if soc_wo
            else project.soc_ref.value
        )

        # TODO: A method must be defined that takes into account the nature of the land use change (defo, affo, oluc) and builds start,w,wo accordingly.

        ha_data = [self.data.ha_start, self.data.ha_w, self.data.ha_wo]
        # if is_parent:
        #     match relative.__class__.__name__:
        #         case Deforestation.__name__:
        #             ha_data = [0, relative.ha_w, (relative.ha_start - relative.ha_wo)]
        #         case Afforestation.__name__:
        #             ha_data = [relative.ha_w, relative.ha_w, relative.ha_wo]
        #         case OtherLandUse.__name__:
        #             ha_data = [relative.ha_start, relative.ha_w, 0]
        if is_parent:
            if relative.__class__.__name__ == Deforestation.__name__:
                ha_data = [0, relative.ha_w, (relative.ha_start - relative.ha_wo)]
            if relative.__class__.__name__ == Afforestation.__name__:
                ha_data = [relative.ha_w, relative.ha_w, relative.ha_wo]
            if relative.__class__.__name__ == OtherLandUse.__name__:
                ha_data = [relative.ha_start, relative.ha_w, 0]

        inputs = [
            *ha_data,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            relative.ha_wo_rate.name if is_parent else self.data.ha_w_rate.name,
            relative.ha_wo_rate.value if is_parent else self.data.ha_w_rate.value,
            relative.ha_w_rate.name if is_parent else self.data.ha_wo_rate.name,
            relative.ha_w_rate.value if is_parent else self.data.ha_wo_rate.value,
            project.gw_potential.n2o,
            project.gw_potential.ch4,
            self.data.years_w_fire_management,
            self.data.years_wo_fire_management,
            self.data.is_fire_used_w,
            self.data.is_fire_used_wo,
            ef.ch4,
            ef.n2o,
            agb.value,
            self.data.agb_t2,
            cf,
            self.data.combustion_factor_t2,
            soc_start,
            self.data.soil_carbon_start_t2,
            soc_w,
            soc_wo,
            self.data.soil_carbon_w_t2,
            self.data.soil_carbon_wo_t2,
        ]

        return Result(*grassland_management.calculate_total_emissions(*inputs))


class SmallFisheryCalculator(BaseCalculator):
    """
    Calculator for small fishery.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single SmallFishery module.
        """

        project = self.data.activity.project
        input = self.data

        ef_diesel_default_list = EnergyDefaultEmissionFactor.objects.filter(fuel_type__fuel_use_type__name__contains="Off-Road")

        # Average of all default emission factors for gasoil/diesel
        ef_diesel_default = sum([ef.t_co2_eq for ef in ef_diesel_default_list]) / len(ef_diesel_default_list)

        fui_default_start = SmallFisheryFUI.objects.get_value_or_average(fishery_type=self.data.fishery_type, gear_type=self.data.gear_type_start)
        fui_default_w = SmallFisheryFUI.objects.get_value_or_average(fishery_type=self.data.fishery_type, gear_type=self.data.gear_type_w)
        fui_default_wo = SmallFisheryFUI.objects.get_value_or_average(fishery_type=self.data.fishery_type, gear_type=self.data.gear_type_wo)

        lost_refrigerant_default = SmallFisheryParameter.object.get("lost_refrigerant_default").value
        tonnes_ice_default = SmallFisheryParameter.object.get("tonnes_ice_default").value
        kw_tonnes = SmallFisheryParameter.object.get("kw_tonnes").value

        electricity_emission = ElectricityEmission.objects.get(country=project.country, continent=project.continent)

        inputs = [
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            self.data.total_catch_yr_w_rate.value,
            self.data.total_catch_yr_wo_rate.value,
            self.data.total_catch_yr_start,
            self.data.total_catch_yr_w,
            self.data.total_catch_yr_wo,
            ef_diesel_default,
            self.data.energy_emission_factor_t2_start,
            self.data.energy_emission_factor_t2_w,
            self.data.energy_emission_factor_t2_wo,
            fui_default_start,
            fui_default_w,
            fui_default_wo,
            self.data.fui_start,
            self.data.fui_w,
            self.data.fui_wo,
            self.data.refrigerant_gwp,
            self.data.refrigerant_gwp_t2_start,
            self.data.refrigerant_gwp_t2_w,
            self.data.refrigerant_gwp_t2_wo,
            lost_refrigerant_default,
            self.data.refrigerant_lost_per_tonne_t2_start,
            self.data.refrigerant_lost_per_tonne_t2_w,
            self.data.refrigerant_lost_per_tonne_t2_wo,
            self.data.refrigerant_pc_start,
            self.data.refrigerant_pc_w,
            self.data.refrigerant_pc_wo,
            tonnes_ice_default,
            self.data.tonnes_of_ice_t2_start,
            self.data.tonnes_of_ice_t2_w,
            self.data.tonnes_of_ice_t2_wo,
            kw_tonnes,
            self.data.inshore_ice_production_kwh_per_tonne_t2_start,
            self.data.inshore_ice_production_kwh_per_tonne_t2_w,
            self.data.inshore_ice_production_kwh_per_tonne_t2_wo,
            electricity_emission.operating_margin,
            self.data.ice_preserved_catch_pc_start,
            self.data.ice_preserved_catch_pc_w,
            self.data.ice_preserved_catch_pc_wo,
        ]

        # print()
        # print("--- INPUTS ---")
        # print()
        # print(inputs)
        # print()
        # print("--- END INPUTS ---")
        # print()

        # print(f"Small fishery: {inputs}")

        return Result(*fisheries_and_aquaculture.total_emissions_small_or_large_fisheries(*inputs))
        


class LargeFisheryCalculator(BaseCalculator):
    """
    Calculator for large fishery.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single LargeFishery module.
        """

        project = self.data.activity.project
        ef_diesel_default_list = EnergyDefaultEmissionFactor.objects.filter(
            fuel_type__name__contains="Off-Road"
        )

        # Average of all default emission factors for gasoil/diesel
        ef_diesel_default = sum(
            [ef.t_co2_eq_m3 for ef in ef_diesel_default_list]
        ) / len(ef_diesel_default_list)

        fui_default_start = LargeFisheryFUI.objects.get_value_or_average(
            fish_type=self.data.fish_type,
            gear_type=self.data.gear_type_start,
        )
        fui_default_w = LargeFisheryFUI.objects.get_value_or_average(
            fish_type=self.data.fish_type,
            gear_type=self.data.gear_type_w,
        )
        fui_default_wo = LargeFisheryFUI.objects.get_value_or_average(
            fish_type=self.data.fish_type,
            gear_type=self.data.gear_type_wo,
        )

        # TODO: Maybe use a table (0.48734, .083 for SmallFishery)
        lost_refrigerant_default = LargeFisheryParameter.objects.get("lost_refrigerant_default").value

        # TODO: Maybe use a table (2.8 for both)
        tonnes_ice_default = LargeFisheryParameter.objects.get("tonnes_ice_default").value

        # TODO: Maybe use a table (60 for both)
        kw_tonnes = LargeFisheryParameter.objects.get("kw_tonnes").value

        electricity_country = (
            self.data.inshore_ice_production_country_t2
            if self.data.inshore_ice_production_country_t2
            else project.country
        )

        electricity_emission = ElectricityEmission.objects.get(
            country=electricity_country, continent=project.continent
        )

        inputs = [
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            self.data.total_catch_yr_w_rate.value,
            self.data.total_catch_yr_wo_rate.value,
            self.data.total_catch_yr_start,
            self.data.total_catch_yr_w,
            self.data.total_catch_yr_wo,
            ef_diesel_default,
            self.data.energy_emission_factor_t2_start,
            self.data.energy_emission_factor_t2_w,
            self.data.energy_emission_factor_t2_wo,
            fui_default_start,
            fui_default_w,
            fui_default_wo,
            self.data.fui_start,
            self.data.fui_w,
            self.data.fui_wo,
            self.data.refrigerant_gwp,
            self.data.refrigerant_gwp_t2_start,
            self.data.refrigerant_gwp_t2_w,
            self.data.refrigerant_gwp_t2_wo,
            lost_refrigerant_default,
            self.data.refrigerant_lost_per_tonne_t2_start,
            self.data.refrigerant_lost_per_tonne_t2_w,
            self.data.refrigerant_lost_per_tonne_t2_wo,
            self.data.refrigerant_pc_start,
            self.data.refrigerant_pc_w,
            self.data.refrigerant_pc_wo,
            tonnes_ice_default,
            self.data.tonnes_of_ice_t2_start,
            self.data.tonnes_of_ice_t2_w,
            self.data.tonnes_of_ice_t2_wo,
            kw_tonnes,
            self.data.inshore_ice_production_kwh_per_tonne_t2_start,
            self.data.inshore_ice_production_kwh_per_tonne_t2_w,
            self.data.inshore_ice_production_kwh_per_tonne_t2_wo,
            electricity_emission.operating_margin,
            self.data.ice_preserved_catch_pc_start,
            self.data.ice_preserved_catch_pc_w,
            self.data.ice_preserved_catch_pc_wo,
        ]

        # print()
        # print("--- INPUTS ---")
        # print()
        # print(inputs)
        # print()
        # print("--- END INPUTS ---")
        # print()

        # print(f"Large fishery: {inputs}")

        return Result(*fisheries_and_aquaculture.total_emissions_small_or_large_fisheries(*inputs))
        


class ForestCalculator(BaseCalculator):
    """
    Calculator for forest.
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
            data = DataOnMangroves.objects.get(
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

        cf: CombustionFactorValues = CombustionFactorValues.objects.get(
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

        project: Project = self.data.activity.project
        NITROUS_EF_DEFAULT = 0.00169
        FEED_EF_DEFAULT = 0

        inputs = [
            self.data.annual_production_start,
            self.data.annual_production_w,
            NITROUS_EF_DEFAULT,
            self.data.production_n2o_ef_t2,
            project.gw_potential.n2o,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            self.data.annual_production_w_rate.value,
            self.data.annual_production_wo_rate.value,
            self.data.annual_production_wo,
            self.data.annual_feed_quantity_start,
            self.data.annual_feed_quantity_w,
            FEED_EF_DEFAULT,
            self.data.feed_use_emissions_t2,
            self.data.annual_feed_quantity_wo,
        ]

        return Result(*fisheries_and_aquaculture.total_inland_coastal_aquaculture(*inputs))


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
            input.activity.change_rate_start.name,
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
            input.activity.change_rate_start.name,
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
                input.activity.change_rate_start.name,
                project.implementation_duration_yrs,
                project.capitalization_duration_yrs,
            ]

            input_wo = [
                ef.t_co2_eq,
                input.ef_t2,
                input.fuel_start,
                input.fuel_wo,
                input.activity.change_rate_start.name,
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
                input.activity.change_rate_start.name,
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
                input.activity.change_rate_start.name,
                project.implementation_duration_yrs,
                project.capitalization_duration_yrs,
            ]

            res_w = SolidConsumption(*input_w).calculate_emissions()
            res_wo = SolidConsumption(*input_wo).calculate_emissions()

            return Result(res_w, res_wo, res_w - res_wo)

        return Result(0, 0, 0)


class IrrigationCalculator(BaseCalculator):
    """
    #TODO: Calculator for irrigation.
    """


class BuildingCalculator(BaseCalculator):
    """
    Calculator for buildings and roads.
    """

    def calculate(self) -> list[Result]:
        """
        Calculate emissions for a single Building module.
        """

        input: Building = self.data

        ef: BuildingEmissionFactor = BuildingEmissionFactor.objects.get(
            building_type=input.building_type
        )

        inputs = [ef.kg_co2_m2, input.t_co2_m2_t2, input.surface_w, input.surface_wo]

        return Result(*math_inputs.roads(*inputs))


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

        LEACHING_MULTI = LivestockParameter.objects.get(
            name="LEACHING_MULTIPLIER"
        ).value

        volatilization_multi = ManureManagementVolatilizationMultiplier.objects.get(
            moisture=project.moisture,
        )

        i_w = [
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate_start.name,
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

        results_w = MathLivestock(*i_w).calculate_emissions()

        i_wo = [
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            input.activity.change_rate_start.name,
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
            _input.activity.change_rate_start.name,
        ]

        results_w = NewIrrigation(*inputs_w).calculate_emissions()

        inputs_wo = [
            ef.value,
            _input.ef_t2_wo,
            _input.ha_start,
            _input.ha_wo,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            _input.activity.change_rate_start.name,
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
            input.activity.change_rate_start.name,
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
            input.activity.change_rate_start.name,
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
            input.activity.change_rate_start.name,
            project.implementation_duration_yrs,
            project.capitalization_duration_yrs,
            transportation_loss.value if input.fuel_type.name == "Electricity" else 0,
            input.gross_irrigation_water_wo,
        ]

        results_wo = OperationPhaseIrrigation(*inputs_wo).calculate_emissions()

        return Result(results_w+results_start, results_wo+results_start, results_w - results_wo)
