from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import *

for model in [model for model in dir() if not model.startswith("_") and not model.startswith("ForestManagementAGB") and not model.startswith("PerennialAGB") and not model.startswith("PerennialBGB") and not model.startswith("AfforestationFLU") and not model.startswith("LivestockTAM") and not model.startswith("LivestockVSER") and not model.startswith("LivestockManureEF") and not model.startswith("FLUData") and not model.startswith("LivestockAWMS") and not model.startswith("ForestManagementBGB")]:
    try:
        admin.site.register(eval(model), ModelAdmin)
    except:
        pass


class AGBAdmin(ModelAdmin):
    search_fields = ["climate__name", "moisture__name", "land_use_type__name", "value"]


class BGBAdmin(ModelAdmin):
    search_fields = [
        "climate__name",
        "moisture__name",
        "land_use_type__name",
        "continent__name",
    ]


class AfforestationFLUAdmin(ModelAdmin):
    search_fields = ["climate__name", "moisture__name", "land_use_type__name"]


class LivestockAWMSAdmin(ModelAdmin):
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


class LivestockTAMAdmin(ModelAdmin):
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


class ForestManagementAGBAdmin(ModelAdmin):
    list_display = [
        "forest_type",
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
        "land_use_type",
        "region",
        "forest_type",
        "forest_condition_type",
    ]

    search_fields = [
        "land_use_type__name",
        "region__name",
        "forest_type__name",
        "forest_condition_type__name",
    ]


class LivestockVSERAdmin(ModelAdmin):
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


class LivestockManureEFAdmin(ModelAdmin):
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


class FLUDataAdmin(ModelAdmin):
    search_fields = ["climate__name", "moisture__name", "land_use_type__name", "value"]


class ForestManagementBGBAdmin(ModelAdmin):
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
        "threshold",
    ]

    search_fields = [
        "land_use_type__name",
        "region__name",
        "forest_type__name",
        "forest_condition_type__name",
        "climate__name",
        "threshold",
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
admin.site.register(ForestManagementBGB, ForestManagementBGBAdmin)
