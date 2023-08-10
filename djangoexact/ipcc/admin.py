from django.contrib import admin
from .models import *

for model in [
    model
    for model in dir()
    if not model.startswith("_")
    and not model.startswith("PerennialAGB")
    and not model.startswith("PerennialBGB")
    and not model.startswith("AfforestationFLU")
    and not model.startswith("LivestockTAM")
    and not model.startswith("LivestockVSER")
    and not model.startswith("LivestockManureEF")
]:
    try:
        admin.site.register(eval(model))
    except:
        pass


class AGBAdmin(admin.ModelAdmin):
    search_fields = ["climate__name", "moisture__name", "land_use_type__name"]


class BGBAdmin(admin.ModelAdmin):
    search_fields = [
        "climate__name",
        "moisture__name",
        "land_use_type__name",
        "continent__name",
    ]


class AfforestationFLUAdmin(admin.ModelAdmin):
    search_fields = ["climate__name", "moisture__name", "land_use_type__name"]


class LivestockTAMAdmin(admin.ModelAdmin):
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


class LivestockVSERAdmin(admin.ModelAdmin):
    list_display = [
        "emission_type",
        "livestock_production_type",
        "livestock_category_type",
        "ipcc_region",
        "value",
    ]

    list_select_related = [
        "emission_type",
        "livestock_production_type",
        "livestock_category_type",
        "ipcc_region",
    ]

    search_fields = [
        "emission_type__name",
        "livestock_production_type__name",
        "livestock_category_type__name",
        "ipcc_region__name",
    ]


class LivestockManureEFAdmin(admin.ModelAdmin):
    list_display = [
        "emission_type",
        "livestock_production_type",
        "livestock_category_type",
        "climate",
        "moisture",
        "value",
    ]

    list_select_related = [
        "emission_type",
        "livestock_production_type",
        "livestock_category_type",
        "climate",
        "moisture",
    ]

    search_fields = [
        "emission_type__name",
        "livestock_production_type__name",
        "livestock_category_type__name",
        "climate__name",
        "moisture__name",
    ]


admin.site.register(PerennialAGB, AGBAdmin)
admin.site.register(PerennialBGB, BGBAdmin)
admin.site.register(AfforestationFLU, AfforestationFLUAdmin)
admin.site.register(LivestockTAM, LivestockTAMAdmin)
admin.site.register(LivestockVSER, LivestockVSERAdmin)
admin.site.register(LivestockManureEF, LivestockManureEFAdmin)
