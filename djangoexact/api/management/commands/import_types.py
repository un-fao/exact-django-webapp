import json
import os

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Load models ending with "Type" from a fixture in a specified app'

    def add_arguments(self, parser):
        parser.add_argument("app_label", type=str, help="App label of the Django application")
        parser.add_argument("fixture", type=str, help="Fixture file name")

    def handle(self, *args, **options):
        app_label = options["app_label"]
        fixture_file = options["fixture"]

        # Load and parse the fixture file
        try:
            with open(fixture_file, "r") as file:
                data = json.load(file)
        except IOError:
            raise CommandError(f"Cannot open fixture file: {fixture_file}")

        # Filter out the models that belong to the specified app and end with 'Type'
        type_model_data = [obj for obj in data if obj["model"].startswith(app_label) and obj["model"].split(".")[-1].endswith("type")]

        if not type_model_data:
            self.stdout.write(self.style.WARNING("No matching models found in the fixture"))
            return

        # Write the filtered data to a temporary file
        temp_fixture_path = "temp_type_models_fixture.json"
        with open(temp_fixture_path, "w") as file:
            json.dump(type_model_data, file)

        # Load the filtered fixture
        try:
            call_command("loaddata", temp_fixture_path)
        except CommandError as e:
            raise CommandError(f"Error loading fixture: {e}")
        finally:
            # Clean up: Remove the temporary file
            os.remove(temp_fixture_path)

        self.stdout.write(self.style.SUCCESS('Successfully loaded models ending with "Type"'))
