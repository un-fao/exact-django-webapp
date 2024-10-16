import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *
import factory.fuzzy as fuzzy
import api.reports as reports

from ..factories import *
import api.tests.base_test_classes as t


class ForestManagementTest(t.ModuleTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="ForestManagement")
        self.create_module()
        available_forests = LandUseType.objects.filter(module_types__in=[self.module_type], climates__in=[self.climate], moistures__in=[self.moisture])
        self.module: ForestManagement
        self.module.land_use_type_start = fuzzy.FuzzyChoice(available_forests).fuzz()
        self.module.land_use_type_w = self.module.land_use_type_start
        self.module.land_use_type_wo = self.module.land_use_type_start
        self.module.save()

    def test(self):
        self.calculate_results()

        rep = reports.BaseProjectReport(self.project)
        rep.build_report()


ForestManagementTest().test()
