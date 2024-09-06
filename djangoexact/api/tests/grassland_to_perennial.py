import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *

from .factories import *
import api.tests.base_test_classes as t
from factory import fuzzy


class GrasslandToPerenial(t.LandUseChangeTest):
    def __init__(self):
        super().__init__()
        self.module_type_start = ModuleType.objects.get(class_name="Grassland")
        self.module_type_wo = ModuleType.objects.get(class_name="Grassland")
        self.module_type_w = ModuleType.objects.get(class_name="PerennialCropland")
        self.create_land_use_change(self.module_type_start, self.module_type_wo, self.module_type_w)
        self.add_activity_modules([self.module_type_start, self.module_type_wo, self.module_type_w])

        self.trees = LandUseType.objects.filter(climates=self.climate, moistures=self.moisture, module_types=self.module_type_w).all()

        self.module_start: Grassland = self.create_module(self.module_type_start, land_use_change=self.land_use_change)
        self.module_end: PerennialCropland = self.create_module(self.module_type_w, land_use_change=self.land_use_change, land_use_type_start=fuzzy.FuzzyChoice(self.trees).fuzz(), land_use_type_wo=fuzzy.FuzzyChoice(self.trees).fuzz(), land_use_type_w=fuzzy.FuzzyChoice(self.trees).fuzz())

    def test(self):
        self.calculate_results()


GrasslandToPerenial().test()
