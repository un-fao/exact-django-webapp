from .models import *
from ipcc.models import *
from typing import List,TypeVar
from .utilities import *
from .serializers import *
from django.db.models import Q
from rest_framework.response import Response
from math_model import defo as defo_math
from math_model import affo as affo_math
from math_model import oluc as oluc_math
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view
from itertools import chain
from django.db import transaction
from rest_framework import exceptions
from django.shortcuts import get_object_or_404

def get_param_or_validation_error(request, param_name):
    param = request.query_params.get(param_name)
    if param is None:
        raise exceptions.ValidationError(f"{param_name} is required")
    return param

T = TypeVar('T')

class AuthenticatedViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

class ProjectViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = Project.objects.all()
    serializer_class = getModelSerializer(Project)

class ActivityViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows activities to be viewed or edited.
    """
    queryset = Activity.objects.all()
    serializer_class = getModelSerializer(Activity)

    def get_queryset(self):
        project_id = get_param_or_validation_error(self.request, 'project_id')

        return Activity.objects.filter(project__id=project_id, project__user=self.request.user)

class ModuleTypeViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows module types to be viewed or edited.
    """
    queryset = ModuleType.objects.all()
    serializer_class = getModelSerializer(ModuleType)

class DeforestationViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows deforestation inputs to be viewed or edited.
    """
    queryset = Deforestation.objects.all()
    serializer_class = getModelSerializer(Deforestation)

    def retrieve(self, request, pk=None):
        deforestation_module = get_object_or_404(Deforestation, pk=pk, activity__project__user=self.request.user)
        return Response(getModelSerializer(Deforestation)(deforestation_module).data)

    def list(self, request):
        """
        Lists the Deforestation module(s) of a given activity,
        by filtering against a `activity_id` query parameter in the URL.
        """

        activity_id = get_param_or_validation_error(self.request, 'activity_id')
        defo = get_object_or_404(Deforestation, activity__id=activity_id)

        serializer = getModelSerializer(Deforestation)(defo)
        return Response(serializer.data)

    def results(self, request, module_id=None):
        """
        Calculate total emissions for all Deforestation inputs.
        get: Returns list of emissions for each input and the total of all inputs
        TODO: Define structure and format of the real response.
        """

        defo_results = calculate_module_results(Deforestation, module_id, self.request.user)

        serializer = getResultSerializer()(defo_results)
        return Response(serializer.data)

class AfforestationViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows afforestation inputs to be viewed or edited.
    """
    queryset = Afforestation.objects.all()
    serializer_class = getModelSerializer(Afforestation)

    def retrieve(self, request, pk=None):
        afforestation_module = get_object_or_404(Afforestation, pk=pk, activity__project__user=self.request.userser)

        return Response(getModelSerializer(Afforestation)(afforestation_module).data)

    def list(self, request):
        """
        Lists the Afforestation module(s) of a given activity,
        by filtering against a `activity_id` query parameter in the URL.
        """

        activity_id = get_param_or_validation_error(self.request, 'activity_id')
        affo = get_object_or_404(Afforestation, activity__id=activity_id)

        serializer = getModelSerializer(Afforestation)(affo)
        return Response(serializer.data)

    def results(self, request, module_id=None):
        """
        Calculate total emissions for a single Deforestation module.
        TODO: Define structure and format of the real response.
        """

        defo_results = calculate_module_results(Afforestation, module_id, self.request.user)
        serializer = getResultSerializer()(defo_results)

        return Response(serializer.data)

class OtherLandUseChangeViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows other land use change inputs to be viewed or edited.
    """
    queryset = OtherLandUseChange.objects.all()
    serializer_class = getModelSerializer(OtherLandUseChange)

    def retrieve(self, request, pk=None):
        oluc_module = get_object_or_404(OtherLandUseChange, pk=pk, activity__project__user=self.request.user)
        return Response(getModelSerializer(OtherLandUseChange)(oluc_module).data)

    def list(self, request):
        """
        Lists the OtherLandUseChange module(s) of a given activity,
        by filtering against a `activity_id` query parameter in the URL.
        """

        activity_id = get_param_or_validation_error(self.request, 'activity_id')
        oluc = get_object_or_404(OtherLandUseChange, activity__id=activity_id)

        return Response(getModelSerializer(OtherLandUseChange)(oluc, many=True).data)

    def results(self, request, module_id=None):
        """
        Calculate total emissions for a single OtherLandUseChange module.
        """
            
        oluc_results = calculate_module_results(OtherLandUseChange, module_id, self.request.user)
        serializer = getResultSerializer()(oluc_results)

        return Response(serializer.data)

class AnnualCroppingViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows annual cropping inputs to be viewed or edited.
    """
    queryset = AnnualCropping.objects.all()
    serializer_class = getModelSerializer(AnnualCropping)

    def retrieve(self, request, pk=None):
        annual_cropping_module = get_object_or_404(AnnualCropping, pk=pk, activity__project__user=self.request.user)
        return Response(getModelSerializer(AnnualCropping)(annual_cropping_module).data)
    
    def list(self, request):
        """
        Lists the AnnualCropping module(s) of a given activity,
        by filtering against a `activity_id` query parameter in the URL.
        """

        activity_id = get_param_or_validation_error(self.request, 'activity_id')
        annual_cropping = get_object_or_404(AnnualCropping, activity__id=activity_id)

        return Response(getModelSerializer(AnnualCropping)(annual_cropping, many=True).data)

class PerennialCroppingViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows perennial cropping inputs to be viewed or edited.
    """
    queryset = PerennialCropping.objects.all()
    serializer_class = getModelSerializer(PerennialCropping)

    def retrieve(self, request, pk=None):
        perennial_cropping_module = get_object_or_404(PerennialCropping, pk=pk, activity__project__user=self.request.user)
        return Response(getModelSerializer(PerennialCropping)(perennial_cropping_module).data)
    
    def list(self, request):
        """
        Lists the PerennialCropping module(s) of a given activity,
        by filtering against a `activity_id` query parameter in the URL.
        """

        activity_id = get_param_or_validation_error(self.request, 'activity_id')
        perennial_cropping = get_object_or_404(PerennialCropping, activity__id=activity_id)

        return Response(getModelSerializer(PerennialCropping)(perennial_cropping, many=True).data)

class FloodedRiceViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows flooded rice inputs to be viewed or edited.
    """
    queryset = FloodedRice.objects.all()
    serializer_class = getModelSerializer(FloodedRice)

    def retrieve(self, request, pk=None):
        flooded_rice_module = get_object_or_404(FloodedRice, pk=pk, activity__project__user=self.request.user)
        return Response(getModelSerializer(FloodedRice)(flooded_rice_module).data)
    
    def list(self, request):
        """
        Lists the FloodedRice module(s) of a given activity,
        by filtering against a `activity_id` query parameter in the URL.
        """

        activity_id = get_param_or_validation_error(self.request, 'activity_id')
        flooded_rice = get_object_or_404(FloodedRice, activity__id=activity_id)

        return Response(getModelSerializer(FloodedRice)(flooded_rice, many=True).data)

class GrasslandViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows grassland inputs to be viewed or edited.
    """
    queryset = Grassland.objects.all()
    serializer_class = getModelSerializer(Grassland)

    def retrieve(self, request, pk=None):
        grassland_module = get_object_or_404(Grassland, pk=pk, activity__project__user=self.request.user)
        return Response(getModelSerializer(Grassland)(grassland_module).data)
    
    def list(self, request):
        """
        Lists the Grassland module(s) of a given activity,
        by filtering against a `activity_id` query parameter in the URL.
        """

        activity_id = get_param_or_validation_error(self.request, 'activity_id')
        grassland = get_object_or_404(Grassland, activity__id=activity_id)

        return Response(getModelSerializer(Grassland)(grassland, many=True).data)

class LivestockViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    """
    API endpoint that allows livestock inputs to be viewed or edited.
    """
    queryset = Livestock.objects.all()
    serializer_class = getModelSerializer(Livestock)

    def retrieve(self, request, pk=None):
        livestock_module = get_object_or_404(Livestock, pk=pk, activity__project__user=self.request.user)
        return Response(getModelSerializer(Livestock)(livestock_module).data)
    
    def list(self, request):
        """
        Lists the Livestock module(s) of a given activity,
        by filtering against a `activity_id` query parameter in the URL.
        """

        activity_id = get_param_or_validation_error(self.request, 'activity_id')
        livestock = get_object_or_404(Livestock, activity__id=activity_id)

        return Response(getModelSerializer(Livestock)(livestock, many=True).data)

@api_view(['GET'])
def get_modules_for_activity(request):

    activity_id = request.query_params.get('activity_id')
    if activity_id is None:
        return Response("activity_id is required", status=status.HTTP_400_BAD_REQUEST)

    modules = {}
    
    module_types = ModuleType.objects.all()
    for module in module_types:
        module_model = apps.get_model('api', module.name.replace(" ", ""))
        module_object = module_model.objects.filter(activity__id=activity_id).first()
        if module_object:
            modules[module.name] = getModelSerializer(module_model)(module_object).data
    
    return Response(data=modules, status=status.HTTP_200_OK)

def calculate_module_results(model: Model, module_id: int, user: User):

    module = get_object_or_404(model, pk=module_id, activity__project__user=user)
    project = get_object_or_404(Project, pk=module.activity.project.id)
    return calc_result(module, project)

def calc_result(input: Model, project:Project):

    result = {}

    match input.__class__.__name__:
        case "Deforestation":
            result = calc_defo_result(input, project)
        case "Afforestation":
            result = calc_affo_result(input, project)
        case "OtherLandUseChange":
            result = calc_oluc_result(input, project)
        case _:
            raise Exception("Invalid input type")

    return result

def calc_activity_results(input_list: List[T], project:Project):

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
    flu = LandUseStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=land_use_type)
    
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

def calc_oluc_result(input: OtherLandUseChange, project:Project):
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

    flu_final = LandUseStockExchangeFactor.objects.get(climate=climate, moisture=moisture, land_use_type=final_land_use_type)

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
