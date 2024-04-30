import math
import random
from time import sleep

import api.calculators as calc
import openpyxl as xl
import pandas as pd
import xlwings as xw
from api.models import (
    Activity,
    Climate,
    Country,
    Grassland,
    Group,
    ModuleType,
    Moisture,
    Project,
    SoilType,
    UserProjectGroup,
)
from api.models import CustomUser as User
from api.tests.factories import ActivityFactory, GrasslandFactory, ProjectFactory
from ipcc.models import GlobalWarmingPotential, SoilOrganicCarbon

BATCH_SIZE = 1

climates = Climate.objects.all().exclude(name="Tropical Montane")
moistures = Moisture.objects.all().exclude(name="Montane")
countries = Country.objects.all()
soil_types = SoilType.objects.all().exclude(name="Aggregated").exclude(name="Spodic").exclude(active=False)
gw_potentials = GlobalWarmingPotential.objects.all()
soc_refs = SoilOrganicCarbon.objects.all()

# workbook = xl.load_workbook(filename="api/tests/EX-ACT_V9.4_open.xlsm")
workbook = xw.Book("api/tests/EX-ACT_V9.4_open.xlsm")
sheet = workbook.sheets["4.Grassland"]

country = Country.objects.get(name="Tajikistan")
region = country.region
climate = Climate.objects.get(name="Cool Temperate")
# country = random.choice(countries)
# climate = random.choice(climates)
# moisture = random.choice(climate.moistures.all())
# soil_type = random.choice(soil_types)
moisture = Moisture.objects.get(name="Moist")
soil_type = SoilType.objects.get(name="High Activity Clay")
gw_potential = GlobalWarmingPotential.objects.get(name="100 yr AR5 w/out CC feedback")

print(f"Country: {country}")
print(f"Region: {region}")
print(f"IPCC Region: {country.ipcc_region}")
print(f"Climate: {climate}")
print(f"Moisture: {moisture}")
print(f"Soil Type: {soil_type}")
print(f"GW Potential: {gw_potential}")

u = User.objects.get(username="admin")
group: Group = Group.objects.get(name="Admin")

p: Project = ProjectFactory.create(
    user=u,
    climate=climate,
    moisture=moisture,
    country=country,
    gw_potential=gw_potential,
    soil_type=soil_type,
)

print(f"Capitalization Years: {p.capitalization_years}")
print(f"Implementation Years: {p.implementation_years}")

UserProjectGroup.objects.create(user=u, project=p, group=group)

ds = workbook.sheets["1.Description"]
ds["Q8"].value = p.country.region.name
ds["Q9"].value = p.country.name
ds["Q10"].value = p.climate.name
ds["Q11"].value = p.moisture.name
ds["Q12"].value = p.soil_type.name + " soils"
ds["T13"].value = p.implementation_years
ds["T14"].value = p.capitalization_years
sleep(1)

a: Activity = ActivityFactory.create(project=p)
a.module_types.set([ModuleType.objects.get(name="Grassland")])
a.save()

grassland: Grassland = GrasslandFactory.create_batch(BATCH_SIZE, activity=a)

total_livestocks = grassland.__len__()
passed_livestocks = 0

print("Testing module...")
for i, grassland in enumerate(grassland):
    print(f"\n\nTesting module {i+1}...")
    print("-----------------------------------")

    print(f"grassland: {grassland}")

    print(f"Grassland Management Type Start: {grassland.grassland_management_type_start}")
    print(f"Grassland Management Type W/O: {grassland.grassland_management_type_wo}")
    print(f"Grassland Management Type W: {grassland.grassland_management_type_w}")

    print(f"Is Fire Used START: {grassland.is_fire_used_start}")
    print(f"Fire Periodicity START: {grassland.fire_periodicity_start}")

    print(f"Is Fire Used W/O: {grassland.is_fire_used_wo}")
    print(f"Fire Periodicity W/O: {grassland.fire_periodicity_wo}")

    print(f"Is Fire Used W: {grassland.is_fire_used_w}")
    print(f"Fire Periodicity W: {grassland.fire_periodicity_w}")

    print(f"Yield Start: {grassland.yield_start}")
    print(f"Yield W/O: {grassland.yield_wo}")
    print(f"Yield W: {grassland.yield_w}")

    sheet["G26"].value = grassland.grassland_management_type_start.name
    sheet["I26"].value = grassland.grassland_management_type_wo.name
    sheet["K26"].value = grassland.grassland_management_type_w.name

    sheet["M26"].value = "YES" if grassland.is_fire_used_wo else "NO"
    sheet["N26"].value = grassland.fire_periodicity_wo if grassland.is_fire_used_wo else 2
    sheet["P26"].value = "YES" if grassland.is_fire_used_w else "NO"
    sheet["Q26"].value = grassland.fire_periodicity_w if grassland.is_fire_used_w else 2

    sheet["S26"].value = grassland.yield_start
    sheet["T26"].value = grassland.yield_wo
    sheet["U26"].value = grassland.yield_w

    sheet["W26"].value = grassland.area

    # print sheet ad76
    # print(f"Sheet Results W (AE38): {sheet['AE38'].value}")
    # print(f"Sheet Results W/O (AD38): {sheet['AD38'].value}")
    # print(f"Sheet Results Balance (AG38): {sheet['AG38'].value}")

    results = calc.CalculatorFactory().calculate_result(grassland)

    # sheet_results_w = float(sheet["AE38"].value)
    # sheet_results_wo = float(sheet["AD38"].value)

    math_results_w = results[0]
    math_results_wo = results[1]
    math_results_balance = results[2]

    print(
        {
            "math_results_w": math_results_w,
            "math_results_wo": math_results_wo,
            "math_results_balance": math_results_balance,
        }
    )

    # Check if sheet results and math results are equal within a margin of error of 5%

    # is_wo_equal = math.isclose(sheet_results_wo, math_results_wo, rel_tol=0.05)
    # is_w_equal = math.isclose(sheet_results_w, math_results_w, rel_tol=0.05)

    # if is_wo_equal and is_w_equal:
    #     passed_livestocks += 1
    #     print("Test Passed!")

    # else:
    #     print("\n\nTest Failed!")
    #     print(f"Sheet Results W/O: {sheet_results_wo}")
    #     print(f"Math Results W/O: {math_results_wo}")
    #     print(f"Sheet Results W: {sheet_results_w}")
    #     print(f"Math Results W: {math_results_w}")

print(f"\nTotal Tested Livestocks: {total_livestocks}")
print(f"Passed Tests: {passed_livestocks}\n\n")
