from api.models import CustomUser as User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "password", "first_name", "last_name", "email", "country")
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            # username=validated_data["username"],
            password=validated_data["password"],
            email=validated_data["email"],
            first_name=validated_data.get("first_name", None),
            last_name=validated_data.get("last_name", None),
            country=validated_data.get("country", None),
        )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255, required=True)
    password = serializers.CharField(max_length=255, required=True)


class LoginResponseSerializer(serializers.Serializer):
    firebase_uid = serializers.CharField(max_length=255, required=True)
    access_token = serializers.CharField(max_length=255, required=True)
    refresh_token = serializers.CharField(max_length=255, required=True)
    expires_in = serializers.IntegerField(required=True)
    kind = serializers.CharField(max_length=255, required=True)


# User serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        refresh = self.get_token(self.user)
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        data["user"] = UserSerializer(self.user).data
        return data
