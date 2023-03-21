from .models import Deforestation, Afforestation, OtherLandUse, AnnualCropping, Project
from math_model import defo, affo, oluc, annuals, perennial_cropping, coastal_wetlands, grassland_management, fisheries_and_aquaculture, forest_management
from .serializers import *
from ipcc.models import *
from .utilities import *

class Result(object):
    """
    Base class for all results.
    """
    def __init__(self, total_w, total_wo, balance):
        self.total_w = total_w
        self.total_wo = total_wo
        self.balance = balance

def calc_result(input: Model) -> list[Result]:
    """
    Calculates the results for a given module.
    """
    try:
        func = f"calc_{input.__class__.__name__.lower()}_result"
        return globals()[func](input)
    except KeyError:
        raise Exception(f"Module '{input.__class__.__name__}' not (yet) supported.")
    except Exception as ex:
        raise ex

def calc_extraction_result(input: Extraction):
    """
    Calculates the results for an extraction module.
    """

    # Extraction
    project = input.activity.project
    climate = project.climate
    moisture = project.moisture
    vegetation_type = input.vegetation_type

    criteria = {
        'climate':climate,
        'moisture':moisture,
        'vegetation_type':vegetation_type
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
                'climate':climate,
                'moisture':moisture,
                'vegetation_type':vegetation_type,
                'soil_type':input.extraction_soil_type_t2
            }
            soil_1m = DefaultSoilCarbonStock.objects.get(**cs_criteria).value
        except DefaultSoilCarbonStock.DoesNotExist:
            # TODO: Insert default values for other soil_types at 0 in db
            soil_1m = 0

    extraction_inputs = [
        input.ha_start,
        input.ha_w_excavated_percentage,
        input.ha_wo_excavated_percentage,
        agb.value,
        bgb.value,
        litter.value,
        dw.value,
        soil_1m,
        .96, #TODO: Add to db
        input.extraction_ag_t2,
        input.extraction_bg_t2,
        input.extraction_litter_t2,
        input.extraction_deadwood_t2,
        input.extraction_soil_t2,
        input.c_after_excavation_t2,

    ]

    extraction_result = Result(*coastal_wetlands.extraction_and_excavation_w_wo(*extraction_inputs))

    # Drainage
    if vegetation_type.name == MANGROVES:
        atwood = Atwood.objects.get(country=project.country)
        soil_1m = atwood.mg_c_ha
    else:
        try:
            cs_criteria = {
                'climate':climate,
                'moisture':moisture,
                'vegetation_type':vegetation_type,
                'soil_type':input.drainage_soil_type_t2
            }
            soil_1m = DefaultSoilCarbonStock.objects.get(**cs_criteria).value
        except DefaultSoilCarbonStock.DoesNotExist:
            # TODO: Insert default values for other soil_types at 0 in db
            soil_1m = 0 
    
    drainage_ef = DrainageEmissionFactor.objects.get(
        climate=climate,
        moisture=moisture,
        vegetation_type=vegetation_type
    )

    drainage_inputs = [
        input.ha_start,
        input.drainage_percentage_start,
        input.drainage_percentage_w,
        input.drainage_percentage_w_rate.name,
        input.drainage_percentage_w_rate.value,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        agb.value,
        bgb.value,
        litter.value,
        dw.value,
        soil_1m,
        drainage_ef.value,
        input.drainage_ag_t2,
        input.drainage_bg_t2,
        input.drainage_litter_t2,
        input.drainage_deadwood_t2,
        input.drainage_soil_t2,
        input.ef_drainage_t2,
        input.drainage_percentage_wo,
        input.drainage_percentage_wo_rate.name,
        input.drainage_percentage_wo_rate.value
    ]

    drainage_result = Result(*coastal_wetlands.drainage_w_wo(*drainage_inputs))

    return [extraction_result, drainage_result]

def calc_coastalwaterbody_result(input:CoastalWaterbody):

    project = input.activity.project
    methane_emission_factor = OtherConstructedWaterbodiesEmissionFactor.objects.get(
        climate=project.climate, 
        moisture=project.moisture,
        waterbody_type=input.waterbody_type    
    )

    inputs = [
        input.ha_start,
        input.ha_w,
        TROPHIC_STATE,
        methane_emission_factor.value,
        input.trophic_alpha_t2,
        input.ch4_start_t2,
        input.ch4_w_t2,
        project.gw_potential.ch4,
        project.capitalization_duration_yrs,
        project.implementation_duration_yrs,
        input.ha_w_rate.value,
        input.ha_wo,
        input.ch4_wo_t2,
        input.ha_wo_rate.value,
        input.trophic_mean_annual_t2,
    ]

    return [Result(*coastal_wetlands.coastal_waterbodies_w_wo(*inputs))]

def calc_rewetting_result(input: Rewetting):
    """
    Calculate emissions for a single Rewetting module.
    """

    project = input.activity.project
    climate = project.climate
    moisture = project.moisture
    vegetation_type = input.vegetation_type

    criteria = {
        'climate':climate,
        'moisture':moisture,
        'vegetation_type':vegetation_type
    }

    agb = CoastalAboveGroundBiomass.objects.get(**criteria)
    bgb = CoastalBGAGRatio.objects.get(**criteria)
    litter = CoastalLitter.objects.get(**criteria)
    dw = CoastalDeadwood.objects.get(**criteria)
    carbon = RewettingCarbonFactor.objects.get(**criteria)
    methane = RewettingMethaneFactor.objects.get(**criteria)

    inputs =  [
        agb.value,
        bgb.value,
        litter.value,
        dw.value,
        carbon.value,
        methane.value,
        input.ag_t2,
        input.bg_t2,
        input.litter_t2,
        input.deadwood_t2,
        input.ef_co2_t2,
        input.ef_ch4_t2,
        input.avg_salinity_t2.value,
        0, # area_start does not exist for rewetting
        input.ha_w,
        input.ha_w_rate.name,
        input.ha_w_rate.value,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        project.gw_potential.ch4,
        input.ha_wo,
        input.ha_wo_rate.name,
        input.ha_wo_rate.value,
    ]

    return [Result(*coastal_wetlands.rewetting_w_wo(*inputs))]

def calc_afforestation_result(input: Afforestation):
    """
    Calculate emissions for a single Afforestation module.
    """

    project = input.activity.project
    lut = input.land_use_type
    vt = input.vegetation_type
    continent = project.continent

    cml = {
        'climate':project.climate,
        'moisture':project.moisture,
        'land_use_type':lut
    }

    cvt = {
        'continent':continent,
        'vegetation_type':vt
    }

    initial_biomass = ForestTotalBiomass.objects.get(**cml,continent=continent)
    combustion_factor = AfforestationCombustionFactorValues.objects.get(land_use_type=lut)
    
    # NOTE: Maybe merge all LandUseStockExchangeFactors and filter by model?
    flu = AfforestationLandUseStockExchangeFactor.objects.get(**cml)
    litter_dw = LitterDeadwoodCarbonStock.objects.get(vegetation_type=vt)
    ag_net_biomass = AboveGroundNetBiomassGrowth.objects.get(**cvt)

    le_20yrs = ag_net_biomass.value_upto_20_years
    gt_20yrs = ag_net_biomass.value_after_20_years

    bg_biomass_before_20_yrs = BelowGroundBiomass.objects.get_max_below_threshold(**cvt,threshold=le_20yrs)
    bg_biomass_after_20_yrs = BelowGroundBiomass.objects.get_max_below_threshold(**cvt,threshold=gt_20yrs)

    ag_biomass = AboveGroundBiomass.objects.get(**cvt)
    bg_biomass_le_125 = BelowGroundBiomass.objects.get_lowest_value(**cvt)
    bg_biomass_gt_125 = BelowGroundBiomass.objects.get_highest_value(**cvt)

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
    
    return [Result(*affo.afforestation(*inputs))]

def calc_deforestation_result(input: Deforestation):
    """
    Calculate emissions for a single Deforestation module.
    """

    project = input.activity.project
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
    moisture_factor = DefaultEmissionFactor.objects.filter(moisture=moisture)
    moisture_factor = moisture_factor.filter(Q(input__name__icontains="Other N Inputs") | Q(input__name__icontains="All N Inputs")).first()
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
        mangroves_data.agb_c if mangroves_data is not None else ag_biomass.value,
        mangroves_data.bgb if mangroves_data is not None else bg_biomass.value,
        CN_RATIO_GRASSLAND,
        input.final_rcs_soil_c_t2, # soil after defo t2
        soc_ref.value if soc_ref.value is not None else 0,
        input.rcs_soil_c_t2 # soil t2
    ]

    return [Result(*defo.GHG_emissions(*inputs))]

def calc_otherlanduse_result(input: OtherLandUse):
    """
    Calculate emissions for a single OtherLandUse module.
    """

    project = input.activity.project
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

    total_biomass = TotalBiomassAfterDefo.objects.get(
        climate=climate, 
        moisture=moisture, 
        continent=continent, 
        land_use_type=final_land_use_type
    )

    flu_initial = AfforestationLandUseStockExchangeFactor.objects.get(
        climate = project.climate,
        moisture = project.moisture,
        land_use_type = initial_land_use
    )

    flu_final = LandUseCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=final_land_use_type)

    c_n_ratio = CN_RATIO_GRASSLAND if initial_land_use.name == "Grassland" else CN_RATIO_FOREST

    moisture_factor = DefaultEmissionFactor.objects.get(moisture=moisture, input__name__icontains="Other N Inputs")
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
    
    return [Result(*oluc.calculate_w_wo_balance(*inputs))]

def calc_annualcropping_result(input: AnnualCropping):
    """
    Calculate emissions for a single AnnualCropping module.
    """

    project = input.activity.project
    climate = project.climate
    moisture = project.moisture
    land_use_type = input.land_use_type
    minor_land_use_type = input.minor_crop_type_t2

    relative, relation = get_assessment_or_parent(input)
    is_parent = relation == 'parent'

    burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Agricultural residues")
    fires_combustion_factor = FiresCombustionFactor.objects.get(land_use_type=land_use_type)
    n_estimation_factor = CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=land_use_type)

    # Minor crop
    try:
        minor_combustion_factor = FiresCombustionFactor.objects.get(land_use_type=minor_land_use_type)
        # TODO: Change logic for cleaner code
        minor_burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Agricultural residues")
        minor_n_estimation_factor = CropNitrousEstimationDefaultFactor.objects.get_or_grains(land_use_type=minor_land_use_type)
    except:
        # If only one of the above operations fails, all minor variables must be set to None
        minor_burning_emission_factor = None
        minor_combustion_factor = None
        minor_n_estimation_factor = None

    # TODO: Rename all tables related to FLU, FI, FMG
    # TODO: DefaultEmissionFactors must be inserted properly in the database (IPCC!B99)
    emission_factors = DefaultEmissionFactor.objects.get(moisture=moisture, input=input.organic_input_type)
    flu = CroplandFLU.objects.get(climate=climate, moisture=moisture, land_use_type__name="Long-Term Cultivated")
    fi = CroplandFI.objects.get(climate=climate, moisture=moisture, organic_input_type=input.organic_input_type)
    fmg = CroplandFMG.objects.get(climate=climate, moisture=moisture, tillage_management_type=input.tillage_management_type)

    crop_yield = input.crop_yield if input.crop_yield else CropYieldStats.objects.get(continent=project.continent, land_use_type=land_use_type).average


    # TODO: Temporary, must be handled by front-end
    ha_data = [input.ha_start, input.ha_w, input.ha_wo]

    if is_parent:
        match relative.__class__.__name__:
            case Deforestation.__name__:
                ha_data = [0, relative.ha_w, (relative.ha_start - relative.ha_wo)]
            case Afforestation.__name__:
                ha_data = [relative.ha_w, relative.ha_w, relative.ha_wo]
            case OtherLandUse.__name__:
                ha_data = [relative.ha_start, relative.ha_w, 0]

    inputs = [

        ### General
        *ha_data,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        input.ha_w_rate.name if not is_parent else relative.ha_w_rate.name,
        input.ha_w_rate.value if not is_parent else relative.ha_w_rate.value,
        input.ha_wo_rate.name if not is_parent else relative.ha_wo_rate.name,
        input.ha_wo_rate.value if not is_parent else relative.ha_wo_rate.value,

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
        crop_yield,
        getattr(minor_burning_emission_factor, "ch4", None), # TODO: Review looking for cleaner logic
        getattr(minor_combustion_factor, "value", None),
        input.minor_biomass_factor_t2,
        getattr(minor_n_estimation_factor, "slope", None),
        getattr(minor_n_estimation_factor, "intercept", None),
        input.minor_yield_t2,
        burning_emission_factor.n2o if input.residue_management_type.name == "Burned" else None,
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

    return [Result(*annuals.calculate_emissions(*inputs))]

def calc_perennialcropping_result(input: PerennialCropping):
    """
    Calculate emissions for a single PerennialCropping module.
    """

    project = input.activity.project
    climate = project.climate
    moisture = project.moisture
    continent = project.continent
    land_use_type = input.land_use_type
    parent, _ = get_assessment_or_parent(input)

    burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Savanna and grassland")
    
    # TODO: Replace 'other' with all the other land_use_types in db
    fires_combustion_factor = FiresCombustionFactor.objects.get_or_other(land_use_type=land_use_type)
    ag_default = PerennialAGB.objects.get_or_default(climate=climate, moisture=moisture, continent=continent, land_use_type=land_use_type)
    agb_max_c = PerennialMaxAGB.objects.get(climate=climate, land_use_type=land_use_type)
    bg_default = PerennialBGB.objects.get_or_default(climate=climate, moisture=moisture, continent=continent, land_use_type=land_use_type)

    flu = CroplandFLU.objects.get(climate=climate, moisture=moisture, land_use_type__name="Perennial/Tree Crop")

    fi = CroplandFI.objects.get(climate=climate, moisture=moisture, organic_input_type=input.organic_input_type)
    fmg = CroplandFMG.objects.get(climate=climate, moisture=moisture, tillage_management_type=input.tillage_management_type)

    inputs = [
        input.ha_start,
        input.ha_w,
        input.ha_wo,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        input.ha_w_rate.name if parent else 'D',
        input.ha_w_rate.value if parent else 0.5,
        input.ha_wo_rate.name if parent else 'D',
        input.ha_wo_rate.value if parent else 0.5,
        project.gw_potential.n2o,
        project.gw_potential.ch4,
        input.is_biomass_burned,
        burning_emission_factor.n2o,
        burning_emission_factor.ch4,
        fires_combustion_factor.value,
        1, # Default
        input.fire_periodicity_t2,
        input.residue_burned_t2,
        ag_default.value, 
        input.ag_t2, 
        agb_max_c.value,
        bg_default.value, 
        input.bg_t2,
        project.soc_ref.value,
        input.soc_t2 if parent else 1,
        flu.value if parent else 1, 
        input.flu_t2,
        fi.value,
        input.input_factor_t2,
        fmg.value,
        input.tillage_factor_t2,
    ]
    # BUG: Results for annual crops do not add up. Wait for Lorenzo's unlocked Excel files
    return [Result(*perennial_cropping.calculate_emissions(*inputs))]

def calc_grassland_result(input: Grassland):
    """
    Calculate emissions for a single Grassland module.
    """

    project = input.activity.project
    ef = BurningEmissionFactor.objects.get(category__name="Savanna and grassland")
    agb = GrasslandAGB.objects.get(climate=project.climate, moisture=project.moisture)
    cf = .77
    proj_soc = project.soc_ref.value

    relative, relation = get_assessment_or_parent(input)
    is_parent = relation == 'parent'

    # NOTE: Default values at start are for 'Non-Degraded' land
    soc_start = GrasslandStockExchangeFactor.objects.filter(
        grassland_management_type=input.grassland_management_type_start, 
        climate=project.climate
    ).first()

    soc_w = GrasslandStockExchangeFactor.objects.filter(
        grassland_management_type=input.grassland_management_type_w, 
        climate=project.climate
    ).first()

    soc_wo = GrasslandStockExchangeFactor.objects.filter(
        grassland_management_type=input.grassland_management_type_wo, 
        climate=project.climate
    ).first()

    soc_start = proj_soc*soc_start.fmg*soc_start.flu*soc_start.fi if soc_start else project.soc_ref.value
    soc_w = proj_soc*soc_w.fmg*soc_w.flu*soc_w.fi if soc_w else project.soc_ref.value
    soc_wo = proj_soc*soc_wo.fmg*soc_wo.flu*soc_wo.fi if soc_wo else project.soc_ref.value

    # TODO: A method must be defined that takes into account the nature of the land use change (defo, affo, oluc) and builds start,w,wo accordingly.

    ha_data = [input.ha_start, input.ha_w, input.ha_wo]

    if is_parent:
        match relative.__class__.__name__:
            case Deforestation.__name__:
                ha_data = [0, relative.ha_w, (relative.ha_start - relative.ha_wo)]
            case Afforestation.__name__:
                ha_data = [relative.ha_w, relative.ha_w, relative.ha_wo]
            case OtherLandUse.__name__:
                ha_data = [relative.ha_start, relative.ha_w, 0]

    inputs = [
        *ha_data,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        relative.ha_wo_rate.name if is_parent else input.ha_w_rate.name,
        relative.ha_wo_rate.value if is_parent else input.ha_w_rate.value,
        relative.ha_w_rate.name if is_parent else input.ha_wo_rate.name,
        relative.ha_w_rate.value if is_parent else input.ha_wo_rate.value,
        project.gw_potential.n2o,
        project.gw_potential.ch4,
        input.years_w_fire_management,
        input.years_wo_fire_management,
        input.is_fire_used_w,
        input.is_fire_used_wo,
        ef.ch4,
        ef.n2o,
        agb.value,
        input.agb_t2,
        cf,
        input.combustion_factor_t2,
        soc_start,
        input.soil_carbon_start_t2,
        soc_w,
        soc_wo,
        input.soil_carbon_w_t2,
        input.soil_carbon_wo_t2
    ]

    return [Result(*grassland_management.calculate_total_emissions(*inputs))]

def calc_smallfishery_result(input: SmallFishery):
    """
    Calculate emissions for a single SmallFishery module.
    """

    project = input.activity.project
    ef_diesel_default_list = EnergyDefaultEmissionFactor.objects.filter(fuel_type__name__contains="Off-Road")

    # Average of all default emission factors for gasoil/diesel
    ef_diesel_default = sum([ef.t_co2_eq_m3 for ef in ef_diesel_default_list]) / len(ef_diesel_default_list)

    fui_default = SmallFisheryFUI.objects.get(
        fishery_type=input.fishery_type,
        gear_type=input.gear_type,
    )

    # TODO: Maybe use a table (.48734 for LargeFishery)
    lost_refrigerant_default = .083 
    
    # TODO: Maybe use a table (2.8 for LargeFishery)
    tonnes_ice_default = 2.8

    # TODO: Maybe use a table (60 for LargeFishery)
    kw_tonnes = 60

    electricity_emission = ElectricityEmission.objects.get(
        country = project.country,
        continent = project.continent
    )

    inputs = [
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        input.total_catch_yr_w_rate.value,
        input.total_catch_yr_wo_rate.value,
        input.total_catch_yr_start,
        input.total_catch_yr_w,
        input.total_catch_yr_wo,
        ef_diesel_default,
        input.energy_emission_factor_t2,
        fui_default.value,
        input.fui_start,
        input.fui_w,
        input.fui_wo,
        input.refrigerant_gwp,
        input.refrigerant_gwp_t2,
        lost_refrigerant_default,
        input.refrigerant_lost_per_tonne_t2,
        input.refrigerant_pc_start,
        input.refrigerant_pc_w,
        input.refrigerant_pc_wo,
        tonnes_ice_default,
        input.inshore_ice_production_emissions_t2,
        kw_tonnes,
        input.inshore_ice_production_kwh_per_tonne_t2,
        electricity_emission.operating_margin,
        input.ice_preserved_catch_pc_start,
        input.ice_preserved_catch_pc_w,
        input.ice_preserved_catch_pc_wo
    ]

    return [Result(*fisheries_and_aquaculture.total_emissions_small_or_large_fisheries(*inputs))]

def calc_largefishery_result(input: LargeFishery):
    """
    Calculate emissions for a single LargeFishery module.
    """

    project = input.activity.project
    ef_diesel_default_list = EnergyDefaultEmissionFactor.objects.filter(fuel_type__name__contains="Off-Road")

    # Average of all default emission factors for gasoil/diesel
    ef_diesel_default = sum([ef.t_co2_eq_m3 for ef in ef_diesel_default_list]) / len(ef_diesel_default_list)

    fui_default = LargeFisheryFUI.objects.get(
        fish_type=input.fish_type,
        gear_type=input.gear_type,
    )

    # TODO: Maybe use a table (.083 for SmallFishery)
    lost_refrigerant_default = .48734 
    
    # TODO: Maybe use a table (2.8 for SmallFishery)
    tonnes_ice_default = 2.8

    # TODO: Maybe use a table (60 for SmallFishery)
    kw_tonnes = 60

    electricity_country = input.inshore_ice_production_country if input.inshore_ice_production_country else project.country

    electricity_emission = ElectricityEmission.objects.get(
        country = electricity_country,
        continent = project.continent
    )

    inputs = [
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        input.total_catch_yr_w_rate.value,
        input.total_catch_yr_wo_rate.value,
        input.total_catch_yr_start,
        input.total_catch_yr_w,
        input.total_catch_yr_wo,
        ef_diesel_default,
        input.energy_emission_factor_t2,
        fui_default.value,
        input.fui_start,
        input.fui_w,
        input.fui_wo,
        input.refrigerant_gwp,
        input.refrigerant_gwp_t2,
        lost_refrigerant_default,
        input.refrigerant_lost_per_tonne_t2,
        input.refrigerant_pc_start,
        input.refrigerant_pc_w,
        input.refrigerant_pc_wo,
        tonnes_ice_default,
        input.inshore_ice_production_emissions_t2,
        kw_tonnes,
        input.inshore_ice_production_kwh_per_tonne_t2,
        electricity_emission.operating_margin,
        input.ice_preserved_catch_pc_start,
        input.ice_preserved_catch_pc_w,
        input.ice_preserved_catch_pc_wo
    ]

    return [Result(*fisheries_and_aquaculture.total_emissions_small_or_large_fisheries(*inputs))]

def calc_forest_result(input: Forest):
    """
    Calculate emissions for a single Forest module.
    """

    project: Project = input.activity.project
    data = None
    agb = None
    bgb = None
    soc = None
    LAND_INPUT_FACTOR_DEFAULT = 1
    AGB_MULTIPLICATION_FACTOR = .47

    if input.vegetation_type.name == "Mangrove Forest":
        data = DataOnMangroves.objects.get(
            climate = project.climate,
            moisture = project.moisture
        )
        agb = data.agb_c
        bgb = data.bgb
        soc = data.soc_ref
    else:
        data = LitterDeadwoodCarbonStock.objects.get(
            vegetation_type = input.vegetation_type
        )
        f_agb = ForestAGB.objects.get(
            continent=project.continent,
            vegetation_type = input.vegetation_type
        )
        f_bgb = BelowGroundBiomass.objects.get_max_below_threshold(
            continent=project.continent,
            vegetation_type = input.vegetation_type,
            threshold=f_agb.value
        )

        agb = f_agb.value * AGB_MULTIPLICATION_FACTOR
        bgb = f_bgb.value * agb
        soc = project.soc_ref.value
    
    cf: CombustionFactorValues = CombustionFactorValues.objects.get(vegetation_type=input.vegetation_type)

    inputs = [
        
        input.ha_start,
        input.ha_w,
        input.ha_wo,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        input.ha_w_rate.name,
        input.ha_wo_rate.name,
        input.ha_w_rate.value,
        input.ha_wo_rate.value,
        project.gw_potential.n2o,
        project.gw_potential.ch4,

        input.degradation_level_w.value,
        input.degradation_level_w_t2.value if input.degradation_level_w_t2 else None,
        input.degradation_level_wo.value,
        input.degradation_level_wo_t2.value if input.degradation_level_wo_t2 else None,
        input.degradation_level_start.value,
        input.degradation_level_start_t2.value if input.degradation_level_start_t2 else None,

        agb,
        input.ag_carbon_t2,
        bgb,
        input.bg_carbon_t2,

        data.litter,
        input.litter_t2,
        data.dw,
        input.deadwood_t2,
        soc,
        input.soil_carbon_t2,
        LAND_INPUT_FACTOR_DEFAULT,
        input.land_input_factor_start_t2,
        input.land_input_factor_w_t2,
        input.land_input_factor_wo_t2,

        input.fire_periodicity_w,
        input.fire_periodicity_wo,
        input.is_fire_used_w,
        input.is_fire_used_wo,
        input.fire_impact_percentage_w,
        input.fire_impact_percentage_wo,

        cf.value,
        cf.ch4,
        cf.n2o

    ]

    return [Result(*forest_management.calculate_emissions(*inputs))]

def calc_aquaculture_result(input: Aquaculture):
    """
    Calculate emissions for a single Aquaculture module.
    """

    project: Project = input.activity.project
    NITROUS_EF_DEFAULT = .00169
    FEED_EF_DEFAULT = 0

    inputs = [
        input.annual_production_start,
        input.annual_production_w,
        NITROUS_EF_DEFAULT,
        input.production_n2o_ef_t2,
        project.gw_potential.n2o,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        input.annual_production_w_rate.value,
        input.annual_production_wo_rate.value,
        input.annual_production_wo,
        input.annual_feed_quantity_start,
        input.annual_feed_quantity_w,
        FEED_EF_DEFAULT,
        input.feed_use_emissions_t2,
        input.annual_feed_quantity_wo
    ]

    return [Result(*fisheries_and_aquaculture.total_inland_coastal_aquaculture(*inputs))]