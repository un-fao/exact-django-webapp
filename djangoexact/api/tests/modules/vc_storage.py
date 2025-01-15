import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *
import api.reports as reports

from ..factories import *
import api.tests.base_test_classes as t


class ValueChainStorageTest(t.ModuleWithSubmodulesTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="Storage")
        self.submodule_types = [
            ModuleType.objects.get(class_name="StorageEntry"),
        ]
        self.create_module()
        self.create_submodules()

    def test(self):
        self.calculate_results()
        self.calculate_submodule_results()

        # res = reports.BaseProjectReport(self.project)
        # res.build_report()


ValueChainStorageTest().test()
