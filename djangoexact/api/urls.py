from rest_framework import routers
from . import views
from rest_framework.documentation import include_docs_urls
from django.urls import path, re_path


# declare router and register viewsets
router = routers.DefaultRouter()
router.register(r'projects', views.ProjectViewSet)
router.register(r'projects/(?P<project_id>[0-9]+)/luc/defo', views.DeforestationInputViewSet, basename='landuseparameters')

# add router to urlpatterns
urlpatterns = [
    path('docs/', include_docs_urls(title='EX-ACT Docs')),
    re_path(r'projects/(?P<project_id>[0-9]+)/luc/defo/results', views.DeforestationInputViewSet.as_view({'get': 'results'})),
]
urlpatterns += router.urls