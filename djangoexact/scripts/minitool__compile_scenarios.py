import minitool.models as models
import statistics
import math
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


def run(clear: bool = False):
    if clear:
        models.EmissionScenario.objects.all().delete()

    scenarios = [
        {
            "name": "Tillage Reduction",
            "module_type": "Perennial Cropland",
            "filters": {
                "land_use_type": "Default",
            },
            "changes": [
                {
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
                    "start": {
                        "field": "tillage_management_type",
                        "value": "Full Tillage",
                    },
                    "end": {
                        "field": "tillage_management_type",
                        "value": "No Tillage",
                    },
                },
            ],
        },
        {
            "name": "Increasing Carbon Input",
            "module_type": "Annual Cropland",
            "filters": {
                "land_use_type": "Default",
            },
            "changes": [
                {
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
                    "start": {
                        "field": "organic_input_type",
                        "value": "High C input, no manure",
                    },
                    "end": {
                        "field": "organic_input_type",
                        "value": "High C input, with manure",
                    },
                },
                {
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
                    "start": {
                        "field": "organic_input_type",
                        "value": "Medium C input",
                    },
                    "end": {
                        "field": "organic_input_type",
                        "value": "High C input, with manure",
                    },
                },
            ],
        },
        {
            "name": "Stopping Residue Burning",
            "module_type": "Annual Cropland",
            "filters": {
                "land_use_type": "Default",
            },
            "changes": [
                {
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
        {
            "name": "Water management before the cultivation",
            "module_type": "Flooded Rice",
            "filters": {},
            "changes": [
                {
                    "start": {
                        "field": "water_management_type_before_cultivation",
                        "value": "Flooded Pre-Season > 30 D",
                    },
                    "end": {
                        "field": "water_management_type_before_cultivation",
                        "value": "Non Flooded Pre-Season >180 D",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_before_cultivation",
                        "value": "Non Flooded Pre-Season <180 D",
                    },
                    "end": {
                        "field": "water_management_type_before_cultivation",
                        "value": "Non Flooded Pre-Season >180 D",
                    },
                },
            ],
        },
        {
            "name": "Water management after cultivation",
            "module_type": "Flooded Rice",
            "filters": {},
            "changes": [
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Deep Water",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Dry Season (Drought Prone)",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Deep Water",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Wet Season (Regular Rainfed)",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Deep Water",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Continuously Flooded",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Deep Water",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Single Drainage Period",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Deep Water",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Multiple Drainage Periods",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Dry Season (Drought Prone)",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Wet Season (Regular Rainfed)",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Dry Season (Drought Prone)",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Continuously Flooded",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Dry Season (Drought Prone)",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Single Drainage Period",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Dry Season (Drought Prone)",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Multiple Drainage Periods",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Wet Season (Regular Rainfed)",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Irrigated, Continuously Flooded",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Wet Season (Regular Rainfed)",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Single Drainage Period",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Rainfed, Wet Season (Regular Rainfed)",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Multiple Drainage Periods",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Continuously Flooded",
                    },
                    "end": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Single Drainage Period",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Continuously Flooded",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Multiple Drainage Periods",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Single Drainage Period",
                    },
                },
                {
                    "start": {
                        "field": "water_management_type_after_cultivation",
                        "value": "Irrigated, Multiple Drainage Periods",
                    },
                },
            ],
        },
        {
            "name": "Forest degradation management",
            "module_type": "Forest Management",
            "filters": {},
            "changes": [
                {
                    "start": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0,
                    },
                    "end": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0.01,
                    },
                },
                {
                    "start": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0,
                    },
                    "end": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0.02,
                    },
                },
                {
                    "start": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0,
                    },
                    "end": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0.03,
                    },
                },
                {
                    "start": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0,
                    },
                    "end": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0.04,
                    },
                },
                {
                    "start": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0,
                    },
                    "end": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0.05,
                    },
                },
                {
                    "start": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0,
                    },
                    "end": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0.1,
                    },
                },
                {
                    "start": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0,
                    },
                    "end": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0.15,
                    },
                },
                {
                    "start": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0,
                    },
                    "end": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0.2,
                    },
                },
                {
                    "start": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0,
                    },
                    "end": {
                        "field": "average_yearly_degradation_percentage",
                        "value": 0.25,
                    },
                },
            ],
        },
    ]

    for scenario in scenarios:
        models.EmissionScenario.objects.create(
            name=scenario["name"],
            module_type=scenario["module_type"],
            changes=scenario["changes"],
        )

    for scenario in scenarios:
        q_objects = Q()
        for change in scenario["changes"]:
            q_objects |= Q(
                module_type=scenario["module_type"],
                field=change["start"]["field"],
                from_value=change["start"]["value"],
                to_value=change["end"]["value"],
            )

        aggregates = models.ChangeRecord.objects.filter(q_objects)
        print(scenario["name"])

        if aggregates.count() == 0:
            print("No aggregates found")
            continue

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
