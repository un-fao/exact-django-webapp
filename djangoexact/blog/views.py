from django.shortcuts import render
import blog.models as models
from rest_framework import viewsets
import blog.serializers as serializers
from api.views import AuthenticatedViewSet


def home(request):
    posts = models.Post.objects.all()
    return render(request, "blog_home.html", {"posts": posts})


def post_detail(request, slug):
    post = models.Post.objects.get(slug=slug)
    return render(request, "post_detail.html", {"post": post})


class PostViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
    queryset = models.Post.objects.all()
    serializer_class = serializers.PostSerializer

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
