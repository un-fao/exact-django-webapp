import random
from time import sleep

import api.calculators as calc
import api.models as models
import xlwings as xw
from api.models import (
    Activity,
    Climate,
    Country,
    ForestManagement,
    Grassland,
    Group,
    LandUseChange,
    ModuleType,
    Moisture,
    Project,
    SoilType,
    StatusType,
    UserProjectGroup,
    OrganicSoil,
)
from api.models import CustomUser as User
from api.tests.factories import (
    ActivityFactory,
    ForestManagementFactory,
    GrasslandFactory,
    LandUseChangeFactory,
    ProjectFactory,
    OrganicSoilFactory,
)
from ipcc.models import GlobalWarmingPotential, SoilOrganicCarbon

PROJECT_SIZE = 1
BATCH_SIZE = 1

climates = Climate.objects.all().exclude(name="Tropical Montane")
moistures = Moisture.objects.all().exclude(name="Montane")
countries = Country.objects.all()
soil_types = SoilType.objects.all().exclude(name="Aggregated").exclude(name="Spodic").exclude(active=False).exclude(name="Organic")
gw_potentials = GlobalWarmingPotential.objects.all()
soc_refs = SoilOrganicCarbon.objects.all()

# workbook = xw.Book("api/tests/EX-ACT_V9.4_open.xlsm")
# sheet = workbook.sheets["4.Cropland"]


for i in range(PROJECT_SIZE):
    country = random.choice(countries)
    region = country.region
    climate = random.choice(climates)
    moisture = random.choice(climate.moistures.all())
    soil_type = random.choice(soil_types)
    gw_potential = GlobalWarmingPotential.objects.get(name="100 yr AR5 w/out CC feedback")

    print(f"\n\nCountry: {country}")
    print(f"Region: {region}")
    print(f"IPCC Region: {country.ipcc_region}")
    print(f"Climate: {climate}")
    print(f"Moisture: {moisture}")
    print(f"Soil Type: {soil_type}")
    print(f"GW Potential: {gw_potential}")

    u = User.objects.get(email="admin@admin.com")
    group: Group = Group.objects.get(name="Admin")

    p: Project = ProjectFactory.create(
        user=u,
        climate=Climate.objects.get(name="Tropical"),
        moisture=Moisture.objects.get(name="Moist"),
        country=Country.objects.get(name="Bahamas"),
        gw_potential=gw_potential,
        soil_type=soil_type,
    )

    UserProjectGroup.objects.create(user=u, project=p, group=group)

    # ds = workbook.sheets["1.Description"]
    # ds["Q8"].value = p.country.region.name
    # ds["Q9"].value = p.country.name
    # ds["Q10"].value = p.climate.name
    # ds["Q11"].value = p.moisture.name
    # ds["Q12"].value = p.soil_type.name + " soils"
    # ds["T13"].value = p.implementation_years
    # ds["T14"].value = p.capitalization_years
    # sleep(1)

    a: Activity = ActivityFactory.create(project=p)

    a.module_types.add(ModuleType.objects.get(name="Forest Management"))
    a.module_types.add(ModuleType.objects.get(name="Grassland"))
    a.module_types.add(ModuleType.objects.get(name="Organic Soil"))
    a.save()

    luc: LandUseChange = LandUseChangeFactory.create(activity=a)
    luc.module_type_start = ModuleType.objects.get(name="Forest Management")
    luc.module_type_wo = ModuleType.objects.get(name="Grassland")
    luc.module_type_w = ModuleType.objects.get(name="Grassland")
    luc.save()

    organic_soil: OrganicSoil = OrganicSoilFactory.create(activity=a, land_use_change=luc)

    luc.organic_soil = organic_soil
    luc.save()

    forests: list[ForestManagement] = ForestManagementFactory.create_batch(BATCH_SIZE, activity=a)
    for forest in forests:
        forest.land_use_type_start = random.choice(models.LandUseType.objects.filter(module_types__class_name="ForestManagement", is_active=True, climates=p.climate).all())
        forest.land_use_type_w = forest.land_use_type_start
        forest.land_use_type_wo = forest.land_use_type_start
        forest.land_use_change = luc
        forest.status = StatusType.objects.get(name="READY")
        forest.save()

    grasslands: list[Grassland] = GrasslandFactory.create_batch(BATCH_SIZE, activity=a)
    for grassland in grasslands:
        grassland.land_use_change = luc
        grassland.status = StatusType.objects.get(name="READY")
        grassland.save()

    total_livestocks = forests.__len__()
    passed_livestocks = 0

    # print("Testing Forest...")
    # for i, forest in enumerate(forests):
    #     print(f"\n\nTesting Forest {i+1}...")
    #     print("-----------------------------------")

    #     print(f"Forest: {forest}")

    #     forest.save()

    #     print("Land Use Type Start: ", forest.land_use_type_start)
    #     print("Land Use Type W/O: ", forest.land_use_type_wo)
    #     print("Land Use Type W: ", forest.land_use_type_w)

    #     results = calc.CalculatorFactory().calculate_result(forest)

    #     math_results_w = results[0]
    #     math_results_wo = results[1]

    #     print(results)

    # print("Testing LUC Deforestation...")
    # print("-----------------------------------")
    # print(luc)

    # luc.save()

    # print("Module Type Start: ", luc.module_type_start)
    # print("Module Type W/O: ", luc.module_type_wo)
    # print("Module Type W: ", luc.module_type_w)

    # results = calc.CalculatorFactory().calculate_result(luc)

    # print(results)

    print("Testing Organic Soil...")
    print("-----------------------------------")
    print(organic_soil)

    organic_soil.save()

    results = calc.CalculatorFactory().calculate_result(organic_soil)

    print("Results: ", results)
