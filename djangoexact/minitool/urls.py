from django.urls import path
from rest_framework.routers import DefaultRouter
import minitool.views as views


router = DefaultRouter()

router.register("entries", views.EntryViewSet, basename="entries")
router.register("statistics", views.StatisticsModuleTotalViewSet, basename="statistics")
router.register("statistics/modules", views.EmissionStatisticsByModuleViewSet, basename="emission-statistics")

urlpatterns = []
urlpatterns += router.urls
