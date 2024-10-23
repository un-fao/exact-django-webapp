import blog.views as views
from django.urls import path

urlpatterns = [
    path("", views.home, name="home"),
    path("<slug:slug>/", views.post_detail, name="post_detail"),
]
