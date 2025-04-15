from minitool.models import Entry
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


def run():
    import_changes_into_entries()
    print("Changes imported successfully.")
