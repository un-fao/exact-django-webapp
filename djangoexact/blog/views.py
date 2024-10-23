from django.shortcuts import render
import blog.models as models

# Create your views here.


def home(request):
    posts = models.Post.objects.all()
    return render(request, "blog_home.html", {"posts": posts})


def post_detail(request, slug):
    post = models.Post.objects.get(slug=slug)
    return render(request, "post_detail.html", {"post": post})
