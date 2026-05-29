from django.contrib import admin

from admin_scripts.models import ComputationJob


@admin.register(ComputationJob)
class ComputationJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "module_type",
        "attribute",
        "from_value",
        "to_value",
        "progress",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "module_type")
    search_fields = ("filters_hash", "module_type", "attribute", "from_value", "to_value")
    readonly_fields = (
        "filters_hash",
        "pid",
        "cloud_run_execution_name",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
    )
    ordering = ("-created_at",)
    list_per_page = 50
