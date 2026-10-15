"""Guard: a fossil-methane fuel must never feed a None GWP into the math.

Project 9908 on review used "AR5 with Climate Change Feedback", whose
ch4_fossil was NULL, with Charcoal in the with-project scenario. The energy
math multiplied by None and the report failed with an opaque TypeError. The
lookup now fails with a message that names the GWP set.

Run with:
    python manage.py test api.tests.reports.test_fossil_methane_gwp
"""
from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

import api.utilities as utils


def _gwp(ch4_fossil):
    return SimpleNamespace(name="AR5 with feedback", ch4=34.0, ch4_fossil=ch4_fossil)


def _fuel(name):
    return SimpleNamespace(name_en=name)


class MethaneGwpTestCase(SimpleTestCase):
    def test_non_fossil_fuel_uses_ch4(self):
        self.assertEqual(utils.methane_gwp(_gwp(29.8), _fuel("Gasoline (2-stroke)")), 34.0)

    def test_missing_fuel_uses_ch4(self):
        self.assertEqual(utils.methane_gwp(_gwp(None), None), 34.0)

    def test_fossil_fuel_uses_ch4_fossil_case_insensitively(self):
        self.assertEqual(utils.methane_gwp(_gwp(29.8), _fuel("Charcoal")), 29.8)

    def test_zero_ch4_fossil_is_a_value_not_a_fallback(self):
        self.assertEqual(utils.methane_gwp(_gwp(0.0), _fuel("Peat")), 0.0)

    def test_null_ch4_fossil_raises_naming_the_gwp_set(self):
        with self.assertRaisesMessage(ValueError, "AR5 with feedback"):
            utils.methane_gwp(_gwp(None), _fuel("Charcoal"))
