from django.contrib import admin

# Register your models here.
from django import forms
from django.contrib import admin
from ckeditor.widgets import CKEditorWidget
from blog.models import Post


class PostAdminForm(forms.ModelForm):
    content = forms.CharField(widget=CKEditorWidget())

    class Meta:
        model = Post
        fields = "__all__"


class PostAdmin(admin.ModelAdmin):
    form = PostAdminForm


admin.site.register(Post, PostAdmin)
