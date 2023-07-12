from django.apps import apps
from .views import generic_viewset
from rest_framework import routers
from .utilities import get_url_name

router = routers.DefaultRouter()


urlpatterns = []

for model_name, model in apps.get_app_config("ipcc").models.items():
    url_name = get_url_name(model.__name__)
    router.register(url_name, generic_viewset(model), basename=url_name)

urlpatterns += router.urls
