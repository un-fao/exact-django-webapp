"""URL configuration for the offline build.

Mirrors `djangoexact.urls` with the `minitool` and `admin_scripts`
routes omitted, since those apps are not installed in the offline
settings module.
"""

from django.contrib import admin
from django.urls import path, include
from api.views import warmup

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("api/public/", include("public.urls")),
    path("api/ipcc/", include("ipcc.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/blog/", include("blog.urls")),
    path("_ah/warmup", warmup),
]
