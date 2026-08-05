import logging

from api.models import CustomUser as User
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from firebase_admin import auth as firebase_admin_auth
from rest_framework import generics, permissions, status
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

import accounts.utils as utils
from djangoexact.settings import auth

from .firebase_auth import FirebaseError, FirebaseResponseError, FirebaseUnavailableError
from .serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSummarySerializer,
    PasswordResetSerializer,
)

logger = logging.getLogger("console")

FIREBASE_UNAVAILABLE_MESSAGE = "Authentication service unavailable"
FIREBASE_INVALID_RESPONSE_MESSAGE = "Invalid response from authentication service"


def firebase_error_response(exc, key, context, fallback="Bad Request"):
    """Turn a :class:`FirebaseError` into a safe DRF response.

    ``key`` is the payload key the endpoint already uses ("error" or "details"),
    so existing clients keep seeing the same response shape. Only the Firebase
    error code is ever echoed back to the client; anything the client cannot act
    on is logged server side and answered with a generic message.
    """
    if isinstance(exc, FirebaseUnavailableError):
        logger.exception("Firebase unreachable during %s", context)
        return Response({key: FIREBASE_UNAVAILABLE_MESSAGE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    if isinstance(exc, FirebaseResponseError):
        logger.exception("Unusable Firebase response during %s", context)
        return Response({key: FIREBASE_INVALID_RESPONSE_MESSAGE}, status=status.HTTP_502_BAD_GATEWAY)

    if exc.code:
        return Response({key: exc.code}, status=status.HTTP_400_BAD_REQUEST)

    logger.exception("Unrecognised Firebase error body during %s (status=%s)", context, exc.status_code)
    return Response({key: fallback}, status=status.HTTP_400_BAD_REQUEST)


@authentication_classes([])
@permission_classes([])
class RegisterView(generics.GenericAPIView):
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user: User = serializer.save()
        user.is_active = False
        user.save()

        return Response(
            {
                "user": UserSummarySerializer(user, context=self.get_serializer_context()).data,
                "message": "User Created Successfully.  Now perform Login to get your token",
            }
        )


class CreateNewUserView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=RegisterSerializer,
        responses={201: "Created", 400: "Bad Request"},
    )
    @transaction.atomic
    def post(self, request):
        data = request.data

        try:
            email = data.get("email")
            password = data.get("password")

            serializer = RegisterSerializer(data=data)

            if not serializer.is_valid():
                return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            serializer.validated_data["email"] = email.casefold().strip()
            email = serializer.validated_data["email"]

            db_user: User = serializer.save()

            firebase_user = firebase_admin_auth.create_user(email=email, password=password)
            firebase_uid = firebase_user.uid

            db_user.firebase_uid = firebase_uid
            db_user.save()

            utils.send_email_verification_link(email, db_user.first_name.capitalize() + " " + db_user.last_name.capitalize())

            return Response(UserSummarySerializer(db_user).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            try:
                # Delete the user if it was created
                firebase_admin_auth.delete_user(firebase_uid)
                db_user.delete()
            except Exception:
                pass
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LoginExistingUserView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={200: LoginResponseSerializer, 400: "Bad Request", 401: "Unauthorized", 404: "Not Found"},
    )
    @transaction.atomic
    def post(self, request):
        data = request.data

        try:
            email = data.get("email")
            password = data.get("password")
            user = firebase_admin_auth.get_user_by_email(email)

            if not user.email_verified:
                return Response({"error": "Email not verified"}, status=status.HTTP_401_UNAUTHORIZED)

            email = email.casefold().strip()

            try:
                user = auth.sign_in_with_email_and_password(email, password)
            except FirebaseError as e:
                if e.code == "INVALID_LOGIN_CREDENTIALS":
                    return Response({"error": "Invalid login credentials"}, status=status.HTTP_401_UNAUTHORIZED)

                return firebase_error_response(e, "error", "login")

            existing_user = User.objects.get(firebase_uid=user["localId"])

            login(request, existing_user)

            if not check_password(password, existing_user.password):
                # If firebase password is different from Django password, update Django password.
                # The password was already authenticated by Firebase; validate before syncing
                # so Django-side hashes conform to current password policies.
                try:
                    validate_password(password, user=existing_user)
                except DjangoValidationError:
                    # Keep the stale Django hash rather than storing a weak password;
                    # the user can still authenticate via Firebase until they reset.
                    pass
                else:
                    existing_user.set_password(password)
                    existing_user.save()

            extra_data = {
                "uid": user["localId"],
                "access_token": user["idToken"],
                "refresh_token": user["refreshToken"],
                "expires_in": user["expiresIn"],
                "kind": user["kind"],
                "user": UserSummarySerializer(existing_user).data,
            }

            return Response(extra_data, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            try:
                auth.delete_user_account(user["localId"])
            except FirebaseError:
                # Best effort cleanup; the client still gets the 404 it expects.
                logger.exception("Failed to delete orphaned Firebase account during login")
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=PasswordResetSerializer,
        responses={200: "OK", 400: "Bad Request"},
    )
    @transaction.atomic
    def post(self, request):
        data = request.data

        try:
            email = data.get("email", None)
            if email:
                email = email.casefold().strip()

            firebase_admin_auth.get_user_by_email(email)

            utils.send_password_reset_link(email)

            return Response({"message": "Password reset email sent"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyUserEmail(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        responses={200: "OK", 400: "Bad Request"},
    )
    @transaction.atomic
    def post(self, request):
        data = request.data

        try:
            email = data.get("email", None)
            if email:
                email = email.casefold

            user = firebase_admin_auth.get_user_by_email(email)

            # Verify user email
            firebase_admin_auth.update_user(user.uid, email_verified=True)

            return Response({"message": "Email verified"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TokenRefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        responses={200: LoginResponseSerializer, 400: "Bad Request"},
    )
    def post(self, request):
        # No @transaction.atomic: this view performs no DB writes (Firebase only).
        # The wrapper forced a DB connection open and turned a transient Cloud SQL
        # restart into a hard 500 on token refresh.
        data = request.data

        refresh_token = data.get("refresh") if isinstance(data, dict) else None

        if not isinstance(refresh_token, str) or not refresh_token.strip():
            # Firebase answers MISSING_REFRESH_TOKEN for this anyway; save the round trip.
            return Response({"details": "MISSING_REFRESH_TOKEN"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = auth.refresh(refresh_token)
        except FirebaseError as e:
            return firebase_error_response(e, "details", "token refresh", fallback="Token refresh failed")

        extra_data = {
            "uid": user["userId"],
            "access_token": user["idToken"],
            "refresh_token": user["refreshToken"],
        }

        return Response(extra_data, status=status.HTTP_200_OK)
