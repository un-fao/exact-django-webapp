import logging as log
import os

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *

import datetime
from factory import fuzzy
from .factories import *
import api.tests.base_test_classes as t


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
        """
        Retrieves the specified parameters from the given source object in dictionary format.

        Args:
            source: The source object from which to retrieve the parameters.

        Returns:
            dict: A dictionary containing the specified parameters and their values.

        """
        parameters = {}
        for parameter in self.parameters_to_print:
            if hasattr(source, parameter):
                parameters[parameter] = getattr(source, parameter)
        return parameters

    def create_project(self):
        """
        Creates a project with the specified parameters.

        Returns:
            ProjectFactory: The created project.

        Raises:
            None.
        """
        self.project: ProjectFactory = ProjectFactory.create(owner=self.user, name=f"{self.date}", climate=self.climate, moisture=self.moisture)
        log.info(f"Created project with parameters {self.get_parameters(self.project)}")

    @abstractmethod
    def test(self):
        pass


class ActivityTest(ProjectTest):
    def __init__(self):
        super().__init__()
        self.create_project()
        self.activity = None

    def create_activity(self):
        """
        Creates an activity for the current project.

        Returns:
            Activity: The created activity object.

        Raises:
            None.
        """
        self.activity: Activity = ActivityFactory.create(project=self.project, name="Activity 1")
        log.info(f"Created activity {self.activity.name} in project {self.project.name}")

    def add_activity_modules(self, module_types: list[ModuleType]):
        """
        Adds the specified module types to the activity.

        Args:
            module_types (list[ModuleType]): A list of module types to be added.

        Returns:
            None

        Raises:
            None
        """
        for module_type in module_types:
            self.activity.module_types.add(module_type)
        self.activity.save()
        log.info(f"Added modules {module_types} to activity {self.activity.name}")

    def create_module(self, module_type: ModuleType, **kwargs):
        """
        Create a module of the specified module_type.

        Parameters:
            module_type (ModuleType): The type of module to create.
            **kwargs: Additional keyword arguments to pass to the module factory.

        Returns:
            Module: The created module.

        Raises:
            KeyError: If the factory for the specified module_type is not found.

        Example:
            create_module(ModuleType.FOO, name='foo_module')
        """
        try:
            factory_name = f"{module_type.class_name}Factory"
            Factory: DjangoModelFactory = globals()[factory_name]
        except KeyError:
            raise KeyError(f"Factory for module type {module_type} not found")

        module: Module = Factory.create(activity=self.activity, **kwargs)
        log.info(f"Created module {module.__class__.__name__} with parameters {self.get_parameters(module)}")

        return module


class ModuleTest(ActivityTest):
    def __init__(self):
        super().__init__()
        self.create_activity()
        self.module_type = None
        self.module = None
        self.module_results = None

    def create_module(self, module_type: ModuleType, **kwargs):
        self.module = super().create_module(module_type, **kwargs)

    def calculate_results(self):
        """
        Calculate the results for the module.

        Returns:
            None

        Raises:
            None
        """
        try:
            self.module_results: tuple = CalculatorFactory().calculate_result(self.module)
            log.info(f"{self.module.__class__.__name__} results: {self.module_results}")
        except Exception as e:
            log.error(traceback.format_exc())
            log.error(e)

            with open(os.path.join(os.getcwd(), "api", "tests", "test.log"), "a") as f:
                f.write(f"Error in {self.__class__.__name__}: {e}\n")


class LandUseChangeTest(ActivityTest):
    def __init__(self):
        super().__init__()
        self.create_activity()

        self.module_type_start = None
        self.module_type_wo = None
        self.module_type_w = None

        self.land_use_change: LandUseChange = None
        self.land_use_change_calculator: LandUseChangeCalculator = None
        self.land_use_change_results: tuple = None

        self.module_start: LandModule = None
        self.module_start_results: tuple = None

        self.module_end: LandModule = None
        self.module_end_results: tuple = None

        self.parameters_to_print = ["module_type_start", "module_type_wo", "module_type_w"]

    def create_land_use_change(self, module_type_start: ModuleType, module_type_wo: ModuleType, module_type_w: ModuleType):
        """
        Create a LandUseChange object with the specified module types.

        Parameters:
        - module_type_start (ModuleType): The module type for the start of the land use change.
        - module_type_wo (ModuleType): The module type without the land use change.
        - module_type_w (ModuleType): The module type with the land use change.

        Returns:
        - None

        """
        self.land_use_change: LandUseChange = LandUseChangeFactory.create(
            activity=self.activity,
            module_type_start=module_type_start,
            module_type_wo=module_type_wo,
            module_type_w=module_type_w,
        )
        log.info(f"Created LUC with parameters {self.get_parameters(self.land_use_change)}")

    def calculate_results(self):

        try:

            self.module_start_results: tuple = CalculatorFactory().calculate_result(self.module_start)
            self.module_end_results: tuple = CalculatorFactory().calculate_result(self.module_end)
            self.land_use_change_results: tuple = CalculatorFactory().calculate_result(self.land_use_change)

            log.info(f"{self.module_start.__class__.__name__} results: {self.module_start_results}")
            log.info(f"{self.module_end.__class__.__name__} results: {self.module_end_results}")
            log.info(f"Land use change results: {self.land_use_change_results}")

        except Exception as e:
            log.error(traceback.format_exc())
            log.error(e)

            with open(os.path.join(os.getcwd(), "api", "tests", "test.log"), "a") as f:
                f.write(f"Error in {self.__class__.__name__}: {e}\n")
