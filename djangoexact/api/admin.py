from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import *


for model in [model for model in dir() if not model.startswith("_") and model != "FieldDefinition"]:
    try:
        admin.site.register(eval(model), ModelAdmin)
    except:
        pass


@admin.register(FieldDefinition)
class FieldDefinitionAdmin(admin.ModelAdmin):
    list_display = ("module_type", "field_name", "description")
    search_fields = ("module_type", "field_name")
