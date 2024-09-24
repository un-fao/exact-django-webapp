from django.contrib import admin
from unfold.admin import ModelAdmin
from modeltranslation.admin import TranslationAdmin

from .models import *


class GenericAdmin(ModelAdmin, TranslationAdmin):
    pass


for model in [model for model in dir() if not model.startswith("_")]:
    try:
        admin.site.register(eval(model), ModelAdmin)
    except:
        pass
