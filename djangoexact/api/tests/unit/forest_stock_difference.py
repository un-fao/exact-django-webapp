from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import status

import api.models as models
from api.services.forest_stock_difference import STOCK_DIFFERENCE_LUC_ERROR, calculate_stock_difference

from . import base_module

START = {"agb": 120.0, "bgb": 30.0, "litter": 5.0, "deadwood": 8.0, "soc": 60.0}
END_W = {"agb": 150.0, "bgb": 36.0, "litter": 6.0, "deadwood": 9.0, "soc": 62.0}
END_WO = {"agb": 100.0, "bgb": 25.0, "litter": 4.0, "deadwood": 6.0, "soc": 58.0}


def stock_fields():
    fields = {}
    for scenario, stocks in (("start", START), ("w", END_W), ("wo", END_WO)):
        fields.update({f"stock_{pool}_{scenario}": value for pool, value in stocks.items()})
    return fields


class ForestStockDifferenceTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.ForestManagement
        super().setUp()

        self.edit_module(
            self.module,
            self.user,
            {
                "land_use_type_start": self.land_use_types.order_by("id").first().id,
                "forest_type": models.ForestType.objects.get(name_en="Natural").id,
                "forest_condition_type": models.ForestConditionType.objects.get(name_en="Primary").id,
            },
        )
        self.module.refresh_from_db()

    def balance(self):
        response = self.get_results(cached="false")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def test_gain_loss_ignores_stock_fields(self):
        before = self.balance()

        self.edit_module(self.module, self.user, stock_fields())
        self.module.refresh_from_db()
        self.assertEqual(self.module.approach, models.ForestManagement.APPROACH_GAIN_LOSS)

        after = self.balance()
        for key in ("total_w", "total_wo", "balance"):
            self.assertEqual(before[key], after[key], key)

    def test_stock_difference_results_follow_the_stock_change(self):
        self.edit_module(self.module, self.user, {"approach": "stock_difference", **stock_fields()})
        self.module.refresh_from_db()
        self.assertEqual(self.module.status.name_en, "READY")

        area = self.module.area
        expected_w = -(sum(END_W.values()) - sum(START.values())) * area * 44 / 12
        expected_wo = -(sum(END_WO.values()) - sum(START.values())) * area * 44 / 12

        data = self.balance()
        self.assertAlmostEqual(data["total_w"], expected_w, places=4)
        self.assertAlmostEqual(data["total_wo"], expected_wo, places=4)

    def test_stock_difference_with_missing_stock_is_not_ready(self):
        fields = stock_fields()
        del fields["stock_soc_wo"]
        self.edit_module(self.module, self.user, {"approach": "stock_difference", **fields})
        self.module.refresh_from_db()
        self.assertEqual(self.module.status.name_en, "EMPTY")


class StockDifferenceLandUseChangeTestCase(SimpleTestCase):
    def test_land_use_change_is_rejected(self):
        module = SimpleNamespace(is_luc_remaining_same=lambda: False, is_business_as_usual=lambda: True)
        with self.assertRaisesMessage(ValueError, STOCK_DIFFERENCE_LUC_ERROR):
            calculate_stock_difference(SimpleNamespace(module=module, forest=None))
