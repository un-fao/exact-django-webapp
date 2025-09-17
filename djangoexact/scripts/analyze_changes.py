#!/usr/bin/env python3
"""
Generalized script to analyze CSV files and identify changes between _start and _w columns.
Generates a changes.json format similar to the existing one.
Works with any module type that has the standard structure.
"""

import csv
import json
import os
import pandas as pd
from typing import Dict, List, Any, Optional


def analyze_changes(csv_file_path: str, module_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Analyze CSV file and identify changes between _start and _w columns.

    Args:
        csv_file_path: Path to the CSV file
        module_type: Optional module type override (if not specified, will be read from CSV)

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
        # Get the basic information (always present)
        row_module_type = module_type or row.get("module_type", "Unknown")
        region = row.get("region", "")
        climate = row.get("climate", "")
        moisture = row.get("moisture", "")
        soil_type = row.get("soil_type", "")
        total = row.get("total", 0)

        # Get module-specific fields (all columns except the standard ones and _start/_w pairs)
        standard_fields = {"module_type", "region", "climate", "moisture", "soil_type", "total"}
        change_fields = set()
        for start_col, w_col, base_name in column_pairs:
            change_fields.add(base_name)

        # Find additional module-specific fields
        module_specific_fields = {}
        for col in columns:
            if col not in standard_fields and not col.endswith("_start") and not col.endswith("_w") and not col.endswith("_wo"):
                module_specific_fields[col] = row.get(col, "")

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

        module_mapping = {
            "livestock": "Livestock",
            "annualcropland": "Annual Cropland",
            "grassland": "Grassland",
            "floodedrice": "Flooded Rice",
            "perennialcropland": "Perennial Cropland",
            "forestmanagement": "Forest Management",
            "smallfishery": "Small Fishery",
            "largefishery": "Large Fishery",
            "input": "Input",
        }

        # Only add to results if there are changes
        if row_changes:
            record = {
                "module_type": module_mapping.get(row_module_type.lower(), row_module_type),
                "region": region,
                "climate": climate,
                "moisture": moisture,
                "soil_type": soil_type,
                "total": total,
                "changes": row_changes,
            }

            # Add module-specific fields
            record.update(module_specific_fields)

            changes_data.append(record)

    return changes_data


def get_module_type_from_filename(file_path: str) -> str:
    """
    Extract module type from filename.

    Args:
        file_path: Path to the CSV file

    Returns:
        Module type extracted from filename
    """
    filename = os.path.basename(file_path)
    name_without_ext = os.path.splitext(filename)[0]

    # Convert common filename patterns to module types
    module_mapping = {
        "livestock": "Livestock",
        "annualcropland": "Annual Cropland",
        "grassland": "Grassland",
        "floodedrice": "Flooded Rice",
        "perennialcropland": "Perennial Cropland",
        "forestmanagement": "Forest Management",
        "smallfishery": "Small Fishery",
        "largefishery": "Large Fishery",
        "input": "Input",
    }

    for key, value in module_mapping.items():
        if key in name_without_ext.lower():
            return value

    # Default: capitalize and replace underscores with spaces
    return name_without_ext.replace("_", " ").title()


def analyze_csv_file(csv_file_path: str, output_file: Optional[str] = None, module_type: Optional[str] = None) -> str:
    """
    Analyze a CSV file and generate changes JSON.

    Args:
        csv_file_path: Path to the CSV file
        output_file: Optional output file path (if not specified, will be generated from input)
        module_type: Optional module type override

    Returns:
        Path to the generated output file
    """
    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

    # Determine module type if not provided
    if not module_type:
        module_type = get_module_type_from_filename(csv_file_path)

    print(f"Analyzing changes in {csv_file_path}...")
    print(f"Module type: {module_type}")

    # Analyze the changes
    changes_data = analyze_changes(csv_file_path, module_type)

    print(f"Found {len(changes_data)} rows with changes")

    # Generate output filename if not provided
    if not output_file:
        base_name = os.path.splitext(os.path.basename(csv_file_path))[0]
        output_file = f"{base_name}_changes.json"

    # Save to JSON file
    output_path = os.path.join("minitool", "data", "changes", output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(changes_data, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {output_path}")

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
            print(f"  Changes: {len(item['changes'])}")
            for change in item["changes"]:
                print(f"    {change['field']}: {change['from']} -> {change['to']}")

    return output_path


def run():
    try:
        # "annualcropland", "grassland", "perennialcropland", "floodedrice", "livestock",
        for module_type in ["smallfishery"]:
            output_path = analyze_csv_file(f"scripts/minitool/{module_type}.csv", f"{module_type}_changes.json", module_type)
        print(f"\nAnalysis completed successfully!")
        print(f"Output file: {output_path}")
    except Exception as e:
        print(f"Error: {e}")
