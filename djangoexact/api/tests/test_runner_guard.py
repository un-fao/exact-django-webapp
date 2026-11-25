"""SeededTestRunner refuses production and review settings before touching any database."""

from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from django.test.runner import DiscoverRunner

from api.tests.runner import SeededTestRunner, refuse_deployed_settings


class RefuseDeployedSettingsTestCase(SimpleTestCase):
    def test_raises_for_deployed_app_modes(self):
        for app_mode in ("production", "review"):
            with self.subTest(app_mode=app_mode), mock.patch.dict("os.environ", {"APP_MODE": app_mode}):
                with self.assertRaisesMessage(ImproperlyConfigured, f"APP_MODE='{app_mode}'"):
                    refuse_deployed_settings()

    def test_allows_local_app_modes(self):
        for app_mode in ("", "develop", "local"):
            with self.subTest(app_mode=app_mode), mock.patch.dict("os.environ", {"APP_MODE": app_mode}):
                refuse_deployed_settings()

    def test_setup_databases_refuses_before_creating_any_database(self):
        with mock.patch.dict("os.environ", {"APP_MODE": "production"}), mock.patch.object(DiscoverRunner, "setup_databases") as super_setup:
            with self.assertRaises(ImproperlyConfigured):
                SeededTestRunner().setup_databases()
        super_setup.assert_not_called()
