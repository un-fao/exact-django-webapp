import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *
import api.reports as reports

from ..factories import *
import api.tests.base_test_classes as t


class ValueChainStorageTest(t.ModuleTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="ValueChain")
        self.create_module()

        self.packaging = ValueChainStorageFactory.create(parent=self.module)

    def test(self):
        self.calculate_results()

        msc = StorageCalculator(self.packaging)
        res = msc.calculate()

        print(f"Packaging results: {Result(*res).breakdown()}")

        # res = reports.BaseProjectReport(self.project)
        # res.build_report()


ValueChainStorageTest().test()
