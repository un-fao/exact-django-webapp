from api import models

# =============================================================================
# FOREST RESTORATION SCENARIOS
# =============================================================================

NATURAL_REGENERATION_1 = {
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

# Same as ASSISTED_NATURAL_REGENERATION_2
NATURAL_REGENERATION_2 = {
    "filename": "forest_degradation_management",
    "fields": {
        "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
        "forest_type": list(models.ForestType.objects.filter(name__in=["Natural"])),
        "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
        "average_yearly_degradation_percentage_start": [0.01, 0.02, 0.03],
        "average_yearly_degradation_percentage_w": [0.0],
    },
}

# TODO: Needs tier2 values before computation
ASSISTED_NATURAL_REGENERATION_1 = {
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

# TODO: Needs tier2 values before computation
DIRECT_PLANTING_1 = {
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
                "forest_type": list(models.ForestType.objects.filter(name__in=["Natural"])),
                "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
            },
        },
    },
}

ENRICHMENT_PLANTING_IN_DEGRADED_FORESTS_1 = {
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
                "forest_type": list(models.ForestType.objects.filter(name__in=["Natural", "Plantation"])),
                "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
            },
        },
    },
}

# TODO: Needs tier2 values before computation
ENRICHMENT_PLANTING_IN_DEGRADED_FORESTS_2 = {
    "filename": "enrichment_planting_in_degraded_forests_2",
    "fields": {
        "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
        "forest_type": list(models.ForestType.objects.filter(name__in=["Plantation", "Natural"])),
        "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
        "average_yearly_degradation_percentage_start": [0.01, 0.02, 0.03],
        "average_yearly_degradation_percentage_w": [0.0],
    },
}

INFILL_PLANTING_TO_ACCELERATE_RECOVERY_1 = {
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

# TODO: Needs tier2 values before computation
INFILL_PLANTING_TO_ACCELERATE_RECOVERY_2 = {
    "filename": "infill_planting_to_accelerate_recovery_2",
    "fields": {
        "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management").all()),
        "forest_type": list(models.ForestType.objects.filter(name__in=["Natural"])),
        "forest_condition_type": list(models.ForestConditionType.objects.filter(name__in=["Secondary"])),
        "average_yearly_degradation_percentage_start": [0.01, 0.02, 0.03],
        "average_yearly_degradation_percentage_w": [0.0],
    },
}

REINTRODUCTION_OF_THREATENED_SPECIES_1 = {
    "filename": "reintroduction_of_threatened_species_1",
    "fields": {
        "land_use_type": models.LandUseType.objects.filter(module_types__name="Forest Management"),
        "forest_type": list(models.ForestType.objects.filter(name__in=["Natural"])),
        "forest_condition_type": models.ForestConditionType.objects.filter(name="Secondary"),
        "average_yearly_degradation_percentage_start": [0.02],
        "average_yearly_degradation_percentage_w": [0.0],
    },
}

# =============================================================================
# SOIL & LAND RESTORATION SCENARIOS
# =============================================================================

# TODO: Needs tier2 values before computation
SOIL_AMENDMENTS_1 = {
    "AnnualCropland": {
        "filename": "soil_amendments__annual_cropland_1",
        "fields": {
            "land_use_type_start": list(models.LandUseType.objects.filter(name__in=["Default"])),
            "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage"])),
            "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"])),
            "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input", "High C input, no manure"])),
            "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure", "High C input, with manure"])),
            "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
            "residue_management_type_w": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
        },
    },
    "Input": {
        "filename": "soil_amendments__input_1",
        "fields": {
            # TODO: Needs tier2 value related to biochar
            # "input_type": list(models.InputType.objects.filter(name__in=["Organic Input"])),
            "value_start": [0],
            "value_w": [1],
        },
    },
}

# TODO: Needs tier2 values before computation
SOIL_AMENDMENTS_2 = {
    "Grassland": {
        "filename": "soil_amendments__grassland_2",
        "fields": {
            "grassland_management_type_start": list(
                models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Severely Degraded", "Improved With Medium Inputs", "Improved Grassland"])
            ),
            "grassland_management_type_w": list(
                models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Improved With Medium Inputs", "Improved Grassland", "Improved With High Inputs"])
            ),
        },
    },
    "Input": {
        "filename": "soil_amendments__input_2",
        "fields": {
            # TODO: Needs tier2 value related to biochar
            # "input_type": list(models.InputType.objects.filter(name__in=["Organic Input"])),
            "value_start": [0],
            "value_w": [1],
        },
    },
}

SOIL_REMEDIATION_1 = {
    "filename": "soil_remediation_1",
    "fields": {
        "module_start": {
            "type": [models.ModuleType.objects.get(class_name="OtherLand")],
            "fields": {
                "is_degraded_land_start": [False],
                "is_degraded_land_w": [False],
            },
        },
    },
    "module_w": {
        "type": [models.ModuleType.objects.get(class_name="SetAside")],
        "fields": {
            "is_set_aside_start": [False],
            "is_set_aside_w": [True],
        },
    },
}

SOIL_REMEDIATION_2 = {
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
}

SOIL_REMEDIATION_3 = {
    "filename": "soil_remediation_3",
    "fields": {
        "module_start": {
            "type": [models.ModuleType.objects.get(class_name="OtherLand")],
            "fields": {
                "is_degraded_land_start": [False],
                "is_degraded_land_w": [False],
            },
        },
    },
    "module_w": {
        "type": [models.ModuleType.objects.get(class_name="Grassland")],
        "fields": {
            "grassland_management_type_start": models.GrasslandManagementType.objects.filter(name__in=["Severely Degraded", "High Intensity Grazing", "Non-Degraded"]),
            "grassland_management_type_w": models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Improved Grassland"]),
        },
    },
}

TERRACING_1 = {
    "Grassland": {
        "filename": "terracing_1",
        "fields": {
            "grassland_management_type_start": models.GrasslandManagementType.objects.filter(name__in=["Severely Degraded", "High Intensity Grazing", "Non-Degraded", "Improved Grassland"]),
            "grassland_management_type_w": models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Improved Grassland"]),
        },
    },
}

TERRACING_2 = {
    "AnnualCropland": {
        "filename": "terracing_2",
        "fields": {
            "land_use_type_start": list(models.LandUseType.objects.filter(name__in=["Default"])),
            "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage"])),
            "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"])),
            "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input"])),
            "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure", "High C input, with manure"])),
            "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
            "residue_management_type_w": list(models.ResidueManagementType.objects.filter(name__in=["Exported"])),
        },
    },
}

TERRACING_3 = {
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
                "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"])),
                "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure"])),
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
            "tillage_management_type_start": models.TillageManagementType.objects.filter(name="Full Tillage"),
            "tillage_management_type_w": models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"]),
            "organic_input_type_start": models.OrganicInputType.objects.filter(name="Low C input"),
            "organic_input_type_w": models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure", "High C input, with manure"]),
            "residue_management_type_start": models.ResidueManagementType.objects.filter(name="Burned"),
            "residue_management_type_w": models.ResidueManagementType.objects.filter(name__in=["Retained", "Exported"]),
        },
    },
}

# =============================================================================
# AGROCOLOGICAL AND PRODUCTIVE SCENARIOS
# =============================================================================

BETTER_CROP_MANAGEMENT_FOR_ANNUAL_CROPS_1 = {
    "filename": "better_crop_management_for_annual_crops_1",
    "fields": {
        "land_use_type_start": [models.LandUseType.objects.get(name="Default")],
        "land_use_type_w": [models.LandUseType.objects.get(name="Default")],
    },
}

AGROFORESTRY_SYSTEMS_1 = {
    "LandUseChange": {
        "filename": "agroforestry_systems_1",
        "fields": {
            "module_start": {
                "type": [models.ModuleType.objects.get(class_name="AnnualCropland")],
                "fields": {
                    "land_use_type_start": list(models.LandUseType.objects.filter(name__in=["Default"])),
                    "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage", "No Tillage"])),
                    "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "High C input, no manure"])),
                    "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Burned"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="PerennialCropland")],
                "fields": {
                    "land_use_type_w": list(models.LandUseType.objects.filter(name__in=["Default", "Alley Cropping", "Hedgerow", "Silvoarable", "Multistrata", "Shaded Perennial", "Orchard"])),
                    "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage", "No Tillage"])),
                    "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input", "High C input, no manure"])),
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
                    "tillage_management_type_start": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage", "No Tillage"])),
                    "organic_input_type_start": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input", "High C input, no manure", "High C input, with manure"])),
                    "residue_management_type_start": list(models.ResidueManagementType.objects.filter(name__in=["Burned"])),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="PerennialCropland")],
                "fields": {
                    "land_use_type_w": list(models.LandUseType.objects.filter(name__in=["Silvopasture", "Parkland"])),
                    "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage", "No Tillage"])),
                    "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input", "High C input, no manure", "High C input, with manure"])),
                },
            },
        },
    },
}

INTERCROPPING_AND_CROP_ROTATION_1 = {
    "AnnualCropland": {
        "filename": "intercropping_and_crop_rotation_1",
        "fields": {
            "land_use_type_start": [models.LandUseType.objects.get(name="Default")],
            "land_use_type_w": [models.LandUseType.objects.get(name="Default")],
            "tillage_management_type_start": models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage"]),
            "tillage_management_type_w": models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"]),
            "organic_input_type_start": models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input", "High C input, no manure"]),
            "organic_input_type_w": models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure"]),
            "residue_management_type_start": models.ResidueManagementType.objects.filter(name__in=["Burned", "Retained", "Exported"]),
            "residue_management_type_w": models.ResidueManagementType.objects.filter(name__in=["Retained", "Exported", "Burned"]),
        },
    },
}

INTERCROPPING_AND_CROP_ROTATION_2 = {
    "filename": "intercropping_and_crop_rotation_2",
    "fields": {
        "is_fire_used_w": [True, False],  # TODO: Modify LandUseChange Processor to handle this field
        "module_start": {
            "type": [models.ModuleType.objects.get(class_name="AnnualCropland")],
            "fields": {
                "land_use_type_start": [models.LandUseType.objects.get(name="Default")],
                "tillage_management_type_start": models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage"]),
                "organic_input_type_start": models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input", "High C input, no manure"]),
                "residue_management_type_start": models.ResidueManagementType.objects.filter(name__in=["Burned", "Retained", "Exported"]),
            },
        },
        "module_w": {
            "type": [models.ModuleType.objects.get(class_name="PerennialCropland")],
            "fields": {
                "land_use_type_w": list(models.LandUseType.objects.filter(name__in=["Alley Cropping"])),
                "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage"])),
                "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure", "High C input, with manure"])),
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
        },
    },
}

MANGROVE_REPLANTING_2 = {
    "CoastalWetland": {
        "filename": "mangrove_replanting_2",
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland", name__in=["Mangrove", "Seagrass", "Tidal Marsh"]),
            "area_not_drained_or_rewetted_start": [0],
            "area_not_drained_or_rewetted_w": [1],
        },
    },
}

COASTAL_ZONE_STABILIZATION_1 = {
    "CoastalWetland": {
        "filename": "coastal_zone_stabilization_1",
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland", name__in=["Mangrove", "Seagrass", "Tidal Marsh"]),
            "area_not_drained_or_rewetted_start": [0],
            "area_not_drained_or_rewetted_w": [1],
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
                    "grassland_management_type_start": models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Severely Degraded"]),
                },
            },
            "module_w": {
                "type": [models.ModuleType.objects.get(class_name="PerennialCropland")],
                "fields": {
                    "land_use_type_w": list(models.LandUseType.objects.filter(module_types__name="Perennial Cropland", name__in=["Default", "Alley Cropping", "Hedgerow", "Silvoarable", "Orchard"])),
                    "tillage_management_type_w": list(models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage", "No Tillage"])),
                    "organic_input_type_w": list(models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input", "High C input, no manure"])),
                },
            },
        },
    },
}
