"""Tests for the accounting timeline in the FAO report project description.

Run with:
    python manage.py test api.tests.reports.test_timeline
"""
from __future__ import annotations

import re
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


def _render(lang: str, implementation_years: int, capitalization_years: int) -> str:
    project = SimpleNamespace(
        name="P", start_year_of_activities=2027, implementation_years=implementation_years,
        last_year_of_accounting=2027 + implementation_years + capitalization_years, cost=0,
    )
    return render_to_string(f"reports/partials/{lang}/project_description.html", {
        "project": project,
        "capitalization_years": capitalization_years,
        "total_project_years": implementation_years + capitalization_years,
    })


def _widths(html: str) -> tuple[str, str]:
    impl = re.search(r'timeline-implementation" style="width: (\d+)%', html).group(1)
    cap = re.search(r'timeline-capitalization" style="left: (\d+)%', html).group(1)
    return impl, cap


class TimelineTestCase(SimpleTestCase):
    def test_segments_follow_the_real_phase_lengths(self):
        self.assertEqual(_widths(_render("en", 6, 13)), ("32", "32"))
        self.assertEqual(_widths(_render("en", 13, 6)), ("68", "68"))

    def test_phase_labels_carry_year_range_and_duration(self):
        html = _render("en", 6, 13)

        self.assertIn("2027–2033, 6 years", html)
        self.assertIn("2033–2046, 13 years", html)
        self.assertIn("2027–2028, 1 year<", _render("en", 1, 19))

    def test_phase_labels_are_translated(self):
        for lang, labels in {
            "fr": ("Phase d'implémentation", "Phase de capitalisation", "6 ans", "2033–2046, 13 ans"),
            "es": ("Fase de implementación", "Fase de capitalización", "6 años", "2033–2046, 13 años"),
        }.items():
            html = _render(lang, 6, 13)
            for label in labels:
                with self.subTest(lang=lang, label=label):
                    self.assertIn(label, html)

    def test_zero_length_period_renders(self):
        self.assertEqual(_widths(_render("en", 0, 0))[0], "0")
