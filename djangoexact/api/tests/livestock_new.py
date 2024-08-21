from time import sleep

import factory.fuzzy as fuzzy
from api.calculators import *
import api.models as api_models
from api.serializers import *
import ipcc.models as ipcc_models

from .factories import *
import datetime

climates = api_models.Climate.objects.all()
countries = api_models.Country.objects.all()
soil_types = api_models.SoilType.objects.all().exclude(active=False).exclude(name="Mineral").exclude(name="Organic")
gw_potentials = ipcc_models.GlobalWarmingPotential.objects.all()

u = api_models.CustomUser.objects.get(email="admin@admin.com")

date = datetime.datetime.now().strftime("%d%m%Y%H%M%S")

climate = fuzzy.FuzzyChoice(climates).fuzz()
moisture = fuzzy.FuzzyChoice(climate.moistures.all()).fuzz()

p: ProjectFactory = ProjectFactory.create(owner=u, name=f"Livestock {date}", climate=climate, moisture=moisture)

a: api_models.Activity = ActivityFactory.create(project=p, name="Activity 1")

a.module_types.add(ModuleType.objects.get(class_name="Livestock"))
a.save()

livestock: api_models.Livestock = LivestockFactory.create(activity=a)

livestock_results = CalculatorFactory().calculate_result(livestock)

print("AO")
