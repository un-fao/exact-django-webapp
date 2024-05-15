import json
import math
from time import sleep

import factory.fuzzy as fuzzy
import openpyxl as xl
import xlwings as xw
from api.calculators import *
from api.models import *
from api.models import CustomUser as User
from api.serializers import *
from django.test import TestCase
from ipcc.models import *
from openpyxl import load_workbook
from rest_framework.test import APIRequestFactory

from .factories import *

BATCH_SIZE = 1
TEST_SM_FISHERY = False
TEST_LG_FISHERY = False
TEST_ANNUAL_CROPPING = False
TEST_PERENNIAL_CROPPING = False
TEST_LIVESTOCK = False
TEST_GRASSLAND = False
TEST_INPUTS = False
TEST_COASTAL_WETLAND = False
INPUTS_BATCH_SIZE = 3

TEST_ENERGY = False
ENERGY_ELECTRICITY_BATCH_SIZE = 0
ENERGY_FUEL_BATCH_SIZE = 2


def verbose_print(obj):
    for attr, value in obj.__dict__.items():
        print(attr, value)


climates = Climate.objects.all()
moistures = Moisture.objects.all()
countries = Country.objects.all()
soil_types = SoilType.objects.all().exclude(active=False)
gw_potentials = GlobalWarmingPotential.objects.all()
soc_refs = SoilOrganicCarbon.objects.all()

f = APIRequestFactory()

# wbook = xw.Book("EX-ACT_V9.4.1_open[1298].xlsb")

# User Creation
u = User.objects.get(username="admin")


while True:
    try:
        country = random.choice(countries)
        continent = country.region
        climate = random.choice(climates)
        moisture = random.choice(moistures)
        soil_type = random.choice(soil_types)
        gw_potential = GlobalWarmingPotential.objects.get(name="100 yr AR5 w/out CC feedback")
        # socref = SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type)

        # country = Country.objects.get(name="Egypt")
        # region = country.region
        # climate = Climate.objects.get(name="Tropical")
        # moisture = Moisture.objects.get(name="Dry")
        # soil_type = SoilType.objects.get(name="Sandy")
        socref = SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type)

        if socref.value is None:
            # TODO: Define behaviour for when socref is None (either input T2 or what?)
            print("socref is None")
            raise Exception
        break
    except Exception as e:
        print(e)
        continue


# Project Creation
p: ProjectFactory = ProjectFactory.create(
    user=u,
    climate=climate,
    moisture=moisture,
    country=country,
    gw_potential=gw_potential,
    soil_type=soil_type,
)

print(f"Country: {country}")
print(f"Continent: {country.region}")
print(f"Climate: {climate}")
print(f"Moisture: {moisture}")
print(f"Soil Type: {soil_type}")
print(f"GW Potential: {gw_potential}")
print(f"Soil Organic Carbon: {socref}")
print(f"Implementation years: {p.implementation_years}")
print(f"Capitalization years: {p.capitalization_years}")

UserProjectGroup.objects.create(user=u, project=p, group=Group.objects.get(name="Admin"))

print(f"Project: {p}")

# Spreadeheet setup
# ds = wbook.sheets["1.Description"]
# ds["Q8"].value = p.continent.name
# ds["Q9"].value = p.country.name
# ds["Q10"].value = p.climate.name
# ds["Q11"].value = p.moisture.name
# ds["Q12"].value = p.soil_type.name + " soils"
# ds["T13"].value = p.implementation_duration_yrs
# ds["T14"].value = p.capitalization_duration_yrs
# sleep(1)

# Activity Creation
a: Activity = ActivityFactory.create(project=p)
print(f"Activity: {a}")

# Fishery Sheet
# fishery_sheet = wbook.sheets["8. Fisheries and aquaculture"]

# Cropland Testing
# cropland_sheet = wbook.sheets["3. Cropland"]

if TEST_SM_FISHERY:
    # Small Fishery Creation
    sm_fisheries = SmallFisheryFactory.create_batch(BATCH_SIZE, activity=a)
    total_fisheries = sm_fisheries.__len__()
    passed_fisheries = 0

    a.module_types.add(ModuleType.objects.get(name="Small Fishery"))
    a.save()

    # Small Fishery Testing
    print("Testing SmallFishery...")
    for i, small_fishery in enumerate(sm_fisheries):
        # print(f"\n\n Testing SmallFishery {i+1}...")
        # print("-----------------------------------")

        small_fishery: SmallFishery

        print(small_fishery)

        print(f"Type of fishery: {small_fishery.fishery_type}")

        print(f"Type of gear START: {small_fishery.gear_type_start}")
        print(f"Refrigerant START: {small_fishery.refrigerant_pc_start}")

        print(f"Type of gear WO: {small_fishery.gear_type_wo}")
        print(f"Refrigerant WO: {small_fishery.refrigerant_pc_wo}")

        print(f"Type of gear W: {small_fishery.gear_type_w}")
        print(f"Refrigerant W: {small_fishery.refrigerant_pc_w}")

        print(f"FUI START: {small_fishery.fui_start}")
        print(f"FUI WO: {small_fishery.fui_wo}")
        print(f"FUI W: {small_fishery.fui_w}")

        print(f"Total Catch START: {small_fishery.total_catch_yr_start}")
        print(f"Total Catch WO: {small_fishery.total_catch_yr_wo}")
        print(f"Total Catch W: {small_fishery.total_catch_yr_w}")

        print(f"Ice Preserved Catch START: {small_fishery.ice_preserved_catch_pc_start}")
        print(f"Ice Preserved Catch WO: {small_fishery.ice_preserved_catch_pc_wo}")
        print(f"Ice Preserved Catch W: {small_fishery.ice_preserved_catch_pc_w}")

        try:
            results = CalculatorFactory().calculate_result(small_fishery)
            print(results)
            passed_fisheries += 1

        # fishery_sheet["C18"].value = fishery.fishery_type.name
        # fishery_sheet["E18"].value = fishery.gear_type_start.name
        # fishery_sheet["H18"].value = fishery.refrigerant_pc_start
        # fishery_sheet["J18"].value = fishery.refrigerant_pc_wo
        # fishery_sheet["L18"].value = fishery.refrigerant_pc_w
        # fishery_sheet["R18"].value = fishery.fui_start
        # fishery_sheet["T18"].value = fishery.fui_wo
        # fishery_sheet["U18"].value = fishery.fui_w
        # fishery_sheet["X18"].value = fishery.total_catch_yr_start
        # fishery_sheet["Z18"].value = fishery.total_catch_yr_wo
        # fishery_sheet["AB18"].value = fishery.total_catch_yr_w

        # fishery_sheet["H26"].value = fishery.ice_preserved_catch_pc_start
        # fishery_sheet["J26"].value = fishery.ice_preserved_catch_pc_wo
        # fishery_sheet["L26"].value = fishery.ice_preserved_catch_pc_w

        # result = results[0]

        # sheet_wo = float(fishery_sheet["AE30"].value)
        # sheet_w = float(fishery_sheet["AG30"].value)
        # sheet_balance = float(fishery_sheet["AI30"].value)

        # assert math.isclose(result.total_w, sheet_w, rel_tol=0.02)
        # assert math.isclose(result.total_wo, sheet_wo, rel_tol=0.02)
        # assert math.isclose(result.balance, sheet_balance, rel_tol=0.02)
        except Exception as e:
            # print("Results do not match the Excel")
            # print(f"total_w: {result.total_w}, total_wo: {result.total_wo}")
            # print(f"balance: {result.balance}")
            # print(f"sheet_w: {sheet_w}, sheet_wo: {sheet_wo}")
            # print(f"sheet_balance: {sheet_balance}")
            pass

    print(f"\nTotal Tested Small Fisheries: {total_fisheries}")
    print(f"Passed Tests: {passed_fisheries}\n\n")

if TEST_LG_FISHERY:
    # Large Fishery Creation
    lg_fisheries = LargeFisheryFactory.build_batch(BATCH_SIZE, activity=a)
    total_lg_fisheries = lg_fisheries.__len__()
    passed_lg_fisheries = 0

    a.module_types.add(ModuleType.objects.get(name="Large Fishery"))
    a.save()

    # Large Fishery Testing
    print("Testing LargeFishery...")
    for i, lg_fishery in enumerate(lg_fisheries):
        # print(f"\n\n Testing LargeFishery {i+1}...")
        # print("-----------------------------------")
        # verbose_print(fishery)

        lg_fishery: LargeFishery

        print(f"Type of fishery: {lg_fishery.fish_type}")

        print(f"Type of gear START: {lg_fishery.gear_type_start}")
        print(f"Refrigerant START: {lg_fishery.refrigerant_pc_start}")

        print(f"Type of gear WO: {lg_fishery.gear_type_wo}")
        print(f"Refrigerant WO: {lg_fishery.refrigerant_pc_wo}")

        print(f"Type of gear W: {lg_fishery.gear_type_w}")
        print(f"Refrigerant W: {lg_fishery.refrigerant_pc_w}")

        print(f"FUI START: {lg_fishery.fui_start}")
        print(f"FUI WO: {lg_fishery.fui_wo}")
        print(f"FUI W: {lg_fishery.fui_w}")

        print(f"Total Catch START: {lg_fishery.total_catch_yr_start}")
        print(f"Total Catch WO: {lg_fishery.total_catch_yr_wo}")
        print(f"Total Catch W: {lg_fishery.total_catch_yr_w}")

        print(f"Ice Preserved Catch START: {lg_fishery.ice_preserved_catch_pc_start}")
        print(f"Ice Preserved Catch WO: {lg_fishery.ice_preserved_catch_pc_wo}")
        print(f"Ice Preserved Catch W: {lg_fishery.ice_preserved_catch_pc_w}")

        results: Result = CalculatorFactory().calculate_result(lg_fishery)
        # print(results)

        print(results)

        # fishery_sheet["C44"].value = fishery.fish_type.name
        # fishery_sheet["E44"].value = fishery.gear_type_start.name
        # fishery_sheet["H44"].value = fishery.refrigerant_pc_start
        # fishery_sheet["J44"].value = fishery.refrigerant_pc_wo
        # fishery_sheet["L44"].value = fishery.refrigerant_pc_w
        # fishery_sheet["R44"].value = fishery.fui_start
        # fishery_sheet["T44"].value = fishery.fui_wo
        # fishery_sheet["U44"].value = fishery.fui_w
        # fishery_sheet["X44"].value = fishery.total_catch_yr_start
        # fishery_sheet["Z44"].value = fishery.total_catch_yr_wo
        # fishery_sheet["AB44"].value = fishery.total_catch_yr_w

        # fishery_sheet["H57"].value = fishery.ice_preserved_catch_pc_start
        # fishery_sheet["J57"].value = fishery.ice_preserved_catch_pc_wo
        # fishery_sheet["L57"].value = fishery.ice_preserved_catch_pc_w

        # sheet_wo = float(fishery_sheet["AE61"].value)
        # sheet_w = float(fishery_sheet["AG61"].value)
        # sheet_balance = float(fishery_sheet["AI61"].value)

        try:
            # assert math.isclose(result.total_w, sheet_w, rel_tol=0.01)
            # assert math.isclose(result.total_wo, sheet_wo, rel_tol=0.01)
            # assert math.isclose(result.balance, sheet_balance, rel_tol=0.01)
            passed_lg_fisheries += 1
        except AssertionError as e:
            print("Results do not match the Excel")
            # print(f"total_w: {result.total_w}, total_wo: {result.total_wo}")
            # print(f"balance: {result.balance}")
            # print(f"sheet_w: {sheet_w}, sheet_wo: {sheet_wo}")
            # print(f"sheet_balance: {sheet_balance}")

    print(f"\nTotal Tested Large Fisheries: {total_lg_fisheries}")
    print(f"Passed Tests: {passed_lg_fisheries}\n\n")

if TEST_ANNUAL_CROPPING:
    annual_croppings = AnnualCroppingFactory.create_batch(BATCH_SIZE, activity=a)
    total_croplands = annual_croppings.__len__()
    passed_croplands = 0

    a.module_types.add(ModuleType.objects.get(name="Annual Cropping"))
    a.save()

    print("Testing AnnualCropping...")
    for i, annual_cropping in enumerate(annual_croppings):
        # print(f"\n\nTesting AnnualCropping {i+1}...")
        # print("-----------------------------------")
        # print(get_module_serializer(AnnualCropping)(annual_cropping).data)

        annual_cropping: AnnualCropping

        print(f"Land Use Type START: {annual_cropping.land_use_type_start}")
        print(f"Land Use Type WO: {annual_cropping.land_use_type_wo}")
        print(f"Land Use Type W: {annual_cropping.land_use_type_w}")

        print(f"Tillage Management Type START: {annual_cropping.tillage_management_type_start}")
        print(f"Tillage Management Type WO: {annual_cropping.tillage_management_type_wo}")
        print(f"Tillage Management Type W: {annual_cropping.tillage_management_type_w}")

        print(f"Organic Input Type START: {annual_cropping.organic_input_type_start}")
        print(f"Organic Input Type WO: {annual_cropping.organic_input_type_wo}")
        print(f"Organic Input Type W: {annual_cropping.organic_input_type_w}")

        print(f"Residue Management Type START: {annual_cropping.residue_management_type_start}")
        print(f"Residue Management Type WO: {annual_cropping.residue_management_type_wo}")
        print(f"Residue Management Type W: {annual_cropping.residue_management_type_w}")

        print(f"Crop Yield START: {annual_cropping.crop_yield_start}")
        print(f"Crop Yield WO: {annual_cropping.crop_yield_wo}")
        print(f"Crop Yield W: {annual_cropping.crop_yield_w}")

        try:
            results: Result = CalculatorFactory().calculate_result(annual_cropping)

            print(results)

            # cropland_sheet["E25"].value = (
            #     annual_cropping.crop_type_start.name
            #     if annual_cropping.crop_type_start.name not in ["Beans", "Pulses"]
            #     else "Beans & pulses"
            # )
            # cropland_sheet["G25"].value = annual_cropping.tillage_management_type_start.name
            # cropland_sheet["I25"].value = annual_cropping.organic_input_type_start.name
            # cropland_sheet["K25"].value = annual_cropping.residue_management_type_start.name
            # cropland_sheet["M25"].value = annual_cropping.crop_yield_start
            # cropland_sheet["Q25"].value = annual_cropping.ha_start
            # cropland_sheet["R25"].value = 0
            # cropland_sheet["T25"].value = 0

            # cropland_sheet["E26"].value = (
            #     annual_cropping.crop_type_wo.name
            #     if annual_cropping.crop_type_wo.name not in ["Beans", "Pulses"]
            #     else "Beans & pulses"
            # )
            # cropland_sheet["G26"].value = annual_cropping.tillage_management_type_wo.name
            # cropland_sheet["I26"].value = annual_cropping.organic_input_type_wo.name
            # cropland_sheet["K26"].value = annual_cropping.residue_management_type_wo.name
            # cropland_sheet["M26"].value = annual_cropping.crop_yield_wo
            # cropland_sheet["Q26"].value = 0
            # cropland_sheet["R26"].value = annual_cropping.ha_wo
            # cropland_sheet["T26"].value = 0

            # cropland_sheet["E27"].value = (
            #     annual_cropping.crop_type_w.name
            #     if annual_cropping.crop_type_w.name not in ["Beans", "Pulses"]
            #     else "Beans & pulses"
            # )
            # cropland_sheet["G27"].value = annual_cropping.tillage_management_type_w.name
            # cropland_sheet["I27"].value = annual_cropping.organic_input_type_w.name
            # cropland_sheet["K27"].value = annual_cropping.residue_management_type_w.name
            # cropland_sheet["M27"].value = annual_cropping.crop_yield_w
            # cropland_sheet["Q27"].value = 0
            # cropland_sheet["R27"].value = 0
            # cropland_sheet["T27"].value = annual_cropping.ha_w

            # sheet_wo = float(cropland_sheet["W37"].value)
            # sheet_w = float(cropland_sheet["X37"].value)
            # sheet_balance = float(cropland_sheet["Z37"].value)
            # sleep(2)

            passed_croplands += 1

            # assert math.isclose(results.total_wo, sheet_wo, rel_tol=0.05)
            # assert math.isclose(results.total_w, sheet_w, rel_tol=0.05)
            # assert math.isclose(results.balance, sheet_balance, rel_tol=0.05)
        except AssertionError as e:
            print("Results do not match the Excel")
            # print(f"total_w: {results.total_w}, total_wo: {results.total_wo}")
            # print(f"balance: {results.balance}")
            # print(f"sheet_w: {sheet_w}, sheet_wo: {sheet_wo}")
            # print(f"sheet_balance: {sheet_balance}")
        except Exception as e:
            print(e)

    print(f"\nTotal Tested Croplands: {total_croplands}")
    print(f"Passed Tests: {passed_croplands}\n\n")

if TEST_PERENNIAL_CROPPING:
    perennials = PerennialCroppingFactory.create_batch(BATCH_SIZE, activity=a)
    a.module_types.add(ModuleType.objects.get(name="Perennial Cropping"))
    a.save()

    total_perennials = perennials.__len__()
    passed_perennials = 0

    print("Testing Perennial...")
    # for i, perennial in enumerate(perennials):

    for i, perennial in enumerate(perennials):
        print(f"\n\nTesting Perennial {i+1}...")
        print("-----------------------------------")

        perennial: PerennialCropping

        print("\n")

        print(f"Land Use Type START: {perennial.land_use_type_start}")
        print(f"Land Use Type WO: {perennial.land_use_type_wo}")
        print(f"Land Use Type W: {perennial.land_use_type_w}")

        print("\n")

        print(f"Tillage Management Type START: {perennial.tillage_management_type_start}")
        print(f"Tillage Management Type WO: {perennial.tillage_management_type_wo}")
        print(f"Tillage Management Type W: {perennial.tillage_management_type_w}")

        print("\n")

        print(f"Organic Input Type START: {perennial.organic_input_type_start}")
        print(f"Organic Input Type WO: {perennial.organic_input_type_wo}")
        print(f"Organic Input Type W: {perennial.organic_input_type_w}")

        print("\n")

        print(f"Is Biomass Burned START: {perennial.is_biomass_burned_start}")
        print(f"Is Biomass Burned WO: {perennial.is_biomass_burned_wo}")
        print(f"Is Biomass Burned W: {perennial.is_biomass_burned_w}")

        print("\n")

        print(f"Crop Yield START: {perennial.crop_yield_start}")
        print(f"Crop Yield WO: {perennial.crop_yield_wo}")
        print(f"Crop Yield W: {perennial.crop_yield_w}")

        print("\n\n")

        try:
            results = CalculatorFactory().calculate_result(perennial)

            print(json.dumps({"math_results_w": f"{results[0]:,f}", "math_results_wo": f"{results[1]:,f}", "math_results_balance": f"{results[2]:,f}"}, indent=4))

            passed_perennials += 1

        except Exception as e:
            print(e)

if TEST_LIVESTOCK:
    # NOTE: Comparison with excel results is impossible because the module changed too much
    # TODO: Missing data for Deer, Llamas And Alpacas, Ostrich LivestockManureEF CH4 and all N2Os. All data is 0, for now

    livestock = LivestockFactory.create_batch(BATCH_SIZE, activity=a)

    a.module_types.add(ModuleType.objects.get(name="Livestock"))
    a.save()

    total_livestocks = livestock.__len__()
    passed_livestocks = 0

    print("Testing module...")
    for i, livestock in enumerate(livestock):
        print(f"\n\nTesting module {i+1}...")
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

if TEST_GRASSLAND:
    grassland = GrasslandFactory.build_batch(BATCH_SIZE, activity=a)

    a.module_types.add(ModuleType.objects.get(name="Grassland"))
    a.save()

    total_grasslands = grassland.__len__()
    passed_grasslands = 0

    print("Testing module...")
    for i, grassland in enumerate(grassland):
        # print(f"\n\nTesting module {i+1}...")
        # print("-----------------------------------")

        results = CalculatorFactory().calculate_result(grassland)
        # print(results)

        passed_grasslands += 1

    print(f"\nTotal Tested Grasslands: {total_grasslands}")
    print(f"Passed Tests: {passed_grasslands}\n\n")

if TEST_INPUTS:
    inputs = InputFactory.create_batch(BATCH_SIZE, activity=a)

    a.module_types.add(ModuleType.objects.get(name="Inputs"))
    a.save()

    total_inputs = inputs.__len__()
    passed_inputs = 0

    print("Testing module...")
    for i, input in enumerate(inputs):
        print(f"\n\nTesting module {i+1}...")
        print("-----------------------------------")

        for i in range(INPUTS_BATCH_SIZE):
            input_entry = InputEntryFactory.create(parent=input)

            log.debug(f"Input Entry n. {i+1}")
            log.debug("-----------------------------------")

            log.debug("\n")

            log.debug(f"Input Type: {input_entry.input_type}")

            log.debug(f"Value start: {input_entry.value_start:,f}")
            log.debug(f"Value wo: {input_entry.value_wo:,f}")
            log.debug(f"Value w: {input_entry.value_w:,f}")

            log.debug("\n")

        results = CalculatorFactory().calculate_result(input)

        log.debug("Total Results")
        log.debug("-----------------------------------")
        log.debug("\n")
        log.debug(json.dumps({"math_results_w": f"{results[0]:,f}", "math_results_wo": f"{results[1]:,f}", "math_results_balance": f"{results[2]:,f}"}, indent=4))

        passed_inputs += 1

    print(f"\nTotal Tested Inputs: {total_inputs}")
    print(f"Passed Tests: {passed_inputs}\n\n")

if TEST_ENERGY:
    energy = EnergyFactory.create_batch(BATCH_SIZE, activity=a)

    a.module_types.add(ModuleType.objects.get(name="Energy"))
    a.save()

    total_energy = energy.__len__()
    passed_energy = 0

    print("Testing module...")
    for i, energy in enumerate(energy):
        print(f"\n\nTesting module {i+1}...")
        print("-----------------------------------")

        for i in range(ENERGY_ELECTRICITY_BATCH_SIZE):
            electricity_entry: Electricity = ElectricityFactory.create(parent=energy)

            log.debug(f"Electricity Entry n. {i+1}")
            log.debug("-----------------------------------")

            log.debug("\n")

            log.debug(f"Country: {electricity_entry.country}")
            log.debug(f"MWH start: {electricity_entry.mwh_start:,f}")
            log.debug(f"MWH wo: {electricity_entry.mwh_wo:,f}")
            log.debug(f"MWH w: {electricity_entry.mwh_w:,f}")
            log.debug(f"MWH Renewables start: {electricity_entry.mwh_renewables_start:,f}")
            log.debug(f"MWH Renewables wo: {electricity_entry.mwh_renewables_wo:,f}")
            log.debug(f"MWH Renewables w: {electricity_entry.mwh_renewables_w:,f}")

            log.debug("\n")

        for i in range(ENERGY_FUEL_BATCH_SIZE):
            fuel_entry: Fuel = FuelFactory.create(parent=energy)

            log.debug(f"Fuel Entry n. {i+1}")
            log.debug("-----------------------------------")

            log.debug("\n")

            log.debug(f"Fuel Type: {fuel_entry.fuel_type}")
            log.debug(f"Fuel consumption start: {fuel_entry.fuel_consumption_start:,f}")
            log.debug(f"Fuel consumption wo: {fuel_entry.fuel_consumption_wo:,f}")
            log.debug(f"Fuel consumption w: {fuel_entry.fuel_consumption_w:,f}")

            log.debug("\n")

        results = CalculatorFactory().calculate_result(energy)

        log.debug("Total Results")
        log.debug("-----------------------------------")
        log.debug("")
        log.debug(json.dumps({"math_results_w": f"{results[0]:,f}", "math_results_wo": f"{results[1]:,f}", "math_results_balance": f"{results[2]:,f}"}, indent=4))

        passed_energy += 1

    print(f"\nTotal Tested Energy: {total_energy}")
    print(f"Passed Tests: {passed_energy}\n\n")

if TEST_COASTAL_WETLAND:
    pass

    coastals: list[CoastalWetland] = CoastalWetlandFactory.create_batch(BATCH_SIZE, activity=a)
    a.module_types.add(ModuleType.objects.get(name="Coastal Wetland"))
    a.save()

    total_coastals = coastals.__len__()
    passed_coastals = 0

    print("Testing module...")

    for i, coastal in enumerate(coastals):
        print(f"\n\nTesting module {i+1}...")
        print("-----------------------------------")

        """
        drained_area_excavated_start = factory.fuzzy.FuzzyFloat(0, area_under_drainage_start)
        drained_area_excavated_w = factory.fuzzy.FuzzyFloat(0, area_under_drainage_w)
        drained_area_excavated_wo = factory.fuzzy.FuzzyFloat(0, area_under_drainage_wo)

        area_not_drained_or_rewetted_start = factory.fuzzy.FuzzyFloat(0, ha_start - area_under_drainage_start)
        area_not_drained_or_rewetted_w = factory.fuzzy.FuzzyFloat(0, ha_w - area_under_drainage_w)
        area_not_drained_or_rewetted_wo = factory.fuzzy.FuzzyFloat(0, ha_wo - area_under_drainage_wo)

        area_w_restored_vegetation_start = factory.fuzzy.FuzzyFloat(0, area_not_drained_or_rewetted_start)
        area_w_restored_vegetation_w = factory.fuzzy.FuzzyFloat(0, area_not_drained_or_rewetted_w)
        area_w_restored_vegetation_wo = factory.fuzzy.FuzzyFloat(0, area_not_drained_or_rewetted_wo)
        """

        coastal.drained_area_excavated_start = 0
        coastal.drained_area_excavated_w = random.uniform(0, coastal.area_under_drainage_w)
        coastal.drained_area_excavated_wo = random.uniform(0, coastal.area_under_drainage_wo)

        coastal.area_not_drained_or_rewetted_start = coastal.area - coastal.area_under_drainage_start
        coastal.area_not_drained_or_rewetted_w = coastal.area - coastal.area_under_drainage_w
        coastal.area_not_drained_or_rewetted_wo = coastal.area - coastal.area_under_drainage_wo

        coastal.area_w_restored_vegetation_start = random.uniform(0, coastal.area_not_drained_or_rewetted_start)
        coastal.area_w_restored_vegetation_w = random.uniform(0, coastal.area_not_drained_or_rewetted_w)
        coastal.area_w_restored_vegetation_wo = random.uniform(0, coastal.area_not_drained_or_rewetted_wo)

        coastal.save()

        print(f"Vegetation Type: {coastal.land_use_type}")

        print(f"Area: {coastal.area:,f}")

        print(f"Area under drainage START: {coastal.area_under_drainage_start:,f}")
        print(f"Area under drainage WO: {coastal.area_under_drainage_wo:,f}")
        print(f"Area under drainage W: {coastal.area_under_drainage_w:,f}")

        print(f"Drained Area Excavated START: {coastal.drained_area_excavated_start:,f}")
        print(f"Drained Area Excavated WO: {coastal.drained_area_excavated_wo:,f}")
        print(f"Drained Area Excavated W: {coastal.drained_area_excavated_w:,f}")

        print(f"Area not drained or rewetted START: {coastal.area_not_drained_or_rewetted_start:,f}")
        print(f"Area not drained or rewetted WO: {coastal.area_not_drained_or_rewetted_wo:,f}")
        print(f"Area not drained or rewetted W: {coastal.area_not_drained_or_rewetted_w:,f}")

        print(f"Area w restored vegetation START: {coastal.area_w_restored_vegetation_start:,f}")
        print(f"Area w restored vegetation WO: {coastal.area_w_restored_vegetation_wo:,f}")
        print(f"Area w restored vegetation W: {coastal.area_w_restored_vegetation_w:,f}")

        results = CalculatorFactory().calculate_result(coastal)

        print(json.dumps({"math_results_w": f"{results[0]:,f}", "math_results_wo": f"{results[1]:,f}", "math_results_balance": f"{results[2]:,f}"}, indent=4))

        passed_coastals += 1
