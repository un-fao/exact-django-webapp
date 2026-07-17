from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from api import utilities as utils
from api.models import AsyncJob, Country, Group, ProjectMembership
from api.tests.factories import ActivityFactory, ProjectFactory, UserFactory


class CopyProjectMembershipTestCase(TestCase):
    """Task 9: copy_project split into create_project_shell + copy_activities_into,
    plus the fix for the Admin-membership bug (checked the source project, not the
    copy) and the double-membership bug in ProjectViewSet.copy.
    """

    def setUp(self):
        # The suite normally seeds "Admin" via the test_seed_data fixture (loaded in
        # CI before manage.py test), but this test file must not depend on that
        # external step running, so ensure the group exists here too.
        Group.objects.get_or_create(name="Admin")
        self.country = Country.objects.filter(region__isnull=False).order_by("?").first() or Country.objects.first()

    def test_copy_creates_exactly_one_admin_membership(self):
        owner = UserFactory(email="copy-owner-1@example.com")
        source = ProjectFactory(owner=owner, country=self.country)

        new_project = utils.copy_project(source, owner)

        admin_memberships = ProjectMembership.objects.filter(
            project=new_project, user=owner, group__name="Admin",
        )
        self.assertEqual(admin_memberships.count(), 1)

    def test_shell_has_no_activities_but_project_row_exists(self):
        owner = UserFactory(email="copy-owner-2@example.com")
        source = ProjectFactory(owner=owner, country=self.country)

        shell = utils.create_project_shell(source, owner)

        self.assertIsNotNone(shell.pk)
        self.assertNotEqual(shell.pk, source.pk)
        self.assertEqual(shell.activities.count(), 0)
        self.assertFalse(shell.is_finalized)
        self.assertFalse(shell.is_public)


class CopyAsyncEndpointTestCase(APITestCase):
    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        self.country = Country.objects.filter(region__isnull=False).order_by("?").first() or Country.objects.first()
        self.user = UserFactory(email="copy-async-user@example.com")
        self.client.force_authenticate(self.user)

    @override_settings(PROJECT_COPY_ASYNC_THRESHOLD=1000)
    def test_small_project_copies_inline_201(self):
        # Empty project: activity_count + module_count == 0 <= 1000 -> sync path.
        project = ProjectFactory(owner=self.user, country=self.country)
        with mock.patch("api.views.security.check_permission", return_value=None), \
             mock.patch("api.views.ProjectViewSet.get_object", return_value=project):
            resp = self.client.post(f"/api/projects/{project.pk}/copy/async/")
        self.assertEqual(resp.status_code, 201)
        self.assertNotEqual(resp.data["id"], project.pk)

    @override_settings(PROJECT_COPY_ASYNC_THRESHOLD=0)
    def test_large_project_offloads_202(self):
        # An empty project would route sync here (0 + 0 <= 0 is True), so give it
        # one activity: activity_count=1, module_count=0 -> 1 > threshold(0) -> async.
        project = ProjectFactory(owner=self.user, country=self.country)
        ActivityFactory(project=project)
        with mock.patch("api.views.security.check_permission", return_value=None), \
             mock.patch("api.views.ProjectViewSet.get_object", return_value=project):
            resp = self.client.post(f"/api/projects/{project.pk}/copy/async/")
        self.assertEqual(resp.status_code, 202)
        self.assertIn("job_id", resp.data)
        self.assertIn("new_project_id", resp.data)
        job = AsyncJob.objects.get(pk=resp.data["job_id"])
        self.assertEqual(job.kind, AsyncJob.Kind.PROJECT_COPY)
        # The shell must exist synchronously even though the copy is offloaded.
        self.assertNotEqual(resp.data["new_project_id"], project.pk)


class CopyJobRunTestCase(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        self.country = Country.objects.filter(region__isnull=False).order_by("?").first() or Country.objects.first()

    def test_run_populates_target(self):
        from api.services import copy_jobs

        owner = UserFactory(email="copy-job-owner@example.com")
        source = ProjectFactory(owner=owner, country=self.country)
        ActivityFactory(project=source)
        target = utils.create_project_shell(source, owner)
        job = AsyncJob.objects.create(
            kind=AsyncJob.Kind.PROJECT_COPY, created_by=owner,
            params={"source_project_id": source.pk, "target_project_id": target.pk},
        )

        result = copy_jobs.run(job)

        self.assertEqual(result["new_project_id"], target.pk)
        self.assertEqual(target.activities.count(), source.activities.count())
