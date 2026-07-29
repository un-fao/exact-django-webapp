from django.contrib import admin
from unfold.admin import ModelAdmin
from django.http import HttpResponse
import csv

from .models import *

from django.db.models import ForeignKey, OneToOneField, ManyToManyField
from django.db.models import Model as DjangoModel


class GenericExportModelAdmin(ModelAdmin):
    actions = ["export_as_csv"]

    def __init__(self, model, admin_site):
        self.list_display = [field.name for field in model._meta.fields]
        search_fields = []
        for field in model._meta.fields:
            if not isinstance(field, (ForeignKey, OneToOneField, ManyToManyField)):
                search_fields.append(field.name)
            elif isinstance(field, (ForeignKey, OneToOneField)):
                # Check if related model has a 'name' attribute
                rel_model = field.remote_field.model
                if any(f.name == "name" for f in rel_model._meta.fields):
                    search_fields.append(f"{field.name}__name")
        self.search_fields = search_fields
        super().__init__(model, admin_site)

    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f"attachment; filename={meta}.csv"
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])
        return response

    export_as_csv.short_description = "Export Selected as CSV"


_ipcc_module_ns = dict(globals())
_excluded_prefixes = (
    "ForestManagementAGB",
    "PerennialAGB",
    "PerennialBGB",
    "AfforestationFLU",
    "LivestockTAM",
    "LivestockVSER",
    "LivestockManureEF",
    "FLUData",
    "LivestockAWMS",
    "ForestManagementRootToShoot",
    "ForestTotalBiomass",
)
for model_name in [
    name
    for name in _ipcc_module_ns
    if not name.startswith("_") and not name.startswith(_excluded_prefixes)
]:
    candidate = _ipcc_module_ns.get(model_name)
    if not isinstance(candidate, type) or not issubclass(candidate, DjangoModel):
        continue
    try:
        admin.site.register(candidate, GenericExportModelAdmin)
    except Exception:
        pass


class AGBAdmin(GenericExportModelAdmin):
    search_fields = ["climate__name", "moisture__name", "land_use_type__name", "value"]


class BGBAdmin(GenericExportModelAdmin):
    search_fields = [
        "climate__name",
        "moisture__name",
        "land_use_type__name",
        "continent__name",
    ]


class AfforestationFLUAdmin(GenericExportModelAdmin):
    search_fields = ["climate__name", "moisture__name", "land_use_type__name"]


class LivestockAWMSAdmin(GenericExportModelAdmin):
    list_display = [
        "livestock_production_type",
        "livestock_category_type",
        "manure_management_type",
        "ipcc_region",
        "value",
    ]

    list_select_related = [
        "livestock_production_type",
        "livestock_category_type",
        "manure_management_type",
        "ipcc_region",
    ]

    search_fields = [
        "livestock_production_type__name",
        "livestock_category_type__name",
        "manure_management_type__name",
        "ipcc_region__name",
    ]


class LivestockTAMAdmin(GenericExportModelAdmin):
    list_display = [
        "livestock_production_type",
        "livestock_category_type",
        "ipcc_region",
        "value",
    ]

    list_select_related = [
        "livestock_production_type",
        "livestock_category_type",
        "ipcc_region",
    ]

    search_fields = [
        "livestock_production_type__name",
        "livestock_category_type__name",
        "ipcc_region__name",
    ]


class ForestManagementAGBAdmin(GenericExportModelAdmin):
    list_display = [
        "forest_type",
        "climate",
        "land_use_type",
        "forest_condition_type",
        "from_year",
        "region",
        "agb_min",
        "agb_max",
        "agb_growth_min",
        "agb_growth_max",
    ]

    list_select_related = [
        "climate",
        "land_use_type",
        "region",
        "forest_type",
        "forest_condition_type",
    ]

    search_fields = [
        "climate__name",
        "land_use_type__name",
        "region__name",
        "forest_type__name",
        "forest_condition_type__name",
    ]


class LivestockVSERAdmin(GenericExportModelAdmin):
    list_display = [
        "livestock_production_type",
        "livestock_category_type",
        "ipcc_region",
        "value",
    ]

    list_select_related = [
        "livestock_production_type",
        "livestock_category_type",
        "ipcc_region",
    ]

    search_fields = [
        "livestock_production_type__name",
        "livestock_category_type__name",
        "ipcc_region__name",
    ]


class LivestockManureEFAdmin(GenericExportModelAdmin):
    list_display = [
        "emission_type",
        "livestock_production_type",
        "livestock_category_type",
        "manure_management_type",
        "climate",
        "moisture",
        "value",
    ]

    list_select_related = [
        "emission_type",
        "livestock_production_type",
        "livestock_category_type",
        "manure_management_type",
        "climate",
        "moisture",
    ]

    search_fields = [
        "emission_type__name",
        "livestock_production_type__name",
        "livestock_category_type__name",
        "manure_management_type__name",
        "climate__name",
        "moisture__name",
    ]


class FLUDataAdmin(GenericExportModelAdmin):
    search_fields = ["climate__name", "moisture__name", "land_use_type__name", "value"]


class ForestManagementRootToShootAdmin(GenericExportModelAdmin):
    list_display = [
        "climate",
        "region",
        "forest_type",
        "land_use_type",
        "threshold",
        "value",
    ]

    list_select_related = [
        "land_use_type",
        "region",
        "forest_type",
        "climate",
    ]

    search_fields = [
        "land_use_type__name",
        "region__name",
        "forest_type__name",
        "climate__name",
        "threshold",
    ]


class ForestTotalBiomassAdmin(GenericExportModelAdmin):
    list_display = [
        "climate",
        "moisture",
        "continent",
        "land_use_type",
        "value",
    ]

    list_select_related = [
        "land_use_type",
        "continent",
        "climate",
        "moisture",
    ]

    search_fields = [
        "land_use_type__name",
        "continent__name",
        "climate__name",
        "moisture__name",
    ]


admin.site.register(FLUData, FLUDataAdmin)
admin.site.register(PerennialAGB, AGBAdmin)
admin.site.register(PerennialBGB, BGBAdmin)
admin.site.register(AfforestationFLU, AfforestationFLUAdmin)
admin.site.register(LivestockTAM, LivestockTAMAdmin)
admin.site.register(LivestockVSER, LivestockVSERAdmin)
admin.site.register(LivestockManureEF, LivestockManureEFAdmin)
admin.site.register(ForestManagementAGB, ForestManagementAGBAdmin)
admin.site.register(LivestockAWMS, LivestockAWMSAdmin)
admin.site.register(ForestManagementRootToShoot, ForestManagementRootToShootAdmin)
admin.site.register(ForestTotalBiomass, ForestTotalBiomassAdmin)
