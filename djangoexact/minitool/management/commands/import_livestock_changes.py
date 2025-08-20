import json
import os
import statistics
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction
from minitool.models import LivestockChange, LivestockChangeAggregate


class Command(BaseCommand):
    help = "Import livestock changes data from JSON file into database models"

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, default="livestock_changes.json", help="Path to the livestock changes JSON file")
        parser.add_argument("--clear", action="store_true", help="Clear existing data before importing")
        parser.add_argument("--aggregate-only", action="store_true", help="Only create aggregated data, skip individual records")

    def handle(self, *args, **options):
        file_path = options["file"]
        clear_existing = options["clear"]
        aggregate_only = options["aggregate_only"]

        # Resolve file path
        if not os.path.isabs(file_path):
            # Look in the minitool app directory
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            file_path = os.path.join(script_dir, file_path)

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        # Load JSON data
        self.stdout.write(f"Loading data from {file_path}...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading JSON file: {e}"))
            return

        self.stdout.write(f"Loaded {len(data)} records")

        # Clear existing data if requested
        if clear_existing:
            self.stdout.write("Clearing existing data...")
            LivestockChange.objects.all().delete()
            LivestockChangeAggregate.objects.all().delete()
            self.stdout.write("Existing data cleared")

        # Import individual records
        if not aggregate_only:
            self.import_individual_records(data)

        # Create aggregated data
        self.create_aggregated_data(data)

        self.stdout.write(self.style.SUCCESS("Import completed successfully!"))

    def import_individual_records(self, data):
        """Import individual livestock change records."""
        self.stdout.write("Importing individual records...")

        records_created = 0
        records_skipped = 0

        with transaction.atomic():
            for record in data:
                module_type = record.get("module_type", "Livestock")
                region = record.get("region", "")
                climate = record.get("climate", "")
                moisture = record.get("moisture", "")
                soil_type = record.get("soil_type", "")
                livestock_category_type = record.get("livestock_category_type", "")
                total = record.get("total", 0)

                for change in record.get("changes", []):
                    field = change.get("field", "")
                    from_value = change.get("from", "")
                    to_value = change.get("to", "")

                    # Skip if any required field is empty
                    if not all([field, from_value, to_value]):
                        records_skipped += 1
                        continue

                    # Create or update record
                    livestock_change, created = LivestockChange.objects.get_or_create(
                        module_type=module_type,
                        region=region,
                        climate=climate,
                        moisture=moisture,
                        soil_type=soil_type,
                        livestock_category_type=livestock_category_type,
                        field=field,
                        from_value=from_value,
                        to_value=to_value,
                        defaults={"total": total},
                    )

                    if created:
                        records_created += 1
                    else:
                        # Update total if record already exists
                        livestock_change.total = total
                        livestock_change.save()

        self.stdout.write(f"Individual records: {records_created} created, {records_skipped} skipped")

    def create_aggregated_data(self, data):
        """Create aggregated livestock change statistics."""
        self.stdout.write("Creating aggregated data...")

        # Group data by change type and filters
        aggregations = {}

        for record in data:
            total = record.get("total", 0)

            for change in record.get("changes", []):
                field = change.get("field", "")
                from_value = change.get("from", "")
                to_value = change.get("to", "")

                if not all([field, from_value, to_value]):
                    continue

                # Create aggregation key
                key = (field, from_value, to_value, record.get("region"), record.get("climate"), record.get("moisture"), record.get("soil_type"), record.get("livestock_category_type"))

                if key not in aggregations:
                    aggregations[key] = []
                aggregations[key].append(total)

        # Calculate statistics and create aggregated records
        records_created = 0
        records_updated = 0

        with transaction.atomic():
            for key, values in aggregations.items():
                field, from_value, to_value, region, climate, moisture, soil_type, livestock_category_type = key

                # Calculate statistics
                stats = self.calculate_statistics(values)

                # Create or update aggregated record
                aggregate_record, created = LivestockChangeAggregate.objects.get_or_create(
                    field=field,
                    from_value=from_value,
                    to_value=to_value,
                    region=region,
                    climate=climate,
                    moisture=moisture,
                    soil_type=soil_type,
                    livestock_category_type=livestock_category_type,
                    defaults={
                        "count": stats["count"],
                        "sum_total": stats["sum"],
                        "mean": stats["mean"],
                        "median": stats["median"],
                        "min_value": stats["min"],
                        "max_value": stats["max"],
                        "q1": stats["q1"],
                        "q3": stats["q3"],
                    },
                )

                if created:
                    records_created += 1
                else:
                    # Update statistics
                    aggregate_record.count = stats["count"]
                    aggregate_record.sum_total = stats["sum"]
                    aggregate_record.mean = stats["mean"]
                    aggregate_record.median = stats["median"]
                    aggregate_record.min_value = stats["min"]
                    aggregate_record.max_value = stats["max"]
                    aggregate_record.q1 = stats["q1"]
                    aggregate_record.q3 = stats["q3"]
                    aggregate_record.save()
                    records_updated += 1

        self.stdout.write(f"Aggregated records: {records_created} created, {records_updated} updated")

    def calculate_statistics(self, values):
        """Calculate statistical measures for a list of values."""
        if not values:
            return {"count": 0, "sum": 0, "mean": 0, "median": 0, "min": 0, "max": 0, "q1": 0, "q3": 0}

        sorted_values = sorted(values)
        n = len(sorted_values)

        q1_idx = n // 4
        q3_idx = 3 * n // 4

        return {
            "count": n,
            "sum": sum(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "q1": sorted_values[q1_idx] if n > 0 else 0,
            "q3": sorted_values[q3_idx] if n > 0 else 0,
        }
