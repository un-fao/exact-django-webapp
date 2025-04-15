from minitool.models import Entry
import json
import os
import django
from django.conf import settings
import pandas as pd
import numpy as np
from django.db.models import Avg
from django.db.models import F, Sum


def compute_practice_differences(aggregation_level=None):
    if aggregation_level is None:
        raise ValueError("Aggregation level must be provided.")

    entries = Entry.objects.filter(changes__0__field=aggregation_level)
    aggregated_data = entries.values("changes__0__from", "changes__0__to").annotate(total=Sum("total")).order_by("changes__0__from", "changes__0__to")

    print(f"Found {len(aggregated_data)} entries with {aggregation_level}.")

    for entry in aggregated_data:
        # Filter entries matching the current group
        group_entries = Entry.objects.filter(changes__0__field=aggregation_level, changes__0__from=entry["changes__0__from"], changes__0__to=entry["changes__0__to"]).values_list("total", flat=True)

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
        print(f"{aggregation_level}: {entry['changes__0__from']} -> {entry['changes__0__to']}, Mean: {entry['mean']}, Median: {entry['median']}, Min: {entry['min']}, Max: {entry['max']}, Q1: {entry['q1']}, Q3: {entry['q3']}")

    # Build dataframe with aggregated data (including field, from and to)
    df = pd.DataFrame(aggregated_data)
    # Add columns at the beginning of the DataFrame
    df.insert(0, "field", aggregation_level)
    df.insert(1, "from", df["changes__0__from"])
    df.insert(2, "to", df["changes__0__to"])
    df.drop(columns=["changes__0__from", "changes__0__to", "total"], inplace=True)

    return df


def run():
    # Get all changes_0 fields
    practices = Entry.objects.values_list("changes__0__field", flat=True).distinct()
    print(f"Found {len(practices)} unique practices.")

    dfs = []

    for practice in practices:
        print(f"Processing practice: {practice}")
        df = compute_practice_differences(practice)
        dfs.append(df)

    # Concatenate all dataframes
    all_data = pd.concat(dfs, ignore_index=True)

    # Save to CSV
    output_path = os.path.join(os.path.dirname(__file__), "minitool")

    if not os.path.exists(output_path):
        os.makedirs(output_path)
    output_file = os.path.join(output_path, "aggregated_practices.csv")
    all_data.to_csv(output_file, index=False)
    print(f"Aggregated data saved to {output_file}")
