#!/usr/bin/env python3
"""
Django management command to import aggregated livestock data into EmissionStatisticsByModule model.
Run this script from the Django project root directory.
"""

import os
import sys
import django
import csv
from pathlib import Path

# Add the Django project to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
django.setup()

# Now import Django models
from minitool.models import EmissionStatisticsByModule


def import_aggregated_module_data():
    """
    Import aggregated module data from CSV into EmissionStatisticsByModule model.
    """
    # Get the script directory and locate the CSV file
    script_dir = Path(__file__).parent
    csv_file = script_dir / "aggregated_data" / "livestock" / "aggregated_by_environmental_factors.csv"

    if not csv_file.exists():
        print(f"Error: CSV file not found at {csv_file}")
        return

    print(f"Reading aggregated livestock data from {csv_file}...")

    # Read the CSV file
    imported_count = 0
    updated_count = 0

    try:
        with open(csv_file, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                # Extract environmental factors
                module_type = row["module_type"]
                region = row["region"]
                climate = row["climate"]
                moisture = row["moisture"]
                soil_type = row["soil_type"]

                # Extract statistical measures
                count = int(row["count"])
                total = float(row["sum"])
                mean = float(row["mean"])
                median = float(row["median"])
                min_val = float(row["min"])
                max_val = float(row["max"])
                q1 = float(row["q1"])
                q3 = float(row["q3"])

                # Check if record already exists
                existing_record, created = EmissionStatisticsByModule.objects.get_or_create(
                    module_type=module_type,
                    region=region,
                    climate=climate,
                    moisture=moisture,
                    soil_type=soil_type,
                    defaults={"count": count, "total": total, "mean": mean, "median": median, "min": min_val, "max": max_val, "q1": q1, "q3": q3},
                )

                if created:
                    imported_count += 1
                    print(f"  - Created new record: {module_type} | {region} | {climate} | {moisture} | {soil_type}")
                    print(f"    Sum: {total:.2f}, Mean: {mean:.2f}, Count: {count}")
                else:
                    # Update existing record
                    existing_record.count = count
                    existing_record.total = total
                    existing_record.mean = mean
                    existing_record.median = median
                    existing_record.min = min_val
                    existing_record.max = max_val
                    existing_record.q1 = q1
                    existing_record.q3 = q3
                    existing_record.save()
                    updated_count += 1
                    print(f"  - Updated existing record: {module_type} | {region} | {climate} | {moisture} | {soil_type}")
                    print(f"    Sum: {total:.2f}, Mean: {mean:.2f}, Count: {count}")

        print(f"\nImport completed successfully!")
        print(f"  - New records created: {imported_count}")
        print(f"  - Existing records updated: {updated_count}")
        print(f"  - Total records processed: {imported_count + updated_count}")

        # Show summary of all records in the model
        print(f"\nCurrent records in EmissionStatisticsByModule:")
        all_records = EmissionStatisticsByModule.objects.all().order_by("-total")
        for record in all_records:
            print(f"  - {record.module_type} | {record.region} | {record.climate} | {record.moisture} | {record.soil_type}")
            print(f"    Sum: {record.total:.2f}, Mean: {record.mean:.2f}, Count: {record.count}")

    except Exception as e:
        print(f"Error during import: {e}")
        return


def run():
    """
    Main function to run the import.
    """
    print("Starting import of aggregated livestock environmental factors data...")
    import_aggregated_module_data()
    print("Import process completed.")
