from rest_framework import routers
from . import views
from rest_framework.documentation import include_docs_urls
from django.urls import path, re_path

router = routers.DefaultRouter()

router.register(r'projects', views.ProjectViewSet)
router.register(r'activities', views.ActivityViewSet, basename='activities')
router.register(r'modules/deforestation', views.DeforestationViewSet, basename='deforestation')
router.register(r'modules/afforestation', views.AfforestationViewSet, basename='afforestation')
router.register(r'modules/otherlanduses', views.OtherLandUseChangeViewSet, basename='otherlanduses')
router.register(r'modules/types', views.ModuleTypeViewSet, basename='modules')

urlpatterns = [
    path('docs/', include_docs_urls(title='EX-ACT Docs')),
    re_path(r'modules/deforestation/(?P<module_id>[0-9]+)/results', views.DeforestationViewSet.as_view({'get': 'results'})),
    re_path(r'modules/afforestation/(?P<module_id>[0-9]+)/results', views.AfforestationViewSet.as_view({'get': 'results'})),
    re_path(r'modules/otherlanduses/(?P<module_id>[0-9]+)/results', views.OtherLandUseChangeViewSet.as_view({'get': 'results'})),
    path('modules/', views.get_modules_for_activity, name='get_modules_for_activity'),
]
urlpatterns += router.urls