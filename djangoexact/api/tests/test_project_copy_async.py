from django.test import TestCase

from api import utilities as utils
from api.models import Country, Group, ProjectMembership
from api.tests.factories import ProjectFactory, UserFactory


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
