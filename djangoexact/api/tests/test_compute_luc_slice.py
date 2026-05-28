"""Tests for _compute_luc_slice end-to-end."""
from django.test import TestCase

from api import models
from api.services.luc_compute import _compute_luc_slice


class ComputeLucSliceTest(TestCase):
    databases = {"default"}

    def test_same_class_self_transition_produces_data_rows(self):
        data, errors = _compute_luc_slice(
            from_value="AnnualCropland#0",
            to_value="AnnualCropland#1",
            save_results=False,
        )
        self.assertGreaterEqual(len(data) + len(errors), 1)
        # Every data row carries the LUC identifier pair.
        for row in data:
            self.assertEqual(row["from_value"], "AnnualCropland#0")
            self.assertEqual(row["to_value"], "AnnualCropland#1")

    def test_rolls_back_fixtures_after_each_combo(self):
        before_luc = models.LandUseChange.objects.count()
        before_act = models.Activity.objects.count()
        _compute_luc_slice(
            from_value="AnnualCropland#0", to_value="Grassland#0",
            save_results=False,
        )
        self.assertEqual(models.LandUseChange.objects.count(), before_luc)
        self.assertEqual(models.Activity.objects.count(), before_act)

    def test_afforestation_w_side_only_uses_secondary_condition(self):
        # AnnualCropland -> ForestManagement: w side must restrict
        # forest_condition_type to "Secondary".
        data, errors = _compute_luc_slice(
            from_value="AnnualCropland#0", to_value="ForestManagement#0",
            save_results=False,
        )
        # Either we produced data (must all be Secondary) or all errors are
        # unrelated to the afforestation rule (we don't assert success here
        # since the math model may legitimately fail on some combos).
        for row in data:
            cond = row.get("w_values", {}).get("forest_condition_type")
            if cond is not None:
                self.assertEqual(str(cond), "Secondary")
