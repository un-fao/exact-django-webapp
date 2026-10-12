from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import serializers

from api.serializers import check_member_management_allowed


class _FakeMembers:
    """Stands in for `project.members` so these checks need no database."""

    def __init__(self, admins):
        self.admins = list(admins)

    def filter(self, user=None, group__name=None):
        matched = group__name == "Admin" and any(admin is user for admin in self.admins)
        return SimpleNamespace(exists=lambda: matched)


def _user(is_superuser=False, is_authenticated=True):
    return SimpleNamespace(is_superuser=is_superuser, is_authenticated=is_authenticated)


def _project(is_finalized=False, is_archived=False, admins=()):
    return SimpleNamespace(is_finalized=is_finalized, is_archived=is_archived, members=_FakeMembers(admins))


class FinalizedMemberManagementTestCase(SimpleTestCase):
    """Finalizing a project must not lock its admins out of managing members."""

    def test_admin_can_manage_members_of_finalized_project(self):
        admin = _user()
        check_member_management_allowed(_project(is_finalized=True, admins=[admin]), SimpleNamespace(user=admin))

    def test_superuser_can_manage_members_of_finalized_project(self):
        check_member_management_allowed(_project(is_finalized=True), SimpleNamespace(user=_user(is_superuser=True)))

    def test_non_admin_cannot_manage_members_of_finalized_project(self):
        with self.assertRaises(serializers.ValidationError):
            check_member_management_allowed(_project(is_finalized=True), SimpleNamespace(user=_user()))

    def test_missing_request_is_rejected_not_crashed(self):
        # The membership update endpoints used to build the serializer without a
        # request in its context, so this path raised KeyError (HTTP 500) instead
        # of a validation error whenever the project was finalized.
        with self.assertRaises(serializers.ValidationError):
            check_member_management_allowed(_project(is_finalized=True), None)

    def test_archived_project_is_closed_even_for_admins(self):
        admin = _user()
        with self.assertRaises(serializers.ValidationError):
            check_member_management_allowed(_project(is_archived=True, admins=[admin]), SimpleNamespace(user=admin))

    def test_non_admin_can_manage_members_of_an_open_project(self):
        check_member_management_allowed(_project(), SimpleNamespace(user=_user()))
