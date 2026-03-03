from django.urls import path

from . import views

app_name = "admin_scripts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("example-script/", views.example_script, name="example-script"),
]
