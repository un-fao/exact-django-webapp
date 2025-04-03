from . import views
from django.urls import path
import api.models as models

from rest_framework.routers import DefaultRouter

# Create a router and register our viewset with it.
router = DefaultRouter()
router.register(r"projects", views.PublicProjectRetrieveViewSet, basename="public_project")
router.register(r"activities", views.PublicActivityRetrieveViewSet, basename="public_activity")
router.register(r"land-use-changes", views.public_module(models.LandUseChange), basename="public_land_use_changes")
router.register(r"annual-croplands", views.public_module(models.AnnualCropland), basename="public_annual_croplands")
router.register(r"minor-season-annual-croplands", views.public_module(models.MinorSeasonAnnualCropland), basename="public_minor_season_annual_croplands")
router.register(r"perennial-croplands", views.public_module(models.PerennialCropland), basename="public_perennial_croplands")
router.register(r"minor-season-perennial-croplands", views.public_module(models.MinorSeasonPerennialCropland), basename="public_minor_season_perennial_croplands")
router.register(r"flooded-rices", views.public_module(models.FloodedRice), basename="public_flooded_rice")
router.register(r"minor-season-flooded-rices", views.public_module(models.MinorSeasonFloodedRice), basename="public_minor_season_flooded_rice")
router.register(r"set-asides", views.public_module(models.SetAside), basename="public_set_aside")
router.register(r"grasslands", views.public_module(models.Grassland), basename="public_grassland")
router.register(r"forest-managements", views.public_module(models.ForestManagement), basename="public_forest_management")
router.register(r"settlements", views.public_module(models.Settlement), basename="public_settlement")
router.register(r"roads", views.public_module(models.Road), basename="public_road")
router.register(r"buildings", views.public_module(models.Building), basename="public_building")
router.register(r"other-infrastructures", views.public_module(models.OtherInfrastructure), basename="public_other_infrastructure")
router.register(r"other-lands", views.public_module(models.OtherLand), basename="public_other_land")
router.register(r"organic-soils", views.public_module(models.OrganicSoil), basename="public_organic_soil")
router.register(r"coastal-wetlands", views.public_module(models.CoastalWetland), basename="public_coastal_wetland")
router.register(r"waterbodys", views.public_module(models.Waterbody), basename="public_waterbody")
router.register(r"livestocks", views.public_module(models.Livestock), basename="public_livestock")
router.register(r"small-fisheries", views.public_module(models.SmallFishery), basename="public_small_fishery")
router.register(r"large-fisheries", views.public_module(models.LargeFishery), basename="public_large_fishery")
router.register(r"aquacultures", views.public_module(models.Aquaculture), basename="public_aquaculture")
router.register(r"irrigations", views.public_module(models.Irrigation), basename="public_irrigation")
router.register(r"irrigation-phases", views.public_module(models.IrrigationPhase), basename="public_irrigation_phase")
router.register(r"irrigation-systems", views.public_module(models.IrrigationSystem), basename="public_irrigation_system")
router.register(r"inputs", views.public_module(models.Input), basename="public_inputs")
router.register(r"input-entries", views.public_module(models.InputEntry), basename="public_input_entries")
router.register(r"energies", views.public_module(models.Energy), basename="public_energies")
router.register(r"energy-entries", views.public_module(models.EnergyEntry), basename="public_energy_entries")
router.register(r"packagings", views.public_module(models.Packaging), basename="public_packagings")
router.register(r"packaging-entries", views.public_module(models.PackagingEntry), basename="public_packaging_entries")
router.register(r"transports", views.public_module(models.Transport), basename="public_transports")
router.register(r"transport-entries", views.public_module(models.TransportEntry), basename="public_transport_entries")
router.register(r"storages", views.public_module(models.Storage), basename="public_storages")
router.register(r"storage-entries", views.public_module(models.StorageEntry), basename="public_storage_entries")
router.register(r"processings", views.public_module(models.Processing), basename="public_processings")
router.register(r"processing-entries", views.public_module(models.ProcessingEntry), basename="public_processing_entries")

urlpatterns = []
urlpatterns += router.urls
