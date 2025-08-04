#!/usr/bin/env python3
"""
Script to aggregate CSV data by environmental factors:
region, climate, moisture, and soil_type combined.
Creates a CSV with multi-dimensional aggregation and summed totals.

Accepts any CSV file with the structure: module_type,climate,moisture,soil_type,region,total
(or module instead of module_type)

Usage:
    python aggregate_by_environmental_factors.py <input_csv_file> [output_directory]

Uses only standard library modules (csv, pathlib).
"""

import csv
import argparse
from pathlib import Path
from collections import defaultdict


def aggregate_by_environmental_factors(data, headers):
    """
    Aggregate data by combining region, climate, moisture, and soil_type.
    Returns both sums and statistical measures for each combination.

    Args:
        data: List of CSV rows
        headers: List of column headers

    Returns:
        dict: Aggregated statistics by environmental factor combinations
    """
    # Find the column indices for the environmental factors
    module_idx = None
    region_idx = None
    climate_idx = None
    moisture_idx = None
    soil_type_idx = None
    total_idx = None

    for i, header in enumerate(headers):
        header_lower = header.lower().strip()
        if header_lower in ["module", "module_type"]:
            module_idx = i
        elif header_lower == "region":
            region_idx = i
        elif header_lower == "climate":
            climate_idx = i
        elif header_lower == "moisture":
            moisture_idx = i
        elif header_lower == "soil_type":
            soil_type_idx = i
        elif header_lower == "total":
            total_idx = i

    # Check if all required columns were found
    missing = []
    if module_idx is None:
        missing.append("module/module_type")
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

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Use defaultdict to store all values for each combination
    aggregated_values = defaultdict(list)

    # Collect all values for each unique combination of environmental factors
    processed_rows = 0
    skipped_rows = 0

    for row in data:
        if len(row) > max(module_idx, region_idx, climate_idx, moisture_idx, soil_type_idx, total_idx):
            try:
                # Create a key combining all environmental factors
                module = row[module_idx].strip() if row[module_idx] else ""
                region = row[region_idx].strip() if row[region_idx] else ""
                climate = row[climate_idx].strip() if row[climate_idx] else ""
                moisture = row[moisture_idx].strip() if row[moisture_idx] else ""
                soil_type = row[soil_type_idx].strip() if row[soil_type_idx] else ""

                # Skip rows with empty key values
                if not all([module, region, climate, moisture, soil_type]):
                    skipped_rows += 1
                    continue

                # Create a tuple key for the combination
                key = (module, region, climate, moisture, soil_type)

                total = float(row[total_idx])
                aggregated_values[key].append(total)
                processed_rows += 1

            except (ValueError, IndexError):
                # Skip rows with invalid total values or missing data
                skipped_rows += 1
                continue
        else:
            skipped_rows += 1

    print(f"  - Processed {processed_rows} valid rows, skipped {skipped_rows} invalid rows")

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

    return aggregated_stats, headers[module_idx]


def main():
    """
    Main function to parse arguments and run the aggregation.
    """
    parser = argparse.ArgumentParser(
        description="Aggregate CSV data by environmental factors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python aggregate_by_environmental_factors.py minitool/livestock.csv
    python aggregate_by_environmental_factors.py minitool/grassland.csv aggregated_data/custom/
    python aggregate_by_environmental_factors.py /path/to/data.csv /path/to/output/

CSV Format:
    The CSV file must contain the following columns (case-insensitive):
    - module or module_type: The module type identifier
    - region: Geographic region
    - climate: Climate type
    - moisture: Moisture conditions
    - soil_type: Soil type
    - total: The value to aggregate

Output:
    Creates a CSV file with aggregated statistics including:
    count, sum, mean, median, min, max, q1, q3 for each unique combination
    of environmental factors.
        """,
    )
    parser.add_argument("input_csv", help="Path to the input CSV file to aggregate")
    parser.add_argument("output_dir", nargs="?", help="Output directory (optional, defaults to aggregated_data/[input_filename]/)")
    parser.add_argument("--output-filename", default="aggregated_by_environmental_factors.csv", help="Output filename (default: aggregated_by_environmental_factors.csv)")

    args = parser.parse_args()

    # Set up paths
    input_file = Path(args.input_csv)
    if not input_file.exists():
        print(f"Error: Input file not found at {input_file}")
        return

    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        # Default: create output directory based on input filename
        script_dir = Path(__file__).parent
        input_stem = input_file.stem  # filename without extension
        output_dir = script_dir / "aggregated_data" / input_stem

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
        print(f"Headers: {headers}")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    print("\nAggregating by environmental factors (region, climate, moisture, soil_type)...")

    try:
        # Aggregate data by environmental factors
        aggregated_data, module_column_name = aggregate_by_environmental_factors(data, headers)

        # Create output filename
        output_path = output_dir / args.output_filename

        # Convert to list of tuples and sort by sum in descending order
        sorted_data = sorted(aggregated_data.items(), key=lambda x: x[1]["sum"], reverse=True)

        # Save to CSV
        with open(output_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            # Use the original column name (module or module_type)
            header_row = [module_column_name, "region", "climate", "moisture", "soil_type", "count", "sum", "mean", "median", "min", "max", "q1", "q3"]
            writer.writerow(header_row)

            for (module, region, climate, moisture, soil_type), stats in sorted_data:
                writer.writerow([module, region, climate, moisture, soil_type, stats["count"], stats["sum"], stats["mean"], stats["median"], stats["min"], stats["max"], stats["q1"], stats["q3"]])

        print(f"  - Created {args.output_filename} with {len(sorted_data)} unique combinations")

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
        print("\n  - Statistics:")
        print(f"    - Number of unique {module_column_name}s: {len(set(module for (module, _, _, _, _), _ in sorted_data))}")
        print(f"    - Number of unique regions: {len(set(region for (_, region, _, _, _), _ in sorted_data))}")
        print(f"    - Number of unique climates: {len(set(climate for (_, _, climate, _, _), _ in sorted_data))}")
        print(f"    - Number of unique moisture levels: {len(set(moisture for (_, _, _, moisture, _), _ in sorted_data))}")
        print(f"    - Number of unique soil types: {len(set(soil_type for (_, _, _, _, soil_type), _ in sorted_data))}")

        # Show overall statistics across all combinations
        all_means = [stats["mean"] for _, stats in sorted_data]
        all_medians = [stats["median"] for _, stats in sorted_data]
        all_mins = [stats["min"] for _, stats in sorted_data]
        all_maxs = [stats["max"] for _, stats in sorted_data]

        print("\n  - Overall statistics across all combinations:")
        print(f"    - Mean of means: {sum(all_means) / len(all_means):.2f}")
        print(f"    - Mean of medians: {sum(all_medians) / len(all_medians):.2f}")
        print(f"    - Global min: {min(all_mins):.2f}")
        print(f"    - Global max: {max(all_maxs):.2f}")

    except Exception as e:
        print(f"  - Error processing environmental factors: {e}")
        return

    print(f"\nAggregation completed. Output file saved at: {output_path}")


if __name__ == "__main__":
    main()
