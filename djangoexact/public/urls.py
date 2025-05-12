from rest_framework.routers import DefaultRouter
import public.views as public_views
import api.models as api_models

router = DefaultRouter()
router.register(r"projects", public_views.PublicProjectViewSet, basename="project")
router.register(r"activities", public_views.PublicActivityViewSet, basename="activity")
router.register(r"land-use-changes", public_views.generic_public_module_viewset(api_models.LandUseChange), basename="landusechange")
router.register(r"organic-soils", public_views.generic_public_module_viewset(api_models.OrganicSoil), basename="organicsoil")
router.register(r"flooded-rices", public_views.generic_public_module_viewset(api_models.FloodedRice), basename="floodedrice")
router.register(r"flooded-rices-minor-seasons", public_views.generic_public_module_viewset(api_models.MinorSeasonFloodedRice), basename="floodedriceminorseason")
router.register(r"livestocks", public_views.generic_public_module_viewset(api_models.Livestock), basename="livestock")
router.register(r"forest-managements", public_views.generic_public_module_viewset(api_models.ForestManagement), basename="forestmanagement")
router.register(r"forest-disturbances", public_views.generic_public_module_viewset(api_models.ForestDisturbance), basename="forestdisturbance")
router.register(r"waterbodies", public_views.generic_public_module_viewset(api_models.Waterbody), basename="waterbody")
router.register(r"settlements", public_views.generic_public_module_viewset(api_models.Settlement), basename="settlement")
router.register(r"buildings", public_views.generic_public_module_viewset(api_models.Building), basename="building")
router.register(r"roads", public_views.generic_public_module_viewset(api_models.Road), basename="road")
router.register(r"other-infrastructures", public_views.generic_public_module_viewset(api_models.OtherInfrastructure), basename="otherinfrastructure")
router.register(r"energies", public_views.generic_public_module_viewset(api_models.Energy), basename="energy")
router.register(r"energy-entries", public_views.generic_public_module_viewset(api_models.EnergyEntry), basename="energyentry")
router.register(r"storages", public_views.generic_public_module_viewset(api_models.Storage), basename="storage")
router.register(r"storage-entries", public_views.generic_public_module_viewset(api_models.StorageEntry), basename="storageentry")
router.register(r"processings", public_views.generic_public_module_viewset(api_models.Processing), basename="processing")
router.register(r"processing-entries", public_views.generic_public_module_viewset(api_models.ProcessingEntry), basename="processingentry")
router.register(r"packagings", public_views.generic_public_module_viewset(api_models.Packaging), basename="packaging")
router.register(r"packaging-entries", public_views.generic_public_module_viewset(api_models.PackagingEntry), basename="packagingentry")
router.register(r"transports", public_views.generic_public_module_viewset(api_models.Transport), basename="transport")
router.register(r"transport-entries", public_views.generic_public_module_viewset(api_models.TransportEntry), basename="transportentry")
router.register(r"inputs", public_views.generic_public_module_viewset(api_models.Input), basename="input")
router.register(r"input-entries", public_views.generic_public_module_viewset(api_models.InputEntry), basename="inputentry")


urlpatterns = []
urlpatterns += router.urls
