import json
import os
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Test the generalized import changes command with sample data"

    def add_arguments(self, parser):
        parser.add_argument("--module-type", type=str, choices=["livestock", "annual-cropland", "flooded-rice", "grassland"], default="livestock", help="Module type to test")
        parser.add_argument("--no-progress", action="store_true", help="Disable progress bar for testing")

    def handle(self, *args, **options):
        module_type = options["module_type"]
        no_progress = options["no_progress"]

        # Create a small test file with sample data
        test_data = self.create_test_data(module_type)
        test_file_path = f"test_{module_type}_changes.json"

        # Write test data to file
        with open(test_file_path, "w") as f:
            json.dump(test_data, f, indent=2)

        self.stdout.write(f"Created test file: {test_file_path}")
        self.stdout.write(f"Test data contains {len(test_data)} records")

        # Test the import command
        try:
            call_command("import_changes", file=test_file_path, module_type=module_type, clear=True, no_progress=no_progress)
            self.stdout.write(self.style.SUCCESS("Import test completed successfully!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Import test failed: {e}"))
        finally:
            # Clean up test file
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
                self.stdout.write(f"Cleaned up test file: {test_file_path}")

    def create_test_data(self, module_type):
        """Create sample test data for the specified module type."""
        if module_type == "livestock":
            return [
                {
                    "module_type": "Livestock",
                    "region": "Test Region",
                    "climate": "Test Climate",
                    "moisture": "Test Moisture",
                    "soil_type": "Test Soil",
                    "total": 10.5,
                    "changes": [{"field": "livestock_production_type", "from": "Default", "to": "High-Productivity"}],
                    "livestock_category_type": "Dairy Cattle",
                },
                {
                    "module_type": "Livestock",
                    "region": "Test Region 2",
                    "climate": "Test Climate 2",
                    "moisture": "Test Moisture 2",
                    "soil_type": "Test Soil 2",
                    "total": 15.2,
                    "changes": [{"field": "livestock_production_type", "from": "Default", "to": "Low-Productivity"}],
                    "livestock_category_type": "Beef Cattle",
                },
            ]
        elif module_type == "annual-cropland":
            return [
                {
                    "module_type": "Annual Cropland",
                    "region": "Test Region",
                    "climate": "Test Climate",
                    "moisture": "Test Moisture",
                    "soil_type": "Test Soil",
                    "total": -5.2,
                    "changes": [{"field": "residue_management_type", "from": "Burned", "to": "Retained"}],
                }
            ]
        elif module_type == "flooded-rice":
            return [
                {
                    "module_type": "Floodedrice",
                    "region": "Test Region",
                    "climate": "Test Climate",
                    "moisture": "Test Moisture",
                    "soil_type": "Test Soil",
                    "total": -3.1,
                    "changes": [{"field": "organic_amendment_type", "from": "Straw Burnt", "to": "Straw Exported"}],
                }
            ]
        elif module_type == "grassland":
            return [
                {
                    "module_type": "Grassland",
                    "region": "Test Region",
                    "climate": "Test Climate",
                    "moisture": "Test Moisture",
                    "soil_type": "Test Soil",
                    "total": -2.5,
                    "changes": [{"field": "fire_impact", "from": 1, "to": 0}],
                    "module": "Grassland",
                }
            ]

        return []
