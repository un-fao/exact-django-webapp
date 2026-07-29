import pandas as pd
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Change:
    field: str
    from_value: str
    to_value: str


@dataclass
class Entry:
    module_type: str
    region: str
    climate: str
    moisture: str
    soil_type: str
    total: float
    changes: List[Change]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_type": self.module_type,
            "region": self.region,
            "climate": self.climate,
            "moisture": self.moisture,
            "soil_type": self.soil_type,
            "total": self.total,
            "changes": [{"field": change.field, "from": change.from_value, "to": change.to_value} for change in self.changes],
        }


def process_annualcropland_csv(filepath: str) -> List[Entry]:
    """Process annualcropland.csv and extract changes"""
    df = pd.read_csv(filepath)
    entries = []

    for _, row in df.iterrows():
        changes = []

        # Check for land use type changes
        if row["land_use_type_start"] != row["land_use_type_w"]:
            changes.append(Change("land_use_type", row["land_use_type_start"], row["land_use_type_w"]))

        # Check for tillage management changes
        if row["tillage_management_type_start"] != row["tillage_management_type_w"]:
            changes.append(Change("tillage_management_type", row["tillage_management_type_start"], row["tillage_management_type_w"]))

        # Check for organic input changes
        if row["organic_input_type_start"] != row["organic_input_type_w"]:
            changes.append(Change("organic_input_type", row["organic_input_type_start"], row["organic_input_type_w"]))

        # Check for residue management changes
        if row["residue_management_type_start"] != row["residue_management_type_w"]:
            changes.append(Change("residue_management_type", row["residue_management_type_start"], row["residue_management_type_w"]))

        if changes:  # Only add entries that have changes
            entry = Entry(module_type=row["module"], region=row["region"], climate=row["climate"], moisture=row["moisture"], soil_type=row["soil_type"], total=row["total"], changes=changes)
            entries.append(entry)

    return entries


def process_livestock_csv(filepath: str) -> List[Entry]:
    """Process livestock.csv and extract changes"""
    df = pd.read_csv(filepath)
    entries = []

    for _, row in df.iterrows():
        changes = []

        # Check for livestock production type changes
        if row["livestock_production_type_start"] != row["livestock_production_type_w"]:
            changes.append(Change("livestock_production_type", row["livestock_production_type_start"], row["livestock_production_type_w"]))

        # Check for heads number changes
        if row["heads_number_start"] != row["heads_number_w"]:
            changes.append(Change("heads_number", str(row["heads_number_start"]), str(row["heads_number_w"])))

        # Check for complementary manure management changes
        if row["complementary_manure_management_type_start"] != row["complementary_manure_management_type_w"]:
            changes.append(Change("complementary_manure_management_type", row["complementary_manure_management_type_start"], row["complementary_manure_management_type_w"]))

        if changes:  # Only add entries that have changes
            entry = Entry(module_type=row["module"], region=row["region"], climate=row["climate"], moisture=row["moisture"], soil_type=row["soil_type"], total=row["total"], changes=changes)
            entries.append(entry)

    return entries


def process_grassland_csv(filepath: str) -> List[Entry]:
    """Process grassland.csv and extract changes"""
    df = pd.read_csv(filepath)
    entries = []

    for _, row in df.iterrows():
        changes = []

        # Check for grassland management type changes
        if row["grassland_management_type_start"] != row["grassland_management_type_w"]:
            changes.append(Change("grassland_management_type", row["grassland_management_type_start"], row["grassland_management_type_w"]))

        # Check for fire usage changes
        if row["is_fire_used_start"] != row["is_fire_used_w"]:
            changes.append(Change("is_fire_used", str(row["is_fire_used_start"]), str(row["is_fire_used_w"])))

        # Check for fire periodicity changes
        if row["fire_periodicity_start"] != row["fire_periodicity_w"]:
            changes.append(Change("fire_periodicity", str(row["fire_periodicity_start"]), str(row["fire_periodicity_w"])))

        # Check for fire impact changes
        if row["fire_impact_start"] != row["fire_impact_w"]:
            changes.append(Change("fire_impact", str(row["fire_impact_start"]), str(row["fire_impact_w"])))

        # Check for yield changes
        if row["yield_start"] != row["yield_w"]:
            changes.append(Change("yield", str(row["yield_start"]), str(row["yield_w"])))

        if changes:  # Only add entries that have changes
            entry = Entry(module_type=row["module"], region=row["region"], climate=row["climate"], moisture=row["moisture"], soil_type=row["soil_type"], total=row["total"], changes=changes)
            entries.append(entry)

    return entries


def process_floodedrice_csv(filepath: str) -> List[Entry]:
    """Process floodedrice.csv and extract changes"""
    df = pd.read_csv(filepath)
    entries = []

    for _, row in df.iterrows():
        changes = []

        # Check for water management before cultivation changes
        if row["water_management_type_before_cultivation_start"] != row["water_management_type_before_cultivation_w"]:
            changes.append(Change("water_management_type_before_cultivation", row["water_management_type_before_cultivation_start"], row["water_management_type_before_cultivation_w"]))

        # Check for water management after cultivation changes
        if row["water_management_type_after_cultivation_start"] != row["water_management_type_after_cultivation_w"]:
            changes.append(Change("water_management_type_after_cultivation", row["water_management_type_after_cultivation_start"], row["water_management_type_after_cultivation_w"]))

        # Check for organic amendment changes
        if row["organic_amendment_type_start"] != row["organic_amendment_type_w"]:
            changes.append(Change("organic_amendment_type", row["organic_amendment_type_start"], row["organic_amendment_type_w"]))

        if changes:  # Only add entries that have changes
            entry = Entry(module_type=row["module"], region=row["region"], climate=row["climate"], moisture=row["moisture"], soil_type=row["soil_type"], total=row["total"], changes=changes)
            entries.append(entry)

    return entries


def run():
    """Process all CSV files and create changes.json"""
    minitool_dir = os.path.join(os.path.dirname(__file__), "minitool")
    all_entries = []

    # Process each module type
    module_processors = {
        # "annualcropland.csv": process_annualcropland_csv,
        "livestock.csv": process_livestock_csv,
        # "grassland.csv": process_grassland_csv,
        # "floodedrice.csv": process_floodedrice_csv,
    }

    for filename, processor in module_processors.items():
        filepath = os.path.join(minitool_dir, filename)
        if os.path.exists(filepath):
            print(f"Processing {filename}...")
            entries = processor(filepath)
            all_entries.extend(entries)
            print(f"Found {len(entries)} entries with changes in {filename}")
        else:
            print(f"File {filename} not found, skipping...")

    # Convert entries to dictionaries
    changes_data = [entry.to_dict() for entry in all_entries]

    # Save to changes.json
    output_file = os.path.join(minitool_dir, "changes.json")
    with open(output_file, "w") as f:
        json.dump(changes_data, f, indent=2)

    print(f"Created changes.json with {len(changes_data)} entries")


if __name__ == "__main__":
    run()
