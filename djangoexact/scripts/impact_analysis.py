import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

# Read the CSV data
df = pd.read_csv(os.path.join(os.path.dirname(__file__), "aggregated_data", "grassland", "aggregated_by_environmental_factors.csv"))


def calculate_element_impact(df, column_name):
    """Calculate the impact of an element based on variance in means"""
    grouped = df.groupby(column_name)["mean"].agg(["mean", "std", "min", "max"])

    # Calculate range and coefficient of variation
    grouped["range"] = grouped["max"] - grouped["min"]
    grouped["cv"] = grouped["std"] / grouped["mean"].abs().replace(0, np.nan)

    # Overall impact metrics
    group_means = df.groupby(column_name)["mean"].mean()
    overall_variance = group_means.var()
    overall_range = grouped["range"].max()
    mean_cv = grouped["cv"].mean()

    # Handle NaN values
    if pd.isna(overall_variance):
        overall_variance = 0.0
    if pd.isna(overall_range):
        overall_range = 0.0
    if pd.isna(mean_cv):
        mean_cv = 0.0

    return {"element": column_name, "variance": float(overall_variance), "range": float(overall_range), "mean_cv": float(mean_cv), "num_categories": int(len(grouped)), "category_stats": grouped.to_dict("index")}


def save_raw_results(results, output_file):
    """Save raw analysis results to JSON"""

    # Convert any remaining numpy types to Python types
    def convert_types(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        return obj

    # Clean the data
    clean_results = []
    for result in results:
        clean_result = {}
        for key, value in result.items():
            if key == "category_stats":
                clean_stats = {}
                for category, stats in value.items():
                    clean_stats[category] = {k: convert_types(v) for k, v in stats.items()}
                clean_result[key] = clean_stats
            else:
                clean_result[key] = convert_types(value)
        clean_results.append(clean_result)

    # Add metadata
    output_data = {"timestamp": datetime.now().isoformat(), "analysis_results": clean_results}

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    return output_file


def run():
    """Run the impact analysis and save results"""
    # Analyze each element
    elements = ["module", "region", "climate", "moisture", "soil_type"]
    impact_results = []

    for element in elements:
        result = calculate_element_impact(df, element)
        impact_results.append(result)

    # Sort by variance (descending)
    sorted_results = sorted(impact_results, key=lambda x: x["variance"], reverse=True)

    # Save results
    output_file = os.path.join(os.path.dirname(__file__), "impact_analysis_raw.json")
    save_raw_results(sorted_results, output_file)

    print(f"Raw analysis data saved to: {output_file}")


if __name__ == "__main__":
    run()
