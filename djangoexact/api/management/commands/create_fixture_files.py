import json
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from api.models import ModuleType


class Command(BaseCommand):
    help = "Splits each model from a specific app in a fixture into separate fixtures"

    def add_arguments(self, parser):
        parser.add_argument("app_label", type=str, help="App label of the Django application")
        parser.add_argument("fixture", type=str, help="Fixture file name")

    def handle(self, *args, **options):
        app_label = options["app_label"]
        fixture_file = options["fixture"]

        try:
            with open(fixture_file, "r") as file:
                data = json.load(file)
        except IOError:
            raise CommandError(f"Cannot open fixture file: {fixture_file}")

        # Organize data by model within the specified app
        models_data = defaultdict(list)
        for entry in data:
            model_label = entry["model"]
            if model_label.startswith(app_label + "."):
                models_data[model_label].append(entry)

        if not models_data:
            self.stdout.write(self.style.WARNING(f"No models found in the {app_label} app"))
            return

        # Create a separate fixture file for each model
        for model, entries in models_data.items():

            app = model.split(".")[0]
            model_name = model.split(".")[-1]

            if ModuleType.objects.filter(class_name__iexact=model_name).exists():
                self.stdout.write(self.style.WARNING(f"Skipping fixture for {model}"))
                continue

            if model_name in ["userprojectgroup", "projectinvitation", "project", "forestdisturbance", "customuser", "activity", "commentthread", "comment"]:
                self.stdout.write(self.style.WARNING(f"Skipping fixture for {model}"))
                continue

            model_fixture_file = f"{model_name.lower()}_fixture.json"
            with open(app + "/fixtures/starting_fixtures/" + model_fixture_file, "w") as file:
                json.dump(entries, file)
            self.stdout.write(self.style.SUCCESS(f"Created fixture for {model}: {model_fixture_file}"))
