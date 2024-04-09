import json
from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create fixtures for models ending with 'type', 'parameter' or 'param'"

    def add_arguments(self, parser):
        parser.add_argument("app_name", type=str, help="Model name")

    def handle(self, *args, **options):
        app_name = options["app_name"]

        if app_name not in [app.name for app in apps.get_app_configs()]:
            raise CommandError(f"App '{app_name}' does not exist")

        models_ending_with_type = [model for model in apps.get_app_config("api").get_models() if model.__name__.endswith("Type")]
        models_ending_with_parameter = [model for model in apps.get_app_config("api").get_models() if model.__name__.endswith("Parameter")]
        models_ending_with_param = [model for model in apps.get_app_config("api").get_models() if model.__name__.endswith("Param")]
        models_ending_with_type.append(apps.get_model("api", "Region"))
        models_ending_with_type.append(apps.get_model("api", "Country"))
        models_ending_with_type.append(apps.get_model("api", "ProjectStatus"))
        models_ending_with_type.append(apps.get_model("api", "Climate"))
        models_ending_with_type.append(apps.get_model("api", "Moisture"))

        models_data = defaultdict(list)
        for model in models_ending_with_type + models_ending_with_parameter + models_ending_with_param:
            model_label = f"{model._meta.app_label}.{model.__name__}"
            for instance in model.objects.all():
                models_data[model_label].append(instance.__dict__)

        # Create only one fixture file for all models
        fixture_file = "starting_fixtures.json"
        with open(f"{apps.get_app_config(app_name).path}/fixtures/" + fixture_file, "w") as file:
            json.dump(models_data, file)
