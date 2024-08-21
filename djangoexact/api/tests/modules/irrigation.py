import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *

from ..factories import *
import api.tests.base_test_classes as t


class IrrigationTest(t.ModuleWithSubmodulesTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="Irrigation")
        self.submodule_types = [
            ModuleType.objects.get(class_name="IrrigationSystem"),
            ModuleType.objects.get(class_name="IrrigationPhase"),
        ]
        self.create_module()
        self.create_submodules()

    def test(self):
        self.calculate_results()


IrrigationTest().test()
