"""The public API returns the same payload shape as the private API.

The frontend renders public projects with the components it uses for private ones, so
it reads related entities as IDs. When #316 moved the private API to IDs and the public
API kept nested objects, public activities lost their builder steps and opened straight
on the "Activity complete" page.
"""

from unittest import mock

from django.conf import settings
from django.test import override_settings
from rest_framework.test import APITestCase

from api.models import Group, ModuleType
from api.tests.factories import ActivityFactory, InputFactory, ProjectFactory, UserFactory
from api.tests.test_finalized_results_frozen import payload
from api.tests.test_project_guided_step import pick_country


def serial_map(func, items, **kwargs):
    return [func(item) for item in items]


# Both stand-ins keep every request inside the test transaction. Worker threads open
# their own connections, which cannot see uncommitted rows, and DatabaseConnectionMiddleware
# closes all connections after each response, ending the transaction for the next test.
@mock.patch("api.concurrency.map_in_bounded_threads", serial_map)
@override_settings(MIDDLEWARE=[m for m in settings.MIDDLEWARE if m != "minitool.middleware.DatabaseConnectionMiddleware"])
class PublicApiShapeTestCase(APITestCase):
    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        self.owner = UserFactory(email="public-shape@example.com")
        self.project = ProjectFactory(owner=self.owner, country=pick_country(), is_public=True)
        self.activity = ActivityFactory(project=self.project, owner=self.owner, name="Public activity")
        self.activity.module_types.add(ModuleType.objects.get(class_name="Input"))
        self.module = InputFactory(activity=self.activity)

    def get(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content[:300])
        return response.json()

    def assert_module_summary(self, module):
        self.assertEqual(module["id"], self.module.pk)
        self.assertIsInstance(module["module_type"], int)
        self.assertIsInstance(module["status"], int)
        self.assertEqual(module["endpoint_url"], "api/public/inputs/")

    def test_project_returns_related_entities_as_ids(self):
        data = self.get(f"/api/public/projects/{self.project.pk}/")

        self.assertEqual(data["country"], self.project.country_id)
        self.assertEqual(data["gw_potential"], self.project.gw_potential_id)
        self.assertNotIn("owner", data)
        self.assertNotIn("role", data)
        self.assertNotIn("note", data)

    def test_activity_returns_ids_and_module_summaries(self):
        data = self.get(f"/api/public/activities/{self.activity.pk}/")

        self.assertEqual(data["project"], self.project.pk)
        self.assertEqual(data["module_types"], [ModuleType.objects.get(class_name="Input").pk])
        self.assertNotIn("owner", data)
        self.assertEqual(len(data["modules"]), 1)
        self.assert_module_summary(data["modules"][0])

    def test_activity_list_returns_module_summaries(self):
        data = self.get(f"/api/public/activities/?project_id={self.project.pk}")

        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["project"], self.project.pk)
        self.assert_module_summary(data["results"][0]["modules"][0])

    def test_activity_modules_returns_module_summaries(self):
        data = self.get(f"/api/public/activities/{self.activity.pk}/modules/")

        self.assertEqual(data["count"], 1)
        self.assert_module_summary(data["results"][0])

    def test_module_list_returns_related_entities_as_ids(self):
        data = self.get(f"/api/public/inputs/?activity={self.activity.pk}")

        self.assertEqual(data[0]["activity"], self.activity.pk)
        self.assertIsInstance(data[0]["status"], int)
        self.assertNotIn("note", data[0])

    def test_activity_results_still_serve_module_results(self):
        with mock.patch("api.services.finalization.compute_module_results", side_effect=lambda module: payload(4.0)):
            data = self.get(f"/api/public/activities/{self.activity.pk}/results/")

        self.assertEqual(len(data["modules"]), 1)
        self.assertEqual(data["modules"][0]["id"], self.module.pk)
        self.assertEqual(data["modules"][0]["results"]["balance"], 4.0)

    def test_private_project_stays_hidden(self):
        self.project.is_public = False
        self.project.save()

        self.assertEqual(self.client.get(f"/api/public/projects/{self.project.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/public/activities/{self.activity.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/public/activities/{self.activity.pk}/modules/").status_code, 404)
