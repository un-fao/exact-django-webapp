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

p: ProjectFactory = ProjectFactory.create(owner=u, name=f"Perennial->Rice {date}", climate=climate, moisture=moisture)

a: Activity = ActivityFactory.create(project=p, name="Activity 1")

a.module_types.add(ModuleType.objects.get(class_name="LandUseChange"))
a.module_types.add(ModuleType.objects.get(class_name="PerennialCropping"))
a.module_types.add(ModuleType.objects.get(class_name="FloodedRice"))
a.save()


luc: LandUseChange = LandUseChangeFactory.create(
    activity=a,
    module_type_start=ModuleType.objects.get(class_name="PerennialCropping"),
    module_type_wo=ModuleType.objects.get(class_name="PerennialCropping"),
    module_type_w=ModuleType.objects.get(class_name="FloodedRice"),
)

perennial_lut_start: LandUseType = fuzzy.FuzzyChoice(LandUseType.objects.filter(climates=climate, moistures=moisture, module_types=ModuleType.objects.get(class_name="PerennialCropping")).all()).fuzz()
perennial_lut_w: LandUseType = fuzzy.FuzzyChoice(LandUseType.objects.filter(climates=climate, moistures=moisture, module_types=ModuleType.objects.get(class_name="PerennialCropping")).all()).fuzz()
perennial_lut_wo: LandUseType = fuzzy.FuzzyChoice(LandUseType.objects.filter(climates=climate, moistures=moisture, module_types=ModuleType.objects.get(class_name="PerennialCropping")).all()).fuzz()

perennial: PerennialCropping = PerennialCroppingFactory.create(activity=a, land_use_change=luc, land_use_type_start=perennial_lut_start, land_use_type_wo=perennial_lut_wo, land_use_type_w=perennial_lut_w)
flooded_rice: FloodedRice = FloodedRiceFactory.create(activity=a, land_use_change=luc)


perennial_results = CalculatorFactory().calculate_result(perennial)
flooded_rice_results = CalculatorFactory().calculate_result(flooded_rice)


print("AO")
