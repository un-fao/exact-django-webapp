import blog.views as views
from django.urls import path, re_path
from rest_framework import routers

router = routers.DefaultRouter()

router.register(r"posts", views.PostViewSet)

urlpatterns = [
    path("ui/", views.home, name="home"),
    # path("<slug:slug>/", views.post_detail, name="post_detail"),
    re_path(r"^ui/(?P<slug>[\w-]+)/$", views.post_detail, name="post_detail"),
]

urlpatterns += router.urls
