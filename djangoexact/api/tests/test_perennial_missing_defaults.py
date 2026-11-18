"""Perennial cropland defaults must say "no default" when the IPCC row is missing.

Regression: an Orchard in a Tropical/Dry project has no IPCC AGB growth row. The
calculator tolerates the miss when the user supplied a tier-2 value and keeps an
unsaved placeholder row whose ``value`` is 0, which the UI showed as "Default = 0.00".
"""

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

import ipcc.models as ipcc
from api.defaults import PerennialCroplandDefaults


class _StubCalculator:
    """Stands in for PerennialCropCalculator: rows not set explicitly come back as plain 1.0 values."""

    rows: dict = {}

    def __init__(self, module):
        for name, row in self.rows.items():
            setattr(self, name, row)

    def get_defaults(self, calculate=False):
        pass

    def __getattr__(self, name):
        return SimpleNamespace(value=1.0)


def _module(start: bool, w: bool, wo: bool):
    project = SimpleNamespace(climate="tropical", moisture="dry", soil_type="lac")
    activity = SimpleNamespace(soc=None, climate_t2=None, moisture_t2=None, project=project)
    return SimpleNamespace(activity=activity, land_use_change=None, is_start=lambda: start, is_with=lambda: w, is_without=lambda: wo)


class PerennialMissingIpccDefaultsTestCase(SimpleTestCase):
    def _defaults(self, rows, start=True, w=True, wo=True):
        stub = type("Stub", (_StubCalculator,), {"rows": rows})
        with mock.patch("api.defaults.calcs.PerennialCropCalculator", stub):
            return PerennialCroplandDefaults(_module(start, w, wo)).get_defaults(calculate=True)

    def test_missing_ipcc_rows_report_no_default(self):
        values = self._defaults({
            "agb_rate_start_default": ipcc.PerennialAGB(),
            "agb_rate_w_default": ipcc.PerennialAGB(),
            "agb_rate_wo_default": ipcc.PerennialAGB(),
            "bgb_start_default": ipcc.PerennialBGB(),
            "bgb_w_default": ipcc.PerennialBGB(),
            "bgb_wo_default": ipcc.PerennialBGB(),
            "agb_max_start_default": ipcc.PerennialMaxAGB(),
            "agb_max_w_default": ipcc.PerennialMaxAGB(),
            "agb_max_wo_default": ipcc.PerennialMaxAGB(),
        })

        for field in ("agb_rate", "bgb", "agb_max"):
            for scenario in ("start", "w", "wo"):
                name = f"{field}_t2_{scenario}_default"
                self.assertIsNone(getattr(values, name), name)
                self.assertIsNone(getattr(values, f"{name}_min"), name)
                self.assertIsNone(getattr(values, f"{name}_max"), name)

    def test_found_ipcc_rows_keep_their_values_including_zero(self):
        values = self._defaults({
            "agb_rate_w_default": ipcc.PerennialAGB(pk=1, value=0.43, value_min=0.2, value_max=0.6),
            "bgb_w_default": ipcc.PerennialBGB(pk=2, value=0.0),
            "agb_max_w_default": ipcc.PerennialMaxAGB(pk=3, value=8.5),
            "agb_rate_start_default": ipcc.PerennialAGB(),
            "agb_rate_wo_default": ipcc.PerennialAGB(),
            "agb_max_start_default": ipcc.PerennialMaxAGB(),
            "agb_max_wo_default": ipcc.PerennialMaxAGB(),
        }, start=False, wo=False)

        self.assertEqual(values.agb_rate_t2_w_default, 0.43)
        self.assertEqual((values.agb_rate_t2_w_default_min, values.agb_rate_t2_w_default_max), (0.2, 0.6))
        # A real IPCC zero is a default, not a missing one.
        self.assertEqual(values.bgb_t2_w_default, 0.0)
        self.assertEqual(values.agb_max_t2_w_default, 8.5)
        # Absent scenarios borrow the with-project max AGB, as before.
        self.assertEqual(values.agb_max_t2_start_default, 8.5)
        self.assertIsNone(values.agb_rate_t2_start_default)
