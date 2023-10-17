from rest_framework import routers
from . import views
from .models import *
from rest_framework.documentation import include_docs_urls
from django.urls import path, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

schema_view = get_schema_view(
    openapi.Info(
        title="EX-ACT API",
        default_version="v1",
        description="",
        # terms_of_service="https://www.google.com/policies/terms/",
        # contact=openapi.Contact(email="contact@snippets.local"),
        # license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.IsAuthenticated],
)

router = routers.DefaultRouter()

router.register(r"projects", views.ProjectViewSet)
router.register(r"activities", views.ActivityViewSet, basename="activities")
router.register(r'threads', views.CommentThreadViewSet, basename='threads')
router.register(r'threads/(?P<thread_id>\d+)/comments', views.CommentViewSet, basename='comments')
router.register(r"land-use-types", views.LandUseTypeViewSet, basename="land-use-types")
router.register(r"module-types", views.ModuleTypeViewSet, basename="modules")
router.register(
    r"deforestations",
    views.generic_module_viewset(Deforestation),
    basename="deforestations",
)
router.register(
    r"afforestations",
    views.generic_module_viewset(Afforestation),
    basename="afforestations",
)
router.register(
    r"other-land-uses",
    views.generic_module_viewset(OtherLandUse),
    basename="otherlanduses",
)
router.register(
    r"annual-croppings",
    views.generic_module_viewset(AnnualCropping),
    basename="annualcroppings",
)
router.register(
    r"perennial-croppings",
    views.generic_module_viewset(PerennialCropping),
    basename="perennialcroppings",
)
router.register(
    r"flooded-rices", views.generic_module_viewset(FloodedRice), basename="floodedrices"
)
router.register(
    r"grasslands", views.generic_module_viewset(Grassland), basename="grasslands"
)
router.register(
    r"livestocks", views.generic_module_viewset(Livestock), basename="livestocks"
)
router.register(r"forest-managements", views.generic_module_viewset(ForestManagement), basename="forests")

router.register(
    r"inland-waterbodies",
    views.generic_module_viewset(InlandWaterbody),
    basename="inland-waterbodies",
)
router.register(
    r"extractions",
    views.generic_module_viewset(Extraction),
    basename="inland-waterbodies",
)
router.register(
    r"rewettings",
    views.generic_module_viewset(Rewetting),
    basename="inland-waterbodies",
)
router.register(
    r"coastal-waterbodies",
    views.generic_module_viewset(CoastalWaterbody),
    basename="inland-waterbodies",
)
router.register(
    r"small-fisheries",
    views.generic_module_viewset(SmallFishery),
    basename="small-fisheries",
)
router.register(
    r"large-fisheries",
    views.generic_module_viewset(LargeFishery),
    basename="large-fisheries",
)
router.register(
    r"aquacultures", views.generic_module_viewset(Aquaculture), basename="aquacultures"
)
router.register(r"inputs", views.generic_module_viewset(Input), basename="inputs")
router.register(
    r"buildings", views.generic_module_viewset(Building), basename="buildings"
)
# router.register(r'roads', views.generic_module_viewset(Road), basename='roads')
router.register(
    r"change-rates", views.generic_viewset(ChangeRate), basename="change-rates"
)
router.register(
    r"small-fishery-gear-types",
    views.generic_viewset(SmallFisheryGearType),
    basename="small-fishery-gear-types",
)
router.register(
    r"large-fishery-gear-types",
    views.generic_viewset(LargeFisheryGearType),
    basename="large-fishery-gear-types",
)
router.register(r"fish-types", views.generic_viewset(FishType), basename="fish-types")
router.register(
    r"fishery-types", views.generic_viewset(FisheryType), basename="fishery-types"
)
router.register(
    r"electricities",
    views.generic_module_viewset(Electricity),
    basename="electricities",
)

router.register(r"fuels", views.generic_module_viewset(Fuel), basename="fuels")
router.register(
    r"irrigation-systems",
    views.generic_module_viewset(IrrigationSystem),
    basename="irrigation-systems",
)
router.register(r'irrigation-phases', views.generic_module_viewset(IrrigationPhase), basename='irrigation-phases')
router.register(r'flooded-rices', views.generic_module_viewset(FloodedRice), basename='flooded-rices')
router.register(r"crop-types", views.generic_viewset(CropType), basename="crop-types")
router.register(r"waterbodies", views.generic_module_viewset(Waterbody), basename="waterbodies")
router.register(r"set-asides", views.generic_module_viewset(SetAside), basename="set-asides")
router.register(r"degraded-lands", views.generic_module_viewset(DegradedLand), basename="degraded-lands")
router.register(r"coastal-wetlands", views.generic_module_viewset(CoastalWetland), basename="coastal-wetlands")
router.register(
    r"tillage-management-types",
    views.generic_viewset(TillageManagementType),
    basename="tillage-management-types",
)
router.register(
    r"organic-input-types",
    views.generic_viewset(OrganicInputType),
    basename="organic-input-types",
)
router.register(r"input-types", views.generic_viewset(InputType), basename="input-types")
router.register(
    r"residue-management-types",
    views.generic_viewset(ResidueManagementType),
    basename="residue-management-types",
)

router.register(
    r"activity-states", views.generic_viewset(ActivityState), basename="activity-states"
)

router.register(r"settlements", views.generic_module_viewset(Settlement), basename="settlements")
router.register(r"land-use-changes", views.generic_module_viewset(LandUseChange), basename="land-use-changes")
router.register(r"organic-soils", views.generic_module_viewset(OrganicSoil), basename="organic-soils")
router.register(r'soil-types', views.generic_viewset(SoilType), basename='soil-types')
router.register(r"climates", views.generic_viewset(Climate), basename="climates")
urlpatterns = [
    path("docs/", include_docs_urls(title="EX-ACT Docs")),
    re_path(
        r"^swagger(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    re_path(
        r"^swagger/$",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    re_path(
        r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"
    ),
]
urlpatterns += router.urls
