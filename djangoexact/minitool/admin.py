from django.contrib import admin

# Register your models here.

from .models import Entry, ChangeAggregate, ChangeRecord, EmissionScenario


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("module_type", "region", "climate", "moisture", "soil_type", "total")
    search_fields = ("module_type", "region", "climate", "moisture", "soil_type")
    list_filter = ("module_type", "region", "climate", "moisture", "soil_type")
    ordering = ("module_type", "region", "climate", "moisture", "soil_type")
    list_per_page = 20


@admin.register(ChangeAggregate)
class ChangeAggregateAdmin(admin.ModelAdmin):
    list_display = ("module_type", "field", "from_value", "to_value", "region", "climate", "moisture", "soil_type")
    search_fields = ("module_type", "field", "from_value", "to_value", "region", "climate", "moisture", "soil_type")
    list_filter = ("module_type", "field", "region", "climate", "moisture", "soil_type")
    ordering = ("module_type", "field", "from_value", "to_value")
    list_per_page = 20


@admin.register(ChangeRecord)
class ChangeRecordAdmin(admin.ModelAdmin):
    list_display = ("module_type", "field", "from_value", "to_value", "region", "climate", "moisture", "soil_type", "total")
    search_fields = ("module_type", "field", "from_value", "to_value", "region", "climate", "moisture", "soil_type", "total")
    list_filter = ("module_type", "field", "region", "climate", "moisture", "soil_type", "total")
    ordering = ("module_type", "field", "from_value", "to_value", "total")
    list_per_page = 20


@admin.register(EmissionScenario)
class EmissionScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "module_type", "created_at", "updated_at")
    search_fields = ("name", "module_type")
    list_filter = ("module_type", "created_at", "updated_at")
    ordering = ("name", "module_type", "created_at", "updated_at")
    list_per_page = 20
