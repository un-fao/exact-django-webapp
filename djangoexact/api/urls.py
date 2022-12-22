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

urlpatterns = [
    path('docs/', include_docs_urls(title='EX-ACT Docs')),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    re_path(r'activities/(?P<activity_id>\w+)/modules/(?P<module_name>\w+)/$', views.ActivityViewSet.as_view({'get': 'get_module_from_uri'}), name='get_module_from_uri'),
    re_path(r'activities/(?P<activity_id>\w+)/modules/(?P<module_name>\w+)/results', views.ActivityViewSet.as_view({'get': 'module_results'}), name='module_results'),
]
urlpatterns += router.urls