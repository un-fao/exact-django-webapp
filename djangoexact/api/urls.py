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

router.register(r"projects", views.ProjectViewSet, basename="project")

project_router = nested_routers.NestedSimpleRouter(router, r"projects", lookup="project")
project_router.register(r"tags", views.ProjectTagViewSet, basename="projecttags")

router.register(r"project-invitations", views.ProjectInvitationViewSet, basename="projectinvitations")
router.register(r"project-memberships", views.ProjectMembershipViewSet)
router.register(r"groups", views.GroupViewSet)
router.register(r"activities", views.ActivityViewSet, basename="activities")
router.register(r"threads", views.CommentThreadViewSet, basename="threads")
router.register(r"comments", views.CommentViewSet, basename="comments")
router.register(r"land-use-types", views.LandUseTypeViewSet, basename="landusetypes")
router.register(r"module-types", views.ModuleTypeViewSet, basename="modules")
router.register(r"notes", views.NoteViewSet, basename="notes")

router.register(r"statuses", views.generic_viewset(models.ProjectStatus), basename="statuses")
router.register(r"regions", views.generic_viewset(models.Region), basename="regions")
router.register(r"countries", views.CountryViewSet, basename="countries")
router.register(r"global-warming-potentials", views.generic_viewset(GlobalWarmingPotential), basename="globalwarmingpotentials")
router.register(r"change-rates", views.generic_viewset(models.ChangeRate), basename="changerates")
router.register(r"organization-types", views.generic_viewset(models.OrganizationType), basename="organizationtypes")

# Annual Cropland
router.register(r"annual-croplands", views.generic_module_viewset(models.AnnualCropland), basename="annualcropland")
router.register(r"annual-croplands-minor-seasons", views.generic_module_viewset(models.MinorSeasonAnnualCropland), basename="annualcroplandminorseason")
router.register(r"tillage-management-types", views.generic_viewset(models.TillageManagementType), basename="tillagemanagementtype")

# Perennial Cropland
router.register(r"perennial-croplands", views.generic_module_viewset(models.PerennialCropland), basename="perennialcropland")
router.register(r"perennial-croplands-minor-seasons", views.generic_module_viewset(models.MinorSeasonPerennialCropland), basename="perennialcroplandminorseason")

# Grassland
router.register(r"grasslands", views.generic_module_viewset(models.Grassland), basename="grassland")
router.register(r"grassland-management-types", views.generic_viewset(models.GrasslandManagementType), basename="grasslandmanagementtype")

# Fishery
router.register(r"small-fisheries", views.generic_module_viewset(models.SmallFishery), basename="smallfishery")
router.register(r"small-fishery-gear-types", views.generic_viewset(models.SmallFisheryGearType), basename="smallfisherygeartypes")

router.register(r"large-fisheries", views.generic_module_viewset(models.LargeFishery), basename="largefishery")
router.register(r"large-fishery-gear-types", views.generic_viewset(models.LargeFisheryGearType), basename="largefisherygeartypes")

router.register(r"fish-types", views.generic_viewset(models.FishType), basename="fishtypes")
router.register(r"fishery-types", views.generic_viewset(models.FisheryType), basename="fisherytypes")


# Aquaculture
router.register(r"aquacultures", views.generic_module_viewset(models.Aquaculture), basename="aquaculture")

# Inputs
router.register(r"inputs", views.generic_module_viewset(models.Input), basename="input")
router.register(r"input-entries", views.generic_module_viewset(models.InputEntry), basename="inputentry")

# Irrigation
router.register(r"irrigations", views.generic_module_viewset(models.Irrigation), basename="irrigation")
router.register(r"irrigation-systems", views.generic_module_viewset(models.IrrigationSystem), basename="irrigationsystem")
router.register(r"irrigation-phases", views.generic_module_viewset(models.IrrigationPhase), basename="irrigationphase")
router.register(r"irrigation-system-types", views.generic_viewset(models.IrrigationSystemType), basename="irrigationsystemtype")

# Set Aside
router.register(r"set-asides", views.generic_module_viewset(models.SetAside), basename="setaside")

# Other Land
router.register(r"other-lands", views.generic_module_viewset(models.OtherLand), basename="otherland")

# Coastal Wetland
router.register(r"coastal-wetlands", views.generic_module_viewset(models.CoastalWetland), basename="coastalwetland")
router.register(r"salinity-types", views.generic_viewset(models.SalinityType), basename="salinitytype")

router.register(r"organic-input-types", views.generic_viewset(models.OrganicInputType), basename="organicinputtype")
router.register(r"macro-input-types", views.generic_viewset(models.MacroInputType), basename="macroinputtype")
router.register(r"input-types", views.InputTypeViewSet, basename="inputtype")
router.register(r"residue-management-types", views.generic_viewset(models.ResidueManagementType), basename="residuemanagementtype")

router.register(r"status-types", views.generic_viewset(models.StatusType), basename="statustype")

router.register(r"land-use-changes", views.generic_module_viewset(models.LandUseChange), basename="landusechange")
router.register(r"organic-soils", views.generic_module_viewset(models.OrganicSoil), basename="organicsoil")
router.register(r"soil-types", views.generic_viewset(models.SoilType), basename="soiltype")
router.register(r"climates", views.generic_viewset(models.Climate), basename="climate")
router.register(r"moistures", views.generic_viewset(models.Moisture), basename="moisture")

router.register(r"funding-agencies", views.generic_viewset(models.FundingAgency), basename="fundingagencies")
router.register(r"executing-agencies", views.generic_viewset(models.ExecutingAgency), basename="executingagencies")

# Flooded Rice
router.register(r"flooded-rices", views.generic_module_viewset(models.FloodedRice), basename="floodedrice")
router.register(r"flooded-rices-minor-seasons", views.generic_module_viewset(models.MinorSeasonFloodedRice), basename="floodedriceminorseason")
router.register(r"crop-types", views.generic_viewset(models.CropType), basename="croptype")
router.register(r"water-management-types-before-cultivation", views.generic_viewset(models.WaterManagementTypeBeforeCultivation), basename="watermanagementtypesbeforecultivation")
router.register(r"water-management-types-after-cultivation", views.generic_viewset(models.WaterManagementTypeAfterCultivation), basename="watermanagementtypesaftercultivation")
router.register(r"organic-amendment-types", views.generic_viewset(models.OrganicAmendmentType), basename="organicamendmenttype")

# Livestock
router.register(r"livestocks", views.generic_module_viewset(models.Livestock), basename="livestock")
router.register(r"livestock-category-types", views.generic_viewset(models.LivestockCategoryType), basename="livestockcategorytypes")
router.register(r"livestock-production-types", views.generic_viewset(models.LivestockProductionType), basename="livestockproductiontypes")
router.register(r"manure-management-types", views.generic_viewset(models.ManureManagementType), basename="manuremanagementtypes")

# Forest Management
router.register(r"forest-managements", views.generic_module_viewset(models.ForestManagement), basename="forestmanagement")
router.register(r"disturbance-types", views.generic_viewset(models.DisturbanceType), basename="disturbancetypes")
router.register(r"forest-types", views.generic_viewset(models.ForestType), basename="foresttypes")
router.register(r"forest-condition-types", views.generic_viewset(models.ForestConditionType), basename="forestconditiontypes")
router.register(r"forest-disturbances", views.generic_module_viewset(models.ForestDisturbance), basename="forestdisturbance")

# Waterbodies
router.register(r"waterbodies", views.generic_module_viewset(models.Waterbody), basename="waterbody")
router.register(r"waterbody-types", views.generic_viewset(models.WaterbodyType), basename="waterbodytypes")
router.register(r"trophic-types", views.generic_viewset(models.TrophicType), basename="trophictypes")

# Settlements
router.register(r"settlements", views.generic_module_viewset(models.Settlement), basename="settlement")
router.register(r"settlement-types", views.generic_viewset(models.SettlementType), basename="settlementtypes")
router.register(r"buildings", views.generic_module_viewset(models.Building), basename="building")
router.register(r"roads", views.generic_module_viewset(models.Road), basename="road")
router.register(r"other-infrastructures", views.generic_module_viewset(models.OtherInfrastructure), basename="otherinfrastructure")
router.register(r"road-types", views.generic_viewset(models.RoadType), basename="roadtypes")
router.register(r"building-types", views.generic_viewset(models.BuildingType), basename="buildingtypes")

# Energy
router.register(r"energies", views.generic_module_viewset(models.Energy), basename="energy")
router.register(r"electricities", views.generic_module_viewset(models.Electricity), basename="electricity")
router.register(r"fuels", views.generic_module_viewset(models.Fuel), basename="fuel")
router.register(r"emission-factor-sources", views.generic_viewset(models.EmissionFactorSource), basename="emissionfactorsources")

# Fuel
router.register(r"macro-fuel-types", views.generic_viewset(models.MacroFuelType), basename="macrofueltypes")
router.register(r"fuel-types", views.generic_viewset(models.FuelType), basename="fueltypes")
router.register(r"fuel-use-types", views.generic_viewset(models.FuelUseType), basename="fuelusetypes")

# Organic Soil
router.register(r"fire-types", views.generic_viewset(models.FireType), basename="firetypes")
router.register(r"peat-types", views.generic_viewset(models.PeatType), basename="peattypes")


router.register(r"users", views.UserViewSet, basename="users")
router.register(r"definitions", views.FieldDefinitionViewSet, basename="definitions")

# Value Chains
router.register(r"storages", views.generic_module_viewset(models.Storage), basename="storage")
router.register(r"processings", views.generic_module_viewset(models.Processing), basename="processing")
router.register(r"packagings", views.generic_module_viewset(models.Packaging), basename="packaging")
router.register(r"transports", views.generic_module_viewset(models.Transport), basename="transport")

urlpatterns = [
    path("docs/", include_docs_urls(title="EX-ACT Docs")),
    re_path(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    re_path(r"^swagger/$", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    re_path(r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
urlpatterns += router.urls
urlpatterns += project_router.urls
