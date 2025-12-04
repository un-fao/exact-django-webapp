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
from api import models as api_models
from . import minitool_scenarios as scenarios


def stats_for(qs):
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

        ss = sum(x * x for x in total_values)

        if n > 1:
            var = (ss - (s * s) / n) / (n - 1)
            std = var**0.5
            se = std / (n**0.5)
            ci95 = 1.96 * se
            ci99 = 2.58 * se
        else:
            std = se = ci95 = ci99 = None

        sorted_values = sorted(total_values)

        if len(sorted_values) >= 4:
            q1 = statistics.quantiles(sorted_values, n=4)[0]
            median = statistics.median(sorted_values)
            q3 = statistics.quantiles(sorted_values, n=4)[2]
        else:
            n_values = len(sorted_values)

            if n_values % 2 == 0:
                median = (sorted_values[n_values // 2 - 1] + sorted_values[n_values // 2]) / 2
            else:
                median = sorted_values[n_values // 2]

            q1_idx = (n_values - 1) * 0.25
            q3_idx = (n_values - 1) * 0.75

            if q1_idx.is_integer():
                q1 = sorted_values[int(q1_idx)]
            else:
                lower_idx = int(q1_idx)
                upper_idx = min(lower_idx + 1, n_values - 1)
                weight = q1_idx - lower_idx
                q1 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

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


def get_module_type_name(module_type_obj_or_class_name):
    """Convert ModuleType object or class_name to display name"""
    if hasattr(module_type_obj_or_class_name, "name"):
        return module_type_obj_or_class_name.name
    if hasattr(module_type_obj_or_class_name, "__iter__") and not isinstance(module_type_obj_or_class_name, str):
        if module_type_obj_or_class_name:
            first = module_type_obj_or_class_name[0]
            if hasattr(first, "name"):
                return first.name
            if hasattr(first, "class_name"):
                try:
                    mt = api_models.ModuleType.objects.get(class_name=first.class_name)
                    return mt.name
                except api_models.ModuleType.DoesNotExist:
                    return str(module_type_obj_or_class_name)
            else:
                return str(module_type_obj_or_class_name)
        else:
            return None
    if isinstance(module_type_obj_or_class_name, str):
        try:
            mt = api_models.ModuleType.objects.get(class_name=module_type_obj_or_class_name)
            return mt.name
        except api_models.ModuleType.DoesNotExist:
            return module_type_obj_or_class_name.replace("_", " ").title()
    return str(module_type_obj_or_class_name)


def extract_name_from_queryset(qs):
    """Extract name values from a queryset or list"""
    if hasattr(qs, "__iter__"):
        if hasattr(qs, "values_list"):
            return list(qs.values_list("name", flat=True))
        elif hasattr(qs, "__getitem__"):
            result = []
            for item in qs:
                if hasattr(item, "name"):
                    result.append(item.name)
                else:
                    result.append(str(item))
            return result
        else:
            return [str(qs)]
    return [str(qs)] if qs else []


def convert_scenario_from_minitool_format(scenario_dict, scenario_name, category):
    """Convert a scenario from minitool_scenarios.py format to compile format"""
    changes = []
    csv_row_filters = {}
    filters = {}

    if "fields" in scenario_dict:
        fields = scenario_dict["fields"]

        if "module_start" in fields or "module_w" in fields:
            module_start = fields.get("module_start", {})
            module_w = fields.get("module_w", {})

            start_type = module_start.get("type")
            w_type = module_w.get("type")

            if start_type and w_type:
                start_type_name = get_module_type_name(start_type[0] if isinstance(start_type, list) else start_type)
                w_type_name = get_module_type_name(w_type[0] if isinstance(w_type, list) else w_type)

                csv_row_filters["module_start_type"] = start_type_name
                csv_row_filters["module_w_type"] = w_type_name

                start_fields = module_start.get("fields", {})
                w_fields = module_w.get("fields", {})

                for field_key, field_value in start_fields.items():
                    if field_key.endswith("_start"):
                        csv_row_filters[field_key] = extract_name_from_queryset(field_value)
                    else:
                        csv_row_filters[f"module_start_{field_key}"] = extract_name_from_queryset(field_value)

                for field_key, field_value in w_fields.items():
                    if field_key.endswith("_w"):
                        csv_row_filters[field_key] = extract_name_from_queryset(field_value)
                    else:
                        csv_row_filters[f"module_w_{field_key}"] = extract_name_from_queryset(field_value)

                changes.append(
                    {
                        "module_type": "Land Use Change",
                        "start": {
                            "field": "module_type",
                            "value": start_type_name,
                        },
                        "end": {
                            "field": "module_type",
                            "value": w_type_name,
                        },
                    }
                )
        else:
            module_type_name = None
            for key in ["AnnualCropland", "Grassland", "ForestManagement", "CoastalWetland", "PerennialCropland"]:
                if any(k.startswith(key.lower()) for k in fields.keys()):
                    module_type_name = get_module_type_name(key)
                    break

            if not module_type_name:
                return None

            field_changes = {}
            field_filters = {}

            for field_key, field_value in fields.items():
                if field_key.endswith("_start"):
                    field_name = field_key[:-6]
                    if field_name not in field_changes:
                        field_changes[field_name] = {"start": [], "end": []}
                    field_changes[field_name]["start"] = extract_name_from_queryset(field_value)
                elif field_key.endswith("_w"):
                    field_name = field_key[:-2]
                    if field_name not in field_changes:
                        field_changes[field_name] = {"start": [], "end": []}
                    field_changes[field_name]["end"] = extract_name_from_queryset(field_value)
                else:
                    field_filters[field_key] = extract_name_from_queryset(field_value)

            for field_name, field_data in field_changes.items():
                start_values = field_data.get("start", [])
                end_values = field_data.get("end", [])

                if not start_values or not end_values:
                    continue

                for start_val in start_values:
                    for end_val in end_values:
                        change = {
                            "module_type": module_type_name,
                            "start": {
                                "field": field_name,
                                "value": start_val,
                            },
                            "end": {
                                "field": field_name,
                                "value": end_val,
                            },
                        }

                        if field_filters:
                            change["filters"] = field_filters.copy()

                        changes.append(change)

    for module_key, module_data in scenario_dict.items():
        if module_key == "fields":
            continue

        if not isinstance(module_data, dict) or "fields" not in module_data:
            continue

        module_fields = module_data["fields"]
        module_type_name = get_module_type_name(module_key)

        if module_type_name == "Land Use Change":
            module_start = module_fields.get("module_start", {})
            module_w = module_fields.get("module_w", {})

            start_type = module_start.get("type")
            w_type = module_w.get("type")

            if start_type and w_type:
                start_type_name = get_module_type_name(start_type[0] if isinstance(start_type, list) else start_type)
                w_type_name = get_module_type_name(w_type[0] if isinstance(w_type, list) else w_type)

                csv_row_filters["module_start_type"] = start_type_name
                csv_row_filters["module_w_type"] = w_type_name

                start_fields = module_start.get("fields", {})
                w_fields = module_w.get("fields", {})

                for field_key, field_value in start_fields.items():
                    if field_key.endswith("_start"):
                        csv_row_filters[field_key] = extract_name_from_queryset(field_value)
                    else:
                        csv_row_filters[f"module_start_{field_key}"] = extract_name_from_queryset(field_value)

                for field_key, field_value in w_fields.items():
                    if field_key.endswith("_w"):
                        csv_row_filters[field_key] = extract_name_from_queryset(field_value)
                    else:
                        csv_row_filters[f"module_w_{field_key}"] = extract_name_from_queryset(field_value)

                changes.append(
                    {
                        "module_type": "Land Use Change",
                        "start": {
                            "field": "module_type",
                            "value": start_type_name,
                        },
                        "end": {
                            "field": "module_type",
                            "value": w_type_name,
                        },
                    }
                )
        else:
            field_changes = {}
            field_filters = {}

            for field_key, field_value in module_fields.items():
                if field_key.endswith("_start"):
                    field_name = field_key[:-6]
                    if field_name not in field_changes:
                        field_changes[field_name] = {"start": [], "end": []}
                    field_changes[field_name]["start"] = extract_name_from_queryset(field_value)
                elif field_key.endswith("_w"):
                    field_name = field_key[:-2]
                    if field_name not in field_changes:
                        field_changes[field_name] = {"start": [], "end": []}
                    field_changes[field_name]["end"] = extract_name_from_queryset(field_value)
                else:
                    field_filters[field_key] = extract_name_from_queryset(field_value)

            for field_name, field_data in field_changes.items():
                start_values = field_data.get("start", [])
                end_values = field_data.get("end", [])

                if not start_values or not end_values:
                    continue

                for start_val in start_values:
                    for end_val in end_values:
                        change = {
                            "module_type": module_type_name,
                            "start": {
                                "field": field_name,
                                "value": start_val,
                            },
                            "end": {
                                "field": field_name,
                                "value": end_val,
                            },
                        }

                        if field_filters:
                            change["filters"] = field_filters.copy()

                        changes.append(change)

    if not changes:
        return None

    return {
        "name": scenario_name,
        "category": category,
        "filters": {**DEFAULT_FILTERS, **filters},
        "csv_row_filters": csv_row_filters,
        "changes": changes,
        "metadata": {
            "additional_information": "",
            "assumptions": "",
        },
    }


FOREST_RESTORATION = [
    convert_scenario_from_minitool_format(
        {
            "fields": {
                "module_start": {
                    "type": [api_models.ModuleType.objects.get(class_name="Grassland")],
                    "fields": {
                        "grassland_management_type_start": list(api_models.GrasslandManagementType.objects.filter(name__in=["Non-Degraded", "High Intensity Grazing"])),
                    },
                },
                "module_w": {
                    "type": [api_models.ModuleType.objects.get(class_name="ForestManagement")],
                    "fields": {
                        "land_use_type": list(api_models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                        "forest_type": list(api_models.ForestType.objects.filter(name__in=["Natural"])),
                        "forest_condition_type": list(api_models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                    },
                },
            },
        },
        "Natural regeneration: Afforestation",
        "Forest Restoration",
    ),
    convert_scenario_from_minitool_format(
        {
            "fields": {
                "land_use_type": list(api_models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                "forest_type": list(api_models.ForestType.objects.filter(name__in=["Natural"])),
                "forest_condition_type": list(api_models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                "average_yearly_degradation_percentage_start": [0.01, 0.02, 0.03],
                "average_yearly_degradation_percentage_w": [0.0],
            },
        },
        "Natural regeneration: forest degradation management",
        "Forest Restoration",
    ),
    convert_scenario_from_minitool_format(
        {
            "fields": {
                "module_start": {
                    "type": [api_models.ModuleType.objects.get(class_name="Grassland")],
                    "fields": {
                        "grassland_management_type_start": list(api_models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded"])),
                    },
                },
                "module_w": {
                    "type": [api_models.ModuleType.objects.get(class_name="ForestManagement")],
                    "fields": {
                        "land_use_type": list(api_models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                        "forest_type": list(api_models.ForestType.objects.filter(name__in=["Natural", "Plantation"])),
                        "forest_condition_type": list(api_models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                    },
                },
            },
        },
        "Enrichment planting in degraded forests: afforestation",
        "Forest Restoration",
    ),
    convert_scenario_from_minitool_format(
        {
            "fields": {
                "module_start": {
                    "type": [api_models.ModuleType.objects.get(class_name="Grassland")],
                    "fields": {
                        "grassland_management_type_start": list(api_models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded"])),
                    },
                },
                "module_w": {
                    "type": [api_models.ModuleType.objects.get(class_name="ForestManagement")],
                    "fields": {
                        "land_use_type": list(api_models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                        "forest_type": list(api_models.ForestType.objects.filter(name__in=["Plantation"])),
                        "forest_condition_type": list(api_models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                    },
                },
            },
        },
        "Infill planting to accelerate recovery: afforestation",
        "Forest Restoration",
    ),
    convert_scenario_from_minitool_format(
        {
            "fields": {
                "land_use_type": list(api_models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                "forest_type": list(api_models.ForestType.objects.filter(name__in=["Natural"])),
                "forest_condition_type": list(api_models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                "average_yearly_degradation_percentage_start": [0.02],
                "average_yearly_degradation_percentage_w": [0.0],
            },
        },
        "Reintroduction of threatened species (e.g. flora, fauna, fungi)",
        "Forest Restoration",
    ),
]

SOIL_LAND_RESTORATION = [
    convert_scenario_from_minitool_format(scenarios.SOIL_REMEDIATION_1, "Soil remediation: Other Land to Set Aside", "Soil and Land Restoration"),
    convert_scenario_from_minitool_format(scenarios.SOIL_REMEDIATION_2, "Soil remediation: Other Land to Grassland (Non-Degraded)", "Soil and Land Restoration"),
    convert_scenario_from_minitool_format(scenarios.SOIL_REMEDIATION_3, "Soil remediation: Grassland", "Soil and Land Restoration"),
    convert_scenario_from_minitool_format(scenarios.TERRACING_1, "Terracing for erosion control and soil conservation: Grassland", "Soil and Land Restoration"),
    convert_scenario_from_minitool_format(scenarios.TERRACING_2, "Terracing for erosion control and soil conservation: Annual Cropland", "Soil and Land Restoration"),
    convert_scenario_from_minitool_format(scenarios.TERRACING_3, "Terracing for erosion control and soil conservation: LUC to some trees (agroforestry)", "Soil and Land Restoration"),
    convert_scenario_from_minitool_format(scenarios.DECOMPACTION_AND_IMPROVEMENT_1, "Decompaction and improvement of degraded soils", "Soil and Land Restoration"),
]

AGROECOLOGICAL_PRODUCTIVE = [
    convert_scenario_from_minitool_format(scenarios.AGROFORESTRY_SYSTEMS_1, "Agroforestry systems with annual and/or perennial crops", "Agroecological and Productive"),
    convert_scenario_from_minitool_format(scenarios.AGROSILVOPASTURAL_SYSTEMS_1, "Agrosilvopastural systems (trees integrated with livestock)", "Agroecological and Productive"),
    convert_scenario_from_minitool_format(scenarios.INTERCROPPING_AND_CROP_ROTATION_1, "Intercropping and crop rotation: annuals", "Agroecological and Productive"),
    convert_scenario_from_minitool_format(scenarios.INTERCROPPING_AND_CROP_ROTATION_2, "Intercropping and crop rotation: perennials", "Agroecological and Productive"),
]

AQUATIC_RESTORATION = [
    convert_scenario_from_minitool_format(scenarios.MANGROVE_REPLANTING_1, "Mangrove Replanting and Natural Recruitment: assuming full restored vegetatin", "Aquatic Restoration"),
    convert_scenario_from_minitool_format(scenarios.MANGROVE_REPLANTING_2, "Mangrove Replanting: and Natural Recruitment: assuming full restoration of hydrology and biomass", "Aquatic Restoration"),
    convert_scenario_from_minitool_format(scenarios.COASTAL_ZONE_STABILIZATION_1, "Coastal Zone Stabilization (e.g. through vegetation or permeable structures)", "Aquatic Restoration"),
    convert_scenario_from_minitool_format(scenarios.RIVERBANK_RESTORATION_1, "Riverbank or Riparian Restoration: Grassland to perennial", "Aquatic Restoration"),
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
            if not scenario:
                continue
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
            if not scenario or not scenario.get("statistics"):
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

    scenarios = [scenario for scenario in (SOIL_LAND_RESTORATION + AGROECOLOGICAL_PRODUCTIVE + AQUATIC_RESTORATION) if scenario is not None]

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

        scenario_filters = scenario.get("filters", {})
        scenario_csv_row_filters = scenario.get("csv_row_filters", {})

        for change in scenario["changes"]:
            module_type = change.get("module_type")
            if not module_type:
                continue

            change_filters = {**scenario_filters, **change.get("filters", {})}
            csv_row_filters = {**scenario_csv_row_filters, **change.get("csv_row_filters", {})}

            def create_flexible_value_query(field_name, value):
                try:
                    float_val = float(value)
                    if float_val.is_integer():
                        return Q(**{field_name: str(int(float_val))}) | Q(**{field_name: str(float_val)})
                    else:
                        return Q(**{field_name: str(float_val)})
                except (ValueError, TypeError):
                    return Q(**{field_name: str(value)})

            change_q = (
                Q(module_type=module_type, field=change["start"]["field"])
                & create_flexible_value_query("from_value", change["start"]["value"])
                & create_flexible_value_query("to_value", change["end"]["value"])
            )

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

            for filter_key, filter_value in change_filters.items():
                if filter_key not in ["region", "climate", "moisture", "soil_type"]:
                    filter_values = filter_value if isinstance(filter_value, list) else [filter_value]
                    filter_q = Q()
                    for val in filter_values:
                        filter_q |= Q(**{f"custom_filters__{filter_key}": val}) | Q(**{f"csv_row_data__{filter_key}": val})
                    change_q &= filter_q

            for filter_key, filter_value in csv_row_filters.items():
                if filter_key in ["module_start_type", "module_w_type"]:
                    continue

                filter_values = filter_value if isinstance(filter_value, list) else [filter_value]
                csv_filter_q = Q()

                prefix = "module_w_" if "w" in filter_key else "module_start_" if "start" in filter_key else ""

                for val in filter_values:
                    csv_filter_q |= Q(**{f"csv_row_data__{prefix}{filter_key}": val})
                change_q &= csv_filter_q

            q_objects |= change_q

        aggregates = models.ChangeRecord.objects.filter(q_objects)
        print(scenario["category"], "-", scenario["name"])

        if aggregates.count() == 0:
            print("No aggregates found")
            print()
            print()
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

    if os.getenv("SAVE_TO_EXCEL"):
        save_to_excel(scenarios)
