from .models import *
from ipcc.models import *
from .utilities import *
from .serializers import *
from django.db.models import Q
from rest_framework.response import Response
from math_model import defo, affo, oluc, annuals
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.views import *
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

activity_id = openapi.Parameter('activity_id', openapi.IN_QUERY, description="ID of activity related to the module", type=openapi.TYPE_INTEGER)
project_id = openapi.Parameter('project_id', openapi.IN_QUERY, description="ID of project related to the activity", type=openapi.TYPE_INTEGER)

class Result(object):
    def __init__(self, total_w, total_wo, balance):
        self.total_w = total_w
        self.total_wo = total_wo
        self.balance = balance

class AuthenticatedViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

class ProjectViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = Project.objects.all()
    serializer_class = get_model_serializer(Project)

class ActivityViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows activities to be viewed or edited. 
    """
    queryset = Activity.objects.all()
    serializer_class = get_module_serializer(Activity)

    @swagger_auto_schema(
        manual_parameters=[project_id],
        responses={400: 'project_id not provided'}
    )
    def list(self, request):
        """
        Get all activities for a given project, by filtering against a `project_id` query parameter in the URL.
        """
        project_id = get_query_param_or_validation_error(self.request, 'project_id')
        list = Activity.objects.filter(project__id=project_id, project__user=self.request.user)
        return Response(data=get_module_serializer(Activity)(list, many=True).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the activity.
        """
        activity = get_object_or_404(Activity, pk=pk, project__user=self.request.user)

        modules = {}
        module_types = ModuleType.objects.all()
        for module in module_types:
            module_model = apps.get_model(API, sanitize_for_model(module.name))
            module_object = module_model.objects.filter(activity__id=pk, activity__project__user=self.request.user).first()
            if module_object:
                modules[module.name] = {}
                modules[module.name][DATA] = get_module_serializer(module_model)(module_object).data
                try:
                    modules[module.name][RESULTS] = calc_result(module_object, activity.project)
                except Exception as e:
                    modules[module.name][RESULTS] = {DETAILS: str(e)}

        return Response(modules)

    @action(detail=True, methods=['get'])
    def modules(self, request, pk=None):
        """
        Lists the modules of a given activity.
        """

        if not Activity.objects.filter(pk=pk, project__user=self.request.user).exists():
            return Response(error(f"Activity with id '{pk}' does not exist."), status=status.HTTP_400_BAD_REQUEST)

        modules = {}
        module_types = ModuleType.objects.all()

        for module in module_types:
            module_model = apps.get_model(API, sanitize_for_model(module.name))
            module_object = module_model.objects.filter(activity__id=pk, activity__project__user=self.request.user).first()
            if module_object:
                modules[module.name] = get_module_serializer(module_model)(module_object).data
        
        return Response(data=modules, status=status.HTTP_200_OK)

class ModuleTypeViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows module types to be viewed or edited.
    """
    queryset = ModuleType.objects.all()
    serializer_class = get_model_serializer(ModuleType)

def generic_module_viewset(model: Model):
    class GenericModuleViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_module_serializer(model)

        def create(self, request):
            """
            Creates a new module for a given activity.
            """

            serializer = get_module_serializer(model)(data=request.data)
            if serializer.is_valid():

                activity_id = serializer.validated_data["activity"].pk

                # Check if the same module for this activity already exists
                # TODO: Can activities have multiples of the same module?
                if model.objects.filter(activity__id=activity_id).exists():
                    return Response(error(f"Module '{model.__name__}' already exists for this activity."), status=status.HTTP_400_BAD_REQUEST)

                # Check if the activity belongs to the user
                activity = get_object_or_404(Activity, pk=activity_id, project__user=self.request.user)
                serializer.save(activity=activity)

                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        def retrieve(self, request, pk=None):
            module = get_object_or_404(model, pk=pk, activity__project__user=self.request.user)
            return Response(get_module_serializer(model)(module).data)

        def list(self, request):
            """
            Lists the module(s) of a given activity,
            by filtering against a `activity_id` query parameter in the URL.
            """

            activity_id = get_query_param_or_validation_error(self.request, 'activity_id')
            module = get_object_or_404(model, activity__id=activity_id)

            serializer = get_module_serializer(model)(module)
            return Response(serializer.data)

        @action(detail=True, methods=['get'])
        def results(self, request, pk=None):
            """
            Calculates and returns total emissions for a single module.
            TODO: Define structure and format of the real response.
            """

            module = get_object_or_404(model, pk=pk, activity__project__user=self.request.user)

            try:
                module_results = calc_result(module, module.activity.project)
            except Exception as e:
                return Response(error(str(e)), status=status.HTTP_400_BAD_REQUEST)

            serializer = get_result_serializer()(module_results)

            return Response(serializer.data)

    return GenericModuleViewSet

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
        case _:
            raise Exception(f"Module '{input.__class__.__name__}' not supported.")

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