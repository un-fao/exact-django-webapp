import time
from .models import *
from ipcc.models import *
from typing import List
from .utilities import *
from .serializers import *
from django.db.models import Q
from rest_framework.response import Response
from . import deforestation_functions as defo_math
from rest_framework import viewsets, status, permissions

class ProjectViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """
        Create a new project
        """
        return super().create(request, *args, **kwargs)

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

        start_time = time.time()

        # NOTE: Fetch heavy. Local page load reduced to ~400ms by not prefetching unnecessary objects. Async in FE?
        #       ~400ms seems to be the floor for load time for any page in Django on this machine
        # TODO: Requires proper performance testing to determine if this is a bottleneck
        # NOTE: For 101 inputs, local page load is ~2s. Although it's extremely unlikely to have that many inputs.
        
        defo_results = calc_defo_results(defo_input_list, project)
        
        print("--- %s seconds ---" % (time.time() - start_time))
        
        serializer = DefoResultsSerializer(defo_results)
        return Response(serializer.data)

def calc_defo_results(input_list: List[DeforestationInput], project:Project):

    # TODO: Define proper objects for results
    defo_results = {
        "inputs_emissions_list": [],
        "result": {
            "total_w": 0,
            "total_wo": 0,
            "balance": 0,
        }
    }

    for input in input_list:

        result = calc_defo_result(input, project)

        defo_results["inputs_emissions_list"].append({'input': input, 'result': result})
        defo_results["result"]["total_w"] += result["total_w"]
        defo_results["result"]["total_wo"] += result["total_wo"]
        defo_results["result"]["balance"] += result["balance"]

    return defo_results

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
    soc_ref = SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil=soil_type)
    total_biomass = TotalBiomassAfterDefo.objects.get(climate=climate, moisture=moisture, continent=continent, vegetation_type=vegetation_type)

    # NOTE: Maybe merge the mangroves and deforestation IPCC tables into one table?
    # NOTE: Maybe use Redis to further improve performance
    if(defo.vegetation_type != MANGROVES):
        defo_table = LitterDeadwoodCarbonStock.objects.get(forest=vegetation_type)
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
    flu = LandUseStockExchangeFactor.objects.get(climate=climate, moisture=moisture, agroforestry_system=land_use_type)
    
    inputs = [
        defo.ha_start,
        defo.ha_w,
        defo.ha_wo,
        project.implementation_duration_yrs,
        project.capitalization_duration_yrs,
        defo.ha_w_rate.name,
        defo.ha_w_rate.value,
        total_biomass.value,
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
        soc_ref.value,
        defo.rcs_soil_c_t2 # soil t2
    ]

    total_w, total_wo, balance = defo_math.GHG_emissions(*inputs)

    results = {
        "total_w": total_w,
        "total_wo": total_wo,
        "balance": balance
    }

    return results