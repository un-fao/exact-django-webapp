from django.conf import settings
import csv
import os
import uuid
from datetime import datetime

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db.models import Model as DjangoModel
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import path, reverse
from google.cloud import storage
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RangeDateTimeFilter

from .models import *

excluded_models = {"FieldDefinition", "APIHealth", "CustomUser", "HandInHandAssessment", "Permission"}

_module_ns = dict(globals())
for model_name in (name for name in _module_ns if not name.startswith("_") and name not in excluded_models):
    candidate = _module_ns.get(model_name)
    if not isinstance(candidate, type) or not issubclass(candidate, DjangoModel):
        continue
    try:
        admin.site.register(candidate, ModelAdmin)
    except Exception:
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


@admin.register(HandInHandAssessment)
class HandInHandAssessmentAdmin(ModelAdmin):
    list_display = ("country", "name", "year", "files_count")
    search_fields = ("country__name", "name", "year")
    list_filter = ("country", "year")
    readonly_fields = ("files_list",)
    actions = ["delete_selected_files"]

    fieldsets = ((None, {"fields": ("country", "name", "year", "link")}),)

    def files_count(self, obj):
        """Display the number of uploaded files"""
        if obj.files_list:
            return len(obj.files_list)
        return 0

    files_count.short_description = "Files"

    def get_urls(self):
        """Expose a custom endpoint for uploading files from the change form."""
        urls = super().get_urls()
        app_label = self.model._meta.app_label
        model_name = self.model._meta.model_name
        custom_urls = [
            path(
                "<path:object_id>/upload/",
                self.admin_site.admin_view(self.upload_file_view),
                name=f"{app_label}_{model_name}_upload_file",
            ),
        ]
        return custom_urls + urls

    def upload_file_view(self, request, object_id, *args, **kwargs):
        """Persist an uploaded Excel file for the given assessment."""
        obj = self.get_object(request, object_id)
        if obj is None:
            messages.error(request, "Assessment not found.")
            return redirect("admin:api_handinhandassessment_changelist")

        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        redirect_url = reverse("admin:api_handinhandassessment_change", args=[obj.pk])

        if request.method != "POST":
            return redirect(redirect_url)

        uploaded_file = request.FILES.get("excel_file")
        if not uploaded_file:
            messages.error(request, "Please choose a file to upload.")
            return redirect(redirect_url)

        if not uploaded_file.name.lower().endswith((".xlsx", ".xls")):
            messages.warning(request, f"{uploaded_file.name} is not an Excel file and was skipped.")
            return redirect(redirect_url)

        try:
            client = storage.Client()
            bucket = client.bucket(settings.STORAGE_BUCKET)

            file_extension = os.path.splitext(uploaded_file.name)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            blob_path = f"hih_uploads/{obj.id}/{unique_filename}"

            blob = bucket.blob(blob_path)
            uploaded_file.seek(0)
            blob.upload_from_file(uploaded_file, content_type=uploaded_file.content_type)

            file_info = {
                "name": uploaded_file.name,
                "url": blob.public_url,
                "size": uploaded_file.size,
                "uploaded_at": datetime.now().isoformat(),
                "blob_path": blob_path,
            }

            current_files = list(obj.files_list or [])
            current_files.append(file_info)
            obj.files_list = current_files
            obj.save(update_fields=["files_list"])

            messages.success(request, f"Successfully uploaded {uploaded_file.name}.")
        except Exception as exc:
            messages.error(request, f"Error uploading {uploaded_file.name}: {exc}")

        return redirect(redirect_url)

    def changelist_view(self, request, extra_context=None):
        """Handle file deletion from the changelist view"""
        if "delete_file" in request.GET:
            file_index = int(request.GET.get("delete_file"))
            assessment_id = request.GET.get("id")

            try:
                assessment = HandInHandAssessment.objects.get(id=assessment_id)
                if assessment.files_list and 0 <= file_index < len(assessment.files_list):
                    file_info = assessment.files_list[file_index]

                    # Delete from Google Cloud Storage
                    client = storage.Client()
                    bucket = client.bucket(settings.STORAGE_BUCKET)
                    blob_path = file_info.get("blob_path")

                    if blob_path:
                        try:
                            blob = bucket.blob(blob_path)
                            blob.delete()
                        except Exception as e:
                            messages.error(request, f"Error deleting file from storage: {str(e)}")

                    # Remove from files_list
                    assessment.files_list.pop(file_index)
                    assessment.save()

                    messages.success(request, f'File "{file_info.get("name", "Unknown")}" deleted successfully.')
                else:
                    messages.error(request, "File not found.")
            except HandInHandAssessment.DoesNotExist:
                messages.error(request, "Assessment not found.")
            except Exception as e:
                messages.error(request, f"Error deleting file: {str(e)}")

        return super().changelist_view(request, extra_context)

    def delete_selected_files(self, request, queryset):
        """Delete all files from selected assessments"""
        deleted_count = 0
        for assessment in queryset:
            if assessment.files_list:
                # Delete files from Google Cloud Storage
                client = storage.Client()
                bucket = client.bucket(settings.STORAGE_BUCKET)

                for file_info in assessment.files_list:
                    blob_path = file_info.get("blob_path")
                    if blob_path:
                        try:
                            blob = bucket.blob(blob_path)
                            blob.delete()
                            deleted_count += 1
                        except Exception as e:
                            messages.error(request, f"Error deleting file {file_info.get('name', 'Unknown')}: {str(e)}")

                # Clear files_list
                assessment.files_list = []
                assessment.save()

        if deleted_count > 0:
            messages.success(request, f"Successfully deleted {deleted_count} file(s).")
        else:
            messages.info(request, "No files found to delete.")

    delete_selected_files.short_description = "Delete all files from selected assessments"
