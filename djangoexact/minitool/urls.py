from django.urls import path
from rest_framework.routers import DefaultRouter
import minitool.views as views


router = DefaultRouter()

router.register("entries", views.EntryViewSet, basename="entries")
router.register("statistics", views.StatisticsModuleTotalViewSet, basename="statistics")
router.register("statistics/projects", views.EmissionStatisticsByModuleViewSet, basename="statistics-projects")
router.register("statistics/modules", views.EmissionsModulesViewSet, basename="statistics-modules")
router.register("statistics/scenarios", views.EmissionScenarioViewSet, basename="statistics-scenarios")


urlpatterns = []
urlpatterns += router.urls
