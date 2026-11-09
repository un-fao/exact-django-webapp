"""401 means the token was not accepted; 403 means signed in but not allowed (#415).

The web client refreshes the session on an authentication failure. While both cases
answered 403 it could not tell them apart, so a real permission denial triggered a
refresh, and a failed refresh logged the user out.

These go through the real FirebaseAuthentication and real endpoints; only Firebase's
token verification is patched.
"""

from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.db import DatabaseError
from firebase_admin import auth as firebase_admin_auth
from rest_framework.test import APIClient, APITestCase

from api import security
from api.models import CustomUser, Group, ProjectMembership
from api.tests.factories import ActivityFactory, ProjectFactory, UserFactory
from api.tests.test_project_guided_step import pick_country

VERIFY = "accounts.firebase.firebase_admin_auth.verify_id_token"


class AuthenticationStatusTestCase(APITestCase):
    def setUp(self):
        self.member = UserFactory(email="auth-member@example.com", firebase_uid="authmember")
        self.outsider = UserFactory(email="auth-outsider@example.com", firebase_uid="authoutsider")
        project = ProjectFactory(owner=self.member, country=pick_country())
        ProjectMembership.objects.create(user=self.member, project=project, group=Group.objects.get_or_create(name="Admin")[0])
        self.project = project
        activity = ActivityFactory(project=project, owner=self.member)
        # IsPublicOrAuthenticated (like every module viewset), then security.check_permission.
        self.permission_checked_url = f"/api/projects/{project.pk}/"
        # Plain IsAuthenticated.
        self.authenticated_only_url = f"/api/activities/{activity.pk}/modules/"

    def get_with_token(self, url, verify, client=None):
        with mock.patch(VERIFY, **verify):
            return (client or self.client).get(url, HTTP_AUTHORIZATION="Bearer some-token")

    def assert_authentication_failure(self, response):
        self.assertEqual(response.status_code, 401, response.data)
        self.assertTrue(response["WWW-Authenticate"].startswith("Bearer"))

    def test_expired_token_is_401(self):
        expired = firebase_admin_auth.ExpiredIdTokenError("Token expired", cause=None)
        response = self.get_with_token(self.permission_checked_url, {"side_effect": expired})

        self.assert_authentication_failure(response)
        self.assertIn("expired", response.json()["detail"])

    def test_invalid_token_is_401(self):
        invalid = firebase_admin_auth.InvalidIdTokenError("Bad signature")
        self.assert_authentication_failure(self.get_with_token(self.permission_checked_url, {"side_effect": invalid}))

    def test_malformed_token_is_401(self):
        self.assert_authentication_failure(self.get_with_token(self.permission_checked_url, {"side_effect": ValueError("Illegal ID token")}))

    def test_token_of_an_unknown_user_is_401(self):
        self.assert_authentication_failure(self.get_with_token(self.permission_checked_url, {"return_value": {"uid": "nobody"}}))

    def test_no_token_on_an_authenticated_only_route_is_401(self):
        self.assert_authentication_failure(self.client.get(self.authenticated_only_url))

    def test_no_token_on_a_permission_checked_route_is_401(self):
        self.assert_authentication_failure(self.client.get(self.permission_checked_url))

    def test_check_permission_answers_anonymous_callers_with_401(self):
        # Views that allow anonymous callers and still call check_permission would otherwise
        # answer 403, which the client reads as "signed in but not allowed".
        response = security.check_permission("view_project", AnonymousUser(), self.project)

        self.assert_authentication_failure(response)

    def test_check_permission_answers_signed_in_outsiders_with_403(self):
        response = security.check_permission("view_project", self.outsider, self.project)

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("WWW-Authenticate", response)

    def test_signed_in_user_without_permission_is_403(self):
        response = self.get_with_token(self.permission_checked_url, {"return_value": {"uid": self.outsider.firebase_uid}})

        self.assertEqual(response.status_code, 403, response.content[:300])
        self.assertNotIn("WWW-Authenticate", response)

    def test_signed_in_member_is_allowed(self):
        response = self.get_with_token(self.permission_checked_url, {"return_value": {"uid": self.member.firebase_uid}})

        self.assertEqual(response.status_code, 200, response.content[:300])

    def test_key_fetch_failure_is_a_server_error_not_401(self):
        outage = firebase_admin_auth.CertificateFetchError("Could not fetch certificates", cause=None)
        response = self.get_with_token(self.permission_checked_url, {"side_effect": outage}, client=APIClient(raise_request_exception=False))

        self.assertEqual(response.status_code, 500)

    def test_database_failure_is_a_server_error_not_401(self):
        user_model = mock.Mock(DoesNotExist=CustomUser.DoesNotExist)
        user_model.objects.get.side_effect = DatabaseError("connection refused")
        with mock.patch("accounts.firebase.User", user_model):
            response = self.get_with_token(
                self.permission_checked_url,
                {"return_value": {"uid": self.member.firebase_uid}},
                client=APIClient(raise_request_exception=False),
            )

        self.assertEqual(response.status_code, 500)
