import json

import requests
from requests.exceptions import HTTPError


class FirebaseAuth:
    """Lightweight replacement for pyrebase's Auth, using Firebase REST API directly."""

    def __init__(self, api_key):
        self.api_key = api_key

    def sign_in_with_email_and_password(self, email, password):
        url = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={0}".format(self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"email": email, "password": password, "returnSecureToken": True})
        response = requests.post(url, headers=headers, data=data, timeout=10)
        self._raise_detailed_error(response)
        return response.json()

    def delete_user_account(self, id_token):
        url = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/deleteAccount?key={0}".format(self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"idToken": id_token})
        response = requests.post(url, headers=headers, data=data, timeout=10)
        self._raise_detailed_error(response)
        return response.json()

    def refresh(self, refresh_token):
        url = "https://securetoken.googleapis.com/v1/token?key={0}".format(self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"grantType": "refresh_token", "refreshToken": refresh_token})
        response = requests.post(url, headers=headers, data=data, timeout=10)
        self._raise_detailed_error(response)
        result = response.json()
        return {
            "userId": result["user_id"],
            "idToken": result["id_token"],
            "refreshToken": result["refresh_token"],
        }

    @staticmethod
    def _raise_detailed_error(response):
        try:
            response.raise_for_status()
        except HTTPError as e:
            raise HTTPError(e, response.text)
