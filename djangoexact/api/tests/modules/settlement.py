import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *
from api.reports import generate_excel_report

from ..factories import *
import api.tests.base_test_classes as t


class SettlementTest(t.ModuleWithSubmodulesTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="Settlement")
        self.submodule_types = [
            ModuleType.objects.get(class_name="Road"),
            ModuleType.objects.get(class_name="Building"),
            ModuleType.objects.get(class_name="OtherInfrastructure"),
        ]
        self.create_module()
        self.create_submodules(n=4)

    def test(self):
        self.calculate_results()

        generate_excel_report(self.project)


SettlementTest().test()
