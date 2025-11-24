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
    list_display = ("name", "category", "module_types_display", "created_at", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("category", "created_at", "updated_at")
    ordering = ("name", "created_at", "updated_at")
    list_per_page = 20

    def module_types_display(self, obj):
        """Display comma-separated list of module types used in this scenario."""
        module_types = obj.get_module_types()
        return ", ".join(sorted(module_types)) if module_types else "-"

    module_types_display.short_description = "Module Types"
