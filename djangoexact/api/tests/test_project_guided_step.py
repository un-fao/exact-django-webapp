"""Tests for Project.guided_step, the frontend tour checkpoint.

A project is guided if and only if guided_step is not null. The field is written
through the regular project PATCH, so these tests pin the side effects that must
not happen on a tour step: wiping module result caches, and being refused on a
finalized project.
"""

from unittest import mock

from django.test import TestCase
from rest_framework.test import APITestCase

from api import utilities as utils
from api.models import Country, Group
from api.serializers import ProjectExportSerializer, ProjectSummarySerializer, ReadProjectSerializer
from api.tests.factories import ProjectFactory, UserFactory


def pick_country():
    return Country.objects.filter(region__isnull=False).order_by("?").first() or Country.objects.first()


class GuidedStepSerializationTestCase(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        self.user = UserFactory(email="guided-serialization@example.com")
        self.project = ProjectFactory(owner=self.user, country=pick_country(), guided_step="activities.intro")

    def test_defaults_to_null(self):
        project = ProjectFactory(owner=self.user, country=pick_country())
        self.assertIsNone(project.guided_step)

    def test_detail_and_summary_return_the_step(self):
        self.assertEqual(ReadProjectSerializer(self.project).data["guided_step"], "activities.intro")
        self.assertEqual(ProjectSummarySerializer(self.project).data["guided_step"], "activities.intro")

    def test_export_omits_the_step(self):
        self.assertNotIn("guided_step", ProjectExportSerializer(self.project).data)

    def test_copy_is_not_guided(self):
        shell = utils.create_project_shell(self.project, self.user)
        shell.refresh_from_db()
        self.assertIsNone(shell.guided_step)


class GuidedStepPatchTestCase(APITestCase):
    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        self.user = UserFactory(email="guided-patch@example.com")
        self.client.force_authenticate(self.user)
        self.project = ProjectFactory(owner=self.user, country=pick_country(), guided_step="activities.intro")

    def patch_project(self, payload):
        # _check_lock_expiration reads a seeded ApplicationParameter that is irrelevant here.
        with mock.patch("api.views.security.check_permission", return_value=None), \
             mock.patch("api.views.ProjectViewSet.get_object", return_value=self.project), \
             mock.patch("api.models.Project._check_lock_expiration"):
            return self.client.patch(f"/api/projects/{self.project.pk}/", payload, format="json")

    def test_patch_advances_the_step(self):
        resp = self.patch_project({"guided_step": "results.carbonBalance"})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["guided_step"], "results.carbonBalance")
        self.project.refresh_from_db()
        self.assertEqual(self.project.guided_step, "results.carbonBalance")

    def test_patch_null_ends_the_tutorial(self):
        resp = self.patch_project({"guided_step": None})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.project.refresh_from_db()
        self.assertIsNone(self.project.guided_step)

    def test_patch_does_not_invalidate_module_caches(self):
        with mock.patch("api.models.invalidate_module_caches") as invalidate:
            resp = self.patch_project({"guided_step": "assessment.openActivity"})
        self.assertEqual(resp.status_code, 200, resp.data)
        invalidate.assert_not_called()

    def test_patch_is_allowed_on_a_finalized_project(self):
        self.project.is_finalized = True
        self.project.save()

        resp = self.patch_project({"guided_step": None})

        self.assertEqual(resp.status_code, 200, resp.data)
        self.project.refresh_from_db()
        self.assertIsNone(self.project.guided_step)

    def test_finalized_project_still_rejects_step_mixed_with_content(self):
        self.project.is_finalized = True
        self.project.save()

        resp = self.patch_project({"guided_step": None, "code": "changed"})

        self.assertEqual(resp.status_code, 400)

    def test_invalid_steps_are_rejected(self):
        for bad in ["", "activities intro", "activities.", ".intro", "step1", "a" * 65]:
            with self.subTest(step=bad):
                resp = self.patch_project({"guided_step": bad})
                self.assertEqual(resp.status_code, 400)
                self.assertIn("guided_step", resp.data)
