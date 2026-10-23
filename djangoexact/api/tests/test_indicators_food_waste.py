"""Food-waste indicator group on a project with two calculated Solid Waste activities.

Run with:
    python manage.py test api.tests.test_indicators_food_waste
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

import api.models as models
from api.services import indicators
from api.tests.unit import base_module
from math_model.no_time_dependency_final.solid_waste import ROUTES

SCENARIOS = ("start", "w", "wo")


def stream(amounts: dict[str, float], routes: dict[str, dict[str, float]]) -> dict:
    data = {f"amount_{s}": amounts[s] for s in SCENARIOS}
    data.update({f"route_{route}_{s}": routes[s].get(route, 0.0) for route in ROUTES for s in SCENARIOS})
    return data


class UnavailableTests(SimpleTestCase):
    def test_project_without_solid_waste_has_the_group_unavailable(self):
        project = SimpleNamespace(pk=1, implementation_years=5, capitalization_years=15, start_year_of_activities=2025)
        group = next(g for g in indicators.build(project, [])["groups"] if g["id"] == "food_waste")
        self.assertFalse(group["available"])
        self.assertEqual(group["indicators"], [])


class FoodWasteIndicatorsTests(base_module.BaseModuleTestCase):
    test_defaults_visible_with_different_lock_holder = None
    test_land_use_change_calculation = None
    test_module_edit_invalidates_cache = None
    test_generic_calculation = None

    def setUp(self):
        self.ModuleClass = models.SolidWaste
        super().setUp()
        landfill = {"swds_uncategorised": 1.0}
        response = self.edit_module(self.module, self.user, stream(
            {"start": 100.0, "w": 60.0, "wo": 100.0},
            {"start": landfill, "w": {"composting": 0.5, "swds_uncategorised": 0.5}, "wo": landfill},
        ))
        self.assertEqual(response.status_code, 200, response.data)

        activity = models.Activity.objects.get(id=self.create_activity(self.project, self.user, [self.module_type]).data["id"])
        self.second = models.SolidWaste.objects.get(activity=activity)
        dumping = {"open_dumping": 1.0}
        response = self.edit_module(self.second, self.user, stream(
            {"start": 50.0, "w": 50.0, "wo": 50.0},
            {"start": dumping, "w": {"anaerobic_digestion": 1.0}, "wo": dumping},
        ))
        self.assertEqual(response.status_code, 200, response.data)

    def _group(self):
        out = indicators.compute_project_indicators(self.project)
        self.assertEqual(out["skipped_activities"], [])
        return next(g for g in out["groups"] if g["id"] == "food_waste")

    def test_sums_over_activities_with_and_without(self):
        group = self._group()
        self.assertTrue(group["available"])
        values = {i["id"]: i for i in group["indicators"]}

        self.assertAlmostEqual(values["food_waste_reference"]["without"], 150.0)
        self.assertAlmostEqual(values["food_waste_target"]["with"], 110.0)
        self.assertAlmostEqual(values["food_waste_reduction"]["value"], 40.0)
        self.assertAlmostEqual(values["food_waste_landfill_reduction"]["value"], 120.0)
        composting = values["food_waste_composting"]
        self.assertAlmostEqual(composting["with"], 30.0)
        self.assertAlmostEqual(composting["without"], 0.0)
        self.assertAlmostEqual(values["food_waste_anaerobic_digestion"]["with"], 50.0)

        series = values["food_waste_reference"]["series"]
        duration = self.project.implementation_years + self.project.capitalization_years
        self.assertEqual(len(series["years"]), duration)
        self.assertEqual(series["years"][0], self.project.start_year_of_activities)
        self.assertAlmostEqual(group["data"]["without"]["swds"], 150.0)
        self.assertAlmostEqual(group["data"]["with"]["anaerobic_digestion"], 50.0)

    def test_excel_indicators_sheet_lists_food_waste(self):
        from io import BytesIO

        import openpyxl

        from api.reports import generate_excel_report

        ws = openpyxl.load_workbook(BytesIO(generate_excel_report(self.project)))["Indicators"]
        labels = [row[0] for row in ws.iter_rows(min_col=1, max_col=1, values_only=True)]
        self.assertIn("Food waste", labels)
        self.assertIn("Food waste valorised by anaerobic digestion", labels)

    def test_cached_module_results_give_the_same_numbers(self):
        cold = self._group()
        warm = self._group()
        self.assertEqual(
            [(i["with"], i["without"], i["value"]) for i in cold["indicators"]],
            [(i["with"], i["without"], i["value"]) for i in warm["indicators"]],
        )
