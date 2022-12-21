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
      title="Snippets API",
      default_version='v1',
      description="Test description",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@snippets.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
)

router = routers.DefaultRouter()

router.register(r'projects', views.ProjectViewSet)
router.register(r'activities', views.ActivityViewSet, basename='activities')
router.register(r'modules/types', views.ModuleTypeViewSet, basename='modules')
router.register(r'modules/deforestations', views.generic_module_viewset(Deforestation), basename='deforestation')
router.register(r'modules/afforestations', views.generic_module_viewset(Afforestation), basename='afforestation')
router.register(r'modules/otherlanduses', views.generic_module_viewset(OtherLandUseChange), basename='otherlanduses')
router.register(r'modules/annualcroppings', views.generic_module_viewset(AnnualCropping), basename='annualcroppings')
router.register(r'modules/perennialcroppings', views.generic_module_viewset(PerennialCropping), basename='perennialcroppings')
router.register(r'modules/grasslands', views.generic_module_viewset(Grassland), basename='grasslands')
router.register(r'modules/livestocks', views.generic_module_viewset(Livestock), basename='livestocks')

urlpatterns = [
    path('docs/', include_docs_urls(title='EX-ACT Docs')),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
urlpatterns += router.urls