"""Tests for build_luc_fixture in luc_compute."""
from django.db import transaction
from django.test import TestCase

from admin_scripts.luc_permutations import Side, expand_preset
from api.services.luc_compute import build_luc_fixture


class BuildLucFixtureTest(TestCase):
    databases = {"default"}

    def test_different_classes_create_two_siblings_and_one_luc(self):
        from api import models
        start_values = expand_preset("AnnualCropland", 0, Side.START)[0]
        w_values = expand_preset("Grassland", 0, Side.W)[0]

        with transaction.atomic():
            luc = build_luc_fixture(
                start_class="AnnualCropland", start_values=start_values,
                w_class="Grassland", w_values=w_values,
            )
            self.assertIsNotNone(luc.pk)
            self.assertEqual(luc.module_type_start.class_name, "AnnualCropland")
            self.assertEqual(luc.module_type_w.class_name, "Grassland")
            self.assertEqual(luc.module_type_wo.class_name, "AnnualCropland")
            activity = luc.activity
            self.assertEqual(activity.annualcropland.count(), 1)
            self.assertEqual(activity.grassland.count(), 1)
            transaction.set_rollback(True)

        # After rollback, none of the rows persist.
        self.assertEqual(models.LandUseChange.objects.count(), 0)
        self.assertEqual(models.AnnualCropland.objects.count(), 0)
        self.assertEqual(models.Grassland.objects.count(), 0)

    def test_same_class_creates_single_sibling_with_both_sides_populated(self):
        from api import models
        start_values = expand_preset("AnnualCropland", 0, Side.START)[0]
        w_values = expand_preset("AnnualCropland", 1, Side.W)[0]

        with transaction.atomic():
            luc = build_luc_fixture(
                start_class="AnnualCropland", start_values=start_values,
                w_class="AnnualCropland", w_values=w_values,
            )
            self.assertEqual(luc.activity.annualcropland.count(), 1)
            sibling = luc.activity.annualcropland.first()
            self.assertEqual(str(sibling.tillage_management_type_start), "Full Tillage")
            self.assertEqual(str(sibling.tillage_management_type_w), "No Tillage")
            self.assertEqual(str(sibling.tillage_management_type_wo), "Full Tillage")
            transaction.set_rollback(True)
