from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import *


for model in [model for model in dir() if not model.startswith("_")]:
    try:
        admin.site.register(eval(model), ModelAdmin)
    except:
        pass
