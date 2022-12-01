from .models import *
from ipcc.models import *
from typing import List,TypeVar
from .utilities import *
from .serializers import *
from django.db.models import Q
from rest_framework.response import Response
from math_model import defo as defo_math
from math_model import affo as affo_math
from rest_framework import viewsets, status, permissions

T = TypeVar('T')

class ProjectViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

class DeforestationInputViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows deforestation inputs to be viewed or edited.
    """
    queryset = DeforestationInput.objects.all()
    serializer_class = DeforestationInputSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, project_id=None):
        """
        Create a new deforestation input.
        """
        serializer = DeforestationInputSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # TODO: GET results for single input?
    def results(self, request, project_id=None, defo_id=None):
        """
        Calculate total emissions for all Deforestation inputs.
        get: Returns total emissions for Deforestation inputs.
        TODO: Communicate with FE on the structure and format of the real response.
        """
        project = Project.objects.prefetch_related().get(pk=project_id)
        defo_input_list = project.deforestationinput_set.all()

        defo_results = calc_results(defo_input_list, project)
        
        serializer = DefoResultsSerializer(defo_results)
        return Response(serializer.data)

class AfforestationInputViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows afforestation inputs to be viewed or edited.
    """
    queryset = AfforestationInput.objects.all()
    serializer_class = AfforestationInputSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, project_id=None):
        """
        Create a new afforestation input.
        """
        serializer = AfforestationInputSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def results(self, request, project_id=None, affo_id=None):
        """
        Calculate total emissions for all Afforestation inputs.
        get: Returns total emissions for Afforestation inputs.
        """
        project = Project.objects.prefetch_related().get(pk=project_id)
        affo_input_list = project.afforestationinput_set.all()

        affo_results = calc_results(affo_input_list, project)
        serializer = AffoResultsSerializer(affo_results)

        return Response(serializer.data, status=status.HTTP_200_OK)

def calc_results(input_list: List[T], project:Project):

    results = {
        "inputs": [],
        "result": {
            "total_w": 0,
            "total_wo": 0,
            "balance": 0,
        }
    }

    for input in input_list:

        match input.__class__.__name__:
            case "DeforestationInput":
                result = calc_defo_result(input, project)
            case "AfforestationInput":
                result = calc_affo_result(input, project)
            case _:
                raise Exception("Invalid input type")

        results["inputs"].append({'input': input, 'result': result})
        results["result"]["total_w"] += result["total_w"]
        results["result"]["total_wo"] += result["total_wo"]
        results["result"]["balance"] += result["balance"]

    return results

def calc_affo_result(input: AfforestationInput, project:Project):
    """
    Calculate emissions for a single Afforestation input.
    """

    initial_biomass = ForestTotalBiomass.objects.get(
        climate = project.climate,
        moisture = project.moisture,
        continent = project.continent,
        land_use_type = input.land_use_type
    )

    combustion_factor = AfforestationCombustionFactorValues.objects.get(land_use_type = input.land_use_type)
    
    # NOTE: Maybe merge all LandUseStockExchangeFactors and filter by model?
    flu = AfforestationLandUseStockExchangeFactor.objects.get(
        climate = project.climate,
        moisture = project.moisture,
        land_use_type = input.land_use_type
    )

    litter_dw = LitterDeadwoodCarbonStock.objects.get(vegetation_type = input.vegetation_type)

    ag_net_biomass = AboveGroundNetBiomassGrowth.objects.get(
        vegetation_type = input.vegetation_type,
        continent = project.continent
    )

    bg_biomass_before_20_yrs = BelowGroundBiomass.objects.get_max_within_threshold(
        continent = project.continent,
        vegetation_type = input.vegetation_type,
        threshold = ag_net_biomass.value_upto_20_years
    )
    bg_biomass_after_20_yrs = BelowGroundBiomass.objects.get_max_within_threshold(
        continent = project.continent,
        vegetation_type = input.vegetation_type,
        threshold = ag_net_biomass.value_after_20_years
    )

    ag_biomass = AboveGroundBiomass.objects.get(
        continent = project.continent,
        vegetation_type = input.vegetation_type
    )

    bg_biomass_le_125 = BelowGroundBiomass.objects.get_lowest_value(
        continent = project.continent,
        vegetation_type = input.vegetation_type,
    )

    bg_biomass_gt_125 = BelowGroundBiomass.objects.get_highest_value(
        continent = project.continent,
        vegetation_type = input.vegetation_type,
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
        None, # TODO: Add project.soc_ref_t2
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

def calc_defo_result(defo: DeforestationInput, project: Project):

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
        print(f"Continent: {continent}, Vegetation type: {vegetation_type}")
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
        CN_RATIO_FOREST,
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