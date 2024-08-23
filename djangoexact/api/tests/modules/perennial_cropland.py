import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *

from ..factories import *
import api.tests.base_test_classes as t
import factory.fuzzy as fuzzy


class PerennialCroplandTest(t.ModuleTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="PerennialCropping")
        self.trees = LandUseType.objects.filter(climates=self.climate, moistures=self.moisture, module_types=self.module_type)
        self.create_module(
            land_use_type_start=fuzzy.FuzzyChoice(self.trees).fuzz(),
            land_use_type_w=fuzzy.FuzzyChoice(self.trees).fuzz(),
            land_use_type_wo=fuzzy.FuzzyChoice(self.trees).fuzz(),
        )

    def test(self):
        self.calculate_results()


PerennialCroplandTest().test()
