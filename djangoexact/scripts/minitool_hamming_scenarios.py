"""
Adapted scenario configurations for minitool_hamming.py

This script adapts the scenario configurations from minitool__compile_scenarios.py
to work with the hamming permutation system. Each scenario is converted to the
appropriate format for the hamming script's MODULE_CONFIGS structure.

Key adaptations:
1. Convert scenario changes to hamming field configurations
2. Create LandUseChange scenarios for module transitions
3. Map scenario filters to hamming field constraints
4. Preserve scenario metadata and categorization
"""

import api.models as models
from typing import Dict, List, Any

# Default filters from the original scenarios
DEFAULT_FILTERS = {
    "soil_type": ["High Activity Clay", "Low Activity Clay", "Sandy"],
}

# =============================================================================
# COASTAL WETLAND SCENARIOS
# =============================================================================

COASTAL_MANGROVE_REPLANTING = {
    "name": "Mangrove Replanting and Natural Recruitment",
    "filename": "coastal_wetland_mangrove_replanting_and_natural_recruitment.json",
    "category": "Aquatic Restoration",
    "fields": {
        "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland", name="Mangrove"),
        "area_w_restored_vegetation_start": [0],
        "area_w_restored_vegetation_w": [1],
    },
    "config_name": "coastal_wetland",
}

COASTAL_ZONE_STABILIZATION = {
    "name": "Coastal Zone Stabilization (e.g. through vegetation or permeable structures)",
    "filename": "coastal_wetland_coastal_zone_stabilization.json",
    "category": "Aquatic Restoration",
    "fields": {
        "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland", name__in=["Mangrove", "Seagrass", "Tidal Marsh"]),
        "area_w_restored_vegetation_start": [0],
        "area_w_restored_vegetation_w": [1],
    },
    "config_name": "coastal_wetland",
}

# =============================================================================
# GRASSLAND SCENARIOS
# =============================================================================

GRASSLAND_REMAINS_GRASSLAND = {
    "name": "Grassland remains Grassland",
    "filename": "grassland_remains_grassland.json",
    "category": "Soil Remediation",
    "fields": {
        "grassland_management_type_start": models.GrasslandManagementType.objects.filter(name__in=["Severely Degraded", "High Intensity Grazing", "Non-Degraded"]),
        "grassland_management_type_w": models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Improved Grassland"]),
        "is_fire_used_start": [True, False],
        "is_fire_used_w": [True, False],
        "fire_periodicity_start": [1],
        "fire_periodicity_w": [1],
        "fire_impact_start": [1, 0],
        "fire_impact_w": [1, 0],
    },
    "config_name": "grassland",
}

GRASSLAND_TERRACING = {
    "name": "Terracing for erosion control and soil conservation",
    "filename": "grassland_terraging_for_erosion_control_and_soil_conservation.json",
    "category": "Soil Conservation",
    "fields": {
        "grassland_management_type_start": models.GrasslandManagementType.objects.filter(name__in=["Severely Degraded", "High Intensity Grazing", "Non-Degraded", "Improved Grassland"]),
        "grassland_management_type_w": models.GrasslandManagementType.objects.filter(name__in=["High Intensity Grazing", "Non-Degraded", "Improved Grassland"]),
        "is_fire_used_start": [True, False],
        "is_fire_used_w": [True, False],
        "fire_periodicity_start": [1],
        "fire_periodicity_w": [1],
        "fire_impact_start": [1, 0],
        "fire_impact_w": [1, 0],
    },
    "config_name": "grassland",
}

# =============================================================================
# ANNUAL CROPLAND SCENARIOS
# =============================================================================

ANNUAL_CROPLAND_DECOMPACTION = {
    "name": "Decompaction and improvement of degraded soils",
    "filename": "annual_cropland_decompaction_and_improvement_of_degraded_soils.json",
    "category": "Soil and Land Restoration",
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
    "config_name": "annual_cropland",
}

ANNUAL_CROPLAND_BETTER_MANAGEMENT = {
    "name": "Better crop management for annual crops",
    "filename": "annual_cropland_better_crop_management_for_annual_crops.json",
    "category": "Intercropping and Crop Rotation",
    "fields": {
        "land_use_type_start": [models.LandUseType.objects.get(name="Default")],
        "land_use_type_w": [models.LandUseType.objects.get(name="Default")],
        "tillage_management_type_start": models.TillageManagementType.objects.filter(name__in=["Full Tillage", "Reduced Tillage"]),
        "tillage_management_type_w": models.TillageManagementType.objects.filter(name__in=["Reduced Tillage", "No Tillage", "No Tillage"]),
        "organic_input_type_start": models.OrganicInputType.objects.filter(name__in=["Low C input", "Medium C input"]),
        "organic_input_type_w": models.OrganicInputType.objects.filter(name__in=["Medium C input", "High C input, no manure", "High C input, no manure"]),
        "residue_management_type_start": models.ResidueManagementType.objects.filter(name__in=["Burned", "Retained", "Exported"]),
        "residue_management_type_w": models.ResidueManagementType.objects.filter(name__in=["Retained", "Exported", "Exported", "Retained"]),
    },
    "config_name": "annual_cropland",
}

# =============================================================================
# FOREST MANAGEMENT SCENARIOS
# =============================================================================

FOREST_NATURAL_REGENERATION = {
    "name": "Natural regeneration: forest degradation management",
    "filename": "forest_management_natural_regeneration_forest_degradation_management.json",
    "category": "Forest Restoration",
    "fields": {
        "land_use_type": models.LandUseType.objects.filter(module_types__name="Forest Management"),
        "forest_type": models.ForestType.objects.filter(name="Natural"),
        "forest_condition_type": models.ForestConditionType.objects.filter(name="Secondary"),
        "average_yearly_degradation_percentage_start": [0.01, 0.02, 0.03],
        "average_yearly_degradation_percentage_w": [0.0, 0.0, 0.0],
    },
    "config_name": "forest_management",
}

FOREST_ENRICHMENT_PLANTING = {
    "name": "Enrichment planting in degraded forests: afforestation",
    "filename": "forest_management_enrichment_planting_in_degraded_forests_afforestation.json",
    "category": "Forest Restoration",
    "fields": {
        "land_use_type": models.LandUseType.objects.filter(module_types__name="Forest Management"),
        "forest_type": models.ForestType.objects.filter(name__in=["Natural", "Plantation"]),
        "forest_condition_type": models.ForestConditionType.objects.filter(name="Secondary"),
        "average_yearly_degradation_percentage_start": [0.01, 0.02, 0.03],
        "average_yearly_degradation_percentage_w": [0.0, 0.0, 0.0],
    },
    "config_name": "forest_management",
}

FOREST_SPECIES_REINTRODUCTION = {
    "name": "Reintroduction of threatened species (e.g. flora, fauna, fungi)",
    "filename": "forest_management_reintroduction_of_threatened_species_flora_fauna_fungi.json",
    "category": "Forest Restoration",
    "fields": {
        "land_use_type": models.LandUseType.objects.filter(module_types__name="Forest Management"),
        "forest_type": models.ForestType.objects.all(),
        "forest_condition_type": models.ForestConditionType.objects.filter(name="Secondary"),
        "average_yearly_degradation_percentage_start": [0.02],
        "average_yearly_degradation_percentage_w": [0.0],
    },
    "config_name": "forest_management",
}

# =============================================================================
# LAND USE CHANGE SCENARIOS
# =============================================================================

NATURAL_REGENERATION_LUC = {
    "name": "Natural regeneration: Afforestation",
    "filename": "land_use_change_natural_regeneration_afforestation.json",
    "category": "Forest Restoration",
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
                "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management")),
                "forest_type": list(models.ForestType.objects.filter(name="Natural")),
                "forest_condition_type": list(models.ForestConditionType.objects.filter(name="Secondary")),
            },
        },
    },
    "config_name": "land_use_change",
}

TERRACING_LUC = {
    "name": "Terracing for erosion control and soil conservation: LUC to some trees",
    "filename": "land_use_change_terraging_for_erosion_control_and_soil_conservation_luc_to_some_trees.json",
    "category": "Soil Conservation",
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
    "config_name": "land_use_change",
}

INFILL_PLANTING_LUC = {
    "name": "Infill planting to accelerate recovery: afforestation",
    "filename": "land_use_change_infill_planting_to_accelerate_recovery_afforestation.json",
    "category": "Forest Restoration",
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
                "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management")),
                "forest_type": list(models.ForestType.objects.filter(name__in=["Natural", "Plantation"])),
                "forest_condition_type": list(models.ForestConditionType.objects.filter(name="Secondary")),
            },
        },
    },
    "config_name": "land_use_change",
}

ENRICHMENT_PLANTING_LUC = {
    "name": "Enrichment planting in degraded forests: forest degradation management",
    "filename": "land_use_change_enrichment_planting_in_degraded_forests_forest_degradation_management.json",
    "category": "Forest Restoration",
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
                "land_use_type": list(models.LandUseType.objects.filter(module_types__name="Forest Management")),
                "forest_type": list(models.ForestType.objects.filter(name="Plantation")),
                "forest_condition_type": list(models.ForestConditionType.objects.filter(name="Secondary")),
            },
        },
    },
    "config_name": "land_use_change",
}

# =============================================================================
# MAIN CONFIGURATION
# =============================================================================

# Updated MODULE_CONFIGS with scenario-based configurations
MODULE_CONFIGS = {
    "CoastalWetland": {
        "subsets": [
            COASTAL_MANGROVE_REPLANTING,  #
            COASTAL_ZONE_STABILIZATION,  #
        ],
        "config_name": "coastal_wetland",
    },
    "Grassland": {
        "subsets": [
            GRASSLAND_REMAINS_GRASSLAND,  #
            GRASSLAND_TERRACING,  #
        ],
        "config_name": "grassland",
    },
    "AnnualCropland": {
        "subsets": [
            ANNUAL_CROPLAND_DECOMPACTION,  #
            ANNUAL_CROPLAND_BETTER_MANAGEMENT,  #
        ],
        "config_name": "annual_cropland",
    },
    "ForestManagement": {
        "subsets": [
            FOREST_NATURAL_REGENERATION,  #
            FOREST_ENRICHMENT_PLANTING,  #
            FOREST_SPECIES_REINTRODUCTION,  #
        ],
        "config_name": "forest_management",
    },
    "LandUseChange": {
        "subsets": [
            # NATURAL_REGENERATION_LUC,
            TERRACING_LUC,
            # INFILL_PLANTING_LUC,
            # ENRICHMENT_PLANTING_LUC,
        ],
        "config_name": "land_use_change",
    },
}

# =============================================================================
# SCENARIO METADATA
# =============================================================================

SCENARIO_METADATA = {
    "coastal_wetland": {
        "additional_information": "Coastal wetland restoration scenarios focusing on mangrove, seagrass, and tidal marsh restoration",
        "assumptions": "Assumes baseline conditions with no restored vegetation and transitions to full restoration",
    },
    "grassland": {
        "additional_information": "Grassland management scenarios including soil remediation and conservation practices",
        "assumptions": "Assumes various degradation levels and management practices for grassland systems",
    },
    "annual_cropland": {
        "additional_information": "Annual cropland management scenarios focusing on soil improvement and better crop management",
        "assumptions": "Assumes transitions from intensive to conservation agriculture practices",
    },
    "forest_management": {
        "additional_information": "Forest restoration scenarios including natural regeneration and enrichment planting",
        "assumptions": "Assumes various levels of forest degradation and restoration interventions",
    },
    "land_use_change": {
        "additional_information": "Land use change scenarios transitioning from grassland to forest or perennial systems",
        "assumptions": "Assumes specific starting conditions and target land use types for transitions",
    },
}


def get_scenario_metadata(category: str) -> Dict[str, str]:
    """Get metadata for a scenario category"""
    return SCENARIO_METADATA.get(
        category,
        {
            "additional_information": "",
            "assumptions": "",
        },
    )


def get_all_scenarios() -> List[Dict[str, Any]]:
    """Get all scenarios as a list for compatibility with the original format"""
    scenarios = []

    for module_name, config in MODULE_CONFIGS.items():
        if "subsets" in config:
            for subset in config["subsets"]:
                scenario = {
                    "name": subset["name"],
                    "category": subset["category"],
                    "module_type": module_name,
                    "metadata": get_scenario_metadata(subset["category"]),
                }
                scenarios.append(scenario)

    return scenarios


if __name__ == "__main__":
    # Print all scenarios for verification
    scenarios = get_all_scenarios()
    print(f"Total scenarios: {len(scenarios)}")
    for scenario in scenarios:
        print(f"- {scenario['category']}: {scenario['name']}")
