import json
import os
import statistics
import sys
import time
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction
from minitool.models import (
    ChangeRecord,
    ChangeAggregate,
)


class Command(BaseCommand):
    help = "Import changes data from JSON files into database models for all module types"

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, help="Path to the changes JSON file")
        parser.add_argument(
            "--module-type",
            type=str,
            choices=["livestock", "annual-cropland", "flooded-rice", "grassland", "perennial-cropland", "forest-management", "small-fishery", "large-fishery"],
            help="Module type to import",
        )
        parser.add_argument("--clear", action="store_true", help="Clear existing data before importing")
        parser.add_argument("--aggregate-only", action="store_true", help="Only create aggregated data, skip individual records")
        parser.add_argument("--all", action="store_true", help="Import all module types from their respective files")
        parser.add_argument("--no-progress", action="store_true", help="Disable progress bar and status updates")

    def handle(self, *args, **options):
        clear_existing = options["clear"]
        aggregate_only = options["aggregate_only"]
        import_all = options["all"]
        show_progress = not options["no_progress"]

        if import_all:
            self.import_all_modules(clear_existing, aggregate_only, show_progress)
        else:
            file_path = options["file"]
            module_type = options["module_type"]

            if not file_path or not module_type:
                self.stdout.write(self.style.ERROR("Both --file and --module-type are required unless using --all"))
                return

            self.import_single_module(file_path, module_type, clear_existing, aggregate_only, show_progress)

    def import_all_modules(self, clear_existing, aggregate_only, show_progress):
        """Import all module types from their respective files."""
        module_configs = [
            ("livestock", "livestock_changes.json"),
            ("annualcropland", "annualcropland_changes.json"),
            ("floodedrice", "floodedrice_changes.json"),
            ("grassland", "grassland_changes.json"),
            ("perennialcropland", "perennialcropland_changes.json"),
            ("forestmanagement", "forestmanagement_changes.json"),
            ("smallfishery", "smallfishery_changes.json"),
            ("largefishery", "largefishery_changes.json"),
        ]

        total_modules = len(module_configs)
        for idx, (module_type, filename) in enumerate(module_configs, 1):
            if show_progress:
                self.stdout.write(f"\n{'=' * 50}")
                self.stdout.write(f"Processing {module_type.upper()} ({idx}/{total_modules})")
                self.stdout.write(f"{'=' * 50}")
            else:
                self.stdout.write(f"\nProcessing {module_type.upper()} ({idx}/{total_modules})")

            # Only clear on first iteration
            should_clear = clear_existing and module_type == "livestock"
            self.import_single_module(filename, module_type, should_clear, aggregate_only, show_progress)

    def import_single_module(self, file_path, module_type, clear_existing, aggregate_only, show_progress):
        """Import data for a single module type."""
        # Resolve file path
        if not os.path.isabs(file_path):
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            file_path = os.path.join(script_dir, "data", "changes", file_path)

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        # Load JSON data
        if show_progress:
            self.stdout.write(f"Loading data from {file_path}...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading JSON file: {e}"))
            return

        total_records = len(data)
        if show_progress:
            self.stdout.write(f"Loaded {total_records:,} records")

        # Clear existing data if requested
        if clear_existing:
            if show_progress:
                self.stdout.write("Clearing existing data...")
            # Clear data for this specific module type
            ChangeRecord.objects.filter(module_type__icontains=module_type.replace("-", " ").title()).delete()
            ChangeAggregate.objects.filter(module_type__icontains=module_type.replace("-", " ").title()).delete()
            if show_progress:
                self.stdout.write("Existing data cleared")

        # Import individual records
        if not aggregate_only:
            self.import_individual_records(data, module_type, show_progress, total_records)

        # Create aggregated data
        self.create_aggregated_data(data, module_type, show_progress, total_records)

        if show_progress:
            self.stdout.write(self.style.SUCCESS(f"Import completed successfully for {module_type}!"))
        else:
            self.stdout.write(f"Import completed for {module_type}")

    def identify_filter_columns(self, data, module_type):
        """
        Identify filter columns based on the rule:
        - If a column is not numerical and doesn't end with "_start", "_w", or "_wo",
          it should be used as a filter
        """
        if not data:
            return []

        # Get all unique keys from the data
        all_keys = set()
        for record in data:
            all_keys.update(record.keys())

        # Standard filter columns that are always included
        standard_filters = {"module_type", "region", "climate", "moisture", "soil_type", "total", "changes"}

        # Identify custom filter columns
        custom_filters = []
        for key in all_keys:
            if key in standard_filters:
                continue

            # Check if it's a numerical field by looking at the first few records
            is_numerical = True
            for record in data[:10]:  # Check first 10 records
                if key in record:
                    value = record[key]
                    if value is not None and value != "":
                        try:
                            float(value)
                        except (ValueError, TypeError):
                            is_numerical = False
                            break

            # If not numerical and doesn't end with excluded suffixes, it's a filter
            if not is_numerical and not any(key.endswith(suffix) for suffix in ["_start", "_w", "_wo"]):
                custom_filters.append(key)

        return custom_filters

    def extract_filter_fields(self, record, filter_columns):
        """Extract filter fields from a record."""
        filter_fields = {}
        for column in filter_columns:
            if column in record:
                filter_fields[column] = record.get(column, "")
        return filter_fields

    def import_individual_records(self, data, module_type, show_progress, total_records):
        """Import individual change records."""
        if show_progress:
            self.stdout.write("Importing individual records...")

        # Identify filter columns for this module
        filter_columns = self.identify_filter_columns(data, module_type)
        if show_progress and filter_columns:
            self.stdout.write(f"Identified filter columns: {', '.join(filter_columns)}")

        records_created = 0
        records_skipped = 0
        processed_records = 0

        with transaction.atomic():
            for record in data:
                processed_records += 1

                # Show progress
                if show_progress and processed_records % 1000 == 0:
                    self.update_progress("Individual Records", processed_records, total_records, records_created, records_skipped)

                # Extract common fields
                module_type_value = record.get("module_type", "")
                region = record.get("region", "")
                climate = record.get("climate", "")
                moisture = record.get("moisture", "")
                soil_type = record.get("soil_type", "")
                total = record.get("total", 0)

                # Extract custom filter fields
                filter_fields = self.extract_filter_fields(record, filter_columns)

                for change in record.get("changes", []):
                    field = change.get("field", "")
                    from_value = change.get("from", "")
                    to_value = change.get("to", "")

                    # Skip if any required field is empty
                    if not all([field, from_value, to_value]):
                        records_skipped += 1
                        continue

                    # Create or update record
                    change_record, created = ChangeRecord.objects.get_or_create(
                        module_type=module_type_value,
                        region=region,
                        climate=climate,
                        moisture=moisture,
                        soil_type=soil_type,
                        field=field,
                        from_value=str(from_value),
                        to_value=str(to_value),
                        custom_filters=filter_fields,
                        defaults={"total": total},
                    )

                    if created:
                        records_created += 1
                    else:
                        # Update total if record already exists
                        change_record.total = total
                        change_record.save()

        # Final progress update
        if show_progress:
            self.update_progress("Individual Records", processed_records, total_records, records_created, records_skipped, final=True)
        else:
            self.stdout.write(f"Individual records: {records_created:,} created, {records_skipped:,} skipped")

    def create_aggregated_data(self, data, module_type, show_progress, total_records):
        """Create aggregated change statistics."""
        if show_progress:
            self.stdout.write("Creating aggregated data...")

        # Identify filter columns for this module
        filter_columns = self.identify_filter_columns(data, module_type)

        # Group data by change type and filters
        aggregations = {}
        processed_records = 0

        for record in data:
            processed_records += 1

            # Show progress during aggregation
            if show_progress and processed_records % 1000 == 0:
                self.update_progress("Aggregating Data", processed_records, total_records, len(aggregations), 0)

            total = record.get("total", 0)

            for change in record.get("changes", []):
                field = change.get("field", "")
                from_value = change.get("from", "")
                to_value = change.get("to", "")

                if not all([field, from_value, to_value]):
                    continue

                # Create aggregation key with standard fields
                key_parts = [field, str(from_value), str(to_value), record.get("region"), record.get("climate"), record.get("moisture"), record.get("soil_type"), record.get("module_type")]

                # Add custom filter fields to the key
                for column in filter_columns:
                    if column in record:
                        key_parts.append(record.get(column, ""))

                key = tuple(key_parts)

                if key not in aggregations:
                    aggregations[key] = []
                aggregations[key].append(total)

        # Calculate statistics and create aggregated records
        records_created = 0
        records_updated = 0
        total_aggregations = len(aggregations)
        processed_aggregations = 0

        if show_progress:
            self.stdout.write(f"Processing {total_aggregations:,} unique aggregations...")

        with transaction.atomic():
            for key, values in aggregations.items():
                processed_aggregations += 1

                # Show progress during database operations
                if show_progress and processed_aggregations % 100 == 0:
                    self.update_progress("Saving Aggregations", processed_aggregations, total_aggregations, records_created, records_updated)

                # Extract key parts
                base_parts = 8  # field, from_value, to_value, region, climate, moisture, soil_type, module_type
                field, from_value, to_value, region, climate, moisture, soil_type, module_type = key[:base_parts]

                # Extract custom filter fields
                custom_filters = {}
                for i, column in enumerate(filter_columns):
                    if i < len(key) - base_parts:
                        custom_filters[column] = key[base_parts + i]

                # Calculate statistics
                stats = self.calculate_statistics(values)

                # Create or update aggregated record
                aggregate_record, created = ChangeAggregate.objects.get_or_create(
                    module_type=module_type,
                    field=field,
                    from_value=from_value,
                    to_value=to_value,
                    region=region,
                    climate=climate,
                    moisture=moisture,
                    soil_type=soil_type,
                    custom_filters=custom_filters,
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

        # Final progress update
        if show_progress:
            self.update_progress("Saving Aggregations", processed_aggregations, total_aggregations, records_created, records_updated, final=True)
        else:
            self.stdout.write(f"Aggregated records: {records_created:,} created, {records_updated:,} updated")

    def calculate_statistics(self, values):
        """Calculate statistical measures for a list of values."""
        if not values:
            return {"count": 0, "sum": 0, "mean": 0, "median": 0, "min": 0, "max": 0, "q1": 0, "q3": 0}

        sorted_values = sorted(values)
        n = len(sorted_values)

        # Use statistics.quantiles for proper quartile calculation
        if n >= 4:
            q1, q3 = statistics.quantiles(sorted_values, n=4)[0], statistics.quantiles(sorted_values, n=4)[2]
        else:
            # For small datasets, use interpolation method
            q1_idx = (n - 1) * 0.25
            q3_idx = (n - 1) * 0.75

            # Interpolate if needed
            if q1_idx.is_integer():
                q1 = sorted_values[int(q1_idx)]
            else:
                lower_idx = int(q1_idx)
                upper_idx = min(lower_idx + 1, n - 1)
                weight = q1_idx - lower_idx
                q1 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

            if q3_idx.is_integer():
                q3 = sorted_values[int(q3_idx)]
            else:
                lower_idx = int(q3_idx)
                upper_idx = min(lower_idx + 1, n - 1)
                weight = q3_idx - lower_idx
                q3 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

        return {
            "count": n,
            "sum": sum(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "q1": q1,
            "q3": q3,
        }

    def update_progress(self, phase, current, total, created, skipped, final=False):
        """Update progress bar and status information."""
        if total == 0:
            return

        percentage = (current / total) * 100
        bar_length = 30
        filled_length = int(bar_length * current // total)
        bar = "█" * filled_length + "-" * (bar_length - filled_length)

        # Format numbers with commas
        current_fmt = f"{current:,}"
        total_fmt = f"{total:,}"
        created_fmt = f"{created:,}"
        skipped_fmt = f"{skipped:,}"

        # Create status line
        status_line = f"\r{phase}: [{bar}] {percentage:5.1f}% | {current_fmt}/{total_fmt} | Created: {created_fmt} | Skipped: {skipped_fmt}"

        # Clear line and write status
        self.stdout.write(status_line, ending="")
        self.stdout.flush()

        if final:
            self.stdout.write()  # New line after completion

    def clear_line(self):
        """Clear the current line in the terminal."""
        self.stdout.write("\r" + " " * 80 + "\r", ending="")
        self.stdout.flush()
