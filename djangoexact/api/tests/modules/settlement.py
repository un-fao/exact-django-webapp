import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *
import api.reports as r

from ..factories import *
import api.tests.base_test_classes as t


class SettlementTest(t.ModuleWithSubmodulesTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="Settlement")
        self.submodule_types = [
            ModuleType.objects.get(class_name="Road"),
            ModuleType.objects.get(class_name="Building"),
        ]
        self.create_module()
        self.create_submodules(n=4)

    def test(self):
        self.calculate_results()

        report = r.BaseProjectReport(self.project)
        report.build_report()


SettlementTest().test()
