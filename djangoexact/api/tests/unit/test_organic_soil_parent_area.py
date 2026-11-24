"""Regression tests for the area an Organic Soil (without LUC) inherits from its parent module.

A Forest Management parent must give `area_affected_by_module == 0`, which the
inlands math treats as "no module-area cap". The check used to compare the
translated `ModuleType.name` ("Forest Management") against the class name
"ForestManagement", so it never matched and forest organic soils got the parent area.
"""

from unittest.mock import patch

from django.test import TestCase

import api.models as models
import ipcc.models as ipcc_models
from api.calculators import OrganicSoilCalculator
from api.tests.unit.factories import (
    UnitTestActivityFactory,
    UnitTestForestManagementFactory,
    UnitTestGrasslandFactory,
    UnitTestOrganicSoilFactory,
    UnitTestProjectFactory,
)

PARENT_AREA = 150


class _StopAfterArea(Exception):
    pass


class OrganicSoilParentAreaTestCase(TestCase):
    def _area_affected_by_module(self, parent_factory, parent_class_name: str, **parent_kwargs) -> float:
        owner = models.CustomUser.objects.create_user(email="organic-soil@test.com", password="testpass123")
        project = UnitTestProjectFactory.create(owner=owner)
        activity = UnitTestActivityFactory.create(project=project)
        activity.module_types.add(models.ModuleType.objects.get(class_name=parent_class_name))
        organic_soil = UnitTestOrganicSoilFactory.create(activity=activity)
        parent_factory.create(activity=activity, area=PARENT_AREA, organic_soil=organic_soil, **parent_kwargs)

        calculator = OrganicSoilCalculator(organic_soil)
        # The first EF lookup runs right after the area is set. Stopping there keeps
        # the test independent of which climate/peat combinations have IPCC factors.
        with patch.object(ipcc_models.OrganicSoilGefEmissionFactor.objects, "get", side_effect=_StopAfterArea):
            with self.assertRaises(_StopAfterArea):
                calculator.get_defaults()
        return calculator.area_affected_by_module

    def test_forest_management_parent_gives_zero_area(self):
        self.assertEqual(self._area_affected_by_module(UnitTestForestManagementFactory, "ForestManagement"), 0)

    def test_non_forest_parent_gives_parent_area(self):
        # UnitTestGrasslandFactory's land_use_type lazy attributes call a method the factory
        # stub does not have, so they must be supplied.
        grassland = models.LandUseType.objects.filter(module_types__class_name="Grassland", is_active=True).first()
        land_use_types = {f"land_use_type_{s}": grassland for s in ("start", "w", "wo")}
        self.assertEqual(self._area_affected_by_module(UnitTestGrasslandFactory, "Grassland", **land_use_types), PARENT_AREA)
