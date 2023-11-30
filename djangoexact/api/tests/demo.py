from .factories import *
from api.models import *
from ipcc.models import SoilOrganicCarbon
from api.calculators import *
import json

##### Test Suite for COP28 Demo #####

u = User.objects.get(username="admin")

country = Country.objects.get(name="Lao People's Democratic Republic")
climate = Climate.objects.get(name="Tropical")
moisture = Moisture.objects.get(name="Moist")
soil_type = SoilType.objects.get(name="High Activity Clay")
gw_potential = GlobalWarmingPotential.objects.get(name="100 yr AR5 w/out CC feedback")
implementation_years = 7
capitalization_years = 10

p = ProjectFactory.build(name="Testsuite project 3", user=u, country=country, climate=climate, moisture=moisture, soil_type=soil_type, gw_potential=gw_potential, implementation_years=implementation_years, capitalization_years=capitalization_years)

a = ActivityFactory.build(name="Activity for demo", project=p)

module_type_start = ModuleType.objects.get(name="Grassland")
module_type_w = ModuleType.objects.get(name="Annual Cropland")
module_type_wo = ModuleType.objects.get(name="Grassland")
area = 150

luc = LandUseChangeFactory.build(activity=a, module_type_start=module_type_start, module_type_w=module_type_w, module_type_wo=module_type_wo, area=area)

grassland = GrasslandFactory.build(
    activity=a,
    land_use_change=luc,
    grassland_management_type_start=GrasslandManagementType.objects.get(name="High Intensity Grazing"),
    grassland_management_type_w=GrasslandManagementType.objects.get(name="High Intensity Grazing"),
    grassland_management_type_wo=GrasslandManagementType.objects.get(name="Severely Degraded"),
    is_fire_used_start = True,
    is_fire_used_w = True,
    is_fire_used_wo = True,
    fire_periodicity_start = 2,
    fire_periodicity_w = 2,
    fire_periodicity_wo = 2,
    fire_impact_start = 0.2,
    fire_impact_w = 0.2,
    fire_impact_wo = 0.2
)

annual_cropland = AnnualCroppingFactory.build(
    activity=a,
    land_use_change=luc,
    land_use_type_start = LandUseType.objects.get(name="Maize"),
    land_use_type_w = LandUseType.objects.get(name="Maize"),
    land_use_type_wo = LandUseType.objects.get(name="Maize"),
    tillage_management_type_start = TillageManagementType.objects.get(name="Full Tillage"),
    tillage_management_type_w = TillageManagementType.objects.get(name="Full Tillage"),
    tillage_management_type_wo = TillageManagementType.objects.get(name="Full Tillage"),
    organic_input_type_start = OrganicInputType.objects.get(name="High C input, no manure"),
    organic_input_type_w = OrganicInputType.objects.get(name="High C input, no manure"),
    organic_input_type_wo = OrganicInputType.objects.get(name="High C input, no manure"),
    residue_management_type_start = ResidueManagementType.objects.get(name="Retained"),
    residue_management_type_w = ResidueManagementType.objects.get(name="Retained"),
    residue_management_type_wo = ResidueManagementType.objects.get(name="Retained"),
)

p.save()
a.save()
luc.save()
grassland.save()
annual_cropland.save()

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