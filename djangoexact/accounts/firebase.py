import os

import firebase_admin
from api.models import CustomUser as User
from firebase_admin import auth as firebase_admin_auth
from firebase_admin import credentials
from rest_framework import authentication, exceptions

from djangoexact.settings import auth

try:
    cred = credentials.Certificate(os.getenv("FIREBASE_ADMIN_SDK_CREDENTIALS_PATH"))
    auth = firebase_admin.initialize_app(cred)
except Exception as e:
    raise Exception(f"Firebase config not found: {e}") from e


class FirebaseAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION")
        if not auth:
            return None

        # If request is for login or register, or admin, skip authentication
        if request.path in ["/api/accounts/register/", "/api/accounts/login/", "/admin"]:
            return None

        parts = auth.split()

        if parts[0].lower() != self.keyword.lower():
            return None

        if len(parts) != 2:
            return None

        return self.authenticate_credentials(request, parts[1])

    def authenticate_credentials(self, request, token):
        try:
            decoded_token = firebase_admin_auth.verify_id_token(token)
            uid = decoded_token["uid"]
            user = User.objects.get(firebase_uid=uid)
        except Exception as e:
            raise exceptions.AuthenticationFailed("Invalid token.")

        return (user, None)
