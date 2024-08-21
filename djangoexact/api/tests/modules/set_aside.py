import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *

from ..factories import *
import api.tests.base_test_classes as t


class SetAsideTest(t.ModuleTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="SetAside")
        self.create_module()

    def test(self):
        self.calculate_results()


SetAsideTest().test()
