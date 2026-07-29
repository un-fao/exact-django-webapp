import json
import math
import pprint
import random

import api.calculators as calc
import api.models as api_models
import api.tests.factories as factories
import ipcc.models as ipcc_models
import pandas as pd

BATCH_SIZE = 1

climates = api_models.Climate.objects.all().exclude(name="Tropical Montane")
moistures = api_models.Moisture.objects.all().exclude(name="Montane")
countries = api_models.Country.objects.all()
soil_types = api_models.SoilType.objects.all().exclude(name="Aggregated").exclude(name="Spodic").exclude(active=False)
gw_potentials = ipcc_models.GlobalWarmingPotential.objects.all()
soc_refs = ipcc_models.SoilOrganicCarbon.objects.all()

country = api_models.Country.objects.get(name_en="Tajikistan")
region = country.region
climate = api_models.Climate.objects.get(name_en="Cool Temperate")
moisture = api_models.Moisture.objects.get(name_en="Moist")
soil_type = api_models.SoilType.objects.get(name_en="High Activity Clay")
gw_potential = ipcc_models.GlobalWarmingPotential.objects.get(name_en="100 yr AR5 w/out CC feedback")

print(f"Country: {country}")
print(f"Region: {region}")
print(f"IPCC Region: {country.ipcc_region}")
print(f"Climate: {climate}")
print(f"Moisture: {moisture}")
print(f"Soil Type: {soil_type}")
print(f"GW Potential: {gw_potential}")

u = api_models.CustomUser.objects.get(username="admin")
group: api_models.Group = api_models.Group.objects.get(name="Admin")

p: api_models.Project = factories.ProjectFactory.create(
    user=u,
    climate=climate,
    moisture=moisture,
    country=country,
    gw_potential=gw_potential,
    soil_type=soil_type,
)

api_models.ProjectMembership.objects.create(user=u, project=p, group=group)

print(f"Capitalization Years: {p.capitalization_years}")
print(f"Implementation Years: {p.implementation_years}")

a: api_models.Activity = factories.ActivityFactory.create(project=p)
a.module_types.set([api_models.ModuleType.objects.get(name_en="Aquaculture")])
a.save()

aquacultures: list[api_models.Aquaculture] = factories.AquacultureFactory.create_batch(BATCH_SIZE, activity=a)

total_aquacultures = len(aquacultures)
passed_aquacultures = 0

print("Testing Aquaculture\n\n")
for i, aqua in enumerate(aquacultures):
    print(f"\n\nTesting module {i+1}...")
    print("-----------------------------------")

    print("\n")

    print(aqua)

    print("\n")

    print(f"annual_production_start: {aqua.annual_production_start}")
    print(f"annual_production_wo: {aqua.annual_production_wo}")
    print(f"annual_production_w: {aqua.annual_production_w}")

    print("\n")

    print(f"n2o_from_production_start: {aqua.n2o_from_production_t2_start}")
    print(f"n2o_from_production_wo: {aqua.n2o_from_production_t2_wo}")
    print(f"n2o_from_production_w: {aqua.n2o_from_production_t2_w}")

    print("\n")

    print(f"electricity_used_t2_start: {aqua.electricity_used_t2_start}")
    print(f"electricity_used_t2_wo: {aqua.electricity_used_t2_wo}")
    print(f"electricity_used_t2_w: {aqua.electricity_used_t2_w}")

    print("\n")

    results = calc.CalculatorFactory().calculate_result(aqua)

    print(json.dumps({"math_results_w": results[0], "math_results_wo": results[1], "math_results_balance": results[2]}, indent=4))
