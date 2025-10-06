"""
Compile emission scenarios script with support for per-change module types and CSV row data filtering.

This script allows you to define scenarios where each change can specify its own module type
and filters, including CSV row data filters using the 'csv_row_filters' parameter.

Example scenario with CSV row filtering:
{
    "name": "Example Scenario with Row Filtering",
    "category": "Example Category",
    "changes": [
        {
            "module_type": "Annual Cropland",
            "filters": {
                "input_type": "Compost",  # Uses custom_filters JSONField
            },
            "csv_row_filters": {
                "soil_type": "High Activity Clay",  # Uses csv_row_data JSONField
                "climate": "Cool Temperate",
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
                "region": "Central Asia",  # Can filter by any CSV column
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
"""

import minitool.models as models
import statistics
from django.db.models import Avg, Sum, Min, Max, Count
from django.db.models import Q


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

COASTAL = [
    # Mangrove Replanting and Natural Recruitment
    {
        "name": "Mangrove Replanting and Natural Recruitment",
        "category": "Coastal Wetland",
        "changes": [
            {
                "module_type": "Coastal Wetland",
                "filters": {
                    "land_use_type": "Mangrove",
                },
                "start": {
                    "field": "area_w_restored_vegetation",
                    "value": "0",
                },
                "end": {
                    "field": "area_w_restored_vegetation",
                    "value": "1",
                },
            },
        ],
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    },
    # Coastal Zone Stabilization (e.g. through vegetation or permeable structures)
    {
        "name": "Coastal Zone Stabilization (e.g. through vegetation or permeable structures)",
        "category": "Coastal Wetland",
        "changes": [
            {
                "module_type": "Coastal Wetland",
                "filters": {
                    "land_use_type": "Mangrove",
                },
                "start": {
                    "field": "area_w_restored_vegetation",
                    "value": "0",
                },
                "end": {
                    "field": "area_w_restored_vegetation",
                    "value": "1",
                },
            },
            {
                "module_type": "Coastal Wetland",
                "filters": {
                    "land_use_type": "Seagrass",
                },
                "start": {
                    "field": "area_w_restored_vegetation",
                    "value": "0",
                },
                "end": {
                    "field": "area_w_restored_vegetation",
                    "value": "1",
                },
            },
            {
                "module_type": "Coastal Wetland",
                "filters": {
                    "land_use_type": "Tidal Marsh",
                },
                "start": {
                    "field": "area_w_restored_vegetation",
                    "value": "0",
                },
                "end": {
                    "field": "area_w_restored_vegetation",
                    "value": "1",
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
        "changes": [
            {
                "module_type": "Annual Cropland",
                "filters": {
                    "land_use_type": "Default",
                },
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
                "filters": {
                    "land_use_type": "Default",
                },
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
                "filters": {
                    "land_use_type": "Default",
                },
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
                "filters": {
                    "land_use_type": "Default",
                },
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
                "filters": {
                    "land_use_type": "Default",
                },
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
                "filters": {
                    "land_use_type": "Default",
                },
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
                "filters": {
                    "land_use_type": "Default",
                },
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
    },
]

FOREST_MANAGEMENT = [
    # Natural regeneration: forest degradation management
    {
        "name": "Natural regeneration: forest degradation management",
        "category": "Forest Restoration",
        "changes": [
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_condition_type": "Secondary",
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
    },
    # Enrichment planting in degraded forests
    {
        "name": "Enrichment planting in degraded forests",
        "category": "Forest Restoration",
        "changes": [
            {
                "module_type": "Forest Management",
                "filters": {
                    "forest_condition_type": "Secondary",
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
    },
    # Reintroduction of threatened species (e.g. flora, fauna, fungi)
    {
        "name": "Reintroduction of threatened species (e.g. flora, fauna, fungi)",
        "category": "Forest Restoration",
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
    },
]

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
        for change in scenario["changes"]:
            module_type = change.get("module_type")
            if not module_type:
                continue

            change_filters = change.get("filters", {})
            csv_row_filters = change.get("csv_row_filters", {})

            # Convert values to strings (matching how they're stored in database)
            from_value = str(change["start"]["value"])
            to_value = str(change["end"]["value"])

            change_q = Q(
                module_type=module_type,
                field=change["start"]["field"],
                from_value=from_value,
                to_value=to_value,
            )

            # Apply standard filters
            if change_filters.get("region"):
                change_q &= Q(region=change_filters["region"])
            if change_filters.get("climate"):
                change_q &= Q(climate=change_filters["climate"])
            if change_filters.get("moisture"):
                change_q &= Q(moisture=change_filters["moisture"])
            if change_filters.get("soil_type"):
                change_q &= Q(soil_type=change_filters["soil_type"])

            # Apply custom filters (stored in custom_filters JSONField or csv_row_data JSONField)
            for filter_key, filter_value in change_filters.items():
                if filter_key not in ["region", "climate", "moisture", "soil_type"]:
                    # Try both custom_filters and csv_row_data for the filter
                    filter_q = Q(**{f"custom_filters__{filter_key}": filter_value}) | Q(**{f"csv_row_data__{filter_key}": filter_value})
                    change_q &= filter_q

            # Apply CSV row data filters (stored in csv_row_data JSONField)
            for filter_key, filter_value in csv_row_filters.items():
                change_q &= Q(**{f"csv_row_data__{filter_key}": filter_value})

            q_objects |= change_q

        aggregates = models.ChangeRecord.objects.filter(q_objects)
        print(scenario["category"], "-", scenario["name"])
        
        # Debug: Show the query being constructed
        print(f"Query: {q_objects}")
        
        # Show CSV row filters if any changes have them
        csv_filters_used = []
        for change in scenario["changes"]:
            if "csv_row_filters" in change and change["csv_row_filters"]:
                csv_filters_used.append(f"{change.get('module_type', 'Unknown')}: {change['csv_row_filters']}")
        
        if csv_filters_used:
            print("CSV row filters applied:")
            for filter_info in csv_filters_used:
                print(f"  {filter_info}")

        # Debug: Show what records exist for this module type
        module_types_in_scenario = set()
        for change in scenario["changes"]:
            if change.get("module_type"):
                module_types_in_scenario.add(change["module_type"])
        
        for module_type in module_types_in_scenario:
            total_records = models.ChangeRecord.objects.filter(module_type=module_type).count()
            print(f"Total {module_type} records in database: {total_records}")
            
            # Show a sample of records for debugging
            sample_records = models.ChangeRecord.objects.filter(module_type=module_type)[:3]
            for i, record in enumerate(sample_records):
                print(f"  Sample {i+1}: field={record.field}, from={record.from_value}, to={record.to_value}")
                print(f"    custom_filters: {record.custom_filters}")
                if hasattr(record, 'csv_row_data'):
                    print(f"    csv_row_data keys: {list(record.csv_row_data.keys()) if record.csv_row_data else 'None'}")

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
