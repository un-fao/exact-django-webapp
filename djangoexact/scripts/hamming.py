from itertools import product
import api.models as models
from .minitool import ClimateMoistureValidator, SoilOrganicCarbonValidator

def domains_from_fields(fields: dict):
    # pair *_start with *_w and get their (same) domain
    pairs = []
    single_fields = []
    
    # Process fields with _start/_w pattern
    for k in sorted(fields):
        if k.endswith('_start'):
            base = k[:-6]
            s = f'{base}_start'
            w = f'{base}_w'
            if w in fields:
                dom = list(fields[s])  # materialize QuerySet once
                pairs.append((base, s, w, dom))
    
    # Process single fields that don't have _start/_w pattern
    for k in sorted(fields):
        if not k.endswith('_start') and not k.endswith('_w') and not k.endswith('_wo'):
            # Check if this field doesn't have a corresponding _start/_w version
            base_start = f'{k}_start'
            base_w = f'{k}_w'
            if base_start not in fields and base_w not in fields:
                dom = list(fields[k])  # materialize QuerySet once
                single_fields.append((k, dom))
    
    return pairs, single_fields  # return both paired and single fields

def hamming_shell_rows(fields: dict):
    """
    fields: your dict of columns -> iterable/QuerySet
    Yields dict rows where exactly one field differs from its baseline value.
    For paired fields (*_start/*_w), we vary the _w value while keeping _start constant.
    For single fields, we iterate through all possible values.
    """
    pairs, single_fields = domains_from_fields(fields)
    
    # Get all domains for baseline assignment
    paired_bases = [dom for (_, _, _, dom) in pairs]
    single_bases = [dom for (_, dom) in single_fields]
    all_bases = paired_bases + single_bases

    # iterate baseline assignment (choose ONE value per field)
    for baseline_vals in product(*all_bases):
        # Split baseline values between paired and single fields
        paired_baseline_vals = baseline_vals[:len(pairs)]
        single_baseline_vals = baseline_vals[len(pairs):]
        
        # map: field -> chosen baseline value
        paired_base_map = {pairs[i][0]: paired_baseline_vals[i] for i in range(len(pairs))}
        single_base_map = {single_fields[i][0]: single_baseline_vals[i] for i in range(len(single_fields))}

        # For each paired field, flip its _w to an alternative value
        for i, (base, s_col, w_col, dom) in enumerate(pairs):
            s_val = paired_base_map[base]
            for alt in dom:
                if alt == s_val:
                    continue  # must differ
                row = {}
                # fill all pairs: start = baseline, w = baseline (same)
                for (b, s, w, _) in pairs:
                    row[s] = paired_base_map[b]
                    row[w] = paired_base_map[b]
                # fill all single fields with baseline values
                for field_name, baseline_val in single_base_map.items():
                    row[field_name] = baseline_val
                # flip exactly one paired field
                row[w_col] = alt
                yield row
        
        # For each single field, vary its value while keeping others at baseline
        for i, (field_name, dom) in enumerate(single_fields):
            baseline_val = single_base_map[field_name]
            for alt in dom:
                if alt == baseline_val:
                    continue  # must differ
                row = {}
                # fill all pairs with baseline values (start = w = baseline)
                for (b, s, w, _) in pairs:
                    row[s] = paired_base_map[b]
                    row[w] = paired_base_map[b]
                # fill all single fields with baseline values
                for other_field_name, other_baseline_val in single_base_map.items():
                    row[other_field_name] = other_baseline_val
                # flip exactly one single field
                row[field_name] = alt
                yield row

def expected_count(fields: dict) -> int:
    pairs, single_fields = domains_from_fields(fields)
    
    # Get sizes for paired and single fields
    paired_sizes = [len(dom) for (_, _, _, dom) in pairs]
    single_sizes = [len(dom) for (_, dom) in single_fields]
    all_sizes = paired_sizes + single_sizes
    
    # Calculate baseline combinations
    prod = 1
    for s in all_sizes:
        prod *= s
    
    # Calculate variations for each field type
    paired_variations = sum(s-1 for s in paired_sizes)
    single_variations = sum(s-1 for s in single_sizes)
    total_variations = paired_variations + single_variations
    
    return prod * total_variations


annual_cropland_climate_moistures = ClimateMoistureValidator.get_valid_combinations([models.LandUseType.objects.get(name="Default")], models)
annual_cropland_soil_types = SoilOrganicCarbonValidator.get_valid_combinations(annual_cropland_climate_moistures, models.SoilType.objects.filter(is_coastal=False, active=True).all(), models)
annual_cropland_regions = models.Region.objects.filter(countries__isnull=False).all()
annual_cropland_climates = list(set((cm[0], cm[1]) for cm in annual_cropland_soil_types))
annual_cropland_moistures = list(set(cm[1] for cm in annual_cropland_soil_types))

# Module configurations
MODULE_CONFIGS = {
    "Grassland": {  # Compute # DONE
        "fields": {
            "grassland_management_type_start": models.GrasslandManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "grassland_management_type_w": models.GrasslandManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "is_fire_used_start": [True, False],
            "is_fire_used_w": [True, False],
            "fire_periodicity_start": [1],
            "fire_periodicity_w": [1],
            "fire_impact_start": [1, 0],
            "fire_impact_w": [1, 0],
        },
        "config_name": "grassland",
    },
    "Livestock": {  # Compute # DONE
        "fields": {
            "livestock_category_types": models.LivestockCategoryType.objects.all(),
            "livestock_production_type_start": models.LivestockProductionType.objects.all(),
            "livestock_production_type_w": models.LivestockProductionType.objects.all(),
            "heads_number_start": [1],
            "heads_number_w": [1],
        },
        "config_name": "livestock",
    },
    "AnnualCropland": {  # DONE
        "fields": {
            "region": annual_cropland_regions,
            "climate": annual_cropland_climates,
            "moisture": annual_cropland_moistures,
            "soil_types": annual_cropland_soil_types,
            "land_use_type_start": [models.LandUseType.objects.get(name="Default")],
            "land_use_type_w": [models.LandUseType.objects.get(name="Default")],
            "tillage_management_type_start": models.TillageManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "tillage_management_type_w": models.TillageManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "organic_input_type_start": models.OrganicInputType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "organic_input_type_w": models.OrganicInputType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "residue_management_type_start": models.ResidueManagementType.objects.all(),
            "residue_management_type_w": models.ResidueManagementType.objects.all(),
        },
        "config_name": "annual_cropland",
    },
    "FloodedRice": {  # Skip
        "fields": {
            "water_management_type_before_cultivation_start": models.WaterManagementTypeBeforeCultivation.objects.all(),
            "water_management_type_before_cultivation_w": models.WaterManagementTypeBeforeCultivation.objects.all(),
            "water_management_type_after_cultivation_start": models.WaterManagementTypeAfterCultivation.objects.all(),
            "water_management_type_after_cultivation_w": models.WaterManagementTypeAfterCultivation.objects.all(),
            "organic_amendment_type_start": models.OrganicAmendmentType.objects.all(),
            "organic_amendment_type_w": models.OrganicAmendmentType.objects.all(),
        },
        "config_name": "flooded_rice",
    },
    "PerennialCropland": {  # Skip
        "fields": {
            "land_use_type_start": models.LandUseType.objects.filter(module_types__name="Perennial Cropland").all(),
            "land_use_type_w": models.LandUseType.objects.filter(module_types__name="Perennial Cropland").all(),
            "organic_input_type_start": models.OrganicInputType.objects.filter(is_active=True).all(),
            "organic_input_type_w": models.OrganicInputType.objects.filter(is_active=True).all(),
            "tillage_management_type_start": models.TillageManagementType.objects.all(),
            "tillage_management_type_w": models.TillageManagementType.objects.all(),
            "is_biomass_burned_start": [True, False],
            "is_biomass_burned_w": [True, False],
            "fire_periodicity_t2_start": [1],
            "fire_periodicity_t2_w": [1],
        },
        "config_name": "perennial_cropland",
    },
    "ForestManagement": {  # Compute
        "fields": {
            "land_use_type_start": models.LandUseType.objects.filter(module_types__name="Forest Management").all(),
            "forest_type": models.ForestType.objects.all(),
            "forest_condition_type": models.ForestConditionType.objects.all(),
            "average_yearly_degradation_percentage_start": [0],
            "average_yearly_degradation_percentage_w": [0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5],  # 1% to 5% and then 10% to 50%
        },
        "config_name": "forest_management",
    },
    "SmallFishery": {  # Compute # DONE
        "fields": {
            "gear_type_start": models.SmallFisheryGearType.objects.all(),
            "gear_type_w": models.SmallFisheryGearType.objects.all(),
            "fishery_type": models.FisheryType.objects.all(),
        },
        "config_name": "small_fishery",
    },
    "LargeFishery": {  # Skip # DONE
        "fields": {
            "gear_type_start": models.LargeFisheryGearType.objects.all(),
            "gear_type_w": models.LargeFisheryGearType.objects.all(),
            "fish_type": models.FishType.objects.all(),
        },
        "config_name": "large_fishery",
    },
    "CoastalWetland": {  # Skip
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland").all(),
            "area_under_drainage_start": [1, 0],
            "area_under_drainage_w": [1, 0],
            "drained_area_excavated_start": [1, 0],
            "drained_area_excavated_w": [1, 0],
            "area_not_drained_or_rewetted_start": [0],
            "area_not_drained_or_rewetted_w": [0],
            "area_w_restored_vegetation_start": [0],
            "area_w_restored_vegetation_w": [0],
        },
        "config_name": "coastal_wetland",
    },
    "CoastalWetland2": {  # Skip
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland").all(),
            "area_under_drainage_start": [0],
            "area_under_drainage_w": [0],
            "drained_area_excavated_start": [0],
            "drained_area_excavated_w": [0],
            "area_not_drained_or_rewetted_start": [1, 0],
            "area_not_drained_or_rewetted_w": [1, 0],
            "area_w_restored_vegetation_start": [1, 0],
            "area_w_restored_vegetation_w": [1, 0],
        },
        "config_name": "coastal_wetland",
    },
    "Input": {  # Compute # BUG: ZERO RESULTS
        "fields": {
            "input_type": models.InputType.objects.all(),
            "value_start": [1, 0],
            "value_w": [1, 0],
        },
        "config_name": "input",
    },
    "Waterbody": {  # Compute # DONE
        "fields": {
            "waterbody_type": models.WaterbodyType.objects.all(),
            "trophic_type_start": models.TrophicType.objects.all(),
            "trophic_type_w": models.TrophicType.objects.all(),
        },
        "config_name": "waterbody",
    },
}

def run():
    # Test with AnnualCropland (paired fields only)
    annual_cropland = MODULE_CONFIGS["AnnualCropland"]
    rows = hamming_shell_rows(annual_cropland["fields"])
    n = expected_count(annual_cropland["fields"])
    print(f"AnnualCropland - Hamming shell count: {n}")
    print(f"AnnualCropland - Hamming shell rows: {len(list(rows))}")
    
    # Test with Input (mixed paired and single fields)
    input_config = MODULE_CONFIGS["Input"]
    input_rows = list(hamming_shell_rows(input_config["fields"]))
    input_n = expected_count(input_config["fields"])
    print(f"\nInput - Hamming shell count: {input_n}")
    print(f"Input - Hamming shell rows: {len(input_rows)}")
    
    # Print a few sample rows to verify input_type is included
    print(f"\nFirst 5 Input module hamming rows:")
    for i, row in enumerate(input_rows[:5]):
        print(f"  Row {i+1}: {row}")
    
    # Check if input_type variations are present
    input_types_found = set()
    for row in input_rows:
        if 'input_type' in row:
            input_types_found.add(str(row['input_type']))
    print(f"\nUnique input_type values found in hamming rows: {len(input_types_found)}")
    if input_types_found:
        print(f"Sample input_type values: {list(input_types_found)[:3]}")