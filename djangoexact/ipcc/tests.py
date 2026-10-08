from django.test import TestCase

from api.models import Climate, ForestType, LandUseType, Region
from ipcc.models import ForestManagementRootToShoot


class RootToShootNullOrderingTest(TestCase):
    """A NULL threshold means "no upper limit" and must sort as the highest threshold on every backend."""

    def setUp(self):
        self.keys = {
            "climate": Climate.objects.create(name="Warm Temperate"),
            "region": Region.objects.create(name="Southern Asia"),
            "forest_type": ForestType.objects.create(name="Natural"),
            "land_use_type": LandUseType.objects.create(name="Humid Forest"),
        }
        ForestManagementRootToShoot.objects.create(**self.keys, threshold=125.0, value=0.23)
        ForestManagementRootToShoot.objects.create(**self.keys, threshold=None, value=0.246)

    def test_get_max_below_threshold_prefers_finite_threshold(self):
        row = ForestManagementRootToShoot.objects.get_max_below_threshold(**self.keys, threshold=1.0)
        self.assertEqual(row.value, 0.23)

    def test_get_first_above_threshold_prefers_null_threshold(self):
        row = ForestManagementRootToShoot.objects.get_first_above_threshold(**self.keys, threshold=200.0)
        self.assertEqual(row.value, 0.246)
