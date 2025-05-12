from django.urls import path
from django.urls import include
from rest_framework.routers import DefaultRouter
import public.views as public_views

router = DefaultRouter()
router.register(r"projects", public_views.PublicProjectViewSet, basename="project")
router.register(r"activities", public_views.PublicActivityViewSet, basename="activity")

urlpatterns = []
urlpatterns += router.urls
