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
from .serializers import *

BATCH_SIZE = 5
TEST_SM_FISHERY = False
TEST_LG_FISHERY = False
TEST_ANNUAL_CROPPING = True
TEST_PERENNIAL_CROPPING = False
TEST_LIVESTOCK = False


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

wbook = xw.Book("EX-ACT_V9.4.1_open[1298].xlsb")

# User Creation
u = User.objects.get(username="admin")


while True:
    try:
        country = random.choice(countries)
        continent = country.continent
        climate = random.choice(climates)
        moisture = random.choice(moistures)
        soil_type = random.choice(soil_types)
        gw_potential = GlobalWarmingPotential.objects.get(name="100 yr AR5 w/out CC feedback")
        socref = SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type)

        if socref.value is None:
            # TODO: Define behaviour for when socref is None (either input T2 or what?)
            raise Exception
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

print(WriteProjectSerializer(p).data)

# Spreadeheet setup
ds = wbook.sheets["1.Description"]
ds["Q8"].value = p.continent.name
ds["Q9"].value = p.country.name
ds["Q10"].value = p.climate.name
ds["Q11"].value = p.moisture.name
ds["Q12"].value = p.soil_type.name + " soils"
ds["T13"].value = p.implementation_duration_yrs
ds["T14"].value = p.capitalization_duration_yrs
sleep(1)

# Activity Creation
a = ActivityFactory.create(project=p, user=u)
print(f"Activity: {a}")

# Fishery Sheet
fishery_sheet = wbook.sheets["8. Fisheries and aquaculture"]

# Cropland Testing
cropland_sheet = wbook.sheets["3. Cropland"]

if TEST_SM_FISHERY:
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

    print(f"\nTotal Tested Small Fisheries: {total_fisheries}")
    print(f"Passed Tests: {passed_fisheries}\n\n")

if TEST_LG_FISHERY:
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

    print(f"\nTotal Tested Large Fisheries: {total_lg_fisheries}")
    print(f"Passed Tests: {passed_lg_fisheries}\n\n")

if TEST_ANNUAL_CROPPING:
    annual_croppings = AnnualCroppingFactory.create_batch(BATCH_SIZE, activity=a)
    total_croplands = annual_croppings.__len__()
    passed_croplands = 0

    print("Testing Cropland...")
    for i, annual_cropping in enumerate(annual_croppings):
        print(f"\n\nTesting AnnualCropping {i+1}...")
        print("-----------------------------------")
        print(get_module_serializer(AnnualCropping)(annual_cropping).data)

        results = CalculatorFactory().calculate_result(annual_cropping)

        cropland_sheet["E25"].value = (
            annual_cropping.crop_type_start.name
            if annual_cropping.crop_type_start.name not in ["Beans", "Pulses"]
            else "Beans & pulses"
        )
        cropland_sheet["G25"].value = annual_cropping.tillage_management_type_start.name
        cropland_sheet["I25"].value = annual_cropping.organic_input_type_start.name
        cropland_sheet["K25"].value = annual_cropping.residue_management_type_start.name
        cropland_sheet["M25"].value = annual_cropping.crop_yield_start
        cropland_sheet["Q25"].value = annual_cropping.ha_start
        cropland_sheet["R25"].value = 0
        cropland_sheet["T25"].value = 0

        cropland_sheet["E26"].value = (
            annual_cropping.crop_type_wo.name
            if annual_cropping.crop_type_wo.name not in ["Beans", "Pulses"]
            else "Beans & pulses"
        )
        cropland_sheet["G26"].value = annual_cropping.tillage_management_type_wo.name
        cropland_sheet["I26"].value = annual_cropping.organic_input_type_wo.name
        cropland_sheet["K26"].value = annual_cropping.residue_management_type_wo.name
        cropland_sheet["M26"].value = annual_cropping.crop_yield_wo
        cropland_sheet["Q26"].value = 0
        cropland_sheet["R26"].value = annual_cropping.ha_wo
        cropland_sheet["T26"].value = 0

        cropland_sheet["E27"].value = (
            annual_cropping.crop_type_w.name
            if annual_cropping.crop_type_w.name not in ["Beans", "Pulses"]
            else "Beans & pulses"
        )
        cropland_sheet["G27"].value = annual_cropping.tillage_management_type_w.name
        cropland_sheet["I27"].value = annual_cropping.organic_input_type_w.name
        cropland_sheet["K27"].value = annual_cropping.residue_management_type_w.name
        cropland_sheet["M27"].value = annual_cropping.crop_yield_w
        cropland_sheet["Q27"].value = 0
        cropland_sheet["R27"].value = 0
        cropland_sheet["T27"].value = annual_cropping.ha_w

        sheet_wo = float(cropland_sheet["W37"].value)
        sheet_w = float(cropland_sheet["X37"].value)
        sheet_balance = float(cropland_sheet["Z37"].value)
        sleep(2)

        try:
            assert math.isclose(results.total_wo, sheet_wo, rel_tol=0.05)
            assert math.isclose(results.total_w, sheet_w, rel_tol=0.05)
            assert math.isclose(results.balance, sheet_balance, rel_tol=0.05)
            passed_croplands += 1
        except AssertionError as e:
            print("Results do not match the Excel")
            print(f"total_w: {results.total_w}, total_wo: {results.total_wo}")
            print(f"balance: {results.balance}")
            print(f"sheet_w: {sheet_w}, sheet_wo: {sheet_wo}")
            print(f"sheet_balance: {sheet_balance}")

    print(f"\nTotal Tested Croplands: {total_croplands}")
    print(f"Passed Tests: {passed_croplands}\n\n")

if TEST_PERENNIAL_CROPPING:
    perennials = PerennialCroppingFactory.create_batch(BATCH_SIZE, activity=a)

    total_perennials = perennials.__len__()
    passed_perennials = 0

    print("Testing Perennial...")
    # for i, perennial in enumerate(perennials):

if TEST_LIVESTOCK:
    # NOTE: Comparison with excel results is impossible because the module changed too much
    # TODO: Missing data for Deer, Llamas And Alpacas, Ostrich LivestockManureEF CH4 and all N2Os. All data is 0, for now

    livestock = LivestockFactory.create_batch(BATCH_SIZE, activity=a)

    total_livestocks = livestock.__len__()
    passed_livestocks = 0

    print("Testing Livestock...")
    for i, livestock in enumerate(livestock):
        print(f"\n\nTesting Livestock {i+1}...")
        print("-----------------------------------")

        print(livestock.id)

        print(livestock.livestock_category_type_start)
        print(livestock.livestock_category_type_w)
        print(livestock.livestock_category_type_wo)

        print(livestock.livestock_production_type_start)
        print(livestock.livestock_production_type_w)
        print(livestock.livestock_production_type_wo)

        results = CalculatorFactory().calculate_result(livestock)

        print(f"total_w: {results.total_w}, total_wo: {results.total_wo}")
        print(f"balance: {results.balance}")

        passed_livestocks += 1

    print(f"\nTotal Tested Livestocks: {total_livestocks}")
    print(f"Passed Tests: {passed_livestocks}\n\n")
