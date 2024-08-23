import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *

from .factories import *
import api.tests.base_test_classes as t


class AnnualToSetAside(t.LandUseChangeTest):
    def __init__(self):
        super().__init__()
        self.module_type_start = ModuleType.objects.get(class_name="AnnualCropping")
        self.module_type_wo = ModuleType.objects.get(class_name="AnnualCropping")
        self.module_type_w = ModuleType.objects.get(class_name="SetAside")
        self.create_land_use_change(self.module_type_start, self.module_type_wo, self.module_type_w)
        self.add_activity_modules([self.module_type_start, self.module_type_wo, self.module_type_w])

        self.module_start: AnnualCropping = self.create_module(self.module_type_start, land_use_change=self.land_use_change)
        self.module_end: SetAside = self.create_module(self.module_type_w, land_use_change=self.land_use_change)

    def test(self):
        self.calculate_results()


AnnualToSetAside().test()
