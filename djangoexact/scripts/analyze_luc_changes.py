#!/usr/bin/env python3
"""
Specialized script to analyze Land Use Change (LUC) CSV files.
Treats LandUseChange as the main module and everything else as filters or field changes.
"""

import csv
import json
import os
import pandas as pd
from typing import Dict, List, Any, Optional


def analyze_luc_changes(csv_file_path: str) -> List[Dict[str, Any]]:
    """
    Analyze LUC CSV file and identify changes between _start and _w columns.

    Args:
        csv_file_path: Path to the LUC CSV file

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
        # Get the basic LUC information (always present)
        region = row.get("region", "")
        climate = row.get("climate", "")
        moisture = row.get("moisture", "")
        soil_type = row.get("soil_type", "")
        total = row.get("total", 0)

        # Get the module type transition (primary change)
        module_type_start = row.get("module_type_start", "")
        module_type_w = row.get("module_type_w", "")

        # Get module-specific fields (all columns except the standard ones and _start/_w pairs)
        standard_fields = {"module", "region", "climate", "moisture", "soil_type", "total", "module_type_start", "module_type_w", "module_type_wo"}
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
                change_type = "field_change"
                if base_name == "module_type":
                    change_type = "module_transition"
                elif base_name in ["module_start_type", "module_w_type"]:
                    change_type = "module_type_change"
                elif base_name.startswith("module_w_"):
                    change_type = "module_field_change"

                row_changes.append({"field": base_name, "from": start_value, "to": w_value, "change_type": change_type})

        # Only add to results if there are changes
        if row_changes:
            record = {
                "module_type": "Land Use Change",
                "region": region,
                "climate": climate,
                "moisture": moisture,
                "soil_type": soil_type,
                "total": total,
                "module_transition": f"{module_type_start} -> {module_type_w}",
                "changes": row_changes,
            }

            # Add module-specific fields
            record.update(module_specific_fields)

            changes_data.append(record)

    return changes_data


def get_luc_file_type_from_filename(file_path: str) -> str:
    """
    Extract LUC file type from filename.

    Args:
        file_path: Path to the CSV file

    Returns:
        LUC file type extracted from filename
    """
    filename = os.path.basename(file_path)
    name_without_ext = os.path.splitext(filename)[0]

    # Convert common filename patterns to LUC types
    luc_mapping = {
        "setaside_settlement": "SetAside to Settlement",
        "setaside_annualcropland": "SetAside to Annual Cropland",
        "setaside_forestmanagement": "SetAside to Forest Management",
        "setaside_grassland": "SetAside to Grassland",
        "setaside_otherland": "SetAside to Other Land",
        "grassland_forestmanagement": "Grassland to Forest Management",
        "forestmanagement_grassland": "Forest Management to Grassland",
    }

    for key, value in luc_mapping.items():
        if key in name_without_ext.lower():
            return value

    # Default: capitalize and replace underscores with spaces
    return name_without_ext.replace("_", " ").title()


def analyze_luc_csv_file(csv_file_path: str, output_file: Optional[str] = None) -> str:
    """
    Analyze a LUC CSV file and generate changes JSON.

    Args:
        csv_file_path: Path to the LUC CSV file
        output_file: Optional output file path (if not specified, will be generated from input)

    Returns:
        Path to the generated output file
    """
    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(f"LUC CSV file not found: {csv_file_path}")

    # Determine LUC file type
    luc_type = get_luc_file_type_from_filename(csv_file_path)

    print(f"Analyzing LUC changes in {csv_file_path}...")
    print(f"LUC type: {luc_type}")

    # Analyze the changes
    changes_data = analyze_luc_changes(csv_file_path)

    print(f"Found {len(changes_data)} rows with changes")

    # Generate output filename if not provided
    if not output_file:
        base_name = os.path.splitext(os.path.basename(csv_file_path))[0]
        output_file = f"{base_name}_luc_changes.json"

    # Save to JSON file
    output_path = os.path.join("minitool", "data", "changes", "luc", output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(changes_data, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {output_path}")

    # Print some statistics
    if changes_data:
        print("\nSample of LUC changes found:")
        for i, item in enumerate(changes_data[:3]):
            print(f"\nRow {i + 1}:")
            print(f"  Region: {item['region']}")
            print(f"  Climate: {item['climate']}")
            print(f"  Moisture: {item['moisture']}")
            print(f"  Soil Type: {item['soil_type']}")
            print(f"  Total: {item['total']}")
            print(f"  Module Transition: {item['module_transition']}")
            print(f"  Changes: {len(item['changes'])}")
            for change in item["changes"]:
                print(f"    {change['field']}: {change['from']} -> {change['to']} ({change['change_type']})")

    return output_path


def run_luc_analysis():
    """Run LUC analysis on all LUC files."""
    try:
        luc_files = [
            "setaside_settlement.csv",
            "setaside_annualcropland.csv",
            "setaside_forestmanagement.csv",
            "setaside_grassland.csv",
            "setaside_otherland.csv",
            "grassland_forestmanagement.csv",
            "forestmanagement_grassland.csv",
        ]

        for luc_file in luc_files:
            file_path = f"scripts/minitool/luc/{luc_file}"
            if os.path.exists(file_path):
                output_path = analyze_luc_csv_file(file_path)
                print(f"Processed {luc_file} -> {output_path}")
            else:
                print(f"File not found: {file_path}")

        print("\nLUC analysis completed successfully!")

    except Exception as e:
        print(f"Error: {e}")


def run():
    run_luc_analysis()
