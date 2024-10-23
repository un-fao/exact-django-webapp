import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *

from ..factories import *
import api.tests.base_test_classes as t

import api.reports as reports


class AnnualCroplandWithMinorSeasonTest(t.ModuleTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="AnnualCropland")

        minor_season = AnnualCroplandWithMinorSeasonFactory.build(activity=self.activity)
        self.create_module(
            minor_land_use_type_start=minor_season.minor_land_use_type_start,
            minor_land_use_type_wo=minor_season.minor_land_use_type_w,
            minor_land_use_type_w=minor_season.minor_land_use_type_wo,
            minor_residue_management_type_start=minor_season.minor_residue_management_type_start,
            minor_residue_management_type_wo=minor_season.minor_residue_management_type_w,
            minor_residue_management_type_w=minor_season.minor_residue_management_type_wo,
        )

    def test(self):
        self.calculate_results()

        res = reports.BaseProjectReport(self.project)
        res.build_report()


AnnualCroplandWithMinorSeasonTest().test()
