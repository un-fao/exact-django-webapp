import json

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Load a fixture while skipping specific models"

    def add_arguments(self, parser):
        parser.add_argument("fixture", type=str, help="Fixture file name")

    def handle(self, *args, **options):
        fixture_file = options["fixture"]
        models_to_skip = ["auditlog.logentry", "api.comment", "api.project", "api.activity", "admin.logentry"]  # Add your model(s) here

        # Load and parse the fixture file
        with open(fixture_file, "r") as file:
            data = json.load(file)

        # Filter out the models to skip
        filtered_data = [obj for obj in data if obj["model"] not in models_to_skip]

        # Write the filtered data to a temporary file
        with open("temp_fixture.json", "w") as file:
            json.dump(filtered_data, file)

        # Load the fixture
        try:
            call_command("loaddata", "temp_fixture.json")
        except CommandError as e:
            raise CommandError(f"Error loading fixture: {e}")
        finally:
            # Clean up: Remove the temporary file
            import os

            os.remove("temp_fixture.json")

        self.stdout.write(self.style.SUCCESS("Successfully loaded fixture, skipping specified models."))
