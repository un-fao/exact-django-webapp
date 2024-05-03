from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

urlpatterns = [
    path("register/", views.CreateNewUserView.as_view(), name="register"),
    path("login/", views.LoginExistingUserView.as_view(), name="login"),
    path("token/refresh/", views.TokenRefreshView.as_view(), name="token_refresh"),
]
