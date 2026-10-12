"""Tests for Firebase error handling.

These run without a database, so they all use ``SimpleTestCase``.

``LoginExistingUserView.post`` is decorated with ``@transaction.atomic``, which
opens a connection to the default database before any of the body runs, while
``SimpleTestCase`` blocks database access. That view therefore cannot be
exercised through the HTTP layer here. Two approaches cover it instead:

- the pieces it delegates to are tested directly, namely ``FirebaseAuth``, which
  turns every transport and body failure into a typed exception, and
  ``firebase_error_response``, which maps those exceptions onto responses;
- for a branch that has to run in the view itself, ``post.__wrapped__`` is the
  undecorated function that ``functools.wraps`` keeps on the wrapper, so calling
  it skips the atomic block and needs no connection.

``TokenRefreshView.post`` dropped its ``@transaction.atomic`` (it performs no DB
writes), so it can be driven directly if a test ever needs to.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import SSLError, Timeout

from accounts.firebase_auth import (
    FirebaseAuth,
    FirebaseAuthError,
    FirebaseError,
    FirebaseResponseError,
    FirebaseUnavailableError,
    parse_firebase_error,
)
from accounts.views import (
    FIREBASE_INVALID_RESPONSE_MESSAGE,
    FIREBASE_UNAVAILABLE_MESSAGE,
    LoginExistingUserView,
    firebase_error_response,
)
from api.models import CustomUser as User

TOKEN_EXPIRED_BODY = json.dumps({"error": {"code": 400, "message": "TOKEN_EXPIRED", "errors": []}})
INVALID_CREDENTIALS_BODY = json.dumps({"error": {"code": 400, "message": "INVALID_LOGIN_CREDENTIALS"}})
PROXY_HTML_BODY = "<html><head><title>502 Bad Gateway</title></head><body>nginx</body></html>"


class FakeResponse:
    """Minimal stand-in for ``requests.Response`` with the attributes we use."""

    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        # requests raises a JSONDecodeError, which is a ValueError subclass.
        return json.loads(self.text)


class ParseFirebaseErrorTestCase(SimpleTestCase):
    """The single body parser must never raise, whatever Firebase sends back."""

    def test_documented_shape_yields_code_and_payload(self):
        code, payload = parse_firebase_error(TOKEN_EXPIRED_BODY)
        self.assertEqual(code, "TOKEN_EXPIRED")
        self.assertEqual(payload["error"]["code"], 400)

    def test_non_json_body_yields_nothing(self):
        self.assertEqual(parse_firebase_error(PROXY_HTML_BODY), (None, None))

    def test_empty_body_yields_nothing(self):
        self.assertEqual(parse_firebase_error(""), (None, None))
        self.assertEqual(parse_firebase_error(None), (None, None))

    def test_json_array_yields_nothing(self):
        self.assertEqual(parse_firebase_error('["nope"]'), (None, None))

    def test_json_object_without_error_key_yields_payload_only(self):
        code, payload = parse_firebase_error('{"unexpected": true}')
        self.assertIsNone(code)
        self.assertEqual(payload, {"unexpected": True})

    def test_error_key_that_is_not_an_object_yields_payload_only(self):
        code, payload = parse_firebase_error('{"error": "TOKEN_EXPIRED"}')
        self.assertIsNone(code)
        self.assertEqual(payload, {"error": "TOKEN_EXPIRED"})

    def test_message_that_is_not_a_string_yields_payload_only(self):
        code, payload = parse_firebase_error('{"error": {"message": 42}}')
        self.assertIsNone(code)
        self.assertEqual(payload, {"error": {"message": 42}})


class FirebaseAuthExceptionTestCase(SimpleTestCase):
    """Every transport and body failure must surface as a typed FirebaseError."""

    def setUp(self):
        self.client = FirebaseAuth("test-api-key")

    def _patch_post(self, **kwargs):
        return patch("accounts.firebase_auth.requests.post", **kwargs)

    def test_http_error_with_documented_body_carries_the_code(self):
        with self._patch_post(return_value=FakeResponse(400, TOKEN_EXPIRED_BODY)):
            with self.assertRaises(FirebaseAuthError) as ctx:
                self.client.refresh("stale-token")

        self.assertEqual(ctx.exception.code, "TOKEN_EXPIRED")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.payload["error"]["message"], "TOKEN_EXPIRED")

    def test_invalid_login_credentials_keeps_its_code(self):
        with self._patch_post(return_value=FakeResponse(400, INVALID_CREDENTIALS_BODY)):
            with self.assertRaises(FirebaseAuthError) as ctx:
                self.client.sign_in_with_email_and_password("user@example.com", "wrong")

        self.assertEqual(ctx.exception.code, "INVALID_LOGIN_CREDENTIALS")

    def test_http_error_with_non_json_body_has_no_code(self):
        with self._patch_post(return_value=FakeResponse(502, PROXY_HTML_BODY)):
            with self.assertLogs("console", level="WARNING"):
                with self.assertRaises(FirebaseAuthError) as ctx:
                    self.client.refresh("token")

        self.assertIsNone(ctx.exception.code)
        self.assertEqual(ctx.exception.payload, {})
        self.assertEqual(ctx.exception.status_code, 502)

    def test_http_error_with_unexpected_json_shape_has_no_code(self):
        with self._patch_post(return_value=FakeResponse(400, '{"message": "nope"}')):
            with self.assertRaises(FirebaseAuthError) as ctx:
                self.client.refresh("token")

        self.assertIsNone(ctx.exception.code)
        self.assertEqual(ctx.exception.payload, {"message": "nope"})

    def test_http_error_with_empty_body_has_no_code(self):
        with self._patch_post(return_value=FakeResponse(500, "")):
            with self.assertRaises(FirebaseAuthError) as ctx:
                self.client.refresh("token")

        self.assertIsNone(ctx.exception.code)

    def test_connection_error_becomes_unavailable(self):
        with self._patch_post(side_effect=RequestsConnectionError("no route to host")):
            with self.assertRaises(FirebaseUnavailableError) as ctx:
                self.client.refresh("token")

        self.assertEqual(ctx.exception.code, "FIREBASE_UNAVAILABLE")

    def test_timeout_becomes_unavailable(self):
        with self._patch_post(side_effect=Timeout("timed out")):
            with self.assertRaises(FirebaseUnavailableError):
                self.client.sign_in_with_email_and_password("user@example.com", "secret")

    def test_ssl_error_becomes_unavailable(self):
        with self._patch_post(side_effect=SSLError("handshake failed")):
            with self.assertRaises(FirebaseUnavailableError):
                self.client.sign_in_with_email_and_password("user@example.com", "secret")

    def test_success_status_with_non_json_body_becomes_response_error(self):
        with self._patch_post(return_value=FakeResponse(200, PROXY_HTML_BODY)):
            with self.assertRaises(FirebaseResponseError):
                self.client.refresh("token")

    def test_success_status_with_json_array_becomes_response_error(self):
        with self._patch_post(return_value=FakeResponse(200, "[1, 2, 3]")):
            with self.assertRaises(FirebaseResponseError):
                self.client.refresh("token")

    def test_success_status_missing_token_fields_becomes_response_error(self):
        with self._patch_post(return_value=FakeResponse(200, '{"user_id": "abc"}')):
            with self.assertRaises(FirebaseResponseError):
                self.client.refresh("token")

    def test_refresh_maps_the_documented_fields(self):
        body = json.dumps({"user_id": "uid-1", "id_token": "id-1", "refresh_token": "refresh-1", "extra": "ignored"})
        with self._patch_post(return_value=FakeResponse(200, body)):
            result = self.client.refresh("refresh-0")

        self.assertEqual(result, {"userId": "uid-1", "idToken": "id-1", "refreshToken": "refresh-1"})

    def test_sign_in_returns_the_decoded_body(self):
        body = json.dumps({"localId": "uid-1", "idToken": "id-1", "refreshToken": "refresh-1"})
        with self._patch_post(return_value=FakeResponse(200, body)):
            result = self.client.sign_in_with_email_and_password("user@example.com", "secret")

        self.assertEqual(result["localId"], "uid-1")


class FirebaseErrorResponseTestCase(SimpleTestCase):
    """The view helper must preserve the existing contract and leak nothing."""

    def _map(self, exc, key, **kwargs):
        # Raise and catch so logger.exception sees real exception info, exactly
        # as it does when called from a view's except block.
        try:
            raise exc
        except FirebaseError as caught:
            return firebase_error_response(caught, key, "test", **kwargs)

    def test_known_code_is_returned_under_the_details_key(self):
        response = self._map(FirebaseAuthError(code="TOKEN_EXPIRED", status_code=400), "details")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"details": "TOKEN_EXPIRED"})

    def test_known_code_is_returned_under_the_error_key(self):
        response = self._map(FirebaseAuthError(code="EMAIL_NOT_FOUND", status_code=400), "error")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "EMAIL_NOT_FOUND"})

    def test_missing_code_falls_back_to_the_login_default(self):
        with self.assertLogs("console", level="ERROR"):
            response = self._map(FirebaseAuthError(status_code=400), "error")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Bad Request"})

    def test_missing_code_falls_back_to_the_supplied_message(self):
        with self.assertLogs("console", level="ERROR"):
            response = self._map(FirebaseAuthError(status_code=502), "details", fallback="Token refresh failed")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"details": "Token refresh failed"})

    def test_unavailable_firebase_returns_service_unavailable(self):
        with self.assertLogs("console", level="ERROR"):
            response = self._map(FirebaseUnavailableError(), "details")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {"details": FIREBASE_UNAVAILABLE_MESSAGE})

    def test_unusable_firebase_body_returns_bad_gateway(self):
        with self.assertLogs("console", level="ERROR"):
            response = self._map(FirebaseResponseError(), "error")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data, {"error": FIREBASE_INVALID_RESPONSE_MESSAGE})

    def test_response_body_never_carries_the_raw_payload(self):
        exc = FirebaseAuthError(code=None, payload={"secret": "do not leak"}, status_code=400)

        with self.assertLogs("console", level="ERROR"):
            response = self._map(exc, "error")

        self.assertNotIn("do not leak", str(response.data))


class OrphanedAccountCleanupTestCase(SimpleTestCase):
    """Login must delete an orphaned Firebase account with a credential it accepts.

    ``LoginExistingUserView.post`` is wrapped in ``@transaction.atomic``, which
    opens a connection before the body runs. ``post.__wrapped__`` is the
    undecorated function that ``functools.wraps`` keeps on the wrapper, so
    calling it drives the real branch with no database involved.
    """

    SIGN_IN_RESULT = {
        "localId": "firebase-uid-123",
        "idToken": "id-token-abc",
        "refreshToken": "refresh-token-xyz",
        "expiresIn": "3600",
        "kind": "identitytoolkit#VerifyPasswordResponse",
    }

    def _post_with_no_django_user(self, delete_side_effect=None):
        request = SimpleNamespace(data={"email": "Orphan@Example.com ", "password": "pw"})
        verified_record = SimpleNamespace(email_verified=True)

        with (
            patch("accounts.views.firebase_admin_auth.get_user_by_email", return_value=verified_record),
            patch("accounts.views.auth.sign_in_with_email_and_password", return_value=self.SIGN_IN_RESULT),
            patch("accounts.views.User.objects.get", side_effect=User.DoesNotExist),
            patch("accounts.views.auth.delete_user_account", side_effect=delete_side_effect) as delete,
        ):
            response = LoginExistingUserView.post.__wrapped__(LoginExistingUserView(), request)

        return response, delete

    def test_cleanup_sends_the_id_token_not_the_uid(self):
        response, delete = self._post_with_no_django_user()

        delete.assert_called_once_with(self.SIGN_IN_RESULT["idToken"])
        self.assertNotIn(self.SIGN_IN_RESULT["localId"], delete.call_args.args)
        self.assertEqual(response.status_code, 404)

    def test_cleanup_failure_still_returns_not_found(self):
        with self.assertLogs("console", level="ERROR"):
            response, delete = self._post_with_no_django_user(delete_side_effect=FirebaseUnavailableError())

        delete.assert_called_once_with(self.SIGN_IN_RESULT["idToken"])
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "User not found"})
