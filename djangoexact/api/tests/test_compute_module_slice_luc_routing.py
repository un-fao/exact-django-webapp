"""Tests that compute_module_slice routes LandUseChange to _compute_luc_slice."""
from unittest.mock import patch

from django.test import SimpleTestCase

from api.services.minitool_compute import compute_module_slice


class ComputeModuleSliceLucRoutingTest(SimpleTestCase):
    def test_landusechange_module_routes_to_luc_slice(self):
        with patch("api.services.luc_compute._compute_luc_slice") as mock_slice:
            mock_slice.return_value = ([{"ok": 1}], [])
            data, errors = compute_module_slice(
                module_type="LandUseChange",
                attribute="module_type",
                from_value="AnnualCropland#0",
                to_value="Grassland#0",
                save_results=False,
            )
            mock_slice.assert_called_once_with(
                from_value="AnnualCropland#0",
                to_value="Grassland#0",
                save_results=False,
                progress_callback=None,
            )
            self.assertEqual(data, [{"ok": 1}])
            self.assertEqual(errors, [])
