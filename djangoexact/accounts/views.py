from api.models import CustomUser as User
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, permissions, status
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

import accounts.utils as utils

from .serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSummarySerializer,
    PasswordResetSerializer,
)


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

            if not email or not password:
                return Response({"error": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

            serializer = RegisterSerializer(data=data)

            if not serializer.is_valid():
                return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            serializer.validated_data["email"] = email.casefold().strip()
            email = serializer.validated_data["email"]

            # Create Django user only (no Firebase user creation)
            db_user: User = serializer.save()

            # Set user as active by default (no email verification needed initially)
            db_user.is_active = True
            db_user.save()

            # Send email verification link (preserving this functionality)
            utils.send_email_verification_link(email, db_user.first_name.capitalize() + " " + db_user.last_name.capitalize())

            return Response(UserSummarySerializer(db_user).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            # Clean up only Django user if created
            try:
                if "db_user" in locals():
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

            if not email or not password:
                return Response({"error": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

            email = email.casefold().strip()

            # Get user from Django database by email
            try:
                existing_user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Check if user is active
            if not existing_user.is_active:
                return Response({"error": "User account is not active"}, status=status.HTTP_401_UNAUTHORIZED)

            # Verify password using Django's built-in password checking
            if not check_password(password, existing_user.password):
                return Response({"error": "Invalid login credentials"}, status=status.HTTP_401_UNAUTHORIZED)

            # Log the user in using Django's session authentication
            login(request, existing_user)

            # Prepare response data (preserving the structure but without Firebase tokens)
            extra_data = {
                "uid": str(existing_user.id),  # Use Django user ID instead of Firebase UID
                "access_token": None,  # No Firebase token needed
                "refresh_token": None,  # No Firebase refresh token needed
                "expires_in": None,  # No token expiration
                "kind": "user",  # Static kind value
                "user": UserSummarySerializer(existing_user).data,
            }

            return Response(extra_data, status=status.HTTP_200_OK)

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
            if not email:
                return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

            email = email.casefold().strip()

            # Check if user exists in Django database
            try:
                User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Send password reset link using existing utility function
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
            if not email:
                return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

            email = email.casefold().strip()

            # Get user from Django database
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Mark user as active/verified in Django
            user.is_active = True
            user.save()

            return Response({"message": "Email verified"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TokenRefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        responses={200: LoginResponseSerializer, 400: "Bad Request"},
    )
    @transaction.atomic
    def post(self, request):
        try:
            # Since we're not using Firebase tokens anymore, this endpoint
            # can be simplified or may not be needed depending on the frontend
            # For now, return a message indicating no refresh is needed
            return Response(
                {
                    "message": "Token refresh not required for Django session authentication",
                    "uid": None,
                    "access_token": None,
                    "refresh_token": None,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
