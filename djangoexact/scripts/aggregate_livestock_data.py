#!/usr/bin/env python3
"""
Script to aggregate livestock.csv data by each categorical column.
Creates separate CSV files for each column aggregation with summed totals.
Uses only standard library modules (csv, pathlib).
"""

import csv
import os
from pathlib import Path
from collections import defaultdict


def identify_categorical_columns(headers):
    """
    Identify categorical columns (excluding numerical columns and columns ending with '_wo').
    """
    categorical_columns = []

    for i, col in enumerate(headers):
        # Skip the 'total' column as it's numerical
        if col == "total":
            continue

        # Skip columns ending with '_wo'
        if col.endswith("_wo"):
            continue

        # Skip columns that are likely numerical (based on name patterns)
        numerical_patterns = ["heads_number", "start", "w"]
        if any(pattern in col for pattern in numerical_patterns):
            continue

        categorical_columns.append(i)

    return categorical_columns


def aggregate_by_column(data, column_index, column_name):
    """
    Aggregate data by a specific column and sum the 'total' values.
    """
    # Use defaultdict to automatically initialize sums to 0
    aggregated = defaultdict(float)

    # Sum totals for each unique value in the column
    for row in data:
        if len(row) > column_index:
            value = row[column_index]
            try:
                total = float(row[5])  # 'total' is at index 5
                aggregated[value] += total
            except (ValueError, IndexError):
                # Skip rows with invalid total values
                continue

    # Convert to list of tuples and sort by total in descending order
    sorted_data = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)

    return sorted_data


def run():
    # Get the script directory
    script_dir = Path(__file__).parent
    input_file = script_dir / "minitool" / "livestock.csv"
    output_dir = script_dir / "aggregated_data"

    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)

    print(f"Reading data from {input_file}...")

    # Read the CSV file
    try:
        with open(input_file, "r", encoding="utf-8") as file:
            reader = csv.reader(file)
            headers = next(reader)  # Get column headers
            data = list(reader)  # Get all data rows

        print(f"Successfully loaded {len(data)} rows and {len(headers)} columns")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    # Identify categorical columns
    categorical_column_indices = identify_categorical_columns(headers)
    categorical_columns = [headers[i] for i in categorical_column_indices]
    print(f"Found {len(categorical_columns)} categorical columns: {categorical_columns}")

    # Process each categorical column
    for i, column_name in zip(categorical_column_indices, categorical_columns):
        print(f"\nProcessing column: {column_name}")

        try:
            # Aggregate data by this column
            aggregated_data = aggregate_by_column(data, i, column_name)

            # Create output filename
            output_filename = f"aggregated_by_{column_name}.csv"
            output_path = output_dir / output_filename

            # Save to CSV
            with open(output_path, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow([column_name, "total"])  # Write header
                writer.writerows(aggregated_data)

            print(f"  - Created {output_filename} with {len(aggregated_data)} unique values")

            # Calculate total sum
            total_sum = sum(total for _, total in aggregated_data)
            print(f"  - Total sum: {total_sum:.2f}")

            # Show top 5 values
            print("  - Top 5 values:")
            for value, total in aggregated_data[:5]:
                print(f"    {value}: {total:.2f}")

        except Exception as e:
            print(f"  - Error processing column {column_name}: {e}")

    print(f"\nAll aggregations completed. Output files saved in: {output_dir}")
