import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *

from ..factories import *
import api.tests.base_test_classes as t


class FloodedRiceTest(t.ModuleTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="FloodedRice")
        self.create_module()

        self.minor_season = MinorSeasonFloodedRiceFactory.create(parent=self.module)

    def test(self):
        self.calculate_results()

        msc = FloodedRiceSeasonCalculator(self.minor_season)
        res = msc.calculate()

        print(f"Minor season results: {Result(*res).breakdown()}")


FloodedRiceTest().test()
