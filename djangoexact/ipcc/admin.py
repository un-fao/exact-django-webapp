from django.contrib import admin
from .models import *

for model in [model for model in dir() if not model.startswith('_') and not model.startswith('PerennialAGB') and not model.startswith('PerennialBGB') and not model.startswith('AfforestationFLU')]:
    try:
        admin.site.register(eval(model))
    except:
        pass

class AGBAdmin(admin.ModelAdmin):
    search_fields = ['climate__name', 'moisture__name', 'land_use_type__name']

class BGBAdmin(admin.ModelAdmin):
    search_fields = ['climate__name', 'moisture__name', 'land_use_type__name', 'continent__name']

class AfforestationFLUAdmin(admin.ModelAdmin):
    search_fields = ['climate__name', 'moisture__name', 'land_use_type__name']

admin.site.register(PerennialAGB, AGBAdmin)
admin.site.register(PerennialBGB, BGBAdmin)
admin.site.register(AfforestationFLU, AfforestationFLUAdmin)