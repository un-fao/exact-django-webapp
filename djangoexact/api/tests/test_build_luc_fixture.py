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

    def test_forest_management_sibling_persists_non_sided_fields(self):
        from api import models
        from admin_scripts.luc_permutations import Side, expand_preset
        # ForestManagement has non-sided forest_type and forest_condition_type
        # FK fields. _save_sibling must write to the plain attributes (not
        # the _start/_w/_wo variants, which don't exist on the model).
        start_values = expand_preset("ForestManagement", 0, Side.START)[0]
        # Pick the same combo on the w side too so we exercise the same-class
        # path that hits the single-sibling branch.
        w_values = start_values

        with transaction.atomic():
            build_luc_fixture(
                start_class="ForestManagement", start_values=start_values,
                w_class="ForestManagement", w_values=w_values,
            )
            sibling = models.ForestManagement.objects.last()
            self.assertIsNotNone(sibling)
            self.assertIsNotNone(sibling.forest_type)
            self.assertIsNotNone(sibling.forest_condition_type)
            transaction.set_rollback(True)

    def test_siblings_status_is_ready_so_calculator_gate_passes(self):
        # OtherLandUseCalculator and DeforestationCalculator both gate on
        # module.status == StatusType(name_en="READY"). Module.status is
        # nullable with no default, so a sibling saved without an explicit
        # status assignment falls through to "All modules ... must be ready"
        # (regression seen in Test Run #12: 138/144 LUC pairs failed).
        from api import models
        ready = models.StatusType.objects.get(name_en="READY")

        # Exercise both different-class and same-class paths.
        start_values_diff = expand_preset("AnnualCropland", 0, Side.START)[0]
        w_values_diff = expand_preset("Grassland", 0, Side.W)[0]
        with transaction.atomic():
            luc = build_luc_fixture(
                start_class="AnnualCropland", start_values=start_values_diff,
                w_class="Grassland", w_values=w_values_diff,
            )
            for module in luc.get_modules():
                self.assertEqual(
                    module.status, ready,
                    f"{module.__class__.__name__}.status must be READY",
                )
            transaction.set_rollback(True)

        start_values_same = expand_preset("ForestManagement", 0, Side.START)[0]
        w_values_same = start_values_same
        with transaction.atomic():
            luc = build_luc_fixture(
                start_class="ForestManagement", start_values=start_values_same,
                w_class="ForestManagement", w_values=w_values_same,
            )
            for module in luc.get_modules():
                self.assertEqual(module.status, ready)
            transaction.set_rollback(True)
