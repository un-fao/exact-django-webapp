"""
Compile emission scenarios script with support for per-change module types and CSV row data filtering.

This script allows you to define scenarios where each change can specify its own module type
and filters, including CSV row data filters using the 'csv_row_filters' parameter.

Example scenario with CSV row filtering:
{
    "name": "Example Scenario with Row Filtering",
    "category": "Example Category",
    "filters": {
        "region": ["Central Asia", "Eastern Europe"],  # Applied to ALL changes
    },
    "csv_row_filters": {
        "climate": "Cool Temperate",  # Applied to ALL changes
    },
    "changes": [
        {
            "module_type": "Annual Cropland",
            "filters": {
                "input_type": "Compost",  # Change-specific filter
            },
            "csv_row_filters": {
                "soil_type": ["High Activity Clay", "Low Activity Clay"],
                "moisture": "Moist",
                "land_use_type_start": "Default",
                "tillage_management_type_start": "Full Tillage"
            },
            "start": {"field": "organic_input_type", "value": "Low C input"},
            "end": {"field": "organic_input_type", "value": "High C input, with manure"}
        },
        {
            "module_type": "Grassland",
            "csv_row_filters": {
                "grassland_management_type_start": "Non-Degraded"
            },
            "start": {"field": "grassland_management_type", "value": "Non-Degraded"},
            "end": {"field": "grassland_management_type", "value": "Improved Grassland"}
        }
    ],
    "metadata": {
        "additional_information": "Description of the scenario",
        "assumptions": "Any assumptions made"
    }
}

Key features:
- Each change can specify its own module_type
- 'filters' uses the custom_filters JSONField for module-specific data
- 'csv_row_filters' uses the csv_row_data JSONField for original CSV column data
- Both filter types can be used together for precise targeting
- All filters support both single strings and lists of strings (OR condition within each filter)
- Scenario-level filters automatically apply to all changes (merged with change-level filters)
"""

import minitool.models as models
import statistics
from django.db.models import Avg, Sum, Min, Max, Count
from django.db.models import Q
import pandas as pd
from datetime import datetime
import os


def stats_for(qs):
    # base aggregates
    agg = qs.aggregate(
        n=Count("id"),
        s=Sum("total"),
        mean=Avg("total"),
        minv=Min("total"),
        maxv=Max("total"),
    )
    n, s = agg["n"] or 0, agg["s"] or 0.0
    mean = agg["mean"] if n else None

    if n > 0:
        total_values = list(qs.values_list("total", flat=True))

        # Sum of squares for variance
        ss = sum(x * x for x in total_values)

        # sample variance/std (n-1)
        if n > 1:
            var = (ss - (s * s) / n) / (n - 1)
            std = var**0.5
            se = std / (n**0.5)
            ci95 = 1.96 * se
            ci99 = 2.58 * se
        else:
            std = se = ci95 = ci99 = None

        # Sorted values for percentile calculations
        sorted_values = sorted(total_values)

        if len(sorted_values) >= 4:
            q1 = statistics.quantiles(sorted_values, n=4)[0]
            median = statistics.median(sorted_values)
            q3 = statistics.quantiles(sorted_values, n=4)[2]
        else:
            # For small datasets, use interpolation method
            n_values = len(sorted_values)

            if n_values % 2 == 0:
                median = (sorted_values[n_values // 2 - 1] + sorted_values[n_values // 2]) / 2
            else:
                median = sorted_values[n_values // 2]

            q1_idx = (n_values - 1) * 0.25
            q3_idx = (n_values - 1) * 0.75

            # Interpolate Q1
            if q1_idx.is_integer():
                q1 = sorted_values[int(q1_idx)]
            else:
                lower_idx = int(q1_idx)
                upper_idx = min(lower_idx + 1, n_values - 1)
                weight = q1_idx - lower_idx
                q1 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

            # Interpolate Q3
            if q3_idx.is_integer():
                q3 = sorted_values[int(q3_idx)]
            else:
                lower_idx = int(q3_idx)
                upper_idx = min(lower_idx + 1, n_values - 1)
                weight = q3_idx - lower_idx
                q3 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight
    else:
        std = se = ci95 = ci99 = None
        q1 = median = q3 = None

    iqr = (q3 - q1) if (q1 is not None and q3 is not None) else None

    return {
        "count": n,
        "sum_total": s,
        "mean": mean,
        "median": median,
        "min": agg["minv"],
        "max": agg["maxv"],
        "std": std,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "ci_95": ci95,
        "ci_99": ci99,
    }


DEFAULT_FILTERS = {
    "soil_type": ["High Activity Clay", "Low Activity Clay", "Sandy"],
}

COASTAL = [
    {
        "name": "Mangrove Replanting and Natural Recruitment",
        "category": "Aquatic Restoration",
        "filters": DEFAULT_FILTERS,
        "changes": [
            {
                "module_type": "Coastal Wetland",
                "filters": {
                    "land_use_type": "Mangrove",
                },
                "start": {
                    "field": "area_w_restored_vegetation",
                    "value": 0,
                },
                "end": {
                    "field": "area_w_restored_vegetation",
                    "value": 1,
                },
            },
        ],
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    },
    {
        "name": "Coastal Zone Stabilization (e.g. through vegetation or permeable structures)",
        "category": "Aquatic Restoration",
        "filters": DEFAULT_FILTERS,
        "changes": [
            {
                "module_type": "Coastal Wetland",
                "filters": {
                    "land_use_type": "Mangrove",
                },
                "start": {
                    "field": "area_w_restored_vegetation",
                    "value": 0,
                },
                "end": {
                    "field": "area_w_restored_vegetation",
                    "value": 1,
                },
            },
            {
                "module_type": "Coastal Wetland",
                "filters": {
                    "land_use_type": "Seagrass",
                },
                "start": {
                    "field": "area_w_restored_vegetation",
                    "value": 0,
                },
                "end": {
                    "field": "area_w_restored_vegetation",
                    "value": 1,
                },
            },
            {
                "module_type": "Coastal Wetland",
                "filters": {
                    "land_use_type": "Tidal Marsh",
                },
                "start": {
                    "field": "area_w_restored_vegetation",
                    "value": 0,
                },
                "end": {
                    "field": "area_w_restored_vegetation",
                    "value": 1,
                },
            },
        ],
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    },
]

GRASSLAND = [
    # Soil Remediation
    {
        "name": "Grassland remains Grassland",
        "category": "Soil Remediation",
        "filters": DEFAULT_FILTERS,
        "changes": [
            {
                "module_type": "Grassland",
                "start": {
                    "field": "grassland_management_type",
                    "value": "Severly Degraded",
                },
                "end": {
                    "field": "grassland_management_type",
                    "value": "High Intensity Grazing",
                },
            },
            {
                "module_type": "Grassland",
                "start": {
                    "field": "grassland_management_type",
                    "value": "High Intensity Grazing",
                },
                "end": {
                    "field": "grassland_management_type",
                    "value": "Non-Degraded",
                },
            },
            {
                "module_type": "Grassland",
                "start": {
                    "field": "grassland_management_type",
                    "value": "Non-Degraded",
                },
                "end": {
                    "field": "grassland_management_type",
                    "value": "Non-Degraded",
                },
            },
        ],
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    },
    # Terracing for erosion control and soil conservation
    {
        "name": "Terracing for erosion control and soil conservation",
        "category": "Soil Conservation",
        "filters": DEFAULT_FILTERS,
        "changes": [
            {
                "module_type": "Grassland",
                "start": {
                    "field": "grassland_management_type",
                    "value": "Severly Degraded",
                },
                "end": {
                    "field": "grassland_management_type",
                    "value": "High Intensity Grazing",
                },
            },
            {
                "module_type": "Grassland",
                "start": {
                    "field": "grassland_management_type",
                    "value": "High Intensity Grazing",
                },
                "end": {
                    "field": "grassland_management_type",
                    "value": "Non-Degraded",
                },
            },
            {
                "module_type": "Grassland",
                "start": {
                    "field": "grassland_management_type",
                    "value": "Non-Degraded",
                },
                "end": {
                    "field": "grassland_management_type",
                    "value": "Improved Grassland",
                },
            },
            {
                "module_type": "Grassland",
                "start": {
                    "field": "grassland_management_type",
                    "value": "Improved Grassland",
                },
                "end": {
                    "field": "grassland_management_type",
                    "value": "Improved Grassland",
                },
            },
        ],
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    },
]

ANNUAL_CROPLAND = [
    # Decompaction and improvement of degraded soils
    {
        "name": "Decompaction and improvement of degraded soils",
        "category": "Soil and Land Restoration",
        "filters": DEFAULT_FILTERS,
        "changes": [
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "tillage_management_type",
                    "value": "Full Tillage",
                },
                "end": {
                    "field": "tillage_management_type",
                    "value": "Reduced Tillage",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "tillage_management_type",
                    "value": "Full Tillage",
                },
                "end": {
                    "field": "tillage_management_type",
                    "value": "No Tillage",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "organic_input_type",
                    "value": "Low C input",
                },
                "end": {
                    "field": "organic_input_type",
                    "value": "Medium C input",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "organic_input_type",
                    "value": "Low C input",
                },
                "end": {
                    "field": "organic_input_type",
                    "value": "High C input, no manure",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "organic_input_type",
                    "value": "Low C input",
                },
                "end": {
                    "field": "organic_input_type",
                    "value": "High C input, with manure",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "residue_management_type",
                    "value": "Burned",
                },
                "end": {
                    "field": "residue_management_type",
                    "value": "Retained",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "residue_management_type",
                    "value": "Burned",
                },
                "end": {
                    "field": "residue_management_type",
                    "value": "Exported",
                },
            },
        ],
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    },
    # Better crop management for annual crops
    {
        "name": "Better crop management for annual crops",
        "category": "Intercropping and Crop Rotation",
        "filters": DEFAULT_FILTERS,
        "changes": [
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "tillage_management_type",
                    "value": "Full Tillage",
                },
                "end": {
                    "field": "tillage_management_type",
                    "value": "Reduced Tillage",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "tillage_management_type",
                    "value": "Full Tillage",
                },
                "end": {
                    "field": "tillage_management_type",
                    "value": "No Tillage",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "tillage_management_type",
                    "value": "Reduced Tillage",
                },
                "end": {
                    "field": "tillage_management_type",
                    "value": "No Tillage",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "organic_input_type",
                    "value": "Low C input",
                },
                "end": {
                    "field": "organic_input_type",
                    "value": "Medium C input",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "organic_input_type",
                    "value": "Medium C input",
                },
                "end": {
                    "field": "organic_input_type",
                    "value": "High C input, no manure",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "organic_input_type",
                    "value": "Low C input",
                },
                "end": {
                    "field": "organic_input_type",
                    "value": "High C input, no manure",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "residue_management_type",
                    "value": "Burned",
                },
                "end": {
                    "field": "residue_management_type",
                    "value": "Retained",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "residue_management_type",
                    "value": "Burned",
                },
                "end": {
                    "field": "residue_management_type",
                    "value": "Exported",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "residue_management_type",
                    "value": "Retained",
                },
                "end": {
                    "field": "residue_management_type",
                    "value": "Exported",
                },
            },
            {
                "module_type": "Annual Cropland",
                "start": {
                    "field": "residue_management_type",
                    "value": "Exported",
                },
                "end": {
                    "field": "residue_management_type",
                    "value": "Retained",
                },
            },
        ],
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    },
]

FOREST_MANAGEMENT = [
    # Natural regeneration: forest degradation management
    {
        "name": "Natural regeneration: forest degradation management",
        "category": "Forest Restoration",
        "filters": DEFAULT_FILTERS,
        "changes": [
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_condition_type": "Secondary",
                    "forest_type": "Natural",
                },
                "start": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0.01,
                },
                "end": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0,
                },
            },
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_condition_type": "Secondary",
                    "forest_type": "Natural",
                },
                "start": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0.02,
                },
                "end": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0,
                },
            },
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_condition_type": "Secondary",
                    "forest_type": "Natural",
                },
                "start": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0.03,
                },
                "end": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0,
                },
            },
        ],
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    },
    # Enrichment planting in degraded forests
    {
        "name": "Enrichment planting in degraded forests",
        "category": "Forest Restoration",
        "filters": DEFAULT_FILTERS,
        "changes": [
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_condition_type": "Secondary",
                    "forest_type": "Natural",
                },
                "start": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0.01,
                },
                "end": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0,
                },
            },
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_condition_type": "Secondary",
                    "forest_type": "Natural",
                },
                "start": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0.02,
                },
                "end": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0,
                },
            },
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_condition_type": "Secondary",
                    "forest_type": "Natural",
                },
                "start": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0.03,
                },
                "end": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0,
                },
            },
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_type": "Plantation",
                },
                "start": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0.01,
                },
                "end": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0,
                },
            },
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_type": "Plantation",
                },
                "start": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0.02,
                },
                "end": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0,
                },
            },
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_type": "Plantation",
                },
                "start": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0.03,
                },
                "end": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0,
                },
            },
        ],
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    },
    # Reintroduction of threatened species (e.g. flora, fauna, fungi)
    {
        "name": "Reintroduction of threatened species (e.g. flora, fauna, fungi)",
        "category": "Forest Restoration",
        "filters": DEFAULT_FILTERS,
        "changes": [
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_condition_type": "Secondary",
                },
                "start": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0.02,
                },
                "end": {
                    "field": "average_yearly_degradation_percentage",
                    "value": 0,
                },
            },
        ],
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    },
]


def save_to_excel(scenarios, output_dir="reports"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"emission_scenarios_{timestamp}.xlsx"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    filepath = os.path.join(output_dir, filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        summary_data = []

        for scenario in scenarios:
            stats = scenario.get("statistics")
            if not stats:
                continue

            mean_minus_median = stats["mean"] - stats["median"] if stats.get("mean") and stats.get("median") else None
            is_symmetric = mean_minus_median < 0.25 * stats["std"] if mean_minus_median is not None and stats.get("std") else None

            if is_symmetric:
                range_lower = stats["mean"] - stats["std"] if stats.get("mean") and stats.get("std") else None
                range_upper = stats["mean"] + stats["std"] if stats.get("mean") and stats.get("std") else None
                distribution_type = "Symmetric"
            else:
                range_lower = stats.get("q1")
                range_upper = stats.get("q3")
                distribution_type = "Skewed"

            summary_data.append(
                {
                    "Category": scenario.get("category", ""),
                    "Scenario Name": scenario.get("name", ""),
                    "Count": stats.get("count", 0),
                    "Sum Total": stats.get("sum_total"),
                    "Mean": stats.get("mean"),
                    "Median": stats.get("median"),
                    "Min": stats.get("min"),
                    "Max": stats.get("max"),
                    "Std Dev": stats.get("std"),
                    "Q1": stats.get("q1"),
                    "Q3": stats.get("q3"),
                    "IQR": stats.get("iqr"),
                    "CI 95%": stats.get("ci_95"),
                    "CI 99%": stats.get("ci_99"),
                    "Distribution": distribution_type,
                    "Range Lower": range_lower,
                    "Range Upper": range_upper,
                }
            )

        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        worksheet = writer.sheets["Summary"]
        for idx, col in enumerate(summary_df.columns):
            max_length = max(summary_df[col].astype(str).apply(len).max(), len(str(col))) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)

        for idx, scenario in enumerate(scenarios):
            if not scenario.get("statistics"):
                continue

            sheet_name = f"S{idx + 1}_{scenario['name'][:25]}"
            sheet_name = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in sheet_name)

            scenario_details = []
            scenario_details.append({"Field": "Scenario Name", "Value": scenario.get("name", "")})
            scenario_details.append({"Field": "Category", "Value": scenario.get("category", "")})
            scenario_details.append({"Field": "", "Value": ""})

            scenario_details.append({"Field": "STATISTICS", "Value": ""})
            stats = scenario["statistics"]
            for key, value in stats.items():
                if value is not None:
                    scenario_details.append({"Field": key.replace("_", " ").title(), "Value": value})

            scenario_details.append({"Field": "", "Value": ""})
            scenario_details.append({"Field": "FILTERS", "Value": ""})
            filters = scenario.get("filters", {})
            for key, value in filters.items():
                scenario_details.append({"Field": key, "Value": str(value)})

            csv_filters = scenario.get("csv_row_filters", {})
            if csv_filters:
                scenario_details.append({"Field": "", "Value": ""})
                scenario_details.append({"Field": "CSV ROW FILTERS", "Value": ""})
                for key, value in csv_filters.items():
                    scenario_details.append({"Field": key, "Value": str(value)})

            scenario_details.append({"Field": "", "Value": ""})
            scenario_details.append({"Field": "CHANGES", "Value": ""})

            changes_data = []
            for change_idx, change in enumerate(scenario.get("changes", []), 1):
                change_info = {
                    "Change #": change_idx,
                    "Module Type": change.get("module_type", ""),
                    "Field": change.get("start", {}).get("field", ""),
                    "From Value": change.get("start", {}).get("value", ""),
                    "To Value": change.get("end", {}).get("value", ""),
                }

                change_filters = change.get("filters", {})
                if change_filters:
                    change_info["Filters"] = str(change_filters)

                change_csv_filters = change.get("csv_row_filters", {})
                if change_csv_filters:
                    change_info["CSV Filters"] = str(change_csv_filters)

                changes_data.append(change_info)

            detail_df = pd.DataFrame(scenario_details)
            detail_df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)

            if changes_data:
                changes_df = pd.DataFrame(changes_data)
                start_row = len(scenario_details) + 2
                changes_df.to_excel(writer, sheet_name=sheet_name, startrow=start_row, index=False)

            worksheet = writer.sheets[sheet_name]
            worksheet.column_dimensions["A"].width = 30
            worksheet.column_dimensions["B"].width = 50

            metadata = scenario.get("metadata", {})
            if metadata:
                metadata_start = len(scenario_details) + len(changes_data) + 5
                metadata_details = [{"Field": "", "Value": ""}]
                metadata_details.append({"Field": "METADATA", "Value": ""})
                for key, value in metadata.items():
                    metadata_details.append({"Field": key.replace("_", " ").title(), "Value": str(value)})

                metadata_df = pd.DataFrame(metadata_details)
                metadata_df.to_excel(writer, sheet_name=sheet_name, startrow=metadata_start, index=False, header=False)

    print(f"\n{'=' * 80}")
    print(f"Excel file saved: {filepath}")
    print(f"{'=' * 80}\n")

    return filepath


def run(clear: bool = False):
    if clear:
        models.EmissionScenario.objects.all().delete()

    scenarios = [
        *FOREST_MANAGEMENT,
        *GRASSLAND,
        *ANNUAL_CROPLAND,
        *COASTAL,
    ]

    """
    # Soil Amendments
        # Annual Cropland remains Annual Cropland
        # {
        #     "name": "Annual Cropland remains Annual Cropland",
        #     "category": "Soil Amendments",
        #     "changes": [
        #         {
        #            "module_type": "Input",
        #            "filters": {
        #                "input_type": "Compost",
        #            },
        #            "start": {
        #                "field": "value",
        #                "value": "0",
        #            },
        #            "end": {
        #                "field": "value",
        #                "value": "1",
        #            },
        #         },
        #         {
        #             "module_type": "Annual Cropland",
        #             "start": {
        #                 "field": "tillage_management_type",
        #                 "value": "Full Tillage",
        #             },
        #             "end": {
        #                 "field": "tillage_management_type",
        #                 "value": "Full Tillage",
        #             },
        #         },
        #         {
        #             "module_type": "Annual Cropland",
        #             "start": {
        #                 "field": "organic_input_type",
        #                 "value": "Low C input",
        #             },
        #             "end": {
        #                 "field": "organic_input_type",
        #                 "value": "Low C input",
        #             },
        #         },
        #         {
        #             "module_type": "Annual Cropland",
        #             "start": {
        #                 "field": "organic_input_type",
        #                 "value": "Medium C input",
        #             },
        #             "end": {
        #                 "field": "organic_input_type",
        #                 "value": "Medium C input",
        #             },
        #         },
        #         {
        #             "module_type": "Annual Cropland",
        #             "start": {
        #                 "field": "organic_input_type",
        #                 "value": "High C input, no manure",
        #             },
        #             "end": {
        #                 "field": "organic_input_type",
        #                 "value": "High C input, no manure",
        #             },
        #         },
        #         {
        #             "module_type": "Annual Cropland",
        #             "start": {
        #                 "field": "organic_input_type",
        #                 "value": "High C input, with manure",
        #             },
        #             "end": {
        #                 "field": "organic_input_type",
        #                 "value": "High C input, with manure",
        #             },
        #         },
        #         {
        #             "module_type": "Annual Cropland",
        #             "start": {
        #                 "field": "residue_management_type",
        #                 "value": "Exported",
        #             },
        #             "end": {
        #                 "field": "residue_management_type",
        #                 "value": "Exported",
        #             },
        #         },
        #     ],
        #     "metadata": {
        #         "additional_information": "",
        #         "assumptions": "",
        #     },
        # },
        # Grassland remains Grassland
        # {
        #     "name": "Grassland remains Grassland",
        #     "category": "Soil Amendments",
        #     "changes": [
        #         {
        #             "module_type": "Input",
        #             "filters": {
        #                 "input_type": "Compost",
        #             },
        #             "start": {
        #                 "field": "value",
        #                 "value": "0",
        #             },
        #             "end": {
        #                 "field": "value",
        #                 "value": "1",
        #             },
        #         },
        #         {
        #             "module_type": "Grassland",
        #             "start": {
        #                 "field": "grassland_management_type",
        #                 "value": "Severly Degraded",
        #             },
        #             "end": {
        #                 "field": "grassland_management_type",
        #                 "value": "Severely Degraded",
        #             },
        #         },
        #         {
        #             "module_type": "Grassland",
        #             "start": {
        #                 "field": "grassland_management_type",
        #                 "value": "High Intensity Grazing",
        #             },
        #             "end": {
        #                 "field": "grassland_management_type",
        #                 "value": "High Intensity Grazing",
        #             },
        #         },
        #         {
        #             "module_type": "Grassland",
        #             "start": {
        #                 "field": "grassland_management_type",
        #                 "value": "Non-Degraded",
        #             },
        #             "end": {
        #                 "field": "grassland_management_type",
        #                 "value": "Non-Degraded",
        #             },
        #         },
        #         {
        #             "module_type": "Grassland",
        #             "start": {
        #                 "field": "grassland_management_type",
        #                 "value": "Improved Grassland",
        #             },
        #             "end": {
        #                 "field": "grassland_management_type",
        #                 "value": "Improved Grassland",
        #             },
        #         },
        #         {
        #             "module_type": "Grassland",
        #             "start": {
        #                 "field": "grassland_management_type",
        #                 "value": "Improved Grassland With Medium Inputs",
        #             },
        #             "end": {
        #                 "field": "grassland_management_type",
        #                 "value": "Improved Grassland With Medium Inputs",
        #             },
        #         },
        #         {
        #             "module_type": "Grassland",
        #             "start": {
        #                 "field": "grassland_management_type",
        #                 "value": "Improved Grassland With High Inputs",
        #             },
        #             "end": {
        #                 "field": "grassland_management_type",
        #                 "value": "Improved Grassland With High Inputs",
        #             },
        #         },
        #     ],
        #     "metadata": {
        #         "additional_information": "- Biochar adds stable carbon; compost improves fertility and microbial activity",
        #         "assumptions": "1) assumes the application of organic inputs (compost and biochar) in cultivated soils;\n2) assumes the application of organic inputs (compost and biochar) in grasslands;\n3) assumes that without the project there would not be application of inputs;\n4) assumes that with project increase the C input in the soil;\n5) assumes change of other practices in soil conservation: tillage to reduce tillage (in some situations zero tillage could be assumed);\n6) GRASSLAND - changes only in C input due to the biochar, no changes in tillage nor residue managment.",
        #     },
        # },
        # {
        #     "name": "Forest Degradation Management",
        #     "category": "Natural Regeneration",
        #     "module_type": "Forest Management",
        #     "filters": {
        #         "forest_condition_type": "Secondary",
        #     },
        #     "changes": [
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.01,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.02,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.03,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #         },
        #     ],
        #     "metadata": {
        #         "additional_information": "- Relies on natural seed banks and dispersal agents\n- Often cheaper but slower; effectiveness depends on proximity to seed sources and absence of severe degradation",
        #         "assumptions": "1) practice would entail the grow of new seedlings, similar as af/re-forestation;\n2) no change in growth rate from as the preconditions for the activities are different and effectiveness is linked to context rather than the activity per se;\n3) Forest degradation management: As it is not possible to determine the SOC it could be assumed as non-degraded or as high-intensity grazing.",
        #     },
        # }
        # {
        #     "name": "Afforestation",
        #     "category": "Natural Regeneration",
        #     "module_type": "Land Use Change",
        #     "filters": {
        #         "module_w_forest_type": "Secondary",
        #     },
        #     "changes": [
        #         {
        #             "start": {
        #                 "field": "module_type",
        #                 "value": "Grassland",
        #             },
        #             "end": {
        #                 "field": "module_type",
        #                 "value": "ForestManagement",
        #             },
        #         },
        #     ],
        #     "metadata": {
        #         "additional_information": "- Relies on natural seed banks and dispersal agents\n- Often cheaper but slower; effectiveness depends on proximity to seed sources and absence of severe degradation",
        #         "assumptions": "1) practice would entail the grow of new seedlings, similar as af/re-forestation;\n2) no change in growth rate from as the preconditions for the activities are different and effectiveness is linked to context rather than the activity per se;\n3) Grassland: As it is not possible to determine the SOC it could be assumed as non-degraded or as high-intensity grazing.",
        #     },
        # },
        # {
        #     "name": "Tillage Reduction",
        #     "module_type": "Perennial Cropland",
        #     "filters": {
        #         "land_use_type": "Default",
        #     },
        #     "changes": [
        #         {
        #             "start": {
        #                 "field": "tillage_management_type",
        #                 "value": "Full Tillage",
        #             },
        #             "end": {
        #                 "field": "tillage_management_type",
        #                 "value": "Reduced Tillage",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "tillage_management_type",
        #                 "value": "Reduced Tillage",
        #             },
        #             "end": {
        #                 "field": "tillage_management_type",
        #                 "value": "No Tillage",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "tillage_management_type",
        #                 "value": "Full Tillage",
        #             },
        #             "end": {
        #                 "field": "tillage_management_type",
        #                 "value": "No Tillage",
        #             },
        #         },
        #     ],
        # },
        # {
        #     "name": "Increasing Carbon Input",
        #     "module_type": "Annual Cropland",
        #     "filters": {
        #         "land_use_type": "Default",
        #     },
        #     "changes": [
        #         {
        #             "start": {
        #                 "field": "organic_input_type",
        #                 "value": "Low C input",
        #             },
        #             "end": {
        #                 "field": "organic_input_type",
        #                 "value": "Medium C input",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "organic_input_type",
        #                 "value": "Medium C input",
        #             },
        #             "end": {
        #                 "field": "organic_input_type",
        #                 "value": "High C input, no manure",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "organic_input_type",
        #                 "value": "High C input, no manure",
        #             },
        #             "end": {
        #                 "field": "organic_input_type",
        #                 "value": "High C input, with manure",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "organic_input_type",
        #                 "value": "Low C input",
        #             },
        #             "end": {
        #                 "field": "organic_input_type",
        #                 "value": "High C input, no manure",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "organic_input_type",
        #                 "value": "Low C input",
        #             },
        #             "end": {
        #                 "field": "organic_input_type",
        #                 "value": "High C input, with manure",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "organic_input_type",
        #                 "value": "Medium C input",
        #             },
        #             "end": {
        #                 "field": "organic_input_type",
        #                 "value": "High C input, with manure",
        #             },
        #         },
        #     ],
        # },
        # {
        #     "name": "Stopping Residue Burning",
        #     "module_type": "Annual Cropland",
        #     "filters": {
        #         "land_use_type": "Default",
        #     },
        #     "changes": [
        #         {
        #             "start": {
        #                 "field": "residue_management_type",
        #                 "value": "Burned",
        #             },
        #             "end": {
        #                 "field": "residue_management_type",
        #                 "value": "Retained",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "residue_management_type",
        #                 "value": "Burned",
        #             },
        #             "end": {
        #                 "field": "residue_management_type",
        #                 "value": "Exported",
        #             },
        #         },
        #     ],
        # },
        # {
        #     "name": "Water management before the cultivation",
        #     "module_type": "Flooded Rice",
        #     "filters": {},
        #     "changes": [
        #         {
        #             "start": {
        #                 "field": "water_management_type_before_cultivation",
        #                 "value": "Flooded Pre-Season > 30 D",
        #             },
        #             "end": {
        #                 "field": "water_management_type_before_cultivation",
        #                 "value": "Non Flooded Pre-Season >180 D",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_before_cultivation",
        #                 "value": "Non Flooded Pre-Season <180 D",
        #             },
        #             "end": {
        #                 "field": "water_management_type_before_cultivation",
        #                 "value": "Non Flooded Pre-Season >180 D",
        #             },
        #         },
        #     ],
        # },
        # {
        #     "name": "Water management after cultivation",
        #     "module_type": "Flooded Rice",
        #     "filters": {},
        #     "changes": [
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Deep Water",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Dry Season (Drought Prone)",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Deep Water",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Wet Season (Regular Rainfed)",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Deep Water",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Continuously Flooded",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Deep Water",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Single Drainage Period",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Deep Water",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Multiple Drainage Periods",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Dry Season (Drought Prone)",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Wet Season (Regular Rainfed)",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Dry Season (Drought Prone)",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Continuously Flooded",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Dry Season (Drought Prone)",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Single Drainage Period",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Dry Season (Drought Prone)",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Multiple Drainage Periods",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Wet Season (Regular Rainfed)",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Irrigated, Continuously Flooded",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Wet Season (Regular Rainfed)",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Single Drainage Period",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Rainfed, Wet Season (Regular Rainfed)",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Multiple Drainage Periods",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Continuously Flooded",
        #             },
        #             "end": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Single Drainage Period",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Continuously Flooded",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Multiple Drainage Periods",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Single Drainage Period",
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "water_management_type_after_cultivation",
        #                 "value": "Irrigated, Multiple Drainage Periods",
        #             },
        #         },
        #     ],
        # },
        # {
        #     "name": "Forest degradation management",
        #     "module_type": "Forest Management",
        #     "filters": {},
        #     "changes": [
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.01,
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.02,
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.03,
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.04,
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.05,
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.1,
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.15,
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.2,
        #             },
        #         },
        #         {
        #             "start": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0,
        #             },
        #             "end": {
        #                 "field": "average_yearly_degradation_percentage",
        #                 "value": 0.25,
        #             },
        #         },
        #     ],
        # },
    """

    for scenario in scenarios:
        category, created = models.EmissionScenarioCategory.objects.get_or_create(name=scenario["category"])

        models.EmissionScenario.objects.create(
            name=scenario["name"],
            changes=scenario["changes"],
            category=category,
            metadata=scenario["metadata"],
        )

    for scenario in scenarios:
        q_objects = Q()

        # Extract scenario-level filters
        scenario_filters = scenario.get("filters", {})
        scenario_csv_row_filters = scenario.get("csv_row_filters", {})

        for change in scenario["changes"]:
            module_type = change.get("module_type")
            if not module_type:
                continue

            # Merge scenario-level filters with change-level filters
            change_filters = {**scenario_filters, **change.get("filters", {})}
            csv_row_filters = {**scenario_csv_row_filters, **change.get("csv_row_filters", {})}

            # Create flexible query that handles both integer and decimal string formats
            # For numeric values, check both formats (e.g., "0" and "0.0", "1" and "1.0")
            def create_flexible_value_query(field_name, value):
                try:
                    float_val = float(value)
                    if float_val.is_integer():
                        # For whole numbers, check both integer and decimal formats
                        return Q(**{field_name: str(int(float_val))}) | Q(**{field_name: str(float_val)})
                    else:
                        # For decimals, only check the decimal format
                        return Q(**{field_name: str(float_val)})
                except (ValueError, TypeError):
                    # For non-numeric values, use exact match
                    return Q(**{field_name: str(value)})

            change_q = (
                Q(
                    module_type=module_type,
                    field=change["start"]["field"],
                )
                & create_flexible_value_query("from_value", change["start"]["value"])
                & create_flexible_value_query("to_value", change["end"]["value"])
            )

            # Apply standard filters
            if change_filters.get("region"):
                region_values = change_filters["region"] if isinstance(change_filters["region"], list) else [change_filters["region"]]
                region_q = Q()
                for val in region_values:
                    region_q |= Q(region=val)
                change_q &= region_q

            if change_filters.get("climate"):
                climate_values = change_filters["climate"] if isinstance(change_filters["climate"], list) else [change_filters["climate"]]
                climate_q = Q()
                for val in climate_values:
                    climate_q |= Q(climate=val)
                change_q &= climate_q

            if change_filters.get("moisture"):
                moisture_values = change_filters["moisture"] if isinstance(change_filters["moisture"], list) else [change_filters["moisture"]]
                moisture_q = Q()
                for val in moisture_values:
                    moisture_q |= Q(moisture=val)
                change_q &= moisture_q

            if change_filters.get("soil_type"):
                soil_type_values = change_filters["soil_type"] if isinstance(change_filters["soil_type"], list) else [change_filters["soil_type"]]
                soil_type_q = Q()
                for val in soil_type_values:
                    soil_type_q |= Q(soil_type=val)
                change_q &= soil_type_q

            # Apply custom filters (stored in custom_filters JSONField or csv_row_data JSONField)
            for filter_key, filter_value in change_filters.items():
                if filter_key not in ["region", "climate", "moisture", "soil_type"]:
                    filter_values = filter_value if isinstance(filter_value, list) else [filter_value]
                    filter_q = Q()
                    for val in filter_values:
                        filter_q |= Q(**{f"custom_filters__{filter_key}": val}) | Q(**{f"csv_row_data__{filter_key}": val})
                    change_q &= filter_q

            # Apply CSV row data filters (stored in csv_row_data JSONField)
            for filter_key, filter_value in csv_row_filters.items():
                filter_values = filter_value if isinstance(filter_value, list) else [filter_value]
                csv_filter_q = Q()
                for val in filter_values:
                    csv_filter_q |= Q(**{f"csv_row_data__{filter_key}": val})
                change_q &= csv_filter_q

            q_objects |= change_q

        aggregates = models.ChangeRecord.objects.filter(q_objects)
        print(scenario["category"], "-", scenario["name"])

        if aggregates.count() == 0:
            print("No aggregates found")
            continue

        print(f"Found {aggregates.count()} matching records")

        scenario["statistics"] = stats_for(aggregates)

        print(scenario["statistics"])
        mean_minus_median = scenario["statistics"]["mean"] - scenario["statistics"]["median"]
        is_dataset_symmetric = mean_minus_median < 0.25 * scenario["statistics"]["std"]
        if is_dataset_symmetric:
            print("Dataset is symmetric")
            print(f"Range: {scenario['statistics']['mean'] - scenario['statistics']['std']} to {scenario['statistics']['mean'] + scenario['statistics']['std']}")
        else:
            print("Dataset is skewed")
            print(f"Range: {scenario['statistics']['q1']} to {scenario['statistics']['q3']}")

        print()
        print()

    import os

    if os.getenv("SAVE_TO_EXCEL"):
        save_to_excel(scenarios)
