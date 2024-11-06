from django.urls import path, re_path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from ipcc.models import GlobalWarmingPotential
from rest_framework import permissions, routers
from rest_framework.documentation import include_docs_urls

from rest_framework_nested import routers as nested_routers


import api.models as models

from . import views

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
)

router = routers.DefaultRouter()

router.register(r"projects", views.ProjectViewSet)

project_router = nested_routers.NestedSimpleRouter(router, r"projects", lookup="project")
project_router.register(r"tags", views.ProjectTagViewSet, basename="project-tags")

router.register(r"project-invitations", views.ProjectInvitationViewSet, basename="project-invitations")
router.register(r"project-memberships", views.ProjectMembershipViewSet)
router.register(r"groups", views.GroupViewSet)
router.register(r"activities", views.ActivityViewSet, basename="activities")
router.register(r"threads", views.CommentThreadViewSet, basename="threads")
router.register(r"comments", views.CommentViewSet, basename="comments")
router.register(r"land-use-types", views.LandUseTypeViewSet, basename="land-use-types")
router.register(r"module-types", views.ModuleTypeViewSet, basename="modules")
router.register(r"notes", views.NoteViewSet, basename="notes")

router.register(r"statuses", views.generic_viewset(models.ProjectStatus), basename="statuses")
router.register(r"regions", views.generic_viewset(models.Region), basename="regions")
router.register(r"countries", views.CountryViewSet, basename="countries")
router.register(r"global-warming-potentials", views.generic_viewset(GlobalWarmingPotential), basename="global-warming-potentials")
router.register(r"change-rates", views.generic_viewset(models.ChangeRate), basename="change-rates")
router.register(r"organization-types", views.generic_viewset(models.OrganizationType), basename="organization-types")

# Annual Cropland
router.register(r"annual-croplands", views.generic_module_viewset(models.AnnualCropland), basename="annual-croppings")
router.register(r"annual-croplands-minor-seasons", views.generic_module_viewset(models.MinorSeasonAnnualCropland), basename="annual-cropland-minor-seasons")
router.register(r"tillage-management-types", views.generic_viewset(models.TillageManagementType), basename="tillage-management-types")

# Perennial Cropland
router.register(r"perennial-croplands", views.generic_module_viewset(models.PerennialCropland), basename="perennial-croplands")
router.register(r"perennial-croplands-minor-seasons", views.generic_module_viewset(models.MinorSeasonPerennialCropland), basename="perennial-cropland-minor-seasons")

# Grassland
router.register(r"grasslands", views.generic_module_viewset(models.Grassland), basename="grasslands")
router.register(r"grassland-management-types", views.generic_viewset(models.GrasslandManagementType), basename="grasslandmanagementtypes")

# Fishery
router.register(r"small-fisheries", views.generic_module_viewset(models.SmallFishery), basename="small-fisheries")
router.register(r"small-fishery-gear-types", views.generic_viewset(models.SmallFisheryGearType), basename="small-fishery-gear-types")

router.register(r"large-fisheries", views.generic_module_viewset(models.LargeFishery), basename="large-fisheries")
router.register(r"large-fishery-gear-types", views.generic_viewset(models.LargeFisheryGearType), basename="large-fishery-gear-types")

router.register(r"fish-types", views.generic_viewset(models.FishType), basename="fish-types")
router.register(r"fishery-types", views.generic_viewset(models.FisheryType), basename="fishery-types")


# Aquaculture
router.register(r"aquacultures", views.generic_module_viewset(models.Aquaculture), basename="aquacultures")

# Inputs
router.register(r"inputs", views.generic_module_viewset(models.Input), basename="inputs")
router.register(r"input-entries", views.generic_module_viewset(models.InputEntry), basename="input-entries")

# Irrigation
router.register(r"irrigations", views.generic_module_viewset(models.Irrigation), basename="irrigations")
router.register(r"irrigation-systems", views.generic_module_viewset(models.IrrigationSystem), basename="irrigation-systems")
router.register(r"irrigation-phases", views.generic_module_viewset(models.IrrigationPhase), basename="irrigation-phases")
router.register(r"irrigation-system-types", views.generic_viewset(models.IrrigationSystemType), basename="irrigation-system-types")

# Set Aside
router.register(r"set-asides", views.generic_module_viewset(models.SetAside), basename="set-asides")

# Other Land
router.register(r"other-lands", views.generic_module_viewset(models.OtherLand), basename="other-lands")

# Coastal Wetland
router.register(r"coastal-wetlands", views.generic_module_viewset(models.CoastalWetland), basename="coastal-wetlands")
router.register(r"salinity-types", views.generic_viewset(models.SalinityType), basename="salinity-types")

router.register(r"organic-input-types", views.generic_viewset(models.OrganicInputType), basename="organic-input-types")
router.register(r"macro-input-types", views.generic_viewset(models.MacroInputType), basename="macro-input-types")
router.register(r"input-types", views.InputTypeViewSet, basename="input-types")
router.register(r"residue-management-types", views.generic_viewset(models.ResidueManagementType), basename="residue-management-types")

router.register(r"status-types", views.generic_viewset(models.StatusType), basename="status-types")

router.register(r"land-use-changes", views.generic_module_viewset(models.LandUseChange), basename="land-use-changes")
router.register(r"organic-soils", views.generic_module_viewset(models.OrganicSoil), basename="organic-soils")
router.register(r"soil-types", views.generic_viewset(models.SoilType), basename="soil-types")
router.register(r"climates", views.generic_viewset(models.Climate), basename="climates")
router.register(r"moistures", views.generic_viewset(models.Moisture), basename="moistures")

router.register(r"funding-agencies", views.generic_viewset(models.FundingAgency), basename="funding-agencies")
router.register(r"executing-agencies", views.generic_viewset(models.ExecutingAgency), basename="executing-agencies")

# Flooded Rice
router.register(r"flooded-rices", views.generic_module_viewset(models.FloodedRice), basename="floodedrices")
router.register(r"flooded-rices-minor-seasons", views.generic_module_viewset(models.MinorSeasonFloodedRice), basename="floodedriceminorseasons")
router.register(r"crop-types", views.generic_viewset(models.CropType), basename="crop-types")
router.register(r"water-management-types-before-cultivation", views.generic_viewset(models.WaterManagementTypeBeforeCultivation), basename="water-management-types-before-cultivation")
router.register(r"water-management-types-after-cultivation", views.generic_viewset(models.WaterManagementTypeAfterCultivation), basename="water-management-types-after-cultivation")
router.register(r"organic-amendment-types", views.generic_viewset(models.OrganicAmendmentType), basename="organic-amendment-types")

# Livestock
router.register(r"livestocks", views.generic_module_viewset(models.Livestock), basename="livestocks")
router.register(r"livestock-category-types", views.generic_viewset(models.LivestockCategoryType), basename="livestock-category-types")
router.register(r"livestock-production-types", views.generic_viewset(models.LivestockProductionType), basename="livestock-production-types")
router.register(r"manure-management-types", views.generic_viewset(models.ManureManagementType), basename="manure-management-types")

# Forest Management
router.register(r"forest-managements", views.generic_module_viewset(models.ForestManagement), basename="forests")
router.register(r"disturbance-types", views.generic_viewset(models.DisturbanceType), basename="disturbance-types")
router.register(r"forest-types", views.generic_viewset(models.ForestType), basename="forest-types")
router.register(r"forest-condition-types", views.generic_viewset(models.ForestConditionType), basename="forest-condition-types")
router.register(r"forest-disturbances", views.generic_module_viewset(models.ForestDisturbance), basename="forest-disturbances")

# Waterbodies
router.register(r"waterbodies", views.generic_module_viewset(models.Waterbody), basename="waterbodies")
router.register(r"waterbody-types", views.generic_viewset(models.WaterbodyType), basename="waterbody-types")
router.register(r"trophic-types", views.generic_viewset(models.TrophicType), basename="trophic-types")

# Settlements
router.register(r"settlements", views.generic_module_viewset(models.Settlement), basename="settlements")
router.register(r"settlement-types", views.generic_viewset(models.SettlementType), basename="settlement-types")
router.register(r"buildings", views.generic_module_viewset(models.Building), basename="buildings")
router.register(r"roads", views.generic_module_viewset(models.Road), basename="roads")
router.register(r"other-infrastructures", views.generic_module_viewset(models.OtherInfrastructure), basename="other-infrastructures")
router.register(r"road-types", views.generic_viewset(models.RoadType), basename="road-types")
router.register(r"building-types", views.generic_viewset(models.BuildingType), basename="building-types")

# Energy
router.register(r"energies", views.generic_module_viewset(models.Energy), basename="energies")
router.register(r"electricities", views.generic_module_viewset(models.Electricity), basename="electricities")
router.register(r"fuels", views.generic_module_viewset(models.Fuel), basename="fuels")
router.register(r"emission-factor-sources", views.generic_viewset(models.EmissionFactorSource), basename="emission-factor-sources")

# Fuel
router.register(r"macro-fuel-types", views.generic_viewset(models.MacroFuelType), basename="macro-fuel-types")
router.register(r"fuel-types", views.generic_viewset(models.FuelType), basename="fuel-types")

# Organic Soil
router.register(r"fire-types", views.generic_viewset(models.FireType), basename="fire-types")
router.register(r"peat-types", views.generic_viewset(models.PeatType), basename="peat-types")


router.register(r"users", views.UserViewSet, basename="users")
router.register(r"definitions", views.FieldDefinitionViewSet, basename="definitions")

router.register(r"value-chains", views.generic_module_viewset(models.ValueChain), basename="value-chains")
router.register(r"storages", views.generic_module_viewset(models.Storage), basename="storages")
router.register(r"processings", views.generic_module_viewset(models.Processing), basename="processing")
router.register(r"packagings", views.generic_module_viewset(models.Packaging), basename="packagings")
router.register(r"transports", views.generic_module_viewset(models.Transport), basename="transports")
router.register(r"fuel-use-types", views.generic_viewset(models.FuelUseType), basename="fuel-use-types")

urlpatterns = [
    path("docs/", include_docs_urls(title="EX-ACT Docs")),
    re_path(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    re_path(r"^swagger/$", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    re_path(r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
urlpatterns += router.urls
urlpatterns += project_router.urls
