from types import SimpleNamespace

from django.test import SimpleTestCase

from api.defaults import root_to_shoot_for_stock


class RootToShootForStockTest(SimpleTestCase):
    under = SimpleNamespace(threshold=125.0, value=0.23)
    over = SimpleNamespace(threshold=None, value=0.246)

    def test_stock_under_threshold_uses_under_ratio(self):
        self.assertEqual(root_to_shoot_for_stock(self.under, self.over, 121.448), 0.23)

    def test_stock_at_or_over_threshold_uses_over_ratio(self):
        self.assertEqual(root_to_shoot_for_stock(self.under, self.over, 125.0), 0.246)
        self.assertEqual(root_to_shoot_for_stock(self.under, self.over, 151.81), 0.246)

    def test_unknown_stock_uses_over_ratio(self):
        self.assertEqual(root_to_shoot_for_stock(self.under, self.over, None), 0.246)

    def test_only_unbounded_row_always_uses_it(self):
        only = SimpleNamespace(threshold=0, value=0.246)
        self.assertEqual(root_to_shoot_for_stock(only, self.over, 10.0), 0.246)
