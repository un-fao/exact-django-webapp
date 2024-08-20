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
import datetime

climates = Climate.objects.all()
countries = Country.objects.all()
soil_types = SoilType.objects.all().exclude(active=False).exclude(name="Mineral").exclude(name="Organic")
gw_potentials = GlobalWarmingPotential.objects.all()

u = User.objects.get(email="admin@admin.com")

date = datetime.datetime.now().strftime("%d%m%Y%H%M%S")

climate = fuzzy.FuzzyChoice(climates).fuzz()
moisture = fuzzy.FuzzyChoice(climate.moistures.all()).fuzz()

p: ProjectFactory = ProjectFactory.create(owner=u, name=f"Grassland->Settlement {date}", climate=climate, moisture=moisture)

a: Activity = ActivityFactory.create(project=p, name="Activity 1")

a.module_types.add(ModuleType.objects.get(class_name="LandUseChange"))
a.module_types.add(ModuleType.objects.get(class_name="Grassland"))
a.module_types.add(ModuleType.objects.get(class_name="Settlement"))
a.save()


luc: LandUseChange = LandUseChangeFactory.create(
    activity=a,
    module_type_start=ModuleType.objects.get(class_name="Grassland"),
    module_type_wo=ModuleType.objects.get(class_name="Grassland"),
    module_type_w=ModuleType.objects.get(class_name="Settlement"),
)

grassland: Grassland = GrasslandFactory.create(activity=a, land_use_change=luc)
settlement: Settlement = SettlementFactory.create(activity=a, land_use_change=luc)
building: Building = BuildingFactory.create(parent=settlement)

grassland_results = CalculatorFactory().calculate_result(grassland)
settlement_results = CalculatorFactory().calculate_result(settlement)


print("AO")
