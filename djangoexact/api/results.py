from .models import Deforestation, Afforestation, OtherLandUse, AnnualCropping, Project
from math_model import defo, affo, oluc, annuals
from .serializers import *
from ipcc.models import *
from .utilities import *

class Result(object):
    def __init__(self, total_w, total_wo, balance):
        self.total_w = total_w
        self.total_wo = total_wo
        self.balance = balance

def calc_result(input: Model, project: Project):

    match input.__class__.__name__:
        case Deforestation.__name__:
            return calc_defo_result(input, project)
        case Afforestation.__name__:
            return calc_affo_result(input, project)
        case OtherLandUse.__name__:
            return calc_oluc_result(input, project)
        case AnnualCropping.__name__:
            return calc_annual_result(input, project)
        case Rewetting.__name__:
            return calc_rewetting_result(input, project)
        case _:
            raise Exception(f"Module '{input.__class__.__name__}' not supported.")

def calc_rewetting_result(input: Rewetting, project: Project):

    climate = project.climate
    moisture = project.moisture
    vegetation_type = input.vegetation_type

    cmv = {
        'climate':climate,
        'moisture':moisture,
        'vegetation_type':vegetation_type
    }

    agb = CoastalAboveGroundBiomass.objects.get(**cmv)
    bgb = CoastalBGAGRatio.objects.get(**cmv)
    litter = CoastalLitter.objects.get(**cmv)
    dw = CoastalDeadwood.objects.get(**cmv)
    carbon = RewettingCarbonFactor.objects.get(**cmv)
    methane = RewettingMethaneFactor.objects.get(**cmv)

    inputs =  [
        agb,
        bgb,
        litter,
        dw,
        carbon,
        methane,
        input.ag_t2,
        input.bg_t2,
        input.litter_t2,
        input.deadwood_t2,
        input.ef_co2_t2,
        input.ef_ch4_t2,
        project.soil_type.name,
        0, # area_start does not exist for rewetting
        input.ha_w,
        input.ha_w_rate.name,
        input.ha_w_rate.value,
        project.gw_potential.ch4,
        input.ha_wo,
        input.ha_wo_rate.name,
        input.ha_wo_rate.value,
    ]

    pass

def calc_affo_result(input: Afforestation, project:Project):
    """
    Calculate emissions for a single Afforestation input.
    """

    inital_land_use = input.land_use_type
    final_land_use = input.vegetation_type

    initial_biomass = ForestTotalBiomass.objects.get(
        climate = project.climate,
        moisture = project.moisture,
        continent = project.continent,
        land_use_type = inital_land_use
    )

    combustion_factor = AfforestationCombustionFactorValues.objects.get(land_use_type = inital_land_use)
    
    # NOTE: Maybe merge all LandUseStockExchangeFactors and filter by model?
    flu = AfforestationLandUseStockExchangeFactor.objects.get(
        climate = project.climate,
        moisture = project.moisture,
        land_use_type = inital_land_use
    )

    litter_dw = LitterDeadwoodCarbonStock.objects.get(vegetation_type = final_land_use)

    ag_net_biomass = AboveGroundNetBiomassGrowth.objects.get(
        vegetation_type = final_land_use,
        continent = project.continent
    )

    bg_biomass_before_20_yrs = BelowGroundBiomass.objects.get_max_within_threshold(
        continent = project.continent,
        vegetation_type = final_land_use,
        threshold = ag_net_biomass.value_upto_20_years
    )
    bg_biomass_after_20_yrs = BelowGroundBiomass.objects.get_max_within_threshold(
        continent = project.continent,
        vegetation_type = final_land_use,
        threshold = ag_net_biomass.value_after_20_years
    )

    ag_biomass = AboveGroundBiomass.objects.get(
        continent = project.continent,
        vegetation_type = final_land_use
    )

    bg_biomass_le_125 = BelowGroundBiomass.objects.get_lowest_value(
        continent = project.continent,
        vegetation_type = final_land_use,
    )

    bg_biomass_gt_125 = BelowGroundBiomass.objects.get_highest_value(
        continent = project.continent,
        vegetation_type = final_land_use,
    )

    inputs = [
        input.ha_w,
        input.ha_wo,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        initial_biomass.value,
        input.initial_biomass_t2,
        input.is_fire_used,
        project.gw_potential.n2o,
        project.gw_potential.ch4,
        combustion_factor.ch4,
        combustion_factor.n2o,
        combustion_factor.value,
        input.ha_w_rate.name,
        input.ha_w_rate.value,
        flu.value,
        project.soc_ref.value,
        project.soc_ref_t2,
        litter_dw.dw,
        input.final_dw_t2,
        litter_dw.litter,
        input.final_litter_t2,
        ag_net_biomass.value_upto_20_years,
        ag_net_biomass.value_after_20_years,
        bg_biomass_before_20_yrs.value,
        bg_biomass_after_20_yrs.value,
        input.final_ag_biomass_le_20yrs_t2,
        input.final_ag_biomass_gt_20yrs_t2,
        input.final_bg_biomass_le_20yrs_t2,
        input.final_bg_biomass_gt_20yrs_t2,
        input.final_rcs_t2,
        ag_biomass.value,
        bg_biomass_le_125.value,
        bg_biomass_gt_125.value
    ]
    
    return Result(*affo.afforestation(*inputs))

def calc_defo_result(input: Deforestation, project: Project):

    climate = project.climate
    moisture = project.moisture
    continent = project.continent
    soil_type = project.soil_type
    land_use_type = input.land_use_type
    vegetation_type = input.vegetation_type

    mangroves_data = None
    defo_table = None

    # Get the IPCC data
    soc_ref = SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type)
    total_biomass = TotalBiomassAfterDefo.objects.get(climate=climate, moisture=moisture, continent=continent, land_use_type=land_use_type)
    
    # NOTE: Maybe merge the mangroves and deforestation IPCC tables into one table?
    if(input.vegetation_type != MANGROVES):
        defo_table = LitterDeadwoodCarbonStock.objects.get(vegetation_type=vegetation_type)
        ag_biomass = AboveGroundBiomass.objects.get(continent=continent, vegetation_type=vegetation_type)
        bg_biomass = BelowGroundBiomass.objects.filter(continent=continent, vegetation_type=vegetation_type)

        # Gets the row matching the lowest threshold value above the ag_biomass threshold limit
        # NOTE: If a new, highest threshold is added to the db, this can return the wrong value unless the old highest threshold is set to a proper value
        # NOTE: This method could be added to the previous one, resulting in a single query but higher cognitive complexity
        # NOTE: For more than ~50 inputs, 25% improvement in performance by merging with the query above.
        bg_biomass = bg_biomass.filter(Q(threshold__gt=ag_biomass.value) | Q(threshold__isnull=True)).order_by('threshold').first()
    else:
        mangroves_data = DataOnMangroves.objects.get(continent=continent)

    combustion_factor = CombustionFactorValues.objects.get(vegetation_type=vegetation_type)
    moisture_factor = DefaultEmissionFactors.objects.get(moisture=moisture, input__name__icontains="Other N Inputs")
    flu = LandUseCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=land_use_type)
    
    inputs = [
        input.ha_start,
        input.ha_w,
        input.ha_wo,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        input.ha_w_rate.name,
        input.ha_w_rate.value,
        total_biomass.value if total_biomass.value is not None else 0,
        input.final_rcs_biomass_t2,
        project.gw_potential.n2o,
        project.gw_potential.ch4,
        input.is_fire_used,
        combustion_factor.n2o,
        combustion_factor.ch4,
        combustion_factor.value,
        moisture_factor.value,
        defo_table.litter if mangroves_data is None else mangroves_data.litter,
        input.rcs_litter_t2,
        defo_table.dw if mangroves_data is None else mangroves_data.dw,
        input.rcs_deadwood_t2,
        input.hwp,
        MANGROVE_FACTOR if mangroves_data is not None else NON_MANGROVE_FACTOR,
        input.rcs_bg_t2,
        input.rcs_ag_t2,
        flu.value,
        getattr(ag_biomass, 'value', mangroves_data.agb_c),
        getattr(bg_biomass, 'value', mangroves_data.bgb),
        CN_RATIO_GRASSLAND,
        input.final_rcs_soil_c_t2, # soil after defo t2
        soc_ref.value if soc_ref.value is not None else 0,
        input.rcs_soil_c_t2 # soil t2
    ]

    return Result(*defo.GHG_emissions(*inputs))

def calc_oluc_result(input: OtherLandUse, project:Project):
    """
    Calculate emissions for a single Afforestation input.
    """

    climate = project.climate
    moisture = project.moisture
    continent = project.continent
    final_land_use_type = input.final_land_use_type
    initial_land_use = input.initial_land_use_type

    initial_biomass = ForestTotalBiomass.objects.get(
        climate = project.climate,
        moisture = project.moisture,
        continent = project.continent,
        land_use_type = initial_land_use
    )

    total_biomass = TotalBiomassAfterDefo.objects.get(climate=climate, moisture=moisture, continent=continent, land_use_type=final_land_use_type)

    flu_initial = AfforestationLandUseStockExchangeFactor.objects.get(
        climate = project.climate,
        moisture = project.moisture,
        land_use_type = initial_land_use
    )

    flu_final = LandUseCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=final_land_use_type)

    c_n_ratio = CN_RATIO_GRASSLAND if initial_land_use.name == "Grassland" else CN_RATIO_FOREST

    moisture_factor = DefaultEmissionFactors.objects.get(moisture=moisture, input__name__icontains="Other N Inputs")
    combustion_factor = AfforestationCombustionFactorValues.objects.get(land_use_type=initial_land_use)

    inputs = [
        initial_biomass.value,
        total_biomass.value,
        input.initial_biomass_t2,
        input.final_biomass_t2,
        project.soc_ref.value,
        flu_initial.value,
        flu_final.value,
        project.soc_ref_t2,
        input.final_soil_carbon_t2, #TODO: Final socref?
        c_n_ratio,
        moisture_factor.value,
        combustion_factor.value,
        combustion_factor.n2o,
        combustion_factor.ch4,
        project.gw_potential.n2o,
        project.gw_potential.ch4,
        input.is_fire_used,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        input.ha_w_rate.name,
        input.ha_w_rate.value,
        input.ha_wo_rate.name,
        input.ha_wo_rate.value,
        input.ha_w,
        input.ha_wo
    ]
    
    return Result(*oluc.calculate_w_wo_balance(*inputs))

def calc_annual_result(input: AnnualCropping, project:Project):
    """
    Calculate emissions for a single Annual Cropping Module.
    """
    climate = project.climate
    moisture = project.moisture
    land_use_type = input.land_use_type
    minor_land_use_type = input.minor_crop_type_t2

    burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Agricultural residues")
    # TODO: Manage inputs for 'other' (Manager with select_or_other)
    fires_combustion_factor = FiresCombustionFactor.objects.get(land_use_type=land_use_type)
    n_estimation_factor = CropNitrousEstimationDefaultFactor.objects.get(land_use_type=land_use_type)

    # Minor crop
    try:
        minor_combustion_factor = FiresCombustionFactor.objects.get(land_use_type=minor_land_use_type)
        # TODO: Change logic for cleaner code
        minor_burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Agricultural residues")
        minor_n_estimation_factor = CropNitrousEstimationDefaultFactor.objects.get(land_use_type=minor_land_use_type)
    except:
        # If only one of the above operations fails, all minor variables must be set to None
        minor_burning_emission_factor = None
        minor_combustion_factor = None
        minor_n_estimation_factor = None

    emission_factors = DefaultEmissionFactors.objects.get(moisture=moisture, input=input.organic_input_type)
    flu = LandUseCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=land_use_type)
    fi = OrganicInputCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, organic_input_type=input.organic_input_type)
    fmg = TillageCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, tillage_management_type=input.tillage_management_type)

    inputs = [

        ### General
        input.ha_start,
        input.ha_w,
        input.ha_wo,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        input.ha_w_rate.name,
        input.ha_w_rate.value,
        input.ha_wo_rate.name,
        input.ha_wo_rate.value,

        ### Soil
        project.soc_ref.value,
        project.soc_ref_t2,
        flu.value,
        input.main_land_use_factor_t2,
        fi.value,
        input.main_organic_input_factor_t2,
        fmg.value,
        input.main_tillage_factor_t2,

        ### SOM
        emission_factors.value,
        project.gw_potential.n2o,

        ### Residue Burning
        project.gw_potential.ch4,
        # TODO: Add residue_management_type attribute to model for cleaner logic
        burning_emission_factor.ch4 if input.residue_management_type.name == "Burned" else None,
        fires_combustion_factor.value,
        input.main_biomass_factor_t2,
        n_estimation_factor.slope,
        n_estimation_factor.intercept,
        input.crop_yield,
        getattr(minor_burning_emission_factor, "ch4", None),
        getattr(minor_combustion_factor, "value", None),
        input.minor_biomass_factor_t2,
        getattr(minor_n_estimation_factor, "slope", None),
        getattr(minor_n_estimation_factor, "intercept", None),
        input.minor_yield_t2,
        burning_emission_factor.n2o,
        input.residue_management_type.name == "Retained",
        getattr(minor_burning_emission_factor, "n2o", None),
        getattr(input.minor_residue_management_type_t2, "name", None) == "Retained",
        n_estimation_factor.n_ag_residues,
        n_estimation_factor.rs_t,
        n_estimation_factor.n_bg_t,
        getattr(minor_n_estimation_factor, "n_ag_residues", None),
        getattr(minor_n_estimation_factor, "rs_t", None),
        getattr(minor_n_estimation_factor, "n_bg_t", None)
    ]

    return Result(*annuals.calculate_emissions(*inputs))