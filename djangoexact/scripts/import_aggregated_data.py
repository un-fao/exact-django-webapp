#!/usr/bin/env python3
"""
Django management command to import aggregated data into EmissionStatisticsByModule model.
Accepts any CSV file with the structure: module,region,climate,moisture,soil_type,count,sum,mean,median,min,max,q1,q3
(or module_type instead of module)

Usage:
    python import_aggregated_data.py <csv_file_path>

Run this script from the Django project root directory.
"""

import os
import sys
import django
import csv
import argparse
from pathlib import Path
from minitool.models import EmissionStatisticsByModule
import glob


def import_aggregated_module_data(csv_file_path):
    """
    Import aggregated module data from CSV into EmissionStatisticsByModule model.

    Args:
        csv_file_path (str): Path to the CSV file to import
    """
    csv_file = Path(csv_file_path)

    if not csv_file.exists():
        print(f"Error: CSV file not found at {csv_file}")
        return False

    print(f"Reading aggregated data from {csv_file}...")

    # Read the CSV file
    imported_count = 0
    updated_count = 0

    try:
        with open(csv_file, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            # Check if the required columns exist
            required_columns = {"region", "climate", "moisture", "soil_type", "count", "sum", "mean", "median", "min", "max", "q1", "q3"}
            module_column = None

            # Determine which module column is present
            if "module_type" in reader.fieldnames:
                module_column = "module_type"
            elif "module" in reader.fieldnames:
                module_column = "module"
            else:
                print("Error: CSV must contain either 'module' or 'module_type' column")
                return False

            missing_columns = required_columns - set(reader.fieldnames)
            if missing_columns:
                print(f"Error: Missing required columns: {missing_columns}")
                return False

            for row in reader:
                # Extract environmental factors
                module_type = row[module_column]
                region = row["region"]
                climate = row["climate"]
                moisture = row["moisture"]
                soil_type = row["soil_type"]

                # Extract statistical measures
                try:
                    count = int(row["count"])
                    total = float(row["sum"])
                    mean = float(row["mean"])
                    median = float(row["median"])
                    min_val = float(row["min"])
                    max_val = float(row["max"])
                    q1 = float(row["q1"])
                    q3 = float(row["q3"])
                except (ValueError, KeyError) as e:
                    print(f"Error parsing row data: {e}")
                    print(f"Row: {row}")
                    continue

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

        return True

    except Exception as e:
        print(f"Error during import: {e}")
        return False


def run():
    """
    Main function to parse arguments and run the import.
    """

    csv_files = glob.glob("scripts/aggregated_data/*/*.csv")

    for csv_file in csv_files:
        success = import_aggregated_module_data(csv_file)

    if success:
        print("Import process completed successfully.")
    else:
        print("Import process failed.")
        sys.exit(1)
