from rest_framework.routers import DefaultRouter
from . import views
from django.urls import path

urlpatterns = [
    path("projects/<int:id>/", views.PublicProjectRetrieveView.as_view(), name="public_project_retrieve"),
]
