import logging

from django.urls import reverse
from rest_framework import status
from rest_framework.test import force_authenticate

import api.models as models
from api.views import ActivityViewSet
from . import base_module

logging.getLogger().setLevel(logging.CRITICAL)
logging.getLogger("django").setLevel(logging.CRITICAL)


class LucSwapSanitizeTestCase(base_module.BaseLandUseChangeTestCase):
    """
    Regression test for swapping the module roles of a Land Use Change.

    Going from
        AnnualCropland (start/wo) -> FloodedRice (w)
    to
        FloodedRice (start/wo) -> AnnualCropland (w)
    must reset every scenario field that no longer applies to each land module.

    Previously ActivityBuilderSerializer.sanitize_input_entries() ran while the
    activity's module_types M2M was cleared, so Activity.modules yielded an empty
    list and the stale _start / _w / _wo values were never cleared.
    """

    def setUp(self):
        super().setUp()
        # Initial LUC: AnnualCropland is the start and without module; FloodedRice is the with module.
        self.setup_land_use_change(
            module_type_start_name="AnnualCropland",
            module_type_w_name="FloodedRice",
            module_type_wo_name="AnnualCropland",
        )

    def _swap_roles(self):
        """Swap the LUC roles through the activity builder: FloodedRice -> start/wo, AnnualCropland -> with."""
        annual_type = models.ModuleType.objects.get(class_name="AnnualCropland")
        rice_type = models.ModuleType.objects.get(class_name="FloodedRice")

        data = {
            "name": self.activity.name,
            "project": self.project.id,
            "area": 100,
            "cost": 0,
            "activity_id": self.activity.id,
            "module_types": [],
            "land_use_change": {
                "module_type_start": rice_type.id,
                "module_type_w": annual_type.id,
                "module_type_wo": rice_type.id,
            },
        }

        view = ActivityViewSet.as_view({"post": "build"})
        request = self.request_factory.post(reverse("activities-list"), data, format="json")
        force_authenticate(request, user=self.user)
        return view(request)

    def test_swapping_luc_roles_clears_stale_scenario_fields(self):
        annual = models.AnnualCropland.objects.get(activity=self.activity)
        rice = models.FloodedRice.objects.get(activity=self.activity)

        # Seed values matching each module's initial role.
        # AnnualCropland is start + without; FloodedRice is with.
        annual.flu_t2_start = 1.0
        annual.flu_t2_wo = 2.0
        annual.flu_t2_w = 3.0  # will become the relevant scenario after the swap
        annual.save()

        rice.flu_t2_w = 4.0
        rice.flu_t2_start = 5.0  # will become relevant after the swap
        rice.flu_t2_wo = 6.0
        rice.save()

        response = self._swap_roles()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        annual.refresh_from_db()
        rice.refresh_from_db()

        # AnnualCropland is now ONLY the "with" module: its start/without values must be cleared,
        # and its "with" value must be preserved.
        self.assertIsNone(annual.flu_t2_start)
        self.assertIsNone(annual.flu_t2_wo)
        self.assertEqual(annual.flu_t2_w, 3.0)

        # FloodedRice is now the start/without module: its "with" value must be cleared,
        # and its start/without values must be preserved.
        self.assertIsNone(rice.flu_t2_w)
        self.assertEqual(rice.flu_t2_start, 5.0)
        self.assertEqual(rice.flu_t2_wo, 6.0)
