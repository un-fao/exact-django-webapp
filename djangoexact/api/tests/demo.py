import json

import factory.fuzzy as fuzzy
from api.calculators import *
from api.models import *
from api.models import CustomUser as User
from ipcc.models import SoilOrganicCarbon

from .factories import *

##### Test Suite for COP28 Demo #####

u = User.objects.get(username="admin")

country = Country.objects.get(name="Lao People's Democratic Republic")
climate = Climate.objects.get(name="Tropical")
moisture = Moisture.objects.get(name="Moist")
soil_type = SoilType.objects.get(name="High Activity Clay")
gw_potential = GlobalWarmingPotential.objects.get(name="100 yr AR5 w/out CC feedback")
implementation_years = 7
capitalization_years = 10

for i in range(10):
    print(f"\n\n\n##### START TEST {i+1} #####\n\n\n")

    p = ProjectFactory.create(name=fuzzy.FuzzyText(length=12), user=u, country=country, climate=climate, moisture=moisture, soil_type=soil_type, gw_potential=gw_potential, implementation_years=implementation_years, capitalization_years=capitalization_years)
    a = ActivityFactory.create(name="Activity for demo", project=p)

    module_type_start = ModuleType.objects.get(name="Grassland")
    module_type_w = ModuleType.objects.get(name="Annual Cropland")
    module_type_wo = ModuleType.objects.get(name="Grassland")
    area = 150

    luc = LandUseChangeFactory.create(activity=a, module_type_start=module_type_start, module_type_w=module_type_w, module_type_wo=module_type_wo, area=area)

    grassland = GrasslandFactory.create(activity=a, land_use_change=luc)

    annual_cropland = AnnualCroppingFactory.create(activity=a, land_use_change=luc)

    print("##### Test Suite for COP28 Demo #####\n\n")

    print("##### PARAMETERS #####\n\n")

    print(f"Hectars: {area}")
    print(f"Country: {country}")
    print(f"Region: {country.region}")
    print(f"Climate: {climate}")
    print(f"Moisture: {moisture}")
    print(f"Soil Type: {soil_type}")
    print(f"Global Warming Potential: {gw_potential}")
    print(f"Implementation Years: {implementation_years}")
    print(f"Capitalization Years: {capitalization_years}")

    print(f"Project: {p}")
    print(f"Activity: {a}")
    print(f"Land Use Change: {luc}")
    print(f"Grassland: {grassland}")
    print(f"Annual Cropland: {annual_cropland}")

    print("\n\n##### END PARAMETERS #####\n\n")

    print("##### TEST 1: Land Use Change #####")
    luc_results = CalculatorFactory().calculate_result(luc)
    print(f"Land Use Change Results: {luc_results}\n\n")

    print("##### TEST 2: Grassland #####")
    grassland_results = CalculatorFactory().calculate_result(grassland)
    print(f"Grassland Results: {grassland_results}\n\n")

    print("##### TEST 3: Annual Cropland #####")
    annual_cropland_results = CalculatorFactory().calculate_result(annual_cropland)
    print(f"Annual Cropland Results: {annual_cropland_results}\n\n")

# p.delete()
