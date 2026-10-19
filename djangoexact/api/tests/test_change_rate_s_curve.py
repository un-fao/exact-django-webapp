"""The "s-curve" change rate end to end, and a pin that the existing change rates did not move.

Run with the Django test runner (never bare pytest):

    python manage.py test api.tests.test_change_rate_s_curve --keepdb
"""

from unittest import mock

import api.models as models
import ipcc.models as ipcc_models
from api.tests.unit import base_module
from math_model.no_time_dependency_final import fisheries_and_aquaculture

# Captured on feat/next-parity-harness (before the S-curve existed) with the fixed inputs below.
PINNED_BEFORE_S_CURVE = {
    "linear": {"total_w": 1519.0610871679248, "total_wo": 2052.3484901098554, "balance": -533.2874029419311},
    "exponential": {"total_w": 3310.7876157987407, "total_wo": 4086.478383714278, "balance": -775.6907679155357},
    "immediate": {"total_w": 1034.2543572207148, "total_wo": 1809.9451251362507, "balance": -775.6907679155363},
}


class SCurveChangeRateTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.SmallFishery
        super().setUp()

        # Everything the fishery result depends on is fixed, so the pinned numbers are reproducible.
        self.project.gw_potential = ipcc_models.GlobalWarmingPotential.objects.order_by("id").first()
        self.project.save()
        gear = models.SmallFisheryGearType.objects.order_by("id").first().id
        self.edit_module(
            self.module,
            self.user,
            {
                "gear_type_start": gear,
                "gear_type_w": gear,
                "gear_type_wo": gear,
                "total_catch_yr_start": 100,
                "total_catch_yr_w": 40,
                "total_catch_yr_wo": 70,
                "fishery_type": models.FisheryType.objects.order_by("id").first().id,
            },
        )

    def results_for(self, rate_name):
        self.activity.change_rate = models.ChangeRate.objects.get(name=rate_name)
        self.activity.save()
        response = self.get_results(cached="false")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_s_curve_row_is_seeded(self):
        self.assertTrue(models.ChangeRate.objects.filter(name="s-curve").exists())

    def test_s_curve_reaches_the_math_model_and_computes(self):
        with mock.patch.object(
            fisheries_and_aquaculture,
            "compute_yearly_or_half_year_cumulative",
            wraps=fisheries_and_aquaculture.compute_yearly_or_half_year_cumulative,
        ) as spy:
            s_curve = self.results_for("s-curve")

        self.assertTrue(spy.called)
        self.assertTrue(all(call.args[4] == "s-curve" for call in spy.call_args_list))
        # Half-year averaging of a curve symmetric about T / 2 sums to the same total as linear;
        # the yearly path differs (see math_model/tests/test_s_curve.py).
        linear = PINNED_BEFORE_S_CURVE["linear"]
        for key in linear:
            self.assertAlmostEqual(s_curve[key], linear[key], places=6)

    def test_existing_change_rates_are_unchanged(self):
        for rate_name, pinned in PINNED_BEFORE_S_CURVE.items():
            results = self.results_for(rate_name)
            for key, value in pinned.items():
                self.assertAlmostEqual(results[key], value, places=6, msg=f"{rate_name}.{key}")
