from django.urls import path
from rest_framework.routers import DefaultRouter
import minitool.views as views


router = DefaultRouter()

router.register("entries", views.EntryViewSet, basename="entries")

urlpatterns = []
urlpatterns += router.urls
