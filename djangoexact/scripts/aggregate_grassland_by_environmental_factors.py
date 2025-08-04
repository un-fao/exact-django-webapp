#!/usr/bin/env python3
"""
Script to aggregate grassland.csv data by environmental factors:
region, climate, moisture, and soil_type combined.
Creates a CSV with multi-dimensional aggregation and summed totals.
Uses only standard library modules (csv, pathlib).
"""

import csv
import os
from pathlib import Path
from collections import defaultdict
import statistics


def aggregate_by_environmental_factors(data, headers):
    """
    Aggregate data by combining region, climate, moisture, and soil_type.
    Returns both sums and statistical measures for each combination.
    """
    # Find the column indices for the environmental factors
    module_idx = None
    region_idx = None
    climate_idx = None
    moisture_idx = None
    soil_type_idx = None
    total_idx = None

    for i, header in enumerate(headers):
        if header == "module":
            module_idx = i
        elif header == "region":
            region_idx = i
        elif header == "climate":
            climate_idx = i
        elif header == "moisture":
            moisture_idx = i
        elif header == "soil_type":
            soil_type_idx = i
        elif header == "total":
            total_idx = i

    # Check if all required columns were found
    if any(idx is None for idx in [module_idx, region_idx, climate_idx, moisture_idx, soil_type_idx, total_idx]):
        missing = []
        if module_idx is None:
            missing.append("module")
        if region_idx is None:
            missing.append("region")
        if climate_idx is None:
            missing.append("climate")
        if moisture_idx is None:
            missing.append("moisture")
        if soil_type_idx is None:
            missing.append("soil_type")
        if total_idx is None:
            missing.append("total")
        raise ValueError(f"Missing required columns: {missing}")

    # Use defaultdict to store all values for each combination
    aggregated_values = defaultdict(list)

    # Collect all values for each unique combination of environmental factors
    for row in data:
        if len(row) > max(module_idx, region_idx, climate_idx, moisture_idx, soil_type_idx, total_idx):
            try:
                # Create a key combining all environmental factors
                module = row[module_idx]
                region = row[region_idx]
                climate = row[climate_idx]
                moisture = row[moisture_idx]
                soil_type = row[soil_type_idx]

                # Create a tuple key for the combination
                key = (module, region, climate, moisture, soil_type)

                total = float(row[total_idx])
                aggregated_values[key].append(total)
            except (ValueError, IndexError):
                # Skip rows with invalid total values or missing data
                continue

    # Calculate statistics for each combination
    aggregated_stats = {}
    for key, values in aggregated_values.items():
        if values:
            values.sort()  # Sort for median and quartile calculations
            n = len(values)

            # Calculate statistics
            total_sum = sum(values)
            mean_val = total_sum / n
            min_val = values[0]
            max_val = values[-1]

            # Calculate median
            if n % 2 == 0:
                median_val = (values[n // 2 - 1] + values[n // 2]) / 2
            else:
                median_val = values[n // 2]

            # Calculate Q1 and Q3
            q1_idx = n // 4
            q3_idx = 3 * n // 4

            q1_val = values[q1_idx]
            q3_val = values[q3_idx]

            aggregated_stats[key] = {"count": n, "sum": total_sum, "mean": mean_val, "median": median_val, "min": min_val, "max": max_val, "q1": q1_val, "q3": q3_val}

    return aggregated_stats


def run():
    # Get the script directory
    script_dir = Path(__file__).parent
    input_file = script_dir / "minitool" / "grassland.csv"
    output_dir = script_dir / "aggregated_data" / "grassland"

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

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

    print("\nAggregating by environmental factors (region, climate, moisture, soil_type)...")

    try:
        # Aggregate data by environmental factors
        aggregated_data = aggregate_by_environmental_factors(data, headers)

        # Create output filename
        output_filename = "aggregated_by_environmental_factors.csv"
        output_path = output_dir / output_filename

        # Convert to list of tuples and sort by sum in descending order
        sorted_data = sorted(aggregated_data.items(), key=lambda x: x[1]["sum"], reverse=True)

        # Save to CSV
        with open(output_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["module", "region", "climate", "moisture", "soil_type", "count", "sum", "mean", "median", "min", "max", "q1", "q3"])  # Write header
            for (module, region, climate, moisture, soil_type), stats in sorted_data:
                writer.writerow([module, region, climate, moisture, soil_type, stats["count"], stats["sum"], stats["mean"], stats["median"], stats["min"], stats["max"], stats["q1"], stats["q3"]])

        print(f"  - Created {output_filename} with {len(sorted_data)} unique combinations")

        # Calculate total sum
        total_sum = sum(stats["sum"] for _, stats in sorted_data)
        print(f"  - Total sum: {total_sum:.2f}")

        # Show top 10 combinations
        print("  - Top 10 environmental factor combinations:")
        for i, ((module, region, climate, moisture, soil_type), stats) in enumerate(sorted_data[:10], 1):
            print(f"    {i}. {module} | {region} | {climate} | {moisture} | {soil_type}")
            print(f"       Sum: {stats['sum']:.2f}, Mean: {stats['mean']:.2f}, Median: {stats['median']:.2f}")
            print(f"       Min: {stats['min']:.2f}, Max: {stats['max']:.2f}, Q1: {stats['q1']:.2f}, Q3: {stats['q3']:.2f}")

        # Show some statistics
        print(f"\n  - Statistics:")
        print(f"    - Number of unique modules: {len(set(module for (module, _, _, _, _), _ in sorted_data))}")
        print(f"    - Number of unique regions: {len(set(region for (_, region, _, _, _), _ in sorted_data))}")
        print(f"    - Number of unique climates: {len(set(climate for (_, _, climate, _, _), _ in sorted_data))}")
        print(f"    - Number of unique moisture levels: {len(set(moisture for (_, _, _, moisture, _), _ in sorted_data))}")
        print(f"    - Number of unique soil types: {len(set(soil_type for (_, _, _, _, soil_type), _ in sorted_data))}")

        # Show overall statistics across all combinations
        all_means = [stats["mean"] for _, stats in sorted_data]
        all_medians = [stats["median"] for _, stats in sorted_data]
        all_mins = [stats["min"] for _, stats in sorted_data]
        all_maxs = [stats["max"] for _, stats in sorted_data]

        print(f"\n  - Overall statistics across all combinations:")
        print(f"    - Mean of means: {sum(all_means) / len(all_means):.2f}")
        print(f"    - Mean of medians: {sum(all_medians) / len(all_medians):.2f}")
        print(f"    - Global min: {min(all_mins):.2f}")
        print(f"    - Global max: {max(all_maxs):.2f}")

    except Exception as e:
        print(f"  - Error processing environmental factors: {e}")

    print(f"\nAggregation completed. Output file saved in: {output_dir}")


if __name__ == "__main__":
    run()
