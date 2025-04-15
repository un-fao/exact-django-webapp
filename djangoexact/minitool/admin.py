from django.contrib import admin

# Register your models here.

from .models import Entry


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("module_type", "region", "climate", "moisture", "soil_type", "total")
    search_fields = ("module_type", "region", "climate", "moisture", "soil_type")
    list_filter = ("module_type", "region", "climate", "moisture", "soil_type")
    ordering = ("module_type", "region", "climate", "moisture", "soil_type")
    list_per_page = 20
