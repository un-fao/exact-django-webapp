from django.contrib import admin

# Register your models here.
from django import forms
from django.contrib import admin
from blog.models import Post
import slugify.slugify as slugify
from unfold.contrib.forms.widgets import WysiwygWidget
from django.db import models
from unfold.admin import ModelAdmin


class PostAdminForm(forms.ModelForm):
    content = forms.CharField(widget=WysiwygWidget)
    slug = forms.CharField(widget=forms.HiddenInput(), required=False)
    author = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Post
        fields = "__all__"


class PostAdmin(ModelAdmin):
    form = PostAdminForm

    list_display = ["title", "author", "date_created"]
    search_fields = ["title", "author__first_name", "author__last_name"]
    readonly_fields = ["slug", "author"]
    fieldsets = [
        (None, {"fields": ["title", "excerpt", "content"]}),
        ("Meta", {"fields": ["slug", "author"]}),
    ]

    def save_model(self, request, obj, form, change):
        obj.author = request.user
        obj.slug = slugify(obj.title)
        super().save_model(request, obj, form, change)


admin.site.register(Post, PostAdmin)
