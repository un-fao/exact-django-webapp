# app_name/management/commands/create_type_fixtures.py

import json
from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create fixtures for models ending with "type"'

    def handle(self, *args, **options):
        models_ending_with_type = [model for model in apps.get_app_config("api").get_models() if model.__name__.endswith("Type")]

        models_data = defaultdict(list)
        for model in models_ending_with_type:
            model_label = f"{model._meta.app_label}.{model.__name__}"
            for instance in model.objects.all():
                models_data[model_label].append(instance)

        # Create only one fixture file for all models
        fixture_file = "type_fixtures.json"
        with open("api/fixtures/" + fixture_file, "w") as file:
            json.dump(models_data, file)
