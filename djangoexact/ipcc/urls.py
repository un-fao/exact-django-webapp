from django.apps import apps
from .views import generic_viewset, table_list_view, table_data_view
from rest_framework import routers
from .utilities import get_url_name
from django.urls import path

router = routers.DefaultRouter()


urlpatterns = [
    path("data/", table_list_view, name="table_list"),
    path("data/<str:model_name>/", table_data_view, name="table_data"),
]

for model_name, model in apps.get_app_config("ipcc").models.items():
    url_name = get_url_name(model.__name__)
    router.register(url_name, generic_viewset(model), basename=url_name)

urlpatterns += router.urls
