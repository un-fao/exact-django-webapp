import json

import firebase_admin
from api.models import CustomUser as User
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from firebase_admin import auth as firebase_admin_auth
from rest_framework import authentication, generics, permissions, status
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

import accounts.utils as utils
from djangoexact.settings import auth

from .serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
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
                "user": UserSerializer(user, context=self.get_serializer_context()).data,
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

            db_user: User = serializer.save()

            firebase_user = firebase_admin_auth.create_user(email=email, password=password)
            firebase_uid = firebase_user.uid

            db_user.firebase_uid = firebase_uid
            db_user.is_active = True
            db_user.save()

            utils.send_email_verification_link(email, db_user.first_name.capitalize() + " " + db_user.last_name.capitalize())

            return Response({"uid": db_user.firebase_uid}, status=status.HTTP_201_CREATED)

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

            user = auth.sign_in_with_email_and_password(email, password)

            existing_user = User.objects.get(firebase_uid=user["localId"])

            login(request, existing_user)

            if not check_password(password, existing_user.password):
                # If firebase password is different from Django password, update Django password
                existing_user.set_password(password)
                existing_user.save()

            extra_data = {
                "uid": user["localId"],
                "access_token": user["idToken"],
                "refresh_token": user["refreshToken"],
                "expires_in": user["expiresIn"],
                "kind": user["kind"],
            }

            return Response(extra_data, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            auth.delete_user(user["localId"])
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TokenRefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        responses={200: LoginResponseSerializer, 400: "Bad Request"},
    )
    @transaction.atomic
    def post(self, request):
        data = request.data

        try:
            refresh_token = data.get("refresh")

            user = auth.refresh(refresh_token)

            extra_data = {
                "uid": user["userId"],
                "access_token": user["idToken"],
                "refresh_token": user["refreshToken"],
            }

            return Response(extra_data, status=status.HTTP_200_OK)

        except Exception as e:
            foo = json.loads(e.strerror)
            return Response({"details": foo["error"]["message"]}, status=status.HTTP_400_BAD_REQUEST)
