"""Guard: each language must print the figure its own label promises.

main_impact is chosen once, in _compute_activity_contexts, with the precedence
land use > fishery > livestock. Every per-language partial then prints the
matching number itself, and the two have to agree.

They did not. The es and fr partials had no livestock case, so a livestock
activity fell through to the else branch and printed activity.area - which is
get_land_modules_area(), zero for an activity with no land modules. A Spanish
report read "0 cabezas de ganado" where the head count belonged: a wrong
number under a correct label, which is worse than an obvious gap.

This renders the partials directly rather than a whole report, because the
number and its label are the only thing under test.

Run with:
    python manage.py test api.tests.reports.test_activity_breakdown_units
"""
from __future__ import annotations

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

LANGS = ("en", "es", "fr")

HEADS = 4321
AREA = 8765
CATCH = 210


def _activity(*, is_luc=False, is_fishery=False, is_livestock=False, main_impact="units"):
    """A stand-in activity.

    Deliberately not a Mock: Django skips calling any attribute whose
    do_not_call_in_templates is truthy, and a Mock auto-creates that attribute,
    so {{ activity.heads }} would render the Mock's repr instead of the count.
    """
    return SimpleNamespace(
        name="Sample activity",
        is_luc=is_luc,
        is_fishery=is_fishery,
        is_livestock=is_livestock,
        # heads is a method on the real model; area and catch are properties.
        heads=lambda: HEADS,
        area=AREA,
        catch=CATCH,
        main_impact=main_impact,
        secondary_impacts=None,
        start_year=2020,
        implementation_years=5,
        last_year_of_accounting=2027,
        results={"balance": -1000.0},
        modules_emissions=[],
    )


def _render(lang, activity):
    return " ".join(
        render_to_string(
            f"reports/partials/{lang}/activity_breakdown.html",
            {"activities_total": [activity]},
        ).split()
    )


class TestActivityBreakdownPrintsTheRightFigure(SimpleTestCase):
    def test_livestock_head_count_reaches_every_language(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                html = _render(lang, _activity(is_livestock=True, main_impact="livestock heads"))
                self.assertIn(str(HEADS), html)
                self.assertNotIn(str(AREA), html)

    def test_land_use_area_reaches_every_language(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                html = _render(lang, _activity(is_luc=True, main_impact="hectares"))
                self.assertIn(str(AREA), html)
                self.assertNotIn(str(HEADS), html)

    def test_fishery_catch_reaches_every_language(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                html = _render(lang, _activity(is_fishery=True, main_impact="tonnes of catch"))
                self.assertIn(str(CATCH), html)
                self.assertNotIn(str(HEADS), html)
