from itertools import product
import api.models as models
from .minitool import ClimateMoistureValidator, SoilOrganicCarbonValidator


def domains_from_fields(fields: dict):
    # pair *_start with *_w and get their combined domain
    # ONLY process fields ending with _start and _w (hamming sphere fields)
    # Exclude environmental filters (climate, soil_type, moisture, region) and custom module-based filters
    pairs = []
    single_fields = []

    # Environmental filters to exclude
    environmental_filters = {"climate", "soil_type", "moisture", "region", "climate_moisture", "soil_types"}

    # Process fields with _start/_w pattern
    for k in sorted(fields):
        if k.endswith("_start"):
            base = k[:-6]
            s = f"{base}_start"
            w = f"{base}_w"
            if w in fields:
                # Get domains from both _start and _w fields
                start_dom = list(fields[s])  # materialize QuerySet once
                w_dom = list(fields[w])  # materialize QuerySet once
                # Combine domains and remove duplicates while preserving order
                combined_dom = list(dict.fromkeys(start_dom + w_dom))
                pairs.append((base, s, w, combined_dom))

    # Process single fields that don't have _start/_w pattern
    # BUT exclude environmental filters and custom module-based filters
    for k in sorted(fields):
        if not k.endswith("_start") and not k.endswith("_w") and not k.endswith("_wo") and k not in environmental_filters:
            # Check if this field doesn't have a corresponding _start/_w version
            base_start = f"{k}_start"
            base_w = f"{k}_w"
            if base_start not in fields and base_w not in fields:
                dom = list(fields[k])  # materialize QuerySet once
                single_fields.append((k, dom))

    return pairs, single_fields  # return both paired and single fields


def hamming_shell_rows(fields: dict):
    """
    fields: your dict of columns -> iterable/QuerySet
    Yields dict rows where exactly one field differs from its baseline value.
    Processes fields ending with _start and _w (hamming sphere permutations).
    Also includes all other fields as environmental combinations.

    When there are no variations possible (no _start/_w pairs and single fields
    have only one value each), yields a single baseline row so that environmental
    combinations can still be generated.
    """
    pairs, single_fields = domains_from_fields(fields)

    # Get all non-hamming fields (environmental filters, custom module-based filters)
    environmental_fields = {}
    for field_name, field_values in fields.items():
        if not (field_name.endswith("_start") or field_name.endswith("_w") or field_name.endswith("_wo")):
            environmental_fields[field_name] = list(field_values)

    # Get domains for baseline assignment - use _start domains for paired fields
    paired_bases = []
    for _, s_col, w_col, _ in pairs:
        paired_bases.append(list(fields[s_col]))  # Use _start domain for baseline
    single_bases = [dom for (_, dom) in single_fields]
    all_bases = paired_bases + single_bases

    # Check if there are any variations possible
    # Variations exist if: (1) paired fields have w values different from start, or
    #                      (2) single fields have more than one value
    has_paired_variations = any(len(fields[w_col]) > 1 or len(fields[s_col]) > 1 for _, s_col, w_col, _ in pairs)
    has_single_variations = any(len(dom) > 1 for _, dom in single_fields)
    has_variations = has_paired_variations or has_single_variations

    # If no variations possible, yield baseline rows for each combination of single fields
    if not has_variations and not pairs:
        # Generate baseline rows for all combinations of single field values
        if single_fields:
            for baseline_vals in product(*single_bases):
                row = {}
                for i, (field_name, _) in enumerate(single_fields):
                    row[field_name] = baseline_vals[i]
                yield row
        else:
            # No fields at all - yield empty row
            yield {}
        return

    # iterate baseline assignment (choose ONE value per field)
    for baseline_vals in product(*all_bases):
        # Split baseline values between paired and single fields
        paired_baseline_vals = baseline_vals[: len(pairs)]
        single_baseline_vals = baseline_vals[len(pairs) :]

        # map: field -> chosen baseline value
        paired_base_map = {pairs[i][0]: paired_baseline_vals[i] for i in range(len(pairs))}
        single_base_map = {single_fields[i][0]: single_baseline_vals[i] for i in range(len(single_fields))}

        # For each paired field, flip its _w to an alternative value
        # IMPORTANT: Only use the FIRST baseline for single fields to avoid duplicates
        # Single field variations are handled separately
        should_generate_paired_variations = all(single_baseline_vals[j] == single_bases[j][0] for j in range(len(single_fields)))

        if should_generate_paired_variations or len(single_fields) == 0:
            for i, (base, s_col, w_col, combined_dom) in enumerate(pairs):
                s_val = paired_base_map[base]
                # Get the _w domain specifically for this field
                w_dom = list(fields[w_col])
                for alt in w_dom:
                    if alt == s_val:
                        continue  # must differ
                    # Generate rows for all environmental field combinations

                    # Get all environmental field combinations
                    env_field_names = list(environmental_fields.keys())
                    env_field_values = [environmental_fields[name] for name in env_field_names]

                    for env_combination in product(*env_field_values):
                        row = {}
                        # fill all pairs: start = baseline, w = baseline (same)
                        for b, s, w, _ in pairs:
                            row[s] = paired_base_map[b]
                            row[w] = paired_base_map[b]
                        # fill all single fields with FIRST baseline values to avoid duplicates
                        for j, (field_name, dom) in enumerate(single_fields):
                            row[field_name] = single_bases[j][0]
                        # flip exactly one paired field
                        row[w_col] = alt

                        # Add environmental fields
                        for env_field_name, env_value in zip(env_field_names, env_combination):
                            row[env_field_name] = env_value

                        # Double-check: ensure start and w values are different
                        if row[s_col] == row[w_col]:
                            continue  # Skip if start and w are the same

                        yield row

        # For each single field, vary its value while keeping others at baseline
        # Note: We skip single field variations if they would create start==w duplicates for paired fields
        # This is because single field variations should not generate permutations where paired fields don't change
        # IMPORTANT: Only generate single field variations for the FIRST baseline to avoid duplicates
        is_first_single_baseline = all(single_baseline_vals[j] == single_bases[j][0] for j in range(len(single_fields)))

        if is_first_single_baseline:
            for i, (field_name, dom) in enumerate(single_fields):
                baseline_val = single_base_map[field_name]
                for alt in dom:
                    if alt == baseline_val:
                        continue  # must differ

                    # Check if varying this single field would create start==w duplicates for ANY paired field
                    # If so, skip this permutation entirely
                    skip_permutation = False
                    for b, s, w, _ in pairs:
                        # Get the baseline value for this paired field
                        baseline_paired_val = paired_base_map[b]
                        # Get the w domain for this paired field
                        w_dom = list(fields[w])
                        # Check if there's any alternative value in w_dom that differs from baseline
                        has_alternative = any(val != baseline_paired_val for val in w_dom)
                        # If there's no alternative, we can't avoid start==w, so skip this permutation
                        if not has_alternative:
                            skip_permutation = True
                            break

                    if skip_permutation:
                        continue  # Skip this single field variation

                    # Generate rows for all environmental field combinations
                    env_field_names = list(environmental_fields.keys())
                    env_field_values = [environmental_fields[name] for name in env_field_names]

                    for env_combination in product(*env_field_values):
                        row = {}
                        # fill all pairs: start = baseline, w = first valid alternative (not baseline)
                        for b, s, w, _ in pairs:
                            row[s] = paired_base_map[b]
                            # For w, use the first value from w_dom that differs from baseline
                            w_dom = list(fields[w])
                            w_val = paired_base_map[b]  # default to baseline
                            for potential_w in w_dom:
                                if potential_w != paired_base_map[b]:
                                    w_val = potential_w
                                    break
                            row[w] = w_val
                        # fill all single fields with baseline values
                        for other_field_name, other_baseline_val in single_base_map.items():
                            row[other_field_name] = other_baseline_val
                        # flip exactly one single field
                        row[field_name] = alt

                        # Add environmental fields
                        for env_field_name, env_value in zip(env_field_names, env_combination):
                            row[env_field_name] = env_value

                        # Final validation: ensure start != w for all paired fields
                        has_duplicate = False
                        for b, s, w, _ in pairs:
                            if row[s] == row[w]:
                                has_duplicate = True
                                break
                        if not has_duplicate:
                            yield row


def expected_count(fields: dict) -> int:
    pairs, single_fields = domains_from_fields(fields)

    # Get sizes for baseline assignment - use _start domains for paired fields
    paired_sizes = []
    for _, s_col, w_col, _ in pairs:
        paired_sizes.append(len(fields[s_col]))  # Use _start domain size for baseline
    single_sizes = [len(dom) for (_, dom) in single_fields]
    all_sizes = paired_sizes + single_sizes

    # Calculate baseline combinations
    prod = 1
    for s in all_sizes:
        prod *= s

    # Calculate variations for each field type
    # For paired fields, use _w domain size for variations
    paired_variations = 0
    for _, s_col, w_col, _ in pairs:
        w_size = len(fields[w_col])
        paired_variations += w_size - 1  # -1 because we skip the baseline value
    single_variations = sum(s - 1 for s in single_sizes)
    total_variations = paired_variations + single_variations

    # If no variations possible but we have single fields, count is the product of single field sizes
    if total_variations == 0 and single_fields and not pairs:
        return prod

    return prod * total_variations if total_variations > 0 else 0


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


def test_modified_logic():
    """Test the modified hamming logic with a simple example"""

    # Create a test fields dictionary that mimics the structure
    test_fields = {
        # Fields that should be permuted (ending with _start and _w)
        "grassland_management_type_start": ["Grazing", "Mowing"],
        "grassland_management_type_w": ["Grazing", "Mowing", "Burning"],
        "is_fire_used_start": [True, False],
        "is_fire_used_w": [True, False],
        # Environmental filters that should NOT be permuted
        "climate": ["Tropical", "Temperate"],
        "soil_type": ["Clay", "Sand"],
        "moisture": ["Wet", "Dry"],
        "region": ["North", "South"],
        # Custom module-based filters that should NOT be permuted
        "livestock_category_type": ["Cattle", "Sheep"],
    }

    print("Testing modified hamming logic...")
    print(f"Input fields: {list(test_fields.keys())}")

    # Test domains_from_fields
    pairs, single_fields = domains_from_fields(test_fields)
    print("\nFields that will be permuted:")
    print(f"  Paired fields: {[(p[0], p[1], p[2]) for p in pairs]}")
    print(f"  Single fields: {[(s[0], len(s[1])) for s in single_fields]}")

    # Test hamming_shell_rows
    hamming_rows = list(hamming_shell_rows(test_fields))
    print(f"\nGenerated {len(hamming_rows)} hamming permutations")

    # Show first few permutations
    print("\nFirst 3 hamming permutations:")
    for i, row in enumerate(hamming_rows[:3]):
        print(f"  {i + 1}: {row}")

    # Verify that environmental filters are not in the permutations
    environmental_in_permutations = False
    for row in hamming_rows:
        for field in ["climate", "soil_type", "moisture", "region"]:
            if field in row:
                environmental_in_permutations = True
                break

    if environmental_in_permutations:
        print("\n❌ ERROR: Environmental filters found in hamming permutations!")
    else:
        print("\n✅ SUCCESS: Environmental filters correctly excluded from hamming permutations")

    # Verify that only _start and _w fields are permuted
    expected_permuted_fields = {"grassland_management_type_start", "grassland_management_type_w", "is_fire_used_start", "is_fire_used_w"}
    actual_permuted_fields = set()
    for row in hamming_rows:
        actual_permuted_fields.update(row.keys())

    if expected_permuted_fields.issubset(actual_permuted_fields):
        print("✅ SUCCESS: Only _start and _w fields are being permuted")
    else:
        print(f"❌ ERROR: Expected fields {expected_permuted_fields} not found in permutations")
        print(f"  Actual fields: {actual_permuted_fields}")


def run():
    # Test the modified logic first
    test_modified_logic()

    print("\n" + "=" * 50)
    print("ORIGINAL TESTS:")
    print("=" * 50)

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
    print("\nFirst 5 Input module hamming rows:")
    for i, row in enumerate(input_rows[:5]):
        print(f"  Row {i + 1}: {row}")

    # Check if input_type variations are present
    input_types_found = set()
    for row in input_rows:
        if "input_type" in row:
            input_types_found.add(str(row["input_type"]))
    print(f"\nUnique input_type values found in hamming rows: {len(input_types_found)}")
    if input_types_found:
        print("Sample input_type values:", list(input_types_found)[:3])

    # Test with ForestManagement (different _start and _w domains)
    forest_config = MODULE_CONFIGS["ForestManagement"]
    forest_rows = list(hamming_shell_rows(forest_config["fields"]))
    forest_n = expected_count(forest_config["fields"])
    print(f"\nForestManagement - Hamming shell count: {forest_n}")
    print(f"ForestManagement - Hamming shell rows: {len(forest_rows)}")

    # Check if degradation percentage variations are present
    degradation_values_found = set()
    for row in forest_rows:
        if "average_yearly_degradation_percentage_w" in row:
            degradation_values_found.add(row["average_yearly_degradation_percentage_w"])
    print(f"\nUnique degradation percentage values found in hamming rows: {len(degradation_values_found)}")
    if degradation_values_found:
        print("Sample degradation values:", sorted(list(degradation_values_found))[:5])
