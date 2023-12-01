from django.test import TestCase
from api.models import *
from ipcc.models import GlobalWarmingPotential
from rest_framework.test import APIRequestFactory, force_authenticate
from api.views import *
from rest_framework.test import APITestCase
from rest_framework.test import APIClient
import json
import factory.fuzzy as fuzzy
import logging

client = APIClient()

u = User.objects.get(username="admin")

client.force_authenticate(user=u)

country = Country.objects.get(name="Lao People's Democratic Republic")
climate = Climate.objects.get(name="Tropical")
moisture = Moisture.objects.get(name="Moist")
soil_type = SoilType.objects.get(name="High Activity Clay")
gw_potential = GlobalWarmingPotential.objects.get(name="100 yr AR5 w/out CC feedback")
implementation_years = 7
capitalization_years = 10

# Generate random name
post_project = {
    "name": fuzzy.FuzzyText().fuzz(),
    "country": country.id,
    "climate": climate.id,
    "moisture": moisture.id,
    "soil_type": soil_type.id,
    "gw_potential": gw_potential.id,
    "implementation_years": implementation_years,
    "capitalization_years": capitalization_years
}

project_response = client.post('/api/projects/', json.dumps(post_project), content_type='application/json')
print(project_response)

post_activity = {
    "name": "Activity for demo",
    "project": project_response.data["id"],
    "module_types": [ModuleType.objects.get(name="Grassland").id, ModuleType.objects.get(name="Annual Cropland").id]
}

activity_response = client.post('/api/activities/', post_activity, format='json')
print(activity_response)

module_type_start = ModuleType.objects.get(name="Grassland")
module_type_w = ModuleType.objects.get(name="Annual Cropland")
module_type_wo = ModuleType.objects.get(name="Grassland")

area = 150

post_luc = {
    "activity": activity_response.data["id"],
    "module_type_start": module_type_start.id,
    "module_type_w": module_type_w.id,
    "module_type_wo": module_type_wo.id,
    "area": area
}

luc_response = client.post('/api/land-use-changes/', post_luc, format='json')
print(luc_response)

post_grassland = {
    "activity": activity_response.data['id'],
    "land_use_change": luc_response.data["id"],
    "grassland_management_type_start": GrasslandManagementType.objects.get(name="High Intensity Grazing").id,
    "grassland_management_type_wo": GrasslandManagementType.objects.get(name="Severely Degraded").id,
    "is_fire_used_start": True,
    "is_fire_used_wo": True,
    "fire_periodicity_start": 2,
    "fire_periodicity_wo": 2,
    "fire_impact_start": 0.2,
    "fire_impact_wo": 0.2
}

post_annual_cropland = {
    "actvity": activity_response.data['id'],
    "land_use_change": luc_response.data["id"],
    "land_use_type_w": LandUseType.objects.get(name="Maize").id,
    "tillage_management_type_w": TillageManagementType.objects.get(name="Full Tillage").id,
    "organic_input_type_w": OrganicInputType.objects.get(name="High C input, no manure").id,
    "residue_management_type_w": ResidueManagementType.objects.get(name="Retained").id,
}

grassland_response = client.post('/api/grasslands/', post_grassland, format='json')
logging.info(grassland_response.data)
grassland_results_response = client.get(f'/api/grasslands/{grassland_response.data["id"]}/results', format='json')
print(grassland_results_response)

annualcropping_response = client.post('/api/annual-croppings/', post_annual_cropland, format='json')
print(annualcropping_response)
annualcropping_results_response = client.get(f'/api/annual-croppings/{annualcropping_response.data["id"]}/results', format='json')
print(annualcropping_results_response)

luc_results_response = client.get(f'/api/land-use-changes/{luc_response.data["id"]}/results', format='json')
print(luc_results_response)

print("##### Test Suite for COP28 Demo #####\n\n")

print("##### PARAMETERS #####\n\n")

print(f"Hectars: {area}")
print(f"Country: {country}")
print(f"Region: {country.region}")
print(f"Climate: {climate}")
print(f"Moisture: {moisture}")
print(f"Soil Type: {soil_type}")

print("##### PROJECT #####\n\n")

print(f"Project name: {project_response.data['name']}")

print("##### ACTIVITY #####\n\n")

print(f"Activity name: {activity_response.data['name']}")

print("##### LAND USE CHANGE #####\n\n")

print(f"Module type start: {module_type_start}")
print(f"Module type w: {module_type_w}")
print(f"Module type wo: {module_type_wo}")

print(f"Results: {luc_results_response.data}")

print("##### GRASSLAND #####\n\n")

print(f"Results: {grassland_results_response.data}")

print("##### ANNUAL CROPLAND #####\n\n")

print(f"Results: {annualcropping_results_response.data}")





