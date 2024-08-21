from time import sleep
import logging as log

import factory.fuzzy as fuzzy
from api.calculators import *
from api.models import *
from api.models import CustomUser as User
from api.serializers import *
from ipcc.models import *

from .factories import *
import datetime


class ProjectTest:
    def __init__(self):
        log.basicConfig(level=log.INFO)
        self.user = User.objects.get(email="admin@admin.com")
        self.climates = Climate.objects.all()
        self.countries = Country.objects.all()
        self.soil_types = SoilType.objects.all().exclude(active=False).exclude(name="Mineral").exclude(name="Organic")
        self.gw_potentials = GlobalWarmingPotential.objects.all()
        self.climate = fuzzy.FuzzyChoice(climates).fuzz()
        self.moisture = fuzzy.FuzzyChoice(self.climate.moistures.all()).fuzz()
        self.date = datetime.datetime.now().strftime("%d%m%Y%H%M%S")
        self.project = None
        self.parameters_to_print = ["climate", "moisture", "soil_type", "country"]

    def get_parameters(self, source) -> dict:
        parameters = {}
        for parameter in self.parameters_to_print:
            if hasattr(source, parameter):
                parameters[parameter] = getattr(source, parameter)
        return parameters

    def create_project(self):
        self.project: ProjectFactory = ProjectFactory.create(owner=self.user, name=f"{self.date}", climate=self.climate, moisture=self.moisture)
        log.info(f"Created project with parameters {self.get_parameters(self.project)}")


class ActivityTest(ProjectTest):
    def __init__(self):
        super().__init__()
        self.create_project()
        self.activity = None

    def create_activity(self):
        self.activity: Activity = ActivityFactory.create(project=self.project, name="Activity 1")
        log.info(f"Created activity {self.activity.name} in project {self.project.name}")

    def add_activity_modules(self, module_types: list[ModuleType]):
        for module_type in module_types:
            self.activity.module_types.add(module_type)
        self.activity.save()
        log.info(f"Added modules {module_types} to activity {self.activity.name}")


class ModuleTest(ActivityTest):
    def __init__(self):
        super().__init__()
        self.create_activity()

    def create_module(self, module_type: ModuleType, **kwargs):
        # Find the module factory as "module_type.nameFactory" in factories.py
        factory_name = f"{module_type.class_name}Factory"
        Factory: DjangoModelFactory = globals()[factory_name]

        module: Module = Factory.create(activity=self.activity, **kwargs)
        log.info(f"Created module {module.__class__.__name__} with parameters {self.get_parameters(module)}")

        return module


class LandUseChangeTest(ModuleTest):
    def __init__(self):
        super().__init__()

        self.module_type_start = None
        self.module_type_wo = None
        self.module_type_w = None

        self.land_use_change: LandUseChange = None
        self.land_use_change_calculator: LandUseChangeCalculator = None
        self.land_use_change_results: tuple = None

        self.parameters_to_print = ["module_type_start", "module_type_wo", "module_type_w"]

    def create_land_use_change(self, module_type_start: ModuleType, module_type_wo: ModuleType, module_type_w: ModuleType):
        self.land_use_change: LandUseChange = LandUseChangeFactory.create(
            activity=self.activity,
            module_type_start=module_type_start,
            module_type_wo=module_type_wo,
            module_type_w=module_type_w,
        )
        log.info(f"Created LUC with parameters {self.get_parameters(self.land_use_change)}")


class AnnualToSetAside(LandUseChangeTest):
    def __init__(self):
        super().__init__()
        self.module_type_start = ModuleType.objects.get(class_name="AnnualCropping")
        self.module_type_wo = ModuleType.objects.get(class_name="AnnualCropping")
        self.module_type_w = ModuleType.objects.get(class_name="SetAside")
        self.create_land_use_change(self.module_type_start, self.module_type_wo, self.module_type_w)
        self.add_activity_modules([self.module_type_start, self.module_type_wo, self.module_type_w])

        self.annual_cropping: AnnualCropping = self.create_module(self.module_type_start, land_use_change=self.land_use_change)
        self.set_aside: SetAside = self.create_module(self.module_type_w, land_use_change=self.land_use_change)

        self.annual_cropping_calculator: AnnualCroppingCalculator = None
        self.set_aside_calculator: SetAsideCalculator = None

        self.annual_cropping_results: tuple = None
        self.set_aside_results: tuple = None

    def test_annual_to_setaside(self):
        try:

            self.annual_cropping_results: tuple = CalculatorFactory().calculate_result(self.annual_cropping)
            self.set_aside_results: tuple = CalculatorFactory().calculate_result(self.set_aside)
            self.land_use_change_results: tuple = CalculatorFactory().calculate_result(self.land_use_change)

            log.info(f"Annual cropping results: {self.annual_cropping_results}")
            log.info(f"Set aside results: {self.set_aside_results}")
            log.info(f"Land use change results: {self.land_use_change_results}")

        except Exception as e:
            e.print_exc()
            log.error(e)


AnnualToSetAside().test_annual_to_setaside()
