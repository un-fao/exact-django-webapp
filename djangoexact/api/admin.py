from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import *
from unfold.contrib.filters.admin import RangeDateTimeFilter


for model in [model for model in dir() if not model.startswith("_") and model != "FieldDefinition" and model != "APIHealth"]:
    try:
        admin.site.register(eval(model), ModelAdmin)
    except:
        pass


@admin.register(FieldDefinition)
class FieldDefinitionAdmin(ModelAdmin):
    list_display = ("module_type", "field_name", "description")
    search_fields = ("module_type", "field_name")

@admin.register(APIHealth)
class APIStatusAdmin(ModelAdmin):
    list_display = ('is_under_maintenance', 'maintenance_end_time')
    list_filter_submit = True  # Submit button at the bottom of the filter
    list_filter = (
        ("maintenance_end_time", RangeDateTimeFilter),  # Datetime filter
    )

    # Ensure only one APIStatus instance exists
    def has_add_permission(self, request):
        return not APIHealth.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False

    # Add datet