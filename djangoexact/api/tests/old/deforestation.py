import json
import logging

import factory.fuzzy as fuzzy
from api.models import *
from api.models import CustomUser as User
from api.views import *
from django.test import TestCase
from ipcc.models import GlobalWarmingPotential
from rest_framework.test import (
    APIClient,
    APIRequestFactory,
    APITestCase,
    force_authenticate,
)

client = APIClient()

u = User.objects.get(email="admin@admin.com")

client.force_authenticate(user=u)

country = Country.objects.get(name="Lao People's Democratic Republic")
climate = Climate.objects.get(name="Tropical")
moisture = Moisture.objects.get(name="Moist")
soil_type = SoilType.objects.get(name="High Activity Clay")
gw_potential = GlobalWarmingPotential.objects.get(name="100 yr AR5 w/out CC feedback")
implementation_years = 5
capitalization_years = 15

# Generate random name
post_project = {"name": fuzzy.FuzzyText().fuzz(), "country": country.id, "climate": climate.id, "moisture": moisture.id, "soil_type": soil_type.id, "gw_potential": gw_potential.id, "implementation_years": implementation_years, "capitalization_years": capitalization_years}

project_response = client.post("/api/projects/", json.dumps(post_project), content_type="application/json")
logging.debug(project_response)


module_type_start = ModuleType.objects.get(name="Forest Management")
module_type_w = ModuleType.objects.get(name="Annual Cropland")
module_type_wo = ModuleType.objects.get(name="Forest Management")

post_activity = {
    "name": "Deforestation to Annual Cropland",
    "climate": climate.id,
    "moisture": moisture.id,
    "soil_type": soil_type.id,
    "duration": 5,
    "project": project_response.data["id"],
    "module_types": [],
    "land_use_change": {
        "module_type_start": module_type_start.id,
        "module_type_w": module_type_w.id,
        "module_type_wo": module_type_wo.id,
    },
    "area": 150,
    "cost": 1000,
}

activity_response = client.post("/api/activities/build/", post_activity, format="json")
logging.debug(activity_response.data)

logging.debug(f"Activity ID: {activity_response.data['id']}")

luc = client.get(f'/api/land-use-changes/?activity={activity_response.data["id"]}')
logging.debug(luc)

post_forest_management = {
    "activity": activity_response.data["id"],
    "land_use_type_start": LandUseType.objects.get(name="Rainforest").id,
    "land_use_type_w": LandUseType.objects.get(name="Rainforest").id,
    "land_use_type_wo": LandUseType.objects.get(name="Rainforest").id,
}

post_annual_cropland = {
    "land_use_type_w": LandUseType.objects.get(name="Maize").id,
    "tillage_management_type_w": TillageManagementType.objects.get(name="Full Tillage").id,
    "organic_input_type_w": OrganicInputType.objects.get(name="High C input, no manure").id,
    "residue_management_type_w": ResidueManagementType.objects.get(name="Retained").id,
}

forest_management = client.get(f'/api/forest-managements/?activity={activity_response.data["id"]}')
logging.debug(forest_management)
forest_response = client.patch(f'/api/forest-managements/{forest_management.data[0]["id"]}/', post_forest_management, format="json")
logging.debug(forest_response)

forest_results_response = client.get(f'/api/forest-managements/{forest_response.data["id"]}/results/')
logging.debug(forest_results_response)

annualcropping = client.get(f'/api/annual-croppings/?activity={activity_response.data["id"]}')
annualcropping_response = client.patch(f'/api/annual-croppings/{annualcropping.data[0]["id"]}/', post_annual_cropland, format="json")
logging.debug(annualcropping_response)

annualcropping_results_response = client.get(f'/api/annual-croppings/{annualcropping_response.data["id"]}/results/')
logging.debug(annualcropping_results_response)

luc_results_response = client.get(f'/api/land-use-changes/{luc.data[0]["id"]}/results/')

logging.debug("##### Test Suite for COP28 Demo #####\n\n")

logging.debug("##### PARAMETERS #####\n\n")

logging.debug(f"Hectars: {activity_response.data['area']}")
logging.debug(f"Country: {country}")
logging.debug(f"Region: {country.region}")
logging.debug(f"Climate: {climate}")
logging.debug(f"Moisture: {moisture}")
logging.debug(f"Soil Type: {soil_type}\n\n")

logging.debug("##### PROJECT #####\n\n")

logging.debug(f"Project name: {project_response.data['name']}\n\n")

logging.debug("##### ACTIVITY #####\n\n")

logging.debug(f"Activity name: {activity_response.data['name']}\n\n")

logging.debug("##### LAND USE CHANGE #####\n\n")

logging.debug(f"Module type start: {module_type_start}")
logging.debug(f"Module type w: {module_type_w}")
logging.debug(f"Module type wo: {module_type_wo}\n\n")

logging.debug(f"Results: {luc_results_response.data}\n\n")

logging.debug("##### GRASSLAND #####\n\n")

logging.debug(f"Results: {forest_results_response.data}\n\n")

logging.debug("##### ANNUAL CROPLAND #####\n\n")

logging.debug(f"Results: {annualcropping_results_response.data}\n\n")

logging.debug("##### TOTAL EMISSIONS FOR PROJECT #####\n\n")


class Result:
    def __init__(self, total_w, total_wo, balance=None) -> None:
        self.w = float(total_w)
        self.wo = float(total_wo)
        self.balance = total_w - total_wo if not balance else float(balance)

    def __str__(self) -> str:
        return f"w: {self.w}, wo: {self.wo}, balance: {self.balance}"

    def __add__(self, other):
        return Result(self.w + other.w, self.wo + other.wo, self.balance + other.balance)

    def __sub__(self, other):
        return Result(self.w - other.w, self.wo - other.wo, self.balance - other.balance)


# Grassland
grassland_results = Result(**forest_results_response.data)

# Annual Cropland
annualcropping_results = Result(**annualcropping_results_response.data)

# Land Use Change
luc_results = Result(**luc_results_response.data)

# Total
total_w = grassland_results.w + annualcropping_results.w + luc_results.w
total_wo = grassland_results.wo + annualcropping_results.wo + luc_results.wo
total_balance = total_w - total_wo

total_results = Result(total_w, total_wo, total_balance)

logging.debug(f"Total results: {total_results}\n\n")
