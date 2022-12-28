from .models import *
from ipcc.models import *
from typing import List
from .utilities import *
from .serializers import *
from django.db.models import Q
from rest_framework.response import Response
from math_model import defo as defo_math
from math_model import affo as affo_math
from math_model import oluc as oluc_math
from math_model import annuals
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.views import *
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

activity_id = openapi.Parameter('activity_id', openapi.IN_QUERY, description="ID of activity related to the module", type=openapi.TYPE_INTEGER)
project_id = openapi.Parameter('project_id', openapi.IN_QUERY, description="ID of project related to the activity", type=openapi.TYPE_INTEGER)

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
    serializer_class = get_model_serializer(Activity)

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
        return Response(data=get_model_serializer(Activity)(list, many=True).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def modules(self, request, pk=None):
        """
        Lists the modules of a given activity.
        """

        get_object_or_404(Activity, pk=pk, project__user=self.request.user)

        modules = {}
        module_types = ModuleType.objects.all()

        for module in module_types:
            module_model = apps.get_model('api', module.name.replace(" ", ""))
            module_object = module_model.objects.filter(activity__id=pk, activity__project__user=self.request.user).first()
            if module_object:
                modules[module.name] = get_model_serializer(module_model)(module_object).data
        
        return Response(data=modules, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        responses={404: 'Module not found', 400: 'Invalid Module name'}
    )
    def module_from_uri(self, request, activity_id=None, module_name: str=None):
        """
        Returns a Module for a given activity matching `activity_id`and `module_name`.
        """

        activity = get_object_or_404(Activity, pk=activity_id, project__user=self.request.user)

        try:
            module_object = apps.get_model('api', module_name.capitalize())
        except LookupError:
            return Response({"details": f"Module '{module_name}' does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        module = get_object_or_404(module_object, activity__id=activity.pk, activity__project__user=self.request.user)
        
        self.serializer_class = get_model_serializer(module.__class__)
        serializer = get_model_serializer(module.__class__)(module)

        return Response(serializer.data)

    @swagger_auto_schema(
        responses={404: 'Activity or Module not found', 400: 'Invalid Module name'}
    )
    def module_results(self, request, activity_id=None, module_name: str=None):
        """
        Calculates and returns total emissions for a single module.
        """

        activity = get_object_or_404(Activity, pk=activity_id, project__user=self.request.user)

        try:
            module_object = apps.get_model('api', module_name.capitalize())
        except LookupError:
            return Response({"details": f"Module '{module_name}' does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        module = get_object_or_404(module_object, activity__id=activity.pk, activity__project__user=self.request.user)

        module_results = calculate_module_results(module.__class__, module.pk, self.request.user)
        serializer = getResultSerializer()(module_results)

        return Response(serializer.data)

class ModuleTypeViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows module types to be viewed or edited.
    """
    queryset = ModuleType.objects.all()
    serializer_class = get_model_serializer(ModuleType)

def generic_module_viewset(model: Model):
    class GenericModelViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_model_serializer(model)

        def create(self, request):
            """
            Creates a new module for a given activity.
            """

            serializer = get_model_serializer(model)(data=request.data)
            if serializer.is_valid():

                activity_id = serializer.validated_data["activity"].pk

                # Check if the same module for this activity already exists
                # TODO: Can activities have multiples of the same module?
                if model.objects.filter(activity__id=activity_id).exists():
                    return Response({"details": f"Module '{model.__name__}' already exists for this activity."}, status=status.HTTP_400_BAD_REQUEST)

                activity = get_object_or_404(Activity, pk=activity_id, project__user=self.request.user)
                serializer.save(activity=activity)

                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        def retrieve(self, request, pk=None):
            module = get_object_or_404(model, pk=pk, activity__project__user=self.request.user)
            return Response(get_model_serializer(model)(module).data)

        def list(self, request):
            """
            Lists the module(s) of a given activity,
            by filtering against a `activity_id` query parameter in the URL.
            """

            activity_id = get_query_param_or_validation_error(self.request, 'activity_id')
            module = get_object_or_404(model, activity__id=activity_id)

            serializer = get_model_serializer(model)(module)
            return Response(serializer.data)

        @action(detail=True, methods=['get'])
        def results(self, request, pk=None):
            """
            Calculates and returns total emissions for a single module.
            TODO: Define structure and format of the real response.
            """

            module_results = calculate_module_results(model, pk, self.request.user)
            serializer = getResultSerializer()(module_results)

            return Response(serializer.data)

    return GenericModelViewSet

def calculate_module_results(model: Model, module_id: int, user: User):

    module = get_object_or_404(model, pk=module_id, activity__project__user=user)
    project = get_object_or_404(Project, pk=module.activity.project.id)
    return calc_result(module, project)

def calc_result(input: Model, project: Project):

    result = {}

    match input.__class__.__name__:
        case "Deforestation":
            result = calc_defo_result(input, project)
        case "Afforestation":
            result = calc_affo_result(input, project)
        case "OtherLandUse":
            result = calc_oluc_result(input, project)
        case "AnnualCropping":
            result = calc_annual_result(input, project)
        case _:
            return Response({"details": f"No implemented calculations for Module '{input.__class__.__name__}'."}, status=status.HTTP_400_BAD_REQUEST)

    return result

def calc_activity_results(input_list: List, project: Project):

    results = {
        "inputs": [],
        "result": {
            "total_w": 0,
            "total_wo": 0,
            "balance": 0,
        }
    }

    for input in input_list:

        result = calc_result(input, project)

        results["inputs"].append({'input': input, 'result': result})
        results["result"]["total_w"] += result["total_w"]
        results["result"]["total_wo"] += result["total_wo"]
        results["result"]["balance"] += result["balance"]

    return results

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
    
    total_w, total_wo, balance = affo_math.afforestation(*inputs)

    results = {
        "total_w": total_w,
        "total_wo": total_wo,
        "balance": balance
    }

    return results

def calc_defo_result(defo: Deforestation, project: Project):

    climate = project.climate
    moisture = project.moisture
    continent = project.continent
    soil_type = project.soil_type
    land_use_type = defo.land_use_type
    vegetation_type = defo.vegetation_type

    mangroves_data = None
    defo_table = None

    # Get the IPCC data
    soc_ref = SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type)
    total_biomass = TotalBiomassAfterDefo.objects.get(climate=climate, moisture=moisture, continent=continent, land_use_type=land_use_type)
    
    # NOTE: Maybe merge the mangroves and deforestation IPCC tables into one table?
    if(defo.vegetation_type != MANGROVES):
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
    moisture_factor = DefaultEmissionFactors.objects.get(moisture=moisture)
    flu = LandUseCarbonStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=land_use_type)
    
    inputs = [
        defo.ha_start,
        defo.ha_w,
        defo.ha_wo,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        defo.ha_w_rate.name,
        defo.ha_w_rate.value,
        total_biomass.value if total_biomass.value is not None else 0,
        defo.final_rcs_biomass_t2, # total_biomass t2
        project.gw_potential.n2o,
        project.gw_potential.ch4,
        defo.is_fire_used,
        combustion_factor.n2o,
        combustion_factor.ch4,
        combustion_factor.value,
        moisture_factor.value,
        defo_table.litter if mangroves_data is None else mangroves_data.litter,
        defo.rcs_litter_t2, # litter t2
        defo_table.dw if mangroves_data is None else mangroves_data.dw,
        defo.rcs_deadwood_t2, # deadwood t2
        defo.hwp,
        MANGROVE_FACTOR if mangroves_data is not None else NON_MANGROVE_FACTOR,
        defo.rcs_bg_t2, # bg t2
        defo.rcs_ag_t2, # ag t2
        flu.value,
        ag_biomass.value if mangroves_data is None else mangroves_data.agb_c,
        bg_biomass.value if mangroves_data is None else mangroves_data.bgb,
        CN_RATIO_GRASSLAND,
        defo.final_rcs_soil_c_t2, # soil after defo t2
        soc_ref.value if soc_ref.value is not None else 0,
        defo.rcs_soil_c_t2 # soil t2
    ]

    total_w, total_wo, balance = defo_math.GHG_emissions(*inputs)

    results = {
        "total_w": total_w,
        "total_wo": total_wo,
        "balance": balance
    }

    return results

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

    moisture_factor = DefaultEmissionFactors.objects.get(moisture=moisture)
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
        None, #Final socref
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
    
    total_w, total_wo, balance = oluc_math.calculate_w_wo_balance(*inputs)

    results = {
        "total_w": total_w,
        "total_wo": total_wo,
        "balance": balance
    }

    return results

def calc_annual_result(input: AnnualCropping, project:Project):
    """
    Calculate emissions for a single Annual Cropping Module.
    """
    climate = project.climate
    moisture = project.moisture
    continent = project.continent
    land_use_type = input.land_use_type
    minor_land_use_type = input.minor_crop_type_t2

    burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Agricultural residues")
    # TODO: Manage inputs for 'other' (Manager with select_or_other)
    fires_combustion_factor = FiresCombustionFactor.objects.get(land_use_type=land_use_type)
    n_estimation_factor = CropNitrousEstimationDefaultFactor.objects.get(land_use_type=land_use_type)

    # Minor crop

    minor_burning_emission_factor = None
    minor_combustion_factor = None
    minor_n_estimation_factor = None

    try:
        minor_combustion_factor = FiresCombustionFactor.objects.get(land_use_type=minor_land_use_type)
        # TODO: Change logic
        minor_burning_emission_factor = BurningEmissionFactor.objects.get(category__name="Agricultural residues")
        minor_n_estimation_factor = CropNitrousEstimationDefaultFactor.objects.get(land_use_type=minor_land_use_type)
    except:
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
        # TODO: Add residue_management_type to db for cleaner logic
        burning_emission_factor.ch4 if input.residue_management_type.name == "Burned" else None,
        fires_combustion_factor.value, # Wrong 0.89 should be 0.85
        input.main_biomass_factor_t2,
        n_estimation_factor.slope,
        n_estimation_factor.intercept,
        input.crop_yield,
        minor_burning_emission_factor.ch4 if minor_burning_emission_factor is not None else None,
        minor_combustion_factor.value if minor_combustion_factor is not None else None, # It's 0.85 in Excel?
        input.minor_biomass_factor_t2, # It's 0 in Excel?
        minor_n_estimation_factor.slope if minor_n_estimation_factor is not None else None,
        minor_n_estimation_factor.intercept if minor_n_estimation_factor is not None else None,
        input.minor_yield_t2,
        burning_emission_factor.n2o,
        input.residue_management_type.name == "Retained",
        minor_burning_emission_factor.n2o if minor_burning_emission_factor is not None else None,
        input.minor_residue_management_type_t2.name == "Retained" if input.minor_residue_management_type_t2 is not None else False,
        n_estimation_factor.n_ag_residues,
        n_estimation_factor.rs_t,
        n_estimation_factor.n_bg_t,
        minor_n_estimation_factor.n_ag_residues if minor_n_estimation_factor is not None else None,
        minor_n_estimation_factor.rs_t if minor_n_estimation_factor is not None else None,
        minor_n_estimation_factor.n_bg_t if minor_n_estimation_factor is not None else None,
    ]
    print(inputs)
    total_w, total_wo, balance = annuals.calculate_emissions(*inputs)

    results = {
        "total_w": total_w,
        "total_wo": total_wo,
        "balance": balance
    }

    return results