from django.test import TestCase

import api.models as models
from api.tests.unit.factories import UnitTestGrasslandFactory, UnitTestOtherLandFactory


class LandUseTypeLazyAttributeTestCase(TestCase):
    """Inside a factory-boy lazy attribute ``self`` is the resolver, so factory methods cannot be called there."""

    def test_grassland_factory_builds(self):
        grassland = UnitTestGrasslandFactory.build()
        expected = models.LandUseType.objects.filter(module_types__class_name="Grassland", is_active=True).first()
        self.assertEqual(grassland.land_use_type_start, expected)
        self.assertEqual(grassland.land_use_type_w, expected)
        self.assertEqual(grassland.land_use_type_wo, expected)

    def test_other_land_factory_builds(self):
        other_land = UnitTestOtherLandFactory.build()
        expected = models.LandUseType.objects.filter(module_types__class_name="OtherLand", is_active=True).first()
        self.assertEqual(other_land.land_use_type_start, expected)
