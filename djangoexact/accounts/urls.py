from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

urlpatterns = [
    path("register/", views.CreateNewUserView.as_view(), name="register"),
    path("login/", views.LoginExistingUserView.as_view(), name="login"),
    path("password-reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path("token/refresh/", views.TokenRefreshView.as_view(), name="token_refresh"),
    path("verify/", views.VerifyUserEmail.as_view(), name="verify_user_email"),
    path("transfer/", views.TransferUser.as_view(), name="transfer_user"),
]
