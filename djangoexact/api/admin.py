from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import *
from unfold.contrib.filters.admin import RangeDateTimeFilter
from django.http import HttpResponse
import csv

for model in [model for model in dir() if not model.startswith("_") and model not in ["FieldDefinition", "APIHealth", "CustomUser"]]:
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
    list_display = ("is_under_maintenance", "maintenance_end_time")
    list_filter_submit = True  # Submit button at the bottom of the filter
    list_filter = (
        ("maintenance_end_time", RangeDateTimeFilter),  # Datetime filter
    )

    # Ensure only one APIStatus instance exists
    def has_add_permission(self, request):
        return not APIHealth.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


from django.contrib.auth.models import Permission


@admin.register(Permission)
class PermissionAdmin(ModelAdmin):
    list_display = ("name", "codename", "content_type")
    search_fields = ("name", "codename", "content_type__app_label", "content_type__model")


@admin.register(CustomUser)
class CustomUserAdmin(ModelAdmin):
    list_display = ("first_name", "last_name", "email")
    search_fields = ("first_name", "last_name", "email")
    actions = ["export_as_csv"]

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=customusers.csv"
        writer = csv.writer(response)
        writer.writerow(["first_name", "last_name", "email"])
        for user in queryset:
            writer.writerow([user.first_name, user.last_name, user.email])
        return response

    export_as_csv.short_description = "Export selected users as CSV"
