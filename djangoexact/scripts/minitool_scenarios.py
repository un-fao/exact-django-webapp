from api import models
import csv
from pathlib import Path

# =============================================================================
# FOREST RESTORATION SCENARIOS
# =============================================================================

FOREST_T2_CSV_PATH = Path(__file__).resolve().parent / "forest_t2.csv"


def _load_forest_t2_rows():
    if not FOREST_T2_CSV_PATH.exists():
        return []

    with FOREST_T2_CSV_PATH.open() as csv_file:
        reader = csv.DictReader(csv_file)
        return [row for row in reader if row.get("climate") and row.get("region")]


_FOREST_T2_ROWS = _load_forest_t2_rows()
_FOREST_T2_CLIMATES = list(models.Climate.objects.filter(name__in={row["climate"] for row in _FOREST_T2_ROWS}))
_FOREST_T2_REGIONS = list(models.Region.objects.filter(name__in={row["region"] for row in _FOREST_T2_ROWS}))


def _create_forest_t2_subsets():
    """Create subsets from forest_t2.csv, one per unique combination with tier 2 values"""
    if not _FOREST_T2_ROWS:
        return []

    subsets = []
    seen_combinations = {}

    for row in _FOREST_T2_ROWS:
        key = (
            row.get("climate"),
            row.get("land_use_type"),
            row.get("region"),
            row.get("forest_condition_type"),
            row.get("forest_type"),
        )

        if not all(key):
            continue

        if key in seen_combinations:
            continue

        seen_combinations[key] = True

        try:
            land_use_type = models.LandUseType.objects.filter(module_types__name="Forest Management", name=row["land_use_type"]).first()
            forest_type = models.ForestType.objects.filter(name=row["forest_type"]).first()
            forest_condition_type = models.ForestConditionType.objects.filter(name=row["forest_condition_type"]).first()
            climate = models.Climate.objects.filter(name=row["climate"]).first()
            region = models.Region.objects.filter(name=row["region"]).first()

            if not all([land_use_type, forest_type, forest_condition_type, climate, region]):
                continue

            def safe_float(val):
                try:
                    return float(val) if val else None
                except (ValueError, TypeError):
                    return None

            subset = {
                "filename": f"forest_management_t2_{row['climate']}_{row['land_use_type']}_{row['region']}_{row['forest_condition_type']}_{row['forest_type']}".replace(" ", "_").replace(",", ""),
                "fields": {
                    "land_use_type": [land_use_type],
                    "forest_type": [forest_type],
                    "forest_condition_type": [forest_condition_type],
                    "average_yearly_degradation_percentage_start": [0.01, 0.02, 0.03],
                    "average_yearly_degradation_percentage_w": [0.0],
                },
                "static_fields": {
                    "agb_max_t2_start": None,
                    "agb_max_t2_w": safe_float(row.get("agb_max_t2")),
                    "agb_growth_rate_le_20_yrs_t2_start": None,
                    "agb_growth_rate_le_20_yrs_t2_w": safe_float(row.get("agb_growth_rate_le_20_yrs_t2")),
                    "agb_growth_rate_gt_20_yrs_t2_start": None,
                    "agb_growth_rate_gt_20_yrs_t2_w": safe_float(row.get("agb_growth_rate_gt_20_yrs_t2")),
                    "bgb_max_t2_start": None,
                    "bgb_max_t2_w": safe_float(row.get("bgb_max_t2")),
                    "bgb_growth_rate_le_20_yrs_t2_start": None,
                    "bgb_growth_rate_le_20_yrs_t2_w": safe_float(row.get("bgb_growth_rate_le_20_yrs_t2")),
                    "bgb_growth_rate_gt_20_yrs_t2_start": None,
                    "bgb_growth_rate_gt_20_yrs_t2_w": safe_float(row.get("bgb_growth_rate_gt_20_yrs_t2")),
                    "litter_t2_start": None,
                    "litter_t2_w": safe_float(row.get("litter_t2")),
                    "deadwood_t2_start": None,
                    "deadwood_t2_w": safe_float(row.get("deadwood_t2")),
                },
                "environment_filters": {
                    "climates": [climate],
                    "regions": [region],
                },
            }
            subsets.append(subset)
        except Exception:
            continue

    return subsets


_FOREST_T2_SUBSETS = _create_forest_t2_subsets()

NATURAL_REGENERATION_1 = {
    "LandUseChange": {
        "filename": "afforestation",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="Grassland")],
                "fields": {
                    "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["Non-Degraded", "High Intensity Grazing"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="ForestManagement")],
                "fields": {
                    "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                    "forest_type": list(models.ForestType.objects.filter(name__in=["Natural"])),
                    "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                },
            },
        },
    }
}

# Same as ASSISTED_NATURAL_REGENERATION_2
NATURAL_REGENERATION_2 = {
    "ForestManagement": {
        "filename": "forest_degradation_management",
        "fields": {
            "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
            "forest_type": list(models.ForestType.objects.filter(name__in=["Natural"])),
            "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
            "average_yearly_degradation_percentage_start": [0.01, 0.02, 0.03],
            "average_yearly_degradation_percentage_w": [0.0],
        },
    },
}

FOREST_T2 = {
    "ForestManagement": {
        "subsets": _FOREST_T2_SUBSETS
        if _FOREST_T2_SUBSETS
        else [
            {
                "filename": "forest_management_t2",
                "fields": {
                    "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                    "forest_type": list(models.ForestType.objects.all()),
                    "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                    "average_yearly_degradation_percentage_start": [0.0],
                    "average_yearly_degradation_percentage_w": [0.0],
                },
            }
        ],
    }
}

ASSISTED_NATURAL_REGENERATION_1 = {
    "LandUseChange": {
        "filename": "afforestation",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="Grassland")],
                "fields": {
                    "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["Non-Degraded", "High Intensity Grazing"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="ForestManagement")],
                "fields": {
                    "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                    "forest_type": list(models.ForestType.objects.filter(name__in=["Natural"])),
                    "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                },
            },
        },
    }
}

DIRECT_PLANTING_1 = {
    "LandUseChange": {
        "filename": "direct_planting_1",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="Grassland")],
                "fields": {
                    "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["Non-Degraded", "High Intensity Grazing"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="ForestManagement")],
                "fields": {
                    "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                    "forest_type": list(models.ForestType.objects.filter(name__in=["Plantation"])),
                    "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                },
            },
        },
    }
}

ENRICHMENT_PLANTING_IN_DEGRADED_FORESTS_1 = {
    "LandUseChange": {
        "filename": "enrichment_planting_in_degraded_forests_1",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="Grassland")],
                "fields": {
                    "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="ForestManagement")],
                "fields": {
                    "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                    "forest_type": list(models.ForestType.objects.filter(name__in=["Plantation"])),
                    "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                },
            },
        },
    }
}

# TODO: Needs tier2 values before computation
ENRICHMENT_PLANTING_IN_DEGRADED_FORESTS_2 = {
    "ForestManagement": {
        "filename": "enrichment_planting_in_degraded_forests_2",
        "fields": {
            "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
            "forest_type": list(models.ForestType.objects.filter(name__in=["Natural"])),
            "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
            "average_yearly_degradation_percentage_start": [0.01, 0.02, 0.03],
            "average_yearly_degradation_percentage_w": [0.0],
        },
    }
}


INFILL_PLANTING_TO_ACCELERATE_RECOVERY_1 = {
    "LandUseChange": {
        "filename": "infill_planting_to_accelerate_recovery",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="Grassland")],
                "fields": {
                    "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="ForestManagement")],
                "fields": {
                    "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
                    "forest_type": list(models.ForestType.objects.filter(name__in=["Plantation"])),
                    "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
                },
            },
        },
    }
}

# TODO: Needs tier2 values before computation
INFILL_PLANTING_TO_ACCELERATE_RECOVERY_2 = {
    "ForestManagement": {
        "filename": "infill_planting_to_accelerate_recovery_2",
        "fields": {
            "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
            "forest_type": list(models.ForestType.objects.filter(name__in=["Natural"])),
            "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
            "average_yearly_degradation_percentage_start": [0.01, 0.02, 0.03],
            "average_yearly_degradation_percentage_w": [0.0],
        },
    }
}

REINTRODUCTION_OF_THREATENED_SPECIES_1 = {
    "ForestManagement": {
        "filename": "reintroduction_of_threatened_species_1",
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Forest Management"),
            "forest_type": list(models.ForestType.objects.filter(name__in=["Natural"])),
            "forest_condition_type": models.ForestConditionType.objects.filter(name="Secondary"),
            "average_yearly_degradation_percentage_start": [0.02],
            "average_yearly_degradation_percentage_w": [0.0],
        },
    }
}

# =============================================================================
# SOIL & LAND RESTORATION SCENARIOS
# =============================================================================

# TODO: Check if tier2 is passed correctly
SOIL_AMENDMENTS_1 = {
    "AnnualCropland": {
        "filename": "soil_amendments__annual_cropland_1",
        "fields": {
            "land_use_type_start": list(models.LandUseType.objects.filter(name__in=["Default"])),
            "land_use_type_w": list(models.LandUseType.objects.filter(name__in=["Default"])),
            "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage"])),
            "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"])),
            "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input"])),
            "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure", "High C input, with manure"])),
            "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
            "residue_management_type_w": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
        },
    },
    "Input": {
        "filename": "soil_amendments__input_1",
        "fields": {
            "input_type": list(models.InputType.objects.filter(name__in=["Compost", "User Defined"])),
            "value_start": [0],
            "value_w": [10],
            "co2_emissions_t2": [0.0051],
        },
    },
}

# TODO: Needs tier2 values before computation
SOIL_AMENDMENTS_2 = {
    "Grassland": {
        "filename": "soil_amendments__grassland_2",
        "fields": {
            "grassland_management_type_start": list(
                models.GrasslandManagementType.objects.filter(name__in=["Severely Degraded", "High Intensity Grazing", "Non-Degraded", "Improved Grassland", "Improved With Medium Inputs"])
            ),
            "grassland_management_type_w": list(
                models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Improved With Medium Inputs", "Improved Grassland", "Improved With High Inputs"])
            ),
            "is_fire_used_start": [False],
            "is_fire_used_w": [False],
            "fire_periodicity_start": [0],
            "fire_periodicity_w": [0],
            "fire_impact_start": [0],
            "fire_impact_w": [0],
        },
    },
    "Input": {
        "filename": "soil_amendments__input_2",
        "fields": {
            "input_type": list(models.InputType.objects.filter(name__in=["Compost"])),
            "value_start": [0],
            "value_w": [10],
        },
    },
}

SOIL_REMEDIATION_1 = {
    "LandUseChange": {
        "filename": "soil_remediation_1",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="OtherLand")],
                "fields": {
                    "is_degraded_land_start": [False],
                    "is_degraded_land_w": [False],
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="SetAside")],
                "fields": {
                    "is_set_aside_start": [False],
                    "is_set_aside_w": [True],
                },
            },
        },
    },
}

SOIL_REMEDIATION_2 = {
    "LandUseChange": {
        "filename": "soil_remediation_2",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="OtherLand")],
                "fields": {
                    "is_degraded_land_start": [False],
                    "is_degraded_land_w": [False],
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="Grassland")],
                "fields": {
                    "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["Non-Degraded"])),
                    "grassland_management_type_w": list(models.GrasslandManagementType.objects.filter(name__in=["Non-Degraded"])),
                },
            },
        },
    },
}

SOIL_REMEDIATION_3 = {
    "Grassland": {
        "filename": "soil_remediation_3",
        "fields": {
            "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["Severely Degraded", "High Intensity Grazing"])),
            "grassland_management_type_w": list(models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Improved Grassland"])),
        },
    },
}

TERRACING_1 = {
    "Grassland": {
        "filename": "terracing_1",
        "fields": {
            "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["Severely Degraded", "High Intensity Grazing", "Non-Degraded"])),
            "grassland_management_type_w": list(models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Improved Grassland"])),
        },
    },
}

TERRACING_2 = {
    "AnnualCropland": {
        "filename": "terracing_2",
        "fields": {
            "land_use_type_start": list(models.LandUseType.objects.filter(name__in=["Default"])),
            "land_use_type_w": list(models.LandUseType.objects.filter(name__in=["Default"])),
            "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage"])),
            "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"])),
            "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input"])),
            "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure"])),
            "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
            "residue_management_type_w": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
        },
    },
}

TERRACING_3 = {
    "LandUseChange": {
        "filename": "terracing_3",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="Grassland")],
                "fields": {
                    "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["Severely Degraded", "High Intensity Grazing", "Non-Degraded"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="PerennialCropland")],
                "fields": {
                    "land_use_type_w": list(models.LandUseType.objects.filter(module_types__name="Perennial Cropland", name__in=["Perennial Fallow", "Orchard", "Short Rotation Coppice", "Hedgerow"])),
                    "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage"])),
                    "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input"])),
                },
            },
        },
    },
}

DECOMPACTION_AND_IMPROVEMENT_1 = {
    "AnnualCropland": {
        "filename": "decompaction_and_improvement_1",
        "fields": {
            "land_use_type_start": [models.LandUseType.objects.get(name="Default")],
            "land_use_type_w": [models.LandUseType.objects.get(name="Default")],
            "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage"])),
            "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"])),
            "organic_input_type_start": list(models.OrganicInputType.objects.filter(name="Low C input")),
            "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input"])),
            "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name="Exported")),
            "residue_management_type_w": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
        },
    },
}

# =============================================================================
# AGROCOLOGICAL AND PRODUCTIVE SCENARIOS
# =============================================================================

AGROFORESTRY_SYSTEMS_1 = {
    "LandUseChange": {
        "filename": "agroforestry_systems_1",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="AnnualCropland")],
                "fields": {
                    "land_use_type_start": list(models.LandUseType.objects.filter(name__in=["Default"])),
                    "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage", "No Tillage"])),
                    "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input"])),
                    "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Burned"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="PerennialCropland")],
                "fields": {
                    "land_use_type_w": list(models.LandUseType.objects.filter(name__in=["Default", "Alley Cropping", "Hedgerow", "Silvoarable", "Multistrata", "Shaded Perennial", "Orchard"])),
                    "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage", "No Tillage"])),
                    "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure"])),
                },
            },
        },
    }
}

AGROSILVOPASTURAL_SYSTEMS_1 = {
    "LandUseChange": {
        "filename": "agrosilvopastural_systems_1",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="AnnualCropland")],
                "fields": {
                    "land_use_type_start": list(models.LandUseType.objects.filter(name__in=["Default"])),
                    "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage"])),
                    "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input"])),
                    "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Burned"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="PerennialCropland")],
                "fields": {
                    "land_use_type_w": list(models.LandUseType.objects.filter(name__in=["Silvopasture", "Parkland"])),
                    "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"])),
                    "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure"])),
                },
            },
        },
    },
}

INTERCROPPING_AND_CROP_ROTATION_1 = {
    "AnnualCropland": {
        "filename": "intercropping_and_crop_rotation_1",
        "fields": {
            "land_use_type_start": list(models.LandUseType.objects.filter(name__in=["Default"])),
            "land_use_type_w": list(models.LandUseType.objects.filter(name__in=["Default"])),
            "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage"])),
            "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"])),
            "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input"])),
            "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure"])),
            "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Burned", "Exported"])),
            "residue_management_type_w": list(models.ResidueManagementType.objects.filter(name__in=["Retained", "Exported"])),
        },
    },
}

INTERCROPPING_AND_CROP_ROTATION_2 = {
    "LandUseChange": {
        "filename": "intercropping_and_crop_rotation_2",
        "fields": {
            "is_fire_used_w": [True, False],  # TODO: Modify LandUseChange Processor to handle this field
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="AnnualCropland")],
                "fields": {
                    "land_use_type_start": list(models.LandUseType.objects.filter(name__in=["Default"])),
                    "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage"])),
                    "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input"])),
                    "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Burned", "Retained", "Exported"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="PerennialCropland")],
                "fields": {
                    "land_use_type_w": list(models.LandUseType.objects.filter(name__in=["Alley Cropping"])),
                    "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"])),
                    "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure"])),
                },
            },
        },
    },
}

# =============================================================================
# AQUATIC RESTORATIONSCENARIOS
# =============================================================================

MANGROVE_REPLANTING_1 = {
    "CoastalWetland": {
        "filename": "mangrove_replanting_1",
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland", name="Mangrove"),
            "area_w_restored_vegetation_start": [0],
            "area_w_restored_vegetation_w": [1],
            # "area_not_drained_or_rewetted_start": [0],
            # "area_not_drained_or_rewetted_w": [0],
            # "area_under_drainage_start": [0],
            # "area_under_drainage_w": [0],
        },
    },
}

MANGROVE_REPLANTING_2 = {
    "CoastalWetland": {
        "filename": "mangrove_replanting_2",
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland", name__in=["Mangrove"]),
            # "area_w_restored_vegetation_start": [0],
            "area_w_restored_vegetation_w": [1],
            "area_not_drained_or_rewetted_start": [0],
            "area_not_drained_or_rewetted_w": [1],
            "area_under_drainage_start": [1],  # Rewetting
            # "area_under_drainage_w": [0],
        },
    },
}

COASTAL_ZONE_STABILIZATION_1 = {
    "CoastalWetland": {
        "filename": "coastal_zone_stabilization_1",
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland", name__in=["Mangrove", "Seagrass", "Tidal Marsh"]),
            # "area_w_restored_vegetation_start": [0],
            "area_w_restored_vegetation_w": [1],
            # "area_not_drained_or_rewetted_start": [0],
            # "area_not_drained_or_rewetted_w": [0],
            "area_under_drainage_start": [1],  # Rewetting
            # "area_under_drainage_w": [0],
        },
    },
}

RIVERBANK_RESTORATION_1 = {
    "LandUseChange": {
        "filename": "riverbank_restoration_1",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="Grassland")],
                "fields": {
                    "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Severely Degraded"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="PerennialCropland")],
                "fields": {
                    "land_use_type_w": list(models.LandUseType.objects.filter(module_types__name="Perennial Cropland", name__in=["Alley Cropping", "Hedgerow", "Silvoarable", "Orchard"])),
                    "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage", "No Tillage"])),
                    "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input", "High C input, no manure"])),
                },
            },
        },
    },
}

WETLAND_HYDROLOGICAL_RESTORATION_1 = {
    "AnnualCropland": {
        "filename": "wetland_hydrological_restoration_1__annual_cropland",
        "fields": {
            "land_use_type_start": list(models.LandUseType.objects.filter(name__in=["Default", "Alley Cropping"])),
            "land_use_type_w": list(models.LandUseType.objects.filter(name__in=["Default", "Alley Cropping"])),
            "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage"])),
            "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage"])),
            "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input"])),
            "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Low C input"])),
            "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
            "residue_management_type_w": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
        },
        "organic_soil": {
            "fields": {
                "drainage_area_start": [1],
                "drainage_area_w": [0],
                "area_not_drained_start": [0],
                "area_not_drained_w": [1],
            },
        },
    },
}

WETLAND_HYDROLOGICAL_RESTORATION_2 = {
    "Grassland": {
        "filename": "wetland_hydrological_restoration_2__grassland",
        "fields": {
            "grassland_management_type_start": list(models.GrasslandManagementType.objects.filter(name__in=["Non-Degraded", "Severely Degraded"])),
            "grassland_management_type_w": list(models.GrasslandManagementType.objects.filter(name__in=["Non-Degraded", "Severely Degraded"])),
        },
        "organic_soil": {
            "fields": {
                "drainage_area_start": [1],
                "drainage_area_w": [0],
                "area_not_drained_start": [0],
                "area_not_drained_w": [1],
            },
        },
    },
}
