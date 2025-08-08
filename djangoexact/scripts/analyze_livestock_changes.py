#!/usr/bin/env python3
"""
Script to analyze livestock.csv and identify changes between _start and _w columns.
Generates a changes.json format similar to the existing one.
"""

import csv
import json
import os
import pandas as pd
from typing import Dict, List, Any


def analyze_livestock_changes(csv_file_path: str) -> List[Dict[str, Any]]:
    """
    Analyze livestock.csv file and identify changes between _start and _w columns.

    Args:
        csv_file_path: Path to the livestock.csv file

    Returns:
        List of dictionaries containing change information
    """
    changes_data = []

    # Read the CSV file
    df = pd.read_csv(csv_file_path)

    # Get all column names
    columns = df.columns.tolist()

    # Find columns with _start and _w suffixes
    start_columns = [col for col in columns if col.endswith("_start")]
    w_columns = [col for col in columns if col.endswith("_w")]

    # Create mapping between start and w columns
    column_pairs = []
    for start_col in start_columns:
        base_name = start_col.replace("_start", "")
        w_col = f"{base_name}_w"
        if w_col in w_columns:
            column_pairs.append((start_col, w_col, base_name))

    print(f"Found {len(column_pairs)} column pairs to analyze:")
    for start_col, w_col, base_name in column_pairs:
        print(f"  {start_col} -> {w_col} (base: {base_name})")

    # Process each row
    for index, row in df.iterrows():
        # Get the basic information
        module_type = row.get("module_type", "Livestock")
        region = row.get("region", "")
        climate = row.get("climate", "")
        moisture = row.get("moisture", "")
        soil_type = row.get("soil_type", "")
        total = row.get("total", 0)
        livestock_category_type = row.get("livestock_category_type", "")

        # Track changes for this row
        row_changes = []

        # Check each column pair for changes
        for start_col, w_col, base_name in column_pairs:
            start_value = row.get(start_col)
            w_value = row.get(w_col)

            # Handle NaN values
            if pd.isna(start_value):
                start_value = None
            if pd.isna(w_value):
                w_value = None

            # Check if there's a change
            if start_value != w_value:
                row_changes.append({"field": base_name, "from": start_value, "to": w_value})

        # Only add to results if there are changes
        if row_changes:
            changes_data.append(
                {
                    "module_type": module_type,
                    "region": region,
                    "climate": climate,
                    "moisture": moisture,
                    "soil_type": soil_type,
                    "total": total,
                    "livestock_category_type": livestock_category_type,
                    "changes": row_changes,
                }
            )

    return changes_data


def run():
    """Main function to run the analysis."""
    csv_file_path = os.path.join(os.path.dirname(__file__), "minitool", "livestock.csv")

    print(f"Analyzing changes in {csv_file_path}...")

    # Analyze the changes
    changes_data = analyze_livestock_changes(csv_file_path)

    print(f"Found {len(changes_data)} rows with changes")

    # Save to JSON file
    output_file = "livestock_changes.json"
    with open(os.path.join(os.path.dirname(__file__), "minitool", output_file), "w", encoding="utf-8") as f:
        json.dump(changes_data, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {output_file}")

    # Print some statistics
    if changes_data:
        print("\nSample of changes found:")
        for i, item in enumerate(changes_data[:3]):
            print(f"\nRow {i + 1}:")
            print(f"  Region: {item['region']}")
            print(f"  Climate: {item['climate']}")
            print(f"  Moisture: {item['moisture']}")
            print(f"  Soil Type: {item['soil_type']}")
            print(f"  Total: {item['total']}")
            print(f"  Livestock Category: {item['livestock_category_type']}")
            print(f"  Changes: {len(item['changes'])}")
            for change in item["changes"]:
                print(f"    {change['field']}: {change['from']} -> {change['to']}")
