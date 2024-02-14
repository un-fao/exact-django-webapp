import json
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Splits models ending with "Type" from a fixture into separate fixtures'

    def add_arguments(self, parser):
        parser.add_argument("fixture", type=str, help="Fixture file name")

    def handle(self, *args, **options):
        fixture_file = options["fixture"]

        try:
            with open(fixture_file, "r") as file:
                data = json.load(file)
        except IOError:
            raise CommandError(f"Cannot open fixture file: {fixture_file}")

        # Organize data by model
        models_data = defaultdict(list)
        for entry in data:
            model_name = entry["model"]
            if model_name.split(".")[-1].endswith("type"):
                models_data[model_name].append(entry)

        if not models_data:
            self.stdout.write(self.style.WARNING('No models ending with "Type" found'))
            return

        # Create a separate fixture file for each model
        for model, entries in models_data.items():
            model_fixture_file = f"{model.split('.')[-1].lower()}_type_fixture.json"
            app = model.split(".")[0]
            with open(app + "/fixtures/" + model_fixture_file, "w") as file:
                json.dump(entries, file)
            self.stdout.write(self.style.SUCCESS(f"Created fixture for {model}: {model_fixture_file}"))
