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

p: ProjectFactory = ProjectFactory.create(owner=u, name=f"Set Aside->Annual {date}", climate=climate, moisture=moisture)

a: Activity = ActivityFactory.create(project=p, name="Activity 1")

a.module_types.add(ModuleType.objects.get(class_name="LandUseChange"))
a.module_types.add(ModuleType.objects.get(class_name="SetAside"))
a.module_types.add(ModuleType.objects.get(class_name="AnnualCropping"))
a.module_types.add(ModuleType.objects.get(class_name="Energy"))
a.module_types.add(ModuleType.objects.get(class_name="Input"))
a.module_types.add(ModuleType.objects.get(class_name="Irrigation"))
a.save()


luc: LandUseChange = LandUseChangeFactory.create(
    activity=a,
    module_type_start=ModuleType.objects.get(class_name="SetAside"),
    module_type_wo=ModuleType.objects.get(class_name="SetAside"),
    module_type_w=ModuleType.objects.get(class_name="AnnualCropping"),
)

set_aside: SetAside = SetAsideFactory.create(activity=a, is_set_aside_start=True, is_set_aside_wo=True, land_use_change=luc)

annual: AnnualCropping = AnnualCroppingFactory.create(activity=a, land_use_change=luc)

irrigation: Irrigation = IrrigationFactory.create(activity=a)
irrigation_phase: IrrigationPhase = IrrigationPhaseFactory.create(parent=irrigation)
irrigation_system: IrrigationSystem = IrrigationSystemFactory.create(parent=irrigation)

energy = EnergyFactory.create(activity=a)
electricity = ElectricityFactory.create(parent=energy)

input = InputFactory.create(activity=a)
input_entry = InputEntryFactory.create(parent=input)

set_aside_calculator = CalculatorFactory().calculate_result(set_aside)
annual_calculator = CalculatorFactory().calculate_result(annual)
luc_calculator = CalculatorFactory().calculate_result(luc)
irrigation_calculator = CalculatorFactory().calculate_result(irrigation)
energy_calculator = CalculatorFactory().calculate_result(energy)
input_calculator = CalculatorFactory().calculate_result(input)

print("AO")
