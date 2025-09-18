from minitool.models import Entry, StatisticsModuleTotal
import json
import os
import django
from django.conf import settings


def import_changes_into_entries():
    # Open changes.json file in this directory
    with open(os.path.join(os.path.dirname(__file__), "minitool", "changes.json"), "r") as f:
        changes = f.read()

    # Parse the JSON data
    changes = json.loads(changes)
    entries = []

    print(f"Found {len(changes)} changes in the JSON file.")

    for change in changes:
        entry = Entry(
            module_type=change["module_type"],
            region=change["region"],
            climate=change["climate"],
            moisture=change["moisture"],
            soil_type=change["soil_type"],
            total=change["total"],
            changes=change["changes"],
        )

        entries.append(entry)

    # Save the entries to the database
    Entry.objects.db_manager("minitool").bulk_create(entries)
    print(f"Imported {len(entries)} entries into the database.")


def import_aggregated_practices_csv():
    # Open aggregated_practices.csv file in this directory
    import csv
    
    entries = []
    BATCH_SIZE = 1000
    batch_count = 0

    with open(os.path.join(os.path.dirname(__file__), "minitool", "aggregated_practices.csv"), "r") as f:
        reader = csv.reader(f)
        header = next(reader)
        print(f"CSV columns: {header}")

        for change in reader:
            try:
                # Create base entry with required fields
                entry_data = {
                    "module_type": change[0],
                    "field": change[1],
                    "from_value": str(change[2]),
                    "to_value": str(change[3]),
                    "mean": float(change[4]) if change[4] else 0,
                    "median": float(change[5]) if change[5] else 0,
                    "min": float(change[6]) if change[6] else 0,
                    "max": float(change[7]) if change[7] else 0,
                    "q1": float(change[8]) if change[8] else 0,
                    "q3": float(change[9]) if change[9] else 0,
                }

                # Add optional aggregation fields if they exist in the CSV
                if "region" in header:
                    region_index = header.index("region")
                    if region_index < len(change):
                        entry_data["region"] = change[region_index] if change[region_index] else None

                if "climate" in header:
                    climate_index = header.index("climate")
                    if climate_index < len(change):
                        entry_data["climate"] = change[climate_index] if change[climate_index] else None

                if "moisture" in header:
                    moisture_index = header.index("moisture")
                    if moisture_index < len(change):
                        entry_data["moisture"] = change[moisture_index] if change[moisture_index] else None

                if "soil_type" in header:
                    soil_type_index = header.index("soil_type")
                    if soil_type_index < len(change):
                        entry_data["soil_type"] = change[soil_type_index] if change[soil_type_index] else None

                entry = StatisticsModuleTotal(**entry_data)
                entries.append(entry)

                # Process batch when it reaches the limit
                if len(entries) >= BATCH_SIZE:
                    StatisticsModuleTotal.objects.db_manager("minitool").bulk_create(entries, ignore_conflicts=True)
                    batch_count += 1
                    print(f"Processed batch {batch_count} with {len(entries)} entries...")
                    entries.clear()

            except (ValueError, IndexError) as e:
                print(f"Error parsing entry: {change}. Error: {e}")
                continue

    # Save remaining entries to the database
    if entries:
        StatisticsModuleTotal.objects.db_manager("minitool").bulk_create(entries, ignore_conflicts=True)
        batch_count += 1
        print(f"Processed final batch {batch_count} with {len(entries)} entries...")
    
    print("Import completed successfully.")


def run():
    # import_changes_into_entries()
    import_aggregated_practices_csv()
    print("Changes imported successfully.")
