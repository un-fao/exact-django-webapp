"""Tests for api.reports.charts.

Run with:
    python manage.py test api.tests.reports.test_charts
"""
from __future__ import annotations

import base64

from django.template.defaultfilters import floatformat
from django.test import SimpleTestCase
from django.utils import translation

from api.reports import charts

ZERO_GASES = {"CO2": 0.0, "CH4": 0.0, "N2O": 0.0, "CO": 0.0, "DOC": 0.0, "OTHER": 0.0}


def _gases(**values: float) -> dict[str, float]:
    return {**ZERO_GASES, **values}


class DivergingBottomsTestCase(SimpleTestCase):
    def test_negatives_stack_down_from_zero_not_over_positives(self):
        rows = [[100.0, -40.0], [-30.0, -10.0], [20.0, 5.0]]

        bottoms = charts.diverging_bottoms(rows)

        self.assertEqual(bottoms, [[0.0, 0.0], [0.0, -40.0], [100.0, 0.0]])

    def test_empty_input(self):
        self.assertEqual(charts.diverging_bottoms([]), [])


class GasRowsTestCase(SimpleTestCase):
    def test_drops_all_zero_series_and_folds_minor_gases_into_other(self):
        rows = charts.gas_rows(_gases(CO2=10.0, CO=1.0, DOC=2.0), _gases(CO2=4.0))

        self.assertEqual(
            [(label, values) for label, values, _color in rows],
            [("CO$_2$", [10.0, 4.0, 6.0]), ("Other", [3.0, 0.0, 3.0])],
        )

    def test_gas_keeps_its_color_when_other_gases_are_absent(self):
        rows = charts.gas_rows(_gases(N2O=5.0), ZERO_GASES)

        self.assertEqual(rows[0][2], "#1baf7a")


class LocalizationTestCase(SimpleTestCase):
    def test_scenario_and_other_labels_follow_active_language(self):
        expected = {
            "fr": (["Avec projet", "Sans projet", "Bilan"], "Autres"),
            "es": (["Con proyecto", "Sin proyecto", "Balance"], "Otros"),
            "ru": (["С проектом", "Без проекта", "Баланс"], "Прочие"),
        }
        for lang, (scenarios, other) in expected.items():
            with self.subTest(lang=lang), translation.override(lang):
                self.assertEqual(charts.scenario_labels(), scenarios)
                self.assertEqual(charts.gas_rows(_gases(DOC=1.0), ZERO_GASES)[0][0], other)

    def test_net_total_marker_is_named_in_each_language(self):
        expected = {
            "en": ("Net total", "Net: 5"),
            "fr": ("Total net", "Net : 5"),
            "es": ("Total neto", "Neto: 5"),
            "ru": ("Итого (нетто)", "Нетто: 5"),
        }
        for lang, (legend, label) in expected.items():
            with self.subTest(lang=lang), translation.override(lang):
                self.assertEqual(translation.gettext("Net total"), legend)
                self.assertEqual(translation.gettext("Net: %(value)s") % {"value": "5"}, label)

    def test_numbers_match_the_figures_in_the_report_text(self):
        # The partials render figures with floatformat:"2g". The older
        # floatformat:2|intcomma gave "-1,234,567,89" outside English.
        value = -1234567.891
        for lang in ("en", "fr", "es", "ru"):
            with self.subTest(lang=lang), translation.override(lang):
                self.assertEqual(charts._fmt(value), floatformat(value, "2g"))
        with translation.override("fr"):
            self.assertEqual(charts._fmt(value), "-1\xa0234\xa0567,89")

    def test_half_cent_sums_round_like_the_report_text(self):
        # 58210.30 + 141870.55 + 18402.90 is stored as 218483.7499...; the text shows .75.
        total = 58_210.30 + 141_870.55 + 18_402.90
        with translation.override("en"):
            self.assertEqual(charts._fmt(total), "218,483.75")
            self.assertEqual(charts._fmt(96_450.10 - 141_870.55), "-45,420.45")


class RenderTestCase(SimpleTestCase):
    def _assert_svg(self, b64: str) -> None:
        self.assertTrue(base64.b64decode(b64).lstrip().startswith(b"<?xml"))

    def test_charts_render_for_edge_case_inputs(self):
        cases = {
            "all zero": (0.0, 0.0, 0.0, ZERO_GASES, ZERO_GASES),
            "net sink": (-50_000.0, 120_000.0, -170_000.0, _gases(CO2=-60_000.0, N2O=10_000.0),
                         _gases(CO2=100_000.0, CH4=20_000.0)),
            "mixed signs": (1_234_567.0, -3.5, 1_234_570.5, _gases(CO2=2e6, CH4=-8e5, DOC=34_567.0),
                            _gases(CH4=-3.5)),
        }
        for name, (w, wo, bal, gw, gwo) in cases.items():
            with self.subTest(name), translation.override("ru"):
                self._assert_svg(charts.chart_project_balance(w, wo, bal))
                self._assert_svg(charts.chart_gases_w_wo(gw, gwo))
