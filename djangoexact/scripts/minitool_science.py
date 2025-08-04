from minitool.models import Entry
import json
import os
import django
from django.conf import settings
import pandas as pd
import numpy as np
from django.db.models import Avg
from django.db.models import F, Sum


def compute_practice_differences(aggregation_level=None, additional_filters=None):
    if aggregation_level is None:
        raise ValueError("Aggregation level must be provided.")

    # Base query for practice-based aggregation
    entries = Entry.objects.filter(changes__0__field=aggregation_level)

    # Apply additional filters if provided
    if additional_filters:
        for field, value in additional_filters.items():
            if value is not None:
                entries = entries.filter(**{field: value})

    # Group by practice changes and additional dimensions
    group_fields = ["changes__0__from", "changes__0__to"]
    if additional_filters:
        group_fields.extend(additional_filters.keys())

    aggregated_data = entries.values(*group_fields).annotate(total=Sum("total")).order_by(*group_fields)

    print(f"Found {len(aggregated_data)} entries with {aggregation_level} and filters: {additional_filters}.")

    for entry in aggregated_data:
        # Build filter conditions for the current group
        filter_conditions = {"changes__0__field": aggregation_level, "changes__0__from": entry["changes__0__from"], "changes__0__to": entry["changes__0__to"]}
        if additional_filters:
            for field, value in additional_filters.items():
                if value is not None:
                    filter_conditions[field] = value

        # Filter entries matching the current group
        group_entries = Entry.objects.filter(**filter_conditions).values_list("total", flat=True)
        module_type = Entry.objects.filter(**filter_conditions).values_list("module_type", flat=True)
        if module_type:
            entry["module_type"] = module_type[0]

        carbon_balances = sorted(group_entries)
        if carbon_balances:
            entry["mean"] = round(float(np.mean(carbon_balances)), 4)
            entry["median"] = round(float(np.median(carbon_balances)), 4)
            entry["min"] = round(float(np.min(carbon_balances)), 4)
            entry["max"] = round(float(np.max(carbon_balances)), 4)
            entry["q1"] = round(float(np.percentile(carbon_balances, 25)), 4)
            entry["q3"] = round(float(np.percentile(carbon_balances, 75)), 4)
        else:
            entry["mean"] = entry["median"] = entry["min"] = entry["max"] = entry["q1"] = entry["q3"] = None

    print("Aggregated data:")
    for entry in aggregated_data:
        print(
            f"{aggregation_level}: {entry['changes__0__from']} -> {entry['changes__0__to']}, Mean: {entry['mean']}, Median: {entry['median']}, Min: {entry['min']}, Max: {entry['max']}, Q1: {entry['q1']}, Q3: {entry['q3']}"
        )

    # Build dataframe with aggregated data
    df = pd.DataFrame(aggregated_data)

    # Add columns at the beginning of the DataFrame
    mt = df["module_type"] if "module_type" in df else ""
    if type(mt) is not str:
        df.drop(columns=["module_type"], inplace=True)
    df.insert(0, "module_type", mt)
    df.insert(1, "field", aggregation_level)
    df.insert(2, "from", df["changes__0__from"])
    df.insert(3, "to", df["changes__0__to"])

    # Add additional dimension columns
    col_index = 4
    if additional_filters:
        for field in additional_filters.keys():
            if field in df.columns:
                df.insert(col_index, field, df[field])
                col_index += 1

    # Drop the original grouped columns
    columns_to_drop = ["changes__0__from", "changes__0__to", "total"]
    df.drop(columns=[col for col in columns_to_drop if col in df.columns], inplace=True)

    return df


def compute_dimension_aggregations():
    """Compute aggregations for different dimensions (region, climate, moisture, soil_type, module_type)"""

    # Get all unique values for each dimension
    regions = Entry.objects.values_list("region", flat=True).distinct()
    climates = Entry.objects.values_list("climate", flat=True).distinct()
    moistures = Entry.objects.values_list("moisture", flat=True).distinct()
    soil_types = Entry.objects.values_list("soil_type", flat=True).distinct()
    module_types = Entry.objects.values_list("module_type", flat=True).distinct()

    print(f"Found {len(regions)} regions, {len(climates)} climates, {len(moistures)} moistures, {len(soil_types)} soil types, {len(module_types)} module types")

    all_dfs = []

    # Get all practice fields
    practices = Entry.objects.values_list("changes__0__field", flat=True).distinct()

    # Aggregate by region
    for region in regions:
        for practice in practices:
            print(f"Processing region: {region}, practice: {practice}")
            df = compute_practice_differences(practice, {"region": region})
            all_dfs.append(df)

    # Aggregate by climate
    for climate in climates:
        for practice in practices:
            print(f"Processing climate: {climate}, practice: {practice}")
            df = compute_practice_differences(practice, {"climate": climate})
            all_dfs.append(df)

    # Aggregate by moisture
    for moisture in moistures:
        for practice in practices:
            print(f"Processing moisture: {moisture}, practice: {practice}")
            df = compute_practice_differences(practice, {"moisture": moisture})
            all_dfs.append(df)

    # Aggregate by soil_type
    for soil_type in soil_types:
        for practice in practices:
            print(f"Processing soil_type: {soil_type}, practice: {practice}")
            df = compute_practice_differences(practice, {"soil_type": soil_type})
            all_dfs.append(df)

    # Aggregate by module_type
    for module_type in module_types:
        for practice in practices:
            print(f"Processing module_type: {module_type}, practice: {practice}")
            df = compute_practice_differences(practice, {"module_type": module_type})
            all_dfs.append(df)

    return all_dfs


def run():
    # Get all changes_0 fields for practice-based aggregation
    practices = Entry.objects.values_list("changes__0__field", flat=True).distinct()
    print(f"Found {len(practices)} unique practices.")

    dfs = []

    # Process practice-based aggregations
    for practice in practices:
        print(f"Processing practice: {practice}")
        df = compute_practice_differences(practice)
        dfs.append(df)

    # Process dimension-based aggregations
    print("Processing dimension-based aggregations...")
    dimension_dfs = compute_dimension_aggregations()
    dfs.extend(dimension_dfs)

    # Concatenate all dataframes
    all_data = pd.concat(dfs, ignore_index=True)

    # Save to CSV
    output_path = os.path.join(os.path.dirname(__file__), "minitool")

    if not os.path.exists(output_path):
        os.makedirs(output_path)
    output_file = os.path.join(output_path, "aggregated_practices.csv")
    all_data.to_csv(output_file, index=False)
    print(f"Aggregated data saved to {output_file}")
