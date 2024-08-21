import json
import math
import random
from time import sleep

import api.calculators as calc
import api.defaults as defaults
import openpyxl as xl
import pandas as pd
import xlwings as xw
from api.models import (
    Activity,
    Climate,
    Country,
    FloodedRice,
    Group,
    ModuleType,
    Moisture,
    Project,
    SoilType,
    ProjectMembership,
)
from api.models import CustomUser as User
from api.tests.factories import ActivityFactory, FloodedRiceFactory, ProjectFactory
from ipcc.models import GlobalWarmingPotential, SoilOrganicCarbon

BATCH_SIZE = 1

climates = Climate.objects.all()
countries = Country.objects.all()
soil_types = SoilType.objects.all().exclude(name="Aggregated")
gw_potentials = GlobalWarmingPotential.objects.all()
soc_refs = SoilOrganicCarbon.objects.all()

# workbook = xl.load_workbook(filename="api/tests/EX-ACT_V9.4_open.xlsm")
# workbook = xw.Book("api/tests/EX-ACT_V9.4_open.xlsm")
# sheet = workbook.sheets["4.Grassland"]

country = random.choice(countries)
region = country.region
climate = random.choice(climates)
moisture = random.choice(climate.moistures.all())
soil_type = random.choice(soil_types)
gw_potential = GlobalWarmingPotential.objects.get(name="100 yr AR5 w/out CC feedback")

u = User.objects.get(email="admin@admin.com")
group: Group = Group.objects.get(name="Admin")

p: Project = ProjectFactory.create(
    user=u,
    climate=climate,
    moisture=moisture,
    country=country,
    gw_potential=gw_potential,
    soil_type=soil_type,
)

ProjectMembership.objects.create(user=u, project=p, group=group)

print(f"Country: {country}")
print(f"Region: {region}")
print(f"IPCC Region: {country.ipcc_region}")
print(f"Climate: {climate}")
print(f"Moisture: {moisture}")
print(f"Soil Type: {soil_type}")
print(f"GW Potential: {gw_potential}")
print(f"Implementation Years: {p.implementation_years}")
print(f"Capitalization Years: {p.capitalization_years}")

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
a.module_types.add(ModuleType.objects.get(name="Flooded Rice"))
a.save()

rices: list[FloodedRice] = FloodedRiceFactory.create_batch(BATCH_SIZE, activity=a)

total_livestocks = rices.__len__()
passed_livestocks = 0

print("Testing module...")
for i, rice in enumerate(rices):
    print(f"\n\nTesting module {i+1}...")
    print("-----------------------------------")

    print(f"Rice: {rice}")
    print(f"Area: {rice.area}")

    print(f"H2O Mgmt Before START: {rice.water_management_type_before_cultivation_start}")
    print(f"H2O Mgmt Before W/O: {rice.water_management_type_before_cultivation_wo}")
    print(f"H2O Mgmt Before W: {rice.water_management_type_before_cultivation_w}")

    print(f"H2O Mgmt After START: {rice.water_management_type_after_cultivation_start}")
    print(f"H2O Mgmt After W/O: {rice.water_management_type_after_cultivation_wo}")
    print(f"H2O Mgmt After W: {rice.water_management_type_after_cultivation_w}")

    print(f"Organic Amendment START: {rice.organic_amendment_type_start}")
    print(f"Organic Amendment W/O: {rice.organic_amendment_type_wo}")
    print(f"Organic Amendment W: {rice.organic_amendment_type_w}")

    print(f"Crop Yield START: {rice.crop_yield_start}")
    print(f"Crop Yield W/O: {rice.crop_yield_wo}")
    print(f"Crop Yield W: {rice.crop_yield_w}")

    # print(f"livestock_category_type_start: {rice.livestock_category_type.name}")
    # print(f"livestock_category_type_wo: {rice.livestock_category_type.name}")
    # print(f"livestock_category_type_w: {rice.livestock_category_type.name}")

    # print(f"livestock_production_type_start: {rice.livestock_production_type_start.name}")
    # print(f"livestock_production_type_wo: {rice.livestock_production_type_wo.name}")
    # print(f"livestock_production_type_w: {rice.livestock_production_type_w.name}")

    # sheet["I56"].value = rice.livestock_category_type.name
    # sheet["I57"].value = rice.livestock_category_type.name
    # sheet["I58"].value = rice.livestock_category_type.name

    # sheet["K56"].value = rice.livestock_production_type_start.name
    # sheet["K57"].value = rice.livestock_production_type_wo.name
    # sheet["K58"].value = rice.livestock_production_type_w.name

    # sheet["W56"].value = rice.heads_number_start
    # sheet["X56"].value = 0 if (sheet["I57"].value != sheet["I56"].value) or (sheet["K56"].value != sheet["K57"].value) else rice.heads_number_wo
    # sheet["Z56"].value = 0 if (sheet["I58"].value != sheet["I56"].value) or (sheet["K56"].value != sheet["K58"].value) else rice.heads_number_w

    # sheet["W57"].value = 0
    # sheet["X57"].value = rice.heads_number_wo if sheet["X56"].value == 0 else 0
    # sheet["Z57"].value = 0

    # sheet["W58"].value = 0
    # sheet["X58"].value = 0
    # sheet["Z58"].value = rice.heads_number_w if sheet["Z56"].value == 0 else 0

    # # print sheet ad76
    # print(f"Sheet Results W (AE76): {sheet['AE76'].value}")
    # print(f"Sheet Results W/O (AD76): {sheet['AD76'].value}")
    # print(f"Sheet Results Balance (AG76): {sheet['AG76'].value}")

    results = calc.CalculatorFactory().calculate_result(rice)
    _defaults = defaults.DefaultsFactory.get_defaults(rice)

    print("Defaults: ")
    print(json.dumps(_defaults.__dict__, indent=4))

    # sheet_results_w = float(sheet["AE76"].value)
    # sheet_results_wo = float(sheet["AD76"].value)

    math_results_w = results[0]
    math_results_wo = results[1]

    print("Math Results: ")
    print(results)

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
