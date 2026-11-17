from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import Country, Group, InvitationStatusType, ProjectInvitation, ProjectMembership
from api.tests.factories import ProjectFactory, UserFactory
from api.utilities import InvitationStatus
from ipcc.models import GlobalWarmingPotential


def _status(value):
    return InvitationStatusType.objects.get_or_create(name=value, defaults={"name_en": value})[0]


class MembershipTestBase(APITestCase):
    def setUp(self):
        self.admin_group = Group.objects.get_or_create(name="Admin")[0]
        self.viewer_group = Group.objects.get_or_create(name="Membership Test Viewer")[0]
        self.pending = _status(InvitationStatus.PENDING.value)
        self.accepted = _status(InvitationStatus.ACCEPTED.value)
        country = Country.objects.get_or_create(name="Membership Test Country")[0]
        self.owner = UserFactory(email="membership-owner@example.com")
        self.member = UserFactory(email="membership-member@example.com")
        gwp = GlobalWarmingPotential.objects.create(name="Membership Test GWP", co2=1, ch4=28, n2o=265)
        self.project = ProjectFactory(owner=self.owner, country=country, gw_potential=gwp)
        ProjectMembership.objects.create(user=self.owner, project=self.project, group=self.admin_group)

    def invite(self, user, group, **kwargs):
        return ProjectInvitation.objects.create(
            sender=self.owner, project=self.project, user=user, group=group, status=self.pending, **kwargs
        )


class ProjectMembershipsListTestCase(MembershipTestBase):
    def setUp(self):
        super().setUp()
        ProjectMembership.objects.create(user=self.member, project=self.project, group=self.viewer_group)
        self.client.force_authenticate(self.owner)

    def get(self, query=""):
        with mock.patch("api.views.security.check_permission", return_value=None), \
             mock.patch("api.views.ProjectViewSet.get_object", return_value=self.project):
            return self.client.get(f"/api/projects/{self.project.pk}/memberships/{query}")

    def test_rows_carry_id_and_member_email(self):
        resp = self.get()
        self.assertEqual(resp.status_code, 200)
        row = next(r for r in resp.data if r["user"] == self.member.pk)
        membership = ProjectMembership.objects.get(user=self.member, project=self.project)
        self.assertEqual(row["id"], membership.pk)
        self.assertEqual(row["user_email"], "membership-member@example.com")

    def test_user_param_returns_only_that_users_membership(self):
        resp = self.get(f"?user={self.member.pk}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([r["user"] for r in resp.data], [self.member.pk])

    def test_non_numeric_user_param_is_rejected(self):
        self.assertEqual(self.get("?user=abc").status_code, 400)


class InvitationLinkAcceptTestCase(MembershipTestBase):
    def url(self, invitation):
        return f"/api/project-invitations/accept/{invitation.token}/"

    def memberships(self, user):
        return ProjectMembership.objects.filter(user=user, project=self.project)

    def test_get_only_shows_confirm_page(self):
        invitation = self.invite(self.member, self.viewer_group)
        resp = self.client.get(self.url(invitation))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Accept invitation")
        self.assertFalse(self.memberships(self.member).exists())

    def test_repeated_accept_creates_one_membership(self):
        invitation = self.invite(self.member, self.viewer_group)
        for _ in range(3):
            resp = self.client.post(self.url(invitation))
            self.assertEqual(resp.status_code, 200)
            self.client.get(self.url(invitation))
        self.assertEqual(self.memberships(self.member).count(), 1)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, self.accepted)

    def test_expired_invitation_is_not_accepted(self):
        invitation = self.invite(self.member, self.viewer_group, token_expiry=timezone.now() - timedelta(minutes=1))
        resp = self.client.post(self.url(invitation))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(self.memberships(self.member).exists())

    def test_existing_member_gets_the_invited_role(self):
        ProjectMembership.objects.create(user=self.member, project=self.project, group=self.viewer_group)
        self.client.post(self.url(self.invite(self.member, self.admin_group)))
        self.assertEqual(list(self.memberships(self.member).values_list("group", flat=True)), [self.admin_group.pk])

    def test_owner_is_never_demoted(self):
        self.client.post(self.url(self.invite(self.owner, self.viewer_group)))
        self.assertEqual(list(self.memberships(self.owner).values_list("group", flat=True)), [self.admin_group.pk])


class InAppAcceptTestCase(MembershipTestBase):
    def test_accepting_as_existing_member_keeps_the_membership(self):
        # Used to fall into the "else: delete" branch and remove the membership.
        ProjectMembership.objects.create(user=self.member, project=self.project, group=self.viewer_group)
        invitation = self.invite(self.member, self.viewer_group)
        self.client.force_authenticate(self.member)
        with mock.patch("api.views.security.check_permission", return_value=None):
            resp = self.client.patch(f"/api/project-invitations/{invitation.pk}/", {"status": self.accepted.pk}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ProjectMembership.objects.filter(user=self.member, project=self.project).exists())


class MembershipUniquenessTestCase(MembershipTestBase):
    def test_database_rejects_a_second_membership(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectMembership.objects.create(user=self.owner, project=self.project, group=self.viewer_group)


class MembershipRoleChangeTestCase(MembershipTestBase):
    LAST_ADMIN_ERROR = "Cannot change the role of the last Admin in the project"

    def setUp(self):
        super().setUp()
        change = Permission.objects.get(codename="change_projectmembership")
        self.admin_group.permissions.add(change)
        self.owner_membership = ProjectMembership.objects.get(user=self.owner, project=self.project)
        self.client.force_authenticate(self.owner)

    def url(self, membership):
        return f"/api/project-memberships/{membership.pk}/"

    def patch_group(self, membership, group):
        return self.client.patch(self.url(membership), {"group": group.pk}, format="json")

    def assert_group(self, membership, group):
        membership.refresh_from_db()
        self.assertEqual(membership.group_id, group.pk)

    def test_patch_refuses_demoting_the_last_admin(self):
        resp = self.patch_group(self.owner_membership, self.viewer_group)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(self.LAST_ADMIN_ERROR, str(resp.data))
        self.assert_group(self.owner_membership, self.admin_group)

    def test_put_refuses_demoting_the_last_admin(self):
        body = {"project": self.project.pk, "user": self.owner.pk, "group": self.viewer_group.pk}
        resp = self.client.put(self.url(self.owner_membership), body, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn(self.LAST_ADMIN_ERROR, str(resp.data))
        self.assert_group(self.owner_membership, self.admin_group)

    def test_patch_without_group_skips_the_check(self):
        resp = self.client.patch(self.url(self.owner_membership), {"project": self.project.pk}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assert_group(self.owner_membership, self.admin_group)

    def test_admin_can_be_demoted_when_another_admin_exists(self):
        other = ProjectMembership.objects.create(user=self.member, project=self.project, group=self.admin_group)
        resp = self.patch_group(other, self.viewer_group)
        self.assertEqual(resp.status_code, 200)
        self.assert_group(other, self.viewer_group)

    def test_non_admin_role_change_still_works(self):
        member = ProjectMembership.objects.create(user=self.member, project=self.project, group=self.viewer_group)
        resp = self.patch_group(member, self.admin_group)
        self.assertEqual(resp.status_code, 200)
        self.assert_group(member, self.admin_group)
