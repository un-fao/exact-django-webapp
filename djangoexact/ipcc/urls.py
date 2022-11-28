from . import views
from django.apps import apps
from django.urls import path

# Create default router and register viewsets
urlpatterns = []

for model_name, model in apps.get_app_config('ipcc').models.items():
    urlpatterns.append(path(f"{model_name}/", views.GenericAPIView.as_view(), {'model': model}))
