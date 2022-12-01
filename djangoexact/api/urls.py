from rest_framework import routers
from . import views
from rest_framework.documentation import include_docs_urls
from django.urls import path, re_path

router = routers.DefaultRouter()
router.register(r'projects', views.ProjectViewSet)
router.register(r'projects/(?P<project_id>[0-9]+)/luc/defo', views.DeforestationInputViewSet, basename='deforestation')
router.register(r'projects/(?P<project_id>[0-9]+)/luc/affo', views.AfforestationInputViewSet, basename='afforestation')

urlpatterns = [
    path('docs/', include_docs_urls(title='EX-ACT Docs')),
    re_path(r'projects/(?P<project_id>[0-9]+)/luc/defo/results', views.DeforestationInputViewSet.as_view({'get': 'results'})),
    re_path(r'projects/(?P<project_id>[0-9]+)/luc/affo/results', views.AfforestationInputViewSet.as_view({'get': 'results'})),
]
urlpatterns += router.urls