import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *

from ..factories import *
import api.tests.base_test_classes as t


class SettlementTest(t.ModuleTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="Settlement")
        self.create_module()

    def test(self):
        self.calculate_results()


SettlementTest().test()
