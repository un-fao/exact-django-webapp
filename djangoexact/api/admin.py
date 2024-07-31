from django.contrib import admin

from .models import *

for model in [model for model in dir() if not model.startswith("_")]:
    try:
        admin.site.register(eval(model))
    except:
        pass
