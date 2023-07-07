from django.test import TestCase
from rest_framework.test import APIRequestFactory
from model_bakery import baker
from .models import *
from ipcc.models import *
from .factories import *
from .calculators import *
import openpyxl as xl
from openpyxl import load_workbook
from time import sleep
import xlwings as xw
import math

BATCH_SIZE = 10


def verbose_print(obj):
    for attr, value in obj.__dict__.items():
        print(attr, value)


climates = Climate.objects.all()
moistures = Moisture.objects.all()
countries = Country.objects.all()
soil_types = SoilType.objects.all()
gw_potentials = GlobalWarmingPotential.objects.all()
soc_refs = SoilOrganicCarbon.objects.all()

f = APIRequestFactory()

wbook = xw.Book("scenario.xlsx")

# User Creation
u = User.objects.get(username="admin")


while True:
    try:
        country = random.choice(countries)
        continent = country.continent
        climate = random.choice(climates)
        moisture = random.choice(moistures)
        soil_type = random.choice(soil_types)
        gw_potential = GlobalWarmingPotential.objects.get(
            name="100 yr AR5 w/out CC feedback"
        )
        socref = SoilOrganicCarbon.objects.get(
            climate=climate, moisture=moisture, soil_type=soil_type
        )
        print(f"Country: {country}")
        print(f"Continent: {continent}")
        print(f"Climate: {climate}")
        print(f"Moisture: {moisture}")
        print(f"Soil Type: {soil_type}")
        print(f"GW Potential: {gw_potential}")
        print(f"Soil Organic Carbon: {socref}")
        break
    except:
        pass


# Project Creation
p: ProjectFactory = ProjectFactory.create(
    user=u,
    climate=climate,
    moisture=moisture,
    continent=continent,
    country=country,
    gw_potential=gw_potential,
    soil_type=soil_type,
    soc_ref=socref,
)

# Spreadeheet setup
ds = wbook.sheets["1.Description"]
ds["Q8"].value = p.continent.name
ds["Q9"].value = p.country.name
ds["Q10"].value = p.climate.name
ds["Q11"].value = p.moisture.name
ds["Q12"].value = p.soil_type.name + " soils"
ds["T13"].value = p.implementation_duration_yrs
ds["T14"].value = p.capitalization_duration_yrs

# Activity Creation
a = ActivityFactory.create(project=p, user=u)

# Fishery Sheet
fishery_sheet = wbook.sheets["8. Fisheries and aquaculture"]

# Small Fishery Creation
sm_fisheries = SmallFisheryFactory.create_batch(BATCH_SIZE, activity=a)
total_fisheries = sm_fisheries.__len__()
passed_fisheries = 0

# Small Fishery Testing
for i, fishery in enumerate(sm_fisheries):
    print(f"Testing SmallFishery {i+1}...")

    results = CalculatorFactory().calculate_result(fishery)

    fishery_sheet["C18"].value = fishery.fishery_type.name
    fishery_sheet["E18"].value = fishery.gear_type_start.name
    fishery_sheet["H18"].value = fishery.refrigerant_pc_start
    fishery_sheet["J18"].value = fishery.refrigerant_pc_wo
    fishery_sheet["L18"].value = fishery.refrigerant_pc_w
    fishery_sheet["R18"].value = fishery.fui_start
    fishery_sheet["T18"].value = fishery.fui_wo
    fishery_sheet["U18"].value = fishery.fui_w
    fishery_sheet["X18"].value = fishery.total_catch_yr_start
    fishery_sheet["Z18"].value = fishery.total_catch_yr_wo
    fishery_sheet["AB18"].value = fishery.total_catch_yr_w

    fishery_sheet["H26"].value = fishery.ice_preserved_catch_pc_start
    fishery_sheet["J26"].value = fishery.ice_preserved_catch_pc_wo
    fishery_sheet["L26"].value = fishery.ice_preserved_catch_pc_w

    result = results[0]

    sheet_wo = float(fishery_sheet["AE30"].value)
    sheet_w = float(fishery_sheet["AG30"].value)
    sheet_balance = float(fishery_sheet["AI30"].value)

    try:
        assert math.isclose(result.total_w, sheet_w, rel_tol=0.02)
        assert math.isclose(result.total_wo, sheet_wo, rel_tol=0.02)
        assert math.isclose(result.balance, sheet_balance, rel_tol=0.02)
        passed_fisheries += 1
    except AssertionError as e:
        print("Results do not match the Excel")
        print(f"total_w: {result.total_w}, total_wo: {result.total_wo}")
        print(f"balance: {result.balance}")
        print(f"sheet_w: {sheet_w}, sheet_wo: {sheet_wo}")
        print(f"sheet_balance: {sheet_balance}")

# Large Fishery Creation
lg_fisheries = LargeFisheryFactory.create_batch(BATCH_SIZE, activity=a)
total_lg_fisheries = lg_fisheries.__len__()
passed_lg_fisheries = 0

# Large Fishery Testing
for i, fishery in enumerate(lg_fisheries):
    print(f"Testing LargeFishery {i+1}...")
    # verbose_print(fishery)

    results = CalculatorFactory().calculate_result(fishery)

    fishery_sheet["C44"].value = fishery.fish_type.name
    fishery_sheet["E44"].value = fishery.gear_type_start.name
    fishery_sheet["H44"].value = fishery.refrigerant_pc_start
    fishery_sheet["J44"].value = fishery.refrigerant_pc_wo
    fishery_sheet["L44"].value = fishery.refrigerant_pc_w
    fishery_sheet["R44"].value = fishery.fui_start
    fishery_sheet["T44"].value = fishery.fui_wo
    fishery_sheet["U44"].value = fishery.fui_w
    fishery_sheet["X44"].value = fishery.total_catch_yr_start
    fishery_sheet["Z44"].value = fishery.total_catch_yr_wo
    fishery_sheet["AB44"].value = fishery.total_catch_yr_w

    fishery_sheet["H57"].value = fishery.ice_preserved_catch_pc_start
    fishery_sheet["J57"].value = fishery.ice_preserved_catch_pc_wo
    fishery_sheet["L57"].value = fishery.ice_preserved_catch_pc_w

    result = results[0]

    sheet_wo = float(fishery_sheet["AE61"].value)
    sheet_w = float(fishery_sheet["AG61"].value)
    sheet_balance = float(fishery_sheet["AI61"].value)

    try:
        assert math.isclose(result.total_w, sheet_w, rel_tol=0.01)
        assert math.isclose(result.total_wo, sheet_wo, rel_tol=0.01)
        assert math.isclose(result.balance, sheet_balance, rel_tol=0.01)
        passed_lg_fisheries += 1
    except AssertionError as e:
        print("Results do not match the Excel")
        print(f"total_w: {result.total_w}, total_wo: {result.total_wo}")
        print(f"balance: {result.balance}")
        print(f"sheet_w: {sheet_w}, sheet_wo: {sheet_wo}")
        print(f"sheet_balance: {sheet_balance}")


print(f"\nTotal Tested Small Fisheries: {total_fisheries}")
print(f"Passed Tests: {passed_fisheries}\n")

print(f"\nTotal Tested Large Fisheries: {total_lg_fisheries}")
print(f"Passed Tests: {passed_lg_fisheries}\n")
