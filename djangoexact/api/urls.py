from rest_framework import routers
from . import views
from .models import *
from rest_framework.documentation import include_docs_urls
from django.urls import path, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="EX-ACT API",
      default_version='v1',
      description="",
      # terms_of_service="https://www.google.com/policies/terms/",
      # contact=openapi.Contact(email="contact@snippets.local"),
      # license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
)

router = routers.DefaultRouter()

router.register(r'projects', views.ProjectViewSet)
router.register(r'activities', views.ActivityViewSet, basename='activities')
router.register(r'modules/types', views.ModuleTypeViewSet, basename='modules')
router.register(r'modules/deforestations', views.generic_module_viewset(Deforestation), basename='deforestations')
router.register(r'modules/afforestations', views.generic_module_viewset(Afforestation), basename='afforestations')
router.register(r'modules/other-land-uses', views.generic_module_viewset(OtherLandUse), basename='otherlanduses')
router.register(r'modules/annual-croppings', views.generic_module_viewset(AnnualCropping), basename='annualcroppings')
router.register(r'modules/perennial-croppings', views.generic_module_viewset(PerennialCropping), basename='perennialcroppings')
router.register(r'modules/floodedrices', views.generic_module_viewset(FloodedRice), basename='floodedrices')
router.register(r'modules/grasslands', views.generic_module_viewset(Grassland), basename='grasslands')
router.register(r'modules/livestocks', views.generic_module_viewset(Livestock), basename='livestocks')
router.register(r'modules/forests', views.generic_module_viewset(Forest), basename='forests')
router.register(r'modules/deforestation-soil-managements', views.generic_module_viewset(DeforestationSoilManagement), basename='deforestation-soil-management')
router.register(r'modules/afforestation-soil-managements', views.generic_module_viewset(AfforestationSoilManagement), basename='afforestation-soil-management')
router.register(r'modules/other-land-use-soil-managements', views.generic_module_viewset(OtherLandUseSoilManagement), basename='other-land-use-soil-management')
router.register(r'modules/forest-land-managements', views.generic_module_viewset(ForestLandManagement), basename='forest-land-management')
router.register(r'modules/other-land-managements', views.generic_module_viewset(OtherLandManagement), basename='other-land-management')
router.register(r'modules/peat-extraction-land-managements', views.generic_module_viewset(PeatExtractionLandManagement), basename='peat-extraction-land-management')
router.register(r'modules/inland-waterbodies', views.generic_module_viewset(InlandWaterbody), basename='inland-waterbodies')

urlpatterns = [
   path('docs/', include_docs_urls(title='EX-ACT Docs')),
   re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
   re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
   re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

   re_path(r'activities/(?P<activity_id>\w+)/modules/(?P<module_name>\w+)/$', views.ActivityViewSet.as_view({'get': 'module_from_uri'}), name='module_from_uri'),
   re_path(r'activities/(?P<activity_id>\w+)/modules/(?P<module_name>\w+)/results', views.ActivityViewSet.as_view({'get': 'module_results'}), name='module_results'),
]
urlpatterns += router.urls