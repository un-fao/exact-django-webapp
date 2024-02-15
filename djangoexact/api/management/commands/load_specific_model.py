import json
import os

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Load only a specific model from a fixture"

    def add_arguments(self, parser):
        parser.add_argument("fixture", type=str, help="Fixture file name")
        parser.add_argument("model", type=str, help="Model to keep in the format app_label.model_name")

    def handle(self, *args, **options):
        fixture_file = options["fixture"]
        model_to_keep = options["model"]

        # Load and parse the fixture file
        with open(fixture_file, "r") as file:
            data = json.load(file)

        # Keep only the specified model
        filtered_data = [obj for obj in data if obj["model"].lower() == model_to_keep.lower()]

        # Write the filtered data to a temporary file
        temp_fixture_path = "temp_specific_model_fixture.json"
        with open(temp_fixture_path, "w") as file:
            json.dump(filtered_data, file)

        # Load the fixture
        try:
            call_command("loaddata", temp_fixture_path)
        except CommandError as e:
            raise CommandError(f"Error loading fixture: {e}")
        finally:
            # Clean up: Remove the temporary file
            os.remove(temp_fixture_path)

        self.stdout.write(self.style.SUCCESS(f"Successfully loaded model {model_to_keep} from fixture."))
