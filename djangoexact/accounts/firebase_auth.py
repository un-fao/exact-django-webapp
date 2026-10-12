import json
import logging

import requests
from requests.exceptions import RequestException

logger = logging.getLogger("console")

REQUEST_TIMEOUT = 10

SIGN_IN_URL = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={0}"
DELETE_ACCOUNT_URL = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/deleteAccount?key={0}"
REFRESH_TOKEN_URL = "https://securetoken.googleapis.com/v1/token?key={0}"


class FirebaseError(Exception):
    """Base class for every failure raised by FirebaseAuth.

    ``code`` is safe to hand back to a client; ``payload`` holds the parsed
    error document for server side logging only.
    """

    default_code = None

    def __init__(self, code=None, payload=None, status_code=None):
        self.code = code or self.default_code
        self.payload = payload or {}
        self.status_code = status_code
        super().__init__(self.code or self.__class__.__name__)


class FirebaseAuthError(FirebaseError):
    """Firebase answered with an HTTP error status.

    ``code`` is the Firebase error code (for example ``TOKEN_EXPIRED``) when the
    body had the documented shape, and ``None`` when it did not.
    """


class FirebaseUnavailableError(FirebaseError):
    """Firebase could not be reached: DNS, connection, TLS or timeout failure."""

    default_code = "FIREBASE_UNAVAILABLE"


class FirebaseResponseError(FirebaseError):
    """Firebase answered with a success status but an unusable body."""

    default_code = "FIREBASE_INVALID_RESPONSE"


def parse_firebase_error(text):
    """Extract ``(code, payload)`` from a Firebase error response body.

    This is the single place where a Firebase error body is decoded. It never
    raises: a body that is empty, not JSON, or JSON of an unexpected shape
    simply yields ``None`` for the parts that could not be recovered.
    """
    if not text:
        return None, None

    try:
        payload = json.loads(text)
    except ValueError:
        return None, None

    if not isinstance(payload, dict):
        return None, None

    error = payload.get("error")
    if not isinstance(error, dict):
        return None, payload

    message = error.get("message")
    if not isinstance(message, str) or not message:
        return None, payload

    return message, payload


class FirebaseAuth:
    """Lightweight replacement for pyrebase's Auth, using Firebase REST API directly."""

    def __init__(self, api_key):
        self.api_key = api_key

    def sign_in_with_email_and_password(self, email, password):
        url = SIGN_IN_URL.format(self.api_key)
        return self._post(url, {"email": email, "password": password, "returnSecureToken": True})

    def delete_user_account(self, id_token):
        url = DELETE_ACCOUNT_URL.format(self.api_key)
        return self._post(url, {"idToken": id_token})

    def refresh(self, refresh_token):
        url = REFRESH_TOKEN_URL.format(self.api_key)
        result = self._post(url, {"grantType": "refresh_token", "refreshToken": refresh_token})

        try:
            return {
                "userId": result["user_id"],
                "idToken": result["id_token"],
                "refreshToken": result["refresh_token"],
            }
        except KeyError as e:
            raise FirebaseResponseError(status_code=200) from e

    def _post(self, url, payload):
        """POST to Firebase and return the decoded body, or raise a FirebaseError."""
        headers = {"content-type": "application/json; charset=UTF-8"}

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=REQUEST_TIMEOUT)
        except RequestException as e:
            raise FirebaseUnavailableError() from e

        self._raise_detailed_error(response)

        try:
            body = response.json()
        except ValueError as e:
            raise FirebaseResponseError(status_code=response.status_code) from e

        if not isinstance(body, dict):
            raise FirebaseResponseError(status_code=response.status_code)

        return body

    @staticmethod
    def _raise_detailed_error(response):
        """Convert a Firebase error status into a :class:`FirebaseAuthError`."""
        if response.ok:
            return

        code, payload = parse_firebase_error(response.text)

        if payload is None and response.text:
            # Typically a proxy or CDN error page. Keep a truncated copy server
            # side, never in the response.
            logger.warning(
                "Firebase returned an unparsable error body (status=%s): %.200s",
                response.status_code,
                response.text,
            )

        raise FirebaseAuthError(code=code, payload=payload, status_code=response.status_code)
