import logging as log

from api.calculators import *
from api.models import *
from api.serializers import *
from ipcc.models import *
from api.reports import generate_excel_report

from .factories import *
import api.tests.base_test_classes as t


class AnnualToOtherLand(t.LandUseChangeTest):
    def __init__(self):
        super().__init__()
        self.module_type_start = ModuleType.objects.get(class_name="AnnualCropland")
        self.module_type_wo = ModuleType.objects.get(class_name="AnnualCropland")
        self.module_type_w = ModuleType.objects.get(class_name="OtherLand")
        self.create_land_use_change(self.module_type_start, self.module_type_wo, self.module_type_w)
        self.add_activity_modules([self.module_type_start, self.module_type_wo, self.module_type_w])

        self.module_start: AnnualCropland = self.create_module(self.module_type_start, land_use_change=self.land_use_change)
        self.module_end: OtherLand = self.create_module(self.module_type_w, land_use_change=self.land_use_change)

        self.activity.module_types.add(ModuleType.objects.get(class_name="OrganicSoil"))
        self.activity.save()
        self.activity.refresh_from_db()

        self.organic_soil: OrganicSoil = self.create_module(ModuleType.objects.get(class_name="OrganicSoil"), land_use_change=self.land_use_change)

    def test(self):
        self.calculate_results()

        generate_excel_report(self.project)


AnnualToOtherLand().test()
