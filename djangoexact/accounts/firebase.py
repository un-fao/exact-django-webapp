import os
import json
import base64
import firebase_admin
from api.models import CustomUser as User
from firebase_admin import auth as firebase_admin_auth
from firebase_admin import credentials
from rest_framework import authentication, exceptions
import pyrebase

from djangoexact.settings import FIREBASE_CONFIG


class FirebaseAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        token = request.META.get("HTTP_AUTHORIZATION")
        if not token:
            return None

        # If request is for login or register, or admin, skip authentication
        if request.path in ["/api/accounts/register/", "/api/accounts/login/", "/api/token/refresh/", "/admin", "/api/swagger/", "/api/accounts/password-reset/"]:
            return None

        parts = token.split()

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
        except firebase_admin_auth.ExpiredIdTokenError:
            raise exceptions.AuthenticationFailed("Token is expired")
        except Exception as e:
            raise exceptions.AuthenticationFailed(str(e))

        return (user, None)
