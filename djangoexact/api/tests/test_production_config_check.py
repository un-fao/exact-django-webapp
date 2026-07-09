"""DB-free unit tests for the production config deploy check.

Exercises api.checks.check_production_config directly (no manage.py
check invocation, no database) across the unsafe and safe env
combinations described in 01-01-PLAN.md.
"""

import os
from unittest.mock import patch

from django.core.checks.registry import registry
from django.test import SimpleTestCase, override_settings

from api.checks import check_production_config


class ProductionConfigCheckTests(SimpleTestCase):
    def test_production_debug_true_flags_e001(self):
        with patch.dict(os.environ, {"APP_MODE": "production"}):
            with override_settings(DEBUG=True, CORS_ALLOWED_ORIGINS=["https://exact.apps.fao.org"]):
                result = check_production_config(None)
        ids = [err.id for err in result]
        self.assertIn("api.E001", ids)

    def test_production_empty_cors_flags_e002(self):
        with patch.dict(os.environ, {"APP_MODE": "production"}):
            with override_settings(DEBUG=False, CORS_ALLOWED_ORIGINS=[]):
                result = check_production_config(None)
        ids = [err.id for err in result]
        self.assertIn("api.E002", ids)

    def test_production_safe_config_passes(self):
        with patch.dict(os.environ, {"APP_MODE": "production"}):
            with override_settings(DEBUG=False, CORS_ALLOWED_ORIGINS=["https://exact.apps.fao.org"]):
                result = check_production_config(None)
        self.assertEqual(result, [])

    def test_non_production_is_silent(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APP_MODE", None)
            with override_settings(DEBUG=True, CORS_ALLOWED_ORIGINS=[]):
                result = check_production_config(None)
        self.assertEqual(result, [])

    def test_check_is_registered_for_deploy(self):
        """Guard the wiring itself: removing `from . import checks` in
        ApiConfig.ready() must fail this test, not silently disable the
        production guard (WR-01)."""
        self.assertIn(check_production_config, registry.deployment_checks)
