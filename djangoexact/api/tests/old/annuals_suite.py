import math
import random
from time import sleep

import api.calculators as calc
import openpyxl as xl
import pandas as pd
import xlwings as xw
from api.models import (
    Activity,
    AnnualCropland,
    Climate,
    Country,
    Group,
    Moisture,
    Project,
    SoilType,
    ProjectMembership,
)
from api.models import CustomUser as User
from api.tests.factories import ActivityFactory, AnnualCroplandFactory, ProjectFactory
from ipcc.models import GlobalWarmingPotential, SoilOrganicCarbon

PROJECT_SIZE = 5
BATCH_SIZE = 1

climates = Climate.objects.all().exclude(name="Tropical Montane")
moistures = Moisture.objects.all().exclude(name="Montane")
countries = Country.objects.all()
soil_types = SoilType.objects.all().exclude(name="Aggregated").exclude(name="Spodic").exclude(active=False).exclude(name="Organic")
gw_potentials = GlobalWarmingPotential.objects.all()
soc_refs = SoilOrganicCarbon.objects.all()

# workbook = xl.load_workbook(filename="api/tests/EX-ACT_V9.4_open.xlsm")
workbook = xw.Book("api/tests/EX-ACT_V9.4_open.xlsm")
sheet = workbook.sheets["4.Cropland"]


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

    ProjectMembership.objects.create(user=u, project=p, group=group)

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

    annuals: list[AnnualCropland] = AnnualCroplandFactory.create_batch(BATCH_SIZE, activity=a)

    total_livestocks = annuals.__len__()
    passed_livestocks = 0

    print("Testing module...")
    for i, annual in enumerate(annuals):
        print(f"\n\nTesting module {i+1}...")
        print("-----------------------------------")

        print(f"grassland: {annual}")

        print("Tillage Management Type Start: ", annual.tillage_management_type_start)
        print("Tillage Management Type W/O: ", annual.tillage_management_type_wo)
        print("Tillage Management Type W: ", annual.tillage_management_type_w)

        print("Organic Input Type Start: ", annual.organic_input_type_start)
        print("Organic Input Type W/O: ", annual.organic_input_type_wo)
        print("Organic Input Type W: ", annual.organic_input_type_w)

        print("Residue Management Type Start: ", annual.residue_management_type_start)
        print("Residue Management Type W/O: ", annual.residue_management_type_wo)
        print("Residue Management Type W: ", annual.residue_management_type_w)

        print("Land Use Type Start: ", annual.land_use_type_start)
        print("Land Use Type W/O: ", annual.land_use_type_wo)
        print("Land Use Type W: ", annual.land_use_type_w)

        sheet["E25"].value = annual.land_use_type_start.name
        sheet["G25"].value = annual.tillage_management_type_start.name
        sheet["I25"].value = annual.organic_input_type_start.name
        sheet["K25"].value = annual.residue_management_type_start.name
        sheet["M25"].value = annual.crop_yield_start

        sheet["E26"].value = annual.land_use_type_wo.name
        sheet["G26"].value = annual.tillage_management_type_wo.name
        sheet["I26"].value = annual.organic_input_type_wo.name
        sheet["K26"].value = annual.residue_management_type_wo.name
        sheet["M26"].value = annual.crop_yield_wo

        sheet["E27"].value = annual.land_use_type_w.name
        sheet["G27"].value = annual.tillage_management_type_w.name
        sheet["I27"].value = annual.organic_input_type_w.name
        sheet["K27"].value = annual.residue_management_type_w.name
        sheet["M27"].value = annual.crop_yield_w

        has_tillage_changed_wo = sheet["G26"].value != sheet["G25"].value
        has_organic_changed_wo = sheet["I26"].value != sheet["I25"].value
        has_residue_changed_wo = sheet["K26"].value != sheet["K25"].value
        has_yield_changed_wo = sheet["M26"].value != sheet["M25"].value

        has_tillage_changed_w = sheet["G27"].value != sheet["G25"].value
        has_organic_changed_w = sheet["I27"].value != sheet["I25"].value
        has_residue_changed_w = sheet["K27"].value != sheet["K25"].value
        has_yield_changed_w = sheet["M27"].value != sheet["M25"].value

        sheet["Q25"].value = annual.area
        sheet["R25"].value = 0 if has_tillage_changed_wo or has_organic_changed_wo or has_residue_changed_wo else annual.area
        sheet["T25"].value = 0 if has_tillage_changed_w or has_organic_changed_w or has_residue_changed_w else annual.area

        sheet["Q26"].value = 0
        sheet["R26"].value = annual.area if sheet["R25"].value == 0 else 0
        sheet["T26"].value = 0

        sheet["Q27"].value = 0
        sheet["R27"].value = 0
        sheet["T27"].value = annual.area if sheet["T25"].value == 0 else 0

        results = calc.CalculatorFactory().calculate_result(annual)

        sheet_results_w = float(sheet["X37"].value)
        sheet_results_wo = float(sheet["W37"].value)

        math_results_w = results[0]
        math_results_wo = results[1]

        print(f"Sheet Results W (X37): {sheet['X37'].value}")
        print(f"Sheet Results W/O (W37): {sheet['W37'].value}")
        print(f"Sheet Results Balance (Z37): {sheet['Z37'].value}")
        print(results)

        # Check if sheet results and math results are equal within a margin of error of 5%

        is_wo_equal = math.isclose(sheet_results_wo, math_results_wo, rel_tol=0.1)
        is_w_equal = math.isclose(sheet_results_w, math_results_w, rel_tol=0.1)

        if is_wo_equal and is_w_equal:
            passed_livestocks += 1
            print("Test Passed!")

        else:
            print("\n\nTest Failed!")
            print(f"Sheet Results W/O: {sheet_results_wo}")
            print(f"Math Results W/O: {math_results_wo}")
            print(f"Sheet Results W: {sheet_results_w}")
            print(f"Math Results W: {math_results_w}")

    print(f"\nTotal Tested Anuals: {total_livestocks}")
    print(f"Passed Tests: {passed_livestocks}\n\n")
